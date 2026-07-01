from types import SimpleNamespace

from rtt.app.rendering import _VIRT_REVIRT_STEP, Renderer


def _renderer(chrome=None, runtime=None):
    return Renderer(
        None, None, None, chrome or SimpleNamespace(), runtime or SimpleNamespace(), None
    )


class TestWebRendering:
    def test_renderer_constructs_without_a_page(self):
        r = _renderer()
        assert r.render_inflight is False
        assert r._last_rings == (frozenset(), frozenset())

    def test_scrolled_past_overscan_detects_a_large_scroll(self):
        r = _renderer()
        ref = (0.0, 0.0, 1000.0, 800.0)
        assert r._scrolled_past_overscan((0.0, _VIRT_REVIRT_STEP, 1000.0, 800.0), ref)
        assert not r._scrolled_past_overscan((10.0, 10.0, 1000.0, 800.0), ref)

    def test_scrolled_past_overscan_detects_a_viewport_resize(self):
        r = _renderer()
        ref = (0.0, 0.0, 1000.0, 800.0)
        assert r._scrolled_past_overscan((0.0, 0.0, 1200.0, 800.0), ref)
        assert r._scrolled_past_overscan((0.0, 0.0, 1000.0, 900.0), ref)

    def test_body_visible_uses_the_current_viewport(self):
        r = _renderer()
        r._viewport = (0.0, 0.0, 100.0, 100.0)
        assert r._body_visible(0, 0, 10, 10, 0)
        assert not r._body_visible(0, 100000, 10, 10, 0)

    def test_request_render_queues_a_followup_while_inflight(self, monkeypatch):
        monkeypatch.delenv("NICEGUI_USER_SIMULATION", raising=False)
        r = _renderer()
        r.render_inflight = True

        def again():
            return None

        r.request_render(after=again)
        assert r.render_again is True
        assert r.render_after is again

    def test_on_viewport_ignores_malformed_args(self):
        r = _renderer()
        before = r._viewport
        r._on_viewport(SimpleNamespace(args={"l": "not-a-number"}))
        assert r._viewport == before

    def test_on_viewport_updates_viewport_without_revirtualizing_when_stationary(self):
        r = _renderer()
        vp = (5.0, 6.0, 1000.0, 800.0)
        r._virt_for = vp
        r._on_viewport(SimpleNamespace(args={"l": 5.0, "t": 6.0, "w": 1000.0, "h": 800.0}))
        assert r._viewport == vp

    def _commit_renderer(self, calls, received, side_effect=None):
        gestures = SimpleNamespace(
            gesture=None, gesture_rendering=False, rank_rendering=False, rank_remove=None
        )
        runtime = SimpleNamespace(last_lay=None)
        sentinel = object()

        def layout(**kwargs):
            calls.append(kwargs)
            if side_effect is not None:
                side_effect(len(calls))
            return sentinel

        r = Renderer(
            SimpleNamespace(layout=layout), None, gestures, None, runtime, None
        )
        r.render = lambda prebuilt=None: received.append(prebuilt)
        return r, sentinel

    async def test_commit_render_builds_layout_once_and_reuses_it(self, monkeypatch):
        monkeypatch.delenv("NICEGUI_USER_SIMULATION", raising=False)
        calls, received = [], []
        r, sentinel = self._commit_renderer(calls, received)
        await r._commit_render()
        assert len(calls) == 1, "the off-loop build is the render's only layout computation"
        assert received == [sentinel], "render reuses the off-loop layout instead of rebuilding it"

    async def test_commit_render_rebuilds_when_state_changed_during_the_build(self, monkeypatch):
        monkeypatch.delenv("NICEGUI_USER_SIMULATION", raising=False)
        calls, received = [], []

        def race(n):
            if n == 1:
                r.render_again = True

        r, sentinel = self._commit_renderer(calls, received, side_effect=race)
        await r._commit_render()
        assert received[0] is None, "a request that arrived mid-build must force an on-loop rebuild"
        assert received[-1] is sentinel, "the follow-up render then reuses a fresh off-loop build"
