import math
from fractions import Fraction

import pytest

from rtt.web import service


def test_base_scheme_name_strips_the_target_prefix():
    # the bare systematic name (the chooser's all-interval form); a target-set prefix
    # ("TILT ", "OLD ", with an optional manual limit) marks a target-based scheme and is stripped
    assert service.base_scheme_name("minimax-S") == "minimax-S"  # all-interval: no prefix
    assert service.base_scheme_name("TILT minimax-S") == "minimax-S"  # target prefix stripped
    assert service.base_scheme_name("9-TILT minimax-ES") == "minimax-ES"  # with a manual limit
    # the prefix is dropped structurally (forcing all-interval and rendering), so a target embedded
    # after a held- prefix is stripped too, not just a leading one
    assert service.base_scheme_name("held-octave OLD minimax-ES") == "held-octave minimax-ES"
    # a control-refined spec is named like any other now that the spec can be rendered
    assert service.base_scheme_name(service.resolve_tuning_scheme("minimax-S")) == "minimax-S"
    assert service.base_scheme_name(service.scheme_with_complexity_norm_power("minimax-S", 2.0)) == "minimax-ES"
    # ...but a genuinely unnameable spec (a non-integer optimization power) is None
    assert service.base_scheme_name(service.scheme_with_power("minimax-S", 1.5)) is None


def test_is_proper_temperament_rejects_degenerate_mappings():
    # a proper temperament has independent rows (full row rank) and reaches every prime (no all-zero
    # column — a prime mapped to nothing is tempered to a unison). Degenerate ones break M·Dᵀ=I and
    # don't round-trip, so the editor rejects them.
    assert service.is_proper_temperament(((1, 1, 0), (0, 1, 4))) is True   # 5-limit meantone
    assert service.is_proper_temperament(((2, 0, 0), (0, 1, 1))) is True   # enfactored but full-rank, every prime reached
    assert service.is_proper_temperament(((1, 2), (0, 0))) is False        # a dependent / zero row (rank < rows)
    assert service.is_proper_temperament(((1, 0),)) is False               # prime 3 tempered to a unison (zero column)


def test_optimization_power_is_the_schemes_lp_norm_order():
    # the optimization power p is trait 2 of the tuning scheme: the order of the
    # Lp norm minimized over the damages. minimax-S (the canonical scheme) is a minimax
    # scheme, so p = ∞; miniRMS is least-squares (p = 2); miniaverage is p = 1.
    assert service.optimization_power("minimax-S") == math.inf
    assert service.optimization_power() == math.inf  # defaults to the canonical scheme (minimax-S)
    assert service.optimization_power("least squares") == 2
    assert service.optimization_power("miniaverage-U") == 1


def test_from_mapping_computes_canonical_comma_basis():
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    assert state.mapping == ((1, 1, 0), (0, 1, 4))
    assert state.comma_basis == ((4, -4, 1),)
    assert (state.d, state.r, state.n) == (3, 2, 1)


def test_from_mapping_records_standard_prime_domain_basis():
    # a standard prime-limit temperament records its domain basis as the first d primes,
    # so the service layer always has a concrete basis (never None) to work from
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    assert state.domain_basis == (2, 3, 5)


def test_from_temperament_data_reads_a_nonstandard_domain_basis():
    # BARBADOS over the 2.3.13/5 subgroup: the domain basis is recorded verbatim
    # (13/5 is a nonprime element) and the dims come from the d=3 mapping
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert state.domain_basis == (2, 3, Fraction(13, 5))
    assert state.mapping == ((1, 2, 2), (0, -2, -3))
    assert (state.d, state.r, state.n) == (3, 2, 1)


def test_from_temperament_data_reads_a_standard_temperament_too():
    # with no domain prefix it is an ordinary prime-limit temperament
    state = service.from_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
    assert state.domain_basis == (2, 3, 5)
    assert state.mapping == ((1, 1, 0), (0, 1, 4))


def test_from_mapping_preserves_noncanonical_input():
    # A non-canonical generating set for meantone stays verbatim as typed,
    # while its dual (the comma basis) is canonical.
    state = service.from_mapping([[1, 1, 0], [1, 2, 4]])
    assert state.mapping == ((1, 1, 0), (1, 2, 4))
    assert state.comma_basis == ((4, -4, 1),)


def test_from_comma_basis_computes_mapping_and_preserves_input():
    state = service.from_comma_basis([[-4, 4, -1]])
    assert state.comma_basis == ((-4, 4, -1),)
    assert state.mapping == ((1, 0, -4), (0, 1, 4))
    assert (state.d, state.r, state.n) == (3, 2, 1)


def test_expand_domain_appends_prime_and_redualizes():
    state = service.expand_domain(service.from_comma_basis([[-4, 4, -1]]))
    assert state.comma_basis == ((-4, 4, -1, 0),)
    assert (state.d, state.r, state.n) == (4, 3, 1)
    # the recomputed mapping still tempers out the (now 7-limit) comma
    assert all(
        sum(m * c for m, c in zip(row, (-4, 4, -1, 0))) == 0 for row in state.mapping
    )


def test_shrink_domain_is_inverse_of_expand():
    meantone = service.from_comma_basis([[-4, 4, -1]])
    state = service.shrink_domain(service.expand_domain(meantone))
    assert state.comma_basis == ((-4, 4, -1),)
    assert state.mapping == ((1, 0, -4), (0, 1, 4))
    assert (state.d, state.r, state.n) == (3, 2, 1)


def test_remove_comma_drops_the_last_comma_and_reranks():
    st = service.from_comma_basis(((4, -4, 1), (1, 0, 0)))  # d=3, n=2, r=1
    assert (st.d, st.r, st.n) == (3, 1, 2)
    removed = service.remove_comma(st)
    assert removed.comma_basis == ((4, -4, 1),)  # the last comma is gone
    assert (removed.d, removed.r, removed.n) == (3, 2, 1)  # rank rises as nullity falls


def test_remove_comma_can_drop_an_arbitrary_index():
    # dragging a comma column out of the basis un-tempers THAT comma, not just the last
    st = service.from_comma_basis(((4, -4, 1), (1, 0, 0)))  # d=3, n=2, r=1
    dropped_first = service.remove_comma(st, 0)  # drop (4,-4,1), keep (1,0,0)
    assert dropped_first.comma_basis == service.from_comma_basis(((1, 0, 0),)).comma_basis
    assert (dropped_first.d, dropped_first.r, dropped_first.n) == (3, 2, 1)
    assert service.remove_comma(st).comma_basis == ((4, -4, 1),)  # default still drops the last


def test_remove_mapping_row_drops_a_generator_holding_dimensionality():
    # the mapping-row − drops a generator (any row), keeping the primes and tempering one
    # more comma: −r, +n, dimensionality held — the dual of the generators − (which drops a prime).
    st = service.remove_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))), 0)  # drop row 0
    assert st.mapping == ((0, 1, 4),)  # the remaining row, kept as-is
    assert (st.d, st.r, st.n) == (3, 1, 2)  # d held, rank down, nullity up


def test_add_mapping_row_un_tempers_a_comma_raising_rank():
    # the mapping + adds a generator by un-tempering a comma: +r, −n, dimensionality held — the
    # inverse direction of remove_mapping_row, and the row-space face of the comma −. Meantone
    # loses its sole comma (81/80) → 5-limit just intonation, re-dualed to clean prime generators.
    st = service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))))  # meantone, n=1
    assert st.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))  # canonical full rank (JI), not a raw comma row
    assert (st.d, st.r, st.n) == (3, 3, 0)  # +r, −n (now full rank), d held
    assert service.generators(st.mapping) == ("2/1", "3/1", "5/1")  # simple generators, not vast ratios


def test_add_mapping_row_to_combines_generators_holding_the_temperament():
    # dragging generator row A onto row B adds A into B: row B becomes A + B. A unimodular row
    # operation, so the temperament is untouched (comma basis, rank and nullity all held) — only
    # the generator basis changes. Meantone: dropping the octave (row 0) onto the fifth (row 1).
    meantone = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    combined = service.add_mapping_row_to(meantone, 0, 1)  # row 1 += row 0
    assert combined.mapping == ((1, 1, 0), (1, 2, 4))  # row 1 is the sum; row 0 kept as-is
    assert combined.comma_basis == meantone.comma_basis  # same temperament tempered out
    assert (combined.d, combined.r, combined.n) == (meantone.d, meantone.r, meantone.n)
    # the dragged generator's ratio shifts (octave → fourth); the target's stays the fifth
    assert service.generators(combined.mapping) == ("4/3", "3/2")


def test_add_comma_to_recombines_the_basis_holding_the_temperament():
    # dragging comma A onto comma B adds A into B: B's vector becomes A + B. The dual of
    # add_mapping_row_to — a unimodular column operation on the comma basis, so the temperament
    # (its mapping, rank and nullity) is untouched; only which intervals name the nullspace
    # changes. 12-ET in the 5-limit has two commas to combine.
    twelve = service.from_mapping(((12, 19, 28),))
    combined = service.add_comma_to(twelve, 0, 1)  # comma 1 += comma 0
    assert combined.comma_basis[1] == tuple(a + b for a, b in zip(twelve.comma_basis[1], twelve.comma_basis[0]))
    assert combined.comma_basis[0] == twelve.comma_basis[0]  # the dragged comma kept as-is
    assert combined.mapping == twelve.mapping  # the temperament (the mapping dual) is unchanged
    assert (combined.d, combined.r, combined.n) == (twelve.d, twelve.r, twelve.n)


