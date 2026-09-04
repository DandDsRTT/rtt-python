from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import NamedTuple

from rtt.app import service
from rtt.app.spreadsheet_constants import SYMBOL_HEIGHT
from rtt.app.spreadsheet_models import _resolve_prescaler_labels, _resolve_show_flags


class Ghosts(NamedTuple):
    row: bool
    comma: bool
    unchanged: bool
    element: bool


def determine_ghosts(inputs) -> Ghosts:
    axes = inputs.ghost_axes
    return Ghosts(
        "generators" in axes and inputs.pending_mapping_row is None,
        "commas" in axes and inputs.pending_comma is None,
        "unchanged" in axes,
        "elements" in axes and inputs.pending_element is None,
    )


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
        show_tuning_ranges=show_flags.tuning_ranges, show_symbols=show_symbols, control_symbol_height=SYMBOL_HEIGHT if show_symbols else 0,
        show_header_symbols=show_flags.header_symbols, show_tile_units=show_flags.tile_units, show_cell_units=show_flags.cell_units,
        show_app_units=show_flags.app_units, show_temperament_tiles=show_flags.temperament_tiles,
        show_form_tiles=show_flags.form_tiles, show_tuning_tiles=show_flags.tuning_tiles,
        show_optimization=show_flags.optimization, show_weighting=show_weighting,
        show_alt_complexity=show_flags.alt_complexity, _complexity_shown=complexity_shown,
        _prescaling_shown=prescaling_shown, weight_unit=weight_unit,
        complexity_unit=f"({service.complexity_annotation(inputs.tuning_scheme)})",
        damage_unit=f"¢{weight_unit}", _prescaling_panel_show=show_flags.prescaling_panel and complexity_shown,
        _complexity_panel_show=show_flags.complexity_panel and complexity_shown, show_generator_detempering=show_flags.generator_detempering,
        show_interest=show_flags.interest, gridded_values=show_flags.gridded_values, show_brackets=show_flags.brackets, show_quantities=show_flags.quantities,
        _decimals=show_flags.decimals, show_ebk=show_flags.ebk, show_interval_ratios=show_flags.interval_ratios,
        show_interval_vectors=show_flags.interval_vectors, show_math_expressions=show_math_expressions,
        terminology_mode=inputs.settings.get("terminology", "dd"),
        custom_weights_active=(inputs.custom_weights is not None
                               and not service.is_all_interval(inputs.tuning_scheme)))


def resolve_superspace_dims(inputs, draft):
    elements = inputs.state.domain_basis
    rank = len(inputs.state.mapping)
    row_draft = inputs.pending_mapping_row is not None or draft.ghost_row
    show_nonstandard_domain = inputs.settings.get("nonstandard_domain", False)
    show_superspace = (show_nonstandard_domain
                       and service.domain_has_nonprimes(elements)
                       and inputs.nonprime_approach != "nonprime-based")
    return replace(
        draft, dimensionality=inputs.state.dimensionality, rank=rank, row_draft=row_draft,
        rank_shown=rank + (1 if row_draft else 0),
        elements=elements, superspace_dimensionality=service.superspace_dimension(elements),
        superspace_rank=service.superspace_rank(inputs.state), superspace_primes=service.superspace_primes(elements),
        show_nonstandard_domain=show_nonstandard_domain, show_superspace=show_superspace,
        show_superspace_generators=show_superspace and inputs.nonprime_approach == "prime-based")


def resolve_prescaler_and_domain_labels(inputs, draft):
    _p = _resolve_prescaler_labels(inputs.state, inputs.tuning_scheme, inputs.custom_prescaler,
                                   draft.show_equivalences, draft.show_superspace)
    return replace(
        draft, _scheme_prescaler=_p.scheme_prescaler, _realized_prescaler=_p.realized,
        prescaler_symbol=_p.symbol, prescaler_equivalence=_p.equivalence,
        prescaling_symbols=_p.prescaling_symbols, column_labels=_p.column_labels, row_labels=_p.row_labels,
        effective_names=_p.effective_names,
        show_identity_objects=inputs.settings.get("identity_objects", False),
        standard_domain=service.is_standard_domain(draft.elements),
        domain_label="b" if service.domain_has_nonprimes(draft.elements) else "p",
        domain_can_shrink=service.can_shrink_domain(inputs.state),
        domain_is_canonical=service.is_canonical_domain_basis(draft.elements))


