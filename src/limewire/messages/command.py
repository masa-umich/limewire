import struct

from .util import Board

class DeviceCommand:
    """A class to represent a device command."""

    MSG_ID: int = 0x04

    length: int
    board: Board
    command_id: int

    def __init__(self, length: int, board: Board, command_id: int):
        self.length = length
        self.board = board
        self.command_id = command_id
        self._validate_self()

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a DeviceCommand by parsing msg_bytes.
        
        Format: [1 byte Length][1 byte MsgID][1 byte Board ID][2 bytes Command ID]
        """
        obj = cls.__new__(cls)

        length = msg_bytes[0]
        msg_id = msg_bytes[1]
        # Check to ensure valid command
        if msg_id != cls.MSG_ID:
            raise ValueError(f"Invalid MSG_ID {msg_id:#02x}")

        obj.length = length
        board_id = msg_bytes[2]
        obj.board = Board(board_id)

        obj.command_id = int.from_bytes(msg_bytes[3:5])

        obj._validate_self()
        return obj

    def _validate_self(self):
        """Validation"""
        pass

    def __bytes__(self) -> bytes:
        """Convert command to bytes: [Length][MsgID][BoardID][CommandID]."""
        length = 1 + 1 + 1 + 2  # length + msg_id + board_id + cmd_id
        return (
            length.to_bytes(1, "big")
            + self.MSG_ID.to_bytes(1, "big")
            + self.board.value.to_bytes(1, "big")
            + self.command_id.to_bytes(2, "big")
        )

    def __repr__(self) -> str:
        return f"DeviceCommand(board={repr(self.board)}, command_id={self.command_id:#04x})"
