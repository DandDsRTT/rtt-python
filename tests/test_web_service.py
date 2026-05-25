import math

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


def test_comma_ratios_renders_each_comma_monzo_as_a_ratio():
    # the comma basis as ratio strings, mirroring service.generators for the maps
    assert service.comma_ratios(((4, -4, 1),)) == ("80/81",)  # the syntonic comma, as-is
    assert service.comma_ratios(((4, -4, 1), (0, 0, 0))) == ("80/81", "1/1")


def test_mapped_intervals():
    mapped = service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
    assert mapped == ((1, 0, -2, 2), (0, 1, 4, -3))


def test_mapped_intervals_of_the_empty_set_is_empty_rows():
    # one (empty) generator row per mapping row, so the r x m matrix stays well-formed
    assert service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ()) == ((), ())


def test_mapped_commas_vanish():
    # every comma the temperament tempers out maps through M to zero (it vanishes)
    mapped = service.mapped_commas([[1, 1, 0], [0, 1, 4]], [[4, -4, 1]])
    assert mapped == ((0,), (0,))  # r=2 generator coords, nc=1 comma, all zero


def test_target_interval_monzos():
    # the interval-vector (monzo) form of each target over the 2.3.5 domain
    monzos = service.target_interval_monzos(("2/1", "3/2", "5/4", "6/5"), 3)
    assert monzos == ((1, 0, 0), (-1, 1, 0), (-2, 0, 1), (1, 1, -1))


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


def test_interval_sizes_project_a_set_through_the_tuning():
    import pytest

    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    s = service.interval_sizes(t, ("2/1", "3/2", "5/4", "6/5"))
    assert s.tempered == pytest.approx((1201.699, 697.564, 386.861, 310.704), abs=1e-2)
    assert s.just == pytest.approx((1200.0, 701.955, 386.314, 315.641), abs=1e-2)
    assert s.errors == pytest.approx((1.699, -4.391, 0.547, -4.937), abs=1e-2)
    assert s.damage == pytest.approx((1.699, 4.391, 0.547, 4.937), abs=1e-2)
    assert all(d >= 0 for d in s.damage)  # damage is non-negative


def test_interval_sizes_of_the_empty_set_are_empty():
    t = service.tuning([[1, 1, 0], [0, 1, 4]])
    s = service.interval_sizes(t, ())
    assert (s.tempered, s.just, s.errors, s.damage) == ((), (), (), ())


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
    # the mapping row's commas tile is the mapped comma list — every comma vanishes,
    # shown in generator coords (close })
    assert pt[("mapping", "commas")] == "[[0 0}]"
    # comma sizes are lists over the commas, like the grid's column
    assert pt[("tuning", "commas")] == f"[{cents(sizes.tempered)}]"
    assert pt[("just", "commas")] == f"[{cents(sizes.just)}]"


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
