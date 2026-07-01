"""Dashboard inline klavye — sekme navigasyonu."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .account_config import get_config
from .store import Account
from .tab_nav import tab_nav_row


def back_home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")


def dashboard_inline_markup(
    acc: Account,
    snap: dict | None = None,
    *,
    user_accs: list[Account] | None = None,
) -> InlineKeyboardMarkup:
    snap = snap or {}
    health = int(snap.get("health") or 0)
    rows: list[list[InlineKeyboardButton]] = [tab_nav_row(active="home")]

    row1 = [
        InlineKeyboardButton("🌾 Altın Kazan", callback_data="action:farmboard"),
        InlineKeyboardButton("🔄 Yenile", callback_data="dash:refresh"),
    ]
    if health < 100:
        row1.insert(1, InlineKeyboardButton("💊 Can", callback_data="action:hap"))
    rows.append(row1)

    rows.append(
        [
            InlineKeyboardButton("▶️ Program", callback_data=f"easy:run:{acc.name.strip().lower()}"),
            InlineKeyboardButton("🎁 Günlük", callback_data="action:daily"),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="menu:settings"),
        ]
    )

    accs = user_accs if user_accs is not None else []
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.append(switch)

    return InlineKeyboardMarkup(rows)


def install_dashboard_markup_patch() -> None:
    from . import telegram_ui

    telegram_ui.dashboard_inline_markup = dashboard_inline_markup
