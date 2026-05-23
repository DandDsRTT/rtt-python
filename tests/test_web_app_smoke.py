"""Light smoke coverage for the NiceGUI layer.

The interaction logic lives in (and is tested via) rtt.web.editor; here we only
guard that the page module imports/wires cleanly and that input parsing matches
the original app's parseInt semantics. Rendering itself is verified in a browser.
"""

import sys

import rtt.web.app as app


def test_app_module_exposes_entry_points():
    assert callable(app.index)
    assert callable(app.main)


def test_main_runs_server_with_reload_enabled(monkeypatch):
    captured = {}
    monkeypatch.setattr(sys, "argv", ["app.py"])
    monkeypatch.setattr(app.ui, "run", lambda **kwargs: captured.update(kwargs))
    app.main()
    assert captured["reload"] is True  # hot-reload: edits are picked up without a manual restart
    assert captured["port"] == 8137  # default dev port when no argv override is given
    assert captured["show"] is False


def test_parse_int_accepts_integers_and_rejects_partial_input():
    assert app._parse_int("5") == 5
    assert app._parse_int("-4") == -4
    assert app._parse_int("  3 ") == 3
    assert app._parse_int("") is None
    assert app._parse_int("-") is None
    assert app._parse_int("x") is None
    assert app._parse_int(None) is None


def test_ratio_parts_splits_fractions_and_passes_through_non_fractions():
    assert app._ratio_parts("3/2") == ("3", "2")  # rendered as a stacked fraction
    assert app._ratio_parts("2/1") == ("2", "1")
    assert app._ratio_parts("5") is None  # a bare integer is not a fraction
    assert app._ratio_parts("") is None


def test_cents_parts_splits_whole_and_fraction_for_decimal_alignment():
    assert app._cents_parts("1899.26") == ("1899", "26")  # big whole, small fraction
    assert app._cents_parts("-2.69") == ("-2", "69")
    assert app._cents_parts("0.00") == ("0", "00")
    assert app._cents_parts("5") == ("5", "")  # no fractional part


def test_bracket_svg_covers_exactly_the_glyphs_the_grid_emits():
    # value brackets are drawn as SVG (not font glyphs) so ⟨ doesn't render as a
    # curly brace; one renderer per glyph the grid emits, and no dead ones.
    from rtt.web.spreadsheet import LIST_BRACKETS, MAP_BRACKETS

    emitted = set(MAP_BRACKETS) | set(LIST_BRACKETS)  # ⟨ ] [
    for ch in emitted:
        svg = app._bracket_svg(ch)
        # non-scaling stroke => identical weight regardless of the cell it fills
        assert svg.startswith("<svg") and "non-scaling-stroke" in svg
    assert set(app._BRACKET_PARTS) == emitted  # no renderer for a glyph never drawn


def test_square_brackets_are_a_thick_bar_with_thin_serifs_angle_is_one_stroke():
    # point of the redesign: a thick main bar, thinner serifs, and an angle
    # bracket that is a single open stroke (no serifs)
    assert app._BR_BAR > app._BR_SERIF
    for ch in ("[", "]"):
        svg = app._bracket_svg(ch)
        assert svg.count("<path") == 3  # one main bar + two serifs
        assert f'stroke-width="{app._BR_BAR}"' in svg and f'stroke-width="{app._BR_SERIF}"' in svg
    assert app._bracket_svg("⟨").count("<path") == 1  # just the open polyline
