"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.app.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from dataclasses import dataclass
from html import escape as _escape
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, NamedTuple
from urllib.parse import quote

from nicegui import app, background_tasks, helpers, ui

from rtt.library.formatting import strip_negative_zero
from rtt.app import presets
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app import tooltips
from rtt.app.editor import Editor
from rtt.app.marks import (
    _BR_COLOR,
    _PENDING_COLOR,
    _angle_bracket,
    _angle_foot,
    _brace,
    _curly_bracket,
    _ebk_svg,
    _qbez,
    _rect,
    _ribbon,
    _square_bracket,
    _svg,
    _top_bracket,
    _vbar,
)


class _KindHandlers(NamedTuple):
    """The build + update pair for one cell kind — the unified replacement for the two
    parallel ``if/elif cb.kind`` ladders (audit #3). ``build(cb, wrap)`` creates the cell's
    child element(s) and registers their per-id handles; ``update(cb)`` refreshes the live
    element from the cell box. ``update`` is None for static kinds (built once, never refilled)."""
    build: Callable
    update: Callable | None = None


_ASSETS = Path(__file__).parent / "assets"  # CSS/JS asset files, loaded at import time

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration
_PANEL_W = 330  # px width the settings drawer opens to (the Show + example columns)
_TAB_W = 40  # px width of the collapsed settings tab (the hamburger over the quarter-turned title)
_TAB_H = 218  # px height of the collapsed tab's chrome (room for the title turned a quarter-turn, ~13px below the 'p')
_CHROME_H = 40  # px height of the open pane's horizontal title bar (hamburger + upright title)
_TOOLTIP_DELAY_MS = 700  # hover delay before a tooltip appears — long enough that the dense grid's
# help waits for a deliberate rest instead of popping on every passing cursor (Quasar defaults to 0)
_STORE_KEY = "rtt_doc"  # store key holding the serialized document (survives refresh)
_DARK_KEY = "rtt_dark"  # store key for the dark-mode preference — a global viewing choice kept
# OUT of the serialized document, so it survives Reset and is independent of "select all / none"
_STORAGE_SECRET = "dnd-rtt-app"  # signs the per-browser session cookie that keys app.storage.user
# Under NiceGUI's in-process User test simulation, app.storage.user is file-backed: writing
# it on every render both litters the tree and races the harness's teardown file-cleanup on
# Windows. The tests re-import this module per case, so a module-level dict gives the same
# survives-a-refresh persistence, isolated per test, with no file I/O. Production is unaffected.
_MEMORY_STORE: dict = {}


def _doc_store() -> dict:
    """Where the serialized document is persisted: the per-browser ``app.storage.user`` in
    production, an in-process dict under the test simulation (see :data:`_MEMORY_STORE`)."""
    return _MEMORY_STORE if helpers.is_user_simulation() else app.storage.user

# the toast shown when an edit would make a degenerate (improper) temperament — dependent
# generators, or a prime tempered to a unison (see service.is_proper_temperament)
_INVALID_TEMPERAMENT = "Not a valid temperament: the generators must be independent and every prime reached."

# the toasts shown when an edited projection P / generator embedding G plain-text string parses but
# isn't a valid projection of this temperament (P must be idempotent with the commas in its kernel;
# 𝑀𝐺 must be the identity). A string that doesn't even parse just reddens the box (no toast).
_INVALID_PROJECTION = "That isn't a valid projection — 𝑃 must be idempotent (𝑃² = 𝑃) with the commas in its kernel."
_INVALID_EMBEDDING = "That isn't a valid embedding — 𝑀𝐺 must equal the identity."

# the toast shown when the "nonstandard domain" Show toggle is turned off while a nonstandard
# basis is still live — the setting can't go off until the basis is back to a standard prime limit
_NONSTANDARD_BASIS_IN_USE = (
    "Can't turn off the nonstandard domain setting while a nonstandard basis is in use — "
    "change the domain back to a standard prime limit first."
)

_SEAM = "#999"  # the thin grey rule separating the frozen title panes from the scrolling body
_PENDING_TEXT_COLOR = "color-mix(in srgb, var(--pending-color) 60%, black)"  # a draft cell's TEXT:
# the green ring (_PENDING_COLOR, imported) DARKENED toward black — single-sourced from --pending-color
# so the wash, the ring and the text are ONE green at three lightnesses (light wash / mid ring / dark
# text). Mixing with black scales every channel equally, so the hue is preserved exactly and only the
# lightness drops; the mid ring is too light to read as text on the pale wash, hence this darker shade.
# The green analogue of the changing _PREVIEW_TEXT_COLOR and going-away _PREVIEW_REMOVE_TEXT_COLOR
_PREVIEW_COLOR = "#e8c00a"  # yellow ring on a cell the in-progress edit moves (the edit-preview
# highlight) — a clear "this changed" hue, kept distinct from the red remove-preview and the green
# _PENDING_COLOR add-preview, so the three highlight hues read apart at a glance
_PREVIEW_TEXT_COLOR = "color-mix(in srgb, var(--preview-color) 60%, black)"  # the "changing" cell's
# TEXT: the yellow ring above DARKENED toward black — single-sourced from --preview-color so the wash,
# the ring and the text are ONE golden-yellow hue at three lightnesses (light wash / mid ring / dark
# text), never a mix of hues. Mixing with black scales every channel equally, so the hue is preserved
# exactly — only the lightness drops. The bright ring itself is too light to read as text on the pale
# wash, hence the dark shade. This is the changing analogue of a draft's green text (_PENDING_COLOR)
# and the going-away red text of the remove-preview (_PREVIEW_REMOVE_TEXT_COLOR)
_PREVIEW_REMOVE_COLOR = "#e53935"  # red ring on a cell a hovered +/- will REMOVE (the structural
# remove-preview) — "this is going away", paired with the yellow "this value moved"
_PREVIEW_REMOVE_TEXT_COLOR = "color-mix(in srgb, var(--preview-remove-color) 60%, black)"  # a going-
# away cell's TEXT: the red remove-ring above DARKENED toward black, single-sourced from
# --preview-remove-color so the wash, ring and text are one red at three lightnesses — the removing
# analogue of the green _PENDING_TEXT_COLOR and changing _PREVIEW_TEXT_COLOR, so a cell a hovered +/-
# will delete reads dark red (not plain black) while it is still on screen
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
# A per-tile bar chart (damage, retuning) is drawn in the same 1:1 SVG box as the EBK
# marks: a left y-axis with nice-stepped gridlines, a darker zero baseline, and one bar
# per value column aligned to the cells below. Bars rise from the zero line for positive
# values and drop from it for negative, so an all-positive chart (damage) reads from the
# bottom and a signed one (retuning) reads from a centred zero.
_CHART_PAD_T = 9  # top padding (room for the top gridline's label)
_CHART_PAD_B = 2  # bottom padding
_CHART_BAR_FRAC = 0.5  # bar width as a fraction of the column it sits in
_CHART_GRID = "#bbbbbb"  # light gridline / tick colour
_CHART_INDICATOR = "#888888"  # the minimized-damage indicator line (a solid lighter grey, labelled)
# The generator tuning-ranges chart: per-generator vertical I-beam range markers drawn
# in the same 1:1 SVG box as the EBK marks. A ranged generator is a stem with a cap at
# top (max cents) and bottom (min), labelled at the caps; a pinned generator (the period,
# octave held pure, so min == max) collapses to a single flat cap with one value.
_RANGE_CAP_W = 14  # I-beam cap width (px); the live-tuning tick is a shorter bar
_RANGE_MARK_W = 1.6  # I-beam stem + cap thickness (px) — constant at any height (1:1 viewBox)
_RANGE_PLOT_T = 11  # plot-area top (room for the top-cap label; the title is now a boxtitle above the chart)
_RANGE_PLOT_B = 12  # plot-area bottom margin (room for the bottom-cap label)
_RANGE_FONT = 7  # cents-label / placeholder font size

# Colorization wash colours, keyed by the group the layout tags a wash with
# (spreadsheet.CELL_FACTORS via _FACTOR_GROUP); a wash sits behind the grey tiles so the
# colour reads through the gaps around them. The three are the muted-channel trio — each
# dims ONE RGB channel to 0x9a — so their darken blends stay clean (tuning ⊓ temperament =
# #9acd9a, the mockup's green). cyan = tuning (the generator embedding G), khaki =
# temperament (the mapping 𝑀 / comma basis C), magenta = form (the form matrix 𝐹 — its
# wash is deferred; the palette entry feeds the greyed Show-panel swatch for now).
_TINTS = {"tuning": "#9acdcd", "temperament": "#cdcd9a", "form": "#cd9acd"}

# Dark-theme palette anchors that have to exist Python-side: the option-box indicator is a baked
# SVG data-URI (which can't read a CSS variable, so its dark variant is generated here), and
# apply_theme paints the body's margin frame inline. The full dark palette lives in
# assets/rtt-dark.css; these few values mirror it (kept in step by eye — they only set the
# checkbox art and the frame, both visible right beside the css-driven surfaces).
_DARK_FRAME = "#15171a"   # the body margin framing the whole app
_DARK_CELL = "#1b1f24"    # value-cell / input fill — and the option-box's own box
_DARK_MARK = "#8d949d"    # the cell rule, the EBK brackets, and the option-box outline
_DARK_TEXT = "#e3e6ea"    # primary text — and the checked option-box's inner fill
_DARK_MUTED = "#71777f"   # disabled text — and the indeterminate option-box's inner fill

# Every editable numeric input maps here to the amount one wheel notch nudges it: ±1 for a
# matrix/vector or power entry, ±0.001 for a complexity-prescaler weight (matching its thousandths
# display). The make_cell listener and on_value_wheel both read this one table, so a NEW numeric
# input gets scroll-to-step by adding a row here — there is no per-input wheel handler. (The
# generator-tuning cell and the target-limit square scroll through their own handlers instead: the
# first fine-tunes by 1/1000 cent with hover + grouped undo, the second debounces its costly commit.)
_WHEEL_STEPS = {
    "mapping": 1, "commacell": 1, "interestcell": 1, "heldcell": 1, "targetcell": 1,
    "powerinput": 1, "prescalercell": 0.001,
}
# The client-side gate for the integer wheel step, shared by every gridded integer input (the
# matrix/vector cells and the TILT/OLD target-limit square): only step (and swallow the scroll) when
# the input holds focus — otherwise let the event through so the grid/panel scrolls as usual. So a
# notch nudges only the input you have clicked into, and an idle scroll never fires a server round-
# trip. ``emit`` ships deltaY to that input's handler (on_value_wheel / on_target_limit_wheel).
_INT_WHEEL_JS = ("(e) => { if (e.currentTarget.contains(document.activeElement)) "
                 "{ e.preventDefault(); emit(e); } }")
# How long after the last target-limit wheel notch to run the commit. Each notch cheaply steps the
# shown number (server-side, so the loopback-controlled field actually updates), but COMMITTING a
# new limit rebuilds the whole target set, re-solves the tuning and re-renders the grid — far too
# heavy per notch (a fast scroll would queue one such solve per notch, each costlier as the set
# grows, and grind the app). So the commit is debounced by this much, mirroring the limit input's
# typing ``debounce=300``. See on_target_limit_wheel.
_TARGET_LIMIT_DEBOUNCE = 0.3


class _GridValueSpec(NamedTuple):
    """How one editable ratio-or-integer cell kind drives the shared ``_build_gridvalue`` /
    ``_update_gridvalue`` component — the unified replacement for the ~10 near-identical builders.
    ``ratio_allowed`` cells can hold a ``"num/den"`` fraction (a numerator over a denominator
    input, the ``/`` key splits a bare integer, a ``1``/blank denominator collapses back to the
    big-integer view); integer-only cells are a single field. ``commit``/``preview`` name the
    handlers on ``self._cb``; ``cid_arg`` is True when they take the cell id (the scalar ratio +
    domain-element cells, committed one at a time) and False when they re-read the WHOLE matrix /
    column and take a ``preview=`` flag (the integer matrix/vector cells). ``arm`` makes the cell a
    drag-to-combine drop target: ``("row",)`` a mapping row, ``("col", group)`` an interval column."""
    ratio_allowed: bool
    pending: bool
    commit: str
    preview: str | None
    cid_arg: bool
    arm: tuple | None = None


# Every editable ratio-or-integer kind, routed to the one shared builder/update via the registry
# (the kind strings stay — they are load-bearing in _WHEEL_STEPS, the drag predicates, tooltips and
# the cell-kind tests).
_GRIDVALUE_SPECS = {
    "ratiocell":     _GridValueSpec(True,  True,  "on_ratio_change",        None,                 True),
    # the chapter-9 domain basis elements (prime:i): an integer prime shows the big-number view, a
    # nonprime the stacked fraction, the kind following the value's shape (so an int↔fraction relabel
    # rebuilds the cell).
    "elementcell":   _GridValueSpec(True,  True,  "on_element_change",      "on_element_preview",  True),
    "elementratio":  _GridValueSpec(True,  True,  "on_element_change",      "on_element_preview",  True),
    "mapping":       _GridValueSpec(False, True,  "on_mapping_change",      "on_mapping_change",   False, ("row",)),
    "commacell":     _GridValueSpec(False, True,  "on_comma_change",        "on_comma_change",     False, ("col", "comma")),
    "unchangedcell": _GridValueSpec(False, False, "on_unchanged_change",    "on_unchanged_change", False),
    "interestcell":  _GridValueSpec(False, True,  "on_interest_change",     "on_interest_change",  False, ("col", "interest")),
    "heldcell":      _GridValueSpec(False, True,  "on_held_change",         "on_held_change",      False, ("col", "held")),
    "targetcell":    _GridValueSpec(False, True,  "on_target_cells_change", "on_target_cells_change", False, ("col", "target")),
}


def _wave_svg(kind: str) -> str:
    """A small waveform glyph (sine/square/triangle/sawtooth) for the bank's waveform control."""
    paths = {"sine": "M1,6 Q3,1 5.5,6 T11,6", "square": "M1,9 V3 H6 V9 H11 V3",
             "triangle": "M1,9 L3.5,3 L6,9 L8.5,3 L11,9", "sawtooth": "M1,9 L6,3 L6,9 L11,3 L11,9"}
    return (f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph"><path d="{paths[kind]}" '
            f'fill="none" stroke="currentColor" stroke-width="1.1"/></svg>')


def _mode_svg(filled) -> str:
    """A 3×3 grid glyph with the given (row, col) cells filled — the play-mode control."""
    rects = [f'<rect x="{1 + c * 3.7:.1f}" y="{1 + r * 3.7:.1f}" width="2.6" height="2.6" '
             f'fill="{"currentColor" if (r, c) in filled else "none"}" stroke="currentColor" '
             f'stroke-width="0.5"/>' for r in range(3) for c in range(3)]
    return f'<svg viewBox="0 0 12 12" class="rtt-audio-glyph">{"".join(rects)}</svg>'


# the four play modes' 3×3 glyphs: 1 one-off (centre), 2 arpeggiate (bottom-left→top-right
# diagonal), 3 chord (centre column), 4 rolled chord (diagonal + the bottom-right triangle)
_MODE_FILLS = (
    frozenset({(1, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2)}),
    frozenset({(0, 1), (1, 1), (2, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2), (1, 2), (2, 1), (2, 2)}),
)
# Glyph variants the bank cycles through. Generated once in Python and shared with the JS
# (injected as rttAudio.glyphs) so the click-side redraw uses the very same markup.
_AUDIO_GLYPHS = {
    "mute": ['<span class="material-icons rtt-audio-glyph">volume_up</span>',    # [0] unmuted: plain speaker
             '<span class="material-icons rtt-audio-glyph">volume_off</span>'],  # [1] muted: speaker with a slash
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(f) for f in _MODE_FILLS],
    "lock": ['<span class="material-icons rtt-audio-glyph">lock_open</span>',
             '<span class="material-icons rtt-audio-glyph">lock</span>'],
    "root": '<span class="rtt-audio-rootglyph">1/1</span>',
}

# The Web Audio engine. ONE global config (waveform, play-mode, hold/loop, include-1/1) drives
# every speaker — the single bank on the dummy tile (see _audio_bank) cycles it and redraws its
# glyphs client-side, and a speaker calls rttAudio.hit(tile, idx, [cents…]) to sound per that
# config; `tile` only picks which speakers to highlight while they ring. All CLIENT-side (no server
# round-trip). 1/1 (root) sounds UNDERNEATH as a drone. freq = 261.626·2^(¢/1200) (1/1 = middle C).
# Modes (0..3): one-off, arpeggiate from the clicked note, chord, rolled chord; hold sustains
# (mode 0 stacks notes, keyed by tile:idx) or loops (2 & 4).
_AUDIO_JS = (_ASSETS / "audio.js").read_text(encoding="utf-8")

# Frozen-pane support. The row band freezes by position:sticky (zero JS on its scroll path), but the
# column-title strip sits OUTSIDE the body scroller (so the vertical scrollbar can stop below it), so
# it can't ride the scroll via CSS — this listener translateX-syncs it to the body's horizontal
# scroll. It also reveals the seams: a frozen region is "stuck" (body scrolled under it) exactly when
# .rtt-gridbody has scrolled off zero on that axis, toggled as rtt-scrolled-x/y on .rtt-app. scroll
# doesn't bubble → capture phase, so the body's scroll events are still caught here.
_FREEZE_JS = (_ASSETS / "freeze.js").read_text(encoding="utf-8")

# Live int<->ratio mode-switching for the editable stacked fraction cells (the "/" key opens a
# denominator, a blank/1 denominator collapses to the big-integer view). Pure client-side — commits
# still happen on blur (see _build_fraction / _build_gridvalue).
_FRACTION_JS = (_ASSETS / "fraction.js").read_text(encoding="utf-8")

# A fraction cell holds TWO inputs (numerator + denominator) in one cell. This client-side guard makes
# a focus/blur/commit handler fire only when focus crosses the WHOLE cell's boundary — not on the
# num<->den Tab hop inside it — so the edit-preview baseline is taken once and the value commits only
# when you truly leave. (relatedTarget is the element focus is moving to/from.)
_FRAC_EXIT_JS = ("(e) => { const b = e.target.closest('.rtt-frac-edit'); "
                 "if (!b || !b.contains(e.relatedTarget)) emit(); }")


def _option_box_svg(fill: str | None, *, box: str = "#fff", border: str = "#555") -> str:
    """A data-URI SVG of the option-box indicator: an n×n ``box``-filled square with a 1px
    ``border`` and, when ``fill`` is given, a centred inner square (inset by the 1px border + a
    2px gap) of that colour. Used as the BACKGROUND of every q-checkbox box and the tuning-ranges
    radio box, so the whole mark scales as ONE vector — staying square with an even border at any
    zoom — instead of separate CSS box edges (border + inset fill), which the browser snaps
    independently to the device-pixel grid, distorting the square and the gap at fractional zooms.
    ``box``/``border`` default to the light theme; dark mode rebakes them (see _CSS_DARK_VARS)."""
    n = spreadsheet.OPTION_BOX_PX
    inner = f"<rect x='3' y='3' width='{n - 6}' height='{n - 6}' fill='{fill}'/>" if fill else ""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}'>"
           f"<rect x='.5' y='.5' width='{n - 1}' height='{n - 1}' fill='{box}' stroke='{border}' stroke-width='1'/>"
           f"{inner}</svg>")
    return "data:image/svg+xml," + quote(svg)


# the fan controls' glyphs, stroked centred in a 12-unit box: the +/− add/remove rules and the
# fold toggles' outward (expand) / inward (collapse) double-chevrons. Drawn in currentColor so the
# element's CSS colour (and :hover) tints them.
_CONTROL_GLYPHS = {
    "plus":     "M6 3V9M3 6H9",
    "minus":    "M3 6H9",
    "expand":   "M3.5 4.7L6 2.6L8.5 4.7M3.5 7.3L6 9.4L8.5 7.3",   # ∧ over ∨ — chevrons point OUT
    "collapse": "M3.5 2.6L6 4.7L8.5 2.6M3.5 9.4L6 7.3L8.5 9.4",   # ∨ over ∧ — chevrons point IN
}
# a fold toggle's state token (spreadsheet._fold_glyph) -> its chevron glyph: a collapsed band
# offers to expand out, an open one to collapse in.
_FOLD_GLYPH = {"unfold_more": "expand", "unfold_less": "collapse"}


def _control_svg(glyph: str) -> str:
    """An inline SVG for a fan control — the +/− add/remove buttons and the fold toggles: a white
    #bbb-bordered square with a centred glyph (a + or − rule, or the expand/collapse double-chevron)
    stroked in currentColor, so the element's CSS colour (and :hover) tints the glyph while the
    white box stays put against the grey fan. One coherent vector like the option-box checkbox, so
    box and glyph stay square and centred at ANY zoom — unlike a font glyph or a CSS-bordered button,
    whose edges the browser snaps to the device-pixel grid independently and drifts off-centre."""
    return (f"<svg viewBox='0 0 12 12' xmlns='http://www.w3.org/2000/svg'>"
            f"<rect x='.5' y='.5' width='11' height='11' fill='#fff' stroke='#bbb' stroke-width='1'/>"
            f"<path d='{_CONTROL_GLYPHS[glyph]}' fill='none' stroke='currentColor' stroke-width='1.2'"
            f" stroke-linecap='round' stroke-linejoin='round'/></svg>")


