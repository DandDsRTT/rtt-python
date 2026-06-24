from __future__ import annotations

from rtt.app import (
    ids,
    service,
    spreadsheet_text,
)
from rtt.app.page_assets import (
    _INVALID_FORM,
    _INVALID_TEMPERAMENT,
    _INVALID_UNCHANGED,
    cb_method,
)
from rtt.app.render_html import (
    _parse_int,
)


class _VectorEdits:
    def __init__(self, e) -> None:
        self.e = e
        self.page = e.page

    def _edit_pending_vector(self, spec, preview, toks, d) -> None:
        cell_id = spec.cell_id
        pt = spreadsheet_text.pending_token(toks)
        if any(self.page.rec.handles(cell_id(pt, p)).value.input is None for p in range(d)):
            if preview:
                self.page.gestures.edit_candidate(None)
            return
        values = [_parse_int(self.page.rec.cells[cell_id(pt, p)].value.input.value) for p in range(d)]
        if preview:
            self.page.gestures.edit_candidate(
                (lambda v=values: spec.set_pending(v)) if spec.draft_arms else None
            )
            return
        spec.set_pending(values)
        if spec.pending() is None:
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
            self.page.rec.handles(cell_id(toks[i], p)).value.input is None
            for i in range(count)
            for p in range(d)
        ):
            self.e._apply_outcome(service.IGNORE, None, preview=preview)
            return
        vectors = [
            [_parse_int(self.page.rec.cells[cell_id(toks[i], p)].value.input.value) for p in range(d)]
            for i in range(count)
        ]
        if any(v is None for vec in vectors for v in vec):
            self.e._apply_outcome(service.IGNORE, None, preview=preview)
            return
        if spec.validate is not None and not spec.validate(vectors):
            self.e._apply_outcome(service.reject(_INVALID_TEMPERAMENT), None, preview=preview)
            return
        self.e._apply_outcome(service.accept(), lambda: spec.commit(vectors), preview=preview)

    @cb_method
    def on_mapping_change(self, preview=False):
        self._edit_vector_grid(self.e._MAPPING_EDIT, preview)

    @cb_method
    def on_form_change(self, preview=False):
        if self.page.building or not self.page.editor.settings.get("form_tiles"):
            return
        r = len(self.page.editor.state.mapping)
        rc = len(service.canonical_mapping(self.page.editor.state.mapping))
        if any(
            self.page.rec.handles(ids.form_cell(i, j)).value.input is None
            for i in range(r)
            for j in range(rc)
        ):
            self.e._apply_outcome(service.IGNORE, None, preview=preview)
            return
        rows = [
            [_parse_int(self.page.rec.cells[ids.form_cell(i, j)].value.input.value) for j in range(rc)]
            for i in range(r)
        ]
        if any(v is None for row in rows for v in row):
            self.e._apply_outcome(service.IGNORE, None, preview=preview)
            return
        if service.mapping_from_form_matrix(self.page.editor.state.mapping, rows) is None:
            self.e._apply_outcome(service.reject(_INVALID_FORM), None, preview=preview)
            return
        self.e._apply_outcome(
            service.accept(), lambda: self.page.editor.edit_form_matrix(rows), preview=preview
        )

    @cb_method
    def on_comma_change(self, preview=False):
        self._edit_vector_grid(self.e._COMMA_EDIT, preview)

    @cb_method
    def on_unchanged_change(self, preview=False):
        if self.page.building:
            return
        d, r = self.page.editor.state.d, self.page.editor.state.r
        if any(
            self.page.rec.handles(ids.unchanged_cell(j, p)).value.input is None
            for j in range(r)
            for p in range(d)
        ):
            self.e._apply_outcome(service.IGNORE, None, preview=preview)
            return
        vectors = [
            [
                _parse_int(self.page.rec.cells[ids.unchanged_cell(j, p)].value.input.value)
                for p in range(d)
            ]
            for j in range(r)
        ]
        if any(v is None for vec in vectors for v in vec):
            self.e._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
            return
        try:
            ratios = service.comma_ratios(
                tuple(tuple(v) for v in vectors), self.page.editor.state.domain_basis
            )
        except (ValueError, ZeroDivisionError, ArithmeticError):
            self.e._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
            return
        self.e._apply_outcome(
            service.accept(), lambda: self.page.editor.set_unchanged_basis(ratios), preview=preview
        )

    @cb_method
    def on_interest_change(self, preview=False):
        self._edit_vector_grid(self.e._INTEREST_EDIT, preview)

    @cb_method
    def on_held_change(self, preview=False):
        self._edit_vector_grid(self.e._HELD_EDIT, preview)

    @cb_method
    def on_target_cells_change(self, preview=False):
        self._edit_vector_grid(self.e._TARGET_EDIT, preview)

    @cb_method
    def on_ratio_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        group, tok = cid.split(":")
        out = service.resolve_ratio_edit(
            self.page.rec.cell_value(cid),
            self.page.editor.state.d,
            self.page.editor.state.domain_basis,
        )

        self.e._apply_outcome(out, lambda: self._apply_ratio_edit(group, tok, out.value))

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
                group,
                tok,
                vector,
                self.page.editor.state.comma_basis,
                self.page.editor.edit_comma_basis,
            )
        elif group == "interest":
            self._replace_interval_vector(
                group,
                tok,
                vector,
                self.page.editor.interest_vectors,
                self.page.editor.set_interest_vectors,
            )
        elif group == "held":
            self._replace_interval_vector(
                group, tok, vector, self.page.editor.held_vectors, self.page.editor.set_held_vectors
            )
        elif group == "unchanged":
            ratios = [
                self.page.rec.cell_value(f"unchanged:{j}")
                for j in range(self.page.editor.state.r)
                if self.page.rec.handles(f"unchanged:{j}").value.input is not None
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

    def _transform_domain_element(self, cid, op, index) -> None:
        out = service.resolve_domain_element_transform(
            self.page.editor.state, index, self.page.rec.cell_value(cid), op
        )
        self.e._apply_outcome(out, lambda: self._apply_domain_element(str(index), out.value))

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

    @cb_method
    def transform_interval(self, cid, op):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        group, tok = cid.split(":")
        if group not in ("comma", "target", "held", "interest", "prime") or tok == "pending":
            return
        self.page.gestures.end_commit_gestures()
        if group == "prime":
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

    @cb_method
    def on_element_change(self, cid):
        if self.page.building or self.page.rec.handles(cid).value.input is None:
            return
        raw = self.page.rec.cell_value(cid)
        tok = cid.split(":")[1]
        out = service.resolve_domain_element_edit(self.page.editor.state, tok, raw)
        self.e._apply_outcome(out, lambda: self._apply_domain_element(tok, raw))

    @cb_method
    def on_element_preview(self, cid):
        g = self.page.gestures.gesture
        if (
            self.page.building
            or g is None
            or g.kind != "edit"
            or g.source != cid
            or self.page.rec.handles(cid).value.input is None
        ):
            return
        raw = self.page.rec.cell_value(cid)
        tok = cid.split(":")[1]
        out = service.resolve_domain_element_edit(self.page.editor.state, tok, raw)
        self.e._apply_outcome(out, lambda: self._apply_domain_element(tok, raw), preview=True)
