from __future__ import annotations

from rtt.app import service
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BRACE_H,
    BRACKET_W,
    COL_W,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    MARK_INSET,
    ROW_H,
    SEP_W,
    TRANSPOSE_W,
    V_SPLIT_GAP,
    VAL_BRACKET_H,
)


class _BracketsMixin:
    def bracket(self, bid: str, rkey: str, ckey: str, y, h, *, fit=False, span=None, pending=False,
                stacked=False) -> None:
        if not self.show_ebk:
            if stacked:
                return
            glyphs = ("[", "]")
        else:
            c = self._ebk(rkey, ckey)
            glyphs = (c.inner_open, c.inner_close) if stacked else (c.outer_open, c.outer_close)
        gx, gw = span if span else self.matrix_span(ckey)
        if fit and not self.show_ebk:
            by, bh = y, h
        elif fit:
            by = y - (FRAME_H + FRAME_GAP) - FRAME_OVERHANG
            bh = h + (FRAME_H + FRAME_GAP) + (FRAME_GAP + BRACE_H) + 2 * FRAME_OVERHANG
        else:
            by, bh = y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H
        self.cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0], pending=pending))
        self.cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1], pending=pending))

    def _ebk(self, rkey, ckey):
        return service.ebk_convention(rkey, ckey, superspace=self.show_superspace)

    def _ebk_foot(self, rkey, ckey, *, outer: bool) -> str:
        c = self._ebk(rkey, ckey)
        return "ebkbrace" if (c.outer_close if outer else c.inner_close) == "}" else "ebkangle"

    def matrix_frame(self, rkey: str, ckey: str, bid: str, span=None) -> None:
        if not self.tile_open(rkey, ckey):
            return
        foot = self._ebk_foot(rkey, ckey, outer=True)
        gx, gw = span if span else self.matrix_span(ckey)
        if not self.show_ebk:
            y, h = self.rows[rkey].y, self.rows[rkey].h
            self.cells.append(CellBox(f"bracket:{bid}:l", gx, y, BRACKET_W, h, "bracket", text="["))
            self.cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, y, BRACKET_W, h, "bracket", text="]"))
            return
        self.cells.append(CellBox(f"ebktop:{bid}", gx, self.frame_top_y(rkey), gw, FRAME_H, "ebktop"))
        self.cells.append(CellBox(f"{foot}:{bid}", gx, self.frame_brace_y(rkey), gw, BRACE_H, foot))

    def vector_list_marks(self, rkey, name, ckey, left, n_cols, top="ebktop", separators=True, pending_col=-1) -> None:
        if not self.tile_open(rkey, ckey):
            return
        foot = self._ebk_foot(rkey, ckey, outer=False)
        if self.show_ebk:
            mark_w = COL_W - 2 * MARK_INSET
            for c in range(n_cols):
                mx = left(c) + MARK_INSET
                pend = (c == pending_col)
                self.cells.append(CellBox(f"{top}:{name}:{c}", mx, self.frame_top_y(rkey), mark_w, FRAME_H, top, pending=pend))
                self.cells.append(CellBox(f"{foot}:{name}:{c}", mx, self.frame_brace_y(rkey), mark_w, BRACE_H, foot, pending=pend))
        elif n_cols:
            if ckey == "interest":
                for c in range(n_cols):
                    self.transpose_mark(f"{name}:{c}", left(c) + COL_W - MARK_INSET, rkey, pending=(c == pending_col))
            else:
                gx, gw = self.matrix_span(ckey)
                self.transpose_mark(name, gx + gw, rkey)
        if not separators:
            return
        if self.show_ebk:
            sep_y = self.frame_top_y(rkey) - FRAME_OVERHANG
            sep_h = self.frame_brace_y(rkey) + BRACE_H + FRAME_OVERHANG - sep_y
        else:
            sep_y, sep_h = self.rows[rkey].y, self.rows[rkey].h
        for c in range(1, n_cols):
            self.cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, sep_y, SEP_W, sep_h, "vbar"))

    def transpose_mark(self, name, x, rkey, pending: bool = False) -> None:
        self.cells.append(CellBox(f"transpose:{name}", x, self.rows[rkey].y - FRAME_GAP, TRANSPOSE_W, ROW_H,
                             "transpose", text="ᵀ", pending=pending))

    def v_split_bars(self) -> None:
        if not self.show_unchanged or self.commas_x is None or self.nc_shown == 0 or self.nu == 0:
            return
        x = self.comma_left(self.nc_shown) - V_SPLIT_GAP / 2 - SEP_W / 2
        u_left = self.comma_left(self.nc_shown)
        u_right = u_left + self.nu * COL_W
        rows_with_u = set()
        for cell in self.cells:
            if u_left - 0.5 <= cell.x < u_right:
                for rkey, band in self.rows.items():
                    if band.y <= cell.y < band.y + band.h:
                        rows_with_u.add(rkey)
                        break
        for rkey in rows_with_u:
            if rkey != "counts" and self.tile_open(rkey, "commas"):
                self.cells.append(CellBox(f"vsplit:{rkey}", x, self.rows[rkey].y, SEP_W, self.rows[rkey].h, "vbar"))

    def _emit_brackets(self) -> None:
        self._emit_canon_brackets()
        self._emit_projection_brackets()
        self._emit_mapping_brackets()
        self._emit_ss_matrix_brackets()
        self._emit_vector_brackets()
        self._emit_prescaling_brackets()
        self._emit_scalar_row_brackets()

    def _emit_canon_brackets(self) -> None:
        self._emit_canon_stacked_brackets()
        self._emit_canon_fit_brackets()

    def _emit_canon_stacked_brackets(self) -> None:
        if self.row_open("canon") and self.tile_open("canon", "primes"):
            for i in range(self.rc):
                self.bracket(f"canon:map:{i}", "canon", "primes", self.canon_top(i), ROW_H, stacked=True)
                self.bracket(f"form:map:{i}", "canon", "gens", self.canon_top(i), ROW_H, stacked=True)
        if self.row_open("canon") and self.tile_open("canon", "canongens"):
            for i in range(self.rc):
                self.bracket(f"fcancel:map:{i}", "canon", "canongens", self.canon_top(i), ROW_H, stacked=True)
        if self.tile_open("mapping", "canongens"):
            for i in range(self.r):
                self.bracket(f"finv:map:{i}", "mapping", "canongens", self.map_top(i), ROW_H, stacked=True)

    def _emit_canon_fit_brackets(self) -> None:
        if not self.row_open("canon"):
            return
        canon_y, canon_h = (self.rows["canon"].y if "canon" in self.rows else 0), self.rc * ROW_H
        if self.tile_open("canon", "detempering"):
            self.bracket("canon_detempering", "canon", "detempering", canon_y, canon_h, fit=True)
        if self.tile_open("canon", "commas"):
            self.bracket("canon_comma", "canon", "commas", canon_y, canon_h, fit=True)
        if self.tile_open("canon", "targets"):
            self.bracket("canon_mapped", "canon", "targets", canon_y, canon_h, fit=True)
        if self.nh and self.tile_open("canon", "held"):
            self.bracket("canon_hmapped", "canon", "held", canon_y, canon_h, fit=True)

    def _emit_projection_brackets(self) -> None:
        if not self.row_open("projection"):
            return
        self._emit_projection_embed_brackets()
        self._emit_projection_list_brackets()

    def _emit_projection_embed_brackets(self) -> None:
        py, ph = self.rows["projection"].y, self.d * ROW_H
        if self.tile_open("projection", "primes"):
            for i in range(self.d):
                self.bracket(f"proj:{i}", "projection", "primes", self.proj_top(i), ROW_H, stacked=True)
        if self.tile_open("projection", "gens"):
            self.bracket("embed", "projection", "gens", py, ph, fit=True)
        if self.tile_open("projection", "canongens"):
            self.bracket("embed_c", "projection", "canongens", py, ph, fit=True)
        if self.tile_open("projection", "ssgens"):
            self.bracket("embed_sl", "projection", "ssgens", py, ph, fit=True)

    def _emit_projection_list_brackets(self) -> None:
        py, ph = self.rows["projection"].y, self.d * ROW_H
        if self.tile_open("projection", "ssprimes"):
            for i in range(self.d):
                self.bracket(f"proj_sl:{i}", "projection", "ssprimes", self.proj_top(i), ROW_H, stacked=True)
        if self.show_unchanged and self.tile_open("projection", "commas"):
            self.bracket("proj_v", "projection", "commas", py, ph, fit=True)
        if self.tile_open("projection", "detempering"):
            self.bracket("proj_pd", "projection", "detempering", py, ph, fit=True)
        if self.tile_open("projection", "targets"):
            self.bracket("proj_pt", "projection", "targets", py, ph, fit=True)
        if self.tile_open("projection", "held"):
            self.bracket("proj_ph", "projection", "held", py, ph, fit=True)

    def _emit_mapping_brackets(self) -> None:
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            self.bracket("scaling", "scaling_factors", "commas", self.rows["scaling_factors"].y, ROW_H)
        if self.row_open("mapping"):
            if self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.bracket(f"map:{i}", "mapping", "primes", self.map_top(i), ROW_H, stacked=True)
                if self.pending_mapping_row is not None:
                    self.bracket("map:pending", "mapping", "primes", self.map_top(self.r), ROW_H, pending=True, stacked=True)
            if self.tile_open("mapping", "commas"):
                self.bracket("mapped_comma", "mapping", "commas", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)
            if self.tile_open("mapping", "targets"):
                self.bracket("mapped", "mapping", "targets", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)
            if self.nh and self.tile_open("mapping", "held"):
                self.bracket("hmapped", "mapping", "held", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)

    def _emit_ss_matrix_brackets(self) -> None:
        self._emit_ss_stacked_brackets()
        self._emit_ss_proj_fit_brackets()
        self._emit_ss_rest_brackets()

    def _emit_ss_stacked_brackets(self) -> None:
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            for i in range(self.rL):
                self.bracket(f"ss_map:{i}", "ss_mapping", "ssprimes", self.ss_map_top(i), ROW_H, stacked=True)
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_proj:{i}", "ss_projection", "ssprimes", self.ss_proj_top(i), ROW_H, stacked=True)

    def _emit_ss_proj_fit_brackets(self) -> None:
        ssp_top, ssp_h = (self.rows["ss_projection"].y if "ss_projection" in self.rows else 0), self.dL * ROW_H
        if self.row_open("ss_projection"):
            if self.tile_open("ss_projection", "ssgens"):
                self.bracket("ss_embed", "ss_projection", "ssgens", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "primes"):
                self.bracket("ss_proj_bls", "ss_projection", "primes", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "detempering"):
                self.bracket("ss_proj_pd", "ss_projection", "detempering", ssp_top, ssp_h, fit=True)
            if self.show_unchanged and self.tile_open("ss_projection", "commas"):
                self.bracket("ss_proj_v", "ss_projection", "commas", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "targets"):
                self.bracket("ss_proj_pt", "ss_projection", "targets", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "held"):
                self.bracket("ss_proj_ph", "ss_projection", "held", ssp_top, ssp_h, fit=True)

    def _emit_ss_rest_brackets(self) -> None:
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_vec_jmap:{i}", "ss_vectors", "ssprimes", self.ss_vec_top(i), ROW_H, stacked=True)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            for i in range(self.rL):
                self.bracket(f"ss_msl:{i}", "ss_mapping", "primes", self.ss_map_top(i), ROW_H, stacked=True)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            self.bracket("ss_selfmap", "ss_mapping", "ssgens",
                         self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)

    def _emit_vector_brackets(self) -> None:
        self._emit_vector_stacked_brackets()
        self._emit_ss_vectors_list_brackets()
        self._emit_ss_mapped_list_brackets()
        self._emit_vec_list_brackets()

    def _emit_vector_stacked_brackets(self) -> None:
        if self.tile_open("vectors", "primes"):
            for i in range(self.d):
                self.bracket(f"vec:primes:{i}", "vectors", "primes", self.vec_top(i), ROW_H, stacked=True)
        if self.tile_open("mapping", "gens"):
            self.bracket("selfmap", "mapping", "gens",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)
        if self.tile_open("mapping", "detempering"):
            self.bracket("mapped_detempering", "mapping", "detempering",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)

    def _emit_ss_vectors_list_brackets(self) -> None:
        if self.row_open("ss_vectors"):
            if self.tile_open("ss_vectors", "primes"):
                self.bracket("ss_vec:primes", "ss_vectors", "primes", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            for group in ("commas", "targets"):
                if self.tile_open("ss_vectors", group):
                    self.bracket(f"ss_vec:{group}", "ss_vectors", group, self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_vectors", "held"):
                self.bracket("ss_vec:held", "ss_vectors", "held", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            if self.tile_open("ss_vectors", "detempering"):
                self.bracket("ss_vec:detempering", "ss_vectors", "detempering", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)

    def _emit_ss_mapped_list_brackets(self) -> None:
        if self.row_open("ss_mapping"):
            for group in ("commas", "targets"):
                if self.tile_open("ss_mapping", group):
                    self.bracket(f"ss_mapped:{group}", "ss_mapping", group, self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_mapping", "held"):
                self.bracket("ss_mapped:held", "ss_mapping", "held", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.tile_open("ss_mapping", "detempering"):
                self.bracket("ss_mapped:detempering", "ss_mapping", "detempering", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)

    def _emit_vec_list_brackets(self) -> None:
        if self.row_open("vectors"):
            for group in ("commas", "targets"):
                if self.tile_open("vectors", group):
                    self.bracket(f"vec:{group}", "vectors", group, self.rows["vectors"].y, self.d * ROW_H, fit=True)
            if self.nh and self.tile_open("vectors", "held"):
                self.bracket("vec:held", "vectors", "held", self.rows["vectors"].y, self.d * ROW_H, fit=True)
            if self.tile_open("vectors", "detempering"):
                self.bracket("vec:detempering", "vectors", "detempering", self.rows["vectors"].y, self.d * ROW_H, fit=True)

    def _emit_prescaling_brackets(self) -> None:
        if self.row_open("prescaling"):
            ph = (self.prescale_rows + self.size_rows) * ROW_H
            bare_col = "ssprimes" if self.show_superspace else "primes"
            for group in ("commas", "detempering", "targets", "held"):
                if self.tile_open("prescaling", group):
                    self.bracket(f"prescaling:{group}", "prescaling", group,
                            self.rows["prescaling"].y, ph, fit=True)
            if self.show_superspace and self.tile_open("prescaling", "primes"):
                self.bracket("prescaling:primes", "prescaling", "primes",
                        self.rows["prescaling"].y, ph, fit=True)
            if self.tile_open("prescaling", bare_col):
                pspan = self.matrix_span(bare_col)
                for i in range(self.prescale_rows + self.size_rows):
                    self.bracket(f"prescaling:row:{i}", "prescaling", bare_col,
                            self.rows["prescaling"].y + i * ROW_H, ROW_H, span=pspan, stacked=True)
                if self.size_rows:
                    gx, gw = pspan
                    self.cells.append(CellBox("bar:prescaling", gx, self.rows["prescaling"].y + self.prescale_rows * ROW_H - SEP_W / 2,
                                         gw, SEP_W, "hbar"))

    def _emit_scalar_row_brackets(self) -> None:
        self._emit_tuning_map_brackets()
        for key in ("tuning", "just", "retune", "complexity"):
            if self.row_open(key):
                self._emit_list_row_brackets(key)
        if self.tile_open("weight", "targets"):
            self.bracket("weight", "weight", "targets", self.rows["weight"].y, ROW_H)
        if self.tile_open("damage", "targets"):
            self.bracket("damage", "damage", "targets", self.rows["damage"].y, ROW_H)

    def _emit_tuning_map_brackets(self) -> None:
        if self.tile_open("tuning", "gens"):
            self.bracket("tuning:genmap", "tuning", "gens", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "canongens"):
            self.bracket("tuning:cangenmap", "tuning", "canongens", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "detempering"):
            self.bracket("tuning:detempering", "tuning", "detempering", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "ssgens"):
            self.bracket("tuning:ssgenmap", "tuning", "ssgens", self.rows["tuning"].y, ROW_H)

    def _emit_list_row_brackets(self, key: str) -> None:
        if self.tile_open(key, "primes"):
            self.bracket(f"{key}:map", key, "primes", self.rows[key].y, ROW_H)
        if self.tile_open(key, "commas"):
            self.bracket(f"{key}:commalist", key, "commas", self.rows[key].y, ROW_H)
        if self.tile_open(key, "targets"):
            self.bracket(f"{key}:list", key, "targets", self.rows[key].y, ROW_H)
        if self.nh and self.tile_open(key, "held"):
            self.bracket(f"{key}:hlist", key, "held", self.rows[key].y, ROW_H)
        if key != "tuning" and self.tile_open(key, "detempering"):
            self.bracket(f"{key}:detemperinglist", key, "detempering", self.rows[key].y, ROW_H)
        if (key != "complexity" or self.show_superspace) and self.tile_open(key, "ssprimes"):
            self.bracket(f"{key}:ssprimes", key, "ssprimes", self.rows[key].y, ROW_H)

    def _emit_ebk_frames_and_marks(self) -> None:
        self._emit_ebk_frames()
        self._emit_ebk_marks()
        self._emit_ebk_vector_marks()

    def _emit_ebk_frames(self) -> None:
        self.matrix_frame("mapping", "primes", "primes")
        self.matrix_frame("projection", "primes", "proj")
        self.matrix_frame("projection", "ssprimes", "proj_sl")
        self.matrix_frame("canon", "primes", "canon")
        self.matrix_frame("canon", "gens", "form")
        self.matrix_frame("canon", "canongens", "fcancel")
        self.matrix_frame("mapping", "canongens", "finv")
        self.matrix_frame("prescaling", "ssprimes" if self.show_superspace else "primes", "prescaling")
        self.matrix_frame("ss_mapping", "ssprimes", "ss_mapping")
        self.matrix_frame("ss_projection", "ssprimes", "ss_proj")
        self.matrix_frame("ss_vectors", "ssprimes", "ss_vec_jmap")
        self.matrix_frame("ss_mapping", "primes", "ss_msl")
        self.matrix_frame("vectors", "primes", "vec:primes")

    def _emit_ebk_marks(self) -> None:
        self.vector_list_marks("mapping", "mapped_comma", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("projection", "proj_v", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("projection", "embed", "gens", self.gen_left, self.r, separators=False)
        self.vector_list_marks("projection", "embed_c", "canongens", self.canongen_left, self.rc, separators=False)
        self.vector_list_marks("projection", "embed_sl", "ssgens", self.ss_gen_left, self.rL, separators=False)
        self.vector_list_marks("projection", "proj_pd", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("projection", "proj_pt", "targets", self.target_left, self.k)
        self.vector_list_marks("projection", "proj_ph", "held", self.held_left, self.nh)
        self.vector_list_marks("projection", "proj_pi", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("ss_projection", "ss_embed", "ssgens", self.ss_gen_left, self.rL, separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_bls", "primes", self.prime_left, self.d, separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_pd", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_v", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_pt", "targets", self.target_left, self.k)
        self.vector_list_marks("ss_projection", "ss_proj_ph", "held", self.held_left, self.nh)
        self.vector_list_marks("ss_projection", "ss_proj_pi", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("mapping", "mapped", "targets", self.target_left, self.k)
        self.vector_list_marks("mapping", "imapped", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("mapping", "hmapped", "held", self.held_left, self.nh)
        self.vector_list_marks("mapping", "selfmap", "gens", self.gen_left, self.r, separators=False)
        self.vector_list_marks("mapping", "mapped_detempering", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("canon", "canon_detempering", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("canon", "canon_comma", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("canon", "canon_mapped", "targets", self.target_left, self.k)
        self.vector_list_marks("canon", "canon_imapped", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("canon", "canon_hmapped", "held", self.held_left, self.nh)

    def _emit_ebk_vector_marks(self) -> None:
        self.vector_list_marks("vectors", "vec:commas", "commas", self.comma_left, self.nv_shown, separators=False,
                         pending_col=(self.nc if self.pending is not None else -1))
        self.vector_list_marks("vectors", "vec:targets", "targets", self.target_left, self.k_shown,
                         pending_col=(self.k if self.pending_target is not None else -1))
        self.vector_list_marks("vectors", "vec:interest", "interest", self.interest_left, self.mi_shown, separators=False,
                         pending_col=(self.mi if self.pending_interest is not None else -1))
        self.vector_list_marks("vectors", "vec:held", "held", self.held_left, self.nh_shown,
                         pending_col=(self.nh if self.pending_held is not None else -1))
        self.vector_list_marks("vectors", "vec:detempering", "detempering", self.detempering_left, self.r)
        self.vector_list_marks("ss_vectors", "ss_vec:primes", "primes", self.prime_left, self.d, separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:commas", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:targets", "targets", self.target_left, self.k)
        self.vector_list_marks("ss_vectors", "ss_vec:held", "held", self.held_left, self.nh)
        self.vector_list_marks("ss_vectors", "ss_vec:interest", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:detempering", "detempering", self.detempering_left, self.r)
        self.vector_list_marks("ss_mapping", "ss_mapped:commas", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:targets", "targets", self.target_left, self.k)
        self.vector_list_marks("ss_mapping", "ss_mapped:held", "held", self.held_left, self.nh)
        if self.show_superspace:
            self.vector_list_marks("prescaling", "prescaling:primes", "primes", self.prime_left, self.d, separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:interest", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:detempering", "detempering", self.detempering_left, self.r)
        self.vector_list_marks("ss_mapping", "ss_selfmap", "ssgens", self.ss_gen_left, self.rL, separators=False)
        self.vector_list_marks("prescaling", "prescaling:commas", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("prescaling", "prescaling:detempering", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("prescaling", "prescaling:targets", "targets", self.target_left, self.k, separators=True)
        self.vector_list_marks("prescaling", "prescaling:held", "held", self.held_left, self.nh, separators=True)
        self.vector_list_marks("prescaling", "prescaling:interest", "interest", self.interest_left, self.mi, separators=False)
        self.v_split_bars()

