class HeartbeatMessage:
    """A class to represent heartbeat messages"""

    MSG_ID: int = 0x03

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        # This is stupid, but it's here to match the other classes
        return cls.__new__(cls)

    def __bytes__(self):
        msg_bytes = self.MSG_ID.to_bytes(1)

        return msg_bytes

    def __repr__(self):
        return "HeartbeatMessage()"
