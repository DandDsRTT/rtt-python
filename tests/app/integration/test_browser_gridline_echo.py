import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

_PORT = 8208
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN = "RTT_BROWSER_SMOKE"

_POISON = "translateX(98765px)"

_MARK_TWINS = ".rtt-column-fill-inner .rtt-line { border-color:#ff00ff !important; }"

_A_SPACE_TAKING_SCROLLBAR_STANDING_IN_AS_A_BORDER = (
    ".rtt-gridbody { border-right:15px solid transparent; box-sizing:border-box; }"
)

_OWNS_TRANSFORM = """
(poison) => {
  const out = {};
  for (const sel of ['.rtt-column-fill-inner', '.rtt-column-head-inner']) {
    const el = document.querySelector(sel);
    const before = el.style.transform;
    el.style.transform = poison;
    out[sel] = getComputedStyle(el).transform;
    el.style.transform = before;
  }
  return out;
}
"""

_TWIN_DRIFT = """
() => {
  const app = document.querySelector('.rtt-app');
  const live = {};
  app.querySelectorAll('.rtt-gridcontent .rtt-line-v')
     .forEach(e => live[e.dataset.eid] = e.getBoundingClientRect().x);
  const drift = [];
  app.querySelectorAll('.rtt-column-fill-inner .rtt-line-v').forEach(e => {
    const twin = live[e.dataset.eid.replace('#fill', '')];
    if (twin !== undefined) drift.push(Math.abs(e.getBoundingClientRect().x - twin));
  });
  return {n: drift.length, worst: drift.length ? Math.max(...drift) : null};
}
"""

_COUNT_MARKED_PIXELS_IN_CHROMES_OWN_PNG_DECODER = """
async (frames) => {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', {willReadFrequently: true});
  const counts = [];
  for (const data of frames) {
    const bitmap = await new Promise((ok, no) => {
      const img = new Image();
      img.onload = () => ok(img);
      img.onerror = no;
      img.src = 'data:image/png;base64,' + data;
    });
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    ctx.drawImage(bitmap, 0, 0);
    const px = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let marked = 0;
    for (let i = 0; i < px.length; i += 4) {
      if (px[i] > 150 && px[i + 2] > 150 && px[i + 1] < 110) marked++;
    }
    counts.push(marked);
  }
  return counts;
}
"""


def _port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _serving(url: str, timeout: float = 40.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def served_app():
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(f"real-browser echo suite is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser echo suite")
    url = f"http://127.0.0.1:{_PORT}"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTEST_CURRENT_TEST" and not key.startswith("NICEGUI_")
    }
    child_env["PORT"] = str(_PORT)
    server = subprocess.Popen([sys.executable, "app.py"], cwd=_REPO_ROOT, env=child_env)
    try:
        if not _serving(f"{url}/"):
            pytest.fail(f"the app never began serving on {url}")
        yield url
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


@pytest.fixture(scope="module")
def browser(served_app):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        try:
            instance = driver.chromium.launch(channel="chrome", args=["--mute-audio"])
        except Exception as launch_failure:
            pytest.skip(f"no Chrome available for the browser suite: {launch_failure}")
        yield instance, served_app
        instance.close()


def _all_show_token() -> str:
    from rtt.app.editor import Editor
    from rtt.app.page_assets import _encode_state

    editor = Editor()
    editor.set_all_show(True)
    return _encode_state(editor.serialize())


@contextmanager
def _overflowing_grid(browser, width=760):
    instance, url = browser
    context = instance.new_context(viewport={"width": width, "height": 820},
                                   device_scale_factor=2)
    page = context.new_page()
    page.add_init_script("try { localStorage.setItem('rttTourSeen', '1'); } catch (e) {}")
    page.goto(f"{url}/?state={_all_show_token()}", wait_until="networkidle")
    page.wait_for_selector(".rtt-gridcontent", timeout=15000)
    page.evaluate("document.querySelector('.rtt-tour-root')?.remove()")
    page.wait_for_timeout(1500)
    body = page.locator(".rtt-gridbody").bounding_box()
    page.mouse.move(body["x"] + body["width"] / 2, body["y"] + body["height"] / 2)
    try:
        yield page, context
    finally:
        context.close()


def _scroll_to(page, x):
    page.evaluate(f"() => document.querySelector('.rtt-gridbody').scrollTo({x}, 0)")
    page.wait_for_timeout(400)


def _reach(page):
    return page.evaluate(
        "() => { const b = document.querySelector('.rtt-gridbody');"
        " return b.scrollWidth - b.clientWidth; }"
    )


