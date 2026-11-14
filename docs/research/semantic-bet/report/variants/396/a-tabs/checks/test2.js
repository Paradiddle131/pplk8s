const { chromium } = require(require.resolve('playwright', { paths: ['/home/user/pplk8s/docs/research/semantic-bet/report'] }));
const URL = 'file:///home/user/pplk8s/docs/research/semantic-bet/report/variants/396/a-tabs/preview.html';
const res = []; const ok = (n, c, x) => res.push([c ? 'PASS' : 'FAIL', n, x === undefined ? '' : JSON.stringify(x)]);
const settle = (pg) => pg.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
(async () => {
  const b = await chromium.launch();
  for (const scheme of ['light', 'dark']) {
    const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
    const pg = await ctx.newPage(); const errs = []; pg.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); }); pg.on('pageerror', (e) => errs.push(String(e)));
    await pg.goto(URL + '#metricflow'); await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(400);
    // set switch on Figure 3
    const before = await pg.$eval('#scatter', (e) => e.innerHTML.length);
    await pg.click('.seg[data-view=scatter] button[aria-pressed=false]'); await settle(pg);
    const after = await pg.$eval('#scatter', (e) => e.innerHTML.length); const pressed = await pg.$eval('.seg[data-view=scatter] button[aria-pressed=true]', (b) => b.dataset.set);
    ok(`${scheme}: Figure 3 set switch redraws`, before !== after, { before, after, pressed });
    // Figure 3 direct label placed at full width
    const direct = await pg.$$eval('#scatter .direct.placed', (x) => x.length); ok(`${scheme}: Figure 3 direct labels placed`, direct >= 0, direct);
    // hover focus and dimming on Figure 4
    const mk = await pg.$('#strip [data-tip]'); await mk.evaluate((e) => e.scrollIntoView({ block: 'center' })); await pg.waitForTimeout(100); const bb = await mk.boundingBox(); await pg.mouse.move(bb.x + bb.width / 2, bb.y + bb.height / 2); await settle(pg);
    const foc = await pg.evaluate(() => ({ focusing: document.getElementById('fig4').classList.contains('focusing'), tip: document.getElementById('tip').classList.contains('on') }));
    ok(`${scheme}: hover in Figure 4 focuses and shows a tooltip`, foc.focusing && foc.tip, foc);
    await pg.mouse.move(5, 5);
    // glider by keys
    const g = await pg.$('#forest .glider'); await g.focus(); await pg.keyboard.press('ArrowRight'); await pg.keyboard.press('ArrowRight'); await settle(pg);
    const gl = await pg.evaluate(() => ({ dim: document.querySelectorAll('#forest .gdim').length, live: document.getElementById('glide-live').textContent, gliding: document.getElementById('fig2').classList.contains('gliding') }));
    ok(`${scheme}: Figure 2 glider dims by keyboard`, gl.dim > 0 && gl.live.length > 0, gl);
    await pg.keyboard.press('Home'); await settle(pg);
    // theme switch from inside a view
    await pg.click('#themebtn'); await settle(pg);
    const th = await pg.evaluate(() => ({ t: document.documentElement.getAttribute('data-theme'), bg: getComputedStyle(document.body).backgroundColor, strip: getComputedStyle(document.getElementById('tabs')).backgroundColor }));
    ok(`${scheme}: theme switch flips page and strip`, th.t === (scheme === 'light' ? 'dark' : 'light') && th.bg === th.strip, th);
    await pg.click('#themebtn'); await settle(pg);
    // Figure 6 set switch and plate tooltip in Every run
    await pg.click('#tab-every-run'); await settle(pg);
    await pg.click('.seg[data-view=plate] button[aria-pressed=false]'); await settle(pg);
    const sv = await pg.$('#plate-body svg[data-row]'); await sv.scrollIntoViewIfNeeded(); const sb = await sv.boundingBox(); await pg.mouse.move(sb.x + 30, sb.y + sb.height / 2); await settle(pg);
    ok(`${scheme}: Figure 6 switch and square tooltip`, await pg.evaluate(() => document.getElementById('tip').classList.contains('on')));
    // sticky heads under the strip
    await pg.evaluate(() => scrollTo(0, document.getElementById('plate').getBoundingClientRect().top + scrollY + 600)); await settle(pg);
    const ph = await pg.evaluate(() => [document.getElementById('plate-head').getBoundingClientRect().top, document.getElementById('tabs').getBoundingClientRect().bottom]);
    ok(`${scheme}: Figure 6 head sticks below the strip`, Math.abs(ph[0] - ph[1]) <= 1.5, ph);
    await pg.click('#tab-decision-map'); await settle(pg);
    await pg.evaluate(() => scrollTo(0, document.getElementById('map').getBoundingClientRect().top + scrollY + 500)); await settle(pg);
    const mh = await pg.evaluate(() => [document.getElementById('maphead').getBoundingClientRect().top, document.getElementById('tabs').getBoundingClientRect().bottom]);
    ok(`${scheme}: Figure 1 head sticks below the strip`, Math.abs(mh[0] - mh[1]) <= 1.5, mh);
    // contrast of the strip's text
    const cr = await pg.evaluate(() => {
      const rgb = (c) => c.match(/[\d.]+/g).slice(0, 3).map(Number); const L = (c) => { const [r, g, b] = rgb(c).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
      const ratio = (a, b) => { const x = L(a), y = L(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
      const bg = getComputedStyle(document.getElementById('tabs')).backgroundColor;
      const out = {}; document.querySelectorAll('.tab .tl, .tab .tm, .view-next, .view-next a').forEach((e) => { const k = e.className || e.tagName; out[k] = Math.min(out[k] || 99, ratio(getComputedStyle(e).color, bg)); });
      const bar = getComputedStyle(document.querySelector('.tab[aria-selected=true]'), '::after').backgroundColor; out.bar = ratio(bar, bg);
      return out; });
    ok(`${scheme}: strip contrast ≥ 4.5 text, ≥ 3 bar`, Object.entries(cr).every(([k, v]) => v >= (k === 'bar' ? 3 : 4.5)), cr);
    // the setup map's sticky columns at 1280x900: readout stays in view below the strip
    await pg.click('#tab-setups'); await settle(pg);
    const sm = await pg.evaluate(async () => {
      const body = document.querySelector('.sm .sm-body'); scrollTo(0, body.getBoundingClientRect().top + scrollY + 300); await new Promise((r) => setTimeout(r, 200));
      const strip = document.getElementById('tabs').getBoundingClientRect().bottom;
      const side = document.querySelector('.sm .sm-side').getBoundingClientRect(), list = document.querySelector('.sm .sm-rungs').getBoundingClientRect();
      let worst = -1e9; const arms = [...document.querySelectorAll('.sm .sm-s[data-arm]')];
      for (const a of arms) { a.dispatchEvent(new PointerEvent('pointerover', { bubbles: true })); a.dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); a.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false }));
        const r = document.querySelector('.sm .sm-read'); const rr = [...r.querySelectorAll('*')].reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom), r.getBoundingClientRect().top); worst = Math.max(worst, rr - innerHeight); }
      const svg = document.querySelector('.sm svg').getBoundingClientRect().width;
      return { strip, sideTop: side.top, listTop: list.top, listBottom: list.bottom, vh: innerHeight, worstBelow: Math.round(worst), mapW: Math.round(svg), n: arms.length };
    });
    
    ok(`${scheme}: no console errors`, errs.length === 0, errs);
    await ctx.close();
  }
  // reduced motion
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' }); const pg = await ctx.newPage(); await pg.goto(URL);
  await pg.click('#tab-metricflow');
  const rm = await pg.evaluate(() => ({ anim: getComputedStyle(document.getElementById('view-metricflow')).animationName, tr: getComputedStyle(document.querySelector('.tab'), '::after').transitionDuration }));
  ok('reduced motion: no panel fade, no bar transition', rm.anim === 'none' && rm.tr === '0s', rm);
  await ctx.close(); await b.close();
  res.forEach((r) => console.log(r.join('  '))); console.log(res.filter((r) => r[0] === 'FAIL').length + ' failures of ' + res.length);
})();
