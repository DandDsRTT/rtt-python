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
from _spreadsheet_support import _memoized_build, _layout, _with


class TestCommasColumn:
    def test_commas_column_sits_between_primes_and_targets_with_its_comma_ratios(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["header:commas"].text == "commas"
        assert cells["comma:0"].text == "80/81"
        assert cells["header:primes"].x < cells["header:commas"].x < cells["header:targets"].x
        assert cells["prime:2"].x < cells["comma:0"].x < cells["target:0"].x

    def test_comma_basis_renders_as_raw_vectors_in_the_interval_vectors_row(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["cell:comma:0:0"].text == "4", "the raw comma basis lives in the interval-vectors row's commas column, d-tall; # the syntonic comma [4, -4, 1] reads top-to-bottom (prime 2, 3, 5) down its column"
        assert cells["cell:comma:1:0"].text == "-4"
        assert cells["cell:comma:2:0"].text == "1"
        c00 = cells["cell:comma:0:0"]
        assert c00.width == c00.height == spreadsheet_constants.ROW_HEIGHT
        assert cells["cell:comma:1:0"].y == c00.y + c00.height
        assert c00.x == cells["comma:0"].x
        assert c00.y == cells["cell:vector:targets:0:0"].y

    def test_mapping_row_commas_show_the_mapped_comma_basis_vanishing(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["cell:mapped_comma:0:0"].text == "0"
        assert cells["cell:mapped_comma:1:0"].text == "0"
        assert cells["cell:mapped_comma:0:0"].y == cells["cell:mapped:0:0"].y
        assert cells["cell:mapped_comma:1:0"].y == cells["cell:mapping:1:0"].y
        assert cells["cell:mapped_comma:0:0"].x == cells["comma:0"].x
        assert cells["cell:comma:0:0"].y < cells["cell:mapped_comma:0:0"].y, "the raw comma basis is NOT here — it sits up in the (higher) interval-vectors row"

    def test_comma_sizes_fill_the_tuning_family_rows(self):
        cells = {c.id: c for c in _layout().cells}
        assert cells["tuning:comma:0"].text == "0.000"
        assert cells["just:comma:0"].text == "-21.506"
        assert cells["retune:comma:0"].text == "21.506"
        assert cells["tuning:comma:0"].x == cells["comma:0"].x

    def test_damage_row_has_no_commas_tile(self):
        layout = _with(names=True, symbols=True, plain_text_values=True, charts=True)
        cells = {c.id for c in layout.cells}
        blocks = {b.id for b in layout.blocks}
        assert "damage:target:0" in cells and "block:damage:targets" in blocks
        assert not any(c.startswith("damage:comma") for c in cells)
        assert "caption:damage:commas" not in cells
        assert "symbol:damage:commas" not in cells
        assert {"bracket:damage:commalist:l", "bracket:damage:commalist:r"}.isdisjoint(cells)
        assert "toggle:tile:damage:commas" not in cells
        assert "plain_text:damage:commas" not in cells
        assert "block:damage:commas" not in blocks

    def test_weighting_on_adds_a_weight_row_over_the_targets(self):
        off = {c.id for c in _with(weighting=False).cells}
        on = {c.id: c for c in _with(weighting=True).cells}
        assert "weight:target:0" not in off
        assert "weight:target:0" in on
        targets = service.target_interval_set(
            service.DEFAULT_TARGET_SPEC, service.standard_primes(3)
        )
        weights = service.interval_weights(
            ((1, 1, 0), (0, 1, 4)), service.DEFAULT_DOCUMENT_SCHEME, targets
        )
        assert len(weights) == 8
        assert on["weight:target:0"].text == service.cents(weights[0])
        assert on["weight:target:7"].text == service.cents(weights[7])

    def test_weight_row_sits_between_retuning_and_damage(self):
        on = {c.id: c for c in _with(weighting=True).cells}
        assert on["retune:target:0"].y < on["weight:target:0"].y < on["damage:target:0"].y, "the weighting region computes prescaling -> complexity -> weight -> damage, # so the weight row lands just above damage (and below retuning)"

    def test_weight_row_value_list_is_bracketed_like_the_other_tuning_lists(self):
        cells = {c.id: c for c in _with(weighting=True).cells}
        assert cells["bracket:weight:l"].text == "[" and cells["bracket:weight:r"].text == "]"
        assert cells["bracket:weight:l"].x < cells["weight:target:0"].x < cells["bracket:weight:r"].x

    def test_charts_on_adds_a_weight_bar_chart_over_the_targets(self):
        on = {c.id: c for c in _with(weighting=True, charts=True).cells}
        off = {c.id for c in _with(weighting=True, charts=False).cells}
        assert "chart:weight:targets" not in off
        ch = on["chart:weight:targets"]
        assert ch.kind == "chart"
        assert len(ch.values) == 8
        assert all(v >= 0 for v in ch.values)
        assert ch.y + ch.height <= on["weight:target:0"].y

    def test_the_size_factor_prescaler_carries_a_horizontal_size_bar(self):
        on = {c.id: c for c in _with("minimax-lils-S", weighting=True).cells}
        bar = on["bar:prescaling"]
        assert bar.kind == "hbar"
        assert on["cell:prescaling:primes:2:0"].y < bar.y < on["cell:prescaling:primes:3:0"].y
        assert "bar:prescaling" not in {c.id for c in _with("minimax-S", weighting=True).cells}, "a square (lp) prescaler has no size row, so no horizontal bar"

    def test_the_size_sensitizing_row_is_labelled_z_not_a_fourth_prime(self):
        lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, header_symbols=True).cells}
        assert lils["matrix_label:row:prescaling:primes:0"].text == "𝒍₁"
        assert lils["matrix_label:row:prescaling:primes:2"].text == "𝒍₃"
        assert lils["matrix_label:row:prescaling:primes:3"].text == "𝒛", "the size row — not 𝒍₄"
        lp = {c.id: c for c in _with("minimax-S", weighting=True, symbols=True, header_symbols=True).cells}
        assert lp["matrix_label:row:prescaling:primes:2"].text == "𝒍₃"
        assert "matrix_label:row:prescaling:primes:3" not in lp

    def test_size_factor_composes_the_size_sensitizing_matrix_with_each_base_prescaler(self):
        st = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        def labels(scheme):
            s = settings.defaults()
            s.update(weighting=True, symbols=True, equivalences=True, names=True, alt_complexity=True)
            cells = {c.id: c for c in spreadsheet.build(st, s, tuning_scheme=scheme).cells}
            return cells["symbol:prescaling:primes"].text, cells["caption:prescaling:primes"].text

        identity = service.scheme_with_diminuator(service.scheme_with_complexity("minimax-S", "copfr"), True)
        prime = service.scheme_with_diminuator(service.scheme_with_complexity("minimax-S", "sopfr"), True)
        assert labels("minimax-lils-S") == (
            "𝑋 = 𝑍𝐿", "complexity pretransformer = size-sensitizing matrix × log-prime matrix")
        assert labels(identity) == (
            "𝑋 = 𝑍", "complexity pretransformer = size-sensitizing matrix")
        assert labels(prime) == (
            "𝑋 = 𝑍·diag(𝒑)", "complexity pretransformer = size-sensitizing matrix × diagonal matrix of primes")
        s = settings.defaults()
        s.update(weighting=True, symbols=True, equivalences=True, names=True)
        lp = {c.id: c for c in spreadsheet.build(st, s, tuning_scheme="minimax-S").cells}
        assert lp["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
        assert lp["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"

    def test_the_size_factor_drops_the_diag_complexity_equivalence(self):
        lils = {c.id: c for c in _with("minimax-lils-S", weighting=True, symbols=True, equivalences=True).cells}
        assert lils["symbol:complexity:targets"].text == "𝒄"
        lp = {c.id: c for c in _with("minimax-S", weighting=True, symbols=True, equivalences=True).cells}
        assert lp["symbol:complexity:targets"].text == "𝒄 = diag(𝐿)"

    def test_weight_row_carries_its_symbol_and_caption(self):
        on = {c.id: c for c in _with(weighting=True, symbols=True, names=True, equivalences=False).cells}
        assert on["symbol:weight:targets"].text == "𝒘"
        assert grid_tables.EQUIVALENCES[("damage", "targets")].endswith("𝒘")
        assert on["caption:weight:targets"].text == "target interval weight list"

    def test_weight_caption_mnemonic_underlines_its_symbol_letter(self):
        on = {c.id: c for c in _with(weighting=True, names=True, mnemonics=True).cells}
        cap = on["caption:weight:targets"]
        assert cap.underlines == ((cap.text.index("weight"), 1),)

    def test_weighting_on_adds_a_complexity_row_over_every_interval_column(self):
        off = {c.id for c in _with(weighting=False).cells}
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}
        assert "complexity:target:0" not in off
        mapping = ((1, 1, 0), (0, 1, 4))
        scheme = service.DEFAULT_TUNING_SCHEME
        targets = service.target_interval_set(service.DEFAULT_TARGET_SPEC, service.standard_primes(3))
        tx = service.interval_complexities(mapping, scheme, targets)
        assert on["complexity:target:0"].text == service.cents(tx[0])
        assert on["complexity:target:7"].text == service.cents(tx[7])
        cx = service.interval_complexities(mapping, scheme, ("80/81",))
        assert on["complexity:comma:0"].text == service.cents(cx[0])
        px = service.interval_complexities(mapping, scheme, ("2/1", "3/1", "5/1"))
        assert on["complexity:prime:0"].text == service.cents(px[0])
        assert on["complexity:prime:2"].text == service.cents(px[2])

    def test_complexity_row_sits_between_retuning_and_weight(self):
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}
        assert on["retune:target:0"].y < on["complexity:target:0"].y < on["weight:target:0"].y

    def test_complexity_over_primes_is_a_map_the_rest_are_lists(self):
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True}, interest=((-3, 2, 0),),
            tuning_scheme="TILT minimax-S",
        ).cells}
        assert cells["bracket:complexity:map:l"].text == "⟨" and cells["bracket:complexity:map:r"].text == "]"
        assert cells["bracket:complexity:commalist:l"].text == "["
        assert cells["bracket:complexity:list:l"].text == "[" and cells["bracket:complexity:list:r"].text == "]"
        assert not any(c.startswith("bracket:complexity:ilist") for c in cells), "...but the interest complexity drops its bracket — the whole interest column is bare"
        assert {"ebktop:prescaling:interest:0", "ebkangle:prescaling:interest:0"} <= set(cells)
        assert "ebkbrace:prescaling:interest:0" not in cells, "NOT a curly close — the ket's angle foot ⟩"
        assert "bracket:prescaling:interest:l" not in cells

    def test_complexity_is_not_charted(self):
        on = {c.id for c in _with(weighting=True, charts=True).cells}
        assert not any(c.startswith("chart:complexity") for c in on)

    def test_complexity_row_carries_its_symbol_and_captions(self):
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True, "symbols": True, "names": True},
            interest=((-3, 2, 0),),
            tuning_scheme="TILT minimax-S",
        ).cells}
        assert cells["symbol:complexity:targets"].text == "𝒄"
        assert cells["caption:complexity:primes"].text == "domain prime complexity map"
        assert cells["caption:complexity:commas"].text == "comma basis interval complexity list"
        assert cells["caption:complexity:targets"].text == "target interval complexity list"
        assert cells["caption:complexity:interest"].text == "interval complexities"
        assert cells["caption:prescaling:interest"].text == "complexity prescaled intervals"

    def test_complexity_caption_mnemonic_underlines_its_symbol_letter(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, names=True, mnemonics=True).cells}
        cap = cells["caption:complexity:targets"]
        assert cap.underlines == ((cap.text.index("complexity"), 1),)

    def test_weighting_on_adds_the_complexity_prescaling_matrix_over_the_primes(self):
        on = {c.id: c for c in _with("minimax-S", weighting=True).cells}
        off = {c.id for c in _with(weighting=False).cells}
        assert "cell:prescaling:primes:0:0" not in off
        pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), service.DEFAULT_TUNING_SCHEME)
        assert on["cell:prescaling:primes:0:0"].kind == "prescalercell"
        assert on["cell:prescaling:primes:0:0"].text == "1"
        assert on["cell:prescaling:primes:1:1"].text == service.cents(pre[1])
        assert on["cell:prescaling:primes:2:2"].text == service.cents(pre[2])
        assert on["cell:prescaling:primes:0:1"].kind == "tuningvalue"
        assert on["cell:prescaling:primes:0:1"].text == "0"
        assert on["cell:prescaling:primes:0:0"].x == on["prime:0"].x
        assert on["cell:prescaling:primes:1:1"].x == on["prime:1"].x
        assert on["cell:prescaling:primes:1:0"].y == on["cell:prescaling:primes:0:0"].y + spreadsheet_constants.ROW_HEIGHT

    def test_size_factor_grows_the_prescaler_into_the_rectangular_ZL_matrix(self):
        lp = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, alt_complexity=True).cells}
        pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), "TILT minimax-S")
        assert "cell:prescaling:primes:3:0" not in lp
        for c in range(3):
            assert lils[f"cell:prescaling:primes:3:{c}"].text == service.prescale_text(pre[c])
            assert lils[f"cell:prescaling:primes:3:{c}"].kind == "tuningvalue"
        assert lils["cell:prescaling:primes:0:0"].kind == "prescalercell"
        assert lils["cell:prescaling:primes:3:0"].y == lils["cell:prescaling:primes:2:0"].y + spreadsheet_constants.ROW_HEIGHT + spreadsheet_constants.V_SPLIT_GAP
        assert lils["bracket:prescaling:row:3:l"].text == "⟨" and lils["bracket:prescaling:row:3:r"].text == "]"

    def test_size_factor_grows_the_prescaler_product_tiles_and_labels_the_size_row(self):
        mapping = ((1, 1, 0), (0, 1, 4))
        lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, alt_complexity=True).cells}
        lils_sym = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, alt_complexity=True, symbols=True, header_symbols=True).cells}
        pre = service.complexity_prescaler(mapping, "TILT minimax-S")
        comma = service.from_mapping(mapping).comma_basis[0]
        expected = service.prescale_text(sum(pre[j] * comma[j] for j in range(3)))
        assert lils["cell:prescaling:commas:3:0"].text == expected
        assert lils["cell:prescaling:commas:3:0"].kind == "tuningvalue"
        assert lils_sym["matrix_label:row:prescaling:primes:3"].text == "𝒛", "the bare matrix's size row carries the 𝒛 row label (the size-sensitizing row, not a 4th prime 𝒍₄)"

    def test_prescaling_tiles_carry_their_per_tile_symbols_and_equivalences(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True, "optimization": True,
             "symbols": True, "equivalences": True},
            held_vectors=((-1, 1, 0),),
            tuning_scheme="TILT minimax-S",
        )
        on = {c.id: c for c in layout.cells}
        assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
        assert on["symbol:prescaling:commas"].text == "𝐿C"
        assert on["symbol:prescaling:targets"].text == "𝐿T"
        assert on["symbol:prescaling:held"].text == "𝐿H"

    def test_size_factor_names_the_bare_prescaler_ZL_not_just_L(self):
        lils = {c.id: c for c in _with(scheme="TILT minimax-lils-S", weighting=True, alt_complexity=True,
                                       symbols=True, names=True, equivalences=True).cells}
        assert lils["symbol:prescaling:primes"].text == "𝑋 = 𝑍𝐿"
        assert lils["caption:prescaling:primes"].text == "complexity pretransformer = size-sensitizing matrix × log-prime matrix", "the size factor also renames 'prescaler' → 'pretransformer' (the guide's term for rectangular 𝑋)"
        lp = {c.id: c for c in _with(scheme="TILT minimax-S", weighting=True, alt_complexity=True,
                                     symbols=True, names=True, equivalences=True).cells}
        assert lp["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
        assert lp["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"

    def test_non_log_prime_prescaler_stays_generic_X_named_in_the_equivalence(self):
        scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "identity")
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True, "optimization": True,
             "symbols": True, "names": True, "equivalences": True},
            tuning_scheme=scheme, held_vectors=((-1, 1, 0),),
        )
        on = {c.id: c for c in layout.cells}
        assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐼"
        assert on["symbol:prescaling:commas"].text == "𝑋C"
        assert on["symbol:prescaling:targets"].text == "𝑋T"
        assert on["symbol:prescaling:held"].text == "𝑋H"
        assert on["caption:prescaling:primes"].text == "complexity prescaler", "the NAME gains its '= log-prime matrix' equivalence ONLY when 𝑋 = 𝐿 — not here"

    def test_prime_prescaler_names_diag_p_in_the_equivalence_not_the_projection_letter(self):
        scheme = service.scheme_with_prescaler(f"TILT {service.DEFAULT_TUNING_SCHEME}", "prime")
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True, "optimization": True,
             "symbols": True, "equivalences": True},
            tuning_scheme=scheme, held_vectors=((-1, 1, 0),),
        )
        on = {c.id: c for c in layout.cells}
        assert on["symbol:prescaling:primes"].text == "𝑋 = diag(𝒑)"
        assert on["symbol:prescaling:commas"].text == "𝑋C"
        assert on["symbol:prescaling:targets"].text == "𝑋T"


