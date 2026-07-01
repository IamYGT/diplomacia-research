"""Telegram callback — zengin özellik handler'ları."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import game_features
from .account_runtime import interactive_account_context
from .dynamic_context import invalidate_snapshot_cache, snapshot_account
from .feature_reports import (
    format_auto_board_html,
    format_countries_board_html,
    format_craft_board_html,
    format_extras_hub_html,
    format_factory_board_html,
    format_military_html,
    format_online_board_html,
    format_passive_board_html,
    format_ping_board_html,
    format_quest_board_html,
    format_quest_claim_html,
    format_training_html,
    format_war_board_html,
    format_war_contribute_html,
)
from .store import Account
from .telegram_ui import back_home_button, result_with_home_markup
from .ui_tracker import edit_safe, spawn_tracked

log = logging.getLogger(__name__)

USER_FACING_ERROR = "İşlem başarısız. /start ile yeniden dene."


async def open_extras_hub(update, context, query, *, edit: bool = True) -> None:
    """Ek menü — anında iskelet, ardından canlı hazırlık özeti."""
    from .telegram_ui import extras_inline_markup, format_extras_html

    if not query or not query.message:
        return
    bot = query.get_bot()
    if edit:
        chat_id = query.message.chat_id
        msg_id = query.message.message_id
        await edit_safe(bot, chat_id, msg_id, format_extras_html(), reply_markup=extras_inline_markup())
    else:
        sent = await query.message.reply_text(
            format_extras_html(),
            parse_mode="HTML",
            reply_markup=extras_inline_markup(),
        )
        chat_id = sent.chat_id
        msg_id = sent.message_id

    default = (context.user_data.get("default_account") or "").strip().lower()
    uid = query.from_user.id if query.from_user else 0
    from .auth import resolve_account, scoped_list_accounts

    acc = resolve_account(default, uid) if default else None
    if not acc:
        accs = scoped_list_accounts(uid)
        acc = accs[0] if accs else None
    if not acc:
        return

    async def _enrich():
        def _fetch():
            from .readiness_probes import fetch_readiness_pack

            with interactive_account_context(acc):
                return fetch_readiness_pack(acc.token, acc.name)

        try:
            pack = await asyncio.to_thread(_fetch)
            if not pack.get("ok"):
                return
            text = format_extras_hub_html(pack.get("readiness") or {})
            snap = {
                "quests_claimable": pack.get("readiness", {}).get("quest_claimable", 0),
                "work_ready": pack.get("readiness", {}).get("work_ready", False),
                "passive_available": pack.get("readiness", {}).get("passive_pts", 0),
                "training_ready": pack.get("readiness", {}).get("training_ready", False),
                "war_active": pack.get("readiness", {}).get("war_active", 0),
                "craft_ready": pack.get("readiness", {}).get("craft_ready", False),
            }
            await edit_safe(
                bot,
                chat_id,
                msg_id,
                text,
                reply_markup=extras_inline_markup(snap),
            )
        except Exception:
            log.exception("extras hub enrich")

    spawn_tracked(context.application, _enrich(), name="menu:extras-enrich")


def extras_inline_markup(snap: dict | None = None) -> InlineKeyboardMarkup:
    """Rozetli ek menü — telegram_ui'dan import edilmezse burada da tanımlı."""
    from .telegram_ui import extras_inline_markup as _ui_extras

    return _ui_extras(snap)


async def try_extra_feature_action(
    update,
    context,
    data: str,
    acc: Account,
    query,
    *,
    begin_tracked_action,
    finish_tracked_action,
) -> bool:
    """Zengin özellik callback'leri."""
    handlers = {
        "action:questlist",
        "action:quests",
        "action:wars",
        "action:warcontrib",
        "action:training",
        "action:military",
        "action:myfactory",
        "action:craft",
        "action:countries",
        "action:online",
        "action:autostatus",
        "action:passive",
        "action:statboard",
        "action:farmboard",
        "action:ping",
    }
    if data not in handlers:
        return False

    coords = await begin_tracked_action(query, data)
    if not coords:
        return True
    bot, chat_id, msg_id = coords

    async def _job():
        try:
            text, markup, parse_mode = await _render_feature(data, acc)
            if data == "action:wars":
                def _ids():
                    with interactive_account_context(acc):
                        p = game_features.fetch_war_board(acc.token, acc.name)
                        return p.get("war_ids") or []

                try:
                    context.user_data["war_board_ids"] = await asyncio.to_thread(_ids)
                except Exception:
                    pass
            if data == "action:myfactory":
                def _fab_ids():
                    with interactive_account_context(acc):
                        p = game_features.fetch_factory_board(acc.token, acc.name)
                        return {
                            "owned": p.get("owned_ids") or [],
                            "region": p.get("region_ids") or [],
                        }

                try:
                    context.user_data["factory_board_ids"] = await asyncio.to_thread(_fab_ids)
                except Exception:
                    pass
            if data in ("action:statboard", "action:passive"):
                def _stat_keys():
                    with interactive_account_context(acc):
                        p = game_features.fetch_stat_board(acc.token, acc.name)
                        return {
                            "active": p.get("active_skill_keys") or [],
                            "passive": p.get("passive_skill_keys") or p.get("skill_keys") or [],
                        }

                try:
                    keys = await asyncio.to_thread(_stat_keys)
                    context.user_data["stat_active_keys"] = keys.get("active") or []
                    context.user_data["stat_passive_keys"] = keys.get("passive") or []
                    context.user_data["stat_board_keys"] = keys.get("passive") or []
                except Exception:
                    pass
            if data == "action:statboard":
                await bot.send_message(
                    chat_id,
                    text,
                    reply_markup=markup,
                    parse_mode=parse_mode,
                )
            else:
                await edit_safe(bot, chat_id, msg_id, text, reply_markup=markup, parse_mode=parse_mode)
        except Exception as e:
            log.exception("feature %s: %s", data, e)
            await finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

    spawn_tracked(context.application, _job(), name=data)
    return True


