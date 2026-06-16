"""Zengin özellik raporları — Telegram HTML."""

from __future__ import annotations

import html
from typing import Any

from .account_config import AccountConfig, get_config, role_label
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
    class_priority_hint,
)
from .user_errors import format_ms
from .version import get_version_label


def _bar(pct: int, width: int = 10) -> str:
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def _quest_line(q: dict, *, show_reward: bool = True) -> str:
    icon = q.get("icon") or "📋"
    label = html.escape(str(q.get("label") or q.get("quest_key") or "?"))
    prog = int(q.get("progress") or 0)
    target = int(q.get("target") or 1)
    pct = int(prog * 100 / target) if target else 0
    diff = q.get("difficulty") or ""
    line = f"{icon} <b>{label}</b> {_bar(pct)} {prog}/{target}"
    if diff:
        line += f" <i>({html.escape(str(diff))})</i>"
    if show_reward:
        rw = q.get("reward") or {}
        parts = []
        if rw.get("money"):
            parts.append(f"+{int(rw['money']):,}₺")
        if rw.get("xp"):
            parts.append(f"+{rw['xp']} XP")
        if rw.get("diamonds"):
            parts.append(f"+{rw['diamonds']}💎")
        if parts:
            line += f"\n   Ödül: {' · '.join(parts)}"
    desc = q.get("desc")
    if desc:
        line += f"\n   <i>{html.escape(str(desc)[:80])}</i>"
    return line


def format_quest_board_html(quests: list[dict], analysis: dict | None = None) -> str:
    analysis = analysis or analyze_quests(quests)
    lines = [
        f"<b>📋 Görev panosu</b> ({analysis['total']} görev)",
    ]
    if analysis["claimable"]:
        lines.append(
            f"\n<b>🎁 Toplanabilir ({analysis['claimable_count']})</b> — "
            f"~{analysis['pending_money']:,}₺ · {analysis['pending_xp']} XP · {analysis['pending_diamonds']}💎"
        )
        for q in analysis["claimable"][:6]:
            lines.append(_quest_line(q))
    if analysis["almost"]:
        lines.append(f"\n<b>🟡 Neredeyse bitti ({len(analysis['almost'])})</b>")
        for q in analysis["almost"][:4]:
            lines.append(_quest_line(q, show_reward=False))
    if analysis["in_progress"]:
        rest = [q for q in analysis["in_progress"] if q not in analysis["almost"]]
        if rest:
            lines.append(f"\n<b>⚪ Devam eden ({len(rest)})</b>")
            for q in rest[:5]:
                lines.append(_quest_line(q, show_reward=False))
    if analysis["done"]:
        lines.append(f"\n<i>✅ Tamamlanan: {len(analysis['done'])}</i>")
    if not quests:
        lines.append("\nGörev bulunamadı.")
    lines.append("\n<i>Ödül toplamak için 📜 Görev topla</i>")
    return "\n".join(lines)


def format_quest_claim_html(results: list[dict], analysis: dict | None = None) -> str:
    if not results:
        if analysis and analysis.get("claimable_count") == 0:
            return (
                "<b>📜 Görev toplama</b>\n\n"
                "Toplanacak ödül yok.\n"
                "<i>İlerleme için farm / savaş / antrenman yap</i>"
            )
        return "Toplanacak görev ödülü yok."
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    total_money = 0
    total_xp = 0
    total_dia = 0
    lines = [f"<b>🎁 Görev ödülleri</b> — {len(ok)} başarılı"]
    for r in ok:
        key = r.get("quest_key", "?")
        d = r.get("data") or {}
        earned = d.get("earned") or d.get("reward") or d
        money = int(earned.get("money") or d.get("money") or 0)
        xp = int(earned.get("xp") or d.get("xp") or 0)
        dia = int(earned.get("diamonds") or d.get("diamonds") or 0)
        total_money += money
        total_xp += xp
        total_dia += dia
        parts = [f"+{money:,}₺"] if money else []
        if xp:
            parts.append(f"+{xp} XP")
        if dia:
            parts.append(f"+{dia}💎")
        lines.append(f"✅ <code>{html.escape(str(key))}</code> {' · '.join(parts)}")
    for r in fail[:4]:
        lines.append(f"❌ <code>{html.escape(str(r.get('quest_key', '?')))}</code> {html.escape(str(r.get('error', '?'))[:80])}")
    if ok:
        lines.append(f"\n<b>Toplam:</b> {total_money:,}₺ · {total_xp} XP · {total_dia}💎")
    return "\n".join(lines)


