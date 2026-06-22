from __future__ import annotations

from rtt.app import ids, service
from rtt.app.grid_tables import (
    COUNTS,
    DETEMPERING_COUNTS,
    OPTIMIZATION_COUNTS,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    SUPERSPACE_COUNTS,
)
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    DASH,
    ETPICK_GAP,
    ETPICK_W,
    GAP,
    GRIP_BAND,
    HEADER_H,
    KET_INSET,
    LABEL_W,
    PAD,
    ROW_H,
    ROW_HANDLE_W,
    TOGGLE,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_models import _MappedTile, _QtyList
from rtt.app.spreadsheet_text import (
    _count_sym,
    _fold_glyph,
    _foldable_ids,
    _pretransform_label,
    _sub,
)


class _EmitMatrixMixin:
    def _emit_headers(self) -> None:
        for key in self.col_x:
            hx = self.col_x[key] + self.outer_gutter_w(key)
            hw = self.col_w[key] - 2 * self.outer_gutter_w(key)
            self.cells.append(CellBox(f"header:{key}", hx, self.header_y, hw, HEADER_H, "colheader", text=self.col_header[key]))
            if self.col_collapsible[key]:
                glyph = _fold_glyph(f"col:{key}" in self.collapsed)
                tx = hx + (hw - TOGGLE) / 2
                self.cells.append(CellBox(f"toggle:col:{key}", tx, self.col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))

        for key in self.rows:
            label = self.rows[key].label
            if self.size_factor or self.prescaler_is_matrix:
                label = _pretransform_label(label)
                label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
            self.cells.append(CellBox(f"label:{key}", 0, self.rows[key].y, LABEL_W, self.rows[key].h, "rowlabel", text=label))
            if self.rows[key].collapsible:
                glyph = _fold_glyph(f"row:{key}" in self.collapsed)
                ty = self.rows[key].y + (self.rows[key].h - TOGGLE) / 2
                self.cells.append(CellBox(f"toggle:row:{key}", self.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))

        foldable = _foldable_ids(self.cells)
        all_collapsed = bool(foldable) and foldable <= self.collapsed
        self.cells.append(CellBox("toggle:all", self.node_x, self.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                             text=_fold_glyph(all_collapsed)))

    def _emit_counts_row(self) -> None:
        if self.row_open("counts"):
            cardinality = {"gens": self.r, "primes": self.d, "commas": self.state.n, "targets": self.k, "held": self.nh,
                           "detempering": self.r,
                           "ssgens": self.rL, "ssprimes": self.dL}
            for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
                if not self.tile_open("counts", ckey):
                    continue
                if ckey == "commas" and self.show_unchanged:
                    comma_half_w = self.nc * COL_W + self.empty_comma_w
                    if comma_half_w:
                        comma_half_x = self.commas_x if self.empty_comma_w else self.comma_left(0)
                        self.cells.append(CellBox("count:commas", comma_half_x, self.rows["counts"].y, comma_half_w, ROW_H,
                                             "count", text=f"{_count_sym('n')} = {self.state.n}"))
                    self.cells.append(CellBox("count:commas:u", self.comma_left(self.nc_shown), self.rows["counts"].y, self.nu * COL_W, ROW_H,
                                         "count", text=f"{_count_sym('u')} = {self.nu}"))
                    continue
                cnt_x, cnt_w = self.tile_span_box("counts", ckey)
                self.cells.append(CellBox(f"count:{ckey}", cnt_x, self.rows["counts"].y, cnt_w, ROW_H,
                                     "count", text=f"{_count_sym(sym)} = {cardinality[ckey]}"))

    def _emit_units(self) -> None:
        matrix_units = {
            "vectors": (self.d, self.vec_top, lambda i: f"{self.domain_label}{_sub(i + 1)}/"),
            "canon": (self.rc, self.canon_top, lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
            "projection": (self.d, self.proj_top, lambda i: f"{self.domain_label}{_sub(i + 1)}/"),
            "mapping": (self.r_shown, self.map_top, lambda i: f"g{_sub(i + 1)}/"),
            "ss_vectors": (self.dL, self.ss_vec_top, lambda i: f"p{_sub(i + 1)}/"),
            "ss_mapping": (self.rL, self.ss_map_top, lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
            "ss_projection": (self.dL, self.ss_proj_top, lambda i: f"p{_sub(i + 1)}/"),
        }
        for key, (n, top, label) in matrix_units.items():
            if not self.tile_open(key, "units"):
                continue
            for i in range(n):
                self.cells.append(CellBox(f"ucol:{key}:{i}", self.col_x["units"], top(i),
                                     self.col_w["units"], ROW_H, "units", text=label(i)))
        const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                       "complexity": f"{self.complexity_unit}/", "weight": f"{self.weight_unit}/",
                       "damage": f"{self.damage_unit}/"}
        for key, text in const_units.items():
            if not self.tile_open(key, "units"):
                continue
            n = self.rows[key].nsub
            for i in range(n):
                cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
                self.cells.append(CellBox(cid, self.col_x["units"], self.rows[key].y + i * ROW_H,
                                     self.col_w["units"], ROW_H, "units", text=text))
        if "units" in self.rows:
            uy = self.rows["units"].y
            column_units = {
                "canongens": (self.rc, self.canongen_left, lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
                "gens": (self.r, self.gen_left, lambda i: f"/g{_sub(i + 1)}"),
                "primes": (self.d, self.prime_left, lambda i: f"/{self.domain_label}{_sub(i + 1)}"),
                "ssgens": (self.rL, self.ss_gen_left, lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
                "ssprimes": (self.dL, self.ss_prime_left, lambda i: f"/p{_sub(i + 1)}"),
                "commas": (self.nv_shown, self.comma_left, lambda i: "/1"),
                "detempering": (self.r, self.detempering_left, lambda i: "/1"),
                "targets": (self.k_shown, self.target_left, lambda i: "/1"),
                "interest": (self.mi_shown, self.interest_left, lambda i: "/1"),
                "held": (self.nh_shown, self.held_left, lambda i: "/1"),
            }
            for key, (n, left, label) in column_units.items():
                if not self.tile_open("units", key):
                    continue
                for i in range(n):
                    self.cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                         "units", text=label(i)))

    def _emit_quantities_row(self) -> None:
        if "quantities" in self.rows:
            qy = self.rows["quantities"].y

            def branch_minus(cid, ckey, i, kind, **kw):
                self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y, COL_W,
                                     qy - self.fanout_y, kind, **kw))

            if self.tile_open("quantities", "gens"):
                for g in range(self.r):
                    self.cells.append(CellBox(f"qgen:{g}", self.gen_left(g), qy, COL_W, ROW_H, "genratio", text=self.gens[g], gen=g))
                if self.r > 1:
                    branch_minus("gen_minus", "gens", self.r - 1, "gen_minus", gen=self.r - 1)
            if self.tile_open("quantities", "canongens"):
                for g in range(self.rc):
                    self.cells.append(CellBox(f"cangen:{g}", self.canongen_left(g), qy, COL_W, ROW_H, "genratio", text=self.canon_gens[g]))
            if self.tile_open("quantities", "primes"):
                for p in range(self.d):
                    text = str(self.elements[p])
                    kind = self._element_cell_kind(text) if self.show_nonstandard_domain else "prime"
                    self.cells.append(CellBox(f"prime:{p}", self.prime_left(p), qy, COL_W, ROW_H, kind, text=text, prime=p))
                    self._voice("quantities:primes", p, self.tun.just_map[p])
                if self.element_draft:
                    draft_text = self.pending_element or "?/?"
                    self.cells.append(CellBox("prime:pending", self.prime_left(self.d), qy, COL_W, ROW_H,
                                              self._element_cell_kind(draft_text), text=draft_text, prime=self.d, pending=True))
                    branch_minus("element_minus:pending", "primes", self.d, "element_minus")
                if self.show_nonstandard_domain:
                    if self.d > 1:
                        for p in range(self.d):
                            branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
                elif self.domain_can_shrink:
                    branch_minus("minus", "primes", self.d - 1, "minus")
            if self.tile_open("quantities", "ssgens"):
                ss_gens = service.superspace_generators(self.state)
                for g in range(self.rL):
                    self.cells.append(CellBox(f"ssqgen:{g}", self.ss_gen_left(g), qy, COL_W, ROW_H, "genratio", text=ss_gens[g]))
            if self.tile_open("quantities", "ssprimes"):
                for p in range(self.dL):
                    self.cells.append(CellBox(f"ssqprime:{p}", self.ss_prime_left(p), qy, COL_W, ROW_H, "prime", text=str(self.superspace_primes[p]), prime=p))
            if self.tile_open("quantities", "commas"):
                for c in range(self.nc):
                    self.cells.append(CellBox(f"comma:{self.col_token('commas', c)}", self.comma_left(c), qy, COL_W, ROW_H, "ratiocell", text=self.comma_ratios[c], comma=c))
                    self._voice("quantities:commas", c, self.comma_sizes.just[c])
                if self.comma_draft:
                    self.cells.append(CellBox("comma:pending", self.comma_left(self.nc), qy, COL_W, ROW_H,
                                         "commaratio" if self.ghost_comma else "ratiocell",
                                         text=(self.ghost_comma_ratio or DASH) if self.ghost_comma else "?/?",
                                         comma=self.nc, pending=True))
                if self.show_unchanged:
                    full_u = self.unchanged_basis is not None and all(v is not None for v in self.unchanged_basis)
                    for j in range(self.nu):
                        doomed = self.pending is not None and j == self.nu - 1
                        self.cells.append(CellBox(f"unchanged:{j}", self.comma_left(self.nc_shown + j), qy, COL_W, ROW_H,
                                             "ratiocell" if (full_u and not doomed) else "commaratio",
                                             text=self.unchanged_ratios[j] or DASH, comma=self.nc + j))
                        self._voice("quantities:commas", self.nc + j, self.unchanged_sizes.just[j])
                for c in range(self.nc):
                    branch_minus(f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
                if self.pending is not None:
                    branch_minus("comma_minus:pending", "commas", self.nc, "comma_minus")
            if self.tile_open("quantities", "detempering"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"detempering:{i}", self.detempering_left(i), qy, COL_W, ROW_H, "commaratio", text=self.gens[i]))
                    self._voice("quantities:detempering", i, self.detempering_sizes.just[i])
            if self.tile_open("quantities", "targets"):
                self._emit_qty_list(_QtyList("targets", "target", self.k, self.target_left, self.targets,
                                             self.target_sizes, self.pending_target,
                                             "ratiocell" if self.targets_editable else "commaratio",
                                             self.targets_editable), qy, branch_minus)
            if self.tile_open("quantities", "held"):
                self._emit_qty_list(_QtyList("held", "held", self.nh, self.held_left, self.held_ratios,
                                             self.held_sizes, self.pending_held, "ratiocell", True), qy, branch_minus)
            if self.tile_open("quantities", "interest"):
                self._emit_qty_list(_QtyList("interest", "interest", self.mi, self.interest_left, self.interest_ratios,
                                             self.interest_sizes, self.pending_interest, "ratiocell", True), qy, branch_minus)

            grip_top = self.branch_top_y + GAP - PAD

            def drag_controls(ckey, n):
                for i in range(n):
                    self.cells.append(CellBox(f"grip:{ckey}:{i}", self.sub_axis_x(ckey, i) - COL_W / 2,
                                         grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
                add_w = COL_W
                if ckey == "commas" and self.show_unchanged:
                    add_w = self.empty_comma_w if self.nc_shown == 0 else V_SPLIT_GAP
                self.cells.append(CellBox(f"grip:{ckey}:add", self.plus_stub_x[ckey] - add_w / 2,
                                     grip_top, add_w, GRIP_BAND, "colgrip"))

            counts = {"commas": self.nc, "targets": self.k, "held": self.nh, "interest": self.mi}
            for ckey in ("commas", "targets", "held", "interest"):
                if self.row_open("quantities") and self._plus_shows(ckey):
                    drag_controls(ckey, counts[ckey])
            if self.show_unchanged:
                for j in range(self.nu):
                    if self.unchanged_basis[j] is not None:
                        self.cells.append(CellBox(f"grip:unchanged:{j}", self.sub_axis_x("commas", self.nc_shown + j) - COL_W / 2,
                                             grip_top, COL_W, GRIP_BAND, "colgrip", comma=j))

    def _emit_column_plus_controls(self) -> None:
        primes_plus = "element_plus" if self.show_nonstandard_domain else "plus"
        for ckey, cid in (("gens", "gen_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                          ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
            if ckey in self.plus_stub_x:
                self.cells.append(CellBox(cid, self.plus_stub_x[ckey] - BTN / 2, self.fanout_y - BTN / 2, BTN, BTN, cid))

    def _emit_rehomed_minus_controls(self) -> None:
        if not self.row_open("quantities") and self.row_open("vectors"):
            vtop = self.rows["vectors"].y
            def vec_minus(cid, ckey, i, kind, **kw):
                self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y,
                                     COL_W, vtop - self.fanout_y, kind, **kw))
            if self.tile_open("vectors", "commas"):
                for c in range(self.nc):
                    vec_minus(f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
                if self.pending is not None:
                    vec_minus("comma_minus:pending", "commas", self.nc, "comma_minus")
            if self.tile_open("vectors", "targets"):
                if self.targets_editable:
                    for j in range(self.k):
                        vec_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
                if self.pending_target is not None:
                    vec_minus("target_minus:pending", "targets", self.k, "target_minus")
            if self.tile_open("vectors", "held"):
                for i in range(self.nh):
                    vec_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
                if self.pending_held is not None:
                    vec_minus("held_minus:pending", "held", self.nh, "held_minus")
            if self.tile_open("vectors", "interest"):
                for i in range(self.mi):
                    vec_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
                if self.pending_interest is not None:
                    vec_minus("interest_minus:pending", "interest", self.mi, "interest_minus")

    def _emit_mapping_band(self) -> None:
        if self.row_open("mapping"):
            if self.tile_open("mapping", "quantities"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"gen:{self.col_token('gens', i)}", self.col_x["quantities"], self.map_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.gens[i] if i < len(self.gens) else "", gen=i))
                map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
                gen_right = self.col_x["quantities"] + self.col_w["quantities"]
                if self.r > 1:
                    for i in range(self.r):
                        self.cells.append(CellBox(f"map_minus:{self.col_token('gens', i)}", map_bus_x, self.map_top(i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
                if "mapping" in self.row_plus_y:
                    self.cells.append(CellBox("map_plus", map_bus_x - BTN / 2, self.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))
            if self.settings.get("drag_to_combine") and self.r > 1 and self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"map_drag:{self.col_token('gens', i)}", self.primes_x + self.etpick_left_pad("primes"), self.map_top(i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))
            mx, mw = self.matrix_span("primes")
            etpick_x = mx + mw + ETPICK_GAP
            for i in range(self.r):
                rt = self.col_token("gens", i)
                if self.tile_open("mapping", "primes"):
                    if self.show_presets:
                        self.cells.append(CellBox(f"etpick:{rt}", etpick_x, self.map_top(i), ETPICK_W, ROW_H, "etpick", gen=i))
                    for p in range(self.d):
                        self.cells.append(CellBox(ids.mapping_cell(rt, p), self.prime_left(p), self.map_top(i), COL_W, ROW_H, "mapping", text=str(self.state.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("mapping", "primes", gen=i, prime=p)))
                if self.tile_open("mapping", "targets"):
                    self._emit_mapped_tile(_MappedTile("mapped", "targets", self.k, self.target_left, self.mapped, self.pending_target), i, rt)
                if self.tile_open("mapping", "interest"):
                    self._emit_mapped_tile(_MappedTile("imapped", "interest", self.mi, self.interest_left, self.interest_mapped, self.pending_interest), i, rt)
                if self.tile_open("mapping", "held"):
                    self._emit_mapped_tile(_MappedTile("hmapped", "held", self.nh, self.held_left, self.held_mapped, self.pending_held), i, rt)
                if self.tile_open("mapping", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.mapped_commas[i][c]), gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
                    if self.comma_draft:
                        mc_text = str(self.ghost_comma_mapped[i]) if (self.ghost_comma and i < len(self.ghost_comma_mapped)) else ""
                        self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.pending_col_token('commas')}", self.comma_left(self.nc), self.map_top(i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
                    for j in range(self.nu):
                        mapped_text = DASH if self.unchanged_mapped[i][j] is None else str(self.unchanged_mapped[i][j])
                        self.cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", self.comma_left(self.nc_shown + j), self.map_top(i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
            if self.row_draft:
                dr = self.r
                drt = self.pending_col_token("gens")
                if self.tile_open("mapping", "quantities"):
                    gen_text = self.ghost_row_ratio if self.ghost_row else "?"
                    self.cells.append(CellBox("gen:pending", self.col_x["quantities"], self.map_top(dr), self.col_w["quantities"], ROW_H, "genratio", text=gen_text, gen=dr, pending=True))
                    if not self.ghost_row:
                        map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
                        gen_right = self.col_x["quantities"] + self.col_w["quantities"]
                        self.cells.append(CellBox("map_minus:pending", map_bus_x, self.map_top(dr), gen_right - map_bus_x, ROW_H, "map_minus", gen=dr, pending=True))
                if self.tile_open("mapping", "primes"):
                    row_kind = "mapped" if self.ghost_row else "mapping"
                    for p in range(self.d):
                        v = self.ghost_row_map[p] if self.ghost_row else self.pending_mapping_row[p]
                        self.cells.append(CellBox(ids.mapping_cell(drt, p), self.prime_left(p), self.map_top(dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
                    if not self.ghost_row and self.show_presets:
                        mx, mw = self.matrix_span("primes")
                        self.cells.append(CellBox("etpick:draft", mx + mw + ETPICK_GAP, self.map_top(dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
                def gmap(key, j):
                    vals = self.ghost_row_mapped.get(key, ()) if self.ghost_row else ()
                    if j >= len(vals):
                        return ""
                    return DASH if vals[j] is None else str(vals[j])
                if self.tile_open("mapping", "targets"):
                    for j in range(self.k):
                        self.cells.append(CellBox(f"cell:mapped:{drt}:{self.col_token('targets', j)}", self.target_left(j), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("targets", j), gen=dr, pending=True))
                if self.tile_open("mapping", "interest"):
                    for ii in range(self.mi):
                        self.cells.append(CellBox(f"cell:imapped:{drt}:{self.col_token('interest', ii)}", self.interest_left(ii), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("interest", ii), gen=dr, pending=True))
                if self.tile_open("mapping", "held"):
                    for hi in range(self.nh):
                        self.cells.append(CellBox(f"cell:hmapped:{drt}:{self.col_token('held', hi)}", self.held_left(hi), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("held", hi), gen=dr, pending=True))
                if self.tile_open("mapping", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:mapped_comma:{drt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("commas", c), gen=dr, pending=True))
                    for j in range(self.nu):
                        self.cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", self.comma_left(self.nc_shown + j), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("unchanged", j), gen=dr, pending=True))

    def _emit_mapped_tile(self, m: _MappedTile, i: int, rt: str) -> None:
        for col in range(m.count):
            self.cells.append(CellBox(f"cell:{m.prefix}:{rt}:{self.col_token(m.group, col)}", m.left_fn(col), self.map_top(i), COL_W, ROW_H, "mapped", text=str(m.data[i][col]), gen=i, unit=self.cell_unit("mapping", m.group, gen=i)))
        if m.pending is not None:
            self.cells.append(CellBox(f"cell:{m.prefix}:{rt}:draft", m.left_fn(m.count), self.map_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))

    def _emit_mapped_grid(self, tile, prefix, grid, n_cols, left, col_kw, *,
                          full=None, colwise=False, col_token_key=None, inset=0,
                          row="projection", top=None, height=None, pending=None) -> None:
        if not (self.row_open(row) and self.tile_open(row, tile)):
            return
        if full is None:
            full = grid is not None
        top = top or self.proj_top
        height = self.d if height is None else height

        def cell(i, j):
            if colwise:
                text = str(grid[j][i]) if full else DASH
                tok = j if col_token_key is None else self.col_token(col_token_key, j)
                cid, kw = f"cell:{prefix}:{tok}:{i}", {"prime": i, col_kw: j}
            else:
                text = grid[i][j] if full else DASH
                cid, kw = f"cell:{prefix}:{i}:{j}", {col_kw: j}
            self.cells.append(CellBox(cid, left(j) + inset, top(i),
                                 COL_W - 2 * inset, ROW_H, "mapped", text=text, **kw))

        if colwise:
            for j in range(n_cols):
                for i in range(height):
                    cell(i, j)
            if pending is not None:
                for i in range(height):
                    self.cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols) + inset, top(i),
                                         COL_W - 2 * inset, ROW_H, "mapped", text="", prime=i, pending=True))
        else:
            for i in range(height):
                for j in range(n_cols):
                    cell(i, j)

    def _emit_projection_band(self) -> None:
        self._emit_mapped_grid("primes", "proj", self.projection_matrix, self.d, self.prime_left, "prime")
        self._emit_mapped_grid("gens", "embed", self.embedding_matrix, self.r, self.gen_left, "gen")
        self._emit_mapped_grid("canongens", "embed_c", self.canon_embedding_matrix, self.rc, self.canongen_left, "gen")
        self._emit_mapped_grid("ssgens", "embed_sl", self.embedding_superspace, self.rL, self.ss_gen_left, "gen")
        self._emit_mapped_grid("ssprimes", "proj_sl", self.projection_superspace, self.dL, self.ss_prime_left, "prime")

        if self.show_unchanged and self.row_open("projection") and self.tile_open("projection", "commas"):
            for c in range(self.nc):
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:{self.col_token('commas', c)}", self.comma_left(c), self.proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            if self.comma_draft:
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:draft", self.comma_left(self.nc), self.proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0" if self.ghost_comma else "", prime=p, pending=True))
            for j in range(self.nu):
                dashed = self.unchanged_basis[j] is None
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:u{j}", self.comma_left(self.nc_shown + j), self.proj_top(p),
                                         COL_W, ROW_H, "mapped",
                                         text=DASH if dashed else str(self.unchanged_basis[j][p]), prime=p, comma=self.nc + j))

        if self.row_open("projection") and self.tile_open("projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.d):
                self.cells.append(CellBox(f"proj_basis:{p}", bx, self.proj_top(p), COL_W, ROW_H, "prime", text=str(self.elements[p]), prime=p))
        full_proj = self.projection_rationals is not None
        self._emit_mapped_grid("detempering", "proj_pd", self.proj_detempering, self.r, self.detempering_left, "gen",
                               full=full_proj, colwise=True, col_token_key="detempering")
        self._emit_mapped_grid("targets", "proj_pt", self.proj_targets, self.k, self.target_left, "comma",
                               full=full_proj, colwise=True, pending=self.pending_target)
        self._emit_mapped_grid("held", "proj_ph", self.proj_held, self.nh, self.held_left, "comma",
                               full=full_proj, colwise=True, pending=self.pending_held)
        self._emit_mapped_grid("interest", "proj_pi", self.proj_interest, self.mi, self.interest_left, "comma",
                               full=full_proj, colwise=True, inset=KET_INSET, pending=self.pending_interest)

        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            scaling = ["0"] * self.nc + [(DASH if v is None else "1") for v in self.unchanged_basis]
            for c, lam in enumerate(scaling):
                self.cells.append(CellBox(f"cell:scaling:{self.col_token('commas', c)}", self.comma_left(self.comma_value_pos(c)), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text=lam, comma=c))
            if self.comma_draft:
                self.cells.append(CellBox("cell:scaling:draft", self.comma_left(self.nc), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text="0" if self.ghost_comma else "", pending=True))

    def _emit_canon_band(self) -> None:
        if self.row_open("canon"):
            if self.tile_open("canon", "quantities"):
                for i in range(self.rc):
                    self.cells.append(CellBox(f"canon:gen:{i}", self.col_x["quantities"], self.canon_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.canon_gens[i] if i < len(self.canon_gens) else ""))
            if self.tile_open("canon", "primes"):
                for i in range(self.rc):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:canon:{i}:{p}", self.prime_left(p), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("canon", "primes", gen=i, prime=p)))
            if self.tile_open("canon", "gens"):
                for i in range(len(self.form_M)):
                    for j in range(len(self.form_M)):
                        self.cells.append(CellBox(f"cell:form:{i}:{j}", self.gen_left(j), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.form_M[i][j]), unit=self.cell_unit("canon", "gens", gen=i)))
            for i in range(self.rc):
                if self.tile_open("canon", "detempering"):
                    for c in range(self.r):
                        self.cells.append(CellBox(f"cell:canon_detempering:{i}:{self.col_token('detempering', c)}", self.detempering_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapped_detempering[i][c]), gen=i, unit=self.cell_unit("canon", "detempering", gen=i)))
                if self.tile_open("canon", "targets"):
                    self._emit_canon_mapped_tile("canon_mapped", "targets", self.k, self.target_left, self.canon_mapped, self.pending_target, i)
                if self.tile_open("canon", "interest"):
                    self._emit_canon_mapped_tile("canon_imapped", "interest", self.mi, self.interest_left, self.canon_interest_mapped, self.pending_interest, i)
                if self.tile_open("canon", "held"):
                    self._emit_canon_mapped_tile("canon_hmapped", "held", self.nh, self.held_left, self.canon_held_mapped, self.pending_held, i)
                if self.tile_open("canon", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.col_token('commas', c)}", self.comma_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapped_commas[i][c]), gen=i, unit=self.cell_unit("canon", "commas", gen=i)))
                    if self.comma_draft:
                        self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.pending_col_token('commas')}", self.comma_left(self.nc), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
                    for j in range(self.nu):
                        ut = DASH if self.canon_unchanged_mapped[i][j] is None else str(self.canon_unchanged_mapped[i][j])
                        self.cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", self.comma_left(self.nc_shown + j), self.canon_top(i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=self.cell_unit("canon", "commas", gen=i)))
        if self.tile_open("mapping", "canongens"):
            for i in range(self.r):
                for j in range(self.rc):
                    self.cells.append(CellBox(f"cell:finv:{i}:{j}", self.canongen_left(j), self.map_top(i), COL_W, ROW_H,
                                         "formcell", text=str(self.inverse_form_M[i][j]), unit=self.cell_unit("mapping", "canongens", gen=i)))

    def _emit_canon_mapped_tile(self, prefix, group, count, left_fn, data, pending, i) -> None:
        for col in range(count):
            self.cells.append(CellBox(f"cell:{prefix}:{i}:{self.col_token(group, col)}", left_fn(col), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=self.cell_unit("canon", group, gen=i)))
        if pending is not None:
            self.cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
