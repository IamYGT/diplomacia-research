"""Özellik analizi — ham API verisinden aksiyon önerisi ve özet."""

from __future__ import annotations

from typing import Any

from .account_config import AccountConfig, CLASS_STAT_PRIORITY, DEFAULT_STAT_PRIORITY, get_config
from .modules.stats import resolve_priority
from .user_errors import format_ms


def _pct(progress: int, target: int) -> int:
    if target <= 0:
        return 0
    return min(100, int(progress * 100 / target))


def analyze_quests(quests: list[dict]) -> dict[str, Any]:
    claimable: list[dict] = []
    in_progress: list[dict] = []
    done: list[dict] = []
    pending_money = 0
    pending_xp = 0
    pending_diamonds = 0

    for q in quests:
        reward = q.get("reward") or {}
        prog = int(q.get("progress") or 0)
        target = int(q.get("target") or 0)
        if q.get("rewarded"):
            done.append(q)
            continue
        if prog >= target > 0:
            claimable.append(q)
            pending_money += int(reward.get("money") or 0)
            pending_xp += int(reward.get("xp") or 0)
            pending_diamonds += int(reward.get("diamonds") or 0)
        else:
            in_progress.append(q)

    # Yakın tamamlanacaklar (≥70%)
    almost = [
        q
        for q in in_progress
        if _pct(int(q.get("progress") or 0), int(q.get("target") or 1)) >= 70
    ]

    return {
        "claimable": claimable,
        "in_progress": in_progress,
        "done": done,
        "almost": almost,
        "claimable_count": len(claimable),
        "pending_money": pending_money,
        "pending_xp": pending_xp,
        "pending_diamonds": pending_diamonds,
        "total": len(quests),
    }


def analyze_wars(data: dict, cfg: AccountConfig | None = None) -> dict[str, Any]:
    cfg = cfg or AccountConfig("x")
    war = data.get("war")
    wars = list(data.get("wars") or [])
    items: list[dict] = []
    if war:
        items.append(war)
    for w in wars:
        if w and w not in items:
            items.append(w)

    active = [w for w in items if w and str(w.get("status", "")).lower() not in ("ended", "finished", "cancelled")]
    target = None
    if cfg.target_war_id:
        for w in active:
            if str(w.get("id")) == cfg.target_war_id:
                target = w
                break
    if not target and active:
        target = active[0]

    side = cfg.contribute_side
    if side == "auto" and target:
        side = target.get("my_side") or target.get("player_side") or "attacker"

    return {
        "active": active,
        "target": target,
        "can_contribute": bool(active) and cfg.war_enabled,
        "suggested_side": side,
        "war_count": len(active),
    }


def analyze_factories(
    factories: list[dict],
    work: dict | None,
    auto: dict | None,
    *,
    province: str | None = None,
) -> dict[str, Any]:
    work = work or {}
    auto = auto or {}
    working = bool(work.get("working"))
    work_factory_id = work.get("factory_id") or work.get("current_factory_id")
    work_ready = int(auto.get("next_work_in_ms") or 0) <= 0

    owned = len(factories)
    total_workers = sum(int(f.get("worker_count") or f.get("workers") or 0) for f in factories)

    tips: list[str] = []
    if not factories:
        tips.append("Fabrika yok — oyunda fabrika kur veya foreign moda geç")
    if not working and work_ready:
        tips.append("Work hazır — farm çalıştır")
    elif not work_ready:
        tips.append(f"Work bekleme: {format_ms(auto.get('next_work_in_ms'))}")
    if province and factories:
        tips.append(f"Eyalet: {province}")

    return {
        "owned": owned,
        "total_workers": total_workers,
        "working": working,
        "work_factory_id": work_factory_id,
        "work_ready": work_ready,
        "work_wait_ms": int(auto.get("next_work_in_ms") or 0),
        "tips": tips,
    }


def analyze_training(auto: dict, war: dict | None) -> dict[str, Any]:
    auto = auto or {}
    free = bool(auto.get("free_attack_available"))
    cd_ms = int(auto.get("free_attack_cooldown_ms") or 0)
    return {
        "has_war": bool(war),
        "war": war,
        "free_attack": free,
        "cooldown_ms": cd_ms,
        "ready": free and bool(war),
        "tips": (
            ["Ücretsiz antrenman saldırısı hazır"]
            if free and war
            else (
                [f"Antrenman CD: {format_ms(cd_ms)}"]
                if cd_ms > 0
                else (["Antrenman savaşı yok — oyunda aç"] if not war else ["Saldırı beklemede"])
            )
        ),
    }


