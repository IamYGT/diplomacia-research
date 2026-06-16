from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from ..account_config import CLASS_STAT_PRIORITY, AccountConfig, DEFAULT_STAT_PRIORITY
from ..game_api import api as default_api, get_profile

ApiFn = Callable[..., tuple[int, Any]]

# upgrade 429 throttle (kalıcı oyun-side) — run_stat_automation ortak noktası (farmer/orchestrator/stat_queue).
# bot-side cooldown POST 429'da set edilmez (dashboard/profile kilitlemesin), bu yüzden ayrı throttle.
_LAST_UPGRADE_429_AT: float = 0.0
_UPGRADE_THROTTLE_SEC = 600


def normalize_upgrade_type(currency: str) -> str:
    """Oyun API: type = money | diamond (gold/altin/elmas değil)."""
    cur = (currency or "gold").strip().lower()
    if cur in ("diamond", "diamonds", "elmas"):
        return "diamond"
    return "money"


def format_upgrade_error(body: dict, api_type: str = "money") -> str:
    """API `required` alanı — yetersiz bakiye/elmas mesajı."""
    required = body.get("required")
    if required is not None:
        try:
            amt_s = f"{int(required):,}".replace(",", ".")
        except (TypeError, ValueError):
            amt_s = str(required)
        if api_type == "money":
            return f"Yetersiz bakiye. Gerekli: {amt_s} ₺"
        return f"Yetersiz elmas. Gerekli: {amt_s} 💎"
    err = body.get("error") or body.get("message")
    return str(err or "Yükseltme başarısız")


