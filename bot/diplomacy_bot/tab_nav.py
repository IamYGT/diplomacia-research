"""Üst sekme çubuğu — Ana | Savaş | Seyahat."""

from __future__ import annotations

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def tab_nav_row(*, active: str = "home") -> list[InlineKeyboardButton]:
    home = "🏠 Ana" + (" ✓" if active == "home" else "")
    war = "⚔️ Savaş" + (" ✓" if active == "war" else "")
    travel = "🚶 Seyahat" + (" ✓" if active == "travel" else "")
    return [
        InlineKeyboardButton(home, callback_data="dash:home"),
        InlineKeyboardButton(war, callback_data="menu:war"),
        InlineKeyboardButton(travel, callback_data="menu:travel"),
    ]


def format_travel_tab_html(
    status_text: str,
    *,
    province: str | None = None,
    has_shortcuts: bool = False,
) -> str:
    loc = html.escape(province or "?")
    body = html.escape(status_text)
    hint = (
        "<i>Alttan hedef seç veya yaz:</i>\n"
        if has_shortcuts
        else "<i>Hedef yazmak için:</i>\n"
    )
    return (
        "<b>🚶 Seyahat</b>\n\n"
        f"{body}\n\n"
        f"<b>Şu anki eyalet:</b> {loc}\n\n"
        f"{hint}"
        "<code>seyahat et Tahran</code>\n"
        "<code>seyahat iptal</code> · <code>seyahat durum</code>"
    )


def travel_tab_markup(suggested: list[dict] | None = None) -> InlineKeyboardMarkup:
    from urllib.parse import quote

    rows: list[list[InlineKeyboardButton]] = [tab_nav_row(active="travel")]
    if suggested:
        row: list[InlineKeyboardButton] = []
        for p in suggested[:5]:
            name = str(p.get("name") or "").strip()
            if not name:
                continue
            label = name if len(name) <= 18 else name[:16] + "…"
            cb = f"travel:go:{quote(name, safe='')}"
            if len(cb.encode("utf-8")) > 64:
                continue
            row.append(InlineKeyboardButton(f"📍 {label}", callback_data=cb))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append(
        [
            InlineKeyboardButton("🔄 Durumu yenile", callback_data="travel:refresh"),
            InlineKeyboardButton("🛑 Seyahati iptal", callback_data="travel:cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def war_tab_markup(analysis: dict, account_name: str) -> InlineKeyboardMarkup:
    from .account_config import get_config
    from .war_board import war_board_inline_markup

    attacks = get_config(account_name).war_enabled
    base = war_board_inline_markup(analysis, attacks_enabled=attacks)
    rows = [tab_nav_row(active="war")]
    for row in base.inline_keyboard:
        if len(row) == 1 and row[0].callback_data == "dash:home":
            continue
        rows.append(row)
    rows.append(
        [InlineKeyboardButton("▶️ Program", callback_data=f"easy:run:{account_name.strip().lower()}")]
    )
    return InlineKeyboardMarkup(rows)
