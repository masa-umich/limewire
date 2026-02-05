from enum import Enum


class ControlSignal(Enum):
    HANDOFF = 1
    ABORT = 0


class HandoffMessage:
    """A class to represent the handoff message"""

    MSG_ID = 0x06
    DEFAULT_CONFIRMATION_SEQ = 0x4D415341

    control_signal: ControlSignal
    confirmation_seq: int

    def __init__(
        self, control_signal, confirmation_seq=DEFAULT_CONFIRMATION_SEQ
    ):
        self.control_signal = control_signal
        self.confirmation_seq = confirmation_seq

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        obj = cls.__new__(cls)

        obj.control_signal = ControlSignal(
            int.from_bytes(msg_bytes[0:1], byteorder="big", signed=False)
        )

        obj.confirmation_seq = int.from_bytes(
            msg_bytes[1:4], byteorder="big", signed=False
        )

        return obj

    def __bytes__(self) -> bytes:
        msg_bytes = (
            self.MSG_ID.to_bytes(1)
            + self.control_signal.value.to_bytes(1)
            + self.DEFAULT_CONFIRMATION_SEQ.to_bytes(4)
        )

        return msg_bytes

    def __repr__(self) -> str:
        return f"HandoffMessage(signal: {repr(self.control_signal)}, confirmation seq: {repr(self.control_signal)})"
