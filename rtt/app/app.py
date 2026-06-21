from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
import os
import sys
import zlib
from dataclasses import dataclass
from html import escape as _escape
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, NamedTuple
from urllib.parse import quote

from nicegui import app, background_tasks, helpers, ui

from rtt.library.formatting import strip_negative_zero
from rtt.app import ids
from rtt.app import presets
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app import tooltips
from rtt.app.editor import Editor
from rtt.app.marks import (
    BR_COLOR,
    PENDING_COLOR,
    angle_bracket,
    angle_foot,
    brace,
    curly_bracket,
    ebk_svg,
    rect,
    ribbon,
    square_bracket,
    svg,
    top_bracket,
    vbar,
)

from rtt.app.render_html import (
    _CHART_BAR_FRAC,
    _CHART_GRID,
    _CHART_INDICATOR,
    _CHART_PAD_B,
    _CHART_PAD_T,
    _CONTROL_GLYPHS,
    _DESCENDERS,
    _DOT_PITCH,
    _EXAMPLE_TEXT,
    _EXPR_CHAR_W,
    _EXPR_MAX_FONT,
    _EXPR_MIN_FONT,
    _FOLD_GLYPH,
    _PTEXT_DEFAULT_EM,
    _PTEXT_GLYPH_EM,
    _RANGE_CAP_W,
    _RANGE_FONT,
    _RANGE_MARK_W,
    _RANGE_PLOT_B,
    _RANGE_PLOT_T,
    _RATIO_DIGIT_EM,
    _RATIO_MAX_FONT,
    _RATIO_PAD,
    _SUB_TAGS,
    _TILE_BR_W,
    _TILE_CAP,
    _TILE_CELL,
    _TILE_CELL_X,
    _TILE_CELL_Y,
    _TILE_ENCLOSE,
    _TILE_EQUIV,
    _TILE_FRAME_H,
    _TILE_FRAME_W,
    _TILE_MATH,
    _TILE_MNEMONIC_AT,
    _TILE_NAME,
    _TILE_PTEXT,
    _TILE_SYMBOL,
    _TILE_UNITS,
    _TILE_VALUE,
    _UNIT_PLAIN,
    _approach_visible,
    _bar_chart,
    _block_panes,
    _bold_units,
    _cents_parts,
    _chart_ticks,
    _control_svg,
    _demath,
    _digit_fit_font,
    _elide_expr_line,
    _example_chart,
    _example_html,
    _fit_font,
    _freeze_container,
    _general_part_html,
    _gentuning_parts,
    _limit_text,
    _line_style,
    _math_html,
    _mathexpr_html,
    _mode_svg,
    _option_box_svg,
    _parse_int,
    _power_parts,
    _ptext_font,
    _ptext_units,
    _range_chart,
    _ratio_font,
    _ratio_parts,
    _run_html,
    _select_props,
    _tile_fold_html,
    _tile_grid_frame_html,
    _tile_name_pieces,
    _tile_preset_html,
    _underline_html,
    _units_font,
    _units_html,
    _wave_svg,
    _wheel_step,
)

_log = logging.getLogger(__name__)


class _KindHandlers(NamedTuple):
    build: Callable
    update: Callable | None = None


_ASSETS = Path(__file__).parent / "assets"

# Self-host the body font as WOFF2 (assets/fonts/) and serve it same-origin, so every machine
# renders the SAME face. The app used to declare 'Cambria' with no webfont, so on any box without
# MS Office (macOS, Render/Linux, mobile) it silently fell back to Georgia — whose old-style
# proportional digits are why matrix columns looked uneven. STIX Two Text is the OFL scientific
# serif we ship instead (Text faces carry both figure sets; the hard-subset STIX Two Math face
# supplies only the ⟨ ⟩ ⟪ ⟫ EBK brackets the Text face omits). The @font-face block below points
# at this route. Registering at import is idempotent across the reload worker and the test
# re-imports (a duplicate FastAPI route is harmless — first match wins).
app.add_static_files("/rtt-fonts", _ASSETS / "fonts")

_PAD = 12
_T = "0.25s"
_PANEL_W = 330
_TAB_W = 40
_TAB_H = 218
_CHROME_H = 40
_TOOLTIP_DELAY_MS = 700
# help waits for a deliberate rest instead of popping on every passing cursor (Quasar defaults to 0)
_STORE_KEY = "rtt_doc"
_STATE_PARAM = "state"
_DARK_KEY = "rtt_dark"
_CHAPTER_KEY = "rtt_chapter"
_STORAGE_SECRET = "dnd-rtt-app"  # signs the per-browser session cookie that keys app.storage.user
# Under NiceGUI's in-process User test simulation, app.storage.user is file-backed: writing
# it on every render both litters the tree and races the harness's teardown file-cleanup on
# Windows. The tests re-import this module per case, so a module-level dict gives the same
# survives-a-refresh persistence, isolated per test, with no file I/O. Production is unaffected.
_MEMORY_STORE: dict = {}


def _doc_store() -> dict:
    return _MEMORY_STORE if helpers.is_user_simulation() else app.storage.user


def _encode_state(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode_state(token: str) -> dict:
    raw = zlib.decompress(base64.urlsafe_b64decode(token.encode("ascii")))
    return json.loads(raw.decode("utf-8"))

_INVALID_TEMPERAMENT = "Not a valid temperament: the generators must be independent and every prime reached."
_INVALID_FORM = "Not a valid generator form: 𝐹 must be a square matrix with determinant ±1 (unimodular)."

_SUBPICK_POPUP_W = 220

_INVALID_PROJECTION = "That isn't a valid projection — 𝑃 must be idempotent (𝑃² = 𝑃) with the commas in its kernel."
_INVALID_EMBEDDING = "That isn't a valid embedding — 𝑀𝐺 must equal the identity."

_INVALID_PRESCALER = "A prescaler diagonal entry must be a positive, finite number."
_INVALID_WEIGHT = "A damage weight must be a positive, finite number."

_INVALID_UNCHANGED = "That isn't a valid unchanged-interval basis — each entry must be a whole number."

_LOAD_FAILED = (
    "Couldn’t restore your saved document — showing the defaults. Your saved data is kept; "
    "editing anything here will replace it."
)

_SEAM = "#999"
_PENDING_TEXT_COLOR = "color-mix(in srgb, var(--pending-color) 60%, black)"
_PREVIEW_COLOR = "#e8c00a"
_PREVIEW_TEXT_COLOR = "color-mix(in srgb, var(--preview-color) 60%, black)"
_PREVIEW_REMOVE_COLOR = "#e53935"
_PREVIEW_REMOVE_TEXT_COLOR = "color-mix(in srgb, var(--preview-remove-color) 60%, black)"
_CELL_BORDER_W = 1
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {BR_COLOR}"
_CELL_FONT = 17
_GENSIGN_W = 9
_STACKED_MAIN_FONT = 10
_TINTS = {"tuning": "#9acdcd", "temperament": "#cdcd9a", "form": "#cd9acd"}

_DARK_FRAME = "#15171a"
_DARK_CELL = "#1b1f24"
_DARK_MARK = "#8d949d"
_DARK_TEXT = "#e3e6ea"
_DARK_MUTED = "#71777f"

_WHEEL_STEPS = {
    "mapping": 1, "commacell": 1, "interestcell": 1, "heldcell": 1, "targetcell": 1,
    "powerinput": 1, "prescalercell": 0.001,
}
_INT_WHEEL_JS = ("(e) => { if (e.currentTarget.contains(document.activeElement)) "
                 "{ e.preventDefault(); emit(e); } }")
# How long after the last target-limit wheel notch to run the commit. Each notch cheaply steps the
# shown number (server-side, so the loopback-controlled field actually updates), but COMMITTING a
# new limit rebuilds the whole target set, re-solves the tuning and re-renders the grid — far too
# heavy per notch (a fast scroll would queue one such solve per notch, each costlier as the set
# grows, and grind the app). So the commit is debounced by this much, mirroring the limit input's
# typing ``debounce=300``. See on_target_limit_wheel.
_TARGET_LIMIT_DEBOUNCE = 0.3
_BUSY_DELAY_MS = 180
_BUSY_SAFETY_MS = 6000


class _GridValueSpec(NamedTuple):
    ratio_allowed: bool
    pending: bool
    commit: str
    preview: str | None
    cid_arg: bool
    arm: tuple | None = None



class _VecGridEdit(NamedTuple):
    group: str
    count: "Callable[[], int]"
    cell_id: "Callable[[object, int], str]"
    pending: "Callable[[], object]"
    set_pending: "Callable[[list], None]"
    commit: "Callable[[list], None]"
    validate: "Callable[[list], bool] | None" = None
    guard: "Callable[[], bool] | None" = None
    draft_arms: bool = False



_GRIDVALUE_SPECS = {
    "ratiocell":     _GridValueSpec(True,  True,  "on_ratio_change",        None,                 True),
    "elementcell":   _GridValueSpec(True,  True,  "on_element_change",      "on_element_preview",  True),
    "elementratio":  _GridValueSpec(True,  True,  "on_element_change",      "on_element_preview",  True),
    "mapping":       _GridValueSpec(False, True,  "on_mapping_change",      "on_mapping_change",   False, ("row",)),
    "formcell":      _GridValueSpec(False, False, "on_form_change",         "on_form_change",      False),
    "commacell":     _GridValueSpec(False, True,  "on_comma_change",        "on_comma_change",     False, ("col", "comma")),
    "unchangedcell": _GridValueSpec(False, False, "on_unchanged_change",    "on_unchanged_change", False),
    "interestcell":  _GridValueSpec(False, True,  "on_interest_change",     "on_interest_change",  False, ("col", "interest")),
    "heldcell":      _GridValueSpec(False, True,  "on_held_change",         "on_held_change",      False, ("col", "held")),
    "targetcell":    _GridValueSpec(False, True,  "on_target_cells_change", "on_target_cells_change", False, ("col", "target")),
}


def _vgroup_key(cb: spreadsheet.CellBox) -> str:
    if cb.kind in ("mapping", "targetcell"):
        return cb.id.rsplit(":", 1)[0]
    if cb.kind == "formcell":
        return "cell:finv"
    parts = cb.id.split(":")
    return ":".join(parts[:2] + parts[3:])


_MODE_FILLS = (
    frozenset({(1, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2)}),
    frozenset({(0, 1), (1, 1), (2, 1)}),
    frozenset({(2, 0), (1, 1), (0, 2), (1, 2), (2, 1), (2, 2)}),
)
_AUDIO_GLYPHS = {
    "mute": ['<span class="material-icons rtt-audio-glyph">volume_up</span>',
             '<span class="material-icons rtt-audio-glyph">volume_off</span>'],
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(f) for f in _MODE_FILLS],
    "lock": ['<span class="material-icons rtt-audio-glyph">lock_open</span>',
             '<span class="material-icons rtt-audio-glyph">lock</span>'],
    "root": '<span class="rtt-audio-rootglyph">1/1</span>',
}

_AUDIO_JS = (_ASSETS / "audio.js").read_text(encoding="utf-8")

# Frozen-pane support. The row band freezes by position:sticky (zero JS on its scroll path), but the
# column-title strip sits OUTSIDE the body scroller (so the vertical scrollbar can stop below it), so
# it can't ride the scroll via CSS — this listener translateX-syncs it to the body's horizontal
# scroll. It also reveals the seams: a frozen region is "stuck" (body scrolled under it) exactly when
# .rtt-gridbody has scrolled off zero on that axis, toggled as rtt-scrolled-x/y on .rtt-app. scroll
# doesn't bubble → capture phase, so the body's scroll events are still caught here.
_FREEZE_JS = (_ASSETS / "freeze.js").read_text(encoding="utf-8")

_FRACTION_JS = (_ASSETS / "fraction.js").read_text(encoding="utf-8")

_DECIMAL_JS = (_ASSETS / "decimal.js").read_text(encoding="utf-8")

_TABNAV_JS = (_ASSETS / "tabnav.js").read_text(encoding="utf-8")

_TOUR_JS = (_ASSETS / "tour.js").read_text(encoding="utf-8")

# The tour steps, walking the app in its DEFAULT state (drawer closed, no extra Show layers on).
# Each step spotlights the element its CSS selector matches (a region class that reaches the DOM —
# NOT a NiceGUI .mark(), which is test-only) and floats the card on `place` side. `open` opens the
# settings drawer first, so the steps that point inside it have their target on screen. An empty
# `sel` is a centred slide. Keep these anchored to real, default-present regions — a missing target
# degrades to a centred card (see tour.js), but the copy would then point at nothing.
_TOUR_STEPS = [
    {"sel": "", "title": "Welcome to D&D's RTT app",
     "body": "A spreadsheet for exploring regular temperaments. Here's a quick tour of what's on "
             "screen — use <b>Next</b> / <b>Back</b> (or the arrow keys), and <b>Skip</b> to leave "
             "anytime."},
    {"sel": ".rtt-app", "place": "left", "title": "The spreadsheet",
     "body": "Everything lives in this grid. Each <b>column</b> is an interval or a whole "
             "temperament, and each <b>row</b> is a quantity computed about it — mappings, "
             "generators, tunings, errors, and more."},
    {"sel": ".rtt-rowband", "place": "right", "title": "Rows — the quantities",
     "body": "The left band names each row. By default you see the core temperament data; the "
             "settings panel can reveal many more rows as you go."},
    {"sel": ".rtt-colhead-inner", "place": "bottom", "title": "Columns — the intervals",
     "body": "Across the top sit the columns. The temperament's mapping and generators get their "
             "own columns; target intervals each get one too."},
    {"sel": ".rtt-zoomable", "place": "right", "title": "The value cells",
     "body": "Most of the grid is computed values. <b>Hover</b> any value to magnify it, and click "
             "a cell's speaker to <b>hear</b> its pitch. Cells drawn with a box are editable — type "
             "a new value and the whole temperament re-solves."},
    {"sel": ".rtt-titletile", "place": "bottom", "title": "Undo, reset & share",
     "body": "Up here: <b>undo</b> / <b>redo</b> your edits, <b>reset</b> everything to defaults, "
             "and <b>share</b> a link that reopens the app in exactly this state."},
    {"sel": ".rtt-hamburger", "place": "right", "open": True, "title": "The settings panel",
     "body": "This hamburger opens the Show panel — the control room for the whole grid. Let's "
             "open it up."},
    {"sel": ".rtt-show-all", "place": "right", "open": True, "title": "Select all & dark mode",
     "body": "<b>Select all / none</b> turns every available row on or off at once, and the "
             "sun/moon button switches between the light and dark themes."},
    {"sel": ".rtt-chapter-slider", "place": "right", "open": True, "title": "Guide chapters",
     "body": "New to the theory? This slider reveals the controls chapter by chapter, the way "
             "D&D's guide introduces them — slide left for a simpler view, right (to ★) for "
             "everything."},
    {"sel": ".rtt-show-tile", "place": "right", "open": True, "title": "Tile features",
     "body": "This sample tile is a live menu: click any part of it — the name, the symbol, the "
             "closed form, the units — to show or hide that feature across the whole grid. The "
             "audio controls up top drive every speaker."},
    {"sel": ".rtt-show-scroll", "place": "right", "open": True, "title": "The Show toggles",
     "body": "Below the sample tile, these checkboxes switch each kind of row on and off. Turn "
             "things on as you need them — start small and build up."},
    {"sel": "", "title": "That's the tour",
     "body": "Explore freely — nothing here is permanent, and <b>reset</b> always brings back the "
             "defaults. Replay this tour anytime from the <b>?</b> button by the undo/redo "
             "controls. Happy tempering!"},
]

_STACKED_EXIT_JS = ("(e) => { const b = e.target.closest('.rtt-frac-edit, .rtt-dec-edit'); "
                    "if (!b || !b.contains(e.relatedTarget)) emit(); }")

_GROUP_EXIT_JS = ("(e) => { const g = e.target.closest('[data-vgroup]'), "
                  "t = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-vgroup]'); "
                  "if (!g || !t || g.getAttribute('data-vgroup') !== t.getAttribute('data-vgroup')) emit(); }")


