from abc import ABC, abstractmethod

from .util import Valve


class ValveMessage(ABC):
    """A class to represent both valve command and valve state messages.

    Since valve command messages and valve state messages are equivalent
    in structure except for the message identifier, this class implements
    the shared functionality of both types of messages, leaving the classes
    for each message type to simply define MSG_ID as a class-level
    property.
    """

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
        return f"{self.__class__.__name__}(valve: {repr(self.valve)}, state: {int(self.state)})"

    def __bytes__(self) -> bytes:
        return (
            self.MSG_ID.to_bytes(1)
            + self.valve.id.to_bytes(1)
            + self.state.to_bytes()
        )

    @property
    @abstractmethod
    def MSG_ID(self) -> int:
        pass


class ValveCommandMessage(ValveMessage):
    """A class to represent a valve command message."""

    @property
    def MSG_ID(self):
        return 0x01


class ValveStateMessage(ValveMessage):
    """A class to represent a valve state message."""

    @property
    def MSG_ID(self):
        return 0x02
