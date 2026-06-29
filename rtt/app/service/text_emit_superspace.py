from __future__ import annotations

from dataclasses import dataclass

from rtt.app.service.core import Tuning
from rtt.app.service.projection import (
    project_vectors,
)
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
from rtt.app.service.text_context import _TextContext
from rtt.app.service.text_conventions import _DASH
from rtt.app.service.text_format import _ket_list, embedding_ebk, projection_ebk


@dataclass(frozen=True)
class _SuperspaceContext:
    superspace_mapping: tuple
    superspace_primes: tuple
    superspace_ji_mapping: tuple
    superspace_mapped_generators: tuple
    domain_to_superspace_generators_mapping: tuple
    basis_change_matrix: tuple
    superspace_tuning_map: Tuning
    superspace_dimensionality: int
    superspace_prescaler: object


def _superspace_tuning(context: _TextContext) -> Tuning:
    derived = context.derived
    if derived is not None and derived.superspace_tuning_map is not None:
        return derived.superspace_tuning_map
    return superspace_tuning(
        context.state,
        context.scheme,
        context.nonprime_approach,
        generator_override=context.superspace_generator_override,
    )


def _derive_superspace(context: _TextContext) -> _SuperspaceContext:
    s = context.state
    superspace_prime_basis = superspace_primes(context.domain_basis)
    return _SuperspaceContext(
        superspace_mapping(s),
        superspace_prime_basis,
        superspace_just_mapping(superspace_prime_basis),
        superspace_self_map(s),
        mapping_to_superspace_generators(s),
        basis_in_superspace(context.domain_basis),
        _superspace_tuning(context),
        len(superspace_prime_basis),
        superspace_complexity_prescaler(s, context.scheme),
    )


def _superspace_u(context: _TextContext) -> list:
    domain_basis = context.domain_basis
    return [
        None if u is None else lift_vectors_to_superspace(domain_basis, (u,))[0]
        for u in context.unchanged.basis
    ]


def _prescaled_superspace(superspace_context: _SuperspaceContext, vectors):
    return tuple(
        tuple(
            superspace_context.superspace_prescaler[i] * v[i]
            for i in range(superspace_context.superspace_dimensionality)
        )
        for v in vectors
    )


def _superspace_prod(context: _TextContext, superspace_context: _SuperspaceContext, vs):
    return context.sized(
        _prescaled_superspace(
            superspace_context, lift_vectors_to_superspace(context.domain_basis, vs)
        )
    )


def _superspace_prime_cols(context: _TextContext, p_L, superspace_dimensionality: int, vectors):
    cols = project_vectors(p_L, lift_vectors_to_superspace(context.domain_basis, vectors))
    return (
        list(cols)
        if cols
        else [tuple(_DASH for _ in range(superspace_dimensionality)) for _ in vectors]
    )


def _superspace_vector_rows(
    context: _TextContext, superspace_context: _SuperspaceContext, superspace_unchanged: list
) -> dict:
    s = context.state
    domain_basis = context.domain_basis
    core = context.core
    return {
        ("superspace_vectors", "primes"): context.render(
            ("superspace_vectors", "primes"), superspace_context.basis_change_matrix
        ),
        ("superspace_vectors", "superspace_primes"): context.render(
            ("superspace_vectors", "superspace_primes"), superspace_context.superspace_ji_mapping
        ),
        ("superspace_vectors", "commas"): _ket_list(
            list(lift_vectors_to_superspace(domain_basis, s.comma_basis)) + superspace_unchanged,
            "⟩",
        ),
        ("superspace_vectors", "targets"): _ket_list(
            lift_vectors_to_superspace(domain_basis, core.target_vectors), "⟩"
        ),
        ("superspace_vectors", "detempering"): _ket_list(
            lift_vectors_to_superspace(domain_basis, core.detemper_vectors), "⟩"
        ),
        ("superspace_vectors", "interest"): _ket_list(
            lift_vectors_to_superspace(domain_basis, context.interest), "⟩", wrap=False
        ),
    }


