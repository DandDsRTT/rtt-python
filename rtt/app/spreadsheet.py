from __future__ import annotations

from dataclasses import replace

from rtt.app import ids, presets, service
from rtt.app.grid_tables import (
    _FACTOR_GROUP,
    ALL_INTERVAL_CAPTIONS,
    ALL_INTERVAL_EQUIVALENCES,
    ALL_INTERVAL_MNEMONICS,
    ALL_INTERVAL_SYMBOLS,
    BLANKED_NUMBER_KINDS,
    CAPTIONED_ROWS,
    CAPTIONS,
    CELL_FACTORS,
    CHARTED_ROWS,
    COL_LABEL_LETTERS,
    COL_LABELED_ROWS,
    COUNTS,
    COUNTS_TILES,
    DETEMPERING_COUNTS,
    DETEMPERING_COUNTS_TILES,
    EDITABLE_PTEXT,
    EDITABLE_PTEXT_ROWS,
    EQUIVALENCES,
    FORM_CHOOSER_ROWS,
    FORM_CHOOSERS,
    FORM_EQUIVALENCES,
    FORM_SUBSCRIPT_GENS,
    FORM_SUBSCRIPT_ROWS,
    FRAMED_ROWS,
    GRIDDED_KINDS,
    MNEMONICS,
    NORM_SUB_CLOSE,
    NORM_SUB_OPEN,
    OPTIMIZATION_COUNTS,
    OPTIMIZATION_COUNTS_TILES,
    PRESCALER_LETTER,
    PRESET_COPIES,
    PRESET_ROWS,
    PRESETS,
    RINGABLE_KINDS,
    ROW_LABEL_LETTERS,
    SPINE_COLUMN_GROUP,
    SPINE_COLUMNS,
    SPINE_ROW_GROUP,
    SPINE_ROWS,
    SUB_CLOSE,
    SUB_OPEN,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    SUPERSPACE_COUNTS,
    SUPERSPACE_COUNTS_TILES,
    SUPERSPACE_REGION_COLUMNS,
    SUPERSPACE_REGION_ROWS,
    SUPERSPACE_TILES,
    SYMBOLED_ROWS,
    SYMBOLS,
    TILES,
    UNITED_ROWS,
    UNITS,
    UNITS_TILES,
    WEIGHT_EQUIVALENCE_BY_SLOPE,
)
from rtt.app.layout import Block, CellBox, Layout, Line
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BAND_GAP,
    BOX_INNER,
    BOX_OUTER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    BRACE_H,
    BRACKET_W,
    BTN,
    CAPTION_CHAR_W,
    CAPTION_FONT,
    CAPTION_LINE,
    CBOX_DROP_W,
    CBOX_NODROP_W,
    CBOX_SLOT_W,
    CBOX_W,
    CHART_GAP,
    CHART_H,
    COL_W,
    COMMAPICK_GAP,
    CTRL_LABEL_GAP,
    DASH,
    ETPICK_GAP,
    ETPICK_W,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    GAP,
    GENMAP_BRACKETS,
    GRIP_BAND,
    HEADER_H,
    KET_INSET,
    LABEL_W,
    LBOX_DIM_W,
    LINE_W,
    LIST_BRACKETS,
    MAP_BRACKETS,
    MARK_INSET,
    MATLABEL_H,
    MATLABEL_PAD,
    MATLABEL_W,
    MATLABEL_W_SS,
    MATLABEL_W_SSPRIMES,
    MAX_CAPTION_LINES,
    OPT_BOX_MIN_W,
    OPT_COL_GAP,
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_L,
    OPT_PAD_R,
    OPT_PAD_T,
    OPT_POW_CAP_W,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    OPTION_BOX_PX,
    PAD,
    PBOX_W,
    PRESET_H,
    PRESET_W,
    PTEXT_EDIT_H,
    PTEXT_H,
    PTEXT_MAX_FONT,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    ROW_HANDLE_GAP,
    ROW_HANDLE_W,
    SCHEME_BTN_SQ,
    SCHEME_CTRL_W,
    SCHEME_LABEL_W,
    SEP_W,
    STRIP,
    SYMBOL_FONT,
    SYMBOL_H,
    TARGET_PRESET_W,
    TBOX_W,
    TITLE_MARGIN,
    TOGGLE,
    TOGGLE_INSET,
    TRANSPOSE_W,
    UNIT_H,
    V_SPLIT_GAP,
    VAL_BRACKET_H,
    WASH_PAD,
)
from rtt.app.spreadsheet_geometry import _GeometryMixin
from rtt.app.spreadsheet_models import (
    RowBand,
    _MappedTile,
    _QtyList,
    _resolve_prescaler_labels,
    _resolve_show_flags,
    _VecGrid,
)
from rtt.app.spreadsheet_text import (
    _bus_span,
    _cell_content,
    _count_sym,
    _fold_glyph,
    _foldable_ids,
    _format_power,
    _log_operand,
    _math_expr,
    _min_width_for_lines,
    _power_mean,
    _prescale_math_expr,
    _pretransform_label,
    _sub,
    _subscript_coord,
    _title_w,
    _wrap_lines,
    assign_column_tokens,
    changed_cell_ids,
    pending_token,
    removed_cell_ids,
    toggle_all_collapsed,
)

__all__ = [
    "ALL_INTERVAL_CAPTIONS",
    "ALL_INTERVAL_EQUIVALENCES",
    "ALL_INTERVAL_MNEMONICS",
    "ALL_INTERVAL_SYMBOLS",
    "APPROACH_RADIO_H",
    "BAND_GAP",
    "BLANKED_NUMBER_KINDS",
    "BOX_INNER",
    "BOX_OUTER",
    "BOX_TITLE_GAP",
    "BOX_TITLE_H",
    "BRACE_H",
    "BRACKET_W",
    "BTN",
    "CAPTIONED_ROWS",
    "CAPTIONS",
    "CAPTION_CHAR_W",
    "CAPTION_FONT",
    "CAPTION_LINE",
    "CBOX_DROP_W",
    "CBOX_NODROP_W",
    "CBOX_SLOT_W",
    "CBOX_W",
    "CELL_FACTORS",
    "CHARTED_ROWS",
    "CHART_GAP",
    "CHART_H",
    "COL_LABELED_ROWS",
    "COL_LABEL_LETTERS",
    "COL_W",
    "COMMAPICK_GAP",
    "COUNTS",
    "COUNTS_TILES",
    "CTRL_LABEL_GAP",
    "DASH",
    "DETEMPERING_COUNTS",
    "DETEMPERING_COUNTS_TILES",
    "EDITABLE_PTEXT",
    "EDITABLE_PTEXT_ROWS",
    "EQUIVALENCES",
    "ETPICK_GAP",
    "ETPICK_W",
    "FORM_CHOOSERS",
    "FORM_CHOOSER_ROWS",
    "FORM_EQUIVALENCES",
    "FORM_SUBSCRIPT_GENS",
    "FORM_SUBSCRIPT_ROWS",
    "FRAMED_ROWS",
    "FRAME_GAP",
    "FRAME_H",
    "FRAME_OVERHANG",
    "GAP",
    "GENMAP_BRACKETS",
    "GRIDDED_KINDS",
    "GRIP_BAND",
    "HEADER_H",
    "KET_INSET",
    "LABEL_W",
    "LBOX_DIM_W",
    "LINE_W",
    "LIST_BRACKETS",
    "MAP_BRACKETS",
    "MARK_INSET",
    "MATLABEL_H",
    "MATLABEL_PAD",
    "MATLABEL_W",
    "MATLABEL_W_SS",
    "MATLABEL_W_SSPRIMES",
    "MAX_CAPTION_LINES",
    "MNEMONICS",
    "NORM_SUB_CLOSE",
    "NORM_SUB_OPEN",
    "OPTIMIZATION_COUNTS",
    "OPTIMIZATION_COUNTS_TILES",
    "OPTION_BOX_PX",
    "OPT_BOX_MIN_W",
    "OPT_COL_GAP",
    "OPT_MEAN_DAMAGE_W",
    "OPT_PAD_B",
    "OPT_PAD_L",
    "OPT_PAD_R",
    "OPT_PAD_T",
    "OPT_POW_CAP_W",
    "OPT_TITLE_GAP",
    "OPT_TITLE_H",
    "PAD",
    "PBOX_W",
    "PRESCALER_LETTER",
    "PRESETS",
    "PRESET_COPIES",
    "PRESET_H",
    "PRESET_ROWS",
    "PRESET_W",
    "PTEXT_EDIT_H",
    "PTEXT_H",
    "PTEXT_MAX_FONT",
    "RANGE_CHART_H",
    "RANGE_GAP",
    "RANGE_MODE_H",
    "RINGABLE_KINDS",
    "ROW_H",
    "ROW_HANDLE_GAP",
    "ROW_HANDLE_W",
    "ROW_LABEL_LETTERS",
    "SCHEME_BTN_SQ",
    "SCHEME_CTRL_W",
    "SCHEME_LABEL_W",
    "SEP_W",
    "SPINE_COLUMNS",
    "SPINE_COLUMN_GROUP",
    "SPINE_ROWS",
    "SPINE_ROW_GROUP",
    "STRIP",
    "SUBSCRIPT_C",
    "SUBSCRIPT_L",
    "SUB_CLOSE",
    "SUB_OPEN",
    "SUPERSPACE_COUNTS",
    "SUPERSPACE_COUNTS_TILES",
    "SUPERSPACE_REGION_COLUMNS",
    "SUPERSPACE_REGION_ROWS",
    "SUPERSPACE_TILES",
    "SYMBOLED_ROWS",
    "SYMBOLS",
    "SYMBOL_FONT",
    "SYMBOL_H",
    "TARGET_PRESET_W",
    "TBOX_W",
    "TILES",
    "TITLE_MARGIN",
    "TOGGLE",
    "TOGGLE_INSET",
    "TRANSPOSE_W",
    "UNITED_ROWS",
    "UNITS",
    "UNITS_TILES",
    "UNIT_H",
    "VAL_BRACKET_H",
    "V_SPLIT_GAP",
    "WASH_PAD",
    "WEIGHT_EQUIVALENCE_BY_SLOPE",
    "_GridBuilder",
    "_cell_content",
    "_log_operand",
    "_math_expr",
    "_min_width_for_lines",
    "_resolve_prescaler_labels",
    "_resolve_show_flags",
    "_sub",
    "_title_w",
    "_wrap_lines",
    "assign_column_tokens",
    "build",
    "changed_cell_ids",
    "pending_token",
    "removed_cell_ids",
    "toggle_all_collapsed",
]


