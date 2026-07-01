from __future__ import annotations

from nicegui import ui

from rtt.app import (
    ids,
    presets,
    service,
    spreadsheet_text,
    tooltips,
)
from rtt.app.page_assets import (
    _INVALID_PRESCALER,
    _INVALID_TEMPERAMENT,
    _INVALID_WEIGHT,
    _TILE_HOST,
    _VecGridEdit,
)

_APPLY_SETTERS = (
    ("preset:tuning", "set_tuning_scheme"),
    ("preset:prescaler", "set_complexity_prescaler"),
    ("preset:projection", "set_established_projection"),
    ("control:slope", "set_weight_slope"),
)


def build_edit_specs(edit_controller) -> None:
    edit_controller._MAPPING_EDIT = _VecGridEdit(
        group="generators",
        count=lambda: len(edit_controller._editor.state.mapping),
        cell_id=ids.mapping_cell,
        pending=lambda: edit_controller._editor.pending_mapping_row,
        set_pending=edit_controller._editor.set_pending_mapping_row,
        commit=edit_controller._editor.edit_mapping,
        validate=service.is_proper_temperament,
        guard=lambda: edit_controller._editor.settings["temperament_tiles"],
    )
    edit_controller._COMMA_EDIT = _VecGridEdit(
        group="commas",
        count=lambda: len(edit_controller._editor.state.comma_basis),
        cell_id=ids.comma_cell,
        pending=lambda: edit_controller._editor.pending_comma,
        set_pending=edit_controller._editor.set_pending_comma,
        commit=edit_controller._editor.edit_comma_basis,
        validate=lambda basis: service.is_proper_temperament(
            service.from_comma_basis(basis).mapping
        ),
    )


def build_vector_list_specs(edit_controller) -> None:
    edit_controller._INTEREST_EDIT = _VecGridEdit(
        group="interest",
        count=lambda: len(edit_controller._editor.interest_vectors),
        cell_id=ids.interest_cell,
        pending=lambda: edit_controller._editor.pending_interest,
        set_pending=edit_controller._editor.set_pending_interest,
        commit=edit_controller._editor.set_interest_vectors,
        draft_arms=True,
    )
    edit_controller._HELD_EDIT = _VecGridEdit(
        group="held",
        count=lambda: len(edit_controller._editor.held_vectors),
        cell_id=ids.held_cell,
        pending=lambda: edit_controller._editor.pending_held,
        set_pending=edit_controller._editor.set_pending_held,
        commit=edit_controller._editor.set_held_vectors,
        draft_arms=True,
    )
    edit_controller._TARGET_EDIT = _VecGridEdit(
        group="targets",
        count=lambda: len(
            edit_controller._editor.target_override
            or service.target_interval_set(
                edit_controller._editor.target_spec, edit_controller._editor.state.domain_basis
            )
        ),
        cell_id=ids.target_cell,
        pending=lambda: edit_controller._editor.pending_target,
        set_pending=edit_controller._editor.set_pending_target,
        commit=edit_controller._editor.set_target_override_vectors,
        draft_arms=True,
    )
    edit_controller.draft_focus = {
        "comma": ("comma:pending", "commacell"),
        "target": ("target:pending", "targetcell"),
        "held": ("held:pending", "heldcell"),
        "interest": ("interest:pending", "interestcell"),
        "element": ("prime:pending", None),
        "mapping": (None, "mapping"),
    }


def reason_message(reason):
    if reason is service.Reason.INVALID_PRESCALER:
        return _INVALID_PRESCALER
    if reason is service.Reason.INVALID_WEIGHT:
        return _INVALID_WEIGHT
    if reason is service.Reason.TARGET_WHOLE:
        return tooltips.target_limit_help("whole")
    if reason is service.Reason.TARGET_ODD:
        return tooltips.target_limit_help("odd")
    return None


