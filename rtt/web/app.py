"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.web.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

import json
import math
import sys
from html import escape as _escape
from pathlib import Path
from urllib.parse import quote

from nicegui import app, helpers, ui

from rtt.web import presets
from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.editor import Editor

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration
_PANEL_W = 330  # px width the settings drawer opens to (the Show + example columns)
_RAIL_W = 40  # px width of the permanent left rail (hamburger + the rotated app title)
_STORE_KEY = "rtt_doc"  # store key holding the serialized document (survives refresh)
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

# One weight and colour for every EBK bracket, brace and monzo rule. Each mark is
# drawn as an SVG whose viewBox maps 1:1 to the cell's px size (see _svg), so a
# stroke specified as N px is exactly N px tall AND wide at any span — no scaling.
_BR_COLOR = "#1a1a1a"
_PENDING_COLOR = "#e53935"  # red for a pending comma's draft cells, brackets and "?"
_SEAM = "#999"  # the thin grey rule separating the frozen title panes from the scrolling body
# the value cells tile into a shared-border grid (a ruled spreadsheet, per the
# mockup): each cell draws a rule and overlaps its neighbour by exactly the rule
# width, so two abutting borders coincide as ONE line — no doubled inner rules.
_CELL_BORDER_W = 1  # px
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {_BR_COLOR}"
_CELL_FONT = 17  # px for the single-digit values in the square cells (≈0.37 of the cell)
_BR_BAR = 2  # main bar / monzo-rule / square-bracket bar thickness (px)
_BR_SERIF_T = 0.9  # square + top bracket serif thickness — a thin foot, well under the bar
_BR_SERIF_L = 6  # square + top bracket serif length (how far the foot reaches) — also
# the shared footprint width every value bracket (square AND angle) draws within
_BR_INSET = 2.5  # gap from a bracket's open side to the value cells it hugs
# The ⟨ and the brace are filled ribbons of varying width (see _ribbon): a
# calligraphic pen lays a LONG stroke down THICK and a SHORT one THIN. The thin
# ends are kept delicate so the thick/thin taper reads clearly.
_BR_ANGLE_THICK = 1.1  # ⟨ half-width at the vertex (heavier)
_BR_ANGLE_THIN = 0.45  # ⟨ half-width at the open tips (much lighter) — a pronounced taper
_BR_BRACE_THICK = 1.15  # brace arm half-width: the long horizontal stroke is thick
_BR_BRACE_THIN = 0.4  # brace end-serif half-width: the short upturn is thin
_BR_BRACE_CUSP = 0.2  # brace central-cusp half-width: the short dip is a near point
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

_AUDIO_KINDS = {"speaker"}  # cells whose baked cents rebuild when the tuning changes
_AUDIO_CTRLS = {"audio_wave", "audio_mode", "audio_hold", "audio_root"}  # the per-tile bank controls


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
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(f) for f in _MODE_FILLS],
    "lock": ['<span class="material-icons rtt-audio-glyph">lock_open</span>',
             '<span class="material-icons rtt-audio-glyph">lock</span>'],
    "root": '<span class="rtt-audio-rootglyph">1/1</span>',
}

# The Web Audio engine. Each audio tile owns independent state (waveform, play-mode, hold/loop,
# include-1/1), keyed by tile id; the bank controls cycle it and redraw their glyph client-side,
# and a speaker calls rttAudio.hit(tile, idx, [cents…]) to sound per that state — all CLIENT-side
# (no server round-trip). 1/1 (root) sounds UNDERNEATH as a drone; playing notes' speakers
# highlight. freq = 261.626·2^(¢/1200) (1/1 = middle C). Modes (0..3): one-off, arpeggiate from
# the clicked note, chord, rolled chord; hold sustains (mode 0 stacks notes) or loops (2 & 4).
_AUDIO_JS = """
window.rttAudio = (function () {
  let ctx = null;
  const WAVES = ['sine', 'square', 'triangle', 'sawtooth'], BASE = 261.6255653005986, STEP = 0.34;
  const tiles = {};
  const api = { glyphs: null };
  function actx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function st(tile) {
    if (!tiles[tile]) tiles[tile] = { wave: 0, mode: 0, hold: false, root: false, stop: null, held: {} };
    return tiles[tile];
  }
  function spk(tile, idx) {
    return document.querySelector('.rtt-spk[data-audio="' + tile + '"][data-idx="' + idx + '"]');
  }
  function hl(tile, idx, on) { const e = spk(tile, idx); if (e) e.classList.toggle('rtt-spk-on', on); }
  function clearHl(tile) {
    const es = document.querySelectorAll('.rtt-spk[data-audio="' + tile + '"]');
    for (let i = 0; i < es.length; i++) es[i].classList.remove('rtt-spk-on');
  }
  function vgain(n) { return 0.45 / Math.max(1, n); }
  // start one oscillator; returns a release() that fades it out (and clears its highlight)
  function voice(tile, idx, cents, gain) {
    const ac = actx(), o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
    o.type = WAVES[st(tile).wave];
    o.frequency.value = BASE * Math.pow(2, cents / 1200);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
    o.connect(g); g.connect(ac.destination); o.start(t);
    if (idx >= 0) hl(tile, idx, true);
    let done = false;
    return function () {
      if (done) return; done = true;
      const r = actx().currentTime;
      g.gain.cancelScheduledValues(r);
      g.gain.setValueAtTime(Math.max(g.gain.value, 0.0001), r);
      g.gain.exponentialRampToValueAtTime(0.0001, r + 0.09);
      o.stop(r + 0.12);
      if (idx >= 0) setTimeout(function () { hl(tile, idx, false); }, 110);
    };
  }
  // sound a set of {idx,cents} together (+ optional root drone); returns a stop()
  function together(tile, items, root) {
    const g = vgain(items.length + (root ? 1 : 0)), rels = [];
    for (let i = 0; i < items.length; i++) rels.push(voice(tile, items[i].idx, items[i].cents, g));
    if (root) rels.push(voice(tile, -1, 0, g));
    return function () { for (let i = 0; i < rels.length; i++) rels[i](); };
  }
  // sequence `order` (indices) one per STEP. roll=true keeps notes ringing (rolled chord);
  // arp releases each before the next. loop repeats. root drones underneath. returns stop().
  function sequence(tile, order, cents, root, roll, loop) {
    const g = vgain(roll ? order.length + (root ? 1 : 0) : 2), timers = [];
    let rels = [], rootRel = root ? voice(tile, -1, 0, g) : null, stopped = false;
    function pass() {
      if (stopped) return;
      rels = [];
      for (let k = 0; k < order.length; k++) {
        timers.push(setTimeout(function (k) {
          if (stopped) return;
          const rel = voice(tile, order[k], cents[order[k]], g);
          rels.push(rel);
          if (!roll) setTimeout(rel, STEP * 1000 * 0.85);  // arp: release before the next note
          if (k === order.length - 1 && loop) {
            timers.push(setTimeout(function () {
              if (stopped) return;
              for (let i = 0; i < rels.length; i++) rels[i]();  // end the pass, then repeat
              pass();
            }, roll ? 520 : STEP * 1000));
          } else if (k === order.length - 1 && roll && !loop) {
            timers.push(setTimeout(function () { for (let i = 0; i < rels.length; i++) rels[i](); }, 900));
          }
        }.bind(null, k), k * STEP * 1000));
      }
    }
    pass();
    return function () {
      stopped = true;
      for (let i = 0; i < timers.length; i++) clearTimeout(timers[i]);
      for (let i = 0; i < rels.length; i++) rels[i]();
      if (rootRel) rootRel();
      clearHl(tile);
    };
  }
  function ctrlEl(tile, ctrl) {
    return document.querySelector('[data-actrl="' + ctrl + '"][data-audio="' + tile + '"]');
  }
  api.hit = function (tile, idx, cents) {
    const s = st(tile);
    if (s.mode === 0) {                                   // one-off / hold-stack
      if (!s.hold) { const stop = together(tile, [{ idx: idx, cents: cents[idx] }], s.root); setTimeout(stop, 650); return; }
      if (s.held[idx]) { s.held[idx](); delete s.held[idx]; }   // click a held note off
      else { s.held[idx] = together(tile, [{ idx: idx, cents: cents[idx] }], s.root); }
      return;
    }
    if (s.stop) { s.stop(); s.stop = null; if (s.hold) return; }  // hold/loop: a second click stops it
    if (s.mode === 1) {                                   // arpeggiate, from the clicked note, wrapping
      const order = []; for (let k = 0; k < cents.length; k++) order.push((idx + k) % cents.length);
      s.stop = sequence(tile, order, cents, s.root, false, s.hold);
      if (!s.hold) s.stop = null;
    } else if (s.mode === 2) {                            // chord: all together
      const items = []; for (let i = 0; i < cents.length; i++) items.push({ idx: i, cents: cents[i] });
      const stop = together(tile, items, s.root);
      if (s.hold) s.stop = stop; else setTimeout(stop, 1000);
    } else {                                              // rolled chord
      const order = []; for (let i = 0; i < cents.length; i++) order.push(i);
      s.stop = sequence(tile, order, cents, s.root, true, s.hold);
      if (!s.hold) s.stop = null;
    }
  };
  function stopAll(tile) { const s = st(tile); if (s.stop) { s.stop(); s.stop = null; }
    for (const k in s.held) s.held[k](); s.held = {}; clearHl(tile); }
  api.cycleWave = function (tile) { const s = st(tile); s.wave = (s.wave + 1) % 4;
    const e = ctrlEl(tile, 'wave'); if (e) e.innerHTML = api.glyphs.wave[s.wave]; };
  api.cycleMode = function (tile) { const s = st(tile); stopAll(tile); s.mode = (s.mode + 1) % 4;
    const e = ctrlEl(tile, 'mode'); if (e) e.innerHTML = api.glyphs.mode[s.mode]; };
  api.toggleHold = function (tile) { const s = st(tile); stopAll(tile); s.hold = !s.hold;
    const e = ctrlEl(tile, 'hold'); if (e) { e.innerHTML = api.glyphs.lock[s.hold ? 1 : 0]; e.classList.toggle('rtt-audio-on', s.hold); } };
  api.toggleRoot = function (tile) { const s = st(tile); s.root = !s.root;
    const e = ctrlEl(tile, 'root'); if (e) e.classList.toggle('rtt-audio-on', s.root); };
  return api;
})();
"""

# Frozen-pane support. The row band freezes by position:sticky (zero JS on its scroll path), but the
# column-title strip sits OUTSIDE the body scroller (so the vertical scrollbar can stop below it), so
# it can't ride the scroll via CSS — this listener translateX-syncs it to the body's horizontal
# scroll. It also reveals the seams: a frozen region is "stuck" (body scrolled under it) exactly when
# .rtt-gridbody has scrolled off zero on that axis, toggled as rtt-scrolled-x/y on .rtt-app. scroll
# doesn't bubble → capture phase, so the body's scroll events are still caught here.
_FREEZE_JS = """
window.rttFreeze = (function () {
  function update() {
    var bodies = document.querySelectorAll('.rtt-gridbody');
    for (var i = 0; i < bodies.length; i++) {
      var b = bodies[i], app = b.closest('.rtt-app');
      if (!app) continue;
      var inner = app.querySelector('.rtt-colhead-inner');
      if (inner) inner.style.transform = 'translateX(' + (-b.scrollLeft) + 'px)';
      app.classList.toggle('rtt-scrolled-y', b.scrollTop > 0);
      app.classList.toggle('rtt-scrolled-x', b.scrollLeft > 0);
    }
  }
  document.addEventListener('scroll', update, true);
  window.addEventListener('resize', update);
  var tries = 0;
  (function boot() { update(); if (++tries < 12) setTimeout(boot, 100); })();
  return { update: update };
})();
"""


def _option_box_svg(fill: str | None) -> str:
    """A data-URI SVG of the option-box indicator: an n×n white square with a 1px #555 border
    and, when ``fill`` is given, a centred inner square (inset by the 1px border + a 2px gap) of
    that colour. Used as the BACKGROUND of every q-checkbox box and the tuning-ranges radio box,
    so the whole mark scales as ONE vector — staying square with an even border at any zoom —
    instead of separate CSS box edges (border + inset fill), which the browser snaps independently
    to the device-pixel grid, distorting the square and the gap at fractional zooms / positions."""
    n = spreadsheet.OPTION_BOX_PX
    inner = f"<rect x='3' y='3' width='{n - 6}' height='{n - 6}' fill='{fill}'/>" if fill else ""
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {n} {n}'>"
           f"<rect x='.5' y='.5' width='{n - 1}' height='{n - 1}' fill='#fff' stroke='#555' stroke-width='1'/>"
           f"{inner}</svg>")
    return "data:image/svg+xml," + quote(svg)


