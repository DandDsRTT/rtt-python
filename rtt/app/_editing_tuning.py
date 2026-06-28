from __future__ import annotations

import asyncio

from nicegui import background_tasks, ui

from rtt.app import (
    service,
)
from rtt.app.page_assets import (
    _INVALID_EMBEDDING,
    _INVALID_PROJECTION,
    _INVALID_TEMPERAMENT,
    _PLAIN_TEXT_DUAL_VECTOR_KIND,
    _TARGET_LIMIT_DEBOUNCE,
    _WHEEL_STEPS,
    cb_method,
)
from rtt.app.render_html import (
    _wheel_step,
)

_PLAIN_TEXT_EDITORS: dict[str, str] = {
    "ptext:mapping:primes": "try_edit_mapping_text",
    "ptext:mapping:canongens": "try_edit_form_matrix_text",
    "ptext:vectors:commas": "try_edit_comma_basis_text",
    "ptext:tuning:gens": "set_generator_tuning_text",
    "ptext:tuning:ssgens": "set_superspace_generator_tuning_text",
    "ptext:vectors:targets": "set_target_override_text",
    "ptext:prescaling:primes": "set_custom_prescaler_text",
    "ptext:projection:primes": "try_edit_projection_text",
    "ptext:projection:gens": "try_edit_embedding_text",
}


class _TuningEdits:
    def __init__(self, e) -> None:
        self.e = e
        self.target_limit_commit = None

    @cb_method
    def on_power_change(self, cid):
        _power_change(self.e, cid)

    @cb_method
    def on_gentuning_change(self, cid):
        _gentuning_change(self.e, cid)

    @cb_method
    def on_gentuning_wheel(self, cid, delta_y):
        _gentuning_wheel(self.e, cid, delta_y)

    @cb_method
    def on_value_wheel(self, cid, delta_y):
        _value_wheel(self.e, cid, delta_y)

    @cb_method
    def on_target_limit_wheel(self, delta_y):
        _target_limit_wheel(self, delta_y)

    @cb_method
    def on_target_limit_preview(self, typed=None):
        _target_limit_preview(self.e, typed)

    @cb_method
    def on_prescaler_change(self, cid):
        _prescaler_change(self.e, cid)

    @cb_method
    def on_weight_change(self, cid):
        _weight_change(self.e, cid)

    @cb_method
    def on_plain_text_edit(self, cid, value):
        _plain_text_edit(self.e, cid, value)


def _power_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    if cid not in ("optimization:power", "control:q"):
        return
    is_q = cid == "control:q"
    power = service.parse_power(ec._rec.cells[cid].value.input.value, minimum=1.0 if is_q else 0.0)
    if power is None:
        return
    if is_q:
        ec._editor.set_complexity_norm_power(power)
    else:
        ec._editor.set_optimization_power(power)
    ec._renderer.request_render()


def _gen_position(ec, tok):
    toks = ec._runtime.col_tokens("gens")
    return toks.index(tok) if tok in toks else tok


def _gentuning_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    mag = ec._rec.decimal_value(cid)
    if not mag:
        return
    try:
        cents = abs(float(mag))
    except ValueError:
        return
    glyph = ec._rec.handles(cid).value.gensign_face
    if glyph is not None and glyph.text not in ("+", ""):
        cents = -cents
    i = int(cid.rsplit(":", 1)[1])
    if ":ssgen:" in cid:
        ec._editor.set_superspace_generator_tuning_component(i, cents)
    else:
        ec._editor.set_generator_tuning_component(_gen_position(ec, i), cents)
    ec._renderer.request_render()


def _gentuning_wheel(ec, cid, delta_y):
    if ec._runtime.building or not delta_y:
        return
    i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
    if ":ssgen:" in cid:
        ec._editor.nudge_superspace_generator_tuning_component(i, steps)
    else:
        ec._editor.nudge_generator_tuning_component(_gen_position(ec, i), steps)
    ec._renderer.request_render()


