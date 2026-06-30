#!/usr/bin/env python3
"""Canlı ygt probu — profil/auto uyumu, dashboard, hap, farm tick."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from diplomacy_bot.account_config import get_config  # noqa: E402
from diplomacy_bot.dynamic_context import snapshot_account  # noqa: E402
from diplomacy_bot.game_features import fetch_auto_status  # noqa: E402
from diplomacy_bot.game_features_health import install_game_features_health_patch  # noqa: E402
from diplomacy_bot.health_sync import health_dashboard_banner, work_health  # noqa: E402
from diplomacy_bot.modules import economy  # noqa: E402
from diplomacy_bot.modules.orchestrator import tick_account  # noqa: E402
from diplomacy_bot.store import get_account, init_db  # noqa: E402
from diplomacy_bot.work_mode_hooks import install_work_mode_hooks  # noqa: E402


def main() -> int:
    account = sys.argv[1] if len(sys.argv) > 1 else "ygt"
    init_db()
    install_work_mode_hooks()
    install_game_features_health_patch()

    acc = get_account(account)
    if not acc:
        print(json.dumps({"ok": False, "error": f"hesap yok: {account}"}, ensure_ascii=False))
        return 1

    snap = snapshot_account(acc, force_refresh=True)
    auto = economy.get_auto_status(acc.token) or {}
    profile_h = work_health(acc.token, auto_status=auto)
    auto_pack = fetch_auto_status(acc.token)
    cfg = get_config(acc.name)

    from diplomacy_bot import telegram_ui as ui

    dash = ui.format_dashboard_html(acc, snap)
    banner = health_dashboard_banner(snap)

    out = {
        "ok": not snap.get("error"),
        "account": account,
        "username": snap.get("username"),
        "profile_health_snap": snap.get("health"),
        "auto_status_health": auto.get("health"),
        "work_health": profile_h,
        "auto_board_health": auto_pack.get("analysis", {}).get("health"),
        "pills": snap.get("pills"),
        "pill_cooldown_ms": snap.get("pill_cooldown_ms"),
        "balance": snap.get("balance"),
        "diamonds": snap.get("diamonds"),
        "dashboard_has_can_zero_banner": "Can 0" in dash,
        "banner_preview": banner[:120] if banner else "",
        "role": cfg.role,
        "autofarm": acc.autofarm,
    }

    if profile_h < 100 and int(snap.get("pills") or 0) > 0 and int(snap.get("pill_cooldown_ms") or 0) <= 0:
        pill_res = economy.use_pills(acc.token)
        out["use_pills_attempt"] = {"ok": pill_res.get("ok"), "error": pill_res.get("error")}
        snap2 = snapshot_account(acc, force_refresh=True)
        out["health_after_pills"] = snap2.get("health")

    if "--tick" in sys.argv:
        tick = tick_account(acc.token, acc.name, cfg=cfg)
        from diplomacy_bot.autofarm_notify import format_autofarm_message

        out["tick"] = {
            "ok": tick.ok,
            "error": tick.error,
            "earned_money": tick.earned_money,
            "actions": tick.actions,
            "notify_preview": (format_autofarm_message(acc, tick) or "")[:200],
        }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    health_ok = out["work_health"] == out.get("profile_health_snap")
    board_ok = out["auto_board_health"] == out["work_health"]
    return 0 if out["ok"] and health_ok and board_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
