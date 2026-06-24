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
    _cents_genmap,
    _cents_list,
    _cents_map,
    _prescale_vector_list,
)


@dataclass(frozen=True)
class DerivedQuantities:
    targets: tuple
    tun: Tuning
    target_weights: tuple
    target_sizes: IntervalSizes
    comma_sizes: IntervalSizes
    superspace_tun: Tuning | None = None


@dataclass(frozen=True)
class _Fmt:
    decimals: bool
    superspace: bool

    def r(self, key, data, fmt=str) -> str:
        return render_ebk(ebk_convention(*key, superspace=self.superspace), data, fmt)

    def cents_map(self, values) -> str:
        return _cents_map(values, self.decimals)

    def cents_list(self, values, wrap: bool = True) -> str:
        return _cents_list(values, wrap, self.decimals)

    def cents_genmap(self, values) -> str:
        return _cents_genmap(values, self.decimals)

    def prescale(self, vectors, col: str = "[⟩", outer: str = "[]") -> str:
        return _prescale_vector_list(vectors, col, outer, self.decimals)


@dataclass(frozen=True)
class _Core:
    targets: tuple
    comma_basis: tuple
    commas: tuple
    mapped: tuple
    mapped_comma: tuple
    target_vectors: tuple
    held_ratios: tuple
    tun: Tuning
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
    comps: list
    scaling: list


@dataclass(frozen=True)
class _Canon:
    mapping: tuple
    rc: int
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
    def db(self) -> tuple:
        return self.state.domain_basis


