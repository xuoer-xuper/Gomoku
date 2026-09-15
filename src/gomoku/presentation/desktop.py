"""Single-window desktop app: lobby, board, chat, undo and rematch."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from gomoku.communication.client import GameClient
from gomoku.communication.discover import discover_host
from gomoku.communication.lan import (
    describe_connect_error,
    is_usable_lan_ipv4,
    list_local_ipv4,
    local_ipv4,
)
from gomoku.communication.messages import Message, MessageType
from gomoku.communication.room_code import (
    RoomCodeError,
    decode_endpoint,
    encode_endpoint,
)
from gomoku.communication.server import (
    set_host_room_code,
    start_embedded_server,
)
from gomoku.config import BOARD_SIZE, DEFAULT_PORT
from gomoku.data.board import Board
from gomoku.data.position import Position
from gomoku.data.stone import Stone
from gomoku.presentation import theme
from gomoku.presentation.board_canvas import BoardCanvas


class GomokuDesktop(tk.Tk):
    """Host and guest share this window; creating a room starts hosting."""

    def __init__(self) -> None:
        super().__init__()
        self.title("联机五子棋")
        self.configure(bg=theme.BG)
        self.resizable(False, False)
        self._client = GameClient()
        self._connected = False
        self._board = Board(BOARD_SIZE)
        self._history: list[Position] = []
        self._my_color: Stone | None = None
        self._current: Stone | None = None
        self._last: Position | None = None
        self._finished = False
        self._room_code = ""
        self._is_host = False
        self._name = "玩家"
        self._pending: str | None = None
        self._joining = False
        self._join_result: tuple[OSError | None, str, int, str] | None = None
        self._build_lobby()
        self._build_game()
        self._show(self._lobby)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(40, self._pump)

    def _build_lobby(self) -> None:
        self._lobby = tk.Frame(self, bg=theme.BG, width=520, height=560)
        self._lobby.pack_propagate(False)
        tk.Label(
            self._lobby,
            text="五 子 棋",
            font=theme.TITLE_FONT,
            fg=theme.GOLD,
            bg=theme.BG,
        ).pack(pady=(72, 8))
        tk.Label(
            self._lobby,
            text="创建房间的人就是房主 · 把房间号发给朋友",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.BG,
        ).pack()
        card = tk.Frame(self._lobby, bg=theme.CARD, padx=28, pady=24)
        card.pack(pady=36, padx=56, fill=tk.X)
        self._name_var = tk.StringVar(value="玩家")
        self._code_var = tk.StringVar()
        self._label(card, "昵称").pack(anchor="w")
        self._entry(card, self._name_var).pack(fill=tk.X, pady=(4, 16))
        self._gold_button(card, "创建房间", self._create).pack(fill=tk.X)
        tk.Label(
            card,
            text="加入朋友的房间",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w", pady=(18, 0))
        self._entry(card, self._code_var).pack(fill=tk.X, pady=(4, 12))
        self._dark_button(card, "加入房间", self._join).pack(fill=tk.X)
        self._lobby_status = tk.Label(
            self._lobby,
            text="同一机房或同一 Wi-Fi 即可对战，无需安装、无需云服务器",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.BG,
            wraplength=400,
            justify="center",
        )
        self._lobby_status.pack(pady=8, padx=24)

    def _build_game(self) -> None:
        self._game = tk.Frame(self, bg=theme.BG)
        left = tk.Frame(self._game, bg=theme.BG, padx=16, pady=16)
        left.pack(side=tk.LEFT, fill=tk.BOTH)
        self._canvas = BoardCanvas(left, self._on_place)
        self._canvas.pack()
        side = tk.Frame(
            self._game,
            bg=theme.PANEL,
            width=300,
            padx=16,
            pady=16,
        )
        side.pack(side=tk.RIGHT, fill=tk.Y)
        side.pack_propagate(False)
        self._room_label = tk.Label(
            side,
            text="房间",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.PANEL,
        )
        self._room_label.pack(anchor="w")
        self._status_label = tk.Label(
            side,
            text="等待对手",
            font=theme.BODY_FONT,
            fg=theme.TEXT,
            bg=theme.PANEL,
            wraplength=260,
            justify="left",
        )
        self._status_label.pack(anchor="w", pady=(4, 8))
        self._players_label = tk.Label(
            side,
            text="",
            font=theme.BODY_FONT,
            fg=theme.MUTED,
            bg=theme.PANEL,
            justify="left",
        )
        self._players_label.pack(anchor="w", pady=(0, 8))
        self._copy_btn = self._dark_button(
            side,
            "复制房间号",
            self._copy_code,
        )
        self._copy_btn.pack(fill=tk.X, pady=(0, 10))
        row = tk.Frame(side, bg=theme.PANEL)
        row.pack(fill=tk.X, pady=(0, 10))
        self._undo_btn = self._dark_button(row, "悔棋", self._request_undo)
        self._undo_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self._rematch_btn = self._gold_button(
            row,
            "再战",
            self._request_rematch,
        )
        self._rematch_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self._prompt = tk.Frame(side, bg=theme.CARD)
        self._prompt_text = tk.Label(
            self._prompt,
            text="",
            font=theme.BODY_FONT,
            fg=theme.TEXT,
            bg=theme.CARD,
            wraplength=250,
        )
        self._prompt_text.pack(anchor="w", padx=8, pady=(8, 4))
        prow = tk.Frame(self._prompt, bg=theme.CARD)
        prow.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._yes_btn = self._gold_button(prow, "同意", self._accept_pending)
        self._yes_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 6))
        self._no_btn = self._dark_button(prow, "拒绝", self._reject_pending)
        self._no_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        tk.Label(
            side,
            text="对话",
            font=theme.HEAD_FONT,
            fg=theme.GOLD,
            bg=theme.PANEL,
        ).pack(anchor="w", pady=(8, 4))
        self._chat = ScrolledText(
            side,
            height=12,
            bg=theme.CARD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            font=theme.BODY_FONT,
            relief=tk.FLAT,
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self._chat.pack(fill=tk.BOTH, expand=True)
        chat_row = tk.Frame(side, bg=theme.PANEL)
        chat_row.pack(fill=tk.X, pady=(8, 0))
        self._chat_var = tk.StringVar()
        chat_entry = tk.Entry(
            chat_row,
            textvariable=self._chat_var,
            font=theme.BODY_FONT,
            bg=theme.CARD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief=tk.FLAT,
        )
        chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        chat_entry.bind("<Return>", lambda _e: self._send_chat())
        self._dark_button(chat_row, "发送", self._send_chat).pack(
            side=tk.RIGHT,
            padx=(8, 0),
        )

    def _label(self, parent: tk.Misc, text: str) -> tk.Label:
        return tk.Label(
            parent,
            text=text,
            font=theme.BODY_FONT,
            fg=theme.TEXT,
            bg=theme.CARD,
        )

    def _entry(self, parent: tk.Misc, var: tk.StringVar) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=var,
            font=theme.HEAD_FONT,
            bg=theme.BG,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief=tk.FLAT,
        )

    def _gold_button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=theme.BUTTON_FONT,
            bg=theme.GOLD,
            fg=theme.BG,
            activebackground=theme.GOLD_DARK,
            relief=tk.FLAT,
            cursor="hand2",
        )

    def _dark_button(self, parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=theme.BUTTON_FONT,
            bg=theme.LINE,
            fg=theme.TEXT,
            activebackground=theme.CARD,
            relief=tk.FLAT,
            cursor="hand2",
        )

    def _show(self, frame: tk.Frame) -> None:
        self._lobby.pack_forget()
        self._game.pack_forget()
        frame.pack(fill=tk.BOTH, expand=True)

    def _player_name(self) -> str:
        return (self._name_var.get().strip() or "玩家")[:16]

    def _create(self) -> None:
        try:
            port = start_embedded_server("0.0.0.0", DEFAULT_PORT)
            lan_ip = local_ipv4()
            code = encode_endpoint(lan_ip, port)
            set_host_room_code(code)
            self._connect("127.0.0.1", port, code, is_host=True)
        except (OSError, RuntimeError, RoomCodeError) as exc:
            self._lobby_status.config(text=str(exc), fg=theme.LOSE)

    def _join(self) -> None:
        raw = self._code_var.get().strip()
        if not raw:
            self._lobby_status.config(text="请输入房间号", fg=theme.LOSE)
            return
        if self._joining:
            return
        try:
            host, port = decode_endpoint(raw)
        except RoomCodeError as exc:
            self._lobby_status.config(text=str(exc), fg=theme.LOSE)
            return
        self._joining = True
        self._lobby_status.config(text="正在加入房间…", fg=theme.MUTED)
        self._name = self._player_name()
        thread = threading.Thread(
            target=self._join_worker,
            args=(host, port, raw.upper()),
            name="gomoku-join",
            daemon=True,
        )
        thread.start()

    def _join_worker(self, host: str, port: int, code: str) -> None:
        error: OSError | None = None
        try:
            self._client.connect(host, port, timeout=2.0)
        except OSError as exc:
            found = discover_host(code, host, port, timeout=2.0)
            if found is None:
                error = exc
            else:
                try:
                    self._client.connect(found[0], found[1], timeout=2.0)
                except OSError as retry_exc:
                    error = retry_exc
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
            self._lobby_status.config(
                text=describe_connect_error(error, host, port),
                fg=theme.LOSE,
            )
            return
        self._enter_game(code, is_host=False)

    def _connect(
        self,
        host: str,
        port: int,
        code: str,
        is_host: bool,
    ) -> None:
        self._name = self._player_name()
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
        self._copy_code()
        self._room_label.config(text=f"房间  {code}")
        self._status_label.config(text="等待对手加入…")
        extras = []
        if is_host:
            lan_ip = local_ipv4()
            extras.append(f"本机 {lan_ip}")
            if not is_usable_lan_ipv4(lan_ip):
                extras.append("未检测到局域网 IP，目前只能本机自测")
            else:
                others = [
                    ip for ip in list_local_ipv4() if ip != lan_ip
                ]
                if others:
                    extras.append("其他网卡 " + "、".join(others[:2]))
        self._players_label.config(
            text="\n".join([f"你：{self._name}", *extras])
        )
        self._append_chat("系统", f"房间号 {code} 已复制")
        if is_host:
            self._append_chat(
                "系统",
                "若对方提示连接失败，请在防火墙弹窗点允许，并关掉代理后再开房间",
            )
        self._show(self._game)
        self._refresh_board()
        self.title(f"联机五子棋  {code}")

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
            self._status_label.config(text="还没轮到你")
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
        if self._connected:
            self._client.request_undo()

    def _request_rematch(self) -> None:
        if self._connected:
            self._client.request_rematch()

    def _accept_pending(self) -> None:
        self._reply_pending(True)

    def _reject_pending(self) -> None:
        self._reply_pending(False)

    def _reply_pending(self, accepted: bool) -> None:
        if self._pending == "undo":
            self._client.reply_undo(accepted)
        elif self._pending == "rematch":
            self._client.reply_rematch(accepted)
        self._pending = None
        self._prompt.pack_forget()

    def _show_prompt(self, kind: str, text: str) -> None:
        self._pending = kind
        self._prompt_text.config(text=text)
        self._prompt.pack(fill=tk.X, pady=(0, 10))

    def _append_chat(self, name: str, text: str) -> None:
        self._chat.config(state=tk.NORMAL)
        self._chat.insert(tk.END, f"{name}：{text}\n")
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
        self.after(80, self._pump)

    def _refresh_board(self) -> None:
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
        )

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
            MessageType.ERROR.value: self._on_invalid,
        }
        handler = table.get(message.type)
        if handler is not None:
            handler(message)

    def _on_waiting(self, _message: Message) -> None:
        self._status_label.config(text="等待对手加入，把房间号发给朋友")

    def _on_start(self, message: Message) -> None:
        color = Stone.from_code(str(message.payload["your_color"]))
        opponent = str(message.payload.get("opponent_name") or "对手")
        self._my_color = color
        self._current = Stone.BLACK
        self._board = Board(BOARD_SIZE)
        self._history = []
        self._last = None
        self._finished = False
        self._pending = None
        self._prompt.pack_forget()
        self._status_label.config(
            text="轮到你落子" if color is Stone.BLACK else "等待对手落子",
            fg=theme.WIN if color is Stone.BLACK else theme.MUTED,
        )
        self._players_label.config(
            text=(
                f"你：{color.label}（{self._name}）\n"
                f"对手：{color.opponent().label}（{opponent}）"
            )
        )
        self._append_chat("系统", "对局开始，黑棋先行")
        self._refresh_board()

    def _on_move(self, message: Message) -> None:
        row = int(message.payload["row"])
        col = int(message.payload["col"])
        stone = Stone.from_code(str(message.payload["color"]))
        position = Position(row, col)
        if self._board.is_empty(position):
            self._board.place(position, stone)
            self._history.append(position)
        self._last = position
        nxt = message.payload.get("next_turn")
        self._current = Stone.from_code(str(nxt)) if nxt else None
        if not self._finished:
            mine = self._current is self._my_color
            self._status_label.config(
                text="轮到你落子" if mine else "等待对手落子",
                fg=theme.WIN if mine else theme.MUTED,
            )
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
        if not winner_code:
            text, color = "和棋", theme.GOLD
        else:
            winner = Stone.from_code(str(winner_code))
            if winner is self._my_color:
                text, color = "你赢了", theme.WIN
            else:
                text, color = "你输了", theme.LOSE
        self._status_label.config(text=f"{text}  ·  可点再战", fg=color)
        self._append_chat("系统", text)
        self._refresh_board()

    def _on_left(self, _message: Message) -> None:
        self._finished = True
        self._status_label.config(text="对手已离开", fg=theme.LOSE)
        self._append_chat("系统", "对手已离开")

    def _on_chat(self, message: Message) -> None:
        name = str(message.payload.get("name") or "玩家")
        text = str(message.payload.get("text") or "")
        self._append_chat(name, text)

    def _on_undo_req(self, message: Message) -> None:
        name = str(message.payload.get("name") or "对方")
        self._show_prompt("undo", f"{name} 请求悔棋")

    def _on_undo(self, message: Message) -> None:
        row = int(message.payload["row"])
        col = int(message.payload["col"])
        position = Position(row, col)
        if not self._board.is_empty(position):
            self._board.clear(position)
        if self._history and self._history[-1] == position:
            self._history.pop()
        self._last = self._history[-1] if self._history else None
        nxt = message.payload.get("next_turn")
        self._current = Stone.from_code(str(nxt)) if nxt else None
        self._finished = False
        self._status_label.config(text="已悔棋", fg=theme.GOLD)
        self._append_chat("系统", "悔棋成功")
        self._pending = None
        self._prompt.pack_forget()
        self._refresh_board()

    def _on_undo_no(self, _message: Message) -> None:
        self._status_label.config(text="对方拒绝悔棋", fg=theme.LOSE)
        self._append_chat("系统", "对方拒绝悔棋")

    def _on_rematch_req(self, message: Message) -> None:
        name = str(message.payload.get("name") or "对方")
        self._show_prompt("rematch", f"{name} 请求再战")

    def _close(self) -> None:
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
