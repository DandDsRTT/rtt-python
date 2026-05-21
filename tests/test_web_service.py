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


def test_full_rank_mapping_has_zero_comma_and_zero_nullity():
    # Just intonation: nothing tempered out. The dual is a single zero comma.
    state = service.from_mapping([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert state.comma_basis == ((0, 0, 0),)
    assert (state.d, state.r, state.n) == (3, 3, 0)


def test_standard_primes_gives_the_domain_basis_header():
    assert service.standard_primes(3) == (2, 3, 5)
    assert service.standard_primes(5) == (2, 3, 5, 7, 11)