class TestWeightingLabels:
    def test_log_prime_prescaler_name_gains_the_equivalence(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True, "alt_complexity": True, "symbols": True, "names": True,
             "equivalences": True}
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
        assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
        assert on["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"
        on2 = {c.id: c for c in spreadsheet.build(base, {**s, "equivalences": False},
                                                  tuning_scheme="TILT minimax-S").cells}
        assert on2["caption:prescaling:primes"].text == "complexity prescaler"

    def test_prescaler_symbol_never_mixes_L_and_X_within_a_tile(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "symbols": True, "header_symbols": True, "weighting": True,
             "alt_complexity": True, "generator_detempering": True}
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
        assert on["symbol:prescaling:detempering"].text == "𝐿D"
        assert on["matrix_label:col:prescaling:detempering:0"].text == "𝐿𝐝₁"

    def test_size_factor_renames_prescaler_to_pretransformer_in_the_labels(self):
        lp = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True,
                                     names=True, presets=True, equivalences=False).cells}
        lils = {c.id: c for c in _with("TILT minimax-lils-S", weighting=True, alt_complexity=True,
                                       names=True, presets=True, equivalences=False).cells}
        assert lp["caption:prescaling:primes"].text == "complexity prescaler"
        assert lils["caption:prescaling:primes"].text == "complexity pretransformer"
        assert lp["caption:prescaling:targets"].text == "complexity prescaled target interval list"
        assert lils["caption:prescaling:targets"].text == "complexity pretransformed target interval list"
        assert lp["label:prescaling"].text == "complexity prescaling"
        assert lils["label:prescaling"].text == "complexity" + chr(160) + "pre-" + chr(10) + "transforming"
        assert lp["block:preset:prescaler:label"].text == "predefined prescalers"
        assert lils["block:preset:prescaler:label"].text == "predefined pretransformers"

    def test_alt_complexity_makes_the_whole_pretransformer_square_editable(self):
        X = ((1.0, 0.5, 0.0), (0.0, 1.585, 0.0), (0.0, 0.0, 2.322))
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        on = {c.id: c for c in spreadsheet.build(
            base, {**settings.defaults(), "weighting": True, "alt_complexity": True},
            tuning_scheme="TILT minimax-S", custom_prescaler=X).cells}
        assert on["cell:prescaling:primes:0:1"].kind == "prescalercell"
        assert on["cell:prescaling:primes:0:1"].text == service.prescale_text(0.5)
        assert on["cell:prescaling:primes:1:1"].kind == "prescalercell"
        assert on["cell:prescaling:primes:2:1"].kind == "prescalercell"
        assert on["cell:prescaling:primes:2:1"].text == "0"
        off = {c.id: c for c in spreadsheet.build(
            base, {**settings.defaults(), "weighting": True, "alt_complexity": False},
            tuning_scheme="minimax-S").cells}
        assert off["cell:prescaling:primes:1:1"].kind == "prescalercell"
        assert off["cell:prescaling:primes:0:1"].kind == "tuningvalue"

    def test_custom_prescaler_diagonal_keeps_the_generic_symbol(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "symbols": True, "header_symbols": True, "equivalences": True,
             "weighting": True, "alt_complexity": True, "generator_detempering": True}
        on = {c.id: c for c in spreadsheet.build(
            base, s, custom_prescaler=(1.0, 1.5, 2.0),
            tuning_scheme="TILT minimax-S").cells}
        assert on["symbol:prescaling:primes"].text == "𝑋"
        assert on["symbol:prescaling:commas"].text == "𝑋C"
        assert on["matrix_label:col:prescaling:detempering:0"].text == "𝑋𝐝₁"
        assert on["matrix_label:row:prescaling:primes:0"].text == "𝒙₁"

    def test_returning_the_prescaler_to_its_shown_log_prime_diagonal_restores_the_L_awareness(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        scheme = f"TILT {service.DEFAULT_TUNING_SCHEME}"
        shown = tuple(float(service.prescale_text(v))
                      for v in service.complexity_prescaler(((1, 1, 0), (0, 1, 4)), scheme))
        s = {**settings.defaults(), "weighting": True, "alt_complexity": True, "symbols": True,
             "names": True, "equivalences": True}
        on = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme, custom_prescaler=shown).cells}
        assert on["symbol:prescaling:primes"].text == "𝑋 = 𝐿"
        assert on["symbol:prescaling:commas"].text == "𝐿C"
        assert on["caption:prescaling:primes"].text == "complexity prescaler = log-prime matrix"

    def test_complexity_symbol_and_mnemonic_only_on_the_target_list(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "symbols": True, "names": True, "mnemonics": True},
            interest=((-3, 2, 0),),
            tuning_scheme="TILT minimax-S",
        )
        on = {c.id: c for c in layout.cells}
        assert on["symbol:complexity:targets"].text == "𝒄"
        assert on["caption:complexity:targets"].underlines != ()
        for col in ("primes", "commas", "interest"):
            assert f"symbol:complexity:{col}" not in on, col
            assert on[f"caption:complexity:{col}"].underlines == (), col

    def test_prescaling_row_spans_commas_and_targets_with_L_scaled_vectors(self):
        layout = _with("TILT minimax-S", weighting=True, alt_complexity=True)
        on = {c.id: c for c in layout.cells}
        blocks = {b.id for b in layout.blocks}
        pre = service.complexity_prescaler(((1, 1, 0), (0, 1, 4)))
        _t = service.prescale_text
        for i, comp in enumerate((4, -4, 1)):
            cell = on[f"cell:prescaling:commas:{i}:0"]
            assert cell.text == _t(pre[i] * comp)
            assert cell.kind == "tuningvalue"
        assert {"block:prescaling:commas", "block:prescaling:targets"} <= blocks
        assert {"ebktop:prescaling:commas:0", "ebkangle:prescaling:commas:0",
                "ebktop:prescaling:targets:0", "ebkangle:prescaling:targets:0"} <= set(on)
        assert "cell:prescaling:targets:0:0" in on

    def test_prescaling_plain_text_shows_the_same_numbers_as_the_grid(self):
        import re
        cells = {c.id: c for c in _with("TILT minimax-S", plain_text_values=True, weighting=True, alt_complexity=True).cells}
        vecbr = {"primes": "⟨]", "commas": "[⟩", "targets": "[⟩"}
        outer = {"primes": "[⟩", "commas": "[]", "targets": "[]"}
        for group in ("primes", "commas", "targets"):
            coords = [re.fullmatch(rf"cell:prescaling:{group}:(\d+):(\d+)", cell_id)
                      for cell_id in cells]
            coords = [(int(m.group(2)), int(m.group(1))) for m in coords if m]
            ncols = max(c for c, _ in coords) + 1
            d = max(r for _, r in coords) + 1
            vo, vc = vecbr[group]
            vecs = [vo + " ".join(cells[f"cell:prescaling:{group}:{i}:{c}"].text
                                  for i in range(d)) + vc
                    for c in range(ncols)]
            op, collapsed = outer[group]
            assert cells[f"plain_text:prescaling:{group}"].text == f"{op}{' '.join(vecs)}{collapsed}", group

    def test_weighting_rows_show_their_units_line_when_units_on(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, units=True, alt_complexity=True).cells}
        assert cells["units:prescaling:primes"].text == "units: oct/p"
        assert cells["units:prescaling:targets"].text == "units: oct"
        assert cells["units:complexity:primes"].text == "units: (C)/p"
        assert cells["units:complexity:targets"].text == "units: (C)"
        assert cells["units:weight:targets"].text == "units: (S)"

    def test_weighting_rows_have_units_column_tiles_when_domain_units_on(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, domain_units=True, alt_complexity=True).cells}
        assert cells["ucol:prescaling:0"].text == "oct/"
        assert cells["ucol:complexity"].text == "(C)/"
        assert cells["ucol:weight"].text == "(S)/"

    def test_damage_weight_and_complexity_units_track_the_tuning_scheme(self):
        cases = [
            ("TILT minimax-U", "¢(U)", "(U)", None),
            ("TILT minimax-C", "¢(C)", "(C)", "(C)"),
            ("TILT minimax-S", "¢(S)", "(S)", "(C)"),
            ("TILT minimax-EC", "¢(EC)", "(EC)", "(EC)"),
            ("TILT minimax-ES", "¢(ES)", "(ES)", "(EC)"),
            ("TILT minimax-sopfr-S", "¢(sopfr-S)", "(sopfr-S)", "(sopfr-C)"),
            ("TILT minimax-E-sopfr-S", "¢(E-sopfr-S)", "(E-sopfr-S)", "(E-sopfr-C)"),
            ("TILT minimax-copfr-C", "¢(copfr-C)", "(copfr-C)", "(copfr-C)"),
            ("TILT minimax-lils-S", "¢(lils-S)", "(lils-S)", "(lils-C)"),
        ]
        for scheme, damage, weight, complexity in cases:
            cells = {c.id: c for c in _with(scheme, weighting=True, units=True, cell_units=True, domain_units=True).cells}
            assert cells["units:damage:targets"].text == f"units: {damage}", scheme
            assert cells["damage:target:0"].unit == damage, scheme
            assert cells["ucol:damage"].text == f"{damage}/", scheme
            assert cells["units:weight:targets"].text == f"units: {weight}", scheme
            assert cells["weight:target:0"].unit == weight, scheme
            assert cells["ucol:weight"].text == f"{weight}/", scheme
            if complexity is None:
                assert "units:complexity:targets" not in cells, scheme
            else:
                assert cells["units:complexity:targets"].text == f"units: {complexity}", scheme
                assert cells["complexity:prime:0"].unit == f"{complexity}/p₁", scheme
                assert cells["ucol:complexity"].text == f"{complexity}/", scheme

    def test_weighting_rows_render_a_plain_text_box_when_plain_text_on(self):
        cells = {c.id for c in _with("TILT minimax-S", weighting=True, plain_text_values=True, alt_complexity=True).cells}
        assert {"plain_text:weight:targets", "plain_text:complexity:primes", "plain_text:complexity:targets",
                "plain_text:prescaling:primes"} <= cells

    def test_prescaling_row_sits_between_retuning_and_complexity(self):
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        assert on["retune:prime:0"].y < on["cell:prescaling:primes:0:0"].y < on["complexity:prime:0"].y

    def test_every_present_row_and_column_has_a_gridline(self):
        layout = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            {**settings.defaults(), "weighting": True, "alt_complexity": True},
            interest=((-3, 2, 0),),
        )
        line_ids = {line.id for line in layout.lines}
        rows = {c.id.split("label:", 1)[1] for c in layout.cells if c.id.startswith("label:")}
        for key in rows:
            if key in grid_tables.FRAMED_ROWS:
                assert f"h:{key}:0" in line_ids, f"matrix row {key!r} has no fanned gridline"
            else:
                assert f"h:{key}" in line_ids, f"row {key!r} has no gridline"
        cols = {c.id.split("header:", 1)[1] for c in layout.cells if c.id.startswith("header:")}
        for key in cols:
            assert f"trunk:{key}" in line_ids, f"column {key!r} has no gridline"

    def test_prescaling_matrices_have_outer_brackets_and_per_column_marks(self):
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        assert on["ebktop:prescaling"].kind == "ebktop"
        assert on["ebkangle:prescaling"].kind == "ebkangle"
        assert on["bracket:prescaling:row:0:l"].text == "⟨"
        assert on["bracket:prescaling:row:0:r"].text == "]"
        assert "bracket:prescaling:l" not in on
        assert "bracket:prescaling:r" not in on
        assert "ebkbrace:prescaling" not in on, "NOT a curly close at bottom — angle close ⟩"
        for bid in ("prescaling:commas", "prescaling:targets"):
            assert on[f"bracket:{bid}:l"].text == "[" and on[f"bracket:{bid}:r"].text == "]"
            assert on[f"ebktop:{bid}:0"].kind == "ebktop"
            assert on[f"ebkangle:{bid}:0"].kind == "ebkangle"
            assert f"ebkbrace:{bid}:0" not in on, "NOT a curly close — the ket's angle foot ⟩"
        assert on["ebktop:primes"].kind == "ebktop" and on["ebkbrace:primes"].kind == "ebkbrace", "the mapping matrix keeps its single top bracket + bottom curly brace (its mapped lists # ARE generator coords, so the } close is correct there)"

    def test_outer_matrix_frame_hugs_the_cells_leaving_subrow_labels_outside(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, symbols=True, header_symbols=True).cells}
        for top_id, foot_id, label_id, left_id, right_id in (
            ("ebktop:primes", "ebkbrace:primes", "matrix_label:row:mapping:primes:0",
             "bracket:map:0:l", "bracket:map:0:r"),
            ("ebktop:prescaling", "ebkangle:prescaling", "matrix_label:row:prescaling:primes:0",
             "bracket:prescaling:row:0:l", "bracket:prescaling:row:0:r"),
        ):
            top, foot = cells[top_id], cells[foot_id]
            label, left, right = cells[label_id], cells[left_id], cells[right_id]
            assert label.x + label.width <= top.x
            assert top.x == left.x == foot.x, "the frame's left and right edges align with the per-row brackets — it hugs the # cell matrix, not the wider grey footprint (top and bottom spans stay in lockstep)"
            assert top.x + top.width == right.x + right.width == foot.x + foot.width

    def test_prescaling_matrix_carries_its_symbol_and_caption(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, symbols=True, names=True, equivalences=False).cells}
        assert cells["symbol:prescaling:primes"].text == "𝑋"
        assert cells["caption:prescaling:primes"].text == "complexity prescaler"

    def test_complexity_prescaler_caption_mnemonic_marks_the_x_in_complexity(self):
        cells = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, names=True, mnemonics=True, equivalences=False).cells}
        cap = cells["caption:prescaling:primes"]
        assert cap.text == "complexity prescaler"
        assert cap.underlines == ((cap.text.index("x"), 1),)

    def test_weighting_is_implemented_now_that_its_region_builds(self):
        assert "weighting" in settings.IMPLEMENTED, "the weighting toggle builds content (the prescaling/complexity/weight rows), so the # Show panel must offer it live rather than greyed out"

    def test_presets_adds_the_prescaler_chooser_under_the_prescaling_tile(self):
        off = {c.id for c in _with("minimax-S", weighting=True, presets=False).cells}
        layout = _with("minimax-S", weighting=True, presets=True)
        on = {c.id: c for c in layout.cells}
        blocks = {b.id: b for b in layout.blocks}
        assert "preset:prescaler" not in off
        selection = on["preset:prescaler"]
        assert selection.kind == "preset", "with alt. complexity off there is only one prescaler (log-prime), so the chooser has no real # choice: it renders as a DISABLED dropdown (greyed), not an interactive one"
        assert selection.disabled is True
        assert selection.text == "log-prime"
        pre = on["cell:prescaling:primes:2:2"]
        box = blocks["block:preset:prescaler"]
        assert selection.y > pre.y
        assert selection.x == box.x + spreadsheet_constants.BOX_INNER
        assert box.x <= pre.x and pre.x + pre.width <= box.x + box.width
        assert "preset:prescaler" not in {c.id for c in _with("minimax-S", weighting=False, presets=True).cells}
        assert "preset:prescaler" not in {
            c.id for c in _with("minimax-S", weighting=True, presets=True, temperament_tiles=False).cells}

    def test_prescaler_chooser_shows_dash_when_a_custom_diagonal_deviates(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["weighting"], s["alt_complexity"] = True, True, True
        scheme = "TILT minimax-S"
        named = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme).cells}
        assert named["preset:prescaler"].text == "log-prime"
        devi = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme,
                                                   custom_prescaler=(1.0, 9.9, 2.322)).cells}
        assert devi["preset:prescaler"].text == ""

    def test_editing_the_prescaler_wipes_the_predefined_complexity_to_custom(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = settings.defaults()
        s["presets"], s["weighting"], s["alt_complexity"] = True, True, True
        scheme = "TILT minimax-S"
        named = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme).cells}
        assert named["control:complexity"].text == "lp (log-product)"
        devi = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme=scheme,
                                                   custom_prescaler=(1.0, 9.9, 2.322)).cells}
        assert devi["preset:prescaler"].text == ""
        assert devi["control:complexity"].text == "custom"

    def test_complexity_machinery_hides_under_unity_weight(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True}
        unity = {c.id for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-U").cells}
        simpl = {c.id for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
        assert not any(c.startswith("complexity:") for c in unity)
        assert "control:complexity" not in unity and "control:q" not in unity
        assert "control:slope" in unity and any(c.startswith("weight:target") for c in unity)
        assert any(c.startswith("complexity:") for c in simpl)
        assert "control:q" in simpl
        assert not any(c.startswith("cell:prescaling") for c in unity)
        assert not any(c.startswith("cell:prescaling") for c in simpl)

    def test_prescaling_band_needs_alt_complexity_or_all_interval(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))

        def cells(scheme, **over):
            s = {**settings.defaults(), "weighting": True, **over}
            return {c.id for c in spreadsheet.build(base, s, tuning_scheme=scheme).cells}

        ordinary = cells("TILT minimax-S")
        with_alt = cells("TILT minimax-S", alt_complexity=True)
        all_int = cells("minimax-S")
        for c in (ordinary, with_alt):
            assert any(x.startswith("complexity:") for x in c)
        assert not any(x.startswith("cell:prescaling") for x in ordinary)
        assert any(x.startswith("cell:prescaling") for x in with_alt)
        assert any(x.startswith("cell:prescaling") for x in all_int)

    def test_box_c_complexity_chooser_is_disabled_until_alt_complexity(self):
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, presets=True).cells}
        ctrl = on["control:complexity"]
        assert ctrl.kind == "control_select"
        assert ctrl.disabled is True
        assert on["caption:complexity"].disabled is True
        assert ctrl.text == "lp (log-product)"
        assert ctrl.values == ("lp (log-product)",)
        assert ctrl.y > on["complexity:target:0"].y
        assert ctrl.x == on["header:targets"].x + spreadsheet_constants.BOX_INNER
        full = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True, presets=True).cells}
        assert full["control:complexity"].disabled is False
        assert full["control:complexity"].values == tuple(service.COMPLEXITY_DISPLAYS.values()) + ("custom",)

    def test_predefined_complexities_dropdown_is_gated_on_presets(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True}
        off = {c.id: c for c in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").cells}
        assert "control:complexity" not in off and "caption:complexity" not in off
        assert "control:q" in off
        on = {c.id: c for c in spreadsheet.build(base, {**s, "presets": True}, tuning_scheme="TILT minimax-S").cells}
        assert "control:complexity" in on and "caption:complexity" in on
        assert off["control:q"].x < on["control:q"].x
        off_box = {b.id: b for b in spreadsheet.build(base, s, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
        on_box = {b.id: b for b in spreadsheet.build(base, {**s, "presets": True}, tuning_scheme="TILT minimax-S").blocks}["block:complexity"]
        assert off_box.width <= on_box.width

    def test_box_c_lays_out_with_q_and_dual_q_norm_power_fields(self):
        on = {c.id: c for c in _with(scheme="minimax-S", weighting=True, presets=True,
                                     all_interval=True, alt_complexity=True).cells}
        assert on["caption:complexity"].kind == "caption"
        assert on["caption:complexity"].text == "predefined complexities"
        assert on["caption:complexity"].y == on["control:complexity"].y + on["control:complexity"].height
        assert on["control:q"].kind == "powerinput"
        assert on["control:q"].text == "1"
        assert on["control:q"].x > on["control:complexity"].x
        assert on["control:q"].y == on["control:complexity"].y
        assert on["symbol:q"].text == "𝑞"
        assert on["symbol:q"].y > on["control:q"].y
        assert on["caption:q"].text == "interval complexity norm power"
        assert on["caption:q"].y > on["symbol:q"].y
        assert on["control:dual"].kind == "powerdisplay", "the dual(q) display: the dual norm power, DERIVED from q (never edited), so it renders as a # read-only powerdisplay — the same face as q (∞ at the q numeral's size), minus the white box"
        assert on["control:dual"].text == "∞"
        assert on["control:dual"].x > on["control:q"].x
        assert on["symbol:dual"].text == "dual(𝑞)"
        assert on["caption:dual"].text == "dual norm power"
        assert on["caption:q"].y == on["caption:dual"].y, "the q and dual(q) captions sit at the same y (one tidy row); the dropdown's caption hugs # higher up against the dropdown's bottom, so it is ABOVE that row"
        assert on["caption:complexity"].y < on["caption:q"].y
        assert "control:norm" not in on


class TestGriddedValuesToggle:
    def test_q_norm_power_is_editable_only_with_alt_complexity(self):
        off = {c.id: c for c in _with("TILT minimax-S", weighting=True).cells}
        assert off["control:q"].kind == "powerdisplay"
        on = {c.id: c for c in _with("TILT minimax-S", weighting=True, alt_complexity=True).cells}
        assert on["control:q"].kind == "powerinput"
        assert off["control:q"].text == on["control:q"].text == "1"

    def test_power_value_cells_hide_when_gridded_values_are_off(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "weighting": True, "optimization": True}
        off = {c.id for c in spreadsheet.build(base, {**s, "gridded_values": False}, tuning_scheme="minimax-S").cells}
        assert not ({"control:q", "control:dual", "optimization:power"} & off)
        on = {c.id for c in spreadsheet.build(base, {**s, "gridded_values": True}, tuning_scheme="minimax-S").cells}
        assert {"control:q", "control:dual", "optimization:power"} <= on

    def test_gridded_values_off_hides_the_nonstandard_domain_element_cells_and_controls(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        s = {**settings.defaults(), "nonstandard_domain": True, "projection": True}
        on = {c.id: c for c in spreadsheet.build(state, {**s, "gridded_values": True}).cells}
        off = {c.id for c in spreadsheet.build(state, {**s, "gridded_values": False}).cells}
        assert on["prime:0"].kind == "elementcell" and on["prime:2"].kind == "elementratio"
        assert on["basis:0"].kind == "elementcell" and on["basis_plus"].kind == "element_plus"
        domain_value_ids = {"prime:0", "prime:1", "prime:2", "basis:0", "basis:1", "basis:2"}
        domain_control_ids = {"element_minus:0", "element_minus:1", "element_minus:2",
                              "element_minus:basis:0", "element_minus:basis:1", "element_minus:basis:2",
                              "element_plus", "basis_plus"}
        projection_grid_ids = {c for c in on if c.startswith(("cell:projection:", "cell:embed:"))}
        assert projection_grid_ids and all(on[c].kind == "mapped" for c in projection_grid_ids)
        assert domain_value_ids <= on.keys() and domain_control_ids <= on.keys()
        assert not (domain_value_ids & off)
        assert not (domain_control_ids & off)
        assert not (projection_grid_ids & off)

    def test_gridded_values_off_hides_the_editable_unchanged_basis_cells(self):
        mt = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        s = {**settings.defaults(), "projection": True}
        on = {c.id: c for c in spreadsheet.build(mt, {**s, "gridded_values": True}, held_basis_ratios=("2/1", "5/4")).cells}
        off = {c.id for c in spreadsheet.build(mt, {**s, "gridded_values": False}, held_basis_ratios=("2/1", "5/4")).cells}
        unchanged_ids = {c for c in on if c.startswith("cell:unchanged:")}
        assert unchanged_ids and all(on[c].kind == "unchangedcell" for c in unchanged_ids)
        assert not (unchanged_ids & off)

    def test_dual_q_shows_only_when_the_scheme_is_all_interval(self):
        on_all = {c.id for c in _with(scheme="minimax-S", weighting=True, presets=True).cells}
        assert {"control:dual", "symbol:dual", "caption:dual"} <= on_all
        on_tilt = {c.id for c in _with(scheme="TILT minimax-S", weighting=True, presets=True).cells}
        assert not ({"control:dual", "symbol:dual", "caption:dual"} & on_tilt)
        assert {"control:q", "control:complexity"} <= on_tilt

    def test_all_interval_removes_all_redundant_target_tiles(self):
        removed = ["block:mapped", "block:prescaling:targets", "block:tuning:targets",
                   "block:just:targets", "block:retune:targets"]
        based = {b.id for b in _with(scheme="TILT minimax-S", weighting=True, alt_complexity=True).blocks}
        allint = {b.id for b in _with(scheme="minimax-S", weighting=True).blocks}
        for bid in removed:
            assert bid in based, bid
            assert bid not in allint, bid
        assert {"block:vector:targets", "block:complexity:targets", "block:weight:targets",
                "block:damage:targets"} <= allint

    def test_all_interval_removes_the_superspace_target_lifts_too(self):
        state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        def blocks(scheme):
            s = settings.defaults()
            s["nonstandard_domain"], s["weighting"] = True, True
            return {b.id for b in spreadsheet.build(state, s, tuning_scheme=scheme).blocks}
        based, allint = blocks("TILT minimax-S"), blocks("minimax-S")
        for bid in ("block:superspace_vectors:targets", "block:superspace_mapping:targets"):
            assert bid in based, bid
            assert bid not in allint, bid
        assert {"block:superspace_vectors:primes", "block:superspace_mapping:primes"} <= allint

    def test_all_interval_relabels_the_optimization_mean_damage(self):
        based = {c.id: c for c in _with(scheme="TILT minimax-S", optimization=True).cells}
        assert based["optimization:mean_damage:symbol"].text == "⟪𝐝⟫ₚ"
        allint = {c.id: c for c in _with(scheme="minimax-S", optimization=True).cells}
        expected = "⟪𝒓𝐿⁻¹⟫" + grid_tables.SUB_OPEN + "dual(𝑞)" + grid_tables.SUB_CLOSE
        assert allint["optimization:mean_damage:symbol"].text == expected
        assert "⟪" in expected and "⟫" in expected and "‖" not in expected, "the symbol denotes the SAME quantity as the value it labels: a power-MEAN (double-angle), not a # norm (single bars). Guards the off-by-√d mean/norm confusion (tuning-core-6)"

    def test_optimization_mean_damage_carries_a_label_caption(self):
        based = _with(scheme="TILT minimax-S", optimization=True)
        allint = _with(scheme="minimax-S", optimization=True)
        on_based = {c.id: c for c in based.cells}
        on_allint = {c.id: c for c in allint.cells}
        assert on_based["optimization:mean_damage:caption"].text == "power mean"
        assert on_allint["optimization:mean_damage:caption"].text == "retuning magnitude"
        cap = on_based["optimization:mean_damage:caption"]
        mean_damage = on_based["optimization:mean_damage"]
        sym = on_based["optimization:mean_damage:symbol"]
        assert cap.y > sym.y
        assert abs((cap.x + cap.width / 2) - (mean_damage.x + mean_damage.width / 2)) < 0.5
        assert on_based["optimization:mean_damage:caption"].height == spreadsheet_constants.CAPTION_LINE, "target-based the short label is one line; all-interval the wide label reserves two, so the # box (and thus the damage tile) grows by exactly that extra line"
        assert on_allint["optimization:mean_damage:caption"].height == 2 * spreadsheet_constants.CAPTION_LINE
        box_based = {b.id: b for b in based.blocks}["block:optimization:box"]
        box_allint = {b.id: b for b in allint.blocks}["block:optimization:box"]
        assert box_allint.height == box_based.height + spreadsheet_constants.CAPTION_LINE

    def test_all_interval_locks_the_optimization_power_to_infinity(self):
        finite_ai = service.scheme_with_power("minimax-S", 2.0)
        assert service.is_all_interval(finite_ai) and service.optimization_power(finite_ai) == 2.0
        allint = {c.id: c for c in _with(scheme=finite_ai, optimization=True).cells}
        assert allint["optimization:power"].text == "∞" and allint["optimization:power"].kind == "powerdisplay"
        finite_based = service.scheme_with_power("TILT minimax-S", 2.0)
        based = {c.id: c for c in _with(scheme=finite_based, optimization=True,
                                        weighting=True, alt_complexity=True).cells}
        assert based["optimization:power"].text == "2" and based["optimization:power"].kind == "powerinput"
