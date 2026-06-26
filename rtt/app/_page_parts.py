from __future__ import annotations

import json

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
    _GUIDE_JS,
    _STATE_PARAM,
    _TABNAV_JS,
    _TOOLTIP_DELAY_MS,
    _TOUR_JS,
    _TOUR_STEPS,
    _ZOOM_JS,
    _encode_state,
)
from rtt.app.render_html import (
    _example_html,
)


def setup_page_head() -> None:
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


def build_layout(pb) -> None:
    with ui.element("div").classes("rtt-shell"):
        pb._chrome.panelgroup = ui.element("div").classes("rtt-panelgroup")
        with pb._chrome.panelgroup:
            with ui.element("div").classes("rtt-chrome"):
                pane_chrome(pb)
            build_drawer(pb)
        build_grid_pane(pb)


def build_grid_pane(pb) -> None:
    pb._chrome.grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
    with pb._chrome.grid_pane:
        pb._chrome.colfill = ui.element("div").classes("rtt-colfill").mark("colfill")
        with pb._chrome.colfill:
            pb._chrome.colfill_inner = (
                ui.element("div").classes("rtt-colfill-inner").mark("colfillinner")
            )
        pb._chrome.colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
        with pb._chrome.colhead:
            pb._chrome.colhead_inner = (
                ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
            )
        build_corner(pb)
        build_gridbody(pb)


def build_drawer(pb) -> None:
    drawer = ui.element("div").classes("rtt-drawer")
    with drawer, ui.element("div").classes("rtt-drawer-inner"):
        build_show_frozen(pb)
        pb._chrome.show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
        with pb._chrome.show_scroll:
            build_chapter_group(pb)
            for group_name, items in show_settings.SHOW_GROUPS:
                with ui.element("div").classes("rtt-show-group"):
                    if group_name == "general":
                        pb._build_general_tile()
                    else:
                        build_show_group(pb, items)


def build_corner(pb) -> None:
    pb._chrome.corner = ui.element("div").classes("rtt-corner").mark("corner")
    with pb._chrome.corner:
        build_title_buttons(pb)
        build_approach_radio(pb)


def build_gridbody(pb) -> None:
    pb._chrome.gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
    with pb._chrome.gridbody:
        pb._chrome.board = ui.element("div").classes("rtt-gridcontent").mark("board")
        with pb._chrome.board, ui.element("div").classes("rtt-band"):
            pb._chrome.rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
    pb._chrome.refs["approach"].move(pb._chrome.board)
    pb._chrome.cell_parents = {
        "corner": pb._chrome.corner,
        "col": pb._chrome.colhead_inner,
        "row": pb._chrome.rowband,
        "body": pb._chrome.board,
    }


def share_link(pb) -> None:
    pb._gestures.end_commit_gestures()
    token = _encode_state(pb._editor.serialize())
    ui.run_javascript(
        "(async function(){"
        f"var u=location.origin+location.pathname+'?{_STATE_PARAM}='+{json.dumps(token)};"
        "try{await navigator.clipboard.writeText(u);}"
        "catch(e){var t=document.createElement('textarea');t.value=u;"
        "document.body.appendChild(t);t.select();"
        "document.execCommand('copy');t.remove();}})()"
    )
    ui.notify("Shareable link copied to clipboard")


def arm_history_previews(pb) -> None:
    def arm(btn, can, op):
        btn.on(
            "mouseenter",
            lambda _=None: pb._gestures.control_hover(op) if can() else None,
        )
        btn.on("mouseleave", lambda _=None: pb._gestures.control_unhover())

    arm(pb._chrome.refs["undo"], lambda: pb._editor.can_undo, pb._editor.undo)
    arm(pb._chrome.refs["redo"], lambda: pb._editor.can_redo, pb._editor.redo)
    arm(pb._chrome.refs["reset"], lambda: pb._editor.can_reset, pb._editor.reset)


def build_title_buttons(pb) -> None:
    with ui.element("div").classes("rtt-titletile").mark("titletile"):
        with ui.element("div").classes("rtt-tile-btns"):
            pb._icon_button(
                "undo",
                "undo",
                lambda: pb._edits.act(pb._editor.undo),
                "rtt-iconbtn rtt-hk-undo",
                "undo",
            )
            pb._icon_button(
                "redo",
                "redo",
                lambda: pb._edits.act(pb._editor.redo),
                "rtt-iconbtn rtt-hk-redo",
                "redo",
            )
            pb._icon_button("reset", "restart_alt", pb._handlers.reset, "rtt-iconbtn", "reset")
            pb._icon_button(
                "share", "share", lambda: share_link(pb), "rtt-iconbtn rtt-noarm", "share"
            )
            pb._icon_button(
                "tour",
                "help_outline",
                lambda: ui.run_javascript("window.rttTour && window.rttTour.start()"),
                "rtt-iconbtn rtt-noarm",
                "tour",
            )
            arm_history_previews(pb)


