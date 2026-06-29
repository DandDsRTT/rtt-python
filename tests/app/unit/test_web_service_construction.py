import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format


class TestFromMapping:
    def test_from_mapping_computes_canonical_comma_basis(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert state.mapping == ((1, 1, 0), (0, 1, 4))
        assert state.comma_basis == ((4, -4, 1),)
        assert (state.d, state.r, state.n) == (3, 2, 1)

    def test_from_mapping_records_standard_prime_domain_basis(self):
        state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert state.domain_basis == (2, 3, 5)

    def test_from_mapping_preserves_noncanonical_input(self):
        state = service.from_mapping([[1, 1, 0], [1, 2, 4]])
        assert state.mapping == ((1, 1, 0), (1, 2, 4))
        assert state.comma_basis == ((4, -4, 1),)

    def test_from_comma_basis_computes_mapping_and_preserves_input(self):
        state = service.from_comma_basis([[-4, 4, -1]])
        assert state.comma_basis == ((-4, 4, -1),)
        assert state.mapping == ((1, 0, -4), (0, 1, 4))
        assert (state.d, state.r, state.n) == (3, 2, 1)

    def test_full_rank_mapping_has_zero_comma_and_zero_nullity(self):
        state = service.from_mapping([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        assert state.comma_basis == ((0, 0, 0),)
        assert (state.d, state.r, state.n) == (3, 3, 0)


class TestFromTemperamentData:
    def test_from_temperament_data_reads_a_nonstandard_domain_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert state.domain_basis == (2, 3, Fraction(13, 5))
        assert state.mapping == ((1, 2, 2), (0, -2, -3))
        assert (state.d, state.r, state.n) == (3, 2, 1)

    def test_from_temperament_data_reads_a_standard_temperament_too(self):
        state = service.from_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
        assert state.domain_basis == (2, 3, 5)
        assert state.mapping == ((1, 1, 0), (0, 1, 4))

    def test_from_temperament_data_reads_a_comma_basis_too(self):
        state = service.from_temperament_data("[-4 4 -1⟩")
        assert (state.d, state.r, state.n) == (3, 2, 1)
        assert state.comma_basis == ((-4, 4, -1),)


class TestCanonicalForms:
    def test_canonical_mapping_defactors_and_hnfs(self):
        assert service.canonical_mapping([[1, 1, 0], [0, 1, 4]]) == ((1, 0, -4), (0, 1, 4))
        assert service.canonical_mapping([[1, 0, -4], [0, 1, 4]]) == ((1, 0, -4), (0, 1, 4))

    def test_form_matrix_is_the_generator_change_of_basis_to_canonical(self):
        assert service.form_matrix([[1, 1, 0], [0, 1, 4]]) == ((1, -1), (0, 1))
        assert service.form_matrix([[1, 0, -4], [0, 1, 4]]) == ((1, 0), (0, 1))

    def test_canonical_comma_basis_defactors_and_canonicalizes(self):
        assert service.canonical_comma_basis([[-8, 8, -2]]) == ((4, -4, 1),)
        assert service.canonical_comma_basis([[4, -4, 1]]) == ((4, -4, 1),)

    def test_parse_form_matrix_rejects_a_contravariant_input(self):
        assert service.parse_form_matrix("[-4 4 -1⟩") is None, "a form matrix is map-kind (ROW); a lone ket is contravariant, so it is not a form"


class TestDomainExpandShrink:
    def test_shrink_domain_falls_back_to_just_intonation_when_no_comma_survives(self):
        from rtt.app.service.state import from_comma_basis, shrink_domain

        shrunk = shrink_domain(from_comma_basis(((0, 0, 1),)))
        assert (shrunk.d, shrunk.n) == (2, 0)

    def test_expand_domain_appends_prime_and_redualizes(self):
        state = service.expand_domain(service.from_comma_basis([[-4, 4, -1]]))
        assert state.comma_basis == ((-4, 4, -1, 0),)
        assert (state.d, state.r, state.n) == (4, 3, 1)
        assert all(
            sum(m * c for m, c in zip(row, (-4, 4, -1, 0))) == 0 for row in state.mapping
        )

    def test_shrink_domain_is_inverse_of_expand(self):
        meantone = service.from_comma_basis([[-4, 4, -1]])
        state = service.shrink_domain(service.expand_domain(meantone))
        assert state.comma_basis == ((-4, 4, -1),)
        assert state.mapping == ((1, 0, -4), (0, 1, 4))
        assert (state.d, state.r, state.n) == (3, 2, 1)

    def test_shrinking_keeps_the_comma_count_equal_to_the_nullity(self):
        twelve = service.from_mapping(((12, 19, 28),))
        one = service.shrink_domain(service.shrink_domain(twelve))
        assert (one.d, one.r, one.n) == (1, 0, 1) and one.d == one.r + one.n
        assert len(one.comma_basis) == one.n == 1, "one comma, not the two it would naively keep"

    def test_standard_primes_gives_the_domain_basis_header(self):
        assert service.standard_primes(3) == (2, 3, 5)
        assert service.standard_primes(5) == (2, 3, 5, 7, 11)


class TestCommaEdits:
    def test_remove_comma_drops_the_last_comma_and_reranks(self):
        st = service.from_comma_basis(((4, -4, 1), (1, 0, 0)))
        assert (st.d, st.r, st.n) == (3, 1, 2)
        removed = service.remove_comma(st)
        assert removed.comma_basis == ((4, -4, 1),)
        assert (removed.d, removed.r, removed.n) == (3, 2, 1)

    def test_remove_comma_can_drop_an_arbitrary_index(self):
        st = service.from_comma_basis(((4, -4, 1), (1, 0, 0)))
        dropped_first = service.remove_comma(st, 0)
        assert dropped_first.comma_basis == service.from_comma_basis(((1, 0, 0),)).comma_basis
        assert (dropped_first.d, dropped_first.r, dropped_first.n) == (3, 2, 1)
        assert service.remove_comma(st).comma_basis == ((4, -4, 1),), "default still drops the last"

    def test_remove_comma_un_tempers_the_sole_comma_to_just_intonation(self):
        meantone = service.from_comma_basis(((4, -4, 1),))
        ji = service.remove_comma(meantone)
        assert (ji.d, ji.r, ji.n) == (3, 3, 0)
        assert ji.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        assert ji.comma_basis == ((0, 0, 0),)

    def test_un_tempering_the_last_comma_keeps_a_nonstandard_domain(self):
        archytas = service.from_comma_basis(((6, -2, -1),), domain_basis=(2, 3, 7))
        ji = service.remove_comma(archytas)
        assert ji.domain_basis == (2, 3, 7)
        assert (ji.d, ji.r, ji.n) == (3, 3, 0) and ji.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        assert service.add_mapping_row(archytas) == ji

    def test_add_comma_to_recombines_the_basis_holding_the_temperament(self):
        twelve = service.from_mapping(((12, 19, 28),))
        combined = service.add_comma_to(twelve, 0, 1)
        assert combined.comma_basis[1] == tuple(a + b for a, b in zip(twelve.comma_basis[1], twelve.comma_basis[0]))
        assert combined.comma_basis[0] == twelve.comma_basis[0]
        assert combined.mapping == twelve.mapping
        assert (combined.d, combined.r, combined.n) == (twelve.d, twelve.r, twelve.n)

    def test_remove_comma_keeps_a_nonstandard_domain_at_higher_nullity(self):
        n2 = service.from_temperament_data("2.3.13/5 [⟨1 1 1]}")
        assert n2.n == 2
        assert service.remove_comma(n2, 0).domain_basis == (2, 3, Fraction(13, 5))
        n1 = service.from_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")
        assert service.remove_comma(n1, 0).domain_basis == (2, 3, Fraction(13, 5))


class TestMappingRowEdits:
    def test_remove_mapping_row_drops_a_generator_holding_dimensionality(self):
        st = service.remove_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))), 0)
        assert st.mapping == ((0, 1, 4),)
        assert (st.d, st.r, st.n) == (3, 1, 2)

    def test_add_mapping_row_un_tempers_a_comma_raising_rank(self):
        st = service.add_mapping_row(service.from_mapping(((1, 1, 0), (0, 1, 4))))
        assert st.mapping == ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "canonical full rank (JI), not a raw comma row"
        assert (st.d, st.r, st.n) == (3, 3, 0)
        assert service.generators(st.mapping) == ("2/1", "3/1", "5/1"), "simple generators, not vast ratios"

    def test_add_mapping_row_to_combines_generators_holding_the_temperament(self):
        meantone = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        combined = service.add_mapping_row_to(meantone, 0, 1)
        assert combined.mapping == ((1, 1, 0), (1, 2, 4))
        assert combined.comma_basis == meantone.comma_basis
        assert (combined.d, combined.r, combined.n) == (meantone.d, meantone.r, meantone.n)
        assert service.generators(combined.mapping) == ("4/3", "3/2")

    def test_remove_mapping_row_keeps_a_nonstandard_domain(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}")
        assert service.remove_mapping_row(state, 1).domain_basis == (2, 3, Fraction(13, 5))


