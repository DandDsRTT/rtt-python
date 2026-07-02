from __future__ import annotations

from dataclasses import dataclass

from rtt.app import terminology


@dataclass(frozen=True)
class Dimensions:
    dimensionality: int
    superspace_dimensionality: int
    rank: int
    superspace_rank: int
    canonical_rank: int
    target_count: int
    comma_count: int
    held_count: int
    interest_count: int
    unchanged_count: int
    target_count_shown: int
    held_count_shown: int
    interest_count_shown: int
    comma_count_shown: int
    vector_count_shown: int
    dimensionality_shown: int
    rank_shown: int
    elements: tuple
    superspace_primes: tuple


@dataclass(frozen=True)
class IntervalSet:
    ratios: object
    sizes: object
    mapped: object
    vectors: object
    pending: object


@dataclass(frozen=True)
class Tuning:
    tuning_map: object
    superspace_tuning_map: object
    from_generators: bool
    target_weights: object
    target_sizes: object
    held_sizes: object
    held_mapped: object
    comma_sizes: object
    interest_sizes: object
    optimum_target_override: object


@dataclass(frozen=True)
class Canon:
    mapping: object
    generators: object
    inverse_form_M: object
    form_M: object
    mapping_form_key: object
    comma_basis_form_key: object
    form_is_canonical: bool
    embedding_matrix: object
    mapped: object
    held_mapped: object
    interest_mapped: object
    mapped_commas: object
    mapped_detempering: object
    unchanged_mapped: object


@dataclass(frozen=True)
class Projection:
    matrix: object
    rationals: object
    superspace: object
    embedding_matrix: object
    embedding_superspace: object
    detempering: object
    targets: object
    held: object
    interest: object
    superspace_matrix: object
    superspace_rationals: object
    superspace_embedding_matrix: object
    superspace_basis: object
    superspace_detempering: object
    superspace_targets: object
    superspace_held: object
    superspace_interest: object
    superspace_unchanged: object
    superspace_unchanged_mapped: object


@dataclass(frozen=True)
class Ghosts:
    row: bool
    comma: bool
    new: object
    row_map: object
    row_ratio: object
    row_mapped: object
    comma_vector: object
    comma_ratio: object
    comma_mapped: object
    comma_just: float
    comma_complexity: float


@dataclass(frozen=True)
class Unchanged:
    shown: bool
    basis: object
    ratios: object
    mapped: object
    sizes: object
    complexities: object
    born: bool
    empty_comma_width: float

    @property
    def full(self) -> bool:
        return self.basis is not None and all(v is not None for v in self.basis)


@dataclass(frozen=True)
class Flags:
    alt_complexity: bool
    canonical: bool
    names: bool
    generator_detempering: bool
    ebk: bool
    equivalences: bool
    form_controls: bool
    form_subscript: bool
    header_symbols: bool
    math_expressions: bool
    mnemonics: bool
    nonstandard_domain: bool
    optimization: bool
    presets: bool
    plain_text_values: bool
    quantities: bool
    superspace: bool
    superspace_generators: bool
    symbols: bool
    tile_units: bool
    weighting: bool
    decimals: bool
    projection: bool
    superspace_projection: bool
    identity_objects: bool
    interval_vectors: bool
    cell_units: bool
    gridded_values: bool
    complexity_shown: bool
    prescaling_shown: bool
    prescaling_box_show: bool
    complexity_box_show: bool
    counts: bool
    charts: bool
    tuning_ranges: bool
    app_units: bool
    temperament_tiles: bool
    tuning_tiles: bool
    interest: bool
    interval_ratios: bool
    terminology_mode: str


@dataclass(frozen=True)
class Scalars:
    all_interval: bool
    comma_draft: bool
    targets_editable: bool
    element_draft: bool
    row_draft: bool
    domain_can_shrink: bool
    standard_domain: bool
    custom_weights_active: bool
    prescaler_is_matrix: bool
    generators: object
    prescaler: object
    complexity_unit: str
    weight_unit: str
    damage_unit: str
    control_symbol_height: float
    displayed_projection_name: object
    displayed_tuning_name: object


@dataclass(frozen=True)
class Labels:
    column_labels: object
    row_labels: object
    captions: object
    prescaling_symbols: object
    prescaler_symbol: str
    prescaler_equivalence: str
    domain_label: str
    realized_prescaler: object
    scheme_prescaler: object


