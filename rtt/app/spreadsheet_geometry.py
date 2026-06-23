from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from rtt.app import service
from rtt.app.grid_tables import (
    BANDS,
    EDITABLE_PTEXT,
    EDITABLE_PTEXT_ROWS,
    EQUIVALENCES,
    FORM_CHOOSERS,
    FORM_EQUIVALENCES,
    FORM_SUBSCRIPT_GENS,
    FORM_SUBSCRIPT_ROWS,
    PRESET_COPIES,
    PRESETS,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    SYMBOLS,
    UNITS,
)
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BOX_INNER,
    BOX_OUTER,
    BRACKET_W,
    CAPTION_LINE,
    CBOX_NODROP_W,
    CBOX_W,
    COL_W,
    CTRL_LABEL_GAP,
    FRAME_GAP,
    FRAME_H,
    LBOX_DIM_W,
    MAX_CAPTION_LINES,
    OPT_BOX_MIN_W,
    PAD,
    PBOX_W,
    PRESET_H,
    PRESET_W,
    PTEXT_EDIT_H,
    PTEXT_H,
    ROW_H,
    SCHEME_BTN_SQ,
    SCHEME_CTRL_W,
    SYMBOL_FONT,
    TARGET_PRESET_W,
    TBOX_W,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_text import (
    _log_operand,
    _min_width_for_lines,
    _sub,
    _subscript_coord,
    _wrap_lines,
    pending_token,
)


