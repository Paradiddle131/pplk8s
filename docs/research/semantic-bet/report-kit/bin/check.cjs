#!/usr/bin/env node
// Checks report pages built with report-kit, in Chromium, the way readers meet them: at widths 360, 400, 768,
// 1024, 1280 and 1440 in the light and the dark theme, and again at a 200% browser text size (light), in every
// part (tab) and every view of every switch. A finding is one of:
//   hscroll   the page scrolls sideways
//   clip      text cut by a box that clips it, or out of the page's reach
//   overflow  a box with hidden overflow or an ellipsis that holds more text than it shows
//   viewbox   SVG text outside its <svg>'s viewBox
//   overlap   two text boxes on top of each other (each cut to what its clipping and scrolling boxes show)
//   contrast  text under 4.5:1 against what is behind it (3:1 at 24px, or 18.66px bold)
//   focus     a focusable element whose focus changes nothing visible
//   tabs, switch, sort, highlight, bubble   a control that does not do what it claims
//   console   a console or page error; the kit's web font (on its first section, else the body) not loaded
//   control   a control the checker could not reach or press in time
//   muted     a heading (h1 to h6) set paler than the words around it, by its colour or its opacity
//   outline   a heading that skips a level on the way down (an h2 straight to an h4); an open modal dialog is an
//             outline of its own, starting at h2
//   static    raw hex outside token blocks (a drawing's own colours inside <svg> are exempt), gradient text, emoji
//             as icons, a banned font, a theme block missing
// Usage: node bin/check.cjs <page.html>... [--quick] [--shots <dir>]   (--quick: 400 and 1280 only)
//        node bin/check.cjs --selftest <page.html>     (plants one case of each geometry kind; each must be found)
// Prints each finding with where it happened, then "N problems"; exit 1 when there is any.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const args = process.argv.slice(2);
const flag = n => { const i = args.indexOf(`--${n}`); return i >= 0 ? (args.splice(i, 1), true) : false; };
const opt = n => { const i = args.indexOf(`--${n}`); return i >= 0 ? args.splice(i, 2)[1] : undefined; };
const QUICK = flag('quick');
const SELFTEST = flag('selftest');
const SHOTS = opt('shots');
const WIDTHS = QUICK ? [400, 1280] : [360, 400, 768, 1024, 1280, 1440];
const FOCUS_WIDTH = 1280;

