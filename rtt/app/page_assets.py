from __future__ import annotations

import base64
import json
import logging
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from nicegui import app, helpers, ui

from rtt.app import (
    service,
    spreadsheet,
    spreadsheet_constants,
    tooltips,
)
from rtt.app.marks import (
    BR_COLOR,
    PENDING_COLOR,
)
from rtt.app.render_html import (
    _mode_svg,
    _option_box_svg,
    _wave_svg,
)

_log = logging.getLogger(__name__)


def cb_method(fn):
    fn._rtt_cb = True
    return fn


class _KindHandlers(NamedTuple):
    build: Callable
    update: Callable | None = None


_ASSETS = Path(__file__).parent / "assets"

# Self-host the body font same-origin so every machine renders the same face (a non-self-hosted face
# falls back per-OS to differing proportional digits). The Math face supplies the ⟨⟩⟪⟫ EBK brackets
# the Text face omits. Registering at import is idempotent across the reload worker and the test
# re-imports (FastAPI's duplicate route is harmless — first match wins).
app.add_static_files("/rtt-fonts", _ASSETS / "fonts")

_PAD = 12
_T = "0.25s"
_PANEL_W = 330
_TAB_W = 40
_TAB_H = 218
_CHROME_H = 40
_TOOLTIP_DELAY_MS = 700
# Quasar defaults the tooltip show-delay to 0; this waits for a deliberate cursor rest instead.
_STORE_KEY = "rtt_doc"
_STATE_PARAM = "state"
_DARK_KEY = "rtt_dark"
_CHAPTER_KEY = "rtt_chapter"
_STORAGE_SECRET = "dnd-rtt-app"
# NiceGUI: under the in-process User test simulation app.storage.user is file-backed, so writing it
# per render litters the tree and races the harness teardown; a module-level dict gives the same
# survives-a-refresh persistence per test with no file I/O (production uses app.storage.user).
_MEMORY_STORE: dict = {}


def _doc_store() -> dict:
    return _MEMORY_STORE if helpers.is_user_simulation() else app.storage.user


def _encode_state(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode_state(token: str) -> dict:
    raw = zlib.decompress(base64.urlsafe_b64decode(token.encode("ascii")))
    return json.loads(raw.decode("utf-8"))


_INVALID_TEMPERAMENT = (
    "Not a valid temperament: the generators must be independent and every prime reached."
)
_INVALID_FORM = (
    "Not a valid generator form: 𝐹 must be a square matrix with determinant ±1 (unimodular)."
)

_SUBPICK_POPUP_W = 220

_INVALID_PROJECTION = (
    "That isn't a valid projection — 𝑃 must be idempotent (𝑃² = 𝑃) with the commas in its kernel."
)
_INVALID_EMBEDDING = "That isn't a valid embedding — 𝑀𝐺 must equal the identity."

_INVALID_PRESCALER = "A prescaler diagonal entry must be a positive, finite number."
_INVALID_WEIGHT = "A damage weight must be a positive, finite number."

_INVALID_UNCHANGED = (
    "That isn't a valid unchanged-interval basis — each entry must be a whole number."
)

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
    "mapping": 1,
    "commacell": 1,
    "interestcell": 1,
    "heldcell": 1,
    "targetcell": 1,
    "powerinput": 1,
    "prescalercell": 0.001,
}
_INT_WHEEL_JS = (
    "(e) => { if (e.currentTarget.contains(document.activeElement)) "
    "{ e.preventDefault(); emit(e); } }"
)
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
    count: Callable[[], int]
    cell_id: Callable[[object, int], str]
    pending: Callable[[], object]
    set_pending: Callable[[list], None]
    commit: Callable[[list], None]
    validate: Callable[[list], bool] | None = None
    guard: Callable[[], bool] | None = None
    draft_arms: bool = False


