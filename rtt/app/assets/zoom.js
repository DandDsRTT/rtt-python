(() => {
  if (window.__rttZoom) return;
  window.__rttZoom = true;
  const F = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom-factor')) || 1.7;
  const DELAY = 130;
  const HIDE = 160;
  const GAP = 8;
  const EDGE = 4;
  let timer = null, hideTimer = null, anchor = null, shownFor = null;

  const overlay = document.createElement('div');
  overlay.className = 'rtt-zoom-overlay';
  overlay.style.display = 'none';
  document.body.appendChild(overlay);

  const hide = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    if (overlay.style.display !== 'none') { overlay.style.display = 'none'; overlay.innerHTML = ''; }
    overlay.classList.remove('rtt-zoom-guided');
    anchor = null;
    shownFor = null;
  };
  // A guided overlay is hoverable (its guide link must be reachable across the GAP), so it hides on
  // a short grace timer the way guide.js does; an unguided one keeps the original instant hide.
  const scheduleHide = () => {
    if (!overlay.classList.contains('rtt-zoom-guided')) { hide(); return; }
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(hide, HIDE);
  };
  const cancelHide = () => {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
  };

  const place = (cell) => {
    const r = cell.getBoundingClientRect();
    const ow = overlay.offsetWidth, oh = overlay.offsetHeight;
    const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    let left = Math.max(EDGE, Math.min(r.left + r.width / 2 - ow / 2, vw - ow - EDGE));
    const audioFloat = cell.classList.contains('rtt-speaker') && !document.body.classList.contains('rtt-audio-muted');
    let top = r.top - GAP - oh;
    let above = true;
    if (audioFloat || top < EDGE) { top = r.bottom + GAP; above = false; }
    top = Math.max(EDGE, Math.min(top, vh - oh - EDGE));
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

    cancelHide();
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
    const guideText = cell.getAttribute('data-guide-text');
    const tipsOff = document.body.classList.contains('rtt-no-tooltips');
    const guided = !!guideText && !tipsOff;
    overlay.classList.toggle('rtt-zoom-guided', guided);
    if ((help || guideText) && !tipsOff) {
      const card = document.createElement('div');
      card.className = 'rtt-zoom-card';
      if (help) {
        const cap = document.createElement('div');
        cap.className = 'rtt-zoom-card-help';
        cap.textContent = help;
        card.appendChild(cap);
      }
      if (guided) {
        const body = document.createElement('div');
        body.className = 'rtt-guide-card-text';
        body.textContent = guideText;
        card.appendChild(body);
        const url = cell.getAttribute('data-guide-url');
        if (url) {
          const a = document.createElement('a');
          a.className = 'rtt-guide-card-link';
          a.href = url; a.target = '_blank'; a.rel = 'noopener';
          a.textContent = cell.getAttribute('data-guide-loc') + ' →';
          card.appendChild(a);
        }
      }
      overlay.appendChild(card);
    }
    shownFor = cell;
    overlay.style.display = 'flex';   // matches the CSS (gap + centering); 'block' would defeat them
    place(cell);
  };

  document.addEventListener('mouseover', (e) => {
    if (overlay.contains(e.target)) {
      cancelHide();
      if (timer) { clearTimeout(timer); timer = null; }
      anchor = shownFor;
      return;
    }
    // the reduce/reciprocate buttons carry their own tooltip; the loupe yields so that at most
    // one text popup is ever up.
    if (e.target.closest && e.target.closest('.rtt-ratio-operation')) { hide(); return; }
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (!cell || cell === anchor) return;
    if (timer) clearTimeout(timer);
    anchor = cell;
    timer = setTimeout(() => { if (anchor === cell && cell.isConnected) build(cell); }, DELAY);
  });
  document.addEventListener('mouseout', (e) => {
    const to = e.relatedTarget;
    const toFloat = to && to.closest && to.closest('.rtt-speaker-float');
    const toOverlay = !!(to && overlay.contains(to));
    if (overlay.contains(e.target)) {
      if (toOverlay || toFloat) return;
      const toCell = to && to.closest && to.closest('.rtt-zoomable');
      if (toCell && toCell === shownFor) return;
      scheduleHide();
      return;
    }
    const cell = e.target.closest && e.target.closest('.rtt-zoomable');
    if (cell && cell === anchor) {
      if (!toFloat && !toOverlay && !cell.contains(to)) scheduleHide();
      return;
    }
    const fromFloat = e.target.closest && e.target.closest('.rtt-speaker-float');
    if (fromFloat && anchor && !toFloat) {
      const toCell = to && to.closest && to.closest('.rtt-zoomable');
      if (toCell !== anchor) hide();
    }
  });
  document.addEventListener('pointerdown', (e) => {
    if (e.target.closest && e.target.closest('.rtt-speaker-float')) return;
    if (overlay.contains(e.target)) return;
    hide();
  }, true);
  document.addEventListener('keydown', hide, true);
  document.addEventListener('wheel', hide, {capture: true, passive: true});
  document.addEventListener('scroll', hide, {capture: true, passive: true});
})()
