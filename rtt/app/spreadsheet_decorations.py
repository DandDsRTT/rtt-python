from __future__ import annotations

from rtt.app import service
from rtt.app.grid_tables import (
    ALL_INTERVAL_CAPTIONS,
    ALL_INTERVAL_EQUIVALENCES,
    ALL_INTERVAL_MNEMONICS,
    ALL_INTERVAL_SYMBOLS,
    EQUIVALENCES,
    FORM_EQUIVALENCES,
    MNEMONICS,
    SUBSCRIPT_C,
    SYMBOLED_ROWS,
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

    def _emit_matrix_labels(self) -> None:
        if self.show_header_symbols:
            group_count = {"gens": self.r, "primes": self.d, "commas": self.nc + self.nu, "targets": self.k,
                           "held": self.nh, "detempering": self.r, "interest": self.mi,
                           "canongens": self.rc, "ssgens": self.rL, "ssprimes": self.dL}
            _prescale_top = lambda i: self.rows["prescaling"].y + i * ROW_H
            row_top = {
                ("mapping", "primes"): self.map_top,
                ("canon", "primes"): self.canon_top,
                ("mapping", "canongens"): self.map_top,
                ("vectors", "primes"): self.vec_top,
                ("projection", "primes"): self.proj_top,
                ("projection", "ssprimes"): self.proj_top,

                ("prescaling", "primes"): _prescale_top,
                ("prescaling", "ssprimes"): _prescale_top,
                ("ss_mapping", "ssprimes"): self.ss_map_top,
                ("ss_mapping", "primes"): self.ss_map_top,
                ("ss_vectors", "ssprimes"): self.ss_vec_top,
                ("ss_projection", "ssprimes"): self.ss_proj_top,
            }
            row_count = {("mapping", "primes"): self.r,
                         ("canon", "primes"): self.rc,
                         ("mapping", "canongens"): self.r,
                         ("vectors", "primes"): self.d,
                         ("projection", "primes"): self.d,
                         ("projection", "ssprimes"): self.d,

                         ("prescaling", "primes"): self.prescale_rows + self.size_rows,
                         ("prescaling", "ssprimes"): self.prescale_rows + self.size_rows,
                         ("ss_mapping", "ssprimes"): self.rL,
                         ("ss_mapping", "primes"): self.rL,
                         ("ss_vectors", "ssprimes"): self.dL,
                         ("ss_projection", "ssprimes"): self.dL}
            for (rkey, ckey), glyph in self.row_labels.items():
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
            for (rkey, ckey), label in self.col_labels.items():
                if ckey not in group_count or rkey not in self.rows or self.rows[rkey].matlabel_top is None:
                    continue
                if not self.tile_open(rkey, ckey):
                    continue
                if (rkey, ckey) == ("weight", "targets") and self.all_interval_simplicity_weight:
                    label = self._weight_simplicity_header
                left = self.group_left[ckey]
                y = self.rows[rkey].matlabel_top
                for i in range(group_count[ckey]):
                    glyph = label if callable(label) else self._form_subscripted(label, rkey, ckey)
                    text = glyph(i) if callable(glyph) else f"{glyph}{_sub(i + 1)}"
                    if self.show_unchanged and ckey == "commas":
                        text = text.replace("𝐜", "𝐯")
                    x = left(self.comma_value_pos(i)) if ckey == "commas" else left(i)
                    self.cells.append(CellBox(
                        f"matlabel:col:{rkey}:{ckey}:{i}",
                        x, y, COL_W, MATLABEL_H,
                        "matlabel", text=text,
                    ))

    def _emit_axes(self) -> None:
        self.bot_bus_y = self.total_h - self.FAN

        self.fanned_columns = set()

        for key in self.group_left:
            self.column_axis(key, self.group_elem[key], self.group_n[key],
                        lambda i, k=key: self.group_left[k](i) + COL_W / 2)

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

    def _emit_washes(self) -> None:
        if self.col_x and self.rows:
            bands = []
            for _bid, rkey, ckey in self.tiles:
                if (rkey, ckey) not in self.declared_tiles or not self.tile_open(rkey, ckey):
                    continue
                y, h = self.rows[rkey].tile_top - WASH_PAD, self.rows[rkey].tile_h + 2 * WASH_PAD
                if (rkey, ckey) == ("counts", "gens") and "canongens" in self.col_x:
                    segments = [("gens", self.tile_box("gens"), self.tile_groups("counts", "gens")),
                                ("canongens", self.tile_box("canongens"), self.tile_groups("counts", "canongens"))]
                else:
                    segments = [(ckey, self.tile_span_box(rkey, ckey), self.tile_groups(rkey, ckey))]
                for seg_key, (tile_x, tile_w), seg_groups in segments:
                    groups = sorted(g for g in seg_groups if self.settings.get(f"{g}_colorization"))
                    if not groups:
                        continue
                    x, w = tile_x - WASH_PAD, tile_w + 2 * WASH_PAD
                    if len(groups) == 3:
                        bands.append((f"white:{rkey}:{seg_key}", x, y, w, h, None))
                    else:
                        for group in groups:
                            bands.append((f"{group}:{rkey}:{seg_key}", x, y, w, h, group))
            for bid, x, y, w, h, _ in bands:
                self.blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
            for bid, x, y, w, h, group in bands:
                if group is not None:
                    self.blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))

    def _emit_symbols_captions(self) -> None:
        ai = service.is_all_interval(self.tuning_scheme)
        slope = service.damage_weight_slope(self.tuning_scheme)
        equivalences = {**EQUIVALENCES,
                        ("weight", "targets"): "" if self.custom_weights_active else WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                        ("prescaling", "ssprimes" if self.show_superspace else "primes"): self.prescaler_equivalence,
                        **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                        **(FORM_EQUIVALENCES if self.show_form_subscript else {}),
                        **({("mapping", "primes"): f" = 𝐹𝑀{SUBSCRIPT_C}"} if self.show_canon else {}),
                        **({("vectors", "commas"): " = C|U", ("mapping", "commas"): ""}
                           if self.show_unchanged else {})}
        if self.show_superspace:
            equivalences[("projection", "primes")] = (
                equivalences[("projection", "primes")] + self._projection_superspace_tail())
        if ai:
            if not self.prescaler_is_matrix and not self.size_factor:
                equivalences[("complexity", "targets")] = f" = diag({self.prescaler_symbol})"
                equivalences[("weight", "targets")] = f" = diag({self.prescaler_symbol})⁻¹"
            equivalences[("damage", "targets")] = f" = |𝒓|{self.prescaler_symbol}⁻¹"
        if not self.show_weighting:
            equivalences[("damage", "targets")] = " = |𝒓|" if ai else " = |𝐞|"
        for (rkey, ckey), name in self.effective_captions.items():
            if ckey == "interest" and not self.interest:
                continue
            if not self.tile_open(rkey, ckey):
                continue
            if ai and (rkey, ckey) in ALL_INTERVAL_CAPTIONS:
                name = ALL_INTERVAL_CAPTIONS[(rkey, ckey)]
            cy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey]
            if (self.show_symbols or self.show_equiv) and rkey in SYMBOLED_ROWS:
                cy += BAND_GAP
                equiv = equivalences.get((rkey, ckey), "") if self.show_equiv else ""
                base_symbol = self.prescaling_symbols.get((rkey, ckey), SYMBOLS.get((rkey, ckey), ""))
                if ai and (rkey, ckey) in ALL_INTERVAL_SYMBOLS:
                    base_symbol = ALL_INTERVAL_SYMBOLS[(rkey, ckey)]
                if self.show_unchanged and ckey == "commas":
                    base_symbol = base_symbol.replace(SUBSCRIPT_C, "\x00").replace("C", "V").replace("\x00", SUBSCRIPT_C)
                base_symbol = self._form_subscripted(base_symbol, rkey, ckey)
                glyph = base_symbol if (self.show_symbols or equiv) else ""
                if glyph or equiv:
                    self.cells.append(CellBox(f"symbol:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
                cy += SYMBOL_H
            if self.show_captions and self.show_unchanged and (rkey, ckey) == ("counts", "commas"):
                comma_half_w = self.nc * COL_W + self.empty_comma_w
                if comma_half_w:
                    comma_half_x = self.commas_x if self.empty_comma_w else self.comma_left(0)
                    self.cells.append(CellBox("caption:counts:commas", comma_half_x, cy, comma_half_w,
                                         self.rows[rkey].cap, "caption", text="nullity"))
                self.cells.append(CellBox("caption:counts:commas:u", self.comma_left(self.nc_shown), cy, self.nu * COL_W,
                                     self.rows[rkey].cap, "caption", text="unchanged interval count"))
                continue
            if self.show_captions:
                kw = MNEMONICS.get((rkey, ckey)) if self.show_mnemonics else None
                underlines = ((name.index(kw), 1),) if (kw and kw in name) else ()
                if self.show_mnemonics and ai:
                    underlines += tuple((name.index(w), 1)
                                        for w in ALL_INTERVAL_MNEMONICS.get((rkey, ckey), ()) if w in name)
                cap_x, cap_w = self.tile_span_box(rkey, ckey)
                self.cells.append(CellBox(f"caption:{rkey}:{ckey}", cap_x, cy, cap_w, self.rows[rkey].cap,
                                     "caption", text=name, underlines=underlines))
            unit = self.tile_unit(rkey, ckey)
            if unit and not (rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")):
                unit = _subscript_coord(unit, "p", self.domain_label)
            if self.show_units and unit:
                uy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey] + self.rows[rkey].sym + self.rows[rkey].cap
                self.cells.append(CellBox(f"units:{rkey}:{ckey}", self.col_x[ckey], uy, self.col_w[ckey], UNIT_H,
                                     "units", text=f"units: {unit}"))
