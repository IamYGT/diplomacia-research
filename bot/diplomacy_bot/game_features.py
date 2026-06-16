"""Oyuncu özellikleri — API keşfi, analiz ve aksiyonlar."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .account_config import AccountConfig, get_config, update_config_field
from .feature_analysis import (
    analyze_auto_status,
    analyze_craft,
    analyze_factories,
    analyze_military,
    analyze_passive,
    analyze_quests,
    analyze_training,
    analyze_wars,
    build_readiness,
)
from .game_api import api, claim_ready_quests, get_profile, get_quests, list_countries
from .modules import economy, stats, training, war


def _err(data: Any, status: int) -> str:
    if isinstance(data, dict):
        return str(data.get("error") or data.get("message") or f"HTTP {status}")
    return f"HTTP {status}"


def _api_get(path: str, token: str, *, delay: float = 0.2) -> dict:
    st, data = api("GET", path, token, delay=delay)
    if st != 200:
        return {"ok": False, "status": st, "error": _err(data, st)}
    return {"ok": True, "data": data if isinstance(data, dict) else {"raw": data}}


def fetch_auto_status(token: str) -> dict:
    status = economy.get_auto_status(token) or {}
    return {"ok": bool(status), "status": status, "analysis": analyze_auto_status(status)}


def fetch_my_factories(token: str) -> dict:
    st, data = api("GET", "/factories/my", token, delay=0.2)
    if st != 200:
        return {"ok": False, "status": st, "error": _err(data, st)}
    factories = (data or {}).get("factories") or []
    return {"ok": True, "factories": factories, "raw": data}


def fetch_region_factories(token: str, *, page: int = 1, limit: int = 8) -> dict:
    st, data = api("GET", f"/factories/region?page={page}&limit={limit}", token, delay=0.25)
    if st != 200:
        return {"ok": False, "error": _err(data, st)}
    return {
        "ok": True,
        "factories": (data or {}).get("factories") or [],
        "province": (data or {}).get("province_name"),
        "raw": data,
    }


def fetch_work_status(token: str) -> dict:
    st, data = api("GET", "/factories/work-status", token, delay=0.2)
    if st != 200:
        return {"ok": False, "status": st, "error": _err(data, st)}
    return {"ok": True, "data": data if isinstance(data, dict) else {}}


def fetch_factory_board(token: str, account_name: str) -> dict:
    """Fabrika + work + auto + bölge — tek paket."""
    prof: dict = {}
    try:
        p = get_profile(token)
        prof = {"province": p.province_name, "diamonds": p.diamonds, "username": p.username}
    except Exception as e:
        prof = {"error": str(e)[:80]}

    def _my():
        return fetch_my_factories(token)

    def _work():
        return fetch_work_status(token)

    def _auto():
        return fetch_auto_status(token)

    def _region():
        return fetch_region_factories(token)

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_my = pool.submit(_my)
        f_work = pool.submit(_work)
        f_auto = pool.submit(_auto)
        f_reg = pool.submit(_region)
        my = f_my.result()
        work = f_work.result()
        auto = f_auto.result()
        region = f_reg.result()

    factories = my.get("factories") or [] if my.get("ok") else []
    work_data = work.get("data") if work.get("ok") else {}
    auto_status = auto.get("status") or {} if auto.get("ok") else {}
    region_list = region.get("factories") or [] if region.get("ok") else []

    cfg = get_config(account_name)
    pack = {
        "factories": factories,
        "work": work_data,
        "auto": auto_status,
        "region_factories": region_list,
        "province": prof.get("province") or region.get("province"),
        "profile": prof,
    }
    from .factory_board import analyze_factory_board_enriched

    analysis = analyze_factory_board_enriched(pack, cfg)
    return {
        "ok": my.get("ok") or work.get("ok"),
        **pack,
        "analysis": analysis,
        "owned_ids": analysis.get("owned_ids") or [],
        "region_ids": analysis.get("region_ids") or [],
    }


def run_factory_action(
    token: str,
    account_name: str,
    action: str,
    *,
    factory_id: str | None = None,
    amount: int | None = None,
    salary_rate: int | None = None,
    name: str | None = None,
    build_type: str | None = None,
    target_player_id: str | None = None,
    resource: str | None = None,
) -> dict:
    """Fabrika API aksiyonları — sonuç action_log için uygun."""
    cfg = get_config(account_name)
    action = action.strip().lower()
    result: dict[str, Any] = {"ok": False, "action": action, "factory_id": factory_id}

    def _msg(data: Any) -> str:
        if isinstance(data, dict):
            return str(data.get("message") or data.get("error") or "")[:300]
        return str(data)[:300]

    if action == "join":
        if not factory_id:
            return {**result, "error": "factory_id gerekli"}
        st, data = api("POST", "/factories/join", token, {"factory_id": factory_id}, delay=0.2)
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        if result["ok"]:
            update_config_field(account_name, preferred_factory_id=factory_id, work_mode="fixed")
            result["message"] = _msg(data) or "Fabrikaya katıldın"
        else:
            result["error"] = _err(data, st)
        return result

    if action == "leave":
        st, data = api("POST", "/factories/leave", token, {}, delay=0.2)
        result["ok"] = st in (200, 201)
        result["message"] = _msg(data) or "Fabrikadan ayrıldın"
        if not result["ok"]:
            result["error"] = _err(data, st)
        return result

    if action == "work":
        from .modules import factory as factory_mod

        cycle = factory_mod.run_work_cycle(token, cfg, factory_id, _api=api)
        result["ok"] = bool(cycle.get("ok"))
        result["earned"] = cycle.get("earned") or {}
        result["factory_id"] = cycle.get("factory_id") or factory_id
        if cycle.get("error"):
            result["error"] = cycle["error"]
        else:
            result["message"] = "Çalışma tamamlandı"
        return result

    if action == "build":
        bname = name or cfg.default_build_name or "BotFarm"
        btype = build_type or "elmas"
        st, data = api(
            "POST",
            "/factories/build",
            token,
            {"type": btype, "name": bname},
            delay=0.25,
        )
        new_id = None
        if isinstance(data, dict):
            new_id = (data.get("factory") or {}).get("id")
        result["factory_id"] = new_id
        result["ok"] = st in (200, 201) and bool(new_id)
        if result["ok"] and new_id:
            update_config_field(
                account_name,
                primary_factory_id=new_id,
                preferred_factory_id=new_id,
            )
            result["message"] = f"{bname} kuruldu"
        else:
            result["error"] = _err(data, st)
        return result

    if not factory_id:
        return {**result, "error": "factory_id gerekli"}

    if action == "close":
        st, data = api("POST", "/factories/close", token, {"factory_id": factory_id}, delay=0.25)
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        if result["ok"]:
            if cfg.primary_factory_id == factory_id:
                update_config_field(account_name, primary_factory_id=None)
            result["message"] = _msg(data) or "Fabrika kapatıldı"
        else:
            result["error"] = _err(data, st)
        return result

    if action == "withdraw":
        amt = amount if amount and amount > 0 else 999_999_999
        st, data = api(
            "POST",
            "/factories/withdraw",
            token,
            {"factory_id": factory_id, "amount": amt},
            delay=0.25,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        if result["ok"]:
            result["message"] = _msg(data) or "Para çekildi"
            if isinstance(data, dict):
                result["earned"] = data.get("withdrawn") or data.get("amount") or {}
        else:
            result["error"] = _err(data, st)
        return result

    if action == "withdraw_resources":
        res = resource or "altin"
        amt = amount if amount and amount > 0 else 999_999
        st, data = api(
            "POST",
            "/factories/withdraw-resources",
            token,
            {"factory_id": factory_id, "resource": res, "amount": amt},
            delay=0.25,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        result["message"] = _msg(data) if result["ok"] else None
        result["error"] = _err(data, st) if not result["ok"] else None
        return result

    if action == "level_up":
        st, data = api("POST", "/factories/level-up", token, {"factory_id": factory_id}, delay=0.25)
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        result["message"] = _msg(data) if result["ok"] else None
        result["error"] = _err(data, st) if not result["ok"] else None
        return result

    if action == "salary":
        rate = salary_rate if salary_rate is not None else cfg.default_salary_rate
        st, data = api(
            "POST",
            "/factories/salary",
            token,
            {"factory_id": factory_id, "salary_rate": rate},
            delay=0.25,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        if result["ok"]:
            update_config_field(account_name, default_salary_rate=rate)
            result["message"] = f"Maaş %{rate} ayarlandı"
        else:
            result["error"] = _err(data, st)
        return result

    if action == "rename":
        new_name = name or cfg.default_build_name
        st, data = api(
            "POST",
            "/factories/rename",
            token,
            {"factory_id": factory_id, "name": new_name},
            delay=0.2,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        result["message"] = _msg(data) if result["ok"] else None
        result["error"] = _err(data, st) if not result["ok"] else None
        return result

    if action == "fire" and target_player_id:
        st, data = api(
            "POST",
            "/factories/fire",
            token,
            {"factory_id": factory_id, "target_player_id": target_player_id},
            delay=0.25,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        result["message"] = _msg(data) if result["ok"] else None
        result["error"] = _err(data, st) if not result["ok"] else None
        return result

    if action == "reset_labor" and target_player_id:
        st, data = api(
            "POST",
            "/factories/reset-labor",
            token,
            {"factory_id": factory_id, "target_player_id": target_player_id},
            delay=0.25,
        )
        result["ok"] = st in (200, 201) and not (isinstance(data, dict) and data.get("error"))
        result["message"] = _msg(data) if result["ok"] else None
        result["error"] = _err(data, st) if not result["ok"] else None
        return result

    return {**result, "error": f"Bilinmeyen aksiyon: {action}"}


def fetch_military(token: str) -> dict:
    st, data = api("GET", "/military/me", token, delay=0.2)
    if st != 200:
        return {"ok": False, "status": st, "error": _err(data, st)}
    body = data if isinstance(data, dict) else {}
    return {"ok": True, "data": body, "analysis": analyze_military(body, {})}


def fetch_military_ops(token: str) -> dict:
    return _api_get("/military-ops/my", token)


def fetch_military_board(token: str) -> dict:
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_m = pool.submit(fetch_military, token)
        f_o = pool.submit(fetch_military_ops, token)
        mil = f_m.result()
        ops = f_o.result()
    ops_data = ops.get("data") if ops.get("ok") else {}
    if mil.get("ok"):
        mil["analysis"] = analyze_military(mil.get("data") or {}, ops_data or {})
    mil["ops"] = ops_data
    return mil


def fetch_training_war(token: str) -> dict:
    war = training.get_my_training_war(token)
    if not war:
        return {"ok": False, "error": "Antrenman savaşı yok", "war": None}
    return {"ok": True, "war": war}


def fetch_training_board(token: str, account_name: str) -> dict:
    auto = economy.get_auto_status(token) or {}
    war = training.get_my_training_war(token)
    cfg = get_config(account_name)
    analysis = analyze_training(auto, war)
    return {
        "ok": True,
        "war": war,
        "auto": auto,
        "analysis": analysis,
        "cfg_training": cfg.training_enabled,
    }


def run_training_attack(token: str, account_name: str) -> dict:
    board = fetch_training_board(token, account_name)
    analysis = board.get("analysis") or {}
    if not board.get("cfg_training"):
        return {"ok": False, "error": "Antrenman kapalı — hybrid/war/farm rolünde açık"}
    if not analysis.get("has_war"):
        return {"ok": False, "error": "Antrenman savaşı yok"}
    if not analysis.get("free_attack"):
        return {
            "ok": False,
            "skipped": "free_attack_cooldown",
            "detail": {"ms": analysis.get("cooldown_ms")},
        }
    cfg = get_config(account_name)
    result = training.try_free_attack(token, cfg)
    if result is None:
        return {"ok": False, "error": "Antrenman çalıştırılamadı"}
    if result.get("skipped"):
        return {"ok": False, "skipped": result["skipped"], "detail": result}
    return {
        "ok": bool(result.get("ok")),
        "result": result,
        "war": board.get("war"),
        "analysis": analysis,
    }


def run_war_contribute(token: str, account_name: str, *, war_id: str | None = None) -> dict:
    cfg = get_config(account_name)
    wars = fetch_wars(token)
    if not wars.get("ok"):
        return wars
    from .war_board import analyze_wars_enriched

    wa = analyze_wars_enriched(
        wars.get("data") or {},
        cfg,
        player_country=wars.get("player_country"),
    )
    if not wa.get("can_contribute"):
        return {"ok": False, "error": "Savaş katkısı kapalı — war/hybrid rolü gerekli"}
    if not wa.get("active"):
        return {"ok": False, "skipped": "no_active_war", "analysis": wa}
    if war_id:
        target_id = war_id
    elif cfg.target_war_id:
        target_id = cfg.target_war_id
    else:
        t = wa.get("target")
        target_id = str(t.get("id")) if t else None
    if not target_id:
        return {"ok": False, "skipped": "no_target_war", "analysis": wa}
    side = cfg.contribute_side
    if side == "auto":
        for w in wa.get("numbered") or []:
            if str(w.get("id")) == target_id:
                side = w.get("my_side") or "attacker"
                break
        else:
            side = "attacker"
    result = war.contribute(token, target_id, side)
    if result is None:
        return {"ok": False, "error": "Savaş katkısı çalıştırılamadı", "analysis": wa}
    if result.get("skipped"):
        return {"ok": False, "skipped": result["skipped"], "detail": result, "analysis": wa}
    result["war_id"] = target_id
    result["war_index"] = next(
        (w.get("index") for w in wa.get("numbered") or [] if str(w.get("id")) == target_id),
        None,
    )
    return {"ok": bool(result.get("ok")), "result": result, "analysis": wa}


def fetch_wars(token: str) -> dict:
    st, data = api("GET", "/wars/my-country", token, delay=0.2)
    if st != 200:
        return {"ok": False, "status": st, "error": _err(data, st)}
    body = data if isinstance(data, dict) else {}
    cfg = AccountConfig("_")
    return {"ok": True, "data": body, "analysis": analyze_wars(body, cfg)}


def fetch_war_board(token: str, account_name: str) -> dict:
    from .game_api import get_profile

    r = fetch_wars(token)
    if not r.get("ok"):
        return r
    cfg = get_config(account_name)
    try:
        prof = get_profile(token)
        country = prof.country_name
    except Exception:
        country = None
    from .war_board import analyze_wars_enriched

    r["player_country"] = country
    r["analysis"] = analyze_wars_enriched(r.get("data") or {}, cfg, player_country=country)
    r["war_ids"] = [str(w.get("id")) for w in r["analysis"].get("numbered") or [] if w.get("id")]
    return r


def fetch_quests(token: str) -> dict:
    try:
        quests = get_quests(token)
        analysis = analyze_quests(quests)
        return {"ok": True, "quests": quests, "analysis": analysis}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def claim_quests_smart(token: str) -> dict:
    board = fetch_quests(token)
    if not board.get("ok"):
        return board
    analysis = board.get("analysis") or {}
    if not analysis.get("claimable_count"):
        return {
            "ok": True,
            "results": [],
            "analysis": analysis,
            "message": "no_claimable",
        }
    results = claim_ready_quests(token)
    return {"ok": True, "results": results, "analysis": analysis}


def fetch_countries(token: str) -> dict:
    try:
        countries = list_countries(token)
        prof = get_profile(token)
        return {
            "ok": True,
            "countries": countries,
            "current_country": prof.country_name,
            "current_province": prof.province_name,
            "has_country": bool(prof.country_id),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_online(token: str) -> dict:
    t0 = time.perf_counter()
    st, data = api("GET", "/online", token, delay=0.15)
    latency = (time.perf_counter() - t0) * 1000
    if st == 200 and isinstance(data, dict):
        return {"ok": True, "data": data, "latency_ms": latency}
    st2, data2 = api("GET", "/online/players", token, delay=0.15)
    latency2 = (time.perf_counter() - t0) * 1000
    if st2 == 200:
        players = data2 if isinstance(data2, list) else (data2 or {}).get("players") or []
        return {"ok": True, "players": players, "count": len(players), "latency_ms": latency2}
    return {"ok": False, "error": _err(data2 if st2 != 200 else data, st2)}


def run_ping(token: str) -> dict:
    t0 = time.perf_counter()
    st, data = api("POST", "/players/ping", token, {}, delay=0.15)
    latency = (time.perf_counter() - t0) * 1000
    return {
        "ok": st in (200, 201),
        "status": st,
        "data": data,
        "latency_ms": latency,
    }


def run_craft_pills(token: str, account_name: str, *, diamonds: int | None = None) -> dict:
    cfg = get_config(account_name)
    try:
        prof = get_profile(token)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    auto = economy.get_auto_status(token) or {}
    analysis = analyze_craft(
        {"diamonds": prof.diamonds, "health_pills": prof.health_pills},
        auto,
        cfg,
    )
    batch = diamonds if diamonds is not None else analysis.get("suggested_batch", 0)
    if batch <= 0:
        return {"ok": False, "error": "Yeterli elmas yok veya craft gerekmiyor", "analysis": analysis}
    result = economy.craft_pills(token, batch)
    return {
        "ok": bool(result.get("ok")),
        "action": "craft",
        "crafted": batch,
        "diamonds": batch,
        "message": f"{batch} elmas → hap" if result.get("ok") else None,
        "status": result.get("status"),
        "data": result.get("data"),
        "analysis": analysis,
        "error": (
            str((result.get("data") or {}).get("error") or (result.get("data") or {}).get("message"))
            if not result.get("ok")
            else None
        ),
    }


def fetch_craft_board(token: str, account_name: str) -> dict:
    """Geriye uyumluluk — farm merkezine yönlendir."""
    board = fetch_farm_board(token, account_name)
    if not board.get("ok"):
        return board
    return {
        "ok": True,
        "analysis": board.get("analysis") or {},
        "profile": board.get("profile"),
        "auto": board.get("auto"),
    }


def fetch_passive_detail(token: str, account_name: str) -> dict:
    """Geriye uyumluluk — stat merkezi için fetch_stat_board kullan."""
    return fetch_stat_board(token, account_name)


def fetch_stat_board(token: str, account_name: str) -> dict:
    passive_data = stats.get_passive_skills(token) or {}
    if not isinstance(passive_data, dict):
        passive_data = {}

    player_class = None
    profile_pts = 0
    active_skills: dict = {}
    balance = 0
    diamonds = 0
    try:
        prof = get_profile(token)
        player_class = prof.player_class
        profile_pts = prof.passive_skill_points
        balance = int(prof.balance or 0)
        diamonds = int(prof.diamonds or 0)
    except Exception:
        prof = None

    st, prof_raw = api("GET", "/players/profile", token, delay=0.15)
    if st == 200 and isinstance(prof_raw, dict):
        player = prof_raw.get("player") or {}
        active_skills = player.get("skills") or {}
        if not player_class:
            player_class = player.get("player_class")
        if not profile_pts:
            profile_pts = int(player.get("passive_skill_points") or 0)
        if not balance:
            balance = int(player.get("balance") or player.get("gold") or 0)
        if not diamonds:
            diamonds = int(player.get("diamonds") or 0)

    if not passive_data and not active_skills:
        return {"ok": False, "error": "Stat verisi alınamadı"}

    cfg = get_config(account_name)
    pack = {
        "passive_data": passive_data,
        "active_skills": active_skills,
        "player_class": player_class,
        "profile_pts": profile_pts,
        "balance": balance,
        "diamonds": diamonds,
    }
    from .stat_board import analyze_stat_board_enriched

    analysis = analyze_stat_board_enriched(pack, cfg)
    return {
        "ok": True,
        **pack,
        "analysis": analysis,
        "skill_keys": analysis.get("skill_keys") or [],
        "active_skill_keys": analysis.get("active_skill_keys") or [],
        "passive_skill_keys": analysis.get("passive_skill_keys") or [],
    }


def run_skill_upgrade(
    token: str,
    account_name: str,
    *,
    skill: str,
    currency: str = "gold",
) -> dict:
    """Aktif stat yükselt (altın/elmas)."""
    r = stats.upgrade_skill(token, skill, currency)
    return {
        "ok": bool(r.get("ok")),
        "action": "upgrade",
        "skill": skill,
        "currency": r.get("currency") or currency,
        "new_level": r.get("new_level"),
        "pending_at": r.get("pending_at"),
        "cooldown_ms": r.get("cooldown_ms"),
        "cost": r.get("cost"),
        "required": r.get("required"),
        "error": r.get("error"),
        "data": r.get("data"),
    }


def run_skill_upgrade_priority(
    token: str,
    account_name: str,
    *,
    currency: str = "gold",
) -> dict:
    """DB stat_priority'deki ilk aktif statı bir kez yükselt."""
    pack = fetch_stat_board(token, account_name)
    if not pack.get("ok"):
        return {"ok": False, "error": pack.get("error") or "Stat paneli yok", "action": "upgrade"}
    analysis = pack.get("analysis") or {}
    primary = analysis.get("primary_active")
    if not primary:
        keys = analysis.get("active_skill_keys") or []
        primary = keys[0] if keys else None
    if not primary:
        return {"ok": False, "error": "Yükseltilecek aktif stat yok", "action": "upgrade"}
    return run_skill_upgrade(token, account_name, skill=primary, currency=currency)


