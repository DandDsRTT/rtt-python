(function () {
  if (window.rttStackedEditMode) return;

  function dispatchInput(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  // field-sizing:content sizes each stacked input to hug its digits in Chrome and Safari 26; Firefox
  // and older Safari lack it, so there we measure the text and set an explicit width (a no-op where
  // native field-sizing works — an inline width would otherwise override it).
  var fieldSizingNative = null;
  function widthSyncNeeded() {
    if (fieldSizingNative === null) {
      try { fieldSizingNative = CSS.supports('field-sizing', 'content'); }
      catch (e) { fieldSizingNative = false; }
    }
    return !fieldSizingNative;
  }
  var measureCtx = null;
  function sizeToContent(input) {
    if (!input) return;
    if (!measureCtx) measureCtx = document.createElement('canvas').getContext('2d');
    var cs = getComputedStyle(input);
    measureCtx.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
    var w = measureCtx.measureText(input.value || input.placeholder || '').width;
    if (cs.boxSizing === 'border-box') {
      w += parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) +
        parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth);
    }
    input.style.width = Math.ceil(w) + 'px';
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
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!second) return;
      if (widthSyncNeeded()) { sizeToContent(first); sizeToContent(second); }
      if (pendingOpen(editor)) { editor.dataset[modeAttr] = modeOn; return; }
      var value = (second.value || '').trim();
      var editing = document.activeElement === second;
      editor.dataset[modeAttr] = (editing || isFilled(value)) ? modeOn : modeOff;
    }

    function enter(input) { input.focus(); input.select(); }

    function beforeCaret(input) { return input.value.slice(0, input.selectionStart); }
    function afterCaret(input) { return input.value.slice(input.selectionEnd); }

    function openMode(editor) {
      editor.dataset[modeAttr] = modeOn;
      if (onOpen) onOpen(editor);
    }

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
        openMode(editor);
        var before = beforeCaret(first);
        var after = afterCaret(first);
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

    document.addEventListener('paste', function (e) {
      var el = e.target;
      if (!el.matches || !e.clipboardData) return;
      var editor = editorOf(el);
      if (!editor) return;
      var first = editor.querySelector(firstSel);
      var second = editor.querySelector(secondSel);
      if (!first || !second || el !== first) return;
      var pasted = e.clipboardData.getData('text').trim();
      var replacing = navigate && editor.dataset.wholeSelect;
      clearWholeSelect(editor);
      var cut = pasted.indexOf(openKey);
      if (cut < 0) {
        if (replacing && second.value) dispatchInput(second, '');
        return;
      }
      e.preventDefault();
      var before = beforeCaret(first);
      var after = afterCaret(first);
      var tail = pasted.slice(cut + openKey.length).trim();
      openMode(editor);
      dispatchInput(first, before + pasted.slice(0, cut).trim());
      second.focus();
      dispatchInput(second, tail + after);
      second.setSelectionRange(tail.length, tail.length);
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

    function cancelCrossDrag() {
      if (!crossDrag) return;
      paintWholeSelect(crossDrag.editor, false);
      crossDrag = null;
    }

    document.addEventListener('mousedown', function (e) {
      if (!navigate) return;
      cancelCrossDrag();
      if (e.button !== 0 || !e.target.matches) return;
      if (!e.target.matches(firstSel) && !e.target.matches(secondSel)) return;
      var editor = editorOf(e.target);
      if (!editor || editor.dataset[modeAttr] !== modeOn) return;
      var second = editor.querySelector(secondSel);
      if (!second || second.value === '') return;
      crossDrag = { editor: editor, fromFirst: e.target.matches(firstSel), crossed: false };
    }, true);

    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') cancelCrossDrag();
    }, true);

    document.addEventListener('mousemove', function (e) {
      if (!crossDrag) return;
      if (!(e.buttons & 1)) { cancelCrossDrag(); return; }
      var target = crossDrag.editor.querySelector(crossDrag.fromFirst ? secondSel : firstSel);
      if (!target) return;
      var rect = target.getBoundingClientRect();
      var entry = rect.height * 0.3;
      var crossed = crossDrag.fromFirst
        ? e.clientY >= rect.top + entry
        : e.clientY <= rect.bottom - entry;
      if (crossed === crossDrag.crossed) return;
      crossDrag.crossed = crossed;
      paintWholeSelect(crossDrag.editor, crossed);
    }, true);

    document.addEventListener('mouseup', function (e) {
      if (!crossDrag || e.button !== 0) return;
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
