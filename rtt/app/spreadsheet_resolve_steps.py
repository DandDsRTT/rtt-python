from __future__ import annotations

from dataclasses import replace
from typing import NamedTuple

from rtt.app import service
from rtt.app.spreadsheet_constants import SYMBOL_H
from rtt.app.spreadsheet_models import _resolve_prescaler_labels, _resolve_show_flags


class Ghosts(NamedTuple):
    ghost_row: bool
    ghost_comma: bool
    preview_remove: object


def determine_ghosts(inputs) -> Ghosts:
    pr = inputs.preview_remove
    ghost_row = (pr is not None and pr[0] == "comma"
                 and 0 <= pr[1] < inputs.state.n)
    ghost_comma = (pr is not None and pr[0] == "row"
                   and len(inputs.state.mapping) > 1 and 0 <= pr[1] < len(inputs.state.mapping))
    return Ghosts(ghost_row, ghost_comma, pr if (ghost_row or ghost_comma) else None)


def unpack_show_flags(inputs, draft):
    _f = _resolve_show_flags(inputs.settings, inputs.collapsed)
    show_symbols, show_weighting, show_math = _f.symbols, _f.weighting, _f.math
    complexity_shown = (show_weighting
                        and service.damage_weight_slope(inputs.tuning_scheme) != "unityWeight")
    prescaling_shown = complexity_shown and (
        service.is_all_interval(inputs.tuning_scheme) or _f.alt_complexity)
    weight_unit = f"({service.weight_annotation(inputs.tuning_scheme)})"
    return replace(
        draft, show_names=_f.names, show_mnemonics=_f.mnemonics, show_equiv=_f.equiv,
        show_presets=_f.presets, show_counts=_f.counts, show_ptext=_f.ptext, show_charts=_f.charts,
        show_ranges=_f.ranges, show_symbols=show_symbols, ctrl_symbol_h=SYMBOL_H if show_symbols else 0,
        show_header_symbols=_f.header_symbols, show_units=_f.units, show_cell_units=_f.cell_units,
        show_domain_units=_f.domain_units, show_temp=_f.temp, show_form=_f.form,
        show_form_controls=_f.form_controls, show_form_tiles=_f.form_tiles, show_tuning=_f.tuning,
        show_optimization=_f.optimization, show_weighting=show_weighting,
        show_alt_complexity=_f.alt_complexity, _complexity_shown=complexity_shown,
        _prescaling_shown=prescaling_shown, weight_unit=weight_unit,
        complexity_unit=f"({service.complexity_annotation(inputs.tuning_scheme)})",
        damage_unit=f"¢{weight_unit}", _lbox_show=_f.lbox and complexity_shown,
        _cbox_show=_f.cbox and complexity_shown, show_detempering=_f.detempering,
        show_interest=_f.interest, gridded=_f.gridded, show_quantities=_f.quantities,
        _decimals=_f.decimals, show_ebk=_f.ebk, show_interval_ratios=_f.interval_ratios,
        show_interval_vectors=_f.interval_vectors, show_math=show_math,
        dd_terminology=inputs.settings.get("dd_terminology", True),
        custom_weights_active=(inputs.custom_weights is not None
                               and not service.is_all_interval(inputs.tuning_scheme)
                               and not show_math))


def resolve_superspace_dims(inputs, draft):
    elements = inputs.state.domain_basis
    r = len(inputs.state.mapping)
    row_draft = inputs.pending_mapping_row is not None or draft.ghost_row
    show_nonstandard_domain = inputs.settings.get("nonstandard_domain", False)
    show_superspace = (show_nonstandard_domain
                       and service.domain_has_nonprimes(elements)
                       and inputs.nonprime_approach != "nonprime-based")
    return replace(
        draft, d=inputs.state.d, r=r, row_draft=row_draft, r_shown=r + (1 if row_draft else 0),
        elements=elements, dL=service.superspace_dimension(elements),
        rL=service.superspace_rank(inputs.state), superspace_primes=service.superspace_primes(elements),
        show_nonstandard_domain=show_nonstandard_domain, show_superspace=show_superspace,
        show_superspace_generators=show_superspace and inputs.nonprime_approach == "prime-based")


