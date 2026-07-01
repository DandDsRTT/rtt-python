from __future__ import annotations

from dataclasses import dataclass

from rtt.app.service.core import (
    IntervalSizes,
    Tuning,
    interval_complexities,
    interval_sizes,
    interval_weights,
    tuning,
    tuning_from_generators,
)
from rtt.app.service.core_forms import canonical_mapping, form_matrix, inverse_form_matrix
from rtt.app.service.core_vectors import (
    comma_ratios,
    element_ratio,
    generator_detempering,
    generators,
    mapped_commas,
    mapped_intervals,
    target_interval_vectors,
)
from rtt.app.service.projection import unchanged_interval_data
from rtt.app.service.schemes import (
    complexity_prescaler,
    complexity_size_factor,
    displayed_targets,
)
from rtt.app.service.state import TemperamentState
from rtt.app.service.text_conventions import _DASH, ebk_convention, render_ebk
from rtt.app.service.text_format import (
    _cents_generator_map,
    _cents_list,
    _cents_map,
    _prescale_vector_list,
)


@dataclass(frozen=True)
class DerivedQuantities:
    targets: tuple
    tuning_map: Tuning
    target_weights: tuple
    target_sizes: IntervalSizes
    comma_sizes: IntervalSizes
    superspace_tuning_map: Tuning | None = None


@dataclass(frozen=True)
class _Formatter:
    decimals: bool
    superspace: bool

    def render(self, key, data, formatter=str) -> str:
        return render_ebk(ebk_convention(*key, superspace=self.superspace), data, formatter)

    def cents_map(self, values) -> str:
        return _cents_map(values, self.decimals)

    def cents_list(self, values, wrap: bool = True) -> str:
        return _cents_list(values, wrap, self.decimals)

    def cents_generator_map(self, values) -> str:
        return _cents_generator_map(values, self.decimals)

    def prescale(self, vectors, column: str = "[⟩", outer: str = "[]") -> str:
        return _prescale_vector_list(vectors, column, outer, self.decimals)


@dataclass(frozen=True)
class _Core:
    targets: tuple
    comma_basis: tuple
    commas: tuple
    mapped: tuple
    mapped_comma: tuple
    target_vectors: tuple
    held_ratios: tuple
    tuning_map: Tuning
    target_weights: tuple
    target_sizes: IntervalSizes
    comma_sizes: IntervalSizes
    detemper_ratios: tuple
    detemper_sizes: IntervalSizes
    detemper_vectors: tuple
    prime_ratios: tuple


@dataclass(frozen=True)
class _Prescale:
    prescaler: object
    is_matrix: bool
    size_factor: object
    bare_rows: list
    bare_size_row: tuple


@dataclass(frozen=True)
class _Unchanged:
    basis: list
    mapped_cols: list
    prescaled: list
    tempered: list
    just: list
    errors: list
    complexities: list
    scaling: list


@dataclass(frozen=True)
class _Canonical:
    mapping: tuple
    rank: int
    form: tuple
    inverse_form: tuple
    mapped: tuple
    mapped_comma: tuple
    mapped_detempering: tuple
    u_mapped_cols: list


@dataclass(frozen=True)
class _Inputs:
    state: TemperamentState
    scheme: str
    target_spec: str
    held: tuple
    interest: tuple
    generator_tuning: object
    target_override: object
    nonprime_approach: str
    superspace: bool
    superspace_generator_override: object
    consolidate_v: bool
    held_basis_ratios: tuple
    custom_prescaler: object
    derived: DerivedQuantities | None
    decimals: bool

    @property
    def domain_basis(self) -> tuple:
        return self.state.domain_basis


