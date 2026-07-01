"""Telegram inline callback router — _handle_callback telegram_app'ten ayrıldı (split adım 2).

handle_callback gövdesi telegram_app'ten birebir taşındı. Helper'lar
telegram_helpers'tan; _send_dashboard monkey-patch hedefi olduğu için app'te
kalır ve buradan lazy import edilir (callbacks→app runtime, acyclic).
"""
from __future__ import annotations

import asyncio
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .account_config import AccountConfig, BOT_ROLES, get_config, normalize_role, update_config_field
from .account_runtime import account_context, interactive_account_context, interactive_run
from .auth import resolve_account, default_account_name
from .dynamic_context import invalidate_snapshot_cache, peek_snapshot_cache
from .store import Account, set_autofarm, update_after_farm, log_action
from .telegram_ui import connect_inline_markup, format_token_guide_html, result_with_home_markup
from .telegram_navigation import callback_prefers_fresh_reply
from .token_console import format_console_script_telegram
from .ui_tracker import edit_safe, spawn_tracked
from .telegram_helpers import (
    USER_FACING_ERROR, _active_account, _begin_tracked_action, _callback_toast,
    _chunk, _default_account, _finish_tracked_action, _inline_markup,
    _loading_edit, _menu_status_text, _open_keyboard_screen, _reply_action_result,
    _reply_long, _resolve_accounts, _send_accounts_picker, _send_fleet,
    _send_settings, _session_pending_connect, _set_default_account,
    _set_pending_connect, _try_extra_feature_action, _uid, _user_accounts,
    admin_only, user_required,
)

log = logging.getLogger(__name__)