def resolve_complexities(inputs, draft):
    def _complexity(intervals):
        return service.interval_complexities(inputs.state.mapping, inputs.tuning_scheme, intervals,
                                             prescaler_override=inputs.custom_prescaler, domain_basis=draft.elements)
    complexities = {
        "primes": _complexity(tuple(service.element_ratio(e) for e in draft.elements)),
        "commas": _complexity(draft.comma_ratios),
        "targets": _complexity(draft.targets),
        "interest": _complexity(draft.interest_ratios),
        "held": _complexity(draft.held_ratios),
        "generators": _complexity(draft.generators),
    }
    if draft.show_generator_detempering:
        canonical_detemper = service.generator_detempering(draft.canonical_mapping)
        complexities["canonical_generators"] = _complexity(service.comma_ratios(canonical_detemper, draft.elements))
    prescaler = service.complexity_prescaler(inputs.state.mapping, inputs.tuning_scheme, override=inputs.custom_prescaler)
    return replace(draft, complexities=complexities, prescaler=prescaler,
                   prescaler_is_matrix=isinstance(prescaler[0], (tuple, list)))


def resolve_detempering(inputs, draft):
    if not draft.show_generator_detempering:
        return replace(draft, detempering_vectors=(), detempering_ratios=(), detempering_sizes=None)
    detempering = inputs.custom_detempering or service.generator_detempering(inputs.state.mapping)
    return replace(
        draft,
        detempering_vectors=detempering,
        detempering_ratios=service.comma_ratios(detempering, draft.elements),
        detempering_sizes=service.interval_sizes(draft.tuning_map, draft.generators, draft.elements))


def resolve_canonical_mapped(inputs, draft):
    canonical_mapping = draft.canonical_mapping
    _canonical_u = [None if (draft.unchanged_basis is None or draft.unchanged_basis[j] is None)
                else tuple(row[0] for row in service.mapped_commas(canonical_mapping, (draft.unchanged_basis[j],)))
                for j in range(draft.unchanged_count)]
    canonical_unchanged_mapped = tuple(
        tuple((None if _canonical_u[j] is None else _canonical_u[j][i]) for j in range(draft.unchanged_count))
        for i in range(draft.canonical_rank))
    return replace(
        draft, canonical_mapped=service.mapped_intervals(canonical_mapping, draft.targets, draft.elements),
        canonical_held_mapped=service.mapped_intervals(canonical_mapping, draft.held_ratios, draft.elements),
        canonical_interest_mapped=service.mapped_intervals(canonical_mapping, draft.interest_ratios, draft.elements),
        canonical_mapped_commas=service.mapped_commas(canonical_mapping, inputs.state.comma_basis),
        canonical_mapped_detempering=(service.mapped_commas(canonical_mapping, draft.detempering_vectors) if draft.show_generator_detempering else ()),
        canonical_unchanged_mapped=canonical_unchanged_mapped)


def _projection_complexities(inputs, draft, show_projection, embedding):
    if not show_projection:
        return draft.complexities
    rank = len(inputs.state.mapping)
    if not embedding:
        values = (None,) * rank
    else:
        columns = [[Fraction(embedding[p][g]) for p in range(len(embedding))] for g in range(len(embedding[0]))]
        values = service.vector_complexities(inputs.state.mapping, inputs.tuning_scheme, columns,
                                             prescaler_override=inputs.custom_prescaler, domain_basis=draft.elements)
    return {**draft.complexities, "generator_embedding": values}


def _matrix_columns(matrix):
    return [[Fraction(matrix[p][g]) for p in range(len(matrix))] for g in range(len(matrix[0]))] if matrix else []


def _superspace_generator_family(inputs, draft, superspace_rationals, embedding):
    full = superspace_rationals is not None

    def project(columns):
        return (service.project_vectors(superspace_rationals, service.lift_vectors_to_superspace(draft.elements, columns))
                if full and columns else None)

    canonical = service.generator_detempering(draft.canonical_mapping) if draft.show_generator_detempering else None
    embed_proj = project(_matrix_columns(embedding))
    canon_proj = project([list(row) for row in canonical]) if canonical else None
    gl = service.superspace_tuning_embedding(inputs.state, inputs.held_basis_ratios) if full else None
    gen_complexity = (service.vector_complexities(service.superspace_mapping(inputs.state), inputs.tuning_scheme,
                                                  _matrix_columns(gl), domain_basis=service.superspace_primes(draft.elements))
                      if gl else None)
    return embed_proj, canon_proj, gen_complexity