_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --tab-w:{_TAB_W}px; --tab-h:{_TAB_H}px; --chrome-h:{_CHROME_H}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --pending-color:{_PENDING_COLOR}; --pending-text-color:{_PENDING_TEXT_COLOR}; --preview-color:{_PREVIEW_COLOR}; --preview-text-color:{_PREVIEW_TEXT_COLOR}; --preview-remove-color:{_PREVIEW_REMOVE_COLOR}; --preview-remove-text-color:{_PREVIEW_REMOVE_TEXT_COLOR};
  --c-gridline:#e0e0e0;
  --wash-base:#fff; --wash-tuning:{_TINTS['tuning']}; --wash-temperament:{_TINTS['temperament']}; --wash-form:{_TINTS['form']};
  --cell-border-w:{_CELL_BORDER_W}px; --cell-border:{_CELL_BORDER}; --cell-font:{_CELL_FONT}px;
  --label-w:{spreadsheet.LABEL_W}px; --header-h:{spreadsheet.HEADER_H}px; --line-w:{spreadsheet.LINE_W}px;
  --ptext-edit-h:{spreadsheet.PTEXT_EDIT_H}px; --option-box:{spreadsheet.OPTION_BOX_PX}px; --btn:{spreadsheet.BTN}px;
  --option-box-unchecked:url("{_option_box_svg(None)}");
  --option-box-checked:url("{_option_box_svg('#000')}");
  --option-box-disabled:url("{_option_box_svg('#888')}");
}}
"""

# The bulk stylesheet lives in assets/rtt.css; it references the CSS custom properties above,
# which _CSS_VARS feeds the Python-side constants (sizes, colours, the option-box SVG data URIs).
#
# Dark theme: a palette overlay in assets/rtt-dark.css, gated on the `rtt-dark` body class (the
# settings drawer's toggle — see apply_theme), so it stays inert in the default light render. Its
# checkbox art can't ride a CSS variable (a data-URI is opaque to the cascade), so the dark
# option-box SVGs are rebaked here onto the --option-box-* properties under body.rtt-dark.
_CSS_DARK_VARS = f"""body.rtt-dark {{
  --option-box-unchecked:url("{_option_box_svg(None, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-checked:url("{_option_box_svg(_DARK_TEXT, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-disabled:url("{_option_box_svg(_DARK_MUTED, box=_DARK_CELL, border=_DARK_MARK)}");
}}
"""
_CSS = (_CSS_VARS + (_ASSETS / "rtt.css").read_text(encoding="utf-8")
        + _CSS_DARK_VARS + (_ASSETS / "rtt-dark.css").read_text(encoding="utf-8"))


# Which sticky band a cell renders into — decided by WHERE its top-left corner falls, not by
# its kind. The column titles + fold toggles AND the column branching (each column's trunk +
# fan-out bus and the ± controls riding it) sit above freeze_y, so they ride the column strip
# (sticky to the window top); the row titles/toggles AND the row branching (each matrix row's
# trunk + left bus and its ± controls) sit left of freeze_x, so they ride the row band (sticky
# to the left); the master toggle, in the corner of both, rides the corner. Everything past both
# seams — the value cells and their grey tiles — scrolls on the body board. Routing by position
# (rather than a hand-kept kind→band map) lets the column + and the basis + — which share the
# kind "plus" but freeze in DIFFERENT bands — each land correctly, and a new control freezes for
# free.
def _freeze_container(cb, fx: float, fy: float) -> str:
    if cb.x < fx and cb.y < fy:
        return "corner"
    if cb.y < fy:
        return "col"
    if cb.x < fx:
        return "row"
    return "body"

# Which panes a BLOCK renders into. Unlike a cell — small enough that its top-left corner picks one
# band — a colorization wash overhangs its tile by WASH_PAD-PAD (so adjacent washes meet across the
# gap), so the top-row / left-column washes spill PAST the freeze seam. A wash rendered only into the
# body is then shaved at those edges: the column strip clips the spill above freeze_y (the body
# scroller stops at the seam) and the row band paints over the spill left of freeze_x. So a wash, like
# a gridline crossing the seam, renders into the body PLUS every frozen pane its rect reaches — each
# copy clipped to its pane, meeting the body copy continuously so the colour fills the inter-title gap
# at the top/left edges too. Grey tiles and bordered boxes sit inside both seams, so they get "body"
# alone and stay single-pane. The frozen copies hide once the body scrolls on that axis (see rtt.css).
def _block_panes(bl, fx: float, fy: float) -> tuple[str, ...]:
    panes = ["body"]
    if bl.y < fy:
        panes.append("col")
    if bl.x < fx:
        panes.append("row")
    if bl.x < fx and bl.y < fy:
        panes.append("corner")
    return tuple(panes)

# A math-expression cell stacks 1–2 lines ("1200 · log₂(3/2)" over "= 701.96") in a
# narrow value square, so each line's font is scaled down to fit the cell width.
_EXPR_MAX_FONT = 9.0  # px — short lines (a bare prime map) sit at the comfortable size
_EXPR_MIN_FONT = 3.5  # px — the floor for the longest target-ratio expressions
_EXPR_CHAR_W = 0.5  # a glyph's width as a fraction of font size (serif average), for the fit


def _fit_font(line: str, width: float, max_font: float = _EXPR_MAX_FONT,
              min_font: float = _EXPR_MIN_FONT, char_w: float = _EXPR_CHAR_W) -> float:
    """Largest font (capped at ``max_font``, floored at ``min_font``) at which ``line``
    fits ``width`` px on one line. Shared by the math-expression cells and the
    plain-text value boxes (which pass their own bounds)."""
    if not line:
        return max_font
    fit = (width - 2) / (len(line) * char_w)
    return max(min_font, min(max_font, fit))


def _mathexpr_html(text: str, width: float) -> str:
    """The stacked HTML for a math-expression cell: each newline-separated line on
    its own row, its font shrunk to fit the cell so long expressions stay in-bounds."""
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{line}</div>'
        for line in text.split("\n")
    )
    return f'<div class="rtt-mathexpr-stack">{lines}</div>'


# the units labels (the domain-units column/row and the per-box "units:" line) and the per-value
# unit overlay shrink to fit their cell, like the math-expression cells — so a long annotated unit
# (¢(E-sopfr-S)/, (E-sopfr-C)) fits its narrow COL_W spine instead of spilling the tile.
_UNITS_MAX_FONT = 10.0    # px — the comfortable units-label size (matches .rtt-units in rtt.css)
_CELLUNIT_MAX_FONT = 6.0  # px — the per-value unit overlay (matches .rtt-cellunit)
_MATLABEL_FONT = 11.0     # px — the default column/row matrix-label size (matches .rtt-matlabel)
_MATLABEL_MIN_FONT = 6.0  # px — floor for a wide column header shrunk to fit its COL_W slot


def _units_font(text: str, width: float, max_font: float) -> float:
    """Font (px) at which a unit label fits ``width`` on one line, so a long annotated unit
    shrinks to its cell rather than spilling. Reuses the math-expression fit; the 0.5 char-width
    estimate overshoots the units sans (Corbel ≈0.42 em), so the chosen size never spills."""
    return _fit_font(text, width, max_font=max_font)

# Every EBK mark is drawn by hand as an SVG sized to the cell. The viewBox is the
# cell's own px box (0 0 w h), so one viewBox unit == one px: a stroke we declare
# as N px renders exactly N px wide regardless of how tall/long the mark spans.
# This is the single rule that keeps the brackets and brace a constant weight —
# the rejected font glyph scaled its weight with its height, and a fixed viewBox
# stretched to the cell sheared its serifs. Square/top brackets are crisp filled
# rects; the calligraphic ⟨ and brace are filled variable-width ribbons (_ribbon).
_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "hbar"}


def _chart_ticks(lo, hi):
    """Nice round tick values enclosing ``[lo, hi]``: rounded down to a tick at/below
    ``lo`` and up to the first tick strictly *above* ``hi`` (~4-5 steps). A chart scaled
    to span the returned ticks therefore always shows a gridline past its tallest bar."""
    span = hi - lo
    if span <= 0:
        return [lo, lo + 1.0]  # flat data (e.g. all-equal values): a unit axis around it
    raw = span / 4
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if raw <= m * mag)
    stop = (math.floor(hi / step) + 1) * step  # first tick strictly above the top value
    ticks, v = [], math.floor(lo / step) * step
    while v <= stop + step * 1e-9:
        ticks.append(round(v, 6))
        v += step
    if ticks[-1] == ticks[0]:  # a sub-precision span (floating-point dust ~1e-13, e.g. a
        return [ticks[0], ticks[0] + 1.0]  # "made to vanish" retuning) rounded to one value:
    return ticks                           # numerically flat, so scale it flat as for span<=0


def _bar_chart(w, h, values, indicator=None, indicator_label=""):
    """A bar chart filling its 1:1 px box: one bar per value, aligned to the value
    columns below, rising/falling from a zero baseline; gridlines mark nice ticks. When
    ``indicator`` is set (the optimization mean damage ⟪𝐝⟫ₚ on the damage chart), a solid
    lighter-grey line marks that minimized-damage level across the plot, broken by a
    ⟪𝐝⟫ label whose subscript is ``indicator_label`` (the scheme's Lp power ∞ / 2 / 1)."""
    axis_x, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    values = tuple(values)
    present = tuple(v for v in values if v is not None)  # a DASHED (None) cell — an unknown size the
    # under-held tuning doesn't pin (a dashed unchanged column of V) — gets no bar and no axis weight
    ticks = _chart_ticks(min(present + (0.0,)), max(present + (0.0,)))  # 0 in range: baseline shows
    axis_lo, axis_hi = ticks[0], ticks[-1]  # the axis spans the ticks, so the top one clears the bars
    plot_top, plot_bot = _CHART_PAD_T, h - _CHART_PAD_B
    span = axis_hi - axis_lo

    def y_of(v):
        return plot_top + (axis_hi - v) / span * (plot_bot - plot_top)

    body = []
    for tv in ticks:
        ty = y_of(tv)
        body.append(f'<line x1="{axis_x:.2f}" y1="{ty:.2f}" x2="{w:.2f}" y2="{ty:.2f}" '
                    f'stroke="{_CHART_GRID}" stroke-width="0.5"/>')
        body.append(f'<text x="{axis_x - 2:.2f}" y="{ty + 2.4:.2f}" text-anchor="end" '
                    f'font-size="7" fill="{_BR_COLOR}">{tv:g}</text>')
    zero_y = y_of(0)
    body.append(f'<line x1="{axis_x:.2f}" y1="{zero_y:.2f}" x2="{w:.2f}" y2="{zero_y:.2f}" '
                f'stroke="{_BR_COLOR}" stroke-width="1"/>')
    body.append(_rect(axis_x, plot_top, 0.8, plot_bot - plot_top))  # vertical y-axis
    bw = col_w * _CHART_BAR_FRAC
    for i, v in enumerate(values):
        if v is None:  # a dashed cell has no bar
            continue
        cx = axis_x + i * col_w + col_w / 2
        yv = y_of(v)
        top, bot = min(zero_y, yv), max(zero_y, yv)
        body.append(_rect(cx - bw / 2, top, bw, bot - top))
    if indicator is not None:  # the minimized-damage level: a solid lighter-grey line BROKEN
        # by its ⟪𝐝⟫ label (a short stub from the axis, then the label in a gap, then the
        # rest of the rule), the scheme's Lp power as the label's subscript
        iy = y_of(indicator)
        lbl_font, sub_font, stub = 9, 6, 8
        # estimate the label's width so the rule gaps just around it (⟪𝐝⟫ + the subscript)
        lbl_w = 3 * lbl_font * 0.62 + len(indicator_label) * sub_font * 0.62 + 3
        lx = axis_x + stub
        body.append(f'<line x1="{axis_x:.2f}" y1="{iy:.2f}" x2="{lx - 2:.2f}" y2="{iy:.2f}" '
                    f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>')
        body.append(f'<line x1="{lx + lbl_w + 2:.2f}" y1="{iy:.2f}" x2="{w:.2f}" y2="{iy:.2f}" '
                    f'stroke="{_CHART_INDICATOR}" stroke-width="1.5"/>')
        sub = (f'<tspan font-size="{sub_font}" dy="2">{_escape(indicator_label)}</tspan>'
               if indicator_label else "")
        body.append(f'<text x="{lx:.2f}" y="{iy + lbl_font * 0.34:.2f}" font-size="{lbl_font}" '
                    f'fill="{_CHART_INDICATOR}"><tspan>⟪</tspan>'
                    f'<tspan font-weight="bold">d</tspan><tspan>⟫</tspan>{sub}</text>')
    return _svg(w, h, "".join(body))


def _range_chart(w, h, ranges, tunings=()):
    """The generator tuning-ranges chart filling its 1:1 px box: one vertical I-beam per
    generator showing its [min, max] tuning in cents (max at the top cap, min at the
    bottom), with a shorter tick marking where the live tuning falls within that range. A
    pinned generator (min == max) draws a single flat cap; empty ``ranges`` draws a 'no
    range' placeholder. The 'tuning ranges' title is a boxtitle above the chart, not in the SVG."""
    cx0, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    if not ranges:
        return _svg(w, h, f'<text x="{w / 2:.2f}" y="{h / 2 + 2:.2f}" text-anchor="middle" '
                    f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">no range</text>')
    plot_top, plot_bot = _RANGE_PLOT_T, h - _RANGE_PLOT_B
    mid, hw = (plot_top + plot_bot) / 2, _RANGE_MARK_W / 2
    cap_half, tick_half = _RANGE_CAP_W / 2, _RANGE_CAP_W / 2 - 3  # the live-tuning tick is shorter

    def bar(cx, y, half):
        return _rect(cx - half, y - hw, 2 * half, _RANGE_MARK_W)

    def label(cx, y, v):
        return (f'<text x="{cx:.2f}" y="{y:.2f}" text-anchor="middle" '
                f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">{strip_negative_zero(f"{v:.3f}")}</text>')

    body = []
    for i, (lo, hi) in enumerate(ranges):
        cx = cx0 + i * col_w + col_w / 2
        if hi - lo < 1e-6:  # pinned (e.g. the period): one value, no range — a single cap
            body.append(bar(cx, mid, cap_half) + label(cx, mid - 4, lo))
            continue
        # a vertical stem capped at the max (top) and min (bottom), labelled at each
        body.append(_rect(cx - hw, plot_top, _RANGE_MARK_W, plot_bot - plot_top))
        body.append(bar(cx, plot_top, cap_half) + bar(cx, plot_bot, cap_half))
        body.append(label(cx, plot_top - 4, hi) + label(cx, plot_bot + 9, lo))
        if i < len(tunings):  # the live tuning, ticked where it falls within [min, max]
            frac = min(1.0, max(0.0, (hi - tunings[i]) / (hi - lo)))
            body.append(bar(cx, plot_top + frac * (plot_bot - plot_top), tick_half))
    return _svg(w, h, "".join(body))


def _parse_int(text):
    """``text`` -> int, or None for blank/partial input (matching the old parseInt)."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _wheel_step(value, delta_y, step=1) -> str:
    """One wheel notch on a numeric input's text value: scroll up (``delta_y`` < 0) adds ``step``,
    down subtracts it. A blank/partial value starts from 0; ``∞`` (the max-norm power) is left
    unchanged — a wheel can't reach it, you type it. An int ``step`` formats a bare integer
    (``2`` → ``3``); a fractional one keeps its own decimal precision (``0.001``: ``1.585`` →
    ``1.586``), so the stepped text reads like the cell already does. The one step shared by every
    gridded numeric input (and the target-limit square)."""
    text = str(value).strip()
    try:
        cur = float(text.replace("∞", "inf"))
    except ValueError:
        cur = 0.0  # blank / partial component starts from 0
    if not math.isfinite(cur):
        return text  # ∞ / inf: leave it; the wheel can't step the max-norm power
    new = cur + (step if delta_y < 0 else -step)
    if isinstance(step, int):
        return str(int(new)) if new == int(new) else str(new)
    decimals = max(0, -math.floor(math.log10(step)))
    return strip_negative_zero(f"{round(new, decimals):.{decimals}f}")


def _limit_text(limit) -> str | None:
    """The target-limit field's text for a resolved limit: the number as a string, or None
    (the "-" placeholder) when there is no limit to show (a typed override / all-interval)."""
    return None if limit is None else str(limit)


def _ratio_parts(text):
    """Split a ratio like ``"3/2"`` into ``("3", "2")``; None if it isn't a fraction."""
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text):
    """Split a cents value like ``"1899.260"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _approach_visible(editor) -> bool:
    """Whether the chapter-9 nonstandard-domain-approach radio (prime-based / nonprime-based /
    neutral) should render — True iff the loaded domain basis carries any element that isn't a
    prime int (e.g. 13/5 in 2.3.13/5). On a pure-prime basis the trait is meaningless, so the
    radio stays hidden, mirroring the maximized mockup's blue-text gating."""
    return service.domain_has_nonprimes(editor.state.domain_basis)


def _gentuning_parts(text):
    """Split a generator-tuning cents value into ``(sign, whole, frac)`` for the genmap's
    clickable signed face: a non-negative value carries an explicit ``"+"`` (ordinarily
    assumed), a negative one a ``"−"`` with the bare magnitude; blank text (quantities off)
    carries no sign. The sign glyph is the part the user clicks to flip the generator."""
    if not text:
        return "", "", ""
    sign, body = ("−", text[1:]) if text.startswith("-") else ("+", text)
    whole, frac = _cents_parts(body)
    return sign, whole, frac


def _power_parts(text):
    """Split an optimization/norm power into a stacked face: ``∞`` carries a small ``"(max)"``
    below it (it IS the max-norm / minimax power), the way a cents value carries its decimal;
    a numeric power (``2``, ``1``) shows bare, with no annotation."""
    return (text, "(max)") if text == "∞" else (text, "")


# Per-glyph widths (in em — font-size multiples) for the .rtt-ptext face, used to estimate a
# plain-text value's width without a browser. An EBK string mixes wide digits with narrow
# punctuation and spaces, so a single average char width over-shrinks a punctuation-heavy
# value (e.g. a prescaling ket-matrix, mostly 0s, dots and spaces); summing the real glyphs
# lets each value fill its box. These are Cambria em-widths rounded up with a ~5% margin, so
# the estimate never falls short of the render and the value never spills. 0.59 (the widest
# glyph, a digit) is the fallback for any character not listed.
_PTEXT_DEFAULT_EM = 0.59
_PTEXT_GLYPH_EM = {
    **{d: 0.59 for d in "0123456789"},
    ".": 0.22, "-": 0.35, "/": 0.52, " ": 0.24,
    "[": 0.37, "]": 0.37, "{": 0.41, "}": 0.41, "⟨": 0.38, "⟩": 0.38,
}


def _ptext_units(text):
    """``text``'s width in em (font-size multiples), summed from the real per-glyph widths —
    so a punctuation-heavy value is estimated narrower than a digit-dense one of the same
    length, and each sizes to fill its box."""
    return sum(_PTEXT_GLYPH_EM.get(c, _PTEXT_DEFAULT_EM) for c in text)


def _ptext_font(text, width):
    """The largest font (px, capped at PTEXT_MAX_FONT) at which ``text`` fits on ONE line
    within a ``width``-px box. The plain-text contract is fit-on-one-line, so there is NO
    readability floor: a dense value (a prescaling ket-matrix at a high prime limit) keeps
    shrinking until it fits rather than spilling, and a short one grows to the cap. Width is
    estimated per glyph (_ptext_units) rather than by a uniform char width, so punctuation-
    heavy strings use the room they actually have. Truncated (not rounded) to 0.1px so the
    chosen size never rounds back up past the fit and spills."""
    units = _ptext_units(text)
    fit = (width - 2) / units if units else spreadsheet.PTEXT_MAX_FONT
    return int(min(spreadsheet.PTEXT_MAX_FONT, fit) * 10) / 10


_RATIO_MAX_FONT = 13.0  # px — the comfortable stacked-fraction size (matches .rtt-ratio in rtt.css)
_RATIO_DIGIT_EM = _PTEXT_GLYPH_EM["0"]  # a digit's width in em (the ptext estimate; fraction lines are all digits)
_RATIO_PAD = 6.0  # px — the .rtt-frac-num/.rtt-frac-den left+right padding (3px a side, the bar's overhang),
                  # fixed regardless of font, so it is reserved before the digits get the rest of the cell


def _digit_fit_font(longest, width, max_font):
    """The largest font (px, capped at ``max_font``) at which ``longest`` digits plus the fixed
    fraction-bar padding fit a ``width``-px square. Truncated (not rounded) to 0.1px so the chosen
    size never rounds back up and spills; like ``_ptext_font`` there is no readability floor — the
    cell is a hard boundary. Shared by the stacked-fraction face (capped at the comfortable ratio
    size) and the big-integer view (capped at the value-cell font)."""
    if not longest:
        return max_font
    fit = (width - _RATIO_PAD) / (longest * _RATIO_DIGIT_EM)
    return int(min(max_font, fit) * 10) / 10


def _ratio_font(num, den, width):
    """The largest font (px, capped at ``_RATIO_MAX_FONT``) at which a stacked fraction's longer
    line fits its ``width``-px square. A long numerator or denominator (e.g. 65536 = the target
    2/1 re-vectored to [16 0 0⟩) spills the 30px cell at the comfortable size, so the whole
    fraction shrinks to fit — num and den share the size, as a fraction should."""
    return _digit_fit_font(max(len(num), len(den)), width, _RATIO_MAX_FONT)


_DESCENDERS = "gjpqy"  # letters whose tail dips below the baseline


def _underline_html(text, spans):
    """``text`` with each ``(start, len)`` span wrapped in ``<u>`` — the mnemonic
    underline marking a caption's symbol letter. All text is HTML-escaped. A span
    holding a descender (g/j/p/q/y) is tagged ``rtt-desc`` so only its underline is
    dropped below the tail; the rest keep the normal snug underline."""
    out, i = [], 0
    for start, length in sorted(spans):
        seg = text[start:start + length]
        tag = '<u class="rtt-desc">' if any(c in _DESCENDERS for c in seg) else "<u>"
        out.append(_escape(text[i:start]) + tag + _escape(seg) + "</u>")
        i = start + length
    out.append(_escape(text[i:]))
    return "".join(out)


# The "example" column of the Show panel's "specific boxes & controls" group: one illustrative
# sample per toggle, read from the mockup's Show legend. Most are a glyph or short string (the
# maps' bold-italic letters, the vectors/matrices' bold-upright ones, the plain captions); a few
# (the colorization swatch, the audio speaker, the tuning-ranges I-beam) are graphical, built in
# _example_html. The "general" group is no longer a checkbox column with samples — it is the
# clickable dummy tile, which carries its own sample content (see the _TILE_* block below) — so
# this table holds only the specific-group keys.
_EXAMPLE_TEXT: dict[str, str] = {
    "counts": "𝑑",
    "domain_quantities": "2.3.5",
    "domain_units": "p₁/",
    "temperament_boxes": "𝑀",
    "form_controls": "canonical form",
    "tuning_boxes": "T",
    "optimization": "𝑝",
    "weighting": "𝒘",
    "all_interval": "minimax-S",
    "alt_complexity": "E-lp",
    "projection": "𝑃",
    "interest": "𝐢",
    "generator_detempering": "D",
    "nonstandard_domain": "Bₗ",
    "identity_objects": "𝑀ⱼ",
}


def _example_chart() -> str:
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with grey horizontal
    gridlines (the chart's tick lines) and a bar dipping below the zero line, as the mockup's
    legend shows. Bars + axes ride _BR_COLOR and the gridlines _CHART_GRID — the same tokens the
    real chart and the EBK frame use — so the dark overlay's [fill]/[stroke] rules retint them."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            # grey horizontal tick lines at the ±5 levels (the chart's gridlines)
            f'<line x1="2" y1="5" x2="64" y2="5" stroke="{_CHART_GRID}" stroke-width="1"/>'
            f'<line x1="2" y1="29" x2="64" y2="29" stroke="{_CHART_GRID}" stroke-width="1"/>'
            f'<line x1="2" y1="3" x2="2" y2="31" stroke="{_BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="0" y1="5" x2="6" y2="5" stroke="{_BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="0" y1="29" x2="6" y2="29" stroke="{_BR_COLOR}" stroke-width="1.4"/>'
            f'<line x1="2" y1="17" x2="62" y2="17" stroke="{_BR_COLOR}" stroke-width="1"/>'
            f'<rect x="16" y="17" width="22" height="6" fill="{_BR_COLOR}"/>'
            '</svg></div>')


def _example_html(key: str) -> str:
    """The example-column sample for one "specific boxes & controls" toggle, as an HTML string.
    (The "general" group is no longer a checkbox column — it is the clickable dummy tile, which
    renders its own samples; see _general_part_html.)"""
    if key in ("temperament_colorization", "tuning_colorization", "form_colorization"):
        # a swatch of the actual wash colour (one source of truth with _TINTS), stamped with
        # the fundamental matrix that drives it: 𝑀 (mapping), 𝐺 (generator embedding), 𝐹 (form)
        group = key.split("_")[0]
        letter = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}[group]
        return (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:36px;height:14px;background:var(--wash-{group})">{_math_html(letter)}</span>')
    if key == "tuning_ranges":  # the tuning-range I-beam (min/max generator bars)
        return ('<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
                '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
                '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
                '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>')
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


# --- the "general" Show group's dummy tile ---------------------------------------------------
# The general layers render as ONE clickable dummy value tile (the alternative to a checkbox
# column), laid out as a real tile reads: the boxed value cell on top — with its closed form and
# value INSIDE the box, the way they appear on a tile rather than as rows of their own — then the
# symbol, the name, units, the plain-text value, the presets chooser, and a chart. Each part is a
# dummy sample shown black when its layer is shown and grey when hidden; clicking it flips the
# layer in the live grid. The tile carries its OWN sample content (below); the specific group's
# example column still uses _example_html / _EXAMPLE_TEXT.
_TILE_NAME = "tile name"        # the name caption; its symbol-spelling letter (the n of "name") underlines for mnemonics
_TILE_SYMBOL = "𝒏"              # the quantity symbol — a bold-italic n, matching the underlined letter
_TILE_EQUIV = " = 𝑒G"          # the symbol's defining-equation tail (𝒏 = 𝑒G — mixed object styling: italic scalar, upright matrix)
_TILE_ROWLABEL = "𝒏₁"           # the matrix's row header (a matlabel) — rides the symbol layer, like real row labels
_TILE_MATH = "1200·log₂(3/2) ="  # math_expressions: a value's closed form; the "=" belongs to the EXPRESSION, not the value
_TILE_VALUE = "701.96"          # quantities: the bare value the form evaluates to (no "=" — that rides the expression)
_TILE_UNITS = "¢/p"             # units: the value's unit (cents per prime) — the "units: …" line AND the per-cell unit
_TILE_PTEXT = "⟨1200 1902 2786]"  # plain_text_values: the same kind of value as a one-line EBK string

_TILE_MNEMONIC_AT = _TILE_NAME.index("n")  # where the mnemonic underline falls (the symbol's letter)

# The tile's stacked lines, top to bottom, by their PRIMARY layer keys (left-to-right render
# order). The value cell additionally shows the symbol layer's row header and the units layer's
# per-cell unit (secondary appearances, added in the builder), and seats math_expressions /
# quantities INSIDE its box rather than on rows of their own. The symbol line seats the symbol +
# its equivalence tail; the name line the mnemonic letter + the rest of the name.
_GENERAL_TILE_LINES: tuple[tuple[str, ...], ...] = (
    # the drag-to-combine grip rides the value line, in a slot to the LEFT of the row label —
    # mirroring where the real handle sits in the grid (left of the 𝒎ᵢ label).
    ("drag_to_combine", "gridded_values", "math_expressions", "quantities"),
    ("symbols", "equivalences"),
    ("mnemonics", "names"),
    ("units",),
    ("plain_text_values",),
    ("presets",),
    ("charts",),
)

# A tile part that renders INSIDE another's cell is inert (greyed, unclickable) until that host
# cell is shown — the dummy mirrors the grid, where the value and its closed form have nowhere to
# sit without the boxed cell. (The refinement layers — equivalences, mnemonics — are NOT here:
# they stay live and instead pull their base layer on when selected; see SUBCONTROLS / set_show.)
_TILE_HOST: dict[str, str] = {
    "quantities": "gridded_values",
    "math_expressions": "gridded_values",
}

# Per-layer font size in the tile (px), matched to the real tile constants so the dummy's
# proportions read like an actual tile: the symbol/equivalence glyph, the name caption, the row
# header (matlabel), the units line, and the per-cell unit (6px grey, like .rtt-cellunit). The
# closed form and value inside the cell are font-FITTED to the COL_W square (see the builder), so
# they aren't listed here.
_TILE_FONT = {
    "symbols": 15, "equivalences": 15, "rowlabel": spreadsheet.MATLABEL_H - 2,
    "names": spreadsheet.CAPTION_FONT, "mnemonics": spreadsheet.CAPTION_FONT,
    "units": 10, "cellunit": 6, "plain_text_values": 11, "drag_to_combine": 18,
}


def _tile_name_pieces() -> tuple[str, str, str]:
    """The name caption split at its mnemonic letter — (before, letter, after) — so the letter
    (the mnemonics target) and the rest of the word (the names target) are separate click targets
    that still read as one word. For "tile name" with the 'n' marked: ("tile ", "n", "ame")."""
    i = _TILE_MNEMONIC_AT
    return _TILE_NAME[:i], _TILE_NAME[i], _TILE_NAME[i + 1:]


def _tile_fold_html() -> str:
    """The decorative fold toggle for the tile's top-left corner — the same boxed double-chevron
    glyph a real tile carries (open/collapse state). Inert here; it only makes the tile read as a tile."""
    return _control_svg(_FOLD_GLYPH["unfold_less"])


# The audio control bank — the single, global home for the shared playback config (window.rttAudio).
# It sits in the dummy tile's head strip opposite the fold toggle. (ctrl, initial glyph, engine fn)
# left-to-right: mute, waveform, play-mode, hold/loop, include-1/1. Mute LEADS and doubles as the
# kill switch: it stops everything sounding and gates whether a clicked cell can play at all. Audio
# starts MUTED, so mute's initial glyph is the slashed one (index 1); the rest start at index 0.
_AUDIO_BANK = (
    ("mute", _AUDIO_GLYPHS["mute"][1], "toggleMute"),
    ("wave", _AUDIO_GLYPHS["wave"][0], "cycleWave"),
    ("mode", _AUDIO_GLYPHS["mode"][0], "cycleMode"),
    ("hold", _AUDIO_GLYPHS["lock"][0], "toggleHold"),
    ("root", _AUDIO_GLYPHS["root"], "toggleRoot"),
)


def _audio_bank() -> "ui.element":
    """Build the dummy tile's audio control bank — the five glyph controls (mute leads), each wired to
    the global Web Audio engine (it cycles its state + redraws its glyph with no server round-trip).
    The bank is always live now: mute is itself the on/off gate, so there is no greyed state."""
    bank = ui.element("div").classes("rtt-tile-bank").mark("audiobank")
    with bank:
        for ctrl, glyph, fn in _AUDIO_BANK:
            ui.html(glyph).classes("rtt-audio-ctrl").mark(f"audioctrl:{ctrl}") \
                .props(f'data-actrl="{ctrl}"') \
                .on("click", js_handler=f"() => window.rttAudio.{fn}()") \
                .tooltip(tooltips.AUDIO_HELP[ctrl])
    return bank


# The value cell's geometry (px), built to read like the real mapping tile's NESTED EBK: an INNER
# per-row covector ⟨ … ] HUGGING the COL_W×ROW_H square cell (the angle/square marks sit right
# against the box, ~_BR_INSET≈2.5px off, exactly as the grid's per-row brackets do), enclosed by an
# OUTER frame — a top bracket + brace that SPAN the inner brackets and sit _TILE_ENCLOSE px above /
# below the cell. (Earlier rounds wrongly pushed the brackets far horizontally; the real app hugs.)
_TILE_CELL = spreadsheet.COL_W           # the square cell side (== ROW_H)
_TILE_BR_W = 9                            # inner ⟨ / ] bracket width — hugs the cell (no gap)
_TILE_ENCLOSE = 5                         # gap between the OUTER top/brace and the cell (the enclosing space)
_TILE_CAP = 5                             # outer top-bracket / brace height
_TILE_FRAME_W = _TILE_BR_W + _TILE_CELL + _TILE_BR_W            # the outer top/brace span ⟨ … ]
_TILE_FRAME_H = _TILE_CAP + _TILE_ENCLOSE + _TILE_CELL + _TILE_ENCLOSE + _TILE_CAP
_TILE_CELL_X = _TILE_BR_W                 # the cell's left edge within the frame (right after the inner ⟨)
_TILE_CELL_Y = _TILE_CAP + _TILE_ENCLOSE  # the cell's top edge within the frame (below the outer top)


def _tile_grid_frame_html() -> str:
    """The value cell's NESTED EBK, like the mapping tile: an inner covector ⟨ … ] hugging the
    COL_W×ROW_H white box, enclosed by an outer top bracket + brace that span the inner brackets and
    sit _TILE_ENCLOSE above / below the cell. The builder lays the closed form and value in the box."""
    def mark(x, y, w, h, inner):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">{inner}</div>'
    cell, cap, bw, cx, cy = _TILE_CELL, _TILE_CAP, _TILE_BR_W, _TILE_CELL_X, _TILE_CELL_Y
    span = _TILE_FRAME_W  # the outer top/brace run the full ⟨ … ] width
    return (f'<div style="position:relative;width:{_TILE_FRAME_W}px;height:{_TILE_FRAME_H}px">'
            # OUTER frame: top bracket + brace spanning the inner brackets, enclosing from above/below
            + mark(0, 0, span, cap, _top_bracket(span, cap))
            + mark(0, _TILE_FRAME_H - cap, span, cap, _brace(span, cap))
            # INNER covector ⟨ … ] hugging the value box
            + mark(0, cy, bw, cell, _angle_bracket(bw, cell))
            + mark(cx, cy, cell, cell, '<div style="width:100%;height:100%;box-sizing:border-box;'
                                       'border:1px solid #555;background:#fff"></div>')
            + mark(cx + cell, cy, bw, cell, _square_bracket(bw, cell, "right"))
            + '</div>')


def _tile_preset_html() -> str:
    """The presets-chooser sample, styled like the app's real q-select dropdowns: a white bordered
    field showing the "(presets)" placeholder with a dropdown caret."""
    return ('<span style="display:flex;align-items:center;justify-content:space-between;'
            'gap:4px;width:100%;height:22px;box-sizing:border-box;background:#fff;border:1px solid #999;'
            'border-radius:2px;padding:0 2px 0 6px;font-size:12px;color:#000">(presets)'
            '<span class="material-icons" style="font-size:16px;color:#555">arrow_drop_down</span></span>')


def _general_part_html(key: str) -> str:
    """The inner sample HTML for one general tile layer (every general key has one). The value
    cell's three layers split apart — gridded_values is the EBK-framed box, math_expressions the
    closed form, quantities the value (the builder stacks the form and value inside the box) — and
    the rest are a glyph, the name word, the units, the plain-text string, the presets field, or a
    chart sparkline."""
    if key == "gridded_values":
        return _tile_grid_frame_html()
    if key == "math_expressions":
        return _math_html(_TILE_MATH)
    if key == "quantities":
        return _math_html(_TILE_VALUE)
    if key == "symbols":
        return _math_html(_TILE_SYMBOL)
    if key == "equivalences":
        return _math_html(_TILE_EQUIV)
    if key == "names":
        return _escape(_TILE_NAME)
    if key == "mnemonics":
        return _escape(_tile_name_pieces()[1])
    if key == "units":
        return f'<span class="rtt-units-pre">units: </span>{_units_html(_TILE_UNITS)}'
    if key == "plain_text_values":
        return _math_html(_TILE_PTEXT)
    if key == "presets":
        return _tile_preset_html()
    if key == "charts":
        return _example_chart()
    if key == "drag_to_combine":  # a grip glyph — the drag handle this layer adds to rows and intervals
        return '<span class="material-icons" style="color:#444">drag_indicator</span>'
    raise KeyError(key)  # every general layer must have a sample


def _demath(ch):
    """A Mathematical Alphanumeric letter (or bold digit) as ``(base, bold, italic)``,
    or None for an ordinary character. Covers the bold, italic and bold-italic letter
    blocks — the maps (bold-italic), matrices/vectors (bold-upright) and the counts'
    plain italic variables — plus the bold digits (the zero list 𝟎 the held interval
    errors vanish to); other characters pass through unstyled."""
    cp = ord(ch)
    if 0x1D7CE <= cp <= 0x1D7D7:  # bold digits 𝟎–𝟗
        return chr(ord("0") + cp - 0x1D7CE), True, False
    if 0x1D400 <= cp <= 0x1D419:  # bold capitals
        return chr(ord("A") + cp - 0x1D400), True, False
    if 0x1D41A <= cp <= 0x1D433:  # bold small
        return chr(ord("a") + cp - 0x1D41A), True, False
    if 0x1D434 <= cp <= 0x1D44D:  # italic capitals
        return chr(ord("A") + cp - 0x1D434), False, True
    if 0x1D44E <= cp <= 0x1D467:  # italic small
        return chr(ord("a") + cp - 0x1D44E), False, True
    if 0x1D468 <= cp <= 0x1D481:  # bold-italic capitals
        return chr(ord("A") + cp - 0x1D468), True, True
    if 0x1D482 <= cp <= 0x1D49B:  # bold-italic small
        return chr(ord("a") + cp - 0x1D482), True, True
    return None


def _math_html(text):
    """``text`` with each Mathematical Alphanumeric letter rendered as its base
    letter in a span carrying explicit CSS weight/slant — so the UI serif draws a
    correctly bold/italic glyph rather than depending on a maths font (which font
    fallback mis-rendered). Ordinary characters pass through, HTML-escaped. The
    matlabel NORM_SUB sentinels wrap a range as italic subscript (the trailing q
    on the complexity row's ‖L𝐜ᵢ‖q). Used for the quantity symbols, their
    equivalence tails, and the matrix labels."""
    out = []
    for ch in text:
        if ch == spreadsheet.NORM_SUB_OPEN:
            out.append('<sub style="font-style:italic">')
            continue
        if ch == spreadsheet.NORM_SUB_CLOSE:
            out.append('</sub>')
            continue
        if ch == spreadsheet.SUB_OPEN:  # a plain subscript: each glyph keeps its own slant
            out.append('<sub>')          # (so "dual" stays upright while the math-italic 𝑞 slants)
            continue
        if ch == spreadsheet.SUB_CLOSE:
            out.append('</sub>')
            continue
        styled = _demath(ch)
        if styled is None:
            out.append(_escape(ch))
            continue
        base, bold, italic = styled
        css = (["font-weight:700"] if bold else []) + (["font-style:italic"] if italic else [])
        out.append(f'<span style="{";".join(css)}">{_escape(base)}</span>')
    return "".join(out)


# Within a unit value these tokens stay un-bold: the units of interval size — the cent
# sign ¢ and the spelled-out "oct" (octaves) — plus the fraction slash and spaces. The
# variable symbols (g, p, b and the placeholder 1, with subscripts) are bold —
# consistently in the per-box line AND the units row/col.
_UNIT_PLAIN = ("oct", "¢", "/", " ")


_SUB_TAGS = {
    spreadsheet.SUB_OPEN: "<sub>", spreadsheet.SUB_CLOSE: "</sub>",
    spreadsheet.NORM_SUB_OPEN: '<sub style="font-style:italic">', spreadsheet.NORM_SUB_CLOSE: "</sub>",
}


def _run_html(s):
    # a bold-able unit run, HTML-escaped, with the subscript sentinels turned into <sub>…</sub>
    # (so the superspace marker gʟ reads as g + subscript capital L, not the raw PUA chars)
    return "".join(_SUB_TAGS.get(ch) or _escape(ch) for ch in s)


def _bold_units(value):
    """A unit value with its variable symbols bold (the unit letters g/p and the
    placeholder 1, plus any subscript), leaving the units ¢ and ``oct`` and the ``/``
    separator un-bold. Bolds maximal runs of variable characters so e.g. ``g₁/`` →
    ``<b>g₁</b>/``, ``oct/p`` → ``oct/<b>p</b>``. All text HTML-escaped."""
    out, run = [], []

    def flush():
        if run:
            out.append(f"<b>{_run_html(''.join(run))}</b>")
            run.clear()

    i = 0
    while i < len(value):
        plain = next((t for t in _UNIT_PLAIN if value.startswith(t, i)), None)
        if plain is not None:
            flush()
            out.append(_escape(plain))
            i += len(plain)
        else:
            run.append(value[i])
            i += 1
    flush()
    return "".join(out)


def _units_html(text):
    """A unit label (kind ``units``). The value's face — a single-story-g sans — comes
    from the ``.rtt-units`` class; the variable symbols are bold (see :func:`_bold_units`).
    A per-box line (``units: g/p``) keeps its ``units:`` label in the serif body face; a
    bare domain-units coordinate label (``g₁/``, ``/p₁``, ``¢/``) is just the bolded value."""
    prefix = "units: "
    if text.startswith(prefix):
        return f'<span class="rtt-units-pre">{prefix}</span>{_bold_units(text[len(prefix):])}'
    return _bold_units(text)


# spacing of the dots on a folded band's gridline: a LINE_W-long dot every _DOT_PITCH px.
# CSS `border-style:dotted` packs dots ~one border-width apart (≈2*LINE_W period) and gives
# no control; painting them ourselves lets us space them out — here ≈twice as sparse.
_DOT_PITCH = 8


def _line_style(ln, y_shift: float = 0) -> str:
    """Absolute-position CSS for one gridline rule (a zero-size div carrying a single
    border). The border grows off one edge, so shift the box back by half the line width
    to seat the rule centred on its coordinate (its toggle-node / cell-column centre).
    ``y_shift`` lifts the rule into the body's scroll space (the frozen column strip's
    height), since every gridline lives on the scrolling board. A folded band's rule reads
    as dotted (a placeholder for the hidden content): the dots are painted as a repeating
    gradient showing through a TRANSPARENT border, so the box keeps its zero cross-size and
    the rule neither resizes nor shimmers as a band folds. The border colour + background
    are emitted here every update, so re-expanding restores the solid rule rather than
    leaving a stuck override -- v rules carry border-left, h rules border-top (per the CSS)."""
    half = spreadsheet.LINE_W / 2
    if ln.orientation == "v":
        pos, edge, sweep = f"left:{ln.pos - half}px; top:{ln.start - y_shift}px; height:{ln.length}px", "left", "to bottom"
    else:
        pos, edge, sweep = f"top:{ln.pos - half - y_shift}px; left:{ln.start}px; width:{ln.length}px", "top", "to right"
    if ln.dotted:
        # paint the dots over the border box (the box has no width of its own — just the
        # border), so the gradient fills the LINE_W-wide border strip rather than the
        # zero-width content box; the transparent border lets it show.
        dots = (f"repeating-linear-gradient({sweep},var(--c-gridline) 0 {spreadsheet.LINE_W}px,"
                f"transparent {spreadsheet.LINE_W}px {_DOT_PITCH}px) border-box")
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:var(--c-gridline); background:none"


def _select_props(min_width: float) -> str:
    """Shared Quasar props for every chooser dropdown (preset / target / form / control
    select): a compact borderless field whose open popup is at least as wide as its trigger
    (``min_width`` px) but grows to ``max-content``, so each entry shows on one line rather
    than wrapping or truncating at the trigger's width."""
    return ("dense options-dense borderless hide-bottom-space "
            "popup-content-class=rtt-select-popup "
            f"popup-content-style=min-width:{min_width}px;width:max-content")


# The option-hover preview's client side, shared by every q-select armed via
# _Reconciler._arm_option_hover (temperament / tuning / prescaler / complexity / weight-slope / form).
# The dropdown popup is TELEPORTED to <body>, so the slot can reach the server neither via
# `$parent.$emit` (its $parent is the menu, not the q-select that `.on()` listens on) nor via a
# `document` call in the slot expression (Vue templates block non-whitelisted globals). So the option
# slot only STAMPS each option's index (`:data-optidx`) AND its chooser's cell id (`data-optcid`) onto
# its q-item, and this one-time, document-level delegation (real JS — globals available, and it
# survives virtual scroll since it's not per-item) reads them off the hovered option and fires a native
# `opthover` CustomEvent at THAT chooser's cell wrap, which listens for it. detail -1 clears.
#
# It DEBOUNCES + dedupes: each preview is a server-side re-solve, and `mouseover` bubbles many times per
# second, so firing on every micro-move floods the socket and the client misses its heartbeat (->
# "implicit handshake failed" -> reload, which also eats clicks). So a hover only fires after the
# pointer SETTLES on an option (~90 ms), and never re-fires the same (chooser, option).
_OPTION_HOVER_DELEGATION = """
(() => {
  if (window.__rttOptHover) return;
  window.__rttOptHover = true;
  let lastCid = null, lastIdx = null, timer = null;
  const fire = (cid, d) => { if (cid === lastCid && d === lastIdx) return; lastCid = cid; lastIdx = d;
    const w = cid && document.querySelector('[data-eid="' + cid + '"]');
    if (w) w.dispatchEvent(new CustomEvent('opthover', {detail: d})); };
  const optOf = (n) => n && n.closest && n.closest('.q-item[data-optidx]');
  document.addEventListener('mouseover', (e) => {
    const it = optOf(e.target);
    if (it) { clearTimeout(timer);
      const cid = it.getAttribute('data-optcid'), idx = parseInt(it.getAttribute('data-optidx'), 10);
      timer = setTimeout(() => fire(cid, idx), 90); }
  });
  document.addEventListener('mouseout', (e) => {
    const it = optOf(e.target);
    if (it && !optOf(e.relatedTarget)) { clearTimeout(timer); fire(it.getAttribute('data-optcid'), -1); }
  });
  // A PRESS ends the hover-intent: the user is committing a pick (or dismissing the popup). Cancel any
  // pending settle-timer right now, so it can't fire AFTER the select commits. A timer armed <90 ms
  // before the click would otherwise fire once the popup has already closed, re-dispatching `opthover`
  // at the chooser. (The SERVER also drops such stale arms — popup_state marks the popup 'closed'
  // before they arrive, see _Reconciler.popup_state — so this cancel is a rate-limit nicety, not the
  // correctness mechanism.) Capture-phase so it runs before the click commits, wherever the press
  // lands. We do NOT lean on the popup-removal `mouseout` above to cancel it: a removed element under
  // the cursor does not fire mouseout reliably across browsers.
  //
  // The press ALSO resets the dedupe. A popup that closes UNDER the pointer (a pick, Escape, an
  // outside click) fires no `mouseout` for the hovered option, so lastCid/lastIdx would otherwise
  // keep that option across popup sessions — and REOPENING the chooser and hovering the SAME option
  // (the common case in a 2-4 option dropdown: you aim at the one you want) would be swallowed as a
  // duplicate, reading as "this chooser's preview is dead". Every reopen starts with a press, so
  // resetting here makes each popup session's first hover always fire.
  document.addEventListener('pointerdown', () => { clearTimeout(timer); lastCid = null; lastIdx = null; }, true);
})()
"""


# A Quasar tooltip (ui.tooltip / .tooltip()) shows on its anchor element's `mouseenter` and hides on
# the matching `mouseleave` (QTooltip.configureAnchorEl binds exactly those two on desktop). That
# leaves it stranded whenever a click REMOVES or REFLOWS the anchor before the pointer leaves it: the
# +/- buttons rebuild the grid and slide the pressed control out from under a stationary cursor, so no
# `mouseleave` ever fires and the hover help hangs on screen with nothing to dismiss it. Pressing a
# control should drop its tooltip regardless, so this one capture-phase `pointerdown` listener
# synthesizes the `mouseleave` Quasar listens for, up the ancestor chain from the pressed node —
# whichever ancestor is the anchor then hides its tooltip through Quasar's own delayHide, BEFORE the
# click round-trips and the grid reflows. It fires `mouseleave` only (never `blur`): the editable
# cells' blur-commit handlers must stay untouched, and QTooltip is hover-shown, so leave is enough.
_TOOLTIP_DISMISS_JS = """
(() => {
  if (window.__rttTipDismiss) return;
  window.__rttTipDismiss = true;
  document.addEventListener('pointerdown', (e) => {
    for (let el = e.target; el instanceof Element; el = el.parentElement) {
      el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: false}));
    }
  }, true);
})()
"""


class _GroupedSelect(ui.select):
    """A chooser whose group-divider rows are non-selectable. Each option whose value
    satisfies ``is_divider`` is handed to Quasar with ``disable=True``, so its q-item
    takes no hover highlight, can't be picked, and a click on it leaves the popup open —
    it reads purely as a section header among the selectable entries."""

    def __init__(self, options, *, is_divider, **kwargs) -> None:
        self._is_divider = is_divider
        super().__init__(options, **kwargs)

    def _update_options(self) -> None:
        # NiceGUI rebuilds the Quasar option dicts here (value/label); flag the divider
        # rows so Quasar renders them disabled. Runs on every rebuild, so it survives a
        # later set_options()/update() too.
        super()._update_options()
        for option, value in zip(self._props["options"], self._values):
            if self._is_divider(value):
                option["disable"] = True


def _set_offlist_prompt(select: ui.select, value, prompt: str = "-") -> None:
    """Show a ``prompt`` in a preset chooser's closed box when its current state matches
    no named entry (``value`` is None) — the temperament chooser with no matching preset, or
    the tuning chooser on a control-refined scheme with no name. It is a Quasar display-value
    placeholder, so it never appears as a pickable row in the open list; when a named entry
    matches, the override is cleared and Quasar shows its label. ``prompt`` defaults to "-"; the
    established-projection / -embedding choosers pass "<choose projection>" / "<choose embedding>"."""
    if value is None:
        select.props(f'display-value="{prompt}"')
    else:
        select.props(remove="display-value")


def _projection_prompt(cid: str) -> str:
    """The placeholder for an established-projection / -embedding chooser when nothing matches:
    the gens copy (under G) reads "<choose embedding>", the base (under P) "<choose projection>"."""
    return "<choose embedding>" if cid.endswith(":gens") else "<choose projection>"


def _hover_index(detail):
    """Normalize an ``opthover`` payload — the hovered option's positional index, or -1 / None on a
    leave — to a 0-based index, or None for a leave. The delegation marshals the index in ``detail``;
    popup-hide passes None. Be defensive about the wrapper shape (a dict/list can slip through the
    event plumbing)."""
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), None)
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else None
    if isinstance(detail, bool) or not isinstance(detail, (int, float)):
        return None
    index = int(detail)
    return index if index >= 0 else None


def _option_key(select: ui.select, index):
    """The option key (the value the select would commit) at a 0-based option index, or None when out
    of range / a leave. NiceGUI numbers each option's client-side value by POSITION (see
    ChoiceElement._update_options), so the hovered index maps back through the live option order —
    the keys of a dict, the items of a list."""
    if index is None:
        return None
    keys = list(select.options)
    return keys[index] if 0 <= index < len(keys) else None


@dataclass
class _Gesture:
    """The ONE record of the active preview gesture — the single source of truth the ring
    highlights are computed from. The DOM's ring classes are a pure function of (document,
    gesture): ``compute_rings`` derives the amber/red sets from this record on every paint, and
    the one idempotent painter applies them — nothing else ever touches the ring classes, so a
    ring structurally cannot outlive its gesture (the stranded-highlight bug class).

    kind        'edit' (a focused editable cell), 'wheel' (gentuning hover-scroll), 'hover'
                (a +/-, history, checkbox, approach or gensign control), 'chooser' (a dropdown
                option), 'temp' (the temperament chooser — its own kind because it may REFLOW),
                or 'drag' (combine / reorder).
    source      the focused/scrolled cell's id — never rung (the user is already looking at it).
    apply       the hypothetical op (a zero-arg editor thunk) the gesture previews WITHOUT
                committing; None = no candidate (invalid/incomplete entry previews nothing).
    baseline    the layout snapshotted when the gesture armed — the diff base for gestures whose
                document MOVES mid-gesture (committed keystrokes / wheel notches / a temporarily
                applied drag or temperament-grow).
    target_pred a drag-combine extra: also ring the dropped-on row/column's editable cells
                (their input values aren't part of the layout content signature).
    token       an editor snapshot held while the DOCUMENT temporarily carries a hypothetical
                state between events (drag, temperament-grow). Ending such a gesture always
                restores the token first (see end_gesture), and render() skips persistence
                while one is held — a hypothetical doc must never reach storage.
    reflowed    temp only: the doc currently holds an applied (grid-reflowing) hypothetical.
    prev        a one-deep suspend: the wheel gesture displaced by the in-cell generator-sign
                hover, re-armed when that hover ends."""
    kind: str
    source: str | None = None
    apply: Callable | None = None
    baseline: "object | None" = None
    target_pred: Callable | None = None
    token: tuple | None = None
    reflowed: bool = False
    prev: "_Gesture | None" = None


class _Reconciler:
    def __init__(self, editor):
        self._editor = editor
        self._cb = None  # callbacks (act, render, on_*) wired by index() after they are defined
        self._row_drag: int | None = None  # the mapping row a drag-to-add started on (dragstart → drop)
        self._col_drag: tuple[str, int] | None = None  # the (interval group, index) a drag-to-add started on
        self.els: dict = {}  # entity id -> outer element (persists across renders)
        self.inputs: dict = {}  # mapping cell id -> q-input (a fraction cell's NUMERATOR / its sole integer input)
        self.den_inputs: dict = {}  # fraction cell id -> its DENOMINATOR q-input (ratio mode only; see _build_gridvalue)
        self.frac_edits: dict = {}  # fraction cell id -> the .rtt-frac-edit box (its data-fracmode drives int/ratio view)
        self.labels: dict = {}  # cell id -> the label whose text tracks state
        self.fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
        self.ratio_faces: dict = {}  # genratio/commaratio id -> its .rtt-ratio container (rebuilt in place)
        self.stacked_faces: dict = {}  # stacked-value cell id -> (main label, sub label): cents whole/.frac, power ∞/(max)
        self.gensign_faces: dict = {}  # generator-tuning cell id -> (sign, whole, .frac) labels: the clickable signed cents face
        self.htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
        self.ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
        self.chart_keys: dict = {}  # chart cell id -> last (w, h, values) drawn, to redraw on resize/data change
        self.range_keys: dict = {}  # range-chart cell id -> last (w, h, ranges) drawn, to redraw on resize/data change
        self.exprs: dict = {}  # math-expression cell id -> the ui.html holding its stacked lines
        self.expr_state: dict = {}  # math-expression cell id -> last (text, w) rendered, to redraw on change
        self.kinds: dict = {}  # entity id -> the kind its element was built for (rebuild when it changes)
        self.selects: dict = {}  # preset cell id -> its q-select
        self.checks: dict = {}  # control_check cell id -> its q-checkbox (the box-𝐋 "replace diminuator")
        self.ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
        self.rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
        self.scheme_buttons: dict = {}  # back-to-scheme button cell id -> its ui.button (for the idle grey)
        self.mean_damage_tips: dict = {}  # optimization-mean damage cell id -> its ui.tooltip (text swaps with all-interval mode)
        self.target_limit_tip = None  # the target chooser's ui.tooltip (text swaps to an invalid-limit message)
        self.captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
        self.caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
        self.math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
        self.math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
        self.fold_state: dict = {}  # fold-toggle cell id -> last state token (unfold_more/less), to swap its SVG on change
        self.cell_units: dict = {}  # value cell id -> the ui.html holding its per-cell unit (the units toggle)
        self.cell_unit_text: dict = {}  # ...and its last unit string, to rewrite on a units toggle / value change
        # The single source of truth for every per-id handle dict, so drop() clears an entity from ALL
        # of them. Forgetting one leaks handles to a deleted element (checks was historically omitted —
        # the box-𝐋 diminuator checkbox); a NEW per-id handle dict MUST be added here.
        self._handle_dicts = (self.els, self.inputs, self.den_inputs, self.frac_edits, self.labels, self.fracs, self.ratio_faces, self.stacked_faces, self.gensign_faces, self.htmls, self.ebk_sizes, self.chart_keys, self.range_keys, self.exprs, self.expr_state, self.kinds, self.selects, self.checks, self.ptext_inputs, self.rangeopts, self.mean_damage_tips, self.captions, self.caption_html, self.math_cells, self.math_rendered, self.fold_state, self.cell_units, self.cell_unit_text)
        # The active preview gesture — the ONE record the ring highlights derive from (see
        # _Gesture). None when no gesture is live; every paint recomputes the rings from it.
        self.gesture: _Gesture | None = None
        # The server-side popup gate: chooser cell id -> 'open' | 'closed' (absent = never
        # tracked, which ALLOWS — the in-process tests drive `opthover` without a popup). An
        # option-hover ARM is dropped when its chooser's popup is 'closed': the client's 90 ms
        # settle-timer can fire AFTER a commit closed the popup, and the socket's FIFO order
        # guarantees that stale arm is seen after the popup-hide — so it can no longer strand a
        # ring (the bug documented on _OPTION_HOVER_DELEGATION). Leaves/popup-hide are ungated.
        self.popup_state: dict = {}
        # The cell-kind dispatch registry (audit #3): kind -> _KindHandlers(build[, update]).
        # Every kind is registered below; make_cell/update_cell index it directly (no fallback),
        # so an unregistered kind raises loudly rather than rendering a silent blank cell.
        self.cell_kinds: dict[str, _KindHandlers] = {}
        for _ebk_kind in _EBK_SVG_KINDS:  # bracket / ebktop / ebkbrace / ebkangle / vbar
            self.cell_kinds[_ebk_kind] = _KindHandlers(self._build_svgfill, self._update_ebk)
        self.cell_kinds["chart"] = _KindHandlers(self._build_svgfill, self._update_chart)
        self.cell_kinds["rangechart"] = _KindHandlers(self._build_svgfill, self._update_rangechart)

        self.cell_kinds["count"] = _KindHandlers(self._build_count, self._update_mathcell)
        self.cell_kinds["symbol"] = _KindHandlers(self._build_symbol, self._update_mathcell)
        self.cell_kinds["matlabel"] = _KindHandlers(self._build_matlabel, self._update_mathcell)
        self.cell_kinds["units"] = _KindHandlers(self._build_units, self._update_mathcell)
        self.cell_kinds["caption"] = _KindHandlers(self._build_caption, self._update_caption)

        self.cell_kinds["ptextpending"] = _KindHandlers(self._build_ptextpending, self._update_ptextpending)
        self.cell_kinds["mathexpr"] = _KindHandlers(self._build_mathexpr, self._update_mathexpr)

        # the unified ratio-or-integer cells all route to one shared builder/update (behaviour per
        # each kind's _GridValueSpec); the kind strings stay (load-bearing for wheel/drag/tooltips).
        _gridvalue = _KindHandlers(self._build_gridvalue, self._update_gridvalue)
        for _gv_kind in ("mapping", "commacell", "unchangedcell",
                         "interestcell", "heldcell", "targetcell"):
            self.cell_kinds[_gv_kind] = _gridvalue
        self.cell_kinds["prescalercell"] = _KindHandlers(self._build_prescalercell, self._update_prescalercell)
        self.cell_kinds["powerinput"] = _KindHandlers(self._build_powerinput, self._update_powerinput)
        self.cell_kinds["powerdisplay"] = _KindHandlers(self._build_powerdisplay, self._update_powerdisplay)
        self.cell_kinds["gentuningcell"] = _KindHandlers(self._build_gentuningcell, self._update_gentuningcell)

        self.cell_kinds["ptextedit"] = _KindHandlers(self._build_ptextedit, self._update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(self._build_genratio, self._update_ratio)
        # the editable quantities-row ratios (comma / target / held / interest): a fraction face
        # the scalar twin of the interval-vectors row's editable column cells — an editable stacked
        # fraction (the shared gridvalue component, ratio_allowed)
        self.cell_kinds["ratiocell"] = _gridvalue
        # a chapter-9 domain basis element (nonstandard-domain box on), and the projection P /
        # embedding G matrix entries — the shared stacked-fraction component. An integer prime shows
        # the big-number view, a nonprime the stacked fraction; the spreadsheet picks elementcell vs
        # elementratio by the value's shape, so a relabel that crosses int↔fraction rebuilds the cell.
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(self._build_commaratio, self._update_ratio)
        self.cell_kinds["tuningvalue"] = _KindHandlers(self._build_tuning_value, self._update_tuning_value)

        # every non-interactive gridded value renders as plain rtt-value text (no box): a box
        # always means editable. prime / formcell / mapped / vec all share this one read-only
        # style — there is deliberately no second "boxed read-only" treatment.
        _value_builder = self._label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["formcell"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(self._label_builder("rtt-colheader"), self._update_label)
        self.cell_kinds["rowlabel"] = _KindHandlers(self._label_builder("rtt-rowlabel"), self._update_label)
        self.cell_kinds["ptext"] = _KindHandlers(self._label_builder("rtt-ptext"), self._update_ptext)
        self.cell_kinds["boxtitle"] = _KindHandlers(self._label_builder("rtt-boxtitle"), None)  # a static in-tile title

        self.cell_kinds["rangemode"] = _KindHandlers(self._build_rangemode, self._update_rangemode)
        self.cell_kinds["scheme_button"] = _KindHandlers(self._build_scheme_button, self._update_scheme_button)
        self.cell_kinds["rowtoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["coltoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["tiletoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["alltoggle"] = _KindHandlers(self._build_alltoggle, self._update_foldtoggle)

        self.cell_kinds["preset"] = _KindHandlers(self._build_preset, self._update_preset)
        self.cell_kinds["control_select"] = _KindHandlers(self._build_control_select, self._update_control_select)
        self.cell_kinds["control_check"] = _KindHandlers(self._build_control_check, self._update_control_check)
        self.cell_kinds["formchooser"] = _KindHandlers(self._build_formchooser, self._update_formchooser)

        self.cell_kinds["minus"] = _KindHandlers(self._build_minus)
        self.cell_kinds["plus"] = _KindHandlers(self._build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(self._build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(self._build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(self._build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(self._build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(self._build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(self._build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(self._build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(self._build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(self._build_comma_plus)
        # the chapter-9 domain basis element draft +/- (nonstandard-domain box on)
        self.cell_kinds["element_plus"] = _KindHandlers(self._build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(self._build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._build_colgrip)

    def drop(self, eid):
        """Remove an entity's element and forget every per-id handle for it (see _handle_dicts)."""
        self.els[eid].delete()
        for d in self._handle_dicts:
            d.pop(eid, None)

    def make_cell(self, cb):
        # build a cell's element in the active parent (the caller opens the freeze container),
        # register it + its kind (and audio key) so render() can place and reconcile it after.
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            # every cell kind is registered (audit #3); indexing rather than .get means an
            # unregistered kind raises loudly here — drift surfaces as a crash, not a silent blank cell
            self.cell_kinds[cb.kind].build(cb, wrap)
            # a click-to-play interval cell (cb.audio set): tag the wrap so the JS engine can find it —
            # it lights the whole column segment on hover, floats a speaker over it, and derives the chord
            if cb.audio is not None:
                self._tag_audio(wrap, cb)
        # explanatory hover text for the interactive controls (read-only value cells get none).
        # All wording lives in rtt.app.tooltips; a NEW cell kind must be classified there
        # (in READONLY_KINDS or with a help entry) or test_web_tooltips' completeness sweep fails.
        # The mark/data-eid ride the wrap, so the tooltip hangs off it too — one shared anchor.
        help_text = tooltips.control_help(cb.kind, cb.id)
        if help_text:
            if cb.id in tooltips.MEAN_DAMAGE_IDS:
                # the read-only mean damage's help names a different quantity per mode (damage
                # ⟪𝐝⟫ₚ vs the all-interval retuning magnitude); keep the Tooltip handle so
                # render() can swap its wording in place when the mode flips, like the symbol glyph
                with wrap:
                    self.mean_damage_tips[cb.id] = ui.tooltip(help_text)
            elif cb.id == "preset:target":
                # keep the target chooser's tooltip handle so the limit validator can swap in an
                # invalid-limit message (an even OLD limit, or a non-whole number) and back — the
                # same in-place relabel the mean damage uses
                with wrap:
                    self.target_limit_tip = ui.tooltip(help_text)
            else:
                wrap.tooltip(help_text)
        self.els[cb.id] = wrap
        self.kinds[cb.id] = cb.kind
        # A fan + / − control must not blur a focused draft cell when clicked. The browser blurs the
        # active input on mousedown of another element, and that blur COMMITS the draft's typed value
        # (its blur handler) BEFORE the control's own click action runs — so clicking a draft's − to
        # cancel it first committed the typed comma (re-ranking), then removed a column: the "− kills
        # the draft AND the column to its left" bug. Swallowing the control's mousedown default keeps
        # the input focused (no commit); the click still fires, the action runs, and the draft cell's
        # later removal-blur is a guarded no-op (on_ratio_change/on_*_change bail on building / a
        # dropped cell). colgrip is excluded — it needs mousedown to start an HTML5 drag.
        if cb.kind.endswith(("plus", "minus")):
            wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
        # an editable text cell drives the edit-preview highlight: focusing it snapshots the grid as
        # the baseline, leaving it clears the rings. Every such cell registers its q-input in `inputs`
        # or `ptext_inputs`, so wiring here covers all of them at once (and no others — a dropdown /
        # checkbox commits instantly, with no "while editing" window to preview).
        edit_input = self.inputs.get(cb.id) or self.ptext_inputs.get(cb.id)
        if edit_input is not None:
            # a fraction cell holds TWO inputs (numerator + denominator) in one cell: wire BOTH, and
            # gate the focus/blur with _FRAC_EXIT_JS so the edit-preview baseline is taken once (not
            # re-snapshotted on the num<->den Tab hop) and on_cell_blur fires only when focus truly
            # leaves the cell. A single-input cell has no den (guard None → fire on every focus/blur).
            den = self.den_inputs.get(cb.id)
            guard = _FRAC_EXIT_JS if den is not None else None
            for fld in (edit_input, den) if den is not None else (edit_input,):
                fld.on("focus", lambda _=None, cid=cb.id: self._cb.on_cell_focus(cid), js_handler=guard)
                fld.on("blur", lambda _=None: self._cb.on_cell_blur(), js_handler=guard)
                # Enter just BLURS the input (client-side) — it does not commit on its own. Blurring routes
                # Enter through the proven blur path: the cell's own blur handler commits the value and
                # on_cell_blur ends the edit-preview. This matches the expected UX (the cursor leaves the box)
                # and, crucially, avoids the bug where committing + re-rendering an input's value WHILE it
                # stays focused desynced it so the browser stopped firing on_change — leaving the live preview
                # working only on the first edit until the cell was left and re-entered (or the tab refreshed).
                fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
        # every editable numeric input steps by its _WHEEL_STEPS amount on a wheel notch while
        # focused. The listener rides the wrap (so a scroll anywhere in the cell counts) and its
        # js_handler only emits when the cell holds focus, so an unfocused scroll just pages the grid
        # (see _INT_WHEEL_JS). One wiring for every kind in the table — no per-input special-casing.
        if cb.kind in _WHEEL_STEPS:
            wrap.on("wheel", lambda e, cid=cb.id: self._cb.on_value_wheel(cid, e.args.get("deltaY")),
                    args=["deltaY"], js_handler=_INT_WHEEL_JS)

    def update_cell(self, cb):
        # reconcile a present cell: run its registered update (value/glyph in sync) then
        # add/refresh/remove the per-cell unit overlay (the `units` toggle).
        handlers = self.cell_kinds[cb.kind]  # registered for every kind (see make_cell); raises on drift
        if handlers.update is not None:
            handlers.update(cb)
        # per-cell unit (the `units` toggle): a tiny line at the bottom of the value
        # cell, the value lifted to stay centred. cb.unit is "" unless units is on, so
        # this adds/updates/removes the overlay as the toggle (or the domain) changes.
        if cb.unit:
            if cb.id not in self.cell_units:
                with self.els[cb.id]:
                    self.cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                self.els[cb.id].classes(add="rtt-cell-united")
            if self.cell_unit_text.get(cb.id) != (cb.unit, cb.w):  # re-fit on a value or width change
                self.cell_units[cb.id].set_content(_bold_units(cb.unit))
                self.cell_units[cb.id].style(f"font-size:{_units_font(cb.unit, cb.w, _CELLUNIT_MAX_FONT):.2f}px")
                self.cell_unit_text[cb.id] = (cb.unit, cb.w)
        elif cb.id in self.cell_units:
            self.cell_units[cb.id].delete()
            self.cell_units.pop(cb.id, None)
            self.cell_unit_text.pop(cb.id, None)
            self.els[cb.id].classes(remove="rtt-cell-united")
        if cb.audio is not None:  # refresh the baked pitch / slot so a reorder or retune stays in sync
            self._tag_audio(self.els[cb.id], cb)

    def _tag_audio(self, el, cb):
        """Tag a cell wrap as a click-to-play voice: the JS engine reads data-audio (its highlight /
        chord group), data-idx (its slot in that group) and data-cents (its pitch) off it, and lights
        it (.rtt-spk) while it sounds. Set on build, refreshed each render so reorder + retune stay live."""
        tile, idx, cents = cb.audio
        el.classes(add="rtt-spk").props(f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"')

    def _put_stacked_face(self, cid, cls, main, sub):
        """Build a stacked value face into the active cell — a big main glyph over a smaller
        sub-line (the read-only tuning value look) — and register the two labels so the update can
        re-sync them. Shared by the cents cells (whole part over .fraction) and the power cells
        (∞ over "(max)")."""
        with ui.element("div").classes(cls):
            m = ui.label(main).classes("rtt-stacked-main")
            s = ui.label(sub).classes("rtt-stacked-sub")
        self.stacked_faces[cid] = (m, s)
        self._size_stacked_main(m, sub)

    def _size_stacked_main(self, main_label, sub):
        """Size a stacked face's main glyph to its sub-line. With NO sub (a bare integer — a
        prescaler 0/1, a finite optimization/norm power) the value isn't a whole-part-over-
        .fraction at all: it renders at the full value-cell font (the `rtt-stacked-solo` class),
        like the plain mapping/mapped integers, instead of the reduced whole-part size that
        leaves room for a fraction. With a sub present (a cents decimal, or ∞ over "(max)") it
        stays the smaller stacked size so the pair fits the square."""
        solo = not sub
        main_label.classes(add="rtt-stacked-solo" if solo else "",
                           remove="" if solo else "rtt-stacked-solo")

    def _sync_stacked_face(self, cid, main, sub):
        """Re-sync a stacked face's two lines in place (the cell kind is unchanged across
        renders, so its labels persist)."""
        m, s = self.stacked_faces[cid]
        m.set_text(main)
        s.set_text(sub)
        self._size_stacked_main(m, sub)  # a value that gained/lost its fraction flips solo too

    def set_cents_face(self, cid, text):
        """Sync a cents cell's stacked face: the whole part over the dot-led fraction (the
        fraction blank when the value is an integer or the cell is blanked). Shared by the
        read-only tuning value cells and the editable cents cells (whose face overlays their input)."""
        whole, frac = _cents_parts(text)
        self._sync_stacked_face(cid, whole, f".{frac}" if frac else "")

    def cents_face(self, cb, cls):
        """Build the stacked int-over-fraction cents face (the read-only tuning value look: the whole
        part big over a smaller dot-led fraction). Shared by the read-only tuning value cell and the
        editable cents cells — the latter pass the overlay class and lay it over their input."""
        whole, frac = _cents_parts(cb.text)
        self._put_stacked_face(cb.id, cls, whole, f".{frac}" if frac else "")

    def _ratio(self, cb, approx, overlay=False):
        """A ratio rendered as a stacked fraction (with a ~ prefix when approximate). With
        ``overlay`` the fraction is an ``rtt-cellface`` laid over an editable input (the
        ratiocell) instead of a read-only cell — it shows when the cell isn't focused. The
        ``.rtt-ratio`` container is kept (``ratio_faces``) so _update_ratio can rebuild its
        contents in place when the value's shape flips between a fraction and a blank/dash."""
        face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
        self.ratio_faces[cb.id] = face
        with face:
            self._ratio_body(cb, approx)

    def _ratio_body(self, cb, approx):
        """Fill the ``.rtt-ratio`` container: the ~approximate marker + stacked fraction for a real
        NUMERIC ratio; otherwise the bare value (empty when blanked, a lone ``—`` when dashed). The
        ~ and the fraction's bar are for numbers only — a dash or a blank gets neither (so a
        quantities-off cell goes truly empty, never leaving a stranded ``~`` over an empty bar).

        A WHOLE numeric ratio (``"n/1"``) collapses to a bare big integer ``n`` — no bar, no
        denominator (``rtt-frac-whole`` hides both) — the read-only twin of the editable cell's int
        view (``_update_fraction``), so a generator-detempering / unrotated-vector-list / generator
        value of ``2/1`` reads "2", not "2 over 1". The ~approximate marker STILL rides a collapsed
        integer in an approximate tile (the generators show "~2", not "2") — it approximates the
        whole VALUE, not just a fraction; only a non-number (dash / blank) drops it. _update_ratio
        rebuilds this body on every render, so the collapse follows the value with no patching."""
        parts = _ratio_parts(cb.text)
        if parts and not all(p.lstrip("-").isdigit() for p in parts):
            parts = None  # a dashed "—/—" isn't a number — render it bare, no ~ / fraction bar
        whole = bool(parts) and parts[1] == "1"  # "n/1" -> the bare integer "n" (collapse like the editable cell)
        if approx and parts:  # ~ marks an approximate NUMBER (integer or fraction); only a dash / blank gets none
            ui.label("~").classes("rtt-approx")
        if parts:
            with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
                num = ui.label(parts[0]).classes("rtt-frac-num")
                den = ui.label(parts[1]).classes("rtt-frac-den")
            self.fracs[cb.id] = (num, den)
            self._fit_ratio(cb.id, parts[0], parts[1], cb.w, whole)
        else:
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value")

    def _fit_ratio(self, cid, num, den, width, whole=False):
        """Size a stacked fraction's two lines to fit its square: a long numerator/denominator
        would spill the cell at the comfortable face size, so num and den shrink together (see
        _ratio_font). A whole ratio (collapsed to a bare integer) fills the square at the big value
        font instead — the read-only twin of the editable int view (_fit_fraction). Shared by the
        build and the in-place update so a re-vectored ratio re-fits."""
        size = _digit_fit_font(len(num), width, float(_CELL_FONT)) if whole else _ratio_font(num, den, width)
        font = f"font-size:{size:.2f}px"
        self.fracs[cid][0].style(font)
        self.fracs[cid][1].style(font)

    def cell_value(self, cid):
        """The committed string a gridded ratio-or-integer cell currently holds, reassembled from
        its input(s). A fraction cell (``_build_gridvalue`` with ``ratio_allowed``) edits its
        numerator and denominator in two separate inputs (``inputs[cid]`` / ``den_inputs[cid]``);
        this rejoins them into the ``"num/den"`` the commit/parse callbacks expect — collapsing a
        blank/``1`` denominator to a bare ``"num"`` (so ``2/1`` reads as ``2``), and a blank
        numerator to ``""`` (a cleared cell, a silent no-op). An integer-mode cell has no
        denominator input, so this is just its sole input's value. The single read every commit /
        whole-matrix callback uses, so a split cell looks like one combined field to them."""
        num = str(self.inputs[cid].value).strip()
        if not num:
            return ""
        if num == "?":  # an untouched draft numerator: the "?/?" no-op sentinel (a blank/cleared draft)
            return "?/?"
        if "/" in num:  # the numerator already carries a whole ratio (a paste, or a test set_value)
            return num
        den = str(self.den_inputs[cid].value).strip() if cid in self.den_inputs else ""
        # a blank/1/"?" (untouched draft) denominator is the big-integer view — so typing a bare
        # integer into a draft's "?/?" commits the integer, not "N/?"
        return num if den in ("", "1", "?") else f"{num}/{den}"

    # ---- cell-kind handlers (audit #3): each kind's build + update, co-located here so a
    # built-but-not-filled drift between the two ladders becomes structurally impossible ----
    # The html-content families build an empty ui.html; the update fills it (re-drawing only
    # when the cached key changes). The EBK marks, bar chart and range chart share the build.
    def _build_svgfill(self, cb, wrap):
        self.htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in the update from the cell's px box

    def _update_ebk(self, cb):
        # the mark is drawn 1:1 to its px box, so redraw it whenever the box changes size (e.g.
        # the brace/top bracket as the domain grows) or its pending (green) state flips (a draft
        # comma's marks committing to black)
        if self.ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
            self.htmls[cb.id].set_content(_ebk_svg(cb))
            self.ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)

    def _update_chart(self, cb):
        # redraw when the box resizes OR the underlying data / indicator changes
        key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
        if self.chart_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(
                _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label))
            self.chart_keys[cb.id] = key

    def _update_rangechart(self, cb):
        # redraw when the box resizes OR the ranges/live tuning change (mapping/mode edit)
        key = (cb.w, cb.h, cb.ranges, cb.values)
        if self.range_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values))
            self.range_keys[cb.id] = key

    def _build_count(self, cb, wrap):
        self.math_cells[cb.id] = ui.html("").classes("rtt-count")  # a scalar "symbol = value"; filled in update

    def _build_symbol(self, cb, wrap):
        wrap.classes("rtt-symbol-cell")
        # the optimization box's symbols (⟪𝐝⟫ₚ, 𝑝) stay on one line (ₚ never wraps off)
        cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
        self.math_cells[cb.id] = ui.html("").classes(cls)

    @staticmethod
    def _matlabel_classes(text, is_row=False):
        # routed through _math_html so a label's bold-italic / bold-upright glyphs draw in the
        # same styled face as the tile symbol it indexes. A plain single-glyph label (𝒎ᵢ, 𝐜ᵢ, w)
        # fits the COL_W spine at the default size; any MULTI-TOKEN label — the complexity
        # norms (‖L𝐜ᵢ‖q) or an equation-form header carrying a space (cₙ = ‖L𝐭ₙ‖q, the
        # all-interval weight's wₙ = cₙ⁻¹) — takes the smaller shrink/wrap variant so it can
        # never outgrow its column and collide with its neighbours. A header can change shape
        # in place (a bare wₙ becoming wₙ = cₙ⁻¹ as all-interval toggles on), so _update_mathcell
        # re-derives this on every relabel, not just at build — else the new text keeps the old
        # (overspilling) class.
        return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"

    def _build_matlabel(self, cb, wrap):
        wrap.classes("rtt-matlabel-cell")
        self.math_cells[cb.id] = ui.html("").classes(self._matlabel_classes(cb.text))

    def _build_units(self, cb, wrap):
        wrap.classes("rtt-units-cell")
        self.math_cells[cb.id] = ui.html("").classes("rtt-units")

    def _update_mathcell(self, cb):  # shared by symbol / count / units / matlabel
        # symbols/equivalence tails/counts and matrix row/col labels go through _math_html (styled
        # math glyphs); units use _units_html (a single-story-g sans value, serif label) and shrink
        # to fit their cell, so a long annotated unit (¢(E-sopfr-S)/) never spills its COL_W spine
        if cb.kind == "units":
            html = _units_html(cb.text)
            if self.math_rendered.get(cb.id) != (html, cb.w):  # rewrite on a toggle / value / width change
                self.math_cells[cb.id].set_content(html)
                self.math_cells[cb.id].style(f"font-size:{_units_font(cb.text, cb.w, _UNITS_MAX_FONT):.2f}px")
                self.math_rendered[cb.id] = (html, cb.w)
            return
        html = _math_html(cb.text)
        # a wide COLUMN header (the superspace / projection labels 𝐠_L→sᵢ, 𝐜ʟᵢ … carrying an arrow +
        # subscript markup) shrinks to fit its COL_W slot rather than overlapping its neighbours —
        # sized off the layout's own width model (_min_width_for_lines) so the fit matches the column.
        # ROW labels keep full size (their gutter widens to hold them); the ‖…‖q / spaced norm labels
        # wrap via their CSS class, so they keep the default size too.
        font = None
        if cb.kind == "matlabel" and ":col:" in cb.id and "‖" not in cb.text and " " not in cb.text:
            w = spreadsheet._min_width_for_lines(cb.text, 1, _MATLABEL_FONT)
            if w > cb.w - 2:  # overflows its slot → shrink to fit (never enlarges; floored for legibility)
                font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cb.w - 2) / w)
        if self.math_rendered.get(cb.id) != (html, font):  # rewrite on a toggle / value / fit change
            self.math_cells[cb.id].set_content(html)
            if font is not None:
                self.math_cells[cb.id].style(f"font-size:{font:.2f}px")
            self.math_rendered[cb.id] = (html, font)
            if cb.kind == "matlabel":
                # the label may have changed shape (bare wₙ → wₙ = cₙ⁻¹); re-pick its size class
                # so a now-wider header takes the shrink/wrap variant instead of overspilling.
                self.math_cells[cb.id].classes(replace=self._matlabel_classes(cb.text))
            if cb.id == "optimization:mean_damage:symbol":
                # all-interval relabels this to the wide retuning magnitude ‖𝒓𝐿⁻¹‖dual(q); shrink
                # it (rtt-opt-wide) so it stays centred over its COL_W value
                wide = "‖" in cb.text
                self.math_cells[cb.id].classes(
                    replace="rtt-symbol rtt-opt-1line rtt-opt-wide" if wide
                    else "rtt-symbol rtt-opt-1line")

    def _build_caption(self, cb, wrap):
        wrap.classes("rtt-caption-cell")
        # the optimization box's captions stay on one line (no wrap), unlike tile names; a caption
        # with align="left" reads left-justified under its control (e.g. a preset chooser's label).
        # The lone exception is the mean damage's own label, whose wide all-interval "retuning
        # magnitude" must wrap to two lines (its slot is too narrow to spread it on one) — it wraps
        # at the space like a tile name, while the short "power mean" still fits on a single line.
        one_line = cb.id.startswith("optimization:") and cb.id != "optimization:mean_damage:caption"
        cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
        if cb.align == "left":
            cls += " rtt-caption-left"
        self.captions[cb.id] = ui.html("").classes(cls)

    def _update_caption(self, cb):
        html = _underline_html(cb.text, cb.underlines)
        if self.caption_html.get(cb.id) != html:  # rewrite when a mnemonic toggle adds/removes underlines
            self.captions[cb.id].set_content(html)
            self.caption_html[cb.id] = html
        # a locked control's caption greys with it (the disabled flag), so the label reads in the
        # same disabled grey as the control rather than the caption's darker default
        self.captions[cb.id].classes(add="rtt-caption-disabled" if cb.disabled else "",
                                     remove="" if cb.disabled else "rtt-caption-disabled")

    def _build_ptextpending(self, cb, wrap):
        # an editable vector-list dual mid-draft (comma basis / target list): a static two-tone
        # box (the draft is typed into the green grid cells, not here); content set in the update
        self.htmls[cb.id] = ui.html("").classes("rtt-ptextpending")

    def _update_ptextpending(self, cb):
        # the committed part black and the draft entry green (same green as its grid cells)
        ed = self._editor
        if cb.id == "ptext:mapping:primes":
            # the mapping draft is a ROW, not a column — splice the green draft map before the
            # committed matrix's closing } (cb.text is the committed mapping plain text)
            prefix, draft, suffix = service.mapping_pending_text(cb.text, ed.pending_mapping_row)
            self.htmls[cb.id].set_content(
                f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
            self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            return
        if cb.id == "ptext:vectors:targets":
            targets = ed.target_override or service.target_interval_set(ed.target_spec, ed.state.domain_basis)
            committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
            pending = ed.pending_target
        else:  # the comma basis
            committed, pending = ed.state.comma_basis, ed.pending_comma
        prefix, draft, suffix = service.vector_list_pending_text(committed, pending)
        self.htmls[cb.id].set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
        self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")

    def _build_mathexpr(self, cb, wrap):
        self.exprs[cb.id] = ui.html("").classes("rtt-mathexpr")  # a just value's stacked closed form; drawn in update

    def _update_mathexpr(self, cb):
        # redraw (with refit fonts) whenever the expression text or cell width changes
        if self.expr_state.get(cb.id) != (cb.text, cb.w):
            self.exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
            self.expr_state[cb.id] = (cb.text, cb.w)

    # ---- the unified editable ratio-or-integer grid cell (was ~10 near-identical builders). One
    # q-input (the integer view / a fraction's numerator), plus a denominator input + bar for the
    # ratio-capable kinds; behaviour driven by the cell's _GridValueSpec. prescalercell /
    # gentuningcell / powerinput are a DIFFERENT family (a decimal cents / power face overlaid on the
    # input) and keep their own builders. ----
    def _build_gridvalue(self, cb, wrap):
        # PREVIEW the ripple as you type (the kinds that have a live preview) and COMMIT on Enter /
        # blur (Enter blurs via make_cell) — never re-solving on every keystroke. A per-cell unit
        # overlays inside the input box; drag-to-combine arming is per its spec. A ratio_allowed kind
        # is an editable stacked fraction (numerator over bar over denominator, two fields); an
        # integer-only kind is one input.
        spec = _GRIDVALUE_SPECS[cb.kind]
        commit, preview = self._gridvalue_handlers(cb, spec)
        if spec.ratio_allowed:
            self._build_fraction(cb, wrap, commit, preview)
        else:
            wrap.classes("rtt-cell-input")
            inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
            inp.on("blur", commit)
            self.inputs[cb.id] = inp
        self._arm_gridvalue(wrap, cb, spec)

    def _build_fraction(self, cb, wrap, commit, preview):
        # the editable stacked fraction: a numerator input over a bar over a denominator input, edited
        # IN PLACE (no overlay face, no diagonal slash). The two are SEPARATE fields — Tab moves
        # num->den, the bar isn't selectable — and the cell collapses to the big-integer view when the
        # denominator is blank/1 ("/" in integer view splits it open again). _FRACTION_JS drives the
        # live int<->ratio switch client-side; make_cell gates focus/blur (it also wires the den) so
        # the commit fires only when focus leaves the WHOLE cell. The white box + black outline rides
        # the WRAP (one box around two inputs), not each input's own Quasar control.
        wrap.classes("rtt-cell-input rtt-fraccell")
        box = ui.element("div").classes("rtt-frac-edit")
        with box:
            num = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput rtt-frac-num-in")
            ui.element("div").classes("rtt-frac-bar")  # the horizontal rule — a div, so it is never selectable
            den = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput rtt-frac-den-in")
        num.on("blur", commit, js_handler=_FRAC_EXIT_JS)  # commit only when focus leaves the whole cell
        den.on("blur", commit, js_handler=_FRAC_EXIT_JS)
        self.inputs[cb.id] = num
        self.den_inputs[cb.id] = den
        self.frac_edits[cb.id] = box

    def _gridvalue_handlers(self, cb, spec):
        """A gridded cell's (commit, preview) event handlers. The scalar ratio / domain-element
        cells pass the cell id and commit one at a time; the integer matrix/vector cells re-read the
        WHOLE matrix and take a ``preview=`` flag. ``preview`` is None for the ratiocell — it commits
        on blur with no live keystroke preview (parsing a half-typed fraction would mis-retune)."""
        fn = getattr(self._cb, spec.commit)
        if spec.cid_arg:
            commit = lambda _=None, cid=cb.id: fn(cid)
            pv = getattr(self._cb, spec.preview) if spec.preview else None
            preview = (lambda e=None, cid=cb.id: pv(cid)) if pv else None
        else:
            commit = lambda _=None: fn()
            preview = (lambda e=None: fn(preview=True)) if spec.preview else None
        return commit, preview

    def _arm_gridvalue(self, wrap, cb, spec):  # drag-to-combine drop target, per the cell's spec
        if spec.arm is None:
            return
        if spec.arm[0] == "row":  # a mapping row: drop a dragged generator row here to combine
            self._arm_row_target(wrap, cb.gen)
        else:  # ("col", group): drop a dragged interval onto this column (its product) to combine
            self._arm_col_target(wrap, spec.arm[1], cb.comma)

    def _update_gridvalue(self, cb):
        spec = _GRIDVALUE_SPECS[cb.kind]
        text = self._gridvalue_text(cb)
        if spec.ratio_allowed:
            self._update_fraction(cb, text)
        else:
            self.inputs[cb.id].value = text
        if spec.pending:  # the green draft ring/wash + text (a comma/target/held/interest being added)
            # the fraction cells carry it on the WRAP (it rings the whole box + colours both fields and
            # the bar); the single-input cells carry it on the input
            target = self.els[cb.id] if spec.ratio_allowed else self.inputs[cb.id]
            target.classes(add="rtt-pending" if cb.pending else "",
                           remove="" if cb.pending else "rtt-pending")

    def _update_fraction(self, cb, text):
        # split the committed value into the two fields and pick the view: a blank/1 denominator is the
        # big-integer view (collapse EVERYWHERE — a committed "2/1" rests as a big "2"), anything else
        # is the stacked fraction. _FRACTION_JS keeps data-fracmode live as you type; this is the
        # authoritative resting state (and the den is cleared in integer view so "/" reopens it empty).
        num, den = _ratio_parts(text) or (text, "")
        ratio = den not in ("", "1")
        self.inputs[cb.id].value = num
        self.den_inputs[cb.id].value = den if ratio else ""
        self.frac_edits[cb.id].props(f'data-fracmode={"ratio" if ratio else "int"}')
        self._fit_fraction(cb.id, num, den, cb.w, ratio)

    def _fit_fraction(self, cid, num, den, width, ratio):
        # the stacked fraction shrinks both lines together to fit a long num/den (capped at the
        # comfortable ratio size); the integer view fills the square at the big value font, shrunk only
        # if a long integer (e.g. a target 65536) would spill. Both share _digit_fit_font. Set on both
        # inputs (the __native font inherits), so they share one size and the fit is readable per field.
        size = _ratio_font(num, den, width) if ratio else _digit_fit_font(len(num), width, float(_CELL_FONT))
        style = f"font-size:{size:.2f}px"
        self.inputs[cid].style(style)
        self.den_inputs[cid].style(style)

    def _gridvalue_text(self, cb):
        """The string a gridded cell shows. A live DRAFT (a comma column / a mapping row being added)
        reads its typed component straight from the editor — it changes during a preview without a
        spreadsheet rebuild; every other cell already carries it in ``cb.text`` (blanked when
        ``quantities`` is off)."""
        if cb.pending and cb.kind in ("commacell", "mapping"):
            draft = self._editor.pending_comma if cb.kind == "commacell" else self._editor.pending_mapping_row
            v = draft[cb.prime] if draft is not None else None
            return "" if v is None else str(v)
        return "" if cb.blank else cb.text

    def _build_prescalercell(self, cb, wrap):
        # a bare prescaler 𝐿 diagonal cell, the user's editable override (off-diagonal cells stay
        # tuning value "0" — 𝐿 is diagonal). Each input dispatches to set_custom_prescaler_entry; the cid
        # carries the diagonal slot, so the lambda closes over it (a free cb would be the LAST
        # cell's id by the time the user types)
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_prescaler_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self.cents_face(cb, "rtt-tuning-value rtt-cellface")  # the stacked face overlaid on the input

    def _update_prescalercell(self, cb):
        # reflect the live prescaler diagonal (the override if set, else the scheme-derived value —
        # spreadsheet.build emits the final text). Blank when quantities are off, like the other cells
        self.inputs[cb.id].value = cb.text
        self.set_cents_face(cb.id, cb.text)  # the overlaid stacked face mirrors the input

    def _build_powerinput(self, cb, wrap):
        # the optimization power 𝑝, the box-𝒄 norm power 𝑞, or its dual. The symbol label rides as
        # a separate cell below; the value carries a stacked gridded face overlaid on the editable
        # input (like a cents cell): ∞ shows a small "(max)" beneath it, a numeric power shows bare.
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_power_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text))

    def _update_powerinput(self, cb):
        # mirror the raw value into the input (shown when focused) and re-sync the overlay face
        # (shown otherwise): ∞ stacks a small "(max)" below it, a numeric power shows bare. (Only the
        # editable powers run through here: the live optimization power 𝑝 and the box-𝒄 norm power 𝑞
        # with alt. complexity on. A locked 𝑝 (all-interval) or 𝑞 (alt. complexity off) and the
        # derived dual(𝑞) are read-only powerdisplays — a different kind — so they never reach here.)
        self.inputs[cb.id].value = cb.text
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_powerdisplay(self, cb, wrap):
        # a READ-ONLY power value: the all-interval-locked optimization power 𝑝, the box-𝒄 norm power 𝑞
        # when alt. complexity is off, or the derived dual norm power dual(𝑞). The SAME stacked
        # ∞-over-"(max)" face as the editable powerinput (_power_parts, same fonts, full-cell centred
        # via rtt-cellface), but with no input — so it looks identical to its editable twin minus the
        # white input box. (rtt-cell-stacked is omitted: with no input there's no face to hide on
        # focus, and it keeps the per-cell-unit padding rule off a value that carries no unit.)
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text))

    def _update_powerdisplay(self, cb):
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_gentuningcell(self, cb, wrap):
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_gentuning_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self._gentuning_face(cb)  # the clickable signed cents face overlaid on the input
        # hover-and-scroll fine-adjust: each wheel notch nudges this generator by 1/1000 cent (the
        # last digit the cents face shows). The listener rides the wrap, not the input, so a scroll
        # over the overlaid signed face (a sibling of the input) still reaches it by bubbling;
        # .prevent stops the grid scrolling out from under the cursor.
        wrap.on("wheel.prevent",
                lambda e, cid=cb.id: self._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
                args=["deltaY"])
        # hovering arms the wheel preview: a baseline is snapshotted so each notch rings the cells it
        # moves; leaving the cell clears the rings (the committed nudge stays).
        wrap.on("mouseenter", lambda _=None, cid=cb.id: self._cb.gentuning_hover(cid))
        wrap.on("mouseleave", lambda _=None, cid=cb.id: self._cb.gentuning_unhover(cid))

    def _update_gentuningcell(self, cb):
        text = "" if cb.blank else cb.text  # blank when quantities off
        self.inputs[cb.id].value = text
        self._set_gentuning_face(cb.id, text)  # the overlaid signed face mirrors the input

    def _gentuning_face(self, cb):
        """The generator-tuning cell's signed, clickable cents face overlaid on its input: a sign
        glyph (the otherwise-assumed "+" of a positive generator, made visible — or "−") the user
        clicks to reverse the generator (negating its mapping row in lockstep, so the tuning map
        holds), then the whole part big over a small dot-led fraction (the shared cents look). Only
        the sign takes pointer events; a click elsewhere falls through to focus the input for typing."""
        sign, whole, frac = _gentuning_parts(cb.text)
        i = int(cb.id.rsplit(":", 1)[1])
        with ui.element("div").classes("rtt-tuning-value rtt-cellface"):
            with ui.element("div").classes("rtt-gentuning-main"):
                s = ui.label(sign).classes("rtt-gensign").mark(f"gensign:{i}") \
                    .on("click", lambda _=None, i=i: self._cb.act(lambda: self._editor.flip_generator(i)))
                # hovering the sign previews REVERSING this generator (ring the cells the flip would
                # change — its tuning sign and its mapping row), the same ring-only hover the other
                # controls give. This is the "+/- in the generator tuning map" hover.
                self._preview_control(s, lambda gi=i: self._editor.flip_generator(gi))
                m = ui.label(whole).classes("rtt-stacked-main")
            sub = ui.label(f".{frac}" if frac else "").classes("rtt-stacked-sub")
        self.gensign_faces[cb.id] = (s, m, sub)

    def _set_gentuning_face(self, cid, text):
        """Re-sync a generator-tuning cell's signed face in place (the cell kind is unchanged
        across renders, so its sign/whole/fraction labels persist)."""
        sign, whole, frac = _gentuning_parts(text)
        s, m, sub = self.gensign_faces[cid]
        s.set_text(sign)
        m.set_text(whole)
        sub.set_text(f".{frac}" if frac else "")

    def _build_ptextedit(self, cb, wrap):
        # an editable dual: typing a valid EBK string drives the grid (its own ptext_inputs dict).
        # Most duals commit LIVE (on_change). The projection P / embedding G bands commit only on
        # SUBMIT (blur / Enter): you type the WHOLE matrix unmolested — no retune, no red box, no toast
        # — until you're done, then it validates (a single partial keystroke can't be a valid matrix).
        if cb.id.startswith("ptext:projection:"):
            inp = ui.input(value=cb.text).props("dense borderless").classes("rtt-ptextedit")
            inp.on("blur", lambda e=None, cid=cb.id: self._cb.on_ptext_edit(cid, self.ptext_inputs[cid].value))
        else:
            inp = ui.input(value=cb.text,
                    on_change=lambda e, cid=cb.id: self._cb.on_ptext_edit(cid, e.value)) \
                .props("dense borderless").classes("rtt-ptextedit")
        self.ptext_inputs[cb.id] = inp

    def _update_ptextedit(self, cb):  # reflect the canonical string + its shrink-to-fit font
        self.ptext_inputs[cb.id].value = cb.text
        self.ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    # ---- ratio faces (a stacked fraction via _ratio) + the read-only cents (tuning value) face ----
    def _build_genratio(self, cb, wrap):
        if cb.pending:  # the draft row's generator ratio: a green "?" placeholder until the row commits
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value rtt-pending-q")
            return
        self._ratio(cb, approx=True)  # a generator ratio, shown ~approximate

    def _build_commaratio(self, cb, wrap):
        self._build_ratio_or_pending(cb)

    def _build_ratio_or_pending(self, cb):
        # a read-only comma ratio heading its column — the generator-detempering D ratio, or a
        # pending comma draft's green "?" placeholder (no value until the vector is filled in). The
        # editable comma/target/held/interest ratios are ratiocells (the shared _build_gridvalue).
        if cb.pending:
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value rtt-pending-q")
        else:
            self._ratio(cb, approx=False)

    def _update_ratio(self, cb):  # genratio / commaratio (read-only): rebuild the stacked fraction face
        # The value's SHAPE can flip between renders — a real numeric ratio <-> a blanked (quantities
        # off) or dashed value, or a whole "n/1" <-> a true fraction — and the ~approx + fraction
        # structure differs from a bare label / bare integer. Patching the fraction's numbers in
        # place (the old path) would strand a ~ over an empty fraction bar when the value blanks (the
        # reported "~-"), so rebuild the container's contents from the current value instead — which
        # also re-applies the whole-number collapse for free. The .rtt-ratio container itself (and
        # the per-cell unit that rides the wrap beside it) are untouched. A pending "?" cell has no
        # container — it's static.
        face = self.ratio_faces.get(cb.id)
        if face is None:
            return
        face.clear()
        self.fracs.pop(cb.id, None)
        self.labels.pop(cb.id, None)
        with face:
            self._ratio_body(cb, approx=(cb.kind == "genratio"))

    def _build_tuning_value(self, cb, wrap):
        self.cents_face(cb, "rtt-tuning-value")  # the read-only stacked int-over-fraction cents face

    def _update_tuning_value(self, cb):
        self.set_cents_face(cb.id, cb.text)
        # a blank pending PLACEHOLDER in a tuning-family row (tuning / just / retune / complexity /
        # …) of the draft column, ringed green by .rtt-cell:not(.rtt-cell-input).rtt-pending — the
        # tuningvalue twin of the _update_label toggle. Committed cells are pending=False (no-op).
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")

    # ---- plain label cells: a ui.label whose text the update keeps in sync (set_text). prime /
    # formcell sit in a white-bordered box; ptext also tracks a shrink-to-fit font; boxtitle is static ----
    def _label_builder(self, cls):  # a build that drops a classed ui.label into the cell, registered in labels
        def build(cb, wrap):
            self.labels[cb.id] = ui.label(cb.text).classes(cls)
        return build

    def _update_label(self, cb):  # prime / formcell / colheader / rowlabel / mapped / vec
        self.labels[cb.id].set_text(cb.text)
        # a blank pending PLACEHOLDER: the draft column's computed rows (mapping / tuning / …) are
        # filled with empty cells so the WHOLE draft column reads green, not just its editable cells.
        # Toggle rtt-pending on the wrap; .rtt-cell:not(.rtt-cell-input).rtt-pending rings it green.
        # Committed cells are pending=False, so this just keeps the class cleared for them.
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")

    def _update_ptext(self, cb):  # a read-only value: keep its text and shrink-to-fit font in sync
        self.labels[cb.id].set_text(cb.text)
        self.labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    # ---- interactive controls with an update: range-mode selector, fold toggles ----
    def _build_rangemode(self, cb, wrap):
        wrap.classes("rtt-rangemode")  # two square indicators side by side (the mockup style)
        opts = {}
        for mode in ("monotone", "tradeoff"):
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                ui.label(mode).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, m=mode: self._cb.on_range_mode(m))
            opts[mode] = opt
        self.rangeopts[cb.id] = opts

    def _update_rangemode(self, cb):  # fill the live mode's square (the other's is hollow)
        for mode, opt in self.rangeopts[cb.id].items():
            (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
             else opt.classes(remove="rtt-rangeopt-on"))

    def _build_scheme_button(self, cb, wrap):
        # single click hands the tuning back to the scheme + target list (back_to_scheme); always
        # present on the projection / embedding tiles, regardless of the presets toggle
        self.scheme_buttons[cb.id] = ui.button(cb.text, on_click=lambda: self._cb.act(self._editor.back_to_scheme),
                                               color=None).props("unelevated dense no-caps").classes("rtt-scheme-btn")

    def _update_scheme_button(self, cb):  # grey it when the tuning is already scheme-driven (nothing to hand back)
        btn = self.scheme_buttons[cb.id]
        (btn.classes(add="rtt-scheme-btn-idle") if not self._editor.manual_tuning
         else btn.classes(remove="rtt-scheme-btn-idle"))

    def _build_foldtoggle(self, cb, wrap):  # rowtoggle / coltoggle / tiletoggle: a clickable chevron over its band
        item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets" / "tile:mapping:primes"
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text  # the glyph swaps on collapse/expand (see _update_foldtoggle)
        wrap.on("click", lambda _=None, it=item: self._cb.on_toggle(it))

    def _build_alltoggle(self, cb, wrap):  # the master expand/collapse-all control in the node corner
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None: self._cb.on_toggle_all())

    def _update_foldtoggle(self, cb):  # swap the chevron SVG when the band folds / unfolds
        if self.fold_state.get(cb.id) != cb.text:
            self.htmls[cb.id].set_content(_control_svg(_FOLD_GLYPH[cb.text]))
            self.fold_state[cb.id] = cb.text

    # ---- chooser dropdowns + the diminuator checkbox ----
    def _target_preset_values(self):
        """The numeric limit + TILT/OLD family the target chooser shows, or ``(None, None)``
        when no named family applies — a typed/edited target list overriding it, or all-interval
        mode (every interval, so no target set scheme). Then both parts fall back to "-" (the
        select via display-value, the number via its "-" placeholder); all-interval also greys+locks
        the chooser (the cell's ``disabled`` flag, applied in :meth:`_update_preset`). A ``None``
        family is also what makes re-picking TILT/OLD a real value change the handler acts on, so the
        chooser doubles as the reset back to a named list — not a same-value no-op Quasar would swallow."""
        if self._editor.target_override is not None or service.is_all_interval(self._editor.tuning_scheme):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:  # no manual limit: show the family's domain default
            limit = service.default_target_limit(
                family, self._editor.state.domain_basis)
        return limit, family

    def _arm_option_hover(self, sel, wrap, cid):
        """Arm a q-select for the shared option-hover preview (any chooser: temperament / tuning /
        prescaler / complexity / weight-slope / form). Hovering an option in the OPEN dropdown rings
        the cells selecting it would change, reverting on leave / popup-close. The teleported Quasar
        popup blocks both a slot ``$emit`` and any ``document`` use inside the slot, so the option slot
        only STAMPS each option's positional index (``:data-optidx``) and this chooser's cell id
        (``data-optcid``); the one document-level delegation (``_OPTION_HOVER_DELEGATION``) reads them
        on hover and fires ``opthover`` at this cell wrap, handled by ``on_chooser_hover``. ``v-bind
        itemProps`` keeps each option clickable and carries a divider's disabled state. Reusable by any
        q-select — a sibling chooser need only call this."""
        sel.add_slot("option", f"""
            <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cid}">
                <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
            </q-item>
        """)
        wrap.on("opthover", lambda e: self._cb.on_chooser_hover(cid, e.args), args=["detail"])
        # the popup events feed the server-side gate (popup_state): an option-hover ARM that
        # arrives while this chooser's popup is 'closed' is a stale debounce-timer fire from a
        # popup that already committed/closed — dropped, so it can never strand a ring. The hide
        # also ends a live chooser/temperament gesture (the leave path), ungated.
        sel.on("popup-show", lambda _=None: self._cb.on_popup(cid, True))
        sel.on("popup-hide", lambda _=None: self._cb.on_popup(cid, False))

    def _build_preset(self, cb, wrap):
        name = cb.id.split(":")[1]  # temperament / tuning / target (a copy adds a :col suffix)
        if name == "target":
            # a numeric limit override beside the TILT/OLD family select. Both fall back to "-"
            # when a typed/edited target list overrides the family (see _target_preset_values):
            # the select via display-value, the number via its "-" placeholder.
            limit, family = self._target_preset_values()
            with ui.element("div").classes("rtt-preset-target"):
                # A TEXT input, not ui.number: a number input lets the browser swallow non-numeric
                # keystrokes to empty, so "abc" would silently blank the limit with no way to toast
                # it. As text, the raw entry reaches the handler, which validates it (whole number?
                # odd for OLD?) and reddens/toasts a bad one. limit_changed tells the handler the
                # user TYPED a limit (toast on a bad one) vs PICKED a family (a switch to OLD that
                # turns an even limit invalid only reddens it). debounce collapses a multi-digit
                # entry into one settled event, so typing "21" never flashes a toast at the even
                # intermediate "2" (the programmatic render echo is Python-side and stays inside the
                # building[0] guard, so debounce can't leak it).
                num = ui.input(value=_limit_text(limit),
                        on_change=lambda e: self._cb.on_target_change(limit_changed=True)) \
                    .props('dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300').classes("rtt-preset-num")
                # make the limit input CONTROLLED (ui.input defaults loopback off, leaving the box
                # uncontrolled during typing). Off, the server can't overwrite what was typed, so a
                # rejected non-number couldn't be reverted nor a value reddened-in-place. On, the
                # server's value always wins — debounce keeps the echo to once-per-settled-entry.
                num.LOOPBACK = True
                num._props['loopback'] = True
                # scroll the focused limit square to step it by ±1, like the integer matrix/vector
                # cells (focus-gated via _INT_WHEEL_JS). Each notch cheaply steps the shown number;
                # the heavy commit (target-set rebuild + solve) is debounced so a fast scroll can't
                # grind the app (see on_target_limit_wheel).
                num.on("wheel", lambda e: self._cb.on_target_limit_wheel(e.args.get("deltaY")),
                       args=["deltaY"], js_handler=_INT_WHEEL_JS)
                # the limit field drives the grid's edit-preview, like an editable matrix/vector cell:
                # focusing it snapshots the baseline, so each committed change (a typed or wheeled limit,
                # both via on_target_change) rings the target rows it moves, and leaving clears them. It
                # lives in `selects` not `inputs`, so make_cell's generic focus/blur wiring misses it.
                # The invalid-limit reddening (_sync_target_limit_error) rides the field itself, a
                # different signal that coexists with the rings (which ride OTHER cells).
                num.on("focus", lambda _=None: self._cb.on_cell_focus(cb.id))
                num.on("blur", lambda _=None: self._cb.on_cell_blur())
                # Enter commits the typed limit. The field is debounce=300 + loopback-controlled, so its
                # value only settles to the server (firing the on_change commit) after a typing pause or
                # on blur — pressing Enter alone did nothing (the reported "Enter doesn't submit the
                # TILT/OLD number, only blur"). Blur the input on Enter: Quasar flushes the debounced
                # value at once (committing via on_change) and the native blur runs on_cell_blur. Pure
                # client-side, so it also works when the debounce hasn't yet elapsed.
                num.on("keydown.enter", js_handler="(e) => e.target.blur()")
                # ...and previews each keystroke LIVE the way a wheel notch does, reddening the rows the
                # typed limit would drop before the debounced commit reflows them away. on_change is the
                # debounced model-value (the commit); this must fire at once on each keystroke instead.
                # NOT the DOM `input` event: a Quasar QInput doesn't forward native `input` to a NiceGUI
                # `.on()` listener (it never reaches the socket — verified), so an `.on("input")` preview
                # silently never ran. `keyup` DOES fire on the QInput; and since NiceGUI's `args=` only
                # filters TOP-LEVEL event keys (it can't pull the nested `target.value`), mirror the
                # wheel's js_handler trick and emit the live DOM text ourselves — `e.args` is then the
                # typed string (the loopback-debounced model value lags a keystroke, so read the event).
                num.on("keyup", lambda e: self._cb.on_target_limit_preview(e.args),
                       js_handler="(e) => emit(e.target.value)")
                sel = ui.select(list(presets.TARGET_SETS), value=family,
                        on_change=lambda e: self._cb.on_target_change(limit_changed=False)) \
                    .props(_select_props(cb.w - 30)).classes("rtt-preset")  # field = cell − the 30px square (touching, no gap)
            _set_offlist_prompt(sel, family)
            # hovering TILT/OLD previews the family switch, like the other choosers: it rings the target
            # rows the switch would drop (red) / move (amber) in place (see on_chooser_hover's target
            # branch). Same shared option-hover hook; the family select rides the (num, sel) tuple.
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = (num, sel)
        elif name == "temperament":
            # a normal dropdown listing only the rank/limit section dividers and their presets
            # (grouped in the open list). The chosen preset shows in the box; when none matches, a "-" prompt
            # shows there as a display-value placeholder — never a pickable row in the list.
            value = presets.identify(self._editor.state)
            sel = _GroupedSelect(presets.temperament_options(), value=value,
                    is_divider=presets.is_divider,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            # hovering an option in the OPEN dropdown previews loading that temperament (reflow the
            # would-be grid, or redden what it would drop — see on_chooser_hover's temperament branch)
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = sel
        elif name == "prescaler":
            # the predefined-prescalers chooser: log-prime always, the rest (identity / prime) gated
            # behind alt-complexities. "-" when a manual diagonal edit deviates from the named
            # prescaler (editor.displayed_prescaler_name returns None then).
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            sel = ui.select(options, value=value,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            self._arm_option_hover(sel, wrap, cb.id)  # hovering a prescaler previews re-solving to it
            self.selects[cb.id] = sel
        elif name == "projection":
            # the established projection / embedding chooser: the temperament's named rational
            # tunings (its held intervals drive P = GM and G). The base (primes) rides P, the copy
            # (gens) rides G; both show the SAME selection — the chosen tuning's name, or the named
            # tuning matching the auto-picked default — under their own placeholder. "-"-style "off
            # list" shows when the temperament has no established rational tuning (a disabled chooser).
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            value = value if value in options else None
            sel = ui.select(options, value=value,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value, prompt=_projection_prompt(cb.id))
            self._arm_option_hover(sel, wrap, cb.id)  # hovering a tuning previews re-forming P/G to it
            self.selects[cb.id] = sel
        else:  # tuning — systematic scheme names, T-prefixed when targeting a list (not all-interval);
            # a control-refined scheme has no name, shown as the "-" placeholder. Alternative-
            # complexity schemes are gated behind the alt. complexity setting.
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme),
                self._editor.settings["alt_complexity"], self._editor.settings["weighting"])
            # the established scheme's name, or "-" — off the offered list (a finite-power spec the
            # lp-only list omits, or an unnameable one), or a hand-edited / held-off tuning that
            # leaves the scheme (displayed_tuning_scheme_name None). A plain scheme pick stays named.
            name = self._editor.displayed_tuning_scheme_name
            scheme = name if name in options else None
            sel = ui.select(options, value=scheme,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, scheme)
            self._arm_option_hover(sel, wrap, cb.id)  # hovering a scheme previews re-solving to it
            self.selects[cb.id] = sel

    def _update_preset(self, cb):
        # mirror the live selection: the temperament chooser shows the matched preset (or its
        # placeholder), the target chooser splits into limit + family, the tuning chooser shows its
        # scheme. building[0] guards echoes.
        if cb.id.startswith("preset:temperament"):  # base + the comma-basis copy
            if self.gesture is not None and self.gesture.kind == "temp" and self.gesture.reflowed:
                return  # a hover preview reflows the GRID; leave the chooser's value + open popup steady
            value = presets.identify(self._editor.state)
            self.selects[cb.id].value = value
            _set_offlist_prompt(self.selects[cb.id], value)
        elif cb.id == "preset:target":
            num, sel = self.selects[cb.id]
            limit, family = self._target_preset_values()  # (None, None) -> both show "-"
            num.value = _limit_text(limit)  # the text field shows the number (or "-" placeholder)
            sel.value = family
            _set_offlist_prompt(sel, family)
            num.set_enabled(not cb.disabled)  # all-interval greys+locks the chooser (it also shows "-")
            sel.set_enabled(not cb.disabled)
            self._sync_target_limit_error(num, family, limit)  # red iff the shown limit is invalid (even OLD)
        elif cb.id == "preset:prescaler":  # the scheme's prescaler, "-" on a deviating edit; the
            # option list widens/narrows as alt-complexities flips, so refresh it too
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value)
            self.selects[cb.id].set_enabled(not cb.disabled)  # greyed+locked when it's the lone prescaler
        elif cb.id.startswith("preset:projection"):  # base (P) + the embedding (G) copy share one selection
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value, prompt=_projection_prompt(cb.id))
            self.selects[cb.id].set_enabled(not cb.disabled)  # disabled when no established tuning exists
        else:  # tuning — an off-list spec or a hand-edited / held-off tuning shows "-"; a pick stays named
            name = self._editor.displayed_tuning_scheme_name
            # the option LABELS T-prefix only while target-based, so recompute them as the all-
            # interval checkbox flips (set once at creation, they would otherwise go stale)
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme),
                self._editor.settings["alt_complexity"], self._editor.settings["weighting"])
            # a name off the offered list (e.g. a finite-power miniRMS scheme — nameable, but not in
            # the lp-only list) falls back to the "-" placeholder, matching the build path
            scheme = name if name in options else None
            self.selects[cb.id].set_options(options, value=scheme)
            _set_offlist_prompt(self.selects[cb.id], scheme)
            self.selects[cb.id].set_enabled(not cb.disabled)  # greyed+locked when it's the lone scheme

    def _sync_target_limit_error(self, num, family, limit):
        """Render-driven flag for the target chooser's limit field: when the DISPLAYED
        ``(family, limit)`` is invalid (an even limit for the odd-limit diamond), redden the field
        and point its tooltip at the reason; otherwise clear it and restore the normal help. Driven
        from the render (not set imperatively in the handler) so it survives every re-render — an
        imperative flag was wiped the moment anything re-rendered (e.g. ui.select's own validation)."""
        problem = service.target_limit_problem(family, limit)
        num.classes(add="rtt-limit-error" if problem else "",
                    remove="" if problem else "rtt-limit-error")
        if self.target_limit_tip is not None:
            self.target_limit_tip.set_text(
                tooltips.target_limit_help(problem) if problem
                else tooltips.control_help("preset", "preset:target"))
            # the explaining tooltip goes red (a red box) while invalid, plain dark otherwise
            self.target_limit_tip.classes(add="rtt-tip-error" if problem else "",
                                          remove="" if problem else "rtt-tip-error")

    def _build_control_select(self, cb, wrap):  # a weighting chooser (complexity / weight slope)
        sel = ui.select(list(cb.values), value=cb.text or None,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")
        self._arm_option_hover(sel, wrap, cb.id)  # hovering an option previews re-weighting to it
        self.selects[cb.id] = sel

    def _update_control_select(self, cb):  # mirror the live choice; grey it when locked (box 𝒘 all-interval)
        # the complexity chooser's option list widens/narrows as alt. complexity flips, so refresh the
        # options in place (not just the value) — otherwise the build-time list goes stale until the row
        # is rebuilt from hidden. A no-op for the fixed-option slope chooser, whose values never change.
        self.selects[cb.id].set_options(list(cb.values), value=cb.text or None)
        self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_control_check(self, cb, wrap):  # the box-𝐋 "replace diminuator" checkbox (size factor)
        self.checks[cb.id] = ui.checkbox(cb.text, value=cb.checked,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props("dense").classes("rtt-control-check")
        apply = self._control_check_preview(cb)
        if apply is not None:  # hover-preview the cells the toggle would change (red/amber), like the +/-
            self._preview_control(wrap, apply)

    def _control_check_preview(self, cb):
        """The hover-preview op for a control checkbox: the SAME trait flip its click commits, toward the
        toggled state. The state is read live (not captured at build) so a re-render that updates the cell
        in place can't strand a stale target."""
        if cb.id == "control:diminuator":  # swap the complexity size factor (lp ↔ lils)
            return lambda: self._editor.set_diminuator_replaced(
                not service.diminuator_replaced(self._editor.tuning_scheme))
        if cb.id == "control:all_interval":  # collapse the targets to the primes (structural: red + amber)
            return lambda: self._editor.set_all_interval(
                not service.is_all_interval(self._editor.tuning_scheme))
        return None

    def _update_control_check(self, cb):  # mirror the live "replace diminuator" state
        self.checks[cb.id].value = cb.checked

    def _build_formchooser(self, cb, wrap):  # the <choose form> control: canonicalizes its matrix on select
        sel = ui.select({"": "choose form", "canonical": "canonical"}, value="",
                on_change=lambda e, c=cb.id: self._cb.on_form_choose(c, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")
        self._arm_option_hover(sel, wrap, cb.id)  # hovering "canonical" previews canonicalizing in place
        self.selects[cb.id] = sel

    def _update_formchooser(self, cb):  # a one-shot action: snap back to the placeholder
        self.selects[cb.id].value = ""

    # ---- static controls (build only, no update): the domain/comma/interest/held ± buttons,
    # the speaker, and the audio bank glyphs. Their click / JS handlers are baked at build time. ----
    def _preview_control(self, el, apply):
        """Arm a control's hover preview: entering it rings the on-screen cells its click would change
        (control_hover) — red for what it removes, amber for what its re-solve moves — and leaving
        clears them. The click still commits via its own handler. Used by the add/remove +/- buttons
        (each passes the editor op its click runs) and by the generator-tuning sign (previewing
        reversing that generator)."""
        el.on("mouseenter", lambda _=None: self._cb.control_hover(apply))
        el.on("mouseleave", lambda _=None: self._cb.control_unhover())

    def _build_minus(self, cb, wrap):  # remove the highest prime; a hover − centred on the last prime's branch point
        wrap.classes("rtt-minus-zone")  # clear of the editable cell below
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))
        self._preview_control(wrap, self._editor.shrink)

    def _build_plus(self, cb, wrap):  # add a prime; the always-shown + on the bus stub
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.expand))
        self._preview_control(wrap, self._editor.expand)

    def _build_gen_minus(self, cb, wrap):  # drop the last generator (+n, −r); the mapping-row − reached from the column
        wrap.classes("rtt-minus-zone")  # clear of the genmap cell below
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))
        self._preview_control(wrap, lambda i=cb.gen: self._editor.remove_mapping_row(i))

    def _build_gen_plus(self, cb, wrap):  # add a generator: open a blank green draft mapping ROW (the bus stub)
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping"))

    def _build_map_minus(self, cb, wrap):  # remove generator cb.gen (a mapping row); a hover − on the left bus
        wrap.classes("rtt-minus-zone")  # clear of the generator-ratio spine it drops over
        if cb.pending:  # the draft row's −: cancel the add (nothing committed yet, so no preview)
            ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
                .on("click", lambda _=None: self._cb.act(self._editor.cancel_pending_mapping_row))
            return
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))
        self._preview_control(wrap, lambda i=cb.gen: self._editor.remove_mapping_row(i))

    def _build_map_plus(self, cb, wrap):  # add a generator: open a blank green draft mapping ROW (left-bus stub)
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping"))

    def _build_map_drag(self, cb, wrap):  # drag generator row cb.gen onto another row's grip to merge
        # HTML5 drag-to-combine, built EXACTLY like the working column-reorder grip (_build_colgrip):
        # the grip is BOTH the drag SOURCE and a drop TARGET, with a per-element dragover preventDefault
        # marking it a valid drop target. This is the proven path — drop one row's GRIP onto another's
        # to add it in. (A Quasar INPUT cell is not a reliable native drop target; reorder hit the same
        # wall and drops grip-to-grip too. The mapping cells are ALSO armed via _arm_row_target so
        # hovering the row itself previews/accepts where the browser allows it, but the grip always
        # works.) dragstart records the source row + effectAllowed='copy'/setData (copy cursor; Firefox
        # drag-start); dragenter previews; drop commits; dragend clears. src==idx (own row) is a no-op.
        # NOTE: no js dragstart — exactly like reorder. We do NOT set effectAllowed (leaving it the
        # default 'uninitialized', which permits ALL drops incl. copy). Setting effectAllowed='copy'
        # here previously LEFT IT 'none' and blocked every drop — the merge regression. dropEffect on
        # dragover still requests the + (copy) cursor, allowed under 'uninitialized'.
        wrap.classes("rtt-drag-handle rtt-row-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, idx=cb.gen: self._begin_row_drag(idx))
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, idx=cb.gen: self._preview_row_drop(idx))
        wrap.on("dragend", lambda _=None: self._end_row_drag())
        wrap.on("drop.prevent", lambda _=None, idx=cb.gen: self._drop_on_row(idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_row_target(self, wrap, gen):  # make a mapping cell a drop target for its row (gen)
        # the mapping row is the drop target for a dragged generator row: dragover keeps every cell a
        # droppable copy surface (preventDefault makes a drop land here; dropEffect='copy' gives the +
        # cursor), dragenter previews dropping the dragged row INTO this row, drop commits it. The py
        # preview/drop are no-ops unless a row drag is actually in flight (_row_drag set), so a
        # non-combine drag — or a row over its own cells — passing over a cell changes nothing.
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, idx=gen: self._preview_row_drop(idx))
        wrap.on("drop.prevent", lambda _=None, idx=gen: self._drop_on_row(idx))

    def _begin_row_drag(self, idx):
        self._row_drag = idx
        self._cb.combine_begin()

    def _end_row_drag(self):
        self._row_drag = None
        self._cb.combine_end()

    def _preview_row_drop(self, idx):  # hovering target row idx: preview the would-be combine (else revert)
        src = self._row_drag
        valid = src is not None and src != idx  # src == idx (the dragged row's own cells) previews nothing
        apply = (lambda: self._editor.add_mapping_row_to(src, idx)) if valid else None
        # highlight the whole target ROW (its editable mapping cells, which change value but don't ring
        # on their own — they're input cells), so the row being dropped onto is clearly marked.
        target = (lambda cb: cb.kind == "mapping" and getattr(cb, "gen", None) == idx) if valid else None
        self._cb.combine_preview(apply, target)

    def _drop_on_row(self, idx):  # add the dragged generator row into the DIFFERENT row dropped on
        src = self._row_drag
        self._row_drag = None
        if src is not None and src != idx:
            self._cb.combine_commit(lambda: self._editor.add_mapping_row_to(src, idx))
        else:
            self._cb.combine_end()  # dropped on its own row / nothing: just revert the preview

    # the interval-column twin of the mapping-row drag. The grip is the SOURCE; the DROP TARGETS are
    # the interval cells in the SAME column (each armed by _arm_col_target). Drag one interval onto a
    # DIFFERENT interval in its column to ADD it in (their product). The source's (group, index) is
    # held server-side; _int_combine enforces the same-column, distinct-interval rule and the
    # dragenter preview shows what a drop will do.
    _INTERVAL_COMBINE = {
        "comma": "add_comma_to", "target": "add_target_to",
        "held": "add_held_to", "interest": "add_interest_to",
    }

    def _build_int_drag(self, cb, wrap):  # drag an interval's grip onto another's grip (same column) to merge
        group = cb.id.split(":")[1]  # int_drag:<group>:<index>
        # the column twin of _build_map_drag: the grip is BOTH source and drop target (drop grip-to-grip,
        # the proven path), and the interval cells are also armed (_arm_col_target) for hovering the column.
        wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, g=group, idx=cb.comma: self._begin_col_drag(g, idx))
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, g=group, idx=cb.comma: self._preview_int_drop(g, idx))
        wrap.on("dragend", lambda _=None: self._end_col_drag())
        wrap.on("drop.prevent", lambda _=None, g=group, idx=cb.comma: self._drop_on_interval(g, idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_col_target(self, wrap, group, idx):  # make an interval cell a drop target for its column
        # the column twin of _arm_row_target: dragover keeps the cell a droppable copy surface, the py
        # dragenter previews / drop commits the combine, gated server-side to the same column and a
        # DIFFERENT interval (see _int_combine), so a non-matching drag over the cell does nothing.
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: self._preview_int_drop(g, i))
        wrap.on("drop.prevent", lambda _=None, g=group, i=idx: self._drop_on_interval(g, i))

    def _int_combine(self, group, idx):  # the combine callable for dropping the dragged interval here, or None
        if self._col_drag is None:
            return None
        src_group, src = self._col_drag
        if src_group != group or src == idx:  # same column only, and onto a DIFFERENT interval
            return None
        combine = getattr(self._editor, self._INTERVAL_COMBINE[group])
        return lambda: combine(src, idx)

    def _begin_col_drag(self, group, idx):
        self._col_drag = (group, idx)
        self._cb.combine_begin()

    def _end_col_drag(self):
        self._col_drag = None
        self._cb.combine_end()

    _GROUP_CELL_KIND = {"comma": "commacell", "target": "targetcell",
                        "held": "heldcell", "interest": "interestcell"}

    def _preview_int_drop(self, group, idx):  # hovering target (group, idx): preview the combine (else revert)
        apply = self._int_combine(group, idx)
        kind = self._GROUP_CELL_KIND[group]  # highlight the whole target COLUMN (its editable cells)
        target = (lambda cb: cb.kind == kind and getattr(cb, "comma", None) == idx) if apply is not None else None
        self._cb.combine_preview(apply, target)

    def _drop_on_interval(self, group, idx):  # add the dragged interval into the one it was dropped on
        apply = self._int_combine(group, idx)
        self._col_drag = None
        if apply is not None:
            self._cb.combine_commit(apply)
        else:
            self._cb.combine_end()

    def _build_basis_minus(self, cb, wrap):  # the domain − on the interval-vectors row's left bus
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))
        self._preview_control(wrap, self._editor.shrink)

    def _build_comma_minus(self, cb, wrap):  # each comma's − un-tempers just that comma; the draft's − cancels it
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_comma, self._editor.remove_comma)

    # the + that opens a blank, off-screen draft column (comma / interest / held / target) gets NO
    # hover preview: the new column is empty and not yet placed, so nothing on screen would change —
    # only removes and the re-solving adds (a prime, un-tempering a comma) have on-screen cells to ring.
    def _build_comma_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_comma, "comma"))

    def _build_element_plus(self, cb, wrap):  # nonstandard-domain box on: open a blank ?/? element draft
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_element, "element"))

    def _build_element_minus(self, cb, wrap):  # nonstandard-domain box on: the domain − (both axes)
        # one builder for every nonstandard-domain −, told apart by id (like _build_list_minus): a
        # ":pending" draft cancels the ?/? draft (remove_element), any other removes that committed
        # element (remove_domain_element, carrying its index as cb.prime). The ":basis" ids are the
        # interval-vectors spine's, revealed vertically on the left bus (rtt-minus-btn-v) like
        # _build_basis_minus; the quantities-row ids reveal above the header (rtt-minus-btn).
        action = self._editor.remove_element if cb.id.endswith(":pending") \
            else (lambda idx=cb.prime: self._editor.remove_domain_element(idx))
        btn = "rtt-minus-btn-v" if ":basis" in cb.id else "rtt-minus-btn"
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes(f"rtt-glyph {btn}") \
            .on("click", lambda _=None: self._cb.act(action))
        self._preview_control(wrap, action)

    def _build_list_minus(self, cb, wrap, cancel, remove):
        # an interval-list column's − (interest / held / target): the draft column's cancels the
        # draft, every other drops just its interval (cb.comma) — each is independently removable
        action = cancel if cb.id.endswith(":pending") else (lambda idx=cb.comma: remove(idx))
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(action))
        self._preview_control(wrap, action)

    def _build_interest_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_interest, self._editor.remove_interest)

    def _build_interest_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_interest, "interest"))

    def _build_held_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_held, self._editor.remove_held)

    def _build_held_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_held, "held"))

    def _build_target_minus(self, cb, wrap):
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_target, self._editor.remove_target)

    def _build_target_plus(self, cb, wrap):
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_target, "target"))

    def _build_colgrip(self, cb, wrap):  # a per-column drag handle / drop target on the fan gridline:
        # drag one column's grip onto another to MOVE/reorder it; the per-list "grip:{list}:add" zone
        # is drop-only — the append / into-empty-list target on the stub gridline, so dropping into a
        # list is always "drop on the gridline" (no separate header/+ target). Mirrors the proven
        # drag-to-combine handle EXACTLY (which the user confirmed works), so it relies on no global
        # drag.js / dragging-class: a grip is BOTH source AND drop target, with a per-element dragover
        # preventDefault (client-side, so it doesn't round-trip per move) marking it a valid target.
        # The dragged column's (list, idx) is held server-side from dragstart through drop.
        _, lst, tail = cb.id.split(":")  # "grip:{list}:{idx}" — idx is "add" for the append/empty zone
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")  # mark a valid drop target
        if tail == "add":  # drop-only: an empty list still gets a gridline target (nothing to drag here)
            wrap.classes("rtt-colgrip rtt-coldrop")
            # hovering the gridline previews appending the dragged column here; dropping commits it
            wrap.on("dragenter.prevent", lambda _=None, l=lst: self._cb.on_drag_enter(l, None))
            wrap.on("drop.prevent", lambda _=None, l=lst: self._cb.on_drop(l, None))
            return
        idx = cb.comma  # the grip is index-keyed (slot-bound): it stays at its slot while a reorder
        # glides the value columns, so its slot index never goes stale and it doesn't move under the cursor
        wrap.classes("rtt-drag-handle rtt-colgrip").props("draggable=true")
        wrap.on("dragstart", lambda _=None, l=lst, i=idx: self._cb.on_drag_start(l, i))
        # hovering a column previews the would-be move (the columns slide to open the drop slot) before
        # the drop commits it — so you see where the column will land while still dragging
        wrap.on("dragenter.prevent", lambda _=None, l=lst, i=idx: self._cb.on_drag_enter(l, i))
        wrap.on("dragend", lambda _=None: self._cb.on_drag_end())
        wrap.on("drop.prevent", lambda _=None, l=lst, i=idx: self._cb.on_drop(l, i))
        ui.icon("drag_indicator").classes("rtt-grip")


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    # Give every tooltip a show delay so the dense grid's hover help waits for a deliberate rest
    # rather than popping the instant the cursor crosses a control. Setting it on the Tooltip
    # element's default props covers the whole population at once — chrome, Show toggles, grid
    # controls and any future tooltip — with no per-call wiring to keep in sync. Idempotent: it
    # re-sets the same class default each page build.
    ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS}")
    # the audio rows' Web Audio engine + its glyph variants (shared markup for click redraws)
    ui.add_body_html(f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>")
    # keep the frozen title bands pinned to the scrolling grid pane (see _FREEZE_JS)
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
    # live int<->ratio switching for the editable stacked fraction cells (see _FRACTION_JS)
    ui.add_body_html(f"<script>{_FRACTION_JS}</script>")
    # trim NiceGUI's default 16px content padding to a slim margin around the whole app
    ui.query(".nicegui-content").style("padding:6px")

    # Dark mode is a global VIEWING preference, kept out of the document's Show settings: it
    # persists under its own store key, so "select all / none" and Reset — which act only on
    # editor.settings — never touch it. apply_theme drives the CSS overlay (assets/rtt-dark.css)
    # by toggling the `rtt-dark` class on <body>, and paints the margin frame inline (its colour
    # beats Quasar's body background the same way the static "#fff" did before).
    dark_mode = [bool(_doc_store().get(_DARK_KEY, False))]

    def _dark_icon():  # the sun/moon glyph shows the theme a click will switch TO
        return "light_mode" if dark_mode[0] else "dark_mode"  # a sun to go light, a moon to go dark

    def apply_theme():
        body = ui.query("body")
        body.classes(add="rtt-dark") if dark_mode[0] else body.classes(remove="rtt-dark")
        body.style(f"background:{_DARK_FRAME if dark_mode[0] else '#fff'}")

    def on_dark_toggle():
        dark_mode[0] = not dark_mode[0]
        _doc_store()[_DARK_KEY] = dark_mode[0]
        apply_theme()
        dark_btn.props(f"icon={_dark_icon()}")  # swap the glyph to the new target theme

    apply_theme()  # paint the persisted theme up front, before the grid builds (no flash)

    # The Editor owns the whole document — temperament, view selections, the Show
    # settings (editor.settings) and the folded rows/columns/tiles (editor.collapsed) —
    # and the undo/redo history over all of it. We persist that document per browser
    # (app.storage.user) so a refresh restores exactly where the user left off; a
    # corrupt/old blob is ignored, falling back to the as-shipped defaults.
    editor = Editor()
    stored = _doc_store().get(_STORE_KEY)
    if stored:
        try:
            editor.load(stored)
        except Exception:
            pass
    rec = _Reconciler(editor)
    building = [False]
    last_lay = [None]  # the most recently built layout, so the master toggle can read its foldable bands
    refs: dict = {}
    target_limit_commit = [None]  # pending debounced commit task for the target-limit wheel

    def _on_disconnect():
        # a pending target-limit debounce must not outlive the page: if the user leaves mid-
        # gesture, cancel it so the commit never renders into a gone client (which would just log
        # an error). And a gesture holding the document in a hypothetical state (a drag / temp-grow
        # whose dragend/popup-hide was lost with the socket) must restore the real document, or it
        # would block persistence indefinitely (see render's persist guard).
        if target_limit_commit[0] is not None:
            target_limit_commit[0].cancel()
        end_gesture()

    ui.context.client.on_disconnect(_on_disconnect)
    # install the shared chooser-option hover delegation once per page (inert until a dropdown opens)
    ui.run_javascript(_OPTION_HOVER_DELEGATION)
    # dismiss any hover tooltip on pointerdown so it can't strand when the click removes/reflows its
    # anchor (the +/- buttons rebuild the grid out from under the cursor — see _TOOLTIP_DISMISS_JS)
    ui.run_javascript(_TOOLTIP_DISMISS_JS)

    def col_tokens(name):
        # the previous render's id-tokens for a reorderable interval list, in column order — so an
        # edit handler reads each column's cells by the token its id actually carries (== the index
        # until the list is reordered), not the bare index
        ids = last_lay[0].identities if last_lay[0] is not None else None
        return [tok for tok, _ in (ids or {}).get(name, [])]

    # ---- The declarative preview-ring core ------------------------------------------------------
    # The ring highlights (amber rtt-preview-change / red rtt-preview-remove) are a PURE FUNCTION
    # of (document, rec.gesture), recomputed and repainted in full on every paint — render() ends
    # with a paint, and gesture transitions that don't move the document paint directly. Nothing
    # else ever touches the ring classes, so a ring structurally cannot survive its gesture: every
    # commit renders, every render repaints from state. (This replaced two parallel mechanisms — a
    # direct class-poke and a baseline render-diff — coordinated by ~10 flags, whose missed clear
    # paths were the recurring stranded-highlight bugs.)

    gesture_rendering = [False]  # True while a gesture's OWN handler renders (drag hover, temp grow)

    def gesture_render():
        # a render initiated by the live gesture itself (a drag's reflow preview, a temperament
        # grow), exempt from render()'s ends-foreign-gestures guard
        gesture_rendering[0] = True
        try:
            render()
        finally:
            gesture_rendering[0] = False

    def end_gesture():
        # The ONE way a gesture dies. A gesture holding a token has the document in a hypothetical
        # state (drag hover, temperament grow) — restore it FIRST, so whatever runs next (a commit,
        # a render) acts on the real document. Returns the ended gesture (or None) so callers can
        # ask whether it had reflowed. Never null rec.gesture directly.
        g, rec.gesture = rec.gesture, None
        if g is not None and g.token is not None:
            editor.restore_for_preview(g.token)
        return g

    def compute_rings(lay):
        # the amber ("value would move" / "value moved") and red ("would be removed") cell-id sets
        # for the current gesture against layout `lay` — the pure function the painter applies.
        # The layout contributes its OWN steady reds independent of any gesture: a builder-driven
        # cb.preview_remove (the value a pending comma draft will delete — the doomed unchanged
        # interval) is render-state, painted with the same red look and kept until the draft
        # closes (the next build without the flag drops it from the set).
        static_red = frozenset(cb.id for cb in lay.cells if cb.preview_remove)
        amber, red = _gesture_rings(lay)
        return amber, red | static_red

    def _gesture_rings(lay):
        # the active gesture's contribution to the ring sets (empty when no gesture is live)
        g = rec.gesture
        if g is None:
            return frozenset(), frozenset()
        if g.apply is not None:
            # hypothetical mode: the document is unchanged; diff the gesture's base (the focus-time
            # baseline for an edit, else the current grid) against the would-be layout, painting on
            # the CURRENT grid — no reflow, so a hovered control never slides from under the cursor.
            # Cells the op would ADD exist only in `hyp`, so they can't ring (off-screen until
            # committed); cells it would REMOVE are still on screen, so red can mark them.
            base = g.baseline if g.baseline is not None else lay
            token = editor.capture_for_preview()
            try:
                g.apply()
                hyp = editor.layout(prev_ids=base.identities)
                amber = spreadsheet.changed_cell_ids(base, hyp)
                # RED marks the rows ON SCREEN NOW that the op would remove, so it must diff the
                # CURRENT layout (`lay`) against `hyp`, NOT the focus-time `base`. An edit gesture
                # commits in place while still focused (a wheeled / typed target limit lands and
                # reflows the grid without ending the gesture), so the on-screen grid can differ
                # from the focus snapshot: e.g. focus at 6-TILT, commit UP to 8-TILT (rows 8/9
                # appear), then preview back DOWN — rows 8/9 are on screen and dropped, but they're
                # absent from the stale `base`, so `removed_cell_ids(base, hyp)` would miss them
                # (and symmetrically a shrunk grid would mark rows no longer present). `lay` is the
                # truth for what's paintable. AMBER stays against `base` — it's the "what your edit
                # moved since you focused" feedback, which is exactly the focus-relative diff.
                red = spreadsheet.removed_cell_ids(lay, hyp)
            finally:
                editor.restore_for_preview(token)  # leave no trace
            return amber - {g.source}, red
        if g.baseline is not None:
            # live mode: the document has moved (committed keystrokes / wheel notches / a
            # temporarily-applied drag or temperament-grow) — diff the arm-time baseline against
            # the current grid. Red never applies here: anything removed is already off-screen.
            amber = spreadsheet.changed_cell_ids(g.baseline, lay) - {g.source}
            if g.target_pred is not None:  # drag-combine: also ring the dropped-on row/column's
                # editable cells (their input values aren't in the layout content signature)
                amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
            return amber, frozenset()
        return frozenset(), frozenset()

    def paint_cell(eid, amber, red):
        # idempotently set one cell's ring classes from the computed sets (NiceGUI's classes() is
        # change-detected, so a no-op repaint sends nothing over the socket)
        el = rec.els.get(eid)
        if el is None:
            return  # a ring id with no DOM element (nothing on screen to mark) — skip
        el.classes(add="rtt-preview-change" if eid in amber else "",
                   remove="" if eid in amber else "rtt-preview-change")
        el.classes(add="rtt-preview-remove" if eid in red else "",
                   remove="" if eid in red else "rtt-preview-remove")

    def paint_rings():
        # repaint every cell's rings from the current gesture WITHOUT a render — the path for
        # gesture transitions that don't move the document (hover arm/disarm, a keystroke's new
        # candidate, blur). render() does the same sweep itself at the end of its cell pass.
        lay = last_lay[0]
        if lay is None:
            return
        amber, red = compute_rings(lay)
        for cb in lay.cells:
            paint_cell(cb.id, amber, red)

    def take_over_gesture():
        # end the live gesture so a new one can arm: the token (if any) restores the real
        # document, and a temperament grow-preview that had REFLOWED the grid rebuilds it
        was = end_gesture()
        if was is not None and was.reflowed:
            gesture_render()

    def _edit_candidate(apply):
        # a keystroke's new preview candidate for the focused cell: the editor thunk the typed
        # value WOULD commit, or None when the entry is invalid/incomplete/a draft (previews
        # nothing). NO commit — the value lands only on Enter/blur.
        g = rec.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        paint_rings()

    def _rebase_edit_gesture():
        # a DRAFT column just materialized under the focused cell (the green pending vector
        # committed the moment its last value was typed — no blur fires, so the edit gesture
        # stays armed). The change is APPLIED, so its rings must go away immediately: rebase the
        # gesture on the just-rendered grid — the diff against the new reality is empty, and any
        # CONTINUED typing previews against the committed state. (Without this, the commit's
        # render rings everything the new column moved, stranded until the user clicks elsewhere
        # — the reported submit-a-held-interval bug.)
        g = rec.gesture
        if g is not None and g.kind == "edit":
            g.baseline = last_lay[0]
            paint_rings()

    def on_mapping_change(preview=False):
        # commit (Enter/blur), or with preview=True (live, on each keystroke) ring the cells the typed
        # matrix WOULD move without committing. An incomplete / improper entry rings nothing (no toast)
        # while previewing; only the commit toasts + reverts.
        if building[0] or not editor.settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        if editor.pending_mapping_row is not None:
            # the draft row rides at index r; hand its cells to the editor, which commits (and
            # re-ranks) once they form a proper, independent generator. Like the comma draft, the row
            # is off-screen-until-committed for preview purposes, so a preview pass rings nothing.
            if any(f"cell:mapping:{r}:{p}" not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return  # the draft cells aren't shown (folded away)
            if preview:
                _edit_candidate(None)
                return
            editor.set_pending_mapping_row([_parse_int(rec.inputs[f"cell:mapping:{r}:{p}"].value) for p in range(d)])
            committed = editor.pending_mapping_row is None  # the draft materialized into a real row
            render()
            if committed:
                _rebase_edit_gesture()  # the change is applied — its rings go away NOW (no blur fires)
            return
        matrix = [[_parse_int(rec.inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            if preview:
                _edit_candidate(None)
            return
        if not service.is_proper_temperament(matrix):
            if preview:
                _edit_candidate(None)  # an improper in-progress matrix previews nothing (no toast)
                return
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
            render()  # revert the cells to the current temperament
            return
        if preview:
            _edit_candidate(lambda: editor.edit_mapping(matrix))
            return
        editor.edit_mapping(matrix)
        render()

    def _draft_comma_reranks(values):
        # whether a complete draft comma is independent of the basis — so committing it raises the
        # nullity (drops the rank), the change worth previewing. Mirrors editor.set_pending_comma's
        # own commit guard, so the preview fires exactly when the blur would commit + re-rank.
        if any(v is None for v in values):
            return False
        new_comma = tuple(int(v) for v in values)
        domain = editor.state.domain_basis if len(new_comma) == editor.state.d else None
        return service.from_comma_basis(editor.state.comma_basis + (new_comma,), domain).n > editor.state.n

    def on_comma_change(preview=False):
        # the comma basis (the mapping's dual) is edited in the interval-vectors row, present
        # independent of the temperament boxes. preview=True rings the would-be change without
        # committing (commit lands on Enter/blur); a complete draft comma previews its would-be
        # commit (the rank drop), an incomplete or dependent one rings nothing.
        if building[0]:
            return
        d, nc = editor.state.d, len(editor.state.comma_basis)
        if editor.pending_comma is not None:
            # the draft column rides at index nc; hand its cells to the editor, which
            # commits (and re-ranks) once they form a valid independent comma
            if any(f"cell:comma:{p}:{nc}" not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return  # the draft cells aren't shown (folded away)
            values = [_parse_int(rec.inputs[f"cell:comma:{p}:{nc}"].value) for p in range(d)]
            if preview:
                # a complete, independent draft comma WILL commit and re-rank on blur — the rank
                # drops, so the last mapping row goes (red) and the survivors recombine, while the
                # rest of the temperament re-solves (amber). Preview that whole commit by arming it
                # as the edit candidate; capture/restore sandboxes the would-be set_pending_comma, so
                # nothing lands on the live document until blur. An incomplete or dependent draft (no
                # re-rank, like the off-screen draft column this used to skip) still rings nothing.
                _edit_candidate((lambda v=values: editor.set_pending_comma(v))
                                if _draft_comma_reranks(values) else None)
                return
            editor.set_pending_comma(values)
            committed = editor.pending_comma is None  # the draft materialized into a real column
            render()
            if committed:
                _rebase_edit_gesture()  # the change is applied — its rings go away NOW (no blur fires)
            return
        if any(f"cell:comma:{p}:{c}" not in rec.inputs for c in range(nc) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return  # the comma cells aren't currently shown (folded away)
        # the comma cells are the basis transposed (prime down the rows, comma across)
        basis = [[_parse_int(rec.inputs[f"cell:comma:{p}:{c}"].value) for p in range(d)] for c in range(nc)]
        if any(v is None for comma in basis for v in comma):
            if preview:
                _edit_candidate(None)
            return
        if not service.is_proper_temperament(service.from_comma_basis(basis).mapping):
            if preview:
                _edit_candidate(None)
                return
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
            render()
            return
        if preview:
            _edit_candidate(lambda: editor.edit_comma_basis(basis))
            return
        editor.edit_comma_basis(basis)
        render()

    def on_unchanged_change(preview=False):
        # the unchanged basis U is editable when it is a full rational projection (like the comma
        # basis): read its d-tall columns and set the tuning to the projection that holds them. A
        # silent revert when they don't form a valid full projection. Mirrors on_comma_change.
        if building[0]:
            return
        d, r = editor.state.d, editor.state.r
        if any(f"cell:unchanged:{p}:{j}" not in rec.inputs for j in range(r) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return  # U isn't editable (under-rank) or not shown
        vectors = [[_parse_int(rec.inputs[f"cell:unchanged:{p}:{j}"].value) for p in range(d)] for j in range(r)]
        if any(v is None for vec in vectors for v in vec):
            if preview:
                _edit_candidate(None)
            return  # an in-progress / non-integer edit
        try:
            ratios = service.comma_ratios(tuple(tuple(v) for v in vectors), editor.state.domain_basis)
        except (ValueError, ZeroDivisionError, ArithmeticError):
            if preview:
                _edit_candidate(None)
            return
        if preview:
            _edit_candidate(lambda: editor.set_unchanged_basis(ratios))
            return
        editor.set_unchanged_basis(ratios)
        render()

    def on_interest_change(preview=False):
        # the intervals of interest are edited as vectors in the interval-vectors row, like the comma
        # basis; read the d-tall columns and replace the set. preview=True rings without committing.
        if building[0]:
            return
        d, mi = editor.state.d, len(editor.interest_vectors)
        toks = col_tokens("interest")  # each column's id-token (== its index until reordered)
        if editor.pending_interest is not None:
            # the draft column rides one token past the committed ones; commit it once filled
            pt = spreadsheet.pending_token(toks)
            if any(f"cell:interest:{p}:{pt}" not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return  # the draft cells aren't shown (folded away)
            if preview:
                _edit_candidate(None)  # a draft column is off-screen until committed — preview nothing
                return
            editor.set_pending_interest([_parse_int(rec.inputs[f"cell:interest:{p}:{pt}"].value) for p in range(d)])
            committed = editor.pending_interest is None  # the draft materialized into a real column
            render()
            if committed:
                _rebase_edit_gesture()  # the change is applied — its rings go away NOW (no blur fires)
            return
        if len(toks) != mi or any(f"cell:interest:{p}:{toks[i]}" not in rec.inputs for i in range(mi) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return  # the interest cells aren't currently shown (folded away)
        vectors = [[_parse_int(rec.inputs[f"cell:interest:{p}:{toks[i]}"].value) for p in range(d)] for i in range(mi)]
        if any(v is None for m in vectors for v in m):
            if preview:
                _edit_candidate(None)
            return
        if preview:
            _edit_candidate(lambda: editor.set_interest_vectors(vectors))
            return
        editor.set_interest_vectors(vectors)
        render()

    def on_held_change(preview=False):
        # the held intervals are edited as vectors in the interval-vectors row, like the intervals of
        # interest; read the d-tall columns and replace the held set. preview=True rings, no commit.
        if building[0]:
            return
        d, nh = editor.state.d, len(editor.held_vectors)
        toks = col_tokens("held")  # each column's id-token (== its index until reordered)
        if editor.pending_held is not None:
            # the draft column rides one token past the committed ones; commit it once filled
            pt = spreadsheet.pending_token(toks)
            if any(f"cell:held:{p}:{pt}" not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return  # the draft cells aren't shown (folded away)
            if preview:
                _edit_candidate(None)  # a draft column is off-screen until committed — preview nothing
                return
            editor.set_pending_held([_parse_int(rec.inputs[f"cell:held:{p}:{pt}"].value) for p in range(d)])
            committed = editor.pending_held is None  # the draft materialized into a real column
            render()
            if committed:
                _rebase_edit_gesture()  # the change is applied — its rings go away NOW (no blur fires)
            return
        if len(toks) != nh or any(f"cell:held:{p}:{toks[i]}" not in rec.inputs for i in range(nh) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return  # the held cells aren't currently shown (folded away / optimization off)
        vectors = [[_parse_int(rec.inputs[f"cell:held:{p}:{toks[i]}"].value) for p in range(d)] for i in range(nh)]
        if any(v is None for m in vectors for v in m):
            if preview:
                _edit_candidate(None)
            return
        if preview:
            _edit_candidate(lambda: editor.set_held_vectors(vectors))
            return
        editor.set_held_vectors(vectors)
        render()

    def on_target_cells_change(preview=False):
        # the target interval list is edited as vector columns, like the comma basis; read the d-tall
        # columns (id is cell:vec:targets:{column}:{prime}) and replace the target set. preview=True
        # rings without committing (commit lands on Enter/blur); a draft column previews nothing.
        if building[0]:
            return
        d = editor.state.d
        targets = editor.target_override or service.target_interval_set(
            editor.target_spec, editor.state.domain_basis)
        k = len(targets)
        toks = col_tokens("targets")  # each column's id-token (== its index until reordered)
        if editor.pending_target is not None:
            # the draft column rides one token past the committed ones; commit it once filled
            pt = spreadsheet.pending_token(toks)
            if any(f"cell:vec:targets:{pt}:{p}" not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return  # the draft cells aren't shown (folded away)
            if preview:
                _edit_candidate(None)  # a draft column is off-screen until committed — preview nothing
                return
            editor.set_pending_target([_parse_int(rec.inputs[f"cell:vec:targets:{pt}:{p}"].value) for p in range(d)])
            committed = editor.pending_target is None  # the draft materialized into a real column
            render()
            if committed:
                _rebase_edit_gesture()  # the change is applied — its rings go away NOW (no blur fires)
            return
        if len(toks) != k or any(f"cell:vec:targets:{toks[j]}:{p}" not in rec.inputs for j in range(k) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return  # the target cells aren't currently shown (folded away)
        vectors = [[_parse_int(rec.inputs[f"cell:vec:targets:{toks[j]}:{p}"].value) for p in range(d)] for j in range(k)]
        if any(v is None for m in vectors for v in m):
            if preview:
                _edit_candidate(None)
            return
        if preview:
            _edit_candidate(lambda: editor.set_target_override_vectors(vectors))
            return
        editor.set_target_override_vectors(vectors)
        render()

    def on_ratio_change(cid):
        # a quantities-row ratio cell committing on blur (comma / target / held / interest) — the
        # scalar twin of the interval-vectors row's column edit. The typed fraction parses to a
        # vector and routes through the SAME setter the vector edit uses; a ":pending" draft fills
        # that column's draft instead (like typing its vector cells). render() always runs: a valid
        # edit shows the new value, an invalid one snaps the field back — and a bad fraction also
        # toasts WHY (unparseable vs outside the prime limit). An untouched "?/?" draft or a cleared
        # cell is a silent no-op (no toast), not an error.
        if building[0] or cid not in rec.inputs:
            return
        group, tok = cid.split(":")  # the column's id-TOKEN, not its index — a reorder decouples them
        raw = rec.cell_value(cid)  # the cell's "num/den" (a fraction cell rejoins its two fields)
        if raw in ("", "?/?"):  # an untouched draft placeholder or a cleared cell
            render()
            return
        try:
            vector = service.interval_vector(raw, editor.state.d, editor.state.domain_basis)
        except ValueError as exc:
            ui.notify(str(exc), type="negative", position="top")
            render()  # revert the field to its current value
            return

        def replace(current, setter):  # swap the edited column in, skipping a no-op blur (no undo step)
            # the token's CURRENT list index: identity-keyed columns may have been reordered, so map
            # the token through the live identities (commas aren't reorderable, so token IS the index)
            list_name = {"target": "targets", "held": "held", "interest": "interest"}.get(group)
            toks = col_tokens(list_name) if list_name else []
            pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
            vectors = [list(v) for v in current]
            if vectors[pos] != list(vector):
                vectors[pos] = vector
                setter(vectors)

        if tok == "pending":  # fill the draft column, committing it like its vector cells do
            {"comma": editor.set_pending_comma, "interest": editor.set_pending_interest,
             "held": editor.set_pending_held, "target": editor.set_pending_target}[group](vector)
        elif group == "comma":
            replace(editor.state.comma_basis, editor.edit_comma_basis)
        elif group == "interest":
            replace(editor.interest_vectors, editor.set_interest_vectors)
        elif group == "held":
            replace(editor.held_vectors, editor.set_held_vectors)
        elif group == "unchanged":
            # the unchanged-interval ratios drive the projection as a WHOLE: read the full basis (this
            # column's new ratio + the others) and retune to the projection that holds it — the scalar
            # twin of editing the U vectors (on_unchanged_change)
            ratios = [rec.cell_value(f"unchanged:{j}") for j in range(editor.state.r)
                      if f"unchanged:{j}" in rec.inputs]
            if len(ratios) == editor.state.r and all(ratios):
                editor.set_unchanged_basis(tuple(ratios))
        else:  # target
            targets = editor.target_override or service.target_interval_set(
                editor.target_spec, editor.state.domain_basis)
            replace(service.target_interval_vectors(targets, editor.state.d, editor.state.domain_basis),
                    editor.set_target_override_vectors)
        render()

    def on_element_change(cid):
        # a chapter-9 domain basis element committing on blur (nonstandard-domain box on). cid is
        # "prime:{index}" (a relabel) or "prime:pending" (the ?/? draft -> add held just). render()
        # always runs: a valid relabel/add shows the new basis, an invalid entry snaps the field
        # back and toasts why. A cleared / unchanged cell is a silent no-op (no toast, no undo step).
        if building[0] or cid not in rec.inputs:
            return
        raw = rec.cell_value(cid)  # the cell's "num/den" (a fraction cell rejoins its two fields)
        tok = cid.split(":")[1]
        if raw in ("", "?/?"):  # an untouched draft placeholder or a cleared cell
            render()
            return
        # parse first, toasting why on failure — the same parse-then-act pattern the interval ratio
        # cells use (on_ratio_change), so the ?/? draft and a relabel report invalid input alike
        parsed = service.parse_domain_element(raw)
        if parsed is None:
            ui.notify(f"“{raw}” is not a positive rational basis element (≠ 1)",
                      type="negative", position="top")
            render()
            return
        if tok == "pending":  # the draft column -> add a new element held just
            if not service.can_add_domain_element(editor.state, parsed):
                ui.notify(f"{raw} isn’t independent of the existing basis", type="negative", position="top")
                render()
                return
            editor.set_pending_element(raw)  # valid -> commits and clears the draft
            render()
            return
        index = int(tok)
        if parsed == editor.state.domain_basis[index]:
            return  # a no-op blur (the element is unchanged) — no undo step
        if not service.can_set_domain_element(editor.state, index, parsed):
            ui.notify(f"{raw} would make the basis dependent", type="negative", position="top")
            render()  # revert the field to the current element
            return
        editor.set_domain_element(index, raw)
        render()

    def on_element_preview(cid):
        # live edit preview: as a VALID element is typed into a domain cell, set the candidate the
        # relabel / held-just add would commit — the rings paint from it WITHOUT committing (the
        # scalar ratio cells commit on blur, so they don't get the per-keystroke vector cells'
        # preview for free). An invalid / unchanged value previews nothing.
        g = rec.gesture
        if building[0] or g is None or g.kind != "edit" or g.source != cid or cid not in rec.inputs:
            return
        raw = rec.cell_value(cid)  # the cell's "num/den" (a fraction cell rejoins its two fields)
        tok = cid.split(":")[1]
        parsed = service.parse_domain_element(raw) if raw not in ("", "?/?") else None
        if tok == "pending":
            valid = parsed is not None and service.can_add_domain_element(editor.state, parsed)
        else:
            valid = (parsed is not None and parsed != editor.state.domain_basis[int(tok)]
                     and service.can_set_domain_element(editor.state, int(tok), parsed))
        if not valid:
            _edit_candidate(None)  # nothing valid to preview (yet)
        elif tok == "pending":
            _edit_candidate(lambda: editor.set_pending_element(raw))  # the held-just add
        else:
            _edit_candidate(lambda: editor.set_domain_element(int(tok), raw))  # the relabel

    def on_power_change(cid):
        # editable power inputs share this kind: optimization:power drives the Lp optimization
        # power; control:q drives the interval-complexity norm power (box 𝒄). Same parse (∞ or a
        # positive number); an unparseable / out-of-range entry leaves the scheme unchanged.
        if building[0] or cid not in rec.inputs:
            return
        if cid not in ("optimization:power", "control:q"):
            return
        raw = str(rec.inputs[cid].value).strip().lower()
        if raw in ("∞", "inf", "max", "minimax"):
            power = float("inf")
        else:
            try:
                power = float(raw)
            except ValueError:
                return  # leave the scheme unchanged on unparseable input
            if power <= 0:
                return
        if cid == "control:q":
            if power < 1:
                return  # an Lq norm power must be ≥ 1
            editor.set_complexity_norm_power(power)
        else:
            editor.set_optimization_power(power)
        render()

    def on_gentuning_change(cid):
        # an editable generator-tuning-map cell: a valid cents number overrides that one
        # generator's tuning (a per-number manual override); an unparseable entry is ignored
        if building[0] or cid not in rec.inputs:
            return
        try:
            cents = float(str(rec.inputs[cid].value).strip())
        except ValueError:
            return
        i = int(cid.rsplit(":", 1)[1])
        # "tuning:ssgen:i" is a superspace generator 𝒈L cell (prime-based shift); "tuning:gen:i" the
        # on-domain 𝒈. Each routes to its own manual-tuning setter.
        if ":ssgen:" in cid:
            editor.set_superspace_generator_tuning_component(i, cents)
        else:
            editor.set_generator_tuning_component(i, cents)
        render()

    def on_gentuning_wheel(cid, delta_y):
        # the genmap cell's hover-and-scroll fine-adjust: each wheel notch nudges this generator's
        # tuning by a thousandth of a cent — scroll up (deltaY < 0) raises it, down lowers it. The
        # cents face shows 3 dp, so one notch moves the last shown digit by one.
        if building[0] or not delta_y:
            return
        i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
        if ":ssgen:" in cid:  # a superspace generator 𝒈L cell (prime-based shift)
            editor.nudge_superspace_generator_tuning_component(i, steps)
        else:
            editor.nudge_generator_tuning_component(i, steps)
        render()

    def on_value_wheel(cid, delta_y):
        # step a focused numeric input by one notch — the per-kind amount in _WHEEL_STEPS (±1 for a
        # matrix/vector or power entry, ±0.001 for a prescaler weight). Setting the input's value
        # fires its OWN on_change (on_mapping_change / on_power_change / on_prescaler_change / …),
        # which validates, applies, and re-renders — so a notch travels the exact path a typed value
        # does, with no per-kind dispatch here. A blank cell starts from 0. The client only emits for
        # the focused cell (see _INT_WHEEL_JS), so this is always a deliberate edit, never a stray
        # scroll. Generic over kind: a new numeric input scrolls the moment it is added to _WHEEL_STEPS.
        if building[0] or not delta_y or cid not in rec.inputs:
            return
        step = _WHEEL_STEPS.get(rec.kinds.get(cid))
        if step is None:
            return
        rec.inputs[cid].value = _wheel_step(rec.inputs[cid].value, delta_y, step)
        # A wheel notch is a deliberate step, so it COMMITS. The matrix/vector cells now only PREVIEW on
        # their on_change (committing on Enter/blur), so the notch must commit them explicitly here; the
        # other wheeled kinds (power / prescaler) still commit in their own on_change, so they don't.
        commit = {"mapping": on_mapping_change, "commacell": on_comma_change,
                  "interestcell": on_interest_change, "heldcell": on_held_change,
                  "targetcell": on_target_cells_change}.get(rec.kinds.get(cid))
        if commit is not None:
            commit()

    def on_target_limit_wheel(delta_y):
        # step the TILT/OLD limit by ±1 per wheel notch. Unlike a matrix/vector cell, COMMITTING a
        # new limit rebuilds the whole target-interval set, re-solves the tuning and re-renders the
        # grid — far too heavy to run on every notch. A fast scroll would queue one such solve per
        # notch, each costlier than the last as the set grows, and grind the app to a halt. So step
        # the shown number now (under the build guard, so the field's own on_target_change echo is a
        # no-op — handle_event runs it inline) and DEBOUNCE the commit: the value is server-side, so
        # the loopback-controlled field actually advances, while a re-armed task collapses the whole
        # gesture into ONE solve at the limit you land on. Focus-gated client-side (see _INT_WHEEL_JS).
        if building[0] or not delta_y:
            return
        num = rec.selects["preset:target"][0]
        building[0] = True  # advance the shown number without committing it
        num.value = _wheel_step(num.value, delta_y)
        building[0] = False
        # redden what the stepped limit would drop, in place, NOW — before the debounced commit reflows
        # them away. Each notch repaints against the focus baseline, so scrolling down lights up exactly
        # the intervals it's shedding while they're still on screen; the commit then deletes them.
        on_target_limit_preview()
        if target_limit_commit[0] is not None:
            target_limit_commit[0].cancel()  # a fresh notch restarts the debounce window
        target_limit_commit[0] = background_tasks.create(
            _debounced_target_commit(), name="target-limit-commit")

    async def _debounced_target_commit():
        # the tail of a target-limit wheel gesture: once the notches stop for _TARGET_LIMIT_DEBOUNCE,
        # commit the number now in the field with the one real solve + render. A new notch cancels
        # this and arms a fresh one. limit_changed=False so landing on an even odd-limit (OLD) reddens
        # the field rather than toasting once per gesture.
        try:
            await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
        except asyncio.CancelledError:
            return
        target_limit_commit[0] = None
        on_target_change(limit_changed=False)

    def on_target_limit_preview(typed=None):
        # live edit preview for the TILT/OLD limit field, mirroring on_element_preview: as the shown
        # limit changes (a wheel notch steps it, a keystroke types it) but BEFORE the debounced commit
        # reflows the grid, the candidate rings the target-interval cells the new limit would MOVE
        # (amber) / REMOVE (red) in place. LOWERING the limit drops intervals; reddening them while
        # they're still on screen is what shows "what's going away" — a post-commit render can't, the
        # reflow has already deleted them. RAISING it just rings the survivors that move (the added
        # rows are off-screen until committed, so they can't ring), like every other no-reflow add
        # preview. `typed` is the live field text for a keystroke (the loopback field's debounced
        # model value lags a keystroke behind); the wheel passes None and reads the stepped number.
        g = rec.gesture
        if building[0] or g is None or g.kind != "edit" or g.source != "preset:target":
            return
        num, sel = rec.selects["preset:target"]
        family = sel.value or "TILT"
        raw = num.value if typed is None else typed
        if service.target_limit_problem(family, raw) == "whole":
            _edit_candidate(None)  # a non-number isn't a previewable limit (yet); the commit toasts it
            return
        text = (str(raw) if raw is not None else "").strip()
        spec = f"{int(float(text))}-{family}" if text else family  # blank -> the bare family (domain default)
        try:
            valid = bool(service.target_interval_set(spec, editor.state.domain_basis))
        except Exception:
            valid = False
        if not valid:
            _edit_candidate(None)
            return
        _edit_candidate(lambda: editor.set_target_spec(spec))  # the same edit on_target_change commits

    def on_prescaler_change(cid):
        # a bare prescaler 𝐿 diagonal cell (cid "cell:prescaling:primes:i:i"): a valid float
        # overrides that one diagonal entry (which then drives EVERY downstream consumer — the
        # product tiles, complexity, weights, the tuning solve and its retunings/damages).
        # The first edit seeds the override from the scheme so the d-1 untouched cells keep
        # their displayed values (set_custom_prescaler_entry handles that). The bare prescaler
        # is a float diagonal (log_prime / prime / identity / typed), so parse as float — an
        # unparseable entry leaves the scheme unchanged, like the other editable cells.
        if building[0] or cid not in rec.inputs:
            return
        try:
            value = float(str(rec.inputs[cid].value).strip())
        except ValueError:
            return
        parts = cid.split(":")  # "cell:prescaling:primes:i:j" — row i, column j (the whole square edits)
        editor.set_custom_prescaler_entry(int(parts[3]), int(parts[4]), value)
        render()

    def on_ptext_edit(cid, value):
        # the editable plain-text duals: a valid EBK string drives the grid (like
        # typing in a matrix cell); an unparseable one reddens the box and is ignored
        if building[0]:
            return
        if cid == "ptext:mapping:primes":
            ok = editor.try_edit_mapping_text(value)
        elif cid == "ptext:vectors:commas":
            ok = editor.try_edit_comma_basis_text(value)
        elif cid == "ptext:tuning:gens":  # a typed cents tuning freezes the generator tuning map
            ok = editor.set_generator_tuning_text(value)
        elif cid == "ptext:tuning:ssgens":  # a typed 𝒈L freezes the superspace generator tuning
            ok = editor.set_superspace_generator_tuning_text(value)
        elif cid == "ptext:vectors:targets":  # a typed vector list overrides the target interval set
            ok = editor.set_target_override_text(value)
        elif cid == "ptext:prescaling:primes":  # a typed d×d matrix overrides the prescaler 𝐿's
            # diagonal — the alternative to per-cell edits in the same tile, and the only path
            # for typing the WHOLE diagonal at once. An invalid shape (non-diagonal, wrong size)
            # reddens the box rather than mangling 𝐿, like the mapping / comma-basis duals.
            ok = editor.set_custom_prescaler_text(value)
        elif cid == "ptext:projection:primes":  # a typed d×d map string retunes to the projection P it
            # defines — the only P edit path (the gridded cells are read-only, since a single entry
            # can't keep P idempotent). Rejected (reddens, toasts) unless it's a valid projection.
            ok = editor.try_edit_projection_text(value)
        elif cid == "ptext:projection:gens":  # a typed vector-list string retunes to the embedding G
            ok = editor.try_edit_embedding_text(value)
        else:
            return
        if ok:
            rec.ptext_inputs[cid].classes(remove="rtt-ptext-error")
            render()
        else:
            rec.ptext_inputs[cid].classes(add="rtt-ptext-error")
            # a string that PARSED but was rejected by the editor (a degenerate temperament, or a P/G
            # that isn't a valid projection / embedding) toasts WHY, like the ratio cells; an
            # unparseable string just reddens (its shape is the feedback)
            toast = None
            if cid == "ptext:mapping:primes":
                st = service.parse_mapping_state(value)
                if st is not None and not service.is_proper_temperament(st.mapping):
                    toast = _INVALID_TEMPERAMENT
            elif cid == "ptext:vectors:commas":
                b = service.parse_comma_basis(value)
                if b is not None and not service.is_proper_temperament(service.from_comma_basis(b).mapping):
                    toast = _INVALID_TEMPERAMENT
            elif cid == "ptext:projection:primes" and service.parse_projection(value) is not None:
                toast = _INVALID_PROJECTION  # parsed as a d×d map, but P² ≠ P / commas not in its kernel
            elif cid == "ptext:projection:gens" and \
                    service.parse_embedding(value, editor.state.d, len(editor.state.mapping)) is not None:
                toast = _INVALID_EMBEDDING  # parsed as a vector list, but 𝑀𝐺 ≠ 𝐼
            if toast:
                ui.notify(toast, type="negative", position="top")

    def act(action):
        # a commit ends any hover-family gesture FIRST — its rings are previews of a click that
        # has now landed (or been superseded), and a token gesture must restore the real document
        # before the action mutates it (e.g. Ctrl+Z while a temperament hover holds a hypothetical
        # doc). The edit/wheel gestures survive their own commits and end on blur/mouseleave.
        if rec.gesture is not None and rec.gesture.kind in ("hover", "chooser", "temp", "drag"):
            end_gesture()
        action()
        render()

    # the draft-column + buttons (comma / target / held / interest, and the nonstandard-domain
    # element) drop the cursor straight into the new green column: the quantities-row ratio cell
    # when that row is shown, else the first gridded value of the interval-vectors column. The map
    # gives each group its (quantities draft-cell id, vectors draft-cell kind); the element draft
    # lives only in the header row, so it has no vectors fallback (None).
    draft_focus = {
        "comma":    ("comma:pending",    "commacell"),
        "target":   ("target:pending",   "targetcell"),
        "held":     ("held:pending",     "heldcell"),
        "interest": ("interest:pending", "interestcell"),
        "element":  ("prime:pending",    None),
        # a draft mapping ROW has no editable ratio cell (the generator ratio is read-only) — so it
        # has no quantities-cell target; focus drops straight into the first matrix cell (prime 0)
        "mapping":  (None,               "mapping"),
    }

    def add_interval(action, group):
        # add the draft column, then focus into it: the quantities ratio cell if its row is shown
        # (the layout emitted it), else the first gridded vector cell (prime 0) of the draft column.
        act(action)
        quant_id, vec_kind = draft_focus[group]
        lay = last_lay[0]
        if any(cb.id == quant_id for cb in lay.cells):
            target = quant_id
        elif vec_kind is not None:
            target = next((cb.id for cb in lay.cells
                           if cb.pending and cb.prime == 0 and cb.kind == vec_kind), None)
        else:
            target = None
        if target is None and group == "element":  # quantities row folded: focus the interval-vectors
            # spine draft instead (basis:pending, the row twin of prime:pending), so the + always lands
            target = next((cb.id for cb in lay.cells if cb.id == "basis:pending"), None)
        inp = rec.inputs.get(target) if target is not None else None
        if inp is not None:
            # Focus into the freshly-created draft cell. A direct runMethod can lose a race in a real
            # (visible) browser: the cell-create 'update' and this focus message can be delivered in
            # one frame, so the focus runs before Vue has mounted the new cell and populated its
            # $ref — and silently no-ops. So defer to the next macrotask and poll briefly for the
            # mount (getElement returns the ref once it exists). setTimeout works whether the page is
            # visible or hidden — requestAnimationFrame would be paused while hidden (e.g. the render
            # tests / a backgrounded tab), so it is the wrong tool here.
            ui.run_javascript(
                f"(function(){{var id={inp.id},n=0;function go(){{"
                f"if(getElement(id)){{runMethod(id,'focus',[]);return;}}"
                f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()")

    def on_show_toggle(key, value):
        # building[0] guards the echo when render() syncs a checkbox to the document
        # (e.g. after undo/redo/reset/select-all) rather than a real user toggle
        if building[0]:
            return
        if key == "nonstandard_domain" and not value and editor.basis_is_nonstandard:
            # the setting can't go off while a nonstandard basis is live (its content would be
            # stranded with nowhere to show). Toast and re-render to restore the checkbox to on.
            ui.notify(_NONSTANDARD_BASIS_IN_USE, type="negative", position="top")
            render()
            return
        editor.set_show(key, value)
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def on_select_all(value):
        # the settings panel's select-all/none: flip every implemented Show toggle at once
        if building[0]:
            return
        if not value and editor.basis_is_nonstandard:
            # select-none can't turn "nonstandard domain" off while a nonstandard basis is live —
            # set_all_show keeps it on (its content would be stranded), leaving the master checkbox
            # in its mixed/grey state. Toast to explain why, matching on_show_toggle's guard.
            ui.notify(_NONSTANDARD_BASIS_IN_USE, type="negative", position="top")
        editor.set_all_show(value)
        render()

    def on_part_click(key):
        # a click on one part of the general dummy tile flips that layer's toggle (the tile is the
        # checkbox column's alternative). A value-cell part (the value, its closed form) is inert
        # until its host cell is shown — there's nowhere to draw it otherwise — so a click while
        # gridded values is off does nothing (the CSS also makes it unclickable; this guards the
        # state too). A refinement (equivalences, mnemonics) stays live and, via set_show, pulls
        # its base layer on when selected. render() then re-styles the tile and animates the grid.
        if building[0]:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not editor.settings[host]:
            return
        editor.set_show(key, not editor.settings[key])
        render()

    def on_preset(cid, value):
        # a preset chooser commits its option: temperament loads a comma basis (an undoable edit), the
        # tuning / prescaler presets re-solve. building[0] guards the re-render echo.
        if building[0]:
            return
        if cid.startswith("preset:temperament"):
            # the divider rows are disabled and the prompt is a display-value placeholder (not a row),
            # so only a real preset reaches here; load its comma basis (undoable), then re-render to
            # snap the box onto the now-matching preset.
            if value in presets.TEMPERAMENT_COMMAS:
                end_gesture()  # a live hover preview reverts (its token restores the real document),
                # so the load below is one clean undo step from the real base
                editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
            render()
            return
        apply = _candidate_apply(cid, value)  # tuning / prescaler — the same option→edit map the hover uses
        if apply is not None:
            apply()
            render()

    def on_form_choose(cid, value):
        # the <choose form> control: selecting "canonical" re-stores that matrix in canonical form (an
        # undoable edit); the placeholder "choose form" yields no edit. The select snaps back to the
        # placeholder on the re-render; building[0] guards that echo.
        if building[0]:
            return
        apply = _candidate_apply(cid, value)
        if apply is not None:
            apply()
            render()

    def on_target_change(limit_changed=False):
        # the target chooser is a numeric limit + a TILT/OLD family; compose them into a spec
        # ("9-TILT", or just "TILT" when the limit is blank). Two kinds of bad entry, handled
        # differently:
        #   - a NON-NUMBER ("whole") is never accepted: toast and re-render, which reverts the field
        #     to the last committed value (you can't end up with garbage in the box).
        #   - an EVEN limit for the odd-limit diamond ("odd") IS committed (so the family pick sticks
        #     and the number stays put), but the field is reddened by the render (see
        #     _sync_target_limit_error) with a tooltip saying it must be odd. A directly TYPED even
        #     limit also toasts; merely switching the family to OLD over an even limit only reddens.
        if building[0]:
            return
        num, sel = rec.selects["preset:target"]
        family = sel.value or "TILT"
        problem = service.target_limit_problem(family, num.value)
        if problem == "whole":
            # a non-number is never accepted: toast and re-render, which restores the committed
            # value (the input is loopback-controlled, so the server's value overwrites the garbage)
            ui.notify(tooltips.target_limit_help("whole"), type="negative", position="top")
            render()
            return
        # blank or a whole number (possibly "6.0"): float→int is safe past the validator
        text = (num.value or "").strip()
        spec = f"{int(float(text))}-{family}" if text else family
        try:
            valid = bool(service.target_interval_set(spec, editor.state.domain_basis))
        except Exception:
            valid = False
        if not valid:
            return
        if problem == "odd" and limit_changed:  # a typed even OLD limit toasts; a family switch only reddens
            ui.notify(tooltips.target_limit_help("odd"), type="negative", position="top")
        editor.set_target_spec(spec)  # commit (even an even OLD limit) so the pick sticks; render reddens it
        render()

    def on_control_select(cid, value):
        # the weighting controls: the box 𝒄 complexity / box 𝒘 weight-slope dropdowns swap a scheme
        # trait (the same option→edit map the hover preview uses, via _candidate_apply), while the box 𝐋
        # / 𝐓 checkboxes pass a bool. The re-render echo is ignored via the guards. (The prescaler
        # chooser is a preset now — see on_preset.)
        if building[0] or value is None:
            return
        apply = _candidate_apply(cid, value)  # complexity / slope dropdowns
        if apply is not None:
            apply()
        elif cid == "control:diminuator":  # the checkbox passes a bool (replace the diminuator?)
            editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":  # the target-controls checkbox: all-interval vs target-based
            editor.set_all_interval(bool(value))
        else:
            return  # the complexity "custom" off-preset state (no candidate) is a no-op — no re-render
        render()

    def on_range_mode(value):
        # which generator tuning range the ranges chart shows. A re-render echo (the radio
        # mirroring editor.range_mode) is ignored via the building/None guards, like the presets.
        if building[0] or value is None:
            return
        editor.set_range_mode(value)
        render()

    def on_toggle(item):  # fold/unfold one row, column, or tile ("row:tuning", "tile:mapping:primes")
        editor.toggle_collapsed(item)
        render()

    def on_toggle_all():  # the master node-corner toggle: fold the whole grid, or expand it all back
        editor.set_collapsed(spreadsheet.toggle_all_collapsed(last_lay[0], editor.collapsed))
        render()

    def on_cell_focus(cid):
        # an editable cell took focus: arm the EDIT gesture — its baseline is the on-screen grid,
        # so every live candidate (and every commit while focused) rings exactly the cells it
        # moves, until the cell is left. Focus takes over from whatever gesture was live (a hover
        # or wheel stands down; a token gesture's document restores first). No paint needed —
        # nothing has changed against itself yet.
        take_over_gesture()
        rec.gesture = _Gesture(kind="edit", source=cid, baseline=last_lay[0])

    def on_cell_blur():
        # leaving the cell ends the edit (or a lingering wheel) gesture; the repaint strips its rings
        if rec.gesture is not None and rec.gesture.kind in ("edit", "wheel"):
            end_gesture()
            paint_rings()

    # drag-to-combine preview: while a row/interval is dragged onto another, show what the drop
    # would do — ring the cells it moves and show their would-be values — by applying the combine
    # to the document under the gesture's token and reverting when the hover moves on or the drag
    # ends. The rings are the baseline diff (pickup grid vs the temporarily-applied grid); the
    # actual drop commits it as one undo step.
    def combine_begin():
        end_gesture()  # a stale token gesture (e.g. stranded by a disconnect) dies first
        rec.gesture = _Gesture(kind="drag", token=editor.capture_for_preview(),
                               baseline=last_lay[0])

    def combine_preview(apply, target_pred=None):
        # hovering a target: revert to the picked-up state, apply the hypothetical combine (when
        # valid; apply is None for an invalid/self target), and render — the moved cells ring +
        # show their would-be values. target_pred marks the dropped-on row/column's editable cells
        # so they ring too (their input values aren't in the layout content signature).
        # Re-entrant: each enter resets first.
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        editor.restore_for_preview(g.token)
        g.target_pred = target_pred if apply is not None else None
        if apply is not None:
            apply()
        gesture_render()

    def combine_commit(apply):
        # the drop: revert the preview (end_gesture restores the picked-up state), then apply the
        # combine for real — one undo step — and render.
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        end_gesture()
        act(apply)

    def combine_end():
        # the drag ended off a target (no drop): revert any live preview and clear the drag state.
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        end_gesture()
        render()

    # +/- control hover preview: hovering a structural +/- (add/remove a prime, generator, comma or
    # interval) previews its click before committing — the cells it REMOVES ring red, the cells
    # whose value the re-solve MOVES ring amber. Unlike the drag preview it does NOT reflow the
    # grid: an add/remove would slide the very button being hovered out from under the cursor (and
    # flicker enter/leave), so the HOVER gesture carries the click's op as a hypothetical candidate
    # — compute_rings applies it to a snapshot, diffs, and reverts, painting the on-screen cells in
    # place. The removed cells are still on screen at hover time (the click hasn't landed), so red
    # shows what goes away; a brand-new column the click would ADD lives off-screen until
    # committed, so it can't ring. The click then commits for real via the control's own handler —
    # and because every render repaints the rings from the gesture (which any commit/foreign
    # render ends), the rings structurally cannot survive the click. A keyboard edit or a drag
    # owns the grid while active, so the control hover stands down for them; a live WHEEL gesture
    # (the generator-sign control rides inside the gentuning cell) is suspended under the hover
    # and re-armed when it ends.
    def control_hover(apply):
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        prev = None
        if g is not None and g.kind == "wheel":
            prev = g  # the in-cell gensign hover displaces the wheel gesture — remember it
        elif g is not None:
            take_over_gesture()  # replace a stale hover/chooser/temp outright
        rec.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        paint_rings()

    def control_unhover():
        # leaving the control ends only ITS hover (not a live edit's or drag's rings); a wheel
        # gesture it displaced comes back as-is
        g = rec.gesture
        if g is None or g.kind != "hover":
            return
        rec.gesture = g.prev
        paint_rings()

    def chooser_hover(apply):
        # a dropdown option hover previews applying its candidate, exactly like control_hover (the
        # CHOOSER gesture carries the option's op; compute_rings snapshots, diffs and reverts — no
        # reflow, so the open popup and the chooser's own value stay put). Its own kind so
        # leaving/closing ends only its rings.
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        if g is not None and g.kind != "chooser":
            take_over_gesture()  # a hover/wheel/temp gives way (a temp's token restores the doc,
            # and a reflowed temp preview rebuilds the real grid)
        if rec.gesture is None:
            rec.gesture = _Gesture(kind="chooser")
        rec.gesture.apply = apply
        paint_rings()

    def chooser_unhover():
        # leaving an option / closing the popup ends only the chooser hover's rings
        g = rec.gesture
        if g is None or g.kind != "chooser":
            return
        end_gesture()
        paint_rings()

    def _end_temperament_preview():
        # revert a live temperament hover preview (pointer left an option / popup closed):
        # end_gesture restores the real document; a REFLOW preview also rebuilds the real grid
        g = rec.gesture
        if g is None or g.kind != "temp":
            return
        was = end_gesture()
        if was.reflowed:
            render()    # only a reflow changed the DOM shape
        else:
            paint_rings()  # a redden preview just drops its rings

    def _temperament_hover_preview(key):
        # hovering a temperament option in the open dropdown previews loading it. How it previews
        # depends on whether the temperament GROWS/keeps the grid or SHRINKS it:
        #   • grow / value-only — REFLOW: apply to the document (under the gesture's token) and
        #     re-render the whole would-be grid, so a new prime / comma / generator actually
        #     APPEARS (a bare ring can't show a cell that isn't there yet), the changed cells
        #     ringed amber against the pre-hover grid (the gesture baseline).
        #   • shrink (fewer primes / commas / generators) — REDDEN, don't reflow: a reflow would
        #     just delete the doomed column/row mid-preview. Instead hold the current grid and arm
        #     the load as a hypothetical candidate — the doomed cells ring RED in place, the
        #     surviving changed cells amber. In a mixed change the deletion wins (additions aren't
        #     shown); seeing what goes away is what was asked for.
        # Temperament alone REFLOWS (it changes the grid's dimensionality), so it keeps this
        # sticky TEMP gesture rather than the amber-only chooser_hover the other dropdowns use.
        # The token is captured ONCE per gesture and survives option-to-option moves (including
        # grow→shrink, which arrives with no leave in between); every option re-bases on it.
        # Reverts on leave / popup-close (_end_temperament_preview), commits on select (on_preset).
        if key not in presets.TEMPERAMENT_COMMAS:  # a divider header, null, or the mouse leaving
            _end_temperament_preview()
            return
        g = rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return  # a keyboard edit / drag owns the grid
            end_gesture()  # replace a plain hover/chooser outright
            g = rec.gesture = _Gesture(kind="temp", token=editor.capture_for_preview(),
                                       baseline=last_lay[0])
        editor.restore_for_preview(g.token)  # re-base: each option evaluates from the real document
        if g.reflowed:                       # a prior option reflowed the DOM — rebuild the real grid
            g.reflowed = False
            g.apply = None
            gesture_render()
        base = editor.state                  # its dimensions, before the temperament...
        editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        hyp = editor.state                   # ...and after, to spot a shrink (state dims only — no
        # probe layout; the one hypothetical layout runs in compute_rings / the reflow render)
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:   # drops a prime / comma / generator
            editor.restore_for_preview(g.token)  # back to the real doc; the grid keeps its shape
            g.apply = lambda: editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
            paint_rings()                    # redden the doomed cells in place, no reflow
        else:
            g.apply = None                   # the document now holds the hypothetical: baseline diff
            g.reflowed = True                # keep the chooser's own value + popup steady (_update_preset)
            gesture_render()                 # reflow into the would-be grid

    def _candidate_apply(cid, value):
        # the SINGLE map from a chooser option to the editor edit it commits, as a zero-arg thunk — or
        # None for a no-op (a leave / placeholder / the off-preset "custom" complexity). Keyed by chooser
        # id and shared by both sides: the hover preview (chooser_hover) runs it on a snapshot and
        # reverts, while on_preset / on_control_select / on_form_choose run it for real and re-render. So
        # an option's effect is defined once. (Temperament is not here — it reflows the grid, handled by
        # _temperament_hover_preview / on_preset's own branch.)
        if value is None:
            return None
        if cid.startswith("preset:tuning"):
            return lambda: editor.set_tuning_scheme(value)
        if cid.startswith("preset:prescaler"):
            return lambda: editor.set_complexity_prescaler(value)
        if cid.startswith("preset:projection"):  # base (P) + the embedding (G) copy — one selection
            return lambda: editor.set_established_projection(value)
        if cid == "control:complexity":
            if value == "custom":  # the off-preset display state — selecting it is a no-op, so is a hover
                return None
            # the dropdown presents the friendly display name ("lp (log-product)"); map it back to the
            # internal complexity key the editor takes ("lp"), exactly as on_control_select commits it
            internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
            return lambda: editor.set_complexity_name(internal)
        if cid == "control:slope":
            return lambda: editor.set_weight_slope(value)
        if cid.startswith("formchooser:"):  # the <choose form> control: only "canonical" acts
            if value != "canonical":
                return None
            name = cid.split(":", 1)[1]  # mapping / comma_basis
            return editor.canonicalize_mapping if name == "mapping" else editor.canonicalize_comma_basis
        return None

    def on_chooser_hover(cid, detail):
        # the shared option-hover preview entry for every q-select armed via _arm_option_hover: the
        # delegation fires `opthover` at the chooser's cell wrap carrying the hovered option's positional
        # index in `detail` (-1 / None on leave). Map it back to the option's key through the live
        # select, then preview applying it. Temperament reflows the grid, so it routes to its own sticky
        # path; the rest (including the TILT/OLD family) are amber-only re-solves handled below.
        entry = rec.selects.get(cid)
        sel = entry[1] if isinstance(entry, tuple) else entry  # the target chooser rides a (num, sel) tuple
        if not isinstance(sel, ui.select):
            return  # the chooser is gone
        index = _hover_index(detail)
        # The server-side popup gate: a positive ARM for a chooser whose popup is 'closed' is a
        # stale client debounce-fire from a popup that already committed/closed (the socket's FIFO
        # order puts it after the popup-hide) — drop it, so it can never strand a ring. Leaves
        # (index None) pass through to the unhover path ungated; an untracked chooser (absent —
        # e.g. the in-process tests, which drive `opthover` without opening a popup) allows.
        if index is not None and rec.popup_state.get(cid) == "closed":
            return
        if cid.startswith("preset:temperament"):
            _temperament_hover_preview(_option_key(sel, index))
            return
        if index is None or not sel.enabled:       # a leave, or a disabled / locked chooser → no preview
            chooser_unhover()
            return
        if cid == "preset:target":
            # the TILT/OLD family: preview switching to it. Compose the spec from the displayed limit +
            # the hovered family, exactly what on_target_change commits, and ring in place — the target
            # set re-derives, so rows the switch drops ring red and survivors that move ring amber, with
            # no reflow (the chooser keeps its value + open popup, like the other amber-only choosers).
            family = _option_key(sel, index)
            if family not in presets.TARGET_SETS:
                chooser_unhover()
                return
            text = (entry[0].value or "").strip()  # the displayed limit (entry[0] is the num input)
            try:
                spec = f"{int(float(text))}-{family}" if text else family
            except ValueError:
                spec = family
            chooser_hover(lambda: editor.set_target_spec(spec))
            return
        apply = _candidate_apply(cid, _option_key(sel, index))
        if apply is None:                          # a placeholder / no-op option
            chooser_unhover()
            return
        chooser_hover(apply)

    def on_popup(cid, is_open):
        # a chooser's Quasar popup opened/closed: feed the server-side gate (see on_chooser_hover)
        # and treat the close as the gesture's leave — the option the pointer was on is gone, so a
        # live chooser/temperament preview ends (ungated; only positive arms are gated).
        rec.popup_state[cid] = "open" if is_open else "closed"
        if not is_open:
            on_chooser_hover(cid, None)

    # generator-tuning wheel preview: hovering the cell arms the WHEEL gesture, whose baseline is
    # the grid at hover time, so each wheel notch (a real, committed nudge — handled by
    # on_gentuning_wheel, which re-renders) rings the OTHER cells it moves against that baseline.
    # Leaving the cell drops the rings; the nudge itself stays. The scrolled cell is the gesture
    # source, so it is never rung. A keyboard edit, a drag, or the in-cell sign's control hover
    # owns the grid while active, so the wheel hover stands down for them (the sign hover SUSPENDS
    # an already-armed wheel gesture and hands it back — see control_hover).
    def gentuning_hover(cid):
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag", "hover"):
            return
        take_over_gesture()  # replace a stale wheel/chooser/temp arm outright
        rec.gesture = _Gesture(kind="wheel", source=cid, baseline=last_lay[0])

    def gentuning_unhover(cid):
        g = rec.gesture
        if g is None or g.kind != "wheel" or g.source != cid:
            return  # not our gesture (a keyboard edit / the sign hover took it over) — leave it be
        end_gesture()
        paint_rings()

    # drag-and-drop reorder: a grip's dragstart records the column it picked up; dropping it onto
    # another column's grip (drop reads the recorded source) moves it to that column's slot, or onto a
    # list's gridline "add" zone appends it (into an empty list or at the end). One editor edit = one
    # undo step. Same proven per-element pattern as drag-to-combine — no global script, no dragging-class.
    drag_src = [None]     # (list, idx) of the column being dragged, or None
    reorder_dst = [None]  # the (list, idx|None) currently previewed, so a repeat dragenter is a no-op

    def on_drag_start(lst, idx):
        drag_src[0] = (lst, idx)
        reorder_dst[0] = (lst, idx)  # pick-up == dropping on itself: no move previewed yet
        end_gesture()  # a stale token gesture (e.g. stranded by a disconnect) dies first
        rec.gesture = _Gesture(kind="drag", token=editor.capture_for_preview(),
                               baseline=last_lay[0])

    def on_drag_enter(dst_list, dst_idx):
        # hovering a target column (or a list's gridline "add" zone, dst_idx=None) while dragging:
        # preview the move from the picked-up state so the columns slide open to show where the drop
        # will land — before releasing. The grips are index-keyed (slot-bound), so they stay put under
        # the cursor while the value columns glide, keeping the previewed target stable. The hover
        # preview is reverted on dragend / re-applied on each new target, and committed on drop.
        # Rings: a move that CHANGES THE SET — across lists, or into/out of the commas (temper out /
        # un-temper) — re-optimizes the temperament, so the baseline diff rings the cells whose value
        # it moves. A pure within-list reorder changes no values (only positions — the columns are
        # content-keyed, so the diff is empty): it just glides, no rings.
        g = rec.gesture
        if g is None or g.kind != "drag" or drag_src[0] is None or (dst_list, dst_idx) == reorder_dst[0]:
            return
        reorder_dst[0] = (dst_list, dst_idx)
        editor.restore_for_preview(g.token)  # back to the picked-up state...
        idx = dst_idx if dst_idx is not None else (1 << 30)
        editor.move_interval(drag_src[0][0], drag_src[0][1], dst_list, idx)  # ...then the hypothetical move
        gesture_render()

    def on_drag_end():
        # released off a target (no drop): revert any live preview to the picked-up state
        if rec.gesture is not None and rec.gesture.kind == "drag":
            end_gesture()
            render()
        drag_src[0] = None
        reorder_dst[0] = None

    def on_drop(dst_list, dst_idx):
        # dst_idx is the dropped-on column's index (insert there), or None from a list's "add" zone
        # (append). Revert the live preview first (end_gesture) so the move is snapshotted from the
        # picked-up state — one undo step — then commit it (the screen is already in the previewed
        # shape, so it doesn't move).
        src = drag_src[0]
        drag_src[0] = None
        reorder_dst[0] = None
        had_preview = rec.gesture is not None and rec.gesture.kind == "drag"
        if had_preview:
            end_gesture()
        if not src:
            if had_preview:
                render()  # clear the reverted preview
            return
        idx = dst_idx if dst_idx is not None else (1 << 30)  # None = append (insert clamps to the end)
        if editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
            render()  # reflow into the committed shape, or (a no-op drop) clear the reverted preview
    # wire the reconciler's callbacks now that the event handlers exist: the cell
    # builders fire these (a control's on_change/on_click -> an editor edit + re-render)
    rec._cb = SimpleNamespace(
        act=act,
        add_interval=add_interval,
        combine_begin=combine_begin,
        combine_preview=combine_preview,
        combine_commit=combine_commit,
        combine_end=combine_end,
        control_hover=control_hover,
        control_unhover=control_unhover,
        gentuning_hover=gentuning_hover,
        gentuning_unhover=gentuning_unhover,
        on_cell_blur=on_cell_blur,
        on_cell_focus=on_cell_focus,
        on_popup=on_popup,
        on_comma_change=on_comma_change,
        on_unchanged_change=on_unchanged_change,
        on_drag_start=on_drag_start,
        on_drag_enter=on_drag_enter,
        on_drag_end=on_drag_end,
        on_drop=on_drop,
        on_control_select=on_control_select,
        on_form_choose=on_form_choose,
        on_gentuning_change=on_gentuning_change,
        on_gentuning_wheel=on_gentuning_wheel,
        on_value_wheel=on_value_wheel,
        on_target_limit_wheel=on_target_limit_wheel,
        on_target_limit_preview=on_target_limit_preview,
        on_chooser_hover=on_chooser_hover,
        on_held_change=on_held_change,
        on_interest_change=on_interest_change,
        on_mapping_change=on_mapping_change,
        on_power_change=on_power_change,
        on_prescaler_change=on_prescaler_change,
        on_preset=on_preset,
        on_ptext_edit=on_ptext_edit,
        on_ratio_change=on_ratio_change,
        on_element_change=on_element_change,
        on_element_preview=on_element_preview,
        on_range_mode=on_range_mode,
        on_target_cells_change=on_target_cells_change,
        on_target_change=on_target_change,
        on_toggle=on_toggle,
        on_toggle_all=on_toggle_all,
    )


    def render():
        # Renders end gestures that don't render: a render arriving while a hover / chooser /
        # temp / drag gesture is live — and NOT initiated by that gesture's own handler
        # (gesture_render) — is by definition an external commit or unrelated rebuild, so the
        # gesture ends here, structurally, whatever path the commit took (act, a chooser's
        # on_change, a Show toggle, the debounced target commit...). end_gesture restores a held
        # token FIRST, so the layout below builds from the real document. The edit/wheel gestures
        # legitimately render mid-gesture (their commits) and end on blur/mouseleave instead —
        # but any doc-moving render consumes a pending edit candidate (it is stale once the doc
        # moves; the baseline diff takes over, and no hypothetical solve runs inside a commit).
        g = rec.gesture
        if g is not None and not gesture_rendering[0]:
            if g.kind in ("hover", "chooser", "temp", "drag"):
                end_gesture()
            else:
                g.apply = None
        building[0] = True
        st = editor.state
        # thread the previous render's interval-column identities so a within-list reorder keeps
        # each column's id-token: its cells then persist across the render and the CSS left/top
        # transition slides them to the new slot (rather than the old cells re-filling in place)
        prev = last_lay[0].identities if last_lay[0] is not None else None
        lay = editor.layout(prev_ids=prev)
        last_lay[0] = lay
        # The body scroller holds the grid shifted up by the column strip's height (freeze_y): the
        # board content is (total_h - fy) tall, its cells/lines/blocks placed at native coords minus
        # fy, so they land where they always did with the column-title rows now lifted into the strip
        # above. The strip (its inner is full grid width, translated horizontally by _FREEZE_JS) and
        # the corner keep native coords. gridbody drops below the strip (top = _PAD + fy).
        fx, fy = lay.freeze_x, lay.freeze_y
        # the grid pane is sized to enclose the grid + the column strip, a _PAD margin on every side,
        # and the last column title's right overhang (right_overhang — the interest title renders
        # unwrapped past its narrow column, so the pane widens to show it instead of clipping). Its
        # grey backdrop then frames the gridlines all round, white beyond, rather than filling the
        # window. The top/left margin is the frozen regions' _PAD inset; the right/bottom margin is the
        # body's own scroll padding, so it survives scrolling to the end (see .rtt-gridbody). The CSS
        # caps the pane at the window, past which the body scrolls.
        base_w = lay.width + lay.right_overhang + 2 * _PAD
        base_h = lay.height + 2 * _PAD
        grid_pane.style(f"width:{base_w}px; height:{base_h}px")
        # publish sizes for the scrollbar-fit pass (rttFreeze.fit): it resets the pane to the base size,
        # sees which axis the window caps, then grows the pane by a scrollbar width on the PERPENDICULAR
        # axis so a vertical scrollbar never tips a spurious horizontal one (and the grid never reflows
        # when a bar appears). base-w/-h are the pane's footprint (incl. the right_overhang the last
        # column title spills); fit-w is the gridlines' own width — the pane width below which the BODY
        # must scroll horizontally. They differ by the overhang, which lives in the frozen colhead (not
        # the body scroller), so it must not count toward needing a body h-scrollbar. See freeze.js.
        fit_w = lay.width + 2 * _PAD
        grid_pane.props(f'data-base-w="{base_w}" data-base-h="{base_h}" data-fit-w="{fit_w}"')
        board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
        colhead.style(f"height:{fy}px")
        colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
        corner.style(f"width:{fx}px; height:{fy}px")
        gridbody.style(f"top:{_PAD + fy}px")
        rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
        # the chrome title bar + the settings frozen header below it together span the grid's frozen
        # column-strip height (freeze_y), so the settings and grid frozen/scrolling seams line up
        # across the app. The header itself is therefore freeze_y minus the chrome bar.
        show_frozen.style(f"height:{max(0, fy - _CHROME_H)}px")
        # the settings body sizes to its own content but caps at the window less the inset and that
        # combined frozen band (which equals the inset + freeze_y), so a tall toggle list scrolls
        # there instead of off-screen
        show_scroll.style(f"max-height:calc(100vh - {_PAD + fy}px)")
        seen = set()

        # Each gridline renders into every pane its extent reaches, so the branching stays put in
        # the frozen header / row band while the body scrolls beneath. The scrolling body holds
        # the copy shifted up by fy; a line rising above freeze_y also draws into the column strip
        # (at native y), and one reaching left of freeze_x into the sticky row band (body space) —
        # each clipped to its band by the pane's overflow:hidden, meeting the body copy
        # continuously at the seam. No gridline falls in the corner (column lines sit right of
        # freeze_x, row lines below freeze_y), so it's skipped. Copies are keyed #col / #row, each
        # added to `seen`, so the orphan sweep below drops one whose line later stops reaching it.
        def place_line(ln, suffix, parent, shift):
            eid = ln.id + suffix
            seen.add(eid)
            if eid not in rec.els:
                with parent:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    rec.els[eid] = ui.element("div").classes(cls).props(f'data-eid="{eid}"')
            rec.els[eid].style(_line_style(ln, shift))

        for ln in lay.lines:
            x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
            y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
            if x1 >= fx and y1 >= fy:
                place_line(ln, "", board, fy)              # the scrolling body
            if x1 >= fx and y0 < fy:
                place_line(ln, "#col", colhead_inner, 0)   # the frozen column strip (native y)
            if x0 < fx and y1 >= fy:
                place_line(ln, "#row", rowband, fy)        # the frozen row band (body scroll space)

        # A block renders into each pane _block_panes routes it to. A grey tile (tint "") or a
        # thin-bordered box (boxed, the nested tuning-ranges / optimization frame) clears both seams,
        # so it gets the body alone; a colorization wash's white base (tint "base") or coloured layer
        # (tint = group name) overhangs the seam, so a top-row / left-column one also rides the frozen
        # strip / band / corner it spills into (suffix #col/#row/#corner), each copy clipped to its
        # pane so the colour fills the inter-title gap rather than being shaved off there. Native y in
        # the column strip + corner, body scroll space (shifted up by freeze_y) in the body + row band,
        # mirroring place_line; the orphan sweep drops a copy a wash later stops needing. The class is
        # chosen once per copy (fixed for its lifetime).
        def place_block(bl, pane):
            suffix = "" if pane == "body" else "#" + pane
            shift = 0 if pane in ("col", "corner") else fy
            eid = bl.id + suffix
            seen.add(eid)
            if eid not in rec.els:
                with cell_parents[pane]:
                    cls = ("rtt-block-boxed" if bl.boxed
                           else "rtt-washbase" if bl.tint == "base"
                           else "rtt-wash" if bl.tint else "rtt-block")
                    rec.els[eid] = ui.element("div").classes(cls).props(f'data-eid="{eid}"').mark(eid)
            style = f"left:{bl.x}px; top:{bl.y - shift}px; width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:  # the coloured layer (the base draws --wash-base from CSS). The
                # tint rides a --wash-<group> variable so dark mode can retint the whole palette;
                # :root defines each to its _TINTS value, so light renders unchanged.
                style += f"; background:var(--wash-{bl.tint})"
            rec.els[eid].style(style)

        for bl in lay.blocks:
            for pane in _block_panes(bl, fx, fy):
                place_block(bl, pane)

        # Source-cell-gone guard: if this render DROPS or REBUILDS the very cell anchoring the
        # gesture — the id vanished (e.g. committing the held:pending ratio cell replaces it with
        # held:{tok}) or its kind flipped (a domain element relabelled int↔fraction,
        # elementcell↔elementratio) — end the gesture now. The blur listeners that would normally
        # end it ride that cell's input, so when the rebuild destroys it they never fire; without
        # this guard the gesture (and its rings) would strand until a later blur landed elsewhere
        # (both the historical "lingers until I click another cell" bug and the reported
        # held-interval-submit one).
        g = rec.gesture
        if g is not None and g.source is not None:
            src_kind = next((cb.kind for cb in lay.cells if cb.id == g.source), None)
            if src_kind is None or (g.source in rec.kinds and rec.kinds[g.source] != src_kind):
                end_gesture()
        # the ring highlights: a pure function of (document, gesture), recomputed every render —
        # so any commit's render structurally repaints/strips them, whatever path it came from.
        # While a gesture is live the renders that reach here are doc-moving (guard at the top
        # nulled any edit candidate), so this is always the cheap baseline diff — never a solve.
        amber, red = compute_rings(lay)

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id in rec.els and rec.kinds[cb.id] != cb.kind:
                rec.drop(cb.id)  # a cell changed kind (e.g. cents <-> math expression): rebuild it
            container = _freeze_container(cb, fx, fy)
            if cb.id not in rec.els:
                with cell_parents[container]:
                    rec.make_cell(cb)
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner
            top = cb.y - (fy if container in ("body", "row") else 0)
            rec.els[cb.id].style(f"left:{cb.x}px; top:{top}px; width:{cb.w}px; height:{cb.h}px")
            rec.update_cell(cb)
            paint_cell(cb.id, amber, red)

        for eid in [e for e in rec.els if e not in seen]:
            rec.drop(eid)

        # the optimization mean damage is read-only yet helped, and that help names a different
        # quantity per mode — the minimized damage ⟪𝐝⟫ₚ over the targets, or (all-interval) the
        # retuning magnitude. Swap its tooltip(s) to match the live scheme, the same in-place
        # relabel the symbol glyph makes; set_text only pushes when the wording actually changes.
        if rec.mean_damage_tips:
            mean_damage_help_text = tooltips.mean_damage_help(service.is_all_interval(editor.tuning_scheme))
            for tip in rec.mean_damage_tips.values():
                tip.set_text(mean_damage_help_text)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        refs["reset"].set_enabled(editor.can_reset)
        # the nonstandard-domain-approach radio: positioned over the reserved band inside the approach
        # box (lay.approach_box, body coordinates → shift up by fy like any body cell) when the domain
        # carries a nonprime element, hidden otherwise. The live approach's square is filled and the
        # others hollow (the _update_rangemode pattern); this runs while building[0] is True, so the
        # class toggle is a pure display sync, never re-firing as an edit.
        if lay.approach_box is not None:
            ax, ay, aw, ah = lay.approach_box
            refs["approach"].style(f"position:absolute; left:{ax}px; top:{ay - fy}px; "
                                   f"width:{aw}px; height:{ah}px")
            refs["approach"].set_visibility(True)
        else:
            refs["approach"].set_visibility(False)
        for key, opt in refs["approach_opts"].items():
            (opt.classes(add="rtt-rangeopt-on") if key == editor.nonprime_basis_approach
             else opt.classes(remove="rtt-rangeopt-on"))
        # reflect the document's Show settings into the panel (after undo/redo/reset/
        # select-all/load). building[0] is still True, so these programmatic value writes
        # are swallowed by on_show_toggle/on_select_all rather than re-firing as edits.
        for key, box in boxes.items():
            if box.value != editor.settings[key]:
                box.value = editor.settings[key]
        # the general dummy tile: style each layer's part(s) by its live setting — black + opaque
        # when shown, grey + dimmed when hidden — so the tile both mirrors and drives the grid. A
        # value-cell part is inert (no click) until its host cell is shown (_TILE_HOST), mirroring
        # the grid where the value/closed-form need the boxed cell to sit in. Mnemonics is special:
        # it is an underline ON the name, so its COLOUR tracks the name (the layer it refines) while
        # only the underline tracks mnemonics itself — else a name-shown/mnemonic-hidden state would
        # grey just the one letter mid-word.
        for key, parts in tile_parts.items():
            shown = editor.settings["names"] if key == "mnemonics" else editor.settings[key]
            host = _TILE_HOST.get(key)
            inert = host is not None and not editor.settings[host]
            for part in parts:
                part.classes(add="rtt-part-on" if shown else "rtt-part-off",
                             remove="rtt-part-off" if shown else "rtt-part-on")
                part.classes(add="rtt-part-inert") if inert else part.classes(remove="rtt-part-inert")
                if key == "mnemonics":
                    part.classes(add="rtt-mnem-underline") if editor.settings["mnemonics"] \
                        else part.classes(remove="rtt-mnem-underline")
        # the master checkbox: checked (true / black fill) when all on, unchecked (false /
        # empty) when all off, MIXED (grey fill) when some-but-not-all are on
        states = [editor.settings[k] for k in show_settings.IMPLEMENTED]
        select_all_box.value = all(states)
        if any(states) and not all(states):
            select_all_box.classes(add="rtt-show-mixed")
        else:
            select_all_box.classes(remove="rtt-show-mixed")
        # persist the whole document so a browser refresh restores exactly this state — UNLESS a
        # token gesture has the document in a temporarily-applied hypothetical state (a drag hover,
        # a temperament grow-preview): persisting that would resurrect a never-committed document
        # on refresh. The gesture's end always renders the real document, which persists then.
        if rec.gesture is None or rec.gesture.token is None:
            _doc_store()[_STORE_KEY] = editor.serialize()
        building[0] = False
        # (the scrollbar-fit pass re-runs on its own when the grid resizes — the board's width/height
        # CSS transition fires the listener in freeze.js — so render needn't push any JS here.)

    # the hamburger toggles the settings pane. Opening (panelgroup gets .rtt-open) collapses the
    # closed-state tab and slides the drawer out, the app reflowing to its right.
    drawer_open = [False]

    def toggle_drawer():
        drawer_open[0] = not drawer_open[0]
        panelgroup.classes(add="rtt-open") if drawer_open[0] else panelgroup.classes(remove="rtt-open")
        # (opening/closing narrows the grid pane via the panelgroup's width transition, which fires the
        # scrollbar-fit listener in freeze.js once it settles — no JS push needed here.)

    def _pane_chrome():
        """The settings hamburger + the app title — one each, rendered once. CSS pins the hamburger
        (absolute, top-left) so it never moves between states, and swings the title (animated
        transform) from a quarter-turn down the closed tab to upright across the open bar."""
        ui.button(icon="menu", on_click=toggle_drawer, color=None).props("flat dense") \
            .classes("rtt-hamburger").tooltip(tooltips.CHROME_HELP["settings"])
        ui.label("D&D's RTT app").classes("rtt-sidetitle")

    with ui.element("div").classes("rtt-shell"):
        # the sidebar is ONE element that widens from a tab into the settings pane (.rtt-panelgroup, a
        # column), the grid to its right. Its chrome sits on top and morphs in place — the hamburger
        # pinned, the title swinging from a quarter-turn to upright — while the drawer below reveals
        # the settings. Opening just widens the panelgroup, so the tab becomes the pane (no swap).
        panelgroup = ui.element("div").classes("rtt-panelgroup")
        with panelgroup:
            # the chrome: one hamburger + one title, pinned/swung by CSS (see _pane_chrome).
            with ui.element("div").classes("rtt-chrome"):
                _pane_chrome()
            drawer = ui.element("div").classes("rtt-drawer")
            with drawer, ui.element("div").classes("rtt-drawer-inner"):
                # the frozen header: just the select-all/none master, pinned above the scrolling
                # groups (render() sizes it to the layout's freeze_y, matching the main app's frozen
                # band). Its bottom border is the frozen/scrolling seam. The show/example column
                # titles are NOT here — they describe only the specific-group checkbox column now
                # (the general group is the dummy tile), so they ride that group's head below.
                show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
                with show_frozen:
                    # the select-all/none master checkbox: one click flips every implemented Show
                    # toggle on or off. Its checked state (all on) is kept in sync by render();
                    # the not-yet-built toggles are left untouched.
                    with ui.element("div").classes("rtt-show-all"):
                        select_all_box = ui.checkbox(
                            "select all / none",
                            value=all(editor.settings[k] for k in show_settings.IMPLEMENTED),
                            on_change=lambda e: on_select_all(e.value)) \
                            .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                            .tooltip(tooltips.CHROME_HELP["select_all"])
                        # the dark-mode toggle rides beside select-all (both are app chrome, not Show
                        # layers): a sun/moon icon button showing the theme a click would switch to.
                        dark_btn = ui.button(on_click=on_dark_toggle, color=None) \
                            .props(f"flat dense round icon={_dark_icon()}") \
                            .classes("rtt-darktoggle").mark("darkmode") \
                            .tooltip(tooltips.CHROME_HELP["dark_mode"])
                # the scrolling body: the toggle groups, which scroll under the frozen header when
                # the panel outgrows the window (rather than spilling off the bottom of the screen)
                boxes: dict = {}  # specific-group toggle key -> checkbox, so a sub-control row can bind to its parent
                tile_parts: dict = {}  # general-group layer key -> its clickable dummy-tile part (render() styles these)
                show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
                with show_scroll:
                    for group_name, items in show_settings.SHOW_GROUPS:
                        with ui.element("div").classes("rtt-show-group"):
                            if group_name == "general":
                                # the general layers render as ONE clickable dummy value tile rather
                                # than a checkbox column — laid out and proportioned like a real value
                                # tile. Each part is a sample of that layer, clicked directly to show/
                                # hide it; render() styles it by the live setting. A layer's PRIMARY
                                # element carries the showpart:<key> marker + hover help; some layers
                                # also surface inside the value cell (the symbol's row header, the
                                # units' per-cell unit) or split in two (the name, around its mnemonic
                                # letter) — those extra elements ride the same key's list.
                                def add_el(key, html, *, marked=False, size=None, style=""):
                                    fs = size if size is not None else _TILE_FONT.get(key)
                                    css = (f"font-size:{fs}px;" if fs else "") + style
                                    el = ui.html(html).classes("rtt-tile-part").tooltip(tooltips.SHOW_HELP[key])
                                    if key == "mnemonics":
                                        el.classes(add="rtt-tile-mnem")  # always underlined; render() colours it
                                    if marked:
                                        el.mark(f"showpart:{key}")
                                    if css:
                                        el.style(css)
                                    el.on("click", lambda k=key: on_part_click(k))
                                    tile_parts.setdefault(key, []).append(el)
                                    return el

                                def part_el(key, *, size=None, style=""):  # the layer's primary (marked) element
                                    return add_el(key, _general_part_html(key), marked=True, size=size, style=style)

                                with ui.element("div").classes("rtt-show-tile"):
                                    # the head strip, like a real tile's: the decorative fold toggle on
                                    # the left, the single global audio bank on the right (the relocation
                                    # of the per-tile banks). render() greys the bank while audio is off.
                                    with ui.element("div").classes("rtt-tile-head"):
                                        ui.html(_tile_fold_html()).classes("rtt-tile-fold")
                                        refs["audio_bank"] = _audio_bank()
                                    for line in _GENERAL_TILE_LINES:
                                        if "gridded_values" in line:
                                            # the value cell, like a real gridded cell: a square box (the
                                            # gridded_values frame) holding the closed form (math_expressions)
                                            # over "= value" (quantities) over the unit (rides the units layer)
                                            # — all stacked INSIDE the box, as on a real tile, the form/value
                                            # font-FITTED to the square so they don't spill. A row-header
                                            # matlabel (rides the symbol layer) sits in a left gutter; an EQUAL
                                            # empty gutter on the right keeps the boxed cell centred in the tile.
                                            gut = 20  # the row-label gutter, mirrored on the right for centring
                                            hgut = 18  # the drag-handle grip slot, left of the row label (mirrors the grid)
                                            cell_x = hgut + gut + _TILE_CELL_X  # the cell's left within the container
                                            cell_y = _TILE_CELL_Y        # the cell's top within the frame (below the outer top)
                                            row_y = cell_y + (_TILE_CELL - 13) // 2  # row label centred on the cell
                                            with ui.element("div").classes("rtt-tile-line"), \
                                                    ui.element("div").style(f"position:relative;"
                                                        f"width:{hgut + gut + _TILE_FRAME_W + gut + hgut}px;height:{_TILE_FRAME_H}px"):
                                                # the drag-to-combine grip, in its own slot LEFT of the row label
                                                part_el("drag_to_combine", size=15,
                                                        style=f"position:absolute;left:0;top:{cell_y}px;width:{hgut}px;"
                                                              f"height:{_TILE_CELL}px;justify-content:center")
                                                add_el("symbols", _math_html(_TILE_ROWLABEL), size=_TILE_FONT["rowlabel"],
                                                       style=f"position:absolute;left:{hgut}px;top:{row_y}px;width:{gut - 3}px;"
                                                             "height:13px;justify-content:flex-end")
                                                part_el("gridded_values", style=f"position:absolute;left:{hgut + gut}px;top:0")
                                                part_el("math_expressions", size=_fit_font(_TILE_MATH, _TILE_CELL),
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
                                                              f"width:{_TILE_CELL}px;height:9px;justify-content:center")
                                                part_el("quantities", size=_fit_font(_TILE_VALUE, _TILE_CELL),
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
                                                              f"width:{_TILE_CELL}px;height:10px;justify-content:center")
                                                add_el("units", _units_html(_TILE_UNITS), size=_TILE_FONT["cellunit"],
                                                       style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
                                                             f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:#555")
                                        elif "names" in line:
                                            # the name word, split so the mnemonic letter is its own target
                                            # while the word still reads whole: "tile " + "n" + "ame". Only
                                            # the first piece is marked, so a test click lands one toggle.
                                            before, _letter, after = _tile_name_pieces()
                                            with ui.element("div").classes("rtt-tile-line"):
                                                add_el("names", _escape(before), marked=True)
                                                part_el("mnemonics")
                                                add_el("names", _escape(after))
                                        elif "presets" in line:
                                            # the presets chooser sits in a control box (bordered, spanning the
                                            # full tile width like a real tile's control boxes); no label.
                                            with ui.element("div").classes("rtt-tile-line rtt-tile-line-wide"), \
                                                    ui.element("div").classes("rtt-tile-cbox"):
                                                part_el("presets")
                                        else:
                                            with ui.element("div").classes("rtt-tile-line"):
                                                for key in line:
                                                    part_el(key)
                                continue
                            # the specific group keeps the show | example column header (moved here from
                            # the frozen band — it describes only this checkbox column now).
                            with ui.element("div").classes("rtt-show-head"):
                                ui.label("show").classes("rtt-show-title")
                                ui.label("example").classes("rtt-show-examplehdr")
                            for key, label, _ in items:
                                row = ui.element("div").classes("rtt-show-row")
                                with row:
                                    box = ui.checkbox(label, value=editor.settings[key],
                                                      on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                                        .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                                        .tooltip(tooltips.SHOW_HELP[key])
                                    example = ui.html(_example_html(key)).classes("rtt-ex-cell")
                                    if key not in show_settings.IMPLEMENTED:
                                        box.props("disable")  # not built yet -> greyed and inert
                                        example.classes(add="rtt-ex-disabled")  # ...and its sample greys to match
                                boxes[key] = box
                                parent = show_settings.SUBCONTROLS.get(key)
                                if parent:  # indent by nesting depth (so a grandchild sits further right
                                    # than its parent) and show the row only while the parent is on. Only the
                                    # checkbox shifts within its grid column, so the example column stays aligned.
                                    box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                                    row.bind_visibility_from(boxes[parent], "value")

        grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with grid_pane:
            # the grid pane splits into frozen title regions OUTSIDE the body scroller (so the body's
            # scrollbars stop at the titles): the column-title strip (scrolls horizontally in sync via
            # _FREEZE_JS), the corner (frozen both), and the body scroller .rtt-gridbody — which holds
            # the value cells, lines and blocks (on .rtt-gridcontent) plus the sticky-left row band.
            # Sizes/positions are set in render() from the layout's freeze_x/freeze_y. Column/corner
            # cells keep native coords; body/row cells shift up by freeze_y into the body's scroll space.
            colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with colhead:
                colhead_inner = ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
            corner = ui.element("div").classes("rtt-corner").mark("corner")
            with corner:
                # the corner holds the undo/redo title tile (the app title is on the rail)
                with ui.element("div").classes("rtt-titletile").mark("titletile"):
                    with ui.element("div").classes("rtt-tile-btns"):
                        refs["undo"] = ui.button(icon="undo", on_click=lambda: act(editor.undo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("undo").tooltip(tooltips.CHROME_HELP["undo"])
                        refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("redo").tooltip(tooltips.CHROME_HELP["redo"])
                        # reset everything (settings, expand/collapse, values) to the
                        # as-shipped defaults — itself an undoable action
                        refs["reset"] = ui.button(icon="restart_alt", on_click=lambda: act(editor.reset), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("reset").tooltip(tooltips.CHROME_HELP["reset"])

                        # hovering a history button previews its effect: it rings exactly the cells one
                        # undo/redo/reset would move (red for a removal, amber for the re-solve) and clears
                        # on leave, like the +/- buttons — the op still fires only on the click. A disabled
                        # button (history at its end, or nothing to reset) shows no preview, matching its
                        # greyed state; the enabled flag is read live, mirroring set_enabled in render().
                        def arm_history_preview(btn, can, op):
                            btn.on("mouseenter", lambda _=None: control_hover(op) if can() else None)
                            btn.on("mouseleave", lambda _=None: control_unhover())
                        arm_history_preview(refs["undo"], lambda: editor.can_undo, editor.undo)
                        arm_history_preview(refs["redo"], lambda: editor.can_redo, editor.redo)
                        arm_history_preview(refs["reset"], lambda: editor.can_reset, editor.reset)
                # the chapter-9 nonstandard-domain-approach radio: prime-based, nonprime-based, or
                # the library's neutral default (which reads a nonprime element as a formal prime).
                # Built as the standard square radio (the tuning-ranges range-mode style — a vertical
                # list of square options), NOT a Quasar inline radio. Hidden when the domain has no
                # nonprime element — the trait is meaningless there — and revealed when a basis like
                # 2.3.13/5 carries one. render() fills the live option and sets visibility each pass.
                approach_options = {"prime-based": "prime-based",
                                    "nonprime-based": "nonprime-based", "": "neutral"}

                def on_approach_change(value):
                    # building[0] is True while render() programmatically syncs the radio to
                    # editor.nonprime_basis_approach (after an undo, a domain change that reset the
                    # field to "", etc.); that sync toggles the option classes directly, never here.
                    if building[0] or value is None:
                        return
                    editor.set_nonprime_basis_approach(value)
                    render()

                def on_approach_hover(value):
                    # preview the hovered approach option: ring the cells reading the temperament that
                    # way would move, without committing (control_hover reverts it). None = leaving the
                    # radio, so clear the preview. Each option is its own hover target (mouseenter).
                    if value is None:
                        control_unhover()
                        return
                    control_hover(lambda a=value: editor.set_nonprime_basis_approach(a))

                # a square option per approach, stacked vertically (the _build_rangemode shape): a
                # .rtt-rangebox square the live class fills + its label; click sets it, hover previews.
                refs["approach"] = ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
                refs["approach_opts"] = {}
                with refs["approach"]:
                    for key, label in approach_options.items():
                        opt = ui.element("div").classes("rtt-rangeopt")
                        with opt:
                            ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                            ui.label(label).classes("rtt-rangelabel")
                        opt.on("click", lambda _=None, k=key: on_approach_change(k))
                        opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
                        opt.mark(f"approach-{label}")  # each option its own hover/click target
                        refs["approach_opts"][key] = opt
                refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))
            gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
            with gridbody:
                board = ui.element("div").classes("rtt-gridcontent").mark("board")
                with board, ui.element("div").classes("rtt-band"):
                    rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
            # the chapter-9 approach radio was created in the corner (where the closures it needs
            # live), but the corner is clipped to freeze_x×freeze_y and overlaid by the title tile,
            # so re-home it onto the scrolling board — render() positions it over lay.approach_box
            # (the reserved band at the bottom of the damage tile) in body coordinates.
            refs["approach"].move(board)
            # where each cell renders: a frozen region (corner/column strip/row band) or the body board
            cell_parents = {"corner": corner, "col": colhead_inner, "row": rowband, "body": board}

    def on_key(e):
        if not (e.action.keydown and e.modifiers.ctrl):
            return
        is_z = e.key == "z" or e.key == "Z"
        if e.key == "y" or (is_z and e.modifiers.shift):
            act(editor.redo)
        elif is_z:
            act(editor.undo)

    ui.keyboard(on_key=on_key)
    render()


def _reload_excludes(worktrees: Path) -> str:
    """The uvicorn ``reload_excludes`` string: NiceGUI's default ignore globs plus the
    agent-worktrees subtree, but only when it exists. An existing directory becomes a
    watchfiles ``exclude_dir`` (every change under it is dropped by path-parent
    containment), the only way to ignore a subtree of unknown depth — uvicorn's glob
    matcher has no ``**`` and a relative dir never matches the absolute change paths. The
    path must therefore be absolute AND exist: uvicorn globs any non-dir exclude relative
    to cwd, and on Python 3.14 pathlib rejects an absolute glob pattern
    (NotImplementedError), crashing the server at startup. Absent, there's nothing to skip."""
    excludes = [".*", ".py[cod]", ".sw.*", "~*"]
    if worktrees.is_dir():
        excludes.append(str(worktrees))
    return ", ".join(excludes)


def main() -> None:
    """Launch the NiceGUI server.

    Bare ``python app.py`` is local dev: port 8137 with hot-reload (the user keeps an
    instance running there to use the app). A hosting platform — Render — sets ``PORT``,
    which switches to a production launch: bind every interface on that port, no
    file-watching reloader, and sign sessions with the secret from the environment.
    """
    hosted_port = os.environ.get("PORT")
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    elif hosted_port:
        port = int(hosted_port)
    else:
        port = 8137
    run_kwargs = dict(
        title="D&D's RTT App", favicon="https://github.com/DandDsRTT.png",
        show=False, port=port,
        storage_secret=os.environ.get("STORAGE_SECRET", _STORAGE_SECRET),
    )
    if hosted_port:
        run_kwargs.update(host="0.0.0.0", reload=False)
    else:
        worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
        # watch the assets too, not just *.py (uvicorn's default), so an audio.js / rtt.css edit
        # hot-reloads on its own — otherwise a JS/CSS-only change leaves the running instance stale
        # until some unrelated .py file happens to change (a JS-only audio fix silently failed to land).
        run_kwargs.update(reload=True, uvicorn_reload_includes="*.py,*.css,*.js",
                          uvicorn_reload_excludes=_reload_excludes(worktrees))
    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__"}:
    main()
