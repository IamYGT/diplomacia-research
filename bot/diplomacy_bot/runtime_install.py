"""Runtime hook'ları — büyük dosyalara dokunmadan davranış güncelleme."""

from __future__ import annotations

import html
import logging

log = logging.getLogger(__name__)

_INSTALLED = False


def patch_dashboard_release_badge() -> None:
    from . import telegram_ui as ui
    from .bot_updates import release_for_version
    from .version import get_version

    if getattr(ui, "_release_badge_installed", False):
        return

    _orig = ui.format_dashboard_html

    def format_dashboard_html_patched(acc, snap=None):
        body = _orig(acc, snap)
        ver = get_version()
        rel = release_for_version(ver)
        if rel:
            codename = html.escape(str(rel.get("codename") or ""))
            badge = f"🆕 v{html.escape(ver)} — {codename}" if codename else f"🆕 v{html.escape(ver)}"
        else:
            badge = f"🆕 v{html.escape(ver)}"
        return f"<i>{badge}</i>\n{body}"

    ui.format_dashboard_html = format_dashboard_html_patched  # type: ignore[assignment]
    ui._release_badge_installed = True
    log.info("Dashboard sürüm rozeti hook kuruldu")


def patch_easy_mode_ui() -> None:
    """Klavye, yardım, dashboard — 35+ sade arayüz."""
    from . import telegram_ui as ui
    from .easy_mode import (
        EASY_MENU_LABELS,
        dashboard_headline,
        format_welcome_easy_html,
        main_reply_keyboard_easy,
        simplify_dashboard_html,
    )
    from .help_easy import format_help_easy_html

    from .easy_role import war_ui_enabled

    if getattr(ui, "_easy_mode_installed", False):
        return

    ui.MENU_LABELS.update(EASY_MENU_LABELS)
    _orig_norm = ui.normalize_menu_text

    def normalize_menu_text_patched(text: str) -> str | None:
        key = text.strip().lower()
        hit = EASY_MENU_LABELS.get(key)
        if hit:
            return hit
        return _orig_norm(text)

    ui.normalize_menu_text = normalize_menu_text_patched
    ui.main_reply_keyboard = main_reply_keyboard_easy  # type: ignore[assignment]

    _orig_help = ui.format_help_html
    ui.format_help_html = format_help_easy_html  # type: ignore[assignment]
    ui._format_help_html_legacy = _orig_help

    _orig_welcome = ui.format_welcome_html

    def format_welcome_patched(uid, account_name, *, gemini_ok, linked):
        return format_welcome_easy_html(uid, account_name, gemini_ok=gemini_ok, linked=linked)

    ui.format_welcome_html = format_welcome_patched  # type: ignore[assignment]

    _orig_dash = ui.format_dashboard_html

    def format_dashboard_easy(acc, snap=None):
        from .dynamic_context import snapshot_account

        snap = snap or snapshot_account(acc)
        body = _orig_dash(acc, snap)
        headline = dashboard_headline(
            snap,
            autofarm=bool(snap.get("autofarm") or acc.autofarm),
            war_enabled=war_ui_enabled(acc.name),
        )
        return f"{headline}\n\n{simplify_dashboard_html(body)}"

    # dashboard_view patch may wrap later — easy patch runs before badge in install order
    ui.format_dashboard_html = format_dashboard_easy  # type: ignore[assignment]

    ui._easy_mode_installed = True
    log.info("Kolay mod UI patch kuruldu (klavye, yardım, dashboard)")


def patch_telegram_dispatch() -> None:
    from . import telegram_app as ta
    from .telegram_easy import handle_easy_menu_action

    if getattr(ta, "_easy_dispatch_installed", False):
        return

    _orig = ta._dispatch_menu

    async def _dispatch_menu(update, context, action):
        if await handle_easy_menu_action(action, update, context):
            return
        await _orig(update, context, action)

    ta._dispatch_menu = _dispatch_menu
    ta._easy_dispatch_installed = True
    log.info("Kolay mod klavye dispatch patch kuruldu")


def patch_cmd_start_onboarding() -> None:
    from . import telegram_app as ta
    from .keyboard_reply import user_reply_keyboard
    from .telegram_helpers import user_required
    from .telegram_onboarding import maybe_send_onboarding_guide

    if getattr(ta, "_onboarding_start_installed", False):
        return

    _orig = ta.cmd_start

    @user_required
    async def cmd_start_patched(update, context):
        uid = ta._uid(update)
        default = ta._default_account(context, uid)
        acc = ta.resolve_account(default, uid) if default else None
        linked = acc is not None
        async with user_reply_keyboard(uid):
            await _orig(update, context)
        await maybe_send_onboarding_guide(
            update, linked=linked, telegram_user_id=uid, account_name=acc.name if acc else None
        )

    ta.cmd_start = cmd_start_patched
    ta._onboarding_start_installed = True
    log.info("/start onboarding rehberi hook kuruldu")