def build_approach_radio(pb) -> None:
    approach_options = {
        "prime-based": "prime-based",
        "nonprime-based": "nonprime-based",
        "": "neutral",
    }

    def on_approach_change(value):
        if pb._runtime.building or value is None:
            return
        pb._editor.set_nonprime_basis_approach(value)
        pb._renderer.request_render()

    def on_approach_hover(value):
        if value is None:
            pb._gestures.control_unhover()
            return
        pb._gestures.control_hover(lambda a=value: pb._editor.set_nonprime_basis_approach(a))

    pb._chrome.refs["approach"] = (
        ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
    )
    pb._chrome.refs["approach_opts"] = {}
    with pb._chrome.refs["approach"]:
        for key, label in approach_options.items():
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")
                ui.label(label).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, k=key: on_approach_change(k))
            opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
            opt.mark(f"approach-{label}")
            pb._chrome.refs["approach_opts"][key] = opt
    pb._chrome.refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))


def build_show_frozen(pb) -> None:
    pb._chrome.show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
    with pb._chrome.show_frozen:
        with ui.element("div").classes("rtt-show-all"):
            pb._chrome.select_all_box = (
                ui.checkbox(
                    "select all / none",
                    value=all(pb._editor.settings[k] for k in show_settings.IMPLEMENTED),
                    on_change=lambda e: pb._edits.on_select_all(e.value),
                )
                .props("dense size=xs color=grey-8")
                .classes("rtt-show-item")
                .mark("showall")
                .tooltip(tooltips.CHROME_HELP["select_all"])
            )
            pb._chrome.dark_btn = (
                ui.button(on_click=pb._handlers.dark_toggle, color=None)
                .props(f"flat dense round icon={pb._runtime.dark_icon()}")
                .classes("rtt-darktoggle")
                .mark("darkmode")
                .tooltip(tooltips.CHROME_HELP["dark_mode"])
            )


def build_chapter_group(pb) -> None:
    with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
        with ui.element("div").classes("rtt-chapter-head"):
            ui.label("guide chapter").classes("rtt-chapter-title")
            pb._chrome.chapter_reading = (
                ui.label(pb._runtime.chapter_reading())
                .classes("rtt-chapter-reading")
                .mark("chapterreading")
            )
        pb._chrome.chapter_slider = (
            ui.slider(
                min=show_settings.CHAPTER_MIN,
                max=show_settings.CHAPTER_STAR,
                step=1,
                value=pb._runtime.chapter,
                on_change=lambda e: pb._handlers.chapter_change(e.value),
            )
            .props("markers snap dense color=grey-8")
            .classes("rtt-chapter-slider")
            .mark("chapterslider")
            .tooltip(tooltips.CHROME_HELP["chapter"])
        )


def build_show_group(pb, items) -> None:
    with ui.element("div").classes("rtt-show-head"):
        ui.label("show").classes("rtt-show-title")
        ui.label("example").classes("rtt-show-examplehdr")
    for key, label, _ in items:
        row = ui.element("div").classes("rtt-show-row").mark(f"showrow:{key}")
        with row:
            box = (
                ui.checkbox(
                    label,
                    value=pb._editor.settings[key],
                    on_change=lambda e, k=key: pb._edits.on_show_toggle(k, e.value),
                )
                .props("dense size=xs color=grey-8")
                .classes("rtt-show-item")
                .mark(f"showbox:{key}")
                .tooltip(tooltips.SHOW_HELP[key])
            )
            example = ui.html(_example_html(key)).classes("rtt-ex-cell").mark(f"showexample:{key}")
        pb._chrome.boxes[key] = box
        pb._chrome.examples[key] = example
        pb._chrome.show_rows[key] = row
        parent = show_settings.SUBCONTROLS.get(key)
        if parent:
            box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
            row.bind_visibility_from(pb._chrome.boxes[parent], "value")


def pane_chrome(pb) -> None:
    ui.button(icon="menu", on_click=pb.toggle_drawer, color=None).props("flat dense").classes(
        "rtt-hamburger"
    ).tooltip(tooltips.CHROME_HELP["settings"])
    ui.label("D&D's RTT app").classes("rtt-sidetitle")
