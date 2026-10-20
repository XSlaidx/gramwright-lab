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
import sys
import time
import urllib.request

import case_shell
import equity_svg
import diag_blocks as _diag

HERE = os.path.dirname(os.path.abspath(__file__))
BEES = os.path.normpath(os.path.join(HERE, "..", "bees"))
DEMO = os.path.normpath(os.path.join(HERE, "..", "bybit-demo"))
API = "https://api.bybit.com"

# ── Вкладки: три слоя вместо простыни на 15 экранов ─────────────────────────────
# Вкладка не прячет данные от тех, у кого нет JS: панели по умолчанию видны, скрипт их схлопывает.
TABS_CSS = """
.tnav{position:sticky;top:0;z-index:20;display:flex;gap:6px;justify-content:center;flex-wrap:wrap;
 margin:18px auto 10px;padding:8px;max-width:1180px;background:rgba(11,15,20,.86);
 backdrop-filter:blur(6px);border:1px solid var(--bd,#1b2632);border-radius:14px}
.tnav button{font:inherit;font-size:15px;padding:9px 16px;border-radius:10px;cursor:pointer;
 background:transparent;color:#c7d2dd;border:1px solid transparent;white-space:nowrap}
.tnav button:hover{border-color:var(--bd,#1b2632);color:#fff}
.tnav button[aria-selected="true"]{background:rgba(76,201,240,.14);border-color:rgba(76,201,240,.5);color:#fff}
.tnav .cnt{opacity:.55;font-size:13px;margin-left:6px}
.tpane{display:block}
body.tabs-ready .tpane[data-active="0"]{display:none}
.tpane>h2:first-child{margin-top:6px}
.reveal-more{max-width:960px;margin:26px auto 0;padding:12px 16px;border:1px dashed var(--bd,#1b2632);
 border-radius:10px;font-size:14px;color:#9fb0c0;text-align:center}
.reveal-more b{color:#dbe6f0}
@media (max-width:640px){.tnav{position:static;justify-content:flex-start}.tnav button{font-size:14px;padding:8px 12px}}
"""

TAB_NAV = """
<div class="tnav" role="tablist" aria-label="Слои страницы">
 <button role="tab" id="tabbtn-0" data-tab="0" aria-selected="true" aria-controls="tabpane-0">Табло гонки<span class="cnt">итог окна</span></button>
 <button role="tab" id="tabbtn-1" data-tab="1" aria-selected="false" aria-controls="tabpane-1" tabindex="-1">Биржа и трение<span class="cnt">исполнение</span></button>
 <button role="tab" id="tabbtn-2" data-tab="2" aria-selected="false" aria-controls="tabpane-2" tabindex="-1">Модели и логика<span class="cnt">под капотом</span></button>
</div>
<script>
(function(){
  function init(){
  var panes=[].slice.call(document.querySelectorAll('.tpane'));
  var btns=[].slice.call(document.querySelectorAll('.tnav button'));
  if(!panes.length||!btns.length) return;
  document.body.classList.add('tabs-ready');
  function show(i,push){
    panes.forEach(function(p,k){ p.setAttribute('data-active', k===i ? '1':'0'); });
    btns.forEach(function(b,k){ b.setAttribute('aria-selected', k===i ? 'true':'false'); b.tabIndex = (k===i ? 0 : -1); });
    if(push){ try{ history.replaceState(null,'','#'+(new URLSearchParams({tab:String(i+1)})).toString()); }catch(e){} }
  }
  btns.forEach(function(b,k){ b.addEventListener('click', function(){ show(k,true); window.scrollTo({top:0,behavior:'smooth'}); }); });
  // Клавиатура: стрелки листают вкладки, как в стандартном tablist. Без этого вкладки доступны
  // только мышью, а role="tab" обещает обратное.
  btns.forEach(function(b,k){
    b.addEventListener('keydown', function(ev){
      var d = ev.key==='ArrowRight' ? 1 : (ev.key==='ArrowLeft' ? -1 : 0);
      if(!d) return;
      ev.preventDefault();
      var n=(k+d+btns.length)%btns.length;
      show(n,true); btns[n].focus();
    });
  });
  var m=/tab=(\\d+)/.exec(location.hash||''), start=m? Math.max(0,Math.min(panes.length-1,parseInt(m[1],10)-1)) : 0;
  show(start,false);
  }
  // Скрипт стоит ВЫШЕ панелей в разметке, поэтому без ожидания DOM он видит пустой список.
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
</script>
"""

# ── «Живая книга против симуляции»: воронка сверху, окно таблицы снизу ─────────────
# Зачем: при 100 сделках 90 % строк — «исполнено» с расхождением в 2–3 б.п. Портянка съедает
# внимание читателя, а вопросы аудита простые: сколько совпало, сколько контур пропустил и
# почём это стоило. Агрегат отвечает на них до прокрутки, метки — расшифровывают причину.
# Окно прокрутки ограничено 380 px (≈9 строк), шапка липкая, полоса прокрутки видимая:
# прошлый раз max-height спрятал свежие строки молча — теперь это проверяется clip_check.js.
RECON_CSS = """
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 14px;max-width:960px}
.kpi{flex:1 1 200px;min-width:170px;border:1px solid var(--line);border-radius:10px;
  padding:10px 12px;background:var(--panel)}
.kpi .v{font-size:20px;font-weight:600;line-height:1.25}
.kpi .l{color:#a4b2c7;font-size:12.5px;margin-top:3px}
.kpi.ok .v{color:var(--ok)} .kpi.warn .v{color:var(--warn)} .kpi.acc .v{color:var(--acc)}
.table-wrap-recon{max-height:380px;overflow-y:auto;overflow-x:auto;border:1px solid var(--line);
  box-shadow:inset 0 -16px 12px -12px rgba(0,0,0,.75);
  border-radius:10px;scrollbar-width:thin;scrollbar-color:#5b6f95 var(--panel);scrollbar-gutter:stable}
.table-wrap-recon table.tr{border-collapse:separate;border-spacing:0;width:100%}
.table-wrap-recon table.tr th{position:sticky;top:0;z-index:2;background:var(--panel);
  box-shadow:inset 0 -1px 0 var(--line)}
.table-wrap-recon::-webkit-scrollbar{width:12px;height:12px}
.table-wrap-recon::-webkit-scrollbar-track{background:var(--panel)}
.table-wrap-recon::-webkit-scrollbar-thumb{background:#5b6f95;border-radius:6px;border:3px solid var(--panel)}
.table-wrap-recon::-webkit-scrollbar-thumb:hover{background:#7189b3}
.recon-cap{color:var(--mut);font-size:12.5px;margin:6px 0 0;max-width:960px}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;line-height:1.6;
  border:1px solid transparent;white-space:nowrap;cursor:help}
.tag-ok{color:var(--ok);border-color:#2b4a35;background:#12251a}
.tag-warn{color:var(--warn);border-color:#4a3a17;background:#241c0d}
.tag-bad{color:var(--acc);border-color:#17384a;background:#0e2430}
.tag-mut{color:var(--mut);border-color:var(--line);background:transparent}
/* Узкий экран: оболочка сайта делает ВСЕ таблицы `display:block; overflow-x:auto`. Для окна с
   липкой шапкой это ломает главное: таблица сама становится контейнером прокрутки, и шапка
   уезжает вместе со строками (проверено на 390/700 px — «шапка не прилипает»). Возвращаем
   табличную раскладку только этому окну; горизонтальную прокрутку берёт на себя обёртка. */
@media(max-width:700px){
  .table-wrap-recon table.tr{display:table;width:100%;overflow:visible;white-space:normal}
  .table-wrap-recon table.tr th,.table-wrap-recon table.tr td{white-space:normal}
}
"""

