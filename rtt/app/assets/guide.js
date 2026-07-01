// Quasar: a tooltip is pointer-events:none and hides the instant the cursor leaves its anchor, so its
// link can't be clicked; this builds a real hoverable card instead, kept open while the cursor is on it.
(() => {
  if (window.__rttGuide) return;
  window.__rttGuide = true;
  const DELAY = 200;
  const HIDE = 160;
  const GAP = 6;
  const EDGE = 4;
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
    let left = Math.max(EDGE, Math.min(r.left, vw - card_width - EDGE));
    let top = r.bottom + GAP;
    if (top + card_height > vh - EDGE) top = Math.max(EDGE, r.top - GAP - card_height);
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
