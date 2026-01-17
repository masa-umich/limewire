import asyncio

from .device_command import DeviceCommandAckMessage, DeviceCommandMessage
from .heartbeat import HeartbeatMessage
from .telemetry import TelemetryMessage
from .valve import ValveCommandMessage, ValveStateMessage

type LMPMessage = (
    DeviceCommandAckMessage
    | DeviceCommandMessage
    | HeartbeatMessage
    | TelemetryMessage
    | ValveCommandMessage
    | ValveStateMessage
)


class FramingError(Exception):
    pass


class LMPFramer:
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        self.reader = reader
        self.writer = writer

    async def send_message(self, message: LMPMessage) -> None:
        msg_bytes = bytes(message)
        self.writer.write(len(msg_bytes).to_bytes(1) + msg_bytes)
        await self.writer.drain()

    async def receive_message(self) -> LMPMessage | None:
        msg_length = await self.reader.read(1)
        if not msg_length:
            return None

        msg_bytes = await self.reader.readexactly(int.from_bytes(msg_length))
        if not msg_bytes:
            return None

        msg_id = int.from_bytes(msg_bytes[0:1])
        match msg_id:
            case DeviceCommandAckMessage.MSG_ID:
                return DeviceCommandAckMessage.from_bytes(msg_bytes)
            case DeviceCommandMessage.MSG_ID:
                return DeviceCommandMessage.from_bytes(msg_bytes)
            case HeartbeatMessage.MSG_ID:
                return HeartbeatMessage.from_bytes(msg_bytes)
            case ValveCommandMessage.MSG_ID:
                return ValveCommandMessage.from_bytes(msg_bytes)
            case ValveStateMessage.MSG_ID:
                return ValveStateMessage.from_bytes(msg_bytes)
            case _:
                raise ValueError(
                    f"Received invalid LMP message identifier: 0x{msg_id:X}"
                )

    async def close(self):
        """Close the underlying TCP reader and writer."""
        self.writer.close()
        await self.writer.wait_closed()


class TelemetryProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        super().__init__()
        self.open = False
        self.packets = asyncio.Queue(0)

    def connection_made(self, transport):
        self.transport = transport
        self.open = True

    def datagram_received(self, data, addr):
        self.packets.put_nowait((data, addr))

    def connection_lost(self, exc):
        self.open = False

    def send_message(self, message: TelemetryMessage):
        msg_bytes = bytes(message)
        if self.transport and self.open:
            # Send to default configured addr
            try:
                self.transport.sendto(
                    len(msg_bytes).to_bytes(1) + msg_bytes,
                    ("255.255.255.255", 6767),
                )
            except Exception as e:
                print("NOOOO", e)
        else:
            print("Attempted to send on closed telemetry transport")

    async def wait_for_close(self):
        while self.open:
            await asyncio.sleep(0.5)

    async def recvfrom(self):
        if self.open:
            return await self.packets.get()
        else:
            raise Exception("Telemetry UDP listener closed")


class TelemetryFramer:
    """A class to handle framing/unframing telemetry data from a UDP socket."""

    def __init__(self, sock: TelemetryProtocol):
        """Initialize the TelemetryFramer.

        If sending messages with this framer, the remote address must be set
        before passing the socket into this function.
        """
        self.sock = sock

    def send_message(self, message: TelemetryMessage):
        # raise NotImplementedError("Can't send UDP over broadcast using this")
        # msg_bytes = bytes(message)
        self.sock.send_message(message)
        # self.sock.sendto(len(msg_bytes).to_bytes(1) + msg_bytes)

    async def receive_message(self) -> TelemetryMessage:
        """Receive a message from the socket.

        Returns:
            The telemetry message received from the socket.

        Raises:
            FramingError: The length prefix and actual message length
                are mismatched.
            ValueError: The message data is an invalid TelemetryMessage.
        """
        data, _ = await self.sock.recvfrom()

        msg_len = int.from_bytes(data[0:1])

        if len(data[1:]) != msg_len:
            raise FramingError(
                f"Message length mismatch (expected {msg_len}, got {len(data[1:])})"
            )

        try:
            message = TelemetryMessage.from_bytes(data[1:])
        except ValueError as err:
            raise err

        return message
