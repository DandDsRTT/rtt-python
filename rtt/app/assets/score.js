(function () {
  if (window.__rttScoreModal) return;
  window.__rttScoreModal = true;
  // Comma-pump sheet music modal. Opened by the float's pump toggles (audio.js calls
  // rttScore.pumpClicked) whenever the comma's payload carries a Prime-Factor-notation score.
  // The tempered pump is a single looping set of bars: one whole-note chord per bar between
  // repeat barlines, each labelled with its ~ratio, a scorewriter-style cursor sweeping each
  // bar in time with the audio. The just flavor notates the same bars with exact ratios (no ~);
  // its per-pass drift by the comma is not yet displayed.
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
    const changed = S.flavor !== flavor;
    S.flavor = flavor;
    rttAudio.pumpToggle(S.index, flavor, S.payload);
    if (changed) render();
    sync();
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
    const commaParts = parsed.score.comma.split('/');
    S.caption.innerHTML = '<span class="rtt-score-cfrac"><span>' + commaParts[0] + '</span><span>' + (commaParts[1] || '1') + '</span></span> pump';
    S.root.classList.add('rtt-score-on');
    S.root.classList.remove('rtt-score-playing');
    document.body.classList.add('rtt-score-open');
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
      const noteX = drawn.getAbsoluteX() + 6;
      const pitchY = stave.getYForLine(0) - 26;
      const pitch = stackedRatio(S.svgWrap.querySelector('svg'), score.steps[k].r, PITCH_SIZE, 'rtt-score-ratio', S.flavor === 't');
      placeGroup(pitch, noteX, pitchY);
      S.bars.push({
        x0: stave.getNoteStartX() + 2,
        x1: stave.getX() + stave.getWidth() - 5,
        nx: noteX,
        tieY: pitchY - PITCH_SIZE - 2,
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
  // Ratios render as stacked fractions (numerator over a vinculum over denominator, whole
  // ratios as the bare numerator), a ~ set to the left. Returns the group so callers can
  // measure and center it.
  function stackedRatio(svg, ratio, numeralSize, className, approximate) {
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.setAttribute('class', className);
    const parts = ratio.split('/');
    const whole = parts.length < 2 || parts[1] === '1';
    function glyph(content, x, y, size, anchor) {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', x);
      text.setAttribute('y', y);
      text.setAttribute('text-anchor', anchor || 'middle');
      text.setAttribute('font-family', "'STIX Two Text', serif");
      text.setAttribute('font-size', size);
      text.setAttribute('font-weight', '600');
      text.textContent = content;
      group.appendChild(text);
      return text;
    }
    if (whole) {
      glyph((approximate ? '~' : '') + parts[0], 0, numeralSize * 0.36, numeralSize);
    } else {
      glyph(parts[0], 0, -1.5, numeralSize);
      glyph(parts[1], 0, numeralSize, numeralSize);
      const width = Math.max(parts[0].length, parts[1].length) * numeralSize * 0.52 + 2;
      const rule = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      rule.setAttribute('x1', -width / 2);
      rule.setAttribute('x2', width / 2);
      rule.setAttribute('y1', 1);
      rule.setAttribute('y2', 1);
      group.appendChild(rule);
      if (approximate) glyph('~', -width / 2 - 2, numeralSize * 0.36, numeralSize * 0.9, 'end');
    }
    svg.appendChild(group);
    return group;
  }
  function placeGroup(group, x, y) {
    group.setAttribute('transform', 'translate(' + x + ' ' + y + ')');
  }
  // Root motions ride a tie row just above the pitch ratios: each interval sits INSIDE its tie,
  // breaking the arc where it lies. The wrap home to 1/1 is the classic broken tie across the
  // repeat — the opening half (labelled) leaves the last chord rightward, the closing half
  // enters the first chord from the left edge. Consecutive ties never touch: each starts and
  // ends short of the chords it links.
  const TIE_ARC = 22, TIE_GAP = 12, PITCH_SIZE = 12, MOVE_SIZE = 10;
  function quadAt(x0, y0, cx, cy, x1, y1, t) {
    const u = 1 - t;
    return { x: u * u * x0 + 2 * u * t * cx + t * t * x1, y: u * u * y0 + 2 * u * t * cy + t * t * y1 };
  }
  // extract the sub-arc t in [ta, tb] of one quadratic — every tie piece on the page is a slice
  // of the same curve family, so full ties, split halves and label gaps all share one shape
  function quadPiece(svg, x0, y0, cx, cy, x1, y1, ta, tb) {
    const start = quadAt(x0, y0, cx, cy, x1, y1, ta);
    const end = quadAt(x0, y0, cx, cy, x1, y1, tb);
    const mid = quadAt(x0, y0, cx, cy, x1, y1, (ta + tb) / 2);
    const controlX = 2 * mid.x - (start.x + end.x) / 2, controlY = 2 * mid.y - (start.y + end.y) / 2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M ' + start.x + ' ' + start.y + ' Q ' + controlX + ' ' + controlY + ' ' + end.x + ' ' + end.y);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-width', '1.1');
    path.setAttribute('class', 'rtt-score-tie');
    svg.appendChild(path);
  }
  // a piece of tie with its ratio breaking the arc, the whole glyph block (tilde included)
  // centered in the gap, every label on one shared row
  function labelledPiece(svg, x0, y0, cx, cy, x1, y1, ta, tb, move, rowY) {
    const group = stackedRatio(svg, move, MOVE_SIZE, 'rtt-score-tie-label', S.flavor === 't');
    const box = group.getBBox();
    const centerX = quadAt(x0, y0, cx, cy, x1, y1, (ta + tb) / 2).x;
    const half = box.width / 2 + 5;
    const tL = Math.max(ta + 0.05, (centerX - half - x0) / (x1 - x0));
    const tR = Math.min(tb - 0.05, (centerX + half - x0) / (x1 - x0));
    quadPiece(svg, x0, y0, cx, cy, x1, y1, ta, tL);
    quadPiece(svg, x0, y0, cx, cy, x1, y1, tR, tb);
    placeGroup(group, centerX - (box.x + box.width / 2), rowY - (box.y + box.height / 2));
  }
  function drawMoveTies(svg, score, n) {
    const spans = [];
    for (let k = 0; k + 1 < n; k++) {
      if (S.bars[k].line === S.bars[k + 1].line) spans.push(S.bars[k + 1].nx - S.bars[k].nx - 2 * TIE_GAP);
    }
    const span = spans.length ? spans.sort(function (p, q) { return p - q; })[Math.floor(spans.length / 2)] : 110;
    function fullTie(a, b, move) {
      const x0 = a.nx + TIE_GAP, x1 = b.nx - TIE_GAP, y = a.tieY;
      labelledPiece(svg, x0, y, (x0 + x1) / 2, y - TIE_ARC, x1, y, 0, 1, move, y - TIE_ARC / 2);
    }
    function openingHalf(a, move) {
      const x0 = a.nx + TIE_GAP, x1 = x0 + span, y = a.tieY;
      quadPiece(svg, x0, y, (x0 + x1) / 2, y - TIE_ARC, x1, y, 0, 0.38);
      const tip = quadAt(x0, y, (x0 + x1) / 2, y - TIE_ARC, x1, y, 0.38);
      const group = stackedRatio(svg, move, MOVE_SIZE, 'rtt-score-tie-label', S.flavor === 't');
      const box = group.getBBox();
      placeGroup(group, tip.x + 6 - box.x, (y - TIE_ARC / 2) - (box.y + box.height / 2));
    }
    function closingHalf(b) {
      const x1 = b.nx - TIE_GAP, x0 = x1 - span, y = b.tieY;
      const clamp = Math.max(0.62, (2 - x0) / (x1 - x0));
      quadPiece(svg, x0, y, (x0 + x1) / 2, y - TIE_ARC, x1, y, clamp, 1);
    }
    for (let k = 0; k + 1 < n; k++) {
      const a = S.bars[k], b = S.bars[k + 1];
      if (a.line === b.line) fullTie(a, b, score.moves[k]);
      else { openingHalf(a, score.moves[k]); closingHalf(b); }
    }
    openingHalf(S.bars[n - 1], score.moves[n - 1]);
    closingHalf(S.bars[0]);
  }
  function onStep(e) {
    if (!S.open || e.index !== S.index) return;
    if (window.rttAudio && (rttAudio.pumpConfig().size !== S.size || (rttAudio.pumpConfig().type || 'mixed') !== S.type)) render();
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
