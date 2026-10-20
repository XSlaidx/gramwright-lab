"""График эквити и мини-линии: SVG, собранный из журналов, а не нарисованный.

Почему SVG, а не картинка: он остаётся чётким на любом экране, весит килобайты и физически
не может разойтись с данными — координаты считаются из тех же файлов, что и числа на странице.
Растр пришлось бы перерисовывать и хранить отдельно, и он бы отставал.

Три источника на одном графике:
  правило  — накопленный net_pct по закрытым сделкам форвардной книги;
  монетка  — полоса 5–95 % из 200 путей контроля на ТЕХ ЖЕ входах и выходах;
  владение — покупка в начале окна, посчитанная по публичным часовым свечам.

Ось X — время закрытия сделки, а не «номер сделки»: иначе две линии на разной длине выглядели бы
сравнимыми, хотя покрывают разные интервалы.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.normpath(os.path.join(HERE, "..", "bybit-demo"))
API = "https://api.bybit.com"

RULE_C = "#4cc9f0"      # бот — голубой
COIN_C = "#f59e0b"      # контроль — янтарный
HOLD_C = "#f472b6"      # владение: розовый — тот же цвет, что у карточки участника
GRID_C = "#1c2a44"
ADVISOR_C = "#8a98a6"   # советник: бумажная книга, серый — как на его карточке
INV_C = "#f97316"       # «Наоборот»: те же входы, перевёрнутая сторона — цвет его карточки
LIVE_C = "#a78bfa"      # живой счёт: фиолетовый — как на карточке и плашке состояния
OKX_C = "#2dd4bf"       # книга OKX: бирюза, чтобы не путалась с фиолетовым живым счётом
# Порог для линии на графике — не «красиво», а осмысленно: две-три точки дают ломаную,
# которую легко принять за тренд. Поэтому книга попадает в график с трёх закрытых сделок,
# а до этого живёт в таблице участников и в карточке. Правило одно для всех книг.
MIN_LINE_TRADES = 3
ZERO_C = "#5c7291"
ZERO_TXT = "#9fb2cc"   # подпись нуля должна читаться, а не намекать
INK_C = "#93a1b8"


def _json(name: str, default=None):
    try:
        with open(os.path.join(DEMO, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _klines(symbol: str, start_ms: int, end_ms: int) -> list[list[float]]:
    url = (f"{API}/v5/market/kline?category=linear&symbol={symbol}&interval=60"
           f"&start={start_ms}&end={end_ms}&limit=1000")
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception:                                     # noqa: BLE001
        return []
    rows = [[int(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])] for x in body["result"]["list"]]
    return list(reversed(rows))


def _hold_path(anchor: int, stamps: list[int]) -> list[float] | None:
    """Средний путь «купить и держать» по BTC и ETH в моменты закрытия сделок."""
    if not anchor or not stamps:
        return None
    per: list[list[float]] = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        rows = _klines(symbol, anchor, max(stamps) + 3_600_000)
        if not rows:
            continue
        first = rows[0][1]
        if first <= 0:
            continue
        series = []
        for ms in stamps:
            px = next((r[4] for r in rows if r[0] >= ms), rows[-1][4])
            series.append((px / first - 1) * 100)
        per.append(series)
    if not per:
        return None
    n = min(len(s) for s in per)
    return [round(sum(s[i] for s in per) / len(per), 3) for i in range(n)]


def series() -> dict:
    """Данные для графика. Всё, чего нет, помечается None — а не нулём."""
    state = _json("state.json", {}) or {}
    book = sorted(state.get("forward_book") or [],
                  key=lambda t: int(t.get("exit_ms") or t.get("bar_ms") or 0))
    anchor = int(state.get("anchor_ms") or 0)
    rc = _json("random-control.json") or {}

    stamps = [int(t.get("exit_ms") or t.get("bar_ms") or 0) for t in book]
    acc, rule = [], []
    for t in book:
        acc.append(float(t.get("net_pct") or 0))
        rule.append(round(sum(acc), 3))

    holding = _hold_path(anchor, stamps) if stamps else None

    coin = None
    raw_steps = rc.get("path_steps_ms") or []
    if raw_steps and rc.get("path_p05") and rc.get("path_p95"):
        coin = {
            "steps": [int(x) for x in raw_steps],
            "p05": [float(x) for x in rc["path_p05"]],
            "p50": [float(x) for x in rc.get("path_p50") or rc["path_p05"]],
            "p95": [float(x) for x in rc["path_p95"]],
        }

    advisor = _advisor_path()
    live = _live_path()
    inverse = _inverse_path()
    okx = _okx_path()
    return {"anchor": anchor, "stamps": stamps, "rule": rule, "holding": holding, "coin": coin,
            "advisor": advisor, "live": live, "inverse": inverse,
            # okx_n и okx_pct есть всегда, okx (линия) — только когда выборки хватает
            "okx_n": (okx or {}).get("n", 0), "okx_pct": (okx or {}).get("pct"),
            "okx_usdt": (okx or {}).get("usdt"),
            "okx": okx if okx and okx["n"] >= MIN_LINE_TRADES else None}


def _okx_path():
    """Книга OKX в процентах от нотионала — та же единица, что у остальных участников.

    USDT сам по себе на графике бесполезен: он зависит от размера контракта. Размер контракта
    взят из публичного эндпоинта OKX (BTC-USDT-SWAP 0,01 BTC, ETH-USDT-SWAP 0,1 ETH).
    """
    ctval = {"BTCUSDT": 0.01, "ETHUSDT": 0.1}
    book_path = os.path.join(HERE, "..", "okx-advisor-book.jsonl")
    state_path = os.path.join(HERE, "..", "okx-advisor-state.json")
    if not os.path.exists(book_path):
        return None
    exits = []
    try:
        with open(book_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("kind") == "exit" and rec.get("measured"):
                    exits.append(rec)
    except OSError:
        return None
    if not exits:
        return None
    stamps_ms = []
    try:
        with open(state_path, encoding="utf-8") as fh:
            st = json.load(fh)
        stamps_ms = [int(c["exit_ms"]) for c in (st.get("closed") or []) if c.get("exit_ms")]
    except (OSError, ValueError, KeyError, TypeError):
        stamps_ms = []
    points, acc, usdt = [], 0.0, 0.0
    for i, rec in enumerate(exits):
        try:
            notional = float(rec["sz"]) * ctval[rec["symbol"]] * float(rec["entry_price"])
            pct = float(rec["net_usdt"]) / notional * 100.0
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue
        acc += pct
        usdt += float(rec.get("net_usdt") or 0)
        if i < len(stamps_ms):
            points.append((stamps_ms[i], round(acc, 3)))
    return {"points": points, "n": len(exits), "pct": round(acc, 3), "usdt": round(usdt, 4)}


def _inverse_path():
    """Контроль «Наоборот»: накопленный итог по времени выхода.

    Точки считаются в bees/inverse_control.py по публичным свечам, поэтому ряд существует даже
    там, где сделок не было: это расчёт, а не исполнение. На графике он пунктирный.
    """
    path = os.path.join(DEMO, "inverse-control-book.jsonl")
    if not os.path.exists(path):
        return None
    stamps, acc, vals = [], 0.0, []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                stamps.append(int(rec.get("exit_ms") or rec.get("entry_ms") or 0))
                acc += float(rec.get("net_pct") or 0)
                vals.append(round(acc, 3))
    except OSError:
        return None
    if not stamps:
        return None
    order = sorted(range(len(stamps)), key=lambda i: stamps[i])
    return {"stamps": [stamps[i] for i in order], "values": [vals[i] for i in order]}


def _advisor_path():
    """Бумажная книга советника: накопленный итог по времени выхода."""
    path = os.path.join(DEMO, "advisor-book.jsonl")
    if not os.path.exists(path):
        return None
    trades = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("kind") == "trade":
                    trades.append(rec)
    except OSError:
        return None
    if not trades:
        return None
    trades.sort(key=lambda r: int(r.get("exit_ms") or 0))
    stamps, acc, vals = [], 0.0, []
    for rec in trades:
        acc += float(rec.get("net_pct") or 0)
        stamps.append(int(rec["exit_ms"]))
        vals.append(round(acc, 3))
    return {"stamps": stamps, "values": vals}


def _live_path():
    """Живой счёт: закрытые сделки с биржи (demo-state.json → closed), накопленный итог по времени выхода.

    Отдельный ряд нужен потому, что линия «симуляция» и линия «живые ордера» — разные вещи, и до
    18.10.2026 в легенде стояла подпись «правило, живые сделки» над кривой форвардной книги.
    """
    state = _json("demo-state.json", {}) or {}
    trades = sorted((state.get("closed") or []), key=lambda t: int(t.get("exit_ms") or 0))
    if not trades:
        return None
    stamps, acc, vals = [], 0.0, []
    for t in trades:
        acc += float(t.get("net_pct") or 0)
        stamps.append(int(t["exit_ms"]))
        vals.append(round(acc, 3))
    return {"stamps": stamps, "values": vals}


def _collapse(pairs):
    """Один момент времени = одна ступенька.

    Советник закрывает по несколько сделок в один час (например, сработал тайм-стоп у сетки).
    Раньше на каждый выход рисовалась своя ступенька с тем же X — получался вертикальный «забор»
    из маркеров. Здесь выходы одного момента складываются, и остаётся финальный итог на это время.
    """
    out = []
    for ms, v in sorted(pairs, key=lambda p: p[0]):
        if out and out[-1][0] == ms:
            out[-1] = (ms, v)
        else:
            out.append((ms, v))
    return out


def _px_collapse(pts, sx, max_run: int = 2):
    """Склеивает точки, попавшие в один пиксель по X.

    Время сделок — минуты, а ширина графика ~900 px на несколько суток: два разных момента могут
    дать одинаковую координату. Без склейки это снова «забор» из вертикальных отрезков.
    """
    out: list[tuple[float, float]] = []
    for ms, v in pts:
        x = round(sx(ms), 1)
        run, i = 0, len(out) - 1
        while i >= 0 and out[i][0] == x:      # сколько точек уже стоит в этом пикселе
            run += 1
            i -= 1
        # Две точки на пиксель — это ступенька (было → стало). Третья и дальше — уже «забор»,
        # поэтому она не добавляется, а заменяет последнюю точку пикселя.
        if run >= max_run:
            out[-1] = (x, v)
        else:
            out.append((x, v))
    return out


def _step_points(anchor: int, pairs, now_ms: int):
    """Ступенчатый путь: (X, было) → (X, стало) … и полка до «сейчас»."""
    pts, prev_v, last_ms = [(anchor, 0.0)], 0.0, anchor
    for ms, v in _collapse(pairs):
        if ms <= anchor:                 # выход раньше начала окна — не рисуем назад
            prev_v = v
            continue
        pts.append((ms, prev_v))
        pts.append((ms, v))
        prev_v, last_ms = v, ms
    pts.append((max(last_ms, now_ms), prev_v))
    return pts, prev_v


def _fmt_day(ms: int) -> str:
    return time.strftime("%d.%m", time.gmtime(ms / 1000))


def chart(width: int = 900, height: int = 330) -> str:
    d = series()
    pts: list[tuple[int, float]] = []
    if d["rule"] and d["anchor"]:
        pts.append((d["anchor"], 0.0))
        pts += list(zip(d["stamps"], d["rule"]))
    if d["holding"]:
        pts += list(zip(d["stamps"], d["holding"]))
    if d["coin"]:
        pts += list(zip(d["coin"]["steps"], d["coin"]["p05"]))
        pts += list(zip(d["coin"]["steps"], d["coin"]["p95"]))
    if d.get("advisor"):
        pts.append((d["anchor"], 0.0))
        pts += list(zip(d["advisor"]["stamps"], d["advisor"]["values"]))
    if d.get("live"):
        pts.append((d["anchor"], 0.0))
        pts += list(zip(d["live"]["stamps"], d["live"]["values"]))
    if d.get("inverse"):
        pts.append((d["anchor"], 0.0))
        pts += list(zip(d["inverse"]["stamps"], d["inverse"]["values"]))
    if d.get("okx"):
        pts.append((d["anchor"], 0.0))
        pts += list(d["okx"]["points"])
    if not pts:
        return ('<div class="eq-empty">Кривых пока нет: в форвардной книге нет закрытых сделок.</div>')

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    now_ms = int(time.time() * 1000)
    x0, x1 = min(xs), max(max(xs), now_ms)      # ось доходит до «сейчас»: простой видно, а не прячем
    lo, hi = min(ys + [0.0]), max(ys + [0.0])
    pad_y = (hi - lo) * 0.14 or 0.6
    lo, hi = lo - pad_y, hi + pad_y
    if x1 == x0:
        x1 = x0 + 3_600_000

    L, R, T, B = 54, 18, 18, 30
    W, H = width - L - R, height - T - B

    def sx(ms: float) -> float:
        return L + (ms - x0) / (x1 - x0) * W

    def sy(v: float) -> float:
        return T + (hi - v) / (hi - lo) * H

    last_txt = _pct_txt(d["rule"][-1]) if d["rule"] else "нет сделок"
    # aria-label перечисляет ВСЕ серии, которые реально нарисованы, с их последними значениями:
    # незрячий читатель должен получить то же, что видит глаз, а не устаревшую подпись.
    _parts = ["путь правила"]
    if d.get("live"):
        _parts.append("живой счёт (исполнено биржей)")
    if d.get("advisor"):
        _parts.append("советник, бумажная книга")
    _parts.append("полоса случайной монетки 5–95 %")
    _parts.append("линия владения")
    if d.get("inverse"):
        _parts.append("пунктир «Наоборот» — те же входы советника с перевёрнутой стороной")
    if d.get("okx"):
        _parts.append(f"книга OKX, {d['okx_n']} закрытых сделок")
    _ends = [f"правило {last_txt}"]
    if d.get("live"):
        _ends.append(f"живой счёт {_pct_txt(d['live']['values'][-1])}")
    if d.get("advisor"):
        _ends.append(f"советник {_pct_txt(d['advisor']['values'][-1])}")
    if d.get("inverse"):
        _ends.append(f"наоборот {_pct_txt(d['inverse']['values'][-1])}")
    if d.get("okx"):
        _ends.append(f"OKX {_pct_txt(d['okx']['pct'])}")
    aria = "График: " + ", ".join(_parts) + ". Последние точки: " + ", ".join(_ends)
    out = [f'<svg class="eq" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{aria}" preserveAspectRatio="xMidYMid meet">']

    # сетка по Y и подписи процентов
    step = 1.0
    for mult in (0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 25.0, 50.0):
        if (hi - lo) / mult <= 5:
            step = mult
            break
    v = int(lo / step) * step
    while v <= hi:
        y = sy(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + W}" y2="{y:.1f}" stroke="{GRID_C}" stroke-width="1"/>')
        lab = f"{v:+.1f} %".replace("-", "\u2212")
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" fill="{INK_C}" font-size="11" text-anchor="end">{lab}</text>')
        v += step

    # нулевая линия — заметнее остальных
    if lo < 0 < hi:
        y = sy(0)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + W}" y2="{y:.1f}" stroke="{ZERO_C}" '
                   f'stroke-opacity="0.95" stroke-width="2" stroke-dasharray="6 4"/>')
        out.append(f'<text x="{L + W - 2:.1f}" y="{y - 5:.1f}" fill="{ZERO_C}" font-size="11" '
                   f'text-anchor="end">0 — граница прибыли и убытка</text>')
        out[-1] = out[-1].replace(f'fill="{ZERO_C}"', f'fill="{ZERO_TXT}"')

    # полоса монетки: сверху p95, снизу p05 обратным ходом
    if d["coin"]:
        st, p05, p95 = d["coin"]["steps"], d["coin"]["p05"], d["coin"]["p95"]
        # Полоса строится по входам правила: когда правило перестало торговать, массив кончался
        # и заливка обрывалась «тупиком». Продлеваем последние значения до правого края, как и линии.
        if st and max(st) < now_ms:
            st = list(st) + [now_ms]
            p05 = list(p05) + [p05[-1]]
            p95 = list(p95) + [p95[-1]]
            d["coin"]["p50"] = list(d["coin"]["p50"]) + [d["coin"]["p50"][-1]]
        top = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in zip(st, p95))
        bot = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in reversed(list(zip(st, p05))))
        out.append(f'<polygon points="{top} {bot}" fill="{COIN_C}" fill-opacity="0.13" '
                   f'stroke="{COIN_C}" stroke-opacity="0.35" stroke-width="1"/>')
        med = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in zip(st, d["coin"]["p50"]))
        out.append(f'<polyline points="{med}" fill="none" stroke="{COIN_C}" stroke-width="2" '
                   f'stroke-dasharray="7 4" stroke-linejoin="round"/>')

    # владение
    if d["holding"]:
        h = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in zip(d["stamps"], d["holding"]))
        out.append(f'<polyline points="{h}" fill="none" stroke="{HOLD_C}" stroke-width="2" '
                   f'stroke-opacity="0.85" stroke-linejoin="round"/>')

    # «Наоборот» — контроль: те же входы советника, сторона перевёрнута. Пунктир = расчёт по свечам,
    # биржа этих сделок не исполняла, поэтому линия визуально отличается от живых.
    if d.get("inverse"):
        pairs = list(zip(d["inverse"]["stamps"], d["inverse"]["values"]))
        pts_i, prev_v = _step_points(d["anchor"], pairs, now_ms)
        i_pts = " ".join(f"{x:.1f},{sy(v):.1f}" for x, v in _px_collapse(pts_i, sx))
        out.append(f'<polyline points="{i_pts}" fill="none" stroke="{INV_C}" stroke-width="2.2" '
                   f'stroke-opacity="0.95" stroke-dasharray="6 4" stroke-linejoin="miter" '
                   f'stroke-linecap="butt"/>')
        for ms, v in _collapse(pairs):
            if ms <= d["anchor"]:
                continue
            out.append(f'<circle cx="{sx(ms):.1f}" cy="{sy(v):.1f}" r="2.6" fill="{INV_C}">'
                       f'<title>{_fmt_day(int(ms))} · наоборот {v:+.2f} %</title></circle>')
        _last = _collapse(pairs)[-1][0]
        out.append(f'<circle cx="{sx(_last):.1f}" cy="{sy(prev_v):.1f}" r="4" '
                   f'fill="none" stroke="{INV_C}" stroke-width="2">'
                   f'<title>наоборот · итог {prev_v:+.2f} %</title></circle>')

    # советник (бумажная книга): один момент выхода = одна ступенька
    if d.get("advisor"):
        pairs = list(zip(d["advisor"]["stamps"], d["advisor"]["values"]))
        pts_a, prev_v = _step_points(d["anchor"], pairs, now_ms)
        a = " ".join(f"{x:.1f},{sy(v):.1f}" for x, v in _px_collapse(pts_a, sx))
        out.append(f'<polyline points="{a}" fill="none" stroke="{ADVISOR_C}" stroke-width="2.4" '
                   f'stroke-opacity="0.95" stroke-linejoin="miter"/>')
        for ms, v in _collapse(pairs):
            if ms <= d["anchor"]:
                continue
            n = sum(1 for m, _ in pairs if m == ms)
            more = f" ({n} сделки)" if n > 1 else ""
            out.append(f'<circle cx="{sx(ms):.1f}" cy="{sy(v):.1f}" r="3" fill="{ADVISOR_C}">'
                       f'<title>{_fmt_day(int(ms))} · советник {v:+.2f} %{more}</title></circle>')
        _last = _collapse(pairs)[-1][0]
        out.append(f'<circle cx="{sx(_last):.1f}" cy="{sy(prev_v):.1f}" r="4" fill="none" '
                   f'stroke="{ADVISOR_C}" stroke-width="2">'
                   f'<title>советник · итог {prev_v:+.2f} %</title></circle>')

    # живой счёт: ступенчатая линия, точки — исполнения биржи
    if d.get("live"):
        pairs = list(zip(d["live"]["stamps"], d["live"]["values"]))
        pts_l, prev_v = _step_points(d["anchor"], pairs, now_ms)
        line = " ".join(f"{x:.1f},{sy(v):.1f}" for x, v in _px_collapse(pts_l, sx))
        out.append(f'<polyline points="{line}" fill="none" stroke="{LIVE_C}" stroke-width="2.2" '
                   f'stroke-opacity="0.95" stroke-dasharray="2 0" stroke-linejoin="miter">'
                   f'<title>живой счёт: исполнено биржей</title></polyline>')
        for ms, v in _collapse(pairs):
            if ms <= d["anchor"]:
                continue
            out.append(f'<circle cx="{sx(ms):.1f}" cy="{sy(v):.1f}" r="3.2" fill="{LIVE_C}">'
                       f'<title>{_fmt_day(int(ms))} · живой счёт {v:+.2f} %</title></circle>')

    # книга OKX — та же единица (процент от нотионала), поэтому рисуется в общем масштабе
    if d.get("okx"):
        pairs = list(d["okx"]["points"])
        # _px_collapse отдаёт уже пиксельные X — второе применение sx() уводило линию
        # в отрицательные координаты (вертикальный «забор» из шести точек на одном X).
        line = " ".join(f"{x:.1f},{sy(v):.1f}" for x, v in _px_collapse(
            [(d["anchor"], 0.0)] + pairs, sx))
        out.append(f'<polyline points="{line}" fill="none" stroke="{OKX_C}" stroke-width="2" '
                   f'stroke-opacity="0.9" stroke-dasharray="5 3" stroke-linejoin="round">'
                   f'<title>книга OKX: {d["okx_n"]} закрытых сделок, итог '
                   f'{d["okx"]["pct"]:+.2f} %</title></polyline>')
        for ms, v in pairs:
            out.append(f'<circle cx="{sx(ms):.1f}" cy="{sy(v):.1f}" r="3" fill="{OKX_C}">'
                       f'<title>{_fmt_day(int(ms))} · OKX {v:+.2f} %</title></circle>')

    # правило
    if d["rule"]:
        r = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in zip([d["anchor"]] + d["stamps"], [0.0] + d["rule"]))
        out.append(f'<polyline points="{r}" fill="none" stroke="{RULE_C}" stroke-width="2.6" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        last_ms, last_v = d["stamps"][-1], d["rule"][-1]
        if now_ms > last_ms:
            out.append(f'<line x1="{sx(last_ms):.1f}" y1="{sy(last_v):.1f}" x2="{sx(now_ms):.1f}" '
                       f'y2="{sy(last_v):.1f}" stroke="{RULE_C}" stroke-width="2.6" stroke-opacity="0.45"/>')
        for ms_t, v_t in zip(d["stamps"], d["rule"]):
            tip = f"{_fmt_day(int(ms_t))} · {_pct_txt(v_t)} накопленным итогом"
            out.append(f'<circle cx="{sx(ms_t):.1f}" cy="{sy(v_t):.1f}" r="2.6" fill="{RULE_C}" '
                       f'fill-opacity="0.8"><title>{tip}</title></circle>')
        out.append(f'<circle cx="{sx(last_ms):.1f}" cy="{sy(last_v):.1f}" r="4.5" fill="{RULE_C}">'
                   f'<title>последняя сделка · {last_v:+.2f} %</title></circle>')

    # метка «сейчас»: читатель должен видеть, что график живой, а книга — нет
    if now_ms > x0:
        out.append(f'<line x1="{sx(now_ms):.1f}" y1="{T}" x2="{sx(now_ms):.1f}" y2="{T + H}" '
                   f'stroke="{INK_C}" stroke-opacity="0.35" stroke-width="1" stroke-dasharray="3 4"/>')
        out.append(f'<text x="{sx(now_ms) - 4:.1f}" y="{T + 12}" fill="{INK_C}" font-size="11" '
                   f'text-anchor="end">сейчас</text>')

    # сетка по дням: три подписи на длинном окне не дают понять, где что
    day = 86_400_000
    span_days = (x1 - x0) / day
    step_days = 1 if span_days <= 8 else (2 if span_days <= 18 else (7 if span_days <= 60 else 30))
    tick = (x0 // day) * day
    while tick <= x1:
        if tick >= x0:
            x = sx(tick)
            out.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T + H}" '
                       f'stroke="{INK_C}" stroke-opacity="0.10" stroke-width="1"/>')
            out.append(f'<text x="{x:.1f}" y="{height - 8}" fill="{INK_C}" font-size="11" '
                       f'text-anchor="middle">{_fmt_day(int(tick))}</text>')
        tick += step_days * day

    out.append("</svg>")
    return "".join(out)


def threshold_note() -> str:
    """Почему книга есть в таблице, но не на графике — считается из данных, а не пишется руками.

    Порог MIN_LINE_TRADES общий для всех книг; текст сам меняется, когда сделок становится больше,
    и сам исчезает, когда линия появилась.
    """
    d = series()
    n = d.get("okx_n") or 0
    if not n or d.get("okx"):
        return ""
    pct = d.get("okx_pct")
    usdt = d.get("okx_usdt")
    tail = ""
    if pct is not None:
        tail = f" (итог {_pct_txt(pct)}"
        if usdt is not None:
            tail += ", " + f"{usdt:+.2f}".replace(".", ",").replace("-", "\u2212") + " USDT"
        tail += ")"
    return (f"OKX пока не на графике: у него {n} закрытых "
            f"{'сделка' if n == 1 else ('сделки' if n < 5 else 'сделок')} при пороге "
            f"{MIN_LINE_TRADES} — две точки читаются как тренд, которого нет{tail}. "
            f"Книга живёт в таблице участников, а линия появится сама, когда сделок станет "
            f"{MIN_LINE_TRADES}. ")


def legend() -> str:
    d = series()
    advisor = (f'<span><i style="background:{ADVISOR_C}"></i>советник, бумажная книга</span>'
               if d.get("advisor") else "")
    live = (f'<span><i style="background:{LIVE_C}"></i>живой счёт: исполнено биржей</span>'
            if d.get("live") else "")
    inverse = (f'<span><i style="background:{INV_C}"></i>«Наоборот»: те же входы советника, '
               f'сторона перевёрнута (расчёт по свечам)</span>' if d.get("inverse") else "")
    return ('<div class="eq-legend">'
            f'<span><i style="background:{RULE_C}"></i>правило, симуляция «Тренд»</span>'
            + live + advisor +
            f'<span><i style="background:{COIN_C};opacity:.75"></i>монетка: 5–95 % из 200 путей</span>'
            f'<span><i style="background:{HOLD_C}"></i>владение: купить и держать</span>'
            + inverse +
            (f'<span><i style="background:{OKX_C}"></i>OKX · исполнение (демо), '
             f'{d["okx_n"]} сделок</span>' if d.get("okx") else "") +
            '</div>')


def spark(kind: str, w: int = 132, h: int = 34) -> str:
    """Мини-линия в карточке: путь участника без осей и подписей.

    Смысл не в цифрах — они рядом, — а в форме: растёт ступенями, падает, дёргается ли.
    """
    d = series()
    if kind == "rule" and d["rule"]:
        vals, color = [0.0] + d["rule"], RULE_C
    elif kind == "hold" and d["holding"]:
        vals, color = [0.0] + list(d["holding"]), HOLD_C
    elif kind == "advisor" and d.get("advisor"):
        vals, color = [0.0] + d["advisor"]["values"], ADVISOR_C
    elif kind == "coin" and d["coin"]:
        vals, color = [0.0] + list(d["coin"]["p50"]), COIN_C
    else:
        return ('<svg class="spark" viewBox="0 0 %d %d" aria-hidden="true">'
                '<text x="%d" y="%d" fill="%s" font-size="10" text-anchor="middle">нет пути</text></svg>'
                % (w, h, w // 2, h // 2 + 3, INK_C))

    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    if hi == lo:
        hi += 1
    n = len(vals)
    pts = []
    for i, val in enumerate(vals):
        x = 2 + i / max(1, n - 1) * (w - 4)
        y = 2 + (hi - val) / (hi - lo) * (h - 4)
        pts.append(f"{x:.1f},{y:.1f}")
    zero_y = 2 + (hi - 0.0) / (hi - lo) * (h - 4)
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" aria-hidden="true">'
            f'<line x1="2" y1="{zero_y:.1f}" x2="{w - 2}" y2="{zero_y:.1f}" stroke="{ZERO_C}" stroke-width="1"/>'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linejoin="round" stroke-linecap="round"/></svg>')


if __name__ == "__main__":
    svg = chart()
    print(f"  график: {len(svg)} байт · линий: "
          f"правило={'да' if '<polyline' in svg else 'нет'}")
    d = series()
    print(f"  точек: стопы={len(d['stamps'])} правило={d['rule'][-1] if d['rule'] else None} "
          f"владение={(d['holding'] or [None])[-1]} монетка={(d['coin'] or {}).get('p50', [None])[-1]}")

def _pct_txt(v: float, digits: int = 2) -> str:
    """Проценты для подсказок и aria: запятая и типографский минус, как во всём тексте."""
    return f"{v:+.{digits}f}".replace("-", "−").replace(".", ",") + " %"


def stale_note(opens: list[str] | None = None) -> str:
    """Почему график плоский: сколько часов нет закрытых сделок.

    19.10.2026 сноска говорила «новых входов с тех пор не было», хотя прямо над графиком висела
    плашка открытой позиции. Причина: сноска читала только `opens`, а состояние могло лежать в
    старом поле `open`. Теперь открытые позиции передаёт вызывающий код, а чтение состояния —
    запасной путь.
    """
    d = series()
    if not d["stamps"]:
        return "Закрытых сделок ещё нет — сравнивать пока нечего."
    last = max(d["stamps"])
    hours = (time.time() * 1000 - last) / 3_600_000
    when = time.strftime("%d.%m %H:%M", time.gmtime(last / 1000))
    if hours < 2:
        return f"Последняя сделка {when} UTC · контур активен."
    # «Сигналов не было» было неправдой: в это время открывалась живая позиция, и советник давал
    # сигнал. Формулировка теперь смотрит на состояние, а не на догадку (аудит 18.10.2026).
    if not opens:
        demo_path = os.path.join(os.path.dirname(HERE), "bybit-demo", "demo-state.json")
        try:
            demo = json.load(open(demo_path, encoding="utf-8"))
            raw = dict(demo.get("opens") or {})
            if not raw and demo.get("open"):          # старое поле на случай миграции
                raw = {"позиция": demo["open"]}
            opens = [f"{k} {'лонг' if float(v.get('side_sign') or 0) > 0 else 'шорт'}"
                     for k, v in raw.items()]
        except (OSError, ValueError):
            opens = []
    tail = ("Новых входов с тех пор не было." if not opens else
            "Открытая позиция " + ", ".join(opens) + " в график не входит — кривая строится только "
            "по зафиксированному PnL.")
    tail_close = ("незакрытая позиция в неё не входит." if opens
                  else "она строится по закрытым сделкам.")
    return (f"Последняя закрытая сделка {when} UTC · прошло {hours:.0f} ч. {tail} "
            f"Кривая поэтому и стоит на месте: {tail_close}")

