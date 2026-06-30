window.rttAudio = (function () {
  let context = null;
  const WAVES = ['sine', 'square', 'triangle', 'sawtooth'], BASE = 261.6255653005986, STEP = 0.34;
  // ONE global config + playing-state drives every speaker (the single bank on the dummy tile cycles
  // it); a speaker's `tile` is used ONLY to pick which speakers to highlight while they ring. The
  // hold-stack (mode 0) keys its held notes by tile:index so each speaker toggles on/off independently
  // even though the waveform / mode / hold / root config is shared.
  // `live` is EVERY currently-sounding voice's release fn — the kill switch (stopAll) clears it, so a
  // note/drone can always be silenced no matter how it was started (S.stop/S.held don't track them all).
  const S = { wave: 0, mode: 0, hold: false, root: false, muted: false, stop: null, finish: null, held: {}, live: new Set() };
  const api = { glyphs: null };
  function actx() {
    if (!context) context = new (window.AudioContext || window.webkitAudioContext)();
    if (context.state === 'suspended') context.resume();
    return context;
  }
  function hl(tile, index, on) {  // light EVERY cell sharing this voice (a vector column shares one index)
    const es = document.querySelectorAll('.rtt-speaker[data-audio="' + tile + '"][data-idx="' + index + '"]');
    for (let i = 0; i < es.length; i++) es[i].classList.toggle('rtt-speaker-on', on);
  }
  function clearHl(tile) {
    const es = document.querySelectorAll('.rtt-speaker[data-audio="' + tile + '"]');
    for (let i = 0; i < es.length; i++) es[i].classList.remove('rtt-speaker-on');
  }
  function vgain(n) { return 0.45 / Math.max(1, n); }
  // start one oscillator; returns a release() that fades it out (and clears its highlight)
  function voice(tile, index, cents, gain) {
    const ac = actx(), o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime;
    o.type = WAVES[S.wave];
    o.frequency.value = BASE * Math.pow(2, cents / 1200);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(gain, t + 0.012);
    o.connect(g); g.connect(ac.destination); o.start(t);
    if (index >= 0) hl(tile, index, true);
    let done = false;
    function release() {
      if (done) return; done = true;
      S.live.delete(release);
      const r = actx().currentTime;
      g.gain.cancelScheduledValues(r);
      g.gain.setValueAtTime(Math.max(g.gain.value, 0.0001), r);
      g.gain.exponentialRampToValueAtTime(0.0001, r + 0.09);
      o.stop(r + 0.12);
      if (index >= 0) setTimeout(function () { hl(tile, index, false); }, 110);
    }
    S.live.add(release);
    return release;
  }
  // sound a set of {index,cents} together (+ optional root drone); returns a stop()
  function together(tile, items, root) {
    const g = vgain(items.length + (root ? 1 : 0)), rels = [];
    for (let i = 0; i < items.length; i++) rels.push(voice(tile, items[i].index, items[i].cents, g));
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
              for (let i = 0; i < rels.length; i++) rels[i]();  // end the pass...
              if (loop) pass();                                 // ...repeat only while the lock is still on
              else { if (rootRel) rootRel(); clearHl(tile); }   // lock turned off mid-loop: finish here, no repeat
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
    return {  // stop() = hard kill (mute); finish() = stop looping but let the current pass play out (lock off)
      stop: function () {
        stopped = true;
        for (let i = 0; i < timers.length; i++) clearTimeout(timers[i]);
        for (let i = 0; i < rels.length; i++) rels[i]();
        if (rootRel) rootRel();
        clearHl(tile);
      },
      finish: function () { loop = false; }
    };
  }
  function ctrlEl(ctrl) {  // the single dummy-tile bank control (data-actrl only — no per-tile copies)
    return document.querySelector('[data-actrl="' + ctrl + '"]');
  }
  api.hit = function (tile, index, cents) {
    if (S.muted) return;                                  // muted: the kill switch is also the gate
    if (S.mode === 0) {                                   // one-off / hold-stack
      if (!S.hold) { const stop = together(tile, [{ index: index, cents: cents[index] }], S.root); setTimeout(stop, 650); return; }
      const key = tile + ':' + index;                       // hold-stack: key per speaker so each toggles alone
      if (S.held[key]) { S.held[key](); delete S.held[key]; }   // click a held note off
      else { S.held[key] = together(tile, [{ index: index, cents: cents[index] }], S.root); }
      return;
    }
    if (S.stop) { S.stop(); S.stop = null; S.finish = null; if (S.hold) return; }  // a second click stops it
    if (S.mode === 1) {                                   // arpeggiate, always from the leftmost pitch
      const order = []; for (let k = 0; k < cents.length; k++) order.push(k);  // (float is per-tile; index is moot)
      const seq = sequence(tile, order, cents, S.root, false, S.hold);
      if (S.hold) { S.stop = seq.stop; S.finish = seq.finish; }   // held arp loops; lock-off finishes the pass
    } else if (S.mode === 2) {                            // chord: all together
      const items = []; for (let i = 0; i < cents.length; i++) items.push({ index: i, cents: cents[i] });
      const stop = together(tile, items, S.root);
      if (S.hold) { S.stop = stop; S.finish = null; }     // a held chord sustains; lock-off releases it (no pass)
      else setTimeout(stop, 1000);
    } else {                                              // rolled chord
      const order = []; for (let i = 0; i < cents.length; i++) order.push(i);
      const seq = sequence(tile, order, cents, S.root, true, S.hold);
      if (S.hold) { S.stop = seq.stop; S.finish = seq.finish; }   // held rolled chord loops; lock-off finishes it
    }
  };
  function stopAll() {  // the HARD kill (mute / mode change): stop the looping/held sequence outright (stop()
    if (S.stop) { S.stop(); S.stop = null; }              // clears its timers + `stopped` flag), drop the graceful
    S.finish = null;                                       // finish handle, release the hold-stack, and sweep any
    for (const k in S.held) S.held[k](); S.held = {};     // voice still live (a one-shot's leaked root) — so a
    Array.from(S.live).forEach(function (r) { r(); });    // loop, a held note or a stuck drone ALL die now
    S.live.clear();
  }
  api.cycleWave = function () { S.wave = (S.wave + 1) % 4;
    const e = ctrlEl('wave'); if (e) e.innerHTML = api.glyphs.wave[S.wave]; };
  api.cycleMode = function () { stopAll(); S.mode = (S.mode + 1) % 4;
    const e = ctrlEl('mode'); if (e) e.innerHTML = api.glyphs.mode[S.mode]; };
  api.toggleHold = function () {
    S.hold = !S.hold;
    if (!S.hold) {                                        // lock OFF: don't hard-cut — let a loop's current pass
      if (S.finish) { S.finish(); S.finish = null; }      // finish (then stop, no repeat); a sustained chord or
      else if (S.stop) { S.stop(); S.stop = null; }       // held note has no pass to finish, so just release it
      for (const k in S.held) S.held[k](); S.held = {};
    }
    const e = ctrlEl('hold'); if (e) { e.innerHTML = api.glyphs.lock[S.hold ? 1 : 0]; e.classList.toggle('rtt-audio-on', S.hold); }
  };
  api.toggleRoot = function () { S.root = !S.root;
    const e = ctrlEl('root'); if (e) e.classList.toggle('rtt-audio-on', S.root); };
  // mute leads the bank and is also the kill switch: muting stops everything sounding and (via the
  // body class the CSS keys off) hides every cell's hover speaker, so a clicked cell can't play.
  // Unmuting re-reveals the speakers but sounds nothing until the next click.
  api.toggleMute = function () { S.muted = !S.muted; if (S.muted) { stopAll(); hideFloat(); }
    const e = ctrlEl('mute'); if (e) e.innerHTML = api.glyphs.mute[S.muted ? 1 : 0];
    document.body.classList.toggle('rtt-audio-muted', S.muted); };
  if (document.body && S.muted) document.body.classList.add('rtt-audio-muted');
  // Close the AudioContext when the page is hidden / reloaded. Without this, each reload leaks its
  // context; a browser caps how many a tab may hold, so after enough reloads (a hot-reload session
  // reloads on every save) new contexts fail to construct and ALL audio dies until the tab is closed.
  window.addEventListener('pagehide', function () { if (context) { try { context.close(); } catch (e) {} context = null; } });
  // Per-COLUMN-SEGMENT audio affordance: a vector's entries aren't individually playable, so the
  // control applies to the whole interval column. Hovering any cell of a column segment lights the
  // segment (.rtt-speaker-hover) and floats ONE speaker above it (tooltip-style, over the app); clicking
  // the float sounds the interval. Gated on unmuted; the chord is derived from the segment's sibling
  // cells live (reorder / retune safe). A grace timer lets the cursor cross the gap onto the button.
  let floatElement = null, floatSeg = null, floatCells = null, hideT = null;
  function segCells(tile, index) {
    return document.querySelectorAll('.rtt-speaker[data-audio="' + tile + '"][data-idx="' + index + '"]');
  }
  function placeFloat() {  // (re)anchor the float over its live cells — viewport coords, so it must
    if (!floatElement || !floatCells || !floatCells.length) return;   // re-run on scroll or it slides away
    let l = Infinity, t = Infinity, r = -Infinity, any = false;
    for (let i = 0; i < floatCells.length; i++) {
      if (!floatCells[i].isConnected) continue;
      const k = floatCells[i].getBoundingClientRect();
      l = Math.min(l, k.left); t = Math.min(t, k.top); r = Math.max(r, k.right); any = true;
    }
    if (!any) { hideFloat(); return; }
    floatElement.style.left = ((l + r) / 2) + 'px';
    floatElement.style.top = t + 'px';
  }
  function clearHover() {
    const es = document.querySelectorAll('.rtt-speaker-hover, .rtt-speaker-dim');
    for (let i = 0; i < es.length; i++) es[i].classList.remove('rtt-speaker-hover', 'rtt-speaker-dim');
  }
  function hideFloat() { if (floatElement) floatElement.classList.remove('rtt-speaker-float-on'); clearHover(); floatSeg = null; floatCells = null; }
  function keepFloat() { if (hideT) { clearTimeout(hideT); hideT = null; } }
  function planHide() { keepFloat(); hideT = setTimeout(hideFloat, 250); }
  function showFloat(tile, index) {
    const all = document.querySelectorAll('.rtt-speaker[data-audio="' + tile + '"]');
    if (!all.length) return;
    clearHover();
    // single-note mode lights just the hovered column SEGMENT; chord / arp modes light the WHOLE tile
    // (hovered column bright, the rest dim) to preview that every pitch plays, and float over them all.
    let cells;
    if (S.mode === 0) {
      cells = segCells(tile, index);
      for (let i = 0; i < cells.length; i++) cells[i].classList.add('rtt-speaker-hover');
    } else {
      cells = all; const key = String(index);
      for (let i = 0; i < all.length; i++) all[i].classList.add(all[i].dataset.idx === key ? 'rtt-speaker-hover' : 'rtt-speaker-dim');
    }
    floatCells = Array.prototype.slice.call(cells);
    if (!floatElement) {
      floatElement = document.createElement('div');
      floatElement.className = 'rtt-speaker-float';
      floatElement.innerHTML = '<span class="material-icons">volume_up</span>';
      floatElement.addEventListener('mouseenter', keepFloat);
      floatElement.addEventListener('mouseleave', planHide);
      floatElement.addEventListener('click', function (event) {
        event.preventDefault(); event.stopPropagation();
        if (floatSeg) api.playSeg(floatSeg.tile, floatSeg.index);
      });
      document.body.appendChild(floatElement);
    }
    floatElement.classList.add('rtt-speaker-float-on');
    floatSeg = { tile: tile, index: index };
    placeFloat();   // centred over the highlighted cells, floated above them
  }
  api.playSeg = function (tile, index) {  // sound a whole column segment (its live sibling chord)
    const chord = [], sibs = document.querySelectorAll('.rtt-speaker[data-audio="' + tile + '"]');
    for (let i = 0; i < sibs.length; i++) chord[+sibs[i].dataset.idx] = +sibs[i].dataset.cents;
    api.hit(tile, index, chord);
  };
  function onFloat(t) { return t && t.closest && t.closest('.rtt-speaker-float'); }
  document.addEventListener('mouseover', function (event) {
    if (S.muted) return;                                   // muted = disengaged: no hover affordance
    const cell = event.target.closest && event.target.closest('.rtt-speaker[data-audio]');
    if (!cell) {
      if (floatSeg && !onFloat(event.target)) planHide();     // moved onto something else: let it go
      return;
    }
    keepFloat();
    showFloat(cell.dataset.audio, +cell.dataset.idx);
  });
  document.addEventListener('mouseout', function (event) {
    const cell = event.target.closest && event.target.closest('.rtt-speaker[data-audio]');
    if (!cell) return;
    const to = event.relatedTarget && event.relatedTarget.closest && event.relatedTarget.closest('.rtt-speaker[data-audio],.rtt-speaker-float');
    if (!to) planHide();                                   // left the column for something non-audio
  });
  // a click or keypress anywhere but the float (e.g. a re-render the cursor never left) dismisses a
  // stuck float, so it can't linger over the grid and block hovering the next cell.
  document.addEventListener('pointerdown', function (event) {
    if (floatSeg && !onFloat(event.target)) hideFloat();
  }, true);
  // Space is the play key (sounded by _ACTIVECELL_JS for the active/hovered cell) — don't let it
  // dismiss the float; any OTHER key clears a lingering float so it can't block the next hover.
  document.addEventListener('keydown', function (event) { if (event.key !== ' ' && floatSeg) hideFloat(); }, true);
  // the grid body scrolls in its own scroller (scroll doesn't bubble) — re-anchor the float to its
  // live cells so it rides the page instead of staying pinned to a viewport spot as the grid moves.
  document.addEventListener('scroll', function () { if (floatSeg) placeFloat(); }, true);
  return api;
})();
