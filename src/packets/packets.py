import struct
from typing import override


class TelemetryValue:
    """A class to encapsulate a single telemetry value."""

    SIZE_BYTES: int = 4

    def __init__(self, data: float):
        self.data: float = data

    def __bytes__(self) -> bytes:
        return struct.pack(">f", self.data)

    @override
    def __repr__(self) -> str:
        return f"TelemetryValue<data={self.data}>"


class TelemetryMessage:
    """A class to represent a single telemetry message."""

    HEADER: int = 0x01

    def __init__(
        self,
        board_id: int | None = None,
        timestamp: int | None = None,
        values: list[TelemetryValue] | None = None,
        bytes_recv: bytes | None = None,
    ):
        if bytes_recv:
            self.deserialize_bytes(bytes_recv)
        else:
            if values is None:
                raise ValueError("Must specify either values or bytes_recv.")
            if timestamp is None:
                raise ValueError("Must specify timestamp with values.")
            if board_id is None:
                raise ValueError("Must specify board ID with values.")

            self.board_id: int = board_id
            self.timestamp: int = timestamp
            self.values: list[TelemetryValue] = values

        # Ensure the board ID corresponds to a valid index channel.
        try:
            self.get_index_channel()
        except ValueError as err:
            raise err

        # Ensure we receive the number of telemetry values we expect given
        # the board ID.
        FC_NUM_VALUES = 47
        BB_NUM_VALUES = 52
        if self.board_id == 0 and len(self.values) != FC_NUM_VALUES:
            raise ValueError(
                f"Invalid number of telemetry values (expected {FC_NUM_VALUES}, got {len(self.values)})"
            )
        elif 1 <= self.board_id <= 3 and len(self.values) != BB_NUM_VALUES:
            raise ValueError(
                f"Invalid number of telemetry values (expected {BB_NUM_VALUES}, got {len(self.values)})"
            )

    def __bytes__(self) -> bytes:
        ret = (
            self.HEADER.to_bytes(1)
            + self.board_id.to_bytes(1)
            + self.timestamp.to_bytes(8)
        )

        for value in self.values:
            ret += bytes(value)

        return ret

    @override
    def __repr__(self) -> str:
        ret = "TelemetryPacket:\n"
        for value in self.values:
            ret += "  " + str(value) + "\n"
        return ret

    def get_index_channel(self) -> str:
        """Return the index channel name corresponding to the board ID.

        Raises:
            ValueError: The board ID is invalid.
        """
        match self.board_id:
            case 0:
                return "fc_timestamp"
            case 1:
                return "bb1_timestamp"
            case 2:
                return "bb2_timestamp"
            case 3:
                return "bb3_timestamp"
            case num:
                raise ValueError(f"Invalid Board ID '{num}'")

    def deserialize_bytes(self, bytes_recv: bytes) -> None:
        """Initialize values using bytes received via TCP.

        Args:
            bytes_recv: The bytes containing the telemetry values.

        Returns:
            None.
        """
        self.board_id = int.from_bytes(
            bytes_recv[0:1], byteorder="big", signed=False
        )

        self.timestamp = int.from_bytes(
            bytes_recv[1:9], byteorder="big", signed=False
        )

        self.values = []
        for chunk in iterate_chunks(bytes_recv[9:], TelemetryValue.SIZE_BYTES):
            data: float = struct.unpack(">f", chunk)[0]
            self.values.append(TelemetryValue(data))


def iterate_chunks(byte_data: bytes, chunk_size: int):
    """Yield chunks of size chunk_size from byte_data."""
    for i in range(0, len(byte_data), chunk_size):
        yield byte_data[i : i + chunk_size]
