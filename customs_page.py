"""Страница «Таможня» для сайта gramwright-lab.

Собирается из тех же файлов, что и локальный терминал: отчёт проверки, декларации курьеров
и журнал пломб. Ни одна цифра здесь не набрана руками — иначе через месяц на сайте висели бы
красивые числа, которых уже нет в данных.

Возвращает только тело страницы: рамку, шапку и подвал даёт build.py, чтобы стиль оставался один.
"""
from __future__ import annotations

import html
import json
import os

BEES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bees")
DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bybit-demo")


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _read_seal() -> dict | None:
    path = os.path.join(DEMO, "seals.jsonl")
    last = None
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
                if rec.get("kind") != "note" and rec.get("ok") and rec.get("verified"):
                    last = rec
    except OSError:
        return None
    return last


def _e(text) -> str:
    return html.escape(str(text), quote=False)


def _money(value: float) -> str:
    return f"{value:+.4f}".replace("-", "\u2212")


BADGE = {"ok": ("c-ok", "допущено"), "bad": ("c-bad", "не прошло"), "caveat": ("c-warn", "с оговоркой")}


def _checks(items: list[str], mark: str) -> str:
    if not items:
        return ""
    return '<ul class="c-chk">' + "".join(f'<li class="{mark}">{_e(x)}</li>' for x in items) + "</ul>"


def _report_lines(report: dict) -> str:
    trades = report.get("trades", [])
    rows = "".join(
        f'<li class="y">{_e(t["symbol"])}: нетто {_money(t["net"])} USDT · '
        f'комиссии {t["fees"]:.4f} · {_e(t["verdict"])}'
        + (" · с поправкой" if t.get("corrected") else "") + "</li>"
        for t in trades
    )
    total = report.get("summary", {}).get("net_sum", 0.0)
    verified = report.get("summary", {}).get("verified", 0)
    return (
        '<p><strong>Проверено по публичным свечам, без ключей:</strong> '
        f'{verified} из {len(trades)} сделок. Сумма нетто {_money(total)} USDT.</p>'
        f'<ul class="c-chk">{rows}</ul>'
        f'<p class="tags">журнал sha256 {_e(report.get("journal_sha256", "")[:16])}… · '
        f'проверяльщик {_e(report.get("verifier", ""))}</p>'
    )


EXTRA_CSS = """/* «Таможня»: только то, чего нет в основном стиле — штампы и списки проверок */
.c-ok{color:#3ecf8e;font-weight:600}
.c-bad{color:#ef6b6b;font-weight:600}
.c-warn{color:#e0b341;font-weight:600}
.c-chk{list-style:none;padding-left:0;margin:10px 0}
.c-chk li{padding-left:18px;position:relative;margin:5px 0;font-size:15px}
.c-chk li.y::before{content:"\\2713";position:absolute;left:0;color:#3ecf8e}
.c-chk li.n::before{content:"\\2717";position:absolute;left:0;color:#ef6b6b}
.c-note{color:var(--muted);font-size:14px;border-left:2px solid var(--line);padding-left:10px;margin:16px 0}
.c-conf{border:1px solid #ef6b6b55;border-radius:8px;padding:14px 16px;margin:22px 0}
.c-conf h3{margin:0 0 8px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#ef6b6b}
"""


def render_body() -> str:
    data = _read_json(os.path.join(BEES, "couriers.json")) or {}
    report = _read_json(os.path.join(DEMO, "verify-report.json"))
    seal = _read_seal()
    couriers = data.get("couriers", [])

    blocks: list[str] = []
    for c in couriers:
        cls, label = BADGE.get(c.get("verdict", ""), ("c-warn", "не проверено"))
        inner = [f'<p><strong>Правило:</strong> {_e(c.get("rule", ""))}</p>']
        if c.get("claim"):
            inner.append(f'<p><strong>Декларация:</strong> {_e(c["claim"])}</p>')
        if c.get("code") == "R1" and report:
            inner.append(_report_lines(report))
        else:
            if c.get("good"):
                inner.append("<p><strong>Что сошлось:</strong></p>" + _checks(c["good"], "y"))
            if c.get("bad"):
                inner.append("<p><strong>Что не сошлось:</strong></p>" + _checks(c["bad"], "n"))
            if c.get("checks"):
                inner.append(_checks(c["checks"], "y"))
        if c.get("caveat"):
            inner.append(f'<p class="c-note">{_e(c["caveat"])}</p>')
        if c.get("data"):
            inner.append(f'<p class="tags">источник: {_e(c["data"])}</p>')
        blocks.append(
            f'<article><h2>{_e(c.get("code", ""))} {_e(c.get("name", ""))} '
            f'<span class="verdict">— <span class="{cls}">{label}</span></span></h2>'
            + "".join(inner) + "</article>"
        )

    conf = data.get("confiscation") or {}
    conf_html = ""
    if conf:
        conf_html = (f'<div class="c-conf"><h3>Конфискат</h3>'
                     f'<p><strong>{_e(conf.get("title", ""))}</strong> {_e(conf.get("text", ""))}</p></div>')

    seal_html = ""
    if seal:
        seal_html = (f'<p class="c-note">Пломба: <code>{_e(seal.get("sealed_at_utc", ""))}</code> · '
                     f'нотариус {_e(seal.get("tsa", ""))} · {_e(seal.get("tsa_time", ""))} · '
                     f'подпись подтверждена. Манифест скрепляет отчёт проверки, журнал сделок '
                     f'и декларации курьеров: подменишь любую цифру — пломба перестанет сходиться.</p>')

    intro = ("Пункт досмотра заявленных результатов. Стратегии приезжают с грузом обещаний, "
             "и каждая проходит проверку по публичным данным биржи: цены существуют, комиссии "
             "по тарифу, нетто сходится. Что прошло — получает штамп. Что не прошло — в конфискат, "
             "с причиной. Штамп означает «записи подлинные», а не «стратегия прибыльна».")

    return ("<h1>Таможня</h1>"
            f'<p class="intro">{intro}</p>'
            + "".join(blocks) + conf_html + seal_html
            + '<p class="c-note">Досмотр идёт по публичным минутным свечам и публичной истории фандинга — '
              'ключей у проверяющего нет, и он может повторить проверку сам.</p>'
            + '<p class="c-note">Контент образовательный, не является инвестиционной рекомендацией. '
              'Торговля связана с риском потери капитала.</p>')