// ---------- static checks, on the page's source without the vendored libraries
function staticChecks(src) {
  const out = [];
  // the vendored libraries are left out, and so are a drawing's own colours: a brand mark inside an <svg> keeps them
  const lines = src.replace(/<!-- report-kit:vendor[\s\S]*?<!-- \/report-kit:vendor -->/g, m => m.replace(/[^\n]/g, ''))
    .replace(/<svg\b[\s\S]*?<\/svg>/gi, m => m.replace(/#[0-9a-fA-F]{3,8}\b/g, x => ' '.repeat(x.length))).split('\n');
  let inRoot = false, depth = 0;
  const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}]/u;
  lines.forEach((ln, i) => {
    const at = `line ${i + 1}`;
    if (!inRoot && /:root[^{]*\{/.test(ln)) { inRoot = true; depth = 0; }
    const rootLine = inRoot;
    if (inRoot) { depth += (ln.match(/\{/g) || []).length - (ln.match(/\}/g) || []).length; if (depth <= 0) inRoot = false; }
    if (!rootLine) for (const m of ln.matchAll(/(?<![&\w])#[0-9a-fA-F]{3,8}\b/g)) {
      if (/(href|data-[\w-]+|aria-[\w-]+)=["']$/.test(ln.slice(Math.max(0, m.index - 40), m.index))) continue; // a link to an id
      out.push({ kind: 'static', text: `raw colour ${m[0]} outside a token block: use a var(--token)`, where: at });
    }
    if (/background-clip\s*:\s*text/i.test(ln)) out.push({ kind: 'static', text: 'gradient text (background-clip: text)', where: at });
    const m = ln.match(/font(?:-family)?\s*:\s*(?:[\d.]+\w*\s+)*['"]?(Inter|Roboto|Arial|Helvetica)\b/i);
    if (m) out.push({ kind: 'static', text: `${m[1]} as the first font: use var(--sans)`, where: at });
    const e = ln.match(EMOJI);
    if (e) out.push({ kind: 'static', text: `emoji ${e[0]} used as an icon: draw a line icon in currentColor`, where: at });
  });
  if (/prefers-color-scheme:\s*dark/.test(src) && !(/:root:not\(\[data-theme="light"\]\)/.test(src) && /:root\[data-theme="dark"\]/.test(src))) {
    out.push({ kind: 'static', text: 'dark tokens need all three blocks: :root, the media query on :root:not([data-theme="light"]), and :root[data-theme="dark"]', where: 'page' });
  }
  return out;
}

// ---------- geometry and contrast, run in the page
async function inspect() {
  const TX = 0.5, TY = 1;
  const out = [];
  const visible = el => el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const isSvg = el => el instanceof SVGElement;
  const where = el => {
    const s = el.closest('section, [role=tabpanel], figure, main');
    const h = s && s.querySelector('h2, figcaption');
    return h ? `"${h.textContent.trim().slice(0, 40)}"` : 'page';
  };
  const clips = cs => cs.overflowX !== 'visible' || cs.overflowY !== 'visible' || (cs.clipPath && cs.clipPath !== 'none');
  const scrolls = v => v === 'auto' || v === 'scroll';
  const items = [], svgTexts = new Set();
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (!n.nodeValue.trim()) continue;
    let el = n.parentElement;
    if (!el || el.closest('script, style, title, template, noscript')) continue;
    if (isSvg(el)) {
      const t = el.closest('text');
      if (!t || svgTexts.has(t) || !visible(t)) continue;
      svgTexts.add(t);
      const r = t.getBoundingClientRect();
      if (r.width && r.height) items.push({ el: t, rects: [r], text: t.textContent.trim(), svg: true });
      continue;
    }
    if (!visible(el)) continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    const rects = [...rg.getClientRects()].filter(r => r.width > 0.5 && r.height > 0.5);
    if (rects.length) items.push({ el, rects, text: n.nodeValue.trim() });
  }
  const docW = document.documentElement.scrollWidth;
  const clippers = el => {
    const list = [];
    for (let a = el; a && a !== document.body; a = a.parentElement) { // the text's own element may clip it too
      const cs = getComputedStyle(a);
      if (clips(cs)) list.push({ a, cs, r: a.getBoundingClientRect() });
    }
    return list;
  };
  const tiny = r => r.width <= 2 || r.height <= 2;
  for (const it of items) {
    const cl = clippers(it.el);
    if (cl.some(c => tiny(c.r))) { it.sr = true; continue; } // screen-reader-only text
    let found = null;
    for (const { a, cs, r: b } of cl) {
      for (const r of it.rects) {
        let dl = b.left + a.clientLeft - r.left, dr = r.right - (b.left + a.clientLeft + a.clientWidth);
        let dt = b.top + a.clientTop - r.top, db = r.bottom - (b.top + a.clientTop + a.clientHeight);
        if (scrolls(cs.overflowX)) { dl -= a.scrollLeft; dr = -1; }
        if (scrolls(cs.overflowY)) { dt -= a.scrollTop; db = -1; }
        if (cs.overflowX === 'visible' && cs.clipPath === 'none') dl = dr = -1;
        if (cs.overflowY === 'visible' && cs.clipPath === 'none') dt = db = -1;
        if (dl > TX || dr > TX || dt > TY || db > TY) { found = `cut by ${a.tagName.toLowerCase()}.${[...a.classList].join('.')}`; break; }
      }
      if (found) break;
    }
    if (!found && !cl.some(c => c.cs.overflowX !== 'visible')) {
      for (const r of it.rects) if (r.left + scrollX < -TX || r.right + scrollX > docW + TX) { found = 'outside the page'; break; }
    }
    if (found) out.push({ kind: 'clip', text: `"${it.text.slice(0, 60)}" ${found}`, where: where(it.el) });
    // what a reader can see of the text: its boxes cut to every ancestor that clips or scrolls it, so text scrolled
    // out of sight inside a scroll box is not taken for text drawn over what lies beyond the box
    let L = -Infinity, T = -Infinity, R = Infinity, B = Infinity;
    for (const { a, cs, r: b } of cl) {
      const clipX = cs.overflowX !== 'visible' || cs.clipPath !== 'none', clipY = cs.overflowY !== 'visible' || cs.clipPath !== 'none';
      if (clipX) { L = Math.max(L, b.left + a.clientLeft); R = Math.min(R, b.left + a.clientLeft + a.clientWidth); }
      if (clipY) { T = Math.max(T, b.top + a.clientTop); B = Math.min(B, b.top + a.clientTop + a.clientHeight); }
    }
    it.seen = it.rects.map(r => ({ left: Math.max(r.left, L), right: Math.min(r.right, R), top: Math.max(r.top, T), bottom: Math.min(r.bottom, B) }))
      .filter(r => r.right - r.left > 0.5 && r.bottom - r.top > 0.5);
  }
  // text over text
  const boxes = items.filter(it => !it.sr).flatMap(it => (it.seen || it.rects).map(r => ({ it, r })));
  boxes.sort((p, q) => p.r.top - q.r.top);
  const seen = new Set();
  for (let i = 0; i < boxes.length; i++) {
    const A = boxes[i];
    for (let j = i + 1; j < boxes.length && boxes[j].r.top < A.r.bottom - 2; j++) {
      const B = boxes[j];
      if (A.it === B.it || A.it.el.contains(B.it.el) || B.it.el.contains(A.it.el)) continue;
      const ox = Math.min(A.r.right, B.r.right) - Math.max(A.r.left, B.r.left);
      const oy = Math.min(A.r.bottom, B.r.bottom) - Math.max(A.r.top, B.r.top);
      if (ox <= 1 || oy <= 2) continue;
      const key = [A.it.text, B.it.text].sort().join('|');
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ kind: 'overlap', text: `"${A.it.text.slice(0, 40)}" over "${B.it.text.slice(0, 40)}"`, where: where(A.it.el) });
    }
  }
  // SVG text against its viewBox
  for (const t of svgTexts) {
    const svg = t.ownerSVGElement, vb = svg && svg.viewBox.baseVal;
    if (!vb || !vb.width) continue;
    const bb = t.getBBox(), m = svg.getScreenCTM().inverse().multiply(t.getScreenCTM());
    const pts = [[bb.x, bb.y], [bb.x + bb.width, bb.y + bb.height]].map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    if (Math.min(pts[0].x, pts[1].x) < vb.x - TX || Math.max(pts[0].x, pts[1].x) > vb.x + vb.width + TX ||
        Math.min(pts[0].y, pts[1].y) < vb.y - TY || Math.max(pts[0].y, pts[1].y) > vb.y + vb.height + TY) {
      out.push({ kind: 'viewbox', text: `"${t.textContent.trim().slice(0, 60)}" outside its viewBox`, where: where(t) });
    }
  }
  // boxes that hide text they hold
  for (const el of document.body.querySelectorAll('*')) {
    if (isSvg(el) || !visible(el) || !el.textContent.trim()) continue;
    const cs = getComputedStyle(el);
    const hx = cs.overflowX === 'hidden' || cs.overflowX === 'clip', hy = cs.overflowY === 'hidden' || cs.overflowY === 'clip';
    const ell = cs.textOverflow && cs.textOverflow !== 'clip';
    if ((!hx && !hy && !ell) || el.clientWidth <= 2 || el.clientHeight <= 2) continue;
    if ((hx && el.scrollWidth > el.clientWidth + 1) || (hy && el.scrollHeight > el.clientHeight + 1) || (ell && el.scrollWidth > el.clientWidth)) {
      out.push({ kind: 'overflow', text: `"${el.textContent.trim().slice(0, 60)}" overflows ${el.tagName.toLowerCase()}`, where: where(el) });
    }
  }
  // contrast, against the backgrounds stacked behind the text
  const parse = c => {
    let m = c && c.match(/^rgba?\(([^)]+)\)/);
    if (m) { const v = m[1].split(/[\s,/]+/).filter(Boolean).map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; }
    m = c && c.match(/^color\(srgb ([^)]+)\)/);
    if (m) { const v = m[1].split(/[\s/]+/).filter(Boolean).map(Number); return [v[0] * 255, v[1] * 255, v[2] * 255, v.length > 3 ? v[3] : 1]; }
    return null;
  };
  const over = (top, under) => { const a = top[3]; return [0, 1, 2].map(i => top[i] * a + under[i] * (1 - a)).concat(1); };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const page = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
  const ground = page[3] < 1 ? over(page, parse(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1]) : page;
  const reported = new Set();
  for (const it of items) {
    if (it.sr) continue;
    const el = it.el, cs = getComputedStyle(el);
    const layers = [];
    let alpha = 1;
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const s = getComputedStyle(e);
      alpha *= +s.opacity;
      const bg = parse(s.backgroundColor);
      if (bg && bg[3] > 0 && e !== document.body) { layers.push(bg); if (bg[3] >= 1) break; }
    }
    let bg = ground;
    for (const l of layers.reverse()) bg = over(l, bg);
    let fg = parse(it.svg ? cs.fill : cs.color);
    if (!fg) continue;
    fg = over([fg[0], fg[1], fg[2], fg[3] * alpha], bg);
    const [l1, l2] = [lum(fg), lum(bg)].sort((p, q) => q - p);
    const ratio = (l1 + 0.05) / (l2 + 0.05);
    const px = parseFloat(cs.fontSize), large = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700);
    const need = large ? 3 : 4.5;
    if (ratio < need && !reported.has(it.text)) {
      reported.add(it.text);
      out.push({ kind: 'contrast', text: `"${it.text.slice(0, 50)}" ${ratio.toFixed(2)}:1, under ${need}:1`, where: where(el) });
    }
  }
  // rank comes from size, weight, space and rules, never a paler grey: a heading keeps the full ink of its text
  const solid = (e, stop) => { let a = 1; for (; e && e !== stop; e = e.parentElement) a *= +getComputedStyle(e).opacity; return a; };
  for (const h of document.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
    if (!visible(h) || !h.textContent.trim()) continue;
    const box = h.parentElement.closest('p, li, td, th, dd, section, main, body');
    const want = parse(getComputedStyle(box).color), got = parse(getComputedStyle(h).color);
    const a = solid(h, box);
    if (want && got && (got.some((v, i) => Math.abs(v - want[i]) > 2) || a < 0.99)) {
      out.push({ kind: 'muted', text: `heading "${h.textContent.trim().slice(0, 40)}" paler than its text: rank it by size, weight and space`, where: where(h) });
    }
  }
  // headings nest by rank: going down, each is at most one level under the one before it; going back up may jump
  const heads = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(h => visible(h) && h.textContent.trim());
  const outline = (hs, prev) => {
    for (const h of hs) {
      const n = +h.tagName[1];
      if (n > prev + 1) out.push({ kind: 'outline', text: `heading "${h.textContent.trim().slice(0, 40)}" is an h${n} under an h${prev}: step down one level at a time`, where: where(h) });
      prev = n;
    }
  };
  outline(heads.filter(h => !h.closest('dialog')), 1); // a page may open at h1, or at h2 when its host holds the h1
  for (const d of document.querySelectorAll('dialog[open]')) outline(heads.filter(h => h.closest('dialog') === d), 1);
  const sw = document.documentElement.scrollWidth, cw = document.documentElement.clientWidth;
  if (sw > cw) out.push({ kind: 'hscroll', text: `the page scrolls sideways (${sw} > ${cw})`, where: 'page' });
  for (const g of document.querySelectorAll('[data-rk-switch]')) {
    const n = g.querySelectorAll('button').length;
    if (n > 4) out.push({ kind: 'switch', text: `a switch with ${n} segments: four at most, else tabs or a select`, where: where(g) });
  }
  return out;
}

