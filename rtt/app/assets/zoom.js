(() => {
  if (window.__rttZoom) return;
  window.__rttZoom = true;
  const F = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom-factor')) || 1.7;
  const DELAY = 130;
  const GAP = 8;
  const EDGE = 4;
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
