import math
from fractions import Fraction

from rtt.web import service


def test_optimization_power_is_the_schemes_lp_norm_order():
    # the optimization power p is trait 2 of the tuning scheme: the order of the
    # Lp norm minimized over the damages. TOP (the shipped default) is a minimax
    # scheme, so p = ∞; miniRMS is least-squares (p = 2); miniaverage is p = 1.
    assert service.optimization_power("TOP") == math.inf
    assert service.optimization_power() == math.inf  # defaults to the shipped scheme (TOP)
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
    # second — read over the basis, not as prime monzos
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
    # surfaced as ratios. The shipped minimax-S (TOP) holds nothing; a held-octave
    # scheme like CTE holds the octave.
    assert service.held_intervals("TOP", 3) == ()
    assert service.held_intervals() == ()  # defaults to the shipped scheme (TOP)
    assert service.held_intervals("CTE", 3) == ("2/1",)


def test_comma_ratios_renders_each_comma_monzo_as_a_ratio():
    # the comma basis as ratio strings, mirroring service.generators for the maps
    assert service.comma_ratios(((4, -4, 1),)) == ("80/81",)  # the syntonic comma, as-is
    assert service.comma_ratios(((4, -4, 1), (0, 0, 0))) == ("80/81", "1/1")


def test_comma_ratios_over_a_nonstandard_domain_multiply_out_the_basis():
    # the comma monzo (2 -3 2) is over the basis 2.3.13/5, so its ratio is
    # 2^2·3^-3·(13/5)^2 = 676/675 (the Barbados comma) — not the prime-monzo reading 100/27
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    assert service.comma_ratios(state.comma_basis, domain_basis=state.domain_basis) == ("676/675",)


def test_mapped_intervals():
    mapped = service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
    assert mapped == ((1, 0, -2, 2), (0, 1, 4, -3))


def test_mapped_intervals_over_a_nonstandard_domain_express_in_the_basis():
    # mapping the basis elements (unit monzos over 2.3.13/5) through M reproduces M itself,
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


def test_target_interval_monzos():
    # the interval-vector (monzo) form of each target over the 2.3.5 domain
    monzos = service.target_interval_monzos(("2/1", "3/2", "5/4", "6/5"), 3)
    assert monzos == ((1, 0, 0), (-1, 1, 0), (-2, 0, 1), (1, 1, -1))


def test_target_interval_monzos_over_a_nonstandard_domain():
    # the basis elements of 2.3.13/5 are the identity monzos over that basis
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    monzos = service.target_interval_monzos(
        ("2/1", "3/1", "13/5"), state.d, domain_basis=state.domain_basis
    )
    assert monzos == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


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
    # every survivor is expressible as an integer monzo over the (nonprime) basis
    monzos = service.target_interval_monzos(targets, state.d, domain_basis=state.domain_basis)
    assert len(monzos) == len(targets)


def test_old_target_interval_set_is_the_odd_limit_diamond():
    # OLD selects the odd-limit-diamond family instead of the TILT triangle
    old = service.target_interval_set("OLD", (2, 3, 5))
    assert "5/4" in old and "6/5" in old and "8/5" in old  # diamond ratios
    assert old != service.target_interval_set("TILT", (2, 3, 5))


def test_default_target_limit_is_the_number_a_bare_family_resolves_to():
    # 2.3.5: TILT defaults to the 6-TILT, OLD to the 5-OLD (so the chooser shows a
    # real number, not "auto"); both grow with the domain
    assert service.default_target_limit("TILT", (2, 3, 5)) == 6
    assert service.default_target_limit("OLD", (2, 3, 5)) == 5
    assert service.default_target_limit("TILT", (2, 3, 5, 7)) == 10


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

    # over 2.3.13/5 a basis element is a unit monzo, so its tempered/just size must equal
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


