from __future__ import annotations

import functools

from rtt.app import service
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
    GAP,
    GRIP_BAND,
    HEADER_H,
    LABEL_W,
    PAD,
    ROW_H,
    TOGGLE,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_models import _QtyList
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
        self._emit_units_matrix()
        self._emit_units_const()
        self._emit_units_columns()

    def _emit_units_matrix(self) -> None:
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

    def _emit_units_const(self) -> None:
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

    def _emit_units_columns(self) -> None:
        if "units" not in self.rows:
            return
        uy = self.rows["units"].y
        column_units = {
            "canongens": (self.rc, self.canongen_left, lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
            "gens": (self.r, self.gen_left, lambda i: f"/g{_sub(i + 1)}"),
            "primes": (self.d, self.prime_left, lambda i: f"/{self.domain_label}{_sub(i + 1)}"),
            "ssgens": (self.rL, self.ss_gen_left, lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
            "ssprimes": (self.dL, self.ss_prime_left, lambda i: f"/p{_sub(i + 1)}"),
            "commas": (self.nv_shown, self.comma_left, lambda _i: "/1"),
            "detempering": (self.r, self.detempering_left, lambda _i: "/1"),
            "targets": (self.k_shown, self.target_left, lambda _i: "/1"),
            "interest": (self.mi_shown, self.interest_left, lambda _i: "/1"),
            "held": (self.nh_shown, self.held_left, lambda _i: "/1"),
        }
        for key, (n, left, label) in column_units.items():
            if not self.tile_open("units", key):
                continue
            for i in range(n):
                self.cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                     "units", text=label(i)))

    def _qty_branch_minus(self, qy, cid, ckey, i, kind, **kw):
        self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y, COL_W,
                             qy - self.fanout_y, kind, **kw))

    def _emit_quantities_row(self) -> None:
        if "quantities" not in self.rows:
            return
        qy = self.rows["quantities"].y
        branch_minus = functools.partial(self._qty_branch_minus, qy)
        self._emit_qty_gens(qy, branch_minus)
        self._emit_qty_canongens(qy)
        self._emit_qty_primes(qy, branch_minus)
        self._emit_qty_ssgens(qy)
        self._emit_qty_ssprimes(qy)
        self._emit_qty_commas(qy, branch_minus)
        self._emit_qty_detempering(qy)
        self._emit_qty_interests(qy, branch_minus)
        self._emit_qty_grips()

    def _emit_qty_gens(self, qy, branch_minus) -> None:
        if self.tile_open("quantities", "gens"):
            for g in range(self.r):
                self.cells.append(CellBox(f"qgen:{g}", self.gen_left(g), qy, COL_W, ROW_H, "genratio", text=self.gens[g], gen=g))
            if self.r > 1:
                branch_minus("gen_minus", "gens", self.r - 1, "gen_minus", gen=self.r - 1)

    def _emit_qty_canongens(self, qy) -> None:
        if self.tile_open("quantities", "canongens"):
            for g in range(self.rc):
                self.cells.append(CellBox(f"cangen:{g}", self.canongen_left(g), qy, COL_W, ROW_H, "genratio", text=self.canon_gens[g]))

    def _emit_qty_primes(self, qy, branch_minus) -> None:
        if not self.tile_open("quantities", "primes"):
            return
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

    def _emit_qty_ssgens(self, qy) -> None:
        if self.tile_open("quantities", "ssgens"):
            ss_gens = service.superspace_generators(self.state)
            for g in range(self.rL):
                self.cells.append(CellBox(f"ssqgen:{g}", self.ss_gen_left(g), qy, COL_W, ROW_H, "genratio", text=ss_gens[g]))

    def _emit_qty_ssprimes(self, qy) -> None:
        if self.tile_open("quantities", "ssprimes"):
            for p in range(self.dL):
                self.cells.append(CellBox(f"ssqprime:{p}", self.ss_prime_left(p), qy, COL_W, ROW_H, "prime", text=str(self.superspace_primes[p]), prime=p))

    def _emit_qty_commas(self, qy, branch_minus) -> None:
        if not self.tile_open("quantities", "commas"):
            return
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

    def _emit_qty_detempering(self, qy) -> None:
        if self.tile_open("quantities", "detempering"):
            for i in range(self.r):
                self.cells.append(CellBox(f"detempering:{i}", self.detempering_left(i), qy, COL_W, ROW_H, "commaratio", text=self.gens[i]))
                self._voice("quantities:detempering", i, self.detempering_sizes.just[i])

    def _emit_qty_interests(self, qy, branch_minus) -> None:
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

    def _qty_drag_controls(self, ckey, n, grip_top) -> None:
        for i in range(n):
            self.cells.append(CellBox(f"grip:{ckey}:{i}", self.sub_axis_x(ckey, i) - COL_W / 2,
                                 grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
        add_w = COL_W
        if ckey == "commas" and self.show_unchanged:
            add_w = self.empty_comma_w if self.nc_shown == 0 else V_SPLIT_GAP
        self.cells.append(CellBox(f"grip:{ckey}:add", self.plus_stub_x[ckey] - add_w / 2,
                             grip_top, add_w, GRIP_BAND, "colgrip"))

    def _emit_qty_grips(self) -> None:
        grip_top = self.branch_top_y + GAP - PAD
        counts = {"commas": self.nc, "targets": self.k, "held": self.nh, "interest": self.mi}
        for ckey in ("commas", "targets", "held", "interest"):
            if self.row_open("quantities") and self._plus_shows(ckey):
                self._qty_drag_controls(ckey, counts[ckey], grip_top)
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

    def _vec_minus(self, vtop, cid, ckey, i, kind, **kw):
        self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y,
                             COL_W, vtop - self.fanout_y, kind, **kw))

    def _emit_rehomed_minus_controls(self) -> None:
        if self.row_open("quantities") or not self.row_open("vectors"):
            return
        vtop = self.rows["vectors"].y
        self._emit_rehomed_commas(vtop)
        self._emit_rehomed_targets(vtop)
        self._emit_rehomed_held(vtop)
        self._emit_rehomed_interest(vtop)

    def _emit_rehomed_commas(self, vtop) -> None:
        if self.tile_open("vectors", "commas"):
            for c in range(self.nc):
                self._vec_minus(vtop, f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
            if self.pending is not None:
                self._vec_minus(vtop, "comma_minus:pending", "commas", self.nc, "comma_minus")

    def _emit_rehomed_targets(self, vtop) -> None:
        if self.tile_open("vectors", "targets"):
            if self.targets_editable:
                for j in range(self.k):
                    self._vec_minus(vtop, f"target_minus:{j}", "targets", j, "target_minus", comma=j)
            if self.pending_target is not None:
                self._vec_minus(vtop, "target_minus:pending", "targets", self.k, "target_minus")

    def _emit_rehomed_held(self, vtop) -> None:
        if self.tile_open("vectors", "held"):
            for i in range(self.nh):
                self._vec_minus(vtop, f"held_minus:{i}", "held", i, "held_minus", comma=i)
            if self.pending_held is not None:
                self._vec_minus(vtop, "held_minus:pending", "held", self.nh, "held_minus")

    def _emit_rehomed_interest(self, vtop) -> None:
        if self.tile_open("vectors", "interest"):
            for i in range(self.mi):
                self._vec_minus(vtop, f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
            if self.pending_interest is not None:
                self._vec_minus(vtop, "interest_minus:pending", "interest", self.mi, "interest_minus")

