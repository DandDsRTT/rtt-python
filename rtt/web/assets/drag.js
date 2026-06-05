// Drag-and-drop fan controls: a column grip (.rtt-colgrip, draggable) is dragged onto a drop
// slot (.rtt-dropslot) to move an interval between or within the lists. This client-side glue
// does the parts that must NOT round-trip the server: while a grip is dragging it marks the body
// so the CSS arms the (otherwise inert) drop slots and dims the other fan controls, prevents the
// default dragover so a drop can fire, and highlights the hovered slot. The pick-up (dragstart)
// and the drop itself cross to Python (NiceGUI per-element handlers) to perform the actual move.
window.rttDrag = (function () {
  function clearOver() {
    var over = document.querySelectorAll('.rtt-dropslot--over');
    for (var i = 0; i < over.length; i++) over[i].classList.remove('rtt-dropslot--over');
  }
  function end() { document.body.classList.remove('rtt-dragging'); clearOver(); }
  document.addEventListener('dragstart', function (e) {
    if (e.target.closest && e.target.closest('.rtt-colgrip')) document.body.classList.add('rtt-dragging');
  }, true);
  document.addEventListener('dragend', end, true);
  document.addEventListener('drop', end, true);
  document.addEventListener('dragover', function (e) {
    var slot = e.target.closest && e.target.closest('.rtt-dropslot');
    if (slot) { e.preventDefault(); slot.classList.add('rtt-dropslot--over'); }  // allow the drop
  }, true);
  document.addEventListener('dragleave', function (e) {
    var slot = e.target.closest && e.target.closest('.rtt-dropslot');
    if (slot) slot.classList.remove('rtt-dropslot--over');
  }, true);
  return {};
})();