def test_interval_complexities_norm_each_intervals_prescaled_monzo():
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]  # meantone over 2.3.5
    ratios = ("2/1", "3/2", "5/4")
    # default log-prime taxicab complexity: sum of |monzo[i]| * log2(prime_i).
    # Independent of the damage slope (slope weights damage; complexity is the norm itself).
    expected = (1.0, 2.585, 4.322)
    assert service.interval_complexities(mapping, "minimax-S", ratios) == pytest.approx(expected, abs=1e-3)
    assert service.interval_complexities(mapping, "minimax-C", ratios) == pytest.approx(expected, abs=1e-3)


def test_interval_complexities_of_the_empty_set_are_empty():
    assert service.interval_complexities([[1, 1, 0], [0, 1, 4]], "minimax-S", ()) == ()


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


def test_scheme_with_norm_switches_taxicab_and_euclidean_complexity():
    import pytest

    m = [[1, 1, 0], [0, 1, 4]]  # 2.3.5
    # taxicab (default, q=1): complexity of 3/2 = |−1|·log2 2 + |1|·log2 3 = 2.585
    assert service.interval_complexities(m, "minimax-S", ("3/2",))[0] == pytest.approx(2.585, abs=1e-3)
    eucl = service.scheme_with_norm("minimax-S", True)
    # Euclidean (q=2): sqrt(1^2 + log2(3)^2) = sqrt(1 + 2.512) = 1.874
    assert service.interval_complexities(m, eucl, ("3/2",))[0] == pytest.approx(1.874, abs=1e-3)
    # it preserves the prescaler and damage slope, only changing the norm power
    assert service.prescaler_of(eucl) == "log-prime"
    assert service.damage_weight_slope(eucl) == "simplicityWeight"


def test_is_euclidean_reports_the_complexity_norm_power():
    assert service.is_euclidean("minimax-S") is False   # taxicab (q=1)
    assert service.is_euclidean("minimax-ES") is True    # Euclidean (q=2)
    assert service.is_euclidean(service.scheme_with_norm("minimax-S", True)) is True


def test_prescaler_of_reports_the_schemes_current_prescaler():
    assert service.prescaler_of("minimax-S") == "log-prime"  # the default (Tenney)
    assert service.prescaler_of("minimax-sopfr-S") == "prime"  # Benedetti
    assert service.prescaler_of("minimax-copfr-S") == "identity"  # unweighted count
    # it round-trips with scheme_with_prescaler
    assert service.prescaler_of(service.scheme_with_prescaler("minimax-S", "prime")) == "prime"


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
    assert service.weight_slope_of("minimax-S") == "simplicity-weight"  # the shipped default (TOP)
    assert service.weight_slope_of("minimax-U") == "unity-weight"
    assert service.weight_slope_of("minimax-C") == "complexity-weight"
    # it round-trips with scheme_with_weight_slope
    assert service.weight_slope_of(service.scheme_with_weight_slope("minimax-S", "unity-weight")) == "unity-weight"


def test_scheme_with_complexity_sets_the_prescaler_norm_and_size_factor():
    # the predefined-complexities master chooser sets the whole complexity shape at once:
    # the prescaler (log-prime/prime/identity) and the norm power (taxicab/Euclidean).
    copfr = service.scheme_with_complexity("minimax-S", "copfr")  # unweighted count
    assert service.prescaler_of(copfr) == "identity" and service.is_euclidean(copfr) is False
    assert service.prescaler_of(service.scheme_with_complexity("minimax-S", "sopfr")) == "prime"  # Benedetti
    lpe = service.scheme_with_complexity("minimax-S", "lp-E")  # Tenney-Euclidean
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
    assert service.complexity_name_of("minimax-ES") == "lp-E"  # Tenney-Euclidean
    assert service.complexity_name_of("minimax-copfr-S") == "copfr"
    assert service.complexity_name_of("minimax-sopfr-S") == "sopfr"
    assert service.complexity_name_of("minimax-lils-S") == "lils"
    assert service.complexity_name_of("minimax-lols-S") == "lols"  # lils + held octave
    # it round-trips with scheme_with_complexity
    assert service.complexity_name_of(service.scheme_with_complexity("minimax-S", "sopfr-E")) == "sopfr-E"
    # an lp shape that also holds the octave is no named complexity (lp clears the octave): custom
    assert service.complexity_name_of("held-octave minimax-S") == "custom"


