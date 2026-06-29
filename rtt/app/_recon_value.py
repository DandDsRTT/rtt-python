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
    _plain_text_font,
    _power_parts,
    _ratio_font,
    _ratio_parts,
)


def _put_stacked_face(rec, cid: str, cls: str, main: str, sub: str, width: float) -> None:
    with ui.element("div").classes(cls):
        m = ui.label(main).classes("rtt-stacked-main").mark(f"{cid}:main")
        s = ui.label(sub).classes("rtt-stacked-sub").mark(f"{cid}:sub")
    rec.cells[cid].value.stacked_face = (m, s)
    rec.cells[cid].value.stacked_w = width
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


def _sync_stacked_face(rec, cid: str, main: str, sub: str) -> None:
    m, s = rec.cells[cid].value.stacked_face
    m.set_text(main)
    s.set_text(sub)
    _size_stacked_main(m, main, sub, rec.cells[cid].value.stacked_w)


def set_cents_face(rec, cid: str, text: str) -> None:
    whole, frac = _cents_parts(text)
    _sync_stacked_face(rec, cid, whole, f".{frac}" if frac else "")


def cents_face(rec, cell_box: spreadsheet.CellBox, cls: str) -> None:
    whole, frac = _cents_parts(cell_box.text)
    _put_stacked_face(rec, cell_box.id, cls, whole, f".{frac}" if frac else "", cell_box.w)


def _ratio(rec, cell_box: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
    face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
    rec.cells[cell_box.id].value.ratio_face = face
    with face:
        _ratio_body(rec, cell_box, approx)


def _ratio_body(rec, cell_box: spreadsheet.CellBox, approx: bool) -> None:
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
        rec.cells[cell_box.id].value.frac = (num, den)
        _fit_ratio(rec, cell_box.id, parts[0], parts[1], cell_box.w, whole)
    else:
        rec.cells[cell_box.id].value.label = ui.label(cell_box.text).classes("rtt-value")


def _fit_ratio(rec, cid: str, num: str, den: str, width: float, whole: bool = False) -> None:
    size = (
        _digit_fit_font(len(num), width, float(_CELL_FONT))
        if whole
        else _ratio_font(num, den, width)
    )
    font = f"font-size:{size:.2f}px"
    rec.cells[cid].value.frac[0].style(font)
    rec.cells[cid].value.frac[1].style(font)


def build_gridvalue(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    spec = _GRIDVALUE_SPECS[cell_box.kind]
    commit, preview = _gridvalue_handlers(rec, cell_box, spec)
    if spec.ratio_allowed:
        _build_fraction(rec, cell_box, wrap, commit, preview)
    else:
        wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cell_box)}"')
        inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
        inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
        rec.cells[cell_box.id].value.input = inp
    _arm_gridvalue(rec, wrap, cell_box, spec)


def _build_fraction(rec, cell_box: spreadsheet.CellBox, wrap, commit, preview) -> None:
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
    rec.cells[cell_box.id].value.input = num
    rec.cells[cell_box.id].value.den_input = den
    rec.cells[cell_box.id].value.frac_edit = box
    _arm_ratio_ops(rec, cell_box, wrap)


def _arm_ratio_ops(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
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
        "click", lambda _=None, cid=cell_box.id: rec._cb.transform_interval(cid, "reduce")
    )
    reciprocate_button.on(
        "click", lambda _=None, cid=cell_box.id: rec._cb.transform_interval(cid, "reciprocate")
    )
    rec.cells[cell_box.id].value.ratio_op = (reduce_button, reciprocate_button)
    _sync_ratio_ops(rec, cell_box.id, cell_box.text)


def _sync_ratio_ops(rec, cid: str, text: str) -> None:
    ops = rec.handles(cid).value.ratio_op
    if ops is None:
        return
    state = rec._editor.state
    availability = service.interval_op_availability(text, state.domain_basis)
    for button, enabled in zip(ops, availability, strict=False):
        button.classes(
            add="" if enabled else "rtt-op-disabled",
            remove="rtt-op-disabled" if enabled else "",
        )


def _gridvalue_handlers(rec, cell_box: spreadsheet.CellBox, spec: _GridValueSpec):
    fn = getattr(rec._cb, spec.commit)
    if spec.cid_arg:

        def commit(_=None, cid=cell_box.id):
            return fn(cid)

        pv = getattr(rec._cb, spec.preview) if spec.preview else None
        preview = (lambda _e=None, cid=cell_box.id: pv(cid)) if pv else None
    else:

        def commit(_=None):
            return fn()

        preview = (lambda _e=None: fn(preview=True)) if spec.preview else None
    return commit, preview


