from types import SimpleNamespace

from rtt.app import service
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
    ec = EditController(SimpleNamespace(), SimpleNamespace(), gestures, renderer, runtime)
    return ec, calls


def test_edit_controller_constructs_without_a_page():
    ec, _ = _controller()
    assert ec.vectors.e is ec
    assert ec.tuning.e is ec


def test_reason_message_maps_a_known_reason_and_ignores_unmapped():
    ec, _ = _controller()
    assert ec._reason_message(service.Reason.INVALID_PRESCALER) == _INVALID_PRESCALER
    assert ec._reason_message(None) is None


def test_act_ends_gestures_runs_action_then_requests_render():
    ec, calls = _controller()
    ec.act(lambda: calls.append("action"))
    assert calls == ["end_commit", "action", "request_render"]


def test_apply_outcome_ignore_does_nothing():
    ec, calls = _controller()
    committed = []
    ec._apply_outcome(service.IGNORE, lambda: committed.append(1))
    assert calls == []
    assert committed == []


def test_apply_outcome_rerender_rerenders_without_committing():
    ec, calls = _controller()
    committed = []
    ec._apply_outcome(service.RERENDER, lambda: committed.append(1))
    assert calls == ["render"]
    assert committed == []


def test_apply_outcome_accept_commits_then_requests_render():
    ec, calls = _controller()
    committed = []
    ec._apply_outcome(service.accept(), lambda: committed.append(1))
    assert committed == [1]
    assert calls == ["request_render"]


def test_apply_outcome_preview_arms_the_edit_candidate():
    ec, calls = _controller()

    def commit():
        return None

    ec._apply_outcome(service.accept(), commit, preview=True)
    assert ("edit_candidate", commit) in calls
