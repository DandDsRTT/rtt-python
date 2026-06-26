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
    _power_parts,
    _ptext_font,
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


def cents_face(rec, cb: spreadsheet.CellBox, cls: str) -> None:
    whole, frac = _cents_parts(cb.text)
    _put_stacked_face(rec, cb.id, cls, whole, f".{frac}" if frac else "", cb.w)


def _ratio(rec, cb: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
    face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
    rec.cells[cb.id].value.ratio_face = face
    with face:
        _ratio_body(rec, cb, approx)


def _ratio_body(rec, cb: spreadsheet.CellBox, approx: bool) -> None:
    parts = _ratio_parts(cb.text)
    if parts and not all(p.lstrip("-").isdigit() for p in parts):
        parts = None
    whole = bool(parts) and parts[1] == "1"
    if approx and parts:
        ui.label("~").classes("rtt-approx")
    if parts:
        with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
            num = ui.label(parts[0]).classes("rtt-frac-num").mark(f"{cb.id}:num")
            den = ui.label(parts[1]).classes("rtt-frac-den").mark(f"{cb.id}:den")
        rec.cells[cb.id].value.frac = (num, den)
        _fit_ratio(rec, cb.id, parts[0], parts[1], cb.w, whole)
    else:
        rec.cells[cb.id].value.label = ui.label(cb.text).classes("rtt-value")


def _fit_ratio(rec, cid: str, num: str, den: str, width: float, whole: bool = False) -> None:
    size = (
        _digit_fit_font(len(num), width, float(_CELL_FONT))
        if whole
        else _ratio_font(num, den, width)
    )
    font = f"font-size:{size:.2f}px"
    rec.cells[cid].value.frac[0].style(font)
    rec.cells[cid].value.frac[1].style(font)


def build_gridvalue(rec, cb: spreadsheet.CellBox, wrap) -> None:
    spec = _GRIDVALUE_SPECS[cb.kind]
    commit, preview = _gridvalue_handlers(rec, cb, spec)
    if spec.ratio_allowed:
        _build_fraction(rec, cb, wrap, commit, preview)
    else:
        wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cb)}"')
        inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
        inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
        rec.cells[cb.id].value.input = inp
    _arm_gridvalue(rec, wrap, cb, spec)


def _build_fraction(rec, cb: spreadsheet.CellBox, wrap, commit, preview) -> None:
    wrap.classes("rtt-cell-input rtt-fraccell")
    box = ui.element("div").classes("rtt-frac-edit").mark(f"{cb.id}:editbox")
    with box:
        num = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cellinput rtt-frac-num-in")
            .mark(f"{cb.id}:num")
        )
        ui.element("div").classes("rtt-frac-bar")
        den = (
            ui.input(on_change=preview)
            .props("dense borderless")
            .classes("rtt-cellinput rtt-frac-den-in")
            .mark(f"{cb.id}:den")
        )
    num.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    den.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    rec.cells[cb.id].value.input = num
    rec.cells[cb.id].value.den_input = den
    rec.cells[cb.id].value.frac_edit = box
    _arm_ratio_ops(rec, cb, wrap)


def _arm_ratio_ops(rec, cb: spreadsheet.CellBox, wrap) -> None:
    if (
        cb.kind not in ("ratiocell", "elementcell", "elementratio")
        or cb.pending
        or cb.id.split(":", 1)[0] not in ("comma", "target", "held", "interest", "prime")
    ):
        return
    wrap.classes("rtt-ratioed")
    with wrap:
        reduce_btn = (
            ui.html(_control_svg("reduce"))
            .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-reduce")
            .mark(f"{cb.id}:reduce")
            .tooltip(tooltips.RATIO_REDUCE_HELP)
        )
        recip_btn = (
            ui.html(_control_svg("reciprocate"))
            .classes("rtt-glyph rtt-ratio-op rtt-ratio-op-recip")
            .mark(f"{cb.id}:reciprocate")
            .tooltip(tooltips.RATIO_RECIPROCATE_HELP)
        )
    reduce_btn.on("click", lambda _=None, cid=cb.id: rec._cb.transform_interval(cid, "reduce"))
    recip_btn.on("click", lambda _=None, cid=cb.id: rec._cb.transform_interval(cid, "reciprocate"))
    rec.cells[cb.id].value.ratio_op = (reduce_btn, recip_btn)
    _sync_ratio_ops(rec, cb.id, cb.text)


def _sync_ratio_ops(rec, cid: str, text: str) -> None:
    ops = rec.handles(cid).value.ratio_op
    if ops is None:
        return
    state = rec._editor.state
    availability = service.interval_op_availability(text, state.domain_basis)
    for btn, enabled in zip(ops, availability, strict=False):
        btn.classes(
            add="" if enabled else "rtt-op-disabled",
            remove="rtt-op-disabled" if enabled else "",
        )


