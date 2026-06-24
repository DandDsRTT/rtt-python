from types import SimpleNamespace

from rtt.app.rendering import _VIRT_REVIRT_STEP, Renderer


def _renderer(**host):
    return Renderer(None, None, None, SimpleNamespace(**host))


def test_renderer_constructs_without_a_page():
    r = _renderer()
    assert r.render_inflight is False
    assert r._last_rings == (frozenset(), frozenset())


def test_scrolled_past_overscan_detects_a_large_scroll():
    r = _renderer()
    ref = (0.0, 0.0, 1000.0, 800.0)
    assert r._scrolled_past_overscan((0.0, _VIRT_REVIRT_STEP, 1000.0, 800.0), ref)
    assert not r._scrolled_past_overscan((10.0, 10.0, 1000.0, 800.0), ref)


def test_scrolled_past_overscan_detects_a_viewport_resize():
    r = _renderer()
    ref = (0.0, 0.0, 1000.0, 800.0)
    assert r._scrolled_past_overscan((0.0, 0.0, 1200.0, 800.0), ref)
    assert r._scrolled_past_overscan((0.0, 0.0, 1000.0, 900.0), ref)


def test_body_visible_uses_the_current_viewport():
    r = _renderer()
    r._viewport = (0.0, 0.0, 100.0, 100.0)
    assert r._body_visible(0, 0, 10, 10, 0)
    assert not r._body_visible(0, 100000, 10, 10, 0)


def test_request_render_queues_a_followup_while_inflight(monkeypatch):
    monkeypatch.delenv("NICEGUI_USER_SIMULATION", raising=False)
    r = _renderer()
    r.render_inflight = True

    def again():
        return None

    r.request_render(after=again)
    assert r.render_again is True
    assert r.render_after is again


def test_on_viewport_ignores_malformed_args():
    r = _renderer()
    before = r._viewport
    r._on_viewport(SimpleNamespace(args={"l": "not-a-number"}))
    assert r._viewport == before


def test_on_viewport_updates_viewport_without_revirtualizing_when_stationary():
    r = _renderer()
    vp = (5.0, 6.0, 1000.0, 800.0)
    r._virt_for = vp
    r._on_viewport(SimpleNamespace(args={"l": 5.0, "t": 6.0, "w": 1000.0, "h": 800.0}))
    assert r._viewport == vp
