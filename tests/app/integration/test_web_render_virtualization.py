import asyncio
import copy
import logging
import re
import sys
from fractions import Fraction
from types import SimpleNamespace
import nicegui.ui as ui
import pytest
from nicegui import core
from nicegui.element_filter import ElementFilter
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from rtt.app import app as web_app
from rtt.app import rendering as web_rendering
from rtt.app import _editing_tuning, page_assets, service, spreadsheet, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.editor import Editor
from _render_support import _toggle, _live_render, _live_page, _body_cells


class TestViewportVirtualization:
    async def test_virtualization_elides_offscreen_body_cells(self, user: User, monkeypatch) -> None:
        monkeypatch.setenv("RTT_VIRT_VIEWPORT", "320x320")
        await user.open("/")
        live, page = _live_page()
        lay, fx, fy, body = _body_cells(live, page)

        visible = {c.id for c in body if page.renderer._body_visible(c.x, c.y, c.width, c.height, fy)}
        offscreen = {c.id for c in body} - visible
        assert offscreen, "a 320x320 viewport must leave some body cells off-screen to elide"

        for cid in offscreen:
            assert cid not in page.rec.entities
        for cid in visible:
            assert cid in page.rec.entities
        for c in lay.cells:
            if _live_render()._freeze_container(c, fx, fy) != "body":
                assert c.id in page.rec.entities

    async def test_scrolling_reveals_far_cells_and_retains_near_ones(self, user: User, monkeypatch) -> None:
        monkeypatch.setenv("RTT_VIRT_VIEWPORT", "320x320")
        await user.open("/")
        live, page = _live_page()
        lay, fx, fy, body = _body_cells(live, page)

        far = max(body, key=lambda c: c.y)
        near = min(body, key=lambda c: c.x + c.y)
        assert far.id not in page.rec.entities
        assert near.id in page.rec.entities

        page.renderer._on_viewport(SimpleNamespace(args={"l": far.x, "t": far.y - fy, "w": 320, "h": 320}))
        assert far.id in page.rec.entities
        assert not page.renderer._body_visible(near.x, near.y, near.width, near.height, fy), "...and the now-far-above near cell is RETAINED, not evicted — a scroll only ever ADDS, so # scrolling back to it never re-blanks (the regression this fixes)"
        assert near.id in page.rec.entities

    async def test_background_fill_materializes_every_deferred_cell(self, user: User, monkeypatch) -> None:
        monkeypatch.setenv("RTT_VIRT_VIEWPORT", "320x320")
        await user.open("/")
        live, page = _live_page()
        lay, fx, fy, body = _body_cells(live, page)
        deferred = [c.id for c in body if c.id not in page.rec.entities]
        assert deferred, "a 320x320 viewport must defer some off-screen cells at cold paint"

        await page.renderer._fill_offscreen(page.renderer._fill_gen)

        for c in lay.cells:
            assert c.id in page.rec.entities, f"fill left {c.id} unmaterialized"

    async def test_revirtualize_keeps_offscreen_scroll_within_overscan_cheap(self, user: User, monkeypatch) -> None:
        monkeypatch.setenv("RTT_VIRT_VIEWPORT", "320x320")
        await user.open("/")
        live, page = _live_page()
        before = set(page.rec.entities)
        page.renderer._on_viewport(SimpleNamespace(args={"l": 4, "t": 4, "w": 320, "h": 320}))
        assert set(page.rec.entities) == before

    def test_scrolled_past_overscan_only_fires_past_the_step_or_on_resize(self) -> None:
        P = web_rendering.Renderer
        dummy = object.__new__(P)
        step = web_rendering._VIRT_REVIRT_STEP
        ref = (0.0, 0.0, 400.0, 300.0)
        assert P._scrolled_past_overscan(dummy, (step + 1, 0.0, 400.0, 300.0), ref) is True
        assert P._scrolled_past_overscan(dummy, (0.0, step + 1, 400.0, 300.0), ref) is True
        assert P._scrolled_past_overscan(dummy, (0.0, 0.0, 401.0, 300.0), ref) is True
        assert P._scrolled_past_overscan(dummy, (0.0, 0.0, 400.0, 299.0), ref) is True
        assert P._scrolled_past_overscan(dummy, (5.0, 5.0, 400.0, 300.0), ref) is False

    def test_on_viewport_ignores_a_malformed_payload(self) -> None:
        P = web_rendering.Renderer
        dummy = object.__new__(P)
        assert P._on_viewport(dummy, SimpleNamespace(args={})) is None
        assert P._on_viewport(dummy, SimpleNamespace(args=None)) is None

    async def test_structural_newborns_are_withheld_scroll_materializations_are_not(self, user: User) -> None:
        await user.open("/")
        live, page = _live_page()
        before = set(page.rec.entities)
        _toggle(user, "charts")
        await user.should_see(marker="chart:retune:targets")
        newborns = set(page.rec.entities) - before
        assert newborns, "enabling charts must add cells"
        assert any("rtt-withhold" in page.rec.entities[cid].el._classes for cid in newborns), \
            "a structurally-born cell must be withheld for the two-step entrance"
        assert all("rtt-noentry" not in page.rec.entities[cid].el._classes for cid in newborns), \
            "rtt-noentry is only for scroll materialization, never a structural newborn"