def _gridvalue_handlers(rec, cb: spreadsheet.CellBox, spec: _GridValueSpec):
    fn = getattr(rec._cb, spec.commit)
    if spec.cid_arg:

        def commit(_=None, cid=cb.id):
            return fn(cid)

        pv = getattr(rec._cb, spec.preview) if spec.preview else None
        preview = (lambda _e=None, cid=cb.id: pv(cid)) if pv else None
    else:

        def commit(_=None):
            return fn()

        preview = (lambda _e=None: fn(preview=True)) if spec.preview else None
    return commit, preview


def _arm_gridvalue(rec, wrap, cb: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
    if spec.arm is None:
        return
    if spec.arm[0] == "row":
        arm_row_target(rec, wrap, cb.gen)
    else:
        arm_col_target(rec, wrap, spec.arm[1], cb.comma)


def update_gridvalue(rec, cb: spreadsheet.CellBox) -> None:
    spec = _GRIDVALUE_SPECS[cb.kind]
    text = _gridvalue_text(rec, cb)
    if spec.ratio_allowed:
        _update_fraction(rec, cb, text)
    else:
        rec.cells[cb.id].value.input.value = text
    if spec.pending:
        target = rec.entities[cb.id].el if spec.ratio_allowed else rec.cells[cb.id].value.input
        target.classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )


def _update_fraction(rec, cb: spreadsheet.CellBox, text: str) -> None:
    num, den = _ratio_parts(text) or (text, "")
    ratio = den not in ("", "1")
    rec.cells[cb.id].value.input.value = num
    rec.cells[cb.id].value.den_input.value = den if ratio else ""
    rec.cells[cb.id].value.frac_edit.props(f"data-fracmode={'ratio' if ratio else 'int'}")
    _fit_fraction(rec, cb.id, num, den, cb.w, ratio)
    _sync_ratio_ops(rec, cb.id, text)


def _fit_fraction(rec, cid: str, num: str, den: str, width: float, ratio: bool) -> None:
    size = (
        _ratio_font(num, den, width)
        if ratio
        else _digit_fit_font(len(num), width, float(_CELL_FONT))
    )
    style = f"font-size:{size:.2f}px"
    rec.cells[cid].value.input.style(style)
    rec.cells[cid].value.den_input.style(style)


def _gridvalue_text(rec, cb: spreadsheet.CellBox) -> str:
    if cb.pending and cb.kind in ("commacell", "mapping"):
        draft = (
            rec._editor.pending_comma if cb.kind == "commacell" else rec._editor.pending_mapping_row
        )
        v = draft[cb.prime] if draft is not None else None
        return "" if v is None else str(v)
    return "" if cb.blank else cb.text


def _build_decimal(rec, cb: spreadsheet.CellBox, wrap, commit, *, gen_index=None) -> None:
    wrap.classes("rtt-cell-input rtt-deccell")
    box = ui.element("div").classes("rtt-dec-edit").mark(f"{cb.id}:editbox")
    with box:
        with ui.element("div").classes("rtt-dec-main"):
            if gen_index is not None:
                s = (
                    ui.label("")
                    .classes("rtt-gensign")
                    .mark(f"gensign:{gen_index} {cb.id}:sign")
                    .on(
                        "click",
                        lambda _=None, i=gen_index: rec._cb.act(
                            lambda: rec._editor.flip_generator(i)
                        ),
                    )
                )
                preview_control(rec, s, lambda gi=gen_index: rec._editor.flip_generator(gi))
                rec.cells[cb.id].value.gensign_face = s
            whole = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cellinput rtt-dec-whole-in")
                .mark(f"{cb.id}:whole")
            )
        with ui.element("div").classes("rtt-dec-sub"):
            ui.label(".").classes("rtt-dec-dot")
            frac = (
                ui.input()
                .props("dense borderless")
                .classes("rtt-cellinput rtt-dec-frac-in")
                .mark(f"{cb.id}:frac")
            )
    whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
    rec.cells[cb.id].value.input = whole
    rec.cells[cb.id].value.den_input = frac
    rec.cells[cb.id].value.frac_edit = box


def _update_decimal(rec, cb: spreadsheet.CellBox, text: str, *, signed=False) -> None:
    if signed:
        sign, whole, frac = _gentuning_parts(text)
        if rec.handles(cb.id).value.gensign_face is not None:
            rec.cells[cb.id].value.gensign_face.set_text(sign)
    else:
        whole, frac = _cents_parts(text)
    rec.cells[cb.id].value.input.value = whole
    rec.cells[cb.id].value.den_input.value = frac
    rec.cells[cb.id].value.frac_edit.props(f"data-decmode={'dec' if frac else 'int'}")
    fit_w = cb.w - _GENSIGN_W if signed else cb.w
    rec.cells[cb.id].value.frac_edit.style(
        f"--dec-whole-font:{_digit_fit_font(len(whole), fit_w, float(_CELL_FONT)):.2f}px"
    )


