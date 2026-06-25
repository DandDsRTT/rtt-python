from __future__ import annotations

import functools

from rtt.app import ids
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    DASH,
    ETPICK_GAP,
    ETPICK_W,
    KET_INSET,
    ROW_H,
    ROW_HANDLE_W,
)
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_models import _MappedTile


def emit_mapping(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    if not query.row_open(geometry, ctx.collapsed, "mapping"):
        return EmitResult()
    _emit_mapping_gens(cells, resolved, geometry, ctx)
    _emit_mapping_drag(cells, resolved, geometry, ctx)
    _emit_mapping_rows(cells, resolved, geometry, ctx)
    if _r.scalars.row_draft:
        _emit_mapping_draft_row(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_mapping_gens(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if not query.tile_open(geometry, ctx.collapsed, "mapping", "quantities"):
        return
    for i in range(_r.dims.r):
        cells.append(CellBox(f"gen:{query.col_token(_r, 'gens', i)}", geometry.col_x["quantities"], query.map_top(geometry, i), geometry.col_w["quantities"], ROW_H, "genratio", text=_r.scalars.gens[i] if i < len(_r.scalars.gens) else "", gen=i))
    map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
    gen_right = geometry.col_x["quantities"] + geometry.col_w["quantities"]
    if _r.dims.r > 1:
        for i in range(_r.dims.r):
            cells.append(CellBox(f"map_minus:{query.col_token(_r, 'gens', i)}", map_bus_x, query.map_top(geometry, i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
    if "mapping" in geometry.row_plus_y:
        cells.append(CellBox("map_plus", map_bus_x - BTN / 2, geometry.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))


def _emit_mapping_drag(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if ctx.settings.get("drag_to_combine") and _r.dims.r > 1 and query.tile_open(geometry, ctx.collapsed, "mapping", "primes"):
        for i in range(_r.dims.r):
            cells.append(CellBox(f"map_drag:{query.col_token(_r, 'gens', i)}", geometry.primes_x + query.etpick_left_pad(geometry, "primes"), query.map_top(geometry, i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))


def _emit_mapping_rows(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    mx, mw = query.matrix_span(geometry, resolved, "primes")
    etpick_x = mx + mw + ETPICK_GAP
    for i in range(_r.dims.r):
        rt = query.col_token(_r, "gens", i)
        if query.tile_open(geometry, ctx.collapsed, "mapping", "primes"):
            if _r.flags.presets:
                cells.append(CellBox(f"etpick:{rt}", etpick_x, query.map_top(geometry, i), ETPICK_W, ROW_H, "etpick", gen=i))
            for p in range(_r.dims.d):
                cells.append(CellBox(ids.mapping_cell(rt, p), query.prime_left(geometry, p), query.map_top(geometry, i), COL_W, ROW_H, "mapping", text=str(ctx.state.mapping[i][p]), gen=i, prime=p, unit=query.cell_unit(_r, "mapping", "primes", gen=i, prime=p)))
        if query.tile_open(geometry, ctx.collapsed, "mapping", "targets"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("mapped", "targets", _r.dims.k, lambda c: query.target_left(geometry, c), _r.targets.mapped, _r.targets.pending), i, rt)
        if query.tile_open(geometry, ctx.collapsed, "mapping", "interest"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("imapped", "interest", _r.dims.mi, lambda c: query.interest_left(geometry, c), _r.interest.mapped, _r.interest.pending), i, rt)
        if query.tile_open(geometry, ctx.collapsed, "mapping", "held"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("hmapped", "held", _r.dims.nh, lambda c: query.held_left(geometry, c), _r.tuning.held_mapped, _r.held.pending), i, rt)
        if query.tile_open(geometry, ctx.collapsed, "mapping", "commas"):
            _emit_mapping_comma_row(cells, resolved, geometry, i, rt)


def _emit_mapping_comma_row(cells, resolved, geometry, i, rt) -> None:
    _r = resolved
    for c in range(_r.dims.nc):
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.col_token(_r, 'commas', c)}", query.comma_left(geometry, _r, c), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=str(_r.commas.mapped[i][c]), gen=i, unit=query.cell_unit(_r, "mapping", "commas", gen=i)))
    if _r.scalars.comma_draft:
        mc_text = str(_r.ghosts.comma_mapped[i]) if (_r.ghosts.comma and i < len(_r.ghosts.comma_mapped)) else ""
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.pending_col_token(_r, 'commas')}", query.comma_left(geometry, _r, _r.dims.nc), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
    for j in range(_r.dims.nu):
        mapped_text = DASH if _r.unchanged.mapped[i][j] is None else str(_r.unchanged.mapped[i][j])
        cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=query.cell_unit(_r, "mapping", "commas", gen=i)))


def _emit_mapping_draft_row(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    dr = _r.dims.r
    drt = query.pending_col_token(_r, "gens")
    if query.tile_open(geometry, ctx.collapsed, "mapping", "quantities"):
        gen_text = _r.ghosts.row_ratio if _r.ghosts.row else "?"
        cells.append(CellBox("gen:pending", geometry.col_x["quantities"], query.map_top(geometry, dr), geometry.col_w["quantities"], ROW_H, "genratio", text=gen_text, gen=dr, pending=True))
        if not _r.ghosts.row:
            map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
            gen_right = geometry.col_x["quantities"] + geometry.col_w["quantities"]
            cells.append(CellBox("map_minus:pending", map_bus_x, query.map_top(geometry, dr), gen_right - map_bus_x, ROW_H, "map_minus", gen=dr, pending=True))
    if query.tile_open(geometry, ctx.collapsed, "mapping", "primes"):
        row_kind = "mapped" if _r.ghosts.row else "mapping"
        for p in range(_r.dims.d):
            v = _r.ghosts.row_map[p] if _r.ghosts.row else ctx.pending_mapping_row[p]
            cells.append(CellBox(ids.mapping_cell(drt, p), query.prime_left(geometry, p), query.map_top(geometry, dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
        if not _r.ghosts.row and _r.flags.presets:
            mx, mw = query.matrix_span(geometry, resolved, "primes")
            cells.append(CellBox("etpick:draft", mx + mw + ETPICK_GAP, query.map_top(geometry, dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
    _emit_mapping_draft_mapped(cells, resolved, geometry, ctx, dr, drt)


def _draft_mapped_text(resolved, key, j) -> str:
    _r = resolved
    vals = _r.ghosts.row_mapped.get(key, ()) if _r.ghosts.row else ()
    if j >= len(vals):
        return ""
    return DASH if vals[j] is None else str(vals[j])


def _emit_mapping_draft_mapped(cells, resolved, geometry, ctx, dr, drt) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "mapping", "targets"):
        for j in range(_r.dims.k):
            cells.append(CellBox(f"cell:mapped:{drt}:{query.col_token(_r, 'targets', j)}", query.target_left(geometry, j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(_r, "targets", j), gen=dr, pending=True))
    if query.tile_open(geometry, ctx.collapsed, "mapping", "interest"):
        for ii in range(_r.dims.mi):
            cells.append(CellBox(f"cell:imapped:{drt}:{query.col_token(_r, 'interest', ii)}", query.interest_left(geometry, ii), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(_r, "interest", ii), gen=dr, pending=True))
    if query.tile_open(geometry, ctx.collapsed, "mapping", "held"):
        for hi in range(_r.dims.nh):
            cells.append(CellBox(f"cell:hmapped:{drt}:{query.col_token(_r, 'held', hi)}", query.held_left(geometry, hi), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(_r, "held", hi), gen=dr, pending=True))
    if query.tile_open(geometry, ctx.collapsed, "mapping", "commas"):
        _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt)


def _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt) -> None:
    _r = resolved
    for c in range(_r.dims.nc):
        cells.append(CellBox(f"cell:mapped_comma:{drt}:{query.col_token(_r, 'commas', c)}", query.comma_left(geometry, _r, c), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(_r, "commas", c), gen=dr, pending=True))
    for j in range(_r.dims.nu):
        cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(_r, "unchanged", j), gen=dr, pending=True))


def _emit_mapped_tile(cells, resolved, geometry, m: _MappedTile, i, rt) -> None:
    _r = resolved
    for col in range(m.count):
        cells.append(CellBox(f"cell:{m.prefix}:{rt}:{query.col_token(_r, m.group, col)}", m.left_fn(col), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=str(m.data[i][col]), gen=i, unit=query.cell_unit(_r, "mapping", m.group, gen=i)))
    if m.pending is not None:
        cells.append(CellBox(f"cell:{m.prefix}:{rt}:draft", m.left_fn(m.count), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))


def emit_mapped_grid(cells, resolved, geometry, collapsed, tile, prefix, grid, n_cols, left, col_kw, *,
                     full=None, colwise=False, col_token_key=None, inset=0,
                     row="projection", top=None, height=None, pending=None) -> None:
    _r = resolved
    if not (query.row_open(geometry, collapsed, row) and query.tile_open(geometry, collapsed, row, tile)):
        return
    if full is None:
        full = grid is not None
    if top is None:
        top = functools.partial(query.proj_top, geometry)
    height = _r.dims.d if height is None else height
    if colwise:
        _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                                  full, col_token_key, inset, top, height, pending)
    else:
        _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, col_kw, full, inset, top, height)


def _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                              full, col_token_key, inset, top, height, pending) -> None:
    for j in range(n_cols):
        for i in range(height):
            text = str(grid[j][i]) if full else DASH
            tok = j if col_token_key is None else query.col_token(resolved, col_token_key, j)
            cells.append(CellBox(f"cell:{prefix}:{tok}:{i}", left(j) + inset, top(i),
                                 COL_W - 2 * inset, ROW_H, "mapped", text=text, prime=i, **{col_kw: j}))
    if pending is not None:
        for i in range(height):
            cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols) + inset, top(i),
                                 COL_W - 2 * inset, ROW_H, "mapped", text="", prime=i, pending=True))


def _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, col_kw,
                              full, inset, top, height) -> None:
    for i in range(height):
        for j in range(n_cols):
            text = grid[i][j] if full else DASH
            cells.append(CellBox(f"cell:{prefix}:{i}:{j}", left(j) + inset, top(i),
                                 COL_W - 2 * inset, ROW_H, "mapped", text=text, **{col_kw: j}))


class _EmitMappingMixin:
    def _emit_mapped_grid(self, tile, prefix, grid, n_cols, left, col_kw, **kw) -> None:
        emit_mapped_grid(self.cells, self.resolved, self.geometry, self.collapsed,
                         tile, prefix, grid, n_cols, left, col_kw, **kw)

    def _emit_projection_band(self) -> None:
        _r = self.resolved
        self._emit_mapped_grid("primes", "proj", _r.projection.matrix, _r.dims.d, self.prime_left, "prime")
        self._emit_mapped_grid("gens", "embed", _r.projection.embedding_matrix, _r.dims.r, self.gen_left, "gen")
        self._emit_mapped_grid("canongens", "embed_c", _r.canon.embedding_matrix, _r.dims.rc, self.canongen_left, "gen")
        self._emit_mapped_grid("ssgens", "embed_sl", _r.projection.embedding_superspace, _r.dims.rL, self.ss_gen_left, "gen")
        self._emit_mapped_grid("ssprimes", "proj_sl", _r.projection.superspace, _r.dims.dL, self.ss_prime_left, "prime")

        self._emit_projection_unchanged()
        self._emit_projection_basis()
        full_proj = _r.projection.rationals is not None
        self._emit_mapped_grid("detempering", "proj_pd", _r.projection.detempering, _r.dims.r, self.detempering_left, "gen",
                               full=full_proj, colwise=True, col_token_key="detempering")
        self._emit_mapped_grid("targets", "proj_pt", _r.projection.targets, _r.dims.k, self.target_left, "comma",
                               full=full_proj, colwise=True, pending=_r.targets.pending)
        self._emit_mapped_grid("held", "proj_ph", _r.projection.held, _r.dims.nh, self.held_left, "comma",
                               full=full_proj, colwise=True, pending=_r.held.pending)
        self._emit_mapped_grid("interest", "proj_pi", _r.projection.interest, _r.dims.mi, self.interest_left, "comma",
                               full=full_proj, colwise=True, inset=KET_INSET, pending=_r.interest.pending)
        self._emit_scaling_factors()

    def _emit_projection_unchanged(self) -> None:
        _r = self.resolved
        if not (_r.unchanged.shown and self.row_open("projection") and self.tile_open("projection", "commas")):
            return
        for c in range(_r.dims.nc):
            for p in range(_r.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:{self.col_token('commas', c)}", self.comma_left(c), self.proj_top(p),
                                     COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
        if _r.scalars.comma_draft:
            for p in range(_r.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:draft", self.comma_left(_r.dims.nc), self.proj_top(p),
                                     COL_W, ROW_H, "mapped", text="0" if _r.ghosts.comma else "", prime=p, pending=True))
        for j in range(_r.dims.nu):
            dashed = _r.unchanged.basis[j] is None
            for p in range(_r.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:u{j}", self.comma_left(_r.dims.nc_shown + j), self.proj_top(p),
                                     COL_W, ROW_H, "mapped",
                                     text=DASH if dashed else str(_r.unchanged.basis[j][p]), prime=p, comma=_r.dims.nc + j))

    def _emit_projection_basis(self) -> None:
        _r = self.resolved
        if self.row_open("projection") and self.tile_open("projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(_r.dims.d):
                self.cells.append(CellBox(f"proj_basis:{p}", bx, self.proj_top(p), COL_W, ROW_H, "prime", text=str(_r.dims.elements[p]), prime=p))

    def _emit_scaling_factors(self) -> None:
        _r = self.resolved
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            scaling = ["0"] * _r.dims.nc + [(DASH if v is None else "1") for v in _r.unchanged.basis]
            for c, lam in enumerate(scaling):
                self.cells.append(CellBox(f"cell:scaling:{self.col_token('commas', c)}", self.comma_left(self.comma_value_pos(c)), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text=lam, comma=c))
            if _r.scalars.comma_draft:
                self.cells.append(CellBox("cell:scaling:draft", self.comma_left(_r.dims.nc), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text="0" if _r.ghosts.comma else "", pending=True))

    def _emit_canon_band(self) -> None:
        _r = self.resolved
        if self.row_open("canon"):
            self._emit_canon_gens()
            self._emit_canon_primes()
            self._emit_canon_form()
            for i in range(_r.dims.rc):
                self._emit_canon_row(i)
        self._emit_canon_finv()

    def _emit_canon_gens(self) -> None:
        _r = self.resolved
        if self.tile_open("canon", "quantities"):
            for i in range(_r.dims.rc):
                self.cells.append(CellBox(f"canon:gen:{i}", self.col_x["quantities"], self.canon_top(i), self.col_w["quantities"], ROW_H, "genratio", text=_r.canon.gens[i] if i < len(_r.canon.gens) else ""))

    def _emit_canon_primes(self) -> None:
        _r = self.resolved
        if self.tile_open("canon", "primes"):
            for i in range(_r.dims.rc):
                for p in range(_r.dims.d):
                    self.cells.append(CellBox(f"cell:canon:{i}:{p}", self.prime_left(p), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(_r.canon.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("canon", "primes", gen=i, prime=p)))

    def _emit_canon_form(self) -> None:
        _r = self.resolved
        if self.tile_open("canon", "gens"):
            for i in range(len(_r.canon.form_M)):
                for j in range(len(_r.canon.form_M)):
                    self.cells.append(CellBox(f"cell:form:{i}:{j}", self.gen_left(j), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(_r.canon.form_M[i][j]), unit=self.cell_unit("canon", "gens", gen=i)))

    def _emit_canon_row(self, i: int) -> None:
        _r = self.resolved
        if self.tile_open("canon", "detempering"):
            for c in range(_r.dims.r):
                self.cells.append(CellBox(f"cell:canon_detempering:{i}:{self.col_token('detempering', c)}", self.detempering_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(_r.canon.mapped_detempering[i][c]), gen=i, unit=self.cell_unit("canon", "detempering", gen=i)))
        if self.tile_open("canon", "targets"):
            self._emit_canon_mapped_tile("canon_mapped", "targets", _r.dims.k, self.target_left, _r.canon.mapped, _r.targets.pending, i)
        if self.tile_open("canon", "interest"):
            self._emit_canon_mapped_tile("canon_imapped", "interest", _r.dims.mi, self.interest_left, _r.canon.interest_mapped, _r.interest.pending, i)
        if self.tile_open("canon", "held"):
            self._emit_canon_mapped_tile("canon_hmapped", "held", _r.dims.nh, self.held_left, _r.canon.held_mapped, _r.held.pending, i)
        if self.tile_open("canon", "commas"):
            self._emit_canon_comma_row(i)

    def _emit_canon_comma_row(self, i: int) -> None:
        _r = self.resolved
        for c in range(_r.dims.nc):
            self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.col_token('commas', c)}", self.comma_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(_r.canon.mapped_commas[i][c]), gen=i, unit=self.cell_unit("canon", "commas", gen=i)))
        if _r.scalars.comma_draft:
            self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.pending_col_token('commas')}", self.comma_left(_r.dims.nc), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
        for j in range(_r.dims.nu):
            ut = DASH if _r.canon.unchanged_mapped[i][j] is None else str(_r.canon.unchanged_mapped[i][j])
            self.cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", self.comma_left(_r.dims.nc_shown + j), self.canon_top(i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=self.cell_unit("canon", "commas", gen=i)))

    def _emit_canon_finv(self) -> None:
        _r = self.resolved
        if self.tile_open("mapping", "canongens"):
            for i in range(_r.dims.r):
                for j in range(_r.dims.rc):
                    self.cells.append(CellBox(f"cell:finv:{i}:{j}", self.canongen_left(j), self.map_top(i), COL_W, ROW_H,
                                         "formcell", text=str(_r.canon.inverse_form_M[i][j]), unit=self.cell_unit("mapping", "canongens", gen=i)))

    def _emit_canon_mapped_tile(self, prefix, group, count, left_fn, data, pending, i) -> None:
        for col in range(count):
            self.cells.append(CellBox(f"cell:{prefix}:{i}:{self.col_token(group, col)}", left_fn(col), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=self.cell_unit("canon", group, gen=i)))
        if pending is not None:
            self.cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
