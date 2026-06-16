"""Dashboard iki aşamalı yayın testleri."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from diplomacy_bot.dashboard_publish import publish_dashboard_two_phase
from diplomacy_bot.store import Account


def _acc():
    return Account(
        id=1,
        name="ygt",
        token="tok",
        player_id="p",
        username="t",
        autofarm=True,
        last_farm_at=0,
        last_balance=0,
        proxy_id="direct",
        proxy_url="",
        status="active",
    )


def test_two_phase_core_then_enrich():
    acc = _acc()
    bot = MagicMock()
    core = {
        "username": "t",
        "level": 5,
        "balance": 100,
        "work_ready": True,
        "active_skills": {},
    }
    enriched = {**core, "quests_claimable": 2, "training_ready": True}

    with (
        patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=None),
        patch("diplomacy_bot.stealth_client.cooldown_remaining_sec", return_value=0),
        patch("diplomacy_bot.dashboard_readiness.is_readiness_cache_fresh", return_value=False),
        patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
        patch(
            "diplomacy_bot.dashboard_publish.asyncio.to_thread",
            new=AsyncMock(side_effect=[core, enriched]),
        ),
        patch("diplomacy_bot.dashboard_publish.edit_safe", new_callable=AsyncMock) as mock_edit,
        patch("diplomacy_bot.dashboard_publish.format_dashboard_html", return_value="html"),
        patch("diplomacy_bot.dashboard_publish.dashboard_inline_markup", return_value=MagicMock()),
    ):

        async def _run():
            await publish_dashboard_two_phase(bot, 1, 99, acc, force_refresh=True)

        asyncio.run(_run())
    assert mock_edit.await_count == 2


def test_cooldown_without_cache_shows_wait():
    acc = _acc()
    bot = MagicMock()

    with (
        patch("diplomacy_bot.dynamic_context.peek_snapshot_cache", return_value=None),
        patch("diplomacy_bot.stealth_client.cooldown_remaining_sec", return_value=120),
        patch("diplomacy_bot.telegram_app._user_accounts", return_value=[]),
        patch("diplomacy_bot.dashboard_publish.edit_safe", new_callable=AsyncMock) as mock_edit,
        patch("diplomacy_bot.dashboard_publish.format_dashboard_html", return_value="html"),
        patch("diplomacy_bot.dashboard_publish.dashboard_inline_markup", return_value=MagicMock()),
    ):

        async def _run():
            await publish_dashboard_two_phase(bot, 1, 99, acc, force_refresh=True)

        asyncio.run(_run())

    assert mock_edit.await_count == 1
    footer = mock_edit.await_args_list[0].args[3]
    assert "120" in footer