_GRIDVALUE_SPECS = {
    "ratiocell": _GridValueSpec(True, True, "on_ratio_change", None, True),
    "elementcell": _GridValueSpec(True, True, "on_element_change", "on_element_preview", True),
    "elementratio": _GridValueSpec(True, True, "on_element_change", "on_element_preview", True),
    "mapping": _GridValueSpec(
        False, True, "on_mapping_change", "on_mapping_change", False, ("row",)
    ),
    "formcell": _GridValueSpec(False, False, "on_form_change", "on_form_change", False),
    "commacell": _GridValueSpec(
        False, True, "on_comma_change", "on_comma_change", False, ("col", "comma")
    ),
    "unchangedcell": _GridValueSpec(
        False, False, "on_unchanged_change", "on_unchanged_change", False
    ),
    "interestcell": _GridValueSpec(
        False, True, "on_interest_change", "on_interest_change", False, ("col", "interest")
    ),
    "heldcell": _GridValueSpec(
        False, True, "on_held_change", "on_held_change", False, ("col", "held")
    ),
    "targetcell": _GridValueSpec(
        False, True, "on_target_cells_change", "on_target_cells_change", False, ("col", "target")
    ),
}


def _vgroup_key(cell_box: spreadsheet.CellBox) -> str:
    if cell_box.kind in ("mapping", "targetcell"):
        return cell_box.id.rsplit(":", 1)[0]
    if cell_box.kind == "formcell":
        return "cell:finv"
    parts = cell_box.id.split(":")
    return ":".join(parts[:2] + parts[3:])




_MODE_FILLS = (
    (frozenset({(1, 1)}), "note"),
    (frozenset({(2, 0), (1, 1), (0, 2)}), "arpeggio"),
    (frozenset({(0, 1), (1, 1), (2, 1)}), "chord"),
    (frozenset({(2, 0), (1, 1), (0, 2), (1, 2), (2, 1), (2, 2)}), "rolled chord"),
)
_AUDIO_GLYPHS = {
    "mute": [
        '<span class="material-icons rtt-audio-glyph">volume_up</span>',
        '<span class="material-icons rtt-audio-glyph">volume_off</span>',
    ],
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(fill, name) for fill, name in _MODE_FILLS],
    "lock": [
        '<span class="material-icons rtt-audio-glyph">lock_open</span>',
        '<span class="material-icons rtt-audio-glyph">lock</span>',
    ],
    "root": '<span class="rtt-audio-root-glyph">1/1</span>',
}

_AUDIO_JS = (_ASSETS / "audio.js").read_text(encoding="utf-8")

# Browser: the column-title strip sits outside the body scroller (so the scrollbar can stop below it),
# so CSS can't make it ride the scroll — this listener translateX-syncs it instead. scroll doesn't
# bubble, so it's caught in the capture phase.
_FREEZE_JS = (_ASSETS / "freeze.js").read_text(encoding="utf-8")

_FRACTION_JS = (_ASSETS / "fraction.js").read_text(encoding="utf-8")

_DECIMAL_JS = (_ASSETS / "decimal.js").read_text(encoding="utf-8")

_ACTIVECELL_JS = (_ASSETS / "activecell.js").read_text(encoding="utf-8")

_MAPPING_DEMO_JS = (_ASSETS / "mapping_demo.js").read_text(encoding="utf-8")

_TOUR_JS = (_ASSETS / "tour.js").read_text(encoding="utf-8")

