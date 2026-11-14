const { chromium } = require(require.resolve('playwright', { paths: ['/home/user/pplk8s/docs/research/semantic-bet/report'] }));
const DIR = '/home/user/pplk8s/docs/research/semantic-bet/report/variants/396/a-tabs/';
const URL = 'file://' + DIR + 'preview.html';
const only = process.argv[2];
async function page(b, w, h, scheme, hash) {
  const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2, colorScheme: scheme, hasTouch: w < 500 });
  const pg = await ctx.newPage(); pg.errs = [];
  pg.on('console', (m) => { if (m.type() === 'error') pg.errs.push(m.text()); }); pg.on('pageerror', (e) => pg.errs.push(String(e)));
  await pg.goto(URL + (hash || ''), { waitUntil: 'load' }); await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(500);
  return pg;
}
const partTop = (pg, extra) => pg.evaluate((extra) => { scrollTo(0, document.getElementById('views').getBoundingClientRect().top + scrollY - document.getElementById('tabs').offsetHeight + (extra || 0)); }, extra);
(async () => {
  const b = await chromium.launch(); const errs = [];
  const want = (n) => !only || only === n;
  if (want('1')) { // desktop light, first view
    const pg = await page(b, 1280, 900, 'light');
    await pg.screenshot({ path: DIR + 'shots/desktop-light-summary.png' }); errs.push(...pg.errs); await pg.context().close();
  }
  if (want('2')) { // desktop dark on the figures view, strip stuck over Figure 2
    const pg = await page(b, 1280, 900, 'dark', '#metricflow');
    await partTop(pg, 0); await pg.waitForTimeout(250);
    await pg.screenshot({ path: DIR + 'shots/desktop-dark-metricflow.png' }); errs.push(...pg.errs); await pg.context().close();
  }
  if (want('3')) { // desktop light, a glossary jump done from Figure 4's heading
    const pg = await page(b, 1280, 900, 'light', '#metricflow');
    const t = '#view-metricflow h2 [data-term="uncovered"]';
    await pg.evaluate((t) => document.querySelector(t).scrollIntoView({ block: 'center' }), t); await pg.waitForTimeout(250);
    await pg.click(t); await pg.waitForTimeout(150);
    await pg.click('#tip .tipjump a'); await pg.waitForTimeout(350);
    await pg.mouse.move(1270, 890);
    await pg.screenshot({ path: DIR + 'shots/desktop-light-glossary-jump.png' }); errs.push(...pg.errs); await pg.context().close();
  }
  if (want('4')) { // phone light with the switcher, mid-strip so both soft edges show
    const pg = await page(b, 390, 844, 'light', '#every-run');
    await pg.waitForTimeout(500);
    await pg.screenshot({ path: DIR + 'shots/phone-light-switcher.png' }); errs.push(...pg.errs); await pg.context().close();
  }
  if (want('5')) { // phone dark on the setups view
    const pg = await page(b, 390, 844, 'dark', '#setups');
    await pg.waitForTimeout(500); await partTop(pg, 0); await pg.waitForTimeout(250);
    await pg.screenshot({ path: DIR + 'shots/phone-dark-setups.png' }); errs.push(...pg.errs); await pg.context().close();
  }
  console.log('console errors:', errs.length ? errs : 'none');
  await b.close();
})();
