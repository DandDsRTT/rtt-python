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

  // set a field's value AND tell Quasar/NiceGUI about it: the q-input's v-model only updates from the
  // native "input" event, so a bare .value assignment would show on screen but never reach the server
  // (the blur commit re-reads the model). Dispatching "input" routes the moved text through the same
  // path normal typing takes — and trips the document "input" listener below to re-sync the view.
  function setVal(input, v) {
    input.value = v;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

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
      // shrink to the ratio size NOW so the bar sits where it settles — otherwise the int-size (17px)
      // font lingers until a render (commit) and floats the bar high. 13 == _RATIO_MAX_FONT; a render
      // re-fits both fields (and shrinks a long fraction further) on commit.
      box.querySelectorAll('.rtt-frac-num-in input, .rtt-frac-den-in input').forEach(function (i) { i.style.fontSize = '13px'; });
      const den = box.querySelector('.rtt-frac-den-in input');
      if (!den) return;
      // split the numerator at the caret: text BEFORE it stays in the numerator, text AFTER it drops
      // into the denominator — so clicking before the "3" and typing "7/" yields 7/3, not 73. Any
      // selection is the slash's replacement target, so it is discarded (native typing would too).
      const before = t.value.slice(0, t.selectionStart);
      const after = t.value.slice(t.selectionEnd);
      den.focus();  // focus first so the document "input" sync below keeps us in ratio view, not int
      if (before !== t.value) setVal(t, before);  // trim the numerator to its pre-caret head
      if (after !== '') {
        // the moved tail becomes the denominator; the caret rests at its end (Quasar restores it
        // there after the re-render), so the next keystroke extends the denominator and Enter keeps
        // the moved text as-is — the common "7/" -> 7/3 case.
        setVal(den, after);
      } else if (den.value === '?') {
        // a draft cell opens as "?/?"; once the numerator is filled, jumping to the denominator should
        // highlight its leftover "?" so the next keystroke replaces it (same no-backspace behaviour the
        // + button gives the numerator). Only the bare "?" placeholder is auto-selected — a real
        // denominator the user is re-editing keeps its cursor untouched.
        den.select();
      }
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