def patch_reply_keyboard_entries() -> None:
    """connect, yardım, tüm komutlar — uid'ye göre klavye."""
    from . import telegram_app as ta
    from .keyboard_reply import patch_all_handler_keyboards, user_reply_keyboard

    if getattr(ta, "_reply_keyboard_entries_installed", False):
        return

    patch_all_handler_keyboards()

    _orig_dispatch = ta._dispatch_menu

    async def _dispatch_menu_patched(update, context, action):
        uid = ta._uid(update)
        async with user_reply_keyboard(uid):
            await _orig_dispatch(update, context, action)

    ta._dispatch_menu = _dispatch_menu_patched

    ta._reply_keyboard_entries_installed = True
    log.info("Reply klavye uid patch (tüm handler'lar) kuruldu")


def install_easy_hooks() -> None:
    from . import callbacks as cb
    from . import telegram_app as ta
    from .telegram_easy import (
        handle_easy_callback,
        register_easy_commands_extra,
        register_easy_handlers,
    )

    if getattr(ta, "_easy_hook_installed", False):
        return

    register_easy_commands_extra()

    _orig_post = ta._post_init

    async def _post_init(application):
        await _orig_post(application)
        register_easy_handlers(application)

    ta._post_init = _post_init

    _orig_cb = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if await handle_easy_callback(data, query, uid):
            return
        return await _orig_cb(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched

    ta._easy_hook_installed = True
    log.info("Kolay mod callback + komut hook kuruldu")


def patch_ai_agent_fast_paths() -> None:
    from . import ai_agent

    if getattr(ai_agent, "_extra_fast_paths_installed", False):
        return

    _orig = ai_agent.run_agent

    def run_agent_patched(
        user_message,
        default_account="ercan2",
        *,
        allow_confirm=False,
        telegram_user_id=None,
    ):
        if not allow_confirm:
            from .store import get_account

            acc = get_account(default_account)
            if acc:
                from .intent_easy_fast import try_easy_fast_path
                from .intent_mission_fast import try_mission_fast_path
                from .intent_war_contrib_fast import try_war_contrib_fast_path

                easy = try_easy_fast_path(user_message, acc)
                if easy is not None:
                    return easy
                mission_fast = try_mission_fast_path(user_message, acc)
                if mission_fast is not None:
                    return mission_fast
                contrib_fast = try_war_contrib_fast_path(user_message, acc)
                if contrib_fast is not None:
                    return contrib_fast
        return _orig(
            user_message,
            default_account,
            allow_confirm=allow_confirm,
            telegram_user_id=telegram_user_id,
        )

    ai_agent.run_agent = run_agent_patched  # type: ignore[assignment]
    ai_agent._extra_fast_paths_installed = True
    log.info("AI agent ek fast-path hook kuruldu (kolay, görev, katkı)")


def install_mission_and_account_hooks() -> None:
    from . import callbacks as cb
    from . import telegram_app as ta
    from .telegram_account_cmds import register_account_handlers
    from .telegram_mission import (
        handle_mission_callback,
        register_mission_commands_extra,
        register_mission_handlers,
    )

    if getattr(ta, "_mission_hook_installed", False):
        return

    _orig_post = ta._post_init

    async def _post_init(application):
        register_mission_commands_extra()
        await _orig_post(application)
        register_mission_handlers(application)
        register_account_handlers(application)

    ta._post_init = _post_init

    _orig_cb = cb.handle_callback

    async def handle_callback_patched(update, context, data, default, query, uid):
        if await handle_mission_callback(data, query, uid):
            return
        return await _orig_cb(update, context, data, default, query, uid)

    cb.handle_callback = handle_callback_patched
    if hasattr(ta, "_handle_callback"):
        ta._handle_callback = handle_callback_patched

    ta._mission_hook_installed = True
    log.info("Görev + setmain hook kuruldu")


def install_all_runtime_hooks() -> None:
    """main.py'den tek çağrı — tüm runtime yamaları."""
    global _INSTALLED
    if _INSTALLED:
        return
    from .war_contribute_format import patch_war_contribute_shims

    patch_war_contribute_shims()
    patch_easy_mode_ui()
    patch_dashboard_release_badge()
    patch_ai_agent_fast_paths()
    patch_telegram_dispatch()
    patch_cmd_start_onboarding()
    patch_reply_keyboard_entries()

    from .dashboard_flood import install_dashboard_flood_patch

    install_dashboard_flood_patch()

    from .settings_easy import install_settings_easy_patch

    install_settings_easy_patch()

    from .telegram_updates import install_updates_post_init

    install_updates_post_init()
    install_mission_and_account_hooks()
    install_easy_hooks()

    from .telegram_tabs import install_tab_hooks

    install_tab_hooks()

    from .token_recovery_hooks import install_token_recovery_hooks

    install_token_recovery_hooks()

    from .connect_save import wire_save_account

    wire_save_account()

    from .autofarm_runtime import install_autofarm_notify_patch

    install_autofarm_notify_patch()

    from .connect_hooks import install_connect_hooks

    install_connect_hooks()

    from .work_mode_hooks import install_work_mode_hooks

    install_work_mode_hooks()

    from .feature_scheduler import install_feature_scheduler_hook

    install_feature_scheduler_hook()
    _INSTALLED = True
    log.info("Tüm runtime hook'lar kuruldu")
