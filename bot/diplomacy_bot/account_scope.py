"""Çoklu hesap izolasyonu — UI fallback, intent ve easy resolve sertleştirme."""

from __future__ import annotations

import contextvars
import logging
import re

log = logging.getLogger(__name__)

_intent_uid: contextvars.ContextVar[int | None] = contextvars.ContextVar("intent_uid", default=None)
_MULTI_ACC_RE = re.compile(r"tüm\s*hesap|hesaplar\s*durum|multi\s*hesap", re.I)
_orig_try_fast_path = None


def bind_intent_uid(uid: int | None):
    return _intent_uid.set(uid)


def reset_intent_uid(token) -> None:
    _intent_uid.reset(token)


def run_with_intent_uid(uid: int | None, fn):
    token = bind_intent_uid(uid)
    try:
        return fn()
    finally:
        reset_intent_uid(token)


def patch_ui_safe_fallbacks() -> None:
    """list_accounts() fallback kaldır — user_accs verilmezse boş liste (sızıntı yok)."""
    from . import telegram_ui as ui

    if getattr(ui, "_scope_fallback_installed", False):
        return

    _orig_fa = ui.format_accounts_html
    _orig_ff = ui.format_fleet_html
    _orig_fi = ui.fleet_inline_markup
    _orig_dash = ui.dashboard_inline_markup

    from .accounts_picker import (
        accounts_inline_markup as picker_accounts_markup,
        format_accounts_html as picker_accounts_html,
    )

    def format_accounts_html(default_name, accs=None):
        safe = accs if accs is not None else []
        uid = safe[0].telegram_user_id if safe else 0
        return picker_accounts_html(default_name, safe, telegram_user_id=uid or None)

    def format_fleet_html(active_name, accs=None):
        return _orig_ff(active_name, accs if accs is not None else [])

    def fleet_inline_markup(active_name, accs=None):
        return _orig_fi(active_name, accs if accs is not None else [])

    def dashboard_safe(acc, snap=None, *, user_accs=None):
        return _orig_dash(acc, snap, user_accs=user_accs if user_accs is not None else [])

    ui.format_accounts_html = format_accounts_html  # type: ignore[assignment]
    ui.format_fleet_html = format_fleet_html  # type: ignore[assignment]
    ui.fleet_inline_markup = fleet_inline_markup  # type: ignore[assignment]
    ui.dashboard_inline_markup = dashboard_safe  # type: ignore[assignment]
    ui._scope_fallback_installed = True

    _orig_settings = ui.settings_inline_markup
    _orig_accounts = ui.accounts_inline_markup

    def settings_inline_markup_safe(acc, *, user_accs=None):
        return _orig_settings(acc, user_accs=user_accs if user_accs is not None else [])

    def accounts_inline_markup_safe(default_name, accs=None):
        safe = accs if accs is not None else []
        uid = safe[0].telegram_user_id if safe else 0
        return picker_accounts_markup(default_name, safe, telegram_user_id=uid or None)

    ui.settings_inline_markup = settings_inline_markup_safe  # type: ignore[assignment]
    ui.accounts_inline_markup = accounts_inline_markup_safe  # type: ignore[assignment]
    rebootstrap_ui_consumers(ui.format_accounts_html, ui.accounts_inline_markup)
    log.info("UI hesap fallback güvenli moda alındı")


def rebootstrap_ui_consumers(fmt, markup) -> None:
    """Hook sonrası telegram_helpers / telegram_app / callbacks stale ref yenile."""
    from .accounts_screen import send_accounts_picker

    for mod_name in ("telegram_helpers", "telegram_app", "callbacks"):
        mod = __import__(f"diplomacy_bot.{mod_name}", fromlist=[mod_name])
        if hasattr(mod, "format_accounts_html"):
            mod.format_accounts_html = fmt  # type: ignore[attr-defined]
        if hasattr(mod, "accounts_inline_markup"):
            mod.accounts_inline_markup = markup  # type: ignore[attr-defined]
        if hasattr(mod, "_send_accounts_picker"):
            mod._send_accounts_picker = send_accounts_picker  # type: ignore[attr-defined]


def _rebind_accounts_ui_consumers(fmt, markup) -> None:
    rebootstrap_ui_consumers(fmt, markup)


def patch_intent_multi_account() -> None:
    global _orig_try_fast_path
    from . import intent_router as ir

    if getattr(ir, "_scoped_multi_acc_installed", False):
        return

    _orig_try_fast_path = ir.try_fast_path

    def try_fast_path_scoped(user_message: str, default_account: str):
        text = (user_message or "").strip()
        uid = _intent_uid.get()
        if uid and _MULTI_ACC_RE.search(text):
            from . import game_api
            from .ai_agent import AgentResult
            from .auth import scoped_list_accounts

            lines: list[str] = []
            for a in scoped_list_accounts(uid)[:10]:
                try:
                    p = game_api.get_profile(a.token)
                    lines.append(
                        f"• *{a.name}* {p.username} lv{p.level} 💰{p.balance:,} `{a.proxy_id}`"
                    )
                except Exception as e:
                    lines.append(f"• *{a.name}*: {e}")
            return AgentResult(reply="\n\n".join(lines) if lines else "Hesap yok.")
        return _orig_try_fast_path(user_message, default_account)

    ir.try_fast_path = try_fast_path_scoped  # type: ignore[assignment]
    ir._scoped_multi_acc_installed = True
    log.info("Intent çoklu hesap sorgusu uid ile kapsamlandı")


