"""Spreadsheet layout for the temperament/tuning grid (the mockup's default view).

Rows are the quantities the temperament exposes (quantities, mapping, tuning,
just tuning, retuning, damage); columns are the interval/generator sets they're
shown over (generators, domain primes, target intervals). Cells sit on shared
coordinate axes — every prime/target is a vertical line shared down its column,
every generator a horizontal line shared across the mapping rows — so the
matrices stay aligned and the reconciling renderer can animate rows/columns in
and out. Reuses the entity types in :mod:`rtt.web.layout`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from dataclasses import replace
from fractions import Fraction

from rtt.web import presets
from rtt.web import service
from rtt.web.layout import Block, CellBox, Layout, Line
from rtt.web.grid_tables import *  # noqa: F403  (semantic content tables, re-exported)
from rtt.web.grid_tables import _FACTOR_GROUP  # build() reads it; import * skips the underscore name
from rtt.web.settings import defaults as _default_settings

ROW_H = 30  # px per row / matrix-entry height
COL_W = 30  # px per value column; == ROW_H so matrix cells are squares that tile
# the column (a shared-border grid, per the mockup); cents stack int-over-frac to fit
GAP = 20  # px between row/column groups (the visible gap between two grey tiles is GAP - 2*PAD)
PAD = 4  # px a block extends around its cells
WASH_PAD = GAP / 2  # px a colorization wash extends around its cells — wide enough that
# adjacent washed tiles' rects meet across the gap, so the colour reads as one
# continuous band behind the grey tiles (which overhang only by the smaller PAD)
LABEL_W = 106  # row-label gutter width (wide enough for the "complexity pre-" pretransforming title)
HEADER_H = 36  # column-header height — two text lines tall, so a multi-word title
# stacks centered onto a second line (via explicit "\n" breaks in col_header, e.g.
# "domain" / "primes"); single-word titles centre as one line
STRIP = 16  # thickness a collapsed row/column shrinks to (label/toggle only)
TOGGLE = 12  # side of a fold [x]/[+] control; fits the gutter-to-content gap
BTN = TOGGLE  # a domain +/− control matches the fold toggle it now sits beside on the fan
GRIP_BAND = 16  # extra fan-out room reserved below the ± for the column reorder-grips (the ⠿ ride
# this band along the gridlines, between the − above and the first tile below)
TOGGLE_INSET = 3  # small grey margin hugging a tile's top-left corner toggle (off the edges and content)
CAPTION_FONT = 9  # px font size of the quantity-name caption (matches the mockup —
# ~0.2 of the cell height; the CSS .rtt-caption must use the same size)
CAPTION_LINE = 10  # px per wrapped caption line (font size + leading); == .rtt-caption line-height
CAPTION_CHAR_W = 0.52  # serif glyph width as a fraction of the font size: a conservative
# (slightly wide) estimate for the greedy caption wrap, so the reservation never falls
# short of the browser's render. Its inverse floors a column wide enough to keep its
# captions within MAX_CAPTION_LINES rather than scaling the font or spilling.
MAX_CAPTION_LINES = 2  # a name wraps to at most this many lines; a longer one widens its tile
PRESET_H = 30  # height of a preset chooser dropdown — aligned with the gridded value
# row (ROW_H), so dropdowns sit at the same height as the value cells beside them
# The box-𝐋 diminuator slot width, hard-coded so the primes column can be widened up front to fit
# it (also reused for the target-controls all-interval check, the same checkbox-over-caption shape).
LBOX_DIM_W = 80     # the diminuator slot (checkbox square + "replace diminuator" caption)
CBOX_DROP_W = 170   # the predefined-complexities dropdown (inverted display names "lp (log-product)" …)
CBOX_SLOT_W = 60    # the q / dual(q) symbol/caption slots (the value cell is COL_W centred within)
CBOX_NODROP_W = CBOX_SLOT_W + 8 + CBOX_SLOT_W  # box 𝒄 sans the predefined-complexities preset: just q | dual(q)
CBOX_W = CBOX_DROP_W + 8 + CBOX_NODROP_W  # the box-𝒄 controls' total footprint (+ the dropdown leading the row)
OPTION_BOX_PX = 16   # the one shared size for every small option square: every q-checkbox box (the
#                      settings panel, the box-𝐋 diminuator, the target-controls all-interval check)
#                      and the tuning-ranges monotone/tradeoff radio boxes. app.py pins the q-checkbox
#                      CSS and the .rtt-rangebox to this, and the control-check CELL hugs the square.
PRESET_W = 124  # its width — fits "<choose temperament>" and caps the wide target tile
TARGET_PRESET_W = 144  # wider: the target chooser seats a 30px gridded limit square + the family select
PTEXT_MAX_FONT = 10  # px cap on the plain-text font; the app shrinks it per box so every value
# always fits on ONE line within its column (a long tuning row just gets smaller text)
PTEXT_H = 13  # px height of a one-line read-only plain-text value
PTEXT_EDIT_H = 16  # px height of an editable plain-text input box (a touch taller than a text line)
SYMBOL_H = 18  # height of the quantity-symbol glyph above the caption (when symbols shown)
MATLABEL_H = 13  # height of a per-column matrix label (𝐜₁, 𝒕₁, 𝐲₁, …) when symbols is on
MATLABEL_PAD = 4  # padding above + below the label within its band, so the label sits
# roughly equidistant from the tile's top edge and the matrix's top bracket
MATLABEL_W = 22  # width reserved left of an EBK ⟨ bracket for row labels (𝒎₁, 𝒎₂, …):
# the bold-italic lowercase form of the matrix's capital + a Unicode subscript. Reserved
# inside the matrix tile's content footprint, so the cells shift right by this much.
# NORM_SUB_OPEN / SUB_OPEN / SUBSCRIPT_L live in grid_tables (re-exported via import * above).
MATLABEL_W_SS = 64  # the primes column's wider row-label gutter when the superspace is shown: it
# also carries M_s→L's 𝒎ₛ→ₗᵢ labels (an arrow + two subscripts, far wider than the plain 𝒎ᵢ),
# so the gutter widens to fit them rather than overflowing the ⟨ bracket. (Centred, like 𝒎ᵢ.)
UNIT_H = 12  # height of the per-box "units: …" line (below the caption, when units shown)
CHART_H = 64  # height of a per-tile bar chart's plot area (when charts shown)
CHART_GAP = 5  # gap between a chart and the value cells below it
RANGE_CHART_H = 58  # height of the generator tuning-ranges I-beam chart (title + caps + min/max labels)
RANGE_MODE_H = 46  # height of the monotone/tradeoff range-mode selector — two rows of square
# indicators STACKED below the chart, with 5px top/bottom padding so neither row touches the
# enclosing box's edge (the bumped 16px boxes don't fit side by side anyway)
RANGE_GAP = 2  # gap between the ranges chart and its mode selector (and the values above the chart)
OPT_TITLE_H = 14  # height of the optimization box's title strip ("optimization")
OPT_PAD_T = 3  # inset above the title so it sits inside the box, not awkwardly on its top border
OPT_PAD_B = 4  # bottom margin below the captions (the box hugs the contents vertically too)
OPT_PAD_L = 8  # left margin: inset of the mean damage from the box's left edge
OPT_PAD_R = 8  # right margin: inset of the optimize button from the box's right edge
OPT_TITLE_GAP = 6  # bottom margin under the title, before the control row
OPT_COL_GAP = 8  # the standard gap between adjacent in-tile controls — sizes OPT_BOX_MIN_W
# (the clearance around the optimization box's centered power) and the box-𝐋 / q-dual / all-
# interval slots elsewhere
# The box spans the FULL width of the damage tile; its three controls DISTRIBUTE across it: the
# mean damage hugs the left edge, the optimize button the right edge, and the power 𝑝 sits centered
# in the gap between them, so the "optimization power" caption has clear room either side. The
# min-damage value and the ∞ field are ordinary COL_W gridded cells (contents centred); their
# symbols/captions centre under them. The captions stay on ONE line each.
OPT_BTN_W = 94   # optimize button — wide enough to seat "double-click to unlock" on one line beneath it
OPT_POW_CAP_W = 90  # the "optimization power" caption cell (one line, centred under the ∞ cell)
OPT_MEAN_DAMAGE_W = 64  # the mean damage's COLUMN: its value cell is COL_W centred within this, and its symbol
# and caption span it, so the WIDEST mean damage label — the min()-wrapped symbol min(⟪𝐝⟫ₚ) (~69px) /
# min(‖𝒓𝐿⁻¹‖dual(q)) — stays centred over the value without overflowing the box's left border or the
# "optimization power" caption to its right. Also the caption's wrap width: "power mean" fits on one
# line, while the wider "retuning magnitude" breaks at the space into the two lines cap_band reserves.
# the narrowest the box can be and still seat its spread-out controls with the power's caption clear
# of both neighbors — left pad | mean damage column | gap | power+caption | gap | button | right pad.
# A damage tile narrower than this floors its column up to fit (see _control_floor).
OPT_BOX_MIN_W = OPT_PAD_L + OPT_MEAN_DAMAGE_W + OPT_COL_GAP + OPT_POW_CAP_W + OPT_COL_GAP + OPT_BTN_W + OPT_PAD_R
# An in-tile control box: a dropdown / checkbox enclosed in a thin-bordered frame that SPANS its
# tile's full width (like the optimization / tuning-ranges boxes), with the control at its top-left
# and a small field LABEL beneath naming what it sets ("established tuning scheme"). BOX_OUTER is
# the vertical gap above/below the box; BOX_INNER insets the control + label off the box border;
# CTRL_LABEL_GAP sits between the label and the control. Box heights vary with the label, so a
# row reserves its tallest.
BOX_OUTER = 4  # vertical gap above/below a control box (it spans its tile's width — see control_box)
BOX_INNER = 5  # inset of the dropdown within the box (off the border)
CTRL_LABEL_GAP = 2  # padding below the label, to the box's bottom edge
# box 𝐓's footprint: the target chooser dropdown + the all-interval checkbox slot on one row,
# both inside one bordered box. Unlike the un-boxed LBOX_DIM_W/CBOX_W above, this includes the box
# padding (BOX_OUTER off the tile, BOX_INNER off the border, each side) so _control_floor can
# widen the target column enough that the box never overhangs the tile.
TBOX_W = 2 * BOX_OUTER + 2 * BOX_INNER + TARGET_PRESET_W + 8 + LBOX_DIM_W  # 8 = OPT_COL_GAP
# box 𝐋's footprint when the diminuator rides the predefined-pretransformers chooser box: the
# dropdown + the "replace diminuator" checkbox slot on one row (the box-𝐓 shape, with PRESET_W).
PBOX_W = 2 * BOX_OUTER + 2 * BOX_INNER + PRESET_W + 8 + LBOX_DIM_W  # 8 = OPT_COL_GAP
BOX_TITLE_H = 14  # px height of the optimization / tuning-ranges boxes' bold title strip
BOX_TITLE_GAP = 4  # gap below that title, before the box's content
APPROACH_RADIO_H = 64  # height of the nonstandard-domain-approach selector — three rows of square
# indicators STACKED (prime-based / nonprime-based / neutral), the tuning-ranges range-mode style
FRAME_H = 9  # height of a matrix's top-bracket framing band (the bar + down-ticks)
BRACE_H = 7  # depth of the bottom curly-brace band; kept shallow so the brace's
# short bounding dimension matches the value brackets' footprint (one EBK weight)
FRAME_GAP = 5  # gap between a framing band and the matrix cells, so they don't merge
BRACKET_W = 16  # gutter inside a value group for an EBK bracket (one side)
ROW_HANDLE_W = 14  # the per-mapping-row drag handle (drag a generator row onto another to add it)
ROW_HANDLE_GAP = 4  # the gap it keeps from the matrix's opening bracket
VAL_BRACKET_H = 16  # a single-row value bracket, kept short and centred in its
# ROW_H row so neighbouring rows' brackets keep a clear gap (the enclosing
# mapped-list [ ] is the tall exception and spans the whole matrix)
MARK_INSET = 8  # inset of a mapped column's top/bottom mark, so it clears the rules
SEP_W = 2  # width of a vertical rule between vector columns (the renderer draws it
# as thick as a square bracket's main bar; this is just the cell it centres in)
KET_INSET = 4  # inset (each side) of an editable interval-vector ket box within its COL_W
# slot, leaving a gap (2·KET_INSET) between adjacent boxes. The interest column (a loose
# collection, not a matrix) uses it so its boxes stand apart rather than abutting into a grid;
# the target list (a matrix WITH separator rules) uses it so the rule shows through the gap
# instead of being painted over by the opaque input box (per the mockup)
LINE_W = 2  # px thickness of the shared-axis gridlines: the renderer's .rtt-line border
# weight, and here the overlap by which a convergence bus reaches past its outer sub-lines
# so the rejoin corners stay solid (the cells sit centred on these rules)
MAP_BRACKETS = ("⟨", "]")  # ⟨ … ] for maps (covectors)
LIST_BRACKETS = ("[", "]")  # [ … ] for plain lists/matrices
GENMAP_BRACKETS = ("{", "]")  # { … ] for the generator tuning map (per the mockup)

# The semantic content tables (COUNTS / CAPTIONS / SYMBOLS / CELL_FACTORS / TILES / ...) -- pure
# data describing which quantities exist and their symbols, captions, units, mnemonics,
# colorization factors and tile sets -- now live in rtt.web.grid_tables, re-exported via the
# `import *` above so spreadsheet.<NAME> stays the public surface app.py / tooltips / tests read.


def _mathit(letter: str) -> str:
    """A single lowercase ASCII letter as its Unicode Mathematical Italic glyph
    (e.g. ``d`` -> ``𝑑``), so a count's variable reads as math italic like the
    Show panel's example. ``h`` is the one hole in the block — it maps to the
    Planck-constant glyph ``ℎ`` instead of an undefined code point."""
    return "ℎ" if letter == "h" else chr(0x1D44E + ord(letter) - ord("a"))


_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _sub(n: int) -> str:
    """``n`` as Unicode subscript digits (e.g. ``1`` -> ``₁``), for the domain-units
    coordinate labels (p₁/, /g₂) that index each prime/generator."""
    return str(n).translate(_SUBSCRIPTS)


def _subscript_coord(text: str, letter: str, replacement: str) -> str:
    """Replace each STANDALONE coordinate ``letter`` (``g`` / ``p`` / ``b``) in a unit string
    with ``replacement`` — its index-subscripted form. A letter flanked by other ASCII letters
    (inside an annotation family name like ``sopfr`` or ``copfr``) is left alone, so a unit such
    as ``(sopfr-C)/p`` subscripts only its trailing prime coordinate, not the ``p`` in ``sopfr``."""
    return re.sub(rf"(?<![A-Za-z]){letter}(?![A-Za-z])", replacement, text)


def _count_sym(sym: str) -> str:
    """A counts-row symbol's rendered math glyph: a bare ASCII letter via :func:`_mathit`
    (𝑟, 𝑑, 𝑛, 𝑘, ℎ), or a two-character ``"<letter>L"`` token that math-italicizes the
    letter and appends the Unicode subscript ₗ (U+2097) — for the superspace rank 𝑟ₗ and
    dimensionality 𝑑ₗ. The COUNTS / SUPERSPACE_COUNTS tables store the source token so
    the rendering lives in one place."""
    head = _mathit(sym[0])
    if len(sym) == 1:
        return head
    if sym[1:] == "L":
        return head + SUBSCRIPT_L  # a real subscript capital L (grid_tables.SUBSCRIPT_L)
    raise ValueError(f"unknown counts symbol: {sym!r}")


def _pretransform_label(text: str) -> str:
    """A rendered label with "prescal…" swapped to the "pretransform…" stem — the guide's term for
    the rectangular (size-factored) 𝑋, which shears rather than scales, so "prescaler" is a misnomer.
    Applied to every prescaling label (caption, row title, preset) while the size factor is on.
    "prescaled"/"prescaling" are swapped before "prescaler" (which also fixes the plural prescalers).
    "prescaling" → "pretransforming" stays parallel to the un-swapped "complexity prescaling" row
    title; the row title then hard-wraps the long word (".. pre-" / "transforming") rather than shrink."""
    for old, new in (("prescaled", "pretransformed"), ("prescaling", "pretransforming"),
                     ("prescaler", "pretransformer")):
        text = text.replace(old, new)
    return text


def _prescaler_col_labels(letter: str, show_equiv: bool, all_interval: bool, show_superspace: bool = False) -> dict:
    """Per-column header labels for the prescaling- and complexity-row product tiles, using
    ``letter`` for the prescaler glyph — 𝐿 when the prescaler IS the log-prime matrix, else
    the generic 𝑋. build() rebuilds these each render so a tile's column headers stay in step
    with its big symbol (𝐿𝐝ᵢ under the 𝐿D tile, 𝑋𝐝ᵢ under the 𝑋D tile — never mixed). The
    complexity headers are the q-norm of the prescaled basis vectors, ‖prescaler·basisᵢ‖q, with
    the trailing q wrapped in NORM_SUB sentinels so the matlabel renderer italic-subscripts it.

    The TARGETS complexity column is the named complexity list 𝒄, so its header is the named
    symbol cₙ, gaining that norm as its EQUIVALENCE tail (cₙ = ‖𝐿𝐭ₙ‖q) when the equivalences
    layer is on — like the tile big-symbols. All-interval (Tₚ = I) replaces the per-target vector
    𝐭ₙ with the n-th prime 𝐞ₙ, i.e. the n-th column 𝐿[n] of the prescaler — so each target's norm
    is exactly the domain prime complexity map's per-column ‖𝐿[n]‖q (not the whole matrix's ‖𝐿‖q)."""
    def norm(inner):
        return lambda i: f"‖{inner(i)}‖{NORM_SUB_OPEN}q{NORM_SUB_CLOSE}"

    def complexity_target(i):
        symbol = f"c{_sub(i + 1)}"
        if not show_equiv:
            return symbol
        # all-interval Tₚ = I: target n IS prime n, so its complexity is the n-th column 𝐿[n] (a
        # vector), matching the domain prime complexity map — NOT the whole matrix 𝐿
        inner = f"{letter}[{i + 1}]" if all_interval else f"{letter}𝐭{_sub(i + 1)}"
        return f"{symbol} = ‖{inner}‖{NORM_SUB_OPEN}q{NORM_SUB_CLOSE}"

    labels = {
        # prescaling row — the prescaled vector lists prescaler·basis (the bare matrix is row-labeled)
        ("prescaling", "commas"): letter + "𝐜",
        ("prescaling", "targets"): letter + "𝐭",
        ("prescaling", "held"): letter + "𝐡",
        ("prescaling", "detempering"): letter + "𝐝",
        # complexity row — ‖prescaler·basisᵢ‖q per the mockup (targets carries the named cₙ symbol too)
        ("complexity", "primes"): norm(lambda i: f"{letter}[{i + 1}]"),
        ("complexity", "commas"): norm(lambda i: f"{letter}𝐜{_sub(i + 1)}"),
        ("complexity", "held"): norm(lambda i: f"{letter}𝐡{_sub(i + 1)}"),
        ("complexity", "detempering"): norm(lambda i: f"{letter}𝐝{_sub(i + 1)}"),
        ("complexity", "targets"): complexity_target,
    }
    if show_superspace:
        # the superspace shift: the 𝐿·B_Ls product (domain-primes column) is a matrix of prescaled
        # subspace-basis-element kets, so it takes COLUMN headers 𝐿𝐛ₗₛᵢ (one per domain element) like
        # B_L — NOT the bare prescaler's row headers.
        labels[("prescaling", "primes")] = letter + "𝐛" + SUBSCRIPT_L + "ₛ"
        # the "next row": the prime complexity map ‖𝐿[i]‖q moves into the ss-primes column, and the
        # domain-primes complexity becomes the subspace basis element map ‖𝐿𝐛ₗₛᵢ‖q (each domain
        # element, lifted through B_L then prescaled — the corrected get_complexity value).
        labels[("complexity", "ssprimes")] = norm(lambda i: f"{letter}[{i + 1}]")
        labels[("complexity", "primes")] = norm(lambda i: f"{letter}𝐛{SUBSCRIPT_L}ₛ{_sub(i + 1)}")
    return labels


def _log_operand(ratio: str) -> str:
    """The operand of a just interval's log₂, e.g. ``3/1`` -> ``3`` (a bare prime,
    matching the mockup's ``log₂3``) and ``3/2`` -> ``(3/2)`` (parenthesised)."""
    num, _, den = ratio.partition("/")
    return num if den == "1" else f"({num}/{den})"


def _math_expr(operand: str, value: float, show_value: bool) -> str:
    """A just value's exact closed form ``1200 · log₂{operand}`` — which *equals* the
    cents value, so the decimal stays in cents and is kept as a true ``= {cents}``.
    The two parts are newline-separated so the renderer stacks them (the ``=`` and
    the decimal on the second line), e.g. ``"1200 · log₂2\\n= 1200.00"``. With the
    value (quantities) off, only the expression shows."""
    expr = f"1200 · log₂{operand}"
    return f"{expr}\n= {service.cents(value)}" if show_value else expr


def _prescale_math_expr(coeff, prime_term: str, value: float, show_value: bool) -> str:
    """A prescaling cell's exact closed form ``{coeff} · {prime_term}`` — where
    ``prime_term`` is what the active prescaler puts on the diagonal (``log₂{prime}`` for
    log-prime, ``{prime}`` for the prime prescaler; identity has no non-trivial closed
    form and never reaches here). Octaves, not cents (the prescaler lives a level below
    the just sizes), so no ``1200 ·`` prefix and the ``= {value}`` second line uses the
    same :func:`service.prescale_text` formatter the bare cells use. Unit coefficients
    drop their ``1 ·`` prefix (``log₂3`` not ``1 · log₂3``), and ``-1`` keeps just the
    sign (``-log₂3``). With quantities off, only the expression shows."""
    if coeff == 1:
        expr = prime_term
    elif coeff == -1:
        expr = f"-{prime_term}"
    else:
        expr = f"{coeff} · {prime_term}"
    return f"{expr}\n= {service.prescale_text(value)}" if show_value else expr


def _format_power(power: float) -> str:
    """The optimization power as shown beside ``𝑝``: ``∞`` for a minimax scheme, else
    the bare integer (``2``, ``1``) — or the decimal for an unusual fractional power."""
    if power == float("inf"):
        return "∞"
    return str(int(power)) if power == int(power) else str(power)


def _power_mean(damages, power: float) -> float:
    """The optimization mean damage ⟨𝐝⟩ₚ — the Lp power-mean of the damage list the scheme
    minimizes: ``max`` for a minimax (∞) scheme, the RMS for miniRMS (2), the mean for
    miniaverage (1). The damage chart's horizontal indicator sits at this level."""
    ds = [abs(d) for d in damages]
    if not ds:
        return 0.0
    if power == float("inf"):
        return max(ds)
    return (sum(d ** power for d in ds) / len(ds)) ** (1 / power)


def _title_w(title: str) -> int:
    """Width of a collapsed column's title strip: wide enough for the widest line of its
    title at 13px bold, with a STRIP floor. A multi-word title carries explicit "\\n"
    breaks (col_header), so it stacks within a strip sized to its longest word-run rather
    than folding to an over-wide one-line ribbon."""
    widest = max(len(line) for line in title.splitlines())
    return max(STRIP, widest * 8 + 10)


def _fold_glyph(is_collapsed: bool) -> str:
    """The fold toggle's state token (app._FOLD_GLYPH maps it to an SVG chevron): a collapsed
    band offers to expand (out-chevrons), an open one to collapse (in-chevrons)."""
    return "unfold_more" if is_collapsed else "unfold_less"


def _foldable_ids(cells) -> set:
    """The row/column fold-ids present among ``cells`` ("row:tuning", "col:targets")
    — the bands the master expand/collapse-all toggle acts on. Tiles are omitted: a
    folded row or column already subsumes its tiles, so collapsing every band folds
    the whole grid. Derived from the emitted toggles so it can't drift from them."""
    return {c.id.split("toggle:", 1)[1] for c in cells
            if c.kind in ("rowtoggle", "coltoggle")}


def toggle_all_collapsed(layout, collapsed) -> set:
    """The next ``collapsed`` set when the master expand/collapse-all toggle fires:
    expand everything (clear the set) when every foldable band is already collapsed,
    otherwise collapse every row and column. Pure — the app stores the result and
    re-renders. Operates on the just-built ``layout`` so it tracks the visible grid."""
    foldable = _foldable_ids(layout.cells)
    if foldable and foldable <= collapsed:
        return set()
    return set(collapsed) | foldable


# The CellBox fields that carry VISIBLE CONTENT — what the user reads off the cell — as opposed to
# its geometry (x/y/w/h, which shift whenever a neighbour grows) or its structural identity
# (gen/prime/comma, fixed for a given id). Two cells with the same id and the same content signature
# display the same thing; a difference between them is a value change worth flagging.
_CONTENT_FIELDS = ("kind", "text", "values", "ranges", "indicator", "indicator_label",
                   "pending", "alert", "checked", "blank", "unit", "underlines")


def _cell_content(cell: CellBox) -> tuple:
    """A cell's visible content as a comparable tuple — every content-bearing field, none of its
    geometry. The diff key for :func:`changed_cell_ids`."""
    return tuple(getattr(cell, field) for field in _CONTENT_FIELDS)


def changed_cell_ids(old: Layout, new: Layout) -> frozenset:
    """The ids of VALUE cells whose displayed value differs between two layouts — the set the editor
    highlights while a cell is being edited, so the user previews which OTHER cells the edit will
    move before committing it. A cell counts as changed when it is new in ``new``, or its content
    signature (:func:`_cell_content`, geometry excluded) differs from ``old`` — a cell that only
    shifted position because a neighbour grew has not changed value, so it is left out. Cells
    dropped in ``new`` are omitted too: there is nothing on screen left to highlight.

    Only the value-bearing kinds (:data:`RINGABLE_KINDS`) ring: the scaffolding around the values —
    the EBK marks, the column separators, the per-column grips and +/- controls — is skipped, so a
    reshape that adds or reflows them doesn't flood the preview with cells that carry no value."""
    before = {c.id: _cell_content(c) for c in old.cells}
    return frozenset(c.id for c in new.cells
                     if c.kind in RINGABLE_KINDS
                     and (c.id not in before or before[c.id] != _cell_content(c)))


def removed_cell_ids(old: Layout, new: Layout) -> frozenset:
    """The ids of VALUE cells present in ``old`` but GONE from ``new`` — the column or row a
    structural − (or a re-solving +) deletes. The counterpart to :func:`changed_cell_ids`, which
    rings the cells whose value MOVES and so omits anything not in ``new``; this rings what
    DISAPPEARS. A removed cell is still on screen while the +/- is merely hovered (the click hasn't
    committed), so the preview can light it up to show exactly what the click takes away. Restricted
    to the value-bearing :data:`RINGABLE_KINDS`, so the scaffolding around a removed value — its
    brackets, separators, drag grips and ± controls — is not flagged."""
    after = {c.id for c in new.cells}
    return frozenset(c.id for c in old.cells
                     if c.kind in RINGABLE_KINDS and c.id not in after)


def assign_column_tokens(prev, keys):
    """Assign a stable id-token to each interval column, so a column keeps its cell ids across a
    render and the reconciler glides it to its new x (rather than re-filling a fixed-index cell).

    ``keys`` is a hashable identity per column — the interval's RATIO ("3/2"), which is the same
    interval across domains, NOT its vector (a domain ± re-dimensions the vector, so matching by
    vector would read every column as new). ``prev`` is the previous render's ``[(token, key), …]``
    (``None`` on the first build); the return is the new ``[(token, key), …]`` aligned to ``keys``. A
    REORDER, ADD, or REMOVE matches columns to the previous render by CONTENT — each surviving column
    finds its old token and carries it to its new slot — so a removal never slides the next interval
    into a freed slot's id (which would falsely read every later column as "changed" in the edit
    preview). Only an in-place EDIT — same column count, one value changed — matches by POSITION, so
    the focused cell keeps its id (reused, not rebuilt mid-keystroke) and a value already present
    elsewhere isn't mistaken for a move into it. Anything still unmatched gets a token greater than
    every token in play, so live columns never collide. With no previous render the columns number
    0,1,2,… in order."""
    keys = list(keys)
    prev = list(prev or [])
    tokens = [None] * len(keys)
    if len(keys) == len(prev) and sorted(keys) != sorted(k for _, k in prev):
        # an in-place EDIT (same column count, one value changed): match by POSITION, so each column
        # keeps the token of the slot it sits in — the focused cell is reused, not rebuilt
        # mid-keystroke, and typing a value that already appears elsewhere isn't taken for a move.
        for j in range(len(keys)):
            tokens[j] = prev[j][0]
    else:
        # a REORDER, ADD, or REMOVE (or first build): match by CONTENT, so each surviving column
        # carries its token to its new slot and glides, and a removed column's id simply vanishes
        # rather than shifting every later column's id down. Equal duplicates claim distinct previous
        # columns in order, keeping every id unique; genuinely new columns fall through to a fresh
        # token below.
        claimed = [False] * len(prev)
        for j, key in enumerate(keys):
            for pi, (tok, pkey) in enumerate(prev):
                if not claimed[pi] and pkey == key:
                    tokens[j], claimed[pi] = tok, True
                    break
    nxt = max([t for t in tokens if t is not None] + [tok for tok, _ in prev] + [-1]) + 1
    for j in range(len(keys)):  # fresh token, greater than any in play (no reuse → no collision)
        if tokens[j] is None:
            tokens[j], nxt = nxt, nxt + 1
    return list(zip(tokens, keys))


def pending_token(tokens):
    """The id-token for a list's draft (pending) column: one past every committed column's token, so
    it can't collide with a live column even after a removal leaves a gap. On a fresh list (tokens =
    indices) this is the column count, so a first draft cell keeps its historical ``…:count`` id."""
    return max(tokens, default=-1) + 1


def _wrap_chars(words: list[str], max_chars: int) -> int:
    """Greedy line count packing ``words`` into lines of at most ``max_chars`` chars
    (an over-long word breaks across lines itself). The character-budget core shared
    by :func:`_wrap_lines` and its inverse :func:`_min_width_for_lines`."""
    lines, cur = 1, 0
    for word in words:
        wlen = len(word)
        if cur and cur + 1 + wlen > max_chars:  # word won't fit on the current line
            lines, cur = lines + 1, 0
        if cur == 0 and wlen > max_chars:  # the word itself overflows one line
            lines += (wlen - 1) // max_chars
            cur = (wlen - 1) % max_chars + 1
        else:
            cur += (1 if cur else 0) + wlen
    return lines


def _chars_per_line(width: float, font: float = CAPTION_FONT) -> int:
    return max(1, int((width - 4) / (font * CAPTION_CHAR_W)))  # -4: a little padding


def _wrap_lines(text: str, width: float, font: float = CAPTION_FONT) -> int:
    """How many lines ``text`` wraps to in a ``width``-px box at ``font`` px, so the
    tile can reserve the height to hold it. A greedy word wrap with a conservative
    serif char-width estimate. Shared by the name captions and the plain-text boxes."""
    return _wrap_chars(text.split(), _chars_per_line(width, font))


def _min_width_for_lines(text: str, max_lines: int, font: float = CAPTION_FONT) -> int:
    """Smallest box width (px) at which ``text`` wraps to at most ``max_lines`` lines —
    the inverse of :func:`_wrap_lines` in the same char-width model. Floors a column
    wide enough that its captions stay within two lines, widening the tile rather than
    scaling the font or letting a long name spill."""
    words = text.split()
    for chars in range(1, len(text) + 1):  # smallest per-line char budget that fits
        if _wrap_chars(words, chars) <= max_lines:
            return int(chars * font * CAPTION_CHAR_W + 4) + 1  # invert _chars_per_line (round up)
    return int(len(text) * font * CAPTION_CHAR_W + 4) + 1


def _bus_span(positions):
    """The (start, length) of a convergence bus across fanned sub-lines at ``positions``.
    It reaches half a line-width past the outer sub-lines so the rejoin corners stay solid
    at LINE_W; when the sub-lines coincide (a collapsed column or a single element) it
    degenerates to a zero-length point so the merged axis reads as one straight rule."""
    ext = LINE_W if positions[-1] != positions[0] else 0
    return positions[0] - ext / 2, (positions[-1] - positions[0]) + ext


@dataclass(frozen=True)
class _ShowFlags:
    """The resolved Show-panel view settings: each toggle plus the cross-toggle / collapsed gating
    that decides what actually renders. Resolved up front (the first build phase), independent of
    any geometry, so the column-width floors can reserve room for in-tile controls before the
    column-width loop runs. ``lbox`` / ``cbox`` gate the box-𝐋 / box-𝒄 in-tile choosers."""
    captions: bool
    mnemonics: bool
    equiv: bool
    presets: bool
    counts: bool
    ptext: bool
    charts: bool
    ranges: bool
    symbols: bool
    units: bool
    domain_units: bool
    temp: bool
    form_controls: bool
    tuning: bool
    optimization: bool
    weighting: bool
    alt_complexity: bool
    lbox: bool
    cbox: bool
    detempering: bool
    interest: bool
    gridded: bool
    quantities: bool
    domain_quantities: bool
    math: bool


