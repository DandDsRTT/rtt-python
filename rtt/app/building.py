from __future__ import annotations

from dataclasses import dataclass
from html import escape as _escape
from typing import TYPE_CHECKING

from nicegui import ui

from rtt.app import _page_parts, tooltips
from rtt.app.page_assets import (
    _GENERAL_TILE_LINES,
    _TILE_FONT,
)
from rtt.app.render_html import (
    _TILE_CELL,
    _TILE_CELL_X,
    _TILE_CELL_Y,
    _TILE_FRAME_H,
    _TILE_FRAME_W,
    _TILE_MATH,
    _fit_font,
    _general_part_html,
    _tile_fold_html,
    _tile_name_pieces,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from rtt.app.editing import EditController
    from rtt.app.editor import Editor
    from rtt.app.gestures import GestureController
    from rtt.app.page_chrome import PageChrome
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.rendering import Renderer


@dataclass(frozen=True)
class ChromeHandlers:
    reset: Callable[[], None]
    dark_toggle: Callable[[], None]
    chapter_change: Callable[[object], None]


class PageBuilder:
    def __init__(
        self,
        editor: Editor,
        chrome: PageChrome,
        runtime: PageRuntime,
        gestures: GestureController,
        edits: EditController,
        renderer: Renderer,
        handlers: ChromeHandlers,
    ) -> None:
        self._editor = editor
        self._chrome = chrome
        self._runtime = runtime
        self._gestures = gestures
        self._edits = edits
        self._renderer = renderer
        self._handlers = handlers
        self.drawer_open = False

    def _setup_page_head(self) -> None:
        _page_parts.setup_page_head()

    def _build_layout(self) -> None:
        _page_parts.build_layout(self)

    def _icon_button(self, ref, icon, on_click, classes, help_key):
        self._chrome.refs[ref] = (
            ui.button(icon=icon, on_click=on_click, color=None)
            .props("flat dense")
            .classes(classes)
            .mark(ref)
            .tooltip(tooltips.CHROME_HELP[help_key])
        )

    def _tile_part(self, key, html, *, marked=False, size=None, style="", passthrough=False):
        fs = size if size is not None else _TILE_FONT.get(key)
        css = (f"font-size:{fs}px;" if fs else "") + style
        if passthrough:
            html = f'<span class="rtt-tile-ink">{html}</span>'
        element = (
            ui.html(html)
            .classes("rtt-tile-part")
            .tooltip(tooltips.show_help(key, _page_parts._setting(self, "terminology")))
        )
        if key == "mnemonics":
            element.classes(add="rtt-tile-mnem")
        if passthrough:
            element.classes(add="rtt-tile-passthrough")
        if marked:
            element.mark(f"showpart:{key}")
        if css:
            element.style(css)
        element.on("click", lambda k=key: self._edits.on_part_click(k))
        self._chrome.tile_parts.setdefault(key, []).append(element)
        return element

    def _tile_named_part(self, key, *, size=None, style="", passthrough=False):
        return self._tile_part(
            key,
            _general_part_html(key),
            marked=True,
            size=size,
            style=style,
            passthrough=passthrough,
        )

    def _build_general_tile(self) -> None:
        ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
        _page_parts._select_all_box(self, "general")
        with ui.element("div").classes("rtt-show-tile"):
            with ui.element("div").classes("rtt-tile-head"):
                ui.html(_tile_fold_html()).classes("rtt-tile-fold")
            for line in _GENERAL_TILE_LINES:
                if "gridded_values" in line:
                    self._build_tile_grid_line()
                elif "names" in line:
                    before, _letter, after = _tile_name_pieces()
                    with ui.element("div").classes("rtt-tile-line"):
                        self._tile_part("names", _escape(before), marked=True)
                        self._tile_named_part("mnemonics")
                        self._tile_part("names", _escape(after))
                elif "presets" in line:
                    with (
                        ui.element("div").classes("rtt-tile-line rtt-tile-line-wide"),
                        ui.element("div").classes("rtt-tile-complexity-box"),
                    ):
                        self._tile_named_part("presets")
                else:
                    with ui.element("div").classes("rtt-tile-line"):
                        for key in line:
                            self._tile_named_part(key)

    def _build_tile_grid_line(self) -> None:
        gut = 20
        hgut = 18
        cell_x = hgut + gut + _TILE_CELL_X
        cell_y = _TILE_CELL_Y
        row_y = cell_y + (_TILE_CELL - 13) // 2
        with (
            ui.element("div").classes("rtt-tile-line"),
            ui.element("div").style(
                f"position:relative;"
                f"width:{hgut + gut + _TILE_FRAME_W + gut + hgut}px;height:{_TILE_FRAME_H}px"
            ),
        ):
            self._tile_named_part(
                "drag_to_combine",
                size=15,
                style=f"position:absolute;left:0;top:{cell_y}px;width:{hgut}px;"
                f"height:{_TILE_CELL}px;justify-content:center",
            )
            self._tile_part(
                "header_symbols",
                _general_part_html("header_symbols"),
                marked=True,
                size=_TILE_FONT["row_label"],
                style=f"position:absolute;left:{hgut}px;top:{row_y}px;width:{gut - 3}px;"
                "height:13px;justify-content:flex-end",
            )
            self._tile_named_part(
                "brackets",
                style=f"position:absolute;left:{hgut + gut}px;top:0",
            )
            self._tile_named_part(
                "gridded_values",
                style=f"position:absolute;left:{cell_x}px;top:{cell_y}px;"
                f"width:{_TILE_CELL}px;height:{_TILE_CELL}px",
            )
            self._tile_value_stack(cell_x, cell_y)

    def _tile_value_stack(self, cell_x, cell_y) -> None:
        self._tile_named_part(
            "math_expressions",
            size=_fit_font(_TILE_MATH, _TILE_CELL),
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
            f"width:{_TILE_CELL}px;height:9px;justify-content:center",
            passthrough=True,
        )
        self._tile_named_part(
            "quantities",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
            f"width:{_TILE_CELL}px;height:11px;justify-content:center",
            passthrough=True,
        )
        self._tile_named_part(
            "decimals",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center",
            passthrough=True,
        )
        self._tile_part(
            "cell_units",
            _general_part_html("cell_units"),
            marked=True,
            size=_TILE_FONT["cellunit"],
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 28}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:var(--fg-caption)",
            passthrough=True,
        )

    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        self._chrome.panelgroup.classes(
            add="rtt-open"
        ) if self.drawer_open else self._chrome.panelgroup.classes(remove="rtt-open")
