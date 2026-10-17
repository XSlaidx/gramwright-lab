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
HOLD_C = "#c9a227"      # владение — тоже контроль, поэтому янтарная гамма, но темнее монетки
GRID_C = "#1c2a44"
ZERO_C = "#3d4f6b"
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

    return {"anchor": anchor, "stamps": stamps, "rule": rule, "holding": holding, "coin": coin}


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
    if not pts:
        return ('<div class="eq-empty">Кривых пока нет: в форвардной книге нет закрытых сделок.</div>')

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = min(xs), max(xs)
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

    out = [f'<svg class="eq" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Путь правила, полоса случайной монетки и линия владения" '
           f'preserveAspectRatio="xMidYMid meet">']

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
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + W}" y2="{y:.1f}" stroke="{ZERO_C}" stroke-width="1.5" '
                   f'stroke-dasharray="4 3"/>')

    # полоса монетки: сверху p95, снизу p05 обратным ходом
    if d["coin"]:
        st, p05, p95 = d["coin"]["steps"], d["coin"]["p05"], d["coin"]["p95"]
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

    # правило
    if d["rule"]:
        r = " ".join(f"{sx(ms):.1f},{sy(v):.1f}" for ms, v in zip([d["anchor"]] + d["stamps"], [0.0] + d["rule"]))
        out.append(f'<polyline points="{r}" fill="none" stroke="{RULE_C}" stroke-width="2.6" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        last_ms, last_v = d["stamps"][-1], d["rule"][-1]
        out.append(f'<circle cx="{sx(last_ms):.1f}" cy="{sy(last_v):.1f}" r="4" fill="{RULE_C}"/>')

    # подписи дат
    for frac in (0.0, 0.5, 1.0):
        ms = x0 + (x1 - x0) * frac
        anchor = "start" if frac == 0 else ("end" if frac == 1 else "middle")
        out.append(f'<text x="{sx(ms):.1f}" y="{height - 8}" fill="{INK_C}" font-size="11" '
                   f'text-anchor="{anchor}">{_fmt_day(int(ms))}</text>')

    out.append("</svg>")
    return "".join(out)


def legend() -> str:
    return ('<div class="eq-legend">'
            f'<span><i style="background:{RULE_C}"></i>правило, живые сделки</span>'
            f'<span><i style="background:{COIN_C};opacity:.75"></i>монетка: 5–95 % из 200 путей</span>'
            f'<span><i style="background:{HOLD_C}"></i>владение: купить и держать</span>'
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
