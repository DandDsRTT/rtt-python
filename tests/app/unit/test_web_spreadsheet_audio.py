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
from _spreadsheet_support import _memoized_build, _layout, _with, _projection_build, _with_interest, _maximized_superspace_builder, _INTEREST, _held, _CANON_MEANTONE, _canonical_cells


class TestPerCellAudio:
    def test_comma_ratio_cell_is_click_to_play_with_its_just_size(self):
        cells = {c.id: c for c in _layout().cells}
        cb = cells["comma:0"]
        assert cb.audio is not None
        tile, index, cents = cb.audio
        assert (tile, index) == ("quantities:commas", 0)
        assert abs(abs(cents) - 21.506) < 0.01, "the meantone comma 81/80 is ~21.506¢ JUST (it is tempered to ~0¢) — so a magnitude of ~21.5 # confirms the ratio sounds the JUST size, not the tempered one (sign is the comma's stored # orientation, the same value the old audio rows sounded)"

    def test_prime_plays_its_just_size_and_a_generator_plays_its_tuned_size(self):
        cells = {c.id: c for c in _layout().cells}
        p = cells["prime:1"]
        assert p.audio is not None
        tile, index, cents = p.audio
        assert (tile, index) == ("quantities:primes", 1)
        assert abs(cents - 1901.955) < 0.01
        g = cells["quantities_generator:0"]
        assert g.audio is not None and g.audio[0] == "quantities:generators" and abs(g.audio[2]) > 100

    def test_tuning_sounds_tempered_just_sounds_just_and_retuning_errors_are_silent(self):
        cells = {c.id: c for c in _layout().cells}
        tuned = cells["tuning:comma:0"]
        assert tuned.audio is not None and tuned.audio[0] == "tuning:commas"
        assert abs(tuned.audio[2]) < 0.01
        just = cells["just:comma:0"]
        assert just.audio is not None and just.audio[0] == "just:commas"
        assert abs(abs(just.audio[2]) - 21.506) < 0.01
        assert all(c.audio is None for c in cells.values() if c.id.startswith("retune:")), "the retuning-error row is not a pitch — none of its cells play"

    def test_generator_map_cell_sounds_the_generators_tuned_size(self):
        cells = {c.id: c for c in _layout().cells}
        g = cells["tuning:generator:0"]
        assert g.audio is not None
        tile, index, cents = g.audio
        assert (tile, index) == ("tuning:generators", 0)
        assert abs(cents) > 100, "a real generator pitch, not silence"
        assert abs(cents - float(cells["tuning:generator:0"].text)) < 0.6

    def test_one_pass_voices_every_interval_cell_so_none_are_silently_missed(self):
        s = settings.defaults()
        for key, val in list(s.items()):
            if isinstance(val, bool):
                s[key] = True
        cells = spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))),
            s,
            held_basis_ratios=("2/1", "5/4"),
            interest=((-2, 0, 1),),
        ).cells
        interval_kinds = {
            "commacell", "commaratio", "ratiocell", "targetcell", "heldcell", "interestcell",
            "vec", "unchangedcell", "elementcell", "elementratio", "generator_ratio", "mapped",
        }
        not_a_pitch = (
            "cell:mapping", "cell:canonical:", "cell:form", "cell:finv", "cell:scaling",
            "cell:vec:primes", "retune:", "damage:", "weight:", "optimization:",
            "cell:proj:", "cell:embed_sl", "cell:proj_sl", "cell:ss",
            "cell:selfmap", "cell:fcancel",
        )
        silent = [
            c.id
            for c in cells
            if c.kind in interval_kinds and c.audio is None and not c.pending
            and not c.id.startswith(not_a_pitch)
        ]
        assert silent == [], silent

    def test_a_rows_ratio_mirror_voices_each_entry_as_its_own_interval(self):
        cells = {c.id: c for c in _layout().cells}
        mirror = [cells[f"basis:{i}"] for i in range(3)]
        assert [m.audio[1] for m in mirror] == [0, 1, 2], "distinct idx, not all 0"
        assert abs(mirror[0].audio[2] - 1200) < 0.01 and abs(mirror[1].audio[2] - 1901.955) < 0.01

    def test_audio_voices_exactly_the_tiles_whose_ebk_inner_is_a_vector(self):
        from rtt.app import spreadsheet_audio as audio
        b = _maximized_superspace_builder()
        g, layout, ss = b.geometry, b.layout(), b.resolved.flags.superspace
        bands = sorted(g.rows.items(), key=lambda kv: kv[1].y)
        spans = [(ck, g.content_x[ck], g.content_width[ck]) for ck in g.content_x]
        missed, wrongly = [], []
        for c in layout.cells:
            if c.kind not in audio._INTERVAL_KINDS or c.pending:
                continue
            rkey = audio._band_of(bands, c.y + c.height / 2)
            ckey = audio._col_of(spans, c.x + c.width / 2)
            if rkey is None or ckey is None:
                continue
            plays = c.audio is not None and c.audio[0].startswith(tuple(audio._TILE_PREFIX.values()))
            if audio._is_interval_tile(rkey, ckey, ss):
                if not plays and c.text and c.text != "—":
                    missed.append((rkey, ckey, c.id))
            elif plays:
                wrongly.append((rkey, ckey, c.id))
        assert not missed, f"interval tiles with a silent value cell: {missed[:12]}"
        assert not wrongly, f"non-interval tiles that wrongly play: {wrongly[:12]}"

    def test_every_interval_ratio_and_vector_is_click_to_play(self):
        base = {c.id: c for c in _layout().cells}
        tr = next(c for c in base.values() if c.id.startswith("target:") and c.id != "target:pending")
        assert tr.audio and tr.audio[0] == "quantities:targets"
        tv = next(c for c in base.values() if c.id.startswith("cell:vector:targets:"))
        assert tv.audio and tv.audio[0] == "vectors:targets"
        assert base["cell:comma:0:0"].audio and base["cell:comma:0:0"].audio[0] == "vectors:commas"
        interest = {c.id: c for c in _with_interest([(-2, 0, 1)]).cells}
        ir = next(c for c in interest.values() if c.id.startswith("interest:") and c.id != "interest:pending")
        assert ir.audio and ir.audio[0] == "quantities:interest"
        iv = next(c for c in interest.values() if c.id.startswith("cell:interest:"))
        assert iv.audio and iv.audio[0] == "vectors:interest"
        held = _held()
        hr = next(c for c in held.values() if c.id.startswith("held:") and c.id != "held:pending")
        assert hr.audio and hr.audio[0] == "quantities:held"
        hv = next(c for c in held.values() if c.id.startswith("cell:held:"))
        assert hv.audio and hv.audio[0] == "vectors:held"
        det = {c.id: c for c in _with(generator_detempering=True).cells}
        assert det["detempering:0"].audio and det["detempering:0"].audio[0] == "quantities:detempering"
        dv = next(c for c in det.values() if c.id.startswith("cell:vector:detempering:"))
        assert dv.audio and dv.audio[0] == "vectors:detempering"

    def test_mapped_interval_column_sounds_tempered_size_distinct_from_the_just_ratio(self):
        cells = {c.id: c for c in _layout().cells}
        mapped_target = cells["cell:mapped:0:1"]
        assert mapped_target.audio is not None
        assert mapped_target.audio[0] == "mapped:targets" and mapped_target.audio[1] == 1
        just_ratio = cells["target:1"]
        assert just_ratio.audio[0] == "quantities:targets"
        assert abs(just_ratio.audio[2] - mapped_target.audio[2]) > 1.0

    def test_mapped_comma_column_sounds_its_tempered_out_unison(self):
        cells = {c.id: c for c in _layout().cells}
        mapped_comma = cells["cell:mapped_comma:0:0"]
        assert mapped_comma.audio is not None and mapped_comma.audio[0] == "mapped:commas"
        assert abs(mapped_comma.audio[2]) < 0.01

    def test_projected_interval_columns_are_click_to_play_when_the_projection_is_rational(self):
        full = {c.id: c for c in _projection_build(held_basis_ratios=("2/1", "5/4")).cells}
        projected_target = next(c for c in full.values() if c.id.startswith("cell:projection_targets:"))
        assert projected_target.audio is not None and projected_target.audio[0] == "projection:targets"
        assert abs(projected_target.audio[2]) > 1.0

    def test_projected_intervals_stay_silent_when_the_projection_is_dashed(self):
        under_held = {c.id: c for c in _projection_build().cells}
        assert all(c.audio is None for c in under_held.values() if c.id.startswith("cell:projection_targets:"))

    def test_projected_unrotated_vector_list_is_click_to_play(self):
        cells = {c.id: c for c in _projection_build(held_basis_ratios=("2/1", "5/4")).cells}
        held_projection = next(c for c in cells.values() if c.id.startswith("cell:projection_vectors:") and ":u" in c.id)
        assert held_projection.audio is not None and held_projection.audio[0] == "projection:commas"
        assert abs(held_projection.audio[2]) > 1.0
        comma_projection = cells["cell:projection_vectors:0:0"]
        assert comma_projection.audio is not None and abs(comma_projection.audio[2]) < 0.01

    def test_form_layer_is_a_live_parent_with_three_live_subcontrols(self):
        keys = {k for _g, items in settings.SHOW_GROUPS for k, *_ in items}
        assert {"form", "form_controls", "form_tiles", "form_colorization"} <= keys
        assert settings.defaults()["form"] is False and "form" in settings.IMPLEMENTED
        assert "form" not in settings.GROUPING_PARENTS
        for child in ("form_controls", "form_tiles", "form_colorization"):
            assert settings.SUBCONTROLS[child] == "form"
            assert settings.defaults()[child] is False
            assert child in settings.IMPLEMENTED
        specific = [k for k, *_ in dict(settings.SHOW_GROUPS)["app features"]]
        assert specific.index("form") < min(specific.index(c)
                                            for c in ("form_controls", "form_tiles", "form_colorization"))


    _CANON_MEANTONE = ((1, 0, -4), (0, 1, 4))

    def test_form_layer_subscripts_the_canonical_form_objects_in_symbols(self):
        C = grid_tables.SUBSCRIPT_C
        on = _canonical_cells(symbols=True, form=True, equivalences=False)
        off = _canonical_cells(symbols=True, equivalences=False)
        assert on["symbol:mapping:primes"].text == f"𝑀{C}"
        assert on["symbol:mapping:commas"].text == f"𝑀{C}C"
        assert on["symbol:mapping:targets"].text == f"Y{C}"
        assert on["symbol:tuning:generators"].text == f"𝒈{C}"
        projection = _canonical_cells(symbols=True, projection=True, form=True, equivalences=False)
        assert projection["symbol:projection:generators"].text == f"G{C}"
        assert on["symbol:tuning:primes"].text == "𝒕"
        assert on["symbol:vectors:commas"].text == "C"
        assert off["symbol:mapping:primes"].text == "𝑀"

    def test_form_layer_subscripts_the_canonical_form_objects_in_equivalences(self):
        C = grid_tables.SUBSCRIPT_C
        on = _canonical_cells(symbols=True, equivalences=True, projection=True, form=True)
        assert on["symbol:tuning:primes"].text == f"𝒕 = 𝒈{C}𝑀{C}"
        assert on["symbol:mapping:targets"].text == f"Y{C} = 𝑀{C}T"
        assert on["symbol:projection:generators"].text == f"G{C} = U(𝑀{C}U)⁻¹"

    def test_form_layer_subscripts_the_matrix_header_labels(self):
        C, s1 = grid_tables.SUBSCRIPT_C, spreadsheet_text._sub(1)
        on = _canonical_cells(symbols=True, header_symbols=True, form=True)
        assert on["matrix_label:row:mapping:primes:0"].text == f"𝒎{C}{s1}"
        assert on["matrix_label:column:mapping:commas:0"].text == f"𝑀{C}𝐜{s1}"
        assert on["matrix_label:column:mapping:targets:0"].text == f"𝐲{C}{s1}"
        assert on["matrix_label:column:tuning:generators:0"].text == f"𝒈{C}{s1}"
        assert on["matrix_label:column:tuning:commas:0"].text == f"𝒕𝐜{s1}"
        assert on["matrix_label:column:vectors:commas:0"].text == f"𝐜{s1}"
        held = _canonical_cells(symbols=True, header_symbols=True, form=True, optimization=True,
                            _held_vectors=[(-1, 1, 0)])
        assert held["matrix_label:column:mapping:held:0"].text == f"𝑀{C}𝐡{s1}"
        projection = _canonical_cells(symbols=True, header_symbols=True, form=True, projection=True,
                            _held_basis_ratios=("2/1", "5/4"))
        assert projection["matrix_label:column:mapping:commas:0"].text.startswith(f"𝑀{C}𝐯")
        assert projection["matrix_label:column:projection:generators:0"].text == f"𝐠{C}{s1}"

    def test_form_subscript_is_two_faced_and_the_canon_row_needs_a_noncanonical_form(self):
        C = grid_tables.SUBSCRIPT_C
        noncanon = {c.id: c for c in _with(symbols=True, form=True).cells}
        assert noncanon["symbol:mapping:primes"].text == "𝑀", "bare: not the canonical form"
        assert not any(cell_id.startswith("cell:canonical:") for cell_id in noncanon)
        canonical = _canonical_cells(symbols=True, form=True)
        assert canonical["symbol:mapping:primes"].text == f"𝑀{C}"
        assert not any(cell_id.startswith("cell:canonical:") for cell_id in canonical)
        tiles = {c.id: c for c in _with(symbols=True, form=True, form_tiles=True).cells}
        assert any(cell_id.startswith("cell:canonical:") for cell_id in tiles)
        canonical_tiles = _canonical_cells(symbols=True, form=True, form_tiles=True)
        assert not any(cell_id.startswith("cell:canonical:") for cell_id in canonical_tiles)
        assert not any(cell_id.startswith("cell:finv:") for cell_id in canonical_tiles)
        assert not any(":canonical_generators" in cell_id for cell_id in canonical_tiles)

    def test_form_box_shows_the_mapping_decomposition_equivalence_only_when_noncanonical(self):
        C = grid_tables.SUBSCRIPT_C
        on = {c.id: c for c in _with(symbols=True, equivalences=True, form_tiles=True).cells}
        assert on["symbol:mapping:primes"].text == f"𝑀 = 𝐹𝑀{C}"
        canonical = _canonical_cells(symbols=True, equivalences=True, form=True, form_tiles=True)
        assert canonical["symbol:mapping:primes"].text == f"𝑀{C}"
        off = {c.id: c for c in _with(symbols=True, equivalences=True).cells}
        assert off["symbol:mapping:primes"].text == "𝑀"

    def test_form_subscript_covers_the_whole_mapping_row_including_new_tiles(self):
        C, s1 = grid_tables.SUBSCRIPT_C, spreadsheet_text._sub(1)
        on = _canonical_cells(symbols=True, header_symbols=True, form=True, equivalences=False,
                         generator_detempering=True, identity_objects=True)
        assert on["symbol:mapping:generators"].text == f"𝑀{C}G"
        assert on["symbol:mapping:detempering"].text == f"𝑀{C}D"
        assert on["matrix_label:column:mapping:detempering:0"].text == f"𝑀{C}𝐝{s1}"

    def test_canonical_mapping_row_carries_its_own_symbols_and_row_headers(self):
        C, s1 = grid_tables.SUBSCRIPT_C, spreadsheet_text._sub(1)
        on = {c.id: c for c in _with(symbols=True, header_symbols=True, form=True, form_tiles=True).cells}
        assert on["symbol:canonical:primes"].text == f"𝑀{C}"
        assert on["symbol:canonical:generators"].text == "𝐹⁻¹"
        assert on["symbol:mapping:canonical_generators"].text == "𝐹"
        assert on["matrix_label:row:canonical:primes:0"].text == f"𝒎{C}{s1}"
        assert on["matrix_label:row:mapping:canonical_generators:0"].text == f"𝒇{s1}"

    def test_canonical_mapping_row_renders_its_mapped_product_tiles(self):
        M = ((1, 1, 0), (0, 1, 4))
        Mc = service.canonical_mapping(M)
        F = service.form_matrix(M)
        held = [(-1, 1, 0)]
        interest = ((1, -2, 1),)
        s = settings.defaults()
        s.update(form=True, form_tiles=True, generator_detempering=True, optimization=True)
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(M), s, held_vectors=held, interest=interest).cells}
        rc, r = len(Mc), len(M)
        assert [[cells[f"cell:canonical:{i}:{p}"].text for p in range(3)] for i in range(rc)] == \
            [[str(x) for x in row] for row in Mc]
        assert [[cells[f"cell:canonical_detempering:{i}:{c}"].text for c in range(r)] for i in range(rc)] == \
            [[str(x) for x in row] for row in F]
        assert all(cells[f"cell:canonical_mapped_comma:{i}:0"].text == "0" for i in range(rc))
        mc_dot = lambda v: [str(sum(Mc[i][p] * v[p] for p in range(3))) for i in range(rc)]
        assert [cells[f"cell:canonical_hmapped:{i}:0"].text for i in range(rc)] == mc_dot(held[0])
        assert [cells[f"cell:canonical_imapped:{i}:0"].text for i in range(rc)] == mc_dot(interest[0])

    def test_canonical_mapping_row_tile_symbols_units_and_equivalences(self):
        C, s1 = grid_tables.SUBSCRIPT_C, spreadsheet_text._sub(1)
        s = settings.defaults()
        s.update(form=True, form_tiles=True, symbols=True, equivalences=True, units=True, header_symbols=True,
                 generator_detempering=True, optimization=True)
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s, held_vectors=[(-1, 1, 0)]).cells}
        assert cells["symbol:canonical:detempering"].text == f"𝑀{C}D = 𝐹"
        assert cells["symbol:canonical:commas"].text == f"𝑀{C}C = O"
        assert cells["symbol:canonical:targets"].text == f"Y{C} = 𝑀{C}T"
        assert cells["symbol:canonical:held"].text == f"𝑀{C}H"
        assert cells["units:canonical:primes"].text == f"units: g{C}/p"
        assert cells["units:canonical:generators"].text == f"units: g{C}/g"
        assert cells["units:canonical:detempering"].text == f"units: g{C}"
        assert cells["units:canonical:targets"].text == f"units: g{C}"
        assert cells["matrix_label:column:canonical:detempering:0"].text == f"𝑀{C}𝐝{s1}"
        assert cells["matrix_label:column:canonical:commas:0"].text == f"𝑀{C}𝐜{s1}"
        assert cells["matrix_label:column:canonical:targets:0"].text == f"𝐲{C}{s1}"
        assert cells["matrix_label:column:canonical:held:0"].text == f"𝑀{C}𝐡{s1}"

    def test_canonical_mapping_row_commas_symbol_keeps_subscript_under_unchanged(self):
        C = grid_tables.SUBSCRIPT_C
        s = settings.defaults()
        s.update(form=True, form_tiles=True, symbols=True, header_symbols=True, projection=True, optimization=True, equivalences=False)
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
            held_basis_ratios=("2/1", "5/4")).cells}
        assert cells["symbol:canonical:commas"].text == f"𝑀{C}V", "the '= O' equivalence drops under V (the column is no longer the bare vanishing comma basis), # for both rows; what matters here is the subscript-C surviving the comma C → V swap"
        assert cells["symbol:mapping:commas"].text == "𝑀V"
        assert cells["matrix_label:column:canonical:commas:0"].text.startswith(f"𝑀{C}𝐯")

    def test_canonical_mapping_row_carries_plain_text(self):
        s = settings.defaults()
        s.update(form=True, form_tiles=True, plain_text_values=True, ebk=True,
                 generator_detempering=True, identity_objects=True, optimization=True)
        cells = {c.id: c for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
            held_vectors=[(-1, 1, 0)], interest=((1, -2, 1),)).cells}
        assert cells["plain_text:canonical:primes"].text == "[⟨1 0 -4] ⟨0 1 4]}"
        assert cells["plain_text:canonical:generators"].text == "[{1 -1] {0 1]}"
        assert cells["plain_text:canonical:canonical_generators"].text == "[{1 0] {0 1]}"
        assert cells["plain_text:canonical:detempering"].text == "{[1 0} [-1 1}]"
        assert cells["plain_text:canonical:commas"].text == "[[0 0}]"
        assert cells["plain_text:canonical:held"].text == "[[-1 1}]"
        assert cells["plain_text:canonical:interest"].text == "[-3 2}"

    def test_interest_is_a_top_level_toggle_after_the_tuning_tiles_group(self):
        items = dict(settings.SHOW_GROUPS)["app features"]
        keys = [k for k, *_ in items]
        assert keys[keys.index("tuning_colorization") + 1] == "interest"
        assert keys[keys.index("interest") + 1] == "generator_detempering"
        assert "interest" not in settings.SUBCONTROLS
        assert "interest" in settings.IMPLEMENTED
        assert settings.defaults()["interest"] is True
        label = dict((k, group_label) for k, group_label, _d in items)["interest"]
        assert label == "other intervals\nof interest"

    def test_interest_column_follows_its_own_toggle_not_tuning_tiles(self):
        off_tuning = {c.id for c in _with(tuning_tiles=False).cells}
        assert "header:targets" not in off_tuning
        assert "header:interest" in off_tuning
        s = settings.defaults(); s["interest"] = False
        off_interest = {c.id for c in spreadsheet.build(
            service.from_mapping(((1, 1, 0), (0, 1, 4))), s, interest=_INTEREST).cells}
        assert "header:interest" not in off_interest
        assert not any(c.startswith(("interest:", "cell:interest:", "cell:imapped:")) for c in off_interest)

    def test_caption_widened_commas_tile_keeps_its_fold_toggle_on_the_panel_edge(self):
        blocks = {b.id: b for b in _with(names=True).blocks}
        narrow = {b.id: b for b in _with(names=False).blocks}
        cells = {c.id: c for c in _with(names=True).cells}
        panel = blocks["block:vector:commas"]
        assert panel.width > narrow["block:vector:commas"].width
        fold = cells["toggle:tile:vectors:commas"]
        assert fold.x == panel.x + spreadsheet_constants.TOGGLE_INSET


