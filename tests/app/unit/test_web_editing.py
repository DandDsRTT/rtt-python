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