def resolve_prescaler_and_domain_labels(inputs, draft):
    _p = _resolve_prescaler_labels(inputs.state, inputs.tuning_scheme, inputs.custom_prescaler,
                                   draft.show_equiv, draft.show_superspace)
    return replace(
        draft, _scheme_prescaler=_p.scheme_prescaler, _realized_prescaler=_p.realized,
        prescaler_symbol=_p.symbol, prescaler_equivalence=_p.equivalence,
        prescaling_symbols=_p.prescaling_symbols, col_labels=_p.col_labels, row_labels=_p.row_labels,
        effective_captions=_p.effective_captions,
        show_identity_objects=inputs.settings.get("identity_objects", False),
        standard_domain=service.is_standard_domain(draft.elements),
        domain_label="b" if service.domain_has_nonprimes(draft.elements) else "p",
        domain_can_shrink=service.can_shrink_domain(inputs.state))


def resolve_complexities(inputs, draft):
    def _cx(intervals):
        return service.interval_complexities(inputs.state.mapping, inputs.tuning_scheme, intervals,
                                             prescaler_override=inputs.custom_prescaler, domain_basis=draft.elements)
    complexities = {
        "primes": _cx(tuple(service.element_ratio(e) for e in draft.elements)),
        "commas": _cx(draft.comma_ratios),
        "targets": _cx(draft.targets),
        "interest": _cx(draft.interest_ratios),
        "held": _cx(draft.held_ratios),
        "detempering": _cx(draft.gens),
    }
    prescaler = service.complexity_prescaler(inputs.state.mapping, inputs.tuning_scheme, override=inputs.custom_prescaler)
    return replace(draft, complexities=complexities, prescaler=prescaler,
                   prescaler_is_matrix=isinstance(prescaler[0], (tuple, list)))


def resolve_detempering(inputs, draft):
    return replace(
        draft,
        detempering_vectors=(service.generator_detempering(inputs.state.mapping) if draft.show_detempering else ()),
        detempering_sizes=(service.interval_sizes(draft.tun, draft.gens, draft.elements) if draft.show_detempering else None))


def resolve_canon_mapped(inputs, draft):
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
        canon_mapped_commas=service.mapped_commas(canon_mapping, inputs.state.comma_basis),
        canon_mapped_detempering=(service.mapped_commas(canon_mapping, draft.detempering_vectors) if draft.show_detempering else ()),
        canon_unchanged_mapped=canon_unchanged_mapped)


def resolve_projection_data(inputs, draft):
    show_projection = draft.show_tuning and inputs.settings["projection"]
    if show_projection:
        _embed_generators_caption(draft.effective_captions)
    rationals = (service.projection_matrix_rationals(inputs.state, inputs.held_basis_ratios)
                 if show_projection else None)
    show_ss = show_projection and draft.show_superspace
    ss_rationals = (service.superspace_projection_matrix_rationals(inputs.state, inputs.held_basis_ratios)
                    if show_ss else None)

    def _lift(vs):
        return service.lift_vectors_to_superspace(draft.elements, vs)

    def _ss_lift(ub):
        return service.lift_vectors_to_superspace(draft.elements, (ub,))[0] if ub is not None else None

    def _ss_map(ub):
        return service.map_vectors_into_superspace_generators(inputs.state, (ub,))[0] if ub is not None else None

    unchanged_basis = draft.unchanged_basis if draft.show_unchanged else ()
    return replace(
        draft, show_projection=show_projection, show_ss_projection=show_ss,
        projection_matrix=(service.tuning_projection(inputs.state, inputs.held_basis_ratios) if show_projection else None),
        embedding_matrix=(service.tuning_embedding(inputs.state, inputs.held_basis_ratios) if show_projection else None),
        canon_embedding_matrix=(service.canonical_generator_embedding(inputs.state, inputs.held_basis_ratios) if show_projection else None),
        projection_rationals=rationals,
        proj_detempering=service.project_vectors(rationals, draft.detempering_vectors),
        proj_held=service.project_vectors(rationals, draft.held),
        proj_targets=service.project_vectors(rationals, draft.target_vectors),
        proj_interest=service.project_vectors(rationals, draft.interest),
        embedding_superspace=(service.superspace_generator_embedding_display(inputs.state, inputs.held_basis_ratios) if show_ss else None),
        projection_superspace=(service.superspace_prime_projection_display(inputs.state, inputs.held_basis_ratios) if show_ss else None),
        ss_projection_matrix=(service.superspace_tuning_projection(inputs.state, inputs.held_basis_ratios) if show_ss else None),
        ss_embedding_matrix=(service.superspace_tuning_embedding(inputs.state, inputs.held_basis_ratios) if show_ss else None),
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
