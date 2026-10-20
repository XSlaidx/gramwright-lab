"""Диагностика, которую можно честно считать уже сейчас.

Два блока, которых не хватало странице:

1. Подводная кривая (underwater) — глубина просадки от исторического максимума.
   Считается из того же ряда, что и путь эквити, без обращения к бирже.
2. Калибровка уверенности — по историческому прогону модели (у каждой сделки есть p и нетто).
   Отвечает на вопрос «0,62 — это много или это float?»: сравниваем заявленную уверенность
   с реальной долей прибыльных сделок.

Правила: число наблюдений всегда рядом с числом; что не посчитано — говорим прямо.
"""

from __future__ import annotations

import json

LONG_C = "#a78bfa"
SHORT_C = "#f59e0b"


def underwater(nets: list[float]) -> dict:
    """Ряд просадок от исторического максимума, в процентах.

    nets — доходности сделок в процентах; капитал считаем аддитивно (как на странице),
    поэтому «максимум» — накопленная сумма. Возвращает точки, максимум просадки и её место.
    """
    eq = 0.0
    peak = 0.0
    points: list[float] = []
    worst = 0.0
    worst_at = -1
    for i, n in enumerate(nets):
        eq += float(n or 0.0)
        peak = max(peak, eq)
        dd = eq - peak
        points.append(dd)
        if dd < worst:
            worst, worst_at = dd, i
    return {"points": points, "worst": worst, "worst_at": worst_at, "n": len(nets)}


def underwater_svg(points: list[float], color: str = "#f87171",
                   width: int = 720, height: int = 64) -> str:
    """Полоса подводной кривой: 0 сверху, просадка вниз. Без осей — их читает подпись."""
    if not points:
        return ""
    lo = min(points + [0.0])
    span = max(1e-9, -lo)
    pad = 4
    w = width - 2 * pad
    h = height - 2 * pad
    n = len(points)
    def x(i: int) -> float:
        return pad + (w * i / max(1, n - 1))
    def y(v: float) -> float:
        # Просадка отрицательна, а «вниз» на экране — это рост y: знак переворачиваем,
        # иначе линия уходит за верхнюю границу и блок выглядит пустым.
        return pad - (h * (v / span))
    path = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, v in enumerate(points))
    area = path + f" L{x(n - 1):.1f},{pad} L{x(0):.1f},{pad} Z"
    # preserveAspectRatio="none" растягивает картинку по осям — вместе с ней растягивалась и
    # толщина линии: на широком блоке она становилась толще, на узком тоньше. vector-effect
    # держит 2px независимо от масштаба. aria-label обязателен: role="img" без имени читалка
    # объявляет просто «image».
    label = (f"Подводная кривая: глубина от исторического максимума, "
             f"худшая точка {abs(lo):.2f} п.п.")
    return (f'<svg class="uw" viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" '
            f'aria-label="{label}">'
            f'<path d="{area}" fill="{color}" opacity=".16"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" '
            f'vector-effect="non-scaling-stroke"/></svg>')


def calibration(model_path: str, run_prefix: str = "мейкер: вся история") -> dict:
    """Калибровка уверенности по историческому прогону модели.

    Уверенность = max(p, 1 − p): модель называет вероятность роста, а сделка может быть в шорт.
    Поэтому «0,35» для шорта — такая же уверенность, как «0,65» для лонга.
    """
    data = json.load(open(model_path, encoding="utf-8"))
    runs = data.get("symbols") or {}
    name = next((k for k in runs if k.startswith(run_prefix)), None)
    if name is None:
        return {"n": 0, "buckets": [], "run": None}
    trades: list[dict] = []
    for block in runs[name].values():
        trades += block.get("trades") or []
    buckets: dict[float, dict] = {}
    for t in trades:
        p = t.get("p")
        if p is None:
            continue
        conf = max(float(p), 1.0 - float(p))
        lo = round(int(conf * 20) / 20, 2)
        b = buckets.setdefault(lo, {"lo": lo, "n": 0, "wins": 0, "net": 0.0,
                                    "long_n": 0, "long_wins": 0, "long_net": 0.0,
                                    "short_n": 0, "short_wins": 0, "short_net": 0.0})
        net = float(t.get("net") or 0.0)
        b["n"] += 1
        b["wins"] += 1 if net > 0 else 0
        b["net"] += net
        if float(p) >= 0.5:
            b["long_n"] += 1
            b["long_wins"] += 1 if net > 0 else 0
            b["long_net"] += net
        else:
            b["short_n"] += 1
            b["short_wins"] += 1 if net > 0 else 0
            b["short_net"] += net
    rows = [buckets[k] for k in sorted(buckets)]
    sides = {}
    for side, label in ((1, "long"), (-1, "short")):
        g = [t for t in trades if int(t.get("side") or 0) == side]
        if not g:
            continue
        n = len(g)
        gross = sum(float(t.get("gross") or 0.0) for t in g) / n
        net = sum(float(t.get("net") or 0.0) for t in g) / n
        sides[label] = {"n": n, "gross": gross, "net": net, "cost": gross - net,
                        "wins_net": 100.0 * sum(1 for t in g if float(t.get("net") or 0) > 0) / n,
                        "wins_gross": 100.0 * sum(1 for t in g if float(t.get("gross") or 0) > 0) / n}
    def _agg(g: list[dict]) -> dict:
        n = len(g)
        if not n:
            return {"n": 0}
        lo = [t for t in g if float(t.get("p") or 0) >= 0.5]
        sh = [t for t in g if float(t.get("p") or 0) < 0.5]
        return {"n": n,
                "wins": 100.0 * sum(1 for t in g if float(t.get("net") or 0) > 0) / n,
                "net": sum(float(t.get("net") or 0) for t in g) / n,
                "long_n": len(lo), "short_n": len(sh),
                "long_wins": (100.0 * sum(1 for t in lo if float(t.get("net") or 0) > 0) / len(lo)) if lo else 0.0,
                "short_wins": (100.0 * sum(1 for t in sh if float(t.get("net") or 0) > 0) / len(sh)) if sh else 0.0}

    hi = [t for t in trades if max(float(t.get("p") or 0), 1.0 - float(t.get("p") or 0)) >= 0.75]
    return {"n": len(trades), "buckets": rows, "run": name, "sides": sides,
            "high": _agg(hi), "total": _agg(trades)}