# NiceGUI: a tour step's `selector` must be a real DOM region class, NOT a .mark() (which exists only under
# the test simulation), or the spotlight finds nothing in production.
_TOUR_STEPS = [
    {
        "selector": "",
        "title": "Welcome to D&D's RTT app",
        "body": "A grid for exploring regular temperaments. Here's a quick tour of what's on "
        "screen — use <b>Next</b> / <b>Back</b> (or the arrow keys), and <b>Skip</b> to leave "
        "anytime.",
    },
    {
        "selector": "",
        "title": "Reading the grid",
        "body": "The grid sets intervals alongside the temperament objects that act on them, so you "
        "can see how they relate. Follow a column down to watch an interval flow through the "
        "temperament — the mapping 𝑀 sends it to a count of generators, then the tuning turns "
        "that into cents. Each value's symbol and its equation (like 𝒕 = 𝒈𝑀) name the product "
        "behind it.",
    },
    {
        "selector": ".rtt-zoomable",
        "place": "right",
        "title": "The value cells",
        "body": "Most of the grid is computed values. Cells drawn with a box are editable — type a "
        "new value and the whole grid recomputes.",
    },
    {
        "selector": ".rtt-fan-button",
        "place": "bottom",
        "title": "Reshaping the grid",
        "body": "The grid grows and shrinks with you. A <b>+</b> button adds a column or row — a new "
        "interval or mapping row; hovering a column or row reveals a <b>−</b> to remove it. "
        "The little chevrons expand or collapse a tile.",
    },
    {
        "selector": ".rtt-titletile",
        "place": "bottom",
        "title": "Undo, reset & share",
        "body": "Up here: <b>undo</b> / <b>redo</b> your edits, <b>reset</b> everything to defaults, "
        "and <b>share</b> a link that reopens the app in exactly this state.",
    },
    {
        "selector": ".rtt-hamburger",
        "place": "right",
        "open": True,
        "title": "The settings panel",
        "body": "This hamburger opens the Show panel — the control room for the whole grid. Let's "
        "open it up.",
    },
    {
        "selector": ".rtt-chapter-group",
        "place": "right",
        "open": True,
        "title": "Guide chapters",
        "body": "New to the theory? This slider reveals the controls chapter by chapter, the way "
        "D&D's guide introduces them — slide left for a simpler view, right (to ★) for "
        "everything.",
    },
    {
        "selector": ".rtt-show-tile",
        "place": "right",
        "open": True,
        "title": "Tile features",
        "body": "This sample tile is a live menu: click any part of it — the name, the symbol, the "
        "closed form, the units — to show or hide that feature across the whole grid. The "
        "audio controls up top drive every speaker.",
    },
    {
        "selector": ".rtt-show-scroll .rtt-show-group:last-child",
        "place": "right",
        "open": True,
        "title": "The Show toggles",
        "body": "These checkboxes reveal each kind of feature — not only extra rows and columns, but "
        "the controls that come with them and which cells you can edit. Turn things on as you "
        "need them — start small and build up.",
    },
    {
        "selector": "",
        "title": "That's the tour",
        "body": "Explore freely — nothing here is permanent, and <b>reset</b> always brings back the "
        "defaults. Replay this tour anytime from the <b>?</b> button by the undo/redo "
        "controls. Happy tempering!",
    },
]

_STACKED_EXIT_JS = (
    "(e) => { const b = e.target.closest('.rtt-fraction-edit, .rtt-decimal-edit'); "
    "if (!b || !b.contains(e.relatedTarget)) emit(); }"
)

_GROUP_EXIT_JS = (
    "(e) => { const g = e.target.closest('[data-vgroup]'), "
    "t = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-vgroup]'); "
    "if (!g || !t || g.getAttribute('data-vgroup') !== t.getAttribute('data-vgroup')) emit(); }"
)


