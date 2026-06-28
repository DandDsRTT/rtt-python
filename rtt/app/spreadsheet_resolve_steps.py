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
    show_flags = _resolve_show_flags(inputs.settings, inputs.collapsed)
    show_symbols, show_weighting, show_math_expressions = show_flags.symbols, show_flags.weighting, show_flags.math_expressions
    complexity_shown = (show_weighting
                        and service.damage_weight_slope(inputs.tuning_scheme) != "unityWeight")
    prescaling_shown = complexity_shown and (
        service.is_all_interval(inputs.tuning_scheme) or show_flags.alt_complexity)
    weight_unit = f"({service.weight_annotation(inputs.tuning_scheme)})"
    return replace(
        draft, show_names=show_flags.names, show_mnemonics=show_flags.mnemonics, show_equivalences=show_flags.equivalences,
        show_presets=show_flags.presets, show_counts=show_flags.counts, show_plain_text_values=show_flags.plain_text_values, show_charts=show_flags.charts,
        show_tuning_ranges=show_flags.tuning_ranges, show_symbols=show_symbols, ctrl_symbol_h=SYMBOL_H if show_symbols else 0,
        show_header_symbols=show_flags.header_symbols, show_units=show_flags.units, show_cell_units=show_flags.cell_units,
        show_domain_units=show_flags.domain_units, show_temperament_tiles=show_flags.temperament_tiles, show_form=show_flags.form,
        show_form_controls=show_flags.form_controls, show_form_tiles=show_flags.form_tiles, show_tuning_tiles=show_flags.tuning_tiles,
        show_optimization=show_flags.optimization, show_weighting=show_weighting,
        show_alt_complexity=show_flags.alt_complexity, _complexity_shown=complexity_shown,
        _prescaling_shown=prescaling_shown, weight_unit=weight_unit,
        complexity_unit=f"({service.complexity_annotation(inputs.tuning_scheme)})",
        damage_unit=f"¢{weight_unit}", _lbox_show=show_flags.lbox and complexity_shown,
        _cbox_show=show_flags.cbox and complexity_shown, show_generator_detempering=show_flags.generator_detempering,
        show_interest=show_flags.interest, gridded_values=show_flags.gridded_values, show_quantities=show_flags.quantities,
        _decimals=show_flags.decimals, show_ebk=show_flags.ebk, show_interval_ratios=show_flags.interval_ratios,
        show_interval_vectors=show_flags.interval_vectors, show_math_expressions=show_math_expressions,
        terminology_mode=inputs.settings.get("terminology", "dd"),
        custom_weights_active=(inputs.custom_weights is not None
                               and not service.is_all_interval(inputs.tuning_scheme)
                               and not show_math_expressions))


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
                                   draft.show_equivalences, draft.show_superspace)
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
        detempering_vectors=(service.generator_detempering(inputs.state.mapping) if draft.show_generator_detempering else ()),
        detempering_sizes=(service.interval_sizes(draft.tuning_map, draft.gens, draft.elements) if draft.show_generator_detempering else None))


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
        canon_mapped_detempering=(service.mapped_commas(canon_mapping, draft.detempering_vectors) if draft.show_generator_detempering else ()),
        canon_unchanged_mapped=canon_unchanged_mapped)


def resolve_projection_data(inputs, draft):
    show_projection = draft.show_tuning_tiles and inputs.settings["projection"]
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
