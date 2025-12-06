from datetime import datetime

from lmp import Board


class FirmwareLog:
    """A firmware log message sent over UDP."""

    timestamp: datetime
    board: Board
    status_code: int
    message: str

    def __init__(
        self, timestamp: datetime, board: Board, status_code: int, message: str
    ):
        if status_code > 9999:
            raise ValueError(f"Invalid status code {status_code}")

        board_matches_status_code = status_code // 100 == board.value
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
        obj = cls.__new__(cls)

        try:
            log_str = log_bytes.decode()
        except UnicodeDecodeError:
            raise ValueError("Message not ASCII-encoded.")

        log_split = log_str.split(" ")

        if len(log_split) < 3:
            raise ValueError(f"Invalid firmware log '{log_str}'")

        try:
            timestamp_str = log_split[0]
            obj.timestamp = datetime.strptime(
                timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except ValueError as err:
            raise err

        try:
            status_code_str = log_split[1]
        except ValueError as err:
            pass
            # TODO
