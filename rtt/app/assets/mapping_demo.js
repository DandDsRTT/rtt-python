(() => {
  if (window.__rttMapDemo) return;
  window.__rttMapDemo = true;
  const NS = 'http://www.w3.org/2000/svg';
  const MAP_PREFIX = 'cell:mapping:';
  const CH = 8; // half a chip — the × box's reach above/left of its anchor point

  // two palettes from the preview-highlighting set: amber (a "change") routes the operand in (left and
  // down jaunts, × boxes); green (an "addition") accumulates the result (right jaunts, product/+/= boxes).
  const AMBER = { stroke: 'var(--preview-color)', fill: 'color-mix(in srgb, var(--preview-color) 22%, #fff)', ink: 'var(--preview-text-color)' };
  const GREEN = { stroke: 'var(--pending-color)', fill: 'color-mix(in srgb, var(--pending-color) 22%, #fff)', ink: 'var(--pending-text-color)' };

  // every interval kind that owns a prime-count vector and a mapped generator-count row. vec ids put
  // the prime index either last (targets) or first (the rest); res is the mapped-row id prefix.
  const KINDS = [
    { key: 'targets', vp: 'cell:vec:targets:', primeLast: true, res: 'cell:mapped:' },
    { key: 'held', vp: 'cell:held:', primeLast: false, res: 'cell:hmapped:' },
    { key: 'interest', vp: 'cell:interest:', primeLast: false, res: 'cell:imapped:' },
    { key: 'commas', vp: 'cell:comma:', primeLast: false, res: 'cell:mapped_comma:' },
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

  const num = (el) => {
    if (!el) return null;
    const inp = el.querySelector('input');
    let t = inp && inp.value !== '' ? inp.value : el.textContent;
    t = (t || '').replace(/[−–—]/g, '-');
    const m = t.match(/-?\d+/);
    return m ? parseInt(m[0], 10) : null;
  };
  const sgn = (n) => (n < 0 ? '−' + Math.abs(n) : String(n));
  const byEid = (eid) => document.querySelector('[data-eid="' + eid + '"]');

  const parseVec = (eid, k) => {
    const rest = eid.slice(k.vp.length);
    if (k.primeLast) { const i = rest.lastIndexOf(':'); return [rest.slice(0, i), parseInt(rest.slice(i + 1), 10)]; }
    const i = rest.indexOf(':'); return [rest.slice(i + 1), parseInt(rest.slice(0, i), 10)];
  };
  const parseMap = (eid) => { const r = eid.slice(MAP_PREFIX.length); const i = r.lastIndexOf(':'); return [r.slice(0, i), parseInt(r.slice(i + 1), 10)]; };
  const kindOf = (eid) => KINDS.find((k) => eid.startsWith(k.vp)) || null;

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

  // ---- draw -----------------------------------------------------------------
  const draw = (k, tok) => {
    const b = board();
    if (!b) return;
    const bRect = b.getBoundingClientRect();
    const C = (el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left - bRect.left + r.width / 2, y: r.top - bRect.top + r.height / 2,
               t: r.top - bRect.top, btm: r.bottom - bRect.top, l: r.left - bRect.left, rt: r.right - bRect.left,
               w: r.width, h: r.height };
    };

    const vp = {};
    document.querySelectorAll('[data-eid^="' + k.vp + '"]').forEach((el) => {
      const [t, p] = parseVec(el.getAttribute('data-eid'), k);
      if (t === tok) vp[p] = { el, c: C(el), v: num(el) };
    });
    if (!Object.keys(vp).length) return;

    const rmap = {};
    document.querySelectorAll('[data-eid^="' + MAP_PREFIX + '"]').forEach((el) => {
      const [rt, p] = parseMap(el.getAttribute('data-eid'));
      (rmap[rt] = rmap[rt] || { rt, cells: {} }).cells[p] = { el, c: C(el), m: num(el) };
    });
    const rows = Object.values(rmap)
      .map((r) => ({ ...r, result: byEid(k.res + r.rt + ':' + tok) }))
      .filter((r) => r.result)
      .map((r) => ({ ...r, rc: C(r.result) }))
      .sort((a, z) => a.rc.y - z.rc.y);
    if (!rows.length) return;

    const primes = Object.keys(vp).map(Number).filter((p) => rows.some((r) => r.cells[p])).sort((a, z) => a - z);
    if (!primes.length) return;
    const R = rows.length;
    const W = rows[0].cells[primes[0]].c.w;
    const colX = {}; primes.forEach((p) => { colX[p] = rows[0].cells[p] ? rows[0].cells[p].c.x : null; });

    ensureSvg(b); clear(); svg.style.display = 'block'; curKey = k.key + ':' + tok;
    const SW = Math.max(b.scrollWidth, b.offsetWidth), SH = Math.max(b.scrollHeight, b.offsetHeight);
    svg.setAttribute('width', SW); svg.setAttribute('height', SH); svg.setAttribute('viewBox', '0 0 ' + SW + ' ' + SH);

    const gap = Math.min(8, (W * 0.45) / Math.max(1, R - 1));

    // (A) operand fan: each prime count splits into one line per mapping row. They share the leftward
    // jaunt (a bus along the vector row), then split into parallel descents — row 0 straight into the
    // top of its × box, each later row peeling left then entering its box from the left.
    primes.forEach((p) => {
      const leftEdge = colX[p] - W / 2, vy = vp[p].c.y;
      const tracks = rows.map((r, i) => (i === 0 ? leftEdge : leftEdge - i * gap));
      line(Math.min(...tracks), vy, vp[p].c.l, vy, AMBER);
      rows.forEach((r, i) => {
        const box = r.cells[p];
        if (!box) return;
        if (i === 0) line(leftEdge, vy, leftEdge, box.c.y - CH, AMBER);
        else path('M ' + tracks[i] + ' ' + vy + ' V ' + box.c.y + ' H ' + leftEdge, AMBER);
      });
    });

    // (B) the running sum along each row: emerge from the first product and ride the boxes' bottom
    // edge through the products and +s, staying low all the way to the result cell's bottom-left corner.
    rows.forEach((r) => {
      const by = r.cells[primes[0]].c.btm;
      line(r.cells[primes[0]].c.x, by, r.rc.l, by, GREEN);
    });

    // (C) per-box marks: × on the left edge (where the operand line lands), the product on the bottom
    // edge; + at each shared bottom corner between adjacent boxes.
    rows.forEach((r) => {
      primes.forEach((p, kx) => {
        const box = r.cells[p]; if (!box) return;
        chip(box.c.l, box.c.y, '×', true, AMBER);
        const prod = (box.m != null && vp[p].v != null) ? box.m * vp[p].v : null;
        if (prod != null) chip(box.c.x, box.c.btm, sgn(prod), false, GREEN);
        if (kx < primes.length - 1) chip(box.c.rt, box.c.btm, '+', true, GREEN);
      });
    });

    // (D) rings on both ends: the prime counts (operand, amber) and the generator counts (result, green).
    primes.forEach((p) => ring(vp[p].c, AMBER));
    rows.forEach((r) => ring(r.rc, GREEN));

    // (E) the = box rides on top of the result ring, at its bottom-left corner.
    rows.forEach((r) => chip(r.rc.l, r.rc.btm, '=', true, GREEN));
  };

  const hoveredInterval = (node) => {
    if (!node || !node.closest) return null;
    for (const k of KINDS) {
      const cell = node.closest('[data-eid^="' + k.vp + '"]');
      if (cell) return { k, tok: parseVec(cell.getAttribute('data-eid'), k)[0] };
    }
    return null;
  };

  document.addEventListener('mouseover', (e) => {
    if (!active()) { if (curKey) clear(); return; }
    const hit = hoveredInterval(e.target);
    if (!hit) return;
    if (hit.k.key + ':' + hit.tok === curKey) return;
    draw(hit.k, hit.tok);
  });
  document.addEventListener('mouseout', (e) => {
    if (!curKey) return;
    const hit = hoveredInterval(e.relatedTarget);
    if (hit && hit.k.key + ':' + hit.tok === curKey) return;
    clear();
  });
  window.addEventListener('scroll', () => { if (curKey) clear(); }, { capture: true, passive: true });
  document.addEventListener('pointerdown', () => { if (curKey) clear(); }, true);
})()
