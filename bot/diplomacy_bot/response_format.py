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


def format_factories_bundle(factories: list[dict], work: dict | None = None) -> str:
    lines = ["🏭 *Fabrikalarım*"]
    if not factories:
        lines.append("Kayıtlı fabrika yok.")
    for f in factories[:8]:
        name = f.get("name") or "?"
        fid = f.get("id") or f.get("factory_id") or "?"
        lvl = f.get("level", "?")
        prov = f.get("province_name") or f.get("region") or ""
        workers = f.get("worker_count") or f.get("workers")
        extra = f" · {workers} işçi" if workers is not None else ""
        lines.append(f"• *{name}* (lv{lvl}){extra}\n  `{fid}` {prov}")
    if work and isinstance(work, dict):
        if work.get("working"):
            lines.append(f"\n✅ Şu an çalışıyor: `{work.get('factory_id', '?')}`")
        else:
            lines.append("\n⏳ Aktif work yok")
    return "\n".join(lines)


def format_military_bundle(data: dict) -> str:
    if not data:
        return "Asker bilgisi yok."
    power = data.get("military_power")
    units = data.get("units") or {}
    barracks = data.get("barracks") or {}
    lines = ["🪖 *Askeri durum*"]
    if power is not None:
        lines.append(f"Güç: *{power:,}*" if isinstance(power, int) else f"Güç: *{power}*")
    if isinstance(units, dict) and units:
        unit_lines = []
        for k, v in list(units.items())[:8]:
            unit_lines.append(f"  {k}: {v}")
        lines.append("Birimler:\n" + "\n".join(unit_lines))
    elif isinstance(units, list) and units:
        for u in units[:6]:
            if isinstance(u, dict):
                lines.append(f"  • {u.get('type', '?')}: {u.get('count', '?')}")
    if barracks:
        lines.append(f"Kışla: `{str(barracks)[:120]}`")
    return "\n".join(lines) if len(lines) > 1 else "🪖 Asker verisi boş."


def format_military_ops(data: dict) -> str:
    if not data:
        return "Aktif askeri operasyon yok."
    op = data.get("operation")
    joined = data.get("is_joined")
    if not op:
        return "Aktif askeri operasyon yok."
    name = op.get("name") or op.get("title") or "Operasyon"
    lines = [f"🎯 *{name}*", f"Katıldın: {'✅' if joined else '❌'}"]
    if data.get("joined_until"):
        lines.append(f"Bitiş: {data['joined_until']}")
    return "\n".join(lines)


def format_training_bundle(war: dict | None, attack: dict | None = None) -> str:
    if attack and attack.get("ok"):
        d = attack.get("result", {}).get("data") or {}
        return f"🏋️ *Antrenman saldırısı* ✅\n{d.get('message') or str(d)[:300]}"
    if attack and attack.get("skipped"):
        return f"🏋️ Antrenman atlandı: `{attack['skipped']}`"
    if attack and not attack.get("ok"):
        return f"🏋️ Antrenman: {attack.get('error') or attack}"
    if war:
        name = war.get("name") or war.get("war_name") or "Antrenman"
        wid = war.get("id") or war.get("war_id") or "?"
        return f"🏋️ *{name}*\nID: `{wid}`\nÜcretsiz saldırı için butona bas."
    return "🏋️ Antrenman savaşı bulunamadı."


def format_war_contribute(result: dict) -> str:
    if result.get("ok"):
        d = result.get("result", {}).get("data") or {}
        side = result.get("result", {}).get("side", "?")
        return f"⚔️ *Savaşa katkı* ({side}) ✅\n{d.get('message') or str(d)[:300]}"
    if result.get("skipped"):
        return f"⚔️ Savaş katkısı atlandı: `{result['skipped']}`"
    return f"⚔️ Savaş katkısı başarısız: {result.get('error') or result}"


def format_auto_status_detail(status: dict) -> str:
    if not status:
        return "Otomasyon durumu alınamadı."
    work_ms = int(status.get("next_work_in_ms") or 0)
    pill_ms = int(status.get("pill_cooldown_ms") or 0)
    free = status.get("free_attack_available")
    lines = [
        "🤖 *Otomasyon durumu*",
        f"Auto work: {'🟢' if status.get('auto_work_active') else '⚪'}",
        f"Auto war: {'🟢' if status.get('auto_war_active') else '⚪'}",
        f"Work: {'✅ hazır' if work_ms <= 0 else f'⏳ {work_ms // 1000}s'}",
        f"Hap CD: {'✅' if pill_ms <= 0 else f'⏳ {pill_ms // 1000}s'}",
        f"Ücretsiz saldırı: {'✅' if free else '⏳ bekliyor'}",
        f"Hap stoğu: {status.get('health_pills', '?')}",
    ]
    return "\n".join(lines)


def format_online_info(payload: dict) -> str:
    if payload.get("count") is not None:
        return f"🌐 *Online oyuncular:* ~{payload['count']}"
    data = payload.get("data") or {}
    if isinstance(data, dict):
        for key in ("online", "count", "players_online", "total"):
            if key in data:
                return f"🌐 *Online:* {data[key]}"
    return f"🌐 Online: `{str(data)[:200]}`"


def format_craft_result(result: dict) -> str:
    if result.get("ok"):
        d = result.get("data") or {}
        if isinstance(d, dict):
            msg = d.get("message") or d.get("success")
            pills = d.get("pills_crafted") or d.get("health_pills")
            parts = [f"💎 {result.get('diamonds')} elmas → hap"]
            if pills is not None:
                parts.append(f"kazanılan: {pills}")
            if msg:
                parts.append(str(msg))
            return "✅ " + " | ".join(parts)
        return f"✅ Hap üretildi ({result.get('diamonds')} elmas)"
    err = result.get("error")
    if isinstance(result.get("data"), dict):
        err = err or result["data"].get("error") or result["data"].get("message")
    return f"❌ Hap üretilemedi: {err or '?'}"


def format_passive_detail(data: dict) -> str:
    pts = int(data.get("available_points") or 0)
    skills = data.get("passive_skills") or {}
    lines = [f"⚡ *Pasif yetenekler* — {pts} puan bekliyor"]
    if isinstance(skills, dict):
        for k, v in list(skills.items())[:10]:
            if isinstance(v, dict):
                lvl = v.get("level", "?")
                lines.append(f"  • {k}: seviye {lvl}")
            else:
                lines.append(f"  • {k}: {v}")
    return "\n".join(lines)


def format_ping_result(result: dict) -> str:
    if result.get("ok"):
        d = result.get("data") or {}
        msg = d.get("message") if isinstance(d, dict) else None
        return f"📡 Ping OK (HTTP {result.get('status')}){f' — {msg}' if msg else ''}"
    return f"📡 Ping başarısız: HTTP {result.get('status')}"


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
