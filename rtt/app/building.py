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


_TEXT_FORM_ORDER = (
    "header_symbols",
    "drag_to_combine",
    "brackets",
    "gridded_values",
    "math_expressions",
    "quantities",
    "decimals",
    "cell_units",
    "symbols",
    "equivalences",
    "names",
    "mnemonics",
    "tile_units",
    "plain_text_values",
    "presets",
    "charts",
    "tile_controls",
)


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
        self._text_form_open = False

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

    def _build_general_tile(self, items) -> None:
        ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
        _page_parts._select_all_checkbox(self, "general")
        with ui.element("div").classes("rtt-show-tile"):
            with ui.element("div").classes("rtt-tile-head"):
                self._tile_part("tile_collapse", _tile_fold_html(), marked=True).classes(
                    add="rtt-tile-fold"
                )
            self._build_general_tile_body()
        self._build_text_form(items)

    def _build_text_form(self, items) -> None:
        with ui.element("div").classes("rtt-show-head"):
            ui.label("show").classes("rtt-show-title")
            ui.label("example").classes("rtt-show-example-header")
        header = (
            ui.element("div")
            .classes("rtt-show-row rtt-grouping-parent rtt-textform-head")
            .mark("textformhead")
            .tooltip(tooltips.TEXT_FORM_HELP)
        )
        with header:
            fold = (
                ui.html(_page_parts._fold_glyph_html(False))
                .classes("rtt-group-fold")
                .mark("textformfold")
            )
            ui.label("settings in text form").classes("rtt-textform-title")
        rows = ui.element("div").classes("rtt-textform-rows")
        rows.set_visibility(False)
        rank = {key: index for index, key in enumerate(_TEXT_FORM_ORDER)}
        with rows:
            for key, label, _default in sorted(
                items, key=lambda item: rank.get(item[0], len(rank))
            ):
                _page_parts.build_show_row(self, key, label)

        def toggle_text_form() -> None:
            self._text_form_open = not self._text_form_open
            rows.set_visibility(self._text_form_open)
            fold.set_content(_page_parts._fold_glyph_html(self._text_form_open))

        header.on("click", toggle_text_form)

    def _build_general_tile_body(self) -> None:
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
                    ui.element("div").classes("rtt-tile-complexity-panel"),
                ):
                    self._tile_named_part("presets")
            else:
                with ui.element("div").classes("rtt-tile-line"):
                    for key in line:
                        self._tile_named_part(key)

    def _build_tile_grid_line(self) -> None:
        gut = 18
        label_h = 13
        label_gap = 4
        frame_top = label_h + label_gap
        cell_x = gut + _TILE_CELL_X
        cell_y = frame_top + _TILE_CELL_Y
        with (
            ui.element("div").classes("rtt-tile-line"),
            ui.element("div").style(
                f"position:relative;"
                f"width:{gut + _TILE_FRAME_W + gut}px;height:{frame_top + _TILE_FRAME_H}px"
            ),
        ):
            self._tile_named_part(
                "drag_to_combine",
                size=15,
                style=f"position:absolute;left:0;top:{cell_y}px;width:{gut}px;"
                f"height:{_TILE_CELL}px;justify-content:center",
            )
            self._tile_part(
                "header_symbols",
                _general_part_html("header_symbols"),
                marked=True,
                size=_TILE_FONT["row_label"],
                style=f"position:absolute;left:{cell_x}px;top:0;width:{_TILE_CELL}px;"
                f"height:{label_h}px;justify-content:center",
            )
            self._tile_named_part(
                "brackets",
                style=f"position:absolute;left:{gut}px;top:{frame_top}px",
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
            f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:var(--fg-name)",
            passthrough=True,
        )

    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        self._chrome.panelgroup.classes(
            add="rtt-open"
        ) if self.drawer_open else self._chrome.panelgroup.classes(remove="rtt-open")