from .war_board import format_war_board_html, war_board_inline_markup  # noqa: F401 — re-export


def format_war_contribute_html(result: dict, analysis: dict | None = None) -> str:
    if result.get("ok"):
        d = result.get("result", {}).get("data") or {}
        side = result.get("result", {}).get("side", "?")
        idx = result.get("result", {}).get("war_index")
        war_tag = f" #{idx}" if idx else ""
        msg = html.escape(str(d.get("message") or ""))
        dmg = d.get("damage") or d.get("contribution")
        extra = f"\nKatkı: {dmg}" if dmg is not None else ""
        troops = d.get("troops_sent") or d.get("units_sent")
        if troops is not None:
            extra += f"\nAsker: {troops}"
        return f"<b>⚔️ Savaşa katkı{war_tag}</b> ({html.escape(str(side))}) ✅\n{msg}{extra}"
    if result.get("skipped") == "no_active_war":
        return "⚔️ Aktif savaş yok — önce ülke savaşı bekle."
    if result.get("skipped"):
        return f"⚔️ Katkı atlandı: <code>{html.escape(str(result['skipped']))}</code>"
    err = html.escape(str(result.get("error") or result)[:200])
    return f"⚔️ Savaş katkısı başarısız\n{err}"


from .factory_board import format_factory_board_html, format_factory_action_html  # noqa: F401 — re-export


def format_training_html(
    war: dict | None,
    attack: dict | None,
    auto: dict | None = None,
    analysis: dict | None = None,
) -> str:
    analysis = analysis or analyze_training(auto or {}, war)
    if attack and attack.get("ok"):
        d = attack.get("result", {}).get("data") or {}
        msg = html.escape(str(d.get("message") or d)[:400])
        reward = d.get("earned") or d.get("reward") or {}
        extra = ""
        if isinstance(reward, dict) and reward.get("xp"):
            extra = f"\n+{reward.get('xp')} XP"
        return f"<b>🏋️ Antrenman saldırısı</b> ✅\n{msg}{extra}"
    if attack and attack.get("skipped"):
        sk = attack["skipped"]
        if sk == "free_attack_cooldown":
            ms = (attack.get("detail") or {}).get("ms")
            return f"⏳ Antrenman CD — {format_ms(ms)} sonra"
        return f"🏋️ Antrenman: <code>{html.escape(str(sk))}</code>"
    if attack and not attack.get("ok"):
        return f"🏋️ {html.escape(str(attack.get('error') or attack)[:200])}"

    lines = ["<b>🏋️ Antrenman durumu</b>"]
    if war:
        name = html.escape(str(war.get("name") or war.get("war_name") or "Antrenman"))
        wid = war.get("id") or war.get("war_id") or "?"
        lines.append(f"Savaş: <b>{name}</b>\n<code>{wid}</code>")
    else:
        lines.append("Aktif antrenman savaşı yok.")
    if analysis["free_attack"]:
        lines.append("✅ Ücretsiz saldırı hazır")
    elif analysis.get("cooldown_ms"):
        lines.append(f"⏳ Saldırı: {format_ms(analysis['cooldown_ms'])}")
    for tip in analysis.get("tips", []):
        lines.append(f"💡 {html.escape(tip)}")
    return "\n".join(lines)


def format_military_html(data: dict, ops: dict | None, analysis: dict | None = None) -> str:
    analysis = analysis or analyze_military(data, ops or {})
    lines = ["<b>🪖 Askeri durum</b>"]
    if analysis.get("power") is not None:
        p = analysis["power"]
        lines.append(f"Güç: <b>{p:,}</b>" if isinstance(p, int) else f"Güç: <b>{p}</b>")
    if analysis.get("unit_total"):
        lines.append(f"Toplam birim: {analysis['unit_total']}")
    units = analysis.get("units") or {}
    if isinstance(units, dict) and units:
        lines.append("<b>Birimler</b>")
        for k, v in list(units.items())[:10]:
            lines.append(f"  {html.escape(str(k))}: {v}")
    if analysis.get("has_operation") and ops:
        op = ops.get("operation") or {}
        name = html.escape(str(op.get("name") or op.get("title") or "Operasyon"))
        joined = "✅" if ops.get("is_joined") else "❌"
        lines.append(f"\n<b>🎯 {name}</b> — katılım {joined}")
    lines.append("\n<i>Eğitim: asker eğit komutu (yakında)</i>")
    return "\n".join(lines)


