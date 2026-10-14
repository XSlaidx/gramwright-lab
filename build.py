"""build.py — собирает статический сайт блога из markdown-постов. Только стандартная библиотека.

Почему так: пост должен жить в markdown внутри репозитория, чтобы история правок была видна в
коммитах, а сайт — быть производным артефактом. `build.py` детерминирован: одинаковый набор
постов даёт байт-в-байт одинаковый `docs/`, поэтому CI может проверять, что генерат не забыли
пересобрать.

Запуск:  python build.py          # пересобрать docs/
         python build.py --check  # упасть, если docs/ отличается от пересборки (для CI)
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, "posts")
DOCS_DIR = os.path.join(ROOT, "docs")
SITE_TITLE = "Gramwright Lab"
SITE_DESC = ("Журнал проверки торговых гипотез: что проверяли, что вышло по факту, сколько съели "
             "издержки. Числа берутся из журнала стенда. Не инвестиционная рекомендация.")
SITE_URL = "https://XSlaidx.github.io/gramwright-lab"
TELEGRAM = "https://t.me/gramwright_lab"

STYLE = """/* Gramwright Lab — единственный стилевой файл: тема, типографика, никаких зависимостей */
:root{--bg:#0b1017;--fg:#e8edf3;--muted:#8fa0b3;--line:#1e2a38;--accent:#4cc9f0;--code:#0f1823}
*{box-sizing:border-box}
body{margin:0 auto;max-width:760px;padding:48px 20px 96px;background:var(--bg);color:var(--fg);
font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header.site{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:32px}
header.site h1{margin:0 0 6px;font-size:24px;letter-spacing:.2px}
header.site p{margin:0;color:var(--muted);font-size:14px}
article{border-bottom:1px solid var(--line);padding:26px 0}
article:last-child{border-bottom:0}
article h2{margin:0 0 4px;font-size:20px;line-height:1.35}
article h2 a{color:var(--fg)}
article time{color:var(--muted);font-size:13px}
article p{margin:12px 0}
article ul{margin:12px 0;padding-left:22px}
article li{margin:6px 0}
article code{background:var(--code);padding:2px 5px;border-radius:4px;font-size:13px}
article pre{background:var(--code);padding:14px;border-radius:8px;overflow:auto}
article pre code{background:none;padding:0}
.tags{color:var(--muted);font-size:13px;margin-top:10px}
.verdict{color:var(--muted);font-size:15px;font-weight:400}
.intro{color:var(--muted);margin-bottom:26px}
.meta{color:var(--muted);font-size:13px;margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
footer.site{border-top:1px solid var(--line);margin-top:44px;padding-top:18px;color:var(--muted);font-size:13px}
"""
FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Post:
    slug: str
    title: str
    date: str
    telegram: str
    tags: list[str]
    summary: str
    body_md: str
    body_html: str


def parse_front_matter(text: str) -> tuple[dict, str]:
    match = FRONT_RE.match(text)
    if not match:
        return {}, text
    meta: dict = {}
    for line in match.group(1).splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def load_posts() -> list[Post]:
    posts: list[Post] = []
    for filename in sorted(os.listdir(POSTS_DIR)):
        if not filename.endswith(".md"):
            continue
        raw = open(os.path.join(POSTS_DIR, filename), encoding="utf-8").read()
        meta, body = parse_front_matter(raw)
        slug = filename[:-3]
        tags = [t.strip() for t in meta.get("tags", "").strip("[]").split(",") if t.strip()]
        posts.append(Post(slug=slug, title=meta.get("title", slug), date=meta.get("date", ""),
                          telegram=meta.get("telegram", TELEGRAM), tags=tags,
                          summary=meta.get("summary", ""), body_md=body.strip(),
                          body_html=markdown_to_html(body.strip())))
    posts.sort(key=lambda p: (p.date, p.slug), reverse=True)
    return posts


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def markdown_to_html(md: str) -> str:
    """Ровно тот subset, который мы пишем руками: заголовки, абзацы, списки, код, акценты."""
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            items = "".join(f"<li>{inline(item)}</li>" for item in list_items)
            blocks.append(f"<ul>{items}</ul>")
            list_items.clear()

    for line in md.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines.clear()
            else:
                flush_paragraph()
                flush_list()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(stripped[2:])
            continue
        if stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            blocks.append(f"<h{min(level + 1, 6)}>{inline(stripped[level:].strip())}</h{min(level + 1, 6)}>")
            continue
        paragraph.append(stripped)
    flush_paragraph()
    flush_list()
    if code_lines:
        blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(blocks)


def page(title: str, body: str, *, description: str = SITE_DESC, path: str = "") -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(description)}">
<meta property="og:type" content="article">
<link rel="alternate" type="application/rss+xml" href="{SITE_URL}/feed.xml">
<link rel="stylesheet" href="{path}style.css">
</head>
<body>
<header class="site">
  <h1><a href="{path}index.html">{SITE_TITLE}</a></h1>
  <p>{SITE_DESC}</p>
</header>
{body}
<footer class="site">
  Код стенда и аудитора: <a href="https://github.com/XSlaidx/truth-engine">XSlaidx/truth-engine</a>
  &middot; <a href="{path}graveyard.html">кладбище правил</a>
  &middot; обсуждение: <a href="{TELEGRAM}">@gramwright_lab</a>
</footer>
</body>
</html>
"""


def render_index(posts: list[Post]) -> str:
    items = []
    for post in posts:
        tags = f'<div class="tags">{" · ".join(post.tags)}</div>' if post.tags else ""
        items.append(f"""<article>
  <h2><a href="posts/{post.slug}.html">{html.escape(post.title)}</a></h2>
  <time>{html.escape(post.date)}</time>
  <p>{inline(post.summary or post.body_md.splitlines()[0])}</p>
  {tags}
  <p><a href="posts/{post.slug}.html">Читать →</a></p>
</article>""")
    body = "\n".join(items) or "<p>Публикаций пока нет.</p>"
    return page(SITE_TITLE, body)


def render_post(post: Post) -> str:
    body = f"""<article>
  <h2>{html.escape(post.title)}</h2>
  <time>{html.escape(post.date)}</time>
  {post.body_html}
  <div class="meta">Обсуждение и комментарии: <a href="{post.telegram}">Telegram</a></div>
</article>"""
    return page(f"{post.title} — {SITE_TITLE}", body, description=post.summary or SITE_DESC, path="../")


def render_feed(posts: list[Post]) -> str:
    items = []
    for post in posts:
        try:
            dt = datetime.strptime(post.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            dt = datetime.now(timezone.utc)
        items.append(f"""  <item>
    <title>{html.escape(post.title)}</title>
    <link>{SITE_URL}/posts/{post.slug}.html</link>
    <guid>{SITE_URL}/posts/{post.slug}.html</guid>
    <pubDate>{format_datetime(dt)}</pubDate>
    <description>{html.escape(post.summary)}</description>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>{SITE_TITLE}</title>
  <link>{SITE_URL}</link>
  <description>{html.escape(SITE_DESC)}</description>
{chr(10).join(items)}
</channel></rss>
"""


def load_graveyard() -> list[dict]:
    """Каждое убитое правило — запись в JSON, а не абзац в посте: так её видно в истории коммитов."""
    path = os.path.join(ROOT, "graveyard.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("entries", [])


def render_graveyard(entries: list[dict]) -> str:
    rows = []
    for entry in entries:
        rows.append(f"""<article>
  <h2>{html.escape(entry['rule'])} <span class="verdict">— {html.escape(entry['verdict'])}</span></h2>
  <p><strong>Проверено:</strong> {html.escape(entry['tested'])}</p>
  <p><strong>Чем убито:</strong> {html.escape(entry['cause'])}</p>
  <p><strong>Цифры:</strong> {html.escape(entry['evidence'])}</p>
  <p class="tags">{html.escape(entry.get('status', ''))}</p>
</article>""")
    intro = ("Записи не удаляются и не редактируются: любая правка видна в истории коммитов. "
             "Отрицательный результат — тоже результат, и здесь он хранится вместе с причиной смерти.")
    body = f"<h1>Кладбище правил</h1>\n<p class=\"intro\">{intro}</p>\n" + ("\n".join(rows) or "<p>Пока пусто.</p>")
    return page("Кладбище правил — " + SITE_TITLE, body)


def build() -> dict[str, str]:
    posts = load_posts()
    files = {"index.html": render_index(posts), "style.css": STYLE, "feed.xml": render_feed(posts),
             "graveyard.html": render_graveyard(load_graveyard()),
             ".nojekyll": ""}
    for post in posts:
        files[f"posts/{post.slug}.html"] = render_post(post)
    return files


def write(files: dict[str, str]) -> None:
    for relative, content in files.items():
        target = os.path.join(DOCS_DIR, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)


def check(files: dict[str, str]) -> list[str]:
    drift = []
    for relative, content in files.items():
        target = os.path.join(DOCS_DIR, relative)
        if not os.path.exists(target) or open(target, encoding="utf-8").read() != content:
            drift.append(relative)
    for root, _dirs, names in os.walk(DOCS_DIR):
        for name in names:
            relative = os.path.relpath(os.path.join(root, name), DOCS_DIR).replace("\\", "/")
            if relative not in files:
                drift.append(f"{relative} (лишний файл)")
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render markdown posts into docs/")
    parser.add_argument("--check", action="store_true", help="fail if docs/ is not up to date")
    args = parser.parse_args(argv)
    files = build()
    if args.check:
        drift = check(files)
        if drift:
            print("docs/ отличается от пересборки:\n  " + "\n  ".join(sorted(drift)))
            return 1
        print(f"docs/ актуален ({len(files)} файлов)")
        return 0
    write(files)
    print(f"собрано {len(files)} файлов в docs/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
