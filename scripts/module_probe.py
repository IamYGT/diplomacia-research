#!/usr/bin/env python3
"""Modül bazlı canlı API probe — oyun state snapshot (read-only ağırlıklı)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parents[1] / "bot"
sys.path.insert(0, str(BOT))

from diplomacy_bot.account_config import get_config
from diplomacy_bot.account_pool import prepare_egress
from diplomacy_bot.account_runtime import account_context
from diplomacy_bot.game_api import api, get_profile
from diplomacy_bot.modules import economy, factory, premium, stats, training, war
from diplomacy_bot.modules.orchestrator import tick_account
from diplomacy_bot.stealth_client import reset_request_proxy, set_request_proxy
from diplomacy_bot.store import get_account, init_db, list_accounts


def probe_account(name: str, *, dry_tick: bool = False) -> dict:
    init_db()
    acc = get_account(name)
    if not acc:
        raise SystemExit(f"Hesap yok: {name}")
    cfg = get_config(name)
    out: dict = {"account": name, "proxy": acc.proxy_id}

    with account_context(acc):
        prof = get_profile(acc.token)
        out["profile"] = {
            "username": prof.username,
            "level": prof.level,
            "balance": prof.balance,
            "diamonds": prof.diamonds,
            "health": prof.health,
            "health_pills": prof.health_pills,
            "province": prof.province_name,
        }
        st_auto = economy.get_auto_status(acc.token)
        out["auto_status"] = {
            "next_work_in_ms": st_auto.get("next_work_in_ms"),
            "pill_cooldown_ms": st_auto.get("pill_cooldown_ms"),
            "health_pills": st_auto.get("health_pills"),
            "free_attack_available": st_auto.get("free_attack_available"),
            "auto_work_active": st_auto.get("auto_work_active"),
            "auto_war_active": st_auto.get("auto_war_active"),
        }
        ready, wait = economy.work_ready(acc.token)
        out["work_ready"] = {"ready": ready, "wait_ms": wait}

        ps = stats.get_passive_skills(acc.token)
        out["passive_skills"] = {
            "available_points": ps.get("available_points"),
            "keys": list((ps.get("passive_skills") or {}).keys()),
        }

        tw = training.get_my_training_war(acc.token)
        out["training_war"] = "none" if tw is None else {"id": tw.get("id"), "keys": list(tw.keys())[:8]}

        wars = war.get_my_country_wars(acc.token)
        out["wars_count"] = len(wars)

        fid, err = factory.resolve_factory_id(acc.token, cfg)
        out["factory_resolve"] = {"id": fid, "error": err, "work_mode": cfg.work_mode}

        out["is_premium"] = premium.is_premium(acc.token)

        if dry_tick:
            out["tick"] = {
                "ok": False,
                "note": "dry_tick disabled — use --tick to run one orchestrator cycle",
            }

    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("account", nargs="?", default="ygt")
    p.add_argument("--tick", action="store_true", help="Bir orchestrator tick çalıştır (state değiştirir)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.tick:
        acc = get_account(args.account)
        if not acc:
            print("Hesap yok")
            return 1
        with account_context(acc):
            r = tick_account(acc.token, acc.name)
        data = {
            "account": acc.name,
            "ok": r.ok,
            "error": r.error,
            "earned_money": r.earned_money,
            "earned_diamonds": r.earned_diamonds,
            "factory_id": r.factory_id,
            "actions": r.actions,
        }
    else:
        data = probe_account(args.account)

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for k, v in data.items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
