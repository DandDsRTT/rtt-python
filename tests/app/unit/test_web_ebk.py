"""The EBK Show toggle (off → plain matrix notation): the string transforms and the gridded marks.

EBK on (default) frames every matrix/vector in its bra-ket brackets; off rewrites the lot — both
the rendered grid marks and the plain-text strings — into plain matrix notation: every angle/curly
brace becomes a square brace, and a superscript ᵀ marks the vector kind (a column-vector list) apart
from the map kind (a covector stack / single covector / scalar list)."""

from rtt.app import service, spreadsheet
from rtt.app import settings as app_settings


# ── the forward transform: EBK string → plain matrix string ──────────────────────────────────
def test_ebk_to_simple_matrix_squares_braces_and_marks_the_vector_kind():
    f = service.ebk_to_simple_matrix
    # a mapping (covector stack) is map-based — square braces, no ᵀ
    assert f("[⟨1 0 -4] ⟨0 1 4]}") == "[[1 0 -4] [0 1 4]]"
    # a single covector (a prime / tuning map) — square, no ᵀ
    assert f("⟨1200 1902 2786]") == "[1200 1902 2786]"
    # a generator map { … ] — square, no ᵀ
    assert f("{1201.699 697.564]") == "[1201.699 697.564]"
    # a comma basis (ket list) is vector-based — square braces + a trailing ᵀ
    assert f("[[-4 4 -1⟩ [7 0 -3⟩]") == "[[-4 4 -1] [7 0 -3]]ᵀ"
    # a lone ket (an interest interval) — square + ᵀ
    assert f("[-4 4 -1⟩") == "[-4 4 -1]ᵀ"
    # a generator embedding { […⟩ …] is a ket list despite the curly outer — vector-based
    assert f("{[1 0 0⟩ [0 0 1/4⟩]") == "[[1 0 0] [0 0 1/4]]ᵀ"
    # the basis-change B_L wraps ⟨ … ] (covector-style) around KET columns — still vector-based
    assert f("⟨[1 0⟩ [0 1⟩]") == "[[1 0] [0 1]]ᵀ"
    # a bare scalar/cents list is already square and map-row-like — untouched, no ᵀ
    assert f("[1200 1902]") == "[1200 1902]"


def test_ebk_to_simple_matrix_preserves_prefix_and_standalone_kets():
    f = service.ebk_to_simple_matrix
    # a domain-basis prefix rides through untouched
    assert f("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") == "2.3.13/5 [[1 2 2] [0 -2 -3]]"
    # the interest column is standalone kets (no outer wrap) — EACH gets its own ᵀ, like the plain text
    assert f("[-4 4 -1⟩ [7 0 -3⟩") == "[-4 4 -1]ᵀ [7 0 -3]ᵀ"
    # a string with no brackets (the domain primes "2.3.5") passes straight through
    assert f("2.3.5") == "2.3.5"
    # the dashed (under-held) column keeps its em-dashes; a scalar list stays map-based
    assert f("[0 0 —]") == "[0 0 —]"


# ── the inverse transform: edited plain matrix string → EBK (so the existing parsers read it) ──
def test_simple_matrix_to_ebk_round_trips_through_the_real_parsers():
    g = service.simple_matrix_to_ebk
    # a mapping (map kind): square → covectors, parses to the same matrix
    st = service.parse_mapping_state(g("[[1 0 -4] [0 1 4]]", False))
    assert st is not None and st.mapping == ((1, 0, -4), (0, 1, 4))
    # a comma basis (vector kind): square + ᵀ → kets
    assert service.parse_comma_basis(g("[[-4 4 -1]]ᵀ", True)) == ((-4, 4, -1),)
    # a projection P (map kind, d×d)
    assert service.parse_projection(g("[[1 1 0][0 0 0][0 1/4 1]]", False)) is not None
    # an embedding G (vector kind, d=3 r=2)
    assert service.parse_embedding(g("[[1 0 0] [0 0 1/4]]ᵀ", True), 3, 2) is not None
    # a bare prescaler diagonal (map kind, d=3)
    assert service.parse_prescaler_diagonal(g("[[1 0 0] [0 1.585 0] [0 0 2.322]]", False), 3) == (1.0, 1.585, 2.322)
    # a cents map (the parser strips brackets, so either reconstruction reads)
    assert service.parse_cents_map(g("[1201.699 697.564]", False)) == (1201.699, 697.564)


