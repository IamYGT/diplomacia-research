"""Sekme navigasyonu ve klavye tercihi testleri."""

from __future__ import annotations

from diplomacy_bot.keyboard_prefs import (
    is_reply_keyboard_enabled,
    keyboard_toggle_label,
    reply_keyboard_for_user,
    set_reply_keyboard_enabled,
    toggle_reply_keyboard,
)
from diplomacy_bot.tab_nav import format_travel_tab_html, tab_nav_row, travel_tab_markup, war_tab_markup
from telegram import ReplyKeyboardRemove


def test_tab_nav_row_active_war():
    row = tab_nav_row(active="war")
    assert len(row) == 3
    assert row[1].callback_data == "menu:war"
    assert "✓" in row[1].text


def test_travel_tab_html_escapes():
    html = format_travel_tab_html("🚶 Seyahat\n📍 A → B", province="Tahran")
    assert "Tahran" in html
    assert "<b>🚶 Seyahat</b>" in html


def test_travel_markup_shortcuts():
    mk = travel_tab_markup(
        [{"name": "Tahran"}, {"name": "İsfahan"}, {"name": "Tehran"}]
    )
    flat = [b.callback_data for row in mk.inline_keyboard for b in row]
    assert any(cb.startswith("travel:go:") for cb in flat)
    assert "travel:cancel" in flat


def test_travel_markup_empty():
    mk = travel_tab_markup()
    flat = [b.callback_data for row in mk.inline_keyboard for b in row]
    assert "travel:cancel" in flat
    assert "menu:travel" in flat


def test_war_tab_markup_has_tabs():
    mk = war_tab_markup({}, "ali")
    flat = [b.callback_data for row in mk.inline_keyboard for b in row]
    assert "menu:war" in flat
    assert "easy:run:ali" in flat


def test_open_travel_tab_unpacks_province_kwonly():
    """open_travel_tab province'ı keyword ile geçmeli (menu:travel callback)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from diplomacy_bot.store import Account
    from diplomacy_bot.telegram_tabs import open_travel_tab

    acc = Account(
        id=1,
        name="ygt",
        token="t",
        player_id="p",
        username="Y",
        autofarm=False,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
        telegram_user_id=515491882,
    )
    query = MagicMock()
    query.message = MagicMock()
    query.message.chat_id = 1
    query.message.message_id = 2
    query.get_bot.return_value = AsyncMock()

    async def _run():
        with (
            patch("diplomacy_bot.telegram_tabs.resolve_account", return_value=acc),
            patch(
                "diplomacy_bot.telegram_tabs._travel_tab_payload",
                new=AsyncMock(return_value=("🚶 Durum Tahran", travel_tab_markup())),
            ),
            patch("diplomacy_bot.telegram_tabs.edit_safe", new_callable=AsyncMock) as edit_mock,
        ):
            await open_travel_tab(query, 515491882, "ygt")
            text = edit_mock.await_args.args[3]
            assert "Tahran" in text or "Durum" in text

    asyncio.run(_run())


def test_keyboard_prefs_toggle(tmp_path, monkeypatch):
    from diplomacy_bot import store

    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    store.init_db()
    uid = 999001
    assert is_reply_keyboard_enabled(uid) is True
    set_reply_keyboard_enabled(uid, False)
    assert is_reply_keyboard_enabled(uid) is False
    kb = reply_keyboard_for_user(uid)
    assert isinstance(kb, ReplyKeyboardRemove)
    assert "Kapalı" in keyboard_toggle_label(uid)
    on = toggle_reply_keyboard(uid)
    assert on is True
    assert is_reply_keyboard_enabled(uid) is True
