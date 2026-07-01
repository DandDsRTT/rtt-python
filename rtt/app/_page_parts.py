from __future__ import annotations

import json

from nicegui import ui

from rtt.app import settings as show_settings
from rtt.app import (
    tooltips,
)
from rtt.app.page_assets import (
    _ACTIVECELL_JS,
    _AUDIO_GLYPHS,
    _AUDIO_JS,
    _CSS,
    _DECIMAL_JS,
    _FRACTION_JS,
    _FREEZE_JS,
    _GUIDE_JS,
    _MAPPING_DEMO_JS,
    _STATE_PARAM,
    _TOOLTIP_DELAY_MS,
    _TOUR_JS,
    _TOUR_STEPS,
    _ZOOM_JS,
    _audio_bank,
    _encode_state,
)
from rtt.app.render_html import (
    _example_html,
)


def setup_page_head() -> None:
    ui.add_css(_CSS)
    ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS} transition-duration=0")
    ui.add_body_html(
        f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>"
    )
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
    ui.add_body_html(f"<script>{_FRACTION_JS}</script>")
    ui.add_body_html(f"<script>{_DECIMAL_JS}</script>")
    ui.add_body_html(f"<script>{_ACTIVECELL_JS}</script>")
    ui.add_body_html(f"<script>{_ZOOM_JS}</script>")
    ui.add_body_html(f"<script>{_GUIDE_JS}</script>")
    ui.add_body_html(f"<script>{_MAPPING_DEMO_JS}</script>")
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


def build_layout(page_builder) -> None:
    slots: dict = {}
    with ui.element("div").classes("rtt-shell"):
        panelgroup = ui.element("div").classes("rtt-panelgroup")
        slots["panelgroup"] = panelgroup
        with panelgroup:
            with ui.element("div").classes("rtt-chrome"):
                pane_chrome(page_builder)
            slots.update(build_drawer(page_builder))
        slots.update(build_grid_pane(page_builder))
    slots["cell_parents"] = {
        "corner": slots["corner"],
        "col": slots["columnhead_inner"],
        "row": slots["rowband"],
        "body": slots["board"],
    }
    page_builder._chrome.populate(slots)
    page_builder._chrome.refs["approach"].move(slots["board"])


def build_grid_pane(page_builder) -> dict:
    grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
    slots: dict = {"grid_pane": grid_pane}
    with grid_pane:
        columnfill = ui.element("div").classes("rtt-column-fill").mark("columnfill")
        slots["columnfill"] = columnfill
        with columnfill:
            slots["columnfill_inner"] = (
                ui.element("div").classes("rtt-column-fill-inner").mark("columnfillinner")
            )
        slots["rowfill"] = ui.element("div").classes("rtt-rowfill").mark("rowfill")
        columnhead = ui.element("div").classes("rtt-column-head").mark("columnhead")
        slots["columnhead"] = columnhead
        with columnhead:
            slots["columnhead_inner"] = (
                ui.element("div").classes("rtt-column-head-inner").mark("columnheadinner")
            )
        slots.update(build_corner(page_builder))
        slots.update(build_gridbody())
    return slots


def build_drawer(page_builder) -> dict:
    slots: dict = {}
    drawer = ui.element("div").classes("rtt-drawer")
    with drawer, ui.element("div").classes("rtt-drawer-inner"):
        slots.update(build_show_frozen(page_builder))
        show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
        slots["show_scroll"] = show_scroll
        with show_scroll:
            slots.update(build_chapter_group(page_builder))
            for group_name, items in show_settings.SHOW_GROUPS:
                with ui.element("div").classes("rtt-show-group"):
                    if group_name == "general":
                        page_builder._build_general_tile()
                    else:
                        build_show_group(page_builder, group_name, items)
    return slots


def build_corner(page_builder) -> dict:
    corner = ui.element("div").classes("rtt-corner").mark("corner")
    with corner:
        build_title_buttons(page_builder)
        build_approach_radio(page_builder)
    return {"corner": corner}


def build_gridbody() -> dict:
    gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
    with gridbody:
        board = ui.element("div").classes("rtt-gridcontent").mark("board")
        with board, ui.element("div").classes("rtt-band"):
            rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
    return {"gridbody": gridbody, "board": board, "rowband": rowband}


def share_link(page_builder) -> None:
    page_builder._gestures.end_commit_gestures()
    token = _encode_state(page_builder._editor.serialize())
    ui.run_javascript(
        "(async function(){"
        f"var u=location.origin+location.pathname+'?{_STATE_PARAM}='+{json.dumps(token)};"
        "try{await navigator.clipboard.writeText(u);}"
        "catch(e){var t=document.createElement('textarea');t.value=u;"
        "document.body.appendChild(t);t.select();"
        "document.execCommand('copy');t.remove();}})()"
    )
    ui.notify("Shareable link copied to clipboard")


