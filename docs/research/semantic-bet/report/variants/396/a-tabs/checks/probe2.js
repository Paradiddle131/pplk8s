const { chromium } = require(require.resolve('playwright', { paths: ['/home/user/pplk8s/docs/research/semantic-bet/report'] }));
(async () => {
  const b = await chromium.launch();
  for (const [w, h] of [[1280, 900], [1280, 800], [1440, 900]]) for (const f of ['index.html', 'variants/396/a-tabs/preview.html#setups']) {
    const pg = await b.newPage({ viewport: { width: w, height: h } });
    await pg.goto('file:///home/user/pplk8s/docs/research/semantic-bet/report/' + f); await pg.waitForTimeout(600);
    const tabs = f.includes('a-tabs');
    await pg.evaluate((tabs) => { const body = document.querySelector('.sm .sm-body'); scrollTo(0, body.getBoundingClientRect().top + scrollY - (tabs ? document.getElementById('tabs').offsetHeight + 8 : 8)); }, tabs);
    await pg.waitForTimeout(150);
    const items = await pg.$$('.sm .sm-s[data-arm], .sm button.sm-rhd[data-rung]'); let worst = -1e9, n = 0;
    for (const it of items) {
      const bb = await it.boundingBox(); if (!bb || bb.y < 60 || bb.y > h - 10) continue;
      await pg.mouse.move(bb.x + 5, bb.y + bb.height / 2); await pg.waitForTimeout(30); n++;
      const r = await pg.evaluate(() => { const r = document.querySelector('.sm .sm-read'); let m = 0; r.querySelectorAll('*').forEach((e) => { if (e.textContent.trim()) m = Math.max(m, e.getBoundingClientRect().bottom); }); return m - innerHeight; });
      worst = Math.max(worst, r);
    }
    const mapW = await pg.evaluate(() => Math.round(document.querySelector('.sm svg').getBoundingClientRect().width));
    console.log(w + 'x' + h, tabs ? 'tabs' : 'orig', 'map', mapW, 'worst readout line vs viewport bottom', Math.round(worst), 'hovered', n, 'of', items.length);
    await pg.close();
  }
  await b.close();
})();
