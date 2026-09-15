"""Stone colors occupying a board intersection."""

from enum import Enum


class Stone(Enum):
    """Occupancy of one intersection."""

    EMPTY = 0
    BLACK = 1
    WHITE = 2

    @property
    def code(self) -> str:
        """Wire-format name used by the protocol."""
        return self.name.lower()

    @property
    def label(self) -> str:
        """Short Chinese label for the HUD."""
        labels = {
            Stone.EMPTY: "空",
            Stone.BLACK: "黑",
            Stone.WHITE: "白",
        }
        return labels[self]

    def opponent(self) -> "Stone":
        """Return the opposite player color."""
        if self is Stone.BLACK:
            return Stone.WHITE
        if self is Stone.WHITE:
            return Stone.BLACK
        raise ValueError("empty stone has no opponent")

    @classmethod
    def from_code(cls, code: str) -> "Stone":
        """Parse a protocol color string."""
        try:
            return cls[code.upper()]
        except KeyError as exc:
            raise ValueError(f"unknown stone code: {code}") from exc