_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --tab-w:{_TAB_W}px; --tab-h:{_TAB_H}px; --chrome-h:{_CHROME_H}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --pending-color:{PENDING_COLOR}; --pending-text-color:{_PENDING_TEXT_COLOR}; --preview-color:{_PREVIEW_COLOR}; --preview-text-color:{_PREVIEW_TEXT_COLOR}; --preview-remove-color:{_PREVIEW_REMOVE_COLOR}; --preview-remove-text-color:{_PREVIEW_REMOVE_TEXT_COLOR};
  --c-gridline:#e0e0e0;
  --wash-base:#fff; --wash-tuning:{_TINTS['tuning']}; --wash-temperament:{_TINTS['temperament']}; --wash-form:{_TINTS['form']};
  --cell-border-w:{_CELL_BORDER_W}px; --cell-border:{_CELL_BORDER}; --cell-font:{_CELL_FONT}px;
  --zoom-factor:{_CELL_FONT / _STACKED_MAIN_FONT};
  --label-w:{spreadsheet.LABEL_W}px; --header-h:{spreadsheet.HEADER_H}px; --line-w:{spreadsheet.LINE_W}px;
  --ptext-edit-h:{spreadsheet.PTEXT_EDIT_H}px; --option-box:{spreadsheet.OPTION_BOX_PX}px; --btn:{spreadsheet.BTN}px;
  --option-box-unchecked:url("{_option_box_svg(None)}");
  --option-box-checked:url("{_option_box_svg('#000')}");
  --option-box-disabled:url("{_option_box_svg('#888')}");
  --rtt-serif:'STIX Two Text','STIX Two Math',Georgia,serif;
  --rtt-units-sans:'Jost','Corbel','Candara','Trebuchet MS',sans-serif;
}}
"""

_FONT_FACE = "".join(
    f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
    f"font-display:swap;src:url('/rtt-fonts/{file}') format('woff2');}}"
    for fam, style, weight, file in (
        ("STIX Two Text", "normal", 400, "STIXTwoText-Regular.woff2"),
        ("STIX Two Text", "italic", 400, "STIXTwoText-Italic.woff2"),
        ("STIX Two Text", "normal", 700, "STIXTwoText-Bold.woff2"),
        ("STIX Two Text", "italic", 700, "STIXTwoText-BoldItalic.woff2"),
        ("STIX Two Math", "normal", 400, "STIXTwoMath-subset.woff2"),
        ("Jost", "normal", 400, "Jost-Regular.woff2"),
        ("Jost", "normal", 700, "Jost-Bold.woff2"),
    )
)

_CSS_DARK_VARS = f"""body.rtt-dark {{
  --option-box-unchecked:url("{_option_box_svg(None, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-checked:url("{_option_box_svg(_DARK_TEXT, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-disabled:url("{_option_box_svg(_DARK_MUTED, box=_DARK_CELL, border=_DARK_MARK)}");
}}
"""
_CSS = (_FONT_FACE + _CSS_VARS + (_ASSETS / "rtt.css").read_text(encoding="utf-8")
        + _CSS_DARK_VARS + (_ASSETS / "rtt-dark.css").read_text(encoding="utf-8")
        + (_ASSETS / "tour.css").read_text(encoding="utf-8"))


_UNITS_MAX_FONT = 10.0
_CELLUNIT_MAX_FONT = 7.0
_MATLABEL_FONT = 11.0
_MATLABEL_MIN_FONT = 6.0


_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "hbar"}

_EBK_SQUARE = str.maketrans("⟨{⟩}", "[[]]")
_TRANSPOSE_MARK = "ᵀ"

_PTEXT_DUAL_VECTOR_KIND = {
    "ptext:vectors:commas": True,
    "ptext:vectors:targets": True,
    "ptext:projection:gens": True,
    "ptext:mapping:primes": False,
    "ptext:projection:primes": False,
    "ptext:prescaling:primes": False,
}


_GENERAL_TILE_LINES: tuple[tuple[str, ...], ...] = (
    ("drag_to_combine", "gridded_values", "math_expressions", "quantities", "decimals"),
    ("symbols", "equivalences"),
    ("mnemonics", "names"),
    ("units",),
    ("plain_text_values",),
    ("presets",),
    ("charts",),
)

_TILE_IN_CELL_LAYERS: tuple[str, ...] = ("header_symbols", "cell_units")

_TILE_HOST: dict[str, str] = {
    "quantities": "gridded_values",
    "decimals": "gridded_values",
    "math_expressions": "gridded_values",
}

_TILE_FONT = {
    "symbols": 15, "equivalences": 15, "rowlabel": spreadsheet.MATLABEL_H - 2,
    "names": spreadsheet.CAPTION_FONT, "mnemonics": spreadsheet.CAPTION_FONT,
    "units": 10, "cellunit": 7, "plain_text_values": 11, "drag_to_combine": 18,
}


_AUDIO_BANK = (
    ("mute", _AUDIO_GLYPHS["mute"][1], "toggleMute"),
    ("wave", _AUDIO_GLYPHS["wave"][0], "cycleWave"),
    ("mode", _AUDIO_GLYPHS["mode"][0], "cycleMode"),
    ("hold", _AUDIO_GLYPHS["lock"][0], "toggleHold"),
    ("root", _AUDIO_GLYPHS["root"], "toggleRoot"),
)


def _audio_bank() -> "ui.element":
    bank = ui.element("div").classes("rtt-tile-bank").mark("audiobank")
    with bank:
        for ctrl, glyph, fn in _AUDIO_BANK:
            ui.html(glyph).classes("rtt-audio-ctrl").mark(f"audioctrl:{ctrl}") \
                .props(f'data-actrl="{ctrl}"') \
                .on("click", js_handler=f"() => window.rttAudio.{fn}()") \
                .tooltip(tooltips.AUDIO_HELP[ctrl])
    return bank


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
# leaves it stranded whenever the anchor is REMOVED or REFLOWED out from under a stationary cursor
# before any `mouseleave` fires — the grid rebuilds and the hover help hangs on screen with nothing
# to dismiss it. So anything that reflows the grid while a tooltip is up must drop it first: these
# capture-phase listeners synthesize the `mouseleave` Quasar hides on, BEFORE the reflow round-trips.
#
#   - `pointerdown`: a click presses the anchor itself, so the pressed node sits UNDER the anchor —
#     walk the `mouseleave` up the ancestor chain from the pressed node (covers every +/- button).
#   - `keydown` / `wheel`: a keyboard commit (Enter/Tab re-solves the sheet) or a wheel-step reflows
#     with NO pointerdown, so the pressed node isn't the anchor — the at-risk tooltip is on whatever
#     the cursor RESTS on. Drop it from the deepest `:hover` element, and only when one is actually
#     showing, so ordinary typing never perturbs the hover-preview rings (which share `mouseleave`).
#
# It fires `mouseleave` only (never `blur`): the editable cells' blur-commit handlers must stay
# untouched, and QTooltip is hover-shown, so leave is enough.
_TOOLTIP_DISMISS_JS = """
(() => {
  if (window.__rttTipDismiss) return;
  window.__rttTipDismiss = true;
  const dropFrom = (node) => {
    for (let el = node; el instanceof Element; el = el.parentElement) {
      el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: false}));
    }
  };
  // a click presses the anchor: the pressed node is under it
  document.addEventListener('pointerdown', (e) => dropFrom(e.target), true);
  // a keystroke / wheel-step reflows with no pointerdown: drop the tooltip on whatever the cursor
  // rests on, and only when one is actually showing (so typing never disturbs the preview rings)
  const dropHovered = () => {
    if (document.querySelector('.q-tooltip') === null) return;
    const hov = document.querySelectorAll(':hover');
    if (hov.length) dropFrom(hov[hov.length - 1]);
  };
  document.addEventListener('keydown', dropHovered, true);
  document.addEventListener('wheel', dropHovered, {capture: true, passive: true});
})()
"""

VALUE_KINDS: frozenset[str] = frozenset({
    "prime", "formcell", "mapped", "vec", "tuningvalue", "genratio", "commaratio",
    "powerdisplay", "mathexpr",
    "mapping", "commacell", "unchangedcell", "interestcell", "heldcell", "targetcell",
    "prescalercell", "weightcell", "powerinput", "gentuningcell",
    "ratiocell", "elementcell", "elementratio",
})

_ZOOM_JS = """
(() => {
  if (window.__rttZoom) return;
  window.__rttZoom = true;
  const F = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom-factor')) || 1.7;
  const DELAY = 130;   // ms before it appears — quick, but not on every cursor that crosses a cell
  const GAP = 8;       // px between the cell and the magnifier
  let timer = null, anchor = null;

  const overlay = document.createElement('div');
  overlay.className = 'rtt-zoom-overlay';
  overlay.style.display = 'none';
  document.body.appendChild(overlay);

  const hide = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    if (overlay.style.display !== 'none') { overlay.style.display = 'none'; overlay.innerHTML = ''; }
    anchor = null;
  };

  const place = (cell) => {
    const r = cell.getBoundingClientRect();
    const ow = overlay.offsetWidth, oh = overlay.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    let left = Math.max(4, Math.min(r.left + r.width / 2 - ow / 2, vw - ow - 4));
    let top = r.top - GAP - oh;                 // prefer above the cell
    let above = true;
    if (top < 4) { top = r.bottom + GAP; above = false; }   // not enough room: drop below
    top = Math.max(4, Math.min(top, vh - oh - 4));
    // the loupe (the value) sits NEAREST the cell/cursor, the help tooltip on the far side: above the
    // cell that means help-on-top / tile-on-bottom (column-reverse); below, tile-on-top (column)
    overlay.style.flexDirection = above ? 'column-reverse' : 'column';
    overlay.style.left = left + 'px';
    overlay.style.top = top + 'px';
  };

  const build = (cell) => {
    const w = cell.offsetWidth, h = cell.offsetHeight;
    if (!w || !h) return;
    // a blanked cell (quantities off) has nothing to magnify — bail before popping an empty card
    const srcInputs = cell.querySelectorAll('input');
    let hasContent = cell.textContent.trim();
    srcInputs.forEach(i => { if (i.value && i.value.trim()) hasContent = true; });
    if (!hasContent) return;

    overlay.innerHTML = '';
    // the scale box carries the magnified layout size; the clone scales 1:1 from its top-left to fill it
    const scale = document.createElement('div');
    scale.className = 'rtt-zoom-scale';
    scale.style.width = (w * F) + 'px';
    scale.style.height = (h * F) + 'px';
    const clone = cell.cloneNode(true);
    clone.classList.add('rtt-zoom-clone');
    clone.removeAttribute('data-eid');
    clone.style.position = 'static';
    clone.style.left = clone.style.top = 'auto';
    clone.style.width = w + 'px';
    clone.style.height = h + 'px';
    clone.style.transform = 'scale(' + F + ')';
    clone.style.transformOrigin = 'top left';
    clone.style.transition = 'none';
    clone.querySelectorAll('.q-tooltip').forEach(n => n.remove());  // don't drag a nested tooltip along
    // cloneNode does NOT copy a live input's typed value (it's a property, not an attribute), so the
    // editable integer cells (value lives only in their input) would clone empty — copy it across
    const cloneInputs = clone.querySelectorAll('input');
    srcInputs.forEach((s, i) => { if (cloneInputs[i]) cloneInputs[i].value = s.value; });
    scale.appendChild(clone);
    // the loupe tile (the value on a grey grid-tile panel) — the magnified, non-interactive value
    const tile = document.createElement('div');
    tile.className = 'rtt-zoom-tile';
    tile.appendChild(scale);
    overlay.appendChild(tile);
    // the cell's own hover help, below the loupe, styled like a normal tooltip (the editable cells'
    // "type to edit…")
    const help = cell.getAttribute('data-zoomhelp');
    if (help) {
      const cap = document.createElement('div');
      cap.className = 'rtt-zoom-help';
      cap.textContent = help;
      overlay.appendChild(cap);
    }
    overlay.style.display = 'flex';   // matches the CSS (gap + centering); 'block' would defeat them
    place(cell);
  };

  // hover in / out of a zoomable cell, delegated so it survives every grid rebuild
  document.addEventListener('mouseover', (e) => {
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (!cell || cell === anchor) return;
    if (timer) clearTimeout(timer);
    anchor = cell;
    timer = setTimeout(() => { if (anchor === cell && cell.isConnected) build(cell); }, DELAY);
  });
  document.addEventListener('mouseout', (e) => {
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (cell && cell === anchor && !cell.contains(e.relatedTarget)) hide();
  });
  // a commit / reflow / scroll yanks the cell out from under the cursor — drop the magnifier
  document.addEventListener('pointerdown', hide, true);
  document.addEventListener('keydown', hide, true);
  document.addEventListener('wheel', hide, {capture: true, passive: true});
  document.addEventListener('scroll', hide, {capture: true, passive: true});
})()
"""

# The client-driven busy scrim. After a committing interaction the app has to think — an off-loop
# re-solve and/or the browser patching a big grid — for anything from nothing to a few seconds. With
# no feedback a slow beat reads as "I crashed it", so the user keeps clicking a frozen-looking page.
# This arms the scrim (`.rtt-busy`, a dim veil + spinner + "Computing…" + wait cursor that also
# swallows clicks) the instant a control is used and reveals it if the work outlasts a short delay.
# It is driven ENTIRELY client-side, which is the whole point: a *synchronous* re-render (a Show
# toggle, a fold) holds the event loop until it finishes, so the server cannot send a "show scrim"
# message mid-work — only the browser can show it in that window. Every server render() ends by
# calling rttBusy.done(), so the scrim lifts exactly when the awaited grid lands.
_BUSY_JS = f"""
(() => {{
  if (window.rttBusy) return;
  let armTimer = null, safety = null;
  const scrim = () => document.querySelector('.rtt-busy');
  const reveal = () => {{ const o = scrim(); if (o) o.classList.add('rtt-busy-on'); }};
  const clear = () => {{
    if (armTimer) {{ clearTimeout(armTimer); armTimer = null; }}
    if (safety) {{ clearTimeout(safety); safety = null; }}
    const o = scrim(); if (o) o.classList.remove('rtt-busy-on');
  }};
  const arm = () => {{
    if (armTimer) clearTimeout(armTimer);
    if (safety) clearTimeout(safety);
    armTimer = setTimeout(reveal, {_BUSY_DELAY_MS});   // a fast edit lands first and never flashes it
    safety = setTimeout(clear, {_BUSY_SAFETY_MS});      // never strand if this click never re-renders
  }};
  window.rttBusy = {{ arm, done: clear }};

  // Arm ONLY on a real (e.isTrusted) user interaction that commits to the document and so triggers
  // a server re-render: the +/-/fold controls and undo/redo/reset (.rtt-iconbtn), the Show checkboxes
  // / range radios, the scheme/target dropdowns and their option picks, Enter committing a cell edit,
  // and Ctrl/Cmd+Z/Y. The isTrusted gate is essential: render() re-syncs control values
  // programmatically (e.g. box.value = …), which fires SYNTHETIC change events — without the gate
  // those would re-arm the scrim after the render, so it would flash "Computing…" for no reason and
  // linger. We deliberately do NOT arm on wheel (it fires on every scroll over the grid, and the
  // shown scrim would then eat the scroll) or on focus leaving a cell (fires on any focus change,
  // mostly with no commit) — those were the spurious-trigger / stuck-spinner sources.
  const BTN = '.rtt-fanbtn,.rtt-minus-btn,.rtt-minus-btn-v,.rtt-toggle,.rtt-iconbtn';
  const at = (e, sel) => e.isTrusted && e.target && e.target.closest && e.target.closest(sel);
  // .rtt-noarm opts a button out: share is an .rtt-iconbtn for styling but only copies a link — it
  // never re-renders, so nothing would ever call rttBusy.done() and the scrim would linger the full
  // safety timeout. Excluding it here keeps it from arming in the first place.
  document.addEventListener('pointerdown',
    (e) => {{ if (at(e, BTN) && !e.target.closest('.rtt-noarm')) window.rttBusy.arm(); }}, true);
  document.addEventListener('click', (e) => {{ if (at(e, '[role=option],.q-item')) window.rttBusy.arm(); }}, true);
  document.addEventListener('change', (e) => {{
    if (at(e, '.q-select,.q-checkbox,.q-radio,input[type=checkbox],input[type=radio]')) window.rttBusy.arm();
  }}, true);
  // Keyboard shortcuts. Each one resolves to an existing on-screen control and synthetically clicks
  // it, so the action runs through the very same handler the mouse uses (act()/add_interval/
  // toggle_drawer) — no parallel server path — and a shortcut is inert exactly when its button isn't
  // on screen (e.g. Alt+C does nothing while the commas column is hidden, because no .rtt-hk-comma
  // exists to click). Per-action modifier choices: Ctrl/Cmd for the edit-history pair (Z/Y) and the
  // settings pane (Ctrl/Cmd+, — the standard Preferences shortcut), Alt for the "add a row" family.
  // Every shortcut takes a modifier, so they all fire even while a cell is focused and bare typing is
  // never intercepted. Keys match on e.code (the physical key) so a Mac's Option+letter dead-keys/
  // special glyphs (and Cmd+, vs Cmd+;) still match. preventDefault stops the browser's own Ctrl+Z /
  // Alt-mnemonic / Cmd+, from also firing.
  document.addEventListener('keydown', (e) => {{
    if (!e.isTrusted) return;
    const mod = e.ctrlKey || e.metaKey;
    let sel = null, arm = true;
    if (mod && !e.altKey && e.code === 'KeyZ') sel = e.shiftKey ? '.rtt-hk-redo' : '.rtt-hk-undo';
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'KeyY') sel = '.rtt-hk-redo';
    else if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {{
      const k = {{KeyC: 'comma', KeyM: 'mapping', KeyT: 'target', KeyH: 'held', KeyI: 'interest', KeyE: 'element'}}[e.code];
      if (k) sel = '.rtt-hk-' + k;
    }}
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'Comma') {{ sel = '.rtt-hamburger'; arm = false; }}  // pane toggle is pure CSS — don't flash the scrim
    if (sel) {{
      const el = document.querySelector(sel);
      if (el) {{ e.preventDefault(); if (arm) window.rttBusy.arm(); el.click(); return; }}
    }}
    if (e.key === 'Enter' && e.target.closest && e.target.closest('.rtt-cell')) window.rttBusy.arm();
  }}, true);

  // The shown scrim swallows pointer events so a pile of clicks can't land on the mid-recompute
  // grid — but the user should still be able to SCROLL it to read while it computes. Its
  // pointer-events:auto veil eats the wheel along with the clicks, so while it's up we forward
  // wheel deltas to the grid's own scroller by hand (freeze.js's scroll listener then re-pins the
  // frozen header/column bands). Gated on rtt-busy-on so normal-state scrolling stays native.
  document.addEventListener('wheel', (e) => {{
    const o = scrim(); if (!o || !o.classList.contains('rtt-busy-on')) return;
    const body = document.querySelector('.rtt-gridbody'); if (!body) return;
    const f = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? body.clientHeight : 1;
    body.scrollTop += e.deltaY * f;
    body.scrollLeft += e.deltaX * f;
  }}, {{capture: true, passive: true}});
}})()
"""


class _GroupedSelect(ui.select):
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
    if value is None:
        select.props(f'display-value="{prompt}"')
    else:
        select.props(remove="display-value")


def _projection_prompt(cid: str) -> str:
    return "<choose embedding>" if cid.endswith(":gens") else "<choose projection>"


def _formchooser_options(cid: str) -> dict:
    if cid.endswith(":mapping"):
        return {"": "choose form", **{k: service.MAPPING_FORM_LABELS[k] for k in service.MAPPING_FORM_KEYS}}
    return {"": "choose form", **{k: service.COMMA_BASIS_FORM_LABELS[k] for k in service.COMMA_BASIS_FORM_KEYS}}


def _hover_index(detail) -> int | None:
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), None)
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else None
    if isinstance(detail, bool) or not isinstance(detail, (int, float)):
        return None
    index = int(detail)
    return index if index >= 0 else None


def _option_key(select: ui.select, index: int | None):
    if index is None:
        return None
    keys = list(select.options)
    return keys[index] if 0 <= index < len(keys) else None


@dataclass
class _Gesture:
    kind: str
    source: str | None = None
    apply: Callable | None = None
    baseline: "object | None" = None
    target_pred: Callable | None = None
    token: tuple | None = None
    reflowed: bool = False
    prev: "_Gesture | None" = None


class _Reconciler:
    def __init__(self, editor: Editor) -> None:
        self._editor = editor
        self._cb = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self.els: dict = {}
        self.inputs: dict = {}
        self.den_inputs: dict = {}
        self.frac_edits: dict = {}
        self.ratio_ops: dict = {}
        self.labels: dict = {}
        self.fracs: dict = {}
        self.ratio_faces: dict = {}
        self.stacked_faces: dict = {}
        self.stacked_w: dict = {}
        self.gensign_faces: dict = {}
        self.htmls: dict = {}
        self.ebk_sizes: dict = {}
        self.chart_keys: dict = {}
        self.range_keys: dict = {}
        self.exprs: dict = {}
        self.expr_state: dict = {}
        self.kinds: dict = {}
        self.selects: dict = {}  # preset cell id -> its q-select
        self.checks: dict = {}
        self.ptext_inputs: dict = {}
        self.rangeopts: dict = {}
        self.scheme_buttons: dict = {}
        self.mean_damage_tips: dict = {}
        self.target_limit_tip = None
        self.captions: dict = {}
        self.caption_html: dict = {}
        self.math_cells: dict = {}
        self.math_rendered: dict = {}
        self.fold_state: dict = {}
        self.cell_units: dict = {}
        self.cell_unit_text: dict = {}
        self._handle_dicts = (self.els, self.inputs, self.den_inputs, self.frac_edits, self.ratio_ops, self.labels, self.fracs, self.ratio_faces, self.stacked_faces, self.stacked_w, self.gensign_faces, self.htmls, self.ebk_sizes, self.chart_keys, self.range_keys, self.exprs, self.expr_state, self.kinds, self.selects, self.checks, self.ptext_inputs, self.rangeopts, self.scheme_buttons, self.mean_damage_tips, self.captions, self.caption_html, self.math_cells, self.math_rendered, self.fold_state, self.cell_units, self.cell_unit_text)
        self.gesture: _Gesture | None = None
        self.popup_state: dict = {}
        self.cell_kinds: dict[str, _KindHandlers] = {}
        for _ebk_kind in _EBK_SVG_KINDS:
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

        _gridvalue = _KindHandlers(self._build_gridvalue, self._update_gridvalue)
        for _gv_kind in ("mapping", "commacell", "unchangedcell",
                         "interestcell", "heldcell", "targetcell", "formcell"):
            self.cell_kinds[_gv_kind] = _gridvalue
        self.cell_kinds["prescalercell"] = _KindHandlers(self._build_prescalercell, self._update_prescalercell)
        self.cell_kinds["weightcell"] = _KindHandlers(self._build_weightcell, self._update_weightcell)
        self.cell_kinds["powerinput"] = _KindHandlers(self._build_powerinput, self._update_powerinput)
        self.cell_kinds["powerdisplay"] = _KindHandlers(self._build_powerdisplay, self._update_powerdisplay)
        self.cell_kinds["gentuningcell"] = _KindHandlers(self._build_gentuningcell, self._update_gentuningcell)

        self.cell_kinds["ptextedit"] = _KindHandlers(self._build_ptextedit, self._update_ptextedit)

        self.cell_kinds["genratio"] = _KindHandlers(self._build_genratio, self._update_ratio)
        self.cell_kinds["ratiocell"] = _gridvalue
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(self._build_commaratio, self._update_ratio)
        self.cell_kinds["tuningvalue"] = _KindHandlers(self._build_tuning_value, self._update_tuning_value)

        _value_builder = self._label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, self._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(self._label_builder("rtt-colheader"), self._update_label)
        self.cell_kinds["rowlabel"] = _KindHandlers(self._label_builder("rtt-rowlabel"), self._update_label)
        self.cell_kinds["ptext"] = _KindHandlers(self._label_builder("rtt-ptext"), self._update_ptext)
        self.cell_kinds["transpose"] = _KindHandlers(self._label_builder("rtt-transpose"), self._update_label)
        self.cell_kinds["boxtitle"] = _KindHandlers(self._label_builder("rtt-boxtitle"), None)

        self.cell_kinds["rangemode"] = _KindHandlers(self._build_rangemode, self._update_rangemode)
        self.cell_kinds["scheme_button"] = _KindHandlers(self._build_scheme_button, self._update_scheme_button)
        self.cell_kinds["rowtoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["coltoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["tiletoggle"] = _KindHandlers(self._build_foldtoggle, self._update_foldtoggle)
        self.cell_kinds["alltoggle"] = _KindHandlers(self._build_alltoggle, self._update_foldtoggle)

        self.cell_kinds["preset"] = _KindHandlers(self._build_preset, self._update_preset)
        self.cell_kinds["etpick"] = _KindHandlers(self._build_etpick, self._update_subpick)
        self.cell_kinds["commapick"] = _KindHandlers(self._build_commapick, self._update_subpick)
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
        self.cell_kinds["element_plus"] = _KindHandlers(self._build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(self._build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._build_colgrip)

    def drop(self, eid: str) -> None:
        self.els[eid].delete()
        for d in self._handle_dicts:
            d.pop(eid, None)

    def make_cell(self, cb: spreadsheet.CellBox) -> None:
        # build a cell's element in the active parent (the caller opens the freeze container),
        # register it + its kind (and audio key) so render() can place and reconcile it after.
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            self.cell_kinds[cb.kind].build(cb, wrap)
            if cb.audio is not None:
                self._tag_audio(wrap, cb)
        # Hover affordances. A gridded VALUE cell (VALUE_KINDS) becomes .rtt-zoomable — hovering it
        # pops the zoom magnifier (a client-side clone, _ZOOM_JS), and its own hover help (if any —
        # the editable cells' "type to edit…", the mean damage / dual(𝑞) explanations) folds INTO that
        # magnifier as data-zoomhelp rather than a separate tooltip, so value cells carry exactly one
        # hover popup. Every other control keeps its plain help tooltip. All wording still lives in
        # rtt.app.tooltips; a NEW kind must be classified there (READONLY_KINDS or a help entry) or
        # test_web_tooltips' completeness sweep fails. The mark/data-eid ride the wrap, so the magnifier
        # (which clones the wrap) and any tooltip hang off it too.
        help_text = tooltips.control_help(cb.kind, cb.id)
        if cb.kind in VALUE_KINDS:
            wrap.classes("rtt-zoomable")
            if help_text:
                wrap._props["data-zoomhelp"] = help_text
        elif help_text:
            if cb.id in tooltips.MEAN_DAMAGE_IDS:
                with wrap:
                    self.mean_damage_tips[cb.id] = ui.tooltip(help_text)
            elif cb.id == "preset:target":
                with wrap:
                    self.target_limit_tip = ui.tooltip(help_text)
            else:
                wrap.tooltip(help_text)
        self.els[cb.id] = wrap
        self.kinds[cb.id] = cb.kind
        if cb.kind.endswith(("plus", "minus")):
            wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
        edit_input = self.inputs.get(cb.id) or self.ptext_inputs.get(cb.id)
        if edit_input is not None:
            den = self.den_inputs.get(cb.id)
            guard = _STACKED_EXIT_JS if den is not None else None
            for fld in (edit_input, den) if den is not None else (edit_input,):
                fld.on("focus", lambda _=None, cid=cb.id: self._cb.on_cell_focus(cid), js_handler=guard)
                fld.on("blur", lambda _=None, cid=cb.id: self._cb.on_cell_blur(cid), js_handler=guard)
                fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
        if cb.kind in _WHEEL_STEPS:
            wrap.on("wheel", lambda e, cid=cb.id: self._cb.on_value_wheel(cid, e.args.get("deltaY")),
                    args=["deltaY"], js_handler=_INT_WHEEL_JS)

    def update_cell(self, cb: spreadsheet.CellBox) -> None:
        handlers = self.cell_kinds[cb.kind]
        if handlers.update is not None:
            handlers.update(cb)
        if cb.unit:
            if cb.id not in self.cell_units:
                with self.els[cb.id]:
                    self.cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                self.els[cb.id].classes(add="rtt-cell-united")
            if self.cell_unit_text.get(cb.id) != (cb.unit, cb.w):
                self.cell_units[cb.id].set_content(_bold_units(cb.unit))
                self.cell_units[cb.id].style(f"font-size:{_units_font(cb.unit, cb.w, _CELLUNIT_MAX_FONT):.2f}px")
                self.cell_unit_text[cb.id] = (cb.unit, cb.w)
        elif cb.id in self.cell_units:
            self.cell_units[cb.id].delete()
            self.cell_units.pop(cb.id, None)
            self.cell_unit_text.pop(cb.id, None)
            self.els[cb.id].classes(remove="rtt-cell-united")
        if cb.audio is not None:
            self._tag_audio(self.els[cb.id], cb)

    def _tag_audio(self, el, cb: spreadsheet.CellBox) -> None:
        tile, idx, cents = cb.audio
        el.classes(add="rtt-spk").props(f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"')

    def _put_stacked_face(self, cid: str, cls: str, main: str, sub: str, width: float) -> None:
        with ui.element("div").classes(cls):
            m = ui.label(main).classes("rtt-stacked-main")
            s = ui.label(sub).classes("rtt-stacked-sub")
        self.stacked_faces[cid] = (m, s)
        self.stacked_w[cid] = width
        self._size_stacked_main(m, main, sub, width)

    def _size_stacked_main(self, main_label, main: str, sub: str, width: float) -> None:
        solo = not sub
        main_label.classes(add="rtt-stacked-solo" if solo else "",
                           remove="" if solo else "rtt-stacked-solo")
        size = _digit_fit_font(len(main), width, float(_CELL_FONT)) if solo else float(_STACKED_MAIN_FONT)
        main_label.style(f"font-size:{size:.2f}px")

    def _sync_stacked_face(self, cid: str, main: str, sub: str) -> None:
        m, s = self.stacked_faces[cid]
        m.set_text(main)
        s.set_text(sub)
        self._size_stacked_main(m, main, sub, self.stacked_w[cid])

    def set_cents_face(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self._sync_stacked_face(cid, whole, f".{frac}" if frac else "")

    def cents_face(self, cb: spreadsheet.CellBox, cls: str) -> None:
        whole, frac = _cents_parts(cb.text)
        self._put_stacked_face(cb.id, cls, whole, f".{frac}" if frac else "", cb.w)

    def _ratio(self, cb: spreadsheet.CellBox, approx: bool, overlay: bool = False) -> None:
        face = ui.element("div").classes("rtt-ratio rtt-cellface" if overlay else "rtt-ratio")
        self.ratio_faces[cb.id] = face
        with face:
            self._ratio_body(cb, approx)

    def _ratio_body(self, cb: spreadsheet.CellBox, approx: bool) -> None:
        parts = _ratio_parts(cb.text)
        if parts and not all(p.lstrip("-").isdigit() for p in parts):
            parts = None
        whole = bool(parts) and parts[1] == "1"
        if approx and parts:
            ui.label("~").classes("rtt-approx")
        if parts:
            with ui.element("div").classes("rtt-frac rtt-frac-whole" if whole else "rtt-frac"):
                num = ui.label(parts[0]).classes("rtt-frac-num")
                den = ui.label(parts[1]).classes("rtt-frac-den")
            self.fracs[cb.id] = (num, den)
            self._fit_ratio(cb.id, parts[0], parts[1], cb.w, whole)
        else:
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value")

    def _fit_ratio(self, cid: str, num: str, den: str, width: float, whole: bool = False) -> None:
        size = _digit_fit_font(len(num), width, float(_CELL_FONT)) if whole else _ratio_font(num, den, width)
        font = f"font-size:{size:.2f}px"
        self.fracs[cid][0].style(font)
        self.fracs[cid][1].style(font)

    def cell_value(self, cid: str) -> str:
        num = str(self.inputs[cid].value).strip()
        if not num:
            return ""
        if num == "?":
            return "?/?"
        if "/" in num:
            return num
        den = str(self.den_inputs[cid].value).strip() if cid in self.den_inputs else ""
        return num if den in ("", "1", "?") else f"{num}/{den}"

    def decimal_value(self, cid: str) -> str:
        whole = str(self.inputs[cid].value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = str(self.den_inputs[cid].value).strip().lstrip(".") if cid in self.den_inputs else ""
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.inputs[cid].value = whole
        if cid in self.den_inputs:
            self.den_inputs[cid].value = frac

    def _build_svgfill(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.htmls[cb.id] = ui.html("").classes("rtt-svgfill")

    def _update_ebk(self, cb: spreadsheet.CellBox) -> None:
        if self.ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
            self.htmls[cb.id].set_content(ebk_svg(cb))
            self.ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)

    def _update_chart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
        if self.chart_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(
                _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label))
            self.chart_keys[cb.id] = key

    def _update_rangechart(self, cb: spreadsheet.CellBox) -> None:
        key = (cb.w, cb.h, cb.ranges, cb.values, cb.decimals)
        if self.range_keys.get(cb.id) != key:
            self.htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values, cb.decimals))
            self.range_keys[cb.id] = key

    def _build_count(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.math_cells[cb.id] = ui.html("").classes("rtt-count")

    def _build_symbol(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-symbol-cell")
        cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
        self.math_cells[cb.id] = ui.html("").classes(cls)

    @staticmethod
    def _matlabel_classes(text: str) -> str:
        return "rtt-matlabel rtt-matlabel-norm" if ("‖" in text or " " in text) else "rtt-matlabel"

    def _build_matlabel(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-matlabel-cell")
        self.math_cells[cb.id] = ui.html("").classes(self._matlabel_classes(cb.text))

    def _build_units(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-units-cell")
        self.math_cells[cb.id] = ui.html("").classes("rtt-units")

    def _update_mathcell(self, cb: spreadsheet.CellBox) -> None:
        if cb.kind == "units":
            html = _units_html(cb.text)
            if self.math_rendered.get(cb.id) != (html, cb.w):
                self.math_cells[cb.id].set_content(html)
                self.math_cells[cb.id].style(f"font-size:{_units_font(cb.text, cb.w, _UNITS_MAX_FONT):.2f}px")
                self.math_rendered[cb.id] = (html, cb.w)
            return
        html = _math_html(cb.text)
        font = None
        if cb.kind == "matlabel" and ":col:" in cb.id and "‖" not in cb.text and " " not in cb.text:
            w = spreadsheet._min_width_for_lines(cb.text, 1, _MATLABEL_FONT)
            if w > cb.w - 2:
                font = max(_MATLABEL_MIN_FONT, _MATLABEL_FONT * (cb.w - 2) / w)
        if self.math_rendered.get(cb.id) != (html, font):
            self.math_cells[cb.id].set_content(html)
            if font is not None:
                self.math_cells[cb.id].style(f"font-size:{font:.2f}px")
            self.math_rendered[cb.id] = (html, font)
            if cb.kind == "matlabel":
                self.math_cells[cb.id].classes(replace=self._matlabel_classes(cb.text))
            if cb.id == "optimization:mean_damage:symbol":
                wide = "‖" in cb.text
                self.math_cells[cb.id].classes(
                    replace="rtt-symbol rtt-opt-1line rtt-opt-wide" if wide
                    else "rtt-symbol rtt-opt-1line")

    def _build_caption(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-caption-cell")
        one_line = cb.id.startswith("optimization:") and cb.id != "optimization:mean_damage:caption"
        cls = "rtt-caption rtt-opt-1line" if one_line else "rtt-caption"
        if cb.align == "left":
            cls += " rtt-caption-left"
        self.captions[cb.id] = ui.html("").classes(cls)

    def _update_caption(self, cb: spreadsheet.CellBox) -> None:
        html = _underline_html(cb.text, cb.underlines)
        if self.caption_html.get(cb.id) != html:
            self.captions[cb.id].set_content(html)
            self.caption_html[cb.id] = html
        self.captions[cb.id].classes(add="rtt-caption-disabled" if cb.disabled else "",
                                     remove="" if cb.disabled else "rtt-caption-disabled")

    def _build_ptextpending(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.htmls[cb.id] = ui.html("").classes("rtt-ptextpending")

    def _update_ptextpending(self, cb: spreadsheet.CellBox) -> None:
        ed = self._editor
        off = not ed.settings.get("ebk", True)

        def squared(prefix, draft, suffix, vector_based):
            if not off:
                return prefix, draft, suffix
            return (prefix.translate(_EBK_SQUARE), draft.translate(_EBK_SQUARE),
                    suffix.translate(_EBK_SQUARE) + (_TRANSPOSE_MARK if vector_based else ""))

        if cb.id == "ptext:mapping:primes":
            committed = service.simple_matrix_to_ebk(cb.text, False) if off else cb.text
            prefix, draft, suffix = squared(*service.mapping_pending_text(committed, ed.pending_mapping_row), False)
            self.htmls[cb.id].set_content(
                f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
            self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            return
        if cb.id == "ptext:vectors:targets":
            targets = ed.target_override or service.target_interval_set(ed.target_spec, ed.state.domain_basis)
            committed = service.target_interval_vectors(targets, ed.state.d, ed.state.domain_basis)
            pending = ed.pending_target
        else:
            committed, pending = ed.state.comma_basis, ed.pending_comma
        prefix, draft, suffix = squared(*service.vector_list_pending_text(committed, pending), True)
        self.htmls[cb.id].set_content(
            f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
        self.htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")

    def _build_mathexpr(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.exprs[cb.id] = ui.html("").classes("rtt-mathexpr")

    def _update_mathexpr(self, cb: spreadsheet.CellBox) -> None:
        if self.expr_state.get(cb.id) != (cb.text, cb.w):
            self.exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
            self.expr_state[cb.id] = (cb.text, cb.w)

    def _build_gridvalue(self, cb: spreadsheet.CellBox, wrap) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        commit, preview = self._gridvalue_handlers(cb, spec)
        if spec.ratio_allowed:
            self._build_fraction(cb, wrap, commit, preview)
        else:
            wrap.classes("rtt-cell-input").props(f'data-vgroup="{_vgroup_key(cb)}"')
            inp = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput")
            inp.on("blur", commit, js_handler=_GROUP_EXIT_JS)
            self.inputs[cb.id] = inp
        self._arm_gridvalue(wrap, cb, spec)

    def _build_fraction(self, cb: spreadsheet.CellBox, wrap, commit, preview) -> None:
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
            ui.element("div").classes("rtt-frac-bar")
            den = ui.input(on_change=preview).props("dense borderless").classes("rtt-cellinput rtt-frac-den-in")
        num.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        den.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.inputs[cb.id] = num
        self.den_inputs[cb.id] = den
        self.frac_edits[cb.id] = box
        self._arm_ratio_ops(cb, wrap)

    def _arm_ratio_ops(self, cb: spreadsheet.CellBox, wrap) -> None:
        # the equave-reduce + reciprocate buttons flanking the bar of an editable interval ratio —
        # any editable interval ratiocell (commas / targets / held / intervals of interest) AND the
        # editable domain basis elements (nonstandard-domain box on: elementcell / elementratio). NOT
        # the read-only derived faces (the ~generator ratios, a non-projection unchanged column, the
        # standard read-only domain primes), which carry no value to edit in place. Each reveals on
        # hover, hides while the cell is edited, and reads disabled when its op is a no-op: an interval
        # already inside [1, equave) can't reduce, a unison can't reciprocate. They commit through
        # transform_interval, one undo step.
        if cb.kind not in ("ratiocell", "elementcell", "elementratio") or cb.pending \
                or cb.id.split(":", 1)[0] not in ("comma", "target", "held", "interest", "prime"):
            return
        wrap.classes("rtt-ratioed")
        with wrap:
            reduce_btn = ui.html(_control_svg("reduce")).classes("rtt-glyph rtt-ratio-op rtt-ratio-op-reduce") \
                .mark(f"{cb.id}:reduce").tooltip(tooltips.RATIO_REDUCE_HELP)
            recip_btn = ui.html(_control_svg("reciprocate")).classes("rtt-glyph rtt-ratio-op rtt-ratio-op-recip") \
                .mark(f"{cb.id}:reciprocate").tooltip(tooltips.RATIO_RECIPROCATE_HELP)
        reduce_btn.on("click", lambda _=None, cid=cb.id: self._cb.transform_interval(cid, "reduce"))
        recip_btn.on("click", lambda _=None, cid=cb.id: self._cb.transform_interval(cid, "reciprocate"))
        self.ratio_ops[cb.id] = (reduce_btn, recip_btn)
        self._sync_ratio_ops(cb.id, cb.text)

    def _sync_ratio_ops(self, cid: str, text: str) -> None:
        ops = self.ratio_ops.get(cid)
        if ops is None:
            return
        availability = service.interval_op_availability(text, self._editor.state.domain_basis)
        for btn, enabled in zip(ops, availability):
            btn.classes(add="" if enabled else "rtt-op-disabled",
                        remove="rtt-op-disabled" if enabled else "")

    def _gridvalue_handlers(self, cb: spreadsheet.CellBox, spec: _GridValueSpec):
        fn = getattr(self._cb, spec.commit)
        if spec.cid_arg:
            commit = lambda _=None, cid=cb.id: fn(cid)
            pv = getattr(self._cb, spec.preview) if spec.preview else None
            preview = (lambda e=None, cid=cb.id: pv(cid)) if pv else None
        else:
            commit = lambda _=None: fn()
            preview = (lambda e=None: fn(preview=True)) if spec.preview else None
        return commit, preview

    def _arm_gridvalue(self, wrap, cb: spreadsheet.CellBox, spec: _GridValueSpec) -> None:
        if spec.arm is None:
            return
        if spec.arm[0] == "row":
            self._arm_row_target(wrap, cb.gen)
        else:
            self._arm_col_target(wrap, spec.arm[1], cb.comma)

    def _update_gridvalue(self, cb: spreadsheet.CellBox) -> None:
        spec = _GRIDVALUE_SPECS[cb.kind]
        text = self._gridvalue_text(cb)
        if spec.ratio_allowed:
            self._update_fraction(cb, text)
        else:
            self.inputs[cb.id].value = text
        if spec.pending:
            target = self.els[cb.id] if spec.ratio_allowed else self.inputs[cb.id]
            target.classes(add="rtt-pending" if cb.pending else "",
                           remove="" if cb.pending else "rtt-pending")

    def _update_fraction(self, cb: spreadsheet.CellBox, text: str) -> None:
        num, den = _ratio_parts(text) or (text, "")
        ratio = den not in ("", "1")
        self.inputs[cb.id].value = num
        self.den_inputs[cb.id].value = den if ratio else ""
        self.frac_edits[cb.id].props(f'data-fracmode={"ratio" if ratio else "int"}')
        self._fit_fraction(cb.id, num, den, cb.w, ratio)
        self._sync_ratio_ops(cb.id, text)

    def _fit_fraction(self, cid: str, num: str, den: str, width: float, ratio: bool) -> None:
        size = _ratio_font(num, den, width) if ratio else _digit_fit_font(len(num), width, float(_CELL_FONT))
        style = f"font-size:{size:.2f}px"
        self.inputs[cid].style(style)
        self.den_inputs[cid].style(style)

    def _gridvalue_text(self, cb: spreadsheet.CellBox) -> str:
        if cb.pending and cb.kind in ("commacell", "mapping"):
            draft = self._editor.pending_comma if cb.kind == "commacell" else self._editor.pending_mapping_row
            v = draft[cb.prime] if draft is not None else None
            return "" if v is None else str(v)
        return "" if cb.blank else cb.text

    def _build_decimal(self, cb: spreadsheet.CellBox, wrap, commit, *, gen_index=None) -> None:
        wrap.classes("rtt-cell-input rtt-deccell")
        box = ui.element("div").classes("rtt-dec-edit")
        with box:
            with ui.element("div").classes("rtt-dec-main"):
                if gen_index is not None:
                    s = ui.label("").classes("rtt-gensign").mark(f"gensign:{gen_index}") \
                        .on("click", lambda _=None, i=gen_index: self._cb.act(lambda: self._editor.flip_generator(i)))
                    self._preview_control(s, lambda gi=gen_index: self._editor.flip_generator(gi))
                    self.gensign_faces[cb.id] = s
                whole = ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-whole-in")
            with ui.element("div").classes("rtt-dec-sub"):
                ui.label(".").classes("rtt-dec-dot")
                frac = ui.input().props("dense borderless").classes("rtt-cellinput rtt-dec-frac-in")
        whole.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        frac.on("blur", commit, js_handler=_STACKED_EXIT_JS)
        self.inputs[cb.id] = whole
        self.den_inputs[cb.id] = frac
        self.frac_edits[cb.id] = box

    def _update_decimal(self, cb: spreadsheet.CellBox, text: str, *, signed=False) -> None:
        if signed:
            sign, whole, frac = _gentuning_parts(text)
            if cb.id in self.gensign_faces:
                self.gensign_faces[cb.id].set_text(sign)
        else:
            whole, frac = _cents_parts(text)
        self.inputs[cb.id].value = whole
        self.den_inputs[cb.id].value = frac
        self.frac_edits[cb.id].props(f'data-decmode={"dec" if frac else "int"}')
        fit_w = cb.w - _GENSIGN_W if signed else cb.w
        self.frac_edits[cb.id].style(f"--dec-whole-font:{_digit_fit_font(len(whole), fit_w, float(_CELL_FONT)):.2f}px")

    def _build_prescalercell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda e=None, cid=cb.id: self._cb.on_prescaler_change(cid))

    def _update_prescalercell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_weightcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_decimal(cb, wrap, lambda e=None, cid=cb.id: self._cb.on_weight_change(cid))

    def _update_weightcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, cb.text)

    def _build_powerinput(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-cell-input rtt-cell-stacked")
        self.inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: self._cb.on_power_change(cid)) \
            .props("dense borderless").classes("rtt-cellinput")
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerinput(self, cb: spreadsheet.CellBox) -> None:
        self.inputs[cb.id].value = cb.text
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_powerdisplay(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._put_stacked_face(cb.id, "rtt-tuning-value rtt-cellface", *_power_parts(cb.text), cb.w)

    def _update_powerdisplay(self, cb: spreadsheet.CellBox) -> None:
        self._sync_stacked_face(cb.id, *_power_parts(cb.text))

    def _build_gentuningcell(self, cb: spreadsheet.CellBox, wrap) -> None:
        i = int(cb.id.rsplit(":", 1)[1])
        self._build_decimal(cb, wrap, lambda e=None, cid=cb.id: self._cb.on_gentuning_change(cid), gen_index=i)
        wrap.on("wheel.prevent",
                lambda e, cid=cb.id: self._cb.on_gentuning_wheel(cid, e.args.get("deltaY")),
                args=["deltaY"])
        wrap.on("mouseenter", lambda _=None, cid=cb.id: self._cb.gentuning_hover(cid))
        wrap.on("mouseleave", lambda _=None, cid=cb.id: self._cb.gentuning_unhover(cid))

    def _update_gentuningcell(self, cb: spreadsheet.CellBox) -> None:
        self._update_decimal(cb, "" if cb.blank else cb.text, signed=True)

    def _build_ptextedit(self, cb: spreadsheet.CellBox, wrap) -> None:
        if cb.id.startswith("ptext:projection:"):
            inp = ui.input(value=cb.text).props("dense borderless").classes("rtt-ptextedit")
            inp.on("blur", lambda e=None, cid=cb.id: self._cb.on_ptext_edit(cid, self.ptext_inputs[cid].value))
        else:
            inp = ui.input(value=cb.text,
                    on_change=lambda e, cid=cb.id: self._cb.on_ptext_edit(cid, e.value)) \
                .props("dense borderless").classes("rtt-ptextedit")
        self.ptext_inputs[cb.id] = inp

    def _update_ptextedit(self, cb: spreadsheet.CellBox) -> None:
        self.ptext_inputs[cb.id].value = cb.text
        self.ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    def _build_genratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=True)

    def _build_commaratio(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_ratio_face(cb, wrap, approx=False)

    def _build_ratio_face(self, cb: spreadsheet.CellBox, wrap, approx: bool) -> None:
        if cb.pending:
            wrap.classes(add="rtt-pending")
        if cb.pending and cb.text in ("?", "?/?", ""):
            self.labels[cb.id] = ui.label(cb.text).classes("rtt-value rtt-pending-q")
        else:
            self._ratio(cb, approx=approx)

    def _update_ratio(self, cb: spreadsheet.CellBox) -> None:
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")
        face = self.ratio_faces.get(cb.id)
        if face is None:
            return
        face.clear()
        self.fracs.pop(cb.id, None)
        self.labels.pop(cb.id, None)
        with face:
            self._ratio_body(cb, approx=(cb.kind == "genratio"))

    def _build_tuning_value(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.cents_face(cb, "rtt-tuning-value")

    def _update_tuning_value(self, cb: spreadsheet.CellBox) -> None:
        self.set_cents_face(cb.id, cb.text)
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")

    def _label_builder(self, cls: str):
        def build(cb, wrap):
            self.labels[cb.id] = ui.label(cb.text).classes(cls)
        return build

    def _update_label(self, cb: spreadsheet.CellBox) -> None:
        self.labels[cb.id].set_text(cb.text)
        self.els[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                remove="" if cb.pending else "rtt-pending")

    def _update_ptext(self, cb: spreadsheet.CellBox) -> None:
        self.labels[cb.id].set_text(cb.text)
        self.labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")

    def _build_rangemode(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-rangemode")
        opts = {}
        for mode in ("monotone", "tradeoff"):
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")
                ui.label(mode).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, m=mode: self._cb.on_range_mode(m))
            opts[mode] = opt
        self.rangeopts[cb.id] = opts

    def _update_rangemode(self, cb: spreadsheet.CellBox) -> None:
        for mode, opt in self.rangeopts[cb.id].items():
            (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
             else opt.classes(remove="rtt-rangeopt-on"))

    def _build_scheme_button(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.scheme_buttons[cb.id] = ui.button(cb.text, on_click=lambda: self._cb.act(self._editor.back_to_scheme),
                                               color=None).props("unelevated dense no-caps").classes("rtt-scheme-btn")

    def _update_scheme_button(self, cb: spreadsheet.CellBox) -> None:
        btn = self.scheme_buttons[cb.id]
        (btn.classes(add="rtt-scheme-btn-idle") if not self._editor.manual_tuning
         else btn.classes(remove="rtt-scheme-btn-idle"))

    def _build_foldtoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        item = cb.id.split("toggle:", 1)[1]
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None, it=item: self._cb.on_toggle(it))

    def _build_alltoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.htmls[cb.id] = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes("rtt-glyph rtt-toggle")
        self.fold_state[cb.id] = cb.text
        wrap.on("click", lambda _=None: self._cb.on_toggle_all())

    def _update_foldtoggle(self, cb: spreadsheet.CellBox) -> None:
        if self.fold_state.get(cb.id) != cb.text:
            self.htmls[cb.id].set_content(_control_svg(_FOLD_GLYPH[cb.text]))
            self.fold_state[cb.id] = cb.text

    def _target_preset_values(self):
        if self._editor.target_override is not None or service.is_all_interval(self._editor.tuning_scheme):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:
            limit = service.default_target_limit(
                family, self._editor.state.domain_basis)
        return limit, family

    def _arm_option_hover(self, sel, wrap, cid: str) -> None:
        sel.add_slot("option", f"""
            <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cid}">
                <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
            </q-item>
        """)
        wrap.on("opthover", lambda e: self._cb.on_chooser_hover(cid, e.args), args=["detail"])
        sel.on("popup-show", lambda _=None: self._cb.on_popup(cid, True))
        sel.on("popup-hide", lambda _=None: self._cb.on_popup(cid, False))

    def _build_preset(self, cb: spreadsheet.CellBox, wrap) -> None:
        name = cb.id.split(":")[1]
        if name == "target":
            limit, family = self._target_preset_values()
            with ui.element("div").classes("rtt-preset-target"):
                num = ui.input(value=_limit_text(limit),
                        on_change=lambda e: self._cb.on_target_change()) \
                    .props('dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300').classes("rtt-preset-num")
                # make the limit input CONTROLLED (ui.input defaults loopback off, leaving the box
                # uncontrolled during typing). Off, the server can't overwrite what was typed, so a
                # rejected non-number couldn't be reverted nor a value reddened-in-place. On, the
                # server's value always wins — debounce keeps the echo to once-per-settled-entry.
                num.LOOPBACK = True
                num._props['loopback'] = True
                num.on("wheel", lambda e: self._cb.on_target_limit_wheel(e.args.get("deltaY")),
                       args=["deltaY"], js_handler=_INT_WHEEL_JS)
                num.on("focus", lambda _=None: self._cb.on_cell_focus(cb.id))
                num.on("blur", lambda _=None, cid=cb.id: self._cb.on_cell_blur(cid))
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
                        on_change=lambda e: self._cb.on_target_change()) \
                    .props(_select_props(cb.w - 30)).classes("rtt-preset")
            _set_offlist_prompt(sel, family)
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = (num, sel)
        elif name == "temperament":
            value = presets.identify(self._editor.state)
            sel = _GroupedSelect(presets.temperament_options(), value=value,
                    is_divider=presets.is_divider,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = sel
        elif name == "prescaler":
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            sel = ui.select(options, value=value,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value)
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = sel
        elif name == "projection":
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            value = value if value in options else None
            sel = ui.select(options, value=value,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, value, prompt=_projection_prompt(cb.id))
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = sel
        else:
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme),
                self._editor.settings["alt_complexity"], self._editor.settings["weighting"])
            name = self._editor.displayed_tuning_scheme_name
            scheme = name if name in options else None
            sel = ui.select(options, value=scheme,
                    on_change=lambda e: self._cb.on_preset(cb.id, e.value)) \
                .props(_select_props(cb.w)).classes("rtt-preset")
            _set_offlist_prompt(sel, scheme)
            self._arm_option_hover(sel, wrap, cb.id)
            self.selects[cb.id] = sel

    def _chooser_reflow_hold(self, cid: str) -> bool:
        # True while a generic chooser hover's REFLOW preview is re-rendering the grid for THIS
        # chooser: the hovered chooser's q-select value + open popup must stay steady across that
        # re-render (re-setting a q-select's value / options would disrupt or close its open popup),
        # so the cell's update is skipped while it holds. Held by chooser GROUP, not exact id: a
        # preset and its copy (preset:tuning ⟷ preset:tuning:gens, preset:projection ⟷
        # preset:projection:gens — one selection shown in two tiles) must move together, else the
        # non-hovered twin would flip to the hypothetical value while the hovered one stays put, so
        # the two faces would disagree mid-preview. The group is the cid's first two ":"-segments
        # (the copy adds a 3rd), so the base + every copy share it. The generic-chooser analogue of
        # the temperament guard below, which groups its own copies via the "preset:temperament" prefix.
        g = self.gesture
        if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
            return False
        group = lambda c: ":".join(c.split(":")[:2])
        return group(cid) == group(g.source)

    def _update_preset(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        if cb.id.startswith("preset:temperament"):
            if self.gesture is not None and self.gesture.kind == "temp" and self.gesture.reflowed:
                return
            value = presets.identify(self._editor.state)
            self.selects[cb.id].value = value
            _set_offlist_prompt(self.selects[cb.id], value)
        elif cb.id == "preset:target":
            num, sel = self.selects[cb.id]
            limit, family = self._target_preset_values()
            num.value = _limit_text(limit)
            sel.value = family
            _set_offlist_prompt(sel, family)
            num.set_enabled(not cb.disabled)
            sel.set_enabled(not cb.disabled)
            self._sync_target_limit_error(num, family, limit)
        elif cb.id == "preset:prescaler":
            options = list(presets.prescaler_options(self._editor.settings["alt_complexity"]))
            value = self._editor.displayed_prescaler_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value)
            self.selects[cb.id].set_enabled(not cb.disabled)
        elif cb.id.startswith("preset:projection"):
            options = presets.projection_options(self._editor.state)
            value = self._editor.displayed_projection_scheme_name
            value = value if value in options else None
            self.selects[cb.id].set_options(options, value=value)
            _set_offlist_prompt(self.selects[cb.id], value, prompt=_projection_prompt(cb.id))
            self.selects[cb.id].set_enabled(not cb.disabled)
        else:
            name = self._editor.displayed_tuning_scheme_name
            options = presets.tuning_scheme_options(
                service.is_all_interval(self._editor.tuning_scheme),
                self._editor.settings["alt_complexity"], self._editor.settings["weighting"])
            scheme = name if name in options else None
            self.selects[cb.id].set_options(options, value=scheme)
            _set_offlist_prompt(self.selects[cb.id], scheme)
            self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_subpick(self, cb, wrap, options, value):
        sel = ui.select(options, value=value if value in options else None,
                on_change=lambda e, cid=cb.id: self._cb.on_subpick(cid, e.value)) \
            .props(_select_props(_SUBPICK_POPUP_W)).classes("rtt-preset rtt-subpick")
        _set_offlist_prompt(sel, value if value in options else None)
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _build_etpick(self, cb, wrap):
        db = self._editor.state.domain_basis
        value = None if cb.pending else presets.identify_et(self._editor.state.mapping[cb.gen], db)
        self._build_subpick(cb, wrap, presets.et_options(db), value)

    def _build_commapick(self, cb, wrap):
        db = self._editor.state.domain_basis
        value = None if cb.pending else presets.identify_comma(self._editor.state.comma_basis[cb.comma], db)
        self._build_subpick(cb, wrap, presets.comma_options(db), value)

    def _update_subpick(self, cb):
        if self.gesture is not None and self.gesture.kind == "temp" and self.gesture.reflowed:
            return
        sel = self.selects.get(cb.id)
        if not isinstance(sel, ui.select):
            return
        db = self._editor.state.domain_basis
        if cb.id.startswith("etpick:"):
            options = presets.et_options(db)
            if cb.pending or cb.gen >= len(self._editor.state.mapping):
                value = None
            else:
                value = presets.identify_et(self._editor.state.mapping[cb.gen], db)
        else:
            options = presets.comma_options(db)
            if cb.pending or cb.comma >= len(self._editor.state.comma_basis):
                value = None
            else:
                value = presets.identify_comma(self._editor.state.comma_basis[cb.comma], db)
        value = value if value in options else None
        sel.set_options(options, value=value)
        _set_offlist_prompt(sel, value)

    def _sync_target_limit_error(self, num, family, limit) -> None:
        problem = service.target_limit_problem(family, limit)
        num.classes(add="rtt-limit-error" if problem else "",
                    remove="" if problem else "rtt-limit-error")
        if self.target_limit_tip is not None:
            self.target_limit_tip.set_text(
                tooltips.target_limit_help(problem) if problem
                else tooltips.control_help("preset", "preset:target"))
            self.target_limit_tip.classes(add="rtt-tip-error" if problem else "",
                                          remove="" if problem else "rtt-tip-error")

    def _build_control_select(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = ui.select(list(cb.values), value=cb.text or None,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _update_control_select(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.selects[cb.id].set_options(list(cb.values), value=cb.text or None)
        self.selects[cb.id].set_enabled(not cb.disabled)

    def _build_control_check(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.checks[cb.id] = ui.checkbox(cb.text, value=cb.checked,
                on_change=lambda e, cid=cb.id: self._cb.on_control_select(cid, e.value)) \
            .props("dense").classes("rtt-control-check")
        apply = self._control_check_preview(cb)
        if apply is not None:
            self._preview_control(wrap, apply)

    def _control_check_preview(self, cb: spreadsheet.CellBox):
        if cb.id == "control:diminuator":
            return lambda: self._editor.set_diminuator_replaced(
                not service.diminuator_replaced(self._editor.tuning_scheme))
        if cb.id == "control:all_interval":
            return lambda: self._editor.set_all_interval(
                not service.is_all_interval(self._editor.tuning_scheme))
        return None

    def _update_control_check(self, cb: spreadsheet.CellBox) -> None:
        self.checks[cb.id].value = cb.checked

    def _build_formchooser(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = ui.select(_formchooser_options(cb.id), value=cb.text or "",
                on_change=lambda e, c=cb.id: self._cb.on_form_choose(c, e.value)) \
            .props(_select_props(cb.w)).classes("rtt-preset")
        self._arm_option_hover(sel, wrap, cb.id)
        self.selects[cb.id] = sel

    def _update_formchooser(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.selects[cb.id].set_options(_formchooser_options(cb.id), value=cb.text or "")

    def _preview_control(self, el, apply) -> None:
        el.on("mouseenter", lambda _=None: self._cb.control_hover(apply))
        el.on("mouseleave", lambda _=None: self._cb.control_unhover())

    def _preview_rank_remove(self, el, axis: str, idx: int) -> None:
        el.on("mouseenter", lambda _=None: self._cb.rank_remove_hover(axis, idx))
        el.on("mouseleave", lambda _=None: self._cb.rank_remove_unhover())

    def _build_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))
        self._preview_control(wrap, self._editor.shrink)

    def _build_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn") \
            .on("click", lambda _=None: self._cb.act(self._editor.expand))
        self._preview_control(wrap, self._editor.expand)

    def _build_gen_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))
        self._preview_rank_remove(wrap, "row", cb.gen)

    def _build_gen_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping"))

    def _build_map_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        if cb.pending:
            ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
                .on("click", lambda _=None: self._cb.act(self._editor.cancel_pending_mapping_row))
            return
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None, idx=cb.gen: self._cb.act(lambda: self._editor.remove_mapping_row(idx)))
        self._preview_rank_remove(wrap, "row", cb.gen)

    def _build_map_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-mapping") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_mapping_row, "mapping"))

    def _build_map_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
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

    def _arm_row_target(self, wrap, gen: int) -> None:
        # the mapping row is the drop target for a dragged generator row: dragover keeps every cell a
        # droppable copy surface (preventDefault makes a drop land here; dropEffect='copy' gives the +
        # cursor), dragenter previews dropping the dragged row INTO this row, drop commits it. The py
        # preview/drop are no-ops unless a row drag is actually in flight (_row_drag set), so a
        # non-combine drag — or a row over its own cells — passing over a cell changes nothing.
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, idx=gen: self._preview_row_drop(idx))
        wrap.on("drop.prevent", lambda _=None, idx=gen: self._drop_on_row(idx))

    def _begin_row_drag(self, idx: int) -> None:
        self._row_drag = idx
        self._cb.combine_begin()

    def _end_row_drag(self) -> None:
        self._row_drag = None
        self._cb.combine_end()

    def _preview_row_drop(self, idx: int) -> None:
        src = self._row_drag
        valid = src is not None and src != idx
        apply = (lambda: self._editor.add_mapping_row_to(src, idx)) if valid else None
        target = (lambda cb: cb.kind == "mapping" and getattr(cb, "gen", None) == idx) if valid else None
        self._cb.combine_preview(apply, target)

    def _drop_on_row(self, idx: int) -> None:
        src = self._row_drag
        self._row_drag = None
        if src is not None and src != idx:
            self._cb.combine_commit(lambda: self._editor.add_mapping_row_to(src, idx))
        else:
            self._cb.combine_end()

    _INTERVAL_COMBINE = {
        "comma": "add_comma_to", "target": "add_target_to",
        "held": "add_held_to", "interest": "add_interest_to",
    }

    def _build_int_drag(self, cb: spreadsheet.CellBox, wrap) -> None:
        group = cb.id.split(":")[1]
        wrap.classes("rtt-drag-handle rtt-col-handle").props("draggable=true")
        wrap.on("dragstart", lambda _=None, g=group, idx=cb.comma: self._begin_col_drag(g, idx))
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, g=group, idx=cb.comma: self._preview_int_drop(g, idx))
        wrap.on("dragend", lambda _=None: self._end_col_drag())
        wrap.on("drop.prevent", lambda _=None, g=group, idx=cb.comma: self._drop_on_interval(g, idx))
        ui.icon("drag_indicator").classes("rtt-grip")

    def _arm_col_target(self, wrap, group: str, idx: int) -> None:
        wrap.on("dragover", js_handler="(e)=>{e.preventDefault();e.dataTransfer.dropEffect='copy';}")
        wrap.on("dragenter.prevent", lambda _=None, g=group, i=idx: self._preview_int_drop(g, i))
        wrap.on("drop.prevent", lambda _=None, g=group, i=idx: self._drop_on_interval(g, i))

    def _int_combine(self, group: str, idx: int):
        if self._col_drag is None:
            return None
        src_group, src = self._col_drag
        if src_group != group or src == idx:
            return None
        combine = getattr(self._editor, self._INTERVAL_COMBINE[group])
        return lambda: combine(src, idx)

    def _begin_col_drag(self, group: str, idx: int) -> None:
        self._col_drag = (group, idx)
        self._cb.combine_begin()

    def _end_col_drag(self) -> None:
        self._col_drag = None
        self._cb.combine_end()

    _GROUP_CELL_KIND = {"comma": "commacell", "target": "targetcell",
                        "held": "heldcell", "interest": "interestcell"}

    def _preview_int_drop(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        kind = self._GROUP_CELL_KIND[group]
        target = (lambda cb: cb.kind == kind and getattr(cb, "comma", None) == idx) if apply is not None else None
        self._cb.combine_preview(apply, target)

    def _drop_on_interval(self, group: str, idx: int) -> None:
        apply = self._int_combine(group, idx)
        self._col_drag = None
        if apply is not None:
            self._cb.combine_commit(apply)
        else:
            self._cb.combine_end()

    def _build_basis_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn-v") \
            .on("click", lambda _=None: self._cb.act(self._editor.shrink))
        self._preview_control(wrap, self._editor.shrink)

    def _build_comma_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_comma, self._editor.remove_comma, rank_axis="comma")

    def _build_comma_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-comma") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_comma, "comma"))

    def _build_element_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-element") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_element, "element"))

    def _build_element_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        action = self._editor.remove_element if cb.id.endswith(":pending") \
            else (lambda idx=cb.prime: self._editor.remove_domain_element(idx))
        btn = "rtt-minus-btn-v" if ":basis" in cb.id else "rtt-minus-btn"
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes(f"rtt-glyph {btn}") \
            .on("click", lambda _=None: self._cb.act(action))
        self._preview_control(wrap, action)

    def _build_list_minus(self, cb: spreadsheet.CellBox, wrap, cancel, remove, rank_axis: str | None = None) -> None:
        pending = cb.id.endswith(":pending")
        action = cancel if pending else (lambda idx=cb.comma: remove(idx))
        wrap.classes("rtt-minus-zone")
        ui.html(_control_svg("minus")).classes("rtt-glyph rtt-minus-btn") \
            .on("click", lambda _=None: self._cb.act(action))
        if rank_axis is not None and not pending:
            self._preview_rank_remove(wrap, rank_axis, cb.comma)
        else:
            self._preview_control(wrap, action)

    def _build_interest_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_interest, self._editor.remove_interest)

    def _build_interest_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-interest") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_interest, "interest"))

    def _build_held_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_held, self._editor.remove_held)

    def _build_held_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-held") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_held, "held"))

    def _build_target_minus(self, cb: spreadsheet.CellBox, wrap) -> None:
        self._build_list_minus(cb, wrap, self._editor.cancel_pending_target, self._editor.remove_target)

    def _build_target_plus(self, cb: spreadsheet.CellBox, wrap) -> None:
        ui.html(_control_svg("plus")).classes("rtt-glyph rtt-fanbtn rtt-hk-target") \
            .on("click", lambda _=None: self._cb.add_interval(self._editor.add_target, "target"))

    def _build_colgrip(self, cb: spreadsheet.CellBox, wrap) -> None:
        # drag one column's grip onto another to MOVE/reorder it; the per-list "grip:{list}:add" zone
        # is drop-only — the append / into-empty-list target on the stub gridline, so dropping into a
        # list is always "drop on the gridline" (no separate header/+ target). Mirrors the proven
        # drag-to-combine handle EXACTLY (which the user confirmed works), so it relies on no global
        # drag.js / dragging-class: a grip is BOTH source AND drop target, with a per-element dragover
        # preventDefault (client-side, so it doesn't round-trip per move) marking it a valid target.
        # The dragged column's (list, idx) is held server-side from dragstart through drop.
        _, lst, tail = cb.id.split(":")
        wrap.on("dragover", js_handler="(e) => e.preventDefault()")
        if tail == "add":
            wrap.classes("rtt-colgrip rtt-coldrop")
            wrap.on("dragenter.prevent", lambda _=None, l=lst: self._cb.on_drag_enter(l, None))
            wrap.on("drop.prevent", lambda _=None, l=lst: self._cb.on_drop(l, None))
            return
        idx = cb.comma
        wrap.classes("rtt-drag-handle rtt-colgrip").props("draggable=true")
        wrap.on("dragstart", lambda _=None, l=lst, i=idx: self._cb.on_drag_start(l, i))
        wrap.on("dragenter.prevent", lambda _=None, l=lst, i=idx: self._cb.on_drag_enter(l, i))
        wrap.on("dragend", lambda _=None: self._cb.on_drag_end())
        wrap.on("drop.prevent", lambda _=None, l=lst, i=idx: self._cb.on_drop(l, i))
        ui.icon("drag_indicator").classes("rtt-grip")


@ui.page("/")
def index(state: str | None = None) -> None:
    ui.add_css(_CSS)
    ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS}")
    ui.add_body_html(f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>")
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
    ui.add_body_html(f"<script>{_FRACTION_JS}</script>")
    ui.add_body_html(f"<script>{_DECIMAL_JS}</script>")
    ui.add_body_html(f"<script>{_TABNAV_JS}</script>")
    ui.add_body_html(f"<script>{_ZOOM_JS}</script>")
    ui.add_body_html(
        f"<script>window.rttTour={{steps:{json.dumps(_TOUR_STEPS)},autostart:true}};\n"
        f"{_TOUR_JS}</script>")
    # trim NiceGUI's default 16px content padding to a slim margin around the whole app
    ui.query(".nicegui-content").style("padding:6px")

    # the busy scrim (fixed, viewport-covering, hidden until revealed): shown while a heavy
    # state change re-solves the tuning off the event loop, so the user sees "Computing…"
    # rather than a frozen grid, and the clicks they'd otherwise pile up are swallowed. Built
    # once, here, so it outlives every grid rebuild (see _request_render / _commit_render).
    with ui.element("div").classes("rtt-busy") as busy_overlay:
        with ui.element("div").classes("rtt-busy-card"):
            ui.element("div").classes("rtt-busy-spin")
            ui.label("Computing…")

    # Dark mode is a global VIEWING preference, kept out of the document's Show settings: it
    # persists under its own store key, so "select all / none" and Reset — which act only on
    # editor.settings — never touch it. apply_theme drives the CSS overlay (assets/rtt-dark.css)
    # by toggling the `rtt-dark` class on <body>, and paints the margin frame inline (its colour
    # beats Quasar's body background the same way the static "#fff" did before).
    dark_mode = [bool(_doc_store().get(_DARK_KEY, False))]

    def _dark_icon():
        return "light_mode" if dark_mode[0] else "dark_mode"

    def apply_theme():
        body = ui.query("body")
        body.classes(add="rtt-dark") if dark_mode[0] else body.classes(remove="rtt-dark")
        body.style(f"background:{_DARK_FRAME if dark_mode[0] else '#fff'}")

    def on_dark_toggle():
        dark_mode[0] = not dark_mode[0]
        _doc_store()[_DARK_KEY] = dark_mode[0]
        apply_theme()
        dark_btn.props(f"icon={_dark_icon()}")

    apply_theme()

    def _clamp_chapter(v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return show_settings.CHAPTER_DEFAULT
        return min(show_settings.CHAPTER_STAR, max(show_settings.CHAPTER_MIN, v))

    chapter = [_clamp_chapter(_doc_store().get(_CHAPTER_KEY, show_settings.CHAPTER_DEFAULT))]

    def _chapter_reading(ch: int) -> str:
        label = "★" if ch >= show_settings.CHAPTER_STAR else str(ch)
        return f"{label}: {show_settings.CHAPTER_TITLES[ch]}"

    def apply_chapter():
        ch = chapter[0]
        chapter_reading.set_text(_chapter_reading(ch))
        chapter_reading.classes(add="rtt-chapter-reading-narrow") \
            if len(show_settings.CHAPTER_TITLES[ch]) >= 25 \
            else chapter_reading.classes(remove="rtt-chapter-reading-narrow")

        def _gate(el, cls, hidden):
            el.classes(add=cls) if hidden else el.classes(remove=cls)
        for key, parts in tile_parts.items():
            for part in parts:
                _gate(part, "rtt-chap-invisible", show_settings.reveal_chapter(key) > ch)
        for key, row in show_rows.items():
            _gate(row, "rtt-chap-hidden", show_settings.reveal_chapter(key) > ch)
        if "audio_bank" in refs:
            _gate(refs["audio_bank"], "rtt-chap-invisible", show_settings.CHAPTER_MIN > ch)
        _sync_show_availability()

    def _available_keys():
        return [k for k in show_settings.IMPLEMENTED
                if show_settings.reveal_chapter(k) <= chapter[0]]

    def _sync_show_availability():
        for key, box in boxes.items():
            disabled = key not in show_settings.IMPLEMENTED \
                or show_settings.reveal_chapter(key) > chapter[0]
            box.props("disable") if disabled else box.props(remove="disable")
            # the example sample greys WITH the checkbox — the single disabled styling for every
            # reason (the box's own label/glyph grey via Quasar's .disabled; this matches the sample)
            examples[key].classes(add="rtt-ex-disabled") if disabled \
                else examples[key].classes(remove="rtt-ex-disabled")
        states = [editor.settings[k] for k in _available_keys()]
        was_building = building[0]
        building[0] = True
        try:
            select_all_box.value = bool(states) and all(states)
        finally:
            building[0] = was_building
        select_all_box.classes(add="rtt-show-mixed") if (any(states) and not all(states)) \
            else select_all_box.classes(remove="rtt-show-mixed")

    def on_chapter_change(v):
        if building[0]:
            return
        chapter[0] = _clamp_chapter(v)
        _doc_store()[_CHAPTER_KEY] = chapter[0]
        editor.disable_hidden_settings(chapter[0])
        apply_chapter()
        render()

    def reset_everything():
        chapter[0] = show_settings.CHAPTER_DEFAULT
        _doc_store()[_CHAPTER_KEY] = chapter[0]
        act(editor.reset)
        apply_chapter()

    # The Editor owns the whole document — temperament, view selections, the Show
    # settings (editor.settings) and the folded rows/columns/tiles (editor.collapsed) —
    # and the undo/redo history over all of it. We persist that document per browser
    # (app.storage.user) so a refresh restores exactly where the user left off; a
    # corrupt/old blob is ignored, falling back to the as-shipped defaults.
    editor = Editor()
    load_failed = [False]
    loaded_from_url = False
    if state:
        try:
            editor.load(_decode_state(state))
            loaded_from_url = True
        except Exception:
            _log.exception("shared URL state failed to load; falling back: %.200r", state)
    if not loaded_from_url:
        stored = _doc_store().get(_STORE_KEY)
        if stored:
            try:
                editor.load(stored)
            except Exception:
                _log.exception("stored document failed to load; using defaults: %.200r", stored)
                load_failed[0] = True
    rec = _Reconciler(editor)
    building = [False]
    last_lay = [None]
    refs: dict = {}
    target_limit_commit = [None]

    def _on_disconnect():
        if target_limit_commit[0] is not None:
            target_limit_commit[0].cancel()
        end_gesture()

    # capture this page's Client now, while the slot context is valid. render() can run from an
    # off-loop background task (_commit_render), where the slot stack is empty and ui.run_javascript
    # — which finds its client via the current slot — would raise. Calling client.run_javascript on
    # the captured client needs no slot, so the busy-scrim push works from the background task too.
    page_client = ui.context.client
    page_client.on_disconnect(_on_disconnect)
    ui.run_javascript(_OPTION_HOVER_DELEGATION)
    ui.run_javascript(_TOOLTIP_DISMISS_JS)
    ui.run_javascript(_BUSY_JS)
    if loaded_from_url:
        ui.run_javascript("window.history.replaceState({}, '', window.location.pathname)")

    def col_tokens(name):
        ids = last_lay[0].identities if last_lay[0] is not None else None
        return [tok for tok, _ in (ids or {}).get(name, [])]

    def _token_index(cid, name):
        token = cid.split(":", 1)[1]
        for i, tok in enumerate(col_tokens(name)):
            if str(tok) == token:
                return i
        return None


    gesture_rendering = [False]
    # a comma−/mapping− hover's transient rank-removal preview — None | ("comma", idx) | ("row", idx).
    # Pure view state (not a gesture, not document state): render() threads it into the build so the
    # builder reflows the dual axis (the born generator/comma ghosts green, the leaver reds, the
    # survivors amber). Set on mouseenter, cleared on mouseleave and on any committing act().
    rank_remove = [None]
    rank_rendering = [False]

    def gesture_render():
        gesture_rendering[0] = True
        try:
            render()
        finally:
            gesture_rendering[0] = False

    def end_gesture():
        g, rec.gesture = rec.gesture, None
        if g is not None and g.token is not None:
            editor.restore_for_preview(g.token)
        return g

    def end_chooser_gesture():
        if rec.gesture is not None and rec.gesture.kind == "chooser":
            end_gesture()

    def compute_rings(lay):
        if not editor.settings["preview_highlighting"]:
            return frozenset(), frozenset()
        static_red = frozenset(cb.id for cb in lay.cells if cb.preview_remove)
        static_amber = frozenset(cb.id for cb in lay.cells if cb.preview_change)
        amber, red = _gesture_rings(lay)
        pending = frozenset(cb.id for cb in lay.cells if cb.pending)
        return (amber | static_amber) - pending, (red | static_red) - pending

    def _gesture_rings(lay):
        g = rec.gesture
        if g is None:
            return frozenset(), frozenset()
        if g.apply is not None:
            base = g.baseline if g.baseline is not None else lay
            token = editor.capture_for_preview()
            try:
                g.apply()
                hyp = editor.layout(prev_ids=base.identities)
                amber = spreadsheet.changed_cell_ids(base, hyp)
                red = spreadsheet.removed_cell_ids(lay, hyp)
            finally:
                editor.restore_for_preview(token)
            return amber - {g.source}, red
        if g.baseline is not None:
            amber = spreadsheet.changed_cell_ids(g.baseline, lay) - {g.source}
            if g.target_pred is not None:
                amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
            return amber, frozenset()
        return frozenset(), frozenset()

    def paint_cell(eid, amber, red):
        # idempotently set one cell's ring classes from the computed sets (NiceGUI's classes() is
        # change-detected, so a no-op repaint sends nothing over the socket)
        el = rec.els.get(eid)
        if el is None:
            return
        el.classes(add="rtt-preview-change" if eid in amber else "",
                   remove="" if eid in amber else "rtt-preview-change")
        el.classes(add="rtt-preview-remove" if eid in red else "",
                   remove="" if eid in red else "rtt-preview-remove")

    def paint_rings():
        lay = last_lay[0]
        if lay is None:
            return
        amber, red = compute_rings(lay)
        for cb in lay.cells:
            paint_cell(cb.id, amber, red)

    def take_over_gesture():
        was = end_gesture()
        if was is not None and was.reflowed:
            gesture_render()

    def _edit_candidate(apply):
        g = rec.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        paint_rings()

    def _rebase_edit_gesture():
        g = rec.gesture
        if g is not None and g.kind == "edit":
            g.baseline = last_lay[0]
            paint_rings()

    def _edit_vector_grid(spec, preview=False):
        if building[0] or (spec.guard is not None and not spec.guard()):
            return
        d = editor.state.d
        toks = col_tokens(spec.group)
        cell_id = spec.cell_id
        if spec.pending() is not None:
            pt = spreadsheet.pending_token(toks)
            if any(cell_id(pt, p) not in rec.inputs for p in range(d)):
                if preview:
                    _edit_candidate(None)
                return
            values = [_parse_int(rec.inputs[cell_id(pt, p)].value) for p in range(d)]
            if preview:
                _edit_candidate((lambda v=values: spec.set_pending(v)) if spec.draft_arms else None)
                return
            spec.set_pending(values)
            if spec.pending() is None:
                # the change is applied (it retunes) — render OFF the loop, then rebase the gesture
                # on the fresh layout so its rings go away NOW (no blur fires)
                _request_render(after=_rebase_edit_gesture)
            return
        count = spec.count()
        if len(toks) != count or any(
                cell_id(toks[i], p) not in rec.inputs for i in range(count) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return
        vectors = [[_parse_int(rec.inputs[cell_id(toks[i], p)].value) for p in range(d)]
                   for i in range(count)]
        if any(v is None for vec in vectors for v in vec):
            if preview:
                _edit_candidate(None)
            return
        if spec.validate is not None and not spec.validate(vectors):
            if preview:
                _edit_candidate(None)
                return
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
            render()
            return
        if preview:
            _edit_candidate(lambda: spec.commit(vectors))
            return
        spec.commit(vectors)
        _request_render()  # a matrix/vector-list edit retunes — render off the loop

    _MAPPING_EDIT = _VecGridEdit(
        group="gens", count=lambda: len(editor.state.mapping),
        cell_id=ids.mapping_cell,
        pending=lambda: editor.pending_mapping_row, set_pending=editor.set_pending_mapping_row,
        commit=editor.edit_mapping,
        validate=lambda rows: service.is_proper_temperament(rows),
        guard=lambda: editor.settings["temperament_tiles"])
    _COMMA_EDIT = _VecGridEdit(
        group="commas", count=lambda: len(editor.state.comma_basis),
        cell_id=ids.comma_cell,
        pending=lambda: editor.pending_comma, set_pending=editor.set_pending_comma,
        commit=editor.edit_comma_basis,
        validate=lambda basis: service.is_proper_temperament(service.from_comma_basis(basis).mapping))
    _INTEREST_EDIT = _VecGridEdit(
        group="interest", count=lambda: len(editor.interest_vectors),
        cell_id=ids.interest_cell,
        pending=lambda: editor.pending_interest, set_pending=editor.set_pending_interest,
        commit=editor.set_interest_vectors, draft_arms=True)
    _HELD_EDIT = _VecGridEdit(
        group="held", count=lambda: len(editor.held_vectors),
        cell_id=ids.held_cell,
        pending=lambda: editor.pending_held, set_pending=editor.set_pending_held,
        commit=editor.set_held_vectors, draft_arms=True)
    _TARGET_EDIT = _VecGridEdit(
        group="targets",
        count=lambda: len(editor.target_override or service.target_interval_set(
            editor.target_spec, editor.state.domain_basis)),
        cell_id=ids.target_cell,
        pending=lambda: editor.pending_target, set_pending=editor.set_pending_target,
        commit=editor.set_target_override_vectors, draft_arms=True)


    def on_mapping_change(preview=False):
        _edit_vector_grid(_MAPPING_EDIT, preview)

    def on_form_change(preview=False):
        if building[0] or not editor.settings.get("form_tiles"):
            return
        r = len(editor.state.mapping)
        rc = len(service.canonical_mapping(editor.state.mapping))
        if any(ids.form_cell(i, j) not in rec.inputs for i in range(r) for j in range(rc)):
            if preview:
                _edit_candidate(None)
            return
        rows = [[_parse_int(rec.inputs[ids.form_cell(i, j)].value) for j in range(rc)] for i in range(r)]
        if any(v is None for row in rows for v in row):
            if preview:
                _edit_candidate(None)
            return
        if service.mapping_from_form_matrix(editor.state.mapping, rows) is None:
            if preview:
                _edit_candidate(None)
                return
            ui.notify(_INVALID_FORM, type="negative", position="top")
            render()
            return
        if preview:
            _edit_candidate(lambda: editor.edit_form_matrix(rows))
            return
        editor.edit_form_matrix(rows)
        _request_render()  # a form change re-stores the mapping (a new generating set) — render off the loop

    def on_comma_change(preview=False):
        _edit_vector_grid(_COMMA_EDIT, preview)

    def on_unchanged_change(preview=False):
        if building[0]:
            return
        d, r = editor.state.d, editor.state.r
        if any(ids.unchanged_cell(j, p) not in rec.inputs for j in range(r) for p in range(d)):
            if preview:
                _edit_candidate(None)
            return
        vectors = [[_parse_int(rec.inputs[ids.unchanged_cell(j, p)].value) for p in range(d)] for j in range(r)]
        if any(v is None for vec in vectors for v in vec):
            if preview:
                _edit_candidate(None)
                return
            ui.notify(_INVALID_UNCHANGED, type="negative", position="top")
            render()
            return
        try:
            ratios = service.comma_ratios(tuple(tuple(v) for v in vectors), editor.state.domain_basis)
        except (ValueError, ZeroDivisionError, ArithmeticError):
            if preview:
                _edit_candidate(None)
                return
            ui.notify(_INVALID_UNCHANGED, type="negative", position="top")
            render()
            return
        if preview:
            _edit_candidate(lambda: editor.set_unchanged_basis(ratios))
            return
        editor.set_unchanged_basis(ratios)
        _request_render()

    def on_interest_change(preview=False):
        _edit_vector_grid(_INTEREST_EDIT, preview)

    def on_held_change(preview=False):
        _edit_vector_grid(_HELD_EDIT, preview)

    def on_target_cells_change(preview=False):
        _edit_vector_grid(_TARGET_EDIT, preview)

    def on_ratio_change(cid):
        if building[0] or cid not in rec.inputs:
            return
        group, tok = cid.split(":")
        raw = rec.cell_value(cid)
        if raw in ("", "?/?"):
            render()
            return
        try:
            vector = service.interval_vector(raw, editor.state.d, editor.state.domain_basis)
        except ValueError as exc:
            ui.notify(str(exc), type="negative", position="top")
            render()
            return

        def replace(current, setter):
            list_name = {"target": "targets", "held": "held", "interest": "interest",
                         "comma": "commas"}.get(group)
            toks = col_tokens(list_name) if list_name else []
            pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
            vectors = [list(v) for v in current]
            if vectors[pos] != list(vector):
                vectors[pos] = vector
                setter(vectors)

        if tok == "pending":
            {"comma": editor.set_pending_comma, "interest": editor.set_pending_interest,
             "held": editor.set_pending_held, "target": editor.set_pending_target}[group](vector)
        elif group == "comma":
            replace(editor.state.comma_basis, editor.edit_comma_basis)
        elif group == "interest":
            replace(editor.interest_vectors, editor.set_interest_vectors)
        elif group == "held":
            replace(editor.held_vectors, editor.set_held_vectors)
        elif group == "unchanged":
            ratios = [rec.cell_value(f"unchanged:{j}") for j in range(editor.state.r)
                      if f"unchanged:{j}" in rec.inputs]
            if len(ratios) == editor.state.r and all(ratios):
                editor.set_unchanged_basis(tuple(ratios))
        else:
            targets = editor.target_override or service.target_interval_set(
                editor.target_spec, editor.state.domain_basis)
            replace(service.target_interval_vectors(targets, editor.state.d, editor.state.domain_basis),
                    editor.set_target_override_vectors)
        # a quantities-row ratio edit routes into a retuning setter (comma/held/target/unchanged) —
        # render off the loop. (An interest edit doesn't retune, but the warm build is cheap.)
        _request_render()

    def transform_interval(cid, op):
        # the equave-reduce / reciprocate buttons flanking an editable interval ratio (commas / targets
        # / held / interest) or an editable domain basis element (prime). Resolve the cell's value,
        # apply the op, and route it through the SAME setter a manual edit uses — one undo step, every
        # dependent row recomputed. A no-op (already reduced, or a unison reciprocated) commits nothing,
        # so a disabled button is safe.
        if building[0] or cid not in rec.inputs:
            return
        group, tok = cid.split(":")
        if group not in ("comma", "target", "held", "interest", "prime") or tok == "pending":
            return
        _end_commit_gestures()
        if group == "prime":  # relabel a domain basis element to its reduced / reciprocated ratio
            new_raw = service.transform_ratio(rec.cell_value(cid), op, editor.state.domain_basis)
            if new_raw is None:
                return  # no-op / unparseable
            index = int(tok)
            parsed = service.parse_domain_element(new_raw)
            if parsed is None:
                ui.notify(f"“{new_raw}” is not a valid basis element (≠ 1)", type="negative", position="top")
                render()
                return
            if not service.can_set_domain_element(editor.state, index, parsed):
                ui.notify(f"{new_raw} would make the basis dependent", type="negative", position="top")
                render()
                return
            editor.set_domain_element(index, new_raw)
            _request_render()
            return
        if group == "comma":
            current, setter, list_name = editor.state.comma_basis, editor.edit_comma_basis, "commas"
        elif group == "target":
            targets = editor.target_override or service.target_interval_set(
                editor.target_spec, editor.state.domain_basis)
            current = service.target_interval_vectors(targets, editor.state.d, editor.state.domain_basis)
            setter, list_name = editor.set_target_override_vectors, "targets"
        elif group == "held":
            current, setter, list_name = editor.held_vectors, editor.set_held_vectors, "held"
        else:
            current, setter, list_name = editor.interest_vectors, editor.set_interest_vectors, "interest"
        toks = col_tokens(list_name)
        pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
        if not 0 <= pos < len(current):
            return
        v = tuple(int(x) for x in current[pos])
        if op == "reciprocate":
            new_v = tuple(-x for x in v)
        else:
            new_v = tuple(int(x) for x in service.equave_reduce_vector(v, editor.state.domain_basis))
        if list(new_v) == list(v):
            return
        vectors = [list(x) for x in current]
        vectors[pos] = list(new_v)
        setter(vectors)
        _request_render()

    def on_element_change(cid):
        if building[0] or cid not in rec.inputs:
            return
        raw = rec.cell_value(cid)
        tok = cid.split(":")[1]
        if raw in ("", "?/?"):
            render()
            return
        parsed = service.parse_domain_element(raw)
        if parsed is None:
            ui.notify(f"“{raw}” is not a positive rational basis element (≠ 1)",
                      type="negative", position="top")
            render()
            return
        if tok == "pending":
            if not service.can_add_domain_element(editor.state, parsed):
                ui.notify(f"{raw} isn’t independent of the existing basis", type="negative", position="top")
                render()
                return
            editor.set_pending_element(raw)
            _request_render()  # a new domain element retunes — render off the loop
            return
        index = int(tok)
        if parsed == editor.state.domain_basis[index]:
            return
        if not service.can_set_domain_element(editor.state, index, parsed):
            ui.notify(f"{raw} would make the basis dependent", type="negative", position="top")
            render()
            return
        editor.set_domain_element(index, raw)
        _request_render()  # relabelling a domain element retunes — render off the loop

    def on_element_preview(cid):
        g = rec.gesture
        if building[0] or g is None or g.kind != "edit" or g.source != cid or cid not in rec.inputs:
            return
        raw = rec.cell_value(cid)
        tok = cid.split(":")[1]
        parsed = service.parse_domain_element(raw) if raw not in ("", "?/?") else None
        if tok == "pending":
            valid = parsed is not None and service.can_add_domain_element(editor.state, parsed)
        else:
            valid = (parsed is not None and parsed != editor.state.domain_basis[int(tok)]
                     and service.can_set_domain_element(editor.state, int(tok), parsed))
        if not valid:
            _edit_candidate(None)
        elif tok == "pending":
            _edit_candidate(lambda: editor.set_pending_element(raw))
        else:
            _edit_candidate(lambda: editor.set_domain_element(int(tok), raw))

    def on_power_change(cid):
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
                return
            if not math.isfinite(power) or power <= 0:
                return
        if cid == "control:q":
            if power < 1:
                return
            editor.set_complexity_norm_power(power)
        else:
            editor.set_optimization_power(power)
        _request_render()  # a new optimization / complexity power retunes — render off the loop

    def _gen_position(tok):
        toks = col_tokens("gens")
        return toks.index(tok) if tok in toks else tok

    def on_gentuning_change(cid):
        if building[0] or cid not in rec.inputs:
            return
        mag = rec.decimal_value(cid)
        if not mag:
            return
        try:
            cents = abs(float(mag))
        except ValueError:
            return
        glyph = rec.gensign_faces.get(cid)
        if glyph is not None and glyph.text not in ("+", ""):
            cents = -cents
        i = int(cid.rsplit(":", 1)[1])
        if ":ssgen:" in cid:
            editor.set_superspace_generator_tuning_component(i, cents)
        else:
            editor.set_generator_tuning_component(_gen_position(i), cents)
        _request_render()  # a manual generator override re-derives the maps — render off the loop

    def on_gentuning_wheel(cid, delta_y):
        if building[0] or not delta_y:
            return
        i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
        if ":ssgen:" in cid:
            editor.nudge_superspace_generator_tuning_component(i, steps)
        else:
            editor.nudge_generator_tuning_component(_gen_position(i), steps)
        # off the loop — rapid notches coalesce into one trailing rebuild at the value you land on
        _request_render()

    def on_value_wheel(cid, delta_y):
        if building[0] or not delta_y or cid not in rec.inputs:
            return
        step = _WHEEL_STEPS.get(rec.kinds.get(cid))
        if step is None:
            return
        if cid in rec.den_inputs:
            building[0] = True
            rec.set_decimal_value(cid, _wheel_step(rec.decimal_value(cid), delta_y, step))
            building[0] = False
            on_prescaler_change(cid)
            return
        rec.inputs[cid].value = _wheel_step(rec.inputs[cid].value, delta_y, step)
        commit = {"mapping": on_mapping_change, "commacell": on_comma_change,
                  "interestcell": on_interest_change, "heldcell": on_held_change,
                  "targetcell": on_target_cells_change, "formcell": on_form_change}.get(rec.kinds.get(cid))
        if commit is not None:
            commit()

    def on_target_limit_wheel(delta_y):
        # step the TILT/OLD limit by ±1 per wheel notch. Unlike a matrix/vector cell, COMMITTING a
        # new limit rebuilds the whole target interval set, re-solves the tuning and re-renders the
        # grid — far too heavy to run on every notch. A fast scroll would queue one such solve per
        # notch, each costlier than the last as the set grows, and grind the app to a halt. So step
        # the shown number now (under the build guard, so the field's own on_target_change echo is a
        # no-op — handle_event runs it inline) and DEBOUNCE the commit: the value is server-side, so
        # the loopback-controlled field actually advances, while a re-armed task collapses the whole
        # gesture into ONE solve at the limit you land on. Focus-gated client-side (see _INT_WHEEL_JS).
        if building[0] or not delta_y:
            return
        num = rec.selects["preset:target"][0]
        building[0] = True
        num.value = _wheel_step(num.value, delta_y)
        building[0] = False
        on_target_limit_preview()
        if target_limit_commit[0] is not None:
            target_limit_commit[0].cancel()
        target_limit_commit[0] = background_tasks.create(
            _debounced_target_commit(), name="target-limit-commit")

    async def _debounced_target_commit():
        # the tail of a target-limit wheel gesture: once the notches stop for _TARGET_LIMIT_DEBOUNCE,
        # commit the number now in the field with the one real solve + render. A new notch cancels
        # this and arms a fresh one. The debounce collapses the whole gesture into one commit, so an
        # even odd-limit (OLD) you land on toasts once here (not once per notch) and the render reddens it.
        # We run off the loop (a background task), where the slot stack is empty — so enter the captured
        # page client's context, or on_target_change's ui.notify can't resolve the client and the toast
        # silently vanishes (render reaches its client the same captured-client way, see page_client above).
        try:
            await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
        except asyncio.CancelledError:
            return
        target_limit_commit[0] = None
        with page_client:
            on_target_change()

    def on_target_limit_preview(typed=None):
        # live edit preview for the TILT/OLD limit field, mirroring on_element_preview: as the shown
        # limit changes (a wheel notch steps it, a keystroke types it) but BEFORE the debounced commit
        # reflows the grid, the candidate rings the target interval cells the new limit would MOVE
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
            _edit_candidate(None)
            return
        text = (str(raw) if raw is not None else "").strip()
        spec = f"{int(float(text))}-{family}" if text else family
        try:
            valid = bool(service.target_interval_set(spec, editor.state.domain_basis))
        except Exception as exc:
            _log.debug("target spec %r rejected: %r", spec, exc)
            valid = False
        if not valid:
            _edit_candidate(None)
            return
        _edit_candidate(lambda: editor.set_target_spec(spec))

    def on_prescaler_change(cid):
        if building[0] or cid not in rec.inputs:
            return
        raw = rec.decimal_value(cid)
        if not raw:
            return
        try:
            value = float(raw)
        except ValueError:
            return
        parts = cid.split(":")
        i, j = int(parts[3]), int(parts[4])
        if not math.isfinite(value) or (i == j and value <= 0):
            ui.notify(_INVALID_PRESCALER, type="negative", position="top")
            render()
            return
        editor.set_custom_prescaler_entry(i, j, value)
        _request_render()  # the prescaler drives the weighted tuning solve — render off the loop

    def on_weight_change(cid):
        if building[0] or cid not in rec.inputs:
            return
        weights = []
        for other in rec.inputs:
            if not other.startswith("weight:"):
                continue
            raw = rec.decimal_value(other)
            if not raw:
                return
            try:
                w = float(raw)
            except ValueError:
                return
            if not math.isfinite(w) or w <= 0:
                ui.notify(_INVALID_WEIGHT, type="negative", position="top")
                render()
                return
            weights.append(w)
        editor.set_custom_weights(weights)
        _request_render()  # the weights drive the tuning solve — render off the loop

    def on_ptext_edit(cid, value):
        if building[0]:
            return
        if not editor.settings.get("ebk", True):
            value = service.simple_matrix_to_ebk(value, _PTEXT_DUAL_VECTOR_KIND.get(cid, False))
        if cid == "ptext:mapping:primes":
            ok = editor.try_edit_mapping_text(value)
        elif cid == "ptext:mapping:canongens":
            ok = editor.try_edit_form_matrix_text(value)
        elif cid == "ptext:vectors:commas":
            ok = editor.try_edit_comma_basis_text(value)
        elif cid == "ptext:tuning:gens":
            ok = editor.set_generator_tuning_text(value)
        elif cid == "ptext:tuning:ssgens":
            ok = editor.set_superspace_generator_tuning_text(value)
        elif cid == "ptext:vectors:targets":
            ok = editor.set_target_override_text(value)
        elif cid == "ptext:prescaling:primes":
            ok = editor.set_custom_prescaler_text(value)
        elif cid == "ptext:projection:primes":
            ok = editor.try_edit_projection_text(value)
        elif cid == "ptext:projection:gens":
            ok = editor.try_edit_embedding_text(value)
        else:
            return
        if ok:
            rec.ptext_inputs[cid].classes(remove="rtt-ptext-error")
            _request_render()  # a typed dual (mapping/commas/tuning/targets/P/G…) retunes — off the loop
        else:
            rec.ptext_inputs[cid].classes(add="rtt-ptext-error")
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
                toast = _INVALID_PROJECTION
            elif cid == "ptext:projection:gens" and \
                    service.parse_embedding(value, editor.state.d, len(editor.state.mapping)) is not None:
                toast = _INVALID_EMBEDDING
            if toast:
                ui.notify(toast, type="negative", position="top")

    def _end_commit_gestures():
        # a commit ends any hover-family gesture FIRST — its rings are previews of a click that
        # has now landed (or been superseded), and a token gesture must restore the real document
        # before the action mutates it (e.g. Ctrl+Z while a temperament hover holds a hypothetical
        # doc). The edit/wheel gestures survive their own commits and end on blur/mouseleave.
        if rec.gesture is not None and rec.gesture.kind in ("hover", "chooser", "temp", "drag"):
            end_gesture()
        rank_remove[0] = None

    def act(action):
        # the universal click/keyboard commit: end gestures, mutate, then render OFF the loop
        # (_request_render) — most of these actions retune (expand/shrink, undo/redo across an
        # edit, a structural remove, back-to-scheme), so the heavy solve must not block the socket.
        _end_commit_gestures()
        action()
        _request_render()

    draft_focus = {
        "comma":    ("comma:pending",    "commacell"),
        "target":   ("target:pending",   "targetcell"),
        "held":     ("held:pending",     "heldcell"),
        "interest": ("interest:pending", "interestcell"),
        "element":  ("prime:pending",    None),
        "mapping":  (None,               "mapping"),
    }

    def add_interval(action, group):
        # add the draft column, then focus into it: the quantities ratio cell if its row is shown
        # (the layout emitted it), else the first gridded vector cell (prime 0) of the draft column.
        # A draft add doesn't retune (the pending green vector isn't committed), so its build is
        # light — render SYNCHRONOUSLY (not the off-loop _request_render) so last_lay is current for
        # the focus hand-off below, which reads the just-built layout.
        _end_commit_gestures()
        action()
        render()
        quant_id, vec_kind = draft_focus[group]
        lay = last_lay[0]
        if any(cb.id == quant_id for cb in lay.cells):
            target = quant_id
        elif vec_kind is not None:
            target = next((cb.id for cb in lay.cells
                           if cb.pending and cb.prime == 0 and cb.kind == vec_kind), None)
        else:
            target = None
        if target is None and group == "element":
            target = next((cb.id for cb in lay.cells if cb.id == "basis:pending"), None)
        inp = rec.inputs.get(target) if target is not None else None
        if inp is not None:
            # Focus into the freshly-created draft cell AND select its contents, so the "?" placeholder
            # the draft starts with is highlighted — the first keystroke replaces it instead of typing
            # after it (no backspace needed). select() resolves through getElement().$refs.qRef to
            # QInput.select() (a native input.select()); it is a harmless no-op on the empty
            # integer-vector fallback cell. A direct runMethod can lose a race in a real (visible)
            # browser: the cell-create 'update' and this focus message can be delivered in one frame,
            # so the focus runs before Vue has mounted the new cell and populated its $ref — and
            # silently no-ops. So defer to the next macrotask and poll briefly for the mount (getElement
            # returns the ref once it exists). setTimeout works whether the page is visible or hidden —
            # requestAnimationFrame would be paused while hidden (e.g. the render tests / a backgrounded
            # tab), so it is the wrong tool here.
            # The draft cell can be off-screen — a + at a far edge, or an add fired by keyboard while
            # scrolled away. So after focusing, scroll the grid body the minimum that brings the cell
            # fully into view (past the frozen left rowband, clear of the top edge). Setting scrollLeft/
            # Top fires the body's own scroll listener, which re-pins the frozen header (see freeze.js).
            ui.run_javascript(
                f"(function(){{var id={inp.id},n=0;function go(){{var c=getElement(id);"
                f"if(c){{runMethod(id,'focus',[]);runMethod(id,'select',[]);"
                f"var el=document.activeElement,cell=el&&el.closest&&el.closest('.rtt-cell'),"
                f"body=cell&&cell.closest('.rtt-gridbody');"
                f"if(body){{var cr=cell.getBoundingClientRect(),br=body.getBoundingClientRect(),"
                f"band=body.querySelector('.rtt-rowband'),bw=band?band.getBoundingClientRect().width:0,pl=24,pt=8;"
                f"if(cr.left<br.left+bw+pl)body.scrollLeft-=br.left+bw+pl-cr.left;"
                f"else if(cr.right>br.right-pl)body.scrollLeft+=cr.right-br.right+pl;"
                f"if(cr.top<br.top+pt)body.scrollTop-=br.top+pt-cr.top;"
                f"else if(cr.bottom>br.bottom-pt)body.scrollTop+=cr.bottom-br.bottom+pt;}}return;}}"
                f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()")

    def on_show_toggle(key, value):
        if building[0]:
            return
        if key == "nonstandard_domain" and not value and editor.basis_is_nonstandard:
            editor.exit_nonstandard_domain()
            render()
            return
        editor.set_show(key, value)
        render()

    def on_select_all(value):
        if building[0]:
            return
        editor.set_all_show(value, _available_keys())
        render()

    def on_part_click(key):
        if building[0]:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not editor.settings[host]:
            return
        editor.set_show(key, not editor.settings[key])
        render()

    def on_preset(cid, value):
        if building[0]:
            return
        if cid.startswith("preset:temperament"):
            if value in presets.TEMPERAMENT_COMMAS:
                end_gesture()
                editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
                _request_render()  # a loaded temperament retunes — render off the loop
            else:
                render()
            return
        apply = _candidate_apply(cid, value)
        if apply is not None:
            end_chooser_gesture()
            apply()
            _request_render()  # a tuning / prescaler preset re-solves — render off the loop

    def on_subpick(cid, value):
        if building[0] or value is None:
            return
        end_gesture()
        db = editor.state.domain_basis
        if cid == "etpick:draft":
            editor.set_pending_mapping_row(list(presets.et_value_to_val(value, db)))
            ok = editor.pending_mapping_row is None
        elif cid == "commapick:draft":
            editor.set_pending_comma(list(presets.comma_value_to_vector(value, db)))
            ok = editor.pending_comma is None
        elif cid.startswith("etpick:"):
            i = _token_index(cid, "gens")
            ok = i is not None and editor.set_mapping_row(i, presets.et_value_to_val(value, db))
        else:
            c = _token_index(cid, "commas")
            ok = c is not None and editor.set_comma(c, presets.comma_value_to_vector(value, db))
        if not ok:
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
        render()

    def on_form_choose(cid, value):
        if building[0]:
            return
        apply = _candidate_apply(cid, value)
        if apply is not None:
            end_chooser_gesture()
            apply()
            _request_render()  # canonicalizing re-keys the tuning solve — render off the loop

    def on_target_change():
        if building[0]:
            return
        end_chooser_gesture()
        num, sel = rec.selects["preset:target"]
        family = sel.value or "TILT"
        problem = service.target_limit_problem(family, num.value)
        if problem == "whole":
            # a non-number is never accepted: toast and re-render, which restores the committed
            # value (the input is loopback-controlled, so the server's value overwrites the garbage)
            ui.notify(tooltips.target_limit_help("whole"), type="negative", position="top")
            render()
            return
        text = (num.value or "").strip()
        spec = f"{int(float(text))}-{family}" if text else family
        try:
            valid = bool(service.target_interval_set(spec, editor.state.domain_basis))
        except Exception as exc:
            _log.debug("target spec %r rejected: %r", spec, exc)
            valid = False
        if not valid:
            return
        if problem == "odd":
            ui.notify(tooltips.target_limit_help("odd"), type="negative", position="top")
        editor.set_target_spec(spec)
        _request_render()  # a new target set re-weights the optimization (retunes) — render off the loop

    def on_control_select(cid, value):
        if building[0] or value is None:
            return
        apply = _candidate_apply(cid, value)
        if apply is not None:
            end_chooser_gesture()
            apply()
        elif cid == "control:diminuator":
            editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":
            editor.set_all_interval(bool(value))
        else:
            return
        _request_render()  # a weighting / complexity / all-interval trait change retunes — off the loop

    def on_range_mode(value):
        if building[0] or value is None:
            return
        editor.set_range_mode(value)
        render()

    def on_toggle(item):
        editor.toggle_collapsed(item)
        render()

    def on_toggle_all():
        editor.set_collapsed(spreadsheet.toggle_all_collapsed(last_lay[0], editor.collapsed))
        render()

    def on_cell_focus(cid):
        take_over_gesture()
        rec.gesture = _Gesture(kind="edit", source=cid, baseline=last_lay[0])

    def on_cell_blur(cid=None):
        g = rec.gesture
        if g is not None and g.kind in ("edit", "wheel") and (cid is None or g.source == cid):
            end_gesture()
            paint_rings()

    def combine_begin():
        end_gesture()
        rec.gesture = _Gesture(kind="drag", token=editor.capture_for_preview(),
                               baseline=last_lay[0])

    def combine_preview(apply, target_pred=None):
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        editor.restore_for_preview(g.token)
        g.target_pred = target_pred if apply is not None else None
        if apply is not None:
            apply()
        gesture_render()

    def combine_commit(apply):
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        end_gesture()
        act(apply)

    def combine_end():
        g = rec.gesture
        if g is None or g.kind != "drag":
            return
        end_gesture()
        render()

    def control_hover(apply):
        if not editor.settings["preview_highlighting"]:
            return
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        prev = None
        if g is not None and g.kind == "wheel":
            prev = g
        elif g is not None:
            take_over_gesture()
        rec.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        paint_rings()

    def control_unhover():
        g = rec.gesture
        if g is None or g.kind != "hover":
            return
        rec.gesture = g.prev
        paint_rings()

    def rank_remove_hover(axis, idx):
        if not editor.settings["preview_highlighting"]:
            return
        if rec.gesture is not None and rec.gesture.kind in ("edit", "drag"):
            return
        rank_remove[0] = (axis, idx)
        rank_rendering[0] = True
        try:
            render()
        finally:
            rank_rendering[0] = False

    def rank_remove_unhover():
        if rank_remove[0] is not None:
            rank_remove[0] = None
            render()

    def _cell_xy(lay, eid):
        for c in lay.cells:
            if c.id == eid:
                return (round(c.x), round(c.y))
        return None

    def chooser_hover(cid, apply):
        if not editor.settings["preview_highlighting"]:
            return
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        if g is not None and (g.kind != "chooser" or g.source != cid):
            take_over_gesture()
        if rec.gesture is None:
            rec.gesture = _Gesture(kind="chooser", source=cid,
                                   token=editor.capture_for_preview(), baseline=last_lay[0])
        g = rec.gesture
        editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            gesture_render()
        if apply is None:
            g.apply = None
            paint_rings()
            return
        base = g.baseline
        apply()
        hyp = editor.layout(prev_ids=base.identities if base is not None else None)
        disturbs = base is not None and (
            spreadsheet.removed_cell_ids(base, hyp) or _cell_xy(base, cid) != _cell_xy(hyp, cid))
        if disturbs:
            editor.restore_for_preview(g.token)
            g.apply = apply
            paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            gesture_render()

    def chooser_unhover():
        g = rec.gesture
        if g is None or g.kind != "chooser":
            return
        was = end_gesture()
        if was is not None and was.reflowed:
            render()
        else:
            paint_rings()

    def _end_temperament_preview():
        g = rec.gesture
        if g is None or g.kind != "temp":
            return
        was = end_gesture()
        if was.reflowed:
            render()
        else:
            paint_rings()

    def _temperament_hover_preview(key):
        if key not in presets.TEMPERAMENT_COMMAS:
            _end_temperament_preview()
            return
        g = rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return
            end_gesture()
            g = rec.gesture = _Gesture(kind="temp", token=editor.capture_for_preview(),
                                       baseline=last_lay[0])
        editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            gesture_render()
        base = editor.state
        editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        hyp = editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            editor.restore_for_preview(g.token)
            g.apply = lambda: editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
            paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            gesture_render()

    def _subpick_hover_preview(cid, value):
        if value is None:
            _end_temperament_preview()
            return
        db = editor.state.domain_basis
        draft = cid in ("etpick:draft", "commapick:draft")
        idx = None
        if not draft:
            idx = _token_index(cid, "gens" if cid.startswith("etpick:") else "commas")
            if idx is None:
                _end_temperament_preview()
                return
        g = rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return
            end_gesture()
            g = rec.gesture = _Gesture(kind="temp", token=editor.capture_for_preview(),
                                       baseline=last_lay[0])
        editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            gesture_render()
        if draft:
            if cid == "etpick:draft":
                editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
            else:
                editor.pending_comma = list(presets.comma_value_to_vector(value, db))
            g.apply = None
            g.reflowed = True
            gesture_render()
            return
        if cid.startswith("etpick:"):
            apply = lambda i=idx, v=value: editor.set_mapping_row(i, presets.et_value_to_val(v, db))
        else:
            apply = lambda c=idx, v=value: editor.set_comma(c, presets.comma_value_to_vector(v, db))
        base = editor.state
        apply()
        hyp = editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            editor.restore_for_preview(g.token)
            g.apply = apply
            paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            gesture_render()

    def _candidate_apply(cid, value):
        if value is None:
            return None
        if cid.startswith("preset:tuning"):
            return lambda: editor.set_tuning_scheme(value)
        if cid.startswith("preset:prescaler"):
            return lambda: editor.set_complexity_prescaler(value)
        if cid.startswith("preset:projection"):
            return lambda: editor.set_established_projection(value)
        if cid == "control:complexity":
            if value == "custom":
                return None
            internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
            return lambda: editor.set_complexity_name(internal)
        if cid == "control:slope":
            return lambda: editor.set_weight_slope(value)
        if cid.startswith("formchooser:"):
            name = cid.split(":", 1)[1]
            if name == "mapping":
                if value not in service.MAPPING_FORM_KEYS:
                    return None
                return lambda: editor.set_mapping_form(value)
            if value not in service.COMMA_BASIS_FORM_KEYS:
                return None
            return lambda: editor.set_comma_basis_form(value)
        return None

    def on_chooser_hover(cid, detail):
        # the shared option-hover preview entry for every q-select armed via _arm_option_hover: the
        # delegation fires `opthover` at the chooser's cell wrap carrying the hovered option's positional
        # index in `detail` (-1 / None on leave). Map it back to the option's key through the live
        # select, then preview applying it. Temperament + the sub-pickers route to their own sticky
        # reflow path; the rest (including the TILT/OLD family) go through chooser_hover below, which
        # reflows a value-only pick and reddens one that would remove cells.
        entry = rec.selects.get(cid)
        sel = entry[1] if isinstance(entry, tuple) else entry
        if not isinstance(sel, ui.select):
            return
        index = _hover_index(detail)
        if index is not None and rec.popup_state.get(cid) == "closed":
            return
        if cid.startswith(("etpick:", "commapick:")):
            _subpick_hover_preview(cid, _option_key(sel, index) if index is not None else None)
            return
        if cid.startswith("preset:temperament"):
            _temperament_hover_preview(_option_key(sel, index))
            return
        if index is None or not sel.enabled:
            chooser_unhover()
            return
        if cid == "preset:target":
            family = _option_key(sel, index)
            if family not in presets.TARGET_SETS:
                chooser_unhover()
                return
            text = (entry[0].value or "").strip()
            try:
                spec = f"{int(float(text))}-{family}" if text else family
            except ValueError:
                spec = family
            chooser_hover(cid, lambda: editor.set_target_spec(spec))
            return
        apply = _candidate_apply(cid, _option_key(sel, index))
        if apply is None:
            chooser_unhover()
            return
        chooser_hover(cid, apply)

    def on_popup(cid, is_open):
        # a chooser's Quasar popup opened/closed: feed the server-side gate (see on_chooser_hover)
        # and treat the close as the gesture's leave — the option the pointer was on is gone, so a
        # live chooser/temperament preview ends (ungated; only positive arms are gated).
        rec.popup_state[cid] = "open" if is_open else "closed"
        if not is_open:
            on_chooser_hover(cid, None)

    def gentuning_hover(cid):
        g = rec.gesture
        if g is not None and g.kind in ("edit", "drag", "hover"):
            return
        take_over_gesture()
        rec.gesture = _Gesture(kind="wheel", source=cid, baseline=last_lay[0])

    def gentuning_unhover(cid):
        g = rec.gesture
        if g is None or g.kind != "wheel" or g.source != cid:
            return
        end_gesture()
        paint_rings()

    drag_src = [None]
    reorder_dst = [None]

    def on_drag_start(lst, idx):
        drag_src[0] = (lst, idx)
        reorder_dst[0] = (lst, idx)
        end_gesture()
        rec.gesture = _Gesture(kind="drag", token=editor.capture_for_preview(),
                               baseline=last_lay[0])

    def on_drag_enter(dst_list, dst_idx):
        g = rec.gesture
        if g is None or g.kind != "drag" or drag_src[0] is None or (dst_list, dst_idx) == reorder_dst[0]:
            return
        reorder_dst[0] = (dst_list, dst_idx)
        editor.restore_for_preview(g.token)
        idx = dst_idx if dst_idx is not None else (1 << 30)
        editor.move_interval(drag_src[0][0], drag_src[0][1], dst_list, idx)
        gesture_render()

    def on_drag_end():
        if rec.gesture is not None and rec.gesture.kind == "drag":
            end_gesture()
            render()
        drag_src[0] = None
        reorder_dst[0] = None

    def on_drop(dst_list, dst_idx):
        src = drag_src[0]
        drag_src[0] = None
        reorder_dst[0] = None
        had_preview = rec.gesture is not None and rec.gesture.kind == "drag"
        if had_preview:
            end_gesture()
        if not src:
            if had_preview:
                render()
            return
        idx = dst_idx if dst_idx is not None else (1 << 30)
        if editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
            render()
    rec._cb = SimpleNamespace(
        act=act,
        add_interval=add_interval,
        combine_begin=combine_begin,
        combine_preview=combine_preview,
        combine_commit=combine_commit,
        combine_end=combine_end,
        control_hover=control_hover,
        control_unhover=control_unhover,
        rank_remove_hover=rank_remove_hover,
        rank_remove_unhover=rank_remove_unhover,
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
        on_form_change=on_form_change,
        on_power_change=on_power_change,
        on_prescaler_change=on_prescaler_change,
        on_weight_change=on_weight_change,
        on_preset=on_preset,
        on_subpick=on_subpick,
        on_ptext_edit=on_ptext_edit,
        on_ratio_change=on_ratio_change,
        transform_interval=transform_interval,
        on_element_change=on_element_change,
        on_element_preview=on_element_preview,
        on_range_mode=on_range_mode,
        on_target_cells_change=on_target_cells_change,
        on_target_change=on_target_change,
        on_toggle=on_toggle,
        on_toggle_all=on_toggle_all,
    )

    # ---- off-loop commit render + busy scrim ----------------------------------------------------
    # A state change that retunes (raising the prime limit, adding/editing a comma or held interval,
    # picking a scheme, undo/redo across such an edit…) re-solves the tuning. At a high prime limit
    # that solve takes a few SECONDS, and run inline on the event loop it would block NiceGUI's
    # websocket heartbeat — the client misses its ping, drops the socket ("lost connection"), and the
    # page looks crashed until a hard reload. So the retuning paths render through _request_render
    # instead of calling render() directly: the heavy solve runs in a worker thread (numpy/scipy
    # release the GIL, so the loop keeps answering pings), warming the tuning memo; render() then
    # rebuilds on the loop from that warm cache (fast).
    #
    # The "Computing…" busy scrim is driven CLIENT-side (see _BUSY_JS), not from here: the moment a
    # committing control is used the browser arms the scrim and reveals it if the work outlasts a
    # short delay — so it appears even while the server's loop is busy (a *synchronous* re-render,
    # e.g. a Show toggle, can't send a "show scrim" message until it has already finished) and while
    # the browser is busy patching a big grid. render() ends by calling rttBusy.done() to clear it.
    render_inflight = [False]
    render_again = [False]
    render_after = [None]

    def _request_render(after=None):
        # schedule an off-loop commit render; a request arriving while one is in flight collapses
        # into a single trailing rebuild (the state it lands on is the only one that matters).
        # ``after`` runs on the loop once render() has rebuilt — for the few commits with a
        # synchronous tail that reads the fresh layout (a draft column materializing then rebasing
        # its edit gesture off last_lay).
        if helpers.is_user_simulation():
            # the in-process User test harness drives clicks/edits and inspects the DOM right after,
            # with no chance for a background task to run — and there is no real socket to protect.
            # Render synchronously there: tests see the same immediate rebuild they always did, and
            # the off-loop machinery (a production websocket concern) is exercised by the live probe.
            render()
            if after is not None:
                after()
            return
        if render_inflight[0]:
            render_again[0] = True
            render_after[0] = after
            return
        background_tasks.create(_commit_render(after))

    async def _commit_render(after=None):
        render_inflight[0] = True
        try:
            again = True
            cont = after
            while again:
                prev = last_lay[0].identities if last_lay[0] is not None else None
                try:
                    # warm the tuning memo off the loop; the result is discarded — render() below
                    # recomputes the layout, now a cache hit. (editor.layout is read-only, and the
                    # mutation that triggered this already ran synchronously in the handler.)
                    await asyncio.to_thread(editor.layout, prev_ids=prev)
                except Exception:
                    _log.exception("off-loop layout warm-up failed; rendering on the loop")
                render()
                if cont is not None:
                    cont()
                again = render_again[0]
                render_again[0] = False
                cont = render_after[0]
                render_after[0] = None
        finally:
            render_inflight[0] = False


    def apply_view_classes():
        # Two of the `interface` Show behaviours gate the whole app through a single <body> class each,
        # so one CSS rule (assets/rtt.css) handles every element: `animations` off adds rtt-no-anim
        # (which zeroes the --t transition var, so every change snaps instead of sliding/fading) and
        # `tooltips` off adds rtt-no-tooltips (which hides every .q-tooltip). Unlike dark mode these
        # live in editor.settings — toggled in the Show panel, so select-all / Reset reach them — so
        # render() re-applies them after any toggle (and on the initial build, before cells animate in).
        # The third behaviour, preview_highlighting, has no body class: it's gated in Python at the
        # preview source (compute_rings + the hover handlers) so no ring or reflow is even produced.
        # render() can run OFF the loop (the _commit_render background task — every act()-driven commit:
        # reset, undo/redo, a structural edit), where the slot stack is empty and ui.query would raise
        # "slot stack ... is empty", aborting the whole render (grid never updates, busy scrim never
        # clears). Enter the captured page client so the <body> query resolves; in the synchronous /
        # test path this just nests harmlessly inside the already-live slot.
        with page_client:
            body = ui.query("body")
            body.classes(add="rtt-no-anim") if not editor.settings["animations"] \
                else body.classes(remove="rtt-no-anim")
            body.classes(add="rtt-no-tooltips") if not editor.settings["tooltips"] \
                else body.classes(remove="rtt-no-tooltips")

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
        if not rank_rendering[0]:
            rank_remove[0] = None
        building[0] = True
        try:
            apply_view_classes()
            st = editor.state
            prev = last_lay[0].identities if last_lay[0] is not None else None
            lay = editor.layout(prev_ids=prev, preview_remove=rank_remove[0])
            last_lay[0] = lay
            fx, fy = lay.freeze_x, lay.freeze_y
            base_w = lay.width + lay.right_overhang + 2 * _PAD
            base_h = lay.height + 2 * _PAD
            grid_pane.style(f"width:{base_w}px; height:{base_h}px")
            fit_w = lay.width + 2 * _PAD
            grid_pane.props(f'data-base-w="{base_w}" data-base-h="{base_h}" data-fit-w="{fit_w}"')
            board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
            colhead.style(f"height:{fy}px")
            colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
            corner.style(f"width:{fx}px; height:{fy}px")
            gridbody.style(f"top:{_PAD + fy}px")
            rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
            show_frozen.style(f"height:{max(0, fy - _CHROME_H)}px")
            show_scroll.style(f"max-height:calc(100vh - {_PAD + fy}px)")
            seen = set()

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
                    place_line(ln, "", board, fy)
                if x1 >= fx and y0 < fy:
                    place_line(ln, "#col", colhead_inner, 0)
                if x0 < fx and y1 >= fy:
                    place_line(ln, "#row", rowband, fy)

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
                if bl.tint in _TINTS:
                    style += f"; background:var(--wash-{bl.tint})"
                rec.els[eid].style(style)

            for bl in lay.blocks:
                for pane in _block_panes(bl, fx, fy):
                    place_block(bl, pane)

            g = rec.gesture
            if g is not None and g.source is not None:
                src_kind = next((cb.kind for cb in lay.cells if cb.id == g.source), None)
                if src_kind is None or (g.source in rec.kinds and rec.kinds[g.source] != src_kind):
                    end_gesture()
            amber, red = compute_rings(lay)

            for cb in lay.cells:
                seen.add(cb.id)
                if cb.id in rec.els and rec.kinds[cb.id] != cb.kind:
                    rec.drop(cb.id)
                container = _freeze_container(cb, fx, fy)
                if cb.id not in rec.els:
                    with cell_parents[container]:
                        rec.make_cell(cb)
                top = cb.y - (fy if container in ("body", "row") else 0)
                rec.els[cb.id].style(f"left:{cb.x}px; top:{top}px; width:{cb.w}px; height:{cb.h}px")
                rec.update_cell(cb)
                paint_cell(cb.id, amber, red)

            for eid in [e for e in rec.els if e not in seen]:
                rec.drop(eid)

            mean_damage_help_text = tooltips.mean_damage_help(service.is_all_interval(editor.tuning_scheme))
            for cid in tooltips.MEAN_DAMAGE_IDS:
                if cid in rec.mean_damage_tips:
                    rec.mean_damage_tips[cid].set_text(mean_damage_help_text)
                    continue
                wrap = rec.els.get(cid)
                if wrap is not None and wrap._props.get("data-zoomhelp") != mean_damage_help_text:
                    wrap._props["data-zoomhelp"] = mean_damage_help_text
                    wrap.update()

            refs["undo"].set_enabled(editor.can_undo)
            refs["redo"].set_enabled(editor.can_redo)
            refs["reset"].set_enabled(editor.can_reset or chapter[0] != show_settings.CHAPTER_DEFAULT)
            if chapter_slider.value != chapter[0]:
                chapter_slider.value = chapter[0]
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
            for key, box in boxes.items():
                if box.value != editor.settings[key]:
                    box.value = editor.settings[key]
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
            _sync_show_availability()
            gesture_idle = rec.gesture is None or rec.gesture.token is None
            if gesture_idle and not (load_failed[0] and not editor.can_undo):
                _doc_store()[_STORE_KEY] = editor.serialize()
        finally:
            building[0] = False
        # clear the busy scrim: this render is the result the user was waiting on, so whatever the
        # client armed (see _BUSY_JS) comes down now. The message rides out with this render's DOM
        # patch, so the scrim stays up across the patch and lifts once the new grid is on screen.
        # Skipped under the User test harness, where there's no live client (and run_javascript from
        # inside a handler-driven render hits a torn-down slot context); the scrim is browser-only.
        if not helpers.is_user_simulation():
            page_client.run_javascript("window.rttBusy && window.rttBusy.done()")

    drawer_open = [False]

    def toggle_drawer():
        drawer_open[0] = not drawer_open[0]
        panelgroup.classes(add="rtt-open") if drawer_open[0] else panelgroup.classes(remove="rtt-open")

    def _pane_chrome():
        ui.button(icon="menu", on_click=toggle_drawer, color=None).props("flat dense") \
            .classes("rtt-hamburger").tooltip(tooltips.CHROME_HELP["settings"])
        ui.label("D&D's RTT app").classes("rtt-sidetitle")

    with ui.element("div").classes("rtt-shell"):
        panelgroup = ui.element("div").classes("rtt-panelgroup")
        with panelgroup:
            with ui.element("div").classes("rtt-chrome"):
                _pane_chrome()
            drawer = ui.element("div").classes("rtt-drawer")
            with drawer, ui.element("div").classes("rtt-drawer-inner"):
                show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
                with show_frozen:
                    with ui.element("div").classes("rtt-show-all"):
                        select_all_box = ui.checkbox(
                            "select all / none",
                            value=all(editor.settings[k] for k in show_settings.IMPLEMENTED),
                            on_change=lambda e: on_select_all(e.value)) \
                            .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                            .mark("showall").tooltip(tooltips.CHROME_HELP["select_all"])
                        dark_btn = ui.button(on_click=on_dark_toggle, color=None) \
                            .props(f"flat dense round icon={_dark_icon()}") \
                            .classes("rtt-darktoggle").mark("darkmode") \
                            .tooltip(tooltips.CHROME_HELP["dark_mode"])
                boxes: dict = {}
                examples: dict = {}
                tile_parts: dict = {}
                show_rows: dict = {}
                show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
                with show_scroll:
                    with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
                        with ui.element("div").classes("rtt-chapter-head"):
                            ui.label("guide chapter").classes("rtt-chapter-title")
                            chapter_reading = ui.label(_chapter_reading(chapter[0])) \
                                .classes("rtt-chapter-reading").mark("chapterreading")
                        chapter_slider = ui.slider(
                            min=show_settings.CHAPTER_MIN, max=show_settings.CHAPTER_STAR,
                            step=1, value=chapter[0],
                            on_change=lambda e: on_chapter_change(e.value)) \
                            .props("markers snap dense color=grey-8") \
                            .classes("rtt-chapter-slider").mark("chapterslider") \
                            .tooltip(tooltips.CHROME_HELP["chapter"])
                    for group_name, items in show_settings.SHOW_GROUPS:
                        with ui.element("div").classes("rtt-show-group"):
                            if group_name == "general":
                                def add_el(key, html, *, marked=False, size=None, style=""):
                                    fs = size if size is not None else _TILE_FONT.get(key)
                                    css = (f"font-size:{fs}px;" if fs else "") + style
                                    el = ui.html(html).classes("rtt-tile-part").tooltip(tooltips.SHOW_HELP[key])
                                    if key == "mnemonics":
                                        el.classes(add="rtt-tile-mnem")
                                    if marked:
                                        el.mark(f"showpart:{key}")
                                    if css:
                                        el.style(css)
                                    el.on("click", lambda k=key: on_part_click(k))
                                    tile_parts.setdefault(key, []).append(el)
                                    return el

                                def part_el(key, *, size=None, style=""):
                                    return add_el(key, _general_part_html(key), marked=True, size=size, style=style)

                                ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
                                with ui.element("div").classes("rtt-show-tile"):
                                    with ui.element("div").classes("rtt-tile-head"):
                                        ui.html(_tile_fold_html()).classes("rtt-tile-fold")
                                        refs["audio_bank"] = _audio_bank()
                                    for line in _GENERAL_TILE_LINES:
                                        if "gridded_values" in line:
                                            gut = 20
                                            hgut = 18
                                            cell_x = hgut + gut + _TILE_CELL_X
                                            cell_y = _TILE_CELL_Y
                                            row_y = cell_y + (_TILE_CELL - 13) // 2
                                            with ui.element("div").classes("rtt-tile-line"), \
                                                    ui.element("div").style(f"position:relative;"
                                                        f"width:{hgut + gut + _TILE_FRAME_W + gut + hgut}px;height:{_TILE_FRAME_H}px"):
                                                part_el("drag_to_combine", size=15,
                                                        style=f"position:absolute;left:0;top:{cell_y}px;width:{hgut}px;"
                                                              f"height:{_TILE_CELL}px;justify-content:center")
                                                add_el("header_symbols", _general_part_html("header_symbols"), marked=True,
                                                       size=_TILE_FONT["rowlabel"],
                                                       style=f"position:absolute;left:{hgut}px;top:{row_y}px;width:{gut - 3}px;"
                                                             "height:13px;justify-content:flex-end")
                                                part_el("gridded_values", style=f"position:absolute;left:{hgut + gut}px;top:0")
                                                part_el("math_expressions", size=_fit_font(_TILE_MATH, _TILE_CELL),
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
                                                              f"width:{_TILE_CELL}px;height:9px;justify-content:center")
                                                part_el("quantities",
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
                                                              f"width:{_TILE_CELL}px;height:11px;justify-content:center")
                                                part_el("decimals",
                                                        style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
                                                              f"width:{_TILE_CELL}px;height:8px;justify-content:center")
                                                add_el("cell_units", _general_part_html("cell_units"), marked=True,
                                                       size=_TILE_FONT["cellunit"],
                                                       style=f"position:absolute;left:{cell_x}px;top:{cell_y + 28}px;"
                                                             f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:#555")
                                        elif "names" in line:
                                            before, _letter, after = _tile_name_pieces()
                                            with ui.element("div").classes("rtt-tile-line"):
                                                add_el("names", _escape(before), marked=True)
                                                part_el("mnemonics")
                                                add_el("names", _escape(after))
                                        elif "presets" in line:
                                            with ui.element("div").classes("rtt-tile-line rtt-tile-line-wide"), \
                                                    ui.element("div").classes("rtt-tile-cbox"):
                                                part_el("presets")
                                        else:
                                            with ui.element("div").classes("rtt-tile-line"):
                                                for key in line:
                                                    part_el(key)
                                continue
                            with ui.element("div").classes("rtt-show-head"):
                                ui.label("show").classes("rtt-show-title")
                                ui.label("example").classes("rtt-show-examplehdr")
                            for key, label, _ in items:
                                row = ui.element("div").classes("rtt-show-row").mark(f"showrow:{key}")
                                with row:
                                    box = ui.checkbox(label, value=editor.settings[key],
                                                      on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                                        .props("dense size=xs color=grey-8").classes("rtt-show-item") \
                                        .mark(f"showbox:{key}").tooltip(tooltips.SHOW_HELP[key])
                                    example = ui.html(_example_html(key)).classes("rtt-ex-cell") \
                                        .mark(f"showexample:{key}")
                                boxes[key] = box
                                examples[key] = example
                                show_rows[key] = row
                                parent = show_settings.SUBCONTROLS.get(key)
                                if parent:
                                    box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                                    row.bind_visibility_from(boxes[parent], "value")

        grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with grid_pane:
            colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with colhead:
                colhead_inner = ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
            corner = ui.element("div").classes("rtt-corner").mark("corner")
            with corner:
                with ui.element("div").classes("rtt-titletile").mark("titletile"):
                    with ui.element("div").classes("rtt-tile-btns"):
                        refs["undo"] = ui.button(icon="undo", on_click=lambda: act(editor.undo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn rtt-hk-undo").mark("undo").tooltip(tooltips.CHROME_HELP["undo"])
                        refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn rtt-hk-redo").mark("redo").tooltip(tooltips.CHROME_HELP["redo"])
                        refs["reset"] = ui.button(icon="restart_alt", on_click=lambda: reset_everything(), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("reset").tooltip(tooltips.CHROME_HELP["reset"])

                        def share_link():
                            _end_commit_gestures()
                            token = _encode_state(editor.serialize())
                            ui.run_javascript(
                                "(async function(){"
                                f"var u=location.origin+location.pathname+'?{_STATE_PARAM}='+{json.dumps(token)};"
                                "try{await navigator.clipboard.writeText(u);}"
                                "catch(e){var t=document.createElement('textarea');t.value=u;"
                                "document.body.appendChild(t);t.select();"
                                "document.execCommand('copy');t.remove();}})()")
                            ui.notify("Shareable link copied to clipboard")
                        refs["share"] = ui.button(icon="share", on_click=share_link, color=None) \
                            .props("flat dense").classes("rtt-iconbtn rtt-noarm").mark("share").tooltip(tooltips.CHROME_HELP["share"])

                        refs["tour"] = ui.button(
                            icon="help_outline",
                            on_click=lambda: ui.run_javascript("window.rttTour && window.rttTour.start()"),
                            color=None) \
                            .props("flat dense").classes("rtt-iconbtn rtt-noarm").mark("tour") \
                            .tooltip(tooltips.CHROME_HELP["tour"])

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
                    if building[0] or value is None:
                        return
                    editor.set_nonprime_basis_approach(value)
                    _request_render()  # the nonprime approach changes how the tuning solves — off the loop

                def on_approach_hover(value):
                    # preview the hovered approach option: ring the cells reading the temperament that
                    # way would move, without committing (control_hover reverts it). None = leaving the
                    # radio, so clear the preview. Each option is its own hover target (mouseenter).
                    if value is None:
                        control_unhover()
                        return
                    control_hover(lambda a=value: editor.set_nonprime_basis_approach(a))

                refs["approach"] = ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
                refs["approach_opts"] = {}
                with refs["approach"]:
                    for key, label in approach_options.items():
                        opt = ui.element("div").classes("rtt-rangeopt")
                        with opt:
                            ui.element("span").classes("rtt-rangebox")
                            ui.label(label).classes("rtt-rangelabel")
                        opt.on("click", lambda _=None, k=key: on_approach_change(k))
                        opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
                        opt.mark(f"approach-{label}")
                        refs["approach_opts"][key] = opt
                refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))
            gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
            with gridbody:
                board = ui.element("div").classes("rtt-gridcontent").mark("board")
                with board, ui.element("div").classes("rtt-band"):
                    rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
            refs["approach"].move(board)
            cell_parents = {"corner": corner, "col": colhead_inner, "row": rowband, "body": board}

    render()
    apply_chapter()
    if load_failed[0]:
        ui.notify(_LOAD_FAILED, type="warning", position="top", multi_line=True, close_button=True)


def _reload_excludes(worktrees: Path) -> str:
    excludes = [".*", ".py[cod]", ".sw.*", "~*"]
    if worktrees.is_dir():
        excludes.append(str(worktrees))
    return ", ".join(excludes)


def main() -> None:
    hosted_port = os.environ.get("PORT")
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    elif hosted_port:
        port = int(hosted_port)
    else:
        port = 8137
    # Serve the DandDsRTT org icon as a LOCAL file (assets/favicon.png — the org's GitHub avatar,
    # vendored). A remote URL would let NiceGUI emit it into the page <link rel=icon> (the tab still
    # works) but registers /favicon.ico → get_favicon_response(), which raises ValueError on any
    # remote URL — every browser/bot/health-check hit on /favicon.ico then 500s. A local file routes
    # /favicon.ico to a working FileResponse (NiceGUI gates on helpers.is_file), so the icon serves
    # and the route stops erroring.
    favicon = str(Path(__file__).parent / "assets" / "favicon.png")
    run_kwargs = dict(
        title="D&D's RTT App", favicon=favicon,
        show=False, port=port,
        storage_secret=os.environ.get("STORAGE_SECRET", _STORAGE_SECRET),
        # The heavy retuning commits now render off the event loop (see _commit_render), so the
        # websocket heartbeat keeps flowing through them. A few paths still build synchronously — the
        # initial page (no socket yet), a structural hover PREVIEW the first time a high-limit state is
        # seen (it warms the cache, so it's a one-off), a drag preview. Give the heartbeat generous
        # headroom so one of those brief sync builds — slower still under parallel CPU load — can't trip
        # the "lost connection" reload NiceGUI's default 3 s timeout caused. (Derived pings: interval
        # max(0.8·t, 4) = 24 s, timeout max(0.4·t, 2) = 12 s.)
        reconnect_timeout=30.0,
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
