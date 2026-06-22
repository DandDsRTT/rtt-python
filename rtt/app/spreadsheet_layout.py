from __future__ import annotations

from rtt.app import service
from rtt.app.grid_tables import (
    CAPTIONED_ROWS,
    CHARTED_ROWS,
    COL_LABELED_ROWS,
    COUNTS_TILES,
    DETEMPERING_COUNTS_TILES,
    FORM_CHOOSER_ROWS,
    FRAMED_ROWS,
    OPTIMIZATION_COUNTS_TILES,
    PRESET_ROWS,
    SUPERSPACE_COUNTS_TILES,
    SUPERSPACE_TILES,
    SYMBOLED_ROWS,
    TILES,
    UNITED_ROWS,
    UNITS_TILES,
)
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BRACE_H,
    BRACKET_W,
    CHART_GAP,
    CHART_H,
    COL_W,
    COMMAPICK_GAP,
    ETPICK_GAP,
    ETPICK_W,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    GAP,
    GRIP_BAND,
    MATLABEL_H,
    MATLABEL_PAD,
    MATLABEL_W,
    MATLABEL_W_SS,
    MATLABEL_W_SSPRIMES,
    PAD,
    ROW_H,
    ROW_HANDLE_GAP,
    ROW_HANDLE_W,
    SCHEME_BTN_SQ,
    STRIP,
    SYMBOL_H,
    TITLE_MARGIN,
    TOGGLE,
    TOGGLE_INSET,
    UNIT_H,
)
from rtt.app.spreadsheet_models import RowBand
from rtt.app.spreadsheet_text import _title_w


