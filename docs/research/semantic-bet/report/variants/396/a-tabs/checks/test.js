const { chromium } = require(require.resolve('playwright', { paths: ['/home/user/pplk8s/docs/research/semantic-bet/report'] }));
const URL = 'file:///home/user/pplk8s/docs/research/semantic-bet/report/variants/396/a-tabs/preview.html';
const res = []; const ok = (name, cond, extra) => { res.push([cond ? 'PASS' : 'FAIL', name, extra === undefined ? '' : JSON.stringify(extra)]); };
const settle = (pg) => pg.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
async function open(b, w, h, hash, opts) {
  const ctx = await b.newContext(Object.assign({ viewport: { width: w, height: h } }, opts || {}));
  const pg = await ctx.newPage(); pg.errs = [];
  pg.on('console', (m) => { if (m.type() === 'error') pg.errs.push(m.text()); }); pg.on('pageerror', (e) => pg.errs.push(String(e)));
  await pg.goto(URL + (hash || ''), { waitUntil: 'load' }); await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(300);
  return pg;
}
const state = (pg) => pg.evaluate(() => {
  const on = [...document.querySelectorAll('.view.on')].map((v) => v.dataset.view);
  const sel = [...document.querySelectorAll('[role=tab][aria-selected=true]')].map((t) => t.id);
  const ti = [...document.querySelectorAll('[role=tab]')].filter((t) => t.tabIndex === 0).map((t) => t.id);
  const inertBad = [...document.querySelectorAll('.view')].filter((v) => v.classList.contains('on') === v.inert).length;
  return { on, sel, ti, inertBad, hash: location.hash, y: Math.round(scrollY), active: document.activeElement && (document.activeElement.id || document.activeElement.className) };
});
// every figure's drawn width against its container's
const widths = (pg) => pg.evaluate(() => {
  const sizes = {}; for (const id of ['forest','scatter','strip','slopes']) sizes[id] = [...document.querySelectorAll('#' + id + ' svg')].filter((s) => !s.closest('.glider')).map((s) => Math.round(s.getBoundingClientRect().width) + 'x' + Math.round(s.getBoundingClientRect().height)).join(' ');
  const out = {};
  for (const id of ['forest', 'scatter', 'strip', 'slopes']) { const el = document.getElementById(id); const svgs = [...el.querySelectorAll(':scope > svg, :scope > div > svg')]; const sw = svgs.length ? Math.max(...svgs.map((s) => +s.getAttribute('width') || s.viewBox.baseVal.width)) : 0; out[id] = [el.clientWidth, Math.round(sw)]; }
  const pb = document.getElementById('plate-body'); out.plate = [pb.clientWidth, pb.firstElementChild ? Math.round(pb.firstElementChild.getBoundingClientRect().width) : 0];
  out.sizes = sizes; return out;
});
async function orig(b, w, h) { const pg = await b.newPage({ viewport: { width: w, height: h } }); await pg.goto('file:///home/user/pplk8s/docs/research/semantic-bet/report/index.html'); await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(400); const W = await widths(pg); await pg.close(); return W; }
const same = (a, b) => JSON.stringify(a.sizes) === JSON.stringify(b.sizes);
(async () => {
  const b = await chromium.launch();
  // 1. click each tab
  let pg = await open(b, 1280, 900);
  const names = await pg.$$eval('[role=tab]', (ts) => ts.map((t) => t.getAttribute('aria-controls').replace('view-', '')));
  for (const n of names) {
    await pg.click(`#tab-${n}`); await settle(pg);
    const s = await state(pg);
    ok(`click opens ${n}`, s.on.length === 1 && s.on[0] === n && s.sel[0] === 'tab-' + n && s.ti[0] === 'tab-' + n && s.inertBad === 0 && (s.hash === '#' + n || (n === 'summary' && s.hash === '')), s);
    const vis = await pg.evaluate((n) => { const v = document.getElementById('view-' + n); const r = v.getBoundingClientRect(); return r.height > 50 && getComputedStyle(v).visibility === 'visible'; }, n);
    ok(`  ${n} visible`, vis);
  }
  // 2. Back/Forward through the clicks
  await pg.goBack(); await settle(pg); let s = await state(pg); ok('Back -> previous view', s.on[0] === names[names.length - 2] && s.hash === '#' + names[names.length - 2], s);
  await pg.goBack(); await settle(pg); s = await state(pg); ok('Back again', s.on[0] === names[names.length - 3], s);
  await pg.goForward(); await settle(pg); s = await state(pg); ok('Forward', s.on[0] === names[names.length - 2], s);
  // scroll restore through history
  await pg.click('#tab-metricflow'); await settle(pg); await pg.evaluate(() => scrollTo(0, 1500)); await pg.waitForTimeout(250);
  await pg.click('#tab-every-run'); await settle(pg); const yRun = (await state(pg)).y;
  await pg.goBack(); await settle(pg); s = await state(pg); ok('Back restores scroll position', s.on[0] === 'metricflow' && Math.abs(s.y - 1500) < 3, { s, yRun });
  ok('no console errors (clicks)', pg.errs.length === 0, pg.errs);
  await pg.context().close();

  // 3. keyboard
  pg = await open(b, 1280, 900);
  await pg.focus('#tab-summary');
  await pg.keyboard.press('ArrowRight'); await settle(pg); s = await state(pg);
  ok('ArrowRight moves focus and opens next', s.on[0] === 'decision-map' && s.active === 'tab-decision-map' && s.ti[0] === 'tab-decision-map', s);
  await pg.keyboard.press('ArrowRight'); await pg.keyboard.press('ArrowRight'); await settle(pg); s = await state(pg);
  ok('two more ArrowRight', s.on[0] === 'every-run' && s.active === 'tab-every-run', s);
  await pg.keyboard.press('End'); await settle(pg); s = await state(pg); ok('End', s.on[0] === names[names.length - 1] && s.active === 'tab-' + names[names.length - 1], s);
  await pg.keyboard.press('ArrowRight'); await settle(pg); s = await state(pg); ok('ArrowRight wraps to first', s.on[0] === 'summary', s);
  await pg.keyboard.press('ArrowLeft'); await settle(pg); s = await state(pg); ok('ArrowLeft wraps to last', s.on[0] === names[names.length - 1], s);
  await pg.keyboard.press('Home'); await settle(pg); s = await state(pg); ok('Home', s.on[0] === 'summary' && s.active === 'tab-summary', s);
  const hl = await pg.evaluate(() => history.length); ok('arrow keys leave one history step', hl <= 3, hl);
  await pg.keyboard.press('ArrowRight'); await pg.keyboard.press('Tab'); await settle(pg);
  const tabInto = await pg.evaluate(() => { const a = document.activeElement; return { inView: !!a.closest('#view-decision-map'), what: a.outerHTML.slice(0, 90) }; });
  ok('Tab from the strip enters the open view', tabInto.inView, tabInto);
  const roles = await pg.evaluate(() => { const t = [...document.querySelectorAll('[role=tab]')]; return t.every((x) => x.parentElement.getAttribute('role') === 'tablist' && document.getElementById(x.getAttribute('aria-controls')).getAttribute('role') === 'tabpanel' && document.getElementById(x.getAttribute('aria-controls')).getAttribute('aria-labelledby') === x.id); });
  ok('ARIA roles wired', roles);
  await pg.context().close();

  // 4. URLs
  for (const [hash, view, sel] of [['#metricflow', 'metricflow'], ['#every-run', 'every-run'], ['#term-confident-wrong', 'method', '#term-confident-wrong'], ['#map-custom-metricflow', 'decision-map', '#map-custom-metricflow'], ['#setup-custom-hybrid', 'setups', 'section.sxb'], ['#other-set-versions', 'question-sets', '#other-set-versions'], ['#setup-map', 'setups', '#setup-map'], ['#nonsense', 'summary']]) {
    pg = await open(b, 1280, 900, hash); await pg.waitForTimeout(200); s = await state(pg);
    let inV = true;
    if (sel) inV = await pg.evaluate((sel) => { const r = document.querySelector(sel).getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight - 40; }, sel);
    let extra = '';
    if (hash === '#setup-custom-hybrid') extra = await pg.evaluate(() => (document.querySelector('.sxb-chip[aria-checked=true]') || {}).dataset?.arm);
    ok(`URL ${hash} opens ${view}`, s.on[0] === view && inV && (hash !== '#setup-custom-hybrid' || extra === 'custom-hybrid') && pg.errs.length === 0, { s, inV, extra, errs: pg.errs });
    if (hash === '#metricflow') { await pg.evaluate(() => scrollTo(0, 900)); await pg.waitForTimeout(250); await pg.reload({ waitUntil: 'load' }); await pg.waitForTimeout(500); s = await state(pg); ok('reload keeps view and place', s.on[0] === 'metricflow' && Math.abs(s.y - 900) < 3, s); }
    await pg.context().close();
  }

  // 5. jumps from a pinned tooltip, across views
  for (const [w, h] of [[1280, 900], [390, 844]]) {
    pg = await open(b, w, h, '#metricflow');
    await pg.evaluate(() => scrollTo(0, 400)); await pg.waitForTimeout(250);
    const termSel = '#view-metricflow h2 [data-term="uncovered"]';
    await pg.locator(termSel).scrollIntoViewIfNeeded(); await pg.waitForTimeout(250);
    const y0 = await pg.evaluate(() => Math.round(scrollY));
    await pg.click(termSel); await settle(pg);
    const link = await pg.$eval('#tip .tipjump a', (a) => a.textContent).catch(() => null);
    ok(`${w}: pinned term tooltip offers glossary jump`, link && /glossary/.test(link), link);
    await pg.click('#tip .tipjump a'); await settle(pg);
    s = await state(pg);
    const j = await pg.evaluate(() => { const t = document.getElementById('term-uncovered'); const r = t.getBoundingClientRect(); return { flashed: t.classList.contains('jumped'), anim: getComputedStyle(t).animationName, inV: r.top > 0 && r.bottom < innerHeight, back: !!t.querySelector('.jumpback'), focus: document.activeElement.className }; });
    ok(`${w}: glossary jump opens Method, scrolls, flashes, offers Back`, s.on[0] === 'method' && s.hash === '#term-uncovered' && j.flashed && j.inV && j.back && j.focus === 'jumpback', { s, j });
    if (w === 1280) { await pg.waitForTimeout(250); await pg.screenshot({ path: 'jump-glossary.png' }); }
    await pg.click('.jumpback'); await pg.waitForTimeout(300);
    s = await state(pg);
    ok(`${w}: ↑ Back returns to the view and place`, s.on[0] === 'metricflow' && Math.abs(s.y - y0) < 3 && s.hash === '#metricflow', { s, y0 });
    const foc = await pg.evaluate(() => document.activeElement.dataset.term); ok(`${w}: focus back on the term`, foc === 'uncovered', foc);
    // setup -> map row, from the Every run view
    await pg.click('#tab-every-run'); await settle(pg);
    const setupSel = '#plate-body .pl .id[data-setup="custom-metricflow"]';
    await pg.locator(setupSel).first().scrollIntoViewIfNeeded(); await pg.waitForTimeout(200);
    const y1 = await pg.evaluate(() => Math.round(scrollY));
    await pg.locator(setupSel).first().click(); await settle(pg);
    const l2 = await pg.$eval('#tip .tipjump a', (a) => a.textContent).catch(() => null);
    ok(`${w}: setup tooltip offers map jump`, l2 && /map/.test(l2), l2);
    await pg.click('#tip .tipjump a'); await settle(pg);
    s = await state(pg);
    const j2 = await pg.evaluate(() => { const t = document.getElementById('map-custom-metricflow'); const r = t.getBoundingClientRect(); const head = document.getElementById('maphead').getBoundingClientRect(); return { flashed: t.classList.contains('jumped'), inV: r.top >= head.bottom - 1 && r.bottom < innerHeight, back: !!t.querySelector('.jumpback') }; });
    ok(`${w}: map jump opens Decision map, row below sticky head, flashes`, s.on[0] === 'decision-map' && j2.flashed && j2.inV && j2.back, { s, j2 });
    await pg.click('.jumpback'); await pg.waitForTimeout(300); s = await state(pg);
    ok(`${w}: ↑ Back to Every run at the same place`, s.on[0] === 'every-run' && Math.abs(s.y - y1) < 3, { s, y1 });
    // browser Back after a jump also returns, and drops the stale ↑ Back
    await pg.locator(setupSel).first().click(); await settle(pg); await pg.click('#tip .tipjump a'); await settle(pg);
    await pg.goBack(); await pg.waitForTimeout(300); s = await state(pg);
    const stale = await pg.$$eval('.jumpback', (x) => x.length);
    ok(`${w}: browser Back after a jump returns and clears ↑ Back`, s.on[0] === 'every-run' && Math.abs(s.y - y1) < 3 && stale === 0, { s, stale });
    ok(`${w}: no console errors (jumps)`, pg.errs.length === 0, pg.errs);
    await pg.context().close();
  }

  // 6. figures at full width: shown first time, and after a resize while hidden
  pg = await open(b, 1280, 900);
  await pg.setViewportSize({ width: 900, height: 900 }); await pg.waitForTimeout(400);
  await pg.click('#tab-metricflow'); await settle(pg); let W = await widths(pg);
  let O = await orig(b, 900, 900); ok('resize while hidden, then open MetricFlow: figures as drawn by the original page at 900', same(W, O) && W.forest[0] > 800, { W: W.sizes, O: O.sizes });
  await pg.click('#tab-summary'); await pg.setViewportSize({ width: 1180, height: 900 }); await pg.waitForTimeout(400);
  await pg.click('#tab-every-run'); await settle(pg); W = await widths(pg);
  ok('resize while hidden, then open Every run: plate fills', W.plate[0] > 1100 && W.plate[1] >= W.plate[0] - 1, W.plate);
  await pg.click('#tab-metricflow'); await settle(pg); W = await widths(pg);
  O = await orig(b, 1180, 900); ok('MetricFlow at 1180 matches the original', same(W, O), { W: W.sizes, O: O.sizes });
  ok('no console errors (resize)', pg.errs.length === 0, pg.errs);
  await pg.context().close();
  // phone: every view, figure widths and no page scroll
  pg = await open(b, 390, 844, '', { hasTouch: true, deviceScaleFactor: 2 });
  for (const n of names) {
    await pg.evaluate((n) => document.getElementById('tab-' + n).click(), n); await pg.waitForTimeout(700);
    const m = await pg.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    const tabVis = await pg.evaluate((n) => { const t = document.getElementById('tab-' + n), r = t.getBoundingClientRect(), rr = t.parentElement.getBoundingClientRect(); return r.left >= rr.left - 1 && r.right <= rr.right + 1; }, n);
    ok(`390: ${n} no page scroll, active tab in view`, m.sw <= m.cw && tabVis, { m, tabVis });
  }
  await pg.evaluate(() => document.getElementById('tab-metricflow').click()); await settle(pg); W = await widths(pg);
  O = await orig(b, 390, 844); ok('390: MetricFlow figures match the original', same(W, O), { W: W.sizes, O: O.sizes });
  const fades = await pg.evaluate(() => { const r = document.querySelector('.tabs-in'); r.scrollLeft = 0; r.dispatchEvent(new Event('scroll')); const a = document.getElementById('tabs').className; r.scrollLeft = 99999; r.dispatchEvent(new Event('scroll')); const b = document.getElementById('tabs').className; r.scrollLeft = 80; r.dispatchEvent(new Event('scroll')); return [a, b, document.getElementById('tabs').className]; });
  ok('390: soft edges follow the strip scroll', /fade-r/.test(fades[0]) && !/fade-l/.test(fades[0]) && /fade-l/.test(fades[1]) && !/fade-r/.test(fades[1]) && /fade-l/.test(fades[2]) && /fade-r/.test(fades[2]), fades);
  ok('390: no console errors', pg.errs.length === 0, pg.errs);
  await pg.context().close();
  await b.close();
  res.forEach((r) => console.log(r.join('  ')));
  console.log(res.filter((r) => r[0] === 'FAIL').length + ' failures of ' + res.length);
})();
