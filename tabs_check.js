// Вкладки на странице соревнования: ровно одна панель видна, высота падает, переключение работает.
// Запуск: node scripts/tabs_check.js file:///C:/Users/xslai/monetization/site/lab/contest/index.html
const puppeteer = require('C:/Users/xslai/node_modules/puppeteer-core');

const target = process.argv[2] || 'https://gramwright.pages.dev/lab/contest/?v=' + Date.now();

(async () => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new', args: ['--no-sandbox'],
  });
  const p = await b.newPage();
  let bad = 0;
  for (const w of [390, 1100]) {
    await p.setViewport({ width: w, height: 900 });
    await p.goto(target, { waitUntil: 'networkidle2' });
    const res = await p.evaluate(async () => {
      const panes = [...document.querySelectorAll('.tpane')];
      const btns = [...document.querySelectorAll('.tnav button')];
      const vis = () => panes.filter((x) => getComputedStyle(x).display !== 'none').length;
      const out = { panes: panes.length, btns: btns.length, first: vis(), heights: [] };
      out.noscriptOk = panes.every((x) => x.textContent.trim().length > 50);
      out.heights.push(Math.round(document.documentElement.scrollHeight));
      for (let i = 0; i < btns.length; i++) {
        btns[i].click();
        await new Promise((r) => setTimeout(r, 120));
        out.heights.push({ tab: i, visible: vis(), h: Math.round(document.documentElement.scrollHeight) });
      }
      out.scroll = [document.documentElement.scrollWidth, document.documentElement.clientWidth];
      return out;
    });
    const problems = [];
    if (res.panes !== 3) problems.push(`панелей ${res.panes}`);
    if (res.btns !== 3) problems.push(`кнопок ${res.btns}`);
    if (res.first !== 1) problems.push(`по умолчанию видны ${res.first} панели`);
    if (!res.noscriptOk) problems.push('есть пустая панель');
    for (const h of res.heights.slice(1)) {
      if (h.visible !== 1) problems.push(`вкладка ${h.tab}: видно панелей ${h.visible}`);
    }
    if (res.scroll[0] > res.scroll[1] + 2) problems.push(`горизонтальная прокрутка ${res.scroll[0]}>${res.scroll[1]}`);
    const hs = [res.heights[0], ...res.heights.slice(1).map((x) => x.h)];
    console.log(`${w}px: было ${hs[0]} px · вкладки ${hs.slice(1).join(' / ')} px · `
      + (problems.length ? 'ПРОБЛЕМЫ: ' + problems.join('; ') : 'чисто'));
    bad += problems.length;
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