def _value_wheel(ec, cid, delta_y):
    if ec._runtime.building or not delta_y or ec._rec.handles(cid).value.input is None:
        return
    step = _WHEEL_STEPS.get(ec._rec.handles(cid).kind)
    if step is None:
        return
    if ec._rec.handles(cid).value.den_input is not None:
        with ec._runtime.building_guard():
            ec._rec.set_decimal_value(cid, _wheel_step(ec._rec.decimal_value(cid), delta_y, step))
        _prescaler_change(ec, cid)
        return
    ec._rec.cells[cid].value.input.value = _wheel_step(
        ec._rec.cells[cid].value.input.value, delta_y, step
    )
    commit = {
        "mapping": ec.vectors.on_mapping_change,
        "commacell": ec.vectors.on_comma_change,
        "interestcell": ec.vectors.on_interest_change,
        "heldcell": ec.vectors.on_held_change,
        "targetcell": ec.vectors.on_target_cells_change,
        "formcell": ec.vectors.on_form_change,
    }.get(ec._rec.handles(cid).kind)
    if commit is not None:
        commit()


def _target_limit_wheel(te, delta_y):
    ec = te.e
    if ec._runtime.building or not delta_y:
        return
    num = ec._rec.cells["preset:target"].chooser.select[0]
    with ec._runtime.building_guard():
        num.value = _wheel_step(num.value, delta_y)
    _target_limit_preview(ec)
    if te.target_limit_commit is not None:
        te.target_limit_commit.cancel()
    te.target_limit_commit = background_tasks.create(
        _debounced_target_commit(te), name="target-limit-commit"
    )


async def _debounced_target_commit(te):
    # NiceGUI: this runs off the loop (a background task) where the slot stack is empty, so enter the
    # captured page client or on_target_change's ui.notify can't resolve the client and the toast
    # silently vanishes.
    try:
        await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
    except asyncio.CancelledError:
        return
    te.target_limit_commit = None
    ec = te.e
    with ec._runtime.page_client:
        ec.on_target_change()


def _target_limit_preview(ec, typed=None):
    g = ec._gestures.gesture
    if ec._runtime.building or g is None or g.kind != "edit" or g.source != "preset:target":
        return
    num, sel = ec._rec.cells["preset:target"].chooser.select
    raw = num.value if typed is None else typed
    out = service.resolve_target_limit(sel.value, raw, ec._editor.state.domain_basis)
    ec._apply_outcome(out, lambda: ec._editor.set_target_spec(out.value), preview=True)


def _prescaler_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    parts = cid.split(":")
    i, j = int(parts[3]), int(parts[4])
    out = service.custom_prescaler_entry(ec._rec.decimal_value(cid), i == j)
    ec._apply_outcome(out, lambda: ec._editor.set_custom_prescaler_entry(i, j, out.value))


def _weight_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    raws = [
        ec._rec.decimal_value(o)
        for o in ec._rec.cells
        if o.startswith("weight:") and ec._rec.cells[o].value.input is not None
    ]
    out = service.custom_weights(raws)
    ec._apply_outcome(out, lambda: ec._editor.set_custom_weights(list(out.value)))


def _plain_text_edit(ec, cid, value):
    if ec._runtime.building:
        return
    editor_method = _PLAIN_TEXT_EDITORS.get(cid)
    if editor_method is None:
        return
    if not ec._editor.settings.get("ebk", True):
        value = service.simple_matrix_to_ebk(value, _PLAIN_TEXT_DUAL_VECTOR_KIND.get(cid, False))
    if getattr(ec._editor, editor_method)(value):
        ec._rec.cells[cid].value.plain_text_input.classes(remove="rtt-ptext-error")
        ec._renderer.request_render()
        return
    ec._rec.cells[cid].value.plain_text_input.classes(add="rtt-ptext-error")
    toast = _plain_text_error_toast(ec, cid, value)
    if toast:
        ui.notify(toast, type="negative", position="top")


def _plain_text_error_toast(ec, cid, value):
    if cid == "ptext:mapping:primes":
        st = service.parse_mapping_state(value)
        if st is not None and not service.is_proper_temperament(st.mapping):
            return _INVALID_TEMPERAMENT
    elif cid == "ptext:vectors:commas":
        b = service.parse_comma_basis(value)
        if b is not None and not service.is_proper_temperament(service.from_comma_basis(b).mapping):
            return _INVALID_TEMPERAMENT
    elif cid == "ptext:projection:primes" and service.parse_projection(value) is not None:
        return _INVALID_PROJECTION
    elif (
        cid == "ptext:projection:gens"
        and service.parse_embedding(value, ec._editor.state.d, len(ec._editor.state.mapping))
        is not None
    ):
        return _INVALID_EMBEDDING
    return None
