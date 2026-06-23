from __future__ import annotations

import json
import logging
from html import escape as _escape

from nicegui import ui

from rtt.app import (
    tooltips,
)
from rtt.app import settings as show_settings
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


from rtt.app.page_assets import (
    _TOOLTIP_DELAY_MS,
    _STATE_PARAM,
    _encode_state,
    _AUDIO_GLYPHS,
    _AUDIO_JS,
    _FREEZE_JS,
    _FRACTION_JS,
    _DECIMAL_JS,
    _TABNAV_JS,
    _TOUR_JS,
    _TOUR_STEPS,
    _CSS,
    _GENERAL_TILE_LINES,
    _TILE_FONT,
    _audio_bank,
    _ZOOM_JS,
    _GUIDE_JS,
)

_log = logging.getLogger(__name__)


class PageBuilder:
    def __init__(self, page) -> None:
        self.page = page
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
        # trim NiceGUI's default 16px content padding to a slim margin around the whole app
        ui.query(".nicegui-content").style("padding:6px")

        # the busy scrim (fixed, viewport-covering, hidden until revealed): shown while a heavy
        # state change re-solves the tuning off the event loop, so the user sees "Computing…"
        # rather than a frozen grid, and the clicks they'd otherwise pile up are swallowed. Built
        # once, here, so it outlives every grid rebuild (see _request_render / _commit_render).
        with ui.element("div").classes("rtt-busy"):
            with ui.element("div").classes("rtt-busy-card"):
                ui.element("div").classes("rtt-busy-spin")
                ui.label("Computing…")

    def _build_layout(self) -> None:
        with ui.element("div").classes("rtt-shell"):
            self.page.panelgroup = ui.element("div").classes("rtt-panelgroup")
            with self.page.panelgroup:
                with ui.element("div").classes("rtt-chrome"):
                    self._pane_chrome()
                self._build_drawer()
            self._build_grid_pane()

    def _build_grid_pane(self) -> None:
        self.page.grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with self.page.grid_pane:
            self.page.colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with self.page.colhead:
                self.page.colhead_inner = (
                    ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
                )
            self._build_corner()
            self._build_gridbody()

    def _build_drawer(self) -> None:
        drawer = ui.element("div").classes("rtt-drawer")
        with drawer, ui.element("div").classes("rtt-drawer-inner"):
            self._build_show_frozen()
            self.page.boxes: dict = {}
            self.page.examples: dict = {}
            self.page.tile_parts: dict = {}
            self.page.show_rows: dict = {}
            self.page.show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
            with self.page.show_scroll:
                self._build_chapter_group()
                for group_name, items in show_settings.SHOW_GROUPS:
                    with ui.element("div").classes("rtt-show-group"):
                        if group_name == "general":
                            self._build_general_tile()
                        else:
                            self._build_show_group(items)

    def _build_corner(self) -> None:
        self.page.corner = ui.element("div").classes("rtt-corner").mark("corner")
        with self.page.corner:
            self._build_title_buttons()
            self._build_approach_radio()

    def _build_gridbody(self) -> None:
        self.page.gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
        with self.page.gridbody:
            self.page.board = ui.element("div").classes("rtt-gridcontent").mark("board")
            with self.page.board, ui.element("div").classes("rtt-band"):
                self.page.rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
        self.page.refs["approach"].move(self.page.board)
        self.page.cell_parents = {
            "corner": self.page.corner,
            "col": self.page.colhead_inner,
            "row": self.page.rowband,
            "body": self.page.board,
        }

    def _icon_button(self, ref, icon, on_click, classes, help_key):
        self.page.refs[ref] = (
            ui.button(icon=icon, on_click=on_click, color=None)
            .props("flat dense")
            .classes(classes)
            .mark(ref)
            .tooltip(tooltips.CHROME_HELP[help_key])
        )

    def _share_link(self) -> None:
        self.page.gestures.end_commit_gestures()
        token = _encode_state(self.page.editor.serialize())
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
            btn.on("mouseenter", lambda _=None: self.page.gestures.control_hover(op) if can() else None)
            btn.on("mouseleave", lambda _=None: self.page.gestures.control_unhover())

        arm(self.page.refs["undo"], lambda: self.page.editor.can_undo, self.page.editor.undo)
        arm(self.page.refs["redo"], lambda: self.page.editor.can_redo, self.page.editor.redo)
        arm(self.page.refs["reset"], lambda: self.page.editor.can_reset, self.page.editor.reset)

    def _build_title_buttons(self) -> None:
        with ui.element("div").classes("rtt-titletile").mark("titletile"):
            with ui.element("div").classes("rtt-tile-btns"):
                self._icon_button(
                    "undo",
                    "undo",
                    lambda: self.page.edits.act(self.page.editor.undo),
                    "rtt-iconbtn rtt-hk-undo",
                    "undo",
                )
                self._icon_button(
                    "redo",
                    "redo",
                    lambda: self.page.edits.act(self.page.editor.redo),
                    "rtt-iconbtn rtt-hk-redo",
                    "redo",
                )
                self._icon_button(
                    "reset", "restart_alt", self.page.reset_everything, "rtt-iconbtn", "reset"
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
        # the chapter-9 nonstandard-domain-approach radio: prime-based, nonprime-based, or
        # the library's neutral default (which reads a nonprime element as a formal prime).
        # Built as the standard square radio (the tuning-ranges range-mode style — a vertical
        # list of square options), NOT a Quasar inline radio. Hidden when the domain has no
        # nonprime element — the trait is meaningless there — and revealed when a basis like
        # 2.3.13/5 carries one. render() fills the live option and sets visibility each pass.
        approach_options = {
            "prime-based": "prime-based",
            "nonprime-based": "nonprime-based",
            "": "neutral",
        }

        def on_approach_change(value):
            if self.page.building or value is None:
                return
            self.page.editor.set_nonprime_basis_approach(value)
            self.page.renderer.request_render()  # the nonprime approach changes how the tuning solves — off the loop

        def on_approach_hover(value):
            # preview the hovered approach option: ring the cells reading the temperament that
            # way would move, without committing (control_hover reverts it). None = leaving the
            # radio, so clear the preview. Each option is its own hover target (mouseenter).
            if value is None:
                self.page.gestures.control_unhover()
                return
            self.page.gestures.control_hover(lambda a=value: self.page.editor.set_nonprime_basis_approach(a))

        self.page.refs["approach"] = (
            ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
        )
        self.page.refs["approach_opts"] = {}
        with self.page.refs["approach"]:
            for key, label in approach_options.items():
                opt = ui.element("div").classes("rtt-rangeopt")
                with opt:
                    ui.element("span").classes("rtt-rangebox")
                    ui.label(label).classes("rtt-rangelabel")
                opt.on("click", lambda _=None, k=key: on_approach_change(k))
                opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
                opt.mark(f"approach-{label}")
                self.page.refs["approach_opts"][key] = opt
        self.page.refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))

    def _build_show_frozen(self) -> None:
        self.page.show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
        with self.page.show_frozen:
            with ui.element("div").classes("rtt-show-all"):
                self.page.select_all_box = (
                    ui.checkbox(
                        "select all / none",
                        value=all(self.page.editor.settings[k] for k in show_settings.IMPLEMENTED),
                        on_change=lambda e: self.page.edits.on_select_all(e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark("showall")
                    .tooltip(tooltips.CHROME_HELP["select_all"])
                )
                self.page.dark_btn = (
                    ui.button(on_click=self.page.on_dark_toggle, color=None)
                    .props(f"flat dense round icon={self.page._dark_icon()}")
                    .classes("rtt-darktoggle")
                    .mark("darkmode")
                    .tooltip(tooltips.CHROME_HELP["dark_mode"])
                )

    def _build_chapter_group(self) -> None:
        with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
            with ui.element("div").classes("rtt-chapter-head"):
                ui.label("guide chapter").classes("rtt-chapter-title")
                self.page.chapter_reading = (
                    ui.label(self.page._chapter_reading(self.page.chapter))
                    .classes("rtt-chapter-reading")
                    .mark("chapterreading")
                )
            self.page.chapter_slider = (
                ui.slider(
                    min=show_settings.CHAPTER_MIN,
                    max=show_settings.CHAPTER_STAR,
                    step=1,
                    value=self.page.chapter,
                    on_change=lambda e: self.page.on_chapter_change(e.value),
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
        el.on("click", lambda k=key: self.page.edits.on_part_click(k))
        self.page.tile_parts.setdefault(key, []).append(el)
        return el

    def _tile_named_part(self, key, *, size=None, style=""):
        return self._tile_part(key, _general_part_html(key), marked=True, size=size, style=style)

    def _build_general_tile(self) -> None:
        ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
        with ui.element("div").classes("rtt-show-tile"):
            with ui.element("div").classes("rtt-tile-head"):
                ui.html(_tile_fold_html()).classes("rtt-tile-fold")
                self.page.refs["audio_bank"] = _audio_bank()
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
                        value=self.page.editor.settings[key],
                        on_change=lambda e, k=key: self.page.edits.on_show_toggle(k, e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark(f"showbox:{key}")
                    .tooltip(tooltips.SHOW_HELP[key])
                )
                example = (
                    ui.html(_example_html(key)).classes("rtt-ex-cell").mark(f"showexample:{key}")
                )
            self.page.boxes[key] = box
            self.page.examples[key] = example
            self.page.show_rows[key] = row
            parent = show_settings.SUBCONTROLS.get(key)
            if parent:
                box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                row.bind_visibility_from(self.page.boxes[parent], "value")

    def toggle_drawer(self):
        self.drawer_open = not self.drawer_open
        self.page.panelgroup.classes(add="rtt-open") if self.drawer_open else self.page.panelgroup.classes(
            remove="rtt-open"
        )

    def _pane_chrome(self):
        ui.button(icon="menu", on_click=self.toggle_drawer, color=None).props("flat dense").classes(
            "rtt-hamburger"
        ).tooltip(tooltips.CHROME_HELP["settings"])
        ui.label("D&D's RTT app").classes("rtt-sidetitle")
