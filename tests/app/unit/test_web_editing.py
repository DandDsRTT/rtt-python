from types import SimpleNamespace

from rtt.app import _editing_controls, service
from rtt.app.editing import EditController
from rtt.app.page_assets import _INVALID_PRESCALER


def _controller():
    calls = []
    renderer = SimpleNamespace(
        render=lambda: calls.append("render"),
        request_render=lambda after=None: calls.append("request_render"),
    )
    gestures = SimpleNamespace(
        end_commit_gestures=lambda: calls.append("end_commit"),
        edit_candidate=lambda commit: calls.append(("edit_candidate", commit)),
    )
    runtime = SimpleNamespace(building=False)
    edit_controller = EditController(SimpleNamespace(), SimpleNamespace(), gestures, renderer, runtime)
    return edit_controller, calls


class TestWebEditing:
    def test_edit_controller_constructs_without_a_page(self):
        edit_controller, _ = _controller()
        assert edit_controller.vectors.e is edit_controller
        assert edit_controller.tuning.e is edit_controller

    def test_reason_message_maps_a_known_reason_and_ignores_unmapped(self):
        assert _editing_controls.reason_message(service.Reason.INVALID_PRESCALER) == _INVALID_PRESCALER
        assert _editing_controls.reason_message(None) is None

    def test_act_ends_gestures_runs_action_then_requests_render(self):
        edit_controller, calls = _controller()
        edit_controller.act(lambda: calls.append("action"))
        assert calls == ["end_commit", "action", "request_render"]

    def test_apply_outcome_ignore_does_nothing(self):
        edit_controller, calls = _controller()
        committed = []
        edit_controller._apply_outcome(service.IGNORE, lambda: committed.append(1))
        assert calls == []
        assert committed == []

    def test_apply_outcome_rerender_rerenders_without_committing(self):
        edit_controller, calls = _controller()
        committed = []
        edit_controller._apply_outcome(service.RERENDER, lambda: committed.append(1))
        assert calls == ["render"]
        assert committed == []

    def test_apply_outcome_accept_commits_then_requests_render(self):
        edit_controller, calls = _controller()
        committed = []
        edit_controller._apply_outcome(service.accept(), lambda: committed.append(1))
        assert committed == [1]
        assert calls == ["request_render"]

    def test_apply_outcome_preview_arms_the_edit_candidate(self):
        edit_controller, calls = _controller()

        def commit():
            return None

        edit_controller._apply_outcome(service.accept(), commit, preview=True)
        assert ("edit_candidate", commit) in calls


class TestComplexityApply:
    def _controller(self):
        calls = []
        editor = SimpleNamespace(
            set_complexity_name=lambda name: calls.append(("set", name)),
        )
        return SimpleNamespace(_editor=editor), calls

    def test_the_custom_readout_is_not_an_actionable_option(self):
        edit_controller, _ = self._controller()
        assert _editing_controls.complexity_apply(edit_controller, "custom") is None

    def test_selecting_a_named_complexity_sets_its_internal_name(self):
        edit_controller, calls = self._controller()
        display = service.COMPLEXITY_DISPLAYS["sopfr"]
        apply = _editing_controls.complexity_apply(edit_controller, display)
        apply()
        assert calls == [("set", "sopfr")]


class TestSlopeApply:
    def test_selecting_a_slope_sets_the_weight_slope(self):
        calls = []
        editor = SimpleNamespace(set_weight_slope=lambda slope: calls.append(("slope", slope)))
        _editing_controls.slope_apply(editor, "unity-weight")()
        assert calls == [("slope", "unity-weight")]

    def test_custom_does_not_preview_so_slope_apply_returns_no_action(self):
        editor = SimpleNamespace()
        assert _editing_controls.slope_apply(editor, "custom") is None, \
            "hovering custom must not preview: selecting it makes cells editable, it does not change any value"

    def test_selecting_custom_seeds_the_weights_from_the_displayed_baseline(self):
        calls = []
        editor = SimpleNamespace(
            custom_weights=None,
            displayed_target_weights=lambda: (1.0, 2.0, 3.0),
            set_custom_weights=lambda w: calls.append(("custom", tuple(w))),
        )
        _editing_controls._select_custom_weights(editor)
        assert calls == [("custom", (1.0, 2.0, 3.0))]

    def test_selecting_custom_is_a_no_op_when_already_in_custom(self):
        calls = []
        editor = SimpleNamespace(
            custom_weights=(9.0,),
            displayed_target_weights=lambda: (1.0,),
            set_custom_weights=lambda w: calls.append(w),
        )
        _editing_controls._select_custom_weights(editor)
        assert calls == [], "re-selecting custom must not reset hand-edited weights to the baseline"
