from __future__ import annotations

from nicegui import ui

from rtt.app import (
    presets,
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_hover import preview_control
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
    _formchooser_options,
    _GroupedSelect,
    _set_offlist_prompt,
    build_radio_label,
    build_radio_option,
)
from rtt.app.render_html import (
    _FOLD_GLYPH,
    _control_svg,
    _limit_text,
    _select_props,
)


def build_rangemode(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-range-mode")
    opts = {}
    for mode in ("monotone", "tradeoff"):
        opt = build_radio_option(mode)
        opt.on("click", lambda _=None, m=mode: reconciler._callbacks.on_range_mode(m))
        opts[mode] = opt
    reconciler.cells[cell.id].chooser.rangeopts = opts


def update_rangemode(reconciler, cell: spreadsheet.Cell) -> None:
    for mode, opt in reconciler.cells[cell.id].chooser.rangeopts.items():
        (
            opt.classes(add="rtt-range-option-on")
            if mode == cell.text
            else opt.classes(remove="rtt-range-option-on")
        )


def build_scheme_button(reconciler, cell: spreadsheet.Cell, _wrap) -> None:
    reconciler.cells[cell.id].chooser.scheme_button = (
        ui.button(
            cell.text,
            on_click=lambda: reconciler._callbacks.act(reconciler._editor.back_to_scheme),
            color=None,
        )
        .props("unelevated dense no-caps flat")
        .classes("rtt-scheme-button")
    )


def update_scheme_button(reconciler, cell: spreadsheet.Cell) -> None:
    active = not reconciler._editor.tuning_is_optimized
    handles = reconciler.cells[cell.id].chooser
    handles.scheme_button.set_enabled(active)
    if handles.scheme_help_tip is not None:
        handles.scheme_help_tip.set_text(tooltips.scheme_help(active))


def build_foldtoggle(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    item = cell.id.split("toggle:", 1)[1]
    reconciler.cells[cell.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cell.text])).classes(
        "rtt-glyph rtt-toggle"
    )
    reconciler.cells[cell.id].chooser.fold_state = cell.text
    wrap.on("click", lambda _=None, it=item: reconciler._callbacks.on_toggle(it))


def build_alltoggle(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    reconciler.cells[cell.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cell.text])).classes(
        "rtt-glyph rtt-toggle"
    )
    reconciler.cells[cell.id].chooser.fold_state = cell.text
    wrap.on("click", lambda _=None: reconciler._callbacks.on_toggle_all())


def update_foldtoggle(reconciler, cell: spreadsheet.Cell) -> None:
    if reconciler.handles(cell.id).chooser.fold_state != cell.text:
        reconciler.cells[cell.id].display.html.set_content(_control_svg(_FOLD_GLYPH[cell.text]))
        reconciler.cells[cell.id].chooser.fold_state = cell.text


def _arm_option_hover(reconciler, selection, wrap, cell_id: str) -> None:
    selection.add_slot(
        "option",
        f"""
        <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cell_id}">
            <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
        </q-item>
    """,
    )
    wrap.on(
        "opthover",
        lambda e: reconciler._callbacks.on_chooser_hover(cell_id, e.args),
        args=["detail"],
    )
    selection.on("popup-show", lambda _=None: reconciler._callbacks.on_popup(cell_id, True))
    selection.on("popup-hide", lambda _=None: reconciler._callbacks.on_popup(cell_id, False))