def test_scheme_with_diminuator_toggles_the_size_factor_between_lp_and_lils():
    # the box-𝐋 "ignore diminuator" checkbox (the size-factor trait 5c): ignoring the diminuator
    # (the lesser of num/den) replaces it with the numinator — the integer-limit/lils behavior.
    assert service.diminuator_ignored("minimax-S") is False  # lp (default) uses the diminuator
    ignored = service.scheme_with_diminuator("minimax-S", True)  # lp -> lils
    assert service.diminuator_ignored(ignored) is True
    assert service.complexity_name_of(ignored) == "lils"
    # un-ignoring returns lils -> lp
    kept = service.scheme_with_diminuator("minimax-lils-S", False)
    assert service.diminuator_ignored(kept) is False and service.complexity_name_of(kept) == "lp"
    # the prescaler, norm and damage slope ride along unchanged
    on_sopfr = service.scheme_with_diminuator("minimax-sopfr-ES", True)
    assert service.prescaler_of(on_sopfr) == "prime" and service.is_euclidean(on_sopfr) is True


def test_complexity_prescaler_is_the_diagonal_of_per_prime_weights():
    import pytest

    mapping = [[1, 1, 0], [0, 1, 4]]  # 2.3.5 domain
    # the default log-prime prescaler L = diag(log2(prime))
    assert service.complexity_prescaler(mapping, "minimax-S") == pytest.approx((1.0, 1.585, 2.322), abs=1e-3)
    # sopfr (Benedetti) prescaler weights each prime by the prime itself
    assert service.complexity_prescaler(mapping, "minimax-sopfr-S") == pytest.approx((2.0, 3.0, 5.0), abs=1e-3)


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


def test_plain_text_interval_vectors_are_monzo_lists():
    # the interval-vectors row shows each basis as a list of monzos (close ⟩),
    # wrapped in an outer [ … ]
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert pt[("vectors", "targets")].startswith("[[1 0 0⟩ [0 1 0⟩ [-1 1 0⟩")  # target monzos
    assert ("vectors", "primes") not in pt  # the domain-basis identity is deferred to identity_objects


def test_plain_text_mapped_list_is_a_list_of_generator_coord_vectors():
    # each target mapped into generator coords becomes one [ … } vector (the } marks
    # generator coordinates), the whole set wrapped in an outer [ … ]
    pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
    assert pt[("mapping", "targets")] == (
        "[[1 0} [1 1} [0 1} [1 -1} [-1 4} [-1 3} [-2 4} [2 -3}]"
    )


def test_plain_text_tuning_rows_use_map_and_list_brackets_at_grid_precision():
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state)
    targets = service.target_interval_set("TILT", service.standard_primes(state.d))
    tun = service.tuning(state.mapping)
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

    # the comma basis (the editable monzo matrix) lives in the interval-vectors row,
    # a list of monzos wrapped in an outer [ … ]
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

    # the held interval basis lives in the interval-vectors row (monzos, close ⟩)
    assert pt[("vectors", "held")] == "[[-1 1 0⟩]"
    # mapped into generator coords (close }) — the fifth is one generator
    assert pt[("mapping", "held")] == "[[0 1}]"
    # the held sizes are lists over the held intervals, matching the held-constrained grid
    assert pt[("tuning", "held")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "held")] == f"[{cents(sizes.just)}]"
    assert pt[("retune", "held")] == f"[{cents(sizes.errors)}]"
    assert abs(float(pt[("retune", "held")].strip("[]"))) < 1e-3  # held just ⇒ no error
    # no held entries when none are held
    assert ("vectors", "held") not in service.plain_text_values(state)


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
    # the size rows are ordinary lists over the intervals, like the targets column
    assert pt[("tuning", "interest")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "interest")] == f"[{cents(sizes.just)}]"
    assert pt[("retune", "interest")] == f"[{cents(sizes.errors)}]"
    assert pt[("complexity", "interest")].startswith("[") and pt[("complexity", "interest")].endswith("]")
    # prescaling mirrors its (still-matrix) grid tile: a wrapped ket list, like the targets
    assert pt[("prescaling", "interest")].startswith("[[") and pt[("prescaling", "interest")].endswith("⟩]")
    # no interest entries when the column is empty
    assert ("vectors", "interest") not in service.plain_text_values(state)


