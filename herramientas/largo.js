// PDF de una sola página continua (alto = contenido) + PNG para WhatsApp
const { chromium } = require('playwright');
(async () => {
  const [, , html, pdf, png] = process.argv;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 794, height: 1123 }, deviceScaleFactor: 2 });
  await p.goto('file://' + html, { waitUntil: 'networkidle' });
  await p.evaluate(() => document.fonts.ready);
  const el = await p.$('.page');
  const box = await el.boundingBox();
  await p.pdf({ path: pdf, width: '210mm', height: `${Math.ceil(box.height) + 1}px`, printBackground: true,
                margin: { top: 0, right: 0, bottom: 0, left: 0 } });
  await el.screenshot({ path: png });
  console.log('alto px', box.height);
  await b.close();
})();
