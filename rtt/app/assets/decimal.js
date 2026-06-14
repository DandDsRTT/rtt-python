// Live mode-switching for the editable stacked DECIMAL cells (.rtt-dec-edit: a big whole-part input
// over a small dot-led fraction input). The DECIMAL twin of fraction.js. A cell shows the big-INTEGER
// view (just the whole part) when it has no fractional part and the DECIMAL view (whole over a small
// ".fraction") otherwise — and it flips between them WHILE you edit, with no server round-trip (the
// inputs commit on their own on_change; see app.py). One document-level delegated listener set,
// matched by class, like fraction.js / audio.js.
//
//  - data-decmode on the box ("int" | "dec") is what the CSS reads to show/hide the fraction line and
//    pick the whole-part font. The server sets it on (re)render from the committed value; this keeps
//    it in sync as you type, and is authoritative again once focus leaves.
//  - "." in the whole part opens the fraction (dec view) and jumps the cursor to it — the decimal
//    analogue of "/" opening a fraction's denominator.
//  - Tab whole->frac is native (the frac input is the next focusable; the dot is a non-input div, so
//    it is never selectable/tabbable). In integer view the frac line is display:none, so Tab leaves.
(function () {
  if (window.__rttDecimal) return;
  window.__rttDecimal = true;

  function boxOf(el) { return el && el.closest ? el.closest('.rtt-dec-edit') : null; }

  // set a field's value AND tell Quasar/NiceGUI about it (the q-input's v-model only updates from the
  // native "input" event; a bare .value would show but never reach the server). The fraction twin of
  // fraction.js's setVal.
  function setVal(input, v) {
    input.value = v;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // the fraction line is shown (dec view) while it is being edited, or while it holds any digits;
  // otherwise the cell collapses to the big-integer (int) view.
  function sync(box) {
    if (!box) return;
    const frac = box.querySelector('.rtt-dec-frac-in input');
    if (!frac) return;
    const v = (frac.value || '').trim();
    const editing = document.activeElement === frac;
    box.dataset.decmode = (editing || (v !== '' && v !== '.')) ? 'dec' : 'int';
  }

  document.addEventListener('keydown', function (e) {
    const t = e.target;
    if (!t.matches || !t.matches('.rtt-dec-whole-in input')) return;
    if (e.key === '.') {  // open the fraction and move there, instead of typing a dot into the whole
      const box = boxOf(t);
      if (!box) return;
      e.preventDefault();
      box.dataset.decmode = 'dec';  // un-hide the frac line NOW so it is focusable in the same tick
      const frac = box.querySelector('.rtt-dec-frac-in input');
      if (!frac) return;
      // split the whole part at the caret: text BEFORE it stays in the whole, text AFTER it drops into
      // the fraction — so clicking before the "01" and typing "7." yields 7.01, not 701 (the decimal
      // analogue of fraction.js). Any selection is the dot's replacement target, so it is discarded.
      const before = t.value.slice(0, t.selectionStart);
      const after = t.value.slice(t.selectionEnd);
      frac.focus();  // focus first so the document "input" sync below keeps us in dec view, not int
      if (before !== t.value) setVal(t, before);  // trim the whole part to its pre-caret head
      if (after !== '') {
        // the moved tail becomes the fractional part; the caret rests at its end (Quasar restores it
        // there after the re-render), so the next keystroke extends the fraction and Enter keeps it.
        setVal(frac, after);
      }
    }
  }, true);

  document.addEventListener('input', function (e) {
    if (e.target.matches && e.target.matches('.rtt-dec-frac-in input, .rtt-dec-whole-in input')) sync(boxOf(e.target));
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