class TestShowFlagGating:
    def test_show_flags_gate_sub_controls_under_their_parent(self):
        s = settings.defaults()
        s.update(tuning_tiles=False, optimization=True, weighting=True, alt_complexity=True,
                 names=False, mnemonics=True)
        f = spreadsheet_models._resolve_show_flags(s, frozenset())
        assert not (f.optimization or f.weighting or f.alt_complexity)
        assert not f.mnemonics
        s.update(tuning_tiles=True, names=True)
        f = spreadsheet_models._resolve_show_flags(s, frozenset())
        assert f.optimization and f.weighting and f.alt_complexity and f.mnemonics

    def test_show_flags_box_choosers_gate_on_the_collapsed_state(self):
        s = settings.defaults()
        s.update(tuning_tiles=True, weighting=True, alt_complexity=True, temperament_tiles=True)
        assert spreadsheet_models._resolve_show_flags(s, frozenset()).prescaling_box
        assert spreadsheet_models._resolve_show_flags(s, frozenset()).complexity_box
        assert not spreadsheet_models._resolve_show_flags(s, frozenset({"row:prescaling"})).prescaling_box
        assert not spreadsheet_models._resolve_show_flags(s, frozenset({"row:complexity"})).complexity_box

    def test_prescaler_labels_resolve_the_log_prime_glyph_and_gated_name(self):
        state = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        p = spreadsheet_models._resolve_prescaler_labels(state, service.DEFAULT_DOCUMENT_SCHEME, None, show_equivalences=True)
        assert p.symbol == "𝐿"
        assert p.effective_captions[("prescaling", "primes")].endswith("= log-prime matrix")
        bare = spreadsheet_models._resolve_prescaler_labels(state, service.DEFAULT_DOCUMENT_SCHEME, None, show_equivalences=False)
        assert "log-prime matrix" not in bare.effective_captions[("prescaling", "primes")]
