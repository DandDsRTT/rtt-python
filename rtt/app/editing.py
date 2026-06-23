from __future__ import annotations

import asyncio
import logging
from typing import ClassVar

from nicegui import background_tasks, ui

from rtt.app import (
    ids,
    presets,
    service,
    spreadsheet_text,
    tooltips,
)
from rtt.app.render_html import (
    _parse_int,
    _wheel_step,
)


from rtt.app.page_assets import (
    _INVALID_TEMPERAMENT,
    _INVALID_FORM,
    _INVALID_PROJECTION,
    _INVALID_EMBEDDING,
    _INVALID_PRESCALER,
    _INVALID_WEIGHT,
    _INVALID_UNCHANGED,
    _WHEEL_STEPS,
    _TARGET_LIMIT_DEBOUNCE,
    _VecGridEdit,
    _PTEXT_DUAL_VECTOR_KIND,
    _TILE_HOST,
)

_log = logging.getLogger(__name__)


class EditController:
    def __init__(self, page) -> None:
        self.page = page
        self.target_limit_commit = None
        # the edit specs read self.page.editor eagerly (set_pending / commit), so they are built
        # by _Page.__init__ after _load_document creates the editor, not here at construction.

    def _build_edit_specs(self) -> None:
        self._MAPPING_EDIT = _VecGridEdit(
            group="gens",
            count=lambda: len(self.page.editor.state.mapping),
            cell_id=ids.mapping_cell,
            pending=lambda: self.page.editor.pending_mapping_row,
            set_pending=self.page.editor.set_pending_mapping_row,
            commit=self.page.editor.edit_mapping,
            validate=service.is_proper_temperament,
            guard=lambda: self.page.editor.settings["temperament_tiles"],
        )
        self._COMMA_EDIT = _VecGridEdit(
            group="commas",
            count=lambda: len(self.page.editor.state.comma_basis),
            cell_id=ids.comma_cell,
            pending=lambda: self.page.editor.pending_comma,
            set_pending=self.page.editor.set_pending_comma,
            commit=self.page.editor.edit_comma_basis,
            validate=lambda basis: service.is_proper_temperament(
                service.from_comma_basis(basis).mapping
            ),
        )

    def _build_vector_list_specs(self) -> None:
        self._INTEREST_EDIT = _VecGridEdit(
            group="interest",
            count=lambda: len(self.page.editor.interest_vectors),
            cell_id=ids.interest_cell,
            pending=lambda: self.page.editor.pending_interest,
            set_pending=self.page.editor.set_pending_interest,
            commit=self.page.editor.set_interest_vectors,
            draft_arms=True,
        )
        self._HELD_EDIT = _VecGridEdit(
            group="held",
            count=lambda: len(self.page.editor.held_vectors),
            cell_id=ids.held_cell,
            pending=lambda: self.page.editor.pending_held,
            set_pending=self.page.editor.set_pending_held,
            commit=self.page.editor.set_held_vectors,
            draft_arms=True,
        )
        self._TARGET_EDIT = _VecGridEdit(
            group="targets",
            count=lambda: len(
                self.page.editor.target_override
                or service.target_interval_set(
                    self.page.editor.target_spec, self.page.editor.state.domain_basis
                )
            ),
            cell_id=ids.target_cell,
            pending=lambda: self.page.editor.pending_target,
            set_pending=self.page.editor.set_pending_target,
            commit=self.page.editor.set_target_override_vectors,
            draft_arms=True,
        )

        self.draft_focus = {
            "comma": ("comma:pending", "commacell"),
            "target": ("target:pending", "targetcell"),
            "held": ("held:pending", "heldcell"),
            "interest": ("interest:pending", "interestcell"),
            "element": ("prime:pending", None),
            "mapping": (None, "mapping"),
        }

    _CB_METHODS: ClassVar[tuple[str, ...]] = (
        "act",
        "add_interval",
        "combine_begin",
        "combine_preview",
        "combine_commit",
        "combine_end",
        "control_hover",
        "control_unhover",
        "rank_remove_hover",
        "rank_remove_unhover",
        "gentuning_hover",
        "gentuning_unhover",
        "on_cell_blur",
        "on_cell_focus",
        "on_popup",
        "on_comma_change",
        "on_unchanged_change",
        "on_drag_start",
        "on_drag_enter",
        "on_drag_end",
        "on_drop",
        "on_control_select",
        "on_form_choose",
        "on_gentuning_change",
        "on_gentuning_wheel",
        "on_value_wheel",
        "on_target_limit_wheel",
        "on_target_limit_preview",
        "on_chooser_hover",
        "on_held_change",
        "on_interest_change",
        "on_mapping_change",
        "on_form_change",
        "on_power_change",
        "on_prescaler_change",
        "on_weight_change",
        "on_preset",
        "on_subpick",
        "on_ptext_edit",
        "on_ratio_change",
        "transform_interval",
        "on_element_change",
        "on_element_preview",
        "on_range_mode",
        "on_target_cells_change",
        "on_target_change",
        "on_toggle",
        "on_toggle_all",
    )

    def _finish_edit(self, preview, outcome) -> None:
        # outcome is ("incomplete",) | ("invalid", message) | ("ok", commit). A preview arms the
        # candidate (the commit itself when ok, else nothing); a real edit commits / notifies / no-ops.
        if preview:
            self.page.gestures.edit_candidate(outcome[1] if outcome[0] == "ok" else None)
            return
        if outcome[0] == "invalid":
            ui.notify(outcome[1], type="negative", position="top")
            self.page.renderer.render()
        elif outcome[0] == "ok":
            outcome[1]()
            self.page.renderer.request_render()

    def _edit_pending_vector(self, spec, preview, toks, d) -> None:
        cell_id = spec.cell_id
        pt = spreadsheet_text.pending_token(toks)
        if any(cell_id(pt, p) not in self.page.rec.inputs for p in range(d)):
            if preview:
                self.page.gestures.edit_candidate(None)
            return
        values = [_parse_int(self.page.rec.inputs[cell_id(pt, p)].value) for p in range(d)]
        if preview:
            self.page.gestures.edit_candidate(
                (lambda v=values: spec.set_pending(v)) if spec.draft_arms else None
            )
            return
        spec.set_pending(values)
        if spec.pending() is None:
            # the change is applied (it retunes) — render OFF the loop, then rebase the gesture
            # on the fresh layout so its rings go away NOW (no blur fires)
            self.page.renderer.request_render(after=self.page.gestures.rebase_edit_gesture)

    def _edit_vector_grid(self, spec, preview=False):
        if self.page.building or (spec.guard is not None and not spec.guard()):
            return
        d = self.page.editor.state.d
        toks = self.page.col_tokens(spec.group)
        if spec.pending() is not None:
            self._edit_pending_vector(spec, preview, toks, d)
            return
        cell_id = spec.cell_id
        count = spec.count()
        if len(toks) != count or any(
            cell_id(toks[i], p) not in self.page.rec.inputs for i in range(count) for p in range(d)
        ):
            self._finish_edit(preview, ("incomplete",))
            return
        vectors = [
            [_parse_int(self.page.rec.inputs[cell_id(toks[i], p)].value) for p in range(d)]
            for i in range(count)
        ]
        if any(v is None for vec in vectors for v in vec):
            self._finish_edit(preview, ("incomplete",))
            return
        if spec.validate is not None and not spec.validate(vectors):
            self._finish_edit(preview, ("invalid", _INVALID_TEMPERAMENT))
            return
        self._finish_edit(preview, ("ok", lambda: spec.commit(vectors)))

    def on_mapping_change(self, preview=False):
        self._edit_vector_grid(self._MAPPING_EDIT, preview)

    def on_form_change(self, preview=False):
        if self.page.building or not self.page.editor.settings.get("form_tiles"):
            return
        r = len(self.page.editor.state.mapping)
        rc = len(service.canonical_mapping(self.page.editor.state.mapping))
        if any(ids.form_cell(i, j) not in self.page.rec.inputs for i in range(r) for j in range(rc)):
            if preview:
                self.page.gestures.edit_candidate(None)
            return
        rows = [
            [_parse_int(self.page.rec.inputs[ids.form_cell(i, j)].value) for j in range(rc)]
            for i in range(r)
        ]
        if any(v is None for row in rows for v in row):
            if preview:
                self.page.gestures.edit_candidate(None)
            return
        if service.mapping_from_form_matrix(self.page.editor.state.mapping, rows) is None:
            if preview:
                self.page.gestures.edit_candidate(None)
                return
            ui.notify(_INVALID_FORM, type="negative", position="top")
            self.page.renderer.render()
            return
        if preview:
            self.page.gestures.edit_candidate(lambda: self.page.editor.edit_form_matrix(rows))
            return
        self.page.editor.edit_form_matrix(rows)
        self.page.renderer.request_render()  # a form change re-stores the mapping (a new generating set) — render off the loop

    def on_comma_change(self, preview=False):
        self._edit_vector_grid(self._COMMA_EDIT, preview)

    def on_unchanged_change(self, preview=False):
        if self.page.building:
            return
        d, r = self.page.editor.state.d, self.page.editor.state.r
        if any(ids.unchanged_cell(j, p) not in self.page.rec.inputs for j in range(r) for p in range(d)):
            self._finish_edit(preview, ("incomplete",))
            return
        vectors = [
            [_parse_int(self.page.rec.inputs[ids.unchanged_cell(j, p)].value) for p in range(d)]
            for j in range(r)
        ]
        if any(v is None for vec in vectors for v in vec):
            self._finish_edit(preview, ("invalid", _INVALID_UNCHANGED))
            return
        try:
            ratios = service.comma_ratios(
                tuple(tuple(v) for v in vectors), self.page.editor.state.domain_basis
            )
        except (ValueError, ZeroDivisionError, ArithmeticError):
            self._finish_edit(preview, ("invalid", _INVALID_UNCHANGED))
            return
        self._finish_edit(preview, ("ok", lambda: self.page.editor.set_unchanged_basis(ratios)))

    def on_interest_change(self, preview=False):
        self._edit_vector_grid(self._INTEREST_EDIT, preview)

    def on_held_change(self, preview=False):
        self._edit_vector_grid(self._HELD_EDIT, preview)

    def on_target_cells_change(self, preview=False):
        self._edit_vector_grid(self._TARGET_EDIT, preview)

    def on_ratio_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        group, tok = cid.split(":")
        out = service.resolve_ratio_edit(
            self.page.rec.cell_value(cid),
            self.page.editor.state.d,
            self.page.editor.state.domain_basis,
        )

        def apply():
            self._apply_ratio_edit(group, tok, out.value)
            # a quantities-row ratio edit routes into a retuning setter (comma/held/target/unchanged)
            # — render off the loop. (An interest edit doesn't retune, but the warm build is cheap.)
            self.page.renderer.request_render()

        self._commit_outcome(out, apply)

    def _replace_interval_vector(self, group, tok, vector, current, setter) -> None:
        list_name = {
            "target": "targets",
            "held": "held",
            "interest": "interest",
            "comma": "commas",
        }.get(group)
        toks = self.page.col_tokens(list_name) if list_name else []
        pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
        vectors = [list(v) for v in current]
        if vectors[pos] != list(vector):
            vectors[pos] = vector
            setter(vectors)

    def _apply_ratio_edit(self, group, tok, vector) -> None:
        if tok == "pending":
            {
                "comma": self.page.editor.set_pending_comma,
                "interest": self.page.editor.set_pending_interest,
                "held": self.page.editor.set_pending_held,
                "target": self.page.editor.set_pending_target,
            }[group](vector)
        elif group == "comma":
            self._replace_interval_vector(
                group, tok, vector, self.page.editor.state.comma_basis, self.page.editor.edit_comma_basis
            )
        elif group == "interest":
            self._replace_interval_vector(
                group, tok, vector, self.page.editor.interest_vectors, self.page.editor.set_interest_vectors
            )
        elif group == "held":
            self._replace_interval_vector(
                group, tok, vector, self.page.editor.held_vectors, self.page.editor.set_held_vectors
            )
        elif group == "unchanged":
            ratios = [
                self.page.rec.cell_value(f"unchanged:{j}")
                for j in range(self.page.editor.state.r)
                if f"unchanged:{j}" in self.page.rec.inputs
            ]
            if len(ratios) == self.page.editor.state.r and all(ratios):
                self.page.editor.set_unchanged_basis(tuple(ratios))
        else:
            targets = self.page.editor.target_override or service.target_interval_set(
                self.page.editor.target_spec, self.page.editor.state.domain_basis
            )
            self._replace_interval_vector(
                group,
                tok,
                vector,
                service.target_interval_vectors(
                    targets, self.page.editor.state.d, self.page.editor.state.domain_basis
                ),
                self.page.editor.set_target_override_vectors,
            )

    def _commit_outcome(self, out, apply, reject_message=None) -> None:
        if out.effect is service.Effect.IGNORE:
            return
        if out.effect is service.Effect.RERENDER:
            self.page.renderer.render()
            return
        if out.effect is service.Effect.REJECT:
            ui.notify(out.message or reject_message, type="negative", position="top")
            self.page.renderer.render()
            return
        if out.message:
            ui.notify(out.message, type="negative", position="top")
        apply()

    def _preview_outcome(self, out, apply) -> None:
        self.page.gestures.edit_candidate(apply if out.effect is service.Effect.ACCEPT else None)

    def _transform_domain_element(self, cid, op, index) -> None:
        out = service.resolve_domain_element_transform(
            self.page.editor.state, index, self.page.rec.cell_value(cid), op
        )
        self._commit_outcome(out, lambda: self._apply_domain_element(str(index), out.value))

    def _interval_group_state(self, group):
        if group == "comma":
            return self.page.editor.state.comma_basis, self.page.editor.edit_comma_basis, "commas"
        if group == "target":
            targets = self.page.editor.target_override or service.target_interval_set(
                self.page.editor.target_spec, self.page.editor.state.domain_basis
            )
            current = service.target_interval_vectors(
                targets, self.page.editor.state.d, self.page.editor.state.domain_basis
            )
            return current, self.page.editor.set_target_override_vectors, "targets"
        if group == "held":
            return self.page.editor.held_vectors, self.page.editor.set_held_vectors, "held"
        return self.page.editor.interest_vectors, self.page.editor.set_interest_vectors, "interest"

    def transform_interval(self, cid, op):
        # the equave-reduce / reciprocate buttons flanking an editable interval ratio (commas / targets
        # / held / interest) or an editable domain basis element (prime). Resolve the cell's value,
        # apply the op, and route it through the SAME setter a manual edit uses — one undo step, every
        # dependent row recomputed. A no-op (already reduced, or a unison reciprocated) commits nothing,
        # so a disabled button is safe.
        if self.page.building or cid not in self.page.rec.inputs:
            return
        group, tok = cid.split(":")
        if group not in ("comma", "target", "held", "interest", "prime") or tok == "pending":
            return
        self.page.gestures.end_commit_gestures()
        if group == "prime":  # relabel a domain basis element to its reduced / reciprocated ratio
            self._transform_domain_element(cid, op, int(tok))
            return
        current, setter, list_name = self._interval_group_state(group)
        toks = self.page.col_tokens(list_name)
        pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
        if not 0 <= pos < len(current):
            return
        new_v = service.transformed_vector(current[pos], op, self.page.editor.state.domain_basis)
        if new_v is None:
            return
        vectors = [list(x) for x in current]
        vectors[pos] = list(new_v)
        setter(vectors)
        self.page.renderer.request_render()

    def _apply_domain_element(self, tok: str, raw: str) -> None:
        if tok == "pending":
            self.page.editor.set_pending_element(raw)
        else:
            self.page.editor.set_domain_element(int(tok), raw)
        self.page.renderer.request_render()  # a new / relabelled domain element retunes — off the loop

    def on_element_change(self, cid):
        if self.page.building or cid not in self.page.rec.inputs:
            return
        raw = self.page.rec.cell_value(cid)
        tok = cid.split(":")[1]
        out = service.resolve_domain_element_edit(self.page.editor.state, tok, raw)
        self._commit_outcome(out, lambda: self._apply_domain_element(tok, raw))

    def on_element_preview(self, cid):
        g = self.page.gestures.gesture
        if (
            self.page.building
            or g is None
            or g.kind != "edit"
            or g.source != cid
            or cid not in self.page.rec.inputs
        ):
            return
        raw = self.page.rec.cell_value(cid)
        tok = cid.split(":")[1]
        out = service.resolve_domain_element_edit(self.page.editor.state, tok, raw)

        def apply():
            if tok == "pending":
                self.page.editor.set_pending_element(raw)
            else:
                self.page.editor.set_domain_element(int(tok), raw)

        self._preview_outcome(out, apply)

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
            "mapping": self.on_mapping_change,
            "commacell": self.on_comma_change,
            "interestcell": self.on_interest_change,
            "heldcell": self.on_held_change,
            "targetcell": self.on_target_cells_change,
            "formcell": self.on_form_change,
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
            self.on_target_change()

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

        self._commit_outcome(out, apply, _INVALID_PRESCALER)

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

        self._commit_outcome(out, apply, _INVALID_WEIGHT)

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

    def act(self, action):
        # the universal click/keyboard commit: end gestures, mutate, then render OFF the loop
        # (_request_render) — most of these actions retune (expand/shrink, undo/redo across an
        # edit, a structural remove, back-to-scheme), so the heavy solve must not block the socket.
        self.page.gestures.end_commit_gestures()
        action()
        self.page.renderer.request_render()

    def add_interval(self, action, group):
        # add the draft column, then focus into it: the quantities ratio cell if its row is shown
        # (the layout emitted it), else the first gridded vector cell (prime 0) of the draft column.
        # A draft add doesn't retune (the pending green vector isn't committed), so its build is
        # light — render SYNCHRONOUSLY (not the off-loop _request_render) so last_lay is current for
        # the focus hand-off below, which reads the just-built layout.
        self.page.gestures.end_commit_gestures()
        action()
        self.page.renderer.render()
        quant_id, vec_kind = self.draft_focus[group]
        lay = self.page.last_lay
        if any(cb.id == quant_id for cb in lay.cells):
            target = quant_id
        elif vec_kind is not None:
            target = next(
                (cb.id for cb in lay.cells if cb.pending and cb.prime == 0 and cb.kind == vec_kind),
                None,
            )
        else:
            target = None
        if target is None and group == "element":
            target = next((cb.id for cb in lay.cells if cb.id == "basis:pending"), None)
        inp = self.page.rec.inputs.get(target) if target is not None else None
        if inp is not None:
            self._focus_draft_cell(inp)

    def _focus_draft_cell(self, inp) -> None:
        # Focus into the freshly-created draft cell AND select its contents, so the "?" placeholder
        # the draft starts with is highlighted — the first keystroke replaces it instead of typing
        # after it (no backspace needed). select() resolves through getElement().$refs.qRef to
        # QInput.select() (a native input.select()); it is a harmless no-op on the empty
        # integer-vector fallback cell. A direct runMethod can lose a race in a real (visible)
        # browser: the cell-create 'update' and this focus message can be delivered in one frame,
        # so the focus runs before Vue has mounted the new cell and populated its $ref — and
        # silently no-ops. So defer to the next macrotask and poll briefly for the mount (getElement
        # returns the ref once it exists). setTimeout works whether the page is visible or hidden —
        # requestAnimationFrame would be paused while hidden (e.g. the render tests / a backgrounded
        # tab), so it is the wrong tool here.
        # The draft cell can be off-screen — a + at a far edge, or an add fired by keyboard while
        # scrolled away. So after focusing, scroll the grid body the minimum that brings the cell
        # fully into view (past the frozen left rowband, clear of the top edge). Setting scrollLeft/
        # Top fires the body's own scroll listener, which re-pins the frozen header (see freeze.js).
        ui.run_javascript(
            f"(function(){{var id={inp.id},n=0;function go(){{var c=getElement(id);"
            f"if(c){{runMethod(id,'focus',[]);runMethod(id,'select',[]);"
            f"var el=document.activeElement,cell=el&&el.closest&&el.closest('.rtt-cell'),"
            f"body=cell&&cell.closest('.rtt-gridbody');"
            f"if(body){{var cr=cell.getBoundingClientRect(),br=body.getBoundingClientRect(),"
            f"band=body.querySelector('.rtt-rowband'),bw=band?band.getBoundingClientRect().width:0,pl=24,pt=8;"
            f"if(cr.left<br.left+bw+pl)body.scrollLeft-=br.left+bw+pl-cr.left;"
            f"else if(cr.right>br.right-pl)body.scrollLeft+=cr.right-br.right+pl;"
            f"if(cr.top<br.top+pt)body.scrollTop-=br.top+pt-cr.top;"
            f"else if(cr.bottom>br.bottom-pt)body.scrollTop+=cr.bottom-br.bottom+pt;}}return;}}"
            f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()"
        )

    def on_show_toggle(self, key, value):
        if self.page.building:
            return
        if key == "nonstandard_domain" and not value and self.page.editor.basis_is_nonstandard:
            self.page.editor.exit_nonstandard_domain()
            self.page.renderer.render()
            return
        self.page.editor.set_show(key, value)
        self.page.renderer.render()

    def on_select_all(self, value):
        if self.page.building:
            return
        self.page.editor.set_all_show(value, self.page._available_keys())
        self.page.renderer.render()

    def on_part_click(self, key):
        if self.page.building:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not self.page.editor.settings[host]:
            return
        self.page.editor.set_show(key, not self.page.editor.settings[key])
        self.page.renderer.render()

    def on_preset(self, cid, value):
        if self.page.building:
            return
        if cid.startswith("preset:temperament"):
            if value in presets.TEMPERAMENT_COMMAS:
                self.page.gestures.end_gesture()
                self.page.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
                self.page.renderer.request_render()  # a loaded temperament retunes — render off the loop
            else:
                self.page.renderer.render()
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self.page.gestures.end_chooser_gesture()
            apply()
            self.page.renderer.request_render()  # a tuning / prescaler preset re-solves — render off the loop

    def on_subpick(self, cid, value):
        if self.page.building or value is None:
            return
        self.page.gestures.end_gesture()
        db = self.page.editor.state.domain_basis
        if cid == "etpick:draft":
            self.page.editor.set_pending_mapping_row(list(presets.et_value_to_val(value, db)))
            ok = self.page.editor.pending_mapping_row is None
        elif cid == "commapick:draft":
            self.page.editor.set_pending_comma(list(presets.comma_value_to_vector(value, db)))
            ok = self.page.editor.pending_comma is None
        elif cid.startswith("etpick:"):
            i = self.page._token_index(cid, "gens")
            ok = i is not None and self.page.editor.set_mapping_row(
                i, presets.et_value_to_val(value, db)
            )
        else:
            c = self.page._token_index(cid, "commas")
            ok = c is not None and self.page.editor.set_comma(
                c, presets.comma_value_to_vector(value, db)
            )
        if not ok:
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
        self.page.renderer.render()

    def on_form_choose(self, cid, value):
        if self.page.building:
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self.page.gestures.end_chooser_gesture()
            apply()
            self.page.renderer.request_render()  # canonicalizing re-keys the tuning solve — render off the loop

    def on_target_change(self):
        if self.page.building:
            return
        self.page.gestures.end_chooser_gesture()
        num, sel = self.page.rec.selects["preset:target"]
        res = service.resolve_target_limit(sel.value, num.value, self.page.editor.state.domain_basis)
        if res.problem == "whole":
            # a non-number is never accepted: toast and re-render, which restores the committed
            # value (the input is loopback-controlled, so the server's value overwrites the garbage)
            ui.notify(tooltips.target_limit_help("whole"), type="negative", position="top")
            self.page.renderer.render()
            return
        if not res.valid:
            return
        if res.problem == "odd":
            ui.notify(tooltips.target_limit_help("odd"), type="negative", position="top")
        self.page.editor.set_target_spec(res.spec)
        self.page.renderer.request_render()  # a new target set re-weights the optimization (retunes) — render off the loop

    def on_control_select(self, cid, value):
        if self.page.building or value is None:
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self.page.gestures.end_chooser_gesture()
            apply()
        elif cid == "control:diminuator":
            self.page.editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":
            self.page.editor.set_all_interval(bool(value))
        else:
            return
        self.page.renderer.request_render()  # a weighting / complexity / all-interval trait change retunes — off the loop

    def on_range_mode(self, value):
        if self.page.building or value is None:
            return
        self.page.editor.set_range_mode(value)
        self.page.renderer.render()

    def on_toggle(self, item):
        self.page.editor.toggle_collapsed(item)
        self.page.renderer.render()

    def on_toggle_all(self):
        self.page.editor.set_collapsed(
            spreadsheet_text.toggle_all_collapsed(self.page.last_lay, self.page.editor.collapsed)
        )
        self.page.renderer.render()

    _APPLY_SETTERS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("preset:tuning", "set_tuning_scheme"),
        ("preset:prescaler", "set_complexity_prescaler"),
        ("preset:projection", "set_established_projection"),
        ("control:slope", "set_weight_slope"),
    )

    def candidate_apply(self, cid, value):
        if value is None:
            return None
        for prefix, setter in self._APPLY_SETTERS:
            if cid.startswith(prefix):
                return lambda v=value, s=setter: getattr(self.page.editor, s)(v)
        if cid == "control:complexity":
            return self._complexity_apply(value)
        if cid.startswith("formchooser:"):
            return self._formchooser_apply(cid, value)
        return None

    def _complexity_apply(self, value):
        if value == "custom":
            return None
        internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
        return lambda: self.page.editor.set_complexity_name(internal)

    def _formchooser_apply(self, cid, value):
        name = cid.split(":", 1)[1]
        if name == "mapping":
            if value not in service.MAPPING_FORM_KEYS:
                return None
            return lambda: self.page.editor.set_mapping_form(value)
        if value not in service.COMMA_BASIS_FORM_KEYS:
            return None
        return lambda: self.page.editor.set_comma_basis_form(value)
