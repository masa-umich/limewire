import struct


class HeartbeatMessage:
    """A class to represent heartbeat messages"""

    MSG_ID: int = 0x03

    ack: bool

    def __init__(self, ack):
        self.ack = ack

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        obj = cls.__new__(cls)

        obj.ack = bool(
            int.from_bytes(msg_bytes[1:2], byteorder="big", signed=False)
        )

        return obj

    def __bytes__(self):
        msg_bytes = self.MSG_ID.to_bytes(1) + self.ack.to_bytes(1)

        return msg_bytes

    def __repr__(self):
        return f"HeartbeatMessage(ack: {self.ack})"