def patch_telegram_easy_resolve() -> None:
    from . import telegram_easy as te

    if getattr(te, "_scoped_resolve_installed", False):
        return

    def _resolve_account(name: str | None, uid: int):
        from .auth import resolve_account, scoped_list_accounts

        accs = scoped_list_accounts(uid)
        if not accs:
            return None, accs
        if name:
            acc = resolve_account(name.strip().lower(), uid)
            return acc, accs
        return accs[0], accs

    te._resolve_account = _resolve_account
    te._scoped_resolve_installed = True
    log.info("telegram_easy resolve_account uid ile sertleştirildi")


def patch_telegram_app_intent_uid() -> None:
    from . import telegram_app as ta

    if getattr(ta, "_intent_uid_bind_installed", False):
        return

    _orig_run_ai = ta._run_ai

    async def _run_ai_patched(update, context, text):
        uid = ta._uid(update)
        token = bind_intent_uid(uid)
        try:
            return await _orig_run_ai(update, context, text)
        finally:
            reset_intent_uid(token)

    ta._run_ai = _run_ai_patched
    ta._intent_uid_bind_installed = True


def patch_ai_agent_intent_uid() -> None:
    from . import ai_agent as ag

    if getattr(ag, "_intent_uid_bind_installed", False):
        return

    _orig = ag.run_agent

    def run_agent_patched(*args, **kwargs):
        uid = kwargs.get("telegram_user_id")

        def _inner():
            return _orig(*args, **kwargs)

        return run_with_intent_uid(uid, _inner)

    ag.run_agent = run_agent_patched
    ag._intent_uid_bind_installed = True


def patch_cmd_confirm_uid() -> None:
    import asyncio

    from . import ai_agent
    from . import telegram_app as ta

    if getattr(ta, "_confirm_uid_installed", False):
        return

    _orig = ta.cmd_confirm

    @ta.user_required
    async def cmd_confirm_patched(update, context):
        pending = context.user_data.get("pending_actions")
        if not pending:
            await update.message.reply_text("Bekleyen işlem yok.")
            return
        uid = ta._uid(update)
        default = ta._default_account(context, uid)
        result = await asyncio.to_thread(
            ai_agent.run_confirmed,
            pending,
            default,
            telegram_user_id=uid,
        )
        context.user_data.pop("pending_actions", None)
        await ta._reply_long(update, result.reply)

    ta.cmd_confirm = cmd_confirm_patched
    ta._confirm_uid_installed = True


def patch_press_like_scope() -> None:
    from . import intent_router as ir

    if getattr(ir, "_press_like_scope_installed", False):
        return

    _orig = ir.try_fast_path

    def try_fast_path_patched(user_message: str, default_account: str):
        uid = _intent_uid.get()
        from .auth import resolve_account
        from .press_like_intent import try_press_like_fast_path

        acc = resolve_account(default_account, uid) if uid else None
        if acc:
            hit = try_press_like_fast_path(user_message, acc)
            if hit is not None:
                return hit
        return _orig(user_message, default_account)

    ir.try_fast_path = try_fast_path_patched  # type: ignore[assignment]
    ir._press_like_scope_installed = True


def patch_runtime_ai_fast_scope() -> None:
    from . import ai_agent

    if getattr(ai_agent, "_scoped_fast_paths_installed", False):
        return

    _orig_patched = ai_agent.run_agent

    def run_agent_scoped(*args, **kwargs):
        if not kwargs.get("allow_confirm"):
            uid = kwargs.get("telegram_user_id")
            default = args[1] if len(args) > 1 else kwargs.get("default_account", "ercan2")
            from .auth import resolve_account

            acc = resolve_account(default, uid) if uid else None
            if acc:
                from .intent_easy_fast import try_easy_fast_path
                from .intent_mission_fast import try_mission_fast_path
                from .intent_war_contrib_fast import try_war_contrib_fast_path

                for fn in (try_easy_fast_path, try_mission_fast_path, try_war_contrib_fast_path):
                    hit = fn(args[0] if args else kwargs.get("user_message", ""), acc)
                    if hit is not None:
                        return hit
        return _orig_patched(*args, **kwargs)

    ai_agent.run_agent = run_agent_scoped  # type: ignore[assignment]
    ai_agent._scoped_fast_paths_installed = True


def install_account_scope_hooks() -> None:
    from .account_session import install_default_account_main_hook
    from .account_store_guard import install_store_guard_hooks

    install_store_guard_hooks()
    install_default_account_main_hook()
    patch_ui_safe_fallbacks()
    patch_intent_multi_account()
    patch_telegram_easy_resolve()
    patch_telegram_app_intent_uid()
    patch_ai_agent_intent_uid()
    patch_cmd_confirm_uid()
    patch_press_like_scope()
    patch_runtime_ai_fast_scope()