@dataclass(frozen=True)
class Resolved:
    dimensions: Dimensions
    targets: IntervalSet
    held: IntervalSet
    commas: IntervalSet
    interest: IntervalSet
    detempering: IntervalSet
    tuning: Tuning
    canonical: Canon
    projection: Projection
    ghosts: Ghosts
    unchanged: Unchanged
    labels: Labels
    flags: Flags
    scalars: Scalars
    complexities: object
    column_ids: object


def _dimensions(b) -> Dimensions:
    return Dimensions(
        dimensionality=b.dimensionality,
        superspace_dimensionality=b.superspace_dimensionality,
        rank=b.rank,
        superspace_rank=b.superspace_rank,
        canonical_rank=b.canonical_rank,
        target_count=b.target_count,
        comma_count=b.comma_count,
        held_count=b.held_count,
        interest_count=b.interest_count,
        unchanged_count=b.unchanged_count,
        target_count_shown=b.target_count_shown,
        held_count_shown=b.held_count_shown,
        interest_count_shown=b.interest_count_shown,
        comma_count_shown=b.comma_count_shown,
        vector_count_shown=b.vector_count_shown,
        dimensionality_shown=b.dimensionality_shown,
        rank_shown=b.rank_shown,
        elements=b.elements,
        superspace_primes=b.superspace_primes,
    )


def _tuning(b) -> Tuning:
    return Tuning(
        tuning_map=b.tuning_map,
        superspace_tuning_map=None,
        from_generators=b._tuning_map_from_generators,
        target_weights=b.target_weights,
        target_sizes=b.target_sizes,
        held_sizes=b.held_sizes,
        held_mapped=b.held_mapped,
        comma_sizes=b.comma_sizes,
        interest_sizes=b.interest_sizes,
        optimum_target_override=b._optimum_target_override,
    )


def _canonical(b) -> Canon:
    return Canon(
        mapping=b.canonical_mapping,
        generators=b.canonical_generators,
        inverse_form_M=b.inverse_form_M,
        form_M=b.form_M,
        mapping_form_key=b.mapping_form_key,
        comma_basis_form_key=b.comma_basis_form_key,
        form_is_canonical=b.form_is_canonical,
        embedding_matrix=b.canonical_embedding_matrix,
        mapped=b.canonical_mapped,
        held_mapped=b.canonical_held_mapped,
        interest_mapped=b.canonical_interest_mapped,
        mapped_commas=b.canonical_mapped_commas,
        mapped_detempering=b.canonical_mapped_detempering,
        unchanged_mapped=b.canonical_unchanged_mapped,
    )


def _projection(b) -> Projection:
    return Projection(
        matrix=b.projection_matrix,
        rationals=b.projection_rationals,
        superspace=b.projection_superspace,
        embedding_matrix=b.embedding_matrix,
        embedding_superspace=b.embedding_superspace,
        detempering=b.projection_detempering,
        targets=b.projection_targets,
        held=b.projection_held,
        interest=b.projection_interest,
        superspace_matrix=b.superspace_projection_matrix,
        superspace_rationals=b.superspace_projection_rationals,
        superspace_embedding_matrix=b.superspace_embedding_matrix,
        superspace_basis=b.superspace_projection_basis,
        superspace_detempering=b.superspace_projection_detempering,
        superspace_targets=b.superspace_projection_targets,
        superspace_held=b.superspace_projection_held,
        superspace_interest=b.superspace_projection_interest,
        superspace_unchanged=b.superspace_unchanged,
        superspace_unchanged_mapped=b.superspace_unchanged_mapped,
    )


def _ghosts(b) -> Ghosts:
    return Ghosts(
        row=b.ghost_row,
        comma=b.ghost_comma,
        new=b.ghost_new,
        row_map=b.ghost_row_map,
        row_ratio=b.ghost_row_ratio,
        row_mapped=b.ghost_row_mapped,
        comma_vector=b.ghost_comma_vector,
        comma_ratio=b.ghost_comma_ratio,
        comma_mapped=b.ghost_comma_mapped,
        comma_just=b.ghost_comma_just,
        comma_complexity=b.ghost_comma_complexity,
    )


def _unchanged(b) -> Unchanged:
    return Unchanged(
        shown=b.show_unchanged,
        basis=b.unchanged_basis,
        ratios=b.unchanged_ratios,
        mapped=b.unchanged_mapped,
        sizes=b.unchanged_sizes,
        complexities=b.unchanged_complexities,
        born=b.born_u,
        empty_comma_width=b.empty_comma_width,
    )


