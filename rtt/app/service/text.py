from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass

from rtt.app.service.core import (
    DEFAULT_TARGET_SPEC,
    DEFAULT_TUNING_SCHEME,
    IntervalSizes,
    Tuning,
    canonical_mapping,
    cents,
    comma_ratios,
    element_ratio,
    form_matrix,
    generator_detempering,
    generators,
    interval_complexities,
    interval_sizes,
    interval_weights,
    inverse_form_matrix,
    mapped_commas,
    mapped_intervals,
    prescale_text,
    target_interval_vectors,
    tuning,
    tuning_from_generators,
)
from rtt.app.service.projection import (
    canonical_generator_embedding,
    project_vectors,
    projection_matrix_rationals,
    tuning_embedding,
    tuning_projection,
    unchanged_interval_data,
)
from rtt.app.service.schemes import (
    complexity_prescaler,
    complexity_size_factor,
    displayed_targets,
)
from rtt.app.service.state import TemperamentState, mapping_ebk
from rtt.app.service.superspace import (
    basis_in_superspace,
    lift_vectors_to_superspace,
    map_vectors_into_superspace_generators,
    mapping_to_superspace_generators,
    superspace_complexity_prescaler,
    superspace_generator_embedding_display,
    superspace_just_mapping,
    superspace_mapping,
    superspace_prime_projection_display,
    superspace_primes,
    superspace_projection_matrix_rationals,
    superspace_rank,
    superspace_self_map,
    superspace_tuning,
    superspace_tuning_embedding,
    superspace_tuning_projection,
)

EbkConvention = namedtuple(
    "EbkConvention", "structure outer_open outer_close inner_open inner_close sep"
)

_MAP = EbkConvention("row", "⟨", "]", "", "", " ")
_GENMAP = EbkConvention("row", "{", "]", "", "", " ")
_SCALARS = EbkConvention("row", "[", "]", "", "", " ")
_SCALARS_BARE = EbkConvention("row", "", "", "", "", " ")
_VEC = EbkConvention("list", "[", "]", "[", "⟩", " ")
_VEC_BARE = EbkConvention("list", "", "", "[", "⟩", " ")
_MAPPED = EbkConvention("list", "[", "]", "[", "}", " ")
_MAPPED_BARE = EbkConvention("list", "", "", "[", "}", " ")
_EMBED = EbkConvention("list", "{", "]", "[", "⟩", " ")
_GENMAPPED = EbkConvention("list", "{", "]", "[", "}", " ")
_BASIS = EbkConvention("list", "⟨", "]", "[", "⟩", " ")
_STACK_BRACE = EbkConvention("stack", "[", "}", "⟨", "]", "")
_STACK_BRACE_SP = EbkConvention("stack", "[", "}", "⟨", "]", " ")
_STACK_ANGLE = EbkConvention("stack", "[", "⟩", "⟨", "]", "")
_BARE_PRESCALER = EbkConvention("stack", "[", "⟩", "⟨", "]", " ")
_CANON_STACK = EbkConvention("stack", "[", "}", "⟨", "]", " ")
_CANON_GEN_STACK = EbkConvention("stack", "[", "}", "{", "]", " ")

