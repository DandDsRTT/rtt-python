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
})();
