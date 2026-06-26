from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from nicegui import ui

from rtt.app import (
    ids,
    presets,
    service,
    spreadsheet_text,
    tooltips,
)
from rtt.app._editing_tuning import _TuningEdits
from rtt.app._editing_vectors import _VectorEdits
from rtt.app.page_assets import (
    _INVALID_PRESCALER,
    _INVALID_TEMPERAMENT,
    _INVALID_WEIGHT,
    _TILE_HOST,
    _VecGridEdit,
    cb_method,
)

if TYPE_CHECKING:
    from rtt.app.editor import Editor
    from rtt.app.gestures import GestureController
    from rtt.app.page_runtime import PageRuntime
    from rtt.app.reconciler import _Reconciler
    from rtt.app.rendering import Renderer

_log = logging.getLogger(__name__)


class EditController:
    def __init__(
        self,
        editor: Editor,
        rec: _Reconciler,
        gestures: GestureController,
        renderer: Renderer,
        runtime: PageRuntime,
    ) -> None:
        self._editor = editor
        self._rec = rec
        self._gestures = gestures
        self._renderer = renderer
        self._runtime = runtime
        self.vectors = _VectorEdits(self)
        self.tuning = _TuningEdits(self)

    def _build_edit_specs(self) -> None:
        self._MAPPING_EDIT = _VecGridEdit(
            group="gens",
            count=lambda: len(self._editor.state.mapping),
            cell_id=ids.mapping_cell,
            pending=lambda: self._editor.pending_mapping_row,
            set_pending=self._editor.set_pending_mapping_row,
            commit=self._editor.edit_mapping,
            validate=service.is_proper_temperament,
            guard=lambda: self._editor.settings["temperament_tiles"],
        )
        self._COMMA_EDIT = _VecGridEdit(
            group="commas",
            count=lambda: len(self._editor.state.comma_basis),
            cell_id=ids.comma_cell,
            pending=lambda: self._editor.pending_comma,
            set_pending=self._editor.set_pending_comma,
            commit=self._editor.edit_comma_basis,
            validate=lambda basis: service.is_proper_temperament(
                service.from_comma_basis(basis).mapping
            ),
        )

    def _build_vector_list_specs(self) -> None:
        self._INTEREST_EDIT = _VecGridEdit(
            group="interest",
            count=lambda: len(self._editor.interest_vectors),
            cell_id=ids.interest_cell,
            pending=lambda: self._editor.pending_interest,
            set_pending=self._editor.set_pending_interest,
            commit=self._editor.set_interest_vectors,
            draft_arms=True,
        )
        self._HELD_EDIT = _VecGridEdit(
            group="held",
            count=lambda: len(self._editor.held_vectors),
            cell_id=ids.held_cell,
            pending=lambda: self._editor.pending_held,
            set_pending=self._editor.set_pending_held,
            commit=self._editor.set_held_vectors,
            draft_arms=True,
        )
        self._TARGET_EDIT = _VecGridEdit(
            group="targets",
            count=lambda: len(
                self._editor.target_override
                or service.target_interval_set(
                    self._editor.target_spec, self._editor.state.domain_basis
                )
            ),
            cell_id=ids.target_cell,
            pending=lambda: self._editor.pending_target,
            set_pending=self._editor.set_pending_target,
            commit=self._editor.set_target_override_vectors,
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

    def _reason_message(self, reason):
        if reason is service.Reason.INVALID_PRESCALER:
            return _INVALID_PRESCALER
        if reason is service.Reason.INVALID_WEIGHT:
            return _INVALID_WEIGHT
        if reason is service.Reason.TARGET_WHOLE:
            return tooltips.target_limit_help("whole")
        if reason is service.Reason.TARGET_ODD:
            return tooltips.target_limit_help("odd")
        return None

    def _apply_outcome(self, out, commit, preview=False) -> None:
        if preview:
            self._gestures.edit_candidate(commit if out.effect is service.Effect.ACCEPT else None)
            return
        if out.effect is service.Effect.IGNORE:
            return
        if out.effect is service.Effect.RERENDER:
            self._renderer.render()
            return
        msg = out.message or self._reason_message(out.reason)
        if out.effect is service.Effect.REJECT:
            ui.notify(msg, type="negative", position="top")
            self._renderer.render()
            return
        if msg:
            ui.notify(msg, type="negative", position="top")
        commit()
        self._renderer.request_render()

    @cb_method
    def act(self, action):
        self._gestures.end_commit_gestures()
        action()
        self._renderer.request_render()

    @cb_method
    def add_interval(self, action, group):
        self._gestures.end_commit_gestures()
        action()
        self._renderer.render()
        quant_id, vec_kind = self.draft_focus[group]
        lay = self._runtime.last_lay
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
        inp = self._rec.handles(target).value.input if target is not None else None
        if inp is not None:
            self._focus_draft_cell(inp)

    def _focus_draft_cell(self, inp) -> None:
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
            f"band=body.querySelector('.rtt-rowband'),bw=band?band.getBoundingClientRect().width:0,pl=24,pt=8;"
            f"if(cr.left<br.left+bw+pl)body.scrollLeft-=br.left+bw+pl-cr.left;"
            f"else if(cr.right>br.right-pl)body.scrollLeft+=cr.right-br.right+pl;"
            f"if(cr.top<br.top+pt)body.scrollTop-=br.top+pt-cr.top;"
            f"else if(cr.bottom>br.bottom-pt)body.scrollTop+=cr.bottom-br.bottom+pt;}}return;}}"
            f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()"
        )

    def on_show_toggle(self, key, value):
        if self._runtime.building:
            return
        if key == "nonstandard_domain" and not value and self._editor.basis_is_nonstandard:
            self._editor.exit_nonstandard_domain()
            self._renderer.render()
            return
        self._editor.set_show(key, value)
        self._renderer.render()

    def on_select_all(self, value):
        if self._runtime.building:
            return
        self._editor.set_all_show(value, self._runtime.available_keys())
        self._renderer.render()

    def on_part_click(self, key):
        if self._runtime.building:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not self._editor.settings[host]:
            return
        self._editor.set_show(key, not self._editor.settings[key])
        self._renderer.render()

    @cb_method
    def on_preset(self, cid, value):
        if self._runtime.building:
            return
        if cid.startswith("preset:temperament"):
            if value in presets.TEMPERAMENT_COMMAS:
                self._gestures.end_gesture()
                self._editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
                self._renderer.request_render()
            else:
                self._renderer.render()
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self._gestures.end_chooser_gesture()
            apply()
            self._renderer.request_render()

    @cb_method
    def on_subpick(self, cid, value):
        if self._runtime.building or value is None:
            return
        self._gestures.end_gesture()
        db = self._editor.state.domain_basis
        if cid == "etpick:draft":
            self._editor.set_pending_mapping_row(list(presets.et_value_to_val(value, db)))
            ok = self._editor.pending_mapping_row is None
        elif cid == "commapick:draft":
            self._editor.set_pending_comma(list(presets.comma_value_to_vector(value, db)))
            ok = self._editor.pending_comma is None
        elif cid.startswith("etpick:"):
            i = self._runtime.token_index(cid, "gens")
            ok = i is not None and self._editor.set_mapping_row(
                i, presets.et_value_to_val(value, db)
            )
        else:
            c = self._runtime.token_index(cid, "commas")
            ok = c is not None and self._editor.set_comma(
                c, presets.comma_value_to_vector(value, db)
            )
        if not ok:
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
        self._renderer.render()

    @cb_method
    def on_form_choose(self, cid, value):
        if self._runtime.building:
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self._gestures.end_chooser_gesture()
            apply()
            self._renderer.request_render()

    @cb_method
    def on_target_change(self):
        if self._runtime.building:
            return
        self._gestures.end_chooser_gesture()
        num, sel = self._rec.cells["preset:target"].chooser.select
        out = service.resolve_target_limit(sel.value, num.value, self._editor.state.domain_basis)
        self._apply_outcome(out, lambda: self._editor.set_target_spec(out.value))

    @cb_method
    def on_control_select(self, cid, value):
        if self._runtime.building or value is None:
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self._gestures.end_chooser_gesture()
            apply()
        elif cid == "control:diminuator":
            self._editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":
            self._editor.set_all_interval(bool(value))
        else:
            return
        self._renderer.request_render()

    @cb_method
    def on_range_mode(self, value):
        if self._runtime.building or value is None:
            return
        self._editor.set_range_mode(value)
        self._renderer.render()

    @cb_method
    def on_toggle(self, item):
        self._editor.toggle_collapsed(item)
        self._renderer.render()

    @cb_method
    def on_toggle_all(self):
        self._editor.set_collapsed(
            spreadsheet_text.toggle_all_collapsed(self._runtime.last_lay, self._editor.collapsed)
        )
        self._renderer.render()

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
                return lambda v=value, s=setter: getattr(self._editor, s)(v)
        if cid == "control:complexity":
            return self._complexity_apply(value)
        if cid.startswith("formchooser:"):
            return self._formchooser_apply(cid, value)
        return None

    def _complexity_apply(self, value):
        if value == "custom":
            return None
        internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
        return lambda: self._editor.set_complexity_name(internal)

    def _formchooser_apply(self, cid, value):
        name = cid.split(":", 1)[1]
        if name == "mapping":
            if value not in service.MAPPING_FORM_KEYS:
                return None
            return lambda: self._editor.set_mapping_form(value)
        if value not in service.COMMA_BASIS_FORM_KEYS:
            return None
        return lambda: self._editor.set_comma_basis_form(value)
