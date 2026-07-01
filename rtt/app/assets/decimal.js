(function () {
  if (window.__rttDecimal) return;
  window.__rttDecimal = true;
  window.rttStackedEditMode({
    boxSel: '.rtt-decimal-edit',
    modeAttr: 'decmode',
    modeOn: 'decimal',
    modeOff: 'int',
    openKey: '.',
    firstSel: '.rtt-decimal-whole-input input',
    secondSel: '.rtt-decimal-fraction-input input',
    isFilled: function (value) { return value !== '' && value !== '.'; },
  });
})();
