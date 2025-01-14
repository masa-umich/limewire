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
        if (
            values is None
            and bytes_recv is None
            or values is not None
            and bytes_recv is not None
        ):
            raise ValueError("Must specify either values or bytes_recv.")

        if bytes_recv:
            self.deserialize_bytes(bytes_recv)
            return

        if timestamp is None:
            raise ValueError("Must specify timestamp with values.")
        if board_id is None:
            raise ValueError("Must specify board ID with values.")

        self.board_id: int = board_id
        self.timestamp: int = timestamp
        self.values: list[TelemetryValue] = values

    def __bytes__(self) -> bytes:
        ret = self.HEADER.to_bytes(1) + self.timestamp.to_bytes(8)

        for value in self.values:
            ret += bytes(value)

        ret += self.timestamp.to_bytes(8)

        return ret

    @override
    def __repr__(self) -> str:
        ret = "TelemetryPacket:\n"
        for value in self.values:
            ret += "  " + str(value) + "\n"
        return ret

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
