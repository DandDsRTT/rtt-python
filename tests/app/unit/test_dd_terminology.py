from rtt.app import presets, settings, spreadsheet, terminology
from rtt.app.editor import Editor


def _grid_texts(dd_terminology):
    layout = spreadsheet.build(Editor().state, {**settings.defaults(), "dd_terminology": dd_terminology})
    return " | ".join(cb.text for cb in layout.cells if getattr(cb, "text", None))


def test_phrase_substitution_is_identity_when_dd_terminology_on():
    assert terminology.wiki("interval vector", True) == "interval vector"
    assert terminology.wiki("comma basis", True) == "comma basis"


def test_phrase_substitution_swaps_in_wiki_terms_when_dd_terminology_off():
    assert terminology.wiki("interval vector", False) == "monzo"
    assert terminology.wiki("interval vectors", False) == "monzos"
    assert terminology.wiki("interval-vectors", False) == "monzos"
    assert terminology.wiki("comma basis", False) == "comma list"
    assert terminology.wiki("projected unrotated vector list", False) == "projected eigenmonzo and comma list"


def test_the_mapping_matrix_term_is_never_substituted():
    assert terminology.wiki("(temperament) mapping", False) == "(temperament) mapping"
    assert terminology.wiki("JI mapping", False) == "JI mapping"


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


def test_grid_captions_keep_dd_terms_when_on():
    on = _grid_texts(True)
    assert "interval vectors" in on
    assert "comma basis" in on


def test_grid_captions_show_wiki_terms_when_off():
    off = _grid_texts(False)
    assert "monzos" in off
    assert "comma list" in off
    assert "interval vectors" not in off
    assert "comma basis" not in off


def test_grid_keeps_the_mapping_term_in_both_modes():
    assert "mapping" in _grid_texts(True)
    assert "mapping" in _grid_texts(False)


def test_displayed_scheme_name_stays_the_systematic_option_key():
    editor = Editor()
    editor.set_tuning_scheme("minimax-S")
    assert editor.displayed_tuning_scheme_name == "minimax-S"
    editor.settings["dd_terminology"] = False
    assert editor.displayed_tuning_scheme_name == "minimax-S"


def test_tuning_scheme_option_labels_substitute_wiki_names_keeping_systematic_keys():
    target_based = presets.tuning_scheme_options(False, False, True, False)
    assert target_based["minimax-S"] == "T TOP"
    assert "minimax-S" in target_based
    assert target_based["minimax-U"] == "T minimax-U"
    all_interval = presets.tuning_scheme_options(True, False, False, False)
    assert all_interval["minimax-S"] == "TOP"
    assert presets.tuning_scheme_options(True, False, False, True)["minimax-S"] == "minimax-S"
