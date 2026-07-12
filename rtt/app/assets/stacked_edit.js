(function () {
  if (window.rttStackedEditMode) return;

  function dispatchInput(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  window.rttStackedEditMode = function (config) {
    var editorSel = config.editorSel;
    var modeAttr = config.modeAttr;
    var modeOn = config.modeOn;
    var modeOff = config.modeOff;
    var openKey = config.openKey;
    var firstSel = config.firstSel;
    var secondSel = config.secondSel;
    var isFilled = config.isFilled;
    var onOpen = config.onOpen;
    var openPlaceholder = config.openPlaceholder;
    var navigate = config.navigate;
    var pendingStaysOpen = config.pendingStaysOpen;

    function editorOf(element) { return element && element.closest ? element.closest(editorSel) : null; }
    function pendingOpen(editor) { return pendingStaysOpen && !!editor.closest('.rtt-pending'); }

    function sync(editor) {
      if (!editor) return;
      var second = editor.querySelector(secondSel);
      if (!second) return;
      if (pendingOpen(editor)) { editor.dataset[modeAttr] = modeOn; return; }
      var value = (second.value || '').trim();
      var editing = document.activeElement === second;
      editor.dataset[modeAttr] = (editing || isFilled(value)) ? modeOn : modeOff;
    }

    function enter(input) { input.focus(); input.select(); }

    document.addEventListener('keydown', function (e) {
      var el = e.target;
      if (!el.matches) return;
      var editor = editorOf(el);
      if (!editor) return;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second) return;

      if (el === first && e.key === openKey) {
        e.preventDefault();
        editor.dataset[modeAttr] = modeOn;
        if (onOpen) onOpen(editor);
        var before = first.value.slice(0, first.selectionStart);
        var after = first.value.slice(first.selectionEnd);
        second.focus();
        if (before !== first.value) dispatchInput(first, before);
        if (after !== '') dispatchInput(second, after);
        else if (openPlaceholder != null && second.value === openPlaceholder) second.select();
        return;
      }

      if (!navigate) return;
      if (el === second && e.key === 'Backspace' && second.value === '') {
        e.preventDefault();
        e.stopImmediatePropagation();
        first.focus();
        var n = first.value.length;
        first.setSelectionRange(n, n);
        return;
      }
      var open = editor.dataset[modeAttr] === modeOn || pendingOpen(editor);
      var forward = (e.key === 'Tab' && !e.shiftKey) || e.key === 'ArrowDown';
      var backward = (e.key === 'Tab' && e.shiftKey) || e.key === 'ArrowUp';
      if (el === first && forward && open) { e.preventDefault(); e.stopImmediatePropagation(); enter(second); }
      else if (el === second && backward) { e.preventDefault(); e.stopImmediatePropagation(); enter(first); }
    }, true);

    (window.__rttStackedReconcilers = window.__rttStackedReconcilers || []).push(
      function () { document.querySelectorAll(editorSel).forEach(sync); }
    );
    window.rttReconcileStacked = function () {
      (window.__rttStackedReconcilers || []).forEach(function (fn) { fn(); });
    };

    document.addEventListener('input', function (e) {
      if (e.target.matches && e.target.matches(firstSel + ', ' + secondSel)) sync(editorOf(e.target));
    }, true);
    document.addEventListener('focusin', function (e) {
      var editor = editorOf(e.target);
      if (editor) sync(editor);
    }, true);
    document.addEventListener('focusout', function (e) {
      var editor = editorOf(e.target);
      if (editor) setTimeout(function () { sync(editor); }, 0);
    }, true);
  };
})();
