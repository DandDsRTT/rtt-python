from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nicegui.element import Element


class PageChrome:
    def __init__(self) -> None:
        self.panelgroup: Element | None = None
        self.grid_pane: Element | None = None
        self.colhead: Element | None = None
        self.colhead_inner: Element | None = None
        self.colfill: Element | None = None
        self.colfill_inner: Element | None = None
        self.rowfill: Element | None = None
        self.corner: Element | None = None
        self.gridbody: Element | None = None
        self.board: Element | None = None
        self.rowband: Element | None = None
        self.show_scroll: Element | None = None
        self.show_frozen: Element | None = None
        self.select_all_box: Element | None = None
        self.dark_button: Element | None = None
        self.chapter_reading: Element | None = None
        self.chapter_slider: Element | None = None
        self.refs: dict = {}
        self.boxes: dict = {}
        self.section_all: dict = {}
        self.examples: dict = {}
        self.tile_parts: dict = {}
        self.show_rows: dict = {}
        self.cell_parents: dict = {}

    def populate(self, slots: dict) -> None:
        for name, element in slots.items():
            setattr(self, name, element)
