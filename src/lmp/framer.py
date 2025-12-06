import asyncudp

from .telemetry import TelemetryMessage


class FramingError(Exception):
    pass


class TelemetryFramer:
    """A class to handle framing/unframing telemetry data from a UDP socket."""

    def __init__(self, sock: asyncudp.Socket):
        """Initialize the TelemetryFramer.

        If sending messages with this framer, the remote address must be set
        before passing the socket into this function.
        """
        self.sock = sock

    def send_message(self, message: TelemetryMessage):
        msg_bytes = bytes(message)
        self.sock.sendto(len(msg_bytes).to_bytes(1) + msg_bytes)

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
