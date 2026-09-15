"""Domain and protocol exceptions."""


class GomokuError(Exception):
    """Base error for recoverable game-rule failures."""


class InvalidMoveError(GomokuError):
    """Raised when a stone cannot be placed at the requested point."""


class NotYourTurnError(GomokuError):
    """Raised when a player acts out of turn."""


class GameNotActiveError(GomokuError):
    """Raised when a move arrives before start or after finish."""


class ProtocolError(GomokuError):
    """Raised when a network payload cannot be decoded."""
