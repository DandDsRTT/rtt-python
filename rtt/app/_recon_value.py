from __future__ import annotations

from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_choosers import (
    preview_control,
)
from rtt.app._recon_drag import (
    arm_col_target,
    arm_row_target,
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
    _gentuning_parts,
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


def cents_face(reconciler, cell_box: spreadsheet.CellBox, cls: str) -> None:
    whole, frac = _cents_parts(cell_box.text)
    _put_stacked_face(
        reconciler, cell_box.id, cls, whole, f".{frac}" if frac else "", cell_box.width
    )


def _ratio(reconciler, cell_box: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
    face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
    reconciler.cells[cell_box.id].value.ratio_face = face
    with face:
        _ratio_body(reconciler, cell_box, approx)


def _ratio_body(reconciler, cell_box: spreadsheet.CellBox, approx: bool) -> None:
    parts = _ratio_parts(cell_box.text)
    if parts and not all(p.lstrip("-").isdigit() for p in parts):
        parts = None
    whole = bool(parts) and parts[1] == "1"
    if approx and parts:
        ui.label("~").classes("rtt-approx")
    if parts:
        with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
            num = ui.label(parts[0]).classes("rtt-frac-num").mark(f"{cell_box.id}:num")
            den = ui.label(parts[1]).classes("rtt-frac-den").mark(f"{cell_box.id}:den")
        reconciler.cells[cell_box.id].value.frac = (num, den)
        _fit_ratio(reconciler, cell_box.id, parts[0], parts[1], cell_box.width, whole)
    else:
        reconciler.cells[cell_box.id].value.label = ui.label(cell_box.text).classes("rtt-value")


def _fit_ratio(
    reconciler, cell_id: str, num: str, den: str, width: float, whole: bool = False
) -> None:
    size = (
        _digit_fit_font(len(num), width, float(_CELL_FONT))
        if whole
        else _ratio_font(num, den, width)
    )
    font = f"font-size:{size:.2f}px"
    reconciler.cells[cell_id].value.frac[0].style(font)
    reconciler.cells[cell_id].value.frac[1].style(font)


def build_gridvalue(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    spec = _GRIDVALUE_SPECS[cell_box.kind]
    commit, preview = _gridvalue_handlers(reconciler, cell_box, spec)
    if spec.ratio_allowed:
        _build_fraction(reconciler, cell_box, wrap, commit, preview)
    else:
        wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cell_box)}"')
        inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
        inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
        reconciler.cells[cell_box.id].value.input = inp
    _arm_gridvalue(reconciler, wrap, cell_box, spec)


def _build_fraction(reconciler, cell_box: spreadsheet.CellBox, wrap, commit, preview) -> None:
    wrap.classes("rtt-cell-input rtt-fraccell")
    box = ui.element("div").classes("rtt-frac-edit").mark(f"{cell_box.id}:editbox")
    with box:
        num = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cellinput rtt-frac-num-in")
            .mark(f"{cell_box.id}:num")
        )
        ui.element("div").classes("rtt-frac-bar")
        den = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cellinput rtt-frac-den-in")
            .mark(f"{cell_box.id}:den")
        )
    num.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    den.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    reconciler.cells[cell_box.id].value.input = num
    reconciler.cells[cell_box.id].value.den_input = den
    reconciler.cells[cell_box.id].value.frac_edit = box
    _arm_ratio_ops(reconciler, cell_box, wrap)


def _arm_ratio_ops(reconciler, cell_box: spreadsheet.CellBox, wrap) -> None:
    if (
        cell_box.kind not in ("ratiocell", "elementcell", "elementratio")
        or cell_box.pending
        or cell_box.id.split(":", 1)[0] not in ("comma", "target", "held", "interest", "prime")
    ):
        return
    wrap.classes("rtt-ratioed")
    with wrap:
        reduce_button = (
            ui.html(_control_svg("reduce"))
            .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-reduce")
            .mark(f"{cell_box.id}:reduce")
            .tooltip(tooltips.RATIO_REDUCE_HELP)
        )
        reciprocate_button = (
            ui.html(_control_svg("reciprocate"))
            .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-recip")
            .mark(f"{cell_box.id}:reciprocate")
            .tooltip(tooltips.RATIO_RECIPROCATE_HELP)
        )
    reduce_button.on(
        "click",
        lambda _=None, cell_id=cell_box.id: reconciler._cell_box.transform_interval(
            cell_id, "reduce"
        ),
    )
    reciprocate_button.on(
        "click",
        lambda _=None, cell_id=cell_box.id: reconciler._cell_box.transform_interval(
            cell_id, "reciprocate"
        ),
    )
    reconciler.cells[cell_box.id].value.ratio_op = (reduce_button, reciprocate_button)
    _sync_ratio_ops(reconciler, cell_box.id, cell_box.text)


def _sync_ratio_ops(reconciler, cell_id: str, text: str) -> None:
    ops = reconciler.handles(cell_id).value.ratio_op
    if ops is None:
        return
    state = reconciler._editor.state
    availability = service.interval_op_availability(text, state.domain_basis)
    for button, enabled in zip(ops, availability, strict=False):
        button.classes(
            add="" if enabled else "rtt-op-disabled",
            remove="rtt-op-disabled" if enabled else "",
        )


