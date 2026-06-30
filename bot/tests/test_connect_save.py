"""connect_save modülü — import ve yardım metni."""

from __future__ import annotations

from diplomacy_bot.connect_intel import format_account_connected_html
from types import SimpleNamespace


def test_format_account_connected_mentions_world():
    prof = SimpleNamespace(username="Farmer", balance=1000, level=5)
    text = format_account_connected_html("cursor", prof, telegram_user_id=999888)
    assert "cursor" in text
    assert "setrole" in text or "Farm" in text
