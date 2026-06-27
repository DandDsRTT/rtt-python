from rtt.app import presets, settings, spreadsheet, terminology
from rtt.app.editor import Editor


def _grid_texts(dd_terminology):
    layout = spreadsheet.build(Editor().state, {**settings.defaults(), "dd_terminology": dd_terminology})
    return " | ".join(cb.text for cb in layout.cells if getattr(cb, "text", None))


def test_phrase_substitution_is_identity_when_dd_terminology_on():
    assert terminology.wiki("interval vector", True) == "interval vector"
    assert terminology.wiki("interval vectors", True) == "interval vectors"


def test_phrase_substitution_swaps_in_wiki_terms_when_dd_terminology_off():
    assert terminology.wiki("interval vector", False) == "monzo"
    assert terminology.wiki("interval vectors", False) == "monzos"
    assert terminology.wiki("interval-vectors", False) == "monzos"
    assert terminology.wiki("prime-count vector", False) == "monzo"


def test_terms_with_an_accepted_non_dd_form_are_left_alone():
    for text in ("comma basis", "(temperament) mapping", "JI mapping", "projected unrotated vector list"):
        assert terminology.wiki(text, False) == text


def test_phrase_substitution_does_not_touch_unrelated_interval_phrases():
    assert terminology.wiki("target interval list", False) == "target interval list"
    assert terminology.wiki("mapped generators", False) == "mapped generators"


def test_scheme_name_substitution_is_identity_when_dd_terminology_on():
    assert terminology.scheme_name("minimax-S", True) == "minimax-S"
    assert terminology.scheme_name("held-octave minimax-ES", True) == "held-octave minimax-ES"


def test_scheme_name_substitution_uses_wiki_names_when_dd_terminology_off():
    assert terminology.scheme_name("minimax-S", False) == "TOP"
    assert terminology.scheme_name("minimax-ES", False) == "TE"
    assert terminology.scheme_name("held-octave minimax-ES", False) == "CTE"
    assert terminology.scheme_name("destretched-octave minimax-ES", False) == "POTE"
    assert terminology.scheme_name("minimax-sopfr-S", False) == "BOP"
    assert terminology.scheme_name("minimax-E-sopfr-S", False) == "BE"
    assert terminology.scheme_name("minimax-lils-S", False) == "Weil"
    assert terminology.scheme_name("minimax-E-lils-S", False) == "WE"
    assert terminology.scheme_name("held-octave minimax-E-lils-S", False) == "CWE"


def test_scheme_name_passes_through_unnamed_schemes_and_none():
    assert terminology.scheme_name("minimax-U", False) == "minimax-U"
    assert terminology.scheme_name(None, False) is None


def test_dd_terminology_registered_and_defaults_on():
    assert settings.defaults()["dd_terminology"] is True
    assert Editor().settings["dd_terminology"] is True
    assert "dd_terminology" in settings.CHAPTER


def test_dd_terminology_round_trips_through_persistence():
    assert settings.from_persisted({"dd_terminology": False})["dd_terminology"] is False
    assert settings.from_persisted({})["dd_terminology"] is True


def test_interval_vector_row_label_becomes_monzos_off_only():
    on = _grid_texts(True)
    off = _grid_texts(False)
    assert "interval vectors" in on
    assert "interval vectors" not in off
    assert "monzos" in off


def test_grid_keeps_accepted_terms_in_both_modes():
    for text in ("mapping", "comma basis"):
        assert text in _grid_texts(True)
        assert text in _grid_texts(False)


def test_displayed_scheme_name_stays_systematic_so_it_matches_an_option_value():
    editor = Editor()
    editor.set_tuning_scheme("minimax-S")
    assert editor.displayed_tuning_scheme_name == "minimax-S"
    editor.settings["dd_terminology"] = False
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def _scheme_cell_text(dd_terminology):
    editor = Editor()
    editor.set_tuning_scheme("minimax-S")
    layout = spreadsheet.build(
        editor.state,
        {**settings.defaults(), "presets": True, "dd_terminology": dd_terminology},
        tuning_scheme=editor.tuning_scheme,
    )
    return next(cb.text for cb in layout.cells if cb.id == "preset:tuning")


def test_scheme_name_cell_shows_the_systematic_name_when_on():
    assert _scheme_cell_text(True) == "minimax-S"


def test_scheme_name_cell_shows_the_wiki_name_when_off():
    assert _scheme_cell_text(False) == "TOP"


def test_tuning_scheme_dropdown_labels_use_wiki_names_when_off_keeping_systematic_values():
    on = presets.tuning_scheme_options(True, True, False, True)
    off = presets.tuning_scheme_options(True, True, False, False)
    assert set(on) == set(off)
    assert on["minimax-S"] == "minimax-S"
    assert off["minimax-S"] == "TOP"
    assert off["minimax-ES"] == "TE"
    assert off["minimax-E-lils-S"] == "WE"
