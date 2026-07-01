// The "active cell" — a single grid cell carrying the four-layer hover/keyboard highlight, and the
// keyboard navigation that moves it. Mouse hover sets the active cell and always wins over the
// keyboard (hovering a new cell steals it). Arrow keys roam the active cell over EVERY cell in the
// grid; Tab / Shift+Tab walk it along the matrix it sits in (the map for a row-based matrix, the
// vector for a column-based one), wrapping within that line. Typing a printable key over an interactive
// cell begins editing it. Keyboard moves scroll the active cell into view (cells off-screen are not
// even in the DOM under viewport virtualization, so the scroll is what materializes them).
//
// The highlight itself is painted by CSS: each cell gets a --rtt-hl opacity that a white overlay
// (.rtt-cell::after, see rtt.css) renders, so summing the layers' weights into one number lightens
// the cell additively in both themes. This file only computes that number per cell.
//
// One document-level delegated set of listeners, like fraction.js / tabnav.js. Cells are absolutely
// positioned, so "same row / same column" is read geometrically off getBoundingClientRect, and the
// matrix a cell belongs to (and its orientation) is read off the server-stamped data-mx / data-mxo.
(function () {
  if (window.__rttActiveCell) return;
  window.__rttActiveCell = true;

  // layer weights — the white-overlay opacity each layer contributes; a cell sums every layer it is
  // on, so the active cell (on its own crosshair, in its matrix, on its matrix line, and itself) is
  // brightest. Tunable in one place.
  var W_CROSS = 0.30;   // the crosshair row OR column through the active cell (each side adds)
  var W_MATRIX = 0.16;  // anywhere in the active cell's matrix
  var W_ORIENT = 0.34;  // the active cell's map (row-based) or vector (column-based) within that matrix
  var NONACTIVE_MAX = 0.52;  // every cell but the active one caps here, so the active cell (always
                             // full) stays clearly the brightest even where layers stack on its line
  var EPS = 3;          // px slack: cells in one column share an exact x and one row an exact y, so a
                        // cell is on the active's crosshair when its centre falls within the active's
                        // own box (plus a few px for a stacked cell's slightly taller box).

  var active = null;        // the active .rtt-cell element (or null)
  var fromHover = false;    // whether the current active cell came from the mouse

  // only gridded VALUE cells take the highlight or the keyboard focus — never names, symbols,
  // captions, EBK brackets, buttons or other chrome. The server marks them with .rtt-gridval.
  var SEL = '.rtt-app .rtt-cell.rtt-gridval';
  function cells() { return document.querySelectorAll(SEL); }
  function rectOf(element) { return element.getBoundingClientRect(); }
  function centerX(r) { return (r.left + r.right) / 2; }
  function centerY(r) { return (r.top + r.bottom) / 2; }

  function inRowBand(r, activeRect) { return centerY(r) >= activeRect.top - EPS && centerY(r) <= activeRect.bottom + EPS; }
  function inColumnBand(r, activeRect) { return centerX(r) >= activeRect.left - EPS && centerX(r) <= activeRect.right + EPS; }

  // roving tabindex: exactly one value cell is in the tab order (tabindex 0) — the active one, or
  // the first cell when nothing is active yet, so Tab from the page chrome can enter the grid. Every
  // other cell is focusable only by script (tabindex -1). Keyboard moves then focus() the new active
  // cell (see moveTo), so the AT focus and the visual highlight always travel together.
  function applyRoving(all) {
    var focusable = (active && active.isConnected) ? active : all[0];
    for (var i = 0; i < all.length; i++) all[i].tabIndex = (all[i] === focusable) ? 0 : -1;
  }

  // recompute every materialized cell's --rtt-hl for the current active cell.
  function paint() {
    var all = cells();
    applyRoving(all);
    if (!active || !active.isConnected) {
      for (var i = 0; i < all.length; i++) all[i].style.removeProperty('--rtt-hl');
      return;
    }
    var activeRect = rectOf(active);
    var amx = active.dataset.mx || '';
    var amxo = active.dataset.mxo || '';
    for (var k = 0; k < all.length; k++) {
      var element = all[k], r = rectOf(element), w = 0;
      var sameRow = inRowBand(r, activeRect), sameColumn = inColumnBand(r, activeRect);
      if (sameRow) w += W_CROSS;
      if (sameColumn) w += W_CROSS;
      if (amx && element.dataset.mx === amx) {
        w += W_MATRIX;
        if (amxo === 'row' ? sameRow : sameColumn) w += W_ORIENT;
      }
      var hl = (element === active) ? 1 : Math.min(NONACTIVE_MAX, w);
      if (hl > 0) element.style.setProperty('--rtt-hl', hl.toFixed(3));
      else element.style.removeProperty('--rtt-hl');
    }
  }

  function setActive(element, hover) {
    if (element === active && hover === fromHover) return;
    if (active) active.classList.remove('rtt-active');
    active = element;
    fromHover = !!hover;
    if (active) active.classList.add('rtt-active');   // carries the CSS :hover affordances by keyboard
    paint();
  }

  // body.rtt-kbd marks "the keyboard is driving": it suppresses the mouse :hover affordances (which
  // would otherwise linger on whatever the cursor sits over) until the mouse actually moves again.
  function kbdMode() { document.body.classList.add('rtt-kbd'); }
  document.addEventListener('mousemove', function () { document.body.classList.remove('rtt-kbd'); });

  // ---- mouse: hovering any cell makes it active and steals from the keyboard ----
  document.addEventListener('mouseover', function (e) {
    var element = e.target.closest && e.target.closest(SEL);
    if (element) setActive(element, true);
  });

  // ---- keyboard navigation ----
  function gridInput(element) { return element && element.querySelector && element.querySelector('.rtt-cell-input-field input:not([disabled])'); }
  function isEditing() {
    var a = document.activeElement;
    return a && a.matches && a.matches('.rtt-cell-input-field input');
  }
  function activeFromFocus() {
    var a = document.activeElement;
    return a && a.closest ? a.closest('.rtt-cell') : null;
  }

  // the nearest cell in a direction (dx,dy in {-1,0,1}); roams every cell, scored by travel along the
  // axis plus a penalty for drifting off it, so it tracks the visually-adjacent cell.
  function neighbour(dirx, diry) {
    if (!active) return null;
    var activeRect = rectOf(active), ax = centerX(activeRect), ay = centerY(activeRect), all = cells(), best = null, bestScore = Infinity;
    for (var i = 0; i < all.length; i++) {
      var element = all[i]; if (element === active) continue;
      var r = rectOf(element), dx = centerX(r) - ax, dy = centerY(r) - ay;
      var along = dirx ? dx * dirx : dy * diry;
      var off = dirx ? Math.abs(dy) : Math.abs(dx);
      if (along <= 1) continue;
      var score = along + off * 3;
      if (score < bestScore) { bestScore = score; best = element; }
    }
    return best;
  }

  // the line Tab walks: the active cell's map/vector within its matrix (ordered along the
  // orientation), or — for a value cell that is not in a matrix — its visual row of value cells, so
  // Tab always moves WITHIN the grid rather than escaping to the page chrome.
  function navLine() {
    if (!active) return [];
    var activeRect = rectOf(active), all = cells(), amx = active.dataset.mx;
    if (!amx) {  // a value cell outside any matrix: walk its visual row, so Tab stays in the grid
      var row = [];
      for (var j = 0; j < all.length; j++) { var e2 = all[j]; if (inRowBand(rectOf(e2), activeRect)) row.push(e2); }
      row.sort(function (a, b) { return centerX(rectOf(a)) - centerX(rectOf(b)); });
      return row;
    }
    var amxo = active.dataset.mxo, mat = [], line = [];
    for (var i = 0; i < all.length; i++) {
      var element = all[i]; if (element.dataset.mx !== amx) continue;
      mat.push(element);
      if (amxo === 'row' ? inRowBand(rectOf(element), activeRect) : inColumnBand(rectOf(element), activeRect)) line.push(element);
    }
    // walk the active cell's map/vector; but a matrix that is a single map or vector (its orientation
    // line is one cell — e.g. the JI mapping, a column) has nothing to loop, so walk the whole matrix.
    var out = line.length > 1 ? line : mat;
    out.sort(function (a, b) {
      var ra = rectOf(a), rb = rectOf(b);
      if (out === line) return amxo === 'row' ? centerX(ra) - centerX(rb) : centerY(ra) - centerY(rb);
      return Math.abs(ra.top - rb.top) > 1 ? ra.top - rb.top : ra.left - rb.left;
    });
    return out;
  }

  function tabStep(back) {
    var line = navLine();
    if (line.length < 2) return null;
    var index = line.indexOf(active);
    if (index === -1) return null;
    return line[(index + (back ? -1 : 1) + line.length) % line.length];
  }

  // moving the active cell by keyboard should look exactly like hovering it: fire the same pointer
  // events the grid's hover features (the audio speaker, the zoom card, tooltips) listen for.
  function hoverSync(previous, next) {
    if (previous && previous !== next)
      previous.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: next }));
    if (next)
      next.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, relatedTarget: previous }));
  }

  function moveTo(element) {
    if (!element) return;
    kbdMode();
    var previous = active;
    setActive(element, false);
    element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (element.focus) element.focus({ preventScroll: true });
    hoverSync(previous, element);
  }

  function beginEdit(element, ch) {
    var input = gridInput(element);
    if (!input) return false;
    input.focus();
    if (input.select) input.select();
    if (ch != null) {
      input.value = ch;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return true;
  }

  var ARROWS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.metaKey || e.ctrlKey) return;

    // While a cell is being edited, let the input own arrows/typing; Tab still walks the matrix
    // (replacing the old tabnav), and Escape leaves edit mode back to keyboard navigation.
    if (isEditing()) {
      if (e.key === 'Tab') {
        if (!active) setActive(activeFromFocus(), false);
        var t = tabStep(e.shiftKey);
        if (t) { e.preventDefault(); moveTo(t); if (!beginEdit(t)) t.focus(); }
      } else if (e.key === 'Escape') {
        document.activeElement.blur();
        var cell = activeFromFocus(); if (cell) setActive(cell, false);
      }
      return;
    }

    if (e.key === 'Tab') {
      // Tab navigates the grid's value cells (it replaces the old tab-nav). Drop any focus that is
      // sitting in the page chrome (the settings pane) so its focus ring stops walking those controls.
      e.preventDefault();
      var ae = document.activeElement;
      if (ae && ae.blur && ae.closest && !ae.closest('.rtt-app')) ae.blur();
      if (!active) { var first = cells()[0]; if (first) moveTo(first); return; }
      moveTo(tabStep(e.shiftKey) || active);
      return;
    }
    if (ARROWS[e.key]) {
      if (!active) { var first = cells()[0]; if (first) setActive(first, false); }
      var d = ARROWS[e.key], n = neighbour(d[0], d[1]);
      if (n) { e.preventDefault(); moveTo(n); }
      return;
    }
    // Space sounds the active cell's interval (the hovered audio speaker), like clicking it.
    if (e.key === ' ') {
      if (active && active.dataset.audio && window.rttAudio) {
        e.preventDefault();
        rttAudio.playSeg(active.dataset.audio, +active.dataset.idx);
      }
      return;
    }
    // any other printable key over an interactive active cell starts editing it.
    if (active && e.key.length === 1) {
      if (beginEdit(active, e.key)) e.preventDefault();
    }
  }, true);

  // ---- keep the highlight correct as cells scroll, reflow, or re-materialize ----
  var repaintTimer = null;
  function schedulePaint() {
    if (repaintTimer) return;
    repaintTimer = setTimeout(function () { repaintTimer = null; paint(); }, 30);
  }
  document.addEventListener('scroll', schedulePaint, true);
  window.addEventListener('resize', schedulePaint);
  // viewport virtualization rebuilds the cell DOM; re-apply the active highlight to the new cells.
  var obs = new MutationObserver(schedulePaint);
  function observe() {
    var bodies = document.querySelectorAll('.rtt-gridbody');
    for (var i = 0; i < bodies.length; i++) obs.observe(bodies[i], { childList: true, subtree: true });
  }
  if (document.readyState !== 'loading') observe();
  else document.addEventListener('DOMContentLoaded', observe);
  // paint() also seeds the roving tabindex, so run it as cells materialize on first load — otherwise
  // no cell is in the tab order until the first scroll/hover/keydown and Tab can't enter the grid.
  var tries = 0;
  (function boot() { observe(); schedulePaint(); if (++tries < 12) setTimeout(boot, 100); })();
})();
