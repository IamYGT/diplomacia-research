"""Telegram Update/Context simülasyonu — handler yolları prod ile aynı auth kullanır."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from .auth import resolve_account, scoped_list_accounts
from .store import Account


@dataclass
class HarnessSession:
    """Tek Telegram kullanıcısı — user_data + scoped hesap erişimi."""

    uid: int
    user_data: dict[str, Any] = field(default_factory=dict)

    def accounts(self) -> list[Account]:
        return scoped_list_accounts(self.uid)

    def resolve(self, name: str) -> Account | None:
        return resolve_account(name.strip().lower(), self.uid)

    def set_default(self, name: str) -> None:
        self.user_data["default_account"] = name.strip().lower()

    def default_name(self) -> str | None:
        stored = (self.user_data.get("default_account") or "").strip().lower()
        if stored and self.resolve(stored):
            return stored
        accs = self.accounts()
        return accs[0].name if accs else None

    def account_switcher_callbacks(
        self,
        active_name: str,
        *,
        user_accs: list[Account] | None = None,
    ) -> list[str]:
        """dashboard_inline_markup üretir — nav:account:* callback listesi."""
        from .dashboard_markup import dashboard_inline_markup

        acc = self.resolve(active_name)
        if not acc:
            return []
        accs = user_accs if user_accs is not None else self.accounts()
        mk = dashboard_inline_markup(acc, {}, user_accs=accs)
        out: list[str] = []
        for row in mk.inline_keyboard:
            for btn in row:
                cb = btn.callback_data or ""
                if cb.startswith("nav:account:"):
                    out.append(cb)
        return out

    def simulate_nav_account(self, target: str) -> Account | None:
        """nav:account:name — prod callbacks ile aynı resolve."""
        acc = self.resolve(target)
        if acc:
            self.set_default(acc.name)
        return acc

    def format_accounts_visible(self) -> list[str]:
        from .telegram_ui import format_accounts_html

        default = self.default_name() or ""
        html = format_accounts_html(default, self.accounts())
        return [a.name for a in self.accounts() if a.name in html]


def make_update(uid: int, *, text: str = "", callback_data: str = "") -> MagicMock:
    """Minimal telegram.Update — effective_user.id = uid."""
    user = MagicMock()
    user.id = uid
    user.first_name = f"u{uid}"
    update = MagicMock()
    update.effective_user = user
    if text:
        msg = MagicMock()
        msg.text = text
        msg.chat = MagicMock()
        msg.chat.id = uid
        update.message = msg
    if callback_data:
        q = MagicMock()
        q.data = callback_data
        q.from_user = user
        q.message = MagicMock()
        q.message.chat_id = uid
        update.callback_query = q
    return update


def make_context(uid: int, user_data: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    ctx.bot = MagicMock()
    return ctx


def cross_user_resolve_matrix(
    sessions: list[HarnessSession],
    account_names: list[str],
) -> dict[tuple[int, str], bool]:
    """(uid, account_name) → erişim var mı — prod resolve_account ile."""
    out: dict[tuple[int, str], bool] = {}
    for sess in sessions:
        for name in account_names:
            out[(sess.uid, name)] = sess.resolve(name) is not None
    return out