def _superspace_base(context: _TextContext, superspace_context: _SuperspaceContext) -> dict:
    s = context.state
    core = context.core
    superspace_unchanged = _superspace_u(context)
    superspace_unchanged_mapped = [
        None if u is None else map_vectors_into_superspace_generators(s, (u,))[0]
        for u in context.unchanged.basis
    ]
    return {
        **_superspace_vector_rows(context, superspace_context, superspace_unchanged),
        ("superspace_mapping", "superspace_primes"): context.render(
            ("superspace_mapping", "superspace_primes"), superspace_context.superspace_mapping
        ),
        ("superspace_mapping", "primes"): context.render(
            ("superspace_mapping", "primes"),
            superspace_context.domain_to_superspace_generators_mapping,
        ),
        ("superspace_mapping", "superspace_generators"): context.render(
            ("superspace_mapping", "superspace_generators"),
            superspace_context.superspace_mapped_generators,
        ),
        ("superspace_mapping", "commas"): _ket_list(
            list(map_vectors_into_superspace_generators(s, s.comma_basis))
            + superspace_unchanged_mapped,
            "}",
        ),
        ("superspace_mapping", "targets"): _ket_list(
            map_vectors_into_superspace_generators(s, core.target_vectors), "}"
        ),
        ("superspace_mapping", "detempering"): context.render(
            ("superspace_mapping", "detempering"),
            map_vectors_into_superspace_generators(s, core.detemper_vectors),
        ),
        ("superspace_mapping", "interest"): _ket_list(
            map_vectors_into_superspace_generators(s, context.interest), "}", wrap=False
        ),
        ("tuning", "superspace_generators"): context.formatter.cents_genmap(
            superspace_context.superspace_tuning_map.generator_map
        ),
        ("tuning", "superspace_primes"): context.formatter.cents_map(
            superspace_context.superspace_tuning_map.tuning_map
        ),
        ("just", "superspace_primes"): context.formatter.cents_map(
            superspace_context.superspace_tuning_map.just_map
        ),
        ("retune", "superspace_primes"): context.formatter.cents_map(
            superspace_context.superspace_tuning_map.retuning_map
        ),
    }


def _superspace_held(context: _TextContext) -> dict:
    domain_basis = context.domain_basis
    held = context.held
    return {
        ("superspace_vectors", "held"): _ket_list(
            lift_vectors_to_superspace(domain_basis, held), "⟩"
        ),
        ("superspace_mapping", "held"): _ket_list(
            map_vectors_into_superspace_generators(context.state, held), "}"
        ),
    }


def _superspace_projection(context: _TextContext, superspace_context: _SuperspaceContext) -> dict:
    s = context.state
    held_basis_ratios = context.held_basis_ratios
    superspace_dimensionality = superspace_context.superspace_dimensionality
    core = context.core
    p_L = superspace_projection_matrix_rationals(s, held_basis_ratios)
    projected_basis_lift = project_vectors(p_L, superspace_context.basis_change_matrix) or [
        tuple(_DASH for _ in range(superspace_dimensionality))
        for _ in superspace_context.basis_change_matrix
    ]
    out = {
        ("superspace_projection", "superspace_primes"): projection_ebk(
            superspace_tuning_projection(s, held_basis_ratios), superspace_dimensionality
        ),
        ("superspace_projection", "superspace_generators"): embedding_ebk(
            superspace_tuning_embedding(s, held_basis_ratios),
            superspace_dimensionality,
            superspace_rank(s),
        ),
        ("superspace_projection", "primes"): context.render(
            ("superspace_projection", "primes"), projected_basis_lift
        ),
        ("superspace_projection", "detempering"): context.render(
            ("superspace_projection", "detempering"),
            _superspace_prime_cols(context, p_L, superspace_dimensionality, core.detemper_vectors),
        ),
        ("superspace_projection", "commas"): _ket_list(
            [(0,) * superspace_dimensionality for _ in core.commas] + _superspace_u(context), "⟩"
        ),
        ("superspace_projection", "targets"): _ket_list(
            _superspace_prime_cols(context, p_L, superspace_dimensionality, core.target_vectors),
            "⟩",
        ),
    }
    if context.held:
        out[("superspace_projection", "held")] = _ket_list(
            _superspace_prime_cols(context, p_L, superspace_dimensionality, context.held), "⟩"
        )
    if context.interest:
        out[("superspace_projection", "interest")] = _ket_list(
            _superspace_prime_cols(context, p_L, superspace_dimensionality, context.interest),
            "⟩",
            wrap=False,
        )
    out.update(_domain_projection_into_superspace(s, held_basis_ratios, superspace_dimensionality))
    return out


