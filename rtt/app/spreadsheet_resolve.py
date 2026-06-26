from __future__ import annotations

from dataclasses import replace
from typing import NamedTuple

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_layout import compute_geometry
from rtt.app.spreadsheet_resolve_draft import ResolveDraft
from rtt.app.spreadsheet_resolve_inputs import make_inputs
from rtt.app.spreadsheet_resolve_steps import (
    resolve_prescaler_and_domain_labels,
    resolve_superspace_dims,
    unpack_show_flags,
)
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
        self.generator_tuning = generator_tuning
        self.target_override = target_override

        if self.settings is None:
            self.settings = _default_settings()
        if self.tuning_scheme is None:
            self.tuning_scheme = service.DEFAULT_DOCUMENT_SCHEME
        if self.target_spec is None:
            self.target_spec = service.DEFAULT_TARGET_SPEC
        self.collapsed = self.collapsed or frozenset()
        self._build(generator_tuning, target_override, held_vectors, pending_comma)

    def _build(self, generator_tuning, target_override, held_vectors, pending_comma) -> None:
        ghost_row = (self.preview_remove is not None and self.preview_remove[0] == "comma"
                     and 0 <= self.preview_remove[1] < self.state.n)
        ghost_comma = (self.preview_remove is not None and self.preview_remove[0] == "row"
                       and len(self.state.mapping) > 1 and 0 <= self.preview_remove[1] < len(self.state.mapping))
        if not (ghost_row or ghost_comma):
            self.preview_remove = None
        inputs = make_inputs(self, held_vectors, pending_comma)
        draft = ResolveDraft(ghost_row=ghost_row, ghost_comma=ghost_comma,
                             displayed_tuning_name=self.displayed_tuning_name,
                             displayed_projection_name=self.displayed_projection_name)
        draft = unpack_show_flags(inputs, draft)
        draft = resolve_superspace_dims(inputs, draft)
        draft = resolve_prescaler_and_domain_labels(inputs, draft)
        draft = self._resolve_interval_sets(draft, generator_tuning, target_override, held_vectors, pending_comma)
        draft = self._resolve_complexities(draft)
        draft = self._resolve_detempering(draft)
        draft = self._resolve_canon_mapped(draft)
        draft = self._resolve_projection_data(draft)
        self.resolved = freeze(draft)
        if self._resolve_only:
            return

        self.geometry = compute_geometry(self.resolved, build_context(self))

    def _resolve_interval_sets(self, draft, generator_tuning, target_override, held_vectors, pending_comma):
        draft = self._resolve_ghost_previews(draft)
        draft = self._resolve_targets(draft, target_override)
        draft = self._resolve_canon_form(draft)
        draft = self._resolve_held(draft, held_vectors)
        draft = self._resolve_tuning(draft, generator_tuning, target_override)
        draft = self._resolve_commas(draft)
        draft = self._resolve_unchanged(draft, pending_comma)
        draft = self._resolve_interest(draft)
        draft = self._resolve_ghost_mapped(draft)
        return self._resolve_col_ids(draft)

    def _resolve_ghost_previews(self, draft):
        elements = draft.elements
        ghost_new = ghost_row_map = ghost_row_ratio = None
        ghost_comma_vec = ghost_comma_ratio = None
        if draft.ghost_row:
            ghost_new = service.remove_comma(self.state, self.preview_remove[1])
            ghost_row_map = ghost_new.mapping[-1]
            born_gens = service.generators(ghost_new.mapping, elements)
            ghost_row_ratio = born_gens[-1] if born_gens else ""
        elif draft.ghost_comma:
            ghost_new = service.remove_mapping_row(self.state, self.preview_remove[1])
            ghost_comma_vec = ghost_new.comma_basis[-1] if ghost_new.comma_basis else None
            born_crs = service.comma_ratios(ghost_new.comma_basis, elements) if ghost_new.comma_basis else ()
            ghost_comma_ratio = born_crs[-1] if born_crs else ""
        return replace(
            draft, gens=service.generators(self.state.mapping, elements), ghost_new=ghost_new,
            ghost_row_map=ghost_row_map, ghost_row_ratio=ghost_row_ratio, ghost_row_mapped={},
            ghost_comma_vec=ghost_comma_vec, ghost_comma_ratio=ghost_comma_ratio,
            ghost_comma_mapped=(), ghost_comma_just=0.0, ghost_comma_complexity=0.0)

    def _resolve_targets(self, draft, target_override):
        targets = service.displayed_targets(self.state, self.tuning_scheme, self.target_spec, target_override)
        all_interval = service.is_all_interval(self.tuning_scheme)
        targets_editable = not all_interval
        k = len(targets)
        pending_target = list(self.pending_target) if (self.pending_target is not None and targets_editable) else None
        return replace(
            draft, targets=targets, all_interval=all_interval, targets_editable=targets_editable, k=k,
            pending_target=pending_target, k_shown=k + (1 if pending_target is not None else 0),
            mapped=service.mapped_intervals(self.state.mapping, targets, draft.elements))

    def _resolve_canon_form(self, draft):
        canon_mapping = service.canonical_mapping(self.state.mapping)
        mapping_form_key = service.resolve_mapping_form(
            self.state.mapping, self.mapping_form, self.state.domain_basis)
        form_is_canonical = mapping_form_key == "canonical"
        return replace(
            draft, canon_mapping=canon_mapping, rc=len(canon_mapping),
            form_M=service.form_matrix(self.state.mapping),
            canon_gens=service.generators(canon_mapping, draft.elements),
            inverse_form_M=service.inverse_form_matrix(self.state.mapping),
            mapping_form_key=mapping_form_key,
            comma_basis_form_key=(service.resolve_comma_basis_form(
                self.state.comma_basis, self.comma_basis_form, self.state.domain_basis) if self.state.n else ""),
            form_is_canonical=form_is_canonical,
            show_form_subscript=draft.show_form and form_is_canonical,
            show_canon=draft.show_form_tiles and not form_is_canonical)

    def _resolve_held(self, draft, held_vectors):
        held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in held_vectors) if draft.show_optimization else ()
        nh = len(held)
        pending_held = list(self.pending_held) if (self.pending_held is not None and draft.show_optimization) else None
        return replace(
            draft, target_vectors=service.target_interval_vectors(draft.targets, draft.d, draft.elements),
            held=held, nh=nh, pending_held=pending_held, nh_shown=nh + (1 if pending_held is not None else 0),
            held_ratios=service.comma_ratios(held, draft.elements))

    def _resolve_tuning(self, draft, generator_tuning, target_override):
        if generator_tuning is not None and len(generator_tuning) == len(self.state.mapping):
            tun = service.tuning_from_generators(self.state.mapping, generator_tuning, draft.elements)
            from_generators = True
        else:
            tun = service.tuning(self.state.mapping, self.tuning_scheme, draft.elements, self.nonprime_approach, held=draft.held_ratios,
                                 prescaler_override=self.custom_prescaler, targets=target_override,
                                 weights_override=self.custom_weights)
            from_generators = False
        target_weights = service.interval_weights(self.state.mapping, self.tuning_scheme, draft.targets,
                                                  prescaler_override=self.custom_prescaler,
                                                  domain_basis=draft.elements, weights_override=self.custom_weights)
        return replace(
            draft, tun=tun, _tun_from_generators=from_generators, _optimum_target_override=target_override,
            target_weights=target_weights,
            target_sizes=service.interval_sizes(tun, draft.targets, draft.elements, weights=target_weights),
            held_mapped=service.mapped_intervals(self.state.mapping, draft.held_ratios, draft.elements),
            held_sizes=service.interval_sizes(tun, draft.held_ratios, draft.elements))

    def _resolve_commas(self, draft):
        comma_ratios = service.comma_ratios(self.state.comma_basis, draft.elements) if self.state.n else ()
        return replace(
            draft, comma_ratios=comma_ratios, nc=len(comma_ratios),
            mapped_commas=service.mapped_commas(self.state.mapping, self.state.comma_basis),
            comma_sizes=service.interval_sizes(draft.tun, comma_ratios, draft.elements))

    def _resolve_unchanged(self, draft, pending_comma):
        _udata = (service.unchanged_interval_data(self.state, self.held_basis_ratios, draft.tun,
                                                  self.tuning_scheme, draft.elements, self.custom_prescaler)
                  if (draft.show_temp and draft.show_tuning and self.settings["projection"]) else None)
        unchanged = _initial_unchanged(_udata)
        nu = len(_udata.basis) if _udata is not None else 0
        born_u = draft.ghost_row and _udata is not None
        if born_u:
            unchanged, nu, born_u = self._augment_born_unchanged(draft, unchanged, nu)
        pending = list(pending_comma) if pending_comma is not None else None
        comma_draft = pending is not None or draft.ghost_comma
        nc_shown = draft.nc + (1 if comma_draft else 0)
        if _udata is not None:
            _rename_commas_to_unrotated(draft.effective_captions)
        return replace(
            draft, show_unchanged=_udata is not None, nu=nu, born_u=born_u,
            unchanged_basis=unchanged.basis, unchanged_ratios=unchanged.ratios,
            unchanged_mapped=unchanged.mapped, unchanged_sizes=unchanged.sizes,
            unchanged_complexities=unchanged.complexities, pending=pending, comma_draft=comma_draft,
            nc_shown=nc_shown, nv_shown=nc_shown + nu,
            empty_comma_w=(_min_width_for_lines("nullity", 1) if (_udata is not None and nc_shown == 0) else 0))

    def _augment_born_unchanged(self, draft, unchanged, nu):
        tun_new = service.tuning(draft.ghost_new.mapping, self.tuning_scheme, draft.elements,
                                 self.nonprime_approach, held=self.held_basis_ratios,
                                 prescaler_override=self.custom_prescaler)
        ud_new = service.unchanged_interval_data(draft.ghost_new, self.held_basis_ratios, tun_new,
                                                 self.tuning_scheme, draft.elements, self.custom_prescaler)
        if ud_new is None or len(ud_new.basis) <= nu:
            return unchanged, nu, False
        bratio = ud_new.ratios[-1]
        bm = service.mapped_intervals(self.state.mapping, (bratio,), draft.elements) if bratio is not None else None
        s, n = unchanged.sizes, ud_new.sizes
        grown = _Unchanged(
            basis=(*tuple(unchanged.basis), ud_new.basis[-1]),
            ratios=(*tuple(unchanged.ratios), bratio),
            mapped=tuple((*tuple(row), bm[i][0] if bm is not None else None) for i, row in enumerate(unchanged.mapped)),
            sizes=service.IntervalSizes(
                (*tuple(s.tempered), n.tempered[-1]), (*tuple(s.just), n.just[-1]),
                (*tuple(s.errors), n.errors[-1]), (*tuple(s.damage), n.damage[-1])),
            complexities=(*tuple(unchanged.complexities), ud_new.complexities[-1]))
        return grown, nu + 1, True

    def _resolve_interest(self, draft):
        interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(draft.d)) for m in self.interest)
        mi = len(interest)
        pending_interest = list(self.pending_interest) if self.pending_interest is not None else None
        element_draft = draft.show_nonstandard_domain and self.pending_element is not None
        interest_ratios = service.comma_ratios(interest, draft.elements)
        return replace(
            draft, interest=interest, mi=mi, pending_interest=pending_interest,
            mi_shown=mi + (1 if pending_interest is not None else 0), element_draft=element_draft,
            d_shown=draft.d + (1 if element_draft else 0), interest_ratios=interest_ratios,
            interest_mapped=service.mapped_intervals(self.state.mapping, interest_ratios, draft.elements),
            interest_sizes=service.interval_sizes(draft.tun, interest_ratios, draft.elements))

    def _resolve_ghost_mapped(self, draft):
        if draft.ghost_row and draft.ghost_new is not None:
            nm = draft.ghost_new.mapping

            def _newborn_mapped(ratios):
                return tuple(service.mapped_intervals(nm, (r,), draft.elements)[-1][0] if r is not None else None
                             for r in ratios)
            return replace(draft, ghost_row_mapped={
                key: _newborn_mapped(ratios)
                for key, ratios in (("targets", draft.targets), ("interest", draft.interest_ratios),
                                    ("held", draft.held_ratios), ("commas", draft.comma_ratios),
                                    ("unchanged", draft.unchanged_ratios))})
        if draft.ghost_comma and draft.ghost_comma_ratio:
            col = service.mapped_intervals(self.state.mapping, (draft.ghost_comma_ratio,), draft.elements)
            return replace(
                draft, ghost_comma_mapped=tuple(row[0] for row in col),
                ghost_comma_just=service.interval_sizes(draft.tun, (draft.ghost_comma_ratio,), draft.elements).just[0],
                ghost_comma_complexity=service.interval_complexities(
                    self.state.mapping, self.tuning_scheme, (draft.ghost_comma_ratio,),
                    prescaler_override=self.custom_prescaler, domain_basis=draft.elements)[0])
        return draft

    def _resolve_col_ids(self, draft):
        col_ids = {
            name: assign_column_tokens(self.prev_ids.get(name), keys, claim_unmatched=claim)
            for name, keys, claim in (("targets", draft.targets, False),
                                      ("held", draft.held_ratios, False),
                                      ("interest", draft.interest_ratios, False),
                                      ("commas", draft.comma_ratios, True),
                                      ("gens", tuple(tuple(row) for row in self.state.mapping), True))
        }
        col_ids["detempering"] = col_ids["gens"]
        return replace(draft, _col_ids=col_ids)

    def _resolve_complexities(self, draft):
        def _cx(intervals):
            return service.interval_complexities(self.state.mapping, self.tuning_scheme, intervals,
                                                 prescaler_override=self.custom_prescaler, domain_basis=draft.elements)
        complexities = {
            "primes": _cx(tuple(service.element_ratio(e) for e in draft.elements)),
            "commas": _cx(draft.comma_ratios),
            "targets": _cx(draft.targets),
            "interest": _cx(draft.interest_ratios),
            "held": _cx(draft.held_ratios),
            "detempering": _cx(draft.gens),
        }
        prescaler = service.complexity_prescaler(self.state.mapping, self.tuning_scheme, override=self.custom_prescaler)
        return replace(draft, complexities=complexities, prescaler=prescaler,
                       prescaler_is_matrix=isinstance(prescaler[0], (tuple, list)))

    def _resolve_detempering(self, draft):
        return replace(
            draft,
            detempering_vectors=(service.generator_detempering(self.state.mapping) if draft.show_detempering else ()),
            detempering_sizes=(service.interval_sizes(draft.tun, draft.gens, draft.elements) if draft.show_detempering else None))

    def _resolve_canon_mapped(self, draft):
        canon_mapping = draft.canon_mapping
        _canon_u = [None if (draft.unchanged_basis is None or draft.unchanged_basis[j] is None)
                    else tuple(row[0] for row in service.mapped_commas(canon_mapping, (draft.unchanged_basis[j],)))
                    for j in range(draft.nu)]
        canon_unchanged_mapped = tuple(
            tuple((None if _canon_u[j] is None else _canon_u[j][i]) for j in range(draft.nu))
            for i in range(draft.rc))
        return replace(
            draft, canon_mapped=service.mapped_intervals(canon_mapping, draft.targets, draft.elements),
            canon_held_mapped=service.mapped_intervals(canon_mapping, draft.held_ratios, draft.elements),
            canon_interest_mapped=service.mapped_intervals(canon_mapping, draft.interest_ratios, draft.elements),
            canon_mapped_commas=service.mapped_commas(canon_mapping, self.state.comma_basis),
            canon_mapped_detempering=(service.mapped_commas(canon_mapping, draft.detempering_vectors) if draft.show_detempering else ()),
            canon_unchanged_mapped=canon_unchanged_mapped)

    def _resolve_projection_data(self, draft):
        show_projection = draft.show_tuning and self.settings["projection"]
        if show_projection:
            _embed_generators_caption(draft.effective_captions)
        rationals = (service.projection_matrix_rationals(self.state, self.held_basis_ratios)
                     if show_projection else None)
        show_ss = show_projection and draft.show_superspace
        ss_rationals = (service.superspace_projection_matrix_rationals(self.state, self.held_basis_ratios)
                        if show_ss else None)

        def _lift(vs):
            return service.lift_vectors_to_superspace(draft.elements, vs)

        def _ss_lift(ub):
            return service.lift_vectors_to_superspace(draft.elements, (ub,))[0] if ub is not None else None

        def _ss_map(ub):
            return service.map_vectors_into_superspace_generators(self.state, (ub,))[0] if ub is not None else None

        unchanged_basis = draft.unchanged_basis if draft.show_unchanged else ()
        return replace(
            draft, show_projection=show_projection, show_ss_projection=show_ss,
            projection_matrix=(service.tuning_projection(self.state, self.held_basis_ratios) if show_projection else None),
            embedding_matrix=(service.tuning_embedding(self.state, self.held_basis_ratios) if show_projection else None),
            canon_embedding_matrix=(service.canonical_generator_embedding(self.state, self.held_basis_ratios) if show_projection else None),
            projection_rationals=rationals,
            proj_detempering=service.project_vectors(rationals, draft.detempering_vectors),
            proj_held=service.project_vectors(rationals, draft.held),
            proj_targets=service.project_vectors(rationals, draft.target_vectors),
            proj_interest=service.project_vectors(rationals, draft.interest),
            embedding_superspace=(service.superspace_generator_embedding_display(self.state, self.held_basis_ratios) if show_ss else None),
            projection_superspace=(service.superspace_prime_projection_display(self.state, self.held_basis_ratios) if show_ss else None),
            ss_projection_matrix=(service.superspace_tuning_projection(self.state, self.held_basis_ratios) if show_ss else None),
            ss_embedding_matrix=(service.superspace_tuning_embedding(self.state, self.held_basis_ratios) if show_ss else None),
            ss_projection_rationals=ss_rationals,
            ss_proj_basis=service.project_vectors(ss_rationals, service.basis_in_superspace(draft.elements)),
            ss_proj_detempering=service.project_vectors(ss_rationals, _lift(draft.detempering_vectors)),
            ss_proj_held=service.project_vectors(ss_rationals, _lift(draft.held)),
            ss_proj_targets=service.project_vectors(ss_rationals, _lift(draft.target_vectors)),
            ss_proj_interest=service.project_vectors(ss_rationals, _lift(draft.interest)),
            ss_unchanged=tuple(_ss_lift(ub) for ub in unchanged_basis),
            ss_unchanged_mapped=tuple(_ss_map(ub) for ub in unchanged_basis))


class _Unchanged(NamedTuple):
    basis: object
    ratios: object
    mapped: object
    sizes: object
    complexities: object


def _initial_unchanged(udata):
    if udata is not None:
        return _Unchanged(udata.basis, udata.ratios, udata.mapped, udata.sizes, udata.complexities)
    return _Unchanged(None, (), (), service.IntervalSizes((), (), (), ()), ())


def _rename_commas_to_unrotated(effective_captions):
    for (rk, ck), name in list(effective_captions.items()):
        if ck != "commas":
            continue
        renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
        if renamed.count("list") > 1:
            renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
        effective_captions[(rk, ck)] = renamed


def _embed_generators_caption(effective_captions):
    for rc in (("mapping", "gens"), ("ss_mapping", "ssgens")):
        cap = effective_captions.get(rc)
        if cap and cap.endswith("generators"):
            effective_captions[rc] = cap[:-1] + "(s / embedding)"