def pending_seconds_remaining(active_raw: dict, skill: str) -> int | None:
    """Profil skills — pending bitişine kalan saniye (çoklu alan adı)."""
    if not isinstance(active_raw, dict):
        return None
    for ms_key in (f"{skill}_pending_ms", f"{skill}_cooldown_ms", f"{skill}_remaining_ms"):
        ms = active_raw.get(ms_key)
        if ms is not None:
            try:
                return max(0, int(ms) // 1000)
            except (TypeError, ValueError):
                pass
    at = (
        active_raw.get(f"{skill}_pending_at")
        or active_raw.get(f"{skill}_pending_until")
        or active_raw.get(f"{skill}_pending_end")
    )
    if at is None:
        return None
    try:
        if isinstance(at, (int, float)):
            ts = float(at)
            if ts > 1e12:
                ts /= 1000.0
            sec = int(ts - datetime.now(timezone.utc).timestamp())
            return max(0, sec)
        raw = str(at).strip()
        if not raw:
            return None
        if raw.isdigit():
            ts = float(raw)
            if ts > 1e12:
                ts /= 1000.0
            sec = int(ts - datetime.now(timezone.utc).timestamp())
            return max(0, sec)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        end = datetime.fromisoformat(raw)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        sec = int((end - datetime.now(timezone.utc)).total_seconds())
        return max(0, sec)
    except (ValueError, TypeError, OSError):
        return None


def skill_is_pending(active_skills: dict, skill: str) -> bool:
    """Cooldown devam ediyor mu — süre bitince veya seviye yakalandıysa hayır."""
    if not isinstance(active_skills, dict):
        return False
    pending_lvl = active_skills.get(f"{skill}_pending")
    has_at = active_skills.get(f"{skill}_pending_at")
    if not pending_lvl and not has_at:
        return False
    if pending_lvl is not None:
        try:
            cur = active_skills.get(skill)
            cur_lvl = int(cur.get("level") if isinstance(cur, dict) else cur or 0)
            if cur_lvl >= int(pending_lvl):
                return False
        except (TypeError, ValueError):
            pass
    sec = pending_seconds_remaining(active_skills, skill)
    if sec is not None:
        return sec > 0
    if has_at:
        return True
    return bool(pending_lvl)


def any_skill_pending(active_skills: dict) -> bool:
    if not isinstance(active_skills, dict):
        return False
    keys = [k for k in active_skills if isinstance(k, str) and "_pending" not in k]
    return any(skill_is_pending(active_skills, k) for k in keys)


def nearest_pending_seconds(active_skills: dict) -> int | None:
    """En yakın pending bitişi (sn)."""
    if not isinstance(active_skills, dict):
        return None
    keys = [k for k in active_skills if isinstance(k, str) and "_pending" not in k]
    secs = [
        s
        for k in keys
        if skill_is_pending(active_skills, k)
        for s in [pending_seconds_remaining(active_skills, k)]
        if s is not None and s > 0
    ]
    return min(secs) if secs else None


def seconds_until_pending_at(pending_at: str | None) -> int | None:
    """ISO pending_at → kalan saniye."""
    if not pending_at:
        return None
    return pending_seconds_remaining({"_x_pending_at": pending_at}, "_x")


def resolve_priority(cfg: AccountConfig, player_class: str | None, passive_keys: list[str]) -> list[str]:
    """Sınıf + mevcut pasif skill anahtarlarına göre harcama sırası."""
    base = list(cfg.stat_priority) if cfg.stat_priority != DEFAULT_STAT_PRIORITY else []
    if not base and player_class:
        base = list(CLASS_STAT_PRIORITY.get(player_class, DEFAULT_STAT_PRIORITY))
    if not base:
        base = list(DEFAULT_STAT_PRIORITY)
    # API'de açık olan pasifleri öne al
    ordered: list[str] = []
    for k in passive_keys:
        if k not in ordered:
            ordered.append(k)
    for k in base:
        if k not in ordered:
            ordered.append(k)
    return ordered


def get_passive_skills(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("GET", "/players/passive-skills", token, delay=0.2)
    if st != 200:
        return {}
    return data if isinstance(data, dict) else {}


def spend_passive(token: str, skill: str, points: int, *, _api: ApiFn = default_api) -> dict:
    st, data = _api(
        "POST",
        "/players/passive-skills/spend",
        token,
        {"skill": skill, "points": points},
        delay=0.3,
    )
    return {"ok": st in (200, 201), "status": st, "skill": skill, "points": points, "data": data}


def upgrade_skill(
    token: str,
    skill: str,
    currency: str = "gold",
    *,
    _api: ApiFn = default_api,
) -> dict:
    """Aktif stat yükselt — POST /players/skills/upgrade (type: money|diamond)."""
    api_type = normalize_upgrade_type(currency)
    st, data = _api(
        "POST",
        "/players/skills/upgrade",
        token,
        {"skill": skill, "type": api_type},
        delay=0.3,
    )
    body = data if isinstance(data, dict) else {}
    err = body.get("error") or body.get("message")
    pending_at = body.get("pending_at")
    success = body.get("success") is True
    has_required = body.get("required") is not None
    ok = bool(
        st in (200, 201)
        and (success or pending_at)
        and not (err and not pending_at)
        and not has_required
    )
    new_lvl = body.get("target_level") or body.get("new_level") or body.get("level")
    if new_lvl is None and isinstance(body.get("skill"), dict):
        new_lvl = body["skill"].get("level")
    ui_currency = "gold" if api_type == "money" else "diamond"
    error_msg = None
    if not ok:
        error_msg = format_upgrade_error(body, api_type) if has_required or err else "Yükseltme başarısız"
    return {
        "ok": ok,
        "status": st,
        "skill": skill,
        "currency": ui_currency,
        "api_type": api_type,
        "new_level": new_lvl,
        "pending_at": pending_at,
        "cooldown_ms": body.get("cooldown_ms"),
        "cost": body.get("cost"),
        "required": body.get("required"),
        "data": body,
        "error": error_msg,
    }


def run_stat_automation(
    token: str,
    cfg: AccountConfig,
    *,
    max_upgrades: int = 1,
    _api: ApiFn = default_api,
) -> dict:
    """Pasif harca + altınla yükselt — farm / orchestrator ortak."""
    if not cfg.stat_auto_enabled:
        return {"passive": [], "upgrades": []}
    # upgrade 429 throttle: her deneme profile'a yük bindirip dashboard'u yavaşlatıyor.
    global _LAST_UPGRADE_429_AT
    if time.time() - _LAST_UPGRADE_429_AT < _UPGRADE_THROTTLE_SEC:
        return {"passive": [], "upgrades": []}
    passive = spend_available(token, cfg, _api=_api)
    upgrades = auto_upgrade_gold(
        token, cfg, max_starts=max(1, max_upgrades), _api=_api
    )
    if any(u.get("status") == 429 for u in upgrades):
        _LAST_UPGRADE_429_AT = time.time()
    return {"passive": passive, "upgrades": upgrades}


def auto_upgrade_gold(
    token: str,
    cfg: AccountConfig,
    *,
    max_starts: int = 1,
    min_balance_reserve: int = 0,
    _api: ApiFn = default_api,
) -> list[dict]:
    """Öncelik sırasına göre altın (money) ile yükselt — cooldown'daki skill atlanır."""
    if not cfg.stat_auto_enabled:
        return []
    try:
        prof = get_profile(token)
        if int(prof.balance or 0) <= min_balance_reserve:
            return []
    except Exception:
        pass
    results: list[dict] = []
    active = get_active_skills(token, _api=_api)
    if not active:
        return results
    base_keys = [k for k in active if "_pending" not in k]
    priority = resolve_active_priority(cfg, base_keys)
    started = 0
    for skill in priority:
        if started >= max(1, max_starts):
            break
        if skill_is_pending(active, skill):
            continue
        r = upgrade_skill(token, skill, "gold", _api=_api)
        results.append(r)
        if r.get("ok"):
            started += 1
            active = get_active_skills(token, _api=_api) or active
            try:
                from ..stat_queue import note_pending_wake

                note_pending_wake(
                    cfg.account_name,
                    pending_at=r.get("pending_at"),
                    cooldown_ms=r.get("cooldown_ms"),
                )
            except Exception:
                pass
            continue
        err = str(r.get("error") or "").lower()
        body = r.get("data") if isinstance(r.get("data"), dict) else {}
        err += " " + str(body.get("error") or body.get("message") or "").lower()
        bucket = _err_bucket(err)
        if bucket in ("funds", "max"):
            continue
        break
    return results


def resolve_active_priority(cfg: AccountConfig, active_keys: list[str]) -> list[str]:
    """DB stat_priority — sadece profildeki aktif skill anahtarları."""
    ordered: list[str] = []
    for k in cfg.stat_priority or []:
        if k in active_keys and k not in ordered:
            ordered.append(k)
    for k in active_keys:
        if k not in ordered:
            ordered.append(k)
    if not ordered:
        ordered = list(DEFAULT_STAT_PRIORITY)
    return ordered


def get_active_skills(token: str, *, _api: ApiFn = default_api) -> dict:
    st, data = _api("GET", "/players/profile", token, delay=0.15)
    if st != 200 or not isinstance(data, dict):
        return {}
    player = data.get("player") or {}
    skills = player.get("skills") or {}
    return skills if isinstance(skills, dict) else {}


def _err_bucket(err: str) -> str:
    e = (err or "").lower()
    if any(x in e for x in ("yetersiz", "insufficient", "not enough", "bakiye", "para yok", "altın", "altin", "gold")):
        return "funds"
    if any(x in e for x in ("max", "maksimum", "limit", "cap", "seviye")):
        return "max"
    return "other"


def spend_available(token: str, cfg: AccountConfig, *, _api: ApiFn = default_api) -> list[dict]:
    """Öncelik listesine göre tüm pasif puanları harca."""
    results: list[dict] = []
    data = get_passive_skills(token, _api=_api)
    points = int(data.get("available_points") or 0)
    if points <= 0:
        return results
    passive = data.get("passive_skills") or {}
    passive_keys = list(passive.keys())
    try:
        prof = get_profile(token)
        player_class = prof.player_class
    except Exception:
        player_class = None
    priority = resolve_priority(cfg, player_class, passive_keys)
    for skill in priority:
        if points <= 0:
            break
        r = spend_passive(token, skill, points, _api=_api)
        results.append(r)
        if r["ok"]:
            points = 0
            break
        err = str((r.get("data") or {}).get("error") or "").lower()
        if "invalid" in err or "geçersiz" in err or "bulunamad" in err:
            continue
        break
    return results