class _GeometryMixin:
    def superspace_tun(self):
        _r = self.resolved
        if self._ss_tun is None:
            ss_override = self.superspace_generator_tuning if _r.flags.superspace_generators else None
            self._ss_tun = service.superspace_tuning(self.state, self.tuning_scheme, self.nonprime_approach,
                                                     generator_override=ss_override)
        return self._ss_tun

    def _caption_floor(self, key: str):
        _r = self.resolved
        if not _r.flags.captions:
            return 0
        return max((_min_width_for_lines(_r.labels.captions[(rk, key)], MAX_CAPTION_LINES)
                    for rk in self.present_caption_rows
                    if (rk, key) in _r.labels.captions and (rk, key) in self.declared_tiles), default=0)

    def _projection_superspace_tail(self) -> str:
        _r = self.resolved
        return f" = G{SUBSCRIPT_L}→ₛ𝑀ₛ→{SUBSCRIPT_L}" if _r.flags.superspace else ""

    def _symbol_floor(self, key: str):
        _r = self.resolved
        if not (_r.flags.symbols or _r.flags.equiv):
            return 0
        floor = 0
        for (rkey, ckey), glyph in SYMBOLS.items():
            if ckey != key or (rkey, ckey) not in self.declared_tiles:
                continue
            equiv = ""
            if _r.flags.equiv:
                equiv = EQUIVALENCES.get((rkey, ckey), "")
                if _r.flags.form_subscript and (rkey, ckey) in FORM_EQUIVALENCES:
                    equiv = FORM_EQUIVALENCES[(rkey, ckey)]
                if (rkey, ckey) == ("projection", "primes"):
                    equiv += self._projection_superspace_tail()
            sub_glyph = self._form_subscripted(glyph, rkey, ckey)
            floor = max(floor, _min_width_for_lines(sub_glyph + equiv, 1, SYMBOL_FONT))
        return floor

    def _form_subscripted(self, glyph: str, rkey: str, ckey: str) -> str:
        _r = self.resolved
        if (glyph and _r.flags.form_subscript
                and (rkey in FORM_SUBSCRIPT_ROWS or (rkey, ckey) in FORM_SUBSCRIPT_GENS)):
            return glyph[:1] + SUBSCRIPT_C + glyph[1:]
        return glyph

    def _control_floor(self, key: str):
        _r = self.resolved
        floor = 0
        if key == ("ssprimes" if _r.flags.superspace else "primes") and self._lbox_show:
            floor = PBOX_W if _r.flags.presets else LBOX_DIM_W + 2 * BOX_INNER
        if key == "targets" and self._cbox_show:
            cbox_w = CBOX_W if _r.flags.presets else CBOX_NODROP_W
            floor = max(floor, cbox_w + 2 * BOX_INNER)
        if key == "targets" and _r.flags.presets and self.settings["all_interval"]:
            floor = max(floor, TBOX_W)
        if (key == "targets" and _r.flags.optimization and "row:damage" not in self.collapsed
                and "tile:damage:targets" not in self.collapsed):
            floor = max(floor, OPT_BOX_MIN_W)
        labels = ([lbl for _n, _r, c, lbl in PRESETS + PRESET_COPIES if c == key and lbl] if _r.flags.presets else [])
        labels += [lbl for _n, _r, c, lbl in FORM_CHOOSERS if c == key and lbl] if _r.flags.form_controls else []
        if labels:
            floor = max(floor, BOX_OUTER + BOX_INNER + 6 + max(_min_width_for_lines(lbl, 1) for lbl in labels))
        if key in ("primes", "gens") and self.settings["projection"]:
            floor = max(floor, 2 * BOX_OUTER + SCHEME_CTRL_W)
        return floor

    def content_box(self, key: str):
        return self.content_x[key], self.content_w[key]

    def tile_box(self, key: str):
        return self.col_x[key], self.col_w[key]

    def tile_span_box(self, rkey: str, ckey: str):
        if (rkey, ckey) == ("counts", "gens") and "canongens" in self.col_x:
            x = self.col_x["canongens"]
            return x, self.col_x["gens"] + self.col_w["gens"] - x
        return self.tile_box(ckey)

    def displayed_optimization_power(self) -> float:
        if service.is_all_interval(self.tuning_scheme):
            return float("inf")
        return service.optimization_power(self.tuning_scheme)

    def displayed_mean_damage_power(self) -> float:
        if service.is_all_interval(self.tuning_scheme):
            return service.dual_norm_power(self.tuning_scheme)
        return service.optimization_power(self.tuning_scheme)

    def col_open(self, key: str) -> bool:
        return key in self.col_x and f"col:{key}" not in self.collapsed

    def _commas_band_w(self, nc_count: int):
        _r = self.resolved
        nv = nc_count + _r.dims.nu
        split = V_SPLIT_GAP if (_r.unchanged.shown and nc_count > 0) else 0
        empty = (_min_width_for_lines("nullity", 1)
                 if (_r.unchanged.shown and nc_count == 0) else 0)
        return 2 * BRACKET_W + nv * COL_W + split + empty

    def _caption_wrap_w(self, ckey: str):
        _r = self.resolved
        if ckey == "commas" and _r.ghosts.comma:
            resting = self._commas_band_w(_r.dims.nc + (1 if _r.commas.pending is not None else 0))
            return max(resting, self._caption_floor(ckey),
                       self._control_floor(ckey), self._symbol_floor(ckey))
        return self.open_col_w[ckey]

    def caption_band(self, key: str, folded: bool):
        _r = self.resolved
        if not (_r.flags.captions and key in BANDS["caption"].rows and not folded):
            return 0
        lines = [_wrap_lines(_r.labels.captions[(key, c)], self._caption_wrap_w(c)) for c in self.col_x
                 if (key, c) in _r.labels.captions and (key, c) in self.declared_tiles]
        if key == "counts" and _r.unchanged.shown and "commas" in self.col_x:
            lines.append(_wrap_lines("unchanged interval count", _r.dims.nu * COL_W))
            lines.append(_wrap_lines("nullity", _r.dims.nc * COL_W + _r.unchanged.empty_comma_w))
        return max(lines, default=1) * CAPTION_LINE

    def ptext_editable(self, rkey: str, ckey: str) -> bool:
        _r = self.resolved
        if rkey == "prescaling":
            return (rkey, ckey) == ("prescaling", "ssprimes" if _r.flags.superspace else "primes")
        if rkey == "tuning" and _r.flags.superspace_generators:
            return ckey == "ssgens"
        return (rkey, ckey) in EDITABLE_PTEXT

    def ptext_height(self, rkey: str, ckey: str):
        return PTEXT_EDIT_H if self.ptext_editable(rkey, ckey) else PTEXT_H

    def ptext_band(self, key: str, folded: bool):
        if folded or not any(rk == key for rk, _ck in self.ptext_strings):
            return 0
        return PTEXT_EDIT_H if key in EDITABLE_PTEXT_ROWS else PTEXT_H

    def control_dims(self, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):
        dropdown_w = max(40, min(self.col_w[ckey] - 2 * BOX_INNER, cap_w))
        label_h = CAPTION_LINE if label else 0
        box_h = 2 * BOX_INNER + PRESET_H + label_h
        box_h += (SCHEME_BTN_SQ + CTRL_LABEL_GAP) if scheme_btn else 0
        if form_label is not None:
            box_h += BAND_GAP + PRESET_H + (CAPTION_LINE if form_label else 0)
        return dropdown_w, label_h, box_h

    def control_band_h(self, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):
        return 2 * BOX_OUTER + self.control_dims(ckey, cap_w, label, scheme_btn, form_label)[2]

    def preset_cap(self, name: str):
        return TARGET_PRESET_W if name == "target" else PRESET_W

    def preset_band_h(self, key: str):
        return max((self.control_band_h(ckey, self.preset_cap(name), label, scheme_btn=(name == "projection"),
                                         form_label=self._preset_form_label(name, rk, ckey))
                    for name, rk, ckey, label in PRESETS + PRESET_COPIES
                    if rk == key and ckey in self.col_w), default=0)

    def formchooser_band_h(self, key: str):
        return max((self.control_band_h(ckey, PRESET_W, label)
                    for name, rk, ckey, label in FORM_CHOOSERS if rk == key and ckey in self.col_w), default=0)

    def row_open(self, key: str) -> bool:
        return key in self.rows and f"row:{key}" not in self.collapsed

    def tile_open(self, rkey: str, ckey: str) -> bool:
        return ((rkey, ckey) in self.declared_tiles and self.row_open(rkey) and self.col_open(ckey)
                and f"tile:{rkey}:{ckey}" not in self.collapsed)

    def tile_unit(self, rkey: str, ckey: str):
        _r = self.resolved
        base = UNITS.get((rkey, ckey))
        if base is None:
            return ""
        if rkey == "complexity":
            return base.replace("(C)", _r.scalars.complexity_unit)
        if rkey == "weight":
            return _r.scalars.weight_unit
        if rkey == "damage":
            return _r.scalars.damage_unit
        return base

    def cell_unit(self, rkey: str, ckey: str, *, gen=None, prime=None, elem=None):
        _r = self.resolved
        if not self.show_cell_units:
            return ""
        u = self.tile_unit(rkey, ckey)
        superspace = rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")
        if gen is not None:
            if superspace:
                u = u.replace(f"g{SUBSCRIPT_L}", f"g{SUBSCRIPT_L}{_sub(gen + 1)}")
            elif f"g{SUBSCRIPT_C}" in u:
                gc = f"g{SUBSCRIPT_C}"
                u = _subscript_coord(u.replace(gc, "\x00"), "g", f"g{_sub(gen + 1)}").replace("\x00", f"{gc}{_sub(gen + 1)}")
            else:
                u = _subscript_coord(u, "g", f"g{_sub(gen + 1)}")
        if prime is not None:
            coord = "p" if superspace else _r.labels.domain_label
            u = _subscript_coord(u, "p", f"{coord}{_sub(prime + 1)}")
        if elem is not None:
            u = _subscript_coord(u, _r.labels.domain_label, f"{_r.labels.domain_label}{_sub(elem + 1)}")
        return u

    def matlabel_gutter_w(self, group_key: str):
        if group_key == "primes":
            return self.matlabel_primes_w
        if group_key == "ssprimes":
            return self.matlabel_ssprimes_w
        return self.matlabel_other_w.get(group_key, 0)

    def handle_gutter_w(self, group_key: str):
        return self.row_handle_w if group_key == "primes" else 0

    def etpick_left_pad(self, group_key: str):
        if group_key != "primes" or not self.etpick_w:
            return 0
        return max(0, self.etpick_w - self.handle_gutter_w(group_key) - self.matlabel_gutter_w(group_key))

    def outer_gutter_w(self, group_key: str):
        return self.etpick_left_pad(group_key) + self.handle_gutter_w(group_key) + self.matlabel_gutter_w(group_key)

    def matrix_span(self, group_key: str):
        _r = self.resolved
        x, w = self.content_box(group_key)
        mx = self.outer_gutter_w(group_key)
        x, w = x + mx, w - 2 * mx
        if group_key == "commas" and _r.unchanged.empty_comma_w:
            x, w = x + _r.unchanged.empty_comma_w, w - _r.unchanged.empty_comma_w
        return x, w

    def _weight_simplicity_header(self, i: int):
        _r = self.resolved
        symbol = f"w{_sub(i + 1)}"
        if not _r.flags.equiv:
            return symbol
        return f"{symbol} = c{_sub(i + 1)}⁻¹"

    def prime_left(self, p: int):
        return self.primes_x + self.outer_gutter_w("primes") + BRACKET_W + p * COL_W

    @staticmethod
    def _element_cell_kind(text: str):
        return "elementratio" if "/" in text else "elementcell"

    def comma_left(self, c: int):
        _r = self.resolved
        gap = V_SPLIT_GAP if (_r.unchanged.shown and 0 < _r.dims.nc_shown <= c) else 0
        return self.commas_x + BRACKET_W + _r.unchanged.empty_comma_w + c * COL_W + gap

    def comma_value_pos(self, i: int):
        _r = self.resolved
        return i if i < _r.dims.nc else i + (_r.dims.nc_shown - _r.dims.nc)

    def target_left(self, j: int):
        return self.targets_x + BRACKET_W + j * COL_W

    def interest_left(self, i: int):
        return self.interest_x + BRACKET_W + i * COL_W

    def held_left(self, i: int):
        return self.held_x + BRACKET_W + i * COL_W

    def detempering_left(self, i: int):
        return self.detempering_x + BRACKET_W + i * COL_W

    def gen_left(self, g: int):
        return self.content_x["gens"] + self.outer_gutter_w("gens") + BRACKET_W + g * COL_W

    def canongen_left(self, g: int):
        return self.canongens_x + self.outer_gutter_w("canongens") + BRACKET_W + g * COL_W

    def ss_gen_left(self, g: int):
        return self.ssgens_x + BRACKET_W + g * COL_W

    def ss_prime_left(self, p: int):
        return self.ssprimes_x + self.outer_gutter_w("ssprimes") + BRACKET_W + p * COL_W

    def map_top(self, i: int):
        return self.rows["mapping"].y + i * ROW_H

    def proj_top(self, i: int):
        return self.rows["projection"].y + i * ROW_H

    def canon_top(self, i: int):
        return self.rows["canon"].y + i * ROW_H

    def vec_top(self, p: int):
        return self.rows["vectors"].y + p * ROW_H

    def ss_vec_top(self, p: int):
        return self.rows["ss_vectors"].y + p * ROW_H

    def ss_map_top(self, i: int):
        return self.rows["ss_mapping"].y + i * ROW_H

    def ss_proj_top(self, i: int):
        return self.rows["ss_projection"].y + i * ROW_H

    def sub_axis_x(self, ckey: str, i: int):
        return self.group_left[ckey](i) + COL_W / 2

    def col_plus_x(self, ckey: str):
        _r = self.resolved
        n = self.group_n[ckey]
        if n == 0:
            mx, mw = self.matrix_span(ckey)
            return mx + mw / 2
        if ckey == "commas" and _r.unchanged.shown:
            if _r.dims.nc_shown == 0:
                return self.commas_x + BRACKET_W + _r.unchanged.empty_comma_w / 2
            return self.comma_left(_r.dims.nc_shown - 1) + COL_W + V_SPLIT_GAP / 2
        return self.sub_axis_x(ckey, n - 1) + COL_W

    def _plus_shows(self, ckey: str) -> bool:
        _r = self.resolved
        if ckey in ("interest", "held"):
            return self.col_open(ckey) and (self.row_open("quantities") or self.row_open("vectors"))
        if ckey == "targets":
            return (self.tile_open("quantities", "targets") or self.tile_open("vectors", "targets")) and not _r.scalars.all_interval
        if ckey == "gens":
            return self.tile_open("quantities", "gens") and self.state.n > 0
        if ckey == "primes":
            return self.tile_open("quantities", "primes") and (_r.flags.nonstandard_domain or _r.scalars.standard_domain)
        if ckey == "commas":
            return self.tile_open("quantities", "commas") or self.tile_open("vectors", "commas")
        return self.tile_open("quantities", ckey) or self.tile_open("vectors", ckey)

    def closed_form_operand(self, key, group, i, value=None):
        _r = self.resolved
        if key == "just":
            ratio = self.group_ratio[group](i)
            return _log_operand(ratio) if ratio is not None else None
        if group == "commas" and key == "retune" and i < _r.dims.nc:
            recip = 1 / Fraction(_r.commas.ratios[i])
            return _log_operand(f"{recip.numerator}/{recip.denominator}")
        if key in ("tuning", "retune") and value is not None:
            if group in ("ssprimes", "ssgens"):
                return self._ss_closed_form_operand(key, group, i, value)
            closed_form = self._closed_form()
            vector = self._tempered_vector(group, i) if closed_form is not None else None
            if vector is not None:
                return (closed_form.tempered_operand(vector, value) if key == "tuning"
                        else closed_form.retune_operand(vector, value))
        return None

    def _ss_closed_form_operand(self, key, group, i, value):
        ss = self._ss_closed_form()
        if ss is None:
            return None
        if group == "ssgens":
            return ss.generator_operand(i, value) if key == "tuning" else None
        vector = tuple(1 if k == i else 0 for k in range(len(ss.primes)))
        return (ss.tempered_operand(vector, value) if key == "tuning"
                else ss.retune_operand(vector, value))

    def _closed_form(self):
        _r = self.resolved
        if not hasattr(self, "_closed_form_cache"):
            self._closed_form_cache = (
                None
                if not _r.flags.math or _r.tuning.from_generators
                else service.closed_form_tuning(
                    self.state.mapping, self.tuning_scheme, _r.dims.elements, self.nonprime_approach,
                    held=_r.held.ratios, prescaler_override=self.custom_prescaler,
                    targets=_r.tuning.optimum_target_override, weights_override=self.custom_weights)
            )
        return self._closed_form_cache

    def _ss_closed_form(self):
        _r = self.resolved
        if not hasattr(self, "_ss_closed_form_cache"):
            self._ss_closed_form_cache = (
                service.closed_form_superspace_tuning(self.state, self.tuning_scheme)
                if _r.flags.math and _r.flags.superspace else None
            )
        return self._ss_closed_form_cache

    def _tempered_vector(self, group, i):
        _r = self.resolved
        if group == "primes":
            return tuple(1 if k == i else 0 for k in range(_r.dims.d))
        if group == "commas":
            return self._comma_tempered_vector(i)
        seqs = {"targets": _r.targets.vectors, "interest": _r.interest.vectors,
                "held": _r.held.vectors, "detempering": _r.detempering.vectors}
        seq = seqs.get(group)
        if seq is None:
            return None
        return seq[i] if i < len(seq) else None

    def _comma_tempered_vector(self, i):
        _r = self.resolved
        if i < _r.dims.nc:
            return self.state.comma_basis[i]
        j = i - _r.dims.nc
        return _r.unchanged.basis[j] if _r.unchanged.basis and j < len(_r.unchanged.basis) else None

    def col_token(self, group: str, i: int):
        _r = self.resolved
        if group == "commas" and i >= _r.dims.nc:
            return f"u{i - _r.dims.nc}"
        pairs = _r.col_ids.get(group)
        return i if pairs is None else pairs[i][0]

    def pending_col_token(self, group: str):
        _r = self.resolved
        return pending_token([tok for tok, _ in _r.col_ids[group]])

    def _pending_draft_idx(self, group: str):
        _r = self.resolved
        return {"commas": (_r.scalars.comma_draft or None, _r.dims.nc), "targets": (_r.targets.pending, _r.dims.k),
                "held": (_r.held.pending, _r.dims.nh), "interest": (_r.interest.pending, _r.dims.mi)}.get(group)

    def _voice(self, tile, idx, cents) -> None:
        if cents is None:
            return
        self.cells[-1] = replace(self.cells[-1], audio=(tile, int(idx), float(cents)))

    def panel_rect(self, ckey: str, rkey: str):
        tile_c = f"tile:{rkey}:{ckey}" in self.collapsed
        col_c = f"col:{ckey}" in self.collapsed or tile_c
        row_c = f"row:{rkey}" in self.collapsed or tile_c
        cx, cw = self.tile_span_box(rkey, ckey)
        ch, cy = self.rows[rkey].tile_h, self.rows[rkey].tile_top
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        return bx - px, by - py, w + 2 * px, h + 2 * py

    def cpick_band_y(self, rkey):
        return self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame

    def ptext_band_y(self, rkey: str):
        return self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey] + self.rows[rkey].sym + self.rows[rkey].cap + self.rows[rkey].units

    def frame_top_y(self, rkey: str):
        return self.rows[rkey].y - FRAME_H - FRAME_GAP

    def frame_brace_y(self, rkey: str):
        return self.rows[rkey].y + self.rows[rkey].h + FRAME_GAP