def _domain_projection_into_superspace(s, held_basis_ratios, superspace_dimensionality) -> dict:
    return {
        ("projection", "superspace_generators"): embedding_ebk(
            superspace_generator_embedding_display(s, held_basis_ratios),
            s.dimensionality,
            superspace_rank(s),
        ),
        ("projection", "superspace_primes"): projection_ebk(
            superspace_prime_projection_display(s, held_basis_ratios),
            s.dimensionality,
            cols=superspace_dimensionality,
        ),
    }


def _superspace_units(superspace_dimensionality: int) -> tuple:
    return tuple(
        tuple(1 if i == p else 0 for i in range(superspace_dimensionality))
        for p in range(superspace_dimensionality)
    )


def _superspace_u_prescaled(context: _TextContext, superspace_context: _SuperspaceContext) -> list:
    domain_basis = context.domain_basis
    return [
        None
        if u is None
        else context.sized(
            _prescaled_superspace(
                superspace_context, lift_vectors_to_superspace(domain_basis, (u,))
            )
        )[0]
        for u in context.unchanged.basis
    ]


def _superspace_prescaling(context: _TextContext, superspace_context: _SuperspaceContext) -> dict:
    formatter = context.formatter
    core = context.core
    superspace_dimensionality = superspace_context.superspace_dimensionality
    sf = context.prescale.size_factor
    superspace_bare_size = (
        (tuple(sf * w for w in superspace_context.superspace_prescaler),) if sf else ()
    )
    out = {
        ("prescaling", "superspace_primes"): formatter.prescale(
            _prescaled_superspace(superspace_context, _superspace_units(superspace_dimensionality))
            + superspace_bare_size,
            col="⟨]",
            outer="[⟩",
        ),
        ("prescaling", "primes"): formatter.prescale(
            context.sized(
                _prescaled_superspace(superspace_context, superspace_context.basis_change_matrix)
            ),
            col="[⟩",
            outer="⟨]",
        ),
        ("complexity", "superspace_primes"): formatter.cents_map(
            superspace_context.superspace_prescaler
        ),
        ("complexity", "primes"): formatter.cents_map(context.complexities(core.prime_ratios)),
        ("prescaling", "commas"): formatter.prescale(
            list(_superspace_prod(context, superspace_context, core.comma_basis))
            + _superspace_u_prescaled(context, superspace_context)
        ),
        ("prescaling", "detempering"): formatter.prescale(
            _superspace_prod(context, superspace_context, core.detemper_vectors)
        ),
        ("prescaling", "targets"): formatter.prescale(
            _superspace_prod(context, superspace_context, core.target_vectors)
        ),
    }
    if context.held:
        out[("prescaling", "held")] = formatter.prescale(
            _superspace_prod(context, superspace_context, context.held)
        )
    if context.interest:
        out[("prescaling", "interest")] = formatter.prescale(
            _superspace_prod(context, superspace_context, context.interest), outer=""
        )
    return out


def _superspace_values(context: _TextContext) -> dict:
    superspace_context = _derive_superspace(context)
    out = _superspace_base(context, superspace_context)
    if context.held:
        out.update(_superspace_held(context))
    if context.consolidate_v:
        out.update(_superspace_projection(context, superspace_context))
    out.update(_superspace_prescaling(context, superspace_context))
    return out