def _gridvalue_handlers(reconciler, cell_box: spreadsheet.CellBox, spec: _GridValueSpec):
    fn = getattr(reconciler._cell_box, spec.commit)
    if spec.cid_arg:

        def commit(_=None, cell_id=cell_box.id):
            return fn(cell_id)

        pv = getattr(reconciler._cell_box, spec.preview) if spec.preview else None
        preview = (lambda _e=None, cell_id=cell_box.id: pv(cell_id)) if pv else None
    else:

        def commit(_=None):
            return fn()

        preview = (lambda _e=None: fn(preview=True)) if spec.preview else None
    return commit, preview


def _arm_gridvalue(reconciler, wrap, cell_box: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
    if spec.arm is None:
        return
    if spec.arm[0] == "row":
        arm_row_target(reconciler, wrap, cell_box.gen)
    else:
        arm_col_target(reconciler, wrap, spec.arm[1], cell_box.comma)


def update_gridvalue(reconciler, cell_box: spreadsheet.CellBox) -> None:
    spec = _GRIDVALUE_SPECS[cell_box.kind]
    text = _gridvalue_text(reconciler, cell_box)
    if spec.ratio_allowed:
        _update_fraction(reconciler, cell_box, text)
    else:
        reconciler.cells[cell_box.id].value.input.value = text
    if spec.pending:
        target = (
            reconciler.entities[cell_box.id].element
            if spec.ratio_allowed
            else reconciler.cells[cell_box.id].value.input
        )
        _set_pending_class(target, cell_box.pending)


def _update_fraction(reconciler, cell_box: spreadsheet.CellBox, text: str) -> None:
    num, den = _ratio_parts(text) or (text, "")
    ratio = den not in ("", "1")
    reconciler.cells[cell_box.id].value.input.value = num
    reconciler.cells[cell_box.id].value.den_input.value = den if ratio else ""
    reconciler.cells[cell_box.id].value.frac_edit.props(
        f"data-fracmode={'ratio' if ratio else 'int'}"
    )
    _fit_fraction(reconciler, cell_box.id, num, den, cell_box.width, ratio)
    _sync_ratio_ops(reconciler, cell_box.id, text)


def _fit_fraction(reconciler, cell_id: str, num: str, den: str, width: float, ratio: bool) -> None:
    size = (
        _ratio_font(num, den, width)
        if ratio
        else _digit_fit_font(len(num), width, float(_CELL_FONT))
    )
    style = f"font-size:{size:.2f}px"
    reconciler.cells[cell_id].value.input.style(style)
    reconciler.cells[cell_id].value.den_input.style(style)


def _gridvalue_text(reconciler, cell_box: spreadsheet.CellBox) -> str:
    if cell_box.pending and cell_box.kind in ("commacell", "mapping"):
        draft = (
            reconciler._editor.pending_comma
            if cell_box.kind == "commacell"
            else reconciler._editor.pending_mapping_row
        )
        v = draft[cell_box.prime] if draft is not None else None
        return "" if v is None else str(v)
    return "" if cell_box.blank else cell_box.text


def _build_decimal(
    reconciler, cell_box: spreadsheet.CellBox, wrap, commit, *, gen_index=None
) -> None:
    wrap.classes("rtt-cell-input rtt-deccell")
    box = ui.element("div").classes("rtt-dec-edit").mark(f"{cell_box.id}:editbox")
    with box:
        with ui.element("div").classes("rtt-dec-main"):
            if gen_index is not None:
                s = (
                    ui.label("")
                    .classes("rtt-gensign")
                    .mark(f"gensign:{gen_index} {cell_box.id}:sign")
                    .on(
                        "click",
                        lambda _=None, i=gen_index: reconciler._cell_box.act(
                            lambda: reconciler._editor.flip_generator(i)
                        ),
                    )
                )
                preview_control(
                    reconciler, s, lambda gi=gen_index: reconciler._editor.flip_generator(gi)
                )
                reconciler.cells[cell_box.id].value.gensign_face = s
            whole = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cellinput rtt-dec-whole-in")
                .mark(f"{cell_box.id}:whole")
            )
        with ui.element("div").classes("rtt-dec-sub"):
            ui.label(".").classes("rtt-dec-dot")
            frac = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cellinput rtt-dec-frac-in")
                .mark(f"{cell_box.id}:frac")
            )
    whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    reconciler.cells[cell_box.id].value.input = whole
    reconciler.cells[cell_box.id].value.den_input = frac
    reconciler.cells[cell_box.id].value.frac_edit = box


def _update_decimal(reconciler, cell_box: spreadsheet.CellBox, text: str, *, signed=False) -> None:
    if signed:
        sign, whole, frac = _gentuning_parts(text)
        if reconciler.handles(cell_box.id).value.gensign_face is not None:
            reconciler.cells[cell_box.id].value.gensign_face.set_text(sign)
    else:
        whole, frac = _cents_parts(text)
    reconciler.cells[cell_box.id].value.input.value = whole
    reconciler.cells[cell_box.id].value.den_input.value = frac
    reconciler.cells[cell_box.id].value.frac_edit.props(f"data-decmode={'dec' if frac else 'int'}")
    fit_width = cell_box.width - _GENSIGN_W if signed else cell_box.width
    reconciler.cells[cell_box.id].value.frac_edit.style(
        f"--dec-whole-font:{_digit_fit_font(len(whole), fit_width, float(_CELL_FONT)):.2f}px"
    )