def arm_history_previews(page_builder) -> None:
    def arm(button, can, op):
        button.on(
            "mouseenter",
            lambda _=None: page_builder._gestures.control_hover(op) if can() else None,
        )
        button.on("mouseleave", lambda _=None: page_builder._gestures.control_unhover())

    arm(
        page_builder._chrome.refs["undo"],
        lambda: page_builder._editor.can_undo,
        page_builder._editor.undo,
    )
    arm(
        page_builder._chrome.refs["redo"],
        lambda: page_builder._editor.can_redo,
        page_builder._editor.redo,
    )
    arm(
        page_builder._chrome.refs["reset"],
        lambda: page_builder._editor.can_reset,
        page_builder._editor.reset,
    )


def build_title_buttons(page_builder) -> None:
    with ui.element("div").classes("rtt-titletile").mark("titletile"):
        with ui.element("div").classes("rtt-tile-buttons"):
            page_builder._icon_button(
                "undo",
                "undo",
                lambda: page_builder._edits.act(page_builder._editor.undo),
                "rtt-icon-button rtt-hk-undo",
                "undo",
            )
            page_builder._icon_button(
                "redo",
                "redo",
                lambda: page_builder._edits.act(page_builder._editor.redo),
                "rtt-icon-button rtt-hk-redo",
                "redo",
            )
            page_builder._icon_button(
                "reset", "restart_alt", page_builder._handlers.reset, "rtt-icon-button", "reset"
            )
            page_builder._icon_button(
                "share",
                "share",
                lambda: share_link(page_builder),
                "rtt-icon-button rtt-noarm",
                "share",
            )
            page_builder._icon_button(
                "tour",
                "help_outline",
                lambda: ui.run_javascript("window.rttTour && window.rttTour.start()"),
                "rtt-icon-button rtt-noarm",
                "tour",
            )
            arm_history_previews(page_builder)


def build_approach_radio(page_builder) -> None:
    approach_options = {
        "prime-based": "prime-based",
        "nonprime-based": "nonprime-based",
        "": "neutral",
    }

    def on_approach_change(value):
        if page_builder._runtime.building or value is None:
            return
        page_builder._editor.set_nonprime_basis_approach(value)
        page_builder._renderer.request_render()

    def on_approach_hover(value):
        if value is None:
            page_builder._gestures.control_unhover()
            return
        page_builder._gestures.control_hover(
            lambda a=value: page_builder._editor.set_nonprime_basis_approach(a)
        )

    radio, opts = build_rangemode_radio(
        page_builder, "approach", approach_options, on_approach_change
    )
    radio.classes(add="rtt-approach")
    for key, opt in opts.items():
        opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
    radio.on("mouseleave", lambda _=None: on_approach_hover(None))


_VIS_KIND = {"animations": "anim", "preview_highlighting": "prev", "tooltips": "tip"}
_VISUAL_ICON = {
    "animations": (
        '<svg class="rtt-anim-icon" viewBox="0 0 14 14">'
        '<rect x="1" y="1" width="3" height="3"/><rect x="5" y="1" width="3" height="3"/>'
        '<rect x="1" y="5" width="3" height="3"/><rect x="5" y="5" width="3" height="3"/>'
        '<rect class="g" x="9" y="1" width="3" height="3"/><rect class="g" x="9" y="5" width="3" height="3"/>'
        '<rect class="g" x="1" y="9" width="3" height="3"/><rect class="g" x="5" y="9" width="3" height="3"/>'
        '<rect class="g" x="9" y="9" width="3" height="3"/></svg>'
    ),
    "preview_highlighting": (
        '<span class="rtt-preview-icon"><span class="rtt-preview-n n1">1</span>'
        '<span class="rtt-preview-n n2">2</span><span class="rtt-preview-n n3">3</span></span>'
    ),
    "tooltips": '<span class="material-icons rtt-vis-mi">chat_bubble</span>',
}


def _setting(page_builder, key):
    return page_builder._editor.settings[key]


def _visual_toggle(page_builder, key):
    on = _setting(page_builder, key)
    cls = f"rtt-vis-control rtt-vis-{_VIS_KIND[key]}" + ("" if on else " rtt-vis-off")
    element = (
        ui.html(_VISUAL_ICON[key])
        .classes(cls)
        .mark(f"visibility_control:{key}")
        .tooltip(tooltips.SHOW_HELP[key])
    )
    element.on(
        "click",
        lambda _=None, k=key: page_builder._edits.on_show_toggle(k, not _setting(page_builder, k)),
    )
    page_builder._chrome.vis_toggles[key] = element
    return element


def _box_label(*lines):
    with ui.element("div").classes("rtt-box-label"):
        for line in lines:
            ui.label(line)


def build_show_frozen(page_builder) -> dict:
    show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
    with show_frozen, ui.element("div").classes("rtt-frozen-banks"):
        with ui.element("div").classes("rtt-settings-box rtt-visual-box").mark("visualbox"):
            _box_label("visual", "settings")
            with ui.element("div").classes("rtt-box-grid rtt-visual-grid"):
                dark_button = (
                    ui.button(on_click=page_builder._handlers.dark_toggle, color=None)
                    .props(f"flat dense round icon={page_builder._runtime.dark_icon()}")
                    .classes("rtt-darktoggle")
                    .mark("darkmode")
                    .tooltip(tooltips.CHROME_HELP["dark_mode"])
                )
                _visual_toggle(page_builder, "animations")
                _visual_toggle(page_builder, "preview_highlighting")
                _visual_toggle(page_builder, "tooltips")
        with ui.element("div").classes("rtt-settings-box rtt-audio-box").mark("audiobox"):
            _box_label("audio", "settings")
            with ui.element("div").classes("rtt-box-grid rtt-audio-grid"):
                _audio_bank()
    return {"show_frozen": show_frozen, "dark_button": dark_button}


