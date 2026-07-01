from functools import partial

import pytest

from rtt.app import (
    grid_tables,
    service,
    settings,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_geometry_query as query,
    spreadsheet_models,
    spreadsheet_text,
)
from rtt.app.editor import Editor
from rtt.app.layout import CellBox, Layout
from rtt.app.spreadsheet_decorations import _tile_groups
from rtt.app.spreadsheet_geometry import plain_text_band
from _spreadsheet_support import _memoized_build, _layout, _with, _with_interest, _INTEREST


class TestInterestTilesAndFolds:
    def test_the_target_list_plain_text_becomes_a_two_tone_draft_box_while_pending(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["plain_text_values"] = True
        drafting = {c.id: c for c in spreadsheet.build(base, s, pending_target=[None, None, None]).cells}
        assert drafting["plain_text:vectors:targets"].kind == "plain_text_pending"
        resting = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert resting["plain_text:vectors:targets"].kind == "plain_text_edit"

    def test_adding_intervals_of_interest_never_shrinks_the_header(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        builds = [spreadsheet.build(base, collapsed=frozenset(), interest=[(0, 0, 0)] * n) for n in range(5)]
        widths = [{c.id: c for c in layout.cells}["header:interest"].width for layout in builds]
        assert widths == sorted(widths)
        assert min(widths) == widths[0]

    def test_interest_tiles_and_footprint_hug_their_content_the_title_overhangs(self):
        layout = _with_interest(_INTEREST[:1])
        cells = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        content_width = 2 * spreadsheet_constants.BRACKET_WIDTH + 1 * spreadsheet_constants.COLUMN_WIDTH
        floor = max(spreadsheet_text._min_width_for_lines(grid_tables.CAPTIONS[(rk, "interest")], spreadsheet_constants.MAX_CAPTION_LINES)
                    for rk in ("vectors", "mapping", "tuning", "just", "retune"))
        hug_width = max(content_width, floor)
        assert blocks["block:interest"].width == hug_width + 2 * spreadsheet_constants.PAD, "the tile hugs that width — just its PAD overhang each side (the + rides the fan, not the tile)"
        assert cells["header:interest"].width == hug_width
        assert cells["header:interest"].width < spreadsheet_text._title_w("other intervals\nof interest")

    def test_interest_title_overhangs_symmetrically_centred_on_the_gridline(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        title_w = spreadsheet_text._title_w("other intervals\nof interest")
        for mi in range(3):
            layout = spreadsheet.build(base, collapsed=frozenset(), interest=[(0, 0, 0)] * mi)
            cells = {c.id: c for c in layout.cells}
            lines = {line.id: line for line in layout.lines}
            header, trunk = cells["header:interest"], lines["trunk:interest"]
            assert header.width < title_w
            assert header.x + header.width / 2 == trunk.position
        one = _with_interest(_INTEREST[:1])
        cells = {c.id: c for c in one.cells}
        lines = {line.id: line for line in one.lines}
        block = {b.id: b for b in one.blocks}["block:interest"]
        trunk = lines["trunk:interest"]
        assert block.width < title_w
        assert block.x + block.width / 2 == trunk.position
        assert lines["v:interest:0"].position == trunk.position

    def test_per_tile_fold_toggle_hugs_its_tile_corner(self):
        layout = _with_interest(_INTEREST[:1])
        cells = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        for toggle_id, block_id in (("toggle:tile:vectors:interest", "block:vector:interest"),
                                    ("toggle:tile:mapping:primes", "block:mapping")):
            toggle, tile = cells[toggle_id], blocks[block_id]
            assert toggle.x == tile.x + spreadsheet_constants.TOGGLE_INSET
            assert tile.x <= toggle.x <= tile.x + tile.width, "...so it sits within the tile"

    def test_populated_interest_mapped_list_is_standalone_columns_not_a_matrix(self):
        cells = {c.id: c for c in _with_interest(_INTEREST[:2]).cells}
        assert {"ebktop:imapped:0", "ebkbrace:imapped:0",
                "ebktop:imapped:1", "ebkbrace:imapped:1"} <= set(cells)
        assert "bracket:imapped:l" not in cells and "bracket:imapped:r" not in cells
        assert not any(c.startswith("sep:imapped:") for c in cells)
        assert not any(c.startswith(("bracket:tuning:ilist", "bracket:just:ilist", "bracket:retune:ilist")) for c in cells), "the tempered/just/retuning size rows drop their list brackets too — the whole interest # column is a loose collection, not a matrix/list, so its values stand bare (per the mockup)"

    def test_populated_interest_has_per_interval_axes_and_panels(self):
        layout = _with_interest(_INTEREST[:3])
        ids = {line.id for line in layout.lines}
        assert {"v:interest:0", "v:interest:1", "v:interest:2"} <= ids
        assert {"trunk:interest", "bus:interest:top", "bus:interest:bot", "foot:interest"} <= ids
        blocks = {b.id for b in layout.blocks}
        assert {"block:interest", "block:imapped", "block:tuning:interest", "block:vector:interest"} <= blocks
        assert "block:damage:interest" not in blocks

    def test_collapsing_interest_hides_its_cells_but_keeps_the_header(self):
        coll = _with_interest(_INTEREST[:2], collapsed={"column:interest"})
        cids = {c.id for c in coll.cells}
        assert not any(c.startswith(("interest:", "cell:imapped:", "cell:interest:", "tuning:interest:")) for c in cids)
        assert "header:interest" in cids and "toggle:column:interest" in cids
        assert "cell:mapped:0:0" in cids

    def test_interest_captions_match_the_mockup_names(self):
        cells = {c.id: c for c in _with_interest(_INTEREST[:1]).cells}
        assert cells["caption:vectors:interest"].text == "intervals of interest"
        assert cells["caption:mapping:interest"].text == "mapped intervals"
        assert cells["caption:tuning:interest"].text == "tempered interval sizes"
        assert cells["caption:just:interest"].text == "(just) interval sizes"
        assert cells["caption:retune:interest"].text == "interval retunings"
        assert "caption:damage:interest" not in cells

    def test_mnemonics_underline_the_symbol_letter_within_the_name_captions(self):
        on = {c.id: c for c in _with(names=True, mnemonics=True).cells}
        off = {c.id: c for c in _with(names=True, mnemonics=False).cells}
        cap = on["caption:mapping:primes"]
        assert cap.text == "(temperament) mapping"
        assert cap.underlines == ((cap.text.index("mapping"), 1),)
        assert off["caption:mapping:primes"].underlines == ()

    def test_mnemonics_mark_each_quantitys_symbol_letter_and_skip_the_symbolless_ones(self):
        on = {c.id: c for c in _with(names=True, mnemonics=True).cells}

        def underlined(cell_id):
            c = on[cell_id]
            return "".join(c.text[s:s + n] for s, n in c.underlines)

        assert underlined("caption:tuning:primes") == "t"
        assert underlined("caption:just:primes") == "j"
        assert underlined("caption:retune:primes") == "r"
        assert underlined("caption:retune:targets") == "e"
        assert underlined("caption:damage:targets") == "d"
        assert on["caption:mapping:targets"].underlines == ()
        assert on["caption:tuning:targets"].underlines == ()
        assert on["caption:just:targets"].underlines == ()

    def test_interval_basis_captions_underline_their_symbol_letters(self):
        on = {c.id: c for c in _with(names=True, mnemonics=True).cells}

        def underlined(cell_id):
            c = on[cell_id]
            return "".join(c.text[s:s + n] for s, n in c.underlines)

        assert underlined("caption:vectors:commas") == "c"
        assert underlined("caption:vectors:targets") == "t"

    def test_symbols_toggles_in_tile_symbol_glyphs_above_the_names(self):
        on = {c.id: c for c in _with(symbols=True, names=True, equivalences=False).cells}
        off = {c.id: c for c in _with(symbols=False, equivalences=False).cells}
        assert on["symbol:mapping:primes"].text == "𝑀"
        assert on["symbol:mapping:targets"].text == "Y"
        assert on["symbol:vectors:targets"].text == "T"
        assert on["symbol:vectors:commas"].text == "C"
        assert on["symbol:tuning:primes"].text == "𝒕"
        assert on["symbol:tuning:targets"].text == "𝐚"
        assert on["symbol:damage:targets"].text == "𝐝"
        assert not any(c.startswith("symbol:") for c in off)
        assert on["symbol:mapping:primes"].y < on["caption:mapping:primes"].y
        assert {"label:mapping", "header:primes"} <= set(on)

    def test_symbol_takes_the_label_slot_and_pushes_the_name_down(self):
        both = {c.id: c for c in _with(symbols=True, names=True).cells}
        sym_only = {c.id: c for c in _with(symbols=True, names=False).cells}
        assert sym_only["symbol:tuning:primes"].y == sym_only["tuning:prime:0"].y + spreadsheet_constants.ROW_HEIGHT + spreadsheet_constants.BAND_GAP
        assert not any(c.startswith("caption:") for c in sym_only)
        assert both["caption:tuning:primes"].y == both["symbol:tuning:primes"].y + spreadsheet_constants.SYMBOL_HEIGHT

    def test_folding_a_row_drops_its_symbols_with_the_rest_of_its_content(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["symbols"] = True
        cells = {c.id for c in spreadsheet.build(base, s, collapsed={"row:tuning"}).cells}
        assert not any(c.startswith("symbol:tuning:") for c in cells)
        assert "symbol:just:primes" in cells

    def test_comma_column_symbols_are_map_times_basis_products(self):
        on = {c.id: c for c in _with(symbols=True, names=True, equivalences=False).cells}
        assert on["symbol:vectors:commas"].text == "C", "the comma basis C lives in the interval-vectors row; the comma column has no # dedicated letters, so the rest are products of the maps and that basis"
        assert on["symbol:mapping:commas"].text == "𝑀C"
        assert on["symbol:tuning:commas"].text == "𝒕C"
        assert on["symbol:just:commas"].text == "𝒋C"
        assert on["symbol:retune:commas"].text == "𝒓C"
        assert on["symbol:tuning:commas"].y == on["symbol:tuning:primes"].y

    def test_other_intervals_of_interest_column_carries_no_symbols(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["symbols"] = True
        cells = {c.id: c for c in spreadsheet.build(base, s, interest=((-1, 1, 0),)).cells}
        assert not any(c.startswith("symbol:") and c.endswith(":interest") for c in cells)
        assert cells["caption:tuning:interest"].y == cells["caption:tuning:primes"].y

    def test_counts_row_reserves_no_symbol_slot_so_its_captions_dont_shift(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        def caps(symbols):
            s = settings.defaults()
            s["counts"], s["symbols"] = True, symbols
            return {c.id: c for c in spreadsheet.build(base, s).cells}

        on, off = caps(symbols=True), caps(symbols=False)
        assert not any(c.startswith("symbol:counts:") for c in on), "the counts row carries no symbol (its r/d/n/k ride the value cells), so turning # symbols on must not reserve a slot that would drift its captions down"
        assert on["caption:counts:primes"].y == off["caption:counts:primes"].y

    def test_every_implemented_toggle_actually_changes_the_layout(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        base_for = {"form": service.from_mapping(((1, 0, -4), (0, 1, 4)))}

        def snapshot(s, key_base=base):
            layout = spreadsheet.build(key_base, s, tuning_scheme="TILT minimax-S")
            return (
                frozenset((c.id, c.x, c.y, c.width, c.height, c.kind, c.text, c.unit, c.underlines) for c in layout.cells),
                frozenset((b.id, b.x, b.y, b.width, b.height, b.tint) for b in layout.blocks),
            )

        rides_on = {"form": "symbols", "form_colorization": "form_tiles"}

        def with_parents_on(key):
            s = settings.defaults()
            for parent in settings.ancestors_of(key):
                s[parent] = True
            if key in rides_on:
                s[rides_on[key]] = True
            return s

        MODE_TOGGLES = {"custom_weights"}
        BEHAVIOUR_TOGGLES = {"animations", "preview_highlighting", "tooltips", "mapping_demos"}
        for key in settings.IMPLEMENTED:
            if key in settings.GROUPING_PARENTS or key in MODE_TOGGLES or key in BEHAVIOUR_TOGGLES:
                continue
            kb = base_for.get(key, base)
            on, off = with_parents_on(key), with_parents_on(key)
            on[key], off[key] = True, False
            assert snapshot(on, kb) != snapshot(off, kb), f"{key} is marked implemented but changes nothing"

    def test_equivalences_extend_the_symbol_line_with_the_defining_equation(self):
        on = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
        sym_only = {c.id: c for c in _with(symbols=True, equivalences=False).cells}
        assert sym_only["symbol:tuning:primes"].text == "𝒕", "equivalences appends the '= …' continuation to the symbol, in the same cell — # no separate equation cell. Glyphs match SYMBOLS (𝒕 = 𝒈𝑀, not faux-styled)"
        assert on["symbol:tuning:primes"].text == "𝒕 = 𝒈𝑀"
        assert on["symbol:retune:primes"].text == "𝒓 = 𝒕 − 𝒋"
        assert on["symbol:mapping:targets"].text == "Y = 𝑀T"
        assert on["symbol:tuning:targets"].text == "𝐚 = 𝒕T = 𝒈𝑀T"
        assert on["symbol:retune:targets"].text == "𝐞 = 𝒕T − 𝒋T = 𝐚 − 𝐨 = 𝒓T"
        assert not any(c.startswith("equivalence:") for c in on)

    def test_equivalences_cover_derived_quantities_but_not_the_fundamentals(self):
        on = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
        extended = {c.split("symbol:", 1)[1] for c in on
                    if c.startswith("symbol:") and " = " in on[c].text}
        assert extended == {
            "mapping:commas", "mapping:targets", "tuning:primes", "tuning:targets",
            "just:targets", "retune:primes", "retune:targets", "damage:targets",
        }
        assert on["symbol:mapping:primes"].text == "𝑀", "the temperament mapping and just tuning map have no buildable continuation yet # (theirs need the canonical-form / superspace features), so their symbol is bare"
        assert on["symbol:just:primes"].text == "𝒋"

    def test_equivalences_alone_render_the_symbol_line_only_where_there_is_an_equation(self):
        eq_only = {c.id: c for c in _with(names=False, symbols=False, equivalences=True).cells}
        assert eq_only["symbol:tuning:primes"].text == "𝒕 = 𝒈𝑀", "the equation needs its left-hand side, so equivalences renders the symbol line # (symbol + continuation) even with symbols and names both off"
        assert "symbol:mapping:primes" not in eq_only, "...but only where there is a continuation to show — a bare symbol is the # symbols feature's job, so the equation-less fundamentals stay absent"
        assert "symbol:just:primes" not in eq_only
        assert not any(c.startswith("caption:") for c in eq_only)

    def test_header_symbols_label_each_matrix_row_or_column_with_a_subscripted_glyph(self):
        on = {c.id: c for c in _with(header_symbols=True, names=True).cells}
        off = {c.id: c for c in _with(header_symbols=False).cells}

        assert on["matrix_label:row:mapping:primes:0"].text == "𝒎₁"
        assert on["matrix_label:row:mapping:primes:1"].text == "𝒎₂"

        assert on["matrix_label:column:vectors:commas:0"].text == "𝐜₁"
        assert on["matrix_label:column:vectors:targets:0"].text == "𝐭₁"
        assert on["matrix_label:column:vectors:targets:7"].text == "𝐭₈"

        assert on["matrix_label:column:tuning:primes:0"].text == "𝒕₁"
        assert on["matrix_label:column:tuning:primes:2"].text == "𝒕₃"

        assert on["matrix_label:column:tuning:commas:0"].text == "𝒕𝐜₁"
        assert on["matrix_label:column:mapping:commas:0"].text == "𝑀𝐜₁"

        assert on["matrix_label:column:mapping:targets:0"].text == "𝐲₁", "The mapped target list Y is itself a list of vectors, so its column label is # the renamed bold-upright 𝐲 + subscript"
        assert on["matrix_label:column:tuning:targets:0"].text == "a₁", "The six target SIZE lists hold SCALARS per cell, so each indexed label is the # bare PLAIN-ASCII letter (neither bold nor italic) — the bold form names the list # (𝐚, 𝐨, 𝐞, 𝒘, 𝐝, 𝒄); the indexed scalar is a/o/e/w/d/c. Plain ASCII passes through # _math_html as plain serif text, with the index subscripted via Unicode"
        assert on["matrix_label:column:just:targets:0"].text == "o₁"
        assert on["matrix_label:column:retune:targets:0"].text == "e₁"
        assert on["matrix_label:column:damage:targets:0"].text == "d₁"

        assert not any(c.startswith("matrix_label:") for c in off), "Header symbols off drops every label (independent of the in-tile symbol/equivalence cells)"

    def test_in_tile_symbols_and_header_symbols_toggle_independently(self):
        sym_only = {c.id for c in _with(symbols=True, header_symbols=False, equivalences=False).cells}
        hdr_only = {c.id for c in _with(symbols=False, header_symbols=True, equivalences=False).cells}
        assert "symbol:tuning:primes" in sym_only
        assert not any(c.startswith("matrix_label:") for c in sym_only)
        assert any(c.startswith("matrix_label:") for c in hdr_only)
        assert not any(c.startswith("symbol:") for c in hdr_only)

    def test_matrix_labels_index_match_their_matrix_size(self):
        on = {c.id for c in _with(header_symbols=True).cells}
        assert {f"matrix_label:row:mapping:primes:{i}" for i in range(2)} <= on
        assert "matrix_label:row:mapping:primes:2" not in on
        assert {f"matrix_label:column:vectors:targets:{j}" for j in range(8)} <= on
        assert "matrix_label:column:vectors:targets:8" not in on
        assert {f"matrix_label:column:tuning:primes:{p}" for p in range(3)} <= on
        assert "matrix_label:column:tuning:primes:3" not in on

    def test_matrix_labels_only_emit_where_the_tile_is_open(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["header_symbols"] = True
        cells = {c.id for c in spreadsheet.build(base, s, collapsed={"row:mapping"}).cells}
        assert not any(c.startswith("matrix_label:row:mapping:") for c in cells)
        assert "matrix_label:column:vectors:commas:0" in cells

    def test_matrix_labels_sit_above_or_left_of_the_cells_they_label(self):
        on = {c.id: c for c in _with(header_symbols=True).cells}
        assert on["matrix_label:column:tuning:primes:0"].x == on["tuning:prime:0"].x
        assert on["matrix_label:column:tuning:primes:0"].y < on["tuning:prime:0"].y
        assert on["matrix_label:row:mapping:primes:0"].x < on["bracket:map:0:l"].x
        assert (on["matrix_label:row:mapping:primes:0"].y <= on["cell:mapping:0:0"].y
                <= on["matrix_label:row:mapping:primes:0"].y + on["matrix_label:row:mapping:primes:0"].height)

    def test_col_labels_sit_inside_the_tile_centred_above_the_bracket(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "header_symbols": True},
        )
        on = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        for tile_block_id, frame_id, label_id in [
            ("block:vector:commas", "vector:commas", "matrix_label:column:vectors:commas:0"),
            ("block:vector:targets", "vector:targets", "matrix_label:column:vectors:targets:0"),
            ("block:mapped", "mapped", "matrix_label:column:mapping:targets:0"),
            ("block:mapped_comma", "mapped_comma", "matrix_label:column:mapping:commas:0"),
        ]:
            label = on[label_id]
            bracket_top = on[f"bracket:{frame_id}:l"].y
            tile_top = blocks[tile_block_id].y + spreadsheet_constants.PAD
            assert label.y >= tile_top - 1, \
                f"{label_id} (y={label.y}) must sit inside tile (top={tile_top}), not in the gap"
            assert label.y + label.height <= bracket_top, \
                f"{label_id} bottom y={label.y + label.height} must be at/above bracket y={bracket_top}"
            dist_above = label.y - tile_top
            dist_below = bracket_top - (label.y + label.height)
            assert abs(dist_above - dist_below) <= 1, \
                f"{label_id}: dist_above={dist_above}, dist_below={dist_below} should be ~equal"


class TestRowAndColumnLabels:
    def test_col_labels_sit_above_the_top_frame_in_framed_rows(self):
        on = {c.id: c for c in _with(header_symbols=True).cells}
        assert on["matrix_label:column:mapping:targets:0"].y + on["matrix_label:column:mapping:targets:0"].height \
            <= on["ebktop:mapped:0"].y
        assert on["matrix_label:column:mapping:commas:0"].y + on["matrix_label:column:mapping:commas:0"].height \
            <= on["ebktop:mapped_comma:0"].y
        assert on["matrix_label:column:vectors:commas:0"].y + on["matrix_label:column:vectors:commas:0"].height \
            <= on["ebktop:vector:commas:0"].y
        assert on["matrix_label:column:vectors:targets:0"].y + on["matrix_label:column:vectors:targets:0"].height \
            <= on["ebktop:vector:targets:0"].y

    def test_mapping_top_frame_hugs_the_cells_not_the_row_label_gutter(self):
        on = {c.id: c for c in _with(header_symbols=True).cells}
        ebktop = on["ebktop:primes"]
        ebkbrace = on["ebkbrace:primes"]
        left_bracket = on["bracket:map:0:l"]
        right_bracket = on["bracket:map:0:r"]
        assert ebktop.x == left_bracket.x
        assert ebkbrace.x == left_bracket.x
        assert ebktop.x + ebktop.width == right_bracket.x + right_bracket.width
        assert ebkbrace.x + ebkbrace.width == right_bracket.x + right_bracket.width

    def test_row_labels_balance_the_primes_tile_with_an_equal_right_gutter(self):
        layout = _with(header_symbols=True)
        on = {c.id: c for c in layout.cells}
        panel = {b.id: b for b in layout.blocks}["block:mapping"]
        left = on["bracket:map:0:l"].x - panel.x
        right = (panel.x + panel.width) - (on["bracket:map:0:r"].x + on["bracket:map:0:r"].width)
        assert abs(left - right) < 0.01, f"primes matrix off-centre in its tile: left={left}, right={right}"
        assert left >= spreadsheet_constants.MATRIX_LABEL_WIDTH

    def test_complexity_col_labels_spell_out_the_norm_definition(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["header_symbols"] = True
        s["equivalences"] = False
        s["weighting"] = True
        s["optimization"] = True
        s["generator_detempering"] = True
        on = {c.id: c for c in spreadsheet.build(
            base, s, held_vectors=((-1, 1, 0),),
            tuning_scheme="TILT minimax-S",
        ).cells}
        q = grid_tables.NORM_SUB_OPEN + "q" + grid_tables.NORM_SUB_CLOSE
        assert on["matrix_label:column:complexity:primes:0"].text == f"‖𝐿[1]‖{q}"
        assert on["matrix_label:column:complexity:primes:2"].text == f"‖𝐿[3]‖{q}"
        assert on["matrix_label:column:complexity:commas:0"].text == f"‖𝐿𝐜₁‖{q}"
        assert on["matrix_label:column:complexity:held:0"].text == f"‖𝐿𝐡₁‖{q}"
        assert on["matrix_label:column:complexity:detempering:0"].text == f"‖𝐿𝐝₁‖{q}"
        assert on["matrix_label:column:complexity:targets:0"].text == "c₁"

    def test_complexity_target_col_headers_gain_the_norm_equivalence(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        q = grid_tables.NORM_SUB_OPEN + "q" + grid_tables.NORM_SUB_CLOSE
        s = {**settings.defaults(), "header_symbols": True, "weighting": True, "equivalences": True}
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
        assert on["matrix_label:column:complexity:targets:0"].text == f"c₁ = ‖𝐿𝐭₁‖{q}"
        assert on["matrix_label:column:complexity:targets:7"].text == f"c₈ = ‖𝐿𝐭₈‖{q}"
        allint = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="minimax-S").cells}
        assert allint["matrix_label:column:complexity:targets:0"].text == f"c₁ = ‖𝐿[1]‖{q}"
        assert allint["matrix_label:column:complexity:targets:2"].text == f"c₃ = ‖𝐿[3]‖{q}"
        assert allint["matrix_label:column:complexity:primes:0"].text == f"‖𝐿[1]‖{q}"
        off = {c.id: c for c in spreadsheet.build(
            base, {**settings.defaults(), "header_symbols": True, "weighting": True, "equivalences": False},
            tuning_scheme="TILT minimax-S").cells}
        assert off["matrix_label:column:complexity:targets:0"].text == "c₁"

    def test_prescaling_matrix_row_and_col_labels(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["header_symbols"] = True
        s["weighting"] = True
        s["optimization"] = True
        s["generator_detempering"] = True
        s["alt_complexity"] = True
        on = {c.id: c for c in spreadsheet.build(
            base, s, held_vectors=((-1, 1, 0),),
            tuning_scheme="TILT minimax-S",
        ).cells}
        assert on["matrix_label:row:prescaling:primes:0"].text == "𝒍₁"
        assert on["matrix_label:row:prescaling:primes:1"].text == "𝒍₂"
        assert on["matrix_label:row:prescaling:primes:2"].text == "𝒍₃"
        assert on["matrix_label:column:prescaling:commas:0"].text == "𝐿𝐜₁"
        assert on["matrix_label:column:prescaling:held:0"].text == "𝐿𝐡₁"
        assert on["matrix_label:column:prescaling:detempering:0"].text == "𝐿𝐝₁"
        assert on["matrix_label:column:prescaling:targets:0"].text == "𝐿𝐭₁"

    def test_units_annotate_each_box_with_its_unit_string(self):
        on = {c.id: c for c in _with(units=True, names=True).cells}
        off = {c.id: c for c in _with(units=False).cells}
        assert on["units:tuning:generators"].text == "units: ¢/g"
        assert on["units:tuning:primes"].text == "units: ¢/p"
        assert on["units:mapping:primes"].text == "units: g/p"
        assert on["units:mapping:targets"].text == "units: g"
        assert on["units:vectors:targets"].text == "units: p"
        assert on["units:damage:targets"].text == "units: ¢(U)"
        assert not any(c.startswith("units:") for c in off)
        assert on["units:tuning:primes"].y > on["caption:tuning:primes"].y

    def test_units_carry_a_per_value_unit_on_each_gridded_cell(self):
        on = {c.id: c for c in _with("TILT minimax-S", units=True, cell_units=True, weighting=True, alt_complexity=True).cells}
        off = {c.id: c for c in _with(units=False, weighting=True).cells}
        assert on["cell:mapping:0:0"].unit == "g₁/p₁"
        assert on["cell:mapping:1:2"].unit == "g₂/p₃"
        assert on["tuning:prime:0"].unit == "¢/p₁"
        assert on["tuning:generator:0"].unit == "¢/g₁"
        assert on["tuning:target:0"].unit == "¢"
        assert on["cell:mapped:0:0"].unit == "g₁"
        assert on["cell:vector:targets:0:0"].unit == "p₁"
        assert on["cell:prescaling:primes:0:0"].unit == "oct/p₁", "the prescaler matrix's per-cell unit is octaves per its COLUMN's prime (oct/p), so the # p subscripts by the column — its diagonal reads oct/pᵢ, and an off-diagonal zero tracks # its column's prime, not its row (the matrix's d columns are the d domain primes)"
        assert on["cell:prescaling:primes:1:1"].unit == "oct/p₂"
        assert on["cell:prescaling:primes:0:1"].unit == "oct/p₂"
        assert on["complexity:prime:0"].unit == "(C)/p₁"
        assert all(not c.unit for c in off.values())

    def test_per_box_units_line_and_cell_units_toggle_independently(self):
        line_only = {c.id: c for c in _with(units=True, cell_units=False).cells}
        cell_only = {c.id: c for c in _with(units=False, cell_units=True).cells}
        assert "units:tuning:primes" in line_only
        assert all(not c.unit for c in line_only.values())
        assert cell_only["tuning:prime:0"].unit == "¢/p₁"
        assert not any(cell_id.startswith("units:") for cell_id in cell_only)

    def test_domain_units_adds_a_units_row_and_column_of_coordinate_labels(self):
        on = {c.id: c for c in _with(domain_units=True).cells}
        off = {c.id: c for c in _with(domain_units=False).cells}
        assert on["units_column:vectors:0"].text == "p₁/"
        assert on["units_column:vectors:2"].text == "p₃/"
        assert on["units_column:mapping:0"].text == "g₁/"
        assert on["units_column:tuning"].text == "¢/"
        assert on["units_column:damage"].text == "¢(U)/"
        assert on["units_row:generators:0"].text == "/g₁"
        assert on["units_row:primes:0"].text == "/p₁"
        assert on["units_row:primes:2"].text == "/p₃"
        assert on["units_row:targets:0"].text == "/1"
        assert on["units_row:primes:0"].x == on["prime:0"].x
        assert on["units_column:vectors:0"].y == on["basis:0"].y
        assert on["units_column:mapping:0"].y == on["generator:0"].y
        assert "header:units" in on and "label:units" in on
        assert not any(c.startswith(("units_column:", "units_row:")) for c in off)
        assert "header:units" not in off and "label:units" not in off
        assert on["header:quantities"].x < on["header:units"].x < on["header:generators"].x
        assert on["label:quantities"].y < on["label:units"].y < on["label:vectors"].y

    def test_nonstandard_domain_units_use_basis_element_label_b(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = settings.defaults()
        s["domain_units"] = True
        s["units"] = True
        s["cell_units"] = True
        s["weighting"] = True
        s["alt_complexity"] = True
        on = {c.id: c for c in spreadsheet.build(state, s, tuning_scheme="TILT minimax-S").cells}
        assert on["units_column:vectors:0"].text == "b₁/"
        assert on["units_column:vectors:2"].text == "b₃/"
        assert on["units_row:primes:0"].text == "/b₁"
        assert on["units_row:primes:2"].text == "/b₃"
        assert on["cell:mapping:0:0"].unit == "g₁/b₁"
        assert on["tuning:prime:0"].unit == "¢/b₁"
        assert on["cell:vector:targets:0:0"].unit == "b₁"
        assert on["cell:prescaling:primes:0:1"].unit == "oct/b₂"

    def test_optimization_box_sits_at_the_bottom_of_the_damage_tile(self):
        layout = _with(optimization=True)
        on = {c.id: c for c in layout.cells}
        assert on["optimization:title"].text == "optimization"
        assert on["optimization:mean_damage"].kind == "tuning_value"
        assert on["optimization:mean_damage:symbol"].text == "⟪𝐝⟫ₚ"
        assert on["optimization:power"].kind == "power_display"
        assert on["optimization:power"].text == "∞"
        assert on["optimization:power:symbol"].text == "𝑝"
        assert on["optimization:power:caption"].text == "optimization power"
        assert on["optimization:title"].y > on["damage:target:0"].y
        assert on["optimization:title"].x == on["header:targets"].x
        assert "label:optimization" not in on
        assert "h:optimization" not in {line.id for line in layout.lines}

    def test_optimization_power_field_reflects_the_current_scheme(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"] = True
        ls = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="held-octave OLD miniRMS-U").cells}
        assert ls["optimization:power"].text == "2"

    def test_optimization_needs_its_parent_tuning_tiles(self):
        cells = {c.id for c in _with(optimization=True, tuning_tiles=False).cells}
        assert "optimization:power" not in cells
        assert "optimization:title" not in cells

    def test_optimization_box_lays_out_mean_damage_and_power(self):
        layout = _with(optimization=True)
        on = {c.id: c for c in layout.cells}
        box = {b.id: b for b in layout.blocks}["block:optimization:box"]
        assert on["optimization:mean_damage"].x < on["optimization:power"].x
        assert on["optimization:mean_damage"].y == on["optimization:power"].y
        assert on["optimization:mean_damage"].y < on["optimization:mean_damage:symbol"].y
        assert (on["optimization:power"].y < on["optimization:power:symbol"].y
                < on["optimization:power:caption"].y)
        assert on["optimization:mean_damage"].width == spreadsheet_constants.COLUMN_WIDTH
        assert on["optimization:power"].width == spreadsheet_constants.COLUMN_WIDTH
        mean_damage_col_x = box.x + spreadsheet_constants.OPTIMIZATION_PADDING_L
        assert on["optimization:mean_damage:symbol"].x == mean_damage_col_x
        assert on["optimization:mean_damage:symbol"].width == spreadsheet_constants.OPTIMIZATION_MEAN_DAMAGE_WIDTH
        assert on["optimization:mean_damage:caption"].x == mean_damage_col_x
        assert on["optimization:mean_damage"].x == mean_damage_col_x + (spreadsheet_constants.OPTIMIZATION_MEAN_DAMAGE_WIDTH - spreadsheet_constants.COLUMN_WIDTH) / 2
        mean_damage_r = mean_damage_col_x + spreadsheet_constants.OPTIMIZATION_MEAN_DAMAGE_WIDTH
        pow_col_x = mean_damage_r + spreadsheet_constants.OPTIMIZATION_COL_GAP
        assert on["optimization:power:caption"].x == pow_col_x
        assert on["optimization:power"].x == pow_col_x + (spreadsheet_constants.OPTIMIZATION_POWER_CAP_WIDTH - spreadsheet_constants.COLUMN_WIDTH) / 2
        cap = on["optimization:power:caption"]
        assert cap.x > mean_damage_r and cap.x + cap.width < box.x + box.width
        assert box.width >= spreadsheet_constants.OPTIMIZATION_BOX_MIN_WIDTH
        assert on["optimization:power:caption"].height == spreadsheet_constants.CAPTION_LINE, "the caption occupies a single line (so 'optimization power' sits right under 𝑝, not a # two-line band that floats it lower)"
        assert on["optimization:title"].y > box.y
        assert on["optimization:mean_damage"].y > on["optimization:title"].y + on["optimization:title"].height
        ids = {c.id for c in layout.cells}
        assert "optimization:button" not in ids
        assert "optimization:button:hint" not in ids
        assert not any(c.id.startswith("optimization:") for c in _with(optimization=False).cells)

    def test_optimization_box_fills_the_full_width_of_the_damage_tile(self):
        layout = _with(optimization=True)
        blk = {b.id: b for b in layout.blocks}
        box = blk["block:optimization:box"]
        panel = blk["block:damage:targets"]
        assert box.x == panel.x + spreadsheet_constants.PAD
        assert box.width == panel.width - 2 * spreadsheet_constants.PAD

    def test_a_narrow_damage_tile_widens_to_seat_the_optimization_box(self):
        base = service.from_mapping(((1, 1), (0, 1)))
        s = settings.defaults()
        s["optimization"] = True
        blk = {b.id: b for b in spreadsheet.build(base, s).blocks}
        box = blk["block:optimization:box"]
        assert box.width >= spreadsheet_constants.OPTIMIZATION_BOX_MIN_WIDTH
        assert box.width == blk["block:damage:targets"].width - 2 * spreadsheet_constants.PAD

    def test_a_manual_generator_tuning_drives_the_displayed_maps(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        manual = {c.id: c for c in spreadsheet.build(base, s, generator_tuning=(1200.0, 701.955)).cells}
        assert manual["tuning:prime:1"].text == "1901.955"
        auto = {c.id: c for c in spreadsheet.build(base, s).cells}
        assert auto["tuning:prime:1"].text != "1901.955"

    def test_typing_the_generator_tuning_map_drives_the_grid_through_the_editor(self):
        editor = Editor()
        assert editor.set_generator_tuning_text("{1200.000 700.000]") is True
        cells = {c.id: c for c in spreadsheet.build(
            editor.state, editor.settings, tuning_scheme=editor.tuning_scheme,
            generator_tuning=editor.effective_generator_tuning()).cells}
        assert cells["tuning:prime:0"].text == "1200.000"
        assert cells["tuning:prime:1"].text == "1900.000"
        assert cells["tuning:prime:2"].text == "2800.000"

    def test_generator_tuning_map_cells_are_editable_inputs(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["tuning:generator:0"].kind == "generator_tuning_cell"
        assert cells["tuning:generator:1"].kind == "generator_tuning_cell"

    def test_a_target_override_drives_the_target_columns(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        cells = {c.id: c for c in spreadsheet.build(base, s, target_override=("2/1", "3/2")).cells}
        assert cells["target:0"].text == "2/1" and cells["target:1"].text == "3/2"
        assert "target:2" not in cells
        assert cells["cell:vector:targets:0:0"].kind == "target_cell"
        for row in ("tuning", "just", "damage"):
            assert f"{row}:target:1" in cells and f"{row}:target:2" not in cells

    def test_a_target_override_retunes_the_generator_map(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        plain = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-U", target_spec="TILT").cells}
        overridden = {c.id: c for c in spreadsheet.build(
            base, s, tuning_scheme="TILT minimax-U", target_spec="TILT", target_override=("2/1", "3/2")).cells}
        assert overridden["tuning:generator:1"].text != plain["tuning:generator:1"].text

    def test_target_interval_list_cells_and_plain_text_are_editable(self):
        cells = {c.id: c for c in _with(plain_text_values=True).cells}
        assert cells["plain_text:vectors:targets"].kind == "plain_text_edit"
        assert cells["cell:vector:targets:0:0"].kind == "target_cell"

    def test_all_interval_target_list_is_read_only(self):
        allint = {c.id: c for c in _with(scheme="minimax-S", plain_text_values=True).cells}
        based = {c.id: c for c in _with(scheme="TILT minimax-S", plain_text_values=True).cells}
        assert allint["cell:vector:targets:0:0"].kind == "vector"
        assert allint["target:0"].kind == "comma_ratio"
        assert allint["plain_text:vectors:targets"].kind == "plain_text"
        assert based["cell:vector:targets:0:0"].kind == "target_cell"
        assert based["target:0"].kind == "ratio_cell"
        assert based["plain_text:vectors:targets"].kind == "plain_text_edit"

    def test_editable_target_vector_cells_clear_the_column_separator(self):
        cells = {c.id: c for c in _layout().cells}
        c0, c1 = cells["cell:vector:targets:0:0"], cells["cell:vector:targets:1:0"]
        sep = cells["sep:vector:targets:1"]
        full = cells["cell:mapped:0:0"]
        assert c0.width == full.width == spreadsheet_constants.COLUMN_WIDTH
        assert c0.x == full.x
        assert c1.x - (c0.x + c0.width) == spreadsheet_constants.INTERVAL_COL_GAP
        assert c0.x + c0.width <= sep.x
        assert sep.x + sep.width <= c1.x

    def test_typing_the_target_interval_list_drives_the_grid_through_the_editor(self):
        editor = Editor()
        assert editor.set_target_override_text("[1 0 0⟩ [-1 1 0⟩") is True
        cells = {c.id: c for c in spreadsheet.build(
            editor.state, editor.settings, tuning_scheme=editor.tuning_scheme,
            target_override=editor.target_override).cells}
        assert cells["target:0"].text == "2/1" and cells["target:1"].text == "3/2"
        assert "target:2" not in cells

    def test_optimization_draws_the_minimized_damage_indicator_on_the_chart(self):
        on = {c.id: c for c in _with(optimization=True, charts=True).cells}
        chart = on["chart:damage:targets"]
        assert chart.indicator is not None
        assert chart.indicator == max(chart.values)
        off = {c.id: c for c in _with(optimization=False, charts=True).cells}
        assert off["chart:damage:targets"].indicator is None

    def test_optimization_indicator_carries_the_power_as_its_subscript_label(self):
        on = {c.id: c for c in _with(optimization=True, charts=True).cells}
        assert on["chart:damage:targets"].indicator_label == "∞"
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["optimization"], s["charts"] = True, True
        rms = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="held-octave OLD miniRMS-U").cells}
        assert rms["chart:damage:targets"].indicator_label == "2"
        off = {c.id: c for c in _with(optimization=False, charts=True).cells}
        assert off["chart:damage:targets"].indicator_label == ""


class TestOptimizationBoxFrame:
    def test_optimization_box_is_a_bordered_frame_nested_in_the_damage_tile(self):
        layout = _with(optimization=True)
        blocks = {b.id: b for b in layout.blocks}
        box = blocks["block:optimization:box"]
        assert box.boxed
        panel = blocks["block:damage:targets"]
        assert panel.y <= box.y and box.y + box.height <= panel.y + panel.height