def test_full_rank_mapping_has_zero_comma_and_zero_nullity():
    # Just intonation: nothing tempered out. The dual is a single zero comma.
    state = service.from_mapping([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert state.comma_basis == ((0, 0, 0),)
    assert (state.d, state.r, state.n) == (3, 3, 0)


def test_standard_primes_gives_the_domain_basis_header():
    assert service.standard_primes(3) == (2, 3, 5)
    assert service.standard_primes(5) == (2, 3, 5, 7, 11)


def test_generators_as_ratios():
    assert service.generators([[1, 1, 0], [0, 1, 4]]) == ("2/1", "3/2")


def test_generators_over_a_nonstandard_domain_multiply_out_the_basis():
    # Barbados (2.3.13/5): its detempering generators are 2/1 and the ~15/13 neutral
    # second — read over the basis, not as prime vectors
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.generators(state.mapping, domain_basis=state.domain_basis) == ("2/1", "15/13")


def test_generator_detempering_vectors():
    # the generator detempering D: one JI interval (as a vector) per generator that
    # tempers to it — the mapping's right-inverse, r vectors over the d primes. For
    # 5-limit meantone the generators are the octave 2/1 and the fifth 3/2.
    assert service.generator_detempering([[1, 1, 0], [0, 1, 4]]) == ((1, 0, 0), (-1, 1, 0))


def test_tuning_from_generators_applies_a_manual_generator_tuning():
    # a manually-set generator tuning gives tuning_map = generators · mapping (not the
    # scheme optimum) — what the optimize button freezes when its auto-lock is off. For
    # 5-limit meantone with a pure octave + pure fifth (1200, 701.955):
    tun = service.tuning_from_generators([[1, 1, 0], [0, 1, 4]], (1200.0, 701.955))
    assert tun.generator_map == (1200.0, 701.955)
    assert abs(tun.tuning_map[0] - 1200.0) < 1e-6        # prime 2 = the octave generator
    assert abs(tun.tuning_map[1] - 1901.955) < 1e-6      # prime 3 = octave + fifth
    assert abs(tun.tuning_map[2] - 4 * 701.955) < 1e-6   # prime 5 = 4 fifths


def test_tuning_holds_user_specified_intervals_just():
    # the held intervals column feeds service.tuning: an interval passed as held comes out
    # tuned exactly justly (zero error), the whole tuning reoptimized around the constraint
    tun = service.tuning([[1, 1, 0], [0, 1, 4]], held=("3/2",))
    fifth = (-1, 1, 0)  # 3/2
    tempered = sum(tun.tuning_map[p] * fifth[p] for p in range(3))
    just = sum(tun.just_map[p] * fifth[p] for p in range(3))
    assert abs(tempered - just) < 1e-6
    # without the constraint the default minimax tuning does NOT hold the fifth pure
    free = service.tuning([[1, 1, 0], [0, 1, 4]])
    assert abs(sum(free.tuning_map[p] * fifth[p] for p in range(3))
               - sum(free.just_map[p] * fifth[p] for p in range(3))) > 1e-6


def test_held_intervals_come_from_the_tuning_scheme():
    # the held intervals (tuned exactly justly) are trait 0 of the tuning scheme,
    # surfaced as ratios. The canonical minimax-S holds nothing; a held-octave
    # scheme like held-octave minimax-ES holds the octave.
    assert service.held_intervals("minimax-S", 3) == ()
    assert service.held_intervals() == ()  # defaults to the canonical scheme (minimax-S)
    assert service.held_intervals("held-octave minimax-ES", 3) == ("2/1",)


def test_comma_ratios_renders_each_comma_vector_as_a_ratio():
    # the comma basis as ratio strings, mirroring service.generators for the maps
    assert service.comma_ratios(((4, -4, 1),)) == ("80/81",)  # the syntonic comma, as-is
    assert service.comma_ratios(((4, -4, 1), (0, 0, 0))) == ("80/81", "1/1")


def test_comma_ratios_over_a_nonstandard_domain_multiply_out_the_basis():
    # the comma vector (2 -3 2) is over the basis 2.3.13/5, so its ratio is
    # 2^2·3^-3·(13/5)^2 = 676/675 (the Barbados comma) — not the prime-vector reading 100/27
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.comma_ratios(state.comma_basis, domain_basis=state.domain_basis) == ("676/675",)


def test_mapped_intervals():
    mapped = service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
    assert mapped == ((1, 0, -2, 2), (0, 1, 4, -3))


def test_mapped_intervals_over_a_nonstandard_domain_express_in_the_basis():
    # mapping the basis elements (unit vectors over 2.3.13/5) through M reproduces M itself,
    # which only holds if the ratios are expressed in the nonprime basis
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    mapped = service.mapped_intervals(
        state.mapping, ("2/1", "3/1", "13/5"), domain_basis=state.domain_basis
    )
    assert mapped == state.mapping


def test_mapped_intervals_of_the_empty_set_is_empty_rows():
    # one (empty) generator row per mapping row, so the r x m matrix stays well-formed
    assert service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ()) == ((), ())


def test_mapped_commas_vanish():
    # every comma the temperament tempers out maps through M to zero (it vanishes)
    mapped = service.mapped_commas([[1, 1, 0], [0, 1, 4]], [[4, -4, 1]])
    assert mapped == ((0,), (0,))  # r=2 generator coords, nc=1 comma, all zero


def test_canonical_mapping_defactors_and_hnfs():
    # the canonical form of the mapping (defactored, then Hermite Normal Form) — the
    # row content of the "canonical mapping" form box; it can differ from the stored
    # matrix, e.g. ((1,1,0),(0,1,4)) canonicalizes to ((1,0,-4),(0,1,4))
    assert service.canonical_mapping([[1, 1, 0], [0, 1, 4]]) == ((1, 0, -4), (0, 1, 4))
    # an already-canonical mapping is returned unchanged
    assert service.canonical_mapping([[1, 0, -4], [0, 1, 4]]) == ((1, 0, -4), (0, 1, 4))


def test_form_matrix_is_the_generator_change_of_basis_to_canonical():
    # the generator form matrix F: the unimodular r×r matrix with F·M = canonical(M).
    # For ((1,1,0),(0,1,4)) — canonical ((1,0,-4),(0,1,4)) — F = ((1,-1),(0,1)).
    assert service.form_matrix([[1, 1, 0], [0, 1, 4]]) == ((1, -1), (0, 1))
    # an already-canonical mapping has F = the identity
    assert service.form_matrix([[1, 0, -4], [0, 1, 4]]) == ((1, 0), (0, 1))


def test_canonical_comma_basis_defactors_and_canonicalizes():
    # the comma-basis analogue of canonical_mapping: a non-saturated basis (the syntonic
    # comma doubled) canonicalizes back to the saturated, sign-normalized form
    assert service.canonical_comma_basis([[-8, 8, -2]]) == ((4, -4, 1),)
    assert service.canonical_comma_basis([[4, -4, 1]]) == ((4, -4, 1),)


def test_target_interval_vectors():
    # the interval-vector form of each target over the 2.3.5 domain
    vectors = service.target_interval_vectors(("2/1", "3/2", "5/4", "6/5"), 3)
    assert vectors == ((1, 0, 0), (-1, 1, 0), (-2, 0, 1), (1, 1, -1))


def test_target_interval_vectors_over_a_nonstandard_domain():
    # the basis elements of 2.3.13/5 are the identity vectors over that basis
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    vectors = service.target_interval_vectors(
        ("2/1", "3/1", "13/5"), state.d, domain_basis=state.domain_basis
    )
    assert vectors == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_interval_vector_parses_a_ratio_into_its_vector():
    # the inverse of comma_ratios, for the editable quantities-row ratio cells: one ratio
    # string back to its interval vector over the d domain primes (a round trip)
    assert service.interval_vector("80/81", 3) == (4, -4, 1)  # the syntonic comma, as comma_ratios shows it
    assert service.interval_vector("5/4", 3) == (-2, 0, 1)
    assert service.interval_vector("2", 3) == (1, 0, 0)  # a bare integer is the prime-2 octave
    basis = ((4, -4, 1), (0, 0, 0))
    assert tuple(service.interval_vector(r, 3) for r in service.comma_ratios(basis)) == basis


def test_interval_vector_raises_a_classified_error_for_bad_input():
    # bad input raises ValueError with a user-facing message the cell surfaces as a toast — and
    # the two failure modes read differently: unparseable / non-positive vs outside the prime limit
    with pytest.raises(ValueError, match="not a valid ratio"):
        service.interval_vector("nonsense", 3)
    with pytest.raises(ValueError, match="not a valid ratio"):
        service.interval_vector("", 3)
    with pytest.raises(ValueError, match="not a positive ratio"):
        service.interval_vector("0", 3)
    with pytest.raises(ValueError, match="outside the 2.3.5 domain"):
        service.interval_vector("7/4", 3)  # prime 7 is beyond the 2.3.5 domain


def test_interval_vector_names_a_nonstandard_domain_in_its_out_of_limit_error():
    # the out-of-limit message names the actual domain basis, not just the standard primes
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    with pytest.raises(ValueError, match=r"outside the 2.3.13/5 domain"):
        service.interval_vector("5/4", state.d, domain_basis=state.domain_basis)  # 5/4 isn't in the subgroup


def test_interval_vector_over_a_nonstandard_domain_expresses_in_the_basis():
    # the ratio is read over the (nonprime) basis elements, like target_interval_vectors
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.interval_vector("13/5", state.d, domain_basis=state.domain_basis) == (0, 0, 1)
    assert service.interval_vector("676/675", state.d, domain_basis=state.domain_basis) == (2, -3, 2)


def test_tilt_target_interval_set_is_the_domains_tilt():
    # the 5-limit default is the 6-TILT (the integer just below the next prime past 5)
    assert service.target_interval_set("TILT", (2, 3, 5)) == (
        "2/1", "3/1", "3/2", "4/3", "5/2", "5/3", "5/4", "6/5",
    )


def test_tilt_target_interval_set_tracks_the_domain():
    # adding prime 7 grows the default to a superset (the 10-TILT); a 7-limit
    # interval that could not appear before now does
    five_limit = set(service.target_interval_set("TILT", (2, 3, 5)))
    seven_limit = set(service.target_interval_set("TILT", (2, 3, 5, 7)))
    assert five_limit < seven_limit
    assert "7/4" in seven_limit


def test_target_interval_set_filters_to_a_nonstandard_subgroup():
    # over 2.3.13/5 only intervals that lie in the subgroup survive: 5/4 (a pure-5
    # interval, 5 unreachable) is dropped, while 3/2 and 13/5 remain
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    targets = service.target_interval_set("TILT", state.domain_basis)
    assert "5/4" not in targets and "7/3" not in targets
    assert "3/2" in targets and "13/5" in targets
    # every survivor is expressible as an integer vector over the (nonprime) basis
    vectors = service.target_interval_vectors(targets, state.d, domain_basis=state.domain_basis)
    assert len(vectors) == len(targets)


def test_old_target_interval_set_is_the_odd_limit_diamond():
    # OLD selects the odd-limit-diamond family instead of the TILT triangle
    old = service.target_interval_set("OLD", (2, 3, 5))
    assert "5/4" in old and "6/5" in old and "8/5" in old  # diamond ratios
    assert old != service.target_interval_set("TILT", (2, 3, 5))


def test_displayed_targets_resolve_the_one_list_the_grid_and_plain_text_share():
    # the single seam both views read so they can't diverge: a target-based scheme resolves the
    # named/TILT set (an override curates it), but an all-interval scheme auto-replaces the list
    # with Tₚ = 𝐈 — the domain basis itself — overriding even a typed override.
    st = service.from_mapping([[1, 1, 0], [0, 1, 4]])  # domain 2.3.5
    assert service.displayed_targets(st, "TILT minimax-S") == service.target_interval_set("TILT", (2, 3, 5))
    assert service.displayed_targets(st, "TILT minimax-S", target_override=("2/1", "3/2")) == ("2/1", "3/2")
    # all-interval: the identity (every prime its own proxy), even with a stale override present
    assert service.displayed_targets(st, "minimax-S") == ("2/1", "3/1", "5/1")
    assert service.displayed_targets(st, "minimax-S", target_override=("2/1", "3/2")) == ("2/1", "3/1", "5/1")


def test_default_target_limit_is_the_number_a_bare_family_resolves_to():
    # 2.3.5: TILT defaults to the 6-TILT, OLD to the 5-OLD (so the chooser shows a
    # real number, not "auto"); both grow with the domain
    assert service.default_target_limit("TILT", (2, 3, 5)) == 6
    assert service.default_target_limit("OLD", (2, 3, 5)) == 5
    assert service.default_target_limit("TILT", (2, 3, 5, 7)) == 10


def test_target_limit_problem_validates_the_chooser_entry():
    # the odd-limit diamond (OLD) is odd by construction, so an even limit is invalid; the
    # truncated integer-limit triangle (TILT) accepts any whole number. A non-whole / unparseable
    # entry is invalid for either family. A blank (or zero) entry is fine — the family then
    # tracks the domain default. (None family = an override / all-interval chooser: no parity rule.)
    assert service.target_limit_problem("OLD", 8) == "odd"      # even odd-limit -> rejected
    assert service.target_limit_problem("OLD", 8.0) == "odd"    # ...as a float too (ui.number gives floats)
    assert service.target_limit_problem("OLD", 9) is None       # odd odd-limit -> fine
    assert service.target_limit_problem("TILT", 8) is None      # even is fine for the triangle
    assert service.target_limit_problem("TILT", 9.5) == "whole" # a decimal isn't a whole number
    assert service.target_limit_problem("OLD", "abc") == "whole"  # unparseable text
    assert service.target_limit_problem("OLD", None) is None    # blank -> the domain default
    assert service.target_limit_problem("OLD", "") is None      # blank -> the domain default
    assert service.target_limit_problem("OLD", 0) is None       # zero reads as blank (matches the chooser)
    assert service.target_limit_problem(None, 8) is None        # no named family -> no parity rule


def test_tuning_maps_under_top():
    import pytest

    # tuning() now yields only the temperament-level prime maps (no interval set)
    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    assert t.generator_map == pytest.approx((1201.699, 697.564), abs=1e-2)
    assert t.tuning_map == pytest.approx((1201.699, 1899.263, 2790.258), abs=1e-2)
    assert t.just_map == pytest.approx((1200.0, 1901.955, 2786.314), abs=1e-2)
    assert t.retuning_map == pytest.approx((1.699, -2.692, 3.944), abs=1e-2)


def test_tuning_threads_an_explicit_standard_basis_like_the_default():
    # passing the resolved standard primes is identical to passing nothing
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    assert (
        service.tuning(state.mapping, domain_basis=state.domain_basis).generator_map
        == service.tuning(state.mapping).generator_map
    )


def test_tuning_over_a_nonstandard_domain_uses_the_basis_elements():
    import pytest

    # over 2.3.13/5 the just map is the size of each (possibly nonprime) element,
    # and the maps run over the d=3 elements / r=2 generators
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    t = service.tuning(state.mapping, domain_basis=state.domain_basis)
    assert len(t.generator_map) == state.r and len(t.tuning_map) == state.d
    assert t.just_map == pytest.approx(
        (1200.0, 1901.955, 1200.0 * math.log2(13 / 5)), abs=1e-2
    )


def test_tuning_mode_changes_the_nonstandard_optimum():
    import pytest

    # 2.7/3.11/3 over the default TILT, minimax-C: the neutral and nonprime-based
    # approaches give different optimal generators (library tests.m 3733-3762)
    state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    neutral = service.tuning(state.mapping, "TILT minimax-C", domain_basis=state.domain_basis)
    nonprime = service.tuning(
        state.mapping, "TILT minimax-C", domain_basis=state.domain_basis,
        nonprime_approach="nonprime-based",
    )
    assert neutral.generator_map == pytest.approx((1194.291, 135.186), abs=1e-2)
    assert nonprime.generator_map == pytest.approx((1192.399, 133.768), abs=1e-2)


def test_interval_sizes_project_a_set_through_the_tuning():
    import pytest

    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    s = service.interval_sizes(t, ("2/1", "3/2", "5/4", "6/5"))
    assert s.tempered == pytest.approx((1201.699, 697.564, 386.861, 310.704), abs=1e-2)
    assert s.just == pytest.approx((1200.0, 701.955, 386.314, 315.641), abs=1e-2)
    assert s.errors == pytest.approx((1.699, -4.391, 0.547, -4.937), abs=1e-2)
    assert s.damage == pytest.approx((1.699, 4.391, 0.547, 4.937), abs=1e-2)
    assert all(d >= 0 for d in s.damage)  # damage is non-negative


def test_interval_sizes_over_a_nonstandard_domain_express_intervals_in_the_basis():
    import pytest

    # over 2.3.13/5 a basis element is a unit vector, so its tempered/just size must equal
    # the corresponding map entry — only true if the ratio is expressed in the (nonprime)
    # basis, not parsed over standard primes (where 13/5 would lose its 13)
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    tun = service.tuning(state.mapping, domain_basis=state.domain_basis)
    s = service.interval_sizes(tun, ("2/1", "3/1", "13/5"), domain_basis=state.domain_basis)
    assert s.tempered == pytest.approx(tun.tuning_map, abs=1e-6)
    assert s.just == pytest.approx(tun.just_map, abs=1e-6)


def test_interval_sizes_of_the_empty_set_are_empty():
    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    s = service.interval_sizes(t, ())
    assert (s.tempered, s.just, s.errors, s.damage) == ((), (), (), ())


def test_interval_weights_follow_the_schemes_damage_slope():
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]  # meantone over 2.3.5
    ratios = ("2/1", "3/2", "5/4")
    # default log-prime (taxicab) complexities: log2 of each interval's primes
    complexities = (1.0, 2.585, 4.322)
    # unity weight -> every weight is 1
    assert service.interval_weights(mapping, "minimax-U", ratios) == pytest.approx((1.0, 1.0, 1.0))
    # complexity weight -> the weight IS the complexity
    assert service.interval_weights(mapping, "minimax-C", ratios) == pytest.approx(complexities, abs=1e-3)
    # simplicity weight (the shipped default's slope) -> 1 / complexity
    assert service.interval_weights(mapping, "minimax-S", ratios) == pytest.approx(
        tuple(1 / c for c in complexities), abs=1e-3
    )


