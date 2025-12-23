import asyncio
from datetime import datetime

from nicegui import app, ui

from lmp import DeviceCommandAckMessage, DeviceCommandMessage
from lmp.util import Board, DeviceCommand

from .device_command_history import DeviceCommandHistoryEntry


class Hydrant:
    def __init__(self, fc_address: tuple[str, int]):
        self.fc_address = fc_address

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

        app.on_startup(self.connect_to_fc())

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
            except (ConnectionRefusedError, TimeoutError):
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

    def main_page(self):
        """Generates page outline and GUI"""
            
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
                main_page_toggle = ui.toggle({1: "Device Commands", 2: "System Configuration", 3: "Event Log"}, value=1).classes("self-center border-2 border-[#2f2d63]").props('toggle-color="purple"')
                with ui.tab_panels().classes("w-full bg-[#121212]").props('animated="false"').bind_value_from(main_page_toggle, "value"):
                    with ui.tab_panel(1).classes("p-0"):
                        # DEVICE COMMANDS
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            with ui.column().classes("w-full"):
                                with ui.card().classes(
                                    "w-full bg-gray-900 border border-gray-700 p-6"
                                ):
                                    ui.label("DEVICE COMMANDS").classes(
                                        "text-xl font-bold text-white mb-4"
                                    )
                                    with ui.column().classes("w-full gap-3"):
                                        # BOARD
                                        ui.label("BOARD").classes("text-lg font-bold text-white")
                                        # Board selector
                                        self.board_select = ui.select(
                                            label="Select a board",
                                            options=list(self.boards_available.keys()),
                                        ).classes("w-full")
                                        # Command
                                        ui.label("COMMAND").classes("text-lg font-bold text-white")
                                        self.command_select = ui.select(
                                            label="Select a command",
                                            options=list(self.commands_available.keys()),
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
                                                ui.button("NO", on_click=lambda: dialog.close())
                                        ui.button(
                                            "SEND", on_click=lambda: self.send_command(dialog)
                                        ).classes("w-half bg-blue-600 text-white hover:bg-blue-700")
                            with ui.column().classes("w-full"):
                                # ERROR LOG
                                with ui.column().classes("w-full gap-4"):
                                    # ERROR LOG CARD
                                    with ui.card().classes("w-full bg-gray-900 border border-gray-700 p-6"):
                                        ui.label("Error Log").classes("text-xl font-bold text-red-400 mb-4")
                                        error_column = ui.column().classes("w-full overflow-y-auto")
                                        with error_column:
                                            ui.label("Errors will appear here").classes("text-gray-500 italic")
                                            ui.image('lebron.png').classes('w-64 h-auto rounded-lg')
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            # COMMAND HISTORY CARD
                            self.command_history_table()
                    with ui.tab_panel(2).classes("p-0"):
                        # SYSTEM CONFIGURATION
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            with ui.column().classes("w-full"):
                                with ui.card().classes("w-full bg-gray-900 border border-gray-700 p-6"):
                                    with ui.row().classes("w-full mx-auto no-wrap"):
                                        with ui.column().classes():
                                            ui.label("SYSTEM CONFIG").classes("text-xl font-bold text-white mb-4")
                                            ui.upload(label="Load from ICD").props('accept=.csv,.xlsx no-thumbnails no-icon auto__false color=lime text-color=black')
                                            ui.button("Write Configuration", color="orange").classes("text-base w-full")
                                        with ui.column().classes("gap-0 pl-10"):
                                            ui.checkbox().classes("h-11")
                                            ui.checkbox("EBox").classes("h-8")
                                            ui.checkbox("Flight Computer").classes("h-8")
                                            ui.checkbox("Bay Board 1 (Press)").classes("h-8")
                                            ui.checkbox("Bay Board 2 (Intertank)").classes("h-8")
                                            ui.checkbox("Bay Board 3 (Engine)").classes("h-8")
                                            ui.checkbox("Flight Recorder").classes("h-8")
                                    ui.separator().classes("w-full h-1")
                                    ui.label("Progress").classes("self-center text-lg")
                                    with ui.row().classes("w-full mx-auto no-wrap gap-0 justify-between"):
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('EBox').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('Flight Computer').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('Bay Board 1').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('Bay Board 2').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('Bay Board 3').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                        with ui.column().classes('items-center gap-0'):
                                            ui.label('Flight Recorder').classes('text-sm')
                                            ui.checkbox('').classes("h-10").props("disable")
                                    
                            with ui.column().classes("w-full"):
                                # ERROR LOG
                                with ui.column().classes("w-full gap-4"):
                                    # ERROR LOG CARD
                                    with ui.card().classes("w-full bg-gray-900 border border-gray-700 p-6"):
                                        ui.label("Error Log").classes("text-xl font-bold text-red-400 mb-4")

                                        error_column = ui.column().classes("w-full overflow-y-auto")
                                        with error_column:
                                            ui.label("Errors will appear here").classes("text-gray-500 italic")
                                            ui.image('lebron.png').classes('w-64 h-auto rounded-lg')
                        with ui.row().classes("w-full mx-auto no-wrap"):
                            # BOARD SPECIFIC CONFIG
                            with ui.card().classes("w-full bg-gray-900 border border-gray-700 p-6"):
                                with ui.row().classes("w-full mx-auto no-wrap"):
                                    ui.label("MANUAL BOARD CONFIG").classes("text-xl font-bold text-white mb-4")
                                    ui.space()
                                    board_config_toggle = ui.toggle({1: "Flight Computer", 2: "Bay Board 1", 3: "Bay Board 2", 4: "Bay Board 3", 5: "Flight Recorder"}, value=1).classes("border-1 border-[#2f2d63]").props('toggle-color="lime" toggle-text-color="black"')
                                    with ui.row().classes("no-wrap items-end gap-1"):
                                        ui.label("TFTP IP Override: ").classes("self-center")
                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                        ui.label(".")
                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                        ui.label(".")
                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                        ui.label(".")
                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                ui.separator().classes("h-1")
                                with ui.row().classes("w-full mx-auto no-wrap"):
                                    with ui.tab_panels().classes("w-full bg-gray-900").props('animated="false"').bind_value_from(board_config_toggle, "value"):
                                        with ui.tab_panel(1).classes("p-0"):
                                            #FC
                                            with ui.column().classes("h-full w-full"):
                                                with ui.row().classes("w-full mx-auto no-wrap flex items-stretch h-full"):
                                                    # PTs
                                                    with ui.column().classes("border-1 p-2 border-gray-500 flex-1 basis-auto"):
                                                        with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                                                            for x in range(5):
                                                                with ui.column().classes("w-full gap-1"):
                                                                    ui.label("PT " + str(x + 1) + "").classes("pb-1 pl-2")
                                                                    ui.separator()
                                                                    ui.number(label="Range", value=1000, precision=0).props("filled dense")
                                                                    ui.number(label="Offset", value=0.5, precision=1).props("filled dense")
                                                                    ui.number(label="Max", value=4.5, precision=1).props("filled dense")
                                                    # TCs
                                                    with ui.column().classes("border-1 p-2 border-gray-500 gap-3 flex-1 basis-auto justify-center"):
                                                        with ui.column().classes("w-full gap-3"):
                                                            for x in range(3):
                                                                with ui.row().classes("w-full mx-auto no-wrap gap-1 items-center"):
                                                                    ui.label("TC " + str(x + 1) + " ").classes("min-w-10")
                                                                    ui.select([1, 2, 4, 8, 16, 32, 64, 128], value=1, label="Gain").props("filled dense").classes("min-w-25")
                                                    # Valves
                                                    with ui.column().classes("border-1 p-2 border-gray-500 flex-1 basis-auto"):
                                                        with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                                                            for x in range(3):
                                                                with ui.column().classes("w-full gap-1"):
                                                                    ui.label("Valve " + str(x + 1) + "").classes("pb-1 pl-2")
                                                                    ui.separator()
                                                                    #ui.checkbox("Enabled")
                                                                    ui.switch("Enabled")
                                                                    ui.select([12, 24], value=24, label="Voltage").props("filled dense").classes("min-w-25")
                                                with ui.row().classes("w-full mx-auto no-wrap flex items-stretch h-full border-1 p-2 border-gray-500"):
                                                    # IP Addresses
                                                    with ui.column().classes("w-full"):
                                                        with ui.column().classes("w-fit items-end"):
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Limewire IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Flight Computer IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    with ui.column().classes("w-full"):
                                                        with ui.column().classes("w-fit items-end"):
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Bay Board 1 IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Bay Board 2 IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    with ui.column().classes("w-full"):
                                                        with ui.column().classes("w-fit items-end"):
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Bay Board 3 IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                            with ui.row().classes("no-wrap items-end gap-1"):
                                                                ui.label("Flight Recorder IP: ").classes("self-center")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                                ui.label(".")
                                                                ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                        with ui.tab_panel(2).classes("p-0"):
                                            with ui.column().classes("h-full w-full"):
                                                # PTs
                                                with ui.row().classes("w-full mx-auto no-wrap flex items-stretch h-full"):
                                                    with ui.column().classes("border-1 p-2 border-gray-500 flex-1 basis-auto"):
                                                        with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                                                            for x in range(10):
                                                                with ui.column().classes("w-full gap-1"):
                                                                    ui.label("PT " + str(x + 1) + "").classes("pb-1 pl-2")
                                                                    ui.separator()
                                                                    ui.number(label="Range", value=1000, precision=0).props("filled dense")
                                                                    ui.number(label="Offset", value=0.5, precision=1).props("filled dense")
                                                                    ui.number(label="Max", value=4.5, precision=1).props("filled dense")
                                                with ui.row().classes("w-full mx-auto no-wrap flex items-stretch h-full"):
                                                    # TCs
                                                    with ui.column().classes("border-1 p-2 border-gray-500 gap-3 flex-1 basis-auto justify-center"):
                                                        with ui.row().classes("w-full mx-auto no-wrap"):
                                                            with ui.column().classes("w-full gap-3"):
                                                                for x in range(3):
                                                                    with ui.row().classes("w-full mx-auto no-wrap gap-1 items-center"):
                                                                        ui.label("TC " + str(x + 1) + " ").classes("min-w-10")
                                                                        ui.select([1, 2, 4, 8, 16, 32, 64, 128], value=1, label="Gain").props("filled dense").classes("min-w-25")
                                                            with ui.column().classes("w-full gap-3"):
                                                                for x in range(3):
                                                                    with ui.row().classes("w-full mx-auto no-wrap gap-1 items-center"):
                                                                        ui.label("TC " + str(x + 1) + " ").classes("min-w-10")
                                                                        ui.select([1, 2, 4, 8, 16, 32, 64, 128], value=1, label="Gain").props("filled dense").classes("min-w-25")
                                                    # Valves
                                                    with ui.column().classes("border-1 p-2 border-gray-500 flex-1 basis-auto"):
                                                        with ui.row().classes("w-full mx-auto no-wrap gap-3"):
                                                            for x in range(5):
                                                                with ui.column().classes("w-full gap-1"):
                                                                    ui.label("Valve " + str(x + 1) + "").classes("pb-1 pl-2")
                                                                    ui.separator()
                                                                    #ui.checkbox("Enabled")
                                                                    ui.switch("Enabled")
                                                                    ui.select([12, 24], value=24, label="Voltage").props("filled dense").classes("min-w-25")
                                                with ui.row().classes("w-full no-wrap justify-center h-full border-1 p-2 border-gray-500"):
                                                    # IP Addresses
                                                    ui.space()
                                                    with ui.row().classes("no-wrap items-end gap-1"):
                                                        ui.label("Bay Board IP: ").classes("self-center")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    ui.space()
                                                    with ui.row().classes("no-wrap items-end gap-1"):
                                                        ui.label("Flight Computer IP: ").classes("self-center")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    ui.space()
                                        with ui.tab_panel(3).classes("p-0"):
                                            ui.label("BB2")
                                        with ui.tab_panel(4).classes("p-0"):
                                            ui.label("BB3")
                                        with ui.tab_panel(5).classes("p-0"):
                                            with ui.column().classes("h-full w-full"):
                                                with ui.row().classes("w-full no-wrap justify-center h-full border-1 p-2 border-gray-500"):
                                                    # IP Addresses
                                                    ui.space()
                                                    with ui.row().classes("no-wrap items-end gap-1"):
                                                        ui.label("Flight Recorder IP: ").classes("self-center")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    ui.space()
                                                    with ui.row().classes("no-wrap items-end gap-1"):
                                                        ui.label("Flight Computer IP: ").classes("self-center")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                        ui.label(".")
                                                        ui.input().props("dense outlined").classes("min-w-[4em] w-[4em]")
                                                    ui.space()
        # FC CONNECTION DIV
        with ui.element('div').style('position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 1000; box-shadow: 0 0 0.5em #7f9fbf35; background-color: black;').classes("") as fc_conn_stat:
            self.fc_connection_status = fc_conn_stat
            fc_conn_stat.set_visibility(self.start_fc_connection_status == False)
            with ui.card().classes('bg-transparent text-white p-6 pl-4 shadow-lg'):
                with ui.row().classes("no-wrap"):
                    ui.icon("error", color="yellow")
                    with ui.column():
                        ui.label('Flight Computer disconnected.').classes("text-bold")
                        ui.label('Trying to reconnect...')
        ui.space().classes("h-32")



    def send_command(self, dialog):
        """Initialize send command process on button press"""
        
        if(self.board_select.value == None or self.command_select.value == None): return
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
        if(self.fc_writer):
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
            self.fc_connection_status.classes(add="animate-[flash-red_1s_ease-in-out_1]")
            ui.timer(1, lambda: self.fc_connection_status.classes(remove='animate-[flash-red_1s_ease-in-out_1]'), active=True, once=True)
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
