from __future__ import annotations

from rtt.app import service
from rtt.app.grid_tables import BANDS, SUB_CLOSE, SUB_OPEN
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_closed_form import (
    _closed_form,
    _ss_closed_form,
    closed_form_operand,
)
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BOX_INNER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    BRACKET_W,
    CAPTION_LINE,
    CBOX_DROP_W,
    CBOX_SLOT_W,
    CHART_H,
    COL_W,
    DASH,
    LBOX_DIM_W,
    OPT_COL_GAP,
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_L,
    OPT_PAD_R,
    OPT_PAD_T,
    OPT_POW_CAP_W,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    OPTION_BOX_PX,
    PRESET_H,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    SYMBOL_H,
)
from rtt.app.spreadsheet_text import (
    _format_power,
    _math_expr,
    _power_mean,
    _prescale_math_expr,
)


class _EmitTuningMixin:
    def tuning_value_row(self, key: str, group: str, values, editable_kind=None) -> None:
        _r = self.resolved
        if not self.tile_open(key, group):
            return
        values = tuple(values)
        if key in BANDS["chart"].rows:
            self.chart_tiles.append((key, group, values))
        y = self.rows[key].y
        is_gen_group = group in ("gens", "ssgens")
        is_prime_group = group in ("primes", "ssprimes")
        for i, v in enumerate(values):
            cid = f"{key}:{self.group_elem[group]}:{self.col_token(group, i)}"
            x = self.group_left[group][self.comma_value_pos(i) if group == "commas" else i]
            u = self.cell_unit(key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
            operand = closed_form_operand(self.resolved, self.geometry, self, key, group, i, v) if _r.flags.math else None
            if operand is not None:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=u))
            else:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, editable_kind or "tuningvalue",
                                     text=service.cents(v, _r.flags.decimals), unit=u))
            if key in ("tuning", "just"):
                self._voice(f"{key}:{group}", i, v)
        pending_idx = self._pending_draft_idx(group)
        if pending_idx is not None and pending_idx[0] is not None:
            text = ""
            if _r.ghosts.comma and group == "commas":
                gsize = {"tuning": 0.0, "just": _r.ghosts.comma_just, "retune": -_r.ghosts.comma_just,
                         "complexity": _r.ghosts.comma_complexity}.get(key)
                if gsize is not None:
                    text = service.cents(gsize, _r.flags.decimals)
            self.cells.append(CellBox(f"{key}:{self.group_elem[group]}:draft", self.group_left[group][pending_idx[1]],
                                      y, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    def chart(self, rkey: str, ckey: str, values, indicator=None, indicator_label="") -> None:
        values = tuple(values)
        if values and rkey in self.rows and self.rows[rkey].chart_top is not None and self.tile_open(rkey, ckey):
            x = self.group_left[ckey][0] - BRACKET_W
            self.cells.append(CellBox(f"chart:{rkey}:{ckey}", x, self.rows[rkey].chart_top,
                                 2 * BRACKET_W + len(values) * COL_W, CHART_H, "chart", values=values,
                                 indicator=indicator, indicator_label=indicator_label))

    def _emit_tuning_rows(self):
        self.chart_tiles = []
        chart_indicators = {}
        self._emit_tuning_prime_rows()
        self._emit_tuning_gen_row()
        self._emit_tuning_canongen_row()
        self._emit_tuning_superspace_rows()
        self._emit_tuning_detempering_rows()
        return chart_indicators

    def _emit_tuning_prime_rows(self):
        _r = self.resolved
        tuning_data = {
            "tuning": (_r.tuning.tun.tuning_map, _r.tuning.comma_sizes.tempered + _r.unchanged.sizes.tempered, _r.tuning.target_sizes.tempered, _r.tuning.interest_sizes.tempered, _r.tuning.held_sizes.tempered),
            "just": (_r.tuning.tun.just_map, _r.tuning.comma_sizes.just + _r.unchanged.sizes.just, _r.tuning.target_sizes.just, _r.tuning.interest_sizes.just, _r.tuning.held_sizes.just),
            "retune": (_r.tuning.tun.retuning_map, _r.tuning.comma_sizes.errors + _r.unchanged.sizes.errors, _r.tuning.target_sizes.errors, _r.tuning.interest_sizes.errors, _r.tuning.held_sizes.errors),
        }
        for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
            if self.row_open(key):
                self.tuning_value_row(key, "primes", prime_vals)
                self.tuning_value_row(key, "commas", comma_vals)
                self.tuning_value_row(key, "targets", target_vals)
                self.tuning_value_row(key, "interest", interest_vals)
                self.tuning_value_row(key, "held", held_vals)

    def _emit_tuning_gen_row(self):
        _r = self.resolved
        if not (self.row_open("tuning") and self.tile_open("tuning", "gens")):
            return
        gen_kind = "tuningvalue" if _r.flags.superspace_generators else "gentuningcell"
        for i, v in enumerate(_r.tuning.tun.generator_map):
            operand = None
            if _r.flags.math and not _r.flags.superspace_generators:
                closed_form = _closed_form(self.resolved, self)
                operand = closed_form.generator_operand(i, v) if closed_form is not None else None
            if operand is not None:
                self.cells.append(CellBox(f"tuning:gen:{self.col_token('gens', i)}", self.group_left["gens"][i], self.rows["tuning"].y, COL_W, ROW_H,
                                     "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=self.cell_unit("tuning", "gens", gen=i)))
            else:
                self.cells.append(CellBox(f"tuning:gen:{self.col_token('gens', i)}", self.group_left["gens"][i], self.rows["tuning"].y, COL_W, ROW_H,
                                     gen_kind, text=service.cents(v, _r.flags.decimals), gen=i, unit=self.cell_unit("tuning", "gens", gen=i)))
            self._voice("tuning:gens", i, v)

    def _emit_tuning_canongen_row(self):
        _r = self.resolved
        if not (self.row_open("tuning") and self.tile_open("tuning", "canongens")):
            return
        gm = _r.tuning.tun.generator_map
        for j in range(_r.dims.rc):
            v = sum(gm[k] * _r.canon.inverse_form_M[k][j] for k in range(_r.dims.r))
            operand = None
            if _r.flags.math:
                closed_form = _closed_form(self.resolved, self)
                if closed_form is not None:
                    coefficients = [_r.canon.inverse_form_M[k][j] for k in range(_r.dims.r)]
                    operand = closed_form.canonical_generator_operand(coefficients, v)
            if operand is not None:
                self.cells.append(CellBox(f"tuning:cangen:{j}", self.canongen_left(j), self.rows["tuning"].y, COL_W, ROW_H,
                                     "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals), unit=self.cell_unit("tuning", "canongens", gen=j)))
            else:
                self.cells.append(CellBox(f"tuning:cangen:{j}", self.canongen_left(j), self.rows["tuning"].y, COL_W, ROW_H,
                                     "tuningvalue", text=service.cents(v, _r.flags.decimals), gen=j, unit=self.cell_unit("tuning", "canongens", gen=j)))
            self._voice("tuning:canongens", j, v)

    def _emit_tuning_superspace_rows(self):
        _r = self.resolved
        if not (_r.flags.superspace and self.row_open("tuning")):
            return
        ss_tun = self.superspace_tun()
        if self.tile_open("tuning", "ssgens"):
            self._emit_tuning_ssgen_row(ss_tun)
        self.tuning_value_row("tuning", "ssprimes", ss_tun.tuning_map)
        if self.row_open("just"):
            self.tuning_value_row("just", "ssprimes", ss_tun.just_map)
        if self.row_open("retune"):
            self.tuning_value_row("retune", "ssprimes", ss_tun.retuning_map)

    def _emit_tuning_ssgen_row(self, ss_tun):
        _r = self.resolved
        if not _r.flags.superspace_generators:
            self.tuning_value_row("tuning", "ssgens", ss_tun.generator_map)
            return
        ss_cf = _ss_closed_form(self.resolved, self) if _r.flags.math else None
        for i, v in enumerate(ss_tun.generator_map):
            operand = ss_cf.generator_operand(i, v) if ss_cf is not None else None
            if operand is not None:
                self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"][i], self.rows["tuning"].y,
                                     COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, _r.flags.quantities, _r.flags.decimals),
                                     unit=self.cell_unit("tuning", "ssgens", gen=i)))
            else:
                self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"][i], self.rows["tuning"].y,
                                     COL_W, ROW_H, "gentuningcell", text=service.cents(v, _r.flags.decimals),
                                     unit=self.cell_unit("tuning", "ssgens", gen=i)))
            self._voice("tuning:ssgens", i, v)

    def _emit_tuning_detempering_rows(self):
        _r = self.resolved
        if not _r.flags.detempering:
            return
        for key, values in (("tuning", _r.detempering.sizes.tempered),
                            ("just", _r.detempering.sizes.just),
                            ("retune", _r.detempering.sizes.errors)):
            if self.row_open(key):
                self.tuning_value_row(key, "detempering", values)

    def _lift_to_superspace(self, vs):
        _r = self.resolved
        return tuple(None if v is None else service.lift_vectors_to_superspace(_r.dims.elements, (v,))[0]
                     for v in vs)

    def _prescale_setup(self, nrows):
        _r = self.resolved
        if _r.flags.superspace:
            prescaler_diag = service.superspace_complexity_prescaler(self.state, self.tuning_scheme)
            prescaler_is_matrix = False
            ss_elements = service.superspace_primes(_r.dims.elements)
            lift = self._lift_to_superspace
            prescale_vectors = {
                "ssprimes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                "primes": service.basis_in_superspace(_r.dims.elements),
                "commas": lift(self.state.comma_basis) + (lift(_r.unchanged.basis) if _r.unchanged.shown else ()),
                "targets": lift(_r.targets.vectors),
                "interest": lift(_r.interest.vectors),
                "held": lift(_r.held.vectors),
                "detempering": lift(_r.detempering.vectors),
            }
            groups = ("ssprimes", "primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "ssprimes"
        else:
            prescaler_diag = _r.scalars.prescaler
            prescaler_is_matrix = _r.scalars.prescaler_is_matrix
            ss_elements = _r.dims.elements
            prescale_vectors = {
                "primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                "commas": self.state.comma_basis + (_r.unchanged.basis if _r.unchanged.shown else ()),
                "targets": _r.targets.vectors,
                "interest": _r.interest.vectors,
                "held": _r.held.vectors,
                "detempering": _r.detempering.vectors,
            }
            groups = ("primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "primes"
        return prescaler_diag, prescaler_is_matrix, ss_elements, prescale_vectors, groups, bare_group

    def _prescale_prime_terms(self, ss_elements):
        _r = self.resolved
        if _r.labels.scheme_prescaler == "log-prime":
            return {i: f"log₂{p}" for i, p in enumerate(ss_elements)}
        if _r.labels.scheme_prescaler == "prime":
            return {i: str(p) for i, p in enumerate(ss_elements)}
        return {}

    def _emit_prescaling_band(self) -> None:
        nrows = self.prescale_rows
        prescaler_diag, prescaler_is_matrix, ss_elements, prescale_vectors, groups, bare_group = self._prescale_setup(nrows)
        prime_term = self._prescale_prime_terms(ss_elements)
        for group in groups:
            if not self.tile_open("prescaling", group):
                continue
            self._emit_prescale_group(group, prescale_vectors[group], prescaler_diag,
                                      prescaler_is_matrix, prime_term, bare_group, nrows)
            self._emit_prescale_draft(group, prescaler_diag, prescaler_is_matrix, nrows)

    def _emit_prescale_group(self, group, vectors, prescaler_diag, prescaler_is_matrix, prime_term, bare_group, nrows):
        left = self.group_left[group]
        for c, vec in enumerate(vectors):
            u = self.cell_unit("prescaling", group, prime=c if group == bare_group else None)
            if vec is None:
                for i in range(nrows + self.size_rows):
                    cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
                    cx, cy = left[self.comma_value_pos(c) if group == "commas" else c], self.rows["prescaling"].y + i * ROW_H
                    self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue", text=DASH, unit=u))
                continue
            prescaled = self._prescale_vector(vec, prescaler_diag, prescaler_is_matrix, nrows)
            self._emit_prescale_cells(group, c, vec, prescaled, prime_term, left, u, nrows)

    def _prescale_vector(self, vec, prescaler_diag, prescaler_is_matrix, nrows):
        return ([sum(prescaler_diag[i][k] * vec[k] for k in range(nrows)) for i in range(nrows)]
                if prescaler_is_matrix
                else [prescaler_diag[i] * vec[i] for i in range(nrows)])

    def _emit_prescale_cells(self, group, c, vec, prescaled, prime_term, left, u, nrows):
        _r = self.resolved
        for i in range(nrows + self.size_rows):
            value = prescaled[i] if i < nrows else self.size_factor * sum(prescaled)
            cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
            cx, cy = left[self.comma_value_pos(c) if group == "commas" else c], self.rows["prescaling"].y + i * ROW_H
            if i < nrows and not _r.flags.superspace and group == "primes" and (i == c or _r.flags.alt_complexity):
                self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "prescalercell",
                                     text=service.prescale_text(value, _r.flags.decimals), prime=i, unit=u))
            elif i < nrows and _r.flags.math and vec[i] != 0 and i in prime_term:
                self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "mathexpr",
                                     text=_prescale_math_expr(vec[i], prime_term[i], value, _r.flags.quantities, _r.flags.decimals), unit=u))
            else:
                self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue",
                                     text=service.prescale_text(value, _r.flags.decimals), unit=u))

    def _emit_prescale_draft(self, group, prescaler_diag, prescaler_is_matrix, nrows):
        _r = self.resolved
        pending_idx = self._pending_draft_idx(group)
        if pending_idx is None or pending_idx[0] is None:
            return
        left = self.group_left[group]
        ghost_pre = None
        if _r.ghosts.comma and group == "commas" and _r.ghosts.comma_vec is not None:
            gvec = self._lift_to_superspace((_r.ghosts.comma_vec,))[0] if _r.flags.superspace else _r.ghosts.comma_vec
            ghost_pre = self._prescale_vector(gvec, prescaler_diag, prescaler_is_matrix, nrows)
        for i in range(nrows + self.size_rows):
            cy = self.rows["prescaling"].y + i * ROW_H
            text = ""
            if ghost_pre is not None:
                value = ghost_pre[i] if i < nrows else self.size_factor * sum(ghost_pre)
                text = service.prescale_text(value, _r.flags.decimals)
            self.cells.append(CellBox(f"cell:prescaling:{group}:{i}:draft", left[pending_idx[1]],
                                 cy, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    def _emit_lbox_control(self) -> None:
        _r = self.resolved
        if self.lbox_ctrl:
            box_top = self.rows["prescaling"].tile_top + self.rows["prescaling"].tile_h - self.lbox_extra + RANGE_GAP
            bx, by = self.control_region("block:diminuator", "ssprimes" if _r.flags.superspace else "primes",
                                         box_top, OPTION_BOX_PX + CAPTION_LINE)
            self.cells.append(CellBox("control:diminuator", bx, by, LBOX_DIM_W, OPTION_BOX_PX,
                                 "control_check", text="",
                                 checked=service.diminuator_replaced(self.tuning_scheme)))
            self.cells.append(CellBox("caption:diminuator", bx, by + OPTION_BOX_PX, LBOX_DIM_W,
                                 CAPTION_LINE, "caption", text="replace diminuator"))

    def _emit_cbox_controls(self) -> None:
        _r = self.resolved
        if self.cbox_ctrl:
            box_top = self.rows["complexity"].tile_top + self.rows["complexity"].tile_h - self.cbox_extra + RANGE_GAP
            tx, cy = self.control_region("block:complexity", "targets", box_top, ROW_H + _r.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)
            sym_y = cy + ROW_H
            cap_y = sym_y + _r.scalars.ctrl_symbol_h
            cap_h = 3 * CAPTION_LINE
            slot_w = CBOX_SLOT_W
            q_slot_x = tx
            if _r.flags.presets:
                drop_w = CBOX_DROP_W
                complexity_key = service.complexity_name_of(self.tuning_scheme)
                if _r.labels.realized_prescaler is None:
                    complexity_key = "custom"
                complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
                complexity_values = (((*tuple(service.COMPLEXITY_DISPLAYS.values()), "custom"))
                                     if _r.flags.alt_complexity else (complexity_text,))
                complexity_locked = self._is_sole_option(complexity_values, complexity_text)
                self.cells.append(CellBox("control:complexity", tx, cy, drop_w, PRESET_H,
                                     "control_select", text=complexity_text, values=complexity_values,
                                     disabled=complexity_locked))
                self.cells.append(CellBox("caption:complexity", tx, cy + PRESET_H, drop_w,
                                     CAPTION_LINE, "caption", text="predefined complexities",
                                     align="left", disabled=complexity_locked))
                q_slot_x = tx + drop_w + OPT_COL_GAP
            q_x = q_slot_x + (slot_w - COL_W) / 2
            q_text = _format_power(service.complexity_norm_power(self.tuning_scheme))
            q_kind = "powerinput" if _r.flags.alt_complexity else "powerdisplay"
            self.cells.append(CellBox("control:q", q_x, cy, COL_W, ROW_H, q_kind, text=q_text))
            if _r.flags.symbols:
                self.cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_w, SYMBOL_H, "symbol", text="𝑞"))
            self.cells.append(CellBox("caption:q", q_slot_x, cap_y, slot_w, cap_h, "caption",
                                 text="interval complexity norm power"))
            if service.is_all_interval(self.tuning_scheme):
                dual_slot_x = q_slot_x + slot_w + OPT_COL_GAP
                dual_x = dual_slot_x + (slot_w - COL_W) / 2
                dual_text = _format_power(service.dual_norm_power(self.tuning_scheme))
                self.cells.append(CellBox("control:dual", dual_x, cy, COL_W, ROW_H, "powerdisplay", text=dual_text))
                if _r.flags.symbols:
                    self.cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_w, SYMBOL_H,
                                         "symbol", text="dual(𝑞)"))
                self.cells.append(CellBox("caption:dual", dual_slot_x, cap_y, slot_w, cap_h, "caption",
                                     text="dual norm power"))

    def _emit_complexity_row(self) -> None:
        _r = self.resolved
        if self.row_open("complexity"):
            for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
                values = _r.complexities[group] + (_r.unchanged.complexities if group == "commas" else ())
                self.tuning_value_row("complexity", group, values)
            if _r.flags.superspace and self.tile_open("complexity", "ssprimes"):
                self.tuning_value_row("complexity", "ssprimes",
                              service.superspace_complexity_prescaler(self.state, self.tuning_scheme))

    def _emit_weight_row(self) -> None:
        _r = self.resolved
        if self.row_open("weight") and self.tile_open("weight", "targets"):
            self.tuning_value_row("weight", "targets", _r.tuning.target_weights,
                                  editable_kind="weightcell" if _r.scalars.custom_weights_active else None)
        if self.slope_ctrl:
            box_top = self.rows["weight"].tile_top + self.rows["weight"].tile_h - self.slope_extra + RANGE_GAP
            bx, by = self.control_region("block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
            slope_w = self.col_w["targets"] - 2 * BOX_INNER
            self.cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                                 "control_select", text=service.weight_slope_of(self.tuning_scheme),
                                 values=tuple(service.WEIGHT_SLOPES), disabled=self.slope_locked))
            self.cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                                 slope_w, CAPTION_LINE, "caption",
                                 text="damage weight slope", align="left", disabled=self.slope_locked))

    def _emit_damage_row(self, chart_indicators) -> None:
        _r = self.resolved
        if self.row_open("damage"):
            self.tuning_value_row("damage", "targets", _r.tuning.target_sizes.damage)
            if _r.flags.optimization:
                power = self.displayed_mean_damage_power()
                chart_indicators[("damage", "targets")] = (
                    _power_mean(_r.tuning.target_sizes.damage, power), _format_power(power))

    def _emit_charts(self, chart_indicators) -> None:
        for rkey, ckey, values in self.chart_tiles:
            indicator, label = chart_indicators.get((rkey, ckey), (None, ""))
            self.chart(rkey, ckey, values, indicator=indicator, indicator_label=label)

    def _emit_tuning_ranges_box(self):
        _r = self.resolved
        gtm_box = None
        if self.gtm_chart:
            chosen = _r.tuning.tun.monotone_generator_range if self.range_mode == "monotone" else _r.tuning.tun.tradeoff_generator_range
            gx, gw = self.col_x["gens"], self.col_w["gens"]
            cy = self.rows["tuning"].tile_top + self.rows["tuning"].tile_h - self.gtm_extra + RANGE_GAP
            self.cells.append(CellBox("rangetitle:tuning:gens", gx, cy + BOX_INNER, gw, BOX_TITLE_H, "boxtitle",
                                 text="tuning ranges", align="left"))
            chart_y = cy + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.cells.append(CellBox("rangechart:tuning:gens", gx, chart_y, gw, RANGE_CHART_H, "rangechart",
                                 ranges=tuple(chosen) if chosen is not None else (),
                                 values=tuple(_r.tuning.tun.generator_map),
                                 decimals=_r.flags.decimals))
            self.cells.append(CellBox("rangemode:tuning:gens", gx, chart_y + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                                 "rangemode", text=self.range_mode))
            gtm_box = (gx, cy, gw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)
        return gtm_box

    def _emit_optimization_box(self):
        _r = self.resolved
        opt_box = None
        if self.opt_ctrl:
            ox = self.col_x["targets"]
            box_w = self.col_w["targets"]
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra + RANGE_GAP)
            title_top = box_top + OPT_PAD_T
            content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP
            sym_top = content_top + ROW_H
            cap_top = sym_top + _r.scalars.ctrl_symbol_h
            cap_band = self.opt_cap_lines * CAPTION_LINE
            body_h = ROW_H + _r.scalars.ctrl_symbol_h + cap_band + OPT_PAD_B
            mean_damage_x = ox + OPT_PAD_L
            mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2
            pow_slot_x = mean_damage_x + OPT_MEAN_DAMAGE_W + OPT_COL_GAP
            pow_x = pow_slot_x + (OPT_POW_CAP_W - COL_W) / 2
            mean_damage = _power_mean(_r.tuning.target_sizes.damage, self.displayed_mean_damage_power())
            power = _format_power(self.displayed_optimization_power())
            self.cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                                 text="optimization"))
            self.cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                                 text=service.cents(mean_damage, _r.flags.decimals)))
            mean_damage_symbol = (f"⟪𝒓{_r.labels.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                          if _r.scalars.all_interval else "⟪𝐝⟫ₚ")
            if self.tuning_optimized:
                mean_damage_symbol = f"min({mean_damage_symbol})"
            if _r.flags.symbols:
                self.cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPT_MEAN_DAMAGE_W, SYMBOL_H,
                                     "symbol", text=mean_damage_symbol))
            self.cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, cap_top, OPT_MEAN_DAMAGE_W, cap_band,
                                 "caption", text=self.mean_damage_caption))
            power_locked = _r.scalars.all_interval or not _r.flags.alt_complexity
            self.cells.append(CellBox("optimization:power", pow_x, content_top, COL_W, ROW_H,
                                 "powerdisplay" if power_locked else "powerinput", text=power))
            if _r.flags.symbols:
                self.cells.append(CellBox("optimization:power:symbol", pow_x, sym_top, COL_W, SYMBOL_H,
                                     "symbol", text="𝑝"))
            self.cells.append(CellBox("optimization:power:caption", pow_x + (COL_W - OPT_POW_CAP_W) / 2, cap_top,
                                 OPT_POW_CAP_W, CAPTION_LINE, "caption", text="optimization power"))
            opt_box = (ox, box_top, box_w, OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + body_h)
        return opt_box

    def _emit_approach_box(self):
        approach_frame = None
        self.approach_box = None
        if self.show_approach:
            ax = self.col_x["targets"]
            aw = self.col_w["targets"]
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra - self.approach_extra + RANGE_GAP)
            self.cells.append(CellBox("optimization:approach:title", ax, box_top + BOX_INNER, aw, BOX_TITLE_H, "boxtitle",
                                 text="nonstandard domain approach", align="left"))
            radio_top = box_top + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.approach_box = (ax + OPT_PAD_L, radio_top,
                                 aw - OPT_PAD_L - OPT_PAD_R, APPROACH_RADIO_H)
            approach_frame = (ax, box_top, aw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H)
        return approach_frame
