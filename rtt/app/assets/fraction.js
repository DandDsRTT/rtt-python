// Live mode-switching for the editable stacked fraction cells (.rtt-frac-edit: a numerator input
// over a bar over a denominator input). A cell shows the big-INTEGER view when its denominator is
// blank/1 and the RATIO view (num over bar over den) otherwise — and it flips between them WHILE you
// edit, with no server round-trip (committing only happens on blur; see app.py). One document-level
// delegated listener set, matched by class, like audio.js / freeze.js.
//
//  - data-fracmode on the box ("int" | "ratio") is what the CSS reads to show/hide the denominator +
//    bar and pick the font. The server sets it on (re)render from the committed value; this keeps it
//    in sync as you type, and is authoritative again once focus leaves.
//  - "/" in the numerator opens the denominator (ratio view) and jumps the cursor to it.
//  - Tab num->den is native (the den input is the next focusable; the bar is a non-input div, so it is
//    never selectable/tabbable). In integer view the den is display:none, so Tab just leaves the cell.
(function () {
  if (window.__rttFraction) return;
  window.__rttFraction = true;

  function boxOf(el) { return el && el.closest ? el.closest('.rtt-frac-edit') : null; }

  // the den is shown (ratio view) while it is being edited, or while it holds a real denominator
  // (anything but blank or "1"); otherwise the cell collapses to the big-integer view.
  function sync(box) {
    if (!box) return;
    const den = box.querySelector('.rtt-frac-den-in input');
    if (!den) return;
    const v = (den.value || '').trim();
    const editing = document.activeElement === den;
    box.dataset.fracmode = (editing || (v !== '' && v !== '1')) ? 'ratio' : 'int';
  }

  document.addEventListener('keydown', function (e) {
    const t = e.target;
    if (!t.matches || !t.matches('.rtt-frac-num-in input')) return;
    if (e.key === '/') {  // open the denominator and move there, instead of typing a slash into the num
      const box = boxOf(t);
      if (!box) return;
      e.preventDefault();
      box.dataset.fracmode = 'ratio';
      const den = box.querySelector('.rtt-frac-den-in input');
      if (den) den.focus();
    }
  }, true);

  document.addEventListener('input', function (e) {
    if (e.target.matches && e.target.matches('.rtt-frac-den-in input, .rtt-frac-num-in input')) sync(boxOf(e.target));
  }, true);
  document.addEventListener('focusin', function (e) {
    const box = boxOf(e.target);
    if (box) sync(box);
  }, true);
  document.addEventListener('focusout', function (e) {
    const box = boxOf(e.target);
    if (box) setTimeout(function () { sync(box); }, 0);  // let document.activeElement settle first
  }, true);
})();
