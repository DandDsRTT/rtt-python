window.rttFreeze = (function () {
  function update() {
    var bodies = document.querySelectorAll('.rtt-gridbody');
    for (var i = 0; i < bodies.length; i++) {
      var b = bodies[i], app = b.closest('.rtt-app');
      if (!app) continue;
      var inner = app.querySelector('.rtt-colhead-inner');
      if (inner) inner.style.transform = 'translateX(' + (-b.scrollLeft) + 'px)';
      // The colfill twins ride the horizontal scroll EXACTLY (so each rests glued under its live column
      // rule — clamping X would un-glue them in a left overscroll and ghost a second set of verticals).
      // The vertical axis is clamped non-negative: iOS WebKit reports scrollTop negative through a top
      // overscroll (desktop holds it at 0), and only the clamp keeps the twins PUT so they bridge the
      // bared strip instead of riding the content down and baring an empty band (CSS extends them far
      // upward — see .rtt-colfill-inner — so an arbitrarily long pull still reads unbroken).
      var sy = Math.max(0, b.scrollTop);
      var fill = app.querySelector('.rtt-colfill-inner');
      if (fill) fill.style.transform = 'translate(' + (-b.scrollLeft) + 'px,' + (-sy) + 'px)';
      app.classList.toggle('rtt-scrolled-y', b.scrollTop > 0);
      app.classList.toggle('rtt-scrolled-x', b.scrollLeft > 0);
    }
    reportViewport();
  }

  // Viewport virtualization: tell the server the body scroller's visible rectangle so it materializes
  // only the cells in view (plus overscan). Coalesced through a short trailing timer (one emit per
  // burst of scroll/resize events) and skipped when nothing moved, so the scroll path stays cheap; the
  // server further throttles and ignores sub-overscan deltas. A timer — not requestAnimationFrame — so
  // the report still fires in a backgrounded tab (rAF is paused there) and under headless automation.
  // emitEvent is NiceGUI's global (absent until the socket is up — guarded).
  var lastVp = '', pendingVp = null, vpTimer = null;
  function reportViewport() {
    var b = document.querySelector('.rtt-gridbody');
    if (!b || typeof emitEvent !== 'function') return;
    var vp = { l: b.scrollLeft, t: b.scrollTop, w: b.clientWidth, h: b.clientHeight };
    var key = vp.l + ',' + vp.t + ',' + vp.w + ',' + vp.h;
    if (key === lastVp) return;
    lastVp = key;
    pendingVp = vp;
    if (vpTimer) return;
    vpTimer = setTimeout(function () { vpTimer = null; emitEvent('rtt_viewport', pendingVp); }, 60);
  }

  // The body scroller fills the pane, which HUGS the grid with only a _PAD (12px) grey margin — narrower
  // than a scrollbar. So when the grid outgrows the window on ONE axis and the body takes a scrollbar
  // there, that bar eats into the perpendicular margin and tips a SECOND, spurious scrollbar onto the
  // other axis (the reported bug: a vertical scrollbar forcing a needless horizontal one). fit() removes
  // the coupling. The pane carries its un-reserved ("base") size in data-base-w/-h (published by
  // render()); fit resets the pane to that, reads which axis the window caps it on, then for each axis
  // that must scroll it (a) grows the pane by the scrollbar's width on the PERPENDICULAR axis, so the bar
  // sits in reserved space instead of stealing from the grid — capped by max-width/height:100%, so it
  // borrows the surrounding white margin only when there is room and never reflows the grid — and (b)
  // drops that side's scroll-padding, so even when the pane is already maxed (no room to grow) the
  // gridlines themselves still fit and only the decorative margin yields. Runs off resize/boot and the
  // board/panelgroup width transitions (see below), never the scroll path, so it adds no scroll-time work.
  var sbw = null;
  function scrollbarWidth() {
    var d = document.createElement('div');
    d.style.cssText = 'position:absolute;top:-9999px;width:100px;height:100px;overflow:scroll';
    document.body.appendChild(d);
    var w = d.offsetWidth - d.clientWidth;
    d.remove();
    return w;
  }
  function fit() {
    if (sbw === null) sbw = scrollbarWidth();
    if (!sbw) return;  // overlay scrollbars steal no width — there is nothing to reserve
    var panes = document.querySelectorAll('.rtt-app');
    for (var i = 0; i < panes.length; i++) {
      var pane = panes[i], body = pane.querySelector('.rtt-gridbody');
      if (!body) continue;
      var bw = parseFloat(pane.dataset.baseW), bh = parseFloat(pane.dataset.baseH);
      var fw = parseFloat(pane.dataset.fitW);  // gridlines' width (base minus the title overhang)
      if (!(bw > 0) || !(bh > 0)) continue;
      pane.style.width = bw + 'px';            // reset to the base size to read the window caps
      pane.style.height = bh + 'px';
      // The pane has overflow:hidden (no scrollbars of its own), so clientWidth/Height are the capped
      // layout size — final immediately and unaffected by which body scrollbars show, so this can't
      // flip-flop. A vertical scrollbar is needed when the window caps the pane shorter than the grid;
      // a horizontal one when it caps the pane narrower than the GRIDLINES (fw) — not merely the title
      // overhang, which sits in the frozen colhead and is clipped there, never scrolled in the body.
      var vNeed = pane.clientHeight < bh - 0.5;
      var hNeed = pane.clientWidth < (fw > 0 ? fw : bw) - 0.5;
      pane.style.width = (vNeed ? bw + sbw : bw) + 'px';   // reserve room for the perpendicular bar...
      pane.style.height = (hNeed ? bh + sbw : bh) + 'px';
      body.style.paddingRight = vNeed ? '0px' : '';        // ...and let the margin yield if maxed out
      body.style.paddingBottom = hNeed ? '0px' : '';
    }
  }
  function all() { fit(); update(); }

  document.addEventListener('scroll', update, true);
  window.addEventListener('resize', all);
  // Re-fit when the grid resizes or the settings sidebar slides — neither fires a scroll or window-
  // resize event, but both animate a width: a render retransitions the board's width/height, and
  // opening the drawer transitions the panelgroup's width (which reflows the pane). Listen for those
  // two elements' transitions (filtered, so the grid's many per-cell transitions — which bubble up
  // here — don't trigger it); start AND end both fire fit, so it tracks immediately and settles right.
  function onTransition(e) {
    if (e.target && e.target.matches && e.target.matches('.rtt-gridcontent, .rtt-panelgroup')) all();
  }
  document.addEventListener('transitionstart', onTransition, true);
  document.addEventListener('transitionend', onTransition, true);
  var tries = 0;
  (function boot() { all(); if (++tries < 12) setTimeout(boot, 100); })();
  return { update: update, fit: fit };
})();
