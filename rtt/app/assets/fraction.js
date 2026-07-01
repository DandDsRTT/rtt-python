(function () {
  if (window.__rttFraction) return;
  window.__rttFraction = true;
  window.rttStackedEditMode({
    boxSel: '.rtt-fraction-edit',
    modeAttr: 'fracmode',
    modeOn: 'ratio',
    modeOff: 'int',
    openKey: '/',
    firstSel: '.rtt-fraction-numerator-input input',
    secondSel: '.rtt-fraction-denominator-input input',
    isFilled: function (value) { return value !== '' && value !== '1'; },
    openPlaceholder: '?',
    onOpen: function (box) {
      var ratioFont = (window.rttFraction && window.rttFraction.ratioFont) || 13;
      box.querySelectorAll('.rtt-fraction-numerator-input input, .rtt-fraction-denominator-input input')
        .forEach(function (input) { input.style.fontSize = ratioFont + 'px'; });
    },
  });
})();