// every focusable element, focused from the keyboard's side, must look different from unfocused
async function focusCheck() {
  const out = [];
  const sel = 'a[href], button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  const look = el => { const s = getComputedStyle(el); return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.backgroundColor, s.color, s.textDecorationLine, s.borderColor].join('|'); };
  for (const el of document.querySelectorAll(sel)) {
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) || el.closest('.rk-tip')) continue;
    el.blur();
    const before = look(el);
    el.focus({ preventScroll: true });
    if (document.activeElement !== el) continue;
    const after = look(el);
    if (before === after || (getComputedStyle(el).outlineStyle === 'none' && !el.matches(':focus-visible'))) {
      out.push({ kind: 'focus', text: `no visible focus on ${el.tagName.toLowerCase()} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 40)}"`, where: 'page' });
    }
    el.blur();
  }
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
  return out;
}

const settle = page => page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 60)))));
const panels = page => page.$$eval('[role=tablist] [role=tab]', ts => ts.map(t => ({ tab: t.id, panel: t.getAttribute('aria-controls') })));
async function openPanel(page, p) {
  if (!p) return;
  await page.evaluate(p => { const t = document.getElementById(p.tab); if (t && t.getAttribute('aria-selected') !== 'true') t.click(); }, p);
  await settle(page);
}
// the page's states: each part, and in it each view of each switch
async function states(page) {
  const ps = await panels(page);
  const out = [];
  for (const p of ps.length ? ps : [null]) {
    await openPanel(page, p);
    const sw = await page.$$eval('[data-rk-switch]', gs => gs.filter(g => g.checkVisibility({ visibilityProperty: true })).map(g => ({ name: g.dataset.rkSwitch, values: [...g.querySelectorAll('button[data-value]')].map(b => b.dataset.value) })));
    if (!sw.length) out.push({ p, label: p ? `#${p.panel}` : 'page' });
    for (const s of sw) for (const v of s.values) out.push({ p, sw: [s.name, v], label: `${p ? `#${p.panel} ` : ''}${s.name}=${v}` });
  }
  return out;
}
async function enter(page, st) {
  await openPanel(page, st.p);
  if (st.sw) await page.evaluate(([n, v]) => { const b = document.querySelector(`[data-rk-switch="${n}"] button[data-value="${v}"]`); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }, st.sw);
  await settle(page);
}

// ---------- behaviour: tabs, switches, sorting, the highlight, the bubble
async function behaviour(page) {
  const out = [];
  const fail = (kind, text, where = 'page') => out.push({ kind, text, where });
  // a control the checker cannot reach or press in time is a finding, not a crash
  const act = async (what, fn) => {
    try { await fn(); await settle(page); return true; } catch (e) {
      if (!/timeout/i.test(`${e.name} ${e.message}`)) throw e;
      fail('control', `${what}: timed out (${e.message.split('\n')[0].slice(0, 120)})`);
      return false;
    }
  };
  // bring the target into view and let the layout settle before the pointer acts on it
  const reach = async sel => { await page.locator(sel).first().scrollIntoViewIfNeeded(); await settle(page); };
  const click = (sel, what = `pressing ${sel}`) => act(what, async () => { await reach(sel); await page.click(sel); });
  const hover = (sel, what = `pointing at ${sel}`) => act(what, async () => { await reach(sel); await page.hover(sel); });
  const ps = await panels(page);
  for (const p of ps) {
    await click(`#${p.tab}`, `tab ${p.tab}`);
    const r = await page.evaluate(p => {
      const all = [...document.querySelectorAll('[role=tabpanel]')];
      const me = document.getElementById(p.panel);
      return { sel: document.getElementById(p.tab).getAttribute('aria-selected'), shown: !!me && me.checkVisibility({ visibilityProperty: true }), empty: !me || !me.textContent.trim(),
        others: all.filter(x => x !== me && x.checkVisibility({ visibilityProperty: true })).map(x => x.id), hash: location.hash };
    }, p);
    if (r.sel !== 'true' || !r.shown || r.others.length) fail('tabs', `tab ${p.tab} does not open only its part (shown ${r.shown}, also open: ${r.others.join(', ') || 'none'})`);
    if (r.hash !== `#${p.panel}`) fail('tabs', `tab ${p.tab} leaves the URL at "${r.hash}", not #${p.panel}`);
    if (r.empty) fail('tabs', `tab ${p.tab} opens an empty part: an empty part should drop out`);
  }
  for (const p of ps.length ? ps : [null]) {
    await openPanel(page, p);
    // switches: each segment shows its views alone
    const groups = await page.$$eval('[data-rk-switch]', gs => gs.filter(g => g.checkVisibility({ visibilityProperty: true })).map(g => g.dataset.rkSwitch));
    for (const name of groups) {
      const values = await page.$$eval(`[data-rk-switch="${name}"] button[data-value]`, bs => bs.map(b => b.dataset.value));
      for (const v of values) {
        await click(`[data-rk-switch="${name}"] button[data-value="${v}"]`, `switch ${name}=${v}`);
        const r = await page.evaluate(([n, v]) => ({
          pressed: document.querySelector(`[data-rk-switch="${n}"] button[data-value="${v}"]`).getAttribute('aria-pressed'),
          wrong: [...document.querySelectorAll('[data-rk-when]')].filter(el => el.dataset.rkWhen.startsWith(n + '=')).filter(el => (el.dataset.rkWhen === `${n}=${v}`) === el.hidden).length,
        }), [name, v]);
        if (r.pressed !== 'true' || r.wrong) fail('switch', `switch ${name}=${v}: pressed ${r.pressed}, ${r.wrong} view(s) shown or hidden wrongly`);
      }
      await click(`[data-rk-switch="${name}"] button[data-value="${values[0]}"]`, `switch ${name}=${values[0]}`);
    }
    // sortable tables: each column orders its rows as aria-sort says; the default column restores the order
    const tables = await page.$$eval('table[data-rk-sort]', ts => ts.map((t, i) => (t.dataset.rkCheck = i, t.checkVisibility({ visibilityProperty: true }) ? i : -1)).filter(i => i >= 0));
    for (const ti of tables) {
      const T = `table[data-rk-check="${ti}"]`;
      const rowsNow = () => page.$$eval(`${T} tbody tr`, rs => rs.map(r => r.cells[0].textContent.trim()));
      const first = await rowsNow();
      const cols = await page.$$eval(`${T} thead th[data-sort]`, hs => hs.map(h => ({ i: h.cellIndex, kind: h.dataset.sort })));
      const toggle = await page.$eval(T, t => t.dataset.rkSort === 'toggle');
      // each column: three presses; the first goes to its first direction (numbers highest first, else A to Z), and
      // every later press flips it; a table in a sort group leaves its group-mates sorted the same way
      for (const c of cols.filter(c => toggle || c.kind !== 'default')) {
        const firstDir = c.kind === 'number' ? 'descending' : 'ascending';
        const flip = d => (d === 'ascending' ? 'descending' : 'ascending');
        // the direction before the first press: a column already sorted flips; one that is not takes its first direction
        let want = await page.$eval(`${T} thead th:nth-child(${c.i + 1})`, h => h.getAttribute('aria-sort'));
        for (let press = 0; press < 3; press++) {
          if (!await click(`${T} thead th:nth-child(${c.i + 1}) button`, `sorting column ${c.i + 1}`)) break;
          const r = await page.evaluate(([T, c]) => {
            const ordered = (t, dir) => {
              if (c.kind === 'default') { const o = [...t.tBodies[0].rows].map(r => +r.dataset.rkOrder); return o.every((x, k) => !k || (dir === 'ascending' ? o[k - 1] < x : o[k - 1] > x)); }
              const val = row => { const x = row.cells[c.i]; const own = n => !(n.classList && n.classList.contains('rk-cell-label')); const raw = x.dataset.v ?? [...x.childNodes].filter(own).map(n => n.textContent).join('').trim(); return c.kind === 'text' ? raw : parseFloat(raw.replace(/[^\d.+-]/g, '')); };
              const v = [...t.tBodies[0].rows].map(val);
              return v.every((x, k) => !k || (dir === 'ascending' ? (c.kind === 'text' ? String(v[k - 1]).localeCompare(String(x)) <= 0 : v[k - 1] <= x) : (c.kind === 'text' ? String(v[k - 1]).localeCompare(String(x)) >= 0 : v[k - 1] >= x)));
            };
            const t = document.querySelector(T);
            const dir = t.tHead.rows[0].cells[c.i].getAttribute('aria-sort');
            const g = t.dataset.rkSortGroup;
            const mates = g ? [...document.querySelectorAll('table[data-rk-sort-group]')].filter(u => u !== t && u.dataset.rkSortGroup === g) : [];
            const off = mates.filter(u => u.tHead.rows[0].cells[c.i].getAttribute('aria-sort') !== dir || !ordered(u, dir)).length;
            return { dir, ok: ordered(t, dir), off, mates: mates.length };
          }, [T, c]);
          if (!['ascending', 'descending'].includes(r.dir) || !r.ok) fail('sort', `column ${c.i + 1}: aria-sort "${r.dir}" but the rows are ${r.ok ? 'in order' : 'not in that order'}`);
          if (r.off) fail('sort', `column ${c.i + 1}: ${r.off} of ${r.mates} table(s) in its sort group not sorted the same way`);
          const expect = !want || want === 'none' ? firstDir : toggle || want === firstDir ? flip(want) : firstDir;
          if (r.dir !== expect) fail('sort', `column ${c.i + 1}, press ${press + 1}: aria-sort "${r.dir}", expected "${expect}"${toggle ? ' (a two-state table flips on every press)' : ''}`);
          want = r.dir;
        }
      }
      const def = cols.find(c => c.kind === 'default');
      if (def) {
        for (let press = 0; press < 2; press++) {
          if (await page.$eval(`${T} thead th:nth-child(${def.i + 1})`, h => h.getAttribute('aria-sort')) === 'ascending' && press) break;
          await click(`${T} thead th:nth-child(${def.i + 1}) button`, 'the default column');
        }
        if ((await rowsNow()).join('|') !== first.join('|')) fail('sort', 'the default column does not restore the page\'s order');
      } else if (!toggle) fail('sort', 'a sortable table without a data-sort="default" column cannot return to its own order: add one, or make it data-rk-sort="toggle"');
    }
    // the highlight: pointing lights one kind, leaving resets it, a sort leaves nothing lit
    const triggers = await page.$$eval('[data-lit]', ts => ts.map((t, i) => (t.dataset.rkCheckLit = i, t.checkVisibility({ visibilityProperty: true }) ? i : -1)).filter(i => i >= 0));
    const litState = i => page.evaluate(i => {
      const t = document.querySelector(`[data-rk-check-lit="${i}"]`);
      const scope = t.closest('[data-rk-lit-scope]') || t.closest('table');
      const marks = scope ? [...scope.querySelectorAll('[data-k]')].filter(m => !m.closest('[data-lit]') && m.checkVisibility({ visibilityProperty: true })) : [];
      return { lit: scope && scope.getAttribute('data-rk-lit'), dim: marks.filter(m => +getComputedStyle(m).opacity < 0.5).length, key: t.dataset.lit,
        others: marks.filter(m => m.dataset.k !== t.dataset.lit).length };
    }, i);
    for (const i of triggers.slice(0, 8)) {
      const T = `[data-rk-check-lit="${i}"]`;
      if (!await hover(T, `the highlight on "${i}"`)) continue;
      let s = await litState(i);
      if (s.lit !== s.key || (s.others && !s.dim)) fail('highlight', `pointing at "${s.key}" does not light its marks (lit "${s.lit}", ${s.dim} stepped back)`);
      await page.mouse.move(1, 1);
      await settle(page);
      s = await litState(i);
      if (s.lit || s.dim) fail('highlight', `the "${s.key}" highlight stays after the pointer leaves`);
      await click(T, 'a highlight trigger');
      await page.mouse.move(1, 1);
      await settle(page);
      s = await litState(i);
      if (s.lit || s.dim) fail('highlight', `a click on "${s.key}" leaves marks lit after the pointer leaves`);
    }
    for (const ti of tables) {
      const def = await page.$(`table[data-rk-check="${ti}"] thead th[data-sort="default"] button`);
      for (let press = 0; def && press < 2 && await def.isVisible(); press++) {
        if (await def.evaluate(b => b.closest('th').getAttribute('aria-sort')) === 'ascending') break;
        await def.click(); await page.mouse.move(1, 1); await settle(page);
      }
    }
  }
  // filters: the panel opens from its button, a box turned off is counted, "Show all" turns them on, Escape closes
  for (const p of ps.length ? ps : [null]) {
    await openPanel(page, p);
    const fs = await page.$$eval('details[data-rk-filter]', ds => ds.map((d, i) => (d.dataset.rkCheckF = i, d.checkVisibility({ visibilityProperty: true }) ? i : -1)).filter(i => i >= 0));
    for (const i of fs) {
      const F = `details[data-rk-check-f="${i}"]`;
      try {
        await page.click(`${F} > summary`); await settle(page);
        const box = `${F} .rk-filter-panel input[type=checkbox]`;
        if (!(await page.$eval(F, d => d.open))) { fail('filter', 'its button does not open the panel'); continue; }
        await page.click(box); await settle(page);
        const n = await page.$eval(`${F} .rk-filter-count`, c => c.textContent);
        if (!/1/.test(n)) fail('filter', `one box off, but the button says "${n}"`);
        const reset = await page.$(`${F} .rk-filter-reset`);
        if (reset) { await reset.click(); await settle(page); }
        if (await page.$$eval(box, bs => bs.some(b => !b.checked))) fail('filter', '"Show all" leaves a box off');
        await page.keyboard.press('Escape'); await settle(page);
        if (await page.$eval(F, d => d.open)) fail('filter', 'Escape does not close the panel');
      } catch (e) { fail('filter', `a filter could not be used: ${String(e.message).split('\n')[0]}`); }
    }
  }
  // the bubble: hover, Escape, focus, blur; pin, drag and close when the page allows pinning
  await openPanel(page, ps[0]);
  const tip = await page.evaluate(() => {
    const els = [...document.querySelectorAll('[data-tip]')].filter(e => e.checkVisibility({ visibilityProperty: true }));
    const plain = els.find(e => !e.matches('a[href], button, [role=tab], [role=button], input, select, textarea, summary'));
    const el = plain || els[0];
    if (!el) return null;
    el.dataset.rkCheckTip = '1';
    const box = document.querySelector('.rk-tip');
    return { text: el.dataset.tip, pin: !!(box && box.hasAttribute('data-pin') && plain), more: el.dataset.tipMore || null };
  });
  if (tip) {
    const E = '[data-rk-check-tip="1"]';
    const bubble = () => page.evaluate(() => { const b = document.querySelector('.rk-tip'); return b ? { shown: !b.hidden && b.checkVisibility({ visibilityProperty: true }), text: b.textContent, pinned: b.classList.contains('is-pinned'), x: b.getBoundingClientRect().left, y: b.getBoundingClientRect().top, inView: (() => { const r = b.getBoundingClientRect(); return b.hidden || (r.left >= 0 && r.right <= document.documentElement.clientWidth && r.top >= 0 && r.bottom <= innerHeight); })() } : null; });
    await hover(E, 'a definition');
    let b = await bubble();
    if (!b || !b.shown || !b.text.includes(tip.text)) fail('bubble', 'hovering a definition does not show it');
    else if (!b.inView) fail('bubble', 'the bubble opens partly outside the viewport');
    await page.keyboard.press('Escape'); await settle(page);
    if ((b = await bubble()) && b.shown) fail('bubble', 'Escape does not close the bubble');
    await page.mouse.move(1, 1);
    await page.evaluate(E => document.querySelector(E).focus(), E); await settle(page);
    if (!(b = await bubble()) || !b.shown) fail('bubble', 'focusing a definition does not show it');
    await page.evaluate(E => document.querySelector(E).blur(), E); await settle(page);
    if ((b = await bubble()) && b.shown) fail('bubble', 'the bubble stays after focus leaves');
    if (tip.pin) {
      await click(E, 'pinning a definition');
      b = await bubble();
      if (!b || !b.pinned) fail('bubble', 'a click does not pin the definition');
      else {
        const h = await page.$('.rk-tip .rk-tip-handle');
        const hb = await h.boundingBox();
        await page.mouse.move(hb.x + 10, hb.y + hb.height / 2);
        await page.mouse.down();
        await page.mouse.move(hb.x - 30, hb.y + hb.height / 2 + 40, { steps: 4 });
        await page.mouse.up();
        const moved = await bubble();
        if (Math.abs(moved.x - b.x) < 5 && Math.abs(moved.y - b.y) < 5) fail('bubble', 'dragging the pinned bubble by its handle does not move it');
        await click('.rk-tip .rk-tip-close', 'the bubble\'s close button');
        if ((b = await bubble()) && (b.shown || b.pinned)) fail('bubble', 'the close button does not close the pinned bubble');
        if (tip.more) {
          await click(E, 'pinning a definition');
          await click('.rk-tip .rk-tip-more a', 'the bubble\'s "more" link');
          const r = await page.evaluate(id => { const t = document.querySelector(id); return !!t && t.checkVisibility({ visibilityProperty: true }); }, tip.more);
          if (!r) fail('bubble', `the bubble's "more" link does not bring ${tip.more} into view`);
          await openPanel(page, ps[0]);
        }
      }
    }
  }
  return out;
}

async function checkFile(browser, file) {
  const findings = staticChecks(fs.readFileSync(file, 'utf8')).map(f => ({ ...f, at: ['source'] }));
  const url = 'file://' + path.resolve(file);
  const runs = [];
  for (const theme of ['light', 'dark']) for (const w of WIDTHS) runs.push({ w, theme, big: false });
  for (const w of WIDTHS) runs.push({ w, theme: 'light', big: true });
  const add = (list, tag) => list.forEach(f => findings.push({ ...f, at: [tag] }));
  for (const run of runs) {
    const tag = `${run.w} ${run.theme}${run.big ? ' 200% text' : ''}`;
    const ctx = await browser.newContext({ viewport: { width: run.w, height: 900 }, colorScheme: run.theme, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    page.setDefaultTimeout(8000);
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    page.on('pageerror', e => errs.push(String(e)));
    if (run.big) {
      const cdp = await ctx.newCDPSession(page);
      await cdp.send('Page.enable');
      await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } });
    }
    await page.goto(url, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(250);
    if (run.big) {
      const fs2 = await page.evaluate(() => getComputedStyle(document.documentElement).fontSize);
      if (fs2 !== '32px') add([{ kind: 'static', text: `the 200% text size did not take (root font ${fs2}); a root font-size in px blocks it`, where: 'page' }], tag);
    }
    if (runs.indexOf(run) === 0) {
      const font = await page.evaluate(() => { const f = getComputedStyle(document.querySelector('.rk-section, .rk-wrap, .rk-table') || document.body).fontFamily.split(',')[0].trim().replace(/["']/g, ''); return { f, ok: document.fonts.check(`16px "${f}"`) && [...document.fonts].some(x => x.family.replace(/["']/g, '') === f && x.status === 'loaded') }; });
      if (!font.ok) add([{ kind: 'static', text: `the web font "${font.f}" did not load (measured in a fallback, the geometry is wrong)`, where: 'page' }], tag);
    }
    if (SHOTS && !run.big) {
      fs.mkdirSync(SHOTS, { recursive: true });
      await page.screenshot({ path: path.join(SHOTS, `${path.basename(file, '.html')}-${run.w}-${run.theme}.png`), fullPage: true });
    }
    if (!run.big && run.w === (QUICK ? 1280 : FOCUS_WIDTH)) {
      await page.keyboard.press('Tab');
      for (const st of await states(page)) { await enter(page, st); add(await page.evaluate(focusCheck), `${tag} ${st.label}`); }
    }
    for (const st of await states(page)) {
      await enter(page, st);
      await page.evaluate(() => window.scrollTo(0, 0));
      await settle(page);
      add(await page.evaluate(inspect), `${tag} ${st.label}`);
    }
    if (!run.big) add(await behaviour(page), tag);
    errs.forEach(e => add([{ kind: 'console', text: e.slice(0, 200), where: 'page' }], tag));
    await ctx.close();
  }
  // one line per finding, with every place it happened
  const groups = new Map();
  for (const f of findings) {
    const k = [f.kind, f.text, f.where].join('|');
    if (!groups.has(k)) groups.set(k, { ...f, at: [] });
    groups.get(k).at.push(...f.at);
  }
  return [...groups.values()];
}

async function selftest(browser, file) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto('file://' + path.resolve(file));
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    const s = document.createElement('section');
    s.innerHTML = `<h2>planted</h2>
      <div style="width:120px;overflow:hidden;white-space:nowrap"><span>a long line cut by its box</span></div>
      <p style="width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">an ellipsis that truncates</p>
      <p style="color:rgb(200,200,200)">faint words</p>
      <h3 style="color:rgb(90,98,120)">a grey sub-head</h3><p>its words in ink</p><h5>skipped a level</h5>
      <svg viewBox="0 0 100 30" width="100" height="30"><text x="-20" y="20">past the viewBox</text></svg>
      <p><span>one</span><span style="margin-left:-20px">two on top</span></p>
      <button type="button" style="outline:none">no focus ring</button>
      <div style="width:3000px">wider than the page</div>
      <div style="height:40px;overflow:auto;line-height:20px"><div>in view</div><div>in view too</div><div>scrolled out of sight</div></div><p style="margin-top:0;line-height:20px">just below the box</p>`;
    document.querySelector('main').prepend(s);
  });
  const found = await page.evaluate(inspect);
  await page.keyboard.press('Tab');
  found.push(...await page.evaluate(focusCheck));
  found.push(...staticChecks('<style>.x { color: #abcdef; background-clip: text; font-family: Arial }</style><p>\u{1F680}</p>'));
  const brand = staticChecks('<svg viewBox="0 0 8 8"><path fill="#7262ff" d="M0 0h8v8z"/></svg>');
  const want = { clip: /cut by its box/, overflow: /ellipsis/, contrast: /faint words/, viewbox: /past the viewBox/, overlap: /one|two on top/, muted: /a grey sub-head/, outline: /skipped a level/, focus: /no focus ring/, hscroll: /sideways/, static: /raw colour/ };
  let missed = 0;
  for (const [kind, re] of Object.entries(want)) {
    const hit = found.some(f => f.kind === kind && re.test(f.text));
    console.log(`selftest ${kind}: ${hit ? 'found' : 'MISSED'}`);
    if (!hit) missed++;
  }
  console.log(`selftest brand mark: ${brand.length ? 'FLAGGED (an <svg>\'s own colours are exempt)' : 'exempt'}`);
  if (brand.length) missed++;
  const scrolled = found.some(f => f.kind === 'overlap' && /scrolled out of sight|just below the box/.test(f.text));
  console.log(`selftest text scrolled out of a box: ${scrolled ? 'FLAGGED (what a scroll box hides overlaps nothing)' : 'not an overlap'}`);
  if (scrolled) missed++;
  await ctx.close();
  return missed;
}

(async () => {
  if (!args.length) { console.error('usage: node bin/check.cjs <page.html>... [--quick] [--shots <dir>] | --selftest <page.html>'); process.exit(2); }
  const browser = await chromium.launch();
  if (SELFTEST) { const missed = await selftest(browser, args[0]); await browser.close(); console.log(missed ? `${missed} problems` : '0 problems'); process.exit(missed ? 1 : 0); }
  let total = 0;
  for (const file of args) {
    const found = await checkFile(browser, file);
    for (const f of found) {
      const at = [...new Set(f.at)];
      console.log(`${file}: [${f.kind}] ${f.where}: ${f.text}\n    at ${at.slice(0, 4).join('; ')}${at.length > 4 ? `; and ${at.length - 4} more` : ''}`);
    }
    total += found.length;
  }
  await browser.close();
  console.log(`${total} problems`);
  process.exit(total ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
