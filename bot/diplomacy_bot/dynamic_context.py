from __future__ import annotations

import time

"""Canlı oyun + bot config özeti — AI koç ve planlayıcı için."""

from .account_config import get_config, normalize_role, role_label
from .store import (
    Account,
    delete_game_snapshot,
    game_snapshot_age_sec,
    get_account,
    get_game_snapshot,
    list_accounts,
    save_game_snapshot,
)

_SNAPSHOT_CACHE: dict[str, tuple[float, dict]] = {}
_SNAPSHOT_TTL_SEC = float(__import__("os").environ.get("SNAPSHOT_CACHE_TTL_SEC", "20"))
_SNAPSHOT_STALE_SEC = float(__import__("os").environ.get("SNAPSHOT_STALE_SEC", "90"))

# Dashboard okuma — UI thread'inde düşük delay (interactive_fast ile uyumlu)
_SNAPSHOT_API_DELAY = float(__import__("os").environ.get("SNAPSHOT_API_DELAY_SEC", "0.08"))


def _cache_put(name: str, row: dict) -> dict:
    if not row.get("_live"):
        return row
    now = time.time()
    _SNAPSHOT_CACHE[name] = (now, row)
    save_game_snapshot(name, row, ttl_sec=_SNAPSHOT_STALE_SEC)
    return row


def _cache_get_memory(account_name: str, *, max_age: float) -> dict | None:
    entry = _SNAPSHOT_CACHE.get(account_name)
    if not entry:
        return None
    ts, cached = entry
    if time.time() - ts >= max_age:
        return None
    if not cached.get("_live"):
        return None
    return dict(cached)


def _cache_get_db(account_name: str, *, max_age: float) -> dict | None:
    row = get_game_snapshot(account_name, max_age_sec=max_age)
    if row and row.get("_live"):
        _SNAPSHOT_CACHE[account_name] = (time.time(), row)
        return row
    return None


def put_snapshot_cache(name: str, row: dict) -> dict:
    """Bellek + SQLite önbelleğe yaz (dashboard ikinci aşama enrich)."""
    return _cache_put(name, row)


def _snapshot_live(acc: Account, *, enrich: bool = True) -> dict:
    """Profil + auto + pasif — tek thread (contextvars/proxy korunur)."""
    from . import game_api

    cfg = get_config(acc.name)
    row: dict = {
        "name": acc.name,
        "proxy": acc.proxy_id,
        "autofarm": acc.autofarm,
        "role": normalize_role(cfg.role),
        "work_mode": cfg.work_mode,
        "premium_hub": cfg.is_premium_hub,
        "factory_id": cfg.preferred_factory_id,
        "war_enabled": cfg.war_enabled,
        "training_enabled": cfg.training_enabled,
        "account_name": acc.name,
        "runtime_state": acc.runtime_state,
    }
    d = _SNAPSHOT_API_DELAY
    try:
        st, prof_raw = game_api.api("GET", "/players/profile", acc.token, delay=d)
        if st != 200 or not isinstance(prof_raw, dict):
            raise RuntimeError((prof_raw or {}).get("error") or f"profile HTTP {st}")
        p = prof_raw.get("player") or {}
        st_a, auto_raw = game_api.api("GET", "/auto/status", acc.token, delay=d)
        auto = auto_raw if st_a == 200 and isinstance(auto_raw, dict) else {}
        st_ps, ps_raw = game_api.api("GET", "/players/passive-skills", acc.token, delay=d)
        ps = ps_raw if st_ps == 200 and isinstance(ps_raw, dict) else {}
        row.update(
            {
                "username": str(p.get("username") or "?"),
                "level": int(p.get("level") or 0),
                "class": p.get("player_class"),
                "province": p.get("province_name"),
                "country": p.get("country_name"),
                "balance": int(p.get("balance") or 0),
                "diamonds": int(p.get("diamonds") or 0),
                "health": int(p.get("health") or 0),
                "pills": int(p.get("health_pills") or 0),
                "premium": bool(p.get("is_premium")),
                "passive_points": int(p.get("passive_skill_points") or 0),
                "premium_until": p.get("premium_until"),
                "premium_days_left": p.get("premium_days_left"),
            }
        )
        from .dashboard_readiness import enrich_snapshot_row, skills_from_profile_player

        row["active_skills"] = skills_from_profile_player(p)
        row["work_ready"] = int(auto.get("next_work_in_ms") or 0) <= 0
        row["work_wait_ms"] = int(auto.get("next_work_in_ms") or 0)
        row["pill_cooldown_ms"] = int(auto.get("pill_cooldown_ms") or 0)
        row["free_attack"] = bool(auto.get("free_attack_available"))
        row["free_attack_cooldown_ms"] = int(auto.get("free_attack_cooldown_ms") or 0)
        row["passive_available"] = int(ps.get("available_points") or 0)
        row["passive_keys"] = list((ps.get("passive_skills") or {}).keys())[:5]
        row["auto_work_active"] = bool(auto.get("auto_work_active"))
        row["auto_war_active"] = bool(auto.get("auto_war_active"))
        row["_live"] = True
        row["fetched_at"] = time.time()
        enrich_snapshot_row(acc, row, api_delay=d, network=enrich)
    except Exception as e:
        row["error"] = str(e)[:120]
    return row


