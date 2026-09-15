"""Start screen: create a room (become host) or join by room code."""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from gomoku.communication.lan import local_ipv4
from gomoku.communication.room_code import (
    RoomCodeError,
    decode_endpoint,
    encode_endpoint,
)
from gomoku.communication.server import start_embedded_server
from gomoku.config import DEFAULT_PORT
from gomoku.presentation.app import run_client

logger = logging.getLogger(__name__)


@dataclass
class SessionLaunch:
    """Parameters collected by the lobby before opening the board."""

    name: str
    host: str
    port: int
    room_code: str | None
    is_host: bool


def run_lobby() -> int:
    """Show the start window; returns after the match window closes."""
    root = tk.Tk()
    app = LobbyApp(root)
    root.mainloop()
    launch = app.launch
    if launch is None:
        return 0
    run_client(
        launch.host,
        launch.port,
        launch.name,
        room_code=launch.room_code,
        is_host=launch.is_host,
    )
    return 0


class LobbyApp:
    """Tkinter lobby. Creating a room starts the host inside this process."""

    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self.launch: SessionLaunch | None = None
        root.title("联机五子棋")
        root.resizable(False, False)
        root.configure(bg="#2e2014")
        root.geometry("420x430")
        self._build()

    def _build(self) -> None:
        pad = {"padx": 28, "pady": 6}
        title = tk.Label(
            self._root,
            text="联机五子棋",
            font=("Microsoft YaHei", 22, "bold"),
            fg="#f5ecd6",
            bg="#2e2014",
        )
        title.pack(pady=(28, 4))
        subtitle = tk.Label(
            self._root,
            text="创建房间的人就是房主，把房间号发给朋友即可",
            font=("Microsoft YaHei", 10),
            fg="#c4b094",
            bg="#2e2014",
        )
        subtitle.pack(**pad)

        form = tk.Frame(self._root, bg="#2e2014")
        form.pack(fill=tk.X, **pad)
        tk.Label(
            form,
            text="昵称",
            font=("Microsoft YaHei", 10),
            fg="#f5ecd6",
            bg="#2e2014",
        ).pack(anchor="w")
        self._name = ttk.Entry(form, font=("Microsoft YaHei", 12))
        self._name.insert(0, "玩家")
        self._name.pack(fill=tk.X, pady=(4, 12))

        create = tk.Button(
            form,
            text="创建房间",
            font=("Microsoft YaHei", 12, "bold"),
            bg="#e8b85c",
            fg="#2e2014",
            activebackground="#f0c878",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_create,
        )
        create.pack(fill=tk.X, ipady=8)

        tk.Label(
            form,
            text="或加入朋友的房间",
            font=("Microsoft YaHei", 10),
            fg="#c4b094",
            bg="#2e2014",
        ).pack(anchor="w", pady=(18, 0))
        self._code = ttk.Entry(form, font=("Microsoft YaHei", 12))
        self._code.pack(fill=tk.X, pady=(4, 12))
        self._code.insert(0, "")

        join = tk.Button(
            form,
            text="加入房间",
            font=("Microsoft YaHei", 12, "bold"),
            bg="#3d2b1c",
            fg="#f5ecd6",
            activebackground="#4a3422",
            relief=tk.FLAT,
            cursor="hand2",
            command=self._on_join,
        )
        join.pack(fill=tk.X, ipady=8)

        self._status = tk.Label(
            self._root,
            text="同一 Wi-Fi 下即可对战，无需云服务器",
            font=("Microsoft YaHei", 9),
            fg="#c4b094",
            bg="#2e2014",
            wraplength=360,
            justify="center",
        )
        self._status.pack(pady=(16, 8))
        self._name.focus_set()

    def _player_name(self) -> str:
        name = self._name.get().strip() or "玩家"
        return name[:16]

    def _on_create(self) -> None:
        try:
            port = start_embedded_server("0.0.0.0", DEFAULT_PORT)
            lan_ip = local_ipv4()
            code = encode_endpoint(lan_ip, port)
        except (OSError, RuntimeError, RoomCodeError) as exc:
            self._status.config(text=f"创建失败：{exc}", fg="#d65648")
            return
        self._copy(code)
        hint = f"房间号 {code} 已复制到剪贴板"
        if lan_ip.startswith("127."):
            hint += "（未检测到局域网 IP，目前只能本机自测）"
        self._status.config(text=hint, fg="#56ba6e")
        self.launch = SessionLaunch(
            name=self._player_name(),
            host="127.0.0.1",
            port=port,
            room_code=code,
            is_host=True,
        )
        self._root.destroy()

    def _on_join(self) -> None:
        raw = self._code.get().strip()
        if not raw:
            self._status.config(text="请输入房间号", fg="#d65648")
            return
        try:
            host, port = decode_endpoint(raw)
        except RoomCodeError as exc:
            self._status.config(text=str(exc), fg="#d65648")
            return
        self.launch = SessionLaunch(
            name=self._player_name(),
            host=host,
            port=port,
            room_code=raw.upper(),
            is_host=False,
        )
        self._root.destroy()

    def _copy(self, text: str) -> None:
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self._root.update_idletasks()
        except tk.TclError:
            logger.debug("clipboard unavailable")
