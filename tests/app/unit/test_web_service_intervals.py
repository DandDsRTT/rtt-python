import math
from fractions import Fraction

import pytest

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings
from rtt.app.service import core_vectors, parse, text_format
from _service_support import _grid_with_plain_text


class TestGenerators:
    def test_generators_as_ratios(self):
        assert service.generators([[1, 1, 0], [0, 1, 4]]) == ("2/1", "3/2")

    def test_generators_over_a_nonstandard_domain_multiply_out_the_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.generators(state.mapping, domain_basis=state.domain_basis) == ("2/1", "15/13")

    def test_generator_detempering_vectors(self):
        assert service.generator_detempering([[1, 1, 0], [0, 1, 4]]) == ((1, 0, 0), (-1, 1, 0))


class TestCommaRatios:
    def test_comma_ratios_renders_each_comma_vector_as_a_ratio(self):
        assert service.comma_ratios(((4, -4, 1),)) == ("80/81",)
        assert service.comma_ratios(((4, -4, 1), (0, 0, 0))) == ("80/81", "1/1")

    def test_comma_ratios_over_a_nonstandard_domain_multiply_out_the_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.comma_ratios(state.comma_basis, domain_basis=state.domain_basis) == ("676/675",)


class TestMappedIntervals:
    def test_mapped_intervals(self):
        mapped = service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ("2/1", "3/2", "5/4", "6/5"))
        assert mapped == ((1, 0, -2, 2), (0, 1, 4, -3))

    def test_mapped_intervals_over_a_nonstandard_domain_express_in_the_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        mapped = service.mapped_intervals(
            state.mapping, ("2/1", "3/1", "13/5"), domain_basis=state.domain_basis
        )
        assert mapped == state.mapping

    def test_mapped_intervals_of_the_empty_set_is_empty_rows(self):
        assert service.mapped_intervals([[1, 1, 0], [0, 1, 4]], ()) == ((), ()), "one (empty) generator row per mapping row, so the r x m matrix stays well-formed"

    def test_mapped_commas_vanish(self):
        mapped = service.mapped_commas([[1, 1, 0], [0, 1, 4]], [[4, -4, 1]])
        assert mapped == ((0,), (0,))