def build_chapter_group(page_builder) -> dict:
    with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
        ui.label("guide settings").classes("rtt-chapter-box-title").mark("guidesettingstitle")
        with ui.element("div").classes("rtt-chapter-head"):
            ui.label("max chapter").classes("rtt-chapter-title")
            chapter_reading = (
                ui.label(page_builder._runtime.chapter_reading())
                .classes("rtt-chapter-reading")
                .mark("chapterreading")
            )
        chapter_slider = (
            ui.slider(
                min=show_settings.CHAPTER_MIN,
                max=show_settings.CHAPTER_STAR,
                step=1,
                value=page_builder._runtime.chapter,
                on_change=lambda e: page_builder._handlers.chapter_change(e.value),
            )
            .props("markers snap dense color=grey-8")
            .classes("rtt-chapter-slider")
            .mark("chapterslider")
            .tooltip(tooltips.CHROME_HELP["chapter"])
        )
        terminology_radio = build_terminology_radio(page_builder)
    return {
        "chapter_reading": chapter_reading,
        "chapter_slider": chapter_slider,
        "terminology_radio": terminology_radio,
    }


def build_rangemode_radio(page_builder, ref, options, on_select):
    radio = ui.element("div").classes("rtt-range-mode").mark(ref)
    opts = {}
    with radio:
        for key, label in options.items():
            opt = ui.element("div").classes("rtt-range-option")
            with opt:
                ui.element("span").classes("rtt-rangebox")
                ui.label(label).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, k=key: on_select(k))
            opt.mark(f"{ref}-{key or label}")
            opts[key] = opt
    page_builder._chrome.refs[ref] = radio
    page_builder._chrome.refs[f"{ref}_opts"] = opts
    return radio, opts


def build_terminology_radio(page_builder):
    with ui.element("div").classes("rtt-terminology-box").mark("terminologybox"):
        ui.label("terminology").classes("rtt-terminology-title")
        radio, _opts = build_rangemode_radio(
            page_builder,
            "terminologyradio",
            {"dd": "D&D", "wiki": "wiki", "both": "both"},
            lambda value: page_builder._edits.on_show_toggle("terminology", value),
        )
        radio.tooltip(tooltips.CHROME_HELP["terminology"])
    return radio


def _settings_checkbox(page_builder, key, label):
    return ui.checkbox(
        label,
        value=_setting(page_builder, key),
        on_change=lambda e, k=key: page_builder._edits.on_show_toggle(k, e.value),
    ).props("dense size=xs color=grey-8")


def _select_all_box(page_builder, group_name):
    keys = show_settings.group_keys(group_name)
    box = (
        ui.checkbox(
            "select all / none",
            value=all(_setting(page_builder, k) for k in keys if k in show_settings.IMPLEMENTED),
            on_change=lambda e, ks=keys: page_builder._edits.on_select_all(e.value, ks),
        )
        .props("dense size=xs color=grey-8")
        .classes("rtt-show-item rtt-section-all")
        .mark(f"sectionall:{group_name}")
        .tooltip(tooltips.CHROME_HELP["select_all"])
    )
    page_builder._chrome.section_all[group_name] = box
    return box


def build_show_group(page_builder, group_name, items) -> None:
    ui.label(group_name).classes("rtt-app-features-title").mark("appfeaturestitle")
    _select_all_box(page_builder, group_name)
    with ui.element("div").classes("rtt-show-head"):
        ui.label("show").classes("rtt-show-title")
        ui.label("example").classes("rtt-show-example-header")
    for key, label, _ in items:
        row = ui.element("div").classes("rtt-show-row").mark(f"showrow:{key}")
        with row:
            box = (
                _settings_checkbox(page_builder, key, label)
                .classes("rtt-show-item")
                .mark(f"showbox:{key}")
                .tooltip(tooltips.SHOW_HELP[key])
            )
            example = (
                ui.html(_example_html(key)).classes("rtt-example-cell").mark(f"showexample:{key}")
            )
        page_builder._chrome.boxes[key] = box
        page_builder._chrome.examples[key] = example
        page_builder._chrome.show_rows[key] = row
        parent = show_settings.SUBCONTROLS.get(key)
        if parent:
            box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
            row.bind_visibility_from(page_builder._chrome.boxes[parent], "value")


def pane_chrome(page_builder) -> None:
    ui.button(icon="menu", on_click=page_builder.toggle_drawer, color=None).props(
        "flat dense"
    ).classes("rtt-hamburger").tooltip(tooltips.CHROME_HELP["settings"])
    ui.label("D&D's RTT app").classes("rtt-sidetitle")
