from fractions import Fraction

from rtt.app import service, settings, spreadsheet
from rtt.app.editor import INITIAL_MAPPING, Editor
from _editor_support import BARBADOS_ALT


class TestDomainElements:
    def test_set_domain_element_relabels_in_place_and_is_undoable(self):
        ed = Editor()
        ed.set_domain_element(2, "13/5")
        assert ed.state.domain_basis == (2, 3, Fraction(13, 5))
        assert ed.state.mapping == Editor().state.mapping
        ed.undo()
        assert ed.state.domain_basis == (2, 3, 5)

    def test_set_domain_element_rejects_a_dependent_relabel(self):
        ed = Editor()
        ed.set_domain_element(2, "9")
        assert ed.state.domain_basis == (2, 3, 5)
        assert not ed.can_undo, "nothing committed, so no undo step"

    def test_add_element_draft_commits_a_valid_rational_held_just(self):
        ed = Editor()
        ed.add_element()
        assert ed.pending_element == "", "a blank green ?/? draft, not yet part of the domain"
        assert ed.state.dimensionality == 3
        ed.set_pending_element("7")
        assert ed.pending_element is None
        assert ed.state.domain_basis == (2, 3, 5, 7)
        assert ed.state.dimensionality == 4 and ed.state.rank == 3
        ed.undo()
        assert ed.state.domain_basis == (2, 3, 5)

    def test_add_element_commits_a_nonprime_and_the_grid_builds(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.add_element()
        ed.set_pending_element("13/5")
        assert ed.state.domain_basis == (2, 3, 5, Fraction(13, 5))
        assert ed.pending_element is None
        ed.layout()

    def test_pending_element_holds_an_invalid_or_partial_draft(self):
        ed = Editor()
        ed.add_element()
        ed.set_pending_element("9")
        assert ed.pending_element == "9"
        assert ed.state.domain_basis == (2, 3, 5)

    def test_domain_drafts_clear_on_a_domain_change(self):
        ed = Editor()
        ed.add_element()
        ed.shrink()
        assert ed.pending_element is None

    def test_remove_element_cancels_the_draft(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.add_element()
        ed.remove_element()
        assert ed.pending_element is None

    def test_remove_domain_element_drops_a_committed_element_and_is_undoable(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        before = ed.state
        ed.remove_domain_element(0)
        assert ed.state.domain_basis == (3, Fraction(13, 5)) and ed.state.dimensionality == 2
        assert ed.can_undo is True
        ed.undo()
        assert ed.state.domain_basis == before.domain_basis and ed.state.comma_basis == before.comma_basis

    def test_remove_domain_element_clears_an_open_draft(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        ed.add_element()
        assert ed.pending_element == ""
        ed.remove_domain_element(2)
        assert ed.pending_element is None and ed.state.domain_basis == (2, 3)

    def test_remove_domain_element_is_a_no_op_at_the_last_element(self):
        ed = Editor()
        ed.settings["nonstandard_domain"] = True
        ed.state = service.from_mapping(((1,),))
        ed.remove_domain_element(0)
        assert ed.state.dimensionality == 1 and ed.can_undo is False

    def test_domain_expand_shrink_are_inert_on_a_nonstandard_domain(self):
        editor = Editor()
        editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        before = editor.state
        assert editor.can_shrink is False and editor.can_expand is False
        editor.expand()
        editor.shrink()
        assert editor.state is before

    def test_standard_domain_can_still_expand(self):
        editor = Editor()
        assert editor.can_expand is True
        editor.expand()
        assert editor.state.dimensionality == 4 and editor.state.domain_basis == (2, 3, 5, 7)

    def test_shrinking_runs_down_to_one_prime_through_degenerate_states(self):
        editor = Editor()
        assert editor.can_shrink is True
        editor.shrink()
        assert editor.state.dimensionality == 2 and editor.can_shrink is True
        editor.shrink()
        assert editor.state.dimensionality == 1
        assert editor.can_shrink is False, "zero primes is not a domain — the floor"
        editor.shrink()
        assert editor.state.dimensionality == 1

    def test_structural_edits_preserve_a_nonstandard_domain(self):
        barbados_domain = (2, 3, Fraction(13, 5))
        for op in (
            lambda e: e.flip_generator(1),
            lambda e: e.edit_mapping([[1, 0, -1], [0, 2, 4]]),
            lambda e: e.canonicalize_mapping(),
            lambda e: e.canonicalize_comma_basis(),
        ):
            editor = Editor()
            assert editor.try_edit_mapping_text(BARBADOS_ALT)
            op(editor)
            assert editor.state.domain_basis == barbados_domain


class TestNonprimeApproach:
    def test_nonprime_basis_approach_starts_neutral_and_holds_a_chosen_mode(self):
        import pytest

        editor = Editor()
        assert editor.nonprime_basis_approach == ""
        editor.set_nonprime_basis_approach("nonprime-based")
        assert editor.nonprime_basis_approach == "nonprime-based"
        editor.set_nonprime_basis_approach("prime-based")
        assert editor.nonprime_basis_approach == "prime-based"
        editor.set_nonprime_basis_approach("")
        assert editor.nonprime_basis_approach == ""
        with pytest.raises(ValueError):
            editor.set_nonprime_basis_approach("bogus")

    def test_nonprime_basis_approach_threads_into_the_layouts_tuning(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.7/3.11/3 [⟨1 1 2] ⟨0 2 -1]]")
        editor.set_tuning_scheme("minimax-C")
        neutral = {c.id: c.text for c in editor.layout().cells}
        editor.set_nonprime_basis_approach("nonprime-based")
        nonprime = {c.id: c.text for c in editor.layout().cells}
        assert neutral["tuning:generator:0"] != nonprime["tuning:generator:0"]
        assert neutral["tuning:generator:1"] != nonprime["tuning:generator:1"]

    def test_nonprime_basis_approach_resets_when_the_domain_loses_its_nonprimes(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        editor.set_nonprime_basis_approach("nonprime-based")
        editor.state = service.from_temperament_data("2.3.13/7 [⟨1 2 2] ⟨0 -2 -3]}")
        assert editor.nonprime_basis_approach == "nonprime-based"
        editor.state = service.from_mapping([[1, 1, 0], [0, 1, 4]])
        assert editor.nonprime_basis_approach == ""

    def test_prime_based_superspace_generator_edit_drives_domain_and_resets(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        editor.set_nonprime_basis_approach("prime-based")
        assert editor.effective_generator_tuning() is None or editor.superspace_generator_tuning is None
        optimum_domain = editor.optimum_generator_tuning()
        editor.set_superspace_generator_tuning_component(2, 999.0)
        assert editor.superspace_generator_tuning is not None and editor.superspace_generator_tuning[2] == 999.0
        projected = editor.effective_generator_tuning()
        assert projected is not None and len(projected) == len(editor.state.mapping)
        assert projected != optimum_domain
        editor.set_nonprime_basis_approach("")
        assert editor.superspace_generator_tuning is None
        editor.set_nonprime_basis_approach("prime-based")
        editor.set_superspace_generator_tuning_component(0, 1200.0)
        editor.edit_mapping([[1, 0, -1], [0, 2, 3]])
        assert editor.state.domain_basis == (2, 3, Fraction(13, 5))
        assert editor.superspace_generator_tuning is None

    def test_approach_switch_clears_a_stranded_manual_flag(self):
        editor = Editor()
        assert editor.try_edit_mapping_text(BARBADOS_ALT)
        editor.set_nonprime_basis_approach("prime-based")
        editor.set_superspace_generator_tuning_component(0, 1190.0)
        assert editor.manual_tuning is True
        editor.set_nonprime_basis_approach("")
        assert editor.superspace_generator_tuning is None
        assert editor.manual_tuning is False

    def test_a_domain_change_forgets_stale_held_interest_and_prescaler(self):
        for walk in ("expand", "shrink"):
            editor = Editor()
            if walk == "shrink":
                editor.try_edit_mapping_text("[⟨1 0 -4 -13] ⟨0 1 4 10]}")
            editor.set_held_vectors([tuple([-1, 1, 0] + [0] * (editor.state.dimensionality - 3))])
            editor.set_interest_vectors([tuple([-2, 0, 1] + [0] * (editor.state.dimensionality - 3))])
            editor.set_custom_prescaler_entry(0, 0, 2.0)
            getattr(editor, walk)()
            assert editor.held_vectors == [] and editor.interest_vectors == []
            assert editor.custom_prescaler is None
            editor.layout()


class TestSuperspaceGeneratorEdit:
    def test_set_superspace_generator_tuning_text_holds_rl_cents_and_rejects_a_wrong_count(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        assert editor.set_superspace_generator_tuning_text("1200 700 400") is True
        assert editor.superspace_generator_tuning == (1200.0, 700.0, 400.0)
        assert editor.set_superspace_generator_tuning_text("1200 700") is False, "not rL values"

    def test_nudge_superspace_generator_tuning_component_steps_by_thousandths_of_a_cent(self):
        editor = Editor()
        editor.state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        seed = editor.optimum_superspace_generator_tuning()[0]
        editor.nudge_superspace_generator_tuning_component(0, 7)
        assert editor.superspace_generator_tuning[0] == round(round(seed, 3) + 7 * 0.001, 3)
