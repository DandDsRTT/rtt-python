(function () {
  if (window.__rttHoverArmInit) return;
  window.__rttHoverArmInit = true;
  window.__rttHoverArmed = false;
  document.addEventListener('pointermove', function () { window.__rttHoverArmed = true; }, true);
  document.addEventListener('pointerdown', function () { window.__rttHoverArmed = false; }, true);
})();