if __name__ == "__main__":
    import sys
    print("подводная кривая:", underwater([-1.0, -0.5, 0.8, -0.3])["worst"])
    cal = calibration(sys.argv[1] if len(sys.argv) > 1 else "../bybit-demo/ai-learner-v5.json")
    print("калибровка, сделок:", cal["n"], "· прогон:", cal["run"])
    for b in cal["buckets"]:
        if b["n"] >= 20:
            print(f"  {b['lo']:.2f}–{b['lo'] + 0.05:.2f}: n={b['n']:4d} "
                  f"· прибыльных {100 * b['wins'] / b['n']:5.1f} % "
                  f"· нетто {b['net'] / b['n']:+.3f} % "
                  f"| лонги {b['long_n']} ({100 * b['long_wins'] / max(1, b['long_n']):.0f} %) "
                  f"шорты {b['short_n']} ({100 * b['short_wins'] / max(1, b['short_n']):.0f} %)")


def _to_ms(ts_local: str) -> int:
    """Отметка в журнале — местное время (UTC+3). Возвращает эпоху в мс."""
    import datetime as _dt
    d = _dt.datetime.strptime(ts_local, "%Y-%m-%d %H:%M:%S")
    return int(d.replace(tzinfo=_dt.timezone(_dt.timedelta(hours=3))).timestamp() * 1000)


def markout(fills: list[dict], cache_path: str | None = None,
            horizons=(1, 5, 15), timeout: int = 8) -> dict:
    """Markout мейкерских входов: куда пошла цена после налива, в б.п.

    Отрицательный markout — нас «снайперили»: налили и сразу пошли против. Это главная метрика
    качества мейкерского бота. Свечи берём с публичного эндпоинта той же биржи, ключи не нужны.
    Кэш: если сеть недоступна, остаётся прошлый результат, а не пустота.
    """
    import json as _json
    import urllib.request

    cache = {}
    if cache_path:
        try:
            cache = _json.load(open(cache_path, encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}

    import time as _time
    now_ms = int(_time.time() * 1000)
    out = []
    for f in fills:
        key = f"{f['symbol']}|{f['ts']}"
        cached = cache.get(key)
        if cached:
            # Запись с недомеренными горизонтами нельзя держать вечно: заявка налилась минуту назад,
            # «+15 мин» появится позже. Пересчитываем, когда время догнало, и только потом кэшируем.
            pend = cached.get("pending") or []
            hit = cached.get("hit_ms")
            ripe = hit and now_ms >= int(hit) + max(horizons) * 60_000 + 60_000
            if not pend or not ripe:
                out.append(cached)
                continue
        try:
            anchor = _to_ms(f.get("placed") or f["ts"])
            t0 = anchor - 3 * 60_000
            t1 = anchor + 40 * 60_000
            url = (f"https://demo-fapi.binance.com/fapi/v1/klines?symbol={f['symbol']}"
                   f"&interval=1m&startTime={t0}&endTime={t1}&limit=120")
            candles = _json.load(urllib.request.urlopen(url, timeout=timeout))
        except Exception as exc:                      # сеть/биржа — не превращаем в ноль
            out.append({"symbol": f["symbol"], "ts": f["ts"], "error": str(exc)[:80]})
            continue
        px = float(f["price"])
        sign = 1.0 if f["side"] == "LONG" else -1.0
        # Коснуться лимитки она могла только ПОСЛЕ постановки: свечи до неё не считаем,
        # иначе «ожидание» получается отрицательным и markout считается от чужого момента.
        hit = None
        for c in candles:
            if int(c[0]) < anchor:
                continue
            low, high = float(c[3]), float(c[2])
            if (sign > 0 and low <= px) or (sign < 0 and high >= px):
                hit = c
                break
        if hit is None:
            out.append({"symbol": f["symbol"], "ts": f["ts"], "error": "цена не касалась лимитки"})
            continue
        i = candles.index(hit)
        rec = {"symbol": f["symbol"], "side": f["side"], "price": px, "ts": f["ts"],
               "hit_ms": int(hit[0]), "pending": [],
               "wait_min": round((int(hit[0]) - _to_ms(f.get("placed") or f["ts"])) / 60000, 1),
               "markout": {}}
        for h in horizons:
            if i + h < len(candles):
                after = float(candles[i + h][4])
                rec["markout"][str(h)] = round(sign * (after - px) / px * 1e4, 1)
            else:
                # Свечей на этот горизонт ещё нет: это «не измерено», а не ноль и не ошибка.
                rec["pending"].append(str(h))
        out.append(rec)
        if cache_path:
            cache[key] = rec

    if cache_path:
        try:
            _json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
    return {"fills": out}