_CSS = f"""
/* the grid's empty top-left corner cell now holds only the undo/redo buttons (the app
   title moved to the left rail). It fills the corner exactly — LABEL_W wide so its right
   edge meets the row-label column, HEADER_H tall so its bottom meets the column-header row
   — i.e. aligned with both the row titles and the column titles. Square (no radius), on the
   same light grey as the rail and pane; the buttons centre within it. It sits in the fixed
   .rtt-corner region (top-left of the frozen panes), positioned at the corner's origin. */
.rtt-titletile {{ position:absolute; top:0; left:0; box-sizing:border-box;
                 width:{spreadsheet.LABEL_W}px; height:{spreadsheet.HEADER_H}px; background:#e0e0e0;
                 display:flex; align-items:center; justify-content:center; }}
.rtt-tile-btns {{ display:flex; gap:3px; }}
/* square bordered icon buttons (undo/redo), matching the mockup's framed glyphs */
.rtt-iconbtn {{ width:18px !important; min-width:18px !important; height:18px !important;
            min-height:18px !important; padding:0 !important; background:#fff !important;
            border:1px solid #000; border-radius:2px !important; box-shadow:none !important; }}
.rtt-iconbtn .q-icon {{ color:#000 !important; font-size:13px; }}
/* a disabled undo/redo button greys out like the disabled Show toggles. NiceGUI marks a
   set_enabled(False) button with the generic `.disabled` class (NOT Quasar's
   q-btn--disable), so target that: grey the icon AND border to #999/#bbb, well off the
   crisp black of an active button — so against Quasar's own disabled fade the button
   reads unmistakably inactive, matching the #999 of a disabled toggle. */
.rtt-iconbtn.disabled {{ border-color:#bbb !important; }}
.rtt-iconbtn.disabled .q-icon {{ color:#999 !important; }}
/* Quasar's reset gives EVERY disabled control -- `.disabled`/`[disabled]` and their
   descendants -- a `not-allowed` cursor (the slashed "no-entry" circle on hover). This app
   never wants it: a greyed button or checkbox already reads as inactive from its dim, so the
   slashed circle is just noise. Neutralise the cursor app-wide (the dim STAYS -- that's the
   real disabled cue). Quasar's rule is `cursor:not-allowed !important` in its
   `quasar_importants` cascade layer; because !important REVERSES layer precedence, a layered
   !important in the earlier `overrides` layer beats it regardless of specificity (an unlayered
   !important would lose). The dropdown-header undim below rides the same trick. */
@layer overrides {{
  .disabled, .disabled *, [disabled], [disabled] * {{ cursor:default !important; }}
}}
/* the left rail: a light-grey column at the screen's left edge holding the hamburger (top)
   and, under it, the app title turned a quarter-turn. It sits to the LEFT of the pane and
   stays #e0e0e0 whether the pane is open or closed, so opening the pane never moves the
   title. It carries no align-self, so the pane group (align-items:stretch) makes it as tall
   as the group — and the group hugs the drawer (below), so the rail matches the settings
   panel's height: a short title tab when the pane is collapsed, the full panel height when
   it is open, regardless of how much taller the grid beside it runs. */
.rtt-rail {{ flex:none; width:{_RAIL_W}px; background:#e0e0e0;
            display:flex; flex-direction:column; align-items:center; gap:10px; padding:7px 0 14px; }}
/* the app title, turned a quarter-turn (writing-mode) so it reads top-to-bottom down the
   rail. Noticeably larger than the 13px row/column titles, yet narrow enough to fit the rail. */
.rtt-sidetitle {{ writing-mode:vertical-rl; font-family:'Cambria',Georgia,serif; font-size:22px;
                 font-weight:bold; color:#000; white-space:nowrap; line-height:1; }}
/* the hamburger, parked at the top of the rail */
.rtt-hamburger {{ width:28px !important; min-width:28px !important; height:28px !important;
                 min-height:28px !important; padding:0 !important; background:#fff !important;
                 border:1px solid #999; border-radius:3px !important; box-shadow:none !important; }}
.rtt-hamburger .q-icon {{ color:#333 !important; font-size:19px; }}
/* the shell lays the fixed left sidebar (rail + settings pane) and the grid pane in a row. It is
   position:fixed at a 6px inset from every window edge, so it fills the window exactly (the page
   itself never scrolls) and the 6px of white body shows as a margin framing the whole app. The
   grid spills inside its OWN pane (.rtt-app) rather than off the page, which keeps the sidebar
   frozen at the left. align-items:flex-start lets each pane HUG its content height (white showing
   below the shorter one) rather than stretching its grey to the full window; the shell's fixed
   size is what each pane caps against (max-height / flex-shrink) before scrolling internally. */
.rtt-shell {{ position:fixed; top:6px; left:6px; right:6px; bottom:6px;
             display:flex; flex-wrap:nowrap; gap:0; align-items:flex-start; }}
/* the rail+pane group is the fixed left sidebar: a flex:none column the shell holds at the left
   edge for the whole session. align-self defaults to the shell's align-items:flex-start, so the
   sidebar HUGS its content — the rail's title tab when the drawer is collapsed, the settings panel's
   height when open — rather than stretching its grey down the whole window. The page no longer
   scrolls, so it needs no position:sticky; it stays put while the grid pane to its right scrolls.
   Opening the drawer widens it, narrowing the grid pane (which reflows). */
.rtt-panelgroup {{ display:flex; flex-wrap:nowrap; flex:none; }}
/* the drawer animates BOTH width (the slide-over) and height (grid-template-rows 0fr->1fr, growing
   the pane to its content height) so the sidebar's grey hugs the settings rather than the window.
   align-self:flex-start stops the panelgroup stretching it (which would defeat the content-fr
   sizing); a collapsed 0fr drawer contributes no height, so the sidebar falls to the rail's tab. */
.rtt-drawer {{ display:grid; grid-template-rows:0fr; align-self:flex-start; width:0; overflow:hidden;
              transition:width {_T}, grid-template-rows {_T}; flex:none; }}
.rtt-drawer.rtt-drawer-open {{ width:{_PANEL_W}px; grid-template-rows:1fr; }}
/* the pane is a flex column: a frozen header (select-all/none + show/example) over a scrolling body
   (the toggle groups), mirroring the grid pane's frozen titles above its scrolling body. It hugs its
   content; the window-height cap lives on the body (.rtt-show-scroll's max-height) so the frozen
   header + a body capped to (window − inset − header) never exceeds the window. overflow:hidden lets
   the drawer's grid-rows open/close animation clip and grow it. */
.rtt-drawer-inner {{ width:{_PANEL_W}px; box-sizing:border-box; background:#e0e0e0; overflow:hidden;
                    min-height:0; display:flex; flex-direction:column;
                    font-family:'Cambria',Georgia,serif; color:#000; }}
/* the grid pane sits right of the sidebar. It HUGS the grid (render() sizes it to the grid's full
   footprint + a _PAD margin on every side, plus the last column title's right overhang) so its grey
   backdrop frames the grid all round — white shows beyond it — rather than stretching into empty
   space. flex:0 1 auto + max-width:100% let it shrink to the room left of the sidebar, and
   max-height:100% caps it at the window; past either cap the body (.rtt-gridbody) scrolls. It is
   the positioning context for the frozen column strip, corner and body scroller (absolutely placed,
   so render() must size it explicitly); overflow:hidden clips them to the pane. */
.rtt-app {{ flex:0 1 auto; min-width:0; max-width:100%; max-height:100%; position:relative;
           overflow:hidden; background:#c0c0c0; font-family:'Cambria',Georgia,serif; }}

/* The grid pane is split so the body's scrollbars stop AT the frozen titles (like the settings
   pane): the column-title strip (.rtt-colhead) and the corner sit OUTSIDE the body scroller
   (.rtt-gridbody), which holds only the value cells + the sticky-left row band. So the body's
   vertical scrollbar starts BELOW the column titles, and its horizontal scrollbar spans only the
   body — neither runs up alongside a frozen title. The strip can't ride the body's scroll via CSS
   (a left-frozen sticky row band needs the body itself to be the horizontal scroll container), so
   _FREEZE_JS translateX-syncs the strip to the body's horizontal scroll. The frozen regions are inset
   _PAD from the pane's top-left — that is the TOP and LEFT grey margin (outside the scroller, always
   shown). The body fills to the pane's right/bottom EDGES, so its scrollbars sit flush there (no grey
   stranded outside them); the RIGHT and BOTTOM margin is the body's own padding (padding:0 _PAD _PAD
   0), which rides INSIDE the scroller so it shows past the last gridline even scrolled to the end —
   sizing the pane larger would only show it until the board overflows. The board (.rtt-gridcontent)
   holds the cells at native coords shifted up by freeze_y (the strip's height), so a body cell lands
   at the same pane position it always had. */
.rtt-colhead {{ position:absolute; top:{_PAD}px; left:{_PAD}px; right:0; z-index:4; overflow:hidden;
               background:#c0c0c0; box-sizing:border-box; border-bottom:1px solid transparent; }}
.rtt-colhead-inner {{ position:absolute; top:0; left:0; will-change:transform; }}
.rtt-corner {{ position:absolute; top:{_PAD}px; left:{_PAD}px; z-index:6; background:#c0c0c0;
              box-sizing:border-box; border-right:1px solid transparent; border-bottom:1px solid transparent; }}
.rtt-gridbody {{ position:absolute; left:{_PAD}px; right:0; bottom:0; overflow:auto;
                padding:0 {_PAD}px {_PAD}px 0; }}
/* isolate the board so the washes' mix-blend-mode composes only with the board's own layers
   (the white wash bases), not the grey pane behind it */
.rtt-gridcontent {{ position:relative; isolation:isolate; transition:width {_T}, height {_T}; }}
.rtt-band {{ position:absolute; inset:0; pointer-events:none; }}
.rtt-rowband {{ position:sticky; left:0; z-index:5; background:#c0c0c0; box-sizing:border-box;
               pointer-events:auto; border-right:1px solid transparent; }}
/* the seam on each frozen region's body-facing edge stays transparent until the body is scrolled
   on that axis (classes toggled on .rtt-app in _FREEZE_JS); the border is always 1px so revealing
   it shifts nothing */
.rtt-app.rtt-scrolled-y .rtt-colhead, .rtt-app.rtt-scrolled-y .rtt-corner {{ border-bottom-color:{_SEAM}; }}
.rtt-app.rtt-scrolled-x .rtt-rowband, .rtt-app.rtt-scrolled-x .rtt-corner {{ border-right-color:{_SEAM}; }}
@keyframes rtt-in {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.rtt-line, .rtt-block, .rtt-block-boxed, .rtt-cell, .rtt-wash, .rtt-washbase {{ animation:rtt-in {_T} ease; }}

.rtt-line {{ position:absolute; z-index:1; opacity:1; transition:left {_T}, top {_T},
            width {_T}, height {_T}, opacity {_T}; }}
.rtt-line-v {{ border-left:{spreadsheet.LINE_W}px solid #e0e0e0; width:0; }}
.rtt-line-h {{ border-top:{spreadsheet.LINE_W}px solid #e0e0e0; height:0; }}
/* a colorization wash: a colour band behind the grey tiles (below the gridlines too)
   filling a colorized group's row/column background. Each group's band has a white
   base on a LOWER layer (z-index:-1) than its darken colour layer (z-index:0), so the
   opaque bases can never cover another group's colour — wherever two colour bands
   cross, the darken min's them over white into the mockup's blend (cyan ⊓ yellow =
   green), independent of which group was toggled on first. */
.rtt-washbase, .rtt-wash {{ position:absolute; opacity:1;
            transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-washbase {{ z-index:-1; background:#fff; }}
.rtt-wash {{ z-index:0; mix-blend-mode:darken; }}
.rtt-block {{ position:absolute; z-index:2; background:#e0e0e0; opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
/* the nested tuning-ranges box: a thin-bordered frame on the generator tuning map tile
   (per the mockup), above the grey tile but below the chart/selector cells */
.rtt-block-boxed {{ position:absolute; z-index:2; background:#e8e8e8; border:1px solid #8a8a8a;
             opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-cell {{ position:absolute; z-index:3; display:flex; align-items:center; justify-content:center;
            opacity:1; transition:left {_T}, top {_T}, opacity {_T}; }}
.rtt-white {{ position:absolute; top:0; left:0;
             width:calc(100% + {_CELL_BORDER_W}px); height:calc(100% + {_CELL_BORDER_W}px);
             box-sizing:border-box; display:flex; align-items:center; justify-content:center;
             background:#fff; border:{_CELL_BORDER}; color:#000; font-size:{_CELL_FONT}px; }}
/* titles carry explicit "\n" breaks (col_header) so a multi-word header stacks to two
   lines (e.g. "domain" / "primes"); `pre` honors them AND never auto-wraps, so a title
   wider than its (content-hugging) column overflows it rather than rewrapping. It is
   absolutely centred on the cell (= the column gridline) so that overflow spills EVENLY
   to both sides — a balanced overhang into the gaps, not clamped against one neighbour the
   way a flow-positioned flex child is. Tight line-height keeps the stacked lines close. */
.rtt-colheader {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
                 font-size:13px; font-weight:bold; color:#000; white-space:pre;
                 text-align:center; line-height:1.1; }}
.rtt-rowlabel {{ font-size:13px; font-weight:bold; color:#000; width:100%; text-align:right;
                padding-right:8px; line-height:1.1; }}
.rtt-val {{ font-size:{_CELL_FONT}px; color:#000; }}
/* the in-tile quantity name: small (≈0.2 of the cell, per the mockup), capped at two
   lines (the column is widened to fit) and balanced across them by text-wrap:balance —
   an even split, not a long first line and a single trailing word. It centres in the
   row's caption band (the cell is the band's full height), so a one-line name sits
   half a line below a two-line sibling's top rather than hugging the cells. */
.rtt-caption {{ width:100%; text-align:center; text-wrap:balance; font-size:9px; line-height:10px;
               color:#333; overflow-wrap:break-word; font-family:'Cambria',Georgia,serif; }}
.rtt-caption-cell {{ align-items:center; }}
/* the optimization box's symbols (⟪𝐝⟫ₚ, 𝑝) and captions ("optimization power", "double-click
   to lock") stay on ONE line — centred under their control, overflowing sideways if need be —
   so ⟪𝐝⟫ₚ never wraps its ₚ to a second line (which also pushed ⟪𝐝⟫ up into the value row) */
.rtt-opt-1line {{ white-space:nowrap; overflow-wrap:normal; text-wrap:nowrap; }}
/* a left-justified caption sits flush against its left edge (the dropdown it labels), free
   to overhang to the right on one line rather than wrapping (e.g. "predefined prescalers").
   The small left inset aligns the caption's first character vertically with the dropdown's
   inner text (which sits a few px from the dropdown's border, per q-field padding); the
   2px top inset nudges it down off the dropdown's bottom border. */
.rtt-caption-left {{ text-align:left !important; white-space:nowrap; overflow:visible;
                    text-wrap:nowrap; padding:2px 0 0 6px; }}
.rtt-caption-cell:has(> .rtt-caption-left) {{ align-items:flex-start; overflow:visible; }}
/* most mnemonic underlines sit snug at the baseline; only a marked descender
   (g/j/p/q/y — e.g. the j of "just tuning map") drops its underline below the tail
   so it reads instead of hiding under the glyph */
.rtt-caption u.rtt-desc {{ text-underline-position:under; }}
.rtt-count {{ font-size:16px; color:#000; white-space:nowrap; }}
/* a read-only plain-text value: serif text on ONE line, no box. Its font-size is set
   inline per box (shrunk to fit its column), so a long value never wraps or spills. */
.rtt-ptext {{ width:100%; text-align:center; color:#000; white-space:nowrap; line-height:1;
             font-family:'Cambria',Georgia,serif; }}
/* the two editable duals (mapping, comma basis): a white bordered input filling its
   cell; an unparseable entry turns the border red (rtt-ptext-error) and is not applied.
   Its font-size is set inline per box too, so the value stays on one line. */
.rtt-ptextedit {{ width:100%; height:100%; }}
.rtt-ptextedit .q-field__control {{ min-height:0 !important; height:100%;
            background:#fff; border:1px solid #888; border-radius:2px; padding:0 3px; }}
.rtt-ptextedit .q-field__control::before, .rtt-ptextedit .q-field__control::after {{ display:none !important; }}
.rtt-ptextedit .q-field__native {{ color:#000; min-height:0 !important; padding:0; text-align:center;
            line-height:{spreadsheet.PTEXT_EDIT_H}px; white-space:nowrap; font-size:inherit !important;
            font-family:'Cambria',Georgia,serif; }}
.rtt-ptextedit .q-field__marginal, .rtt-ptextedit .q-field__bottom {{ display:none !important; }}
.rtt-ptextedit.rtt-ptext-error .q-field__control {{ border-color:#d33; }}
/* the quantity symbol above the caption: _math_html renders the base letter in the
   UI serif with explicit weight/slant (bold-italic for maps, bold-upright for
   vectors/matrices) — not a maths-font glyph, whose styling font fallback dropped */
.rtt-symbol {{ width:100%; text-align:center; font-size:15px; color:#000; line-height:1;
              font-family:'Cambria',Georgia,serif; }}
/* the per-row / per-column matrix label (𝒎ᵢ at the left of each mapping row, 𝐜ᵢ
   above each comma, 𝒕ᵢ above each tuned prime, …): same _math_html serif as .rtt-symbol
   but smaller, so the subscript reads at a glance without dominating the value below */
.rtt-matlabel {{ width:100%; text-align:center; font-size:11px; color:#000; line-height:1;
              font-family:'Cambria',Georgia,serif; white-space:nowrap; }}
/* the complexity row's column labels spell out the q-norm (‖L𝐜ᵢ‖q), which is much
   wider than a plain subscripted letter. Drop the font size so the labels don't
   collide and let them overflow the COL_W cell width without clipping (overflow:visible). */
.rtt-matlabel-norm {{ font-size:8px; overflow:visible; }}
.rtt-matlabel sub {{ font-size:70%; vertical-align:sub; line-height:0; }}
/* the per-box "units: …" line below the caption, and the domain-units row/col labels.
   The unit VALUE is set in a single-story-g sans face (the mockup's distinct unit style):
   Corbel (the ClearType sans companion to the body Cambria) has a single-story g —
   Cambria, Calibri, Verdana, Segoe UI all draw a double-story g, so they're excluded.
   The per-box "units:" label keeps the serif body face via .rtt-units-pre. */
.rtt-units {{ width:100%; text-align:center; font-size:10px; color:#333; line-height:1;
            white-space:nowrap; font-family:'Corbel','Candara','Trebuchet MS',sans-serif; }}
.rtt-units-pre {{ font-family:'Cambria',Georgia,serif; }}
/* the per-value unit (the `units` toggle): a tiny line in the same single-story-g sans,
   stacked right beneath the value so the value + unit read as one centred pair — like the
   cents int-over-fraction stack, the unit hugging its value rather than floating away. */
.rtt-cellunit {{ font-size:6px; line-height:1; color:#555; white-space:nowrap; text-align:center;
            font-family:'Corbel','Candara','Trebuchet MS',sans-serif; }}
/* a read-only value cell simply stacks [value, unit] in a centred column; the value's
   line-height is tightened so the value + unit pair fits the square and stays centred */
.rtt-cell-united:not(.rtt-cell-input) {{ flex-direction:column; line-height:1; }}
.rtt-cell-united:not(.rtt-cell-input) .rtt-val {{ line-height:1; }}
/* an editable value cell keeps its full-size white input box (border stays on the input)
   and overlays the unit INSIDE it, with the number nudged up to clear the unit */
.rtt-cell-united.rtt-cell-input .rtt-cellunit {{ position:absolute; left:0; right:0; bottom:2.5px;
            pointer-events:none; z-index:1; }}
.rtt-cell-united.rtt-cell-input .rtt-cellinput .q-field__native {{ padding-bottom:11px !important; }}
/* every EBK mark (⟨ ] [, top bracket, brace, monzo rule) is one SVG that fills
   its cell at a 1:1 viewBox, so its strokes keep a constant px weight at any span */
.rtt-svgfill {{ width:100%; height:100%; line-height:0; }}
/* the symbol + caption (and the units line) hold off their fade-in until the tile has expanded */
.rtt-caption-cell, .rtt-symbol-cell, .rtt-units-cell, .rtt-matlabel-cell {{ animation-delay:{_T}; animation-fill-mode:backwards; }}
/* the preselect chooser dropdowns: a compact bordered q-select that fills its
   PRESELECT_H cell, with a thin grey rule and a small caret — like the mockup */
.rtt-preselect {{ width:100%; }}
.rtt-preselect .q-field__control {{ min-height:0 !important; height:30px;
            background:#fff; border:1px solid #999; border-radius:2px; padding:0 2px 0 6px; }}
.rtt-preselect .q-field__control::before, .rtt-preselect .q-field__control::after {{ display:none !important; }}
.rtt-preselect .q-field__native, .rtt-preselect .q-field__input {{ font-size:12px; color:#000;
            min-height:0 !important; padding:0; line-height:30px; font-family:'Cambria',Georgia,serif; }}
.rtt-preselect .q-field__marginal, .rtt-preselect .q-field__append {{ height:30px; min-height:0 !important; }}
.rtt-preselect .q-icon {{ font-size:16px; color:#555; }}
.rtt-control-check {{ width:100%; height:100%; display:flex; justify-content:center;
            align-items:center; }}  /* visually centres the q-checkbox inside its cell wrap */
/* Universal checkbox look AND size — every q-checkbox in the app (settings panel, the box-𝐋
   diminuator, the target-controls all-interval check, anywhere else) renders as ONE uniform
   square pinned to OPTION_BOX_PX: __inner sets the box model, __bg carries the mark. The mark —
   a white square with a 1px #555 border, plus a centred inner fill when checked — is drawn as a
   single SVG BACKGROUND image (see _option_box_svg), NOT a CSS border + inset ::after fill. A CSS
   border and a separately-positioned fill snap to the device-pixel grid INDEPENDENTLY, so at
   fractional zooms / sub-pixel box positions the border thickness and gap drift and the fill stops
   looking square; one SVG scales as a coherent vector, staying square with an even border at every
   zoom. Sizes are pinned !important to override Quasar's dense/size scaling so every box matches;
   Quasar's own checkmark SVG and ::before ripple are neutralised. */
.q-checkbox__inner {{ width:{spreadsheet.OPTION_BOX_PX}px !important;
            min-width:{spreadsheet.OPTION_BOX_PX}px !important; height:{spreadsheet.OPTION_BOX_PX}px !important; }}
.q-checkbox__bg {{ top:0 !important; left:0 !important; width:{spreadsheet.OPTION_BOX_PX}px !important;
            height:{spreadsheet.OPTION_BOX_PX}px !important; box-sizing:border-box !important;
            border:none !important; border-radius:0 !important; opacity:1 !important;
            background-color:transparent !important; background-repeat:no-repeat !important;
            background-position:center !important; background-size:100% 100% !important;
            background-image:url("{_option_box_svg(None)}") !important; }}
.q-checkbox__bg::before {{ background:transparent !important; border-radius:0 !important; }}
.q-checkbox__svg {{ display:none !important; }}
/* checked: swap in the SVG that carries the black inner fill (two selectors — Quasar's truthy
   class + the standard aria-checked attribute — so it fires regardless of Quasar version). */
.q-checkbox__inner--truthy .q-checkbox__bg,
.q-checkbox[aria-checked="true"] .q-checkbox__bg {{
            background-image:url("{_option_box_svg('#000')}") !important; }}
/* MIXED state for the select-all/none master (some-but-not-all targets on): a GREY inner fill for
   the indeterminate third state, via the .rtt-show-mixed class toggled in render(). */
.rtt-show-mixed .q-checkbox__bg {{
            background-image:url("{_option_box_svg('#888')}") !important; }}
/* each chooser's dropdown popup matches the field's Cambria text, with compact items */
.rtt-select-popup {{ font-family:'Cambria',Georgia,serif; }}
/* compact items; the popup grows to max-content (see _select_props), widening past
   the field so a long name (e.g. a systematic tuning) shows on one line */
.rtt-select-popup .q-item {{ min-height:22px; padding:1px 8px; font-size:11px; }}
.rtt-select-popup .q-item__label {{ font-size:11px; white-space:normal;
              font-family:'Cambria',Georgia,serif; }}
/* greyscale the selection (no Quasar primary blue): the chosen item keeps a steady
   light-grey wash so it stays visible, lighter than the darker grey hover/keyboard
   highlight (the focus-helper, at Quasar's own hover/focus opacity) */
.rtt-select-popup .q-item--active {{ color:#000 !important; background:#ededed; }}
.rtt-select-popup .q-focus-helper {{ background:#000 !important; }}
/* the prime-limit divider rows are disabled (non-selectable): Quasar renders a disabled
   q-item with no focus-helper (so no hover highlight) and skips it on click, so it can't be
   picked and a click leaves the popup open. But Quasar's reset also DIMS a disabled item
   (opacity .6), unwanted on what is really a header — so undim it back to full opacity.
   (Its not-allowed cursor is already cleared app-wide above, in this same `overrides` layer
   — see that block for the !important-layer-reversal that lets the override win.) */
@layer overrides {{
  .rtt-select-popup .q-item.disabled {{ opacity:1 !important; }}
}}
/* ...and the divider reads as a section header: a centred grey label flanked by rules. It
   keeps the items' horizontal padding (it does NOT run to the popup's literal edges), so the
   rules stop the same 8px in from each edge as the item text. The label flex-centres its text
   with the lines as its ::before/::after (flex:1, filling the inset space on either side).
   Grey (#777), lighter than the items' black. Normal (unlayered) declarations — they win on
   specificity, and unlayered beats Quasar's lower layers (the !important reversal above is only
   for the dimming reset). */
.rtt-select-popup .q-item.disabled .q-item__label {{ display:flex; align-items:center;
            justify-content:center; gap:6px; white-space:nowrap; color:#777; }}
.rtt-select-popup .q-item.disabled .q-item__label::before,
.rtt-select-popup .q-item.disabled .q-item__label::after {{ content:""; flex:1;
            border-top:1px solid #777; }}
/* the target chooser pairs a SQUARE numeric limit override with the TILT/OLD family select */
.rtt-preselect-target {{ width:100%; height:30px; display:flex; gap:0; align-items:center; }}
.rtt-preselect-target .rtt-preselect-num {{ flex:0 0 30px; }}  /* a gridded value square (COL_W x ROW_H), touching the select */
.rtt-preselect-target .rtt-preselect {{ flex:1 1 auto; width:auto; }}
.rtt-preselect-num .q-field__control {{ min-height:0 !important; height:30px;
            background:#fff; border:1px solid #999; border-radius:2px; padding:0 2px; }}
.rtt-preselect-num .q-field__control::before, .rtt-preselect-num .q-field__control::after {{ display:none !important; }}
.rtt-preselect-num .q-field__native {{ font-size:{_CELL_FONT}px; color:#000; min-height:0 !important; padding:0;
            line-height:30px; text-align:center; font-family:'Cambria',Georgia,serif; }}
.rtt-preselect-num .q-field__native::-webkit-inner-spin-button {{ -webkit-appearance:none; margin:0; }}
.rtt-preselect-num .q-field__marginal, .rtt-preselect-num .q-field__append {{ display:none !important; }}
/* the monotone/tradeoff range selector under the ranges chart: two square indicators
   stacked vertically (filled = selected), per the mockup, with small Cambria labels.
   Vertical stack because the bumped 16px boxes don't fit side by side. Each row is
   LEFT-aligned (align-items:flex-start) so the two boxes line up at the same x, with
   their labels extending to the right — the labels have different widths and would look
   awkward if the boxes were centred and so didn't align vertically. */
.rtt-rangemode {{ width:100%; display:flex; flex-direction:column; align-items:flex-start;
                  justify-content:center; gap:3px; line-height:1; overflow:hidden;
                  padding:5px 5px 5px 10px; }}  /* top/bottom 5 so the bottom row doesn't touch the box edge */
.rtt-rangeopt {{ display:flex; align-items:center; gap:4px; cursor:pointer; user-select:none; }}
.rtt-rangebox {{ width:{spreadsheet.OPTION_BOX_PX}px; height:{spreadsheet.OPTION_BOX_PX}px; flex:none;
                box-sizing:border-box; background-repeat:no-repeat; background-size:100% 100%;
                background-image:url("{_option_box_svg(None)}"); }}
/* selected = a square "radio": the SAME SVG art with a centred black inner square (a radio dot,
   but square) — one vector, so it stays square with an even border at any zoom (see _option_box_svg) */
.rtt-rangeopt-on .rtt-rangebox {{ background-image:url("{_option_box_svg('#000')}"); }}
.rtt-rangelabel {{ font-family:'Cambria',Georgia,serif; font-size:10px; color:#000; white-space:nowrap; }}
.rtt-ratio {{ display:flex; align-items:center; justify-content:center; gap:1px;
             font-size:13px; color:#000; }}
.rtt-approx {{ font-size:13px; align-self:center; }}
.rtt-frac {{ display:inline-flex; flex-direction:column; align-items:center; line-height:1.04; }}
.rtt-frac-num {{ border-bottom:1px solid #000; padding:0 3px; }}
.rtt-frac-den {{ padding:0 3px; }}
.rtt-tval {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
            width:100%; color:#000; white-space:nowrap; line-height:1.05; }}
.rtt-cents-int {{ font-size:10px; }}
.rtt-cents-frac {{ font-size:7px; color:#000; }}
/* an editable cents cell (the generator tuning map 𝒈, the bare prescaler 𝐋 diagonal): a
   single-line input overflows the square with a 3-dp value, so it carries the SAME stacked
   int-over-fraction face as a read-only cents cell, overlaid on top of the input. The face
   ignores pointer events (a click falls through and focuses the input); focusing the cell
   then swaps to the raw single-line text for editing and hides the face. */
.rtt-cellface {{ position:absolute; top:0; left:0; width:100%; height:100%;
            pointer-events:none; z-index:1; }}
.rtt-cell-stacked .rtt-cellinput .q-field__native {{ color:transparent; font-size:10px; }}
.rtt-cell-stacked:focus-within .rtt-cellinput .q-field__native {{ color:#000; }}
.rtt-cell-stacked:focus-within .rtt-cellface {{ display:none; }}
/* with the per-cell unit on, lift the face's centred value to clear the unit pinned at the
   cell's bottom (a read-only cents cell stacks value-over-unit; this overlay pads instead) */
.rtt-cell-united.rtt-cell-stacked .rtt-cellface {{ padding-bottom:9px; }}
/* a just value's closed form, stacked as "1200 · log₂(3/2)" over "= 701.96"; each
   line's font is scaled (inline) to fit the narrow value square, so it never overflows.
   No fixed height (like .rtt-tval): the cell centres it, and when a per-cell unit is
   added the value+unit hug as one pair — height:100% would float the unit to the bottom. */
.rtt-mathexpr {{ width:100%; display:flex; align-items:center; justify-content:center; }}
.rtt-mathexpr-stack {{ display:flex; flex-direction:column; align-items:center; justify-content:center;
                      line-height:1.15; color:#000; white-space:nowrap; }}
.rtt-cellinput {{ width:100% !important; height:100%; min-height:0; overflow:visible; }}
.rtt-cellinput .q-field__inner {{ overflow:visible; }}
.rtt-cellinput .q-field__control {{ position:absolute !important; top:0; left:0;
            width:calc(100% + {_CELL_BORDER_W}px) !important; height:calc(100% + {_CELL_BORDER_W}px) !important;
            max-width:none !important; min-height:0 !important;
            box-sizing:border-box; padding:0 !important; background:#fff; border:{_CELL_BORDER}; }}
.rtt-cellinput .q-field__control::before, .rtt-cellinput .q-field__control::after {{ display:none !important; }}
.rtt-cellinput .q-field__native {{ text-align:center; padding:0 !important; color:#000; font-size:{_CELL_FONT}px;
            min-height:0; font-family:'Cambria',Georgia,serif; }}
.rtt-cellinput .q-field__bottom, .rtt-cellinput .q-field__marginal {{ display:none !important; }}
/* a pending comma's draft cells: red-outlined and empty until the user types a valid
   independent comma, at which point it commits and reverts to a normal black cell. The
   typed entries are red too, matching the brackets, the "?" quantity, and the plain text */
.rtt-cellinput.rtt-pending .q-field__control {{ border-color:{_PENDING_COLOR} !important; }}
.rtt-cellinput.rtt-pending .q-field__native {{ color:{_PENDING_COLOR} !important; }}
/* a pending comma's "?" quantity (and the draft vector in the plain text), in the same
   red as its draft cells/brackets */
.rtt-pending-q {{ color:{_PENDING_COLOR} !important; }}
/* the comma basis plain text while a comma is pending: not an editable input (which is
   one colour) but a static box matching the input's frame, holding the committed commas
   in black and the red draft vector — you edit the draft in the red grid cells */
.rtt-ptextpending {{ width:100%; height:100%; box-sizing:border-box; display:flex;
            align-items:center; justify-content:center; background:#fff; border:1px solid #888;
            border-radius:2px; padding:0 3px; color:#000; white-space:nowrap; overflow:hidden;
            font-family:'Cambria',Georgia,serif; }}
/* the +/− controls are half the square mapping/prime cell, sharing its exact border */
.rtt-btn {{ width:15px !important; min-width:15px !important; height:15px !important;
           min-height:15px !important; background:#fff !important; border:{_CELL_BORDER} !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }}
/* center the glyph: Quasar's content box defaults to a tall line-height that
   overflowed the small square; pin it to the box so the flex centering can take over */
.rtt-btn .q-btn__content {{ color:#000 !important; font-size:13px; line-height:1; min-height:0;
           font-family:'Cambria',Georgia,serif; }}
/* the optimize button fills its cell (a normal rectangle hugging the word); its text is the
   same size as the optimization power number (the ∞ box, _CELL_FONT). It's a 3D button: a
   light-top/dark-bottom face with a crisp inset bevel (white highlight top-left, soft shadow
   bottom-right) just inside the black cell border, so it reads as raised off the row. Pressing
   it (:active) or latching it (.rtt-optimize-locked, the double-click auto-optimize lock)
   inverts the shading — the face flips dark-top/light-bottom, the bevel becomes an inset
   shadow, and the label nudges down-right — so a held click and a locked latch both look
   pushed in. Hover/active are scoped :not(-locked) so the latched look stays put under either. */
.rtt-optimize {{ width:100% !important; min-width:0 !important; height:100% !important;
            background:linear-gradient(#fafafa,#cfcfcf) !important;
            box-shadow:inset 1px 1px 0 #fff, inset -1px -1px 1px rgba(0,0,0,0.30) !important;
            transition:background .06s linear, box-shadow .06s linear !important; }}
.rtt-optimize .q-btn__content {{ font-size:{_CELL_FONT}px;
            transition:transform .06s linear; }}
.rtt-optimize:hover:not(.rtt-optimize-locked) {{ background:linear-gradient(#fff,#dadada) !important; }}
.rtt-optimize:active:not(.rtt-optimize-locked) {{ background:linear-gradient(#c2c2c2,#e6e6e6) !important;
            box-shadow:inset 1px 1px 2px rgba(0,0,0,0.38), inset -1px -1px 0 rgba(255,255,255,0.65) !important; }}
.rtt-optimize:active:not(.rtt-optimize-locked) .q-btn__content {{ transform:translate(1px,1px); }}
.rtt-optimize-locked {{ background:linear-gradient(#1f1f1f,#3c3c3c) !important;
            box-shadow:inset 1px 1px 3px rgba(0,0,0,0.75), inset -1px -1px 0 rgba(255,255,255,0.18) !important; }}
.rtt-optimize-locked .q-btn__content {{ color:#fff !important; transform:translate(1px,1px); }}
/* an in-tile box title (the optimization box's "optimization" header, and every titled
   control box): left-aligned at the top-left of the box (its cell otherwise centres it),
   padded off the left border. One line that overhangs to the right rather than wrapping —
   the box is sized to seat it, so it never clips. */
.rtt-boxtitle {{ font-family:'Cambria',Georgia,serif; font-size:11px; font-weight:bold;
                 color:#000; width:100%; text-align:left; padding-left:8px;
                 white-space:nowrap; overflow:visible; }}
/* the audio rows' speaker buttons (one per pitch). Flat and transparent so the cyan/green
   wash shows through; the icon fills the (square) cell. .rtt-spk-on highlights it while sounding. */
.rtt-audio-btn {{ width:100% !important; height:100% !important; min-width:0 !important;
           min-height:0 !important; padding:0 !important; box-shadow:none !important;
           background:transparent !important; color:#444 !important; }}
.rtt-audio-btn .q-btn__content {{ min-height:0; padding:0; }}
.rtt-audio-btn .q-icon, .rtt-audio-btn .material-icons {{ font-size:15px; color:#444 !important; }}
.rtt-spk-on .q-icon, .rtt-spk-on .material-icons {{ color:#000 !important; }}
.rtt-spk-on {{ background:#bdbdbd !important; border-radius:3px; }}
/* a per-tile bank control square (waveform / play-mode / hold-loop / include-1/1), the same
   12px box as the fold toggle; .rtt-audio-on marks the active hold/1-1 (greyscale, not blue). */
.rtt-audio-ctrl {{ width:100%; height:100%; display:flex; align-items:center; justify-content:center;
           color:#666; cursor:pointer; user-select:none; }}
.rtt-audio-ctrl:hover {{ color:#000; }}
.rtt-audio-ctrl.rtt-audio-on {{ background:#666; color:#fff; border-radius:2px; }}
.rtt-audio-glyph {{ width:12px; height:12px; display:block; }}
.material-icons.rtt-audio-glyph {{ font-size:12px; width:auto; height:auto; }}
.rtt-audio-rootglyph {{ font-size:8px; font-family:'Cambria',Georgia,serif; line-height:1; }}
/* the domain − is a hover affordance: an invisible zone over the removable prime's
   header reveals the button parked at its top (above the header, clear of inputs). The
   zone sits above the prime cells (z-index) so a column added via + can't paint over it
   and shrink the hover target down to just the button itself. */
.rtt-minus-zone {{ background:transparent; z-index:4; }}
.rtt-minus-btn {{ position:absolute !important; top:0; left:50%; transform:translateX(-50%);
           opacity:0; pointer-events:none; transition:opacity {_T}; }}
.rtt-minus-zone:hover .rtt-minus-btn {{ opacity:1; pointer-events:auto; }}
/* the vertical basis's domain −: reveals to the RIGHT of the highest prime (the
   spine's spare width), since the row above it is the next prime, not free space */
.rtt-minus-btn-v {{ position:absolute !important; right:0; top:50%; transform:translateY(-50%);
           opacity:0; pointer-events:none; transition:opacity {_T}; }}
.rtt-minus-zone:hover .rtt-minus-btn-v {{ opacity:1; pointer-events:auto; }}

.rtt-toggle {{ width:100%; height:100%; display:flex; align-items:center; justify-content:center;
              font-size:12px !important; line-height:1; color:#666; background:#fff;
              border:1px solid #bbb; cursor:pointer; user-select:none; }}
.rtt-toggle:hover {{ background:#ececec; color:#000; }}
/* the pane's frozen header: the select-all/none master + the show/example titles, pinned above
   the scrolling toggle groups exactly as the column band pins the column titles above the grid.
   Its height is set in render() to the layout's freeze_y, so it matches the main app's frozen band
   to the pixel; the two rows centre within that height (compressed to both fit). Its bottom border
   is the frozen/scrolling seam — the darker rule that used to sit under select-all/none. The full
   330px-wide border (drawn on the border-box edge despite the 14px side padding) reads as one
   clean divider across the pane, like the column band's seam. */
.rtt-show-frozen {{ flex:none; box-sizing:border-box; display:flex; flex-direction:column;
                   justify-content:center; gap:3px; padding:0 14px; border-bottom:1px solid #c4c4c4; }}
/* the scrolling body: the two toggle groups. It sizes to its OWN content (flex:none) capped by a
   max-height set in render() to the window less the inset and the frozen header — NOT by filling the
   flex column. That decoupling matters: when the panel fits, the body equals its content exactly, so
   a sub-pixel rounding in the flex/grid hug would otherwise leave it a hair short and pop a spurious
   scrollbar; sizing to its own content makes any rounding a 1px gap instead. It scrolls (overflow-y:
   auto) only once its content genuinely exceeds the max-height. */
.rtt-show-scroll {{ flex:none; overflow-y:auto; padding:0 14px 16px; }}
/* the select-all/none master toggle — the header's first line (above the show/example titles);
   one click flips every implemented Show toggle. The rule that set it apart now sits below the
   whole header (.rtt-show-frozen's border), so it keeps only its horizontal inset. */
.rtt-show-all {{ padding:0 9px; }}
/* the panel's two column headers: "show" (the toggles) and "example" (their sample
   renders), aligned over the grid columns the rows below use. Both share one font and
   sit on a common baseline so the two words line up. */
.rtt-show-head {{ display:grid; grid-template-columns:160px 1fr; align-items:baseline;
                 padding:0 9px; }}
.rtt-show-title {{ font-size:14px; font-weight:bold; }}
.rtt-show-examplehdr {{ font-size:14px; font-weight:bold; }}
/* general and specific each sit in their own rounded, lightly-bordered sub-card,
   stacked vertically (general above specific) */
.rtt-show-group {{ border:1px solid #c4c4c4; border-radius:5px; background:#e6e6e6;
                  padding:6px 8px; margin-top:8px; }}
.rtt-show-grouptitle {{ font-size:13px; font-weight:bold; text-align:center;
                       color:#000; margin-bottom:4px; }}
/* one toggle row: the checkbox+label in the Show column, its sample in the example column */
.rtt-show-row {{ display:grid; grid-template-columns:160px 1fr; align-items:center; min-height:26px; }}
.rtt-show-item .q-checkbox__label {{ font-family:'Cambria',Georgia,serif; font-size:13px;
                                    color:#000; white-space:pre-line; line-height:1; }}
/* a not-yet-built toggle is disabled — make that unmistakable: render its label AND
   its checkbox box the same light grey (vs the crisp black of an active toggle), a
   far clearer "inactive" cue than Quasar's faint default opacity dim alone */
.rtt-show-item.disabled .q-checkbox__label {{ color:#999; }}
.rtt-show-item.disabled .q-checkbox__inner {{ color:#999 !important; }}
.rtt-ex-cell {{ font-family:'Cambria',Georgia,serif; font-size:14px; color:#000;
               display:flex; align-items:center; min-height:24px; }}
/* a disabled toggle's sample greys to match its label — color for the glyph examples,
   plus the same 0.75 dim Quasar puts on the checkbox so the two read as one shade */
.rtt-ex-cell.rtt-ex-disabled {{ color:#999; opacity:0.75; }}
.rtt-ex {{ white-space:nowrap; }}
"""


