// Проверка «таблица не обрезана своей обёрткой» и «окно прокрутки не прячет строки».
// Причина проверки: .table-wrap имел max-height:420px — таблица уходила за срез, полоса прокрутки
// поверх контента не видна, блок читался как пустой, а самые свежие строки исчезали.
//
// Теперь у «Живой книги против симуляции» окно прокрутки СОЗНАТЕЛЬНО (380 px, липкая шапка).
// Такое окно допустимо только при трёх условиях, и все три здесь проверяются:
//   1) подпись «Всего N строк» совпадает с числом строк в таблице;
//   2) последняя строка достижима прокруткой до конца;
//   3) шапка прилипает к верху окна, а не уезжает вместе со строками.
// Запуск: node scripts/clip_check.js <url|file>   · код выхода 1, если что-то не так.
const puppeteer = require('C:/Users/xslai/node_modules/puppeteer-core');

const target = process.argv[2] || 'https://gramwright.pages.dev/lab/contest/';

(async () => {
  const b = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new', args: ['--no-sandbox'],
  });
  const p = await b.newPage();
  let bad = 0;
  for (const w of [390, 700, 1100]) {
    await p.setViewport({ width: w, height: 900 });
    await p.goto(target, { waitUntil: 'networkidle2' });
    // ВАЖНО: панели вкладок скрыты через display:none, и таблица в скрытой панели меряется
    // как 0 px — проверка «обрезки нет» проходит на пустоте, ничего не измерив. Поэтому сначала
    // снимаем режим вкладок и показываем все панели, и только потом меряем.
    await p.evaluate(() => {
      document.body.classList.remove('tabs-ready');
      document.querySelectorAll('.tpane').forEach((el) => {
        el.dataset.active = '1';
        el.style.display = 'block';
      });
      document.querySelectorAll('details').forEach((d) => { d.open = true; });
    });
    await new Promise((r) => setTimeout(r, 250));
    const measured = await p.evaluate(() => [...document.querySelectorAll('.table-wrap')]
      .map((w) => Math.round(w.getBoundingClientRect().height)));
    if (measured.every((h) => h === 0)) {
      console.log(`${w}px: ОШИБКА ПРОВЕРКИ — все обёртки 0 px, мерить нечего (вкладки/спойлеры)`);
      bad += 1;
    }

    const res = await p.evaluate(() => {
      const out = [];
      document.querySelectorAll('.table-wrap').forEach((wrap, i) => {
        const tbl = wrap.querySelector('table');
        if (!tbl) return;
        const wh = wrap.getBoundingClientRect().height;
        const th = tbl.getBoundingClientRect().height;
        // .table-wrap-recon — окно прокрутки по замыслу; его проверяют отдельно (ниже)
        const recon = wrap.classList.contains('table-wrap-recon');
        out.push({ i, rows: tbl.querySelectorAll('tbody tr').length, recon,
                   wrap: Math.round(wh), table: Math.round(th), clipped: th - wh > 4 && !recon });
      });
      return out;
    });
    const win = await p.evaluate(() => {
      const out = [];
      document.querySelectorAll('.table-wrap-recon').forEach((wrap) => {
        const tbl = wrap.querySelector('table');
        const cap = (wrap.nextElementSibling && wrap.nextElementSibling.classList.contains('recon-cap'))
          ? wrap.nextElementSibling.textContent : '';
        const m = /Всего\s+(\d+)/.exec(cap || '');
        const want = m ? parseInt(m[1], 10) : null;
        const rows = tbl ? tbl.querySelectorAll('tbody tr').length : 0;
        const scrolled = wrap.scrollHeight > wrap.clientHeight;
        wrap.scrollTop = wrap.scrollHeight;
        const last = tbl && tbl.querySelector('tbody tr:last-child');
        const head = tbl && tbl.querySelector('thead th');
        const wb = wrap.getBoundingClientRect();
        const lb = last ? last.getBoundingClientRect() : null;
        const hb = head ? head.getBoundingClientRect() : null;
        out.push({
          rows, want, scrolled,
          lastReachable: !!lb && lb.bottom <= wb.bottom + 3 && lb.top >= wb.top - 2,
          stickyHead: !!hb && Math.abs(hb.top - wb.top) <= 3,
        });
        wrap.scrollTop = 0;
      });
      return out;
    });

    const clipped = res.filter((x) => x.clipped);
    const total = res.reduce((s, x) => s + x.rows, 0);
    let line = `${w}px: таблиц ${res.length} · строк всего ${total} · `
      + (clipped.length
        ? `ОБРЕЗАНО ${clipped.length}: ` + clipped.map((c) => `#${c.i} ${c.table}px в ${c.wrap}px`).join(', ')
        : 'обрезки нет');
    for (const o of win) {
      const errs = [];
      if (o.want === null) errs.push('нет подписи «Всего N»');
      else if (o.want !== o.rows) errs.push(`подпись говорит ${o.want}, строк ${o.rows}`);
      if (!o.lastReachable) errs.push('последняя строка не достижима прокруткой');
      if (!o.stickyHead) errs.push('шапка не прилипает');
      line += ` · окно: строк ${o.rows}, прокрутка ${o.scrolled ? 'есть' : 'не нужна'}, `
        + (errs.length ? 'ОШИБКИ: ' + errs.join('; ') : 'подпись/доступность/шапка ok');
      bad += errs.length;
    }
    console.log(line);
    bad += clipped.length;
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
