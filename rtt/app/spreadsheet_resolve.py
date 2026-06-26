from __future__ import annotations

from dataclasses import replace

from rtt.app import service
from rtt.app.settings import defaults as _default_settings
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_layout import compute_geometry
from rtt.app.spreadsheet_resolve_draft import ResolveDraft
from rtt.app.spreadsheet_resolve_inputs import make_inputs
from rtt.app.spreadsheet_resolve_intervals import resolve_interval_sets
from rtt.app.spreadsheet_resolve_steps import (
    resolve_prescaler_and_domain_labels,
    resolve_superspace_dims,
    unpack_show_flags,
)
from rtt.app.spreadsheet_resolved import freeze


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
        self._build(held_vectors, pending_comma)

    def _build(self, held_vectors, pending_comma) -> None:
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
        draft = resolve_interval_sets(inputs, draft)
        draft = self._resolve_complexities(draft)
        draft = self._resolve_detempering(draft)
        draft = self._resolve_canon_mapped(draft)
        draft = self._resolve_projection_data(draft)
        self.resolved = freeze(draft)
        if self._resolve_only:
            return

        self.geometry = compute_geometry(self.resolved, build_context(self))

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


def _embed_generators_caption(effective_captions):
    for rc in (("mapping", "gens"), ("ss_mapping", "ssgens")):
        cap = effective_captions.get(rc)
        if cap and cap.endswith("generators"):
            effective_captions[rc] = cap[:-1] + "(s / embedding)"
