import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings


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
    # scheme, so p = ∞; miniRMS is p = 2; miniaverage is p = 1.
    assert service.optimization_power("minimax-S") == math.inf
    assert service.optimization_power() == math.inf  # defaults to the canonical scheme (minimax-S)
    assert service.optimization_power("miniRMS-U") == 2
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


def test_from_temperament_data_reads_a_comma_basis_too():
    # a contravariant (ket / comma-basis) input is routed through from_comma_basis, not the
    # mapping path: meantone's 81/80 comma reconstructs the same rank-2 5-limit temperament
    state = service.from_temperament_data("[-4 4 -1⟩")
    assert (state.d, state.r, state.n) == (3, 2, 1)
    assert state.comma_basis == ((-4, 4, -1),)


def test_shrink_domain_falls_back_to_just_intonation_when_no_comma_survives():
    from rtt.app.service.state import from_comma_basis, shrink_domain

    # the lone comma lives entirely in the top prime, so dropping that domain coordinate leaves
    # nothing independent to temper — the shrunk domain is plain JI over the remaining primes.
    shrunk = shrink_domain(from_comma_basis(((0, 0, 1),)))
    assert (shrunk.d, shrunk.n) == (2, 0)


def test_is_independent_domain_basis_rejects_the_empty_basis():
    assert service.is_independent_domain_basis(()) is False


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
    assert state.comma_basis == ((-4, 4, -1),)  # a clean round-trip leaves the comma untouched
    assert state.mapping == ((1, 0, -4), (0, 1, 4))
    assert (state.d, state.r, state.n) == (3, 2, 1)


def test_shrinking_keeps_the_comma_count_equal_to_the_nullity():
    # trimming a prime can collapse independent commas to dependent ones over the smaller domain;
    # shrink must then drop the now-redundant rows so the basis carries exactly n commas — otherwise
    # the state holds more comma vectors than the nullity (d ≠ r + n) and the grid shows phantom
    # comma columns. 12-ET (n=2) shrunk twice reaches a single prime, where the nullity is 1.
    twelve = service.from_mapping(((12, 19, 28),))  # d=3 r=1 n=2, two commas
    one = service.shrink_domain(service.shrink_domain(twelve))  # -> d=1
    assert (one.d, one.r, one.n) == (1, 0, 1) and one.d == one.r + one.n
    assert len(one.comma_basis) == one.n == 1  # one comma, not the two it would naively keep


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


def test_remove_comma_un_tempers_the_sole_comma_to_just_intonation():
    # removing the LAST comma un-tempers everything — just intonation over the domain (the identity
    # mapping, every prime its own generator), nullity 0. Dualizing an empty comma basis can't
    # recover d, so it builds the identity directly; the result matches reaching n=0 the mapping way.
    meantone = service.from_comma_basis(((4, -4, 1),))  # d=3, n=1
    ji = service.remove_comma(meantone)
    assert (ji.d, ji.r, ji.n) == (3, 3, 0)  # full rank: nothing tempered
    assert ji.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))  # JI over 2.3.5
    assert ji.comma_basis == ((0, 0, 0),)  # the nullity-0 placeholder (the full-rank dual)


def test_un_tempering_the_last_comma_keeps_a_nonstandard_domain():
    # un-tempering the sole comma builds the identity over the DOMAIN — it must keep a nonstandard
    # subgroup (2.3.7), not silently revert to the standard 2.3.5. And the mapping + is the same
    # primitive, so it reaches an identical state.
    archytas = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))  # n=1
    ji = service.remove_comma(archytas)
    assert ji.domain_basis == (2, 3, 7)  # the subgroup survives
    assert (ji.d, ji.r, ji.n) == (3, 3, 0) and ji.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert service.add_mapping_row(archytas) == ji  # the mapping + IS removing the last comma


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
    # scheme optimum) — what a manual generator-tuning override produces. For
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


def test_equave_quotient_is_the_first_basis_element():
    assert service.equave_quotient() == Fraction(2)              # standard prime limit
    assert service.equave_quotient((2, 3, 5)) == Fraction(2)
    assert service.equave_quotient((3, 5, 7)) == Fraction(3)     # a tritave-equave subgroup
    assert service.equave_quotient((2, 3, Fraction(13, 5))) == Fraction(2)


def test_equave_reduce_vector_folds_only_the_equave_coordinate():
    assert service.equave_reduce_vector((-2, 2, 0)) == (-3, 2, 0)   # 9/4 -> 9/8
    assert service.equave_reduce_vector((-2, 0, 1)) == (-2, 0, 1)   # 5/4 already reduced, unchanged
    assert service.equave_reduce_vector((0, 0, 1)) == (-2, 0, 1)    # 5/1 -> 5/4
    assert service.equave_reduce_vector((1, 0, 0)) == (0, 0, 0)     # the octave -> the unison


def test_equave_reduce_vector_over_a_nonstandard_domain():
    # 2.3.13/5: the equave is still 2, so folding the lifted 13/5 keeps it in [1, 2)
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    octave = service.interval_vector("2/1", state.d, state.domain_basis)
    assert service.equave_reduce_vector(octave, state.domain_basis) == (0, 0, 0)


def test_interval_op_availability_gates_the_two_buttons():
    # (can_reduce, can_reciprocate): reduce only when outside [1, equave), reciprocate only off 1/1
    assert service.interval_op_availability("9/4") == (True, True)   # a major ninth: both apply
    assert service.interval_op_availability("5/4") == (False, True)  # already reduced, still flippable
    assert service.interval_op_availability("2") == (True, True)     # the octave reduces to a unison
    assert service.interval_op_availability("1") == (False, False)   # a unison: neither op does anything
    assert service.interval_op_availability("?/?") == (False, False) # a blank draft: neither
    assert service.interval_op_availability("") == (False, False)
    # a tritave-equave subgroup widens the reduce window: 5/2 is still inside [1, 3)
    assert service.interval_op_availability("5/2", (3, 5, 7)) == (False, True)


def test_transform_ratio_reduces_or_reciprocates_a_ratio_string():
    # the ratio-string form used to relabel a domain basis element through set_domain_element
    assert service.transform_ratio("13/5", "reduce", (2, 3, Fraction(13, 5))) == "13/10"
    assert service.transform_ratio("13/5", "reciprocate") == "5/13"
    assert service.transform_ratio("9/4", "reduce") == "9/8"
    assert service.transform_ratio("2", "reduce") == "1"            # the equave folds to a bare integer
    assert service.transform_ratio("5/4", "reduce") is None         # already reduced — a no-op
    assert service.transform_ratio("1", "reciprocate") is None      # a unison — a no-op
    assert service.transform_ratio("?/?", "reduce") is None         # a blank draft


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
    assert service.target_limit_problem("OLD", 8.0) == "odd"    # ...as a float too
    assert service.target_limit_problem("OLD", 9) is None       # odd odd-limit -> fine
    assert service.target_limit_problem("TILT", 8) is None      # even is fine for the triangle
    assert service.target_limit_problem("TILT", 9.5) == "whole" # a decimal isn't a whole number
    assert service.target_limit_problem("OLD", "abc") == "whole"  # unparseable text
    assert service.target_limit_problem("OLD", None) is None    # blank -> the domain default
    assert service.target_limit_problem("OLD", "") is None      # blank -> the domain default
    assert service.target_limit_problem("OLD", 0) is None       # zero reads as blank (matches the chooser)
    assert service.target_limit_problem(None, 8) is None        # no named family -> no parity rule
    # the chooser's limit is a TEXT field, so the entry arrives as a string: validate those too
    assert service.target_limit_problem("OLD", "8") == "odd"
    assert service.target_limit_problem("OLD", "9") is None
    assert service.target_limit_problem("TILT", "8.5") == "whole"


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
    # approaches give different optimal generators. Neutral is (1191.880, 133.594): it
    # prime-factors complexity, so the 3 shared by 7/3 and 11/3 cancels in targets like
    # 11/7 (see test_tuning_nonstandard for the mechanism). The historical tests.m 3733-3762
    # reference (1194.291, 135.186) measured that complexity in the nonprime basis-vector
    # form, double-counting the shared 3 — corrected here.
    state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    neutral = service.tuning(state.mapping, "TILT minimax-C", domain_basis=state.domain_basis)
    nonprime = service.tuning(
        state.mapping, "TILT minimax-C", domain_basis=state.domain_basis,
        nonprime_approach="nonprime-based",
    )
    assert neutral.generator_map == pytest.approx((1191.880, 133.594), abs=1e-2)
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


def test_interval_sizes_weights_scale_damage_into_the_scheme_weighted_form():
    # 𝐝 = |𝐞|·W: passing the scheme's damage weights turns the plain |error| damage row
    # into the weighted quantity the optimizer minimizes and the ¢(C) unit labels. Meantone
    # under quarter-comma (the unity minimax tuning) with complexity weights reproduces the
    # guide's per-target damages — e.g. 3/2 → 13.90, 4/3 → 19.28, 6/5 → 26.39, not 5.377.
    import pytest

    state = service.from_mapping([[1, 0, -4], [0, 1, 4]])
    tun = service.tuning(state.mapping, "TILT minimax-U")  # quarter-comma meantone, pure octave
    targets = service.displayed_targets(state, "TILT minimax-C")
    weights = service.interval_weights(state.mapping, "TILT minimax-C", targets)
    s = service.interval_sizes(tun, targets, weights=weights)
    by_ratio = dict(zip(targets, s.damage))
    assert by_ratio["3/2"] == pytest.approx(13.898, abs=1e-2)
    assert by_ratio["4/3"] == pytest.approx(19.275, abs=1e-2)
    assert by_ratio["6/5"] == pytest.approx(26.382, abs=1e-2)
    # unity weight leaves the damage as plain |error| (the default, weights=None)
    unweighted = service.interval_sizes(tun, targets)
    assert unweighted.damage == pytest.approx(tuple(abs(e) for e in s.errors), abs=1e-9)


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