class _GridBuilder(_GeometryMixin):
    def __init__(self, state, settings=None, collapsed=None,
                 tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
                 pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
                 custom_prescaler=None, custom_weights=None, tuning_optimized=False,
                 pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, held_basis_ratios=(), displayed_projection_name=None,
                 targets_in_use=True, pending_mapping_row=None, preview_remove=None,
                 mapping_form=None, comma_basis_form=None):
        self.prev_ids = prev_ids or {}
        self.mapping_form = mapping_form
        self.comma_basis_form = comma_basis_form
        self.preview_remove = preview_remove
        self.ghost_row = (preview_remove is not None and preview_remove[0] == "comma"
                          and 0 <= preview_remove[1] < state.n)
        self.ghost_comma = (preview_remove is not None and preview_remove[0] == "row"
                            and len(state.mapping) > 1 and 0 <= preview_remove[1] < len(state.mapping))
        if not (self.ghost_row or self.ghost_comma):
            self.preview_remove = None
        self.targets_in_use = targets_in_use
        self.state = state
        self.settings = settings
        self.collapsed = collapsed
        self.tuning_scheme = tuning_scheme
        self.target_spec = target_spec
        self.interest = interest
        self.range_mode = range_mode
        self.pending_interest = pending_interest
        self.pending_held = pending_held
        self.pending_target = pending_target
        self.pending_element = pending_element
        self.pending_mapping_row = pending_mapping_row
        self.custom_prescaler = custom_prescaler
        self.custom_weights = custom_weights
        self.tuning_optimized = tuning_optimized
        self.nonprime_approach = nonprime_approach
        self.superspace_generator_tuning = superspace_generator_tuning
        self.displayed_tuning_name = displayed_tuning_name
        self.held_basis_ratios = held_basis_ratios
        self.displayed_projection_name = displayed_projection_name

        if self.settings is None:
            self.settings = _default_settings()
        if self.tuning_scheme is None:
            self.tuning_scheme = service.DEFAULT_DOCUMENT_SCHEME
        if self.target_spec is None:
            self.target_spec = service.DEFAULT_TARGET_SPEC
        self.collapsed = self.collapsed or frozenset()
        (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
         show_tuning, show_interest, show_interval_ratios) = self._unpack_show_flags()
        label_w = LABEL_W
        header_h = HEADER_H
        self._resolve_superspace_dims()
        self._resolve_prescaler_and_domain_labels()
        self._resolve_interval_sets(generator_tuning, target_override, held_vectors, pending_comma,
                                    show_temp, show_tuning)
        self._resolve_complexities()
        interest_tiles, held_tiles, detempering_tiles = self._declare_interval_column_tiles()
        self._resolve_projection_data(show_tuning)
        self._declare_tiles(interest_tiles, held_tiles, detempering_tiles)

        col_bands, content_x0 = self._define_col_bands(show_interval_ratios, show_domain_units,
                                                       show_temp, show_tuning, show_interest, label_w)

        row_bands = self._define_row_bands(show_counts, show_interval_ratios, show_domain_units,
                                           show_temp, show_tuning)

        self._layout_columns(col_bands, content_x0)

        tile_extra = self._resolve_tile_extras(show_ranges, show_tuning)

        rows_top_y = self._init_row_geometry(header_h)

        self._resolve_ptext_strings(generator_tuning, target_override)

        self._layout_rows(row_bands, tile_extra, rows_top_y, show_charts)

        self._init_group_geometry()

    def _unpack_show_flags(self):
        _f = _resolve_show_flags(self.settings, self.collapsed)
        self.show_captions = _f.captions
        self.show_mnemonics = _f.mnemonics
        self.show_equiv = _f.equiv
        self.show_presets = _f.presets
        show_counts = _f.counts
        self.show_ptext = _f.ptext
        show_charts = _f.charts
        show_ranges = _f.ranges
        self.show_symbols = _f.symbols
        self.ctrl_symbol_h = SYMBOL_H if self.show_symbols else 0
        self.show_header_symbols = _f.header_symbols
        self.show_units = _f.units
        self.show_cell_units = _f.cell_units
        show_domain_units = _f.domain_units
        show_temp = _f.temp
        self.show_form = _f.form
        self.show_form_controls = _f.form_controls
        self.show_form_tiles = _f.form_tiles
        show_tuning = _f.tuning
        self.show_optimization = _f.optimization
        self.show_weighting = _f.weighting
        self.show_alt_complexity = _f.alt_complexity
        self._complexity_shown = (self.show_weighting
                                  and service.damage_weight_slope(self.tuning_scheme) != "unityWeight")
        self.weight_unit = f"({service.weight_annotation(self.tuning_scheme)})"
        self.complexity_unit = f"({service.complexity_annotation(self.tuning_scheme)})"
        self.damage_unit = f"¢{self.weight_unit}"
        self._lbox_show = _f.lbox and self._complexity_shown
        self._cbox_show = _f.cbox and self._complexity_shown
        self.show_detempering = _f.detempering
        show_interest = _f.interest
        self.gridded = _f.gridded
        self.show_quantities = _f.quantities
        self._decimals = _f.decimals
        self.show_ebk = _f.ebk
        show_interval_ratios = _f.interval_ratios
        self.show_interval_vectors = _f.interval_vectors
        self.show_math = _f.math
        self.custom_weights_active = (self.custom_weights is not None
                                      and not service.is_all_interval(self.tuning_scheme)
                                      and not self.show_math)
        return (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
                show_tuning, show_interest, show_interval_ratios)

    def _resolve_superspace_dims(self) -> None:
        self.d = self.state.d
        self.r = len(self.state.mapping)
        self.row_draft = self.pending_mapping_row is not None or self.ghost_row
        self.r_shown = self.r + (1 if self.row_draft else 0)
        self.elements = self.state.domain_basis
        self.dL = service.superspace_dimension(self.elements)
        self.rL = service.superspace_rank(self.state)
        self._ss_tun = None
        self.superspace_primes = service.superspace_primes(self.elements)
        self.show_nonstandard_domain = self.settings.get("nonstandard_domain", False)
        self.show_superspace = (
            self.show_nonstandard_domain
            and service.domain_has_nonprimes(self.elements)
            and self.nonprime_approach != "nonprime-based"
        )
        self.show_superspace_generators = self.show_superspace and self.nonprime_approach == "prime-based"

    def _resolve_prescaler_and_domain_labels(self) -> None:
        _p = _resolve_prescaler_labels(self.state, self.tuning_scheme, self.custom_prescaler,
                                       self.show_equiv, self.show_superspace)
        self._scheme_prescaler = _p.scheme_prescaler
        self._realized_prescaler = _p.realized
        self.prescaler_symbol = _p.symbol
        self.prescaler_equivalence = _p.equivalence
        self.prescaling_symbols = _p.prescaling_symbols
        self.col_labels = _p.col_labels
        self.row_labels = _p.row_labels
        self.effective_captions = _p.effective_captions
        self.show_identity_objects = self.settings.get("identity_objects", False)
        self.standard_domain = service.is_standard_domain(self.elements)
        self.domain_label = "b" if service.domain_has_nonprimes(self.elements) else "p"
        self.domain_can_shrink = service.can_shrink_domain(self.state)

    def _resolve_interval_sets(self, generator_tuning, target_override, held_vectors, pending_comma,
                               show_temp, show_tuning) -> None:
        self.gens = service.generators(self.state.mapping, self.elements)
        self.ghost_new = None
        self.ghost_row_map = self.ghost_row_ratio = None
        self.ghost_row_mapped = {}
        self.ghost_comma_vec = self.ghost_comma_ratio = None
        self.ghost_comma_mapped = ()
        self.ghost_comma_just = 0.0
        self.ghost_comma_complexity = 0.0
        if self.ghost_row:
            self.ghost_new = service.remove_comma(self.state, self.preview_remove[1])
            self.ghost_row_map = self.ghost_new.mapping[-1]
            born_gens = service.generators(self.ghost_new.mapping, self.elements)
            self.ghost_row_ratio = born_gens[-1] if born_gens else ""
        elif self.ghost_comma:
            self.ghost_new = service.remove_mapping_row(self.state, self.preview_remove[1])
            self.ghost_comma_vec = self.ghost_new.comma_basis[-1] if self.ghost_new.comma_basis else None
            born_crs = service.comma_ratios(self.ghost_new.comma_basis, self.elements) if self.ghost_new.comma_basis else ()
            self.ghost_comma_ratio = born_crs[-1] if born_crs else ""
        self.targets = service.displayed_targets(self.state, self.tuning_scheme, self.target_spec, target_override)
        self.all_interval = service.is_all_interval(self.tuning_scheme)
        self.targets_editable = not self.all_interval
        self.k = len(self.targets)
        self.pending_target = list(self.pending_target) if (self.pending_target is not None and self.targets_editable) else None
        self.k_shown = self.k + (1 if self.pending_target is not None else 0)
        self.mapped = service.mapped_intervals(self.state.mapping, self.targets, self.elements)
        self.canon_mapping = service.canonical_mapping(self.state.mapping)
        self.rc = len(self.canon_mapping)
        self.form_M = service.form_matrix(self.state.mapping)
        self.canon_gens = service.generators(self.canon_mapping, self.elements)
        self.inverse_form_M = service.inverse_form_matrix(self.state.mapping)
        self.mapping_form_key = service.resolve_mapping_form(
            self.state.mapping, self.mapping_form, self.state.domain_basis)
        self.comma_basis_form_key = (
            service.resolve_comma_basis_form(self.state.comma_basis, self.comma_basis_form, self.state.domain_basis)
            if self.state.n else "")
        self.form_is_canonical = self.mapping_form_key == "canonical"
        self.show_form_subscript = self.show_form and self.form_is_canonical
        self.show_canon = self.show_form_tiles and not self.form_is_canonical
        self.target_vectors = service.target_interval_vectors(self.targets, self.d, self.elements)
        self.held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in held_vectors) if self.show_optimization else ()
        self.nh = len(self.held)
        self.pending_held = list(self.pending_held) if (self.pending_held is not None and self.show_optimization) else None
        self.nh_shown = self.nh + (1 if self.pending_held is not None else 0)
        self.held_ratios = service.comma_ratios(self.held, self.elements)
        if generator_tuning is not None and len(generator_tuning) == len(self.state.mapping):
            self.tun = service.tuning_from_generators(self.state.mapping, generator_tuning, self.elements)
            self._tun_from_generators = True
        else:
            self.tun = service.tuning(self.state.mapping, self.tuning_scheme, self.elements, self.nonprime_approach, held=self.held_ratios,
                                 prescaler_override=self.custom_prescaler, targets=target_override,
                                 weights_override=self.custom_weights)
            self._tun_from_generators = False
        self._optimum_target_override = target_override
        self.target_weights = service.interval_weights(self.state.mapping, self.tuning_scheme, self.targets,
                                                  prescaler_override=self.custom_prescaler,
                                                  domain_basis=self.elements,
                                                  weights_override=self.custom_weights)
        self.target_sizes = service.interval_sizes(self.tun, self.targets, self.elements, weights=self.target_weights)
        self.held_mapped = service.mapped_intervals(self.state.mapping, self.held_ratios, self.elements)
        self.held_sizes = service.interval_sizes(self.tun, self.held_ratios, self.elements)
        self.comma_ratios = service.comma_ratios(self.state.comma_basis, self.elements) if self.state.n else ()
        self.nc = len(self.comma_ratios)
        self.mapped_commas = service.mapped_commas(self.state.mapping, self.state.comma_basis)
        self.comma_sizes = service.interval_sizes(self.tun, self.comma_ratios, self.elements)
        _udata = (service.unchanged_interval_data(self.state, self.held_basis_ratios, self.tun,
                                                  self.tuning_scheme, self.elements, self.custom_prescaler)
                  if (show_temp and show_tuning and self.settings["projection"]) else None)
        self.show_unchanged = _udata is not None
        self.nu = len(_udata.basis) if self.show_unchanged else 0
        if _udata is not None:
            self.unchanged_basis, self.unchanged_ratios = _udata.basis, _udata.ratios
            self.unchanged_mapped, self.unchanged_sizes = _udata.mapped, _udata.sizes
            self.unchanged_complexities = _udata.complexities
        else:
            self.unchanged_basis = None
            self.unchanged_ratios = self.unchanged_mapped = self.unchanged_complexities = ()
            self.unchanged_sizes = service.IntervalSizes((), (), (), ())
        self.born_u = self.ghost_row and self.show_unchanged
        if self.born_u:
            tun_new = service.tuning(self.ghost_new.mapping, self.tuning_scheme, self.elements,
                                     self.nonprime_approach, held=self.held_basis_ratios,
                                     prescaler_override=self.custom_prescaler)
            ud_new = service.unchanged_interval_data(self.ghost_new, self.held_basis_ratios, tun_new,
                                                     self.tuning_scheme, self.elements, self.custom_prescaler)
            if ud_new is not None and len(ud_new.basis) > self.nu:
                bratio = ud_new.ratios[-1]
                bm = service.mapped_intervals(self.state.mapping, (bratio,), self.elements) if bratio is not None else None
                self.unchanged_basis = tuple(self.unchanged_basis) + (ud_new.basis[-1],)
                self.unchanged_ratios = tuple(self.unchanged_ratios) + (bratio,)
                self.unchanged_mapped = tuple(tuple(row) + (bm[i][0] if bm is not None else None,) for i, row in enumerate(self.unchanged_mapped))
                self.unchanged_complexities = tuple(self.unchanged_complexities) + (ud_new.complexities[-1],)
                s, n = self.unchanged_sizes, ud_new.sizes
                self.unchanged_sizes = service.IntervalSizes(
                    tuple(s.tempered) + (n.tempered[-1],), tuple(s.just) + (n.just[-1],),
                    tuple(s.errors) + (n.errors[-1],), tuple(s.damage) + (n.damage[-1],))
                self.nu += 1
            else:
                self.born_u = False
        self.pending = (list(pending_comma)
                        if pending_comma is not None else None)
        self.comma_draft = self.pending is not None or self.ghost_comma
        self.nc_shown = self.nc + (1 if self.comma_draft else 0)
        self.nv_shown = self.nc_shown + self.nu
        self.empty_comma_w = (_min_width_for_lines("nullity", 1)
                              if (self.show_unchanged and self.nc_shown == 0) else 0)
        if self.show_unchanged:
            for (rk, ck), name in list(self.effective_captions.items()):
                if ck == "commas":
                    renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
                    if renamed.count("list") > 1:
                        renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
                    self.effective_captions[(rk, ck)] = renamed
        self.interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in self.interest)
        self.mi = len(self.interest)
        self.pending_interest = list(self.pending_interest) if self.pending_interest is not None else None
        self.mi_shown = self.mi + (1 if self.pending_interest is not None else 0)
        self.element_draft = self.show_nonstandard_domain and self.pending_element is not None
        self.d_shown = self.d + (1 if self.element_draft else 0)
        self.interest_ratios = service.comma_ratios(self.interest, self.elements)
        self.interest_mapped = service.mapped_intervals(self.state.mapping, self.interest_ratios, self.elements)
        self.interest_sizes = service.interval_sizes(self.tun, self.interest_ratios, self.elements)
        if self.ghost_row and self.ghost_new is not None:
            nm = self.ghost_new.mapping
            def _newborn_mapped(ratios):
                return tuple(service.mapped_intervals(nm, (r,), self.elements)[-1][0] if r is not None else None
                             for r in ratios)
            self.ghost_row_mapped = {
                key: _newborn_mapped(ratios)
                for key, ratios in (("targets", self.targets), ("interest", self.interest_ratios),
                                    ("held", self.held_ratios), ("commas", self.comma_ratios),
                                    ("unchanged", self.unchanged_ratios))}
        elif self.ghost_comma and self.ghost_comma_ratio:
            col = service.mapped_intervals(self.state.mapping, (self.ghost_comma_ratio,), self.elements)
            self.ghost_comma_mapped = tuple(row[0] for row in col)
            self.ghost_comma_just = service.interval_sizes(self.tun, (self.ghost_comma_ratio,), self.elements).just[0]
            self.ghost_comma_complexity = service.interval_complexities(
                self.state.mapping, self.tuning_scheme, (self.ghost_comma_ratio,),
                prescaler_override=self.custom_prescaler, domain_basis=self.elements)[0]
        self._col_ids = {
            name: assign_column_tokens(self.prev_ids.get(name), keys, claim_unmatched=claim)
            for name, keys, claim in (("targets", self.targets, False),
                                      ("held", self.held_ratios, False),
                                      ("interest", self.interest_ratios, False),
                                      ("commas", self.comma_ratios, True),
                                      ("gens", tuple(tuple(row) for row in self.state.mapping), True))
        }
        self._col_ids["detempering"] = self._col_ids["gens"]

    def _resolve_complexities(self) -> None:
        self.complexities = {
            "primes": service.interval_complexities(self.state.mapping, self.tuning_scheme, tuple(service.element_ratio(e) for e in self.elements),
                                                    prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "commas": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.comma_ratios,
                                                    prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "targets": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.targets,
                                                     prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "interest": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.interest_ratios,
                                                      prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "held": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.held_ratios,
                                                  prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "detempering": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.gens,
                                                         prescaler_override=self.custom_prescaler, domain_basis=self.elements),
        }
        self.prescaler = service.complexity_prescaler(self.state.mapping, self.tuning_scheme, override=self.custom_prescaler)
        self.prescaler_is_matrix = isinstance(self.prescaler[0], (tuple, list))

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

    def _resolve_projection_data(self, show_tuning) -> None:
        self.show_projection = show_tuning and self.settings["projection"]
        if self.show_projection:
            for rc in (("mapping", "gens"), ("ss_mapping", "ssgens")):
                cap = self.effective_captions.get(rc)
                if cap and cap.endswith("generators"):
                    self.effective_captions[rc] = cap[:-1] + "(s / embedding)"
        self.projection_matrix = (service.tuning_projection(self.state, self.held_basis_ratios)
                                  if self.show_projection else None)
        self.embedding_matrix = (service.tuning_embedding(self.state, self.held_basis_ratios)
                                 if self.show_projection else None)
        self.canon_embedding_matrix = (service.canonical_generator_embedding(self.state, self.held_basis_ratios)
                                       if self.show_projection else None)
        self.projection_rationals = (service.projection_matrix_rationals(self.state, self.held_basis_ratios)
                                     if self.show_projection else None)
        self.proj_detempering = service.project_vectors(self.projection_rationals, self.detempering_vectors)
        self.proj_held = service.project_vectors(self.projection_rationals, self.held)
        self.proj_targets = service.project_vectors(self.projection_rationals, self.target_vectors)
        self.proj_interest = service.project_vectors(self.projection_rationals, self.interest)
        self.embedding_superspace = (service.superspace_generator_embedding_display(self.state, self.held_basis_ratios)
                                     if (self.show_projection and self.show_superspace) else None)
        self.projection_superspace = (service.superspace_prime_projection_display(self.state, self.held_basis_ratios)
                                      if (self.show_projection and self.show_superspace) else None)
        self.show_ss_projection = self.show_projection and self.show_superspace
        self.ss_projection_matrix = (service.superspace_tuning_projection(self.state, self.held_basis_ratios)
                                     if self.show_ss_projection else None)
        self.ss_embedding_matrix = (service.superspace_tuning_embedding(self.state, self.held_basis_ratios)
                                    if self.show_ss_projection else None)
        self.ss_projection_rationals = (service.superspace_projection_matrix_rationals(self.state, self.held_basis_ratios)
                                        if self.show_ss_projection else None)
        _lift = lambda vs: service.lift_vectors_to_superspace(self.elements, vs)
        _ssp = self.ss_projection_rationals
        self.ss_proj_basis = service.project_vectors(_ssp, service.basis_in_superspace(self.elements))
        self.ss_proj_detempering = service.project_vectors(_ssp, _lift(self.detempering_vectors))
        self.ss_proj_held = service.project_vectors(_ssp, _lift(self.held))
        self.ss_proj_targets = service.project_vectors(_ssp, _lift(self.target_vectors))
        self.ss_proj_interest = service.project_vectors(_ssp, _lift(self.interest))
        self.ss_unchanged = tuple(
            (service.lift_vectors_to_superspace(self.elements, (ub,))[0] if ub is not None else None)
            for ub in (self.unchanged_basis if self.show_unchanged else ()))
        self.ss_unchanged_mapped = tuple(
            (service.map_vectors_into_superspace_generators(self.state, (ub,))[0] if ub is not None else None)
            for ub in (self.unchanged_basis if self.show_unchanged else ()))

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

    def _resolve_tile_extras(self, show_ranges, show_tuning):
        self.gtm_chart = (show_ranges and show_tuning and "row:tuning" not in self.collapsed
                     and self.col_open("gens") and "tile:tuning:gens" not in self.collapsed)
        self.gtm_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if self.gtm_chart else 0
        self.lbox_ctrl = self._lbox_show and self.col_open("ssprimes" if self.show_superspace else "primes") and not self.show_presets
        self.lbox_extra = (RANGE_GAP + self.control_region_band_h(OPTION_BOX_PX + CAPTION_LINE)) if self.lbox_ctrl else 0
        self.cbox_ctrl = self._cbox_show and self.col_open("targets")
        self.cbox_extra = (RANGE_GAP + self.control_region_band_h(ROW_H + self.ctrl_symbol_h + 3 * CAPTION_LINE)) if self.cbox_ctrl else 0
        self.opt_ctrl = (self.show_optimization and "row:damage" not in self.collapsed
                    and self.col_open("targets") and "tile:damage:targets" not in self.collapsed)
        self.mean_damage_caption = "retuning magnitude" if self.all_interval else "power mean"
        if self.tuning_optimized:
            self.mean_damage_caption = f"minimized {self.mean_damage_caption}"
        self.opt_cap_lines = _wrap_lines(self.mean_damage_caption, OPT_MEAN_DAMAGE_W) if self.opt_ctrl else 1
        self.opt_extra = ((RANGE_GAP + OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + ROW_H + self.ctrl_symbol_h
                      + self.opt_cap_lines * CAPTION_LINE + OPT_PAD_B) if self.opt_ctrl else 0)
        self.show_approach = (service.domain_has_nonprimes(self.elements)
                          and "row:damage" not in self.collapsed and self.col_open("targets")
                          and "tile:damage:targets" not in self.collapsed)
        self.approach_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if self.show_approach else 0
        self.slope_ctrl = (self.show_weighting
                      and "row:weight" not in self.collapsed
                      and self.col_open("targets") and "tile:weight:targets" not in self.collapsed)
        self.slope_locked = self.slope_ctrl and (service.is_all_interval(self.tuning_scheme)
                                                 or self.custom_weights_active)
        self.slope_extra = (RANGE_GAP + self.control_region_band_h(PRESET_H + CAPTION_LINE)) if self.slope_ctrl else 0
        tile_extra = {
            "tuning": self.gtm_extra,
            "prescaling": self.lbox_extra,
            "complexity": self.cbox_extra,
            "weight": self.slope_extra,
            "damage": self.opt_extra + self.approach_extra,
        }
        return tile_extra

    def _init_row_geometry(self, header_h):
        self.header_y = 0
        self.col_node_y = header_h + (GAP - TOGGLE) / 2
        self.branch_top_y = self.col_node_y + TOGGLE
        rows_top_y = self.branch_top_y + GAP + GRIP_BAND
        self.FAN = (GAP - PAD) / 2

        self.rows: dict[str, RowBand] = {}
        self.row_cpick = {}
        return rows_top_y

    def _resolve_ptext_strings(self, generator_tuning, target_override) -> None:
        self.ptext_strings = (service.plain_text_values(self.state, self.tuning_scheme, self.target_spec,
                                                   held=self.held, interest=self.interest,
                                                   generator_tuning=generator_tuning,
                                                   target_override=target_override,
                                                   nonprime_approach=self.nonprime_approach,
                                                   superspace=self.show_superspace,
                                                   superspace_generator_override=(
                                                       self.superspace_generator_tuning
                                                       if self.show_superspace_generators else None),
                                                   consolidate_v=self.show_unchanged,
                                                   held_basis_ratios=self.held_basis_ratios,
                                                   decimals=self._decimals,
                                                   custom_prescaler=self.custom_prescaler,
                                                   derived=service.DerivedQuantities(
                                                       targets=self.targets, tun=self.tun,
                                                       target_weights=self.target_weights,
                                                       target_sizes=self.target_sizes,
                                                       comma_sizes=self.comma_sizes,
                                                       superspace_tun=(self.superspace_tun()
                                                                       if self.show_superspace else None)))
                         if self.show_ptext else {})
        if not self.show_ebk:
            self.ptext_strings = {k: service.ebk_to_simple_matrix(v) for k, v in self.ptext_strings.items()}

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

    def tuning_value_row(self, key: str, group: str, values, editable_kind=None) -> None:
        if not self.tile_open(key, group):
            return
        values = tuple(values)
        if key in CHARTED_ROWS:
            self.chart_tiles.append((key, group, values))
        y = self.rows[key].y
        is_gen_group = group in ("gens", "ssgens")
        is_prime_group = group in ("primes", "ssprimes")
        for i, v in enumerate(values):
            cid = f"{key}:{self.group_elem[group]}:{self.col_token(group, i)}"
            x = self.group_left[group](self.comma_value_pos(i) if group == "commas" else i)
            u = self.cell_unit(key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
            operand = self.closed_form_operand(key, group, i, v) if self.show_math else None
            if operand is not None:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, self.show_quantities, self._decimals), unit=u))
            else:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, editable_kind or "tuningvalue",
                                     text=service.cents(v, self._decimals), unit=u))
            if key in ("tuning", "just"):
                self._voice(f"{key}:{group}", i, v)
        pending_idx = self._pending_draft_idx(group)
        if pending_idx is not None and pending_idx[0] is not None:
            text = ""
            if self.ghost_comma and group == "commas":
                gsize = {"tuning": 0.0, "just": self.ghost_comma_just, "retune": -self.ghost_comma_just,
                         "complexity": self.ghost_comma_complexity}.get(key)
                if gsize is not None:
                    text = service.cents(gsize, self._decimals)
            self.cells.append(CellBox(f"{key}:{self.group_elem[group]}:draft", self.group_left[group](pending_idx[1]),
                                      y, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    def chart(self, rkey: str, ckey: str, values, indicator=None, indicator_label="") -> None:
        values = tuple(values)
        if values and rkey in self.rows and self.rows[rkey].chart_top is not None and self.tile_open(rkey, ckey):
            x = self.group_left[ckey](0) - BRACKET_W
            self.cells.append(CellBox(f"chart:{rkey}:{ckey}", x, self.rows[rkey].chart_top,
                                 2 * BRACKET_W + len(values) * COL_W, CHART_H, "chart", values=values,
                                 indicator=indicator, indicator_label=indicator_label))

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

    def tile_groups(self, rkey: str, ckey: str):
        region = set()
        if rkey == "canon" or ckey == "canongens":
            region |= {"temperament", "form"}
        if rkey in ("projection", "tuning"):
            region |= {"tuning"}
        if self.show_unchanged and ckey == "commas":
            return {"temperament", "tuning"} | region
        as_groups = lambda g: {g} if isinstance(g, str) else set(g)
        if rkey in SPINE_ROWS and ckey in SPINE_COLUMN_GROUP:
            return as_groups(SPINE_COLUMN_GROUP[ckey]) | region
        if ckey in SPINE_COLUMNS and rkey in SPINE_ROW_GROUP:
            return as_groups(SPINE_ROW_GROUP[rkey]) | region
        if ckey in SUPERSPACE_REGION_COLUMNS or rkey in SUPERSPACE_REGION_ROWS:
            groups = {"tuning"}
            if SPINE_COLUMN_GROUP.get(ckey) == "temperament":
                groups.add("temperament")
            return groups | region
        return {_FACTOR_GROUP[f] for f in CELL_FACTORS.get((rkey, ckey), ())} | region

    @staticmethod
    def _is_sole_option(options, value) -> bool:
        opts = options if isinstance(options, dict) else {o: o for o in options}
        return len(opts) == 1 and value in opts

    def _preset_locked(self, name: str) -> bool:
        if name == "tuning":
            options = presets.tuning_scheme_options(
                service.is_all_interval(self.tuning_scheme),
                self.settings["alt_complexity"], self.settings["weighting"])
            return self._is_sole_option(options, self.displayed_tuning_name)
        if name == "prescaler":
            return self._is_sole_option(presets.prescaler_options(self.settings["alt_complexity"]),
                                        self._realized_prescaler)
        if name == "projection":
            return not presets.projection_options(self.state)
        return False

    def control_box(self, box_id: str, ckey: str, top, cap_w, label, disabled: bool = False,
                    scheme_btn: bool = False, form_chooser=None):
        form_label = form_chooser[1] if form_chooser else None
        dropdown_w, label_h, box_h = self.control_dims(ckey, cap_w, label, scheme_btn, form_label)
        box_x, box_y = self.col_x[ckey], top + BOX_OUTER
        self.blocks.append(Block(box_id, box_x, box_y, self.col_w[ckey], box_h, boxed=True))
        ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER
        if scheme_btn:
            self.emit_scheme_button(ctrl_x, ctrl_y, ckey)
            ctrl_y += SCHEME_BTN_SQ + CTRL_LABEL_GAP
        if label:
            self.cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                                 "caption", text=label, align="left", disabled=disabled))
        if form_chooser:
            fid, fcap = form_chooser
            form_y = ctrl_y + PRESET_H + label_h + BAND_GAP
            self.cells.append(CellBox(fid, ctrl_x, form_y, dropdown_w, PRESET_H, "formchooser",
                                 text=self.mapping_form_key if fid.endswith(":mapping") else self.comma_basis_form_key))
            self.cells.append(CellBox(f"{fid}:label", ctrl_x, form_y + PRESET_H, dropdown_w, CAPTION_LINE,
                                 "caption", text=fcap, align="left"))
        return ctrl_x, dropdown_w, ctrl_y

    def _preset_form_label(self, name: str, rkey: str, ckey: str):
        embeds = (name == "temperament" and self.show_form_controls
                  and any(rk == rkey and ck == ckey for _n, rk, ck, _l in FORM_CHOOSERS))
        return "form" if embeds else None

    def control_region(self, box_id: str, ckey: str, top, content_h):
        box_y = top + BOX_OUTER
        self._control_region_boxes.append(Block(box_id, self.col_x[ckey], box_y, self.col_w[ckey],
                                                 2 * BOX_INNER + content_h, boxed=True))
        return self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER

    def control_region_band_h(self, content_h):
        return 2 * BOX_OUTER + 2 * BOX_INNER + content_h

    def emit_all_interval_check(self, check_x, ctrl_y) -> None:
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2
        self.cells.append(CellBox("control:all_interval", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.is_all_interval(self.tuning_scheme)))
        self.cells.append(CellBox("caption:all_interval", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="all-interval"))

    def emit_scheme_button(self, x, y, ckey: str) -> None:
        self.cells.append(CellBox(f"scheme:{ckey}", x, y, SCHEME_BTN_SQ, SCHEME_BTN_SQ, "scheme_button", text="✕"))
        label_y = y + (SCHEME_BTN_SQ - CAPTION_LINE) / 2
        self.cells.append(CellBox(f"scheme:{ckey}:label", x + SCHEME_BTN_SQ + 2, label_y, SCHEME_LABEL_W,
                             CAPTION_LINE, "caption", text="return to scheme", align="left"))

    def emit_diminuator_check(self, check_x, ctrl_y) -> None:
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2
        self.cells.append(CellBox("control:diminuator", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.diminuator_replaced(self.tuning_scheme)))
        self.cells.append(CellBox("caption:diminuator", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="replace diminuator"))

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
            for p in range(self.d):
                self.cells.append(CellBox(g.id_fn(self.col_token(g.group, col), p), g.left_fn(col) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.committed_kind, text=str(g.data[col][p]), prime=p, comma=col, unit=self.cell_unit("vectors", g.group, prime=p)))
                self._voice(f"vectors:{g.group}", col, g.sizes.just[col])
        if g.pending is not None:
            for p in range(self.d):
                v = g.pending[p]
                self.cells.append(CellBox(g.id_fn(self.pending_col_token(g.group), p), g.left_fn(g.count) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.pending_kind,
                                     text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=self.cell_unit("vectors", g.group, prime=p)))

    def _emit_vectors_band(self) -> None:
        if self.row_open("vectors"):
            if self.tile_open("vectors", "quantities"):
                bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
                for p in range(self.d):
                    text = str(self.elements[p])
                    kind = self._element_cell_kind(text) if self.show_nonstandard_domain else "prime"
                    self.cells.append(CellBox(f"basis:{p}", bx, self.vec_top(p), COL_W, ROW_H, kind, text=text, prime=p))
                basis_bus_x = self.node_edge + self.FAN if self._row_fans("vectors") else self.node_edge
                def basis_minus(cid, p, kind, **kw):
                    self.cells.append(CellBox(cid, basis_bus_x, self.vec_top(p),
                                         (bx + COL_W) - basis_bus_x, ROW_H, kind, **kw))
                if self.element_draft:
                    draft_text = self.pending_element or "?/?"
                    self.cells.append(CellBox("basis:pending", bx, self.vec_top(self.d), COL_W, ROW_H,
                                              self._element_cell_kind(draft_text), text=draft_text, prime=self.d, pending=True))
                    basis_minus("element_minus:basis:pending", self.d, "element_minus")
                if self.show_nonstandard_domain:
                    if self.d > 1:
                        for p in range(self.d):
                            basis_minus(f"element_minus:basis:{p}", p, "element_minus", prime=p)
                elif self.domain_can_shrink:
                    basis_minus("basis_minus", self.d - 1, "basis_minus")
                if "vectors" in self.row_plus_y:
                    plus_kind = "element_plus" if self.show_nonstandard_domain else "plus"
                    self.cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, self.row_plus_y["vectors"] - BTN / 2,
                                         BTN, BTN, plus_kind))
            if self.tile_open("vectors", "commas"):
                for c in range(self.nc):
                    for p in range(self.d):
                        self.cells.append(CellBox(ids.comma_cell(self.col_token('commas', c), p), self.comma_left(c), self.vec_top(p), COL_W, ROW_H, "commacell", text=str(self.state.comma_basis[c][p]), prime=p, comma=c, unit=self.cell_unit("vectors", "commas", prime=p)))
                        self._voice("vectors:commas", c, self.comma_sizes.just[c])
                    if self.show_presets:
                        self.cells.append(CellBox(f"commapick:{self.col_token('commas', c)}", self.comma_left(c), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=c))
                full_u = self.unchanged_basis is not None and all(v is not None for v in self.unchanged_basis)
                for j in range(self.nu):
                    doomed = self.pending is not None and j == self.nu - 1
                    born = self.born_u and j == self.nu - 1
                    for p in range(self.d):
                        vec_text = DASH if self.unchanged_basis[j] is None else str(self.unchanged_basis[j][p])
                        self.cells.append(CellBox(ids.unchanged_cell(j, p), self.comma_left(self.nc_shown + j), self.vec_top(p), COL_W, ROW_H,
                                             "unchangedcell" if (full_u and not doomed and not born) else "vec", text=vec_text, prime=p, comma=self.nc + j,
                                             unit=self.cell_unit("vectors", "commas", prime=p)))
                    self._voice("vectors:commas", self.nc + j, self.unchanged_sizes.just[j])
                if self.comma_draft:
                    col_kind = "vec" if self.ghost_comma else "commacell"
                    for p in range(self.d):
                        v = self.ghost_comma_vec[p] if self.ghost_comma else self.pending[p]
                        self.cells.append(CellBox(ids.comma_cell(self.pending_col_token('commas'), p), self.comma_left(self.nc), self.vec_top(p), COL_W, ROW_H, col_kind,
                                             text="" if v is None else str(v), prime=p, comma=self.nc, pending=True, unit=self.cell_unit("vectors", "commas", prime=p)))
                    if self.pending is not None and self.show_presets:
                        self.cells.append(CellBox("commapick:draft", self.comma_left(self.nc), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=self.nc, pending=True))
            if self.tile_open("vectors", "targets"):
                target_kind = "targetcell" if self.targets_editable else "vec"
                cell_inset = KET_INSET if self.targets_editable else 0
                self._emit_vec_grid(_VecGrid("targets", self.k, ids.target_cell, self.target_left,
                    cell_inset, target_kind, "targetcell", self.target_vectors, self.pending_target, self.target_sizes))
            if self.tile_open("vectors", "held"):
                self._emit_vec_grid(_VecGrid("held", self.nh, ids.held_cell, self.held_left,
                    0, "heldcell", "heldcell", self.held, self.pending_held, self.held_sizes))
            if self.tile_open("vectors", "detempering"):
                for i in range(self.r):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:vec:detempering:{self.col_token('detempering', i)}:{p}", self.detempering_left(i), self.vec_top(p), COL_W, ROW_H, "vec", text=str(self.detempering_vectors[i][p]), unit=self.cell_unit("vectors", "detempering", prime=p)))
                        self._voice("vectors:detempering", i, self.detempering_sizes.just[i])
            if self.tile_open("vectors", "interest"):
                self._emit_vec_grid(_VecGrid("interest", self.mi, ids.interest_cell, self.interest_left,
                    KET_INSET, "interestcell", "interestcell", self.interest, self.pending_interest, self.interest_sizes))
            if "vectors" in self.rows and self.rows["vectors"].int_handle_top is not None:
                hy = self.rows["vectors"].int_handle_top
                for group, count, col_left, ckey in (("comma", self.nc, self.comma_left, "commas"),
                                                     ("target", self.k, self.target_left, "targets"),
                                                     ("held", self.nh, self.held_left, "held"),
                                                     ("interest", self.mi, self.interest_left, "interest")):
                    if count >= 2 and self.tile_open("vectors", ckey) and (ckey != "targets" or self.targets_editable):
                        for i in range(count):
                            self.cells.append(CellBox(f"int_drag:{group}:{i}", col_left(i), hy, COL_W, ROW_HANDLE_W, "int_drag", comma=i))

    def _emit_superspace_rows(self) -> None:
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.dL):
                self.cells.append(CellBox(f"ss_basis:{p}", bx, self.ss_vec_top(p), COL_W, ROW_H,
                                          "prime", text=str(self.superspace_primes[p]), prime=p))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "quantities"):
            ss_gens = service.superspace_generators(self.state)
            for i in range(self.rL):
                self.cells.append(CellBox(f"ss_gen:{i}", self.col_x["quantities"], self.ss_map_top(i),
                                          self.col_w["quantities"], ROW_H, "genratio",
                                          text=ss_gens[i] if i < len(ss_gens) else ""))
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2
            for p in range(self.dL):
                self.cells.append(CellBox(f"ss_proj_basis:{p}", bx, self.ss_proj_top(p), COL_W, ROW_H, "prime",
                                          text=str(self.superspace_primes[p]), prime=p))
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "primes"):
            basis = service.basis_in_superspace(self.elements)
            for ss_prime_idx in range(self.dL):
                for elem_idx in range(self.d):
                    value = basis[elem_idx][ss_prime_idx]
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}",
                        self.prime_left(elem_idx), self.ss_vec_top(ss_prime_idx), COL_W, ROW_H,
                        "vec", text=str(value), prime=ss_prime_idx, comma=elem_idx,
                        unit=self.cell_unit("ss_vectors", "primes", prime=ss_prime_idx, elem=elem_idx),
                    ))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            ml = service.superspace_mapping(self.state)
            for gen_idx in range(self.rL):
                for ss_prime_idx in range(self.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}",
                        self.ss_prime_left(ss_prime_idx), self.ss_map_top(gen_idx), COL_W, ROW_H,
                        "mapped", text=str(ml[gen_idx][ss_prime_idx]),
                        gen=gen_idx, prime=ss_prime_idx,
                        unit=self.cell_unit("ss_mapping", "ssprimes", gen=gen_idx, prime=ss_prime_idx),
                    ))
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            mjl = service.superspace_just_mapping(self.superspace_primes)
            for i in range(self.dL):
                for j in range(self.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_vec_top(i), COL_W, ROW_H,
                        "mapped", text=str(mjl[i][j]), gen=i, prime=j,
                        unit=self.cell_unit("ss_vectors", "ssprimes", prime=j)))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            mlgl = service.superspace_self_map(self.state)
            for i in range(self.rL):
                for j in range(self.rL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssgens:{i}:{j}",
                        self.ss_gen_left(j), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(mlgl[i][j]), gen=i,
                        unit=self.cell_unit("ss_mapping", "ssgens", gen=i)))
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            msl = service.mapping_to_superspace_generators(self.state)
            for i in range(self.rL):
                for e in range(self.d):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:primes:{i}:{e}",
                        self.prime_left(e), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(msl[i][e]), gen=i,
                        unit=self.cell_unit("ss_mapping", "primes", gen=i, elem=e)))
        ss_lists = (("commas", self.state.comma_basis, self.nc, self.comma_left, self.comma_draft),
                    ("targets", self.target_vectors, self.k, self.target_left, self.pending_target is not None),
                    ("held", self.held, self.nh, self.held_left, self.pending_held is not None),
                    ("interest", self.interest, self.mi, self.interest_left, self.pending_interest is not None),
                    ("detempering", self.detempering_vectors, self.r, self.detempering_left, False))
        for ckey, vectors, n, left, draft in ss_lists:
            cols = tuple(vectors)[:n]
            if self.row_open("ss_vectors") and self.tile_open("ss_vectors", ckey):
                lifted = service.lift_vectors_to_superspace(self.elements, cols)
                for c in range(len(lifted)):
                    for p in range(self.dL):
                        self.cells.append(CellBox(
                            f"cell:ss_vectors:{ckey}:{p}:{c}", left(c), self.ss_vec_top(p),
                            COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                            unit=self.cell_unit("ss_vectors", ckey, prime=p)))
                if draft:
                    for p in range(self.dL):
                        self.cells.append(CellBox(f"cell:ss_vectors:{ckey}:{p}:draft", left(n), self.ss_vec_top(p),
                                             COL_W, ROW_H, "vec", text="", prime=p, pending=True))
                if ckey == "commas":
                    for j in range(self.nu):
                        uj = self.ss_unchanged[j]
                        for p in range(self.dL):
                            self.cells.append(CellBox(
                                f"cell:ss_vectors:commas:{p}:u{j}", self.comma_left(self.nc_shown + j), self.ss_vec_top(p),
                                COL_W, ROW_H, "vec", text=DASH if uj is None else str(uj[p]), prime=p, comma=self.nc + j,
                                unit=self.cell_unit("ss_vectors", "commas", prime=p)))
            if self.row_open("ss_mapping") and self.tile_open("ss_mapping", ckey):
                mapped = service.map_vectors_into_superspace_generators(self.state, cols)
                for c in range(len(mapped)):
                    for g in range(self.rL):
                        self.cells.append(CellBox(
                            f"cell:ss_mapping:{ckey}:{g}:{c}", left(c), self.ss_map_top(g),
                            COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                            unit=self.cell_unit("ss_mapping", ckey, gen=g)))
                if draft:
                    for g in range(self.rL):
                        self.cells.append(CellBox(f"cell:ss_mapping:{ckey}:{g}:draft", left(n), self.ss_map_top(g),
                                             COL_W, ROW_H, "mapped", text="", gen=g, pending=True))
                if ckey == "commas":
                    for j in range(self.nu):
                        uj = self.ss_unchanged_mapped[j]
                        for g in range(self.rL):
                            self.cells.append(CellBox(
                                f"cell:ss_mapping:commas:{g}:u{j}", self.comma_left(self.nc_shown + j), self.ss_map_top(g),
                                COL_W, ROW_H, "mapped", text=DASH if uj is None else str(uj[g]), gen=g, comma=self.nc + j,
                                unit=self.cell_unit("ss_mapping", "commas", gen=g)))
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            full = self.ss_projection_matrix is not None
            for i in range(self.dL):
                for j in range(self.dL):
                    text = DASH if not full else self.ss_projection_matrix[i][j]
                    self.cells.append(CellBox(
                        f"cell:ss_projection:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_proj_top(i), COL_W, ROW_H,
                        "mapped", text=text, gen=i, prime=j,
                        unit=self.cell_unit("ss_projection", "ssprimes", gen=i, prime=j),
                    ))
        ss_full = self.ss_projection_rationals is not None
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssgens"):
            for i in range(self.dL):
                for g in range(self.rL):
                    text = DASH if not ss_full else self.ss_embedding_matrix[i][g]
                    self.cells.append(CellBox(f"cell:ss_embed:{i}:{g}", self.ss_gen_left(g), self.ss_proj_top(i),
                                         COL_W, ROW_H, "mapped", text=text, gen=g))
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "primes"):
            for e in range(self.d):
                for p in range(self.dL):
                    text = DASH if not ss_full else str(self.ss_proj_basis[e][p])
                    self.cells.append(CellBox(f"cell:ss_proj_bls:{e}:{p}", self.prime_left(e), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text=text, prime=p, comma=e))
        _ssp = dict(full=ss_full, colwise=True, row="ss_projection", top=self.ss_proj_top, height=self.dL)
        self._emit_mapped_grid("detempering", "ss_proj_pd", self.ss_proj_detempering, self.r, self.detempering_left, "gen", **_ssp)
        if self.show_unchanged and self.row_open("ss_projection") and self.tile_open("ss_projection", "commas"):
            for c in range(self.nc):
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{c}", self.comma_left(c), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            if self.pending is not None:
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:draft", self.comma_left(self.nc), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text="", prime=p, pending=True))
            for j in range(self.nu):
                dashed = self.ss_unchanged[j] is None
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{self.nc + j}", self.comma_left(self.nc_shown + j), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped",
                                         text=DASH if dashed else str(self.ss_unchanged[j][p]), prime=p, comma=self.nc + j))
        self._emit_mapped_grid("targets", "ss_proj_pt", self.ss_proj_targets, self.k, self.target_left, "comma",
                               pending=self.pending_target, **_ssp)
        self._emit_mapped_grid("held", "ss_proj_ph", self.ss_proj_held, self.nh, self.held_left, "comma",
                               pending=self.pending_held, **_ssp)
        self._emit_mapped_grid("interest", "ss_proj_pi", self.ss_proj_interest, self.mi, self.interest_left, "comma",
                               inset=KET_INSET, pending=self.pending_interest, **_ssp)

    def _emit_identity_objects(self) -> None:
        if self.tile_open("vectors", "primes"):
            for i in range(self.d):
                for k in range(self.d):
                    self.cells.append(CellBox(
                        f"cell:vec:primes:{i}:{k}", self.prime_left(k), self.vec_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i, prime=k,
                        unit=self.cell_unit("vectors", "primes", prime=k)))
        for ckey, prefix, left in (("gens", "selfmap", self.gen_left),
                                   ("detempering", "mapped_detempering", self.detempering_left)):
            if self.tile_open("mapping", ckey):
                for i in range(self.r):
                    for k in range(self.r):
                        self.cells.append(CellBox(
                            f"cell:{prefix}:{i}:{k}", left(k), self.map_top(i), COL_W, ROW_H,
                            "mapped", text="1" if i == k else "0", gen=i,
                            unit=self.cell_unit("mapping", ckey, gen=i)))
        if self.tile_open("canon", "canongens"):
            for i in range(self.rc):
                for k in range(self.rc):
                    self.cells.append(CellBox(
                        f"cell:fcancel:{i}:{k}", self.canongen_left(k), self.canon_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i,
                        unit=self.cell_unit("canon", "canongens", gen=i)))

    def _emit_tuning_rows(self):
        self.chart_tiles = []
        chart_indicators = {}

        tuning_data = {
            "tuning": (self.tun.tuning_map, self.comma_sizes.tempered + self.unchanged_sizes.tempered, self.target_sizes.tempered, self.interest_sizes.tempered, self.held_sizes.tempered),
            "just": (self.tun.just_map, self.comma_sizes.just + self.unchanged_sizes.just, self.target_sizes.just, self.interest_sizes.just, self.held_sizes.just),
            "retune": (self.tun.retuning_map, self.comma_sizes.errors + self.unchanged_sizes.errors, self.target_sizes.errors, self.interest_sizes.errors, self.held_sizes.errors),
        }
        for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
            if self.row_open(key):
                self.tuning_value_row(key, "primes", prime_vals)
                self.tuning_value_row(key, "commas", comma_vals)
                self.tuning_value_row(key, "targets", target_vals)
                self.tuning_value_row(key, "interest", interest_vals)
                self.tuning_value_row(key, "held", held_vals)
        if self.row_open("tuning") and self.tile_open("tuning", "gens"):
            gen_kind = "tuningvalue" if self.show_superspace_generators else "gentuningcell"
            for i, v in enumerate(self.tun.generator_map):
                operand = None
                if self.show_math and not self.show_superspace_generators:
                    closed_form = self._closed_form()
                    operand = closed_form.generator_operand(i, v) if closed_form is not None else None
                if operand is not None:
                    self.cells.append(CellBox(f"tuning:gen:{self.col_token('gens', i)}", self.group_left["gens"](i), self.rows["tuning"].y, COL_W, ROW_H,
                                         "mathexpr", text=_math_expr(operand, v, self.show_quantities, self._decimals), unit=self.cell_unit("tuning", "gens", gen=i)))
                else:
                    self.cells.append(CellBox(f"tuning:gen:{self.col_token('gens', i)}", self.group_left["gens"](i), self.rows["tuning"].y, COL_W, ROW_H,
                                         gen_kind, text=service.cents(v, self._decimals), gen=i, unit=self.cell_unit("tuning", "gens", gen=i)))
                self._voice("tuning:gens", i, v)
        if self.row_open("tuning") and self.tile_open("tuning", "canongens"):
            gm = self.tun.generator_map
            for j in range(self.rc):
                v = sum(gm[k] * self.inverse_form_M[k][j] for k in range(self.r))
                operand = None
                if self.show_math:
                    closed_form = self._closed_form()
                    if closed_form is not None:
                        coefficients = [self.inverse_form_M[k][j] for k in range(self.r)]
                        operand = closed_form.canonical_generator_operand(coefficients, v)
                if operand is not None:
                    self.cells.append(CellBox(f"tuning:cangen:{j}", self.canongen_left(j), self.rows["tuning"].y, COL_W, ROW_H,
                                         "mathexpr", text=_math_expr(operand, v, self.show_quantities, self._decimals), unit=self.cell_unit("tuning", "canongens", gen=j)))
                else:
                    self.cells.append(CellBox(f"tuning:cangen:{j}", self.canongen_left(j), self.rows["tuning"].y, COL_W, ROW_H,
                                         "tuningvalue", text=service.cents(v, self._decimals), gen=j, unit=self.cell_unit("tuning", "canongens", gen=j)))
                self._voice("tuning:canongens", j, v)
        if self.show_superspace and self.row_open("tuning"):
            ss_tun = self.superspace_tun()
            if self.tile_open("tuning", "ssgens"):
                if self.show_superspace_generators:
                    ss_cf = self._ss_closed_form() if self.show_math else None
                    for i, v in enumerate(ss_tun.generator_map):
                        operand = ss_cf.generator_operand(i, v) if ss_cf is not None else None
                        if operand is not None:
                            self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"](i), self.rows["tuning"].y,
                                                 COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, self.show_quantities, self._decimals),
                                                 unit=self.cell_unit("tuning", "ssgens", gen=i)))
                        else:
                            self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"](i), self.rows["tuning"].y,
                                                 COL_W, ROW_H, "gentuningcell", text=service.cents(v, self._decimals),
                                                 unit=self.cell_unit("tuning", "ssgens", gen=i)))
                        self._voice("tuning:ssgens", i, v)
                else:
                    self.tuning_value_row("tuning", "ssgens", ss_tun.generator_map)
            self.tuning_value_row("tuning", "ssprimes", ss_tun.tuning_map)
            if self.row_open("just"):
                self.tuning_value_row("just", "ssprimes", ss_tun.just_map)
            if self.row_open("retune"):
                self.tuning_value_row("retune", "ssprimes", ss_tun.retuning_map)
        if self.show_detempering:
            for key, values in (("tuning", self.detempering_sizes.tempered),
                                ("just", self.detempering_sizes.just),
                                ("retune", self.detempering_sizes.errors)):
                if self.row_open(key):
                    self.tuning_value_row(key, "detempering", values)
        return chart_indicators

    def _emit_prescaling_band(self) -> None:
        nrows = self.prescale_rows
        if self.show_superspace:
            prescaler_diag = service.superspace_complexity_prescaler(self.state, self.tuning_scheme)
            prescaler_is_matrix = False
            ss_elements = service.superspace_primes(self.elements)
            _lift = lambda vs: tuple(None if v is None else service.lift_vectors_to_superspace(self.elements, (v,))[0]
                                     for v in vs)
            prescale_vectors = {
                "ssprimes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                "primes": service.basis_in_superspace(self.elements),
                "commas": _lift(self.state.comma_basis) + (_lift(self.unchanged_basis) if self.show_unchanged else ()),
                "targets": _lift(self.target_vectors),
                "interest": _lift(self.interest),
                "held": _lift(self.held),
                "detempering": _lift(self.detempering_vectors),
            }
            groups = ("ssprimes", "primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "ssprimes"
        else:
            prescaler_diag = self.prescaler
            prescaler_is_matrix = self.prescaler_is_matrix
            ss_elements = self.elements
            prescale_vectors = {
                "primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                "commas": self.state.comma_basis + (self.unchanged_basis if self.show_unchanged else ()),
                "targets": self.target_vectors,
                "interest": self.interest,
                "held": self.held,
                "detempering": self.detempering_vectors,
            }
            groups = ("primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "primes"
        if self._scheme_prescaler == "log-prime":
            prime_term = {i: f"log₂{p}" for i, p in enumerate(ss_elements)}
        elif self._scheme_prescaler == "prime":
            prime_term = {i: str(p) for i, p in enumerate(ss_elements)}
        else:
            prime_term = {}
        for group in groups:
            if not self.tile_open("prescaling", group):
                continue
            left = self.group_left[group]
            for c, vec in enumerate(prescale_vectors[group]):
                u = self.cell_unit("prescaling", group, prime=c if group == bare_group else None)
                if vec is None:
                    for i in range(nrows + self.size_rows):
                        cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
                        cx, cy = left(self.comma_value_pos(c) if group == "commas" else c), self.rows["prescaling"].y + i * ROW_H
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue", text=DASH, unit=u))
                    continue
                prescaled = ([sum(prescaler_diag[i][k] * vec[k] for k in range(nrows)) for i in range(nrows)]
                             if prescaler_is_matrix
                             else [prescaler_diag[i] * vec[i] for i in range(nrows)])
                for i in range(nrows + self.size_rows):
                    value = prescaled[i] if i < nrows else self.size_factor * sum(prescaled)
                    cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
                    cx, cy = left(self.comma_value_pos(c) if group == "commas" else c), self.rows["prescaling"].y + i * ROW_H
                    if i < nrows and not self.show_superspace and group == "primes" and (i == c or self.show_alt_complexity):
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "prescalercell",
                                             text=service.prescale_text(value, self._decimals), prime=i, unit=u))
                    elif i < nrows and self.show_math and vec[i] != 0 and i in prime_term:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "mathexpr",
                                             text=_prescale_math_expr(vec[i], prime_term[i], value, self.show_quantities, self._decimals), unit=u))
                    else:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue",
                                             text=service.prescale_text(value, self._decimals), unit=u))
            pending_idx = self._pending_draft_idx(group)
            if pending_idx is not None and pending_idx[0] is not None:
                ghost_pre = None
                if self.ghost_comma and group == "commas" and self.ghost_comma_vec is not None:
                    gvec = _lift((self.ghost_comma_vec,))[0] if self.show_superspace else self.ghost_comma_vec
                    ghost_pre = ([sum(prescaler_diag[i][k] * gvec[k] for k in range(nrows)) for i in range(nrows)]
                                 if prescaler_is_matrix else [prescaler_diag[i] * gvec[i] for i in range(nrows)])
                for i in range(nrows + self.size_rows):
                    cy = self.rows["prescaling"].y + i * ROW_H
                    text = ""
                    if ghost_pre is not None:
                        value = ghost_pre[i] if i < nrows else self.size_factor * sum(ghost_pre)
                        text = service.prescale_text(value, self._decimals)
                    self.cells.append(CellBox(f"cell:prescaling:{group}:{i}:draft", left(pending_idx[1]),
                                         cy, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    def _emit_lbox_control(self) -> None:
        if self.lbox_ctrl:
            box_top = self.rows["prescaling"].tile_top + self.rows["prescaling"].tile_h - self.lbox_extra + RANGE_GAP
            bx, by = self.control_region("block:diminuator", "ssprimes" if self.show_superspace else "primes",
                                         box_top, OPTION_BOX_PX + CAPTION_LINE)
            self.cells.append(CellBox("control:diminuator", bx, by, LBOX_DIM_W, OPTION_BOX_PX,
                                 "control_check", text="",
                                 checked=service.diminuator_replaced(self.tuning_scheme)))
            self.cells.append(CellBox("caption:diminuator", bx, by + OPTION_BOX_PX, LBOX_DIM_W,
                                 CAPTION_LINE, "caption", text="replace diminuator"))

    def _emit_cbox_controls(self) -> None:
        if self.cbox_ctrl:
            box_top = self.rows["complexity"].tile_top + self.rows["complexity"].tile_h - self.cbox_extra + RANGE_GAP
            tx, cy = self.control_region("block:complexity", "targets", box_top, ROW_H + self.ctrl_symbol_h + 3 * CAPTION_LINE)
            sym_y = cy + ROW_H
            cap_y = sym_y + self.ctrl_symbol_h
            cap_h = 3 * CAPTION_LINE
            slot_w = CBOX_SLOT_W
            q_slot_x = tx
            if self.show_presets:
                drop_w = CBOX_DROP_W
                complexity_key = service.complexity_name_of(self.tuning_scheme)
                if self._realized_prescaler is None:
                    complexity_key = "custom"
                complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
                complexity_values = ((tuple(service.COMPLEXITY_DISPLAYS.values()) + ("custom",))
                                     if self.show_alt_complexity else (complexity_text,))
                complexity_locked = self._is_sole_option(complexity_values, complexity_text)
                self.cells.append(CellBox("control:complexity", tx, cy, drop_w, PRESET_H,
                                     "control_select", text=complexity_text, values=complexity_values,
                                     disabled=complexity_locked))
                self.cells.append(CellBox("caption:complexity", tx, cy + PRESET_H, drop_w,
                                     CAPTION_LINE, "caption", text="predefined complexities",
                                     align="left", disabled=complexity_locked))
                q_slot_x = tx + drop_w + OPT_COL_GAP
            q_x = q_slot_x + (slot_w - COL_W) / 2
            q_text = _format_power(service.complexity_norm_power(self.tuning_scheme))
            q_kind = "powerinput" if self.show_alt_complexity else "powerdisplay"
            self.cells.append(CellBox("control:q", q_x, cy, COL_W, ROW_H, q_kind, text=q_text))
            if self.show_symbols:
                self.cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_w, SYMBOL_H, "symbol", text="𝑞"))
            self.cells.append(CellBox("caption:q", q_slot_x, cap_y, slot_w, cap_h, "caption",
                                 text="interval complexity norm power"))
            if service.is_all_interval(self.tuning_scheme):
                dual_slot_x = q_slot_x + slot_w + OPT_COL_GAP
                dual_x = dual_slot_x + (slot_w - COL_W) / 2
                dual_text = _format_power(service.dual_norm_power(self.tuning_scheme))
                self.cells.append(CellBox("control:dual", dual_x, cy, COL_W, ROW_H, "powerdisplay", text=dual_text))
                if self.show_symbols:
                    self.cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_w, SYMBOL_H,
                                         "symbol", text="dual(𝑞)"))
                self.cells.append(CellBox("caption:dual", dual_slot_x, cap_y, slot_w, cap_h, "caption",
                                     text="dual norm power"))

    def _emit_complexity_row(self) -> None:
        if self.row_open("complexity"):
            for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
                values = self.complexities[group] + (self.unchanged_complexities if group == "commas" else ())
                self.tuning_value_row("complexity", group, values)
            if self.show_superspace and self.tile_open("complexity", "ssprimes"):
                self.tuning_value_row("complexity", "ssprimes",
                              service.superspace_complexity_prescaler(self.state, self.tuning_scheme))

    def _emit_weight_row(self) -> None:
        if self.row_open("weight") and self.tile_open("weight", "targets"):
            self.tuning_value_row("weight", "targets", self.target_weights,
                                  editable_kind="weightcell" if self.custom_weights_active else None)
        if self.slope_ctrl:
            box_top = self.rows["weight"].tile_top + self.rows["weight"].tile_h - self.slope_extra + RANGE_GAP
            bx, by = self.control_region("block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
            slope_w = self.col_w["targets"] - 2 * BOX_INNER
            self.cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                                 "control_select", text=service.weight_slope_of(self.tuning_scheme),
                                 values=tuple(service.WEIGHT_SLOPES), disabled=self.slope_locked))
            self.cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                                 slope_w, CAPTION_LINE, "caption",
                                 text="damage weight slope", align="left", disabled=self.slope_locked))

    def _emit_damage_row(self, chart_indicators) -> None:
        if self.row_open("damage"):
            self.tuning_value_row("damage", "targets", self.target_sizes.damage)
            if self.show_optimization:
                power = self.displayed_mean_damage_power()
                chart_indicators[("damage", "targets")] = (
                    _power_mean(self.target_sizes.damage, power), _format_power(power))

    def _emit_charts(self, chart_indicators) -> None:
        for rkey, ckey, values in self.chart_tiles:
            indicator, label = chart_indicators.get((rkey, ckey), (None, ""))
            self.chart(rkey, ckey, values, indicator=indicator, indicator_label=label)

    def _emit_tuning_ranges_box(self):
        gtm_box = None
        if self.gtm_chart:
            chosen = self.tun.monotone_generator_range if self.range_mode == "monotone" else self.tun.tradeoff_generator_range
            gx, gw = self.col_x["gens"], self.col_w["gens"]
            cy = self.rows["tuning"].tile_top + self.rows["tuning"].tile_h - self.gtm_extra + RANGE_GAP
            self.cells.append(CellBox("rangetitle:tuning:gens", gx, cy + BOX_INNER, gw, BOX_TITLE_H, "boxtitle",
                                 text="tuning ranges", align="left"))
            chart_y = cy + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.cells.append(CellBox("rangechart:tuning:gens", gx, chart_y, gw, RANGE_CHART_H, "rangechart",
                                 ranges=tuple(chosen) if chosen is not None else (),
                                 values=tuple(self.tun.generator_map),
                                 decimals=self._decimals))
            self.cells.append(CellBox("rangemode:tuning:gens", gx, chart_y + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                                 "rangemode", text=self.range_mode))
            gtm_box = (gx, cy, gw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)
        return gtm_box

    def _emit_optimization_box(self):
        opt_box = None
        if self.opt_ctrl:
            ox = self.col_x["targets"]
            box_w = self.col_w["targets"]
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra + RANGE_GAP)
            title_top = box_top + OPT_PAD_T
            content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP
            sym_top = content_top + ROW_H
            cap_top = sym_top + self.ctrl_symbol_h
            cap_band = self.opt_cap_lines * CAPTION_LINE
            body_h = ROW_H + self.ctrl_symbol_h + cap_band + OPT_PAD_B
            mean_damage_x = ox + OPT_PAD_L
            mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2
            pow_slot_x = mean_damage_x + OPT_MEAN_DAMAGE_W + OPT_COL_GAP
            pow_x = pow_slot_x + (OPT_POW_CAP_W - COL_W) / 2
            mean_damage = _power_mean(self.target_sizes.damage, self.displayed_mean_damage_power())
            power = _format_power(self.displayed_optimization_power())
            self.cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                                 text="optimization"))
            self.cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                                 text=service.cents(mean_damage, self._decimals)))
            mean_damage_symbol = (f"⟪𝒓{self.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                          if self.all_interval else "⟪𝐝⟫ₚ")
            if self.tuning_optimized:
                mean_damage_symbol = f"min({mean_damage_symbol})"
            if self.show_symbols:
                self.cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPT_MEAN_DAMAGE_W, SYMBOL_H,
                                     "symbol", text=mean_damage_symbol))
            self.cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, cap_top, OPT_MEAN_DAMAGE_W, cap_band,
                                 "caption", text=self.mean_damage_caption))
            power_locked = self.all_interval or not self.show_alt_complexity
            self.cells.append(CellBox("optimization:power", pow_x, content_top, COL_W, ROW_H,
                                 "powerdisplay" if power_locked else "powerinput", text=power))
            if self.show_symbols:
                self.cells.append(CellBox("optimization:power:symbol", pow_x, sym_top, COL_W, SYMBOL_H,
                                     "symbol", text="𝑝"))
            self.cells.append(CellBox("optimization:power:caption", pow_x + (COL_W - OPT_POW_CAP_W) / 2, cap_top,
                                 OPT_POW_CAP_W, CAPTION_LINE, "caption", text="optimization power"))
            opt_box = (ox, box_top, box_w, OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + body_h)
        return opt_box

    def _emit_approach_box(self):
        approach_frame = None
        self.approach_box = None
        if self.show_approach:
            ax = self.col_x["targets"]
            aw = self.col_w["targets"]
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra - self.approach_extra + RANGE_GAP)
            self.cells.append(CellBox("optimization:approach:title", ax, box_top + BOX_INNER, aw, BOX_TITLE_H, "boxtitle",
                                 text="nonstandard domain approach", align="left"))
            radio_top = box_top + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.approach_box = (ax + OPT_PAD_L, radio_top,
                                 aw - OPT_PAD_L - OPT_PAD_R, APPROACH_RADIO_H)
            approach_frame = (ax, box_top, aw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H)
        return approach_frame

    def _emit_brackets(self) -> None:
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
        if self.row_open("canon"):
            canon_y, canon_h = (self.rows["canon"].y if "canon" in self.rows else 0), self.rc * ROW_H
            if self.tile_open("canon", "detempering"):
                self.bracket("canon_detempering", "canon", "detempering", canon_y, canon_h, fit=True)
            if self.tile_open("canon", "commas"):
                self.bracket("canon_comma", "canon", "commas", canon_y, canon_h, fit=True)
            if self.tile_open("canon", "targets"):
                self.bracket("canon_mapped", "canon", "targets", canon_y, canon_h, fit=True)
            if self.nh and self.tile_open("canon", "held"):
                self.bracket("canon_hmapped", "canon", "held", canon_y, canon_h, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "primes"):
            for i in range(self.d):
                self.bracket(f"proj:{i}", "projection", "primes", self.proj_top(i), ROW_H, stacked=True)
        if self.row_open("projection") and self.tile_open("projection", "gens"):
            self.bracket("embed", "projection", "gens", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "canongens"):
            self.bracket("embed_c", "projection", "canongens", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "ssgens"):
            self.bracket("embed_sl", "projection", "ssgens", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "ssprimes"):
            for i in range(self.d):
                self.bracket(f"proj_sl:{i}", "projection", "ssprimes", self.proj_top(i), ROW_H, stacked=True)
        if self.show_unchanged and self.row_open("projection") and self.tile_open("projection", "commas"):
            self.bracket("proj_v", "projection", "commas", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "detempering"):
            self.bracket("proj_pd", "projection", "detempering", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "targets"):
            self.bracket("proj_pt", "projection", "targets", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "held"):
            self.bracket("proj_ph", "projection", "held", self.rows["projection"].y, self.d * ROW_H, fit=True)
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
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            for i in range(self.rL):
                self.bracket(f"ss_map:{i}", "ss_mapping", "ssprimes", self.ss_map_top(i), ROW_H, stacked=True)
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_proj:{i}", "ss_projection", "ssprimes", self.ss_proj_top(i), ROW_H, stacked=True)
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
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_vec_jmap:{i}", "ss_vectors", "ssprimes", self.ss_vec_top(i), ROW_H, stacked=True)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            for i in range(self.rL):
                self.bracket(f"ss_msl:{i}", "ss_mapping", "primes", self.ss_map_top(i), ROW_H, stacked=True)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            self.bracket("ss_selfmap", "ss_mapping", "ssgens",
                         self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
        if self.tile_open("vectors", "primes"):
            for i in range(self.d):
                self.bracket(f"vec:primes:{i}", "vectors", "primes", self.vec_top(i), ROW_H, stacked=True)
        if self.tile_open("mapping", "gens"):
            self.bracket("selfmap", "mapping", "gens",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)
        if self.tile_open("mapping", "detempering"):
            self.bracket("mapped_detempering", "mapping", "detempering",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)
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
        if self.row_open("ss_mapping"):
            for group in ("commas", "targets"):
                if self.tile_open("ss_mapping", group):
                    self.bracket(f"ss_mapped:{group}", "ss_mapping", group, self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_mapping", "held"):
                self.bracket("ss_mapped:held", "ss_mapping", "held", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.tile_open("ss_mapping", "detempering"):
                self.bracket("ss_mapped:detempering", "ss_mapping", "detempering", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
        if self.row_open("vectors"):
            for group in ("commas", "targets"):
                if self.tile_open("vectors", group):
                    self.bracket(f"vec:{group}", "vectors", group, self.rows["vectors"].y, self.d * ROW_H, fit=True)
            if self.nh and self.tile_open("vectors", "held"):
                self.bracket("vec:held", "vectors", "held", self.rows["vectors"].y, self.d * ROW_H, fit=True)
            if self.tile_open("vectors", "detempering"):
                self.bracket("vec:detempering", "vectors", "detempering", self.rows["vectors"].y, self.d * ROW_H, fit=True)
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
        if self.tile_open("tuning", "gens"):
            self.bracket("tuning:genmap", "tuning", "gens", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "canongens"):
            self.bracket("tuning:cangenmap", "tuning", "canongens", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "detempering"):
            self.bracket("tuning:detempering", "tuning", "detempering", self.rows["tuning"].y, ROW_H)
        if self.tile_open("tuning", "ssgens"):
            self.bracket("tuning:ssgenmap", "tuning", "ssgens", self.rows["tuning"].y, ROW_H)
        for key in ("tuning", "just", "retune", "complexity"):
            if self.row_open(key):
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
        if self.tile_open("weight", "targets"):
            self.bracket("weight", "weight", "targets", self.rows["weight"].y, ROW_H)
        if self.tile_open("damage", "targets"):
            self.bracket("damage", "damage", "targets", self.rows["damage"].y, ROW_H)

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

    def _emit_presets(self) -> None:
        if self.show_presets:
            preset_text = {"temperament": "", "target": self.target_spec,
                              "tuning": service.base_scheme_name(self.tuning_scheme) or "",
                              "prescaler": self._realized_prescaler or "",
                              "projection": self.displayed_projection_name or ""}

            def emit_preset(cid, name, rkey, ckey, label):
                if not self.tile_open(rkey, ckey):
                    return
                if self.size_factor or self.prescaler_is_matrix:
                    label = _pretransform_label(label)
                top = self.ptext_band_y(rkey) + self.rows[rkey].ptext
                disabled = (name == "target" and service.is_all_interval(self.tuning_scheme)) \
                    or self._preset_locked(name)
                fc = next((fn for fn, rk, ck, _l in FORM_CHOOSERS if rk == rkey and ck == ckey), None)
                form_chooser = (f"formchooser:{fc}", "form") if (fc and self._preset_form_label(name, rkey, ckey)) else None
                cx, cw, cy = self.control_box(f"block:{cid}", ckey, top, self.preset_cap(name), label,
                                              disabled=disabled, scheme_btn=(name == "projection"),
                                              form_chooser=form_chooser)
                self.cells.append(CellBox(cid, cx, cy, cw, PRESET_H, "preset", text=preset_text[name],
                                     disabled=disabled))
                if name == "target" and self.settings["all_interval"]:
                    self.emit_all_interval_check(cx + cw + OPT_COL_GAP, cy)
                if name == "prescaler" and self.settings["alt_complexity"]:
                    self.emit_diminuator_check(cx + cw + OPT_COL_GAP, cy)

            for name, rkey, ckey, label in PRESETS:
                if name == "prescaler" and self.show_superspace:
                    ckey = "ssprimes"
                emit_preset(f"preset:{name}", name, rkey, ckey, label)
            for name, rkey, ckey, label in PRESET_COPIES:
                if name == "tuning" and ckey == "gens" and self.show_superspace_generators:
                    ckey = "ssgens"
                emit_preset(f"preset:{name}:{ckey}", name, rkey, ckey, label)

    def _emit_all_interval_check_fallback(self) -> None:
        if self.settings["all_interval"] and not self.show_presets and self.tile_open("vectors", "targets"):
            top = self.ptext_band_y("vectors") + self.rows["vectors"].ptext
            self.emit_all_interval_check(self.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)

    def _emit_form_choosers(self) -> None:
        if self.show_form_controls and not self.show_presets:
            for name, rkey, ckey, label in FORM_CHOOSERS:
                if not self.tile_open(rkey, ckey):
                    continue
                top = self.ptext_band_y(rkey) + self.rows[rkey].ptext + self.rows[rkey].pre
                cx, cw, cy = self.control_box(f"block:formchooser:{name}", ckey, top, PRESET_W, label)
                self.cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser",
                                     text=self.mapping_form_key if name == "mapping" else self.comma_basis_form_key))

    def _emit_scheme_buttons(self) -> None:
        if self.settings["projection"] and not self.show_presets:
            for ckey in ("primes", "gens"):
                if not self.tile_open("projection", ckey):
                    continue
                top = self.ptext_band_y("projection") + self.rows["projection"].ptext
                box_y = top + BOX_OUTER
                self.blocks.append(Block(f"block:scheme:{ckey}", self.col_x[ckey], box_y, self.col_w[ckey],
                                         BOX_INNER + SCHEME_BTN_SQ + CTRL_LABEL_GAP, boxed=True))
                self.emit_scheme_button(self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER, ckey)

    def _emit_ptext_band(self) -> None:
        if self.show_ptext:
            for (rkey, ckey), text in self.ptext_strings.items():
                if not self.tile_open(rkey, ckey):
                    continue
                if (rkey, ckey) == ("vectors", "commas") and self.pending is not None \
                        or (rkey, ckey) == ("vectors", "targets") and self.pending_target is not None \
                        or (rkey, ckey) == ("mapping", "primes") and self.pending_mapping_row is not None:
                    kind = "ptextpending"
                elif self.ptext_editable(rkey, ckey) and (ckey != "targets" or self.targets_editable):
                    kind = "ptextedit"
                else:
                    kind = "ptext"
                self.cells.append(CellBox(f"ptext:{rkey}:{ckey}", self.col_x[ckey], self.ptext_band_y(rkey),
                                     self.col_w[ckey], self.ptext_height(rkey, ckey), kind, text=text))

    def _emit_ebk_frames_and_marks(self) -> None:
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

    def _emit_tile_toggles(self) -> None:
        for _bid, rkey, ckey in self.tiles:
            if ((rkey, ckey) in self.declared_tiles
                    and rkey in self.rows and ckey in self.col_x and self.row_open(rkey) and self.col_open(ckey)):
                glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in self.collapsed)
                tog_x, _tw = self.tile_span_box(rkey, ckey)
                self.cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                     tog_x - PAD + TOGGLE_INSET, self.rows[rkey].tile_top - PAD + TOGGLE_INSET,
                                     TOGGLE, TOGGLE, "tiletoggle", text=glyph))

    def _apply_value_display_filters(self) -> None:
        if not self.gridded:
            self.cells = [cb for cb in self.cells if cb.kind not in GRIDDED_KINDS]
        elif not self.show_quantities:
            self.cells = [replace(cb, blank=True, text="") if cb.kind in BLANKED_NUMBER_KINDS else cb
                     for cb in self.cells]

        if (self.pending is not None or self.ghost_comma) and self.show_unchanged and self.nu:
            doomed_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, preview_remove=True)
                          if (cb.w == COL_W and cb.x == doomed_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

        if self.born_u:
            born_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, pending=True)
                          if (cb.w == COL_W and cb.x == born_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

        remove_rows = change_rows = remove_commas = change_commas = frozenset()
        if self.pending is not None and self.r:
            remove_rows, change_rows = frozenset({self.r - 1}), frozenset(range(self.r - 1))
        if self.pending_mapping_row is not None and self.nc:
            remove_commas, change_commas = frozenset({self.nc - 1}), frozenset(range(self.nc - 1))
        if self.preview_remove is not None:
            axis, idx = self.preview_remove
            if axis == "comma":
                remove_commas, change_rows = frozenset({idx}), frozenset(range(self.r))
            else:
                remove_rows, change_commas = frozenset({idx}), frozenset(range(self.nc))
        if remove_rows or change_rows or remove_commas or change_commas:
            red_xs = frozenset(self.comma_left(c) for c in remove_commas)
            amber_xs = frozenset(self.comma_left(c) for c in change_commas)
            def _dual(cb):
                if cb.kind not in RINGABLE_KINDS or cb.preview_remove:
                    return cb
                if cb.gen in remove_rows or cb.x in red_xs:
                    return replace(cb, preview_remove=True, pending=False)
                if cb.pending:
                    return cb
                if cb.gen in change_rows or cb.x in amber_xs:
                    return replace(cb, preview_change=True)
                return cb
            self.cells = [_dual(cb) for cb in self.cells]

    def layout(self) -> Layout:
        self.cells: list[CellBox] = []
        self.lines: list[Line] = []
        self.blocks: list[Block] = []
        self._control_region_boxes: list[Block] = []

        self._emit_headers()
        self._emit_counts_row()
        self._emit_units()
        self._emit_quantities_row()
        self._emit_column_plus_controls()
        self._emit_rehomed_minus_controls()
        self._emit_mapping_band()
        self._emit_projection_band()
        self._emit_canon_band()
        self._emit_vectors_band()
        self._emit_superspace_rows()
        self._emit_identity_objects()
        chart_indicators = self._emit_tuning_rows()
        self._emit_prescaling_band()
        self._emit_lbox_control()
        self._emit_cbox_controls()
        self._emit_complexity_row()
        self._emit_weight_row()
        self._emit_damage_row(chart_indicators)
        self._emit_charts(chart_indicators)
        gtm_box = self._emit_tuning_ranges_box()
        opt_box = self._emit_optimization_box()
        approach_frame = self._emit_approach_box()
        self._emit_brackets()
        self._emit_matrix_labels()
        self._emit_axes()
        self._emit_panels(gtm_box, opt_box, approach_frame)
        self._emit_washes()
        self._emit_symbols_captions()
        self._emit_presets()
        self._emit_all_interval_check_fallback()
        self._emit_form_choosers()
        self._emit_scheme_buttons()
        self._emit_ptext_band()
        self._emit_ebk_frames_and_marks()
        self._emit_tile_toggles()
        self._apply_value_display_filters()

        title_right = max((c.x + c.w / 2 + _title_w(c.text) / 2 for c in self.cells if c.kind == "colheader"),
                          default=self.total_w)
        right_overhang = max(0.0, title_right - self.total_w)

        return Layout(self.total_w, self.total_h, tuple(self.lines), tuple(self.blocks), tuple(self.cells),
                      freeze_x=self.node_edge + GAP - PAD, freeze_y=self.branch_top_y + GAP + GRIP_BAND - PAD,
                      right_overhang=right_overhang, identities=self._col_ids,
                      approach_box=self.approach_box)


def build(state, settings=None, collapsed=None, **inputs) -> Layout:
    return _GridBuilder(state, settings=settings, collapsed=collapsed, **inputs).layout()