def run_stat_auto_now(token: str, account_name: str) -> dict:
    """Pasif harca + altınla yükselt — tek seferlik otomasyon."""
    cfg = get_config(account_name)
    pack = fetch_stat_board(token, account_name)
    analysis = pack.get("analysis") or {}
    auto_status = analysis.get("auto_status") or {}
    if not cfg.stat_auto_enabled:
        return {
            "ok": False,
            "action": "auto",
            "error": "Otomatik kapalı — aç veya 💎 elmas kullan",
            "passive": [],
            "upgrades": [],
            "analysis": analysis,
            "idle_summary": auto_status.get("summary"),
        }
    stat = stats.run_stat_automation(token, cfg)
    passive = stat.get("passive") or []
    upgrades = stat.get("upgrades") or []
    ok = any(p.get("ok") for p in passive) or any(u.get("ok") for u in upgrades)
    return {
        "ok": ok,
        "action": "auto",
        "passive": passive,
        "upgrades": upgrades,
        "analysis": analysis,
        "idle_summary": auto_status.get("summary") if not ok else None,
        "error": None if ok else "Bakiye veya pasif puan yok",
    }


def run_stat_spend(
    token: str,
    account_name: str,
    *,
    skill: str | None = None,
    points: int | None = None,
) -> dict:
    """Tek skill veya öncelik sırasına göre tüm puanları harca."""
    cfg = get_config(account_name)
    data = stats.get_passive_skills(token)
    available = int(data.get("available_points") or 0)
    if available <= 0:
        return {"ok": False, "error": "Bekleyen pasif puan yok", "available": 0}

    if skill:
        pts = points if points and points > 0 else available
        pts = min(pts, available)
        r = stats.spend_passive(token, skill, pts)
        ok = bool(r.get("ok"))
        body = r.get("data") if isinstance(r.get("data"), dict) else {}
        new_lvl = body.get("new_level") or body.get("level")
        return {
            "ok": ok,
            "action": "spend",
            "skill": skill,
            "points": pts,
            "new_level": new_lvl,
            "error": str(body.get("error") or body.get("message") or "") if not ok else None,
            "data": body,
        }

    spent = stats.spend_available(token, cfg)
    if not spent:
        return {"ok": False, "error": "Harcanacak puan yok veya skill bulunamadı", "action": "spend"}
    first = spent[0]
    ok = bool(first.get("ok"))
    return {
        "ok": ok,
        "action": "spend",
        "spent_list": spent,
        "skill": first.get("skill"),
        "points": first.get("points"),
        "error": None if ok else str((first.get("data") or {}).get("error") or "harcama başarısız"),
    }


