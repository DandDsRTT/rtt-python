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
    def on_ratio_change(self, cell_id):
        _ratio_change(self.e, cell_id)

    @cb_method
    def transform_interval(self, cell_id, op):
        _transform_interval(self.e, cell_id, op)

    @cb_method
    def on_element_change(self, cell_id):
        _element_change(self.e, cell_id)

    @cb_method
    def on_element_preview(self, cell_id):
        _element_preview(self.e, cell_id)


def _edit_pending_vector(edit_controller, spec, preview, toks, d) -> None:
    cell_id = spec.cell_id
    pt = spreadsheet_text.pending_token(toks)
    if any(edit_controller._rec.handles(cell_id(pt, p)).value.input is None for p in range(d)):
        if preview:
            edit_controller._gestures.edit_candidate(None)
        return
    values = [
        _parse_int(edit_controller._rec.cells[cell_id(pt, p)].value.input.value) for p in range(d)
    ]
    if preview:
        edit_controller._gestures.edit_candidate(
            (lambda v=values: spec.set_pending(v)) if spec.draft_arms else None
        )
        return
    spec.set_pending(values)
    if spec.pending() is None:
        edit_controller._renderer.request_render(
            after=edit_controller._gestures.rebase_edit_gesture
        )


def _edit_vector_grid(edit_controller, spec, preview=False):
    if edit_controller._runtime.building or (spec.guard is not None and not spec.guard()):
        return
    d = edit_controller._editor.state.dimensionality
    toks = edit_controller._runtime.column_tokens(spec.group)
    if spec.pending() is not None:
        _edit_pending_vector(edit_controller, spec, preview, toks, d)
        return
    cell_id = spec.cell_id
    count = spec.count()
    if len(toks) != count or any(
        edit_controller._rec.handles(cell_id(toks[i], p)).value.input is None
        for i in range(count)
        for p in range(d)
    ):
        edit_controller._apply_outcome(service.IGNORE, None, preview=preview)
        return
    vectors = [
        [
            _parse_int(edit_controller._rec.cells[cell_id(toks[i], p)].value.input.value)
            for p in range(d)
        ]
        for i in range(count)
    ]
    if any(v is None for vector in vectors for v in vector):
        edit_controller._apply_outcome(service.IGNORE, None, preview=preview)
        return
    if spec.validate is not None and not spec.validate(vectors):
        edit_controller._apply_outcome(service.reject(_INVALID_TEMPERAMENT), None, preview=preview)
        return
    edit_controller._apply_outcome(service.accept(), lambda: spec.commit(vectors), preview=preview)


def _form_change(edit_controller, preview=False):
    if edit_controller._runtime.building or not edit_controller._editor.settings.get("form_tiles"):
        return
    r = len(edit_controller._editor.state.mapping)
    rc = len(service.canonical_mapping(edit_controller._editor.state.mapping))
    if any(
        edit_controller._rec.handles(ids.form_cell(i, j)).value.input is None
        for i in range(r)
        for j in range(rc)
    ):
        edit_controller._apply_outcome(service.IGNORE, None, preview=preview)
        return
    rows = [
        [
            _parse_int(edit_controller._rec.cells[ids.form_cell(i, j)].value.input.value)
            for j in range(rc)
        ]
        for i in range(r)
    ]
    if any(v is None for row in rows for v in row):
        edit_controller._apply_outcome(service.IGNORE, None, preview=preview)
        return
    if service.mapping_from_form_matrix(edit_controller._editor.state.mapping, rows) is None:
        edit_controller._apply_outcome(service.reject(_INVALID_FORM), None, preview=preview)
        return
    edit_controller._apply_outcome(
        service.accept(), lambda: edit_controller._editor.edit_form_matrix(rows), preview=preview
    )


def _unchanged_change(edit_controller, preview=False):
    if edit_controller._runtime.building:
        return
    d, r = edit_controller._editor.state.dimensionality, edit_controller._editor.state.rank
    if any(
        edit_controller._rec.handles(ids.unchanged_cell(j, p)).value.input is None
        for j in range(r)
        for p in range(d)
    ):
        edit_controller._apply_outcome(service.IGNORE, None, preview=preview)
        return
    vectors = [
        [
            _parse_int(edit_controller._rec.cells[ids.unchanged_cell(j, p)].value.input.value)
            for p in range(d)
        ]
        for j in range(r)
    ]
    if any(v is None for vector in vectors for v in vector):
        edit_controller._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
        return
    try:
        ratios = service.comma_ratios(
            tuple(tuple(v) for v in vectors), edit_controller._editor.state.domain_basis
        )
    except (ValueError, ZeroDivisionError, ArithmeticError):
        edit_controller._apply_outcome(service.reject(_INVALID_UNCHANGED), None, preview=preview)
        return
    edit_controller._apply_outcome(
        service.accept(),
        lambda: edit_controller._editor.set_unchanged_basis(ratios),
        preview=preview,
    )


def _ratio_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    group, token = cell_id.split(":")
    out = service.resolve_ratio_edit(
        edit_controller._rec.cell_value(cell_id),
        edit_controller._editor.state.dimensionality,
        edit_controller._editor.state.domain_basis,
    )
    edit_controller._apply_outcome(
        out, lambda: _apply_ratio_edit(edit_controller, group, token, out.value)
    )


