from datetime import datetime
from enum import Enum


class LogMessageSource(Enum):
    """A class to represent the source of a log message."""

    LIMEWIRE = 0
    FC = 1
    BB1 = 2
    BB2 = 3
    BB3 = 4


class LogMessage:
    """A log message sent over UDP from the flight computer or Limewire."""

    def __init__(
        self,
        timestamp: datetime,
        source: LogMessageSource,
        error_code: int,
        message: str,
    ):
        self.timestamp = timestamp
        self.source = source
        self.error_code = error_code
        self.message = message

    @classmethod
    def from_bytes(cls, msg_bytes: bytes):
        """Construct a LogMessage by parsing msg_bytes.

        Raises:
            ValueError: The message is in an invalid format.
        """
        try:
            msg_str = msg_bytes.decode("ascii")
        except UnicodeDecodeError:
            raise ValueError(
                "Unable to decode log message (expected ASCII-encoded string)"
            )
