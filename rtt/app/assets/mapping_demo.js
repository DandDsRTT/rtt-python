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

  // The grid holds two interval-vector spaces — prime-basis vectors and superspace-lifted vectors —
  // each in one of every interval kind (targets / held / interest / commas / unchanged / detempering).
  const STD_VEC = /^cell:(vector:targets|held|interest|comma|unchanged|vector:detempering):/;
  const SS_VEC = /^cell:superspace_vectors:(targets|held|interest|commas|detempering):/;

  // …and five transformation bands, each sending an interval vector through a matrix to a result
  // vector of the same kind. A band is defined once by its matrix and a test for "a result cell of
  // this band"; the geometry engine links source ↔ matrix ↔ result by column x and row order, so
  // every interval tile in the band is covered without enumerating tiles.
  const BANDS = [
    { name: 'mapping', matrix: 'cell:mapping:', result: /^cell:(mapped|hmapped|imapped|mapped_comma|mapped_unchanged|mapped_detempering):/, vec: STD_VEC },
    { name: 'canonical', matrix: 'cell:canonical:', result: /^cell:canonical_/, vec: STD_VEC },
    { name: 'projection', matrix: 'cell:projection:', result: /^cell:projection_/, vec: STD_VEC },
    { name: 'superspace_mapping', matrix: 'cell:superspace_mapping:superspace_primes:', result: /^cell:superspace_mapping:(targets|held|interest|commas|detempering):/, vec: SS_VEC },
    { name: 'superspace_projection', matrix: 'cell:superspace_projection:superspace_primes:', result: /^cell:superspace_projection_(targets|held|interest|detempering|vectors):/, vec: SS_VEC },
  ];
  // hovering a bare interval vector flows it through its space's mapping (the forward computation).
  const forwardBand = (id) => (SS_VEC.test(id) ? BANDS[3] : BANDS[0]);

  let svg = null, currentKey = null;
  const board = () => document.querySelector('.rtt-gridcontent');
  const active = () => document.body.classList.contains('rtt-mapping-demos');

  const ensureSvg = (b) => {
    if (svg && svg.parentNode === b) return svg;
    svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'rtt-demo-overlay');
    b.appendChild(svg);
    return svg;
  };
  const clear = () => { if (svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); svg.style.display = 'none'; } currentKey = null; };

  // the cell carries its model value in data-value (stamped server-side), so the overlay never has to
  // reconstruct it from the rendered face — a stacked numerator-over-denominator fraction's textContent would
  // concatenate ("1/4" -> "14"). The input/textContent reads are fallbacks for any value cell that
  // somehow lacks the attribute.
  const text = (element) => {
    const dv = element.getAttribute && element.getAttribute('data-value');
    if (dv) return dv;
    const i = element.querySelector('input');
    if (i && i.value !== '') return i.value;
    return element.textContent;
  };

  // ---- svg primitives -------------------------------------------------------
  const line = (x1, y1, x2, y2, palette) => {
    const l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2);
    l.setAttribute('stroke', palette.stroke); l.setAttribute('stroke-width', '3'); l.setAttribute('stroke-linecap', 'round');
    svg.appendChild(l);
  };
  const path = (d, palette) => {
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', d); p.setAttribute('fill', 'none');
    p.setAttribute('stroke', palette.stroke); p.setAttribute('stroke-width', '3');
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
  const chip = (centerX, centerY, s, sq, palette) => {
    const txt = String(s);
    const w = sq ? 16 : Math.max(16, 7 + txt.length * 7), h = 16;
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', centerX - w / 2); r.setAttribute('y', centerY - h / 2);
    r.setAttribute('width', w); r.setAttribute('height', h);
    r.setAttribute('rx', 4); r.setAttribute('fill', palette.fill); r.setAttribute('stroke', palette.stroke); r.setAttribute('stroke-width', '1.5');
    svg.appendChild(r);
    glyph(centerX, centerY, txt, 11, palette.ink);
  };
  const ring = (c, palette) => {
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', c.l + 1); r.setAttribute('y', c.t + 1);
    r.setAttribute('width', c.w - 2); r.setAttribute('height', c.h - 2);
    r.setAttribute('fill', 'none'); r.setAttribute('stroke', palette.stroke); r.setAttribute('stroke-width', '3');
    svg.appendChild(r);
  };

  const cluster = (vals) => {
    const s = [...vals].sort((a, z) => a - z), out = [];
    for (const v of s) if (!out.length || v - out[out.length - 1] > 6) out.push(v);
    return out;
  };

  // ---- draw -----------------------------------------------------------------
  const draw = (band, hov) => {
    const b = board();
    if (!b) return false;
    const bRect = b.getBoundingClientRect();
    const C = (element) => {
      const r = element.getBoundingClientRect();
      return { x: r.left - bRect.left + r.width / 2, y: r.top - bRect.top + r.height / 2,
               t: r.top - bRect.top, btm: r.bottom - bRect.top, l: r.left - bRect.left, rt: r.right - bRect.left, w: r.width, h: r.height };
    };
    const columnX = C(hov).x;
    const inColumn = (o) => Math.abs(o.c.x - columnX) < 8;
    const all = [...board().querySelectorAll('[data-eid]')];
    const elementId = (element) => element.getAttribute('data-eid');

    const source = all.filter((element) => band.vec.test(elementId(element))).map((element) => ({ c: C(element), v: FR.parse(text(element)) }))
      .filter(inColumn).sort((a, z) => a.c.y - z.c.y);
    const mcells = all.filter((element) => elementId(element).startsWith(band.matrix)).map((element) => ({ c: C(element), m: FR.parse(text(element)) }));
    const res = all.filter((element) => band.result.test(elementId(element))).map((element) => ({ c: C(element) }))
      .filter(inColumn).sort((a, z) => a.c.y - z.c.y);
    if (!source.length || !mcells.length || !res.length) return false;

    const ux = cluster(mcells.map((o) => o.c.x)), uy = cluster(mcells.map((o) => o.c.y));
    const at = (i, p) => mcells.find((o) => Math.abs(o.c.y - uy[i]) < 6 && Math.abs(o.c.x - ux[p]) < 6);
    const P = Math.min(source.length, ux.length), R = Math.min(res.length, uy.length);
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
      const leftEdge = box0.c.l, vy = source[p].c.y;
      const tracks = []; for (let i = 0; i < R; i++) tracks.push(i === 0 ? leftEdge : leftEdge - i * gap);
      line(Math.min(...tracks), vy, source[p].c.l, vy, AMBER);
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
        const prod = (cell.m && source[p].v) ? FR.mul(cell.m, source[p].v) : null;
        if (prod) chip(cell.c.x, cell.c.btm, FR.str(prod), false, GREEN);
        if (p < P - 1) chip(cell.c.rt, cell.c.btm, '+', true, GREEN);
      }
    }

    // (D) rings on both ends: the operand vector (amber) and the result vector (green).
    for (let p = 0; p < P; p++) ring(source[p].c, AMBER);
    for (let i = 0; i < R; i++) ring(res[i].c, GREEN);
    return true;
  };

  const hovered = (node) => {
    const cell = node && node.closest && node.closest('[data-eid]');
    if (!cell) return null;
    const id = cell.getAttribute('data-eid');
    for (const band of BANDS) if (band.result.test(id)) return { band, cell };
    if (STD_VEC.test(id) || SS_VEC.test(id)) return { band: forwardBand(id), cell };
    return null;
  };
  const keyOf = (h) => h.band.name + ':' + Math.round(h.cell.getBoundingClientRect().left);

  document.addEventListener('mouseover', (e) => {
    if (!active()) { if (currentKey) clear(); return; }
    const h = hovered(e.target);
    if (!h) return;
    const key = keyOf(h);
    if (key === currentKey) return;
    if (draw(h.band, h.cell)) currentKey = key;
  });
  document.addEventListener('mouseout', (e) => {
    if (!currentKey) return;
    const h = hovered(e.relatedTarget);
    if (h && keyOf(h) === currentKey) return;
    clear();
  });
  window.addEventListener('scroll', () => { if (currentKey) clear(); }, { capture: true, passive: true });
  document.addEventListener('pointerdown', () => { if (currentKey) clear(); }, true);
})()