_LABEL_KINDS = {"prime", "formcell", "colheader", "rowlabel", "mapped", "vec",
                "rowtoggle", "coltoggle", "tiletoggle", "alltoggle"}  # "ptext" has its own font-sync branch

# Which sticky band each title/toggle kind renders into; every other cell goes to the body
# board. The column titles + their fold toggles ride the column band (sticky to the window top);
# the row titles + toggles the row band (sticky to the left); the master toggle (and the undo/
# redo title tile) the corner band (sticky to both). Per-tile toggles aren't frozen.
_FREEZE_CONTAINER = {"colheader": "col", "coltoggle": "col",
                     "rowlabel": "row", "rowtoggle": "row",
                     "alltoggle": "corner"}

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

# Every EBK mark is drawn by hand as an SVG sized to the cell. The viewBox is the
# cell's own px box (0 0 w h), so one viewBox unit == one px: a stroke we declare
# as N px renders exactly N px wide regardless of how tall/long the mark spans.
# This is the single rule that keeps the brackets and brace a constant weight —
# the rejected font glyph scaled its weight with its height, and a fixed viewBox
# stretched to the cell sheared its serifs. Square/top brackets are crisp filled
# rects; the calligraphic ⟨ and brace are filled variable-width ribbons (_ribbon).
_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar"}


