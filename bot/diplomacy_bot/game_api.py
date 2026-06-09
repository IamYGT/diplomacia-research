from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import API_BASE, FARM_DELAY_SEC


@dataclass
class Profile:
    player_id: str
    username: str
    balance: int
    diamonds: int
    xp: int
    level: int
    health: int
    health_pills: int
    onboarding_step: int | None
    country_id: str | None = None
    country_name: str | None = None
    province_name: str | None = None
    reputation: int | None = None


def api(method: str, path: str, token: str, body: dict | None = None, delay: float = FARM_DELAY_SEC) -> tuple[int, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; DiplomacyYGTBot/1.0)",
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    time.sleep(delay)
    req = urllib.request.Request(API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw.strip().startswith("{") else {"raw": raw[:300]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"error": raw[:300]}


def get_profile(token: str) -> Profile:
    st, d = api("GET", "/players/profile", token, delay=0.3)
    if st != 200:
        raise RuntimeError(d.get("error") or f"profile HTTP {st}")
    p = d.get("player", {})
    return Profile(
        player_id=str(p.get("id", "")),
        username=str(p.get("username", "?")),
        balance=int(p.get("balance") or 0),
        diamonds=int(p.get("diamonds") or 0),
        xp=int(p.get("xp") or 0),
        level=int(p.get("level") or 0),
        health=int(p.get("health") or 0),
        health_pills=int(p.get("health_pills") or 0),
        onboarding_step=p.get("onboarding_step"),
        country_id=p.get("country_id"),
        country_name=p.get("country_name"),
        province_name=p.get("province_name"),
        reputation=int(p.get("reputation") or 0) if p.get("reputation") is not None else None,
    )


def list_countries(token: str) -> list[dict]:
    st, d = api("GET", "/countries", token, delay=0.3)
    if st != 200:
        raise RuntimeError(d.get("error") or f"countries HTTP {st}")
    return d.get("countries") or []


def select_country(token: str, country_id: str) -> dict:
    st, d = api("POST", "/countries/select", token, {"country_id": country_id}, delay=0.5)
    if st not in (200, 201):
        raise RuntimeError(d.get("error") or d.get("message") or f"select HTTP {st}")
    return d


def auto_assign_country(token: str) -> dict:
    st, d = api("POST", "/countries/auto-assign", token, {}, delay=0.5)
    if st not in (200, 201):
        raise RuntimeError(d.get("error") or d.get("message") or f"auto-assign HTTP {st}")
    return d


def get_quests(token: str) -> list[dict]:
    st, d = api("GET", "/quests", token, delay=0.3)
    if st != 200:
        raise RuntimeError(d.get("error") or f"quests HTTP {st}")
    return d.get("quests") or []


def claim_quest(token: str, quest_key: str) -> dict:
    st, d = api("POST", f"/quests/{quest_key}/claim", token, {}, delay=0.5)
    if st not in (200, 201):
        raise RuntimeError(d.get("error") or d.get("message") or f"claim HTTP {st}")
    return d


def claim_ready_quests(token: str) -> list[dict]:
    """Tamamlanmış ama ödülü alınmamış görevleri claim et."""
    results: list[dict] = []
    for q in get_quests(token):
        key = q.get("quest_key")
        if not key or q.get("rewarded"):
            continue
        prog = int(q.get("progress") or 0)
        target = int(q.get("target") or 0)
        if prog >= target > 0:
            try:
                results.append({"quest_key": key, "ok": True, "data": claim_quest(token, key)})
            except Exception as e:
                results.append({"quest_key": key, "ok": False, "error": str(e)})
    return results


def use_pills(token: str) -> dict:
    st, d = api("POST", "/auto/use-pills", token, {}, delay=0.5)
    if st not in (200, 201):
        raise RuntimeError(d.get("error") or d.get("message") or f"pills HTTP {st}")
    return d


def get_my_wars(token: str) -> dict:
    st, d = api("GET", "/wars/my-country", token, delay=0.3)
    if st != 200:
        raise RuntimeError(d.get("error") or f"wars HTTP {st}")
    return d


def find_country_by_name(countries: list[dict], query: str) -> dict | None:
    q = query.lower().strip()
    if not q:
        return None
    for c in countries:
        if q in (c.get("name") or "").lower():
            return c
    for c in countries:
        name = (c.get("name") or "").lower()
        if any(part in name for part in q.split() if len(part) >= 3):
            return c
    return None


def ping(token: str) -> tuple[int, Any]:
    return api("POST", "/players/ping", token, {}, delay=0.2)


def daily_claim(token: str) -> tuple[int, Any]:
    return api("POST", "/players/daily-claim", token, {}, delay=0.5)


def ensure_factory(token: str) -> str | None:
    from .factory_service import ensure_factory as _ensure

    return _ensure(token)


def farm_once(token: str, factory_id: str | None = None) -> dict:
    from .factory_service import run_work_cycle

    return run_work_cycle(token, factory_id)