_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --tab-w:{_TAB_W}px; --tab-h:{_TAB_H}px; --chrome-h:{_CHROME_H}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --pending-color:{PENDING_COLOR}; --pending-text-color:{_PENDING_TEXT_COLOR}; --preview-color:{_PREVIEW_COLOR}; --preview-text-color:{_PREVIEW_TEXT_COLOR}; --preview-remove-color:{_PREVIEW_REMOVE_COLOR}; --preview-remove-text-color:{_PREVIEW_REMOVE_TEXT_COLOR};
  --c-gridline:#e0e0e0;
  --wash-base:#fff; --wash-tuning:{_TINTS["tuning"]}; --wash-temperament:{_TINTS["temperament"]}; --wash-form:{_TINTS["form"]};
  --cell-border-w:{_CELL_BORDER_W}px; --cell-border:{_CELL_BORDER}; --cell-font:{_CELL_FONT}px;
  --zoom-factor:{_CELL_FONT / _STACKED_MAIN_FONT};
  --label-w:{spreadsheet_constants.LABEL_WIDTH}px; --header-h:{spreadsheet_constants.HEADER_HEIGHT}px; --line-w:{spreadsheet_constants.LINE_WIDTH}px;
  --plain-text-edit-h:{spreadsheet_constants.PLAIN_TEXT_EDIT_HEIGHT}px; --option-box:{spreadsheet_constants.OPTION_BOX_PX}px; --button:{spreadsheet_constants.BUTTON}px;
  --option-box-unchecked:url("{_option_box_svg(None)}");
  --option-box-checked:url("{_option_box_svg("#000")}");
  --option-box-disabled:url("{_option_box_svg("#888")}");
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
_CSS = (
    _FONT_FACE
    + _CSS_VARS
    + (_ASSETS / "rtt.css").read_text(encoding="utf-8")
    + _CSS_DARK_VARS
    + (_ASSETS / "rtt-dark.css").read_text(encoding="utf-8")
    + (_ASSETS / "tour.css").read_text(encoding="utf-8")
)


_UNITS_MAX_FONT = 10.0
_CELLUNIT_MAX_FONT = 7.0
_MATLABEL_FONT = 11.0
_MATLABEL_MIN_FONT = 6.0


_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "hbar"}

GRIDVALUE_KINDS = frozenset({
    "mapping", "commacell", "unchangedcell", "interestcell", "heldcell", "targetcell",
    "formcell", "ratiocell", "elementcell", "elementratio",
})

_EBK_SQUARE = str.maketrans("⟨{⟩}", "[[]]")
_TRANSPOSE_MARK = "ᵀ"

_PLAIN_TEXT_DUAL_VECTOR_KIND = {
    "plain_text:vectors:commas": True,
    "plain_text:vectors:targets": True,
    "plain_text:projection:generators": True,
    "plain_text:mapping:primes": False,
    "plain_text:projection:primes": False,
    "plain_text:prescaling:primes": False,
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
    "symbols": 15,
    "equivalences": 15,
    "rowlabel": spreadsheet_constants.MATLABEL_HEIGHT - 2,
    "names": spreadsheet_constants.CAPTION_FONT,
    "mnemonics": spreadsheet_constants.CAPTION_FONT,
    "units": 10,
    "cellunit": 7,
    "plain_text_values": 11,
    "drag_to_combine": 18,
}


_AUDIO_BANK = (
    ("mute", _AUDIO_GLYPHS["mute"][0], "toggleMute"),
    ("wave", _AUDIO_GLYPHS["wave"][0], "cycleWave"),
    ("mode", _AUDIO_GLYPHS["mode"][0], "cycleMode"),
    ("hold", _AUDIO_GLYPHS["lock"][0], "toggleHold"),
    ("root", _AUDIO_GLYPHS["root"], "toggleRoot"),
)


def _audio_bank() -> ui.element:
    bank = ui.element("div").classes("rtt-tile-bank").mark("audiobank")
    with bank:
        for control, glyph, fn in _AUDIO_BANK:
            ui.html(glyph).classes("rtt-audio-control").mark(f"audio_control:{control}").props(
                f'data-audio-control="{control}"'
            ).on("click", js_handler=f"() => window.rttAudio.{fn}()").tooltip(
                tooltips.AUDIO_HELP[control]
            )
    return bank


# Quasar/Vue: the dropdown popup is teleported to <body>, so a per-option slot can't reach the server
# (its $parent is the menu, and Vue templates block non-whitelisted globals like `document`). So each
# option stamps data-optidx/data-optcid and this one document-level delegation reads them and fires an
# `opthover` CustomEvent at the chooser's cell. It debounces (~90 ms settle) and dedupes because each
# preview is a server re-solve and raw mouseover would flood the socket past its heartbeat (-> reload).
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
  // Browser: a removed element under the cursor does not fire mouseout reliably, so the pending
  // settle-timer is cancelled here on pointerdown rather than relying on the popup-removal mouseout.
  document.addEventListener('pointerdown', () => { clearTimeout(timer); lastCid = null; lastIdx = null; }, true);
})()
"""


# Quasar: a tooltip hides only on its anchor's `mouseleave`, so it strands on screen when the anchor is
# removed or reflowed out from under a stationary cursor before any leave fires. These capture-phase
# listeners synthesize that `mouseleave` (only — never blur, so the cells' blur-commit handlers stay
# untouched) before a reflow: from the pressed node on pointerdown, from the :hover node on keydown/wheel.
_TOOLTIP_DISMISS_JS = """
(() => {
  if (window.__rttTipDismiss) return;
  window.__rttTipDismiss = true;
  const dropFrom = (node) => {
    for (let el = node; el instanceof Element; el = el.parentElement) {
      el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: false}));
    }
  };
  document.addEventListener('pointerdown', (e) => dropFrom(e.target), true);
  const dropHovered = () => {
    if (document.querySelector('.q-tooltip') === null) return;
    const hov = document.querySelectorAll(':hover');
    if (hov.length) dropFrom(hov[hov.length - 1]);
  };
  document.addEventListener('keydown', dropHovered, true);
  document.addEventListener('wheel', dropHovered, {capture: true, passive: true});
})()
"""


_ZOOM_JS = """
(() => {
  if (window.__rttZoom) return;
  window.__rttZoom = true;
  const F = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom-factor')) || 1.7;
  const DELAY = 130;
  const GAP = 8;
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
    const audioFloat = cell.classList.contains('rtt-speaker') && !document.body.classList.contains('rtt-audio-muted');
    let top = r.top - GAP - oh;
    let above = true;
    if (audioFloat || top < 4) { top = r.bottom + GAP; above = false; }
    top = Math.max(4, Math.min(top, vh - oh - 4));
    overlay.style.flexDirection = above ? 'column-reverse' : 'column';
    overlay.style.left = left + 'px';
    overlay.style.top = top + 'px';
  };

  const build = (cell) => {
    const w = cell.offsetWidth, h = cell.offsetHeight;
    if (!w || !h) return;
    const srcInputs = cell.querySelectorAll('input');
    let hasContent = cell.textContent.trim();
    srcInputs.forEach(i => { if (i.value && i.value.trim()) hasContent = true; });
    if (!hasContent) return;

    overlay.innerHTML = '';
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
    clone.querySelectorAll('.q-tooltip').forEach(n => n.remove());
    clone.querySelectorAll('.rtt-ratio-operation').forEach(n => n.remove());
    // Browser: cloneNode does NOT copy a live input's typed value (a property, not an attribute), so
    // each editable cell's value is copied onto the clone by hand or it would clone empty.
    const cloneInputs = clone.querySelectorAll('input');
    srcInputs.forEach((s, i) => { if (cloneInputs[i]) cloneInputs[i].value = s.value; });
    scale.appendChild(clone);
    const tile = document.createElement('div');
    tile.className = 'rtt-zoom-tile';
    tile.appendChild(scale);
    overlay.appendChild(tile);
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

  document.addEventListener('mouseover', (e) => {
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (!cell || cell === anchor) return;
    if (timer) clearTimeout(timer);
    anchor = cell;
    timer = setTimeout(() => { if (anchor === cell && cell.isConnected) build(cell); }, DELAY);
  });
  document.addEventListener('mouseout', (e) => {
    const toFloat = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.rtt-speaker-float');
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (cell && cell === anchor) {
      if (!toFloat && !cell.contains(e.relatedTarget)) hide();
      return;
    }
    const fromFloat = e.target.closest && e.target.closest('.rtt-speaker-float');
    if (fromFloat && anchor && !toFloat) {
      const toCell = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.rtt-zoomable');
      if (toCell !== anchor) hide();
    }
  });
  document.addEventListener('pointerdown', (e) => {
    if (e.target.closest && e.target.closest('.rtt-speaker-float')) return;
    hide();
  }, true);
  document.addEventListener('keydown', hide, true);
  document.addEventListener('wheel', hide, {capture: true, passive: true});
  document.addEventListener('scroll', hide, {capture: true, passive: true});
})()
"""

# Quasar: a tooltip is pointer-events:none and hides the instant the cursor leaves its anchor, so its
# link can't be clicked; this builds a real hoverable card instead, kept open while the cursor is on it.
_GUIDE_JS = """
(() => {
  if (window.__rttGuide) return;
  window.__rttGuide = true;
  const DELAY = 200;
  const HIDE = 160;
  const GAP = 6;
  let showTimer = null, hideTimer = null, anchor = null, shownTile = null;

  const card = document.createElement('div');
  card.className = 'rtt-guide-card';
  card.style.display = 'none';
  document.body.appendChild(card);

  const reallyHide = () => {
    card.style.display = 'none'; card.innerHTML = ''; anchor = null; shownTile = null;
  };
  const scheduleHide = () => { clearTimeout(hideTimer); hideTimer = setTimeout(reallyHide, HIDE); };
  const cancelHide = () => { clearTimeout(hideTimer); };

  const place = (cell) => {
    const r = cell.getBoundingClientRect();
    const card_width = card.offsetWidth, card_height = card.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    let left = Math.max(4, Math.min(r.left, vw - card_width - 4));
    let top = r.bottom + GAP;
    if (top + card_height > vh - 4) top = Math.max(4, r.top - GAP - card_height);
    card.style.left = left + 'px';
    card.style.top = top + 'px';
  };

  const show = (cell) => {
    if (document.body.classList.contains('rtt-no-tooltips')) return;
    const text = cell.getAttribute('data-guide-text');
    if (!text) return;
    const loc = cell.getAttribute('data-guide-loc');
    const url = cell.getAttribute('data-guide-url');
    card.innerHTML = '';
    const body = document.createElement('div');
    body.className = 'rtt-guide-card-text';
    body.textContent = text;
    card.appendChild(body);
    if (url) {
      const a = document.createElement('a');
      a.className = 'rtt-guide-card-link';
      a.href = url; a.target = '_blank'; a.rel = 'noopener';
      a.textContent = loc + ' →';
      card.appendChild(a);
    }
    shownTile = cell.getAttribute('data-guide-tile');
    card.style.display = 'block';
    place(cell);
  };

  card.addEventListener('mouseenter', cancelHide);
  card.addEventListener('mouseleave', scheduleHide);

  document.addEventListener('mouseover', (e) => {
    const cell = e.target.closest && e.target.closest('.rtt-guide-link');
    if (!cell) return;
    cancelHide();
    if (card.style.display === 'block' && cell.getAttribute('data-guide-tile') === shownTile) return;
    if (cell === anchor) return;
    if (showTimer) clearTimeout(showTimer);
    anchor = cell;
    showTimer = setTimeout(() => { if (anchor === cell && cell.isConnected) show(cell); }, DELAY);
  });
  document.addEventListener('mouseout', (e) => {
    const cell = e.target.closest && e.target.closest('.rtt-guide-link');
    if (!cell) return;
    const to = e.relatedTarget;
    const toCell = to && to.closest && to.closest('.rtt-guide-link');
    if (to && (card.contains(to) ||
               (toCell && toCell.getAttribute('data-guide-tile') === cell.getAttribute('data-guide-tile')))) return;
    if (showTimer) { clearTimeout(showTimer); showTimer = null; }
    scheduleHide();
  });
  document.addEventListener('pointerdown', (e) => { if (!card.contains(e.target)) reallyHide(); }, true);
  document.addEventListener('keydown', reallyHide, true);
  document.addEventListener('wheel', reallyHide, {capture: true, passive: true});
  document.addEventListener('scroll', reallyHide, {capture: true, passive: true});
})()
"""

# The busy scrim is armed client-side because a synchronous re-render holds the event loop until it
# finishes, so the server can't send a "show scrim" message mid-work — only the browser can in that
# window. Every server render() ends by calling rttBusy.done(), so the scrim lifts when the grid lands.
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
    armTimer = setTimeout(reveal, {_BUSY_DELAY_MS});
    safety = setTimeout(clear, {_BUSY_SAFETY_MS});
  }};
  window.rttBusy = {{ arm, done: clear }};

  // reads --t off BODY, where the `animations`-off CSS class overrides it to 0s, so the reveal is
  // instant when animations are off.
  window.rttScheduleReveal = () => {{
    const t = getComputedStyle(document.body).getPropertyValue('--t').trim();
    const ms = (t.endsWith('ms') ? parseFloat(t) : parseFloat(t) * 1000) * 1.3;
    clearTimeout(window.__rttReveal);
    window.__rttReveal = setTimeout(() => {{
      document.querySelectorAll('.rtt-withhold').forEach(el => {{
        el.classList.remove('rtt-withhold');
        el.classList.add('rtt-reveal');
      }});
    }}, ms);
  }};

  // Browser: render() re-syncs control values programmatically (box.value = …), which fires SYNTHETIC
  // events; the e.isTrusted gate keeps those from re-arming the scrim after a render.
  const BUTTON = '.rtt-fan-button,.rtt-minus-button,.rtt-minus-button-v,.rtt-toggle,.rtt-icon-button';
  const at = (e, selector) => e.isTrusted && e.target && e.target.closest && e.target.closest(selector);
  document.addEventListener('pointerdown',
    (e) => {{ if (at(e, BUTTON) && !e.target.closest('.rtt-noarm')) window.rttBusy.arm(); }}, true);
  // Quasar's QCheckbox/QRadio commit on a CLICK of their role= div and never emit a DOM `change`,
  // so the committing settings controls are reached here on click, not on a `change` event.
  document.addEventListener('click', (e) => {{
    if (at(e, '[role=option],.q-item,.q-checkbox,.q-radio,.rtt-range-option')) window.rttBusy.arm();
  }}, true);
  // Browser: keys match on e.code (the physical key) so a Mac's Option+letter dead-keys and special
  // glyphs still match; preventDefault stops the browser's own Ctrl+Z / Alt-mnemonic / Cmd+, firing.
  document.addEventListener('keydown', (e) => {{
    if (!e.isTrusted) return;
    const mod = e.ctrlKey || e.metaKey;
    let selector = null, arm = true;
    if (mod && !e.altKey && e.code === 'KeyZ') selector = e.shiftKey ? '.rtt-hk-redo' : '.rtt-hk-undo';
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'KeyY') selector = '.rtt-hk-redo';
    else if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {{
      const k = {{KeyC: 'comma', KeyM: 'mapping', KeyT: 'target', KeyH: 'held', KeyI: 'interest', KeyE: 'element'}}[e.code];
      if (k) selector = '.rtt-hk-' + k;
    }}
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'Comma') {{ selector = '.rtt-hamburger'; arm = false; }}  // pane toggle is pure CSS — don't flash the scrim
    if (selector) {{
      const el = document.querySelector(selector);
      if (el) {{ e.preventDefault(); if (arm) window.rttBusy.arm(); el.click(); return; }}
    }}
    if (e.key === 'Enter' && e.target.closest && e.target.closest('.rtt-cell')) window.rttBusy.arm();
  }}, true);

  // Browser: the shown scrim's pointer-events:auto veil eats the wheel along with clicks, so while it
  // is up the wheel deltas are forwarded to the grid's own scroller by hand.
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
        # NiceGUI rebuilds the Quasar option dicts in super()._update_options(), so the divider rows
        # must be re-flagged disabled here after it, or a later set_options()/update() drops the flag.
        super()._update_options()
        for option, value in zip(self._props["options"], self._values, strict=False):
            if self._is_divider(value):
                option["disable"] = True


def _set_offlist_prompt(select: ui.select, value, prompt: str = "-") -> None:
    if value is None:
        select.props(f'display-value="{prompt}"')
    else:
        select.props(remove="display-value")


def _formchooser_options(cell_id: str) -> dict:
    if cell_id.endswith(":mapping"):
        return {
            "": "choose form",
            **{k: service.MAPPING_FORM_LABELS[k] for k in service.MAPPING_FORM_KEYS},
        }
    return {
        "": "choose form",
        **{k: service.COMMA_BASIS_FORM_LABELS[k] for k in service.COMMA_BASIS_FORM_KEYS},
    }


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
    baseline: object | None = None
    target_pred: Callable | None = None
    token: tuple | None = None
    reflowed: bool = False
    previous: _Gesture | None = None
