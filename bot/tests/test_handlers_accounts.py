"""Account handler testleri (M11)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_account_handlers_module_exports():
    from diplomacy_bot.handlers.cmd_accounts import (
        cmd_accounts,
        cmd_add,
        cmd_remove,
        cmd_setaccount,
        cmd_status,
        cmd_whoami,
    )

    for fn in (cmd_whoami, cmd_setaccount, cmd_accounts, cmd_add, cmd_remove, cmd_status):
        assert callable(fn)


def test_cmd_add_delegates_save_to_telegram_app():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from diplomacy_bot.handlers.cmd_accounts import cmd_add

    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["alias", "eyJtoken"]
    context.user_data = {}

    with (
        patch("diplomacy_bot.handlers.cmd_accounts._uid", return_value=515491882),
        patch(
            "diplomacy_bot.auth.default_account_name",
            return_value="u515491882_alias",
        ),
        patch("diplomacy_bot.telegram_app._save_account", new_callable=AsyncMock) as save,
    ):
        asyncio.run(cmd_add(update, context))
    save.assert_awaited_once()
