const { chromium } = require('playwright-core');
(async () => {
  const b = await chromium.connectOverCDP('http://localhost:29229'); const ctx = b.contexts()[0]; const p = await ctx.newPage(); await p.setViewportSize({ width: 1280, height: 900 });
  await p.goto('file:///home/ubuntu/Documents/report/improve-with-ola-v1.html');
  await p.click('#t10'); await p.waitForTimeout(800);
  const figs = await p.$$('#p10 figure');
  for (let i = 0; i < figs.length; i++) await figs[i].screenshot({ path: `g_fig${i}.png` });
  const grids = await p.$$('#p10 > div[style*="grid"]');
  for (let i = 0; i < grids.length; i++) await grids[i].screenshot({ path: `g_grid${i}.png` });
  console.log(figs.length, grids.length); await p.close();
})();
