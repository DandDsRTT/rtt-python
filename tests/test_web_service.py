from rtt.web import service


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


def test_add_comma_appends_a_blank_comma_to_fill_in():
    st = service.from_mapping(((1, 1, 0), (0, 1, 4)))  # d=3, one comma
    added = service.add_comma(st)
    assert added.comma_basis == ((4, -4, 1), (0, 0, 0))  # a blank monzo, ready to edit
    assert added.d == 3  # domain unchanged
    assert added.n == 1  # the blank comma is dependent, so rank holds until it is filled


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


def test_mapped_target_intervals():
    mapped = service.mapped_target_intervals([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
    assert mapped == ((1, 0, -2, 2), (0, 1, 4, -3))


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


def test_tuning_values_under_top():
    import pytest

    t = service.tuning([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
    assert t.tuning_map == pytest.approx((1201.699, 1899.263, 2790.258), abs=1e-2)
    assert t.just_map == pytest.approx((1200.0, 1901.955, 2786.314), abs=1e-2)
    assert t.retuning_map == pytest.approx((1.699, -2.692, 3.944), abs=1e-2)
    assert t.target_damage == pytest.approx((1.699, 4.391, 0.547, 4.937), abs=1e-2)
    assert all(d >= 0 for d in t.target_damage)  # damage is non-negative
