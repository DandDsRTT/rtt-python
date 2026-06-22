"""Unit tests for the pure SVG-chart helpers in rtt.app.render_html."""

import signal

import pytest

from rtt.app.render_html import _chart_ticks


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
