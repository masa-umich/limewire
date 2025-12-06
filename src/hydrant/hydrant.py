import asyncio
from datetime import datetime

from loguru import logger
from nicegui import app, ui

from lmp import DeviceCommandAckMessage, DeviceCommandMessage
from lmp.framer import FramingError, LMPFramer
from lmp.util import Board, DeviceCommand

from .device_command_history import DeviceCommandHistoryEntry


class Hydrant:
    def __init__(self, fc_address: tuple[str, int]):
        logger.info("! HYDRANT RUNNING !")
        self.fc_address = fc_address

        self.boards_available = {board.name: board for board in Board}
        self.commands_available = {cmd.name: cmd for cmd in DeviceCommand}

        # Initially not assigned; updates on user input
        self.board_select = None
        self.command_select = None
        self.confirm_label = None
        self.selected_board_name = None
        self.selected_command_name = None

        self.device_command_history: list[DeviceCommandHistoryEntry] = []
        self.device_command_recency: dict[
            tuple[Board, DeviceCommand],
            DeviceCommandHistoryEntry,
        ] = {}

        app.on_startup(self.connect_to_fc())

    async def connect_to_fc(self):
        """Maintain connection to flight computer."""
        while True:
            try:
                logger.info(
                    f"Connecting to FC at {self.fc_address[0]}:{self.fc_address[1]}..."
                )
                self.fc_reader, self.fc_writer = await asyncio.open_connection(
                    *self.fc_address
                )

                self.lmp_framer = LMPFramer(self.fc_reader, self.fc_writer)
                logger.info("Connection successful.")
            except ConnectionRefusedError:
                await asyncio.sleep(1)
                continue

            fc_listen_task = asyncio.create_task(self.listen_for_acks())

            try:
                await fc_listen_task
            except asyncio.CancelledError:
                logger.info("Hydrant cancelled.")
                break
            except Exception as e:
                logger.error(f"Got exception: {e}")
                continue

    async def listen_for_acks(self):
        while True:
            try:
                message = await self.lmp_framer.receive_message()
            except (FramingError, ValueError) as err:
                logger.error(str(err))
                logger.opt(exception=err).debug("Traceback", exc_info=True)
                continue

            if not message:
                continue
            if type(message) is DeviceCommandAckMessage:
                history_entry = self.device_command_recency.get(
                    (message.board, message.command)
                )
                if history_entry is None:
                    continue
                history_entry.set_ack(datetime.now(), message.response_msg)

                self.refresh_history_table()

    def main_page(self):
        """Generates page outline and GUI"""

        ui.page_title("Hydrant")
        ui.dark_mode().enable()

        # HEADER
        with ui.header().classes(
            "bg-black text-white px-6 py-4 border-b border-gray-700"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.label("HYDRANT").classes(
                    "text-3xl font-extrabold tracking-wider"
                )

        # MAIN PAGE CONTENT
        with ui.column().classes(
            "w-full p-6 gap-4 max-w-7xl mx-auto"
        ) as main_page_content:
            self.main_page_content = main_page_content

            # DEVICE COMMANDS
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

            # COMMAND HISTORY CARD
            self.command_history_table()

            # ERROR LOG CARD
            with ui.card().classes(
                "w-full bg-gray-900 border border-gray-700 p-6"
            ):
                ui.label("Error Log").classes(
                    "text-xl font-bold text-red-400 mb-4"
                )

                error_column = ui.column().classes("w-full overflow-y-auto")
                with error_column:
                    ui.label("Errors will appear here").classes(
                        "text-gray-500 italic"
                    )

    def send_command(self, dialog):
        """Initialize send command process on button press"""

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

        logger.info(
            f"Sending {self.selected_command_name} to board {self.selected_board_name}"
        )

        msg = DeviceCommandMessage(self.board, self.command)
        await self.lmp_framer.send_message(msg)

        new_entry = DeviceCommandHistoryEntry(
            board=msg.board,
            command=msg.command,
            send_time=datetime.now(),
        )
        self.device_command_history.append(new_entry)
        self.device_command_recency[(msg.board, msg.command)] = new_entry
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
                if field == "Send Time":
                    col_def["sort"] = "desc"
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