def _arm_gridvalue(rec, wrap, cell_box: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
    if spec.arm is None:
        return
    if spec.arm[0] == "row":
        arm_row_target(rec, wrap, cell_box.gen)
    else:
        arm_col_target(rec, wrap, spec.arm[1], cell_box.comma)


def update_gridvalue(rec, cell_box: spreadsheet.CellBox) -> None:
    spec = _GRIDVALUE_SPECS[cell_box.kind]
    text = _gridvalue_text(rec, cell_box)
    if spec.ratio_allowed:
        _update_fraction(rec, cell_box, text)
    else:
        rec.cells[cell_box.id].value.input.value = text
    if spec.pending:
        target = (
            rec.entities[cell_box.id].el
            if spec.ratio_allowed
            else rec.cells[cell_box.id].value.input
        )
        target.classes(
            add="rtt-pending" if cell_box.pending else "",
            remove="" if cell_box.pending else "rtt-pending",
        )


def _update_fraction(rec, cell_box: spreadsheet.CellBox, text: str) -> None:
    num, den = _ratio_parts(text) or (text, "")
    ratio = den not in ("", "1")
    rec.cells[cell_box.id].value.input.value = num
    rec.cells[cell_box.id].value.den_input.value = den if ratio else ""
    rec.cells[cell_box.id].value.frac_edit.props(f"data-fracmode={'ratio' if ratio else 'int'}")
    _fit_fraction(rec, cell_box.id, num, den, cell_box.w, ratio)
    _sync_ratio_ops(rec, cell_box.id, text)


def _fit_fraction(rec, cid: str, num: str, den: str, width: float, ratio: bool) -> None:
    size = (
        _ratio_font(num, den, width)
        if ratio
        else _digit_fit_font(len(num), width, float(_CELL_FONT))
    )
    style = f"font-size:{size:.2f}px"
    rec.cells[cid].value.input.style(style)
    rec.cells[cid].value.den_input.style(style)


def _gridvalue_text(rec, cell_box: spreadsheet.CellBox) -> str:
    if cell_box.pending and cell_box.kind in ("commacell", "mapping"):
        draft = (
            rec._editor.pending_comma
            if cell_box.kind == "commacell"
            else rec._editor.pending_mapping_row
        )
        v = draft[cell_box.prime] if draft is not None else None
        return "" if v is None else str(v)
    return "" if cell_box.blank else cell_box.text


def _build_decimal(rec, cell_box: spreadsheet.CellBox, wrap, commit, *, gen_index=None) -> None:
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
                        lambda _=None, i=gen_index: rec._cb.act(
                            lambda: rec._editor.flip_generator(i)
                        ),
                    )
                )
                preview_control(rec, s, lambda gi=gen_index: rec._editor.flip_generator(gi))
                rec.cells[cell_box.id].value.gensign_face = s
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
    rec.cells[cell_box.id].value.input = whole
    rec.cells[cell_box.id].value.den_input = frac
    rec.cells[cell_box.id].value.frac_edit = box


def _update_decimal(rec, cell_box: spreadsheet.CellBox, text: str, *, signed=False) -> None:
    if signed:
        sign, whole, frac = _gentuning_parts(text)
        if rec.handles(cell_box.id).value.gensign_face is not None:
            rec.cells[cell_box.id].value.gensign_face.set_text(sign)
    else:
        whole, frac = _cents_parts(text)
    rec.cells[cell_box.id].value.input.value = whole
    rec.cells[cell_box.id].value.den_input.value = frac
    rec.cells[cell_box.id].value.frac_edit.props(f"data-decmode={'dec' if frac else 'int'}")
    fit_w = cell_box.w - _GENSIGN_W if signed else cell_box.w
    rec.cells[cell_box.id].value.frac_edit.style(
        f"--dec-whole-font:{_digit_fit_font(len(whole), fit_w, float(_CELL_FONT)):.2f}px"
    )