def apply_outcome(edit_controller, out, commit, preview=False) -> None:
    if preview:
        edit_controller._gestures.edit_candidate(
            commit if out.effect is service.Effect.ACCEPT else None
        )
        return
    if out.effect is service.Effect.IGNORE:
        return
    if out.effect is service.Effect.RERENDER:
        edit_controller._renderer.render()
        return
    message = out.message or reason_message(out.reason)
    if out.effect is service.Effect.REJECT:
        ui.notify(message, type="negative", position="top")
        edit_controller._renderer.render()
        return
    if message:
        ui.notify(message, type="negative", position="top")
    commit()
    edit_controller._renderer.request_render()


def act(gestures, renderer, action):
    gestures.end_commit_gestures()
    action()
    renderer.request_render()


def add_interval(edit_controller, action, group):
    edit_controller._gestures.end_commit_gestures()
    action()
    edit_controller._renderer.render()
    quant_id, vector_kind = edit_controller.draft_focus[group]
    layout = edit_controller._runtime.last_lay
    if any(cell_box.id == quant_id for cell_box in layout.cells):
        target = quant_id
    elif vector_kind is not None:
        target = next(
            (
                cell_box.id
                for cell_box in layout.cells
                if cell_box.pending and cell_box.prime == 0 and cell_box.kind == vector_kind
            ),
            None,
        )
    else:
        target = None
    if target is None and group == "element":
        target = next(
            (cell_box.id for cell_box in layout.cells if cell_box.id == "basis:pending"), None
        )
    inp = edit_controller._rec.handles(target).value.input if target is not None else None
    if inp is not None:
        focus_draft_cell(inp)


def focus_draft_cell(inp) -> None:
    # Browser: a direct runMethod can race Vue's mount in a real browser (the cell-create update
    # and this focus can arrive in one frame, so focus runs before the $ref exists and no-ops), so
    # defer to the next macrotask and poll for the mount. setTimeout (not requestAnimationFrame,
    # which is paused while the tab is hidden, e.g. the render tests) drives both visible and hidden.
    ui.run_javascript(
        f"(function(){{var id={inp.id},n=0;function go(){{var c=getElement(id);"
        f"if(c){{runMethod(id,'focus',[]);runMethod(id,'select',[]);"
        f"var el=document.activeElement,cell=el&&el.closest&&el.closest('.rtt-cell'),"
        f"body=cell&&cell.closest('.rtt-gridbody');"
        f"if(body){{var cr=cell.getBoundingClientRect(),br=body.getBoundingClientRect(),"
        f"band=body.querySelector('.rtt-rowband'),band_width=band?band.getBoundingClientRect().width:0,pl=24,pt=8;"
        f"if(cr.left<br.left+band_width+pl)body.scrollLeft-=br.left+band_width+pl-cr.left;"
        f"else if(cr.right>br.right-pl)body.scrollLeft+=cr.right-br.right+pl;"
        f"if(cr.top<br.top+pt)body.scrollTop-=br.top+pt-cr.top;"
        f"else if(cr.bottom>br.bottom-pt)body.scrollTop+=cr.bottom-br.bottom+pt;}}return;}}"
        f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()"
    )


def on_show_toggle(edit_controller, key, value):
    if edit_controller._runtime.building:
        return
    if key == "nonstandard_domain" and not value and edit_controller._editor.basis_is_nonstandard:
        edit_controller._editor.exit_nonstandard_domain()
        edit_controller._renderer.render()
        return
    edit_controller._editor.set_show(key, value)
    edit_controller._renderer.render()


def on_select_all(editor, renderer, runtime, value, keys):
    if runtime.building:
        return
    editor.set_all_show(value, runtime.available_in(keys))
    renderer.render()


def on_part_click(editor, renderer, runtime, key):
    if runtime.building:
        return
    host = _TILE_HOST.get(key)
    if host is not None and not editor.settings[host]:
        return
    editor.set_show(key, not editor.settings[key])
    renderer.render()


def on_preset(edit_controller, cell_id, value):
    if edit_controller._runtime.building:
        return
    if cell_id.startswith("preset:temperament"):
        if value in presets.TEMPERAMENT_COMMAS:
            edit_controller._gestures.end_gesture()
            edit_controller._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
            edit_controller._renderer.request_render()
        else:
            edit_controller._renderer.render()
        return
    apply = candidate_apply(edit_controller, cell_id, value)
    if apply is not None:
        edit_controller._gestures.end_chooser_gesture()
        apply()
        edit_controller._renderer.request_render()


