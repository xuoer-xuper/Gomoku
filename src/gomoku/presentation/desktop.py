"""Single-window desktop app: lobby, history, board, chat."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

from gomoku.communication.client import GameClient
from gomoku.communication.discover import discover_host
from gomoku.communication.lan import describe_connect_error
from gomoku.communication.messages import Message, MessageType
from gomoku.communication.room_code import (
    RoomCodeError,
    encode_endpoint,
    generate_room_code,
    normalize_room_code,
)
from gomoku.communication.server import (
    set_host_room_code,
    start_embedded_server,
)
from gomoku.communication.settings import RoomSettings
from gomoku.config import BOARD_SIZE, DEFAULT_PORT, THINK_CHOICES
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
from gomoku.presentation.history import HistoryPage
from gomoku.presentation.widgets import Field, HoverButton, NavTab
from gomoku.service.referee import Referee


class GomokuDesktop(tk.Tk):
    """Host and guest share this window; creating a room starts hosting."""

    def __init__(self) -> None:
        super().__init__()
        self.title("联机五子棋")
        self.configure(bg=theme.BG)
        self.geometry("1080x720")
        self.resizable(False, False)
        self._state = AppState()
        self._client = GameClient()
        self._connected = False
        self._board = Board(BOARD_SIZE)
        self._history: list[Position] = []
        self._moves: list[dict] = []
        self._my_color: Stone | None = None
        self._current: Stone | None = None
        self._last: Position | None = None
        self._finished = False
        self._recorded = False
        self._room_code = ""
        self._is_host = False
        self._name = self._state.nickname
        self._opponent = ""
        self._started_at = 0.0
        self._pending: str | None = None
        self._joining = False
        self._join_result: tuple[OSError | None, str, int, str] | None = None
        self._page = "lobby"
        self._win_line: list[Position] = []
        self._opponent_gone = False
        self._result_kind = ""
        self._allow_undo = True
        self._think_seconds = 0
        self._turn_deadline = 0.0
        self._undo_var = tk.BooleanVar(value=True)
        self._think_var = tk.IntVar(value=0)
        self._setup_name = tk.StringVar()
        self._build_nav()
        self._build_lobby()
        self._history_page = HistoryPage(self, self._state)
        self._build_game()
        self._build_setup()
        self._show_page("lobby")
        if not self._state.nickname_set:
            self._setup.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(40, self._pump)

    def _build_nav(self) -> None:
        self._nav = tk.Frame(self, bg=theme.NAV, height=56)
        self._nav.pack(fill=tk.X)
        self._nav.pack_propagate(False)
        tk.Label(
            self._nav,
            text="五子棋",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.NAV,
            padx=20,
        ).pack(side=tk.LEFT)
        self._tab_lobby = NavTab(self._nav, "大厅", lambda: self._show_page("lobby"))
        self._tab_history = NavTab(
            self._nav,
            "战绩",
            lambda: self._show_page("history"),
        )
        self._tab_lobby.pack(side=tk.LEFT, padx=(8, 0))
        self._tab_history.pack(side=tk.LEFT)
        self._nav_status = tk.Label(
            self._nav,
            text="",
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.NAV,
        )
        self._nav_status.pack(side=tk.RIGHT, padx=16)
        self._nick_label = tk.Label(
            self._nav,
            text="",
            font=theme.CAPTION_FONT,
            fg=theme.GOLD_SOFT,
            bg=theme.NAV,
        )
        self._nick_label.pack(side=tk.RIGHT, padx=(0, 8))
        self._leave_btn = HoverButton(
            self._nav,
            "离开房间",
            self._leave_game,
            variant="danger",
            pady=6,
            padx=12,
            font=theme.BODY_FONT,
        )
        self._refresh_nick()

    def _build_lobby(self) -> None:
        self._lobby = tk.Frame(self, bg=theme.BG, width=1080, height=664)
        self._lobby.pack_propagate(False)
        hero = tk.Frame(self._lobby, bg=theme.BG)
        hero.pack(fill=tk.X, padx=48, pady=(36, 8))
        tk.Label(
            hero,
            text="对 弈 一 局",
            font=theme.TITLE_FONT,
            fg=theme.TEXT,
            bg=theme.BG,
        ).pack(anchor="w")
        tk.Label(
            hero,
            text="创建房间即是房主，把房间号发给同一机房的朋友即可开局",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.BG,
        ).pack(anchor="w", pady=(6, 0))

        cards = tk.Frame(self._lobby, bg=theme.BG)
        cards.pack(fill=tk.X, padx=48, pady=20)
        cards.columnconfigure(0, weight=1, uniform="lobby")
        cards.columnconfigure(1, weight=1, uniform="lobby")
        cards.rowconfigure(0, weight=1)
        self._name_var = tk.StringVar(value=self._state.nickname)
        self._code_var = tk.StringVar()

        create = tk.Frame(cards, bg=theme.CARD, padx=24, pady=22, height=340)
        create.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(
            create,
            text="创建房间",
            font=theme.DISPLAY_FONT,
            fg=theme.GOLD,
            bg=theme.CARD,
        ).pack(anchor="w")
        tk.Label(
            create,
            text="先设规则，再生成随机房间号",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w", pady=(4, 14))
        undo_row = tk.Frame(create, bg=theme.CARD)
        undo_row.pack(fill=tk.X)
        tk.Checkbutton(
            undo_row,
            text="允许悔棋（需对方同意，撤回自己上一手）",
            variable=self._undo_var,
            font=theme.BODY_FONT,
            bg=theme.CARD,
            fg=theme.TEXT,
            selectcolor=theme.FIELD,
            activebackground=theme.CARD,
            activeforeground=theme.TEXT,
            highlightthickness=0,
        ).pack(anchor="w")
        think_row = tk.Frame(create, bg=theme.CARD)
        think_row.pack(fill=tk.X, pady=(12, 0))
        tk.Label(
            think_row,
            text="每手思考时间",
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w")
        options = []
        for seconds in THINK_CHOICES:
            label = "不限" if seconds == 0 else f"{seconds} 秒"
            options.append(label)
        self._think_labels = {
            (0 if item == "不限" else int(item.split()[0])): item
            for item in options
        }
        self._think_display = tk.StringVar(value="不限")
        think_btn = tk.Menubutton(
            think_row,
            textvariable=self._think_display,
            font=theme.HEAD_FONT,
            bg=theme.FIELD,
            fg=theme.TEXT,
            activebackground=theme.LINE,
            activeforeground=theme.TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.LINE,
            highlightcolor=theme.GOLD,
            anchor="w",
            padx=12,
            pady=8,
            cursor="hand2",
            direction="below",
        )
        think_menu = tk.Menu(
            think_btn,
            tearoff=0,
            bg=theme.CARD,
            fg=theme.TEXT,
            activebackground=theme.LINE,
            activeforeground=theme.TEXT,
            font=theme.HEAD_FONT,
            bd=0,
        )
        for label in options:
            think_menu.add_command(
                label=label,
                command=lambda item=label: self._on_think_choice(item),
            )
        think_btn.configure(menu=think_menu)
        think_btn.pack(fill=tk.X, pady=(6, 0), ipady=4)
        HoverButton(create, "创建房间", self._create).pack(
            fill=tk.X,
            pady=(18, 0),
            side=tk.BOTTOM,
        )
        tk.Frame(create, bg=theme.CARD).pack(fill=tk.BOTH, expand=True)

        join = tk.Frame(cards, bg=theme.CARD, padx=24, pady=22, height=340)
        join.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        tk.Label(
            join,
            text="加入房间",
            font=theme.DISPLAY_FONT,
            fg=theme.GOLD,
            bg=theme.CARD,
        ).pack(anchor="w")
        tk.Label(
            join,
            text="输入朋友的随机房间号",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w", pady=(4, 14))
        Field(join, "房间号", self._code_var).pack(fill=tk.X)
        HoverButton(
            join,
            "加入房间",
            self._join,
            variant="secondary",
        ).pack(fill=tk.X, pady=(18, 0), side=tk.BOTTOM)
        tk.Frame(join, bg=theme.CARD).pack(fill=tk.BOTH, expand=True)

        self._lobby_status = tk.Label(
            self._lobby,
            text="同一机房或同一 Wi-Fi 即可对战，战绩保存在这台电脑",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.BG,
            wraplength=900,
            justify="left",
        )
        self._lobby_status.pack(fill=tk.X, padx=48, pady=(4, 12))

        recent_wrap = tk.Frame(self._lobby, bg=theme.BG)
        recent_wrap.pack(fill=tk.BOTH, expand=True, padx=48, pady=(8, 24))
        header = tk.Frame(recent_wrap, bg=theme.BG)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="最近对局",
            font=theme.HEAD_FONT,
            fg=theme.TEXT,
            bg=theme.BG,
        ).pack(side=tk.LEFT)
        HoverButton(
            header,
            "查看全部战绩",
            lambda: self._show_page("history"),
            variant="ghost",
            pady=4,
            padx=10,
            font=theme.CAPTION_FONT,
        ).pack(side=tk.RIGHT)
        self._recent_row = tk.Frame(recent_wrap, bg=theme.BG)
        self._recent_row.pack(fill=tk.X, pady=(12, 0))

    def _build_game(self) -> None:
        self._game = tk.Frame(self, bg=theme.BG, width=1080, height=664)
        self._game.pack_propagate(False)
        self._board_host = tk.Frame(self._game, bg=theme.BG, padx=20, pady=16)
        self._board_host.pack(side=tk.LEFT, fill=tk.BOTH)
        self._canvas = BoardCanvas(self._board_host, self._on_place)
        self._canvas.pack()
        self._build_result_overlay()
        side = tk.Frame(self._game, bg=theme.PANEL, width=340)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)
        inner = tk.Frame(side, bg=theme.PANEL, padx=18, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)

        self._room_label = tk.Label(
            inner,
            text="房间",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.PANEL,
        )
        self._room_label.pack(anchor="w")
        HoverButton(
            inner,
            "复制房间号",
            self._copy_code,
            variant="ghost",
            pady=6,
        ).pack(fill=tk.X, pady=(8, 12))

        players = tk.Frame(inner, bg=theme.PANEL)
        players.pack(fill=tk.X)
        self._me_card, self._me_name, self._me_role = self._player_card(
            players,
            "你",
        )
        self._me_card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self._op_card, self._op_name, self._op_role = self._player_card(
            players,
            "对手",
        )
        self._op_card.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self._status_label = tk.Label(
            inner,
            text="等待对手加入",
            font=theme.DISPLAY_FONT,
            fg=theme.TEXT,
            bg=theme.PANEL,
            wraplength=300,
            justify="left",
        )
        self._status_label.pack(anchor="w", pady=(14, 4))
        self._hint_label = tk.Label(
            inner,
            text="",
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.PANEL,
            wraplength=300,
            justify="left",
        )
        self._hint_label.pack(anchor="w", pady=(0, 10))

        self._action_row = tk.Frame(inner, bg=theme.PANEL)
        self._action_row.pack(fill=tk.X, pady=(0, 8))
        self._undo_btn = HoverButton(
            self._action_row,
            "悔棋",
            self._request_undo,
            variant="secondary",
            pady=8,
        )
        self._undo_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        HoverButton(
            self._action_row,
            "投降",
            self._resign,
            variant="danger",
            pady=8,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X)

        self._prompt_slot = tk.Frame(inner, bg=theme.PANEL)
        self._prompt_slot.pack(fill=tk.X)
        self._prompt = tk.Frame(self._prompt_slot, bg=theme.CARD)
        self._prompt_text = tk.Label(
            self._prompt,
            text="",
            font=theme.BODY_FONT,
            fg=theme.TEXT,
            bg=theme.CARD,
            wraplength=280,
        )
        self._prompt_text.pack(anchor="w", padx=10, pady=(10, 6))
        prow = tk.Frame(self._prompt, bg=theme.CARD)
        prow.pack(fill=tk.X, padx=10, pady=(0, 10))
        HoverButton(prow, "同意", self._accept_pending, pady=6).pack(
            side=tk.LEFT,
            expand=True,
            fill=tk.X,
            padx=(0, 6),
        )
        HoverButton(
            prow,
            "拒绝",
            self._reject_pending,
            variant="secondary",
            pady=6,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X)

        tk.Label(
            inner,
            text="对话",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.PANEL,
        ).pack(anchor="w", pady=(8, 4))
        self._chat = ScrolledText(
            inner,
            height=10,
            bg=theme.FIELD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            font=theme.BODY_FONT,
            relief=tk.FLAT,
            state=tk.DISABLED,
            wrap=tk.WORD,
            bd=0,
        )
        self._chat.pack(fill=tk.BOTH, expand=True)
        self._chat.tag_config("sys", foreground=theme.MUTED)
        self._chat.tag_config("me", foreground=theme.GOLD)
        self._chat.tag_config("peer", foreground=theme.TEXT)
        chat_row = tk.Frame(inner, bg=theme.PANEL)
        chat_row.pack(fill=tk.X, pady=(8, 0))
        self._chat_var = tk.StringVar()
        chat_entry = tk.Entry(
            chat_row,
            textvariable=self._chat_var,
            font=theme.BODY_FONT,
            bg=theme.FIELD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=theme.LINE,
            highlightcolor=theme.GOLD,
        )
        chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7)
        chat_entry.bind("<Return>", lambda _e: self._send_chat())
        HoverButton(
            chat_row,
            "发送",
            self._send_chat,
            variant="secondary",
            pady=6,
            padx=12,
        ).pack(side=tk.RIGHT, padx=(8, 0))

    def _player_card(
        self,
        parent: tk.Misc,
        caption: str,
    ) -> tuple[tk.Frame, tk.Label, tk.Label]:
        card = tk.Frame(parent, bg=theme.CARD, padx=10, pady=8)
        tk.Label(
            card,
            text=caption,
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w")
        name = tk.Label(
            card,
            text="—",
            font=theme.HEAD_FONT,
            fg=theme.TEXT,
            bg=theme.CARD,
        )
        name.pack(anchor="w")
        role = tk.Label(
            card,
            text="",
            font=theme.CAPTION_FONT,
            fg=theme.GOLD_SOFT,
            bg=theme.CARD,
        )
        role.pack(anchor="w")
        return card, name, role

    def _build_result_overlay(self) -> None:
        self._result = tk.Frame(self._board_host, bg=theme.CARD, padx=28, pady=22)
        self._result_badge = tk.Canvas(
            self._result,
            width=92,
            height=92,
            bg=theme.CARD,
            highlightthickness=0,
        )
        self._result_badge.pack(pady=(4, 8))
        self._result_title = tk.Label(
            self._result,
            text="",
            font=theme.RESULT_FONT,
            fg=theme.GOLD,
            bg=theme.CARD,
        )
        self._result_title.pack()
        self._result_sub = tk.Label(
            self._result,
            text="",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        )
        self._result_sub.pack(pady=(4, 16))
        self._result_btns = tk.Frame(self._result, bg=theme.CARD)
        self._result_btns.pack(fill=tk.X)
        self._result_leave = HoverButton(
            self._result_btns,
            "离开",
            self._leave_game,
            variant="secondary",
        )
        self._result_rematch = HoverButton(
            self._result_btns,
            "再战",
            self._request_rematch,
            variant="primary",
        )
        self._result_accept = HoverButton(
            self._result_btns,
            "同意再战",
            self._accept_pending,
            variant="primary",
        )
        self._result_reject = HoverButton(
            self._result_btns,
            "拒绝",
            self._reject_pending,
            variant="secondary",
        )

    def _paint_result_badge(self, kind: str) -> None:
        canvas = self._result_badge
        canvas.delete("all")
        if kind == "win":
            fill, text, fg = theme.GOLD, "胜", theme.BG
        elif kind == "lose":
            fill, text, fg = theme.LOSE, "负", theme.TEXT
        else:
            fill, text, fg = theme.LINE, "和", theme.GOLD_SOFT
        canvas.create_oval(8, 8, 84, 84, fill=fill, outline=theme.GOLD_SOFT, width=2)
        canvas.create_text(46, 46, text=text, font=theme.BADGE_FONT, fill=fg)

    def _show_result_overlay(
        self,
        kind: str,
        title: str,
        subtitle: str = "",
        mode: str = "actions",
    ) -> None:
        self._result_kind = kind
        self._paint_result_badge(kind)
        color = {
            "win": theme.WIN,
            "lose": theme.LOSE,
            "draw": theme.GOLD,
        }.get(kind, theme.TEXT)
        self._result_title.config(text=title, fg=color)
        self._result_sub.config(text=subtitle)
        self._result.place(relx=0.5, rely=0.5, anchor="center")
        self._result.lift()
        self._set_result_mode(mode)

    def _hide_result_overlay(self) -> None:
        self._result.place_forget()
        self._result_kind = ""

    def _set_result_mode(self, mode: str) -> None:
        for widget in (
            self._result_leave,
            self._result_rematch,
            self._result_accept,
            self._result_reject,
        ):
            widget.pack_forget()
        if mode == "gone":
            self._result_sub.config(text="对方已离开房间")
            self._result_leave.pack(fill=tk.X)
            return
        if mode == "waiting":
            self._result_sub.config(text="已请求再战，等待对方同意")
            self._result_leave.pack(fill=tk.X)
            return
        if mode == "incoming":
            self._result_leave.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
            self._result_accept.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
            self._result_reject.pack(side=tk.LEFT, expand=True, fill=tk.X)
            return
        self._result_leave.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        self._result_rematch.pack(side=tk.LEFT, expand=True, fill=tk.X)

    def _build_setup(self) -> None:
        self._setup = tk.Frame(self, bg=theme.BG)
        card = tk.Frame(self._setup, bg=theme.CARD, padx=36, pady=32)
        card.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            card,
            text="欢迎来到五子棋",
            font=theme.TITLE_FONT,
            fg=theme.TEXT,
            bg=theme.CARD,
        ).pack()
        tk.Label(
            card,
            text="第一次使用，请先取一个昵称",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(pady=(8, 18))
        Field(card, "昵称", self._setup_name).pack(fill=tk.X)
        self._setup_status = tk.Label(
            card,
            text="",
            font=theme.CAPTION_FONT,
            fg=theme.LOSE,
            bg=theme.CARD,
        )
        self._setup_status.pack(pady=(8, 0))
        HoverButton(card, "进入游戏", self._finish_setup).pack(
            fill=tk.X,
            pady=(16, 0),
        )

    def _finish_setup(self) -> None:
        name = self._setup_name.get().strip()
        if not name:
            self._setup_status.config(text="请输入昵称")
            return
        self._state.nickname = name[:16]
        self._state.nickname_set = True
        self._state.save()
        self._name_var.set(self._state.nickname)
        self._name = self._state.nickname
        self._refresh_nick()
        self._setup.place_forget()

    def _refresh_nick(self) -> None:
        if self._state.nickname:
            self._nick_label.config(text=self._state.nickname)
        else:
            self._nick_label.config(text="")

    def _on_think_choice(self, label: str) -> None:
        self._think_display.set(label)
        if label == "不限":
            self._think_var.set(0)
        else:
            self._think_var.set(int(label.split()[0]))

    def _show_page(self, name: str) -> None:
        if self._connected and name != "game":
            return
        self._page = name
        self._lobby.pack_forget()
        self._history_page.pack_forget()
        self._game.pack_forget()
        self._leave_btn.pack_forget()
        if name == "lobby":
            self._render_recent()
            self._lobby.pack(fill=tk.BOTH, expand=True)
        elif name == "history":
            self._history_page.refresh()
            self._history_page.pack(fill=tk.BOTH, expand=True)
        else:
            self._game.pack(fill=tk.BOTH, expand=True)
            self._leave_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=10)
        self._tab_lobby.set_active(name == "lobby")
        self._tab_history.set_active(name == "history")
        in_game = name == "game"
        self._tab_lobby.configure(cursor="arrow" if in_game else "hand2")
        self._tab_history.configure(cursor="arrow" if in_game else "hand2")

    def _render_recent(self) -> None:
        for child in self._recent_row.winfo_children():
            child.destroy()
        records = self._state.records[:3]
        if not records:
            tk.Label(
                self._recent_row,
                text="还没有对局。开一盘后，胜负会记在战绩里。",
                font=theme.BODY_FONT,
                fg=theme.MUTED,
                bg=theme.BG,
            ).pack(anchor="w")
            return
        colors = {
            RESULT_WIN: theme.WIN,
            RESULT_LOSE: theme.LOSE,
            RESULT_DRAW: theme.GOLD,
            RESULT_LEFT: theme.MUTED,
        }
        for record in records:
            card = tk.Frame(self._recent_row, bg=theme.CARD, padx=14, pady=12)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
            tk.Label(
                card,
                text=record.result_label,
                font=theme.HEAD_FONT,
                fg=colors.get(record.result, theme.TEXT),
                bg=theme.CARD,
            ).pack(anchor="w")
            tk.Label(
                card,
                text=f"vs {record.opponent_name}",
                font=theme.BODY_FONT,
                fg=theme.TEXT,
                bg=theme.CARD,
            ).pack(anchor="w", pady=(4, 0))
            tk.Label(
                card,
                text=record.played_at.replace("T", " ")[:16],
                font=theme.CAPTION_FONT,
                fg=theme.MUTED,
                bg=theme.CARD,
            ).pack(anchor="w")

    def _remember_name(self) -> str:
        name = (self._name_var.get().strip() or self._state.nickname or "玩家")[:16]
        self._name = name
        self._state.nickname = name
        self._state.nickname_set = True
        self._state.save()
        self._refresh_nick()
        return name

    def _create(self) -> None:
        if not self._state.nickname_set:
            self._setup.place(relx=0, rely=0, relwidth=1, relheight=1)
            return
        self._remember_name()
        settings = RoomSettings(
            allow_undo=bool(self._undo_var.get()),
            think_seconds=int(self._think_var.get()),
        )
        try:
            port = start_embedded_server(
                "0.0.0.0",
                DEFAULT_PORT,
                settings,
            )
            code = generate_room_code()
            set_host_room_code(code)
            self._allow_undo = settings.allow_undo
            self._think_seconds = settings.think_seconds
            self._connect("127.0.0.1", port, code, is_host=True)
        except (OSError, RuntimeError, RoomCodeError) as exc:
            self._lobby_status.config(text=str(exc), fg=theme.LOSE)

    def _join(self) -> None:
        if not self._state.nickname_set:
            self._setup.place(relx=0, rely=0, relwidth=1, relheight=1)
            return
        raw = self._code_var.get().strip()
        if not raw:
            self._lobby_status.config(text="请输入房间号", fg=theme.LOSE)
            return
        if self._joining:
            return
        try:
            code = normalize_room_code(raw)
        except RoomCodeError as exc:
            self._lobby_status.config(text=str(exc), fg=theme.LOSE)
            return
        self._remember_name()
        self._joining = True
        self._lobby_status.config(text="正在寻找房间…", fg=theme.MUTED)
        thread = threading.Thread(
            target=self._join_worker,
            args=(code,),
            name="gomoku-join",
            daemon=True,
        )
        thread.start()

    def _join_worker(self, code: str) -> None:
        error: OSError | None = None
        host, port = "0.0.0.0", 0
        found = discover_host(code, timeout=3.0)
        if found is None:
            error = OSError("找不到房间。请确认房主已创建，且在同一网络。")
        else:
            host, port = found
            try:
                self._client.connect(host, port, timeout=2.0)
            except OSError as exc:
                error = exc
        if error is None:
            try:
                self._client.join(self._name)
            except OSError as exc:
                error = exc
        self._join_result = (error, host, port, code)

    def _finish_join(
        self,
        error: OSError | None,
        host: str,
        port: int,
        code: str,
    ) -> None:
        self._joining = False
        if error is not None:
            self._client.close()
            self._client = GameClient()
            text = str(error)
            if port and not text.startswith("找不到"):
                text = describe_connect_error(error, host, port)
            self._lobby_status.config(text=text, fg=theme.LOSE)
            return
        self._enter_game(code, is_host=False)

    def _connect(
        self,
        host: str,
        port: int,
        code: str,
        is_host: bool,
    ) -> None:
        try:
            self._client.connect(host, port)
            self._client.join(self._name)
        except OSError as exc:
            self._lobby_status.config(
                text=describe_connect_error(exc, host, port),
                fg=theme.LOSE,
            )
            return
        self._enter_game(code, is_host=is_host)

    def _enter_game(self, code: str, is_host: bool) -> None:
        self._room_code = code
        self._is_host = is_host
        self._connected = True
        self._opponent_gone = False
        self._hide_result_overlay()
        self._copy_code()
        self._room_label.config(text=f"房间  {code}")
        self._status_label.config(text="等待对手加入", fg=theme.TEXT)
        self._hint_label.config(text="把房间号发给朋友，对方加入后自动开局")
        self._sync_rule_buttons()
        self._me_name.config(text=self._name)
        self._me_role.config(text="房主" if is_host else "客人")
        self._op_name.config(text="等待中")
        self._op_role.config(text="")
        self._chat.config(state=tk.NORMAL)
        self._chat.delete("1.0", tk.END)
        self._chat.config(state=tk.DISABLED)
        self._append_chat("系统", f"房间号 {code} 已复制", "sys")
        if is_host:
            self._hint_label.config(
                text=RoomSettings(
                    self._allow_undo,
                    self._think_seconds,
                ).label()
            )
            self._append_chat(
                "系统",
                "房间号每次随机。若对方找不到房间，请双方确认同一网络并允许防火墙。",
                "sys",
            )
        self._nav_status.config(text="对局中")
        self._show_page("game")
        self._refresh_board()
        self.title(f"联机五子棋  {code}")

    def _leave_game(self) -> None:
        playing = self._connected and not self._finished and self._my_color is not None
        if playing:
            if not messagebox.askyesno(
                "离开房间",
                "对局进行中离开将判负，确定吗？",
            ):
                return
            self._save_record(RESULT_LOSE)
        if self._connected:
            self._client.close()
        self._client = GameClient()
        self._connected = False
        self._finished = False
        self._recorded = False
        self._board = Board(BOARD_SIZE)
        self._history = []
        self._moves = []
        self._my_color = None
        self._current = None
        self._last = None
        self._win_line = []
        self._pending = None
        self._prompt.pack_forget()
        self._hide_result_overlay()
        self._opponent_gone = False
        self._canvas.reset()
        self._nav_status.config(text="")
        self.title("联机五子棋")
        self._lobby_status.config(
            text="已返回大厅，可以再开一局或查看战绩",
            fg=theme.MUTED,
        )
        self._show_page("lobby")

    def _copy_code(self) -> None:
        if not self._room_code:
            return
        self.clipboard_clear()
        self.clipboard_append(self._room_code)
        self._status_label.config(text=f"房间号已复制  {self._room_code}")

    def _on_place(self, position: Position) -> None:
        if self._finished or self._my_color is None:
            return
        if self._current is not self._my_color:
            self._status_label.config(text="还没轮到你", fg=theme.GOLD)
            return
        if not self._board.is_empty(position):
            return
        self._client.place(position.row, position.col)

    def _send_chat(self) -> None:
        text = self._chat_var.get().strip()
        if not text or not self._connected:
            return
        self._client.chat(text)
        self._chat_var.set("")

    def _request_undo(self) -> None:
        if not self._allow_undo:
            self._status_label.config(text="本房间不允许悔棋", fg=theme.LOSE)
            return
        if self._connected:
            self._client.request_undo()

    def _resign(self) -> None:
        if not self._connected or self._finished or self._my_color is None:
            return
        if not messagebox.askyesno("投降", "确定认输吗？"):
            return
        self._client.resign()

    def _request_rematch(self) -> None:
        if not self._connected or not self._finished:
            self._status_label.config(text="对局进行中不能再战", fg=theme.LOSE)
            return
        if self._opponent_gone:
            self._set_result_mode("gone")
            return
        self._client.request_rematch()
        self._set_result_mode("waiting")

    def _accept_pending(self) -> None:
        self._reply_pending(True)

    def _reject_pending(self) -> None:
        self._reply_pending(False)

    def _reply_pending(self, accepted: bool) -> None:
        if self._pending == "undo":
            self._client.reply_undo(accepted)
        elif self._pending == "rematch":
            self._client.reply_rematch(accepted)
            if not accepted and self._result_kind:
                self._set_result_mode("actions")
        self._pending = None
        self._prompt.pack_forget()

    def _show_prompt(self, kind: str, text: str) -> None:
        self._pending = kind
        self._prompt_text.config(text=text)
        self._prompt.pack(fill=tk.X, pady=(0, 10), in_=self._prompt_slot)

    def _append_chat(self, name: str, text: str, tag: str = "peer") -> None:
        self._chat.config(state=tk.NORMAL)
        self._chat.insert(tk.END, f"{name}  ", tag)
        self._chat.insert(tk.END, f"{text}\n", tag)
        self._chat.see(tk.END)
        self._chat.config(state=tk.DISABLED)

    def _pump(self) -> None:
        result = self._join_result
        if result is not None:
            self._join_result = None
            self._finish_join(*result)
        if self._connected:
            for message in self._client.poll():
                self._dispatch(message)
        self._refresh_clock()
        self.after(80, self._pump)

    def _sync_rule_buttons(self) -> None:
        if self._allow_undo:
            if not self._undo_btn.winfo_ismapped():
                self._undo_btn.pack(
                    side=tk.LEFT,
                    expand=True,
                    fill=tk.X,
                    padx=(0, 6),
                )
        else:
            self._undo_btn.pack_forget()

    def _arm_clock(self) -> None:
        if self._think_seconds > 0 and not self._finished:
            self._turn_deadline = time.time() + self._think_seconds
        else:
            self._turn_deadline = 0.0

    def _refresh_clock(self) -> None:
        if (
            not self._connected
            or self._finished
            or self._think_seconds <= 0
            or self._turn_deadline <= 0
            or self._my_color is None
        ):
            return
        remain = max(0, int(self._turn_deadline - time.time()))
        mine = self._current is self._my_color
        who = "你" if mine else "对方"
        self._hint_label.config(text=f"{who}的思考时间  {remain} 秒")

    def _refresh_board(self, animate: bool = True) -> None:
        my_turn = (
            not self._finished
            and self._my_color is not None
            and self._current is self._my_color
        )
        self._canvas.set_board(
            self._board,
            self._last,
            self._my_color if my_turn else None,
            my_turn,
            win_line=self._win_line,
            animate=animate,
        )
        self._paint_turn()

    def _paint_turn(self) -> None:
        mine = (
            not self._finished
            and self._my_color is not None
            and self._current is self._my_color
        )
        theirs = (
            not self._finished
            and self._my_color is not None
            and self._current is not None
            and not mine
        )
        self._me_card.configure(bg=theme.LINE if mine else theme.CARD)
        self._op_card.configure(bg=theme.LINE if theirs else theme.CARD)

    def _dispatch(self, message: Message) -> None:
        table = {
            MessageType.WAITING.value: self._on_waiting,
            MessageType.GAME_START.value: self._on_start,
            MessageType.MOVE.value: self._on_move,
            MessageType.INVALID.value: self._on_invalid,
            MessageType.GAME_OVER.value: self._on_over,
            MessageType.OPPONENT_LEFT.value: self._on_left,
            MessageType.CHAT.value: self._on_chat,
            MessageType.UNDO_REQUEST.value: self._on_undo_req,
            MessageType.UNDO.value: self._on_undo,
            MessageType.UNDO_REJECTED.value: self._on_undo_no,
            MessageType.REMATCH_REQUEST.value: self._on_rematch_req,
            MessageType.REMATCH_REJECTED.value: self._on_rematch_no,
            MessageType.ERROR.value: self._on_invalid,
        }
        handler = table.get(message.type)
        if handler is not None:
            handler(message)

    def _on_waiting(self, _message: Message) -> None:
        self._status_label.config(text="等待对手加入", fg=theme.TEXT)

    def _on_start(self, message: Message) -> None:
        color = Stone.from_code(str(message.payload["your_color"]))
        opponent = str(message.payload.get("opponent_name") or "对手")
        self._my_color = color
        self._opponent = opponent
        self._current = Stone.BLACK
        self._board = Board(BOARD_SIZE)
        self._history = []
        self._moves = []
        self._last = None
        self._win_line = []
        self._finished = False
        self._recorded = False
        self._started_at = time.time()
        self._pending = None
        self._prompt.pack_forget()
        self._hide_result_overlay()
        self._opponent_gone = False
        self._allow_undo = bool(message.payload.get("allow_undo", True))
        self._think_seconds = int(message.payload.get("think_seconds") or 0)
        self._sync_rule_buttons()
        self._arm_clock()
        mine = color is Stone.BLACK
        self._status_label.config(
            text="轮到你落子" if mine else "等待对手落子",
            fg=theme.WIN if mine else theme.MUTED,
        )
        rules = RoomSettings(self._allow_undo, self._think_seconds).label()
        self._hint_label.config(text=rules)
        self._me_name.config(text=self._name)
        self._me_role.config(text=f"{color.label}棋")
        self._op_name.config(text=opponent)
        self._op_role.config(text=f"{color.opponent().label}棋")
        self._append_chat("系统", "对局开始，黑棋先行", "sys")
        self._refresh_board(animate=False)

    def _on_move(self, message: Message) -> None:
        row = int(message.payload["row"])
        col = int(message.payload["col"])
        stone = Stone.from_code(str(message.payload["color"]))
        position = Position(row, col)
        if self._board.is_empty(position):
            self._board.place(position, stone)
            self._history.append(position)
            self._moves.append(
                {"row": row, "col": col, "color": stone.code}
            )
        self._last = position
        nxt = message.payload.get("next_turn")
        self._current = Stone.from_code(str(nxt)) if nxt else None
        if not self._finished:
            mine = self._current is self._my_color
            self._status_label.config(
                text="轮到你落子" if mine else "等待对手落子",
                fg=theme.WIN if mine else theme.MUTED,
            )
            self._arm_clock()
        self._refresh_board()

    def _on_invalid(self, message: Message) -> None:
        reason = str(
            message.payload.get("reason")
            or message.payload.get("message")
            or "无效操作"
        )
        self._status_label.config(text=reason, fg=theme.LOSE)

    def _on_over(self, message: Message) -> None:
        self._finished = True
        winner_code = message.payload.get("winner")
        reason = str(message.payload.get("reason") or "")
        extra = ""
        if not winner_code:
            title, color, result, kind = "和棋", theme.GOLD, RESULT_DRAW, "draw"
        else:
            winner = Stone.from_code(str(winner_code))
            won = winner is self._my_color
            if won:
                title, color, result, kind = (
                    "你赢了",
                    theme.WIN,
                    RESULT_WIN,
                    "win",
                )
            else:
                title, color, result, kind = (
                    "你输了",
                    theme.LOSE,
                    RESULT_LOSE,
                    "lose",
                )
            extra = {
                "resign": "对方投降" if won else "你已投降",
                "left": "对方离开" if won else "你已离开",
                "timeout": "对方超时" if won else "你已超时",
            }.get(reason, "")
        text = f"{title}（{extra}）" if extra else title
        if self._last is not None and reason in {"", "five_in_a_row"}:
            self._win_line = Referee().winning_line(self._board, self._last)
        self._turn_deadline = 0.0
        self._status_label.config(text=text, fg=color)
        self._hint_label.config(text="终局后可再战或离开")
        self._append_chat("系统", text, "sys")
        self._save_record(result)
        self._refresh_board()
        mode = "gone" if reason == "left" or self._opponent_gone else "actions"
        self._show_result_overlay(kind, title, extra, mode=mode)

    def _on_left(self, _message: Message) -> None:
        was_playing = not self._finished
        self._finished = True
        self._opponent_gone = True
        self._status_label.config(text="对手已离开", fg=theme.LOSE)
        self._hint_label.config(text="对方已离开，只能返回大厅")
        self._append_chat("系统", "对手已离开", "sys")
        if was_playing and self._moves:
            self._save_record(RESULT_WIN)
            self._show_result_overlay("win", "你赢了", "对方离开", mode="gone")
        elif self._result_kind:
            self._set_result_mode("gone")
        self._refresh_board(animate=False)

    def _on_chat(self, message: Message) -> None:
        name = str(message.payload.get("name") or "玩家")
        text = str(message.payload.get("text") or "")
        system = bool(message.payload.get("system"))
        if system:
            tag = "sys"
        elif name == self._name:
            tag = "me"
        else:
            tag = "peer"
        self._append_chat(name, text, tag)

    def _on_undo_req(self, message: Message) -> None:
        name = str(message.payload.get("name") or "对方")
        self._show_prompt("undo", f"{name} 请求悔棋")

    def _on_undo(self, message: Message) -> None:
        removed = message.payload.get("removed")
        items: list[dict] = []
        if isinstance(removed, list) and removed:
            items = [item for item in removed if isinstance(item, dict)]
        else:
            items = [message.payload]
        for item in items:
            try:
                position = Position(int(item["row"]), int(item["col"]))
            except (KeyError, TypeError, ValueError):
                continue
            if not self._board.is_empty(position):
                self._board.clear(position)
            if self._history and self._history[-1] == position:
                self._history.pop()
            if self._moves:
                self._moves.pop()
        self._last = self._history[-1] if self._history else None
        nxt = message.payload.get("next_turn")
        self._current = Stone.from_code(str(nxt)) if nxt else None
        self._finished = False
        self._win_line = []
        self._arm_clock()
        self._status_label.config(
            text="已悔棋，轮到你" if self._current is self._my_color else "已悔棋",
            fg=theme.GOLD,
        )
        self._append_chat("系统", "悔棋成功，回到请求方上一手", "sys")
        self._pending = None
        self._prompt.pack_forget()
        self._refresh_board(animate=False)

    def _on_undo_no(self, _message: Message) -> None:
        self._status_label.config(text="对方拒绝悔棋", fg=theme.LOSE)
        self._append_chat("系统", "对方拒绝悔棋", "sys")

    def _on_rematch_req(self, message: Message) -> None:
        if not self._finished:
            return
        name = str(message.payload.get("name") or "对方")
        self._pending = "rematch"
        if self._result_kind:
            self._result_sub.config(text=f"{name} 请求再战")
            self._set_result_mode("incoming")
        else:
            self._show_prompt("rematch", f"{name} 请求再战")

    def _on_rematch_no(self, _message: Message) -> None:
        self._status_label.config(text="对方拒绝再战", fg=theme.LOSE)
        self._append_chat("系统", "对方拒绝再战", "sys")
        if self._result_kind:
            self._set_result_mode("actions")
            self._result_sub.config(text="对方拒绝再战，可再次邀请")

    def _save_record(self, result: str) -> None:
        if self._recorded or self._my_color is None:
            return
        self._recorded = True
        duration = time.time() - self._started_at if self._started_at else 0
        record = MatchRecord.create(
            my_name=self._name,
            opponent_name=self._opponent or "对手",
            my_color=self._my_color.code,
            result=result,
            duration_seconds=int(duration),
            room_code=self._room_code,
            moves=self._moves,
        )
        self._state.add_record(record)

    def _close(self) -> None:
        playing = self._connected and not self._finished and self._my_color is not None
        if playing:
            self._save_record(RESULT_LOSE)
        if self._connected:
            self._client.close()
        self.destroy()


def run_app() -> int:
    app = GomokuDesktop()
    app.mainloop()
    return 0


def run_direct_client(host: str, port: int, name: str) -> int:
    app = GomokuDesktop()
    app._name_var.set(name)
    try:
        fake = encode_endpoint(host, port)
    except RoomCodeError:
        fake = f"{host}:{port}"
    app._connect(host, port, fake, is_host=False)
    app.mainloop()
    return 0