class TestTargetIntervalVectors:
    def test_target_interval_vectors(self):
        vectors = service.target_interval_vectors(("2/1", "3/2", "5/4", "6/5"), 3)
        assert vectors == ((1, 0, 0), (-1, 1, 0), (-2, 0, 1), (1, 1, -1))

    def test_target_interval_vectors_over_a_nonstandard_domain(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        vectors = service.target_interval_vectors(
            ("2/1", "3/1", "13/5"), state.dimensionality, domain_basis=state.domain_basis
        )
        assert vectors == ((1, 0, 0), (0, 1, 0), (0, 0, 1))


class TestEquave:
    def test_equave_quotient_is_the_first_basis_element(self):
        assert service.equave_quotient() == Fraction(2)
        assert service.equave_quotient((2, 3, 5)) == Fraction(2)
        assert service.equave_quotient((3, 5, 7)) == Fraction(3)
        assert service.equave_quotient((2, 3, Fraction(13, 5))) == Fraction(2)

    def test_equave_reduce_vector_folds_only_the_equave_coordinate(self):
        assert service.equave_reduce_vector((-2, 2, 0)) == (-3, 2, 0)
        assert service.equave_reduce_vector((-2, 0, 1)) == (-2, 0, 1)
        assert service.equave_reduce_vector((0, 0, 1)) == (-2, 0, 1)
        assert service.equave_reduce_vector((1, 0, 0)) == (0, 0, 0)

    def test_equave_reduce_vector_over_a_nonstandard_domain(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        octave = service.interval_vector("2/1", state.dimensionality, state.domain_basis)
        assert service.equave_reduce_vector(octave, state.domain_basis) == (0, 0, 0)


class TestIntervalOps:
    def test_interval_op_availability_gates_the_two_buttons(self):
        assert service.interval_op_availability("9/4") == (True, True)
        assert service.interval_op_availability("5/4") == (False, True)
        assert service.interval_op_availability("2") == (True, True)
        assert service.interval_op_availability("1") == (False, False)
        assert service.interval_op_availability("?/?") == (False, False)
        assert service.interval_op_availability("") == (False, False)
        assert service.interval_op_availability("5/2", (3, 5, 7)) == (False, True)

    def test_transform_ratio_reduces_or_reciprocates_a_ratio_string(self):
        assert service.transform_ratio("13/5", "reduce", (2, 3, Fraction(13, 5))) == "13/10"
        assert service.transform_ratio("13/5", "reciprocate") == "5/13"
        assert service.transform_ratio("9/4", "reduce") == "9/8"
        assert service.transform_ratio("2", "reduce") == "1"
        assert service.transform_ratio("5/4", "reduce") is None
        assert service.transform_ratio("1", "reciprocate") is None
        assert service.transform_ratio("?/?", "reduce") is None

    def test_transformed_vector_reciprocates_and_reduces(self):
        assert service.transformed_vector((-1, 1, 0), "reciprocate", (2, 3, 5)) == (1, -1, 0)
        assert service.transformed_vector((-1, 1, 0), "reduce", (2, 3, 5)) is None
        assert service.transformed_vector((-2, 2, 0), "reduce", (2, 3, 5)) == (-3, 2, 0)

    def test_transformed_vector_reports_a_unison_reciprocation_as_no_op(self):
        assert service.transformed_vector((0, 0, 0), "reciprocate", (2, 3, 5)) is None


class TestIntervalVector:
    def test_interval_vector_parses_a_ratio_into_its_vector(self):
        assert service.interval_vector("80/81", 3) == (4, -4, 1)
        assert service.interval_vector("5/4", 3) == (-2, 0, 1)
        assert service.interval_vector("2", 3) == (1, 0, 0)
        basis = ((4, -4, 1), (0, 0, 0))
        assert tuple(service.interval_vector(r, 3) for r in service.comma_ratios(basis)) == basis

    def test_interval_vector_raises_a_classified_error_for_bad_input(self):
        with pytest.raises(ValueError, match="not a valid ratio"):
            service.interval_vector("nonsense", 3)
        with pytest.raises(ValueError, match="not a valid ratio"):
            service.interval_vector("", 3)
        with pytest.raises(ValueError, match="not a positive ratio"):
            service.interval_vector("0", 3)
        with pytest.raises(ValueError, match="outside the 2.3.5 domain"):
            service.interval_vector("7/4", 3)

    def test_interval_vector_names_a_nonstandard_domain_in_its_out_of_limit_error(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        with pytest.raises(ValueError, match=r"outside the 2.3.13/5 domain"):
            service.interval_vector("5/4", state.dimensionality, domain_basis=state.domain_basis)

    def test_interval_vector_over_a_nonstandard_domain_expresses_in_the_basis(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert service.interval_vector("13/5", state.dimensionality, domain_basis=state.domain_basis) == (0, 0, 1)
        assert service.interval_vector("676/675", state.dimensionality, domain_basis=state.domain_basis) == (2, -3, 2)


class TestTargetSets:
    def test_tilt_target_interval_set_is_the_domains_tilt(self):
        assert service.target_interval_set("TILT", (2, 3, 5)) == (
            "2/1", "3/1", "3/2", "4/3", "5/2", "5/3", "5/4", "6/5",
        )

    def test_tilt_target_interval_set_tracks_the_domain(self):
        five_limit = set(service.target_interval_set("TILT", (2, 3, 5)))
        seven_limit = set(service.target_interval_set("TILT", (2, 3, 5, 7)))
        assert five_limit < seven_limit
        assert "7/4" in seven_limit

    def test_target_interval_set_filters_to_a_nonstandard_subgroup(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        targets = service.target_interval_set("TILT", state.domain_basis)
        assert "5/4" not in targets and "7/3" not in targets
        assert "3/2" in targets and "13/5" in targets
        vectors = service.target_interval_vectors(targets, state.dimensionality, domain_basis=state.domain_basis)
        assert len(vectors) == len(targets)

    def test_old_target_interval_set_is_the_odd_limit_diamond(self):
        old = service.target_interval_set("OLD", (2, 3, 5))
        assert "5/4" in old and "6/5" in old and "8/5" in old
        assert old != service.target_interval_set("TILT", (2, 3, 5))


class TestDisplayedTargets:
    def test_displayed_targets_resolve_the_one_list_the_grid_and_plain_text_share(self):
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert service.displayed_targets(st, "TILT minimax-S") == service.target_interval_set("TILT", (2, 3, 5))
        assert service.displayed_targets(st, "TILT minimax-S", target_override=("2/1", "3/2")) == ("2/1", "3/2")
        assert service.displayed_targets(st, "minimax-S") == ("2/1", "3/1", "5/1")
        assert service.displayed_targets(st, "minimax-S", target_override=("2/1", "3/2")) == ("2/1", "3/1", "5/1")

    def test_default_target_limit_is_the_number_a_bare_family_resolves_to(self):
        assert service.default_target_limit("TILT", (2, 3, 5)) == 6, "2.3.5: TILT defaults to the 6-TILT, OLD to the 5-OLD (so the chooser shows a # real number, not 'auto'); both grow with the domain"
        assert service.default_target_limit("OLD", (2, 3, 5)) == 5
        assert service.default_target_limit("TILT", (2, 3, 5, 7)) == 10

    def test_target_limit_problem_validates_the_chooser_entry(self):
        assert service.target_limit_problem("OLD", 8) == "odd", "the odd-limit diamond (OLD) is odd by construction, so an even limit is invalid; the # truncated integer-limit triangle (TILT) accepts any whole number. A non-whole / unparseable # entry is invalid for either family. A blank (or zero) entry is fine — the family then # tracks the domain default. (None family = an override / all-interval chooser: no parity rule.)"
        assert service.target_limit_problem("OLD", 8.0) == "odd"
        assert service.target_limit_problem("OLD", 9) is None
        assert service.target_limit_problem("TILT", 8) is None
        assert service.target_limit_problem("TILT", 9.5) == "whole"
        assert service.target_limit_problem("OLD", "abc") == "whole"
        assert service.target_limit_problem("OLD", None) is None
        assert service.target_limit_problem("OLD", "") is None
        assert service.target_limit_problem("OLD", 0) is None
        assert service.target_limit_problem(None, 8) is None
        assert service.target_limit_problem("OLD", "8") == "odd", "the chooser's limit is a TEXT field, so the entry arrives as a string: validate those too"
        assert service.target_limit_problem("OLD", "9") is None
        assert service.target_limit_problem("TILT", "8.5") == "whole"
        assert service.target_limit_problem("TILT", service.NO_LIMIT_TEXT) is None
        assert service.target_limit_problem("OLD", service.NO_LIMIT_TEXT) is None

    def test_target_spec_builds_leniently_falling_back_to_the_bare_family(self):
        assert service.target_spec("TILT", "9") == "9-TILT"
        assert service.target_spec("OLD", "") == "OLD"
        assert service.target_spec("OLD", None) == "OLD"
        assert service.target_spec("TILT", "abc") == "TILT"
        assert service.target_spec("TILT", "8.5") == "8-TILT"
        assert service.target_spec("TILT", service.NO_LIMIT_TEXT) == "TILT"


class TestResolveTargetLimit:
    def test_resolve_target_limit_accepts_the_spec_from_family_and_limit(self):
        out = service.resolve_target_limit("OLD", "9", (2, 3, 5))
        assert out.effect is service.Effect.ACCEPT
        assert out.value == "9-OLD"
        assert out.reason is None

    def test_resolve_target_limit_defaults_a_blank_family_to_tilt(self):
        out = service.resolve_target_limit(None, None, (2, 3, 5))
        assert out.effect is service.Effect.ACCEPT
        assert out.value == "TILT"
        assert bool(service.target_interval_set(out.value, (2, 3, 5)))

    def test_resolve_target_limit_rejects_a_non_whole_limit_with_the_whole_reason(self):
        out = service.resolve_target_limit("TILT", "8.5", (2, 3, 5))
        assert out.effect is service.Effect.REJECT
        assert out.reason is service.Reason.TARGET_WHOLE

    def test_resolve_target_limit_accepts_an_even_old_limit_with_the_odd_warning(self):
        out = service.resolve_target_limit("OLD", "8", (2, 3, 5))
        assert out.effect is service.Effect.ACCEPT
        assert out.value == "8-OLD"
        assert out.reason is service.Reason.TARGET_ODD

    def test_resolve_target_limit_ignores_an_unproducible_spec(self):
        out = service.resolve_target_limit("TILT", "1", (2, 3, 5))
        assert out.effect is service.Effect.IGNORE


class TestResolveRatioEdit:
    def test_resolve_ratio_edit_parses_a_ratio_into_a_domain_vector(self):
        out = service.resolve_ratio_edit("3/2", 3, (2, 3, 5))
        assert out.effect is service.Effect.ACCEPT
        assert out.value == (-1, 1, 0)

    def test_resolve_ratio_edit_treats_blank_and_placeholder_as_rerender(self):
        assert service.resolve_ratio_edit("", 3, (2, 3, 5)).effect is service.Effect.RERENDER
        assert service.resolve_ratio_edit("?/?", 3, (2, 3, 5)).effect is service.Effect.RERENDER

    def test_resolve_ratio_edit_reports_an_invalid_ratio_with_the_parser_message(self):
        out = service.resolve_ratio_edit("7/4", 3, (2, 3, 5))
        assert out.effect is service.Effect.REJECT
        assert out.message
        assert service.resolve_ratio_edit("x", 3, (2, 3, 5)).effect is service.Effect.REJECT


class TestCents:
    def test_cents_drops_negative_zero(self):
        assert service.cents(-0.0) == "0.000", "negative zero carries no meaning, so a value that shows as zero never wears a minus sign"
        assert service.cents(-0.0004) == "0.000"
        assert service.cents(-0.0006) == "-0.001"
        assert service.cents(0.0) == "0.000"
        assert service.cents(None) == "—"

    def test_cents_and_prescale_text_round_to_integer_when_decimals_off(self):
        assert service.cents(701.955) == "701.955", "the shared value formatters carry the Show panel's 'decimals' setting: on (the default) they # keep the 3-dp cents reading; off they round to the nearest integer — the single chokepoint the # grid and plain-text views both route through, so turning decimals off rounds the whole app"
        assert service.cents(701.955, decimals=False) == "702"
        assert service.cents(None, decimals=False) == "—"
        assert service.prescale_text(1.0, decimals=False) == "1"
        assert service.prescale_text(1.585) == "1.585"
        assert service.prescale_text(1.585, decimals=False) == "2"


class TestPendingText:
    def test_vector_list_pending_text_splits_the_draft_for_two_tone_display(self):
        prefix, draft, suffix = service.vector_list_pending_text(((4, -4, 1),), [4, None, 1])
        assert (prefix, draft, suffix) == ("[[4 -4 1⟩ ", "[4 1⟩", "]")
        assert prefix + draft + suffix == "[[4 -4 1⟩ [4 1⟩]"
        assert service.vector_list_pending_text(((4, -4, 1),), [None, None, None])[1] == "[⟩"
        assert service.vector_list_pending_text(((4, -4, 1), (4, -5, 1)), [None, None, None])[0] == "[[4 -4 1⟩ [4 -5 1⟩ "

    def test_mapping_pending_text_splices_the_draft_map_before_the_closing_brace(self):
        prefix, draft, suffix = service.mapping_pending_text("[⟨1 1 0] ⟨0 1 4]}", [0, None, 1])
        assert (prefix, draft, suffix) == ("[⟨1 1 0] ⟨0 1 4] ", "⟨0 1]", "}")
        assert prefix + draft + suffix == "[⟨1 1 0] ⟨0 1 4] ⟨0 1]}"
        assert service.mapping_pending_text("[⟨1 1 0] ⟨0 1 4]}", [None, None, None])[1] == "⟨]"
        assert service.mapping_pending_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}", [None, None, None])[0] \
            == "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3] "


class TestParsing:
    def test_parse_mapping_state_reads_an_ebk_map_string(self):
        assert service.parse_mapping_state("[⟨1 1 0] ⟨0 1 4]}").mapping == ((1, 1, 0), (0, 1, 4))
        assert service.parse_mapping_state("⟨12 19 28]").mapping == ((12, 19, 28),)
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
        assert service.parse_mapping_state(pt[("mapping", "primes")]).mapping == ((1, 1, 0), (0, 1, 4))

    def test_parse_comma_basis_reads_an_ebk_vector_string(self):
        assert service.parse_comma_basis("[4 -4 1⟩") == ((4, -4, 1),)
        pt = service.plain_text_values(service.from_mapping([[1, 1, 0], [0, 1, 4]]))
        assert service.parse_comma_basis(pt[("vectors", "commas")]) == ((4, -4, 1),)

    def test_parse_rejects_unparseable_wrong_variance_or_non_integer(self):
        assert service.parse_mapping_state("garbage") is None
        assert service.parse_mapping_state("") is None
        assert service.parse_mapping_state("[1 0 0⟩") is None, "a vector, not a map"
        assert service.parse_mapping_state("⟨1 1.5 0]") is None
        assert service.parse_comma_basis("⟨1 0 0]") is None, "a map, not a vector"
        assert service.parse_comma_basis("nonsense") is None

    def test_parse_cents_map_reads_a_genmap_or_tuning_string(self):
        assert service.parse_cents_map("{1201.699 697.564]") == (1201.699, 697.564)
        assert service.parse_cents_map("⟨1200.000 1901.955 2786.314]") == (1200.0, 1901.955, 2786.314)
        st = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        generator_map = service.tuning(st.mapping).generator_map
        parsed = service.parse_cents_map(service.plain_text_values(st)[("tuning", "gens")])
        assert parsed == tuple(round(g, 3) for g in generator_map)
        assert service.parse_cents_map("{1200 700]", 2) == (1200.0, 700.0), "an optional length check, so a caller can demand exactly r generators"
        assert service.parse_cents_map("{1200 700]", 3) is None
        assert service.parse_cents_map("garbage") is None
        assert service.parse_cents_map("{1200 x]") is None
        assert service.parse_cents_map("") is None


class TestVectorsToRatios:
    def test_vectors_to_ratios_flags_an_over_complex_ratio_instead_of_crashing(self):
        huge = service.from_mapping(((3, 4, -8), (-1, 7, 6), (3, 0, 6)))
        gens = service.generators(huge.mapping)
        assert gens == (core_vectors._OVER_COMPLEX_RATIO,) * 3, "flagged, not a 4300+-digit string (no crash)"
        assert service.generators(((1, 1, 0), (0, 1, 4))) == ("2/1", "3/2")

    def test_over_complex_generators_round_trip_back_to_a_finite_size(self):
        state = service.from_mapping(((3, 4, -8), (-1, 7, 6), (3, 0, 6)))
        tuning_map = service.tuning(state.mapping, "TILT minimax-U")
        sizes = service.interval_sizes(tuning_map, service.generators(state.mapping))
        assert all(math.isfinite(s) for s in sizes.tempered)
        pt = service.plain_text_values(state, "TILT minimax-U", "TILT")
        assert pt[("tuning", "detempering")]
        gb = _grid_with_plain_text(state, "TILT minimax-U")
        assert core_vectors._OVER_COMPLEX_RATIO in gb.resolved.scalars.gens