WAR_BOARD_IDS = "war_board_ids"
STAT_ACTIVE_KEYS = "stat_active_keys"
STAT_PASSIVE_KEYS = "stat_passive_keys"
STAT_BOARD_KEYS = "stat_board_keys"
FACTORY_BOARD_IDS = "factory_board_ids"


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
    default: str | None,
    query,
    uid: int,
):
    from . import telegram_app as _app
    def _acc(name: str | None = None) -> Account | None:
        key = name or default
        if not key:
            return None
        return resolve_account(key, uid)


    if data.startswith("nav:account:"):
        name = data.split(":", 2)[2]
        acc = _acc(name)
        if acc:
            _set_default_account(context, uid, name)
            await _app._send_dashboard(
                update,
                acc,
                context,
                edit=not callback_prefers_fresh_reply(data, query),
            )
        return

    if data == "dash:home":
        acc = _acc()
        edit = not callback_prefers_fresh_reply(data, query)
        if acc:
            await _app._send_dashboard(update, acc, context, edit=edit)
        elif query.message:
            if edit:
                await query.message.edit_text(
                    format_token_guide_html(),
                    parse_mode="HTML",
                    reply_markup=connect_inline_markup(),
                )
            else:
                await query.message.reply_text(
                    format_token_guide_html(),
                    parse_mode="HTML",
                    reply_markup=connect_inline_markup(),
                    disable_web_page_preview=True,
                )
        return

    if data == "dash:refresh":
        acc = _acc()
        if acc:
            await _app._send_dashboard(update, acc, context, edit=True, force_refresh=True)
        return

    if data == "menu:settings":
        acc = _acc()
        if acc:
            await _send_settings(
                update,
                acc,
                edit=not callback_prefers_fresh_reply(data, query),
                uid=uid,
            )
        return

    if data == "menu:accounts" or data.startswith("menu:accounts:p:"):
        page = 0
        if data.startswith("menu:accounts:p:"):
            try:
                page = int(data.rsplit(":", 1)[1])
            except ValueError:
                page = 0
        await _send_accounts_picker(
            update,
            context,
            edit=not callback_prefers_fresh_reply(data, query),
            page=page,
        )
        return

    if data == "menu:fleet":
        await _send_fleet(
            update,
            context,
            edit=not callback_prefers_fresh_reply(data, query),
        )
        return

    if data == "menu:connect":
        if query.message:
            if callback_prefers_fresh_reply(data, query):
                await query.message.reply_text(
                    format_token_guide_html(),
                    parse_mode="HTML",
                    reply_markup=connect_inline_markup(),
                    disable_web_page_preview=True,
                )
            else:
                await query.message.edit_text(
                    format_token_guide_html(),
                    parse_mode="HTML",
                    reply_markup=connect_inline_markup(),
                    disable_web_page_preview=True,
                )
            await query.message.reply_text(format_console_script_telegram())
        _set_pending_connect(context, uid, True)
        return

    if data == "connect:script":
        if query.message:
            await query.message.reply_text(format_console_script_telegram())
        _set_pending_connect(context, uid, True)
        try:
            await query.answer("Konsol kodu gönderildi")
        except Exception:
            pass
        return

    if data == "menu:extras":
        from .feature_handlers import open_extras_hub

        await open_extras_hub(
            update,
            context,
            query,
            edit=not callback_prefers_fresh_reply(data, query),
        )
        return

    if data.startswith("role:set:"):
        parts = data.split(":")
        if len(parts) >= 4:
            name, role = parts[2], parts[3]
            if resolve_account(name, uid) and role in BOT_ROLES:
                update_config_field(name, role=role)
                acc = resolve_account(name, uid)
                if acc and name == default:
                    await _send_settings(update, acc, edit=True)
                else:
                    await _send_fleet(update, context, edit=True)
                return
        await _loading_edit(query, f"❌ {USER_FACING_ERROR}")
        return

    if data.startswith("role:pick:"):
        name = data.split(":", 2)[2]
        if query.message:
            await query.edit_message_text(
                f"Rol seç — *{name}*",
                parse_mode="Markdown",
                reply_markup=role_picker_markup(name),
            )
        return

    if data.startswith("fleet:tick:"):
        kind = data.split(":")[2]
        role = None if kind == "all" else kind
        from .fleet_live import format_fleet_final, resolve_fleet_accounts, run_fleet_parallel_live

        accs = resolve_fleet_accounts(role, accounts=_user_accounts(uid))
        if not accs:
            await query.edit_message_text("👥 Filo boş — önce hesap ekle veya rolü off yapma.")
            return
        if query.message:
            await query.edit_message_text(
                f"👥 Filo başlıyor…\n\n" + "\n".join(f"⏳ {a.name} — hazırlanıyor" for a in accs[:12])
            )
            run = await run_fleet_parallel_live(
                context.bot,
                query.message.chat_id,
                query.message.message_id,
                accs,
            )
            await query.message.edit_text(
                format_fleet_final(run),
                reply_markup=result_with_home_markup(),
            )
        return

    if data.startswith("fleet:af:on:"):
        kind = data.split(":")[3]
        n = 0
        for a in _user_accounts(uid):
            if normalize_role(get_config(a.name).role) == kind:
                set_autofarm(a.name, True)
                n += 1
        await _send_fleet(update, context, edit=True)
        return

    if data == "toggle:autofarm":
        acc = _acc()
        if acc:
            set_autofarm(acc.name, not acc.autofarm)
            acc = resolve_account(acc.name, uid)
            await _send_settings(update, acc, edit=True, uid=uid)
        return

    if data in ("cfg:foreign", "cfg:own", "cfg:auto"):
        acc = _acc()
        mode = data.split(":")[1]
        if acc:
            update_config_field(acc.name, work_mode=mode, preferred_factory_id=None)
            invalidate_snapshot_cache(acc.name)
            acc = resolve_account(acc.name, uid)
            await _send_settings(update, acc, edit=True, uid=uid)
        return

    acc = _acc()
    if not acc:
        await query.edit_message_text("Hesap yok.")
        return

    if data.startswith("war:pick:"):
        try:
            idx = int(data.split(":")[2])
        except (IndexError, ValueError):
            return
        war_ids = context.user_data.get("war_board_ids") or []
        if not war_ids:
            from . import game_features

            def _ids():
                with interactive_account_context(acc):
                    p = game_features.fetch_war_board(acc.token, acc.name)
                    return p.get("war_ids") or []

            war_ids = await asyncio.to_thread(_ids)
            context.user_data["war_board_ids"] = war_ids
        if not (0 < idx <= len(war_ids)):
            await query.answer("Savaş bulunamadı — panoyu yenile", show_alert=True)
            return

        async def _refresh_war_panel():
            from . import game_features
            from .war_board import format_war_board_html, war_board_inline_markup

            def _fetch():
                with interactive_account_context(acc):
                    return game_features.fetch_war_board(acc.token, acc.name)

            update_config_field(acc.name, target_war_id=war_ids[idx - 1])
            pack = await asyncio.to_thread(_fetch)
            context.user_data["war_board_ids"] = pack.get("war_ids") or []
            if query.message and pack.get("ok"):
                await edit_safe(
                    query.get_bot(),
                    query.message.chat_id,
                    query.message.message_id,
                    format_war_board_html(
                        pack.get("data") or {},
                        pack.get("analysis"),
                        get_config(acc.name),
                    ),
                    reply_markup=war_board_inline_markup(pack.get("analysis") or {}),
                )

        await query.answer(f"Hedef savaş: #{idx}")
        spawn_tracked(context.application, _refresh_war_panel(), name="war:pick")
        return

    if data.startswith("war:contrib:"):
        try:
            idx = int(data.split(":")[2])
        except (IndexError, ValueError):
            return
        war_ids = context.user_data.get("war_board_ids") or []
        if not war_ids:
            from . import game_features

            def _ids():
                with interactive_account_context(acc):
                    p = game_features.fetch_war_board(acc.token, acc.name)
                    return p.get("war_ids") or []

            war_ids = await asyncio.to_thread(_ids)
        if not (0 < idx <= len(war_ids)):
            await query.answer("Savaş bulunamadı", show_alert=True)
            return
        war_id = war_ids[idx - 1]
        coords = await _begin_tracked_action(query, "action:warcontrib")
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _war_contrib_job():
            from . import game_features
            from .feature_reports import format_war_contribute_html

            try:
                def _run():
                    with interactive_account_context(acc):
                        return game_features.run_war_contribute(
                            acc.token, acc.name, war_id=war_id
                        )

                pack = await asyncio.to_thread(_run)
                invalidate_snapshot_cache(acc.name)
                log_action(
                    "war:contrib",
                    account_name=acc.name,
                    telegram_user_id=uid,
                    result=f"#{idx}",
                    success=bool(pack.get("ok")),
                )
                await edit_safe(
                    bot,
                    chat_id,
                    msg_id,
                    format_war_contribute_html(pack, pack.get("analysis")),
                    reply_markup=result_with_home_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                log.exception("war contrib %s: %s", idx, e)
                await _finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

        spawn_tracked(context.application, _war_contrib_job(), name="war:contrib")
        return

    if data.startswith("war:side:"):
        side = data.split(":")[2] if len(data.split(":")) > 2 else "attacker"
        if side in ("attacker", "defender"):
            update_config_field(acc.name, contribute_side=side)
            label = "saldırgan" if side == "attacker" else "savunucu"
            await query.answer(f"Katkı tarafı: {label}")
        return

    if data == "action:statboard":
        extra = await _try_extra_feature_action(update, context, data, acc, query)
        if extra:
            return

    if data.startswith("farm:"):
        from . import game_features
        from .farm_board import (
            farm_board_inline_markup,
            format_farm_action_html,
            format_farm_board_html,
        )

        parts = data.split(":")
        farm_cmd = parts[1] if len(parts) > 1 else ""

        async def _refresh_farm_panel(footer: str = ""):
            def _fetch():
                with interactive_account_context(acc):
                    return game_features.fetch_farm_board(acc.token, acc.name)

            pack = await asyncio.to_thread(_fetch)
            analysis = pack.get("analysis") or {}
            cfg = get_config(acc.name)
            text = format_farm_board_html(pack, analysis, cfg)
            if footer:
                text = f"{text}\n\n{footer}"
            if query.message and pack.get("ok"):
                await edit_safe(
                    query.get_bot(),
                    query.message.chat_id,
                    query.message.message_id,
                    text,
                    reply_markup=farm_board_inline_markup(analysis),
                )

        async def _run_farm(action: str, **kw):
            def _do():
                with interactive_account_context(acc):
                    if action == "work":
                        return game_features.run_farm_work(acc.token, acc.name)
                    if action == "smart":
                        return game_features.run_farm_smart(acc.token, acc.name)
                    if action == "hap":
                        return game_features.run_use_pills(acc.token, acc.name)
                    if action == "craft":
                        return game_features.run_craft_pills(
                            acc.token, acc.name, diamonds=kw.get("diamonds")
                        )
                    return {"ok": False, "error": "unknown"}

            result = await asyncio.to_thread(_do)
            invalidate_snapshot_cache(acc.name)
            if action in ("work", "smart") and result.get("farm_result"):
                from .store import update_after_farm

                fr = result["farm_result"]
                update_after_farm(acc.name, fr.balance_after)
            log_action(
                f"farm:{action}",
                account_name=acc.name,
                telegram_user_id=uid,
                result=str(result.get("message") or result.get("error") or "")[:200],
                success=bool(result.get("ok")),
            )
            await _refresh_farm_panel(format_farm_action_html(result))

        if farm_cmd == "work":
            await query.answer("Çalışılıyor…")
            spawn_tracked(context.application, _run_farm("work"), name="farm:work")
            return

        if farm_cmd == "smart":
            await query.answer("Akıllı döngü…")
            spawn_tracked(context.application, _run_farm("smart"), name="farm:smart")
            return

        if farm_cmd == "hap":
            await query.answer("Can dolduruluyor…")
            spawn_tracked(context.application, _run_farm("hap"), name="farm:hap")
            return

        if farm_cmd == "craft" and len(parts) > 2:
            try:
                amount = int(parts[2])
            except ValueError:
                return
            update_config_field(acc.name, craft_diamond_batch=amount)
            await query.answer(f"💎 {amount} craft…")
            spawn_tracked(
                context.application,
                _run_farm("craft", diamonds=amount),
                name="farm:craft",
            )
            return

        if farm_cmd == "toggle" and len(parts) > 2 and parts[2] == "autocraft":
            cfg = get_config(acc.name)
            update_config_field(acc.name, craft_pills_when_low=not cfg.craft_pills_when_low)
            await query.answer(
                "Oto craft açık" if not cfg.craft_pills_when_low else "Oto craft kapalı"
            )
            spawn_tracked(context.application, _refresh_farm_panel(), name="farm:toggle")
            return

        return

    if data.startswith("stat:"):
        from . import game_features
        from .stat_board import (
            format_stat_board_html,
            format_stat_spend_result_html,
            resolve_active_skill_key,
            resolve_passive_skill_key,
            stat_board_inline_markup,
        )

        parts = data.split(":")
        stat_cmd = parts[1] if len(parts) > 1 else ""

        async def _refresh_stat_panel(footer: str = ""):
            def _fetch():
                with interactive_account_context(acc):
                    return game_features.fetch_stat_board(acc.token, acc.name)

            pack = await asyncio.to_thread(_fetch)
            context.user_data["stat_active_keys"] = pack.get("active_skill_keys") or []
            context.user_data["stat_passive_keys"] = pack.get("passive_skill_keys") or []
            context.user_data["stat_board_keys"] = pack.get("passive_skill_keys") or []
            analysis = pack.get("analysis") or {}
            cfg = get_config(acc.name)
            text = format_stat_board_html(pack, analysis, cfg)
            if footer:
                text = f"{text}\n\n{footer}"
            if query.message and pack.get("ok"):
                await edit_safe(
                    query.get_bot(),
                    query.message.chat_id,
                    query.message.message_id,
                    text,
                    reply_markup=stat_board_inline_markup(analysis),
                )

        if stat_cmd == "refresh":
            await query.answer("Güncelleniyor…")
            spawn_tracked(context.application, _refresh_stat_panel(), name="stat:refresh")
            return

        async def _run_spend(*, skill: str | None = None, use_next: bool = False):
            def _do():
                with interactive_account_context(acc):
                    if use_next:
                        pack = game_features.fetch_stat_board(acc.token, acc.name)
                        nxt = (pack.get("analysis") or {}).get("next_passive") or (
                            pack.get("analysis") or {}
                        ).get("next_skill")
                        if not nxt:
                            return {"ok": False, "error": "Önerilen pasif skill yok", "action": "spend"}
                        return game_features.run_stat_spend(acc.token, acc.name, skill=nxt)
                    if skill:
                        return game_features.run_stat_spend(acc.token, acc.name, skill=skill)
                    return game_features.run_stat_spend(acc.token, acc.name)

            result = await asyncio.to_thread(_do)
            invalidate_snapshot_cache(acc.name)
            log_action(
                f"stat:{stat_cmd}",
                account_name=acc.name,
                telegram_user_id=uid,
                result=str(result.get("skill") or result.get("error") or "")[:200],
                success=bool(result.get("ok")),
            )
            await _refresh_stat_panel(format_stat_spend_result_html(result))

        async def _run_upgrade(*, skill: str, currency: str = "gold"):
            def _do():
                with interactive_account_context(acc):
                    return game_features.run_skill_upgrade(
                        acc.token, acc.name, skill=skill, currency=currency
                    )

            result = await asyncio.to_thread(_do)
            invalidate_snapshot_cache(acc.name)
            log_action(
                f"stat:up:{skill}:{currency}",
                account_name=acc.name,
                telegram_user_id=uid,
                result=str(result.get("new_level") or result.get("error") or "")[:200],
                success=bool(result.get("ok")),
            )
            await _refresh_stat_panel(format_stat_spend_result_html(result))

        if stat_cmd == "toggle" and len(parts) > 2 and parts[2] == "auto":
            cfg = get_config(acc.name)
            update_config_field(acc.name, stat_auto_enabled=not cfg.stat_auto_enabled)
            state = "açık" if not cfg.stat_auto_enabled else "kapalı"
            await query.answer(f"Otomatik stat {state}")
            spawn_tracked(context.application, _refresh_stat_panel(), name="stat:toggle")
            return

        if stat_cmd == "auto" and len(parts) > 2 and parts[2] == "now":
            await query.answer("Stat otomasyonu…")

            async def _auto_now():
                def _do():
                    with interactive_account_context(acc):
                        return game_features.run_stat_auto_now(acc.token, acc.name)

                result = await asyncio.to_thread(_do)
                invalidate_snapshot_cache(acc.name)
                await _refresh_stat_panel(
                    format_stat_spend_result_html(result, result.get("analysis"))
                )

            spawn_tracked(context.application, _auto_now(), name="stat:auto")
            return

        if stat_cmd == "all":
            await query.answer("Pasif puan harcanıyor…")
            spawn_tracked(context.application, _run_spend(), name="stat:all")
            return

        if stat_cmd == "next":
            await query.answer("Önerilene harcanıyor…")
            spawn_tracked(context.application, _run_spend(use_next=True), name="stat:next")
            return

        if stat_cmd == "uppri":
            cur = parts[2] if len(parts) > 2 else "gold"
            await query.answer("Öncelikli stat yükseltiliyor…")

            async def _up_pri():
                def _do():
                    with interactive_account_context(acc):
                        return game_features.run_skill_upgrade_priority(
                            acc.token, acc.name, currency=cur
                        )

                result = await asyncio.to_thread(_do)
                invalidate_snapshot_cache(acc.name)
                await _refresh_stat_panel(format_stat_spend_result_html(result))

            spawn_tracked(context.application, _up_pri(), name="stat:uppri")
            return

        if stat_cmd == "up" and len(parts) > 3:
            skill_token = parts[2]
            currency = parts[3]

            async def _up_idx():
                from .stat_board import resolve_active_skill_key

                def _fetch():
                    with interactive_account_context(acc):
                        return game_features.fetch_stat_board(acc.token, acc.name)

                pack = await asyncio.to_thread(_fetch)
                skill = resolve_active_skill_key(pack.get("analysis") or {}, skill_token)
                if not skill:
                    await query.answer("Stat bulunamadı", show_alert=True)
                    return
                await query.answer(f"Yükseltiliyor…")
                await _run_upgrade(skill=skill, currency=currency)

            spawn_tracked(context.application, _up_idx(), name="stat:up")
            return

        if stat_cmd == "pspend" and len(parts) > 2:
            skill_token = parts[2]

            async def _pspend_idx():
                from .stat_board import skill_short_name

                def _fetch():
                    with interactive_account_context(acc):
                        return game_features.fetch_stat_board(acc.token, acc.name)

                pack = await asyncio.to_thread(_fetch)
                skill = resolve_passive_skill_key(pack.get("analysis") or {}, skill_token)
                if not skill:
                    await query.answer("Pasif stat bulunamadı", show_alert=True)
                    return
                await query.answer(skill_short_name(skill))
                await _run_spend(skill=skill)

            spawn_tracked(context.application, _pspend_idx(), name="stat:pspend")
            return

        if stat_cmd == "spend" and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            keys = context.user_data.get("stat_passive_keys") or context.user_data.get(
                "stat_board_keys"
            ) or []

            async def _load_and_spend():
                if not keys:
                    def _k():
                        with interactive_account_context(acc):
                            p = game_features.fetch_stat_board(acc.token, acc.name)
                            return p.get("passive_skill_keys") or p.get("skill_keys") or []

                    loaded = await asyncio.to_thread(_k)
                    context.user_data["stat_passive_keys"] = loaded
                    key_list = loaded
                else:
                    key_list = keys
                if not (0 < idx <= len(key_list)):
                    await query.answer("Pasif skill bulunamadı", show_alert=True)
                    return
                skill = key_list[idx - 1]
                await query.answer(f"⚡ {skill}…")
                await _run_spend(skill=skill)

            spawn_tracked(context.application, _load_and_spend(), name="stat:spend")
            return

        if stat_cmd == "prio" and len(parts) > 2:
            skill_token = parts[2]

            async def _set_prio():
                from .stat_board import resolve_active_skill_key, skill_short_name

                def _fetch():
                    with interactive_account_context(acc):
                        return game_features.fetch_stat_board(acc.token, acc.name)

                pack = await asyncio.to_thread(_fetch)
                analysis = pack.get("analysis") or {}
                skill = resolve_active_skill_key(analysis, skill_token)
                if not skill:
                    await query.answer("Bu stat bulunamadı", show_alert=True)
                    return
                cfg = get_config(acc.name)
                prio = [s for s in cfg.stat_priority if s != skill]
                prio.insert(0, skill)
                update_config_field(acc.name, stat_priority=prio)
                await query.answer(f"Önce: {skill_short_name(skill)}")
                await _refresh_stat_panel()

            spawn_tracked(context.application, _set_prio(), name="stat:prio")
            return

        return

    if data.startswith("fab:"):
        from . import game_features
        from .factory_board import (
            factory_board_inline_markup,
            format_factory_action_html,
            format_factory_board_html,
            resolve_factory_index,
        )
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        parts = data.split(":")
        fab_cmd = parts[1] if len(parts) > 1 else ""

        async def _load_fab_ids() -> dict:
            cached = context.user_data.get("factory_board_ids") or {}
            if cached.get("owned") is not None or cached.get("region"):
                return cached

            def _fetch():
                with interactive_account_context(acc):
                    p = game_features.fetch_factory_board(acc.token, acc.name)
                    return {"owned": p.get("owned_ids") or [], "region": p.get("region_ids") or []}

            cached = await asyncio.to_thread(_fetch)
            context.user_data["factory_board_ids"] = cached
            return cached

        async def _refresh_factory_panel(extra_footer: str = ""):
            def _fetch():
                with interactive_account_context(acc):
                    return game_features.fetch_factory_board(acc.token, acc.name)

            pack = await asyncio.to_thread(_fetch)
            context.user_data["factory_board_ids"] = {
                "owned": pack.get("owned_ids") or [],
                "region": pack.get("region_ids") or [],
            }
            analysis = pack.get("analysis") or {}
            cfg = get_config(acc.name)
            text = format_factory_board_html(pack, analysis, cfg)
            if extra_footer:
                text = f"{text}\n\n{extra_footer}"
            if query.message and pack.get("ok"):
                await edit_safe(
                    query.get_bot(),
                    query.message.chat_id,
                    query.message.message_id,
                    text,
                    reply_markup=factory_board_inline_markup(analysis),
                )

        async def _run_fab_action(action: str, *, factory_id: str | None = None, **kw):
            def _do():
                with interactive_account_context(acc):
                    return game_features.run_factory_action(
                        acc.token, acc.name, action, factory_id=factory_id, **kw
                    )

            result = await asyncio.to_thread(_do)
            invalidate_snapshot_cache(acc.name)
            log_action(
                f"fab:{action}",
                account_name=acc.name,
                telegram_user_id=uid,
                result=str(result.get("message") or result.get("error") or "")[:200],
                success=bool(result.get("ok")),
            )
            footer = format_factory_action_html(result)
            await _refresh_factory_panel(footer)
            return result

        if fab_cmd == "mode" and len(parts) > 2:
            mode = parts[2]
            if mode in ("own", "foreign", "auto"):
                update_config_field(acc.name, work_mode=mode, preferred_factory_id=None)
                await query.answer(f"Mod: {mode}")
                spawn_tracked(context.application, _refresh_factory_panel(), name="fab:mode")
            return

        if fab_cmd == "primary" and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            ids = await _load_fab_ids()
            owned = ids.get("owned") or []
            if 0 < idx <= len(owned):
                update_config_field(acc.name, primary_factory_id=owned[idx - 1])
                await query.answer(f"Ana fabrika: #{idx}")
                spawn_tracked(context.application, _refresh_factory_panel(), name="fab:primary")
            else:
                await query.answer("Fabrika yok — yenile", show_alert=True)
            return

        if fab_cmd == "fixed" and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            ids = await _load_fab_ids()
            owned = ids.get("owned") or []
            region = ids.get("region") or []
            fid = None
            if 0 < idx <= len(owned):
                fid = owned[idx - 1]
            elif parts[2].startswith("r") or (len(parts) > 3 and parts[2] == "r"):
                pass
            if fid:
                update_config_field(
                    acc.name, work_mode="fixed", preferred_factory_id=fid, primary_factory_id=fid
                )
                await query.answer(f"Sabit fabrika: #{idx}")
                spawn_tracked(context.application, _refresh_factory_panel(), name="fab:fixed")
            else:
                await query.answer("Fabrika bulunamadı", show_alert=True)
            return

        if fab_cmd == "join" and len(parts) > 3 and parts[2] == "r":
            try:
                ridx = int(parts[3])
            except ValueError:
                return
            ids = await _load_fab_ids()
            region = ids.get("region") or []
            if not (0 < ridx <= len(region)):
                await query.answer("Bölge fabrikası yok", show_alert=True)
                return
            fid = region[ridx - 1]
            await query.answer(f"R{ridx} katılınıyor…")
            spawn_tracked(
                context.application,
                _run_fab_action("join", factory_id=fid),
                name="fab:join",
            )
            return

        if fab_cmd in ("work", "leave", "build"):
            await query.answer("Çalıştırılıyor…")
            spawn_tracked(context.application, _run_fab_action(fab_cmd), name=f"fab:{fab_cmd}")
            return

        if fab_cmd == "close" and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            ids = await _load_fab_ids()
            owned = ids.get("owned") or []
            if not (0 < idx <= len(owned)):
                await query.answer("Fabrika yok", show_alert=True)
                return
            if query.message:
                confirm = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"✅ Evet, #{idx} kapat",
                                callback_data=f"fab:yesclose:{idx}",
                            ),
                            InlineKeyboardButton("İptal", callback_data="action:myfactory"),
                        ]
                    ]
                )
                await edit_safe(
                    query.get_bot(),
                    query.message.chat_id,
                    query.message.message_id,
                    f"<b>🔒 Fabrika #{idx} kapatılsın mı?</b>\n<code>{html.escape(owned[idx - 1])}</code>",
                    reply_markup=confirm,
                )
            return

        if fab_cmd == "yesclose" and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            ids = await _load_fab_ids()
            owned = ids.get("owned") or []
            if not (0 < idx <= len(owned)):
                await query.answer("Fabrika yok", show_alert=True)
                return
            await query.answer("Kapatılıyor…")
            spawn_tracked(
                context.application,
                _run_fab_action("close", factory_id=owned[idx - 1]),
                name="fab:yesclose",
            )
            return

        if fab_cmd in ("withdraw", "level") and len(parts) > 2:
            try:
                idx = int(parts[2])
            except ValueError:
                return
            ids = await _load_fab_ids()
            owned = ids.get("owned") or []
            if not (0 < idx <= len(owned)):
                await query.answer("Fabrika yok", show_alert=True)
                return
            action = "withdraw" if fab_cmd == "withdraw" else "level_up"
            await query.answer(f"#{idx} {action}…")
            spawn_tracked(
                context.application,
                _run_fab_action(action, factory_id=owned[idx - 1]),
                name=f"fab:{fab_cmd}",
            )
            return

        return

    if data.startswith("country:"):
        country_id = data.split(":", 1)[1]
        coords = await _begin_tracked_action(query, "action:country")
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _country_job():
            try:
                from .response_format import format_country_result

                result = await asyncio.to_thread(
                    interactive_run, acc, game_api.select_country, acc.token, country_id
                )
                invalidate_snapshot_cache(acc.name)
                await _finish_tracked_action(
                    bot, chat_id, msg_id, format_country_result(result), parse_mode="Markdown"
                )
            except Exception as e:
                log.exception("country select: %s", e)
                await _finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

        spawn_tracked(context.application, _country_job(), name="action:country")
        return

    if data == "action:hap":
        snap = peek_snapshot_cache(acc.name) or {}
        block = format_hap_preflight(snap)
        if block:
            await _reply_action_result(update, block, parse_mode=None)
            return
        coords = await _begin_tracked_action(query, "action:hap")
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _hap_job():
            try:
                from .response_format import format_pills

                result = await asyncio.to_thread(interactive_run, acc, game_api.try_use_pills, acc.token)
                if result.get("ok"):
                    invalidate_snapshot_cache(acc.name)
                    await _finish_tracked_action(
                        bot, chat_id, msg_id, format_pills(result.get("data") or {})
                    )
                else:
                    await _finish_tracked_action(
                        bot,
                        chat_id,
                        msg_id,
                        format_pill_error(result.get("data"), exc=result.get("error")),
                        parse_mode=None,
                    )
            except Exception as e:
                log.exception("hap: %s", e)
                await _finish_tracked_action(
                    bot, chat_id, msg_id, format_pill_error(exc=str(e)), parse_mode=None
                )

        spawn_tracked(context.application, _hap_job(), name="action:hap")
        return

    if data in ("action:farm", "action:smartfarm", "action:farmboard"):
        if data == "action:farmboard" or data == "action:farm":
            extra = await _try_extra_feature_action(
                update, context, "action:farmboard", acc, query
            )
            if extra:
                return
        if data != "action:smartfarm":
            return
        key = "action:smartfarm"
        coords = await _begin_tracked_action(query, key)
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _farm_job():
            def _farm():
                with interactive_account_context(acc):
                    if data == "action:smartfarm":
                        from .modules.orchestrator import tick_account

                        t = tick_account(acc.token, acc.name)
                        return farmer._tick_to_farm(t)
                    return farmer.run_quick_farm(
                        acc.token, acc.name, acc.proxy_url or None, acc.proxy_id or ""
                    )

            try:
                r = await asyncio.to_thread(_farm)
                update_after_farm(acc.name, r.balance_after)
                invalidate_snapshot_cache(acc.name)
                log_action(
                    key,
                    account_name=acc.name,
                    telegram_user_id=uid,
                    result=f"balance={r.balance_after}",
                )
                from .feature_reports import format_farm_html

                await edit_safe(
                    bot,
                    chat_id,
                    msg_id,
                    format_farm_html(r),
                    reply_markup=result_with_home_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                log.exception("farm: %s", e)
                log_action(key, account_name=acc.name, telegram_user_id=uid, result=str(e)[:200], success=False)
                await _finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

        spawn_tracked(context.application, _farm_job(), name=key)
        return

    if data == "action:status":
        await _app._send_dashboard(update, acc, context, edit=True, force_refresh=True)
        return

    if data == "action:plan":
        coords = await _begin_tracked_action(query, "action:plan")
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _plan_job():
            from .dynamic_context import snapshot_account
            from .feature_reports import format_plan_board_html

            def _snap():
                with interactive_account_context(acc):
                    return snapshot_account(acc, force_refresh=True)

            try:
                snap = await asyncio.to_thread(_snap)
                await edit_safe(
                    bot,
                    chat_id,
                    msg_id,
                    format_plan_board_html(acc.name, snap),
                    reply_markup=result_with_home_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                log.exception("plan: %s", e)
                await _finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

        spawn_tracked(context.application, _plan_job(), name="action:plan")
        return

    if data == "action:copyfactory":
        def _fid():
            with account_context(acc):
                from .dynamic_context import snapshot_account
                s = snapshot_account(acc)
                return s.get("factory_id") or get_config(acc.name).preferred_factory_id or "yok"

        fid = await asyncio.to_thread(_fid)
        await _reply_action_result(update, f"Fabrika ID:\n`{fid}`")
        return

    if data == "action:daily":
        coords = await _begin_tracked_action(query, "action:daily")
        if not coords:
            return
        bot, chat_id, msg_id = coords

        async def _daily_job():
            from .feature_reports import format_daily_html

            try:
                st, d = await asyncio.to_thread(interactive_run, acc, game_api.daily_claim, acc.token)
                invalidate_snapshot_cache(acc.name)
                body = d if isinstance(d, dict) else {"raw": str(d)}
                await edit_safe(
                    bot,
                    chat_id,
                    msg_id,
                    format_daily_html(st, body),
                    reply_markup=result_with_home_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                log.exception("daily: %s", e)
                await _finish_tracked_action(bot, chat_id, msg_id, f"❌ {USER_FACING_ERROR}", parse_mode=None)

        spawn_tracked(context.application, _daily_job(), name="action:daily")
        return

    if data == "action:stat":
        extra = await _try_extra_feature_action(update, context, "action:statboard", acc, query)
        if extra:
            return

    extra = await _try_extra_feature_action(update, context, data, acc, query)
    if extra:
        return