EBK_CONVENTIONS = {
    ("vectors", "commas"): _VEC,
    ("vectors", "targets"): _VEC,
    ("vectors", "detempering"): _VEC,
    ("vectors", "held"): _VEC,
    ("vectors", "interest"): _VEC_BARE,
    ("vectors", "primes"): _STACK_ANGLE,
    ("mapping", "primes"): _STACK_BRACE_SP,
    ("mapping", "commas"): _MAPPED,
    ("mapping", "targets"): _MAPPED,
    ("mapping", "held"): _MAPPED,
    ("mapping", "interest"): _MAPPED_BARE,
    ("mapping", "gens"): _GENMAPPED,
    ("mapping", "detempering"): _GENMAPPED,
    ("mapping", "canongens"): _CANON_GEN_STACK,
    ("canon", "primes"): _CANON_STACK,
    ("canon", "gens"): _CANON_GEN_STACK,
    ("canon", "canongens"): _CANON_GEN_STACK,
    ("canon", "detempering"): _GENMAPPED,
    ("canon", "commas"): _MAPPED,
    ("canon", "targets"): _MAPPED,
    ("canon", "held"): _MAPPED,
    ("canon", "interest"): _MAPPED_BARE,
    ("scaling_factors", "commas"): _SCALARS,
    ("projection", "commas"): _VEC,
    ("projection", "targets"): _VEC,
    ("projection", "held"): _VEC,
    ("projection", "interest"): _VEC_BARE,
    ("projection", "detempering"): _EMBED,
    ("projection", "primes"): _STACK_ANGLE,
    ("projection", "gens"): _EMBED,
    ("projection", "canongens"): _EMBED,
    ("projection", "ssgens"): _EMBED,
    ("projection", "ssprimes"): _STACK_ANGLE,
    ("tuning", "gens"): _GENMAP,
    ("tuning", "canongens"): _GENMAP,
    ("tuning", "primes"): _MAP,
    ("tuning", "commas"): _SCALARS,
    ("tuning", "detempering"): _GENMAP,
    ("tuning", "targets"): _SCALARS,
    ("tuning", "held"): _SCALARS,
    ("tuning", "interest"): _SCALARS_BARE,
    ("tuning", "ssgens"): _GENMAP,
    ("tuning", "ssprimes"): _MAP,
    ("just", "primes"): _MAP,
    ("just", "commas"): _SCALARS,
    ("just", "detempering"): _SCALARS,
    ("just", "targets"): _SCALARS,
    ("just", "held"): _SCALARS,
    ("just", "interest"): _SCALARS_BARE,
    ("just", "ssprimes"): _MAP,
    ("retune", "primes"): _MAP,
    ("retune", "commas"): _SCALARS,
    ("retune", "detempering"): _SCALARS,
    ("retune", "targets"): _SCALARS,
    ("retune", "held"): _SCALARS,
    ("retune", "interest"): _SCALARS_BARE,
    ("retune", "ssprimes"): _MAP,
    ("damage", "targets"): _SCALARS,
    ("weight", "targets"): _SCALARS,
    ("complexity", "primes"): _MAP,
    ("complexity", "commas"): _SCALARS,
    ("complexity", "detempering"): _SCALARS,
    ("complexity", "targets"): _SCALARS,
    ("complexity", "held"): _SCALARS,
    ("complexity", "interest"): _SCALARS_BARE,
    ("complexity", "ssprimes"): _MAP,
    ("prescaling", "commas"): _VEC,
    ("prescaling", "detempering"): _VEC,
    ("prescaling", "targets"): _VEC,
    ("prescaling", "held"): _VEC,
    ("prescaling", "interest"): _VEC_BARE,
    ("prescaling", "ssprimes"): _BARE_PRESCALER,
    ("ss_vectors", "primes"): _BASIS,
    ("ss_vectors", "ssprimes"): _STACK_ANGLE,
    ("ss_vectors", "commas"): _VEC,
    ("ss_vectors", "targets"): _VEC,
    ("ss_vectors", "detempering"): _VEC,
    ("ss_vectors", "held"): _VEC,
    ("ss_vectors", "interest"): _VEC_BARE,
    ("ss_mapping", "ssprimes"): _STACK_BRACE,
    ("ss_mapping", "primes"): _STACK_BRACE,
    ("ss_mapping", "ssgens"): _GENMAPPED,
    ("ss_mapping", "commas"): _MAPPED,
    ("ss_mapping", "targets"): _MAPPED,
    ("ss_mapping", "detempering"): _GENMAPPED,
    ("ss_mapping", "held"): _MAPPED,
    ("ss_mapping", "interest"): _MAPPED_BARE,
    ("ss_projection", "ssprimes"): _STACK_ANGLE,
    ("ss_projection", "ssgens"): _EMBED,
    ("ss_projection", "primes"): _BASIS,
    ("ss_projection", "detempering"): _EMBED,
    ("ss_projection", "commas"): _VEC,
    ("ss_projection", "targets"): _VEC,
    ("ss_projection", "held"): _VEC,
    ("ss_projection", "interest"): _VEC_BARE,
}


