"""Раздел «Соревнование»: общая шкала, карточки участников и решения ИИ.

Схема взята из макета владельца: главный элемент — не список чисел, а одна шкала, на которой
видно, где лежит правило относительно разброса случайной монетки. Числа для неё считаются здесь:
истина одна — журналы стенда.

Правило без исключений: если данных нет, в тексте стоит «—» и об этом сказано словами.
Ноль вместо непроведённого опыта — тот же обман, только аккуратнее.
"""
from __future__ import annotations

import html
import json
import os
import time
import urllib.request

import equity_svg

HERE = os.path.dirname(os.path.abspath(__file__))
BEES = os.path.normpath(os.path.join(HERE, "..", "bees"))
DEMO = os.path.normpath(os.path.join(HERE, "..", "bybit-demo"))
API = "https://api.bybit.com"

EXTRA_CSS = """/* «Соревнование»: шкала, карточки участников, решение ИИ — в палитре сайта */
.lead{font-size:18px;color:var(--soft);max-width:700px;margin:0}
.sub{color:var(--mut);margin:0 0 18px;max-width:680px;font-size:15px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0;padding:0;list-style:none}
.chips li{padding:6px 12px;border:1px solid var(--line);border-radius:999px;color:var(--soft);
  font-size:14px;background:#0e1729aa}
.chips .no{border-color:#7a5a1a;color:#e9c987}

.scale{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px 22px 16px}
.row{display:grid;grid-template-columns:120px 1fr 130px;align-items:center;gap:14px;padding:11px 0;
  border-bottom:1px solid #1a2740}
.row:last-of-type{border-bottom:0}
.row .who{font-weight:650}
.row .who small{display:block;color:var(--mut);font-weight:400;font-size:12.5px}
.row .val{text-align:right;font-weight:700;font-size:17px}
.row .val small{display:block;color:var(--mut);font-weight:400;font-size:12px}
.track{position:relative;height:30px}
.track::before{content:"";position:absolute;left:0;right:0;top:50%;height:2px;background:#1c2a44;
  transform:translateY(-50%)}
.dot{position:absolute;top:50%;left:var(--x);width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;
  background:var(--c);box-shadow:0 0 0 4px #0b122099;z-index:2}
.band{position:absolute;top:50%;left:var(--a);width:var(--w);height:14px;margin-top:-7px;border-radius:7px;
  background:#f59e0b33;border:1px solid #f59e0b88}
.med{position:absolute;top:50%;left:var(--x);width:3px;height:22px;margin:-11px 0 0 -1px;
  background:var(--warn);border-radius:2px;z-index:2}
.axis{display:grid;grid-template-columns:120px 1fr 130px;gap:14px;margin-top:4px}
.axis div{position:relative;height:18px;color:var(--mut);font-size:12px}
.axis span{position:absolute;transform:translateX(-50%);white-space:nowrap}
.read{margin:14px 0 0;padding-top:12px;border-top:1px solid #1a2740;color:var(--soft);font-size:15px}
.read b{color:#fff}

.cn-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(176px,1fr));gap:12px;margin:16px 0 0}
.cn-card{background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--c,var(--line));
  border-radius:12px;padding:14px 15px 15px;display:flex;flex-direction:column}
.cn-card .em{color:var(--c,var(--acc));height:58px}
.cn-card .em svg{width:56px;height:56px}
.cn-card .nm{font-weight:700;margin-top:6px;color:#fff}
.cn-card .rl{color:var(--mut);font-size:13px;line-height:1.45;margin-top:4px}
.cn-card .big{font-size:25px;font-weight:760;color:#fff;margin-top:12px;line-height:1.1}
.cn-card .nb{color:var(--mut);font-size:12.5px;margin-top:4px;line-height:1.4}
.cn-card .tg{margin-top:auto;padding-top:12px;font-size:12.5px;color:var(--mut)}
.cn-card .tg i{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--c);
  margin-right:7px}

.ai{display:grid;grid-template-columns:auto 1fr;gap:6px 22px;background:#0e1729;
  border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-top:14px}
.ai .pair{font-size:26px;font-weight:760}
.ai .side{display:inline-block;margin-left:10px;padding:2px 10px;border-radius:6px;background:#4ade8022;
  color:var(--ok);font-size:14px;font-weight:700;vertical-align:middle}
.ai .side.short{background:#f8717122;color:var(--bad)}
.ai .side.flat{background:#93a1b822;color:var(--mut)}
.ai .conf{grid-row:2;color:var(--mut);font-size:13px}
.meter{height:6px;width:150px;border-radius:3px;background:#1c2a44;margin-top:6px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--acc)}
.ai p{grid-column:2;grid-row:1/3;margin:0;color:var(--soft);font-size:15px;align-self:center}

.cn-does{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);
  border-radius:12px;padding:18px 22px;margin:26px 0 0}
.cn-does h2{margin:0 0 8px;font-size:18px}
.cn-does ul{margin:0;padding-left:20px}
.cn-does li{margin:7px 0;color:var(--soft);font-size:15px}
.tags{color:var(--mut);font-size:13px;margin:18px 0 0}
.note{color:var(--mut);font-size:13px;margin:8px 0 0}

/* Кривые эквити: SVG из журналов, без растровых картинок */
.eq{width:100%;height:auto;display:block}
.eq-legend{display:flex;flex-wrap:wrap;gap:16px;color:var(--mut);font-size:13px;margin:10px 0 0}
.eq-legend span{display:inline-flex;align-items:center;gap:7px}
.eq-legend i{width:14px;height:3px;border-radius:2px;display:inline-block}
.eq-wrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px 12px}
.eq-empty{color:var(--mut);font-size:13px;padding:14px 0}
.spark{width:100%;height:34px;display:block;margin-top:8px}

@media (max-width:640px){
 .row,.axis{grid-template-columns:1fr auto;gap:4px 10px}
 .row .track{grid-column:1/-1;grid-row:2}
 .row .val{grid-row:1;grid-column:2}
 .axis>div:first-child,.axis>div:last-child{display:none}
 .axis{grid-template-columns:1fr}
 .ai{grid-template-columns:1fr}
 .ai p{grid-column:1;grid-row:auto}
}
"""

