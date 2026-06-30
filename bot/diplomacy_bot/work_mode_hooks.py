"""work_mode world — setfabric, ayarlar, callback, intent patch'leri."""

from __future__ import annotations

import logging
import re

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from .account_config import update_config_field
from .auth import resolve_account
from .dynamic_context import invalidate_snapshot_cache
from .telegram_helpers import user_required

log = logging.getLogger(__name__)

SETFABRIC_HELP = (
    "/setfabric isim uuid\n"
    "/setfabric isim own — kendi eyalet fabrikası\n"
    "/setfabric isim foreign — bölgedeki en iyi yabancı fabrika\n"
    "/setfabric isim world — dünya geneli en iyi fabrika (nomad)\n"
    "/setfabric isim auto — eski otomatik (build dahil)"
)

VALID_MODES = frozenset({"own", "foreign", "auto", "world"})


def _patch_work_mode_labels() -> None:
    from . import factory_board as fb
    from . import telegram_ui as ui

    fb.WORK_MODE_LABELS.setdefault("world", "Dünya")
    ui.WORK_MODE_TR.setdefault("world", "Dünya fabrikası")


def patch_setfabric_world() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_setfabric_world_patched", False):
        return

    @user_required
    async def cmd_setfabric_patched(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(context.args) < 2:
            await update.message.reply_text(SETFABRIC_HELP)
            return
        name, mode = context.args[0].lower(), context.args[1].lower()
        uid = ta._uid(update)
        if not resolve_account(name, uid):
            await update.message.reply_text("Hesap bulunamadı veya senin değil.")
            return
        if mode in VALID_MODES:
            update_config_field(name, work_mode=mode, preferred_factory_id=None)
            extra = ""
            if mode == "world":
                extra = "\n💡 Otomatik seyahat için ayarlardan «Seyahat otomatik» aç."
            await update.message.reply_text(f"✅ {name} work_mode={mode}{extra}")
            return
        if len(mode) > 20:
            update_config_field(name, work_mode="fixed", preferred_factory_id=mode)
            await update.message.reply_text(f"✅ {name} → sabit fabrika `{mode}`", parse_mode="Markdown")
            return
        await update.message.reply_text("Geçersiz mod. own|foreign|world|auto veya fabrika UUID.")

    ta.cmd_setfabric = cmd_setfabric_patched
    ta._setfabric_world_patched = True
    log.info("setfabric world modu patch kuruldu")


def patch_settings_world_button() -> None:
    from . import telegram_ui as ui

    if getattr(ui, "_settings_world_btn_installed", False):
        return

    _orig = ui.settings_inline_markup

    def settings_with_world(acc, *, user_accs=None):
        from .store import list_accounts

        markup = _orig(acc, user_accs=user_accs)
        rows = list(markup.inline_keyboard)
        for i, row in enumerate(rows):
            if any(b.callback_data in ("cfg:foreign", "cfg:own", "cfg:auto") for b in row):
                new_row = list(row)
                if not any(b.callback_data == "cfg:world" for b in new_row):
                    from .account_config import get_config

                    cfg = get_config(acc.name)
                    new_row.insert(
                        0,
                        InlineKeyboardButton(
                            "✓ Dünya" if cfg.work_mode == "world" else "Dünya fabrika",
                            callback_data="cfg:world",
                        ),
                    )
                rows[i] = new_row[:3]
                break
        return __import__("telegram").InlineKeyboardMarkup(rows)

    ui.settings_inline_markup = settings_with_world  # type: ignore[assignment]
    ui._settings_world_btn_installed = True


def patch_cfg_world_callback() -> None:
    from . import callbacks as cb

    if getattr(cb, "_cfg_world_installed", False):
        return

    _orig = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if data == "cfg:world":
            from .telegram_helpers import _send_settings

            acc = cb.resolve_account(default, uid) if default else None
            if acc:
                update_config_field(acc.name, work_mode="world", preferred_factory_id=None)
                invalidate_snapshot_cache(acc.name)
                acc = cb.resolve_account(acc.name, uid)
                await _send_settings(update, acc, edit=True, uid=uid)
            return

        if data == "fab:mode:world":
            acc = cb.resolve_account(default, uid) if default else None
            if acc:
                update_config_field(acc.name, work_mode="world", preferred_factory_id=None)
                invalidate_snapshot_cache(acc.name)
                try:
                    await query.answer("Mod: world")
                except Exception:
                    pass
                return await _orig(update, context, "action:myfactory", default, query, uid)

        return await _orig(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    cb._cfg_world_installed = True

    from . import telegram_app as ta

    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched


def patch_intent_world_mode() -> None:
    from . import intent_router as ir

    if getattr(ir, "_world_mode_intent_installed", False):
        return

    _orig = ir.try_fast_path

    def try_fast_path_patched(user_message: str, default_account: str):
        text = (user_message or "").strip()
        if re.search(r"dünya\s*fabrika|dunya\s*fabrika|world\s*mod|\bworld\b", text, re.I):
            if re.search(r"fabrika|mod|ayarla|setfabric", text, re.I):
                from .auth import resolve_account
                from .modules.agent_types import AgentResult

                acc = resolve_account(default_account, default_account)
                if acc:
                    update_config_field(acc.name, work_mode="world", preferred_factory_id=None)
                    return AgentResult(reply=f"✅ {acc.name} fabrika modu: `world`")
        return _orig(user_message, default_account)

    ir.try_fast_path = try_fast_path_patched
    ir._world_mode_intent_installed = True


def patch_factory_board_world_button() -> None:
    from . import factory_board as fb

    if getattr(fb, "_world_mode_btn_installed", False):
        return

    _orig = fb.factory_board_inline_markup

    def factory_board_inline_markup_patched(analysis: dict):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        mk = _orig(analysis)
        rows = list(mk.inline_keyboard)
        mode = str((analysis or {}).get("work_mode") or "own")
        for i, row in enumerate(rows):
            if any(b.callback_data == "fab:mode:foreign" for b in row):
                new_row = list(row)
                if not any(b.callback_data == "fab:mode:world" for b in new_row):
                    new_row.insert(
                        1,
                        InlineKeyboardButton(
                            "Dünya" + (" ✓" if mode == "world" else ""),
                            callback_data="fab:mode:world",
                        ),
                    )
                rows[i] = new_row[:4]
                break
        return InlineKeyboardMarkup(rows)

    fb.factory_board_inline_markup = factory_board_inline_markup_patched  # type: ignore[assignment]
    fb._world_mode_btn_installed = True


def install_work_mode_hooks() -> None:
    _patch_work_mode_labels()
    patch_setfabric_world()
    patch_settings_world_button()
    patch_cfg_world_callback()
    patch_intent_world_mode()
    patch_factory_board_world_button()
    from .press_like_intent import install_press_like_intent_hook

    install_press_like_intent_hook()
    from .health_sync import install_health_sync_hooks

    install_health_sync_hooks()
