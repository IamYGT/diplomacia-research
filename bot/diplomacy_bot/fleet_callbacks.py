"""Filo komuta callback zinciri."""

from __future__ import annotations

from .fleet_command import (
    assign_fleet_to_factory,
    bootstrap_fleet,
    format_batch_html,
    format_fleet_ops_status,
    format_next_steps_footer,
    travel_fleet,
)
from .fleet_ui_markup import fleet_more_inline_markup, fleet_nav_inline_markup
from .telegram_navigation import callback_prefers_fresh_reply

_SIDE_EFFECT_LABELS = {
    "fleet:af:on:hybrid": "Hybrid bootstrap",
    "fleet:cmd:inbox": "Token inbox",
    "fleet:cmd:factory": "Fabrika",
    "fleet:cmd:travel": "Hürmüz",
    "fleet:cmd:bootstrap": "Hazırla",
    "fleet:cmd:repair": "Onar",
}


def fleet_menu_should_edit(data: str, query) -> bool:
    return not callback_prefers_fresh_reply(data, query)


async def open_fleet_more_menu(query, data: str) -> None:
    if not query or not query.message:
        return
    text = "⚙️ <b>Filo işlemleri</b> — birini seç:"
    kwargs = {"parse_mode": "HTML", "reply_markup": fleet_more_inline_markup()}
    if fleet_menu_should_edit(data, query):
        await query.edit_message_text(text, **kwargs)
    else:
        await query.message.reply_text(text, **kwargs)


async def reject_stale_fleet_command(query, data: str) -> bool:
    label = _SIDE_EFFECT_LABELS.get(data)
    if not label:
        return False
    from .fleet_action_guard import reject_stale_fleet_action

    return await reject_stale_fleet_action(query, label)


def install_fleet_command_callbacks() -> None:
    from . import callbacks as cb

    if getattr(cb, "_fleet_cmd_callbacks_installed", False):
        return

    _orig = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if data == "fleet:menu:main":
            from .telegram_helpers import _send_fleet

            await _send_fleet(update, context, edit=fleet_menu_should_edit(data, query))
            return
        if data == "fleet:menu:more":
            await open_fleet_more_menu(query, data)
            return
        if data == "fleet:af:on:hybrid":
            if await reject_stale_fleet_command(query, data):
                return
            batch = bootstrap_fleet(uid, role="hybrid")
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html(
                        "🔀 Hybrid bootstrap",
                        batch,
                        footer=format_next_steps_footer(uid),
                    ),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:inbox":
            if await reject_stale_fleet_command(query, data):
                return
            from .fleet_mission_service import start_fleet_autopilot_for_uid
            from .fleet_region_mission_ui import format_autopilot_html

            result = start_fleet_autopilot_for_uid(uid)
            if query and query.message:
                await query.message.reply_text(
                    format_autopilot_html(result),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:factory":
            if await reject_stale_fleet_command(query, data):
                return
            batch = assign_fleet_to_factory(uid)
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html(
                        "🏭 Filo fabrika atama",
                        batch,
                        footer=format_next_steps_footer(uid),
                    ),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:travel":
            if await reject_stale_fleet_command(query, data):
                return
            batch = travel_fleet(uid, "Hürmüz")
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html("🚶 Filo seyahat → Hürmüz", batch),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:bootstrap":
            if await reject_stale_fleet_command(query, data):
                return
            batch = bootstrap_fleet(uid, role="hybrid")
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html(
                        "🚀 Filo bootstrap",
                        batch,
                        footer=format_next_steps_footer(uid),
                    ),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:ops":
            if query and query.message:
                await query.message.reply_text(
                    format_fleet_ops_status(uid),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        if data == "fleet:cmd:repair":
            if await reject_stale_fleet_command(query, data):
                return
            from .fleet_autonomy_repair import repair_fleet_autonomy_for_uid

            batch = repair_fleet_autonomy_for_uid(uid)
            if query and query.message:
                await query.message.reply_text(
                    format_batch_html(
                        "🛠 Filo otonomi onarım",
                        batch,
                        footer=format_next_steps_footer(uid),
                    ),
                    parse_mode="HTML",
                    reply_markup=fleet_nav_inline_markup(),
                )
            return
        return await _orig(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    from . import telegram_app as ta

    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched
    cb._fleet_cmd_callbacks_installed = True