def snapshot_account(acc: Account, *, force_refresh: bool = False, enrich: bool = True) -> dict:
    """Canlı probe — bellek + SQLite önbellek."""
    key = acc.name
    if not force_refresh:
        cached = _cache_get_memory(key, max_age=_SNAPSHOT_TTL_SEC)
        if cached:
            return cached
        cached = _cache_get_db(key, max_age=_SNAPSHOT_TTL_SEC)
        if cached:
            return cached
    row = _snapshot_live(acc, enrich=enrich)
    if row.get("error") or not row.get("_live"):
        return row
    return _cache_put(key, row)


def peek_snapshot_cache(account_name: str, *, allow_stale: bool = False) -> dict | None:
    """TTL içindeyse canlı API çağırmadan panel verisi."""
    limit = _SNAPSHOT_STALE_SEC if allow_stale else _SNAPSHOT_TTL_SEC
    cached = _cache_get_memory(account_name, max_age=limit)
    if cached:
        return cached
    return _cache_get_db(account_name, max_age=limit)


def snapshot_cache_age_sec(account_name: str) -> float | None:
    mem = _SNAPSHOT_CACHE.get(account_name)
    if mem:
        return time.time() - mem[0]
    return game_snapshot_age_sec(account_name)


def is_snapshot_fresh(account_name: str) -> bool:
    age = snapshot_cache_age_sec(account_name)
    return age is not None and age < _SNAPSHOT_TTL_SEC


def invalidate_snapshot_cache(account_name: str | None = None) -> None:
    from .dashboard_readiness import invalidate_readiness_cache

    if account_name:
        _SNAPSHOT_CACHE.pop(account_name, None)
        delete_game_snapshot(account_name)
        invalidate_readiness_cache(account_name)
    else:
        _SNAPSHOT_CACHE.clear()
        delete_game_snapshot(None)
        invalidate_readiness_cache()


def build_ai_context(default_account: str, *, telegram_user_id: int | None = None) -> str:
    """Gemini system prompt'a eklenecek dinamik blok."""
    from .auth import scoped_list_accounts

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
    if telegram_user_id:
        others = [
            a.name
            for a in scoped_list_accounts(telegram_user_id)
            if a.name != default_account
        ][:5]
    else:
        others = []
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
        f"• Görev: {role_label(cfg.role)}\n"
        f"• Fabrika modu: `{cfg.work_mode}`"
        + (f" → `{cfg.preferred_factory_id}`" if cfg.preferred_factory_id else "")
        + "\n"
        f"• Premium hub: {'evet' if cfg.is_premium_hub else 'hayır'}\n"
        f"• Stat önceliği: {', '.join(cfg.stat_priority[:4])}\n"
        f"• Training: {'on' if cfg.training_enabled else 'off'} | Savaş: {'on' if cfg.war_enabled else 'off'}\n"
        f"• Hap craft: {'on' if cfg.craft_pills_when_low else 'off'} (min {cfg.min_pill_stock})"
    )
