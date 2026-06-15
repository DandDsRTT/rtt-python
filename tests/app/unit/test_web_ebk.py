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
    # it's a show/example checkbox row (a notation MODE, not a per-tile dummy-tile layer), in the
    # "specific tiles & controls" group just above its "units" (domain_units) row — the user's placement
    specific = [k for k, *_ in dict(app_settings.SHOW_GROUPS)["specific tiles & controls"]]
    assert specific.index("ebk") == specific.index("domain_units") - 1
    general = [k for k, *_ in dict(app_settings.SHOW_GROUPS)["general"]]
    assert "ebk" not in general                            # NOT a dummy-tile part


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
    assert "transpose" not in kinds          # no ᵀ marks
    assert {"⟨", "{"} & _bracket_glyphs(layout)  # angle/curly side brackets present


def test_ebk_off_is_a_single_square_bracket_per_matrix_no_nesting():
    layout = _build(False)
    kinds = _mark_kinds(layout)
    # a plain matrix has NO EBK framing marks at all — no top bars, no braces, no angle feet
    assert not ({"ebktop", "ebkbrace", "ebkangle"} & kinds)
    assert _bracket_glyphs(layout) <= {"[", "]"}          # every bracket is square
    # the mapping (a covector stack) collapses to ONE full-height [ ] pair — no per-row brackets
    bracket_ids = {c.id for c in layout.cells if c.kind == "bracket"}
    assert {"bracket:primes:l", "bracket:primes:r"} <= bracket_ids
    assert not any(i.startswith("bracket:map:") for i in bracket_ids)  # the per-row ⟨…] are gone
    # the vector kind still carries a ᵀ; the map kind (the mapping) does not
    assert "transpose" in kinds
    assert all(c.text == "ᵀ" for c in layout.cells if c.kind == "transpose")
    assert not any(c.id == "transpose:primes" for c in layout.cells)  # mapping = map kind, no ᵀ


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


# ── an OPEN list tile keeps its outer EBK even when empty ──────────────────────────────────────
def _empty_target_layout(ebk: bool):
    """The meantone grid with the plain-text + weighting layers and an EXPLICIT empty target
    list (k = 0) — the prescaling/complexity layers the prescaler product tiles live under,
    with nothing in the target column."""
    s = app_settings.defaults()
    s.update({"plain_text_values": True, "weighting": True, "alt_complexity": True, "ebk": ebk})
    return spreadsheet.build(service.from_temperament_data(_MEANTONE), settings=s,
                             tuning_scheme=service.resolve_tuning_scheme("TILT minimax-S"),
                             target_spec="TILT", target_override=())


def test_empty_open_list_tiles_keep_their_outer_ebk():
    """An OPEN list/matrix tile always wears its outer [ … ] wrap — even with zero columns. The
    prescaling target tile (𝐿T) once gated its bracket on the column count, so an empty target
    list dropped the [] entirely (the brackets vanished while the sibling vectors/mapping target
    tiles still showed []); this guards that whole family of parallel rows in both EBK modes."""
    for ebk in (True, False):
        layout = _empty_target_layout(ebk)
        ids = {c.id for c in layout.cells}
        # the empty target column is still open across the value rows, so every one of its list
        # tiles must show its outer [] — including the prescaling 𝐿T tile that regressed.
        for stem in ("vec:targets", "mapped", "prescaling:targets"):
            assert f"bracket:{stem}:l" in ids and f"bracket:{stem}:r" in ids, \
                f"ebk={ebk}: outer bracket missing for {stem} over an empty target list"