def build_preset(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    name = cell.id.split(":")[1]
    if name == "target":
        _build_preset_target(reconciler, cell, wrap)
    elif name == "temperament":
        _build_preset_temperament(reconciler, cell, wrap)
    else:
        options, value, prompt = _scheme_options(reconciler, name)
        _build_scheme_select(reconciler, cell, wrap, options, value, prompt)


def _build_preset_target(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    limit, family = reconciler._target_preset_values()
    with ui.element("div").classes("rtt-preset-target"):
        number = (
            ui.input(
                value=_limit_text(limit) or service.NO_LIMIT_TEXT,
                on_change=lambda _e: reconciler._callbacks.on_target_change(),
            )
            .props(
                'dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300'
            )
            .classes("rtt-preset-number")
        )
        # NiceGUI: ui.input defaults loopback off (uncontrolled during typing), so the server can't
        # overwrite what was typed; _wire_target_limit turns loopback on so a rejected value reverts.
        _wire_target_limit(reconciler, number, cell)
        selection = (
            ui.select(
                list(presets.TARGET_SETS),
                value=family,
                on_change=lambda _e: reconciler._callbacks.on_target_change(),
            )
            .props(_select_props(cell.width - 30))
            .classes("rtt-preset")
        )
    _set_offlist_prompt(selection, family)
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = (number, selection)


def _wire_target_limit(reconciler, number, cell: spreadsheet.Cell) -> None:
    number.LOOPBACK = True
    number._props["loopback"] = True
    number.on(
        "wheel",
        lambda e: reconciler._callbacks.on_target_limit_wheel(e.args.get("deltaY")),
        args=["deltaY"],
        js_handler=_INT_WHEEL_JS,
    )
    number.on("focus", lambda _=None: reconciler._callbacks.on_cell_focus(cell.id))
    number.on("blur", lambda _=None, cell_id=cell.id: reconciler._callbacks.on_cell_blur(cell_id))
    # Quasar: a debounced field only commits its value on a typing pause or blur, so Enter alone
    # never submits; blurring on Enter makes Quasar flush the debounced value (firing on_change).
    number.on("keydown.enter", js_handler="(e) => e.target.blur()")
    # NiceGUI/Quasar: a Quasar QInput doesn't forward native `input` to a NiceGUI `.on()` listener,
    # and NiceGUI's `args=` filters only TOP-LEVEL event keys (it can't pull nested target.value),
    # so listen on `keyup` and emit the live DOM text ourselves to preview each keystroke.
    number.on(
        "keyup",
        lambda e: reconciler._callbacks.on_target_limit_preview(e.args),
        js_handler="(e) => emit(e.target.value)",
    )


def _build_preset_temperament(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    value = presets.identify(reconciler._editor.state)
    selection = (
        _GroupedSelect(
            presets.temperament_options(),
            value=value,
            is_divider=presets.is_divider,
            on_change=lambda e: reconciler._callbacks.on_preset(cell.id, e.value),
        )
        .props(_select_props(cell.width))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(selection, value)
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = selection


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


def _build_scheme_select(reconciler, cell, wrap, options, value, prompt) -> None:
    selection = (
        ui.select(
            options,
            value=value,
            on_change=lambda e: reconciler._callbacks.on_preset(cell.id, e.value),
        )
        .props(_select_props(cell.width))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(selection, value, prompt)
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = selection


def _chooser_reflow_hold(reconciler, cell_id: str) -> bool:
    # Quasar: re-setting a q-select's value/options while its popup is open disrupts or closes the
    # popup, so a hovered chooser's cell update is skipped across the reflow-preview re-render.
    g = reconciler._cur_gesture
    if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
        return False

    def group(c):
        return ":".join(c.split(":")[:2])

    return group(cell_id) == group(g.source)


def update_preset(reconciler, cell: spreadsheet.Cell) -> None:
    if _chooser_reflow_hold(reconciler, cell.id):
        return
    if cell.id.startswith("preset:temperament"):
        g = reconciler._cur_gesture
        if g is not None and g.kind == "temp" and g.reflowed:
            return
        value = presets.identify(reconciler._editor.state)
        reconciler.cells[cell.id].chooser.select.value = value
        _set_offlist_prompt(reconciler.cells[cell.id].chooser.select, value)
    elif cell.id == "preset:target":
        number, selection = reconciler.cells[cell.id].chooser.select
        limit, family = reconciler._target_preset_values()
        number.value = _limit_text(limit) or service.NO_LIMIT_TEXT
        selection.value = family
        _set_offlist_prompt(selection, family)
        number.set_enabled(not cell.disabled)
        selection.set_enabled(not cell.disabled)
        _sync_target_limit_error(reconciler, number, family, limit)
    elif cell.id == "preset:prescaler":
        options = list(presets.prescaler_options(reconciler._editor.settings["alt_complexity"]))
        value = reconciler._editor.displayed_prescaler_name
        value = value if value in options else None
        reconciler.cells[cell.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(reconciler.cells[cell.id].chooser.select, value)
        reconciler.cells[cell.id].chooser.select.set_enabled(not cell.disabled)
    elif cell.id.startswith("preset:projection"):
        options = presets.projection_options(reconciler._editor.state)
        value = reconciler._editor.displayed_projection_scheme_name
        value = value if value in options else None
        reconciler.cells[cell.id].chooser.select.set_options(options, value=value)
        _set_offlist_prompt(reconciler.cells[cell.id].chooser.select, value)
        reconciler.cells[cell.id].chooser.select.set_enabled(not cell.disabled)
        if (tip := reconciler.cells[cell.id].preset_help_tip) is not None:
            tip.set_text(tooltips.control_help("preset", cell.id, disabled=cell.disabled))
    else:
        name = reconciler._editor.displayed_tuning_scheme_name
        options = presets.tuning_scheme_options(
            service.is_all_interval(reconciler._editor.tuning_scheme),
            reconciler._editor.settings["alt_complexity"],
            reconciler._editor.settings["weighting"],
            reconciler._editor.settings["terminology"],
        )
        scheme = name if name in options else None
        reconciler.cells[cell.id].chooser.select.set_options(options, value=scheme)
        _set_offlist_prompt(reconciler.cells[cell.id].chooser.select, scheme)
        reconciler.cells[cell.id].chooser.select.set_enabled(not cell.disabled)


_SUBPICK_CHAR_PX = 6
_SUBPICK_POPUP_PAD_PX = 18
_SUBPICK_POPUP_MIN_PX = 120


def _subpick_popup_width(options) -> int:
    longest = max((len(label) for label in options.values()), default=0)
    return max(_SUBPICK_POPUP_MIN_PX, longest * _SUBPICK_CHAR_PX + _SUBPICK_POPUP_PAD_PX)


def _build_subpick(reconciler, cell, wrap, options, value):
    selection = (
        ui.select(
            options,
            value=value if value in options else None,
            on_change=lambda e, cell_id=cell.id: reconciler._callbacks.on_subpick(cell_id, e.value),
        )
        .props(_select_props(_subpick_popup_width(options), fixed=True))
        .classes("rtt-preset rtt-subpick")
    )
    _set_offlist_prompt(selection, value if value in options else None)
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = selection


def build_etpick(reconciler, cell, wrap):
    state = reconciler._editor.state
    db = state.domain_basis
    value = None if cell.pending else presets.identify_et(state.mapping[cell.generator], db)
    _build_subpick(reconciler, cell, wrap, presets.et_options(db), value)


def build_commapick(reconciler, cell, wrap):
    state = reconciler._editor.state
    db = state.domain_basis
    value = None if cell.pending else presets.identify_comma(state.comma_basis[cell.comma], db)
    _build_subpick(reconciler, cell, wrap, presets.comma_options(db), value)


def update_subpick(reconciler, cell):
    g = reconciler._cur_gesture
    if g is not None and g.kind == "temp" and g.reflowed:
        return
    selection = reconciler.handles(cell.id).chooser.select
    if not isinstance(selection, ui.select):
        return
    state = reconciler._editor.state
    db = state.domain_basis
    if cell.id.startswith("etpick:"):
        options = presets.et_options(db)
        if cell.pending or cell.generator >= len(state.mapping):
            value = None
        else:
            value = presets.identify_et(state.mapping[cell.generator], db)
    else:
        options = presets.comma_options(db)
        if cell.pending or cell.comma >= len(state.comma_basis):
            value = None
        else:
            value = presets.identify_comma(state.comma_basis[cell.comma], db)
    value = value if value in options else None
    selection.set_options(options, value=value)
    _set_offlist_prompt(selection, value)


def _sync_target_limit_error(reconciler, number, family, limit) -> None:
    problem = service.target_limit_problem(family, limit)
    number.classes(
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


def _control_select_value(cell: spreadsheet.Cell):
    return cell.text if cell.text in cell.values else None


def build_control_select(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    value = _control_select_value(cell)
    selection = (
        ui.select(
            list(cell.values),
            value=value,
            on_change=lambda e, cell_id=cell.id: reconciler._callbacks.on_control_select(
                cell_id, e.value
            ),
        )
        .props(_select_props(cell.width))
        .classes("rtt-preset")
    )
    _set_offlist_prompt(selection, value, cell.text or "-")
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = selection


def update_control_select(reconciler, cell: spreadsheet.Cell) -> None:
    if _chooser_reflow_hold(reconciler, cell.id):
        return
    value = _control_select_value(cell)
    reconciler.cells[cell.id].chooser.select.set_options(list(cell.values), value=value)
    _set_offlist_prompt(reconciler.cells[cell.id].chooser.select, value, cell.text or "-")
    reconciler.cells[cell.id].chooser.select.set_enabled(not cell.disabled)


def _fill_control_radio(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    opts = {}
    labels = cell.option_labels or cell.values
    for idx, (value, label) in enumerate(zip(cell.values, labels, strict=False)):
        opt = build_radio_option(label).mark(f"{cell.id}:{value}")
        opt._props["data-optidx"] = idx
        opt._props["data-optcid"] = cell.id
        opt.on("click", lambda _=None, v=value: reconciler._callbacks.on_control_select(cell.id, v))
        opts[value] = opt
    if cell.label:
        build_radio_label(cell.label)
    reconciler.cells[cell.id].chooser.rangeopts = opts
    reconciler.cells[cell.id].chooser.radio = (tuple(cell.values), cell.disabled)
    _sync_control_radio(reconciler, cell, wrap)


def build_control_radio(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    wrap.classes("rtt-range-mode")
    wrap.on(
        "opthover",
        lambda e: reconciler._callbacks.on_chooser_hover(cell.id, e.args),
        args=["detail"],
    )
    _fill_control_radio(reconciler, cell, wrap)


def update_control_radio(reconciler, cell: spreadsheet.Cell) -> None:
    wrap = reconciler.entities[cell.id].element
    if reconciler.cells[cell.id].chooser.radio[0] != tuple(cell.values):
        wrap.clear()
        with wrap:
            _fill_control_radio(reconciler, cell, wrap)
        return
    reconciler.cells[cell.id].chooser.radio = (tuple(cell.values), cell.disabled)
    _sync_control_radio(reconciler, cell, wrap)


def _sync_control_radio(reconciler, cell: spreadsheet.Cell, element) -> None:
    for value, opt in reconciler.cells[cell.id].chooser.rangeopts.items():
        (
            opt.classes(add="rtt-range-option-on")
            if value == cell.text
            else opt.classes(remove="rtt-range-option-on")
        )
    element.classes(add="rtt-range-mode-disabled") if cell.disabled else element.classes(
        remove="rtt-range-mode-disabled"
    )


def build_control_check(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    reconciler.cells[cell.id].chooser.check = (
        ui.checkbox(
            cell.text,
            value=cell.checked,
            on_change=lambda e, cell_id=cell.id: reconciler._callbacks.on_control_select(
                cell_id, e.value
            ),
        )
        .props("dense")
        .classes("rtt-control-check")
    )
    apply = _control_check_preview(reconciler, cell)
    if apply is not None:
        preview_control(reconciler, wrap, apply, source_id=cell.id)


def _control_check_preview(reconciler, cell: spreadsheet.Cell):
    if cell.id == "control:diminuator":
        return lambda: reconciler._editor.set_diminuator_replaced(
            not service.diminuator_replaced(reconciler._editor.tuning_scheme)
        )
    if cell.id == "control:all_interval":
        return lambda: reconciler._editor.set_all_interval(
            not service.is_all_interval(reconciler._editor.tuning_scheme)
        )
    return None


def update_control_check(reconciler, cell: spreadsheet.Cell) -> None:
    reconciler.cells[cell.id].chooser.check.value = cell.checked


def build_formchooser(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    selection = (
        ui.select(
            _formchooser_options(cell.id),
            value=cell.text or "",
            on_change=lambda e, c=cell.id: reconciler._callbacks.on_form_choose(c, e.value),
        )
        .props(_select_props(cell.width))
        .classes("rtt-preset")
    )
    _arm_option_hover(reconciler, selection, wrap, cell.id)
    reconciler.cells[cell.id].chooser.select = selection


def update_formchooser(reconciler, cell: spreadsheet.Cell) -> None:
    if _chooser_reflow_hold(reconciler, cell.id):
        return
    reconciler.cells[cell.id].chooser.select.set_options(
        _formchooser_options(cell.id), value=cell.text or ""
    )
