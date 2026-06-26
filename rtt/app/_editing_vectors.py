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

    @cb_method
    def on_mapping_change(self, preview=False):
        _edit_vector_grid(self.e, self.e._MAPPING_EDIT, preview)

    @cb_method
    def on_form_change(self, preview=False):
        _form_change(self.e, preview)

    @cb_method
    def on_comma_change(self, preview=False):
        _edit_vector_grid(self.e, self.e._COMMA_EDIT, preview)

    @cb_method
    def on_unchanged_change(self, preview=False):
        _unchanged_change(self.e, preview)

    @cb_method
    def on_interest_change(self, preview=False):
        _edit_vector_grid(self.e, self.e._INTEREST_EDIT, preview)

    @cb_method
    def on_held_change(self, preview=False):
        _edit_vector_grid(self.e, self.e._HELD_EDIT, preview)

    @cb_method
    def on_target_cells_change(self, preview=False):
        _edit_vector_grid(self.e, self.e._TARGET_EDIT, preview)

    @cb_method
    def on_ratio_change(self, cid):
        _ratio_change(self.e, cid)

    @cb_method
    def transform_interval(self, cid, op):
        _transform_interval(self.e, cid, op)

    @cb_method
    def on_element_change(self, cid):
        _element_change(self.e, cid)

    @cb_method
    def on_element_preview(self, cid):
        _element_preview(self.e, cid)


def _edit_pending_vector(ec, spec, preview, toks, d) -> None:
    cell_id = spec.cell_id
    pt = spreadsheet_text.pending_token(toks)
    if any(ec._rec.handles(cell_id(pt, p)).value.input is None for p in range(d)):
        if preview:
            ec._gestures.edit_candidate(None)
        return
    values = [_parse_int(ec._rec.cells[cell_id(pt, p)].value.input.value) for p in range(d)]
    if preview:
        ec._gestures.edit_candidate(
            (lambda v=values: spec.set_pending(v)) if spec.draft_arms else None
        )
        return
    spec.set_pending(values)
    if spec.pending() is None:
        ec._renderer.request_render(after=ec._gestures.rebase_edit_gesture)


def _edit_vector_grid(ec, spec, preview=False):
    if ec._runtime.building or (spec.guard is not None and not spec.guard()):
        return
    d = ec._editor.state.d
    toks = ec._runtime.col_tokens(spec.group)
    if spec.pending() is not None:
        _edit_pending_vector(ec, spec, preview, toks, d)
        return
    cell_id = spec.cell_id
    count = spec.count()
    if len(toks) != count or any(
        ec._rec.handles(cell_id(toks[i], p)).value.input is None
        for i in range(count)
        for p in range(d)
    ):
        ec._apply_outcome(service.IGNORE, None, preview=preview)
        return
    vectors = [
        [_parse_int(ec._rec.cells[cell_id(toks[i], p)].value.input.value) for p in range(d)]
        for i in range(count)
    ]
    if any(v is None for vec in vectors for v in vec):
        ec._apply_outcome(service.IGNORE, None, preview=preview)
        return
    if spec.validate is not None and not spec.validate(vectors):
        ec._apply_outcome(service.reject(_INVALID_TEMPERAMENT), None, preview=preview)
        return
    ec._apply_outcome(service.accept(), lambda: spec.commit(vectors), preview=preview)


def _form_change(ec, preview=False):
    if ec._runtime.building or not ec._editor.settings.get("form_tiles"):
        return
    r = len(ec._editor.state.mapping)
    rc = len(service.canonical_mapping(ec._editor.state.mapping))
    if any(
        ec._rec.handles(ids.form_cell(i, j)).value.input is None
        for i in range(r)
        for j in range(rc)
    ):
        ec._apply_outcome(service.IGNORE, None, preview=preview)
        return
    rows = [
        [_parse_int(ec._rec.cells[ids.form_cell(i, j)].value.input.value) for j in range(rc)]
        for i in range(r)
    ]
    if any(v is None for row in rows for v in row):
        ec._apply_outcome(service.IGNORE, None, preview=preview)
        return
    if service.mapping_from_form_matrix(ec._editor.state.mapping, rows) is None:
        ec._apply_outcome(service.reject(_INVALID_FORM), None, preview=preview)
        return
    ec._apply_outcome(service.accept(), lambda: ec._editor.edit_form_matrix(rows), preview=preview)


def _unchanged_change(ec, preview=False):
    if ec._runtime.building:
        return
    d, r = ec._editor.state.d, ec._editor.state.r
    if any(
        ec._rec.handles(ids.unchanged_cell(j, p)).value.input is None
        for j in range(r)
        for p in range(d)
    ):
        ec._apply_outcome(service.IGNORE, None, preview=preview)
        return
    vectors = [
        [_parse_int(ec._rec.cells[ids.unchanged_cell(j, p)].value.input.value) for p in range(d)]
        for j in range(r)
    ]
    if any(v is None for vec in vectors for v in vec):
        ec._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
        return
    try:
        ratios = service.comma_ratios(
            tuple(tuple(v) for v in vectors), ec._editor.state.domain_basis
        )
    except (ValueError, ZeroDivisionError, ArithmeticError):
        ec._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
        return
    ec._apply_outcome(
        service.accept(), lambda: ec._editor.set_unchanged_basis(ratios), preview=preview
    )


