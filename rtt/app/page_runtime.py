from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from rtt.app import settings as show_settings

if TYPE_CHECKING:
    from nicegui import Client

    from rtt.app.layout import Layout


def clamp_chapter(value) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return show_settings.CHAPTER_DEFAULT
    return min(show_settings.CHAPTER_STAR, max(show_settings.CHAPTER_MIN, value))


class PageRuntime:
    def __init__(self) -> None:
        self.building = False
        self.last_lay: Layout | None = None
        self.page_client: Client | None = None
        self.chapter = show_settings.CHAPTER_DEFAULT
        self.dark_mode = False
        self.load_failed = False
        self.tour_active = False

    @contextmanager
    def building_guard(self):
        previous = self.building
        self.building = True
        try:
            yield
        finally:
            self.building = previous

    def set_last_lay(self, layout: Layout) -> None:
        self.last_lay = layout

    def bind_client(self, client: Client) -> None:
        self.page_client = client

    def set_chapter(self, value) -> int:
        self.chapter = clamp_chapter(value)
        return self.chapter

    def column_tokens(self, name: str) -> list:
        idents = self.last_lay.identities if self.last_lay is not None else None
        return [token for token, _ in (idents or {}).get(name, [])]

    def token_index(self, cell_id: str, name: str) -> int | None:
        cell_token = cell_id.split(":", 1)[1]
        for i, token in enumerate(self.column_tokens(name)):
            if str(token) == cell_token:
                return i
        return None

    def available_keys(self) -> list[str]:
        return self.available_in(show_settings.IMPLEMENTED)

    def available_in(self, keys) -> list[str]:
        return [
            k
            for k in keys
            if k in show_settings.IMPLEMENTED and show_settings.reveal_chapter(k) <= self.chapter
        ]

    def chapter_reading(self) -> str:
        chapter = self.chapter
        title = show_settings.CHAPTER_TITLES[chapter]
        return title if chapter >= show_settings.CHAPTER_STAR else f"{chapter}: {title}"

    def dark_icon(self) -> str:
        return "light_mode" if self.dark_mode else "dark_mode"