def _resolve_show_flags(settings, collapsed) -> _ShowFlags:
    """The first build phase: derive the view flags + their gating from the Show settings. Pure —
    depends only on the settings dict and the collapsed set (no geometry)."""
    captions = settings["names"]  # the in-tile quantity captions; row/col titles always show
    temp = settings["temperament_boxes"]
    tuning = settings["tuning_boxes"]
    # optimization / weighting are sub-controls of tuning boxes: they annotate / open the tuning
    # region, so they only apply while that region (and its target column) shows. alt. complexity
    # is a sub-control of weighting: it adds the box-𝐋 "replace diminuator" checkbox.
    optimization = tuning and settings["optimization"]
    weighting = tuning and settings["weighting"]
    alt_complexity = weighting and settings["alt_complexity"]
    return _ShowFlags(
        captions=captions,
        mnemonics=captions and settings["mnemonics"],  # underline a caption's symbol letter
        equiv=settings["equivalences"],  # extend the symbol line with the defining equation
        presets=settings["presets"],  # the per-quantity chooser dropdowns
        counts=settings["counts"],
        ptext=settings["plain_text_values"],  # the boxed EBK string under each tile
        charts=settings["charts"],  # per-tile bar charts above the value cells
        ranges=settings["tuning_ranges"],  # the generator tuning-ranges I-beam chart (in the gens box)
        symbols=settings["symbols"],  # the in-tile quantity symbols, stacked above the captions
        units=settings["units"],  # the in-tile "units: …" line, below each box's caption
        domain_units=settings["domain_units"],  # the units row (spine) + units column
        temp=temp,
        form_controls=settings["form_controls"],  # the canonical-mapping form row + <choose form> chooser
        tuning=tuning,
        optimization=optimization,
        weighting=weighting,
        alt_complexity=alt_complexity,
        # Whether each alt.-complexity in-tile chooser emits — evaluated up front (without col_x,
        # which the column-width loop computes later) so the column-width floor can widen the
        # primes / targets columns to fit the controls. box 𝒄 (the complexity chooser) shows with
        # WEIGHTING alone (the norm is core to weighting, not an alt.-complexity extra); only box 𝐋
        # (the prescaler controls) stays on alt_complexity.
        lbox=(alt_complexity and settings["temperament_boxes"]
              and "col:primes" not in collapsed and "row:prescaling" not in collapsed
              and "tile:prescaling:primes" not in collapsed),
        cbox=(weighting
              and "col:targets" not in collapsed and "row:complexity" not in collapsed
              and "tile:complexity:targets" not in collapsed),
        detempering=settings["generator_detempering"],  # the generator-detempering column (matrix D)
        interest=settings["interest"],  # the other-intervals-of-interest column (its own box toggle)
        # Value-display toggles. "gridded values" is the master switch: off filters every value a
        # tile holds (see GRIDDED_KINDS). "quantities" is gentler — it keeps boxes/EBK marks and
        # only blanks the body numbers (BLANKED_NUMBER_KINDS); "domain_quantities" governs the
        # quantities row and its spine column. "math" prefixes a tuning cent with its closed form.
        gridded=settings["gridded_values"],
        quantities=settings["quantities"],
        domain_quantities=settings["domain_quantities"],
        math=settings["math_expressions"],
    )


@dataclass(frozen=True)
class _PrescalerLabels:
    """The resolved complexity-prescaler glyph + labels (build's phase 2). The prescaler the
    DISPLAYED diagonal realises decides whether the product tiles and their complexity-norm column
    headers carry the concrete 𝐿 or the abstract 𝑋, and the bare tile's row labels / name
    equivalence follow suit. Resolved up front so the caption-width floor can size the (maybe
    longer, "= log-prime matrix") name before the column-width loop runs."""
    scheme_prescaler: object   # the scheme's nominal prescaler: "log-prime" / "prime" / "identity" / None
    realized: object           # the prescaler the DISPLAYED diagonal realises (None when a custom edit deviates)
    symbol: str                # the glyph products + headers use: 𝐿 when 𝑋 = 𝐿, else the abstract 𝑋
    equivalence: str           # the bare tile's symbol-line equivalence: " = 𝐿" / " = diag(𝒑)" / " = 𝐼" / ""
    prescaling_symbols: dict   # the prescaling tile's product symbols with "L" resolved to the live glyph
    col_labels: dict
    row_labels: dict
    effective_captions: dict   # CAPTIONS, the bare tile's name gaining "= log-prime matrix" when 𝑋 = 𝐿


def _resolve_prescaler_labels(state, tuning_scheme, custom_prescaler, show_equiv, show_superspace=False) -> _PrescalerLabels:
    """Resolve the prescaler glyph + labels. The prescaler 𝑋 "further appears" as 𝐿 in the product
    tiles and their complexity-norm column headers WHEN 𝑋 = 𝐿 — i.e. when the prescaler the displayed
    diagonal realises is the log-prime matrix. A prime/identity scheme, or a custom diagonal that
    genuinely deviates, leaves the generic 𝑋 everywhere. The bare prescaler tile is the DEFINITION
    locus: it keeps the abstract 𝑋 (rows 𝒙ᵢ), with the equivalence "= 𝐿" / "= diag(𝒑)" / "= 𝐼" (or
    nothing for a real deviation), and — when 𝑋 = 𝐿 — its NAME gains "= log-prime matrix". So a tile
    never mixes the two: the bare matrix is all 𝑋, every product and column header all 𝐿."""
    all_interval = service.is_all_interval(tuning_scheme)  # Tₚ = I drops the per-target 𝐭ₙ from the headers
    scheme_prescaler = service.prescaler_of(tuning_scheme)  # the scheme's nominal prescaler
    # the prescaler the DISPLAYED diagonal realises — matched at display precision, so editing a
    # cell to its shown value and back recovers the named prescaler (and the 𝑋 = 𝐿 awareness)
    realized = service.displayed_prescaler_name(state.mapping, tuning_scheme, custom_prescaler)
    size_factor = service.complexity_size_factor(tuning_scheme)
    is_log_prime = realized == "log-prime"
    symbol = "𝐿" if is_log_prime else "𝑋"
    # the bare tile's SYMBOL equivalence names the realised prescaler concretely; a real deviation
    # has no closed form, so none. The size factor COMPOSES the size-sensitizing matrix 𝑍 with the base
    # prescaler (the guide's 𝑋 = 𝑍𝐿, 𝑍diag(𝒑), or just 𝑍 since 𝑍𝐼 vaporizes), so the bare tile names THAT.
    if size_factor and realized:
        base = "" if realized == "identity" else PRESCALER_LETTER[realized]  # 𝑍𝐼 = 𝑍, so identity drops its base
        # a single-glyph base juxtaposes cleanly (𝑍𝐿, the guide's form); a multi-letter one (diag(𝒑))
        # needs a · so "𝑍diag" doesn't read as one word
        sep = "·" if base.startswith("diag") else ""
        equivalence = f" = 𝑍{sep}{base}"
    elif realized:
        equivalence = f" = {PRESCALER_LETTER[realized]}"
    else:
        equivalence = ""
    # the bare matrix keeps the literal abstract 𝑋 as its big SYMBOL; only the products' "L"
    # placeholder resolves to the live glyph ("LC"/"LD"/… → 𝐿C/… or 𝑋C/…), matching their headers
    prescaling_symbols = {(r, c): symbol + s[1:] for (r, c), s in SYMBOLS.items()
                          if r == "prescaling" and s.startswith("L")}
    effective_captions = dict(CAPTIONS)
    # the bare prescaler column: normally the domain primes, but once the superspace appears the bare
    # 𝐿 has moved one column LEFT into ss-primes (over the TRUE primes), and the domain-primes tile is
    # now the product 𝐿·B_Ls — the prescaled subspace basis elements. Redirect the row labels, the
    # product symbol, the "= log-prime matrix" name, and the captions accordingly.
    bare_col = "ssprimes" if show_superspace else "primes"
    # the bare matrix's per-row labels take the lowercase of the realised glyph — 𝒍ᵢ when 𝑋 = 𝐿,
    # else the generic 𝒙ᵢ. ONLY the bare prescaler carries them: under the superspace the 𝐿·B_Ls
    # product (domain-primes column) is a matrix of kets (its columns the domain elements), so it
    # gets COLUMN headers (𝐿𝐛ₗₛᵢ, see _prescaler_col_labels) like B_L, not the bare prescaler's rows.
    row_labels = dict(ROW_LABEL_LETTERS)
    row_labels.pop(("prescaling", "primes"), None)
    row_labels.pop(("prescaling", "ssprimes"), None)
    row_labels[("prescaling", bare_col)] = "𝒍" if is_log_prime else "𝒙"
    if show_superspace:
        prescaling_symbols[("prescaling", "primes")] = f"{symbol}B{SUBSCRIPT_L}ₛ"
        effective_captions[("prescaling", "primes")] = "complexity prescaled subspace basis elements"
        effective_captions[("complexity", "primes")] = "subspace basis element complexity map"
    # the NAME spells the equivalence out in words (guide ch8 table names). The plain diagonal is just
    # its base matrix ("= log-prime matrix"); the size factor composes the size-sensitizing matrix with
    # that base ("= size-sensitizing matrix × log-prime matrix" / "× diagonal matrix of primes", or just
    # "= size-sensitizing matrix" when the base is the identity). A real deviation (realized None) gets
    # none. It lands on the bare-prescaler column — ss-primes once the superspace shows.
    _BASE_MATRIX_NAME = {"log-prime": "log-prime matrix", "prime": "diagonal matrix of primes", "identity": "identity matrix"}
    if show_equiv and realized:
        if size_factor:
            base = _BASE_MATRIX_NAME[realized]
            effective_captions[("prescaling", bare_col)] += (
                " = size-sensitizing matrix" + ("" if realized == "identity" else f" × {base}"))
        elif is_log_prime:
            effective_captions[("prescaling", bare_col)] += f" = {_BASE_MATRIX_NAME['log-prime']}"
    if size_factor:  # the rectangular 𝑋 is a "pretransformer", not a "prescaler" (guide terminology)
        effective_captions = {k: _pretransform_label(v) for k, v in effective_captions.items()}
    return _PrescalerLabels(
        scheme_prescaler=scheme_prescaler, realized=realized, symbol=symbol, equivalence=equivalence,
        prescaling_symbols=prescaling_symbols,
        col_labels={**COL_LABEL_LETTERS, **_prescaler_col_labels(symbol, show_equiv, all_interval, show_superspace)},
        row_labels=row_labels, effective_captions=effective_captions,
    )