def build_prescalercell(rec, cb: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(rec, cb, wrap, lambda _e=None, cid=cb.id: rec._cb.on_prescaler_change(cid))


def update_prescalercell(rec, cb: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cb, cb.text)


def build_weightcell(rec, cb: spreadsheet.CellBox, wrap) -> None:
    _build_decimal(rec, cb, wrap, lambda _e=None, cid=cb.id: rec._cb.on_weight_change(cid))


def update_weightcell(rec, cb: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cb, cb.text)


def build_powerinput(rec, cb: spreadsheet.CellBox, wrap) -> None:
    wrap.classes("rtt-cell-input rtt-cell-stacked")
    rec.cells[cb.id].value.input = (
        ui.input(on_change=lambda _e, cid=cb.id: rec._cb.on_power_change(cid))
        .props("dense borderless")
        .classes("rtt-cellinput")
    )
    _put_stacked_face(rec, cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)


def update_powerinput(rec, cb: spreadsheet.CellBox) -> None:
    rec.cells[cb.id].value.input.value = cb.text
    _sync_stacked_face(rec, cb.id, *_power_parts(cb.text))


def build_powerdisplay(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    _put_stacked_face(rec, cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)


def update_powerdisplay(rec, cb: spreadsheet.CellBox) -> None:
    _sync_stacked_face(rec, cb.id, *_power_parts(cb.text))


def build_gentuningcell(rec, cb: spreadsheet.CellBox, wrap) -> None:
    i = int(cb.id.rsplit(":", 1)[1])
    _build_decimal(
        rec, cb, wrap, lambda _e=None, cid=cb.id: rec._cb.on_gentuning_change(cid), gen_index=i
    )
    wrap.on(
        "wheel.prevent",
        lambda e, cid=cb.id: rec._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
        args=["deltaY"],
    )
    wrap.on("mouseenter", lambda _=None, cid=cb.id: rec._cb.gentuning_hover(cid))
    wrap.on("mouseleave", lambda _=None, cid=cb.id: rec._cb.gentuning_unhover(cid))


def update_gentuningcell(rec, cb: spreadsheet.CellBox) -> None:
    _update_decimal(rec, cb, "" if cb.blank else cb.text, signed=True)


def build_ptextedit(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    if cb.id.startswith("ptext:projection:"):
        inp = ui.input(value=cb.text).props("dense borderless").classes("rtt-ptextedit")
        inp.on(
            "blur",
            lambda _e=None, cid=cb.id: rec._cb.on_ptext_edit(
                cid, rec.cells[cid].value.ptext_input.value
            ),
        )
    else:
        inp = (
            ui.input(
                value=cb.text,
                on_change=lambda e, cid=cb.id: rec._cb.on_ptext_edit(cid, e.value),
            )
            .props("dense borderless")
            .classes("rtt-ptextedit")
        )
    rec.cells[cb.id].value.ptext_input = inp


def update_ptextedit(rec, cb: spreadsheet.CellBox) -> None:
    rec.cells[cb.id].value.ptext_input.value = cb.text
    rec.cells[cb.id].value.ptext_input.style(f"font-size:{_ptext_font(cb.text, cb.w)}px")


def build_genratio(rec, cb: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(rec, cb, wrap, approx=True)


def build_commaratio(rec, cb: spreadsheet.CellBox, wrap) -> None:
    _build_ratio_face(rec, cb, wrap, approx=False)


def _build_ratio_face(rec, cb: spreadsheet.CellBox, wrap, approx: bool) -> None:
    if cb.pending:
        wrap.classes(add="rtt-pending")
    if cb.pending and cb.text in ("?", "?/?", ""):
        rec.cells[cb.id].value.label = ui.label(cb.text).classes("rtt-value rtt-pending-q")
    else:
        _ratio(rec, cb, approx=approx)


def update_ratio(rec, cb: spreadsheet.CellBox) -> None:
    rec.entities[cb.id].el.classes(
        add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
    )
    face = rec.handles(cb.id).value.ratio_face
    if face is None:
        return
    face.clear()
    rec.cells[cb.id].value.frac = None
    rec.cells[cb.id].value.label = None
    with face:
        _ratio_body(rec, cb, approx=(cb.kind == "genratio"))


def build_tuning_value(rec, cb: spreadsheet.CellBox, _wrap) -> None:
    cents_face(rec, cb, "rtt-tuning-value")


def update_tuning_value(rec, cb: spreadsheet.CellBox) -> None:
    set_cents_face(rec, cb.id, cb.text)
    rec.entities[cb.id].el.classes(
        add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
    )


def label_builder(cls: str):
    def build(rec, cb, _wrap):
        rec.cells[cb.id].value.label = ui.label(cb.text).classes(cls)

    return build


def update_label(rec, cb: spreadsheet.CellBox) -> None:
    rec.cells[cb.id].value.label.set_text(cb.text)
    rec.entities[cb.id].el.classes(
        add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
    )


def update_ptext(rec, cb: spreadsheet.CellBox) -> None:
    rec.cells[cb.id].value.label.set_text(cb.text)
    rec.cells[cb.id].value.label.style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