def _fling_from_the_far_end(page, context, direction, steps=9):
    _scroll_to(page, 0 if direction > 0 else _reach(page))
    page.wait_for_timeout(600)
    step = max(60, int(_reach(page) * 0.8 / steps))
    start = page.evaluate("() => document.querySelector('.rtt-gridbody').scrollLeft")
    frames: list[str] = []
    session = context.new_cdp_session(page)
    session.on("Page.screencastFrame", lambda p: (
        frames.append(p["data"]),
        session.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}),
    ))
    session.send("Page.startScreencast", {"format": "png", "everyNthFrame": 1})
    for _ in range(steps):
        page.mouse.wheel(direction * step, 0)
        page.wait_for_timeout(14)
    page.wait_for_timeout(700)
    session.send("Page.stopScreencast")
    session.detach()
    end = page.evaluate("() => document.querySelector('.rtt-gridbody').scrollLeft")
    return frames, abs(end - start)


class TestTheBounceBridgeTwinsNeverSurfaceAsShadowGridlines:
    def test_the_scroll_timeline_owns_the_frozen_layers_transform_across_the_whole_range(
        self, browser
    ):
        with _overflowing_grid(browser) as (page, _):
            reach = _reach(page)
            assert reach > 200, "the fixture must overflow horizontally or there is no range to test"
            for where, x in (("the start", 0), ("mid-range", reach // 2), ("the end", reach)):
                _scroll_to(page, x)
                owned = page.evaluate(_OWNS_TRANSFORM, _POISON)
                for selector, computed in owned.items():
                    assert "98765" not in computed, (
                        f"at {where} of the scroll range the rtt-body-x animation stops driving "
                        f"{selector}, so a poisoned inline transform shows through. An animation "
                        "that falls out of effect anywhere in its range cannot be handed to the "
                        "compositor at all, so it samples on the MAIN thread and lags a fast fling "
                        "— which bares the columnfill twins as a second, shadowed set of vertical "
                        "gridlines. Keep both keyframe animations on animation-fill-mode:both."
                    )

    def test_the_twins_sit_exactly_under_their_live_rules_at_rest_and_at_full_scroll(self, browser):
        with _overflowing_grid(browser) as (page, _):
            reach = _reach(page)
            for x in (0, reach // 3, reach):
                _scroll_to(page, x)
                drift = page.evaluate(_TWIN_DRIFT)
                assert drift["n"] >= 4, "the bounce bridge must carry twins of the full-height rules"
                assert drift["worst"] < 0.5, (
                    f"at scrollLeft {x} the columnfill twins sit {drift['worst']}px off their live "
                    "rules. Nothing opaque covers them, so any offset at all shows as doubled "
                    "gridlines: the twins' keyframe range must equal the body's own scroll range."
                )

    def test_a_scrollbar_that_takes_space_does_not_shorten_the_twins_travel(self, browser):
        with _overflowing_grid(browser) as (page, _):
            page.add_style_tag(content=_A_SPACE_TAKING_SCROLLBAR_STANDING_IN_AS_A_BORDER)
            page.evaluate("() => window.rttFreeze && window.rttFreeze.fit()")
            page.wait_for_timeout(600)
            lost = page.evaluate(
                "() => { const b = document.querySelector('.rtt-gridbody');"
                " return Math.round(b.getBoundingClientRect().width) - b.clientWidth; }"
            )
            assert lost > 8, "the fixture must actually cost the scroller some client width"
            _scroll_to(page, _reach(page))
            drift = page.evaluate(_TWIN_DRIFT)
            assert drift["worst"] < 0.5, (
                f"with a {lost}px scrollbar eating the scroller's client width the twins end "
                f"{drift['worst']}px short of their live rules at full scroll. The keyframes size "
                "the range off the clip's BORDER box while the body scrolls over its CONTENT box, "
                "so every platform whose scrollbars take room (Linux, Windows, macOS set to always "
                "show them) gets a permanent shadow set at the right-hand end — and the frozen "
                "column titles go out of register with it."
            )

    def test_neither_direction_of_a_fast_fling_exposes_a_columnfill_twin(self, browser):
        with _overflowing_grid(browser) as (page, context):
            page.add_style_tag(content=_MARK_TWINS)
            page.wait_for_timeout(300)
            for direction, name in ((1, "rightward"), (-1, "leftward")):
                frames, travelled = _fling_from_the_far_end(page, context, direction)
                assert len(frames) > 4, "the screencast must catch the frames the fling composited"
                assert travelled > 200, (
                    "the fling has to keep MOVING the whole way: one that saturates at the end of "
                    "the range stops the board, and a layer that is not moving cannot be caught lagging"
                )
                counts = page.evaluate(_COUNT_MARKED_PIXELS_IN_CHROMES_OWN_PNG_DECODER, frames)
                bared = [n for n in counts if n > 40]
                assert not bared, (
                    f"a {name} fling bared the columnfill twins on {len(bared)} of {len(counts)} "
                    f"composited frames (worst {max(counts)} marked pixels). The twins are hidden "
                    "only by sitting exactly under their live rules, so a layer that samples the "
                    "scroll a frame late paints a whole second set of shadow gridlines."
                )