def fetch_farm_board(token: str, account_name: str) -> dict:
    """Farm + auto + work + profil — tek paket."""
    try:
        prof = get_profile(token)
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

    auto = economy.get_auto_status(token) or {}
    work = fetch_work_status(token)
    work_data = work.get("data") if work.get("ok") else {}

    cfg = get_config(account_name)
    pack = {
        "profile": prof,
        "auto": auto,
        "work": work_data,
    }
    from .farm_board import analyze_farm_board_enriched

    analysis = analyze_farm_board_enriched(pack, cfg)
    return {"ok": True, **pack, "analysis": analysis}


def run_farm_work(token: str, account_name: str) -> dict:
    from . import farmer

    r = farmer.run_quick_farm(token, account_name)
    return {
        "ok": r.ok,
        "action": "work",
        "message": "Çalışma tamamlandı" if r.ok else (r.error or "work başarısız"),
        "error": None if r.ok else r.error,
        "earned_money": r.earned_money,
        "earned_diamonds": r.earned_diamonds,
        "factory_id": r.factory_id,
        "farm_result": r,
    }


def run_farm_smart(token: str, account_name: str) -> dict:
    from . import farmer
    from .modules.orchestrator import tick_account

    t = tick_account(token, account_name)
    r = farmer._tick_to_farm(t)
    return {
        "ok": r.ok,
        "action": "smart",
        "message": "Akıllı döngü tamamlandı" if r.ok else (r.error or "döngü atlandı"),
        "error": None if r.ok else r.error,
        "earned_money": r.earned_money,
        "earned_diamonds": r.earned_diamonds,
        "factory_id": r.factory_id,
        "farm_result": r,
        "actions": r.actions,
    }


