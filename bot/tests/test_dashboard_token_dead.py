"""Dashboard token-expired stale cache testi."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_token_dead_skips_stale_cache():
    from diplomacy_bot.store import Account
    from diplomacy_bot.telegram_ui import format_dashboard_html

    acc = Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="Y.G.T",
        autofarm=True,
        last_farm_at=0.0,
        last_balance=1250,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=1,
    )
    stale = {
        "_live": True,
        "balance": 999999,
        "level": 50,
        "username": "Y.G.T",
        "health": 100,
        "autofarm": True,
    }
    dead = {"error": "Oturum süresi doldu. Lütfen tekrar giriş yapın."}
    dead_html = format_dashboard_html(acc, dead)
    stale_html = format_dashboard_html(acc, stale)
    assert "token yenile" in dead_html.lower() or "oturum" in dead_html.lower()
    assert "999,999" in stale_html or "999999" in stale_html
    assert "999,999" not in dead_html and "999999" not in dead_html