def ebk_convention(rkey: str, ckey: str, *, superspace: bool = False) -> EbkConvention:
    if (rkey, ckey) == ("prescaling", "primes"):
        return _BASIS if superspace else _BARE_PRESCALER
    return EBK_CONVENTIONS[(rkey, ckey)]


def render_ebk(conv: EbkConvention, items, fmt=str) -> str:
    oo, oc, io, ic, sep = (
        conv.outer_open,
        conv.outer_close,
        conv.inner_open,
        conv.inner_close,
        conv.sep,
    )
    if conv.structure == "row":
        return oo + sep.join(_DASH if v is None else fmt(v) for v in items) + oc
    vectors = list(items)
    dim = next((len(v) for v in vectors if v is not None), 0)
    pieces = [
        io
        + " ".join([_DASH] * dim if v is None else [_DASH if x is None else fmt(x) for x in v])
        + ic
        for v in vectors
    ]
    return oo + sep.join(pieces) + oc


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


def _base_structural(ctx: _Ctx) -> dict:
    s = ctx.state
    db = ctx.db
    core = ctx.core
    canon = ctx.canon
    un = ctx.unchanged
    return {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        ("vectors", "commas"): _ket_list(list(core.comma_basis) + un.basis, "⟩"),
        ("projection", "commas"): _ket_list([(0,) * s.d for _ in core.commas] + un.basis, "⟩"),
        ("scaling_factors", "commas"): ctx.r(
            ("scaling_factors", "commas"), ["0"] * len(core.commas) + un.scaling
        ),
        ("vectors", "targets"): _ket_list(core.target_vectors, "⟩"),
        ("vectors", "detempering"): _ket_list(core.detemper_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(s),
        ("mapping", "commas"): _ket_list(
            list(zip(*core.mapped_comma, strict=False)) + un.mapped_cols, "}"
        ),
        ("mapping", "targets"): _ket_list(zip(*core.mapped, strict=False), "}"),
        ("vectors", "primes"): ctx.r(("vectors", "primes"), _identity(s.d)),
        ("mapping", "gens"): ctx.r(("mapping", "gens"), _identity(len(s.mapping))),
        ("mapping", "detempering"): ctx.r(("mapping", "detempering"), _identity(len(s.mapping))),
        ("canon", "primes"): ctx.r(("canon", "primes"), canon.mapping),
        ("canon", "gens"): ctx.r(("canon", "gens"), canon.form),
        ("canon", "canongens"): ctx.r(("canon", "canongens"), _identity(canon.rc)),
        ("canon", "detempering"): ctx.r(
            ("canon", "detempering"), list(zip(*canon.mapped_detempering, strict=False))
        ),
        ("canon", "commas"): _ket_list(
            list(zip(*canon.mapped_comma, strict=False)) + canon.u_mapped_cols, "}"
        ),
        ("canon", "targets"): _ket_list(zip(*canon.mapped, strict=False), "}"),
        ("mapping", "canongens"): ctx.r(("mapping", "canongens"), canon.inverse_form),
    }


def _canon_gen_sizes(ctx: _Ctx) -> list:
    tun = ctx.core.tun
    inverse_form = ctx.canon.inverse_form
    nrow = len(ctx.state.mapping)
    return [
        sum(tun.generator_map[k] * inverse_form[k][j] for k in range(nrow))
        for j in range(ctx.canon.rc)
    ]


def _base_sizes(ctx: _Ctx) -> dict:
    core = ctx.core
    un = ctx.unchanged
    tun = core.tun
    fmt = ctx.fmt
    return {
        ("tuning", "canongens"): fmt.cents_genmap(_canon_gen_sizes(ctx)),
        ("tuning", "gens"): fmt.cents_genmap(tun.generator_map),
        ("tuning", "primes"): fmt.cents_map(tun.tuning_map),
        ("tuning", "commas"): fmt.cents_list(list(core.comma_sizes.tempered) + un.tempered),
        ("tuning", "detempering"): fmt.cents_genmap(core.detemper_sizes.tempered),
        ("tuning", "targets"): fmt.cents_list(core.target_sizes.tempered),
        ("just", "primes"): fmt.cents_map(tun.just_map),
        ("just", "commas"): fmt.cents_list(list(core.comma_sizes.just) + un.just),
        ("just", "detempering"): fmt.cents_list(core.detemper_sizes.just),
        ("just", "targets"): fmt.cents_list(core.target_sizes.just),
        ("retune", "primes"): fmt.cents_map(tun.retuning_map),
        ("retune", "commas"): fmt.cents_list(list(core.comma_sizes.errors) + un.errors),
        ("retune", "detempering"): fmt.cents_list(core.detemper_sizes.errors),
        ("retune", "targets"): fmt.cents_list(core.target_sizes.errors),
        ("damage", "targets"): fmt.cents_list(core.target_sizes.damage),
    }


def _base_prescale_complexity(ctx: _Ctx) -> dict:
    core = ctx.core
    un = ctx.unchanged
    pre = ctx.prescale
    fmt = ctx.fmt
    return {
        ("prescaling", "primes"): fmt.prescale(
            pre.bare_rows + list(pre.bare_size_row), col="⟨]", outer="[⟩"
        ),
        ("prescaling", "commas"): fmt.prescale(
            list(ctx.sized(ctx.prescaled(core.comma_basis))) + un.prescaled
        ),
        ("prescaling", "detempering"): fmt.prescale(
            ctx.sized(ctx.prescaled(core.detemper_vectors))
        ),
        ("prescaling", "targets"): fmt.prescale(ctx.sized(ctx.prescaled(core.target_vectors))),
        ("complexity", "primes"): fmt.cents_map(ctx.complexities(core.prime_ratios)),
        ("complexity", "commas"): fmt.cents_list(list(ctx.complexities(core.commas)) + un.comps),
        ("complexity", "detempering"): fmt.cents_list(ctx.complexities(core.detemper_ratios)),
        ("complexity", "targets"): fmt.cents_list(ctx.complexities(core.targets)),
        ("weight", "targets"): fmt.cents_list(core.target_weights),
    }


def _held_values(ctx: _Ctx) -> dict:
    s = ctx.state
    db = ctx.db
    held = ctx.held
    held_ratios = ctx.core.held_ratios
    fmt = ctx.fmt
    held_sizes = interval_sizes(ctx.core.tun, held_ratios, db)
    held_mapped = mapped_intervals(s.mapping, held_ratios, db)
    canon_held_mapped = mapped_intervals(ctx.canon.mapping, held_ratios, db)
    return {
        ("vectors", "held"): _ket_list(held, "⟩"),
        ("mapping", "held"): _ket_list(zip(*held_mapped, strict=False), "}"),
        ("canon", "held"): _ket_list(zip(*canon_held_mapped, strict=False), "}"),
        ("tuning", "held"): fmt.cents_list(held_sizes.tempered),
        ("just", "held"): fmt.cents_list(held_sizes.just),
        ("retune", "held"): fmt.cents_list(held_sizes.errors),
        ("prescaling", "held"): fmt.prescale(ctx.sized(ctx.prescaled(held))),
        ("complexity", "held"): fmt.cents_list(ctx.complexities(held_ratios)),
    }


def _interest_values(ctx: _Ctx) -> dict:
    s = ctx.state
    db = ctx.db
    interest = ctx.interest
    fmt = ctx.fmt
    interest_ratios = comma_ratios(interest, db)
    interest_mapped = mapped_intervals(s.mapping, interest_ratios, db)
    canon_interest_mapped = mapped_intervals(ctx.canon.mapping, interest_ratios, db)
    interest_sizes = interval_sizes(ctx.core.tun, interest_ratios, db)
    return {
        ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
        ("mapping", "interest"): _ket_list(zip(*interest_mapped, strict=False), "}", wrap=False),
        ("canon", "interest"): _ket_list(
            zip(*canon_interest_mapped, strict=False), "}", wrap=False
        ),
        ("tuning", "interest"): fmt.cents_list(interest_sizes.tempered, wrap=False),
        ("just", "interest"): fmt.cents_list(interest_sizes.just, wrap=False),
        ("retune", "interest"): fmt.cents_list(interest_sizes.errors, wrap=False),
        ("prescaling", "interest"): fmt.prescale(ctx.sized(ctx.prescaled(interest)), outer=""),
        ("complexity", "interest"): fmt.cents_list(ctx.complexities(interest_ratios), wrap=False),
    }


def _proj_cols(ctx: _Ctx, p_rat, vectors):
    cols = project_vectors(p_rat, vectors)
    return list(cols) if cols else [tuple(_DASH for _ in range(ctx.d)) for _ in vectors]


def _projection_values(ctx: _Ctx) -> dict:
    s = ctx.state
    hbr = ctx.held_basis_ratios
    p_rat = projection_matrix_rationals(s, hbr)
    out = {
        ("projection", "primes"): projection_ebk(tuning_projection(s, hbr), s.d),
        ("projection", "gens"): embedding_ebk(tuning_embedding(s, hbr), s.d, len(s.mapping)),
        ("projection", "canongens"): embedding_ebk(
            canonical_generator_embedding(s, hbr), s.d, ctx.canon.rc
        ),
        ("projection", "detempering"): ctx.r(
            ("projection", "detempering"), _proj_cols(ctx, p_rat, ctx.core.detemper_vectors)
        ),
        ("projection", "targets"): _ket_list(_proj_cols(ctx, p_rat, ctx.core.target_vectors), "⟩"),
    }
    if ctx.held:
        out[("projection", "held")] = _ket_list(_proj_cols(ctx, p_rat, ctx.held), "⟩")
    if ctx.interest:
        out[("projection", "interest")] = _ket_list(
            _proj_cols(ctx, p_rat, ctx.interest), "⟩", wrap=False
        )
    return out


@dataclass(frozen=True)
class _SsCtx:
    ml: tuple
    ss_primes: tuple
    mjl: tuple
    mlgl: tuple
    msl: tuple
    bl: tuple
    ss_tun: Tuning
    dL: int
    ss_prescaler: object


def _superspace_tuning(ctx: _Ctx) -> Tuning:
    derived = ctx.derived
    if derived is not None and derived.superspace_tun is not None:
        return derived.superspace_tun
    return superspace_tuning(
        ctx.state,
        ctx.scheme,
        ctx.nonprime_approach,
        generator_override=ctx.superspace_generator_override,
    )


def _derive_superspace(ctx: _Ctx) -> _SsCtx:
    s = ctx.state
    ss_primes = superspace_primes(ctx.db)
    return _SsCtx(
        superspace_mapping(s),
        ss_primes,
        superspace_just_mapping(ss_primes),
        superspace_self_map(s),
        mapping_to_superspace_generators(s),
        basis_in_superspace(ctx.db),
        _superspace_tuning(ctx),
        len(ss_primes),
        superspace_complexity_prescaler(s, ctx.scheme),
    )


def _ss_u(ctx: _Ctx) -> list:
    db = ctx.db
    return [
        None if u is None else lift_vectors_to_superspace(db, (u,))[0] for u in ctx.unchanged.basis
    ]


def _prescaled_ss(ssc: _SsCtx, vectors):
    return tuple(tuple(ssc.ss_prescaler[i] * v[i] for i in range(ssc.dL)) for v in vectors)


def _ss_prod(ctx: _Ctx, ssc: _SsCtx, vs):
    return ctx.sized(_prescaled_ss(ssc, lift_vectors_to_superspace(ctx.db, vs)))


def _ssp_cols(ctx: _Ctx, p_L, dL: int, vectors):
    cols = project_vectors(p_L, lift_vectors_to_superspace(ctx.db, vectors))
    return list(cols) if cols else [tuple(_DASH for _ in range(dL)) for _ in vectors]


def _ss_base(ctx: _Ctx, ssc: _SsCtx) -> dict:
    s = ctx.state
    db = ctx.db
    core = ctx.core
    ss_u = _ss_u(ctx)
    ss_u_mapped = [
        None if u is None else map_vectors_into_superspace_generators(s, (u,))[0]
        for u in ctx.unchanged.basis
    ]
    return {
        ("ss_vectors", "primes"): ctx.r(("ss_vectors", "primes"), ssc.bl),
        ("ss_vectors", "ssprimes"): ctx.r(("ss_vectors", "ssprimes"), ssc.mjl),
        ("ss_vectors", "commas"): _ket_list(
            list(lift_vectors_to_superspace(db, s.comma_basis)) + ss_u, "⟩"
        ),
        ("ss_vectors", "targets"): _ket_list(
            lift_vectors_to_superspace(db, core.target_vectors), "⟩"
        ),
        ("ss_vectors", "detempering"): _ket_list(
            lift_vectors_to_superspace(db, core.detemper_vectors), "⟩"
        ),
        ("ss_vectors", "interest"): _ket_list(
            lift_vectors_to_superspace(db, ctx.interest), "⟩", wrap=False
        ),
        ("ss_mapping", "ssprimes"): ctx.r(("ss_mapping", "ssprimes"), ssc.ml),
        ("ss_mapping", "primes"): ctx.r(("ss_mapping", "primes"), ssc.msl),
        ("ss_mapping", "ssgens"): ctx.r(("ss_mapping", "ssgens"), ssc.mlgl),
        ("ss_mapping", "commas"): _ket_list(
            list(map_vectors_into_superspace_generators(s, s.comma_basis)) + ss_u_mapped, "}"
        ),
        ("ss_mapping", "targets"): _ket_list(
            map_vectors_into_superspace_generators(s, core.target_vectors), "}"
        ),
        ("ss_mapping", "detempering"): ctx.r(
            ("ss_mapping", "detempering"),
            map_vectors_into_superspace_generators(s, core.detemper_vectors),
        ),
        ("ss_mapping", "interest"): _ket_list(
            map_vectors_into_superspace_generators(s, ctx.interest), "}", wrap=False
        ),
        ("tuning", "ssgens"): ctx.fmt.cents_genmap(ssc.ss_tun.generator_map),
        ("tuning", "ssprimes"): ctx.fmt.cents_map(ssc.ss_tun.tuning_map),
        ("just", "ssprimes"): ctx.fmt.cents_map(ssc.ss_tun.just_map),
        ("retune", "ssprimes"): ctx.fmt.cents_map(ssc.ss_tun.retuning_map),
    }


def _ss_held(ctx: _Ctx) -> dict:
    db = ctx.db
    held = ctx.held
    return {
        ("ss_vectors", "held"): _ket_list(lift_vectors_to_superspace(db, held), "⟩"),
        ("ss_mapping", "held"): _ket_list(
            map_vectors_into_superspace_generators(ctx.state, held), "}"
        ),
    }


def _ss_projection(ctx: _Ctx, ssc: _SsCtx) -> dict:
    s = ctx.state
    hbr = ctx.held_basis_ratios
    dL = ssc.dL
    core = ctx.core
    p_L = superspace_projection_matrix_rationals(s, hbr)
    proj_bl = project_vectors(p_L, ssc.bl) or [tuple(_DASH for _ in range(dL)) for _ in ssc.bl]
    out = {
        ("ss_projection", "ssprimes"): projection_ebk(superspace_tuning_projection(s, hbr), dL),
        ("ss_projection", "ssgens"): embedding_ebk(
            superspace_tuning_embedding(s, hbr), dL, superspace_rank(s)
        ),
        ("ss_projection", "primes"): ctx.r(("ss_projection", "primes"), proj_bl),
        ("ss_projection", "detempering"): ctx.r(
            ("ss_projection", "detempering"), _ssp_cols(ctx, p_L, dL, core.detemper_vectors)
        ),
        ("ss_projection", "commas"): _ket_list([(0,) * dL for _ in core.commas] + _ss_u(ctx), "⟩"),
        ("ss_projection", "targets"): _ket_list(_ssp_cols(ctx, p_L, dL, core.target_vectors), "⟩"),
    }
    if ctx.held:
        out[("ss_projection", "held")] = _ket_list(_ssp_cols(ctx, p_L, dL, ctx.held), "⟩")
    if ctx.interest:
        out[("ss_projection", "interest")] = _ket_list(
            _ssp_cols(ctx, p_L, dL, ctx.interest), "⟩", wrap=False
        )
    out[("projection", "ssgens")] = embedding_ebk(
        superspace_generator_embedding_display(s, hbr), s.d, superspace_rank(s)
    )
    out[("projection", "ssprimes")] = projection_ebk(
        superspace_prime_projection_display(s, hbr), s.d, cols=dL
    )
    return out


def _ss_units(dL: int) -> tuple:
    return tuple(tuple(1 if i == p else 0 for i in range(dL)) for p in range(dL))


def _ss_u_prescaled(ctx: _Ctx, ssc: _SsCtx) -> list:
    db = ctx.db
    return [
        None
        if u is None
        else ctx.sized(_prescaled_ss(ssc, lift_vectors_to_superspace(db, (u,))))[0]
        for u in ctx.unchanged.basis
    ]


def _ss_prescaling(ctx: _Ctx, ssc: _SsCtx) -> dict:
    fmt = ctx.fmt
    core = ctx.core
    dL = ssc.dL
    sf = ctx.prescale.size_factor
    ss_bare_size = (tuple(sf * w for w in ssc.ss_prescaler),) if sf else ()
    out = {
        ("prescaling", "ssprimes"): fmt.prescale(
            _prescaled_ss(ssc, _ss_units(dL)) + ss_bare_size, col="⟨]", outer="[⟩"
        ),
        ("prescaling", "primes"): fmt.prescale(
            ctx.sized(_prescaled_ss(ssc, ssc.bl)), col="[⟩", outer="⟨]"
        ),
        ("complexity", "ssprimes"): fmt.cents_map(ssc.ss_prescaler),
        ("complexity", "primes"): fmt.cents_map(ctx.complexities(core.prime_ratios)),
        ("prescaling", "commas"): fmt.prescale(
            list(_ss_prod(ctx, ssc, core.comma_basis)) + _ss_u_prescaled(ctx, ssc)
        ),
        ("prescaling", "detempering"): fmt.prescale(_ss_prod(ctx, ssc, core.detemper_vectors)),
        ("prescaling", "targets"): fmt.prescale(_ss_prod(ctx, ssc, core.target_vectors)),
    }
    if ctx.held:
        out[("prescaling", "held")] = fmt.prescale(_ss_prod(ctx, ssc, ctx.held))
    if ctx.interest:
        out[("prescaling", "interest")] = fmt.prescale(_ss_prod(ctx, ssc, ctx.interest), outer="")
    return out


def _superspace_values(ctx: _Ctx) -> dict:
    ssc = _derive_superspace(ctx)
    out = _ss_base(ctx, ssc)
    if ctx.held:
        out.update(_ss_held(ctx))
    if ctx.consolidate_v:
        out.update(_ss_projection(ctx, ssc))
    out.update(_ss_prescaling(ctx, ssc))
    return out


def plain_text_values(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
    target_spec: str = DEFAULT_TARGET_SPEC,
    held=(),
    interest=(),
    generator_tuning=None,
    target_override=None,
    nonprime_approach: str = "",
    superspace: bool = False,
    superspace_generator_override=None,
    consolidate_v: bool = False,
    held_basis_ratios=(),
    custom_prescaler=None,
    derived: DerivedQuantities | None = None,
    decimals: bool = True,
) -> dict[tuple[str, str], str]:
    inp = _Inputs(
        state,
        scheme,
        target_spec,
        held,
        interest,
        generator_tuning,
        target_override,
        nonprime_approach,
        superspace,
        superspace_generator_override,
        consolidate_v,
        held_basis_ratios,
        custom_prescaler,
        derived,
        decimals,
    )
    ctx = _build_context(inp)
    values = _base_structural(ctx)
    values.update(_base_sizes(ctx))
    values.update(_base_prescale_complexity(ctx))
    if ctx.held:
        values.update(_held_values(ctx))
    if ctx.interest:
        values.update(_interest_values(ctx))
    if ctx.consolidate_v:
        values.update(_projection_values(ctx))
    if ctx.superspace:
        values.update(_superspace_values(ctx))
    return values


_DASH = "—"


_EBK_OPEN = "[⟨{"
_EBK_CLOSE = "]⟩}"
_KET_CLOSE = "⟩}"
_TRANSPOSE = "ᵀ"


def _flatten_brackets(group: str) -> str:
    return "".join("[" if c in _EBK_OPEN else "]" if c in _EBK_CLOSE else c for c in group)


def _group_is_vector_based(group: str) -> bool:
    inner = group[1:-1].lstrip()
    if inner and inner[0] in _EBK_OPEN:
        return inner[0] == "["
    return group[-1] in _KET_CLOSE


def ebk_to_simple_matrix(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in _EBK_OPEN:
            depth, j = 0, i
            while j < n:
                if text[j] in _EBK_OPEN:
                    depth += 1
                elif text[j] in _EBK_CLOSE:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:
                out.append(text[i:])
                break
            group = text[i : j + 1]
            out.append(
                _flatten_brackets(group) + (_TRANSPOSE if _group_is_vector_based(group) else "")
            )
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def simple_matrix_to_ebk(text: str, vector_based: bool) -> str:
    text = text.replace(_TRANSPOSE, "")
    start = text.find("[")
    if start == -1:
        return text
    prefix, body = text[:start], text[start:]
    open_ch, close_ch = ("[", "⟩") if vector_based else ("⟨", "]")
    wrapped = body[1:].lstrip().startswith("[")
    out, depth = [], 0
    for c in body:
        if c == "[":
            depth += 1
            out.append("[" if (wrapped and depth == 1) else open_ch)
        elif c == "]":
            out.append("]" if (wrapped and depth == 1) else close_ch)
            depth -= 1
        else:
            out.append(c)
    return prefix + "".join(out)


def _ket_list(vectors, close: str, wrap: bool = True) -> str:
    return render_ebk(
        EbkConvention("list", "[" if wrap else "", "]" if wrap else "", "[", close, " "), vectors
    )


def projection_ebk(matrix, d: int, cols: int | None = None) -> str:
    cols = d if cols is None else cols
    grid = matrix if matrix is not None else [(_DASH,) * cols for _ in range(d)]
    return render_ebk(_STACK_ANGLE, grid)


def embedding_ebk(matrix, d: int, r: int) -> str:
    grid = matrix if matrix is not None else [(_DASH,) * r for _ in range(d)]
    return render_ebk(_EMBED, list(zip(*grid, strict=False)))


def _prescale_vector_list(
    vectors, col: str = "[⟩", outer: str = "[]", decimals: bool = True
) -> str:
    oo, oc = (outer[0], outer[1]) if outer else ("", "")
    structure = "stack" if col[0] == "⟨" else "list"
    conv = EbkConvention(structure, oo, oc, col[0], col[1], " ")
    return render_ebk(conv, vectors, fmt=lambda x: prescale_text(x, decimals))


def vector_list_pending_text(committed_vectors, pending) -> tuple[str, str, str]:
    committed = _ket_list(committed_vectors, "⟩")
    draft = "[" + " ".join(str(x) for x in pending if x is not None) + "⟩"
    return committed[:-1] + " ", draft, "]"


def mapping_pending_text(committed_ebk, pending) -> tuple[str, str, str]:
    draft = "⟨" + " ".join(str(x) for x in pending if x is not None) + "]"
    return committed_ebk[:-1] + " ", draft, "}"


def _cents_map(values, decimals: bool = True) -> str:
    return render_ebk(_MAP, values, fmt=lambda v: cents(v, decimals))


def _cents_list(values, wrap: bool = True, decimals: bool = True) -> str:
    return render_ebk(_SCALARS if wrap else _SCALARS_BARE, values, fmt=lambda v: cents(v, decimals))


def _cents_genmap(values, decimals: bool = True) -> str:
    return render_ebk(_GENMAP, values, fmt=lambda v: cents(v, decimals))
