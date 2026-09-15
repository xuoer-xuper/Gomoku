"""Small Tk widgets with hover states for a cleaner desktop chrome."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from gomoku.presentation import theme


class HoverButton(tk.Button):
    """Flat button that darkens on hover."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        variant: str = "primary",
        **kwargs,
    ) -> None:
        colors = theme.BUTTONS[variant]
        super().__init__(
            master,
            text=text,
            command=command,
            font=kwargs.pop("font", theme.BUTTON_FONT),
            bg=colors["bg"],
            fg=colors["fg"],
            activebackground=colors["hover"],
            activeforeground=colors["fg"],
            padx=kwargs.pop("padx", 16),
            pady=kwargs.pop("pady", 9),
            cursor="hand2",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            **kwargs,
        )
        self._bg = colors["bg"]
        self._hover = colors["hover"]
        self.bind("<Enter>", lambda _e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda _e: self.configure(bg=self._bg))

    def set_text(self, text: str) -> None:
        self.configure(text=text)


class NavTab(tk.Label):
    """Top-bar text tab."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            text=text,
            font=theme.HEAD_FONT,
            bg=theme.NAV,
            fg=theme.MUTED,
            cursor="hand2",
            padx=12,
            pady=8,
        )
        self._command = command
        self.bind("<Button-1>", lambda _e: self._command())
        self.bind("<Enter>", lambda _e: self.configure(fg=theme.TEXT))
        self.bind("<Leave>", lambda _e: self._idle())
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        self._idle()

    def _idle(self) -> None:
        self.configure(fg=theme.GOLD if self._active else theme.MUTED)


class Field(tk.Frame):
    """Caption + entry used on the lobby cards."""

    def __init__(
        self,
        master: tk.Misc,
        caption: str,
        variable: tk.StringVar,
        placeholder: str = "",
    ) -> None:
        super().__init__(master, bg=theme.CARD)
        tk.Label(
            self,
            text=caption,
            font=theme.CAPTION_FONT,
            fg=theme.MUTED,
            bg=theme.CARD,
        ).pack(anchor="w")
        self.entry = tk.Entry(
            self,
            textvariable=variable,
            font=theme.HEAD_FONT,
            bg=theme.FIELD,
            fg=theme.TEXT,
            insertbackground=theme.TEXT,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=theme.LINE,
            highlightcolor=theme.GOLD,
        )
        self.entry.pack(fill=tk.X, pady=(6, 0), ipady=8)
        if placeholder and not variable.get():
            self.entry.insert(0, placeholder)
