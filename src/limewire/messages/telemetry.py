import struct
from enum import Enum

TELEM_VALUE_SIZE: int = 4


class BoardID(Enum):
    """An Enum to store board identifier constants."""

    FC = 0
    BB1 = 1
    BB2 = 2
    BB3 = 3
    FR = 4

    @property
    def num_values(self) -> int:
        """The number of telemetry values for this board."""
        NUM_VALUES = {
            BoardID.FC: 47,
            BoardID.BB1: 52,
            BoardID.BB2: 52,
            BoardID.BB3: 52,
            BoardID.FR: 14,
        }
        return NUM_VALUES[self]

    @property
    def index_channel(self) -> str:
        """The Synnax index channel name for this board."""
        return f"{self.name.lower()}_timestamp"

    def __str__(self) -> str:
        return repr(self).removeprefix(f"{self.__class__.__name__}.")


class TelemetryMessage:
    """A class to represent a telemetry message."""

    # Class variables
    MSG_ID: int = 0x00

    # Instance variables
    board_id: BoardID
    timestamp: int
    values: list[float]

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a TelemetryMessage by parsing msg_bytes.

        Raises:
            ValueError: The parsed board_id is invalid or the number of
                values received doesn't match the number of values expected
                based on the board ID.
        """
        obj = cls()

        obj.board_id = BoardID(
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

    @classmethod
    def from_data(cls, board_id: BoardID, timestamp: int, values: list[float]):
        """Construct a TelemetryMessage with the given data."""
        obj = cls()
        obj.board_id = board_id
        obj.timestamp = timestamp
        obj.values = values
        obj._validate_self()
        return obj

    def _validate_self(self):
        """Raise ValueError if number of values is invalid."""
        if len(self.values) != self.board_id.num_values:
            raise ValueError(
                f"Expected {self.board_id.num_values} values for {self.board_id}, got {len(self.values)}"
            )

    def __repr__(self) -> str:
        return f"TelemetryMessage(board_id: {repr(self.board_id)}, timestamp: {self.timestamp})"

    def __bytes__(self) -> bytes:
        msg_bytes = (
            self.MSG_ID.to_bytes(1)
            + self.board_id.value.to_bytes(1)
            + self.timestamp.to_bytes(8)
        )

        for value in self.values:
            msg_bytes += struct.pack(">f", value)

        return msg_bytes

    @property
    def index_channel(self) -> str:
        """The Synnax channel that indexes this message's data."""
        return self.board_id.index_channel


def iterate_chunks(byte_data: bytes, chunk_size: int):
    """Yield chunks of size chunk_size from byte_data."""
    for i in range(0, len(byte_data), chunk_size):
        yield byte_data[i : i + chunk_size]
