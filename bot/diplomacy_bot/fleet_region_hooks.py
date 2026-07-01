"""Faz 3 filo bölge komutları — ikamet, oy, vatandaşlık, AOD setup."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .fleet_autopilot_policy import policy_from_region_args, save_fleet_autopilot_policy
from .fleet_command import format_batch_html, format_next_steps_footer
from .fleet_action_guard import reject_stale_fleet_action
from .fleet_region_mission_ui import format_region_mission_html, parse_region_args
from .fleet_start_planner import resolve_fleet_start_plan, tag_fleet_plan
from .fleet_status import format_post_aod_footer
from .fleet_residence import (
    DEFAULT_RESIDENCE_PROVINCE,
    fleet_citizenship_apply,
    fleet_visa_apply,
    fleet_vote,
    set_fleet_residence,
)
from .telegram_helpers import user_required
from .fleet_ui_markup import fleet_nav_inline_markup

log = logging.getLogger(__name__)
_REGISTERED = False
def _format_aod_html(steps: dict, telegram_user_id: int) -> str:
    from .account_config import get_config
    from .account_main import get_main_account_name

    lines = ["<b>🇦🇴 AOD tam kurulum</b>\n"]
    main = get_main_account_name(telegram_user_id)
    if main and not (get_config(main).primary_factory_id or "").strip():
        lines.append(
            "⚠️ <b>Ana fabrika UUID yok</b> — fabrika panelinden 🎯 işaretle veya "
            "<code>/fleetfactory main</code>\n"
        )
    labels = {
        "bootstrap": "🚀 Bootstrap",
        "factory": "🏭 Fabrika",
        "travel": "✈️ Seyahat",
        "residence": "🏠 İkamet",
    }
    for key, batch in steps.items():
        label = labels.get(key, key)
        if key == "factory" and batch.total == 1 and batch.results and "atlandı" in batch.results[0].message:
            lines.append(f"{label}: ⏭ atlandı (ana fabrika yok)")
        else:
            lines.append(f"{label}: {batch.ok}/{batch.total} başarılı")
    lines.append("\n<i>Detay: /fleet status</i>")
    lines.append(f"\n{format_post_aod_footer()}")
    return "\n".join(lines)


def _format_aod_mission_html(result) -> str:
    import html

    lines = [
        "<b>🇦🇴 AOD mission kuyruğu</b>",
        f"<code>{html.escape(result.fleet_id)}</code>",
        f"{result.batch.ok}/{result.batch.total} hesap kalıcı plana alındı\n",
    ]
    for r in result.batch.results[:20]:
        icon = "✅" if r.ok else "❌"
        lines.append(f"{icon} <code>{html.escape(r.account_name)}</code> — {html.escape(r.message)}")
    lines.append("\n<i>Worker seyahat, ikamet ve farm adımlarını kaldığı yerden sürdürecek.</i>")
    lines.append(f"\n{format_post_aod_footer()}")
    return "\n".join(lines)


@user_required
async def cmd_fleetresidence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    prov = " ".join(context.args) if context.args else DEFAULT_RESIDENCE_PROVINCE
    batch = set_fleet_residence(uid, prov)
    await msg.reply_text(
        format_batch_html(f"🏠 Filo ikamet → {prov}", batch, footer=format_next_steps_footer(uid)),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetvote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    cand = context.args[0] if context.args else None
    batch = fleet_vote(uid, candidate_id=cand)
    await msg.reply_text(
        format_batch_html("🗳 Filo seçim oyu", batch, footer=format_next_steps_footer(uid)),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetcitizen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    cid = context.args[0] if context.args else None
    batch = fleet_citizenship_apply(uid, country_id=cid)
    await msg.reply_text(
        format_batch_html("🪪 Filo vatandaşlık başvurusu", batch, footer=format_next_steps_footer(uid)),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetvisa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    cid = context.args[0] if context.args else None
    batch = fleet_visa_apply(uid, country_id=cid)
    await msg.reply_text(
        format_batch_html("📋 Filo vize başvurusu", batch, footer=format_next_steps_footer(uid)),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetaod(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    prov = " ".join(context.args) if context.args else DEFAULT_RESIDENCE_PROVINCE
    from .fleet_mission_service import enqueue_aod_missions_for_uid

    result = enqueue_aod_missions_for_uid(uid, province=prov)
    await msg.reply_text(
        _format_aod_mission_html(result),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetregion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .fleet_mission_service import enqueue_region_missions_for_uid

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    args = list(context.args or [])
    plan = resolve_fleet_start_plan(uid, args)
    if args:
        save_fleet_autopilot_policy(uid, policy_from_region_args(plan.province, plan.opts))
    result = tag_fleet_plan(enqueue_region_missions_for_uid(uid, province=plan.province, **plan.opts), plan)
    await msg.reply_text(
        format_region_mission_html(result, plan.province),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetstart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .fleet_mission_service import start_fleet_autopilot_for_uid
    from .fleet_region_mission_ui import format_autopilot_html

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    args = list(context.args or [])
    if args:
        plan = resolve_fleet_start_plan(uid, args)
        save_fleet_autopilot_policy(uid, policy_from_region_args(plan.province, plan.opts))
        result = tag_fleet_plan(start_fleet_autopilot_for_uid(uid, province=plan.province, **plan.opts), plan)
    else:
        result = start_fleet_autopilot_for_uid(uid)
    await msg.reply_text(
        format_autopilot_html(result),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )
def register_fleet_region_handlers(application: Application) -> None:
    from .fleet_plan_preview import cmd_fleetplan
    global _REGISTERED
    if _REGISTERED:
        return
    commands = (
        ("fleetresidence", cmd_fleetresidence), ("fleetvote", cmd_fleetvote),
        ("fleetcitizen", cmd_fleetcitizen), ("fleetvisa", cmd_fleetvisa),
        ("fleetaod", cmd_fleetaod), ("fleetregion", cmd_fleetregion), ("fleetstart", cmd_fleetstart), ("fleetplan", cmd_fleetplan),
    )
    for name, handler in commands:
        application.add_handler(CommandHandler(name, handler))
    _REGISTERED = True
    log.info("Filo bölge komutları kayıtlı")


def patch_fleet_region_callbacks() -> None:
    from . import callbacks as cb

    if getattr(cb, "_fleet_region_callbacks_installed", False):
        return

    _orig = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if data == "fleet:cmd:start":
            from .fleet_mission_service import start_fleet_autopilot_for_uid
            from .fleet_region_mission_ui import format_autopilot_html

            if await reject_stale_fleet_action(query, "Başlat", uid): return
            result = start_fleet_autopilot_for_uid(uid)
            if query and query.message:
                await query.message.reply_text(
                    format_autopilot_html(result),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:aod":
            from .fleet_mission_service import enqueue_aod_missions_for_uid

            if await reject_stale_fleet_action(query, "AOD", uid): return
            result = enqueue_aod_missions_for_uid(uid)
            if query and query.message:
                await query.message.reply_text(
                    _format_aod_mission_html(result),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:residence":
            if await reject_stale_fleet_action(query, "İkamet", uid): return
            batch = set_fleet_residence(uid, DEFAULT_RESIDENCE_PROVINCE)
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html("🏠 Filo ikamet", batch, footer=format_next_steps_footer(uid)),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:vote":
            if await reject_stale_fleet_action(query, "Oy ver", uid): return
            batch = fleet_vote(uid)
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html("🗳 Filo oy", batch, footer=format_next_steps_footer(uid)),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        return await _orig(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    from . import telegram_app as ta

    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched
    cb._fleet_region_callbacks_installed = True


def install_fleet_region_hooks() -> None:
    from . import fleet_command_hooks as fch
    from . import telegram_app as ta

    if getattr(fch, "_fleet_region_hooks_installed", False):
        return

    patch_fleet_region_callbacks()

    _orig_post = ta._post_init

    async def _post_init(application: Application) -> None:
        await _orig_post(application)
        register_fleet_region_handlers(application)

    ta._post_init = _post_init
    fch._fleet_region_hooks_installed = True
    log.info("Filo bölge hook'ları kuruldu")
