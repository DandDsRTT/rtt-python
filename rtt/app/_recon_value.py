from __future__ import annotations

from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_drag import (
    arm_col_target,
    arm_row_target,
)
from rtt.app._recon_hover import (
    wire_action,
)
from rtt.app.page_assets import (
    _CELL_FONT,
    _GENSIGN_W,
    _GRIDVALUE_SPECS,
    _GROUP_EXIT_JS,
    _STACKED_EXIT_JS,
    _STACKED_MAIN_FONT,
    _GridValueSpec,
    _vgroup_key,
)
from rtt.app.render_html import (
    _cents_parts,
    _control_svg,
    _digit_fit_font,
    _generator_tuning_parts,
    _ratio_font,
    _ratio_parts,
)


def _put_stacked_face(
    reconciler, cell_id: str, cls: str, main: str, sub: str, width: float
) -> None:
    with ui.element("div").classes(cls):
        m = ui.label(main).classes("rtt-stacked-main").mark(f"{cell_id}:main")
        s = ui.label(sub).classes("rtt-stacked-sub").mark(f"{cell_id}:sub")
    reconciler.cells[cell_id].value.stacked_face = (m, s)
    reconciler.cells[cell_id].value.stacked_width = width
    _size_stacked_main(m, main, sub, width)


def _size_stacked_main(main_label, main: str, sub: str, width: float) -> None:
    solo = not sub
    main_label.classes(
        add="rtt-stacked-solo" if solo else "", remove="" if solo else "rtt-stacked-solo"
    )
    size = (
        _digit_fit_font(len(main), width, float(_CELL_FONT)) if solo else float(_STACKED_MAIN_FONT)
    )
    main_label.style(f"font-size:{size:.2f}px")


def _sync_stacked_face(reconciler, cell_id: str, main: str, sub: str) -> None:
    m, s = reconciler.cells[cell_id].value.stacked_face
    m.set_text(main)
    s.set_text(sub)
    _size_stacked_main(m, main, sub, reconciler.cells[cell_id].value.stacked_width)


def set_cents_face(reconciler, cell_id: str, text: str) -> None:
    whole, frac = _cents_parts(text)
    _sync_stacked_face(reconciler, cell_id, whole, f".{frac}" if frac else "")


def _set_pending_class(element, pending: bool) -> None:
    element.classes(
        add="rtt-pending" if pending else "",
        remove="" if pending else "rtt-pending",
    )


def cents_face(reconciler, cell: spreadsheet.Cell, cls: str) -> None:
    whole, frac = _cents_parts(cell.text)
    _put_stacked_face(reconciler, cell.id, cls, whole, f".{frac}" if frac else "", cell.width)


def _ratio(reconciler, cell: spreadsheet.Cell, approx: bool, overlay: bool = False) -> None:
    face = ui.element("div").classes("rtt-ratio rtt-cell-face" if overlay else "rtt-ratio")
    reconciler.cells[cell.id].value.ratio_face = face
    with face:
        _ratio_body(reconciler, cell, approx)


def _ratio_body(reconciler, cell: spreadsheet.Cell, approx: bool) -> None:
    parts = _ratio_parts(cell.text)
    if parts and not all(p.lstrip("-").isdigit() for p in parts):
        parts = None
    whole = bool(parts) and parts[1] == "1"
    if approx and parts:
        ui.label("~").classes("rtt-approximate")
    if parts:
        with ui.element("div").classes(
            "rtt-fraction rtt-fraction-whole" if whole else "rtt-fraction"
        ):
            numerator = (
                ui.label(parts[0]).classes("rtt-fraction-numerator").mark(f"{cell.id}:numerator")
            )
            denominator = (
                ui.label(parts[1])
                .classes("rtt-fraction-denominator")
                .mark(f"{cell.id}:denominator")
            )
        reconciler.cells[cell.id].value.frac = (numerator, denominator)
        _fit_ratio(reconciler, cell.id, parts[0], parts[1], cell.width, whole)
    else:
        reconciler.cells[cell.id].value.label = ui.label(cell.text).classes("rtt-value")


def _fit_ratio(
    reconciler, cell_id: str, numerator: str, denominator: str, width: float, whole: bool = False
) -> None:
    size = (
        _digit_fit_font(len(numerator), width, float(_CELL_FONT))
        if whole
        else _ratio_font(numerator, denominator, width)
    )
    font = f"font-size:{size:.2f}px"
    reconciler.cells[cell_id].value.frac[0].style(font)
    reconciler.cells[cell_id].value.frac[1].style(font)


