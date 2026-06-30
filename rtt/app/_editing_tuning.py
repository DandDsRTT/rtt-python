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
    "plain_text:mapping:primes": "try_edit_mapping_text",
    "plain_text:mapping:canonical_generators": "try_edit_form_matrix_text",
    "plain_text:vectors:commas": "try_edit_comma_basis_text",
    "plain_text:tuning:generators": "set_generator_tuning_text",
    "plain_text:tuning:superspace_generators": "set_superspace_generator_tuning_text",
    "plain_text:vectors:targets": "set_target_override_text",
    "plain_text:prescaling:primes": "set_custom_prescaler_text",
    "plain_text:projection:primes": "try_edit_projection_text",
    "plain_text:projection:generators": "try_edit_embedding_text",
}


class _TuningEdits:
    def __init__(self, e) -> None:
        self.e = e
        self.target_limit_commit = None

    @cb_method
    def on_power_change(self, cell_id):
        _power_change(self.e, cell_id)

    @cb_method
    def on_generator_tuning_change(self, cell_id):
        _generator_tuning_change(self.e, cell_id)

    @cb_method
    def on_generator_tuning_wheel(self, cell_id, delta_y):
        _generator_tuning_wheel(self.e, cell_id, delta_y)

    @cb_method
    def on_value_wheel(self, cell_id, delta_y):
        _value_wheel(self.e, cell_id, delta_y)

    @cb_method
    def on_target_limit_wheel(self, delta_y):
        _target_limit_wheel(self, delta_y)

    @cb_method
    def on_target_limit_preview(self, typed=None):
        _target_limit_preview(self.e, typed)

    @cb_method
    def on_prescaler_change(self, cell_id):
        _prescaler_change(self.e, cell_id)

    @cb_method
    def on_weight_change(self, cell_id):
        _weight_change(self.e, cell_id)

    @cb_method
    def on_plain_text_edit(self, cell_id, value):
        _plain_text_edit(self.e, cell_id, value)


def _power_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    if cell_id not in ("optimization:power", "control:q"):
        return
    is_q = cell_id == "control:q"
    power = service.parse_power(
        edit_controller._rec.cells[cell_id].value.input.value, minimum=1.0 if is_q else 0.0
    )
    if power is None:
        return
    if is_q:
        edit_controller._editor.set_complexity_norm_power(power)
    else:
        edit_controller._editor.set_optimization_power(power)
    edit_controller._renderer.request_render()


def _generator_position(edit_controller, token):
    toks = edit_controller._runtime.column_tokens("generators")
    return toks.index(token) if token in toks else token


def _generator_tuning_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    mag = edit_controller._rec.decimal_value(cell_id)
    if not mag:
        return
    try:
        cents = abs(float(mag))
    except ValueError:
        return
    glyph = edit_controller._rec.handles(cell_id).value.generator_sign_face
    if glyph is not None and glyph.text not in ("+", ""):
        cents = -cents
    i = int(cell_id.rsplit(":", 1)[1])
    if ":superspace_generator:" in cell_id:
        edit_controller._editor.set_superspace_generator_tuning_component(i, cents)
    else:
        edit_controller._editor.set_generator_tuning_component(
            _generator_position(edit_controller, i), cents
        )
    edit_controller._renderer.request_render()


