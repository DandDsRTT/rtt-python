from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from html import escape as _escape
from typing import TYPE_CHECKING

from nicegui import ui

from rtt.app import settings as show_settings
from rtt.app import (
    tooltips,
)
from rtt.app.page_assets import (
    _AUDIO_GLYPHS,
    _AUDIO_JS,
    _CSS,
    _DECIMAL_JS,
    _FRACTION_JS,
    _FREEZE_JS,
    _GENERAL_TILE_LINES,
    _GUIDE_JS,
    _STATE_PARAM,
    _TABNAV_JS,
    _TILE_FONT,
    _TOOLTIP_DELAY_MS,
    _TOUR_JS,
    _TOUR_STEPS,
    _ZOOM_JS,
    _audio_bank,
    _encode_state,
)
from rtt.app.render_html import (
    _TILE_CELL,
    _TILE_CELL_X,
    _TILE_CELL_Y,
    _TILE_FRAME_H,
    _TILE_FRAME_W,
    _TILE_MATH,
    _example_html,
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

_log = logging.getLogger(__name__)


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
        ui.add_css(_CSS)
        ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS}")
        ui.add_body_html(
            f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>"
        )
        ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
        ui.add_body_html(f"<script>{_FRACTION_JS}</script>")
        ui.add_body_html(f"<script>{_DECIMAL_JS}</script>")
        ui.add_body_html(f"<script>{_TABNAV_JS}</script>")
        ui.add_body_html(f"<script>{_ZOOM_JS}</script>")
        ui.add_body_html(f"<script>{_GUIDE_JS}</script>")
        ui.add_body_html(
            f"<script>window.rttTour={{steps:{json.dumps(_TOUR_STEPS)},autostart:true}};\n"
            f"{_TOUR_JS}</script>"
        )
        # NiceGUI: trim its default 16px .nicegui-content padding to a slim app margin.
        ui.query(".nicegui-content").style("padding:6px")

        with ui.element("div").classes("rtt-busy"):
            with ui.element("div").classes("rtt-busy-card"):
                ui.element("div").classes("rtt-busy-spin")
                ui.label("Computing…")

    def _build_layout(self) -> None:
        with ui.element("div").classes("rtt-shell"):
            self._chrome.panelgroup = ui.element("div").classes("rtt-panelgroup")
            with self._chrome.panelgroup:
                with ui.element("div").classes("rtt-chrome"):
                    self._pane_chrome()
                self._build_drawer()
            self._build_grid_pane()

    def _build_grid_pane(self) -> None:
        self._chrome.grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with self._chrome.grid_pane:
            self._chrome.colfill = ui.element("div").classes("rtt-colfill").mark("colfill")
            with self._chrome.colfill:
                self._chrome.colfill_inner = (
                    ui.element("div").classes("rtt-colfill-inner").mark("colfillinner")
                )
            self._chrome.colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with self._chrome.colhead:
                self._chrome.colhead_inner = (
                    ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
                )
            self._build_corner()
            self._build_gridbody()

    def _build_drawer(self) -> None:
        drawer = ui.element("div").classes("rtt-drawer")
        with drawer, ui.element("div").classes("rtt-drawer-inner"):
            self._build_show_frozen()
            self._chrome.show_scroll = (
                ui.element("div").classes("rtt-show-scroll").mark("showscroll")
            )
            with self._chrome.show_scroll:
                self._build_chapter_group()
                for group_name, items in show_settings.SHOW_GROUPS:
                    with ui.element("div").classes("rtt-show-group"):
                        if group_name == "general":
                            self._build_general_tile()
                        else:
                            self._build_show_group(items)

    def _build_corner(self) -> None:
        self._chrome.corner = ui.element("div").classes("rtt-corner").mark("corner")
        with self._chrome.corner:
            self._build_title_buttons()
            self._build_approach_radio()

    def _build_gridbody(self) -> None:
        self._chrome.gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
        with self._chrome.gridbody:
            self._chrome.board = ui.element("div").classes("rtt-gridcontent").mark("board")
            with self._chrome.board, ui.element("div").classes("rtt-band"):
                self._chrome.rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
        self._chrome.refs["approach"].move(self._chrome.board)
        self._chrome.cell_parents = {
            "corner": self._chrome.corner,
            "col": self._chrome.colhead_inner,
            "row": self._chrome.rowband,
            "body": self._chrome.board,
        }

    def _icon_button(self, ref, icon, on_click, classes, help_key):
        self._chrome.refs[ref] = (
            ui.button(icon=icon, on_click=on_click, color=None)
            .props("flat dense")
            .classes(classes)
            .mark(ref)
            .tooltip(tooltips.CHROME_HELP[help_key])
        )

    def _share_link(self) -> None:
        self._gestures.end_commit_gestures()
        token = _encode_state(self._editor.serialize())
        ui.run_javascript(
            "(async function(){"
            f"var u=location.origin+location.pathname+'?{_STATE_PARAM}='+{json.dumps(token)};"
            "try{await navigator.clipboard.writeText(u);}"
            "catch(e){var t=document.createElement('textarea');t.value=u;"
            "document.body.appendChild(t);t.select();"
            "document.execCommand('copy');t.remove();}})()"
        )
        ui.notify("Shareable link copied to clipboard")

    def _arm_history_previews(self) -> None:
        def arm(btn, can, op):
            btn.on(
                "mouseenter",
                lambda _=None: self._gestures.control_hover(op) if can() else None,
            )
            btn.on("mouseleave", lambda _=None: self._gestures.control_unhover())

        arm(self._chrome.refs["undo"], lambda: self._editor.can_undo, self._editor.undo)
        arm(self._chrome.refs["redo"], lambda: self._editor.can_redo, self._editor.redo)
        arm(self._chrome.refs["reset"], lambda: self._editor.can_reset, self._editor.reset)

    def _build_title_buttons(self) -> None:
        with ui.element("div").classes("rtt-titletile").mark("titletile"):
            with ui.element("div").classes("rtt-tile-btns"):
                self._icon_button(
                    "undo",
                    "undo",
                    lambda: self._edits.act(self._editor.undo),
                    "rtt-iconbtn rtt-hk-undo",
                    "undo",
                )
                self._icon_button(
                    "redo",
                    "redo",
                    lambda: self._edits.act(self._editor.redo),
                    "rtt-iconbtn rtt-hk-redo",
                    "redo",
                )
                self._icon_button(
                    "reset", "restart_alt", self._handlers.reset, "rtt-iconbtn", "reset"
                )
                self._icon_button(
                    "share", "share", self._share_link, "rtt-iconbtn rtt-noarm", "share"
                )
                self._icon_button(
                    "tour",
                    "help_outline",
                    lambda: ui.run_javascript("window.rttTour && window.rttTour.start()"),
                    "rtt-iconbtn rtt-noarm",
                    "tour",
                )
                self._arm_history_previews()

    def _build_approach_radio(self) -> None:
        approach_options = {
            "prime-based": "prime-based",
            "nonprime-based": "nonprime-based",
            "": "neutral",
        }

        def on_approach_change(value):
            if self._runtime.building or value is None:
                return
            self._editor.set_nonprime_basis_approach(value)
            self._renderer.request_render()

        def on_approach_hover(value):
            if value is None:
                self._gestures.control_unhover()
                return
            self._gestures.control_hover(
                lambda a=value: self._editor.set_nonprime_basis_approach(a)
            )

        self._chrome.refs["approach"] = (
            ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
        )
        self._chrome.refs["approach_opts"] = {}
        with self._chrome.refs["approach"]:
            for key, label in approach_options.items():
                opt = ui.element("div").classes("rtt-rangeopt")
                with opt:
                    ui.element("span").classes("rtt-rangebox")
                    ui.label(label).classes("rtt-rangelabel")
                opt.on("click", lambda _=None, k=key: on_approach_change(k))
                opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
                opt.mark(f"approach-{label}")
                self._chrome.refs["approach_opts"][key] = opt
        self._chrome.refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))

    def _build_show_frozen(self) -> None:
        self._chrome.show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
        with self._chrome.show_frozen:
            with ui.element("div").classes("rtt-show-all"):
                self._chrome.select_all_box = (
                    ui.checkbox(
                        "select all / none",
                        value=all(self._editor.settings[k] for k in show_settings.IMPLEMENTED),
                        on_change=lambda e: self._edits.on_select_all(e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark("showall")
                    .tooltip(tooltips.CHROME_HELP["select_all"])
                )
                self._chrome.dark_btn = (
                    ui.button(on_click=self._handlers.dark_toggle, color=None)
                    .props(f"flat dense round icon={self._runtime.dark_icon()}")
                    .classes("rtt-darktoggle")
                    .mark("darkmode")
                    .tooltip(tooltips.CHROME_HELP["dark_mode"])
                )

    def _build_chapter_group(self) -> None:
        with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
            with ui.element("div").classes("rtt-chapter-head"):
                ui.label("guide chapter").classes("rtt-chapter-title")
                self._chrome.chapter_reading = (
                    ui.label(self._runtime.chapter_reading())
                    .classes("rtt-chapter-reading")
                    .mark("chapterreading")
                )
            self._chrome.chapter_slider = (
                ui.slider(
                    min=show_settings.CHAPTER_MIN,
                    max=show_settings.CHAPTER_STAR,
                    step=1,
                    value=self._runtime.chapter,
                    on_change=lambda e: self._handlers.chapter_change(e.value),
                )
                .props("markers snap dense color=grey-8")
                .classes("rtt-chapter-slider")
                .mark("chapterslider")
                .tooltip(tooltips.CHROME_HELP["chapter"])
            )

    def _tile_part(self, key, html, *, marked=False, size=None, style=""):
        fs = size if size is not None else _TILE_FONT.get(key)
        css = (f"font-size:{fs}px;" if fs else "") + style
        el = ui.html(html).classes("rtt-tile-part").tooltip(tooltips.SHOW_HELP[key])
        if key == "mnemonics":
            el.classes(add="rtt-tile-mnem")
        if marked:
            el.mark(f"showpart:{key}")
        if css:
            el.style(css)
        el.on("click", lambda k=key: self._edits.on_part_click(k))
        self._chrome.tile_parts.setdefault(key, []).append(el)
        return el

    def _tile_named_part(self, key, *, size=None, style=""):
        return self._tile_part(key, _general_part_html(key), marked=True, size=size, style=style)

    def _build_general_tile(self) -> None:
        ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
        with ui.element("div").classes("rtt-show-tile"):
            with ui.element("div").classes("rtt-tile-head"):
                ui.html(_tile_fold_html()).classes("rtt-tile-fold")
                self._chrome.refs["audio_bank"] = _audio_bank()
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
                        ui.element("div").classes("rtt-tile-cbox"),
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
                size=_TILE_FONT["rowlabel"],
                style=f"position:absolute;left:{hgut}px;top:{row_y}px;width:{gut - 3}px;"
                "height:13px;justify-content:flex-end",
            )
            self._tile_named_part(
                "gridded_values",
                style=f"position:absolute;left:{hgut + gut}px;top:0",
            )
            self._tile_value_stack(cell_x, cell_y)

    def _tile_value_stack(self, cell_x, cell_y) -> None:
        self._tile_named_part(
            "math_expressions",
            size=_fit_font(_TILE_MATH, _TILE_CELL),
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
            f"width:{_TILE_CELL}px;height:9px;justify-content:center",
        )
        self._tile_named_part(
            "quantities",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
            f"width:{_TILE_CELL}px;height:11px;justify-content:center",
        )
        self._tile_named_part(
            "decimals",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center",
        )
        self._tile_part(
            "cell_units",
            _general_part_html("cell_units"),
            marked=True,
            size=_TILE_FONT["cellunit"],
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 28}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:#555",
        )

    def _build_show_group(self, items) -> None:
        with ui.element("div").classes("rtt-show-head"):
            ui.label("show").classes("rtt-show-title")
            ui.label("example").classes("rtt-show-examplehdr")
        for key, label, _ in items:
            row = ui.element("div").classes("rtt-show-row").mark(f"showrow:{key}")
            with row:
                box = (
                    ui.checkbox(
                        label,
                        value=self._editor.settings[key],
                        on_change=lambda e, k=key: self._edits.on_show_toggle(k, e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark(f"showbox:{key}")
                    .tooltip(tooltips.SHOW_HELP[key])
                )
                example = (
                    ui.html(_example_html(key)).classes("rtt-ex-cell").mark(f"showexample:{key}")
                )
            self._chrome.boxes[key] = box
            self._chrome.examples[key] = example
            self._chrome.show_rows[key] = row
            parent = show_settings.SUBCONTROLS.get(key)
            if parent:
                box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                row.bind_visibility_from(self._chrome.boxes[parent], "value")

    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        self._chrome.panelgroup.classes(
            add="rtt-open"
        ) if self.drawer_open else self._chrome.panelgroup.classes(remove="rtt-open")

    def _pane_chrome(self):
        ui.button(icon="menu", on_click=self.toggle_drawer, color=None).props("flat dense").classes(
            "rtt-hamburger"
        ).tooltip(tooltips.CHROME_HELP["settings"])
        ui.label("D&D's RTT app").classes("rtt-sidetitle")
