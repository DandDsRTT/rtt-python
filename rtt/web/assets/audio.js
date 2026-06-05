window.rttAudio = (function () {
  let ctx = null;
  const WAVES = ['sine', 'square', 'triangle', 'sawtooth'], BASE = 261.6255653005986, STEP = 0.34;
  // ONE global config + playing-state drives every speaker (the single bank on the dummy tile cycles
  // it); a speaker's `tile` is used ONLY to pick which speakers to highlight while they ring. The
  // hold-stack (mode 0) keys its held notes by tile:idx so each speaker toggles on/off independently
  // even though the waveform / mode / hold / root config is shared.
  const S = { wave: 0, mode: 0, hold: false, root: false, stop: null, held: {} };
  const api = { glyphs: null };
  function actx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
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
    o.type = WAVES[S.wave];
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
  function ctrlEl(ctrl) {  // the single dummy-tile bank control (data-actrl only — no per-tile copies)
    return document.querySelector('[data-actrl="' + ctrl + '"]');
  }
  api.hit = function (tile, idx, cents) {
    if (S.mode === 0) {                                   // one-off / hold-stack
      if (!S.hold) { const stop = together(tile, [{ idx: idx, cents: cents[idx] }], S.root); setTimeout(stop, 650); return; }
      const key = tile + ':' + idx;                       // hold-stack: key per speaker so each toggles alone
      if (S.held[key]) { S.held[key](); delete S.held[key]; }   // click a held note off
      else { S.held[key] = together(tile, [{ idx: idx, cents: cents[idx] }], S.root); }
      return;
    }
    if (S.stop) { S.stop(); S.stop = null; if (S.hold) return; }  // hold/loop: a second click stops it
    if (S.mode === 1) {                                   // arpeggiate, from the clicked note, wrapping
      const order = []; for (let k = 0; k < cents.length; k++) order.push((idx + k) % cents.length);
      S.stop = sequence(tile, order, cents, S.root, false, S.hold);
      if (!S.hold) S.stop = null;
    } else if (S.mode === 2) {                            // chord: all together
      const items = []; for (let i = 0; i < cents.length; i++) items.push({ idx: i, cents: cents[i] });
      const stop = together(tile, items, S.root);
      if (S.hold) S.stop = stop; else setTimeout(stop, 1000);
    } else {                                              // rolled chord
      const order = []; for (let i = 0; i < cents.length; i++) order.push(i);
      S.stop = sequence(tile, order, cents, S.root, true, S.hold);
      if (!S.hold) S.stop = null;
    }
  };
  function stopAll() { if (S.stop) { S.stop(); S.stop = null; }
    for (const k in S.held) S.held[k](); S.held = {}; }   // each release clears its own speaker's highlight
  api.cycleWave = function () { S.wave = (S.wave + 1) % 4;
    const e = ctrlEl('wave'); if (e) e.innerHTML = api.glyphs.wave[S.wave]; };
  api.cycleMode = function () { stopAll(); S.mode = (S.mode + 1) % 4;
    const e = ctrlEl('mode'); if (e) e.innerHTML = api.glyphs.mode[S.mode]; };
  api.toggleHold = function () { stopAll(); S.hold = !S.hold;
    const e = ctrlEl('hold'); if (e) { e.innerHTML = api.glyphs.lock[S.hold ? 1 : 0]; e.classList.toggle('rtt-audio-on', S.hold); } };
  api.toggleRoot = function () { S.root = !S.root;
    const e = ctrlEl('root'); if (e) e.classList.toggle('rtt-audio-on', S.root); };
  return api;
})();
