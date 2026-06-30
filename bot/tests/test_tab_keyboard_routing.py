"""Klavye sekmeleri pinned dashboard üzerinden açılır."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from diplomacy_bot.store import Account


def test_war_tab_uses_pinned_dashboard():
    from diplomacy_bot.telegram_easy import handle_easy_menu_action

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
        telegram_user_id=1,
    )
    update = MagicMock()
    update.effective_user = SimpleNamespace(id=1)
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    async def _run():
        with (
            patch("diplomacy_bot.telegram_easy._resolve_account", return_value=(acc, [acc])),
            patch("diplomacy_bot.telegram_tabs.open_tab_from_message", new=AsyncMock()) as open_mock,
        ):
            handled = await handle_easy_menu_action("war_tab", update, context)

        assert handled is True
        open_mock.assert_awaited_once()
        assert open_mock.await_args.args[1].name == "ygt"
        assert open_mock.await_args.args[2] == "war"
        update.message.reply_text.assert_not_awaited()

    asyncio.run(_run())
