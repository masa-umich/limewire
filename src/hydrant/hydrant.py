import asyncio

from nicegui import app, background_tasks, ui

from lmp import DeviceCommandAckMessage, DeviceCommandMessage
from lmp.util import Board, DeviceCommand


class Hydrant:
    def __init__(self):
        self.boards_available = {board.name: board for board in Board}
        self.commands_available = {cmd.name: cmd for cmd in DeviceCommand}

        # Initially not assigned; updates on user input
        self.board_select = None
        self.command_select = None
        self.confirm_label = None
        self.selected_board_name = None
        self.selected_command_name = None

    async def connect_to_fc(self):
        """Maintain connection to flight computer."""
        while True:
            try:
                self.fc_reader, self.fc_writer = await asyncio.open_connection(
                    "127.0.0.1", 8888
                )
            except ConnectionRefusedError:
                await asyncio.sleep(1)
                continue

            fc_listen_task = background_tasks.create(self.listen_for_acks())

            try:
                await fc_listen_task
            except Exception:
                # Connection closed
                continue

    async def listen_for_acks(self):
        while True:
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
                    with self.main_page_content:
                        ui.notify(f"{msg}", close_button="OK")
                case _:
                    continue

    def main_page(self):
        """Generates page outline and GUI"""

        # Register background tasks
        self.fc_connect_task = background_tasks.create(self.connect_to_fc())

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
            # TWO-COLUMN LAYOUT
            with ui.row().classes("w-full gap-4 items-stretch"):
                # LEFT COLUMN
                with ui.card().classes(
                    "flex-1 bg-gray-900 border border-gray-700 p-6"
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
                            options=list(self.boards_available.keys()),
                        ).classes("w-full")

                        # Command
                        ui.label("COMMAND").classes(
                            "text-lg font-bold text-white"
                        )
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
                        ).classes(
                            "w-half bg-blue-600 text-white hover:bg-blue-700"
                        )

                # RIGHT COLUMN
                with ui.column().classes("flex-1 gap-4"):
                    # COMMAND HISTORY CARD
                    with ui.card().classes(
                        "flex-1 bg-gray-900 border border-gray-700 p-6"
                    ):
                        ui.label("Command History").classes(
                            "text-xl font-bold text-blue-400 mb-4"
                        )

                        history_column = ui.column().classes(
                            "w-full overflow-y-auto"
                        )
                        with history_column:
                            ui.label(
                                "Command history will appear here"
                            ).classes("text-gray-500 italic")

                    # ERROR LOG CARD
                    with ui.card().classes(
                        "flex-1 bg-gray-900 border border-gray-700 p-6"
                    ):
                        ui.label("Error Log").classes(
                            "text-xl font-bold text-red-400 mb-4"
                        )

                        error_column = ui.column().classes(
                            "w-full overflow-y-auto"
                        )
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

        msg = DeviceCommandMessage(self.board, self.command)
        msg_bytes = bytes(msg)

        print(
            f"Sending {self.selected_command_name} to board {self.selected_board_name}"
        )
        self.fc_writer.write(len(msg_bytes).to_bytes(1) + msg_bytes)
        await self.fc_writer.drain()
