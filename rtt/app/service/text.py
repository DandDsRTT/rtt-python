"""The plain-text (EBK) view: plain_text_values and its bracket-notation builders.

The grid and this text show the same numbers two ways; :class:`DerivedQuantities`
hands the grid's own derivations in so the two views structurally cannot diverge."""

from __future__ import annotations

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


@dataclass(frozen=True)
class DerivedQuantities:
    """The displayed quantities the grid has already derived, handed into
    :func:`plain_text_values` so the EBK text is built FROM the grid's own numbers
    rather than from a parallel re-derivation: divergence between the two views is
    structurally impossible, and the optimizer solve behind ``tun`` runs once per
    build instead of twice. ``superspace_tun`` rides along whenever the grid shows
    the chapter-9 block (None otherwise; the text then solves it itself)."""

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
    """Each value group's natural plain-text form, keyed by its ``(row, column)``
    tile (the same vocabulary the spreadsheet layout uses). The grid and this text
    show the same numbers two ways — the EBK string is the inline notation. ``held``
    (the held interval vectors), ``interest`` (the other-intervals-of-interest vectors),
    ``generator_tuning`` (a frozen manual tuning), ``target_override`` (a typed explicit
    target list), ``nonprime_approach`` (the nonprime-basis optimization trait) and
    ``custom_prescaler`` (the bare prescaler tile's hand-edited diagonal / matrix override)
    are threaded into the same tuning/weights/complexity/prescaling the grid builds, so the
    two views can't diverge. The grid passes ``derived`` — its own already-computed
    :class:`DerivedQuantities` — making that guarantee structural; a direct caller may
    omit it and this function derives the same quantities itself.

    ``decimals`` (the Show panel's decimals toggle) off rounds every cents/prescale value in the
    returned strings to the nearest integer, so the plain text matches the rounded grid. It is
    bound onto the cents/prescale formatters here so the many call sites below need no threading."""
    # rebind the shared formatters to this view's decimals setting (off → round to integers); the
    # call sites below stay verbatim, and the module-level _cents_map/etc. keep their 3-dp default.
    _cents_map = partial(_CENTS_MAP, decimals=decimals)
    _cents_list = partial(_CENTS_LIST, decimals=decimals)
    _cents_genmap = partial(_CENTS_GENMAP, decimals=decimals)
    _prescale_vector_list = partial(_PRESCALE_VECTOR_LIST, decimals=decimals)
    db = state.domain_basis
    targets = derived.targets if derived else \
        displayed_targets(state, scheme, target_spec, target_override)  # all-interval-aware, like the grid
    # the REAL comma basis: empty at full rank (n = 0), where state.comma_basis is just the trivial
    # zero comma — the grid shows no comma column there, so the plain text must show no comma vector
    # either (not a phantom [0 0 0⟩). Everything comma-side below reads this, like the grid's self.nc.
    comma_basis = state.comma_basis if state.n else ()
    commas = comma_ratios(comma_basis, db)
    mapped = mapped_intervals(state.mapping, targets, db)
    mapped_comma = mapped_commas(state.mapping, comma_basis)
    target_vectors = target_interval_vectors(targets, state.d, db)
    held_ratios = comma_ratios(held, db) if held else ()
    # match the grid's tuning exactly: the grid hands over its own solve when it built one;
    # otherwise a manual generator-tuning override drives the maps directly, else the
    # scheme's optimum holding the held intervals just
    if derived is not None:
        tun = derived.tun
    elif generator_tuning is not None and len(generator_tuning) == len(state.mapping):
        tun = tuning_from_generators(state.mapping, generator_tuning, db)
    else:  # a typed target-list override retunes the optimum, matching the grid's own tuning —
        # over the SAME nonprime approach + custom prescaler the grid threads (else the tuning rows
        # diverge from the grid's optimum under a hand-edited prescaler or a nonprime domain)
        tun = tuning(state.mapping, scheme, db, nonprime_approach, held=held_ratios,
                     prescaler_override=custom_prescaler, targets=target_override)
    # the target damage row is the scheme-weighted 𝐝 = |𝐞|·W (the same weights the weight row
    # shows and the optimizer minimizes), so the displayed damage tracks the unity/complexity/
    # simplicity slope rather than staying plain |error|. The custom prescaler rides into the
    # weights too (the grid passes it to interval_weights), so a hand-edited diagonal reweights here.
    target_damage_weights = derived.target_weights if derived else \
        interval_weights(state.mapping, scheme, targets, domain_basis=db,
                         prescaler_override=custom_prescaler)
    target_sizes = derived.target_sizes if derived else \
        interval_sizes(tun, targets, db, weights=target_damage_weights)
    comma_sizes = derived.comma_sizes if derived else \
        interval_sizes(tun, commas, db)  # comma sizes, like the grid's commas column
    detemper_ratios = generators(state.mapping, db)  # the detempering as ratios (= service.generators)
    detemper_sizes = interval_sizes(tun, detemper_ratios, db)  # tempered = the genmap, plus just/error
    detemper_vectors = generator_detempering(state.mapping)  # D's vectors, for the prescaling matrix
    # the weighting region: complexity (a covector over the primes, lists elsewhere), the
    # per-target weight list, and the prescaling matrices (L applied to each vector set, as
    # ket lists). Complexity over the primes is the complexity of each domain basis element
    # (over the domain basis, like the grid) — NOT the standard primes, so a nonprime element
    # prime-factors correctly (13/5 reads log₂(13·5), not log₂5 over a domain that has no 5).
    prime_ratios = tuple(element_ratio(e) for e in db)
    # the bare prescaler 𝑋 (its diagonal, or a hand-entered non-diagonal matrix override) — the
    # SAME override the grid threads into every prescaling/complexity/weight/tuning calculation,
    # over the actual domain basis + approach (so a prime-subgroup or nonprime-based diagonal reads
    # log₂ of the right elements, matching the complexity row). (nonstandard-superspace-6.)
    prescaler = complexity_prescaler(state.mapping, scheme, override=custom_prescaler,
                                     domain_basis=db, nonprime_approach=nonprime_approach)
    prescaler_is_matrix = bool(prescaler) and isinstance(prescaler[0], (tuple, list))
    size_factor = complexity_size_factor(scheme)  # nonzero ⇒ the rectangular 𝑋 = 𝑍𝐿 (size row)

    def _prescaled(vectors):
        # the prescaled vector 𝑋·v: a diagonal pretransformer multiplies element-wise (𝐿ᵢvᵢ); a
        # non-diagonal one (the editable square's matrix override) is a matrix-vector product — the
        # same split the grid takes (spreadsheet.py's prescaling loop)
        if prescaler_is_matrix:
            return tuple(tuple(sum(prescaler[i][k] * v[k] for k in range(state.d)) for i in range(state.d))
                         for v in vectors)
        return tuple(tuple(prescaler[i] * v[i] for i in range(state.d)) for v in vectors)

    def _sized(cols):
        """Append the size component sf·Σ(𝐿ⱼ·vⱼ) (= sf·sum of the prescaled column) to each
        prescaled COLUMN, growing a 𝐿·basis product into the rectangular 𝑍𝐿 form when the size
        factor is on — the guide's size-sensitizing row. A no-op for the square (lp) case."""
        if not size_factor:
            return cols
        return tuple(col + (size_factor * sum(col),) for col in cols)

    # the bare prescaler 𝑋 as its d matrix ROWS: a diagonal 𝐿 broadcast to [0…𝐿ᵢ…0] rows; a
    # hand-entered non-diagonal pretransformer its own rows — matching the grid's 2D placement,
    # where cell (i, c) = 𝑋[i][c] (the diagonal case renders identically either way).
    if prescaler_is_matrix:
        bare_rows = [tuple(prescaler[i]) for i in range(state.d)]
    else:
        bare_rows = [tuple(prescaler[i] if k == i else 0 for k in range(state.d)) for i in range(state.d)]
    # the bare prescaler is a covector STACK, so the size factor appends one extra ROW — the
    # size-sensitizing covector sf·𝐋 (each entry sf·Σᵢ𝑋ᵢⱼ, the column sum — sf·𝐿ⱼ for a diagonal),
    # keeping the row length d — rather than extending each column the way the products do. This
    # 𝑋 = 𝑍𝐿 size row is the only growth the weighting region shows; the all-interval simplicity
    # weight stays a per-target list (its 𝒘 = 𝒄⁻¹ form lives in the grid tile's symbol, not here).
    bare_size_row = ((tuple(size_factor * sum(col) for col in zip(*bare_rows)),) if size_factor else ())
    weight_text = _cents_list(target_damage_weights)
    tp_text = _ket_list(target_vectors, "⟩")
    bare_x_text = _prescale_vector_list(bare_rows + list(bare_size_row), col="⟨]", outer="[⟩")
    complexity_text = _cents_list(interval_complexities(state.mapping, scheme, targets, domain_basis=db,
                                                        prescaler_override=custom_prescaler))
    damage_text = _cents_list(target_sizes.damage)
    # the unchanged half U of the consolidated V = C|U column (projection on): assembled the SAME way
    # the grid does — service.unchanged_interval_data, over the same custom prescaler — so the inline
    # plain text matches the grid cell-for-cell, em-dashes and all, where the under-held tuning leaves
    # a direction irrational. Off (or n = 0), the u_* lists stay empty and every V tile reads as C alone.
    udata = unchanged_interval_data(state, held_basis_ratios, tun, scheme, db,
                                    custom_prescaler) if consolidate_v else None
    if udata is not None:
        nrow = len(state.mapping)
        u_basis = list(udata.basis)  # P·𝐮 = 𝐮, so this also serves the projected list P·V's unchanged half
        u_mapped_cols = [None if udata.basis[j] is None else tuple(udata.mapped[i][j] for i in range(nrow))
                         for j in range(len(udata.basis))]
        u_prescaled = [None if u is None else _sized(_prescaled((u,)))[0]
                       for u in udata.basis]
        u_tempered, u_just, u_errors = list(udata.sizes.tempered), list(udata.sizes.just), list(udata.sizes.errors)
        u_comps = list(udata.complexities)
        u_scaling = [_DASH if v is None else "1" for v in udata.basis]  # λ = 1 (held) / — (dashed)
    else:
        u_basis = u_mapped_cols = u_prescaled = u_tempered = u_just = u_errors = u_comps = u_scaling = []
    # the canonical-mapping row's plain text — 𝑀_C and its mapped lists (the canonical-form twins of
    # the mapping row's strings), surfaced by the form-tiles layer. 𝑀_C·D = 𝐹 (the form matrix); the
    # mapped comma basis vanishes; 𝐹⁻¹𝐹 = 𝐼. The renderer gates these on form_tiles / identity_objects
    # via tile_open, so they can sit in the dict unconditionally, like the standard identity objects.
    canon_mapping = canonical_mapping(state.mapping)
    rc = len(canon_mapping)
    canon_form = form_matrix(state.mapping)                                   # 𝐹
    canon_inverse_form = inverse_form_matrix(state.mapping)                    # 𝐹⁻¹ (mapping row, 𝑀 = 𝐹⁻¹𝑀_C)
    canon_mapped = mapped_intervals(canon_mapping, targets, db)              # Y_C = 𝑀_C·T
    canon_mapped_comma = mapped_commas(canon_mapping, comma_basis)           # 𝑀_C·C = 𝑂
    canon_mapped_detempering = mapped_commas(canon_mapping, detemper_vectors)  # 𝑀_C·D = 𝐹
    # 𝑀_C·U for the consolidated V column's unchanged half (None → dashed, like u_mapped_cols)
    canon_u_mapped_cols = [None if u is None else tuple(sum(canon_mapping[i][p] * u[p] for p in range(state.d))
                                                        for i in range(rc)) for u in u_basis]

    def _canon_stack(rows, op):  # a covector stack [ op…] op…] } — per-row op-open + ], brace close (𝑀_C / 𝐹 / 𝐹⁻¹𝐹)
        return "[" + " ".join(op + " ".join(str(x) for x in r) + "]" for r in rows) + "}"

    # Keyed by the tile each value group occupies. The interval-vectors row holds the
    # vector lists (close ⟩); the mapping row holds the mapping (a list of maps, close ])
    # and the mapped lists (generator-coordinate vectors, close }). The editable duals
    # are the mapping (mapping/primes) and the comma basis (vectors/commas). The
    # quantities row's only plain text is the domain-primes basis ("2.3.5"), keyed here; its
    # interval-ratio columns (commas/targets/held/detempering) carry none — their gridded
    # ratio is already the formatted value. The generators (mapping/quantities) carry none either.
    values = {
        ("quantities", "primes"): ".".join(str(e) for e in db),
        # the consolidated V = C|U column shows BOTH halves in every tile: the comma side C then the
        # unchanged side U (em-dashed where the tuning leaves a direction irrational). Off projection
        # the u_* lists are empty, so each tile falls back to the bare comma side exactly as before.
        ("vectors", "commas"): _ket_list(list(comma_basis) + u_basis, "⟩"),
        # the projected unrotated vector list P·V: P·𝐜 = 𝟎 (the commas vanish), P·𝐮 = 𝐮 (held), so it
        # is the zero comma columns followed by the unchanged vectors themselves — prime-count (⟩)
        ("projection", "commas"): _ket_list([(0,) * state.d for _ in commas] + u_basis, "⟩"),
        # the scaling factors λ = diag(λ): 0 per comma (vanished), 1 per (known) unchanged, — if dashed
        ("scaling_factors", "commas"): "[" + " ".join(["0"] * len(commas) + u_scaling) + "]",
        ("vectors", "targets"): tp_text,  # Tₚ — the target identity
        # D — the generator detempering as a vector list (r prime-count kets, close ⟩),
        # matching its gridded matrix and the commas/targets columns it sits beside
        ("vectors", "detempering"): _ket_list(detemper_vectors, "⟩"),
        ("mapping", "primes"): mapping_ebk(state),
        ("mapping", "commas"): _ket_list(list(zip(*mapped_comma)) + u_mapped_cols, "}"),
        ("mapping", "targets"): _ket_list(zip(*mapped), "}"),
        # the standard-domain identity objects (on-domain twins of M_jL / M_LGL). The renderer gates
        # them on identity_objects via tile_open, so the strings can sit here unconditionally. M_j is
        # the p/p JI mapping — a d × d covector stack (⟨ … ] rows) closing with the angle ⟩ (an
        # operator, like P), NOT the mapping's }. MG / MD are the r × r identity M·D as a COLUMN-first
        # vector list in generator coords — kets [ … } inside an outer { … ], like M_LGL.
        ("vectors", "primes"): "[" + "".join(
            "⟨" + " ".join("1" if i == k else "0" for k in range(state.d)) + "]"
            for i in range(state.d)) + "⟩",
        ("mapping", "gens"): "{" + _ket_list([[1 if i == k else 0 for k in range(len(state.mapping))]
                                              for i in range(len(state.mapping))], "}", wrap=False) + "]",
        ("mapping", "detempering"): "{" + _ket_list([[1 if i == k else 0 for k in range(len(state.mapping))]
                                                     for i in range(len(state.mapping))], "}", wrap=False) + "]",
        # the canonical-mapping row: 𝑀_C a covector stack (map rows ⟨ … ], brace close) like 𝑀; 𝐹 and
        # 𝐹⁻¹𝐹 = 𝐼 genmap covector stacks ({ … ] rows); the mapped lists ket lists like the mapping
        # row's (𝑀_C·D = 𝐹 a generator-coord vector list { … ]; 𝑀_C·C vanishes; Y_C = 𝑀_C·T).
        ("canon", "primes"): _canon_stack(canon_mapping, "⟨"),
        ("canon", "gens"): _canon_stack(canon_form, "{"),
        ("canon", "canongens"): _canon_stack([[1 if i == k else 0 for k in range(rc)] for i in range(rc)], "{"),
        ("canon", "detempering"): "{" + _ket_list(zip(*canon_mapped_detempering), "}", wrap=False) + "]",
        ("canon", "commas"): _ket_list(list(zip(*canon_mapped_comma)) + canon_u_mapped_cols, "}"),
        ("canon", "targets"): _ket_list(zip(*canon_mapped), "}"),
        # the canonical-generators column's mapping/tuning-row tiles: 𝐹⁻¹ a genmap covector stack like
        # 𝐹 (𝑀 = 𝐹⁻¹𝑀_C), and 𝒈_C = 𝒈·F⁻¹ the canonical generator tuning map (a cents genmap like 𝒈).
        # G_C (projection row) is conditional below, with G.
        ("mapping", "canongens"): _canon_stack(canon_inverse_form, "{"),
        ("tuning", "canongens"): _cents_genmap(
            [sum(tun.generator_map[k] * canon_inverse_form[k][j] for k in range(len(state.mapping)))
             for j in range(rc)]),
        ("tuning", "gens"): _cents_genmap(tun.generator_map),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(list(comma_sizes.tempered) + u_tempered),
        # the detempering's tempered sizes ARE the generator tuning map (𝒕D = 𝒈), shown
        # genmap-style ({ ]); its just and retuning sizes are ordinary cents lists
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
        # the bare prescaler 𝐿 is the asymmetric exception of the prescaling row: it reads
        # as a covector stack like the mapping — per-row ⟨ … ] (angle open + square close)
        # inside outer [ … ⟩ (square open + ket close). Every 𝐿·basis product (𝐿C/𝐿D/𝐿H/𝐿T)
        # is instead a matrix of prescaled VECTORS — per-column ket [ … ⟩ inside symmetric
        # outer [ … ] — so the bare prescaler reads as the matrix itself rather than a
        # product with another basis.
        ("prescaling", "primes"): bare_x_text,  # the bare 𝑋 — gains its 𝑍𝐿 size ROW under the size factor
        ("prescaling", "commas"): _prescale_vector_list(list(_sized(_prescaled(comma_basis))) + u_prescaled),
        ("prescaling", "detempering"): _prescale_vector_list(_sized(_prescaled(detemper_vectors))),
        ("prescaling", "targets"): _prescale_vector_list(_sized(_prescaled(target_vectors))),
        ("complexity", "primes"): _cents_map(interval_complexities(state.mapping, scheme, prime_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        ("complexity", "commas"): _cents_list(list(interval_complexities(state.mapping, scheme, commas, domain_basis=db, prescaler_override=custom_prescaler)) + u_comps),
        ("complexity", "detempering"): _cents_list(interval_complexities(state.mapping, scheme, detemper_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        ("complexity", "targets"): complexity_text,
        ("weight", "targets"): weight_text,
    }
    # the held interval column mirrors the comma column: the basis as a vector list, mapped
    # into generator coords, then the held-just sizes/errors and complexity. Added only when
    # the user has held intervals (an empty set declares no held tiles, like the commas).
    if held:
        held_sizes = interval_sizes(tun, held_ratios, db)
        held_mapped = mapped_intervals(state.mapping, held_ratios, db)
        canon_held_mapped = mapped_intervals(canon_mapping, held_ratios, db)  # 𝑀_C·H
        values.update({
            ("vectors", "held"): _ket_list(held, "⟩"),
            ("mapping", "held"): _ket_list(zip(*held_mapped), "}"),
            ("canon", "held"): _ket_list(zip(*canon_held_mapped), "}"),
            ("tuning", "held"): _cents_list(held_sizes.tempered),
            ("just", "held"): _cents_list(held_sizes.just),
            ("retune", "held"): _cents_list(held_sizes.errors),
            ("prescaling", "held"): _prescale_vector_list(_sized(_prescaled(held))),
            ("complexity", "held"): _cents_list(interval_complexities(state.mapping, scheme, held_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        })
    # the other-intervals-of-interest column is a loose collection, not a basis, so every
    # row is unwrapped (wrap=False): its vectors and mapped images stand alone (each its own
    # ket, space-separated, no outer [ … ]), unlike the comma/target/held matrices; the size
    # rows drop their [ … ] too, and prescaling lists each prescaled vector as its own parens.
    if interest:
        interest_ratios = comma_ratios(interest, db)
        interest_mapped = mapped_intervals(state.mapping, interest_ratios, db)
        canon_interest_mapped = mapped_intervals(canon_mapping, interest_ratios, db)  # 𝑀_C·interest
        interest_sizes = interval_sizes(tun, interest_ratios, db)
        values.update({
            ("vectors", "interest"): _ket_list(interest, "⟩", wrap=False),
            ("mapping", "interest"): _ket_list(zip(*interest_mapped), "}", wrap=False),
            ("canon", "interest"): _ket_list(zip(*canon_interest_mapped), "}", wrap=False),
            ("tuning", "interest"): _cents_list(interest_sizes.tempered, wrap=False),
            ("just", "interest"): _cents_list(interest_sizes.just, wrap=False),
            ("retune", "interest"): _cents_list(interest_sizes.errors, wrap=False),
            ("prescaling", "interest"): _prescale_vector_list(_sized(_prescaled(interest)), outer=""),
            ("complexity", "interest"): _cents_list(interval_complexities(state.mapping, scheme, interest_ratios, domain_basis=db, prescaler_override=custom_prescaler), wrap=False),
        })
    # the projection P and generator embedding G plain-text bands (the editable duals — the only edit
    # path now that the gridded cells are read-only). Computed from the SAME held basis the grid's
    # P/G cells use, so band and grid agree cell-for-cell, dashed in lockstep when the tuning isn't a
    # full rational projection. Only when projection is on (consolidate_v), like the grid.
    if consolidate_v:
        values[("projection", "primes")] = projection_ebk(tuning_projection(state, held_basis_ratios), state.d)
        values[("projection", "gens")] = embedding_ebk(tuning_embedding(state, held_basis_ratios), state.d, len(state.mapping))
        # G_C the canonical generator embedding (= G·F⁻¹), a vector list like G over the rc canonical
        # generators — dashed in lockstep with G when the tuning isn't a full rational projection
        values[("projection", "canongens")] = embedding_ebk(
            canonical_generator_embedding(state, held_basis_ratios), state.d, rc)
        # the projected vector lists' read-only EBK bands (P·D / P·T / P·H / P·interest), the projection-
        # row counterparts of the interval-vectors row's strings. P·D = the embedding G takes the curly
        # { … ] (generator-coordinate columns, like G); P·T / P·H the plain [ … ]; P·interest stands
        # alone (no outer wrap). Dashed in lockstep with P when the tuning isn't a rational projection.
        p_rat = projection_matrix_rationals(state, held_basis_ratios)

        def _proj_cols(vectors):
            cols = project_vectors(p_rat, vectors)
            return list(cols) if cols else [tuple(_DASH for _ in range(state.d)) for _ in vectors]

        values[("projection", "detempering")] = "{" + _ket_list(_proj_cols(detemper_vectors), "⟩", wrap=False) + "]"
        values[("projection", "targets")] = _ket_list(_proj_cols(target_vectors), "⟩")
        if held:
            values[("projection", "held")] = _ket_list(_proj_cols(held), "⟩")
        if interest:
            values[("projection", "interest")] = _ket_list(_proj_cols(interest), "⟩", wrap=False)
    # the chapter-9 nonstandard-domain superspace region: B_L (the basis-embedding matrix
    # as a list of dL-tall kets, one per domain element), M_L (the temperament's mapping
    # over the superspace primes — a covector stack like M), M_jL (the dL × dL identity),
    # and the cyan tuning maps 𝒈ₗ / 𝒕ₗ / 𝒋ₗ / 𝒓ₗ (covectors over the superspace primes,
    # respectively the generators for 𝒈ₗ). Same bracket conventions as the existing tiles
    # they parallel — _ket_list for B_L's vector columns, _cents_map for the covector maps,
    # _cents_genmap for the genmap 𝒈ₗ — so each new EBK string reads consistently with its
    # non-superspace cousin (per the rendered mockup, which kept the existing brackets).
    if superspace:
        db = state.domain_basis
        ml = superspace_mapping(state)
        ss_primes = superspace_primes(db)
        mjl = superspace_just_mapping(ss_primes)
        mlgl = superspace_self_map(state)
        msl = mapping_to_superspace_generators(state)
        bl = basis_in_superspace(db)
        ss_tun = (derived.superspace_tun
                  if derived is not None and derived.superspace_tun is not None else
                  superspace_tuning(state, scheme, nonprime_approach,
                                    generator_override=superspace_generator_override))

        def _covector_stack(rows):  # mapping-style: each row ⟨ … ], outer [ … }
            return "[" + "".join("⟨" + " ".join(str(x) for x in r) + "]" for r in rows) + "}"

        # the lifted interval lists (B_L · each column) over the superspace primes, and the
        # mapped versions (M_s→L · each column) over the superspace generators
        C_L = lift_vectors_to_superspace(db, state.comma_basis)
        T_L = lift_vectors_to_superspace(db, target_vectors)
        I_L = lift_vectors_to_superspace(db, interest)
        D_L = lift_vectors_to_superspace(db, detemper_vectors)
        mapped_C = map_vectors_into_superspace_generators(state, state.comma_basis)
        mapped_T = map_vectors_into_superspace_generators(state, target_vectors)
        mapped_I = map_vectors_into_superspace_generators(state, interest)
        mapped_D = map_vectors_into_superspace_generators(state, detemper_vectors)
        # the unchanged half U of the consolidated V = C|U column, lifted into the superspace (B_L·𝐮)
        # and mapped into the superspace generators (M_s→L·𝐮) — the superspace twins of the on-domain
        # u_basis / u_mapped_cols, appended to the comma half so the two ss tiles read C|U like the grid.
        # u_basis is empty off projection, so these collapse to nothing and each tile is C alone.
        ss_u = [None if u is None else lift_vectors_to_superspace(db, (u,))[0] for u in u_basis]
        ss_u_mapped = [None if u is None else map_vectors_into_superspace_generators(state, (u,))[0] for u in u_basis]
        values.update({
            # B_L (basis change matrix): the mockup wraps it ⟨ … ] (distinct from the plain
            # [ … ] lifted lists), its columns the domain-element kets [ … ⟩.
            ("ss_vectors", "primes"): "⟨" + _ket_list(bl, "⟩", wrap=False) + "]",
            # M_jL = I: the p/p JI mapping over the superspace primes — a covector stack closing with the angle ⟩ (operator,
            # like P_L), not the mapping's }. Matches matrix_frame(ss_vec_jmap, foot="ebkangle").
            ("ss_vectors", "ssprimes"): "[" + "".join(
                "⟨" + " ".join(str(x) for x in row) + "]" for row in mjl) + "⟩",
            ("ss_vectors", "commas"): _ket_list(list(C_L) + ss_u, "⟩"),  # C_L then B_L·U over V
            ("ss_vectors", "targets"): _ket_list(T_L, "⟩"),         # T_L
            ("ss_vectors", "detempering"): _ket_list(D_L, "⟩"),     # D_L (lifted detempering)
            ("ss_vectors", "interest"): _ket_list(I_L, "⟩", wrap=False),
            ("ss_mapping", "ssprimes"): _covector_stack(ml),        # M_L
            ("ss_mapping", "primes"): _covector_stack(msl),         # M_s→L
            # M_LGL = I: a COLUMN-first vector list — kets [ … } in an outer { … ] (gen coords),
            # like MG / MD. Matches the grid's vector_list_marks + { … ] wrap.
            ("ss_mapping", "ssgens"): "{" + _ket_list(mlgl, "}", wrap=False) + "]",
            ("ss_mapping", "commas"): _ket_list(list(mapped_C) + ss_u_mapped, "}"),  # M_s→L·C (→ 0) then M_s→L·U over V
            ("ss_mapping", "targets"): _ket_list(mapped_T, "}"),    # Y_L
            # detempering mapped into ss generators: a column-first list in an outer { … ] (gen
            # coords), matching the grid's { … ] wrap and its row-sibling M_LGL above — not [ … ]
            ("ss_mapping", "detempering"): "{" + _ket_list(mapped_D, "}", wrap=False) + "]",
            ("ss_mapping", "interest"): _ket_list(mapped_I, "}", wrap=False),
            ("tuning", "ssgens"): _cents_genmap(ss_tun.generator_map),
            ("tuning", "ssprimes"): _cents_map(ss_tun.tuning_map),
            ("just", "ssprimes"): _cents_map(ss_tun.just_map),
            ("retune", "ssprimes"): _cents_map(ss_tun.retuning_map),
        })
        # the held interval column's superspace tiles (declared only when held intervals exist,
        # like its on-domain cousins): H_L the lifted held vectors, and the held mapped into the
        # superspace generators — the same lift/map the commas/targets columns take above.
        if held:
            values[("ss_vectors", "held")] = _ket_list(lift_vectors_to_superspace(db, held), "⟩")
            values[("ss_mapping", "held")] = _ket_list(map_vectors_into_superspace_generators(state, held), "}")
        # the superspace projection row's EBK bands — the plain-text twins of its grid tiles. P_L
        # itself is a covector stack closing with the angle ⟩ (the b/b operator, framed like the on-
        # domain P); the embedding G_L is a vector list ({…]); and each projected list is P_L applied
        # to the lifted vectors, mirroring the on-domain G / P·B_Ls / P·D / P·V / P·T / P·H / P·interest
        # plain text. Only when the projection toggle is on (consolidate_v), like the on-domain bands,
        # built from the SAME P_L so the two views agree; dashed in lockstep when P_L is None.
        if consolidate_v:
            dL = len(ss_primes)
            p_L = superspace_projection_matrix_rationals(state, held_basis_ratios)

            def _ssp_cols(vectors):  # P_L · each lifted vector, dashed (dL-tall) when P_L is None
                cols = project_vectors(p_L, lift_vectors_to_superspace(db, vectors))
                return list(cols) if cols else [tuple(_DASH for _ in range(dL)) for _ in vectors]

            proj_bl = project_vectors(p_L, bl) or [tuple(_DASH for _ in range(dL)) for _ in bl]
            values[("ss_projection", "ssprimes")] = projection_ebk(
                superspace_tuning_projection(state, held_basis_ratios), dL)
            values[("ss_projection", "ssgens")] = embedding_ebk(
                superspace_tuning_embedding(state, held_basis_ratios), dL, superspace_rank(state))
            # P_L·B_Ls keeps B_L's outer ⟨ … ] (covector-style) around its per-element kets [ … ⟩
            values[("ss_projection", "primes")] = "⟨" + _ket_list(proj_bl, "⟩", wrap=False) + "]"
            values[("ss_projection", "detempering")] = "{" + _ket_list(_ssp_cols(detemper_vectors), "⟩", wrap=False) + "]"
            # P_L·V: the comma half vanishes (P_L·𝐜 = 𝟎) then the unchanged half held, lifted (like on-domain P·V)
            values[("ss_projection", "commas")] = _ket_list([(0,) * dL for _ in commas] + ss_u, "⟩")
            values[("ss_projection", "targets")] = _ket_list(_ssp_cols(target_vectors), "⟩")
            if held:
                values[("ss_projection", "held")] = _ket_list(_ssp_cols(held), "⟩")
            if interest:
                values[("ss_projection", "interest")] = _ket_list(_ssp_cols(interest), "⟩", wrap=False)
            # the ON-DOMAIN projection row's superspace-column tiles (G_L→s / P_L→s), which sit between
            # G and P in that row but read superspace data, so they live here. G_L→s is the d×rL embedding
            # from the superspace generators to the subspace — a vector list { … ] like G; P_L→s = G_L→s·M_L
            # the d×dL projection from the superspace to the subspace — a covector stack ⟨ … ]⟩ like P. Built
            # from the SAME display grids the grid cells use, dashed in lockstep when the tuning isn't rational.
            values[("projection", "ssgens")] = embedding_ebk(
                superspace_generator_embedding_display(state, held_basis_ratios), state.d, superspace_rank(state))
            values[("projection", "ssprimes")] = projection_ebk(
                superspace_prime_projection_display(state, held_basis_ratios), state.d, cols=dL)
        # the chapter-9 prescaler SHIFT (the plain-text twin of the gridded cells): the bare 𝐿
        # moves into the ss-primes column — the dL×dL log-prime diagonal over the TRUE primes, a
        # covector stack [ ⟨…] ⟨…] ⟩ that stays EDITABLE — while the domain-primes tile becomes the
        # 𝐿·B_Ls product, the prescaled subspace basis elements: a READ-ONLY matrix of d prescaled
        # kets [ … ⟩ (NOT the bare prescaler's covector stack — that backwards EBK was the bug). The
        # complexity row mirrors it: the prime complexity map ‖𝐿[i]‖ moves to ss-primes; the domain-
        # primes complexity becomes the subspace basis element map (prime-factored over the domain).
        ss_prescaler = superspace_complexity_prescaler(state, scheme)
        dL = len(ss_primes)
        ss_units = tuple(tuple(1 if i == p else 0 for i in range(dL)) for p in range(dL))

        def _prescaled_ss(vectors):  # element-wise 𝐿ᵢvᵢ over the dL superspace primes
            return tuple(tuple(ss_prescaler[i] * v[i] for i in range(dL)) for v in vectors)

        ss_bare_size = ((tuple(size_factor * w for w in ss_prescaler),) if size_factor else ())
        elem_ratios = tuple(element_ratio(e) for e in db)
        values.update({
            ("prescaling", "ssprimes"): _prescale_vector_list(_prescaled_ss(ss_units) + ss_bare_size, col="⟨]", outer="[⟩"),
            # 𝐿·B_Ls is the prescaled basis-change matrix, so it follows B_L's wrap: outer ⟨ … ]
            # around the per-column kets [ … ⟩ (matching ss_vectors/primes, not the plain products)
            ("prescaling", "primes"): _prescale_vector_list(_sized(_prescaled_ss(bl)), col="[⟩", outer="⟨]"),
            ("complexity", "ssprimes"): _cents_map(ss_prescaler),
            ("complexity", "primes"): _cents_map(interval_complexities(state.mapping, scheme, elem_ratios, domain_basis=db, prescaler_override=custom_prescaler)),
        })
        # every prescaling 𝐿·v product ALSO lifts to dL-tall over the superspace primes and prescales
        # with the superspace diagonal — the same lift the grid takes (spreadsheet.build). Leaving the
        # commas/targets/held/detempering/interest products as the earlier UNLIFTED d-tall domain
        # vectors (with the wrong domain diagonal) made the band contradict the grid cells above it —
        # e.g. a 13/5 column reading 2·log₂5 instead of the lifted log₂13/log₂5 split. (ebk-notation-4.)
        _ss_prod = lambda vs: _sized(_prescaled_ss(lift_vectors_to_superspace(db, vs)))
        ss_u_prescaled = [None if u is None else _sized(_prescaled_ss(lift_vectors_to_superspace(db, (u,))))[0]
                          for u in u_basis]
        values[("prescaling", "commas")] = _prescale_vector_list(list(_ss_prod(comma_basis)) + ss_u_prescaled)
        values[("prescaling", "detempering")] = _prescale_vector_list(_ss_prod(detemper_vectors))
        values[("prescaling", "targets")] = _prescale_vector_list(_ss_prod(target_vectors))
        if held:
            values[("prescaling", "held")] = _prescale_vector_list(_ss_prod(held))
        if interest:
            values[("prescaling", "interest")] = _prescale_vector_list(_ss_prod(interest), outer="")
    return values


_DASH = "—"  # an em-dash column/value: an unknown the under-held tuning doesn't pin (matches the grid)


# ── EBK ⇄ plain-matrix notation (the Show panel's "EBK" toggle, off) ──────────────────────────
# EBK off rewrites every notation string into a plain matrix: each angle/curly brace becomes a
# square brace, and a superscript ᵀ marks the VECTOR-based kind (a list of column vectors / kets)
# apart from the MAP-based kind (a covector stack, or a single covector / scalar list). It is the
# string twin of the gridded mark swap (square brackets + ᵀ) the spreadsheet builder makes, so the
# two views stay identical off as on. A pure display transform — the underlying objects are untouched.
_EBK_OPEN = "[⟨{"     # the three EBK openers: square ket-open, angle bra-open, curly genmap/list-open
_EBK_CLOSE = "]⟩}"    # the three EBK closers: square bra-close, angle ket-close, curly ket-close
_KET_CLOSE = "⟩}"     # a ket closes with the angle ⟩ (over d) or curly } (over generator coords)
_TRANSPOSE = "ᵀ"      # MODIFIER LETTER CAPITAL T (U+1D40) — the plain-matrix mark of the vector kind


def _flatten_brackets(group: str) -> str:
    """Replace every EBK bracket in ``group`` with its square brace (openers → ``[``, closers → ``]``)."""
    return "".join("[" if c in _EBK_OPEN else "]" if c in _EBK_CLOSE else c for c in group)


def _group_is_vector_based(group: str) -> bool:
    """Whether one top-level EBK group is the VECTOR kind (gets a ᵀ). A group that wraps sub-items is
    vector-based when those items are KETS (open ``[``) rather than bras (open ``⟨``/``{``) — so the
    mapping ``[⟨…]…}`` is map-based while the comma basis ``[[…⟩…]`` and the basis-change ``⟨[…⟩…]``
    are vector-based, told apart by the CHILD opener, never the outer wrap. A bare group (numbers, no
    sub-items) is vector-based when it CLOSES as a ket (``⟩`` / ``}``): a single ket ``[…⟩`` yes, a
    single covector ``⟨…]`` / genmap ``{…]`` / scalar list ``[…]`` no."""
    inner = group[1:-1].lstrip()
    if inner and inner[0] in _EBK_OPEN:
        return inner[0] == "["          # a ket child opens with [; a bra child with ⟨ or {
    return group[-1] in _KET_CLOSE      # a single vector closes with ⟩ / }; a covector / list with ]


def ebk_to_simple_matrix(text: str) -> str:
    """Rewrite an EBK notation string into plain matrix notation (the EBK-toggle-off form): every
    angle/curly brace → a square brace, and a trailing ``ᵀ`` on each top-level VECTOR-kind group
    (:func:`_group_is_vector_based`). Inter-group text (a domain-basis prefix, the spaces between
    standalone interest kets) is preserved verbatim, and a string with no brackets passes through.

    Examples: ``[⟨1 0 -4] ⟨0 1 4]}`` → ``[[1 0 -4] [0 1 4]]`` (a mapping, map-based — no ᵀ);
    ``[[-4 4 -1⟩]`` → ``[[-4 4 -1]]ᵀ`` (a comma basis, vector-based); ``⟨1200 1902]`` → ``[1200 1902]``
    (a tuning map); ``[-4 4 -1⟩`` → ``[-4 4 -1]ᵀ`` (a lone ket)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in _EBK_OPEN:
            depth, j = 0, i
            while j < n:                       # scan to this group's matching close
                if text[j] in _EBK_OPEN:
                    depth += 1
                elif text[j] in _EBK_CLOSE:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if depth != 0:                     # unbalanced (shouldn't happen) — leave the rest as-is
                out.append(text[i:])
                break
            group = text[i:j + 1]
            out.append(_flatten_brackets(group) + (_TRANSPOSE if _group_is_vector_based(group) else ""))
            i = j + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def simple_matrix_to_ebk(text: str, vector_based: bool) -> str:
    """Rewrite a plain-matrix notation string (an edited EBK-off dual) back into EBK so the existing
    parsers read it. The inverse of :func:`ebk_to_simple_matrix` for ONE object whose variance the
    caller knows (a comma basis / target list / embedding is ``vector_based=True``; a mapping /
    projection / prescaler ``False``), so it need not rely on the user keeping the ``ᵀ``. A wrapped
    matrix ``[[…] […]]`` restores its inner items to kets ``[…⟩`` (vector) or bras ``⟨…]`` (map),
    the outer ``[ … ]`` kept; a bare ``[…]`` restores to a single ket / covector. Any ``ᵀ`` and a
    leading domain-basis prefix are handled; a string with no bracket passes through unchanged (the
    cents parsers strip brackets themselves)."""
    text = text.replace(_TRANSPOSE, "")
    start = text.find("[")
    if start == -1:
        return text
    prefix, body = text[:start], text[start:]
    open_ch, close_ch = ("[", "⟩") if vector_based else ("⟨", "]")
    wrapped = body[1:].lstrip().startswith("[")   # an outer [ … ] around inner [ … ] items
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
    """A list of column vectors: ``[[1 0 0⟩ [0 1 0⟩]`` for vectors (close ``⟩``),
    ``[[1 0} [0 1}]`` for generator-coordinate vectors (close ``}``). The outer ``[ ]``
    wraps the whole list (a matrix presentation, even a single vector); ``wrap=False``
    drops it for the intervals-of-interest column, whose intervals stand alone. A ``None``
    column is a DASHED unchanged vector — all em-dashes, width matched to the known columns."""
    vectors = list(vectors)
    dim = next((len(v) for v in vectors if v is not None), 0)
    def _ket(v):
        comps = [_DASH] * dim if v is None else [str(x) for x in v]
        return "[" + " ".join(comps) + close
    kets = " ".join(_ket(v) for v in vectors)
    return f"[{kets}]" if wrap else kets


def projection_ebk(matrix, d: int, cols: int | None = None) -> str:
    """The rational tempering projection P as a map-list EBK string — a covector stack like the
    mapping (each row a map ``⟨ … ]``), but closing with the prime-coordinate ket ``⟩`` since P is
    p/p: ``[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩``. ``matrix`` is the d×``cols`` grid of display strings from
    :func:`tuning_projection`; ``None`` (not a full rational projection) dashes every entry to match
    the dashed grid. The editable dual the projection-primes plain text shows (parsed by
    :func:`parse_projection`). ``cols`` defaults to ``d`` (the square on-domain P); the superspace
    P_L→s is the rectangular d×dL case (each row a covector over the dL superspace primes)."""
    cols = d if cols is None else cols
    grid = matrix if matrix is not None else tuple((_DASH,) * cols for _ in range(d))
    return "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in grid) + "⟩"


def embedding_ebk(matrix, d: int, r: int) -> str:
    """The rational generator embedding G as a vector-list EBK string — its r held generators as
    prime-count ket columns inside an outer ``{ … ]`` (curly open, square close — generator-coordinate
    columns): ``{[1 0 0⟩ [0 0 1/4⟩]``. ``matrix`` is the d×r grid of display strings from
    :func:`tuning_embedding`; ``None`` dashes every entry. The editable dual the projection-gens plain
    text shows (parsed by :func:`parse_embedding`)."""
    grid = matrix if matrix is not None else tuple((_DASH,) * r for _ in range(d))  # d×r
    return "{" + _ket_list(list(zip(*grid)), "⟩", wrap=False) + "]"  # transpose to the r ket columns


def _prescale_vector_list(vectors, col: str = "[⟩", outer: str = "[]", decimals: bool = True) -> str:
    """A list of complexity-prescaler matrix columns — for the weighting prescaling matrices
    (the prescaled vectors 𝐿·v). A 𝐿·basis product is a matrix of prescaled VECTORS, so each
    column is a ket ``[ … ⟩`` (square open + angle close — the default ``col``); the OUTER
    wrap then differs by tile family:

      * 𝐿·basis products  — ``col="[⟩"``, ``outer="[]"`` (kets inside a symmetric square).
      * Interest tile     — ``col="[⟩"``, ``outer=""``  (standalone kets, no wrap).
      * Bare prescaler 𝐿  — ``col="⟨]"``, ``outer="[⟩"`` (the asymmetric exception: it reads
        as a covector stack like the mapping — per-row ⟨ … ] inside outer [ … ⟩, mirroring
        the mapping's ``[ … }`` but with the angle ⟩ instead of the curly }).

    Each value is formatted with prescale_text, so the string shows exactly the grid's
    numbers (whole numbers bare, else 3-dp) rather than a denser all-3-dp form."""
    vectors = list(vectors)
    dim = next((len(v) for v in vectors if v is not None), 0)  # a dashed (None) column is all em-dashes
    def _col(v):
        body = " ".join([_DASH] * dim if v is None else [prescale_text(x, decimals) for x in v])
        return col[0] + body + col[1]
    cols = " ".join(_col(v) for v in vectors)
    if not outer:
        return cols
    return f"{outer[0]}{cols}{outer[1]}"


def vector_list_pending_text(committed_vectors, pending) -> tuple[str, str, str]:
    """Split a wrapped vector-list plain text for the two-tone draft display: the committed
    vectors and the wrapping ``[ … ]`` stay black, the in-progress draft vector greens.
    Shared by the comma basis and the target interval list (both wrapped ket lists). Returns
    ``(black_prefix, green_draft_ket, black_suffix)``. The draft ket shows the entered components
    only (``None`` blanks omitted): ``[4, None, 1] -> "[4 1⟩"``."""
    committed = _ket_list(committed_vectors, "⟩")  # e.g. "[[4 -4 1⟩]" — drop its close ] to reopen
    draft = "[" + " ".join(str(x) for x in pending if x is not None) + "⟩"
    return committed[:-1] + " ", draft, "]"


def mapping_pending_text(committed_ebk, pending) -> tuple[str, str, str]:
    """Split the wrapped mapping plain text for the two-tone draft display while a generator ROW is
    being added: the committed maps and the wrapping ``[ … }`` stay black, the in-progress draft map
    greens. The ROW mirror of :func:`vector_list_pending_text`. ``committed_ebk`` is the mapping's
    plain text (e.g. ``"[⟨1 1 0] ⟨0 1 4]}"``, possibly domain-prefixed), which always closes with the
    generator-coordinate ``}``. Returns ``(black_prefix, green_draft_map, black_suffix)``; the draft
    map shows the entered components only (``None`` blanks omitted): ``[0, None, 1] -> "⟨0 1]"``."""
    draft = "⟨" + " ".join(str(x) for x in pending if x is not None) + "]"
    return committed_ebk[:-1] + " ", draft, "}"


def _cents_map(values, decimals: bool = True) -> str:
    """A tuning covector over the primes: ``⟨1200.000 1901.955 …]``."""
    return "⟨" + " ".join(cents(v, decimals) for v in values) + "]"


def _cents_list(values, wrap: bool = True, decimals: bool = True) -> str:
    """A tuning list over the targets: ``[1200.000 1901.955 …]``. ``wrap=False`` drops the
    enclosing ``[ ]`` for the intervals-of-interest column, whose values stand bare."""
    body = " ".join(_DASH if v is None else cents(v, decimals) for v in values)  # None → a dashed (unknown) entry
    return f"[{body}]" if wrap else body


def _cents_genmap(values, decimals: bool = True) -> str:
    """The generator tuning map: ``{1201.699 697.564]`` — curly open, square close,
    per the mockup (distinct from the primes' covector ``⟨ … ]``)."""
    return "{" + " ".join(cents(v, decimals) for v in values) + "]"


# Module-level handles for the four cents/prescale formatters, so plain_text_values can rebind each
# NAME to a decimals-bound partial without self-recursion (a function-local shadow can't reference
# the global it shadows). The bare names keep their 3-dp default for the direct service.* callers.
_CENTS_MAP = _cents_map
_CENTS_LIST = _cents_list
_CENTS_GENMAP = _cents_genmap
_PRESCALE_VECTOR_LIST = _prescale_vector_list