async def _render_feature(data: str, acc: Account) -> tuple[str, InlineKeyboardMarkup, str | None]:
    parse_mode = "HTML"
    markup = result_with_home_markup()

    def _run(fn):
        with interactive_account_context(acc):
            return fn()

    if data == "action:questlist":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_quests(acc.token))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        return (
            format_quest_board_html(pack.get("quests") or [], pack.get("analysis")),
            markup,
            parse_mode,
        )

    if data == "action:quests":
        pack = await asyncio.to_thread(_run, lambda: game_features.claim_quests_smart(acc.token))
        invalidate_snapshot_cache(acc.name)
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        return (
            format_quest_claim_html(pack.get("results") or [], pack.get("analysis")),
            markup,
            parse_mode,
        )

    if data == "action:wars":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_war_board(acc.token, acc.name))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        from .account_config import get_config
        from .war_board import format_war_board_html, war_board_inline_markup

        analysis = pack.get("analysis") or {}
        return (
            format_war_board_html(pack.get("data") or {}, analysis, get_config(acc.name)),
            war_board_inline_markup(analysis),
            parse_mode,
        )

    if data == "action:warcontrib":
        from .war_ops import run_war_contribute

        pack = await asyncio.to_thread(_run, lambda: run_war_contribute(acc.token, acc.name))
        invalidate_snapshot_cache(acc.name)
        return format_war_contribute_html(pack, pack.get("analysis")), markup, parse_mode

    if data == "action:training":
        pack = await asyncio.to_thread(_run, lambda: game_features.run_training_attack(acc.token, acc.name))
        invalidate_snapshot_cache(acc.name)
        return (
            format_training_html(
                pack.get("war"),
                pack,
                analysis=pack.get("analysis"),
            ),
            markup,
            parse_mode,
        )

    if data == "action:military":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_military_board(acc.token))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        return (
            format_military_html(pack.get("data") or {}, pack.get("ops"), pack.get("analysis")),
            markup,
            parse_mode,
        )

    if data == "action:myfactory":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_factory_board(acc.token, acc.name))
        if not pack.get("ok") and not pack.get("factories"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        from .account_config import get_config
        from .factory_board import factory_board_inline_markup, format_factory_board_html

        analysis = pack.get("analysis") or {}
        return (
            format_factory_board_html(pack, analysis, get_config(acc.name)),
            factory_board_inline_markup(analysis),
            parse_mode,
        )

    if data in ("action:farmboard", "action:craft"):
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_farm_board(acc.token, acc.name))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        from .account_config import get_config
        from .farm_board import farm_board_inline_markup, format_farm_board_html

        analysis = pack.get("analysis") or {}
        return (
            format_farm_board_html(pack, analysis, get_config(acc.name)),
            farm_board_inline_markup(analysis),
            parse_mode,
        )

    if data == "action:countries":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_countries(acc.token))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        countries = pack.get("countries") or []
        text = format_countries_board_html(countries, current_country=pack.get("current_country"))
        rows = [
            [InlineKeyboardButton(c.get("name", "?")[:36], callback_data=f"country:{c['id']}")]
            for c in sorted(countries, key=lambda x: int(x.get("player_count") or 0), reverse=True)[:8]
            if c.get("id")
        ]
        rows.append([back_home_button()])
        return text, InlineKeyboardMarkup(rows), parse_mode

    if data == "action:online":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_online(acc.token))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        return format_online_board_html(pack, pack.get("players")), markup, parse_mode

    if data == "action:autostatus":
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_auto_status(acc.token))
        status = pack.get("status") or {}
        return format_auto_board_html(status, pack.get("analysis")), markup, parse_mode

    if data in ("action:passive", "action:statboard"):
        pack = await asyncio.to_thread(_run, lambda: game_features.fetch_stat_board(acc.token, acc.name))
        if not pack.get("ok"):
            return f"❌ {pack.get('error', USER_FACING_ERROR)}", markup, None
        from .account_config import get_config
        from .stat_board import format_stat_board_html, stat_board_inline_markup

        analysis = pack.get("analysis") or {}
        return (
            format_stat_board_html(pack, analysis, get_config(acc.name)),
            stat_board_inline_markup(analysis),
            parse_mode,
        )

    if data == "action:ping":
        pack = await asyncio.to_thread(_run, lambda: game_features.run_ping(acc.token))
        return format_ping_board_html(pack, latency_ms=pack.get("latency_ms")), markup, parse_mode

    return f"❌ Bilinmeyen aksiyon: {data}", markup, None
