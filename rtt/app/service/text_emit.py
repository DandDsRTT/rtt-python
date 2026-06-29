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
from rtt.app.service.text_context import _identity, _TextContext
from rtt.app.service.text_conventions import _DASH
from rtt.app.service.text_format import _ket_list, embedding_ebk, projection_ebk


def _base_structural(context: _TextContext) -> dict:
    s = context.state
    domain_basis = context.domain_basis
    core = context.core
    canon = context.canon
    unchanged = context.unchanged
    return {
        ("quantities", "primes"): ".".join(str(e) for e in domain_basis),
        ("vectors", "commas"): _ket_list(list(core.comma_basis) + unchanged.basis, "⟩"),
        ("projection", "commas"): _ket_list(
            [(0,) * s.d for _ in core.commas] + unchanged.basis, "⟩"
        ),
        ("scaling_factors", "commas"): context.render(
            ("scaling_factors", "commas"), ["0"] * len(core.commas) + unchanged.scaling
        ),
        ("vectors", "targets"): _ket_list(core.target_vectors, "⟩"),
        ("vectors", "detempering"): _ket_list(core.detemper_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(s),
        ("mapping", "commas"): _ket_list(
            list(zip(*core.mapped_comma, strict=False)) + unchanged.mapped_cols, "}"
        ),
        ("mapping", "targets"): _ket_list(zip(*core.mapped, strict=False), "}"),
        ("vectors", "primes"): context.render(("vectors", "primes"), _identity(s.d)),
        ("mapping", "gens"): context.render(("mapping", "gens"), _identity(len(s.mapping))),
        ("mapping", "detempering"): context.render(
            ("mapping", "detempering"), _identity(len(s.mapping))
        ),
        ("canon", "primes"): context.render(("canon", "primes"), canon.mapping),
        ("canon", "gens"): context.render(("canon", "gens"), canon.form),
        ("canon", "canongens"): context.render(("canon", "canongens"), _identity(canon.rank)),
        ("canon", "detempering"): context.render(
            ("canon", "detempering"), list(zip(*canon.mapped_detempering, strict=False))
        ),
        ("canon", "commas"): _ket_list(
            list(zip(*canon.mapped_comma, strict=False)) + canon.u_mapped_cols, "}"
        ),
        ("canon", "targets"): _ket_list(zip(*canon.mapped, strict=False), "}"),
        ("mapping", "canongens"): context.render(("mapping", "canongens"), canon.inverse_form),
    }


def _canon_gen_sizes(context: _TextContext) -> list:
    tuning_map = context.core.tuning_map
    inverse_form = context.canon.inverse_form
    row_count = len(context.state.mapping)
    return [
        sum(tuning_map.generator_map[k] * inverse_form[k][j] for k in range(row_count))
        for j in range(context.canon.rank)
    ]


def _base_sizes(context: _TextContext) -> dict:
    core = context.core
    unchanged = context.unchanged
    tuning_map = core.tuning_map
    formatter = context.formatter
    return {
        ("tuning", "canongens"): formatter.cents_genmap(_canon_gen_sizes(context)),
        ("tuning", "gens"): formatter.cents_genmap(tuning_map.generator_map),
        ("tuning", "primes"): formatter.cents_map(tuning_map.tuning_map),
        ("tuning", "commas"): formatter.cents_list(
            list(core.comma_sizes.tempered) + unchanged.tempered
        ),
        ("tuning", "detempering"): formatter.cents_genmap(core.detemper_sizes.tempered),
        ("tuning", "targets"): formatter.cents_list(core.target_sizes.tempered),
        ("just", "primes"): formatter.cents_map(tuning_map.just_map),
        ("just", "commas"): formatter.cents_list(list(core.comma_sizes.just) + unchanged.just),
        ("just", "detempering"): formatter.cents_list(core.detemper_sizes.just),
        ("just", "targets"): formatter.cents_list(core.target_sizes.just),
        ("retune", "primes"): formatter.cents_map(tuning_map.retuning_map),
        ("retune", "commas"): formatter.cents_list(
            list(core.comma_sizes.errors) + unchanged.errors
        ),
        ("retune", "detempering"): formatter.cents_list(core.detemper_sizes.errors),
        ("retune", "targets"): formatter.cents_list(core.target_sizes.errors),
        ("damage", "targets"): formatter.cents_list(core.target_sizes.damage),
    }


def _base_prescale_complexity(context: _TextContext) -> dict:
    core = context.core
    unchanged = context.unchanged
    prescale = context.prescale
    formatter = context.formatter
    return {
        ("prescaling", "primes"): formatter.prescale(
            prescale.bare_rows + list(prescale.bare_size_row), col="⟨]", outer="[⟩"
        ),
        ("prescaling", "commas"): formatter.prescale(
            list(context.sized(context.prescaled(core.comma_basis))) + unchanged.prescaled
        ),
        ("prescaling", "detempering"): formatter.prescale(
            context.sized(context.prescaled(core.detemper_vectors))
        ),
        ("prescaling", "targets"): formatter.prescale(
            context.sized(context.prescaled(core.target_vectors))
        ),
        ("complexity", "primes"): formatter.cents_map(context.complexities(core.prime_ratios)),
        ("complexity", "commas"): formatter.cents_list(
            list(context.complexities(core.commas)) + unchanged.complexities
        ),
        ("complexity", "detempering"): formatter.cents_list(
            context.complexities(core.detemper_ratios)
        ),
        ("complexity", "targets"): formatter.cents_list(context.complexities(core.targets)),
        ("weight", "targets"): formatter.cents_list(core.target_weights),
    }


def _held_values(context: _TextContext) -> dict:
    s = context.state
    domain_basis = context.domain_basis
    held = context.held
    held_ratios = context.core.held_ratios
    formatter = context.formatter
    held_sizes = interval_sizes(context.core.tuning_map, held_ratios, domain_basis)
    held_mapped = mapped_intervals(s.mapping, held_ratios, domain_basis)
    canon_held_mapped = mapped_intervals(context.canon.mapping, held_ratios, domain_basis)
    return {
        ("vectors", "held"): _ket_list(held, "⟩"),
        ("mapping", "held"): _ket_list(zip(*held_mapped, strict=False), "}"),
        ("canon", "held"): _ket_list(zip(*canon_held_mapped, strict=False), "}"),
        ("tuning", "held"): formatter.cents_list(held_sizes.tempered),
        ("just", "held"): formatter.cents_list(held_sizes.just),
        ("retune", "held"): formatter.cents_list(held_sizes.errors),
        ("prescaling", "held"): formatter.prescale(context.sized(context.prescaled(held))),
        ("complexity", "held"): formatter.cents_list(context.complexities(held_ratios)),
    }


def _interest_values(context: _TextContext) -> dict:
    s = context.state
    domain_basis = context.domain_basis
    interest = context.interest
    formatter = context.formatter
    interest_ratios = comma_ratios(interest, domain_basis)
    interest_mapped = mapped_intervals(s.mapping, interest_ratios, domain_basis)
    canon_interest_mapped = mapped_intervals(context.canon.mapping, interest_ratios, domain_basis)
    interest_sizes = interval_sizes(context.core.tuning_map, interest_ratios, domain_basis)
    return {
        ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
        ("mapping", "interest"): _ket_list(zip(*interest_mapped, strict=False), "}", wrap=False),
        ("canon", "interest"): _ket_list(
            zip(*canon_interest_mapped, strict=False), "}", wrap=False
        ),
        ("tuning", "interest"): formatter.cents_list(interest_sizes.tempered, wrap=False),
        ("just", "interest"): formatter.cents_list(interest_sizes.just, wrap=False),
        ("retune", "interest"): formatter.cents_list(interest_sizes.errors, wrap=False),
        ("prescaling", "interest"): formatter.prescale(
            context.sized(context.prescaled(interest)), outer=""
        ),
        ("complexity", "interest"): formatter.cents_list(
            context.complexities(interest_ratios), wrap=False
        ),
    }


def _projection_cols(context: _TextContext, p_rat, vectors):
    cols = project_vectors(p_rat, vectors)
    return (
        list(cols)
        if cols
        else [tuple(_DASH for _ in range(context.dimensionality)) for _ in vectors]
    )


def _projection_values(context: _TextContext) -> dict:
    s = context.state
    hbr = context.held_basis_ratios
    p_rat = projection_matrix_rationals(s, hbr)
    out = {
        ("projection", "primes"): projection_ebk(tuning_projection(s, hbr), s.d),
        ("projection", "gens"): embedding_ebk(tuning_embedding(s, hbr), s.d, len(s.mapping)),
        ("projection", "canongens"): embedding_ebk(
            canonical_generator_embedding(s, hbr), s.d, context.canon.rank
        ),
        ("projection", "detempering"): context.render(
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
