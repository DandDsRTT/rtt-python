from __future__ import annotations


from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    tooltips,
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



class _ReconValueCells:
    def __init__(self, r) -> None:
        self.r = r

    def _put_stacked_face(self, cid: str, cls: str, main: str, sub: str, width: float) -> None:
        with ui.element("div").classes(cls):
            m = ui.label(main).classes("rtt-stacked-main")
            s = ui.label(sub).classes("rtt-stacked-sub")
        self.r.stacked_faces[cid] = (m, s)
        self.r.stacked_w[cid] = width
        self._size_stacked_main(m, main, sub, width)

    def _size_stacked_main(self, main_label, main: str, sub: str, width: float) -> None:
        solo = not sub
        main_label.classes(
            add="rtt-stacked-solo" if solo else "", remove="" if solo else "rtt-stacked-solo"
        )
        size = (
            _digit_fit_font(len(main), width, float(_CELL_FONT))
            if solo
            else float(_STACKED_MAIN_FONT)
        )
        main_label.style(f"font-size:{size:.2f}px")

    def _sync_stacked_face(self, cid: str, main: str, sub: str) -> None:
        m, s = self.r.stacked_faces[cid]
        m.set_text(main)
        s.set_text(sub)
        self._size_stacked_main(m, main, sub, self.r.stacked_w[cid])

    def set_cents_face(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self._sync_stacked_face(cid, whole, f".{frac}" if frac else "")

    def cents_face(self, cb: spreadsheet.CellBox, cls: str) -> None:
        whole, frac = _cents_parts(cb.text)
        self._put_stacked_face(cb.id, cls, whole, f".{frac}" if frac else "", cb.w)

    def _ratio(self, cb: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
        face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
        self.r.ratio_faces[cb.id] = face
        with face:
            self._ratio_body(cb, approx)

    def _ratio_body(self, cb: spreadsheet.CellBox, approx: bool) -> None:
        parts = _ratio_parts(cb.text)
        if parts and not all(p.lstrip("-").isdigit() for p in parts):
            parts = None
        whole = bool(parts) and parts[1] == "1"
        if approx and parts:
            ui.label("~").classes("rtt-approx")
        if parts:
            with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
                num = ui.label(parts[0]).classes("rtt-frac-num")
                den = ui.label(parts[1]).classes("rtt-frac-den")
            self.r.fracs[cb.id] = (num, den)
            self._fit_ratio(cb.id, parts[0], parts[1], cb.w, whole)
        else:
            self.r.labels[cb.id] = ui.label(cb.text).classes("rtt-value")

    def _fit_ratio(self, cid: str, num: str, den: str, width: float, whole: bool = False) -> None:
        size = (
            _digit_fit_font(len(num), width, float(_CELL_FONT))
            if whole
            else _ratio_font(num, den, width)
        )
        font = f"font-size:{size:.2f}px"
        self.r.fracs[cid][0].style(font)
        self.r.fracs[cid][1].style(font)

    def _build_gridvalue(self, cb: spreadsheet.CellBox, wrap) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        commit, preview = self._gridvalue_handlers(cb, spec)
        if spec.ratio_allowed:
            self._build_fraction(cb, wrap, commit, preview)
        else:
            wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cb)}"')
            inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
            inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
            self.r.inputs[cb.id] = inp
        self._arm_gridvalue(wrap, cb, spec)

    def _build_fraction(self, cb: spreadsheet.CellBox, wrap, commit, preview) -> None:
        # the editable stacked fraction: a numerator input over a bar over a denominator input, edited
        # IN PLACE (no overlay face, no diagonal slash). The two are SEPARATE fields — Tab moves
        # num->den, the bar isn't selectable — and the cell collapses to the big-integer view when the
        # denominator is blank/1 ("/" in integer view splits it open again). _FRACTION_JS drives the
        # live int<->ratio switch client-side; make_cell gates focus/blur (it also wires the den) so
        # the commit fires only when focus leaves the WHOLE cell. The white box + black outline rides
        # the WRAP (one box around two inputs), not each input's own Quasar control.
        wrap.classes("rtt-cell-input rtt-fraccell")
        box = ui.element("div").classes("rtt-frac-edit")
        with box:
            num = (
                ui.input(on_change=preview)
                .props("dense borderless")
                .classes("rtt-cellinput rtt-frac-num-in")
            )
            ui.element("div").classes("rtt-frac-bar")
            den = (
                ui.input(on_change=preview)
                .props("dense borderless")
                .classes("rtt-cellinput rtt-frac-den-in")
            )
        num.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        den.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.r.inputs[cb.id] = num
        self.r.den_inputs[cb.id] = den
        self.r.frac_edits[cb.id] = box
        self._arm_ratio_ops(cb, wrap)

    def _arm_ratio_ops(self, cb: spreadsheet.CellBox, wrap) -> None:
        # the equave-reduce + reciprocate buttons flanking the bar of an editable interval ratio —
        # any editable interval ratiocell (commas / targets / held / intervals of interest) AND the
        # editable domain basis elements (nonstandard-domain box on: elementcell / elementratio). NOT
        # the read-only derived faces (the ~generator ratios, a non-projection unchanged column, the
        # standard read-only domain primes), which carry no value to edit in place. Each reveals on
        # hover, hides while the cell is edited, and reads disabled when its op is a no-op: an interval
        # already inside [1, equave) can't reduce, a unison can't reciprocate. They commit through
        # transform_interval, one undo step.
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
        reduce_btn.on("click", lambda _=None, cid=cb.id: self.r._cb.transform_interval(cid, "reduce"))
        recip_btn.on(
            "click", lambda _=None, cid=cb.id: self.r._cb.transform_interval(cid, "reciprocate")
        )
        self.r.ratio_ops[cb.id] = (reduce_btn, recip_btn)
        self._sync_ratio_ops(cb.id, cb.text)

    def _sync_ratio_ops(self, cid: str, text: str) -> None:
        ops = self.r.ratio_ops.get(cid)
        if ops is None:
            return
        availability = service.interval_op_availability(text, self.r._editor.state.domain_basis)
        for btn, enabled in zip(ops, availability, strict=False):
            btn.classes(
                add="" if enabled else "rtt-op-disabled",
                remove="rtt-op-disabled" if enabled else "",
            )

    def _gridvalue_handlers(self, cb: spreadsheet.CellBox, spec: _GridValueSpec):
        fn = getattr(self.r._cb, spec.commit)
        if spec.cid_arg:

            def commit(_=None, cid=cb.id):
                return fn(cid)

            pv = getattr(self.r._cb, spec.preview) if spec.preview else None
            preview = (lambda _e=None, cid=cb.id: pv(cid)) if pv else None
        else:

            def commit(_=None):
                return fn()

            preview = (lambda _e=None: fn(preview=True)) if spec.preview else None
        return commit, preview

    def _arm_gridvalue(self, wrap, cb: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
        if spec.arm is None:
            return
        if spec.arm[0] == "row":
            self.r._drag._arm_row_target(wrap, cb.gen)
        else:
            self.r._drag._arm_col_target(wrap, spec.arm[1], cb.comma)

    def _update_gridvalue(self, cb: spreadsheet.CellBox) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        text = self._gridvalue_text(cb)
        if spec.ratio_allowed:
            self._update_fraction(cb, text)
        else:
            self.r.inputs[cb.id].value = text
        if spec.pending:
            target = self.r.els[cb.id] if spec.ratio_allowed else self.r.inputs[cb.id]
            target.classes(
                add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
            )

    def _update_fraction(self, cb: spreadsheet.CellBox, text: str) -> None:
        num, den = _ratio_parts(text) or (text, "")
        ratio = den not in ("", "1")
        self.r.inputs[cb.id].value = num
        self.r.den_inputs[cb.id].value = den if ratio else ""
        self.r.frac_edits[cb.id].props(f"data-fracmode={'ratio' if ratio else 'int'}")
        self._fit_fraction(cb.id, num, den, cb.w, ratio)
        self._sync_ratio_ops(cb.id, text)

    def _fit_fraction(self, cid: str, num: str, den: str, width: float, ratio: bool) -> None:
        size = (
            _ratio_font(num, den, width)
            if ratio
            else _digit_fit_font(len(num), width, float(_CELL_FONT))
        )
        style = f"font-size:{size:.2f}px"
        self.r.inputs[cid].style(style)
        self.r.den_inputs[cid].style(style)

    def _gridvalue_text(self, cb: spreadsheet.CellBox) -> str:
        if cb.pending and cb.kind in ("commacell", "mapping"):
            draft = (
                self.r._editor.pending_comma
                if cb.kind == "commacell"
                else self.r._editor.pending_mapping_row
            )
            v = draft[cb.prime] if draft is not None else None
            return "" if v is None else str(v)
        return "" if cb.blank else cb.text

    def _build_decimal(self, cb: spreadsheet.CellBox, wrap, commit, *, gen_index=None) -> None:
        wrap.classes("rtt-cell-input rtt-deccell")
        box = ui.element("div").classes("rtt-dec-edit")
        with box:
            with ui.element("div").classes("rtt-dec-main"):
                if gen_index is not None:
                    s = (
                        ui.label("")
                        .classes("rtt-gensign")
                        .mark(f"gensign:{gen_index}")
                        .on(
                            "click",
                            lambda _=None, i=gen_index: self.r._cb.act(
                                lambda: self.r._editor.flip_generator(i)
                            ),
                        )
                    )
                    self.r._choose._preview_control(s, lambda gi=gen_index: self.r._editor.flip_generator(gi))
                    self.r.gensign_faces[cb.id] = s
                whole = (
                    ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-whole-in")
                )
            with ui.element("div").classes("rtt-dec-sub"):
                ui.label(".").classes("rtt-dec-dot")
                frac = ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-frac-in")
        whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.r.inputs[cb.id] = whole
        self.r.den_inputs[cb.id] = frac
        self.r.frac_edits[cb.id] = box

    def _update_decimal(self, cb: spreadsheet.CellBox, text: str, *, signed=False) -> None:
        if signed:
            sign, whole, frac = _gentuning_parts(text)
            if cb.id in self.r.gensign_faces:
                self.r.gensign_faces[cb.id].set_text(sign)
        else:
            whole, frac = _cents_parts(text)
        self.r.inputs[cb.id].value = whole
        self.r.den_inputs[cb.id].value = frac
        self.r.frac_edits[cb.id].props(f"data-decmode={'dec' if frac else 'int'}")
        fit_w = cb.w - _GENSIGN_W if signed else cb.w
        self.r.frac_edits[cb.id].style(
            f"--dec-whole-font:{_digit_fit_font(len(whole), fit_w, float(_CELL_FONT)):.2f}px"
        )

    def _build_prescalercell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda _e=None, cid=cb.id: self.r._cb.on_prescaler_change(cid))

    def _update_prescalercell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_weightcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda _e=None, cid=cb.id: self.r._cb.on_weight_change(cid))

    def _update_weightcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_powerinput(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.r.inputs[cb.id] = (
            ui.input(on_change=lambda _e, cid=cb.id: self.r._cb.on_power_change(cid))
            .props("dense borderless")
            .classes("rtt-cellinput")
        )
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerinput(self, cb: spreadsheet.CellBox) -> None:
        self.r.inputs[cb.id].value = cb.text
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_powerdisplay(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerdisplay(self, cb: spreadsheet.CellBox) -> None:
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_gentuningcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        i = int(cb.id.rsplit(":", 1)[1])
        self._build_decimal(
            cb, wrap, lambda _e=None, cid=cb.id: self.r._cb.on_gentuning_change(cid), gen_index=i
        )
        wrap.on(
            "wheel.prevent",
            lambda e, cid=cb.id: self.r._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
            args=["deltaY"],
        )
        wrap.on("mouseenter", lambda _=None, cid=cb.id: self.r._cb.gentuning_hover(cid))
        wrap.on("mouseleave", lambda _=None, cid=cb.id: self.r._cb.gentuning_unhover(cid))

    def _update_gentuningcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, "" if cb.blank else cb.text, signed=True)

    def _build_ptextedit(self, cb: spreadsheet.CellBox, _wrap) -> None:
        if cb.id.startswith("ptext:projection:"):
            inp = ui.input(value=cb.text).props("dense borderless").classes("rtt-ptextedit")
            inp.on(
                "blur",
                lambda _e=None, cid=cb.id: self.r._cb.on_ptext_edit(
                    cid, self.r.ptext_inputs[cid].value
                ),
            )
        else:
            inp = (
                ui.input(
                    value=cb.text,
                    on_change=lambda e, cid=cb.id: self.r._cb.on_ptext_edit(cid, e.value),
                )
                .props("dense borderless")
                .classes("rtt-ptextedit")
            )
        self.r.ptext_inputs[cb.id] = inp

    def _update_ptextedit(self, cb: spreadsheet.CellBox) -> None:
        self.r.ptext_inputs[cb.id].value = cb.text
        self.r.ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    def _build_genratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=True)

    def _build_commaratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=False)

    def _build_ratio_face(self, cb: spreadsheet.CellBox, wrap, approx: bool) -> None:
        if cb.pending:
            wrap.classes(add="rtt-pending")
        if cb.pending and cb.text in ("?", "?/?", ""):
            self.r.labels[cb.id] = ui.label(cb.text).classes("rtt-value rtt-pending-q")
        else:
            self._ratio(cb, approx=approx)

    def _update_ratio(self, cb: spreadsheet.CellBox) -> None:
        self.r.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )
        face = self.r.ratio_faces.get(cb.id)
        if face is None:
            return
        face.clear()
        self.r.fracs.pop(cb.id, None)
        self.r.labels.pop(cb.id, None)
        with face:
            self._ratio_body(cb, approx=(cb.kind == "genratio"))

    def _build_tuning_value(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.cents_face(cb, "rtt-tuning-value")

    def _update_tuning_value(self, cb: spreadsheet.CellBox) -> None:
        self.set_cents_face(cb.id, cb.text)
        self.r.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )

    def _label_builder(self, cls: str):
        def build(cb, _wrap):
            self.r.labels[cb.id] = ui.label(cb.text).classes(cls)

        return build

    def _update_label(self, cb: spreadsheet.CellBox) -> None:
        self.r.labels[cb.id].set_text(cb.text)
        self.r.els[cb.id].classes(
            add="rtt-pending" if cb.pending else "", remove="" if cb.pending else "rtt-pending"
        )

    def _update_ptext(self, cb: spreadsheet.CellBox) -> None:
        self.r.labels[cb.id].set_text(cb.text)
        self.r.labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
