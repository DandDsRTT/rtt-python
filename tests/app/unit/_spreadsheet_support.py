import pickle
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


@pytest.fixture(autouse=True, scope="module")
def _memoized_build():
    """Cache byte-identical spreadsheet.build calls for this module. Measured: ~465 of this
    file's ~857 builds repeat a prior (args, kwargs) exactly — ~34s of pure waste per run.
    Layout and its parts are frozen dataclasses and no test mutates a returned layout, so
    handing repeat calls the same object is behavior-preserving. In-file (not a tests/app
    conftest) deliberately: the render tests re-import rtt.* and must not see a stale patch."""
    real = spreadsheet.build
    cache: dict = {}

    def cached(*args, **kwargs):
        try:
            key = pickle.dumps((args, sorted(kwargs.items())), protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            return real(*args, **kwargs)
        if key not in cache:
            cache[key] = real(*args, **kwargs)
        return cache[key]

    spreadsheet.build = cached
    try:
        yield
    finally:
        spreadsheet.build = real


def _layout(mapping=((1, 1, 0), (0, 1, 4))):
    return spreadsheet.build(service.from_mapping(mapping))


def _drag_layout(mapping=((1, 1, 0), (0, 1, 4)), **kw):
    return spreadsheet.build(service.from_mapping(mapping),
                             {**settings.defaults(), "drag_to_combine": True}, **kw)


def _with(scheme=None, **overrides):
    s = settings.defaults()
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s, tuning_scheme=scheme)


def _projection_build(held_basis_ratios=(), **overrides):
    s = settings.defaults()
    s["projection"] = True
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_basis_ratios=held_basis_ratios)


def _with_interest(interest, collapsed=None):
    return spreadsheet.build(
        service.from_mapping(((1, 1, 0), (0, 1, 4))), collapsed=collapsed, interest=interest
    )


def _title_edges(layout):
    return [(c.id.split("header:", 1)[1],
             c.x + c.width / 2 - spreadsheet_text._title_w(c.text) / 2,
             c.x + c.width / 2 + spreadsheet_text._title_w(c.text) / 2)
            for c in sorted((c for c in layout.cells if c.kind == "columnheader"), key=lambda c: c.x)]


def _assert_freeze_partition(layout):
    fx, fy = layout.freeze_x, layout.freeze_y
    for cell_box in layout.cells:
        if cell_box.kind in {"columnheader", "columntoggle"}:
            assert cell_box.y + cell_box.height <= fy
        elif cell_box.kind in {"rowlabel", "rowtoggle"}:
            assert cell_box.x + cell_box.width <= fx
        elif cell_box.kind == "alltoggle":
            assert cell_box.y + cell_box.height <= fy and cell_box.x + cell_box.width <= fx
        elif cell_box.kind.endswith(("plus", "minus")) or cell_box.kind == "columngrip":
            assert cell_box.x < fx or cell_box.y < fy
        else:
            assert cell_box.x >= fx and cell_box.y >= fy
    for bl in layout.blocks:
        if bl.tint == "" and not bl.boxed:
            assert bl.x >= fx and bl.y >= fy


def _all_on():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return s


def _maximized_superspace_builder():
    s = settings.defaults()
    for k, v in list(s.items()):
        if isinstance(v, bool):
            s[k] = True
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    return spreadsheet._GridBuilder(state, s, tuning_scheme="minimax-ES",
                                    held_vectors=((1, 0, 0), (0, 0, 1)), interest=((-1, 1, 0),))


def _tokens(pairs):
    return [token for token, _ in pairs]


def _held_state():
    return service.from_mapping(((1, 1, 0), (0, 1, 4)))


def _reorder_volatile(cell_id):
    return cell_id.startswith(("chart:", "plain_text:", "tuning:", "retune:", "rangechart:"))


def _in_targets(cell_id):
    return (cell_id.startswith(("target:", "cell:mapped:", "damage:target:"))
            or cell_id.startswith(("tuning:target:", "just:target:", "retune:target:")))


def _foldable(layout):
    return {c.id.split("toggle:", 1)[1] for c in layout.cells
            if c.kind in ("rowtoggle", "columntoggle")}


_EBK_OPEN, _EBK_CLOSE = "[⟨{", "]⟩}"


