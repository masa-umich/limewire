from enum import Enum


class DeviceCommand(Enum):
    "A class to represent commands going to the rocket."

    # TODO: Add command definitions
    RESET_BOARD = 0x00
    CLEAR_FLASH = 0x01
    FLASH_SPACE = 0x02

    def __str__(self) -> str:
        return repr(self).removeprefix(f"{self.__class__.__name__}.")


class Board(Enum):
    """A class to represent a board on the rocket.

    This class inherits from Enum, which means that each variant (defined
    in all caps below) has a value associated with it, which can be
    accessed using `.value`. The value associated with each variant is the
    board's LMP identifier.
    """

    FC = 0
    BB1 = 1
    BB2 = 2
    BB3 = 3
    FR = 4

    @property
    def num_values(self) -> int:
        """The number of telemetry values for this board."""
        NUM_VALUES = {
            Board.FC: 39,
            Board.BB1: 52,
            Board.BB2: 52,
            Board.BB3: 52,
            Board.FR: 14,
        }
        return NUM_VALUES[self]

    @property
    def num_valves(self) -> int:
        """The number of valves this board controls."""
        NUM_VALVES = {
            Board.FC: 3,
            Board.BB1: 7,
            Board.BB2: 7,
            Board.BB3: 7,
            Board.FR: 0,
        }
        return NUM_VALVES[self]

    @property
    def index_channel(self) -> str:
        """The Synnax index channel name for this board."""
        return f"{self.name.lower()}_timestamp"

    def __str__(self) -> str:
        return repr(self).removeprefix(f"{self.__class__.__name__}.")


class Valve:
    """A class to represent a valve on the rocket."""

    def __init__(self, board: Board, num: int):
        self.board = board
        self.num = num

    @classmethod
    def from_identifier(cls, id: int):
        """Construct a Valve from an LMP valve identifier.

        Raises:
            ValueError: The valve identifier given is invalid.
        """
        board = Board(id // 10)
        num = id % 10

        if num > board.num_valves:
            raise ValueError(
                f"Invalid valve identifer {id} (valve number must be <={board.num_valves} for board {board})"
            )

        return cls(board, num)

    @classmethod
    def from_channel_name(cls, name: str):
        """Construct a Valve from a Synnax channel name.

        Raises:
            ValueError: The channel name passed in is not a valve channel.
        """

        if "vlv" not in name:
            raise ValueError(f"Invalid valve channel {name}")

        components = name.split("_")
        board_name = components[0]
        num = int(components[1][-1])

        return cls(Board[board_name.upper()], num)

    def __repr__(self) -> str:
        return f"Valve(board: {self.board}, num: {self.num})"

    @property
    def id(self) -> int:
        """The valve's LMP identifier."""
        return 10 * self.board.value + self.num

    @property
    def cmd_channel(self) -> str:
        """The Synnax command channel name for this valve."""
        return f"{self.board.name.lower()}_vlv_{self.num}"

    @property
    def cmd_channel_index(self) -> str:
        """The Synnax index channel name for this valve's command channel."""
        return f"{self.board.name.lower()}_vlv_{self.num}_timestamp"

    @property
    def state_channel(self) -> str:
        """The Synnax state channel name for this valve."""
        return f"{self.board.name.lower()}_state_{self.num}"

    @property
    def state_channel_index(self) -> str:
        """The Synnax index channel name for this valve's state channel."""
        return f"{self.board.name.lower()}_state_{self.num}_timestamp"