def _labels(b) -> Labels:
    return Labels(
        column_labels=b.column_labels,
        row_labels=b.row_labels,
        captions=terminology.substitute_captions(b.effective_captions, b.terminology_mode),
        prescaling_symbols=b.prescaling_symbols,
        prescaler_symbol=b.prescaler_symbol,
        prescaler_equivalence=b.prescaler_equivalence,
        domain_label=b.domain_label,
        realized_prescaler=b._realized_prescaler,
        scheme_prescaler=b._scheme_prescaler,
    )


def _flags(b) -> Flags:
    return Flags(
        alt_complexity=b.show_alt_complexity,
        canonical=b.show_canonical,
        names=b.show_names,
        generator_detempering=b.show_generator_detempering,
        ebk=b.show_ebk,
        equivalences=b.show_equivalences,
        form_controls=b.show_form_controls,
        form_subscript=b.show_form_subscript,
        header_symbols=b.show_header_symbols,
        math_expressions=b.show_math_expressions,
        mnemonics=b.show_mnemonics,
        nonstandard_domain=b.show_nonstandard_domain,
        optimization=b.show_optimization,
        presets=b.show_presets,
        plain_text_values=b.show_plain_text_values,
        quantities=b.show_quantities,
        superspace=b.show_superspace,
        superspace_generators=b.show_superspace_generators,
        symbols=b.show_symbols,
        tile_units=b.show_tile_units,
        weighting=b.show_weighting,
        decimals=b._decimals,
        projection=b.show_projection,
        superspace_projection=b.show_superspace_projection,
        identity_objects=b.show_identity_objects,
        interval_vectors=b.show_interval_vectors,
        cell_units=b.show_cell_units,
        gridded_values=b.gridded_values,
        complexity_shown=b._complexity_shown,
        prescaling_shown=b._prescaling_shown,
        prescaling_box_show=b._prescaling_box_show,
        complexity_box_show=b._complexity_box_show,
        counts=b.show_counts,
        charts=b.show_charts,
        tuning_ranges=b.show_tuning_ranges,
        app_units=b.show_app_units,
        temperament_tiles=b.show_temperament_tiles,
        tuning_tiles=b.show_tuning_tiles,
        interest=b.show_interest,
        interval_ratios=b.show_interval_ratios,
        terminology_mode=b.terminology_mode,
    )


def _scalars(b) -> Scalars:
    return Scalars(
        all_interval=b.all_interval,
        comma_draft=b.comma_draft,
        targets_editable=b.targets_editable,
        element_draft=b.element_draft,
        row_draft=b.row_draft,
        domain_can_shrink=b.domain_can_shrink,
        standard_domain=b.standard_domain,
        custom_weights_active=b.custom_weights_active,
        prescaler_is_matrix=b.prescaler_is_matrix,
        generators=b.generators,
        prescaler=b.prescaler,
        complexity_unit=b.complexity_unit,
        weight_unit=b.weight_unit,
        damage_unit=b.damage_unit,
        control_symbol_height=b.control_symbol_height,
        displayed_projection_name=b.displayed_projection_name,
        displayed_tuning_name=b.displayed_tuning_name,
    )


def freeze(draft) -> Resolved:
    return Resolved(
        dimensions=_dimensions(draft),
        targets=IntervalSet(
            ratios=draft.targets,
            sizes=draft.target_sizes,
            mapped=draft.mapped,
            vectors=draft.target_vectors,
            pending=draft.pending_target,
        ),
        held=IntervalSet(
            ratios=draft.held_ratios,
            sizes=draft.held_sizes,
            mapped=draft.held_mapped,
            vectors=draft.held,
            pending=draft.pending_held,
        ),
        commas=IntervalSet(
            ratios=draft.comma_ratios,
            sizes=draft.comma_sizes,
            mapped=draft.mapped_commas,
            vectors=None,
            pending=draft.pending,
        ),
        interest=IntervalSet(
            ratios=draft.interest_ratios,
            sizes=draft.interest_sizes,
            mapped=draft.interest_mapped,
            vectors=draft.interest,
            pending=draft.pending_interest,
        ),
        detempering=IntervalSet(
            ratios=None,
            sizes=draft.detempering_sizes,
            mapped=None,
            vectors=draft.detempering_vectors,
            pending=None,
        ),
        tuning=_tuning(draft),
        canonical=_canonical(draft),
        projection=_projection(draft),
        ghosts=_ghosts(draft),
        unchanged=_unchanged(draft),
        labels=_labels(draft),
        flags=_flags(draft),
        scalars=_scalars(draft),
        complexities=draft.complexities,
        column_ids=draft._col_ids,
    )