def test_cents_drops_negative_zero():
    # negative zero carries no meaning, so a value that shows as zero never wears a minus sign
    assert service.cents(-0.0) == "0.000"
    assert service.cents(-0.0004) == "0.000"  # rounds to zero at 3-dp → unsigned
    assert service.cents(-0.0006) == "-0.001"  # a real nonzero residual keeps its sign
    assert service.cents(0.0) == "0.000"
    assert service.cents(None) == "—"


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


def test_weight_annotation_codes_the_complexity_slope_and_euclideanization():
    # the damage/weight annotated-unit code (guide ch.10 "Annotated units"): the weight-slope
    # letter — U (unity), C (complexity), S (simplicity) — gaining an E prefix at a Euclidean
    # (q=2) norm and the alternative-complexity family name when it isn't the log-product default.
    # Damage renders ¢(<code>), the weight (<code>).
    assert service.weight_annotation("minimax-U") == "U"
    assert service.weight_annotation("minimax-C") == "C"
    assert service.weight_annotation("minimax-S") == "S"
    assert service.weight_annotation("minimax-EC") == "EC"
    assert service.weight_annotation("minimax-ES") == "ES"
    # a named alternative complexity slots its family in — E prefixes the family, not the slope
    assert service.weight_annotation("minimax-sopfr-S") == "sopfr-S"
    assert service.weight_annotation("minimax-E-sopfr-S") == "E-sopfr-S"
    assert service.weight_annotation("minimax-copfr-C") == "copfr-C"
    assert service.weight_annotation("minimax-lils-S") == "lils-S"
    assert service.weight_annotation("minimax-lols-S") == "lols-S"
    # unity weight applies no complexity — always just "U", even with sopfr traits at q=2
    assert service.weight_annotation(service.scheme_with_weight_slope("minimax-E-sopfr-S", "unity-weight")) == "U"


def test_complexity_annotation_codes_the_family_and_euclideanization():
    # the complexity quantity carries no weight slope (always "complexity", letter C); only the
    # family and Euclideanization vary it — C / EC for the log-product default, sopfr-C / E-sopfr-C
    # for a named family. Independent of the weight slope (sopfr-S still has an sopfr-C complexity).
    assert service.complexity_annotation("minimax-S") == "C"     # log-product, taxicab
    assert service.complexity_annotation("minimax-ES") == "EC"   # log-product, Euclidean
    assert service.complexity_annotation("minimax-sopfr-S") == "sopfr-C"
    assert service.complexity_annotation("minimax-E-sopfr-S") == "E-sopfr-C"
    assert service.complexity_annotation("minimax-copfr-C") == "copfr-C"
    assert service.complexity_annotation("minimax-lils-S") == "lils-C"
    assert service.complexity_annotation("minimax-lols-S") == "lols-C"


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


def test_scheme_with_complexity_held_octave_handling():
    # lols (log-odd-limit) is lils plus a held octave (trait 0); selecting it tunes 2/1 just
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols")) == ("2/1",)
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lols-E")) == ("2/1",)
    # lils does NOT hold the octave
    assert service.held_intervals(service.scheme_with_complexity("minimax-S", "lils")) == ()
    # a SCHEME-level held octave (held-octave minimax-ES) SURVIVES a complexity swap, just as the
    # destretched-octave modifier does: held-octave minimax-ES + sopfr -> held-octave minimax-sopfr-S
    # (all-interval-alt-complexity-8 / presets-sweep-3).
    swapped = service.scheme_with_complexity("held-octave minimax-ES", "sopfr")
    assert service.held_intervals(swapped) == ("2/1",)
    assert service.base_scheme_name(swapped) == "held-octave minimax-sopfr-S"
    # but a held octave that was the OLD complexity's OWN internal fold (lols/ols) is cleared when
    # swapping to a non-held complexity — that octave belonged to the complexity, not the scheme.
    assert service.held_intervals(service.scheme_with_complexity("minimax-lols-S", "lp")) == ()


def test_complexity_name_of_reports_the_named_complexity_else_custom():
    assert service.complexity_name_of("minimax-S") == "lp"    # the default (log-prime taxicab)
    assert service.complexity_name_of("minimax-ES") == "lp-E"  # E-lp
    assert service.complexity_name_of("minimax-copfr-S") == "copfr"
    assert service.complexity_name_of("minimax-sopfr-S") == "sopfr"
    assert service.complexity_name_of("minimax-lils-S") == "lils"
    assert service.complexity_name_of("minimax-lols-S") == "lols"  # lils + held octave
    # it round-trips with scheme_with_complexity
    assert service.complexity_name_of(service.scheme_with_complexity("minimax-S", "sopfr-E")) == "sopfr-E"
    # a SCHEME-level held octave is a scheme modifier, NOT part of the complexity identity, so it
    # must not push the chooser to "custom": held-octave minimax-ES still names its complexity lp-E,
    # held-octave minimax-S still names lp (all-interval-alt-complexity-7).
    assert service.complexity_name_of("held-octave minimax-ES") == "lp-E"
    assert service.complexity_name_of("held-octave minimax-S") == "lp"


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


def test_interval_weights_return_the_weights_override_verbatim():
    import pytest

    # the manual weights override is the SAME the solve uses, so the displayed weight row IS it
    mapping = [[1, 1, 0], [0, 1, 4]]
    targets = ("3/2", "5/4", "5/3")
    got = service.interval_weights(mapping, "minimax-C", targets, weights_override=(1.0, 2.0, 5.0))
    assert got == pytest.approx((1.0, 2.0, 5.0))


def test_tuning_uses_the_weights_override_and_the_cache_distinguishes_it():
    import pytest

    # two DIFFERENT overrides must give two DIFFERENT tunings — guards the lru_cache key (a
    # missing weights_override in the key would return the first solve for the second override)
    mapping = [[1, 1, 0], [0, 1, 4]]
    scheme, targets = "TILT minimax-C", ("3/2", "5/4", "5/3")
    a = service.tuning(mapping, scheme, targets=targets, weights_override=(1.0, 1.0, 1.0))
    b = service.tuning(mapping, scheme, targets=targets, weights_override=(1.0, 50.0, 50.0))
    assert a.generator_map != pytest.approx(b.generator_map, abs=1e-3)
    # and an all-ones override over a complexity scheme matches the unity-weighted scheme
    unity = service.tuning(mapping, "TILT minimax-U", targets=targets)
    assert a.generator_map == pytest.approx(unity.generator_map, abs=1e-3)


def test_all_interval_tuning_ignores_the_weights_override():
    import pytest

    # an all-interval scheme has no per-target weights, so the override must not change it
    mapping = [[1, 1, 0], [0, 1, 4]]
    plain = service.tuning(mapping, "minimax-S")
    overridden = service.tuning(mapping, "minimax-S", weights_override=(9.0, 0.1, 7.0))
    assert overridden.generator_map == pytest.approx(plain.generator_map, abs=1e-3)


def test_all_interval_solver_handles_a_non_diagonal_pretransformer():
    import numpy as np
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]
    # a 2-D DIAGONAL override gives the SAME all-interval tuning as the equivalent 1-D diagonal —
    # the new X⁻¹-columns mean damage reduces to the old per-prime path for a diagonal matrix
    diag = (1.0, 1.585, 2.322)
    diag_2d = tuple(tuple(diag[i] if i == k else 0.0 for k in range(3)) for i in range(3))
    t1 = service.tuning(mapping, "minimax-S", prescaler_override=diag)
    t2 = service.tuning(mapping, "minimax-S", prescaler_override=diag_2d)
    assert t2.tuning_map == pytest.approx(t1.tuning_map, abs=1e-4)
    # a NON-diagonal pretransformer: the all-interval solve minimizes the TRUE mean damage ‖𝒓𝑋⁻¹‖∞
    # (minimax-S's dual norm power is ∞), not the per-prime diagonal approximation
    nondiag = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
    t3 = service.tuning(mapping, "minimax-S", prescaler_override=nondiag)
    M, j = np.array(mapping, float), np.array(t3.just_map)
    Xinv = np.linalg.inv(np.array(nondiag))
    magnitude = lambda g: float(np.max(np.abs((np.array(g) @ M - j) @ Xinv)))
    g0 = np.array(t3.generator_map)
    base = magnitude(g0)
    # g0 is the minimax of ‖𝒓𝑋⁻¹‖∞: no small generator perturbation reduces the mean damage
    for dg in ([0.5, 0], [0, 0.5], [-0.5, 0], [0, -0.5], [0.3, 0.3], [-0.3, 0.3]):
        assert magnitude(g0 + np.array(dg)) >= base - 1e-6


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


def _grid_with_ptext(state, scheme, custom_prescaler=None, **extra):
    """A _GridBuilder with the plain-text band + weighting + alt-complexity on (the layers the
    prescaler/complexity divergences live under), so ptext_strings and the grid's own quantities
    can be compared directly inside one builder — the strongest 'the two views agree' check."""
    se = app_settings.defaults()
    se.update({"plain_text_values": True, "weighting": True, "alt_complexity": True})
    se.update(extra)
    return spreadsheet._GridBuilder(state, se, None, service.resolve_tuning_scheme(scheme), "TILT",
                                    custom_prescaler=custom_prescaler)


