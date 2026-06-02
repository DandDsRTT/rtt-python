window.rttAudio = (function () {
  let ctx = null;
  const WAVES = ['sine', 'square', 'triangle', 'sawtooth'], BASE = 261.6255653005986, STEP = 0.34;
  const tiles = {};
  const api = { glyphs: null };
  function actx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function st(tile) {
    if (!tiles[tile]) tiles[tile] = { wave: 0, mode: 0, hold: false, root: false, stop: null, held: {} };
    return tiles[tile];
  }
  function spk(tile, idx) {
    return document.querySelector('.rtt-spk[data-audio="' + tile + '"][data-idx="' + idx + '"]');
  }
  function hl(tile, idx, on) { const e = spk(tile, idx); if (e) e.classList.toggle('rtt-spk-on', on); }
  function clearHl(tile) {
    const es = document.querySelectorAll('.rtt-spk[data-audio="' + tile + '"]');
    for (let i = 0; i < es.length; i++) es[i].classList.remove('rtt-spk-on');
  }
  function vgain(n) { return 0.45 / Math.max(1, n); }
  // start one oscillator; returns a release() that fades it out (and clears its highlight)
  function voice(tile, idx, cents, gain) {
    const ac = actx(), o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
    o.type = WAVES[st(tile).wave];
    o.frequency.value = BASE * Math.pow(2, cents / 1200);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
    o.connect(g); g.connect(ac.destination); o.start(t);
    if (idx >= 0) hl(tile, idx, true);
    let done = false;
    return function () {
      if (done) return; done = true;
      const r = actx().currentTime;
      g.gain.cancelScheduledValues(r);
      g.gain.setValueAtTime(Math.max(g.gain.value, 0.0001), r);
      g.gain.exponentialRampToValueAtTime(0.0001, r + 0.09);
      o.stop(r + 0.12);
      if (idx >= 0) setTimeout(function () { hl(tile, idx, false); }, 110);
    };
  }
  // sound a set of {idx,cents} together (+ optional root drone); returns a stop()
  function together(tile, items, root) {
    const g = vgain(items.length + (root ? 1 : 0)), rels = [];
    for (let i = 0; i < items.length; i++) rels.push(voice(tile, items[i].idx, items[i].cents, g));
    if (root) rels.push(voice(tile, -1, 0, g));
    return function () { for (let i = 0; i < rels.length; i++) rels[i](); };
  }
  // sequence `order` (indices) one per STEP. roll=true keeps notes ringing (rolled chord);
  // arp releases each before the next. loop repeats. root drones underneath. returns stop().
  function sequence(tile, order, cents, root, roll, loop) {
    const g = vgain(roll ? order.length + (root ? 1 : 0) : 2), timers = [];
    let rels = [], rootRel = root ? voice(tile, -1, 0, g) : null, stopped = false;
    function pass() {
      if (stopped) return;
      rels = [];
      for (let k = 0; k < order.length; k++) {
        timers.push(setTimeout(function (k) {
          if (stopped) return;
          const rel = voice(tile, order[k], cents[order[k]], g);
          rels.push(rel);
          if (!roll) setTimeout(rel, STEP * 1000 * 0.85);  // arp: release before the next note
          if (k === order.length - 1 && loop) {
            timers.push(setTimeout(function () {
              if (stopped) return;
              for (let i = 0; i < rels.length; i++) rels[i]();  // end the pass, then repeat
              pass();
            }, roll ? 520 : STEP * 1000));
          } else if (k === order.length - 1 && roll && !loop) {
            timers.push(setTimeout(function () { for (let i = 0; i < rels.length; i++) rels[i](); }, 900));
          }
        }.bind(null, k), k * STEP * 1000));
      }
    }
    pass();
    return function () {
      stopped = true;
      for (let i = 0; i < timers.length; i++) clearTimeout(timers[i]);
      for (let i = 0; i < rels.length; i++) rels[i]();
      if (rootRel) rootRel();
      clearHl(tile);
    };
  }
  function ctrlEl(tile, ctrl) {
    return document.querySelector('[data-actrl="' + ctrl + '"][data-audio="' + tile + '"]');
  }
  api.hit = function (tile, idx, cents) {
    const s = st(tile);
    if (s.mode === 0) {                                   // one-off / hold-stack
      if (!s.hold) { const stop = together(tile, [{ idx: idx, cents: cents[idx] }], s.root); setTimeout(stop, 650); return; }
      if (s.held[idx]) { s.held[idx](); delete s.held[idx]; }   // click a held note off
      else { s.held[idx] = together(tile, [{ idx: idx, cents: cents[idx] }], s.root); }
      return;
    }
    if (s.stop) { s.stop(); s.stop = null; if (s.hold) return; }  // hold/loop: a second click stops it
    if (s.mode === 1) {                                   // arpeggiate, from the clicked note, wrapping
      const order = []; for (let k = 0; k < cents.length; k++) order.push((idx + k) % cents.length);
      s.stop = sequence(tile, order, cents, s.root, false, s.hold);
      if (!s.hold) s.stop = null;
    } else if (s.mode === 2) {                            // chord: all together
      const items = []; for (let i = 0; i < cents.length; i++) items.push({ idx: i, cents: cents[i] });
      const stop = together(tile, items, s.root);
      if (s.hold) s.stop = stop; else setTimeout(stop, 1000);
    } else {                                              // rolled chord
      const order = []; for (let i = 0; i < cents.length; i++) order.push(i);
      s.stop = sequence(tile, order, cents, s.root, true, s.hold);
      if (!s.hold) s.stop = null;
    }
  };
  function stopAll(tile) { const s = st(tile); if (s.stop) { s.stop(); s.stop = null; }
    for (const k in s.held) s.held[k](); s.held = {}; clearHl(tile); }
  api.cycleWave = function (tile) { const s = st(tile); s.wave = (s.wave + 1) % 4;
    const e = ctrlEl(tile, 'wave'); if (e) e.innerHTML = api.glyphs.wave[s.wave]; };
  api.cycleMode = function (tile) { const s = st(tile); stopAll(tile); s.mode = (s.mode + 1) % 4;
    const e = ctrlEl(tile, 'mode'); if (e) e.innerHTML = api.glyphs.mode[s.mode]; };
  api.toggleHold = function (tile) { const s = st(tile); stopAll(tile); s.hold = !s.hold;
    const e = ctrlEl(tile, 'hold'); if (e) { e.innerHTML = api.glyphs.lock[s.hold ? 1 : 0]; e.classList.toggle('rtt-audio-on', s.hold); } };
  api.toggleRoot = function (tile) { const s = st(tile); s.root = !s.root;
    const e = ctrlEl(tile, 'root'); if (e) e.classList.toggle('rtt-audio-on', s.root); };
  return api;
})();