@dataclass(frozen=True)
class _TextContext:
    inputs: _Inputs
    formatter: _Formatter
    core: _Core
    prescale: _Prescale
    unchanged: _Unchanged
    canonical: _Canonical

    @property
    def state(self) -> TemperamentState:
        return self.inputs.state

    @property
    def scheme(self) -> str:
        return self.inputs.scheme

    @property
    def domain_basis(self) -> tuple:
        return self.inputs.state.domain_basis

    @property
    def dimensionality(self) -> int:
        return self.inputs.state.dimensionality

    @property
    def held(self) -> tuple:
        return self.inputs.held

    @property
    def interest(self) -> tuple:
        return self.inputs.interest

    @property
    def consolidate_v(self) -> bool:
        return self.inputs.consolidate_v

    @property
    def superspace(self) -> bool:
        return self.inputs.superspace

    @property
    def held_basis_ratios(self) -> tuple:
        return self.inputs.held_basis_ratios

    @property
    def custom_prescaler(self) -> object:
        return self.inputs.custom_prescaler

    @property
    def nonprime_approach(self) -> str:
        return self.inputs.nonprime_approach

    @property
    def superspace_generator_override(self) -> object:
        return self.inputs.superspace_generator_override

    @property
    def derived(self) -> DerivedQuantities | None:
        return self.inputs.derived

    def render(self, key, data, formatter=str) -> str:
        return self.formatter.render(key, data, formatter)

    def prescaled(self, vectors):
        return _apply_prescaler(self.prescale, self.state.dimensionality, vectors)

    def sized(self, columns):
        return _apply_size(self.prescale, columns)

    def complexities(self, ratios):
        return interval_complexities(
            self.state.mapping,
            self.scheme,
            ratios,
            domain_basis=self.domain_basis,
            prescaler_override=self.custom_prescaler,
        )


def _identity(n: int) -> list:
    return [[1 if i == k else 0 for k in range(n)] for i in range(n)]


def _apply_prescaler(prescale: _Prescale, d: int, vectors):
    p = prescale.prescaler
    if prescale.is_matrix:
        return tuple(
            tuple(sum(p[i][k] * v[k] for k in range(d)) for i in range(d)) for v in vectors
        )
    return tuple(tuple(p[i] * v[i] for i in range(d)) for v in vectors)


def _apply_size(prescale: _Prescale, columns):
    if not prescale.size_factor:
        return columns
    return tuple((*column, prescale.size_factor * sum(column)) for column in columns)


def _derive_tuning(inputs: _Inputs, held_ratios):
    if inputs.derived is not None:
        return inputs.derived.tuning_map
    state = inputs.state
    if inputs.generator_tuning is not None and len(inputs.generator_tuning) == len(state.mapping):
        return tuning_from_generators(state.mapping, inputs.generator_tuning, inputs.domain_basis)
    return tuning(
        state.mapping,
        inputs.scheme,
        inputs.domain_basis,
        inputs.nonprime_approach,
        held=held_ratios,
        prescaler_override=inputs.custom_prescaler,
        targets=inputs.target_override,
    )


def _derive_core(inputs: _Inputs, targets, held_ratios) -> _Core:
    state, domain_basis = inputs.state, inputs.domain_basis
    comma_basis = state.comma_basis if state.nullity else ()
    commas = comma_ratios(comma_basis, domain_basis)
    tuning_map = _derive_tuning(inputs, held_ratios)
    weights = (
        inputs.derived.target_weights
        if inputs.derived
        else interval_weights(
            state.mapping,
            inputs.scheme,
            targets,
            domain_basis=domain_basis,
            prescaler_override=inputs.custom_prescaler,
        )
    )
    target_sizes = (
        inputs.derived.target_sizes
        if inputs.derived
        else interval_sizes(tuning_map, targets, domain_basis, weights=weights)
    )
    comma_sizes = (
        inputs.derived.comma_sizes
        if inputs.derived
        else interval_sizes(tuning_map, commas, domain_basis)
    )
    detemper_ratios = generators(state.mapping, domain_basis)
    return _Core(
        targets,
        comma_basis,
        commas,
        mapped_intervals(state.mapping, targets, domain_basis),
        mapped_commas(state.mapping, comma_basis),
        target_interval_vectors(targets, state.dimensionality, domain_basis),
        held_ratios,
        tuning_map,
        weights,
        target_sizes,
        comma_sizes,
        detemper_ratios,
        interval_sizes(tuning_map, detemper_ratios, domain_basis),
        generator_detempering(state.mapping),
        tuple(element_ratio(e) for e in domain_basis),
    )


