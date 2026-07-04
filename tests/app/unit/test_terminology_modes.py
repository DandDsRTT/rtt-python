import re

from rtt.app import presets, service, settings, spreadsheet, terminology, tooltips
from rtt.app.editor import Editor


def _projection_texts(mode, **overrides):
    s = {**settings.defaults(), "projection": True, "terminology": mode, **overrides}
    layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                               held_basis_ratios=("2/1", "5/4"))
    return {c.id: c for c in layout.cells}


def _grid_texts(mode):
    layout = spreadsheet.build(Editor().state, {**settings.defaults(), "terminology": mode})
    return " | ".join(cell.text for cell in layout.cells if getattr(cell, "text", None))


class TestTerminologyModes:
    def test_dd_mode_is_identity(self):
        assert terminology.substitute("interval vector", "dd") == "interval vector"
        assert terminology.substitute("interval vectors", "dd") == "interval vectors"
        assert terminology.scheme("minimax-S", "dd") == "minimax-S"

    def test_wiki_mode_replaces_dd_terms(self):
        assert terminology.substitute("interval vector", "wiki") == "monzo"
        assert terminology.substitute("interval vectors", "wiki") == "monzos"
        assert terminology.substitute("prime-count vector", "wiki") == "monzo"
        assert terminology.substitute("unchanged interval basis", "wiki") == "eigenmonzo list"
        assert terminology.substitute("mapped interval", "wiki") == "tmonzo"
        assert terminology.substitute("mapped intervals", "wiki") == "tmonzos"
        assert terminology.substitute("held interval", "wiki") == "constraint"
        assert terminology.substitute("held intervals", "wiki") == "constraints"
        assert terminology.substitute("generator detempering", "wiki") == "generator preimage transversal"
        assert terminology.substitute("unrotated vector list", "wiki") == "eigenmonzo and comma list"
        assert terminology.substitute("mapping", "wiki") == "val list"

    def test_wiki_terms_compose_into_longer_phrases(self):
        assert terminology.substitute("unchanged interval count", "wiki") == "eigenmonzo count"
        assert terminology.substitute("held interval count", "wiki") == "constraint count"
        assert terminology.substitute("canonical mapping", "wiki") == "canonical val list"
        assert terminology.substitute("generator detempering in superspace", "wiki") == "generator preimage transversal in superspace"

    def test_canonically_mapped_intervals_reads_as_canonical_tmonzos(self):
        assert terminology.substitute("canonically mapped intervals", "wiki") == "canonical tmonzos"
        assert terminology.substitute("mapped intervals", "wiki") == "tmonzos"

    def test_the_longest_matching_dd_phrase_wins(self):
        assert terminology.substitute("unchanged interval basis", "wiki") == "eigenmonzo list"
        assert terminology.substitute("unchanged interval", "wiki") == "eigenmonzo"

    def test_both_mode_keeps_dd_term_with_the_wiki_name_in_parentheses(self):
        assert terminology.substitute("interval vector", "both") == "interval vector (monzo)"
        assert terminology.substitute("unchanged interval basis", "both") == "unchanged interval basis (eigenmonzo list)"
        assert terminology.substitute("unchanged interval count", "both") == "unchanged interval (eigenmonzo) count"
        assert terminology.substitute("mapping", "both") == "mapping (val list)"
        assert terminology.scheme("minimax-S", "both") == "minimax-S (TOP)"

    def test_both_mode_never_double_substitutes_its_own_output(self):
        assert terminology.substitute("unchanged interval basis", "both") == "unchanged interval basis (eigenmonzo list)"

    def test_a_term_split_across_a_line_break_still_substitutes(self):
        assert terminology.substitute("generator\ndetempering", "wiki") == "generator preimage transversal"
        assert terminology.substitute("held\nintervals", "wiki") == "constraints"

    def test_map_the_noun_becomes_val_but_the_verb_is_left_alone(self):
        assert terminology.substitute("tuning map", "wiki") == "tuning val"
        assert terminology.substitute("generator tuning map", "wiki") == "generator tuning val"
        assert terminology.substitute("retuning map", "wiki") == "retuning val"
        assert terminology.substitute("one map per generator", "wiki") == "one val per generator"
        assert terminology.substitute("used to map intervals from your domain", "wiki") == "used to map intervals from your domain"

    def test_map_to_val_does_not_touch_mapping_or_mapped(self):
        assert terminology.substitute("mapped generators", "wiki") == "mapped generators"
        assert terminology.substitute("(temperament) mapping", "wiki") == "(temperament) val list"

    def test_terms_with_an_accepted_non_dd_form_are_left_alone_in_every_mode(self):
        for mode in ("dd", "wiki", "both"):
            for text in ("comma basis", "target interval list", "mapped generators"):
                assert terminology.substitute(text, mode) == text

    def test_substitution_does_not_touch_unrelated_interval_phrases(self):
        assert terminology.substitute("target interval list", "wiki") == "target interval list"
        assert terminology.substitute("mapped generators", "wiki") == "mapped generators"

    def test_every_systematic_all_interval_scheme_has_its_wiki_name(self):
        expected = {
            "minimax-S": "TOP",
            "held-octave minimax-S": "CTOP",
            "destretched-octave minimax-S": "POTOP",
            "minimax-ES": "TE",
            "held-octave minimax-ES": "CTE",
            "destretched-octave minimax-ES": "POTE",
            "minimax-E-copfr-S": "Frobenius",
            "minimax-sopfr-S": "BOP",
            "minimax-E-sopfr-S": "BE",
            "minimax-lils-S": "Weil",
            "held-octave minimax-lils-S": "CWOP",
            "destretched-octave minimax-lils-S": "Kees",
            "minimax-E-lils-S": "WE",
            "held-octave minimax-E-lils-S": "CWE",
            "destretched-octave minimax-E-lils-S": "POWE",
        }
        for systematic, wiki in expected.items():
            assert terminology.scheme(systematic, "wiki") == wiki
            assert terminology.scheme(systematic, "both") == f"{systematic} ({wiki})"

    def test_every_offered_all_interval_scheme_has_a_wiki_name_except_copfr(self):
        for name in presets.TUNING_SCHEMES:
            if name == "minimax-copfr-S":
                assert terminology.scheme(name, "wiki") == name
            else:
                assert terminology.scheme(name, "wiki") != name

    def test_scheme_passes_through_unnamed_schemes_and_none(self):
        assert terminology.scheme("minimax-U", "wiki") == "minimax-U"
        assert terminology.scheme("minimax-copfr-S", "wiki") == "minimax-copfr-S"
        assert terminology.scheme(None, "wiki") is None

    def test_terminology_registered_and_defaults_to_dd(self):
        assert settings.defaults()["terminology"] == "dd"
        assert Editor().settings["terminology"] == "dd"
        assert "terminology" in settings.CHAPTER

    def test_terminology_round_trips_through_persistence(self):
        assert settings.from_persisted({"terminology": "wiki"})["terminology"] == "wiki"
        assert settings.from_persisted({"terminology": "both"})["terminology"] == "both"
        assert settings.from_persisted({})["terminology"] == "dd"

    def test_interval_vector_row_label_follows_the_mode(self):
        assert "interval vectors" in _grid_texts("dd")
        assert "monzos" not in _grid_texts("dd")
        assert "monzos" in _grid_texts("wiki")
        assert "interval vectors" not in _grid_texts("wiki")
        assert "interval vectors (monzos)" in _grid_texts("both")

    def test_settings_tooltip_follows_the_mode(self):
        assert tooltips.show_help("interval_vectors", "dd") == "Show the interval vectors row."
        assert tooltips.show_help("interval_vectors", "wiki") == "Show the monzos row."
        assert tooltips.show_help("interval_vectors", "both") == "Show the interval vectors (monzos) row."

    def test_settings_tooltip_keeps_accepted_terms_in_every_mode(self):
        for mode in ("dd", "wiki", "both"):
            assert tooltips.show_help("app_units", mode) == "Show the units row and column."

    def test_no_settings_tooltip_hardcodes_a_wiki_term(self):
        wiki_terms = [wiki for _dd, wiki in terminology._PHRASE_WIKI_TERMS]
        for key, text in tooltips.SHOW_HELP.items():
            for wiki in wiki_terms:
                assert not re.search(rf"\b{re.escape(wiki)}\b", text, re.IGNORECASE), (
                    f"SHOW_HELP[{key!r}] hardcodes the wiki term {wiki!r}; write the D&D term in the "
                    "base text so show_help() can swap it per the terminology mode"
                )

    def test_grid_keeps_accepted_terms_in_every_mode(self):
        for mode in ("dd", "wiki", "both"):
            assert "comma basis" in _grid_texts(mode)

    def test_mapping_tile_name_becomes_val_list_in_wiki_mode(self):
        def name(mode):
            layout = spreadsheet.build(Editor().state, {**settings.defaults(), "terminology": mode})
            return {c.id: c for c in layout.cells}["name:mapping:primes"].text
        assert name("dd") == "(temperament) mapping"
        assert name("wiki") == "(temperament) val list"
        assert name("both") == "(temperament) mapping (val list)"

    def test_generator_detempering_column_header_follows_the_mode(self):
        s = {**settings.defaults(), "generator_detempering": True, "terminology": "wiki"}
        layout = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s)
        headers = [c.text for c in layout.cells if c.kind == "column_header"]
        assert "generator preimage transversal" in headers
        assert "generator\ndetempering" not in headers

    def test_unchanged_interval_count_follows_the_mode(self):
        dd = _projection_texts("dd", counts=True)
        both = _projection_texts("both", counts=True)
        assert dd["name:counts:commas:u"].text == "unchanged interval count"
        assert both["name:counts:commas:u"].text == "unchanged interval (eigenmonzo) count"
        assert dd["name:counts:commas"].text == "nullity"

    def test_displayed_scheme_name_stays_systematic_so_it_matches_an_option_value(self):
        editor = Editor()
        editor.set_tuning_scheme("minimax-S")
        assert editor.displayed_tuning_scheme_name == "minimax-S"
        editor.settings["terminology"] = "wiki"
        assert editor.displayed_tuning_scheme_name == "minimax-S"

    def test_tuning_scheme_dropdown_labels_follow_the_mode_keeping_systematic_values(self):
        dd = presets.tuning_scheme_options(True, True, False, "dd")
        wiki = presets.tuning_scheme_options(True, True, False, "wiki")
        both = presets.tuning_scheme_options(True, True, False, "both")
        assert set(dd) == set(wiki) == set(both)
        assert dd["minimax-S"] == "minimax-S"
        assert wiki["minimax-S"] == "TOP"
        assert both["minimax-S"] == "minimax-S (TOP)"
        assert wiki["minimax-E-copfr-S"] == "Frobenius"
