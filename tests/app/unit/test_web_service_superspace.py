import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format
from _service_support import _barbados_state


class TestSuperspaceBasis:
    def test_domain_has_nonprimes_flags_any_nonprime_element(self):
        assert service.domain_has_nonprimes((2, 3, 5)) is False, "The mode-radio (prime-based / nonprime-based / neutral) only matters when the domain # has nonprime elements: a reordering of primes still has the prime-only structure, so # this is a finer test than `is_standard_domain` (which is True only for canonical-order # prime limits). BARBADOS over 2.3.13/5 has the nonprime 13/5; 2.9.5 has the composite 9"
        assert service.domain_has_nonprimes((3, 2, 5)) is False
        assert service.domain_has_nonprimes((2, 5, 7)) is False
        assert service.domain_has_nonprimes((2, 3, Fraction(7, 1))) is False
        assert service.domain_has_nonprimes((2, 3, Fraction(13, 5))) is True
        assert service.domain_has_nonprimes((2, 9, 5)) is True

    def test_superspace_primes_collects_every_prime_appearing_in_the_basis(self):
        assert service.superspace_primes((2, 3, 5)) == (2, 3, 5)
        assert service.superspace_primes((3, 2, 5)) == (2, 3, 5)
        assert service.superspace_primes((2, 3, Fraction(13, 5))) == (2, 3, 5, 13)
        assert service.superspace_primes((2, 9, 5)) == (2, 3, 5)

    def test_superspace_dimension_is_the_count_of_superspace_primes(self):
        assert service.superspace_dimension((2, 3, 5)) == 3
        assert service.superspace_dimension((2, 3, Fraction(13, 5))) == 4
        assert service.superspace_dimension((2, 9, 5)) == 3

    def test_basis_in_superspace_writes_each_element_as_a_vector_over_the_superspace_primes(self):
        barbados = service.basis_in_superspace((2, 3, Fraction(13, 5)))
        assert barbados == ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 1))
        assert service.basis_in_superspace((2, 3, 5)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        assert service.basis_in_superspace((2, 9, 5)) == ((1, 0, 0), (0, 2, 0), (0, 0, 1))


class TestSuperspaceMapping:
    def test_superspace_complexity_prescaler_is_log_prime_over_the_superspace_primes(self):
        s = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.superspace_complexity_prescaler(s) == pytest.approx(
            (1.0, math.log2(3), math.log2(5), math.log2(13))
        )
        s2 = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]}")
        assert service.superspace_complexity_prescaler(s2) == pytest.approx(
            (1.0, math.log2(3), math.log2(7), math.log2(11))
        )

    def test_superspace_mapping_re_expresses_the_temperament_over_the_superspace_primes(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        ml = service.superspace_mapping(state)
        assert len(ml) == 3 and all(len(row) == 4 for row in ml)
        assert all(isinstance(x, int) for row in ml for x in row)
        embedded_comma = (2, -3, -2, 2)
        for row in ml:
            assert sum(a * b for a, b in zip(row, embedded_comma)) == 0

    def test_superspace_mapping_returns_the_canonical_mapping_when_already_prime_only(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.superspace_mapping(state) == service.canonical_mapping(state.mapping)

    def test_superspace_rank_is_r_plus_the_extra_primes(self):
        barbados = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.superspace_rank(barbados) == 3
        meantone = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.superspace_rank(meantone) == 2

    def test_superspace_just_mapping_is_the_dL_identity(self):
        assert service.superspace_just_mapping((2, 3, 5, 13)) == (
            (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)
        )
        assert service.superspace_just_mapping((2, 3, 5)) == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class TestSuperspaceTuning:
    def test_superspace_tuning_runs_over_the_superspace_primes(self):
        import pytest

        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        tuning_map = service.superspace_tuning(state, "minimax-S")
        assert len(tuning_map.generator_map) == 3
        assert len(tuning_map.tuning_map) == 4 and len(tuning_map.just_map) == 4
        assert tuning_map.just_map == pytest.approx(
            (1200.0, 1200.0 * math.log2(3), 1200.0 * math.log2(5), 1200.0 * math.log2(13)), abs=1e-6
        )
        assert tuning_map.retuning_map == pytest.approx(
            tuple(t - j for t, j in zip(tuning_map.tuning_map, tuning_map.just_map)), abs=1e-9
        )

    def test_superspace_tuning_projection_reduces_to_the_on_domain_projection(self):
        mt = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        held = ("2", "5/4")
        assert service.superspace_tuning_projection(mt, held) == service.tuning_projection(mt, held)

    def test_superspace_tuning_projection_is_the_identity_for_just_intonation(self):
        triv = service.from_temperament_data("2.3.13/5 [⟨1 0 0] ⟨0 1 0] ⟨0 0 1]}")
        pl = service.superspace_tuning_projection(triv)
        assert pl == (("1", "0", "0", "0"), ("0", "1", "0", "0"),
                      ("0", "0", "1", "0"), ("0", "0", "0", "1"))

    def test_superspace_tuning_projection_is_a_dL_idempotent_holding_the_lifted_held(self):
        import sympy as sp
        barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        pl = service.superspace_tuning_projection(barb, ("2", "13/5"))
        assert pl is not None
        assert len(pl) == 4 and all(len(row) == 4 for row in pl)
        m = sp.Matrix([[sp.Rational(x) for x in row] for row in pl])
        assert m * m == m
        for held in ((1, 0, 0, 0), (0, 0, -1, 1)):
            assert list(m * sp.Matrix(4, 1, list(held))) == list(held)
        assert list(m * sp.Matrix(4, 1, [2, -3, -2, 2])) == [0, 0, 0, 0]

    def test_superspace_tuning_embedding_is_the_dL_by_rL_factor_of_P_L(self):
        import sympy as sp
        barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        left_functions = service.superspace_tuning_embedding(barb, ("2", "13/5"))
        assert len(left_functions) == 4 and all(len(row) == 3 for row in left_functions)
        assert service.superspace_tuning_embedding(barb, ("2",)) is None
        ml = service.superspace_mapping(barb)
        g = sp.Matrix([[sp.Rational(x) for x in row] for row in left_functions])
        m = sp.Matrix([list(r) for r in ml])
        pl = sp.Matrix([[sp.Rational(x) for x in row] for row in service.superspace_tuning_projection(barb, ("2", "13/5"))])
        assert g * m == pl

    def test_superspace_tuning_projection_is_none_when_under_held(self):
        barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.superspace_tuning_projection(barb, ("2",)) is None
        assert service.tuning_projection(barb, ("2",)) is None


class TestSuperspaceProjection:
    def test_superspace_projection_matrix_rationals_matches_the_display_strings(self):
        barb = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        rat = service.superspace_projection_matrix_rationals(barb, ("2", "13/5"))
        disp = service.superspace_tuning_projection(barb, ("2", "13/5"))
        assert tuple(tuple(str(x) for x in row) for row in rat) == disp
        assert service.superspace_projection_matrix_rationals(barb, ("2",)) is None

    def test_superspace_generator_embedding_and_projection_for_barbados(self):
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

    def test_superspace_projection_satisfies_the_mockup_identities(self):
        from rtt.library.matrix_utils import matrix_multiply, transpose
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        p = service.projection_matrix_rationals(state, ("2/1", "3/1"))
        g_ls = service.superspace_generator_embedding(state, ("2/1", "3/1"))
        p_ls = service.superspace_prime_projection(state, ("2/1", "3/1"))
        msl = service.mapping_to_superspace_generators(state)
        bl = service.basis_in_superspace(state.domain_basis)
        assert matrix_multiply(g_ls, msl) == p
        assert matrix_multiply(p_ls, transpose(bl)) == p

    def test_superspace_projection_is_none_when_under_held(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.superspace_generator_embedding_display(state) is None
        assert service.superspace_prime_projection_display(state) is None


class TestSuperspaceGenerators:
    def test_superspace_generators_are_the_lifted_mappings_detempering(self):
        from rtt.app.service import superspace as superspace
        assert superspace.superspace_generators(_barbados_state()) == ("2/1", "26/3", "130/3")

    def test_superspace_self_map_is_the_rank_L_identity(self):
        from rtt.app.service import superspace as superspace
        state = _barbados_state()
        rl = superspace.superspace_rank(state)
        assert superspace.superspace_self_map(state) == tuple(
            tuple(1 if i == j else 0 for j in range(rl)) for i in range(rl))

    def test_mapping_into_superspace_generators_sends_the_commas_to_zero(self):
        from rtt.app.service import superspace as superspace
        state = _barbados_state()
        mapped = superspace.map_vectors_into_superspace_generators(state, state.comma_basis)
        assert all(all(x == 0 for x in row) for row in mapped)

    def test_projecting_superspace_generators_to_domain_recovers_the_on_domain_tuning(self):
        from rtt.app.service import superspace as superspace
        state = _barbados_state()
        superspace_optimum = superspace.superspace_tuning(state, "minimax-S").generator_map
        projected = superspace.project_superspace_generators_to_domain(state, superspace_optimum)
        on_domain = service.tuning(state.mapping, "minimax-S", state.domain_basis).generator_map
        assert projected == pytest.approx(tuple(on_domain))