def on_subpick(edit_controller, cell_id, value):
    if edit_controller._runtime.building or value is None:
        return
    edit_controller._gestures.end_gesture()
    db = edit_controller._editor.state.domain_basis
    if cell_id == "etpick:draft":
        edit_controller._editor.set_pending_mapping_row(list(presets.et_value_to_val(value, db)))
        ok = edit_controller._editor.pending_mapping_row is None
    elif cell_id == "commapick:draft":
        edit_controller._editor.set_pending_comma(list(presets.comma_value_to_vector(value, db)))
        ok = edit_controller._editor.pending_comma is None
    elif cell_id.startswith("etpick:"):
        i = edit_controller._runtime.token_index(cell_id, "generators")
        ok = i is not None and edit_controller._editor.set_mapping_row(
            i, presets.et_value_to_val(value, db)
        )
    else:
        c = edit_controller._runtime.token_index(cell_id, "commas")
        ok = c is not None and edit_controller._editor.set_comma(
            c, presets.comma_value_to_vector(value, db)
        )
    if not ok:
        ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
    edit_controller._renderer.render()


def on_form_choose(edit_controller, cell_id, value):
    if edit_controller._runtime.building:
        return
    apply = candidate_apply(edit_controller, cell_id, value)
    if apply is not None:
        edit_controller._gestures.end_chooser_gesture()
        apply()
        edit_controller._renderer.request_render()


def on_target_change(edit_controller):
    if edit_controller._runtime.building:
        return
    edit_controller._gestures.end_chooser_gesture()
    number, selection = edit_controller._rec.cells["preset:target"].chooser.select
    out = service.resolve_target_limit(
        selection.value, number.value, edit_controller._editor.state.domain_basis
    )
    apply_outcome(edit_controller, out, lambda: edit_controller._editor.set_target_spec(out.value))


def on_control_select(edit_controller, cell_id, value):
    if edit_controller._runtime.building or value is None:
        return
    apply = candidate_apply(edit_controller, cell_id, value)
    if apply is not None:
        edit_controller._gestures.end_chooser_gesture()
        apply()
    elif cell_id == "control:diminuator":
        edit_controller._editor.set_diminuator_replaced(bool(value))
    elif cell_id == "control:all_interval":
        edit_controller._editor.set_all_interval(bool(value))
    else:
        return
    edit_controller._renderer.request_render()


def on_range_mode(edit_controller, value):
    if edit_controller._runtime.building or value is None:
        return
    edit_controller._editor.set_range_mode(value)
    edit_controller._renderer.render()


def on_toggle(edit_controller, item):
    edit_controller._editor.toggle_collapsed(item)
    edit_controller._renderer.render()


def on_toggle_all(edit_controller):
    edit_controller._editor.set_collapsed(
        spreadsheet_text.toggle_all_collapsed(
            edit_controller._runtime.last_lay, edit_controller._editor.collapsed
        )
    )
    edit_controller._renderer.render()


def candidate_apply(edit_controller, cell_id, value):
    if value is None:
        return None
    for prefix, setter in _APPLY_SETTERS:
        if cell_id.startswith(prefix):
            return lambda v=value, s=setter: getattr(edit_controller._editor, s)(v)
    if cell_id == "control:complexity":
        return complexity_apply(edit_controller, value)
    if cell_id.startswith("formchooser:"):
        return formchooser_apply(edit_controller, cell_id, value)
    return None


def complexity_apply(edit_controller, value):
    if value == "custom":
        return None
    internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
    return lambda: edit_controller._editor.set_complexity_name(internal)


def formchooser_apply(edit_controller, cell_id, value):
    name = cell_id.split(":", 1)[1]
    if name == "mapping":
        if value not in service.MAPPING_FORM_KEYS:
            return None
        return lambda: edit_controller._editor.set_mapping_form(value)
    if value not in service.COMMA_BASIS_FORM_KEYS:
        return None
    return lambda: edit_controller._editor.set_comma_basis_form(value)
