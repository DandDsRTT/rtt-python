from __future__ import annotations

import functools

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
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
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_models import _QtyList
from rtt.app.spreadsheet_text import (
    _count_sym,
    _fold_glyph,
    _foldable_ids,
    _pretransform_label,
    _sub,
)


def emit_headers(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    for key in geometry.col_x:
        hx = geometry.col_x[key] + query.outer_gutter_w(geometry, key)
        hw = geometry.col_w[key] - 2 * query.outer_gutter_w(geometry, key)
        cells.append(CellBox(f"header:{key}", hx, geometry.header_y, hw, HEADER_H, "colheader", text=geometry.col_header[key]))
        if geometry.col_collapsible[key]:
            glyph = _fold_glyph(f"col:{key}" in ctx.collapsed)
            tx = hx + (hw - TOGGLE) / 2
            cells.append(CellBox(f"toggle:col:{key}", tx, geometry.col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))
    for key in geometry.rows:
        label = geometry.rows[key].label
        if geometry.size_factor or _r.scalars.prescaler_is_matrix:
            label = _pretransform_label(label)
            label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
        cells.append(CellBox(f"label:{key}", 0, geometry.rows[key].y, LABEL_W, geometry.rows[key].h, "rowlabel", text=label))
        if geometry.rows[key].collapsible:
            glyph = _fold_glyph(f"row:{key}" in ctx.collapsed)
            ty = geometry.rows[key].y + (geometry.rows[key].h - TOGGLE) / 2
            cells.append(CellBox(f"toggle:row:{key}", geometry.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))
    foldable = _foldable_ids(cells)
    all_collapsed = bool(foldable) and foldable <= ctx.collapsed
    cells.append(CellBox("toggle:all", geometry.node_x, geometry.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                         text=_fold_glyph(all_collapsed)))
    return EmitResult(cells=tuple(cells))


def emit_counts_row(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    if not query.row_open(geometry, ctx.collapsed, "counts"):
        return EmitResult()
    cardinality = {"gens": _r.dims.r, "primes": _r.dims.d, "commas": ctx.state.n, "targets": _r.dims.k, "held": _r.dims.nh,
                   "detempering": _r.dims.r,
                   "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}
    for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
        if not query.tile_open(geometry, ctx.collapsed, "counts", ckey):
            continue
        if ckey == "commas" and _r.unchanged.shown:
            comma_half_w = _r.dims.nc * COL_W + _r.unchanged.empty_comma_w
            if comma_half_w:
                comma_half_x = geometry.commas_x if _r.unchanged.empty_comma_w else query.comma_left(geometry, _r, 0)
                cells.append(CellBox("count:commas", comma_half_x, geometry.rows["counts"].y, comma_half_w, ROW_H,
                                     "count", text=f"{_count_sym('n')} = {ctx.state.n}"))
            cells.append(CellBox("count:commas:u", query.comma_left(geometry, _r, _r.dims.nc_shown), geometry.rows["counts"].y, _r.dims.nu * COL_W, ROW_H,
                                 "count", text=f"{_count_sym('u')} = {_r.dims.nu}"))
            continue
        cnt_x, cnt_w = query.tile_span_box(geometry, "counts", ckey)
        cells.append(CellBox(f"count:{ckey}", cnt_x, geometry.rows["counts"].y, cnt_w, ROW_H,
                             "count", text=f"{_count_sym(sym)} = {cardinality[ckey]}"))
    return EmitResult(cells=tuple(cells))


def emit_units(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    _emit_units_matrix(cells, resolved, geometry, ctx)
    _emit_units_const(cells, resolved, geometry, ctx)
    _emit_units_columns(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_units_matrix(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    matrix_units = {
        "vectors": (_r.dims.d, lambda i: query.vec_top(geometry, i), lambda i: f"{_r.labels.domain_label}{_sub(i + 1)}/"),
        "canon": (_r.dims.rc, lambda i: query.canon_top(geometry, i), lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
        "projection": (_r.dims.d, lambda i: query.proj_top(geometry, i), lambda i: f"{_r.labels.domain_label}{_sub(i + 1)}/"),
        "mapping": (_r.dims.r_shown, lambda i: query.map_top(geometry, i), lambda i: f"g{_sub(i + 1)}/"),
        "ss_vectors": (_r.dims.dL, lambda i: query.ss_vec_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
        "ss_mapping": (_r.dims.rL, lambda i: query.ss_map_top(geometry, i), lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
        "ss_projection": (_r.dims.dL, lambda i: query.ss_proj_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
    }
    for key, (n, top, label) in matrix_units.items():
        if not query.tile_open(geometry, ctx.collapsed, key, "units"):
            continue
        for i in range(n):
            cells.append(CellBox(f"ucol:{key}:{i}", geometry.col_x["units"], top(i),
                                 geometry.col_w["units"], ROW_H, "units", text=label(i)))


def _emit_units_const(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                   "complexity": f"{_r.scalars.complexity_unit}/", "weight": f"{_r.scalars.weight_unit}/",
                   "damage": f"{_r.scalars.damage_unit}/"}
    for key, text in const_units.items():
        if not query.tile_open(geometry, ctx.collapsed, key, "units"):
            continue
        n = geometry.rows[key].nsub
        for i in range(n):
            cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
            cells.append(CellBox(cid, geometry.col_x["units"], geometry.rows[key].y + i * ROW_H,
                                 geometry.col_w["units"], ROW_H, "units", text=text))


def _emit_units_columns(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if "units" not in geometry.rows:
        return
    uy = geometry.rows["units"].y
    column_units = {
        "canongens": (_r.dims.rc, lambda i: query.canongen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
        "gens": (_r.dims.r, lambda i: query.gen_left(geometry, i), lambda i: f"/g{_sub(i + 1)}"),
        "primes": (_r.dims.d, lambda i: query.prime_left(geometry, i), lambda i: f"/{_r.labels.domain_label}{_sub(i + 1)}"),
        "ssgens": (_r.dims.rL, lambda i: query.ss_gen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
        "ssprimes": (_r.dims.dL, lambda i: query.ss_prime_left(geometry, i), lambda i: f"/p{_sub(i + 1)}"),
        "commas": (_r.dims.nv_shown, lambda i: query.comma_left(geometry, _r, i), lambda _i: "/1"),
        "detempering": (_r.dims.r, lambda i: query.detempering_left(geometry, i), lambda _i: "/1"),
        "targets": (_r.dims.k_shown, lambda i: query.target_left(geometry, i), lambda _i: "/1"),
        "interest": (_r.dims.mi_shown, lambda i: query.interest_left(geometry, i), lambda _i: "/1"),
        "held": (_r.dims.nh_shown, lambda i: query.held_left(geometry, i), lambda _i: "/1"),
    }
    for key, (n, left, label) in column_units.items():
        if not query.tile_open(geometry, ctx.collapsed, "units", key):
            continue
        for i in range(n):
            cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                 "units", text=label(i)))


class _EmitMatrixMixin:
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
        _r = self.resolved
        if self.tile_open("quantities", "gens"):
            for g in range(_r.dims.r):
                self.cells.append(CellBox(f"qgen:{g}", self.gen_left(g), qy, COL_W, ROW_H, "genratio", text=_r.scalars.gens[g], gen=g))
            if _r.dims.r > 1:
                branch_minus("gen_minus", "gens", _r.dims.r - 1, "gen_minus", gen=_r.dims.r - 1)

    def _emit_qty_canongens(self, qy) -> None:
        _r = self.resolved
        if self.tile_open("quantities", "canongens"):
            for g in range(_r.dims.rc):
                self.cells.append(CellBox(f"cangen:{g}", self.canongen_left(g), qy, COL_W, ROW_H, "genratio", text=_r.canon.gens[g]))

    def _emit_qty_primes(self, qy, branch_minus) -> None:
        _r = self.resolved
        if not self.tile_open("quantities", "primes"):
            return
        for p in range(_r.dims.d):
            text = str(_r.dims.elements[p])
            kind = self._element_cell_kind(text) if _r.flags.nonstandard_domain else "prime"
            self.cells.append(CellBox(f"prime:{p}", self.prime_left(p), qy, COL_W, ROW_H, kind, text=text, prime=p))
            self._voice("quantities:primes", p, _r.tuning.tun.just_map[p])
        if _r.scalars.element_draft:
            draft_text = self.pending_element or "?/?"
            self.cells.append(CellBox("prime:pending", self.prime_left(_r.dims.d), qy, COL_W, ROW_H,
                                      self._element_cell_kind(draft_text), text=draft_text, prime=_r.dims.d, pending=True))
            branch_minus("element_minus:pending", "primes", _r.dims.d, "element_minus")
        if _r.flags.nonstandard_domain:
            if _r.dims.d > 1:
                for p in range(_r.dims.d):
                    branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
        elif _r.scalars.domain_can_shrink:
            branch_minus("minus", "primes", _r.dims.d - 1, "minus")

    def _emit_qty_ssgens(self, qy) -> None:
        _r = self.resolved
        if self.tile_open("quantities", "ssgens"):
            ss_gens = service.superspace_generators(self.state)
            for g in range(_r.dims.rL):
                self.cells.append(CellBox(f"ssqgen:{g}", self.ss_gen_left(g), qy, COL_W, ROW_H, "genratio", text=ss_gens[g]))

    def _emit_qty_ssprimes(self, qy) -> None:
        _r = self.resolved
        if self.tile_open("quantities", "ssprimes"):
            for p in range(_r.dims.dL):
                self.cells.append(CellBox(f"ssqprime:{p}", self.ss_prime_left(p), qy, COL_W, ROW_H, "prime", text=str(_r.dims.superspace_primes[p]), prime=p))

    def _emit_qty_commas(self, qy, branch_minus) -> None:
        _r = self.resolved
        if not self.tile_open("quantities", "commas"):
            return
        for c in range(_r.dims.nc):
            self.cells.append(CellBox(f"comma:{self.col_token('commas', c)}", self.comma_left(c), qy, COL_W, ROW_H, "ratiocell", text=_r.commas.ratios[c], comma=c))
            self._voice("quantities:commas", c, _r.tuning.comma_sizes.just[c])
        if _r.scalars.comma_draft:
            self.cells.append(CellBox("comma:pending", self.comma_left(_r.dims.nc), qy, COL_W, ROW_H,
                                 "commaratio" if _r.ghosts.comma else "ratiocell",
                                 text=(_r.ghosts.comma_ratio or DASH) if _r.ghosts.comma else "?/?",
                                 comma=_r.dims.nc, pending=True))
        if _r.unchanged.shown:
            full_u = _r.unchanged.basis is not None and all(v is not None for v in _r.unchanged.basis)
            for j in range(_r.dims.nu):
                doomed = _r.commas.pending is not None and j == _r.dims.nu - 1
                self.cells.append(CellBox(f"unchanged:{j}", self.comma_left(_r.dims.nc_shown + j), qy, COL_W, ROW_H,
                                     "ratiocell" if (full_u and not doomed) else "commaratio",
                                     text=_r.unchanged.ratios[j] or DASH, comma=_r.dims.nc + j))
                self._voice("quantities:commas", _r.dims.nc + j, _r.unchanged.sizes.just[j])
        for c in range(_r.dims.nc):
            branch_minus(f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
        if _r.commas.pending is not None:
            branch_minus("comma_minus:pending", "commas", _r.dims.nc, "comma_minus")

    def _emit_qty_detempering(self, qy) -> None:
        _r = self.resolved
        if self.tile_open("quantities", "detempering"):
            for i in range(_r.dims.r):
                self.cells.append(CellBox(f"detempering:{i}", self.detempering_left(i), qy, COL_W, ROW_H, "commaratio", text=_r.scalars.gens[i]))
                self._voice("quantities:detempering", i, _r.detempering.sizes.just[i])

    def _emit_qty_interests(self, qy, branch_minus) -> None:
        _r = self.resolved
        if self.tile_open("quantities", "targets"):
            self._emit_qty_list(_QtyList("targets", "target", _r.dims.k, self.target_left, _r.targets.ratios,
                                         _r.tuning.target_sizes, _r.targets.pending,
                                         "ratiocell" if _r.scalars.targets_editable else "commaratio",
                                         _r.scalars.targets_editable), qy, branch_minus)
        if self.tile_open("quantities", "held"):
            self._emit_qty_list(_QtyList("held", "held", _r.dims.nh, self.held_left, _r.held.ratios,
                                         _r.tuning.held_sizes, _r.held.pending, "ratiocell", True), qy, branch_minus)
        if self.tile_open("quantities", "interest"):
            self._emit_qty_list(_QtyList("interest", "interest", _r.dims.mi, self.interest_left, _r.interest.ratios,
                                         _r.tuning.interest_sizes, _r.interest.pending, "ratiocell", True), qy, branch_minus)

    def _qty_drag_controls(self, ckey, n, grip_top) -> None:
        _r = self.resolved
        for i in range(n):
            self.cells.append(CellBox(f"grip:{ckey}:{i}", self.sub_axis_x(ckey, i) - COL_W / 2,
                                 grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
        add_w = COL_W
        if ckey == "commas" and _r.unchanged.shown:
            add_w = _r.unchanged.empty_comma_w if _r.dims.nc_shown == 0 else V_SPLIT_GAP
        self.cells.append(CellBox(f"grip:{ckey}:add", self.plus_stub_x[ckey] - add_w / 2,
                             grip_top, add_w, GRIP_BAND, "colgrip"))

    def _emit_qty_grips(self) -> None:
        _r = self.resolved
        grip_top = self.branch_top_y + GAP - PAD
        counts = {"commas": _r.dims.nc, "targets": _r.dims.k, "held": _r.dims.nh, "interest": _r.dims.mi}
        for ckey in ("commas", "targets", "held", "interest"):
            if self.row_open("quantities") and self._plus_shows(ckey):
                self._qty_drag_controls(ckey, counts[ckey], grip_top)
        if _r.unchanged.shown:
            for j in range(_r.dims.nu):
                if _r.unchanged.basis[j] is not None:
                    self.cells.append(CellBox(f"grip:unchanged:{j}", self.sub_axis_x("commas", _r.dims.nc_shown + j) - COL_W / 2,
                                         grip_top, COL_W, GRIP_BAND, "colgrip", comma=j))

    def _emit_column_plus_controls(self) -> None:
        _r = self.resolved
        primes_plus = "element_plus" if _r.flags.nonstandard_domain else "plus"
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
        _r = self.resolved
        if self.tile_open("vectors", "commas"):
            for c in range(_r.dims.nc):
                self._vec_minus(vtop, f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
            if _r.commas.pending is not None:
                self._vec_minus(vtop, "comma_minus:pending", "commas", _r.dims.nc, "comma_minus")

    def _emit_rehomed_targets(self, vtop) -> None:
        _r = self.resolved
        if self.tile_open("vectors", "targets"):
            if _r.scalars.targets_editable:
                for j in range(_r.dims.k):
                    self._vec_minus(vtop, f"target_minus:{j}", "targets", j, "target_minus", comma=j)
            if _r.targets.pending is not None:
                self._vec_minus(vtop, "target_minus:pending", "targets", _r.dims.k, "target_minus")

    def _emit_rehomed_held(self, vtop) -> None:
        _r = self.resolved
        if self.tile_open("vectors", "held"):
            for i in range(_r.dims.nh):
                self._vec_minus(vtop, f"held_minus:{i}", "held", i, "held_minus", comma=i)
            if _r.held.pending is not None:
                self._vec_minus(vtop, "held_minus:pending", "held", _r.dims.nh, "held_minus")

    def _emit_rehomed_interest(self, vtop) -> None:
        _r = self.resolved
        if self.tile_open("vectors", "interest"):
            for i in range(_r.dims.mi):
                self._vec_minus(vtop, f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
            if _r.interest.pending is not None:
                self._vec_minus(vtop, "interest_minus:pending", "interest", _r.dims.mi, "interest_minus")

