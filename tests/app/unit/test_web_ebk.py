"""The EBK Show toggle (off → plain matrix notation): the string transforms and the gridded marks.

EBK on (default) frames every matrix/vector in its bra-ket brackets; off rewrites the lot — both
the rendered grid marks and the plain-text strings — into plain matrix notation: every angle/curly
brace becomes a square brace, and a superscript ᵀ marks the vector kind (a column-vector list) apart
from the map kind (a covector stack / single covector / scalar list)."""

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings


_MEANTONE = "[⟨1 0 -4] ⟨0 1 4]}"


def _build(ebk: bool, **extra):
    s = app_settings.defaults()
    s.update(extra)
    s["ebk"] = ebk
    return spreadsheet.build(service.from_temperament_data(_MEANTONE), settings=s)


def _mark_kinds(layout):
    return {c.kind for c in layout.cells}


def _bracket_glyphs(layout):
    return {c.text for c in layout.cells if c.kind == "bracket"}


def _empty_target_layout(ebk: bool):
    """The meantone grid with the plain-text + weighting layers and an EXPLICIT empty target
    list (k = 0) — the prescaling/complexity layers the prescaler product tiles live under,
    with nothing in the target column."""
    s = app_settings.defaults()
    s.update({"plain_text_values": True, "weighting": True, "alt_complexity": True, "ebk": ebk})
    return spreadsheet.build(service.from_temperament_data(_MEANTONE), settings=s,
                             tuning_scheme=service.resolve_tuning_scheme("TILT minimax-S"),
                             target_spec="TILT", target_override=())


