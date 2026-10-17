"""Схема устройства стенда: одна картинка вместо абзаца.

Читатель не держит в голове шесть шагов из текста, а на схеме видит их сразу и в правильном
порядке: откуда данные, кто принимает решение, где стоит риск-слой, что нельзя подправить и
чем подтверждается время. SVG, а не растр: тот же вес, что один абзац, и остаётся чётким.

Важно, что схема описывает ТОЛЬКО то, что реально работает: у каждого блока подпись с механикой,
а не с обещанием. Если блок ещё не в строю — его на схеме нет.
"""
from __future__ import annotations

ACC = "#4cc9f0"
PANEL = "#111a2e"
LINE = "#22304a"
INK = "#e8eef8"
MUT = "#93a1b8"
WARN = "#f59e0b"
OK = "#4ade80"

STEPS = [
    ("Данные", "публичные часовые свечи", "свечи"),
    ("Правило", "код: EMA, стоп, тейк", "код"),
    ("Риск-слой", "размер, лимит, серии", "риск"),
    ("Журнал", "только дописать", "журнал"),
    ("Пломба", "FreeTSA, RFC 3161", "время"),
    ("Страница", "сборка из журналов", "лист"),
]

ICONS = {
    "свечи": '<path d="M-9 -7v6M-9 3v4M-4 -9v10M-4 6v3"/><rect x="-11" y="-1" width="4" height="4"/>'
             '<rect x="-6" y="-3" width="4" height="8"/>'
             '<path d="M3 -6v4M3 2v6M8 -8v14"/><rect x="1" y="-2" width="4" height="4"/>'
             '<rect x="6" y="-8" width="4" height="6"/>',
    "код": '<path d="M-9 -6L-3 0L-9 6"/><path d="M3 -6L9 0L3 6"/>',
    "риск": '<path d="M0 -9L9 7H-9z"/><path d="M0 -3v4"/><circle cx="0" cy="4" r="1" fill="currentColor"/>',
    "журнал": '<rect x="-8" y="-9" width="16" height="18" rx="2"/><path d="M-4 -4h8M-4 0h8M-4 4h5"/>',
    "время": '<circle cx="0" cy="0" r="9"/><path d="M0 -5V0l4 3"/>',
    "лист": '<rect x="-9" y="-8" width="18" height="16" rx="2"/><path d="M-5 3l4-5 3 3 4-6"/>',
}


def build(width: int = 980, height: int = 200) -> str:
    n = len(STEPS)
    gap = 10
    box_w = (width - 24 - gap * (n - 1)) / n
    box_h = 118
    top = 46
    out = [f'<svg class="schema" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Устройство стенда: данные, правило, риск-слой, журнал, пломба, страница">']

    for i, (title, sub, icon) in enumerate(STEPS):
        x = 12 + i * (box_w + gap)
        color = OK if icon == "время" else ACC
        out.append(f'<rect x="{x:.1f}" y="{top}" width="{box_w:.1f}" height="{box_h}" rx="12" '
                   f'fill="{PANEL}" stroke="{LINE}" stroke-width="1.5"/>')
        cx = x + box_w / 2
        out.append(f'<g transform="translate({cx:.1f},{top + 30})" stroke="{color}" fill="none" '
                   f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</g>')
        out.append(f'<text x="{cx:.1f}" y="{top + 64}" fill="{INK}" font-size="15" font-weight="640" '
                   f'text-anchor="middle">{title}</text>')
        # подпись рвём на две строки вручную: ширина блока известна заранее
        words = sub.split()
        lines = [" ".join(words[:2]), " ".join(words[2:])] if len(words) > 2 else [sub]
        for j, line in enumerate(lines):
            out.append(f'<text x="{cx:.1f}" y="{top + 84 + j * 15}" fill="{MUT}" font-size="11.5" '
                       f'text-anchor="middle">{line}</text>')
        if i < n - 1:
            ax = x + box_w + gap / 2
            out.append(f'<path d="M{ax - 4:.1f} {top + box_h / 2}h8m-3-3l3 3l-3 3" stroke="{MUT}" '
                       f'stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')

    # нижняя сквозная подпись: два контура проверки
    y = top + box_h + 40
    out.append(f'<path d="M{12 + box_w / 2:.1f} {y}H{12 + 5 * (box_w + gap) + box_w / 2:.1f}" '
               f'stroke="{WARN}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    out.append(f'<path d="M{12 + 5 * (box_w + gap) + box_w / 2 - 5:.1f} {y - 3}l5 3l-5 3" '
               f'stroke="{WARN}" stroke-width="1.5" fill="none" stroke-linecap="round"/>')
    out.append(f'<text x="{width / 2:.1f}" y="{y + 20}" fill="{MUT}" font-size="12" '
               f'text-anchor="middle">любой может повторить проверку: свечи публичные, ключи не нужны</text>')
    out.append("</svg>")
    return "".join(out)
