(() => {
  if (window.__rttMapDemo) return;
  window.__rttMapDemo = true;
  const NS = 'http://www.w3.org/2000/svg';
  const CH = 8; // half a chip — the × box's reach above its anchor point
  const TAIL = 12; // the little horizontal run into the result box, after the sum line jerks up

  // two palettes from the preview-highlighting set: amber (a "change") routes the operand in (left and
  // down jaunts, × boxes); green (an "addition") accumulates the result (right jaunts, product/+ boxes).
  const AMBER = { stroke: 'var(--preview-color)', fill: 'color-mix(in srgb, var(--preview-color) 22%, #fff)', ink: 'var(--preview-text-color)' };
  const GREEN = { stroke: 'var(--pending-color)', fill: 'color-mix(in srgb, var(--pending-color) 22%, #fff)', ink: 'var(--pending-text-color)' };

  // a tiny exact-rational type — the projection/superspace matrices carry fractions like 1/4, so the
  // products and sums must stay exact rather than float.
  const FR = (() => {
    const gcd = (a, b) => { a = Math.abs(a); b = Math.abs(b); while (b) { [a, b] = [b, a % b]; } return a || 1; };
    const mk = (n, d) => { if (d < 0) { n = -n; d = -d; } const k = gcd(n, d); return { n: n / k, d: d / k }; };
    const parse = (s) => {
      s = (s || '').replace(/[−–—]/g, '-').replace(/⁄/g, '/').trim();
      let m;
      if ((m = s.match(/^(-?\d+)\/(-?\d+)$/))) return mk(+m[1], +m[2]);
      if (/^-?\d+$/.test(s)) return mk(+s, 1);
      return null;
    };
    const mul = (a, b) => mk(a.n * b.n, a.d * b.d);
    const add = (a, b) => mk(a.n * b.d + b.n * a.d, a.d * b.d);
    const str = (a) => { const sign = a.n < 0 ? '−' : ''; const n = Math.abs(a.n); return a.d === 1 ? sign + n : sign + n + '/' + a.d; };
    return { parse, mul, add, str };
  })();

  // each flow is one "matrix × interval-vector" computation. Source/result cells are linked to the
  // matrix purely by geometry (shared column x, top-to-bottom order), so the differing id grammars and
  // raw-vs-token column keys across mapping/projection/superspace don't matter.
  const sel = (...prefixes) => prefixes.map((p) => '[data-eid^="' + p + '"]').join(',');
  const VEC = sel('cell:vec:targets:', 'cell:held:', 'cell:interest:', 'cell:comma:', 'cell:unchanged:', 'cell:vec:detempering:');
  const MAPPED = sel('cell:mapped:', 'cell:hmapped:', 'cell:imapped:', 'cell:mapped_comma:', 'cell:mapped_unchanged:', 'cell:mapped_detempering:');
  const PROJ = sel('cell:proj_pt:', 'cell:proj_ph:', 'cell:proj_pi:', 'cell:proj_pd:', 'cell:proj_v:');
  const SSVEC = sel('cell:ss_vectors:targets:', 'cell:ss_vectors:held:', 'cell:ss_vectors:interest:', 'cell:ss_vectors:commas:', 'cell:ss_vectors:detempering:');
  const SSMAP = sel('cell:ss_mapping:targets:', 'cell:ss_mapping:held:', 'cell:ss_mapping:interest:', 'cell:ss_mapping:commas:', 'cell:ss_mapping:detempering:');
  const SSPROJ = sel('cell:ss_proj_pt:', 'cell:ss_proj_ph:', 'cell:ss_proj_pi:', 'cell:ss_proj_pd:', 'cell:ss_proj_v:');

  const FLOWS = [
    { name: 'mapping', trigger: VEC + ',' + MAPPED, source: VEC, matrix: '[data-eid^="cell:mapping:"]', result: MAPPED },
    { name: 'projection', trigger: PROJ, source: VEC, matrix: '[data-eid^="cell:proj:"]', result: PROJ },
    { name: 'ss_mapping', trigger: SSVEC + ',' + SSMAP, source: SSVEC, matrix: '[data-eid^="cell:ss_mapping:ssprimes:"]', result: SSMAP },
    { name: 'ss_projection', trigger: SSPROJ, source: SSVEC, matrix: '[data-eid^="cell:ss_projection:ssprimes:"]', result: SSPROJ },
  ];

  let svg = null, curKey = null;
  const board = () => document.querySelector('.rtt-gridcontent');
  const active = () => document.body.classList.contains('rtt-mapping-demos');

  const ensureSvg = (b) => {
    if (svg && svg.parentNode === b) return svg;
    svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'rtt-demo-overlay');
    b.appendChild(svg);
    return svg;
  };
  const clear = () => { if (svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); svg.style.display = 'none'; } curKey = null; };

  const text = (el) => { const i = el.querySelector('input'); return (i && i.value !== '') ? i.value : el.textContent; };

  // ---- svg primitives -------------------------------------------------------
  const line = (x1, y1, x2, y2, pal) => {
    const l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2);
    l.setAttribute('stroke', pal.stroke); l.setAttribute('stroke-width', '3'); l.setAttribute('stroke-linecap', 'round');
    svg.appendChild(l);
  };
  const path = (d, pal) => {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', d); p.setAttribute('fill', 'none');
    p.setAttribute('stroke', pal.stroke); p.setAttribute('stroke-width', '3');
    p.setAttribute('stroke-linecap', 'round'); p.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(p);
  };
  const glyph = (x, y, s, size, fill) => {
    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', x); t.setAttribute('y', y);
    t.setAttribute('text-anchor', 'middle'); t.setAttribute('dominant-baseline', 'central');
    t.setAttribute('font-size', size); t.setAttribute('fill', fill);
    t.setAttribute('font-family', "'STIX Two Text', Georgia, serif");
    t.textContent = s; svg.appendChild(t);
  };
  const chip = (cx, cy, s, sq, pal) => {
    const txt = String(s);
    const w = sq ? 16 : Math.max(16, 7 + txt.length * 7), h = 16;
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', cx - w / 2); r.setAttribute('y', cy - h / 2);
    r.setAttribute('width', w); r.setAttribute('height', h);
    r.setAttribute('rx', 4); r.setAttribute('fill', pal.fill); r.setAttribute('stroke', pal.stroke); r.setAttribute('stroke-width', '1.5');
    svg.appendChild(r);
    glyph(cx, cy, txt, 11, pal.ink);
  };
  const ring = (c, pal) => {
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', c.l + 1); r.setAttribute('y', c.t + 1);
    r.setAttribute('width', c.w - 2); r.setAttribute('height', c.h - 2);
    r.setAttribute('fill', 'none'); r.setAttribute('stroke', pal.stroke); r.setAttribute('stroke-width', '3');
    svg.appendChild(r);
  };

  const cluster = (vals) => {
    const s = [...vals].sort((a, z) => a - z), out = [];
    for (const v of s) if (!out.length || v - out[out.length - 1] > 6) out.push(v);
    return out;
  };

  // ---- draw -----------------------------------------------------------------
  const draw = (flow, hov) => {
    const b = board();
    if (!b) return false;
    const bRect = b.getBoundingClientRect();
    const C = (el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left - bRect.left + r.width / 2, y: r.top - bRect.top + r.height / 2,
               t: r.top - bRect.top, btm: r.bottom - bRect.top, l: r.left - bRect.left, rt: r.right - bRect.left, w: r.width, h: r.height };
    };
    const colX = C(hov).x;
    const inCol = (o) => Math.abs(o.c.x - colX) < 8;

    const src = [...document.querySelectorAll(flow.source)].map((el) => ({ c: C(el), v: FR.parse(text(el)) }))
      .filter(inCol).sort((a, z) => a.c.y - z.c.y);
    const mcells = [...document.querySelectorAll(flow.matrix)].map((el) => ({ c: C(el), m: FR.parse(text(el)) }));
    const res = [...document.querySelectorAll(flow.result)].map((el) => ({ c: C(el) }))
      .filter(inCol).sort((a, z) => a.c.y - z.c.y);
    if (!src.length || !mcells.length || !res.length) return false;

    const ux = cluster(mcells.map((o) => o.c.x)), uy = cluster(mcells.map((o) => o.c.y));
    const at = (i, p) => mcells.find((o) => Math.abs(o.c.y - uy[i]) < 6 && Math.abs(o.c.x - ux[p]) < 6);
    const P = Math.min(src.length, ux.length), R = Math.min(res.length, uy.length);
    if (!P || !R) return false;
    const W = mcells[0].c.w;

    ensureSvg(b);
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.style.display = 'block';
    const SW = Math.max(b.scrollWidth, b.offsetWidth), SH = Math.max(b.scrollHeight, b.offsetHeight);
    svg.setAttribute('width', SW); svg.setAttribute('height', SH); svg.setAttribute('viewBox', '0 0 ' + SW + ' ' + SH);

    const gap = Math.min(12, (W * 0.5) / Math.max(1, R - 1));

    // (A) operand fan: each prime count splits into one line per matrix row — shared leftward bus, then
    // split descents; row 0 into the top of its × box, later rows peeling left into the box's left edge.
    for (let p = 0; p < P; p++) {
      const box0 = at(0, p); if (!box0) continue;
      const leftEdge = box0.c.l, vy = src[p].c.y;
      const tracks = []; for (let i = 0; i < R; i++) tracks.push(i === 0 ? leftEdge : leftEdge - i * gap);
      line(Math.min(...tracks), vy, src[p].c.l, vy, AMBER);
      for (let i = 0; i < R; i++) {
        const box = at(i, p); if (!box) continue;
        if (i === 0) line(leftEdge, vy, leftEdge, box.c.y - CH, AMBER);
        else path('M ' + tracks[i] + ' ' + vy + ' V ' + box.c.y + ' H ' + leftEdge, AMBER);
      }
    }

    // (B) running sum per row: emerge from the first product, ride the bottom edge through products/+s,
    // stay low across the gap, then jerk up just left of the result box and run a tiny horizontal tail
    // into the centre of its left edge (so the entry reads as distinct from the box's own outline).
    for (let i = 0; i < R; i++) {
      const first = at(i, 0), last = at(i, P - 1); if (!first || !last) continue;
      const riseX = Math.max(last.c.rt, res[i].c.l - TAIL);
      path('M ' + first.c.x + ' ' + first.c.btm + ' H ' + riseX + ' V ' + res[i].c.y + ' H ' + res[i].c.l, GREEN);
    }

    // (C) per-box marks: × on the left edge, the product on the bottom edge, + at the shared corners.
    for (let i = 0; i < R; i++) {
      for (let p = 0; p < P; p++) {
        const cell = at(i, p); if (!cell) continue;
        chip(cell.c.l, cell.c.y, '×', true, AMBER);
        const prod = (cell.m && src[p].v) ? FR.mul(cell.m, src[p].v) : null;
        if (prod) chip(cell.c.x, cell.c.btm, FR.str(prod), false, GREEN);
        if (p < P - 1) chip(cell.c.rt, cell.c.btm, '+', true, GREEN);
      }
    }

    // (D) rings on both ends: the operand vector (amber) and the result vector (green).
    for (let p = 0; p < P; p++) ring(src[p].c, AMBER);
    for (let i = 0; i < R; i++) ring(res[i].c, GREEN);
    return true;
  };

  const hovered = (node) => {
    if (!node || !node.closest) return null;
    for (const flow of FLOWS) { const cell = node.closest(flow.trigger); if (cell) return { flow, cell }; }
    return null;
  };
  const keyOf = (h) => h.flow.name + ':' + Math.round(h.cell.getBoundingClientRect().left);

  document.addEventListener('mouseover', (e) => {
    if (!active()) { if (curKey) clear(); return; }
    const h = hovered(e.target);
    if (!h) return;
    const key = keyOf(h);
    if (key === curKey) return;
    if (draw(h.flow, h.cell)) curKey = key;
  });
  document.addEventListener('mouseout', (e) => {
    if (!curKey) return;
    const h = hovered(e.relatedTarget);
    if (h && keyOf(h) === curKey) return;
    clear();
  });
  window.addEventListener('scroll', () => { if (curKey) clear(); }, { capture: true, passive: true });
  document.addEventListener('pointerdown', () => { if (curKey) clear(); }, true);
})()