def test_plain_text_custom_prescaler_matches_the_grid():
    # the bare prescaler tile's hand-edited diagonal threads into plain_text_values exactly as it
    # does into the grid: the SAME retuned tuning map, target complexity and weight (the grid passes
    # custom_prescaler into service.tuning / interval_weights / interval_complexities). Without the
    # thread the ptext re-derived from the scheme's log-prime diagonal and diverged from every one of
    # those grid tiles — the bug this guards.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone over 2.3.5
    gb = _grid_with_ptext(state, "TILT minimax-S", custom_prescaler=(1.0, 2.0, 3.0))
    pt = gb.ptext_strings
    # each retuned ptext tile equals the grid's own quantity (the same formatter the grid value uses)
    assert pt[("tuning", "primes")] == service._cents_map(gb.tun.tuning_map)
    assert pt[("complexity", "targets")] == service._cents_list(gb.complexities["targets"])
    assert pt[("weight", "targets")] == service._cents_list(gb.target_weights)
    # the bare prescaler reads the typed diagonal (1, 2, 3), not the scheme's log-prime weights
    assert pt[("prescaling", "primes")] == "[⟨1 0 0] ⟨0 2 0] ⟨0 0 3]⟩"
    # and it genuinely deviates from the no-override views (the divergence is gone, not coincidental)
    plain = _grid_with_ptext(state, "TILT minimax-S").ptext_strings
    assert pt[("tuning", "primes")] != plain[("tuning", "primes")]
    assert pt[("prescaling", "primes")] != plain[("prescaling", "primes")]


def test_plain_text_custom_prescaler_renders_an_off_diagonal_matrix_like_the_grid():
    # a non-diagonal pretransformer (the alt-complexity square's off-diagonal edit) renders its actual
    # matrix ROWS in the bare prescaler band — not the transpose — matching the grid cell (i, c) =
    # 𝑋[i][c]: the 0.5 sits in row 0, col 1. A naïve 𝐿·eₚ reuse would have shown its transpose.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    matrix = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
    pt = _grid_with_ptext(state, "TILT minimax-S", custom_prescaler=matrix).ptext_strings
    assert pt[("prescaling", "primes")] == "[⟨1 0.500 0] ⟨0 1.585 0] ⟨0 0 2.322]⟩"
    # the products and complexity still match the grid under the matrix override (no element-wise crash)
    gb = _grid_with_ptext(state, "TILT minimax-S", custom_prescaler=matrix)
    assert gb.ptext_strings[("tuning", "primes")] == service._cents_map(gb.tun.tuning_map)
    assert gb.ptext_strings[("complexity", "targets")] == service._cents_list(gb.complexities["targets"])


def test_plain_text_primes_complexity_runs_over_the_domain_basis_not_standard_primes():
    # the complexity-over-primes tile is each DOMAIN basis element's complexity, like the grid — NOT
    # the standard primes. Over 2.3.7 the third column is log₂7, never log₂5 (a prime the domain does
    # not even contain). Guards the standard_primes() truncation that diverged from the grid.
    state = service.from_temperament_data("2.3.7 [⟨1 1 3] ⟨0 2 -1]}")
    band = service.plain_text_values(state, "TILT minimax-S", "TILT")[("complexity", "primes")]
    elems = tuple(service.element_ratio(e) for e in state.domain_basis)
    over_basis = service.interval_complexities(state.mapping, "TILT minimax-S", elems,
                                               domain_basis=state.domain_basis)
    assert band == service._cents_map(over_basis)        # exactly the grid's domain-basis map
    assert service.cents(over_basis[2]) in band          # log₂7 ≈ 2.807 shows
    truncated = service.interval_complexities(state.mapping, "TILT minimax-S",
                                              tuple(f"{p}/1" for p in service.standard_primes(state.d)))
    assert service.cents(truncated[2]) not in band       # not the prime-truncated log₂5 ≈ 2.322


def test_plain_text_threads_the_nonprime_approach_into_its_tuning():
    # the grid passes nonprime_approach into service.tuning; plain_text_values must too, or its tuning
    # rows diverge from the grid over a nonprime domain. A nonprime-based approach retunes differently
    # from the neutral default here, so the ptext tuning map moves when the approach is threaded.
    state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
    neutral = service.plain_text_values(state, "TILT minimax-S", "TILT")
    nonprime = service.plain_text_values(state, "TILT minimax-S", "TILT", nonprime_approach="nonprime-based")
    assert nonprime[("tuning", "primes")] != neutral[("tuning", "primes")]
    # and it matches service.tuning called with that same approach (the grid's own input)
    tun = service.tuning(state.mapping, "TILT minimax-S", state.domain_basis, "nonprime-based")
    assert nonprime[("tuning", "primes")] == service._cents_map(tun.tuning_map)


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
    # 𝑀ⱼ = 𝐼, the domain-basis identity, is the p/p JI mapping — a covector stack closing with the
    # angle ⟩ (an operator, like P), not the mapping's }. (Gated on identity_objects via tile_open;
    # the string is always available here.)
    assert pt[("vectors", "primes")] == "[⟨1 0 0]⟨0 1 0]⟨0 0 1]⟩"


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
    # minimax-S is simplicity-weighted, so the damage row is 𝐝 = |𝐞|·W, not plain |error| —
    # the comparison sizes must carry the same weights or the two views diverge
    weights = service.interval_weights(state.mapping, "TILT minimax-S", targets)
    sizes = service.interval_sizes(tun, targets, weights=weights)

    def cents(values):  # the same 3-dp the grid shows, so the two views agree
        return " ".join(f"{v:.3f}" for v in values)

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

    def cents(values):
        return " ".join(f"{v:.3f}" for v in values)

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

    def cents(values):
        return " ".join(f"{v:.3f}" for v in values)

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

    def cents(values):
        return " ".join(f"{v:.3f}" for v in values)

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
    # draft vector greens. The helper returns (black prefix, green draft ket, black suffix); the
    # draft shows the entered components only (blanks omitted), e.g. (4, _, 1) -> "[4 1⟩".
    prefix, draft, suffix = service.vector_list_pending_text(((4, -4, 1),), [4, None, 1])
    assert (prefix, draft, suffix) == ("[[4 -4 1⟩ ", "[4 1⟩", "]")
    assert prefix + draft + suffix == "[[4 -4 1⟩ [4 1⟩]"  # the full string, reassembled
    # a brand-new (all-blank) draft is just an empty ket
    assert service.vector_list_pending_text(((4, -4, 1),), [None, None, None])[1] == "[⟩"
    # a second committed vector extends the black prefix; the draft is still its own ket
    assert service.vector_list_pending_text(((4, -4, 1), (4, -5, 1)), [None, None, None])[0] == "[[4 -4 1⟩ [4 -5 1⟩ "


def test_mapping_pending_text_splices_the_draft_map_before_the_closing_brace():
    # the ROW mirror: while a generator row is being added the editable mapping string is shown
    # two-tone — the committed maps (and the wrapping [ … }) stay black, the draft map greens. The
    # helper returns (black prefix, green draft map, black suffix); the draft shows the entered
    # components only (blanks omitted), e.g. (0, _, 1) -> "⟨0 1]".
    prefix, draft, suffix = service.mapping_pending_text("[⟨1 1 0] ⟨0 1 4]}", [0, None, 1])
    assert (prefix, draft, suffix) == ("[⟨1 1 0] ⟨0 1 4] ", "⟨0 1]", "}")
    assert prefix + draft + suffix == "[⟨1 1 0] ⟨0 1 4] ⟨0 1]}"  # the full string, reassembled
    # a brand-new (all-blank) draft is just an empty map
    assert service.mapping_pending_text("[⟨1 1 0] ⟨0 1 4]}", [None, None, None])[1] == "⟨]"
    # a domain-prefixed (nonstandard) mapping keeps its prefix in the black part
    assert service.mapping_pending_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}", [None, None, None])[0] \
        == "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3] "


def test_parse_mapping_state_reads_an_ebk_map_string():
    assert service.parse_mapping_state("[⟨1 1 0] ⟨0 1 4]}").mapping == ((1, 1, 0), (0, 1, 4))
    assert service.parse_mapping_state("⟨12 19 28]").mapping == ((12, 19, 28),)  # a single map
    # round-trips the mapping plain text
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert service.parse_mapping_state(pt[("mapping", "primes")]).mapping == ((1, 1, 0), (0, 1, 4))


def test_parse_comma_basis_reads_an_ebk_vector_string():
    assert service.parse_comma_basis("[4 -4 1⟩") == ((4, -4, 1),)
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert service.parse_comma_basis(pt[("vectors", "commas")]) == ((4, -4, 1),)


def test_parse_rejects_unparseable_wrong_variance_or_non_integer():
    assert service.parse_mapping_state("garbage") is None
    assert service.parse_mapping_state("") is None
    assert service.parse_mapping_state("[1 0 0⟩") is None  # a vector, not a map
    assert service.parse_mapping_state("⟨1 1.5 0]") is None  # a non-integer entry
    assert service.parse_comma_basis("⟨1 0 0]") is None  # a map, not a vector
    assert service.parse_comma_basis("nonsense") is None