def _ebk_text_convention(text):
    """The bracket convention a plain-text EBK band declares, as
    ``(structure, outer_open, outer_close, inner_open, inner_close)`` — structure ∈
    ``stack`` (covector stack), ``list`` (vector list / kets), ``row`` (single line), ``none``."""
    i = min((text.find(ch) for ch in _EBK_OPEN if ch in text), default=-1)
    if i == -1:
        return ("none", "", "", "", "")
    s = text[i:]
    groups, depth, start = [], 0, 0
    for j, c in enumerate(s):
        if c in _EBK_OPEN:
            if depth == 0:
                start = j
            depth += 1
        elif c in _EBK_CLOSE:
            depth -= 1
            if depth == 0:
                groups.append(s[start:j + 1])
    multi = len(groups) > 1
    g = groups[0]
    inner = g[1:-1].strip()
    if inner and inner[0] in _EBK_OPEN:
        io, depth, ic = inner[0], 0, ""
        for c in inner:
            depth += c in _EBK_OPEN
            depth -= c in _EBK_CLOSE
            if depth == 0 and c in _EBK_CLOSE:
                ic = c
                break
        structure = "list" if io == "[" else "stack"
        return (structure, "", "", io, ic) if multi else (structure, g[0], g[-1], io, ic)
    if multi:
        return ("list", "", "", "[", g[-1])
    return ("row", g[0], g[-1], "", "")


def _ebk_grid_convention(b, layout, row_key, column_key):
    """The bracket convention the GRID draws around a tile's cells, reconstructed from its frame
    bands (matrix_frame's ebktop/ebkbrace/ebkangle), per-column ket marks and bracket glyphs.
    Cell-id shape disambiguates: a per-column mark / per-row stacked bracket ends in ``:<int>``,
    a spanning matrix_frame band or an outer list wrap does not."""
    cx, cw = b.geometry.column_x[column_key], b.geometry.column_width[column_key]

    def in_tile(c):
        if not (cx - 2 <= c.x + c.width / 2 <= cx + cw + 2):
            return False
        ccy = c.y + c.height / 2
        return min(b.geometry.rows, key=lambda k: abs(b.geometry.rows[k].y + b.geometry.rows[k].height / 2 - ccy)) == row_key

    frame_top = col_marks = False
    brace = angle = False
    outer, perrow = [], []
    for c in layout.cells:
        if not in_tile(c):
            continue
        digit = c.id.rsplit(":", 1)[-1].isdigit()
        if c.id.startswith("ebktop:"):
            col_marks |= digit
            frame_top |= not digit
        elif c.id.startswith("ebkbrace:"):
            col_marks |= digit
            brace = True
        elif c.id.startswith("ebkangle:"):
            col_marks |= digit
            angle = True
        elif c.id.startswith("bracket:") and c.id.endswith(":l"):
            base = c.id[:-2]
            if base.rsplit(":", 1)[-1].isdigit():
                perrow.append(c.text)
            else:
                r = next((x for x in layout.cells if x.id == base + ":r"), None)
                outer.append((c.text, r.text if r else "]"))
    foot = "}" if brace else "⟩" if angle else ""
    if frame_top:
        io = sorted(set(perrow))[0] if perrow else "⟨"
        return ("stack", "[", foot, io, "]")
    if col_marks:
        if outer:
            oo, oc = sorted(outer)[0]
            return ("list", oo, oc, "[", foot)
        return ("list", "", "", "[", foot)
    if outer:
        oo, oc = sorted(outer)[0]
        return ("row", oo, oc, "", "")
    return ("none", "", "", "", "")


def _ebk_canonical(convention):
    """Fold the one harmless ambiguity away before comparing: a single ket (a no-wrap list of one
    interval, ``[…⟩`` / ``[…}``) reads as a bare ``row`` by the close char but IS a 1-item list."""
    structure, oo, oc, io, ic = convention
    if structure == "row" and oo == "[" and oc in "⟩}":
        return ("list", "", "", "[", oc)
    return convention


def _ebk_table_canonical(convention):
    """Reduce an EBK_CONVENTIONS row to the 5-tuple the band parser yields: drop the (text-only)
    separator, and fold a bracket-less ``row`` to ``none`` (a bare scalar list reads as ``none``)."""
    structure, oo, oc, io, ic, _sep = convention
    if structure == "row" and not oo and not oc:
        return ("none", "", "", "", "")
    return (structure, oo, oc, io, ic)


def _in_commas(cell_id):
    return cell_id.startswith(("comma:", "cell:comma:")) or cell_id.split(":")[0:2] in (
        ["tuning", "comma"], ["just", "comma"], ["retune", "comma"])


