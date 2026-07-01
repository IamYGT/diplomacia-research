"""Filo Telegram inline klavye — kompakt panel + alt menü."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def fleet_more_inline_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏭 Fabrika", callback_data="fleet:cmd:factory"),
                InlineKeyboardButton("🚶 Hürmüz", callback_data="fleet:cmd:travel"),
            ],
            [
                InlineKeyboardButton("🚀 Bootstrap", callback_data="fleet:cmd:bootstrap"),
                InlineKeyboardButton("🔀 Hybrid", callback_data="fleet:af:on:hybrid"),
            ],
            [
                InlineKeyboardButton("📥 Inbox", callback_data="fleet:cmd:inbox"),
                InlineKeyboardButton("🏠 İkamet", callback_data="fleet:cmd:residence"),
            ],
            [
                InlineKeyboardButton("🛠 Onar", callback_data="fleet:cmd:repair"),
                InlineKeyboardButton("🗳 Oy ver", callback_data="fleet:cmd:vote"),
            ],
            [InlineKeyboardButton("◀️ Filo paneli", callback_data="fleet:menu:main")],
        ]
    )


def fleet_nav_inline_markup() -> InlineKeyboardMarkup:
    """Small return rail shown under fleet result messages."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Durum", callback_data="fleet:cmd:ops"),
                InlineKeyboardButton("▶️ Başlat", callback_data="fleet:cmd:start"),
            ],
            [
                InlineKeyboardButton("⚙️ İşlemler", callback_data="fleet:menu:more"),
                InlineKeyboardButton("◀️ Ana panel", callback_data="fleet:menu:main"),
            ],
        ]
    )


def patch_fleet_ui_buttons() -> None:
    from . import telegram_ui as ui

    if getattr(ui, "_fleet_ops_buttons_installed", False):
        return

    _orig = ui.fleet_inline_markup

    def fleet_inline_markup_patched(active_name: str, accs=None):
        markup = _orig(active_name, accs)
        rows = list(markup.inline_keyboard)
        rows.insert(
            0,
            [
                InlineKeyboardButton("▶️ Başlat", callback_data="fleet:cmd:start"),
                InlineKeyboardButton("🇦🇴 AOD kurulum", callback_data="fleet:cmd:aod"),
                InlineKeyboardButton("📋 Durum", callback_data="fleet:cmd:ops"),
            ],
        )
        rows.insert(
            1,
            [
                InlineKeyboardButton("⚙️ İşlemler", callback_data="fleet:menu:more"),
            ],
        )
        return InlineKeyboardMarkup(rows)

    ui.fleet_inline_markup = fleet_inline_markup_patched
    ui._fleet_ops_buttons_installed = True
