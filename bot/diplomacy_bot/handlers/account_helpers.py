"""Hesap API yardımcıları — telegram_app farm/daily için (M11)."""

from __future__ import annotations

import asyncio

from diplomacy_bot import game_api
from diplomacy_bot.account_runtime import account_context, run_for_account
from diplomacy_bot.store import Account


def proxy_ctx(acc: Account):
    return account_context(acc)


async def profile_for_account(a: Account):
    def _fetch():
        with account_context(a):
            return game_api.get_profile(a.token)

    return await asyncio.to_thread(_fetch)


async def api_for_account(a: Account, fn):
    return await asyncio.to_thread(run_for_account, a, fn, a.token)
