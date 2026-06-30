from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_updates_fast_path(text: str, acc) -> "AgentResult | None":
    from .ai_agent import AgentResult
    from .bot_updates import format_updates_html, updates_inline_markup

    t = text.strip().lower()
    if not re.search(
        r"güncelleme|guncelleme|yenilik|changelog|sürüm not|surum not|ne değişti|yeni özellik",
        t,
    ):
        return None

    page = 0
    m = re.search(r"(\d+)\s*$", t)
    if m:
        page = max(0, int(m.group(1)) - 1)

    return AgentResult(
        reply=format_updates_html(page=page),
        inline_buttons=_buttons_to_agent(page),
        parse_mode="HTML",
    )


def _buttons_to_agent(page: int) -> list[list[tuple[str, str]]]:
    from .bot_updates import list_releases

    total = len(list_releases())
    page = max(0, min(page, max(0, total - 1)))
    rows: list[list[tuple[str, str]]] = []
    nav: list[tuple[str, str]] = []
    if page < total - 1:
        nav.append(("◀ Eski", f"updates:page:{page + 1}"))
    if page > 0:
        nav.append(("Yeni ▶", f"updates:page:{page - 1}"))
    if nav:
        rows.append(nav)
    rows.append([("🏠 Ana Sayfa", "dash:home")])
    return rows