def build_gridvalue(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    spec = _GRIDVALUE_SPECS[cell.kind]
    commit, preview = _gridvalue_handlers(reconciler, cell, spec)
    if spec.ratio_allowed:
        _build_fraction(reconciler, cell, wrap, commit, preview)
    else:
        wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cell)}"')
        inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cell-input-field")
        inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
        reconciler.cells[cell.id].value.input = inp
    _arm_gridvalue(reconciler, wrap, cell, spec)


def _build_fraction(reconciler, cell: spreadsheet.Cell, wrap, commit, preview) -> None:
    wrap.classes("rtt-cell-input rtt-fraction-cell")
    if cell.approx:
        wrap.classes("rtt-approx-cell")
        with wrap:
            ui.label("(~)").classes("rtt-approx-token")
    editor = ui.element("div").classes("rtt-fraction-edit").mark(f"{cell.id}:editor")
    with editor:
        numerator = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cell-input-field rtt-fraction-numerator-input")
            .mark(f"{cell.id}:numerator")
        )
        ui.element("div").classes("rtt-fraction-bar")
        denominator = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cell-input-field rtt-fraction-denominator-input")
            .mark(f"{cell.id}:denominator")
        )
    numerator.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    denominator.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    reconciler.cells[cell.id].value.input = numerator
    reconciler.cells[cell.id].value.denominator_input = denominator
    reconciler.cells[cell.id].value.frac_edit = editor
    _arm_ratio_ops(reconciler, cell, wrap)


def _arm_ratio_ops(reconciler, cell: spreadsheet.Cell, wrap) -> None:
    if (
        cell.kind not in ("ratio_cell", "element_cell", "element_ratio")
        or cell.pending
        or cell.id.split(":", 1)[0] not in ("comma", "target", "held", "interest", "prime")
    ):
        return
    wrap.classes("rtt-ratioed")
    with wrap:
        reduce_button = (
            ui.html(_control_svg("reduce"))
            .classes("rtt-glyph rtt-ratio-operation rtt-ratio-operation-reduce")
            .mark(f"{cell.id}:reduce")
            .tooltip(tooltips.RATIO_REDUCE_HELP)
        )
        reciprocate_button = (
            ui.html(_control_svg("reciprocate"))
            .classes("rtt-glyph rtt-ratio-operation rtt-ratio-operation-reciprocate")
            .mark(f"{cell.id}:reciprocate")
            .tooltip(tooltips.RATIO_RECIPROCATE_HELP)
        )
    reduce_button.on("mousedown", js_handler="(e) => e.preventDefault()")
    reciprocate_button.on("mousedown", js_handler="(e) => e.preventDefault()")
    reduce_button.on(
        "click",
        lambda _=None, cell_id=cell.id: reconciler._callbacks.transform_interval(cell_id, "reduce"),
    )
    reciprocate_button.on(
        "click",
        lambda _=None, cell_id=cell.id: reconciler._callbacks.transform_interval(
            cell_id, "reciprocate"
        ),
    )
    reconciler.cells[cell.id].value.ratio_op = (reduce_button, reciprocate_button)
    _sync_ratio_ops(reconciler, cell.id, cell.text)


def _sync_ratio_ops(reconciler, cell_id: str, text: str) -> None:
    ops = reconciler.handles(cell_id).value.ratio_op
    if ops is None:
        return
    state = reconciler._editor.state
    availability = service.interval_op_availability(text, state.domain_basis)
    for button, enabled in zip(ops, availability, strict=False):
        button.classes(
            add="" if enabled else "rtt-operation-disabled",
            remove="rtt-operation-disabled" if enabled else "",
        )


def _gridvalue_handlers(reconciler, cell: spreadsheet.Cell, spec: _GridValueSpec):
    function = getattr(reconciler._callbacks, spec.commit)
    if spec.cid_arg:

        def commit(_=None, cell_id=cell.id):
            return function(cell_id)

        pv = getattr(reconciler._callbacks, spec.preview) if spec.preview else None
        preview = (lambda _e=None, cell_id=cell.id: pv(cell_id)) if pv else None
    else:

        def commit(_=None):
            return function()

        preview = (lambda _e=None: function(preview=True)) if spec.preview else None
    return commit, preview


def _arm_gridvalue(reconciler, wrap, cell: spreadsheet.Cell, spec: _GridValueSpec) -> None:
    if spec.arm is None:
        return
    if spec.arm[0] == "row":
        arm_row_target(reconciler, wrap, cell.generator)
    else:
        arm_col_target(reconciler, wrap, spec.arm[1], cell.comma)


