from __future__ import annotations

from rtt.app import service
from rtt.app.grid_tables import (
    ALL_INTERVAL_CAPTIONS,
    ALL_INTERVAL_EQUIVALENCES,
    ALL_INTERVAL_MNEMONICS,
    ALL_INTERVAL_SYMBOLS,
    BANDS,
    EQUIVALENCES,
    FORM_EQUIVALENCES,
    MNEMONICS,
    SUBSCRIPT_C,
    SYMBOLS,
    WEIGHT_EQUIVALENCE_BY_SLOPE,
)
from rtt.app.layout import Block, CellBox, Line
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    COL_W,
    MATLABEL_H,
    ROW_H,
    SYMBOL_H,
    UNIT_H,
    WASH_PAD,
)
from rtt.app.spreadsheet_text import _bus_span, _sub, _subscript_coord


class _DecorationsMixin:
    def gridline(self, lid: str, orientation: str, pos, start, length, *, dotted: bool) -> None:
        self.lines.append(Line(lid, orientation, pos, start, length, dotted=dotted))

    def column_axis(self, key: str, prefix: str, n: int, center_open: bool) -> None:
        if key not in self.col_x:
            return
        self.fanned_columns.add(key)
        dotted = f"col:{key}" in self.collapsed
        mx, mw = self.matrix_span(key)
        cx = mx + mw / 2
        if n == 0:
            self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.fanout_y - self.branch_top_y, dotted=dotted)
            self.gridline(f"foot:{key}", "v", cx, self.fanout_y, self.total_h - self.fanout_y, dotted=dotted)
            return
        xs = [cx] * n if dotted else [center_open(i) for i in range(n)]
        for i in range(n):
            self.gridline(f"v:{prefix}:{i}", "v", xs[i], self.fanout_y, self.bot_bus_y - self.fanout_y, dotted=dotted)
        bx, bw = _bus_span(xs)
        top_end = max(self.plus_stub_x[key], bx + bw) if key in self.plus_stub_x else bx + bw
        bus_left = min(self.plus_stub_x[key], bx) if key in self.plus_stub_x else bx
        self.gridline(f"bus:{key}:top", "h", self.fanout_y, bus_left, top_end - bus_left, dotted=dotted)
        self.gridline(f"bus:{key}:bot", "h", self.bot_bus_y, bx, bw, dotted=dotted)
        self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.fanout_y - self.branch_top_y, dotted=dotted)
        self.gridline(f"foot:{key}", "v", cx, self.bot_bus_y, self.total_h - self.bot_bus_y, dotted=dotted)

    def _row_fans(self, key: str):
        return self.rows[key].nsub > 1 or key in self.row_plus_y

    def row_axis(self, key: str) -> None:
        n = self.rows[key].nsub
        folded = f"row:{key}" in self.collapsed
        cy = self.rows[key].y + self.rows[key].h / 2
        ys = [cy] * n if folded else [self.rows[key].y + i * ROW_H + ROW_H / 2 for i in range(n)]
        left_bus_x = self.node_edge + self.FAN if (self._row_fans(key) and not folded) else self.node_edge
        for i in range(n):
            self.gridline(f"h:{key}:{i}", "h", ys[i], left_bus_x, self.right_bus_x - left_bus_x, dotted=folded)
        bus_y, bus_h = _bus_span(ys)
        left_bottom = self.row_plus_y[key] if key in self.row_plus_y else bus_y + bus_h
        self.gridline(f"vbar:{key}:left", "v", left_bus_x, bus_y, left_bottom - bus_y, dotted=folded)
        self.gridline(f"vbar:{key}:right", "v", self.right_bus_x, bus_y, bus_h, dotted=folded)
        self.gridline(f"trunk:{key}", "h", cy, self.node_edge, left_bus_x - self.node_edge, dotted=folded)
        self.gridline(f"foot:{key}", "h", cy, self.right_bus_x, self.total_w - self.right_bus_x, dotted=folded)

    def panel(self, bid: str, ckey: str, rkey: str) -> None:
        if ckey not in self.col_x or rkey not in self.rows:
            return
        self.blocks.append(Block(bid, *self.panel_rect(ckey, rkey)))

    def _prescale_matlabel_top(self, i: int):
        return self.rows["prescaling"].y + i * ROW_H

    def _matlabel_group_count(self):
        _r = self.resolved
        return {"gens": _r.dims.r, "primes": _r.dims.d, "commas": _r.dims.nc + _r.dims.nu, "targets": _r.dims.k,
                "held": _r.dims.nh, "detempering": _r.dims.r, "interest": _r.dims.mi,
                "canongens": _r.dims.rc, "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}

    def _emit_matrix_row_labels(self) -> None:
        _r = self.resolved
        row_top = {
            ("mapping", "primes"): self.map_top,
            ("canon", "primes"): self.canon_top,
            ("mapping", "canongens"): self.map_top,
            ("vectors", "primes"): self.vec_top,
            ("projection", "primes"): self.proj_top,
            ("projection", "ssprimes"): self.proj_top,

            ("prescaling", "primes"): self._prescale_matlabel_top,
            ("prescaling", "ssprimes"): self._prescale_matlabel_top,
            ("ss_mapping", "ssprimes"): self.ss_map_top,
            ("ss_mapping", "primes"): self.ss_map_top,
            ("ss_vectors", "ssprimes"): self.ss_vec_top,
            ("ss_projection", "ssprimes"): self.ss_proj_top,
        }
        row_count = {("mapping", "primes"): _r.dims.r,
                     ("canon", "primes"): _r.dims.rc,
                     ("mapping", "canongens"): _r.dims.r,
                     ("vectors", "primes"): _r.dims.d,
                     ("projection", "primes"): _r.dims.d,
                     ("projection", "ssprimes"): _r.dims.d,

                     ("prescaling", "primes"): self.prescale_rows + self.size_rows,
                     ("prescaling", "ssprimes"): self.prescale_rows + self.size_rows,
                     ("ss_mapping", "ssprimes"): _r.dims.rL,
                     ("ss_mapping", "primes"): _r.dims.rL,
                     ("ss_vectors", "ssprimes"): _r.dims.dL,
                     ("ss_projection", "ssprimes"): _r.dims.dL}
        for (rkey, ckey), glyph in _r.labels.row_labels.items():
            if not self.tile_open(rkey, ckey):
                continue
            top = row_top[(rkey, ckey)]
            for i in range(row_count[(rkey, ckey)]):
                size_row = rkey == "prescaling" and i == self.prescale_rows and self.size_rows
                g = self._form_subscripted(glyph, rkey, ckey)
                text = "𝒛" if size_row else f"{g}{_sub(i + 1)}"
                self.cells.append(CellBox(
                    f"matlabel:row:{rkey}:{ckey}:{i}",
                    self.content_x[ckey] + self.etpick_left_pad(ckey) + self.handle_gutter_w(ckey), top(i),
                    self.matlabel_gutter_w(ckey), ROW_H,
                    "matlabel", text=text,
                ))

    def _emit_matrix_col_labels(self) -> None:
        _r = self.resolved
        group_count = self._matlabel_group_count()
        for (rkey, ckey), label in _r.labels.col_labels.items():
            if ckey not in group_count or rkey not in self.rows or self.rows[rkey].matlabel_top is None:
                continue
            if not self.tile_open(rkey, ckey):
                continue
            col_label = label
            if (rkey, ckey) == ("weight", "targets") and self.all_interval_simplicity_weight:
                col_label = self._weight_simplicity_header
            left = self.group_left[ckey]
            y = self.rows[rkey].matlabel_top
            for i in range(group_count[ckey]):
                glyph = col_label if callable(col_label) else self._form_subscripted(col_label, rkey, ckey)
                text = glyph(i) if callable(glyph) else f"{glyph}{_sub(i + 1)}"
                if _r.unchanged.shown and ckey == "commas":
                    text = text.replace("𝐜", "𝐯")
                x = left[self.comma_value_pos(i)] if ckey == "commas" else left[i]
                self.cells.append(CellBox(
                    f"matlabel:col:{rkey}:{ckey}:{i}",
                    x, y, COL_W, MATLABEL_H,
                    "matlabel", text=text,
                ))

    def _emit_matrix_labels(self) -> None:
        _r = self.resolved
        if not _r.flags.header_symbols:
            return
        self._emit_matrix_row_labels()
        self._emit_matrix_col_labels()

    def _emit_axes(self) -> None:
        self.bot_bus_y = self.total_h - self.FAN

        self.fanned_columns = set()

        for key in self.group_left:
            self.column_axis(key, self.group_elem[key], self.group_n[key],
                        lambda i, k=key: self.group_left[k][i] + COL_W / 2)

        for key in self.col_x:
            if key in self.fanned_columns:
                continue
            cx = self.col_x[key] + self.col_w[key] / 2
            self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.total_h - self.branch_top_y,
                     dotted=f"col:{key}" in self.collapsed)

        self.right_bus_x = self.total_w - self.FAN

        for key in self.rows:
            if self._row_fans(key):
                self.row_axis(key)
            else:
                self.gridline(f"h:{key}", "h", self.rows[key].y + self.rows[key].h / 2, self.node_edge, self.total_w - self.node_edge,
                         dotted=f"row:{key}" in self.collapsed)

    def _emit_panels(self, gtm_box, opt_box, approach_frame) -> None:
        for bid, rkey, ckey in self.tiles:
            if (rkey, ckey) in self.declared_tiles:
                self.panel(bid, ckey, rkey)
        self.blocks.extend(self._control_region_boxes)
        if gtm_box is not None:
            self.blocks.append(Block("block:tuning:rangesbox", *gtm_box, boxed=True))
        if opt_box is not None:
            self.blocks.append(Block("block:optimization:box", *opt_box, boxed=True))
        if approach_frame is not None:
            self.blocks.append(Block("block:optimization:approach:box", *approach_frame, boxed=True))

    def _wash_segments(self, rkey: str, ckey: str):
        if (rkey, ckey) == ("counts", "gens") and "canongens" in self.col_x:
            return [("gens", self.tile_box("gens"), self.tile_groups("counts", "gens")),
                    ("canongens", self.tile_box("canongens"), self.tile_groups("counts", "canongens"))]
        return [(ckey, self.tile_span_box(rkey, ckey), self.tile_groups(rkey, ckey))]

    def _wash_bands(self):
        bands = []
        for _bid, rkey, ckey in self.tiles:
            if (rkey, ckey) not in self.declared_tiles or not self.tile_open(rkey, ckey):
                continue
            y, h = self.rows[rkey].tile_top - WASH_PAD, self.rows[rkey].tile_h + 2 * WASH_PAD
            for seg_key, (tile_x, tile_w), seg_groups in self._wash_segments(rkey, ckey):
                groups = sorted(g for g in seg_groups if self.settings.get(f"{g}_colorization"))
                if not groups:
                    continue
                x, w = tile_x - WASH_PAD, tile_w + 2 * WASH_PAD
                if len(groups) == 3:
                    bands.append((f"white:{rkey}:{seg_key}", x, y, w, h, None))
                else:
                    for group in groups:
                        bands.append((f"{group}:{rkey}:{seg_key}", x, y, w, h, group))
        return bands

    def _emit_washes(self) -> None:
        if not (self.col_x and self.rows):
            return
        bands = self._wash_bands()
        for bid, x, y, w, h, _ in bands:
            self.blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
        for bid, x, y, w, h, group in bands:
            if group is not None:
                self.blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))

    def _caption_equivalences(self, ai: bool, slope) -> dict:
        _r = self.resolved
        equivalences = {**EQUIVALENCES,
                        ("weight", "targets"): "" if _r.scalars.custom_weights_active else WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                        ("prescaling", "ssprimes" if _r.flags.superspace else "primes"): _r.labels.prescaler_equivalence,
                        **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                        **(FORM_EQUIVALENCES if _r.flags.form_subscript else {}),
                        **({("mapping", "primes"): f" = 𝐹𝑀{SUBSCRIPT_C}"} if _r.flags.canon else {}),
                        **({("vectors", "commas"): " = C|U", ("mapping", "commas"): ""}
                           if _r.unchanged.shown else {})}
        if _r.flags.superspace:
            equivalences[("projection", "primes")] = (
                equivalences[("projection", "primes")] + self._projection_superspace_tail())
        if ai:
            if not _r.scalars.prescaler_is_matrix and not self.size_factor:
                equivalences[("complexity", "targets")] = f" = diag({_r.labels.prescaler_symbol})"
                equivalences[("weight", "targets")] = f" = diag({_r.labels.prescaler_symbol})⁻¹"
            equivalences[("damage", "targets")] = f" = |𝒓|{_r.labels.prescaler_symbol}⁻¹"
        if not _r.flags.weighting:
            equivalences[("damage", "targets")] = " = |𝒓|" if ai else " = |𝐞|"
        return equivalences

    def _emit_tile_symbol(self, rkey: str, ckey: str, cy: float) -> float:
        _r = self.resolved
        cy += BAND_GAP
        equiv = self._caption_equivs.get((rkey, ckey), "") if _r.flags.equiv else ""
        base_symbol = _r.labels.prescaling_symbols.get((rkey, ckey), SYMBOLS.get((rkey, ckey), ""))
        if self._caption_ai and (rkey, ckey) in ALL_INTERVAL_SYMBOLS:
            base_symbol = ALL_INTERVAL_SYMBOLS[(rkey, ckey)]
        if _r.unchanged.shown and ckey == "commas":
            base_symbol = base_symbol.replace(SUBSCRIPT_C, "\x00").replace("C", "V").replace("\x00", SUBSCRIPT_C)
        base_symbol = self._form_subscripted(base_symbol, rkey, ckey)
        glyph = base_symbol if (_r.flags.symbols or equiv) else ""
        if glyph or equiv:
            self.cells.append(CellBox(f"symbol:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
        return cy + SYMBOL_H

    def _emit_unchanged_counts_caption(self, rkey: str, cy: float) -> None:
        _r = self.resolved
        comma_half_w = _r.dims.nc * COL_W + _r.unchanged.empty_comma_w
        if comma_half_w:
            comma_half_x = self.commas_x if _r.unchanged.empty_comma_w else self.comma_left(0)
            self.cells.append(CellBox("caption:counts:commas", comma_half_x, cy, comma_half_w,
                                 self.rows[rkey].cap, "caption", text="nullity"))
        self.cells.append(CellBox("caption:counts:commas:u", self.comma_left(_r.dims.nc_shown), cy, _r.dims.nu * COL_W,
                             self.rows[rkey].cap, "caption", text="unchanged interval count"))

    def _emit_tile_caption(self, rkey: str, ckey: str, name: str, cy: float) -> None:
        _r = self.resolved
        kw = MNEMONICS.get((rkey, ckey)) if _r.flags.mnemonics else None
        underlines = ((name.index(kw), 1),) if (kw and kw in name) else ()
        if _r.flags.mnemonics and self._caption_ai:
            underlines += tuple((name.index(w), 1)
                                for w in ALL_INTERVAL_MNEMONICS.get((rkey, ckey), ()) if w in name)
        cap_x, cap_w = self.tile_span_box(rkey, ckey)
        self.cells.append(CellBox(f"caption:{rkey}:{ckey}", cap_x, cy, cap_w, self.rows[rkey].cap,
                             "caption", text=name, underlines=underlines))

    def _emit_tile_units(self, rkey: str, ckey: str) -> None:
        _r = self.resolved
        unit = self.tile_unit(rkey, ckey)
        if unit and not (rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")):
            unit = _subscript_coord(unit, "p", _r.labels.domain_label)
        if _r.flags.units and unit:
            uy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey] + self.rows[rkey].sym + self.rows[rkey].cap
            self.cells.append(CellBox(f"units:{rkey}:{ckey}", self.col_x[ckey], uy, self.col_w[ckey], UNIT_H,
                                 "units", text=f"units: {unit}"))

    def _emit_tile_symbols_captions(self, rkey: str, ckey: str, name: str) -> None:
        _r = self.resolved
        if self._caption_ai and (rkey, ckey) in ALL_INTERVAL_CAPTIONS:
            name = ALL_INTERVAL_CAPTIONS[(rkey, ckey)]
        cy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey]
        if (_r.flags.symbols or _r.flags.equiv) and rkey in BANDS["symbol"].rows:
            cy = self._emit_tile_symbol(rkey, ckey, cy)
        if _r.flags.captions and _r.unchanged.shown and (rkey, ckey) == ("counts", "commas"):
            self._emit_unchanged_counts_caption(rkey, cy)
            return
        if _r.flags.captions:
            self._emit_tile_caption(rkey, ckey, name, cy)
        self._emit_tile_units(rkey, ckey)

    def _emit_symbols_captions(self) -> None:
        _r = self.resolved
        self._caption_ai = service.is_all_interval(self.tuning_scheme)
        slope = service.damage_weight_slope(self.tuning_scheme)
        self._caption_equivs = self._caption_equivalences(self._caption_ai, slope)
        for (rkey, ckey), name in _r.labels.captions.items():
            if ckey == "interest" and not _r.interest.vectors:
                continue
            if not self.tile_open(rkey, ckey):
                continue
            self._emit_tile_symbols_captions(rkey, ckey, name)