def _replace_interval_vector(edit_controller, group, token, vector, current, setter) -> None:
    list_name = {
        "target": "targets",
        "held": "held",
        "interest": "interest",
        "comma": "commas",
    }.get(group)
    toks = edit_controller._runtime.column_tokens(list_name) if list_name else []
    pos = toks.index(int(token)) if int(token) in toks else int(token)
    vectors = [list(v) for v in current]
    if vectors[pos] != list(vector):
        vectors[pos] = vector
        setter(vectors)


def _apply_ratio_edit(edit_controller, group, token, vector) -> None:
    editor = edit_controller._editor
    if token == "pending":
        {
            "comma": editor.set_pending_comma,
            "interest": editor.set_pending_interest,
            "held": editor.set_pending_held,
            "target": editor.set_pending_target,
        }[group](vector)
    elif group == "comma":
        _replace_interval_vector(
            edit_controller, group, token, vector, editor.state.comma_basis, editor.edit_comma_basis
        )
    elif group == "interest":
        _replace_interval_vector(
            edit_controller,
            group,
            token,
            vector,
            editor.interest_vectors,
            editor.set_interest_vectors,
        )
    elif group == "held":
        _replace_interval_vector(
            edit_controller, group, token, vector, editor.held_vectors, editor.set_held_vectors
        )
    elif group == "unchanged":
        ratios = [
            edit_controller._rec.cell_value(f"unchanged:{j}")
            for j in range(editor.state.rank)
            if edit_controller._rec.handles(f"unchanged:{j}").value.input is not None
        ]
        if len(ratios) == editor.state.rank and all(ratios):
            editor.set_unchanged_basis(tuple(ratios))
    else:
        targets = editor.target_override or service.target_interval_set(
            editor.target_spec, editor.state.domain_basis
        )
        _replace_interval_vector(
            edit_controller,
            group,
            token,
            vector,
            service.target_interval_vectors(
                targets, editor.state.dimensionality, editor.state.domain_basis
            ),
            editor.set_target_override_vectors,
        )


def _transform_domain_element(edit_controller, cell_id, op, index) -> None:
    out = service.resolve_domain_element_transform(
        edit_controller._editor.state, index, edit_controller._rec.cell_value(cell_id), op
    )
    edit_controller._apply_outcome(
        out, lambda: _apply_domain_element(edit_controller, str(index), out.value)
    )


def _interval_group_state(edit_controller, group):
    if group == "comma":
        return (
            edit_controller._editor.state.comma_basis,
            edit_controller._editor.edit_comma_basis,
            "commas",
        )
    if group == "target":
        targets = edit_controller._editor.target_override or service.target_interval_set(
            edit_controller._editor.target_spec, edit_controller._editor.state.domain_basis
        )
        current = service.target_interval_vectors(
            targets,
            edit_controller._editor.state.dimensionality,
            edit_controller._editor.state.domain_basis,
        )
        return current, edit_controller._editor.set_target_override_vectors, "targets"
    if group == "held":
        return (
            edit_controller._editor.held_vectors,
            edit_controller._editor.set_held_vectors,
            "held",
        )
    return (
        edit_controller._editor.interest_vectors,
        edit_controller._editor.set_interest_vectors,
        "interest",
    )


def _transform_interval(edit_controller, cell_id, op):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    group, token = cell_id.split(":")
    if group not in ("comma", "target", "held", "interest", "prime") or token == "pending":
        return
    edit_controller._gestures.end_commit_gestures()
    if group == "prime":
        _transform_domain_element(edit_controller, cell_id, op, int(token))
        return
    current, setter, list_name = _interval_group_state(edit_controller, group)
    toks = edit_controller._runtime.column_tokens(list_name)
    pos = toks.index(int(token)) if int(token) in toks else int(token)
    if not 0 <= pos < len(current):
        return
    new_v = service.transformed_vector(current[pos], op, edit_controller._editor.state.domain_basis)
    if new_v is None:
        return
    vectors = [list(x) for x in current]
    vectors[pos] = list(new_v)
    setter(vectors)
    edit_controller._renderer.request_render()


def _apply_domain_element(edit_controller, token: str, raw: str) -> None:
    if token == "pending":
        edit_controller._editor.set_pending_element(raw)
    else:
        edit_controller._editor.set_domain_element(int(token), raw)


def _element_change(edit_controller, cell_id):
    if (
        edit_controller._runtime.building
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    raw = edit_controller._rec.cell_value(cell_id)
    token = cell_id.split(":")[1]
    out = service.resolve_domain_element_edit(edit_controller._editor.state, token, raw)
    edit_controller._apply_outcome(out, lambda: _apply_domain_element(edit_controller, token, raw))


def _element_preview(edit_controller, cell_id):
    g = edit_controller._gestures.gesture
    if (
        edit_controller._runtime.building
        or g is None
        or g.kind != "edit"
        or g.source != cell_id
        or edit_controller._rec.handles(cell_id).value.input is None
    ):
        return
    raw = edit_controller._rec.cell_value(cell_id)
    token = cell_id.split(":")[1]
    out = service.resolve_domain_element_edit(edit_controller._editor.state, token, raw)
    edit_controller._apply_outcome(
        out, lambda: _apply_domain_element(edit_controller, token, raw), preview=True
    )