class TestDomainElementEdits:
    def test_parse_domain_element_accepts_positive_rationals_and_rejects_junk(self):
        assert service.parse_domain_element("7") == 7
        assert service.parse_domain_element("13/5") == Fraction(13, 5)
        assert service.parse_domain_element("9/3") == 3
        for junk in ("abc", "", "1", "0", "-3", "5/0"):
            assert service.parse_domain_element(junk) is None

    def test_is_independent_domain_basis_rejects_the_empty_basis(self):
        assert service.is_independent_domain_basis(()) is False

    def test_is_independent_domain_basis_rejects_dependent_elements(self):
        assert service.is_independent_domain_basis((2, 3, 5))
        assert service.is_independent_domain_basis((2, 3, Fraction(13, 5)))
        assert not service.is_independent_domain_basis((2, 3, 9))
        assert not service.is_independent_domain_basis((2, 4))

    def test_add_domain_element_holds_the_new_element_just(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        added = service.add_domain_element(state, service.parse_domain_element("7"))
        assert added.domain_basis == (2, 3, 5, 7)
        assert added.d == state.d + 1 and added.r == state.r + 1 and added.n == state.n
        assert added.mapping == ((1, 1, 0, 0), (0, 1, 4, 0), (0, 0, 0, 1))
        tuning_map = service.tuning(added.mapping, service.DEFAULT_TUNING_SCHEME, added.domain_basis)
        assert tuning_map.tuning_map[3] == pytest.approx(1200 * math.log2(7), abs=1e-6)

    def test_add_domain_element_accepts_a_nonprime(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        added = service.add_domain_element(state, service.parse_domain_element("13/5"))
        assert added.domain_basis == (2, 3, 5, Fraction(13, 5))
        assert added.d == 4 and added.r == 3 and added.n == state.n

    def test_can_add_domain_element_guards_validity_and_independence(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.can_add_domain_element(state, "7")
        assert service.can_add_domain_element(state, "13/5")
        assert not service.can_add_domain_element(state, "9")
        assert not service.can_add_domain_element(state, "1")
        assert not service.can_add_domain_element(state, "abc"), "not a rational"

    def test_set_domain_element_is_a_pure_relabel(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        relabelled = service.set_domain_element(state, 2, service.parse_domain_element("13/5"))
        assert relabelled.domain_basis == (2, 3, Fraction(13, 5))
        assert relabelled.mapping == state.mapping

    def test_can_set_domain_element_rejects_a_dependent_relabel(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        assert service.can_set_domain_element(state, 2, "13/5")
        assert not service.can_set_domain_element(state, 2, "9")
        assert not service.can_set_domain_element(state, 2, "8")
        assert not service.can_set_domain_element(state, 2, "1")

    def test_remove_domain_element_drops_the_named_element_keeping_the_basis_nonstandard(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.remove_domain_element(state, 0).domain_basis == (3, Fraction(13, 5))
        assert service.remove_domain_element(state, 1).domain_basis == (2, Fraction(13, 5))
        assert service.remove_domain_element(state, 2).domain_basis == (2, 3)
        for k in range(state.d):
            assert service.remove_domain_element(state, k).d == state.d - 1

    def test_remove_domain_element_inverts_add_domain_element(self):
        state = service.from_comma_basis(((4, -4, 1),))
        added = service.add_domain_element(state, service.parse_domain_element("13/5"))
        back = service.remove_domain_element(added, added.d - 1)
        assert back.domain_basis == state.domain_basis and back.comma_basis == state.comma_basis
        assert (back.d, back.r, back.n) == (state.d, state.r, state.n)

    def test_remove_domain_element_matches_shrink_for_the_last_standard_element(self):
        state = service.from_comma_basis(((4, -4, 1),))
        removed = service.remove_domain_element(state, state.d - 1)
        shrunk = service.shrink_domain(state)
        assert removed.domain_basis == shrunk.domain_basis == (2, 3)
        assert removed.mapping == shrunk.mapping and removed.comma_basis == shrunk.comma_basis

    def test_remove_domain_element_collapsing_every_comma_leaves_just_intonation(self):
        state = service.from_comma_basis(((0, 0, 1),))
        ji = service.remove_domain_element(state, 2)
        assert ji.domain_basis == (2, 3) and ji.n == 0 and ji.r == ji.d == 2

    def test_can_remove_domain_element_keeps_at_least_one_element(self):
        assert service.can_remove_domain_element(service.from_comma_basis(((4, -4, 1),)))
        assert not service.can_remove_domain_element(service.from_mapping(((1,),)))


class TestResolveDomainElement:
    def test_resolve_domain_element_transform_applies_a_valid_relabel(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        out = service.resolve_domain_element_transform(st, 1, "3", "reduce")
        assert out.effect is service.Effect.ACCEPT
        assert out.value == "3/2"

    def test_resolve_domain_element_transform_flags_a_no_op(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.resolve_domain_element_transform(st, 1, "3/2", "reduce").effect is service.Effect.IGNORE, "3/2 is already octave-reduced, so reducing it again changes nothing"

    def test_resolve_domain_element_transform_rejects_a_unison_result(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        out = service.resolve_domain_element_transform(st, 0, "2", "reduce")
        assert out.effect is service.Effect.REJECT
        assert "1" in out.message

    def test_resolve_domain_element_transform_rejects_a_dependent_result(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        out = service.resolve_domain_element_transform(st, 1, "4", "reciprocate")
        assert out.effect is service.Effect.REJECT
        assert "1/4" in out.message

    def test_resolve_domain_element_edit_classifies_a_blank_or_placeholder_field(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.resolve_domain_element_edit(st, "1", "").effect is service.Effect.RERENDER
        assert service.resolve_domain_element_edit(st, "1", "?/?").effect is service.Effect.RERENDER

    def test_resolve_domain_element_edit_rejects_an_unparseable_element(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.resolve_domain_element_edit(st, "1", "1").effect is service.Effect.REJECT
        assert service.resolve_domain_element_edit(st, "1", "x").effect is service.Effect.REJECT

    def test_resolve_domain_element_edit_reports_an_unchanged_index_as_no_op(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.resolve_domain_element_edit(st, "1", "3").effect is service.Effect.IGNORE

    def test_resolve_domain_element_edit_accepts_a_fresh_relabel(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        out = service.resolve_domain_element_edit(st, "1", "7")
        assert out.effect is service.Effect.ACCEPT
        assert out.value == "7"

    def test_resolve_domain_element_edit_flags_a_dependent_relabel(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        out = service.resolve_domain_element_edit(st, "1", "4")
        assert out.effect is service.Effect.REJECT
        assert "dependent" in out.message

    def test_resolve_domain_element_edit_distinguishes_the_pending_dependent_message(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert "independent" in service.resolve_domain_element_edit(st, "pending", "9").message

    def test_resolve_domain_element_edit_checks_a_pending_addition_for_independence(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.resolve_domain_element_edit(st, "pending", "7").effect is service.Effect.ACCEPT, "a pending element extends the basis, so it must be independent of all existing primes"
        assert service.resolve_domain_element_edit(st, "pending", "9").effect is service.Effect.REJECT


class TestTemperamentProperties:
    def test_is_proper_temperament_rejects_degenerate_mappings(self):
        assert service.is_proper_temperament(((1, 1, 0), (0, 1, 4))) is True, "a proper temperament has independent rows (full row rank) and reaches every prime (no all-zero # column — a prime mapped to nothing is tempered to a unison). Degenerate ones break M·Dᵀ=I and # don't round-trip, so the editor rejects them"
        assert service.is_proper_temperament(((2, 0, 0), (0, 1, 1))) is True
        assert service.is_proper_temperament(((1, 2), (0, 0))) is False
        assert service.is_proper_temperament(((1, 0),)) is False

    def test_greatest_factor_and_is_enfactored_detect_temperoids(self):
        assert service.greatest_factor(((24, 38, 56),)) == 2, "the defactoring digest (column-HNF pivot product), NOT a row GCD: it catches hidden enfactoring # where no single row is divisible. is_enfactored is the gate the renderer uses to dash the # generator/detempering rows (M·Dᵀ ≠ I for a temperoid), deliberately SEPARATE from # is_proper_temperament, which still accepts enfactored full-rank mappings. (canonical-defactor-4.)"
        assert service.greatest_factor(((2, 2, 0), (0, 1, 4))) == 2
        assert service.greatest_factor(((1, 1, 0), (0, 1, 4))) == 1
        assert service.greatest_factor(((0, 1, 4),)) == 1, "a zero-column state is not enfactored"
        assert service.greatest_factor(((1, 0, -4), (2, 0, -8))) == 1
        assert service.is_enfactored(((24, 38, 56),)) is True
        assert service.is_enfactored(((1, 1, 0), (0, 1, 4))) is False
        assert service.is_proper_temperament(((2, 0, 0), (0, 1, 1))) is True
        assert service.is_enfactored(((2, 0, 0), (0, 1, 1))) is True

    def test_standardize_to_prime_limit_fills_the_limit_up_to_the_largest_prime(self):
        state = service.standardize_to_prime_limit((2, 3, Fraction(13, 5)), ("13/5",))
        assert state.domain_basis == (2, 3, 5, 7, 11, 13)

    def test_resolve_comma_basis_form_prefers_the_user_pick_when_forms_coincide(self):
        positive = ((-4, 4, -1),)
        assert service.identify_comma_basis_form(positive) == "positive-ratio"
        assert service.resolve_comma_basis_form(positive, "minimal") == "minimal"
        assert service.resolve_comma_basis_form(positive, "positive-ratio") == "positive-ratio"
        assert service.resolve_comma_basis_form(positive, "canonical") == "positive-ratio", "a preferred form the matrix is NOT in is ignored — falls back to the first real match"
        assert service.resolve_comma_basis_form(((4, -4, 1),), None) == "canonical"
        assert service.resolve_mapping_form(((1, 1, 0), (0, 1, 4)), None) == "equave-reduced"