def test_interval_weights_of_the_empty_set_are_empty():
    assert service.interval_weights([[1, 1, 0], [0, 1, 4]], "minimax-S", ()) == ()


def test_interval_weight_uses_the_full_domain_basis_vector():
    import pytest

    # minimax-S weights by simplicity (1 / complexity), so the weight of the 2.3.13/5 basis
    # element "13/5" is 1 / log2(65) — derived from its domain-basis vector, the same fix
    # the complexity row needs (both share _temperament_spec_vectors).
    mapping = [[1, 2, 2], [0, -2, -3]]  # Barbados over 2.3.13/5
    db = (2, 3, Fraction(13, 5))
    got = service.interval_weights(mapping, "minimax-S", ("13/5",), domain_basis=db)[0]
    assert got == pytest.approx(1 / math.log2(13 * 5), abs=1e-6)


def test_plain_text_complexity_runs_over_the_nonstandard_domain_basis():
    # the complexity band must express each ratio over the domain basis, like the grid:
    # a 13/5 target over 2.3.13/5 takes its basis-vector height (log2(65)), not the prime-
    # truncated reading. Guards that plain_text_values threads the domain basis to the seam.
    state = service.parse_mapping_state("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    targets = ("13/5", "3/2")
    band = service.plain_text_values(state, "minimax-S", target_override=targets)[("complexity", "targets")]
    over_basis = service.interval_complexities(state.mapping, "minimax-S", targets, domain_basis=state.domain_basis)
    truncated = service.interval_complexities(state.mapping, "minimax-S", targets)  # no basis: drops the 13
    assert service.cents(over_basis[0]) in band     # the domain-basis height shows
    assert service.cents(truncated[0]) not in band  # not the prime-truncated value


def test_interval_complexities_norm_each_intervals_prescaled_vector():
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]  # meantone over 2.3.5
    ratios = ("2/1", "3/2", "5/4")
    # default log-prime taxicab complexity: sum of |vector[i]| * log2(prime_i).
    # Independent of the damage slope (slope weights damage; complexity is the norm itself).
    expected = (1.0, 2.585, 4.322)
    assert service.interval_complexities(mapping, "minimax-S", ratios) == pytest.approx(expected, abs=1e-3)
    assert service.interval_complexities(mapping, "minimax-C", ratios) == pytest.approx(expected, abs=1e-3)