def test_simple_matrix_to_ebk_inverts_the_forward_transform():
    # forward then inverse (with the known variance) recovers an EBK string the forward maps back
    f, g = service.ebk_to_simple_matrix, service.simple_matrix_to_ebk
    for ebk, vector_based in [("[⟨1 0 -4] ⟨0 1 4]}", False), ("[[-4 4 -1⟩ [7 0 -3⟩]", True),
                              ("⟨1200 1902]", False), ("[-4 4 -1⟩", True)]:
        simple = f(ebk)
        assert f(g(simple, vector_based)) == simple  # the round-trip is stable under the forward map


# ── settings wiring ──────────────────────────────────────────────────────────────────────────
def test_ebk_toggle_is_registered_on_by_default_from_chapter_two():
    assert app_settings.DEFAULTS["ebk"] is True            # as-shipped: EBK on
    assert "ebk" in app_settings.IMPLEMENTED               # a live toggle, not greyed
    assert app_settings.CHAPTER["ebk"] == 2                # revealed by the default slider (ch4 ≥ 2)
    assert app_settings.reveal_chapter("ebk") == 2
    # it sits in the general group, just above units (the user's placement)
    general = [k for k, *_ in dict(app_settings.SHOW_GROUPS)["general"]]
    assert general.index("ebk") == general.index("units") - 1


# ── the gridded marks: square frame + ᵀ off, EBK brackets on ──────────────────────────────────
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


def test_ebk_on_keeps_angle_and_curly_marks_no_transpose():
    layout = _build(True)
    kinds = _mark_kinds(layout)
    assert {"ebkbrace", "ebkangle"} & kinds  # EBK feet present
    assert "ebkbot" not in kinds             # no square bottom
    assert "transpose" not in kinds          # no ᵀ marks
    assert {"⟨", "{"} & _bracket_glyphs(layout)  # angle/curly side brackets present


def test_ebk_off_squares_every_mark_and_tags_the_vector_kind():
    layout = _build(False)
    kinds = _mark_kinds(layout)
    assert "ebkbot" in kinds                              # the square bottom replaces the feet
    assert not ({"ebkbrace", "ebkangle"} & kinds)         # no EBK feet remain
    assert "transpose" in kinds                           # the vector matrices carry ᵀ
    assert _bracket_glyphs(layout) <= {"[", "]"}          # every side bracket is square
    assert all(c.text == "ᵀ" for c in layout.cells if c.kind == "transpose")


def test_ebk_off_transforms_the_plain_text_strings():
    def ptext(layout, rk, ck):
        return next((c.text for c in layout.cells if c.id == f"ptext:{rk}:{ck}"), None)
    on = _build(True, plain_text_values=True)
    off = _build(False, plain_text_values=True)
    # the mapping reads its EBK string on, the plain matrix off (map kind — no ᵀ)
    assert ptext(on, "mapping", "primes") == "[⟨1 0 -4] ⟨0 1 4]}"
    assert ptext(off, "mapping", "primes") == "[[1 0 -4] [0 1 4]]"
    # the target interval vectors are the vector kind — a ᵀ off
    assert ptext(on, "vectors", "targets").startswith("[[")
    assert ptext(off, "vectors", "targets").endswith("]ᵀ")
    assert "⟨" not in ptext(off, "vectors", "targets") and "⟩" not in ptext(off, "vectors", "targets")
