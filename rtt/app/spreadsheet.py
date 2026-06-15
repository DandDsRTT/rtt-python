"""Spreadsheet layout for the temperament/tuning grid (the mockup's default view).

Rows are the quantities the temperament exposes (quantities, mapping, tuning,
just tuning, retuning, damage); columns are the interval/generator sets they're
shown over (generators, domain primes, target intervals). Cells sit on shared
coordinate axes — every prime/target is a vertical line shared down its column,
every generator a horizontal line shared across the mapping rows — so the
matrices stay aligned and the reconciling renderer can animate rows/columns in
and out. Reuses the entity types in :mod:`rtt.app.layout`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Callable, NamedTuple

from rtt.app import ids
from rtt.app import presets
from rtt.app import service
from rtt.app.layout import Block, CellBox, Layout, Line
from rtt.app.marks import BR_INSET, BR_SERIF_L  # bracket-glyph insets, for FRAME_OVERHANG below
from rtt.app.grid_tables import *  # noqa: F403  (semantic content tables, re-exported)
from rtt.app.grid_tables import _FACTOR_GROUP  # build() reads it; import * skips the underscore name
from rtt.app.settings import defaults as _default_settings

ROW_H = 37  # px per row / matrix-entry height
COL_W = 37  # px per value column; == ROW_H so matrix cells are squares that tile
# the column (a shared-border grid, per the mockup); cents stack int-over-frac to fit
GAP = 28  # px between row/column groups (the visible gap between two grey tiles is GAP - 2*PAD)
PAD = 4  # px a block extends around its cells
TITLE_MARGIN = 8  # min px kept between two adjacent columns' centred, unwrapped titles: a column's
# title overhangs its content-hugged footprint into the gaps (see the col-layout loop), so the gap
# to its neighbour widens by however much keeps the two overhanging titles this far apart — no title
# can overspill into a neighbour's, however narrow either column is
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
SCHEME_BTN_SQ = 22  # the square ✕ "return to scheme" button on the projection / embedding tiles
SCHEME_LABEL_W = 92  # the "return to scheme" caption beside it
SCHEME_CTRL_W = SCHEME_BTN_SQ + 2 + SCHEME_LABEL_W  # the ✕ + gap + caption, as one control slot
TARGET_PRESET_W = 144  # wider: the target chooser seats a 30px gridded limit square + the family select
PTEXT_MAX_FONT = 10  # px cap on the plain-text font; the app shrinks it per box so every value
# always fits on ONE line within its column (a long tuning row just gets smaller text)
PTEXT_H = 13  # px height of a one-line read-only plain-text value
PTEXT_EDIT_H = 16  # px height of an editable plain-text input box (a touch taller than a text line)
SYMBOL_H = 18  # height of the quantity-symbol glyph above the caption (when symbols shown)
BAND_GAP = 6  # breathing room added to each in-tile band (symbol, caption, units, plain text) so the
# stacked bands — values, symbol/equivalence, name, units, plain text, control boxes — don't crowd
# (each present band reserves +BAND_GAP, centred, so adjacent bands clear each other by ~BAND_GAP)
SYMBOL_FONT = 15  # px font size of the symbol + equivalence glyph (matches .rtt-symbol in rtt.css);
# its width drives _symbol_floor, which widens a tile so the symbol/equivalence never wraps
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
MATLABEL_W_SSPRIMES = 56  # the ssprimes column's row-label gutter: wider than the plain MATLABEL_W
# (22) so the projection row's P_L→s covector labels 𝒑ₗ→ₛᵢ (an arrow + two subscripts, like M_s→L)
# fit beside M_L's 𝒎ʟᵢ rather than overflowing the ⟨ bracket. (Centred, like 𝒎ʟᵢ.)
UNIT_H = 12  # height of the per-box "units: …" line (below the caption, when units shown)
CHART_H = 64  # height of a per-tile bar chart's plot area (when charts shown)
CHART_GAP = 4  # gap between a chart and the value cells below it
RANGE_CHART_H = 58  # height of the generator tuning-ranges I-beam chart (title + caps + min/max labels)
RANGE_MODE_H = 46  # height of the monotone/tradeoff range-mode selector — two rows of square
# indicators STACKED below the chart, with 4px top/bottom padding so neither row touches the
# enclosing box's edge (the bumped 16px boxes don't fit side by side anyway)
RANGE_GAP = 2  # gap between the ranges chart and its mode selector (and the values above the chart)
OPT_TITLE_H = 14  # height of the optimization box's title strip ("optimization")
OPT_PAD_T = 8  # inset above the title (== BOX_INNER, so every control box pads its content the same)
OPT_PAD_B = 8  # bottom inset below the captions (== BOX_INNER)
OPT_PAD_L = 8  # left inset of the mean damage from the box's edge (== BOX_INNER)
OPT_PAD_R = 8  # right inset of the power's clearance from the box's edge (== BOX_INNER)
OPT_TITLE_GAP = 4  # bottom margin under the title, before the control row
OPT_COL_GAP = 8  # the standard gap between adjacent in-tile controls — sizes OPT_BOX_MIN_W
# (the clearance around the optimization box's centered power) and the box-𝐋 / q-dual / all-
# interval slots elsewhere
# The box spans the FULL width of the damage tile; its two controls DISTRIBUTE across it: the
# mean damage hugs the left edge, and the power 𝑝 sits centered in the gap to its right, so the
# "optimization power" caption has clear room either side. The min-damage value and the ∞ field
# are ordinary COL_W gridded cells (contents centred); their symbols/captions centre under them.
OPT_POW_CAP_W = 90  # the "optimization power" caption cell (one line, centred under the ∞ cell)
OPT_MEAN_DAMAGE_W = 64  # the mean damage's COLUMN: its value cell is COL_W centred within this, and its symbol
# and caption span it, so the WIDEST mean damage label — the min()-wrapped symbol min(⟪𝐝⟫ₚ) (~69px) /
# min(⟪𝒓𝐿⁻¹⟫dual(q)) — stays centred over the value without overflowing the box's left border or the
# "optimization power" caption to its right. Also the caption's wrap width: "power mean" fits on one
# line, while the wider "retuning magnitude" breaks at the space into the two lines cap_band reserves.
# the narrowest the box can be and still seat its spread-out controls with the power's caption clear
# of both neighbors — left pad | mean damage column | gap | power+caption | right pad.
# A damage tile narrower than this floors its column up to fit (see _control_floor).
OPT_BOX_MIN_W = OPT_PAD_L + OPT_MEAN_DAMAGE_W + OPT_COL_GAP + OPT_POW_CAP_W + OPT_PAD_R
# An in-tile control box: a dropdown / checkbox enclosed in a thin-bordered frame that SPANS its
# tile's full width (like the optimization / tuning-ranges boxes), with the control at its top-left
# and a small field LABEL beneath naming what it sets ("established tuning scheme"). BOX_OUTER is
# the vertical gap above/below the box; BOX_INNER insets the control + label off the box border;
# CTRL_LABEL_GAP sits between the label and the control. Box heights vary with the label, so a
# row reserves its tallest.
BOX_OUTER = 4  # vertical gap above/below a control box (it spans its tile's width — see control_box)
BOX_INNER = 8  # padding inside a control box, from its content to its border (all four sides)
CTRL_LABEL_GAP = 2  # gap between the scheme-button row and the dropdown below it
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
# How far a vector-list outer [ ] (and its column rules) overhangs the per-column marks at
# top and bottom — equal to the margin by which the mapping's spanning top/bottom bracket
# overhangs its per-row ⟨ ] in x. There the outer bracket reaches the gutter's outer edge
# while the inner glyph sits BR_INSET + BR_SERIF_L in from it, so the overhang is the rest
# of the gutter: BRACKET_W − (BR_INSET + BR_SERIF_L) = 7.5px. Tying it to the same glyph
# insets keeps the vertical overhang exactly matched to the horizontal one if either is retuned.
FRAME_OVERHANG = BRACKET_W - BR_INSET - BR_SERIF_L
ROW_HANDLE_W = 14  # the per-mapping-row drag handle (drag a generator row onto another to add it)
ROW_HANDLE_GAP = 4  # the gap it keeps from the matrix's opening bracket
ETPICK_W = COL_W  # the per-mapping-row ET picker (a compact chooser ~one gridded value wide, riding
# a RIGHT-only gutter of the primes column, past the ]): pick a curated ET to set that row to its val
ETPICK_GAP = 4  # the gap the ET picker keeps from the row's closing ] bracket
COMMAPICK_GAP = 4  # the gap a comma column's per-column comma picker keeps below the ⟩ foot
VAL_BRACKET_H = 16  # a single-row value bracket, kept short and centred in its
# ROW_H row so neighbouring rows' brackets keep a clear gap (the enclosing
# mapped-list [ ] is the tall exception and spans the whole matrix)
TRANSPOSE_W = 9  # the EBK-off ᵀ superscript box at a vector matrix's top-right corner (just past its ])
MARK_INSET = 8  # inset of a mapped column's top/bottom mark, so it clears the rules
SEP_W = 2  # width of a vertical rule between vector columns (the renderer draws it
# as thick as a square bracket's main bar; this is just the cell it centres in)
V_SPLIT_GAP = 16  # extra breathing room between the comma half C and the unchanged half U of the
# consolidated V = C|U column, so the dividing bar clears the interactive gridded cells on each side
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
DASH = "—"  # an em-dash for a DASHED cell — an unknown value the under-held tuning doesn't pin
            # (an unchanged column the held basis doesn't reach, or P/G when h < r — not a projection)

# The semantic content tables (COUNTS / CAPTIONS / SYMBOLS / CELL_FACTORS / TILES / ...) -- pure
# data describing which quantities exist and their symbols, captions, units, mnemonics,
# colorization factors and tile sets -- now live in rtt.app.grid_tables, re-exported via the
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


def _math_expr(operand: str, value: float, show_value: bool, decimals: bool = True) -> str:
    """A just value's exact closed form ``1200 · log₂{operand}`` — which *equals* the
    cents value, so the decimal stays in cents and is kept as a true ``= {cents}``.
    The two parts are newline-separated so the renderer stacks them (the ``=`` and
    the decimal on the second line), e.g. ``"1200 · log₂2\\n= 1200.00"``. With the
    value (quantities) off, only the expression shows; with decimals off the value rounds."""
    expr = f"1200 · log₂{operand}"
    return f"{expr}\n= {service.cents(value, decimals)}" if show_value else expr


def _prescale_math_expr(coeff, prime_term: str, value: float, show_value: bool, decimals: bool = True) -> str:
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
    return f"{expr}\n= {service.prescale_text(value, decimals)}" if show_value else expr


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
                   "pending", "checked", "blank", "unit", "underlines")


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
    brackets, separators, drag grips and ± controls — is not flagged. PENDING cells (a green
    draft's placeholders) never read as removed either: they are not committed content, and an op
    that materializes (or discards) the draft merely renames its placeholder ids — red there would
    speckle the very column being typed into."""
    after = {c.id for c in new.cells}
    return frozenset(c.id for c in old.cells
                     if c.kind in RINGABLE_KINDS and not c.pending and c.id not in after)


def assign_column_tokens(prev, keys, claim_unmatched=False):
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
    elsewhere isn't mistaken for a move into it. With ``claim_unmatched`` (the BASIS groups — the
    mapping rows and the commas, whose entries a re-solve rewrites in place), a count change that
    leaves entries unmatched on BOTH sides pairs the unmatched new entries with the unclaimed
    previous tokens in order, so the diff reads them as moved values rather than a wholesale
    remove-plus-recreate — a rank change reads "survivors move (amber), the surplus slot goes
    (red)". The independent interval SETS (targets/held/interest) leave it off: a brand-new ratio
    is genuinely new, never "the same column as" a dropped one, so a family switch reds what it
    drops instead of relabelling it. Anything still unmatched gets a token greater than every
    token in play, so live columns never collide. With no previous render the columns number
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
        # a BASIS group's re-solve can rewrite the surviving entries wholesale (a rank change
        # recombines every mapping row), so nothing content-matches even though the slots are still
        # on screen. Pair the still-unmatched new entries with the unclaimed previous slots IN
        # ORDER: the diff then reads "this slot's value moved" (amber) and only the genuinely
        # surplus previous slots read as removed (red) — rather than every slot reading
        # removed-plus-brand-new. A pure add or a survivor-verbatim remove leaves no (unmatched,
        # unclaimed) pair, so this changes nothing for the cases content already matches.
        if claim_unmatched:
            unclaimed = iter([pi for pi in range(len(prev)) if not claimed[pi]])
            for j in range(len(keys)):
                if tokens[j] is None:
                    pi = next(unclaimed, None)
                    if pi is None:
                        break
                    tokens[j] = prev[pi][0]
    nxt = max([t for t in tokens if t is not None] + [tok for tok, _ in prev] + [-1]) + 1
    for j in range(len(keys)):  # fresh token, greater than any in play (no reuse → no collision)
        if tokens[j] is None:
            tokens[j], nxt = nxt, nxt + 1
    return list(zip(tokens, keys))


def pending_token(tokens) -> int:
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


def _bus_span(positions) -> tuple[float, float]:
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
    header_symbols: bool
    units: bool
    cell_units: bool
    domain_units: bool
    temp: bool
    form: bool
    form_controls: bool
    form_tiles: bool
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
    decimals: bool
    ebk: bool
    interval_ratios: bool
    interval_vectors: bool
    math: bool


def _resolve_show_flags(settings, collapsed) -> _ShowFlags:
    """The first build phase: derive the view flags + their gating from the Show settings. Pure —
    depends only on the settings dict and the collapsed set (no geometry)."""
    captions = settings["names"]  # the in-tile quantity captions; row/col titles always show
    temp = settings["temperament_tiles"]
    tuning = settings["tuning_tiles"]
    # optimization / weighting are sub-controls of tuning tiles: they annotate / open the tuning
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
        header_symbols=settings["header_symbols"],  # the matrix row/col header labels (matlabels 𝒎ᵢ, 𝐜ᵢ)
        units=settings["units"],  # the in-tile "units: …" line, below each box's caption
        cell_units=settings["cell_units"],  # the per-value unit beneath each gridded cell
        domain_units=settings["domain_units"],  # the units row (spine) + units column
        temp=temp,
        form=settings["form"],  # the canonical-form subscript C on 𝑀/𝒈/G (the parent layer)
        form_controls=settings["form_controls"],  # the <choose form> chooser dropdowns
        form_tiles=settings["form_tiles"],  # the canonical-mapping row + 𝐹 matrix (greyed for now)
        tuning=tuning,
        optimization=optimization,
        weighting=weighting,
        alt_complexity=alt_complexity,
        # Whether each alt.-complexity in-tile chooser emits — evaluated up front (without col_x,
        # which the column-width loop computes later) so the column-width floor can widen the
        # primes / targets columns to fit the controls. box 𝒄 (the complexity chooser) shows with
        # WEIGHTING alone (the norm is core to weighting, not an alt.-complexity extra); only box 𝐋
        # (the prescaler controls) stays on alt_complexity.
        lbox=(alt_complexity and settings["temperament_tiles"]
              and "col:primes" not in collapsed and "row:prescaling" not in collapsed
              and "tile:prescaling:primes" not in collapsed),
        cbox=(weighting
              and "col:targets" not in collapsed and "row:complexity" not in collapsed
              and "tile:complexity:targets" not in collapsed),
        detempering=settings["generator_detempering"],  # the generator-detempering column (matrix D)
        interest=settings["interest"],  # the other-intervals-of-interest column (its own tiles toggle)
        # Value-display toggles. "gridded values" is the master switch: off filters every value a
        # tile holds (see GRIDDED_KINDS). "quantities" is gentler — it keeps boxes/EBK marks and
        # only blanks the body numbers (BLANKED_NUMBER_KINDS); "interval_ratios" governs the
        # interval-ratios row and its spine column, and "interval_vectors" the interval-vectors row
        # (which used to ride temperament_tiles). "math" prefixes a tuning cent with its closed form.
        gridded=settings["gridded_values"],
        quantities=settings["quantities"],
        # decimals off rounds every shown value to the nearest integer (service.cents / prescale_text).
        # .get keeps old persisted/hand-built settings dicts (pre-decimals) reading at full precision.
        decimals=settings.get("decimals", True),
        # ebk off rewrites every matrix/vector into plain matrix notation (square braces + a ᵀ on the
        # vector kind), both the gridded marks and the plain-text strings. .get keeps old persisted
        # dicts (pre-ebk) reading in full EBK notation, the as-shipped default.
        ebk=settings.get("ebk", True),
        interval_ratios=settings["interval_ratios"],
        interval_vectors=settings["interval_vectors"],
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


class _VecGrid(NamedTuple):
    """Per-list descriptor for the three cleanly-uniform editable interval-vector grids
    (targets, held, intervals of interest) emitted by _emit_vectors_band. Each emits the
    same `for col: for prime:` committed grid plus one pending-draft column; only these
    parameters differ. (Commas and detempering are NOT in this family — see the method.)"""
    group: str                          # tile/col-token group key ("targets" / "held" / "interest")
    count: int                          # committed column count (k / nh / mi)
    id_fn: Callable[[str, int], str]    # cell-id builder (ids.target_cell / held_cell / interest_cell)
    left_fn: Callable[[int], float]     # column-left x (self.target_left / held_left / interest_left)
    inset: float                        # per-side box inset within the COL_W slot
    committed_kind: str                 # cell kind for committed cells (targets: "targetcell" or "vec")
    pending_kind: str                   # cell kind for the draft column (always the editable kind)
    data: object                        # the committed vector columns (self.target_vectors / held / interest)
    pending: object                     # the open draft vector, or None (self.pending_target / held / interest)
    sizes: object                       # the size record whose .just[col] feeds _voice


class _QtyList(NamedTuple):
    """Per-list descriptor for the three cleanly-uniform editable interval-ratio columns of the
    quantities row (targets, held, intervals of interest) emitted by _emit_quantities_row. Each
    emits one ratio CellBox per committed column (+ a _voice and a branch_minus −), then a
    pending-draft ratio cell with its own cancel −; only these parameters differ. (Commas, the
    generator/domain/superspace lists and read-only detempering are NOT in this family — they
    stay inline in the method.)"""
    group: str                          # tile/col-token/_voice group key ("targets" / "held" / "interest")
    singular: str                       # id + minus-id prefix ("target" / "held" / "interest")
    count: int                          # committed column count (k / nh / mi)
    left_fn: Callable[[int], float]     # column-left x (self.target_left / held_left / interest_left)
    ratios: object                      # the committed ratio texts (self.targets / held_ratios / interest_ratios)
    sizes: object                       # the size record whose .just[col] feeds _voice
    pending: object                     # the open draft, or None (self.pending_target / held / interest)
    kind: str                           # committed cell kind ("ratiocell"; targets: "commaratio" when read-only)
    minus_gate: bool                    # whether committed columns carry a − (always True except auto targets)


class _MappedTile(NamedTuple):
    """Per-list descriptor for the three cleanly-uniform read-only ("mapped") M·X tiles of the
    mapping band's committed generator rows (M·target / M·interest / M·held). Each emits, in one
    generator row, one CellBox per committed column carrying str(data[i][col]), plus a blank green
    placeholder under the open draft column; only these parameters differ. (The commas mapped tile —
    M·comma, with its mc_text ghost — and the pending-draft generator row are NOT in this family;
    they stay inline.)"""
    prefix: str                         # cell-id prefix ("mapped" / "imapped" / "hmapped")
    group: str                          # tile/col-token/cell_unit group key ("targets" / "interest" / "held")
    count: int                          # committed column count (k / mi / nh)
    left_fn: Callable[[int], float]     # column-left x (self.target_left / interest_left / held_left)
    data: object                        # the committed mapped columns (self.mapped / interest_mapped / held_mapped)
    pending: object                     # the open draft, or None (self.pending_target / interest / held)


@dataclass
class RowBand:
    """Per-row geometry for one laid-out row band (replaces ~17 parallel row-key-keyed dicts).

    Field ↔ former-dict mapping (all keyed by the same row key in self.rows):
        y               ← row_y            (value-band top: cells/gridlines, below toggle head + top frame + chart)
        h               ← row_h            (value-band height: STRIP when folded, else natural)
        label           ← row_label        (the row's gutter label)
        collapsible     ← row_collapsible  (whether the row has a fold toggle)
        tile_h          ← tile_h           (full grey-panel height, head→schemebtn, + any tile_extra)
        tile_top        ← tile_top         (grey-panel top y)
        frame           ← row_frame        (bottom brace-band height below the values)
        sym             ← row_sym          (symbol/equivalence slot height above the caption)
        cap             ← row_cap          (caption band height)
        units           ← row_units        (units line height)
        ptext           ← row_ptext        (plain-text box band height)
        pre             ← row_pre          (preset-chooser band height)
        schemebtn       ← row_schemebtn    (✕ return-to-scheme control-row height)
        nsub            ← row_nsub         (natural cell-row count = matrix height in cells)
    Conditionally-present fields — None when the old dict had NO entry for this row
    (i.e. the reservation was not made); a check `if k in self.OLD_DICT:` becomes
    `if self.rows[k].FIELD is not None:`:
        chart_top       ← chart_top          (chart band top; None unless the row reserved a chart band)
        int_handle_top  ← row_int_handle_top (drag-handle band top; None unless drag-to-combine reserved it)
        matlabel_top    ← row_matlabel_top   (column-label band top; None unless a matlabel was reserved)
    """
    y: float
    h: float
    label: str
    collapsible: bool
    tile_h: float
    tile_top: float
    frame: float
    sym: float
    cap: float
    units: float
    ptext: float
    pre: float
    schemebtn: float
    nsub: int
    chart_top: float | None = None
    int_handle_top: float | None = None
    matlabel_top: float | None = None


