"""Превью для ссылок (og:image): своя картинка на каждую страницу, из шаблона.

Зачем: одна и та же audit/og.png на всех страницах означает, что в Telegram и соцсетях любая
ссылка выглядит одинаково, и читатель не понимает, что за ней — разбор сетки, стенд или аудит.
Своё превью с главным числом даёт на порядок больше переходов, чем общая картинка.

Как: HTML → headless Chrome → PNG 1200×630. Тот же приём, что для «Таможни»: текст в шаблоне,
числа подставляются из журналов, поэтому превью не может разойтись с данными.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):   # крон подменяет stdout на StringIO
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SITE = os.path.join(ROOT, "site")
DEMO = os.path.join(ROOT, "bybit-demo")
OUT = os.path.join(SITE, "og")

CHROME = next((p for p in (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
) if os.path.exists(p)), None)

BG, PANEL, LINE, INK, MUT, ACC, WARN = ("#0b1220", "#111a2e", "#22304a",
                                       "#e8eef8", "#93a1b8", "#4cc9f0", "#f59e0b")

TEMPLATE = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;background:%(bg)s;color:%(ink)s;
 font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 display:flex;flex-direction:column;justify-content:space-between;padding:64px 72px;
 background-image:radial-gradient(900px 420px at 12%% -10%%, #16233c 0%%, %(bg)s 62%%)}
.top{display:flex;align-items:center;gap:14px;color:%(mut)s;font-size:20px;letter-spacing:.4px}
.logo{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,%(acc)s,%(ok)s)}
h1{font-size:56px;line-height:1.12;font-weight:800;letter-spacing:-.5px;max-width:980px}
.big{font-size:104px;font-weight:800;letter-spacing:-2px;color:%(acc)s;line-height:1}
.sub{color:%(mut)s;font-size:24px;max-width:900px}
.bar{display:flex;gap:12px;align-items:center}
.tag{padding:8px 16px;border:1px solid %(line)s;border-radius:999px;color:%(mut)s;font-size:18px}
</style></head><body>
<div class="top"><div class="logo"></div>Gramwright Lab</div>
<div><h1>%(title)s</h1></div>
<div><div class="big">%(big)s</div><div class="sub">%(sub)s</div></div>
<div class="bar">%(tags)s</div>
</body></html>"""


def _json(name, default=None):
    try:
        with open(os.path.join(DEMO, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _pct(v):
    return "—" if v is None else f"{v:+.2f} %".replace("-", "\u2212")


def cards() -> list[dict]:
    """Что рисовать. Числа берутся из тех же файлов, что и на страницах."""
    state = _json("state.json", {}) or {}
    book = state.get("forward_book") or []
    rule = round(sum(float(t.get("net_pct") or 0) for t in book), 2) if book else None
    rc = _json("random-control.json") or {}
    hold = None
    try:
        h = json.load(open(os.path.join(DEMO, "hold-cache.json"), encoding="utf-8"))
        hold = h.get("avg_pct")
    except (OSError, ValueError):
        hold = None

    return [
        {"slug": "index", "title": "Telegram-боты и мини-приложения за 5–14 дней",
         "big": "5–14 дней", "sub": "Разбор процесса, цена и срок до старта. Отвечаю в течение часа.",
         "tags": ["бо́ты", "мини-приложения", "автоматизация"]},
        {"slug": "demo", "title": "Продукты в работе, а не макеты",
         "big": "150 320", "sub": "изменений статусов отслежено парсером очередей на границе",
         "tags": ["живые сборки", "скриншоты без ретуши"]},
        {"slug": "audit", "title": "Проверка заявленного результата до передачи капитала",
         "big": "$90", "sub": "экспресс за 72 часа: воспроизведение, PBO/DSR, MinBTL, издержки",
         "tags": ["218 испытаний", "7,8 года планка"]},
        {"slug": "lab-stand", "title": "Стенд: измеритель, а не заработок",
         "big": _pct(rule), "sub": "форвардная книга против случайной монетки и простого владения",
         "tags": [f"{len(book)} сделок", "гейт не пройден"]},
        {"slug": "lab-contest", "title": "Бот против контролей",
         "big": _pct(rule),
         "sub": (f"монетка: {_pct(rc.get('random_p05_pct'))} … {_pct(rc.get('random_p95_pct'))}"
                 if rc else "контроль не посчитан"),
         "tags": ["преимущество не показано" if rc else "нет данных", "рейтинга нет до 30 сделок"]},
        {"slug": "lab-funding", "title": "Премия за плечо: шорт перпа против спота",
         "big": "+9,23 %", "sub": "в год на ноционал: 15 монет, 7 лет, после издержек — плата за риск, не мастерство",
         "tags": ["15 из 15 положительных", "выжила в 2022", "сжимается"]},
        {"slug": "lab-seal", "title": "Проверьте сами: журнал и внешняя метка времени",
         "big": "FreeTSA", "sub": "пломба на манифест с хешами, проверка повторяется одной командой",
         "tags": ["RFC 3161", "только дозапись"]},
        {"slug": "archive", "title": "Журнал проверки торговых гипотез",
         "big": "10", "sub": "гипотез в «кладбище» — с причиной смерти и цифрами, ни одна не удалена",
         "tags": ["без обещаний доходности"]},
    ]


def render(card: dict) -> str | None:
    os.makedirs(OUT, exist_ok=True)
    html = TEMPLATE % {
        "bg": BG, "ink": INK, "mut": MUT, "line": LINE, "acc": ACC, "ok": "#4ade80",
        "title": card["title"], "big": card["big"], "sub": card["sub"],
        "tags": "".join(f'<span class="tag">{t}</span>' for t in card["tags"]),
    }
    tmp_html = os.path.join(OUT, f"_{card['slug']}.html")
    with open(tmp_html, "w", encoding="utf-8") as fh:
        fh.write(html)
    png = os.path.join(OUT, f"{card['slug']}.png")
    if not CHROME:
        print("  Chrome не найден — превью не собрать")
        return None
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=1200,630",
         f"--screenshot={png}", f"file:///{tmp_html.replace(os.sep, '/')}"],
        capture_output=True, timeout=90)
    os.remove(tmp_html)
    return png if os.path.exists(png) else None


def main() -> int:
    ok = 0
    for card in cards():
        png = render(card)
        if png:
            ok += 1
            print(f"  {card['slug']:12s} {os.path.getsize(png) // 1024:4d} КБ  {card['big']}")
        else:
            print(f"  {card['slug']:12s} НЕ СОБРАНО")
    print(f"  готово: {ok} из {len(cards())} · каталог {OUT}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