@dataclass(frozen=True)
class _Ctx:
    inp: _Inputs
    fmt: _Fmt
    core: _Core
    prescale: _Prescale
    unchanged: _Unchanged
    canon: _Canon

    @property
    def state(self) -> TemperamentState:
        return self.inp.state

    @property
    def scheme(self) -> str:
        return self.inp.scheme

    @property
    def db(self) -> tuple:
        return self.inp.state.domain_basis

    @property
    def d(self) -> int:
        return self.inp.state.d

    @property
    def held(self) -> tuple:
        return self.inp.held

    @property
    def interest(self) -> tuple:
        return self.inp.interest

    @property
    def consolidate_v(self) -> bool:
        return self.inp.consolidate_v

    @property
    def superspace(self) -> bool:
        return self.inp.superspace

    @property
    def held_basis_ratios(self) -> tuple:
        return self.inp.held_basis_ratios

    @property
    def custom_prescaler(self) -> object:
        return self.inp.custom_prescaler

    @property
    def nonprime_approach(self) -> str:
        return self.inp.nonprime_approach

    @property
    def superspace_generator_override(self) -> object:
        return self.inp.superspace_generator_override

    @property
    def derived(self) -> DerivedQuantities | None:
        return self.inp.derived

    def r(self, key, data, fmt=str) -> str:
        return self.fmt.r(key, data, fmt)

    def prescaled(self, vectors):
        return _apply_prescaler(self.prescale, self.state.d, vectors)

    def sized(self, cols):
        return _apply_size(self.prescale, cols)

    def complexities(self, ratios):
        return interval_complexities(
            self.state.mapping,
            self.scheme,
            ratios,
            domain_basis=self.db,
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


def _apply_size(prescale: _Prescale, cols):
    if not prescale.size_factor:
        return cols
    return tuple((*col, prescale.size_factor * sum(col)) for col in cols)


def _derive_tuning(inp: _Inputs, held_ratios):
    if inp.derived is not None:
        return inp.derived.tun
    state = inp.state
    if inp.generator_tuning is not None and len(inp.generator_tuning) == len(state.mapping):
        return tuning_from_generators(state.mapping, inp.generator_tuning, inp.db)
    return tuning(
        state.mapping,
        inp.scheme,
        inp.db,
        inp.nonprime_approach,
        held=held_ratios,
        prescaler_override=inp.custom_prescaler,
        targets=inp.target_override,
    )


def _derive_core(inp: _Inputs, targets, held_ratios) -> _Core:
    state, db = inp.state, inp.db
    comma_basis = state.comma_basis if state.n else ()
    commas = comma_ratios(comma_basis, db)
    tun = _derive_tuning(inp, held_ratios)
    weights = (
        inp.derived.target_weights
        if inp.derived
        else interval_weights(
            state.mapping,
            inp.scheme,
            targets,
            domain_basis=db,
            prescaler_override=inp.custom_prescaler,
        )
    )
    target_sizes = (
        inp.derived.target_sizes
        if inp.derived
        else interval_sizes(tun, targets, db, weights=weights)
    )
    comma_sizes = inp.derived.comma_sizes if inp.derived else interval_sizes(tun, commas, db)
    detemper_ratios = generators(state.mapping, db)
    return _Core(
        targets,
        comma_basis,
        commas,
        mapped_intervals(state.mapping, targets, db),
        mapped_commas(state.mapping, comma_basis),
        target_interval_vectors(targets, state.d, db),
        held_ratios,
        tun,
        weights,
        target_sizes,
        comma_sizes,
        detemper_ratios,
        interval_sizes(tun, detemper_ratios, db),
        generator_detempering(state.mapping),
        tuple(element_ratio(e) for e in db),
    )


def _derive_prescale(inp: _Inputs) -> _Prescale:
    state, db = inp.state, inp.db
    prescaler = complexity_prescaler(
        state.mapping,
        inp.scheme,
        override=inp.custom_prescaler,
        domain_basis=db,
        nonprime_approach=inp.nonprime_approach,
    )
    is_matrix = bool(prescaler) and isinstance(prescaler[0], (tuple, list))
    size_factor = complexity_size_factor(inp.scheme)
    if is_matrix:
        bare_rows = [tuple(prescaler[i]) for i in range(state.d)]
    else:
        bare_rows = [
            tuple(prescaler[i] if k == i else 0 for k in range(state.d)) for i in range(state.d)
        ]
    bare_size_row = (
        (tuple(size_factor * sum(col) for col in zip(*bare_rows, strict=False)),)
        if size_factor
        else ()
    )
    return _Prescale(prescaler, is_matrix, size_factor, bare_rows, bare_size_row)


def _derive_unchanged(inp: _Inputs, core: _Core, prescale: _Prescale) -> _Unchanged:
    state, db = inp.state, inp.db
    udata = (
        unchanged_interval_data(
            state, inp.held_basis_ratios, core.tun, inp.scheme, db, inp.custom_prescaler
        )
        if inp.consolidate_v
        else None
    )
    if udata is None:
        return _Unchanged([], [], [], [], [], [], [], [])
    nrow = len(state.mapping)
    mapped_cols = [
        None if udata.basis[j] is None else tuple(udata.mapped[i][j] for i in range(nrow))
        for j in range(len(udata.basis))
    ]
    prescaled = [
        None if u is None else _apply_size(prescale, _apply_prescaler(prescale, state.d, (u,)))[0]
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


def _derive_canon(inp: _Inputs, targets, core: _Core, unchanged: _Unchanged) -> _Canon:
    state, db = inp.state, inp.db
    mapping = canonical_mapping(state.mapping)
    rc = len(mapping)
    u_mapped_cols = [
        None
        if u is None
        else tuple(sum(mapping[i][p] * u[p] for p in range(state.d)) for i in range(rc))
        for u in unchanged.basis
    ]
    return _Canon(
        mapping,
        rc,
        form_matrix(state.mapping),
        inverse_form_matrix(state.mapping),
        mapped_intervals(mapping, targets, db),
        mapped_commas(mapping, core.comma_basis),
        mapped_commas(mapping, core.detemper_vectors),
        u_mapped_cols,
    )


def _resolve_targets(inp: _Inputs):
    if inp.derived:
        return inp.derived.targets
    return displayed_targets(inp.state, inp.scheme, inp.target_spec, inp.target_override)


def _build_context(inp: _Inputs) -> _Ctx:
    targets = _resolve_targets(inp)
    held_ratios = comma_ratios(inp.held, inp.db) if inp.held else ()
    core = _derive_core(inp, targets, held_ratios)
    prescale = _derive_prescale(inp)
    unchanged = _derive_unchanged(inp, core, prescale)
    canon = _derive_canon(inp, targets, core, unchanged)
    fmt = _Fmt(inp.decimals, inp.superspace)
    return _Ctx(inp, fmt, core, prescale, unchanged, canon)