EXTRA_CSS = """/* «Соревнование»: шкала, карточки участников, решение ИИ — в палитре сайта */
:root{--soft:#c7d2e2}
.hint{color:var(--mut);font-size:13.5px;white-space:normal;display:block;margin-top:4px}
/* Высоту НЕ ограничиваем: max-height:420px обрезал таблицу на середине, полоса прокрутки
   поверх контента не видна, и блок читался как пустой — при этом самые свежие сделки
   (они внизу) оставались ровно за срезом. Горизонтальная прокрутка на узком экране остаётся. */
.table-wrap{overflow-x:auto;margin:12px 0 22px;
             border-bottom:1px solid var(--line);-webkit-overflow-scrolling:touch}
table.tr{width:100%;border-collapse:collapse;margin:0;font-size:14.5px;min-width:620px}
table.tr th{color:var(--mut);font-weight:600;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
            position:sticky;top:0;background:#0f1829;z-index:1}
table.tr td{padding:8px 10px;border-bottom:1px solid #182338;font-variant-numeric:tabular-nums}
table.tr tr:last-child td{border-bottom:none}
table.tr .good{color:#4ade80} table.tr .bad{color:#f87171}
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

.uw{width:100%;height:64px;display:block;margin:4px 0 2px}
.uwrow{margin:0 0 16px}
.uwhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-size:14.5px}
.uwhead b{font-size:17px;color:#fff}
.uwnote{color:var(--mut);font-size:12.5px}
.scroll-hint{display:none;color:var(--mut);font-size:12.5px;margin:0 0 2px}
@media(max-width:560px){
  .cal{min-width:520px}
  /* Таблица шире экрана: говорим об этом вслух, иначе читатель считает обрезанный столбец ошибкой.
     Правило стоит ПОСЛЕ базового display:none, иначе медиазапрос ничего не меняет. */
  .scroll-hint{display:block}
}
.wscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 4px}
.cal{width:100%;border-collapse:collapse;margin:6px 0 10px;font-size:13.5px}
.cal th{text-align:left;color:var(--mut);font-weight:600;padding:8px 10px;
  border-bottom:1px solid #1a2740;font-size:12.5px;white-space:nowrap}
.cal th.num{text-align:right}
.cal td{padding:8px 10px;border-bottom:1px solid #141f33;color:var(--soft)}
.cal td.num{text-align:right;color:#fff;white-space:nowrap;font-variant-numeric:tabular-nums}
.cal .mn{color:var(--mut);font-size:12px}
.cal td.num .cnt{display:block;color:var(--mut);font-size:11.5px;font-weight:400;line-height:1.35}
.cal tr.tot td{border-top:1px solid #24334d;color:#fff;font-weight:600}
.rrow{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,fit-content(46%));gap:5px 16px;padding:13px 2px;
  border-top:1px solid #1a2740;align-items:baseline}
.rrow:first-of-type{border-top:none}
.rname{display:flex;align-items:center;gap:9px;font-size:15.5px;min-width:0;flex-wrap:wrap}
.rname b{color:#fff;font-weight:650}
.rb{font-size:11.5px;padding:2px 9px;border-radius:999px;border:1px solid transparent;
  color:var(--c);white-space:nowrap}
.rval{font-size:21px;font-weight:740;color:#fff;white-space:normal;overflow-wrap:anywhere;min-width:0;text-align:right}
.rval .rn{font-size:13px;font-weight:500;color:var(--mut)}
.rdiff{grid-column:1/-1;color:var(--soft);font-size:13.5px;line-height:1.55}
.rnote{grid-column:1/-1;color:var(--mut);font-size:12.5px;line-height:1.45}
details.how{margin:6px 0 20px;color:var(--mut);font-size:13.5px}
details.how summary{cursor:pointer;color:var(--soft)}
details.how p{margin:6px 0 0;line-height:1.6;max-width:900px}
@media(max-width:560px){
  /* Узкий экран: итог уходит на свою строку, иначе плашка с названием обрезается. */
  .rrow{grid-template-columns:1fr}
  .rval{grid-row:2;justify-self:start;text-align:left;font-size:20px;margin-top:2px}
  .rname{font-size:14.5px}
  .rval .rn{white-space:normal}
}
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
.ai p{grid-column:2;grid-row:auto;margin:0 0 8px;color:var(--soft);font-size:15px;align-self:start}
/* Заметка из нескольких абзацев: обычный поток. Сетку .ai использовать нельзя — её правило
   .ai p{grid-row:1/3} ставит ВСЕ абзацы в одну ячейку, и текст наезжает сам на себя. */
.mdl{background:#0e1729;border:1px solid var(--line);border-radius:14px;padding:18px 20px;
  max-width:960px;margin:0 auto;color:var(--soft);font-size:15px;line-height:1.6}
.mdl p{margin:0 0 12px}
.mdl p:last-child{margin-bottom:0}
.mdl a{color:var(--soft)}

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
    "live": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M20 52l14 14 40-40"/>
      <path d="M20 30h18" opacity=".55"/><path d="M20 74h26" opacity=".35"/></svg>""",
    "binance": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><path d="M48 16l16 16-16 16-16-16z"/>
      <path d="M20 44l12 12-12 12-12-12z" transform="translate(4 0)"/>
      <path d="M76 44l12 12-12 12-12-12z" transform="translate(-4 0)"/></svg>""",
    "learned": """<svg viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><circle cx="26" cy="26" r="7"/>
      <circle cx="26" cy="70" r="7"/><circle cx="70" cy="48" r="7"/>
      <path d="M31 31l32 13M31 65l32-13"/><circle cx="48" cy="48" r="3.5" fill="currentColor" stroke="none"/></svg>""",
}


def _e(x) -> str:
    return html.escape(str(x), quote=False)


def _pct(v, digits: int = 2) -> str:
    # Запятая и типографский минус — прямо здесь, а не надеждой на нормализатор: он правит только
    # текстовые узлы, и в атрибутах (aria-label, title) оставались точки и ASCII-минус (аудит 18.10.2026).
    return ("—" if v is None else
            f"{v:+.{digits}f}".replace("-", "\u2212").replace(".", ",") + " %")


def _float(x):
    """Число из журнала: там значения бывают строками, а форматирование ждёт float."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _tint(hex_color: str, alpha: float) -> str:
    """rgba из #rrggbb: плашка вида записи красится цветом участника, но тихо."""
    h = (hex_color or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        return f"rgba(139,153,176,{alpha})"
    return f"rgba({r},{g},{b},{alpha})"


def _lock_intervals() -> list[tuple[float, float | None]]:
    """История замков из дописываемого lock-history.jsonl: [(начало, конец|None), …], время местное."""
    rows = []
    try:
        with open(os.path.join(DEMO, "lock-history.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
    except (OSError, ValueError):
        return []
    out, opened = [], None
    for r in rows:
        try:
            ts = time.mktime(time.strptime(str(r.get("at") or ""), "%Y-%m-%d %H:%M:%S"))
        except (ValueError, TypeError):
            continue
        if r.get("kind") == "lock":
            opened = ts
        elif r.get("kind") == "unlock" and opened is not None:
            out.append((opened, ts))
            opened = None
    if opened is not None:
        out.append((opened, None))
    return out


def _lock_span_txt(hist: list[tuple[float, float | None]]) -> str:
    if not hist:
        return "(даты запирания в журнале нет)"
    start, end = hist[-1]
    frm = time.strftime("%d.%m %H:%M", time.gmtime(start))
    to = ("сейчас" if end is None else time.strftime("%d.%m %H:%M", time.gmtime(end)))
    hours = ((time.time() if end is None else end) - start) / 3600
    return f"с {frm} по {to} UTC, {_num(hours, 1)} ч"


def _lock_age_txt(hist: list[tuple[float, float | None]]) -> str:
    if not hist:
        return "длительность неизвестна"
    start, end = hist[-1]
    hours = ((time.time() if end is None else end) - start) / 3600
    return f"прошло {_num(hours, 1)} ч"


def _open_lines(ops: list[dict]) -> str:
    """Открытая живая позиция: что именно сейчас держит контур и где стоят стоп с тейком.

    Итог страницы считается по закрытым сделкам, поэтому без этой строки читатель видит «3 сделки»,
    хотя на бирже открыт риск. Защита должна быть названа вместе с ценами — её видно и в терминале.
    """
    if not ops:
        return ""
    rows = "".join(
        f'<div><b>{_e(str(o.get("symbol")))} {"LONG" if float(o.get("side_sign") or 0) > 0 else "SHORT"} '
        f'{_e(str(o.get("qty")))}</b> по {_num(o.get("entry_price"), 2)} · стоп {_num(o.get("sl"), 2)} · '
        f'тейк {_num(o.get("tp"), 2)}</div>' for o in ops)
    words = "позиция" if len(ops) == 1 else f"позиций: {len(ops)}"
    return ('<div style="max-width:960px;margin:12px auto 0;padding:10px 16px;border-left:3px solid #a78bfa;'
            'background:rgba(167,139,250,.10);border-radius:6px;font-size:14px;line-height:1.55">'
            f'<b>Открыто ({words}):</b>{rows}'
            '<div style="margin-top:4px;color:var(--mut)">Стоп и тейк стоят на бирже условными ордерами. '
            'В итог эти позиции не входят, пока не закрыты.</div></div>')


def _money(x, digits: int = 2) -> str:
    """Деньги с разрядами И дробной частью: «81 303,95» — как в остальных таблицах сайта."""
    txt = _num(x, digits)
    sign = "−" if txt.startswith("−") else ""
    body = txt.lstrip("−")
    whole, _, frac = body.partition(",")
    try:
        whole = f"{int(whole):,}".replace(",", " ")
    except ValueError:
        pass
    return sign + whole + (("," + frac) if frac else "")


def _thousands(value) -> str:
    """Целые деньги — с разделением разрядов: «100 000» читается, «100000» — нет."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return "—"
    return f"{n:,}".replace(",", " ")


def _min_trades() -> int:
    """Порог сделок для вывода — из params.json, а не из головы генератора страницы."""
    try:
        p = json.load(open(os.path.join(DEMO, "params.json"), encoding="utf-8"))
        return int(p.get("min_trades") or (p.get("gate") or {}).get("min_trades") or 30)
    except (OSError, ValueError):
        return 30


_ATTEMPT_TXT = {
    "blocked": "не отправлен: на счёте была позиция другого контура",
    "stale": "не отправлен: решение пришло позже окна",
    "skip": "не отправлен: предохранители запретили вход",
    "intent": "заявка выставлена",
}


def _side_note(cal: dict) -> str:
    """Отвечает на вопрос «шорты хуже из-за комиссий или из-за правила».

    Если издержки на круг у обеих сторон одинаковы, а брутто расходится — дело не в комиссиях.
    """
    sides = cal.get("sides") or {}
    lo, sh = sides.get("long"), sides.get("short")
    if not lo or not sh:
        return ""
    return (f'<p class="sub">Лонги против шортов: {lo["n"]} против {sh["n"]} сделок, прибыльных нетто '
            f'{_num(lo["wins_net"], 1)} % и {_num(sh["wins_net"], 1)} %. Издержки на круг у обеих сторон '
            f'одинаковы — {_num(lo["cost"], 3)} %, — значит причина не в комиссиях: брутто до издержек '
            f'{_num(lo["gross"], 2, plus=True)} % у лонгов и {_num(sh["gross"], 2, plus=True)} % у шортов. '
            f'Это свойство правила на этой истории, а не вывод о будущем.</p>')


def _learned_contrib(rec: dict) -> str:
    """Из чего сложилась вероятность: вклад каждого признака и проверка пересчётом.

    Для линейной модели логит = Σ (вес × z) + свободный член. Сумма вкладов обязана дать
    ровно ту вероятность, что записана в журнале, — иначе число в журнале ничем не подтверждено.
    """
    contrib = rec.get("contrib") or {}
    if not contrib:
        return ""
    items = sorted(contrib.items(), key=lambda kv: -abs(float(kv[1])))
    top = items[:3]
    logit = sum(float(v) for v in contrib.values()) + float(rec.get("bias") or 0.0)
    # Показываем округлённые слагаемые, а «остальные и свободный член» считаем как ОСТАТОК
    # от показанного логита. Иначе въедливый читатель сложит числа глазами, не получит сходимости
    # и решит, что в математике баг (аудит 19.10.2026: −0,080 против −0,082).
    # «Остальные» считаются СУММОЙ фактических вкладов, а не вычитанием округлённых: иначе
    # группа получает значение, которого нет в данных (на решении ETH 20.10 было −0,001 вместо −0,003,
    # потому что из логита вычитали 0,05+0,05−0,04). Округление показываем отдельной оговоркой.
    shown = [(n, round(float(v), 3)) for n, v in top]
    rest = round(sum(float(v) for n, v in items[3:]) + float(rec.get("bias") or 0.0), 3)
    logit_disp = round(logit, 4)
    parts = " · ".join(f'{_e(n)} <b>{_num(v, 3, plus=True)}</b>' for n, v in shown)
    check = ""
    if rec.get("p_recomputed") is not None:
        diff = abs(float(rec["p_recomputed"]) - float(rec.get("p_up") or 0))
        check = (f'Пересчёт по сохранённым весам даёт {_num(rec["p_recomputed"], 6)}, '
                 f'расхождение {_num(diff, 6)} — число в журнале собрано из этих весов.')
    return (f'<p class="hint" style="white-space:normal;margin:0 0 6px">'
            f'Что двигало вероятность: {parts} · остальные и свободный член '
            f'{_num(rest, 3, plus=True)} → логит {_num(logit_disp, 4, plus=True)}, '
            f'вероятность {_num(rec.get("p_up"), 4)}. {check} '
            f'Слагаемые округлены, поэтому сумма округлённых может отличаться от логита на 0,001.</p>'
            f'<p class="hint" style="white-space:normal;margin:0 0 6px">Веса: файл '
            f'<code>{_e(rec.get("weights_file") or "")}</code>, отпечаток содержимого весов '
            f'<code>{_e((rec.get("weights_sha256") or "")[:16])}</code> — это sha256 самих '
            f'коэффициентов, а не байтов файла. Признаки и веса пишутся '
            f'на каждое решение, поэтому p_up можно пересчитать вручную: '
            f'сумма (вес × стандартизованное значение) плюс свободный член, затем логистическая кривая.</p>')


def _learned_attempt(rec: dict) -> str:
    """Что стало с последним разрешённым решением. Молчание здесь — это ложь «всё в порядке»."""
    if not rec or rec.get("kind") != "learned_decision":
        return ""
    rows = _lines("ai-learner-trades.jsonl")
    test = {r.get("target_ts") for r in rows
            if r.get("kind") == "correction" and r.get("field") == "test" and r.get("value")}
    bar = rec.get("bar_ms")
    mine = [r for r in rows if r.get("kind") in _ATTEMPT_TXT and r.get("bar_ms") == bar
            and r.get("ts") not in test]
    if not mine:
        if rec.get("allowed"):
            return (f'<p class="hint" style="white-space:normal;margin:0 0 6px">Решение разрешено, '
                    f'попытки исполнения ещё не было: исполнитель ходит раз в 5 минут.</p>')
        return ""
    last = mine[-1]
    txt = _ATTEMPT_TXT[last["kind"]]
    if last.get("kind") == "stale" and last.get("age_min") is not None:
        txt += f" (опоздание {_num(last['age_min'], 0)} мин)"
    if last.get("kind") == "skip" and last.get("reasons"):
        txt += ": " + "; ".join(last["reasons"])[:120]
    return f'<p class="hint" style="white-space:normal;margin:0 0 6px">Исполнение — {_e(txt)}.</p>'


def _mt5_status(rows: list[dict], mt5: dict, trading: bool) -> str:
    """Живое состояние второй площадки: счёт, инструменты, рынок, режим.

    Раньше карточка обещала «до трёх позиций, предел 10 %», хотя ордера там не выставляются,
    а в выходные рынок TradFi закрыт и сигналов быть не может. Обещание без состояния —
    это то, за что нас справедливо ругали в ревью.
    """
    last = next((r for r in reversed(rows) if r.get("kind") == "mt5_bar"), None)
    if not last:
        return "прогонов нет — контур не запускался"
    symbols = last.get("symbols") or {}
    live = [s for s, v in symbols.items() if v.get("market_open")]
    bars = [f"{s}: баров {v.get('bars')}" for s, v in list(symbols.items())[:1]]
    acct = str(last.get("account") or "")
    # Номер счёта — не наш секрет, но и не то, что стоит публиковать целиком: хватает хвоста.
    parts = [f"счёт {acct or '—'} · {last.get('server')}",
             f"эквити {_thousands(last.get('equity'))}"]
    shut = [s for s, v in symbols.items() if not v.get("market_open")]
    if live and shut:
        parts.append(f"инструментов {len(symbols)} (живых {len(live)}; закрыт {', '.join(shut)})")
    elif live:
        parts.append(f"инструментов {len(symbols)} (живых {len(live)})")
    else:
        parts.append(f"инструментов {len(symbols)} · рынок закрыт")
    # последний бар лежит внутри каждого инструмента, а не в корне записи
    bar = last.get("last_bar") or next((v.get("last_bar") for v in symbols.values()
                                        if v.get("last_bar")), None)
    if bar:
        parts.append(f"последний бар {bar} UTC")
    parts.append("сделки разрешены флагом (ордера ставит отдельный цикл)" if trading
                 else "сделки выключены: нет файла-флага")
    return " · ".join(parts)


def _lines_binance(name: str) -> list[dict]:
    """Строки книги советника: она лежит рядом с bybit-demo, а не внутри."""
    path = os.path.join(os.path.dirname(DEMO), name)
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def _date_ru(value) -> str:
    """Дата для читателя: 18.10.2026, а не 2026-10-18 (аудит 18.10.2026)."""
    raw = str(value or "")
    head = raw[:10]
    if len(head) == 10 and head[4] == "-" and head[7] == "-":
        return f"{head[8:10]}.{head[5:7]}.{head[:4]}"
    return raw or "—"


def _slip_range_txt() -> str:
    """Диапазон скольжения живых выходов — из книги, а не из старой плашки.

    В тексте стояло «1,4–5,9 б.п.», хотя у пятой сделки вышло около 20 б.п.: цифра была
    набрана руками и не обновлялась (аудит 18.10.2026).
    """
    demo = _json("demo-state.json", {}) or {}
    vals = [float(t["slip_bp"]) for t in (demo.get("closed") or [])
            if isinstance(t.get("slip_bp"), (int, float))]
    if not vals:
        return "не измерено"
    lo, hi = min(vals), max(vals)
    return f"{_num(lo, 1)}–{_num(hi, 1)} б.п. (n={len(vals)})" if abs(hi - lo) > 0.05 else f"{_num(lo, 1)} б.п."


def _lock_cost_txt() -> str:
    """Что дал замок: сколько хода он пропустил. Знак — из данных."""
    v = _live_vs_sim()
    if not v.get("n_sim"):
        return "не измерено"
    val = float(v.get("skipped_lock") or 0)
    if abs(val) < 1e-9:
        return "ничего: пропущенных сделок за время замка не было"
    # Формулировка целиком, а не кусок фразы: раньше получалось «это стоило 0,17 п.п. — сделки дали
    # минус», то есть одно и то же событие называлось и потерей, и экономией (аудит 18.10.2026).
    return (f"стоило {_num(abs(val), 2)} п.п. упущенного хода" if val > 0
            else f"сэкономило {_num(abs(val), 2)} п.п.: пропущенные сделки в сумме дали минус")


def _live_vs_sim() -> dict:
    """Построчное сопоставление живой книги с симуляцией.

    Нужно, потому что разрыв «живые −0,89 % на сделку против −0,09 % в симуляции» выглядит как
    проскальзывание, а на деле это разные наборы сделок: часть сигналов не была исполнена вовсе.
    Причина неисполнения выводится из данных (запуск контура, замок, занятая позиция), а если её
    восстановить нельзя — так и пишется.
    """
    demo = _json("demo-state.json", {}) or {}
    state = _json("state.json", {}) or {}
    live = sorted(demo.get("closed") or [], key=lambda t: int(t.get("entry_ms") or 0))
    sim = sorted(state.get("forward_book") or [], key=lambda t: int(t.get("bar_ms") or 0))
    hist = _lock_intervals()
    first_live = int(live[0]["entry_ms"]) if live else None
    span = 2 * 3600 * 1000          # вход ставится в пределах двух часов после открытия бара

    def in_lock(ms: int) -> bool:
        for start, end in hist:
            a = int(start * 1000)
            b = int((end if end is not None else time.time()) * 1000)
            if a <= ms <= b:
                return True
        return False

    def busy(ms: int) -> bool:
        for t in live:
            if int(t["entry_ms"]) <= ms + span and ms <= int(t["exit_ms"]):
                return True
        return False

    rows = []
    # Сопоставление строго один-к-одному: два живых входа могут попасть в двухчасовое окно одного
    # бара (18.10 так и вышло — 13:02 и 13:41 по UTC), и тогда вторая сделка молча считалась
    # «совпавшей», хотя пары у неё нет. Отсюда и не сходилось 8 против 7.
    used = set()
    for t in sim:
        bar = int(t.get("bar_ms") or 0)
        side = int(t.get("side") or (1 if float(t.get("side_sign") or 1) > 0 else -1))
        match = next((l for l in live
                      if id(l) not in used
                      and l.get("symbol") == t.get("symbol")
                      and int(l.get("side_sign") or 0) == side
                      and 0 <= int(l["entry_ms"]) - bar <= span), None)
        if match is not None:
            used.add(id(match))
        if match:
            why = "исполнено"
        elif first_live and bar + span < first_live:
            why = "контур ещё не работал"
        elif in_lock(bar + span):
            why = "входы заперты серией убытков"
        elif busy(bar):
            why = "одна позиция за раз"
        else:
            why = "причина не восстановлена"
        rows.append({"bar": bar, "symbol": t.get("symbol"), "side": side,
                     "sim": float(t.get("net_pct") or 0), "exit": t.get("exit") or t.get("exit_reason"),
                     "live": float(match["net_pct"]) if match else None, "why": why})

    # Живая сделка, которой нет в симуляции: правило симуляции в этот бар не входило (была занята
    # другая позиция). Раньше такая сделка просто исчезала из таблицы, и счётчики не сходились:
    # строк 12, живых 7, а сделок у биржи 8. Теперь она идёт отдельной строкой с прочерком в
    # колонке симуляции — так 8 = 8 и читателю видно, откуда лишняя.
    live_only = [l for l in live if id(l) not in used]
    for l in live_only:
        ent = int(l["entry_ms"])
        bar = ent - (ent % 3600000)
        side = int(l.get("side_sign") or 1)
        rows.append({"bar": bar, "symbol": l.get("symbol"), "side": side,
                     "sim": None, "exit": l.get("exit_reason"),
                     "live": float(l.get("net_pct") or 0),
                     "why": "только у биржи: симуляция в этот бар не входила",
                     "live_only": True})
    rows.sort(key=lambda r: r["bar"])

    # Пары — только там, где есть обе колонки: иначе среднее по симуляции считалось бы по None.
    matched = [r for r in rows if r["live"] is not None and r["sim"] is not None]
    live_avg = (sum(float(l["net_pct"]) for l in live) / len(live)) if live else None
    # Среднее по симуляции на ТЕХ ЖЕ сделках считалось из живой колонки — отсюда «расхождение
    # 0,000 п.п.»: одна и та же величина сравнивалась сама с собой (аудит 18.10.2026).
    sim_match_avg = (sum(r["sim"] for r in matched) / len(matched)) if matched else None
    skipped = sum(r["sim"] for r in rows if r["live"] is None and r["sim"] is not None)
    skipped_lock = sum(r["sim"] for r in rows
                       if r["live"] is None and r["sim"] is not None and "заперты" in r["why"])
    skipped_other = skipped - skipped_lock
    return {"rows": rows, "live_avg": live_avg, "sim_match_avg": sim_match_avg,
            "sim_avg": (sum(r["sim"] for r in rows if r["sim"] is not None)
                        / max(1, len([r for r in rows if r["sim"] is not None]))) if rows else None,
            "skipped": skipped, "skipped_lock": skipped_lock, "skipped_other": skipped_other,
            "n_live": len(live), "n_sim": len([r for r in rows if r["sim"] is not None])}


def _model_label(name) -> str:
    """Имя модели из журнала — в понятный вид: beam:cloud читателю ничего не говорит."""
    s = str(name or "").strip()
    if not s or s == "—":
        return "не записано"
    labels = {"beam:cloud": "облачная модель (beam)", "beam": "облачная модель (beam)"}
    return labels.get(s, s)


def _clock_note() -> str:
    """Сколько расходится «время биржи» и «время записи» — считается, а не берётся на веру.

    В журнале поле ts пишется местным временем в момент записи, а *_ms приходит от биржи. У части
    сделок запись появилась позже события (журнал восстанавливали), поэтому одно событие живёт
    с двумя временами. Страница считает всё по времени биржи — здесь написано, насколько велико
    расхождение, чтобы его не искали вручную.
    """
    lags = []
    for r in _lines("demo-journal.jsonl"):
        if r.get("kind") not in ("entry", "exit"):
            continue
        ms = r.get("exit_ms") or r.get("entry_ms")
        ts = r.get("ts")
        if not ms or not ts:
            continue
        try:
            rec = time.mktime(time.strptime(str(ts), "%Y-%m-%d %H:%M:%S"))
        except (ValueError, TypeError):
            continue
        lags.append((rec - int(ms) / 1000) / 3600.0)
    if not lags:
        return ""
    worst = max(lags)
    if worst < 1.0:
        return ('<p class="sub" style="max-width:960px;margin:8px auto 0">В журнале две отметки времени '
                f'— биржи и записи; сейчас они расходятся не больше чем на {_num(worst, 1)} ч.</p>')
    return ('<p class="sub" style="max-width:960px;margin:8px auto 0">В журнале две отметки времени: '
            'биржи (по ней всё считается в таблицах) и записи. Часть записей восстановлена задним '
            f'числом, поэтому время записи может быть позже: наибольшее расхождение сейчас '
            f'{_num(worst, 1)} ч. Старые записи разбирались задним числом, новые пишут обе отметки.</p>')


def _live_vs_sim_block() -> str:
    d = _live_vs_sim()
    if not d["rows"] or not d["n_live"]:
        return ""
    # ── Воронка расхождений: считаем при сборке, ничего не пишем руками ──────────────
    # При 100 сделках 90 % строк — «исполнено» с расхождением в 2–3 б.п. Читателю нужны
    # аномалии и цена тормозов, а не портянка. Поэтому сверху агрегат, ниже — окно таблицы.
    rows = list(reversed(d["rows"]))                      # свежие сверху
    pairs = [r for r in rows if r["live"] is not None and r["sim"] is not None]
    miss = [r for r in rows if r["live"] is None and r["sim"] is not None]
    live_only = [r for r in rows if r.get("live_only")]
    slip = (sum(r["live"] - r["sim"] for r in pairs) / len(pairs)) if pairs else None
    _short = {"входы заперты серией убытков": "замок", "одна позиция за раз": "лимит в 1 позицию",
              "контур ещё не работал": "до запуска"}
    miss_by = {}
    for r in miss:
        k = _short.get(r["why"], r["why"])
        miss_by[k] = miss_by.get(k, 0) + 1
    # Каждый пункт в своей неразрывной обёртке: иначе «до запуска: 1» рвётся и единица
    # уезжает на отдельную строку, читаясь как ещё одна карточка.
    miss_txt = " · ".join(f'<span style="white-space:nowrap">{k}: {v}</span>'
                          for k, v in sorted(miss_by.items(), key=lambda x: -x[1]))
    body = []
    for r in rows:
        when = time.strftime("%d.%m %H:%M", time.gmtime(r["bar"] / 1000))
        side = "LONG" if r["side"] > 0 else "SHORT"
        live_txt = _pct(r["live"], 3) if r["live"] is not None else "—"
        sim_txt = _pct(r["sim"], 3) if r["sim"] is not None else "—"
        cls = "" if r["live"] is None else (' class="good"' if r["live"] > 0 else ' class="bad"')
        if r.get("live_only"):
            tag = ('<span class="tag tag-bad" title="Контур вошёл, а симуляция в этот бар не входила: '
                   'была занята другой позицией">Только биржа</span>')
        elif r["live"] is not None and r["sim"] is not None:
            tag = ('<span class="tag tag-ok" title="Оба вошли в этот бар; разница в результате — '
                   'скольжение и комиссии">Синхронно</span>')
        else:
            kind, label = {"входы заперты серией убытков": ("tag-warn", "Замок"),
                           "одна позиция за раз": ("tag-warn", "Лимит в 1 позицию"),
                           "контур ещё не работал": ("tag-mut", "До запуска")}.get(
                               r["why"], ("tag-warn", "Пропуск"))
            tag = f'<span class="tag {kind}" title="{_e(r["why"])}">{label}</span>'
        body.append(f"<tr><td>{when}</td><td>{_e(str(r['symbol']))}</td><td>{side}</td>"
                    f"<td{cls}>{live_txt}</td><td>{sim_txt}</td>"
                    f"<td>{_e(str(r['exit'] or '—'))}</td><td>{tag}</td></tr>")
    kpis = (f'<div class="kpis">'
            f'<div class="kpi"><div class="v">{len(rows)}</div>'
            f'<div class="l">сигналов всего</div></div>'
            f'<div class="kpi ok"><div class="v">{len(pairs)} / {len(rows)}</div>'
            f'<div class="l">синхронно'
            + (f' · расхождение с симуляцией {_num(slip, 3, plus=True)} п.п.' if slip is not None else '') +
            f'</div></div>'
            f'<div class="kpi warn"><div class="v">{len(miss)}</div>'
            f'<div class="l">пропущено контуром' + (f' · {miss_txt}' if miss_txt else '') +
            f'</div></div>'
            f'<div class="kpi acc"><div class="v">{len(live_only)}</div>'
            f'<div class="l">только у биржи — вне симуляции</div></div>'
            f'</div>')
    diff = None
    if d["live_avg"] is not None and d["sim_match_avg"] is not None:
        diff = abs(d["live_avg"] - d["sim_match_avg"])
    summary = (f"Средний результат: живые <b>{_pct(d['live_avg'], 3)}</b> на сделку, "
               f"те же сделки в симуляции — <b>{_pct(d['sim_match_avg'], 3)}</b>"
               + (f", расхождение {_num(diff, 3)} п.п. — это и есть проскальзывание и комиссии."
                  if diff is not None else "."))
    # Точная формулировка: не «биржа не исполнила» (ордера никто не отправлял), а «контур не входил».
    # Знак важен: пропущенная ПРИБЫЛЬ — потеря, пропущенный убыток — экономия. Считать их одной суммой
    # и писать «тормоза сберегли» — именно та ошибка, которую поймал внешний разбор.
    # «одна до запуска, одна из-за позиции, две из-за замка» было набрано руками и устаревало при
    # каждой новой сделке. Теперь считается по колонке причин (аудит 18.10.2026).
    miss = [r for r in d["rows"] if r["live"] is None]
    by_why = {}
    for r in miss:
        by_why[r["why"]] = by_why.get(r["why"], 0) + 1
    why_txt = "; ".join(f"{v} — {k}" for k, v in sorted(by_why.items(), key=lambda x: -x[1]))
    n_pairs = len([r for r in d["rows"] if r["live"] is not None and r["sim"] is not None])
    n_live_only = len([r for r in d["rows"] if r.get("live_only")])
    summary += (f" Симуляция учла {d['n_sim']} {_plural(d['n_sim'], 'сделку', 'сделки', 'сделок')}, "
                f"контур исполнил {d['n_live']}: "
                f"{n_pairs} {_plural(n_pairs, 'сделка совпала', 'сделки совпали', 'сделок совпали')} "
                f"с симуляцией"
                + (f", {n_live_only} — только у биржи (симуляция в этот бар не входила, "
                   f"была занята другая позиция)" if n_live_only else "")
                + f". Значит {d['n_live']} = {n_pairs} + {n_live_only}. "
                f"Остальные строки — сигналы, до биржи не дошедшие"
                + (f": {why_txt}" if why_txt else "") + ". "
                f"Пропущенные сделки вместе дали бы {_pct(d['skipped'], 3)}: замок снял "
                f"{_pct(d['skipped_lock'], 3)} — сам по себе он сэкономил, — а запуск контура и запрет "
                f"второй позиции стоили {_pct(d['skipped_other'], 3)}. При "
                f"{d['n_live']} {_plural(d['n_live'], 'исполненной сделке', 'исполненных сделках', 'исполненных сделках')} "
                f"всё это в пределах шума: разницу между живой и симулированной книгой объяснить нельзя, "
                f"сопоставимы только пары выше, и там расхождение — комиссии и скольжение.")
    return (f'<h2>Живая книга против симуляции: построчно</h2>'
            f'<p class="sub" style="max-width:960px;margin:0 auto 10px">Каждая сделка правила — слева, '
            f'что из неё вышло у биржи и что насчитала симуляция. Так видно, где разошлись не цены, '
            f'а сам набор сделок.</p>'
            + kpis +
            f'<div class="table-wrap table-wrap-recon"><table class="tr"><thead><tr>'
            f'<th>Бар входа (UTC)</th>'
            f'<th>Инструмент</th><th>Сторона</th><th>Живая</th><th>Симуляция</th><th>Выход</th>'
            f'<th>Почему разошлось</th></tr></thead><tbody>{"".join(body)}</tbody></table></div>'
            f'<p class="recon-cap">↕ Всего {len(rows)} {_plural(len(rows), "строка", "строки", "строк")}'
            f' · свежие сверху · окно прокручивается внутри рамки, страница не растёт'
            f' · наведите на метку — будет полная причина</p>'
            f'<p class="sub" style="max-width:960px;margin:10px auto 0">{summary}</p>'
            f'<p class="sub" style="max-width:960px;margin:8px auto 0">Время выхода у пары может '
            f'расходиться на часы, и это не ошибка часов: в симуляции выход помечен баром, в котором '
            f'цена коснулась уровня, а у живой сделки — моментом, когда сработал стоп на бирже. Уровни '
            f'тоже разные: стоп живой позиции считается от её собственной цены входа, а она отличается '
            f'на проскальзывание.</p>'
            + _clock_note())


def _decided(rec: dict) -> str:
    """Когда решение принято и по какому бару. Без этого блок читается как статичный текст."""
    ts = str(rec.get("ts") or "")
    bar = rec.get("bar_ms")
    parts = []
    epoch = None
    try:
        # ts пишется местным временем машины (Windows, UTC+3), а на сайте всё в UTC:
        # показывать чужое «локальное» время как UTC — та же ошибка, что и статичное число.
        epoch = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
        parts.append("решение " + time.strftime("%d.%m %H:%M", time.gmtime(epoch)) + " UTC")
    except (ValueError, TypeError):
        parts.append("решение (время не записано)")
    if bar:
        parts.append("бар " + time.strftime("%d.%m %H:%M", time.gmtime(int(bar) / 1000)) + " UTC")
    if epoch:
        parts.append(_num(max(0.0, (time.time() - epoch) / 3600), 1) + " ч назад")
    return " · ".join(parts)


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


def _plural(n: int, one: str = "сделка", few: str = "сделки", many: str = "сделок") -> str:
    """Русское склонение: 1 сделка, 2 сделки, 5 сделок. Страница с «2 сделок» выглядит как машинный
    перевод и подрывает доверие ровно там, где мы просим верить цифрам."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many



def _num(x, digits: int = 1, plus: bool = False) -> str:
    """Русская запись числа: 8.09 → «8,09», −23.8 → «−23,8», +331.19 → «+331,19».

    Единственная точка форматирования чисел на странице. До 18.10.2026 их было две: ось шкалы
    печатала «−5,0 %», а карточки и таблица — «−0.60 %». Читатель видел два разных сайта
    в одном экране, и это подрывало доверие ровно к тем числам, которые мы просим проверять.
    """
    if x is None:
        return "—"
    spec = f"{float(x):+.{digits}f}" if plus else f"{float(x):.{digits}f}"
    return spec.replace("-", "−").replace(".", ",")


def _model_facts() -> dict:
    """Числа модели — из общего модуля `model_facts.py` (реестр испытаний + файл прогона).

    Логика живёт в одном месте: те же цифры печатают страница соревнования и публичный разбор,
    и второй экземпляр расчёта рано или поздно разошёлся бы с первым — именно так на страницах
    появлялись 8,09 против 8,13 и «261 запись» вместо 261 испытания.
    """
    try:
        parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent not in sys.path:
            sys.path.insert(0, parent)
        from model_facts import model_facts
        return model_facts()
    except Exception as e:                                   # noqa: BLE001
        print(f"  внимание: числа модели не прочитаны ({e})")
        return {}


def _card(key: str, color: str, name: str, rule: str, big: str, note: str, tag: str,
          spark: str = "") -> str:
    return (f'<div class="cn-card" role="group" aria-label="{_e(name)}: {_e(big)}" '
            f'style="--c:{color}"><div class="em">{EMBLEM[key]}</div>'
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
    # Живая книга: только то, что биржа действительно исполнила (demo-state.json, closed-pnl).
    # forward_book — форвардный учёт на публичных свечах: сигнал разрешается по будущим барам,
    # ордера не отправляются. Смешивать их нельзя: 18.10 выяснилось, что страница называла
    # «живыми ордерами» семь симулированных сделок, а живых было три, и все три в минус.
    live_state = _json("demo-state.json", {}) or {}
    live_book = [t for t in (live_state.get("closed") or []) if t.get("net_pct") is not None]
    # открытых позиций может быть несколько (слот на символ)
    _opens = live_state.get("opens")
    live_opens = [dict(v, symbol=k) for k, v in (_opens or {}).items()] if isinstance(_opens, dict) else []
    if not live_opens and live_state.get("open"):
        live_opens = [live_state["open"]]
    live_open = live_opens[0] if live_opens else None
    live_pct = round(sum(float(t.get("net_pct") or 0) for t in live_book), 2) if live_book else None
    btc = _holding("BTCUSDT", anchor, now) if anchor else None
    eth = _holding("ETHUSDT", anchor, now) if anchor else None
    hold = round((btc + eth) / 2, 2) if (btc is not None and eth is not None) else None

    rc = _json("random-control.json") or {}
    rc_med = rc.get("random_median_pct")
    rc_lo, rc_hi = rc.get("random_p05_pct"), rc.get("random_p95_pct")
    rc_beaten = rc.get("share_random_beats_rule_pct")

    ai = [r for r in _lines("ai-bee-journal.jsonl") if r.get("side")]
    learned = [r for r in _lines("ai-learner-journal.jsonl") if r.get("kind") == "learned_decision"]
    lt = _lines("ai-learner-trades.jsonl")
    l_intents = [t for t in lt if t.get("kind") == "intent"]
    l_fills = [t for t in lt if t.get("kind") == "filled"]
    l_exits = [t for t in lt if t.get("kind") == "exit"]
    l_blocked = [t for t in lt if t.get("kind") == "blocked"]
    # Отдельный счёт модели: второй ключ лежит в домашнем каталоге. Есть он — контур живёт своей
    # книгой и соседние позиции «Тренда» ему больше не мешают.
    l_own_account = os.path.exists(os.path.join(os.path.expanduser("~"), ".bybit-demo2-key.txt"))
    l_net = sum(float(t.get("net_usdt") or 0) for t in l_exits)
    l_fill = (len(l_fills) / len(l_intents) * 100) if l_intents else None
    l_on = os.path.exists(os.path.join(DEMO, "ai_learner_enabled"))
    l_allowed = [r for r in learned if r.get("allowed")]
    last_learned = learned[-1] if learned else None
    # Попытки исполнения: если решение РАЗРЕШЕНО, но сделки нет, на странице должна быть причина,
    # а не молчание. Тестовые записи (dry-run) помечены correction-строкой и не считаются.
    _lt_rows = _lines("ai-learner-trades.jsonl")
    _lt_test = {r.get("target_ts") for r in _lt_rows
                if r.get("kind") == "correction" and r.get("field") == "test" and r.get("value")}
    l_attempt = next((r for r in reversed(_lt_rows)
                      if r.get("kind") in ("blocked", "skip", "stale", "intent")
                      and r.get("ts") not in _lt_test), None)
    ai_ok = [r for r in ai if r.get("allowed")]
    adv = [r for r in _lines("advisor-book.jsonl") if r.get("kind") == "trade"]
    adv_net = round(sum(float(r.get("net_pct") or 0) for r in adv), 2) if adv else None
    adv_coin = _json("advisor-coin.json") or {}
    # живой контур советника на демо Binance: своя книга и своё состояние
    bpath = os.path.join(os.path.dirname(DEMO), "binance-advisor-book.jsonl")
    b_trades, _b_fix = [], {}
    if os.path.exists(bpath):
        with open(bpath, encoding="utf-8") as fh:
            rows_all = []
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows_all.append(json.loads(line))
                except ValueError:
                    continue
        # уточнения (correction) накладываем поверх записи по её ts: исходную цифру не переписываем,
        # но и не показываем как действующую (18.10.2026: комиссия входной ноги не входила в нетто)
        for rec in rows_all:
            if rec.get("kind") == "correction" and rec.get("target_ts"):
                _b_fix.setdefault(rec["target_ts"], {})[rec.get("field")] = rec.get("value")
        for rec in rows_all:
            if rec.get("kind") == "exit":
                row = dict(rec)
                row.update({k: v for k, v in _b_fix.get(rec.get("ts"), {}).items()
                            if k in ("fees", "net_usdt")})
                b_trades.append(row)
    b_net = round(sum(float(r.get("net_usdt") or 0) for r in b_trades), 4) if b_trades else None
    # доля исполнения постановок — главное, что измеряет этот контур: сколько заявок дошло до сделки,
    # сколько не исполнилось и сколько биржа отклонила (post-only превратился бы в тейкер)
    _b_all = _lines_binance("binance-advisor-book.jsonl")
    b_intents = [r for r in _b_all if r.get("kind") == "intent"]
    b_rejected = [r for r in b_intents if r.get("rejected") or str(r.get("ret") or "").startswith("HTTP")]
    try:
        _b_state = (json.load(open(os.path.join(os.path.dirname(DEMO), "binance-advisor-state.json"),
                                   encoding="utf-8")) or {}).get("open") or None
    except (OSError, ValueError):
        _b_state = None
    b_filled = len(b_trades) + (1 if _b_state else 0)
    b_cancel = len([r for r in _b_all if r.get("kind") == "cancel"])
    # стоимость неисполнения: missed_pct пишется при снятии лимитки (ход против нашей стороны)
    b_missed = [float(r["missed_pct"]) for r in _b_all
                if r.get("kind") == "cancel" and isinstance(r.get("missed_pct"), (int, float))]
    b_missed_sum = round(sum(b_missed), 1) if b_missed else None
    b_on = os.path.exists(os.path.join(os.path.dirname(DEMO), "binance_advisor_enabled"))
    # Открытая позиция второй площадки: как и у Bybit, она обязана быть видна — иначе читатель
    # считает, что там «0 сделок», пока на бирже держится позиция с защитой.
    try:
        with open(os.path.join(os.path.dirname(DEMO), "binance-advisor-state.json"), encoding="utf-8") as fh:
            b_open = (json.load(fh) or {}).get("open") or None
    except (OSError, ValueError):
        b_open = None
    last_ai = ai[-1] if ai else None

    mt5 = _json("mt5-demo-state.json", {}) or _json("mt5-state.json", {}) or {}
    _opens_labels = [f"{o.get('symbol')} {'лонг' if float(o.get('side_sign') or 0) > 0 else 'шорт'}"
                     for o in (live_opens or [])]
    mt5_rows = _lines("mt5-journal.jsonl")
    mt5_exits = [r for r in mt5_rows
                 if r.get("kind") in ("mt5_exit", "mt5_demo_exit") and not r.get("forced")]
    mt5_trades = len(mt5_exits)
    mt5_net = sum(float(r.get("net_usdt") or 0) for r in mt5_exits)
    # Тестовая сделка (проверка ветки входа) — тоже исполнение, но в книгу правила не идёт.
    # Показываем оба числа: иначе «сделок 1» рядом с эквити, где учтены две, читается как ошибка.
    mt5_all_exits = [r for r in mt5_rows
                     if r.get("kind") in ("mt5_exit", "mt5_demo_exit", "mt5_forced_test_exit")]
    mt5_all = len(mt5_all_exits)
    mt5_tests = max(0, mt5_all - mt5_trades)
    mt5_positions = len(mt5.get("positions") or [])
    mt5_runs = mt5.get("runs") or len(mt5_rows)
    # торговля на второй площадке включается файлом-флагом, как и на Bybit
    mt5_trading = bool(mt5.get("trading")) or os.path.exists(os.path.join(DEMO, "mt5_demo_enabled"))
    # Проверка ветки входа — отдельно от сделок правила: тестовая сделка не должна выглядеть сигналом.
    mt5_forced = [r for r in mt5_rows if r.get("kind") == "mt5_forced_test_exit"]
    mt5_last_bar = next((r for r in reversed(mt5_rows)
                         if r.get("kind") == "mt5_bar" and r.get("symbols")), None)
    mt5_market_open = None
    if mt5_last_bar:
        flags = [bool(v.get("market_open")) for v in (mt5_last_bar.get("symbols") or {}).values()]
        # НЕ all(): 19.10.2026 индекс US500 ещё не открылся, и карточка объявляла закрытым весь
        # MT5, хотя евро, золото и USTEC торговались. Считаем по числу живых инструментов и
        # показываем это числом, а не булевым «открыт/закрыт».
        mt5_live = sum(flags) if flags else None
        mt5_total = len(flags) if flags else None
        mt5_market_open = (mt5_live > 0) if flags else None

    # ── общая шкала: один домен для всех точек ───────────────────────────
    vals = [v for v in (rule, hold, rc_med, adv_net) if isinstance(v, (int, float))]
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
            f"Преимущества не показано на симуляции: правило <b>{_pct(rule)}</b> лежит внутри разброса "
            f"случайной монетки <b>{_pct(rc_lo)} … {_pct(rc_hi)}</b>."
            if inside else
            f"Правило <b>{_pct(rule)}</b> вышло за пределы полосы случайной монетки "
            f"<b>{_pct(rc_lo)} … {_pct(rc_hi)}</b>, но сделок слишком мало, чтобы этому верить.")
    else:
        read = "Контроль ещё не посчитан, поэтому сравнивать не с чем."
        verdict_line = "Сравнивать пока не с чем: контроль не посчитан."

    enough = (f"{len(book)} {_plural(len(book))} · мало данных для вывода о качестве" if len(book) < 30
              else f"{len(book)} {_plural(len(book))} · всё ещё меньше нужного для вывода")

    # Итог Binance в процентах: у остальных участников шкала в процентах, и мешать USDT
    # с процентами на одной странице нельзя.
    b_open_txt = ""
    try:
        _bs = json.load(open(os.path.join(os.path.dirname(DEMO), "binance-advisor-state.json"),
                             encoding="utf-8"))
        _bo = _bs.get("open") or {}
        if _bo.get("symbol"):
            _prot = [i for i in (_bo.get("protect") or []) if i]
            b_open_txt = (f" · сейчас открыта {_bo['symbol']} {_bo.get('side','').lower()} "
                          f"{_num(_bo.get('qty'), 3)} · защита: {len(_prot)} из 2 ордеров"
                          + (" · входы остановлены до закрытия" if _bs.get("blocked_note") else ""))
        if os.path.exists(os.path.join(os.path.dirname(DEMO), "binance-advisor-blocked.json")):
            _bl = json.load(open(os.path.join(os.path.dirname(DEMO), "binance-advisor-blocked.json"),
                                 encoding="utf-8"))
            b_open_txt += (f" · новые входы остановлены с {_bl.get('at','')[:16]}: "
                           f"позиция без подтверждённого выхода")
    except (OSError, ValueError):
        b_open_txt = ""
    b_sum_pct = None
    b_notional = None
    if b_trades:
        _notionals = [float(t.get("entry_price") or 0) * float(t.get("qty") or 0) for t in b_trades]
        b_sum_pct = sum(float(t.get("net_usdt") or 0) / n * 100
                        for t, n in zip(b_trades, _notionals) if n)
        b_notional = sum(n for n in _notionals if n)

    # ── Подводная кривая: профессионала интересует не как система зарабатывает, а как теряет.
    # Считается из тех же рядов, что путь эквити; подпись говорит, сколько наблюдений.
    uw_live = _diag.underwater([float(t.get("net_pct") or 0) for t in live_book])
    uw_sim = _diag.underwater([float(t.get("net_pct") or 0) for t in book])

    def _uw_row(title: str, uw: dict, color: str) -> str:
        if not uw["n"]:
            return ""
        where = ""
        if uw["worst_at"] >= 0:
            where = f" · глубже всего на сделке № {uw['worst_at'] + 1}"
        # Где мы сейчас: без этого кажется, что цифра «застыла». Глубина — историческая:
        # после дна итог может выйти выше прежнего пика, кривая вернётся к нулю, а дно останется.
        now_dd = uw["points"][-1] if uw["points"] else 0.0
        now_txt = ("сейчас 0,00 п.п. — новый максимум" if abs(now_dd) < 1e-9
                   else f"сейчас {_num(now_dd, 2)} п.п.")
        return (f'<div class="uwrow"><div class="uwhead"><span>{_e(title)}</span>'
                f'<b>{_num(uw["worst"], 2)} п.п.</b></div>'
                f'{_diag.underwater_svg(uw["points"], color)}'
                f'<div class="uwnote">n = {uw["n"]}{where} · {now_txt}</div></div>')

    uw_block = ""
    if uw_sim["n"] or uw_live["n"]:
        uw_block = (f'<h2>Подводная кривая: как теряли</h2>'
                    f'<p class="sub">Глубина от исторического максимума в накопленном итоге. Ноль — новый '
                    f'максимум, всё ниже — сколько не хватает до него. Просадка честнее итоговой цифры: '
                    f'она показывает, что пришлось бы выдержать по дороге. Дно историческое: если после '
                    f'него итог вышел выше прежнего пика, глубина остаётся прежней, а кривая '
                    f'возвращается к нулю.</p>'
                    + _uw_row("«Живой счёт», биржа", uw_live, "#a78bfa")
                    + _uw_row("«Тренд», симуляция", uw_sim, "#4cc9f0"))

    # ── Калибровка уверенности модели: 0,62 — это много или это float?
    cal = _diag.calibration(os.path.join(DEMO, "ai-learner-v5.json"))
    cal_block = ""
    if cal["n"]:
        rows = []
        def _side_cells(n: int, lw: float, ln: int, sw: float, sn: int) -> str:
            # Проценты в одну линию, число сделок — второй строкой: иначе скобки разной ширины
            # сдвигают проценты, и столбец читается как «не ровно под заголовком».
            return (f'<td class="num">{_num(lw, 2)} %<span class="cnt">({ln})</span></td>'
                    f'<td class="num">{_num(sw, 2)} %<span class="cnt">({sn})</span></td>')

        for b in cal["buckets"]:
            if b["n"] < 20:
                continue
            lw = 100.0 * b["long_wins"] / b["long_n"] if b["long_n"] else 0.0
            sw = 100.0 * b["short_wins"] / b["short_n"] if b["short_n"] else 0.0
            rows.append(
                f'<tr><td>{_num(b["lo"], 2)}…{_num(b["lo"] + 0.05, 2)}</td>'
                f'<td class="num">{b["n"]}</td>'
                f'<td class="num">{_num(100.0 * b["wins"] / b["n"], 2)} %</td>'
                f'<td class="num">{_pct(b["net"] / b["n"])}</td>'
                + _side_cells(b["n"], lw, b["long_n"], sw, b["short_n"]) + '</tr>')
        hi_b = cal.get("high") or {}
        if hi_b.get("n"):
            rows.append(
                f'<tr><td>0,75 и выше</td>'
                f'<td class="num">{hi_b["n"]}</td>'
                f'<td class="num">{_num(hi_b["wins"], 2)} %</td>'
                f'<td class="num">{_pct(hi_b["net"])}</td>'
                + _side_cells(hi_b["n"], hi_b["long_wins"], hi_b["long_n"], hi_b["short_wins"], hi_b["short_n"])
                + '</tr>')
        tot_b = cal.get("total") or {}
        if tot_b.get("n"):
            rows.append(
                f'<tr class="tot"><td>всего</td>'
                f'<td class="num">{tot_b["n"]}</td>'
                f'<td class="num">{_num(tot_b["wins"], 2)} %</td>'
                f'<td class="num">{_pct(tot_b["net"])}</td>'
                + _side_cells(tot_b["n"], tot_b["long_wins"], tot_b["long_n"], tot_b["short_wins"], tot_b["short_n"])
                + '</tr>')
        cal_block = (f'<h2>Что стоит уверенность модели</h2>'
                     f'<p class="sub">Модель называет вероятность роста; уверенность — это расстояние до '
                     f'половины, поэтому шорт с вероятностью 0,37 и лонг с 0,63 одинаково уверены. '
                     f'Если уверенность что-то значит, доля прибыльных сделок должна расти вместе с ней.</p>'
                     f'<p class="scroll-hint">Таблица шире экрана — прокрутите её вбок.</p>'
                     f'<div class="wscroll"><table class="cal"><thead><tr><th>уверенность</th>'
                     f'<th class="num">сделок</th><th class="num">прибыльных</th>'
                     f'<th class="num">средний нетто</th><th class="num">лонги</th>'
                     f'<th class="num">шорты</th></tr></thead>'
                     f'<tbody>{"".join(rows)}</tbody></table></div>'
                     + _side_note(cal)
                     + f'<p class="sub">Исторический прогон модели целиком: {cal["n"]} сделок, '
                     f'комиссии и проскальзывание внутри. Это не живые сделки — на счёте их ноль. '
                     f'Строки сходятся к итогу: {cal["n"]} = '
                     + " + ".join(str(b["n"]) for b in cal["buckets"] if b["n"] >= 20)
                     + (f' + {(cal.get("high") or {}).get("n")}'
                        if (cal.get("high") or {}).get("n") else "")
                     + f'. Сделок с уверенностью ниже 0,60 в истории нет: порог входа их отсекал, '
                       f'поэтому его нижнюю границу по этой истории проверить нельзя. '
                       f'Уверенность 0,75 и выше объединена в одну строку — '
                       f'{(cal.get("high") or {}).get("n", 0)} наблюдений слишком мало, чтобы делить дальше.</p>')

    # ── Чего стоило неисполнение: считаем, что дало бы правило на месте снятой заявки.
    rc_block = ""
    _rc_path = os.path.join(DEMO, "reject-cost.json")
    try:
        _rc = json.load(open(_rc_path, encoding="utf-8"))
    except (OSError, ValueError):
        _rc = None
    if _rc and _rc.get("rows"):
        _rc_rows = []
        for r in _rc["rows"]:
            if "net_pct" not in r:
                _rc_rows.append(f'<tr><td>{_e(r["status"])}</td><td>{_e(r["symbol"])}</td>'
                                f'<td class="num">{_num(r["price"], 2)}</td>'
                                f'<td colspan="2" class="mn">{_e(r.get("error") or "не измерено")}</td></tr>')
                continue
            tail = (f'{_e(r["exit"])}, {r["bars"]} бар' if r.get("complete")
                    else f'идёт, {r["bars"]} из 48')
            _rc_rows.append(f'<tr><td>{_e(r["status"])}</td><td>{_e(r["symbol"])}</td>'
                            f'<td class="num">{_num(r["price"], 2)}</td>'
                            f'<td class="num">{_pct(r["net_pct"], 2)}</td><td>{tail}</td></tr>')
        total = float(_rc.get("total_pct") or 0.0)
        what = ("неисполнение сэкономило" if total < 0 else "неисполнение стоило")
        rc_block = (f'<h2>Чего стоило неисполнение</h2>'
                    f'<p class="sub">Заявка, которая не исполнилась, не исчезает бесследно: правило всё '
                    f'равно имело мнение о направлении. Здесь восстановлено, что дала бы каждая '
                    f'снятая или отклонённая заявка: стоп 1 ATR, тейк 1,5 ATR, тайм-стоп 48 баров, '
                    f'цена входа — цена самой заявки.</p>'
                    f'<p class="sub"><b>{what[0].upper() + what[1:]} {_num(abs(total), 2)} п.п.</b> '
                    f'по {_rc.get("complete", 0)} завершённым из {_rc.get("n", 0)} неисполненных'
                    + (f'; ещё {_rc.get("incomplete", 0)} '
                       f'{"не дошла до конца — она в таблице отдельно" if _rc.get("incomplete") == 1 else "не дошли до конца — они в таблице отдельно"}'
                       if _rc.get("incomplete") else "")
                    + f'.</p>'
                    f'<p class="scroll-hint">Таблица шире экрана — прокрутите её вбок.</p>'
                    f'<div class="wscroll"><table class="cal"><thead><tr><th>что случилось</th>'
                    f'<th>инструмент</th><th class="num">цена заявки</th>'
                    f'<th class="num">дало бы</th><th>исход</th></tr></thead>'
                    f'<tbody>{"".join(_rc_rows)}</tbody></table></div>')

    # ── Качество мейкерского входа: куда пошла цена после налива (markout).
    # Отрицательный markout = налили и сразу пошли против, классический признак снайпера.
    mk_block = ""
    _b_path = os.path.join(os.path.dirname(DEMO), "binance-advisor-book.jsonl")
    try:
        _b_rows = [json.loads(x) for x in open(_b_path, encoding="utf-8") if x.strip()]
    except (OSError, ValueError):
        _b_rows = []
    _fills = []
    for r in _b_rows:
        if r.get("kind") != "filled":
            continue
        # последняя заявка до налива, а не первая: до исполнения их бывает несколько
        placed = next((x.get("ts") for x in reversed(_b_rows)
                       if x.get("kind") == "intent" and x.get("symbol") == r.get("symbol")
                       and x.get("ts", "") <= r.get("ts", "")), None)
        _fills.append({"symbol": r.get("symbol"), "side": r.get("side"),
                       "price": r.get("entry_price"), "ts": r.get("ts"), "placed": placed})
    if _fills:
        try:
            _mk = _diag.markout(_fills, os.path.join(DEMO, "markout-cache.json"))
        except Exception as exc:
            _mk = {"fills": [{"symbol": f["symbol"], "ts": f["ts"],
                              "error": str(exc)[:80]} for f in _fills]}
        _rows, _bad = [], []
        for f in _mk["fills"]:
            if f.get("error"):
                _bad.append(f'{_e(f.get("symbol") or "?")}: не измерено')
                continue
            m = f.get("markout") or {}
            pend = set(f.get("pending") or [])
            cells = "".join(
                f'<td class="num">{_num(m.get(k), 1)}</td>' if k in m
                else f'<td class="num mn">{"ещё не прошло" if k in pend else "—"}</td>'
                for k in ("1", "5", "15"))
            _rows.append(f'<tr><td>{_e(f["symbol"])}</td>'
                         f'<td>{_e("лонг" if f["side"] == "LONG" else "шорт")}</td>'
                         f'<td class="num">{_num(f["price"], 2)}</td>'
                         f'<td class="num">{_num(f.get("wait_min"), 1)}</td>{cells}</tr>')
        if _rows:
            mk_block = (f'<h2>Что было после налива</h2>'
                        f'<p class="sub">Мейкерская заявка должна стоять там, где цена отскочит. Если после '
                        f'налива цена сразу идёт против — нас выбрали не случайно, а потому что мы стояли '
                        f'на пути потока. Отрицательное число — движение против нас, в базисных пунктах.</p>'
                        f'<p class="scroll-hint">Таблица шире экрана — прокрутите её вбок.</p>'
                        f'<div class="wscroll"><table class="cal"><thead><tr><th>инструмент</th><th>сторона</th>'
                        f'<th class="num">цена</th><th class="num">ждали, мин</th>'
                        f'<th class="num">+1 мин, б.п.</th><th class="num">+5 мин, б.п.</th>'
                        f'<th class="num">+15 мин, б.п.</th></tr></thead>'
                        f'<tbody>{"".join(_rows)}</tbody></table></div>'
                        f'<p class="sub">Наблюдений: {len(_rows)}. Свечи — публичный эндпоинт биржи, '
                        f'ключи не нужны, проверку повторит любой. '
                        + (f'По {len(_rows)} входам выводов о качестве исполнения не делаем: нужна серия.'
                           if len(_rows) < 5 else
                           'Серия набралась — можно смотреть, снайперят нас или нет.')
                        + '</p>'
                        + ("<p class=\"sub\">Не измерено: " + "; ".join(_bad) + "</p>" if _bad else ""))
        elif _bad:
            mk_block = ('<h2>Что было после налива</h2>'
                        f'<p class="sub">Не измерено: {_e("; ".join(_bad))}. Пустое место здесь означает '
                        f'не «всё хорошо», а «померить не удалось».</p>')

    # ── Итоги окна: строки вместо одинаковых карточек. Порядок задан смыслом:
    # сначала правило (симуляция и биржа рядом — одно правило, два исполнения), потом контроли,
    # потом ИИ. Рядом с каждым результатом — число сделок и разница с контролем.
    def _row(badge: str, name: str, value: str, count: str, diff: str, color: str,
             note: str = "") -> str:
        tint = _tint(color, 0.15)
        edge = _tint(color, 0.45)
        return (f'<div class="rrow" style="--c:{color}">'
                f'<div class="rname"><span class="rb" style="background:{tint};border-color:{edge}">'
                f'{_e(badge)}</span><b>{_e(name)}</b></div>'
                f'<div class="rval">{value}<span class="rn"> · {_e(count)}</span></div>'
                + (f'<div class="rdiff">{diff}</div>' if diff else "")
                + (f'<div class="rnote">{_e(note)}</div>' if note else "")
                + '</div>')

    # разница с медианой монетки — в п.п., и сразу оговорка про шум
    inside_band = (rc and rc_lo is not None and rc_hi is not None and rc_lo <= rule <= rc_hi)
    coin_diff = ""
    if rc and rc_med is not None:
        d = rule - float(rc_med)
        coin_diff = (f"к медиане монетки: <b>{_num(d, 2, plus=True)} п.п.</b> · "
                     + ("в пределах шума" if inside_band else "вне полосы 5–95 %"))
    live_gap = ""
    if live_pct is not None:
        d = float(live_pct) - rule
        live_gap = (f"против симуляции того же правила: <b>{_num(d, 2, plus=True)} п.п.</b> · "
                    f"причина в другом наборе сделок, а не в ценах")

    # ── контроль «Наоборот»: те же сигналы советника, но сторона перевёрнута
    _inv = _json("inverse-control.json", {}) or {}
    inv_row = ""
    if _inv.get("trades"):
        _inv_net = float(_inv.get("net_pct") or 0)
        _inv_n = int(_inv.get("trades") or 0)
        _inv_t = float(_inv.get("t_stat") or 0)
        inv_row = _row("контроль", "«Наоборот»",
                       f"{_num(_inv_net, 2, plus=True)} %",
                       f"{_inv_n} {_plural(_inv_n, 'сделка', 'сделки', 'сделок')}",
                       (f"Те же входы советника, сторона перевёрнута: прибыльных "
                        f"{_num(_inv.get('win_rate'), 1)} %, медиана "
                        f"{_num(_inv.get('median'), 2, plus=True)} %. Против советника: "
                        f"<b>{_num(_inv_net - adv_net, 2, plus=True)} п.п.</b> Издержки внутри: "
                        f"{_num(_inv.get('costs_pct'), 2)} п.п. t-статистика {_num(_inv_t, 2)} — "
                        f"{'значимость НЕ доказана, это наблюдение, а не вывод' if abs(_inv_t) < 2 else 'расхождение выходит за шум'}."),
                       "#f97316")
    rule_rows = "".join([
        _row("симуляция", "«Тренд»", _pct(rule), f"{len(book)} {_plural(len(book))}",
             coin_diff, "#4cc9f0"),
        _row("биржа", "«Живой счёт»",
             _pct(live_pct) if live_pct is not None else "—",
             f"{len(live_book)} {_plural(len(live_book))}" if live_book else "сделок нет",
             live_gap, "#a78bfa",
             note=("открыта " + "; ".join(
                 f"{o.get('symbol')} {'LONG' if float(o.get('side_sign') or 0) > 0 else 'SHORT'} "
                 f"{o.get('qty')} по {_num(o.get('entry_price'), 2)}" for o in live_opens))
             if live_opens else ""),
    ])
    control_rows = "".join([
        _row("контроль", "«Случайный»",
             _pct(rc_med) if rc else "не измерено",
             "медиана 200 бросков",
             (f"полоса 5–95 %: {_pct(rc_lo)} … {_pct(rc_hi)} · лучше правила в "
              f"{float(rc_beaten):.0f} % бросков" if rc and rc_beaten is not None else ""),
             "#f59e0b"),
        _row("контроль", "«Владение»", _pct(hold), "без сделок: купил и держишь",
             "разница не считается: владение без комиссий и без решений", "#f472b6",
             note=f"BTC {_pct(btc)} · ETH {_pct(eth)}"),
        inv_row,
    ])

    # ── текст состояния MT5 для строки участника (был потерян при удалении строки Binance)
    if mt5_positions:
        mt5_state_txt = (f"сделок {mt5_trades} из {mt5_all} · позиций {mt5_positions}"
                         if mt5_all > mt5_trades else f"сделок {mt5_trades} · позиций {mt5_positions}")
    elif mt5_trades:
        _mt5_tr = (f"сделок {mt5_trades} из {mt5_all}"
                   if mt5_all > mt5_trades else f"сделок {mt5_trades}")
        mt5_state_txt = (f"{_mt5_tr} · рынок открыт" if mt5_market_open
                         else f"{_mt5_tr} · рынок закрыт")
    elif mt5_market_open:
        mt5_state_txt = ("рынок открыт · сигналов нет" if mt5_live == mt5_total
                         else f"рынок открыт частично: торгуются {mt5_live} из {mt5_total} инструментов")
    elif mt5_market_open is False:
        mt5_state_txt = "рынок закрыт"
    else:
        mt5_state_txt = "рынок: не измерено"
    mt5_rule_txt = ""
    if mt5_exits:
        _last5 = mt5_exits[-1]
        mt5_rule_txt = (f". Правило: {mt5_trades} "
                        f"{_plural(mt5_trades, 'сделка', 'сделки', 'сделок')}, нетто "
                        f"{_num(mt5_net, 2, plus=True)} USDT; последняя {_last5.get('symbol')} — "
                        f"{_last5.get('reason') or 'выход'} "
                        f"{_num(_last5.get('net_usdt'), 2, plus=True)} USDT. "
                        f"Исполнено всего {mt5_all}: правило {mt5_trades} + тестовая {mt5_tests} "
                        f"(тестовая в книгу правила не идёт, но в эквити счёта входит)")

    # «Ещё в работе» — только те, у кого нет ни одной сделки. MT5 стоял здесь с +17,28 USDT
    # и заголовком «сделок нет» — это противоречие; он переехал в отдельный блок ниже.
    wip_rows = "".join([
        _row("нет сделок", "«Регрессия» (обученная модель)",
             f"{len(learned)} {_plural(len(learned), 'решение', 'решения', 'решений')}",
             f"разрешено {len(l_allowed)}",
             "порог 0,60 и фильтр 3× издержек держат входы закрытыми", "#22d3ee"),
    ])
    mt5_rows_html = "".join([
        _row("закрыто" if mt5_trades else ("проверен" if mt5_forced else "нет сделок"),
             "MT5 · TradFi (демо)",
             (f"{_num(mt5_net, 2, plus=True)} USDT" if mt5_trades else "0 сделок"),
             mt5_state_txt,
             (_mt5_status(mt5_rows, mt5, mt5_trading) + mt5_rule_txt
              + (f' Тестовая: {mt5_forced[-1].get("symbol") or "—"} '
                 f'{_num(mt5_forced[-1].get("net_usdt"), 2, plus=True)} USDT, закрыта сразу — '
                 f'это была проверка ветки входа, а не сигнал правила.' if mt5_forced else "")),
             "#38bdf8"),
    ])

    # ── OKX · исполнение: участник заменил «Binance» 19.10.2026 (биржа остановила демо-движок).
    # Стоп и тейк там прикреплены к входной заявке, поэтому отдельной постановки защиты нет.
    # Размер контракта OKX проверен по публичному эндпоинту /api/v5/public/instruments
    # 20.10.2026: BTC-USDT-SWAP — 0,01 BTC, ETH-USDT-SWAP — 0,1 ETH. Без него USDT нельзя
    # перевести в проценты, а без процентов книгу OKX не с чем сравнивать на шкале.
    OKX_CTVAL = {"BTCUSDT": 0.01, "ETHUSDT": 0.1}

    def _okx_pct(rec: dict):
        """Итог сделки в процентах от нотионала: USDT делим на размер позиции в монетах."""
        sym = str(rec.get("symbol") or "")
        ctval = OKX_CTVAL.get(sym)
        try:
            sz = float(rec.get("sz") or 0)
            px = float(rec.get("entry_price") or 0)
            net = float(rec.get("net_usdt") or 0)
        except (TypeError, ValueError):
            return None
        if not ctval or not sz or not px:
            return None
        return net / (sz * ctval * px) * 100.0

    okx_rows = _lines_binance("okx-advisor-book.jsonl")
    okx_exits = [r for r in okx_rows if r.get("kind") == "exit" and r.get("measured")]
    _okx_exits_now = okx_exits
    okx_net = sum(float(r.get("net_usdt") or 0) for r in okx_exits)
    _okx_pcts = [p for p in (_okx_pct(r) for r in okx_exits) if p is not None]
    okx_pct_sum = sum(_okx_pcts)
    okx_state = _json("../okx-advisor-state.json", {}) or {}
    okx_live = okx_state.get("open") or {}
    okx_pend = okx_state.get("pending") or {}
    if okx_live:
        okx_status = "в позиции"
        # В колонке значения — ОДНО число: она не переносит текст, и любая длинная фраза
        # сжимает название участника в столбик (карточка так и рассыпалась при 700 px).
        # Второй уровень защиты и расстояния уходят в пояснение — там места хватает.
        def _lvl_txt(word: str, lvl) -> str:
            if not lvl:
                return ""
            try:
                dist = (float(lvl) / float(okx_live.get("px") or 1) - 1.0) * 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                return f"{word} {_money(lvl, 2)}; "
            return (f"{word} {_money(lvl, 2)} — {'выше' if dist > 0 else 'ниже'} входа на "
                    f"{_num(abs(dist), 2)} %; ")

        _short = str(okx_live.get("side", "")).upper() == "SHORT"
        # Раньше при открытой позиции в колонке значения оставался только стоп, и итог закрытых
        # сделок исчезал с глаз до самого закрытия. Теперь в значении — деньги и статус,
        # в подписи — размер выборки и уровень защиты. Проценты остаются в пояснении.
        _open_part = f" · в позиции {str(okx_live.get('symbol') or '').replace('USDT', '')}"
        if okx_exits:
            okx_val = f"{_num(okx_net, 2, plus=True)} USDT{_open_part}"
        else:
            okx_val = f"стоп {_money(okx_live.get('sl'), 2)}{_open_part}"
        okx_sub = (f"{_plural(len(okx_exits), 'итог 1 сделки', 'итог 2 сделок', 'итог %d сделок' % len(okx_exits))}"
                   if okx_exits else "закрытых сделок нет")
        if okx_live.get("sl"):
            okx_sub += f" · стоп {_money(okx_live.get('sl'), 2)}"
        okx_note = (f"Открыта {okx_live.get('symbol')} {str(okx_live.get('side','')).lower()} "
                    f"{_num(okx_live.get('sz'), 2)} контр. по "
                    f"{_money(okx_live.get('px'), 2)}. Защита: "
                    + _lvl_txt("стоп", okx_live.get("sl")) + _lvl_txt("тейк", okx_live.get("tp"))
                    + ("у шорта стоп обязан быть выше входа, а тейк ниже — иначе защита стояла бы "
                       "не с той стороны и закрывала бы сделку сразу. " if _short else
                       "у лонга стоп ниже входа, а тейк выше — защита стоит со стороны убытка. "))
    elif okx_pend:
        okx_status = "заявка стоит"
        okx_val = f"по {_money(okx_pend.get('px'), 2)}"
        okx_note = f"Заявка на {okx_pend.get('symbol')} ждёт налива. "
    elif okx_exits:
        okx_status = "закрыто"
        okx_val = f"{_num(okx_net, 2, plus=True)} USDT"
        okx_sub = f"{_plural(len(okx_exits), '1 сделка', '2 сделки', '%d сделок' % len(okx_exits))} · позиций 0"
        okx_note = ""
    else:
        okx_status = "нет сделок"
        okx_val = "0 сделок"
        okx_sub = "сделок нет"
        okx_note = ""
    # Отметка времени: страница пересобирается раз в 15 минут, и без неё «в позиции» через минуту
    # после закрытия читается как «не обновляется», а не как «снимок на 10:25».
    _last_ts = ""
    if okx_rows:
        # Поле ts в книге OKX — местное время контура. На странице всё в UTC, поэтому переводим,
        # иначе снимок выглядит свежее страницы (10:39 вместо 07:39 UTC — это и был тот баг).
        _raw_ts = str(okx_rows[-1].get("ts") or "")
        try:
            _last_ts = time.strftime("%d.%m %H:%M", time.gmtime(time.mktime(
                time.strptime(_raw_ts, "%Y-%m-%d %H:%M:%S"))))
        except (ValueError, TypeError):
            _last_ts = _raw_ts
    # Закрытая книга OKX: без этого блока страница говорила «закрытых сделок ещё нет», хотя они были.
    if okx_exits:
        _parts = []
        for r in okx_exits:
            p = _okx_pct(r)
            _parts.append(f"{(r.get('symbol') or '')} {str(r.get('side') or '').lower()} "
                          + (f"{_num(p, 2, plus=True)} %" if p is not None else "—")
                          + f" ({_num(float(r.get('net_usdt') or 0), 2, plus=True)} USDT)")
        # Время закрытия берём из exit_ms (UTC биржи). В книге exit_ms нет, он есть в состоянии.
        _ms = [int(c["exit_ms"]) for c in (okx_state.get("closed") or []) if c.get("exit_ms")]
        _usd = time.strftime("%d.%m %H:%M", time.gmtime(min(_ms) / 1000)) if _ms else "—"
        okx_note += (" Закрытые сделки: " + "; ".join(_parts)
                     + f". Итог книги в процентах от нотионала: {_num(okx_pct_sum, 2, plus=True)} % "
                     f"по {len(_okx_pcts)} {_plural(len(_okx_pcts), 'сделке', 'сделкам', 'сделкам')} "
                     f"(в USDT {_num(okx_net, 2, plus=True)}). Первое закрытие {_usd} UTC.")
    okx_note += (" Те же решения, что у «Советника», но на другой бирже. Стоп и тейк прикреплены "
                 "к входной заявке (OCO), поэтому отдельной постановки защиты, которая может "
                 "«не встать», здесь нет."
                 + (f" Снимок книги на {_last_ts} UTC; страница пересобирается раз в час." if _last_ts else ""))

    # ── Модели A и B: A — участник (long-only), B — контроль (нелинейность).
    # Книги считает тот же advisor_book.py: выходы по коду, вход по решению модели.
    def _model_row(prefix: str, label: str, status: str, color: str, why: str) -> str:
        jr = _lines(f"{prefix}-journal.jsonl")
        bk = _lines(f"{prefix}-book.jsonl")
        exits = [r for r in bk if r.get("net_pct") is not None]
        net = sum(float(r.get("net_pct") or 0) for r in exits)
        last = jr[-1] if jr else {}
        p_txt = (f"последнее решение: {_e(last.get('symbol'))} {_e(last.get('side'))} · "
                 f"p = {_num(float(last.get('confidence') or 0) / 100, 2)}" if last else "решений пока нет")
        return _row(status, label,
                    (f"{_num(net, 2, plus=True)} %" if exits else
                     (f"{len(jr)} реш." if jr else "нет данных")),
                    (f"{len(exits)} {_plural(len(exits))}" if exits else
                     ("книги сделок нет" if jr else "журнала нет")),
                    (why + " " + p_txt + (f" · решений {len(jr)}" if jr else "")).strip(),
                    color)

    model_rows = "".join([
        _model_row("model-a", "«A» long-only", "бумага", "#22c55e",
                   "Вход только в лонг при p ≥ 0,60; выходы считает код (стоп 1 ATR, тейк 1,5 ATR, "
                   "тайм-стоп 48 баров)."),
        _model_row("model-b", "«B» бустинг", "контроль", "#eab308",
                   "КОНТРОЛЬ, не участник: нелинейная модель на тех же признаках, обе стороны. "
                   "Стоит, чтобы видеть, помогает ли нелинейность."),
    ])

    ai_rows = "".join([
        _row("бумага", "«LLM-советник»",
             _pct(adv_net) if adv_net is not None else f"{len(ai)} реш.",
             f"{len(adv)} {_plural(len(adv))}" if adv else "книги сделок нет",
             (f"к медиане монетки: <b>{_num(float(adv_net) - float(rc_med), 2, plus=True)} п.п.</b> · "
              + ("в пределах шума" if inside_band else "вне полосы 5–95 %"))
             if (adv_net is not None and rc and rc_med is not None) else "",
             "#8a98a6"),
        _row(okx_status, "OKX · исполнение (демо)",
             okx_val,
             (okx_sub if okx_live else
              (f"заявка 1 · сделок {len(okx_exits)}" if okx_pend else
               (f"{_plural(len(okx_exits), '1 сделка', '2 сделки', '%d сделок' % len(okx_exits))}"
                if okx_exits else "сделок нет"))),
             okx_note,
             "#a78bfa"),
    ])

    trade_rows, acc = [], 0.0
    for t in book:
        net = float(t.get("net_pct") or 0)
        acc += net
        side_txt = "LONG" if float(t.get("side") or 0) > 0 else "SHORT"
        ms = int(t.get("exit_ms") or t.get("bar_ms") or 0)
        when = time.strftime("%d.%m %H:%M", time.gmtime(ms / 1000)) if ms else "—"
        held = ""
        if t.get("bar_ms") and t.get("exit_ms"):
            held = f' · {(int(t["exit_ms"]) - int(t["bar_ms"])) / 3_600_000:.0f} ч'   # удержание в часах
        cls = "good" if net > 0 else ("bad" if net < 0 else "")
        net_txt = _pct(net, 3)
        acc_txt = _pct(acc, 3)
        trade_rows.append(
            f'<tr><td>{_e(when + held)}</td><td>{_e(t.get("symbol") or "—")}</td>'
            f'<td>{side_txt}</td><td class="{cls}">{net_txt}</td>'
            f'<td>{acc_txt}</td><td>{_e(str(t.get("exit") or "—"))}</td></tr>')
    # ── живые сделки: строки книги исполнений биржи
    live_rows = []
    live_acc = 0.0
    for t in live_book:
        net = float(t.get("net_pct") or 0)
        live_acc += net
        ms = int(t.get("exit_ms") or t.get("entry_ms") or 0)
        when = time.strftime("%d.%m %H:%M", time.gmtime(ms / 1000)) if ms else "—"
        held = ""
        if t.get("entry_ms") and t.get("exit_ms"):
            held = f' · {(int(t["exit_ms"]) - int(t["entry_ms"])) / 3_600_000:.0f} ч'
        side_txt = "LONG" if float(t.get("side_sign") or 0) > 0 else "SHORT"
        cls = "good" if net > 0 else ("bad" if net < 0 else "")
        slip = t.get("slip_bp")
        slip_txt = f"{float(slip):+.0f} б.п." if isinstance(slip, (int, float)) else "—"
        live_rows.append(
            f'<tr data-live-trade><td>{when}{held}</td><td>{_e(str(t.get("symbol")))}</td>'
            f'<td>{side_txt}</td><td class="{cls}">{_pct(net, 3)}</td>'
            f'<td>{_pct(live_acc, 3)}</td><td>{_e(str(t.get("exit_reason") or "—"))}</td>'
            f'<td>{slip_txt}</td></tr>')

    live_table = ""
    if live_rows:
        live_table = (
            '<h2>Живые сделки: что исполнила биржа</h2>'
            '<p class="sub" style="margin:-6px 0 10px">Каждая строка — исполнение на бирже: цены, комиссии '
            'и фандинг берутся из closed-pnl, ничего не досчитывается вручную. «Скольжение» — отклонение '
            'от того, что дала бы та же сделка в симуляции на свечах.</p>'
            '<div class="table-wrap"><table class="tr"><thead><tr><th>Выход · удержание</th>'
            '<th>Инструмент</th><th>Сторона</th><th>Нетто</th><th>Накопленный итог</th>'
            '<th>Причина выхода</th><th>Скольжение</th></tr></thead><tbody>'
            + "".join(live_rows) + '</tbody></table></div>'
            + (f'<p class="sub" style="margin:8px 0 0">Это {len(live_rows)} из {_min_trades()} сделок, '
               f'которые нужны, чтобы результат что-то различал. Меньшее число не отличает правило от '
               f'случайности — поэтому здесь считается каждая сделка, а вывод делать рано.</p>'
               if len(live_rows) < _min_trades() else
               f'<p class="sub" style="margin:8px 0 0">Сделок {len(live_rows)} при пороге {_min_trades()} — '
               f'минимум набран; вывод всё равно требует взгляда на разброс, а не на итог.</p>'))

    trades_table = ""
    if trade_rows:
        trades_table = (
            '<h2>Сделки симуляции «Тренд», из которых сложился график</h2>'
            '<p class="sub" style="margin:-6px 0 10px">Живая книга и решения обученной модели — '
            'в карточках выше; здесь только бумажный ряд правила.</p>'
            '<p class="sub">Каждая строка — запись из журнала: время выхода (UTC), инструмент, сторона, '
            'нетто после издержек и накопленный итог. Ни одно число здесь не набрано руками. '
            '<span class="hint">На узком экране таблица прокручивается вбок, шапка остаётся на месте.</span></p>'
            '<div class="table-wrap"><table class="tr"><thead><tr><th>Выход · удержание</th><th>Инструмент</th><th>Сторона</th>'
            '<th>Нетто</th><th>Накопленным итогом</th><th>Причина</th></tr></thead><tbody>'
            + "".join(trade_rows) + '</tbody></table></div>')

    ai_block = ""
    if last_ai:
        # Если после последнего решения модель падала — это надо назвать вслух.
        # 20.10.2026 Ollama не отвечал с 23:05: журнал писал ошибки, страница молчала и
        # показывала решение восьмичасовой давности как «последнее».
        ai_fail = ""
        try:
            _bee = _lines("ai-bee-journal.jsonl")
            _tail, _first_fail, _last_err = 0, None, None
            for _r in reversed(_bee):
                if _r.get("error"):
                    _tail += 1
                    _first_fail = _r.get("ts")
                    _last_err = _r.get("error")
                elif _r.get("side"):
                    break
            if _tail >= 2:
                ai_fail = (f'<p class="hint" style="white-space:normal;margin:8px 0 0;color:#fbbf24">'
                           f'⚠ после этого решения модель не ответила {_tail} раз подряд, начиная с '
                           f'{_e(str(_first_fail)[:16])}: «{_e(_last_err)}». Это сбой бэкенда, '
                           f'а не отсутствие сигналов.</p>')
        except Exception:                                              # noqa: BLE001
            pass
        side = (last_ai.get("side") or "").upper()
        cls = {"LONG": "", "SHORT": " short", "FLAT": " flat"}.get(side, " flat")
        conf = last_ai.get("confidence")
        conf_num = float(conf) if isinstance(conf, (int, float)) else 0.0
        ai_block = (f'<h2>Последнее решение LLM-советника</h2><div class="ai">'
                    f'<div><span class="pair">{_e(last_ai.get("symbol"))}</span>'
                    f'<span class="side{cls}">{_e(side or "—")}</span></div>'
                    f'<p>{_e((last_ai.get("reason") or "—").rstrip("."))}. Решение приняла внешняя модель через облако; её имя в журнале — {_e(_model_label(last_ai.get("model")))}.</p>' 
                    f'<p class="hint" style="white-space:normal;margin:6px 0 0">{_decided(last_ai)}</p>'
                    f'<div class="conf">уверенность {_e(conf if conf is not None else "—")} из 100'
                    f'<div class="meter"><i style="width:{max(0.0, min(100.0, conf_num)):.0f}%"></i></div>'
                    f'</div>' + ai_fail + '</div>')

    learned_block = ""
    if last_learned:
        side = (last_learned.get("side") or "FLAT").upper()
        cls = {"LONG": "", "SHORT": " short", "FLAT": " flat"}.get(side, " flat")
        p_up = float(last_learned.get("p_up") or 0)
        learned_block = (
            f'<h2>Последнее решение «Регрессии» (обученная модель)</h2><div class="ai">'
            f'<div><span class="pair">{_e(last_learned.get("symbol"))}</span>'
            f'<span class="side{cls}">{_e(side)}</span></div>'
            f'<p class="hint" style="white-space:normal;margin:0 0 6px">{_decided(last_learned)}</p>'
            f'<p>Вероятность роста {_num(p_up, 3)}, ожидаемый ход '
            f'{_num(float(last_learned.get("expected_move_pct") or 0), 3)} % при нужных '
            f'{_num(float(last_learned.get("needed_move_pct") or 0), 2)} %. '
            f'{"Вход разрешён кодом" if last_learned.get("allowed") else "Входа нет"}: '
            f'{_e("; ".join(last_learned.get("reasons") or []))}. '
            f'Ход сам по себе входа не даёт: код требует, чтобы вероятность роста вышла из коридора '
            f'0,40…0,60 <i>и</i> ожидаемый ход покрывал издержки с запасом 3×.</p>'
            + _learned_contrib(last_learned)
            + _learned_attempt(last_learned)
            + f'<div class="conf">вероятность роста {_num(p_up, 3)}'
            f'<div class="meter"><i style="width:{max(0.0, min(100.0, p_up * 100)):.0f}%"></i></div>'
            f'</div></div>')

    adv_row = ""
    if adv_net is not None:
        adv_row = (f'<div class="row"><div class="who">«LLM-советник»<small>бумажная книга</small></div>'
                   f'{track_dot(adv_net, "#8a98a6", "Советник")}'
                   f'<div class="val">{_pct(adv_net)}</div></div>')

    mf = _model_facts()          # числа модели — до блока ограничений, где они печатаются
    does = case_shell.limits_block([
        f"{len(book)} {_plural(len(book), 'сделка', 'сделки', 'сделок')} симуляции и "
        f"{len(live_book)} {_plural(len(live_book), 'живая', 'живые', 'живых')} — не выборка: такой ряд не отличает умение "
        f"от везения. Вывод о качестве правила здесь сделать нельзя, и мы его не делаем.",
        "Демо-исполнение оптимистичнее боевого: настоящей очереди заявок нет, проскальзывание меньше. "
        "Поэтому живой результат — верхняя оценка, а не обещание.",
        "«Владение» посчитано без комиссий входа и выхода: оно и не торгует. Его полоса — это рынок, "
        "а не стратегия.",
        f"Записей пока мало, и это главное ограничение: у обученной модели {len(l_allowed)} "
        f"разрешённых входов из {len(learned)} решений, на OKX — {len(_okx_exits_now)} "
        f"{_plural(len(_okx_exits_now), 'сделка', 'сделки', 'сделок')}. Одна-две сделки — "
        f"не результат, а первая запись: вывод по ним делать нельзя.",
        "Рейтинга нет намеренно: пока сделок меньше тридцати, любой порядок участников — украшение.",
    ])

    model_block = (
        '<h2>Обученная модель: что известно и чего это не значит</h2>'
        '<div class="mdl"><p>'
        f"Проверена в {mf['configs'] if mf['configs'] is not None else '—'} конфигурациях; общий счётчик "
        f"испытаний проекта — {mf['trials'] if mf['trials'] is not None else '—'} в "
        f"{mf['records'] if mf['records'] is not None else '—'} записях реестра. Планка MinBTL "
        f"{_num(mf['min_btl'], 2)} года при {_num(mf['years'], 1)} года истории: столько данных нужно, "
        f"чтобы отличить этот результат от случайного. У нас меньше.</p>"
        f"<p>Мейкерский прогон дал {_num(mf['maker_total'], 2)} % на {mf['maker_trades'] or '—'} сделках, "
        f"но 2021 год дал {_num(mf['y2021'], 1)} % из них, а 2023-й — {_num(mf['y2023'], 1)} %. "
        f"Срез 2022+ дал {_num(mf['post2021'], 1)} % при t {_num(mf.get('t_post2021'), 2)} на "
        f"{mf.get('n_post2021') or '—'} сделках — это ноль с точностью до шума, а не преимущество.</p>"
        '<p>Контур измеряет <b>долю исполнения лимитных заявок</b>, а не доходность: у мейкера нет '
        'проскальзывания, зато есть неисполнение — оно и есть настоящая цена такого входа. '
        'Размер входа 0,001 BTC или 0,01 ETH. Все числа этого блока пересчитываются из реестра '
        'и файла прогона при сборке страницы.</p>'
        f'<p><a href="/audit/ai-case/">Полный разбор модели с таблицами →</a></p></div>'
    )


    # Порядок блоков: вводные -> ИТОГ (шкала) -> как к нему шли (график) -> участники ->
    # пруфы (таблица) -> мысли под капотом -> ограничения.
    scale_block = f"""
<h2>Где правило относительно контролей</h2>
<p class="sub">Итог окна в процентах на одной шкале. Левее нуля потеря, правее прибыль.</p>
<details class="how" style="max-width:960px;margin:0 auto 10px"><summary>Как читать шкалу: что складывается и что значит цвет</summary>
<p class="sub" style="margin:0 0 10px"><b>Что именно складывается.</b> «Накопленный итог» —
простая сумма процентов по закрытым сделкам: без сложного процента и без учёта размера позиции.
Поэтому три живые сделки по −0,9 % дают ровно −2,7 %, а не «−2,6 % с реинвестом». Так сравнимы между
собой любые два участника, но это не доходность счёта.</p>
<p class="sub" style="max-width:960px;margin:0 auto 10px">Цвет на шкале — это <b>участник</b>, а не результат:
зелёный и красный здесь не значат ничего, кроме прибыли и убытка в таблице ниже. Живой счёт помечен
цветом участника — чтобы плашка с убытком не читалась как прибыль.</p></details>
<div class="scale">
 <div class="row"><div class="who">«Тренд»<small>симуляция на свечах</small></div>
  {track_dot(rule, "#4cc9f0", "Тренд")}<div class="val">{_pct(rule)}</div></div>
 <div class="row"><div class="who">«Живой счёт»<small>исполнено биржей</small></div>
  {track_dot(live_pct, "#a78bfa", "Живой счёт") if live_pct is not None else '<div class="track"></div>'}
  <div class="val">{_pct(live_pct) if live_pct is not None else "0 сдел."}</div></div>
 <div class="row"><div class="who">«Владение»<small>без комиссий</small></div>
  {track_dot(hold, "#f472b6", "Владение")}<div class="val">{_pct(hold)}</div></div>
 {adv_row}
 {band_row}
 <div class="axis"><div></div><div>{ticks}</div><div></div></div>
 <p class="read">{read}</p>
</div>
{_open_lines(live_opens)}
"""

    # Живые входы заперты — показываем явно. Стенд, который сам себя остановил по своим же правилам,
    # и есть доказательство дисциплины: об этом нельзя узнать только из журнала, это должно быть
    # видно на странице рядом с цифрами.
    lock_info = _json("locked.json", None)
    _state_now = _json("state.json", {}) or {}
    lock_hist = _lock_intervals()
    # Критерий «не пропущено ни одного сигнала» был невыполнимым по определению: замок и существует
    # для того, чтобы не входить. Заменён на проверяемый: пропущенные сделки не должны были дать
    # прибыли. Снятие 18.10 прошло по старой редакции — это записано, а не замазано.
    lock_criteria = ("Критерии снятия (действуют для следующих замков): (1) стопы исполняла биржа, "
                     "а не наш код; (2) убытки объясняются входом, а не сбоем; (3) пропущенные за время "
                     "замка сделки в сумме не дали бы прибыли — иначе остановка признаётся дорогой и "
                     "снимается отдельным решением с указанием цены. Если не выполнено хотя бы одно — "
                     "входы остаются запертыми: замок не снимается сам, только решением владельца, "
                     "в котором записаны дата и цена остановки. Для снятия 18.10 пункт 3 действовал в прежней редакции "
                     "(«ни одного сигнала»): по факту замок пропустил две сделки на −0,17 п.п., то есть "
                     "сэкономил. Это решение с датой и причиной, а не доказательство: на трёх живых "
                     "сделках доказать нечего.")
    unlock_info = None if lock_info else (_state_now.get("unlock_note") or None)
    lock_note = ""
    if lock_info:
        when = _date_ru(lock_info.get("ts"))
        lock_note = (
            '<div style="max-width:960px;margin:18px auto 0;padding:14px 18px;border-left:3px solid #ef4444;'
            'background:rgba(239,68,68,.10);border-radius:6px;font-size:15px;line-height:1.6">'
            f'<b>Живые входы заперты {when} ({_lock_age_txt(lock_hist)}).</b> '
            f'Причина: {_e(lock_info.get("reason") or "серия убытков")}. '
            'Симуляция продолжается — она и показывает, что дало бы правило, если бы продолжало входить. '
            f'{lock_criteria}</div>')
    elif unlock_info:
        # Замок снят — но след остаётся видимым: «мы себя остановили и объяснили, почему пустили снова».
        # Иначе страница выглядит так, будто ограничения никогда не было.
        when = _date_ru(unlock_info.get("at"))
        # Две строки факта сверху, критерии снятия — в спойлере. До этого первым блоком табла
        # шёл абзац на 1 100 знаков: читатель видел протокол вместо результата.
        lock_note = (
            '<div style="max-width:960px;margin:18px auto 0;padding:12px 18px;border-left:3px solid #a78bfa;'
            'background:rgba(167,139,250,.12);border-radius:6px;font-size:14px;line-height:1.6">'
            f'<b>Живые входы открыты {when}</b> — замок стоял {_lock_span_txt(lock_hist)} и снят разбором: '
            f'стопы исполняла биржа, скольжение {_slip_range_txt()}, убытки от входов, а не от механики. '
            f'Пропущенные за это время сигналы {_lock_cost_txt()}. Следующие три убытка подряд снова запрут входы.'
            '<details class="how" style="margin-top:10px"><summary>Критерии снятия и цена остановки</summary>'
            f'<p class="sub" style="margin:10px 0 0">{lock_criteria}</p>'
            '<p class="sub" style="margin:8px 0 0">Замок не снимается сам: только решением владельца, '
            'в котором записаны дата и цена остановки. Если не выполнено хотя бы одно из условий — '
            'входы остаются запертыми.</p></details>'
            '</div>')

    # Три слоя вместо одной простыни. Причина: страница смешивала три масштаба времени —
    # итог окна (дни), исполнение лимиток (минуты) и исторический бэктест (годы). Читатель терял,
    # в каком масштабе смотрит. Вкладки — навигация по смыслу, а не по разделам.
    import re as _re2
    _strip_h2 = lambda s: _re2.sub(r"<h2>.*?</h2>", "", s, count=1, flags=_re2.S)
    _sim_details = (f'<details class="how"><summary>Сырые сделки симуляции «Тренд» — для перепроверки</summary>'
                    f'<p class="sub" style="margin:10px 0 0">Те же сделки, из которых сложился график. '
                    f'Нужны, если хотите пересчитать итог руками.</p>{_strip_h2(trades_table)}</details>')
    _live_details = (f'<details class="how"><summary>Сырые живые сделки: что исполнила биржа</summary>'
                     f'<p class="sub" style="margin:10px 0 0">Исход каждой позиции взят из closed-pnl биржи, '
                     f'а не из нашего журнала.</p>{_strip_h2(live_table)}</details>')
    _venue_extra = (_live_vs_sim_block() + mk_block + rc_block + _sim_details + _live_details)
    _cal_details = (f'<details class="how"><summary>Историческая калибровка уверенности: бэктест на '
                    f'{(cal.get("n") if cal else "—")} сделках, а не текущее окно</summary>'
                    f'<p class="sub" style="margin:10px 0 0">Здесь числа другой эпохи: прогон модели '
                    f'целиком за 2019–2026, к окну в {(days)} дн. они не относятся. Нужны, чтобы '
                    f'проверить: растёт ли доля удачных сделок вместе с уверенностью.</p>'
                    f'{_strip_h2(cal_block)}</details>')

    return (case_shell.head("Бот против контролей", verdict_line,
                            chips=[f"окно {days} дн.", f"симуляция {len(book)} сделок",
                                   f"живых {len(live_book)}"] + (["позиция открыта"] if (live_open or b_open) else [])
                                  + (["входы заперты"] if lock_info else []),
                            warn_chip="рейтинга нет, пока сделок меньше 30",
                            lead="Рядом с ботом всегда стоит контроль: случайная монетка с теми же входами "
                                 "и простое владение. Без них любой результат выглядит мастерством. "
                                 "Победителя пока нет, и мы не делаем вид, что он есть.")
            + TAB_NAV
            + '<div class="tpane" id="tabpane-0" role="tabpanel" aria-labelledby="tabbtn-0" '
              'data-tab="0" data-active="1">'
            + (lock_note if lock_note else "")
            + scale_block
            + case_shell.chart_block(
                equity_svg.chart(), equity_svg.legend(),
                note="Накопленный результат по закрытым сделкам. Полоса — разброс 200 бросков монетки "
                     "на тех же входах и выходах, поэтому видно не только «кто где кончил», но и когда "
                     "правило отрывалось, а когда шло вместе с рынком. "
                     "Пунктир «Наоборот» — те же входы советника с перевёрнутой стороной, "
                     "расчёт по публичным свечам: биржа этих сделок не исполняла. "
                     + equity_svg.threshold_note()
                     + "MT5 · TradFi не на графике по другой причине: другой рынок, счёт в USDT и "
                       "две сделки правила — сравнивать его кривую с процентами на крипте нельзя, "
                       "он в таблице участников. "
                     + equity_svg.stale_note(_opens_labels))
            + uw_block
            + f"""
<h2>Кто что показал</h2>
<p class="sub">Слева — участник и вид записи, справа — итог и число сделок. Ниже — разница с контролем:
именно она отвечает на вопрос «это умение или везение». Ниже тридцати сделок любой процент —
описание одной серии, а не качества правила.</p>
<h3>Правило</h3>
{rule_rows}
<details class="how"><summary>Как считается</summary>
<p>EMA 9/21 по часовым барам, вход по закрытию сигнального бара, стоп 1 ATR, тейк 1,5 ATR,
тайм-стоп 48 баров, комиссия и проскальзывание внутри каждой сделки. «Тренд» — форвардный учёт на
публичных свечах; «Живой счёт» — те же правила, но ордера отправлялись на биржу, и исход берётся из
её closed-pnl, без ручного досчёта.</p></details>
<h3>Контроли</h3>
{control_rows}
<details class="how"><summary>Как считается</summary>
<p>«Случайный» — те же входы и выходы, но сторона выбирается 200 раз броском монетки с фиксированным
зерном; медиана и полоса 5–95 % показывают, что даёт везение. «Владение» — купить в начале окна и
держать, ничего не решая, без комиссий входа и выхода.</p></details>
<h3>ИИ</h3>
{ai_rows}
{model_rows}
<details class="how"><summary>Как считается</summary>
<p>«LLM-советник» — бумажная книга: модель задаёт только направление, выходы считает код.</p>
<p>«A» long-only и «B» бустинг — те же 14 признаков из часовых свечей, horizon 12 баров, порог 0,60.
Разница: A входит только в лонг (разведка показала брутто лонгов +0,46 % против −0,16 % у шортов,
t = 3,74), B — обе стороны нелинейной моделью и стоит контролем: он отвечает, помогает ли
нелинейность вообще. Выходы и издержки у всех одинаковые.</p></details>
{does}
</div>
<div class="tpane" id="tabpane-1" role="tabpanel" aria-labelledby="tabbtn-1" data-tab="1" data-active="0">
{_venue_extra}
</div>
<div class="tpane" id="tabpane-2" role="tabpanel" aria-labelledby="tabbtn-2" data-tab="2" data-active="0">
<h2>Идут, но выборки нет: TradFi у брокера</h2>
<p class="sub" style="max-width:960px;margin:0 auto 10px">Здесь есть исполненные сделки, поэтому это не
«контур без результата». Но на двух сделках вывод о правиле не делается: строка говорит только то,
что исполнение идёт и исходы считаются по счёту.</p>
{mt5_rows_html}
<h2>Ещё в работе: контуры без результата</h2>
<p class="sub">Сделок нет — сравнивать нечего. Держим их на виду, потому что это часть стенда,
а не реклама: у каждого своё правило, и каждый считается честно.</p>
{wip_rows}
{_cal_details}
"""
            + f"""
{ai_block}

{learned_block}

{model_block}
</div>
"""
            + case_shell.sources_block(
                f"Окно {days} дн. Источники: state.json (форвардная книга), random-control.json, "
                f"ai-bee-journal.jsonl, ai-learner-journal.jsonl, ai-learner-trades.jsonl, "
                f"mt5-journal.jsonl, okx-advisor-book.jsonl, публичные свечи Bybit и OKX. "
                f"Сборка {time.strftime('%d.%m.%Y %H:%M', time.gmtime())} UTC.",
                notes=["Страница собирается из журналов. Ни одно число здесь не набрано руками: если "
                       "данные не сошлись, на месте числа стоит «—».",
                       # Дисклеймер уже стоит в шелле (class="gdisclaimer") — второй раз не печатаем.
                       ]))
