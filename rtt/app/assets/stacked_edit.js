(function () {
  if (window.rttStackedEditMode) return;

  function dispatchInput(input, value) {
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  window.rttStackedEditMode = function (config) {
    var boxSel = config.boxSel;
    var modeAttr = config.modeAttr;
    var modeOn = config.modeOn;
    var modeOff = config.modeOff;
    var openKey = config.openKey;
    var firstSel = config.firstSel;
    var secondSel = config.secondSel;
    var isFilled = config.isFilled;
    var onOpen = config.onOpen;
    var openPlaceholder = config.openPlaceholder;

    function boxOf(element) { return element && element.closest ? element.closest(boxSel) : null; }

    function sync(box) {
      if (!box) return;
      var second = box.querySelector(secondSel);
      if (!second) return;
      var value = (second.value || '').trim();
      var editing = document.activeElement === second;
      box.dataset[modeAttr] = (editing || isFilled(value)) ? modeOn : modeOff;
    }

    document.addEventListener('keydown', function (e) {
      var opener = e.target;
      if (!opener.matches || !opener.matches(firstSel)) return;
      if (e.key !== openKey) return;
      var box = boxOf(opener);
      if (!box) return;
      e.preventDefault();
      box.dataset[modeAttr] = modeOn;
      if (onOpen) onOpen(box);
      var second = box.querySelector(secondSel);
      if (!second) return;
      var before = opener.value.slice(0, opener.selectionStart);
      var after = opener.value.slice(opener.selectionEnd);
      second.focus();
      if (before !== opener.value) dispatchInput(opener, before);
      if (after !== '') dispatchInput(second, after);
      else if (openPlaceholder != null && second.value === openPlaceholder) second.select();
    }, true);

    document.addEventListener('input', function (e) {
      if (e.target.matches && e.target.matches(firstSel + ', ' + secondSel)) sync(boxOf(e.target));
    }, true);
    document.addEventListener('focusin', function (e) {
      var box = boxOf(e.target);
      if (box) sync(box);
    }, true);
    document.addEventListener('focusout', function (e) {
      var box = boxOf(e.target);
      if (box) setTimeout(function () { sync(box); }, 0);
    }, true);
  };
})();
