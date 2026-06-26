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


def build_rangemode(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-rangemode")
    opts = {}
    for mode in ("monotone", "tradeoff"):
        opt = ui.element("div").classes("rtt-rangeopt")
        with opt:
            ui.element("span").classes("rtt-rangebox")
            ui.label(mode).classes("rtt-rangelabel")
        opt.on("click", lambda _=None, m=mode: rec._cb.on_range_mode(m))
        opts[mode] = opt
    rec.cells[cb.id].chooser.rangeopts = opts


def update_rangemode(rec, cb: spreadsheet.CellBox) -> None:
    for mode, opt in rec.cells[cb.id].chooser.rangeopts.items():
        (
            opt.classes(add="rtt-rangeopt-on")
            if mode == cb.text
            else opt.classes(remove="rtt-rangeopt-on")
        )


def build_scheme_button(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    rec.cells[cb.id].chooser.scheme_button = (
        ui.button(cb.text, on_click=lambda: rec._cb.act(rec._editor.back_to_scheme), color=None)
        .props("unelevated dense no-caps")
        .classes("rtt-scheme-btn")
    )


def update_scheme_button(rec, cb: spreadsheet.CellBox) -> None:
    btn = rec.cells[cb.id].chooser.scheme_button
    (
        btn.classes(add="rtt-scheme-btn-idle")
        if not rec._editor.manual_tuning
        else btn.classes(remove="rtt-scheme-btn-idle")
    )


def build_foldtoggle(rec, cb: spreadsheet.CellBox, wrap) -> None:
    item = cb.id.split("toggle:", 1)[1]
    rec.cells[cb.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
        "rtt-glyph rtt-toggle"
    )
    rec.cells[cb.id].chooser.fold_state = cb.text
    wrap.on("click", lambda _=None, it=item: rec._cb.on_toggle(it))


def build_alltoggle(rec, cb: spreadsheet.CellBox, wrap) -> None:
    rec.cells[cb.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
        "rtt-glyph rtt-toggle"
    )
    rec.cells[cb.id].chooser.fold_state = cb.text
    wrap.on("click", lambda _=None: rec._cb.on_toggle_all())


def update_foldtoggle(rec, cb: spreadsheet.CellBox) -> None:
    if rec.handles(cb.id).chooser.fold_state != cb.text:
        rec.cells[cb.id].display.html.set_content(_control_svg(_FOLD_GLYPH[cb.text]))
        rec.cells[cb.id].chooser.fold_state = cb.text


def _arm_option_hover(rec, sel, wrap, cid: str) -> None:
    sel.add_slot(
        "option",
        f"""
        <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cid}">
            <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
        </q-item>
    """,
    )
    wrap.on("opthover", lambda e: rec._cb.on_chooser_hover(cid, e.args), args=["detail"])
    sel.on("popup-show", lambda _=None: rec._cb.on_popup(cid, True))
    sel.on("popup-hide", lambda _=None: rec._cb.on_popup(cid, False))


def build_preset(rec, cb: spreadsheet.CellBox, wrap) -> None:
    name = cb.id.split(":")[1]
    if name == "target":
        _build_preset_target(rec, cb, wrap)
    elif name == "temperament":
        _build_preset_temperament(rec, cb, wrap)
    else:
        options, value, prompt = _scheme_options(rec, name)
        _build_scheme_select(rec, cb, wrap, options, value, prompt)


def _build_preset_target(rec, cb: spreadsheet.CellBox, wrap) -> None:
    limit, family = rec._target_preset_values()
    with ui.element("div").classes("rtt-preset-target"):
        num = (
            ui.input(value=_limit_text(limit), on_change=lambda _e: rec._cb.on_target_change())
            .props(
                'dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300'
            )
            .classes("rtt-preset-num")
        )
        # NiceGUI: ui.input defaults loopback off (uncontrolled during typing), so the server can't
        # overwrite what was typed; _wire_target_limit turns loopback on so a rejected value reverts.
        _wire_target_limit(rec, num, cb)
        sel = (
            ui.select(
                list(presets.TARGET_SETS),
                value=family,
                on_change=lambda _e: rec._cb.on_target_change(),
            )
            .props(_select_props(cb.w - 30))
            .classes("rtt-preset")
        )
    _set_offlist_prompt(sel, family)
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = (num, sel)


def _wire_target_limit(rec, num, cb: spreadsheet.CellBox) -> None:
    num.LOOPBACK = True
    num._props["loopback"] = True
    num.on(
        "wheel",
        lambda e: rec._cb.on_target_limit_wheel(e.args.get("deltaY")),
        args=["deltaY"],
        js_handler=_INT_WHEEL_JS,
    )
    num.on("focus", lambda _=None: rec._cb.on_cell_focus(cb.id))
    num.on("blur", lambda _=None, cid=cb.id: rec._cb.on_cell_blur(cid))
    # Quasar: a debounced field only commits its value on a typing pause or blur, so Enter alone
    # never submits; blurring on Enter makes Quasar flush the debounced value (firing on_change).
    num.on("keydown.enter", js_handler="(e) => e.target.blur()")
    # NiceGUI/Quasar: a Quasar QInput doesn't forward native `input` to a NiceGUI `.on()` listener,
    # and NiceGUI's `args=` filters only TOP-LEVEL event keys (it can't pull nested target.value),
    # so listen on `keyup` and emit the live DOM text ourselves to preview each keystroke.
    num.on(
        "keyup",
        lambda e: rec._cb.on_target_limit_preview(e.args),
        js_handler="(e) => emit(e.target.value)",
    )


def _build_preset_temperament(rec, cb: spreadsheet.CellBox, wrap) -> None:
    value = presets.identify(rec._editor.state)
    sel = (
        _GroupedSelect(
            presets.temperament_options(),
            value=value,
            is_divider=presets.is_divider,
            on_change=lambda e: rec._cb.on_preset(cb.id, e.value),
        )
        .props(_select_props(cb.w))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(sel, value)
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = sel


def _scheme_options(rec, name: str) -> tuple[list, object, str]:
    if name == "prescaler":
        options = list(presets.prescaler_options(rec._editor.settings["alt_complexity"]))
        value = rec._editor.displayed_prescaler_name
        return options, (value if value in options else None), "-"
    if name == "projection":
        options = presets.projection_options(rec._editor.state)
        value = rec._editor.displayed_projection_scheme_name
        return options, (value if value in options else None), "-"
    options = presets.tuning_scheme_options(
        service.is_all_interval(rec._editor.tuning_scheme),
        rec._editor.settings["alt_complexity"],
        rec._editor.settings["weighting"],
    )
    scheme = rec._editor.displayed_tuning_scheme_name
    return options, (scheme if scheme in options else None), "-"


def _build_scheme_select(rec, cb, wrap, options, value, prompt) -> None:
    sel = (
        ui.select(options, value=value, on_change=lambda e: rec._cb.on_preset(cb.id, e.value))
        .props(_select_props(cb.w))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(sel, value, prompt)
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = sel


def _chooser_reflow_hold(rec, cid: str) -> bool:
    # Quasar: re-setting a q-select's value/options while its popup is open disrupts or closes the
    # popup, so a hovered chooser's cell update is skipped across the reflow-preview re-render.
    g = rec._cur_gesture
    if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
        return False

    def group(c):
        return ":".join(c.split(":")[:2])

    return group(cid) == group(g.source)


def update_preset(rec, cb: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(rec, cb.id):
        return
    if cb.id.startswith("preset:temperament"):
        g = rec._cur_gesture
        if g is not None and g.kind == "temp" and g.reflowed:
            return
        value = presets.identify(rec._editor.state)
        rec.cells[cb.id].chooser.select.value = value
        _set_offlist_prompt(rec.cells[cb.id].chooser.select, value)
    elif cb.id == "preset:target":
        num, sel = rec.cells[cb.id].chooser.select
        limit, family = rec._target_preset_values()
        num.value = _limit_text(limit)
        sel.value = family
        _set_offlist_prompt(sel, family)
        num.set_enabled(not cb.disabled)
        sel.set_enabled(not cb.disabled)
        _sync_target_limit_error(rec, num, family, limit)
    elif cb.id == "preset:prescaler":
        options = list(presets.prescaler_options(rec._editor.settings["alt_complexity"]))
        value = rec._editor.displayed_prescaler_name
        value = value if value in options else None
        rec.cells[cb.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(rec.cells[cb.id].chooser.select, value)
        rec.cells[cb.id].chooser.select.set_enabled(not cb.disabled)
    elif cb.id.startswith("preset:projection"):
        options = presets.projection_options(rec._editor.state)
        value = rec._editor.displayed_projection_scheme_name
        value = value if value in options else None
        rec.cells[cb.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(rec.cells[cb.id].chooser.select, value)
        rec.cells[cb.id].chooser.select.set_enabled(not cb.disabled)
    else:
        name = rec._editor.displayed_tuning_scheme_name
        options = presets.tuning_scheme_options(
            service.is_all_interval(rec._editor.tuning_scheme),
            rec._editor.settings["alt_complexity"],
            rec._editor.settings["weighting"],
        )
        scheme = name if name in options else None
        rec.cells[cb.id].chooser.select.set_options(options, value=scheme)
        _set_offlist_prompt(rec.cells[cb.id].chooser.select, scheme)
        rec.cells[cb.id].chooser.select.set_enabled(not cb.disabled)


def _build_subpick(rec, cb, wrap, options, value):
    sel = (
        ui.select(
            options,
            value=value if value in options else None,
            on_change=lambda e, cid=cb.id: rec._cb.on_subpick(cid, e.value),
        )
        .props(_select_props(_SUBPICK_POPUP_W))
        .classes("rtt-preset rtt-subpick")
    )
    _set_offlist_prompt(sel, value if value in options else None)
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = sel


def build_etpick(rec, cb, wrap):
    state = rec._editor.state
    db = state.domain_basis
    value = None if cb.pending else presets.identify_et(state.mapping[cb.gen], db)
    _build_subpick(rec, cb, wrap, presets.et_options(db), value)


def build_commapick(rec, cb, wrap):
    state = rec._editor.state
    db = state.domain_basis
    value = None if cb.pending else presets.identify_comma(state.comma_basis[cb.comma], db)
    _build_subpick(rec, cb, wrap, presets.comma_options(db), value)


def update_subpick(rec, cb):
    g = rec._cur_gesture
    if g is not None and g.kind == "temp" and g.reflowed:
        return
    sel = rec.handles(cb.id).chooser.select
    if not isinstance(sel, ui.select):
        return
    state = rec._editor.state
    db = state.domain_basis
    if cb.id.startswith("etpick:"):
        options = presets.et_options(db)
        if cb.pending or cb.gen >= len(state.mapping):
            value = None
        else:
            value = presets.identify_et(state.mapping[cb.gen], db)
    else:
        options = presets.comma_options(db)
        if cb.pending or cb.comma >= len(state.comma_basis):
            value = None
        else:
            value = presets.identify_comma(state.comma_basis[cb.comma], db)
    value = value if value in options else None
    sel.set_options(options, value=value)
    _set_offlist_prompt(sel, value)


def _sync_target_limit_error(rec, num, family, limit) -> None:
    problem = service.target_limit_problem(family, limit)
    num.classes(
        add="rtt-limit-error" if problem else "", remove="" if problem else "rtt-limit-error"
    )
    if rec.target_limit_tip is not None:
        rec.target_limit_tip.set_text(
            tooltips.target_limit_help(problem)
            if problem
            else tooltips.control_help("preset", "preset:target")
        )
        rec.target_limit_tip.classes(
            add="rtt-tip-error" if problem else "", remove="" if problem else "rtt-tip-error"
        )


def build_control_select(rec, cb: spreadsheet.CellBox, wrap) -> None:
    sel = (
        ui.select(
            list(cb.values),
            value=cb.text or None,
            on_change=lambda e, cid=cb.id: rec._cb.on_control_select(cid, e.value),
        )
        .props(_select_props(cb.w))
        .classes("rtt-preset")
    )
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = sel


def update_control_select(rec, cb: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(rec, cb.id):
        return
    rec.cells[cb.id].chooser.select.set_options(list(cb.values), value=cb.text or None)
    rec.cells[cb.id].chooser.select.set_enabled(not cb.disabled)


def build_control_check(rec, cb: spreadsheet.CellBox, wrap) -> None:
    rec.cells[cb.id].chooser.check = (
        ui.checkbox(
            cb.text,
            value=cb.checked,
            on_change=lambda e, cid=cb.id: rec._cb.on_control_select(cid, e.value),
        )
        .props("dense")
        .classes("rtt-control-check")
    )
    apply = _control_check_preview(rec, cb)
    if apply is not None:
        preview_control(rec, wrap, apply)


def _control_check_preview(rec, cb: spreadsheet.CellBox):
    if cb.id == "control:diminuator":
        return lambda: rec._editor.set_diminuator_replaced(
            not service.diminuator_replaced(rec._editor.tuning_scheme)
        )
    if cb.id == "control:all_interval":
        return lambda: rec._editor.set_all_interval(
            not service.is_all_interval(rec._editor.tuning_scheme)
        )
    return None


def update_control_check(rec, cb: spreadsheet.CellBox) -> None:
    rec.cells[cb.id].chooser.check.value = cb.checked


def build_formchooser(rec, cb: spreadsheet.CellBox, wrap) -> None:
    sel = (
        ui.select(
            _formchooser_options(cb.id),
            value=cb.text or "",
            on_change=lambda e, c=cb.id: rec._cb.on_form_choose(c, e.value),
        )
        .props(_select_props(cb.w))
        .classes("rtt-preset")
    )
    _arm_option_hover(rec, sel, wrap, cb.id)
    rec.cells[cb.id].chooser.select = sel


def update_formchooser(rec, cb: spreadsheet.CellBox) -> None:
    if _chooser_reflow_hold(rec, cb.id):
        return
    rec.cells[cb.id].chooser.select.set_options(_formchooser_options(cb.id), value=cb.text or "")


def preview_control(rec, el, apply) -> None:
    el.on("mouseenter", lambda _=None: rec._cb.control_hover(apply))
    el.on("mouseleave", lambda _=None: rec._cb.control_unhover())


def preview_rank_remove(rec, el, axis: str, idx: int) -> None:
    el.on("mouseenter", lambda _=None: rec._cb.rank_remove_hover(axis, idx))
    el.on("mouseleave", lambda _=None: rec._cb.rank_remove_unhover())
