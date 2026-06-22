from __future__ import annotations

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_constants import (
    APPROACH_RADIO_H,
    BOX_INNER,
    BOX_TITLE_GAP,
    BOX_TITLE_H,
    CAPTION_LINE,
    HEADER_H,
    LABEL_W,
    OPT_MEAN_DAMAGE_W,
    OPT_PAD_B,
    OPT_PAD_T,
    OPT_TITLE_GAP,
    OPT_TITLE_H,
    OPTION_BOX_PX,
    PRESET_H,
    RANGE_CHART_H,
    RANGE_GAP,
    RANGE_MODE_H,
    ROW_H,
    SYMBOL_H,
)
from rtt.app.spreadsheet_models import _resolve_prescaler_labels, _resolve_show_flags
from rtt.app.spreadsheet_text import _min_width_for_lines, _wrap_lines, assign_column_tokens


class _ResolveMixin:
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
