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
                InlineKeyboardButton("📥 Token inbox", callback_data="fleet:cmd:inbox"),
                InlineKeyboardButton("🚀 Hazırla", callback_data="fleet:cmd:bootstrap"),
            ],
            [
                InlineKeyboardButton("🏠 İkamet", callback_data="fleet:cmd:residence"),
                InlineKeyboardButton("🛠 Onar", callback_data="fleet:cmd:repair"),
            ],
            [
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


def _pending_inbox_count(accounts: list) -> int:
    uid = int(getattr(accounts[0], "telegram_user_id", 0) or 0) if accounts else 0
    if not uid:
        return 0
    try:
        from .token_watch import list_fresh_inbox_import_candidates

        return len(list_fresh_inbox_import_candidates(uid))
    except Exception:
        return 0


def patch_fleet_ui_buttons() -> None:
    from . import telegram_ui as ui

    if getattr(ui, "_fleet_ops_buttons_installed", False):
        return

    def fleet_inline_markup_patched(active_name: str, accs=None):
        from .account_config import get_config, normalize_role

        accounts = list(accs or [])
        pending = _pending_inbox_count(accounts)
        start_label = f"▶️ {pending} tokeni başlat" if pending else "▶️ Başlat"
        rows = [
            [
                InlineKeyboardButton(start_label, callback_data="fleet:cmd:start"),
                InlineKeyboardButton("📋 Durum", callback_data="fleet:cmd:ops"),
            ],
            [
                InlineKeyboardButton("🇦🇴 AOD", callback_data="fleet:cmd:aod"),
                InlineKeyboardButton("⚙️ İşlemler", callback_data="fleet:menu:more"),
            ],
        ]
        labels = getattr(ui, "ROLE_LABELS_TR")
        for acc in accounts[:8]:
            cfg = get_config(acc.name)
            mark = "⭐" if acc.name == active_name else ""
            role = labels.get(normalize_role(cfg.role), "?")
            rows.append([InlineKeyboardButton(f"{mark}{acc.name} · {role}", callback_data=f"role:pick:{acc.name}")])
        rows.append([ui.back_home_button()])
        return InlineKeyboardMarkup(rows)

    ui.fleet_inline_markup = fleet_inline_markup_patched
    ui._fleet_ops_buttons_installed = True
