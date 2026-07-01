"""Hesap bakiyesi — canlı API / snapshot / stale DB."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .store import Account


@dataclass(frozen=True)
class DisplayBalance:
    amount: int | None
    source: str  # live | cache | stale | none
    token_error: bool = False

    def format(self) -> str:
        if self.amount is None:
            return "— 🔑" if self.token_error else "—"
        text = f"{self.amount:,}₺"
        if self.source == "stale":
            text = f"~{text}"
        if self.token_error:
            text = f"{text} 🔑"
        return text


def _balance_from_snapshot(acc: Account) -> int | None:
    from .dynamic_context import peek_snapshot_cache
    from .store import get_game_snapshot

    snap = peek_snapshot_cache(acc.name, allow_stale=True)
    if snap and snap.get("balance") is not None:
        return int(snap["balance"])
    gs = get_game_snapshot(acc.name, max_age_sec=86400)
    if gs and gs.get("balance") is not None:
        return int(gs["balance"])
    return None


def resolve_display_balance(acc: Account) -> DisplayBalance:
    """Tek hesap — önbellek katmanları, canlı API yok."""
    cached = _balance_from_snapshot(acc)
    if cached is not None:
        return DisplayBalance(cached, "cache")
    if acc.last_balance:
        return DisplayBalance(acc.last_balance, "stale")
    return DisplayBalance(None, "none")


def refresh_display_balances(accs: list[Account]) -> dict[str, DisplayBalance]:
    """Liste ekranı — her hesap için canlı profil dene, DB senkronla."""
    from . import game_api
    from .token_recovery import is_token_auth_error

    out: dict[str, DisplayBalance] = {}
    for acc in accs:
        try:
            prof = game_api.get_profile(acc.token, fresh=True)
            bal = int(prof.balance or 0)
            persist_last_balance(acc.name, bal)
            out[acc.name] = DisplayBalance(bal, "live")
        except Exception as e:
            err = str(e)
            token_bad = is_token_auth_error(err)
            cached = _balance_from_snapshot(acc)
            if cached is not None:
                out[acc.name] = DisplayBalance(cached, "cache", token_error=token_bad)
            elif acc.last_balance:
                out[acc.name] = DisplayBalance(acc.last_balance, "stale", token_error=token_bad)
            else:
                out[acc.name] = DisplayBalance(None, "none", token_error=token_bad)
    return out


def persist_last_balance(name: str, balance: int) -> None:
    """last_balance güncelle — last_farm_at dokunulmaz (store.py patch yok)."""
    from .config import DB_PATH

    key = name.strip().lower()
    with sqlite3.connect(DB_PATH, timeout=30.0) as c:
        c.execute("UPDATE accounts SET last_balance=? WHERE name=?", (int(balance), key))


def any_token_errors(balances: dict[str, DisplayBalance]) -> bool:
    return any(b.token_error for b in balances.values())


def stale_balance_footer() -> str:
    return "<i>~ = son kayıt · 🔑 = token yenile (/connect)</i>"
