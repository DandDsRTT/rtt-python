from __future__ import annotations

from dataclasses import dataclass

from rtt.app.service.core import Tuning, comma_ratios, interval_sizes, mapped_intervals
from rtt.app.service.projection import (
    canonical_generator_embedding,
    project_vectors,
    projection_matrix_rationals,
    tuning_embedding,
    tuning_projection,
)
from rtt.app.service.state import mapping_ebk
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
from rtt.app.service.text import _DASH, _ket_list, embedding_ebk, projection_ebk
from rtt.app.service.text_context import _Ctx, _identity


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
