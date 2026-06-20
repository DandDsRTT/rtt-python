// Predictable Tab / Shift+Tab navigation across the editable grid cells. The value cells are
// absolutely positioned (each wrap gets its own left/top), so the browser's NATIVE Tab order
// follows DOM source order — which is the spreadsheet's tile BUILD order, not its on-screen
// reading order — and Tab jumps erratically around the grid. This restores the order a spreadsheet
// implies: Tab walks the editable cells top-to-bottom, left-to-right, keeping each multi-cell
// interval-vector / mapping group (a [data-vgroup]) contiguous and filled in its own build
// direction (down a column-vector, across a mapping row). That contiguity is also what the
// blur-commit guard (_GROUP_EXIT_JS, app.py) needs: a vector commits only when focus leaves the
// WHOLE group, so the group's cells must stay adjacent in the Tab ring.
//
// One document-level delegated listener, matched by class, like fraction.js / decimal.js. It only
// acts while focus is inside a grid input; Tab elsewhere (the chrome controls) stays native.
(function () {
  if (window.__rttTabNav) return;
  window.__rttTabNav = true;

  // a grid input is the inner <input> of a .rtt-cellinput inside a .rtt-cell wrap, AND laid out
  // (a collapsed fraction/decimal hides its second field with display:none -> offsetParent null,
  // so an int-view cell's hidden denominator stays out of the Tab ring, exactly as native Tab did).
  const SEL = '.rtt-cell .rtt-cellinput input';
  function focusables() {
    return Array.prototype.filter.call(document.querySelectorAll(SEL),
      function (i) { return !i.disabled && i.offsetParent !== null; });
  }

  // the group a field shares its commit with: the data-vgroup of an integer vector/mapping cell, or
  // the cell's own id (its data-eid) when it stands alone (a scalar ratio / cents / element cell).
  function groupId(c) { return c ? (c.dataset.vgroup || c.dataset.eid || '') : ''; }

  const NEAR = 1;  // px tolerance: items on one visual line share a top within rounding

  // visual reading order, anchored on the CELL wraps (each absolutely positioned at its row y), NOT
  // the inner fields: a stacked cell raises its numerator a few px above an integer neighbour's lone
  // line, so anchoring on fields would scramble one visual row. Order by the group's top-left, then
  // within a group by each CELL's top-left (down a column-vector, across a mapping row), then by the
  // FIELD's top (a stacked cell's numerator over its denominator), DOM order breaking an exact tie.
  function ordered() {
    const inputs = focusables();
    const cellR = new Map(), fieldR = new Map(), anchors = new Map();
    inputs.forEach(function (i) {
      const c = i.closest('.rtt-cell');
      const cr = c.getBoundingClientRect();
      cellR.set(i, cr);
      fieldR.set(i, i.getBoundingClientRect());
      const g = groupId(c), a = anchors.get(g);
      if (!a || cr.top < a.top - NEAR || (Math.abs(cr.top - a.top) <= NEAR && cr.left < a.left))
        anchors.set(g, { top: cr.top, left: cr.left });
    });
    function cmp(pa, pb) {
      if (Math.abs(pa.top - pb.top) > NEAR) return pa.top - pb.top;
      return pa.left - pb.left;
    }
    return inputs.sort(function (a, b) {
      const byGroup = cmp(anchors.get(groupId(a.closest('.rtt-cell'))),
                          anchors.get(groupId(b.closest('.rtt-cell'))));
      if (byGroup) return byGroup;
      const byCell = cmp(cellR.get(a), cellR.get(b));
      if (byCell) return byCell;
      const byField = fieldR.get(a).top - fieldR.get(b).top;  // numerator over denominator
      if (Math.abs(byField) > NEAR) return byField;
      return (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1;
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab' || e.altKey || e.ctrlKey || e.metaKey) return;
    const t = e.target;
    if (!t.matches || !t.matches(SEL)) return;
    const list = ordered();
    const idx = list.indexOf(t);
    if (idx === -1) return;
    const next = list[idx + (e.shiftKey ? -1 : 1)];
    if (!next) return;  // at a grid end: let Tab move focus out of the grid natively
    e.preventDefault();
    next.focus();
    if (next.select) next.select();  // select the content, as native Tab-into-a-text-field does
  }, true);
})();
