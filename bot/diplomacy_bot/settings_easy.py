"""Ayarlar paneli — diğer hesaplar + klavye aç/kapa."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .store import Account


def install_settings_easy_patch() -> None:
    from . import telegram_ui as ui

    if getattr(ui, "_settings_easy_installed", False):
        return

    _orig = ui.settings_inline_markup

    def settings_inline_markup_patched(acc: Account, *, user_accs: list[Account] | None = None) -> InlineKeyboardMarkup:
        markup = _orig(acc, user_accs=user_accs)
        all_accs = user_accs if user_accs is not None else []
        rows = list(markup.inline_keyboard)
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    "⌨️ Alttaki butonlar (aç/kapa)",
                    callback_data="cfg:keyboard:toggle",
                ),
            ],
        )
        insert_at = max(0, len(rows) - 1)
        if len(all_accs) > 1:
            rows.insert(
                insert_at,
                [
                    InlineKeyboardButton(
                        f"👥 Diğer Hesaplar ({len(all_accs)})",
                        callback_data="menu:accounts",
                    ),
                    InlineKeyboardButton("👥 Filo", callback_data="menu:fleet"),
                ],
            )
        return InlineKeyboardMarkup(rows)

    ui.settings_inline_markup = settings_inline_markup_patched  # type: ignore[assignment]
    ui._settings_easy_installed = True
