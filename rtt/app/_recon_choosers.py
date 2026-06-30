from __future__ import annotations

from nicegui import ui

from rtt.app import (
    presets,
    service,
    spreadsheet,
    tooltips,
)
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
    _SUBPICK_POPUP_W,
    _formchooser_options,
    _GroupedSelect,
    _set_offlist_prompt,
)
from rtt.app.render_html import (
    _FOLD_GLYPH,
    _control_svg,
    _limit_text,
    _select_props,
)


def build_rangemode(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-rangemode")
    opts = {}
    for mode in ("monotone", "tradeoff"):
        opt = ui.element("div").classes("rtt-rangeopt")
        with opt:
            ui.element("span").classes("rtt-rangebox")
            ui.label(mode).classes("rtt-rangelabel")
        opt.on("click", lambda _=None, m=mode: reconciler._cell_box.on_range_mode(m))
        opts[mode] = opt
    reconciler.cells[cell_box.id].chooser.rangeopts = opts


def update_rangemode(reconciler, cell_box: spreadsheet.CellBox) -> None:
    for mode, opt in reconciler.cells[cell_box.id].chooser.rangeopts.items():
        (
            opt.classes(add="rtt-rangeopt-on")
            if mode == cell_box.text
            else opt.classes(remove="rtt-rangeopt-on")
        )


def build_scheme_button(reconciler, cell_box: spreadsheet.CellBox, _wrap) -> None:
    reconciler.cells[cell_box.id].chooser.scheme_button = (
        ui.button(
            cell_box.text,
            on_click=lambda: reconciler._cell_box.act(reconciler._editor.back_to_scheme),
            color=None,
        )
        .props("unelevated dense no-caps")
        .classes("rtt-scheme-button")
    )


def update_scheme_button(reconciler, cell_box: spreadsheet.CellBox) -> None:
    button = reconciler.cells[cell_box.id].chooser.scheme_button
    (
        button.classes(add="rtt-scheme-button-idle")
        if not reconciler._editor.manual_tuning
        else button.classes(remove="rtt-scheme-button-idle")
    )


def build_foldtoggle(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    item = cell_box.id.split("toggle:", 1)[1]
    reconciler.cells[cell_box.id].display.html = ui.html(
        _control_svg(_FOLD_GLYPH[cell_box.text])
    ).classes("rtt-glyph rtt-toggle")
    reconciler.cells[cell_box.id].chooser.fold_state = cell_box.text
    wrap.on("click", lambda _=None, it=item: reconciler._cell_box.on_toggle(it))


def build_alltoggle(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    reconciler.cells[cell_box.id].display.html = ui.html(
        _control_svg(_FOLD_GLYPH[cell_box.text])
    ).classes("rtt-glyph rtt-toggle")
    reconciler.cells[cell_box.id].chooser.fold_state = cell_box.text
    wrap.on("click", lambda _=None: reconciler._cell_box.on_toggle_all())


def update_foldtoggle(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if reconciler.handles(cell_box.id).chooser.fold_state != cell_box.text:
        reconciler.cells[cell_box.id].display.html.set_content(
            _control_svg(_FOLD_GLYPH[cell_box.text])
        )
        reconciler.cells[cell_box.id].chooser.fold_state = cell_box.text


def _arm_option_hover(reconciler, sel, wrap, cell_id: str) -> None:
    sel.add_slot(
        "option",
        f"""
        <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cell_id}">
            <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
        </q-item>
    """,
    )
    wrap.on(
        "opthover",
        lambda e: reconciler._cell_box.on_chooser_hover(cell_id, e.args),
        args=["detail"],
    )
    sel.on("popup-show", lambda _=None: reconciler._cell_box.on_popup(cell_id, True))
    sel.on("popup-hide", lambda _=None: reconciler._cell_box.on_popup(cell_id, False))


def build_preset(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    name = cell_box.id.split(":")[1]
    if name == "target":
        _build_preset_target(reconciler, cell_box, wrap)
    elif name == "temperament":
        _build_preset_temperament(reconciler, cell_box, wrap)
    else:
        options, value, prompt = _scheme_options(reconciler, name)
        _build_scheme_select(reconciler, cell_box, wrap, options, value, prompt)


def _build_preset_target(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    limit, family = reconciler._target_preset_values()
    with ui.element("div").classes("rtt-preset-target"):
        num = (
            ui.input(
                value=_limit_text(limit) or service.NO_LIMIT_TEXT,
                on_change=lambda _e: reconciler._cell_box.on_target_change(),
            )
            .props(
                'dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300'
            )
            .classes("rtt-preset-num")
        )
        # NiceGUI: ui.input defaults loopback off (uncontrolled during typing), so the server can't
        # overwrite what was typed; _wire_target_limit turns loopback on so a rejected value reverts.
        _wire_target_limit(reconciler, num, cell_box)
        sel = (
            ui.select(
                list(presets.TARGET_SETS),
                value=family,
                on_change=lambda _e: reconciler._cell_box.on_target_change(),
            )
            .props(_select_props(cell_box.width - 30))
            .classes("rtt-preset")
        )
    _set_offlist_prompt(sel, family)
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = (num, sel)


def _wire_target_limit(reconciler, num, cell_box: spreadsheet.CellBox) -> None:
    num.LOOPBACK = True
    num._props["loopback"] = True
    num.on(
        "wheel",
        lambda e: reconciler._cell_box.on_target_limit_wheel(e.args.get("deltaY")),
        args=["deltaY"],
        js_handler=_INT_WHEEL_JS,
    )
    num.on("focus", lambda _=None: reconciler._cell_box.on_cell_focus(cell_box.id))
    num.on("blur", lambda _=None, cell_id=cell_box.id: reconciler._cell_box.on_cell_blur(cell_id))
    # Quasar: a debounced field only commits its value on a typing pause or blur, so Enter alone
    # never submits; blurring on Enter makes Quasar flush the debounced value (firing on_change).
    num.on("keydown.enter", js_handler="(e) => e.target.blur()")
    # NiceGUI/Quasar: a Quasar QInput doesn't forward native `input` to a NiceGUI `.on()` listener,
    # and NiceGUI's `args=` filters only TOP-LEVEL event keys (it can't pull nested target.value),
    # so listen on `keyup` and emit the live DOM text ourselves to preview each keystroke.
    num.on(
        "keyup",
        lambda e: reconciler._cell_box.on_target_limit_preview(e.args),
        js_handler="(e) => emit(e.target.value)",
    )


def _build_preset_temperament(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    value = presets.identify(reconciler._editor.state)
    sel = (
        _GroupedSelect(
            presets.temperament_options(),
            value=value,
            is_divider=presets.is_divider,
            on_change=lambda e: reconciler._cell_box.on_preset(cell_box.id, e.value),
        )
        .props(_select_props(cell_box.width))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(sel, value)
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = sel


def _scheme_options(reconciler, name: str) -> tuple[list, object, str]:
    if name == "prescaler":
        options = list(presets.prescaler_options(reconciler._editor.settings["alt_complexity"]))
        value = reconciler._editor.displayed_prescaler_name
        return options, (value if value in options else None), "-"
    if name == "projection":
        options = presets.projection_options(reconciler._editor.state)
        value = reconciler._editor.displayed_projection_scheme_name
        return options, (value if value in options else None), "-"
    options = presets.tuning_scheme_options(
        service.is_all_interval(reconciler._editor.tuning_scheme),
        reconciler._editor.settings["alt_complexity"],
        reconciler._editor.settings["weighting"],
        reconciler._editor.settings["terminology"],
    )
    scheme = reconciler._editor.displayed_tuning_scheme_name
    return options, (scheme if scheme in options else None), "-"


def _build_scheme_select(reconciler, cell_box, wrap, options, value, prompt) -> None:
    sel = (
        ui.select(
            options,
            value=value,
            on_change=lambda e: reconciler._cell_box.on_preset(cell_box.id, e.value),
        )
        .props(_select_props(cell_box.width))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(sel, value, prompt)
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = sel


def _chooser_reflow_hold(reconciler, cell_id: str) -> bool:
    # Quasar: re-setting a q-select's value/options while its popup is open disrupts or closes the
    # popup, so a hovered chooser's cell update is skipped across the reflow-preview re-render.
    g = reconciler._cur_gesture
    if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
        return False

    def group(c):
        return ":".join(c.split(":")[:2])

    return group(cell_id) == group(g.source)


def update_preset(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(reconciler, cell_box.id):
        return
    if cell_box.id.startswith("preset:temperament"):
        g = reconciler._cur_gesture
        if g is not None and g.kind == "temp" and g.reflowed:
            return
        value = presets.identify(reconciler._editor.state)
        reconciler.cells[cell_box.id].chooser.select.value = value
        _set_offlist_prompt(reconciler.cells[cell_box.id].chooser.select, value)
    elif cell_box.id == "preset:target":
        num, sel = reconciler.cells[cell_box.id].chooser.select
        limit, family = reconciler._target_preset_values()
        num.value = _limit_text(limit) or service.NO_LIMIT_TEXT
        sel.value = family
        _set_offlist_prompt(sel, family)
        num.set_enabled(not cell_box.disabled)
        sel.set_enabled(not cell_box.disabled)
        _sync_target_limit_error(reconciler, num, family, limit)
    elif cell_box.id == "preset:prescaler":
        options = list(presets.prescaler_options(reconciler._editor.settings["alt_complexity"]))
        value = reconciler._editor.displayed_prescaler_name
        value = value if value in options else None
        reconciler.cells[cell_box.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(reconciler.cells[cell_box.id].chooser.select, value)
        reconciler.cells[cell_box.id].chooser.select.set_enabled(not cell_box.disabled)
    elif cell_box.id.startswith("preset:projection"):
        options = presets.projection_options(reconciler._editor.state)
        value = reconciler._editor.displayed_projection_scheme_name
        value = value if value in options else None
        reconciler.cells[cell_box.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(reconciler.cells[cell_box.id].chooser.select, value)
        reconciler.cells[cell_box.id].chooser.select.set_enabled(not cell_box.disabled)
    else:
        name = reconciler._editor.displayed_tuning_scheme_name
        options = presets.tuning_scheme_options(
            service.is_all_interval(reconciler._editor.tuning_scheme),
            reconciler._editor.settings["alt_complexity"],
            reconciler._editor.settings["weighting"],
            reconciler._editor.settings["terminology"],
        )
        scheme = name if name in options else None
        reconciler.cells[cell_box.id].chooser.select.set_options(options, value=scheme)
        _set_offlist_prompt(reconciler.cells[cell_box.id].chooser.select, scheme)
        reconciler.cells[cell_box.id].chooser.select.set_enabled(not cell_box.disabled)


def _build_subpick(reconciler, cell_box, wrap, options, value):
    sel = (
        ui.select(
            options,
            value=value if value in options else None,
            on_change=lambda e, cell_id=cell_box.id: reconciler._cell_box.on_subpick(
                cell_id, e.value
            ),
        )
        .props(_select_props(_SUBPICK_POPUP_W))
        .classes("rtt-preset rtt-subpick")
    )
    _set_offlist_prompt(sel, value if value in options else None)
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = sel


def build_etpick(reconciler, cell_box, wrap):
    state = reconciler._editor.state
    db = state.domain_basis
    value = None if cell_box.pending else presets.identify_et(state.mapping[cell_box.gen], db)
    _build_subpick(reconciler, cell_box, wrap, presets.et_options(db), value)


def build_commapick(reconciler, cell_box, wrap):
    state = reconciler._editor.state
    db = state.domain_basis
    value = (
        None if cell_box.pending else presets.identify_comma(state.comma_basis[cell_box.comma], db)
    )
    _build_subpick(reconciler, cell_box, wrap, presets.comma_options(db), value)


def update_subpick(reconciler, cell_box):
    g = reconciler._cur_gesture
    if g is not None and g.kind == "temp" and g.reflowed:
        return
    sel = reconciler.handles(cell_box.id).chooser.select
    if not isinstance(sel, ui.select):
        return
    state = reconciler._editor.state
    db = state.domain_basis
    if cell_box.id.startswith("etpick:"):
        options = presets.et_options(db)
        if cell_box.pending or cell_box.gen >= len(state.mapping):
            value = None
        else:
            value = presets.identify_et(state.mapping[cell_box.gen], db)
    else:
        options = presets.comma_options(db)
        if cell_box.pending or cell_box.comma >= len(state.comma_basis):
            value = None
        else:
            value = presets.identify_comma(state.comma_basis[cell_box.comma], db)
    value = value if value in options else None
    sel.set_options(options, value=value)
    _set_offlist_prompt(sel, value)


def _sync_target_limit_error(reconciler, num, family, limit) -> None:
    problem = service.target_limit_problem(family, limit)
    num.classes(
        add="rtt-limit-error" if problem else "", remove="" if problem else "rtt-limit-error"
    )
    if reconciler.target_limit_tip is not None:
        reconciler.target_limit_tip.set_text(
            tooltips.target_limit_help(problem)
            if problem
            else tooltips.control_help("preset", "preset:target")
        )
        reconciler.target_limit_tip.classes(
            add="rtt-tip-error" if problem else "", remove="" if problem else "rtt-tip-error"
        )


def build_control_select(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    sel = (
        ui.select(
            list(cell_box.values),
            value=cell_box.text or None,
            on_change=lambda e, cell_id=cell_box.id: reconciler._cell_box.on_control_select(
                cell_id, e.value
            ),
        )
        .props(_select_props(cell_box.width))
        .classes("rtt-preset")
    )
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = sel


def update_control_select(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(reconciler, cell_box.id):
        return
    reconciler.cells[cell_box.id].chooser.select.set_options(
        list(cell_box.values), value=cell_box.text or None
    )
    reconciler.cells[cell_box.id].chooser.select.set_enabled(not cell_box.disabled)


def build_control_check(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    reconciler.cells[cell_box.id].chooser.check = (
        ui.checkbox(
            cell_box.text,
            value=cell_box.checked,
            on_change=lambda e, cell_id=cell_box.id: reconciler._cell_box.on_control_select(
                cell_id, e.value
            ),
        )
        .props("dense")
        .classes("rtt-control-check")
    )
    apply = _control_check_preview(reconciler, cell_box)
    if apply is not None:
        preview_control(reconciler, wrap, apply)


def _control_check_preview(reconciler, cell_box: spreadsheet.CellBox):
    if cell_box.id == "control:diminuator":
        return lambda: reconciler._editor.set_diminuator_replaced(
            not service.diminuator_replaced(reconciler._editor.tuning_scheme)
        )
    if cell_box.id == "control:all_interval":
        return lambda: reconciler._editor.set_all_interval(
            not service.is_all_interval(reconciler._editor.tuning_scheme)
        )
    return None


def update_control_check(reconciler, cell_box: spreadsheet.CellBox) -> None:
    reconciler.cells[cell_box.id].chooser.check.value = cell_box.checked


def build_formchooser(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    sel = (
        ui.select(
            _formchooser_options(cell_box.id),
            value=cell_box.text or "",
            on_change=lambda e, c=cell_box.id: reconciler._cell_box.on_form_choose(c, e.value),
        )
        .props(_select_props(cell_box.width))
        .classes("rtt-preset")
    )
    _arm_option_hover(reconciler, sel, wrap, cell_box.id)
    reconciler.cells[cell_box.id].chooser.select = sel


def update_formchooser(reconciler, cell_box: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(reconciler, cell_box.id):
        return
    reconciler.cells[cell_box.id].chooser.select.set_options(
        _formchooser_options(cell_box.id), value=cell_box.text or ""
    )


def preview_control(reconciler, el, apply) -> None:
    el.on("mouseenter", lambda _=None: reconciler._cell_box.control_hover(apply))
    el.on("mouseleave", lambda _=None: reconciler._cell_box.control_unhover())


def preview_rank_remove(reconciler, el, axis: str, index: int) -> None:
    el.on("mouseenter", lambda _=None: reconciler._cell_box.rank_remove_hover(axis, index))
    el.on("mouseleave", lambda _=None: reconciler._cell_box.rank_remove_unhover())
