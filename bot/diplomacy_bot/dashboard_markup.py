"""Dashboard inline klavye — readiness rozetleri."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .account_config import get_config
from .store import Account, list_accounts


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

    row1: list[InlineKeyboardButton] = [
        InlineKeyboardButton("🌾 Farm", callback_data="action:farmboard"),
        InlineKeyboardButton("🔄 Yenile", callback_data="dash:refresh"),
    ]
    if health < 100:
        row1.insert(1, InlineKeyboardButton("💊 Can", callback_data="action:hap"))
    row1.append(InlineKeyboardButton("⚡ Statlar", callback_data="action:statboard"))

    rows: list[list[InlineKeyboardButton]] = [row1]

    qc = int(snap.get("quests_claimable") or 0)
    quick: list[InlineKeyboardButton] = []
    if qc > 0:
        quick.append(InlineKeyboardButton(f"📜 Görev ({qc})", callback_data="action:quests"))
    if snap.get("training_ready"):
        quick.append(InlineKeyboardButton("🏋️ Antrenman", callback_data="action:training"))
    if snap.get("craft_ready"):
        quick.append(InlineKeyboardButton("💎 Hap üret", callback_data="action:farmboard"))
    if quick:
        rows.append(quick)

    extras_bits: list[str] = []
    if qc:
        extras_bits.append(f"📜{qc}")
    if snap.get("training_ready"):
        extras_bits.append("🏋️")
    extras_label = "⋯ Daha" + (f" ({' '.join(extras_bits)})" if extras_bits else "")

    rows.append(
        [
            InlineKeyboardButton("🎁 Günlük", callback_data="action:daily"),
            InlineKeyboardButton("📋 Plan", callback_data="action:plan"),
            InlineKeyboardButton(extras_label, callback_data="menu:extras"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("👥 Filo", callback_data="menu:fleet"),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="menu:settings"),
            InlineKeyboardButton("🎮 Oyun", url="https://diplomacia.com.tr/"),
        ]
    )

    fid = snap.get("factory_id") or get_config(acc.name).preferred_factory_id
    if fid:
        rows.append([InlineKeyboardButton("📋 Fabrika ID", callback_data="action:copyfactory")])

    accs = user_accs if user_accs is not None else list_accounts()
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.append(switch)
    else:
        rows.append([InlineKeyboardButton("👤 Hesaplar", callback_data="menu:accounts")])

    return InlineKeyboardMarkup(rows)


def install_dashboard_markup_patch() -> None:
    """telegram_ui.dashboard_inline_markup → bu modül (büyük dosya refactor öncesi)."""
    from . import telegram_ui

    telegram_ui.dashboard_inline_markup = dashboard_inline_markup