def resolve_projection_data(inputs, draft):
    show_projection = draft.show_tuning_tiles and inputs.settings["projection"]
    if show_projection:
        _embed_generators_name(draft.effective_names)
    rationals = (service.projection_matrix_rationals(inputs.state, inputs.held_basis_ratios)
                 if show_projection else None)
    show_superspace = show_projection and draft.show_superspace
    superspace_rationals = (service.superspace_projection_matrix_rationals(inputs.state, inputs.held_basis_ratios)
                    if show_superspace else None)

    def _lift(vs):
        return service.lift_vectors_to_superspace(draft.elements, vs)

    def _superspace_lift(ub):
        return service.lift_vectors_to_superspace(draft.elements, (ub,))[0] if ub is not None else None

    def _superspace_map(ub):
        return service.map_vectors_into_superspace_generators(inputs.state, (ub,))[0] if ub is not None else None

    unchanged_basis = draft.unchanged_basis if draft.show_unchanged else ()
    embedding = service.tuning_embedding(inputs.state, inputs.held_basis_ratios) if show_projection else None
    embed_proj, canon_proj, gen_complexity = _superspace_generator_family(inputs, draft, superspace_rationals, embedding)
    return replace(
        draft, show_projection=show_projection, show_superspace_projection=show_superspace,
        complexities=_projection_complexities(inputs, draft, show_projection, embedding),
        projection_matrix=(service.tuning_projection(inputs.state, inputs.held_basis_ratios) if show_projection else None),
        embedding_matrix=embedding,
        embedding_ratios=(service.embedding_ratios(embedding, draft.elements) if show_projection else ()),
        embedding_sizes=(service.interval_sizes(draft.tuning_map, draft.generators, draft.elements) if show_projection else None),
        canonical_embedding_matrix=(service.canonical_generator_embedding(inputs.state, inputs.held_basis_ratios) if show_projection else None),
        projection_rationals=rationals,
        projection_detempering=service.project_vectors(rationals, draft.detempering_vectors),
        projection_held=service.project_vectors(rationals, draft.held),
        projection_targets=service.project_vectors(rationals, draft.target_vectors),
        projection_interest=service.project_vectors(rationals, draft.interest),
        embedding_superspace=(service.superspace_generator_embedding_display(inputs.state, inputs.held_basis_ratios) if show_superspace else None),
        projection_superspace=(service.superspace_prime_projection_display(inputs.state, inputs.held_basis_ratios) if show_superspace else None),
        superspace_projection_matrix=(service.superspace_tuning_projection(inputs.state, inputs.held_basis_ratios) if show_superspace else None),
        superspace_embedding_matrix=(service.superspace_tuning_embedding(inputs.state, inputs.held_basis_ratios) if show_superspace else None),
        superspace_projection_rationals=superspace_rationals,
        superspace_projection_basis=service.project_vectors(superspace_rationals, service.basis_in_superspace(draft.elements)),
        superspace_projection_detempering=service.project_vectors(superspace_rationals, _lift(draft.detempering_vectors)),
        superspace_projection_embedding=embed_proj,
        superspace_projection_canonical=canon_proj,
        superspace_generator_complexity=gen_complexity,
        superspace_projection_held=service.project_vectors(superspace_rationals, _lift(draft.held)),
        superspace_projection_targets=service.project_vectors(superspace_rationals, _lift(draft.target_vectors)),
        superspace_projection_interest=service.project_vectors(superspace_rationals, _lift(draft.interest)),
        superspace_unchanged=tuple(_superspace_lift(ub) for ub in unchanged_basis),
        superspace_unchanged_mapped=tuple(_superspace_map(ub) for ub in unchanged_basis))


def _embed_generators_name(effective_names):
    for rc in (("mapping", "generators"), ("superspace_mapping", "superspace_generators")):
        cap = effective_names.get(rc)
        if cap and cap.endswith("generators"):
            effective_names[rc] = cap[:-1] + "(s / embedding)"