class _GridBuilder:
    def __init__(self, state, settings=None, collapsed=None,
                 tuning_scheme=None, target_spec=None, interest=(), range_mode="monotone",
                 pending_comma=None, held_vectors=(), generator_tuning=None, target_override=None,
                 custom_prescaler=None, custom_weights=None, tuning_optimized=False,
                 pending_interest=None, pending_held=None, pending_target=None, prev_ids=None,
                 pending_element=None, nonprime_approach="", superspace_generator_tuning=None,
                 displayed_tuning_name=None, held_basis_ratios=(), displayed_projection_name=None,
                 targets_in_use=True, pending_mapping_row=None, preview_remove=None,
                 mapping_form=None, comma_basis_form=None):
        self.prev_ids = prev_ids or {}
        self.mapping_form = mapping_form          # the user's sticky <choose form> picks (tiebreakers
        self.comma_basis_form = comma_basis_form  # when offered forms coincide — see resolve_*_form)
        # a − hover's transient rank-removal preview: None | ("comma", idx) | ("row", idx). Removing
        # a comma raises the rank (a generator is BORN — a green ghost mapping row) and recombines
        # the surviving rows; removing a generator raises the nullity (a comma is born — a green
        # ghost comma column) and recombines the surviving commas. The dual twin of the +/draft
        # preview, but on a hover, so it renders a non-editable green GHOST rather than an editable
        # draft. (The red leaver is the hovered comma/row itself, already on screen — just flagged.)
        # Validate against the live counts so an out-of-range / impossible removal previews nothing
        # (the UI gates these — no comma − without a comma, no row − at rank 1 — but the builder must
        # not crash if asked anyway, e.g. a stale hover): a comma idx must be a REAL comma (state.n,
        # so just intonation's placeholder zero-comma doesn't count), a row idx removable (r > 1).
        self.preview_remove = preview_remove
        self.ghost_row = (preview_remove is not None and preview_remove[0] == "comma"
                          and 0 <= preview_remove[1] < state.n)
        self.ghost_comma = (preview_remove is not None and preview_remove[0] == "row"
                            and len(state.mapping) > 1 and 0 <= preview_remove[1] < len(state.mapping))
        if not (self.ghost_row or self.ghost_comma):
            self.preview_remove = None
        # the target interval column is hidden when the targets aren't computing the tuning (the
        # displayed tuning has deviated from the scheme's target-driven optimum onto a projection)
        self.targets_in_use = targets_in_use
        self.state = state
        self.settings = settings
        self.collapsed = collapsed
        self.tuning_scheme = tuning_scheme
        self.target_spec = target_spec
        self.interest = interest
        self.range_mode = range_mode
        self.pending_interest = pending_interest
        self.pending_held = pending_held
        self.pending_target = pending_target
        self.pending_element = pending_element  # chapter-9 domain basis element draft (str / None)
        # a generator being added: a draft mapping ROW (d ints, None while blank) the user types in,
        # rendered as a green draft row across the mapping band — the row mirror of pending_comma
        self.pending_mapping_row = pending_mapping_row
        self.custom_prescaler = custom_prescaler
        self.custom_weights = custom_weights  # the user's manual per-target weights, or None
        self.tuning_optimized = tuning_optimized
        self.nonprime_approach = nonprime_approach
        self.superspace_generator_tuning = superspace_generator_tuning  # manual 𝒈L (rL) in prime-based
        # the named scheme the DISPLAYED tuning realises (editor.displayed_tuning_scheme_name), or
        # None off the named list — threaded in so the tuning chooser's single-option lock matches
        # app._build_preset's on-list check. None (a bare spreadsheet.build) keeps the chooser a
        # dropdown; the live page always passes it (see Editor.layout).
        self.displayed_tuning_name = displayed_tuning_name
        # the tuning's held interval basis (ratio strings: the scheme's structural held plus the
        # held column — editor.held_basis_ratios) drives the projection P = GM, the embedding G and
        # the unchanged basis U; whatever it doesn't pin (h < r) is dashed out. The NAME the
        # established-projection chooser shows (editor.displayed_projection_scheme_name) is threaded
        # in to match app._build_preset's on-list check, like the tuning name.
        self.held_basis_ratios = held_basis_ratios
        self.displayed_projection_name = displayed_projection_name

        if self.settings is None:
            self.settings = _default_settings()
        if self.tuning_scheme is None:
            # the as-shipped scheme is target-based and unity-weighted, matching the editor's default
            self.tuning_scheme = service.DEFAULT_DOCUMENT_SCHEME
        if self.target_spec is None:
            self.target_spec = service.DEFAULT_TARGET_SPEC
        self.collapsed = self.collapsed or frozenset()  # ids ("row:tuning", "col:targets") shown as strips
        (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
         show_tuning, show_interest, show_interval_ratios) = self._unpack_show_flags()
        # Row labels and column headers (and their gutters) are always present.
        label_w = LABEL_W
        header_h = HEADER_H
        self._resolve_superspace_dims()
        self._resolve_prescaler_and_domain_labels()
        self._resolve_interval_sets(generator_tuning, target_override, held_vectors, pending_comma,
                                    show_temp, show_tuning)
        self._resolve_complexities()
        interest_tiles, held_tiles, detempering_tiles = self._declare_interval_column_tiles()
        self._resolve_projection_data(show_tuning)
        self._declare_tiles(interest_tiles, held_tiles, detempering_tiles)

        col_bands, content_x0 = self._define_col_bands(show_interval_ratios, show_domain_units,
                                                       show_temp, show_tuning, show_interest, label_w)

        row_bands = self._define_row_bands(show_counts, show_interval_ratios, show_domain_units,
                                           show_temp, show_tuning)

        self._layout_columns(col_bands, content_x0)

        tile_extra = self._resolve_tile_extras(show_ranges, show_tuning)

        rows_top_y = self._init_row_geometry(header_h)

        self._resolve_ptext_strings(generator_tuning, target_override)

        self._layout_rows(row_bands, tile_extra, rows_top_y, show_charts)

        self._init_group_geometry()

    def _unpack_show_flags(self):
        """Phase 1: resolve the Show-panel view flags onto self; returns the build-local ones."""
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
        self.show_header_symbols = _f.header_symbols
        self.show_units = _f.units
        self.show_cell_units = _f.cell_units
        show_domain_units = _f.domain_units
        show_temp = _f.temp
        self.show_form = _f.form  # the form layer: subscript-C the canonical-form objects (𝑀/𝒈/G)
        self.show_form_controls = _f.form_controls
        self.show_form_tiles = _f.form_tiles  # the canonical-mapping row + 𝐹 matrix (greyed for now)
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
        self._decimals = _f.decimals  # False rounds every formatted value to the nearest integer
        # False (EBK off) rewrites every gridded mark + plain-text string into plain matrix notation:
        # square braces throughout, a ᵀ on the vector kind. Read by bracket()/matrix_frame()/
        # vector_list_marks() (the marks) and _resolve_ptext_strings (the strings).
        self.show_ebk = _f.ebk
        show_interval_ratios = _f.interval_ratios
        # the interval-vectors row's own toggle (it used to ride temperament_tiles); read in
        # _define_row_bands off self so the band-signature tuple stays unchanged.
        self.show_interval_vectors = _f.interval_vectors
        self.show_math = _f.math
        # custom-weight mode is target-mode only AND not the math-expr view: there the 𝒘 row's cells
        # are editable inputs and the slope chooser greys (the typed weights supersede the slope)
        self.custom_weights_active = (self.custom_weights is not None
                                      and not service.is_all_interval(self.tuning_scheme)
                                      and not self.show_math)
        return (show_counts, show_charts, show_ranges, show_domain_units, show_temp,
                show_tuning, show_interest, show_interval_ratios)

    def _resolve_superspace_dims(self) -> None:
        """Resolve the domain dims (d, r, elements) and the chapter-9 superspace dims + show flags."""
        self.d = self.state.d
        self.r = len(self.state.mapping)
        # the mapping rows the grid SHOWS: the r committed generators, plus one extra while a draft
        # generator row is being added (the row mirror of nc_shown growing the comma half) OR while a
        # comma − is hovered (a generator is BORN — the green ghost mapping row). Either rides at index
        # r (one past the committed rows); it grows ONLY the mapping band's height, so its brackets
        # enclose the green ?/blank row, while everything keyed off self.r (the genmap, canonical
        # mapping, comma dual, tuning rows) stays at the committed rank.
        # a green mapping ROW rides at index r — an editable draft (pending_mapping_row) or a
        # non-editable ghost (comma − hover born generator); `row_draft` gates the shared emission,
        # `ghost_row` picks editable-vs-read-only within it.
        self.row_draft = self.pending_mapping_row is not None or self.ghost_row
        self.r_shown = self.r + (1 if self.row_draft else 0)
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
        # the chapter-9 superspace tuning solve, memoized (see superspace_tun below): the
        # plain-text bundle and layout()'s ss tuning rows share one solve per build
        self._ss_tun = None
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

    def _resolve_prescaler_and_domain_labels(self) -> None:
        """Phase 2: resolve the prescaler glyph/labels, the identity-objects gate and the domain coordinate labels."""
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
        # generators, domain primes as vectors over themselves, 𝑀·D, the form matrices
        # cancelling 𝐹⁻¹𝐹, and in the superspace block M_L over its own generators and the JI
        # mapping M_jL = I). A live, default-off Show toggle (settings.IMPLEMENTED) that gates
        # the two tiles BUILT so far — the superspace M_jL = I (ss_vectors × ssprimes) and
        # M_LgL = I (ss_mapping × ssgens); the standard-domain self-maps aren't in the tile list
        # yet, so the gate has nothing to drop for them until they're built.
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

    def _resolve_interval_sets(self, generator_tuning, target_override, held_vectors, pending_comma,
                               show_temp, show_tuning) -> None:
        """Resolve the interval sets (targets/held/commas/unchanged/interest), their pending drafts, derived quantities and id-tokens."""
        self.gens = service.generators(self.state.mapping, self.elements)
        # the − hover's BORN row/column shows COMPUTED values (the op is known): removing comma idx
        # gives a definite new temperament whose extra generator is the green ghost mapping row;
        # removing generator idx gives the extra comma. The newborn is the fresh-token entry — the
        # last row / comma of the re-dualed basis (assign_column_tokens pairs the survivors
        # positionally, so the surplus lands last). Computed once; the ghost emission fills its cells.
        self.ghost_new = None  # the post-remove temperament the − hover previews (its newborn is the ghost)
        self.ghost_row_map = self.ghost_row_ratio = None
        self.ghost_row_mapped = {}        # comma−: the newborn generator's M·interval over each set (filled at 1149)
        self.ghost_comma_vec = self.ghost_comma_ratio = None
        self.ghost_comma_mapped = ()      # mapping−: M_current[i]·newborn per row (0 for survivors)
        self.ghost_comma_just = 0.0       # mapping−: the newborn comma's just size (it vanishes → tempered 0)
        self.ghost_comma_complexity = 0.0 # mapping−: the newborn comma's complexity ‖𝐿·comma‖q
        if self.ghost_row:
            self.ghost_new = service.remove_comma(self.state, self.preview_remove[1])
            self.ghost_row_map = self.ghost_new.mapping[-1]
            born_gens = service.generators(self.ghost_new.mapping, self.elements)
            self.ghost_row_ratio = born_gens[-1] if born_gens else ""
        elif self.ghost_comma:
            self.ghost_new = service.remove_mapping_row(self.state, self.preview_remove[1])
            self.ghost_comma_vec = self.ghost_new.comma_basis[-1] if self.ghost_new.comma_basis else None
            born_crs = service.comma_ratios(self.ghost_new.comma_basis, self.elements) if self.ghost_new.comma_basis else ()
            self.ghost_comma_ratio = born_crs[-1] if born_crs else ""
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
        # a target being added rides as a pending draft column (blank green cells + a "?" ratio)
        # until its vector is filled in, like the comma / interest / held draft. Suppressed when
        # the list isn't editable (all-interval's auto Tₚ = I set is not user-curated, no + draft).
        self.pending_target = list(self.pending_target) if (self.pending_target is not None and self.targets_editable) else None
        self.k_shown = self.k + (1 if self.pending_target is not None else 0)
        self.mapped = service.mapped_intervals(self.state.mapping, self.targets, self.elements)
        self.canon_mapping = service.canonical_mapping(self.state.mapping)  # M defactored + HNF (the form box)
        self.rc = len(self.canon_mapping)  # canonical rank (== r for a valid temperament)
        self.form_M = service.form_matrix(self.state.mapping)  # F: the generator form matrix (r×r), F·M = canonical
        # the canonical generators as ratios (g_C) — the canonical mapping's detempering, the
        # canonical-generators-column twin of self.gens (the stored mapping's generators). For
        # 5-limit meantone the equave-reduced default gens are (2/1, 3/2) but the canonical ones
        # are (2/1, 3/1) — the octave and the (non-equave-reduced) fifth-as-3.
        self.canon_gens = service.generators(self.canon_mapping, self.elements)
        # which generator form the STORED mapping currently is (so the <choose form> dropdown shows it
        # selected) — "" when it matches none of the offered forms (an unlisted equivalent generating set)
        # honor the user's explicit <choose form> pick as a tiebreaker (mapping_form): forms can
        # coincide, so deriving the selection from the matrix alone would snap off the chosen option
        self.mapping_form_key = service.resolve_mapping_form(
            self.state.mapping, self.mapping_form, self.state.domain_basis)
        # likewise for the comma-basis <choose form> dropdown (canonical / positive-ratio / minimal),
        # where a comma's minimal form commonly equals its positive-ratio form
        self.comma_basis_form_key = (
            service.resolve_comma_basis_form(self.state.comma_basis, self.comma_basis_form, self.state.domain_basis)
            if self.state.n else "")
        # the form layer's two-faced display (step 3c): the subscript C marks the canonical form, so it
        # rides the MAIN rows only when the stored mapping IS canonical. When it is a non-canonical form
        # (incl. the default equave-reduced), the main rows stay bare — and the canonical form is then
        # seen via the canonical-mapping row + 𝐹 column, which the user reveals with the form-tiles toggle.
        self.form_is_canonical = self.mapping_form_key == "canonical"
        self.show_form_subscript = self.show_form and self.form_is_canonical  # subscript-C on the main rows
        # the canonical-mapping row + the canonical-generators column are gated SOLELY on form_tiles:
        # off → NEITHER can appear (even under a non-canonical form); on → both surface.
        self.show_canon = self.show_form_tiles
        self.target_vectors = service.target_interval_vectors(self.targets, self.d, self.elements)  # k vectors, each d-tall
        # held intervals: the optimization box's held-just constraints — user-edited vectors in the
        # held column (like the intervals of interest). The tuning holds each exactly just, so
        # they are folded into service.tuning below. Present only with the optimization sub-control.
        self.held = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in held_vectors) if self.show_optimization else ()
        self.nh = len(self.held)
        # a held interval being added rides as a pending draft column (blank green cells + a "?"
        # ratio) until its vector is filled in, like the comma / interest draft. Gated on the
        # optimization sub-control, since the held column only exists there.
        self.pending_held = list(self.pending_held) if (self.pending_held is not None and self.show_optimization) else None
        self.nh_shown = self.nh + (1 if self.pending_held is not None else 0)
        self.held_ratios = service.comma_ratios(self.held, self.elements)  # vector -> "num/den" (the shared renderer)
        # a manual generator-tuning override drives the maps directly; otherwise the scheme's
        # optimum (holding the held intervals just), recomputed every build — optimization is
        # always on. A stale override whose generator count no longer matches the mapping (a
        # rank change) falls back to the optimum.
        if generator_tuning is not None and len(generator_tuning) == len(self.state.mapping):
            self.tun = service.tuning_from_generators(self.state.mapping, generator_tuning, self.elements)
        else:
            # a typed target-list override retunes the optimum (minimize over THOSE intervals), so
            # the grid's auto-optimized tuning tracks the displayed targets, not just the named set
            self.tun = service.tuning(self.state.mapping, self.tuning_scheme, self.elements, self.nonprime_approach, held=self.held_ratios,
                                 prescaler_override=self.custom_prescaler, targets=target_override,
                                 weights_override=self.custom_weights)
        self.target_weights = service.interval_weights(self.state.mapping, self.tuning_scheme, self.targets,
                                                  prescaler_override=self.custom_prescaler,
                                                  domain_basis=self.elements,
                                                  weights_override=self.custom_weights)  # the damage row's 𝒘
        # the target damage list is the scheme-weighted 𝐝 = |𝐞|·W (the same weights shown in the
        # weight row and minimized by the optimizer), so it — and the optimization tile's mean damage
        # over it — tracks the unity/complexity/simplicity slope rather than staying plain |error|.
        self.target_sizes = service.interval_sizes(self.tun, self.targets, self.elements, weights=self.target_weights)
        self.held_mapped = service.mapped_intervals(self.state.mapping, self.held_ratios, self.elements)  # M·held (gen coords)
        self.held_sizes = service.interval_sizes(self.tun, self.held_ratios, self.elements)  # tempered/just/error sizes
        # a full-rank temperament (n=0) carries only the trivial zero comma; show nothing, not a "1/1"
        self.comma_ratios = service.comma_ratios(self.state.comma_basis, self.elements) if self.state.n else ()
        self.nc = len(self.comma_ratios)  # the real commas (those that define the temperament)
        self.mapped_commas = service.mapped_commas(self.state.mapping, self.state.comma_basis)  # M·commas = 0 (vanish)
        self.comma_sizes = service.interval_sizes(self.tun, self.comma_ratios, self.elements)  # comma sizes (tempered ~0)
        # the unchanged interval basis U = nullspace(P − I): the projection P's eigenvalue-1
        # eigenvectors (the intervals held exactly just). When projection is on, U consolidates
        # with the comma basis C into one "unrotated vector basis" column V = C|U — the comma
        # sub-columns then the unchanged ones — and its eigenvalue list λ (0 per comma, 1 per
        # unchanged) becomes the scaling-factors row above the interval-vectors row. U is
        # derived/read-only (only C stays editable), so the V view also freezes the comma
        # +/−/drag and the pending draft (a structural edit would change the rank, hence U). Gated
        # on there being a comma to merge with (n > 0). Its mapped / sized / complexity twins are
        # precomputed so the V value tiles read one geometry, exactly as the comma column's do.
        # the unchanged basis U from the tuning's held interval basis: r columns, the h held
        # intervals (known) padded with None (dashed) for what the tuning doesn't pin. So the V =
        # C|U column and the scaling row track the held intervals / established-projection chooser.
        # the unchanged half U (vectors, ratios, M·U, sizes, complexities — dash-aware) is assembled
        # ONCE by service.unchanged_interval_data and shared with the plain text (see
        # plain_text_values), so the consolidated V = C|U reads identically as a grid and as inline
        # EBK text. None only when projection is off. NB it stays present at full rank (n = 0, just
        # intonation): nothing is tempered, so P = I and U is the FULL basis of all d primes (C
        # empty) — the column shows that complete unchanged basis rather than collapsing, and the
        # comma + (still shown) adds a first comma back.
        _udata = (service.unchanged_interval_data(self.state, self.held_basis_ratios, self.tun,
                                                  self.tuning_scheme, self.elements, self.custom_prescaler)
                  if (show_temp and show_tuning and self.settings["projection"]) else None)
        self.show_unchanged = _udata is not None
        self.nu = len(_udata.basis) if self.show_unchanged else 0
        if _udata is not None:
            self.unchanged_basis, self.unchanged_ratios = _udata.basis, _udata.ratios
            self.unchanged_mapped, self.unchanged_sizes = _udata.mapped, _udata.sizes
            self.unchanged_complexities = _udata.complexities
        else:
            self.unchanged_basis = None
            self.unchanged_ratios = self.unchanged_mapped = self.unchanged_complexities = ()
            self.unchanged_sizes = service.IntervalSizes((), (), (), ())
        # A comma − hover RAISES the rank, so in projection the U half grows: a held interval is BORN.
        # Compute the new (higher-rank) projection's unchanged basis and APPEND its surplus interval,
        # so every U loop + the V geometry render it for free; a green post-pass below tints it. (Only
        # the comma − hover: its dual mapping-row DRAFT can't compute the born U — the generator isn't
        # typed yet.) It vanishes nothing — a held interval has tempered = just, error 0 — so the
        # appended sizes come straight from the new projection.
        self.born_u = self.ghost_row and self.show_unchanged
        if self.born_u:
            tun_new = service.tuning(self.ghost_new.mapping, self.tuning_scheme, self.elements,
                                     self.nonprime_approach, held=self.held_basis_ratios,
                                     prescaler_override=self.custom_prescaler)
            ud_new = service.unchanged_interval_data(self.ghost_new, self.held_basis_ratios, tun_new,
                                                     self.tuning_scheme, self.elements, self.custom_prescaler)
            if ud_new is not None and len(ud_new.basis) > self.nu:
                bratio = ud_new.ratios[-1]  # None when the born held interval is irrational (dashed)
                bm = service.mapped_intervals(self.state.mapping, (bratio,), self.elements) if bratio is not None else None
                self.unchanged_basis = tuple(self.unchanged_basis) + (ud_new.basis[-1],)
                self.unchanged_ratios = tuple(self.unchanged_ratios) + (bratio,)
                self.unchanged_mapped = tuple(tuple(row) + (bm[i][0] if bm is not None else None,) for i, row in enumerate(self.unchanged_mapped))
                self.unchanged_complexities = tuple(self.unchanged_complexities) + (ud_new.complexities[-1],)
                s, n = self.unchanged_sizes, ud_new.sizes
                self.unchanged_sizes = service.IntervalSizes(
                    tuple(s.tempered) + (n.tempered[-1],), tuple(s.just) + (n.just[-1],),
                    tuple(s.errors) + (n.errors[-1],), tuple(s.damage) + (n.damage[-1],))
                self.nu += 1
            else:
                self.born_u = False
        # a comma being added is shown as a pending draft column to the right of the real
        # ones: blank green cells and a "?" quantity until it is a valid independent comma
        # (then it commits and the mapping re-ranks). It is not a real comma, so it does
        # not enter the nullity, the mapping, or the sizes — only the displayed column count.
        # (Suppressed under the consolidated V view, where comma structural edits are frozen.)
        self.pending = (list(pending_comma)
                        if pending_comma is not None else None)
        # a green comma COLUMN rides at index nc — an editable draft (pending) or a non-editable
        # ghost (mapping − hover born comma); `comma_draft` gates the shared emission, `ghost_comma`
        # picks editable-vs-read-only within it.
        self.comma_draft = self.pending is not None or self.ghost_comma
        self.nc_shown = self.nc + (1 if self.comma_draft else 0)
        # the V column's shown sub-columns: the comma sub-columns (with any pending draft) then
        # the u unchanged sub-columns (0 off-projection). One geometry for the width, the gridline
        # fan, the EBK marks and every value tile that renders over the consolidated column.
        self.nv_shown = self.nc_shown + self.nu
        # at full rank (no comma sub-columns: n = 0 and no pending draft) the comma half would
        # collapse to zero width, squishing the "nullity" count caption to one character per line
        # and dropping the "n = 0" tally. Reserve a comma-half stub wide enough for "nullity" on a
        # single line: the nullity count + caption sit in it, and the unchanged half is pushed right
        # of it (comma_left), so the space where the commas were "remains". The stub is held OUTSIDE
        # the EBK matrix (matrix_span subtracts it on the left) so the bracket still hugs U.
        self.empty_comma_w = (_min_width_for_lines("nullity", 1)
                              if (self.show_unchanged and self.nc_shown == 0) else 0)
        # under the consolidated view EVERY tile of this column reads as the unrotated vector list
        # V = C|U, not the bare comma basis C: the column title, each tile's name ("comma basis" →
        # "unrotated vector list"), its symbol (C → V, in the caption loop) and its per-column labels
        # (𝐜 → 𝐯, in the col-label loop). The "(made to vanish!)" note is dropped — only the comma
        # half of V vanishes now, and the scaling-factors row's λ = 0 already marks which sub-columns.
        # (The column TITLE is renamed where col_header is built, below.)
        if self.show_unchanged:
            for (rk, ck), name in list(self.effective_captions.items()):
                if ck == "commas":
                    renamed = name.replace("comma basis", "unrotated vector list").replace(" (made to vanish!)", "")
                    # where the rename leaves "list" twice (e.g. "…unrotated vector list interval
                    # size list") it reads silly, so drop the FIRST one: "unrotated vector list" → "…vector"
                    if renamed.count("list") > 1:
                        renamed = renamed.replace("unrotated vector list", "unrotated vector", 1)
                    self.effective_captions[(rk, ck)] = renamed
        # other intervals of interest: a user-built set held as vectors and edited like
        # the comma basis (editable vector cells). Normalize each vector to the current d
        # (pad/trim) so a domain change can't misalign them, then derive the ratios the
        # quantities row shows and the mapping/sizes the lower rows show. It carries no
        # damage row and contributes tiles only when populated, so an empty column adds no
        # panels or fold toggles — just its header and a single straight axis rule.
        self.interest = tuple(tuple(m[p] if p < len(m) else 0 for p in range(self.d)) for m in self.interest)
        self.mi = len(self.interest)
        # an interval of interest being added rides as a pending draft column to the right of the
        # committed ones (blank green cells + a "?" ratio), exactly like the pending comma, until its
        # vector is filled in (then it commits). The draft is not a real interval, so it stays out
        # of the ratios/sizes/complexity below — only the displayed column count grows.
        self.pending_interest = list(self.pending_interest) if self.pending_interest is not None else None
        self.mi_shown = self.mi + (1 if self.pending_interest is not None else 0)
        # the chapter-9 domain basis element draft: with the nonstandard-domain box on, a typed-in
        # new basis element rides as a green ?/? column to the right of the d real elements (exactly
        # like the pending comma), until a valid rational fills it (then it commits, added held
        # just). It is not a real element — no mapping/tuning/count — so the matrix rows still
        # iterate self.d and leave its column empty; only the displayed domain width grows by one.
        self.element_draft = self.show_nonstandard_domain and self.pending_element is not None
        self.d_shown = self.d + (1 if self.element_draft else 0)
        self.interest_ratios = service.comma_ratios(self.interest, self.elements)  # vector -> "num/den" (shared renderer)
        self.interest_mapped = service.mapped_intervals(self.state.mapping, self.interest_ratios, self.elements)
        self.interest_sizes = service.interval_sizes(self.tun, self.interest_ratios, self.elements)
        # the − hover ghost's DERIVED values (now that the tuning + interval sets are resolved). The
        # ghost is the newborn row/column of self.ghost_new, so its derived cells are that entry's
        # mapped images / sizes — lifted from the post-remove temperament, the same service calls the
        # real rows/columns use, indexed at the newborn ([-1], the fresh-token surplus).
        if self.ghost_row and self.ghost_new is not None:
            nm = self.ghost_new.mapping
            def _newborn_mapped(ratios):  # the newborn generator's image of each interval ([-1] row);
                # per-ratio so a DASHED (None) unchanged interval maps to None (DASH), not a crash
                return tuple(service.mapped_intervals(nm, (r,), self.elements)[-1][0] if r is not None else None
                             for r in ratios)
            self.ghost_row_mapped = {
                key: _newborn_mapped(ratios)
                for key, ratios in (("targets", self.targets), ("interest", self.interest_ratios),
                                    ("held", self.held_ratios), ("commas", self.comma_ratios),
                                    ("unchanged", self.unchanged_ratios))}
        elif self.ghost_comma and self.ghost_comma_ratio:
            # the born comma down the mapping rows: M_current[i]·newborn — 0 for every SURVIVING row
            # (the rank-reduced mapping still tempers it out), nonzero only on the removed row (which
            # reds over it). And its just size (it vanishes in the new temperament, so tempered 0).
            col = service.mapped_intervals(self.state.mapping, (self.ghost_comma_ratio,), self.elements)
            self.ghost_comma_mapped = tuple(row[0] for row in col)
            self.ghost_comma_just = service.interval_sizes(self.tun, (self.ghost_comma_ratio,), self.elements).just[0]
            # its complexity 𝒄 = ‖𝐿·comma‖q, the same service call the committed commas use (_resolve_complexities)
            self.ghost_comma_complexity = service.interval_complexities(
                self.state.mapping, self.tuning_scheme, (self.ghost_comma_ratio,),
                prescaler_override=self.custom_prescaler, domain_basis=self.elements)[0]
        # a stable id-token per column of each interval list (and per mapping ROW), matched against
        # the previous render (prev_ids): a within-list reorder keeps a column's token, so all its
        # cells keep their ids and the reconciler slides them to the new x — and a MID-LIST removal
        # keeps every survivor's id, so the remove-preview reds exactly the removed column/row, not
        # whichever one happens to sit last. Fresh (no prev) numbers each list by index, so every
        # cell id is unchanged until the first reorder/removal. The identity key for the interval
        # lists is the RATIO, not the vector: a domain ± re-dimensions the vector (a 5-limit
        # target's 3-tall vector becomes 2-tall), so matching by vector read every shared target as
        # a whole-list delete; the ratio is the same interval across domains, so a shared column
        # keeps its token and only the genuinely-dropped intervals (the lost prime's) read as
        # removed. Commas key by ratio too (each comma's − removes ANY one, so removal attribution
        # needs identity even though a reorder is unobservable); only the COMMITTED commas are keyed
        # — a pending draft rides at pending_col_token. The mapping rows ("gens") key by the row
        # tuple itself: remove_mapping_row keeps the survivors verbatim, so the hovered row's −
        # reds that row, while a re-rank that rewrites every row falls back to positional claiming
        # (see assign_column_tokens) and reads as "survivors move, last row goes". The generator
        # detempering columns are the generators seen from the comma side — one column per mapping
        # row — so they SHARE the gens identity.
        # claim_unmatched is on for the two BASIS groups only (commas, gens): a re-solve rewrites
        # their surviving entries in place, so unmatched new entries positionally claim freed slots
        # (amber) rather than reading as remove-plus-recreate. The interval SETS stay strict: a
        # brand-new ratio is never "the same column as" a dropped one, so a family switch reds it.
        self._col_ids = {
            name: assign_column_tokens(self.prev_ids.get(name), keys, claim_unmatched=claim)
            for name, keys, claim in (("targets", self.targets, False),
                                      ("held", self.held_ratios, False),
                                      ("interest", self.interest_ratios, False),
                                      ("commas", self.comma_ratios, True),
                                      ("gens", tuple(tuple(row) for row in self.state.mapping), True))
        }
        self._col_ids["detempering"] = self._col_ids["gens"]

    def _resolve_complexities(self) -> None:
        """Resolve the per-column complexity lists and the prescaler matrix 𝑋."""
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

    def _declare_interval_column_tiles(self):
        """Declare the interest/held/detempering column tiles (and resolve the detempering data)."""
        # the WHOLE column declares on the SHOWN count (committed + any open draft) — so opening a
        # draft (even the first interval, with nothing committed yet) declares every row the column
        # crosses, and the draft greens top-to-bottom across all of them, exactly as the comma and
        # target columns do. The committed-cell loops emit nothing while the count is 0; each row's
        # pending slot fills the draft column. (Gating the derived rows on the committed count
        # instead left a first draft with blank panels in 9 of the rows — the bug this fixes.)
        interest_tiles = ()
        if self.mi_shown:
            interest_tiles += (
                ("block:vec:interest", "vectors", "interest"),
                ("block:interest", "quantities", "interest"),
                ("block:imapped", "mapping", "interest"),
                ("block:tuning:interest", "tuning", "interest"),
                ("block:just:interest", "just", "interest"),
                ("block:retune:interest", "retune", "interest"),
                ("block:urow:interest", "units", "interest"),  # the units row's /1 over the interest column
                ("block:prescaling:interest", "prescaling", "interest"),
                ("block:complexity:interest", "complexity", "interest"),
            )
        # the held interval column's tiles: a user-editable interval list, like the intervals of
        # interest — declared on the shown count too, so a draft greens every derived row.
        held_tiles = ()
        if self.nh_shown:
            held_tiles += (
                ("block:held", "quantities", "held"),
                ("block:vec:held", "vectors", "held"),
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
        # basis / target list. An independent tiles toggle, riding between domain primes and commas.
        self.detempering_vectors = service.generator_detempering(self.state.mapping) if self.show_detempering else ()
        # the detempering intervals' sizes under the tuning: the tempered sizes ARE the generator
        # tuning map (𝒕D = 𝒈, since each D tempers to its generator), with just and retuning sizes
        # like any interval set. gens is the detempering as ratio strings (service.generators = D).
        self.detempering_sizes = service.interval_sizes(self.tun, self.gens, self.elements) if self.show_detempering else None
        detempering_tiles = (
            ("block:detempering", "quantities", "detempering"),
            ("block:vec:detempering", "vectors", "detempering"),
            ("block:mapped_detempering", "mapping", "detempering"),  # 𝑀D = 𝐼 (gated on identity_objects)
            ("block:tuning:detempering", "tuning", "detempering"),
            ("block:just:detempering", "just", "detempering"),
            ("block:retune:detempering", "retune", "detempering"),
            ("block:prescaling:detempering", "prescaling", "detempering"),
            ("block:complexity:detempering", "complexity", "detempering"),
            ("block:urow:detempering", "units", "detempering"),
        ) if self.show_detempering else ()
        # the canonical-mapping row's mapped lists — 𝑀_C applied to each column's basis, the
        # canonical-form twins of the mapping row's 𝑀·X tiles (read-only, surfaced when a non-
        # canonical form is chosen). 𝑀_C·D = 𝐹 (𝐅𝑀 = 𝑀_C and 𝑀D = 𝐼); 𝑀_C·C vanishes to 𝑂; Y_C = 𝑀_C·T.
        self.canon_mapped = service.mapped_intervals(self.canon_mapping, self.targets, self.elements)
        self.canon_held_mapped = service.mapped_intervals(self.canon_mapping, self.held_ratios, self.elements)
        self.canon_interest_mapped = service.mapped_intervals(self.canon_mapping, self.interest_ratios, self.elements)
        self.canon_mapped_commas = service.mapped_commas(self.canon_mapping, self.state.comma_basis)
        self.canon_mapped_detempering = (service.mapped_commas(self.canon_mapping, self.detempering_vectors)
                                         if self.show_detempering else ())
        # 𝑀_C·U for the consolidated V = C|U column's unchanged half (None where U is dashed), shaped
        # [canon row][U column] like the mapping row's unchanged_mapped
        _canon_u = [None if (self.unchanged_basis is None or self.unchanged_basis[j] is None)
                    else tuple(row[0] for row in service.mapped_commas(self.canon_mapping, (self.unchanged_basis[j],)))
                    for j in range(self.nu)]
        self.canon_unchanged_mapped = tuple(
            tuple((None if _canon_u[j] is None else _canon_u[j][i]) for j in range(self.nu))
            for i in range(self.rc))
        return interest_tiles, held_tiles, detempering_tiles

    def _resolve_projection_data(self, show_tuning) -> None:
        """Resolve the projection/embedding matrices and the projected vector lists (domain + superspace)."""
        # the rational tempering projection P = GM and its generator embedding G (the projection
        # sub-control of tuning tiles): P is a d×d operator over the domain primes, G a d×r matrix
        # whose columns are the held tuning's generators as fractional vectors. Both are built from
        # the tuning's held interval basis (self.held_basis_ratios) — so P = GM. service returns None
        # when the tuning is NOT a full rational projection (it holds fewer than r rational intervals,
        # or a degenerate basis): the box then renders TOTALLY DASHED rather than asserting a tuning
        # the optimum doesn't have. The band/tiles are present whenever the projection toggle is on
        # (self.show_projection), so the dashed P/G show — they aren't dropped, only dashed.
        self.show_projection = show_tuning and self.settings["projection"]
        # MG = I (and superspace M_LGL = I) ALSO read as the generator embedding once the projection
        # feature is on — P·D = GMD = G since M·D = I — so their caption gains "/ embedding":
        # "mapped generators" → "mapped generator(s / embedding)" (the mockup's projection-on label).
        if self.show_projection:
            for rc in (("mapping", "gens"), ("ss_mapping", "ssgens")):
                cap = self.effective_captions.get(rc)
                if cap and cap.endswith("generators"):  # "…generators" → "…generator(s / embedding)"
                    self.effective_captions[rc] = cap[:-1] + "(s / embedding)"
        self.projection_matrix = (service.tuning_projection(self.state, self.held_basis_ratios)
                                  if self.show_projection else None)
        self.embedding_matrix = (service.tuning_embedding(self.state, self.held_basis_ratios)
                                 if self.show_projection else None)
        # the projected vector lists riding the projection row band: P applied to each column's
        # interval vectors. P·D is the generator embedding G (P·D = GMD = G, since M·D = I); P·H = H
        # (the held intervals are P's eigenvalue-1 directions); P·T / P·interest send each target /
        # interest interval to its tempered fractional vector. Rationals (Fraction entries) so the
        # cells show "1/4" like P itself; () / None when the tuning isn't a full rational projection,
        # so the tiles dash in lockstep with P (projection_rationals None ⟺ projection_matrix None).
        self.projection_rationals = (service.projection_matrix_rationals(self.state, self.held_basis_ratios)
                                     if self.show_projection else None)
        self.proj_detempering = service.project_vectors(self.projection_rationals, self.detempering_vectors)
        self.proj_held = service.project_vectors(self.projection_rationals, self.held)
        self.proj_targets = service.project_vectors(self.projection_rationals, self.target_vectors)
        self.proj_interest = service.project_vectors(self.projection_rationals, self.interest)
        # the chapter-9 superspace projection tiles (only when the superspace columns show): G_L→s the
        # embedding from the superspace generators to the subspace elements (d×rL), P_L→s = G_L→s·M_L the
        # projection from the superspace to the subspace (d×dL). Display-string grids, None (dashed) in
        # lockstep with P/G when the tuning isn't a full rational projection.
        self.embedding_superspace = (service.superspace_generator_embedding_display(self.state, self.held_basis_ratios)
                                     if (self.show_projection and self.show_superspace) else None)
        self.projection_superspace = (service.superspace_prime_projection_display(self.state, self.held_basis_ratios)
                                      if (self.show_projection and self.show_superspace) else None)
        # the chapter-9 superspace projection row P_L = G_L·M_L (its own row band, the superspace analogue
        # of the on-domain projection row): a dL×dL operator over the superspace primes, present when the
        # projection toggle is on AND the superspace shows. None (totally dashed) in lockstep with P when
        # the tuning isn't a full rational projection — service.superspace_tuning_projection mirrors
        # service.tuning_projection, built from the same held basis lifted into the superspace.
        self.show_ss_projection = self.show_projection and self.show_superspace
        self.ss_projection_matrix = (service.superspace_tuning_projection(self.state, self.held_basis_ratios)
                                     if self.show_ss_projection else None)
        # the superspace projection row's other column tiles — the chapter-9 analogues of the on-domain
        # projection-row tiles, each P_L applied to a list LIFTED into the superspace (or, for G_L, the
        # held basis): G_L the dL×rL embedding (P_L = G_L·M_L), P_L·B_Ls the projected subspace basis
        # elements (P_L·B_L), and P_L·D_L / P_L·C_L / P_L·H_L / P_L·T_L / P_L·interest the projected lifted
        # lists. G_L as display strings; the rational P_L drives project_vectors. None / () (dashed) in
        # lockstep with P_L when the tuning isn't a full rational projection.
        self.ss_embedding_matrix = (service.superspace_tuning_embedding(self.state, self.held_basis_ratios)
                                    if self.show_ss_projection else None)
        self.ss_projection_rationals = (service.superspace_projection_matrix_rationals(self.state, self.held_basis_ratios)
                                        if self.show_ss_projection else None)
        _lift = lambda vs: service.lift_vectors_to_superspace(self.elements, vs)
        _ssp = self.ss_projection_rationals
        self.ss_proj_basis = service.project_vectors(_ssp, service.basis_in_superspace(self.elements))  # P_L·B_Ls (d cols)
        # P_L·D_L projects the LIFTED DOMAIN detempering (r cols) — unlike the on-domain P·D = G, the
        # lifted D_L is not M_L's right inverse (it is dL×r, not dL×rL), so this is NOT the embedding G_L
        # (which lives over the ssgens column). It is the chapter-9 "projected generator detempering".
        self.ss_proj_detempering = service.project_vectors(_ssp, _lift(self.detempering_vectors))
        self.ss_proj_held = service.project_vectors(_ssp, _lift(self.held))                                # P_L·H_L = H_L
        self.ss_proj_targets = service.project_vectors(_ssp, _lift(self.target_vectors))                   # P_L·T_L
        self.ss_proj_interest = service.project_vectors(_ssp, _lift(self.interest))                        # P_L·interest
        # P_L·V over the consolidated V = C|U column (show_unchanged): the comma half vanishes (P_L·C = 0)
        # and each unchanged interval is held (P_L·𝐮 = 𝐮), so the row shows the unchanged basis LIFTED into
        # the superspace — None entries (a dashed unchanged direction) pass through as None (dashed cell).
        self.ss_unchanged = tuple(
            (service.lift_vectors_to_superspace(self.elements, (ub,))[0] if ub is not None else None)
            for ub in (self.unchanged_basis if self.show_unchanged else ()))
        # the same unchanged half mapped into the superspace GENERATORS (M_s→L·𝐮) — the ss_mapping row's
        # share of the consolidated V column, the superspace twin of the on-domain unchanged_mapped
        # (M·𝐮). The comma half maps to 𝟎 (handled in the lists loop); this fills the U half. None
        # (a dashed unchanged direction) passes through as None, exactly like ss_unchanged above.
        self.ss_unchanged_mapped = tuple(
            (service.map_vectors_into_superspace_generators(self.state, (ub,))[0] if ub is not None else None)
            for ub in (self.unchanged_basis if self.show_unchanged else ()))

    def _declare_tiles(self, interest_tiles, held_tiles, detempering_tiles) -> None:
        """Declare the projection-row column tiles and assemble the authoritative tile set."""
        # the projection row's column tiles, each gated on its column being present exactly like the
        # vectors-row tile it projects (and overall on the projection toggle): the quantities/units
        # spine, then P·D / P·T / P·H / P·interest. Declared here (not in the static TILES) so the
        # conditional columns drop their projected tile with the column, cells/brackets/marks and all.
        projection_col_tiles = ()
        if self.show_projection:
            projection_col_tiles += (
                ("block:proj:quantities", "projection", "quantities"),
                ("block:proj:units", "projection", "units"),
            )
            if self.show_detempering:
                projection_col_tiles += (("block:proj:detempering", "projection", "detempering"),)
            if self.targets_editable:  # present whenever the targets column is (col_open gates it),
                # like the other ("*","targets") tiles — so P·T shows an empty [] alongside them when
                # the list is empty, never a partial state (PT missing while the rest show []). Dropped
                # in all-interval (Tₚ = I) with the other product-with-T tiles, since P·Tₚ = P.
                projection_col_tiles += (("block:proj:targets", "projection", "targets"),)
            if self.nh_shown:
                projection_col_tiles += (("block:proj:held", "projection", "held"),)
            if self.mi_shown:
                projection_col_tiles += (("block:proj:interest", "projection", "interest"),)
            if self.show_superspace:  # G_L→s / P_L→s ride the ssgens / ssprimes columns (between G and P)
                projection_col_tiles += (
                    ("block:proj:ssgens", "projection", "ssgens"),
                    ("block:proj:ssprimes", "projection", "ssprimes"),
                )
        # the SUPERSPACE projection row's column tiles, mirroring projection_col_tiles over the superspace:
        # the embedding G_L (ssgens) and the projected subspace basis P_L·B_Ls (primes) always ride the row,
        # then P_L·D_L / P_L·C_L / P_L·T_L / P_L·H_L / P_L·interest follow their column exactly as the on-domain
        # P·D / P·V / P·T / P·H / P·interest do. ((ss_projection, ssprimes/quantities/units) are the static
        # SUPERSPACE_TILES.) Declared here so a conditional column drops its projected tile with it.
        ss_projection_col_tiles = ()
        if self.show_ss_projection:
            ss_projection_col_tiles += (
                ("block:ssproj:ssgens", "ss_projection", "ssgens"),   # G_L (the embedding, dL×rL)
                ("block:ssproj:primes", "ss_projection", "primes"),   # P_L·B_Ls (the projected subspace basis)
            )
            if self.show_unchanged:  # P_L·V over the consolidated V = C|U column (commas vanish, U held)
                ss_projection_col_tiles += (("block:ssproj:commas", "ss_projection", "commas"),)
            if self.show_detempering:
                ss_projection_col_tiles += (("block:ssproj:detempering", "ss_projection", "detempering"),)
            if self.targets_editable:
                ss_projection_col_tiles += (("block:ssproj:targets", "ss_projection", "targets"),)
            if self.nh_shown:
                ss_projection_col_tiles += (("block:ssproj:held", "ss_projection", "held"),)
            if self.mi_shown:
                ss_projection_col_tiles += (("block:ssproj:interest", "ss_projection", "interest"),)
        # the canonical-mapping row's column tiles (the mapped 𝑀_C·X lists), gated on the canon row
        # being surfaced and each on its column being present — exactly like projection_col_tiles, so a
        # conditional column drops its canon tile with it. (canon × primes / gens are the static
        # block:canon / block:form; col_open gates display, this gates declaration off when form is canonical.)
        canon_col_tiles = ()
        if self.show_canon:
            canon_col_tiles += (("block:canon_comma", "canon", "commas"),)  # 𝑀_C·C = 𝑂 (+ V's unchanged half)
            if self.show_detempering:
                canon_col_tiles += (("block:canon_detempering", "canon", "detempering"),)  # 𝑀_C·D = 𝐹
            if self.targets_editable:
                canon_col_tiles += (("block:canon_mapped", "canon", "targets"),)  # Y_C = 𝑀_C·T
            if self.nh_shown:
                canon_col_tiles += (("block:canon_held", "canon", "held"),)  # 𝑀_C·H
            if self.mi_shown:
                canon_col_tiles += (("block:canon_interest", "canon", "interest"),)  # 𝑀_C·interest
        # the optimization controls (power 𝑝 etc.) nest at the bottom of the damage×targets
        # tile (see opt_box below), not in a tile/row of their own
        self.tiles = (COUNTS_TILES + OPTIMIZATION_COUNTS_TILES + DETEMPERING_COUNTS_TILES
                 + SUPERSPACE_COUNTS_TILES
                 + TILES + UNITS_TILES + SUPERSPACE_TILES
                 + interest_tiles + held_tiles + detempering_tiles + projection_col_tiles
                 + ss_projection_col_tiles + canon_col_tiles)
        # The authoritative set of real (row, column) tiles. tile_open() consults it, so a
        # tile's existence lives in ONE place: drop its entry here (via TILES etc.) and it
        # vanishes everywhere — panels, toggles, cells, brackets and marks — with no chance
        # for a stray hardcoded column list to keep drawing a tile that no longer exists.
        self.declared_tiles = {(rkey, ckey) for _bid, rkey, ckey in self.tiles}
        if service.is_all_interval(self.tuning_scheme):
            # all-interval (Tₚ = I): every target-column list that just re-expresses an existing column
            # collapses to a duplicate, so drop it — mapped 𝑀T → 𝑀, prescaled 𝐿T → 𝐿, and each size/error
            # list to its prime map (tempered 𝐚 → 𝒕, just 𝐨 → 𝒋, error 𝐞 → 𝒓). The superspace lifts collapse
            # the same way: the target vectors T_L → B_L (the (ss_vectors, primes) tile) and the mapped
            # targets Y_L → M_s→L (the (ss_mapping, primes) tile), so they drop too — the projection rows'
            # P·T / P_L·T already drop via targets_editable below. The kept target tiles are the target list
            # itself (Tₚ = I), the complexity ‖𝐿‖, and the weight/damage; so the whole column wipes from the
            # mapping row down to the complexity row. Dropping a tile here clears its cells, bracket, caption,
            # panel and fold toggle (never a blank box).
            self.declared_tiles -= {("mapping", "targets"), ("prescaling", "targets"),
                               ("tuning", "targets"), ("just", "targets"), ("retune", "targets"),
                               ("ss_vectors", "targets"), ("ss_mapping", "targets")}
        if not self.show_identity_objects:
            # the identity objects — the trivial self-maps that equal 𝐼 — gate here. Standard domain:
            # the JI mapping 𝑀ⱼ (vectors × primes), 𝑀𝐺 = mapping over its own generators (mapping ×
            # gens) and 𝑀D = the mapped generator detempering (mapping × detempering). Superspace: the
            # JI mapping M_jL (ss_vectors × ssprimes) and M_LgL (ss_mapping × ssgens). The form box's
            # 𝐹⁻¹𝐹 = 𝐼 (canon × canongens) joins them now that the canonical-generators column exists —
            # it surfaces only with the canonical-mapping row (show_canon), the column gating it further.
            # Dropping a tile clears its cells, brackets, caption, symbol, panel and fold toggle; the
            # rows themselves stay for the mapping / B_L / M_L / canonical generators in their other columns.
            self.declared_tiles -= {("vectors", "primes"), ("mapping", "gens"),
                                    ("mapping", "detempering"), ("canon", "canongens"),
                                    ("ss_vectors", "ssprimes"), ("ss_mapping", "ssgens")}
        # the superspace held / interest tiles only exist to lift an actual held / interest list (or
        # an open draft of one) — with none shown (nh_shown / mi_shown == 0) they'd be empty boxes,
        # so drop them (cells, panel, caption, brackets and fold toggle all go with the tile).
        if not self.nh_shown:
            self.declared_tiles -= {("ss_vectors", "held"), ("ss_mapping", "held")}
        if not self.mi_shown:
            self.declared_tiles -= {("ss_vectors", "interest"), ("ss_mapping", "interest")}

    def _define_col_bands(self, show_interval_ratios, show_domain_units, show_temp,
                          show_tuning, show_interest, label_w):
        """Define the column bands (key, natural width, present, collapsible) and the content origin."""
        # Column bands left-to-right: (key, natural width, present, collapsible).
        # Each set-column belongs to a tiles toggle: generators, the domain primes and
        # the commas are the temperament's (shown with temperament_tiles), target-
        # intervals are the tuning's (shown with tuning_tiles), and the other-intervals-
        # of-interest column has its own (shown with interest) -- turning a tile group off
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
        self.col_header = {"quantities": "interval ratios", "units": "units",
                      "canongens": "canonical\ngenerators", "gens": "generators",
                      "ssgens": "superspace\ngenerators", "ssprimes": "superspace\nprimes",
                      "primes": domain_title, "detempering": "generator\ndetempering",
                      "commas": "commas",
                      "held": "held\nintervals", "targets": "target\nintervals",
                      "interest": "other intervals\nof interest"}
        if self.show_unchanged:  # the consolidated column is the unrotated vector list V = C|U
            self.col_header["commas"] = "unrotated\nvector list"
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
                                  if (self.show_header_symbols and show_temp) else 0)
        # M_L / M_jL stack covectors in the ssprimes column with row labels (𝒎ʟᵢ), so it needs
        # the same MATLABEL_W gutter the primes column reserves — without it the labels collide
        # with each row's ⟨ bracket and first cell
        self.matlabel_ssprimes_w = MATLABEL_W_SSPRIMES if (self.show_header_symbols and self.show_superspace) else 0
        # the drag-to-combine row handles ride a gutter to the LEFT of the row labels (the 𝒎ᵢ
        # matlabels), so the primes column reserves room for them — present when the feature is on
        # and there are ≥ 2 generator rows to combine. Balanced by an equal empty right gutter (like
        # the matlabel gutter) so the matrix stays centred in its tile.
        self.row_handle_w = (ROW_HANDLE_W + ROW_HANDLE_GAP) if (
            self.settings.get("drag_to_combine") and show_temp and self.r > 1) else 0
        # the per-mapping-row ET pickers ride the primes column's RIGHT gutter, past each row's ]
        # (one compact chooser per row — see the etpick emission). Reserved whenever the preset
        # choosers show and the mapping renders. This right gutter REUSES the empty space that
        # already balanced the left furniture (handles + 𝒎ᵢ labels); the left is padded out only if
        # the picker is wider than that furniture (etpick_left_pad), so the two gutters stay equal
        # and the matrix stays centred — the pickers take the balancing space, they don't add to it.
        self.etpick_w = (ETPICK_W + ETPICK_GAP) if (self.show_presets and show_temp) else 0
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
            ("quantities", COL_W, show_interval_ratios, True),
            ("units", COL_W, show_domain_units, True),
            # the canonical-generators column rides between the units spine and the generators
            # column (the mockup), surfaced with the canonical-mapping row (show_canon): rc cells
            # wide in the standard EBK-gutter footprint, like the gens column it parallels. It holds
            # the canonical generator ratios (over the quantities row) and 𝐅⁻¹𝐅 = 𝐼 (over the canon row).
            ("canongens", 2 * BRACKET_W + self.rc * COL_W, self.show_canon, True),
            ("gens", 2 * BRACKET_W + self.r * COL_W, show_temp, True),
            # the chapter-9 superspace columns ride between gens and the domain primes — rL
            # cells (superspace generators) and dL cells (superspace primes), each in the
            # standard EBK-gutter footprint like the gens/primes columns they parallel
            ("ssgens", 2 * BRACKET_W + self.rL * COL_W, self.show_superspace, True),
            ("ssprimes", 2 * BRACKET_W + self.dL * COL_W + 2 * self.matlabel_ssprimes_w, self.show_superspace, True),
            ("primes", 2 * BRACKET_W + self.d_shown * COL_W + 2 * self.outer_gutter_w("primes"), show_temp, True),
            ("detempering", 2 * BRACKET_W + self.r * COL_W, self.show_detempering, True),
            ("commas", self._commas_band_w(self.nc_shown), show_temp, True),
            ("held", 2 * BRACKET_W + self.nh_shown * COL_W, self.show_optimization, True),
            ("targets", 2 * BRACKET_W + self.k_shown * COL_W, show_tuning and self.targets_in_use, True),
            # The interest column's tiles hug this content width (32 + mi·COL_W) — no empty
            # padding. Its long two-line title is wider than that, so (like the spine titles) it
            # overhangs the narrow footprint, centred on the column gridline above the tiles, which
            # centre on the same gridline. The gap to its left neighbour widens to keep that overhang
            # clear of the neighbour's title (the gap rule in the loop below). The board height is
            # independent of mi.
            ("interest", 2 * BRACKET_W + self.mi_shown * COL_W, show_interest, True),
        )
        # A fold-toggle node column sits between the row-label gutter and the content
        # (when names show); content starts past it with a clear gap so the tiles
        # never collide with the nodes. Row lines fan from the node's right edge so
        # their gaps match the columns'.
        self.node_x = label_w + GAP
        self.node_edge = self.node_x + TOGGLE  # the node's content-facing (right) edge
        content_x0 = self.node_x + TOGGLE + GAP
        return col_bands, content_x0

    def _define_row_bands(self, show_counts, show_interval_ratios, show_domain_units,
                          show_temp, show_tuning):
        """Define the row bands (key, natural height, present, collapsible, label) and the captioned-row set."""
        # Row bands top-to-bottom: (key, natural height, present, collapsible, label), laid
        # out below by the same running-cursor rule as the columns. Defined here, ahead of
        # that layout, so each column's width can reserve room for its present rows' captions.
        row_bands = (
            ("counts", ROW_H, show_counts, True, "counts"),
            # the interval-ratios row (band key still "quantities") and its spine column ride
            # interval_ratios; its title now reads "interval ratios", forced onto two lines to match
            # the two-line "interval vectors" row title just below it.
            ("quantities", ROW_H, show_interval_ratios, True, "interval\nratios"),
            ("units", ROW_H, show_domain_units, True, "units"),
            # the scaling factors λ = diag(λ) — the projection's eigenvalue list (0 per comma,
            # vanished; 1 per unchanged, held) — a one-row scalar list over the consolidated V
            # column, riding just above the interval-vectors row (the mockup). Present with the
            # projection toggle, exactly when V consolidates (show_unchanged).
            ("scaling_factors", ROW_H, self.show_unchanged, True, "scaling factors"),
            # the interval-vectors row now owns its own toggle (interval_vectors) rather than riding
            # temperament_tiles, so it can show/hide independently of the mapping + domain columns.
            ("vectors", self.d * ROW_H, self.show_interval_vectors, True, "interval vectors"),
            ("canon", self.rc * ROW_H, self.show_canon, True, "canonical mapping"),
            ("mapping", self.r_shown * ROW_H, show_temp, True, "mapping"),
            # the chapter-9 superspace rows sit between mapping and the projection row, the row
            # counterparts of the ssgens / ssprimes columns: ss_vectors holds the dL-tall vector
            # columns (B_L, target/comma vectors, and the JI mapping M_jL = I over its ssprimes
            # column); ss_mapping the rL × dL matrix M_L (plus M_LgL = I over its ssgens column).
            # Both gate on the same nonstandard_domain toggle as the columns, so the bands collapse
            # to nothing whenever the toggle is off; M_jL / M_LgL gate further on identity_objects
            # (see declared_tiles above), but their rows stay for B_L / M_L either way.
            ("ss_vectors", self.dL * ROW_H, self.show_superspace, True, "superspace\ninterval vectors"),
            ("ss_mapping", self.rL * ROW_H, self.show_superspace, True, "superspace\nmapping"),
            # the superspace tempering projection P_L = G_L M_L, a dL × dL matrix over the superspace
            # primes — the chapter-9 analogue of the projection row, framed like M_L. Seats just below
            # the superspace mapping and above the on-domain projection (the mockup). Present with the
            # projection toggle AND the superspace; a None matrix dashes the band (it isn't dropped).
            ("ss_projection", self.dL * ROW_H, self.show_ss_projection, True, "superspace\nprojection"),
            # the rational tempering projection P = GM, a d×d matrix over the domain primes — d rows
            # tall like the interval-vectors row, framed like the mapping. Comes AFTER the superspace
            # rows (the mockup), so its superspace tiles G_L→s / P_L→s sit below B_L / M_L. Present only
            # when service could build it (projection on, tuning tiles on); a None matrix drops the band.
            ("projection", self.d * ROW_H, self.show_projection, True, "projection"),
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
        return row_bands

    def _layout_columns(self, col_bands, content_x0) -> None:
        """Lay the column bands left-to-right (the running-cursor walk): col_x/col_w/content_w/total_w."""
        # each column hugs its content (a long caption widens the footprint), the columns laid
        # left to right a GAP apart — widened to TITLE_MARGIN where two columns' overhanging titles
        # would otherwise collide (see the gap rule at the foot of the loop). The element +/−
        # controls no longer ride inside these tiles (they sit up on the fan's top bus, see
        # plus_stub_x), so no column reserves overhang for one.
        self.col_x, self.col_w, self.content_w, self.col_collapsible, self.open_col_w = {}, {}, {}, {}, {}
        x = content_x0
        first_present = True  # the leftmost column carries a title-clearance floor (see below)
        prev_title_oh = None  # previous present column's title half-overhang (signed); None before the first
        for key, natural, present, collapsible in col_bands:
            if not present:
                continue
            collapsed_col = f"col:{key}" in self.collapsed
            hug_w = max(natural, self._caption_floor(key), self._control_floor(key), self._symbol_floor(key))  # hugs content (+ caption / control / symbol room)
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
            # column gridline; the gap to the neighbour then widens to keep the two titles clear (the
            # rule at the foot of the loop). The grey tile fills the footprint, with content centred
            # within it (see content_x).
            if collapsed_col:
                # Folded to a title strip — sized to read the (widest line of the) title, but capped
                # at the open footprint so collapsing never WIDENS a column: one already narrower than
                # its title (a spine) keeps its width, the title overhanging, instead of ballooning out.
                self.col_w[key] = self.content_w[key] = min(hug_w, _title_w(self.col_header[key]))
            else:
                self.content_w[key] = natural
                self.col_w[key] = hug_w  # the footprint widens for a long caption
            self.col_collapsible[key] = collapsible
            # A title renders unwrapped, centred on its column gridline, so it overhangs a
            # content-hugged column symmetrically by half_oh each side (negative when it fits within
            # the column). Seat each column a GAP from its left neighbour, but open the gap wider where
            # the two columns' overhanging titles would otherwise land within TITLE_MARGIN of each
            # other — so a long title (the interest header) can never overspill into a neighbour's,
            # however narrow either column is. The widening only kicks in on an actual collision: a
            # wide neighbour (its title well inside, half_oh negative) feeds slack in and the gap stays
            # GAP, leaving the common layouts untouched.
            half_oh = _title_w(self.col_header[key]) / 2 - self.col_w[key] / 2
            if prev_title_oh is not None:
                x += max(GAP, TITLE_MARGIN + prev_title_oh + half_oh)
            self.col_x[key] = x
            x += self.col_w[key]
            prev_title_oh = half_oh
        self.total_w = x + GAP

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
        self.canongens_x = self.content_x.get("canongens")  # None when the canonical-generators column is hidden (show_canon off)
        self.ssgens_x = self.content_x.get("ssgens")  # None when the superspace generators column is hidden
        self.ssprimes_x = self.content_x.get("ssprimes")  # None when the superspace primes column is hidden

    def _resolve_tile_extras(self, show_ranges, show_tuning):
        """Reserve the nested tile-control heights (ranges chart, box 𝐋/𝒄/𝒘, optimization box, approach radio)."""
        # The generator tuning-ranges box (the chart + its mode selector) nests at the bottom
        # of the generator tuning map tile when tuning_ranges is on. Its extra height is
        # reserved in the tuning row (below) so the rows beneath drop clear of it rather than
        # the box spilling across them. Determinable up front: it rides the open, uncollapsed
        # gens tile of the (present, unfolded) tuning row.
        self.gtm_chart = (show_ranges and show_tuning and "row:tuning" not in self.collapsed
                     and self.col_open("gens") and "tile:tuning:gens" not in self.collapsed)
        self.gtm_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H) if self.gtm_chart else 0
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
        # the optimization box: a title strip over a row of two controls distributed across the
        # tile's full width — the mean damage (the minimized damage ⟪𝐝⟫ₚ, "power mean", or the
        # all-interval retuning magnitude) and the editable power 𝑝 (each a value above its symbol
        # above its caption). Its height = a title inset + the title + a
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
        self.approach_extra = (RANGE_GAP + 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H) if self.show_approach else 0
        # the weight-slope chooser (U/S/C) is the core of box 𝒘 — like box 𝒄's complexity norm it
        # shows with WEIGHTING itself, not gated on the alt. complexity extra. In all-interval
        # mode the weight is simplicity by construction, not a free choice, so the chooser stays put
        # but greys out (slope_locked), locked to its forced simplicity-weight value. Custom-weight
        # mode greys it the same way — the typed 𝒘 cells supersede the slope, so it isn't a free choice.
        self.slope_ctrl = (self.show_weighting
                      and "row:weight" not in self.collapsed
                      and self.col_open("targets") and "tile:weight:targets" not in self.collapsed)
        self.slope_locked = self.slope_ctrl and (service.is_all_interval(self.tuning_scheme)
                                                 or self.custom_weights_active)
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
        return tile_extra

    def _init_row_geometry(self, header_h):
        """Seat the header/fan anchors and initialize the per-row geometry maps; returns the first row band's top y."""
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
        # row_y (RowBand.y) is the value top (cells/gridlines); tile_top is the grey panel top.
        # self.rows[key] is one RowBand per laid-out row band, folding together the ~17 per-row
        # geometry maps that used to run in parallel (row_y/row_h/tile_h/chart_top/…); see RowBand
        # for the field↔former-dict mapping. The conditional bands (chart_top / int_handle_top /
        # matlabel_top) are None on rows that didn't reserve them — a former `k in self.chart_top`
        # is now `self.rows[k].chart_top is not None`.
        self.rows: dict[str, RowBand] = {}
        self.row_cpick = {}  # the per-comma-column picker band height (interval-vectors row only)
        return rows_top_y

    def _resolve_ptext_strings(self, generator_tuning, target_override) -> None:
        """Build the plain-text value strings from the grid's own derived quantities."""
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
                                                       if self.show_superspace_generators else None),
                                                   # consolidated V = C|U: the plain text appends the
                                                   # unchanged half U to every V tile, matching the grid
                                                   consolidate_v=self.show_unchanged,
                                                   held_basis_ratios=self.held_basis_ratios,
                                                   # decimals off rounds every value in the EBK strings
                                                   # too, so the plain text matches the rounded grid
                                                   decimals=self._decimals,
                                                   # the bare prescaler tile's hand-edited diagonal /
                                                   # matrix override, threaded into the same tuning /
                                                   # weights / complexity / prescaling the grid builds
                                                   custom_prescaler=self.custom_prescaler,
                                                   # the grid's own derived quantities: the text is
                                                   # built FROM these (one tuning solve per build,
                                                   # and the two views structurally cannot diverge)
                                                   derived=service.DerivedQuantities(
                                                       targets=self.targets, tun=self.tun,
                                                       target_weights=self.target_weights,
                                                       target_sizes=self.target_sizes,
                                                       comma_sizes=self.comma_sizes,
                                                       superspace_tun=(self.superspace_tun()
                                                                       if self.show_superspace else None)))
                         if self.show_ptext else {})
        # EBK off: rewrite every plain-text string into plain matrix notation (square braces + a ᵀ on
        # the vector kind), the string twin of the gridded mark swap below — so the two views read
        # identically off as on. A pure display transform on the assembled strings.
        if not self.show_ebk:
            self.ptext_strings = {k: service.ebk_to_simple_matrix(v) for k, v in self.ptext_strings.items()}

    def _layout_rows(self, row_bands, tile_extra, rows_top_y, show_charts) -> None:
        """Lay the row bands top-to-bottom (the running-cursor walk): row_y/tile_h/total_h + the fan-out bus."""
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
            has_matlabel = (self.show_header_symbols and key in COL_LABELED_ROWS and not folded)
            head_default = TOGGLE + 2 * TOGGLE_INSET - PAD  # toggle's natural head reservation
            # the drag-to-combine handles ride a band at the TOP of the interval-vectors head, ABOVE
            # the column labels (so the grip sits OUTSIDE the c₁/𝒕ᵢ labels, mirroring the row handle
            # to the left of the 𝒎ᵢ labels). Present only when the feature is on and some interval
            # column that is OPEN has ≥ 2 entries to combine — the head grows by the band so the tile
            # is taller. The col_open guard matters now the interval-vectors row can show while a
            # column is hidden (it answers to interval_vectors, not the columns' temperament/tuning
            # toggles), so a closed column's count must not reserve an empty handle band.
            int_handle = (key == "vectors" and not folded and self.settings.get("drag_to_combine")
                          and ((self.nc >= 2 and self.col_open("commas"))
                               or (self.k >= 2 and not self.all_interval and self.col_open("targets"))
                               or (self.nh >= 2 and self.col_open("held"))
                               or (self.mi >= 2 and self.col_open("interest"))))
            handle_band = (ROW_HANDLE_W + ROW_HANDLE_GAP) if int_handle else 0
            # the matlabel needs MATLABEL_H + 2*PAD of head to sit centred with breathing room
            base_head = 0 if folded else max(head_default, MATLABEL_H + 2 * MATLABEL_PAD if has_matlabel else head_default)
            head = base_head + handle_band  # the handle band rides above the toggle/label head
            # framing bands stand off the cells by FRAME_GAP: a top bracket (FRAME_H)
            # and a taller bottom curly brace (BRACE_H, with room for its spike). Each band
            # also reserves FRAME_OVERHANG beyond the marks for the outer [ ] / column rules,
            # which overhang the marks by that much (see bracket's fit branch) — without it the
            # overhang would bleed into the toggle head above and the symbol/caption stack below.
            top_frame = (FRAME_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
            bot_frame = (BRACE_H + FRAME_GAP + FRAME_OVERHANG) if framed else 0
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
            # the ✕ "return to scheme" control. With presets ON it lives INSIDE the established-
            # projection chooser's box (preset_band_h already reserves the extra row via scheme_btn), so
            # no band here. With presets OFF there is no chooser, so it gets its own small box on this row.
            schemebtn = (self.control_region_band_h(SCHEME_BTN_SQ)
                         if (key == "projection" and self.settings["projection"] and not self.show_presets and not folded) else 0)
            # the <choose form> dropdown rides INSIDE the temperament chooser's box (preset_band_h
            # reserves the extra row via _preset_form_label), so it needs NO band of its own when
            # presets are on. Only with presets OFF — no chooser box to ride in — does it get its own.
            formctrl = (self.formchooser_band_h(key)
                        if (self.show_form_controls and not self.show_presets
                            and key in FORM_CHOOSER_ROWS and not folded) else 0)
            # the per-comma-column pickers ride a band just below the ⟩ foot of the comma matrix
            # (above the symbol/caption stack and the whole-temperament chooser): one compact comma
            # chooser per real comma column, plus one on a green draft column being added. Reserved on
            # the interval-vectors row when the preset choosers show, the commas COLUMN is open, and
            # there's a comma (or a draft adding the first) to pick — a full-rank temperament with no
            # draft has none. The col_open guard matters now the interval-vectors row can show while
            # the commas column is hidden (it answers to interval_vectors, not temperament_tiles): the
            # picker cells (tile_open("vectors","commas")) would not emit, so reserve no empty band.
            cpick = (COMMAPICK_GAP + ROW_H) if (key == "vectors" and self.show_presets
                                               and self.col_open("commas")
                                               and (self.nc > 0 or self.pending is not None) and not folded) else 0
            ptext = self.ptext_band(key, folded)
            # open a consistent gap between the stacked in-tile bands: pad each present one by BAND_GAP
            # (its content centres, so adjacent bands clear each other) — values, symbol/equivalence,
            # name, units, plain text and the control boxes below no longer crowd
            if sym:   sym += BAND_GAP
            if cap:   cap += BAND_GAP
            if uni:   uni += BAND_GAP
            if ptext: ptext += BAND_GAP
            row_h = STRIP if folded else natural
            # the chart band sits below the top frame; None (no band) unless the row is charted
            chart_top = (y + head + top_frame) if charted else None
            # the grip band rides the very top of the head, above the column labels; None unless reserved
            int_handle_top = (y + (handle_band - ROW_HANDLE_W) // 2) if int_handle else None
            # col-label sits below the handle band (when present), centred in the remaining head —
            # roughly equidistant from the band/tile-top above and the bracket below; None unless reserved
            matlabel_top = (y + handle_band + (base_head - MATLABEL_H) // 2) if has_matlabel else None
            self.row_cpick[key] = cpick  # the comma-picker band sits below the brace, above the symbol slot
            tile_h = head + top_frame + chart_band + row_h + bot_frame + cpick + sym + cap + uni + pre + ptext + formctrl + schemebtn
            # a row with a nested tile-control (ranges chart, alt-complexity chooser, optimization
            # block) adds its reserved height here, so the rows below drop clear of it and every
            # tile in the row grows to the same height (the row stays one uniform band)
            tile_h += tile_extra.get(key, 0)
            self.rows[key] = RowBand(
                y=y + head + top_frame + chart_band,  # values sit below toggle head, top frame, chart
                h=row_h,
                label=label,
                collapsible=collapsible,
                tile_h=tile_h,
                tile_top=y,
                frame=bot_frame,        # the symbol/caption stack sits below the bottom brace band
                sym=sym,                # the caption (and bands below it) sit below the symbol slot
                cap=cap,                # the units line and plain-text box sit below the caption
                units=uni,              # the plain-text box and preset chooser sit below the units line
                ptext=ptext,            # the plain-text band, with the preset chooser below it
                pre=pre,                # the preset band, with the <choose form> chooser below it
                schemebtn=schemebtn,    # the ✕ return-to-scheme row, below the preset band
                nsub=round(natural / ROW_H),  # matrix height in cells (fold-independent)
                chart_top=chart_top,
                int_handle_top=int_handle_top,
                matlabel_top=matlabel_top,
            )
            y += tile_h + GAP
        self.total_h = y

        # Each multi-element column runs a single trunk down to the fan-out bus, where it
        # splits into one line per element. The bus sits centred in the whitespace of the GAP
        # above the first row band (FAN below the branch top) -- immediately after the column
        # toggle, mirroring how the rows fan out at node_edge + FAN just after the row toggle.
        # The element +/− controls ride this bus (see below), and the counts row's per-column
        # cardinality simply has the already-split sub-lines threading through it.
        self.fanout_y = self.branch_top_y + self.FAN

    def _init_group_geometry(self) -> None:
        """Define the value-group geometry maps (element names, left edges, counts, ratios) and the +/− stubs."""
        # The value groups share an element name (for cell ids), a left-edge accessor, a fanned
        # element count, and the operand of their just log₂ (a bare prime, or a comma/target
        # ratio). Defined here — ahead of the cells, the EBK pass and the column_axis fan — so the
        # +/− controls, the brackets and the gridlines all read ONE geometry. primes carry a map,
        # commas and targets interval lists.
        self.group_elem = {"gens": "gen", "primes": "prime", "commas": "comma", "targets": "target",
                      "interest": "interest", "held": "held", "detempering": "detempering",
                      "canongens": "cangen", "ssgens": "ssgen", "ssprimes": "ssprime"}
        self.group_left = {"gens": self.gen_left, "primes": self.prime_left, "commas": self.comma_left, "targets": self.target_left,
                      "interest": self.interest_left, "held": self.held_left, "detempering": self.detempering_left,
                      "canongens": self.canongen_left, "ssgens": self.ss_gen_left, "ssprimes": self.ss_prime_left}
        # how many side-by-side cells each group column carries: its element count, so the
        # gridline pass can fan every group column into that many vertical sub-axes (commas
        # count the shown columns, draft included). Keyed identically to group_left/group_elem
        # so a column with cells can never be left out of the fan (the generators-column bug).
        self.group_n = {"gens": self.r, "primes": self.d_shown, "commas": self.nv_shown,
                   "targets": self.k_shown,
                   "interest": self.mi_shown, "held": self.nh_shown, "detempering": self.r,
                   "canongens": self.rc, "ssgens": self.rL, "ssprimes": self.dL}
        self.group_ratio = {  # the just interval ratio each value group is taken over
            "primes": lambda i: service.element_ratio(self.elements[i]),  # a prime "p/1", or a nonprime element "n/d"
            # over V = C|U the comma sub-columns index the comma ratios, the unchanged sub-columns
            # (i ≥ nc) the unchanged interval ratios — so the just/retune closed forms resolve for both
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
        # the basis + rides the stub one ROW_H below the stack (PAST any ?/? element draft, so
        # d_shown not d). It shows whenever the quantities-row primes + does — the standard prime
        # walk (box off, standard limit) OR a typed element draft (nonstandard-domain box on).
        if self.tile_open("vectors", "quantities") and (self.show_nonstandard_domain or self.standard_domain):
            self.row_plus_y["vectors"] = self.vec_top(self.d_shown) + ROW_H / 2
        if self.tile_open("mapping", "quantities") and self.state.n > 0:
            # below the last SHOWN row — so an open draft row pushes the + down past it
            self.row_plus_y["mapping"] = self.map_top(self.r_shown) + ROW_H / 2

    def superspace_tun(self):
        """The chapter-9 superspace tuning, solved at most once per build — the plain-text
        bundle and layout()'s ss tuning rows share this one (expensive) solve."""
        if self._ss_tun is None:
            ss_override = self.superspace_generator_tuning if self.show_superspace_generators else None
            self._ss_tun = service.superspace_tuning(self.state, self.tuning_scheme, self.nonprime_approach,
                                                     generator_override=ss_override)
        return self._ss_tun

    def _caption_floor(self, key: str):
        """the width an open column needs so its captions stay within MAX_CAPTION_LINES,
        widening the tile rather than scaling the font or letting a long name spill;
        zero when names are hidden (no caption renders) so the column keeps its content size"""
        if not self.show_captions:
            return 0
        return max((_min_width_for_lines(self.effective_captions[(rk, key)], MAX_CAPTION_LINES)
                    for rk in self.present_caption_rows
                    if (rk, key) in self.effective_captions and (rk, key) in self.declared_tiles), default=0)

    def _projection_superspace_tail(self) -> str:
        """the superspace decomposition appended to P's equivalence when the superspace block shows
        (per the mockup): P = … = Gₛ→ₗ𝑀ₛ→ₗ. Shared by the build() override and _symbol_floor so the
        widened width and the rendered text agree."""
        return f" = G{SUBSCRIPT_L}→ₛ𝑀ₛ→{SUBSCRIPT_L}" if self.show_superspace else ""

    def _symbol_floor(self, key: str):
        """the width an open column needs so its widest symbol + equivalence fits on ONE line — the
        symbol/equivalence element must never wrap (it widens the tile instead, like a long caption).
        Zero when neither symbols nor equivalences show. P's equivalence (with the superspace tail)
        is the long one this guards; short symbols floor below the natural width, so no effect."""
        if not (self.show_symbols or self.show_equiv):
            return 0
        floor = 0
        for (rkey, ckey), glyph in SYMBOLS.items():
            # declared_tiles (not tile_open) — this runs during column sizing, before row_y exists,
            # exactly like _caption_floor
            if ckey != key or (rkey, ckey) not in self.declared_tiles:
                continue
            equiv = ""
            if self.show_equiv:
                equiv = EQUIVALENCES.get((rkey, ckey), "")
                if self.show_form_subscript and (rkey, ckey) in FORM_EQUIVALENCES:  # the subscripted equation
                    equiv = FORM_EQUIVALENCES[(rkey, ckey)]
                if (rkey, ckey) == ("projection", "primes"):
                    equiv += self._projection_superspace_tail()
            glyph = self._form_subscripted(glyph, rkey, ckey)  # the subscripted symbol
            floor = max(floor, _min_width_for_lines(glyph + equiv, 1, SYMBOL_FONT))
        return floor

    def _form_subscripted(self, glyph: str, rkey: str, ckey: str) -> str:
        """Mark a canonical-form object's glyph with the subscript C when the main mapping is in
        canonical form — inserted after the leading glyph so it composes with any trailing column
        letter / index (𝑀 → 𝑀_C, 𝑀𝐜 → 𝑀_C𝐜, 𝒈 → 𝒈_C), in both tile symbols and matrix row/column
        header labels. Applies by ROW (see FORM_SUBSCRIPT_ROWS): the WHOLE mapping row — so every
        mapped product, including new ones like 𝑀G / 𝑀D, inherits it without per-tile registration —
        plus the two lone generator-basis cells (𝒈, G). Form-invariant rows pass through untouched;
        the canonical-mapping row carries its own static 𝑀_C (its SYMBOLS), not this dynamic one."""
        if (glyph and self.show_form_subscript
                and (rkey in FORM_SUBSCRIPT_ROWS or (rkey, ckey) in FORM_SUBSCRIPT_GENS)):
            return glyph[:1] + SUBSCRIPT_C + glyph[1:]
        return glyph

    def _control_floor(self, key: str):
        """the width an open column needs so its in-tile choosers fit without overhanging the
        column's right edge (e.g. the narrow targets column is widened to seat box 𝒄's wide
        predefined-complexities dropdown); widens the column to enclose them"""
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
        # the ✕ "return to scheme" control (button + caption) rides its own row on the projection /
        # embedding tiles; widen the column only enough to seat that one row (no chooser beside it)
        if key in ("primes", "gens") and self.settings["projection"]:
            floor = max(floor, 2 * BOX_OUTER + SCHEME_CTRL_W)
        return floor

    def content_box(self, key: str):
        """the (x, width) of a column's actual content — the value cells and the brackets/
        axes that hug them, centred within the (possibly wider) tile and footprint"""
        return self.content_x[key], self.content_w[key]

    def tile_box(self, key: str):
        """the (x, width) of a column's grey tile/panel: the full footprint (the panel fills it
        and overhangs by PAD). The caption stack rides this width; content centres within."""
        return self.col_x[key], self.col_w[key]

    def displayed_optimization_power(self) -> float:
        """the optimization power 𝑝 as shown: ∞ in all-interval mode, the scheme's stored power
        otherwise. All-interval tuning minimaxes over every interval (it optimizes the primes at
        the dual norm power and never reads the stored 𝑝), so 𝑝 is fixed at ∞ there — the cell
        shows ∞ and goes disabled (app._update_powerinput). The power cell, the mean damage, and the
        damage-chart indicator all read this so the locked display stays consistent."""
        if service.is_all_interval(self.tuning_scheme):
            return float("inf")
        return service.optimization_power(self.tuning_scheme)

    def displayed_mean_damage_power(self) -> float:
        """the power at which the displayed mean damage AGGREGATES the per-target/per-prime weighted
        damages — i.e. the power the optimizer actually minimized at (matching
        tuning.get_tuning_map_mean_damage). For a target-based scheme that is the optimization
        power 𝑝 (∞/2/1), same as displayed_optimization_power(). For an all-interval scheme the
        minimax-over-every-interval is, by duality, an optimization over the PRIMES at the DUAL of
        the complexity norm power — 2 for a Euclidean (ES) norm, ∞ for taxicab (-S) — so the
        mean damage is that dual-power mean of the per-prime damages, NOT their max. (The 𝑝 cell still
        shows ∞: that is the power over intervals; this is the power over primes, the mean damage
        symbol's dual(𝑞) subscript.) For -S, dual(𝑞) = ∞ so this coincides with 𝑝, as before."""
        if service.is_all_interval(self.tuning_scheme):
            return service.dual_norm_power(self.tuning_scheme)
        return service.optimization_power(self.tuning_scheme)

    def col_open(self, key: str) -> bool:
        return key in self.col_x and f"col:{key}" not in self.collapsed

    def _commas_band_w(self, nc_count: int):
        """The commas/V column's natural footprint for ``nc_count`` comma sub-columns (the
        real commas, plus any draft). Factored out of the column band so caption wrapping can
        price the column at its RESTING comma count — see :meth:`_caption_wrap_w`."""
        nv = nc_count + self.nu
        split = V_SPLIT_GAP if (self.show_unchanged and nc_count > 0) else 0
        empty = (_min_width_for_lines("nullity", 1)
                 if (self.show_unchanged and nc_count == 0) else 0)
        return 2 * BRACKET_W + nv * COL_W + split + empty

    def _caption_wrap_w(self, ckey: str):
        """the width a caption wraps within: the column's OPEN footprint, EXCEPT the commas/V
        column is priced at its RESTING comma count while a mapping-row − hover previews a
        born comma (ghost_comma). That transient ghost widens the column by one cell; without
        this, every commas-column caption ("scaling factors", "projection", …) could rewrap
        from two lines to one, shrinking those tiles and lifting the hovered − button out from
        under the cursor. A real comma DRAFT (self.pending) DOES count — the layout grows on
        that deliberate click, so its caption may rewrap as usual."""
        if ckey == "commas" and self.ghost_comma:
            resting = self._commas_band_w(self.nc + (1 if self.pending is not None else 0))
            return max(resting, self._caption_floor(ckey),
                       self._control_floor(ckey), self._symbol_floor(ckey))
        return self.open_col_w[ckey]

    def caption_band(self, key: str, folded: bool):
        """the row's caption band is sized to its tallest (wrapped) caption, so the longest
        name fits within its tile rather than spilling off a narrow column. Only columns
        that actually declare a tile here count: an empty interest column declares no
        tile, so it reserves no caption height (its captions would otherwise wrap tall in
        the bare bracket-gutter stub and inflate the empty board). Each caption wraps at
        its column's OPEN width — collapse-independent — so collapsing a column (hiding its
        caption) never drops the band and shrinks the row's other tiles. A folded ROW shows
        no captions at all."""
        if not (self.show_captions and key in CAPTIONED_ROWS and not folded):
            return 0
        lines = [_wrap_lines(self.effective_captions[(key, c)], self._caption_wrap_w(c)) for c in self.col_x
                 if (key, c) in self.effective_captions and (key, c) in self.declared_tiles]
        # the V counts tile carries TWO names — "nullity" over the comma half, "unchanged interval
        # count" over the unchanged half — each wrapped within its own (narrower) sub-area, so the
        # band must reserve for the taller of the two (the long unchanged name in its u·COL_W half)
        if key == "counts" and self.show_unchanged and "commas" in self.col_x:
            lines.append(_wrap_lines("unchanged interval count", self.nu * COL_W))
            lines.append(_wrap_lines("nullity", self.nc * COL_W + self.empty_comma_w))
        return max(lines, default=1) * CAPTION_LINE

    def ptext_editable(self, rkey: str, ckey: str) -> bool:
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

    def ptext_height(self, rkey: str, ckey: str):  # one line; the app shrinks the font to fit the box width
        return PTEXT_EDIT_H if self.ptext_editable(rkey, ckey) else PTEXT_H

    def ptext_band(self, key: str, folded: bool):
        """a single-line band for every value row's plain text (taller for the rows whose
        band holds an editable input); the font auto-fits so nothing wraps or spills"""
        if not (self.show_ptext and key in PTEXT_ROWS and not folded):
            return 0
        return PTEXT_EDIT_H if key in EDITABLE_PTEXT_ROWS else PTEXT_H

    # a control box (preset / form chooser): the box spans its column's tile (see control_box),
    # and the dropdown keeps its NATURAL width (cap_w) seated at the box's left — only shrunk if a
    # tiny tile can't seat even that. The label is the standard one-line left-justified caption
    # hugging the dropdown's bottom (the .rtt-caption-left asset), overflowing right if long.
    def control_dims(self, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):
        # the dropdown keeps a consistent capped width; the box spans the tile (see control_box) and
        # insets its content BOX_INNER off every border
        dropdown_w = max(40, min(self.col_w[ckey] - 2 * BOX_INNER, cap_w))
        label_h = CAPTION_LINE if label else 0  # one line, hugging the dropdown's bottom (overflows right if long)
        box_h = 2 * BOX_INNER + PRESET_H + label_h  # BOX_INNER pad, dropdown, hugging caption, BOX_INNER pad
        # the established-projection chooser carries the ✕ "return to scheme" button on a row inside
        # its own box, ABOVE the dropdown + caption (so the button is NOT a separate control box)
        box_h += (SCHEME_BTN_SQ + CTRL_LABEL_GAP) if scheme_btn else 0
        # the <choose form> dropdown rides in THIS box too — a second dropdown (+ its caption) BELOW
        # the main one, so it is NOT a separate control box (like the scheme button above). BAND_GAP
        # (not the tight CTRL_LABEL_GAP) separates it from the main chooser's caption, so that caption
        # reads as belonging to its OWN dropdown above, not to the form dropdown below it.
        if form_label is not None:
            box_h += BAND_GAP + PRESET_H + (CAPTION_LINE if form_label else 0)
        return dropdown_w, label_h, box_h

    def control_band_h(self, ckey: str, cap_w, label, scheme_btn: bool = False, form_label=None):  # box + outer padding
        return 2 * BOX_OUTER + self.control_dims(ckey, cap_w, label, scheme_btn, form_label)[2]

    def preset_cap(self, name: str):
        return TARGET_PRESET_W if name == "target" else PRESET_W

    def preset_band_h(self, key: str):  # the tallest preset control box riding this row
        return max((self.control_band_h(ckey, self.preset_cap(name), label, scheme_btn=(name == "projection"),
                                         form_label=self._preset_form_label(name, rk, ckey))
                    for name, rk, ckey, label in PRESETS + PRESET_COPIES
                    if rk == key and ckey in self.col_w), default=0)

    def formchooser_band_h(self, key: str):
        return max((self.control_band_h(ckey, PRESET_W, label)
                    for name, rk, ckey, label in FORM_CHOOSERS if rk == key and ckey in self.col_w), default=0)

    def row_open(self, key: str) -> bool:
        return key in self.rows and f"row:{key}" not in self.collapsed

    def tile_open(self, rkey: str, ckey: str) -> bool:  # a real tile, whose row + column are open and not folded
        return ((rkey, ckey) in self.declared_tiles and self.row_open(rkey) and self.col_open(ckey)
                and f"tile:{rkey}:{ckey}" not in self.collapsed)

    def tile_unit(self, rkey: str, ckey: str):
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

    def cell_unit(self, rkey: str, ckey: str, *, gen=None, prime=None, elem=None):
        """the per-value unit shown beneath a gridded cell when cell units are on (a toggle
        independent of the per-box "units: …" line): the tile's unit
        (tile_unit) with its STANDALONE coordinate variables subscripted by this cell's
        generator/prime index — so the g/p mapping reads g₁/p₁, the tuning map ¢/p₁, a mapped
        list g₁. Only standalone tokens subscript (see _subscript_coord), so the p inside an
        annotation family like (sopfr-C)/p stays put while the trailing prime coordinate becomes
        p₁. A nonstandard subgroup swaps the on-domain p for b (basis element); see domain_label.
        The chapter-9 superspace tiles run over true primes (p) and superspace generators (gL),
        NOT the on-domain g/b — so they keep p (the p → b swap is scoped to non-superspace
        tiles) and subscript the gL token (gL₁) for M_L / 𝒈ₗ."""
        if not self.show_cell_units:
            return ""
        u = self.tile_unit(rkey, ckey)
        superspace = rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")
        if gen is not None:
            if superspace:  # the superspace generator coordinate gʟ (g + subscript-L marker)
                u = u.replace(f"g{SUBSCRIPT_L}", f"g{SUBSCRIPT_L}{_sub(gen + 1)}")
            elif f"g{SUBSCRIPT_C}" in u:  # the canonical generator coordinate g_C (form box) — subscript
                # the g_C token, AND any bare input g (F's g_C/g denominator), without double-hitting
                # the protected g_C (whose trailing sentinel would otherwise match the bare-g regex)
                gc = f"g{SUBSCRIPT_C}"
                u = _subscript_coord(u.replace(gc, "\x00"), "g", f"g{_sub(gen + 1)}").replace("\x00", f"{gc}{_sub(gen + 1)}")
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

    def matlabel_gutter_w(self, group_key: str):
        """The MATLABEL_W gutter reserved on EACH side of a content footprint for row
        labels (𝒎₁, …) — only the primes column under the mapping matrix needs it in
        the built layout. The LEFT gutter carries the labels; the RIGHT one is empty,
        mirroring it so the matrix stays centred in its tile (see content_w above).
        Shared by prime_left and the bracket placement so the cells, the left ⟨ and the
        labels stay in lockstep."""
        if group_key == "primes":
            return self.matlabel_primes_w
        if group_key == "ssprimes":
            return self.matlabel_ssprimes_w
        return 0

    def handle_gutter_w(self, group_key: str):
        """The drag-handle gutter reserved OUTSIDE the row-label gutter (further from the matrix),
        on each side for balance — only the primes column, only when drag-to-combine is on. The
        left one carries the per-row handles; the right one balances them, like the matlabel gutter."""
        return self.row_handle_w if group_key == "primes" else 0

    def etpick_left_pad(self, group_key: str):
        """Empty LEFT padding that balances the per-row ET-picker gutter. The pickers ride the
        primes column's RIGHT gutter, past the ] (a compact chooser per mapping row, ETPICK_W
        wide). That gutter must be at least etpick_w; the left furniture (handles + 𝒎ᵢ labels) is
        usually narrower, so we pad the LEFT out to match — the matrix then stays centred with the
        labels/handles hugging the ⟨ and the pickers hugging the ]. Zero unless the picker gutter
        exceeds the furniture (and only on the primes column, the only one carrying pickers)."""
        if group_key != "primes" or not self.etpick_w:
            return 0
        return max(0, self.etpick_w - self.handle_gutter_w(group_key) - self.matlabel_gutter_w(group_key))

    def outer_gutter_w(self, group_key: str):
        """the full left/right reservation outside the cells, EQUAL on both sides so the matrix
        stays centred: the handle gutter, then the row-label gutter, plus (on the primes column,
        when the ET pickers show) the pad that balances their right gutter against this furniture.
        Used wherever the cells' true left edge matters (prime_left, the EBK span, the header)."""
        return self.etpick_left_pad(group_key) + self.handle_gutter_w(group_key) + self.matlabel_gutter_w(group_key)

    def matrix_span(self, group_key: str):
        """The (x, width) of a group's CELL matrix — its content_box minus the outer gutters, which
        content_w carries on BOTH sides (the left holds the handles + row labels, the right
        balances them). This is the region the EBK encloses: the per-row ⟨ … ] brackets seat
        their ⟨ at its left edge and ] at its right, and the spanning ebktop/ebkbrace/ebkangle
        frame runs its full width. Anchored to the cells (not the wider grey footprint), so a
        column widened past them keeps the EBK hugging the matrix with the labels/handles outside."""
        x, w = self.content_box(group_key)
        mx = self.outer_gutter_w(group_key)
        x, w = x + mx, w - 2 * mx
        # outer_gutter_w is now equal on both sides (the primes column pads its left to match the
        # ET-picker right gutter — see etpick_left_pad), so dropping it from both edges already hugs
        # the EBK to the cells: the labels/handles sit in the left gutter, the per-row ET pickers in
        # the right one, and the matrix stays centred between them.
        # the consolidated V column reserves a comma-half stub on the LEFT (empty_comma_w, for the
        # nullity count/caption) when there are no comma columns; the EBK matrix hugs U, so the
        # bracket starts past that stub — drop it from the span's left edge (right edge unchanged).
        if group_key == "commas" and self.empty_comma_w:
            x, w = x + self.empty_comma_w, w - self.empty_comma_w
        return x, w

    def _weight_simplicity_header(self, i: int):
        """the all-interval simplicity weight's per-column header — simply the reciprocal of the
        complexity column cₙ (whose own header cₙ = ‖𝐿[n]‖q carries the norm detail, so it needn't be
        repeated here). Matches the tile's big symbol 𝒘 = 𝒄⁻¹, subscripted per column: wₙ = cₙ⁻¹ (bare
        wₙ when equivalences are off)."""
        symbol = f"w{_sub(i + 1)}"
        if not self.show_equiv:
            return symbol
        return f"{symbol} = c{_sub(i + 1)}⁻¹"

    def prime_left(self, p: int):
        return self.primes_x + self.outer_gutter_w("primes") + BRACKET_W + p * COL_W

    @staticmethod
    def _element_cell_kind(text: str):
        """The editable domain-element kind for a value's display form: a fraction (e.g. "13/5", or
        the "?/?" draft) renders as a stacked fraction face (elementratio); a bare integer prime
        ("2") as a plain number (elementcell). Switching kind across a relabel makes the reconciler
        rebuild the cell, so the face form follows the value."""
        return "elementratio" if "/" in text else "elementcell"

    def comma_left(self, c: int):
        """the unchanged half U (the sub-columns at or past nc_shown — i.e. past the comma cells AND
        any pending draft) is pushed right by V_SPLIT_GAP, opening the gap that holds the C|U
        divider clear of the cells. Only when there IS a comma half (nc_shown > 0): at full rank
        (n = 0) the column is the whole unchanged basis with no C, so no gap and no divider."""
        gap = V_SPLIT_GAP if (self.show_unchanged and 0 < self.nc_shown <= c) else 0
        return self.commas_x + BRACKET_W + self.empty_comma_w + c * COL_W + gap

    def comma_value_pos(self, i: int):
        """the DISPLAY sub-column for the i-th value of the consolidated commas group, whose value
        sequence is the comma values (0..nc-1) then the unchanged values (nc..nc+nu-1). The
        unchanged half sits past any pending comma draft (which occupies index nc), so it shifts
        right by nc_shown - nc (= 1 while a draft is open, 0 otherwise). Identity off-projection."""
        return i if i < self.nc else i + (self.nc_shown - self.nc)

    def target_left(self, j: int):
        return self.targets_x + BRACKET_W + j * COL_W

    def interest_left(self, i: int):
        return self.interest_x + BRACKET_W + i * COL_W

    def held_left(self, i: int):
        return self.held_x + BRACKET_W + i * COL_W

    def detempering_left(self, i: int):  # the i-th generator detempering column
        return self.detempering_x + BRACKET_W + i * COL_W

    def gen_left(self, g: int):  # the g-th generator column in the generators box (its tuning-map cells)
        return self.content_x["gens"] + BRACKET_W + g * COL_W

    def canongen_left(self, g: int):  # the g-th canonical-generator column (the form box's F⁻¹F = I / canonical ratios)
        return self.canongens_x + BRACKET_W + g * COL_W

    def ss_gen_left(self, g: int):  # the g-th superspace generator column (chapter-9)
        return self.ssgens_x + BRACKET_W + g * COL_W

    def ss_prime_left(self, p: int):  # the p-th superspace prime column (chapter-9)
        return self.ssprimes_x + self.outer_gutter_w("ssprimes") + BRACKET_W + p * COL_W

    def map_top(self, i: int):
        return self.rows["mapping"].y + i * ROW_H

    def proj_top(self, i: int):  # the y of projection-matrix row i (the d stacked maps of P = GM)
        return self.rows["projection"].y + i * ROW_H

    def canon_top(self, i: int):  # the y of canonical-mapping row i (the r stacked canonical maps)
        return self.rows["canon"].y + i * ROW_H

    def vec_top(self, p: int):  # the y of vector component p in the d-tall interval-vectors row
        return self.rows["vectors"].y + p * ROW_H

    def ss_vec_top(self, p: int):  # the y of superspace-vector component p in the dL-tall ss_vectors row
        return self.rows["ss_vectors"].y + p * ROW_H

    def ss_map_top(self, i: int):  # the y of ss_mapping row i (the rL stacked superspace maps)
        return self.rows["ss_mapping"].y + i * ROW_H

    def ss_proj_top(self, i: int):  # the y of ss_projection row i (the dL stacked maps of P_L = G_L M_L)
        return self.rows["ss_projection"].y + i * ROW_H

    # The element +/− controls ride each fanning column's TOP bus (the fan-out, just after the
    # toggle), not the quantities row: the − sits on a branch point (a per-element split), the +
    # on a "stub" one COL_W past the last branch point — the slot where the next element would
    # branch — with the top bus stretched out to reach it. sub_axis_x is the split's x (column_axis
    # fans the same centres); plus_stub_x records, per addable column that shows a +, where that +
    # (and so the bus end) sits, keeping the cells and the gridlines in lockstep.
    def sub_axis_x(self, ckey: str, i: int):  # centre of column ckey's i-th per-element sub-axis (a branch point)
        return self.group_left[ckey](i) + COL_W / 2

    def col_plus_x(self, ckey: str):
        n = self.group_n[ckey]
        if n == 0:  # an empty set has no branch points: the + centres on the single trunk
            mx, mw = self.matrix_span(ckey)
            return mx + mw / 2
        if ckey == "commas" and self.show_unchanged:
            # the comma + / drop-zone stub rides the comma half's append point, kept CLEAR of the
            # unchanged half U so it doesn't occlude U's first reorder grip (grip:unchanged:0):
            #   • commas present → the V_SPLIT_GAP between C (incl. any pending draft) and U — the
            #     visual "next comma" slot, where the new comma's gridline lands when clicked.
            #   • full rank (no commas) → the reserved empty-comma nullity stub ("the space where the
            #     commas were"), LEFT of U — NOT U's first sub-axis, where the old "one slot past the
            #     last comma" arithmetic landed it (occluding grip:unchanged:0, exactly at full rank).
            # The top bus still spans all of V either way; column_axis reaches it out to this stub.
            if self.nc_shown == 0:
                return self.commas_x + BRACKET_W + self.empty_comma_w / 2
            return self.comma_left(self.nc_shown - 1) + COL_W + V_SPLIT_GAP / 2
        return self.sub_axis_x(ckey, n - 1) + COL_W  # one slot past the last branch point

    def _plus_shows(self, ckey: str) -> bool:  # whether column ckey shows a + (and so where its fan bus ends).
        """The interval columns (commas / targets / held / interest) are addable from EITHER interval
        row — the quantities ratios OR the interval vectors — so their + survives hiding the
        quantities row, then drops the cursor into the new column's first vector cell instead (see
        app.add_interval). gens / primes add through the quantities row alone: their draft is a
        ratio / domain-element header with no editable vectors-row twin to fall back to."""
        if ckey in ("interest", "held"):  # addable sets, so an empty-but-open column still adds one
            return self.col_open(ckey) and (self.row_open("quantities") or self.row_open("vectors"))
        if ckey == "targets":  # the target list is user-curated only when NOT all-interval (else it's auto Tₚ = I)
            return (self.tile_open("quantities", "targets") or self.tile_open("vectors", "targets")) and not self.all_interval
        if ckey == "gens":  # the generators + un-temps a comma (−n, +r), so it needs one to un-temper
            return self.tile_open("quantities", "gens") and self.state.n > 0
        if ckey == "primes":  # off: the + walks to the next standard prime (inapplicable to a subgroup).
            # On (nonstandard-domain box): the + starts a typed ?/? element draft, valid for ANY domain.
            return self.tile_open("quantities", "primes") and (self.show_nonstandard_domain or self.standard_domain)
        if ckey == "commas":  # commas stay addable/removable even in the consolidated V view (adding
            return self.tile_open("quantities", "commas") or self.tile_open("vectors", "commas")  # one shrinks U — see comma_value_pos
        return self.tile_open("quantities", ckey) or self.tile_open("vectors", ckey)

    def closed_form_operand(self, key, group, i):
        """The operand ``R`` of a cell's exact closed form ``1200 · log₂R``, or None
        when the value has no closed form. A just size IS ``1200·log₂`` of its
        interval. A comma vanishes in the temperament, so its retuning is the negated
        just size — the exact log of the inverted comma. The tempered sizes and the
        prime/target errors come from optimization, so they have none — as do the
        unchanged sub-columns of V (i ≥ nc): an unchanged interval isn't tempered out,
        so its retuning is the optimization error, not the negated-just closed form."""
        if key == "just":
            ratio = self.group_ratio[group](i)
            return _log_operand(ratio) if ratio is not None else None  # a dashed unchanged col: no ratio
        if group == "commas" and key == "retune" and i < self.nc:
            recip = 1 / Fraction(self.comma_ratios[i])
            return _log_operand(f"{recip.numerator}/{recip.denominator}")
        return None

    def col_token(self, group: str, i: int):
        """The stable id-token for column ``i`` of an identity-keyed list (targets/held/interest/
        commas, the gens mapping rows and their detempering twins), so all of an entry's cells
        share one token and re-key together when it moves or a neighbour is removed (the
        reconciler glides them; the remove-preview reds the right entry). A group without
        identity (the primes, the superspace bands) keeps its bare index. Over the consolidated
        V = C|U the commas group runs past the nc commas into the unchanged intervals, which
        carry their own positional ``u{j}`` namespace — U only ever shrinks from its end, and a
        distinct namespace keeps a comma token from ever colliding with an unchanged id."""
        if group == "commas" and i >= self.nc:
            return f"u{i - self.nc}"
        pairs = self._col_ids.get(group)
        return i if pairs is None else pairs[i][0]

    def pending_col_token(self, group: str):
        """The id-token for a list's draft (pending) column — one past every committed column's, so
        it never collides with a live column. On a fresh list this is the column count, matching the
        historical ``…:count`` draft-cell ids."""
        return pending_token([tok for tok, _ in self._col_ids[group]])

    def _pending_draft_idx(self, group: str):
        """The ``(draft-marker, committed-count)`` for an interval list's pending draft column,
        or ``None`` for a group with no draft. Shared by the quantities/tuning rows and the
        prescaling row, which each append one blank green slot one column past the committed
        ones when the marker is set (the count is where that slot sits)."""
        return {"commas": (self.comma_draft or None, self.nc), "targets": (self.pending_target, self.k),
                "held": (self.pending_held, self.nh), "interest": (self.pending_interest, self.mi)}.get(group)

    def _voice(self, tile, idx, cents) -> None:
        """Make the just-built cell (``self.cells[-1]``) click-to-play: hovering it reveals a speaker
        that sounds ``cents``. ``tile`` + ``idx`` group a row's cells so the bank's arp / chord /
        rolled-chord modes sweep the whole tile from the clicked note — the client derives the chord
        from the tile's sibling cells, so it stays correct across reorders with no baked pitch list.
        A ``None`` size (a DASHED cell — an unchanged interval the tuning doesn't pin) has no pitch."""
        if cents is None:
            return
        self.cells[-1] = replace(self.cells[-1], audio=(tile, int(idx), float(cents)))

    def tuning_value_row(self, key: str, group: str, values, editable_kind=None) -> None:
        # ``editable_kind`` (e.g. "weightcell") swaps the read-only "tuningvalue" face for an editable
        # input cell on the committed columns — the manual-weight row's override cells. The math-expr
        # view, charts, voicing and the pending-draft green placeholder are unchanged.
        if not self.tile_open(key, group):
            return
        values = tuple(values)
        if key in CHARTED_ROWS:
            self.chart_tiles.append((key, group, values))
        y = self.rows[key].y
        # the tuning-family unit is cents per the column's coordinate: over the generators
        # it's ¢/gᵢ (gens) or ¢/gLᵢ (the chapter-9 superspace ssgens), over the primes ¢/pᵢ /
        # ¢/bᵢ (the domain primes / basis elements) or ¢/pᵢ (the superspace ssprimes, true
        # primes), and over the (dimensionless) interval columns plain ¢
        is_gen_group = group in ("gens", "ssgens")
        is_prime_group = group in ("primes", "ssprimes")
        for i, v in enumerate(values):
            cid = f"{key}:{self.group_elem[group]}:{self.col_token(group, i)}"
            # over the consolidated V the values run comma sizes then unchanged sizes; comma_value_pos
            # places the unchanged half past any pending comma draft (identity for every other group)
            x = self.group_left[group](self.comma_value_pos(i) if group == "commas" else i)
            u = self.cell_unit(key, group, gen=i if is_gen_group else None, prime=i if is_prime_group else None)
            operand = self.closed_form_operand(key, group, i) if self.show_math else None
            if operand is not None:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, "mathexpr", text=_math_expr(operand, v, self.show_quantities, self._decimals), unit=u))
            else:
                self.cells.append(CellBox(cid, x, y, COL_W, ROW_H, editable_kind or "tuningvalue",
                                     text=service.cents(v, self._decimals), unit=u))
            if key in ("tuning", "just"):  # the tuning row sounds each interval's TEMPERED size, the
                self._voice(f"{key}:{group}", i, v)  # just row its JUST size; retune (errors) is no pitch
        # a pending comma/target/held/interest draft also gets a blank GREEN placeholder in every
        # tuning-family row (tuning / just / retune / complexity / damage / weight), so the draft
        # column reads green top-to-bottom — not only at its editable vectors up top. The enclosing
        # bracket already spans the draft (content_w is _shown-wide), so only the cell is needed.
        pending_idx = self._pending_draft_idx(group)
        if pending_idx is not None and pending_idx[0] is not None:
            # a real draft's size is unknown (blank); the mapping − hover's born comma has known sizes
            # — it vanishes in the new temperament, so tempered 0, just its just size, error −just,
            # and its own complexity ‖𝐿·comma‖q (the complexity row reads green through the ghost too).
            text = ""
            if self.ghost_comma and group == "commas":
                gsize = {"tuning": 0.0, "just": self.ghost_comma_just, "retune": -self.ghost_comma_just,
                         "complexity": self.ghost_comma_complexity}.get(key)
                if gsize is not None:
                    text = service.cents(gsize, self._decimals)
            self.cells.append(CellBox(f"{key}:{self.group_elem[group]}:draft", self.group_left[group](pending_idx[1]),
                                      y, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    # a charted tile draws a bar chart in the band reserved above its values. The box spans
    # the value block exactly — the left bracket gutter, the value columns, and the right
    # bracket gutter — anchored to group_left (the cells), NOT the column footprint. So the
    # chart's BRACKET_W-inset axis and COL_W bar pitch overlay the cells: each bar centres on
    # its value's gridline even when a caption widens the footprint or a matlabel gutter
    # offsets the cells within it (the gridlines follow the cells the same way; see
    # column_axis). chart_top[key] exists only where a chart band was reserved (charts on,
    # row charted, not folded), so it gates emission against the layout with no drift.
    def chart(self, rkey: str, ckey: str, values, indicator=None, indicator_label="") -> None:
        values = tuple(values)
        if values and rkey in self.rows and self.rows[rkey].chart_top is not None and self.tile_open(rkey, ckey):
            x = self.group_left[ckey](0) - BRACKET_W  # the left bracket gutter, where the value block starts
            self.cells.append(CellBox(f"chart:{rkey}:{ckey}", x, self.rows[rkey].chart_top,
                                 2 * BRACKET_W + len(values) * COL_W, CHART_H, "chart", values=values,
                                 indicator=indicator, indicator_label=indicator_label))

    # EBK brackets in the value groups' gutters: prime-side rows are maps (⟨…]),
    # target-side rows are lists ([ … ]). Maps stack one per generator row.
    def bracket(self, bid: str, glyphs, group_key: str, y, h, *, fit=False, span=None, pending=False,
                stacked=False) -> None:
        """value brackets are short and centred in their row (so stacked rows keep a
        gap); the enclosing vector-list [ ] passes fit=True to span the matrix.
        matrix_span hugs the cells (interest's content, not its footprint) and steps
        the left ⟨ right past the matlabel gutter, so the row labels sit inside the
        panel left of the ⟨ rather than overflowing it. ``span`` overrides the default span.
        ``pending`` recolours the bracket green (via ebk_svg) to match a draft row's cells.
        ``stacked`` marks a per-ROW bracket of a covector stack (one ⟨ … ] per generator row):
        with EBK off the stack collapses to ONE full-height square [ … ] (drawn by matrix_frame),
        so a stacked per-row bracket emits nothing — only EBK shows a bracket per row."""
        if not self.show_ebk:  # EBK off: a plain matrix wears ONE square [ … ] — see matrix_frame
            if stacked:
                return  # the single full-height bracket is matrix_frame's job; skip the per-row one
            glyphs = ("[", "]")  # every other bracket just squares (⟨ / { → [, ] stays ])
        gx, gw = span if span else self.matrix_span(group_key)
        if fit and not self.show_ebk:
            by, bh = y, h  # a plain matrix's outer [ ] hugs the cell matrix exactly (no frame bands)
        elif fit:
            # A vector-list outer wrap [ … ] spans the matrix's full FRAMED height, so it
            # ENCLOSES the per-column top/bottom marks (each ket's ebktop + ebkbrace/angle,
            # which stand FRAME_GAP off the cells — see vector_list_marks). This mirrors how a
            # covector matrix's spanning top bracket + brace enclose its per-row ⟨ … ] across
            # the full WIDTH: there the horizontal wrap reaches past the vertical inner marks;
            # here the vertical wrap reaches past the horizontal ones — and, like the mapping's
            # bracket, OVERHANGS them: it clears the marks' extreme y by FRAME_OVERHANG at each
            # end, the same margin the mapping's bracket clears its inner ⟨ ] by in x. ``y`` is
            # always the matrix's row_y, so y - (FRAME_H + FRAME_GAP) is its frame_top_y (the top
            # marks' top edge) and FRAME_GAP + BRACE_H below the cells is the bottom marks' foot;
            # the wrap then reaches FRAME_OVERHANG beyond each. Without the span the wrap covered
            # only the value cells, so the marks poked out and the [ ] hugged the gridded values.
            by = y - (FRAME_H + FRAME_GAP) - FRAME_OVERHANG
            bh = h + (FRAME_H + FRAME_GAP) + (FRAME_GAP + BRACE_H) + 2 * FRAME_OVERHANG
        else:
            by, bh = y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H
        self.cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0], pending=pending))
        self.cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1], pending=pending))

    # the single place a gridline is recorded. ``dotted`` marks a rule whose band is
    # collapsed: a folded row/column converges its fan onto one centre rule, drawn dotted
    # so the band reads as a placeholder for its hidden content (see Line.dotted).
    def gridline(self, lid: str, orientation: str, pos, start, length, *, dotted: bool) -> None:
        self.lines.append(Line(lid, orientation, pos, start, length, dotted=dotted))

    def column_axis(self, key: str, prefix: str, n: int, center_open: bool) -> None:
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
        # an addable column stretches its TOP bus out to the + stub, so the branching bar reaches the
        # + (which rides plus_stub_x); the bottom bus just spans the data. max(…, bx + bw) keeps the
        # bus spanning ALL sub-axes when the + rides INSIDE the data (the consolidated V comma +, in
        # the C|U gap), and min(…, bx) reaches it the other way when the + rides LEFT of the data (the
        # same comma + at full rank, on the reserved nullity stub left of the unchanged columns).
        top_end = max(self.plus_stub_x[key], bx + bw) if key in self.plus_stub_x else bx + bw
        bus_left = min(self.plus_stub_x[key], bx) if key in self.plus_stub_x else bx
        self.gridline(f"bus:{key}:top", "h", self.fanout_y, bus_left, top_end - bus_left, dotted=dotted)
        self.gridline(f"bus:{key}:bot", "h", self.bot_bus_y, bx, bw, dotted=dotted)
        self.gridline(f"trunk:{key}", "v", cx, self.branch_top_y, self.fanout_y - self.branch_top_y, dotted=dotted)
        self.gridline(f"foot:{key}", "v", cx, self.bot_bus_y, self.total_h - self.bot_bus_y, dotted=dotted)
    def _row_fans(self, key: str):
        """A row fans its left bus OUT to node_edge + FAN (branching into per-sub-row rules) when it
        has more than one cell-row OR carries a row + stub. The + must ride a fanned bus to sit
        beside the content and stay reached by the connecting bar — so even a SINGLE-row band that
        adds elements fans (a rank-1 ET mapping, whose lone generator row still shows the
        comma-un-tempering +): the row mirror of an addable column always fanning to seat its +."""
        return self.rows[key].nsub > 1 or key in self.row_plus_y

    def row_axis(self, key: str) -> None:
        n = self.rows[key].nsub
        folded = f"row:{key}" in self.collapsed  # the whole fan dots and converges when the row folds
        cy = self.rows[key].y + self.rows[key].h / 2
        ys = [cy] * n if folded else [self.rows[key].y + i * ROW_H + ROW_H / 2 for i in range(n)]
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
    def panel_rect(self, ckey: str, rkey: str):
        """a folded tile collapses both ways at once, so it shrinks to a point at its
        centre — like a row+column collapse confined to this one tile."""
        tile_c = f"tile:{rkey}:{ckey}" in self.collapsed
        col_c = f"col:{ckey}" in self.collapsed or tile_c
        row_c = f"row:{rkey}" in self.collapsed or tile_c
        cx, cw = self.tile_box(ckey)  # the tile widens for a long caption; content centres within it
        ch, cy = self.rows[rkey].tile_h, self.rows[rkey].tile_top
        w, px = (0, 0) if col_c else (cw, PAD)
        h, py = (0, 0) if row_c else (ch, PAD)
        bx = cx + cw / 2 if col_c else cx
        by = cy + ch / 2 if row_c else cy
        return bx - px, by - py, w + 2 * px, h + 2 * py

    def panel(self, bid: str, ckey: str, rkey: str) -> None:
        if ckey not in self.col_x or rkey not in self.rows:
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
    def tile_groups(self, rkey: str, ckey: str):
        """the consolidated unrotated-vector-list column V = C|U mixes the comma half (the comma basis
        C — temperament/yellow) with the unchanged half (the held/unchanged intervals — tuning/cyan),
        so EVERY tile of the column reads GREEN (the darken blend of the two washes). This overrides
        the per-tile factors: off projection each commas tile keeps its own colour (C-yellow, etc.)."""
        if self.show_unchanged and ckey == "commas":
            return {"temperament", "tuning"}
        # a spine family may be one string or a set of families (a both-families band reads green)
        as_groups = lambda g: {g} if isinstance(g, str) else set(g)
        if rkey in SPINE_ROWS and ckey in SPINE_COLUMN_GROUP:
            return as_groups(SPINE_COLUMN_GROUP[ckey])  # a counts/units row cell: its column's family
        if ckey in SPINE_COLUMNS and rkey in SPINE_ROW_GROUP:
            return as_groups(SPINE_ROW_GROUP[rkey])     # a quantities/units column cell: its row's family
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

    def cpick_band_y(self, rkey):
        # the per-comma-column picker band, just below the ⟩ foot (above the symbol/caption stack)
        return self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame

    # the plain-text box sits directly below the symbol/caption/units stack; the preset
    # chooser rides one plain-text band lower (so presets appear under plain text).
    def ptext_band_y(self, rkey: str):
        return self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey] + self.rows[rkey].sym + self.rows[rkey].cap + self.rows[rkey].units

    # A chooser dropdown that offers only ONE option, with that option already selected, is not a
    # choice — it renders as a DISABLED dropdown (greyed, non-interactive, but still left-justified
    # like any dropdown), exactly like the all-interval-locked target / weight-slope choosers
    # (Douglas's request). These predicates decide that, shared by the preset choosers (tuning /
    # prescaler) and the box-𝒄 complexity control select.
    @staticmethod
    def _is_sole_option(options, value) -> bool:
        """True when ``options`` offers exactly one choice AND ``value`` is it — so the chooser has
        no real choice and renders disabled. ``options`` is a ``{value: label}`` mapping (a list/tuple
        is taken as value==label). False for a real choice (≥2 options) or an off-list value — a
        deviating edit shows "-", which stays interactive so its one option can reset it."""
        opts = options if isinstance(options, dict) else {o: o for o in options}
        return len(opts) == 1 and value in opts

    def _preset_locked(self, name: str) -> bool:
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
    def control_box(self, box_id: str, ckey: str, top, cap_w, label, disabled: bool = False,
                    scheme_btn: bool = False, form_chooser=None):
        # form_chooser, when set, is (cell_id, caption) for a <choose form> dropdown stacked inside
        # this same box below the main chooser + its caption — never a separate box (the user's rule).
        form_label = form_chooser[1] if form_chooser else None
        dropdown_w, label_h, box_h = self.control_dims(ckey, cap_w, label, scheme_btn, form_label)
        box_x, box_y = self.col_x[ckey], top + BOX_OUTER  # the box spans the tile's full width (col_w)
        self.blocks.append(Block(box_id, box_x, box_y, self.col_w[ckey], box_h, boxed=True))
        ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER  # content inset BOX_INNER off every border
        if scheme_btn:  # the ✕ "return to scheme" row sits ABOVE the dropdown, at the top of the box
            self.emit_scheme_button(ctrl_x, ctrl_y, ckey)
            ctrl_y += SCHEME_BTN_SQ + CTRL_LABEL_GAP  # the dropdown + caption drop below it
        if label:  # disabled greys the label with its control (a locked chooser, e.g. all-interval target)
            self.cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                                 "caption", text=label, align="left", disabled=disabled))
        if form_chooser:  # the <choose form> dropdown + its caption, below the main chooser, in this box
            fid, fcap = form_chooser
            form_y = ctrl_y + PRESET_H + label_h + BAND_GAP
            self.cells.append(CellBox(fid, ctrl_x, form_y, dropdown_w, PRESET_H, "formchooser",
                                 text=self.mapping_form_key if fid.endswith(":mapping") else self.comma_basis_form_key))
            self.cells.append(CellBox(f"{fid}:label", ctrl_x, form_y + PRESET_H, dropdown_w, CAPTION_LINE,
                                 "caption", text=fcap, align="left"))
        return ctrl_x, dropdown_w, ctrl_y

    def _preset_form_label(self, name: str, rkey: str, ckey: str):
        """The "form" caption when the <choose form> dropdown embeds in this preset's box — i.e. the
        temperament chooser on a form-chooser tile (mapping / comma basis) while form controls are
        shown. Else None. Keeps :func:`preset_band_h` and :func:`_emit_presets` in step on the box's
        height and contents, so the embedded dropdown is reserved for and drawn in the same box."""
        embeds = (name == "temperament" and self.show_form_controls
                  and any(rk == rkey and ck == ckey for _n, rk, ck, _l in FORM_CHOOSERS))
        return "form" if embeds else None

    def control_region(self, box_id: str, ckey: str, top, content_h):
        """A bordered control box (boxed Block) spanning tile ``ckey`` from ``top``, enclosing
        ``content_h`` of stacked controls inset BOX_INNER at the top and CTRL_LABEL_GAP at the
        bottom — the control_box frame, but for arbitrary content (the box-𝐋 checkbox, the box-𝒄
        multi-control row) rather than just a dropdown+label. Returns the inner top-left (x, y) the
        controls start at, so each control's own offsets stay as they were, just shifted inside. The
        box Block is DEFERRED (collected, not appended now) so it layers on top of the grey panels."""
        box_y = top + BOX_OUTER
        self._control_region_boxes.append(Block(box_id, self.col_x[ckey], box_y, self.col_w[ckey],
                                                 2 * BOX_INNER + content_h, boxed=True))  # BOX_INNER pad top AND bottom
        return self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER

    def control_region_band_h(self, content_h):
        """The full band a :func:`control_region` of ``content_h`` reserves — the box plus its
        BOX_OUTER vertical padding above and below (the counterpart of :func:`control_band_h`)."""
        return 2 * BOX_OUTER + 2 * BOX_INNER + content_h

    def emit_all_interval_check(self, check_x, ctrl_y) -> None:
        """the all-interval checkbox + its caption, seated on a control row at ctrl_y: an OPTION_BOX_PX
        square over an "all-interval" caption in an LBOX_DIM_W slot (the box-𝐋 diminuator's shape). It
        reflects whether the scheme targets every interval (ticking it is wired in app.py)."""
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2  # centre the square on the control row
        self.cells.append(CellBox("control:all_interval", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.is_all_interval(self.tuning_scheme)))
        self.cells.append(CellBox("caption:all_interval", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="all-interval"))

    def emit_scheme_button(self, x, y, ckey: str) -> None:
        """the square ✕ "return to scheme" button + a caption snug to its right (vertically centred on
        the square), with the ✕'s top-left at (x, y). Seated INSIDE the established-projection
        chooser's box (the row ABOVE the dropdown) when presets is on, or in its own small box when
        presets is off. back_to_scheme is wired in app.py, which greys it when the tuning is already
        scheme-driven."""
        self.cells.append(CellBox(f"scheme:{ckey}", x, y, SCHEME_BTN_SQ, SCHEME_BTN_SQ, "scheme_button", text="✕"))
        label_y = y + (SCHEME_BTN_SQ - CAPTION_LINE) / 2  # centre the one-line caption on the square
        # the caption box starts 2px right of the ✕; its rtt-caption-left class adds a 6px text inset,
        # so the glyphs sit ~8px off the square — snug, and tighter than the prior 4px box gap.
        self.cells.append(CellBox(f"scheme:{ckey}:label", x + SCHEME_BTN_SQ + 2, label_y, SCHEME_LABEL_W,
                             CAPTION_LINE, "caption", text="return to scheme", align="left"))

    def emit_diminuator_check(self, check_x, ctrl_y) -> None:
        """the "replace diminuator" checkbox + caption, seated to the RIGHT of the predefined-
        pretransformers dropdown inside its preset box — box 𝐋's control riding the existing
        pretransformer-chooser box, the way the all-interval check rides the target chooser box."""
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2  # centre the square on the control row
        self.cells.append(CellBox("control:diminuator", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.diminuator_replaced(self.tuning_scheme)))
        self.cells.append(CellBox("caption:diminuator", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="replace diminuator"))

    # a framed matrix's top bracket + bottom brace stand off the cells by FRAME_GAP:
    # the top bracket just above row 0 (below the toggle head), the brace a matching
    # gap below the last row of that band.
    def frame_top_y(self, rkey: str):
        return self.rows[rkey].y - FRAME_H - FRAME_GAP

    def frame_brace_y(self, rkey: str):
        return self.rows[rkey].y + self.rows[rkey].h + FRAME_GAP

    # a matrix tile (the primes mapping and its canonical forms) is enclosed by a top
    # bracket + bottom curly brace spanning its whole column: the brace marks generator
    # coordinates, so it's the right close for the mapping but not for raw vectors or
    # prescaled vectors (those use per-column marks via vector_list_marks). ``bid`` keeps
    # each frame's ids stable so two framed rows over the same column never collide.
    def matrix_frame(self, rkey: str, ckey: str, bid: str, foot: str = "ebkbrace", span=None) -> None:
        """The spanning frame hugs the CELL matrix — content_box, exactly as the per-row
        bracket() calls do — not the grey footprint (col_x/col_w). The matlabel gutter
        (row labels 𝒎ᵢ / 𝒙ᵢ) sits LEFT of that matrix, OUTSIDE the frame. Anchoring to
        the footprint instead would, whenever it is widened past its content (e.g. by the
        prescaler chooser or box-𝐋 diminuator under the prescaling matrix), drag the frame left
        over those labels and right past the cells. ``foot`` is the bottom-spanning close:
        ``ebkbrace`` for the mapping family (generator coordinates, curly close),
        ``ebkangle`` for the bare prescaler 𝐿 (angle close ⟩, mirroring the mapping's
        plain-text bracket but with ⟩ in place of })."""
        if not self.tile_open(rkey, ckey):
            return
        gx, gw = span if span else self.matrix_span(ckey)  # ``span`` overrides the default cell-matrix span
        if not self.show_ebk:
            # EBK off: a plain matrix wears ONE pair of full-height square brackets — no top bar, no
            # bottom brace, no per-row brackets (those are skipped, stacked=True). The covector stack
            # is the MAP kind, so no ᵀ. Inner cell borders / gridlines stay (linear-algebra standard).
            y, h = self.rows[rkey].y, self.rows[rkey].h
            self.cells.append(CellBox(f"bracket:{bid}:l", gx, y, BRACKET_W, h, "bracket", text="["))
            self.cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, y, BRACKET_W, h, "bracket", text="]"))
            return
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
    def vector_list_marks(self, rkey, name, ckey, left, n_cols, top="ebktop", foot="ebkbrace", separators=True, pending_col=-1) -> None:
        if not self.tile_open(rkey, ckey):
            return
        if self.show_ebk:
            mark_w = COL_W - 2 * MARK_INSET
            for c in range(n_cols):
                mx = left(c) + MARK_INSET
                pend = (c == pending_col)  # the draft column's ket marks render green, like its cells
                self.cells.append(CellBox(f"{top}:{name}:{c}", mx, self.frame_top_y(rkey), mark_w, FRAME_H, top, pending=pend))
                self.cells.append(CellBox(f"{foot}:{name}:{c}", mx, self.frame_brace_y(rkey), mark_w, BRACE_H, foot, pending=pend))
        elif n_cols:
            # EBK off: a plain matrix has NO per-column brackets — its single outer [ … ] (the fit
            # bracket) frames the whole list. We only tag the VECTOR kind with ᵀ: a standalone
            # collection (interest, no outer wrap) per column, a wrapped matrix once past its outer ].
            if ckey == "interest":
                for c in range(n_cols):
                    self.transpose_mark(f"{name}:{c}", left(c) + COL_W - MARK_INSET, rkey, pending=(c == pending_col))
            else:
                gx, gw = self.matrix_span(ckey)
                self.transpose_mark(name, gx + gw, rkey)
        if not separators:
            return
        # the dividing rules (the matrix's inner vertical gridlines). With EBK on they span the full
        # FRAMED height to enclose the per-column marks (FRAME_OVERHANG past them); with EBK off there
        # are no marks, so they hug the cell matrix exactly — a plain matrix's inner lines, no overshoot.
        if self.show_ebk:
            sep_y = self.frame_top_y(rkey) - FRAME_OVERHANG
            sep_h = self.frame_brace_y(rkey) + BRACE_H + FRAME_OVERHANG - sep_y
        else:
            sep_y, sep_h = self.rows[rkey].y, self.rows[rkey].h
        for c in range(1, n_cols):  # a rule on each interior column boundary
            self.cells.append(CellBox(f"sep:{name}:{c}", left(c) - SEP_W / 2, sep_y, SEP_W, sep_h, "vbar"))

    def transpose_mark(self, name, x, rkey, pending: bool = False) -> None:
        """The EBK-off ᵀ superscript marking a vector-kind matrix, seated at its top-right corner at
        ``x`` (the matrix's outer-] right edge, or a standalone ket's right). ``pending`` greens it
        with its draft column's cells, via _update_label (like the brackets)."""
        self.cells.append(CellBox(f"transpose:{name}", x, self.rows[rkey].y - FRAME_GAP, TRANSPOSE_W, ROW_H,
                             "transpose", text="ᵀ", pending=pending))

    def v_split_bars(self) -> None:
        """the single vertical rule dividing the comma half C from the unchanged half U, centred in
        the V_SPLIT_GAP between them, down EVERY tile of the consolidated unrotated-vector-list
        column V = C|U (the mockup's V | divider). The per-column separators are off throughout V,
        so this lone bar is its only divider.

        The bar is a property OF THE COLUMN, not of a named list of rows: any tile whose commas
        cells actually reach into the unchanged half U gets it — discovered from the emitted cells
        (this runs last, after every band is laid), so it can never drift as rows come and go. That
        picks up any future consolidating row automatically (and the superspace B_L / M_L lists,
        now that they render their U half too); it skips a tile whose comma half holds only C and
        no U — there's nothing to divide. The counts tile is the lone exclusion: it holds two
        scalar tallies (n, u), not a matrix, and the user didn't want a rule sitting between them."""
        if not self.show_unchanged or self.commas_x is None or self.nc_shown == 0 or self.nu == 0:
            return  # no comma half (full rank, n = 0) or no unchanged half: nothing to divide
        x = self.comma_left(self.nc_shown) - V_SPLIT_GAP / 2 - SEP_W / 2  # mid-gap, between C (+ any draft) and U
        u_left = self.comma_left(self.nc_shown)         # first sub-column of the unchanged half
        u_right = u_left + self.nu * COL_W              # past the last; bounds the U band, clear of the next column
        rows_with_u = set()                             # row keys with a cell sitting in the U half of the V column
        for cell in self.cells:
            if u_left - 0.5 <= cell.x < u_right:
                for rkey, band in self.rows.items():
                    if band.y <= cell.y < band.y + band.h:
                        rows_with_u.add(rkey)
                        break
        for rkey in rows_with_u:
            if rkey != "counts" and self.tile_open(rkey, "commas"):  # counts holds only the n | u tallies — no rule
                self.cells.append(CellBox(f"vsplit:{rkey}", x, self.rows[rkey].y, SEP_W, self.rows[rkey].h, "vbar"))

    def _emit_headers(self) -> None:
        """Column headers, row labels, their fold toggles, and the master expand/collapse-all toggle."""
        # column headers (always shown; a collapsed column keeps its title) plus a
        # fold toggle in the header band for collapsible ones. A matlabel-widened column
        # (primes when symbols is on) carries the gutter on both sides, so the header + toggle
        # drop the gutter from each edge and stay centred over the CELLS rather than the wider
        # column footprint — the gutters only frame the row labels, never the title.
        for key in self.col_x:
            hx = self.col_x[key] + self.outer_gutter_w(key)
            # the header centres over the CELLS — drop the (now symmetric) outer gutters from both
            # edges; on the primes column those already include the ET-picker balance, so the title
            # stays centred over the matrix, not the wider footprint
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
        for key in self.rows:
            label = self.rows[key].label
            if self.size_factor:
                label = _pretransform_label(label)
                # "complexity pretransforming" is too long for the gutter; hyphenate the word at "pre-"
                # and hard-break before "transforming" (full font, no shrink). The nbsp keeps "complexity
                # pre-" together (LABEL_W is now wide enough for it) and the newline (the pre-line
                # rtt-rowlabel honours it) drops "transforming": two lines, "complexity pre-" / "transforming".
                label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
            self.cells.append(CellBox(f"label:{key}", 0, self.rows[key].y, LABEL_W, self.rows[key].h, "rowlabel", text=label))
            if self.rows[key].collapsible:
                glyph = _fold_glyph(f"row:{key}" in self.collapsed)
                ty = self.rows[key].y + (self.rows[key].h - TOGGLE) / 2
                self.cells.append(CellBox(f"toggle:row:{key}", self.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))

        # the master expand/collapse-all toggle, in the corner where the row-toggle column
        # (node_x) meets the column-toggle row (col_node_y). Its glyph mirrors the whole
        # grid: out-chevrons to expand when every foldable row and column is already
        # collapsed, in-chevrons to collapse otherwise.
        foldable = _foldable_ids(self.cells)  # the row/col toggles emitted just above
        all_collapsed = bool(foldable) and foldable <= self.collapsed
        self.cells.append(CellBox("toggle:all", self.node_x, self.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                             text=_fold_glyph(all_collapsed)))

    def _emit_counts_row(self) -> None:
        """The counts row: each present column's set cardinality, centred over its values."""
        # counts row: each present column's set cardinality, centred over its values. The
        # detempering column counts the rank r (one detempering interval per generator); the
        # superspace columns count their own rank rL and dimensionality dL.
        if self.row_open("counts"):
            cardinality = {"gens": self.r, "primes": self.d, "commas": self.state.n, "targets": self.k, "held": self.nh,
                           "detempering": self.r,
                           "ssgens": self.rL, "ssprimes": self.dL}
            for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
                if not self.tile_open("counts", ckey):
                    continue
                if ckey == "commas" and self.show_unchanged:
                    # the consolidated V = C|U carries two counts: the nullity n over the comma half,
                    # the unchanged interval count u over the unchanged half (split by the C|U bar).
                    # At full rank (n = 0) the comma half is the reserved empty_comma_w stub — the
                    # n = 0 tally and its "nullity" caption still show there (sized to fit), and only
                    # a true zero-width comma half (a pending first comma, no stub) drops the tally.
                    comma_half_w = self.nc * COL_W + self.empty_comma_w
                    if comma_half_w:
                        # the reserved stub sits LEFT of the EBK bracket (at commas_x); the real comma
                        # cells sit after it (comma_left(0)). Pick whichever this case has.
                        comma_half_x = self.commas_x if self.empty_comma_w else self.comma_left(0)
                        self.cells.append(CellBox("count:commas", comma_half_x, self.rows["counts"].y, comma_half_w, ROW_H,
                                             "count", text=f"{_count_sym('n')} = {self.state.n}"))
                    self.cells.append(CellBox("count:commas:u", self.comma_left(self.nc_shown), self.rows["counts"].y, self.nu * COL_W, ROW_H,
                                         "count", text=f"{_count_sym('u')} = {self.nu}"))
                    continue
                self.cells.append(CellBox(f"count:{ckey}", self.col_x[ckey], self.rows["counts"].y, self.col_w[ckey], ROW_H,
                                     "count", text=f"{_count_sym(sym)} = {cardinality[ckey]}"))

    def _emit_units(self) -> None:
        """The units row + column: coordinate-unit labels per row and per column."""
        # units row + column (the specific `domain_units` toggle): coordinate-unit labels.
        # The units COLUMN labels each row's coordinate — the interval-vectors basis in
        # primes (pᵢ/), the mapping in generators (gᵢ/), the cents tuning rows as ¢/. The
        # units ROW labels each column's coordinate — /gᵢ over generators, /pᵢ over the
        # domain primes, /1 over the ratio columns. Each rides its own grey tile
        # (UNITS_TILES), so tile_open gates emission against the live layout.
        # The matrix rows' units-column labels — one table entry per tile: (row count, row-top
        # accessor, label for subrow i). The projection row labels each of its prime-indexed rows
        # like the interval-vectors row (P is a p/p operator — the numerator side of its p/p units;
        # the /pᵢ denominators ride the units row over the primes columns). The chapter-9 superspace
        # rows label their coordinate too: B_L's components and M_jL's identity are superspace primes
        # (pᵢ/), M_L's rows are superspace generators (gLᵢ/) — true primes / superspace generators,
        # never the on-domain b/g. The superspace projection P_L = G_L·M_L is likewise a superspace-
        # prime → superspace-prime operator (dL × dL, NOT a basis-element operator), so its units-
        # column numerator reads pᵢ/ — true primes, exactly like the M_L / M_jL / B_L rows above it,
        # NEVER the on-domain b.
        matrix_units = {
            "vectors": (self.d, self.vec_top, lambda i: f"{self.domain_label}{_sub(i + 1)}/"),
            # the canonical-mapping row's coordinate is the canonical generator g_Cᵢ/ (the spine
            # twin of the /g_Cᵢ units over the canonical-generators column), like the mapping's gᵢ/
            "canon": (self.rc, self.canon_top, lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
            "projection": (self.d, self.proj_top, lambda i: f"{self.domain_label}{_sub(i + 1)}/"),
            # r_shown so a pending mapping-row draft's band carries its gₙ/ label too, matching every
            # committed row (and the comma draft column's /1) — the draft row reads complete.
            "mapping": (self.r_shown, self.map_top, lambda i: f"g{_sub(i + 1)}/"),
            "ss_vectors": (self.dL, self.ss_vec_top, lambda i: f"p{_sub(i + 1)}/"),
            "ss_mapping": (self.rL, self.ss_map_top, lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
            "ss_projection": (self.dL, self.ss_proj_top, lambda i: f"p{_sub(i + 1)}/"),
        }
        for key, (n, top, label) in matrix_units.items():
            if not self.tile_open(key, "units"):
                continue
            for i in range(n):
                self.cells.append(CellBox(f"ucol:{key}:{i}", self.col_x["units"], top(i),
                                     self.col_w["units"], ROW_H, "units", text=label(i)))
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
            n = self.rows[key].nsub
            for i in range(n):
                cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
                self.cells.append(CellBox(cid, self.col_x["units"], self.rows[key].y + i * ROW_H,
                                     self.col_w["units"], ROW_H, "units", text=text))
        if "units" in self.rows:
            uy = self.rows["units"].y
            # The units row's per-column-family table: (column count, column-left accessor, label
            # for column i). /gᵢ over the generators, /pᵢ over the domain primes; the chapter-9
            # superspace columns take /gLᵢ over the superspace generators and /pᵢ over the
            # superspace primes (true primes p — NOT the on-domain b, even when nonstandard).
            # Every ratio column is dimensionless /1: all of V = C|U (each sub-column), each
            # detempering generator, the targets, the interest kets and the held intervals. The
            # interval lists use their SHOWN count so an open draft column gets its /1 too (the
            # consolidated V already does, via nv_shown) — otherwise the units row alone goes blank
            # under the draft while every other row greens it.
            column_units = {
                "canongens": (self.rc, self.canongen_left, lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
                "gens": (self.r, self.gen_left, lambda i: f"/g{_sub(i + 1)}"),
                "primes": (self.d, self.prime_left, lambda i: f"/{self.domain_label}{_sub(i + 1)}"),
                "ssgens": (self.rL, self.ss_gen_left, lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
                "ssprimes": (self.dL, self.ss_prime_left, lambda i: f"/p{_sub(i + 1)}"),
                # the *_shown counts so a pending draft column carries its /1 too — commas already did
                # (nv_shown); targets/held/interest now match, the draft column reading complete.
                "commas": (self.nv_shown, self.comma_left, lambda i: "/1"),
                "detempering": (self.r, self.detempering_left, lambda i: "/1"),
                "targets": (self.k_shown, self.target_left, lambda i: "/1"),
                "interest": (self.mi_shown, self.interest_left, lambda i: "/1"),
                "held": (self.nh_shown, self.held_left, lambda i: "/1"),
            }
            for key, (n, left, label) in column_units.items():
                if not self.tile_open("units", key):
                    continue
                for i in range(n):
                    self.cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                         "units", text=label(i)))

    def _emit_quantities_row(self) -> None:
        """The quantities row: domain primes, interval ratios, their ± controls and the reorder grips."""
        # quantities row: domain primes (+ controls) and target ratios (below the
        # tile's toggle head, like every other row's values). The whole row -- its
        # headers and the domain/comma ± controls riding it -- answers to the specific
        # "quantities" toggle, which drops it from row_y via its present flag.
        if "quantities" in self.rows:
            qy = self.rows["quantities"].y

            def branch_minus(cid, ckey, i, kind, **kw):
                """a hover − centred on column ckey's i-th branch point (its top-bus split): the
                zone occupies the fan-out gap ABOVE the header (where the revealed button parks),
                COL_W wide on the sub-axis, frozen with the fan. It stops AT the header's top edge
                — the header ratio is an editable input, and a covering z-index-4 zone would
                swallow clicks into it. For an interval column the prominent drag grip overlays the
                zone's TOP, so its button reveals at the zone's BOTTOM instead (CSS .rtt-minus-low)."""
                self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y, COL_W,
                                     qy - self.fanout_y, kind, **kw))

            if self.tile_open("quantities", "gens"):  # the generator ratios heading their sub-columns,
                for g in range(self.r):                # the column-header dual of the spine list (gen:i)
                    self.cells.append(CellBox(f"qgen:{g}", self.gen_left(g), qy, COL_W, ROW_H, "genratio", text=self.gens[g], gen=g))
                # the generators ± mirrors the mapping-row ± (same quantity, the generators): the + on
                # the column stub un-temps a comma (−n, +r, hold d), the − on the LAST generator's
                # branch point drops that row (+n, −r, hold d), removable when r > 1
                if self.r > 1:
                    branch_minus("gen_minus", "gens", self.r - 1, "gen_minus", gen=self.r - 1)
            if self.tile_open("quantities", "canongens"):  # the canonical generator ratios heading the
                for g in range(self.rc):                   # canonical-generators column (read-only; no ±)
                    self.cells.append(CellBox(f"cangen:{g}", self.canongen_left(g), qy, COL_W, ROW_H, "genratio", text=self.canon_gens[g]))
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
                if self.element_draft:  # the green ?/? draft column: type a rational to add a new basis
                    # element (held just). A distinct id so it's removed, not restructured, on commit.
                    draft_text = self.pending_element or "?/?"
                    self.cells.append(CellBox("prime:pending", self.prime_left(self.d), qy, COL_W, ROW_H,
                                              self._element_cell_kind(draft_text), text=draft_text, prime=self.d, pending=True))
                    branch_minus("element_minus:pending", "primes", self.d, "element_minus")
                # The domain −. Box OFF (standard prime walk): only the HIGHEST prime is removable
                # (shrink_domain trims the last), so a single − rides that prime's branch point — and
                # only when the shrink actually applies (gated like editor.shrink, never shown inert).
                # Box ON (nonstandard, typed domain): the walk − gives way to a per-element − on EVERY
                # element's branch point — each removes just that element (remove_domain_element),
                # mirroring how each interval-list column carries its own −. Both are withheld at the
                # last element (d == 1: a domain keeps one). The draft column carries its own cancel −.
                if self.show_nonstandard_domain:
                    if self.d > 1:
                        for p in range(self.d):
                            branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
                elif self.domain_can_shrink:
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
                    self.cells.append(CellBox(f"comma:{self.col_token('commas', c)}", self.comma_left(c), qy, COL_W, ROW_H, "ratiocell", text=self.comma_ratios[c], comma=c))
                    self._voice("quantities:commas", c, self.comma_sizes.just[c])
                if self.comma_draft:  # the draft/ghost's ratio over its vector column. A real draft is
                    # an editable "?/?" (type a fraction to fill it, or its vector cells); a hover ghost
                    # is a read-only face showing the born comma's COMPUTED ratio. A distinct id so it's
                    # removed, not restructured, on commit.
                    self.cells.append(CellBox("comma:pending", self.comma_left(self.nc), qy, COL_W, ROW_H,
                                         "commaratio" if self.ghost_comma else "ratiocell",
                                         text=(self.ghost_comma_ratio or DASH) if self.ghost_comma else "?/?",
                                         comma=self.nc, pending=True))
                if self.show_unchanged:  # the unchanged interval ratios complete V = C|U. EDITABLE (the
                    # scalar twin of the editable U vector) when the tuning is a full rational projection —
                    # typing a fraction retunes; read-only "commaratio" (em-dash) otherwise.
                    full_u = self.unchanged_basis is not None and all(v is not None for v in self.unchanged_basis)
                    for j in range(self.nu):  # (derived from the projection), the held primes "2/1", "5/1"
                        doomed = self.pending is not None and j == self.nu - 1  # about to be deleted → read-only
                        self.cells.append(CellBox(f"unchanged:{j}", self.comma_left(self.nc_shown + j), qy, COL_W, ROW_H,
                                             "ratiocell" if (full_u and not doomed) else "commaratio",
                                             text=self.unchanged_ratios[j] or DASH, comma=self.nc + j))
                        self._voice("quantities:commas", self.nc + j, self.unchanged_sizes.just[j])
                # commas mirror the interval lists: + starts a (pending) comma; each comma carries
                # its OWN − on its branch point, so ANY one is removable — un-tempering it (−n, +r),
                # down to and including the last (which leaves just intonation, nullity 0). The draft
                # column's − cancels it. Stays live in the consolidated V view (removing a comma grows
                # U by a column) — only the C half carries −, never the derived unchanged columns.
                for c in range(self.nc):
                    branch_minus(f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
                if self.pending is not None:
                    branch_minus("comma_minus:pending", "commas", self.nc, "comma_minus")
            if self.tile_open("quantities", "detempering"):  # the detempering generators as ratios (read-only,
                for i in range(self.r):                       # derived from M like the comma ratios — no ± control)
                    self.cells.append(CellBox(f"detempering:{i}", self.detempering_left(i), qy, COL_W, ROW_H, "commaratio", text=self.gens[i]))
                    self._voice("quantities:detempering", i, self.detempering_sizes.just[i])
            # the three cleanly-uniform editable interval-ratio lists. Each heads its columns with an
            # editable ratiocell (the scalar twin of the editable vector below), _voice's it, and rides
            # a per-column − plus a pending-draft "?/?" cell with its own cancel −. The only per-list
            # differences (count, left-x, ratio/size source, draft, kind, whether a − shows) live in
            # the _QtyList descriptor. Targets are special only in that the auto Tₚ = I list is the
            # read-only computed twin of its vectors column (commaratio, no −); user-curated targets,
            # held and interest are all editable ratiocells, each column removable.
            if self.tile_open("quantities", "targets"):
                self._emit_qty_list(_QtyList("targets", "target", self.k, self.target_left, self.targets,
                                             self.target_sizes, self.pending_target,
                                             "ratiocell" if self.targets_editable else "commaratio",
                                             self.targets_editable), qy, branch_minus)
            if self.tile_open("quantities", "held"):  # the held intervals, edited like the intervals of interest
                self._emit_qty_list(_QtyList("held", "held", self.nh, self.held_left, self.held_ratios,
                                             self.held_sizes, self.pending_held, "ratiocell", True), qy, branch_minus)
            if self.tile_open("quantities", "interest"):  # the user's other intervals of interest
                self._emit_qty_list(_QtyList("interest", "interest", self.mi, self.interest_left, self.interest_ratios,
                                             self.interest_sizes, self.pending_interest, "ratiocell", True), qy, branch_minus)

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
                # Under the consolidated V the comma stub rides the C|U gap (or the nullity stub at full
                # rank — see col_plus_x), so narrow the zone to that stub's width: a full COL_W zone
                # would reach across the gap and occlude U's first grip (grip:unchanged:0).
                add_w = COL_W
                if ckey == "commas" and self.show_unchanged:
                    add_w = self.empty_comma_w if self.nc_shown == 0 else V_SPLIT_GAP
                self.cells.append(CellBox(f"grip:{ckey}:add", self.plus_stub_x[ckey] - add_w / 2,
                                     grip_top, add_w, GRIP_BAND, "colgrip"))

            # the grips (and their drop zone) ride this quantities-row block, so they stay tied to it:
            # _plus_shows now also fires for a column shown only in the vectors row (so its + survives
            # there), but the reorder grips remain a quantities-row affordance — gate them back on the
            # row being open. Every list grips each existing column: even a sole comma drags out now.
            counts = {"commas": self.nc, "targets": self.k, "held": self.nh, "interest": self.mi}
            for ckey in ("commas", "targets", "held", "interest"):
                if self.row_open("quantities") and self._plus_shows(ckey):
                    drag_controls(ckey, counts[ckey])
            # the consolidated V's unchanged half U also grips — each KNOWN unchanged interval is a
            # cross-list DRAG SOURCE (drop it on another list to copy it there; U is derived, so it
            # isn't removed and accepts no drops — see editor.move_interval). A dashed column has no
            # interval, so no grip. Keyed "grip:unchanged:{j}" so the colgrip handler reads list
            # "unchanged" and idx j (the U index move_interval expects); placed on the U sub-axes.
            if self.show_unchanged:
                for j in range(self.nu):
                    if self.unchanged_basis[j] is not None:
                        self.cells.append(CellBox(f"grip:unchanged:{j}", self.sub_axis_x("commas", self.nc_shown + j) - COL_W / 2,
                                             grip_top, COL_W, GRIP_BAND, "colgrip", comma=j))

    def _emit_column_plus_controls(self) -> None:
        """The addable columns' + controls riding the shared column fan above the grid."""
        # The addable columns' + controls ride the shared column fan above the grid, NOT inside the
        # quantities row — so they survive that row being hidden, keeping every interval kind addable
        # from the interval-vectors row alone (clicking + then drops the cursor into the new column's
        # first vector cell; see app.add_interval). plus_stub_x already holds exactly the columns whose
        # + shows — built from _plus_shows, which counts the vectors row too — and where on the fan its
        # stub rides (the top bus stretches out to reach it; an empty set centres it on the trunk). With
        # the nonstandard-domain box on, the domain + opens a typed ?/? element draft (element_plus →
        # editor.add_element) rather than walking to the next prime (plus → expand).
        primes_plus = "element_plus" if self.show_nonstandard_domain else "plus"
        for ckey, cid in (("gens", "gen_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                          ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
            if ckey in self.plus_stub_x:
                self.cells.append(CellBox(cid, self.plus_stub_x[ckey] - BTN / 2, self.fanout_y - BTN / 2, BTN, BTN, cid))

    def _emit_rehomed_minus_controls(self) -> None:
        """The interval columns' − controls re-homed onto the vectors row when the quantities row is hidden."""
        # The interval columns' − controls — each column's removal, and the draft column's cancel —
        # normally ride the quantities row (emitted in its block above). When that row is hidden but
        # the interval vectors are shown, re-home them onto the vectors row: its top edge bounds the
        # hover zone, exactly as the quantities row's did, so a column (or an accidental draft) stays
        # removable there. The block above already emits these when the quantities row IS open, so
        # this stays idle then to avoid doubling them. The domain/generator − are NOT re-homed — their
        # twins basis_minus (vectors row) and map_minus (mapping row) already cover those.
        if not self.row_open("quantities") and self.row_open("vectors"):
            vtop = self.rows["vectors"].y
            def vec_minus(cid, ckey, i, kind, **kw):  # a − hover zone over column ckey's i-th branch point
                self.cells.append(CellBox(cid, self.sub_axis_x(ckey, i) - COL_W / 2, self.fanout_y,
                                     COL_W, vtop - self.fanout_y, kind, **kw))
            if self.tile_open("vectors", "commas"):
                for c in range(self.nc):
                    vec_minus(f"comma_minus:{self.col_token('commas', c)}", "commas", c, "comma_minus", comma=c)
                if self.pending is not None:
                    vec_minus("comma_minus:pending", "commas", self.nc, "comma_minus")
            if self.tile_open("vectors", "targets"):
                if self.targets_editable:
                    for j in range(self.k):
                        vec_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
                if self.pending_target is not None:
                    vec_minus("target_minus:pending", "targets", self.k, "target_minus")
            if self.tile_open("vectors", "held"):
                for i in range(self.nh):
                    vec_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
                if self.pending_held is not None:
                    vec_minus("held_minus:pending", "held", self.nh, "held_minus")
            if self.tile_open("vectors", "interest"):
                for i in range(self.mi):
                    vec_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
                if self.pending_interest is not None:
                    vec_minus("interest_minus:pending", "interest", self.mi, "interest_minus")

    def _emit_mapping_band(self) -> None:
        """Generator ratios, the mapping matrix, its mapped lists and the draft generator row."""
        # generator ratios (aligned with the mapping rows they label) + the mapping
        # matrix and its mapped target interval list
        if self.row_open("mapping"):
            # the generators list the mapping's rows: a vertical ratio list in the
            # quantities spine column, labelling the rows as the primes label the columns
            if self.tile_open("mapping", "quantities"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"gen:{self.col_token('gens', i)}", self.col_x["quantities"], self.map_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.gens[i] if i < len(self.gens) else "", gen=i))
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
                        self.cells.append(CellBox(f"map_minus:{self.col_token('gens', i)}", map_bus_x, self.map_top(i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
                if "mapping" in self.row_plus_y:  # only when there's a comma to un-temper (n > 0)
                    self.cells.append(CellBox("map_plus", map_bus_x - BTN / 2, self.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))
            # a drag handle hugging the left of each mapping row: drag one generator row onto another
            # to ADD it into that row (a generator-basis change holding the temperament and tuning).
            # Needs ≥ 2 rows to combine; rides the reserved handle gutter to the LEFT of the row
            # labels (𝒎ᵢ), the leftmost slot of the widened primes column. (The column-reorder
            # handles a sibling concern adds ride the branch points up top — deliberately separate.)
            if self.settings.get("drag_to_combine") and self.r > 1 and self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.cells.append(CellBox(f"map_drag:{self.col_token('gens', i)}", self.primes_x + self.etpick_left_pad("primes"), self.map_top(i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))
            mx, mw = self.matrix_span("primes")
            etpick_x = mx + mw + ETPICK_GAP  # past the ] (the right gutter matrix_span reclaimed)
            for i in range(self.r):
                rt = self.col_token("gens", i)  # the row's stable id-token (== i until a removal/re-rank)
                if self.tile_open("mapping", "primes"):
                    # the per-row ET picker rides the RIGHT gutter, past the ] (a compact chooser; pick
                    # a curated ET to set this generator row to its val) — the analogue of the comma
                    # picker below each comma column. The crowded left (handles, 𝒎ᵢ labels) stays clear.
                    if self.show_presets:
                        self.cells.append(CellBox(f"etpick:{rt}", etpick_x, self.map_top(i), ETPICK_W, ROW_H, "etpick", gen=i))
                    for p in range(self.d):
                        # text carries the mapping entry into the CellBox content (like the comma /
                        # target / held / interest vector cells already do) so changed_cell_ids sees a
                        # mapping change — otherwise the edit preview is blind to the matrix a
                        # temperament swap or a +/- rewrites. The input still shows it via _update_mapping.
                        self.cells.append(CellBox(ids.mapping_cell(rt, p), self.prime_left(p), self.map_top(i), COL_W, ROW_H, "mapping", text=str(self.state.mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("mapping", "primes", gen=i, prime=p)))
                if self.tile_open("mapping", "targets"):
                    self._emit_mapped_tile(_MappedTile("mapped", "targets", self.k, self.target_left, self.mapped, self.pending_target), i, rt)
                if self.tile_open("mapping", "interest"):  # interest mapped through M, like the targets
                    self._emit_mapped_tile(_MappedTile("imapped", "interest", self.mi, self.interest_left, self.interest_mapped, self.pending_interest), i, rt)
                if self.tile_open("mapping", "held"):  # held mapped through M, like the targets / interest
                    self._emit_mapped_tile(_MappedTile("hmapped", "held", self.nh, self.held_left, self.held_mapped, self.pending_held), i, rt)
                # the comma basis mapped through M — it vanishes to 0 (parallel to the
                # mapped target list); the raw basis lives in the interval-vectors row.
                # Over V the unchanged basis maps too (M·U ≠ 0 — the held intervals in gen coords).
                if self.tile_open("mapping", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(i), COL_W, ROW_H, "mapped", text=str(self.mapped_commas[i][c]), gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
                    if self.comma_draft:  # the draft/ghost comma's cell in this row, so the column reads
                        # green down through the computed rows. A real draft is blank; a − hover ghost
                        # shows M[i]·newborn (0 on every surviving row, nonzero only on the removed row,
                        # which reds over it).
                        mc_text = str(self.ghost_comma_mapped[i]) if (self.ghost_comma and i < len(self.ghost_comma_mapped)) else ""
                        self.cells.append(CellBox(f"cell:mapped_comma:{rt}:{self.pending_col_token('commas')}", self.comma_left(self.nc), self.map_top(i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
                    for j in range(self.nu):
                        mapped_text = DASH if self.unchanged_mapped[i][j] is None else str(self.unchanged_mapped[i][j])
                        self.cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", self.comma_left(self.nc_shown + j), self.map_top(i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=self.cell_unit("mapping", "commas", gen=i)))
            # the draft generator row being added: a green ?/blank row at index r — the ROW mirror of
            # the pending comma COLUMN. It rides ONLY the mapping band (the genmap, canonical mapping
            # and comma dual all stay at the committed rank), and commits once the typed row appended
            # to M is a proper temperament (set_pending_mapping_row). Beyond the editable matrix BLANKS
            # the user fills (plus a "?" generator ratio on the spine and a − to cancel), every derived
            # mapped tile gets a blank green PLACEHOLDER at the draft row, so the row reads green ALL
            # THE WAY ACROSS the band — the row mirror of a draft column reading green top-to-bottom
            # (the values are undefined until the row commits). The r_shown brackets enclose them.
            # The green row at index r: an editable DRAFT (pending_mapping_row — the user types a new
            # generator) or a non-editable GHOST (a comma − hover's born generator). Same green
            # ?/blank row across the band; the ghost just renders read-only ("mapped" matrix cells,
            # no cancel −) since there's nothing to type during a hover.
            if self.row_draft:
                dr = self.r  # the draft/ghost row's index, one past the committed generators
                drt = self.pending_col_token("gens")  # its id-token, one past every committed row's
                if self.tile_open("mapping", "quantities"):
                    # a real draft's generator ratio is unknown ("?"); the hover ghost's is the born
                    # generator's computed ratio
                    gen_text = self.ghost_row_ratio if self.ghost_row else "?"
                    self.cells.append(CellBox("gen:pending", self.col_x["quantities"], self.map_top(dr), self.col_w["quantities"], ROW_H, "genratio", text=gen_text, gen=dr, pending=True))
                    if not self.ghost_row:  # a real draft carries a − to cancel it; a hover ghost doesn't
                        map_bus_x = self.node_edge + self.FAN if self._row_fans("mapping") else self.node_edge
                        gen_right = self.col_x["quantities"] + self.col_w["quantities"]
                        self.cells.append(CellBox("map_minus:pending", map_bus_x, self.map_top(dr), gen_right - map_bus_x, ROW_H, "map_minus", gen=dr, pending=True))
                if self.tile_open("mapping", "primes"):
                    row_kind = "mapped" if self.ghost_row else "mapping"  # ghost is read-only
                    for p in range(self.d):
                        # the ghost shows the born generator's COMPUTED prime coords; a real draft is blank
                        v = self.ghost_row_map[p] if self.ghost_row else self.pending_mapping_row[p]
                        self.cells.append(CellBox(ids.mapping_cell(drt, p), self.prime_left(p), self.map_top(dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
                    # a real draft row gets its own ET picker too (right gutter, like the committed
                    # rows): pick a curated ET to fill and commit it (add it as a generator). A hover
                    # ghost (read-only) doesn't.
                    if not self.ghost_row and self.show_presets:
                        mx, mw = self.matrix_span("primes")
                        self.cells.append(CellBox("etpick:draft", mx + mw + ETPICK_GAP, self.map_top(dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
                # the derived mapped tiles (M·target / M·interest / M·held / M·comma / M·U for the new
                # generator). A real draft is blank (undefined until it commits); a − hover ghost shows
                # the born generator's COMPUTED images (self.ghost_row_mapped), so the row reads green
                # all the way across with real values.
                def gmap(key, j):
                    vals = self.ghost_row_mapped.get(key, ()) if self.ghost_row else ()
                    if j >= len(vals):
                        return ""
                    return DASH if vals[j] is None else str(vals[j])
                if self.tile_open("mapping", "targets"):
                    for j in range(self.k):
                        self.cells.append(CellBox(f"cell:mapped:{drt}:{self.col_token('targets', j)}", self.target_left(j), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("targets", j), gen=dr, pending=True))
                if self.tile_open("mapping", "interest"):
                    for ii in range(self.mi):
                        self.cells.append(CellBox(f"cell:imapped:{drt}:{self.col_token('interest', ii)}", self.interest_left(ii), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("interest", ii), gen=dr, pending=True))
                if self.tile_open("mapping", "held"):
                    for hi in range(self.nh):
                        self.cells.append(CellBox(f"cell:hmapped:{drt}:{self.col_token('held', hi)}", self.held_left(hi), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("held", hi), gen=dr, pending=True))
                if self.tile_open("mapping", "commas"):
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:mapped_comma:{drt}:{self.col_token('commas', c)}", self.comma_left(c), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("commas", c), gen=dr, pending=True))
                    for j in range(self.nu):
                        self.cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", self.comma_left(self.nc_shown + j), self.map_top(dr), COL_W, ROW_H, "mapped", text=gmap("unchanged", j), gen=dr, pending=True))

    def _emit_mapped_tile(self, m: _MappedTile, i: int, rt: str) -> None:
        """Emit one committed-row read-only M·X tile (targets / interest / held) for generator row
        `i` (id-token `rt`): one "mapped" CellBox per committed column carrying str(m.data[i][col]),
        then a blank green placeholder under the open draft column. Caller has already gated on the
        tile being open. Behaviour-identical to the former three inline blocks; only `m` differs."""
        for col in range(m.count):
            self.cells.append(CellBox(f"cell:{m.prefix}:{rt}:{self.col_token(m.group, col)}", m.left_fn(col), self.map_top(i), COL_W, ROW_H, "mapped", text=str(m.data[i][col]), gen=i, unit=self.cell_unit("mapping", m.group, gen=i)))
        if m.pending is not None:  # blank green placeholder under the draft column
            self.cells.append(CellBox(f"cell:{m.prefix}:{rt}:draft", m.left_fn(m.count), self.map_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))

    def _emit_mapped_grid(self, tile, prefix, grid, n_cols, left, col_kw, *,
                          full=None, colwise=False, col_token_key=None, inset=0,
                          row="projection", top=None, height=None, pending=None) -> None:
        """One read-only ("mapped") grid of a projection band: ``height`` rows over ``row``'s
        prime-indexed tops (``top``, default proj_top) × ``n_cols`` columns at ``left(j)``, each
        cell id ``cell:{prefix}:…`` with ``col_kw`` (prime/gen/comma) carrying the column index.
        ``full`` gates dashing — every cell an em-dash when the tuning isn't a full rational
        projection — defaulting to ``grid is not None`` (P, G and the superspace pair each dash
        on their own matrix; the P·X family instead shares the caller's one projection_rationals
        flag). Row-major grids (P / G / G_L→s / P_L→s) are matrices of pre-stringified entries
        emitted row-by-row with ids ``…:{row}:{col}``. ``colwise`` grids (the P·X family) are
        lists of ``height``-tall projected column vectors: emitted column-by-column, entries
        ``grid[col][row]`` str()-wrapped, ids ``…:{col}:{row}`` — ``col_token_key`` swaps that
        id's column index for the column's identity token — and each cell also carries
        ``prime=row``. ``inset`` narrows each cell within its COL_W slot (centred), like the
        loose interest kets the P·interest grid sits under. ``row``/``top``/``height`` retarget
        the whole grid to another projection band (the superspace P_L row reuses this verbatim).

        A ``pending`` draft (the colwise P·X family of an interval list being added) appends one
        blank green column at ``left(n_cols)`` — so the existence of the tile is enough to green
        the draft column, with no per-list draft branch to forget (the gap this rework closes)."""
        if not (self.row_open(row) and self.tile_open(row, tile)):
            return
        if full is None:
            full = grid is not None
        top = top or self.proj_top
        height = self.d if height is None else height

        def cell(i, j):  # row i (a domain-prime index), column j
            if colwise:
                text = str(grid[j][i]) if full else DASH
                tok = j if col_token_key is None else self.col_token(col_token_key, j)
                cid, kw = f"cell:{prefix}:{tok}:{i}", {"prime": i, col_kw: j}
            else:
                text = grid[i][j] if full else DASH
                cid, kw = f"cell:{prefix}:{i}:{j}", {col_kw: j}
            self.cells.append(CellBox(cid, left(j) + inset, top(i),
                                 COL_W - 2 * inset, ROW_H, "mapped", text=text, **kw))

        if colwise:
            for j in range(n_cols):
                for i in range(height):
                    cell(i, j)
            if pending is not None:  # the open draft column: a blank green slot per row (the fix)
                for i in range(height):
                    self.cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols) + inset, top(i),
                                         COL_W - 2 * inset, ROW_H, "mapped", text="", prime=i, pending=True))
        else:
            for i in range(height):
                for j in range(n_cols):
                    cell(i, j)

    def _emit_projection_band(self) -> None:
        """The projection band: P = GM, the embedding G, the projected lists and the scaling factors."""
        # the projection matrix P = GM: a d×d operator over the domain primes, a stack of read-only
        # maps like the mapping. Its cells are "mapped" (a computed value, NOT per-cell editable — a
        # single entry can't keep P idempotent with the commas in its kernel, so editing is only via
        # the whole-matrix plain-text band below), carrying the rational entry text ("1", "0", "1/4")
        # service stringified. P is totally DASHED when the tuning isn't a full rational projection
        # (projection_matrix None — it holds fewer than r rational intervals): every cell an em-dash.
        self._emit_mapped_grid("primes", "proj", self.projection_matrix, self.d, self.prime_left, "prime")
        # the generator embedding G = H(MH)⁻¹ (d×r), beside P in the gens columns: its columns are
        # the held tuning's generators as fractional vectors. Read-only ("mapped") cells like P (edited
        # only via the plain-text band, since 𝑀𝐺 = 𝐼 couples every entry), over the r generator columns
        # rather than the d primes. Dashed in lockstep with P (embedding_matrix None ⟺ not a full rational projection).
        self._emit_mapped_grid("gens", "embed", self.embedding_matrix, self.r, self.gen_left, "gen")
        # the chapter-9 superspace projection tiles (between G and P): G_L→s a d×rL vector list over the
        # superspace-generator columns, P_L→s a d×dL covector stack over the superspace-prime columns —
        # read-only ("mapped"), dashed in lockstep with P/G when the tuning isn't a full rational projection.
        self._emit_mapped_grid("ssgens", "embed_sl", self.embedding_superspace, self.rL, self.ss_gen_left, "gen")  # G_L→s
        self._emit_mapped_grid("ssprimes", "proj_sl", self.projection_superspace, self.dL, self.ss_prime_left, "prime")  # P_L→s = G_L→s·M_L

        # the projected unrotated vector list P·V (the projection row over the V column): each
        # unrotated vector scaled by its eigenvalue — the comma columns vanish (P·𝐜 = 0, the
        # eigenvalue-0 directions), the unchanged columns are held unchanged (P·𝐮 = 𝐮, eigenvalue 1).
        # d-tall prime-count-vector columns, like the interval-vectors V it projects.
        if self.show_unchanged and self.row_open("projection") and self.tile_open("projection", "commas"):
            for c in range(self.nc):  # P·comma = the zero vector
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:{self.col_token('commas', c)}", self.comma_left(c), self.proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            if self.comma_draft:  # the draft/ghost comma's P·column: a born comma (ghost) vanishes, so
                # P·comma = 0 (the zero vector) like every committed comma; a real draft is blank
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:draft", self.comma_left(self.nc), self.proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0" if self.ghost_comma else "", prime=p, pending=True))
            for j in range(self.nu):  # P·unchanged = the unchanged interval itself (dashed if U is)
                dashed = self.unchanged_basis[j] is None
                for p in range(self.d):
                    self.cells.append(CellBox(f"cell:proj_v:{p}:u{j}", self.comma_left(self.nc_shown + j), self.proj_top(p),
                                         COL_W, ROW_H, "mapped",
                                         text=DASH if dashed else str(self.unchanged_basis[j][p]), prime=p, comma=self.nc + j))

        # the projection row's quantities spine: the domain primes (2, 3, 5) label its prime-indexed
        # rows, like the interval-vectors basis spine — read-only (the whole projection row is derived,
        # so no editable elementcell / domain ± controls; the domain is edited from the vectors row).
        if self.row_open("projection") and self.tile_open("projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2  # square, centred in the spine
            for p in range(self.d):
                self.cells.append(CellBox(f"proj_basis:{p}", bx, self.proj_top(p), COL_W, ROW_H, "prime", text=str(self.elements[p]), prime=p))
        # the projected vector lists — P applied to each column's interval vectors — read-only ("mapped")
        # cells carrying the rational entry text ("1", "0", "1/4"), DASHED in lockstep with P when the
        # tuning isn't a full rational projection (projection_rationals None). d-tall columns over the
        # domain primes, like the interval-vectors row they project: P·D over the detempering column (=
        # the embedding G), P·T over the targets, P·H = H over the held basis, P·interest over the loose
        # interest kets (inset, a collection not a matrix).
        full_proj = self.projection_rationals is not None
        self._emit_mapped_grid("detempering", "proj_pd", self.proj_detempering, self.r, self.detempering_left, "gen",
                               full=full_proj, colwise=True, col_token_key="detempering")  # P·D = G
        self._emit_mapped_grid("targets", "proj_pt", self.proj_targets, self.k, self.target_left, "comma",
                               full=full_proj, colwise=True, pending=self.pending_target)  # P·T
        self._emit_mapped_grid("held", "proj_ph", self.proj_held, self.nh, self.held_left, "comma",
                               full=full_proj, colwise=True, pending=self.pending_held)  # P·H = H
        self._emit_mapped_grid("interest", "proj_pi", self.proj_interest, self.mi, self.interest_left, "comma",
                               full=full_proj, colwise=True, inset=KET_INSET, pending=self.pending_interest)  # P·interest

        # the scaling factors λ = diag(λ): the projection's eigenvalue list over the V column —
        # 0 for each comma sub-column (vanished, eigenvalue 0) then 1 for each unchanged
        # sub-column (held, eigenvalue 1). Read-only computed values ("mapped"), one ROW_H list.
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):
            # 0 for each comma (vanished), 1 for each KNOWN unchanged direction; a dashed unchanged
            # column (the tuning leaves that direction irrational) has no determined eigenvalue → dash
            scaling = ["0"] * self.nc + [(DASH if v is None else "1") for v in self.unchanged_basis]
            for c, lam in enumerate(scaling):  # comma_value_pos skips the pending-draft slot for the U half
                self.cells.append(CellBox(f"cell:scaling:{self.col_token('commas', c)}", self.comma_left(self.comma_value_pos(c)), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text=lam, comma=c))
            if self.comma_draft:  # the comma draft column's λ slot: a born comma (ghost) vanishes, so
                # eigenvalue 0 like every committed comma; a real draft is blank until it commits
                self.cells.append(CellBox("cell:scaling:draft", self.comma_left(self.nc), self.rows["scaling_factors"].y,
                                     COL_W, ROW_H, "mapped", text="0" if self.ghost_comma else "", pending=True))

    def _emit_canon_band(self) -> None:
        """The canonical-mapping row: 𝑀_C, the generator form matrix 𝐹, and 𝑀_C's mapped lists."""
        # the canonical-mapping form box: M in canonical form (defactored + HNF), a stack of
        # read-only maps over the primes, framed like the mapping matrix one row above it; the
        # generator form matrix F (units g_C/g) rides its gens column as a bordered r×r grid.
        # The canonical generators ratio list (g_C) labels the canon rows in the quantities spine,
        # exactly as the stored generators label the mapping rows one row below (𝐹⁻¹𝐹 = 𝐼 rides
        # the canonical-generators column — see _emit_identity_objects). The remaining tiles are
        # 𝑀_C's mapped lists (𝑀_C·D / 𝑀_C·C / 𝑀_C·H / Y_C / 𝑀_C·interest) — the canonical-form twins
        # of the mapping row's read-only M·X tiles, emitted the same way (gen=i over the rc rows).
        if self.row_open("canon"):
            if self.tile_open("canon", "quantities"):  # the canonical generators in the spine, labelling the canon rows
                for i in range(self.rc):
                    self.cells.append(CellBox(f"canon:gen:{i}", self.col_x["quantities"], self.canon_top(i), self.col_w["quantities"], ROW_H, "genratio", text=self.canon_gens[i] if i < len(self.canon_gens) else ""))
            if self.tile_open("canon", "primes"):
                for i in range(self.rc):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:canon:{i}:{p}", self.prime_left(p), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapping[i][p]), gen=i, prime=p, unit=self.cell_unit("canon", "primes", gen=i, prime=p)))
            if self.tile_open("canon", "gens"):
                for i in range(len(self.form_M)):
                    for j in range(len(self.form_M)):
                        self.cells.append(CellBox(f"cell:form:{i}:{j}", self.gen_left(j), self.canon_top(i), COL_W, ROW_H, "formcell", text=str(self.form_M[i][j]), unit=self.cell_unit("canon", "gens", gen=i)))
            # 𝑀_C's mapped lists — the canonical-form twins of the mapping row's read-only M·X tiles
            for i in range(self.rc):
                if self.tile_open("canon", "detempering"):  # 𝑀_C·D = 𝐹, an rc × r genmap like 𝑀D = 𝐼
                    for c in range(self.r):
                        self.cells.append(CellBox(f"cell:canon_detempering:{i}:{self.col_token('detempering', c)}", self.detempering_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapped_detempering[i][c]), gen=i, unit=self.cell_unit("canon", "detempering", gen=i)))
                if self.tile_open("canon", "targets"):  # Y_C = 𝑀_C·T
                    self._emit_canon_mapped_tile("canon_mapped", "targets", self.k, self.target_left, self.canon_mapped, self.pending_target, i)
                if self.tile_open("canon", "interest"):  # 𝑀_C·interest (stands alone, no outer bracket)
                    self._emit_canon_mapped_tile("canon_imapped", "interest", self.mi, self.interest_left, self.canon_interest_mapped, self.pending_interest, i)
                if self.tile_open("canon", "held"):  # 𝑀_C·H
                    self._emit_canon_mapped_tile("canon_hmapped", "held", self.nh, self.held_left, self.canon_held_mapped, self.pending_held, i)
                if self.tile_open("canon", "commas"):  # 𝑀_C·C vanishes to 𝑂; the V = C|U unchanged half maps too
                    for c in range(self.nc):
                        self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.col_token('commas', c)}", self.comma_left(c), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(self.canon_mapped_commas[i][c]), gen=i, unit=self.cell_unit("canon", "commas", gen=i)))
                    if self.comma_draft:  # green the draft comma column through the canon row too
                        self.cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{self.pending_col_token('commas')}", self.comma_left(self.nc), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
                    for j in range(self.nu):
                        ut = DASH if self.canon_unchanged_mapped[i][j] is None else str(self.canon_unchanged_mapped[i][j])
                        self.cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", self.comma_left(self.nc_shown + j), self.canon_top(i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=self.cell_unit("canon", "commas", gen=i)))

    def _emit_canon_mapped_tile(self, prefix, group, count, left_fn, data, pending, i) -> None:
        """One canon-row read-only 𝑀_C·X tile (targets / interest / held) for canonical row i: a
        "mapped" CellBox per committed column carrying str(data[i][col]), then a green placeholder
        under the open draft column — the canon-row twin of _emit_mapped_tile."""
        for col in range(count):
            self.cells.append(CellBox(f"cell:{prefix}:{i}:{self.col_token(group, col)}", left_fn(col), self.canon_top(i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=self.cell_unit("canon", group, gen=i)))
        if pending is not None:  # blank green placeholder under the draft column
            self.cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), self.canon_top(i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))

    def _emit_qty_list(self, q: _QtyList, qy: float, branch_minus) -> None:
        """Emit one editable interval-ratio column-list of the quantities row (targets / held /
        interest): per committed column a ratio CellBox, its _voice and (when minus_gate) its
        branch_minus −, then the pending-draft ratio cell with its cancel −. Behaviour-identical
        to the former three inline blocks; only `q`'s parameters differ. `branch_minus` and `qy`
        are the method-local control closure / row-y the inline blocks used."""
        for j in range(q.count):
            self.cells.append(CellBox(f"{q.singular}:{self.col_token(q.group, j)}", q.left_fn(j), qy, COL_W, ROW_H, q.kind, text=q.ratios[j], comma=j))
            self._voice(f"quantities:{q.group}", j, q.sizes.just[j])
            if q.minus_gate:
                branch_minus(f"{q.singular}_minus:{j}", q.group, j, f"{q.singular}_minus", comma=j)
        if q.pending is not None:  # the draft column: an editable "?/?" ratio, blank green cells below, − to cancel
            self.cells.append(CellBox(f"{q.singular}:pending", q.left_fn(q.count), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=q.count, pending=True))
            branch_minus(f"{q.singular}_minus:pending", q.group, q.count, f"{q.singular}_minus")

    def _emit_vec_grid(self, g: _VecGrid) -> None:
        """Emit one editable interval-vector grid (targets / held / interest): the committed
        `for col: for prime:` matrix of CellBoxes, then the pending-draft column if one is open.
        Behaviour-identical to the former three inline blocks; only `g`'s parameters differ."""
        for col in range(g.count):
            for p in range(self.d):
                self.cells.append(CellBox(g.id_fn(self.col_token(g.group, col), p), g.left_fn(col) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.committed_kind, text=str(g.data[col][p]), prime=p, comma=col, unit=self.cell_unit("vectors", g.group, prime=p)))
                self._voice(f"vectors:{g.group}", col, g.sizes.just[col])
        if g.pending is not None:  # the draft column: blank, green-outlined cells the user fills in
            for p in range(self.d):
                v = g.pending[p]
                self.cells.append(CellBox(g.id_fn(self.pending_col_token(g.group), p), g.left_fn(g.count) + g.inset, self.vec_top(p), COL_W - 2 * g.inset, ROW_H, g.pending_kind,
                                     text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=self.cell_unit("vectors", g.group, prime=p)))

    def _emit_vectors_band(self) -> None:
        """The interval-vectors row: the basis spine, comma/target/held/interest vectors and drag handles."""
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
                    # with the nonstandard-domain box on the spine elements are typeable — the vertical
                    # mirror of the editable quantities-row prime cells (same on_element_change): typing a
                    # rational relabels that basis element, holding its mapping coordinates. An integer
                    # prime shows as a plain number (elementcell), a nonprime as a stacked fraction
                    # (elementratio). Off, they're read-only domain primes.
                    text = str(self.elements[p])
                    kind = self._element_cell_kind(text) if self.show_nonstandard_domain else "prime"
                    self.cells.append(CellBox(f"basis:{p}", bx, self.vec_top(p), COL_W, ROW_H, kind, text=text, prime=p))
                # the left bus the controls ride (node_edge + FAN when the row fans — matching
                # row_axis); the − zone drops from it rightward over the bottom prime as the hover target
                basis_bus_x = self.node_edge + self.FAN if self._row_fans("vectors") else self.node_edge
                def basis_minus(cid, p, kind, **kw):  # a vertical − zone on the left bus, over row p's prime
                    self.cells.append(CellBox(cid, basis_bus_x, self.vec_top(p),
                                         (bx + COL_W) - basis_bus_x, ROW_H, kind, **kw))
                if self.element_draft:  # the green ?/? draft row below the stack: type a rational to add a
                    # new basis element (held just) — the row twin of the quantities-row prime:pending draft,
                    # committing through the SAME on_element_change. A distinct id so it's removed, not
                    # restructured, on commit; its − cancels the draft (like the quantities row's). The
                    # ":basis" id steers the shared element_minus builder to vertical (left-bus) styling.
                    draft_text = self.pending_element or "?/?"
                    self.cells.append(CellBox("basis:pending", bx, self.vec_top(self.d), COL_W, ROW_H,
                                              self._element_cell_kind(draft_text), text=draft_text, prime=self.d, pending=True))
                    basis_minus("element_minus:basis:pending", self.d, "element_minus")
                # the domain − on the spine, the row twin of the quantities − (see there). Box OFF: the
                # walk − (shrink) over the highest prime, only when it applies. Box ON: a per-element −
                # over EVERY element's row, each removing just that element; both withheld at d == 1.
                if self.show_nonstandard_domain:
                    if self.d > 1:
                        for p in range(self.d):
                            basis_minus(f"element_minus:basis:{p}", p, "element_minus", prime=p)
                elif self.domain_can_shrink:
                    basis_minus("basis_minus", self.d - 1, "basis_minus")
                if "vectors" in self.row_plus_y:  # the basis +: a typed ?/? element draft (element_plus →
                    # editor.add_element, box on) or the standard prime walk (plus → editor.expand, box off)
                    plus_kind = "element_plus" if self.show_nonstandard_domain else "plus"
                    self.cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, self.row_plus_y["vectors"] - BTN / 2,
                                         BTN, BTN, plus_kind))
            if self.tile_open("vectors", "commas"):
                for c in range(self.nc):
                    for p in range(self.d):
                        self.cells.append(CellBox(ids.comma_cell(self.col_token('commas', c), p), self.comma_left(c), self.vec_top(p), COL_W, ROW_H, "commacell", text=str(self.state.comma_basis[c][p]), prime=p, comma=c, unit=self.cell_unit("vectors", "commas", prime=p)))
                        self._voice("vectors:commas", c, self.comma_sizes.just[c])
                    # the per-column comma picker, in the band below the ⟩ foot (a compact chooser;
                    # pick a curated comma to set this column to its vector) — only REAL commas (not
                    # the unchanged half U, nor the pending draft) get one — see cpick_band_y
                    if self.show_presets:
                        self.cells.append(CellBox(f"commapick:{self.col_token('commas', c)}", self.comma_left(c), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=c))
                # the unchanged basis U completes V = C|U: the projection's eigenvalue-1 eigenvectors,
                # held just (e.g. 2/1, 5/1). EDITABLE (like the comma basis) when U is a FULL rational
                # projection — typing a new basis retunes to the projection that holds it; read-only
                # "vec" (with em-dashes) when the tuning leaves any direction irrational. While a comma
                # is being ADDED (a pending draft), the rank drops by one, so the last unchanged column
                # is about to be deleted: it goes read-only (not editable) and a single post-pass below
                # previews its WHOLE column red with the app's standard remove-preview look.
                full_u = self.unchanged_basis is not None and all(v is not None for v in self.unchanged_basis)
                for j in range(self.nu):
                    doomed = self.pending is not None and j == self.nu - 1
                    born = self.born_u and j == self.nu - 1  # the comma − hover's born held interval: read-only
                    for p in range(self.d):
                        vec_text = DASH if self.unchanged_basis[j] is None else str(self.unchanged_basis[j][p])
                        self.cells.append(CellBox(ids.unchanged_cell(j, p), self.comma_left(self.nc_shown + j), self.vec_top(p), COL_W, ROW_H,
                                             "unchangedcell" if (full_u and not doomed and not born) else "vec", text=vec_text, prime=p, comma=self.nc + j,
                                             unit=self.cell_unit("vectors", "commas", prime=p)))
                    self._voice("vectors:commas", self.nc + j, self.unchanged_sizes.just[j])
                if self.comma_draft:  # the green column at index nc: an editable draft, or a hover GHOST
                    col_kind = "vec" if self.ghost_comma else "commacell"  # ghost is read-only
                    for p in range(self.d):
                        # the ghost shows the born comma's COMPUTED prime coords; a real draft is blank
                        v = self.ghost_comma_vec[p] if self.ghost_comma else self.pending[p]
                        self.cells.append(CellBox(ids.comma_cell(self.pending_col_token('commas'), p), self.comma_left(self.nc), self.vec_top(p), COL_W, ROW_H, col_kind,
                                             text="" if v is None else str(v), prime=p, comma=self.nc, pending=True, unit=self.cell_unit("vectors", "commas", prime=p)))
                    # a real draft column gets its own picker too: pick a curated comma to fill and
                    # commit it (add it to the basis). A hover ghost (read-only) doesn't.
                    if self.pending is not None and self.show_presets:
                        self.cells.append(CellBox("commapick:draft", self.comma_left(self.nc), self.cpick_band_y("vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=self.nc, pending=True))
            if self.tile_open("vectors", "targets"):
                # the target interval list as vector columns — an EDITABLE hybrid input like the comma
                # basis (typing a column overrides the target set) — except the auto Tₚ = I list, which
                # is read-only, the computed twin of its quantities ratio (a plain "vec", like D)
                target_kind = "targetcell" if self.targets_editable else "vec"
                # the list is a matrix drawn WITH separator rules between its columns; an editable
                # input's opaque box, flush at the slot boundary, would paint over the thin rule. So
                # the editable cells are inset within their COL_W slot (like the interest kets, KET_INSET)
                # — leaving a gap the separator shows through — while the read-only Tₚ vecs stay full
                # COL_W (no covering box, so they abut their column separators). The draft column is
                # always the editable "targetcell" kind (a read-only Tₚ = I list has no draft).
                cell_inset = KET_INSET if self.targets_editable else 0
                self._emit_vec_grid(_VecGrid("targets", self.k, ids.target_cell, self.target_left,
                    cell_inset, target_kind, "targetcell", self.target_vectors, self.pending_target, self.target_sizes))
            if self.tile_open("vectors", "held"):  # the held intervals as editable vectors, like the intervals of interest
                self._emit_vec_grid(_VecGrid("held", self.nh, ids.held_cell, self.held_left,
                    0, "heldcell", "heldcell", self.held, self.pending_held, self.held_sizes))
            if self.tile_open("vectors", "detempering"):  # the matrix D, one vector column per generator
                for i in range(self.r):
                    for p in range(self.d):
                        self.cells.append(CellBox(f"cell:vec:detempering:{self.col_token('detempering', i)}:{p}", self.detempering_left(i), self.vec_top(p), COL_W, ROW_H, "vec", text=str(self.detempering_vectors[i][p]), unit=self.cell_unit("vectors", "detempering", prime=p)))
                        self._voice("vectors:detempering", i, self.detempering_sizes.just[i])
            if self.tile_open("vectors", "interest"):  # the user's intervals of interest: editable vectors, like the comma basis
                # inset within the COL_W slot (centred) so each ket is its own box with a
                # gap to its neighbours — the interest column is a collection, not a matrix
                self._emit_vec_grid(_VecGrid("interest", self.mi, ids.interest_cell, self.interest_left,
                    KET_INSET, "interestcell", "interestcell", self.interest, self.pending_interest, self.interest_sizes))
            # the drag-to-combine handles ride the band above the column labels (one per interval
            # entry): drag one interval onto another in the same column to ADD it in (their product).
            # Gated on the feature + ≥ 2 entries; targets only when the list is editable (not Tₚ = I).
            if "vectors" in self.rows and self.rows["vectors"].int_handle_top is not None:
                hy = self.rows["vectors"].int_handle_top
                for group, count, col_left, ckey in (("comma", self.nc, self.comma_left, "commas"),
                                                     ("target", self.k, self.target_left, "targets"),
                                                     ("held", self.nh, self.held_left, "held"),
                                                     ("interest", self.mi, self.interest_left, "interest")):
                    if count >= 2 and self.tile_open("vectors", ckey) and (ckey != "targets" or self.targets_editable):
                        for i in range(count):
                            self.cells.append(CellBox(f"int_drag:{group}:{i}", col_left(i), hy, COL_W, ROW_HANDLE_W, "int_drag", comma=i))

    def _emit_superspace_rows(self) -> None:
        """The chapter-9 superspace rows: spines, B_L, M_L, M_jL, the lifted lists and the P_L tiles."""
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
        # the superspace PROJECTION row's spine: the dL superspace primes label its prime-indexed
        # rows, like the superspace interval-vectors spine (ss_basis) above it and the on-domain
        # projection's domain-prime spine. (The mockup draws placeholder Greek letters α, β, γ …
        # here; they stand for these superspace primes.) Read-only, like proj_basis (the whole row
        # is derived). Centred COL_W squares, sharing the spine's x with ss_basis.
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "quantities"):
            bx = self.col_x["quantities"] + (self.col_w["quantities"] - COL_W) / 2  # square, centred in the spine
            for p in range(self.dL):
                self.cells.append(CellBox(f"ss_proj_basis:{p}", bx, self.ss_proj_top(p), COL_W, ROW_H, "prime",
                                          text=str(self.superspace_primes[p]), prime=p))
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
        # each entry's `draft` flag says whether an open draft column rides past its committed cells
        # (commas via comma_draft, the editable lists via their pending vector) — so the lifted
        # ss_vectors / ss_mapping rows green that column too, like every other derived row.
        ss_lists = (("commas", self.state.comma_basis, self.nc, self.comma_left, self.comma_draft),
                    ("targets", self.target_vectors, self.k, self.target_left, self.pending_target is not None),
                    ("held", self.held, self.nh, self.held_left, self.pending_held is not None),
                    ("interest", self.interest, self.mi, self.interest_left, self.pending_interest is not None),
                    ("detempering", self.detempering_vectors, self.r, self.detempering_left, False))
        for ckey, vectors, n, left, draft in ss_lists:
            cols = tuple(vectors)[:n]
            if self.row_open("ss_vectors") and self.tile_open("ss_vectors", ckey):
                lifted = service.lift_vectors_to_superspace(self.elements, cols)
                for c in range(len(lifted)):
                    for p in range(self.dL):
                        self.cells.append(CellBox(
                            f"cell:ss_vectors:{ckey}:{p}:{c}", left(c), self.ss_vec_top(p),
                            COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                            unit=self.cell_unit("ss_vectors", ckey, prime=p)))
                if draft:  # the open draft column: one blank green slot per superspace prime
                    for p in range(self.dL):
                        self.cells.append(CellBox(f"cell:ss_vectors:{ckey}:{p}:draft", left(n), self.ss_vec_top(p),
                                             COL_W, ROW_H, "vec", text="", prime=p, pending=True))
                if ckey == "commas":  # consolidated V = C|U: the unchanged half, lifted (B_L·𝐮)
                    for j in range(self.nu):
                        uj = self.ss_unchanged[j]
                        for p in range(self.dL):
                            self.cells.append(CellBox(
                                f"cell:ss_vectors:commas:{p}:u{j}", self.comma_left(self.nc_shown + j), self.ss_vec_top(p),
                                COL_W, ROW_H, "vec", text=DASH if uj is None else str(uj[p]), prime=p, comma=self.nc + j,
                                unit=self.cell_unit("ss_vectors", "commas", prime=p)))
            if self.row_open("ss_mapping") and self.tile_open("ss_mapping", ckey):
                mapped = service.map_vectors_into_superspace_generators(self.state, cols)
                for c in range(len(mapped)):
                    for g in range(self.rL):
                        self.cells.append(CellBox(
                            f"cell:ss_mapping:{ckey}:{g}:{c}", left(c), self.ss_map_top(g),
                            COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                            unit=self.cell_unit("ss_mapping", ckey, gen=g)))
                if draft:  # the open draft column: one blank green slot per superspace generator
                    for g in range(self.rL):
                        self.cells.append(CellBox(f"cell:ss_mapping:{ckey}:{g}:draft", left(n), self.ss_map_top(g),
                                             COL_W, ROW_H, "mapped", text="", gen=g, pending=True))
                if ckey == "commas":  # consolidated V = C|U: the unchanged half mapped into ss generators (M_s→L·𝐮)
                    for j in range(self.nu):
                        uj = self.ss_unchanged_mapped[j]
                        for g in range(self.rL):
                            self.cells.append(CellBox(
                                f"cell:ss_mapping:commas:{g}:u{j}", self.comma_left(self.nc_shown + j), self.ss_map_top(g),
                                COL_W, ROW_H, "mapped", text=DASH if uj is None else str(uj[g]), gen=g, comma=self.nc + j,
                                unit=self.cell_unit("ss_mapping", "commas", gen=g)))
        # P_L = G_L M_L (superspace projection): the dL × dL rational projection the tuning lifts to
        # over its superspace primes. Sits in (ss_projection, ssprimes), each row a covector over the
        # dL ss_primes — read-only "mapped" cells like M_L (P_L is DERIVED, edited only via the on-
        # domain held basis). TOTALLY DASHED (every cell an em-dash) when self.ss_projection_matrix is
        # None — the tuning isn't a full rational projection — in lockstep with the on-domain P.
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            full = self.ss_projection_matrix is not None
            for i in range(self.dL):
                for j in range(self.dL):
                    text = DASH if not full else self.ss_projection_matrix[i][j]
                    self.cells.append(CellBox(
                        f"cell:ss_projection:ssprimes:{i}:{j}",
                        self.ss_prime_left(j), self.ss_proj_top(i), COL_W, ROW_H,
                        "mapped", text=text, gen=i, prime=j,
                        unit=self.cell_unit("ss_projection", "ssprimes", gen=i, prime=j),
                    ))
        # the rest of the superspace projection row — P_L applied to each column's vectors (lifted into
        # the superspace), the chapter-9 analogues of the embedding G and P·D / P·V / P·T / P·H / P·interest.
        # All dL-tall over ss_proj_top, read-only "mapped" cells, DASHED in lockstep with P_L (when
        # ss_projection_rationals is None) exactly like the on-domain projected lists.
        ss_full = self.ss_projection_rationals is not None
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssgens"):  # G_L = the embedding
            for i in range(self.dL):
                for g in range(self.rL):
                    text = DASH if not ss_full else self.ss_embedding_matrix[i][g]
                    self.cells.append(CellBox(f"cell:ss_embed:{i}:{g}", self.ss_gen_left(g), self.ss_proj_top(i),
                                         COL_W, ROW_H, "mapped", text=text, gen=g))
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "primes"):  # P_L·B_Ls
            for e in range(self.d):
                for p in range(self.dL):
                    text = DASH if not ss_full else str(self.ss_proj_basis[e][p])
                    self.cells.append(CellBox(f"cell:ss_proj_bls:{e}:{p}", self.prime_left(e), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text=text, prime=p, comma=e))
        # the interval-list columns of P_L (D_L / T_L / H_L / interest) reuse the same _emit_mapped_grid
        # as the on-domain projection band, retargeted to the ss_projection row (top=ss_proj_top, dL-tall)
        # — so each draftable list (T/H/interest) greens its draft column automatically, no per-list branch.
        _ssp = dict(full=ss_full, colwise=True, row="ss_projection", top=self.ss_proj_top, height=self.dL)
        self._emit_mapped_grid("detempering", "ss_proj_pd", self.ss_proj_detempering, self.r, self.detempering_left, "gen", **_ssp)  # P_L·D_L
        if self.show_unchanged and self.row_open("ss_projection") and self.tile_open("ss_projection", "commas"):  # P_L·V
            for c in range(self.nc):  # P_L·comma = the zero vector (the comma half of V vanishes)
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{c}", self.comma_left(c), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            if self.pending is not None:  # blank green placeholder column under the draft comma
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:draft", self.comma_left(self.nc), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped", text="", prime=p, pending=True))
            for j in range(self.nu):  # P_L·unchanged = the unchanged interval itself, lifted (dashed if U is)
                dashed = self.ss_unchanged[j] is None
                for p in range(self.dL):
                    self.cells.append(CellBox(f"cell:ss_proj_v:{p}:{self.nc + j}", self.comma_left(self.nc_shown + j), self.ss_proj_top(p),
                                         COL_W, ROW_H, "mapped",
                                         text=DASH if dashed else str(self.ss_unchanged[j][p]), prime=p, comma=self.nc + j))
        self._emit_mapped_grid("targets", "ss_proj_pt", self.ss_proj_targets, self.k, self.target_left, "comma",
                               pending=self.pending_target, **_ssp)  # P_L·T_L
        self._emit_mapped_grid("held", "ss_proj_ph", self.ss_proj_held, self.nh, self.held_left, "comma",
                               pending=self.pending_held, **_ssp)  # P_L·H_L
        self._emit_mapped_grid("interest", "ss_proj_pi", self.ss_proj_interest, self.mi, self.interest_left, "comma",
                               inset=KET_INSET, pending=self.pending_interest, **_ssp)  # P_L·interest

    def _emit_identity_objects(self) -> None:
        """The standard-domain identity objects — the trivial self-maps that equal 𝐼, each gated on
        the identity_objects toggle (tile_open consults declared_tiles, from which the gate drops
        them when the toggle is off). The on-domain twins of the superspace M_jL / M_LgL, built the
        same way (read-only "mapped" cells + per-row brackets + a spanning matrix_frame):
          • 𝑀ⱼ = 𝐼  (vectors × primes): the JI mapping, a d × d covector stack of the domain primes
            over themselves — one ⟨ … ] per prime (rows labelled 𝒎ⱼᵢ in the primes gutter).
          • 𝑀𝐺 = 𝐼  (mapping × gens): the r × r mapping over its own generators, a { … ] genmap stack.
          • 𝑀D = 𝐼  (mapping × detempering): the SAME r × r identity = M·D, over the detempering
            column (its columns headed 𝑀𝐝ᵢ). Rides the detempering toggle as well, via col_open."""
        # M_j = I — d × d identity over the primes column, framed like the mapping it parallels
        if self.tile_open("vectors", "primes"):
            for i in range(self.d):
                for k in range(self.d):
                    self.cells.append(CellBox(
                        f"cell:vec:primes:{i}:{k}", self.prime_left(k), self.vec_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i, prime=k,
                        unit=self.cell_unit("vectors", "primes", prime=k)))
        # 𝑀𝐺 = I (gens) and 𝑀D = I (detempering): the same r × r identity M·D, in generator coords
        for ckey, prefix, left in (("gens", "selfmap", self.gen_left),
                                   ("detempering", "mapped_detempering", self.detempering_left)):
            if self.tile_open("mapping", ckey):
                for i in range(self.r):
                    for k in range(self.r):
                        self.cells.append(CellBox(
                            f"cell:{prefix}:{i}:{k}", left(k), self.map_top(i), COL_W, ROW_H,
                            "mapped", text="1" if i == k else "0", gen=i,
                            unit=self.cell_unit("mapping", ckey, gen=i)))
        # 𝐹⁻¹𝐹 = 𝐼 (canon × canongens): the rc × rc identity in canonical-generator coords, the form
        # box's own self-map — F composed with its inverse cancels. Framed { … ] like 𝑀𝐺, in the
        # canonical-generators column (g_C/g_C). Gated on identity_objects (declared_tiles), the
        # canonical-generators column (show_canon) gating it further.
        if self.tile_open("canon", "canongens"):
            for i in range(self.rc):
                for k in range(self.rc):
                    self.cells.append(CellBox(
                        f"cell:fcancel:{i}:{k}", self.canongen_left(k), self.canon_top(i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i,
                        unit=self.cell_unit("canon", "canongens", gen=i)))

    def _emit_tuning_rows(self):
        """The tuning/just/retune rows; returns the chart_indicators dict the chart pass reads."""
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
        # the comma sizes then the unchanged interval sizes (the empty unchanged tuples no-op off
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
                self.tuning_value_row(key, "held", held_vals)
        # the generator tuning map: the tuning row's map over the generators (the gens-column
        # counterpart of the tuning map over the primes). Its cells are EDITABLE (a hybrid input):
        # typing a cents value overrides that generator's tuning, like typing the whole map in the
        # plain text. The genmap has no closed form, so they are plain editable cells (never mathexpr).
        # Under the prime-based superspace shift, though, the optimization lives over 𝒈L, so 𝒈 is the
        # read-only PROJECTION of the editable 𝒈L (ssgens, below) — its cells go plain tuning value.
        if self.row_open("tuning") and self.tile_open("tuning", "gens"):
            gen_kind = "tuningvalue" if self.show_superspace_generators else "gentuningcell"
            for i, v in enumerate(self.tun.generator_map):
                self.cells.append(CellBox(f"tuning:gen:{self.col_token('gens', i)}", self.group_left["gens"](i), self.rows["tuning"].y, COL_W, ROW_H,
                                     gen_kind, text=service.cents(v, self._decimals), gen=i, unit=self.cell_unit("tuning", "gens", gen=i)))
                self._voice("tuning:gens", i, v)  # the genmap sounds each generator's tuned size
        # the chapter-9 superspace tuning row: 𝒈ₗ over the ssgens column, 𝒕ₗ / 𝒋ₗ / 𝒓ₗ over ssprimes.
        # In the prime-based approach the optimization IS over the superspace generators, so 𝒈L is the
        # EDITABLE generator map (gentuningcell, the editing 𝒈 gave up above) — a manual 𝒈L freezes
        # via service.superspace_tuning's generator_override and projects down to drive 𝒈 and every
        # on-domain map. In neutral the superspace is only a complexity lens, so 𝒈L stays read-only.
        if self.show_superspace and self.row_open("tuning"):
            ss_tun = self.superspace_tun()  # memoized: shared with the plain-text bundle's solve
            if self.tile_open("tuning", "ssgens"):
                if self.show_superspace_generators:  # editable 𝒈L cells (the prime-based live map)
                    for i, v in enumerate(ss_tun.generator_map):
                        self.cells.append(CellBox(f"tuning:ssgen:{i}", self.group_left["ssgens"](i), self.rows["tuning"].y,
                                             COL_W, ROW_H, "gentuningcell", text=service.cents(v, self._decimals),
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
        return chart_indicators

    def _emit_prescaling_band(self) -> None:
        """The prescaling row: the prescaler applied to each column group's vectors."""
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
            # None-preserving lift: a DASHED unchanged column (V = C|U over a nonstandard domain)
            # has no vector to lift, so it stays None (the prescaling loop dashes it out below)
            _lift = lambda vs: tuple(None if v is None else service.lift_vectors_to_superspace(self.elements, (v,))[0]
                                     for v in vs)
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
                u = self.cell_unit("prescaling", group, prime=c if group == bare_group else None)
                if vec is None:  # a DASHED unchanged column of V = C|U — its prescaled vector 𝐿·v is unknown
                    for i in range(nrows + self.size_rows):
                        cid = f"cell:prescaling:{group}:{i}:{self.col_token(group, c)}"
                        cx, cy = left(self.comma_value_pos(c) if group == "commas" else c), self.rows["prescaling"].y + i * ROW_H
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue", text=DASH, unit=u))
                    continue
                # the bare prescaler's columns ARE the (super)space primes, so each column's unit
                # subscripts its p by that prime (oct/pᵢ) — like the mapping's /p denominator. The
                # other groups (incl. 𝐿·B_Ls) scale a vector set, plain octaves (no per-column p).
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
                    cx, cy = left(self.comma_value_pos(c) if group == "commas" else c), self.rows["prescaling"].y + i * ROW_H
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
                                             text=service.prescale_text(value, self._decimals), prime=i, unit=u))
                    elif i < nrows and self.show_math and vec[i] != 0 and i in prime_term:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "mathexpr",
                                             text=_prescale_math_expr(vec[i], prime_term[i], value, self.show_quantities, self._decimals), unit=u))
                    else:
                        self.cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue",
                                             text=service.prescale_text(value, self._decimals), unit=u))
            # a pending comma/target/held/interest draft also gets a blank GREEN placeholder column,
            # stacked over every prescaled sub-row, so the draft reads green through the advanced
            # complexity-prescaling matrix too — the multi-row twin of tuning_value_row's single-row
            # placeholder (lines ~2147). The enclosing bracket already spans the draft (content_w is
            # _shown-wide), so only the cells are needed. left() is this group's group_left.
            pending_idx = self._pending_draft_idx(group)
            if pending_idx is not None and pending_idx[0] is not None:
                # a real draft's prescaled column is unknown (blank); the mapping − hover's born comma
                # has a known vector, so its 𝐿·comma fills the placeholder (lifted into the superspace
                # first when shown), the same per-row product the committed comma columns use above.
                ghost_pre = None
                if self.ghost_comma and group == "commas" and self.ghost_comma_vec is not None:
                    gvec = _lift((self.ghost_comma_vec,))[0] if self.show_superspace else self.ghost_comma_vec
                    ghost_pre = ([sum(prescaler_diag[i][k] * gvec[k] for k in range(nrows)) for i in range(nrows)]
                                 if prescaler_is_matrix else [prescaler_diag[i] * gvec[i] for i in range(nrows)])
                for i in range(nrows + self.size_rows):
                    cy = self.rows["prescaling"].y + i * ROW_H
                    text = ""
                    if ghost_pre is not None:
                        value = ghost_pre[i] if i < nrows else self.size_factor * sum(ghost_pre)
                        text = service.prescale_text(value, self._decimals)
                    self.cells.append(CellBox(f"cell:prescaling:{group}:{i}:draft", left(pending_idx[1]),
                                         cy, COL_W, ROW_H, "tuningvalue", text=text, pending=True))

    def _emit_lbox_control(self) -> None:
        """Box 𝐋's lone alt.-complexity control: the replace-diminuator checkbox."""
        if self.lbox_ctrl:  # box 𝐋's lone alt.-complexity control: the "replace diminuator" checkbox,
            # in a bordered box at the bottom of the prescaling matrix (the prescaler chooser is a preset
            # now, riding the preset band above). A SQUARE (no inline label — it wraps broken in the narrow
            # primes column) over its "replace diminuator" caption hugging its bottom.
            box_top = self.rows["prescaling"].tile_top + self.rows["prescaling"].tile_h - self.lbox_extra + RANGE_GAP
            bx, by = self.control_region("block:diminuator", "ssprimes" if self.show_superspace else "primes",
                                         box_top, OPTION_BOX_PX + CAPTION_LINE)
            self.cells.append(CellBox("control:diminuator", bx, by, LBOX_DIM_W, OPTION_BOX_PX,
                                 "control_check", text="",  # square only; label moves to a caption below
                                 checked=service.diminuator_replaced(self.tuning_scheme)))
            self.cells.append(CellBox("caption:diminuator", bx, by + OPTION_BOX_PX, LBOX_DIM_W,
                                 CAPTION_LINE, "caption", text="replace diminuator"))

    def _emit_cbox_controls(self) -> None:
        """Box 𝒄's controls: the predefined-complexities dropdown, q and dual(q)."""
        if self.cbox_ctrl:  # box 𝒄's three controls sit on one row in a bordered box at the bottom of the
            # complexity list: [predefined complexities ▼] | q | dual(q). The dropdown's caption hugs its
            # bottom; q and dual(q) use the optimization box's value-over-symbol-over-caption stack — the
            # value cell stays at COL_W (a standard gridded number), but the symbol/caption sit in
            # a wider overhanging SLOT so "dual(q)" doesn't overflow and multi-word captions wrap
            # readable. dual(q) only appears in all-interval mode (the dual norm power is
            # meaningful via the dual-norm inequality used to minimax over every interval).
            box_top = self.rows["complexity"].tile_top + self.rows["complexity"].tile_h - self.cbox_extra + RANGE_GAP
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

    def _emit_complexity_row(self) -> None:
        """The complexity row: 𝒄 over every interval set."""
        if self.row_open("complexity"):  # 𝒄 over every interval set: a map over primes, lists elsewhere
            for group in ("primes", "commas", "targets", "interest", "held", "detempering"):
                # the comma list runs over V = C|U when projection is on (the unchanged intervals'
                # complexities append to the commas'); the empty tuple no-ops off projection
                values = self.complexities[group] + (self.unchanged_complexities if group == "commas" else ())
                self.tuning_value_row("complexity", group, values)
            # the superspace shift's "next row": the prime complexity map moves into the ss-primes
            # column (‖𝐿[i]‖q = each true prime's own diagonal weight), while the domain-primes tile
            # above keeps self.complexities["primes"] — now the SUBSPACE basis element complexity map
            # (each domain element's complexity, prime-factored through B_L, per the corrected
            # get_complexity). The two captions are swapped in _resolve_prescaler_labels.
            if self.show_superspace and self.tile_open("complexity", "ssprimes"):
                self.tuning_value_row("complexity", "ssprimes",
                              service.superspace_complexity_prescaler(self.state, self.tuning_scheme))

    def _emit_weight_row(self) -> None:
        """The weight row and box 𝒘's weight-slope chooser."""
        if self.row_open("weight") and self.tile_open("weight", "targets"):
            # the weight is always a per-target list (it scales the targets, like damage). The all-
            # interval simplicity weight that has no concrete diagonal form (the size factor / a non-
            # diagonal 𝑋) still renders as this list — it just shows the generic 𝒘 = 𝒄⁻¹ symbol and per-
            # column cₙ⁻¹ headers instead of the concrete diag(𝐿)⁻¹ equivalence, never a matrix.
            # In custom-weight mode (target-based, plain-value view) the cells become editable inputs —
            # the user's typed weights override the slope; all-interval keeps the read-only prime-proxy
            # list (no per-target weights there) and the math-expr view stays read-only.
            self.tuning_value_row("weight", "targets", self.target_weights,
                                  editable_kind="weightcell" if self.custom_weights_active else None)
        if self.slope_ctrl:  # box 𝒘's weight-slope chooser (U/S/C), in a bordered box at the bottom of the
            # weight list, with its "damage weight slope" caption beneath (the optimization box's caption pattern)
            box_top = self.rows["weight"].tile_top + self.rows["weight"].tile_h - self.slope_extra + RANGE_GAP
            bx, by = self.control_region("block:slope", "targets", box_top, PRESET_H + CAPTION_LINE)
            slope_w = self.col_w["targets"] - 2 * BOX_INNER  # the chooser fills the box, inset off its border
            self.cells.append(CellBox("control:slope", bx, by, slope_w, PRESET_H,
                                 "control_select", text=service.weight_slope_of(self.tuning_scheme),
                                 values=tuple(service.WEIGHT_SLOPES), disabled=self.slope_locked))
            self.cells.append(CellBox("caption:slope", bx, by + PRESET_H,
                                 slope_w, CAPTION_LINE, "caption",
                                 text="damage weight slope", align="left", disabled=self.slope_locked))

    def _emit_damage_row(self, chart_indicators) -> None:
        """The damage row; records the minimized-damage chart indicator."""
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

    def _emit_charts(self, chart_indicators) -> None:
        """Draw a bar chart over every tile a charted row recorded."""
        # Draw a bar chart over every tile a charted row recorded (see chart_tiles above):
        # one pass, so the set of charts always equals the set of charted-row value tiles.
        for rkey, ckey, values in self.chart_tiles:
            indicator, label = chart_indicators.get((rkey, ckey), (None, ""))
            self.chart(rkey, ckey, values, indicator=indicator, indicator_label=label)

    def _emit_tuning_ranges_box(self):
        """The generator tuning-ranges chart box; returns its frame rect (gtm_box)."""
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
            cy = self.rows["tuning"].tile_top + self.rows["tuning"].tile_h - self.gtm_extra + RANGE_GAP
            self.cells.append(CellBox("rangetitle:tuning:gens", gx, cy + BOX_INNER, gw, BOX_TITLE_H, "boxtitle",
                                 text="tuning ranges", align="left"))
            chart_y = cy + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.cells.append(CellBox("rangechart:tuning:gens", gx, chart_y, gw, RANGE_CHART_H, "rangechart",
                                 ranges=tuple(chosen) if chosen is not None else (),
                                 values=tuple(self.tun.generator_map),  # the live tuning, marked within each range
                                 decimals=self._decimals))  # off → the I-beam's cents labels round to integers
            self.cells.append(CellBox("rangemode:tuning:gens", gx, chart_y + RANGE_CHART_H + RANGE_GAP, gw, RANGE_MODE_H,
                                 "rangemode", text=self.range_mode))
            gtm_box = (gx, cy, gw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + RANGE_CHART_H + RANGE_GAP + RANGE_MODE_H)
        return gtm_box

    def _emit_optimization_box(self):
        """The optimization box at the bottom of the damage tile; returns its frame rect (opt_box)."""
        # the optimization box, nested at the BOTTOM of the target interval damage list tile (the
        # tuning's own column, whose damages it minimizes): a bordered box titled "optimization",
        # spanning the FULL width of the tile (like the tuning-ranges box) and DISTRIBUTING two
        # controls across it — the minimized-damage mean damage (a read-only gridded value over ⟪𝐝⟫ₚ)
        # hugging the left, and the editable power (the ∞ cell over 𝑝 over "optimization power")
        # centered in the gap to its right, so its caption has clear room either side. The min-damage
        # and ∞ are plain COL_W gridded cells (contents centred). The damage tile's panel grows by
        # opt_extra to enclose the box's height, and the targets column is floored to OPT_BOX_MIN_W
        # (see _control_floor) so the spread-out controls always fit.
        opt_box = None  # (x, y, w, h) of the bordered frame around the optimization controls
        if self.opt_ctrl:
            ox = self.col_x["targets"]
            box_w = self.col_w["targets"]                 # the box spans the full width of the damage tile
            # the opt box sits at the very bottom of the tile (the approach box rides above it)
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra + RANGE_GAP)
            title_top = box_top + OPT_PAD_T          # inset below the box's top border (not on it)
            content_top = title_top + OPT_TITLE_H + OPT_TITLE_GAP  # a gap below the title
            sym_top = content_top + ROW_H            # the symbol/hint row, under the values
            cap_top = sym_top + SYMBOL_H             # the caption row, under the symbols
            cap_band = self.opt_cap_lines * CAPTION_LINE  # one line, or two when the wide mean damage wraps
            body_h = ROW_H + SYMBOL_H + cap_band + OPT_PAD_B  # value + symbol + caption band + pad
            # the two controls, distributed across the box: the mean damage column at the left, the
            # power centered in the gap to its right (so its caption clears both the mean damage and
            # the box's right edge). The mean damage's value/symbol/caption all centre on the column's
            # mid-line, so a wide symbol/caption overflows evenly and stays within the box.
            mean_damage_x = ox + OPT_PAD_L                       # the mean damage column's left edge
            mean_damage_val_x = mean_damage_x + (OPT_MEAN_DAMAGE_W - COL_W) / 2  # the COL_W value cell, centred in the column
            pow_x = ((mean_damage_x + OPT_MEAN_DAMAGE_W) + (ox + box_w - OPT_PAD_R)) / 2 - COL_W / 2
            # the mean damage aggregates the damages at the power the optimizer MINIMIZED at — 𝑝 target-
            # based, dual(𝑞) all-interval (the ⟪𝒓𝑋⁻¹⟫ symbol's dual(𝑞) subscript). The 𝑝 cell below
            # keeps displayed_optimization_power() (∞ all-interval): power over intervals vs over primes.
            mean_damage = _power_mean(self.target_sizes.damage, self.displayed_mean_damage_power())
            power = _format_power(self.displayed_optimization_power())
            self.cells.append(CellBox("optimization:title", ox, title_top, box_w, OPT_TITLE_H, "boxtitle",
                                 text="optimization"))
            # the mean damage: the minimized-damage value (read-only, so unboxed — a plain centred gridded
            # value, the same COL_W cell as any damage value) over its symbol and a label caption, the
            # same value/symbol/caption stack as the power beside it.
            self.cells.append(CellBox("optimization:mean_damage", mean_damage_val_x, content_top, COL_W, ROW_H, "tuningvalue",
                                 text=service.cents(mean_damage, self._decimals)))
            # all-interval: the minimized mean damage is the all-interval retuning magnitude (the
            # mockup's "becomes 'retuning magnitude'", named by the caption below). The VALUE is the
            # dual-power MEAN of the retuning map 𝒓𝑋⁻¹'s per-prime damages — the same _power_mean (÷d
            # inside the root) the value cell above and the damage chart's ⟪𝐝⟫ indicator both draw.
            # So the symbol must be the double-angle power-MEAN ⟪…⟫ over 𝒓𝑋⁻¹ at dual(q) — NOT the
            # single-bar NORM ‖…‖, which omits the /d and so reads √d too large (it would contradict
            # both the value and the chart line; the mockup itself DRAWS this value with ⟪…⟫). The
            # prescaler inverse carries the live glyph (𝐿⁻¹ for the log-prime matrix, else generic 𝑋⁻¹).
            mean_damage_symbol = (f"⟪𝒓{self.prescaler_symbol}⁻¹⟫{SUB_OPEN}dual(𝑞){SUB_CLOSE}"
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
            opt_box = (ox, box_top, box_w, OPT_PAD_T + OPT_TITLE_H + OPT_TITLE_GAP + body_h)
        return opt_box

    def _emit_approach_box(self):
        """The chapter-9 approach box above the optimization box; returns its frame rect (approach_frame)."""
        approach_frame = None  # (x, y, w, h) of the bordered frame around the approach box
        self.approach_box = None  # (x, y, w, h) the approach radio is positioned over (None ⇒ hidden)
        # the chapter-9 approach box: a bordered control box (the tuning-ranges / optimization style)
        # titled "nonstandard domain approach", framing the prime-based/nonprime-based/neutral square
        # radio. It rides the reserved approach_extra slice ABOVE the optimization box, spanning the
        # tile's full width like its siblings. A left-aligned boxtitle tops it (like every control
        # box); the radio itself is an interactive widget app.py owns, so here we emit the title and
        # publish approach_box (its target x/y/w/h) for render() to position the square radio over.
        if self.show_approach:
            ax = self.col_x["targets"]
            aw = self.col_w["targets"]
            box_top = (self.rows["damage"].tile_top + self.rows["damage"].tile_h
                       - self.opt_extra - self.approach_extra + RANGE_GAP)
            self.cells.append(CellBox("optimization:approach:title", ax, box_top + BOX_INNER, aw, BOX_TITLE_H, "boxtitle",
                                 text="nonstandard domain approach", align="left"))
            radio_top = box_top + BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP
            self.approach_box = (ax + OPT_PAD_L, radio_top,
                                 aw - OPT_PAD_L - OPT_PAD_R, APPROACH_RADIO_H)
            approach_frame = (ax, box_top, aw, 2 * BOX_INNER + BOX_TITLE_H + BOX_TITLE_GAP + APPROACH_RADIO_H)
        return approach_frame

    def _emit_brackets(self) -> None:
        """The per-row / per-list EBK brackets across all the bands."""
        if self.row_open("canon") and self.tile_open("canon", "primes"):  # canonical maps: ⟨ … ] per row
            for i in range(self.rc):
                self.bracket(f"canon:map:{i}", MAP_BRACKETS, "primes", self.canon_top(i), ROW_H, stacked=True)
                self.bracket(f"form:map:{i}", GENMAP_BRACKETS, "gens", self.canon_top(i), ROW_H, stacked=True)
        if self.row_open("canon") and self.tile_open("canon", "canongens"):  # 𝐹⁻¹𝐹 = 𝐼: { … ] per row, like 𝑀𝐺
            for i in range(self.rc):
                self.bracket(f"fcancel:map:{i}", GENMAP_BRACKETS, "canongens", self.canon_top(i), ROW_H, stacked=True)
        # the canonical-mapping row's mapped lists, framed like their mapping-row twins (a single OUTER
        # wrap + per-column ket marks from vector_list_marks below): 𝑀_C·D = 𝐹 a vector list { … ]
        # (generator coords, like P·D = G); 𝑀_C·C / Y_C / 𝑀_C·H a [ … ] over the rc rows; 𝑀_C·interest
        # stands alone (no outer wrap), mirroring the mapping row's interest.
        if self.row_open("canon"):
            canon_y, canon_h = (self.rows["canon"].y if "canon" in self.rows else 0), self.rc * ROW_H
            if self.tile_open("canon", "detempering"):
                self.bracket("canon_detempering", GENMAP_BRACKETS, "detempering", canon_y, canon_h, fit=True)
            if self.tile_open("canon", "commas"):
                self.bracket("canon_comma", LIST_BRACKETS, "commas", canon_y, canon_h, fit=True)
            if self.tile_open("canon", "targets"):
                self.bracket("canon_mapped", LIST_BRACKETS, "targets", canon_y, canon_h, fit=True)
            if self.nh and self.tile_open("canon", "held"):
                self.bracket("canon_hmapped", LIST_BRACKETS, "held", canon_y, canon_h, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "primes"):  # P = GM: ⟨ … ] per row, like the mapping
            for i in range(self.d):
                self.bracket(f"proj:{i}", MAP_BRACKETS, "primes", self.proj_top(i), ROW_H, stacked=True)
        if self.row_open("projection") and self.tile_open("projection", "gens"):
            # G is a vector LIST: each held generator a prime-count ket [ … ⟩ column (marks emitted by
            # vector_list_marks below) inside an outer { … ] (curly open, square close, generator
            # coords) — matching its plain text {[…⟩…], NOT a covector stack
            self.bracket("embed", GENMAP_BRACKETS, "gens", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "ssgens"):
            # G_L→s is a vector LIST like G — outer { … ] over the superspace-generator columns
            self.bracket("embed_sl", GENMAP_BRACKETS, "ssgens", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "ssprimes"):
            # P_L→s is a covector stack like P: ⟨ … ] per row over the superspace primes
            for i in range(self.d):
                self.bracket(f"proj_sl:{i}", MAP_BRACKETS, "ssprimes", self.proj_top(i), ROW_H, stacked=True)
        if self.show_unchanged and self.row_open("projection") and self.tile_open("projection", "commas"):
            # P·V is a list of projected vectors (kets) — [ … ⟩ per column, [ ] outer, like V itself
            self.bracket("proj_v", LIST_BRACKETS, "commas", self.rows["projection"].y, self.d * ROW_H, fit=True)
        # the projected vector lists' outer brackets (their per-column ket marks come from
        # vector_list_marks below): P·D = the embedding G takes the curly { … ] (generator-coordinate
        # columns, like G), P·T and P·H the plain [ … ] of the lists they project. P·interest stands
        # alone (no outer wrap), like the interest column it projects.
        if self.row_open("projection") and self.tile_open("projection", "detempering"):
            self.bracket("proj_pd", GENMAP_BRACKETS, "detempering", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "targets"):
            self.bracket("proj_pt", LIST_BRACKETS, "targets", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("projection") and self.tile_open("projection", "held"):
            self.bracket("proj_ph", LIST_BRACKETS, "held", self.rows["projection"].y, self.d * ROW_H, fit=True)
        if self.row_open("scaling_factors") and self.tile_open("scaling_factors", "commas"):  # λ: a [ … ] list over V
            self.bracket("scaling", LIST_BRACKETS, "commas", self.rows["scaling_factors"].y, ROW_H)
        if self.row_open("mapping"):
            # the primes mapping is a stack of maps: ⟨ … ] per row
            if self.tile_open("mapping", "primes"):
                for i in range(self.r):
                    self.bracket(f"map:{i}", MAP_BRACKETS, "primes", self.map_top(i), ROW_H, stacked=True)
                if self.pending_mapping_row is not None:  # the draft row's own ⟨ … ] map brackets, green
                    self.bracket("map:pending", MAP_BRACKETS, "primes", self.map_top(self.r), ROW_H, pending=True, stacked=True)
            # the spanning derived [ ]s grow to r_shown — enclosing the (empty) draft-row slot at the
            # band floor, exactly as the comma-draft's mapped_comma [ ] grows over nc_shown to enclose
            # its empty draft-column slot. r_shown == r whenever no row is pending, so the resting
            # render is unchanged.
            if self.tile_open("mapping", "commas"):  # the mapped (vanishing) comma basis: a [ ] over the rows
                self.bracket("mapped_comma", LIST_BRACKETS, "commas", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)
            if self.tile_open("mapping", "targets"):
                self.bracket("mapped", LIST_BRACKETS, "targets", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)
            # the interest mapped images stand alone (no outer [ … ]), mirroring the vectors row
            if self.nh and self.tile_open("mapping", "held"):  # held mapped list, like the targets / interest
                self.bracket("hmapped", LIST_BRACKETS, "held", self.rows["mapping"].y, self.r_shown * ROW_H, fit=True)
        # the chapter-9 superspace mapping M_L: a rL × dL covector stack over the ssprimes
        # column, framed exactly like M (per-row ⟨ … ] brackets + top/bottom matrix_frame)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssprimes"):
            for i in range(self.rL):
                self.bracket(f"ss_map:{i}", MAP_BRACKETS, "ssprimes", self.ss_map_top(i), ROW_H, stacked=True)
        # P_L: a dL × dL covector stack over the ssprimes column, per-row ⟨ … ] like M_L / M_jL
        if self.row_open("ss_projection") and self.tile_open("ss_projection", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_proj:{i}", MAP_BRACKETS, "ssprimes", self.ss_proj_top(i), ROW_H, stacked=True)
        # the rest of the superspace projection row's OUTER brackets (their inner per-column kets come
        # from vector_list_marks below), mirroring the on-domain G / P·D / P·V / P·T / P·H / P·interest:
        # the embedding G_L and P_L·D_L take the curly { … ] (generator coords); P_L·B_Ls the covector-
        # style ⟨ … ] (like B_L); P_L·C_L / P_L·T_L / P_L·H_L the plain [ … ]; P_L·interest stands alone.
        ssp_top, ssp_h = (self.rows["ss_projection"].y if "ss_projection" in self.rows else 0), self.dL * ROW_H
        if self.row_open("ss_projection"):
            if self.tile_open("ss_projection", "ssgens"):
                self.bracket("ss_embed", GENMAP_BRACKETS, "ssgens", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "primes"):
                self.bracket("ss_proj_bls", MAP_BRACKETS, "primes", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "detempering"):
                self.bracket("ss_proj_pd", GENMAP_BRACKETS, "detempering", ssp_top, ssp_h, fit=True)
            if self.show_unchanged and self.tile_open("ss_projection", "commas"):  # P_L·V over the V = C|U column
                self.bracket("ss_proj_v", LIST_BRACKETS, "commas", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "targets"):
                self.bracket("ss_proj_pt", LIST_BRACKETS, "targets", ssp_top, ssp_h, fit=True)
            if self.tile_open("ss_projection", "held"):
                self.bracket("ss_proj_ph", LIST_BRACKETS, "held", ssp_top, ssp_h, fit=True)
        # the chapter-9 "new × new" tiles. M_jL = I at (ss_vectors, ssprimes): a dL × dL covector
        # stack ⟨ … ] like M_L. M_s→L at (ss_mapping, primes): rL covectors over the domain
        # elements. M_LgL = I at (ss_mapping, ssgens): the gen-space self-map, framed { … ] (the
        # generator dimension, like the canonical generator form F and the genmap).
        if self.row_open("ss_vectors") and self.tile_open("ss_vectors", "ssprimes"):
            for i in range(self.dL):
                self.bracket(f"ss_vec_jmap:{i}", MAP_BRACKETS, "ssprimes", self.ss_vec_top(i), ROW_H, stacked=True)
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "primes"):
            for i in range(self.rL):
                self.bracket(f"ss_msl:{i}", MAP_BRACKETS, "primes", self.ss_map_top(i), ROW_H, stacked=True)
        # M_LGL = I at (ss_mapping, ssgens): a COLUMN-first vector list — each superspace generator a
        # ket [ … } in generator coords, wrapped in an outer { … ]. Per-column marks come from
        # vector_list_marks below; here just the outer { … ] wrap (NOT a per-row covector stack).
        if self.row_open("ss_mapping") and self.tile_open("ss_mapping", "ssgens"):
            self.bracket("ss_selfmap", GENMAP_BRACKETS, "ssgens",
                         self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
        # the standard-domain identity objects (the on-domain twins of the two above). M_j = I is a
        # d × d covector stack ⟨ … ] over the primes column (per-row brackets + matrix_frame, like M
        # — but closing with the angle ⟩ since it's the p/p JI mapping, an operator like P). MG = I /
        # MD = I are COLUMN-first vector lists { … ] (each generator/detempering a ket [ … }), like
        # M_LGL — the outer wrap here, the per-column marks via vector_list_marks below.
        if self.tile_open("vectors", "primes"):
            for i in range(self.d):
                self.bracket(f"vec:primes:{i}", MAP_BRACKETS, "primes", self.vec_top(i), ROW_H, stacked=True)
        if self.tile_open("mapping", "gens"):
            self.bracket("selfmap", GENMAP_BRACKETS, "gens",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)
        if self.tile_open("mapping", "detempering"):
            self.bracket("mapped_detempering", GENMAP_BRACKETS, "detempering",
                         self.rows["mapping"].y, self.r * ROW_H, fit=True)
        # the lifted interval lists: B_L over the primes column (the basis change matrix) and the
        # lifted C/T/H/detempering lists, each a [ … ] over the dL components in the ss_vectors row;
        # the mapped versions a [ … ] over the rL rows in the ss_mapping row (interest stands alone,
        # no outer wrap — mirroring the on-domain vectors / mapping rows).
        if self.row_open("ss_vectors"):
            # B_L the basis change matrix wraps in an OUTER ⟨ … ] (a covector-style bracket per
            # the mockup — distinct from the plain [ … ] of the lifted lists), its inner columns
            # the domain-element kets from vector_list_marks below
            if self.tile_open("ss_vectors", "primes"):
                self.bracket("ss_vec:primes", MAP_BRACKETS, "primes", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            for group in ("commas", "targets"):
                if self.tile_open("ss_vectors", group):
                    self.bracket(f"ss_vec:{group}", LIST_BRACKETS, group, self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_vectors", "held"):
                self.bracket("ss_vec:held", LIST_BRACKETS, "held", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
            if self.tile_open("ss_vectors", "detempering"):
                self.bracket("ss_vec:detempering", LIST_BRACKETS, "detempering", self.rows["ss_vectors"].y, self.dL * ROW_H, fit=True)
        if self.row_open("ss_mapping"):
            for group in ("commas", "targets"):
                if self.tile_open("ss_mapping", group):
                    self.bracket(f"ss_mapped:{group}", LIST_BRACKETS, group, self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.nh and self.tile_open("ss_mapping", "held"):
                self.bracket("ss_mapped:held", LIST_BRACKETS, "held", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
            if self.tile_open("ss_mapping", "detempering"):
                self.bracket("ss_mapped:detempering", GENMAP_BRACKETS, "detempering", self.rows["ss_mapping"].y, self.rL * ROW_H, fit=True)
        if self.row_open("vectors"):  # each group is a list of vectors: a [ ] spanning the d components
            for group in ("commas", "targets"):
                if self.tile_open("vectors", group):
                    self.bracket(f"vec:{group}", LIST_BRACKETS, group, self.rows["vectors"].y, self.d * ROW_H, fit=True)
            # the interest column is a loose collection, not a matrix — its kets stand alone,
            # so no outer [ … ] wraps them (see the de-matrixed mapped/imapped row below)
            if self.nh and self.tile_open("vectors", "held"):
                self.bracket("vec:held", LIST_BRACKETS, "held", self.rows["vectors"].y, self.d * ROW_H, fit=True)
            if self.tile_open("vectors", "detempering"):
                self.bracket("vec:detempering", LIST_BRACKETS, "detempering", self.rows["vectors"].y, self.d * ROW_H, fit=True)
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
            # gate the outer [ … ] on tile_open ALONE, never on the column count — an OPEN tile
            # always wears its wrap, even with zero columns (an empty target list reads as [],
            # like the vectors / mapping rows it parallels). An empty-but-open tile is real here:
            # the targets column stays open with k = 0 (it's addable), and the V column at full
            # rank has nc = 0 yet shows the unchanged half. The held / detempering / superspace
            # tiles instead vanish entirely when empty (they're undeclared, so tile_open is False),
            # so this gate handles them too. (Gating on the count once dropped the [] from the
            # empty 𝐿T tile — see test_empty_open_list_tiles_keep_their_outer_ebk.)
            for group in ("commas", "detempering", "targets", "held"):
                if self.tile_open("prescaling", group):
                    self.bracket(f"prescaling:{group}", LIST_BRACKETS, group,
                            self.rows["prescaling"].y, ph, fit=True)
            # 𝐿·B_Ls is the prescaled basis-change matrix, so it wraps ⟨ … ] like B_L (not the
            # symmetric [ … ] of the plain products); its per-column ket caps come from
            # vector_list_marks below, mirroring ss_vectors/primes.
            if self.show_superspace and self.tile_open("prescaling", "primes"):
                self.bracket("prescaling:primes", MAP_BRACKETS, "primes",
                        self.rows["prescaling"].y, ph, fit=True)
            # the bare prescaler 𝐿 is mapping-style: per-row ⟨ … ] brackets, one pair per row (the size
            # factor adds one more, for the size row). Its outer top + bottom frame is the matrix_frame
            # call above (ebktop + ebkangle), which spans the grown matrix height and that same width.
            if self.tile_open("prescaling", bare_col):
                pspan = self.matrix_span(bare_col)
                for i in range(self.prescale_rows + self.size_rows):
                    self.bracket(f"prescaling:row:{i}", MAP_BRACKETS, bare_col,
                            self.rows["prescaling"].y + i * ROW_H, ROW_H, span=pspan, stacked=True)
                if self.size_rows:  # the guide's \hline in 𝑋 = 𝑍𝐿: a horizontal rule separating the bottom
                    # size row from the top square
                    gx, gw = pspan
                    self.cells.append(CellBox("bar:prescaling", gx, self.rows["prescaling"].y + self.prescale_rows * ROW_H - SEP_W / 2,
                                         gw, SEP_W, "hbar"))
        if self.tile_open("tuning", "gens"):  # the generator tuning map is framed { … ] (per the mockup)
            self.bracket("tuning:genmap", GENMAP_BRACKETS, "gens", self.rows["tuning"].y, ROW_H)
        # the detempering tuning row IS the generator tuning map (𝒕D = 𝒈), so it too is framed
        # { … ]; its just/retune rows are ordinary interval lists, framed below with the rest
        if self.tile_open("tuning", "detempering"):
            self.bracket("tuning:detempering", GENMAP_BRACKETS, "detempering", self.rows["tuning"].y, ROW_H)
        # the cyan superspace tuning row's 𝒈ₗ tile takes the same { … ] genmap shape as 𝒈
        # (a covector over the rL superspace generators); 𝒕ₗ / 𝒋ₗ / 𝒓ₗ over the ssprimes
        # column take the regular ⟨ … ] map brackets (covectors over the dL superspace primes).
        if self.tile_open("tuning", "ssgens"):
            self.bracket("tuning:ssgenmap", GENMAP_BRACKETS, "ssgens", self.rows["tuning"].y, ROW_H)
        for key in ("tuning", "just", "retune", "complexity"):
            if self.row_open(key):
                if self.tile_open(key, "primes"):
                    self.bracket(f"{key}:map", MAP_BRACKETS, "primes", self.rows[key].y, ROW_H)
                if self.tile_open(key, "commas"):
                    self.bracket(f"{key}:commalist", LIST_BRACKETS, "commas", self.rows[key].y, ROW_H)
                if self.tile_open(key, "targets"):
                    self.bracket(f"{key}:list", LIST_BRACKETS, "targets", self.rows[key].y, ROW_H)
                # the interest size rows carry NO bracket — the whole interest column is a bare
                # collection of standalone values, not a [ … ] list (per the mockup)
                if self.nh and self.tile_open(key, "held"):
                    self.bracket(f"{key}:hlist", LIST_BRACKETS, "held", self.rows[key].y, ROW_H)
                # detempering's just/retune/complexity sizes are ordinary lists; its tuning row
                # is the genmap, bracketed { … ] above (so it's skipped here)
                if key != "tuning" and self.tile_open(key, "detempering"):
                    self.bracket(f"{key}:detemperinglist", LIST_BRACKETS, "detempering", self.rows[key].y, ROW_H)
                # the chapter-9 superspace tuning cells over the ssprimes column: each row is a
                # covector over the dL ss_primes, ⟨ … ] like the primes column above (𝒕ₗ / 𝒋ₗ / 𝒓ₗ).
                # The complexity row joins them once the superspace shows: its ss-primes tile is the
                # prime complexity map ‖𝐿[i]‖q, a covector ⟨ … ] just like the domain-primes map.
                if (key != "complexity" or self.show_superspace) and self.tile_open(key, "ssprimes"):
                    self.bracket(f"{key}:ssprimes", MAP_BRACKETS, "ssprimes", self.rows[key].y, ROW_H)
        if self.tile_open("weight", "targets"):
            self.bracket("weight", LIST_BRACKETS, "targets", self.rows["weight"].y, ROW_H)
        if self.tile_open("damage", "targets"):
            self.bracket("damage", LIST_BRACKETS, "targets", self.rows["damage"].y, ROW_H)

    def _emit_matrix_labels(self) -> None:
        """Matrix row + column labels (when header symbols are on — independent of the in-tile symbol)."""
        # Matrix row + column labels (when header symbols are on — a toggle independent of the
        # in-tile big symbol above). A row-labelled tile is a
        # covector stack — the mapping 𝑀, the prescaler 𝑋 — and labels each row 𝒎ᵢ / 𝒙ᵢ
        # at the LEFT of the row's ⟨, inside the MATLABEL_W gutter reserved in the primes
        # column. Every other multi-cell tile labels its COLUMNS above each cell in the
        # MATLABEL_H band reserved at the top of the row's value band.
        if self.show_header_symbols:
            # the per-column group's count, so a tile's columns are iterated by its
            # (rkey, ckey) without re-deriving the loop bounds each time
            group_count = {"gens": self.r, "primes": self.d, "commas": self.nc + self.nu, "targets": self.k,
                           "held": self.nh, "detempering": self.r, "interest": self.mi,
                           "ssgens": self.rL, "ssprimes": self.dL}
            # the y of the i-th row inside a row-labelled tile: the mapping stacks under
            # row_y["mapping"]; the prescaler stacks d rows under row_y["prescaling"]; the
            # chapter-9 superspace mapping M_L stacks rL rows under row_y["ss_mapping"]
            # the bare prescaler's covector rows stack under row_y["prescaling"]; once the superspace
            # shows it lives in the ss-primes column (prescale_rows = dL tall), else the domain primes
            # (d tall). Both keyed so row_labels (which targets whichever column is the bare prescaler)
            # always resolves.
            _prescale_top = lambda i: self.rows["prescaling"].y + i * ROW_H
            row_top = {
                ("mapping", "primes"): self.map_top,
                ("canon", "primes"): self.canon_top,  # 𝑀_C's rc covector rows 𝒎_Cᵢ
                ("canon", "gens"): self.canon_top,    # the form matrix 𝐹's rc rows 𝒇ᵢ
                ("vectors", "primes"): self.vec_top,  # M_j = I's d covector rows 𝒎ⱼᵢ, in the primes gutter
                ("projection", "primes"): self.proj_top,  # P's d rows of maps 𝒑ᵢ, like the mapping's 𝒎ᵢ
                ("projection", "ssprimes"): self.proj_top,  # P_L→s's d rows of maps 𝒑_L→sᵢ

                ("prescaling", "primes"): _prescale_top,
                ("prescaling", "ssprimes"): _prescale_top,
                ("ss_mapping", "ssprimes"): self.ss_map_top,
                ("ss_mapping", "primes"): self.ss_map_top,
                ("ss_vectors", "ssprimes"): self.ss_vec_top,  # M_jL = I's dL rows of maps 𝒎ⱼₗᵢ
                ("ss_projection", "ssprimes"): self.ss_proj_top,  # P_L's dL rows of maps 𝒑ₗᵢ
            }
            row_count = {("mapping", "primes"): self.r,
                         ("canon", "primes"): self.rc,  # 𝑀_C is rc × d
                         ("canon", "gens"): self.rc,    # the form matrix 𝐹 is rc × rc
                         ("vectors", "primes"): self.d,  # M_j = I is d × d
                         ("projection", "primes"): self.d,  # P is d×d (a map per domain prime)
                         ("projection", "ssprimes"): self.d,  # P_L→s is d×dL (a covector per domain prime)

                         ("prescaling", "primes"): self.prescale_rows + self.size_rows,
                         ("prescaling", "ssprimes"): self.prescale_rows + self.size_rows,
                         ("ss_mapping", "ssprimes"): self.rL,
                         ("ss_mapping", "primes"): self.rL,
                         ("ss_vectors", "ssprimes"): self.dL,
                         ("ss_projection", "ssprimes"): self.dL}  # P_L is dL × dL (a covector per superspace prime)
            for (rkey, ckey), glyph in self.row_labels.items():
                if not self.tile_open(rkey, ckey):
                    continue
                top = row_top[(rkey, ckey)]
                for i in range(row_count[(rkey, ckey)]):
                    # the bare pretransformer 𝑋 = 𝑍𝐿's bottom (size-sensitizing) row is labelled 𝒛 (the
                    # size-sensitizing matrix 𝑍's row variable), NOT 𝒍₄ / 𝒙₄ — it isn't a fourth prime.
                    size_row = rkey == "prescaling" and i == self.prescale_rows and self.size_rows
                    g = self._form_subscripted(glyph, rkey, ckey)  # 𝒎ᵢ → 𝒎_Cᵢ when the form layer is on
                    text = "𝒛" if size_row else f"{g}{_sub(i + 1)}"
                    self.cells.append(CellBox(
                        f"matlabel:row:{rkey}:{ckey}:{i}",
                        # past the etpick balance pad + the drag-handle gutter (when present), so the
                        # handle sits to its left and the label still hugs the ⟨; the box fills the
                        # column's row-label gutter (wider in the superspace primes column, for
                        # M_s→L's 𝒎ₛ→ₗᵢ) so a wide label never overflows the ⟨ bracket
                        self.content_x[ckey] + self.etpick_left_pad(ckey) + self.handle_gutter_w(ckey), top(i),
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
                if ckey not in group_count or rkey not in self.rows or self.rows[rkey].matlabel_top is None:
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
                y = self.rows[rkey].matlabel_top
                for i in range(group_count[ckey]):
                    # the form layer subscripts the mapped products' leading glyph too — 𝑀𝐜ᵢ → 𝑀_C𝐜ᵢ,
                    # 𝑀𝐡ᵢ → 𝑀_C𝐡ᵢ, 𝒈ᵢ → 𝒈_Cᵢ, 𝐠ᵢ → 𝐠_Cᵢ — matching the tile symbols (the form-invariant
                    # 𝒕𝐜 / 𝒋𝐜 / P columns stay bare). Done on the bare glyph, BEFORE the index subscript.
                    glyph = label if callable(label) else self._form_subscripted(label, rkey, ckey)
                    text = glyph(i) if callable(glyph) else f"{glyph}{_sub(i + 1)}"
                    if self.show_unchanged and ckey == "commas":  # the column's vectors are 𝐯, not 𝐜
                        text = text.replace("𝐜", "𝐯")
                    # the consolidated V's value cells shift the U half right past any pending comma
                    # draft (comma_value_pos); the column labels must track them so 𝐯ₙ sits over its
                    # own column — else every U-half label lands one slot left (onto the draft) and the
                    # last U column goes unlabelled. comma_value_pos is identity off-draft, so this is a
                    # no-op without a pending comma (and for every non-comma group).
                    x = left(self.comma_value_pos(i)) if ckey == "commas" else left(i)
                    self.cells.append(CellBox(
                        f"matlabel:col:{rkey}:{ckey}:{i}",
                        x, y, COL_W, MATLABEL_H,
                        "matlabel", text=text,
                    ))

    def _emit_axes(self) -> None:
        """Shared axes: the fanned column/row buses, the trunks and the spine gridlines."""
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
        for key in self.rows:
            if self._row_fans(key):
                self.row_axis(key)
            else:
                self.gridline(f"h:{key}", "h", self.rows[key].y + self.rows[key].h / 2, self.node_edge, self.total_w - self.node_edge,
                         dotted=f"row:{key}" in self.collapsed)

    def _emit_panels(self, gtm_box, opt_box, approach_frame) -> None:
        """The grey tile panels plus the control-region / ranges / optimization / approach boxes."""
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

    def _emit_washes(self) -> None:
        """The colorization washes: white bases plus the per-group colour bands."""
        if self.col_x and self.rows:
            bands = []  # (id, x, y, w, h, group)
            # walk self.tiles (the ordered declaration), NOT the declared_tiles set: set
            # iteration order varies per process (string hashing), which emitted the wash
            # blocks in a different DOM order on every server restart. Same filter, fixed order.
            for _bid, rkey, ckey in self.tiles:
                if (rkey, ckey) not in self.declared_tiles or not self.tile_open(rkey, ckey):
                    continue
                groups = sorted(g for g in self.tile_groups(rkey, ckey) if self.settings.get(f"{g}_colorization"))
                if not groups:
                    continue
                x, w = self.col_x[ckey] - WASH_PAD, self.col_w[ckey] + 2 * WASH_PAD
                y, h = self.rows[rkey].tile_top - WASH_PAD, self.rows[rkey].tile_h + 2 * WASH_PAD
                for group in groups:
                    bands.append((f"{group}:{rkey}:{ckey}", x, y, w, h, group))
            for bid, x, y, w, h, _ in bands:  # white bases (a layer below the colour bands)
                self.blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
            for bid, x, y, w, h, group in bands:  # the darken colour bands over them
                self.blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))

    def _emit_symbols_captions(self) -> None:
        """Quantity symbols, equivalences, captions and units lines inside each tile."""
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
                        # custom (manual) weights have no closed form — the 𝒘 row drops its "= 𝒄⁻¹"
                        # slope equivalence (like a typed prescaler override drops "𝑋 = 𝐿")
                        ("weight", "targets"): "" if self.custom_weights_active else WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                        ("prescaling", "ssprimes" if self.show_superspace else "primes"): self.prescaler_equivalence,
                        **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                        # the form layer subscripts the canonical-form objects in their defining
                        # equations too (𝒕 = 𝒈C𝑀C, P = GC𝑀C, …); the form-invariant tails stay bare.
                        **(FORM_EQUIVALENCES if self.show_form_subscript else {}),
                        # the consolidated interval-vectors header: V = C|U (the comma basis and the
                        # unchanged basis concatenated). The mapped tile drops its "= 𝑂" (only the
                        # comma half of M·V vanishes; the unchanged half maps to the held generators).
                        **({("vectors", "commas"): " = C|U", ("mapping", "commas"): ""}
                           if self.show_unchanged else {})}
        if self.show_superspace:  # P's equivalence gains the superspace decomposition (per the mockup)
            # append the superspace tail to the CURRENT base (form-subscripted when show_form), so the
            # P = GC𝑀C decomposition keeps its subscripts ahead of the " = Gₛ→ₗ𝑀ₛ→ₗ" tail
            equivalences[("projection", "primes")] = (
                equivalences[("projection", "primes")] + self._projection_superspace_tail())
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
            cy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey]
            if (self.show_symbols or self.show_equiv) and rkey in SYMBOLED_ROWS:
                # the symbol band reserves SYMBOL_H + BAND_GAP (see the row-height pass); spend that
                # BAND_GAP ABOVE the glyph so the symbol/equivalence clears the values/EBK region above
                # it, mirroring the gap the caption already gets below the symbol — the symbol cell is a
                # fixed SYMBOL_H drawn flush, so without this offset the gap would all fall below it
                cy += BAND_GAP
                equiv = equivalences.get((rkey, ckey), "") if self.show_equiv else ""
                base_symbol = self.prescaling_symbols.get((rkey, ckey), SYMBOLS.get((rkey, ckey), ""))
                if ai and (rkey, ckey) in ALL_INTERVAL_SYMBOLS:  # e.g. the target list T → Tₚ
                    base_symbol = ALL_INTERVAL_SYMBOLS[(rkey, ckey)]
                if self.show_unchanged and ckey == "commas":  # the whole column reads V, not C
                    # swap the comma-basis C → V, but PROTECT a baked-in subscript-C marker (the canon
                    # row's symbols carry it already, e.g. 𝑀_C C) so the swap never turns its sentinel
                    # "C" into "V" — the main mapping row instead gets its subscript added just below.
                    base_symbol = base_symbol.replace(SUBSCRIPT_C, "\x00").replace("C", "V").replace("\x00", SUBSCRIPT_C)
                # mark the canonical form with a subscript C after the leading glyph (𝑀/Y/𝒈/G), AFTER
                # the unchanged C→V swap so the mapped-comma tile reads 𝑀_C·V and the subscript's own
                # "C" sentinel is never hit by that swap. The matrix labels get the same treatment.
                base_symbol = self._form_subscripted(base_symbol, rkey, ckey)
                glyph = base_symbol if (self.show_symbols or equiv) else ""
                if glyph or equiv:
                    self.cells.append(CellBox(f"symbol:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
                cy += SYMBOL_H
            if self.show_captions and self.show_unchanged and (rkey, ckey) == ("counts", "commas"):
                # the consolidated V counts split into two names, each centred over its half (mirroring
                # the n / u tallies above them): "nullity" over the comma sub-columns, "unchanged
                # interval count" over the unchanged ones
                comma_half_w = self.nc * COL_W + self.empty_comma_w
                if comma_half_w:
                    comma_half_x = self.commas_x if self.empty_comma_w else self.comma_left(0)
                    self.cells.append(CellBox("caption:counts:commas", comma_half_x, cy, comma_half_w,
                                         self.rows[rkey].cap, "caption", text="nullity"))
                self.cells.append(CellBox("caption:counts:commas:u", self.comma_left(self.nc_shown), cy, self.nu * COL_W,
                                     self.rows[rkey].cap, "caption", text="unchanged interval count"))
                continue
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
                self.cells.append(CellBox(f"caption:{rkey}:{ckey}", self.col_x[ckey], cy, self.col_w[ckey], self.rows[rkey].cap,
                                     "caption", text=name, underlines=underlines))
            # the "units: …" line sits below the caption band (independent of names/symbols),
            # reading the box's entry from tile_unit (UNITS, with the damage/weight/complexity
            # annotation resolved from the live scheme) — bold-upright unit glyphs via _math_html
            unit = self.tile_unit(rkey, ckey)
            # the on-domain coordinate p reads b (basis element) over a nonstandard subgroup —
            # consistently with the gridded cells and the units row/column, so the whole column
            # swaps together. Superspace tiles are excluded (their p is a TRUE prime, kept): a wholly-
            # superspace tile (ss_ row) keeps every p, and a superspace COLUMN protects its p
            # denominator — which is why the projection row's bridge tiles into that column (P_L→s
            # b/p, G_L→s b/gL) carry their domain numerator as a literal b, not a swapped p.
            if unit and not (rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")):
                unit = _subscript_coord(unit, "p", self.domain_label)
            if self.show_units and unit:
                uy = self.rows[rkey].y + self.rows[rkey].h + self.rows[rkey].frame + self.row_cpick[rkey] + self.rows[rkey].sym + self.rows[rkey].cap
                self.cells.append(CellBox(f"units:{rkey}:{ckey}", self.col_x[ckey], uy, self.col_w[ckey], UNIT_H,
                                     "units", text=f"units: {unit}"))

    def _emit_presets(self) -> None:
        """Preset chooser dropdowns in the reserved band below each governing tile."""
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
                top = self.ptext_band_y(rkey) + self.rows[rkey].ptext  # below the plain-text band
                # a chooser with no real choice renders as a DISABLED dropdown (greyed, non-interactive,
                # caption greyed with it), like the all-interval-locked target / weight-slope choosers:
                #  - the target set scheme doesn't apply in all-interval (it targets every interval), and
                #  - a tuning / prescaler chooser locked to its single on-list option (e.g. the default
                #    T minimax-U / log-prime) — see _preset_locked.
                disabled = (name == "target" and service.is_all_interval(self.tuning_scheme)) \
                    or self._preset_locked(name)
                # the <choose form> dropdown embeds in the temperament chooser's box (mapping / comma
                # basis) while form controls show — same box, never a separate one
                fc = next((fn for fn, rk, ck, _l in FORM_CHOOSERS if rk == rkey and ck == ckey), None)
                form_chooser = (f"formchooser:{fc}", "form") if (fc and self._preset_form_label(name, rkey, ckey)) else None
                cx, cw, cy = self.control_box(f"block:{cid}", ckey, top, self.preset_cap(name), label,
                                              disabled=disabled, scheme_btn=(name == "projection"),
                                              form_chooser=form_chooser)
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

    def _emit_all_interval_check_fallback(self) -> None:
        """The all-interval checkbox alone in the band when the presets layer is hidden."""
        # the all-interval checkbox is revealed by the show-panel "all-interval" entry ALONE (not the
        # presets toggle). When the target chooser is shown, emit_preset seats the checkbox inside
        # the chooser's box (box 𝐓, above); when it is hidden the checkbox is the band's only target
        # control, alone at the column's left. The vectors row reserves the band either way.
        if self.settings["all_interval"] and not self.show_presets and self.tile_open("vectors", "targets"):
            top = self.ptext_band_y("vectors") + self.rows["vectors"].ptext
            self.emit_all_interval_check(self.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)

    def _emit_form_choosers(self) -> None:
        """The <choose form> choosers when presets are OFF — in their own box (there is no chooser
        box to ride in). With presets ON they embed in the temperament chooser's box instead (see
        :func:`_emit_presets` / :func:`control_box`), never a separate box."""
        # it canonicalizes the mapping / comma basis it rides (an undoable edit). A control, so it
        # ignores the value-display toggles, like the preset choosers.
        if self.show_form_controls and not self.show_presets:
            for name, rkey, ckey, label in FORM_CHOOSERS:
                if not self.tile_open(rkey, ckey):
                    continue
                top = self.ptext_band_y(rkey) + self.rows[rkey].ptext + self.rows[rkey].pre
                cx, cw, cy = self.control_box(f"block:formchooser:{name}", ckey, top, PRESET_W, label)
                self.cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser",
                                     text=self.mapping_form_key if name == "mapping" else self.comma_basis_form_key))

    def _emit_scheme_buttons(self) -> None:
        """The return-to-scheme ✕ buttons in their own boxes when presets are off."""
        # the always-present "return to scheme" ✕ button on the projection (P) and embedding (G) tiles —
        # hands a picked/edited tuning back to the scheme + target list (editor.back_to_scheme). With
        # presets ON it rides INSIDE the established-projection chooser's box (control_box's scheme_btn,
        # ABOVE the dropdown + caption). With presets OFF there is no chooser, so it gets its own small
        # box here. app.py greys it when there's nothing to revert.
        if self.settings["projection"] and not self.show_presets:
            for ckey in ("primes", "gens"):
                if not self.tile_open("projection", ckey):
                    continue
                top = self.ptext_band_y("projection") + self.rows["projection"].ptext
                # its own small box (the presets-off counterpart of control_box's scheme_btn row).
                # We're past the _control_region_boxes flush, so append the box straight to self.blocks
                # — it still layers on top of the panels (appended just above) since z-order is list order.
                box_y = top + BOX_OUTER
                self.blocks.append(Block(f"block:scheme:{ckey}", self.col_x[ckey], box_y, self.col_w[ckey],
                                         BOX_INNER + SCHEME_BTN_SQ + CTRL_LABEL_GAP, boxed=True))
                self.emit_scheme_button(self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER, ckey)

    def _emit_ptext_band(self) -> None:
        """The plain-text value band below each tile's symbol/caption stack."""
        # plain-text value band: each tile's value as its natural EBK string, directly
        # below the symbol/caption stack (above the preset chooser). The two editable
        # duals (mapping, comma basis) render as inputs that drive the grid; every other
        # value is read-only. The app shrinks each box's font so the value fits one line.
        if self.show_ptext:
            for (rkey, ckey), text in self.ptext_strings.items():
                if not self.tile_open(rkey, ckey):
                    continue
                # an editable dual flips to a static two-tone box while it has a pending draft (the
                # committed part black, the draft entry green — a single-colour input can't do that):
                # the comma basis when a comma is pending, the target list when a target is, and the
                # MAPPING when a generator ROW is pending (the draft map greens like its grid cells).
                # The other read-only values keep their normal kinds.
                if (rkey, ckey) == ("vectors", "commas") and self.pending is not None \
                        or (rkey, ckey) == ("vectors", "targets") and self.pending_target is not None \
                        or (rkey, ckey) == ("mapping", "primes") and self.pending_mapping_row is not None:
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

    def _emit_ebk_frames_and_marks(self) -> None:
        """Matrix frames, vector-list ket marks and the C|U split bars."""
        self.matrix_frame("mapping", "primes", "primes")
        # P = GM: a covector stack like the mapping, but closing with the prime-coordinate ket ⟩
        # (P is p/p) — matching its plain text [⟨…]…⟩, not the mapping's generator-coordinate }
        self.matrix_frame("projection", "primes", "proj", foot="ebkangle")
        # P_L→s the superspace projection: a covector stack like P, framed over the ssprimes column
        self.matrix_frame("projection", "ssprimes", "proj_sl", foot="ebkangle")
        self.matrix_frame("canon", "primes", "canon")
        self.matrix_frame("canon", "gens", "form")
        self.matrix_frame("canon", "canongens", "fcancel")  # 𝐹⁻¹𝐹 = 𝐼, framed { … ] like 𝑀𝐺
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
        # the superspace projection P_L = G_L M_L: a covector stack framed like P (the on-domain
        # projection), closing with the prime-coordinate angle ⟩ (ebkangle) — an operator, not a map
        self.matrix_frame("ss_projection", "ssprimes", "ss_proj", foot="ebkangle")
        # M_jL = I (ss_vectors, ssprimes): a covector stack like M_L, but it's the p/p JI mapping over
        # the superspace primes — an operator, so it closes with the angle ⟩ (ebkangle), like P_L, NOT the
        # mapping's curly }. M_s→L is the genuine rL × d mapping (framed like M_L, brace foot).
        self.matrix_frame("ss_vectors", "ssprimes", "ss_vec_jmap", foot="ebkangle")
        self.matrix_frame("ss_mapping", "primes", "ss_msl")
        # M_j = I (vectors, primes): the on-domain twin of M_jL — a p/p covector stack closing with
        # the angle ⟩ (ebkangle), like P. (MG / MD / M_LGL are COLUMN-first vector lists, framed by
        # vector_list_marks below, NOT matrix_frame.)
        self.matrix_frame("vectors", "primes", "vec:primes", foot="ebkangle")

        # the mapped comma basis is one bracketed list, NOT a matrix of separated columns — so no
        # dividing rules between its entries (a long-standing stray-separator bug); over V the single
        # C|U bar (drawn by _v_split) is the only divider, as for every consolidated-column tile
        self.vector_list_marks("mapping", "mapped_comma", "commas", self.comma_left, self.nc + self.nu, separators=False)  # M·C then M·U over V
        # the projected unrotated vector list P·V: prime-count-vector columns (kets), C|U bar only
        self.vector_list_marks("projection", "proj_v", "commas", self.comma_left, self.nc + self.nu, foot="ebkangle", separators=False)
        # the generator embedding G: each held generator a prime-count ket [ … ⟩ column over the gens
        # columns (the outer { … ] is the bracket() call above), no dividing rules
        self.vector_list_marks("projection", "embed", "gens", self.gen_left, self.r, foot="ebkangle", separators=False)
        # G_L→s the superspace generator embedding: a vector list like G over the ssgens columns
        self.vector_list_marks("projection", "embed_sl", "ssgens", self.ss_gen_left, self.rL, foot="ebkangle", separators=False)
        # the projected vector lists' per-column ket marks (P·D / P·T / P·H / P·interest): [ … ⟩ feet
        # over each column, like the interval-vectors row they project. P·D = the embedding G (no
        # separators, like G); P·T a matrix (separator rules, like T); P·H mirrors the held column; the
        # P·interest kets stand alone (no separators, no outer wrap, like interest).
        self.vector_list_marks("projection", "proj_pd", "detempering", self.detempering_left, self.r, foot="ebkangle", separators=False)
        self.vector_list_marks("projection", "proj_pt", "targets", self.target_left, self.k, foot="ebkangle")
        self.vector_list_marks("projection", "proj_ph", "held", self.held_left, self.nh, foot="ebkangle")
        self.vector_list_marks("projection", "proj_pi", "interest", self.interest_left, self.mi, foot="ebkangle", separators=False)
        # the SUPERSPACE projection row's per-column ket marks (the inner [ … ⟩ of G_L / P_L·B_Ls /
        # P_L·D_L / P_L·C_L / P_L·T_L / P_L·H_L / P_L·interest), dL-tall, mirroring the on-domain marks above
        self.vector_list_marks("ss_projection", "ss_embed", "ssgens", self.ss_gen_left, self.rL, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_bls", "primes", self.prime_left, self.d, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_pd", "detempering", self.detempering_left, self.r, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_v", "commas", self.comma_left, self.nc + self.nu, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_projection", "ss_proj_pt", "targets", self.target_left, self.k, foot="ebkangle")
        self.vector_list_marks("ss_projection", "ss_proj_ph", "held", self.held_left, self.nh, foot="ebkangle")
        self.vector_list_marks("ss_projection", "ss_proj_pi", "interest", self.interest_left, self.mi, foot="ebkangle", separators=False)
        self.vector_list_marks("mapping", "mapped", "targets", self.target_left, self.k)
        # the interest column's mapped images stand alone — no separator rules between columns
        self.vector_list_marks("mapping", "imapped", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("mapping", "hmapped", "held", self.held_left, self.nh)
        # MG = I / MD = I (identity objects): COLUMN-first vector lists in generator coords — each
        # column a ket [ … } (the default ebkbrace foot), the outer { … ] wrap from the bracket pass.
        self.vector_list_marks("mapping", "selfmap", "gens", self.gen_left, self.r, separators=False)
        self.vector_list_marks("mapping", "mapped_detempering", "detempering", self.detempering_left, self.r, separators=False)
        # the canonical-mapping row's mapped lists — per-column ket marks mirroring the mapping row's
        # (default ebkbrace foot, generator coords; the outer { … ] / [ … ] wraps come from the bracket
        # pass above). 𝑀_C·D = 𝐹 is a vector list like MD; 𝑀_C·V's lone C|U bar is _v_split's job; the
        # 𝑀_C·interest kets stand alone (no separators, no outer wrap), like the mapping interest.
        self.vector_list_marks("canon", "canon_detempering", "detempering", self.detempering_left, self.r, separators=False)
        self.vector_list_marks("canon", "canon_comma", "commas", self.comma_left, self.nc + self.nu, separators=False)
        self.vector_list_marks("canon", "canon_mapped", "targets", self.target_left, self.k)
        self.vector_list_marks("canon", "canon_imapped", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("canon", "canon_hmapped", "held", self.held_left, self.nh)
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
        self.vector_list_marks("ss_vectors", "ss_vec:commas", "commas", self.comma_left, self.nc + self.nu, foot="ebkangle", separators=False)  # B_L·C then B_L·U over V
        self.vector_list_marks("ss_vectors", "ss_vec:targets", "targets", self.target_left, self.k, foot="ebkangle")
        self.vector_list_marks("ss_vectors", "ss_vec:held", "held", self.held_left, self.nh, foot="ebkangle")
        self.vector_list_marks("ss_vectors", "ss_vec:interest", "interest", self.interest_left, self.mi, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_vectors", "ss_vec:detempering", "detempering", self.detempering_left, self.r, foot="ebkangle")
        self.vector_list_marks("ss_mapping", "ss_mapped:commas", "commas", self.comma_left, self.nc + self.nu, separators=False)  # M_s→L·C then M_s→L·U over V
        self.vector_list_marks("ss_mapping", "ss_mapped:targets", "targets", self.target_left, self.k)
        self.vector_list_marks("ss_mapping", "ss_mapped:held", "held", self.held_left, self.nh)
        # 𝐿·B_Ls (the prescaled basis-change matrix in the domain-primes column once the superspace
        # shows): per-column ket caps over its dL-tall prescaled columns, exactly like B_L above
        if self.show_superspace:
            self.vector_list_marks("prescaling", "prescaling:primes", "primes", self.prime_left, self.d, foot="ebkangle", separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:interest", "interest", self.interest_left, self.mi, separators=False)
        self.vector_list_marks("ss_mapping", "ss_mapped:detempering", "detempering", self.detempering_left, self.r)
        # M_LGL = I (identity object): a COLUMN-first vector list over the superspace generators —
        # each a ket [ … } (default ebkbrace foot), the outer { … ] wrap from the bracket pass.
        self.vector_list_marks("ss_mapping", "ss_selfmap", "ssgens", self.ss_gen_left, self.rL, separators=False)
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
        self.v_split_bars()  # the lone C|U divider down every tile of the consolidated V column

    def _emit_tile_toggles(self) -> None:
        """A per-tile fold toggle inset into each content tile's top-left corner."""
        # a per-tile fold toggle inset into each content tile's top-left corner: it
        # sits in the head strip reserved above the content, TOGGLE_INSET in from the
        # grey panel's top-left, so it never touches an edge or overlaps the frame.
        # Anchored to the grey panel's left edge (col_x), not the centred content — so a
        # caption-widened tile keeps the toggle on its edge rather than drifting it inward.
        # Present whenever the tile's row and column bands are open — it stays put when
        # only the tile is folded, so the tile can be re-expanded.
        for _bid, rkey, ckey in self.tiles:
            if ((rkey, ckey) in self.declared_tiles  # a dropped tile (e.g. all-interval's retune×targets) takes its toggle too
                    and rkey in self.rows and ckey in self.col_x and self.row_open(rkey) and self.col_open(ckey)):
                glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in self.collapsed)
                self.cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                     self.col_x[ckey] - PAD + TOGGLE_INSET, self.rows[rkey].tile_top - PAD + TOGGLE_INSET,
                                     TOGGLE, TOGGLE, "tiletoggle", text=glyph))

    def _apply_value_display_filters(self) -> None:
        """Value-display filtering and the doomed-column remove preview over the final cells."""
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

        # Any rank DROP over the consolidated V column deletes the last unchanged interval (in
        # projection #unchanged = rank): a comma DRAFT being added (self.pending), or a mapping − hover
        # un-tempering a comma born in its place (self.ghost_comma). Preview that interval's WHOLE
        # column red — the standard remove look — across every value tile. The doomed column's value
        # cells all share one x (comma_left of its sub-column), so a single pass flags them; the
        # w == COL_W / kind guard skips the count + caption that ride that x when nu == 1. (A rank
        # RISE — comma − / mapping-row draft — instead BIRTHS a U interval; see the born-U ghost below.)
        if (self.pending is not None or self.ghost_comma) and self.show_unchanged and self.nu:
            doomed_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, preview_remove=True)
                          if (cb.w == COL_W and cb.x == doomed_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

        # The dual: a comma − hover RAISES the rank, BIRTHING the last unchanged column (appended to
        # the U arrays above with its computed values). Tint that whole column green — the standard
        # newborn look — BEFORE the rank-duality pass below, so its `pending` survives the amber the
        # crossing mapping rows would otherwise paint (green beats amber; only a red row/col overrides).
        if self.born_u:
            born_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, pending=True)
                          if (cb.w == COL_W and cb.x == born_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

        # The comma↔mapping rank-duality preview. The comma basis and the mapping are duals
        # (r + n = d), so every rank change is one operation seen from two sides, and the grid
        # previews BOTH: what LEAVES reds, what RECOMBINES ambers, what is BORN greens. The BORN
        # green is rendered above (the editable draft column/row, or the non-editable hover ghost
        # whose VALUES are computed for a − hover); this pass paints the structural red/amber.
        #   • comma DRAFT / comma − : the mapping side moves. A draft drops the LAST row (red) and
        #     recombines the rest (amber); a − hover recombines ALL rows (amber) as a generator is
        #     born (the green ghost row above).
        #   • mapping-row DRAFT / mapping − : the comma side moves, dually. (Meantone has one comma,
        #     so a draft just reds it — no survivor to amber.)
        remove_rows = change_rows = remove_commas = change_commas = frozenset()
        if self.pending is not None and self.r:               # adding a comma → drops the last row
            remove_rows, change_rows = frozenset({self.r - 1}), frozenset(range(self.r - 1))
        if self.pending_mapping_row is not None and self.nc:  # adding a generator → drops the last comma
            remove_commas, change_commas = frozenset({self.nc - 1}), frozenset(range(self.nc - 1))
        if self.preview_remove is not None:                   # a − hover: red the hovered leaver,
            axis, idx = self.preview_remove                   # amber every survivor on the dual axis
            if axis == "comma":      # removing comma idx → that comma reds; all mapping rows recombine
                remove_commas, change_rows = frozenset({idx}), frozenset(range(self.r))
            else:                    # removing row idx → that row reds; all commas recombine
                remove_rows, change_commas = frozenset({idx}), frozenset(range(self.nc))
        if remove_rows or change_rows or remove_commas or change_commas:
            # A red row/column overrides the perpendicular amber AND green at every crossing — the
            # cell there is about to vanish with its row/column. A mapping ROW is its cells by the
            # `gen` attr (which the matrix, mapped values, generator ratio AND the generator's tuning
            # cell all carry); a comma COLUMN is the value cells sharing its x (the `comma` attr is
            # overloaded across interval groups, so x is the safe column key). Precedence: RED (row
            # OR col) > the green newborn (pending) > AMBER. Cells already reddened above (the doomed
            # unchanged column) keep their red.
            red_xs = frozenset(self.comma_left(c) for c in remove_commas)
            amber_xs = frozenset(self.comma_left(c) for c in change_commas)
            def _dual(cb):
                if cb.kind not in RINGABLE_KINDS or cb.preview_remove:
                    return cb
                if cb.gen in remove_rows or cb.x in red_xs:
                    # red overrides the green/amber it crosses; clear `pending` so a crossed ghost
                    # cell renders purely red (its value vanishes with its row/column)
                    return replace(cb, preview_remove=True, pending=False)
                if cb.pending:
                    return cb                                  # the green newborn, where no red crossed it
                if cb.gen in change_rows or cb.x in amber_xs:
                    return replace(cb, preview_change=True)
                return cb
            self.cells = [_dual(cb) for cb in self.cells]

    def layout(self) -> Layout:
        self.cells: list[CellBox] = []
        self.lines: list[Line] = []
        self.blocks: list[Block] = []
        # the box-𝐋/𝒄/𝒘 control boxes are emitted during the cell pass (to position their controls)
        # but must LAYER ON TOP of the grey tile panels — appended below the panel loop, like the
        # optimization / ranges boxes — so collect them here and flush them after the panels.
        self._control_region_boxes: list[Block] = []

        self._emit_headers()
        self._emit_counts_row()
        self._emit_units()
        self._emit_quantities_row()
        self._emit_column_plus_controls()
        self._emit_rehomed_minus_controls()
        self._emit_mapping_band()
        self._emit_projection_band()
        self._emit_canon_band()
        self._emit_vectors_band()
        self._emit_superspace_rows()
        self._emit_identity_objects()
        chart_indicators = self._emit_tuning_rows()
        self._emit_prescaling_band()
        self._emit_lbox_control()
        self._emit_cbox_controls()
        self._emit_complexity_row()
        self._emit_weight_row()
        self._emit_damage_row(chart_indicators)
        self._emit_charts(chart_indicators)
        gtm_box = self._emit_tuning_ranges_box()
        opt_box = self._emit_optimization_box()
        approach_frame = self._emit_approach_box()
        self._emit_brackets()
        self._emit_matrix_labels()
        self._emit_axes()
        self._emit_panels(gtm_box, opt_box, approach_frame)
        self._emit_washes()
        self._emit_symbols_captions()
        self._emit_presets()
        self._emit_all_interval_check_fallback()
        self._emit_form_choosers()
        self._emit_scheme_buttons()
        self._emit_ptext_band()
        self._emit_ebk_frames_and_marks()
        self._emit_tile_toggles()
        self._apply_value_display_filters()

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


def build(state, settings=None, collapsed=None, **inputs) -> Layout:
    """Build the spreadsheet :class:`Layout` for ``state``. Every view/document input beyond
    ``state`` / ``settings`` / ``collapsed`` (``tuning_scheme``, the ``pending_*`` drafts,
    ``held_vectors``, ``custom_prescaler``, … and their defaults) is declared ONCE on
    :class:`_GridBuilder` and forwarded here by keyword — so a new build input is added in a
    single place instead of being re-spelled in this wrapper's signature too. No caller passes
    a 4th positional argument (verified across all ~315 call sites), so ``**inputs`` is safe."""
    return _GridBuilder(state, settings=settings, collapsed=collapsed, **inputs).layout()
