from __future__ import annotations

from rtt.app import ids
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
from rtt.app.spreadsheet_models import _MappedTile


class _EmitMappingMixin:
    def _emit_mapping_band(self) -> None:
        if not self.row_open("mapping"):
            return
        self._emit_mapping_gens()
        self._emit_mapping_drag()
        self._emit_mapping_rows()
        if self.row_draft:
            self._emit_mapping_draft_row()

    def _emit_mapping_gens(self) -> None:
        if not self.tile_open("mapping", "quantities"):
            return
        for i in range(self.resolved.dims.r):
            self.cells.append(CellBox(f"gen:{self.col_token('gens', i)}", self.col_x["quantities"], self.map_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.gens[i] if i < len(self.gens) else "", gen=i))
        map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
        gen_right = self.col_x["quantities"] + self.col_w["quantities"]
        if self.resolved.dims.r > 1:
            for i in range(self.resolved.dims.r):
                self.cells.append(CellBox(f"map_minus:{self.col_token('gens', i)}", map_bus_x, self.map_top(i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
        if "mapping" in self.row_plus_y:
            self.cells.append(CellBox("map_plus", map_bus_x - BTN / 2, self.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))

    def _emit_mapping_drag(self) -> None:
        if self.settings.get("drag_to_combine") and self.resolved.dims.r > 1 and self.tile_open("mapping", "primes"):
            for i in range(self.resolved.dims.r):
                self.cells.append(CellBox(f"map_drag:{self.col_token('gens', i)}", self.primes_x + self.etpick_left_pad("primes"), self.map_top(i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))

    def _emit_mapping_rows(self) -> None:
        mx, mw = self.matrix_span("primes")
        etpick_x = mx + mw + ETPICK_GAP
        for i in range(self.resolved.dims.r):
            rt = self.col_token("gens", i)
            if self.tile_open("mapping", "primes"):
                if self.resolved.flags.presets:
                    self.cells.append(CellBox(f"etpick:{rt}", etpick_x, self.map_top(i), ETPICK_W, ROW_H, "etpick", gen=i))
                for p in range(self.resolved.dims.d):
                    self.cells.append(CellBox(ids.mapping_cell(rt, p), self.prime_left(p), self.map_top(i), COL_W, ROW_H, "mapping", text=str(self.state.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("mapping", "primes", gen=i, prime=p)))
            if self.tile_open("mapping", "targets"):
                self._emit_mapped_tile(_MappedTile("mapped", "targets", self.resolved.dims.k, self.target_left, self.resolved.targets.mapped, self.resolved.targets.pending), i, rt)
            if self.tile_open("mapping", "interest"):
                self._emit_mapped_tile(_MappedTile("imapped", "interest", self.resolved.dims.mi, self.interest_left, self.resolved.interest.mapped, self.resolved.interest.pending), i, rt)
            if self.tile_open("mapping", "held"):
                self._emit_mapped_tile(_MappedTile("hmapped", "held", self.resolved.dims.nh, self.held_left, self.resolved.tuning.held_mapped, self.resolved.held.pending), i, rt)
            if self.tile_open("mapping", "commas"):
                self._emit_mapping_comma_row(i, rt)

    def _emit_mapping_comma_row(self, i: int, rt: str) -> None:
        for c in range(self.resolved.dims.nc):
            self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.resolved.commas.mapped[i][c]), gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
        if self.comma_draft:
            mc_text = str(self.resolved.ghosts.comma_mapped[i]) if (self.resolved.ghosts.comma and i < len(self.resolved.ghosts.comma_mapped)) else ""
            self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.pending_col_token('commas')}", self.comma_left(self.resolved.dims.nc), self.map_top(i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
        for j in range(self.resolved.dims.nu):
            mapped_text = DASH if self.resolved.unchanged.mapped[i][j] is None else str(self.resolved.unchanged.mapped[i][j])
            self.cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.map_top(i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))

    def _emit_mapping_draft_row(self) -> None:
        dr = self.resolved.dims.r
        drt = self.pending_col_token("gens")
        if self.tile_open("mapping", "quantities"):
            gen_text = self.resolved.ghosts.row_ratio if self.resolved.ghosts.row else "?"
            self.cells.append(CellBox("gen:pending", self.col_x["quantities"], self.map_top(dr), self.col_w["quantities"], ROW_H, "genratio", text=gen_text, gen=dr, pending=True))
            if not self.resolved.ghosts.row:
                map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
                gen_right = self.col_x["quantities"] + self.col_w["quantities"]
                self.cells.append(CellBox("map_minus:pending", map_bus_x, self.map_top(dr), gen_right - map_bus_x, ROW_H, "map_minus", gen=dr, pending=True))
        if self.tile_open("mapping", "primes"):
            row_kind = "mapped" if self.resolved.ghosts.row else "mapping"
            for p in range(self.resolved.dims.d):
                v = self.resolved.ghosts.row_map[p] if self.resolved.ghosts.row else self.pending_mapping_row[p]
                self.cells.append(CellBox(ids.mapping_cell(drt, p), self.prime_left(p), self.map_top(dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
            if not self.resolved.ghosts.row and self.resolved.flags.presets:
                mx, mw = self.matrix_span("primes")
                self.cells.append(CellBox("etpick:draft", mx + mw + ETPICK_GAP, self.map_top(dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
        self._emit_mapping_draft_mapped(dr, drt)

    def _draft_mapped_text(self, key, j) -> str:
        vals = self.resolved.ghosts.row_mapped.get(key, ()) if self.resolved.ghosts.row else ()
        if j >= len(vals):
            return ""
        return DASH if vals[j] is None else str(vals[j])

    def _emit_mapping_draft_mapped(self, dr: int, drt: str) -> None:
        if self.tile_open("mapping", "targets"):
            for j in range(self.resolved.dims.k):
                self.cells.append(CellBox(f"cell:mapped:{drt}:{self.col_token('targets', j)}", self.target_left(j), self.map_top(dr), COL_W, ROW_H, "mapped", text=self._draft_mapped_text("targets", j), gen=dr, pending=True))
        if self.tile_open("mapping", "interest"):
            for ii in range(self.resolved.dims.mi):
                self.cells.append(CellBox(f"cell:imapped:{drt}:{self.col_token('interest', ii)}", self.interest_left(ii), self.map_top(dr), COL_W, ROW_H, "mapped", text=self._draft_mapped_text("interest", ii), gen=dr, pending=True))
        if self.tile_open("mapping", "held"):
            for hi in range(self.resolved.dims.nh):
                self.cells.append(CellBox(f"cell:hmapped:{drt}:{self.col_token('held', hi)}", self.held_left(hi), self.map_top(dr), COL_W, ROW_H, "mapped", text=self._draft_mapped_text("held", hi), gen=dr, pending=True))
        if self.tile_open("mapping", "commas"):
            self._emit_mapping_draft_commas(dr, drt)

    def _emit_mapping_draft_commas(self, dr: int, drt: str) -> None:
        for c in range(self.resolved.dims.nc):
            self.cells.append(CellBox(f"cell:mapped_comma:{drt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(dr), COL_W, ROW_H, "mapped", text=self._draft_mapped_text("commas", c), gen=dr, pending=True))
        for j in range(self.resolved.dims.nu):
            self.cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.map_top(dr), COL_W, ROW_H, "mapped", text=self._draft_mapped_text("unchanged", j), gen=dr, pending=True))

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
        height = self.resolved.dims.d if height is None else height
        if colwise:
            self._emit_mapped_grid_colwise(prefix, grid, n_cols, left, col_kw,
                                           full, col_token_key, inset, top, height, pending)
        else:
            self._emit_mapped_grid_rowwise(prefix, grid, n_cols, left, col_kw,
                                           full, inset, top, height)

    def _emit_mapped_grid_colwise(self, prefix, grid, n_cols, left, col_kw,
                                  full, col_token_key, inset, top, height, pending) -> None:
        for j in range(n_cols):
            for i in range(height):
                text = str(grid[j][i]) if full else DASH
                tok = j if col_token_key is None else self.col_token(col_token_key, j)
                self.cells.append(CellBox(f"cell:{prefix}:{tok}:{i}", left(j) + inset, top(i),
                                     COL_W - 2 * inset, ROW_H, "mapped", text=text, prime=i, **{col_kw: j}))
        if pending is not None:
            for i in range(height):
                self.cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols) + inset, top(i),
                                     COL_W - 2 * inset, ROW_H, "mapped", text="", prime=i, pending=True))

    def _emit_mapped_grid_rowwise(self, prefix, grid, n_cols, left, col_kw,
                                  full, inset, top, height) -> None:
        for i in range(height):
            for j in range(n_cols):
                text = grid[i][j] if full else DASH
                self.cells.append(CellBox(f"cell:{prefix}:{i}:{j}", left(j) + inset, top(i),
                                     COL_W - 2 * inset, ROW_H, "mapped", text=text, **{col_kw: j}))

    def _emit_projection_band(self) -> None:
        self._emit_mapped_grid("primes", "proj", self.resolved.projection.matrix, self.resolved.dims.d, self.prime_left, "prime")
        self._emit_mapped_grid("gens", "embed", self.resolved.projection.embedding_matrix, self.resolved.dims.r, self.gen_left, "gen")
        self._emit_mapped_grid("canongens", "embed_c", self.resolved.canon.embedding_matrix, self.resolved.dims.rc, self.canongen_left, "gen")
        self._emit_mapped_grid("ssgens", "embed_sl", self.resolved.projection.embedding_superspace, self.resolved.dims.rL, self.ss_gen_left, "gen")
        self._emit_mapped_grid("ssprimes", "proj_sl", self.resolved.projection.superspace, self.resolved.dims.dL, self.ss_prime_left, "prime")

        self._emit_projection_unchanged()
        self._emit_projection_basis()
        full_proj = self.resolved.projection.rationals is not None
        self._emit_mapped_grid("detempering", "proj_pd", self.resolved.projection.detempering, self.resolved.dims.r, self.detempering_left, "gen",
                               full=full_proj, colwise=True, col_token_key="detempering")
        self._emit_mapped_grid("targets", "proj_pt", self.resolved.projection.targets, self.resolved.dims.k, self.target_left, "comma",
                               full=full_proj, colwise=True, pending=self.resolved.targets.pending)
        self._emit_mapped_grid("held", "proj_ph", self.resolved.projection.held, self.resolved.dims.nh, self.held_left, "comma",
                               full=full_proj, colwise=True, pending=self.resolved.held.pending)
        self._emit_mapped_grid("interest", "proj_pi", self.resolved.projection.interest, self.resolved.dims.mi, self.interest_left, "comma",
                               full=full_proj, colwise=True, inset=KET_INSET, pending=self.resolved.interest.pending)
        self._emit_scaling_factors()

    def _emit_projection_unchanged(self) -> None:
        if not (self.resolved.unchanged.shown and self.row_open("projection") and self.tile_open("projection", "commas")):
            return
        for c in range(self.resolved.dims.nc):
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:{self.col_token('commas', c)}", self.comma_left(c), self.proj_top(p),
                                     COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
        if self.comma_draft:
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:draft", self.comma_left(self.resolved.dims.nc), self.proj_top(p),
                                     COL_W, ROW_H, "mapped", text="0" if self.resolved.ghosts.comma else "", prime=p, pending=True))
        for j in range(self.resolved.dims.nu):
            dashed = self.resolved.unchanged.basis[j] is None
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(f"cell:proj_v:{p}:u{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.proj_top(p),
                                     COL_W, ROW_H, "mapped",
                                     text=DASH if dashed else str(self.resolved.unchanged.basis[j][p]), prime=p, comma=self.resolved.dims.nc + j))

    def _emit_projection_basis(self) -> None:
        if self.row_open("projection") and self.tile_open("projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(f"proj_basis:{p}", bx, self.proj_top(p), COL_W, ROW_H, "prime", text=str(self.resolved.dims.elements[p]), prime=p))

    def _emit_scaling_factors(self) -> None:
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            scaling = ["0"] * self.resolved.dims.nc + [(DASH if v is None else "1") for v in self.resolved.unchanged.basis]
            for c, lam in enumerate(scaling):
                self.cells.append(CellBox(f"cell:scaling:{self.col_token('commas', c)}", self.comma_left(self.comma_value_pos(c)), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text=lam, comma=c))
            if self.comma_draft:
                self.cells.append(CellBox("cell:scaling:draft", self.comma_left(self.resolved.dims.nc), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text="0" if self.resolved.ghosts.comma else "", pending=True))

    def _emit_canon_band(self) -> None:
        if self.row_open("canon"):
            self._emit_canon_gens()
            self._emit_canon_primes()
            self._emit_canon_form()
            for i in range(self.resolved.dims.rc):
                self._emit_canon_row(i)
        self._emit_canon_finv()

    def _emit_canon_gens(self) -> None:
        if self.tile_open("canon", "quantities"):
            for i in range(self.resolved.dims.rc):
                self.cells.append(CellBox(f"canon:gen:{i}", self.col_x["quantities"], self.canon_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.resolved.canon.gens[i] if i < len(self.resolved.canon.gens) else ""))

    def _emit_canon_primes(self) -> None:
        if self.tile_open("canon", "primes"):
            for i in range(self.resolved.dims.rc):
                for p in range(self.resolved.dims.d):
                    self.cells.append(CellBox(f"cell:canon:{i}:{p}", self.prime_left(p), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.resolved.canon.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("canon", "primes", gen=i, prime=p)))

    def _emit_canon_form(self) -> None:
        if self.tile_open("canon", "gens"):
            for i in range(len(self.resolved.canon.form_M)):
                for j in range(len(self.resolved.canon.form_M)):
                    self.cells.append(CellBox(f"cell:form:{i}:{j}", self.gen_left(j), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.resolved.canon.form_M[i][j]), unit=self.cell_unit("canon", "gens", gen=i)))

    def _emit_canon_row(self, i: int) -> None:
        if self.tile_open("canon", "detempering"):
            for c in range(self.resolved.dims.r):
                self.cells.append(CellBox(f"cell:canon_detempering:{i}:{self.col_token('detempering', c)}", self.detempering_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.resolved.canon.mapped_detempering[i][c]), gen=i, unit=self.cell_unit("canon", "detempering", gen=i)))
        if self.tile_open("canon", "targets"):
            self._emit_canon_mapped_tile("canon_mapped", "targets", self.resolved.dims.k, self.target_left, self.resolved.canon.mapped, self.resolved.targets.pending, i)
        if self.tile_open("canon", "interest"):
            self._emit_canon_mapped_tile("canon_imapped", "interest", self.resolved.dims.mi, self.interest_left, self.resolved.canon.interest_mapped, self.resolved.interest.pending, i)
        if self.tile_open("canon", "held"):
            self._emit_canon_mapped_tile("canon_hmapped", "held", self.resolved.dims.nh, self.held_left, self.resolved.canon.held_mapped, self.resolved.held.pending, i)
        if self.tile_open("canon", "commas"):
            self._emit_canon_comma_row(i)

    def _emit_canon_comma_row(self, i: int) -> None:
        for c in range(self.resolved.dims.nc):
            self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.col_token('commas', c)}", self.comma_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.resolved.canon.mapped_commas[i][c]), gen=i, unit=self.cell_unit("canon", "commas", gen=i)))
        if self.comma_draft:
            self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.pending_col_token('commas')}", self.comma_left(self.resolved.dims.nc), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
        for j in range(self.resolved.dims.nu):
            ut = DASH if self.resolved.canon.unchanged_mapped[i][j] is None else str(self.resolved.canon.unchanged_mapped[i][j])
            self.cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.canon_top(i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=self.cell_unit("canon", "commas", gen=i)))

    def _emit_canon_finv(self) -> None:
        if self.tile_open("mapping", "canongens"):
            for i in range(self.resolved.dims.r):
                for j in range(self.resolved.dims.rc):
                    self.cells.append(CellBox(f"cell:finv:{i}:{j}", self.canongen_left(j), self.map_top(i), COL_W, ROW_H,
                                         "formcell", text=str(self.resolved.canon.inverse_form_M[i][j]), unit=self.cell_unit("mapping", "canongens", gen=i)))

    def _emit_canon_mapped_tile(self, prefix, group, count, left_fn, data, pending, i) -> None:
        for col in range(count):
            self.cells.append(CellBox(f"cell:{prefix}:{i}:{self.col_token(group, col)}", left_fn(col), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=self.cell_unit("canon", group, gen=i)))
        if pending is not None:
            self.cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
