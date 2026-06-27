(() => {
  if (window.__rttMapDemo) return;
  window.__rttMapDemo = true;
  const NS = 'http://www.w3.org/2000/svg';
  const LINE = '#ffce00';
  const INK = '#5a4500';
  const VEC_PREFIX = 'cell:vec:targets:';
  const MAP_PREFIX = 'cell:mapping:';

  let svg = null, curTok = null;

  const board = () => document.querySelector('.rtt-gridcontent');

  const active = () => document.body.classList.contains('rtt-mapping-demos');

  const ensureSvg = (b) => {
    if (svg && svg.parentNode === b) return svg;
    svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'rtt-demo-overlay');
    b.appendChild(svg);
    return svg;
  };

  const clear = () => { if (svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); svg.style.display = 'none'; } curTok = null; };

  const num = (el) => {
    if (!el) return null;
    const inp = el.querySelector('input');
    let t = inp && inp.value !== '' ? inp.value : el.textContent;
    t = (t || '').replace(/[−–—]/g, '-');
    const m = t.match(/-?\d+/);
    return m ? parseInt(m[0], 10) : null;
  };

  const byEid = (eid) => document.querySelector('[data-eid="' + eid + '"]');

  // eids are "<fixed-prefix><token>:<int>"; the token itself may carry colons, so split off only
  // the trailing integer and treat everything between prefix and it as the token.
  const splitTail = (eid, prefix) => {
    const rest = eid.slice(prefix.length);
    const i = rest.lastIndexOf(':');
    return [rest.slice(0, i), parseInt(rest.slice(i + 1), 10)];
  };

  const line = (x1, y1, x2, y2) => {
    const l = document.createElementNS(NS, 'line');
    l.setAttribute('x1', x1); l.setAttribute('y1', y1);
    l.setAttribute('x2', x2); l.setAttribute('y2', y2);
    l.setAttribute('stroke', LINE); l.setAttribute('stroke-width', '3');
    l.setAttribute('stroke-linecap', 'round');
    svg.appendChild(l);
  };

  const glyph = (x, y, s, size, fill) => {
    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', x); t.setAttribute('y', y);
    t.setAttribute('text-anchor', 'middle');
    t.setAttribute('dominant-baseline', 'central');
    t.setAttribute('font-size', size || 12);
    t.setAttribute('fill', fill || INK);
    t.setAttribute('font-family', "'STIX Two Text', Georgia, serif");
    t.textContent = s;
    svg.appendChild(t);
  };

  const pill = (cx, cy, s) => {
    const w = 9 + String(s).length * 7, h = 15;
    const r = document.createElementNS(NS, 'rect');
    r.setAttribute('x', cx - w / 2); r.setAttribute('y', cy - h / 2);
    r.setAttribute('width', w); r.setAttribute('height', h);
    r.setAttribute('rx', 4); r.setAttribute('fill', '#fff8d0');
    r.setAttribute('stroke', LINE); r.setAttribute('stroke-width', '1.5');
    svg.appendChild(r);
    glyph(cx, cy, s, 11, INK);
  };

  const draw = (tok) => {
    const b = board();
    if (!b) return;
    const bRect = b.getBoundingClientRect();
    const C = (el) => {
      const r = el.getBoundingClientRect();
      return { x: r.left - bRect.left + r.width / 2, y: r.top - bRect.top + r.height / 2,
               t: r.top - bRect.top, btm: r.bottom - bRect.top,
               l: r.left - bRect.left, rt: r.right - bRect.left, w: r.width, h: r.height };
    };

    // operand vector v[p] of the hovered interval (a vertical stack in the interval column)
    const vp = {};
    document.querySelectorAll('[data-eid^="' + VEC_PREFIX + tok + ':"]').forEach((el) => {
      const [t, p] = splitTail(el.getAttribute('data-eid'), VEC_PREFIX);
      if (t === tok) vp[p] = { el, c: C(el), v: num(el) };
    });

    // mapping matrix M[row][p]
    const rows = {};
    document.querySelectorAll('[data-eid^="' + MAP_PREFIX + '"]').forEach((el) => {
      const [rt, p] = splitTail(el.getAttribute('data-eid'), MAP_PREFIX);
      (rows[rt] = rows[rt] || { rt, cells: {} }).cells[p] = { el, c: C(el), m: num(el) };
    });

    const primes = Object.keys(vp).map(Number).sort((a, z) => a - z);
    if (!primes.length) return;
    const colX = {};
    primes.forEach((p) => {
      for (const rt in rows) if (rows[rt].cells[p]) { colX[p] = rows[rt].cells[p].c.x; break; }
    });
    const drawn = primes.filter((p) => p in colX);
    if (!drawn.length) return;

    ensureSvg(b);
    clear();
    svg.style.display = 'block';
    curTok = tok;
    const W = Math.max(b.scrollWidth, b.offsetWidth), H = Math.max(b.scrollHeight, b.offsetHeight);
    svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

    const rowList = Object.values(rows)
      .map((r) => ({ ...r, result: byEid('cell:mapped:' + r.rt + ':' + tok) }))
      .filter((r) => r.result)
      .map((r) => ({ ...r, rc: C(r.result) }))
      .sort((a, z) => a.rc.y - z.rc.y);
    if (!rowList.length) return;

    const colTop = Math.min(...rowList.map((r) => r.rc.t));
    const colBtm = Math.max(...rowList.map((r) => r.rc.btm));

    // operand routing: feed each prime count from its vector cell across to its mapping column,
    // then straight down through every box in that column.
    drawn.forEach((p) => {
      const x = colX[p], vy = vp[p].c.y, vx = vp[p].c.x;
      const fromX = vx < x ? vp[p].c.rt : vp[p].c.l;
      line(fromX, vy, x, vy);
      line(x, Math.min(vy, colTop), x, colBtm);
      pill(x, (vy + colTop) / 2, vp[p].v);
    });

    // each mapping row: highlight the row, annotate the product in every box, sum across to result.
    rowList.forEach((r) => {
      const y = r.rc.y;
      const xs = drawn.map((p) => colX[p]);
      line(Math.min(...xs), y, r.rc.l, y);
      drawn.forEach((p, k) => {
        const cell = r.cells[p];
        const prod = (cell && cell.m != null && vp[p].v != null) ? cell.m * vp[p].v : null;
        if (cell) glyph(cell.c.x, cell.c.btm - 4, '×', 11, INK); // × in the box
        if (prod != null) pill(colX[p], y - r.rc.h / 2 - 9, prod);     // product above the box-row
        if (k < drawn.length - 1) glyph((colX[p] + colX[drawn[k + 1]]) / 2, y, '+', 13, INK);
      });
      glyph(r.rc.l - 7, y, '=', 13, INK);
      const rr = document.createElementNS(NS, 'rect');
      rr.setAttribute('x', r.rc.l + 1); rr.setAttribute('y', r.rc.t + 1);
      rr.setAttribute('width', r.rc.w - 2); rr.setAttribute('height', r.rc.h - 2);
      rr.setAttribute('fill', 'none'); rr.setAttribute('stroke', LINE); rr.setAttribute('stroke-width', '3');
      svg.appendChild(rr);
    });
  };

  const intervalTokOf = (node) => {
    const cell = node.closest && node.closest('[data-eid^="' + VEC_PREFIX + '"]');
    if (!cell) return null;
    return splitTail(cell.getAttribute('data-eid'), VEC_PREFIX)[0];
  };

  document.addEventListener('mouseover', (e) => {
    if (!active()) { if (curTok) clear(); return; }
    const tok = intervalTokOf(e.target);
    if (tok == null) return;
    if (tok === curTok) return;
    draw(tok);
  });
  document.addEventListener('mouseout', (e) => {
    if (!curTok) return;
    const to = e.relatedTarget;
    if (to && intervalTokOf(to) === curTok) return;
    clear();
  });
  window.addEventListener('scroll', () => { if (curTok) clear(); }, { capture: true, passive: true });
  document.addEventListener('pointerdown', () => { if (curTok) clear(); }, true);
})()