def _ratio_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    group, tok = cid.split(":")
    out = service.resolve_ratio_edit(
        ec._rec.cell_value(cid),
        ec._editor.state.d,
        ec._editor.state.domain_basis,
    )
    ec._apply_outcome(out, lambda: _apply_ratio_edit(ec, group, tok, out.value))


def _replace_interval_vector(ec, group, tok, vector, current, setter) -> None:
    list_name = {
        "target": "targets",
        "held": "held",
        "interest": "interest",
        "comma": "commas",
    }.get(group)
    toks = ec._runtime.col_tokens(list_name) if list_name else []
    pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
    vectors = [list(v) for v in current]
    if vectors[pos] != list(vector):
        vectors[pos] = vector
        setter(vectors)


def _apply_ratio_edit(ec, group, tok, vector) -> None:
    if tok == "pending":
        {
            "comma": ec._editor.set_pending_comma,
            "interest": ec._editor.set_pending_interest,
            "held": ec._editor.set_pending_held,
            "target": ec._editor.set_pending_target,
        }[group](vector)
    elif group == "comma":
        _replace_interval_vector(
            ec, group, tok, vector, ec._editor.state.comma_basis, ec._editor.edit_comma_basis
        )
    elif group == "interest":
        _replace_interval_vector(
            ec, group, tok, vector, ec._editor.interest_vectors, ec._editor.set_interest_vectors
        )
    elif group == "held":
        _replace_interval_vector(
            ec, group, tok, vector, ec._editor.held_vectors, ec._editor.set_held_vectors
        )
    elif group == "unchanged":
        ratios = [
            ec._rec.cell_value(f"unchanged:{j}")
            for j in range(ec._editor.state.r)
            if ec._rec.handles(f"unchanged:{j}").value.input is not None
        ]
        if len(ratios) == ec._editor.state.r and all(ratios):
            ec._editor.set_unchanged_basis(tuple(ratios))
    else:
        targets = ec._editor.target_override or service.target_interval_set(
            ec._editor.target_spec, ec._editor.state.domain_basis
        )
        _replace_interval_vector(
            ec,
            group,
            tok,
            vector,
            service.target_interval_vectors(
                targets, ec._editor.state.d, ec._editor.state.domain_basis
            ),
            ec._editor.set_target_override_vectors,
        )


def _transform_domain_element(ec, cid, op, index) -> None:
    out = service.resolve_domain_element_transform(
        ec._editor.state, index, ec._rec.cell_value(cid), op
    )
    ec._apply_outcome(out, lambda: _apply_domain_element(ec, str(index), out.value))


def _interval_group_state(ec, group):
    if group == "comma":
        return ec._editor.state.comma_basis, ec._editor.edit_comma_basis, "commas"
    if group == "target":
        targets = ec._editor.target_override or service.target_interval_set(
            ec._editor.target_spec, ec._editor.state.domain_basis
        )
        current = service.target_interval_vectors(
            targets, ec._editor.state.d, ec._editor.state.domain_basis
        )
        return current, ec._editor.set_target_override_vectors, "targets"
    if group == "held":
        return ec._editor.held_vectors, ec._editor.set_held_vectors, "held"
    return ec._editor.interest_vectors, ec._editor.set_interest_vectors, "interest"


def _transform_interval(ec, cid, op):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    group, tok = cid.split(":")
    if group not in ("comma", "target", "held", "interest", "prime") or tok == "pending":
        return
    ec._gestures.end_commit_gestures()
    if group == "prime":
        _transform_domain_element(ec, cid, op, int(tok))
        return
    current, setter, list_name = _interval_group_state(ec, group)
    toks = ec._runtime.col_tokens(list_name)
    pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
    if not 0 <= pos < len(current):
        return
    new_v = service.transformed_vector(current[pos], op, ec._editor.state.domain_basis)
    if new_v is None:
        return
    vectors = [list(x) for x in current]
    vectors[pos] = list(new_v)
    setter(vectors)
    ec._renderer.request_render()


def _apply_domain_element(ec, tok: str, raw: str) -> None:
    if tok == "pending":
        ec._editor.set_pending_element(raw)
    else:
        ec._editor.set_domain_element(int(tok), raw)


def _element_change(ec, cid):
    if ec._runtime.building or ec._rec.handles(cid).value.input is None:
        return
    raw = ec._rec.cell_value(cid)
    tok = cid.split(":")[1]
    out = service.resolve_domain_element_edit(ec._editor.state, tok, raw)
    ec._apply_outcome(out, lambda: _apply_domain_element(ec, tok, raw))


def _element_preview(ec, cid):
    g = ec._gestures.gesture
    if (
        ec._runtime.building
        or g is None
        or g.kind != "edit"
        or g.source != cid
        or ec._rec.handles(cid).value.input is None
    ):
        return
    raw = ec._rec.cell_value(cid)
    tok = cid.split(":")[1]
    out = service.resolve_domain_element_edit(ec._editor.state, tok, raw)
    ec._apply_outcome(out, lambda: _apply_domain_element(ec, tok, raw), preview=True)