class _LayoutMixin:
    def _declare_interval_column_tiles(self):
        interest_tiles = ()
        if self.mi_shown:
            interest_tiles += (
                ("block:vec:interest", "vectors", "interest"),
                ("block:interest", "quantities", "interest"),
                ("block:imapped", "mapping", "interest"),
                ("block:tuning:interest", "tuning", "interest"),
                ("block:just:interest", "just", "interest"),
                ("block:retune:interest", "retune", "interest"),
                ("block:urow:interest", "units", "interest"),
                ("block:prescaling:interest", "prescaling", "interest"),
                ("block:complexity:interest", "complexity", "interest"),
            )
        held_tiles = ()
        if self.nh_shown:
            held_tiles += (
                ("block:held", "quantities", "held"),
                ("block:vec:held", "vectors", "held"),
                ("block:hmapped", "mapping", "held"),
                ("block:tuning:held", "tuning", "held"),
                ("block:just:held", "just", "held"),
                ("block:retune:held", "retune", "held"),
                ("block:urow:held", "units", "held"),
                ("block:prescaling:held", "prescaling", "held"),
                ("block:complexity:held", "complexity", "held"),
            )
        self.detempering_vectors = service.generator_detempering(self.state.mapping) if self.show_detempering else ()
        self.detempering_sizes = service.interval_sizes(self.tun, self.gens, self.elements) if self.show_detempering else None
        detempering_tiles = (
            ("block:detempering", "quantities", "detempering"),
            ("block:vec:detempering", "vectors", "detempering"),
            ("block:mapped_detempering", "mapping", "detempering"),
            ("block:tuning:detempering", "tuning", "detempering"),
            ("block:just:detempering", "just", "detempering"),
            ("block:retune:detempering", "retune", "detempering"),
            ("block:prescaling:detempering", "prescaling", "detempering"),
            ("block:complexity:detempering", "complexity", "detempering"),
            ("block:urow:detempering", "units", "detempering"),
        ) if self.show_detempering else ()
        self.canon_mapped = service.mapped_intervals(self.canon_mapping, self.targets, self.elements)
        self.canon_held_mapped = service.mapped_intervals(self.canon_mapping, self.held_ratios, self.elements)
        self.canon_interest_mapped = service.mapped_intervals(self.canon_mapping, self.interest_ratios, self.elements)
        self.canon_mapped_commas = service.mapped_commas(self.canon_mapping, self.state.comma_basis)
        self.canon_mapped_detempering = (service.mapped_commas(self.canon_mapping, self.detempering_vectors)
                                         if self.show_detempering else ())
        _canon_u = [None if (self.unchanged_basis is None or self.unchanged_basis[j] is None)
                    else tuple(row[0] for row in service.mapped_commas(self.canon_mapping, (self.unchanged_basis[j],)))
                    for j in range(self.nu)]
        self.canon_unchanged_mapped = tuple(
            tuple((None if _canon_u[j] is None else _canon_u[j][i]) for j in range(self.nu))
            for i in range(self.rc))
        return interest_tiles, held_tiles, detempering_tiles

    def _declare_tiles(self, interest_tiles, held_tiles, detempering_tiles) -> None:
        projection_col_tiles = ()
        if self.show_projection:
            projection_col_tiles += (
                ("block:proj:quantities", "projection", "quantities"),
                ("block:proj:units", "projection", "units"),
            )
            if self.show_detempering:
                projection_col_tiles += (("block:proj:detempering", "projection", "detempering"),)
            if self.targets_editable:
                projection_col_tiles += (("block:proj:targets", "projection", "targets"),)
            if self.nh_shown:
                projection_col_tiles += (("block:proj:held", "projection", "held"),)
            if self.mi_shown:
                projection_col_tiles += (("block:proj:interest", "projection", "interest"),)
            if self.show_superspace:
                projection_col_tiles += (
                    ("block:proj:ssgens", "projection", "ssgens"),
                    ("block:proj:ssprimes", "projection", "ssprimes"),
                )
        ss_projection_col_tiles = ()
        if self.show_ss_projection:
            ss_projection_col_tiles += (
                ("block:ssproj:ssgens", "ss_projection", "ssgens"),
                ("block:ssproj:primes", "ss_projection", "primes"),
            )
            if self.show_unchanged:
                ss_projection_col_tiles += (("block:ssproj:commas", "ss_projection", "commas"),)
            if self.show_detempering:
                ss_projection_col_tiles += (("block:ssproj:detempering", "ss_projection", "detempering"),)
            if self.targets_editable:
                ss_projection_col_tiles += (("block:ssproj:targets", "ss_projection", "targets"),)
            if self.nh_shown:
                ss_projection_col_tiles += (("block:ssproj:held", "ss_projection", "held"),)
            if self.mi_shown:
                ss_projection_col_tiles += (("block:ssproj:interest", "ss_projection", "interest"),)
        canon_col_tiles = ()
        if self.show_canon:
            canon_col_tiles += (("block:canon_comma", "canon", "commas"),)
            if self.show_detempering:
                canon_col_tiles += (("block:canon_detempering", "canon", "detempering"),)
            if self.targets_editable:
                canon_col_tiles += (("block:canon_mapped", "canon", "targets"),)
            if self.nh_shown:
                canon_col_tiles += (("block:canon_held", "canon", "held"),)
            if self.mi_shown:
                canon_col_tiles += (("block:canon_interest", "canon", "interest"),)
        self.tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
                 + SUPERSPACE_COUNTS_TILES
                 + TILES + UNITS_TILES + SUPERSPACE_TILES
                 + interest_tiles + held_tiles + detempering_tiles + projection_col_tiles
                 + ss_projection_col_tiles + canon_col_tiles)
        self.declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in self.tiles}
        if service.is_all_interval(self.tuning_scheme):
            self.declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                               ("tuning", "targets"), ("just", "targets"), ("retune", "targets"),
                               ("ss_vectors", "targets"), ("ss_mapping", "targets")}
        if not self.show_identity_objects:
            self.declared_tiles -= {("vectors", "primes"), ("mapping", "gens"),
                                    ("mapping", "detempering"), ("canon", "canongens"),
                                    ("ss_vectors", "ssprimes"), ("ss_mapping", "ssgens")}
        if not self.nh_shown:
            self.declared_tiles -= {("ss_vectors", "held"), ("ss_mapping", "held")}
        if not self.mi_shown:
            self.declared_tiles -= {("ss_vectors", "interest"), ("ss_mapping", "interest")}

    def _define_col_bands(self, show_interval_ratios, show_domain_units, show_temp,
                          show_tuning, show_interest, label_w):
        domain_title = ("domain basis\nelements"
                        if service.domain_has_nonprimes(self.elements)
                        else "domain\nprimes")
        self.col_header = {"quantities": "interval ratios", "units": "units",
                      "canongens": "canonical\ngenerators", "gens": "generators",
                      "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                      "primes": domain_title, "detempering": "generator\ndetempering",
                      "commas": "commas",
                      "held": "held\nintervals", "targets": "target\nintervals",
                      "interest": "other intervals\nof interest"}
        if self.show_unchanged:
            self.col_header["commas"] = "unrotated\nvector list"
        self.matlabel_primes_w = ((MATLABEL_W_SS if self.show_superspace else MATLABEL_W)
                                  if (self.show_header_symbols and show_temp) else 0)
        self.matlabel_ssprimes_w = MATLABEL_W_SSPRIMES if (self.show_header_symbols and self.show_superspace) else 0
        _label_row_present = {"mapping": show_temp, "vectors": self.show_interval_vectors,
                              "canon": self.show_canon, "projection": self.show_projection,
                              "prescaling": self._complexity_shown, "ss_mapping": self.show_superspace,
                              "ss_vectors": self.show_superspace, "ss_projection": self.show_ss_projection}
        self.matlabel_other_w = {}
        if self.show_header_symbols:
            for (rk, ck) in self.row_labels:
                if ck not in ("primes", "ssprimes") and _label_row_present.get(rk) and (rk, ck) in self.declared_tiles:
                    self.matlabel_other_w[ck] = MATLABEL_W
        self.row_handle_w = (ROW_HANDLE_W + ROW_HANDLE_GAP) if (
            self.settings.get("drag_to_combine") and show_temp and self.r > 1) else 0
        self.etpick_w = (ETPICK_W + ETPICK_GAP) if (self.show_presets and show_temp) else 0
        self.size_factor = service.complexity_size_factor(self.tuning_scheme)
        self.size_rows = 1 if self.size_factor else 0
        self.prescale_rows = self.dL if self.show_superspace else self.d
        self.all_interval_simplicity_weight = self.all_interval and (
            bool(self.size_factor) or self.prescaler_is_matrix)
        col_bands = (
            ("quantities", COL_W, show_interval_ratios, True),
            ("units", COL_W, show_domain_units, True),
            ("canongens", 2 * BRACKET_W + self.rc * COL_W + 2 * self.matlabel_gutter_w("canongens"), self.show_canon, True),
            ("gens", 2 * BRACKET_W + self.r * COL_W + 2 * self.matlabel_gutter_w("gens"), show_temp, True),
            ("ssgens", 2 * BRACKET_W + self.rL * COL_W, self.show_superspace, True),
            ("ssprimes", 2 * BRACKET_W + self.dL * COL_W + 2 * self.matlabel_ssprimes_w, self.show_superspace, True),
            ("primes", 2 * BRACKET_W + self.d_shown * COL_W + 2 * self.outer_gutter_w("primes"), show_temp, True),
            ("detempering", 2 * BRACKET_W + self.r * COL_W, self.show_detempering, True),
            ("commas", self._commas_band_w(self.nc_shown), show_temp, True),
            ("held", 2 * BRACKET_W + self.nh_shown * COL_W, self.show_optimization, True),
            ("targets", 2 * BRACKET_W + self.k_shown * COL_W, show_tuning and self.targets_in_use, True),
            ("interest", 2 * BRACKET_W + self.mi_shown * COL_W, show_interest, True),
        )
        self.node_x = label_w + GAP
        self.node_edge = self.node_x + TOGGLE
        content_x0 = self.node_x + TOGGLE + GAP
        return col_bands, content_x0

    def _define_row_bands(self, show_counts, show_interval_ratios, show_domain_units,
                          show_temp, show_tuning):
        row_bands = (
            ("counts", ROW_H, show_counts, True, "counts"),
            ("quantities", ROW_H, show_interval_ratios, True, "interval\nratios"),
            ("units", ROW_H, show_domain_units, True, "units"),
            ("scaling_factors", ROW_H, self.show_unchanged, True, "scaling factors"),
            ("vectors", self.d * ROW_H, self.show_interval_vectors, True, "interval vectors"),
            ("canon", self.rc * ROW_H, self.show_canon, True, "canonical mapping"),
            ("mapping", self.r_shown * ROW_H, show_temp, True, "mapping"),
            ("ss_vectors", self.dL * ROW_H, self.show_superspace, True, "superspace\ninterval vectors"),
            ("ss_mapping", self.rL * ROW_H, self.show_superspace, True, "superspace\nmapping"),
            ("ss_projection", self.dL * ROW_H, self.show_ss_projection, True, "superspace\nprojection"),
            ("projection", self.d * ROW_H, self.show_projection, True, "projection"),
            ("tuning", ROW_H, show_tuning, True, "tuning"),
            ("just", ROW_H, show_tuning, True, "just tuning"),
            ("retune", ROW_H, show_tuning, True, "retuning"),
            ("prescaling", (self.prescale_rows + self.size_rows) * ROW_H, self._complexity_shown, True, "complexity prescaling"),
            ("complexity", ROW_H, self._complexity_shown, True, "complexity"),
            ("weight", ROW_H, self.show_weighting, True, "weight"),
            ("damage", ROW_H, show_tuning, True, "damage"),
        )
        self.present_caption_rows = frozenset(
            key for key, _h, present, _c, _l in row_bands if present and key in CAPTIONED_ROWS)
        return row_bands

    def _layout_columns(self, col_bands, content_x0) -> None:
        self.col_x, self.col_w, self.content_w, self.col_collapsible, self.open_col_w = {}, {}, {}, {}, {}
        x = content_x0
        first_present = True
        prev_title_oh = None
        for key, natural, present, collapsible in col_bands:
            if not present:
                continue
            collapsed_col = f"col:{key}" in self.collapsed
            hug_w = max(natural, self._caption_floor(key), self._control_floor(key), self._symbol_floor(key))
            if first_present:
                hug_w = max(hug_w, _title_w(self.col_header[key]) - 2 * PAD)
                first_present = False
            self.open_col_w[key] = hug_w
            if collapsed_col:
                self.col_w[key] = self.content_w[key] = min(hug_w, _title_w(self.col_header[key]))
            else:
                self.content_w[key] = natural
                self.col_w[key] = hug_w
            self.col_collapsible[key] = collapsible
            half_oh = _title_w(self.col_header[key]) / 2 - self.col_w[key] / 2
            if prev_title_oh is not None:
                x += max(GAP, TITLE_MARGIN + prev_title_oh + half_oh)
            self.col_x[key] = x
            x += self.col_w[key]
            prev_title_oh = half_oh
        self.total_w = x + GAP

        self.content_x = {key: self.col_x[key] + (self.col_w[key] - self.content_w[key]) / 2 for key in self.col_x}

        self.primes_x = self.content_x.get("primes")
        self.commas_x = self.content_x.get("commas")
        self.targets_x = self.content_x.get("targets")
        self.interest_x = self.content_x.get("interest")
        self.held_x = self.content_x.get("held")
        self.detempering_x = self.content_x.get("detempering")
        self.canongens_x = self.content_x.get("canongens")
        self.ssgens_x = self.content_x.get("ssgens")
        self.ssprimes_x = self.content_x.get("ssprimes")

    def _init_row_geometry(self, header_h):
        self.header_y = 0
        self.col_node_y = header_h + (GAP - TOGGLE) / 2
        self.branch_top_y = self.col_node_y + TOGGLE
        rows_top_y = self.branch_top_y + GAP + GRIP_BAND
        self.FAN = (GAP - PAD) / 2

        self.rows: dict[str, RowBand] = {}
        self.row_cpick = {}
        return rows_top_y

    def _layout_rows(self, row_bands, tile_extra, rows_top_y, show_charts) -> None:
        y = rows_top_y
        for key, natural, present, collapsible, label in row_bands:
            if not present:
                continue
            folded = f"row:{key}" in self.collapsed
            framed = key in FRAMED_ROWS and not folded
            has_matlabel = (self.show_header_symbols and key in COL_LABELED_ROWS and not folded)
            head_default = TOGGLE + 2 * TOGGLE_INSET - PAD
            int_handle = (key == "vectors" and not folded and self.settings.get("drag_to_combine")
                          and ((self.nc >= 2 and self.col_open("commas"))
                               or (self.k >= 2 and not self.all_interval and self.col_open("targets"))
                               or (self.nh >= 2 and self.col_open("held"))
                               or (self.mi >= 2 and self.col_open("interest"))))
            handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if int_handle else 0
            base_head = 0 if folded else max(head_default, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else head_default)
            head = base_head + handle_band
            top_frame = (FRAME_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
            bot_frame = (BRACE_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
            charted = show_charts and key in CHARTED_ROWS and not folded and natural == ROW_H
            chart_band = (CHART_H + CHART_GAP) if charted else 0
            cap = self.caption_band(key, folded)
            sym = SYMBOL_H if ((self.show_symbols or self.show_equiv) and key in SYMBOLED_ROWS and not folded) else 0
            uni = UNIT_H if (self.show_units and key in UNITED_ROWS and not folded) else 0
            pre = self.preset_band_h(key) if ((self.show_presets and key in PRESET_ROWS
                                             or self.settings["all_interval"] and key == "vectors")
                                            and not folded) else 0
            schemebtn = (self.control_region_band_h(SCHEME_BTN_SQ)
                         if (key == "projection" and self.settings["projection"] and not self.show_presets and not folded) else 0)
            formctrl = (self.formchooser_band_h(key)
                        if (self.show_form_controls and not self.show_presets
                            and key in FORM_CHOOSER_ROWS and not folded) else 0)
            cpick = (COMMAPICK_GAP + ROW_H) if (key == "vectors" and self.show_presets
                                               and self.col_open("commas")
                                               and (self.nc > 0 or self.pending is not None) and not folded) else 0
            ptext = self.ptext_band(key, folded)
            if sym:   sym += BAND_GAP
            if cap:   cap += BAND_GAP
            if uni:   uni += BAND_GAP
            if ptext: ptext += BAND_GAP
            row_h = STRIP if folded else natural
            chart_top = (y + head + top_frame) if charted else None
            int_handle_top = (y + (handle_band - ROW_HANDLE_W) // 2) if int_handle else None
            matlabel_top = (y + handle_band + (base_head - MATLABEL_H) // 2) if has_matlabel else None
            self.row_cpick[key] = cpick
            tile_h = head + top_frame + chart_band + row_h + bot_frame + cpick + sym + cap + uni + pre + ptext + formctrl + schemebtn
            tile_h += tile_extra.get(key, 0)
            self.rows[key] = RowBand(
                y=y + head + top_frame + chart_band,
                h=row_h,
                label=label,
                collapsible=collapsible,
                tile_h=tile_h,
                tile_top=y,
                frame=bot_frame,
                sym=sym,
                cap=cap,
                units=uni,
                ptext=ptext,
                pre=pre,
                schemebtn=schemebtn,
                nsub=round(natural / ROW_H),
                chart_top=chart_top,
                int_handle_top=int_handle_top,
                matlabel_top=matlabel_top,
            )
            y += tile_h + GAP
        self.total_h = y

        self.fanout_y = self.branch_top_y + self.FAN

    def _init_group_geometry(self) -> None:
        self.group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                      "interest": "interest", "held": "held", "detempering": "detempering",
                      "canongens": "cangen", "ssgens": "ssgen", "ssprimes": "ssprime"}
        self.group_left = {"gens": self.gen_left, "primes": self.prime_left, "commas": self.comma_left, "targets": self.target_left,
                      "interest": self.interest_left, "held": self.held_left, "detempering": self.detempering_left,
                      "canongens": self.canongen_left, "ssgens": self.ss_gen_left, "ssprimes": self.ss_prime_left}
        self.group_n = {"gens": self.r, "primes": self.d_shown, "commas": self.nv_shown,
                   "targets": self.k_shown,
                   "interest": self.mi_shown, "held": self.nh_shown, "detempering": self.r,
                   "canongens": self.rc, "ssgens": self.rL, "ssprimes": self.dL}
        self.group_ratio = {
            "primes": lambda i: service.element_ratio(self.elements[i]),
            "commas": lambda i: self.comma_ratios[i] if i < self.nc else self.unchanged_ratios[i - self.nc],
            "targets": lambda i: self.targets[i],
            "interest": lambda i: self.interest_ratios[i],
            "held": lambda i: self.held_ratios[i],
            "detempering": lambda i: self.gens[i],
            "ssprimes": lambda i: service.element_ratio(self.superspace_primes[i]),
        }

        self.plus_stub_x = {ckey: self.col_plus_x(ckey) for ckey in ("gens", "primes", "commas", "targets", "interest", "held")
                       if self._plus_shows(ckey)}

        self.row_plus_y = {}
        if self.tile_open("vectors", "quantities") and (self.show_nonstandard_domain or self.standard_domain):
            self.row_plus_y["vectors"] = self.vec_top(self.d_shown) + ROW_H / 2
        if self.tile_open("mapping", "quantities") and self.state.n > 0:
            self.row_plus_y["mapping"] = self.map_top(self.r_shown) + ROW_H / 2