def update_gridvalue(reconciler, cell: spreadsheet.Cell) -> None:
    spec = _GRIDVALUE_SPECS[cell.kind]
    text = _gridvalue_text(reconciler, cell)
    if spec.ratio_allowed:
        _update_fraction(reconciler, cell, text)
    else:
        reconciler.cells[cell.id].value.input.value = text
    if spec.pending:
        target = (
            reconciler.entities[cell.id].element
            if spec.ratio_allowed
            else reconciler.cells[cell.id].value.input
        )
        _set_pending_class(target, cell.pending)


def _update_fraction(reconciler, cell: spreadsheet.Cell, text: str) -> None:
    if cell.pending and text in ("?/?", "?", ""):
        numerator, denominator, ratio = "", "1", True
    else:
        numerator, denominator = _ratio_parts(text) or (text, "")
        ratio = denominator not in ("", "1")
    reconciler.cells[cell.id].value.input.value = numerator
    reconciler.cells[cell.id].value.denominator_input.value = denominator if ratio else ""
    reconciler.cells[cell.id].value.frac_edit.props(f"data-fracmode={'ratio' if ratio else 'int'}")
    _fit_fraction(reconciler, cell.id, numerator, denominator, cell.width, ratio)
    _sync_ratio_ops(reconciler, cell.id, text)


def _fit_fraction(
    reconciler, cell_id: str, numerator: str, denominator: str, width: float, ratio: bool
) -> None:
    size = (
        _ratio_font(numerator, denominator, width)
        if ratio
        else _digit_fit_font(len(numerator), width, float(_CELL_FONT))
    )
    style = f"font-size:{size:.2f}px"
    reconciler.cells[cell_id].value.input.style(style)
    reconciler.cells[cell_id].value.denominator_input.style(style)


def _gridvalue_text(reconciler, cell: spreadsheet.Cell) -> str:
    if cell.pending and cell.kind in ("comma_cell", "mapping"):
        draft = (
            reconciler._editor.pending_comma
            if cell.kind == "comma_cell"
            else reconciler._editor.pending_mapping_row
        )
        v = draft[cell.prime] if draft is not None else None
        return "" if v is None else str(v)
    return "" if cell.blank else cell.text


def _build_decimal(
    reconciler, cell: spreadsheet.Cell, wrap, commit, *, generator_index=None
) -> None:
    wrap.classes("rtt-cell-input rtt-decimal-cell")
    editor = ui.element("div").classes("rtt-decimal-edit").mark(f"{cell.id}:editor")
    with editor:
        with ui.element("div").classes("rtt-decimal-main"):
            if generator_index is not None:
                s = (
                    ui.label("")
                    .classes("rtt-generator-sign")
                    .mark(f"generator_sign:{generator_index} {cell.id}:sign")
                )
                wire_action(
                    reconciler,
                    s,
                    s,
                    lambda gi=generator_index: reconciler._editor.flip_generator(gi),
                    source_id=cell.id,
                )
                reconciler.cells[cell.id].value.generator_sign_face = s
            whole = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cell-input-field rtt-decimal-whole-input")
                .mark(f"{cell.id}:whole")
            )
        with ui.element("div").classes("rtt-decimal-sub"):
            ui.label(".").classes("rtt-decimal-dot")
            frac = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cell-input-field rtt-decimal-fraction-input")
                .mark(f"{cell.id}:fraction")
            )
    whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    reconciler.cells[cell.id].value.input = whole
    reconciler.cells[cell.id].value.denominator_input = frac
    reconciler.cells[cell.id].value.frac_edit = editor


def _update_decimal(reconciler, cell: spreadsheet.Cell, text: str, *, signed=False) -> None:
    if signed:
        sign, whole, frac = _generator_tuning_parts(text)
        if reconciler.handles(cell.id).value.generator_sign_face is not None:
            reconciler.cells[cell.id].value.generator_sign_face.set_text(sign)
    else:
        whole, frac = _cents_parts(text)
    reconciler.cells[cell.id].value.input.value = whole
    reconciler.cells[cell.id].value.denominator_input.value = frac
    reconciler.cells[cell.id].value.frac_edit.props(f"data-decmode={'dec' if frac else 'int'}")
    fit_width = cell.width - _GENSIGN_W if signed else cell.width
    reconciler.cells[cell.id].value.frac_edit.style(
        f"--dec-whole-font:{_digit_fit_font(len(whole), fit_width, float(_CELL_FONT)):.2f}px"
    )
