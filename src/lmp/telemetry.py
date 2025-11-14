import struct

from .util import Board

TELEM_VALUE_SIZE: int = 4


class TelemetryMessage:
    """A class to represent a telemetry message."""

    # Class variables
    MSG_ID: int = 0x00

    # Instance variables
    board: Board
    timestamp: int
    values: list[float]

    def __init__(self, board: Board, timestamp: int, values: list[float]):
        """Construct a TelemetryMessage with the given data."""
        self.board = board
        self.timestamp = timestamp
        self.values = values
        self._validate_self()

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a TelemetryMessage by parsing msg_bytes.

        Raises:
            ValueError: The parsed board_id is invalid or the number of
                values received doesn't match the number of values expected
                based on the board ID.
        """
        # Bypass __init__ to create an "empty" TelemetryMessage
        obj = cls.__new__(cls)

        obj.board = Board(
            int.from_bytes(msg_bytes[1:2], byteorder="big", signed=False)
        )

        obj.timestamp = int.from_bytes(
            msg_bytes[2:10], byteorder="big", signed=False
        )

        obj.values = []
        for chunk in iterate_chunks(msg_bytes[10:], TELEM_VALUE_SIZE):
            data: float = struct.unpack(">f", chunk)[0]
            obj.values.append(data)

        obj._validate_self()

        return obj

    def _validate_self(self):
        """Raise ValueError if number of values is invalid."""
        if len(self.values) != self.board.num_values:
            raise ValueError(
                f"Expected {self.board.num_values} values for {self.board}, got {len(self.values)}"
            )

    def __repr__(self) -> str:
        return f"TelemetryMessage(board: {repr(self.board)}, timestamp: {self.timestamp})"

    def __bytes__(self) -> bytes:
        msg_bytes = (
            self.MSG_ID.to_bytes(1)
            + self.board.value.to_bytes(1)
            + self.timestamp.to_bytes(8)
        )

        for value in self.values:
            msg_bytes += struct.pack(">f", value)

        return msg_bytes

    @property
    def index_channel(self) -> str:
        """The Synnax channel that indexes this message's data."""
        return self.board.index_channel


def iterate_chunks(byte_data: bytes, chunk_size: int):
    """Yield chunks of size chunk_size from byte_data."""
    for i in range(0, len(byte_data), chunk_size):
        yield byte_data[i : i + chunk_size]