def test_cents_and_prescale_text_round_to_integer_when_decimals_off():
    # the shared value formatters carry the Show panel's "decimals" setting: on (the default) they
    # keep the 3-dp cents reading; off they round to the nearest integer — the single chokepoint the
    # grid and plain-text views both route through, so turning decimals off rounds the whole app.
    assert service.cents(701.955) == "701.955"            # default: 3 dp
    assert service.cents(701.955, decimals=False) == "702"  # off: nearest integer, no point
    assert service.cents(None, decimals=False) == "—"     # a dashed value is still an em-dash
    # prescale_text keeps whole entries bare either way; a non-whole one rounds with decimals off
    assert service.prescale_text(1.0, decimals=False) == "1"
    assert service.prescale_text(1.585) == "1.585"
    assert service.prescale_text(1.585, decimals=False) == "2"


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
    # a 3-wide matrix read as d == 2 clears the row-count gate (3 ∈ {2, 3}) but every row is too
    # wide for d == 2, so the per-row width check rejects it
    assert service.parse_prescaler_diagonal("[⟨1 0 0] ⟨0 1 0] ⟨0 0 1]⟩", 2) is None
    # a fractional diagonal entry is not a real (float) scaling factor — 𝐿's diagonal is sizes
    assert service.parse_prescaler_diagonal("[⟨1/2 0 0] ⟨0 1 0] ⟨0 0 1]⟩", 3) is None


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
    assert service.domain_has_nonprimes((2, 5, 7)) is False  # pure-prime nonstandard subgroup (skips 3)
    assert service.domain_has_nonprimes((2, 3, Fraction(7, 1))) is False  # Fraction that IS a prime int
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


def test_basis_in_superspace_writes_each_element_as_a_vector_over_the_superspace_primes():
    # Convention (chosen rows-as-elements, matching the comma-basis / target-vector storage in
    # this service): each ROW is one domain element written as a vector over the superspace
    # primes — d rows of length dL. For BARBADOS over 2.3.13/5 with superspace (2,3,5,13):
    # 2 → ⟨1 0 0 0], 3 → ⟨0 1 0 0], 13/5 → ⟨0 0 -1 1].
    barbados = service.basis_in_superspace((2, 3, Fraction(13, 5)))
    assert barbados == ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
    # a standard prime basis is the identity over itself (each element is one prime, one slot)
    assert service.basis_in_superspace((2, 3, 5)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    # composites factor: 9 = 3² → (0, 2, 0) over (2, 3, 5)
    assert service.basis_in_superspace((2, 9, 5)) == ((1, 0, 0), (0, 2, 0), (0, 0, 1))


def test_superspace_complexity_prescaler_is_log_prime_over_the_superspace_primes():
    # The prescaler the neutral/prime-based approaches measure complexity with lives over the
    # SUPERSPACE primes (both prime-factor), not the nonprime domain. For BARBADOS over 2.3.13/5
    # with superspace (2, 3, 5, 13) the log-prime diagonal is (1, log2 3, log2 5, log2 13) — note
    # the 13/5 element does NOT appear as log2(13/5); it's the true primes 5 and 13 that carry weight.
    s = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.superspace_complexity_prescaler(s) == pytest.approx(
        (1.0, math.log2(3), math.log2(5), math.log2(13))
    )
    # the article example 2.7/3.11/3 lifts to (2, 3, 7, 11): (1, log2 3, log2 7, log2 11)
    s2 = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]}")
    assert service.superspace_complexity_prescaler(s2) == pytest.approx(
        (1.0, math.log2(3), math.log2(7), math.log2(11))
    )


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


def test_superspace_tuning_projection_reduces_to_the_on_domain_projection():
    # over a standard prime basis the superspace IS the domain (dL = d), so P_L = P: the
    # superspace projection equals the on-domain tuning_projection cell-for-cell. Quarter-comma
    # meantone held by {2/1, 5/4} is a full rational projection there.
    mt = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    held = ("2", "5/4")
    assert service.superspace_tuning_projection(mt, held) == service.tuning_projection(mt, held)


def test_superspace_tuning_projection_is_the_identity_for_just_intonation():
    # n = 0 (no commas) over a nonstandard domain: nothing is tempered, so P_L = I_dL. JI over
    # 2.3.13/5 lifts to dL = 4, and every superspace prime is held justly.
    triv = service.from_temperament_data("2.3.13/5 [⟨1 0 0] ⟨0 1 0] ⟨0 0 1]}")
    pl = service.superspace_tuning_projection(triv)
    assert pl == (("1", "0", "0", "0"), ("0", "1", "0", "0"),
                  ("0", "0", "1", "0"), ("0", "0", "0", "1"))


def test_superspace_tuning_projection_is_a_dL_idempotent_holding_the_lifted_held():
    # BARBADOS over 2.3.13/5 (d=3, dL=4, r=2, rL=3) held by {2/1, 13/5}: P_L is the dL × dL = 4×4
    # rational projection P_L = G_L·M_L over the superspace primes (2, 3, 5, 13). It is idempotent,
    # holds each held interval (lifted) justly, and tempers out the lifted comma 676/675 = (2,-3,-2,2).
    import sympy as sp
    barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pl = service.superspace_tuning_projection(barb, ("2", "13/5"))
    assert pl is not None
    assert len(pl) == 4 and all(len(row) == 4 for row in pl)  # dL × dL
    m = sp.Matrix([[sp.Rational(x) for x in row] for row in pl])
    assert m * m == m  # idempotent (a genuine projection)
    # holds 2/1 = (1,0,0,0) and 13/5 = (0,0,-1,1) lifted to the superspace
    for held in ((1, 0, 0, 0), (0, 0, -1, 1)):
        assert list(m * sp.Matrix(4, 1, list(held))) == list(held)
    # the lifted comma is in the kernel (tempered out)
    assert list(m * sp.Matrix(4, 1, [2, -3, -2, 2])) == [0, 0, 0, 0]


def test_superspace_tuning_embedding_is_the_dL_by_rL_factor_of_P_L():
    # G_L = H_L·(M_L·H_L)⁻¹, the embedding factor of P_L = G_L·M_L (the ssgens-column tile): dL × rL,
    # its columns the held tuning's superspace generators as fractional superspace-prime vectors.
    # BARBADOS over 2.3.13/5 (dL=4, rL=3) held by {2/1, 13/5}. None (dashed) in lockstep with P_L.
    import sympy as sp
    barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    gl = service.superspace_tuning_embedding(barb, ("2", "13/5"))
    assert len(gl) == 4 and all(len(row) == 3 for row in gl)  # dL × rL
    assert service.superspace_tuning_embedding(barb, ("2",)) is None  # under-held dashes, like P_L
    # G_L is genuinely the embedding factor of P_L: G_L·M_L equals P_L (rebuilt from the rationals)
    ml = service.superspace_mapping(barb)
    g = sp.Matrix([[sp.Rational(x) for x in row] for row in gl])
    m = sp.Matrix([list(r) for r in ml])
    pl = sp.Matrix([[sp.Rational(x) for x in row] for row in service.superspace_tuning_projection(barb, ("2", "13/5"))])
    assert g * m == pl  # P_L = G_L · M_L


def test_superspace_projection_matrix_rationals_matches_the_display_strings():
    # the rational (Fraction) P_L drives project_vectors for the row's P_L·B_Ls / P_L·V / P_L·T_L tiles;
    # str() of each entry is exactly the display grid superspace_tuning_projection returns.
    barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    rat = service.superspace_projection_matrix_rationals(barb, ("2", "13/5"))
    disp = service.superspace_tuning_projection(barb, ("2", "13/5"))
    assert tuple(tuple(str(x) for x in row) for row in rat) == disp
    assert service.superspace_projection_matrix_rationals(barb, ("2",)) is None  # dashes in lockstep


def test_superspace_tuning_projection_is_none_when_under_held():
    # under-held (fewer than r rational held intervals): no full rational projection, so None —
    # the row dashes, exactly like the on-domain tuning_projection. BARBADOS (r=2) held by only 2/1.
    barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.superspace_tuning_projection(barb, ("2",)) is None
    assert service.tuning_projection(barb, ("2",)) is None  # the on-domain row dashes in lockstep


def test_plain_text_values_includes_the_superspace_projection_when_projection_on():
    # parity with the on-domain projection P and the sibling superspace matrices (B_L, M_L, M_jL):
    # P_L gets a plain-text EBK band too — a covector stack closing with the prime-coordinate angle ⟩
    # (a p/p operator over the superspace primes, framed like P), gated on the projection toggle (consolidate_v) like P. Dashed
    # in lockstep when the tuning isn't a full rational projection.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=("2", "13/5"))
    assert pt[("ss_projection", "ssprimes")] == "[⟨1 2/3 0 0]⟨0 0 0 0]⟨0 -2/3 1 0]⟨0 2/3 0 1]⟩"
    # projection off (no V consolidation): no P_L band, exactly like the on-domain P plain text
    off = service.plain_text_values(state, superspace=True, consolidate_v=False, held_basis_ratios=("2", "13/5"))
    assert ("ss_projection", "ssprimes") not in off
    # under-held: the band is present but fully dashed (lockstep with the dashed grid)
    dashed = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=())
    assert dashed[("ss_projection", "ssprimes")] == service.projection_ebk(None, 4)


def test_plain_text_values_includes_every_superspace_projection_tile():
    # parity with the on-domain projection row: EVERY tile of the superspace projection row gets its EBK
    # band, not just P_L — the embedding G_L and P_L applied to each lifted list (P_L·B_L / P_L·D_L /
    # P_L·V / P_L·T_L), each built from the same P_L the grid uses.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=("2", "13/5"))
    for col in ("ssgens", "ssprimes", "primes", "detempering", "commas", "targets"):
        assert ("ss_projection", col) in pt, col
    # the bracket shapes mirror the on-domain twins: G_L a vector list ({…]), P_L·B_Ls the covector-style
    # ⟨…] of B_L, P_L·D_L the generator-coordinate {…], P_L·V / P_L·T_L the plain […]
    assert pt[("ss_projection", "ssgens")].startswith("{") and pt[("ss_projection", "ssgens")].endswith("]")
    assert pt[("ss_projection", "primes")].startswith("⟨")
    assert pt[("ss_projection", "detempering")].startswith("{")
    assert pt[("ss_projection", "targets")].startswith("[")
    # dashed in lockstep with P_L when under-held
    dashed = service.plain_text_values(state, superspace=True, consolidate_v=True, held_basis_ratios=())
    assert "—" in dashed[("ss_projection", "primes")]


