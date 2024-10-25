import struct


class TelemetryValue:
    """A class to encapsulate a single telemetry value."""

    SIZE_BYTES = 13

    def __init__(self, channel_id: int, data: float, timestamp: int):
        if not (0 <= channel_id < 256):
            raise ValueError(
                f"Invalid channel_id {
                    channel_id}; channel_id must fit within a byte."
            )
        self.channel_id = channel_id
        self.data = data
        self.timestamp = timestamp

    def __bytes__(self) -> bytes:
        return (
            self.channel_id.to_bytes(1)
            + struct.pack(">f", self.data)
            + self.timestamp.to_bytes(8, byteorder="big")
        )

    def __repr__(self) -> str:
        return f"TelemetryValue<channel_id={self.channel_id}, data={self.data}, timestamp={self.timestamp}>"


class TelemetryPacket:
    """A class to represent a single telemetry packet."""

    HEADER = 0x01
    MAX_NUM_BYTES = 3330

    def __init__(
        self,
        values: list[TelemetryValue] = None,
        bytes_recv: bytes = None,
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

        if len(values) > 256:
            raise ValueError("Must pass 256 or fewer values.")
        self.values = values

    def __bytes__(self) -> bytes:
        ret = self.HEADER.to_bytes(1) + len(self.values).to_bytes(1)
        for value in self.values:
            ret += bytes(value)
        return ret

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

        Raises:
            ValueError: bytes_recv is of an invalid size.
        """
        if len(bytes_recv) % TelemetryValue.SIZE_BYTES != 0:
            raise ValueError("Invalid bytes_recv.")
        self.values = []
        for chunk in iterate_chunks(bytes_recv, TelemetryValue.SIZE_BYTES):
            channel_id = chunk[0]
            data = struct.unpack(">f", chunk[1:5])[0]
            timestamp = int.from_bytes(chunk[5:], byteorder="big", signed=False)
            self.values.append(TelemetryValue(channel_id, data, timestamp))


def iterate_chunks(byte_data: bytes, chunk_size: int):
    """Yield chunks of size chunk_size from byte_data."""
    for i in range(0, len(byte_data), chunk_size):
        yield byte_data[i : i + chunk_size]
