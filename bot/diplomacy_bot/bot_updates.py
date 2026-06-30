from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR
from .version import get_version, get_version_label

_UPDATES_PATH = DATA_DIR / "bot_updates.json"
_PAGE_SIZE = 1


@lru_cache(maxsize=1)
def load_updates_catalog() -> dict:
    if not _UPDATES_PATH.exists():
        return {"releases": [], "intro": ""}
    return json.loads(_UPDATES_PATH.read_text(encoding="utf-8"))


def list_releases() -> list[dict]:
    return list(load_updates_catalog().get("releases") or [])


def release_for_version(version: str | None = None) -> dict | None:
    v = (version or get_version()).strip()
    for rel in list_releases():
        if str(rel.get("version")) == v:
            return rel
    return None


def _format_story(text: str) -> str:
    parts = [p.strip() for p in (text or "").split("\n") if p.strip()]
    return "\n\n".join(html.escape(p) for p in parts)


def format_release_block(rel: dict, *, current: bool = False) -> str:
    ver = html.escape(str(rel.get("version") or "?"))
    date = html.escape(str(rel.get("date") or ""))
    title = html.escape(str(rel.get("title") or ""))
    codename = html.escape(str(rel.get("codename") or ""))
    badge = " 🆕" if current else ""
    head = f"<b>v{ver}</b>{badge} · {date}"
    if codename:
        head += f"\n<i>{codename}</i>"
    if title:
        head += f"\n{title}"
    story = _format_story(str(rel.get("story") or ""))
    lines = [head]
    if story:
        lines.append(f"\n{story}")
    highlights = rel.get("highlights") or []
    if highlights:
        lines.append("\n<b>Öne çıkanlar</b>")
        for h in highlights:
            lines.append(f"• {html.escape(str(h))}")
    try_now = rel.get("try_now") or []
    if try_now:
        lines.append("\n<b>Dene</b>")
        for t in try_now:
            lines.append(f"→ <code>{html.escape(str(t))}</code>")
    return "\n".join(lines)


def format_updates_html(*, page: int = 0) -> str:
    catalog = load_updates_catalog()
    releases = list_releases()
    intro = html.escape(str(catalog.get("intro") or ""))
    current = get_version()

    if not releases:
        return (
            f"<b>📋 Güncellemeler</b> {get_version_label()}\n\n"
            "Henüz sürüm notu yüklenmedi."
        )

    page = max(0, min(page, max(0, len(releases) - 1)))
    rel = releases[page]
    is_current = str(rel.get("version")) == current

    header = (
        f"<b>📋 Bot güncellemeleri</b> {get_version_label()}\n"
        f"<i>{intro}</i>\n"
        f"—\n"
        f"Sürüm {page + 1}/{len(releases)}\n"
    )
    body = format_release_block(rel, current=is_current)
    footer = ""
    if page == 0 and is_current:
        footer = (
            "\n\n<i>Bu sürümü kullanıyorsun. "
            "Eski notlar için ◀ ile geçmişe bakabilirsin.</i>"
        )
    return header + body + footer


def updates_inline_markup(page: int = 0) -> "InlineKeyboardMarkup":
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    releases = list_releases()
    total = len(releases)
    page = max(0, min(page, max(0, total - 1)))
    row_nav = []
    if page < total - 1:
        row_nav.append(InlineKeyboardButton("◀ Eski", callback_data=f"updates:page:{page + 1}"))
    if page > 0:
        row_nav.append(InlineKeyboardButton("Yeni ▶", callback_data=f"updates:page:{page - 1}"))
    rows = []
    if row_nav:
        rows.append(row_nav)
    rows.append([InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")])
    return InlineKeyboardMarkup(rows)


def format_version_short_html() -> str:
    rel = release_for_version()
    lines = [
        f"<b>🤖 Diplomacia Bot {get_version_label()}</b>",
    ]
    if rel:
        lines.append(f"<i>{html.escape(str(rel.get('codename') or ''))}</i>")
        lines.append(html.escape(str(rel.get("title") or "")))
        lines.append("\nDetaylı hikâye için: /guncellemeler")
    else:
        lines.append("Modüller: economy · factory · stats · training · war · travel")
        lines.append("Detay: /guncellemeler")
    return "\n".join(lines)
