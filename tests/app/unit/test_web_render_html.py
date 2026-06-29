"""Unit tests for the pure SVG-chart helpers in rtt.app.render_html."""

import signal

import pytest

from rtt.app.render_html import _chart_ticks, _rect_in_view


_VIEW = (100.0, 200.0, 400.0, 300.0)


class TestWebRenderHtml:
    @pytest.mark.parametrize(
        "lo, hi, expected",
        [
            (0.0, 10.0, [0.0, 2.5, 5.0, 7.5, 10.0, 12.5]),
            (-5.0, 5.0, [-5.0, -2.5, 0.0, 2.5, 5.0, 7.5]),
            (0.0, 0.0, [0.0, 1.0]),
        ],
    )
    def test_chart_ticks_lays_out_a_nice_axis(self, lo, hi, expected):
        assert _chart_ticks(lo, hi) == expected

    def test_chart_ticks_terminates_on_a_large_value_with_a_sub_ulp_span(self):
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

    @pytest.mark.parametrize(
        "x, y, width, height, overscan, expected",
        [
            (200.0, 260.0, 30.0, 20.0, 0.0, True),
            (200.0, 5000.0, 30.0, 20.0, 0.0, False),
            (5000.0, 260.0, 30.0, 20.0, 0.0, False),
            (520.0, 260.0, 30.0, 20.0, 0.0, False),
            (520.0, 260.0, 30.0, 20.0, 600.0, True),
            (300.0, 250.0, 0.0, 100.0, 0.0, True),
            (900.0, 250.0, 0.0, 100.0, 0.0, False),
            (60.0, 260.0, 40.0, 20.0, 0.0, False),
        ],
    )
    def test_rect_in_view_intersects_the_visible_window(self, x, y, width, height, overscan, expected):
        assert _rect_in_view(x, y, width, height, 50.0, _VIEW, overscan) is expected

    def test_rect_in_view_with_no_viewport_admits_everything(self):
        assert _rect_in_view(99999.0, 99999.0, 10.0, 10.0, 50.0, None, 0.0) is True
