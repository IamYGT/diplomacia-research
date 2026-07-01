"""Telegram PTB press like job (M9)."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

log = logging.getLogger(__name__)


async def run_press_like_telegram_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    from diplomacy_bot.account_config import get_config
    from diplomacy_bot.config import TELEGRAM_ADMIN_IDS
    from diplomacy_bot.press_likes import auto_like_articles, format_like_result_html
    from diplomacy_bot.store import list_accounts

    for acc in list_accounts():
        cfg = get_config(acc.name)
        if not cfg.auto_like_articles:
            continue
        try:
            res = await asyncio.to_thread(auto_like_articles, acc.token, acc.name)
        except Exception as e:
            log.warning("press_like %s: %s", acc.name, e)
            continue
        if res.get("liked", 0) > 0 or res.get("errors", 0) > 0:
            notify_uid = acc.telegram_user_id or (
                next(iter(TELEGRAM_ADMIN_IDS)) if TELEGRAM_ADMIN_IDS else None
            )
            if notify_uid:
                try:
                    await context.bot.send_message(
                        chat_id=notify_uid,
                        text=format_like_result_html(res),
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
