"""Local match-history persistence and query."""

from pathlib import Path

from gomoku.data.records import (
    RESULT_DRAW,
    RESULT_LOSE,
    RESULT_WIN,
    AppState,
    MatchRecord,
)


def _record(result: str, opponent: str = "李四") -> MatchRecord:
    return MatchRecord.create(
        my_name="玩家",
        opponent_name=opponent,
        my_color="black",
        result=result,
        duration_seconds=42,
        room_code="ABCDE-FGHIJ",
        moves=[{"row": 7, "col": 7, "color": "black"}],
    )


def test_roundtrip_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = AppState(path)
    state.nickname = "甲"
    state.add_record(_record(RESULT_WIN, "乙"))
    loaded = AppState(path)
    assert loaded.nickname == "甲"
    assert len(loaded.records) == 1
    item = loaded.records[0]
    assert item.opponent_name == "乙"
    assert item.result_label == "胜利"
    assert item.moves[0]["row"] == 7


def test_query_by_result_and_keyword(tmp_path: Path) -> None:
    state = AppState(tmp_path / "state.json")
    state.add_record(_record(RESULT_WIN, "张三"))
    state.add_record(_record(RESULT_LOSE, "李四"))
    state.add_record(_record(RESULT_DRAW, "张三"))
    wins = state.query(result=RESULT_WIN)
    assert len(wins) == 1
    assert wins[0].opponent_name == "张三"
    found = state.query(keyword="李")
    assert len(found) == 1
    assert found[0].result == RESULT_LOSE


def test_stats_win_rate(tmp_path: Path) -> None:
    state = AppState(tmp_path / "state.json")
    state.add_record(_record(RESULT_WIN))
    state.add_record(_record(RESULT_WIN))
    state.add_record(_record(RESULT_LOSE))
    stats = state.stats()
    assert stats.total == 3
    assert stats.wins == 2
    assert abs(stats.win_rate - 2 / 3) < 1e-9
