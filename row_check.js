// Геометрия строк-карточек: название участника и значение не должны пересекаться,
// а длинное значение не имеет права сжимать название в столбик из трёх строк.
// Запуск: node scripts/row_check.js file:///C:/Users/xslai/monetization/site/lab/contest/index.html
const puppeteer = require('C:/Users/xslai/node_modules/puppeteer-core');

const target = process.argv[2] || 'https://gramwright.pages.dev/lab/contest/?v=' + Date.now();

(async () => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new', args: ['--no-sandbox'],
  });
  const p = await b.newPage();
  let bad = 0;
  for (const w of [390, 560, 700, 1100]) {
    await p.setViewport({ width: w, height: 900 });
    await p.goto(target, { waitUntil: 'networkidle2' });
    const r = await p.evaluate(() => {
      const out = [];
      const inter = (a, b) => !(a.right <= b.left + 1 || b.right <= a.left + 1 ||
                                a.bottom <= b.top + 1 || b.bottom <= a.top + 1);
      document.querySelectorAll('.rrow').forEach((row, i) => {
        const nm = row.querySelector('.rname');
        const vl = row.querySelector('.rval');
        if (!nm || !vl) return;
        const a = nm.getBoundingClientRect(), c = vl.getBoundingClientRect();
        const label = (vl.textContent || '').trim().slice(0, 34);
        if (inter(a, c)) out.push(`строка ${i}: значение перекрывает название («${label}»)`);
        const fs = parseFloat(getComputedStyle(nm).fontSize) || 16;
        if (a.height > fs * 3.2) out.push(`строка ${i}: название развалилось на ${Math.round(a.height / (fs * 1.35))} строк («${label}»)`);
        if (vl.scrollWidth > vl.clientWidth + 2) out.push(`строка ${i}: значение шире своей колонки («${label}»)`);
      });
      const de = document.documentElement;
      if (de.scrollWidth > de.clientWidth + 2) out.push(`горизонтальная прокрутка ${de.scrollWidth} > ${de.clientWidth}`);
      return out;
    });
    if (r.length) bad += r.length;
    console.log(w + 'px: ' + (r.length ? r.join(' | ') : 'чисто'));
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
