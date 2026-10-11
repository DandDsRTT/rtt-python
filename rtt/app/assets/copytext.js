(function () {
  if (window.__rttCopyText) return;
  window.__rttCopyText = true;

  var PROSE = '.rtt-text, .rtt-column-header, .rtt-row-label';

  function proseOf(node) {
    var el = node && node.nodeType === 1 ? node : node && node.parentElement;
    return el && el.closest ? el.closest(PROSE) : null;
  }

  function squashed(text) {
    return text.replace(/\s+/g, ' ').trim();
  }

  // A triple-click or a sloppy drag runs the selection past the label's inline box to the end of
  // the block that holds it, and the clipboard serializes that block boundary as a trailing
  // newline. Selection.toString() carries no such newline, so re-set the plain text from it —
  // but only when the selection is exactly one label, so a drag across several still copies them
  // all, and a stacked ratio keeps the browser's own num-over-den serialization.
  document.addEventListener('copy', function (e) {
    var selection = window.getSelection();
    if (!e.clipboardData || !selection || selection.isCollapsed || selection.rangeCount !== 1) return;
    var range = selection.getRangeAt(0);
    var prose = proseOf(range.startContainer);
    var end = proseOf(range.endContainer);
    if (!prose || (end && end !== prose)) return;
    var text = selection.toString().replace(/\s+$/, '');
    if (squashed(text) !== squashed(prose.textContent)) return;
    e.clipboardData.setData('text/plain', text);
    e.preventDefault();
  }, true);
})();