def run_use_pills(token: str, account_name: str) -> dict:
    result = economy.use_pills(token)
    ok = bool(result.get("ok"))
    err = result.get("error")
    if not ok and not err and isinstance(result.get("data"), dict):
        err = (result["data"] or {}).get("error") or (result["data"] or {}).get("message")
    return {
        "ok": ok,
        "action": "hap",
        "message": "Can dolduruldu" if ok else None,
        "error": err if not ok else None,
        "cooldown_ms": result.get("cooldown_ms"),
    }


def fetch_extras_readiness(token: str, account_name: str) -> dict:
    """Ek menü rozeti — paralel hafif probe."""

    def _quests():
        try:
            return analyze_quests(get_quests(token))
        except Exception:
            return {}

    def _auto():
        return analyze_auto_status(economy.get_auto_status(token) or {})

    def _wars():
        try:
            st, d = api("GET", "/wars/my-country", token, delay=0.15)
            if st == 200:
                return analyze_wars(d if isinstance(d, dict) else {}, get_config(account_name))
        except Exception:
            pass
        return {}

    def _passive():
        try:
            ps = stats.get_passive_skills(token)
            return analyze_passive(ps, get_config(account_name))
        except Exception:
            return {}

    def _craft():
        try:
            p = get_profile(token)
            auto = economy.get_auto_status(token) or {}
            return analyze_craft(
                {"diamonds": p.diamonds, "health_pills": p.health_pills},
                auto,
                get_config(account_name),
            )
        except Exception:
            return {}

    def _training():
        try:
            return analyze_training(economy.get_auto_status(token) or {}, training.get_my_training_war(token))
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        qa = pool.submit(_quests).result()
        aa = pool.submit(_auto).result()
        wa = pool.submit(_wars).result()
        pa = pool.submit(_passive).result()
        ca = pool.submit(_craft).result()
        ta = pool.submit(_training).result()

    readiness = build_readiness(
        quests_analysis=qa,
        auto_analysis=aa,
        wars_analysis=wa,
        passive_analysis=pa,
        craft_analysis=ca,
        training_analysis=ta,
    )
    return {
        "ok": True,
        "readiness": readiness,
        "quests": qa,
        "auto": aa,
        "wars": wa,
        "passive": pa,
        "craft": ca,
        "training": ta,
    }
