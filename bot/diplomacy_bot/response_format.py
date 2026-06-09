from __future__ import annotations

from typing import Any


def format_profile(data: dict) -> str:
    p = data.get("player") or data
    if not isinstance(p, dict):
        return str(data)[:400]
    country = p.get("country_name") or "yok"
    province = p.get("province_name") or "yok"
    hints = []
    if not p.get("country_id"):
        hints.append("💡 Ülke yok — `ülkeye katıl`")
    health = int(p.get("health") or 0)
    pills = int(p.get("health_pills") or 0)
    if health < 50 and pills > 0:
        hints.append("💊 Can düşük — `hap kullan`")
    hint_block = ("\n" + "\n".join(hints)) if hints else ""
    return (
        f"👤 *{p.get('username', '?')}* (lv{p.get('level', '?')})\n"
        f"💰 {int(p.get('balance') or 0):,} altın | 💎 {p.get('diamonds', 0)}\n"
        f"⭐ XP {p.get('xp', 0)} | itibar {p.get('reputation', '?')}\n"
        f"❤️ Can {health}/100 | hap {pills}\n"
        f"🌍 Ülke: {country} | eyalet: {province}{hint_block}"
    )


def format_countries(countries: list[dict], limit: int = 12) -> str:
    if not countries:
        return "Ülke listesi boş."
    lines = [f"🌍 *Ülkeler* ({len(countries)} adet)"]
    for c in countries[:limit]:
        name = c.get("name", "?")
        players = c.get("player_count", "?")
        treasury = int(c.get("treasury") or 0)
        lines.append(f"• *{name}* — {players} oyuncu | hazine {treasury:,}")
    if len(countries) > limit:
        lines.append(f"_… +{len(countries) - limit} ülke daha_")
    lines.append("\nKatılmak için: `ülkeye katıl` veya `ülke: El Turko`")
    return "\n".join(lines)


def format_country_result(data: dict) -> str:
    if data.get("already_assigned"):
        return (
            f"✅ Zaten ülkedesin: *{data.get('country_name', '?')}* "
            f"({data.get('province_name', '?')})"
        )
    msg = data.get("message")
    player = data.get("player") or {}
    if player.get("country_name"):
        return (
            f"✅ {msg or 'Ülke seçildi!'}\n"
            f"🌍 *{player.get('country_name')}* — eyalet: {player.get('province_name', '?')}"
        )
    if data.get("country_name"):
        return (
            f"✅ {msg or 'Atandı!'}\n"
            f"🌍 *{data.get('country_name')}* — eyalet: {data.get('province_name', '?')}"
        )
    return msg or str(data)[:300]


def format_quest_claims(results: list[dict]) -> str:
    if not results:
        return "Toplanacak görev ödülü yok."
    lines = ["🎁 *Görev ödülleri*"]
    for r in results:
        key = r.get("quest_key", "?")
        if r.get("ok"):
            d = r.get("data") or {}
            earned = d.get("earned") or d.get("reward") or {}
            money = int(earned.get("money") or d.get("money") or 0)
            lines.append(f"✅ {key}: +{money:,} altın")
        else:
            lines.append(f"❌ {key}: {r.get('error', '?')}")
    return "\n".join(lines)


def format_wars(data: dict) -> str:
    war = data.get("war")
    wars = data.get("wars") or []
    if not war and not wars:
        return "⚔️ Aktif savaş yok."
    lines = ["⚔️ *Savaş durumu*"]
    items = [war] if war else []
    items.extend(w for w in wars if w and w not in items)
    for w in items[:5]:
        if not w:
            continue
        name = w.get("war_name") or w.get("name") or "Savaş"
        status = w.get("status", "?")
        wtype = w.get("war_type", "?")
        atk = w.get("attacker_name") or w.get("attacker_province", "?")
        defn = w.get("defender_name") or w.get("defender_province", "?")
        lines.append(f"• *{name}* [{status}] ({wtype})")
        lines.append(f"  {atk} vs {defn}")
    lines.append("\nKatkı: `savaşa katıl` (Gemini planlar)")
    return "\n".join(lines)


def format_pills(data: dict) -> str:
    if data.get("success"):
        return (
            f"💊 {data.get('pills_used', 0)} hap kullanıldı\n"
            f"❤️ Can: {data.get('health', '?')}/100 | kalan hap: {data.get('pills_remaining', '?')}"
        )
    return data.get("message") or data.get("error") or str(data)[:200]


def format_quests(data: dict) -> str:
    quests = data.get("quests") or []
    if not quests:
        return "Görev bulunamadı."
    lines = ["📋 *Görevler*"]
    for q in quests[:12]:
        key = q.get("quest_key", "?")
        prog = q.get("progress", 0)
        target = q.get("target", "?")
        done = q.get("completed") or q.get("rewarded")
        status = "✅" if q.get("rewarded") else ("🟡" if prog >= target else "⚪")
        title = (q.get("title") or key)[:40]
        lines.append(f"{status} {title} ({prog}/{target}) [{key}]")
    return "\n".join(lines)


def format_api_result(path: str, data: Any) -> str:
    if not isinstance(data, dict):
        return str(data)[:500]
    if "/players/profile" in path:
        return format_profile(data)
    if "/quests" in path and "quests" in data:
        return format_quests(data)
    if "/countries" in path and "countries" in data:
        return format_countries(data.get("countries") or [])
    if "/countries/select" in path or "/countries/auto-assign" in path:
        return format_country_result(data)
    if "/wars/my-country" in path:
        return format_wars(data)
    if "/auto/use-pills" in path:
        return format_pills(data)
    if "earned" in data or "message" in data:
        earned = data.get("earned") or {}
        if earned:
            return (
                f"✅ {data.get('message', 'Tamam')}\n"
                f"+{earned.get('money', 0):,} altın | +{earned.get('xp', 0)} XP | +{earned.get('diamonds', 0)} 💎"
            )
        return data.get("message") or data.get("error") or str(data)[:300]
    if "error" in data:
        return f"❌ {data['error']}"
    if "daily_reward" in data:
        r = data.get("daily_reward")
        return "Günlük ödül alındı." if r else "Bugün günlük ödül yok veya zaten alındı."
    # kısa özet
    text = str(data)
    return text[:450] + ("…" if len(text) > 450 else "")


def format_step_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        if "error" in r and "result" not in r:
            lines.append(f"{i}. ❌ {r['error']}")
            continue
        res = r.get("result", {})
        path = res.get("path", "?")
        data = res.get("data", {})
        icon = "✅" if res.get("ok") else "⚠️"
        summary = format_api_result(path, data)
        lines.append(f"{icon} `{path}`\n{summary}")
    return "\n\n".join(lines) if lines else ""