def format_auto_board_html(status: dict, analysis: dict | None = None) -> str:
    analysis = analysis or analyze_auto_status(status)
    if not status:
        return "Otomasyon durumu alınamadı."
    lines = [
        "<b>🤖 Otomasyon merkezi</b>",
        f"Auto work: {'🟢' if analysis['auto_work'] else '⚪'} · "
        f"Auto war: {'🟢' if analysis['auto_war'] else '⚪'}",
        f"❤️ Can {analysis['health']}/{analysis['health_max']} · 💊 {analysis['pills']} hap",
    ]
    if analysis.get("regen"):
        lines.append(f"Can yenilenme: +{analysis['regen']}")
    rows = [
        ("🌾 Work", analysis["work_ready"], analysis["work_ms"]),
        ("💊 Hap CD", analysis["pill_ready"], analysis["pill_ms"]),
        ("⚔️ Savaş CD", analysis["war_ready"], analysis["war_ms"]),
        ("🏋️ Ücretsiz saldırı", analysis["free_attack"], analysis["attack_ms"]),
    ]
    lines.append("")
    for label, ready, ms in rows:
        if ready:
            lines.append(f"{label}: ✅ hazır")
        else:
            lines.append(f"{label}: ⏳ {format_ms(ms)}")
    if status.get("auto_war_id"):
        lines.append(f"\nAuto savaş: <code>{status.get('auto_war_id')}</code> ({status.get('auto_war_side')})")
    return "\n".join(lines)


def format_craft_board_html(result: dict | None, analysis: dict | None) -> str:
    if result and result.get("ok"):
        d = result.get("data") or {}
        pills = d.get("pills_crafted") or d.get("health_pills") or d.get("crafted")
        return (
            f"<b>💎 Hap üretimi</b> ✅\n"
            f"{result.get('diamonds')} elmas harcandı"
            + (f" → +{pills} hap" if pills is not None else "")
            + (f"\n{html.escape(str(d.get('message') or ''))}" if d.get("message") else "")
        )
    if result and not result.get("ok"):
        err = html.escape(str(result.get("error") or "?"))
        return f"<b>💎 Hap üretimi</b> ❌\n{err}"

    analysis = analysis or {}
    lines = [
        "<b>💎 Hap ekonomisi</b>",
        f"Elmas: {analysis.get('diamonds', '?')} · Hap: {analysis.get('pills', '?')}",
        f"Hedef stok: {analysis.get('need_pills', 0)} eksik",
        f"Önerilen craft: {analysis.get('suggested_batch', 0)} elmas",
        f"<i>{html.escape(str(analysis.get('roi_note', '')))}</i>",
    ]
    if analysis.get("can_craft"):
        lines.append("\n✅ Üretim yapılabilir — butona bas")
    else:
        lines.append("\n⏳ Yeterli elmas yok veya stok dolu")
    return "\n".join(lines)


def format_passive_board_html(
    data: dict,
    analysis: dict | None = None,
    *,
    player_class: str | None = None,
    cfg: AccountConfig | None = None,
) -> str:
    analysis = analysis or analyze_passive(data, cfg or AccountConfig("x"), player_class)
    pts = analysis["available"]
    lines = [f"<b>⚡ Pasif yetenekler</b> — <b>{pts}</b> puan bekliyor"]
    if player_class:
        lines.append(f"Sınıf: <b>{html.escape(player_class)}</b> · öncelik: {html.escape(class_priority_hint(player_class))}")
    skills = analysis.get("skills") or {}
    if isinstance(skills, dict):
        for k, v in list(skills.items())[:12]:
            if isinstance(v, dict):
                lvl = v.get("level", "?")
                lines.append(f"  • {html.escape(str(k))}: seviye <b>{lvl}</b>")
            else:
                lines.append(f"  • {html.escape(str(k))}: {v}")
    if analysis.get("next_skill") and pts > 0:
        lines.append(f"\n💡 Sonraki harcama: <code>{html.escape(str(analysis['next_skill']))}</code>")
    elif pts <= 0:
        lines.append("\n<i>Bekleyen puan yok — farm/savaş ile biriktir</i>")
    return "\n".join(lines)