def build_prescalercell(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(
        rec, cell_box, wrap, lambda _e=None, cid=cell_box.id: rec._cb.on_prescaler_change(cid)
    )


def update_prescalercell(rec, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cell_box, cell_box.text)


def build_weightcell(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(
        rec, cell_box, wrap, lambda _e=None, cid=cell_box.id: rec._cb.on_weight_change(cid)
    )


def update_weightcell(rec, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cell_box, cell_box.text)


def build_powerinput(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-cell-input rtt-cell-stacked")
    rec.cells[cell_box.id].value.input = (
        ui.input(on_change=lambda _e, cid=cell_box.id: rec._cb.on_power_change(cid))
        .props("dense borderless")
        .classes("rtt-cellinput")
    )
    _put_stacked_face(
        rec, cell_box.id, "rtt-tuning-value rtt-cellface", *_power_parts(cell_box.text), cell_box.w
    )


def update_powerinput(rec, cell_box: spreadsheet.CellBox) -> None:
    rec.cells[cell_box.id].value.input.value = cell_box.text
    _sync_stacked_face(rec, cell_box.id, *_power_parts(cell_box.text))


def build_powerdisplay(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    _put_stacked_face(
        rec, cell_box.id, "rtt-tuning-value rtt-cellface", *_power_parts(cell_box.text), cell_box.w
    )


def update_powerdisplay(rec, cell_box: spreadsheet.CellBox) -> None:
    _sync_stacked_face(rec, cell_box.id, *_power_parts(cell_box.text))


def build_gentuningcell(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    i = int(cell_box.id.rsplit(":", 1)[1])
    _build_decimal(
        rec,
        cell_box,
        wrap,
        lambda _e=None, cid=cell_box.id: rec._cb.on_gentuning_change(cid),
        gen_index=i,
    )
    wrap.on(
        "wheel.prevent",
        lambda e, cid=cell_box.id: rec._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
        args=["deltaY"],
    )
    wrap.on("mouseenter", lambda _=None, cid=cell_box.id: rec._cb.gentuning_hover(cid))
    wrap.on("mouseleave", lambda _=None, cid=cell_box.id: rec._cb.gentuning_unhover(cid))


def update_gentuningcell(rec, cell_box: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cell_box, "" if cell_box.blank else cell_box.text, signed=True)


def build_plain_text_edit(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    if cell_box.id.startswith("plain_text:projection:"):
        inp = ui.input(value=cell_box.text).props("dense borderless").classes("rtt-plain-text-edit")
        inp.on(
            "blur",
            lambda _e=None, cid=cell_box.id: rec._cb.on_plain_text_edit(
                cid, rec.cells[cid].value.plain_text_input.value
            ),
        )
    else:
        inp = (
            ui.input(
                value=cell_box.text,
                on_change=lambda e, cid=cell_box.id: rec._cb.on_plain_text_edit(cid, e.value),
            )
            .props("dense borderless")
            .classes("rtt-plain-text-edit")
        )
    rec.cells[cell_box.id].value.plain_text_input = inp


def update_plain_text_edit(rec, cell_box: spreadsheet.CellBox) -> None:
    rec.cells[cell_box.id].value.plain_text_input.value = cell_box.text
    rec.cells[cell_box.id].value.plain_text_input.style(
        f"font-size:{_plain_text_font(cell_box.text, cell_box.w)}px"
    )


def build_genratio(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(rec, cell_box, wrap, approx=True)


def build_commaratio(rec, cell_box: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(rec, cell_box, wrap, approx=False)


def build_mapped(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    _ratio(rec, cell_box, approx=False)


def _build_ratio_face(rec, cell_box: spreadsheet.CellBox, wrap, approx: bool) -> None:
    if cell_box.pending:
        wrap.classes(add="rtt-pending")
    if cell_box.pending and cell_box.text in ("?", "?/?", ""):
        rec.cells[cell_box.id].value.label = ui.label(cell_box.text).classes(
            "rtt-value rtt-pending-q"
        )
    else:
        _ratio(rec, cell_box, approx=approx)


def update_ratio(rec, cell_box: spreadsheet.CellBox) -> None:
    rec.entities[cell_box.id].el.classes(
        add="rtt-pending" if cell_box.pending else "",
        remove="" if cell_box.pending else "rtt-pending",
    )
    face = rec.handles(cell_box.id).value.ratio_face
    if face is None:
        return
    face.clear()
    rec.cells[cell_box.id].value.frac = None
    rec.cells[cell_box.id].value.label = None
    with face:
        _ratio_body(rec, cell_box, approx=(cell_box.kind == "genratio"))


def build_tuning_value(rec, cell_box: spreadsheet.CellBox, _wrap) -> None:
    cents_face(rec, cell_box, "rtt-tuning-value")


def update_tuning_value(rec, cell_box: spreadsheet.CellBox) -> None:
    set_cents_face(rec, cell_box.id, cell_box.text)
    rec.entities[cell_box.id].el.classes(
        add="rtt-pending" if cell_box.pending else "",
        remove="" if cell_box.pending else "rtt-pending",
    )


def label_builder(cls: str):
    def build(rec, cell_box, _wrap):
        rec.cells[cell_box.id].value.label = ui.label(cell_box.text).classes(cls)

    return build


def update_label(rec, cell_box: spreadsheet.CellBox) -> None:
    rec.cells[cell_box.id].value.label.set_text(cell_box.text)
    rec.entities[cell_box.id].el.classes(
        add="rtt-pending" if cell_box.pending else "",
        remove="" if cell_box.pending else "rtt-pending",
    )


def update_plain_text(rec, cell_box: spreadsheet.CellBox) -> None:
    rec.cells[cell_box.id].value.label.set_text(cell_box.text)
    rec.cells[cell_box.id].value.label.style(
        f"font-size:{_plain_text_font(cell_box.text, cell_box.w)}px"
    )
