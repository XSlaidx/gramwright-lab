"""Единый шаблон разбора: заголовок, вывод, график, ограничения, источники.

Зачем отдельный модуль: пять разборов писались в разное время, и у каждого своя структура —
где-то вывод в конце, где-то график отсутствует, где-то ограничения растворены в тексте.
Читатель не должен заново учиться читать каждую страницу.

Порядок блоков зафиксирован:
  1. заголовок + главный вывод ДВУМЯ строками (до всех цифр и таблиц);
  2. главный график, если он есть;
  3. ограничения («чего это не доказывает») — до, а не после похвалы;
  4. источники и оговорка.

Ничего не выдумывается: если у разбора нет графика или ограничений, блок не рисуется вовсе —
пустая рамка «здесь будет график» хуже, чем её отсутствие.
"""
from __future__ import annotations

import html


def _e(x) -> str:
    return html.escape(str(x), quote=False)


def head(title: str, verdict: str, chips: list[str] | None = None,
         lead: str = "", warn_chip: str = "") -> str:
    parts = [f"<h1>{_e(title)}</h1>"]
    if verdict:
        parts.append(f'<p class="lead">{verdict}</p>')     # вывод — готовый HTML: в нём <b> с числами
    if lead:
        parts.append(f'<p class="sub">{_e(lead)}</p>')
    items = list(chips or [])
    if items or warn_chip:
        lis = "".join(f"<li>{_e(c)}</li>" for c in items)
        if warn_chip:
            lis += f'<li class="no">{_e(warn_chip)}</li>'
        parts.append(f'<ul class="chips">{lis}</ul>')
    return "".join(parts)


def chart_block(svg: str, legend: str, note: str = "",
                title: str = "Путь во времени, а не только итог") -> str:
    if not svg or "eq-empty" in svg:
        return ""
    note_html = f'<p class="note">{_e(note)}</p>' if note else ""
    return (f"<h2>{_e(title)}</h2>"
            f'<div class="eq-wrap">{svg}{legend}</div>{note_html}')


def limits_block(items: list[str], title: str = "Чего это не доказывает") -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_e(i)}</li>" for i in items)
    return f'<div class="cn-does"><h2>{_e(title)}</h2><ul>{lis}</ul></div>'


def sources_block(text: str, notes: list[str] | None = None) -> str:
    parts = [f'<p class="tags">{_e(text)}</p>']
    for n in notes or []:
        parts.append(f'<p class="note">{_e(n)}</p>')
    return "".join(parts)


DISCLAIMER = ("Контент образовательный, не является инвестиционной рекомендацией. "
              "Торговля связана с риском потери капитала.")
