(function () {
  if (window.__rttHoverArmInit) return;
  window.__rttHoverArmInit = true;
  window.__rttHoverArmed = false;
  document.addEventListener('pointermove', function () { window.__rttHoverArmed = true; }, true);
  document.addEventListener('pointerdown', function () { window.__rttHoverArmed = false; }, true);
  // A hover preview that inserts cells LEFT of (or above) the hovered control shifts the control out
  // from under a stationary cursor: the browser fires mouseleave, the preview collapses, the control
  // slides back, mouseenter re-fires — an enter/leave loop. While a preview control is hovered, a rAF
  // loop counter-scrolls the grid body by the control's drift so it holds its viewport position and
  // the shift never paints. Drift is measured in the CONTENT frame — the frozen column-head inner for
  // header controls (its transform rides the body's scrollLeft, possibly compositor-driven) or the
  // grid board for body controls. In-frame position is invariant under scrolling however the ride is
  // synced, so only genuine layout shifts register, and user scrolling is never fought.
  var anchor = null, raf = null;
  function frameOf(el) {
    if (!el || !el.closest) return null;
    return el.closest('.rtt-column-head-inner') || el.closest('.rtt-gridcontent');
  }
  function measure() {
    var el = anchor.el;
    if (!el.isConnected) { anchor = null; return null; }
    var frame = frameOf(el);
    var app = el.closest('.rtt-app');
    var pane = app ? app.querySelector('.rtt-gridbody') : null;
    if (!frame || !pane) { anchor = null; return null; }
    var r = el.getBoundingClientRect(), f = frame.getBoundingClientRect();
    return {
      pane: pane,
      // The frozen head never rides scrollTop, so vertical counter-scroll cannot hold
      // a header control still — compensate x alone there.
      vertical: pane.contains(el),
      dx: (r.left - f.left) - anchor.cx,
      dy: (r.top - f.top) - anchor.cy
    };
  }
  function step() {
    if (!anchor) return;
    var d = measure();
    if (d && (d.dx || (d.vertical && d.dy))) {
      anchor.cx += d.dx;
      d.pane.scrollLeft += d.dx;
      if (d.vertical) {
        anchor.cy += d.dy;
        d.pane.scrollTop += d.dy;
      }
    }
  }
  function loop() {
    raf = requestAnimationFrame(function () {
      if (!anchor) { raf = null; return; }
      step();
      loop();
    });
  }
  window.rttHoverAnchor = {
    set: function (el) {
      var frame = frameOf(el);
      if (!frame) { anchor = null; return; }
      var r = el.getBoundingClientRect(), f = frame.getBoundingClientRect();
      anchor = { el: el, cx: r.left - f.left, cy: r.top - f.top };
      if (!raf) loop();
    },
    clear: function (el) { if (anchor && (!el || anchor.el === el)) anchor = null; },
    step: step
  };
})();
