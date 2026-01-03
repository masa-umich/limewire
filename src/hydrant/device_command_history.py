from datetime import datetime

from lmp.util import Board, DeviceCommand


class DeviceCommandHistoryEntry:
    board: Board
    command: DeviceCommand
    send_time: datetime
    ack: bool
    ack_time: datetime | None
    ack_msg: str | None

    def __init__(
        self, board: Board, command: DeviceCommand, send_time: datetime
    ):
        self.board = board
        self.command = command
        self.send_time = send_time
        self.ack = False
        self.ack_time = None
        self.ack_msg = None

    def set_ack(self, ack_time: datetime, ack_msg: str):
        self.ack = True
        self.ack_time = ack_time
        self.ack_msg = ack_msg

    def to_gui_dict(self):
        date_format = "%b %d, %Y %I:%M:%S %p"
        return {
            "Board": self.board.pretty_name,
            "Command": self.command.name,
            "Send Time": self.send_time.strftime(date_format),
            "ACK?": self.ack,
            "ACK Time": None
            if self.ack_time is None
            else self.ack_time.strftime(date_format),
            "ACK Message": self.ack_msg,
        }

    @classmethod
    def fields(cls):
        return [
            "Board",
            "Command",
            "Send Time",
            "ACK?",
            "ACK Time",
            "ACK Message",
        ]