def test_interval_complexities_of_the_empty_set_are_empty():
    assert service.interval_complexities([[1, 1, 0], [0, 1, 4]], "minimax-S", ()) == ()


def test_interval_complexity_uses_the_full_domain_basis_vector():
    import pytest

    # Over a nonstandard domain 2.3.13/5, the target "13/5" IS the third basis element
    # (the unit vector [0 0 1]), not a 13-limit prime rational. Its log-prime complexity
    # is the height log2(13*5) = log2(65). Without the domain basis threaded through, the
    # ratio parsed to a length-6 prime vector that was silently truncated to d=3 — dropping
    # the 13 and reporting log2(5) for an interval that has no 5 in this basis.
    mapping = [[1, 2, 2], [0, -2, -3]]  # Barbados over 2.3.13/5
    db = (2, 3, Fraction(13, 5))
    got = service.interval_complexities(mapping, "minimax-S", ("13/5",), domain_basis=db)[0]
    assert got == pytest.approx(math.log2(13 * 5), abs=1e-6)


def test_scheme_with_prescaler_swaps_the_prescaler_preserving_the_rest():
    import pytest

    m = [[1, 1, 0], [0, 1, 4]]
    # swapping the prescaler changes the prescaler diagonal: log-prime -> prime (diag prime),
    # -> identity (diag 1)
    assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "prime")) == pytest.approx((2.0, 3.0, 5.0))
    assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "identity")) == pytest.approx((1.0, 1.0, 1.0))
    assert service.complexity_prescaler(m, service.scheme_with_prescaler("minimax-S", "log-prime")) == pytest.approx((1.0, 1.585, 2.322), abs=1e-3)
    # the optimization power and damage slope ride along unchanged
    assert service.damage_weight_slope(service.scheme_with_prescaler("miniRMS-C", "prime")) == "complexityWeight"
    assert service.optimization_power(service.scheme_with_prescaler("miniRMS-C", "prime")) == 2
    # round trip: keeping the same (log-prime) prescaler yields the identical tuning
    same = service.scheme_with_prescaler("minimax-S", "log-prime")
    assert service.tuning(m, same).tuning_map == pytest.approx(service.tuning(m, "minimax-S").tuning_map, abs=1e-6)


def test_scheme_with_prescaler_preserves_the_size_factor():
    # the prescaler chooser swaps only the DIAGONAL (the top d×d of 𝑋); it must NOT clear the size
    # factor ("replace diminuator"). The diagonal 𝐷 and the size-sensitizing 𝑍 are independent axes,
    # so picking a prescaler while the diminuator is on keeps it on (lp -> prime stays size-factored).
    lils = service.scheme_with_diminuator("minimax-S", True)  # diminuator ON (lils)
    assert service.diminuator_replaced(lils) is True
    swapped = service.scheme_with_prescaler(lils, "prime")
    assert service.diminuator_replaced(swapped) is True   # still on after swapping the diagonal
    assert service.prescaler_of(swapped) == "prime"       # the diagonal did change
    # and toggling back to log-prime keeps it on too
    assert service.diminuator_replaced(service.scheme_with_prescaler(lils, "log-prime")) is True


def test_scheme_with_complexity_norm_power_sets_the_norm_and_its_dual():
    import pytest

    m = [[1, 1, 0], [0, 1, 4]]  # 2.3.5
    # taxicab (default, q=1): complexity of 3/2 = |−1|·log2 2 + |1|·log2 3 = 2.585
    assert service.complexity_norm_power("minimax-S") == 1
    assert service.interval_complexities(m, "minimax-S", ("3/2",))[0] == pytest.approx(2.585, abs=1e-3)
    eucl = service.scheme_with_complexity_norm_power("minimax-S", 2)
    assert service.complexity_norm_power(eucl) == 2
    # Euclidean (q=2): sqrt(1^2 + log2(3)^2) = sqrt(1 + 2.512) = 1.874
    assert service.interval_complexities(m, eucl, ("3/2",))[0] == pytest.approx(1.874, abs=1e-3)
    # it preserves the prescaler and damage slope, only changing the norm power
    assert service.prescaler_of(eucl) == "log-prime"
    assert service.damage_weight_slope(eucl) == "simplicityWeight"
    # the dual norm power dual(q) = q/(q−1): dual(1) = ∞, dual(2) = 2
    assert service.dual_norm_power("minimax-S") == float("inf")
    assert service.dual_norm_power(eucl) == pytest.approx(2.0)


def test_is_euclidean_reports_the_complexity_norm_power():
    assert service.is_euclidean("minimax-S") is False   # taxicab (q=1)
    assert service.is_euclidean("minimax-ES") is True    # Euclidean (q=2)
    assert service.is_euclidean(service.scheme_with_complexity_norm_power("minimax-S", 2)) is True


def test_prescaler_of_reports_the_schemes_current_prescaler():
    assert service.prescaler_of("minimax-S") == "log-prime"  # the default
    assert service.prescaler_of("minimax-sopfr-S") == "prime"  # sopfr
    assert service.prescaler_of("minimax-copfr-S") == "identity"  # unweighted count
    # it round-trips with scheme_with_prescaler
    assert service.prescaler_of(service.scheme_with_prescaler("minimax-S", "prime")) == "prime"


def test_displayed_prescaler_name_falls_back_to_none_on_a_deviating_override():
    # the prescaler chooser shows the scheme's named prescaler, or None ("-") when a custom
    # diagonal override deviates from it — the seam the bare prescaler tile's manual edits ride.
    mapping = ((1, 1, 0), (0, 1, 4))
    # no override -> the scheme's own prescaler name (like prescaler_of)
    assert service.displayed_prescaler_name(mapping, "minimax-S") == "log-prime"
    assert service.displayed_prescaler_name(mapping, "minimax-sopfr-S") == "prime"
    # an override EQUAL to the scheme's computed diagonal still reads as the named prescaler
    same = service.complexity_prescaler(mapping, "minimax-S")
    assert service.displayed_prescaler_name(mapping, "minimax-S", same) == "log-prime"
    # a DEVIATING override -> None (the chooser shows "-")
    assert service.displayed_prescaler_name(mapping, "minimax-S", (1.0, 9.9, 2.322)) is None


def test_displayed_prescaler_name_recognizes_a_rounded_return_to_the_scheme_diagonal():
    # a prescaler cell shows its value rounded (prescale_text, 3-dp), and editing stores that shown
    # value — so a round-trip (deviate a cell, then type the shown log-prime value back) leaves a
    # diagonal differing from the full-precision scheme diagonal only by display rounding. That must
    # still read as the scheme's prescaler — not "-" — so the chooser and the 𝑋 = 𝐿 awareness recover.
    mapping = ((1, 1, 0), (0, 1, 4))
    computed = service.complexity_prescaler(mapping, "minimax-S")           # (1, 1.5849625…, 2.3219281…)
    shown = tuple(float(service.prescale_text(v)) for v in computed)        # (1.0, 1.585, 2.322)
    assert shown != computed                                               # the rounding really differs
    assert service.displayed_prescaler_name(mapping, "minimax-S", shown) == "log-prime"


def test_scheme_with_weight_slope_swaps_the_damage_slope_preserving_the_rest():
    # the weight box's "damage weight slope" chooser: swap how complexity becomes a weight
    # (unity 𝒘=1, complexity 𝒘=𝒄, simplicity 𝒘=1/𝒄) without disturbing the complexity itself.
    assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-S", "unity-weight")) == "unityWeight"
    assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-S", "complexity-weight")) == "complexityWeight"
    assert service.damage_weight_slope(service.scheme_with_weight_slope("minimax-U", "simplicity-weight")) == "simplicityWeight"
    # the prescaler, norm and optimization power ride along unchanged
    swapped = service.scheme_with_weight_slope("minimax-sopfr-ES", "unity-weight")
    assert service.prescaler_of(swapped) == "prime"  # sopfr kept
    assert service.is_euclidean(swapped) is True      # E kept
    assert service.optimization_power(swapped) == math.inf


def test_weight_slope_of_reports_the_schemes_current_slope():
    assert service.weight_slope_of("minimax-S") == "simplicity-weight"  # the canonical all-interval scheme
    assert service.weight_slope_of("minimax-U") == "unity-weight"
    assert service.weight_slope_of("minimax-C") == "complexity-weight"
    # it round-trips with scheme_with_weight_slope
    assert service.weight_slope_of(service.scheme_with_weight_slope("minimax-S", "unity-weight")) == "unity-weight"