def test_plain_text_values_includes_superspace_entries_when_superspace_on():
    # Phase 4: the nonstandard-domain superspace region (B_L, M_L, M_jL, 𝒈ₗ / 𝒕ₗ / 𝒋ₗ /
    # 𝒓ₗ) gets its own plain-text strings when the superspace flag is on — the EBK string
    # under each new tile, matching the gridded cells the spreadsheet emits.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state, superspace=True)
    # B_L (basis change matrix): each domain element as a ket over the superspace primes,
    # wrapped in the distinct OUTER ⟨ … ] the mockup draws for it
    assert pt[("ss_vectors", "primes")] == "⟨[1 0 0 0⟩ [0 1 0 0⟩ [0 0 -1 1⟩]"
    # M_L: the temperament's mapping over the superspace primes (covector stack — same
    # mapping-style ⟨ … ] inside [ … } shape the existing M uses)
    ml = service.superspace_mapping(state)
    expected_ml = "[" + "".join("⟨" + " ".join(str(x) for x in row) + "]" for row in ml) + "}"
    assert pt[("ss_mapping", "ssprimes")] == expected_ml
    # M_jL = I (dL × dL identity) — the p/p JI mapping over the superspace primes, a tile in the ss_vectors row. A covector
    # stack closing with the angle ⟩ (an operator, like P_L), NOT the mapping's }.
    assert pt[("ss_vectors", "ssprimes")] == (
        "[⟨1 0 0 0]⟨0 1 0 0]⟨0 0 1 0]⟨0 0 0 1]⟩"
    )
    # M_LGL = I (rL × rL identity) — a COLUMN-first vector list { … ] (kets [ … } in gen coords)
    assert pt[("ss_mapping", "ssgens")] == "{[1 0 0} [0 1 0} [0 0 1}]"
    # the cyan tuning rows have entries
    assert ("tuning", "ssgens") in pt
    assert ("tuning", "ssprimes") in pt
    assert ("just", "ssprimes") in pt
    assert ("retune", "ssprimes") in pt


def test_plain_text_values_omits_superspace_entries_when_superspace_off():
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state)  # superspace=False (default)
    for key in (("ss_vectors", "primes"), ("ss_mapping", "ssprimes"),
                ("ss_vectors", "ssprimes"), ("tuning", "ssgens"),
                ("tuning", "ssprimes"), ("just", "ssprimes"), ("retune", "ssprimes")):
        assert key not in pt


def test_plain_text_all_interval_lils_weight_is_the_per_target_list():
    # all-interval lils: the weight plain text is the per-target simplicity-weight LIST (the same the grid
    # renders) — NOT the [[…] …] matrix form. The grid's tile symbol carries its 𝒘 = 𝒄⁻¹ form, not here.
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]), scheme="minimax-lils-S")
    w = pt[("weight", "targets")]
    assert w.startswith("[") and not w.startswith("[[")   # a flat list, not a nested matrix
    assert "|" not in w                                    # no size-augmentation divider
# ── domain basis element editing (chapter-9 nonstandard-domain input) ────────────────────────

def test_resolve_comma_basis_form_prefers_the_user_pick_when_forms_coincide():
    # meantone's positive-ratio comma 81/80 is ALSO its minimal form (a single comma is already
    # minimal), so the two options produce the same matrix. identify_* returns only the earliest
    # (positive-ratio); resolve_* honors the user's actual pick as a tiebreaker.
    positive = ((-4, 4, -1),)
    assert service.identify_comma_basis_form(positive) == "positive-ratio"
    assert service.resolve_comma_basis_form(positive, "minimal") == "minimal"
    assert service.resolve_comma_basis_form(positive, "positive-ratio") == "positive-ratio"
    # a preferred form the matrix is NOT in is ignored — falls back to the first real match
    assert service.resolve_comma_basis_form(positive, "canonical") == "positive-ratio"
    # no/unknown preference behaves exactly like identify (just never None — "" placeholder)
    assert service.resolve_comma_basis_form(((4, -4, 1),), None) == "canonical"
    assert service.resolve_mapping_form(((1, 1, 0), (0, 1, 4)), None) == "equave-reduced"


def test_parse_domain_element_accepts_positive_rationals_and_rejects_junk():
    assert service.parse_domain_element("7") == 7  # an integer normalizes to a bare int
    assert service.parse_domain_element("13/5") == Fraction(13, 5)  # a nonprime stays a Fraction
    assert service.parse_domain_element("9/3") == 3  # reduces, then normalizes to int
    for junk in ("abc", "", "1", "0", "-3", "5/0"):
        assert service.parse_domain_element(junk) is None


def test_is_independent_domain_basis_rejects_dependent_elements():
    assert service.is_independent_domain_basis((2, 3, 5))
    assert service.is_independent_domain_basis((2, 3, Fraction(13, 5)))  # 13/5 adds the 13 direction
    assert not service.is_independent_domain_basis((2, 3, 9))  # 9 = 3², dependent
    assert not service.is_independent_domain_basis((2, 4))  # 4 = 2², dependent


def test_add_domain_element_holds_the_new_element_just():
    # meantone 2.3.5: adding 7 makes it its own pure generator — a block-diagonal mapping row
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    added = service.add_domain_element(state, service.parse_domain_element("7"))
    assert added.domain_basis == (2, 3, 5, 7)
    assert added.d == state.d + 1 and added.r == state.r + 1 and added.n == state.n  # +d, +r, n held
    assert added.mapping == ((1, 1, 0, 0), (0, 1, 4, 0), (0, 0, 0, 1))  # existing cols intact, unit row
    # the new element's own generator tunes it pure (zero error on 7)
    tun = service.tuning(added.mapping, service.DEFAULT_TUNING_SCHEME, added.domain_basis)
    assert tun.tuning_map[3] == pytest.approx(1200 * math.log2(7), abs=1e-6)


def test_add_domain_element_accepts_a_nonprime():
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    added = service.add_domain_element(state, service.parse_domain_element("13/5"))
    assert added.domain_basis == (2, 3, 5, Fraction(13, 5))
    assert added.d == 4 and added.r == 3 and added.n == state.n


def test_can_add_domain_element_guards_validity_and_independence():
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5
    assert service.can_add_domain_element(state, "7")
    assert service.can_add_domain_element(state, "13/5")
    assert not service.can_add_domain_element(state, "9")   # 9 = 3², dependent on the present 3
    assert not service.can_add_domain_element(state, "1")   # the unison spans nothing
    assert not service.can_add_domain_element(state, "abc")  # not a rational


def test_set_domain_element_is_a_pure_relabel():
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5
    relabelled = service.set_domain_element(state, 2, service.parse_domain_element("13/5"))
    assert relabelled.domain_basis == (2, 3, Fraction(13, 5))
    assert relabelled.mapping == state.mapping  # coordinates untouched — only the basis label changed


def test_can_set_domain_element_rejects_a_dependent_relabel():
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 2.3.5
    assert service.can_set_domain_element(state, 2, "13/5")
    assert not service.can_set_domain_element(state, 2, "9")  # 2.3.9 is dependent
    assert not service.can_set_domain_element(state, 2, "8")  # 2.3.8 (8 = 2³) is dependent
    assert not service.can_set_domain_element(state, 2, "1")


def test_remove_domain_element_drops_the_named_element_keeping_the_basis_nonstandard():
    # over the nonstandard 2.3.13/5: removing ANY element drops it and re-duals over the remaining
    # basis (kept nonstandard, not reset to a prime limit), lowering d by one.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.remove_domain_element(state, 0).domain_basis == (3, Fraction(13, 5))
    assert service.remove_domain_element(state, 1).domain_basis == (2, Fraction(13, 5))
    assert service.remove_domain_element(state, 2).domain_basis == (2, 3)  # the lone nonprime gone → standard
    for k in range(state.d):
        assert service.remove_domain_element(state, k).d == state.d - 1


def test_remove_domain_element_inverts_add_domain_element():
    # add_domain_element appends an element with an all-zero comma column (held just); trimming that
    # column and re-dualing recovers the SAME temperament (comma basis + domain) it started from. The
    # mapping re-canonicalizes (a re-dual, like shrink_domain), so compare the temperament, not the
    # generator basis.
    state = service.from_comma_basis(((4, -4, 1),))  # meantone 2.3.5
    added = service.add_domain_element(state, service.parse_domain_element("13/5"))
    back = service.remove_domain_element(added, added.d - 1)  # drop the element just added
    assert back.domain_basis == state.domain_basis and back.comma_basis == state.comma_basis
    assert (back.d, back.r, back.n) == (state.d, state.r, state.n)


def test_remove_domain_element_matches_shrink_for_the_last_standard_element():
    # over a standard limit, removing the highest element is exactly the prime-walk shrink — so the
    # box-on per-element − and the box-off walk − coincide on the last element.
    state = service.from_comma_basis(((4, -4, 1),))  # meantone 2.3.5
    removed = service.remove_domain_element(state, state.d - 1)
    shrunk = service.shrink_domain(state)
    assert removed.domain_basis == shrunk.domain_basis == (2, 3)
    assert removed.mapping == shrunk.mapping and removed.comma_basis == shrunk.comma_basis


def test_remove_domain_element_collapsing_every_comma_leaves_just_intonation():
    # tempering out the prime 5 (comma 0,0,1): removing the 5 trims that comma to zero, so nothing
    # tempered survives — just intonation over the reduced basis (nullity 0).
    state = service.from_comma_basis(((0, 0, 1),))  # 2.3.5, 5 tempered to a unison
    ji = service.remove_domain_element(state, 2)
    assert ji.domain_basis == (2, 3) and ji.n == 0 and ji.r == ji.d == 2


