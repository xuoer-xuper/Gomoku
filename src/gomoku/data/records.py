"""Local match history: records, stats and JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

RESULT_WIN = "win"
RESULT_LOSE = "lose"
RESULT_DRAW = "draw"
RESULT_LEFT = "left"

_RESULT_LABEL = {
    RESULT_WIN: "胜利",
    RESULT_LOSE: "失败",
    RESULT_DRAW: "和棋",
    RESULT_LEFT: "中断",
}


def default_state_path() -> Path:
    """Per-user file under LocalAppData (or ~/.gomoku)."""
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    folder = Path(root) / "Gomoku" if root else Path.home() / ".gomoku"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "state.json"


@dataclass
class MatchRecord:
    """One finished or interrupted local match, from this player's view."""

    id: str
    played_at: str
    my_name: str
    opponent_name: str
    my_color: str
    result: str
    move_count: int
    duration_seconds: int
    room_code: str
    moves: list[dict[str, Any]] = field(default_factory=list)

    @property
    def result_label(self) -> str:
        return _RESULT_LABEL.get(self.result, self.result)

    @property
    def color_label(self) -> str:
        return "黑" if self.my_color == "black" else "白"

    @classmethod
    def create(
        cls,
        *,
        my_name: str,
        opponent_name: str,
        my_color: str,
        result: str,
        duration_seconds: int,
        room_code: str,
        moves: list[dict[str, Any]],
    ) -> "MatchRecord":
        return cls(
            id=uuid.uuid4().hex[:12],
            played_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            my_name=my_name,
            opponent_name=opponent_name,
            my_color=my_color,
            result=result,
            move_count=len(moves),
            duration_seconds=max(0, int(duration_seconds)),
            room_code=room_code,
            moves=list(moves),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchRecord":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            played_at=str(data.get("played_at") or ""),
            my_name=str(data.get("my_name") or "玩家"),
            opponent_name=str(data.get("opponent_name") or "对手"),
            my_color=str(data.get("my_color") or "black"),
            result=str(data.get("result") or RESULT_LEFT),
            move_count=int(data.get("move_count") or 0),
            duration_seconds=int(data.get("duration_seconds") or 0),
            room_code=str(data.get("room_code") or ""),
            moves=list(data.get("moves") or []),
        )


@dataclass(frozen=True)
class RecordStats:
    """Aggregate counters for the history header."""

    total: int
    wins: int
    losses: int
    draws: int
    interrupted: int

    @property
    def win_rate(self) -> float:
        played = self.wins + self.losses + self.draws
        if played <= 0:
            return 0.0
        return self.wins / played


class AppState:
    """Nickname plus match records saved as one JSON document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_state_path()
        self.nickname = ""
        self.nickname_set = False
        self.records: list[MatchRecord] = []
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        name = str(raw.get("nickname") or "").strip()
        if name:
            self.nickname = name[:16]
            self.nickname_set = bool(raw.get("nickname_set", True))
        else:
            self.nickname_set = bool(raw.get("nickname_set", False))
        items = raw.get("records") or []
        if isinstance(items, list):
            loaded = []
            for item in items:
                if isinstance(item, dict):
                    loaded.append(MatchRecord.from_dict(item))
            self.records = loaded

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nickname": self.nickname,
            "nickname_set": self.nickname_set,
            "records": [item.to_dict() for item in self.records],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=self.path.parent,
            suffix=".tmp",
        )
        try:
            handle.write(text)
            handle.close()
            os.replace(handle.name, self.path)
        except OSError:
            handle.close()
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise

    def add_record(self, record: MatchRecord) -> None:
        self.records.insert(0, record)
        self.records = self.records[:200]
        self.save()

    def query(
        self,
        result: str | None = None,
        keyword: str = "",
    ) -> list[MatchRecord]:
        """Newest first. ``keyword`` matches opponent or self name."""
        needle = keyword.strip().lower()
        found: list[MatchRecord] = []
        for record in self.records:
            if result and record.result != result:
                continue
            if needle:
                blob = f"{record.opponent_name} {record.my_name}".lower()
                if needle not in blob:
                    continue
            found.append(record)
        return found

    def stats(self) -> RecordStats:
        wins = losses = draws = interrupted = 0
        for record in self.records:
            if record.result == RESULT_WIN:
                wins += 1
            elif record.result == RESULT_LOSE:
                losses += 1
            elif record.result == RESULT_DRAW:
                draws += 1
            else:
                interrupted += 1
        return RecordStats(
            total=len(self.records),
            wins=wins,
            losses=losses,
            draws=draws,
            interrupted=interrupted,
        )
