from rtt.app import presets, settings, spreadsheet, terminology
from rtt.app.editor import Editor


def _grid_texts(mode):
    layout = spreadsheet.build(Editor().state, {**settings.defaults(), "terminology": mode})
    return " | ".join(cb.text for cb in layout.cells if getattr(cb, "text", None))


def test_dd_mode_is_identity():
    assert terminology.substitute("interval vector", "dd") == "interval vector"
    assert terminology.substitute("interval vectors", "dd") == "interval vectors"
    assert terminology.scheme("minimax-S", "dd") == "minimax-S"


def test_wiki_mode_replaces_dd_terms():
    assert terminology.substitute("interval vector", "wiki") == "monzo"
    assert terminology.substitute("interval vectors", "wiki") == "monzos"
    assert terminology.substitute("prime-count vector", "wiki") == "monzo"
    assert terminology.substitute("unchanged interval basis", "wiki") == "eigenmonzo list"


def test_both_mode_keeps_dd_term_with_the_wiki_name_in_parentheses():
    assert terminology.substitute("interval vector", "both") == "interval vector (monzo)"
    assert terminology.substitute("unchanged interval basis", "both") == "unchanged interval basis (eigenmonzo list)"
    assert terminology.scheme("minimax-S", "both") == "minimax-S (TOP)"


def test_terms_with_an_accepted_non_dd_form_are_left_alone_in_every_mode():
    for mode in ("dd", "wiki", "both"):
        for text in ("comma basis", "(temperament) mapping", "JI mapping", "projected unrotated vector list"):
            assert terminology.substitute(text, mode) == text


def test_substitution_does_not_touch_unrelated_interval_phrases():
    assert terminology.substitute("target interval list", "wiki") == "target interval list"
    assert terminology.substitute("mapped generators", "wiki") == "mapped generators"


def test_every_systematic_all_interval_scheme_has_its_wiki_name():
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


def test_every_offered_all_interval_scheme_has_a_wiki_name_except_copfr():
    for name in presets.TUNING_SCHEMES:
        if name == "minimax-copfr-S":
            assert terminology.scheme(name, "wiki") == name
        else:
            assert terminology.scheme(name, "wiki") != name


def test_scheme_passes_through_unnamed_schemes_and_none():
    assert terminology.scheme("minimax-U", "wiki") == "minimax-U"
    assert terminology.scheme("minimax-copfr-S", "wiki") == "minimax-copfr-S"
    assert terminology.scheme(None, "wiki") is None


def test_terminology_registered_and_defaults_to_dd():
    assert settings.defaults()["terminology"] == "dd"
    assert Editor().settings["terminology"] == "dd"
    assert "terminology" in settings.CHAPTER


def test_terminology_round_trips_through_persistence():
    assert settings.from_persisted({"terminology": "wiki"})["terminology"] == "wiki"
    assert settings.from_persisted({"terminology": "both"})["terminology"] == "both"
    assert settings.from_persisted({})["terminology"] == "dd"


def test_interval_vector_row_label_follows_the_mode():
    assert "interval vectors" in _grid_texts("dd")
    assert "monzos" not in _grid_texts("dd")
    assert "monzos" in _grid_texts("wiki")
    assert "interval vectors" not in _grid_texts("wiki")
    assert "interval vectors (monzos)" in _grid_texts("both")


def test_grid_keeps_accepted_terms_in_every_mode():
    for mode in ("dd", "wiki", "both"):
        assert "mapping" in _grid_texts(mode)
        assert "comma basis" in _grid_texts(mode)


def test_displayed_scheme_name_stays_systematic_so_it_matches_an_option_value():
    editor = Editor()
    editor.set_tuning_scheme("minimax-S")
    assert editor.displayed_tuning_scheme_name == "minimax-S"
    editor.settings["terminology"] = "wiki"
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def test_tuning_scheme_dropdown_labels_follow_the_mode_keeping_systematic_values():
    dd = presets.tuning_scheme_options(True, True, False, "dd")
    wiki = presets.tuning_scheme_options(True, True, False, "wiki")
    both = presets.tuning_scheme_options(True, True, False, "both")
    assert set(dd) == set(wiki) == set(both)
    assert dd["minimax-S"] == "minimax-S"
    assert wiki["minimax-S"] == "TOP"
    assert both["minimax-S"] == "minimax-S (TOP)"
    assert wiki["minimax-E-copfr-S"] == "Frobenius"