def _generator_tuning_wheel(edit_controller, cell_id, delta_y):
    if edit_controller._runtime.building or not delta_y:
        return
    i, steps = int(cell_id.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
    if ":superspace_generator:" in cell_id:
        edit_controller._editor.nudge_superspace_generator_tuning_component(i, steps)
    else:
        edit_controller._editor.nudge_generator_tuning_component(
            _generator_position(edit_controller, i), steps
        )
    edit_controller._renderer.request_render()


def _value_wheel(edit_controller, cell_id, delta_y):
    if (
        edit_controller._runtime.building
        or not delta_y
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    step = _WHEEL_STEPS.get(edit_controller._rec.handles(cell_id).kind)
    if step is None:
        return
    if edit_controller._rec.handles(cell_id).value.den_input is not None:
        with edit_controller._runtime.building_guard():
            edit_controller._rec.set_decimal_value(
                cell_id, _wheel_step(edit_controller._rec.decimal_value(cell_id), delta_y, step)
            )
        _prescaler_change(edit_controller, cell_id)
        return
    edit_controller._rec.cells[cell_id].value.input.value = _wheel_step(
        edit_controller._rec.cells[cell_id].value.input.value, delta_y, step
    )
    commit = {
        "mapping": edit_controller.vectors.on_mapping_change,
        "commacell": edit_controller.vectors.on_comma_change,
        "interestcell": edit_controller.vectors.on_interest_change,
        "heldcell": edit_controller.vectors.on_held_change,
        "targetcell": edit_controller.vectors.on_target_cells_change,
        "formcell": edit_controller.vectors.on_form_change,
    }.get(edit_controller._rec.handles(cell_id).kind)
    if commit is not None:
        commit()


def _target_limit_wheel(tuning_edits, delta_y):
    edit_controller = tuning_edits.e
    if edit_controller._runtime.building or not delta_y:
        return
    num = edit_controller._rec.cells["preset:target"].chooser.select[0]
    with edit_controller._runtime.building_guard():
        num.value = _wheel_step(num.value, delta_y)
    _target_limit_preview(edit_controller)
    if tuning_edits.target_limit_commit is not None:
        tuning_edits.target_limit_commit.cancel()
    tuning_edits.target_limit_commit = background_tasks.create(
        _debounced_target_commit(tuning_edits), name="target-limit-commit"
    )


async def _debounced_target_commit(tuning_edits):
    # NiceGUI: this runs off the loop (a background task) where the slot stack is empty, so enter the
    # captured page client or on_target_change's ui.notify can't resolve the client and the toast
    # silently vanishes.
    try:
        await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
    except asyncio.CancelledError:
        return
    tuning_edits.target_limit_commit = None
    edit_controller = tuning_edits.e
    with edit_controller._runtime.page_client:
        edit_controller.on_target_change()


def _target_limit_preview(edit_controller, typed=None):
    g = edit_controller._gestures.gesture
    if (
        edit_controller._runtime.building
        or g is None
        or g.kind != "edit"
        or g.source != "preset:target"
    ):
        return
    num, selection = edit_controller._rec.cells["preset:target"].chooser.select
    raw = num.value if typed is None else typed
    out = service.resolve_target_limit(
        selection.value, raw, edit_controller._editor.state.domain_basis
    )
    edit_controller._apply_outcome(
        out, lambda: edit_controller._editor.set_target_spec(out.value), preview=True
    )


def _prescaler_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    parts = cell_id.split(":")
    i, j = int(parts[3]), int(parts[4])
    out = service.custom_prescaler_entry(edit_controller._rec.decimal_value(cell_id), i == j)
    edit_controller._apply_outcome(
        out, lambda: edit_controller._editor.set_custom_prescaler_entry(i, j, out.value)
    )


def _weight_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    raws = [
        edit_controller._rec.decimal_value(o)
        for o in edit_controller._rec.cells
        if o.startswith("weight:") and edit_controller._rec.cells[o].value.input is not None
    ]
    out = service.custom_weights(raws)
    edit_controller._apply_outcome(
        out, lambda: edit_controller._editor.set_custom_weights(list(out.value))
    )


def _plain_text_edit(edit_controller, cell_id, value):
    if edit_controller._runtime.building:
        return
    editor_method = _PLAIN_TEXT_EDITORS.get(cell_id)
    if editor_method is None:
        return
    if not edit_controller._editor.settings.get("ebk", True):
        value = service.simple_matrix_to_ebk(
            value, _PLAIN_TEXT_DUAL_VECTOR_KIND.get(cell_id, False)
        )
    if getattr(edit_controller._editor, editor_method)(value):
        edit_controller._rec.cells[cell_id].value.plain_text_input.classes(
            remove="rtt-plain-text-error"
        )
        edit_controller._renderer.request_render()
        return
    edit_controller._rec.cells[cell_id].value.plain_text_input.classes(add="rtt-plain-text-error")
    toast = _plain_text_error_toast(edit_controller, cell_id, value)
    if toast:
        ui.notify(toast, type="negative", position="top")


def _plain_text_error_toast(edit_controller, cell_id, value):
    if cell_id == "plain_text:mapping:primes":
        st = service.parse_mapping_state(value)
        if st is not None and not service.is_proper_temperament(st.mapping):
            return _INVALID_TEMPERAMENT
    elif cell_id == "plain_text:vectors:commas":
        b = service.parse_comma_basis(value)
        if b is not None and not service.is_proper_temperament(service.from_comma_basis(b).mapping):
            return _INVALID_TEMPERAMENT
    elif cell_id == "plain_text:projection:primes" and service.parse_projection(value) is not None:
        return _INVALID_PROJECTION
    elif (
        cell_id == "plain_text:projection:generators"
        and service.parse_embedding(
            value,
            edit_controller._editor.state.dimensionality,
            len(edit_controller._editor.state.mapping),
        )
        is not None
    ):
        return _INVALID_EMBEDDING
    return None