def test_plain_text_weighting_rows_mirror_the_grid():
    state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
    pt = service.plain_text_values(state)
    # complexity: a covector ⟨ … ] over the primes (their log-prime complexities), a
    # list [ … ] over the commas (the comma's complexity is its prescaled monzo's norm)
    assert pt[("complexity", "primes")] == "⟨1.000 1.585 2.322]"
    assert pt[("complexity", "commas")] == "[12.662]"
    assert pt[("complexity", "targets")].startswith("[") and pt[("complexity", "targets")].endswith("]")
    # the per-target weight list (simplicity-weighted by default → 1/complexity)
    assert pt[("weight", "targets")].startswith("[") and pt[("weight", "targets")].endswith("]")
    # the prescaling row is L applied to each vector set, a ket list: L·[4,-4,1] = [4,-6.34,2.322]
    assert pt[("prescaling", "commas")] == "[[4.000 -6.340 2.322⟩]"


def test_plain_text_over_a_nonstandard_domain_uses_the_basis():
    # the plain-text view of a 2.3.13/5 temperament names the domain basis in dot
    # notation and tunes over its elements (not the standard primes)
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    pt = service.plain_text_values(state)
    assert pt[("quantities", "primes")] == "2.3.13/5"
    assert pt[("vectors", "commas")] == "[[2 -3 2⟩]"  # the comma monzo, basis-relative
    tun = service.tuning(state.mapping, domain_basis=state.domain_basis)
    cents = " ".join(f"{v:.3f}" for v in tun.tuning_map)
    assert pt[("tuning", "primes")] == f"⟨{cents}]"


def test_comma_basis_pending_text_splits_the_draft_for_two_tone_display():
    # while a comma is being added the comma-basis string is shown two-tone: the
    # committed commas (and the wrapping brackets) stay black, the draft vector reddens.
    # The helper returns (black prefix, red draft ket, black suffix); the draft shows the
    # entered components only (blanks omitted), e.g. (4, _, 1) -> "[4 1⟩".
    prefix, draft, suffix = service.comma_basis_pending_text(((4, -4, 1),), [4, None, 1])
    assert (prefix, draft, suffix) == ("[[4 -4 1⟩ ", "[4 1⟩", "]")
    assert prefix + draft + suffix == "[[4 -4 1⟩ [4 1⟩]"  # the full string, reassembled
    # a brand-new (all-blank) draft is just an empty ket
    assert service.comma_basis_pending_text(((4, -4, 1),), [None, None, None])[1] == "[⟩"
    # a second committed comma extends the black prefix; the draft is still its own ket
    assert service.comma_basis_pending_text(((4, -4, 1), (4, -5, 1)), [None, None, None])[0] == "[[4 -4 1⟩ [4 -5 1⟩ "


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


def test_tuning_exposes_diamond_generator_ranges():
    import pytest

    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    # Octave held pure pins the period generator; the fifth gets a real range.
    assert t.tradeoff_generator_range[0] == pytest.approx((1200.0, 1200.0), abs=1e-6)
    assert t.tradeoff_generator_range[1] == pytest.approx((694.786, 701.955), abs=1e-2)
    assert t.monotone_generator_range[1] == pytest.approx((685.714, 720.0), abs=1e-2)
