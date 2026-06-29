from fractions import Fraction

from rtt.library.matrix_utils import matrix_multiply
from rtt.library.superspace import (
    apply_matrix_to_vectors,
    compose_mapping_with_embedding,
    extend_to_full_image_rank,
    greedy_independent_rows,
    least_squares_left_factor,
    lift_vectors,
)

BARBADOS_BL = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
BARBADOS_ML = ((1, 0, 0, -1), (0, 2, 0, 3), (0, 0, 1, 1))

QUARTER_COMMA_P = (
    (1, 1, 0),
    (0, 0, 0),
    (0, Fraction(1, 4), 1),
)


class TestSuperspace:
    def test_apply_matrix_to_vectors_applies_the_matrix_to_each_vector(self):
        """P·v for each d-tall vector. Projecting meantone's generator detempering D through
        quarter-comma's P gives the embedding G (P·D = GMD = G, since M·D = I): the second
        generator projects to 5^(1/4) = [0 0 1/4]."""
        detempering = ((1, 0, 0), (-1, 1, 0))
        assert apply_matrix_to_vectors(QUARTER_COMMA_P, detempering) == (
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(1, 4)),
        )

    def test_apply_matrix_to_vectors_holds_the_projections_held_intervals_fixed(self):
        """P·H = H: the held intervals are the eigenvalue-1 directions, unchanged by the
        projection — quarter-comma's 2/1 and 5/4 pass through untouched."""
        held = ((1, 0, 0), (-2, 0, 1))
        assert apply_matrix_to_vectors(QUARTER_COMMA_P, held) == (
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(-2), Fraction(0), Fraction(1)),
        )

    def test_apply_matrix_to_vectors_degenerate_shapes(self):
        """No vectors yields (); an empty matrix sends every vector to the empty tuple."""
        assert apply_matrix_to_vectors(QUARTER_COMMA_P, ()) == ()
        assert apply_matrix_to_vectors((), ((1, 0, 0), (0, 1, 0))) == ((), ())

    def test_lift_vectors_re_expresses_domain_vectors_over_the_superspace_primes(self):
        """B_L·v per row: BARBADOS' comma (2,-3,2) over 2.3.13/5 lifts to 676/675 = (2,-3,-2,2)
        over (2, 3, 5, 13) — the 13/5 component spreads across the 5 and 13 columns."""
        assert lift_vectors(BARBADOS_BL, ((2, -3, 2),)) == ((2, -3, -2, 2),)
        identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        assert lift_vectors(identity, ((4, -4, 1), (-1, 1, 0))) == ((4, -4, 1), (-1, 1, 0))

    def test_lift_vectors_degenerate_shapes(self):
        """An empty embedding lifts every vector to the empty tuple; no vectors yields ()."""
        assert lift_vectors((), ((1, 0), (0, 1))) == ((), ())
        assert lift_vectors(BARBADOS_BL, ()) == ()

    def test_compose_mapping_with_embedding_sends_domain_elements_to_superspace_generators(self):
        """M_L·B_Lᵀ is the rL × d composite M_s→L: BARBADOS' domain elements straight to their
        superspace-generator coordinates."""
        assert compose_mapping_with_embedding(BARBADOS_ML, BARBADOS_BL) == (
            (1, 0, -1),
            (0, 2, 3),
            (0, 0, 0),
        )

    def test_compose_mapping_with_embedding_agrees_with_lift_then_map(self):
        """The composite acts on domain vectors exactly as lifting then mapping: M_s→L·v equals
        M_L·(B_L·v) for every domain vector v."""
        msl = compose_mapping_with_embedding(BARBADOS_ML, BARBADOS_BL)
        vectors = ((2, -3, 2), (1, 0, 0), (0, 1, -1))
        assert apply_matrix_to_vectors(msl, vectors) == apply_matrix_to_vectors(
            BARBADOS_ML, lift_vectors(BARBADOS_BL, vectors)
        )

    def test_compose_mapping_with_embedding_is_empty_when_either_factor_is(self):
        assert compose_mapping_with_embedding((), BARBADOS_BL) == ()
        assert compose_mapping_with_embedding(BARBADOS_ML, ()) == ()

    def test_greedy_independent_rows_drops_dependent_rows_preserving_order(self):
        """Each row is kept iff independent of those already kept — (2,0,0) ∥ (1,0,0) is
        dropped, and the earlier row wins."""
        assert greedy_independent_rows(((1, 0, 0), (2, 0, 0), (0, 0, 1)), 3) == (
            (1, 0, 0),
            (0, 0, 1),
        )

    def test_greedy_independent_rows_caps_at_the_limit(self):
        """No more than `limit` rows are kept, reading left to right; a zero limit keeps none."""
        rows = ((1, 0, 0), (0, 0, 1), (0, 1, 0))
        assert greedy_independent_rows(rows, 2) == ((1, 0, 0), (0, 0, 1))
        assert greedy_independent_rows(rows, 0) == ()

    def test_extend_to_full_image_rank_fills_with_the_lowest_units_that_extend_the_image(self):
        """BARBADOS' lifted held basis {2/1, 13/5} spans only 2 of M_L's rL = 3 image
        dimensions; the fill skips e₀ and e₁ (their images already lie in the held span) and
        appends e₂ — the lowest superspace prime extending the image."""
        lifted_held = ((1, 0, 0, 0), (0, 0, -1, 1))
        assert extend_to_full_image_rank(BARBADOS_ML, lifted_held) == (
            (1, 0, 0, 0),
            (0, 0, -1, 1),
            (0, 0, 1, 0),
        )

    def test_extend_to_full_image_rank_keeps_a_full_mandatory_set_as_given(self):
        """rL mandatory vectors come back unchanged — even a degenerate set (the second vector
        here is meantone's comma, killed by the mapping): the mandatory vectors are kept
        unconditionally, and the caller's downstream inversion is what detects degeneracy."""
        meantone = ((1, 1, 0), (0, 1, 4))
        assert extend_to_full_image_rank(meantone, ((1, 0, 0), (4, -4, 1))) == (
            (1, 0, 0),
            (4, -4, 1),
        )

    def test_extend_to_full_image_rank_is_none_when_full_image_rank_is_unreachable(self):
        """A mapping with row rank below rL leaves no unit vector able to complete the image,
        so the fill comes up short and yields None."""
        assert extend_to_full_image_rank(((1, 0), (2, 0)), ()) is None

    def test_least_squares_left_factor_recovers_the_superspace_generator_embedding(self):
        """G_L→s = P·(M_s→L)⁺ for BARBADOS holding {2/1, 3/1}: the least-squares left factor
        through the rank-deficient M_s→L (rank 2 of 3 rows), where a plain right-inverse would
        not exist. Fraction entries, and a genuine factor: G_L→s·M_s→L = P."""
        p = (
            (Fraction(1), Fraction(0), Fraction(-1)),
            (Fraction(0), Fraction(1), Fraction(3, 2)),
            (Fraction(0), Fraction(0), Fraction(0)),
        )
        msl = ((1, 0, -1), (0, 2, 3), (0, 0, 0))
        g_ls = least_squares_left_factor(p, msl)
        assert g_ls == (
            (Fraction(1), Fraction(0), Fraction(0)),
            (Fraction(0), Fraction(1, 2), Fraction(0)),
            (Fraction(0), Fraction(0), Fraction(0)),
        )
        assert matrix_multiply(g_ls, msl) == p

    def test_least_squares_left_factor_inverts_an_invertible_right_factor_exactly(self):
        """Against an invertible right factor the least-squares factor IS the exact one:
        X·(2I) = I gives X = I/2."""
        assert least_squares_left_factor(((1, 0), (0, 1)), ((2, 0), (0, 2))) == (
            (Fraction(1, 2), Fraction(0)),
            (Fraction(0), Fraction(1, 2)),
        )