def test_can_remove_domain_element_keeps_at_least_one_element():
    assert service.can_remove_domain_element(service.from_comma_basis(((4, -4, 1),)))  # d = 3
    assert not service.can_remove_domain_element(service.from_mapping(((1,),)))  # d = 1: nothing to remove


def test_generator_tuning_range_is_none_for_an_unmeasurable_mixed_basis():
    # 2.3.5.13/5 (5 and 13/5 share the prime 5): the odd-limit diamond the range solver works over
    # isn't defined, so the range gracefully degrades to None rather than crashing the tuning build.
    state = service.from_mapping(((1, 1, 0, 0), (0, 1, 4, 0), (0, 0, 0, 1)),
                                 domain_basis=(2, 3, 5, Fraction(13, 5)))
    t = service.tuning(state.mapping, service.DEFAULT_TUNING_SCHEME, state.domain_basis)
    assert t.monotone_generator_range is None and t.tradeoff_generator_range is None
    assert all(x == x for x in t.tuning_map)  # the tuning itself is finite and unaffected


def test_tuning_projection_is_dashed_for_an_under_held_tuning():
    # the corrected model: a tuning is a rational projection ONLY if it holds a full-rank (r)
    # rational basis. Given an EMPTY unchanged basis (a tuning known to hold nothing rational, like
    # minimax-S) or only the octave (h=1 < r=2), P is dashed out (None), never fabricated. (Which
    # rational intervals the displayed tuning actually holds is read off it by
    # unchanged_ratios_of_tuning, then fed here.)
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_projection(state) is None
    assert service.tuning_projection(state, ("2/1",)) is None


def test_unchanged_ratios_of_tuning_reads_the_held_intervals_off_the_tuning():
    # U comes from the DISPLAYED tuning, not a held column: the default minimax-U meantone holds 2/1
    # and 5/4 at zero damage (it IS quarter-comma), so they are reported with no held column at all —
    # tested only against the candidate ratios, established representatives first for clean output.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    candidates = ("2/1", "5/4", "6/5", "3/2", "9/8")
    default = service.tuning(state.mapping, service.DEFAULT_DOCUMENT_SCHEME)
    assert service.unchanged_ratios_of_tuning(state, default.retuning_map, candidates) == ("2/1", "5/4")
    # an irrational optimum (minimax-S tempers even the octave) holds nothing rational → empty → dashed
    minimax_s = service.tuning(state.mapping, "minimax-S")
    assert service.unchanged_ratios_of_tuning(state, minimax_s.retuning_map, candidates) == ()


def test_tuning_projection_of_just_intonation_is_the_identity():
    # nullity 0 (no commas): nothing is tempered, so every prime is held and P = I.
    state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert service.tuning_projection(state) == (
        ("1", "0", "0"),
        ("0", "1", "0"),
        ("0", "0", "1"),
    )


def test_tuning_projection_for_a_full_rational_held_basis_quarter_comma():
    # a FULL-RANK rational hold pins the tuning as a rational projection: {2/1, 5/4} is
    # quarter-comma meantone, P = GM holding 2 and 5/4.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_projection(state, ("2/1", "5/4")) == (
        ("1", "1", "0"),
        ("0", "0", "0"),
        ("0", "1/4", "1"),
    )


def test_tuning_projection_third_comma():
    # third-comma meantone holds {2/1, 6/5} (pure minor third) — a different rational tuning.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_projection(state, ("2/1", "6/5")) == (
        ("1", "4/3", "4/3"),
        ("0", "-1/3", "-4/3"),
        ("0", "1/3", "4/3"),
    )


def test_tuning_projection_pythagorean():
    # the Pythagorean (0-comma) tuning of meantone holds {2/1, 3/2} (pure fifth).
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_projection(state, ("2/1", "3/2")) == (
        ("1", "0", "-4"),
        ("0", "1", "4"),
        ("0", "0", "0"),
    )


def test_tuning_embedding_for_a_full_rational_held_basis():
    # G = H·(M·H)⁻¹: its columns are the generators as fractional vectors. Quarter-comma's
    # second generator is 5^(1/4) — the [0 0 1/4] column.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_embedding(state, ("2/1", "5/4")) == (
        ("1", "0"),
        ("0", "0"),
        ("0", "1/4"),
    )


def test_tuning_embedding_third_comma():
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_embedding(state, ("2/1", "6/5")) == (
        ("1", "1/3"),
        ("0", "-1/3"),
        ("0", "1/3"),
    )


def test_tuning_embedding_is_dashed_when_the_projection_is():
    # G is dashed (None) exactly when P is — an under-held tuning is no rational embedding either.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.tuning_embedding(state) is None
    assert service.tuning_embedding(state, ("2/1",)) is None


def test_projection_matrix_rationals_returns_the_rational_p():
    # the rational source behind tuning_projection's display strings — Fraction entries, so the
    # spreadsheet can multiply vector sets through P (the projected lists P·D, P·H, P·T, P·interest)
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.projection_matrix_rationals(state, ("2/1", "5/4")) == (
        (Fraction(1), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(0)),
        (Fraction(0), Fraction(1, 4), Fraction(1)),
    )


def test_projection_matrix_rationals_is_none_for_an_under_held_tuning():
    # None in lockstep with tuning_projection — an under-held tuning is no rational projection
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.projection_matrix_rationals(state) is None
    assert service.projection_matrix_rationals(state, ("2/1",)) is None


def test_project_vectors_is_empty_without_a_projection():
    # the projection MATH (P·v per column, P·H = H) is pinned library-side in
    # tests/library/unit/test_superspace.py; here the wrapper's dash policy:
    # no P (None, an under-held tuning) or no vectors → empty, so the caller dashes / shows nothing
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    p = service.projection_matrix_rationals(state, ("2/1", "5/4"))
    assert service.project_vectors(None, ((1, 0, 0),)) == ()
    assert service.project_vectors(p, ()) == ()


def test_superspace_generator_embedding_and_projection_for_barbados():
    # the superspace projection-row tiles G_L→s (d×rL) and P_L→s (d×dL) for BARBADOS over 2.3.13/5,
    # holding {2/1, 3/1}. P·(M_s→L)⁺ gives G_L→s; P_L→s = G_L→s·M_L.
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.superspace_generator_embedding_display(state, ("2/1", "3/1")) == (
        ("1", "0", "0"),
        ("0", "1/2", "0"),
        ("0", "0", "0"),
    )
    assert service.superspace_prime_projection_display(state, ("2/1", "3/1")) == (
        ("1", "0", "0", "-1"),
        ("0", "1", "0", "3/2"),
        ("0", "0", "0", "0"),
    )


def test_superspace_projection_satisfies_the_mockup_identities():
    # the defining identities the mockup pins: P = G_L→s·M_s→L and P = P_L→s·B_Lᵀ
    from rtt.library.matrix_utils import matrix_multiply, transpose
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    p = service.projection_matrix_rationals(state, ("2/1", "3/1"))
    g_ls = service.superspace_generator_embedding(state, ("2/1", "3/1"))
    p_ls = service.superspace_prime_projection(state, ("2/1", "3/1"))
    msl = service.mapping_to_superspace_generators(state)
    bl = service.basis_in_superspace(state.domain_basis)
    assert matrix_multiply(g_ls, msl) == p             # G_L→s · M_s→L = P
    assert matrix_multiply(p_ls, transpose(bl)) == p   # P_L→s · B_Lᵀ = P


def test_superspace_projection_is_none_when_under_held():
    # dashed in lockstep with the on-domain projection — an under-held tuning is no rational projection
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.superspace_generator_embedding_display(state) is None
    assert service.superspace_prime_projection_display(state) is None


def test_unchanged_basis_from_projection_recovers_U_and_rejects_invalid():
    # a hand-edited P round-trips to its unchanged basis (eigenvalue-1 eigenvectors); an invalid edit
    # (not idempotent, or commas not in its kernel) is rejected with None
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    p13 = service.tuning_projection(state, ("2/1", "6/5"))           # third-comma's P
    U = service.unchanged_basis_from_projection(state, p13)
    assert U is not None and service.tuning_projection(state, service.comma_ratios(U)) == p13
    assert service.unchanged_basis_from_projection(state, (("1", "1", "0"), ("0", "1", "0"), ("0", "0", "1"))) is None
    assert service.unchanged_basis_from_projection(state, (("2", "0", "0"), ("0", "1", "0"), ("0", "0", "1"))) is None


def test_unchanged_basis_from_embedding_recovers_U_and_rejects_invalid():
    # a hand-edited G round-trips to its unchanged basis (column space); an invalid edit (M·G ≠ I) is
    # rejected with None
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    g13 = service.tuning_embedding(state, ("2/1", "6/5"))            # third-comma's G
    U = service.unchanged_basis_from_embedding(state, g13)
    assert U is not None and service.tuning_embedding(state, service.comma_ratios(U)) == g13
    assert service.unchanged_basis_from_embedding(state, (("2", "0"), ("0", "0"), ("0", "1/4"))) is None  # M·G ≠ I


