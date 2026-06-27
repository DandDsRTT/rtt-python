from __future__ import annotations

from dataclasses import dataclass

from rtt.app import terminology


@dataclass(frozen=True)
class Dims:
    d: int
    dL: int
    r: int
    rL: int
    rc: int
    k: int
    nc: int
    nh: int
    mi: int
    nu: int
    k_shown: int
    nh_shown: int
    mi_shown: int
    nc_shown: int
    nv_shown: int
    d_shown: int
    r_shown: int
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
    tun: object
    ss_tun: object
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
    gens: object
    form_M: object
    inverse_form_M: object
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
    ss_matrix: object
    ss_rationals: object
    ss_embedding_matrix: object
    ss_basis: object
    ss_detempering: object
    ss_targets: object
    ss_held: object
    ss_interest: object
    ss_unchanged: object
    ss_unchanged_mapped: object


@dataclass(frozen=True)
class Ghosts:
    row: bool
    comma: bool
    new: object
    row_map: object
    row_ratio: object
    row_mapped: object
    comma_vec: object
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
    empty_comma_w: float


@dataclass(frozen=True)
class Flags:
    alt_complexity: bool
    canon: bool
    names: bool
    detempering: bool
    ebk: bool
    equiv: bool
    form_controls: bool
    form_subscript: bool
    header_symbols: bool
    math: bool
    mnemonics: bool
    nonstandard_domain: bool
    optimization: bool
    presets: bool
    ptext: bool
    quantities: bool
    superspace: bool
    superspace_generators: bool
    symbols: bool
    units: bool
    weighting: bool
    decimals: bool
    projection: bool
    ss_projection: bool
    identity_objects: bool
    interval_vectors: bool
    cell_units: bool
    gridded: bool
    complexity_shown: bool
    prescaling_shown: bool
    lbox_show: bool
    cbox_show: bool
    counts: bool
    charts: bool
    ranges: bool
    domain_units: bool
    temp: bool
    tuning: bool
    interest: bool
    interval_ratios: bool
    dd_terminology: bool


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
    gens: object
    prescaler: object
    complexity_unit: str
    weight_unit: str
    damage_unit: str
    ctrl_symbol_h: float
    displayed_projection_name: object
    displayed_tuning_name: object


@dataclass(frozen=True)
class Labels:
    col_labels: object
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
    dims: Dims
    targets: IntervalSet
    held: IntervalSet
    commas: IntervalSet
    interest: IntervalSet
    detempering: IntervalSet
    tuning: Tuning
    canon: Canon
    projection: Projection
    ghosts: Ghosts
    unchanged: Unchanged
    labels: Labels
    flags: Flags
    scalars: Scalars
    complexities: object
    col_ids: object


def _dims(b) -> Dims:
    return Dims(
        d=b.d,
        dL=b.dL,
        r=b.r,
        rL=b.rL,
        rc=b.rc,
        k=b.k,
        nc=b.nc,
        nh=b.nh,
        mi=b.mi,
        nu=b.nu,
        k_shown=b.k_shown,
        nh_shown=b.nh_shown,
        mi_shown=b.mi_shown,
        nc_shown=b.nc_shown,
        nv_shown=b.nv_shown,
        d_shown=b.d_shown,
        r_shown=b.r_shown,
        elements=b.elements,
        superspace_primes=b.superspace_primes,
    )


def _tuning(b) -> Tuning:
    return Tuning(
        tun=b.tun,
        ss_tun=None,
        from_generators=b._tun_from_generators,
        target_weights=b.target_weights,
        target_sizes=b.target_sizes,
        held_sizes=b.held_sizes,
        held_mapped=b.held_mapped,
        comma_sizes=b.comma_sizes,
        interest_sizes=b.interest_sizes,
        optimum_target_override=b._optimum_target_override,
    )


def _canon(b) -> Canon:
    return Canon(
        mapping=b.canon_mapping,
        gens=b.canon_gens,
        form_M=b.form_M,
        inverse_form_M=b.inverse_form_M,
        mapping_form_key=b.mapping_form_key,
        comma_basis_form_key=b.comma_basis_form_key,
        form_is_canonical=b.form_is_canonical,
        embedding_matrix=b.canon_embedding_matrix,
        mapped=b.canon_mapped,
        held_mapped=b.canon_held_mapped,
        interest_mapped=b.canon_interest_mapped,
        mapped_commas=b.canon_mapped_commas,
        mapped_detempering=b.canon_mapped_detempering,
        unchanged_mapped=b.canon_unchanged_mapped,
    )


