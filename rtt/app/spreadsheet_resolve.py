from __future__ import annotations

from types import SimpleNamespace

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_constants import (
    HEADER_H,
    LABEL_W,
    SYMBOL_H,
)
from rtt.app.spreadsheet_models import _resolve_prescaler_labels, _resolve_show_flags
from rtt.app.spreadsheet_resolved import freeze
from rtt.app.spreadsheet_text import _min_width_for_lines, assign_column_tokens


class Resolver:
    def __init__(self, state, settings=None, collapsed=None,
                 tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
                 pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
                 custom_prescaler=None, custom_weights=None, tuning_optimized=False,
                 pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, held_basis_ratios=(), displayed_projection_name=None,
                 targets_in_use=True, pending_mapping_row=None, preview_remove=None,
                 mapping_form=None, comma_basis_form=None, resolve_only=False):
        self._resolve_only = resolve_only
        self.prev_ids = prev_ids or {}
        self.mapping_form = mapping_form
        self.comma_basis_form = comma_basis_form
        self.preview_remove = preview_remove
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
        self._build(generator_tuning, target_override, held_vectors, pending_comma)

    def _build(self, generator_tuning, target_override, held_vectors, pending_comma) -> None:
        draft = SimpleNamespace()
        draft.ghost_row = (self.preview_remove is not None and self.preview_remove[0] == "comma"
                           and 0 <= self.preview_remove[1] < self.state.n)
        draft.ghost_comma = (self.preview_remove is not None and self.preview_remove[0] == "row"
                             and len(self.state.mapping) > 1 and 0 <= self.preview_remove[1] < len(self.state.mapping))
        if not (draft.ghost_row or draft.ghost_comma):
            self.preview_remove = None
        draft.displayed_tuning_name = self.displayed_tuning_name
        draft.displayed_projection_name = self.displayed_projection_name
        (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
         show_tuning, show_interest, show_interval_ratios) = self._unpack_show_flags(draft)
        label_w = LABEL_W
        header_h = HEADER_H
        self._resolve_superspace_dims(draft)
        self._resolve_prescaler_and_domain_labels(draft)
        self._resolve_interval_sets(draft, generator_tuning, target_override, held_vectors, pending_comma,
                                    show_temp, show_tuning)
        self._resolve_complexities(draft)
        self._resolve_detempering(draft)
        self._resolve_canon_mapped(draft)
        self._resolve_projection_data(draft, show_tuning)
        self.resolved = freeze(draft)
        if self._resolve_only:
            return

        interest_tiles, held_tiles, detempering_tiles = self._declare_interval_column_tiles()
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

    def _unpack_show_flags(self, draft):
        _f = _resolve_show_flags(self.settings, self.collapsed)
        draft.show_captions = _f.captions
        draft.show_mnemonics = _f.mnemonics
        draft.show_equiv = _f.equiv
        draft.show_presets = _f.presets
        show_counts = _f.counts
        draft.show_ptext = _f.ptext
        show_charts = _f.charts
        show_ranges = _f.ranges
        draft.show_symbols = _f.symbols
        draft.ctrl_symbol_h = SYMBOL_H if draft.show_symbols else 0
        draft.show_header_symbols = _f.header_symbols
        draft.show_units = _f.units
        draft.show_cell_units = _f.cell_units
        show_domain_units = _f.domain_units
        show_temp = _f.temp
        self.show_form = _f.form
        draft.show_form_controls = _f.form_controls
        self.show_form_tiles = _f.form_tiles
        show_tuning = _f.tuning
        draft.show_optimization = _f.optimization
        draft.show_weighting = _f.weighting
        draft.show_alt_complexity = _f.alt_complexity
        draft._complexity_shown = (draft.show_weighting
                                  and service.damage_weight_slope(self.tuning_scheme) != "unityWeight")
        draft._prescaling_shown = draft._complexity_shown and (
            service.is_all_interval(self.tuning_scheme) or draft.show_alt_complexity)
        draft.weight_unit = f"({service.weight_annotation(self.tuning_scheme)})"
        draft.complexity_unit = f"({service.complexity_annotation(self.tuning_scheme)})"
        draft.damage_unit = f"¢{draft.weight_unit}"
        draft._lbox_show = _f.lbox and draft._complexity_shown
        draft._cbox_show = _f.cbox and draft._complexity_shown
        draft.show_detempering = _f.detempering
        show_interest = _f.interest
        draft.gridded = _f.gridded
        draft.show_quantities = _f.quantities
        draft._decimals = _f.decimals
        draft.show_ebk = _f.ebk
        show_interval_ratios = _f.interval_ratios
        draft.show_interval_vectors = _f.interval_vectors
        draft.show_math = _f.math
        draft.custom_weights_active = (self.custom_weights is not None
                                      and not service.is_all_interval(self.tuning_scheme)
                                      and not draft.show_math)
        return (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
                show_tuning, show_interest, show_interval_ratios)

    def _resolve_superspace_dims(self, draft) -> None:
        draft.d = self.state.d
        draft.r = len(self.state.mapping)
        draft.row_draft = self.pending_mapping_row is not None or draft.ghost_row
        draft.r_shown = draft.r + (1 if draft.row_draft else 0)
        draft.elements = self.state.domain_basis
        draft.dL = service.superspace_dimension(draft.elements)
        draft.rL = service.superspace_rank(self.state)
        self._ss_tun = None
        draft.superspace_primes = service.superspace_primes(draft.elements)
        draft.show_nonstandard_domain = self.settings.get("nonstandard_domain", False)
        draft.show_superspace = (
            draft.show_nonstandard_domain
            and service.domain_has_nonprimes(draft.elements)
            and self.nonprime_approach != "nonprime-based"
        )
        draft.show_superspace_generators = draft.show_superspace and self.nonprime_approach == "prime-based"

    def _resolve_prescaler_and_domain_labels(self, draft) -> None:
        _p = _resolve_prescaler_labels(self.state, self.tuning_scheme, self.custom_prescaler,
                                       draft.show_equiv, draft.show_superspace)
        draft._scheme_prescaler = _p.scheme_prescaler
        draft._realized_prescaler = _p.realized
        draft.prescaler_symbol = _p.symbol
        draft.prescaler_equivalence = _p.equivalence
        draft.prescaling_symbols = _p.prescaling_symbols
        draft.col_labels = _p.col_labels
        draft.row_labels = _p.row_labels
        draft.effective_captions = _p.effective_captions
        draft.show_identity_objects = self.settings.get("identity_objects", False)
        draft.standard_domain = service.is_standard_domain(draft.elements)
        draft.domain_label = "b" if service.domain_has_nonprimes(draft.elements) else "p"
        draft.domain_can_shrink = service.can_shrink_domain(self.state)

    def _resolve_interval_sets(self, draft, generator_tuning, target_override, held_vectors, pending_comma,
                               show_temp, show_tuning) -> None:
        self._resolve_ghost_previews(draft)
        self._resolve_targets(draft, target_override)
        self._resolve_canon_form(draft)
        self._resolve_held(draft, held_vectors)
        self._resolve_tuning(draft, generator_tuning, target_override)
        self._resolve_commas(draft)
        self._resolve_unchanged(draft, pending_comma, show_temp, show_tuning)
        self._resolve_interest(draft)
        self._resolve_ghost_mapped(draft)
        self._resolve_col_ids(draft)

    def _resolve_ghost_previews(self, draft) -> None:
        draft.gens = service.generators(self.state.mapping, draft.elements)
        draft.ghost_new = None
        draft.ghost_row_map = draft.ghost_row_ratio = None
        draft.ghost_row_mapped = {}
        draft.ghost_comma_vec = draft.ghost_comma_ratio = None
        draft.ghost_comma_mapped = ()
        draft.ghost_comma_just = 0.0
        draft.ghost_comma_complexity = 0.0
        if draft.ghost_row:
            draft.ghost_new = service.remove_comma(self.state, self.preview_remove[1])
            draft.ghost_row_map = draft.ghost_new.mapping[-1]
            born_gens = service.generators(draft.ghost_new.mapping, draft.elements)
            draft.ghost_row_ratio = born_gens[-1] if born_gens else ""
        elif draft.ghost_comma:
            draft.ghost_new = service.remove_mapping_row(self.state, self.preview_remove[1])
            draft.ghost_comma_vec = draft.ghost_new.comma_basis[-1] if draft.ghost_new.comma_basis else None
            born_crs = service.comma_ratios(draft.ghost_new.comma_basis, draft.elements) if draft.ghost_new.comma_basis else ()
            draft.ghost_comma_ratio = born_crs[-1] if born_crs else ""

    def _resolve_targets(self, draft, target_override) -> None:
        draft.targets = service.displayed_targets(self.state, self.tuning_scheme, self.target_spec, target_override)
        draft.all_interval = service.is_all_interval(self.tuning_scheme)
        draft.targets_editable = not draft.all_interval
        draft.k = len(draft.targets)
        draft.pending_target = list(self.pending_target) if (self.pending_target is not None and draft.targets_editable) else None
        draft.k_shown = draft.k + (1 if draft.pending_target is not None else 0)
        draft.mapped = service.mapped_intervals(self.state.mapping, draft.targets, draft.elements)

    def _resolve_canon_form(self, draft) -> None:
        draft.canon_mapping = service.canonical_mapping(self.state.mapping)
        draft.rc = len(draft.canon_mapping)
        draft.form_M = service.form_matrix(self.state.mapping)
        draft.canon_gens = service.generators(draft.canon_mapping, draft.elements)
        draft.inverse_form_M = service.inverse_form_matrix(self.state.mapping)
        draft.mapping_form_key = service.resolve_mapping_form(
            self.state.mapping, self.mapping_form, self.state.domain_basis)
        draft.comma_basis_form_key = (
            service.resolve_comma_basis_form(self.state.comma_basis, self.comma_basis_form, self.state.domain_basis)
            if self.state.n else "")
        draft.form_is_canonical = draft.mapping_form_key == "canonical"
        draft.show_form_subscript = self.show_form and draft.form_is_canonical
        draft.show_canon = self.show_form_tiles and not draft.form_is_canonical

    def _resolve_held(self, draft, held_vectors) -> None:
        draft.target_vectors = service.target_interval_vectors(draft.targets, draft.d, draft.elements)
        draft.held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in held_vectors) if draft.show_optimization else ()
        draft.nh = len(draft.held)
        draft.pending_held = list(self.pending_held) if (self.pending_held is not None and draft.show_optimization) else None
        draft.nh_shown = draft.nh + (1 if draft.pending_held is not None else 0)
        draft.held_ratios = service.comma_ratios(draft.held, draft.elements)

    def _resolve_tuning(self, draft, generator_tuning, target_override) -> None:
        if generator_tuning is not None and len(generator_tuning) == len(self.state.mapping):
            draft.tun = service.tuning_from_generators(self.state.mapping, generator_tuning, draft.elements)
            draft._tun_from_generators = True
        else:
            draft.tun = service.tuning(self.state.mapping, self.tuning_scheme, draft.elements, self.nonprime_approach, held=draft.held_ratios,
                                 prescaler_override=self.custom_prescaler, targets=target_override,
                                 weights_override=self.custom_weights)
            draft._tun_from_generators = False
        draft._optimum_target_override = target_override
        draft.target_weights = service.interval_weights(self.state.mapping, self.tuning_scheme, draft.targets,
                                                  prescaler_override=self.custom_prescaler,
                                                  domain_basis=draft.elements,
                                                  weights_override=self.custom_weights)
        draft.target_sizes = service.interval_sizes(draft.tun, draft.targets, draft.elements, weights=draft.target_weights)
        draft.held_mapped = service.mapped_intervals(self.state.mapping, draft.held_ratios, draft.elements)
        draft.held_sizes = service.interval_sizes(draft.tun, draft.held_ratios, draft.elements)

    def _resolve_commas(self, draft) -> None:
        draft.comma_ratios = service.comma_ratios(self.state.comma_basis, draft.elements) if self.state.n else ()
        draft.nc = len(draft.comma_ratios)
        draft.mapped_commas = service.mapped_commas(self.state.mapping, self.state.comma_basis)
        draft.comma_sizes = service.interval_sizes(draft.tun, draft.comma_ratios, draft.elements)

    def _resolve_unchanged(self, draft, pending_comma, show_temp, show_tuning) -> None:
        _udata = (service.unchanged_interval_data(self.state, self.held_basis_ratios, draft.tun,
                                                  self.tuning_scheme, draft.elements, self.custom_prescaler)
                  if (show_temp and show_tuning and self.settings["projection"]) else None)
        draft.show_unchanged = _udata is not None
        draft.nu = len(_udata.basis) if draft.show_unchanged else 0
        if _udata is not None:
            draft.unchanged_basis, draft.unchanged_ratios = _udata.basis, _udata.ratios
            draft.unchanged_mapped, draft.unchanged_sizes = _udata.mapped, _udata.sizes
            draft.unchanged_complexities = _udata.complexities
        else:
            draft.unchanged_basis = None
            draft.unchanged_ratios = draft.unchanged_mapped = draft.unchanged_complexities = ()
            draft.unchanged_sizes = service.IntervalSizes((), (), (), ())
        draft.born_u = draft.ghost_row and draft.show_unchanged
        if draft.born_u:
            tun_new = service.tuning(draft.ghost_new.mapping, self.tuning_scheme, draft.elements,
                                     self.nonprime_approach, held=self.held_basis_ratios,
                                     prescaler_override=self.custom_prescaler)
            ud_new = service.unchanged_interval_data(draft.ghost_new, self.held_basis_ratios, tun_new,
                                                     self.tuning_scheme, draft.elements, self.custom_prescaler)
            if ud_new is not None and len(ud_new.basis) > draft.nu:
                bratio = ud_new.ratios[-1]
                bm = service.mapped_intervals(self.state.mapping, (bratio,), draft.elements) if bratio is not None else None
                draft.unchanged_basis = (*tuple(draft.unchanged_basis), ud_new.basis[-1])
                draft.unchanged_ratios = (*tuple(draft.unchanged_ratios), bratio)
                draft.unchanged_mapped = tuple((*tuple(row), bm[i][0] if bm is not None else None) for i, row in enumerate(draft.unchanged_mapped))
                draft.unchanged_complexities = (*tuple(draft.unchanged_complexities), ud_new.complexities[-1])
                s, n = draft.unchanged_sizes, ud_new.sizes
                draft.unchanged_sizes = service.IntervalSizes(
                    (*tuple(s.tempered), n.tempered[-1]), (*tuple(s.just), n.just[-1]),
                    (*tuple(s.errors), n.errors[-1]), (*tuple(s.damage), n.damage[-1]))
                draft.nu += 1
            else:
                draft.born_u = False
        draft.pending = (list(pending_comma)
                        if pending_comma is not None else None)
        draft.comma_draft = draft.pending is not None or draft.ghost_comma
        draft.nc_shown = draft.nc + (1 if draft.comma_draft else 0)
        draft.nv_shown = draft.nc_shown + draft.nu
        draft.empty_comma_w = (_min_width_for_lines("nullity", 1)
                              if (draft.show_unchanged and draft.nc_shown == 0) else 0)
        if draft.show_unchanged:
            for (rk, ck), name in list(draft.effective_captions.items()):
                if ck == "commas":
                    renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
                    if renamed.count("list") > 1:
                        renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
                    draft.effective_captions[(rk, ck)] = renamed

    def _resolve_interest(self, draft) -> None:
        draft.interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in self.interest)
        draft.mi = len(draft.interest)
        draft.pending_interest = list(self.pending_interest) if self.pending_interest is not None else None
        draft.mi_shown = draft.mi + (1 if draft.pending_interest is not None else 0)
        draft.element_draft = draft.show_nonstandard_domain and self.pending_element is not None
        draft.d_shown = draft.d + (1 if draft.element_draft else 0)
        draft.interest_ratios = service.comma_ratios(draft.interest, draft.elements)
        draft.interest_mapped = service.mapped_intervals(self.state.mapping, draft.interest_ratios, draft.elements)
        draft.interest_sizes = service.interval_sizes(draft.tun, draft.interest_ratios, draft.elements)

    def _resolve_ghost_mapped(self, draft) -> None:
        if draft.ghost_row and draft.ghost_new is not None:
            nm = draft.ghost_new.mapping
            def _newborn_mapped(ratios):
                return tuple(service.mapped_intervals(nm, (r,), draft.elements)[-1][0] if r is not None else None
                             for r in ratios)
            draft.ghost_row_mapped = {
                key: _newborn_mapped(ratios)
                for key, ratios in (("targets", draft.targets), ("interest", draft.interest_ratios),
                                    ("held", draft.held_ratios), ("commas", draft.comma_ratios),
                                    ("unchanged", draft.unchanged_ratios))}
        elif draft.ghost_comma and draft.ghost_comma_ratio:
            col = service.mapped_intervals(self.state.mapping, (draft.ghost_comma_ratio,), draft.elements)
            draft.ghost_comma_mapped = tuple(row[0] for row in col)
            draft.ghost_comma_just = service.interval_sizes(draft.tun, (draft.ghost_comma_ratio,), draft.elements).just[0]
            draft.ghost_comma_complexity = service.interval_complexities(
                self.state.mapping, self.tuning_scheme, (draft.ghost_comma_ratio,),
                prescaler_override=self.custom_prescaler, domain_basis=draft.elements)[0]

    def _resolve_col_ids(self, draft) -> None:
        draft._col_ids = {
            name: assign_column_tokens(self.prev_ids.get(name), keys, claim_unmatched=claim)
            for name, keys, claim in (("targets", draft.targets, False),
                                      ("held", draft.held_ratios, False),
                                      ("interest", draft.interest_ratios, False),
                                      ("commas", draft.comma_ratios, True),
                                      ("gens", tuple(tuple(row) for row in self.state.mapping), True))
        }
        draft._col_ids["detempering"] = draft._col_ids["gens"]

    def _resolve_complexities(self, draft) -> None:
        draft.complexities = {
            "primes": service.interval_complexities(self.state.mapping, self.tuning_scheme, tuple(service.element_ratio(e) for e in draft.elements),
                                                    prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
            "commas": service.interval_complexities(self.state.mapping, self.tuning_scheme, draft.comma_ratios,
                                                    prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
            "targets": service.interval_complexities(self.state.mapping, self.tuning_scheme, draft.targets,
                                                     prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
            "interest": service.interval_complexities(self.state.mapping, self.tuning_scheme, draft.interest_ratios,
                                                      prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
            "held": service.interval_complexities(self.state.mapping, self.tuning_scheme, draft.held_ratios,
                                                  prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
            "detempering": service.interval_complexities(self.state.mapping, self.tuning_scheme, draft.gens,
                                                         prescaler_override=self.custom_prescaler, domain_basis=draft.elements),
        }
        draft.prescaler = service.complexity_prescaler(self.state.mapping, self.tuning_scheme, override=self.custom_prescaler)
        draft.prescaler_is_matrix = isinstance(draft.prescaler[0], (tuple, list))

    def _resolve_detempering(self, draft) -> None:
        draft.detempering_vectors = (service.generator_detempering(self.state.mapping)
                                     if draft.show_detempering else ())
        draft.detempering_sizes = (service.interval_sizes(draft.tun, draft.gens, draft.elements)
                                   if draft.show_detempering else None)

    def _resolve_canon_mapped(self, draft) -> None:
        draft.canon_mapped = service.mapped_intervals(draft.canon_mapping, draft.targets, draft.elements)
        draft.canon_held_mapped = service.mapped_intervals(draft.canon_mapping, draft.held_ratios, draft.elements)
        draft.canon_interest_mapped = service.mapped_intervals(draft.canon_mapping, draft.interest_ratios, draft.elements)
        draft.canon_mapped_commas = service.mapped_commas(draft.canon_mapping, self.state.comma_basis)
        draft.canon_mapped_detempering = (service.mapped_commas(draft.canon_mapping, draft.detempering_vectors)
                                          if draft.show_detempering else ())
        _canon_u = [None if (draft.unchanged_basis is None or draft.unchanged_basis[j] is None)
                    else tuple(row[0] for row in service.mapped_commas(draft.canon_mapping, (draft.unchanged_basis[j],)))
                    for j in range(draft.nu)]
        draft.canon_unchanged_mapped = tuple(
            tuple((None if _canon_u[j] is None else _canon_u[j][i]) for j in range(draft.nu))
            for i in range(draft.rc))

    def _resolve_projection_data(self, draft, show_tuning) -> None:
        draft.show_projection = show_tuning and self.settings["projection"]
        if draft.show_projection:
            for rc in (("mapping", "gens"), ("ss_mapping", "ssgens")):
                cap = draft.effective_captions.get(rc)
                if cap and cap.endswith("generators"):
                    draft.effective_captions[rc] = cap[:-1] + "(s / embedding)"
        draft.projection_matrix = (service.tuning_projection(self.state, self.held_basis_ratios)
                                  if draft.show_projection else None)
        draft.embedding_matrix = (service.tuning_embedding(self.state, self.held_basis_ratios)
                                 if draft.show_projection else None)
        draft.canon_embedding_matrix = (service.canonical_generator_embedding(self.state, self.held_basis_ratios)
                                       if draft.show_projection else None)
        draft.projection_rationals = (service.projection_matrix_rationals(self.state, self.held_basis_ratios)
                                     if draft.show_projection else None)
        draft.proj_detempering = service.project_vectors(draft.projection_rationals, draft.detempering_vectors)
        draft.proj_held = service.project_vectors(draft.projection_rationals, draft.held)
        draft.proj_targets = service.project_vectors(draft.projection_rationals, draft.target_vectors)
        draft.proj_interest = service.project_vectors(draft.projection_rationals, draft.interest)
        draft.embedding_superspace = (service.superspace_generator_embedding_display(self.state, self.held_basis_ratios)
                                     if (draft.show_projection and draft.show_superspace) else None)
        draft.projection_superspace = (service.superspace_prime_projection_display(self.state, self.held_basis_ratios)
                                      if (draft.show_projection and draft.show_superspace) else None)
        draft.show_ss_projection = draft.show_projection and draft.show_superspace
        draft.ss_projection_matrix = (service.superspace_tuning_projection(self.state, self.held_basis_ratios)
                                     if draft.show_ss_projection else None)
        draft.ss_embedding_matrix = (service.superspace_tuning_embedding(self.state, self.held_basis_ratios)
                                    if draft.show_ss_projection else None)
        draft.ss_projection_rationals = (service.superspace_projection_matrix_rationals(self.state, self.held_basis_ratios)
                                        if draft.show_ss_projection else None)
        def _lift(vs):
            return service.lift_vectors_to_superspace(draft.elements, vs)
        _ssp = draft.ss_projection_rationals
        draft.ss_proj_basis = service.project_vectors(_ssp, service.basis_in_superspace(draft.elements))
        draft.ss_proj_detempering = service.project_vectors(_ssp, _lift(draft.detempering_vectors))
        draft.ss_proj_held = service.project_vectors(_ssp, _lift(draft.held))
        draft.ss_proj_targets = service.project_vectors(_ssp, _lift(draft.target_vectors))
        draft.ss_proj_interest = service.project_vectors(_ssp, _lift(draft.interest))
        draft.ss_unchanged = tuple(
            (service.lift_vectors_to_superspace(draft.elements, (ub,))[0] if ub is not None else None)
            for ub in (draft.unchanged_basis if draft.show_unchanged else ()))
        draft.ss_unchanged_mapped = tuple(
            (service.map_vectors_into_superspace_generators(self.state, (ub,))[0] if ub is not None else None)
            for ub in (draft.unchanged_basis if draft.show_unchanged else ()))