def format_countries_board_html(
    countries: list[dict],
    *,
    current_country: str | None = None,
    limit: int = 12,
) -> str:
    lines = [f"<b>🌍 Ülkeler</b> ({len(countries)} kayıtlı)"]
    if current_country:
        lines.append(f"Şu an: <b>{html.escape(current_country)}</b>")
    ranked = sorted(countries, key=lambda c: int(c.get("player_count") or 0), reverse=True)
    for c in ranked[:limit]:
        name = html.escape(str(c.get("name", "?")))
        players = c.get("player_count", "?")
        treasury = int(c.get("treasury") or 0)
        lines.append(f"• <b>{name}</b> — {players} oyuncu · hazine {treasury:,}₺")
    if len(countries) > limit:
        lines.append(f"<i>… +{len(countries) - limit} ülke</i>")
    lines.append("\n<i>Katılmak için ülkeye bas</i>")
    return "\n".join(lines)


def format_online_board_html(payload: dict, players: list[dict] | None = None) -> str:
    lines = ["<b>🌐 Online</b>"]
    if payload.get("count") is not None:
        lines.append(f"Aktif oyuncu: <b>~{payload['count']}</b>")
    data = payload.get("data") or {}
    if isinstance(data, dict):
        for key in ("online", "count", "players_online", "total"):
            if key in data:
                lines.append(f"Sunucu: <b>{data[key]}</b> online")
                break
    plist = players or payload.get("players") or []
    if plist:
        lines.append("\n<b>Örnek oyuncular</b>")
        for p in plist[:8]:
            if isinstance(p, dict):
                un = html.escape(str(p.get("username") or p.get("name") or "?"))
                lv = p.get("level", "")
                lines.append(f"  • {un}" + (f" lv{lv}" if lv else ""))
            else:
                lines.append(f"  • {html.escape(str(p))}")
    return "\n".join(lines)


def format_ping_board_html(result: dict, *, latency_ms: float | None = None) -> str:
    if result.get("ok"):
        d = result.get("data") or {}
        msg = html.escape(str(d.get("message") or "")) if isinstance(d, dict) else ""
        lat = f"\nGecikme: <b>{latency_ms:.0f}ms</b>" if latency_ms is not None else ""
        prof = ""
        if isinstance(d, dict) and d.get("server_time"):
            prof = f"\nSunucu saati: {html.escape(str(d['server_time']))}"
        return f"<b>📡 Bağlantı testi</b> ✅ HTTP {result.get('status')}{lat}{prof}\n{msg}"
    return f"<b>📡 Bağlantı testi</b> ❌ HTTP {result.get('status')}"


def format_extras_hub_html(readiness: dict) -> str:
    lines = [
        f"<b>⋯ Özellik merkezi</b> {get_version_label()}",
        "",
        "<b>📌 Hazır aksiyonlar</b>",
    ]
    highlights = readiness.get("highlights") or []
    if highlights:
        lines.extend(f"• {html.escape(h)}" for h in highlights)
    else:
        lines.append("• Şu an bekleyen öncelikli aksiyon yok — farm döngüsüne devam")
    lines.append("\n<i>Alttaki butonlarla detaylı rapor ve aksiyon</i>")
    return "\n".join(lines)


def format_daily_html(status: int, data: dict) -> str:
    if not isinstance(data, dict):
        return f"🎁 Günlük ödül (HTTP {status})\n{html.escape(str(data)[:300])}"
    reward = data.get("daily_reward")
    if reward is None and status in (200, 201):
        return (
            "<b>🎁 Günlük ödül</b>\n\n"
            "Bugünkü ödül zaten alınmış veya şu an yok.\n"
            "<i>Yarın tekrar dene</i>"
        )
    if isinstance(reward, dict):
        parts = []
        if reward.get("money"):
            parts.append(f"+{int(reward['money']):,}₺")
        if reward.get("xp"):
            parts.append(f"+{reward['xp']} XP")
        if reward.get("diamonds"):
            parts.append(f"+{reward['diamonds']}💎")
        body = " · ".join(parts) if parts else str(reward)
        return f"<b>🎁 Günlük ödül alındı</b> ✅\n{html.escape(body)}"
    msg = data.get("message") or data.get("error")
    return f"<b>🎁 Günlük</b> (HTTP {status})\n{html.escape(str(msg or data)[:350])}"


