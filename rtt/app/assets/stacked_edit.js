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

    function clearWholeSelect(editor) {
      if (!editor || !editor.dataset.wholeSelect) return;
      delete editor.dataset.wholeSelect;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (first) first.classList.remove('rtt-frac-selected');
      if (second) second.classList.remove('rtt-frac-selected');
    }

    document.addEventListener('keydown', function (e) {
      var el = e.target;
      if (!el.matches) return;
      var editor = editorOf(el);
      if (!editor) return;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second) return;

      if (navigate && editor.dataset.wholeSelect) {
        var k = e.key;
        var typing = k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
        var deleting = k === 'Backspace' || k === 'Delete';
        var moving = k === 'Tab' || k === 'Escape' || k === 'Enter' ||
          k === 'Home' || k === 'End' || k.indexOf('Arrow') === 0;
        if (typing || deleting || moving) {
          clearWholeSelect(editor);
          if ((typing || deleting) && el === first && k !== openKey && second.value) {
            dispatchInput(second, '');
          }
        }
      }

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

    document.addEventListener('click', function (e) {
      if (!navigate || e.detail < 3 || !e.target.matches) return;
      if (!e.target.matches(firstSel) && !e.target.matches(secondSel)) return;
      var editor = editorOf(e.target);
      if (!editor) return;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second || second.value === '') return;
      first.focus();
      first.select();
      first.classList.add('rtt-frac-selected');
      second.classList.add('rtt-frac-selected');
      editor.dataset.wholeSelect = '1';
    }, true);

    document.addEventListener('mousedown', function () {
      if (navigate) document.querySelectorAll(editorSel).forEach(clearWholeSelect);
    }, true);

    var crossDrag = null;

    function paintWholeSelect(editor, lit) {
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second) return;
      first.classList.toggle('rtt-frac-selected', lit);
      second.classList.toggle('rtt-frac-selected', lit);
    }

    document.addEventListener('mousedown', function (e) {
      if (!navigate || e.button !== 0 || !e.target.matches) return;
      if (!e.target.matches(firstSel) && !e.target.matches(secondSel)) return;
      var editor = editorOf(e.target);
      if (!editor || editor.dataset[modeAttr] !== modeOn) return;
      crossDrag = { editor: editor, fromFirst: e.target.matches(firstSel), crossed: false };
    }, true);

    document.addEventListener('mousemove', function (e) {
      if (!crossDrag) return;
      var anchor = crossDrag.editor.querySelector(crossDrag.fromFirst ? firstSel : secondSel);
      if (!anchor) return;
      var rect = anchor.getBoundingClientRect();
      var crossed = crossDrag.fromFirst ? e.clientY > rect.bottom : e.clientY < rect.top;
      if (crossed === crossDrag.crossed) return;
      crossDrag.crossed = crossed;
      paintWholeSelect(crossDrag.editor, crossed);
    }, true);

    document.addEventListener('mouseup', function () {
      if (!crossDrag) return;
      var editor = crossDrag.editor;
      var crossed = crossDrag.crossed;
      crossDrag = null;
      if (!crossed) return;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second) return;
      first.focus();
      first.select();
      first.classList.add('rtt-frac-selected');
      second.classList.add('rtt-frac-selected');
      editor.dataset.wholeSelect = '1';
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
      if (editor) { clearWholeSelect(editor); setTimeout(function () { sync(editor); }, 0); }
    }, true);
  };
})();