def test_scheme_with_complexity_sets_the_prescaler_norm_and_size_factor():
    # the predefined-complexities master chooser sets the whole complexity shape at once:
    # the prescaler (log-prime/prime/identity) and the norm power (taxicab/Euclidean).
    copfr = service.scheme_with_complexity("minimax-S", "copfr")  # unweighted count
    assert service.prescaler_of(copfr) == "identity" and service.is_euclidean(copfr) is False
    assert service.prescaler_of(service.scheme_with_complexity("minimax-S", "sopfr")) == "prime"  # sopfr
    lpe = service.scheme_with_complexity("minimax-S", "lp-E")  # E-lp
    assert service.prescaler_of(lpe) == "log-prime" and service.is_euclidean(lpe) is True
    # the optimization power and damage slope ride along unchanged
    assert service.optimization_power(service.scheme_with_complexity("miniRMS-C", "copfr")) == 2
    assert service.damage_weight_slope(service.scheme_with_complexity("miniRMS-C", "copfr")) == "complexityWeight"


def test_scheme_with_complexity_lols_holds_the_octave_others_clear_it():
    # lols (log-odd-limit) is lils plus a held octave (trait 0); selecting it tunes 2/1 just
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols")) == ("2/1",)
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols-E")) == ("2/1",)
    # lils does NOT hold the octave
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lils")) == ()
    # a non-lols complexity clears a previously-held octave (the held interval is its own)
    assert service.held_intervals(service.scheme_with_complexity("held-octave minimax-ES", "lp")) == ()


def test_complexity_name_of_reports_the_named_complexity_else_custom():
    assert service.complexity_name_of("minimax-S") == "lp"    # the default (log-prime taxicab)
    assert service.complexity_name_of("minimax-ES") == "lp-E"  # E-lp
    assert service.complexity_name_of("minimax-copfr-S") == "copfr"
    assert service.complexity_name_of("minimax-sopfr-S") == "sopfr"
    assert service.complexity_name_of("minimax-lils-S") == "lils"
    assert service.complexity_name_of("minimax-lols-S") == "lols"  # lils + held octave
    # it round-trips with scheme_with_complexity
    assert service.complexity_name_of(service.scheme_with_complexity("minimax-S", "sopfr-E")) == "sopfr-E"
    # an lp shape that also holds the octave is no named complexity (lp clears the octave): custom
    assert service.complexity_name_of("held-octave minimax-S") == "custom"


def test_scheme_with_diminuator_toggles_the_size_factor_between_lp_and_lils():
    # the box-𝐋 "replace diminuator" checkbox (the size-factor trait 5c): replacing the diminuator
    # (the lesser of num/den) replaces it with the numinator — the integer-limit/lils behavior.
    assert service.diminuator_replaced("minimax-S") is False  # lp (default) uses the diminuator
    replaced = service.scheme_with_diminuator("minimax-S", True)  # lp -> lils
    assert service.diminuator_replaced(replaced) is True
    assert service.complexity_name_of(replaced) == "lils"
    # keeping the diminuator returns lils -> lp
    kept = service.scheme_with_diminuator("minimax-lils-S", False)
    assert service.diminuator_replaced(kept) is False and service.complexity_name_of(kept) == "lp"
    # the prescaler, norm and damage slope ride along unchanged
    on_sopfr = service.scheme_with_diminuator("minimax-sopfr-ES", True)
    assert service.prescaler_of(on_sopfr) == "prime" and service.is_euclidean(on_sopfr) is True


def test_complexity_size_factor_reports_the_schemes_size_factor():
    # the size factor (trait 5c) the "replace diminuator" checkbox toggles: 0 for lp (the
    # square pretransformer), 1 for lils (the rectangular ZL, with the guide's size row). The
    # renderer sizes the prescaling matrix's extra row off this.
    assert service.complexity_size_factor("minimax-S") == 0
    assert service.complexity_size_factor("minimax-lils-S") == 1
    assert service.complexity_size_factor("TILT minimax-lils-S") == 1


def test_damage_weight_matrix_left_inverts_the_rectangular_pretransformer():
    import numpy as np
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]
    # with the size factor on (lils), the weight has no per-prime-list form: it is the d×(d+1)
    # left inverse 𝑊 = (𝑍𝐿)⁻ = 𝐿⁻¹𝑍⁻ (the guide's representative; 𝑍⁻ = [𝐼 − ½𝐽 | ½𝟏])
    W = np.array(service.damage_weight_matrix(mapping, "minimax-lils-S"))
    assert W.shape == (3, 4)
    L = np.diag(service.complexity_prescaler(mapping, "minimax-S"))
    ZL = np.vstack([np.eye(3), np.ones(3)]) @ L
    assert np.allclose(W @ ZL, np.eye(3))   # it left-inverts the rectangular pretransformer 𝑋 = 𝑍𝐿
    # row 0 is the guide's representative ½[1,-1,-1,1] (𝐿₀ = log₂2 = 1); row 1 divides by log₂3
    assert W[0] == pytest.approx([0.5, -0.5, -0.5, 0.5])
    assert W[1] == pytest.approx([-0.31546, 0.31546, -0.31546, 0.31546], abs=1e-4)


def test_complexity_prescaler_is_the_diagonal_of_per_prime_weights():
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]  # 2.3.5 domain
    # the default log-prime prescaler L = diag(log2(prime))
    assert service.complexity_prescaler(mapping, "minimax-S") == pytest.approx((1.0, 1.585, 2.322), abs=1e-3)
    # sopfr prescaler weights each prime by the prime itself
    assert service.complexity_prescaler(mapping, "minimax-sopfr-S") == pytest.approx((2.0, 3.0, 5.0), abs=1e-3)


def test_complexity_prescaler_override_short_circuits_the_schemes_diagonal():
    # the bare prescaler tile's editable cells write a custom diagonal the user types in;
    # the service threads that diagonal through every consumer by accepting it as an
    # override — bypassing the scheme's log-prime / prime / identity computation entirely
    mapping = [[1, 1, 0], [0, 1, 4]]
    custom = (2.0, 3.0, 5.0)
    assert service.complexity_prescaler(mapping, "minimax-S", override=custom) == custom
    # None falls back to the scheme's computed diagonal (today's behavior)
    assert service.complexity_prescaler(mapping, "minimax-S", override=None) == \
        service.complexity_prescaler(mapping, "minimax-S")


def test_interval_complexities_use_the_prescaler_override():
    import pytest

    # the complexity row reads the same prescaler the matrix shows, so a custom diagonal
    # flows into it directly. The override (2, 3, 5) IS the sopfr prescaler, so the
    # complexities under the default scheme + override should match the sopfr scheme's
    mapping = [[1, 1, 0], [0, 1, 4]]
    ratios = ("3/2", "5/4")
    overridden = service.interval_complexities(
        mapping, "minimax-S", ratios, prescaler_override=(2.0, 3.0, 5.0))
    sopfr = service.interval_complexities(mapping, "minimax-sopfr-S", ratios)
    assert overridden == pytest.approx(sopfr, abs=1e-6)


def test_interval_complexities_accept_a_full_matrix_pretransformer():
    import numpy as np
    import pytest

    # the editable pretransformer can be a full (non-diagonal) matrix 𝑋, not just a diagonal: the
    # complexity is then ‖𝑋·v‖ (a matrix-vector product) — the general pretransformer form. The 0.5
    # off the diagonal couples prime 3 into prime 2's row.
    mapping = [[1, 1, 0], [0, 1, 4]]
    X = ((1.0, 0.5, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 3.0))
    comps = service.interval_complexities(mapping, "minimax-S", ("3/2", "5/4"), prescaler_override=X)
    # minimax-S is taxicab (q=1), no size factor: complexity = ‖𝑋·v‖₁
    for got, vec in zip(comps, ([-1, 1, 0], [-2, 0, 1])):
        assert got == pytest.approx(float(np.linalg.norm(np.array(X) @ np.array(vec), 1)))


def test_interval_weights_use_the_prescaler_override():
    import pytest

    # damage weights flow off complexity (when the slope isn't unity), so the override
    # flows there too: an override that matches sopfr's diagonal yields sopfr's weights
    mapping = [[1, 1, 0], [0, 1, 4]]
    targets = ("3/2", "5/4", "5/3")
    overridden = service.interval_weights(
        mapping, "minimax-S", targets, prescaler_override=(2.0, 3.0, 5.0))
    sopfr = service.interval_weights(mapping, "minimax-sopfr-S", targets)
    assert overridden == pytest.approx(sopfr, abs=1e-6)


def test_tuning_uses_the_prescaler_override():
    import pytest

    # the tuning solve weights its damage minimization by complexity-derived weights, so
    # the override reaches the optimum — overriding to the sopfr diagonal yields the
    # tuning the sopfr scheme would have produced
    mapping = [[1, 1, 0], [0, 1, 4]]
    overridden = service.tuning(mapping, "minimax-S", prescaler_override=(2.0, 3.0, 5.0))
    sopfr = service.tuning(mapping, "minimax-sopfr-S")
    assert overridden.tuning_map == pytest.approx(sopfr.tuning_map, abs=1e-6)
    assert overridden.generator_map == pytest.approx(sopfr.generator_map, abs=1e-6)