def _svg(w, h, body):
    return (f'<svg width="100%" height="100%" viewBox="0 0 {w:.2f} {h:.2f}" '
            f'preserveAspectRatio="none" style="display:block;overflow:visible">{body}</svg>')


def _rect(x, y, w, h):
    return f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{_BR_COLOR}"/>'


def _ribbon(pts):
    """One filled path tracing a variable-width stroke down a centreline. ``pts``
    is a list of ``(x, y, half_width)``; the outline runs up one offset edge and
    back down the other. A long run can be laid thick and a short turn thin, and
    the centreline may double back (the brace cusp, the ⟨ vertex) — the offsets
    meet at a clean point there, and any inner overlap fills solid (nonzero)."""
    edge_a, edge_b = [], []
    n = len(pts)
    for i in range(n):
        x, y, hw = pts[i]
        px, py = pts[i - 1][:2] if i else pts[i][:2]
        nx, ny = pts[i + 1][:2] if i < n - 1 else pts[i][:2]
        tx, ty = nx - px, ny - py
        length = math.hypot(tx, ty) or 1.0
        ox, oy = -ty / length * hw, tx / length * hw  # normal * half-width
        edge_a.append((x + ox, y + oy))
        edge_b.append((x - ox, y - oy))
    outline = edge_a + edge_b[::-1]
    return ('<path fill="' + _BR_COLOR + '" d="M'
            + ' '.join(f'{x:.2f},{y:.2f}' for x, y in outline) + ' Z"/>')


def _qbez(p0, ctrl, p1, w0, w1, n, *, skip_first=False):
    """Sample a quadratic Bézier from ``p0`` to ``p1`` into ``(x, y, half_width)``
    centreline points, the width lerped ``w0``->``w1`` along it."""
    out = []
    for i in range(n + 1):
        if skip_first and i == 0:
            continue
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * p1[1]
        out.append((x, y, w0 + (w1 - w0) * t))
    return out


def _square_bracket(w, h, side):
    """``[`` or ``]`` as a bar + two perpendicular feet, hugging the value cells
    (open side ``_BR_INSET`` from them). Constant weight at 1 row or many."""
    if side == "left":  # bar on the left, feet reaching right toward the cells
        x_in = w - _BR_INSET
        x_out = x_in - _BR_SERIF_L
        bar_x = x_out
    else:  # "right": bar on the right, feet reaching left toward the cells
        x_out = _BR_INSET
        bar_x = x_out + _BR_SERIF_L - _BR_BAR
    return _svg(w, h,
        _rect(bar_x, 0, _BR_BAR, h)
        + _rect(x_out, 0, _BR_SERIF_L, _BR_SERIF_T)
        + _rect(x_out, h - _BR_SERIF_T, _BR_SERIF_L, _BR_SERIF_T))


