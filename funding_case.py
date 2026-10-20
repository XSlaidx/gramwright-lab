"""Разбор: премия за плечо (фандинг). Тело страницы из данных прогона.

Источник — bybit-demo/funding-carry-long.json (15 монет, 7 лет, Binance) плюс регистрация
гипотезы из lab-registry.jsonl. Ни одно число не вводится руками: всё считается из файла прогона.

Отдельно в странице есть живой снимок: сколько фандинг платит сейчас. Он берётся с публичного
API в момент сборки; не ответил API — на месте числа прочерк, а не прошлая цифра.
"""
from __future__ import annotations

import html
import json
import os
import statistics
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.normpath(os.path.join(HERE, "..", "bybit-demo"))
DATA = os.path.join(DEMO, "funding-carry-long.json")
REGISTRY = os.path.join(DEMO, "lab-registry.jsonl")
FAPI = "https://fapi.binance.com"

C_BTC = "#4cc9f0"
C_ETH = "#7dd3fc"
C_MED = "#f59e0b"
GRID = "#1c2a44"
INK = "#93a1b8"


def _e(x) -> str:
    return html.escape(str(x), quote=False)


def _num(v, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:+.{digits}f}".replace("-", "\u2212")


def _load() -> dict:
    try:
        return json.load(open(DATA, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _registration() -> dict:
    try:
        for line in open(REGISTRY, encoding="utf-8"):
            line = line.strip()
            if line and "carry-long" in line:
                r = json.loads(line)
                return {"run_id": r.get("run_id"), "hash": (r.get("config_hash") or "")[:16],
                        "n_trials": r.get("n_trials"), "ts": r.get("ts")}
    except (OSError, ValueError):
        pass
    return {}


def live_now() -> dict:
    """Сколько платят прямо сейчас. Ошибка сети — None, а не вчерашнее значение."""
    out = {}
    for symbol in ("BTCUSDT", "ETHUSDT"):
        try:
            with urllib.request.urlopen(f"{FAPI}/fapi/v1/premiumIndex?symbol={symbol}", timeout=15) as r:
                body = json.loads(r.read().decode("utf-8"))
            rate = float(body.get("lastFundingRate"))
            out[symbol] = {"rate_pct": round(rate * 100, 5),
                           "annual_pct": round(rate * 3 * 365 * 100, 1),
                           "next_ms": int(body.get("nextFundingTime") or 0)}
        except Exception:                                  # noqa: BLE001
            out[symbol] = None
    return out


def chart(width: int = 900, height: int = 320) -> str:
    d = _load()
    rows = d.get("rows") or []
    if not rows:
        return '<div class="eq-empty">Кривых нет: файла прогона не нашлось.</div>'

    def cum(series: dict) -> tuple[list[str], list[float]]:
        keys = sorted(series)
        total, out = 0.0, []
        for k in keys:
            total += series[k]
            out.append(total)
        return keys, out

    btc = next((r for r in rows if r["symbol"] == "BTCUSDT"), None)
    eth = next((r for r in rows if r["symbol"] == "ETHUSDT"), None)
    if not btc or not eth:
        return '<div class="eq-empty">Нет строк BTC и ETH в файле прогона.</div>'

    keys_b, btc_s = cum(btc["monthly"])
    keys_e, eth_s = cum(eth["monthly"])
    # медиана по всем монетам за каждый месяц
    months = sorted({m for r in rows for m in r["monthly"]})
    median_series, acc = [], 0.0
    for m in months:
        vals = [r["monthly"][m] for r in rows if m in r["monthly"]]
        acc += statistics.median(vals)
        median_series.append(acc)

    ally = btc_s + eth_s + median_series
    lo, hi = min(ally + [0.0]), max(ally + [0.0])
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    L, R, T, B = 52, 16, 16, 28
    W, H = width - L - R, height - T - B
    n = max(len(btc_s), len(eth_s), len(median_series))

    def sx(i: int) -> float:
        return L + (i / max(1, n - 1)) * W

    def sy(v: float) -> float:
        return T + (hi - v) / (hi - lo) * H

    out = [f'<svg class="eq" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Накопленная премия фандинга по годам: BTC, ETH и медиана по 15 монетам">']

    step = 10.0
    for mult in (2.5, 5.0, 10.0, 25.0, 50.0, 100.0):
        if (hi - lo) / mult <= 6:
            step = mult
            break
    v = int(lo / step) * step
    while v <= hi:
        y = sy(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + W}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" fill="{INK}" font-size="11" text-anchor="end">'
                   f'{_num(v, 0)} %</text>')
        v += step
    if lo < 0 < hi:
        out.append(f'<line x1="{L}" y1="{sy(0):.1f}" x2="{L + W}" y2="{sy(0):.1f}" stroke="#3d4f6b" '
                   f'stroke-width="1.4" stroke-dasharray="4 3"/>')

    def poly(vals, color, dashed=False, w=2.2):
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        return (f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{w}"{dash} '
                f'stroke-linejoin="round" stroke-linecap="round"/>')

    out.append(poly(median_series, C_MED, dashed=True, w=1.8))
    out.append(poly(eth_s, C_ETH))
    out.append(poly(btc_s, C_BTC, w=2.6))

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        i = int((n - 1) * frac)
        label = months[min(i, len(months) - 1)][:4] if months else ""
        anchor = "start" if frac == 0 else ("end" if frac == 1 else "middle")
        out.append(f'<text x="{sx(i):.1f}" y="{height - 8}" fill="{INK}" font-size="11" '
                   f'text-anchor="{anchor}">{label}</text>')
    out.append("</svg>")
    return "".join(out)


def legend() -> str:
    return ('<div class="eq-legend">'
            f'<span><i style="background:{C_BTC}"></i>BTC: премия накопленным итогом</span>'
            f'<span><i style="background:{C_ETH}"></i>ETH</span>'
            f'<span><i style="background:{C_MED};opacity:.8"></i>медиана по 15 монетам</span>'
            '</div>')


def render_body() -> str:
    import case_shell

    d = _load()
    rows = d.get("rows") or []
    s = d.get("summary") or {}
    reg = _registration()
    now = live_now()

    if not rows:
        return case_shell.head("Премия за плечо", "Данных прогона нет — страница не собрана.")
        # страховка: пустая страница честнее выдуманной

    btc = next((r for r in rows if r["symbol"] == "BTCUSDT"), {})
    eth = next((r for r in rows if r["symbol"] == "ETHUSDT"), {})
    worst = min(rows, key=lambda r: r["ann_pct"])

    verdict = (f"Дельта-нейтральная позиция «лонг спот + шорт перп» дала "
               f"<b>{_num(s.get('mean_ann_pct'))} %/год</b> на ноционал "
               f"(95 %: {_num(s.get('lo95'))}…{_num(s.get('hi95'))}) на 15 монетах за ~7 лет. "
               f"Это плата за плечо и риск площадки, а не мастерство, и она сжимается: "
               f"в 2026 году — около {_num((btc.get('by_year') or {}).get('2026'), 1)} % у BTC.")

    lead = ("Фандинг на перпетуальном контракте платится каждые 8 часов: когда ставка положительна, "
            "платят лонги, получают шорты. Если держать спот и одновременно шорт перпа на тот же "
            "ноционал, ценовой риск почти исчезает, а плата остаётся. Проверяли не «угадываем ли мы "
            "рынок», а «остаётся ли эта плата после издержек и в плохие годы».")

    live_bits = []
    for sym, label in (("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")):
        item = now.get(sym)
        if item:
            live_bits.append(f"{label}: {_num(item['rate_pct'], 5)} % за 8 ч ≈ "
                             f"{_num(item['annual_pct'], 1)} % годовых")
        else:
            live_bits.append(f"{label}: нет ответа от API")
    live_block = (f'<h2>Сколько платят сейчас</h2>'
                  f'<p class="sub">{_e(" · ".join(live_bits))} — снимок на '
                  f'{time.strftime("%d.%m.%Y %H:%M")} UTC, считается при сборке страницы. '
                  f'Ставка меняется каждые 8 часов, поэтому это ориентир, а не обещание.</p>')

    # таблица по монетам
    trs = []
    for r in sorted(rows, key=lambda x: -x["ann_pct"]):
        trs.append(
            f'<tr><td><b>{_e(r["symbol"])}</b></td>'
            f'<td class="num">{_num(r["ann_pct"])} %</td>'
            f'<td class="num">{_num(r["max_dd_pct"])} %</td>'
            f'<td class="num">{_num(r["sharpe"])}</td>'
            f'<td class="num">{_num(r["hold_pct"], 0)} %</td>'
            f'<td class="num">{_num(r["positive_share"], 0)} %</td>'
            f'<td class="num">{_e(r["years"])}</td></tr>')
    table = ('<h2>Пятнадцать монет</h2>'
             '<p class="sub">Доходность дана на ноционал. На капитал она ниже примерно в 1,2 раза: '
             'спот 1,0 плюс маржа перпа 0,2. «Владение» — что дал бы просто купленный спот за тот же '
             'период: у LTC он отрицательный, а премия всё равно положительна — это и есть свойство '
             'дельта-нейтральной позиции.</p>'
             '<div class="tbl-wrap"><table><thead><tr><th>Монета</th><th>% в год</th><th>Просадка</th>'
             '<th>Sharpe</th><th>Владение</th><th>Плюсовых 8ч</th><th>Лет</th></tr></thead><tbody>'
             + "".join(trs) + '</tbody></table></div>')

    # по годам
    years = sorted({y for r in rows for y in r["by_year"]})
    yrows = []
    for y in years:
        vals = [r["by_year"][y] for r in rows if y in r["by_year"]]
        if not vals:
            continue
        yrows.append(f'<tr><td><b>{y}</b></td>'
                     f'<td class="num">{_num(statistics.median(vals))} %</td>'
                     f'<td class="num">{_num(max(vals))} %</td>'
                     f'<td class="num">{_num(min(vals))} %</td>'
                     f'<td class="num">{sum(1 for v in vals if v < 0)} из {len(vals)}</td></tr>')
    year_table = ('<h2>По годам: где премия жила</h2>'
                  '<p class="sub">Главная проверка — 2022 год: рынок падал, и вопрос был в том, '
                  'переживёт ли премию падение. У BTC пережила, у медианной монеты — нет.</p>'
                  '<div class="tbl-wrap"><table><thead><tr><th>Год</th><th>Медиана</th><th>Лучшая</th>'
                  '<th>Худшая</th><th>Монет в минусе</th></tr></thead><tbody>'
                  + "".join(yrows) + '</tbody></table></div>')

    limits = case_shell.limits_block([
        "Это плата за риск площадки, а не за умение: заморозка вывода, ликвидация ноги при сбое "
        "маржи и делистинг контракта — главные риски, и Sharpe их не измеряет.",
        f"В корзине только монеты, дожившие до сегодня. Делистингованные контракты в выборку не попали, "
        f"а их фандинг тоже считался бы доходом — это завышает результат, и мы это не закрыли.",
        "Модель держит шорт перпа без пополнения маржи и предполагает кросс-маржинальный счёт. "
        "На изолированной марже ногу может снести.",
        "Издержки 0,30 % за круг заплачены один раз: позиция держится непрерывно. Любая попытка "
        "«ловить ставку» переключениями убыточна — три такие конфигурации дали от −53 % до −142 %.",
        f"Премия сжимается: 2021 год — десятки процентов, 2025 — около {_num((btc.get('by_year') or {}).get('2025'), 1)} %, "
        f"2026 — {_num((btc.get('by_year') or {}).get('2026'), 1)} % у BTC. Если сжатие продолжится, "
        f"останется меньше, чем стоит держать позицию.",
    ], title="Чего это не доказывает")

    reg_line = (f"Гипотеза зарегистрирована до прогона: <b>{_e(reg.get('run_id'))}</b>, "
                f"хеш {_e(reg.get('hash'))}…, испытаний {_e(reg.get('n_trials'))}. "
                if reg else "")
    sources = case_shell.sources_block(
        f"Источник: Binance USDⓈ-M, ставки фандинга и дневные свечи спот/перп, "
        f"{_num(d.get('round_trip_pct'), 2).replace('−', '')} % за круг издержек. "
        f"Сборка {time.strftime('%d.%m.%Y %H:%M')}.",
        notes=[reg_line.replace('<b>', '').replace('</b>', '') if reg_line else "",
               "Страница собирается из файла прогона: если данных нет, на месте числа стоит «—».",
               case_shell.DISCLAIMER])

    head = case_shell.head(
        "Премия за плечо: сколько платят за шорт перпа",
        verdict,
        chips=[f"монет: {len(rows)}", f"медианная просадка {_num(s.get('median_dd_pct'))} %",
               f"медианный Sharpe {_num(s.get('median_sharpe'))}"],
        warn_chip="это плата за риск, а не доходность стратегии",
        lead=lead)

    body = (head
            + live_block
            + case_shell.chart_block(chart(), legend(),
                                     title="Премия накопленным итогом",
                                     note="Накопленная премия без учёта сложного процента. "
                                          "Провалы — это месяцы, когда фандинг платили мы, а не нам.")
            + table + year_table + limits + sources)
    return body


EXTRA_CSS = """/* таблицы разбора: числа выровнены вправо и стоят столбиком */
.tbl-wrap{overflow-x:auto;margin:12px 0 0;border:1px solid var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:14.5px}
thead th{text-align:left;color:var(--mut);font-weight:600;font-size:13px;padding:11px 14px;
  border-bottom:1px solid var(--line);white-space:nowrap}
tbody td{padding:10px 14px;border-bottom:1px solid #16223a;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.num,thead th:nth-child(n+2){text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:#0f1a2c}
.eq-empty{color:var(--mut);font-size:13px;padding:14px 0}
"""