def test_all_interval_solver_handles_a_non_diagonal_pretransformer():
    import numpy as np
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]
    # a 2-D DIAGONAL override gives the SAME all-interval tuning as the equivalent 1-D diagonal —
    # the new X⁻¹-columns objective reduces to the old per-prime path for a diagonal matrix
    diag = (1.0, 1.585, 2.322)
    diag_2d = tuple(tuple(diag[i] if i == k else 0.0 for k in range(3)) for i in range(3))
    t1 = service.tuning(mapping, "minimax-S", prescaler_override=diag)
    t2 = service.tuning(mapping, "minimax-S", prescaler_override=diag_2d)
    assert t2.tuning_map == pytest.approx(t1.tuning_map, abs=1e-4)
    # a NON-diagonal pretransformer: the all-interval solve minimizes the TRUE objective ‖𝒓𝑋⁻¹‖∞
    # (minimax-S's dual norm power is ∞), not the per-prime diagonal approximation
    nondiag = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
    t3 = service.tuning(mapping, "minimax-S", prescaler_override=nondiag)
    M, j = np.array(mapping, float), np.array(t3.just_map)
    Xinv = np.linalg.inv(np.array(nondiag))
    obj = lambda g: float(np.max(np.abs((np.array(g) @ M - j) @ Xinv)))
    g0 = np.array(t3.generator_map)
    base = obj(g0)
    # g0 is the minimax of ‖𝒓𝑋⁻¹‖∞: no small generator perturbation reduces the objective
    for dg in ([0.5, 0], [0, 0.5], [-0.5, 0], [0, -0.5], [0.3, 0.3], [-0.3, 0.3]):
        assert obj(g0 + np.array(dg)) >= base - 1e-6


def test_tuning_optimizes_over_an_explicit_target_override():
    import pytest

    # a typed explicit target interval list (the target-list override) replaces the scheme's
    # named TILT/OLD set, so the optimum minimizes damage over THOSE intervals — targeting only
    # 2/1 + 3/2 under minimax-U makes the fifth pure (701.955 c), unlike the full TILT optimum
    mapping = [[1, 1, 0], [0, 1, 4]]
    base = service.tuning(mapping, "TILT minimax-U")
    targeted = service.tuning(mapping, "TILT minimax-U", targets=("2/1", "3/2"))
    assert targeted.generator_map != base.generator_map
    assert targeted.generator_map == pytest.approx((1200.0, 701.955), abs=1e-2)


def test_plain_text_tuning_follows_a_target_override():
    # plain_text_values must show the same tuning the grid builds, so a typed target-list override
    # retunes its tuning rows too (not just the target-column values) — else the EBK dual would
    # disagree with the grid once the list is overridden
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    base = service.plain_text_values(state, "TILT minimax-U", "TILT")
    overridden = service.plain_text_values(state, "TILT minimax-U", "TILT", target_override=("2/1", "3/2"))
    assert overridden[("tuning", "gens")] != base[("tuning", "gens")]


def test_plain_text_mapping_is_the_ebk_string():
    # the mapping tile's plain-text value is the temperament's EBK string: a list
    # of per-generator maps, ⟨ … ] inside, enclosed by the rank-count [ … }
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert pt[("mapping", "primes")] == "[⟨1 1 0] ⟨0 1 4]}"


def test_plain_text_basis_and_ratio_quantities():
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert pt[("quantities", "primes")] == "2.3.5"  # the domain basis, dot notation
    # the generators carry no plain-text form (the mapping/quantities tile stays bare)
    assert ("mapping", "quantities") not in pt
    # the per-ratio quantity sets (commas, targets) are placed per column by the
    # layout, directly below each ratio — they are not packed into one brace-set here
    assert ("quantities", "commas") not in pt
    assert ("quantities", "targets") not in pt


def test_plain_text_interval_vectors_are_vector_lists():
    # the interval-vectors row shows each basis as a list of vectors (close ⟩), wrapped in an
    # outer [ … ]. A target-based scheme so the targets are the curated TILT set, not Tₚ = 𝐈
    # (the bare default scheme is all-interval, which auto-replaces the list with the identity).
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), "TILT minimax-S")
    assert pt[("vectors", "targets")].startswith("[[1 0 0⟩ [0 1 0⟩ [-1 1 0⟩")  # target vectors
    assert ("vectors", "primes") not in pt  # the domain-basis identity is deferred to identity_objects


def test_plain_text_mapped_list_is_a_list_of_generator_coord_vectors():
    # each target mapped into generator coords becomes one [ … } vector (the } marks generator
    # coordinates), the whole set wrapped in an outer [ … ]. A target-based scheme so the targets
    # are the TILT set (the bare default is all-interval, which collapses the list to Tₚ = 𝐈).
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), "TILT minimax-S")
    assert pt[("mapping", "targets")] == (
        "[[1 0} [1 1} [0 1} [1 -1} [-1 4} [-1 3} [-2 4} [2 -3}]"
    )


def test_plain_text_tuning_rows_use_map_and_list_brackets_at_grid_precision():
    # a target-based scheme throughout (the bare default is all-interval, whose target list is
    # Tₚ = 𝐈, not the TILT set): the plain text and the comparison tuning/sizes use the same scheme.
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state, "TILT minimax-S")
    targets = service.target_interval_set("TILT", service.standard_primes(state.d))
    tun = service.tuning(state.mapping, "TILT minimax-S")
    sizes = service.interval_sizes(tun, targets)

    def cents(vals):  # the same 3-dp the grid shows, so the two views agree
        return " ".join(f"{v:.3f}" for v in vals)

    # tuning / just / retuning maps over the primes are covectors: ⟨ … ]
    assert pt[("tuning", "primes")] == f"⟨{cents(tun.tuning_map)}]"
    assert pt[("just", "primes")] == f"⟨{cents(tun.just_map)}]"
    assert pt[("retune", "primes")] == f"⟨{cents(tun.retuning_map)}]"
    # the size / error / damage lists over the targets are plain lists: [ … ]
    assert pt[("tuning", "targets")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "targets")] == f"[{cents(sizes.just)}]"
    assert pt[("retune", "targets")] == f"[{cents(sizes.errors)}]"
    assert pt[("damage", "targets")] == f"[{cents(sizes.damage)}]"
    assert pt[("just", "primes")].startswith("⟨1200.000 ")  # the just octave is pure


def test_plain_text_generator_tuning_map_uses_curly_open_square_close():
    # the generator tuning map reads { … ] (curly open, square close) per the mockup —
    # distinct from the prime maps' ⟨ … ] — at the same 3-dp the grid shows
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state)
    tun = service.tuning(state.mapping)
    cents = " ".join(f"{v:.3f}" for v in tun.generator_map)
    assert pt[("tuning", "gens")] == "{" + cents + "]"


def test_plain_text_commas_column_mirrors_the_grid():
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state)
    commas = service.comma_ratios(state.comma_basis)
    sizes = service.interval_sizes(service.tuning(state.mapping), commas)

    def cents(vals):
        return " ".join(f"{v:.3f}" for v in vals)

    # the comma basis (the editable vector matrix) lives in the interval-vectors row,
    # a list of vectors wrapped in an outer [ … ]
    assert pt[("vectors", "commas")] == "[[4 -4 1⟩]"
    # the mapping row's commas tile is the mapped comma basis — every comma vanishes,
    # shown in generator coords (close })
    assert pt[("mapping", "commas")] == "[[0 0}]"
    # comma sizes are lists over the commas, like the grid's column
    assert pt[("tuning", "commas")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "commas")] == f"[{cents(sizes.just)}]"


def test_plain_text_held_column_mirrors_the_grid():
    # the held interval column gets plain text like the comma column, with the tuning
    # computed under the held-just constraint so the two views agree
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    held = [(-1, 1, 0)]  # the fifth 3/2, held exactly just
    pt = service.plain_text_values(state, held=held)
    held_ratios = service.comma_ratios(held)
    tun = service.tuning(state.mapping, held=held_ratios)
    sizes = service.interval_sizes(tun, held_ratios)

    def cents(vals):
        return " ".join(f"{v:.3f}" for v in vals)

    # the held interval basis lives in the interval-vectors row (vectors, close ⟩)
    assert pt[("vectors", "held")] == "[[-1 1 0⟩]"
    # mapped into generator coords (close }) — the fifth is one generator
    assert pt[("mapping", "held")] == "[[0 1}]"
    # the held sizes are lists over the held intervals, matching the held-constrained grid
    assert pt[("tuning", "held")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "held")] == f"[{cents(sizes.just)}]"
    assert pt[("retune", "held")] == f"[{cents(sizes.errors)}]"
    assert abs(float(pt[("retune", "held")].strip("[]"))) < 1e-3  # held just ⇒ no error
    # the prescaling row over the held basis: 𝐿 applied to each held vector (like the comma
    # column's 𝐿·C). The fifth 3/2 = [-1, 1, 0] prescaled by log-prime 𝐿 = [-1, 1.585, 0].
    # The 𝐿·basis products (𝐿H here, 𝐿C / 𝐿D / 𝐿T elsewhere) are matrices of prescaled
    # VECTORS, so each column is a ket ``[ … ⟩`` inside the symmetric outer ``[ … ]``. (The
    # bare prescaler 𝐿 is the exception — covector rows ``⟨ … ]`` inside outer ``[ … ⟩``.)
    assert pt[("prescaling", "held")] == "[[-1 1.585 0⟩]"
    # no held entries when none are held
    assert ("vectors", "held") not in service.plain_text_values(state)
    assert ("prescaling", "held") not in service.plain_text_values(state)


