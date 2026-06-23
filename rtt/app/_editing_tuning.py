from __future__ import annotations

import asyncio
from typing import ClassVar

from nicegui import background_tasks, ui

from rtt.app import (
    service,
)
from rtt.app.page_assets import (
    _INVALID_EMBEDDING,
    _INVALID_PRESCALER,
    _INVALID_PROJECTION,
    _INVALID_TEMPERAMENT,
    _INVALID_WEIGHT,
    _PTEXT_DUAL_VECTOR_KIND,
    _TARGET_LIMIT_DEBOUNCE,
    _WHEEL_STEPS,
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

    def on_power_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        if cid not in ("optimization:power", "control:q"):
            return
        is_q = cid == "control:q"
        power = service.parse_power(self.page.rec.inputs[cid].value, minimum=1.0 if is_q else 0.0)
        if power is None:
            return
        if is_q:
            self.page.editor.set_complexity_norm_power(power)
        else:
            self.page.editor.set_optimization_power(power)
        self.page.renderer.request_render()  # a new optimization / complexity power retunes — render off the loop

    def _gen_position(self, tok):
        toks = self.page.col_tokens("gens")
        return toks.index(tok) if tok in toks else tok

    def on_gentuning_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        mag = self.page.rec.decimal_value(cid)
        if not mag:
            return
        try:
            cents = abs(float(mag))
        except ValueError:
            return
        glyph = self.page.rec.gensign_faces.get(cid)
        if glyph is not None and glyph.text not in ("+", ""):
            cents = -cents
        i = int(cid.rsplit(":", 1)[1])
        if ":ssgen:" in cid:
            self.page.editor.set_superspace_generator_tuning_component(i, cents)
        else:
            self.page.editor.set_generator_tuning_component(self._gen_position(i), cents)
        self.page.renderer.request_render()  # a manual generator override re-derives the maps — render off the loop

    def on_gentuning_wheel(self, cid, delta_y):
        if self.page.building or not delta_y:
            return
        i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
        if ":ssgen:" in cid:
            self.page.editor.nudge_superspace_generator_tuning_component(i, steps)
        else:
            self.page.editor.nudge_generator_tuning_component(self._gen_position(i), steps)
        # off the loop — rapid notches coalesce into one trailing rebuild at the value you land on
        self.page.renderer.request_render()

    def on_value_wheel(self, cid, delta_y):
        if self.page.building or not delta_y or cid not in self.page.rec.inputs:
            return
        step = _WHEEL_STEPS.get(self.page.rec.kinds.get(cid))
        if step is None:
            return
        if cid in self.page.rec.den_inputs:
            self.page.building = True
            self.page.rec.set_decimal_value(cid, _wheel_step(self.page.rec.decimal_value(cid), delta_y, step))
            self.page.building = False
            self.on_prescaler_change(cid)
            return
        self.page.rec.inputs[cid].value = _wheel_step(self.page.rec.inputs[cid].value, delta_y, step)
        commit = {
            "mapping": self.e.vectors.on_mapping_change,
            "commacell": self.e.vectors.on_comma_change,
            "interestcell": self.e.vectors.on_interest_change,
            "heldcell": self.e.vectors.on_held_change,
            "targetcell": self.e.vectors.on_target_cells_change,
            "formcell": self.e.vectors.on_form_change,
        }.get(self.page.rec.kinds.get(cid))
        if commit is not None:
            commit()

    def on_target_limit_wheel(self, delta_y):
        # step the TILT/OLD limit by ±1 per wheel notch. Unlike a matrix/vector cell, COMMITTING a
        # new limit rebuilds the whole target interval set, re-solves the tuning and re-renders the
        # grid — far too heavy to run on every notch. A fast scroll would queue one such solve per
        # notch, each costlier than the last as the set grows, and grind the app to a halt. So step
        # the shown number now (under the build guard, so the field's own on_target_change echo is a
        # no-op — handle_event runs it inline) and DEBOUNCE the commit: the value is server-side, so
        # the loopback-controlled field actually advances, while a re-armed task collapses the whole
        # gesture into ONE solve at the limit you land on. Focus-gated client-side (see _INT_WHEEL_JS).
        if self.page.building or not delta_y:
            return
        num = self.page.rec.selects["preset:target"][0]
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
        # the tail of a target-limit wheel gesture: once the notches stop for _TARGET_LIMIT_DEBOUNCE,
        # commit the number now in the field with the one real solve + render. A new notch cancels
        # this and arms a fresh one. The debounce collapses the whole gesture into one commit, so an
        # even odd-limit (OLD) you land on toasts once here (not once per notch) and the render reddens it.
        # We run off the loop (a background task), where the slot stack is empty — so enter the captured
        # page client's context, or on_target_change's ui.notify can't resolve the client and the toast
        # silently vanishes (render reaches its client the same captured-client way, see page_client above).
        try:
            await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
        except asyncio.CancelledError:
            return
        self.target_limit_commit = None
        with self.page.page_client:
            self.e.on_target_change()

    def on_target_limit_preview(self, typed=None):
        # live edit preview for the TILT/OLD limit field, mirroring on_element_preview: as the shown
        # limit changes (a wheel notch steps it, a keystroke types it) but BEFORE the debounced commit
        # reflows the grid, the candidate rings the target interval cells the new limit would MOVE
        # (amber) / REMOVE (red) in place. LOWERING the limit drops intervals; reddening them while
        # they're still on screen is what shows "what's going away" — a post-commit render can't, the
        # reflow has already deleted them. RAISING it just rings the survivors that move (the added
        # rows are off-screen until committed, so they can't ring), like every other no-reflow add
        # preview. `typed` is the live field text for a keystroke (the loopback field's debounced
        # model value lags a keystroke behind); the wheel passes None and reads the stepped number.
        g = self.page.gestures.gesture
        if self.page.building or g is None or g.kind != "edit" or g.source != "preset:target":
            return
        num, sel = self.page.rec.selects["preset:target"]
        raw = num.value if typed is None else typed
        res = service.resolve_target_limit(sel.value, raw, self.page.editor.state.domain_basis)
        if res.problem == "whole" or not res.valid:
            self.page.gestures.edit_candidate(None)
            return
        self.page.gestures.edit_candidate(lambda: self.page.editor.set_target_spec(res.spec))

    def on_prescaler_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        parts = cid.split(":")
        i, j = int(parts[3]), int(parts[4])
        out = service.custom_prescaler_entry(self.page.rec.decimal_value(cid), i == j)

        def apply():
            self.page.editor.set_custom_prescaler_entry(i, j, out.value)
            self.page.renderer.request_render()  # the prescaler drives the weighted solve — off the loop

        self.e._commit_outcome(out, apply, _INVALID_PRESCALER)

    def on_weight_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        raws = [
            self.page.rec.decimal_value(o) for o in self.page.rec.inputs if o.startswith("weight:")
        ]
        out = service.custom_weights(raws)

        def apply():
            self.page.editor.set_custom_weights(list(out.value))
            self.page.renderer.request_render()  # the weights drive the tuning solve — off the loop

        self.e._commit_outcome(out, apply, _INVALID_WEIGHT)

    def on_ptext_edit(self, cid, value):
        if self.page.building:
            return
        editor_method = self._PTEXT_EDITORS.get(cid)
        if editor_method is None:
            return
        if not self.page.editor.settings.get("ebk", True):
            value = service.simple_matrix_to_ebk(value, _PTEXT_DUAL_VECTOR_KIND.get(cid, False))
        if getattr(self.page.editor, editor_method)(value):
            self.page.rec.ptext_inputs[cid].classes(remove="rtt-ptext-error")
            self.page.renderer.request_render()  # a typed dual (mapping/commas/tuning/targets/P/G…) retunes — off the loop
            return
        self.page.rec.ptext_inputs[cid].classes(add="rtt-ptext-error")
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
            and service.parse_embedding(value, self.page.editor.state.d, len(self.page.editor.state.mapping))
            is not None
        ):
            return _INVALID_EMBEDDING
        return None
