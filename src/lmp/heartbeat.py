class HeartbeatMessage:
    """A class to represent heartbeat messages"""

    MSG_ID: int = 0x03

    def __bytes__(self):
        msg_bytes = self.MSG_ID.to_bytes(1)
        return msg_bytes

    def __repr__(self):
        return "HeartbeatMessage()"