def format_farm_html(result) -> str:
    """FarmResult için zengin HTML."""
    from .farmer import FarmResult

    if not isinstance(result, FarmResult):
        return html.escape(str(result)[:500])
    if result.error and result.earned_money <= 0 and not result.ok:
        err = html.escape(str(result.error))
        fab = f"\n🏭 <code>{result.factory_id}</code>" if result.factory_id else ""
        return f"<b>🌾 Farm</b> ❌\n{err}{fab}"
    extra = ""
    if result.factory_id:
        extra = f"\n🏭 <code>{result.factory_id}</code>"
    if result.earned_diamonds:
        extra += f" · +{result.earned_diamonds}💎"
    if result.actions:
        extra += f"\n<i>Ek: {html.escape(str(result.actions)[:200])}</i>"
    return (
        f"<b>🌾 Farm</b> ✅ <b>{html.escape(result.username)}</b>\n"
        f"+{result.earned_money:,}₺ · +{result.earned_xp} XP{extra}\n"
        f"Bakiye: {result.balance_before:,} → <b>{result.balance_after:,}</b>"
    )


def format_stat_spend_html(spent: list[dict]) -> str:
    if not spent:
        return "⚡ Harcanacak pasif puan yok."
    ok = [s for s in spent if s.get("ok")]
    if not ok:
        last = spent[-1]
        err = (last.get("data") or {}).get("error") or last
        return f"⚡ Stat harcanamadı\n<code>{html.escape(str(err)[:200])}</code>"
    lines = ["<b>⚡ Pasif stat harcandı</b>"]
    for s in ok:
        skill = html.escape(str(s.get("skill", "?")))
        pts = s.get("points", "?")
        d = s.get("data") or {}
        new_lvl = d.get("new_level") or d.get("level")
        extra = f" → seviye <b>{new_lvl}</b>" if new_lvl is not None else ""
        lines.append(f"✅ {pts} puan → <code>{skill}</code>{extra}")
    return "\n".join(lines)


def format_plan_board_html(account_name: str, snap: dict | None = None) -> str:
    cfg = get_config(account_name)
    snap = snap or {}
    lines = [
        f"<b>📋 Operasyon planı — {html.escape(account_name)}</b>",
        f"Görev rolü: <b>{html.escape(role_label(cfg.role))}</b>",
        f"Fabrika: <b>{html.escape(cfg.work_mode)}</b>"
        + (f" → <code>{cfg.preferred_factory_id}</code>" if cfg.preferred_factory_id else "")
        + (f"\nAna fabrika: <code>{cfg.primary_factory_id}</code>" if cfg.primary_factory_id else ""),
        f"Premium hub: {'evet' if cfg.is_premium_hub else 'hayır'}",
        f"Stat önceliği: {', '.join(html.escape(s) for s in cfg.stat_priority[:4])}",
        f"Antrenman: {'açık' if cfg.training_enabled else 'kapalı'} · Savaş: {'açık' if cfg.war_enabled else 'kapalı'}",
        f"Hap craft: {'açık' if cfg.craft_pills_when_low else 'kapalı'} (min {cfg.min_pill_stock}, batch {cfg.craft_diamond_batch})",
    ]
    if snap:
        lines.extend(
            [
                "",
                "<b>Canlı durum</b>",
                f"💰 {int(snap.get('balance') or 0):,}₺ · 💎 {snap.get('diamonds', '?')} · ❤️ {snap.get('health', '?')}/100",
                f"Work: {'✅ hazır' if snap.get('work_ready') else '⏳'} · Pasif puan: {snap.get('passive_available', 0)}",
            ]
        )
        steps: list[str] = []
        if int(snap.get("passive_available") or 0) > 0:
            steps.append("⚡ Stat harca")
        if snap.get("work_ready"):
            steps.append("🌾 Farm")
        if int(snap.get("health") or 0) < 100 and int(snap.get("pills") or 0) > 0:
            steps.append("💊 Can doldur")
        if steps:
            lines.append(f"\n<b>Sıradaki:</b> {' → '.join(steps)}")
    if snap.get("error"):
        lines.append(f"⚠️ {html.escape(str(snap['error'])[:100])}")
    return "\n".join(lines)
