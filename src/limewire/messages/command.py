import struct
from .util import Board, Command


class DeviceCommandMessage:
    """A class to represent a device command.
    Format: [1 byte MsgID][1 byte Board ID][1 byte Command ID]
    """

    MSG_ID: int = 0x04
    board: Board
    command: Command

    def __init__(self, board: Board, command_id: Command):
        self.board = board
        self.command = command_id

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a DeviceCommand by parsing msg_bytes."""
        obj = cls.__new__(cls)

        obj.board = Board(
            int.from_bytes(msg_bytes[1:2], byteorder="big", signed=False)
        )

        obj.command = Command(
            int.from_bytes(msg_bytes[2:3], byteorder="big", signed=False)
        )

        return obj

    def __bytes__(self) -> bytes:
        """Convert command to bytes: [MsgID][BoardID][CommandID]."""
        msg_bytes = (
            self.MSG_ID.to_bytes(1)
            + self.board.value.to_bytes(1)
            + self.command.value.to_bytes(1)
        )
        return msg_bytes

    def __repr__(self) -> str:
        return f"DeviceCommand(board: {repr(self.board)}, command: {repr(self.command)})"