EMBLEM = {
    "trend": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M16 40 48 24l32 16v34L48 90 16 74z"/>
      <path d="M16 40l32 16 32-16"/><path d="M48 56v34"/><path d="M48 40V20M40 28l8-8 8 8"/></svg>""",
    "random": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><circle cx="48" cy="48" r="28"/>
      <path d="M48 22v8M48 66v8"/>
      <path d="M40 40h12a6 6 0 0 1 0 12H40m0 0h14a6 6 0 0 1 0 12H40V34"/></svg>""",
    "hold": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><rect x="22" y="44" width="52" height="38" rx="7"/>
      <path d="M34 44V32a14 14 0 0 1 28 0v12"/>
      <circle cx="48" cy="60" r="4.5" fill="currentColor" stroke="none"/><path d="M48 64v8"/></svg>""",
    "ai": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M28 58h40v12a20 20 0 0 1-40 0z"/>
      <path d="M28 58a20 20 0 0 1 40 0"/><circle cx="48" cy="44" r="5"/>
      <path d="M20 34h8M68 34h8M48 30V18"/></svg>""",
    "mt5": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><rect x="14" y="20" width="68" height="46" rx="5"/>
      <path d="M22 54l12-13 10 8 12-18 12 11"/><path d="M22 74h52M34 82h28"/></svg>""",
}


def _e(x) -> str:
    return html.escape(str(x), quote=False)


def _pct(v, digits: int = 2) -> str:
    return "—" if v is None else f"{v:+.{digits}f} %".replace("-", "\u2212")


def _num(x, digits: int = 2) -> str:
    return "—" if x is None else f"{x:+.{digits}f}".replace("-", "\u2212")


def _json(name: str, default=None):
    try:
        with open(os.path.join(DEMO, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _lines(name: str) -> list[dict]:
    out = []
    try:
        with open(os.path.join(DEMO, name), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out


def _holding(symbol: str, start_ms: int, end_ms: int) -> float | None:
    url = (f"{API}/v5/market/kline?category=linear&symbol={symbol}&interval=60"
           f"&start={start_ms}&end={end_ms}&limit=1000")
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            rows = json.loads(r.read().decode("utf-8"))["result"]["list"]
    except Exception:                                   # noqa: BLE001
        return None
    if not rows:
        return None
    return round((float(rows[0][4]) / float(rows[-1][1]) - 1) * 100, 2)


def _card(key: str, color: str, name: str, rule: str, big: str, note: str, tag: str,
          spark: str = "") -> str:
    return (f'<div class="cn-card" style="--c:{color}"><div class="em">{EMBLEM[key]}</div>'
            f'<div class="nm">{_e(name)}</div><div class="rl">{_e(rule)}</div>'
            f'<div class="big">{big}</div>{spark}<div class="nb">{_e(note)}</div>'
            f'<div class="tg"><i></i>{_e(tag)}</div></div>')


def render_body() -> str:
    state = _json("state.json", {}) or {}
    book = state.get("forward_book") or []
    anchor = int(state.get("anchor_ms") or 0)
    now = int(time.time() * 1000)
    days = round((now - anchor) / 86400000, 2) if anchor else 0

    rule = round(sum(float(t.get("net_pct") or 0) for t in book), 2) if book else None
    btc = _holding("BTCUSDT", anchor, now) if anchor else None
    eth = _holding("ETHUSDT", anchor, now) if anchor else None
    hold = round((btc + eth) / 2, 2) if (btc is not None and eth is not None) else None

    rc = _json("random-control.json") or {}
    rc_med = rc.get("random_median_pct")
    rc_lo, rc_hi = rc.get("random_p05_pct"), rc.get("random_p95_pct")
    rc_beaten = rc.get("share_random_beats_rule_pct")

    ai = [r for r in _lines("ai-bee-journal.jsonl") if r.get("side")]
    ai_ok = [r for r in ai if r.get("allowed")]
    last_ai = ai[-1] if ai else None

    mt5 = _json("mt5-state.json", {}) or {}
    mt5_rows = _lines("mt5-journal.jsonl")
    mt5_trades = sum(1 for r in mt5_rows if str(r.get("kind", "")).startswith(("mt5_entry", "mt5_exit")))
    mt5_positions = len(mt5.get("positions") or [])
    mt5_runs = mt5.get("runs") or len(mt5_rows)

    # ── общая шкала: один домен для всех точек ───────────────────────────
    vals = [v for v in (rule, hold, rc_med) if isinstance(v, (int, float))]
    if rc_lo is not None and rc_hi is not None:
        vals += [float(rc_lo), float(rc_hi)]
    if vals:
        lo, hi = float(min(vals)), float(max(vals))
        pad = (hi - lo) * 0.12 or 1.0
        lo, hi = lo - pad, hi + pad

        def pos(v: float) -> float:
            return max(2.0, min(98.0, (v - lo) / (hi - lo) * 100))

        zero = pos(0.0)
        # Деления — по «круглому» шагу. Просто делить домен на три части нельзя:
        # получаются подписи вида −6.9 / −3.3 / +0.4, которые читаются как случайный шум.
        step = 1.0
        for mult in (0.1, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 25.0, 50.0):
            if (hi - lo) / mult <= 5:
                step = mult
                break
        tick_src = []
        v = (int(lo / step) - 1) * step
        while v <= hi + 1e-9:
            if lo - 1e-9 <= v:
                tick_src.append(round(v, 6))
            v += step
        ticks = "".join(f'<span style="left:{pos(t):.1f}%">{_num(t, 1)} %</span>' for t in tick_src)
    else:
        def pos(v: float) -> float:                     # noqa: ARG001
            return 50.0
        zero, ticks = 50.0, ""

    def track_dot(value, color, label) -> str:
        zero_line = (f'<span style="position:absolute;left:{zero:.1f}%;top:0;bottom:0;width:1px;'
                     f'background:#33445f"></span>')
        if value is None:
            return ('<div class="track" role="img" aria-label="нет данных">' + zero_line +
                    '<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);'
                    'color:var(--mut);font-size:12px">нет данных</span></div>')
        return (f'<div class="track" role="img" aria-label="{_e(label)}: {_e(_pct(value))}">' + zero_line +
                f'<span class="dot" style="--x:{pos(value):.1f}%;--c:{color}"></span></div>')

    if rc_lo is not None and rc_hi is not None:
        a, b = pos(float(rc_lo)), pos(float(rc_hi))
        med = pos(float(rc_med)) if isinstance(rc_med, (int, float)) else (a + b) / 2
        band_row = (f'<div class="row"><div class="who">«Случайный»<small>200 бросков</small></div>'
                    f'<div class="track" role="img" aria-label="Случайный: медиана {_e(_pct(rc_med))}, '
                    f'диапазон {_e(_pct(rc_lo))} — {_e(_pct(rc_hi))}">'
                    f'<span class="band" style="--a:{a:.1f}%;--w:{max(1.0, b - a):.1f}%"></span>'
                    f'<span class="med" style="--x:{med:.1f}%"></span></div>'
                    f'<div class="val">{_pct(rc_med)}<small>медиана</small></div></div>')
    else:
        band_row = ('<div class="row"><div class="who">«Случайный»<small>200 бросков</small></div>'
                    '<div class="track"><span style="position:absolute;left:50%;top:50%;'
                    'transform:translate(-50%,-50%);color:var(--mut);font-size:12px">не измерено</span>'
                    '</div><div class="val">—</div></div>')

    if rc_beaten is not None and rule is not None:
        inside = 5 <= float(rc_beaten) <= 95
        read = (f'Полоса — 5–95 % бросков: <b>{_pct(rc_lo)} … {_pct(rc_hi)}</b>. '
                f'Бросков лучше правила: <b>{float(rc_beaten):.0f} %</b>. ' +
                ("Метка правила лежит внутри полосы — на таком ряду умение от везения не отличить."
                 if inside else
                 "Правило лежит на краю полосы или вне её — но ряд короткий, и верить этому рано."))
        # Вывод — в первые две строки страницы, до всех цифр и таблиц.
        verdict_line = (
            f"Преимущества не показано: правило <b>{_pct(rule)}</b> лежит внутри разброса "
            f"случайной монетки <b>{_pct(rc_lo)} … {_pct(rc_hi)}</b>."
            if inside else
            f"Правило <b>{_pct(rule)}</b> вышло за пределы полосы случайной монетки "
            f"<b>{_pct(rc_lo)} … {_pct(rc_hi)}</b>, но сделок слишком мало, чтобы этому верить.")
    else:
        read = "Контроль ещё не посчитан, поэтому сравнивать не с чем."
        verdict_line = "Сравнивать пока не с чем: контроль не посчитан."

    enough = (f"{len(book)} сделок · мало данных для вывода о качестве" if len(book) < 30
              else f"{len(book)} сделок · всё ещё меньше нужного для вывода")

    cards = [
        _card("trend", "#4cc9f0", "«Тренд»",
              "EMA 9/21 по часу, стоп 1 ATR, тейк 1,5 ATR. Живые ордера на демо-счёте",
              _pct(rule), enough, "живые ордера", equity_svg.spark("rule")),
        _card("random", "#f59e0b", "«Случайный»",
              "Те же входы и выходы, сторона — 200 бросков монетки",
              _pct(rc_med) if rc else "не измерено",
              (f"медиана · 5–95 %: {_pct(rc_lo)} … {_pct(rc_hi)} · лучше правила: {float(rc_beaten):.0f} %"
               if rc and rc_beaten is not None else "контроль не посчитан"), "контроль",
              equity_svg.spark("coin")),
        _card("hold", "#c9a227", "«Владение»",
              "Купил в начале окна и держишь. Ничего не решает",
              _pct(hold), f"BTC {_pct(btc)} · ETH {_pct(eth)} · без комиссий входа и выхода", "контроль",
              equity_svg.spark("hold")),
        _card("ai", "#4cc9f0", "«ИИ»",
              "beam:cloud, при отказе локальная qwen3.8:27b. Модель предлагает, код проверяет",
              f"{len(ai)} реш.", f"разрешено кодом {len(ai_ok)} · книги сделок пока нет", "только решения"),
        _card("mt5", "#38bdf8", "«Вторая площадка»",
              "MT5: индексы, золото, EURUSD. До трёх позиций, предел 10 % по сумме",
              f"{mt5_trades} сдел.",
              f"{mt5_runs} прогонов · позиций сейчас {mt5_positions} · рынок TradFi закрыт по выходным",
              "живой счёт"),
    ]

    ai_block = ""
    if last_ai:
        side = (last_ai.get("side") or "").upper()
        cls = {"LONG": "", "SHORT": " short", "FLAT": " flat"}.get(side, " flat")
        conf = last_ai.get("confidence")
        conf_num = float(conf) if isinstance(conf, (int, float)) else 0.0
        ai_block = (f'<h2>Последнее решение ИИ</h2><div class="ai">'
                    f'<div><span class="pair">{_e(last_ai.get("symbol"))}</span>'
                    f'<span class="side{cls}">{_e(side or "—")}</span></div>'
                    f'<p>{_e((last_ai.get("reason") or "—"))}. Модель: {_e(last_ai.get("model") or "—")}.</p>'
                    f'<div class="conf">уверенность {_e(conf if conf is not None else "—")}'
                    f'<div class="meter"><i style="width:{max(0.0, min(100.0, conf_num)):.0f}%"></i></div>'
                    f'</div></div>')

    does = (f'<div class="cn-does"><h2>Чего это не доказывает</h2><ul>'
            f'<li>{len(book)} сделок и {days} дня — не выборка. Такой ряд не отличает умение от везения.</li>'
            '<li>Демо-исполнение оптимистичнее боевого: настоящей очереди заявок нет, проскальзывание меньше.</li>'
            '<li>«Владение» посчитано без комиссий входа и выхода: оно и не торгует.</li>'
            '<li>У ИИ нет книги сделок, поэтому сравнивать его можно только по решениям, не по результату.</li>'
            '<li>Рейтинга нет намеренно: пока сделок меньше тридцати, любой порядок участников — украшение.</li>'
            '</ul></div>')

    return f"""<h1>Бот против контролей</h1>
<p class="lead">{verdict_line}</p>
<p class="sub">Рядом с ботом всегда стоит контроль: случайная монетка с теми же входами и простое владение.
Без них любой результат выглядит мастерством. Победителя пока нет, и мы не делаем вид, что он есть.</p>
<ul class="chips"><li>окно {days} дн.</li><li>{len(book)} сделок</li>
<li class="no">рейтинга нет, пока сделок меньше 30</li></ul>

<h2>Путь во времени, а не только итог</h2>
<p class="sub">Накопленный результат по закрытым сделкам. Полоса — весь разброс 200 бросков монетки
на тех же входах и выходах, поэтому видно не только «кто где кончил», но и когда правило отрывалось,
а когда шло вместе с рынком.</p>
<div class="eq-wrap">{equity_svg.chart()}{equity_svg.legend()}</div>

<h2>Где правило относительно контролей</h2>
<p class="sub">Итог окна в процентах на одной шкале. Левее нуля потеря, правее прибыль.</p>
<div class="scale">
 <div class="row"><div class="who">«Тренд»<small>живые ордера</small></div>
  {track_dot(rule, "#4cc9f0", "Тренд")}<div class="val">{_pct(rule)}</div></div>
 <div class="row"><div class="who">«Владение»<small>без комиссий</small></div>
  {track_dot(hold, "#c9a227", "Владение")}<div class="val">{_pct(hold)}</div></div>
 {band_row}
 <div class="axis"><div></div><div>{ticks}</div><div></div></div>
 <p class="read">{read}</p>
</div>

<h2>Участники</h2>
<div class="cn-grid">{''.join(cards)}</div>

{ai_block}

{does}

<p class="tags">Окно {days} дн. Источники: state.json (форвардная книга), random-control.json,
ai-bee-journal.jsonl, mt5-journal.jsonl, публичные свечи Bybit. Сборка {time.strftime('%d.%m.%Y %H:%M')}.</p>
<p class="note">Страница собирается из журналов. Ни одно число здесь не набрано руками: если данные
не сошлись, на месте числа стоит «—».</p>
<p class="note">Контент образовательный, не является инвестиционной рекомендацией.
Торговля связана с риском потери капитала.</p>"""
