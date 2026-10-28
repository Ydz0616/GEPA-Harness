const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.connectOverCDP('http://localhost:29229');
  const ctx = b.contexts()[0] || await b.newContext();
  const page = await ctx.newPage(); const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('file:///home/ubuntu/Documents/report/improve-with-ola-v1.html'); await page.waitForTimeout(800);
  const tabs = await page.$$('[role=tab]'); console.log('tabs', tabs.length);
  for (let i = 0; i < tabs.length; i++) {
    await tabs[i].click(); await page.waitForTimeout(500);
    const vis = await page.$$eval('[role=tabpanel]', ps => ps.filter(p => !p.hidden).map(p => p.id));
    console.log('tab', i, 'visible', vis.join(','));
    if (i === 0) { const n = await page.$('[data-a-node]'); await n.click(); await page.waitForTimeout(300); console.log('inspector:', (await page.$eval('[data-a-inspector]', e => e.textContent)).slice(0, 90)); }
    if (i === 2 || i === 5) { const svgs = await page.$$eval('[data-a-chart] svg', s => s.length); console.log('chart svgs', svgs); }
    await page.screenshot({ path: `/home/ubuntu/Documents/report/pw/tab${i+1}.png`, fullPage: i !== 0 });
  }
  await page.setViewportSize({ width: 375, height: 800 }); await tabs[3].click(); await page.waitForTimeout(400);
  await page.screenshot({ path: '/home/ubuntu/Documents/report/pw/mobile.png', fullPage: true });
  console.log('errors', JSON.stringify(errs)); await page.close(); await b.close();
})().catch(e => { console.error('FAIL', e); process.exit(1); });
