(function () {
  if (window.__rttScoreModal) return;
  window.__rttScoreModal = true;
  // Comma-pump sheet music modal. Opened by the float's pump toggles (audio.js calls
  // rttScore.pumpClicked) whenever the comma's payload carries a Prime-Factor-notation score.
  // The tempered pump is a single looping set of bars: one whole-note chord per bar between
  // repeat barlines, each labelled with its ~ratio, a scorewriter-style cursor sweeping each
  // bar in time with the audio. The just flavor plays audio-only for now: its notation must
  // drift by the comma each pass, a display not designed yet, so the sheet dims instead.
  const BAR_MIN = 118, CLEF_W = 34, LINE_H = 172, TOP_PAD = 14, MAX_LINE_W = 700, X0 = 8;
  const S = { root: null, sheet: null, svgWrap: null, cursor: null, caption: null, jbtn: null, tbtn: null,
              open: false, index: -1, flavor: 't', payload: '', d: null, size: 0, type: 'mixed', bars: [] };
  let vexQueue = null;
  function ensureVex(ready) {
    if (window.Vex && window.Vex.Flow) return ready();
    if (vexQueue) { vexQueue.push(ready); return; }
    vexQueue = [ready];
    const tag = document.createElement('script');
    tag.src = (window.rttScoreCfg && rttScoreCfg.vexUrl) || '/rtt-assets/vexflow-bravura.js';
    tag.onload = function () { const q = vexQueue; vexQueue = null; for (let i = 0; i < q.length; i++) q[i](); };
    document.head.appendChild(tag);
  }
  function build() {
    if (S.root) return;
    const root = document.createElement('div');
    root.className = 'rtt-score-root';
    root.innerHTML =
      '<div class="rtt-score-backdrop"></div>' +
      '<div class="rtt-score-modal" role="dialog" aria-label="comma pump notation">' +
        '<div class="rtt-score-head">' +
          '<span class="rtt-score-caption"></span>' +
          '<span class="rtt-pump-btn rtt-pump-just" title="Loop this comma’s pump in just intonation — each cycle drifts by the comma."><span class="material-icons">repeat</span>just</span>' +
          '<span class="rtt-pump-btn rtt-pump-tempered" title="Loop this comma’s pump in the tempered tuning — the drift is tempered out, so it closes."><span class="material-icons">repeat</span>tempered</span>' +
          '<span class="rtt-score-close material-icons" title="Stop the pump and close">close</span>' +
        '</div>' +
        '<div class="rtt-score-sheet"><div class="rtt-score-svg"></div><div class="rtt-score-cursor"></div></div>' +
        '<div class="rtt-score-footnote">just-pump notation is still being designed — audio only for now</div>' +
      '</div>';
    document.body.appendChild(root);
    S.root = root;
    S.sheet = root.querySelector('.rtt-score-sheet');
    S.svgWrap = root.querySelector('.rtt-score-svg');
    S.cursor = root.querySelector('.rtt-score-cursor');
    S.caption = root.querySelector('.rtt-score-caption');
    S.jbtn = root.querySelector('.rtt-pump-just');
    S.tbtn = root.querySelector('.rtt-pump-tempered');
    root.querySelector('.rtt-score-backdrop').addEventListener('click', close);
    root.querySelector('.rtt-score-close').addEventListener('click', close);
    S.jbtn.addEventListener('click', function () { toggle('ji'); });
    S.tbtn.addEventListener('click', function () { toggle('t'); });
  }
  function toggle(flavor) {
    if (!window.rttAudio) return;
    S.flavor = flavor;
    rttAudio.pumpToggle(S.index, flavor, S.payload);
    mode();
    sync();
  }
  function mode() {
    if (S.root) S.root.classList.toggle('rtt-score-ji', S.flavor === 'ji');
  }
  function sync() {
    if (!S.root || !S.open || !window.rttAudio) return;
    const state = rttAudio.pumpState();
    S.jbtn.classList.toggle('rtt-audio-on', state === S.index + ':ji');
    S.tbtn.classList.toggle('rtt-audio-on', state === S.index + ':t');
  }
  function close() {
    if (!S.open) return;
    S.open = false;
    if (window.rttAudio && rttAudio.pumpKill) rttAudio.pumpKill();
    S.root.classList.remove('rtt-score-on', 'rtt-score-playing');
    document.body.classList.remove('rtt-score-open');
  }
  function pumpClicked(index, flavor, payload) {
    if (!payload) return false;
    let parsed;
    try { parsed = payload === S.payload ? S.d : JSON.parse(payload); } catch (e) { return false; }
    if (!parsed || !parsed.score) return false;
    build();
    S.index = index; S.flavor = flavor; S.payload = payload; S.d = parsed;
    S.open = true;
    S.caption.textContent = parsed.score.comma + ' pump';
    S.root.classList.add('rtt-score-on');
    S.root.classList.remove('rtt-score-playing');
    document.body.classList.add('rtt-score-open');
    mode();
    sync();
    ensureVex(render);
    return true;
  }
  // chord voicing mirrors audio.js pumpChord: the payload spells every tone of each chord per
  // chord type; 'mixed' is the pump's own per-chord quality, and the first N tones are what the
  // current chord-size setting sounds.
  function chordVoices(step) {
    const chord = S.d.score.steps[step].tones;
    const spelled = chord[S.type] || chord.mixed;
    return spelled.slice(0, Math.max(1, S.size)).map(function (spec) { return { spec: spec }; });
  }
  const DIATONIC = { c: 0, d: 1, e: 2, f: 3, g: 4, a: 5, b: 6 };
  const CONVENTIONAL = { '1': '#', '2': '##', '-1': 'b', '-2': 'bb' };
  function makeBar(VF, score, k) {
    const voices = chordVoices(k).map(function (v) {
      const letter = v.spec.p[0], octave = +v.spec.p.split('/')[1];
      return { key: letter + '/' + octave, order: octave * 7 + DIATONIC[letter], spec: v.spec };
    }).sort(function (a, b) { return a.order - b.order; });
    // no align_center: VexFlow centers only the notehead, so a wide accidental stack would hang
    // left across the barline; left-aligned notes let the formatter reserve the stack's room
    const note = new VF.StaveNote({ keys: voices.map(function (v) { return v.key; }), duration: 'w' });
    voices.forEach(function (v, i) {
      // VexFlow renders same-note accidentals first-added-nearest, so feed it the stack
      // inside-out: conventional sharp/flat innermost, then sagittals largest-alteration-first
      // — on the page that reads smallest … largest, #/b, notehead (the t=99 ordering).
      const conventional = CONVENTIONAL[String(v.spec.s)];
      if (conventional) note.addModifier(new VF.Accidental(conventional), i);
      for (let g = v.spec.g.length - 1; g >= 0; g--) note.addModifier(new VF.Accidental(v.spec.g[g]), i);
    });
    const label = new VF.Annotation('~' + score.steps[k].r);
    label.setFont('STIX Two Text', 11);
    label.setVerticalJustification(VF.Annotation.VerticalJustify.TOP);
    note.addModifier(label, 0);
    const voice = new VF.Voice({ num_beats: 4, beat_value: 4 }).setMode(VF.Voice.Mode.SOFT);
    voice.addTickables([note]);
    return voice;
  }
  function render() {
    if (!S.open || !window.Vex) return;
    const VF = Vex.Flow, score = S.d.score, n = score.steps.length;
    const config = window.rttAudio ? rttAudio.pumpConfig() : { size: 1, type: 'mixed' };
    S.size = config.size;
    S.type = config.type || 'mixed';
    S.bars = [];
    S.svgWrap.innerHTML = '';
    S.root.classList.remove('rtt-score-playing');
    // pass 1: measure each bar's content so accidental stacks widen their bar instead of spilling
    const widths = [];
    for (let k = 0; k < n; k++) {
      const min = new VF.Formatter().joinVoices([makeBar(VF, score, k)]).preCalculateMinTotalWidth([makeBar(VF, score, k)]);
      widths.push(Math.max(BAR_MIN, Math.ceil(min) + 42));
    }
    // pass 2: wrap bars into systems by width
    const slots = [];
    let x = X0, line = 0;
    for (let k = 0; k < n; k++) {
      let first = x === X0;
      if (!first && x + widths[k] > X0 + MAX_LINE_W) { x = X0; line++; first = true; }
      const w = widths[k] + (first ? CLEF_W : 0);
      slots.push({ x: x, line: line, w: w, first: first });
      x += w;
    }
    const renderer = new VF.Renderer(S.svgWrap, VF.Renderer.Backends.SVG);
    let width = X0 + 8;
    for (let k = 0; k < n; k++) width = Math.max(width, slots[k].x + slots[k].w + 8);
    renderer.resize(width, TOP_PAD + (line + 1) * LINE_H + 40);
    const ctx = renderer.getContext();
    for (let k = 0; k < n; k++) {
      const stave = new VF.Stave(slots[k].x, TOP_PAD + slots[k].line * LINE_H, slots[k].w);
      if (slots[k].first) stave.addClef('treble');
      if (k === 0) stave.setBegBarType(VF.Barline.type.REPEAT_BEGIN);
      if (k === n - 1) stave.setEndBarType(VF.Barline.type.REPEAT_END);
      stave.setContext(ctx).draw();
      const voice = makeBar(VF, score, k);
      new VF.Formatter().joinVoices([voice]).formatToStave([voice], stave);
      voice.draw(ctx, stave);
      const drawn = voice.getTickables()[0];
      S.bars.push({
        x0: stave.getNoteStartX() + 2,
        x1: stave.getX() + stave.getWidth() - 5,
        nx: drawn.getAbsoluteX() + 6,
        y: stave.getYForLine(0) - 12,
        h: stave.getYForLine(4) - stave.getYForLine(0) + 24,
        line: slots[k].line,
        right: stave.getX() + stave.getWidth(),
        left: stave.getX(),
      });
    }
    const svg = S.svgWrap.querySelector('svg');
    if (score.moves) drawMoveTies(svg, score, n);
    // size the viewport to what was actually drawn: ledger notes below the last system (and any
    // overshoot above the first) must never clip
    const box = svg.getBBox();
    const top = Math.min(0, Math.floor(box.y) - 6), height = Math.ceil(box.y + box.height) + 12 - top;
    const fullWidth = Math.max(width, Math.ceil(box.x + box.width) + 8);
    svg.setAttribute('viewBox', '0 ' + top + ' ' + fullWidth + ' ' + height);
    svg.setAttribute('width', fullWidth);
    svg.style.width = fullWidth + 'px';
    svg.setAttribute('height', height);
    svg.style.height = height + 'px';
    if (top < 0) S.bars.forEach(function (b) { b.y -= top; });  // the viewBox shift moves the drawing; the cursor div lives in element pixels
    if (window.rttAudio && rttAudio.pumpLastStep) {
      const sounding = rttAudio.pumpLastStep();  // the first step fired before the modal existed — catch the cursor up
      if (sounding) onStep(sounding);
    }
  }
  // the root-motion row: each interval to the next chord rides a tie-like slur one row above the
  // pitch-ratio labels; the wrap back to 1/1 is the classic broken tie across the repeat — its
  // opening half leaves the last chord rightward, its closing half enters the first chord from
  // the left edge, and the ratio labels the opening half.
  function tiePiece(svg, x0, y0, x1, y1, apexY) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M ' + x0 + ' ' + y0 + ' Q ' + ((x0 + x1) / 2) + ' ' + apexY + ' ' + x1 + ' ' + y1);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-width', '1.1');
    path.setAttribute('class', 'rtt-score-tie');
    svg.appendChild(path);
  }
  function tieLabel(svg, x, y, move) {
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', x);
    text.setAttribute('y', y);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('font-family', "'STIX Two Text', serif");
    text.setAttribute('font-size', '11');
    text.setAttribute('class', 'rtt-score-tie-label');
    text.textContent = '~' + move;
    svg.appendChild(text);
  }
  function drawMoveTies(svg, score, n) {
    const RISE = 40, ARC = 16;
    for (let k = 0; k + 1 < n; k++) {
      const a = S.bars[k], b = S.bars[k + 1];
      const y = a.y - RISE + 12;
      if (a.line === b.line) {
        tiePiece(svg, a.nx, y, b.nx, y, y - ARC);
        tieLabel(svg, (a.nx + b.nx) / 2, y - ARC - 4, score.moves[k]);
      } else {
        tiePiece(svg, a.nx, y, a.right + 4, y - ARC * 0.7, y - ARC);
        tieLabel(svg, (a.nx + a.right) / 2, y - ARC - 4, score.moves[k]);
        const yb = b.y - RISE + 12;
        tiePiece(svg, b.left - 2, yb - ARC * 0.7, b.nx, yb, yb - ARC);
      }
    }
    const last = S.bars[n - 1], first = S.bars[0];
    const yl = last.y - RISE + 12;
    tiePiece(svg, last.nx, yl, last.right + 6, yl - ARC * 0.7, yl - ARC);
    tieLabel(svg, (last.nx + last.right + 6) / 2, yl - ARC - 4, score.moves[n - 1]);
    const yf = first.y - RISE + 12;
    tiePiece(svg, first.left - 4, yf - ARC * 0.7, first.nx, yf, yf - ARC);
  }
  function onStep(e) {
    if (!S.open || e.index !== S.index) return;
    if (window.rttAudio && (rttAudio.pumpConfig().size !== S.size || (rttAudio.pumpConfig().type || 'mixed') !== S.type)) render();
    if (e.flavor === 'ji') return;
    const bar = S.bars[e.step];
    if (!bar) return;
    S.root.classList.add('rtt-score-playing');
    const c = S.cursor;
    c.style.transition = 'none';
    c.style.left = bar.x0 + 'px';
    c.style.top = bar.y + 'px';
    c.style.height = bar.h + 'px';
    void c.offsetWidth;
    c.style.transition = 'left ' + e.ms + 'ms linear';
    c.style.left = bar.x1 + 'px';
  }
  function onStop() {
    if (!S.open || !S.cursor) return;
    const pinned = getComputedStyle(S.cursor).left;
    S.cursor.style.transition = 'none';
    S.cursor.style.left = pinned;
  }
  document.addEventListener('keydown', function (event) {
    if (S.open && event.key === 'Escape') {
      event.stopPropagation();
      event.preventDefault();
      close();
    }
  }, true);
  if (window.rttAudio) { rttAudio.onPumpStep = onStep; rttAudio.onPumpStop = onStop; }
  window.rttScore = { pumpClicked: pumpClicked, sync: sync, close: close, open: function () { return S.open; } };
})();
