(function () {
  if (window.__rttFraction) return;
  window.__rttFraction = true;
  window.rttStackedEditMode({
    editorSel: '.rtt-fraction-edit',
    modeAttr: 'fracmode',
    modeOn: 'ratio',
    modeOff: 'int',
    openKey: '/',
    firstSel: '.rtt-fraction-numerator-input input',
    secondSel: '.rtt-fraction-denominator-input input',
    isFilled: function (value) { return value !== '' && value !== '1'; },
    openPlaceholder: '?',
    navigate: true,
    pendingStaysOpen: true,
    onOpen: function (field) {
      var ratioFont = (window.rttFraction && window.rttFraction.ratioFont) || 13;
      field.querySelectorAll('.rtt-fraction-numerator-input input, .rtt-fraction-denominator-input input')
        .forEach(function (input) { input.style.fontSize = ratioFont + 'px'; });
    },
  });
})();
