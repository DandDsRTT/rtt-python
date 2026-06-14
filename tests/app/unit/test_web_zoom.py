"""The zoom-on-hover magnifier's pure face builder (rtt.app.render_html.zoom_tip_html /
zoom_blank). Hovering a read-only gridded value pops a tooltip showing that SAME value face
enlarged, scaled so the small cents whole-part of "1200.000" reaches a normal integer cell's size.
These cover the markup + the blank suppression; the render-level attachment (which cells actually
get a magnifier) lives in tests/app/integration/test_web_render.py."""

import rtt.app.app as app
from rtt.app.render_html import ZOOM_KINDS, zoom_blank, zoom_tip_html

_F = app._CELL_FONT  # the integer-value cell font a small face is enlarged up to


def test_zoom_factor_lifts_the_cents_whole_part_to_the_integer_size():
    # the calibration: the .rtt-stacked-main whole-part (10px) times the zoom factor reaches the
    # normal integer gridded value's font (--cell-font = 17px), so a "1200.000" whole-part ends up
    # as big as a "1" cell. The CSS .rtt-zoom-scale scales by exactly this ratio.
    assert app._CELL_FONT / app._STACKED_MAIN_FONT == 1.7
    # zoom_tip_html emits the LIVE face classes (.rtt-zoom-scale wraps .rtt-stacked-main), so the
    # transform enlarges the identical face — the calibration lives in that one class.
    html = zoom_tip_html("tuningvalue", "1200.000", 37, _F)
    assert 'class="rtt-zoom-scale"' in html and 'class="rtt-stacked-main"' in html


def test_cents_face_stacks_whole_over_fraction():
    html = zoom_tip_html("tuningvalue", "1200.000", 37, _F)
    assert '<div class="rtt-stacked-main">1200</div>' in html
    assert '<div class="rtt-stacked-sub">.000</div>' in html


def test_integer_cents_renders_solo_with_no_fraction():
    # a whole cents value (no decimal) is solo at the full cell font, mirroring the live face's
    # rtt-stacked-solo flip — there is no .fraction to stack beneath it.
    html = zoom_tip_html("tuningvalue", "0", 37, _F)
    assert 'rtt-stacked-main rtt-stacked-solo">0<' in html
    assert "rtt-stacked-sub" not in html


def test_power_face_stacks_infinity_over_max_but_a_finite_power_is_solo():
    inf = zoom_tip_html("powerdisplay", "∞", 37, _F)
    assert '<div class="rtt-stacked-main">∞</div>' in inf
    assert '<div class="rtt-stacked-sub">(max)</div>' in inf
    assert "rtt-stacked-solo" not in inf
    assert 'rtt-stacked-solo">2<' in zoom_tip_html("powerdisplay", "2", 37, _F)


def test_genratio_keeps_the_approximate_marker_and_stacks_the_fraction():
    html = zoom_tip_html("genratio", "3/2", 37, _F)
    assert 'class="rtt-approx">~<' in html               # a generator ratio is approximate
    assert 'class="rtt-frac"' in html and "rtt-frac-whole" not in html
    assert ">3</div>" in html and ">2</div>" in html


def test_commaratio_is_exact_and_a_whole_ratio_collapses_to_a_big_integer():
    exact = zoom_tip_html("commaratio", "81/80", 37, _F)
    assert "rtt-approx" not in exact                      # a comma ratio carries no ~
    assert ">81</div>" in exact and ">80</div>" in exact
    whole = zoom_tip_html("genratio", "2/1", 37, _F)      # "n/1" -> a bare big integer
    assert "rtt-frac-whole" in whole


def test_mathexpr_reuses_the_stacked_closed_form():
    html = zoom_tip_html("mathexpr", "1200 · log₂(3/2)\n= 701.96", 37, _F)
    assert "rtt-mathexpr-stack" in html and "701.96" in html


def test_zoom_blank_suppresses_empty_and_dashed_values_but_not_real_ones():
    assert zoom_blank("") and zoom_blank("   ")           # quantities off -> blank
    assert zoom_blank("—/—") and zoom_blank("?/?") and zoom_blank("—")  # dashed / placeholder
    assert not zoom_blank("1200.000") and not zoom_blank("0") and not zoom_blank("3/2")


def test_zoom_kinds_are_the_read_only_value_faces():
    assert ZOOM_KINDS == frozenset({"tuningvalue", "genratio", "commaratio", "powerdisplay", "mathexpr"})