def test_projection_and_embedding_ebk_match_the_mockup_and_round_trip():
    # P is a map-list EBK ([⟨…]…⟩, a covector stack closing with the prime ket ⟩); G a vector-list EBK
    # ([[…⟩…], its held generators as ket columns). The strings match the mockup, and parse back to the
    # exact grids (G's r kets transposed into the d×r matrix the setter expects).
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # 5-limit meantone, d=3 r=2
    P = service.tuning_projection(state, ("2/1", "5/4"))   # 1/4-comma
    G = service.tuning_embedding(state, ("2/1", "5/4"))
    assert service.projection_ebk(P, 3) == "[⟨1 1 0]⟨0 0 0]⟨0 1/4 1]⟩"   # map list, outer [ … ⟩
    assert service.embedding_ebk(G, 3, 2) == "{[1 0 0⟩ [0 0 1/4⟩]"        # vector list, outer { … ]
    assert service.parse_projection(service.projection_ebk(P, 3)) == P
    assert service.parse_embedding(service.embedding_ebk(G, 3, 2), 3, 2) == G
    # a None matrix (not a full rational projection) dashes every entry, matching the dashed grid
    assert service.projection_ebk(None, 3) == "[⟨— — —]⟨— — —]⟨— — —]⟩"
    assert service.embedding_ebk(None, 3, 2) == "{[— — —⟩ [— — —⟩]"


def test_projection_and_embedding_parsers_reject_bad_input():
    # the parsers gate shape, variance, and rationality before the editor's idempotency / 𝑀𝐺=𝐼 checks
    assert service.parse_projection("[[1 0 0⟩[0 1 0⟩[0 0 1⟩]") is None     # COL variance (a vector list), not a map
    assert service.parse_projection("[⟨1.5 0 0]⟨0 1 0]⟨0 0 1]⟩") is None   # a float entry
    assert service.parse_projection("garbage") is None                     # unparseable
    assert service.parse_embedding("[⟨1 1 0]⟨0 1 4]}", 3, 2) is None       # ROW variance (a map), not a vector list
    assert service.parse_embedding("[[1 0 0⟩[0 0 1/4⟩[0 0 0⟩]", 3, 2) is None  # 3 kets, but r = 2
    assert service.parse_embedding("[[1 0⟩[0 1⟩]", 3, 2) is None           # kets of length 2, but d = 3


def test_rational_matrix_or_none_accepts_fractions_rejects_floats_and_ragged():
    from fractions import Fraction
    assert service._rational_matrix_or_none(((1, Fraction(1, 4)), (0, -1))) == (("1", "1/4"), ("0", "-1"))
    assert service._rational_matrix_or_none(((1.5, 0), (0, 1))) is None     # float
    assert service._rational_matrix_or_none(((True, 0), (0, 1))) is None    # bool
    assert service._rational_matrix_or_none(((1, 0), (0,))) is None         # ragged
    assert service._rational_matrix_or_none(()) is None                     # empty


def test_tuning_embedding_of_just_intonation_is_the_identity():
    # nullity 0: every prime is its own generator, so G = I (the d×d identity).
    state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert service.tuning_embedding(state) == (
        ("1", "0", "0"),
        ("0", "1", "0"),
        ("0", "0", "1"),
    )


def test_tuning_projection_and_embedding_drop_a_degenerate_held_basis():
    # pajara maps 7/5 to exactly half the octave's image, so {2/1, 7/5} cannot be a
    # simultaneous unchanged interval basis: M·H is singular and no rational projection
    # forms. Both helpers return None rather than crash (the chooser then won't offer it).
    state = service.from_mapping(((2, 3, 5, 6), (0, 1, -2, -2)))
    assert service.tuning_projection(state, ("2/1", "7/5")) is None
    assert service.tuning_embedding(state, ("2/1", "7/5")) is None


# --- the unchanged interval basis U: the held intervals padded to rank r with dashes ---

def test_unchanged_interval_basis_is_all_dashes_for_an_under_held_tuning():
    # the default meantone tuning holds nothing rational (h=0), so BOTH unchanged columns are
    # dashed (None): the tuning isn't a rational projection, and nothing is fabricated.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.unchanged_interval_basis(state) == (None, None)
    assert service.unchanged_interval_ratios(state) == ()  # no KNOWN unchanged intervals


def test_unchanged_interval_basis_pads_a_partial_hold_with_a_dash():
    # holding only the octave (h=1 < r=2) fills ONE unchanged column; the other stays dashed
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.unchanged_interval_basis(state, ("2/1",)) == ((1, 0, 0), None)
    assert service.unchanged_interval_ratios(state, ("2/1",)) == ("2/1",)


def test_unchanged_interval_basis_is_the_held_basis_when_full_rank():
    # a full-rank rational hold completes U (no dashes) — it IS the held intervals, as entered:
    # {2/1, 5/4} for quarter-comma, {2/1, 6/5} for third-comma.
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.unchanged_interval_basis(state, ("2/1", "5/4")) == ((1, 0, 0), (-2, 0, 1))
    assert service.unchanged_interval_ratios(state, ("2/1", "5/4")) == ("2/1", "5/4")
    assert service.unchanged_interval_basis(state, ("2/1", "6/5")) == ((1, 0, 0), (1, 1, -1))


