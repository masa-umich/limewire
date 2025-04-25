from enum import Enum


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
            Board.FC: 47,
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