def analyze_military(data: dict, ops: dict | None) -> dict[str, Any]:
    data = data or {}
    ops = ops or {}
    power = data.get("military_power")
    units = data.get("units") or {}
    unit_total = 0
    if isinstance(units, dict):
        unit_total = sum(int(v) for v in units.values() if isinstance(v, (int, float)))
    elif isinstance(units, list):
        unit_total = sum(int(u.get("count") or 0) for u in units if isinstance(u, dict))

    op = ops.get("operation") if isinstance(ops, dict) else None
    return {
        "power": power,
        "unit_total": unit_total,
        "units": units,
        "has_operation": bool(op),
        "joined_op": bool(ops.get("is_joined")) if isinstance(ops, dict) else False,
        "operation": op,
    }


def analyze_craft(profile: dict, auto: dict, cfg: AccountConfig) -> dict[str, Any]:
    diamonds = int(profile.get("diamonds") or 0)
    pills = int(auto.get("health_pills") or profile.get("health_pills") or 0)
    need = max(0, cfg.min_pill_stock - pills)
    batch = min(cfg.craft_diamond_batch, diamonds) if diamonds > 0 else 0
    can = batch > 0 and (need > 0 or pills < cfg.min_pill_stock)
    return {
        "diamonds": diamonds,
        "pills": pills,
        "need_pills": need,
        "suggested_batch": batch,
        "can_craft": can,
        "roi_note": "Her work ~+20 elmas (premium/hap döngüsü)",
    }


def analyze_passive(data: dict, cfg: AccountConfig, player_class: str | None = None) -> dict[str, Any]:
    pts = int(data.get("available_points") or 0)
    skills = data.get("passive_skills") or {}
    keys = list(skills.keys()) if isinstance(skills, dict) else []
    priority = resolve_priority(cfg, player_class, keys)
    next_skill = priority[0] if priority and pts > 0 else None
    return {
        "available": pts,
        "skills": skills,
        "priority": priority[:6],
        "next_skill": next_skill,
        "can_spend": pts > 0,
    }


def analyze_auto_status(status: dict) -> dict[str, Any]:
    status = status or {}
    work_ms = int(status.get("next_work_in_ms") or 0)
    pill_ms = int(status.get("pill_cooldown_ms") or 0)
    war_ms = int(status.get("next_war_in_ms") or 0)
    atk_ms = int(status.get("free_attack_cooldown_ms") or 0)
    return {
        "work_ready": work_ms <= 0,
        "work_ms": work_ms,
        "pill_ready": pill_ms <= 0,
        "pill_ms": pill_ms,
        "war_ready": war_ms <= 0,
        "war_ms": war_ms,
        "free_attack": bool(status.get("free_attack_available")),
        "attack_ms": atk_ms,
        "auto_work": bool(status.get("auto_work_active")),
        "auto_war": bool(status.get("auto_war_active")),
        "health": int(status.get("health") or 0),
        "health_max": int(status.get("health_max") or 100),
        "pills": int(status.get("health_pills") or 0),
        "regen": status.get("health_regen_amount"),
    }


def build_readiness(
    *,
    quests_analysis: dict | None = None,
    auto_analysis: dict | None = None,
    wars_analysis: dict | None = None,
    passive_analysis: dict | None = None,
    craft_analysis: dict | None = None,
    training_analysis: dict | None = None,
) -> dict[str, Any]:
    """Ek menü rozeti ve özet için kompakt hazırlık haritası."""
    qa = quests_analysis or {}
    aa = auto_analysis or {}
    wa = wars_analysis or {}
    pa = passive_analysis or {}
    ca = craft_analysis or {}
    ta = training_analysis or {}

    items: list[str] = []
    if qa.get("claimable_count"):
        items.append(f"📜 {qa['claimable_count']} görev ödülü (~{qa.get('pending_money', 0):,}₺)")
    if aa.get("work_ready"):
        items.append("🌾 Farm hazır")
    elif aa.get("work_ms"):
        items.append(f"🌾 Farm {format_ms(aa['work_ms'])}")
    if pa.get("can_spend"):
        items.append(f"⚡ {pa['available']} pasif puan")
    if ta.get("ready"):
        items.append("🏋️ Antrenman hazır")
    if wa.get("can_contribute") and wa.get("war_count"):
        items.append(f"⚔️ {wa['war_count']} aktif savaş")
    if ca.get("can_craft"):
        items.append(f"💎 Hap üret ({ca['suggested_batch']} elmas)")

    return {
        "highlights": items[:6],
        "quest_claimable": qa.get("claimable_count", 0),
        "work_ready": aa.get("work_ready", False),
        "passive_pts": pa.get("available", 0),
        "training_ready": ta.get("ready", False),
        "war_active": wa.get("war_count", 0),
        "craft_ready": ca.get("can_craft", False),
    }


def class_priority_hint(player_class: str | None) -> str:
    if not player_class:
        return ", ".join(DEFAULT_STAT_PRIORITY[:3])
    return ", ".join(CLASS_STAT_PRIORITY.get(player_class, DEFAULT_STAT_PRIORITY)[:3])
