"""Top status bar and footer hint."""

from __future__ import annotations

import pygame

from gomoku.presentation import colors


class Hud:
    """Renders match status; does not own game rules."""

    def __init__(
        self,
        width: int,
        hud_height: int,
        footer_y: int,
        footer_height: int,
        title_font: pygame.font.Font,
        body_font: pygame.font.Font,
    ) -> None:
        self._width = width
        self._hud_height = hud_height
        self._footer_y = footer_y
        self._footer_height = footer_height
        self._title_font = title_font
        self._body_font = body_font

    def draw(
        self,
        surface: pygame.Surface,
        title: str,
        status: str,
        detail: str,
        hint: str,
        status_color: tuple[int, int, int] = colors.ACCENT,
    ) -> None:
        pygame.draw.rect(
            surface,
            colors.HUD_BG,
            pygame.Rect(0, 0, self._width, self._hud_height),
        )
        title_img = self._title_font.render(title, True, colors.TEXT)
        status_img = self._body_font.render(status, True, status_color)
        detail_img = self._body_font.render(detail, True, colors.MUTED)
        surface.blit(title_img, (18, 12))
        surface.blit(status_img, (18, 42))
        surface.blit(detail_img, (18, 62))

        footer = pygame.Rect(
            0,
            self._footer_y,
            self._width,
            self._footer_height,
        )
        pygame.draw.rect(surface, colors.HUD_BG, footer)
        hint_img = self._body_font.render(hint, True, colors.MUTED)
        surface.blit(hint_img, (18, self._footer_y + 12))
