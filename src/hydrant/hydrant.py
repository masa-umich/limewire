import asyncio
import json
import pathlib
from datetime import datetime

from nicegui import app, client, ui

from lmp import DeviceCommandAckMessage, DeviceCommandMessage
from lmp.util import Board, DeviceCommand

from .device_command_history import DeviceCommandHistoryEntry
from .hydrant_error_ui import EventLogListener, EventLogUI, LogTable
from .hydrant_system_config import (
    DEFAULT_BB1_IP,
    DEFAULT_BB2_IP,
    DEFAULT_BB3_IP,
    DEFAULT_FC_IP,
    DEFAULT_FR_IP,
)
from .hydrant_telemetry import BoardTelemetryUI, TelemetryListener
from .hydrant_ui import (
    BBConfigUI,
    FCConfigUI,
    FRConfigUI,
    IPAddressUI,
    SystemConfigUI,
)


class Hydrant:
    def __init__(self, fc_address: tuple[str, int], log_table: pathlib.Path):
        self.fc_address = fc_address
        self.log_lookup = None
        if log_table is not None:
            if log_table.suffix == ".csv":
                try:
                    self.log_lookup = LogTable(log_table)
                except Exception as err:
                    print("Failed to parse error lookup table " + str(err))
            else:
                print("Error lookup table file must be .csv")
        channels_file = (
            pathlib.Path(__file__).parent.parent
            / "limewire"
            / "data"
            / "channels.json"
        )
        with channels_file.open() as f:
            self.channels: dict[str, list[str]] = json.load(f)
        self.boards_available = {board.pretty_name: board for board in Board}
        self.commands_available = {cmd.name: cmd for cmd in DeviceCommand}

        # Initially not assigned; updates on user input
        self.board_select = None
        self.command_select = None
        self.confirm_label = None
        self.selected_board_name = None
        self.selected_command_name = None

        self.start_fc_connection_status = False

        self.fc_writer = None
        self.fc_reader = None

        self.device_command_history: list[DeviceCommandHistoryEntry] = []
        self.device_command_recency: dict[
            tuple[Board, DeviceCommand],
            DeviceCommandHistoryEntry,
        ] = {}

        self.log_listener = Event_Log_Listener()
        self.telem_listener = TelemetryListener()
        app.on_startup(self.connect_to_fc())
        app.on_startup(self.log_listener.open_listener())
        app.on_startup(self.telem_listener.open_listener())

    async def connect_to_fc(self):
        """Maintain connection to flight computer."""
        while True:
            self.fc_reader = None
            self.fc_writer = None
            try:
                self.start_fc_connection_status = False
                self.fc_connection_status.set_visibility(True)
            except AttributeError:
                pass
            try:
                print(
                    f"Connecting to FC at {self.fc_address[0]}:{self.fc_address[1]}..."
                )
                self.fc_reader, self.fc_writer = await asyncio.open_connection(
                    *self.fc_address
                )
                print("Connection successful.")
            except (ConnectionRefusedError, TimeoutError, OSError):
                await asyncio.sleep(1)
                continue

            try:
                self.start_fc_connection_status = True
                self.fc_connection_status.set_visibility(False)
            except AttributeError:
                pass

            fc_listen_task = asyncio.create_task(self.listen_for_acks())

            try:
                await fc_listen_task
            except asyncio.CancelledError:
                print("Hydrant cancelled.")
                break
            except Exception as e:
                print(f"Got exception: {e}")
                continue

    async def listen_for_acks(self):
        while True:
            while self.fc_reader is None:
                await asyncio.sleep(0.5)
            msg_length = await self.fc_reader.read(1)
            if not msg_length:
                break

            msg_length = int.from_bytes(msg_length)
            msg_bytes = await self.fc_reader.readexactly(msg_length)
            if not msg_bytes:
                break

            msg_id = int.from_bytes(msg_bytes[0:1])
            match msg_id:
                case DeviceCommandAckMessage.MSG_ID:
                    msg = DeviceCommandAckMessage.from_bytes(msg_bytes)

                    history_entry = self.device_command_recency.get(
                        (msg.board, msg.command)
                    )
                    if history_entry is None:
                        continue
                    history_entry.set_ack(datetime.now(), msg.response_msg)

                    self.refresh_history_table()
                case _:
                    continue

    def main_page(self, client: client.Client):
        """Generates page outline and GUI"""

        error_log = Event_Log_UI(self.log_lookup)

        ui.page_title("Hydrant")
        ui.dark_mode().enable()

        ui.add_head_html("""
            <style>
            @keyframes flash-red {
            100% { background-color: black; }
            0% { background-color: #942626; }
            }
            </style>
        """)

        # HEADER
        with ui.header().classes(
            "bg-black text-white px-6 py-4 border-b border-gray-700"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.label("HYDRANT").classes(
                    "text-3xl font-extrabold tracking-wider"
                )

        # MAIN PAGE CONTENT
        with ui.row().classes("w-full mx-auto no-wrap") as main_page_content:
            self.main_page_content = main_page_content

            # DEVICE COMMANDS & SYSTEM CONFIGURATION
            with ui.column().classes("w-full p-6 gap-4"):
                with ui.row().classes("w-full no-wrap justify-center relative"):
                    main_page_toggle = (
                        ui.toggle(
                            {
                                1: "Device Commands",
                                2: "System Configuration",
                                3: "Telemetry",
                            },
                            value=1,
                        )
                        .classes("self-center border-2 border-[#2f2d63]")
                        .props('toggle-color="purple"')
                    )
                    ui.button(
                        "Reset", on_click=self.warn_restore_defaults
                    ).classes("absolute right-0").bind_visibility_from(
                        main_page_toggle, "value", backward=lambda v: v == 2
                    )
                with (
                    ui.tab_panels()
                    .classes("w-full bg-[#121212]")
                    .props('animated="false"')
                    .bind_value_from(main_page_toggle, "value")
                ):
                    with ui.tab_panel(1).classes("p-0"):
                        # DEVICE COMMANDS
                        with ui.row().classes(
                            "w-full mx-auto no-wrap h-[27em] gap-0"
                        ):
                            with ui.column().classes("w-1/2 h-full pr-2"):
                                with ui.card().classes(
                                    "w-full bg-gray-900 border border-gray-700 p-6 h-full"
                                ):
                                    ui.label("DEVICE COMMANDS").classes(
                                        "text-xl font-bold text-white mb-4"
                                    )
                                    with ui.column().classes("w-full gap-3"):
                                        # BOARD
                                        ui.label("BOARD").classes(
                                            "text-lg font-bold text-white"
                                        )
                                        # Board selector
                                        self.board_select = ui.select(
                                            label="Select a board",
                                            options=list(
                                                self.boards_available.keys()
                                            ),
                                        ).classes("w-full")
                                        # Command
                                        ui.label("COMMAND").classes(
                                            "text-lg font-bold text-white"
                                        )
                                        self.command_select = ui.select(
                                            label="Select a command",
                                            options=list(
                                                self.commands_available.keys()
                                            ),
                                        ).classes("w-full")
                                        # Dialog that is used for popup
                                        with ui.dialog() as dialog, ui.card():
                                            self.confirm_label = ui.label("")
                                            with ui.row():
                                                ui.button(
                                                    "YES",
                                                    on_click=lambda: self.send_after_confirm(
                                                        dialog
                                                    ),
                                                )
                                                ui.button(
                                                    "NO",
                                                    on_click=lambda: dialog.close(),
                                                )
                                        ui.button(
                                            "SEND",
                                            on_click=lambda: self.send_command(
                                                dialog
                                            ),
                                        ).classes(
                                            "w-half bg-blue-600 text-white hover:bg-blue-700"
                                        )
                            with ui.column().classes("w-1/2 h-full pl-2"):
                                # ERROR LOG
                                with ui.column().classes("w-full gap-4 h-full"):
                                    # ERROR LOG CARD
                                    error_log.display()
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            # COMMAND HISTORY CARD
                            self.command_history_table()
                    with ui.tab_panel(2).classes("p-0"):
                        # SYSTEM CONFIGURATION
                        with ui.row().classes(
                            "w-full mx-auto no-wrap h-[31em] gap-0"
                        ):
                            with ui.column().classes("w-1/2 pr-2 h-full"):
                                self.system_config = SystemConfigUI(
                                    self, self.log_listener
                                )
                            with ui.column().classes("w-1/2 pl-2 h-full"):
                                # ERROR LOG
                                with ui.column().classes("w-full gap-4 h-full"):
                                    # ERROR LOG CARD
                                    error_log.display()
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            # BOARD SPECIFIC CONFIG
                            with ui.card().classes(
                                "w-full bg-gray-900 border border-gray-700 p-6"
                            ):
                                with ui.row().classes("w-full mx-auto no-wrap"):
                                    ui.label("MANUAL BOARD CONFIG").classes(
                                        "text-xl font-bold text-white mb-4"
                                    )
                                    ui.space()
                                    board_config_toggle = (
                                        ui.toggle(
                                            {
                                                1: "Flight Computer",
                                                2: "Bay Board 1",
                                                3: "Bay Board 2",
                                                4: "Bay Board 3",
                                                5: "Flight Recorder",
                                            },
                                            value=1,
                                        )
                                        .classes("border-1 border-[#2f2d63]")
                                        .props(
                                            'toggle-color="lime" toggle-text-color="black"'
                                        )
                                    )
                                    with (
                                        ui.tab_panels()
                                        .classes("bg-gray-900")
                                        .props('animated="false"')
                                        .bind_value_from(
                                            board_config_toggle, "value"
                                        )
                                    ):
                                        with ui.tab_panel(1).classes("p-0"):
                                            self.FC_TFTP_IP = IPAddressUI(
                                                DEFAULT_FC_IP, "TFTP IP"
                                            )
                                        with ui.tab_panel(2).classes("p-0"):
                                            self.BB1_TFTP_IP = IPAddressUI(
                                                DEFAULT_BB1_IP, "TFTP IP"
                                            )
                                        with ui.tab_panel(3).classes("p-0"):
                                            self.BB2_TFTP_IP = IPAddressUI(
                                                DEFAULT_BB2_IP, "TFTP IP"
                                            )
                                        with ui.tab_panel(4).classes("p-0"):
                                            self.BB3_TFTP_IP = IPAddressUI(
                                                DEFAULT_BB3_IP, "TFTP IP"
                                            )
                                        with ui.tab_panel(5).classes("p-0"):
                                            self.FR_TFTP_IP = IPAddressUI(
                                                DEFAULT_FR_IP, "TFTP IP"
                                            )
                                ui.separator().classes("h-1")
                                with ui.row().classes("w-full mx-auto no-wrap"):
                                    with (
                                        ui.tab_panels()
                                        .classes("w-full bg-gray-900")
                                        .props('animated="false"')
                                        .bind_value_from(
                                            board_config_toggle, "value"
                                        )
                                    ):
                                        with ui.tab_panel(1).classes("p-0"):
                                            self.FC_config = FCConfigUI()
                                        with ui.tab_panel(2).classes("p-0"):
                                            self.BB1_config = BBConfigUI(1)
                                        with ui.tab_panel(3).classes("p-0"):
                                            self.BB2_config = BBConfigUI(2)
                                        with ui.tab_panel(4).classes("p-0"):
                                            self.BB3_config = BBConfigUI(3)
                                        with ui.tab_panel(5).classes("p-0"):
                                            self.FR_config = FR_Config_UI()
                    with ui.tab_panel(3).classes("p-0"):
                        # TELEMETRY
                        with ui.row().classes("w-full no-wrap gap-0 h-[48em]"):
                            # FLIGHT COMPUTER
                            with ui.column().classes("w-1/2 pr-2 h-full"):
                                fc_telemetry = BoardTelemetryUI(
                                    self.channels["fc_timestamp"], Board.FC, 3
                                )
                                self.telem_listener.attach_ui(
                                    fc_telemetry, Board.FC, client
                                )
                            with ui.column().classes("w-1/2 pl-2 h-full"):
                                # ERROR LOG
                                with ui.column().classes("w-full gap-4 h-full"):
                                    # ERROR LOG CARD
                                    error_log.display()
                        with ui.row().classes("w-full no-wrap"):
                            # BAY BOARD
                            with ui.column().classes("w-full h-full"):
                                bb1_telemetry = BoardTelemetryUI(
                                    self.channels["bb1_timestamp"], Board.BB1, 6
                                )
                                self.telem_listener.attach_ui(
                                    bb1_telemetry, Board.BB1, client
                                )
                                bb2_telemetry = BoardTelemetryUI(
                                    self.channels["bb2_timestamp"], Board.BB2, 6
                                )
                                self.telem_listener.attach_ui(
                                    bb2_telemetry, Board.BB2, client
                                )
                                bb3_telemetry = BoardTelemetryUI(
                                    self.channels["bb3_timestamp"], Board.BB3, 6
                                )
                                self.telem_listener.attach_ui(
                                    bb3_telemetry, Board.BB3, client
                                )
                                fr_telemetry = BoardTelemetryUI(
                                    self.channels["fr_timestamp"], Board.FR, 5
                                )
                                self.telem_listener.attach_ui(
                                    fr_telemetry, Board.FR, client
                                )
        # FC CONNECTION DIV
        with (
            ui.element("div")
            .style(
                "position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 1000; box-shadow: 0 0 0.5em #7f9fbf35; background-color: black;"
            )
            .classes("rounded-sm") as fc_conn_stat
        ):
            self.fc_connection_status = fc_conn_stat
            fc_conn_stat.set_visibility(not self.start_fc_connection_status)
            with ui.card().classes(
                "bg-transparent text-white p-6 pl-4 shadow-lg"
            ):
                with ui.row().classes("no-wrap"):
                    ui.icon("error", color="yellow")
                    with ui.column():
                        ui.label("Flight Computer disconnected.").classes(
                            "text-bold"
                        )
                        ui.label("Trying to reconnect...")
        ui.space().classes("h-32")  # for better scrolling

        self.log_listener.attach_ui(error_log, client)

    def warn_restore_defaults(self):
        with (
            ui.dialog() as dialog,
            ui.card().classes(
                "w-100 h-30 flex flex-col justify-center items-center"
            ),
        ):
            ui.button(icon="close", on_click=lambda e: dialog.close()).classes(
                "absolute right-0 top-0 bg-transparent"
            ).props('flat color="white" size="lg"')
            ui.label("Confirm reset to defaults").classes("text-xl")
            ui.button(
                "Confirm",
                on_click=lambda e: (self.restore_defaults(), dialog.close()),
            )
            dialog.open()

    def restore_defaults(self):
        self.system_config.ICD_config = None
        self.FC_TFTP_IP.set_ip(DEFAULT_FC_IP)
        self.BB1_TFTP_IP.set_ip(DEFAULT_BB1_IP)
        self.BB2_TFTP_IP.set_ip(DEFAULT_BB2_IP)
        self.BB3_TFTP_IP.set_ip(DEFAULT_BB3_IP)
        self.FR_TFTP_IP.set_ip(DEFAULT_FR_IP)

        self.FC_config.restore_defaults()
        self.BB1_config.restore_defaults()
        self.BB2_config.restore_defaults()
        self.BB3_config.restore_defaults()
        self.FR_config.restore_defaults()

        self.system_config.reset_progress_indicators()
        self.system_config.ICD_file.reset()
        self.system_config.ICD_config = None

    def send_command(self, dialog):
        """Initialize send command process on button press"""

        if self.board_select.value is None or self.command_select.value is None:
            return
        self.selected_board_name = self.board_select.value
        self.selected_command_name = self.command_select.value

        self.confirm_label.text = (
            f"Are you sure you want to send command '{self.selected_command_name}' "
            f"to board '{self.selected_board_name}'?"
        )

        dialog.open()

    async def send_after_confirm(self, dialog):
        """Send command to board after confirmation"""
        dialog.close()
        self.selected_board_name = self.board_select.value
        self.selected_command_name = self.command_select.value

        self.board = self.boards_available[self.selected_board_name]
        self.command = self.commands_available[self.selected_command_name]
        if self.fc_writer:
            msg = DeviceCommandMessage(self.board, self.command)
            msg_bytes = bytes(msg)

            print(
                f"Sending {self.selected_command_name} to board {self.selected_board_name}"
            )
            self.fc_writer.write(len(msg_bytes).to_bytes(1) + msg_bytes)
            await self.fc_writer.drain()

            new_entry = DeviceCommandHistoryEntry(
                board=msg.board,
                command=msg.command,
                send_time=datetime.now(),
            )
            self.device_command_history.append(new_entry)
            self.device_command_recency[(msg.board, msg.command)] = new_entry
        else:
            self.fc_connection_status.classes(
                add="animate-[flash-red_1s_ease-in-out_1]"
            )
            ui.timer(
                1,
                lambda: self.fc_connection_status.classes(
                    remove="animate-[flash-red_1s_ease-in-out_1]"
                ),
                active=True,
                once=True,
            )
        self.refresh_history_table()

    def refresh_history_table(self):
        self.cmd_history_grid.options["rowData"] = self.history_dict()
        self.cmd_history_grid.update()

    def command_history_table(self):
        with ui.card().classes(
            "w-full bg-gray-900 border border-gray-700 p-6"
        ) as card:
            ui.label("Command History").classes(
                "text-xl font-bold text-blue-400 mb-4"
            )

            history_column = ui.column().classes("w-full overflow-y-auto")

            column_defs = []
            for field in DeviceCommandHistoryEntry.fields():
                col_def = {"field": field}
                col_def["tooltipField"] = field
                if field == "Send Time":
                    col_def["sort"] = "desc"

                if field == "ACK?":
                    col_def["width"] = 100
                    col_def["maxWidth"] = 100
                elif field == "ACK Message":
                    pass
                else:
                    col_def["maxWidth"] = 210
                column_defs.append(col_def)

            with history_column:
                self.cmd_history_grid = ui.aggrid(
                    {
                        "columnDefs": column_defs,
                        "rowData": self.history_dict(),
                        "defaultColDef": {
                            "filter": True,
                            "sortable": True,
                            "floatingFilter": True,
                        },
                    }
                )

        return card

    def history_dict(self):
        return [entry.to_gui_dict() for entry in self.device_command_history]
