"""Hesap seçici — /accounts metin + inline klavye."""

from __future__ import annotations

import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .account_config import get_config, normalize_role, role_label
from .account_main import get_main_account_name
from .account_balance import DisplayBalance, any_token_errors, resolve_display_balance, stale_balance_footer
from .config import MAX_ACCOUNTS_PER_USER
from .store import Account

ACCOUNT_BUTTONS_PER_PAGE = 8


def sort_accounts_for_display(
    accs: list[Account],
    *,
    telegram_user_id: int,
    active_name: str,
) -> list[Account]:
    """Ana hesap → aktif → alfabetik."""
    main = (get_main_account_name(telegram_user_id) or "").strip().lower()
    active = (active_name or "").strip().lower()

    def sort_key(a: Account) -> tuple:
        n = a.name.strip().lower()
        if main and n == main:
            return (0, n)
        if active and n == active:
            return (1, n)
        return (2, n)

    return sorted(accs, key=sort_key)


def _account_badges(name: str, *, main: str, active: str) -> str:
    n = name.strip().lower()
    bits: list[str] = []
    if main and n == main:
        bits.append("👑")
    if active and n == active:
        bits.append("⭐")
    return "".join(bits)


def _short_button_label(acc: Account, *, main: str, active: str) -> str:
    badges = _account_badges(acc.name, main=main, active=active)
    uname = (acc.username or acc.name)[:12]
    label = f"{badges}{uname}".strip()
    return label[:28] if label else acc.name[:20]


def format_accounts_html(
    default_name: str,
    accs: list[Account] | None = None,
    *,
    telegram_user_id: int | None = None,
    balances: dict[str, DisplayBalance] | None = None,
) -> str:
    accs = list(accs or [])
    if not accs:
        return (
            "<b>👤 Hesaplarım</b>\n\n"
            "Henüz hesap yok.\n"
            "<code>/connect</code> — ilk hesap\n"
            "<code>/add takma_ad</code> — filo hesabı"
        )

    uid = telegram_user_id or (accs[0].telegram_user_id if accs else 0)
    main = (get_main_account_name(uid) or "").strip().lower()
    active = (default_name or "").strip().lower()
    ordered = sort_accounts_for_display(accs, telegram_user_id=uid, active_name=active)

    lines = [
        f"<b>👤 Hesaplarım</b> — {len(ordered)}/{MAX_ACCOUNTS_PER_USER}",
        "<i>👑 ana · ⭐ aktif · butonla geç</i>\n",
    ]
    for a in ordered:
        badges = _account_badges(a.name, main=main, active=active)
        af = "🟢" if a.autofarm else "⚪"
        role = role_label(normalize_role(get_config(a.name).role))
        bal_info = (balances or {}).get(a.name) or resolve_display_balance(a)
        bal = bal_info.format()
        lines.append(
            f"{badges} <b>{html.escape(a.name)}</b> · {html.escape(a.username or '?')}\n"
            f"    {role} {af} {bal} · <code>{html.escape(a.proxy_id or 'direct')}</code>"
        )
    if balances and any_token_errors(balances):
        lines.append(f"\n{stale_balance_footer()}")
    elif any((balances or {}).get(a.name, resolve_display_balance(a)).source == "stale" for a in ordered):
        lines.append(f"\n{stale_balance_footer()}")
    return "\n".join(lines)


def accounts_inline_markup(
    default_name: str,
    accs: list[Account] | None = None,
    *,
    telegram_user_id: int | None = None,
    page: int = 0,
) -> InlineKeyboardMarkup:
    accs = list(accs or [])
    if not accs:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔗 Hesap bağla", callback_data="menu:connect")],
            ]
        )

    uid = telegram_user_id or accs[0].telegram_user_id
    main = (get_main_account_name(uid) or "").strip().lower()
    active = (default_name or "").strip().lower()
    ordered = sort_accounts_for_display(accs, telegram_user_id=uid, active_name=active)
    total_pages = max(1, (len(ordered) + ACCOUNT_BUTTONS_PER_PAGE - 1) // ACCOUNT_BUTTONS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * ACCOUNT_BUTTONS_PER_PAGE
    visible = ordered[start : start + ACCOUNT_BUTTONS_PER_PAGE]

    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for a in visible:
        label = _short_button_label(a, main=main, active=active)
        row.append(
            InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}")
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    if total_pages > 1:
        pager: list[InlineKeyboardButton] = []
        if page > 0:
            pager.append(InlineKeyboardButton("◀️", callback_data=f"menu:accounts:p:{page - 1}"))
        pager.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="menu:accounts"))
        if page < total_pages - 1:
            pager.append(InlineKeyboardButton("▶️", callback_data=f"menu:accounts:p:{page + 1}"))
        rows.append(pager)

    rows.append(
        [
            InlineKeyboardButton("➕ Yeni hesap", callback_data="menu:connect"),
            InlineKeyboardButton("👥 Filo", callback_data="menu:fleet"),
            InlineKeyboardButton("🏠 Ana sayfa", callback_data="dash:home"),
        ]
    )
    return InlineKeyboardMarkup(rows)
