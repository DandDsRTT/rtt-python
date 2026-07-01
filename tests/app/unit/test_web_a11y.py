import re

import pytest

from rtt.app import marks, page_assets, service, spreadsheet
from rtt.app.reconciler import _cell_role
from rtt.app.render_html_glyphs import _control_svg, _mode_svg, _wave_svg


def _meantone_cells():
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4)))).cells


class TestGlyphAccessibleNames:
    @pytest.mark.parametrize(
        "kind, name",
        [
            ("sine", "sine waveform"),
            ("square", "square waveform"),
            ("triangle", "triangle waveform"),
            ("sawtooth", "sawtooth waveform"),
        ],
    )
    def test_wave_glyph_is_named(self, kind, name):
        svg = _wave_svg(kind)
        assert 'role="img"' in svg
        assert f'aria-label="{name}"' in svg

    def test_every_wave_variant_in_the_bank_is_named(self):
        for svg in page_assets._AUDIO_GLYPHS["wave"]:
            assert 'role="img"' in svg
            assert 'aria-label="' in svg

    def test_mode_glyph_is_named(self):
        svg = _mode_svg(frozenset({(1, 1)}), "note")
        assert 'role="img"' in svg
        assert 'aria-label="note play mode"' in svg

    def test_every_mode_variant_in_the_bank_is_named(self):
        names = {
            re.search(r'aria-label="([^"]+)"', svg).group(1)
            for svg in page_assets._AUDIO_GLYPHS["mode"]
        }
        assert names == {
            "note play mode",
            "arpeggio play mode",
            "chord play mode",
            "rolled chord play mode",
        }

    @pytest.mark.parametrize(
        "glyph, name",
        [
            ("plus", "add"),
            ("minus", "remove"),
            ("expand", "expand"),
            ("collapse", "collapse"),
            ("reduce", "octave-reduce"),
            ("reciprocate", "reciprocate"),
        ],
    )
    def test_control_glyph_is_named(self, glyph, name):
        svg = _control_svg(glyph)
        assert "role='img'" in svg
        assert f"aria-label='{name}'" in svg

    def test_decorative_marks_svg_is_hidden_from_assistive_tech(self):
        assert 'aria-hidden="true"' in marks.svg(10, 10, "<rect/>")


class TestGridAriaSemantics:
    def test_every_in_grid_cell_carries_an_aria_label(self):
        cells = _meantone_cells()
        in_grid = [c for c in cells if c.in_grid]
        assert in_grid
        assert all(c.aria for c in in_grid)

    def test_aria_label_names_row_column_and_value(self):
        cells = {c.id: c for c in _meantone_cells()}
        assert cells["prime:0"].aria == "interval ratios, domain primes, 2"
        assert cells["tuning:generator:0"].aria == "tuning, generators, 1200.000"

    def test_aria_label_uses_no_private_use_glyphs(self):
        for c in _meantone_cells():
            assert not any("\ue000" <= ch <= "\uf8ff" for ch in c.aria)

    def test_non_grid_cells_get_no_aria(self):
        cells = _meantone_cells()
        assert all(not c.aria for c in cells if not c.in_grid)

    @pytest.mark.parametrize(
        "in_grid, kind, expected",
        [
            (True, "mapped", "gridcell"),
            (True, "ratio_cell", "gridcell"),
            (False, "column_header", "columnheader"),
            (False, "row_label", "rowheader"),
            (False, "count", None),
            (False, "columntoggle", None),
        ],
    )
    def test_cell_role_by_kind(self, in_grid, kind, expected):
        from rtt.app.layout import CellBox

        cb = CellBox("x", 0, 0, 10, 10, kind, in_grid=in_grid)
        assert _cell_role(cb) == expected


class TestFocusAndTargetAssets:
    def _asset(self, name):
        from rtt.app.page_assets import _ASSETS

        return (_ASSETS / name).read_text(encoding="utf-8")

    def test_active_cell_js_uses_roving_tabindex(self):
        js = self._asset("activecell.js")
        assert "tabIndex" in js
        assert "applyRoving" in js

    def test_active_cell_js_focuses_on_keyboard_move(self):
        js = self._asset("activecell.js")
        move = js[js.index("function moveTo") : js.index("function beginEdit")]
        assert ".focus(" in move

    def test_css_gives_in_grid_marks_a_larger_hit_target(self):
        css = self._asset("rtt.css")
        assert ".rtt-control-check .q-checkbox::before" in css
        assert "width:24px" in css
        assert "@media (pointer:coarse)" in css
        assert "width:44px" in css

    def test_css_shows_a_keyboard_focus_ring_on_value_cells(self):
        css = self._asset("rtt.css")
        assert ".rtt-cell:focus-visible" in css

    def test_dark_mode_recolors_the_base_caption_not_only_the_disabled_variant(self):
        dark = self._asset("rtt-dark.css")
        assert re.search(r"body\.rtt-dark\s+\.rtt-caption\s*[,{]", dark)