def _projection(b) -> Projection:
    return Projection(
        matrix=b.projection_matrix,
        rationals=b.projection_rationals,
        superspace=b.projection_superspace,
        embedding_matrix=b.embedding_matrix,
        embedding_superspace=b.embedding_superspace,
        detempering=b.proj_detempering,
        targets=b.proj_targets,
        held=b.proj_held,
        interest=b.proj_interest,
        ss_matrix=b.ss_projection_matrix,
        ss_rationals=b.ss_projection_rationals,
        ss_embedding_matrix=b.ss_embedding_matrix,
        ss_basis=b.ss_proj_basis,
        ss_detempering=b.ss_proj_detempering,
        ss_targets=b.ss_proj_targets,
        ss_held=b.ss_proj_held,
        ss_interest=b.ss_proj_interest,
        ss_unchanged=b.ss_unchanged,
        ss_unchanged_mapped=b.ss_unchanged_mapped,
    )


def _ghosts(b) -> Ghosts:
    return Ghosts(
        row=b.ghost_row,
        comma=b.ghost_comma,
        new=b.ghost_new,
        row_map=b.ghost_row_map,
        row_ratio=b.ghost_row_ratio,
        row_mapped=b.ghost_row_mapped,
        comma_vec=b.ghost_comma_vec,
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
        empty_comma_w=b.empty_comma_w,
    )


def _labels(b) -> Labels:
    return Labels(
        col_labels=b.col_labels,
        row_labels=b.row_labels,
        captions=terminology.wiki_captions(b.effective_captions, b.dd_terminology),
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
        canon=b.show_canon,
        names=b.show_names,
        detempering=b.show_detempering,
        ebk=b.show_ebk,
        equiv=b.show_equiv,
        form_controls=b.show_form_controls,
        form_subscript=b.show_form_subscript,
        header_symbols=b.show_header_symbols,
        math=b.show_math,
        mnemonics=b.show_mnemonics,
        nonstandard_domain=b.show_nonstandard_domain,
        optimization=b.show_optimization,
        presets=b.show_presets,
        ptext=b.show_ptext,
        quantities=b.show_quantities,
        superspace=b.show_superspace,
        superspace_generators=b.show_superspace_generators,
        symbols=b.show_symbols,
        units=b.show_units,
        weighting=b.show_weighting,
        decimals=b._decimals,
        projection=b.show_projection,
        ss_projection=b.show_ss_projection,
        identity_objects=b.show_identity_objects,
        interval_vectors=b.show_interval_vectors,
        cell_units=b.show_cell_units,
        gridded=b.gridded,
        complexity_shown=b._complexity_shown,
        prescaling_shown=b._prescaling_shown,
        lbox_show=b._lbox_show,
        cbox_show=b._cbox_show,
        counts=b.show_counts,
        charts=b.show_charts,
        ranges=b.show_ranges,
        domain_units=b.show_domain_units,
        temp=b.show_temp,
        tuning=b.show_tuning,
        interest=b.show_interest,
        interval_ratios=b.show_interval_ratios,
        dd_terminology=b.dd_terminology,
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
        gens=b.gens,
        prescaler=b.prescaler,
        complexity_unit=b.complexity_unit,
        weight_unit=b.weight_unit,
        damage_unit=b.damage_unit,
        ctrl_symbol_h=b.ctrl_symbol_h,
        displayed_projection_name=b.displayed_projection_name,
        displayed_tuning_name=b.displayed_tuning_name,
    )


def freeze(draft) -> Resolved:
    return Resolved(
        dims=_dims(draft),
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
        canon=_canon(draft),
        projection=_projection(draft),
        ghosts=_ghosts(draft),
        unchanged=_unchanged(draft),
        labels=_labels(draft),
        flags=_flags(draft),
        scalars=_scalars(draft),
        complexities=draft.complexities,
        col_ids=draft._col_ids,
    )
