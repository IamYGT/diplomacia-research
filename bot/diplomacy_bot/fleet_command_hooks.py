"""Filo komuta Telegram komutları — telegram_app patch."""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .fleet_command import (
    assign_fleet_to_factory,
    bootstrap_fleet,
    format_batch_html,
    format_fleet_ops_status,
    format_next_steps_footer,
    set_fleet_roles,
    travel_fleet,
)
from .telegram_helpers import user_required
from .fleet_ui_markup import fleet_nav_inline_markup

log = logging.getLogger(__name__)
_REGISTERED = False


@user_required
async def cmd_fleetfactory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    arg = (context.args[0] if context.args else "main").strip()
    factory_id = None if arg.lower() == "main" else arg
    if factory_id and not re.match(r"^[0-9a-f-]{8,}$", factory_id, re.I):
        await msg.reply_text(
            "Kullanım:\n"
            "<code>/fleetfactory main</code> — ana hesabın fabrikası\n"
            "<code>/fleetfactory &lt;uuid&gt;</code>",
            parse_mode="HTML",
        )
        return
    batch = assign_fleet_to_factory(uid, factory_id=factory_id)
    await msg.reply_text(
        format_batch_html(
            "🏭 Filo fabrika atama",
            batch,
            footer=format_next_steps_footer(uid),
        ),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleettravel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    if not context.args:
        await msg.reply_text("Kullanım: <code>/fleettravel Hürmüz</code>", parse_mode="HTML")
        return
    province = " ".join(context.args)
    batch = travel_fleet(uid, province)
    await msg.reply_text(
        format_batch_html(f"🚶 Filo seyahat → {province}", batch),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetbootstrap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    role = "hybrid"
    limit = None
    if context.args:
        if context.args[0].isdigit():
            limit = int(context.args[0])
            if len(context.args) > 1:
                role = context.args[1]
        else:
            role = context.args[0]
            if len(context.args) > 1 and context.args[1].isdigit():
                limit = int(context.args[1])
    batch = bootstrap_fleet(uid, role=role, limit=limit)
    await msg.reply_text(
        format_batch_html(
            f"🚀 Filo bootstrap ({role})",
            batch,
            footer=format_next_steps_footer(uid),
        ),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetroles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    if not context.args:
        await msg.reply_text(
            "Kullanım: <code>/fleetroles hybrid</code> veya <code>/fleetroles farm 20</code>",
            parse_mode="HTML",
        )
        return
    role = context.args[0]
    limit = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else None
    batch = set_fleet_roles(uid, role, limit=limit)
    await msg.reply_text(
        format_batch_html(f"👥 Filo rol → {role}", batch),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleetinbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .fleet_inbox_import import format_inbox_import_footer, import_inbox_for_uid

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    batch = import_inbox_for_uid(uid)
    await msg.reply_text(
        format_batch_html(
            "📥 Filo inbox import",
            batch,
            footer=format_inbox_import_footer(uid, batch),
        ),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


@user_required
async def cmd_fleethelp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from .fleet_help import format_fleet_help_html

    msg = update.effective_message
    if msg:
        await msg.reply_text(format_fleet_help_html(), parse_mode="HTML")


@user_required
async def cmd_fleetops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    await msg.reply_text(format_fleet_ops_status(uid), parse_mode="HTML", reply_markup=fleet_nav_inline_markup())


@user_required
async def cmd_fleetrepair(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta
    from .fleet_autonomy_repair import repair_fleet_autonomy_for_uid

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    role = context.args[0] if context.args else "hybrid"
    batch = repair_fleet_autonomy_for_uid(uid, role=role)
    await msg.reply_text(
        format_batch_html("🛠 Filo otonomi onarım", batch, footer=format_next_steps_footer(uid)),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )


def register_fleet_command_handlers(application: Application) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    for name, handler in (
        ("fleetfactory", cmd_fleetfactory),
        ("fleettravel", cmd_fleettravel),
        ("fleetbootstrap", cmd_fleetbootstrap),
        ("fleetroles", cmd_fleetroles),
        ("fleetops", cmd_fleetops),
        ("fleetrepair", cmd_fleetrepair),
        ("fleetinbox", cmd_fleetinbox),
        ("fleethelp", cmd_fleethelp),
    ):
        application.add_handler(CommandHandler(name, handler))
    _REGISTERED = True
    log.info("Filo komuta komutları kayıtlı")


def install_fleet_command_hooks() -> None:
    from . import telegram_app as ta
    from .fleet_callbacks import install_fleet_command_callbacks
    from .fleet_ui_markup import patch_fleet_ui_buttons

    if getattr(ta, "_fleet_command_hooks_installed", False):
        return

    patch_fleet_ui_buttons()
    install_fleet_command_callbacks()

    _orig_post = ta._post_init

    async def _post_init(application: Application) -> None:
        await _orig_post(application)
        register_fleet_command_handlers(application)

    ta._post_init = _post_init
    ta._fleet_command_hooks_installed = True

    from .fleet_region_hooks import install_fleet_region_hooks

    install_fleet_region_hooks()

    _orig_fleet = ta.cmd_fleet

    @user_required
    async def cmd_fleet_patched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args and context.args[0].lower() in ("start", "baslat", "başlat", "go"):
            from .fleet_region_hooks import cmd_fleetstart

            context.args = context.args[1:]
            await cmd_fleetstart(update, context)
            return
        if context.args and context.args[0].lower() in ("repair", "onar", "fix"):
            await cmd_fleetrepair(update, context)
            return
        if context.args and context.args[0].lower() in ("status", "ops", "komuta", "audit"):
            uid = ta._uid(update)
            msg = update.effective_message
            if msg:
                await msg.reply_text(
                    format_fleet_ops_status(uid),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        await _orig_fleet(update, context)

    ta.cmd_fleet = cmd_fleet_patched

    _orig_help = ta.cmd_help

    @user_required
    async def cmd_help_patched(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args and context.args[0].lower() in ("filo", "fleet", "filo"):
            from .fleet_help import format_fleet_help_html
            from .telegram_ui import main_reply_keyboard

            msg = update.effective_message
            if msg:
                await msg.reply_text(
                    format_fleet_help_html(),
                    parse_mode="HTML",
                    reply_markup=main_reply_keyboard(),
                )
            return
        await _orig_help(update, context)

    ta.cmd_help = cmd_help_patched
    log.info("Filo komuta hook'ları kuruldu")