def _derive_prescale(inputs: _Inputs) -> _Prescale:
    state, domain_basis = inputs.state, inputs.domain_basis
    prescaler = complexity_prescaler(
        state.mapping,
        inputs.scheme,
        override=inputs.custom_prescaler,
        domain_basis=domain_basis,
        nonprime_approach=inputs.nonprime_approach,
    )
    is_matrix = bool(prescaler) and isinstance(prescaler[0], (tuple, list))
    size_factor = complexity_size_factor(inputs.scheme)
    if is_matrix:
        bare_rows = [tuple(prescaler[i]) for i in range(state.dimensionality)]
    else:
        bare_rows = [
            tuple(prescaler[i] if k == i else 0 for k in range(state.dimensionality))
            for i in range(state.dimensionality)
        ]
    bare_size_row = (
        (tuple(size_factor * sum(column) for column in zip(*bare_rows, strict=False)),)
        if size_factor
        else ()
    )
    return _Prescale(prescaler, is_matrix, size_factor, bare_rows, bare_size_row)


def _derive_unchanged(inputs: _Inputs, core: _Core, prescale: _Prescale) -> _Unchanged:
    state, domain_basis = inputs.state, inputs.domain_basis
    udata = (
        unchanged_interval_data(
            state,
            inputs.held_basis_ratios,
            core.tuning_map,
            inputs.scheme,
            domain_basis,
            inputs.custom_prescaler,
        )
        if inputs.consolidate_v
        else None
    )
    if udata is None:
        return _Unchanged([], [], [], [], [], [], [], [])
    row_count = len(state.mapping)
    mapped_cols = [
        None if udata.basis[j] is None else tuple(udata.mapped[i][j] for i in range(row_count))
        for j in range(len(udata.basis))
    ]
    prescaled = [
        None
        if u is None
        else _apply_size(prescale, _apply_prescaler(prescale, state.dimensionality, (u,)))[0]
        for u in udata.basis
    ]
    return _Unchanged(
        list(udata.basis),
        mapped_cols,
        prescaled,
        list(udata.sizes.tempered),
        list(udata.sizes.just),
        list(udata.sizes.errors),
        list(udata.complexities),
        [_DASH if v is None else "1" for v in udata.basis],
    )


def _derive_canonical(inputs: _Inputs, targets, core: _Core, unchanged: _Unchanged) -> _Canonical:
    state, domain_basis = inputs.state, inputs.domain_basis
    mapping = canonical_mapping(state.mapping)
    rc = len(mapping)
    u_mapped_cols = [
        None
        if u is None
        else tuple(
            sum(mapping[i][p] * u[p] for p in range(state.dimensionality)) for i in range(rc)
        )
        for u in unchanged.basis
    ]
    return _Canonical(
        mapping,
        rc,
        inverse_form_matrix(state.mapping),
        form_matrix(state.mapping),
        mapped_intervals(mapping, targets, domain_basis),
        mapped_commas(mapping, core.comma_basis),
        mapped_commas(mapping, core.detemper_vectors),
        u_mapped_cols,
    )


def _resolve_targets(inputs: _Inputs):
    if inputs.derived:
        return inputs.derived.targets
    return displayed_targets(
        inputs.state, inputs.scheme, inputs.target_spec, inputs.target_override
    )


def _build_context(inputs: _Inputs) -> _TextContext:
    targets = _resolve_targets(inputs)
    held_ratios = comma_ratios(inputs.held, inputs.domain_basis) if inputs.held else ()
    core = _derive_core(inputs, targets, held_ratios)
    prescale = _derive_prescale(inputs)
    unchanged = _derive_unchanged(inputs, core, prescale)
    canonical = _derive_canonical(inputs, targets, core, unchanged)
    formatter = _Formatter(inputs.decimals, inputs.superspace)
    return _TextContext(inputs, formatter, core, prescale, unchanged, canonical)
