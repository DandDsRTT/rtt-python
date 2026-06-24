from __future__ import annotations

from rtt.app import service
from rtt.app.grid_tables import (
    BANDS,
    COUNTS_TILES,
    DETEMPERING_COUNTS_TILES,
    OPTIMIZATION_COUNTS_TILES,
    SUPERSPACE_COUNTS_TILES,
    SUPERSPACE_TILES,
    TILES,
    UNITS_TILES,
)
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BAND_GAP,
    BOX_INNER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    BRACE_H,
    BRACKET_W,
    CAPTION_LINE,
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
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_T,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    OPTION_BOX_PX,
    PAD,
    PRESET_H,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    ROW_HANDLE_GAP,
    ROW_HANDLE_W,
    SCHEME_BTN_SQ,
    STRIP,
    TITLE_MARGIN,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_models import RowBand
from rtt.app.spreadsheet_text import _title_w, _wrap_lines


class _LayoutMixin:
    def _declare_interval_column_tiles(self):
        _r = self.resolved
        interest_tiles = ()
        if _r.dims.mi_shown:
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
        if _r.dims.nh_shown:
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
        ) if _r.flags.detempering else ()
        return interest_tiles, held_tiles, detempering_tiles

    def _declare_tiles(self, interest_tiles, held_tiles, detempering_tiles) -> None:
        self.tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
                 + SUPERSPACE_COUNTS_TILES
                 + TILES + UNITS_TILES + SUPERSPACE_TILES
                 + interest_tiles + held_tiles + detempering_tiles + self._projection_col_tiles()
                 + self._ss_projection_col_tiles() + self._canon_col_tiles())
        self.declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in self.tiles}
        self._prune_declared_tiles()

    def _projection_col_tiles(self):
        _r = self.resolved
        if not _r.flags.projection:
            return ()
        tiles = (
            ("block:proj:quantities", "projection", "quantities"),
            ("block:proj:units", "projection", "units"),
        )
        if _r.flags.detempering:
            tiles += (("block:proj:detempering", "projection", "detempering"),)
        if _r.scalars.targets_editable:
            tiles += (("block:proj:targets", "projection", "targets"),)
        if _r.dims.nh_shown:
            tiles += (("block:proj:held", "projection", "held"),)
        if _r.dims.mi_shown:
            tiles += (("block:proj:interest", "projection", "interest"),)
        if _r.flags.superspace:
            tiles += (
                ("block:proj:ssgens", "projection", "ssgens"),
                ("block:proj:ssprimes", "projection", "ssprimes"),
            )
        return tiles

    def _ss_projection_col_tiles(self):
        _r = self.resolved
        if not _r.flags.ss_projection:
            return ()
        tiles = (
            ("block:ssproj:ssgens", "ss_projection", "ssgens"),
            ("block:ssproj:primes", "ss_projection", "primes"),
        )
        if _r.unchanged.shown:
            tiles += (("block:ssproj:commas", "ss_projection", "commas"),)
        if _r.flags.detempering:
            tiles += (("block:ssproj:detempering", "ss_projection", "detempering"),)
        if _r.scalars.targets_editable:
            tiles += (("block:ssproj:targets", "ss_projection", "targets"),)
        if _r.dims.nh_shown:
            tiles += (("block:ssproj:held", "ss_projection", "held"),)
        if _r.dims.mi_shown:
            tiles += (("block:ssproj:interest", "ss_projection", "interest"),)
        return tiles

    def _canon_col_tiles(self):
        _r = self.resolved
        if not _r.flags.canon:
            return ()
        tiles = (("block:canon_comma", "canon", "commas"),)
        if _r.flags.detempering:
            tiles += (("block:canon_detempering", "canon", "detempering"),)
        if _r.scalars.targets_editable:
            tiles += (("block:canon_mapped", "canon", "targets"),)
        if _r.dims.nh_shown:
            tiles += (("block:canon_held", "canon", "held"),)
        if _r.dims.mi_shown:
            tiles += (("block:canon_interest", "canon", "interest"),)
        return tiles

    def _prune_declared_tiles(self) -> None:
        _r = self.resolved
        if service.is_all_interval(self.tuning_scheme):
            self.declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                               ("tuning", "targets"), ("just", "targets"), ("retune", "targets"),
                               ("ss_vectors", "targets"), ("ss_mapping", "targets")}
        if not _r.flags.identity_objects:
            self.declared_tiles -= {("vectors", "primes"), ("mapping", "gens"),
                                    ("mapping", "detempering"), ("canon", "canongens"),
                                    ("ss_vectors", "ssprimes"), ("ss_mapping", "ssgens")}
        if not _r.dims.nh_shown:
            self.declared_tiles -= {("ss_vectors", "held"), ("ss_mapping", "held")}
        if not _r.dims.mi_shown:
            self.declared_tiles -= {("ss_vectors", "interest"), ("ss_mapping", "interest")}

    def _resolve_col_headers(self) -> None:
        _r = self.resolved
        domain_title = ("domain basis\nelements"
                        if service.domain_has_nonprimes(_r.dims.elements)
                        else "domain\nprimes")
        self.col_header = {"quantities": "interval ratios", "units": "units",
                      "canongens": "canonical\ngenerators", "gens": "generators",
                      "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                      "primes": domain_title, "detempering": "generator\ndetempering",
                      "commas": "commas",
                      "held": "held\nintervals", "targets": "target\nintervals",
                      "interest": "other intervals\nof interest"}
        if _r.unchanged.shown:
            self.col_header["commas"] = "unrotated\nvector list"

    def _define_col_bands(self, label_w):
        _r = self.resolved
        self._resolve_col_headers()
        self.matlabel_primes_w = ((MATLABEL_W_SS if _r.flags.superspace else MATLABEL_W)
                                  if (_r.flags.header_symbols and _r.flags.temp) else 0)
        self.matlabel_ssprimes_w = MATLABEL_W_SSPRIMES if (_r.flags.header_symbols and _r.flags.superspace) else 0
        _label_row_present = {"mapping": _r.flags.temp, "vectors": _r.flags.interval_vectors,
                              "canon": _r.flags.canon, "projection": _r.flags.projection,
                              "prescaling": _r.flags.prescaling_shown, "ss_mapping": _r.flags.superspace,
                              "ss_vectors": _r.flags.superspace, "ss_projection": _r.flags.ss_projection}
        self.matlabel_other_w = {}
        if _r.flags.header_symbols:
            for (rk, ck) in _r.labels.row_labels:
                if ck not in ("primes", "ssprimes") and _label_row_present.get(rk) and (rk, ck) in self.declared_tiles:
                    self.matlabel_other_w[ck] = MATLABEL_W
        self.row_handle_w = (ROW_HANDLE_W + ROW_HANDLE_GAP) if (
            self.settings.get("drag_to_combine") and _r.flags.temp and _r.dims.r > 1) else 0
        self.etpick_w = (ETPICK_W + ETPICK_GAP) if (_r.flags.presets and _r.flags.temp) else 0
        self.size_factor = service.complexity_size_factor(self.tuning_scheme)
        self.size_rows = 1 if self.size_factor else 0
        self.prescale_rows = _r.dims.dL if _r.flags.superspace else _r.dims.d
        self.all_interval_simplicity_weight = _r.scalars.all_interval and (
            bool(self.size_factor) or _r.scalars.prescaler_is_matrix)
        col_bands = (
            ("quantities", COL_W, _r.flags.interval_ratios, True),
            ("units", COL_W, _r.flags.domain_units, True),
            ("canongens", 2 * BRACKET_W + _r.dims.rc * COL_W + 2 * self.matlabel_gutter_w("canongens"), _r.flags.canon, True),
            ("gens", 2 * BRACKET_W + _r.dims.r * COL_W + 2 * self.matlabel_gutter_w("gens"), _r.flags.temp, True),
            ("ssgens", 2 * BRACKET_W + _r.dims.rL * COL_W, _r.flags.superspace, True),
            ("ssprimes", 2 * BRACKET_W + _r.dims.dL * COL_W + 2 * self.matlabel_ssprimes_w, _r.flags.superspace, True),
            ("primes", 2 * BRACKET_W + _r.dims.d_shown * COL_W + 2 * self.outer_gutter_w("primes"), _r.flags.temp, True),
            ("detempering", 2 * BRACKET_W + _r.dims.r * COL_W, _r.flags.detempering, True),
            ("commas", self._commas_band_w(_r.dims.nc_shown), _r.flags.temp, True),
            ("held", 2 * BRACKET_W + _r.dims.nh_shown * COL_W, _r.flags.optimization, True),
            ("targets", 2 * BRACKET_W + _r.dims.k_shown * COL_W, _r.flags.tuning and self.targets_in_use, True),
            ("interest", 2 * BRACKET_W + _r.dims.mi_shown * COL_W, _r.flags.interest, True),
        )
        self.node_x = label_w + GAP
        self.node_edge = self.node_x + TOGGLE
        content_x0 = self.node_x + TOGGLE + GAP
        return col_bands, content_x0

    def _define_row_bands(self):
        _r = self.resolved
        row_bands = (
            ("counts", ROW_H, _r.flags.counts, True, "counts"),
            ("quantities", ROW_H, _r.flags.interval_ratios, True, "interval\nratios"),
            ("units", ROW_H, _r.flags.domain_units, True, "units"),
            ("scaling_factors", ROW_H, _r.unchanged.shown, True, "scaling factors"),
            ("vectors", _r.dims.d * ROW_H, _r.flags.interval_vectors, True, "interval vectors"),
            ("canon", _r.dims.rc * ROW_H, _r.flags.canon, True, "canonical mapping"),
            ("mapping", _r.dims.r_shown * ROW_H, _r.flags.temp, True, "mapping"),
            ("ss_vectors", _r.dims.dL * ROW_H, _r.flags.superspace, True, "superspace\ninterval vectors"),
            ("ss_mapping", _r.dims.rL * ROW_H, _r.flags.superspace, True, "superspace\nmapping"),
            ("ss_projection", _r.dims.dL * ROW_H, _r.flags.ss_projection, True, "superspace\nprojection"),
            ("projection", _r.dims.d * ROW_H, _r.flags.projection, True, "projection"),
            ("tuning", ROW_H, _r.flags.tuning, True, "tuning"),
            ("just", ROW_H, _r.flags.tuning, True, "just tuning"),
            ("retune", ROW_H, _r.flags.tuning, True, "retuning"),
            ("prescaling", (self.prescale_rows + self.size_rows) * ROW_H, _r.flags.prescaling_shown, True, "complexity prescaling"),
            ("complexity", ROW_H, _r.flags.complexity_shown, True, "complexity"),
            ("weight", ROW_H, _r.flags.weighting, True, "weight"),
            ("damage", ROW_H, _r.flags.tuning, True, "damage"),
        )
        self.present_caption_rows = frozenset(
            key for key, _h, present, _c, _l in row_bands if present and key in BANDS["caption"].rows)
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

    def _layout_rows(self, row_bands, tile_extra, rows_top_y) -> None:
        show_charts = self.resolved.flags.charts
        y = rows_top_y
        for key, natural, present, collapsible, label in row_bands:
            if not present:
                continue
            band = self._compute_row_band(key, natural, collapsible, label, tile_extra, show_charts, y)
            self.rows[key] = band
            y += band.tile_h + GAP
        self.total_h = y

        self.fanout_y = self.branch_top_y + self.FAN

    def _row_int_handle(self, key, folded):
        _r = self.resolved
        return (key == "vectors" and not folded and self.settings.get("drag_to_combine")
                and ((_r.dims.nc >= 2 and self.col_open("commas"))
                     or (_r.dims.k >= 2 and not _r.scalars.all_interval and self.col_open("targets"))
                     or (_r.dims.nh >= 2 and self.col_open("held"))
                     or (_r.dims.mi >= 2 and self.col_open("interest"))))

    def _compute_row_band(self, key, natural, collapsible, label, tile_extra, show_charts, y) -> RowBand:
        _r = self.resolved
        folded = f"row:{key}" in self.collapsed
        framed = key in BANDS["frame"].rows and not folded
        has_matlabel = (_r.flags.header_symbols and key in BANDS["col_label"].rows and not folded)
        head_default = TOGGLE + 2 * TOGGLE_INSET - PAD
        int_handle = self._row_int_handle(key, folded)
        handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if int_handle else 0
        base_head = 0 if folded else max(head_default, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else head_default)
        head = base_head + handle_band
        top_frame = (FRAME_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
        bot_frame = (BRACE_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
        charted = show_charts and key in BANDS["chart"].rows and not folded and natural == ROW_H
        chart_band = (CHART_H + CHART_GAP) if charted else 0
        cap = self.caption_band(key, folded)
        sym = BANDS["symbol"].height if ((_r.flags.symbols or _r.flags.equiv)
                                         and key in BANDS["symbol"].rows and not folded) else 0
        uni = BANDS["units"].height if (_r.flags.units and key in BANDS["units"].rows and not folded) else 0
        pre = self.preset_band_h(key) if (((_r.flags.presets and key in BANDS["preset"].rows)
                                         or (self.settings["all_interval"] and key == "vectors"))
                                        and not folded) else 0
        schemebtn = (self.control_region_band_h(SCHEME_BTN_SQ)
                     if (key == "projection" and self.settings["projection"] and not _r.flags.presets and not folded) else 0)
        formctrl = (self.formchooser_band_h(key)
                    if (_r.flags.form_controls and not _r.flags.presets
                        and key in BANDS["form_chooser"].rows and not folded) else 0)
        cpick = (COMMAPICK_GAP + ROW_H) if (key == "vectors" and _r.flags.presets
                                           and self.col_open("commas")
                                           and (_r.dims.nc > 0 or _r.commas.pending is not None) and not folded) else 0
        ptext = self.ptext_band(key, folded)
        sym += BAND_GAP if sym else 0
        cap += BAND_GAP if cap else 0
        uni += BAND_GAP if uni else 0
        ptext += BAND_GAP if ptext else 0
        row_h = STRIP if folded else natural
        chart_top = (y + head + top_frame) if charted else None
        int_handle_top = (y + (handle_band - ROW_HANDLE_W) // 2) if int_handle else None
        matlabel_top = (y + handle_band + (base_head - MATLABEL_H) // 2) if has_matlabel else None
        self.row_cpick[key] = cpick
        tile_h = (head + top_frame + chart_band + row_h + bot_frame + cpick + sym + cap + uni
                  + pre + ptext + formctrl + schemebtn + tile_extra.get(key, 0))
        return RowBand(
            y=y + head + top_frame + chart_band, h=row_h, label=label, collapsible=collapsible,
            tile_h=tile_h, tile_top=y, frame=bot_frame, sym=sym, cap=cap, units=uni, ptext=ptext,
            pre=pre, schemebtn=schemebtn, nsub=round(natural / ROW_H),
            chart_top=chart_top, int_handle_top=int_handle_top, matlabel_top=matlabel_top)

    def _init_group_geometry(self) -> None:
        _r = self.resolved
        self.group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                      "interest": "interest", "held": "held", "detempering": "detempering",
                      "canongens": "cangen", "ssgens": "ssgen", "ssprimes": "ssprime"}
        self.group_left = {"gens": self.gen_left, "primes": self.prime_left, "commas": self.comma_left, "targets": self.target_left,
                      "interest": self.interest_left, "held": self.held_left, "detempering": self.detempering_left,
                      "canongens": self.canongen_left, "ssgens": self.ss_gen_left, "ssprimes": self.ss_prime_left}
        self.group_n = {"gens": _r.dims.r, "primes": _r.dims.d_shown, "commas": _r.dims.nv_shown,
                   "targets": _r.dims.k_shown,
                   "interest": _r.dims.mi_shown, "held": _r.dims.nh_shown, "detempering": _r.dims.r,
                   "canongens": _r.dims.rc, "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}
        self.group_ratio = {
            "primes": lambda i: service.element_ratio(_r.dims.elements[i]),
            "commas": lambda i: _r.commas.ratios[i] if i < _r.dims.nc else _r.unchanged.ratios[i - _r.dims.nc],
            "targets": lambda i: _r.targets.ratios[i],
            "interest": lambda i: _r.interest.ratios[i],
            "held": lambda i: _r.held.ratios[i],
            "detempering": lambda i: _r.scalars.gens[i],
            "ssprimes": lambda i: service.element_ratio(_r.dims.superspace_primes[i]),
        }

        self.plus_stub_x = {ckey: self.col_plus_x(ckey) for ckey in ("gens", "primes", "commas", "targets", "interest", "held")
                       if self._plus_shows(ckey)}

        self.row_plus_y = {}
        if self.tile_open("vectors", "quantities") and (_r.flags.nonstandard_domain or _r.scalars.standard_domain):
            self.row_plus_y["vectors"] = self.vec_top(_r.dims.d_shown) + ROW_H / 2
        if self.tile_open("mapping", "quantities") and self.state.n > 0:
            self.row_plus_y["mapping"] = self.map_top(_r.dims.r_shown) + ROW_H / 2

    def _resolve_tile_extras(self):
        _r = self.resolved
        self.gtm_chart = (_r.flags.ranges and _r.flags.tuning and "row:tuning" not in self.collapsed
                     and self.col_open("gens") and "tile:tuning:gens" not in self.collapsed)
        self.gtm_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if self.gtm_chart else 0
        self.lbox_ctrl = _r.flags.lbox_show and self.col_open("ssprimes" if _r.flags.superspace else "primes") and not _r.flags.presets
        self.lbox_extra = (RANGE_GAP + self.control_region_band_h(OPTION_BOX_PX + CAPTION_LINE)) if self.lbox_ctrl else 0
        self.cbox_ctrl = _r.flags.cbox_show and self.col_open("targets")
        self.cbox_extra = (RANGE_GAP + self.control_region_band_h(ROW_H + _r.scalars.ctrl_symbol_h + 3 * CAPTION_LINE)) if self.cbox_ctrl else 0
        self.opt_ctrl = (_r.flags.optimization and "row:damage" not in self.collapsed
                    and self.col_open("targets") and "tile:damage:targets" not in self.collapsed)
        self.mean_damage_caption = "retuning magnitude" if _r.scalars.all_interval else "power mean"
        if self.tuning_optimized:
            self.mean_damage_caption = f"minimized {self.mean_damage_caption}"
        self.opt_cap_lines = _wrap_lines(self.mean_damage_caption, OPT_MEAN_DAMAGE_W) if self.opt_ctrl else 1
        self.opt_extra = ((RANGE_GAP + OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + ROW_H + _r.scalars.ctrl_symbol_h
                      + self.opt_cap_lines * CAPTION_LINE + OPT_PAD_B) if self.opt_ctrl else 0)
        self.show_approach = (service.domain_has_nonprimes(_r.dims.elements)
                          and "row:damage" not in self.collapsed and self.col_open("targets")
                          and "tile:damage:targets" not in self.collapsed)
        self.approach_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if self.show_approach else 0
        self.slope_ctrl = (_r.flags.weighting
                      and "row:weight" not in self.collapsed
                      and self.col_open("targets") and "tile:weight:targets" not in self.collapsed)
        self.slope_locked = self.slope_ctrl and (service.is_all_interval(self.tuning_scheme)
                                                 or _r.scalars.custom_weights_active)
        self.slope_extra = (RANGE_GAP + self.control_region_band_h(PRESET_H + CAPTION_LINE)) if self.slope_ctrl else 0
        return {
            "tuning": self.gtm_extra,
            "prescaling": self.lbox_extra,
            "complexity": self.cbox_extra,
            "weight": self.slope_extra,
            "damage": self.opt_extra + self.approach_extra,
        }

    def _resolve_ptext_strings(self, generator_tuning, target_override) -> None:
        _r = self.resolved
        self.ptext_strings = (service.plain_text_values(self.state, self.tuning_scheme, self.target_spec,
                                                   held=_r.held.vectors, interest=_r.interest.vectors,
                                                   generator_tuning=generator_tuning,
                                                   target_override=target_override,
                                                   nonprime_approach=self.nonprime_approach,
                                                   superspace=_r.flags.superspace,
                                                   superspace_generator_override=(
                                                       self.superspace_generator_tuning
                                                       if _r.flags.superspace_generators else None),
                                                   consolidate_v=_r.unchanged.shown,
                                                   held_basis_ratios=self.held_basis_ratios,
                                                   decimals=_r.flags.decimals,
                                                   custom_prescaler=self.custom_prescaler,
                                                   derived=service.DerivedQuantities(
                                                       targets=_r.targets.ratios, tun=_r.tuning.tun,
                                                       target_weights=_r.tuning.target_weights,
                                                       target_sizes=_r.targets.sizes,
                                                       comma_sizes=_r.commas.sizes,
                                                       superspace_tun=(self.superspace_tun()
                                                                       if _r.flags.superspace else None)))
                         if _r.flags.ptext else {})
        if not _r.flags.ebk:
            self.ptext_strings = {k: service.ebk_to_simple_matrix(v) for k, v in self.ptext_strings.items()}
