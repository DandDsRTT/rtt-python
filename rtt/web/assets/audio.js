window.rttAudio = (function () {
  let ctx = null;
  const WAVES = ['sine', 'square', 'triangle', 'sawtooth'], BASE = 261.6255653005986, STEP = 0.34;
  // ONE global config + playing-state drives every speaker (the single bank on the dummy tile cycles
  // it); a speaker's `tile` is used ONLY to pick which speakers to highlight while they ring. The
  // hold-stack (mode 0) keys its held notes by tile:idx so each speaker toggles on/off independently
  // even though the waveform / mode / hold / root config is shared.
  // `live` is EVERY currently-sounding voice's release fn — the kill switch (stopAll) clears it, so a
  // note/drone can always be silenced no matter how it was started (S.stop/S.held don't track them all).
  const S = { wave: 0, mode: 0, hold: false, root: false, muted: true, stop: null, held: {}, live: new Set() };
  const api = { glyphs: null };
  function actx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function hl(tile, idx, on) {  // light EVERY cell sharing this voice (a vector column shares one idx)
    const es = document.querySelectorAll('.rtt-spk[data-audio="' + tile + '"][data-idx="' + idx + '"]');
    for (let i = 0; i < es.length; i++) es[i].classList.toggle('rtt-spk-on', on);
  }
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
    function release() {
      if (done) return; done = true;
      S.live.delete(release);
      const r = actx().currentTime;
      g.gain.cancelScheduledValues(r);
      g.gain.setValueAtTime(Math.max(g.gain.value, 0.0001), r);
      g.gain.exponentialRampToValueAtTime(0.0001, r + 0.09);
      o.stop(r + 0.12);
      if (idx >= 0) setTimeout(function () { hl(tile, idx, false); }, 110);
    }
    S.live.add(release);
    return release;
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
          } else if (k === order.length - 1 && !loop) {
            // one-shot end: release any still-ringing notes (a rolled chord) AND the root drone, then
            // clear the highlights — without releasing rootRel the 1/1 would drone forever (the bug)
            timers.push(setTimeout(function () {
              for (let i = 0; i < rels.length; i++) rels[i]();
              if (rootRel) rootRel();
              clearHl(tile);
            }, roll ? 900 : STEP * 1000));
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
    if (S.muted) return;                                  // muted: the kill switch is also the gate
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
  function stopAll() {  // the kill switch: release EVERY sounding voice, however it was started, so a
    Array.from(S.live).forEach(function (r) { r(); });    // stuck note or 1/1 drone can always be silenced
    S.live.clear(); S.stop = null; S.held = {};
  }
  api.cycleWave = function () { S.wave = (S.wave + 1) % 4;
    const e = ctrlEl('wave'); if (e) e.innerHTML = api.glyphs.wave[S.wave]; };
  api.cycleMode = function () { stopAll(); S.mode = (S.mode + 1) % 4;
    const e = ctrlEl('mode'); if (e) e.innerHTML = api.glyphs.mode[S.mode]; };
  api.toggleHold = function () { stopAll(); S.hold = !S.hold;
    const e = ctrlEl('hold'); if (e) { e.innerHTML = api.glyphs.lock[S.hold ? 1 : 0]; e.classList.toggle('rtt-audio-on', S.hold); } };
  api.toggleRoot = function () { S.root = !S.root;
    const e = ctrlEl('root'); if (e) e.classList.toggle('rtt-audio-on', S.root); };
  // mute leads the bank and is also the kill switch: muting stops everything sounding and (via the
  // body class the CSS keys off) hides every cell's hover speaker, so a clicked cell can't play.
  // Unmuting re-reveals the speakers but sounds nothing until the next click.
  api.toggleMute = function () { S.muted = !S.muted; if (S.muted) { stopAll(); hideFloat(); }
    const e = ctrlEl('mute'); if (e) e.innerHTML = api.glyphs.mute[S.muted ? 1 : 0];
    document.body.classList.toggle('rtt-audio-muted', S.muted); };
  if (document.body) document.body.classList.add('rtt-audio-muted');  // start muted (matches S.muted)
  // Close the AudioContext when the page is hidden / reloaded. Without this, each reload leaks its
  // context; a browser caps how many a tab may hold, so after enough reloads (a hot-reload session
  // reloads on every save) new contexts fail to construct and ALL audio dies until the tab is closed.
  window.addEventListener('pagehide', function () { if (ctx) { try { ctx.close(); } catch (e) {} ctx = null; } });
  // Per-COLUMN-SEGMENT audio affordance: a vector's entries aren't individually playable, so the
  // control applies to the whole interval column. Hovering any cell of a column segment lights the
  // segment (.rtt-spk-hover) and floats ONE speaker above it (tooltip-style, over the app); clicking
  // the float sounds the interval. Gated on unmuted; the chord is derived from the segment's sibling
  // cells live (reorder / retune safe). A grace timer lets the cursor cross the gap onto the button.
  let floatEl = null, floatSeg = null, hideT = null;
  function segCells(tile, idx) {
    return document.querySelectorAll('.rtt-spk[data-audio="' + tile + '"][data-idx="' + idx + '"]');
  }
  function clearHover() {
    const es = document.querySelectorAll('.rtt-spk-hover');
    for (let i = 0; i < es.length; i++) es[i].classList.remove('rtt-spk-hover');
  }
  function hideFloat() { if (floatEl) floatEl.classList.remove('rtt-spk-float-on'); clearHover(); floatSeg = null; }
  function keepFloat() { if (hideT) { clearTimeout(hideT); hideT = null; } }
  function planHide() { keepFloat(); hideT = setTimeout(hideFloat, 250); }
  function showFloat(tile, idx) {
    const cells = segCells(tile, idx); if (!cells.length) return;
    let l = Infinity, t = Infinity, r = -Infinity;
    for (let i = 0; i < cells.length; i++) { const k = cells[i].getBoundingClientRect(); l = Math.min(l, k.left); t = Math.min(t, k.top); r = Math.max(r, k.right); }
    if (!floatEl) {
      floatEl = document.createElement('div');
      floatEl.className = 'rtt-spk-float';
      floatEl.innerHTML = '<span class="material-icons">volume_up</span>';
      floatEl.addEventListener('mouseenter', keepFloat);
      floatEl.addEventListener('mouseleave', planHide);
      floatEl.addEventListener('click', function (ev) {
        ev.preventDefault(); ev.stopPropagation();
        if (!floatSeg) return;
        const chord = [], sibs = document.querySelectorAll('.rtt-spk[data-audio="' + floatSeg.tile + '"]');
        for (let i = 0; i < sibs.length; i++) chord[+sibs[i].dataset.idx] = +sibs[i].dataset.cents;
        api.hit(floatSeg.tile, floatSeg.idx, chord);
      });
      document.body.appendChild(floatEl);
    }
    floatEl.style.left = ((l + r) / 2) + 'px';   // centred over the column, floated above its top
    floatEl.style.top = t + 'px';
    floatEl.classList.add('rtt-spk-float-on');
    clearHover();
    for (let i = 0; i < cells.length; i++) cells[i].classList.add('rtt-spk-hover');
    floatSeg = { tile: tile, idx: idx };
  }
  document.addEventListener('mouseover', function (ev) {
    if (S.muted) return;                                   // muted = disengaged: no hover affordance
    const cell = ev.target.closest && ev.target.closest('.rtt-spk[data-audio]');
    if (!cell) return;
    keepFloat();
    showFloat(cell.dataset.audio, +cell.dataset.idx);
  });
  document.addEventListener('mouseout', function (ev) {
    const cell = ev.target.closest && ev.target.closest('.rtt-spk[data-audio]');
    if (!cell) return;
    const to = ev.relatedTarget && ev.relatedTarget.closest && ev.relatedTarget.closest('.rtt-spk[data-audio],.rtt-spk-float');
    if (!to) planHide();                                   // left the column for something non-audio
  });
  return api;
})();
