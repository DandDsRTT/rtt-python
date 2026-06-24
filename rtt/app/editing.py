from __future__ import annotations

import logging
from typing import ClassVar

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

_log = logging.getLogger(__name__)


class EditController:
    def __init__(self, page) -> None:
        self.page = page
        self.vectors = _VectorEdits(self)
        self.tuning = _TuningEdits(self)

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

    def _reason_message(self, reason):
        # the ONE place the view phrases a service Reason — fixed view copy (page_assets constants)
        # or view-layer help text (tooltips) the service must not import. Decisions whose wording is
        # derived from the input (parser errors, f-strings over the typed value) ride on
        # Outcome.message instead and never pass through here.
        if reason is service.Reason.INVALID_PRESCALER:
            return _INVALID_PRESCALER
        if reason is service.Reason.INVALID_WEIGHT:
            return _INVALID_WEIGHT
        if reason is service.Reason.TARGET_WHOLE:
            return tooltips.target_limit_help("whole")
        if reason is service.Reason.TARGET_ODD:
            return tooltips.target_limit_help("odd")
        return None

    def _commit_outcome(self, out, apply) -> None:
        if out.effect is service.Effect.IGNORE:
            return
        if out.effect is service.Effect.RERENDER:
            self.page.renderer.render()
            return
        msg = out.message or self._reason_message(out.reason)
        if out.effect is service.Effect.REJECT:
            ui.notify(msg, type="negative", position="top")
            self.page.renderer.render()
            return
        if msg:  # ACCEPT carrying a non-blocking warning (e.g. an even OLD limit)
            ui.notify(msg, type="negative", position="top")
        apply()

    def _preview_outcome(self, out, apply) -> None:
        self.page.gestures.edit_candidate(apply if out.effect is service.Effect.ACCEPT else None)

    @cb_method
    def act(self, action):
        # the universal click/keyboard commit: end gestures, mutate, then render OFF the loop
        # (_request_render) — most of these actions retune (expand/shrink, undo/redo across an
        # edit, a structural remove, back-to-scheme), so the heavy solve must not block the socket.
        self.page.gestures.end_commit_gestures()
        action()
        self.page.renderer.request_render()

    @cb_method
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
        inp = self.page.rec.handles(target).input if target is not None else None
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

    @cb_method
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

    @cb_method
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

    @cb_method
    def on_form_choose(self, cid, value):
        if self.page.building:
            return
        apply = self.candidate_apply(cid, value)
        if apply is not None:
            self.page.gestures.end_chooser_gesture()
            apply()
            self.page.renderer.request_render()  # canonicalizing re-keys the tuning solve — render off the loop

    @cb_method
    def on_target_change(self):
        if self.page.building:
            return
        self.page.gestures.end_chooser_gesture()
        num, sel = self.page.rec.cells["preset:target"].select
        out = service.resolve_target_limit(
            sel.value, num.value, self.page.editor.state.domain_basis
        )
        # a non-number rejects (toast + re-render restores the loopback-controlled field); an even OLD
        # limit accepts but warns; a valid limit accepts; an unrealizable spec is silently ignored.

        def apply():
            self.page.editor.set_target_spec(out.value)
            self.page.renderer.request_render()  # a new target set re-weights the optimization — off the loop

        self._commit_outcome(out, apply)

    @cb_method
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

    @cb_method
    def on_range_mode(self, value):
        if self.page.building or value is None:
            return
        self.page.editor.set_range_mode(value)
        self.page.renderer.render()

    @cb_method
    def on_toggle(self, item):
        self.page.editor.toggle_collapsed(item)
        self.page.renderer.render()

    @cb_method
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
