"""Board coordinate value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    """Zero-based intersection on the board."""

    row: int
    col: int
