from __future__ import annotations

from rtt.app.service.core import interval_sizes
from rtt.app.service.core_vectors import comma_ratios, mapped_intervals
from rtt.app.service.projection import (
    canonical_generator_embedding,
    project_vectors,
    projection_matrix_rationals,
    tuning_embedding,
    tuning_projection,
)
from rtt.app.service.state import mapping_ebk
from rtt.app.service.text_context import _Ctx, _identity
from rtt.app.service.text_conventions import _DASH
from rtt.app.service.text_format import _ket_list, embedding_ebk, projection_ebk


def _base_structural(context: _Ctx) -> dict:
    s = context.state
    db = context.db
    core = context.core
    canon = context.canon
    un = context.unchanged
    return {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        ("vectors", "commas"): _ket_list(list(core.comma_basis) + un.basis, "⟩"),
        ("projection", "commas"): _ket_list([(0,) * s.d for _ in core.commas] + un.basis, "⟩"),
        ("scaling_factors", "commas"): context.r(
            ("scaling_factors", "commas"), ["0"] * len(core.commas) + un.scaling
        ),
        ("vectors", "targets"): _ket_list(core.target_vectors, "⟩"),
        ("vectors", "detempering"): _ket_list(core.detemper_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(s),
        ("mapping", "commas"): _ket_list(
            list(zip(*core.mapped_comma, strict=False)) + un.mapped_cols, "}"
        ),
        ("mapping", "targets"): _ket_list(zip(*core.mapped, strict=False), "}"),
        ("vectors", "primes"): context.r(("vectors", "primes"), _identity(s.d)),
        ("mapping", "gens"): context.r(("mapping", "gens"), _identity(len(s.mapping))),
        ("mapping", "detempering"): context.r(
            ("mapping", "detempering"), _identity(len(s.mapping))
        ),
        ("canon", "primes"): context.r(("canon", "primes"), canon.mapping),
        ("canon", "gens"): context.r(("canon", "gens"), canon.form),
        ("canon", "canongens"): context.r(("canon", "canongens"), _identity(canon.rc)),
        ("canon", "detempering"): context.r(
            ("canon", "detempering"), list(zip(*canon.mapped_detempering, strict=False))
        ),
        ("canon", "commas"): _ket_list(
            list(zip(*canon.mapped_comma, strict=False)) + canon.u_mapped_cols, "}"
        ),
        ("canon", "targets"): _ket_list(zip(*canon.mapped, strict=False), "}"),
        ("mapping", "canongens"): context.r(("mapping", "canongens"), canon.inverse_form),
    }


def _canon_gen_sizes(context: _Ctx) -> list:
    tuning_map = context.core.tuning_map
    inverse_form = context.canon.inverse_form
    nrow = len(context.state.mapping)
    return [
        sum(tuning_map.generator_map[k] * inverse_form[k][j] for k in range(nrow))
        for j in range(context.canon.rc)
    ]


def _base_sizes(context: _Ctx) -> dict:
    core = context.core
    un = context.unchanged
    tuning_map = core.tuning_map
    fmt = context.fmt
    return {
        ("tuning", "canongens"): fmt.cents_genmap(_canon_gen_sizes(context)),
        ("tuning", "gens"): fmt.cents_genmap(tuning_map.generator_map),
        ("tuning", "primes"): fmt.cents_map(tuning_map.tuning_map),
        ("tuning", "commas"): fmt.cents_list(list(core.comma_sizes.tempered) + un.tempered),
        ("tuning", "detempering"): fmt.cents_genmap(core.detemper_sizes.tempered),
        ("tuning", "targets"): fmt.cents_list(core.target_sizes.tempered),
        ("just", "primes"): fmt.cents_map(tuning_map.just_map),
        ("just", "commas"): fmt.cents_list(list(core.comma_sizes.just) + un.just),
        ("just", "detempering"): fmt.cents_list(core.detemper_sizes.just),
        ("just", "targets"): fmt.cents_list(core.target_sizes.just),
        ("retune", "primes"): fmt.cents_map(tuning_map.retuning_map),
        ("retune", "commas"): fmt.cents_list(list(core.comma_sizes.errors) + un.errors),
        ("retune", "detempering"): fmt.cents_list(core.detemper_sizes.errors),
        ("retune", "targets"): fmt.cents_list(core.target_sizes.errors),
        ("damage", "targets"): fmt.cents_list(core.target_sizes.damage),
    }


def _base_prescale_complexity(context: _Ctx) -> dict:
    core = context.core
    un = context.unchanged
    pre = context.prescale
    fmt = context.fmt
    return {
        ("prescaling", "primes"): fmt.prescale(
            pre.bare_rows + list(pre.bare_size_row), col="⟨]", outer="[⟩"
        ),
        ("prescaling", "commas"): fmt.prescale(
            list(context.sized(context.prescaled(core.comma_basis))) + un.prescaled
        ),
        ("prescaling", "detempering"): fmt.prescale(
            context.sized(context.prescaled(core.detemper_vectors))
        ),
        ("prescaling", "targets"): fmt.prescale(
            context.sized(context.prescaled(core.target_vectors))
        ),
        ("complexity", "primes"): fmt.cents_map(context.complexities(core.prime_ratios)),
        ("complexity", "commas"): fmt.cents_list(
            list(context.complexities(core.commas)) + un.comps
        ),
        ("complexity", "detempering"): fmt.cents_list(context.complexities(core.detemper_ratios)),
        ("complexity", "targets"): fmt.cents_list(context.complexities(core.targets)),
        ("weight", "targets"): fmt.cents_list(core.target_weights),
    }


def _held_values(context: _Ctx) -> dict:
    s = context.state
    db = context.db
    held = context.held
    held_ratios = context.core.held_ratios
    fmt = context.fmt
    held_sizes = interval_sizes(context.core.tuning_map, held_ratios, db)
    held_mapped = mapped_intervals(s.mapping, held_ratios, db)
    canon_held_mapped = mapped_intervals(context.canon.mapping, held_ratios, db)
    return {
        ("vectors", "held"): _ket_list(held, "⟩"),
        ("mapping", "held"): _ket_list(zip(*held_mapped, strict=False), "}"),
        ("canon", "held"): _ket_list(zip(*canon_held_mapped, strict=False), "}"),
        ("tuning", "held"): fmt.cents_list(held_sizes.tempered),
        ("just", "held"): fmt.cents_list(held_sizes.just),
        ("retune", "held"): fmt.cents_list(held_sizes.errors),
        ("prescaling", "held"): fmt.prescale(context.sized(context.prescaled(held))),
        ("complexity", "held"): fmt.cents_list(context.complexities(held_ratios)),
    }


def _interest_values(context: _Ctx) -> dict:
    s = context.state
    db = context.db
    interest = context.interest
    fmt = context.fmt
    interest_ratios = comma_ratios(interest, db)
    interest_mapped = mapped_intervals(s.mapping, interest_ratios, db)
    canon_interest_mapped = mapped_intervals(context.canon.mapping, interest_ratios, db)
    interest_sizes = interval_sizes(context.core.tuning_map, interest_ratios, db)
    return {
        ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
        ("mapping", "interest"): _ket_list(zip(*interest_mapped, strict=False), "}", wrap=False),
        ("canon", "interest"): _ket_list(
            zip(*canon_interest_mapped, strict=False), "}", wrap=False
        ),
        ("tuning", "interest"): fmt.cents_list(interest_sizes.tempered, wrap=False),
        ("just", "interest"): fmt.cents_list(interest_sizes.just, wrap=False),
        ("retune", "interest"): fmt.cents_list(interest_sizes.errors, wrap=False),
        ("prescaling", "interest"): fmt.prescale(
            context.sized(context.prescaled(interest)), outer=""
        ),
        ("complexity", "interest"): fmt.cents_list(
            context.complexities(interest_ratios), wrap=False
        ),
    }


def _projection_cols(context: _Ctx, p_rat, vectors):
    cols = project_vectors(p_rat, vectors)
    return list(cols) if cols else [tuple(_DASH for _ in range(context.d)) for _ in vectors]


def _projection_values(context: _Ctx) -> dict:
    s = context.state
    hbr = context.held_basis_ratios
    p_rat = projection_matrix_rationals(s, hbr)
    out = {
        ("projection", "primes"): projection_ebk(tuning_projection(s, hbr), s.d),
        ("projection", "gens"): embedding_ebk(tuning_embedding(s, hbr), s.d, len(s.mapping)),
        ("projection", "canongens"): embedding_ebk(
            canonical_generator_embedding(s, hbr), s.d, context.canon.rc
        ),
        ("projection", "detempering"): context.r(
            ("projection", "detempering"),
            _projection_cols(context, p_rat, context.core.detemper_vectors),
        ),
        ("projection", "targets"): _ket_list(
            _projection_cols(context, p_rat, context.core.target_vectors), "⟩"
        ),
    }
    if context.held:
        out[("projection", "held")] = _ket_list(_projection_cols(context, p_rat, context.held), "⟩")
    if context.interest:
        out[("projection", "interest")] = _ket_list(
            _projection_cols(context, p_rat, context.interest), "⟩", wrap=False
        )
    return out
