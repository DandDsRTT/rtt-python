import json

import pytest
from _spreadsheet_support import _layout, _projection_build

from rtt.app.page_assets import _pump_type_js, _pump_type_options
from rtt.app.service.pump import comma_pump_chords, pump_payload

_J5 = (1200.0, 1901.955, 2786.3137)
_T5 = (1200.0, 1896.578, 2786.312)
_J7 = (1200.0, 1901.955, 2786.3137, 3368.8259)
_T64_63 = (1200.0, 1896.578, 2786.312, 3406.844)


class TestCommaPumpChords:
    def test_syntonic_pump_is_the_classic_I_vi_ii_V(self):
        roots, qualities, seventh = comma_pump_chords([-4, 4, -1])
        assert roots == [(0, 0, 0), (-1, -1, 1), (0, -2, 1), (1, -3, 1), (2, -4, 1)]
        assert qualities == ["major", "minor", "minor", "major", "major"]
        assert seventh is False

    def test_the_returning_tonic_equals_the_negated_comma_modulo_octaves(self):
        for comma in ([-4, 4, -1], [11, -4, -2], [1, -5, 3]):
            roots, _q, _s = comma_pump_chords(comma)
            returning = roots[-1]
            assert [returning[k] - (-comma[k]) for k in range(1, len(comma))] == [0] * (len(comma) - 1)

    def test_prime5_free_comma_falls_back_to_open_fifth_chords(self):
        roots, qualities, seventh = comma_pump_chords([-19, 12, 0])
        assert set(qualities) == {"open"} and len(roots) == 13
        assert all(roots[i + 1][1] - roots[i][1] == -1 for i in range(len(roots) - 1))

    def test_prime7_comma_flags_the_seventh(self):
        _r, _q, seventh = comma_pump_chords([6, -2, 0, -1])
        assert seventh is True


