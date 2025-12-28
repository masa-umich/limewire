import ipaddress
from datetime import datetime, timezone

from lmp import Board


class FirmwareLog:
    """A firmware log message sent over UDP."""

    timestamp: datetime # UTC timestamp
    board: Board
    status_code: int
    message: str
    ip: ipaddress.IPv4Address

    def __init__(
        self, timestamp: datetime, board: Board, status_code: int, message: str
    ):
        if(status_code is not None and status_code > 9999):
            raise ValueError(f"Invalid status code {status_code}")
        
        if(board is not None and status_code is not None):
            board_matches_status_code = status_code // 1000 == board.value
            if not board_matches_status_code:
                raise ValueError(
                    f"Status code {status_code} isn't from board {board.name}"
                )

        self.timestamp = timestamp
        self.board = board
        self.status_code = status_code
        self.message = message

    @classmethod
    def from_bytes(cls, log_bytes: bytes):
        """Construct a FirmwareLog by parsing log_bytes."""
        try:
            log_str = log_bytes.decode().strip()
        except UnicodeDecodeError:
            raise ValueError("Message not ASCII-encoded.")
        
        timestamp = None # default if no timestamp is given
        try:
            timestamp_str = log_str[:24]
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            log_str = log_str[24:]
            if(log_str[0] == " "):
                log_str = log_str[1:]
        except Exception:
            pass # It's ok to not have a timestamp, some logs will not
        
        code = None # default if no error code is included
        try:
            code_str = log_str[:4]
            if not code_str.isdigit(): 
                raise ValueError()
            code = int(code_str)
            log_str = log_str[4:]
            if(log_str[0] == " "):
                log_str = log_str[1:]
        except Exception:
            pass
        
        board = None
        if(code is not None):
            board = Board(code // 1000)
            
        return cls(timestamp, board, code, log_str)
    
    def __str__(self):
        return f"{{Timestamp: {self.timestamp}, Board: {self.board}, Code: {self.status_code}, Msg: '{self.message}'}}"
    
    def to_log(self):
        time_str = None
        if(self.timestamp is not None):
            timestamp = self.timestamp
            local_zone = datetime.now(timezone.utc).astimezone().tzinfo
            timestamp = timestamp.astimezone(local_zone)
            time_str = timestamp.strftime("%b %d, %Y %I:%M:%S.%f %p %Z")
        return f"'{self.message}', Timestamp: {time_str}, Code: {self.status_code}, Board: {self.board.pretty_name if self.board is not None else None}"