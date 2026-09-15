"""Match-history page: filter, list and board replay snapshot."""

from __future__ import annotations

import tkinter as tk

from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.records import (
    RESULT_DRAW,
    RESULT_LEFT,
    RESULT_LOSE,
    RESULT_WIN,
    AppState,
    MatchRecord,
)
from gomoku.data.stone import Stone
from gomoku.presentation import theme
from gomoku.presentation.board_canvas import BoardCanvas
from gomoku.service.referee import Referee

_FILTERS = (
    ("全部", None),
    ("胜利", RESULT_WIN),
    ("失败", RESULT_LOSE),
    ("和棋", RESULT_DRAW),
    ("中断", RESULT_LEFT),
)


class HistoryPage(tk.Frame):
    """Browse locally saved matches."""

    def __init__(self, master: tk.Misc, state: AppState) -> None:
        super().__init__(master, bg=theme.BG)
        self._state = state
        self._filter: str | None = None
        self._keyword = tk.StringVar()
        self._selected: MatchRecord | None = None
        self._filter_tabs: list[tuple[str | None, tk.Label]] = []
        self._build()

    def refresh(self) -> None:
        self._render_stats()
        self._render_list()
        if self._selected is not None:
            current = next(
                (
                    item
                    for item in self._state.records
                    if item.id == self._selected.id
                ),
                None,
            )
            self._show_detail(current)

    def _build(self) -> None:
        head = tk.Frame(self, bg=theme.BG)
        head.pack(fill=tk.X, padx=28, pady=(16, 8))
        self._stats_row = tk.Frame(head, bg=theme.BG)
        self._stats_row.pack(fill=tk.X)

        tools = tk.Frame(self, bg=theme.BG)
        tools.pack(fill=tk.X, padx=28, pady=(4, 8))
        for label, value in _FILTERS:
            tab = tk.Label(
                tools,
                text=label,
                font=theme.BODY_FONT,
                bg=theme.CARD,
                fg=theme.MUTED,
                padx=12,
                pady=5,
                cursor="hand2",
            )
            tab.pack(side=tk.LEFT, padx=(0, 8))
            tab.bind(
                "<Button-1>",
                lambda _e, item=value: self._set_filter(item),
            )
            self._filter_tabs.append((value, tab))
        search = tk.Entry(
            tools,
            textvariable=self._keyword,
            font=theme.BODY_FONT,
            bg=theme.FIELD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=theme.LINE,
            highlightcolor=theme.GOLD,
        )
        search.pack(side=tk.RIGHT, ipady=5, ipadx=8)
        search.bind("<KeyRelease>", lambda _e: self._render_list())
        tk.Label(
            tools,
            text="搜索昵称",
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.BG,
        ).pack(side=tk.RIGHT, padx=(0, 8))

        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 20))
        left = tk.Frame(body, bg=theme.BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._list_canvas = tk.Canvas(
            left,
            bg=theme.BG,
            highlightthickness=0,
            width=420,
        )
        scroll = tk.Scrollbar(left, command=self._list_canvas.yview)
        self._list_inner = tk.Frame(self._list_canvas, bg=theme.BG)
        self._list_inner.bind(
            "<Configure>",
            lambda _e: self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all")
            ),
        )
        self._list_canvas.create_window(
            (0, 0),
            window=self._list_inner,
            anchor="nw",
            width=400,
        )
        self._list_canvas.configure(yscrollcommand=scroll.set)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._list_canvas.bind("<Enter>", self._bind_wheel)
        self._list_canvas.bind("<Leave>", self._unbind_wheel)

        right = tk.Frame(body, bg=theme.PANEL, width=460, padx=16, pady=16)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(16, 0))
        right.pack_propagate(False)
        self._detail_title = tk.Label(
            right,
            text="选择一局查看棋谱",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.PANEL,
        )
        self._detail_title.pack(anchor="w")
        self._detail_meta = tk.Label(
            right,
            text="对局结束后会自动记在这台电脑上",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.PANEL,
            justify="left",
            wraplength=420,
        )
        self._detail_meta.pack(anchor="w", pady=(4, 10))
        self._mini = BoardCanvas(
            right,
            cell=24,
            margin=28,
            interactive=False,
        )
        self._mini.pack()
        self._sync_filter_tabs()

    def _bind_wheel(self, _event: tk.Event) -> None:
        self._list_canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event: tk.Event) -> None:
        self._list_canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event: tk.Event) -> None:
        self._list_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_filter(self, result: str | None) -> None:
        self._filter = result
        self._sync_filter_tabs()
        self._render_list()

    def _sync_filter_tabs(self) -> None:
        for value, tab in self._filter_tabs:
            active = value == self._filter
            tab.configure(
                bg=theme.GOLD if active else theme.CARD,
                fg=theme.BG if active else theme.MUTED,
            )

    def _render_stats(self) -> None:
        for child in self._stats_row.winfo_children():
            child.destroy()
        stats = self._state.stats()
        rate = f"{stats.win_rate * 100:.0f}%"
        chips = (
            ("总场", str(stats.total)),
            ("胜", str(stats.wins)),
            ("负", str(stats.losses)),
            ("和", str(stats.draws)),
            ("胜率", rate),
        )
        for title, value in chips:
            card = tk.Frame(self._stats_row, bg=theme.CARD, padx=16, pady=10)
            card.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(
                card,
                text=title,
                font=theme.CAPTION_FONT,
                fg=theme.MUTED,
                bg=theme.CARD,
            ).pack(anchor="w")
            tk.Label(
                card,
                text=value,
                font=theme.DISPLAY_FONT,
                fg=theme.TEXT,
                bg=theme.CARD,
            ).pack(anchor="w")

    def _render_list(self) -> None:
        for child in self._list_inner.winfo_children():
            child.destroy()
        records = self._state.query(
            result=self._filter,
            keyword=self._keyword.get(),
        )
        if not records:
            tk.Label(
                self._list_inner,
                text="没有符合条件的对局",
                font=theme.BODY_FONT,
                fg=theme.MUTED,
                bg=theme.BG,
            ).pack(anchor="w", pady=24)
            return
        for record in records:
            self._add_row(record)

    def _add_row(self, record: MatchRecord) -> None:
        selected = (
            self._selected is not None and self._selected.id == record.id
        )
        bg = theme.LINE if selected else theme.CARD
        row = tk.Frame(self._list_inner, bg=bg, padx=14, pady=10)
        row.pack(fill=tk.X, pady=(0, 8))
        color = {
            RESULT_WIN: theme.WIN,
            RESULT_LOSE: theme.LOSE,
            RESULT_DRAW: theme.GOLD,
            RESULT_LEFT: theme.MUTED,
        }.get(record.result, theme.TEXT)
        top = tk.Frame(row, bg=bg)
        top.pack(fill=tk.X)
        tk.Label(
            top,
            text=record.result_label,
            font=theme.HEAD_FONT,
            fg=color,
            bg=bg,
        ).pack(side=tk.LEFT)
        tk.Label(
            top,
            text=record.played_at.replace("T", " ")[:16],
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=bg,
        ).pack(side=tk.RIGHT)
        tk.Label(
            row,
            text=(
                f"对阵 {record.opponent_name}  ·  "
                f"执{record.color_label}  ·  "
                f"{record.move_count} 手"
            ),
            font=theme.BODY_FONT,
            fg=theme.TEXT,
            bg=bg,
        ).pack(anchor="w", pady=(4, 0))
        for widget in (row, *row.winfo_children(), top, *top.winfo_children()):
            widget.bind("<Button-1>", lambda _e, item=record: self._pick(item))

    def _pick(self, record: MatchRecord) -> None:
        self._selected = record
        self._render_list()
        self._show_detail(record)

    def _show_detail(self, record: MatchRecord | None) -> None:
        if record is None:
            self._detail_title.config(text="选择一局查看棋谱")
            self._detail_meta.config(text="对局结束后会自动记在这台电脑上")
            self._mini.reset()
            return
        minutes, seconds = divmod(record.duration_seconds, 60)
        self._detail_title.config(
            text=f"{record.result_label}  ·  vs {record.opponent_name}"
        )
        self._detail_meta.config(
            text=(
                f"{record.played_at.replace('T', ' ')[:19]}  ·  "
                f"你执{record.color_label}  ·  {record.move_count} 手  ·  "
                f"{minutes:02d}:{seconds:02d}\n房间 {record.room_code or '—'}"
            )
        )
        board = Board(15)
        last = None
        for item in record.moves:
            try:
                pos = Position(int(item["row"]), int(item["col"]))
                stone = Stone.from_code(str(item["color"]))
            except (KeyError, TypeError, ValueError):
                continue
            if board.in_bounds(pos) and board.is_empty(pos):
                board.place(pos, stone)
                last = pos
        win_line: list[Position] = []
        if last is not None:
            win_line = Referee().winning_line(board, last)
        self._mini.set_board(
            board,
            last,
            None,
            False,
            win_line=win_line,
            animate=False,
        )
