from .util import Valve


class ValveCommandMessage:
    """A class to represent a valve command message."""

    # Class variables
    MSG_ID = 0x01

    # Instance variables
    valve: Valve
    state: bool

    def __init__(self, valve: Valve, state: bool):
        self.valve = valve
        self.state = state

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a ValveCommandMessage by parsing msg_bytes.

        Raises:
            ValueError: The valve identifier is invalid.
        """
        obj = cls.__new__(cls)

        obj.valve = Valve.from_identifier(
            int.from_bytes(msg_bytes[1:2], byteorder="big", signed=False)
        )
        obj.state = bool.from_bytes(msg_bytes[2:3])

        return obj

    def __repr__(self) -> str:
        return f"ValveCommandMessage(valve: {repr(self.valve)}, state: {int(self.state)})"

    def __bytes__(self) -> bytes:
        return (
            self.MSG_ID.to_bytes(1)
            + self.valve.id.to_bytes(1)
            + self.state.to_bytes()
        )


class ValveStateMessage:
    """A class to represent a valve state message."""

    # Class variables
    MSG_ID = 0x02

    # Instance variables
    valve: Valve
    state: bool
    timestamp: int

    def __init__(self, valve: Valve, state: bool, timestamp: int):
        self.valve = valve
        self.state = state
        self.timestamp = timestamp

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a ValveStateMessage by parsing msg_bytes.

        Raises:
            ValueError: The valve identifier is invalid.
        """
        obj = cls.__new__(cls)

        obj.valve = Valve.from_identifier(
            int.from_bytes(msg_bytes[1:2], byteorder="big", signed=False)
        )
        obj.state = bool.from_bytes(msg_bytes[2:3])
        obj.timestamp = int.from_bytes(msg_bytes[3:11])

        return obj

    def __repr__(self) -> str:
        return f"ValveStateMessage(valve: {repr(self.valve)}, state: {int(self.state)}, timestamp: {self.timestamp})"

    def __bytes__(self) -> bytes:
        return (
            self.MSG_ID.to_bytes(1)
            + self.valve.id.to_bytes(1)
            + self.state.to_bytes()
            + self.timestamp.to_bytes(8)
        )
