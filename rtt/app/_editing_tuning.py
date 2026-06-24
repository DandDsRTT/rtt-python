from __future__ import annotations

import asyncio
from typing import ClassVar

from nicegui import background_tasks, ui

from rtt.app import (
    service,
)
from rtt.app.page_assets import (
    _INVALID_EMBEDDING,
    _INVALID_PROJECTION,
    _INVALID_TEMPERAMENT,
    _PTEXT_DUAL_VECTOR_KIND,
    _TARGET_LIMIT_DEBOUNCE,
    _WHEEL_STEPS,
    cb_method,
)
from rtt.app.render_html import (
    _wheel_step,
)


class _TuningEdits:
    _PTEXT_EDITORS: ClassVar[dict[str, str]] = {
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

    def __init__(self, e) -> None:
        self.e = e
        self.page = e.page
        self.target_limit_commit = None

    @cb_method
    def on_power_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        if cid not in ("optimization:power", "control:q"):
            return
        is_q = cid == "control:q"
        power = service.parse_power(
            self.page.rec.cells[cid].value.input.value, minimum=1.0 if is_q else 0.0
        )
        if power is None:
            return
        if is_q:
            self.page.editor.set_complexity_norm_power(power)
        else:
            self.page.editor.set_optimization_power(power)
        self.page.renderer.request_render()

    def _gen_position(self, tok):
        toks = self.page.col_tokens("gens")
        return toks.index(tok) if tok in toks else tok

    @cb_method
    def on_gentuning_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        mag = self.page.rec.decimal_value(cid)
        if not mag:
            return
        try:
            cents = abs(float(mag))
        except ValueError:
            return
        glyph = self.page.rec.handles(cid).value.gensign_face
        if glyph is not None and glyph.text not in ("+", ""):
            cents = -cents
        i = int(cid.rsplit(":", 1)[1])
        if ":ssgen:" in cid:
            self.page.editor.set_superspace_generator_tuning_component(i, cents)
        else:
            self.page.editor.set_generator_tuning_component(self._gen_position(i), cents)
        self.page.renderer.request_render()

    @cb_method
    def on_gentuning_wheel(self, cid, delta_y):
        if self.page.building or not delta_y:
            return
        i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
        if ":ssgen:" in cid:
            self.page.editor.nudge_superspace_generator_tuning_component(i, steps)
        else:
            self.page.editor.nudge_generator_tuning_component(self._gen_position(i), steps)
        self.page.renderer.request_render()

    @cb_method
    def on_value_wheel(self, cid, delta_y):
        if self.page.building or not delta_y or self.page.rec.handles(cid).value.input is None:
            return
        step = _WHEEL_STEPS.get(self.page.rec.handles(cid).kind)
        if step is None:
            return
        if self.page.rec.handles(cid).value.den_input is not None:
            self.page.building = True
            self.page.rec.set_decimal_value(
                cid, _wheel_step(self.page.rec.decimal_value(cid), delta_y, step)
            )
            self.page.building = False
            self.on_prescaler_change(cid)
            return
        self.page.rec.cells[cid].value.input.value = _wheel_step(
            self.page.rec.cells[cid].value.input.value, delta_y, step
        )
        commit = {
            "mapping": self.e.vectors.on_mapping_change,
            "commacell": self.e.vectors.on_comma_change,
            "interestcell": self.e.vectors.on_interest_change,
            "heldcell": self.e.vectors.on_held_change,
            "targetcell": self.e.vectors.on_target_cells_change,
            "formcell": self.e.vectors.on_form_change,
        }.get(self.page.rec.handles(cid).kind)
        if commit is not None:
            commit()

    @cb_method
    def on_target_limit_wheel(self, delta_y):
        if self.page.building or not delta_y:
            return
        num = self.page.rec.cells["preset:target"].chooser.select[0]
        self.page.building = True
        num.value = _wheel_step(num.value, delta_y)
        self.page.building = False
        self.on_target_limit_preview()
        if self.target_limit_commit is not None:
            self.target_limit_commit.cancel()
        self.target_limit_commit = background_tasks.create(
            self._debounced_target_commit(), name="target-limit-commit"
        )

    async def _debounced_target_commit(self):
        # NiceGUI: this runs off the loop (a background task) where the slot stack is empty, so enter the
        # captured page client or on_target_change's ui.notify can't resolve the client and the toast
        # silently vanishes.
        try:
            await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
        except asyncio.CancelledError:
            return
        self.target_limit_commit = None
        with self.page.page_client:
            self.e.on_target_change()

    @cb_method
    def on_target_limit_preview(self, typed=None):
        g = self.page.gestures.gesture
        if self.page.building or g is None or g.kind != "edit" or g.source != "preset:target":
            return
        num, sel = self.page.rec.cells["preset:target"].chooser.select
        raw = num.value if typed is None else typed
        out = service.resolve_target_limit(sel.value, raw, self.page.editor.state.domain_basis)
        self.e._apply_outcome(
            out, lambda: self.page.editor.set_target_spec(out.value), preview=True
        )

    @cb_method
    def on_prescaler_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        parts = cid.split(":")
        i, j = int(parts[3]), int(parts[4])
        out = service.custom_prescaler_entry(self.page.rec.decimal_value(cid), i == j)

        self.e._apply_outcome(
            out, lambda: self.page.editor.set_custom_prescaler_entry(i, j, out.value)
        )

    @cb_method
    def on_weight_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        raws = [
            self.page.rec.decimal_value(o)
            for o in self.page.rec.cells
            if o.startswith("weight:") and self.page.rec.cells[o].value.input is not None
        ]
        out = service.custom_weights(raws)

        self.e._apply_outcome(out, lambda: self.page.editor.set_custom_weights(list(out.value)))

    @cb_method
    def on_ptext_edit(self, cid, value):
        if self.page.building:
            return
        editor_method = self._PTEXT_EDITORS.get(cid)
        if editor_method is None:
            return
        if not self.page.editor.settings.get("ebk", True):
            value = service.simple_matrix_to_ebk(value, _PTEXT_DUAL_VECTOR_KIND.get(cid, False))
        if getattr(self.page.editor, editor_method)(value):
            self.page.rec.cells[cid].value.ptext_input.classes(remove="rtt-ptext-error")
            self.page.renderer.request_render()
            return
        self.page.rec.cells[cid].value.ptext_input.classes(add="rtt-ptext-error")
        toast = self._ptext_error_toast(cid, value)
        if toast:
            ui.notify(toast, type="negative", position="top")

    def _ptext_error_toast(self, cid, value):
        if cid == "ptext:mapping:primes":
            st = service.parse_mapping_state(value)
            if st is not None and not service.is_proper_temperament(st.mapping):
                return _INVALID_TEMPERAMENT
        elif cid == "ptext:vectors:commas":
            b = service.parse_comma_basis(value)
            if b is not None and not service.is_proper_temperament(
                service.from_comma_basis(b).mapping
            ):
                return _INVALID_TEMPERAMENT
        elif cid == "ptext:projection:primes" and service.parse_projection(value) is not None:
            return _INVALID_PROJECTION
        elif (
            cid == "ptext:projection:gens"
            and service.parse_embedding(
                value, self.page.editor.state.d, len(self.page.editor.state.mapping)
            )
            is not None
        ):
            return _INVALID_EMBEDDING
        return None
