window.rttFreeze = (function () {
  function update() {
    var bodies = document.querySelectorAll('.rtt-gridbody');
    for (var i = 0; i < bodies.length; i++) {
      var b = bodies[i], app = b.closest('.rtt-app');
      if (!app) continue;
      var inner = app.querySelector('.rtt-colhead-inner');
      if (inner) inner.style.transform = 'translateX(' + (-b.scrollLeft) + 'px)';
      app.classList.toggle('rtt-scrolled-y', b.scrollTop > 0);
      app.classList.toggle('rtt-scrolled-x', b.scrollLeft > 0);
    }
  }
  document.addEventListener('scroll', update, true);
  window.addEventListener('resize', update);
  var tries = 0;
  (function boot() { update(); if (++tries < 12) setTimeout(boot, 100); })();
  return { update: update };
})();