class TestWebEbk:
    def test_ebk_to_simple_matrix_squares_braces_and_marks_the_vector_kind(self):
        f = service.ebk_to_simple_matrix
        assert f("[⟨1 0 -4] ⟨0 1 4]}") == "[[1 0 -4] [0 1 4]]"
        assert f("⟨1200 1902 2786]") == "[1200 1902 2786]"
        assert f("{1201.699 697.564]") == "[1201.699 697.564]"
        assert f("[[-4 4 -1⟩ [7 0 -3⟩]") == "[[-4 4 -1] [7 0 -3]]ᵀ"
        assert f("[-4 4 -1⟩") == "[-4 4 -1]ᵀ"
        assert f("{[1 0 0⟩ [0 0 1/4⟩]") == "[[1 0 0] [0 0 1/4]]ᵀ"
        assert f("⟨[1 0⟩ [0 1⟩]") == "[[1 0] [0 1]]ᵀ"
        assert f("[1200 1902]") == "[1200 1902]"

    def test_ebk_to_simple_matrix_preserves_prefix_and_standalone_kets(self):
        f = service.ebk_to_simple_matrix
        assert f("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") == "2.3.13/5 [[1 2 2] [0 -2 -3]]"
        assert f("[-4 4 -1⟩ [7 0 -3⟩") == "[-4 4 -1]ᵀ [7 0 -3]ᵀ"
        assert f("2.3.5") == "2.3.5"
        assert f("[0 0 —]") == "[0 0 —]"

    def test_simple_matrix_to_ebk_round_trips_through_the_real_parsers(self):
        g = service.simple_matrix_to_ebk
        st = service.parse_mapping_state(g("[[1 0 -4] [0 1 4]]", False))
        assert st is not None and st.mapping == ((1, 0, -4), (0, 1, 4))
        assert service.parse_comma_basis(g("[[-4 4 -1]]ᵀ", True)) == ((-4, 4, -1),)
        assert service.parse_projection(g("[[1 1 0][0 0 0][0 1/4 1]]", False)) is not None
        assert service.parse_embedding(g("[[1 0 0] [0 0 1/4]]ᵀ", True), 3, 2) is not None
        assert service.parse_prescaler_diagonal(g("[[1 0 0] [0 1.585 0] [0 0 2.322]]", False), 3) == (1.0, 1.585, 2.322)
        assert service.parse_cents_map(g("[1201.699 697.564]", False)) == (1201.699, 697.564), "a cents map (the parser strips brackets, so either reconstruction reads)"

    def test_simple_matrix_to_ebk_inverts_the_forward_transform(self):
        f, g = service.ebk_to_simple_matrix, service.simple_matrix_to_ebk
        for ebk, vector_based in [("[⟨1 0 -4] ⟨0 1 4]}", False), ("[[-4 4 -1⟩ [7 0 -3⟩]", True),
                                  ("⟨1200 1902]", False), ("[-4 4 -1⟩", True)]:
            simple = f(ebk)
            assert f(g(simple, vector_based)) == simple

    def test_ebk_toggle_is_registered_on_by_default_from_chapter_two(self):
        assert app_settings.DEFAULTS["ebk"] is True
        assert "ebk" in app_settings.IMPLEMENTED, "a live toggle, not greyed"
        assert app_settings.CHAPTER["ebk"] == 2
        assert app_settings.reveal_chapter("ebk") == 2
        specific = [k for k, *_ in dict(app_settings.SHOW_GROUPS)["app features"]]
        assert specific.index("ebk") == specific.index("app_units") - 1
        general = [k for k, *_ in dict(app_settings.SHOW_GROUPS)["general"]]
        assert "ebk" not in general, "NOT a dummy-tile part"

    def test_ebk_on_keeps_angle_and_curly_marks_no_transpose(self):
        layout = _build(True)
        kinds = _mark_kinds(layout)
        assert {"ebkbrace", "ebkangle"} & kinds
        assert "transpose" not in kinds
        assert {"⟨", "{"} & _bracket_glyphs(layout)

    def test_ebk_off_is_a_single_square_bracket_per_matrix_no_nesting(self):
        layout = _build(False)
        kinds = _mark_kinds(layout)
        assert not ({"ebktop", "ebkbrace", "ebkangle"} & kinds)
        assert _bracket_glyphs(layout) <= {"[", "]"}
        bracket_ids = {c.id for c in layout.cells if c.kind == "bracket"}
        assert {"bracket:primes:l", "bracket:primes:r"} <= bracket_ids
        assert not any(i.startswith("bracket:map:") for i in bracket_ids)
        assert "transpose" in kinds
        assert all(c.text == "ᵀ" for c in layout.cells if c.kind == "transpose")
        assert not any(c.id == "transpose:primes" for c in layout.cells)

    def test_ebk_off_transforms_the_plain_text_strings(self):
        def plain_text(layout, rk, ck):
            return next((c.text for c in layout.cells if c.id == f"plain_text:{rk}:{ck}"), None)
        on = _build(True, plain_text_values=True)
        off = _build(False, plain_text_values=True)
        assert plain_text(on, "mapping", "primes") == "[⟨1 0 -4] ⟨0 1 4]}"
        assert plain_text(off, "mapping", "primes") == "[[1 0 -4] [0 1 4]]"
        assert plain_text(on, "vectors", "targets").startswith("[[")
        assert plain_text(off, "vectors", "targets").endswith("]ᵀ")
        assert "⟨" not in plain_text(off, "vectors", "targets") and "⟩" not in plain_text(off, "vectors", "targets")

    def test_empty_open_list_tiles_keep_their_outer_ebk(self):
        """An OPEN list/matrix tile always wears its outer [ … ] wrap — even with zero columns. The
        prescaling target tile (𝐿T) once gated its bracket on the column count, so an empty target
        list dropped the [] entirely (the brackets vanished while the sibling vectors/mapping target
        tiles still showed []); this guards that whole family of parallel rows in both EBK modes."""
        for ebk in (True, False):
            layout = _empty_target_layout(ebk)
            ids = {c.id for c in layout.cells}
            for stem in ("vector:targets", "mapped", "prescaling:targets"):
                assert f"bracket:{stem}:l" in ids and f"bracket:{stem}:r" in ids, \
                    f"ebk={ebk}: outer bracket missing for {stem} over an empty target list"
