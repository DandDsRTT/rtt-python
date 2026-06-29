"""Unit tests for the pure SVG-chart helpers in rtt.app.render_html."""

import signal

import pytest

from rtt.app.render_html import _chart_ticks, _rect_in_view


@pytest.mark.parametrize(
    "lo, hi, expected",
    [
        # a clean 0..10 span steps by 2.5 (the 1/2/2.5/5/10 ladder picks 2.5 for span/4 = 2.5)
        (0.0, 10.0, [0.0, 2.5, 5.0, 7.5, 10.0, 12.5]),
        # a symmetric span keeps zero on a tick
        (-5.0, 5.0, [-5.0, -2.5, 0.0, 2.5, 5.0, 7.5]),
        # a degenerate (zero) span falls back to a unit interval rather than dividing by zero
        (0.0, 0.0, [0.0, 1.0]),
    ],
)
def test_chart_ticks_lays_out_a_nice_axis(lo, hi, expected):
    assert _chart_ticks(lo, hi) == expected


def test_chart_ticks_terminates_on_a_large_value_with_a_sub_ulp_span():
    # regression: when lo is large and the span is smaller than the float ULP of lo, the old
    # accumulator loop's `v += step` never advanced v, so `while v <= stop` spun forever (this
    # hung the optimization+charts render under coverage when a near-degenerate damage span fed
    # the chart). The bounded tick count must terminate and return a finite, usable axis.
    timed_out = False

    def _raise(signum, frame):
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, 3)
    try:
        ticks = _chart_ticks(1e10, 1e10 + 2e-6)
    except TimeoutError:
        timed_out = True
        ticks = []
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)

    assert not timed_out, "_chart_ticks must not loop forever on a sub-ULP span"
    assert len(ticks) >= 2


# Viewport virtualization predicate: which body rects intersect the visible scroll rectangle. The
# view is (scrollLeft, scrollTop, clientW, clientH); a body item sits at board-local (x, y - fy), the
# frame the scroll metrics use. Overscan inflates the rectangle on every edge. fy=50 throughout, so a
# cell's grid-y is shifted up by 50 before testing.
_VIEW = (100.0, 200.0, 400.0, 300.0)  # visible x:[100,500] board-y:[200,500]


@pytest.mark.parametrize(
    "x, y, width, height, overscan, expected",
    [
        # squarely inside the visible window (grid-y 260 → board-y 210, within [200,500])
        (200.0, 260.0, 30.0, 20.0, 0.0, True),
        # far below the window with no overscan — elided
        (200.0, 5000.0, 30.0, 20.0, 0.0, False),
        # far to the right of the window — elided
        (5000.0, 260.0, 30.0, 20.0, 0.0, False),
        # just past the right edge (board x starts at 520 > 500) with no overscan — elided
        (520.0, 260.0, 30.0, 20.0, 0.0, False),
        # ...but overscan of 600 pulls it back in
        (520.0, 260.0, 30.0, 20.0, 600.0, True),
        # a zero-width vertical gridline whose x sits inside the window is kept
        (300.0, 250.0, 0.0, 100.0, 0.0, True),
        # a zero-width gridline outside the window (with no overscan) is elided
        (900.0, 250.0, 0.0, 100.0, 0.0, False),
        # touching the left edge exactly: x+w == left is NOT an intersection (strict >)
        (60.0, 260.0, 40.0, 20.0, 0.0, False),
    ],
)
def test_rect_in_view_intersects_the_visible_window(x, y, width, height, overscan, expected):
    assert _rect_in_view(x, y, width, height, 50.0, _VIEW, overscan) is expected


def test_rect_in_view_with_no_viewport_admits_everything():
    # view is None before the client reports its scroll rectangle (and when virtualization is off):
    # every rect, however far out, is materialized.
    assert _rect_in_view(99999.0, 99999.0, 10.0, 10.0, 50.0, None, 0.0) is True
