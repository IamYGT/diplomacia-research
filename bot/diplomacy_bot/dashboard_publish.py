"""Dashboard iki aşamalı yayın — önce çekirdek snapshot, sonra readiness enrich."""

from __future__ import annotations

import asyncio
import html
import logging
import os

from telegram import InlineKeyboardMarkup

from .account_runtime import interactive_account_context
from .store import Account
from .telegram_ui import dashboard_inline_markup, format_dashboard_html
from .ui_tracker import edit_safe, tracker_footer

log = logging.getLogger(__name__)

_CORE_TIMEOUT_SEC = float(os.environ.get("DASHBOARD_CORE_TIMEOUT_SEC", "20"))
_ENRICH_TIMEOUT_SEC = float(os.environ.get("DASHBOARD_ENRICH_TIMEOUT_SEC", "18"))


async def publish_dashboard_two_phase(
    bot,
    chat_id: int,
    message_id: int,
    acc: Account,
    *,
    force_refresh: bool = False,
    uid: int = 0,
) -> None:
    from .dashboard_view import snap_is_live
    from .dashboard_readiness import enrich_snapshot_row, is_readiness_cache_fresh
    from .dynamic_context import peek_snapshot_cache, put_snapshot_cache, snapshot_account
    from .stealth_client import cooldown_remaining_sec
    from .telegram_app import _user_accounts

    user_accs = _user_accounts(uid) if uid else None
    log.info("[dash] refresh start acc=%s force=%s uid=%s", acc.name, force_refresh, uid)
    stale = peek_snapshot_cache(acc.name, allow_stale=True)

    def _render(snap: dict, *, footer: str = "") -> tuple[str, InlineKeyboardMarkup]:
        text = format_dashboard_html(acc, snap)
        if footer:
            text = f"{text}{footer}"
        markup = dashboard_inline_markup(acc, snap, user_accs=user_accs)
        return text, markup

    cached = peek_snapshot_cache(acc.name, allow_stale=force_refresh)
    if cached and "error" not in cached and not force_refresh:
        text, markup = _render(cached)
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)
        return

    if cached and "error" not in cached and force_refresh:
        text, markup = _render(cached, footer=tracker_footer("Güncelleniyor"))
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)

    cd = cooldown_remaining_sec()
    if cd > 0 and stale and "error" not in stale:
        text, markup = _render(
            stale,
            footer=f"\n\n<i>⏳ API bekleme ({cd} sn) — önbellek gösteriliyor</i>",
        )
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)
        return

    if cd > 0 and not stale:
        text, markup = _render(
            {"error": f"API bekleme ({cd} sn)"},
            footer=f"\n\n<i>⏳ Rate limit — {cd} sn sonra tekrar deneyin</i>",
        )
        await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)
        return

    def _snap_core() -> dict:
        with interactive_account_context(acc):
            return snapshot_account(acc, force_refresh=True, enrich=False)

    try:
        snap = await asyncio.wait_for(asyncio.to_thread(_snap_core), timeout=_CORE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        snap = stale or {"error": "Çekirdek API zaman aşımı"}
    except Exception as e:
        log.exception("dashboard core snapshot: %s", e)
        snap = stale or {"error": str(e)[:120]}

    if snap.get("error") and stale and "error" not in stale:
        text, markup = _render(
            stale,
            footer=f"\n\n<i>⚠️ Canlı veri alınamadı: {html.escape(str(snap['error'])[:80])}</i>",
        )
    else:
        footer = tracker_footer("Hazır rozetler yükleniyor") if not is_readiness_cache_fresh(acc.name) else ""
        text, markup = _render(snap, footer=footer)
    await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)

    if snap.get("error") or is_readiness_cache_fresh(acc.name):
        return

    def _snap_enrich(base: dict) -> dict:
        with interactive_account_context(acc):
            row = dict(base)
            enrich_snapshot_row(acc, row, network=True)
            return put_snapshot_cache(acc.name, row)

    try:
        snap2 = await asyncio.wait_for(asyncio.to_thread(_snap_enrich, snap), timeout=_ENRICH_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        return
    except Exception as e:
        log.warning("dashboard enrich: %s", e)
        return

    if snap2.get("error"):
        return
    text, markup = _render(snap2)
    await edit_safe(bot, chat_id, message_id, text, reply_markup=markup, disable_web_page_preview=True)


def install_dashboard_publish_patch() -> None:
    """telegram_app._publish_dashboard_message → iki aşamalı hızlı açılış."""
    from . import telegram_app

    if getattr(telegram_app, "_publish_dashboard_message", None) is publish_dashboard_two_phase:
        return
    telegram_app._publish_dashboard_message = publish_dashboard_two_phase