def test_unchanged_interval_basis_of_just_intonation_is_every_prime():
    # nullity 0 (no commas): P = I, so every prime is unchanged — U spans the whole domain.
    state = service.from_mapping(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    assert service.unchanged_interval_basis(state) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert service.unchanged_interval_ratios(state) == ("2/1", "3/1", "5/1")


def test_unchanged_interval_basis_always_has_r_columns():
    # 7-limit pajara (d=4, r=2): U always has r=2 columns. Under-held → both dashed; holding the
    # two primes 2 and 7 (a full rational basis) completes it.
    state = service.from_mapping(((2, 3, 5, 6), (0, 1, -2, -2)))
    assert service.unchanged_interval_basis(state) == (None, None)
    assert len(service.unchanged_interval_basis(state)) == state.r == state.d - state.n
    assert service.unchanged_interval_basis(state, ("2/1", "7/1")) == ((1, 0, 0, 0), (0, 0, 0, 1))


def test_held_basis_vectors_keeps_only_independent_in_domain_intervals():
    # the held interval basis reduces to a basis: dependent / out-of-domain / beyond-rank entries
    # are dropped (a tuning can't hold more than r independent directions).
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    assert service.held_basis_vectors(state, ("2/1", "4/1")) == ((1, 0, 0),)   # 4/1 ∥ 2/1, dropped
    assert service.held_basis_vectors(state, ("2/1", "5/4", "3/2")) == ((1, 0, 0), (-2, 0, 1))  # capped at r=2


# ── audit fixes: crash guard, domain preservation, prescaler basis, enfactoring, empty targets ──
# (the functionality-audit report's service-layer findings; each reproduces the exact repro and
# asserts the fix. The report predates the service.py → service/ package split, so line numbers
# in the finding IDs below refer to the old single file.)


def test_vectors_to_ratios_flags_an_over_complex_ratio_instead_of_crashing():
    # CPython refuses to stringify an int past ~4300 digits, so a degenerate near-full-rank mapping
    # whose generator detempering is astronomically complex used to crash the formatter mid-render
    # (and, with no try/finally around render(), brick the page). Such a ratio is now flagged with a
    # sentinel rather than rendered. (editor-state-machine-1.)
    huge = service.from_mapping(((3, 4, -8), (-1, 7, 6), (3, 0, 6)))  # full-rank, accepted, vast generators
    gens = service.generators(huge.mapping)
    assert gens == (service._OVER_COMPLEX_RATIO,) * 3  # flagged, not a 4300+-digit string (no crash)
    # a normal (small) generator still renders its ratio — the guard only intercepts the meaningless
    assert service.generators(((1, 1, 0), (0, 1, 4))) == ("2/1", "3/2")


def test_over_complex_generators_round_trip_back_to_a_finite_size():
    # the flagged ratio is parsed back as a unison so the detempering size / complexity rows that
    # round-trip these ratio strings stay finite instead of crashing the same way. The whole grid
    # build (the original crash site, service.generators inside spreadsheet.build) succeeds.
    state = service.from_mapping(((3, 4, -8), (-1, 7, 6), (3, 0, 6)))
    tun = service.tuning(state.mapping, "TILT minimax-U")
    sizes = service.interval_sizes(tun, service.generators(state.mapping))  # would have raised at parse
    assert all(math.isfinite(s) for s in sizes.tempered)
    pt = service.plain_text_values(state, "TILT minimax-U", "TILT")  # the ptext detempering round-trip
    assert pt[("tuning", "detempering")]  # built without raising
    gb = _grid_with_ptext(state, "TILT minimax-U")  # the exact crash site: _resolve_interval_sets
    assert service._OVER_COMPLEX_RATIO in gb.gens   # the genmap cell shows the sentinel, render survives


def test_remove_mapping_row_keeps_a_nonstandard_domain():
    # dropping a generator changes the temperament, not its domain — the re-dual must keep a
    # nonstandard subgroup, not silently revert to the standard primes. (nonstandard-superspace-5.)
    state = service.from_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")
    assert service.remove_mapping_row(state, 1).domain_basis == (2, 3, Fraction(13, 5))


def test_remove_comma_keeps_a_nonstandard_domain_at_higher_nullity():
    # the n ≥ 2 branch of the comma − re-dualed WITHOUT the domain basis, resetting 2.3.13/5 to the
    # standard primes; the n == 1 (emptied → just intonation) branch already preserved it. Both must.
    # (nonstandard-superspace-5 / canonical-defactor-7.)
    n2 = service.from_temperament_data("2.3.13/5 [⟨1 1 1]}")  # n = 2
    assert n2.n == 2
    assert service.remove_comma(n2, 0).domain_basis == (2, 3, Fraction(13, 5))  # n ≥ 2 branch
    n1 = service.from_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")  # n = 1
    assert service.remove_comma(n1, 0).domain_basis == (2, 3, Fraction(13, 5))  # emptied branch


def test_complexity_prescaler_runs_over_the_domain_basis_not_standard_primes():
    # the bare prescaler 𝑋 diagonal is each DOMAIN element's pre-norm weight, like the complexity row
    # — over 2.3.7 the third entry is log₂7, never log₂5 (a prime the domain does not contain). The
    # no-domain_basis build read log₂ of the first d standard primes and contradicted the complexity
    # row directly below it (and seeded the wrong diagonal into the solve). (nonstandard-superspace-6.)
    diag = service.complexity_prescaler(((1, 1, 3), (0, 3, -1)), "minimax-C", domain_basis=(2, 3, 7))
    assert diag == pytest.approx((1.0, math.log2(3), math.log2(7)), abs=1e-9)
    # it agrees with the complexity-over-primes row computed from the same scheme + domain
    elems = ("2/1", "3/1", "7/1")
    comps = service.interval_complexities(((1, 1, 3), (0, 3, -1)), "minimax-C", elems, domain_basis=(2, 3, 7))
    assert service.cents(diag[2]) == service.cents(comps[2])  # the two adjacent rows now match


def test_complexity_prescaler_honors_the_nonprime_based_approach():
    # under the nonprime-based approach a nonprime element is an atom (13/5 → log₂(13/5)=1.379), not
    # prime-factored (log₂65). Threaded so the displayed diagonal tracks the approach radio.
    db = (2, 3, Fraction(13, 5))
    neutral = service.complexity_prescaler(((1, 0, -1), (0, 2, 3)), "minimax-C", domain_basis=db)
    nonprime = service.complexity_prescaler(((1, 0, -1), (0, 2, 3)), "minimax-C", domain_basis=db,
                                            nonprime_approach="nonprime-based")
    assert neutral[2] == pytest.approx(math.log2(13 * 5), abs=1e-9)      # prime-factored
    assert nonprime[2] == pytest.approx(math.log2(Fraction(13, 5)), abs=1e-9)  # the atom


def test_greatest_factor_and_is_enfactored_detect_temperoids():
    # the defactoring digest (column-HNF pivot product), NOT a row GCD: it catches hidden enfactoring
    # where no single row is divisible. is_enfactored is the gate the renderer uses to dash the
    # generator/detempering rows (M·Dᵀ ≠ I for a temperoid), deliberately SEPARATE from
    # is_proper_temperament, which still accepts enfactored full-rank mappings. (canonical-defactor-4.)
    assert service.greatest_factor(((24, 38, 56),)) == 2            # ⟨24 38 56] = 2·⟨12 19 28]
    assert service.greatest_factor(((2, 2, 0), (0, 1, 4))) == 2     # hidden: no single row is divisible
    assert service.greatest_factor(((1, 1, 0), (0, 1, 4))) == 1     # meantone, defactored
    assert service.greatest_factor(((0, 1, 4),)) == 1               # a zero-column state is not enfactored
    assert service.greatest_factor(((1, 0, -4), (2, 0, -8))) == 1   # dependent rows → no well-defined factor
    assert service.is_enfactored(((24, 38, 56),)) is True
    assert service.is_enfactored(((1, 1, 0), (0, 1, 4))) is False
    # is_proper still ACCEPTS the enfactored full-rank mapping (acceptance is policy; dashing is display)
    assert service.is_proper_temperament(((2, 0, 0), (0, 1, 1))) is True
    assert service.is_enfactored(((2, 0, 0), (0, 1, 1))) is True    # but it IS flagged enfactored


def test_tuning_honors_an_explicit_empty_target_override():
    # deleting EVERY target leaves an explicit empty override (). It used to be falsy and ignored, so
    # Optimize silently froze the full default-TILT optimum behind an empty displayed list. An empty
    # override now means the underdetermined empty set — the SAME degenerate optimum the family's
    # 1-limit (1-TILT / 1-OLD) produces, so the two empty-set routes agree. (tuning-core-10.)
    m = ((1, 1, 0), (0, 1, 4))
    assert service.tuning(m, "TILT minimax-U", targets=()).generator_map \
        == service.tuning(m, "1-TILT minimax-U").generator_map        # consistent with the limit chooser
    assert service.tuning(m, "OLD minimax-U", targets=()).generator_map \
        == service.tuning(m, "1-OLD minimax-U").generator_map         # family-aware (OLD → 1-OLD)
    # None (no override) still optimizes the full set; a non-empty override still retunes to that list
    assert service.tuning(m, "TILT minimax-U", targets=None).generator_map \
        != service.tuning(m, "TILT minimax-U", targets=()).generator_map
    assert service.tuning(m, "TILT minimax-U", targets=("3/2",)).generator_map[1] == pytest.approx(701.955, abs=1e-2)
    # an all-interval scheme (target set {} = every interval) is untouched: () is not a target override there
    assert service.tuning(m, "minimax-S", targets=()).generator_map \
        == service.tuning(m, "minimax-S").generator_map


def test_plain_text_superspace_prescaling_lifts_like_the_grid():
    # under the superspace the prescaling 𝐿·v products lift to dL-tall over the TRUE primes and
    # prescale with the superspace diagonal — the grid does this; the plain-text band used to show the
    # UNLIFTED d-tall domain vectors with the wrong (domain-prime) diagonal, contradicting the grid
    # cells above it. (ebk-notation-4.)
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state, "minimax-ES", superspace=True)
    ss_pre = service.superspace_complexity_prescaler(state, "minimax-ES")   # the dL-tall diagonal
    lifted = service.lift_vectors_to_superspace(state.domain_basis, state.comma_basis)
    expected_cols = [tuple(ss_pre[i] * v[i] for i in range(len(ss_pre))) for v in lifted]
    assert pt[("prescaling", "commas")] == service._prescale_vector_list(expected_cols)
    # dL-tall (4 over the 2.3.5.13 superspace), not the unlifted d = 3 the bug showed
    assert len(expected_cols[0]) == len(ss_pre) == 4
    # the band agrees with the lifted-and-prescaled basis the grid renders for the same tile
    assert " 7.401" in pt[("prescaling", "commas")]   # 2·log₂13 — the lifted 13-coordinate, never log₂5


def test_standardize_to_prime_limit_fills_the_limit_up_to_the_largest_prime():
    state = service.standardize_to_prime_limit((2, 3, Fraction(13, 5)), ("13/5",))
    assert state.domain_basis == (2, 3, 5, 7, 11, 13)


def test_scheme_with_targets_flips_between_all_interval_and_target_based():
    assert service.is_all_interval(service.scheme_with_targets("minimax-S", "{}"))
    assert not service.is_all_interval(service.scheme_with_targets("minimax-S", "TILT"))


def test_weight_slope_variants_offers_three_with_weighting_and_only_unity_without():
    assert service.weight_slope_variants("minimax-S", True) == ("minimax-S", "minimax-U", "minimax-C")
    assert service.weight_slope_variants("minimax-S", False) == ("minimax-U",)


def test_scheme_json_round_trips_through_the_inf_optimization_power_sentinel():
    encoded = service.scheme_to_json("minimax-S")
    assert encoded["optimization_power"] == "inf"
    assert service.optimization_power(service.scheme_from_json(encoded)) == float("inf")


def test_unchanged_interval_data_dashes_the_directions_an_under_held_tuning_leaves_free():
    from rtt.app.service.projection import unchanged_interval_data
    state = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # meantone, r = 2
    tun = service.tuning(state.mapping, "minimax-S", state.domain_basis)
    data = unchanged_interval_data(state, ("2/1",), tun, "minimax-S", state.domain_basis)
    assert data.basis == ((1, 0, 0), None)            # one held direction known, one left dashed
    assert data.ratios == ("2/1", None)
    assert data.mapped == ((1, None), (0, None))       # M·U scattered back, dashed column None
    assert data.complexities[1] is None and data.complexities[0] is not None


def _barbados_state():
    return service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")


def test_superspace_generators_are_the_lifted_mappings_detempering():
    from rtt.app.service import superspace as ss
    assert ss.superspace_generators(_barbados_state()) == ("2/1", "26/3", "130/3")


def test_superspace_self_map_is_the_rank_L_identity():
    from rtt.app.service import superspace as ss
    state = _barbados_state()
    rl = ss.superspace_rank(state)
    assert ss.superspace_self_map(state) == tuple(
        tuple(1 if i == j else 0 for j in range(rl)) for i in range(rl))


def test_mapping_into_superspace_generators_sends_the_commas_to_zero():
    from rtt.app.service import superspace as ss
    state = _barbados_state()
    mapped = ss.map_vectors_into_superspace_generators(state, state.comma_basis)
    assert all(all(x == 0 for x in row) for row in mapped)


def test_projecting_superspace_generators_to_domain_recovers_the_on_domain_tuning():
    from rtt.app.service import superspace as ss
    state = _barbados_state()
    ss_optimum = ss.superspace_tuning(state, "minimax-S").generator_map
    projected = ss.project_superspace_generators_to_domain(state, ss_optimum)
    on_domain = service.tuning(state.mapping, "minimax-S", state.domain_basis).generator_map
    assert projected == pytest.approx(tuple(on_domain))


# ── service.parse rejection branches (every parser returns None, never raises, on bad input) ──
def test_int_matrix_or_none_rejects_empty_and_ragged_matrices():
    from rtt.app.service.parse import _int_matrix_or_none

    assert _int_matrix_or_none(()) is None  # no rows
    assert _int_matrix_or_none(((),)) is None  # an empty row
    assert _int_matrix_or_none(((1, 2), (3,))) is None  # rows of unequal width


def test_parse_embedding_returns_none_on_unparseable_text():
    # the parser swallows the underlying ValueError and reports "not an embedding" as None
    assert service.parse_embedding("not a matrix !!", 3, 2) is None


def test_parse_form_matrix_rejects_a_contravariant_input():
    # a form matrix is map-kind (ROW); a lone ket is contravariant, so it is not a form
    assert service.parse_form_matrix("[-4 4 -1⟩") is None