def test_plain_text_interest_column_is_standalone_kets_not_a_matrix():
    # the other-intervals-of-interest column is a loose collection, not a basis/matrix:
    # each interval stands alone as its own ket, space-separated, with NO outer [ … ]
    # wrapping (unlike the comma basis, target list and held basis, which are matrices).
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    interest = [(-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1)]  # 3/2, 9/8, 10/9, 8/5
    pt = service.plain_text_values(state, interest=interest)
    interest_ratios = service.comma_ratios(interest)
    tun = service.tuning(state.mapping)
    sizes = service.interval_sizes(tun, interest_ratios)

    def cents(vals):
        return " ".join(f"{v:.3f}" for v in vals)

    # interval vectors: standalone kets (close ⟩), space-separated, no outer wrapping
    assert pt[("vectors", "interest")] == "[-1 1 0⟩ [-3 2 0⟩ [1 -2 1⟩ [3 0 -1⟩"
    # mapped into generator coords (close }), again standalone — not a bracketed matrix
    assert pt[("mapping", "interest")] == "[0 1} [-1 2} [-1 2} [3 -4}"
    # the size rows are bare numbers — the whole interest column drops the enclosing [ … ]
    assert pt[("tuning", "interest")] == cents(sizes.tempered)
    assert pt[("just", "interest")] == cents(sizes.just)
    assert pt[("retune", "interest")] == cents(sizes.errors)
    assert "[" not in pt[("complexity", "interest")] and "]" not in pt[("complexity", "interest")]
    # prescaling/interest is standalone vectors (no outer wrap), like the interval-vectors
    # row's standalone kets — each prescaled vector its own ket ``[ … ⟩`` (square open +
    # angle close), space-separated, with no surrounding bracket. Same per-vector shape as
    # the 𝐿·basis product tiles, just stripped of the outer wrap (the interest pattern).
    assert pt[("prescaling", "interest")].startswith("[") and pt[("prescaling", "interest")].endswith("⟩")
    assert not pt[("prescaling", "interest")].endswith("⟩]")  # no outer wrap
    # no interest entries when the column is empty
    assert ("vectors", "interest") not in service.plain_text_values(state)


def test_plain_text_weighting_rows_mirror_the_grid():
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state)
    # complexity: a covector ⟨ … ] over the primes (their log-prime complexities), a
    # list [ … ] over the commas (the comma's complexity is its prescaled vector's norm)
    assert pt[("complexity", "primes")] == "⟨1.000 1.585 2.322]"
    assert pt[("complexity", "commas")] == "[12.662]"
    assert pt[("complexity", "targets")].startswith("[") and pt[("complexity", "targets")].endswith("]")
    # the per-target weight list (the canonical minimax-S is simplicity-weighted → 1/complexity)
    assert pt[("weight", "targets")].startswith("[") and pt[("weight", "targets")].endswith("]")
    # the prescaling row is 𝐿 applied to each vector set, a […⟩-per-vector matrix:
    # 𝐿·[4,-4,1] = [4,-6.34,2.322] — each prescaled vector a ket ``[ … ⟩`` (square open +
    # angle close), wrapped in outer [ … ] like the mockup's 𝐿C tile. The string shows the
    # SAME numbers as the grid — whole numbers bare (4, not 4.000)
    assert pt[("prescaling", "commas")] == "[[4 -6.340 2.322⟩]"


def test_plain_text_lils_prescaler_grows_the_size_row_matching_the_grid():
    # with the size factor on (lils), the complexity pretransformer is the rectangular 𝑋 = 𝑍𝐿.
    # The plain text grows to match the grid: the bare prescaler gains one covector ROW (the
    # size-sensitizing sf·𝐋), and each 𝑋·basis product COLUMN gains the size component sf·Σ(𝐿ⱼ·vⱼ).
    mapping = [[1, 1, 0], [0, 1, 4]]
    _t = service.prescale_text
    pre = service.complexity_prescaler(mapping, "TILT minimax-S")  # the square (lp) diagonal
    pt = service.plain_text_values(service.from_mapping(mapping), scheme="TILT minimax-lils-S")
    # bare 𝑋: three diagonal covector rows, then the size row ⟨sf·𝐿₀ sf·𝐿₁ sf·𝐿₂] (sf = 1)
    rows = [["0", "0", "0"] for _ in range(3)]
    for i in range(3):
        rows[i][i] = _t(pre[i])
    rows.append([_t(pre[c]) for c in range(3)])
    assert pt[("prescaling", "primes")] == "[" + " ".join("⟨" + " ".join(r) + "]" for r in rows) + "⟩"
    # the 𝑋C product column grows the size component sf·Σ(𝐿ⱼ·commaⱼ) as its 4th ket entry
    comma = service.from_mapping(mapping).comma_basis[0]
    col = [pre[i] * comma[i] for i in range(3)]
    col.append(sum(col))  # sf = 1
    assert pt[("prescaling", "commas")] == "[[" + " ".join(_t(x) for x in col) + "⟩]"


def test_plain_text_all_interval_lils_weight_is_the_matrix_not_the_list():
    # all-interval lils: the weight plain text matches the grid — a covector-row matrix 𝑊 = (𝑍𝐿)⁻,
    # not the per-prime list (which is blind to the size factor).
    mapping = [[1, 1, 0], [0, 1, 4]]
    W = service.damage_weight_matrix(mapping, "minimax-lils-S")
    pt = service.plain_text_values(service.from_mapping(mapping), scheme="minimax-lils-S")
    expected = "[" + " ".join("⟨" + " ".join(service.cents(x) for x in row) + "]" for row in W) + "]"
    assert pt[("weight", "targets")] == expected
    # the square (lp) all-interval weight stays a flat per-prime list — no covector rows
    pt_lp = service.plain_text_values(service.from_mapping(mapping), scheme="minimax-S")
    assert "⟨" not in pt_lp[("weight", "targets")]


def test_plain_text_over_a_nonstandard_domain_uses_the_basis():
    # the plain-text view of a 2.3.13/5 temperament names the domain basis in dot
    # notation and tunes over its elements (not the standard primes)
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state)
    assert pt[("quantities", "primes")] == "2.3.13/5"
    assert pt[("vectors", "commas")] == "[[2 -3 2⟩]"  # the comma vector, basis-relative
    tun = service.tuning(state.mapping, domain_basis=state.domain_basis)
    cents = " ".join(f"{v:.3f}" for v in tun.tuning_map)
    assert pt[("tuning", "primes")] == f"⟨{cents}]"


def test_vector_list_pending_text_splits_the_draft_for_two_tone_display():
    # while an interval is being added the editable vector-list string (comma basis / target
    # list) is shown two-tone: the committed vectors (and the wrapping brackets) stay black, the
    # draft vector reddens. The helper returns (black prefix, red draft ket, black suffix); the
    # draft shows the entered components only (blanks omitted), e.g. (4, _, 1) -> "[4 1⟩".
    prefix, draft, suffix = service.vector_list_pending_text(((4, -4, 1),), [4, None, 1])
    assert (prefix, draft, suffix) == ("[[4 -4 1⟩ ", "[4 1⟩", "]")
    assert prefix + draft + suffix == "[[4 -4 1⟩ [4 1⟩]"  # the full string, reassembled
    # a brand-new (all-blank) draft is just an empty ket
    assert service.vector_list_pending_text(((4, -4, 1),), [None, None, None])[1] == "[⟩"
    # a second committed vector extends the black prefix; the draft is still its own ket
    assert service.vector_list_pending_text(((4, -4, 1), (4, -5, 1)), [None, None, None])[0] == "[[4 -4 1⟩ [4 -5 1⟩ "


def test_parse_mapping_reads_an_ebk_map_string():
    assert service.parse_mapping("[⟨1 1 0] ⟨0 1 4]}") == ((1, 1, 0), (0, 1, 4))
    assert service.parse_mapping("⟨12 19 28]") == ((12, 19, 28),)  # a single map
    # round-trips the mapping plain text
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert service.parse_mapping(pt[("mapping", "primes")]) == ((1, 1, 0), (0, 1, 4))


def test_parse_comma_basis_reads_an_ebk_vector_string():
    assert service.parse_comma_basis("[4 -4 1⟩") == ((4, -4, 1),)
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert service.parse_comma_basis(pt[("vectors", "commas")]) == ((4, -4, 1),)


def test_parse_rejects_unparseable_wrong_variance_or_non_integer():
    assert service.parse_mapping("garbage") is None
    assert service.parse_mapping("") is None
    assert service.parse_mapping("[1 0 0⟩") is None  # a vector, not a map
    assert service.parse_mapping("⟨1 1.5 0]") is None  # a non-integer entry
    assert service.parse_comma_basis("⟨1 0 0]") is None  # a map, not a vector
    assert service.parse_comma_basis("nonsense") is None


def test_parse_cents_map_reads_a_genmap_or_tuning_string():
    # the generator tuning map ({ … ]) and a prime tuning map (⟨ … ]), float-tolerant
    assert service.parse_cents_map("{1201.699 697.564]") == (1201.699, 697.564)
    assert service.parse_cents_map("⟨1200.000 1901.955 2786.314]") == (1200.0, 1901.955, 2786.314)
    # round-trips the genmap plain text it inverts (to the 3-dp the string carries)
    st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    gm = service.tuning(st.mapping).generator_map
    parsed = service.parse_cents_map(service.plain_text_values(st)[("tuning", "gens")])
    assert parsed == tuple(round(g, 3) for g in gm)
    # an optional length check, so a caller can demand exactly r generators
    assert service.parse_cents_map("{1200 700]", 2) == (1200.0, 700.0)
    assert service.parse_cents_map("{1200 700]", 3) is None
    # junk / non-numeric / empty -> None
    assert service.parse_cents_map("garbage") is None
    assert service.parse_cents_map("{1200 x]") is None
    assert service.parse_cents_map("") is None