_INTEREST = ((-1, 1, 0), (-3, 2, 0), (1, -2, 1), (3, 0, -1))


def _with_held(held_vectors, pending_held=None):
    s = settings.defaults()
    s["optimization"], s["counts"] = True, True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_vectors=held_vectors, pending_held=pending_held)


def _target_count():
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    return len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, base.domain_basis))


def _held(scheme=None, **overrides):
    base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
    s = settings.defaults()
    s["optimization"] = True
    s.update(overrides)
    return {c.id: c for c in spreadsheet.build(
        base, s, tuning_scheme=scheme, held_vectors=[(-1, 1, 0)]).cells}


def _color_at(layout, x, y):
    return {b.tint for b in layout.blocks if b.tint in ("temperament", "tuning")
            and b.x <= x <= b.x + b.width and b.y <= y <= b.y + b.height}


def _mid(cells, cell_id):
    c = cells[cell_id]
    return c.x + c.width / 2, c.y + c.height / 2


def _colormap_layout():
    s = settings.defaults()
    s["tuning_colorization"] = True
    s["temperament_colorization"] = True
    s["optimization"] = True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))


def _spine_colormap():
    s = settings.defaults()
    s["tuning_colorization"] = s["temperament_colorization"] = True
    s["counts"] = s["domain_units"] = s["interval_ratios"] = True
    s["weighting"] = s["alt_complexity"] = s["optimization"] = s["generator_detempering"] = True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             tuning_scheme="TILT minimax-S",
                             interest=((-1, 1, 0),), held_vectors=((-1, 1, 0),))


_CANON_MEANTONE = ((1, 0, -4), (0, 1, 4))


def _canonical_cells(**overrides):
    s = settings.defaults()
    s.update(overrides)
    held = s.pop("_held_vectors", None)
    ratios = s.pop("_held_basis_ratios", None)
    kw = {}
    if held is not None:
        kw["held_vectors"] = held
    if ratios is not None:
        kw["held_basis_ratios"] = ratios
    return {c.id: c for c in spreadsheet.build(service.from_mapping(_CANON_MEANTONE), s, **kw).cells}


def _diff_layout(*cells):
    return Layout(width=0, height=0, lines=(), blocks=(), cells=tuple(cells), freeze_x=0, freeze_y=0)


def _diff_cell(cell_id, text, **kw):
    return CellBox(id=cell_id, x=0, y=0, width=10, height=10, kind="tuningvalue", text=text, **kw)


def _barbados_superspace(**overrides):
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    s.update(overrides)
    return spreadsheet.build(state, s)


def _barbados_superspace_identity(**overrides):
    return _barbados_superspace(identity_objects=True, **overrides)


def _barbados_projection(held_basis_ratios=("2", "13/5"), **overrides):
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s["nonstandard_domain"] = True
    s["projection"] = True
    s.update(overrides)
    return spreadsheet.build(state, s, held_basis_ratios=held_basis_ratios)


def _barbados_prescaling(approach="", nonstandard=True):
    state = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults() | {"nonstandard_domain": nonstandard, "weighting": True, "alt_complexity": True,
                               "symbols": True, "header_symbols": True, "captions": True, "equivalences": True,
                               "plain_text_values": True, "presets": True}
    return spreadsheet.build(state, s, tuning_scheme="TILT minimax-C", nonprime_approach=approach)


_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _barbados_state():
    return service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")


def _barbados_superspace_tuning():
    return service.superspace_tuning(_barbados_state(), service.DEFAULT_DOCUMENT_SCHEME)


def _nonstd_on(state):
    return settings.defaults() | {"nonstandard_domain": True}


def _projection_full(**overrides):
    s = settings.defaults()
    s["projection"] = True
    kwargs = {k: overrides.pop(k) for k in ("held_vectors", "interest") if k in overrides}
    s.update(overrides)
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                             held_basis_ratios=("2/1", "5/4"), **kwargs)


def _projection_superspace(**overrides):
    st = service.from_temperament_data("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
    s = settings.defaults()
    s.update(projection=True, nonstandard_domain=True)
    s.update(overrides)
    return spreadsheet.build(st, s, held_basis_ratios=("2/1", "3/1"))


def _assert_plain_text_cells_match(layout, pt):
    plain_text_cells = [c for c in layout.cells if c.id.startswith("plain_text:")]
    assert len(plain_text_cells) >= 8
    for c in plain_text_cells:
        _, row_key, column_key = c.id.split(":")
        assert c.text == pt[(row_key, column_key)], c.id
