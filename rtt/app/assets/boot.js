(function () {
  if (window.rttBoot) return;
  var RETRIES = 12, INTERVAL = 100;
  window.rttBoot = function (fn, done) {
    var tries = 0;
    (function step() { fn(); if ((!done || !done()) && ++tries < RETRIES) setTimeout(step, INTERVAL); })();
  };
})();