class _GridBuilder:
    def __init__(self, state, settings=None, collapsed=None,
                 tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
                 pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
                 custom_prescaler=None, optimize_locked=False, tuning_optimized=False,
                 pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, projection_held=None, displayed_projection_name=None):
        self.prev_ids = prev_ids or {}
        self.state = state
        self.settings = settings
        self.collapsed = collapsed
        self.tuning_scheme = tuning_scheme
        self.target_spec = target_spec
        self.interest = interest
        self.range_mode = range_mode
        self.pending_comma = pending_comma
        self.pending_interest = pending_interest
        self.pending_held = pending_held
        self.pending_target = pending_target
        self.pending_element = pending_element  # chapter-9 domain basis element draft (str / None)
        self.held_vectors = held_vectors
        self.generator_tuning = generator_tuning
        self.target_override = target_override
        self.custom_prescaler = custom_prescaler
        self.optimize_locked = optimize_locked
        self.tuning_optimized = tuning_optimized
        self.nonprime_approach = nonprime_approach
        self.superspace_generator_tuning = superspace_generator_tuning  # manual 𝒈L (rL) in prime-based
        # the named scheme the DISPLAYED tuning realises (editor.displayed_tuning_scheme_name), or
        # None off the named list — threaded in so the tuning chooser's single-option lock matches
        # app._build_preset's on-list check. None (a bare spreadsheet.build) keeps the chooser a
        # dropdown; the live page always passes it (see Editor.layout).
        self.displayed_tuning_name = displayed_tuning_name
        # the established projection / embedding chosen in that chooser: the rational unchanged
        # intervals (ratio strings) driving P = GM and G, or None for the auto-picked default
        # (editor.projection_held); and the NAME the chooser shows (editor.displayed_projection_
        # scheme_name), threaded in to match app._build_preset's on-list check like the tuning name.
        self.projection_held = projection_held
        self.displayed_projection_name = displayed_projection_name

        if self.settings is None:
            self.settings = _default_settings()
        if self.tuning_scheme is None:
            # the as-shipped scheme is target-based and unity-weighted, matching the editor's default
            self.tuning_scheme = service.DEFAULT_DOCUMENT_SCHEME
        if self.target_spec is None:
            self.target_spec = service.DEFAULT_TARGET_SPEC
        self.collapsed = self.collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
        # Phase 1 — resolve the Show-panel view flags + their gating (see _resolve_show_flags above),
        # then unpack into the local names the rest of build() reads.
        _f = _resolve_show_flags(self.settings, self.collapsed)
        self.show_captions = _f.captions
        self.show_mnemonics = _f.mnemonics
        self.show_equiv = _f.equiv
        self.show_presets = _f.presets
        show_counts = _f.counts
        self.show_ptext = _f.ptext
        show_charts = _f.charts
        show_ranges = _f.ranges
        self.show_symbols = _f.symbols
        self.show_units = _f.units
        show_domain_units = _f.domain_units
        show_temp = _f.temp
        self.show_form_controls = _f.form_controls
        show_tuning = _f.tuning
        self.show_optimization = _f.optimization
        self.show_weighting = _f.weighting
        # alt. complexity, resolved (it needs weighting). Gates the advanced tuning knobs' EDITABILITY:
        # the norm power 𝑞 and the optimization power 𝑝 are editable only with it on, read-only
        # (powerdisplay) otherwise (matching the all-interval lock; the editor keeps the scheme basic,
        # minimax-lp, whenever it's off). It also gates the whole pretransformer square's editability.
        self.show_alt_complexity = _f.alt_complexity
        # The prescaling + complexity machinery only matters when the damage weight derives from
        # complexity (complexity-/simplicity-weight). Under the default unity-weight the weight is 1
        # regardless, so those rows and their box-𝐋/𝒄 controls don't render — a visibility condition
        # on the slope, NOT a fold default (INITIAL_COLLAPSED stays empty; see no-collapsed-defaults).
        self._complexity_shown = (self.show_weighting
                                  and service.damage_weight_slope(self.tuning_scheme) != "unityWeight")
        # the damage/weight/complexity unit annotations track the live scheme (guide ch.10
        # "Annotated units"): the weight is (U)/(C)/(S)/(EC)/(ES), damage the ¢-prefixed form,
        # the complexity its own slope-free (C)/(EC). Built once here, consumed by tile_unit and
        # the weighting rows' units-column spine.
        self.weight_unit = f"({service.weight_annotation(self.tuning_scheme)})"
        self.complexity_unit = f"({service.complexity_annotation(self.tuning_scheme)})"
        self.damage_unit = f"¢{self.weight_unit}"  # weighted cents — the ¢-prefixed weight unit
        self._lbox_show = _f.lbox and self._complexity_shown
        self._cbox_show = _f.cbox and self._complexity_shown
        self.show_detempering = _f.detempering
        show_interest = _f.interest
        self.gridded = _f.gridded
        self.show_quantities = _f.quantities
        show_domain_quantities = _f.domain_quantities
        self.show_math = _f.math
        # Row labels and column headers (and their gutters) are always present.
        label_w = LABEL_W
        header_h = HEADER_H
        self.d = self.state.d
        self.r = len(self.state.mapping)
        # the d domain elements: the standard primes, or a nonstandard subgroup's (possibly
        # nonprime) basis. Every interval set is read over this basis (so 13/5 keeps its 13).
        self.elements = self.state.domain_basis
        # Chapter 9 superspace dimensions. dL = the simplest prime-only basis containing the
        # domain — the number of superspace primes — so dL ≥ d, with equality for a standard
        # (or reordered) prime limit. rL = r + (dL − d) since nullity is preserved by the
        # embedding (each extra prime adds an extra generator). Used to size the new
        # superspace columns (rL wide / dL wide) and rows (rL / dL tall) and to count the
        # spine basis index — kept on self even when the toggle is off so a future feature
        # can reach them without re-resolving the service call.
        self.dL = service.superspace_dimension(self.elements)
        self.rL = service.superspace_rank(self.state)
        # the dL superspace primes (e.g. (2, 3, 5, 13) for BARBADOS) — the basis the
        # ss_vectors row's spine column labels its rows with, and the columns of M_L
        self.superspace_primes = service.superspace_primes(self.elements)
        # the chapter-9 "nonstandard domain" Show toggle. Checking it makes the domain basis
        # editable (the cells become "elementcell" rather than read-only "prime") and renames the
        # column to "domain basis elements" — but on its own it does NOT reveal the superspace
        # columns/rows; that waits on the basis actually becoming nonstandard (see show_superspace).
        self.show_nonstandard_domain = self.settings.get("nonstandard_domain", False)
        # the superspace columns/rows render only when the toggle is on, the basis carries a
        # NONPRIME element (e.g. 13/5 in 2.3.13/5), AND the approach is prime-based or neutral.
        # A nonstandard subgroup that's still all primes (2.5.7) or a mere reordering has nothing
        # to embed, so the superspace would just clone the domain. The domain_has_nonprimes half
        # matches the damage-tile approach radio's own gate (app._approach_visible), so the
        # columns/rows and that radio appear together — while the toggle half preserves the
        # additive-only contract (toggle off ⇒ no superspace trace). The nonprime-based approach
        # honors the basis as-is and never converts to the prime superspace, so the whole block
        # (columns AND rows) collapses there; the radio itself stays (it's gated only on the
        # nonprime element) so it can be switched back. Switch to neutral/prime-based to restore.
        self.show_superspace = (
            self.show_nonstandard_domain
            and service.domain_has_nonprimes(self.elements)
            and self.nonprime_approach != "nonprime-based"
        )
        # the GENERATOR shift is narrower than the prescaler/complexity shift: complexity is measured
        # in the superspace for BOTH neutral and prime-based (both prime-factor), but the optimization
        # itself only HAPPENS in the superspace for prime-based — it solves the rL superspace
        # generators 𝒈L and projects them back to the r domain generators 𝒈. So only prime-based moves
        # the generator-map editing/controls to 𝒈L (ssgens): there 𝒈L is the live map and 𝒈 is its
        # read-only projection. Neutral optimizes in the domain, so 𝒈 stays live there.
        self.show_superspace_generators = self.show_superspace and self.nonprime_approach == "prime-based"
        # Phase 2 — resolve the complexity-prescaler glyph + labels (see _resolve_prescaler_labels).
        # Resolved here, AFTER show_superspace, because the superspace shift renames/relocates the
        # bare-prescaler captions, symbols and row labels (the bare 𝐿 moves into the ss-primes column,
        # the domain-primes tile becomes 𝐿·B_Ls).
        _p = _resolve_prescaler_labels(self.state, self.tuning_scheme, self.custom_prescaler,
                                       self.show_equiv, self.show_superspace)
        self._scheme_prescaler = _p.scheme_prescaler
        self._realized_prescaler = _p.realized  # the displayed prescaler's name, or None off the named list
        self.prescaler_symbol = _p.symbol
        self.prescaler_equivalence = _p.equivalence
        self.prescaling_symbols = _p.prescaling_symbols
        self.col_labels = _p.col_labels
        self.row_labels = _p.row_labels
        self.effective_captions = _p.effective_captions
        # identity objects — the trivial self-maps that equal 𝐼 (mapping over its own
        # generators, domain primes as vectors over themselves, 𝑀·D, and in the superspace
        # block M_L over its own generators and the JI mapping M_jL = I). They're deferred to
        # the not-yet-built identity_objects feature, so this defaults off and stays out of
        # settings.IMPLEMENTED; tests pass it through build's settings directly. Until then
        # the two superspace identity tiles gate on it the way the standard-domain identity
        # tiles are simply absent from the tile list.
        self.show_identity_objects = self.settings.get("identity_objects", False)
        # the domain coordinate label that indexes each element in unit strings — 𝑝 (prime)
        # over a standard prime limit, 𝒃 (basis element) over a nonstandard subgroup, since
        # a nonprime basis element isn't a prime. Switches every domain-side unit at once: the
        # interval-vectors row's 𝒃ᵢ/, the basis-elements column's /𝒃ᵢ, and each gridded cell's
        # per-coordinate denominator (𝑔/𝒃ᵢ, ¢/𝒃ᵢ, oct/𝒃ᵢ, (C)/𝒃ᵢ).
        # whether the domain is a standard prime limit (a prime prefix) rather than a nonstandard
        # subgroup whose basis isn't a prime sequence. Switches the domain coordinate label (𝑝 vs 𝒃)
        # and the column title, AND gates the domain + (expand walks to the next standard prime, so
        # it doesn't apply to a subgroup — the + is withheld, never shown inert).
        self.standard_domain = service.is_standard_domain(self.elements)
        # the coordinate label is p (prime) unless the basis carries a NONPRIME element, in which
        # case it's b (basis element). Keyed on nonprimes, NOT standard_domain: a nonstandard but
        # all-prime subgroup like 2.3.7 still reads p (its elements are genuine primes).
        self.domain_label = "b" if service.domain_has_nonprimes(self.elements) else "p"
        # whether the domain − applies — the shared predicate the editor's shrink guard uses, so the
        # button only shows when a click would actually drop the top prime (not on a nonstandard
        # subgroup, nor when the smaller temperament would be improper). Gates both the quantities-row
        # − and its interval-vectors-row twin, so neither ever appears inert.
        self.domain_can_shrink = service.can_shrink_domain(self.state)
        self.gens = service.generators(self.state.mapping, self.elements)
        # the displayed target list: a typed explicit target list overrides the TILT/OLD spec, but
        # all-interval auto-replaces it with Tₚ = I (the domain basis, every interval's prime-based
        # proxy). Resolved in the service so the grid and the plain text can't diverge; every target
        # consumer below derives from this one tuple — including the prime-based "when all-interval"
        # forms (𝐿, ‖𝐿‖, 𝐿⁻¹, 𝑟, |𝑟|𝑋⁻¹) every target-column row then takes.
        self.targets = service.displayed_targets(self.state, self.tuning_scheme, self.target_spec, target_override)
        self.all_interval = service.is_all_interval(self.tuning_scheme)  # T auto-becomes Tₚ = I (no ± then)
        # the auto Tₚ = I list isn't user-curated, so all-interval drops every target editing
        # affordance at once — the vector cells, the quantities-row ratio twin, the plain text,
        # and the ± — rendering the list as a read-only computed value (like the detempering D)
        self.targets_editable = not self.all_interval
        self.k = len(self.targets)
        # a target being added rides as a pending draft column (blank red cells + a "?" ratio)
        # until its vector is filled in, like the comma / interest / held draft. Suppressed when
        # the list isn't editable (all-interval's auto Tₚ = I set is not user-curated, no + draft).
        self.pending_target = list(self.pending_target) if (self.pending_target is not None and self.targets_editable) else None
        self.k_shown = self.k + (1 if self.pending_target is not None else 0)
        self.mapped = service.mapped_intervals(self.state.mapping, self.targets, self.elements)
        self.canon_mapping = service.canonical_mapping(self.state.mapping)  # M defactored + HNF (the form box)
        self.rc = len(self.canon_mapping)  # canonical rank (== r for a valid temperament)
        self.form_M = service.form_matrix(self.state.mapping)  # F: the generator form matrix (r×r), F·M = canonical
        self.target_vectors = service.target_interval_vectors(self.targets, self.d, self.elements)  # k vectors, each d-tall
        # held intervals: the optimization box's held-just constraints — user-edited vectors in the
        # held column (like the intervals of interest). The tuning holds each exactly just, so
        # they are folded into service.tuning below. Present only with the optimization sub-control.
        self.held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in held_vectors) if self.show_optimization else ()
        self.nh = len(self.held)
        # a held interval being added rides as a pending draft column (blank red cells + a "?"
        # ratio) until its vector is filled in, like the comma / interest draft. Gated on the
        # optimization sub-control, since the held column only exists there.
        self.pending_held = list(self.pending_held) if (self.pending_held is not None and self.show_optimization) else None
        self.nh_shown = self.nh + (1 if self.pending_held is not None else 0)
        self.held_ratios = service.comma_ratios(self.held, self.elements)  # vector -> "num/den" (the shared renderer)
        # a frozen manual generator tuning (optimize lock off) drives the maps directly; otherwise
        # the scheme's optimum (holding the held intervals just). A stale tuning whose generator
        # count no longer matches the mapping (a rank change) falls back to the optimum.
        if generator_tuning is not None and len(generator_tuning) == len(self.state.mapping):
            self.tun = service.tuning_from_generators(self.state.mapping, generator_tuning, self.elements)
        else:
            # a typed target-list override retunes the optimum (minimize over THOSE intervals), so
            # the grid's auto-optimized tuning tracks the displayed targets, not just the named set
            self.tun = service.tuning(self.state.mapping, self.tuning_scheme, self.elements, self.nonprime_approach, held=self.held_ratios,
                                 prescaler_override=self.custom_prescaler, targets=target_override)
        self.target_weights = service.interval_weights(self.state.mapping, self.tuning_scheme, self.targets,
                                                  prescaler_override=self.custom_prescaler,
                                                  domain_basis=self.elements)  # the damage row's 𝒘
        # the target damage list is the scheme-weighted 𝐝 = |𝐞|·W (the same weights shown in the
        # weight row and minimized by the optimizer), so it — and the optimization tile's mean damage
        # over it — tracks the unity/complexity/simplicity slope rather than staying plain |error|.
        self.target_sizes = service.interval_sizes(self.tun, self.targets, self.elements, weights=self.target_weights)
        self.held_mapped = service.mapped_intervals(self.state.mapping, self.held_ratios, self.elements)  # M·held (gen coords)
        self.held_sizes = service.interval_sizes(self.tun, self.held_ratios, self.elements)  # tempered/just/error sizes
        # a held interval stays "held" only while the current tuning tunes it exactly just. Once the
        # user changes something (the mapping, a generator, the held set) so the tuning no longer
        # does, its retuning error reads nonzero — and the whole interval renders red (CellBox.alert),
        # clearing back to black when the tuning is re-optimized to hold it. Decided at DISPLAY
        # precision (the shown cents), so typing the displayed optimum — which reads 0.000 though it
        # carries sub-milli-cent float noise — counts as held, not a false red.
        self.held_unheld = tuple(float(service.cents(e)) != 0.0 for e in self.held_sizes.errors)
        # a full-rank temperament (n=0) carries only the trivial zero comma; show nothing, not a "1/1"
        self.comma_ratios = service.comma_ratios(self.state.comma_basis, self.elements) if self.state.n else ()
        self.nc = len(self.comma_ratios)  # the real commas (those that define the temperament)
        self.mapped_commas = service.mapped_commas(self.state.mapping, self.state.comma_basis)  # M·commas = 0 (vanish)
        self.comma_sizes = service.interval_sizes(self.tun, self.comma_ratios, self.elements)  # comma sizes (tempered ~0)
        # the unchanged-interval basis U = nullspace(P − I): the projection P's eigenvalue-1
        # eigenvectors (the intervals held exactly just). When projection is on, U consolidates
        # with the comma basis C into one "unrotated vector basis" column V = C|U — the comma
        # sub-columns then the unchanged ones — and its eigenvalue list λ (0 per comma, 1 per
        # unchanged) becomes the scaling-factors row above the interval-vectors row. U is
        # derived/read-only (only C stays editable), so the V view also freezes the comma
        # +/−/drag and the pending draft (a structural edit would change the rank, hence U). Gated
        # on there being a comma to merge with (n > 0). Its mapped / sized / complexity twins are
        # precomputed so the V value tiles read one geometry, exactly as the comma column's do.
        self.unchanged_basis = (service.unchanged_interval_basis(self.state)
                                if (show_temp and show_tuning and self.settings["projection"] and self.state.n) else None)
        self.show_unchanged = self.unchanged_basis is not None
        self.nu = len(self.unchanged_basis) if self.show_unchanged else 0
        if self.show_unchanged:
            self.unchanged_ratios = service.comma_ratios(self.unchanged_basis, self.elements)
            self.unchanged_mapped = service.mapped_commas(self.state.mapping, self.unchanged_basis)  # M·U (r × u; held, ≠ 0)
            self.unchanged_sizes = service.interval_sizes(self.tun, self.unchanged_ratios, self.elements)
            self.unchanged_complexities = service.interval_complexities(
                self.state.mapping, self.tuning_scheme, self.unchanged_ratios,
                prescaler_override=self.custom_prescaler, domain_basis=self.elements)
        else:
            self.unchanged_ratios = self.unchanged_mapped = self.unchanged_complexities = ()
            self.unchanged_sizes = service.IntervalSizes((), (), (), ())
        # a comma being added is shown as a pending draft column to the right of the real
        # ones: blank red cells and a "?" quantity until it is a valid independent comma
        # (then it commits and the mapping re-ranks). It is not a real comma, so it does
        # not enter the nullity, the mapping, or the sizes — only the displayed column count.
        # (Suppressed under the consolidated V view, where comma structural edits are frozen.)
        self.pending = (list(pending_comma)
                        if (pending_comma is not None and not self.show_unchanged) else None)
        self.nc_shown = self.nc + (1 if self.pending is not None else 0)
        # the V column's shown sub-columns: the comma sub-columns (with any pending draft) then
        # the u unchanged sub-columns (0 off-projection). One geometry for the width, the gridline
        # fan, the EBK marks and every value tile that renders over the consolidated column.
        self.nv_shown = self.nc_shown + self.nu
        # under the consolidated view the interval-vectors header tile reads as the whole unrotated
        # vector basis V = C|U, not just the comma basis C (the symbol → V, the equiv → C|U are set
        # in the caption loop). Overriding the caption here also widens the column to seat the name.
        if self.show_unchanged:
            self.effective_captions[("vectors", "commas")] = "unrotated vector basis"
            # the V column's per-column labels keep the C|U identities the mockup draws: 𝐜ᵢ over the
            # comma sub-columns, 𝐮ᵢ over the unchanged ones (the scaling row's λᵢ spans all of V).
            self.col_labels[("vectors", "commas")] = (
                lambda i: f"𝐜{_sub(i + 1)}" if i < self.nc else f"𝐮{_sub(i - self.nc + 1)}")
        # other intervals of interest: a user-built set held as vectors and edited like
        # the comma basis (editable vector cells). Normalize each vector to the current d
        # (pad/trim) so a domain change can't misalign them, then derive the ratios the
        # quantities row shows and the mapping/sizes the lower rows show. It carries no
        # damage row and contributes tiles only when populated, so an empty column adds no
        # panels or fold toggles — just its header and a single straight axis rule.
        self.interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in self.interest)
        self.mi = len(self.interest)
        # an interval of interest being added rides as a pending draft column to the right of the
        # committed ones (blank red cells + a "?" ratio), exactly like the pending comma, until its
        # vector is filled in (then it commits). The draft is not a real interval, so it stays out
        # of the ratios/sizes/complexity below — only the displayed column count grows.
        self.pending_interest = list(self.pending_interest) if self.pending_interest is not None else None
        self.mi_shown = self.mi + (1 if self.pending_interest is not None else 0)
        # the chapter-9 domain basis element draft: with the nonstandard-domain box on, a typed-in
        # new basis element rides as a red ?/? column to the right of the d real elements (exactly
        # like the pending comma), until a valid rational fills it (then it commits, added held
        # just). It is not a real element — no mapping/tuning/count — so the matrix rows still
        # iterate self.d and leave its column empty; only the displayed domain width grows by one.
        self.element_draft = self.show_nonstandard_domain and self.pending_element is not None
        self.d_shown = self.d + (1 if self.element_draft else 0)
        self.interest_ratios = service.comma_ratios(self.interest, self.elements)  # vector -> "num/den" (shared renderer)
        self.interest_mapped = service.mapped_intervals(self.state.mapping, self.interest_ratios, self.elements)
        self.interest_sizes = service.interval_sizes(self.tun, self.interest_ratios, self.elements)
        # a stable id-token per column of each reorderable interval list, matched against the
        # previous render (prev_ids): a within-list reorder keeps a column's token, so all its cells
        # keep their ids and the reconciler slides them to the new x. Fresh (no prev) numbers each
        # list by index, so every cell id is unchanged until the first reorder. Commas are excluded
        # (their column order is canonicalized by the dual — a reorder is unobservable). The identity
        # key is the interval's RATIO, not its vector: a domain ± re-dimensions the vector (a 5-limit
        # target's 3-tall vector becomes 2-tall), so matching by vector read every shared target as a
        # whole-list delete; the ratio is the same interval across domains, so a shared column keeps
        # its token and only the genuinely-dropped intervals (the lost prime's) read as removed.
        self._col_ids = {
            name: assign_column_tokens(self.prev_ids.get(name), ratios)
            for name, ratios in (("targets", self.targets),
                                 ("held", self.held_ratios), ("interest", self.interest_ratios))
        }
        # the complexity row norms each interval's prescaled vector (𝒄): a covector over the
        # domain elements (each element's complexity, log₂ of it for the default log-prime
        # norm), a list over the comma / target / interest interval sets.
        self.complexities = {
            # over the DOMAIN basis (like every sibling call below) so a nonprime element's complexity
            # prime-factors correctly — 13/5 reads log₂(13·5), not log₂5 (dropping the out-of-limit 13).
            # This is the subspace basis element complexity map once the superspace shows.
            "primes": service.interval_complexities(self.state.mapping, self.tuning_scheme, tuple(service.element_ratio(e) for e in self.elements),
                                                    prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "commas": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.comma_ratios,
                                                    prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "targets": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.targets,
                                                     prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "interest": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.interest_ratios,
                                                      prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "held": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.held_ratios,
                                                  prescaler_override=self.custom_prescaler, domain_basis=self.elements),
            "detempering": service.interval_complexities(self.state.mapping, self.tuning_scheme, self.gens,
                                                         prescaler_override=self.custom_prescaler, domain_basis=self.elements),
        }
        # the prescaler 𝑋: a d×d diagonal matrix over the primes (diag = each prime's pre-norm
        # weight, the values the complexity map norms). log-prime by default: diag(log₂ prime).
        # A custom_prescaler override (the bare prescaler tile's editable diagonal) short-circuits
        # the scheme's computed diagonal here, threading the user's typed values into every
        # prescaling/complexity/weight/tuning calculation downstream.
        self.prescaler = service.complexity_prescaler(self.state.mapping, self.tuning_scheme, override=self.custom_prescaler)
        # a non-diagonal pretransformer (the editable square, off-diagonal entries typed in) is a
        # d×d matrix rather than a per-prime diagonal; its rows/products multiply, and — like the
        # size factor — its inverse weight has no per-prime diagonal closed form (see
        # all_interval_simplicity_weight below, which drops the weight tile's concrete diag(𝐿)⁻¹
        # equivalence for the generic 𝒘 = 𝒄⁻¹ + per-column cₙ⁻¹ headers).
        self.prescaler_is_matrix = isinstance(self.prescaler[0], (tuple, list))
        # a pending draft alone (no committed intervals) declares just the two tiles that host
        # it — the editable vector ket and its "?" ratio header; the derived rows (sizes,
        # complexity, …) have no value until it commits, so they stay undeclared (no empty
        # bracketed panels). With at least one committed interval the full set declares, and the
        # draft rides as a blank slot within those tiles, exactly as the pending comma does.
        interest_tiles = ()
        if self.mi_shown:
            interest_tiles += (
                ("block:vec:interest", "vectors", "interest"),
                ("block:interest", "quantities", "interest"),
            )
        if self.mi:
            interest_tiles += (
                ("block:imapped", "mapping", "interest"),
                ("block:tuning:interest", "tuning", "interest"),
                ("block:just:interest", "just", "interest"),
                ("block:retune:interest", "retune", "interest"),
                ("block:urow:interest", "units", "interest"),  # the units row's /1 over the interest column
                ("block:prescaling:interest", "prescaling", "interest"),
                ("block:complexity:interest", "complexity", "interest"),
            )
        # the held interval column's tiles: a user-editable interval list, like the intervals of
        # interest. Empty by default. A pending draft alone declares just the two tiles that host
        # it (the ket + its "?" ratio); the derived rows declare once an interval commits — the
        # same split the interest column uses, so a draft never leaves empty bracketed panels.
        held_tiles = ()
        if self.nh_shown:
            held_tiles += (
                ("block:held", "quantities", "held"),
                ("block:vec:held", "vectors", "held"),
            )
        if self.nh:
            held_tiles += (
                ("block:hmapped", "mapping", "held"),       # M·held in generator coords
                ("block:tuning:held", "tuning", "held"),    # tempered sizes (= just, since held)
                ("block:just:held", "just", "held"),        # just sizes
                ("block:retune:held", "retune", "held"),    # errors (≈ 0, since held just)
                ("block:urow:held", "units", "held"),       # the units row's /1 over the held column
                ("block:prescaling:held", "prescaling", "held"),
                ("block:complexity:held", "complexity", "held"),
            )
        # The optimization box's other mockup column — unchanged intervals (count u) — is
        # deferred to the projection feature: the unchanged interval basis is U = nullspace(P − I),
        # the projection P's eigenvalue-1 eigenvectors (en.xen.wiki/w/Projection#The_unchanged-interval_basis),
        # so it can't be built until projection lands. Until then the box ships with the held
        # column above plus the power line below (held intervals are a subset of the unchanged ones).
        # the generator-detempering column holds the matrix D — one JI interval (a vector) per
        # generator that tempers to it (the mapping's right-inverse), framed like the comma
        # basis / target list. An independent box toggle, riding between domain primes and commas.
        self.detempering_vectors = service.generator_detempering(self.state.mapping) if self.show_detempering else ()
        # the detempering intervals' sizes under the tuning: the tempered sizes ARE the generator
        # tuning map (𝒕D = 𝒈, since each D tempers to its generator), with just and retuning sizes
        # like any interval set. gens is the detempering as ratio strings (service.generators = D).
        self.detempering_sizes = service.interval_sizes(self.tun, self.gens, self.elements) if self.show_detempering else None
        detempering_tiles = (
            ("block:detempering", "quantities", "detempering"),
            ("block:vec:detempering", "vectors", "detempering"),
            ("block:tuning:detempering", "tuning", "detempering"),
            ("block:just:detempering", "just", "detempering"),
            ("block:retune:detempering", "retune", "detempering"),
            ("block:prescaling:detempering", "prescaling", "detempering"),
            ("block:complexity:detempering", "complexity", "detempering"),
            ("block:urow:detempering", "units", "detempering"),
        ) if self.show_detempering else ()
        # the rational tempering projection P = GM and its generator embedding G (the projection
        # sub-control of tuning boxes): P is a d×d operator over the domain primes, G a d×r matrix
        # whose columns are the held tuning's generators as fractional vectors. Both are built from
        # the SAME unchanged-interval basis — the established projection the chooser selected
        # (self.projection_held: ratio strings), or the auto-picked default when None — so P = GM.
        # service returns None for any case it can't form (degenerate hold, etc.), so the box simply
        # drops rather than rendering. Computed only when both the tuning boxes and the projection
        # toggle are on. Resolved here, ahead of the row-band list, so the band can gate on it.
        show_projection = show_tuning and self.settings["projection"]
        self.projection_matrix = (service.tuning_projection(self.state, held=self.projection_held)
                                  if show_projection else None)
        self.embedding_matrix = (service.tuning_embedding(self.state, held=self.projection_held)
                                 if show_projection else None)
        # the optimization controls (power 𝑝 etc.) nest at the bottom of the damage×targets
        # tile (see opt_box below), not in a tile/row of their own
        self.tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
                 + SUPERSPACE_COUNTS_TILES
                 + TILES + UNITS_TILES + SUPERSPACE_TILES
                 + interest_tiles + held_tiles + detempering_tiles)
        # The authoritative set of real (row, column) tiles. tile_open() consults it, so a
        # tile's existence lives in ONE place: drop its entry here (via TILES etc.) and it
        # vanishes everywhere — panels, toggles, cells, brackets and marks — with no chance
        # for a stray hardcoded column list to keep drawing a tile that no longer exists.
        self.declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in self.tiles}
        if self.embedding_matrix is None:
            # the generator embedding G shares P's held basis, so it forms exactly when P does;
            # drop its tile whenever P couldn't be built (projection off, or a degenerate basis)
            # so the gens-column box never shows empty (the P band is already gone in that case).
            self.declared_tiles -= {("projection", "gens")}
        if service.is_all_interval(self.tuning_scheme):
            # all-interval (Tₚ = I): every target-column list that just re-expresses an existing column
            # collapses to a duplicate, so drop it — mapped 𝑀T → 𝑀, prescaled 𝐿T → 𝐿, and each size/error
            # list to its prime map (tempered 𝐚 → 𝒕, just 𝐨 → 𝒋, error 𝐞 → 𝒓). The kept target tiles are
            # the target list itself (Tₚ = I), the complexity ‖𝐿‖, and the weight/damage. Dropping a tile
            # here clears its cells, bracket, caption, panel and fold toggle (never a blank box).
            self.declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                               ("tuning", "targets"), ("just", "targets"), ("retune", "targets")}
        if not self.show_identity_objects:
            # the superspace identity objects — M_L over its own generators (ss_mapping × gens,
            # trivially 𝐼) and the JI mapping M_jL = I (ss_just_mapping × ssprimes) — are deferred
            # to the not-yet-built identity_objects feature, exactly like their standard-domain
            # counterparts (mapping × gens, vectors × primes, mapping × detempering), which simply
            # aren't in the tile list. Dropping them here clears their cells, brackets, captions,
            # symbols, panels and fold toggles. (ss_just_mapping's whole row band is gated off too,
            # above; ss_mapping's stays for the real M_L in its ssprimes column.)
            self.declared_tiles -= {("ss_mapping", "gens"), ("ss_just_mapping", "ssprimes"),
                                    ("ss_vectors", "ssprimes"), ("ss_mapping", "ssgens")}
        # the superspace held / interest tiles only exist to lift an actual held / interest list —
        # with none present (nh / mi == 0) they'd be empty boxes, so drop them (cells, panel,
        # caption, brackets and fold toggle all go with the tile).
        if not self.nh:
            self.declared_tiles -= {("ss_vectors", "held"), ("ss_mapping", "held")}
        if not self.mi:
            self.declared_tiles -= {("ss_vectors", "interest"), ("ss_mapping", "interest")}

        # Column bands left-to-right: (key, natural width, present, collapsible).
        # Each set-column belongs to a box toggle: generators, the domain primes and
        # the commas are the temperament's (shown with temperament_boxes), target-
        # intervals are the tuning's (shown with tuning_boxes), and the other-intervals-
        # of-interest column has its own (shown with interest) -- turning a box off
        # takes its whole column with it, including the other family's cells that ride
        # in it (e.g. the tuning maps over primes, or the mapped target interval list
        # over targets). A collapsed column folds to a strip sized to read its title, but never
        # wider than it was open — so collapsing a column only ever narrows it (see col_w below).
        # The domain/comma + controls ride just right of their blocks when open; each −
        # is a hover affordance on the removable highest-prime / last-comma column.
        # the domain column header reflects the BASIS itself: "domain basis elements" (the guide's
        # term) once any element is a nonprime, else "domain primes" — including for a nonstandard
        # but still all-prime subgroup like 2.3.7, whose elements ARE primes. (The "domain" prefix
        # deviates from the mockup, which dropped it.) Keyed on domain_has_nonprimes like the p/b
        # coordinate label and the superspace columns — independent of the nonstandard-domain box
        # (the box makes the cells editable; the title just tracks the actual basis). It is never a
        # bare "basis elements" and never "domain primes" over a basis that carries a nonprime.
        domain_title = ("domain basis\nelements"
                        if service.domain_has_nonprimes(self.elements)
                        else "domain\nprimes")
        self.col_header = {"quantities": "quantities", "units": "units", "gens": "generators",
                      "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                      "primes": domain_title, "detempering": "generator\ndetempering",
                      "commas": "commas",
                      "held": "held\nintervals", "targets": "target\nintervals",
                      "interest": "other intervals\nof interest"}
        # The leftmost quantities column is the spine: a header + fold toggle + a single
        # vertical rule, the column-axis dual of the quantities spine row. The units column
        # (the specific `domain_units` toggle) is a second spine column right after it,
        # carrying each row's coordinate-unit labels (pᵢ/, gᵢ/, ¢/). Each spine holds a single
        # COL_W-wide index per row (a basis square / generator ratio; a unit label) and so is
        # one COL_W wide — its longer header overhangs it (see the col_w hug-content rule above).
        # primes and targets reserve a BRACKET_W gutter on each side for EBK brackets;
        # the value cells are inset by BRACKET_W within the group. The primes column
        # additionally reserves a MATLABEL_W gutter on the left when symbols is on AND
        # the mapping row will render, so its row labels (𝒎₁, 𝒎₂, …) seat left of each
        # row's ⟨ bracket without overflowing the panel. An equal empty gutter is mirrored
        # on the RIGHT (see col_bands below) so the row labels don't shove the matrix
        # off-centre in its tile — the left label gutter is balanced by the empty right one.
        # widen the primes gutter when the superspace is shown — it also carries M_s→L's wide
        # 𝒎ₛ→ₗᵢ row labels (see MATLABEL_W_SS), which would otherwise overflow the ⟨ bracket
        self.matlabel_primes_w = ((MATLABEL_W_SS if self.show_superspace else MATLABEL_W)
                                  if (self.show_symbols and show_temp) else 0)
        # M_L / M_jL stack covectors in the ssprimes column with row labels (𝒎ʟᵢ), so it needs
        # the same MATLABEL_W gutter the primes column reserves — without it the labels collide
        # with each row's ⟨ bracket and first cell
        self.matlabel_ssprimes_w = MATLABEL_W if (self.show_symbols and self.show_superspace) else 0
        # the drag-to-combine row handles ride a gutter to the LEFT of the row labels (the 𝒎ᵢ
        # matlabels), so the primes column reserves room for them — present when the feature is on
        # and there are ≥ 2 generator rows to combine. Balanced by an equal empty right gutter (like
        # the matlabel gutter) so the matrix stays centred in its tile.
        self.row_handle_w = (ROW_HANDLE_W + ROW_HANDLE_GAP) if (
            self.settings.get("drag_to_combine") and show_temp and self.r > 1) else 0
        # The complexity size factor (the box-𝐋 "replace diminuator" trait, lp→lils): a nonzero
        # factor makes the complexity pretransformer 𝑋 rectangular — the guide's 𝑋 = 𝑍𝐿, the
        # diagonal log-prime matrix 𝐿 composed with a size-sensitizing matrix 𝑍 that appends one
        # extra row, the size-weighted sf·𝐿. The prescaling matrices (the bare 𝑋 and its 𝑋·basis
        # products) grow that one row; every other row is unchanged.
        self.size_factor = service.complexity_size_factor(self.tuning_scheme)
        self.size_rows = 1 if self.size_factor else 0
        # the prescaling matrix's row count: over a nonstandard domain with the superspace shown
        # (neutral / prime-based), complexity is measured in the prime superspace, so the bare 𝐿 and
        # every 𝐿·basis product lift to dL rows (the true primes), not the d (possibly nonprime)
        # domain elements. The size row, if any, still sits one below.
        self.prescale_rows = self.dL if self.show_superspace else self.d
        # All-interval, whenever the pretransformer isn't a plain per-prime diagonal: the per-prime
        # simplicity weight has no concrete diagonal closed form (the size factor / off-diagonal entries
        # don't ride into a diagonal). The weight still renders as a LIST — it just drops the concrete
        # diag(𝐿)⁻¹ tile equivalence for the generic 𝒘 = 𝒄⁻¹ (reciprocal complexity, exactly as the
        # complexity row drops diag(𝐿) for a bare 𝒄), spelling each entry out in per-column cₙ⁻¹
        # headers. In target-based mode the per-target weights still differ (the off-diagonal/size factor
        # already rode into them), so the list + chart stay too.
        self.all_interval_simplicity_weight = self.all_interval and (
            bool(self.size_factor) or self.prescaler_is_matrix)
        col_bands = (
            ("quantities", COL_W, show_domain_quantities, True),
            ("units", COL_W, show_domain_units, True),
            ("gens", 2 * BRACKET_W + self.r * COL_W, show_temp, True),
            # the chapter-9 superspace columns ride between gens and the domain primes — rL
            # cells (superspace generators) and dL cells (superspace primes), each in the
            # standard EBK-gutter footprint like the gens/primes columns they parallel
            ("ssgens", 2 * BRACKET_W + self.rL * COL_W, self.show_superspace, True),
            ("ssprimes", 2 * BRACKET_W + self.dL * COL_W + 2 * self.matlabel_ssprimes_w, self.show_superspace, True),
            ("primes", 2 * BRACKET_W + self.d_shown * COL_W + 2 * self.matlabel_primes_w + 2 * self.row_handle_w, show_temp, True),
            ("detempering", 2 * BRACKET_W + self.r * COL_W, self.show_detempering, True),
            ("commas", 2 * BRACKET_W + self.nv_shown * COL_W, show_temp, True),
            ("held", 2 * BRACKET_W + self.nh_shown * COL_W, self.show_optimization, True),
            ("targets", 2 * BRACKET_W + self.k_shown * COL_W, show_tuning, True),
            # The interest column's tiles hug this content width (32 + mi·COL_W) — no empty
            # padding. Its long two-line title needs more room, so the column's *footprint*
            # is floored at the title width (see the loop below) and the narrow content is
            # centred within it: the title centres over the whole column on its gridline, and
            # the tiles centre on that same gridline. The board height is independent of mi.
            ("interest", 2 * BRACKET_W + self.mi_shown * COL_W, show_interest, True),
        )
        # A fold-toggle node column sits between the row-label gutter and the content
        # (when names show); content starts past it with a clear gap so the tiles
        # never collide with the nodes. Row lines fan from the node's right edge so
        # their gaps match the columns'.
        self.node_x = label_w + GAP
        self.node_edge = self.node_x + TOGGLE  # the node's content-facing (right) edge
        content_x0 = self.node_x + TOGGLE + GAP

        # Row bands top-to-bottom: (key, natural height, present, collapsible, label), laid
        # out below by the same running-cursor rule as the columns. Defined here, ahead of
        # that layout, so each column's width can reserve room for its present rows' captions.
        row_bands = (
            ("counts", ROW_H, show_counts, True, "counts"),
            ("quantities", ROW_H, show_domain_quantities, True, "quantities"),
            ("units", ROW_H, show_domain_units, True, "units"),
            # the scaling factors λ = diag(λ) — the projection's eigenvalue list (0 per comma,
            # vanished; 1 per unchanged, held) — a one-row scalar list over the consolidated V
            # column, riding just above the interval-vectors row (the mockup). Present with the
            # projection toggle, exactly when V consolidates (show_unchanged).
            ("scaling_factors", ROW_H, self.show_unchanged, True, "scaling factors"),
            ("vectors", self.d * ROW_H, show_temp, True, "interval vectors"),
            ("canon", self.rc * ROW_H, self.show_form_controls, True, "canonical mapping"),
            ("mapping", self.r * ROW_H, show_temp, True, "mapping"),
            # the rational tempering projection P = GM, a d×d matrix over the domain primes —
            # d rows tall like the interval-vectors row, framed like the mapping. Placed between
            # the mapping and the tuning rows (the mockup). Present only when service could build
            # it (projection on, tuning boxes on); a None matrix drops the band entirely.
            ("projection", self.d * ROW_H, self.projection_matrix is not None, True, "projection"),
            # the chapter-9 superspace rows sit between mapping and tuning, the row
            # counterparts of the ssgens / ssprimes columns: ss_vectors holds the dL-tall
            # vector columns (B_L, target/comma vectors in the superspace); ss_mapping the
            # rL × dL matrix M_L; ss_just_mapping the dL × dL identity M_jL (each
            # superspace prime is its own basis element). All three gate on the same
            # nonstandard_domain toggle as the columns, so the bands collapse to nothing
            # whenever the toggle is off.
            ("ss_vectors", self.dL * ROW_H, self.show_superspace, True, "superspace\ninterval vectors"),
            ("ss_mapping", self.rL * ROW_H, self.show_superspace, True, "superspace\nmapping"),
            # the M_jL = I band exists ONLY to hold that identity object, so it gates on
            # identity_objects too (its sole tile is the deferred ss_just_mapping × ssprimes —
            # see declared_tiles below). The ss_mapping band stays: it also carries the real
            # rL × dL mapping M_L (ss_mapping × ssprimes), only its gens-column self-map drops.
            ("ss_just_mapping", self.dL * ROW_H,
             self.show_superspace and self.show_identity_objects, True, "superspace\nJI mapping"),
            ("tuning", ROW_H, show_tuning, True, "tuning"),
            ("just", ROW_H, show_tuning, True, "just tuning"),
            ("retune", ROW_H, show_tuning, True, "retuning"),
            ("prescaling", (self.prescale_rows + self.size_rows) * ROW_H, self._complexity_shown, True, "complexity prescaling"),
            ("complexity", ROW_H, self._complexity_shown, True, "complexity"),
            ("weight", ROW_H, self.show_weighting, True, "weight"),
            ("damage", ROW_H, show_tuning, True, "damage"),
        )
        # the present rows that carry an in-tile caption; a column is floored wide enough to
        # keep each of these within MAX_CAPTION_LINES (see _caption_floor in the loop)
        self.present_caption_rows = frozenset(
            key for key, _h, present, _c, _l in row_bands if present and key in CAPTIONED_ROWS)

        # each column hugs its content (a long caption widens the footprint), the columns laid
        # left to right a GAP apart. The element +/− controls no longer ride inside these tiles
        # (they sit up on the fan's top bus, see plus_stub_x), so no column reserves overhang for one.
        self.col_x, self.col_w, self.content_w, self.col_collapsible, self.open_col_w = {}, {}, {}, {}, {}
        x = content_x0
        first_present = True  # the leftmost column carries a title-clearance floor (see below)
        for key, natural, present, collapsible in col_bands:
            if not present:
                continue
            collapsed_col = f"col:{key}" in self.collapsed
            hug_w = max(natural, self._caption_floor(key), self._control_floor(key))  # the open footprint: hugs content (+ caption / control room)
            if first_present:
                # The leftmost column's title can't overhang LEFT: the frozen corner abuts the first
                # tile at freeze_x and paints over anything left of it (clipping "quantities" to
                # "…iantities"). So unlike the other spine titles — free to overhang into the
                # inter-column gaps — this one's footprint is floored to seat its centred title within
                # its own grey tile, clear of the corner. The tile (panel) is col_w + 2·PAD wide, so it
                # holds the title once col_w ≥ title_w − 2·PAD.
                hug_w = max(hug_w, _title_w(self.col_header[key]) - 2 * PAD)
                first_present = False
            self.open_col_w[key] = hug_w  # the width it has (or would have) OPEN — collapse-independent, for caption wrapping
            # The content (value cells + their bracket gutters) is the natural width. The column
            # footprint (col_w) hugs that content, or widens where a long caption needs the room;
            # it does NOT otherwise reserve room for a wider title (the leftmost column above is the
            # one exception). A title wider than its column (the "quantities"/"units" spines, the long
            # interest header) overhangs it instead, rendered without wrapping and centred on the
            # column gridline. The grey tile fills the footprint, with content centred within it (see
            # content_x).
            if collapsed_col:
                # Folded to a title strip — sized to read the (widest line of the) title, but capped
                # at the open footprint so collapsing never WIDENS a column: one already narrower than
                # its title (a spine) keeps its width, the title overhanging, instead of ballooning out.
                self.col_w[key] = self.content_w[key] = min(hug_w, _title_w(self.col_header[key]))
            else:
                self.content_w[key] = natural
                self.col_w[key] = hug_w  # the footprint widens for a long caption
            self.col_collapsible[key] = collapsible
            self.col_x[key] = x
            x += self.col_w[key] + GAP
        self.total_w = x

        # Content is centred within each footprint: the margin is (footprint − content) / 2,
        # zero for the common case (content fills the column) and positive only where a long
        # caption widened the footprint, reserving even margins around the narrower content.
        self.content_x = {key: self.col_x[key] + (self.col_w[key] - self.content_w[key]) / 2 for key in self.col_x}

        self.primes_x = self.content_x.get("primes")  # centred content-left; None when the column is hidden
        self.commas_x = self.content_x.get("commas")  # None when the commas column is hidden
        self.targets_x = self.content_x.get("targets")  # None when the target intervals column is hidden
        self.interest_x = self.content_x.get("interest")  # None when the interest column is hidden
        self.held_x = self.content_x.get("held")  # None when the held intervals column is hidden
        self.detempering_x = self.content_x.get("detempering")  # None when the generator-detempering column is hidden
        self.ssgens_x = self.content_x.get("ssgens")  # None when the superspace generators column is hidden
        self.ssprimes_x = self.content_x.get("ssprimes")  # None when the superspace primes column is hidden

        # The generator tuning-ranges box (the chart + its mode selector) nests at the bottom
        # of the generator tuning map tile when tuning_ranges is on. Its extra height is
        # reserved in the tuning row (below) so the rows beneath drop clear of it rather than
        # the box spilling across them. Determinable up front: it rides the open, uncollapsed
        # gens tile of the (present, unfolded) tuning row.
        self.gtm_chart = (show_ranges and show_tuning and "row:tuning" not in self.collapsed
                     and self.col_open("gens") and "tile:tuning:gens" not in self.collapsed)
        self.gtm_extra = (RANGE_GAP + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if self.gtm_chart else 0
        # the alt.-complexity controls nest at the bottom of their matrix/list tiles (like the
        # ranges box in the gens tile): box 𝐋 (the prescaling matrix over the primes) carries the
        # "replace diminuator" checkbox, box 𝒄 (the complexity list over the targets) stacks the
        # predefined-complexity chooser then the norm chooser, and box 𝒘 (the weight list over the
        # targets) carries the weight-slope chooser. (The prescaler chooser is a preset now, riding
        # the preset band above — see PRESETS.) Each tile reserves its controls' height up front.
        # the diminuator rides the pretransformer chooser's box when presets is on; its own box (here)
        # is only the presets-OFF fallback, mirroring the all-interval checkbox's vectors-row fallback
        self.lbox_ctrl = self._lbox_show and self.col_open("ssprimes" if self.show_superspace else "primes") and not self.show_presets
        # box 𝐋's lone control is the diminuator checkbox at the column's left, over its "replace
        # diminuator" caption: a small square (OPTION_BOX_PX) plus a one-line caption sets the reserve.
        self.lbox_extra = (RANGE_GAP + self.control_region_band_h(OPTION_BOX_PX + CAPTION_LINE)) if self.lbox_ctrl else 0
        # box 𝒄 lays its controls in ONE row below the complexity list: the predefined-complexity
        # master dropdown on the left (a preset — only with the presets layer on), then the q norm-power
        # field and the dual(q) display, each captioned (q/dual using the optimization box's
        # value-symbol-caption stack). q/dual's captions ("interval complexity norm power", "dual norm
        # power") wrap to up to three lines in their overhanging caption slot — reserve the height up
        # front. The targets column was widened up front (by _control_floor) to enclose them — to CBOX_W
        # with the dropdown, the narrower CBOX_NODROP_W (just q | dual) without it.
        self.cbox_ctrl = self._cbox_show and self.col_open("targets")
        self.cbox_extra = (RANGE_GAP + self.control_region_band_h(ROW_H + SYMBOL_H + 3 * CAPTION_LINE)) if self.cbox_ctrl else 0
        # the optimization controls (the power 𝑝 etc.) nest at the bottom of the target interval
        # damage list tile (like the ranges box in the gens tile), gated on the optimization
        # sub-control. Reserve their height up front so the board stays clear below the tile.
        self.opt_ctrl = (self.show_optimization and "row:damage" not in self.collapsed
                    and self.col_open("targets") and "tile:damage:targets" not in self.collapsed)
        # the optimization box: a title strip over a row of three controls distributed across the
        # tile's full width — the mean damage (the minimized damage ⟪𝐝⟫ₚ, "power mean", or the
        # all-interval retuning magnitude) and the editable power 𝑝 (each a value above its symbol
        # above its caption) plus the optimize button. Its height = a title inset + the title + a
        # title gap + the value row + the symbol row + the caption band + pad (the width is the
        # targets column, floored to OPT_BOX_MIN_W). The mean damage's caption names the quantity, and
        # gains a "minimized" prefix while the tuning is optimized (matching the symbol's min() wrap).
        # It wraps within the mean damage column, so reserve however many lines it takes — one ("power
        # mean"), two ("minimized power mean" / "retuning magnitude"), or three ("minimized retuning
        # magnitude").
        self.mean_damage_caption = "retuning magnitude" if self.all_interval else "power mean"
        if self.tuning_optimized:
            self.mean_damage_caption = f"minimized {self.mean_damage_caption}"
        self.opt_cap_lines = _wrap_lines(self.mean_damage_caption, OPT_MEAN_DAMAGE_W) if self.opt_ctrl else 1
        self.opt_extra = ((RANGE_GAP + OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + ROW_H + SYMBOL_H
                      + self.opt_cap_lines * CAPTION_LINE + OPT_PAD_B) if self.opt_ctrl else 0)
        # the chapter-9 nonstandard-domain-approach radio (neutral / prime-based / nonprime-based)
        # rides a reserved band near the bottom of the damage tile, ABOVE the optimization box —
        # shown only when the basis carries a NONPRIME element (the same domain_has_nonprimes gate
        # as the superspace columns/rows), and only while the damage tile is open (its home). Reserve
        # a bold title strip + the three-row square radio so the rows below drop clear, like opt_extra.
        self.show_approach = (service.domain_has_nonprimes(self.elements)
                          and "row:damage" not in self.collapsed and self.col_open("targets")
                          and "tile:damage:targets" not in self.collapsed)
        self.approach_extra = (RANGE_GAP + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if self.show_approach else 0
        # the weight-slope chooser (U/S/C) is the core of box 𝒘 — like box 𝒄's complexity norm it
        # shows with WEIGHTING itself, not gated on the alt. complexity extra. In all-interval
        # mode the weight is simplicity by construction, not a free choice, so the chooser stays put
        # but greys out (slope_locked), locked to its forced simplicity-weight value.
        self.slope_ctrl = (self.show_weighting
                      and "row:weight" not in self.collapsed
                      and self.col_open("targets") and "tile:weight:targets" not in self.collapsed)
        self.slope_locked = self.slope_ctrl and service.is_all_interval(self.tuning_scheme)
        self.slope_extra = (RANGE_GAP + self.control_region_band_h(PRESET_H + CAPTION_LINE)) if self.slope_ctrl else 0
        # Each of these nested controls lives at the bottom of one tile of its row, but its reserved
        # height (keyed here by row) is added to the whole row's tile_h: the rows below drop clear of
        # it AND every tile in the row grows to the same height, so the row stays one uniform band.
        tile_extra = {
            "tuning": self.gtm_extra,        # the generator tuning-ranges chart (box in the genmap)
            "prescaling": self.lbox_extra,   # box 𝐋: the "replace diminuator" checkbox
            "complexity": self.cbox_extra,   # box 𝒄: the predefined-complexity + norm choosers
            "weight": self.slope_extra,      # box 𝒘: the weight-slope chooser
            "damage": self.opt_extra + self.approach_extra,  # optimization controls + the approach radio band
        }

        self.header_y = 0
        self.col_node_y = header_h + (GAP - TOGGLE) / 2  # the column toggle sits just under the header text
        # Branching (trunk/bus/verticals) starts just below the column nodes so no
        # line pokes up past them; with names hidden it starts at the very top.
        self.branch_top_y = self.col_node_y + TOGGLE
        # the first row band sits a GRIP_BAND lower than the bare fan gap, reserving room on the
        # fan for the column reorder-grips (the ⠿ ride this band along the gridlines, between the −
        # above and the first tile below). freeze_y (the seam) drops by the same amount.
        rows_top_y = self.branch_top_y + GAP + GRIP_BAND  # top of the first row band (counts/quantities)
        # The grey tiles overhang their cells by PAD and sit over the gridlines, so the
        # *visible* fan segment runs from a bus only to the tile edge. FAN places each bus
        # midway between the node/foot edge and the tile edge (PAD inside the cell), so
        # the inner (bus->tile) and outer (node->bus) segments are equal: (GAP-PAD)/2.
        self.FAN = (GAP - PAD) / 2

        # row_bands (the top-to-bottom band list) is defined above, ahead of the column
        # widths so they can reserve room for each present row's caption. Every row folds to
        # a strip via its toggle; "quantities" additionally hides that row and its column.
        # A tile stacks (top frame band) + values + (bottom frame band) + (caption).
        # row_y is the value top (cells/gridlines); tile_top is the grey panel top.
        self.row_y, self.row_h, self.row_label, self.row_collapsible = {}, {}, {}, {}
        self.tile_h, self.tile_top, self.row_frame, self.row_sym, self.row_cap, self.row_units, self.row_ptext, self.chart_top = {}, {}, {}, {}, {}, {}, {}, {}
        self.row_pre = {}  # the preset band height, so the <choose form> chooser can stack below it
        self.row_nsub = {}  # each row's natural cell-row count (a matrix's height in cells), so the
        # gridline pass can fan a multi-row matrix into that many horizontal sub-axes -- and keep
        # drawing all of them, converged, while it's folded, so the fold animates as a merge
        self.row_matlabel_top = {}  # y of the column-label band when reserved (one MATLABEL_H slot above
        self.row_int_handle_top = {}  # y of the interval drag-handle band (above the column labels, when drag-to-combine is on)

        # pass the held intervals + any frozen manual tuning so the plain text builds the SAME
        # tuning the grid does (held-just sizes, frozen-tuning maps) — the two views can't diverge.
        # The superspace flag adds the chapter-9 superspace tile strings (B_L, M_L, M_jL, 𝒈ₗ / 𝒕ₗ
        # / 𝒋ₗ / 𝒓ₗ) when the nonstandard-domain toggle is on, matching what the grid emits.
        self.ptext_strings = (service.plain_text_values(self.state, self.tuning_scheme, self.target_spec,
                                                   held=self.held, interest=self.interest,
                                                   generator_tuning=generator_tuning,
                                                   target_override=target_override,
                                                   nonprime_approach=self.nonprime_approach,
                                                   superspace=self.show_superspace,
                                                   superspace_generator_override=(
                                                       self.superspace_generator_tuning
                                                       if self.show_superspace_generators else None))
                         if self.show_ptext else {})

        y = rows_top_y
        for key, natural, present, collapsible, label in row_bands:
            if not present:
                continue
            folded = f"row:{key}" in self.collapsed
            framed = key in FRAMED_ROWS and not folded
            # column labels (𝐜ᵢ above each comma, 𝒕ᵢ above each tuned prime, …) sit INSIDE
            # the tile, in the head area above the top bracket — roughly equidistant from
            # the tile_top and the bracket. The head is expanded when a matlabel is present
            # so the label has padding on both sides (the toggle stays in its corner — the
            # two share the head's y-range but at different x).
            has_matlabel = (self.show_symbols and key in COL_LABELED_ROWS and not folded)
            head_default = TOGGLE + 2 * TOGGLE_INSET - PAD  # toggle's natural head reservation
            # the drag-to-combine handles ride a band at the TOP of the interval-vectors head, ABOVE
            # the column labels (so the grip sits OUTSIDE the c₁/𝒕ᵢ labels, mirroring the row handle
            # to the left of the 𝒎ᵢ labels). Present only when the feature is on and some interval
            # column has ≥ 2 entries to combine — the head grows by the band so the tile is taller.
            int_handle = (key == "vectors" and not folded and self.settings.get("drag_to_combine")
                          and (self.nc >= 2 or (self.k >= 2 and not self.all_interval)
                               or self.nh >= 2 or self.mi >= 2))
            handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if int_handle else 0
            # the matlabel needs MATLABEL_H + 2*PAD of head to sit centred with breathing room
            base_head = 0 if folded else max(head_default, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else head_default)
            head = base_head + handle_band  # the handle band rides above the toggle/label head
            # framing bands stand off the cells by FRAME_GAP: a top bracket (FRAME_H)
            # and a taller bottom curly brace (BRACE_H, with room for its spike)
            top_frame = (FRAME_H + FRAME_GAP) if framed else 0
            bot_frame = (BRACE_H + FRAME_GAP) if framed else 0
            # a charted row grows a chart band (above the values, below the top frame) — but ONLY when its
            # value band is a single row: a bar chart is one bar per column, so a matrix-valued charted row
            # would draw no chart and must reserve no band (else its tile's top third sits empty)
            charted = show_charts and key in CHARTED_ROWS and not folded and natural == ROW_H
            chart_band = (CHART_H + CHART_GAP) if charted else 0
            cap = self.caption_band(key, folded)
            # the symbol line reserves a slot above the caption for every symboled row;
            # equivalences extends that same line (the "= …" continuation) rather than
            # adding a band, so it reserves the slot too even when symbols itself is off
            sym = SYMBOL_H if ((self.show_symbols or self.show_equiv) and key in SYMBOLED_ROWS and not folded) else 0
            # the units line reserves a slot below the caption (above the plain-text box)
            # for every united row, like the symbol slot above the caption
            uni = UNIT_H if (self.show_units and key in UNITED_ROWS and not folded) else 0
            # below the caption/units a tile reserves bands for the plain-text value box and
            # the preset chooser (its row), stacked in that order. The all-interval checkbox rides
            # the vectors row's band too, so the show-panel "all-interval" entry reserves it there even
            # when presets is off (preset_band_h("vectors") gives the target chooser's box height).
            pre = self.preset_band_h(key) if ((self.show_presets and key in PRESET_ROWS
                                             or self.settings["all_interval"] and key == "vectors")
                                            and not folded) else 0
            # the form chooser rides one box below the preset chooser, in the mapping and
            # comma-basis boxes, when form controls are shown
            formctrl = self.formchooser_band_h(key) if (self.show_form_controls and key in FORM_CHOOSER_ROWS and not folded) else 0
            ptext = self.ptext_band(key, folded)
            self.row_h[key] = STRIP if folded else natural
            self.row_nsub[key] = round(natural / ROW_H)  # matrix height in cells (fold-independent)
            self.tile_top[key] = y
            if charted:
                self.chart_top[key] = y + head + top_frame  # the chart sits below the top frame
            if int_handle:  # the grip band rides the very top of the head, above the column labels
                self.row_int_handle_top[key] = y + (handle_band - ROW_HANDLE_W) // 2
            if has_matlabel:
                # col-label sits below the handle band (when present), centred in the remaining head —
                # roughly equidistant from the band/tile-top above and the bracket below
                self.row_matlabel_top[key] = y + handle_band + (base_head - MATLABEL_H) // 2
            self.row_y[key] = y + head + top_frame + chart_band  # values sit below toggle head, top frame, chart
            self.row_frame[key] = bot_frame  # the symbol/caption stack sits below the bottom brace band
            self.row_sym[key] = sym  # the caption (and bands below it) sit below the symbol slot
            self.row_cap[key] = cap  # the units line and plain-text box sit below the caption
            self.row_units[key] = uni  # the plain-text box and preset chooser sit below the units line
            self.row_ptext[key] = ptext  # the plain-text band, with the preset chooser below it
            self.row_pre[key] = pre  # the preset band, with the <choose form> chooser below it
            self.row_label[key] = label
            self.row_collapsible[key] = collapsible
            self.tile_h[key] = head + top_frame + chart_band + self.row_h[key] + bot_frame + sym + cap + uni + pre + ptext + formctrl
            # a row with a nested tile-control (ranges chart, alt-complexity chooser, optimization
            # block) adds its reserved height here, so the rows below drop clear of it and every
            # tile in the row grows to the same height (the row stays one uniform band)
            self.tile_h[key] += tile_extra.get(key, 0)
            y += self.tile_h[key] + GAP
        self.total_h = y

        # Each multi-element column runs a single trunk down to the fan-out bus, where it
        # splits into one line per element. The bus sits centred in the whitespace of the GAP
        # above the first row band (FAN below the branch top) -- immediately after the column
        # toggle, mirroring how the rows fan out at node_edge + FAN just after the row toggle.
        # The element +/− controls ride this bus (see below), and the counts row's per-column
        # cardinality simply has the already-split sub-lines threading through it.
        self.fanout_y = self.branch_top_y + self.FAN

        # The value groups share an element name (for cell ids), a left-edge accessor, a fanned
        # element count, and the operand of their just log₂ (a bare prime, or a comma/target
        # ratio). Defined here — ahead of the cells, the EBK pass and the column_axis fan — so the
        # +/− controls, the brackets and the gridlines all read ONE geometry. primes carry a map,
        # commas and targets interval lists.
        self.group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                      "interest": "interest", "held": "held", "detempering": "detempering",
                      "ssgens": "ssgen", "ssprimes": "ssprime"}
        self.group_left = {"gens": self.gen_left, "primes": self.prime_left, "commas": self.comma_left, "targets": self.target_left,
                      "interest": self.interest_left, "held": self.held_left, "detempering": self.detempering_left,
                      "ssgens": self.ss_gen_left, "ssprimes": self.ss_prime_left}
        # how many side-by-side cells each group column carries: its element count, so the
        # gridline pass can fan every group column into that many vertical sub-axes (commas
        # count the shown columns, draft included). Keyed identically to group_left/group_elem
        # so a column with cells can never be left out of the fan (the generators-column bug).
        self.group_n = {"gens": self.r, "primes": self.d_shown, "commas": self.nv_shown,
                   "targets": self.k_shown,
                   "interest": self.mi_shown, "held": self.nh_shown, "detempering": self.r,
                   "ssgens": self.rL, "ssprimes": self.dL}
        self.group_ratio = {  # the just interval ratio each value group is taken over
            "primes": lambda i: service.element_ratio(self.elements[i]),  # a prime "p/1", or a nonprime element "n/d"
            # over V = C|U the comma sub-columns index the comma ratios, the unchanged sub-columns
            # (i ≥ nc) the unchanged-interval ratios — so the just/retune closed forms resolve for both
            "commas": lambda i: self.comma_ratios[i] if i < self.nc else self.unchanged_ratios[i - self.nc],
            "targets": lambda i: self.targets[i],
            "interest": lambda i: self.interest_ratios[i],
            "held": lambda i: self.held_ratios[i],
            "detempering": lambda i: self.gens[i],  # the detempering interval as a ratio (service.generators = D)
            # the superspace primes — straight prime ratios since the superspace is prime-only
            # by construction (each prime is its own basis element). The ssgens row's just
            # operand is the superspace generator ratio; Phase 4 adds it (this phase emits no
            # just-row content over the superspace generators, so the lookup isn't reached).
            "ssprimes": lambda i: service.element_ratio(self.superspace_primes[i]),
        }

        self.plus_stub_x = {ckey: self.col_plus_x(ckey) for ckey in ("gens", "primes", "commas", "targets", "interest", "held")
                       if self._plus_shows(ckey)}

        # The interval-vectors basis AND the mapping rows fan HORIZONTALLY (one sub-row per prime /
        # generator), so their + is the row mirror of the columns' top-bus +: it rides a stub one
        # ROW_H below the last sub-row, on the row's left bus, with that bus's left bar stretched
        # down to reach it. row_plus_y records it for row_axis (as plus_stub_x does for the columns):
        # the vectors row carries the basis +, the mapping row the +r,−n mapping-row + (only when
        # there's a comma to un-temper — at full rank a generator can't be added holding d).
        self.row_plus_y = {}
        if self.tile_open("vectors", "quantities") and self.standard_domain:  # basis + walks primes
            self.row_plus_y["vectors"] = self.vec_top(self.d) + ROW_H / 2
        if self.tile_open("mapping", "quantities") and self.state.n > 0:
            self.row_plus_y["mapping"] = self.map_top(self.r) + ROW_H / 2

    def _caption_floor(self, key):
        # the width an open column needs so its captions stay within MAX_CAPTION_LINES,
        # widening the tile rather than scaling the font or letting a long name spill;
        # zero when names are hidden (no caption renders) so the column keeps its content size
        if not self.show_captions:
            return 0
        return max((_min_width_for_lines(self.effective_captions[(rk, key)], MAX_CAPTION_LINES)
                    for rk in self.present_caption_rows
                    if (rk, key) in self.effective_captions and (rk, key) in self.declared_tiles), default=0)

    def _control_floor(self, key):
        # the width an open column needs so its in-tile choosers fit without overhanging the
        # column's right edge (e.g. the narrow targets column is widened to seat box 𝒄's wide
        # predefined-complexities dropdown); widens the column to enclose them
        floor = 0
        # each weighting control sits in a bordered box (control_region), so the column must fit the
        # control PLUS the box's BOX_INNER inset on each side, like the optimization box's OPT_PAD.
        # box 𝐋 rides the bare-prescaler column — ss-primes once the superspace shift moves the
        # bare 𝐿 (and its chooser) there, else the domain primes.
        if key == ("ssprimes" if self.show_superspace else "primes") and self._lbox_show:
            # box 𝐋: with presets on, the diminuator rides the pretransformer-chooser box (PBOX_W,
            # the box-𝐓 shape); with presets off it falls back to its own diminuator-only box
            floor = PBOX_W if self.show_presets else LBOX_DIM_W + 2 * BOX_INNER
        if key == "targets" and self._cbox_show:
            # box 𝒄: the complexity + norm choosers, boxed. The predefined-complexities dropdown is a
            # preset, so it (and the width it needs) drops out when the presets layer is off.
            cbox_w = CBOX_W if self.show_presets else CBOX_NODROP_W
            floor = max(floor, cbox_w + 2 * BOX_INNER)
        if key == "targets" and self.show_presets and self.settings["all_interval"]:
            floor = max(floor, TBOX_W)  # box 𝐓: target chooser + all-interval checkbox, one box
        if (key == "targets" and self.show_optimization and "row:damage" not in self.collapsed
                and "tile:damage:targets" not in self.collapsed):
            floor = max(floor, OPT_BOX_MIN_W)  # seat the box's spread-out controls (see opt_box)
        # the preset / form dropdowns' one-line labels (the .rtt-caption-left asset) must fit
        # the column too, so a long label like "established tuning scheme" widens its (narrow)
        # tile rather than spilling it — e.g. the generator tuning map's tuning-scheme copy
        labels = ([l for _n, _r, c, l in PRESETS + PRESET_COPIES if c == key and l] if self.show_presets else [])
        labels += [l for _n, _r, c, l in FORM_CHOOSERS if c == key and l] if self.show_form_controls else []
        if labels:
            floor = max(floor, BOX_OUTER + BOX_INNER + 6 + max(_min_width_for_lines(l, 1) for l in labels))
        return floor

    def content_box(self, key):
        # the (x, width) of a column's actual content — the value cells and the brackets/
        # axes that hug them, centred within the (possibly wider) tile and footprint
        return self.content_x[key], self.content_w[key]

    def tile_box(self, key):
        # the (x, width) of a column's grey tile/panel: the full footprint (the panel fills it
        # and overhangs by PAD). The caption stack rides this width; content centres within.
        return self.col_x[key], self.col_w[key]

    def displayed_optimization_power(self) -> float:
        # the optimization power 𝑝 as shown: ∞ in all-interval mode, the scheme's stored power
        # otherwise. All-interval tuning minimaxes over every interval (it optimizes the primes at
        # the dual norm power and never reads the stored 𝑝), so 𝑝 is fixed at ∞ there — the cell
        # shows ∞ and goes disabled (app._update_powerinput). The power cell, the mean damage, and the
        # damage-chart indicator all read this so the locked display stays consistent.
        if service.is_all_interval(self.tuning_scheme):
            return float("inf")
        return service.optimization_power(self.tuning_scheme)

    def displayed_mean_damage_power(self) -> float:
        # the power at which the displayed mean damage AGGREGATES the per-target/per-prime weighted
        # damages — i.e. the power the optimizer actually minimized at (matching
        # tuning.get_tuning_map_mean_damage). For a target-based scheme that is the optimization
        # power 𝑝 (∞/2/1), same as displayed_optimization_power(). For an all-interval scheme the
        # minimax-over-every-interval is, by duality, an optimization over the PRIMES at the DUAL of
        # the complexity norm power — 2 for a Euclidean (ES) norm, ∞ for taxicab (-S) — so the
        # mean damage is that dual-power mean of the per-prime damages, NOT their max. (The 𝑝 cell still
        # shows ∞: that is the power over intervals; this is the power over primes, the mean damage
        # symbol's dual(𝑞) subscript.) For -S, dual(𝑞) = ∞ so this coincides with 𝑝, as before.
        if service.is_all_interval(self.tuning_scheme):
            return service.dual_norm_power(self.tuning_scheme)
        return service.optimization_power(self.tuning_scheme)

    def col_open(self, key):
        return key in self.col_x and f"col:{key}" not in self.collapsed
    # the value cells), so column labels (𝐜₁, 𝒕₁, …) can be emitted at a fixed row-relative y

    def caption_band(self, key, folded):
        # the row's caption band is sized to its tallest (wrapped) caption, so the longest
        # name fits within its tile rather than spilling off a narrow column. Only columns
        # that actually declare a tile here count: an empty interest column declares no
        # tile, so it reserves no caption height (its captions would otherwise wrap tall in
        # the bare bracket-gutter stub and inflate the empty board). Each caption wraps at
        # its column's OPEN width — collapse-independent — so collapsing a column (hiding its
        # caption) never drops the band and shrinks the row's other tiles. A folded ROW shows
        # no captions at all.
        if not (self.show_captions and key in CAPTIONED_ROWS and not folded):
            return 0
        lines = [_wrap_lines(self.effective_captions[(key, c)], self.open_col_w[c]) for c in self.col_x
                 if (key, c) in self.effective_captions and (key, c) in self.declared_tiles]
        return max(lines, default=1) * CAPTION_LINE

    def ptext_editable(self, rkey, ckey):
        """Whether a tile's plain text is an editable input. Normally :data:`EDITABLE_PTEXT`, but
        under the superspace shift the editable bare prescaler MOVES from the domain-primes column
        to ss-primes (the domain-primes tile is then the read-only 𝐿·B_Ls product), so the
        prescaling row's editable column follows the bare prescaler."""
        if rkey == "prescaling":
            return (rkey, ckey) == ("prescaling", "ssprimes" if self.show_superspace else "primes")
        # the prime-based superspace shift moves the editable generator map from 𝒈 (gens) to 𝒈L
        # (ssgens) — the same relocation the gridded genmap cells make
        if rkey == "tuning" and self.show_superspace_generators:
            return ckey == "ssgens"
        return (rkey, ckey) in EDITABLE_PTEXT

    def ptext_height(self, rkey, ckey):  # one line; the app shrinks the font to fit the box width
        return PTEXT_EDIT_H if self.ptext_editable(rkey, ckey) else PTEXT_H

    def ptext_band(self, key, folded):
        # a single-line band for every value row's plain text (taller for the rows whose
        # band holds an editable input); the font auto-fits so nothing wraps or spills
        if not (self.show_ptext and key in PTEXT_ROWS and not folded):
            return 0
        return PTEXT_EDIT_H if key in EDITABLE_PTEXT_ROWS else PTEXT_H

    # a control box (preset / form chooser): the box spans its column's tile (see control_box),
    # and the dropdown keeps its NATURAL width (cap_w) seated at the box's left — only shrunk if a
    # tiny tile can't seat even that. The label is the standard one-line left-justified caption
    # hugging the dropdown's bottom (the .rtt-caption-left asset), overflowing right if long.
    def control_dims(self, ckey, cap_w, label):
        dropdown_w = max(40, min(self.col_w[ckey] - 2 * BOX_INNER, cap_w))
        label_h = CAPTION_LINE if label else 0  # one line (overflows right, never wraps the box wider)
        box_h = BOX_INNER + PRESET_H + (label_h + CTRL_LABEL_GAP if label else BOX_INNER)
        return dropdown_w, label_h, box_h

    def control_band_h(self, ckey, cap_w, label):  # the box plus outer padding above and below
        return 2 * BOX_OUTER + self.control_dims(ckey, cap_w, label)[2]

    def preset_cap(self, name):
        return TARGET_PRESET_W if name == "target" else PRESET_W

    def preset_band_h(self, key):  # the tallest preset control box riding this row
        return max((self.control_band_h(ckey, self.preset_cap(name), label)
                    for name, rk, ckey, label in PRESETS + PRESET_COPIES
                    if rk == key and ckey in self.col_w), default=0)

    def formchooser_band_h(self, key):
        return max((self.control_band_h(ckey, PRESET_W, label)
                    for name, rk, ckey, label in FORM_CHOOSERS if rk == key and ckey in self.col_w), default=0)

    def row_open(self, key):
        return key in self.row_y and f"row:{key}" not in self.collapsed

    def tile_open(self, rkey, ckey):  # a real tile, whose row + column are open and not folded
        return ((rkey, ckey) in self.declared_tiles and self.row_open(rkey) and self.col_open(ckey)
                and f"tile:{rkey}:{ckey}" not in self.collapsed)

    def tile_unit(self, rkey, ckey):
        """The (rkey, ckey) tile's unit string before per-cell subscripting — the static UNITS
        template, but with the damage / weight / complexity annotation resolved from the live
        scheme (guide ch.10 "Annotated units"): the weight reads ``(<weight_code>)``, damage its
        ``¢``-prefixed form, the complexity ``(<complexity_code>)``. The slope/Euclidean
        parenthetical is the only scheme-dependent unit; every other tile is the static template.
        ``""`` for a tile that carries no unit."""
        base = UNITS.get((rkey, ckey))
        if base is None:
            return ""
        if rkey == "complexity":
            return base.replace("(C)", self.complexity_unit)
        if rkey == "weight":
            return self.weight_unit
        if rkey == "damage":
            return self.damage_unit
        return base

    def cell_unit(self, rkey, ckey, *, gen=None, prime=None, elem=None):
        # the per-value unit shown beneath a gridded cell when units is on: the tile's unit
        # (tile_unit) with its STANDALONE coordinate variables subscripted by this cell's
        # generator/prime index — so the g/p mapping reads g₁/p₁, the tuning map ¢/p₁, a mapped
        # list g₁. Only standalone tokens subscript (see _subscript_coord), so the p inside an
        # annotation family like (sopfr-C)/p stays put while the trailing prime coordinate becomes
        # p₁. A nonstandard subgroup swaps the on-domain p for b (basis element); see domain_label.
        # The chapter-9 superspace tiles run over true primes (p) and superspace generators (gL),
        # NOT the on-domain g/b — so they keep p (the p → b swap is scoped to non-superspace
        # tiles) and subscript the gL token (gL₁) for M_L / 𝒈ₗ.
        if not self.show_units:
            return ""
        u = self.tile_unit(rkey, ckey)
        superspace = rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")
        if gen is not None:
            if superspace:  # the superspace generator coordinate gʟ (g + subscript-L marker)
                u = u.replace(f"g{SUBSCRIPT_L}", f"g{SUBSCRIPT_L}{_sub(gen + 1)}")
            else:
                u = _subscript_coord(u, "g", f"g{_sub(gen + 1)}")
        if prime is not None:
            coord = "p" if superspace else self.domain_label
            u = _subscript_coord(u, "p", f"{coord}{_sub(prime + 1)}")
        # the domain-element coordinate b (the on-domain basis elements that head the primes
        # column): subscripted for tiles whose COLUMN runs over the domain elements — B_L's b/p
        # and M_s→L's gL/b. ``elem`` is the element (column) index.
        if elem is not None:
            u = _subscript_coord(u, self.domain_label, f"{self.domain_label}{_sub(elem + 1)}")
        return u

    def matlabel_gutter_w(self, group_key):
        # The MATLABEL_W gutter reserved on EACH side of a content footprint for row
        # labels (𝒎₁, …) — only the primes column under the mapping matrix needs it in
        # the built layout. The LEFT gutter carries the labels; the RIGHT one is empty,
        # mirroring it so the matrix stays centred in its tile (see content_w above).
        # Shared by prime_left and the bracket placement so the cells, the left ⟨ and the
        # labels stay in lockstep.
        if group_key == "primes":
            return self.matlabel_primes_w
        if group_key == "ssprimes":
            return self.matlabel_ssprimes_w
        return 0

    def handle_gutter_w(self, group_key):
        # The drag-handle gutter reserved OUTSIDE the row-label gutter (further from the matrix),
        # on each side for balance — only the primes column, only when drag-to-combine is on. The
        # left one carries the per-row handles; the right one balances them, like the matlabel gutter.
        return self.row_handle_w if group_key == "primes" else 0

    def outer_gutter_w(self, group_key):
        # the full left/right reservation outside the cells: the handle gutter then the row-label
        # gutter. Used wherever the cells' true left edge matters (prime_left, the EBK span, the header).
        return self.handle_gutter_w(group_key) + self.matlabel_gutter_w(group_key)

    def matrix_span(self, group_key):
        # The (x, width) of a group's CELL matrix — its content_box minus the outer gutters, which
        # content_w carries on BOTH sides (the left holds the handles + row labels, the right
        # balances them). This is the region the EBK encloses: the per-row ⟨ … ] brackets seat
        # their ⟨ at its left edge and ] at its right, and the spanning ebktop/ebkbrace/ebkangle
        # frame runs its full width. Anchored to the cells (not the wider grey footprint), so a
        # column widened past them keeps the EBK hugging the matrix with the labels/handles outside.
        x, w = self.content_box(group_key)
        mx = self.outer_gutter_w(group_key)
        return x + mx, w - 2 * mx

    def _weight_simplicity_header(self, i):
        # the all-interval simplicity weight's per-column header — simply the reciprocal of the
        # complexity column cₙ (whose own header cₙ = ‖𝐿[n]‖q carries the norm detail, so it needn't be
        # repeated here). Matches the tile's big symbol 𝒘 = 𝒄⁻¹, subscripted per column: wₙ = cₙ⁻¹ (bare
        # wₙ when equivalences are off).
        symbol = f"w{_sub(i + 1)}"
        if not self.show_equiv:
            return symbol
        return f"{symbol} = c{_sub(i + 1)}⁻¹"

    def prime_left(self, p):
        return self.primes_x + self.outer_gutter_w("primes") + BRACKET_W + p * COL_W

    @staticmethod
    def _element_cell_kind(text):
        """The editable domain-element kind for a value's display form: a fraction (e.g. "13/5", or
        the "?/?" draft) renders as a stacked fraction face (elementratio); a bare integer prime
        ("2") as a plain number (elementcell). Switching kind across a relabel makes the reconciler
        rebuild the cell, so the face form follows the value."""
        return "elementratio" if "/" in text else "elementcell"

    def comma_left(self, c):
        return self.commas_x + BRACKET_W + c * COL_W

    def target_left(self, j):
        return self.targets_x + BRACKET_W + j * COL_W

    def interest_left(self, i):
        return self.interest_x + BRACKET_W + i * COL_W

    def held_left(self, i):
        return self.held_x + BRACKET_W + i * COL_W

    def detempering_left(self, i):  # the i-th generator detempering column
        return self.detempering_x + BRACKET_W + i * COL_W

    def gen_left(self, g):  # the g-th generator column in the generators box (its tuning-map cells)
        return self.content_x["gens"] + BRACKET_W + g * COL_W

    def ss_gen_left(self, g):  # the g-th superspace generator column (chapter-9)
        return self.ssgens_x + BRACKET_W + g * COL_W

    def ss_prime_left(self, p):  # the p-th superspace prime column (chapter-9)
        return self.ssprimes_x + self.outer_gutter_w("ssprimes") + BRACKET_W + p * COL_W

    def map_top(self, i):
        return self.row_y["mapping"] + i * ROW_H

    def proj_top(self, i):  # the y of projection-matrix row i (the d stacked maps of P = GM)
        return self.row_y["projection"] + i * ROW_H

    def canon_top(self, i):  # the y of canonical-mapping row i (the r stacked canonical maps)
        return self.row_y["canon"] + i * ROW_H

    def vec_top(self, p):  # the y of vector component p in the d-tall interval-vectors row
        return self.row_y["vectors"] + p * ROW_H

    def ss_vec_top(self, p):  # the y of superspace-vector component p in the dL-tall ss_vectors row
        return self.row_y["ss_vectors"] + p * ROW_H

    def ss_map_top(self, i):  # the y of ss_mapping row i (the rL stacked superspace maps)
        return self.row_y["ss_mapping"] + i * ROW_H

    def ss_just_map_top(self, i):  # the y of ss_just_mapping row i (the dL stacked superspace JI maps)
        return self.row_y["ss_just_mapping"] + i * ROW_H

    # The element +/− controls ride each fanning column's TOP bus (the fan-out, just after the
    # toggle), not the quantities row: the − sits on a branch point (a per-element split), the +
    # on a "stub" one COL_W past the last branch point — the slot where the next element would
    # branch — with the top bus stretched out to reach it. sub_axis_x is the split's x (column_axis
    # fans the same centres); plus_stub_x records, per addable column that shows a +, where that +
    # (and so the bus end) sits, keeping the cells and the gridlines in lockstep.
    def sub_axis_x(self, ckey, i):  # centre of column ckey's i-th per-element sub-axis (a branch point)
        return self.group_left[ckey](i) + COL_W / 2

    def col_plus_x(self, ckey):
        n = self.group_n[ckey]
        if n == 0:  # an empty set has no branch points: the + centres on the single trunk
            mx, mw = self.matrix_span(ckey)
            return mx + mw / 2
        return self.sub_axis_x(ckey, n - 1) + COL_W  # one slot past the last branch point

    def _plus_shows(self, ckey):  # mirrors the +'s emit gate in the quantities block (col_open for the
        if ckey in ("interest", "held"):  # addable sets, so an empty-but-open column still adds one)
            return self.col_open(ckey) and self.row_open("quantities")
        if ckey == "targets":  # the target list is user-curated only when NOT all-interval (else it's auto Tₚ = I)
            return self.tile_open("quantities", "targets") and not self.all_interval
        if ckey == "gens":  # the generators + un-temps a comma (−n, +r), so it needs one to un-temper
            return self.tile_open("quantities", "gens") and self.state.n > 0
        if ckey == "primes":  # off: the + walks to the next standard prime (inapplicable to a subgroup).
            # On (nonstandard-domain box): the + starts a typed ?/? element draft, valid for ANY domain.
            return self.tile_open("quantities", "primes") and (self.show_nonstandard_domain or self.standard_domain)
        if ckey == "commas":  # the consolidated V view freezes the comma count (a +/− would change
            return self.tile_open("quantities", "commas") and not self.show_unchanged  # the rank, hence U)
        return self.tile_open("quantities", ckey)

    def closed_form_operand(self, key, group, i):
        """The operand ``R`` of a cell's exact closed form ``1200 · log₂R``, or None
        when the value has no closed form. A just size IS ``1200·log₂`` of its
        interval. A comma vanishes in the temperament, so its retuning is the negated
        just size — the exact log of the inverted comma. The tempered sizes and the
        prime/target errors come from optimization, so they have none — as do the
        unchanged sub-columns of V (i ≥ nc): an unchanged interval isn't tempered out,
        so its retuning is the optimization error, not the negated-just closed form."""
        if key == "just":
            return _log_operand(self.group_ratio[group](i))
        if group == "commas" and key == "retune" and i < self.nc:
            recip = 1 / Fraction(self.comma_ratios[i])
            return _log_operand(f"{recip.numerator}/{recip.denominator}")
        return None

    def col_token(self, group, i):
        """The stable id-token for column ``i`` of a reorderable interval list (targets/held/
        interest), so all of a column's cells share one token and re-key together when it moves
        (the reconciler then glides them). Any other group (gens/primes/commas, which don't reorder)
        keeps its bare index, so those cell ids are unchanged."""
        pairs = self._col_ids.get(group)
        return i if pairs is None else pairs[i][0]

    def pending_col_token(self, group):
        """The id-token for a list's draft (pending) column — one past every committed column's, so
        it never collides with a live column. On a fresh list this is the column count, matching the
        historical ``…:count`` draft-cell ids."""
        return pending_token([tok for tok, _ in self._col_ids[group]])

    def _voice(self, tile, idx, cents):
        """Make the just-built cell (``self.cells[-1]``) click-to-play: hovering it reveals a speaker
        that sounds ``cents``. ``tile`` + ``idx`` group a row's cells so the bank's arp / chord /
        rolled-chord modes sweep the whole tile from the clicked note — the client derives the chord
        from the tile's sibling cells, so it stays correct across reorders with no baked pitch list."""
        self.cells[-1] = replace(self.cells[-1], audio=(tile, int(idx), float(cents)))

    def tuning_value_row(self, key, group, values, alerts=()):
        if not self.tile_open(key, group):
            return
        values = tuple(values)
        if key in CHARTED_ROWS:
            self.chart_tiles.append((key, group, values))
        y = self.row_y[key]
        # the tuning-family unit is cents per the column's coordinate: over the generators
        # it's ¢/gᵢ (gens) or ¢/gLᵢ (the chapter-9 superspace ssgens), over the primes ¢/pᵢ /
        # ¢/bᵢ (the domain primes / basis elements) or ¢/pᵢ (the superspace ssprimes, true
        # primes), and over the (dimensionless) interval columns plain ¢
        is_gen_group = group in ("gens", "ssgens")
        is_prime_group = group in ("primes", "ssprimes")
        for i, v in enumerate(values):
            cid = f"{key}:{self.group_elem[group]}:{self.col_token(group, i)}"
            x = self.group_left[group](i)
            u = self.cell_unit(key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
            # the held column passes per-interval alert flags: an interval the tuning no longer
            # holds reddens its size cells too (alerts is empty — no flags — for every other column)
            alert = bool(alerts[i]) if i < len(alerts) else False
            operand = self.closed_form_operand(key, group, i) if self.show_math else None
            if operand is not None:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, self.show_quantities), unit=u, alert=alert))
            else:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, "tuningvalue", text=service.cents(v), unit=u, alert=alert))
            if key in ("tuning", "just"):  # the tuning row sounds each interval's TEMPERED size, the
                self._voice(f"{key}:{group}", i, v)  # just row its JUST size; retune (errors) is no pitch

    # a charted tile draws a bar chart in the band reserved above its values. The box spans
    # the value block exactly — the left bracket gutter, the value columns, and the right
    # bracket gutter — anchored to group_left (the cells), NOT the column footprint. So the
    # chart's BRACKET_W-inset axis and COL_W bar pitch overlay the cells: each bar centres on
    # its value's gridline even when a caption widens the footprint or a matlabel gutter
    # offsets the cells within it (the gridlines follow the cells the same way; see
    # column_axis). chart_top[key] exists only where a chart band was reserved (charts on,
    # row charted, not folded), so it gates emission against the layout with no drift.
    def chart(self, rkey, ckey, values, indicator=None, indicator_label=""):
        values = tuple(values)
        if values and rkey in self.chart_top and self.tile_open(rkey, ckey):
            x = self.group_left[ckey](0) - BRACKET_W  # the left bracket gutter, where the value block starts
            self.cells.append(CellBox(f"chart:{rkey}:{ckey}", x, self.chart_top[rkey],
                                 2 * BRACKET_W + len(values) * COL_W, CHART_H, "chart", values=values,
                                 indicator=indicator, indicator_label=indicator_label))

    # EBK brackets in the value groups' gutters: prime-side rows are maps (⟨…]),
    # target-side rows are lists ([ … ]). Maps stack one per generator row.
    def bracket(self, bid, glyphs, group_key, y, h, *, fit=False, span=None):
        # value brackets are short and centred in their row (so stacked rows keep a
        # gap); the enclosing mapped-list [ ] passes fit=True to span the matrix.
        # matrix_span hugs the cells (interest's content, not its footprint) and steps
        # the left ⟨ right past the matlabel gutter, so the row labels sit inside the
        # panel left of the ⟨ rather than overflowing it. ``span`` overrides the default span.
        gx, gw = span if span else self.matrix_span(group_key)
        by, bh = (y, h) if fit else (y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H)
        self.cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0]))
        self.cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1]))

    # the single place a gridline is recorded. ``dotted`` marks a rule whose band is
    # collapsed: a folded row/column converges its fan onto one centre rule, drawn dotted
    # so the band reads as a placeholder for its hidden content (see Line.dotted).
    def gridline(self, lid, orientation, pos, start, length, *, dotted):
        self.lines.append(Line(lid, orientation, pos, start, length, dotted=dotted))

    def column_axis(self, key, prefix, n, center_open):
        if key not in self.col_x:
            return
        self.fanned_columns.add(key)
        dotted = f"col:{key}" in self.collapsed  # the whole fan dots when the column folds
        # the trunk centres on the cell SPAN (matrix_span), not the wider column footprint:
        # the two diverge when a matrix-label gutter offsets the cells (primes under the
        # mapping). matrix_span is collapse-aware -- it shrinks to the title strip when the
        # column folds -- so a collapsed column's gridline tracks its fold node and the
        # panels converging onto it, instead of stranding at the centre of where the OPEN
        # cells used to sit (which left it off-centre by half the width the fold shed).
        mx, mw = self.matrix_span(key)
        cx = mx + mw / 2
        if n == 0:  # an empty interval set (interest, before any are entered) is one straight axis
            self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.fanout_y - self.branch_top_y, dotted=dotted)
            self.gridline(f"foot:{key}", "v", cx, self.fanout_y, self.total_h - self.fanout_y, dotted=dotted)
            return
        xs = [cx] * n if dotted else [center_open(i) for i in range(n)]
        for i in range(n):
            self.gridline(f"v:{prefix}:{i}", "v", xs[i], self.fanout_y, self.bot_bus_y - self.fanout_y, dotted=dotted)
        bx, bw = _bus_span(xs)
        # an addable column stretches its TOP bus out past the last sub-axis to the + stub, so the
        # branching bar reaches the + (which rides plus_stub_x); the bottom bus just spans the data.
        top_end = self.plus_stub_x[key] if key in self.plus_stub_x else bx + bw
        self.gridline(f"bus:{key}:top", "h", self.fanout_y, bx, top_end - bx, dotted=dotted)
        self.gridline(f"bus:{key}:bot", "h", self.bot_bus_y, bx, bw, dotted=dotted)
        self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.fanout_y - self.branch_top_y, dotted=dotted)
        self.gridline(f"foot:{key}", "v", cx, self.bot_bus_y, self.total_h - self.bot_bus_y, dotted=dotted)
    def _row_fans(self, key):
        # A row fans its left bus OUT to node_edge + FAN (branching into per-sub-row rules) when it
        # has more than one cell-row OR carries a row + stub. The + must ride a fanned bus to sit
        # beside the content and stay reached by the connecting bar — so even a SINGLE-row band that
        # adds elements fans (a rank-1 ET mapping, whose lone generator row still shows the
        # comma-un-tempering +): the row mirror of an addable column always fanning to seat its +.
        return self.row_nsub[key] > 1 or key in self.row_plus_y

    def row_axis(self, key):
        n = self.row_nsub[key]
        folded = f"row:{key}" in self.collapsed  # the whole fan dots and converges when the row folds
        cy = self.row_y[key] + self.row_h[key] / 2
        ys = [cy] * n if folded else [self.row_y[key] + i * ROW_H + ROW_H / 2 for i in range(n)]
        left_bus_x = self.node_edge + self.FAN if (self._row_fans(key) and not folded) else self.node_edge
        for i in range(n):
            self.gridline(f"h:{key}:{i}", "h", ys[i], left_bus_x, self.right_bus_x - left_bus_x, dotted=folded)
        bus_y, bus_h = _bus_span(ys)
        # a row with a + stub (the vectors basis +, the mapping-row +) stretches its LEFT bar down
        # past the last sub-row to that stub (row_plus_y), so the branching bar reaches the +; the
        # right bar just spans the data.
        left_bottom = self.row_plus_y[key] if key in self.row_plus_y else bus_y + bus_h
        self.gridline(f"vbar:{key}:left", "v", left_bus_x, bus_y, left_bottom - bus_y, dotted=folded)
        self.gridline(f"vbar:{key}:right", "v", self.right_bus_x, bus_y, bus_h, dotted=folded)
        self.gridline(f"trunk:{key}", "h", cy, self.node_edge, left_bus_x - self.node_edge, dotted=folded)
        self.gridline(f"foot:{key}", "h", cy, self.right_bus_x, self.total_w - self.right_bus_x, dotted=folded)

    # #e0e0e0 panels behind each content group. A panel folds to zero size along
    # any collapsed axis (collapsing toward the band centre), so the renderer
    # animates it shrinking away to nothing — leaving only the band's gridline,
    # never a leftover grey strip. Every tile is simply its row band's full height — a row with
    # a nested control (chart/chooser) is one uniform band: tile_h already includes that control's
    # reservation, so every tile in the row gets the same (extended) height here.
    def panel_rect(self, ckey, rkey):
        # a folded tile collapses both ways at once, so it shrinks to a point at its
        # centre — like a row+column collapse confined to this one tile.
        tile_c = f"tile:{rkey}:{ckey}" in self.collapsed
        col_c = f"col:{ckey}" in self.collapsed or tile_c
        row_c = f"row:{rkey}" in self.collapsed or tile_c
        cx, cw = self.tile_box(ckey)  # the tile widens for a long caption; content centres within it
        ch, cy = self.tile_h[rkey], self.tile_top[rkey]
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        return bx - px, by - py, w + 2 * px, h + 2 * py

    def panel(self, bid, ckey, rkey):
        if ckey not in self.col_x or rkey not in self.row_y:
            return
        self.blocks.append(Block(bid, *self.panel_rect(ckey, rkey)))

    # Colorization washes. Each colour-bearing tile renders one band per group — a white
    # base plus the group's colour at mix-blend-mode:darken (see app.py). The base sits a
    # layer BELOW the colour (z-index), so where a tile carries both groups the two colour
    # bands darken-compose regardless of paint order: cyan over yellow gives the mockup's
    # green. Each band hugs its (open) tile's extent and overhangs by WASH_PAD — so a run of
    # same-coloured tiles meets across the inter-tile gaps and reads as one continuous band
    # rather than leaving grey strips between them. A folded tile (by its own toggle, its row
    # or its column) is not open, so its colour goes away with its content. Two sources of a
    # tile's groups: most tiles colour by CONTENT (the colour-bearing objects multiplied into
    # their quantity, CELL_FACTORS); the spine label cells colour by the BAND they head — the
    # counts + units rows by their column's family, the quantities + units columns by their
    # row's family — continuing each value band's colour through the spine (see SPINE_*).
    def tile_groups(self, rkey, ckey):
        if rkey in SPINE_ROWS and ckey in SPINE_COLUMN_GROUP:
            return {SPINE_COLUMN_GROUP[ckey]}          # a counts/units row cell: its column's family
        if ckey in SPINE_COLUMNS and rkey in SPINE_ROW_GROUP:
            return {SPINE_ROW_GROUP[rkey]}             # a quantities/units column cell: its row's family
        # the chapter-9 superspace block is a cyan (tuning) REGION, green only where it crosses a
        # yellow temperament COLUMN (the domain-basis elements / commas, carrying P / C) — a coarse
        # region tint, not the per-object CELL_FACTORS scheme (see SUPERSPACE_REGION_* in grid_tables).
        # Its own ssgens / ssprimes columns read cyan (the superspace primes are deliberately NOT
        # washed yellow here), as do the tuning maps, the M_jL identity and the spine.
        if ckey in SUPERSPACE_REGION_COLUMNS or rkey in SUPERSPACE_REGION_ROWS:
            groups = {"tuning"}
            if SPINE_COLUMN_GROUP.get(ckey) == "temperament":
                groups.add("temperament")
            return groups
        return {_FACTOR_GROUP[f] for f in CELL_FACTORS.get((rkey, ckey), ())}

    # the plain-text box sits directly below the symbol/caption/units stack; the preset
    # chooser rides one plain-text band lower (so presets appear under plain text).
    def ptext_band_y(self, rkey):
        return self.row_y[rkey] + self.row_h[rkey] + self.row_frame[rkey] + self.row_sym[rkey] + self.row_cap[rkey] + self.row_units[rkey]

    # A chooser dropdown that offers only ONE option, with that option already selected, is not a
    # choice — it renders as a DISABLED dropdown (greyed, non-interactive, but still left-justified
    # like any dropdown), exactly like the all-interval-locked target / weight-slope choosers
    # (Douglas's request). These predicates decide that, shared by the preset choosers (tuning /
    # prescaler) and the box-𝒄 complexity control select.
    @staticmethod
    def _is_sole_option(options, value):
        """True when ``options`` offers exactly one choice AND ``value`` is it — so the chooser has
        no real choice and renders disabled. ``options`` is a ``{value: label}`` mapping (a list/tuple
        is taken as value==label). False for a real choice (≥2 options) or an off-list value — a
        deviating edit shows "-", which stays interactive so its one option can reset it."""
        opts = options if isinstance(options, dict) else {o: o for o in options}
        return len(opts) == 1 and value in opts

    def _preset_locked(self, name):
        """Whether a tuning / prescaler preset is locked to its single on-list option (→ a disabled
        dropdown). Temperament and target always offer a real choice. The on-list value mirrors
        app._build_preset: the tuning chooser's via the threaded displayed_tuning_name, the
        prescaler's via the realised diagonal name resolved in phase 2."""
        if name == "tuning":
            options = presets.tuning_scheme_options(
                service.is_all_interval(self.tuning_scheme),
                self.settings["alt_complexity"], self.settings["weighting"])
            return self._is_sole_option(options, self.displayed_tuning_name)
        if name == "prescaler":
            return self._is_sole_option(presets.prescaler_options(self.settings["alt_complexity"]),
                                        self._realized_prescaler)
        if name == "projection":
            # a temperament with no established rational tuning has nothing to offer — show a
            # disabled, placeholder-only chooser (like the all-interval-locked target chooser)
            return not presets.projection_options(self.state)
        return False

    # a control box: a thin-bordered frame SPANNING the full width of its column's tile (like the
    # optimization / tuning-ranges boxes), with the dropdown seated at its top-left at the dropdown's
    # natural width and the standard dropdown-label underneath — a left-justified one-line caption
    # (.rtt-caption-left: 6px left, 2px top) hugging the dropdown's bottom edge, the same asset every
    # other labelled control uses. Any sibling control (the target chooser's all-interval checkbox,
    # box 𝐓) rides the empty space to the dropdown's right, inside this same full-width box. Returns
    # the (x, width, y) to seat the dropdown at.
    def control_box(self, box_id, ckey, top, cap_w, label, disabled=False):
        dropdown_w, label_h, box_h = self.control_dims(ckey, cap_w, label)
        box_x, box_y = self.col_x[ckey], top + BOX_OUTER  # spans the tile footprint; BOX_OUTER is vertical only
        self.blocks.append(Block(box_id, box_x, box_y, self.col_w[ckey], box_h, boxed=True))
        ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER
        if label:  # disabled greys the label with its control (a locked chooser, e.g. all-interval target)
            self.cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                                 "caption", text=label, align="left", disabled=disabled))
        return ctrl_x, dropdown_w, ctrl_y

    def control_region(self, box_id, ckey, top, content_h):
        """A bordered control box (boxed Block) spanning tile ``ckey`` from ``top``, enclosing
        ``content_h`` of stacked controls inset BOX_INNER at the top and CTRL_LABEL_GAP at the
        bottom — the control_box frame, but for arbitrary content (the box-𝐋 checkbox, the box-𝒄
        multi-control row) rather than just a dropdown+label. Returns the inner top-left (x, y) the
        controls start at, so each control's own offsets stay as they were, just shifted inside. The
        box Block is DEFERRED (collected, not appended now) so it layers on top of the grey panels."""
        box_y = top + BOX_OUTER
        self._control_region_boxes.append(Block(box_id, self.col_x[ckey], box_y, self.col_w[ckey],
                                                 BOX_INNER + content_h + CTRL_LABEL_GAP, boxed=True))
        return self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER

    def control_region_band_h(self, content_h):
        """The full band a :func:`control_region` of ``content_h`` reserves — the box plus its
        BOX_OUTER vertical padding above and below (the counterpart of :func:`control_band_h`)."""
        return 2 * BOX_OUTER + BOX_INNER + content_h + CTRL_LABEL_GAP

    def emit_all_interval_check(self, check_x, ctrl_y):
        # the all-interval checkbox + its caption, seated on a control row at ctrl_y: an OPTION_BOX_PX
        # square over an "all-interval" caption in an LBOX_DIM_W slot (the box-𝐋 diminuator's shape). It
        # reflects whether the scheme targets every interval (ticking it is wired in app.py).
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2  # centre the square on the control row
        self.cells.append(CellBox("control:all_interval", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.is_all_interval(self.tuning_scheme)))
        self.cells.append(CellBox("caption:all_interval", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="all-interval"))

    def emit_diminuator_check(self, check_x, ctrl_y):
        # the "replace diminuator" checkbox + caption, seated to the RIGHT of the predefined-
        # pretransformers dropdown inside its preset box — box 𝐋's control riding the existing
        # pretransformer-chooser box, the way the all-interval check rides the target chooser box.
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2  # centre the square on the control row
        self.cells.append(CellBox("control:diminuator", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.diminuator_replaced(self.tuning_scheme)))
        self.cells.append(CellBox("caption:diminuator", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="replace diminuator"))

    # a framed matrix's top bracket + bottom brace stand off the cells by FRAME_GAP:
    # the top bracket just above row 0 (below the toggle head), the brace a matching
    # gap below the last row of that band.
    def frame_top_y(self, rkey):
        return self.row_y[rkey] - FRAME_H - FRAME_GAP

    def frame_brace_y(self, rkey):
        return self.row_y[rkey] + self.row_h[rkey] + FRAME_GAP

    # a matrix tile (the primes mapping and its canonical forms) is enclosed by a top
    # bracket + bottom curly brace spanning its whole column: the brace marks generator
    # coordinates, so it's the right close for the mapping but not for raw vectors or
    # prescaled vectors (those use per-column marks via vector_list_marks). ``bid`` keeps
    # each frame's ids stable so two framed rows over the same column never collide.
    def matrix_frame(self, rkey, ckey, bid, foot="ebkbrace", span=None):
        # The spanning frame hugs the CELL matrix — content_box, exactly as the per-row
        # bracket() calls do — not the grey footprint (col_x/col_w). The matlabel gutter
        # (row labels 𝒎ᵢ / 𝒙ᵢ) sits LEFT of that matrix, OUTSIDE the frame. Anchoring to
        # the footprint instead would, whenever it is widened past its content (e.g. by the
        # prescaler chooser or box-𝐋 diminuator under the prescaling matrix), drag the frame left
        # over those labels and right past the cells. ``foot`` is the bottom-spanning close:
        # ``ebkbrace`` for the mapping family (generator coordinates, curly close),
        # ``ebkangle`` for the bare prescaler 𝐿 (angle close ⟩, mirroring the mapping's
        # plain-text bracket but with ⟩ in place of }).
        if not self.tile_open(rkey, ckey):
            return
        gx, gw = span if span else self.matrix_span(ckey)  # ``span`` overrides the default cell-matrix span
        self.cells.append(CellBox(f"ebktop:{bid}", gx, self.frame_top_y(rkey), gw, FRAME_H, "ebktop"))
        self.cells.append(CellBox(f"{foot}:{bid}", gx, self.frame_brace_y(rkey), gw, BRACE_H, foot))
    # the 𝐿·basis product matrices (𝐿C/𝐿D/𝐿T/𝐿H) and the interest tile use a
    # COLUMN-WISE construction instead — per-column ket ``[ … ⟩`` marks with outer ``[ … ]``
    # left/right brackets (or no outer wrap for interest). See the vector_list_marks +
    # bracket calls further below.

    # a matrix of vector columns: vertical rules separate the columns, and each is
    # marked top + bottom — inset so they stop short of the rules. ``top`` and ``foot``
    # pick the per-column shapes: a tempered/mapped column (generator coords) takes the
    # default ``[ ... }`` (ebktop + ebkbrace curly close); a raw (untempered) vector or a
    # prescaled vector is a ket, closing with the angle ⟩ (ebkangle) instead — ``[ ... ⟩``.
    # ``separators=False`` drops the dividing rules: for a bordered grid (the comma
    # basis — its own cell borders already divide the columns) or for the standalone
    # columns of the intervals-of-interest collection (which isn't a matrix at all).
    def vector_list_marks(self, rkey, name, ckey, left, n_cols, top="ebktop", foot="ebkbrace", separators=True, pending_col=-1):
        if not self.tile_open(rkey, ckey):
            return
        mark_w = COL_W - 2 * MARK_INSET
        for c in range(n_cols):
            mx = left(c) + MARK_INSET
            pend = (c == pending_col)  # the draft column's ket marks render red, like its cells
            self.cells.append(CellBox(f"{top}:{name}:{c}", mx, self.frame_top_y(rkey), mark_w, FRAME_H, top, pending=pend))
            self.cells.append(CellBox(f"{foot}:{name}:{c}", mx, self.frame_brace_y(rkey), mark_w, BRACE_H, foot, pending=pend))
        if not separators:
            return
        for c in range(1, n_cols):  # a rule on each interior column boundary
            self.cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, self.row_y[rkey], SEP_W, self.row_h[rkey], "vbar"))

    def layout(self) -> Layout:
        self.cells: list[CellBox] = []
        self.lines: list[Line] = []
        self.blocks: list[Block] = []
        # the box-𝐋/𝒄/𝒘 control boxes are emitted during the cell pass (to position their controls)
        # but must LAYER ON TOP of the grey tile panels — appended below the panel loop, like the
        # optimization / ranges boxes — so collect them here and flush them after the panels.
        self._control_region_boxes: list[Block] = []

        # column headers (always shown; a collapsed column keeps its title) plus a
        # fold toggle in the header band for collapsible ones. A matlabel-widened column
        # (primes when symbols is on) carries the gutter on both sides, so the header + toggle
        # drop the gutter from each edge and stay centred over the CELLS rather than the wider
        # column footprint — the gutters only frame the row labels, never the title.
        for key in self.col_x:
            hx = self.col_x[key] + self.outer_gutter_w(key)
            hw = self.col_w[key] - 2 * self.outer_gutter_w(key)
            self.cells.append(CellBox(f"header:{key}", hx, self.header_y, hw, HEADER_H, "colheader", text=self.col_header[key]))
            if self.col_collapsible[key]:
                glyph = _fold_glyph(f"col:{key}" in self.collapsed)
                # the fold toggle sits on the column's gridline (its content centre), so it
                # stays aligned with the trunk even when the interest header floats wider
                tx = hx + (hw - TOGGLE) / 2
                self.cells.append(CellBox(f"toggle:col:{key}", tx, self.col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))

        # row labels (always shown; a collapsed row keeps its label as the strip)
        # plus a fold toggle in the gutter for the collapsible ones
        for key in self.row_y:
            label = self.row_label[key]
            if self.size_factor:
                label = _pretransform_label(label)
                # "complexity pretransforming" is too long for the gutter; hyphenate the word at "pre-"
                # and hard-break before "transforming" (full font, no shrink). The nbsp keeps "complexity
                # pre-" together (LABEL_W is now wide enough for it) and the newline (the pre-line
                # rtt-rowlabel honours it) drops "transforming": two lines, "complexity pre-" / "transforming".
                label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
            self.cells.append(CellBox(f"label:{key}", 0, self.row_y[key], LABEL_W, self.row_h[key], "rowlabel", text=label))
            if self.row_collapsible[key]:
                glyph = _fold_glyph(f"row:{key}" in self.collapsed)
                ty = self.row_y[key] + (self.row_h[key] - TOGGLE) / 2
                self.cells.append(CellBox(f"toggle:row:{key}", self.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))

        # the master expand/collapse-all toggle, in the corner where the row-toggle column
        # (node_x) meets the column-toggle row (col_node_y). Its glyph mirrors the whole
        # grid: out-chevrons to expand when every foldable row and column is already
        # collapsed, in-chevrons to collapse otherwise.
        foldable = _foldable_ids(self.cells)  # the row/col toggles emitted just above
        all_collapsed = bool(foldable) and foldable <= self.collapsed
        self.cells.append(CellBox("toggle:all", self.node_x, self.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                             text=_fold_glyph(all_collapsed)))

        # counts row: each present column's set cardinality, centred over its values. The
        # detempering column counts the rank r (one detempering interval per generator); the
        # superspace columns count their own rank rL and dimensionality dL.
        if self.row_open("counts"):
            cardinality = {"gens": self.r, "primes": self.d, "commas": self.state.n, "targets": self.k, "held": self.nh,
                           "detempering": self.r,
                           "ssgens": self.rL, "ssprimes": self.dL}
            for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
                if self.tile_open("counts", ckey):
                    self.cells.append(CellBox(f"count:{ckey}", self.col_x[ckey], self.row_y["counts"], self.col_w[ckey], ROW_H,
                                         "count", text=f"{_count_sym(sym)} = {cardinality[ckey]}"))

        # units row + column (the specific `domain_units` toggle): coordinate-unit labels.
        # The units COLUMN labels each row's coordinate — the interval-vectors basis in
        # primes (pᵢ/), the mapping in generators (gᵢ/), the cents tuning rows as ¢/. The
        # units ROW labels each column's coordinate — /gᵢ over generators, /pᵢ over the
        # domain primes, /1 over the ratio columns. Each rides its own grey tile
        # (UNITS_TILES), so tile_open gates emission against the live layout.
        if self.tile_open("vectors", "units"):
            for p in range(self.d):
                self.cells.append(CellBox(f"ucol:vectors:{p}", self.col_x["units"], self.vec_top(p), self.col_w["units"], ROW_H,
                                     "units", text=f"{self.domain_label}{_sub(p + 1)}/"))
        if self.tile_open("mapping", "units"):
            for i in range(self.r):
                self.cells.append(CellBox(f"ucol:mapping:{i}", self.col_x["units"], self.map_top(i), self.col_w["units"], ROW_H,
                                     "units", text=f"g{_sub(i + 1)}/"))
        # the chapter-9 superspace rows label their coordinate in the units column too: B_L's
        # components and M_jL's identity are superspace primes (pᵢ/), M_L's rows are superspace
        # generators (gLᵢ/) — true primes / superspace generators, never the on-domain b/g
        if self.tile_open("ss_vectors", "units"):
            for p in range(self.dL):
                self.cells.append(CellBox(f"ucol:ss_vectors:{p}", self.col_x["units"], self.ss_vec_top(p), self.col_w["units"], ROW_H,
                                     "units", text=f"p{_sub(p + 1)}/"))
        if self.tile_open("ss_mapping", "units"):
            for i in range(self.rL):
                self.cells.append(CellBox(f"ucol:ss_mapping:{i}", self.col_x["units"], self.ss_map_top(i), self.col_w["units"], ROW_H,
                                     "units", text=f"g{SUBSCRIPT_L}{_sub(i + 1)}/"))
        if self.tile_open("ss_just_mapping", "units"):
            for p in range(self.dL):
                self.cells.append(CellBox(f"ucol:ss_just_mapping:{p}", self.col_x["units"], self.ss_just_map_top(p), self.col_w["units"], ROW_H,
                                     "units", text=f"p{_sub(p + 1)}/"))
        # the cents / octave / annotated-unit rows (guide ch.10 "Annotated units"). Each renders one
        # unit cell PER SUBROW — derived from the cell-row count row_nsub — so a matrix-valued row (the
        # prescaler 𝑋 = 𝑍𝐿's size row) carries a unit on EVERY row, not just its first. Generic to any
        # multi-row tile, so this can't silently regress when a new matrix row appears. Single-row tiles
        # keep the bare id; multi-row ones index it by subrow (matching the prescaler's existing ids).
        const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                       "complexity": f"{self.complexity_unit}/", "weight": f"{self.weight_unit}/",
                       "damage": f"{self.damage_unit}/"}
        for key, text in const_units.items():
            if not self.tile_open(key, "units"):
                continue
            n = self.row_nsub[key]
            for i in range(n):
                cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
                self.cells.append(CellBox(cid, self.col_x["units"], self.row_y[key] + i * ROW_H,
                                     self.col_w["units"], ROW_H, "units", text=text))
        if "units" in self.row_y:
            uy = self.row_y["units"]
            if self.tile_open("units", "gens"):
                for g in range(self.r):
                    self.cells.append(CellBox(f"urow:gens:{g}", self.gen_left(g), uy, COL_W, ROW_H, "units", text=f"/g{_sub(g + 1)}"))
            if self.tile_open("units", "primes"):
                for p in range(self.d):
                    self.cells.append(CellBox(f"urow:primes:{p}", self.prime_left(p), uy, COL_W, ROW_H, "units", text=f"/{self.domain_label}{_sub(p + 1)}"))
            # the chapter-9 superspace columns: /gLᵢ over the superspace generators, /pᵢ over
            # the superspace primes (true primes p — NOT the on-domain b, even when nonstandard)
            if self.tile_open("units", "ssgens"):
                for g in range(self.rL):
                    self.cells.append(CellBox(f"urow:ssgens:{g}", self.ss_gen_left(g), uy, COL_W, ROW_H, "units", text=f"/g{SUBSCRIPT_L}{_sub(g + 1)}"))
            if self.tile_open("units", "ssprimes"):
                for p in range(self.dL):
                    self.cells.append(CellBox(f"urow:ssprimes:{p}", self.ss_prime_left(p), uy, COL_W, ROW_H, "units", text=f"/p{_sub(p + 1)}"))
            if self.tile_open("units", "commas"):
                for c in range(self.nv_shown):  # over all of V = C|U (each sub-column dimensionless)
                    self.cells.append(CellBox(f"urow:commas:{c}", self.comma_left(c), uy, COL_W, ROW_H, "units", text="/1"))
            if self.tile_open("units", "detempering"):  # each detempering generator is a ratio column
                for i in range(self.r):
                    self.cells.append(CellBox(f"urow:detempering:{i}", self.detempering_left(i), uy, COL_W, ROW_H, "units", text="/1"))
            if self.tile_open("units", "targets"):
                for j in range(self.k):
                    self.cells.append(CellBox(f"urow:targets:{j}", self.target_left(j), uy, COL_W, ROW_H, "units", text="/1"))
            if self.tile_open("units", "interest"):
                for ii in range(self.mi):
                    self.cells.append(CellBox(f"urow:interest:{ii}", self.interest_left(ii), uy, COL_W, ROW_H, "units", text="/1"))
            if self.tile_open("units", "held"):
                for ih in range(self.nh):
                    self.cells.append(CellBox(f"urow:held:{ih}", self.held_left(ih), uy, COL_W, ROW_H, "units", text="/1", alert=self.held_unheld[ih]))

        # quantities row: domain primes (+ controls) and target ratios (below the
        # tile's toggle head, like every other row's values). The whole row -- its
        # headers and the domain/comma ± controls riding it -- answers to the specific
        # "quantities" toggle, which drops it from row_y via its present flag.
        if "quantities" in self.row_y:
            qy = self.row_y["quantities"]

            def branch_minus(cid, ckey, i, kind, **kw):
                # a hover − centred on column ckey's i-th branch point (its top-bus split): the
                # zone occupies the fan-out gap ABOVE the header (where the revealed button parks),
                # COL_W wide on the sub-axis, frozen with the fan. It stops AT the header's top edge
                # — the header ratio is an editable input, and a covering z-index-4 zone would
                # swallow clicks into it. For an interval column the prominent drag grip overlays the
                # zone's TOP, so its button reveals at the zone's BOTTOM instead (CSS .rtt-minus-low).
                self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y, COL_W,
                                     qy - self.fanout_y, kind, **kw))

            def branch_plus(cid, ckey, kind):
                # the always-shown + centred on the column's stub, one slot past the last branch
                # point (the top bus stretches out to reach it); an empty set centres it on the trunk
                self.cells.append(CellBox(cid, self.plus_stub_x[ckey] - BTN / 2, self.fanout_y - BTN / 2, BTN, BTN, kind))

            if self.tile_open("quantities", "gens"):  # the generator ratios heading their sub-columns,
                for g in range(self.r):                # the column-header dual of the spine list (gen:i)
                    self.cells.append(CellBox(f"qgen:{g}", self.gen_left(g), qy, COL_W, ROW_H, "genratio", text=self.gens[g], gen=g))
                # the generators ± mirrors the mapping-row ± (same quantity, the generators): the + on
                # the column stub un-temps a comma (−n, +r, hold d), the − on the LAST generator's
                # branch point drops that row (+n, −r, hold d), removable when r > 1
                if self.r > 1:
                    branch_minus("gen_minus", "gens", self.r - 1, "gen_minus", gen=self.r - 1)
            if self.tile_open("quantities", "primes"):
                # with the nonstandard-domain box on the domain elements are typeable — an editable
                # elementcell (typing a rational relabels that basis element, holding the mapping
                # coordinates). Off, they're read-only domain primes walked by the ± only.
                for p in range(self.d):
                    # with the box on the element is editable: an integer prime shows as a plain number
                    # (elementcell), a nonprime as a stacked fraction face (elementratio) — matching its
                    # read-only display, and switching kind (so the cell rebuilds) across a relabel that
                    # crosses int↔fraction. Off, it's a read-only domain prime.
                    text = str(self.elements[p])
                    kind = self._element_cell_kind(text) if self.show_nonstandard_domain else "prime"
                    self.cells.append(CellBox(f"prime:{p}", self.prime_left(p), qy, COL_W, ROW_H, kind, text=text, prime=p))
                    self._voice("quantities:primes", p, self.tun.just_map[p])
                if self.element_draft:  # the red ?/? draft column: type a rational to add a new basis
                    # element (held just). A distinct id so it's removed, not restructured, on commit.
                    draft_text = self.pending_element or "?/?"
                    self.cells.append(CellBox("prime:pending", self.prime_left(self.d), qy, COL_W, ROW_H,
                                              self._element_cell_kind(draft_text), text=draft_text, prime=self.d, pending=True))
                    branch_minus("element_minus:pending", "primes", self.d, "element_minus")
                # Only the highest prime is removable (shrink_domain trims the last), so its
                # − rides that prime's branch point (the last top-bus split) — and only when the
                # shrink actually applies (gated like editor.shrink, never shown inert). With the
                # nonstandard-domain box on the domain is edited by typing, not prime-walked, so the
                # walk − is suppressed (the draft column carries its own − to cancel instead).
                if self.domain_can_shrink and not self.show_nonstandard_domain:
                    branch_minus("minus", "primes", self.d - 1, "minus")
            # the chapter-9 superspace columns' quantity headers (the dual of their spine basis
            # index): the rL superspace generators as ~ratios (read-only — derived from M_L) and
            # the dL superspace primes, the column-header twins of the gens / primes ratios above.
            # Derived bases carry no ± controls.
            if self.tile_open("quantities", "ssgens"):
                ss_gens = service.superspace_generators(self.state)
                for g in range(self.rL):
                    self.cells.append(CellBox(f"ssqgen:{g}", self.ss_gen_left(g), qy, COL_W, ROW_H, "genratio", text=ss_gens[g]))
            if self.tile_open("quantities", "ssprimes"):
                for p in range(self.dL):
                    self.cells.append(CellBox(f"ssqprime:{p}", self.ss_prime_left(p), qy, COL_W, ROW_H, "prime", text=str(self.superspace_primes[p]), prime=p))
            if self.tile_open("quantities", "commas"):
                for c in range(self.nc):
                    # the comma ratio is editable — a ratiocell, the scalar twin of the editable
                    # comma vector below it: typing a fraction re-parses to that comma's vector
                    self.cells.append(CellBox(f"comma:{c}", self.comma_left(c), qy, COL_W, ROW_H, "ratiocell", text=self.comma_ratios[c], comma=c))
                    self._voice("quantities:commas", c, self.comma_sizes.just[c])
                if self.pending is not None:  # the draft's editable "?/?" ratio: type a fraction to fill it
                    # (or its vector cells). A distinct id so it's removed, not restructured, on commit.
                    self.cells.append(CellBox("comma:pending", self.comma_left(self.nc), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=self.nc, pending=True))
                if self.show_unchanged:  # the unchanged-interval ratios complete V = C|U — read-only
                    for j in range(self.nu):  # (derived from the projection), the held primes "2/1", "5/1"
                        self.cells.append(CellBox(f"unchanged:{j}", self.comma_left(self.nc + j), qy, COL_W, ROW_H, "commaratio", text=self.unchanged_ratios[j], comma=self.nc + j))
                        self._voice("quantities:commas", self.nc + j, self.unchanged_sizes.just[j])
                # commas mirror the domain controls: + starts a (pending) comma; the − rides the
                # last column's branch point — cancelling the draft, or un-tempering a real comma,
                # down to the last one (which leaves just intonation, nullity 0 — nothing to remove).
                # Frozen under the consolidated V view, where the comma count can't change.
                if (self.pending is not None or self.nc > 0) and not self.show_unchanged:
                    branch_minus("comma_minus", "commas", self.nc_shown - 1, "comma_minus")
            if self.tile_open("quantities", "detempering"):  # the detempering generators as ratios (read-only,
                for i in range(self.r):                       # derived from M like the comma ratios — no ± control)
                    self.cells.append(CellBox(f"detempering:{i}", self.detempering_left(i), qy, COL_W, ROW_H, "commaratio", text=self.gens[i]))
                    self._voice("quantities:detempering", i, self.detempering_sizes.just[i])
            if self.tile_open("quantities", "targets"):
                # editable like the comma ratio (typing a fraction overrides the target set), but the
                # auto Tₚ = I list is the read-only computed twin of its vectors column (commaratio, as D)
                target_ratio_kind = "ratiocell" if self.targets_editable else "commaratio"
                for j in range(self.k):
                    self.cells.append(CellBox(f"target:{self.col_token('targets', j)}", self.target_left(j), qy, COL_W, ROW_H, target_ratio_kind, text=self.targets[j], comma=j))
                    self._voice("quantities:targets", j, self.target_sizes.just[j])
                    # each user-curated target carries its own − (like the intervals of interest); the
                    # auto-generated all-interval list (Tₚ = I) is not editable, so it carries none
                    if self.targets_editable:
                        branch_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
                if self.pending_target is not None:  # the draft column: an editable "?/?" ratio, blank red cells below, − to cancel
                    self.cells.append(CellBox("target:pending", self.target_left(self.k), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=self.k, pending=True))
                    branch_minus("target_minus:pending", "targets", self.k, "target_minus")
            if self.tile_open("quantities", "held"):  # the held intervals, edited like the intervals of interest
                for i in range(self.nh):
                    # the ratio heads each column and is editable too (a ratiocell, like the comma)
                    self.cells.append(CellBox(f"held:{self.col_token('held', i)}", self.held_left(i), qy, COL_W, ROW_H, "ratiocell", text=self.held_ratios[i], comma=i, alert=self.held_unheld[i]))
                    self._voice("quantities:held", i, self.held_sizes.just[i])
                    # each held interval carries its own − on its branch point (any one is removable)
                    branch_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
                if self.pending_held is not None:  # the draft column: an editable "?/?" ratio, blank red cells below, − to cancel
                    self.cells.append(CellBox("held:pending", self.held_left(self.nh), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=self.nh, pending=True))
                    branch_minus("held_minus:pending", "held", self.nh, "held_minus")
            if self.tile_open("quantities", "interest"):  # the user's other intervals of interest
                for i in range(self.mi):
                    # the ratio heads each column and is editable too (a ratiocell, like the comma)
                    self.cells.append(CellBox(f"interest:{self.col_token('interest', i)}", self.interest_left(i), qy, COL_W, ROW_H, "ratiocell", text=self.interest_ratios[i], comma=i))
                    self._voice("quantities:interest", i, self.interest_sizes.just[i])
                    # every interval carries its own − on its branch point: any one is removable,
                    # unlike the domain/comma last-only −
                    branch_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
                if self.pending_interest is not None:  # the draft column: an editable "?/?" ratio,
                    # blank red vector cells below, and a − on its branch point to cancel the draft
                    self.cells.append(CellBox("interest:pending", self.interest_left(self.mi), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=self.mi, pending=True))
                    branch_minus("interest_minus:pending", "interest", self.mi, "interest_minus")
            # the always-shown + on each addable column's stub (plus_stub_x has the entry exactly
            # when its emit gate held above — col_open for the empty-but-open interest/held sets, so
            # the first interval can still be added). The − is the hover counterpart on a branch point.
            # with the nonstandard-domain box on, the domain + starts a typed ?/? element draft
            # (element_plus → editor.add_element) rather than walking to the next prime (plus → expand)
            primes_plus = "element_plus" if self.show_nonstandard_domain else "plus"
            for ckey, cid in (("gens", "gen_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                              ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
                if ckey in self.plus_stub_x:
                    branch_plus(cid, ckey, cid)

            # drag-and-drop reorder grips: a ⠿ on each interval column, riding the GRIP_BAND room on
            # the fan — along the column's sub-axis gridline, in the band BETWEEN the − above (at the
            # branch point) and the first tile below. Each grip is BOTH the drag source AND a drop
            # target (drop one column's grip on another to move it there). EVERY list also emits a
            # drop-only zone at its stub gridline (its trunk when empty) — "grip:{list}:add" — so
            # dropping INTO a list is ALWAYS "drop on the gridline", identical whether the list is
            # full (drop on a column grip) or empty (drop on the lone trunk zone): no separate header
            # or + target. The grips sit above the freeze seam (the band is reserved within the frozen
            # fan), so the colhead doesn't clip them. A comma grip both drags one comma INTO another to
            # combine them (add_comma_to) and drags a comma OUT to another list to un-temper it — so
            # even a lone comma grips (dragging it out leaves just intonation, parity with the −). A
            # comma always accepts a drop (temper an interval in). The target list is inert in
            # all-interval (the auto Tₚ = I set isn't curated).
            grip_top = self.branch_top_y + GAP - PAD  # top of the reserved grip band (the old seam)

            def drag_controls(ckey, n):
                for i in range(n):  # a full-width ⠿ grip centred on the column's gridline, in the band
                    self.cells.append(CellBox(f"grip:{ckey}:{i}", self.sub_axis_x(ckey, i) - COL_W / 2,
                                         grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
                # the append / into-empty-list drop target, on the SAME band at the list's stub gridline
                # (the trunk when empty) — so an empty list still has a gridline target, like the grips.
                self.cells.append(CellBox(f"grip:{ckey}:add", self.plus_stub_x[ckey] - COL_W / 2,
                                     grip_top, COL_W, GRIP_BAND, "colgrip"))

            # gate on _plus_shows — the same "this list's fan (with its +) is visible" test the + uses.
            # Every list grips each existing column: even a sole comma drags out now (un-tempering it).
            counts = {"commas": self.nc, "targets": self.k, "held": self.nh, "interest": self.mi}
            for ckey in ("commas", "targets", "held", "interest"):
                if self._plus_shows(ckey):
                    drag_controls(ckey, counts[ckey])

        # generator ratios (aligned with the mapping rows they label) + the mapping
        # matrix and its mapped target interval list
        if self.row_open("mapping"):
            # the generators list the mapping's rows: a vertical ratio list in the
            # quantities spine column, labelling the rows as the primes label the columns
            if self.tile_open("mapping", "quantities"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"gen:{i}", self.col_x["quantities"], self.map_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.gens[i] if i < len(self.gens) else "", gen=i))
                # the mapping-row ± ride the row's LEFT bus (like the basis controls on the vectors
                # row), out to the left of the generator-ratio spine: a − on EACH generator's branch
                # point (any row removable, −r,+n), the + on the stub below the stack (un-temper a
                # comma, +r,−n). The − zone drops rightward over its generator ratio as the hover target.
                # The bus tracks row_axis's fanned left bus — node_edge + FAN even at rank 1 (the ET
                # case, where the lone-row band still fans to seat its + against the connecting bar).
                map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
                gen_right = self.col_x["quantities"] + self.col_w["quantities"]
                if self.r > 1:  # never down to rank 0
                    for i in range(self.r):
                        self.cells.append(CellBox(f"map_minus:{i}", map_bus_x, self.map_top(i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
                if "mapping" in self.row_plus_y:  # only when there's a comma to un-temper (n > 0)
                    self.cells.append(CellBox("map_plus", map_bus_x - BTN / 2, self.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))
            # a drag handle hugging the left of each mapping row: drag one generator row onto another
            # to ADD it into that row (a generator-basis change holding the temperament and tuning).
            # Needs ≥ 2 rows to combine; rides the reserved handle gutter to the LEFT of the row
            # labels (𝒎ᵢ), the leftmost slot of the widened primes column. (The column-reorder
            # handles a sibling concern adds ride the branch points up top — deliberately separate.)
            if self.settings.get("drag_to_combine") and self.r > 1 and self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"map_drag:{i}", self.primes_x, self.map_top(i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))
            for i in range(self.r):
                if self.tile_open("mapping", "primes"):
                    for p in range(self.d):
                        # text carries the mapping entry into the CellBox content (like the comma /
                        # target / held / interest vector cells already do) so changed_cell_ids sees a
                        # mapping change — otherwise the edit preview is blind to the matrix a
                        # temperament swap or a +/- rewrites. The input still shows it via _update_mapping.
                        self.cells.append(CellBox(f"cell:mapping:{i}:{p}", self.prime_left(p), self.map_top(i), COL_W, ROW_H, "mapping", text=str(self.state.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("mapping", "primes", gen=i, prime=p)))
                if self.tile_open("mapping", "targets"):
                    for j in range(self.k):
                        self.cells.append(CellBox(f"cell:mapped:{i}:{self.col_token('targets', j)}", self.target_left(j), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.mapped[i][j]), gen=i, unit=self.cell_unit("mapping", "targets", gen=i)))
                if self.tile_open("mapping", "interest"):  # interest mapped through M, like the targets
                    for ii in range(self.mi):
                        self.cells.append(CellBox(f"cell:imapped:{i}:{self.col_token('interest', ii)}", self.interest_left(ii), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.interest_mapped[i][ii]), gen=i, unit=self.cell_unit("mapping", "interest", gen=i)))
                if self.tile_open("mapping", "held"):  # held mapped through M, like the targets / interest
                    for hi in range(self.nh):
                        self.cells.append(CellBox(f"cell:hmapped:{i}:{self.col_token('held', hi)}", self.held_left(hi), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.held_mapped[i][hi]), gen=i, unit=self.cell_unit("mapping", "held", gen=i), alert=self.held_unheld[hi]))
                # the comma basis mapped through M — it vanishes to 0 (parallel to the
                # mapped target list); the raw basis lives in the interval-vectors row.
                # Over V the unchanged basis maps too (M·U ≠ 0 — the held intervals in gen coords).
                if self.tile_open("mapping", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:mapped_comma:{i}:{c}", self.comma_left(c), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.mapped_commas[i][c]), gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
                    for j in range(self.nu):
                        self.cells.append(CellBox(f"cell:mapped_unchanged:{i}:{j}", self.comma_left(self.nc + j), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.unchanged_mapped[i][j]), gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))

        # the projection matrix P = GM: a d×d operator over the domain primes, a stack of read-only
        # maps like the mapping. Its cells are "mapped" (a computed value, not editable like the
        # mapping's), carrying the rational entry text ("1", "0", "1/4") service stringified.
        if self.row_open("projection") and self.tile_open("projection", "primes"):
            for i in range(self.d):
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj:{i}:{p}", self.prime_left(p), self.proj_top(i),
                                         COL_W, ROW_H, "mapped", text=self.projection_matrix[i][p], prime=p))
        # the generator embedding G = H(MH)⁻¹ (d×r), beside P in the gens columns: its columns are
        # the held tuning's generators as fractional vectors. Read-only ("mapped") cells like P, but
        # over the r generator columns rather than the d primes (rows are the d primes, like P).
        if self.row_open("projection") and self.tile_open("projection", "gens"):
            for i in range(self.d):
                for g in range(self.r):
                    self.cells.append(CellBox(f"cell:embed:{i}:{g}", self.gen_left(g), self.proj_top(i),
                                         COL_W, ROW_H, "mapped", text=self.embedding_matrix[i][g], gen=g))

        # the scaling factors λ = diag(λ): the projection's eigenvalue list over the V column —
        # 0 for each comma sub-column (vanished, eigenvalue 0) then 1 for each unchanged
        # sub-column (held, eigenvalue 1). Read-only computed values ("mapped"), one ROW_H list.
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            scaling = [0] * self.nc + [1] * self.nu
            for c, lam in enumerate(scaling):
                self.cells.append(CellBox(f"cell:scaling:{c}", self.comma_left(c), self.row_y["scaling_factors"],
                                     COL_W, ROW_H, "mapped", text=str(lam), comma=c))

        # the canonical-mapping form box: M in canonical form (defactored + HNF), a stack of
        # read-only maps over the primes, framed like the mapping matrix one row above it; the
        # generator form matrix F (units 𝒈/𝒈) rides its gens column as a bordered r×r grid
        if self.row_open("canon"):
            if self.tile_open("canon", "primes"):
                for i in range(self.rc):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:canon:{i}:{p}", self.prime_left(p), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapping[i][p])))
            if self.tile_open("canon", "gens"):
                for i in range(len(self.form_M)):
                    for j in range(len(self.form_M)):
                        self.cells.append(CellBox(f"cell:form:{i}:{j}", self.gen_left(j), self.canon_top(i), COL_W, ROW_H, "formcell", text=str(self.form_M[i][j])))

        # interval-vectors row: each column's intervals as vectors (d-tall columns over
        # the domain primes), on the same prime/comma/target axes as the quantities row.
        # The comma basis is the editable raw vectors (the mapping's dual); the targets
        # become a d x k matrix of vector columns.
        if self.row_open("vectors"):
            # the domain basis lists the interval-vectors' rows: the d primes as boxed
            # COL_W squares (the same the quantities row heads its columns with) stacked
            # down the quantities spine — the dual index, as the generators label the
            # mapping rows. Its domain ± controls ride the row's LEFT bus, out to the left of
            # the primes (the row mirror of the columns' top-bus controls): a + on the stub
            # one ROW_H below the stack, and a − on the bottom prime's branch point.
            if self.tile_open("vectors", "quantities"):
                bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2  # square, centred in the spine
                for p in range(self.d):
                    self.cells.append(CellBox(f"basis:{p}", bx, self.vec_top(p), COL_W, ROW_H, "prime", text=str(self.elements[p]), prime=p))
                # the left bus the controls ride (node_edge + FAN when the row fans — matching
                # row_axis); the − zone drops from it rightward over the bottom prime as the hover target
                basis_bus_x = self.node_edge + self.FAN if self._row_fans("vectors") else self.node_edge
                if self.domain_can_shrink:  # the highest prime is removable only when the shrink applies
                    self.cells.append(CellBox("basis_minus", basis_bus_x, self.vec_top(self.d - 1),
                                         (bx + COL_W) - basis_bus_x, ROW_H, "basis_minus"))
                if self.standard_domain:  # the basis + walks the next standard prime (row_plus_y set to match)
                    self.cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, self.row_plus_y["vectors"] - BTN / 2,
                                         BTN, BTN, "plus"))
            if self.tile_open("vectors", "commas"):
                for c in range(self.nc):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:comma:{p}:{c}", self.comma_left(c), self.vec_top(p), COL_W, ROW_H, "commacell", text=str(self.state.comma_basis[c][p]), prime=p, comma=c, unit=self.cell_unit("vectors", "commas", prime=p)))
                        self._voice("vectors:commas", c, self.comma_sizes.just[c])
                # the unchanged basis U completes V = C|U: read-only vector columns ("vec", like the
                # detempering D), the projection's eigenvalue-1 eigenvectors held just (e.g. 2/1, 5/1)
                for j in range(self.nu):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:unchanged:{p}:{j}", self.comma_left(self.nc + j), self.vec_top(p), COL_W, ROW_H, "vec", text=str(self.unchanged_basis[j][p]), prime=p, comma=self.nc + j, unit=self.cell_unit("vectors", "commas", prime=p)))
                    self._voice("vectors:commas", self.nc + j, self.unchanged_sizes.just[j])
                if self.pending is not None:  # the draft column: blank, red-outlined cells the user fills in
                    for p in range(self.d):
                        v = self.pending[p]
                        self.cells.append(CellBox(f"cell:comma:{p}:{self.nc}", self.comma_left(self.nc), self.vec_top(p), COL_W, ROW_H, "commacell",
                                             text="" if v is None else str(v), prime=p, comma=self.nc, pending=True, unit=self.cell_unit("vectors", "commas", prime=p)))
            if self.tile_open("vectors", "targets"):
                # the target interval list as vector columns — an EDITABLE hybrid input like the comma
                # basis (typing a column overrides the target set) — except the auto Tₚ = I list, which
                # is read-only, the computed twin of its quantities ratio (a plain "vec", like D)
                target_kind = "targetcell" if self.targets_editable else "vec"
                # the list is a matrix drawn WITH separator rules between its columns; an editable
                # input's opaque box, flush at the slot boundary, would paint over the thin rule. So
                # the editable cells are inset within their COL_W slot (like the interest kets, KET_INSET)
                # — leaving a gap the separator shows through — while the read-only Tₚ vecs stay full
                # COL_W (no covering box, so they abut their column separators).
                cell_inset = KET_INSET if self.targets_editable else 0
                for j in range(self.k):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:vec:targets:{self.col_token('targets', j)}:{p}", self.target_left(j) + cell_inset, self.vec_top(p), COL_W - 2 * cell_inset, ROW_H, target_kind, text=str(self.target_vectors[j][p]), prime=p, comma=j, unit=self.cell_unit("vectors", "targets", prime=p)))
                        self._voice("vectors:targets", j, self.target_sizes.just[j])
                if self.pending_target is not None:  # the draft column: blank, red-outlined cells the user fills in
                    for p in range(self.d):
                        v = self.pending_target[p]
                        self.cells.append(CellBox(f"cell:vec:targets:{self.pending_col_token('targets')}:{p}", self.target_left(self.k) + cell_inset, self.vec_top(p), COL_W - 2 * cell_inset, ROW_H, "targetcell",
                                             text="" if v is None else str(v), prime=p, comma=self.k, pending=True, unit=self.cell_unit("vectors", "targets", prime=p)))
            if self.tile_open("vectors", "held"):  # the held intervals as editable vectors, like the intervals of interest
                for i in range(self.nh):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:held:{p}:{self.col_token('held', i)}", self.held_left(i), self.vec_top(p), COL_W, ROW_H, "heldcell", text=str(self.held[i][p]), prime=p, comma=i, unit=self.cell_unit("vectors", "held", prime=p), alert=self.held_unheld[i]))
                        self._voice("vectors:held", i, self.held_sizes.just[i])
                if self.pending_held is not None:  # the draft column: blank, red-outlined cells the user fills in
                    for p in range(self.d):
                        v = self.pending_held[p]
                        self.cells.append(CellBox(f"cell:held:{p}:{self.pending_col_token('held')}", self.held_left(self.nh), self.vec_top(p), COL_W, ROW_H, "heldcell",
                                             text="" if v is None else str(v), prime=p, comma=self.nh, pending=True, unit=self.cell_unit("vectors", "held", prime=p)))
            if self.tile_open("vectors", "detempering"):  # the matrix D, one vector column per generator
                for i in range(self.r):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:vec:detempering:{i}:{p}", self.detempering_left(i), self.vec_top(p), COL_W, ROW_H, "vec", text=str(self.detempering_vectors[i][p]), unit=self.cell_unit("vectors", "detempering", prime=p)))
                        self._voice("vectors:detempering", i, self.detempering_sizes.just[i])
            if self.tile_open("vectors", "interest"):  # the user's intervals of interest: editable vectors, like the comma basis
                for i in range(self.mi):
                    for p in range(self.d):
                        # inset within the COL_W slot (centred) so each ket is its own box with a
                        # gap to its neighbours — the interest column is a collection, not a matrix
                        self.cells.append(CellBox(f"cell:interest:{p}:{self.col_token('interest', i)}", self.interest_left(i) + KET_INSET, self.vec_top(p), COL_W - 2 * KET_INSET, ROW_H, "interestcell", text=str(self.interest[i][p]), prime=p, comma=i, unit=self.cell_unit("vectors", "interest", prime=p)))
                        self._voice("vectors:interest", i, self.interest_sizes.just[i])
                if self.pending_interest is not None:  # the draft column: blank, red-outlined cells the user fills in
                    for p in range(self.d):
                        v = self.pending_interest[p]
                        self.cells.append(CellBox(f"cell:interest:{p}:{self.pending_col_token('interest')}", self.interest_left(self.mi) + KET_INSET, self.vec_top(p), COL_W - 2 * KET_INSET, ROW_H, "interestcell",
                                             text="" if v is None else str(v), prime=p, comma=self.mi, pending=True, unit=self.cell_unit("vectors", "interest", prime=p)))
            # the drag-to-combine handles ride the band above the column labels (one per interval
            # entry): drag one interval onto another in the same column to ADD it in (their product).
            # Gated on the feature + ≥ 2 entries; targets only when the list is editable (not Tₚ = I).
            if "vectors" in self.row_int_handle_top:
                hy = self.row_int_handle_top["vectors"]
                for group, count, col_left, ckey in (("comma", self.nc, self.comma_left, "commas"),
                                                     ("target", self.k, self.target_left, "targets"),
                                                     ("held", self.nh, self.held_left, "held"),
                                                     ("interest", self.mi, self.interest_left, "interest")):
                    if count >= 2 and self.tile_open("vectors", ckey) and (ckey != "targets" or self.targets_editable):
                        for i in range(count):
                            self.cells.append(CellBox(f"int_drag:{group}:{i}", col_left(i), hy, COL_W, ROW_HANDLE_W, "int_drag", comma=i))

        # the chapter-9 superspace interval-vectors row's spine basis index: the dL
        # superspace primes stacked down the quantities spine column, one per row — the
        # row counterpart of the d domain primes that head the existing vectors row's spine
        # (basis:p cells). Phase 3 reserves the band; Phase 4 populates the matrix tiles
        # (B_L over the domain primes, commas/targets as superspace vectors).
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2  # square, centred in the spine
            for p in range(self.dL):
                self.cells.append(CellBox(f"ss_basis:{p}", bx, self.ss_vec_top(p), COL_W, ROW_H,
                                          "prime", text=str(self.superspace_primes[p]), prime=p))
        # the chapter-9 superspace MAPPING row's spine: the rL superspace generators as a
        # vertical ratio list down the quantities spine — the row counterpart of the on-domain
        # mapping spine (the gen:i generators that label M's rows), here labelling M_L's rows.
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "quantities"):
            ss_gens = service.superspace_generators(self.state)
            for i in range(self.rL):
                self.cells.append(CellBox(f"ss_gen:{i}", self.col_x["quantities"], self.ss_map_top(i),
                                          self.col_w["quantities"], ROW_H, "genratio",
                                          text=ss_gens[i] if i < len(ss_gens) else ""))
        # B_L (basis-embedding matrix): each domain element as a dL-tall vector of integer
        # vector coefficients over the superspace primes. The cells form a dL × d grid sharing
        # the prime-column gridlines with the existing vectors row above (the same prime_left
        # x-axis, the ss_vec_top y-axis) — a read-only "vec" cell per (ss_prime_row, element_col).
        # service.basis_in_superspace stores ROWS-as-elements (matching the comma-basis storage
        # convention), so the (ss_prime_row, element_col) entry is basis[element_col][ss_prime_row].
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "primes"):
            basis = service.basis_in_superspace(self.elements)
            for ss_prime_idx in range(self.dL):
                for elem_idx in range(self.d):
                    value = basis[elem_idx][ss_prime_idx]
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}",
                        self.prime_left(elem_idx), self.ss_vec_top(ss_prime_idx), COL_W, ROW_H,
                        "vec", text=str(value), prime=ss_prime_idx, comma=elem_idx,
                        unit=self.cell_unit("ss_vectors", "primes", prime=ss_prime_idx, elem=elem_idx),
                    ))
        # M_L (superspace mapping): the rL × dL covector stack the temperament lifts to over its
        # superspace primes. Sits in (ss_mapping, ssprimes), each row a covector over the dL
        # ss_primes — read-only "mapped" cells (the kind the canonical-form row and mapped-target
        # tiles use), since M_L is DERIVED from M via the basis embedding B_L; the user edits the
        # on-domain M and M_L follows. Editable "mapping" cells would crash the renderer too —
        # _update_mapping reads state.mapping[cb.gen][cb.prime], and rL can exceed r / dL exceed d.
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            ml = service.superspace_mapping(self.state)
            for gen_idx in range(self.rL):
                for ss_prime_idx in range(self.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}",
                        self.ss_prime_left(ss_prime_idx), self.ss_map_top(gen_idx), COL_W, ROW_H,
                        "mapped", text=str(ml[gen_idx][ss_prime_idx]),
                        gen=gen_idx, prime=ss_prime_idx,
                        unit=self.cell_unit("ss_mapping", "ssprimes", gen=gen_idx, prime=ss_prime_idx),
                    ))
        # ── the rest of the chapter-9 superspace block: the two new rows mirror the on-domain
        # vectors / mapping rows, lifted into the superspace. First the "new × new" tiles.
        # M_jL = I at (ss_vectors, ssprimes): the superspace JI mapping, a dL × dL identity
        # (each superspace prime is its own basis element) — a covector stack like M_L.
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            mjl = service.superspace_just_mapping(self.superspace_primes)
            for i in range(self.dL):
                for j in range(self.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_vectors:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_vec_top(i), COL_W, ROW_H,
                        "mapped", text=str(mjl[i][j]), gen=i, prime=j,
                        unit=self.cell_unit("ss_vectors", "ssprimes", prime=j)))
        # M_LgL = I at (ss_mapping, ssgens): the superspace mapping over its OWN generators, an
        # rL × rL identity (each superspace generator maps to itself) — the gen-space M_jL.
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            mlgl = service.superspace_self_map(self.state)
            for i in range(self.rL):
                for j in range(self.rL):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:ssgens:{i}:{j}",
                        self.ss_gen_left(j), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(mlgl[i][j]), gen=i,
                        unit=self.cell_unit("ss_mapping", "ssgens", gen=i)))
        # M_s→L at (ss_mapping, primes): the rL × d mapping straight from domain intervals to
        # superspace-generator coordinates (M_L · B_L) — a covector stack over the domain elements.
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            msl = service.mapping_to_superspace_generators(self.state)
            for i in range(self.rL):
                for e in range(self.d):
                    self.cells.append(CellBox(
                        f"cell:ss_mapping:primes:{i}:{e}",
                        self.prime_left(e), self.ss_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(msl[i][e]), gen=i,
                        unit=self.cell_unit("ss_mapping", "primes", gen=i, elem=e)))
        # the interval lists, lifted. Each on-domain list (commas C, targets T, held H, interest,
        # detempering D) becomes dL-tall vector columns over the superspace primes in the ss_vectors
        # row (B_L · column), and rL-tall mapped columns over the superspace generators in the
        # ss_mapping row (M_s→L · column — mapped commas vanish to 0, like the on-domain mapped
        # comma basis). Same column axes as the on-domain vectors / mapping rows above.
        ss_lists = (("commas", self.state.comma_basis, self.nc, self.comma_left),
                    ("targets", self.target_vectors, self.k, self.target_left),
                    ("held", self.held, self.nh, self.held_left),
                    ("interest", self.interest, self.mi, self.interest_left),
                    ("detempering", self.detempering_vectors, self.r, self.detempering_left))
        for ckey, vectors, n, left in ss_lists:
            cols = tuple(vectors)[:n]
            if self.row_open("ss_vectors") and self.tile_open("ss_vectors", ckey):
                lifted = service.lift_vectors_to_superspace(self.elements, cols)
                for c in range(len(lifted)):
                    for p in range(self.dL):
                        self.cells.append(CellBox(
                            f"cell:ss_vectors:{ckey}:{p}:{c}", left(c), self.ss_vec_top(p),
                            COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                            unit=self.cell_unit("ss_vectors", ckey, prime=p)))
            if self.row_open("ss_mapping") and self.tile_open("ss_mapping", ckey):
                mapped = service.map_vectors_into_superspace_generators(self.state, cols)
                for c in range(len(mapped)):
                    for g in range(self.rL):
                        self.cells.append(CellBox(
                            f"cell:ss_mapping:{ckey}:{g}:{c}", left(c), self.ss_map_top(g),
                            COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                            unit=self.cell_unit("ss_mapping", ckey, gen=g)))
        # M_jL (superspace JI mapping): the dL × dL identity. Each superspace prime is its
        # own basis element, so the just mapping is trivially I. Same read-only "mapped" kind
        # and bracket convention as M_L; lives in its own row band ss_just_mapping below it.
        # Units b/b — each cell's row dimension is the i-th basis element, its column the
        # j-th, both subscripted via cell_unit. (Two prime subscripts on one unit don't
        # collide because cell_unit subscripts ALL b's; the row index would only differ on
        # an off-diagonal entry, and M_jL is the identity.)
        if self.row_open("ss_just_mapping") and self.tile_open("ss_just_mapping", "ssprimes"):
            mjl = service.superspace_just_mapping(self.superspace_primes)
            for i in range(self.dL):
                for j in range(self.dL):
                    self.cells.append(CellBox(
                        f"cell:ss_just_mapping:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_just_map_top(i), COL_W, ROW_H,
                        "mapped", text=str(mjl[i][j]),
                        gen=i, prime=j,
                        unit=self.cell_unit("ss_just_mapping", "ssprimes", prime=j),
                    ))

        # tuning rows over the primes, commas and targets (cents); each can collapse on
        # its own. Commas sit on the same footing as targets — they are just the dual
        # interval set. Math expressions only ADDS the exact closed form where one exists
        # (a "mathexpr" kind prefixing the cents value); a cell with no closed form is
        # untouched — it keeps its plain cents cell. Math expressions never removes a
        # value, bracket, caption or tile: those are governed by quantities/gridded/names.
        # Charts track tiles: a charted row (retuning/weight/damage) draws a bar chart over
        # EVERY tile it shows. tuning_value_row — the one place a charted row's value cells are emitted
        # — records each tile it draws here, and a single loop below charts them all. So a
        # column joining a charted row is charted automatically (no per-column chart() call to
        # forget), and a chart can never drift from the values beneath it.
        self.chart_tiles = []  # (row, col, values) per open value tile of a charted row
        chart_indicators = {}  # (row, col) -> (indicator, label); only the damage chart carries one

        # the comma-column size lists run over the consolidated V = C|U when projection is on:
        # the comma sizes then the unchanged-interval sizes (the empty unchanged tuples no-op off
        # projection). Same geometry as the comma column's, so tuning_value_row places each at
        # comma_left(i) over the d V sub-columns.
        tuning_data = {
            "tuning": (self.tun.tuning_map, self.comma_sizes.tempered + self.unchanged_sizes.tempered, self.target_sizes.tempered, self.interest_sizes.tempered, self.held_sizes.tempered),
            "just": (self.tun.just_map, self.comma_sizes.just + self.unchanged_sizes.just, self.target_sizes.just, self.interest_sizes.just, self.held_sizes.just),
            "retune": (self.tun.retuning_map, self.comma_sizes.errors + self.unchanged_sizes.errors, self.target_sizes.errors, self.interest_sizes.errors, self.held_sizes.errors),
        }
        for key, (prime_vals, comma_vals, target_vals, interest_vals, held_vals) in tuning_data.items():
            if self.row_open(key):
                self.tuning_value_row(key, "primes", prime_vals)
                self.tuning_value_row(key, "commas", comma_vals)
                self.tuning_value_row(key, "targets", target_vals)
                self.tuning_value_row(key, "interest", interest_vals)
                self.tuning_value_row(key, "held", held_vals, alerts=self.held_unheld)
        # the generator tuning map: the tuning row's map over the generators (the gens-column
        # counterpart of the tuning map over the primes). Its cells are EDITABLE (a hybrid input):
        # typing a cents value overrides that generator's tuning, like typing the whole map in the
        # plain text. The genmap has no closed form, so they are plain editable cells (never mathexpr).
        # Under the prime-based superspace shift, though, the optimization lives over 𝒈L, so 𝒈 is the
        # read-only PROJECTION of the editable 𝒈L (ssgens, below) — its cells go plain tuning value.
        if self.row_open("tuning") and self.tile_open("tuning", "gens"):
            gen_kind = "tuningvalue" if self.show_superspace_generators else "gentuningcell"
            for i, v in enumerate(self.tun.generator_map):
                self.cells.append(CellBox(f"tuning:gen:{i}", self.group_left["gens"](i), self.row_y["tuning"], COL_W, ROW_H,
                                     gen_kind, text=service.cents(v), unit=self.cell_unit("tuning", "gens", gen=i)))
                self._voice("tuning:gens", i, v)  # the genmap sounds each generator's tuned size
        # the chapter-9 superspace tuning row: 𝒈ₗ over the ssgens column, 𝒕ₗ / 𝒋ₗ / 𝒓ₗ over ssprimes.
        # In the prime-based approach the optimization IS over the superspace generators, so 𝒈L is the
        # EDITABLE generator map (gentuningcell, the editing 𝒈 gave up above) — a manual 𝒈L freezes
        # via service.superspace_tuning's generator_override and projects down to drive 𝒈 and every
        # on-domain map. In neutral the superspace is only a complexity lens, so 𝒈L stays read-only.
        if self.show_superspace and self.row_open("tuning"):
            ss_override = self.superspace_generator_tuning if self.show_superspace_generators else None
            ss_tun = service.superspace_tuning(self.state, self.tuning_scheme, self.nonprime_approach,
                                               generator_override=ss_override)
            if self.tile_open("tuning", "ssgens"):
                if self.show_superspace_generators:  # editable 𝒈L cells (the prime-based live map)
                    for i, v in enumerate(ss_tun.generator_map):
                        self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"](i), self.row_y["tuning"],
                                             COL_W, ROW_H, "gentuningcell", text=service.cents(v),
                                             unit=self.cell_unit("tuning", "ssgens", gen=i)))
                        self._voice("tuning:ssgens", i, v)
                else:
                    self.tuning_value_row("tuning", "ssgens", ss_tun.generator_map)
            self.tuning_value_row("tuning", "ssprimes", ss_tun.tuning_map)
            if self.row_open("just"):
                self.tuning_value_row("just", "ssprimes", ss_tun.just_map)
            if self.row_open("retune"):
                self.tuning_value_row("retune", "ssprimes", ss_tun.retuning_map)
        # the detempering column's size rows: tempering the detempering intervals recovers the
        # generators, so its tuning row IS the generator tuning map (𝒕D = 𝒈); its just and
        # retuning sizes are ordinary interval lists (𝒋D, 𝒓D), the latter charted like the targets.
        if self.show_detempering:
            for key, values in (("tuning", self.detempering_sizes.tempered),
                                ("just", self.detempering_sizes.just),
                                ("retune", self.detempering_sizes.errors)):
                if self.row_open(key):
                    self.tuning_value_row(key, "detempering", values)

        # the prescaling row applies the prescaler 𝐿 to each column group's vectors: over the
        # primes it is the d×d diagonal (𝐿·eₚ — the prescaler matrix itself), over the comma /
        # target / interest sets it is 𝐿·vector (each component scaled by the diagonal), a d-tall
        # matrix per group like the interval-vectors row. Rendered as int/frac gridded cells.
        #
        # SUPERSPACE SHIFT (neutral / prime-based over a nonprime domain, self.show_superspace):
        # log-product complexity is measured in the prime superspace, so the whole row lifts to dL
        # rows. The bare 𝐿 moves one column LEFT into ss-primes as the (superspace) complexity
        # prescaler (the dL×dL log-prime diagonal over the TRUE primes); the domain-primes tile
        # becomes 𝐿·B_Ls, the prescaled subspace basis elements (each domain element lifted through
        # the basis-embedding B_L, then prescaled); and every product 𝐿·v is taken over the lifted
        # vector B_L·v. The displayed cells are exactly the operand the corrected get_complexity
        # norms — ‖𝐿·(B_L·v)‖ — so the tiles and the optimization stay in lockstep.
        nrows = self.prescale_rows
        if self.show_superspace:
            prescaler_diag = service.superspace_complexity_prescaler(self.state, self.tuning_scheme)
            prescaler_is_matrix = False
            ss_elements = service.superspace_primes(self.elements)
            _lift = lambda vs: service.lift_vectors_to_superspace(self.elements, vs)
            prescale_vectors = {
                # the bare (superspace) prescaler 𝐿: identity columns over the dL true primes
                "ssprimes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                # 𝐿·B_Ls: each domain element as a dL superspace vector (B_L's rows ARE these columns)
                "primes": service.basis_in_superspace(self.elements),
                # over V the prescaler scales the unchanged basis too (its held intervals)
                "commas": _lift(self.state.comma_basis) + (_lift(self.unchanged_basis) if self.show_unchanged else ()),
                "targets": _lift(self.target_vectors),
                "interest": _lift(self.interest),
                "held": _lift(self.held),
                "detempering": _lift(self.detempering_vectors),
            }
            groups = ("ssprimes", "primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "ssprimes"  # the diagonal bare-prescaler column (was "primes" off-superspace)
        else:
            prescaler_diag = self.prescaler
            prescaler_is_matrix = self.prescaler_is_matrix
            ss_elements = self.elements
            prescale_vectors = {
                "primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
                # over V = C|U the prescaler scales the unchanged basis too (its held intervals)
                "commas": self.state.comma_basis + (self.unchanged_basis if self.show_unchanged else ()),
                "targets": self.target_vectors,
                "interest": self.interest,
                "held": self.held,
                "detempering": self.detempering_vectors,
            }
            groups = ("primes", "commas", "targets", "interest", "held", "detempering")
            bare_group = "primes"
        # the active prescaler's per-prime diagonal term, lifted as the math-expression
        # operand: log-prime puts ``log₂{prime}`` on the diagonal, prime puts ``{prime}``
        # itself, identity puts a constant ``1`` — and ``1`` IS the value, so the cell would
        # be ``coeff · 1 = coeff`` (no information added). Following the just row's rule
        # (math expressions only where a non-trivial closed form exists), the identity
        # scheme is read as "no closed form" → cells stay tuning value. Over the superspace the
        # operands are the TRUE primes (ss_elements), so 𝐿·B_Ls's 13/5 column reads −log₂5 + log₂13.
        if self._scheme_prescaler == "log-prime":
            prime_term = {i: f"log₂{p}" for i, p in enumerate(ss_elements)}
        elif self._scheme_prescaler == "prime":
            prime_term = {i: str(p) for i, p in enumerate(ss_elements)}
        else:  # "identity" — coeff · 1 is silly, skip mathexpr (cell stays tuning value)
            prime_term = {}
        for group in groups:
            if not self.tile_open("prescaling", group):
                continue
            left = self.group_left[group]
            for c, vec in enumerate(prescale_vectors[group]):
                # the bare prescaler's columns ARE the (super)space primes, so each column's unit
                # subscripts its p by that prime (oct/pᵢ) — like the mapping's /p denominator. The
                # other groups (incl. 𝐿·B_Ls) scale a vector set, plain octaves (no per-column p).
                u = self.cell_unit("prescaling", group, prime=c if group == bare_group else None)
                # the prescaled vector 𝑋·v: a diagonal pretransformer multiplies element-wise (𝐿ᵢvᵢ);
                # a non-diagonal one (the editable square's matrix override) is a matrix-vector product
                prescaled = ([sum(prescaler_diag[i][k] * vec[k] for k in range(nrows)) for i in range(nrows)]
                             if prescaler_is_matrix
                             else [prescaler_diag[i] * vec[i] for i in range(nrows)])
                for i in range(nrows + self.size_rows):
                    # the nrows prescaled rows are (𝑋·v)ᵢ; the extra size row (i == nrows, present only
                    # with the size factor) is the guide's size-sensitizing row, sf·Σ(𝑋·v) (= sf·log₂ size)
                    value = prescaled[i] if i < nrows else self.size_factor * sum(prescaled)
                    cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
                    cx, cy = left(c), self.row_y["prescaling"] + i * ROW_H
                    # held column: a prescaled held interval the tuning no longer holds reddens too
                    # (the editable 𝐋 diagonal below is primes-only, so it never carries this flag)
                    alert = self.held_unheld[c] if group == "held" else False
                    # the bare pretransformer's EDITABLE cells are prescalercells — the input boxes the
                    # user types overrides into — and win over the math-expression closed form. The
                    # diagonal is always editable; with alt complexity the WHOLE top square is, so a
                    # non-diagonal pretransformer can be hand-entered (off the diagonal it reads 0 until
                    # touched). Without alt complexity the off-diagonal stays a pinned-0 tuning value. Every
                    # 𝑋·basis product (𝑋C/𝑋D/…) is computed, not editable — math_expressions still
                    # styles a non-zero coefficient with its closed form, a zero one staying tuning value.
                    # The superspace bare 𝐿 is display-only (editing the superspace prescaler isn't
                    # wired into the lifted optimization yet), so it skips the prescalercell branch.
                    if i < nrows and not self.show_superspace and group == "primes" and (i == c or self.show_alt_complexity):
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "prescalercell",
                                             text=service.prescale_text(value), prime=i, unit=u))
                    elif i < nrows and self.show_math and vec[i] != 0 and i in prime_term:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "mathexpr",
                                             text=_prescale_math_expr(vec[i], prime_term[i], value, self.show_quantities), unit=u, alert=alert))
                    else:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue",
                                             text=service.prescale_text(value), unit=u, alert=alert))
        if self.lbox_ctrl:  # box 𝐋's lone alt.-complexity control: the "replace diminuator" checkbox,
            # in a bordered box at the bottom of the prescaling matrix (the prescaler chooser is a preset
            # now, riding the preset band above). A SQUARE (no inline label — it wraps broken in the narrow
            # primes column) over its "replace diminuator" caption hugging its bottom.
            box_top = self.tile_top["prescaling"] + self.tile_h["prescaling"] - self.lbox_extra + RANGE_GAP
            bx, by = self.control_region("block:diminuator", "ssprimes" if self.show_superspace else "primes",
                                         box_top, OPTION_BOX_PX + CAPTION_LINE)
            self.cells.append(CellBox("control:diminuator", bx, by, LBOX_DIM_W, OPTION_BOX_PX,
                                 "control_check", text="",  # square only; label moves to a caption below
                                 checked=service.diminuator_replaced(self.tuning_scheme)))
            self.cells.append(CellBox("caption:diminuator", bx, by + OPTION_BOX_PX, LBOX_DIM_W,
                                 CAPTION_LINE, "caption", text="replace diminuator"))
        if self.cbox_ctrl:  # box 𝒄's three controls sit on one row in a bordered box at the bottom of the
            # complexity list: [predefined complexities ▼] | q | dual(q). The dropdown's caption hugs its
            # bottom; q and dual(q) use the optimization box's value-over-symbol-over-caption stack — the
            # value cell stays at COL_W (a standard gridded number), but the symbol/caption sit in
            # a wider overhanging SLOT so "dual(q)" doesn't overflow and multi-word captions wrap
            # readable. dual(q) only appears in all-interval mode (the dual norm power is
            # meaningful via the dual-norm inequality used to minimax over every interval).
            box_top = self.tile_top["complexity"] + self.tile_h["complexity"] - self.cbox_extra + RANGE_GAP
            tx, cy = self.control_region("block:complexity", "targets", box_top, ROW_H + SYMBOL_H + 3 * CAPTION_LINE)
            sym_y = cy + ROW_H
            cap_y = sym_y + SYMBOL_H
            cap_h = 3 * CAPTION_LINE
            slot_w = CBOX_SLOT_W
            q_slot_x = tx  # 𝑞 leads the row when the predefined-complexities preset is hidden (presets off)
            # the predefined-complexities master dropdown — a PRESET, so it rides the presets layer (like
            # the predefined-prescalers preset) on top of box 𝒄's weighting gate. The dropdown stores the
            # short internal key ("lp", "copfr", …) but presents the inverted-form display name
            # ("lp (log-product)", …). While alt. complexity is OFF (the default) it offers ONLY the
            # current complexity (lp for every scheme today); turning alt. complexity ON opens the full
            # preset list + the inert "custom" (shown when the fine controls leave the shape off-preset).
            # The caption hugs its bottom (rather than bottom-aligning with the q/dual captions further
            # down). With the dropdown hidden, 𝑞 takes its leftmost slot so the box hugs the q/dual pair.
            if self.show_presets:
                drop_w = CBOX_DROP_W
                complexity_key = service.complexity_name_of(self.tuning_scheme)
                # the prescaler is one of the complexity's defining controls (box 𝐋), so a hand-edited
                # prescaler diagonal/matrix that deviates from any named prescaler (realized is None)
                # leaves the complexity shape off-preset too — the chooser shows "custom", matching the
                # prescaler chooser's own "-". (complexity_name_of sees only the scheme, not the override.)
                if self._realized_prescaler is None:
                    complexity_key = "custom"
                complexity_text = service.COMPLEXITY_DISPLAYS.get(complexity_key, complexity_key)
                complexity_values = ((tuple(service.COMPLEXITY_DISPLAYS.values()) + ("custom",))
                                     if self.show_alt_complexity else (complexity_text,))
                # with alt. complexity off the list is just the live measure (one option) → no real
                # choice, so the dropdown + caption render disabled/greyed (the single-option rule the
                # presets use, and the look the all-interval-locked slope chooser already uses)
                complexity_locked = self._is_sole_option(complexity_values, complexity_text)
                self.cells.append(CellBox("control:complexity", tx, cy, drop_w, PRESET_H,
                                     "control_select", text=complexity_text, values=complexity_values,
                                     disabled=complexity_locked))
                self.cells.append(CellBox("caption:complexity", tx, cy + PRESET_H, drop_w,
                                     CAPTION_LINE, "caption", text="predefined complexities",
                                     align="left", disabled=complexity_locked))
                q_slot_x = tx + drop_w + OPT_COL_GAP
            # the interval-complexity norm power 𝑞, styled to match the optimization box's 𝑝 field (a
            # slot wider than the value cell, value centred, so the italic 𝑞 and the multi-word caption
            # render without overflow). 𝑞 is an ALTERNATE-complexity control — typing a new value
            # switches the scheme's Lq complexity — so it is an editable powerinput only when alt.
            # complexity is on; otherwise the complexity (hence 𝑞) is fixed and it renders as a read-only
            # powerdisplay (the same face, no white box), exactly like the all-interval-locked power 𝑝.
            q_x = q_slot_x + (slot_w - COL_W) / 2
            q_text = _format_power(service.complexity_norm_power(self.tuning_scheme))
            q_kind = "powerinput" if self.show_alt_complexity else "powerdisplay"
            self.cells.append(CellBox("control:q", q_x, cy, COL_W, ROW_H, q_kind, text=q_text))
            self.cells.append(CellBox("symbol:q", q_slot_x, sym_y, slot_w, SYMBOL_H, "symbol", text="𝑞"))
            self.cells.append(CellBox("caption:q", q_slot_x, cap_y, slot_w, cap_h, "caption",
                                 text="interval complexity norm power"))
            # the q field always shows with box 𝒄 (the dropdown above rides the presets layer); dual(q)
            # is gated separately — meaningful only when the scheme is all-interval (its checkbox is on)
            if service.is_all_interval(self.tuning_scheme):
                dual_slot_x = q_slot_x + slot_w + OPT_COL_GAP
                dual_x = dual_slot_x + (slot_w - COL_W) / 2
                dual_text = _format_power(service.dual_norm_power(self.tuning_scheme))
                # dual(q) is DERIVED from q (never edited), so it always renders as a read-only
                # powerdisplay: the same face as q — ∞ at the same visual size as the q numeral — minus
                # the white box (an editable-looking box for a value you can't edit was the old wart).
                self.cells.append(CellBox("control:dual", dual_x, cy, COL_W, ROW_H, "powerdisplay", text=dual_text))
                self.cells.append(CellBox("symbol:dual", dual_slot_x, sym_y, slot_w, SYMBOL_H,
                                     "symbol", text="dual(𝑞)"))
                self.cells.append(CellBox("caption:dual", dual_slot_x, cap_y, slot_w, cap_h, "caption",
                                     text="dual norm power"))
        if self.row_open("complexity"):  # 𝒄 over every interval set: a map over primes, lists elsewhere
            for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
                # the comma list runs over V = C|U when projection is on (the unchanged intervals'
                # complexities append to the commas'); the empty tuple no-ops off projection
                values = self.complexities[group] + (self.unchanged_complexities if group == "commas" else ())
                self.tuning_value_row("complexity", group, values,
                              alerts=self.held_unheld if group == "held" else ())
            # the superspace shift's "next row": the prime complexity map moves into the ss-primes
            # column (‖𝐿[i]‖q = each true prime's own diagonal weight), while the domain-primes tile
            # above keeps self.complexities["primes"] — now the SUBSPACE basis element complexity map
            # (each domain element's complexity, prime-factored through B_L, per the corrected
            # get_complexity). The two captions are swapped in _resolve_prescaler_labels.
            if self.show_superspace and self.tile_open("complexity", "ssprimes"):
                self.tuning_value_row("complexity", "ssprimes",
                              service.superspace_complexity_prescaler(self.state, self.tuning_scheme))
        if self.row_open("weight") and self.tile_open("weight", "targets"):
            # the weight is always a per-target list (it scales the targets, like damage). The all-
            # interval simplicity weight that has no concrete diagonal form (the size factor / a non-
            # diagonal 𝑋) still renders as this list — it just shows the generic 𝒘 = 𝒄⁻¹ symbol and per-
            # column cₙ⁻¹ headers instead of the concrete diag(𝐿)⁻¹ equivalence, never a matrix.
            self.tuning_value_row("weight", "targets", self.target_weights)
        if self.slope_ctrl:  # box 𝒘's weight-slope chooser (U/S/C), in a bordered box at the bottom of the
            # weight list, with its "damage weight slope" caption beneath (the optimization box's caption pattern)
            box_top = self.tile_top["weight"] + self.tile_h["weight"] - self.slope_extra + RANGE_GAP
            bx, by = self.control_region("block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
            slope_w = self.col_w["targets"] - 2 * BOX_INNER  # the chooser fills the box, inset off its border
            self.cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                                 "control_select", text=service.weight_slope_of(self.tuning_scheme),
                                 values=tuple(service.WEIGHT_SLOPES), disabled=self.slope_locked))
            self.cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                                 slope_w, CAPTION_LINE, "caption",
                                 text="damage weight slope", align="left", disabled=self.slope_locked))
        if self.row_open("damage"):  # damage is over the targets only (the tuning's own column)
            self.tuning_value_row("damage", "targets", self.target_sizes.damage)
            # optimization adds the horizontal minimized-damage indicator (the mean damage ⟪𝐝⟫ₚ
            # the tuning minimizes) across the damage chart, labelled with the scheme's Lp power
            # (∞ / 2 / 1); off, the chart is plain bars. Recorded for the chart loop below.
            if self.show_optimization:
                power = self.displayed_mean_damage_power()  # 𝑝 target-based; dual(𝑞) all-interval (the
                # aggregation power the optimizer minimized at — NOT the ∞ the 𝑝 cell shows all-interval)
                chart_indicators[("damage", "targets")] = (
                    _power_mean(self.target_sizes.damage, power), _format_power(power))

        # Draw a bar chart over every tile a charted row recorded (see chart_tiles above):
        # one pass, so the set of charts always equals the set of charted-row value tiles.
        for rkey, ckey, values in self.chart_tiles:
            indicator, label = chart_indicators.get((rkey, ckey), (None, ""))
            self.chart(rkey, ckey, values, indicator=indicator, indicator_label=label)

        # The generator tuning-ranges chart nests at the BOTTOM of the generator tuning map
        # tile (below its values and caption), a per-generator [min, max] I-beam (octave held
        # pure, so the period generator pins to a point) under the selected mode, diamond-
        # monotone or -tradeoff. Gated on the tuning_ranges toggle; the tile's own panel is
        # extended to enclose it (see gtm_extra in the panel loop), so it sits inside the tile
        # rather than floating. The monotone range can be None (no monotone tuning exists),
        # passed as () so the chart draws a placeholder rather than I-beams. gtm_chart/gtm_extra
        # were computed up front (so the tuning row could reserve the box's height).
        gtm_box = None  # (x, y, w, h) of the bordered box framing the title, chart + selector
        if self.gtm_chart:
            chosen = self.tun.monotone_generator_range if self.range_mode == "monotone" else self.tun.tradeoff_generator_range
            gx, gw = self.col_x["gens"], self.col_w["gens"]
            # the box nests below the tile's values + caption (tile_h now includes gtm_extra
            # for the box itself, so back it out to find the values' bottom); a left-aligned
            # boxtitle tops it (like every control box), then the chart, then the mode selector
            cy = self.tile_top["tuning"] + self.tile_h["tuning"] - self.gtm_extra + RANGE_GAP
            self.cells.append(CellBox("rangetitle:tuning:gens", gx, cy, gw, BOX_TITLE_H, "boxtitle",
                                 text="tuning ranges", align="left"))
            chart_y = cy + BOX_TITLE_H + BOX_TITLE_GAP
            self.cells.append(CellBox("rangechart:tuning:gens", gx, chart_y, gw, RANGE_CHART_H, "rangechart",
                                 ranges=tuple(chosen) if chosen is not None else (),
                                 values=tuple(self.tun.generator_map)))  # the live tuning, marked within each range
            self.cells.append(CellBox("rangemode:tuning:gens", gx, chart_y + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                                 "rangemode", text=self.range_mode))
            gtm_box = (gx, cy, gw, BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)

        # the optimization box, nested at the BOTTOM of the target interval damage list tile (the
        # tuning's own column, whose damages it minimizes): a bordered box titled "optimization",
        # spanning the FULL width of the tile (like the tuning-ranges box) and DISTRIBUTING three
        # controls across it — the minimized-damage mean damage (a read-only gridded value over ⟪𝐝⟫ₚ)
        # hugging the left, the optimize button (over its "double-click to lock" hint) hugging the
        # right, and the editable power (the ∞ cell over 𝑝 over "optimization power") centered in the
        # gap between them, so its caption has clear room either side. The min-damage and ∞ are plain
        # COL_W gridded cells (contents centred). The damage tile's panel grows by opt_extra to enclose
        # the box's height, and the targets column is floored to OPT_BOX_MIN_W (see _control_floor) so
        # the spread-out controls always fit.
        opt_box = None  # (x, y, w, h) of the bordered frame around the optimization controls
        approach_frame = None  # (x, y, w, h) of the bordered frame around the approach box
        self.approach_box = None  # (x, y, w, h) the approach radio is positioned over (None ⇒ hidden)
        if self.opt_ctrl:
            ox = self.col_x["targets"]
            box_w = self.col_w["targets"]                 # the box spans the full width of the damage tile
            # the opt box sits at the very bottom of the tile (the approach box rides above it)
            box_top = (self.tile_top["damage"] + self.tile_h["damage"]
                       - self.opt_extra + RANGE_GAP)
            title_top = box_top + OPT_PAD_T          # inset below the box's top border (not on it)
            content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP  # a gap below the title
            sym_top = content_top + ROW_H            # the symbol/hint row, under the values
            cap_top = sym_top + SYMBOL_H             # the caption row, under the symbols
            cap_band = self.opt_cap_lines * CAPTION_LINE  # one line, or two when the wide mean damage wraps
            body_h = ROW_H + SYMBOL_H + cap_band + OPT_PAD_B  # value + symbol + caption band + pad
            # the three controls, distributed across the box: the mean damage column at the left, the
            # optimize button at the right, the power centered in the gap between them (so its caption
            # clears both neighbors). The mean damage's value/symbol/caption all centre on the column's
            # mid-line, so a wide symbol/caption overflows evenly and stays within the box.
            mean_damage_x = ox + OPT_PAD_L                       # the mean damage column's left edge
            mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2  # the COL_W value cell, centred in the column
            btn_x = ox + box_w - OPT_PAD_R - OPT_BTN_W
            pow_x = ((mean_damage_x + OPT_MEAN_DAMAGE_W) + btn_x) / 2 - COL_W / 2
            # the mean damage aggregates the damages at the power the optimizer MINIMIZED at — 𝑝 target-
            # based, dual(𝑞) all-interval (the ‖𝒓𝑋⁻¹‖ symbol's dual(𝑞) subscript). The 𝑝 cell below
            # keeps displayed_optimization_power() (∞ all-interval): power over intervals vs over primes.
            mean_damage = _power_mean(self.target_sizes.damage, self.displayed_mean_damage_power())
            power = _format_power(self.displayed_optimization_power())
            self.cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                                 text="optimization"))
            # the mean damage: the minimized-damage value (read-only, so unboxed — a plain centred gridded
            # value, the same COL_W cell as any damage value) over its symbol and a label caption, the
            # same value/symbol/caption stack as the power beside it.
            self.cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                                 text=service.cents(mean_damage)))
            # all-interval: the minimized mean damage IS the retuning magnitude ‖𝒓𝑋⁻¹‖ at the dual norm
            # power (the mockup's "becomes 'retuning magnitude'") — relabel the symbol, with dual(q) as
            # the norm subscript; its value already computes over the primes. The prescaler inverse
            # carries the live glyph (𝐿⁻¹ for the log-prime matrix, else generic 𝑋⁻¹).
            mean_damage_symbol = (f"‖𝒓{self.prescaler_symbol}⁻¹‖{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
                          if self.all_interval else "⟪𝐝⟫ₚ")
            # once the displayed tuning is the scheme's optimum, the value shown IS the minimized
            # mean damage, so wrap the symbol in min(…) (the mockup's "make ⟪𝐝⟫ₚ into min(⟪𝐝⟫ₚ)"); a
            # hand-edited tuning that deviates shows the bare symbol — its value is no longer the min.
            if self.tuning_optimized:
                mean_damage_symbol = f"min({mean_damage_symbol})"
            self.cells.append(CellBox("optimization:mean_damage:symbol", mean_damage_x, sym_top, OPT_MEAN_DAMAGE_W, SYMBOL_H,
                                 "symbol", text=mean_damage_symbol))
            # the caption naming the mean damage, the analogue of "optimization power": the Lp "power
            # mean" of the target damages, or the "retuning magnitude" when all-interval (so the label
            # tracks the symbol's relabel), prefixed "minimized" while the tuning is optimized. It
            # spans the mean damage column, centred on it, wrapping to the lines cap_band reserves.
            self.cells.append(CellBox("optimization:mean_damage:caption", mean_damage_x, cap_top, OPT_MEAN_DAMAGE_W, cap_band,
                                 "caption", text=self.mean_damage_caption))
            # the power: the ∞ cell (∞ minimax, 2 miniRMS, 1 miniaverage) — a COL_W gridded cell — over
            # the symbol 𝑝 and the caption "optimization power" (one line, centred under it). 𝑝 ≠ ∞ is an
            # ADVANCED choice (every preset is minimax), so 𝑝 is editable only with alt. complexity on;
            # off, the editor holds the scheme at minimax so it shows ∞ read-only. All-interval likewise
            # locks 𝑝 at ∞ (the solver minimaxes over every interval, ignoring the stored 𝑝). Either way
            # it renders as a read-only value (a powerdisplay — the SAME ∞-over-"(max)" stacked face as
            # the editable input, just no white box; its symbol/caption stay the normal value black).
            power_locked = self.all_interval or not self.show_alt_complexity
            self.cells.append(CellBox("optimization:power", pow_x, content_top, COL_W, ROW_H,
                                 "powerdisplay" if power_locked else "powerinput", text=power))
            self.cells.append(CellBox("optimization:power:symbol", pow_x, sym_top, COL_W, SYMBOL_H,
                                 "symbol", text="𝑝"))
            self.cells.append(CellBox("optimization:power:caption", pow_x + (COL_W - OPT_POW_CAP_W) / 2, cap_top,
                                 OPT_POW_CAP_W, CAPTION_LINE, "caption", text="optimization power"))
            # the optimize button: a normal ROW_H-tall rectangle wide enough to seat the "double-click
            # to unlock" hint on one line beneath it. It single-clicks to optimize once, double-clicks
            # to lock auto-optimize; app.py owns that behaviour + the lock visual. The hint names the
            # double-click's NEXT effect, so it flips to "unlock" while the auto-optimize lock is on.
            self.cells.append(CellBox("optimization:button", btn_x, content_top, OPT_BTN_W, ROW_H, "optimize",
                                 text="optimize"))
            self.cells.append(CellBox("optimization:button:hint", btn_x, sym_top, OPT_BTN_W, CAPTION_LINE,
                                 "caption", text=f"double-click to {'unlock' if self.optimize_locked else 'lock'}"))
            opt_box = (ox, box_top, box_w, OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + body_h)

        # the chapter-9 approach box: a bordered control box (the tuning-ranges / optimization style)
        # titled "nonstandard domain approach", framing the prime-based/nonprime-based/neutral square
        # radio. It rides the reserved approach_extra slice ABOVE the optimization box, spanning the
        # tile's full width like its siblings. A left-aligned boxtitle tops it (like every control
        # box); the radio itself is an interactive widget app.py owns, so here we emit the title and
        # publish approach_box (its target x/y/w/h) for render() to position the square radio over.
        if self.show_approach:
            ax = self.col_x["targets"]
            aw = self.col_w["targets"]
            box_top = (self.tile_top["damage"] + self.tile_h["damage"]
                       - self.opt_extra - self.approach_extra + RANGE_GAP)
            self.cells.append(CellBox("optimization:approach:title", ax, box_top, aw, BOX_TITLE_H, "boxtitle",
                                 text="nonstandard domain approach", align="left"))
            radio_top = box_top + BOX_TITLE_H + BOX_TITLE_GAP
            self.approach_box = (ax + OPT_PAD_L, radio_top,
                                 aw - OPT_PAD_L - OPT_PAD_R, APPROACH_RADIO_H)
            approach_frame = (ax, box_top, aw, BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H)

        if self.row_open("canon") and self.tile_open("canon", "primes"):  # canonical maps: ⟨ … ] per row
            for i in range(self.rc):
                self.bracket(f"canon:map:{i}", MAP_BRACKETS, "primes", self.canon_top(i), ROW_H)
        if self.row_open("canon") and self.tile_open("canon", "gens"):  # the generator form matrix: { … ] per row
            for i in range(len(self.form_M)):
                self.bracket(f"form:map:{i}", GENMAP_BRACKETS, "gens", self.canon_top(i), ROW_H)
        if self.row_open("projection") and self.tile_open("projection", "primes"):  # P = GM: ⟨ … ] per row, like the mapping
            for i in range(self.d):
                self.bracket(f"proj:{i}", MAP_BRACKETS, "primes", self.proj_top(i), ROW_H)
        if self.row_open("projection") and self.tile_open("projection", "gens"):  # G: { … ] per row, generator coords
            for i in range(self.d):
                self.bracket(f"embed:{i}", GENMAP_BRACKETS, "gens", self.proj_top(i), ROW_H)
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):  # λ: a [ … ] list over V
            self.bracket("scaling", LIST_BRACKETS, "commas", self.row_y["scaling_factors"], ROW_H)
        if self.row_open("mapping"):
            # the primes mapping is a stack of maps: ⟨ … ] per row
            if self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.bracket(f"map:{i}", MAP_BRACKETS, "primes", self.map_top(i), ROW_H)
            if self.tile_open("mapping", "commas"):  # the mapped (vanishing) comma basis: a [ ] over r rows
                self.bracket("mapped_comma", LIST_BRACKETS, "commas", self.row_y["mapping"], self.r * ROW_H, fit=True)
            if self.tile_open("mapping", "targets"):
                self.bracket("mapped", LIST_BRACKETS, "targets", self.row_y["mapping"], self.r * ROW_H, fit=True)
            # the interest mapped images stand alone (no outer [ … ]), mirroring the vectors row
            if self.nh and self.tile_open("mapping", "held"):  # held mapped list, like the targets / interest
                self.bracket("hmapped", LIST_BRACKETS, "held", self.row_y["mapping"], self.r * ROW_H, fit=True)
        # the chapter-9 superspace mapping M_L: a rL × dL covector stack over the ssprimes
        # column, framed exactly like M (per-row ⟨ … ] brackets + top/bottom matrix_frame)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            for i in range(self.rL):
                self.bracket(f"ss_map:{i}", MAP_BRACKETS, "ssprimes", self.ss_map_top(i), ROW_H)
        # M_jL = I: a dL × dL identity, framed identically to M_L (per-row ⟨ … ] + frame)
        if self.row_open("ss_just_mapping") and self.tile_open("ss_just_mapping", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_just_map:{i}", MAP_BRACKETS, "ssprimes",
                             self.ss_just_map_top(i), ROW_H)
        # the chapter-9 "new × new" tiles. M_jL = I at (ss_vectors, ssprimes): a dL × dL covector
        # stack ⟨ … ] like M_L. M_s→L at (ss_mapping, primes): rL covectors over the domain
        # elements. M_LgL = I at (ss_mapping, ssgens): the gen-space self-map, framed { … ] (the
        # generator dimension, like the canonical generator form F and the genmap).
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_vec_jmap:{i}", MAP_BRACKETS, "ssprimes", self.ss_vec_top(i), ROW_H)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            for i in range(self.rL):
                self.bracket(f"ss_msl:{i}", MAP_BRACKETS, "primes", self.ss_map_top(i), ROW_H)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            for i in range(self.rL):
                self.bracket(f"ss_selfmap:{i}", GENMAP_BRACKETS, "ssgens", self.ss_map_top(i), ROW_H)
        # the lifted interval lists: B_L over the primes column (the basis change matrix) and the
        # lifted C/T/H/detempering lists, each a [ … ] over the dL components in the ss_vectors row;
        # the mapped versions a [ … ] over the rL rows in the ss_mapping row (interest stands alone,
        # no outer wrap — mirroring the on-domain vectors / mapping rows).
        if self.row_open("ss_vectors"):
            # B_L the basis change matrix wraps in an OUTER ⟨ … ] (a covector-style bracket per
            # the mockup — distinct from the plain [ … ] of the lifted lists), its inner columns
            # the domain-element kets from vector_list_marks below
            if self.tile_open("ss_vectors", "primes"):
                self.bracket("ss_vec:primes", MAP_BRACKETS, "primes", self.row_y["ss_vectors"], self.dL * ROW_H, fit=True)
            for group in ("commas", "targets"):
                if self.tile_open("ss_vectors", group):
                    self.bracket(f"ss_vec:{group}", LIST_BRACKETS, group, self.row_y["ss_vectors"], self.dL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_vectors", "held"):
                self.bracket("ss_vec:held", LIST_BRACKETS, "held", self.row_y["ss_vectors"], self.dL * ROW_H, fit=True)
            if self.tile_open("ss_vectors", "detempering"):
                self.bracket("ss_vec:detempering", LIST_BRACKETS, "detempering", self.row_y["ss_vectors"], self.dL * ROW_H, fit=True)
        if self.row_open("ss_mapping"):
            for group in ("commas", "targets"):
                if self.tile_open("ss_mapping", group):
                    self.bracket(f"ss_mapped:{group}", LIST_BRACKETS, group, self.row_y["ss_mapping"], self.rL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_mapping", "held"):
                self.bracket("ss_mapped:held", LIST_BRACKETS, "held", self.row_y["ss_mapping"], self.rL * ROW_H, fit=True)
            if self.tile_open("ss_mapping", "detempering"):
                self.bracket("ss_mapped:detempering", GENMAP_BRACKETS, "detempering", self.row_y["ss_mapping"], self.rL * ROW_H, fit=True)
        if self.row_open("vectors"):  # each group is a list of vectors: a [ ] spanning the d components
            for group in ("commas", "targets"):
                if self.tile_open("vectors", group):
                    self.bracket(f"vec:{group}", LIST_BRACKETS, group, self.row_y["vectors"], self.d * ROW_H, fit=True)
            # the interest column is a loose collection, not a matrix — its kets stand alone,
            # so no outer [ … ] wraps them (see the de-matrixed mapped/imapped row below)
            if self.nh and self.tile_open("vectors", "held"):
                self.bracket("vec:held", LIST_BRACKETS, "held", self.row_y["vectors"], self.d * ROW_H, fit=True)
            if self.tile_open("vectors", "detempering"):
                self.bracket("vec:detempering", LIST_BRACKETS, "detempering", self.row_y["vectors"], self.d * ROW_H, fit=True)
        if self.row_open("prescaling"):  # 𝐿·basis matrices: outer brackets over the d-tall prescaled columns.
            # Each 𝐿·basis product (𝐿C/𝐿D/𝐿T/𝐿H) gets symmetric ``[ … ]`` left/right brackets
            # like the mapped lists; the interest tile (standalone columns) gets none. The bare
            # prescaler 𝐿 is the exception — its outer wrap is the matrix_frame top+bottom span
            # above (ebktop + ebkangle), not left/right brackets, mirroring the mapping's
            # construction (plain text ``[ … ⟩``).
            # the bare-prescaler column: the domain primes normally, but ss-primes once the superspace
            # shows (the bare 𝐿 moved there). The domain-primes tile is then 𝐿·B_Ls, a list like the
            # other products. Every product list grows to prescale_rows (dL over the superspace).
            ph = (self.prescale_rows + self.size_rows) * ROW_H
            bare_col = "ssprimes" if self.show_superspace else "primes"
            list_groups = [("commas", self.nc), ("detempering", self.r),
                           ("targets", self.k), ("held", self.nh)]
            for group, n_cols in list_groups:
                if n_cols and self.tile_open("prescaling", group):
                    self.bracket(f"prescaling:{group}", LIST_BRACKETS, group,
                            self.row_y["prescaling"], ph, fit=True)
            # 𝐿·B_Ls is the prescaled basis-change matrix, so it wraps ⟨ … ] like B_L (not the
            # symmetric [ … ] of the plain products); its per-column ket caps come from
            # vector_list_marks below, mirroring ss_vectors/primes.
            if self.show_superspace and self.tile_open("prescaling", "primes"):
                self.bracket("prescaling:primes", MAP_BRACKETS, "primes",
                        self.row_y["prescaling"], ph, fit=True)
            # the bare prescaler 𝐿 is mapping-style: per-row ⟨ … ] brackets, one pair per row (the size
            # factor adds one more, for the size row). Its outer top + bottom frame is the matrix_frame
            # call above (ebktop + ebkangle), which spans the grown matrix height and that same width.
            if self.tile_open("prescaling", bare_col):
                pspan = self.matrix_span(bare_col)
                for i in range(self.prescale_rows + self.size_rows):
                    self.bracket(f"prescaling:row:{i}", MAP_BRACKETS, bare_col,
                            self.row_y["prescaling"] + i * ROW_H, ROW_H, span=pspan)
                if self.size_rows:  # the guide's \hline in 𝑋 = 𝑍𝐿: a horizontal rule separating the bottom
                    # size row from the top square
                    gx, gw = pspan
                    self.cells.append(CellBox("bar:prescaling", gx, self.row_y["prescaling"] + self.prescale_rows * ROW_H - SEP_W / 2,
                                         gw, SEP_W, "hbar"))
        if self.tile_open("tuning", "gens"):  # the generator tuning map is framed { … ] (per the mockup)
            self.bracket("tuning:genmap", GENMAP_BRACKETS, "gens", self.row_y["tuning"], ROW_H)
        # the detempering tuning row IS the generator tuning map (𝒕D = 𝒈), so it too is framed
        # { … ]; its just/retune rows are ordinary interval lists, framed below with the rest
        if self.tile_open("tuning", "detempering"):
            self.bracket("tuning:detempering", GENMAP_BRACKETS, "detempering", self.row_y["tuning"], ROW_H)
        # the cyan superspace tuning row's 𝒈ₗ tile takes the same { … ] genmap shape as 𝒈
        # (a covector over the rL superspace generators); 𝒕ₗ / 𝒋ₗ / 𝒓ₗ over the ssprimes
        # column take the regular ⟨ … ] map brackets (covectors over the dL superspace primes).
        if self.tile_open("tuning", "ssgens"):
            self.bracket("tuning:ssgenmap", GENMAP_BRACKETS, "ssgens", self.row_y["tuning"], ROW_H)
        for key in ("tuning", "just", "retune", "complexity"):
            if self.row_open(key):
                if self.tile_open(key, "primes"):
                    self.bracket(f"{key}:map", MAP_BRACKETS, "primes", self.row_y[key], ROW_H)
                if self.tile_open(key, "commas"):
                    self.bracket(f"{key}:commalist", LIST_BRACKETS, "commas", self.row_y[key], ROW_H)
                if self.tile_open(key, "targets"):
                    self.bracket(f"{key}:list", LIST_BRACKETS, "targets", self.row_y[key], ROW_H)
                # the interest size rows carry NO bracket — the whole interest column is a bare
                # collection of standalone values, not a [ … ] list (per the mockup)
                if self.nh and self.tile_open(key, "held"):
                    self.bracket(f"{key}:hlist", LIST_BRACKETS, "held", self.row_y[key], ROW_H)
                # detempering's just/retune/complexity sizes are ordinary lists; its tuning row
                # is the genmap, bracketed { … ] above (so it's skipped here)
                if key != "tuning" and self.tile_open(key, "detempering"):
                    self.bracket(f"{key}:detemperinglist", LIST_BRACKETS, "detempering", self.row_y[key], ROW_H)
                # the chapter-9 superspace tuning cells over the ssprimes column: each row is a
                # covector over the dL ss_primes, ⟨ … ] like the primes column above (𝒕ₗ / 𝒋ₗ / 𝒓ₗ).
                # The complexity row joins them once the superspace shows: its ss-primes tile is the
                # prime complexity map ‖𝐿[i]‖q, a covector ⟨ … ] just like the domain-primes map.
                if (key != "complexity" or self.show_superspace) and self.tile_open(key, "ssprimes"):
                    self.bracket(f"{key}:ssprimes", MAP_BRACKETS, "ssprimes", self.row_y[key], ROW_H)
        if self.tile_open("weight", "targets"):
            self.bracket("weight", LIST_BRACKETS, "targets", self.row_y["weight"], ROW_H)
        if self.tile_open("damage", "targets"):
            self.bracket("damage", LIST_BRACKETS, "targets", self.row_y["damage"], ROW_H)

        # Matrix row + column labels (when symbols is on). A row-labelled tile is a
        # covector stack — the mapping 𝑀, the prescaler 𝑋 — and labels each row 𝒎ᵢ / 𝒙ᵢ
        # at the LEFT of the row's ⟨, inside the MATLABEL_W gutter reserved in the primes
        # column. Every other multi-cell tile labels its COLUMNS above each cell in the
        # MATLABEL_H band reserved at the top of the row's value band.
        if self.show_symbols:
            # the per-column group's count, so a tile's columns are iterated by its
            # (rkey, ckey) without re-deriving the loop bounds each time
            group_count = {"gens": self.r, "primes": self.d, "commas": self.nc + self.nu, "targets": self.k,
                           "held": self.nh, "detempering": self.r,
                           "ssgens": self.rL, "ssprimes": self.dL}
            # the y of the i-th row inside a row-labelled tile: the mapping stacks under
            # row_y["mapping"]; the prescaler stacks d rows under row_y["prescaling"]; the
            # chapter-9 superspace mapping M_L stacks rL rows under row_y["ss_mapping"]
            # the bare prescaler's covector rows stack under row_y["prescaling"]; once the superspace
            # shows it lives in the ss-primes column (prescale_rows = dL tall), else the domain primes
            # (d tall). Both keyed so row_labels (which targets whichever column is the bare prescaler)
            # always resolves.
            _prescale_top = lambda i: self.row_y["prescaling"] + i * ROW_H
            row_top = {
                ("mapping", "primes"): self.map_top,
                ("prescaling", "primes"): _prescale_top,
                ("prescaling", "ssprimes"): _prescale_top,
                ("ss_mapping", "ssprimes"): self.ss_map_top,
                ("ss_mapping", "primes"): self.ss_map_top,
                ("ss_just_mapping", "ssprimes"): self.ss_just_map_top,
            }
            row_count = {("mapping", "primes"): self.r,
                         ("prescaling", "primes"): self.prescale_rows + self.size_rows,
                         ("prescaling", "ssprimes"): self.prescale_rows + self.size_rows,
                         ("ss_mapping", "ssprimes"): self.rL,
                         ("ss_mapping", "primes"): self.rL,
                         ("ss_just_mapping", "ssprimes"): self.dL}
            for (rkey, ckey), glyph in self.row_labels.items():
                if not self.tile_open(rkey, ckey):
                    continue
                top = row_top[(rkey, ckey)]
                for i in range(row_count[(rkey, ckey)]):
                    # the bare pretransformer 𝑋 = 𝑍𝐿's bottom (size-sensitizing) row is labelled 𝒛 (the
                    # size-sensitizing matrix 𝑍's row variable), NOT 𝒍₄ / 𝒙₄ — it isn't a fourth prime.
                    size_row = rkey == "prescaling" and i == self.prescale_rows and self.size_rows
                    text = "𝒛" if size_row else f"{glyph}{_sub(i + 1)}"
                    self.cells.append(CellBox(
                        f"matlabel:row:{rkey}:{ckey}:{i}",
                        # past the drag-handle gutter (when present), so the handle sits to its left;
                        # the box fills the column's row-label gutter (wider in the superspace primes
                        # column, for M_s→L's 𝒎ₛ→ₗᵢ) so a wide label never overflows the ⟨ bracket
                        self.content_x[ckey] + self.handle_gutter_w(ckey), top(i),
                        self.matlabel_gutter_w(ckey), ROW_H,
                        "matlabel", text=text,
                    ))
            # column labels — one per cell of each col-labelled tile, in the band above
            # the top frame (so a framed matrix reads label / [bracket] / cells). A label
            # value is either a string (the bare glyph; the i+1 subscript is appended) or
            # a callable (i) → full label text, for tiles whose label has a richer form
            # than glyph+subscript (the complexity row's norm expressions). The prescaling/
            # complexity product-column labels carry the LIVE prescaler glyph (𝐿𝐜/𝐿𝐭/… or
            # 𝑋𝐜/𝑋𝐭/…) — matching the tile-symbol slot below — via col_labels.
            for (rkey, ckey), label in self.col_labels.items():
                if ckey not in group_count or rkey not in self.row_matlabel_top:
                    continue
                if not self.tile_open(rkey, ckey):
                    continue
                # the all-interval simplicity weight (size factor / non-diagonal 𝑋) heads each column with
                # the reciprocal of that column's complexity: wₙ = cₙ⁻¹ (the per-prime simplicity weight is
                # 1/the complexity) — the norm detail stays on the 𝒄 tile's own cₙ = ‖𝐿[n]‖q header, not
                # repeated here. Matches the list's generic tile symbol 𝒘 = 𝒄⁻¹ (no concrete diagonal).
                if (rkey, ckey) == ("weight", "targets") and self.all_interval_simplicity_weight:
                    label = self._weight_simplicity_header
                left = self.group_left[ckey]
                y = self.row_matlabel_top[rkey]
                for i in range(group_count[ckey]):
                    text = label(i) if callable(label) else f"{label}{_sub(i + 1)}"
                    self.cells.append(CellBox(
                        f"matlabel:col:{rkey}:{ckey}:{i}",
                        left(i), y, COL_W, MATLABEL_H,
                        "matlabel", text=text,
                    ))

        # Shared axes. A multi-element group is one line that fans out at the near end
        # (from its node) into one line per element, runs through the data, then fans
        # back in at the far end to a foot extending a touch past the data — pinched at
        # both ends, bulging through the middle. Collapsing converges the per-element
        # lines onto the centre and shrinks both buses to nothing, so the renderer
        # animates the merge into a single straight gridline.
        self.bot_bus_y = self.total_h - self.FAN

        # the columns that fan into one rule per element — recorded by column_axis as it runs, so
        # the spine loop below can skip EXACTLY these. A single source of truth: a fanned column
        # therefore can never ALSO be drawn a full-height centre trunk (which left a spurious
        # gridline down a 2+-element column when a hand-kept fan list drifted from these calls).
        self.fanned_columns = set()

        # every group column fans into one vertical sub-axis per element, derived from
        # group_left/group_elem/group_n (not a hand-kept call list) so a column with cells --
        # the generators column included -- can never be missed and left a lone centre spine.
        for key in self.group_left:
            self.column_axis(key, self.group_elem[key], self.group_n[key],
                        lambda i, k=key: self.group_left[k](i) + COL_W / 2)

        # every NON-fanning present column is a spine: a single full-height trunk rule. Both ends
        # are derived, not hand-kept — the columns come from col_x (so a column can never lack its
        # gridline) and the fanned ones are excluded via fanned_columns (filled by the column_axis
        # calls above), so a fanned column never doubles up a centre trunk on top of its fan. The
        # spines are just the quantities/units columns: each carries one index per row (a basis
        # square / generator ratio; a unit label), so there are no side-by-side cells to fan.
        for key in self.col_x:
            if key in self.fanned_columns:
                continue
            cx = self.col_x[key] + self.col_w[key] / 2
            self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.total_h - self.branch_top_y,
                     dotted=f"col:{key}" in self.collapsed)

        # A matrix row is the horizontal mirror of a group column: it fans out at the node into
        # one rule per cell-row, runs through the data, and rejoins on the right to a foot past it.
        # Whether a row fans is DERIVED (_row_fans) from its own cell-row count or a row + stub,
        # exactly as a column fans on its element count — NOT a hand-kept membership list. So ANY
        # multi-row tile (the mapping, vectors, the d×(d+1) prescaler 𝑋 = 𝑍𝐿, …) fans
        # automatically and a new one can never be left with a lone centre spine (the row-side of
        # the generators-column bug); so too does a SINGLE-row band that adds elements (a rank-1 ET
        # mapping), so its + rides a fanned bus with a connecting bar instead of floating off the
        # side. Sub-rules are keyed by the row (h:mapping:i, h:weight:i): unlike a column, whose
        # element type picks one column, several rows share an element type (vectors and prescaling
        # are both d primes tall), so the row key — not the element — is what keeps the ids unique.
        self.right_bus_x = self.total_w - self.FAN

        # one pass over the present rows (top to bottom): fan the rows that branch, give every other
        # single-row band one full-width rule. Derived from row_y + _row_fans, so a row can never lack
        # its gridline — present or collapsed (a folded row still leaves its rule, fanned or spine).
        for key in self.row_y:
            if self._row_fans(key):
                self.row_axis(key)
            else:
                self.gridline(f"h:{key}", "h", self.row_y[key] + self.row_h[key] / 2, self.node_edge, self.total_w - self.node_edge,
                         dotted=f"row:{key}" in self.collapsed)

        for bid, rkey, ckey in self.tiles:
            if (rkey, ckey) in self.declared_tiles:  # a dropped tile (e.g. all-interval's redundant ones) loses its panel too
                self.panel(bid, ckey, rkey)
        # the box-𝐋/𝒄/𝒘 control boxes, on top of the panels now (collected during the cell pass)
        self.blocks.extend(self._control_region_boxes)
        # the nested tuning-ranges box: a thin-bordered frame around the chart + selector,
        # appended after the tile panels so it layers on top of the generator tuning map tile
        if gtm_box is not None:
            self.blocks.append(Block("block:tuning:rangesbox", *gtm_box, boxed=True))
        # the optimization box's thin border, around its title + mean damage/power/button
        if opt_box is not None:
            self.blocks.append(Block("block:optimization:box", *opt_box, boxed=True))
        # the approach box's thin border, around its title + the square radio, above the opt box
        if approach_frame is not None:
            self.blocks.append(Block("block:optimization:approach:box", *approach_frame, boxed=True))

        if self.col_x and self.row_y:
            bands = []  # (id, x, y, w, h, group)
            for rkey, ckey in self.declared_tiles:
                if not self.tile_open(rkey, ckey):
                    continue
                groups = {g for g in self.tile_groups(rkey, ckey) if self.settings.get(f"{g}_colorization")}
                if not groups:
                    continue
                x, w = self.col_x[ckey] - WASH_PAD, self.col_w[ckey] + 2 * WASH_PAD
                y, h = self.tile_top[rkey] - WASH_PAD, self.tile_h[rkey] + 2 * WASH_PAD
                for group in groups:
                    bands.append((f"{group}:{rkey}:{ckey}", x, y, w, h, group))
            for bid, x, y, w, h, _ in bands:  # white bases (a layer below the colour bands)
                self.blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
            for bid, x, y, w, h, group in bands:  # the darken colour bands over them
                self.blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))

        # quantity symbol + name stacked inside each tile, below its values + bottom
        # frame: the symbol line (toggled by symbols) on top, the long-form name
        # (toggled by names) under it. Equivalences extends the symbol line with the
        # quantity's defining equation — the "= …" continuation appended to the glyph,
        # so it reads e.g. "𝒕 = 𝒈𝑀"; turning it on shows the glyph too (the equation's
        # left side) even when symbols itself is off. Within a symboled row the slot is
        # reserved for every captioned column so the names stay aligned; the glyph and
        # equation are drawn only where defined (the comma columns have none yet). An
        # empty interest column has no tiles. Mnemonics underlines the symbol letter.
        # The weight row's equation resolves per build from the live scheme's damage-weight slope
        # (𝒘 = 𝒄 / 𝟏 / 𝒄⁻¹ — the bold 𝟏 is the all-ones weight vector). The damage row names its
        # weight factor 𝒘 (a LIST, so 𝒘 — never diag(𝒘)) only while the weight row is on screen; with
        # weighting hidden it drops to 𝐝 = |𝐞| rather than dangle a reference to a row the reader can't
        # see. The bare prescaling tile is the only one whose SYMBOL equivalence names the live prescaler
        # concretely (``𝑋 = 𝐿`` for log-prime, ``𝑋 = diag(𝒑)`` / ``𝑋 = 𝐼`` otherwise, or nothing for a
        # typed override — see prescaler_equivalence). Its NAME additionally gains "= log-prime matrix"
        # when 𝑋 = 𝐿 (see effective_captions). The product tiles carry the live glyph as their SYMBOL
        # (𝐿C/…) and print no "= …".
        ai = service.is_all_interval(self.tuning_scheme)  # all-interval: kept target tiles use prime-proxy labels
        slope = service.damage_weight_slope(self.tuning_scheme)
        # the "𝑋 = 𝐿" symbol-equivalence rides the BARE prescaler tile — which sits in ss-primes
        # once the superspace shows (the domain-primes tile is then the 𝐿·B_Ls product, no "= …").
        equivalences = {**EQUIVALENCES,
                        ("weight", "targets"): WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                        ("prescaling", "ssprimes" if self.show_superspace else "primes"): self.prescaler_equivalence,
                        **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                        # the consolidated interval-vectors header: V = C|U (the comma basis and
                        # the unchanged basis concatenated)
                        **({("vectors", "commas"): " = C|U"} if self.show_unchanged else {})}
        if ai:
            # all-interval (Tₚ = I): the kept target tiles take prime-proxy closed forms in the live
            # prescaler glyph (X→L). The complexity list IS the prescaler diagonal; the (simplicity)
            # weight its reciprocal — diag(𝐿)⁻¹, more concrete than the slope's 𝒄⁻¹; the damage the
            # retuning-MAP magnitude times that weight — |𝒓|𝐿⁻¹ (there is no target error list 𝐞 here,
            # the retune row's 𝐞→𝒓). These need the live glyph, so they can't be static.
            if not self.prescaler_is_matrix and not self.size_factor:  # ONLY a plain diagonal 𝑋 has
                # 𝒄 = diag(𝑋). A non-diagonal 𝑋 has no diagonal; the SIZE FACTOR makes the lils complexity
                # ‖𝑍𝐿·i‖ ≠ diag(𝐿) (the size row doubles each prime) — so neither gets the diag equivalence.
                equivalences[("complexity", "targets")] = f" = diag({self.prescaler_symbol})"
                equivalences[("weight", "targets")] = f" = diag({self.prescaler_symbol})⁻¹"
            equivalences[("damage", "targets")] = f" = |𝒓|{self.prescaler_symbol}⁻¹"
            # the all-interval weight is the per-prime SIMPLICITY weight = reciprocal complexity. Only a
            # PLAIN diagonal 𝑋 gets the concrete diag(𝐿)⁻¹ above; the size factor / a non-diagonal 𝑋 break
            # that diagonal (as they do the complexity's diag(𝐿)), so the weight keeps the generic slope
            # form 𝒘 = 𝒄⁻¹ (set in the defaults), with its per-column cₙ⁻¹ headers spelling out each entry.
        if not self.show_weighting:  # the weight factor's row is hidden, so don't dangle it (𝒘 / 𝐿⁻¹)
            equivalences[("damage", "targets")] = " = |𝒓|" if ai else " = |𝐞|"
        for (rkey, ckey), name in self.effective_captions.items():
            if ckey == "interest" and not self.interest:
                continue
            if not self.tile_open(rkey, ckey):
                continue
            if ai and (rkey, ckey) in ALL_INTERVAL_CAPTIONS:  # the prime-proxy name (per the Guide)
                name = ALL_INTERVAL_CAPTIONS[(rkey, ckey)]
            cy = self.row_y[rkey] + self.row_h[rkey] + self.row_frame[rkey]
            if (self.show_symbols or self.show_equiv) and rkey in SYMBOLED_ROWS:
                equiv = equivalences.get((rkey, ckey), "") if self.show_equiv else ""
                base_symbol = self.prescaling_symbols.get((rkey, ckey), SYMBOLS.get((rkey, ckey), ""))
                if ai and (rkey, ckey) in ALL_INTERVAL_SYMBOLS:  # e.g. the target list T → Tₚ
                    base_symbol = ALL_INTERVAL_SYMBOLS[(rkey, ckey)]
                if self.show_unchanged and (rkey, ckey) == ("vectors", "commas"):  # C → V (the unrotated basis)
                    base_symbol = "V"
                glyph = base_symbol if (self.show_symbols or equiv) else ""
                if glyph or equiv:
                    self.cells.append(CellBox(f"symbol:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
                cy += SYMBOL_H
            if self.show_captions:
                kw = MNEMONICS.get((rkey, ckey)) if self.show_mnemonics else None
                underlines = ((name.index(kw), 1),) if (kw and kw in name) else ()
                if self.show_mnemonics and ai:  # all-interval subscript letters (Tₚ → the p's in prime/proxy)
                    underlines += tuple((name.index(w), 1)
                                        for w in ALL_INTERVAL_MNEMONICS.get((rkey, ckey), ()) if w in name)
                # the caption spans the row's whole caption band (row_cap — the tallest wrapped
                # name in the row), and the CSS centres the text within it. So a one-line name
                # sits centred (half a blank line above and below) against a two-line sibling,
                # rather than hugging the cells with all the slack below.
                self.cells.append(CellBox(f"caption:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], self.row_cap[rkey],
                                     "caption", text=name, underlines=underlines))
            # the "units: …" line sits below the caption band (independent of names/symbols),
            # reading the box's entry from tile_unit (UNITS, with the damage/weight/complexity
            # annotation resolved from the live scheme) — bold-upright unit glyphs via _math_html
            unit = self.tile_unit(rkey, ckey)
            # the on-domain coordinate p reads b (basis element) over a nonstandard subgroup —
            # consistently with the gridded cells and the units row/column, so the whole column
            # swaps together (the superspace tiles keep p, true primes; see cell_unit)
            if unit and not (rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")):
                unit = _subscript_coord(unit, "p", self.domain_label)
            if self.show_units and unit:
                uy = self.row_y[rkey] + self.row_h[rkey] + self.row_frame[rkey] + self.row_sym[rkey] + self.row_cap[rkey]
                self.cells.append(CellBox(f"units:{rkey}:{ckey}", self.col_x[ckey], uy, self.col_w[ckey], UNIT_H,
                                     "units", text=f"units: {unit}"))

        # preset chooser dropdowns, in the reserved band below each governing tile's
        # plain-text box. The tuning/target choosers carry the live selection; the
        # temperament chooser is a placeholder (it loads, not mirrors). These are controls,
        # so they ride the tile whether or not math expressions has emptied its values.
        if self.show_presets:
            # the tuning chooser shows the scheme's bare systematic name (rendered from its spec),
            # blank ("-") when the scheme has no systematic name. The prescaler chooser shows the
            # scheme's named prescaler, blank when a custom diagonal override deviates from it (the
            # bare prescaler tile's manual edits).
            preset_text = {"temperament": "", "target": self.target_spec,
                              "tuning": service.base_scheme_name(self.tuning_scheme) or "",
                              "prescaler": self._realized_prescaler or "",
                              "projection": self.displayed_projection_name or ""}

            def emit_preset(cid, name, rkey, ckey, label):
                if not self.tile_open(rkey, ckey):
                    return
                if self.size_factor:  # "predefined prescalers" → "…pretransformers" (guide terminology)
                    label = _pretransform_label(label)
                top = self.ptext_band_y(rkey) + self.row_ptext[rkey]  # below the plain-text band
                # a chooser with no real choice renders as a DISABLED dropdown (greyed, non-interactive,
                # caption greyed with it), like the all-interval-locked target / weight-slope choosers:
                #  - the target set scheme doesn't apply in all-interval (it targets every interval), and
                #  - a tuning / prescaler chooser locked to its single on-list option (e.g. the default
                #    T minimax-U / log-prime) — see _preset_locked.
                disabled = (name == "target" and service.is_all_interval(self.tuning_scheme)) \
                    or self._preset_locked(name)
                cx, cw, cy = self.control_box(f"block:{cid}", ckey, top, self.preset_cap(name), label,
                                              disabled=disabled)
                self.cells.append(CellBox(cid, cx, cy, cw, PRESET_H, "preset", text=preset_text[name],
                                     disabled=disabled))
                # the target chooser carries the all-interval checkbox to the dropdown's right, in the
                # empty space of its now-tile-spanning box (box 𝐓); TBOX_W floors the column wide enough.
                if name == "target" and self.settings["all_interval"]:
                    self.emit_all_interval_check(cx + cw + OPT_COL_GAP, cy)
                # the pretransformer chooser likewise carries the "replace diminuator" checkbox to its
                # right (box 𝐋), in one box; PBOX_W floors the column. With presets off it falls back to
                # its own box at the matrix bottom (lbox_ctrl), mirroring the all-interval checkbox.
                if name == "prescaler" and self.settings["alt_complexity"]:
                    self.emit_diminuator_check(cx + cw + OPT_COL_GAP, cy)

            for name, rkey, ckey, label in PRESETS:
                # the prescaler chooser (+ its "replace diminuator" checkbox) follows the bare
                # prescaler into the ss-primes column under the superspace shift
                if name == "prescaler" and self.show_superspace:
                    ckey = "ssprimes"
                emit_preset(f"preset:{name}", name, rkey, ckey, label)
            for name, rkey, ckey, label in PRESET_COPIES:  # the same control in a second tile
                # the tuning-scheme chooser under the generator map follows the editable genmap to
                # 𝒈L (ssgens) under the prime-based superspace shift
                if name == "tuning" and ckey == "gens" and self.show_superspace_generators:
                    ckey = "ssgens"
                emit_preset(f"preset:{name}:{ckey}", name, rkey, ckey, label)

        # the all-interval checkbox is revealed by the show-panel "all-interval" entry ALONE (not the
        # presets toggle). When the target chooser is shown, emit_preset seats the checkbox inside
        # the chooser's box (box 𝐓, above); when it is hidden the checkbox is the band's only target
        # control, alone at the column's left. The vectors row reserves the band either way.
        if self.settings["all_interval"] and not self.show_presets and self.tile_open("vectors", "targets"):
            top = self.ptext_band_y("vectors") + self.row_ptext["vectors"]
            self.emit_all_interval_check(self.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)

        # the form chooser, one box below the preset chooser: it canonicalizes the mapping /
        # comma basis it rides (an undoable edit). A control, so it ignores the value-display
        # toggles, like the preset choosers.
        if self.show_form_controls:
            for name, rkey, ckey, label in FORM_CHOOSERS:
                if not self.tile_open(rkey, ckey):
                    continue
                top = self.ptext_band_y(rkey) + self.row_ptext[rkey] + self.row_pre[rkey]  # below the preset box
                cx, cw, cy = self.control_box(f"block:formchooser:{name}", ckey, top, PRESET_W, label)
                self.cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser"))

        # plain-text value band: each tile's value as its natural EBK string, directly
        # below the symbol/caption stack (above the preset chooser). The two editable
        # duals (mapping, comma basis) render as inputs that drive the grid; every other
        # value is read-only. The app shrinks each box's font so the value fits one line.
        if self.show_ptext:
            for (rkey, ckey), text in self.ptext_strings.items():
                if not self.tile_open(rkey, ckey):
                    continue
                # an editable vector-list dual flips to a static two-tone box while its column has
                # a pending draft (the committed vectors black, the draft vector red — a single-
                # colour input can't do that): the comma basis when a comma is pending, the target
                # list when a target is. The mapping and read-only values keep their normal kinds.
                if (rkey, ckey) == ("vectors", "commas") and self.pending is not None \
                        or (rkey, ckey) == ("vectors", "targets") and self.pending_target is not None:
                    kind = "ptextpending"
                elif self.ptext_editable(rkey, ckey) and (ckey != "targets" or self.targets_editable):
                    kind = "ptextedit"  # the auto Tₚ = I list reads as static plain text, not an input
                else:
                    kind = "ptext"
                self.cells.append(CellBox(f"ptext:{rkey}:{ckey}", self.col_x[ckey], self.ptext_band_y(rkey),
                                     self.col_w[ckey], self.ptext_height(rkey, ckey), kind, text=text))
            # the quantities row's interval-ratio columns (commas, targets, held, detempering, …)
            # emit no per-column plain text: their gridded cell already shows the formatted ratio,
            # so a line repeating it would be a pure duplicate. Only the domain-primes column carries
            # a quantities-row plain text — "2.3.5", the compact prime-limit notation (from the
            # service seam above), which the gridded "2 3 5" cells don't show that way.

        self.matrix_frame("mapping", "primes", "primes")
        self.matrix_frame("projection", "primes", "proj")  # P = GM, framed like the mapping
        self.matrix_frame("projection", "gens", "embed", foot="ebkbrace")  # G, framed like the genmap
        self.matrix_frame("canon", "primes", "canon")
        self.matrix_frame("canon", "gens", "form")
        # the BARE prescaler 𝐿 reads exactly like the mapping in plain text — outer
        # ``[ … ⟩`` with per-row ``⟨ … ]`` covectors — so its gridded EBK uses the SAME
        # matrix_frame + per-row bracket pattern the mapping uses, just with an angle ⟩
        # (ebkangle) at the bottom-span instead of the curly } (ebkbrace). Once the superspace
        # shows, the bare 𝐿 lives in the ss-primes column (the domain-primes tile is the 𝐿·B_Ls
        # product, list-bracketed above), so frame that column instead.
        self.matrix_frame("prescaling", "ssprimes" if self.show_superspace else "primes", "prescaling", foot="ebkangle")
        # the chapter-9 superspace mapping M_L is M's parallel over the superspace primes,
        # framed the same way (top bracket + bottom curly brace spanning the rL × dL matrix)
        self.matrix_frame("ss_mapping", "ssprimes", "ss_mapping")
        # M_jL = I rides the same matrix-frame pattern over its own dL × dL identity band
        self.matrix_frame("ss_just_mapping", "ssprimes", "ss_just_mapping")
        # the chapter-9 "new × new" covector stacks: M_jL = I in the ss_vectors row, M_s→L over
        # the domain elements, and the gen-space self-map M_LgL = I — each framed like M_L
        self.matrix_frame("ss_vectors", "ssprimes", "ss_vec_jmap")
        self.matrix_frame("ss_mapping", "primes", "ss_msl")
        self.matrix_frame("ss_mapping", "ssgens", "ss_selfmap")

        self.vector_list_marks("mapping", "mapped_comma", "commas", self.comma_left, self.nc + self.nu)  # M·C then M·U over V
        self.vector_list_marks("mapping", "mapped", "targets", self.target_left, self.k)
        # the interest column's mapped images stand alone — no separator rules between columns
        self.vector_list_marks("mapping", "imapped", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("mapping", "hmapped", "held", self.held_left, self.nh)
        # the interval-vectors row holds raw (untempered) vectors, so every column is a
        # ket — angle ⟩ feet, not braces. The comma basis is the editable bordered grid
        # (commacell), so it skips the separator rules (its cell borders divide the columns);
        # nc_shown includes the pending draft column so it gets its ket marks too. The
        # interest column's intervals likewise stand alone (no separators between columns).
        self.vector_list_marks("vectors", "vec:commas", "commas", self.comma_left, self.nv_shown, foot="ebkangle", separators=False,
                         pending_col=(self.nc if self.pending is not None else -1))
        self.vector_list_marks("vectors", "vec:targets", "targets", self.target_left, self.k_shown, foot="ebkangle",
                         pending_col=(self.k if self.pending_target is not None else -1))
        self.vector_list_marks("vectors", "vec:interest", "interest", self.interest_left, self.mi_shown, foot="ebkangle", separators=False,
                         pending_col=(self.mi if self.pending_interest is not None else -1))
        self.vector_list_marks("vectors", "vec:held", "held", self.held_left, self.nh_shown, foot="ebkangle",
                         pending_col=(self.nh if self.pending_held is not None else -1))
        self.vector_list_marks("vectors", "vec:detempering", "detempering", self.detempering_left, self.r, foot="ebkangle")
        # the chapter-9 superspace lifted lists: B_L (the basis change matrix over the domain
        # elements) and the lifted C/T/H/detempering, each a matrix of kets (⌐ top, ∨ angle foot)
        # like the on-domain vectors row; interest stands alone (no separators). The mapped
        # versions in the ss_mapping row take curly-brace feet (} ) like the on-domain mapped lists.
        self.vector_list_marks("ss_vectors", "ss_vec:primes", "primes", self.prime_left, self.d, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:commas", "commas", self.comma_left, self.nc, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:targets", "targets", self.target_left, self.k, foot="ebkangle")
        self.vector_list_marks("ss_vectors", "ss_vec:held", "held", self.held_left, self.nh, foot="ebkangle")
        self.vector_list_marks("ss_vectors", "ss_vec:interest", "interest", self.interest_left, self.mi, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:detempering", "detempering", self.detempering_left, self.r, foot="ebkangle")
        self.vector_list_marks("ss_mapping", "ss_mapped:commas", "commas", self.comma_left, self.nc)
        self.vector_list_marks("ss_mapping", "ss_mapped:targets", "targets", self.target_left, self.k)
        self.vector_list_marks("ss_mapping", "ss_mapped:held", "held", self.held_left, self.nh)
        # 𝐿·B_Ls (the prescaled basis-change matrix in the domain-primes column once the superspace
        # shows): per-column ket caps over its dL-tall prescaled columns, exactly like B_L above
        if self.show_superspace:
            self.vector_list_marks("prescaling", "prescaling:primes", "primes", self.prime_left, self.d, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:interest", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:detempering", "detempering", self.detempering_left, self.r)
        # the prescaling row's per-column marks read off as the same EBK its plain-text uses.
        # Every 𝐿·basis product (𝐿C/𝐿D/𝐿T/𝐿H) and the interest tile is a matrix of prescaled
        # VECTORS, so each column is a ket ``[ … ⟩`` — top = ebktop (square open ⌐), foot =
        # ebkangle (angle/ket foot ∨) — the default vector_list_marks shape (no overrides). The
        # bare prescaler 𝐿 is the exception: it has NO per-column marks (its EBK is mapping-
        # style — see the matrix_frame + per-row ⟨ … ] bracket calls above).
        #
        # Separators between columns are drawn for 𝐿T and 𝐿H per the mockup; the 𝐿C / 𝐿D tiles
        # keep their columns spaced without dividing rules. Interest stays standalone (no outer
        # wrap, no separators).
        self.vector_list_marks("prescaling", "prescaling:commas", "commas", self.comma_left, self.nc + self.nu, foot="ebkangle", separators=False)  # 𝐿C then 𝐿U over V
        self.vector_list_marks("prescaling", "prescaling:detempering", "detempering", self.detempering_left, self.r, foot="ebkangle", separators=False)
        self.vector_list_marks("prescaling", "prescaling:targets", "targets", self.target_left, self.k, foot="ebkangle", separators=True)
        self.vector_list_marks("prescaling", "prescaling:held", "held", self.held_left, self.nh, foot="ebkangle", separators=True)
        self.vector_list_marks("prescaling", "prescaling:interest", "interest", self.interest_left, self.mi, foot="ebkangle", separators=False)

        # a per-tile fold toggle inset into each content tile's top-left corner: it
        # sits in the head strip reserved above the content, TOGGLE_INSET in from the
        # grey panel's top-left, so it never touches an edge or overlaps the frame.
        # Anchored to the grey panel's left edge (col_x), not the centred content — so a
        # caption-widened tile keeps the toggle on its edge rather than drifting it inward.
        # Present whenever the tile's row and column bands are open — it stays put when
        # only the tile is folded, so the tile can be re-expanded.
        for _bid, rkey, ckey in self.tiles:
            if ((rkey, ckey) in self.declared_tiles  # a dropped tile (e.g. all-interval's retune×targets) takes its toggle too
                    and rkey in self.row_y and ckey in self.col_x and self.row_open(rkey) and self.col_open(ckey)):
                glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in self.collapsed)
                self.cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                     self.col_x[ckey] - PAD + TOGGLE_INSET, self.tile_top[rkey] - PAD + TOGGLE_INSET,
                                     TOGGLE, TOGGLE, "tiletoggle", text=glyph))

        # Value-display filtering. The tiles (blocks) and gridlines (lines) always
        # stand; only a tile's *contents* answer to the value-display toggles, applied
        # here by kind rather than threaded through every emission above. "gridded
        # values" off drops them outright -- numbers, boxes, EBK marks, controls -- so
        # the tiles go empty. "quantities" (general) off is gentler: it keeps the boxes
        # and marks and only blanks the body numbers, baring the gridded structure.
        if not self.gridded:
            self.cells = [cb for cb in self.cells if cb.kind not in GRIDDED_KINDS]
        elif not self.show_quantities:
            self.cells = [replace(cb, blank=True, text="") if cb.kind in BLANKED_NUMBER_KINDS else cb
                     for cb in self.cells]

        # Each column title renders unwrapped and centred on its gridline (see _title_w and the
        # .rtt-colheader rule), so one wider than its content-hugging column overhangs it. Interior
        # overhangs spill into the gaps over neighbours, but the LAST column's title spills past the
        # grid's right edge — the narrow (empty) interest column's long "other intervals of interest"
        # reaches well beyond total_w. Publish that reach so the renderer widens the grey pane to show
        # the title rather than clip it. Computed from the final cells (after any blanking), so a mode
        # that drops or empties the titles reports no overhang.
        title_right = max((c.x + c.w / 2 + _title_w(c.text) / 2 for c in self.cells if c.kind == "colheader"),
                          default=self.total_w)
        right_overhang = max(0.0, title_right - self.total_w)

        # The frozen bands reach past the branching (each column's trunk + fan-out bus, each
        # matrix row's trunk + left bus, and the ± controls riding those buses) to the first
        # value tile's panel edge: one GAP past the toggle band, less the PAD the grey tile
        # overhangs its cells by. So the branching + ± ride the frozen header/row-band and only
        # the value tiles scroll beneath them.
        return Layout(self.total_w, self.total_h, tuple(self.lines), tuple(self.blocks), tuple(self.cells),
                      freeze_x=self.node_edge + GAP - PAD, freeze_y=self.branch_top_y + GAP + GRIP_BAND - PAD,
                      right_overhang=right_overhang, identities=self._col_ids,
                      approach_box=self.approach_box)


def build(state, settings=None, collapsed=None,
          tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
          pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
          custom_prescaler=None, optimize_locked=False, tuning_optimized=False,
          pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
          pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
          displayed_tuning_name=None, projection_held=None, displayed_projection_name=None) -> Layout:
    return _GridBuilder(
        state, settings, collapsed, tuning_scheme, target_spec, interest, range_mode,
        pending_comma, held_vectors, generator_tuning, target_override, custom_prescaler,
        optimize_locked, tuning_optimized, pending_interest, pending_held, pending_target,
        prev_ids, pending_element, nonprime_approach, superspace_generator_tuning,
        displayed_tuning_name, projection_held, displayed_projection_name,
    ).layout()
