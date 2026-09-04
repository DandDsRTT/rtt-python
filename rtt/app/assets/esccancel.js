(function () {
  if (window.__rttEscCancel) return;
  window.__rttEscCancel = true;

  function cellOf(el) { return el && el.closest ? el.closest('.rtt-cell') : null; }
  function inputsOf(cell) { return cell ? cell.querySelectorAll('input') : []; }

  document.addEventListener('focusin', function (e) {
    if (e.target.tagName !== 'INPUT') return;
    var cell = cellOf(e.target);
    if (!cell || cell._rttEditing) return;
    cell._rttEditing = true;
    inputsOf(cell).forEach(function (i) { i._rttCommitted = i.value; });
  }, true);

  document.addEventListener('focusout', function (e) {
    var cell = cellOf(e.target);
    if (!cell) return;
    setTimeout(function () { if (!cell.contains(document.activeElement)) cell._rttEditing = false; }, 0);
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !e.target.matches || e.target.tagName !== 'INPUT') return;
    var cell = cellOf(e.target);
    if (!cell || !cell._rttEditing) return;
    // A draft cell cancels the whole draft via its own keydown.escape (wired in _recon_cells,
    // marked rtt-draft-input). Defer to it: reverting-and-blurring here would stopImmediatePropagation
    // and preempt that cancel, leaving the draft open.
    if (cell.classList.contains('rtt-draft-input') || cell.classList.contains('rtt-pending')) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    inputsOf(cell).forEach(function (i) {
      if (i._rttCommitted != null && i.value !== i._rttCommitted) {
        i.value = i._rttCommitted;
        i.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
    cell._rttEditing = false;
    e.target.blur();
  }, true);

  // Escape anywhere OUTSIDE a draft input cancels an open draft: click the draft's cancel glyph.
  // A focused draft INPUT is handled by that cell's own keydown.escape (wired in _recon_cells).
  // The ".rtt-glyph" descendant narrows [data-eid$=":pending"] to the minus/cancel cells only
  // (an editable draft input matches the eid suffix but holds an <input>, not a glyph).
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (e.target && e.target.tagName === 'INPUT') return;
    var btn = document.querySelector('[data-eid$=":pending"] .rtt-glyph');
    if (!btn) return;
    e.preventDefault();
    btn.click();
  }, true);
})();
