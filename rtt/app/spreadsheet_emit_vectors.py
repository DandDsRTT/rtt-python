from __future__ import annotations

from rtt.app import ids, service
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    COMMAPICK_GAP,
    DASH,
    KET_INSET,
    ROW_H,
    ROW_HANDLE_W,
)
from rtt.app.spreadsheet_models import _QtyList, _VecGrid


class _EmitVectorsMixin:
    def _emit_qty_list(self, q: _QtyList, qy: float, branch_minus) -> None:
        for j in range(q.count):
            self.cells.append(CellBox(f"{q.singular}:{self.col_token(q.group, j)}", q.left_fn(j), qy, COL_W, ROW_H, q.kind, text=q.ratios[j], comma=j))
            self._voice(f"quantities:{q.group}", j, q.sizes.just[j])
            if q.minus_gate:
                branch_minus(f"{q.singular}_minus:{j}", q.group, j, f"{q.singular}_minus", comma=j)
        if q.pending is not None:
            self.cells.append(CellBox(f"{q.singular}:pending", q.left_fn(q.count), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=q.count, pending=True))
            branch_minus(f"{q.singular}_minus:pending", q.group, q.count, f"{q.singular}_minus")

    def _emit_vec_grid(self, g: _VecGrid) -> None:
        for col in range(g.count):
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(g.id_fn(self.col_token(g.group, col), p), g.left_fn(col) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.committed_kind, text=str(g.data[col][p]), prime=p, comma=col, unit=self.cell_unit("vectors", g.group, prime=p)))
                self._voice(f"vectors:{g.group}", col, g.sizes.just[col])
        if g.pending is not None:
            for p in range(self.resolved.dims.d):
                v = g.pending[p]
                self.cells.append(CellBox(g.id_fn(self.pending_col_token(g.group), p), g.left_fn(g.count) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.pending_kind,
                                     text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=self.cell_unit("vectors", g.group, prime=p)))

    def _emit_vectors_band(self) -> None:
        if not self.row_open("vectors"):
            return
        if self.tile_open("vectors", "quantities"):
            self._emit_vectors_basis_col()
        if self.tile_open("vectors", "commas"):
            self._emit_vectors_commas_col()
        if self.tile_open("vectors", "targets"):
            target_kind = "targetcell" if self.resolved.scalars.targets_editable else "vec"
            cell_inset = KET_INSET if self.resolved.scalars.targets_editable else 0
            self._emit_vec_grid(_VecGrid("targets", self.resolved.dims.k, ids.target_cell, self.target_left,
                cell_inset, target_kind, "targetcell", self.resolved.targets.vectors, self.resolved.targets.pending, self.resolved.tuning.target_sizes))
        if self.tile_open("vectors", "held"):
            self._emit_vec_grid(_VecGrid("held", self.resolved.dims.nh, ids.held_cell, self.held_left,
                0, "heldcell", "heldcell", self.resolved.held.vectors, self.resolved.held.pending, self.resolved.tuning.held_sizes))
        if self.tile_open("vectors", "detempering"):
            self._emit_vectors_detempering_col()
        if self.tile_open("vectors", "interest"):
            self._emit_vec_grid(_VecGrid("interest", self.resolved.dims.mi, ids.interest_cell, self.interest_left,
                KET_INSET, "interestcell", "interestcell", self.resolved.interest.vectors, self.resolved.interest.pending, self.resolved.tuning.interest_sizes))
        self._emit_vectors_int_handles()

    def _basis_col_x(self):
        bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
        basis_bus_x = self.node_edge + self.FAN if self._row_fans("vectors") else self.node_edge
        return bx, basis_bus_x

    def _emit_basis_minus(self, cid, p, kind, **kw):
        bx, basis_bus_x = self._basis_col_x()
        self.cells.append(CellBox(cid, basis_bus_x, self.vec_top(p),
                             (bx + COL_W) - basis_bus_x, ROW_H, kind, **kw))

    def _emit_vectors_basis_col(self) -> None:
        bx, basis_bus_x = self._basis_col_x()
        for p in range(self.resolved.dims.d):
            text = str(self.resolved.dims.elements[p])
            kind = self._element_cell_kind(text) if self.resolved.flags.nonstandard_domain else "prime"
            self.cells.append(CellBox(f"basis:{p}", bx, self.vec_top(p), COL_W, ROW_H, kind, text=text, prime=p))
        if self.resolved.scalars.element_draft:
            draft_text = self.pending_element or "?/?"
            self.cells.append(CellBox("basis:pending", bx, self.vec_top(self.resolved.dims.d), COL_W, ROW_H,
                                      self._element_cell_kind(draft_text), text=draft_text, prime=self.resolved.dims.d, pending=True))
            self._emit_basis_minus("element_minus:basis:pending", self.resolved.dims.d, "element_minus")
        if self.resolved.flags.nonstandard_domain:
            if self.resolved.dims.d > 1:
                for p in range(self.resolved.dims.d):
                    self._emit_basis_minus(f"element_minus:basis:{p}", p, "element_minus", prime=p)
        elif self.resolved.scalars.domain_can_shrink:
            self._emit_basis_minus("basis_minus", self.resolved.dims.d - 1, "basis_minus")
        if "vectors" in self.row_plus_y:
            plus_kind = "element_plus" if self.resolved.flags.nonstandard_domain else "plus"
            self.cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, self.row_plus_y["vectors"] - BTN / 2,
                                 BTN, BTN, plus_kind))

    def _emit_vectors_commas_col(self) -> None:
        for c in range(self.resolved.dims.nc):
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(ids.comma_cell(self.col_token('commas', c), p), self.comma_left(c), self.vec_top(p), COL_W, ROW_H, "commacell", text=str(self.state.comma_basis[c][p]), prime=p, comma=c, unit=self.cell_unit("vectors", "commas", prime=p)))
                self._voice("vectors:commas", c, self.resolved.tuning.comma_sizes.just[c])
            if self.resolved.flags.presets:
                self.cells.append(CellBox(f"commapick:{self.col_token('commas', c)}", self.comma_left(c), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=c))
        full_u = self.resolved.unchanged.basis is not None and all(v is not None for v in self.resolved.unchanged.basis)
        for j in range(self.resolved.dims.nu):
            doomed = self.resolved.commas.pending is not None and j == self.resolved.dims.nu - 1
            born = self.resolved.unchanged.born and j == self.resolved.dims.nu - 1
            for p in range(self.resolved.dims.d):
                vec_text = DASH if self.resolved.unchanged.basis[j] is None else str(self.resolved.unchanged.basis[j][p])
                self.cells.append(CellBox(ids.unchanged_cell(j, p), self.comma_left(self.resolved.dims.nc_shown + j), self.vec_top(p), COL_W, ROW_H,
                                     "unchangedcell" if (full_u and not doomed and not born) else "vec", text=vec_text, prime=p, comma=self.resolved.dims.nc + j,
                                     unit=self.cell_unit("vectors", "commas", prime=p)))
            self._voice("vectors:commas", self.resolved.dims.nc + j, self.resolved.unchanged.sizes.just[j])
        if self.resolved.scalars.comma_draft:
            col_kind = "vec" if self.resolved.ghosts.comma else "commacell"
            for p in range(self.resolved.dims.d):
                v = self.resolved.ghosts.comma_vec[p] if self.resolved.ghosts.comma else self.resolved.commas.pending[p]
                self.cells.append(CellBox(ids.comma_cell(self.pending_col_token('commas'), p), self.comma_left(self.resolved.dims.nc), self.vec_top(p), COL_W, ROW_H, col_kind,
                                     text="" if v is None else str(v), prime=p, comma=self.resolved.dims.nc, pending=True, unit=self.cell_unit("vectors", "commas", prime=p)))
            if self.resolved.commas.pending is not None and self.resolved.flags.presets:
                self.cells.append(CellBox("commapick:draft", self.comma_left(self.resolved.dims.nc), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=self.resolved.dims.nc, pending=True))

    def _emit_vectors_detempering_col(self) -> None:
        for i in range(self.resolved.dims.r):
            for p in range(self.resolved.dims.d):
                self.cells.append(CellBox(f"cell:vec:detempering:{self.col_token('detempering', i)}:{p}", self.detempering_left(i), self.vec_top(p), COL_W, ROW_H, "vec", text=str(self.resolved.detempering.vectors[i][p]), unit=self.cell_unit("vectors", "detempering", prime=p)))
                self._voice("vectors:detempering", i, self.resolved.detempering.sizes.just[i])

    def _emit_vectors_int_handles(self) -> None:
        if "vectors" in self.rows and self.rows["vectors"].int_handle_top is not None:
            hy = self.rows["vectors"].int_handle_top
            for group, count, col_left, ckey in (("comma", self.resolved.dims.nc, self.comma_left, "commas"),
                                                 ("target", self.resolved.dims.k, self.target_left, "targets"),
                                                 ("held", self.resolved.dims.nh, self.held_left, "held"),
                                                 ("interest", self.resolved.dims.mi, self.interest_left, "interest")):
                if count >= 2 and self.tile_open("vectors", ckey) and (ckey != "targets" or self.resolved.scalars.targets_editable):
                    for i in range(count):
                        self.cells.append(CellBox(f"int_drag:{group}:{i}", col_left(i), hy, COL_W, ROW_HANDLE_W, "int_drag", comma=i))

    def _emit_superspace_rows(self) -> None:
        self._emit_ss_quantity_rows()
        self._emit_ss_matrix_rows()
        self._emit_ss_vector_lists()
        self._emit_ss_projection_rows()

    def _emit_ss_quantity_rows(self) -> None:
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"ss_basis:{p}", bx, self.ss_vec_top(p), COL_W, ROW_H,
                                          "prime", text=str(self.resolved.dims.superspace_primes[p]), prime=p))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "quantities"):
            ss_gens = service.superspace_generators(self.state)
            for i in range(self.resolved.dims.rL):
                self.cells.append(CellBox(f"ss_gen:{i}", self.col_x["quantities"], self.ss_map_top(i),
                                          self.col_w["quantities"], ROW_H, "genratio",
                                          text=ss_gens[i] if i < len(ss_gens) else ""))
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"ss_proj_basis:{p}", bx, self.ss_proj_top(p), COL_W, ROW_H, "prime",
                                          text=str(self.resolved.dims.superspace_primes[p]), prime=p))

    def _emit_ss_matrix_rows(self) -> None:
        self._emit_ss_matrix_vectors()
        self._emit_ss_matrix_mapping()

    def _emit_ss_matrix_vectors(self) -> None:
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "primes"):
            basis = service.basis_in_superspace(self.resolved.dims.elements)
            for ss_prime_idx in range(self.resolved.dims.dL):
                for elem_idx in range(self.resolved.dims.d):
                    value = basis[elem_idx][ss_prime_idx]
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}",
                        self.prime_left(elem_idx), self.ss_vec_top(ss_prime_idx), COL_W, ROW_H,
                        "vec", text=str(value), prime=ss_prime_idx, comma=elem_idx,
                        unit=self.cell_unit("ss_vectors", "primes", prime=ss_prime_idx, elem=elem_idx),
                    ))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            ml = service.superspace_mapping(self.state)
            for gen_idx in range(self.resolved.dims.rL):
                for ss_prime_idx in range(self.resolved.dims.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}",
                        self.ss_prime_left(ss_prime_idx), self.ss_map_top(gen_idx), COL_W, ROW_H,
                        "mapped", text=str(ml[gen_idx][ss_prime_idx]),
                        gen=gen_idx, prime=ss_prime_idx,
                        unit=self.cell_unit("ss_mapping", "ssprimes", gen=gen_idx, prime=ss_prime_idx),
                    ))
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            mjl = service.superspace_just_mapping(self.resolved.dims.superspace_primes)
            for i in range(self.resolved.dims.dL):
                for j in range(self.resolved.dims.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_vec_top(i), COL_W, ROW_H,
                        "mapped", text=str(mjl[i][j]), gen=i, prime=j,
                        unit=self.cell_unit("ss_vectors", "ssprimes", prime=j)))

    def _emit_ss_matrix_mapping(self) -> None:
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            mlgl = service.superspace_self_map(self.state)
            for i in range(self.resolved.dims.rL):
                for j in range(self.resolved.dims.rL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssgens:{i}:{j}",
                        self.ss_gen_left(j), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(mlgl[i][j]), gen=i,
                        unit=self.cell_unit("ss_mapping", "ssgens", gen=i)))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            msl = service.mapping_to_superspace_generators(self.state)
            for i in range(self.resolved.dims.rL):
                for e in range(self.resolved.dims.d):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:primes:{i}:{e}",
                        self.prime_left(e), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(msl[i][e]), gen=i,
                        unit=self.cell_unit("ss_mapping", "primes", gen=i, elem=e)))

    def _emit_ss_vector_lists(self) -> None:
        ss_lists = (("commas", self.state.comma_basis, self.resolved.dims.nc, self.comma_left, self.resolved.scalars.comma_draft),
                    ("targets", self.resolved.targets.vectors, self.resolved.dims.k, self.target_left, self.resolved.targets.pending is not None),
                    ("held", self.resolved.held.vectors, self.resolved.dims.nh, self.held_left, self.resolved.held.pending is not None),
                    ("interest", self.resolved.interest.vectors, self.resolved.dims.mi, self.interest_left, self.resolved.interest.pending is not None),
                    ("detempering", self.resolved.detempering.vectors, self.resolved.dims.r, self.detempering_left, False))
        for row in ss_lists:
            self._emit_ss_vector_list_lift(row)
            self._emit_ss_vector_list_map(row)

    def _emit_ss_vector_list_lift(self, row) -> None:
        ckey, vectors, n, left, draft = row
        cols = tuple(vectors)[:n]
        if not (self.row_open("ss_vectors") and self.tile_open("ss_vectors", ckey)):
            return
        lifted = service.lift_vectors_to_superspace(self.resolved.dims.elements, cols)
        for c in range(len(lifted)):
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(
                    f"cell:ss_vectors:{ckey}:{p}:{c}", left(c), self.ss_vec_top(p),
                    COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                    unit=self.cell_unit("ss_vectors", ckey, prime=p)))
        if draft:
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"cell:ss_vectors:{ckey}:{p}:draft", left(n), self.ss_vec_top(p),
                                     COL_W, ROW_H, "vec", text="", prime=p, pending=True))
        if ckey == "commas":
            for j in range(self.resolved.dims.nu):
                uj = self.resolved.projection.ss_unchanged[j]
                for p in range(self.resolved.dims.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:commas:{p}:u{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.ss_vec_top(p),
                        COL_W, ROW_H, "vec", text=DASH if uj is None else str(uj[p]), prime=p, comma=self.resolved.dims.nc + j,
                        unit=self.cell_unit("ss_vectors", "commas", prime=p)))

    def _emit_ss_vector_list_map(self, row) -> None:
        ckey, vectors, n, left, draft = row
        cols = tuple(vectors)[:n]
        if not (self.row_open("ss_mapping") and self.tile_open("ss_mapping", ckey)):
            return
        mapped = service.map_vectors_into_superspace_generators(self.state, cols)
        for c in range(len(mapped)):
            for g in range(self.resolved.dims.rL):
                self.cells.append(CellBox(
                    f"cell:ss_mapping:{ckey}:{g}:{c}", left(c), self.ss_map_top(g),
                    COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                    unit=self.cell_unit("ss_mapping", ckey, gen=g)))
        if draft:
            for g in range(self.resolved.dims.rL):
                self.cells.append(CellBox(f"cell:ss_mapping:{ckey}:{g}:draft", left(n), self.ss_map_top(g),
                                     COL_W, ROW_H, "mapped", text="", gen=g, pending=True))
        if ckey == "commas":
            for j in range(self.resolved.dims.nu):
                uj = self.resolved.projection.ss_unchanged_mapped[j]
                for g in range(self.resolved.dims.rL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:commas:{g}:u{j}", self.comma_left(self.resolved.dims.nc_shown + j), self.ss_map_top(g),
                        COL_W, ROW_H, "mapped", text=DASH if uj is None else str(uj[g]), gen=g, comma=self.resolved.dims.nc + j,
                        unit=self.cell_unit("ss_mapping", "commas", gen=g)))

    def _emit_ss_projection_rows(self) -> None:
        self._emit_ss_proj_ssprimes()
        ss_full = self.resolved.projection.ss_rationals is not None
        self._emit_ss_proj_ssgens(ss_full)
        self._emit_ss_proj_primes(ss_full)
        _ssp = {"full": ss_full, "colwise": True, "row": "ss_projection", "top": self.ss_proj_top, "height": self.resolved.dims.dL}
        self._emit_mapped_grid("detempering", "ss_proj_pd", self.resolved.projection.ss_detempering, self.resolved.dims.r, self.detempering_left, "gen", **_ssp)
        self._emit_ss_proj_commas()
        self._emit_mapped_grid("targets", "ss_proj_pt", self.resolved.projection.ss_targets, self.resolved.dims.k, self.target_left, "comma",
                               pending=self.resolved.targets.pending, **_ssp)
        self._emit_mapped_grid("held", "ss_proj_ph", self.resolved.projection.ss_held, self.resolved.dims.nh, self.held_left, "comma",
                               pending=self.resolved.held.pending, **_ssp)
        self._emit_mapped_grid("interest", "ss_proj_pi", self.resolved.projection.ss_interest, self.resolved.dims.mi, self.interest_left, "comma",
                               inset=KET_INSET, pending=self.resolved.interest.pending, **_ssp)

    def _emit_ss_proj_ssprimes(self) -> None:
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            full = self.resolved.projection.ss_matrix is not None
            for i in range(self.resolved.dims.dL):
                for j in range(self.resolved.dims.dL):
                    text = DASH if not full else self.resolved.projection.ss_matrix[i][j]
                    self.cells.append(CellBox(
                        f"cell:ss_projection:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_proj_top(i), COL_W, ROW_H,
                        "mapped", text=text, gen=i, prime=j,
                        unit=self.cell_unit("ss_projection", "ssprimes", gen=i, prime=j),
                    ))

    def _emit_ss_proj_ssgens(self, ss_full) -> None:
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssgens"):
            for i in range(self.resolved.dims.dL):
                for g in range(self.resolved.dims.rL):
                    text = DASH if not ss_full else self.resolved.projection.ss_embedding_matrix[i][g]
                    self.cells.append(CellBox(f"cell:ss_embed:{i}:{g}", self.ss_gen_left(g), self.ss_proj_top(i),
                                         COL_W, ROW_H, "mapped", text=text, gen=g))

    def _emit_ss_proj_primes(self, ss_full) -> None:
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "primes"):
            for e in range(self.resolved.dims.d):
                for p in range(self.resolved.dims.dL):
                    text = DASH if not ss_full else str(self.resolved.projection.ss_basis[e][p])
                    self.cells.append(CellBox(f"cell:ss_proj_bls:{e}:{p}", self.prime_left(e), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text=text, prime=p, comma=e))

    def _emit_ss_proj_commas(self) -> None:
        if not (self.resolved.unchanged.shown and self.row_open("ss_projection") and self.tile_open("ss_projection", "commas")):
            return
        for c in range(self.resolved.dims.nc):
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{c}", self.comma_left(c), self.ss_proj_top(p),
                                     COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
        if self.resolved.commas.pending is not None:
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"cell:ss_proj_v:{p}:draft", self.comma_left(self.resolved.dims.nc), self.ss_proj_top(p),
                                     COL_W, ROW_H, "mapped", text="", prime=p, pending=True))
        for j in range(self.resolved.dims.nu):
            dashed = self.resolved.projection.ss_unchanged[j] is None
            for p in range(self.resolved.dims.dL):
                self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{self.resolved.dims.nc + j}", self.comma_left(self.resolved.dims.nc_shown + j), self.ss_proj_top(p),
                                     COL_W, ROW_H, "mapped",
                                     text=DASH if dashed else str(self.resolved.projection.ss_unchanged[j][p]), prime=p, comma=self.resolved.dims.nc + j))

    def _emit_identity_objects(self) -> None:
        self._emit_identity_vec_primes()
        for ckey, prefix, left in (("gens", "selfmap", self.gen_left),
                                   ("detempering", "mapped_detempering", self.detempering_left)):
            if self.tile_open("mapping", ckey):
                for i in range(self.resolved.dims.r):
                    for k in range(self.resolved.dims.r):
                        self.cells.append(CellBox(
                            f"cell:{prefix}:{i}:{k}", left(k), self.map_top(i), COL_W, ROW_H,
                            "mapped", text="1" if i == k else "0", gen=i,
                            unit=self.cell_unit("mapping", ckey, gen=i)))
        self._emit_identity_canongens()

    def _emit_identity_vec_primes(self) -> None:
        if self.tile_open("vectors", "primes"):
            for i in range(self.resolved.dims.d):
                for k in range(self.resolved.dims.d):
                    self.cells.append(CellBox(
                        f"cell:vec:primes:{i}:{k}", self.prime_left(k), self.vec_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i, prime=k,
                        unit=self.cell_unit("vectors", "primes", prime=k)))

    def _emit_identity_canongens(self) -> None:
        if self.tile_open("canon", "canongens"):
            for i in range(self.resolved.dims.rc):
                for k in range(self.resolved.dims.rc):
                    self.cells.append(CellBox(
                        f"cell:fcancel:{i}:{k}", self.canongen_left(k), self.canon_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i,
                        unit=self.cell_unit("canon", "canongens", gen=i)))