def test_parse_prescaler_diagonal_reads_the_matrix_form_and_extracts_the_diagonal():
    # the bare prescaler 𝐿's plain text shows the FULL d×d matrix ([⟨…] ⟨…] ⟨…]⟩) even
    # though 𝐿 is diagonal — the off-diagonal cells are pinned 0. The parser inverts that
    # display: it reads the matrix, verifies the off-diagonal is all zero (else 𝐿 wouldn't
    # be diagonal — reject as malformed), and returns the diagonal as a d-tuple of floats.
    assert service.parse_prescaler_diagonal(
        "[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩", 3) == (1.0, 1.585, 2.322)
    # round-trips the live plain text the bare prescaler tile renders
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert service.parse_prescaler_diagonal(pt[("prescaling", "primes")], 3) == (1.0, 1.585, 2.322)
    # a hand-typed override: change the prime-3 slot to 4 (the diagonal becomes 1, 4, 2.322)
    assert service.parse_prescaler_diagonal(
        "[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩", 3) == (1.0, 4.0, 2.322)


def test_parse_prescaler_diagonal_rejects_unparseable_or_non_diagonal_or_wrong_size():
    # rejects: unparseable, the wrong matrix size, a non-zero off-diagonal (𝐿 is diagonal),
    # a vector (col variance) instead of a matrix of covectors, or empty input. None lets
    # the caller flag the input without mangling the override.
    assert service.parse_prescaler_diagonal("garbage", 3) is None
    assert service.parse_prescaler_diagonal("", 3) is None
    # a 2x2 matrix when d == 3 (the wrong size)
    assert service.parse_prescaler_diagonal("[⟨1 0] ⟨0 2]⟩", 3) is None
    # a nonzero off-diagonal: 𝐿 is diagonal, so a 0.5 outside the diagonal is malformed
    assert service.parse_prescaler_diagonal("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩", 3) is None
    # a covector list rather than a covector matrix (one ⟨…] only) — wrong shape for the
    # bare prescaler tile, even if the d numbers parse as floats
    assert service.parse_prescaler_diagonal("⟨1 1.585 2.322]", 3) is None


def test_parse_prescaler_diagonal_accepts_the_optional_size_row():
    # with the size factor on, the bare prescaler is the rectangular 𝑋 = 𝑍𝐿 — (d+1)×d: the d
    # diagonal rows plus the derived size-sensitizing row sf·𝐋. The parser reads the diagonal
    # from the first d rows and ignores the size row (it is recomputed, never user-set).
    assert service.parse_prescaler_diagonal(
        "[⟨1 0 0] ⟨0 1.585 0] ⟨0 0 2.322] ⟨1 1.585 2.322]⟩", 3) == (1.0, 1.585, 2.322)
    # round-trips the live lils plain text the bare prescaler tile renders
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), scheme="TILT minimax-lils-S")
    assert service.parse_prescaler_diagonal(pt[("prescaling", "primes")], 3) == (1.0, 1.585, 2.322)
    # a hand-edited diagonal still parses with the size row present (whatever it holds is ignored)
    assert service.parse_prescaler_diagonal(
        "[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322] ⟨9 9 9]⟩", 3) == (1.0, 4.0, 2.322)


def test_plain_text_targets_honor_an_override():
    st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    # a target-based scheme: an override curates the target list, which only applies when the
    # scheme is target-based (all-interval auto-replaces the list with Tₚ = 𝐈, overriding the override).
    pt = service.plain_text_values(st, "TILT minimax-S", target_override=("2/1", "3/2"))
    # the target columns reflect exactly the two overridden intervals across the value rows
    assert pt[("vectors", "targets")] == "[[1 0 0⟩ [-1 1 0⟩]"
    assert pt[("tuning", "targets")].count(".") == 2  # two cents values, one per overridden target


def test_tuning_exposes_diamond_generator_ranges():
    import pytest

    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    # Octave held pure pins the period generator; the fifth gets a real range.
    assert t.tradeoff_generator_range[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)
    assert t.tradeoff_generator_range[1] == pytest.approx((694.786, 701.955), abs=1e-2)
    assert t.monotone_generator_range[1] == pytest.approx((685.714, 720.0), abs=1e-2)


def test_domain_has_nonprimes_flags_any_nonprime_element():
    # The mode-radio (prime-based / nonprime-based / neutral) only matters when the domain
    # has nonprime elements: a reordering of primes still has the prime-only structure, so
    # this is a finer test than `is_standard_domain` (which is True only for canonical-order
    # prime limits). BARBADOS over 2.3.13/5 has the nonprime 13/5; 2.9.5 has the composite 9.
    assert service.domain_has_nonprimes((2, 3, 5)) is False  # standard primes
    assert service.domain_has_nonprimes((3, 2, 5)) is False  # reordered primes, still all prime
    assert service.domain_has_nonprimes((2, 3, Fraction(13, 5))) is True  # 13/5 has a denominator
    assert service.domain_has_nonprimes((2, 9, 5)) is True  # 9 = 3² is composite


def test_superspace_primes_collects_every_prime_appearing_in_the_basis():
    # The superspace is the smallest prime-only basis containing all the domain's primes —
    # the rail the prime-based optimization runs over and the column header (α β γ δ ε …) of
    # the nonstandard-domain superspace region. BARBADOS over 2.3.13/5 collects 2,3,5,13.
    assert service.superspace_primes((2, 3, 5)) == (2, 3, 5)  # already prime-only: passes through
    assert service.superspace_primes((3, 2, 5)) == (2, 3, 5)  # reordered, sorted on the way out
    assert service.superspace_primes((2, 3, Fraction(13, 5))) == (2, 3, 5, 13)  # BARBADOS
    assert service.superspace_primes((2, 9, 5)) == (2, 3, 5)  # 9 = 3² contributes prime 3


def test_superspace_dimension_is_the_count_of_superspace_primes():
    # dL = len(superspace_primes); for BARBADOS d=3 grows to dL=4 (the extra prime 13).
    assert service.superspace_dimension((2, 3, 5)) == 3
    assert service.superspace_dimension((2, 3, Fraction(13, 5))) == 4  # +13
    assert service.superspace_dimension((2, 9, 5)) == 3  # collapses to {2,3,5}


def test_basis_in_superspace_writes_each_element_as_a_monzo_over_the_superspace_primes():
    # Convention (chosen rows-as-elements, matching the comma-basis / target-vector storage in
    # this service): each ROW is one domain element written as a monzo over the superspace
    # primes — d rows of length dL. For BARBADOS over 2.3.13/5 with superspace (2,3,5,13):
    # 2 → ⟨1 0 0 0], 3 → ⟨0 1 0 0], 13/5 → ⟨0 0 -1 1].
    barbados = service.basis_in_superspace((2, 3, Fraction(13, 5)))
    assert barbados == ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
    # a standard prime basis is the identity over itself (each element is one prime, one slot)
    assert service.basis_in_superspace((2, 3, 5)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    # composites factor: 9 = 3² → (0, 2, 0) over (2, 3, 5)
    assert service.basis_in_superspace((2, 9, 5)) == ((1, 0, 0), (0, 2, 0), (0, 0, 1))


def test_superspace_mapping_re_expresses_the_temperament_over_the_superspace_primes():
    # M_L is the temperament's mapping re-expressed over the simplest prime-only basis: rL × dL,
    # integer, full row rank, tempering out every comma the original tempered. For BARBADOS
    # over 2.3.13/5 with comma (2,-3,2) → 676/675 (= 2² · 13² / (3³ · 5²) over (2,3,5,13)
    # = (2,-3,-2,2)), M_L is a 3×4 integer matrix that tempers out (2,-3,-2,2).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    ml = service.superspace_mapping(state)
    assert len(ml) == 3 and all(len(row) == 4 for row in ml)  # rL × dL = 3 × 4
    assert all(isinstance(x, int) for row in ml for x in row)  # integer entries
    embedded_comma = (2, -3, -2, 2)  # 676/675 over (2, 3, 5, 13)
    for row in ml:
        assert sum(a * b for a, b in zip(row, embedded_comma)) == 0  # tempers out the comma


def test_superspace_mapping_returns_the_canonical_mapping_when_already_prime_only():
    # over a standard prime basis the superspace IS the domain, so the embedding is a no-op:
    # M_L equals the canonical form of M itself — no extra rows, no new primes to lift.
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])  # 5-limit meantone
    assert service.superspace_mapping(state) == service.canonical_mapping(state.mapping)


def test_superspace_rank_is_r_plus_the_extra_primes():
    # rL = r + (dL − d): nullity is preserved by the embedding, so each new prime above the
    # original basis contributes one extra generator. BARBADOS: r=2, d=3, dL=4 → rL=3. A
    # standard-prime temperament's rL equals its own r (no extra primes).
    barbados = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.superspace_rank(barbados) == 3
    meantone = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    assert service.superspace_rank(meantone) == 2


def test_superspace_just_mapping_is_the_dL_identity():
    # M_jL = I_dL: in the superspace each prime IS a basis element, so the just mapping is
    # the identity. Exposed as a named function so the layout can render it uniformly
    # alongside the other superspace matrices. dL=4 for BARBADOS.
    assert service.superspace_just_mapping((2, 3, 5, 13)) == (
        (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)
    )
    assert service.superspace_just_mapping((2, 3, 5)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_superspace_tuning_runs_over_the_superspace_primes():
    import pytest

    # BARBADOS over 2.3.13/5 lifts into a 3×4 mapping over (2, 3, 5, 13). The just map over
    # the superspace is the size of each prime; the tuning has rL=3 generators and dL=4
    # prime sizes. retuning_map = tempered - just (component-wise).
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    tun = service.superspace_tuning(state, "minimax-S")
    assert len(tun.generator_map) == 3  # rL
    assert len(tun.tuning_map) == 4 and len(tun.just_map) == 4  # dL
    assert tun.just_map == pytest.approx(
        (1200.0, 1200.0 * math.log2(3), 1200.0 * math.log2(5), 1200.0 * math.log2(13)), abs=1e-6
    )
    assert tun.retuning_map == pytest.approx(
        tuple(t - j for t, j in zip(tun.tuning_map, tun.just_map)), abs=1e-9
    )
