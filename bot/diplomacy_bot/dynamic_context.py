from __future__ import annotations

"""Canlı oyun + bot config özeti — AI koç ve planlayıcı için."""

from .account_config import get_config
from .modules import economy, stats
from .store import Account, get_account, list_accounts


def snapshot_account(acc: Account) -> dict:
    from . import game_api

    cfg = get_config(acc.name)
    row: dict = {
        "name": acc.name,
        "proxy": acc.proxy_id,
        "autofarm": acc.autofarm,
        "work_mode": cfg.work_mode,
        "premium_hub": cfg.is_premium_hub,
        "factory_id": cfg.preferred_factory_id,
        "war_enabled": cfg.war_enabled,
        "training": cfg.training_enabled,
    }
    try:
        p = game_api.get_profile(acc.token)
        row.update(
            {
                "username": p.username,
                "level": p.level,
                "class": p.player_class,
                "province": p.province_name,
                "country": p.country_name,
                "balance": p.balance,
                "diamonds": p.diamonds,
                "health": p.health,
                "pills": p.health_pills,
                "premium": p.is_premium,
                "passive_points": p.passive_skill_points,
            }
        )
        auto = economy.get_auto_status(acc.token)
        row["work_ready"] = int(auto.get("next_work_in_ms") or 0) <= 0
        row["free_attack"] = bool(auto.get("free_attack_available"))
        ps = stats.get_passive_skills(acc.token)
        row["passive_available"] = int(ps.get("available_points") or 0)
        row["passive_keys"] = list((ps.get("passive_skills") or {}).keys())[:5]
    except Exception as e:
        row["error"] = str(e)[:120]
    return row


def build_ai_context(default_account: str) -> str:
    """Gemini system prompt'a eklenecek dinamik blok."""
    lines = ["CANLI DURUM (probe):"]
    acc = get_account(default_account)
    if acc:
        s = snapshot_account(acc)
        lines.append(
            f"- {s.get('name')}: lv{s.get('level')} {s.get('class') or '?'} | "
            f"{s.get('province') or '?'} | 💰{s.get('balance', '?')} 💎{s.get('diamonds', '?')} | "
            f"can {s.get('health')}/100 hap {s.get('pills')} | "
            f"pasif_puan={s.get('passive_available', 0)} | work_ready={s.get('work_ready')} | "
            f"mod={s.get('work_mode')} hub={s.get('premium_hub')}"
        )
        if s.get("passive_keys"):
            lines.append(f"  pasif_skills: {', '.join(s['passive_keys'])}")
        if s.get("error"):
            lines.append(f"  hata: {s['error']}")
    others = [a.name for a in list_accounts() if a.name != default_account][:5]
    if others:
        lines.append(f"Diğer hesaplar: {', '.join(others)}")
    lines.append(
        "ÖNERİLER: pasif_puan>0 → stat harca; work_ready → farm; eyalet≠fabrika → foreign mod; "
        "premium hub → auto/work sadece aynı eyalette."
    )
    return "\n".join(lines)


def format_plan_summary(account_name: str) -> str:
    cfg = get_config(account_name)
    acc = get_account(account_name)
    proxy = acc.proxy_id if acc else "?"
    return (
        f"📋 *Plan — {account_name}* (`{proxy}`)\n"
        f"• Fabrika modu: `{cfg.work_mode}`"
        + (f" → `{cfg.preferred_factory_id}`" if cfg.preferred_factory_id else "")
        + "\n"
        f"• Premium hub: {'evet' if cfg.is_premium_hub else 'hayır'}\n"
        f"• Stat önceliği: {', '.join(cfg.stat_priority[:4])}\n"
        f"• Training: {'on' if cfg.training_enabled else 'off'} | Savaş: {'on' if cfg.war_enabled else 'off'}\n"
        f"• Hap craft: {'on' if cfg.craft_pills_when_low else 'off'} (min {cfg.min_pill_stock})"
    )
