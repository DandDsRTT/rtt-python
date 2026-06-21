from __future__ import annotations

from collections import namedtuple
from dataclasses import dataclass
from functools import partial

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
    inverse_form_matrix,
    interval_complexities,
    interval_sizes,
    interval_weights,
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
    _cents_map = partial(_CENTS_MAP, decimals=decimals)
    _cents_list = partial(_CENTS_LIST, decimals=decimals)
    _cents_genmap = partial(_CENTS_GENMAP, decimals=decimals)
    _prescale_vector_list = partial(_PRESCALE_VECTOR_LIST, decimals=decimals)

    def _R(key, data, fmt=str):
        return render_ebk(ebk_convention(*key, superspace=superspace), data, fmt)

    db = state.domain_basis
    targets = (
        derived.targets
        if derived
        else displayed_targets(state, scheme, target_spec, target_override)
    )
    comma_basis = state.comma_basis if state.n else ()
    commas = comma_ratios(comma_basis, db)
    mapped = mapped_intervals(state.mapping, targets, db)
    mapped_comma = mapped_commas(state.mapping, comma_basis)
    target_vectors = target_interval_vectors(targets, state.d, db)
    held_ratios = comma_ratios(held, db) if held else ()
    if derived is not None:
        tun = derived.tun
    elif generator_tuning is not None and len(generator_tuning) == len(state.mapping):
        tun = tuning_from_generators(state.mapping, generator_tuning, db)
    else:
        tun = tuning(
            state.mapping,
            scheme,
            db,
            nonprime_approach,
            held=held_ratios,
            prescaler_override=custom_prescaler,
            targets=target_override,
        )
    target_damage_weights = (
        derived.target_weights
        if derived
        else interval_weights(
            state.mapping, scheme, targets, domain_basis=db, prescaler_override=custom_prescaler
        )
    )
    target_sizes = (
        derived.target_sizes
        if derived
        else interval_sizes(tun, targets, db, weights=target_damage_weights)
    )
    comma_sizes = derived.comma_sizes if derived else interval_sizes(tun, commas, db)
    detemper_ratios = generators(state.mapping, db)
    detemper_sizes = interval_sizes(tun, detemper_ratios, db)
    detemper_vectors = generator_detempering(state.mapping)
    prime_ratios = tuple(element_ratio(e) for e in db)
    prescaler = complexity_prescaler(
        state.mapping,
        scheme,
        override=custom_prescaler,
        domain_basis=db,
        nonprime_approach=nonprime_approach,
    )
    prescaler_is_matrix = bool(prescaler) and isinstance(prescaler[0], (tuple, list))
    size_factor = complexity_size_factor(scheme)

    def _prescaled(vectors):
        if prescaler_is_matrix:
            return tuple(
                tuple(sum(prescaler[i][k] * v[k] for k in range(state.d)) for i in range(state.d))
                for v in vectors
            )
        return tuple(tuple(prescaler[i] * v[i] for i in range(state.d)) for v in vectors)

    def _sized(cols):
        if not size_factor:
            return cols
        return tuple(col + (size_factor * sum(col),) for col in cols)

    if prescaler_is_matrix:
        bare_rows = [tuple(prescaler[i]) for i in range(state.d)]
    else:
        bare_rows = [
            tuple(prescaler[i] if k == i else 0 for k in range(state.d)) for i in range(state.d)
        ]
    bare_size_row = (
        (tuple(size_factor * sum(col) for col in zip(*bare_rows)),) if size_factor else ()
    )
    weight_text = _cents_list(target_damage_weights)
    tp_text = _ket_list(target_vectors, "⟩")
    bare_x_text = _prescale_vector_list(bare_rows + list(bare_size_row), col="⟨]", outer="[⟩")
    complexity_text = _cents_list(
        interval_complexities(
            state.mapping, scheme, targets, domain_basis=db, prescaler_override=custom_prescaler
        )
    )
    damage_text = _cents_list(target_sizes.damage)
    udata = (
        unchanged_interval_data(state, held_basis_ratios, tun, scheme, db, custom_prescaler)
        if consolidate_v
        else None
    )
    if udata is not None:
        nrow = len(state.mapping)
        u_basis = list(udata.basis)
        u_mapped_cols = [
            None if udata.basis[j] is None else tuple(udata.mapped[i][j] for i in range(nrow))
            for j in range(len(udata.basis))
        ]
        u_prescaled = [None if u is None else _sized(_prescaled((u,)))[0] for u in udata.basis]
        u_tempered, u_just, u_errors = (
            list(udata.sizes.tempered),
            list(udata.sizes.just),
            list(udata.sizes.errors),
        )
        u_comps = list(udata.complexities)
        u_scaling = [_DASH if v is None else "1" for v in udata.basis]
    else:
        u_basis = u_mapped_cols = u_prescaled = u_tempered = u_just = u_errors = u_comps = (
            u_scaling
        ) = []
    canon_mapping = canonical_mapping(state.mapping)
    rc = len(canon_mapping)
    canon_form = form_matrix(state.mapping)
    canon_inverse_form = inverse_form_matrix(state.mapping)
    canon_mapped = mapped_intervals(canon_mapping, targets, db)
    canon_mapped_comma = mapped_commas(canon_mapping, comma_basis)
    canon_mapped_detempering = mapped_commas(canon_mapping, detemper_vectors)
    canon_u_mapped_cols = [
        None
        if u is None
        else tuple(sum(canon_mapping[i][p] * u[p] for p in range(state.d)) for i in range(rc))
        for u in u_basis
    ]

    def _identity(n):
        return [[1 if i == k else 0 for k in range(n)] for i in range(n)]

    values = {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        ("vectors", "commas"): _ket_list(list(comma_basis) + u_basis, "⟩"),
        ("projection", "commas"): _ket_list([(0,) * state.d for _ in commas] + u_basis, "⟩"),
        ("scaling_factors", "commas"): _R(
            ("scaling_factors", "commas"), ["0"] * len(commas) + u_scaling
        ),
        ("vectors", "targets"): tp_text,
        ("vectors", "detempering"): _ket_list(detemper_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(state),
        ("mapping", "commas"): _ket_list(list(zip(*mapped_comma)) + u_mapped_cols, "}"),
        ("mapping", "targets"): _ket_list(zip(*mapped), "}"),
        ("vectors", "primes"): _R(("vectors", "primes"), _identity(state.d)),
        ("mapping", "gens"): _R(("mapping", "gens"), _identity(len(state.mapping))),
        ("mapping", "detempering"): _R(("mapping", "detempering"), _identity(len(state.mapping))),
        ("canon", "primes"): _R(("canon", "primes"), canon_mapping),
        ("canon", "gens"): _R(("canon", "gens"), canon_form),
        ("canon", "canongens"): _R(("canon", "canongens"), _identity(rc)),
        ("canon", "detempering"): _R(
            ("canon", "detempering"), list(zip(*canon_mapped_detempering))
        ),
        ("canon", "commas"): _ket_list(list(zip(*canon_mapped_comma)) + canon_u_mapped_cols, "}"),
        ("canon", "targets"): _ket_list(zip(*canon_mapped), "}"),
        ("mapping", "canongens"): _R(("mapping", "canongens"), canon_inverse_form),
        ("tuning", "canongens"): _cents_genmap(
            [
                sum(
                    tun.generator_map[k] * canon_inverse_form[k][j]
                    for k in range(len(state.mapping))
                )
                for j in range(rc)
            ]
        ),
        ("tuning", "gens"): _cents_genmap(tun.generator_map),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(list(comma_sizes.tempered) + u_tempered),
        ("tuning", "detempering"): _cents_genmap(detemper_sizes.tempered),
        ("tuning", "targets"): _cents_list(target_sizes.tempered),
        ("just", "primes"): _cents_map(tun.just_map),
        ("just", "commas"): _cents_list(list(comma_sizes.just) + u_just),
        ("just", "detempering"): _cents_list(detemper_sizes.just),
        ("just", "targets"): _cents_list(target_sizes.just),
        ("retune", "primes"): _cents_map(tun.retuning_map),
        ("retune", "commas"): _cents_list(list(comma_sizes.errors) + u_errors),
        ("retune", "detempering"): _cents_list(detemper_sizes.errors),
        ("retune", "targets"): _cents_list(target_sizes.errors),
        ("damage", "targets"): damage_text,
        ("prescaling", "primes"): bare_x_text,
        ("prescaling", "commas"): _prescale_vector_list(
            list(_sized(_prescaled(comma_basis))) + u_prescaled
        ),
        ("prescaling", "detempering"): _prescale_vector_list(_sized(_prescaled(detemper_vectors))),
        ("prescaling", "targets"): _prescale_vector_list(_sized(_prescaled(target_vectors))),
        ("complexity", "primes"): _cents_map(
            interval_complexities(
                state.mapping,
                scheme,
                prime_ratios,
                domain_basis=db,
                prescaler_override=custom_prescaler,
            )
        ),
        ("complexity", "commas"): _cents_list(
            list(
                interval_complexities(
                    state.mapping,
                    scheme,
                    commas,
                    domain_basis=db,
                    prescaler_override=custom_prescaler,
                )
            )
            + u_comps
        ),
        ("complexity", "detempering"): _cents_list(
            interval_complexities(
                state.mapping,
                scheme,
                detemper_ratios,
                domain_basis=db,
                prescaler_override=custom_prescaler,
            )
        ),
        ("complexity", "targets"): complexity_text,
        ("weight", "targets"): weight_text,
    }
    if held:
        held_sizes = interval_sizes(tun, held_ratios, db)
        held_mapped = mapped_intervals(state.mapping, held_ratios, db)
        canon_held_mapped = mapped_intervals(canon_mapping, held_ratios, db)
        values.update(
            {
                ("vectors", "held"): _ket_list(held, "⟩"),
                ("mapping", "held"): _ket_list(zip(*held_mapped), "}"),
                ("canon", "held"): _ket_list(zip(*canon_held_mapped), "}"),
                ("tuning", "held"): _cents_list(held_sizes.tempered),
                ("just", "held"): _cents_list(held_sizes.just),
                ("retune", "held"): _cents_list(held_sizes.errors),
                ("prescaling", "held"): _prescale_vector_list(_sized(_prescaled(held))),
                ("complexity", "held"): _cents_list(
                    interval_complexities(
                        state.mapping,
                        scheme,
                        held_ratios,
                        domain_basis=db,
                        prescaler_override=custom_prescaler,
                    )
                ),
            }
        )
    if interest:
        interest_ratios = comma_ratios(interest, db)
        interest_mapped = mapped_intervals(state.mapping, interest_ratios, db)
        canon_interest_mapped = mapped_intervals(canon_mapping, interest_ratios, db)
        interest_sizes = interval_sizes(tun, interest_ratios, db)
        values.update(
            {
                ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
                ("mapping", "interest"): _ket_list(zip(*interest_mapped), "}", wrap=False),
                ("canon", "interest"): _ket_list(zip(*canon_interest_mapped), "}", wrap=False),
                ("tuning", "interest"): _cents_list(interest_sizes.tempered, wrap=False),
                ("just", "interest"): _cents_list(interest_sizes.just, wrap=False),
                ("retune", "interest"): _cents_list(interest_sizes.errors, wrap=False),
                ("prescaling", "interest"): _prescale_vector_list(
                    _sized(_prescaled(interest)), outer=""
                ),
                ("complexity", "interest"): _cents_list(
                    interval_complexities(
                        state.mapping,
                        scheme,
                        interest_ratios,
                        domain_basis=db,
                        prescaler_override=custom_prescaler,
                    ),
                    wrap=False,
                ),
            }
        )
    if consolidate_v:
        values[("projection", "primes")] = projection_ebk(
            tuning_projection(state, held_basis_ratios), state.d
        )
        values[("projection", "gens")] = embedding_ebk(
            tuning_embedding(state, held_basis_ratios), state.d, len(state.mapping)
        )
        values[("projection", "canongens")] = embedding_ebk(
            canonical_generator_embedding(state, held_basis_ratios), state.d, rc
        )
        p_rat = projection_matrix_rationals(state, held_basis_ratios)

        def _proj_cols(vectors):
            cols = project_vectors(p_rat, vectors)
            return list(cols) if cols else [tuple(_DASH for _ in range(state.d)) for _ in vectors]

        values[("projection", "detempering")] = _R(
            ("projection", "detempering"), _proj_cols(detemper_vectors)
        )
        values[("projection", "targets")] = _ket_list(_proj_cols(target_vectors), "⟩")
        if held:
            values[("projection", "held")] = _ket_list(_proj_cols(held), "⟩")
        if interest:
            values[("projection", "interest")] = _ket_list(_proj_cols(interest), "⟩", wrap=False)
    if superspace:
        db = state.domain_basis
        ml = superspace_mapping(state)
        ss_primes = superspace_primes(db)
        mjl = superspace_just_mapping(ss_primes)
        mlgl = superspace_self_map(state)
        msl = mapping_to_superspace_generators(state)
        bl = basis_in_superspace(db)
        ss_tun = (
            derived.superspace_tun
            if derived is not None and derived.superspace_tun is not None
            else superspace_tuning(
                state, scheme, nonprime_approach, generator_override=superspace_generator_override
            )
        )

        C_L = lift_vectors_to_superspace(db, state.comma_basis)
        T_L = lift_vectors_to_superspace(db, target_vectors)
        I_L = lift_vectors_to_superspace(db, interest)
        D_L = lift_vectors_to_superspace(db, detemper_vectors)
        mapped_C = map_vectors_into_superspace_generators(state, state.comma_basis)
        mapped_T = map_vectors_into_superspace_generators(state, target_vectors)
        mapped_I = map_vectors_into_superspace_generators(state, interest)
        mapped_D = map_vectors_into_superspace_generators(state, detemper_vectors)
        ss_u = [None if u is None else lift_vectors_to_superspace(db, (u,))[0] for u in u_basis]
        ss_u_mapped = [
            None if u is None else map_vectors_into_superspace_generators(state, (u,))[0]
            for u in u_basis
        ]
        values.update(
            {
                ("ss_vectors", "primes"): _R(("ss_vectors", "primes"), bl),
                ("ss_vectors", "ssprimes"): _R(("ss_vectors", "ssprimes"), mjl),
                ("ss_vectors", "commas"): _ket_list(list(C_L) + ss_u, "⟩"),
                ("ss_vectors", "targets"): _ket_list(T_L, "⟩"),
                ("ss_vectors", "detempering"): _ket_list(D_L, "⟩"),
                ("ss_vectors", "interest"): _ket_list(I_L, "⟩", wrap=False),
                ("ss_mapping", "ssprimes"): _R(("ss_mapping", "ssprimes"), ml),
                ("ss_mapping", "primes"): _R(("ss_mapping", "primes"), msl),
                ("ss_mapping", "ssgens"): _R(("ss_mapping", "ssgens"), mlgl),
                ("ss_mapping", "commas"): _ket_list(list(mapped_C) + ss_u_mapped, "}"),
                ("ss_mapping", "targets"): _ket_list(mapped_T, "}"),
                ("ss_mapping", "detempering"): _R(("ss_mapping", "detempering"), mapped_D),
                ("ss_mapping", "interest"): _ket_list(mapped_I, "}", wrap=False),
                ("tuning", "ssgens"): _cents_genmap(ss_tun.generator_map),
                ("tuning", "ssprimes"): _cents_map(ss_tun.tuning_map),
                ("just", "ssprimes"): _cents_map(ss_tun.just_map),
                ("retune", "ssprimes"): _cents_map(ss_tun.retuning_map),
            }
        )
        if held:
            values[("ss_vectors", "held")] = _ket_list(lift_vectors_to_superspace(db, held), "⟩")
            values[("ss_mapping", "held")] = _ket_list(
                map_vectors_into_superspace_generators(state, held), "}"
            )
        if consolidate_v:
            dL = len(ss_primes)
            p_L = superspace_projection_matrix_rationals(state, held_basis_ratios)

            def _ssp_cols(vectors):
                cols = project_vectors(p_L, lift_vectors_to_superspace(db, vectors))
                return list(cols) if cols else [tuple(_DASH for _ in range(dL)) for _ in vectors]

            proj_bl = project_vectors(p_L, bl) or [tuple(_DASH for _ in range(dL)) for _ in bl]
            values[("ss_projection", "ssprimes")] = projection_ebk(
                superspace_tuning_projection(state, held_basis_ratios), dL
            )
            values[("ss_projection", "ssgens")] = embedding_ebk(
                superspace_tuning_embedding(state, held_basis_ratios), dL, superspace_rank(state)
            )
            values[("ss_projection", "primes")] = _R(("ss_projection", "primes"), proj_bl)
            values[("ss_projection", "detempering")] = _R(
                ("ss_projection", "detempering"), _ssp_cols(detemper_vectors)
            )
            values[("ss_projection", "commas")] = _ket_list([(0,) * dL for _ in commas] + ss_u, "⟩")
            values[("ss_projection", "targets")] = _ket_list(_ssp_cols(target_vectors), "⟩")
            if held:
                values[("ss_projection", "held")] = _ket_list(_ssp_cols(held), "⟩")
            if interest:
                values[("ss_projection", "interest")] = _ket_list(
                    _ssp_cols(interest), "⟩", wrap=False
                )
            values[("projection", "ssgens")] = embedding_ebk(
                superspace_generator_embedding_display(state, held_basis_ratios),
                state.d,
                superspace_rank(state),
            )
            values[("projection", "ssprimes")] = projection_ebk(
                superspace_prime_projection_display(state, held_basis_ratios), state.d, cols=dL
            )
        ss_prescaler = superspace_complexity_prescaler(state, scheme)
        dL = len(ss_primes)
        ss_units = tuple(tuple(1 if i == p else 0 for i in range(dL)) for p in range(dL))

        def _prescaled_ss(vectors):
            return tuple(tuple(ss_prescaler[i] * v[i] for i in range(dL)) for v in vectors)

        ss_bare_size = (tuple(size_factor * w for w in ss_prescaler),) if size_factor else ()
        elem_ratios = tuple(element_ratio(e) for e in db)
        values.update(
            {
                ("prescaling", "ssprimes"): _prescale_vector_list(
                    _prescaled_ss(ss_units) + ss_bare_size, col="⟨]", outer="[⟩"
                ),
                ("prescaling", "primes"): _prescale_vector_list(
                    _sized(_prescaled_ss(bl)), col="[⟩", outer="⟨]"
                ),
                ("complexity", "ssprimes"): _cents_map(ss_prescaler),
                ("complexity", "primes"): _cents_map(
                    interval_complexities(
                        state.mapping,
                        scheme,
                        elem_ratios,
                        domain_basis=db,
                        prescaler_override=custom_prescaler,
                    )
                ),
            }
        )
        _ss_prod = lambda vs: _sized(_prescaled_ss(lift_vectors_to_superspace(db, vs)))
        ss_u_prescaled = [
            None if u is None else _sized(_prescaled_ss(lift_vectors_to_superspace(db, (u,))))[0]
            for u in u_basis
        ]
        values[("prescaling", "commas")] = _prescale_vector_list(
            list(_ss_prod(comma_basis)) + ss_u_prescaled
        )
        values[("prescaling", "detempering")] = _prescale_vector_list(_ss_prod(detemper_vectors))
        values[("prescaling", "targets")] = _prescale_vector_list(_ss_prod(target_vectors))
        if held:
            values[("prescaling", "held")] = _prescale_vector_list(_ss_prod(held))
        if interest:
            values[("prescaling", "interest")] = _prescale_vector_list(_ss_prod(interest), outer="")
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
    return render_ebk(_EMBED, list(zip(*grid)))


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


# Python treats a name assigned anywhere in a function as local throughout it, so
# plain_text_values can't write `_cents_map = partial(_cents_map, ...)` (the right-hand
# _cents_map would be the as-yet-unbound local). These distinct global aliases give that
# rebinding something to read.
_CENTS_MAP = _cents_map
_CENTS_LIST = _cents_list
_CENTS_GENMAP = _cents_genmap
_PRESCALE_VECTOR_LIST = _prescale_vector_list