class TestPumpPayload:
    def test_payload_carries_roots_tones_and_qualities_in_both_flavors(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert set(d) == {"ji", "t", "cji", "ct", "q", "types", "dji", "dt", "eji", "et"}
        assert d["q"] == ["major", "minor", "minor", "major"]
        assert d["ji"] == pytest.approx([0.0, 884.3587, 182.4037, 680.4487], abs=1e-3)

    def test_each_chord_is_a_just_triad_above_its_root(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert d["cji"][0] == pytest.approx([0.0, 386.314, 701.955, 1200.0], abs=1e-3)
        assert d["cji"][1] == pytest.approx([0.0, 315.641, 701.955, 1200.0], abs=1e-3)

    def test_tempered_chords_retune_the_thirds_and_fifths_toward_the_temperament(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert d["ct"][0] == pytest.approx([0.0, 386.312, 696.578, 1200.0], abs=1e-3)
        assert d["ct"][1] == pytest.approx([0.0, 310.266, 696.578, 1200.0], abs=1e-3)
        assert d["ct"] != d["cji"], "meantone narrows the fifth and shifts the minor third off just"

    def test_tempered_drift_closes_while_just_sinks_by_the_comma(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        assert abs(d["dt"]) < 1e-9, "the comma is tempered out, so one lap returns home to float precision"
        assert d["dji"] == pytest.approx(-21.5063, abs=1e-3), "in JI each lap sinks flat by the comma"

    def test_consecutive_chords_share_a_common_tone_when_tempered(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5))
        equave = d["et"]

        def classes(step):
            return {round((d["t"][step] + o) % equave, 3) for o in d["ct"][step][:3]}

        for step in range(len(d["t"])):
            shared = classes(step) & classes((step + 1) % len(d["t"]))
            assert shared, f"chord {step} shares no tone with the next"

    def test_open_pump_offers_a_septimal_top_when_the_comma_has_prime_seven(self):
        d = json.loads(pump_payload([6, -2, 0, -1], _J7, _T64_63))
        assert set(d["q"]) == {"open"}
        assert d["cji"][0] == pytest.approx([0.0, 701.955, 1200.0, 968.826], abs=1e-3)

    def test_degenerate_and_untempered_payloads_are_empty(self):
        assert pump_payload([0, 0, 0], _J5, _T5) == ""
        assert pump_payload([-4, 4, -1], _J5, (1200.0, 1896.578)) == ""
        assert pump_payload([-4, 4, -1], _J5, (1200.0, 1901.0, 2786.0)) == "", "a map that does not temper the comma yields no closing pump"


class TestPumpChordTypes:
    def test_types_offer_fixed_shapes_alongside_mixed(self):
        types = json.loads(pump_payload([-4, 4, -1], _J5, _T5))["types"]
        assert {"fifth", "fourth", "major third", "minor third", "neutral third"} <= set(types)
        assert {"major", "minor", "neutral", "diminished", "augmented"} <= set(types)
        assert {"dominant seventh", "major seventh", "minor seventh"} <= set(types)

    def test_fixed_major_and_minor_are_just_triads_tempered_to_the_temperament(self):
        types = json.loads(pump_payload([-4, 4, -1], _J5, _T5))["types"]
        assert types["major"]["ji"] == pytest.approx([0.0, 386.314, 701.955], abs=1e-3)
        assert types["minor"]["ji"] == pytest.approx([0.0, 315.641, 701.955], abs=1e-3)
        assert types["major"]["t"] == pytest.approx([0.0, 386.312, 696.578], abs=1e-3)
        assert types["fifth"]["ji"] == pytest.approx([0.0, 701.955], abs=1e-3)

    def test_ambiguous_intervals_track_the_temperament(self):
        five = json.loads(pump_payload([-4, 4, -1], _J5, _T5))["types"]
        assert five["diminished"]["ji"][2] == pytest.approx(609.776, abs=1e-3), "5-limit → 64/45"
        assert five["augmented"]["ji"][2] == pytest.approx(772.627, abs=1e-3), "5-limit → 25/16"
        assert five["minor seventh"]["ji"][3] == pytest.approx(1017.596, abs=1e-3), "5-limit → 9/5"
        seven = json.loads(pump_payload([6, -2, 0, -1], _J7, _T64_63))["types"]
        assert seven["diminished"]["ji"][2] == pytest.approx(582.512, abs=1e-3), "prime 7 → 7/5"
        assert seven["minor seventh"]["ji"][3] == pytest.approx(968.826, abs=1e-3), "prime 7 → 7/4"

    def test_foreign_tones_stay_just_while_domain_tones_temper(self):
        five = json.loads(pump_payload([-4, 4, -1], _J5, _T5))["types"]
        assert five["dominant seventh"]["t"][3] == pytest.approx(968.826, abs=1e-3), "no prime 7 in 5-limit → just 7/4"
        assert five["dominant seventh"]["t"][2] == pytest.approx(696.578, abs=1e-3), "the fifth still tempers"


class TestPumpTypeOptions:
    def test_type_options_depend_on_chord_size(self):
        assert _pump_type_options(1) == [], "a monad has no chord type"
        assert set(_pump_type_options(2)) == {"mixed", "fifth", "fourth", "major third", "minor third", "neutral third"}
        assert set(_pump_type_options(3)) == {"mixed", "major", "minor", "neutral", "diminished", "augmented"}
        assert set(_pump_type_options(4)) == {"mixed", "dominant seventh", "major seventh", "minor seventh"}
        assert all("mixed" in _pump_type_options(n) for n in (2, 3, 4)), "mixed is offered at every size"

    def test_labels_are_spelled_out_not_abbreviated(self):
        labels = [label for size in (2, 3, 4) for label in _pump_type_options(size)]
        assert "major third" in labels and "neutral third" in labels
        assert "dominant seventh" in labels and "major seventh" in labels and "minor seventh" in labels
        assert not any(any(abbr in label for abbr in ("3rd", "7 ", " 7", "maj ", "min ", "dom ")) for label in labels)

    def test_choosing_a_type_issues_the_engine_call_with_the_picked_label(self):
        js = _pump_type_js("major third")
        assert 'window.rttAudio.setPumpType("major third")' in js, "the picked label is fed straight to the engine"
        assert "rttBusy" in js and "done()" in js, "and the busy scrim is cleared so no Computing… hangs"


class TestPumpStamping:
    def test_comma_column_cells_carry_the_pump_payload(self):
        cells = {c.id: c for c in _layout().cells}
        ratio = cells["comma:0"]
        assert ratio.pump, "the quantities-column comma ratio cell offers the pump"
        d = json.loads(ratio.pump)
        assert set(d) == {"ji", "t", "cji", "ct", "q", "types", "dji", "dt", "eji", "et", "score"}
        assert len(d["ji"]) == len(d["cji"]) == len(d["q"]) == len(d["score"]["steps"]) == 4
        assert d["q"] == ["major", "minor", "minor", "major"]
        assert abs(d["dt"]) < 1e-6 and abs(abs(d["dji"]) - 21.5063) < 1e-3
        vector_pumps = [c.pump for c in cells.values() if c.kind == "comma_cell"]
        assert vector_pumps and all(p == ratio.pump for p in vector_pumps), "every cell of the comma's column shares one payload"

    def test_noncomma_and_unchanged_columns_carry_no_pump(self):
        layout = _layout()
        assert all(not c.pump for c in layout.cells if c.kind in ("prime", "target_cell", "held_cell", "unchanged_cell", "generator_ratio"))
        assert all(not c.pump for c in layout.cells if c.audio is not None and not c.audio[0].endswith(":commas")), "only the commas tiles' columns offer a pump"
        assert any(c.pump for c in layout.cells if c.kind == "mapped" and c.audio is not None and c.audio[0] == "mapped:commas"), "the mapping row's slice of the comma's column offers it too"
        unchanged = [c for c in _projection_build(("3/2",)).cells if c.audio is not None and c.audio[0].endswith(":commas") and c.audio[1] >= 1]
        assert unchanged and all(not c.pump for c in unchanged), "unchanged-interval columns share the commas tile but are not pumpable"

    def test_pump_tempered_chords_reflect_the_temperament_not_ji(self):
        cells = {c.id: c for c in _layout().cells}
        d = json.loads(cells["comma:0"].pump)
        assert d["t"] != d["ji"], "meantone retunes the pump's roots away from their just sizes"
        assert d["ct"] != d["cji"], "and retunes the chord tones too"

    def test_retagging_a_changed_pump_payload_flushes_the_element_to_the_client(self):
        from types import SimpleNamespace

        from rtt.app._recon_cells import tag_audio
        element = SimpleNamespace(_props={}, updates=0)
        element.update = lambda: setattr(element, "updates", element.updates + 1)
        element.classes = lambda add=None: element
        element.props = lambda _: element
        old = SimpleNamespace(audio=("vectors:commas", 0, 0.0), pump="OLD")
        tag_audio(element, old)
        assert element._props["data-pump"] == "OLD" and element.updates == 1
        tag_audio(element, old)
        assert element.updates == 1, "an unchanged payload must not dirty the element"
        tag_audio(element, SimpleNamespace(audio=("vectors:commas", 0, 0.0), pump="NEW"))
        assert element._props["data-pump"] == "NEW" and element.updates == 2, "a comma swap can change ONLY the payload — it must still flush"
        tag_audio(element, SimpleNamespace(audio=("vectors:commas", 0, 0.0), pump=""))
        assert "data-pump" not in element._props and element.updates == 3

    def test_update_gate_signature_counts_a_pump_only_change(self):
        from dataclasses import replace as _replace
        from types import SimpleNamespace

        from rtt.app import _rendering_ops
        from rtt.app._recon_handles import CellHandles
        cell = next(c for c in _layout().cells if c.id == "comma:0")
        handles, seen = CellHandles(), []
        rec = SimpleNamespace(handles=lambda cid: handles, cells={cell.id: handles}, update_cell=lambda c: seen.append(c.pump))
        r = SimpleNamespace(_rec=rec)
        _rendering_ops.update_cell_content(r, cell)
        _rendering_ops.update_cell_content(r, cell)
        assert len(seen) == 1, "an unchanged cell must not re-update"
        _rendering_ops.update_cell_content(r, _replace(cell, pump='{"other":1}'))
        assert len(seen) == 2, "a comma swap can leave text/audio/size identical and change ONLY the pump — the gate must still update"