def _top_bracket(w, h):
    """The matrix's spanning top bracket: a bar across the top with a down-foot at
    each end. Same weights as the square brackets, so the frame reads as one font."""
    return _svg(w, h,
        _rect(0, 0, w, _BR_BAR)
        + _rect(0, 0, _BR_SERIF_T, _BR_SERIF_L)
        + _rect(w - _BR_SERIF_T, 0, _BR_SERIF_T, _BR_SERIF_L))


def _angle_bracket(w, h):
    """``⟨`` drawn within the SAME oblong footprint as the square brackets — a
    serif-length wide and the full cell height — so every value bracket shares one
    rectangle. A filled ribbon, subtly heavier at the vertex than the open tips.
    The centreline insets (vertex by the thick half-width, tips by the thin one)
    land the ribbon's outer edge on that footprint, vertex hugging the far side."""
    bx1 = w - _BR_INSET  # open tips, nearest the value cells
    bx0 = bx1 - _BR_SERIF_L  # vertex, at the far edge — width matches the square's reach
    cy = h / 2
    vx, tx = bx0 + _BR_ANGLE_THICK, bx1 - 0.4
    top, vertex, bot = (tx, 0.2), (vx, cy), (tx, h - 0.2)
    n = 10
    pts = [(top[0] + (vertex[0] - top[0]) * i / n, top[1] + (vertex[1] - top[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (bot[0] - vertex[0]) * i / n, vertex[1] + (bot[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _brace(w, h):
    """The matrix's bottom curly brace as ONE variable-width ribbon computed from
    the width: long horizontal arms (THICK) sweeping from upturned end-serifs
    (THIN) into a central downward cusp (a THIN near-point). The main (arm) stroke
    runs through the vertical CENTRE of the box, with the end-serifs rising and the
    cusp dipping by the SAME amount, so the brace is balanced about its main stroke
    (not top-heavy). Its depth (the short bounding dimension) matches the value
    brackets' footprint. On a wide span the curls keep a fixed shape and only the
    arm grows; on a narrow span (the per-column braces) the curls shrink together
    so a short arm always survives. One outline, so no seams or overshoot."""
    cx = w / 2
    end_x, serif_dx, cusp_dx = 2.0, 3.2, 5.5
    span = end_x + serif_dx + cusp_dx + 1.0  # the curls plus a reserved minimal arm
    if span > cx:  # too narrow to fit full curls — shrink them together to fit
        s = cx / span
        end_x, serif_dx, cusp_dx = end_x * s, serif_dx * s, cusp_dx * s
    arm_y = h / 2  # the main stroke runs through the box's vertical centre...
    reach = h / 2 - 0.5  # ...with the serifs rising this far above it. The cusp
    # centreline stops a touch short because its pointed tip's fill overshoots
    # downward, so this lands the cusp's fill symmetric to the serif tips — i.e.
    # the arm ends up at the bounding box's exact centre, not above it.
    tip_y, cusp_y = arm_y - reach, arm_y + reach - 0.3
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((end_x, tip_y), (end_x, arm_y), (end_x + serif_dx, arm_y), thin, thick, n)
    pts.append((cx - cusp_dx, arm_y, thick))
    pts += _qbez((cx - cusp_dx, arm_y), (cx, arm_y), (cx, cusp_y), thick, cusp, n, skip_first=True)
    pts += _qbez((cx, cusp_y), (cx, arm_y), (cx + cusp_dx, arm_y), cusp, thick, n, skip_first=True)
    pts.append((w - end_x - serif_dx, arm_y, thick))
    pts += _qbez((w - end_x - serif_dx, arm_y), (w - end_x, arm_y), (w - end_x, tip_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _curly_bracket(w, h):
    """A left curly brace ``{`` for the generator tuning map's frame (it reads ``{ … ]`` —
    curly open, square close — per the mockup). The matrix brace (:func:`_brace`) turned a
    quarter-turn: ONE variable-width ribbon with a vertical spine, the two ends curling
    toward the value cells (thin tips) and a central cusp poking to the far edge (a thin
    near-point). Shares the value brackets' oblong footprint, so the cusp sits where a ``⟨``
    vertex would. The curls keep a fixed shape; only the spine grows with the cell height."""
    cy = h / 2
    end_y, serif_dy, cusp_dy = 2.0, 3.2, 5.5
    span = end_y + serif_dy + cusp_dy + 1.0  # the curls plus a reserved minimal spine
    if span > cy:  # too short to fit full curls — shrink them together to fit
        s = cy / span
        end_y, serif_dy, cusp_dy = end_y * s, serif_dy * s, cusp_dy * s
    tip_x = w - _BR_INSET  # the end-tips curl in toward the value cells
    cusp_x = tip_x - _BR_SERIF_L  # the cusp pokes to the far edge (width matches the ⟨ reach)
    arm_x = (tip_x + cusp_x) / 2  # the spine runs midway between
    thick, thin, cusp = _BR_BRACE_THICK, _BR_BRACE_THIN, _BR_BRACE_CUSP
    n = 10
    pts = _qbez((tip_x, end_y), (arm_x, end_y), (arm_x, end_y + serif_dy), thin, thick, n)
    pts.append((arm_x, cy - cusp_dy, thick))
    pts += _qbez((arm_x, cy - cusp_dy), (arm_x, cy), (cusp_x, cy), thick, cusp, n, skip_first=True)
    pts += _qbez((cusp_x, cy), (arm_x, cy), (arm_x, cy + cusp_dy), cusp, thick, n, skip_first=True)
    pts.append((arm_x, h - end_y - serif_dy, thick))
    pts += _qbez((arm_x, h - end_y - serif_dy), (arm_x, h - end_y), (tip_x, h - end_y),
                 thick, thin, n, skip_first=True)
    return _svg(w, h, _ribbon(pts))


def _angle_foot(w, h):
    """The ket's ``⟩`` turned a quarter-turn to close a raw (untempered) monzo column:
    a shallow downward chevron from the top corners to a centre vertex, the calligraphic
    weight of the ⟨ angle bracket (heavier at the vertex than the open tips). A monzo
    thus reads ``[ … ⟩`` down its column — square top, angle foot — telling it apart
    from a tempered column, which closes with the curly brace (:func:`_brace`)."""
    cx = w / 2
    # the vertex's outer (thick) edge must land inside the box, not poke past it, so
    # the chevron's footprint matches the other marks' shared short dimension — hence
    # the vertex centreline sits a thick-half-width-plus-margin up from the bottom
    ty, vy = 0.85, h - 0.5 - _BR_ANGLE_THICK
    left, vertex, right = (0.8, ty), (cx, vy), (w - 0.8, ty)
    n = 8
    pts = [(left[0] + (vertex[0] - left[0]) * i / n, left[1] + (vertex[1] - left[1]) * i / n,
            _BR_ANGLE_THIN + (_BR_ANGLE_THICK - _BR_ANGLE_THIN) * i / n) for i in range(n + 1)]
    pts += [(vertex[0] + (right[0] - vertex[0]) * i / n, vertex[1] + (right[1] - vertex[1]) * i / n,
             _BR_ANGLE_THICK + (_BR_ANGLE_THIN - _BR_ANGLE_THICK) * i / n) for i in range(1, n + 1)]
    return _svg(w, h, _ribbon(pts))


def _vbar(w, h):
    """A vertical rule between the mapped list's monzo columns, the bar's weight."""
    return _svg(w, h, _rect((w - _BR_BAR) / 2, 0, _BR_BAR, h))


def _ebk_svg(cb):
    """The SVG for one EBK cell, generated from its current px box (cb.w, cb.h). A
    pending comma's marks are recoloured red to match its draft cells."""
    if cb.kind == "bracket":
        if cb.text == "⟨":
            svg = _angle_bracket(cb.w, cb.h)
        elif cb.text == "{":
            svg = _curly_bracket(cb.w, cb.h)
        else:
            svg = _square_bracket(cb.w, cb.h, "left" if cb.text == "[" else "right")
    elif cb.kind == "ebktop":
        svg = _top_bracket(cb.w, cb.h)
    elif cb.kind == "ebkbrace":
        svg = _brace(cb.w, cb.h)
    elif cb.kind == "ebkangle":
        svg = _angle_foot(cb.w, cb.h)
    else:
        svg = _vbar(cb.w, cb.h)  # "vbar"
    return svg.replace(_BR_COLOR, _PENDING_COLOR) if cb.pending else svg


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
    ``indicator`` is set (the optimization objective ⟪𝐝⟫ₚ on the damage chart), a solid
    lighter-grey line marks that minimized-damage level across the plot, broken by a
    ⟪𝐝⟫ label whose subscript is ``indicator_label`` (the scheme's Lp power ∞ / 2 / 1)."""
    axis_x, col_w = spreadsheet.BRACKET_W, spreadsheet.COL_W
    vals = tuple(values)
    ticks = _chart_ticks(min(vals + (0.0,)), max(vals + (0.0,)))  # 0 in range: baseline shows
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
    for i, v in enumerate(vals):
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
                f'font-size="{_RANGE_FONT}" fill="{_BR_COLOR}">{v:.3f}</text>')

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


def _ratio_parts(text):
    """Split a ratio like ``"3/2"`` into ``("3", "2")``; None if it isn't a fraction."""
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text):
    """Split a cents value like ``"1899.260"`` into a big whole part and small fraction."""
    whole, _, frac = str(text).partition(".")
    return whole, frac


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


# The "example" column of the Show panel: one illustrative sample per toggle, read
# from the mockup's Show legend. Most are a glyph or short string (the maps' bold-
# italic letters, the vectors/matrices' bold-upright ones, the plain captions); the
# few graphical samples (the gridded EBK mark, the chart, the preselect chooser) are
# built below from the same primitives the grid uses.
_EXAMPLE_TEXT: dict[str, str] = {
    "names": "tuning map",
    "symbols": "𝒕",
    "equivalences": "𝒕 = 𝒈𝑀",
    "plain_text_values": "[ ⟨12 19 24] }",
    "units": "𝐩",
    "math_expressions": "log₂3",
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
    "nonstandard_domain": "prime-based",
    "identity_objects": "𝑀ⱼ",
}


def _example_grid() -> str:
    """The gridded-values sample: the ⟨12 19 24] EBK mark (angle bracket, three
    boxed components, closing bracket) framed by the matrix top-bracket and brace —
    the same hand-drawn marks the grid uses, shrunk to a legend sample."""
    def box(x, text):
        return (f'<div style="position:absolute;left:{x}px;top:11px;width:22px;height:20px;'
                'border:1px solid #000;background:#fff;display:flex;align-items:center;'
                f'justify-content:center;font-size:11px">{text}</div>')

    def mark(x, y, w, h, svg):
        return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">{svg}</div>'

    return ('<div style="position:relative;width:90px;height:42px">'
            + mark(11, 2, 66, 6, _top_bracket(66, 6))
            + mark(0, 11, 10, 20, _angle_bracket(10, 20))
            + box(12, "12") + box(33, "19") + box(54, "24")
            + mark(78, 11, 10, 20, _square_bracket(10, 20, "right"))
            + mark(11, 34, 66, 6, _brace(66, 6))
            + '</div>')


def _example_chart() -> str:
    """The charts sample: a tiny signed bar sparkline — a 5 / −5 axis with a bar
    dipping below the zero line, as the mockup's legend shows."""
    return ('<div style="position:relative;width:84px;height:34px">'
            '<span style="position:absolute;left:0;top:0;font-size:9px">5</span>'
            '<span style="position:absolute;left:0;bottom:0;font-size:9px">-5</span>'
            '<svg width="66" height="34" viewBox="0 0 66 34" '
            'style="position:absolute;left:16px;top:0">'
            '<line x1="2" y1="3" x2="2" y2="31" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="5" x2="6" y2="5" stroke="#000" stroke-width="1.4"/>'
            '<line x1="0" y1="29" x2="6" y2="29" stroke="#000" stroke-width="1.4"/>'
            '<line x1="2" y1="17" x2="62" y2="17" stroke="#000" stroke-width="1"/>'
            '<rect x="16" y="17" width="22" height="6" fill="#000"/>'
            '</svg></div>')


def _example_preselect() -> str:
    """The preselects sample: the chooser as a bordered field with a caret box."""
    return ('<span style="display:inline-flex;align-items:stretch;font-size:10px">'
            '<span style="border:1px solid #000;border-right:none;padding:2px 6px;'
            'color:#555">&lt;choose form&gt;</span>'
            '<span style="border:1px solid #000;padding:2px 4px;display:flex;'
            'align-items:center">▼</span></span>')


def _example_html(key: str) -> str:
    """The example-column sample for one Show toggle, as an HTML string."""
    if key == "gridded_values":
        return _example_grid()
    if key == "charts":
        return _example_chart()
    if key == "preselects":
        return _example_preselect()
    if key == "mnemonics":  # the underlined mnemonic letters. Wrap in one element: the
        # example cell is a flex box, which would split the words into separate items and
        # trim the space between them — every branch here must return a single root element.
        return f'<span class="rtt-ex">{_underline_html("canonical mapping", ((0, 1), (10, 1)))}</span>'
    if key == "quantities":  # a generic quantity over its size: 1 above .585
        return ('<span style="display:inline-flex;flex-direction:column;align-items:center;'
                'line-height:1.05"><span>1</span><span style="font-size:9px">.585</span></span>')
    if key in ("temperament_colorization", "tuning_colorization", "form_colorization"):
        # a swatch of the actual wash colour (one source of truth with _TINTS), stamped with
        # the fundamental matrix that drives it: 𝑀 (mapping), 𝐺 (generator embedding), 𝐹 (form)
        group = key.split("_")[0]
        letter = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}[group]
        return (f'<span style="display:inline-flex;align-items:center;justify-content:center;'
                f'width:36px;height:14px;background:{_TINTS[group]}">{_math_html(letter)}</span>')
    if key == "audio":  # a speaker glyph — the per-pitch play button the audio rows carry
        return '<span class="material-icons" style="font-size:18px;color:#444">volume_up</span>'
    if key == "tuning_ranges":  # the tuning-range I-beam (min/max generator bars)
        return ('<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
                '<rect x="6" y="2" width="2" height="16" fill="#000"/>'
                '<rect x="2" y="2" width="10" height="2" fill="#000"/>'
                '<rect x="2" y="16" width="10" height="2" fill="#000"/></svg>')
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


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


def _bold_units(value):
    """A unit value with its variable symbols bold (the unit letters g/p and the
    placeholder 1, plus any subscript), leaving the units ¢ and ``oct`` and the ``/``
    separator un-bold. Bolds maximal runs of variable characters so e.g. ``g₁/`` →
    ``<b>g₁</b>/``, ``oct/p`` → ``oct/<b>p</b>``. All text HTML-escaped."""
    out, run = [], []

    def flush():
        if run:
            out.append(f"<b>{_escape(''.join(run))}</b>")
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
        dots = (f"repeating-linear-gradient({sweep},#e0e0e0 0 {spreadsheet.LINE_W}px,"
                f"transparent {spreadsheet.LINE_W}px {_DOT_PITCH}px) border-box")
        return f"{pos}; border-{edge}-color:transparent; background:{dots}"
    return f"{pos}; border-{edge}-color:#e0e0e0; background:none"


def _select_props(min_width: float) -> str:
    """Shared Quasar props for every chooser dropdown (preselect / target / form / control
    select): a compact borderless field whose open popup is at least as wide as its trigger
    (``min_width`` px) but grows to ``max-content``, so each entry shows on one line rather
    than wrapping or truncating at the trigger's width."""
    return ("dense options-dense borderless hide-bottom-space "
            "popup-content-class=rtt-select-popup "
            f"popup-content-style=min-width:{min_width}px;width:max-content")


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


def _set_offlist_prompt(select: ui.select, value) -> None:
    """Show a "-" prompt in a preselect chooser's closed box when its current state matches
    no named entry (``value`` is None) — the temperament chooser with no matching preset, or
    the tuning chooser on a control-refined scheme with no name. It is a Quasar display-value
    placeholder, so "-" never appears as a pickable row in the open list; when a named entry
    matches, the override is cleared and Quasar shows its label."""
    if value is None:
        select.props('display-value="-"')
    else:
        select.props(remove="display-value")


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    # the audio rows' Web Audio engine + its glyph variants (shared markup for click redraws)
    ui.add_body_html(f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>")
    # keep the frozen title bands pinned to the scrolling grid pane (see _FREEZE_JS)
    ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
    ui.query("body").style("background:#fff")
    # trim NiceGUI's default 16px content padding to a slim margin around the whole app
    ui.query(".nicegui-content").style("padding:6px")

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
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # mapping cell id -> q-input
    labels: dict = {}  # cell id -> the label whose text tracks state
    fracs: dict = {}  # ratio cell id -> (numerator label, denominator label)
    cents: dict = {}  # cents cell id -> (whole label, fraction label), aligned on the point
    htmls: dict = {}  # EBK svg cell id -> the ui.html holding its hand-drawn mark
    ebk_sizes: dict = {}  # EBK svg cell id -> last (w, h) it was drawn at, to redraw on resize
    chart_keys: dict = {}  # chart cell id -> last (w, h, values) drawn, to redraw on resize/data change
    range_keys: dict = {}  # range-chart cell id -> last (w, h, ranges) drawn, to redraw on resize/data change
    audio_keys: dict = {}  # speaker/arp/chord cell id -> last cents tuple, to rebuild its click handler on change
    exprs: dict = {}  # math-expression cell id -> the ui.html holding its stacked lines
    expr_state: dict = {}  # math-expression cell id -> last (text, w) rendered, to redraw on change
    kinds: dict = {}  # entity id -> the kind its element was built for (rebuild when it changes)
    selects: dict = {}  # preselect cell id -> its q-select
    checks: dict = {}  # control_check cell id -> its q-checkbox (the box-𝐋 "ignore diminuator")
    ptext_inputs: dict = {}  # editable plain-text cell id -> its q-input (mapping / comma basis)
    rangeopts: dict = {}  # range-mode cell id -> {mode: its clickable square option} (monotone / tradeoff)
    opt_buttons: dict = {}  # optimize-button cell id -> its ui.button (for the auto-lock visual)
    captions: dict = {}  # caption cell id -> the ui.html holding its (maybe underlined) name
    caption_html: dict = {}  # caption cell id -> last html, to rewrite on a mnemonic toggle
    math_cells: dict = {}  # symbol/count cell id -> the ui.html holding its _math_html glyph(s)
    math_rendered: dict = {}  # ...and its last html, to rewrite on an equivalences toggle / value change
    cell_units: dict = {}  # value cell id -> the ui.html holding its per-cell unit (the units toggle)
    cell_unit_text: dict = {}  # ...and its last unit string, to rewrite on a units toggle / value change
    building = [False]
    last_lay = [None]  # the most recently built layout, so the master toggle can read its foldable bands
    refs: dict = {}

    def drop(eid):
        """Remove an entity's element and forget every per-id handle for it."""
        els[eid].delete()
        for d in (els, inputs, labels, fracs, cents, htmls, ebk_sizes, exprs, expr_state, kinds,
                  selects, ptext_inputs, captions, caption_html, math_cells, math_rendered,
                  cell_units, cell_unit_text, chart_keys, range_keys, audio_keys, rangeopts,
                  opt_buttons):
            d.pop(eid, None)

    def set_cents_face(cid, text):
        """Sync a cents cell's stacked face: the whole part over the dot-led fraction (the
        fraction blank when the value is an integer or the cell is blanked). Shared by the
        read-only tval cells and the editable cents cells (whose face overlays their input)."""
        whole, frac = _cents_parts(text)
        cents[cid][0].set_text(whole)
        cents[cid][1].set_text(f".{frac}" if frac else "")

    def on_mapping_change():
        if building[0] or not editor.settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            return
        editor.edit_mapping(matrix)
        render()

    def on_comma_change():
        # the comma basis (the mapping's dual) is edited in the interval-vectors row,
        # which is present independent of the temperament boxes
        if building[0]:
            return
        d, nc = editor.state.d, len(editor.state.comma_basis)
        if editor.pending_comma is not None:
            # the draft column rides at index nc; hand its cells to the editor, which
            # commits (and re-ranks) once they form a valid independent comma
            if any(f"cell:comma:{p}:{nc}" not in inputs for p in range(d)):
                return  # the draft cells aren't shown (folded away)
            editor.set_pending_comma([_parse_int(inputs[f"cell:comma:{p}:{nc}"].value) for p in range(d)])
            render()
            return
        if any(f"cell:comma:{p}:{c}" not in inputs for c in range(nc) for p in range(d)):
            return  # the comma cells aren't currently shown (folded away)
        # the comma cells are the basis transposed (prime down the rows, comma across)
        basis = [[_parse_int(inputs[f"cell:comma:{p}:{c}"].value) for p in range(d)] for c in range(nc)]
        if any(v is None for comma in basis for v in comma):
            return
        editor.edit_comma_basis(basis)
        render()

    def on_interest_change():
        # the intervals of interest are edited as monzos in the interval-vectors row,
        # like the comma basis; read the d-tall columns and replace the set
        if building[0]:
            return
        d, mi = editor.state.d, len(editor.interest_monzos)
        if any(f"cell:interest:{p}:{i}" not in inputs for i in range(mi) for p in range(d)):
            return  # the interest cells aren't currently shown (folded away)
        monzos = [[_parse_int(inputs[f"cell:interest:{p}:{i}"].value) for p in range(d)] for i in range(mi)]
        if any(v is None for m in monzos for v in m):
            return
        editor.set_interest_monzos(monzos)
        render()

    def on_held_change():
        # the held intervals are edited as monzos in the interval-vectors row, like the
        # intervals of interest; read the d-tall columns and replace the held set
        if building[0]:
            return
        d, nh = editor.state.d, len(editor.held_monzos)
        if any(f"cell:held:{p}:{i}" not in inputs for i in range(nh) for p in range(d)):
            return  # the held cells aren't currently shown (folded away / optimization off)
        monzos = [[_parse_int(inputs[f"cell:held:{p}:{i}"].value) for p in range(d)] for i in range(nh)]
        if any(v is None for m in monzos for v in m):
            return
        editor.set_held_monzos(monzos)
        render()

    def on_target_cells_change():
        # the target interval list is edited as monzo columns, like the comma basis; read the
        # d-tall columns (id is cell:vec:targets:{column}:{prime}) and replace the target set
        if building[0]:
            return
        d = editor.state.d
        targets = editor.target_override or service.target_interval_set(
            editor.target_spec, editor.state.domain_basis)
        k = len(targets)
        if any(f"cell:vec:targets:{j}:{p}" not in inputs for j in range(k) for p in range(d)):
            return  # the target cells aren't currently shown (folded away)
        monzos = [[_parse_int(inputs[f"cell:vec:targets:{j}:{p}"].value) for p in range(d)] for j in range(k)]
        if any(v is None for m in monzos for v in m):
            return
        editor.set_target_override_monzos(monzos)
        render()

    def on_power_change(cid):
        # editable power inputs share this kind. optimization:power drives the Lp optimization
        # power; control:q (the complexity norm power in box 𝒄) is styling-only for now, so we
        # accept the keystroke but don't yet wire it through to the scheme.
        if building[0] or cid not in inputs:
            return
        if cid != "optimization:power":
            return  # control:q: white-box look, no behaviour yet (wiring later)
        raw = str(inputs[cid].value).strip().lower()
        if raw in ("∞", "inf", "max", "minimax"):
            power = float("inf")
        else:
            try:
                power = float(raw)
            except ValueError:
                return  # leave the scheme unchanged on unparseable input
            if power <= 0:
                return
        editor.set_optimization_power(power)
        render()

    def on_gentuning_change(cid):
        # an editable generator-tuning-map cell: a valid cents number overrides that one
        # generator's tuning (a per-number manual override); an unparseable entry is ignored
        if building[0] or cid not in inputs:
            return
        try:
            cents = float(str(inputs[cid].value).strip())
        except ValueError:
            return
        editor.set_generator_tuning_component(int(cid.rsplit(":", 1)[1]), cents)
        render()

    def on_prescaler_change(cid):
        # a bare prescaler 𝐿 diagonal cell (cid "cell:prescaling:primes:i:i"): a valid float
        # overrides that one diagonal entry (which then drives EVERY downstream consumer — the
        # product tiles, complexity, weights, the tuning solve and its retunings/damages).
        # The first edit seeds the override from the scheme so the d-1 untouched cells keep
        # their displayed values (set_custom_prescaler_entry handles that). The bare prescaler
        # is a float diagonal (log_prime / prime / identity / typed), so parse as float — an
        # unparseable entry leaves the scheme unchanged, like the other editable cells.
        if building[0] or cid not in inputs:
            return
        try:
            value = float(str(inputs[cid].value).strip())
        except ValueError:
            return
        editor.set_custom_prescaler_entry(int(cid.split(":")[3]), value)
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
        elif cid == "ptext:vectors:targets":  # a typed vector list overrides the target interval set
            ok = editor.set_target_override_text(value)
        elif cid == "ptext:prescaling:primes":  # a typed d×d matrix overrides the prescaler 𝐿's
            # diagonal — the alternative to per-cell edits in the same tile, and the only path
            # for typing the WHOLE diagonal at once. An invalid shape (non-diagonal, wrong size)
            # reddens the box rather than mangling 𝐿, like the mapping / comma-basis duals.
            ok = editor.set_custom_prescaler_text(value)
        else:
            return
        if ok:
            ptext_inputs[cid].classes(remove="rtt-ptext-error")
            render()
        else:
            ptext_inputs[cid].classes(add="rtt-ptext-error")

    def act(action):
        action()
        render()

    def on_show_toggle(key, value):
        # building[0] guards the echo when render() syncs a checkbox to the document
        # (e.g. after undo/redo/reset/select-all) rather than a real user toggle
        if building[0]:
            return
        editor.set_show(key, value)
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def on_select_all(value):
        # the settings panel's select-all/none: flip every implemented Show toggle at once
        if building[0]:
            return
        editor.set_all_show(value)
        render()

    def on_preselect(name, value):
        # the temperament chooser loads a mapping (an undoable edit); the tuning chooser
        # sets the view scheme. A re-render echo is ignored via the building guard.
        if building[0]:
            return
        if name == "temperament":
            # the divider rows are disabled and the prompt is a display-value placeholder
            # (not a row), so only a preset reaches here; load its comma basis as an
            # undoable edit, then re-render to snap the box onto the now-matching preset.
            if value in presets.TEMPERAMENT_COMMAS:
                editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
            render()
        elif name == "tuning" and value is not None:
            editor.set_tuning_scheme(value)  # the bare name, applied in the live target mode
            render()

    def on_form_choose(name, value):
        # the <choose form> control: selecting "canonical" re-stores that matrix in
        # canonical form (an undoable edit). The select snaps back to its placeholder on
        # the re-render. building[0] guards the echo from that reset.
        if building[0] or value != "canonical":
            return
        if name == "mapping":
            editor.canonicalize_mapping()
        elif name == "comma_basis":
            editor.canonicalize_comma_basis()
        render()

    def on_target_change():
        # the target chooser is a numeric limit + a TILT/OLD family; compose them into
        # a spec ("9-TILT", or just "TILT" when the limit is blank). An incomplete or
        # out-of-range limit (one that resolves to no intervals) is held without
        # disturbing the grid, mirroring how a half-typed mapping cell is ignored.
        if building[0]:
            return
        num, sel = selects["preselect:target"]
        family = sel.value or "TILT"
        spec = f"{int(num.value)}-{family}" if num.value else family
        try:
            valid = bool(service.target_interval_set(spec, service.standard_primes(editor.state.d)))
        except Exception:
            valid = False
        if not valid:
            return
        editor.set_target_spec(spec)
        render()

    def on_control_select(cid, value):
        # the alt.-complexity choosers (box 𝐋 prescaler, box 𝒄 complexity norm, box 𝒘 weight
        # slope): each swaps a scheme trait, re-weighting and retuning. The re-render echo is
        # ignored via the guards.
        if building[0] or value is None:
            return
        if cid == "control:prescaler":
            editor.set_complexity_prescaler(value)
        elif cid == "control:norm":
            editor.set_complexity_euclidean(value == "Euclidean")
        elif cid == "control:slope":
            editor.set_weight_slope(value)
        elif cid == "control:complexity":
            if value == "custom":  # a display-only state (a shape off the preset list): no-op
                return
            # the dropdown presents the friendly display name ("log-product (lp)"); map it back
            # to the internal complexity key the editor takes ("lp")
            internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
            editor.set_complexity_name(internal)
        elif cid == "control:diminuator":  # the checkbox passes a bool (ignore the diminuator?)
            editor.set_diminuator_ignored(bool(value))
        elif cid == "control:all_interval":  # the target-controls checkbox: all-interval vs target-based
            editor.set_all_interval(bool(value))
        render()

    def on_range_mode(value):
        # which generator tuning range the ranges chart shows. A re-render echo (the radio
        # mirroring editor.range_mode) is ignored via the building/None guards, like the preselects.
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

    def _ratio(cb, approx):
        """A ratio rendered as a stacked fraction (with a ~ prefix when approximate)."""
        parts = _ratio_parts(cb.text)
        with ui.element("div").classes("rtt-ratio"):
            if approx:
                ui.label("~").classes("rtt-approx")
            if parts:
                with ui.element("div").classes("rtt-frac"):
                    num = ui.label(parts[0]).classes("rtt-frac-num")
                    den = ui.label(parts[1]).classes("rtt-frac-den")
                fracs[cb.id] = (num, den)
            else:
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")

    def _make_cell(cb):
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)

        def cents_face(cls):
            """Build the stacked int-over-fraction cents face (the read-only tval look: the
            whole part big over a smaller dot-led fraction) and register its labels so render()
            keeps them synced. Shared by the read-only tval cell and the editable cents cells —
            the latter pass the overlay class and lay it over their input."""
            whole, frac = _cents_parts(cb.text)
            with ui.element("div").classes(cls):
                w = ui.label(whole).classes("rtt-cents-int")
                f = ui.label(f".{frac}" if frac else "").classes("rtt-cents-frac")
            cents[cb.id] = (w, f)

        with wrap:
            if cb.kind == "mapping":
                wrap.classes("rtt-cell-input")  # a per-cell unit overlays inside the input box
                inputs[cb.id] = ui.input(on_change=lambda e: on_mapping_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "commacell":
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_comma_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "interestcell":  # an editable interval of interest monzo component
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_interest_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "heldcell":  # an editable held interval monzo component (constrains the tuning)
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_held_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "targetcell":  # an editable target interval list monzo component (overrides the set)
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e: on_target_cells_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prescalercell":  # a bare prescaler 𝐿 diagonal cell, the user's editable
                # override (off-diagonal cells stay tval "0" — 𝐿 is diagonal). Each input dispatches
                # to set_custom_prescaler_entry; the cid carries the diagonal slot, so the lambda
                # closes over it (a free cb would be the LAST cell's id by the time the user types)
                wrap.classes("rtt-cell-input rtt-cell-stacked")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_prescaler_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
                cents_face("rtt-tval rtt-cellface")  # the stacked face overlaid on the input
            elif cb.kind in ("prime", "formcell"):  # a read-only bordered cell (domain prime / form-matrix entry)
                with ui.element("div").classes("rtt-white"):
                    labels[cb.id] = ui.label(cb.text)
            elif cb.kind == "genratio":
                _ratio(cb, approx=True)
            elif cb.kind == "commaratio" and cb.pending:  # the draft comma's "?" quantity, red
                labels[cb.id] = ui.label(cb.text).classes("rtt-val rtt-pending-q")
            elif cb.kind in ("target", "commaratio"):
                _ratio(cb, approx=False)
            elif cb.kind in ("mapped", "vec"):  # plain integer values (mapped lists, monzo components)
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")
            elif cb.kind == "count":  # a scalar "symbol = value" (the counts row's 𝑑 = 3 etc.)
                math_cells[cb.id] = ui.html("").classes("rtt-count")  # content set in render()
            elif cb.kind in _EBK_SVG_KINDS:  # ⟨ ] [, top bracket, brace, monzo rule
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # drawn in render() from its px box
            elif cb.kind == "chart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # bar chart drawn in render()
            elif cb.kind == "rangechart":
                htmls[cb.id] = ui.html("").classes("rtt-svgfill")  # I-beam ranges chart drawn in render()
            elif cb.kind == "rangemode":  # the monotone/tradeoff range selector under the ranges chart
                wrap.classes("rtt-rangemode")  # two square indicators side by side (the mockup style)
                opts = {}
                for mode in ("monotone", "tradeoff"):
                    opt = ui.element("div").classes("rtt-rangeopt")
                    with opt:
                        ui.element("span").classes("rtt-rangebox")  # the square (filled when selected)
                        ui.label(mode).classes("rtt-rangelabel")
                    opt.on("click", lambda _=None, m=mode: on_range_mode(m))
                    opts[mode] = opt
                rangeopts[cb.id] = opts
            elif cb.kind == "symbol":
                wrap.classes("rtt-symbol-cell")
                # the optimization box's symbols (⟪𝐝⟫ₚ, 𝑝) stay on one line (ₚ never wraps off)
                cls = "rtt-symbol rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-symbol"
                math_cells[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "matlabel":  # per-row / per-column matrix label (𝒎ᵢ, 𝐜ᵢ, 𝒕ᵢ, …):
                # routed through _math_html so its bold-italic / bold-upright glyphs draw in
                # the same styled face as the tile symbol it indexes. The complexity row's
                # labels are longer (‖L𝐜ᵢ‖q) so they use a smaller variant to avoid colliding
                cls = "rtt-matlabel rtt-matlabel-norm" if "‖" in cb.text else "rtt-matlabel"
                wrap.classes("rtt-matlabel-cell")
                math_cells[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "units":  # the per-box units line and the domain-units row/col labels
                wrap.classes("rtt-units-cell")
                math_cells[cb.id] = ui.html("").classes("rtt-units")  # content set in render()
            elif cb.kind == "caption":
                wrap.classes("rtt-caption-cell")
                # the optimization box's captions stay on one line (no wrap), unlike tile names.
                # a caption with align="left" reads left-justified under its control (e.g. the
                # box-𝐋 "predefined prescalers" label sitting under the prescaler dropdown)
                cls = "rtt-caption rtt-opt-1line" if cb.id.startswith("optimization:") else "rtt-caption"
                if cb.align == "left":
                    cls += " rtt-caption-left"
                captions[cb.id] = ui.html("").classes(cls)  # content set in render()
            elif cb.kind == "preselect":
                name = cb.id.split(":")[1]  # temperament / tuning / target (a copy adds a :col suffix)
                if name == "target":
                    # a numeric limit override beside the TILT/OLD family select, seeded
                    # from the editor's live target family + (optional) manual limit
                    with ui.element("div").classes("rtt-preselect-target"):
                        num = ui.number(value=editor.target_limit, min=2,
                                on_change=lambda e: on_target_change()) \
                            .props("dense borderless hide-bottom-space").classes("rtt-preselect-num")
                        sel = ui.select(list(presets.TARGET_SETS), value=editor.target_family,
                                on_change=lambda e: on_target_change()) \
                            .props(_select_props(cb.w - 30)).classes("rtt-preselect")  # field = cell − the 30px square (touching, no gap)
                    selects[cb.id] = (num, sel)
                elif name == "temperament":
                    # a normal dropdown listing only the prime-limit dividers and their
                    # presets (grouped in the open list). The chosen preset shows in the
                    # box; when none matches, a "-" prompt shows there as a display-value
                    # placeholder — never a pickable row in the list.
                    value = presets.identify(editor.state)
                    sel = _GroupedSelect(presets.temperament_options(), value=value,
                            is_divider=presets.is_divider,
                            on_change=lambda e: on_preselect("temperament", e.value)) \
                        .props(_select_props(cb.w)).classes("rtt-preselect")
                    _set_offlist_prompt(sel, value)
                    selects[cb.id] = sel
                else:  # tuning — systematic scheme names, T-prefixed when targeting a list (not all-
                    # interval); a control-refined scheme has no name, shown as the "-" placeholder.
                    # Alternative-complexity schemes are gated behind the alt. complexity setting.
                    options = presets.tuning_scheme_options(
                        service.is_all_interval(editor.tuning_scheme), editor.settings["alt_complexity"])
                    # "-" when the displayed tuning is off the named list — a refined spec, or a
                    # manual override deviating from the scheme's optimum; else the offered name
                    name = editor.displayed_tuning_scheme_name
                    scheme = name if name in options else None
                    sel = ui.select(options, value=scheme,
                            on_change=lambda e: on_preselect("tuning", e.value)) \
                        .props(_select_props(cb.w)).classes("rtt-preselect")
                    _set_offlist_prompt(sel, scheme)
                    selects[cb.id] = sel
            elif cb.kind == "control_select":  # an alt.-complexity chooser (prescaler / norm / weight slope)
                selects[cb.id] = ui.select(list(cb.values), value=cb.text or None,
                        on_change=lambda e, cid=cb.id: on_control_select(cid, e.value)) \
                    .props(_select_props(cb.w)).classes("rtt-preselect")
            elif cb.kind == "control_check":  # the box-𝐋 "ignore diminuator" checkbox (size factor)
                checks[cb.id] = ui.checkbox(cb.text, value=cb.checked,
                        on_change=lambda e, cid=cb.id: on_control_select(cid, e.value)) \
                    .props("dense").classes("rtt-control-check")
            elif cb.kind == "formchooser":  # the <choose form> control: canonicalizes its matrix on select
                name = cb.id.split(":", 1)[1]  # mapping / comma_basis
                selects[cb.id] = ui.select({"": "choose form", "canonical": "canonical"}, value="",
                        on_change=lambda e, n=name: on_form_choose(n, e.value)) \
                    .props(_select_props(cb.w)).classes("rtt-preselect")
            elif cb.kind == "ptext":  # a read-only value: plain wrapping text, no box
                labels[cb.id] = ui.label(cb.text).classes("rtt-ptext")
            elif cb.kind == "ptextedit":  # an editable dual: typing a valid EBK string drives the grid
                ptext_inputs[cb.id] = ui.input(value=cb.text,
                        on_change=lambda e, cid=cb.id: on_ptext_edit(cid, e.value)) \
                    .props("dense borderless").classes("rtt-ptextedit")
            elif cb.kind == "ptextpending":  # comma basis mid-draft: a static two-tone box (the
                # draft is typed into the red grid cells, not here), content set in render()
                htmls[cb.id] = ui.html("").classes("rtt-ptextpending")
            elif cb.kind == "tval":
                cents_face("rtt-tval")
            elif cb.kind == "mathexpr":  # a just value's stacked closed form, fit to the cell
                exprs[cb.id] = ui.html("").classes("rtt-mathexpr")  # content drawn in render()
            elif cb.kind == "colheader":
                labels[cb.id] = ui.label(cb.text).classes("rtt-colheader")
            elif cb.kind == "rowlabel":
                labels[cb.id] = ui.label(cb.text).classes("rtt-rowlabel")
            elif cb.kind in ("rowtoggle", "coltoggle", "tiletoggle"):
                item = cb.id.split("toggle:", 1)[1]  # "row:tuning" / "col:targets" / "tile:mapping:primes"
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None, it=item: on_toggle(it))
            elif cb.kind == "alltoggle":  # the master expand/collapse-all control in the node corner
                labels[cb.id] = ui.label(cb.text).classes("rtt-toggle material-icons")
                wrap.on("click", lambda _=None: on_toggle_all())
            elif cb.kind == "minus":
                # the zone spans the removable prime's header (the hover target); the
                # button hides at its top and reveals on hover, above the header so it
                # never covers the editable mapping cell below
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "basis_minus":
                # the domain − for the vertical basis: a hover zone over the highest
                # prime revealing the − to its right, so it never covers the box
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn-v")
            elif cb.kind == "comma_minus":
                # the same hover affordance as the domain −, but on the last comma
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda: act(editor.remove_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "comma_plus":
                ui.button("+", on_click=lambda: act(editor.add_comma), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "interest_minus":
                # one per interval (every interval of interest is removable); the hover
                # zone over its header reveals a − that drops just that interval
                i = int(cb.id.split(":", 1)[1])
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda _=None, idx=i: act(lambda: editor.remove_interest(idx)), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "interest_plus":
                ui.button("+", on_click=lambda: act(editor.add_interest), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "held_minus":  # one per held interval; its − drops just that one
                wrap.classes("rtt-minus-zone")
                ui.button("-", on_click=lambda _=None, idx=cb.comma: act(lambda: editor.remove_held(idx)), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn rtt-minus-btn")
            elif cb.kind == "held_plus":
                ui.button("+", on_click=lambda: act(editor.add_held), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "optimize":
                # single click optimizes once (freeze at the optimum); double click toggles
                # the auto-optimize lock. A double-click also fires its two single clicks, but
                # optimize() is idempotent, so a double-click's net effect is the lock toggle.
                opt_buttons[cb.id] = ui.button(cb.text, on_click=lambda: act(editor.optimize), color=None) \
                    .props("unelevated dense no-caps").classes("rtt-btn rtt-optimize")
                opt_buttons[cb.id].on("dblclick", lambda: act(editor.toggle_optimize_lock))
            elif cb.kind == "boxtitle":  # an in-tile box title (e.g. "optimization")
                labels[cb.id] = ui.label(cb.text).classes("rtt-boxtitle")
            elif cb.kind == "powerinput":  # an editable cell-input number (the optimization power
                # 𝑝, or the box-𝒄 norm power 𝑞). The symbol label rides as a separate cell
                # below; the field itself shows only the value, in the bordered cell-input box.
                wrap.classes("rtt-cell-input")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_power_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "gentuningcell":  # an editable generator-tuning-map cell (per-generator override)
                wrap.classes("rtt-cell-input rtt-cell-stacked")
                inputs[cb.id] = ui.input(on_change=lambda e, cid=cb.id: on_gentuning_change(cid)) \
                    .props("dense borderless").classes("rtt-cellinput")
                cents_face("rtt-tval rtt-cellface")  # the stacked face overlaid on the input
            elif cb.kind == "speaker":  # play this pitch per its tile's mode (client-side engine)
                tile = cb.text  # the tile key "<row>:<group>", shared with the tile's control bank
                idx = int(cb.id.rsplit(":", 1)[1])
                pitches = ",".join(f"{float(v):.6f}" for v in cb.values)  # the whole tile (for arp/chord)
                # color=None drops Quasar's default primary (blue): the app is greyscale,
                # leaving colour to the yellow/cyan/magenta colorization. .rtt-spk + the data
                # attrs let the engine highlight this speaker while it sounds.
                ui.button(icon="volume_up", color=None) \
                    .props(f'flat dense round data-audio="{tile}" data-idx="{idx}"') \
                    .classes("rtt-audio-btn rtt-spk") \
                    .on("click", js_handler=f"() => window.rttAudio.hit('{tile}', {idx}, [{pitches}])")
            elif cb.kind in _AUDIO_CTRLS:  # a bank control: cycles its state + glyph client-side
                tile = cb.id.split(":", 1)[1]      # "<row>:<group>"
                ctrl = cb.kind.split("_", 1)[1]     # wave | mode | hold | root
                glyph = {"wave": _AUDIO_GLYPHS["wave"][0], "mode": _AUDIO_GLYPHS["mode"][0],
                         "hold": _AUDIO_GLYPHS["lock"][0], "root": _AUDIO_GLYPHS["root"]}[ctrl]
                fn = {"wave": "cycleWave", "mode": "cycleMode",
                      "hold": "toggleHold", "root": "toggleRoot"}[ctrl]
                ui.html(glyph).classes("rtt-audio-ctrl") \
                    .props(f'data-audio="{tile}" data-actrl="{ctrl}"') \
                    .on("click", js_handler=f"() => window.rttAudio.{fn}('{tile}')")
        return wrap

    def render():
        building[0] = True
        st = editor.state
        lay = editor.layout()
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
        grid_pane.style(f"width:{lay.width + lay.right_overhang + 2 * _PAD}px; height:{lay.height + 2 * _PAD}px")
        board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
        colhead.style(f"height:{fy}px")
        colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
        corner.style(f"width:{fx}px; height:{fy}px")
        gridbody.style(f"top:{_PAD + fy}px")
        rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
        # the settings pane's frozen header takes the same height as the grid's frozen column
        # strip, so the two frozen/scrolling seams line up across the app
        show_frozen.style(f"height:{fy}px")
        # the settings body sizes to its own content but caps at the window less the inset (12px) and
        # the frozen header (fy) above it, so a tall toggle list scrolls there instead of off-screen
        show_scroll.style(f"max-height:calc(100vh - {12 + fy}px)")
        seen = set()

        for ln in lay.lines:
            seen.add(ln.id)
            if ln.id not in els:
                with board:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    els[ln.id] = ui.element("div").classes(cls).props(f'data-eid="{ln.id}"')
            els[ln.id].style(_line_style(ln, fy))

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in els:
                # a block is a thin-bordered box (boxed, the nested tuning-ranges frame), a
                # plain grey tile (tint ""), a colorization wash's white base (tint "base"),
                # or its coloured layer (tint = group name). Fixed for the block's lifetime,
                # so the class is chosen once.
                with board:
                    cls = ("rtt-block-boxed" if bl.boxed
                           else "rtt-washbase" if bl.tint == "base"
                           else "rtt-wash" if bl.tint else "rtt-block")
                    els[bl.id] = ui.element("div").classes(cls).props(f'data-eid="{bl.id}"')
            style = f"left:{bl.x}px; top:{bl.y - fy}px; width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:  # the coloured layer (the base draws white from CSS)
                style += f"; background:{_TINTS[bl.tint]}"
            els[bl.id].style(style)

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id in els and kinds[cb.id] != cb.kind:
                drop(cb.id)  # a cell changed kind (e.g. cents <-> math expression): rebuild it
            if cb.kind in _AUDIO_KINDS and cb.id in els and audio_keys.get(cb.id) != cb.values:
                drop(cb.id)  # cents changed -> rebuild so the baked-in click handler sounds the new pitch
            container = _FREEZE_CONTAINER.get(cb.kind, "body")
            if cb.id not in els:
                with cell_parents[container]:
                    els[cb.id] = _make_cell(cb)
                kinds[cb.id] = cb.kind
                if cb.kind in _AUDIO_KINDS:
                    audio_keys[cb.id] = cb.values
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner
            top = cb.y - (fy if container in ("body", "row") else 0)
            els[cb.id].style(f"left:{cb.x}px; top:{top}px; width:{cb.w}px; height:{cb.h}px")
            if cb.kind in _EBK_SVG_KINDS:
                # the mark is drawn 1:1 to its px box, so redraw it whenever the box
                # changes size (e.g. the brace/top bracket as the domain grows) or its
                # pending (red) state flips (a draft comma's marks committing to black)
                if ebk_sizes.get(cb.id) != (cb.w, cb.h, cb.pending):
                    htmls[cb.id].set_content(_ebk_svg(cb))
                    ebk_sizes[cb.id] = (cb.w, cb.h, cb.pending)
            elif cb.kind == "chart":
                # redraw when the box resizes OR the underlying data / indicator changes
                key = (cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label)
                if chart_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(
                        _bar_chart(cb.w, cb.h, cb.values, cb.indicator, cb.indicator_label))
                    chart_keys[cb.id] = key
            elif cb.kind == "rangechart":
                # redraw when the box resizes OR the ranges/live tuning change (mapping/mode edit)
                key = (cb.w, cb.h, cb.ranges, cb.values)
                if range_keys.get(cb.id) != key:
                    htmls[cb.id].set_content(_range_chart(cb.w, cb.h, cb.ranges, cb.values))
                    range_keys[cb.id] = key
            elif cb.kind == "rangemode":  # fill the live mode's square (the other's is hollow)
                for mode, opt in rangeopts[cb.id].items():
                    (opt.classes(add="rtt-rangeopt-on") if mode == cb.text
                     else opt.classes(remove="rtt-rangeopt-on"))
            elif cb.kind == "optimize":  # mark the button when its auto-optimize lock is on
                (opt_buttons[cb.id].classes(add="rtt-optimize-locked") if editor.optimize_locked
                 else opt_buttons[cb.id].classes(remove="rtt-optimize-locked"))
            elif cb.kind == "powerinput":  # reflect the live optimization power (∞ / 2 / 1)
                inputs[cb.id].value = cb.text
            elif cb.kind == "gentuningcell":  # reflect the live generator tuning (blank when quantities off)
                text = "" if cb.blank else cb.text
                inputs[cb.id].value = text
                set_cents_face(cb.id, text)  # the overlaid stacked face mirrors the input
            elif cb.kind == "mapping":
                inputs[cb.id].value = "" if cb.blank else str(st.mapping[cb.gen][cb.prime])
            elif cb.kind == "commacell":
                if cb.pending:  # the draft column: show the typed component (blank if None), red-outlined
                    v = editor.pending_comma[cb.prime] if editor.pending_comma is not None else None
                    inputs[cb.id].value = "" if v is None else str(v)
                else:
                    inputs[cb.id].value = "" if cb.blank else str(st.comma_basis[cb.comma][cb.prime])
                inputs[cb.id].classes(add="rtt-pending" if cb.pending else "",
                                      remove="" if cb.pending else "rtt-pending")
            elif cb.kind == "interestcell":
                inputs[cb.id].value = cb.text  # the normalized monzo component build computed
            elif cb.kind == "heldcell":
                inputs[cb.id].value = cb.text  # the normalized held monzo component build computed
            elif cb.kind == "targetcell":
                inputs[cb.id].value = cb.text  # the target monzo component build computed (blank when quantities off)
            elif cb.kind == "prescalercell":  # reflect the live prescaler diagonal (the override if set,
                # else the scheme-derived value — spreadsheet.build resolves that and emits the final
                # text already). Blank when quantities are off, mirroring the other editable matrix cells
                inputs[cb.id].value = cb.text
                set_cents_face(cb.id, cb.text)  # the overlaid stacked face mirrors the input
            elif cb.kind == "ptext":  # read-only value: keep its text and shrink-to-fit font in sync
                labels[cb.id].set_text(cb.text)
                labels[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextedit":  # reflect the canonical string + its shrink-to-fit font
                ptext_inputs[cb.id].value = cb.text
                ptext_inputs[cb.id].style(f"font-size:{_ptext_font(cb.text, cb.w)}px")
            elif cb.kind == "ptextpending":  # comma basis with a draft comma: two-tone, the
                # committed commas black and the draft vector red (same red as its grid cells)
                prefix, draft, suffix = service.comma_basis_pending_text(st.comma_basis, editor.pending_comma)
                htmls[cb.id].set_content(
                    f"{prefix}<span class='rtt-pending-q'>{draft}</span>{suffix}")
                htmls[cb.id].style(f"font-size:{_ptext_font(prefix + draft + suffix, cb.w)}px")
            elif cb.kind == "mathexpr":
                # redraw (with refit fonts) whenever the expression text or cell width changes
                if expr_state.get(cb.id) != (cb.text, cb.w):
                    exprs[cb.id].set_content(_mathexpr_html(cb.text, cb.w))
                    expr_state[cb.id] = (cb.text, cb.w)
            elif cb.id in fracs:
                num, den = _ratio_parts(cb.text) or (cb.text, "")
                fracs[cb.id][0].set_text(num)
                fracs[cb.id][1].set_text(den)
            elif cb.id in cents:  # a read-only cents (tval) cell: split into the stacked face
                set_cents_face(cb.id, cb.text)
            elif cb.kind == "preselect":
                # mirror the live selection: the temperament chooser shows the matched
                # preset (or its placeholder), the target chooser splits into limit +
                # family, the tuning chooser shows its scheme. building[0] guards echoes.
                if cb.id.startswith("preselect:temperament"):  # base + the comma-basis copy
                    value = presets.identify(editor.state)
                    selects[cb.id].value = value
                    _set_offlist_prompt(selects[cb.id], value)
                elif cb.id == "preselect:target":
                    num, sel = selects[cb.id]
                    family = editor.target_family
                    # always show the number in use: the manual limit, or the domain default
                    limit = editor.target_limit
                    num.value = limit if limit is not None else \
                        service.default_target_limit(family, service.standard_primes(editor.state.d))
                    sel.value = family
                else:  # tuning — a refined spec or a deviating manual override shows "-"
                    scheme = editor.displayed_tuning_scheme_name
                    # the option LABELS T-prefix only while target-based, so recompute them as the
                    # all-interval checkbox flips (set once at creation, they would otherwise go stale)
                    options = presets.tuning_scheme_options(
                        service.is_all_interval(editor.tuning_scheme), editor.settings["alt_complexity"])
                    selects[cb.id].set_options(options, value=scheme)
                    _set_offlist_prompt(selects[cb.id], scheme)
            elif cb.kind == "control_select":  # mirror the live alt.-complexity choice
                selects[cb.id].value = cb.text or None
            elif cb.kind == "control_check":  # mirror the live "ignore diminuator" state
                checks[cb.id].value = cb.checked
            elif cb.kind == "formchooser":  # a one-shot action: snap back to the placeholder
                selects[cb.id].value = ""
            elif cb.kind in ("symbol", "count", "units", "matlabel"):  # text rendered as HTML:
                # symbols/equivalence tails/counts and matrix row/col labels go through
                # _math_html (styled math glyphs); units use _units_html (a single-story-g
                # sans value, serif label)
                html = _units_html(cb.text) if cb.kind == "units" else _math_html(cb.text)
                if math_rendered.get(cb.id) != html:  # rewrite on a toggle / value change
                    math_cells[cb.id].set_content(html)
                    math_rendered[cb.id] = html
            elif cb.kind == "caption":
                html = _underline_html(cb.text, cb.underlines)
                if caption_html.get(cb.id) != html:  # rewrite when a mnemonic toggle adds/removes underlines
                    captions[cb.id].set_content(html)
                    caption_html[cb.id] = html
            elif cb.kind in _LABEL_KINDS:
                labels[cb.id].set_text(cb.text)

            # per-cell unit (the `units` toggle): a tiny line at the bottom of the value
            # cell, the value lifted to stay centred. cb.unit is "" unless units is on, so
            # this adds/updates/removes the overlay as the toggle (or the domain) changes.
            if cb.unit:
                if cb.id not in cell_units:
                    with els[cb.id]:
                        cell_units[cb.id] = ui.html("").classes("rtt-cellunit")
                    els[cb.id].classes(add="rtt-cell-united")
                if cell_unit_text.get(cb.id) != cb.unit:
                    cell_units[cb.id].set_content(_bold_units(cb.unit))
                    cell_unit_text[cb.id] = cb.unit
            elif cb.id in cell_units:
                cell_units[cb.id].delete()
                cell_units.pop(cb.id, None)
                cell_unit_text.pop(cb.id, None)
                els[cb.id].classes(remove="rtt-cell-united")

        for eid in [e for e in els if e not in seen]:
            drop(eid)

        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        refs["reset"].set_enabled(editor.can_reset)
        # reflect the document's Show settings into the panel (after undo/redo/reset/
        # select-all/load). building[0] is still True, so these programmatic value writes
        # are swallowed by on_show_toggle/on_select_all rather than re-firing as edits.
        for key, box in boxes.items():
            if box.value != editor.settings[key]:
                box.value = editor.settings[key]
        # the master checkbox: checked (true / black fill) when all on, unchecked (false /
        # empty) when all off, MIXED (grey fill) when some-but-not-all are on
        states = [editor.settings[k] for k in show_settings.IMPLEMENTED]
        select_all_box.value = all(states)
        if any(states) and not all(states):
            select_all_box.classes(add="rtt-show-mixed")
        else:
            select_all_box.classes(remove="rtt-show-mixed")
        # persist the whole document so a browser refresh restores exactly this state
        _doc_store()[_STORE_KEY] = editor.serialize()
        building[0] = False

    # the corner hamburger toggles the settings drawer, which slides the app right
    drawer_open = [False]

    def toggle_drawer():
        drawer_open[0] = not drawer_open[0]
        drawer.classes(add="rtt-drawer-open") if drawer_open[0] else drawer.classes(remove="rtt-drawer-open")

    with ui.element("div").classes("rtt-shell"):
        # the rail and the settings pane share one group so the rail's grey stretches to the
        # pane's height; the app sits to the group's right
        with ui.element("div").classes("rtt-panelgroup"):
            # the left rail: the hamburger on top, the app title rotated a quarter-turn below it.
            # The rail is left of the pane, so opening the pane never moves the title.
            with ui.element("div").classes("rtt-rail"):
                ui.button(icon="menu", on_click=toggle_drawer, color=None).props("flat dense").classes("rtt-hamburger")
                ui.label("D&D's RTT app").classes("rtt-sidetitle")
            drawer = ui.element("div").classes("rtt-drawer")
            with drawer, ui.element("div").classes("rtt-drawer-inner"):
                # the frozen header: the select-all/none master + the show/example titles, pinned
                # above the scrolling groups (render() sizes it to the layout's freeze_y, matching
                # the main app's frozen band). Its bottom border is the frozen/scrolling seam.
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
                            .props("dense size=xs color=grey-8").classes("rtt-show-item")
                    with ui.element("div").classes("rtt-show-head"):
                        ui.label("show").classes("rtt-show-title")
                        ui.label("example").classes("rtt-show-examplehdr")
                # the scrolling body: the toggle groups, which scroll under the frozen header when
                # the panel outgrows the window (rather than spilling off the bottom of the screen)
                boxes: dict = {}  # toggle key -> checkbox, so a sub-control row can bind to its parent
                show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
                with show_scroll:
                    for group_name, items in show_settings.SHOW_GROUPS:
                        with ui.element("div").classes("rtt-show-group"):
                            ui.label(group_name).classes("rtt-show-grouptitle")
                            for key, label, _ in items:
                                row = ui.element("div").classes("rtt-show-row")
                                with row:
                                    box = ui.checkbox(label, value=editor.settings[key],
                                                      on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                                        .props("dense size=xs color=grey-8").classes("rtt-show-item")
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
                            .props("flat dense").classes("rtt-iconbtn").mark("undo")
                        refs["redo"] = ui.button(icon="redo", on_click=lambda: act(editor.redo), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("redo")
                        # reset everything (settings, expand/collapse, values) to the
                        # as-shipped defaults — itself an undoable action
                        refs["reset"] = ui.button(icon="restart_alt", on_click=lambda: act(editor.reset), color=None) \
                            .props("flat dense").classes("rtt-iconbtn").mark("reset")
            gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
            with gridbody:
                board = ui.element("div").classes("rtt-gridcontent").mark("board")
                with board, ui.element("div").classes("rtt-band"):
                    rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
    ui.run(title="D&D's RTT App", favicon="https://github.com/DandDsRTT.png",
           reload=True, show=False, port=port, storage_secret=_STORAGE_SECRET,
           uvicorn_reload_excludes=_reload_excludes(worktrees))


if __name__ in {"__main__", "__mp_main__"}:
    main()
