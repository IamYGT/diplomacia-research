from __future__ import annotations

import re
from dataclasses import asdict
from typing import TYPE_CHECKING

from . import farmer, game_api
from .account_config import get_config, update_config_field
from .dynamic_context import format_plan_summary
from .game_client import call
from .response_format import (
    format_api_result,
    format_countries,
    format_country_result,
    format_pills,
    format_profile,
    format_quest_claims,
    format_quests,
    format_wars,
)
from .store import get_account, update_after_farm

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def _match(text: str, patterns: list[str]) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in patterns)


def try_fast_path(user_message: str, default_account: str) -> "AgentResult | None":
    """Gemini olmadan sık komutlar — 503 ve gecikmeden kaçınır."""
    from .ai_agent import AgentResult

    text = user_message.strip()
    acc = get_account(default_account)
    if not acc:
        return AgentResult(reply=f"Hesap yok: {default_account}. /add ile ekle.")

    if _match(text, [r"^naber", r"^selam", r"^merhaba", r"^hey", r"^sa\b"]):
        try:
            p = game_api.get_profile(acc.token)
            cfg = get_config(acc.name)
            if p.passive_skill_points > 0:
                hint = f"\n⚡ {p.passive_skill_points} pasif stat — `stat harca`"
            elif p.health < 100 and p.health_pills > 0:
                hint = "\n💊 Can düşük — `hap kullan` veya `akıllı farm`"
            else:
                hint = "\n🌾 `akıllı farm` | `planım` | `ne durumdayım`"
            return AgentResult(
                reply=(
                    f"İyidir patron 😎 *{p.username}* hazır.\n"
                    f"💰 {p.balance:,} | 💎 {p.diamonds} | lv{p.level} | ❤️ {p.health}/100\n"
                    f"📍 {p.province_name or '?'} | mod: `{cfg.work_mode}`"
                    f"{hint}"
                )
            )
        except Exception as e:
            return AgentResult(reply=f"Selam! (profil: {e})")

    if _match(text, [r"akıllı\s*farm", r"oto\s*döngü", r"\btick\b", r"orchestrator", r"tam\s*döngü"]):
        from .modules.orchestrator import tick_account

        r = tick_account(acc.token, acc.name)
        update_after_farm(acc.name, r.balance_after)
        fr = farmer.FarmResult(
            account_name=r.account_name,
            username=r.username,
            ok=r.ok,
            balance_before=r.balance_before,
            balance_after=r.balance_after,
            earned_money=r.earned_money,
            earned_xp=r.earned_xp,
            earned_diamonds=r.earned_diamonds,
            error=r.error,
            factory_id=r.factory_id,
        )
        out = farmer.format_farm_result(fr)
        if r.actions:
            out += f"\n📎 `{str(r.actions)[:350]}`"
        return AgentResult(reply=out)

    if _match(text, [r"planım", r"plan\s*ne", r"bot\s*plan", r"strateji\s*plan"]):
        return AgentResult(
            reply=format_plan_summary(acc.name),
            inline_buttons=[[("🌾 Akıllı farm", "action:smartfarm"), ("📋 Durum", "action:status")]],
        )

    if _match(text, [r"stat\s*harca", r"pasif\s*stat", r"skill\s*harca", r"puan\s*harca"]):
        from .modules import stats

        cfg = get_config(acc.name)
        spent = stats.spend_available(acc.token, cfg)
        if not spent:
            return AgentResult(reply="Pasif stat puanı yok.")
        ok = [s for s in spent if s.get("ok")]
        if ok:
            s0 = ok[0]
            return AgentResult(reply=f"✅ {s0.get('points')} puan → `{s0.get('skill')}`")
        return AgentResult(reply=f"❌ Stat harcanamadı: {spent[-1].get('data', spent[-1])}")

    if _match(text, [r"fabrika\s*(ayarla|mod)", r"foreign\s*mod", r"yabancı\s*fabrika"]):
        mode = "foreign"
        if _match(text, [r"\bown\b", r"kendi"]):
            mode = "own"
        elif _match(text, [r"\bauto\b"]):
            mode = "auto"
        m = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text, re.I
        )
        if m:
            update_config_field(acc.name, work_mode="fixed", preferred_factory_id=m.group(1))
            return AgentResult(reply=f"✅ Sabit fabrika: `{m.group(1)}`")
        update_config_field(acc.name, work_mode=mode, preferred_factory_id=None)
        return AgentResult(reply=f"✅ {acc.name} fabrika modu: `{mode}`")

    if _match(text, [r"tüm\s*hesap", r"hesaplar\s*durum", r"multi\s*hesap"]):
        from .store import list_accounts

        lines = []
        for a in list_accounts()[:10]:
            try:
                p = game_api.get_profile(a.token)
                lines.append(f"• *{a.name}* {p.username} lv{p.level} 💰{p.balance:,} `{a.proxy_id}`")
            except Exception as e:
                lines.append(f"• *{a.name}*: {e}")
        return AgentResult(reply="\n\n".join(lines) if lines else "Hesap yok.")

    if _match(text, [r"savaş", r"\bwar\b", r"cephe"]):
        try:
            data = game_api.get_my_wars(acc.token)
            return AgentResult(reply=format_wars(data))
        except Exception as e:
            return AgentResult(reply=f"❌ Savaş bilgisi alınamadı: {e}")

    if _match(
        text,
        [r"durum", r"ne durumda", r"bakiye", r"profil", r"hesabım", r"şu an", r"status"],
    ):
        p = game_api.get_profile(acc.token)
        return AgentResult(reply=format_profile({"player": asdict(p)}))

    if _match(text, [r"farm", r"çalış", r"fabrika", r"iş yap", r"grind", r"farm yap"]):
        cycles = 1
        m = re.search(r"(\d+)\s*(kez|tur|döngü|x)", text.lower())
        if m:
            cycles = min(int(m.group(1)), 10)
        r = farmer.run_farm(acc.token, acc.name, cycles)
        update_after_farm(acc.name, r.balance_after)
        return AgentResult(reply=farmer.format_farm_result(r))

    if _match(text, [r"günlük", r"daily", r"günün ödül"]):
        _, d = game_api.daily_claim(acc.token)
        return AgentResult(reply=format_api_result("/players/daily-claim", d))

    if _match(text, [r"görev\s*topla", r"görev\s*claim", r"ödül\s*al", r"quest\s*claim"]):
        results = game_api.claim_ready_quests(acc.token)
        return AgentResult(reply=format_quest_claims(results))

    if _match(text, [r"görev", r"quest"]):
        res = call("GET", "/quests", token=acc.token, delay=0.3)
        return AgentResult(reply=format_quests(res.get("data", {})))

    if _match(text, [r"hap\s*kullan", r"can\s*doldur", r"pills", r"sağlık"]):
        try:
            result = game_api.use_pills(acc.token)
            return AgentResult(reply=format_pills(result))
        except Exception as e:
            return AgentResult(reply=f"❌ Hap kullanılamadı: {e}")

    if _match(text, [r"makale", r"gazete", r"press", r"yazı paylaş"]):
        if not _match(text, [r"başlık", r"title", r"konu:"]) or len(text) < 30:
            return AgentResult(
                reply=(
                    "📰 Makale için başlık + içerik gerekli.\n\n"
                    "Örnek:\n"
                    "`makale başlık: Rapor konu: Bugün fabrikada 2500 altın kazandım...`"
                )
            )

    if _match(
        text,
        [
            r"ülke\s*list",
            r"ülkeler",
            r"ülke listele",
            r"hangi ülk",
            r"countries",
        ],
    ):
        countries = game_api.list_countries(acc.token)
        buttons = [
            [(c.get("name", "?")[:40], f"country:{c['id']}")]
            for c in countries[:8]
            if c.get("id")
        ]
        return AgentResult(
            reply=format_countries(countries),
            inline_buttons=buttons or None,
        )

    if _match(
        text,
        [
            r"ülke\s*yok",
            r"neden ülke",
            r"ülkeye katıl",
            r"ülke seç",
            r"ülkeye git",
            r"gidebilir",
            r"katıl",
            r"ülke:",
            r"ülke\s+[A-Za-zÇĞİÖŞÜçğıöşü]",
        ],
    ):
        prof = game_api.get_profile(acc.token)
        if prof.country_id:
            return AgentResult(
                reply=(
                    f"Zaten *{prof.country_name}* ülkesindesin "
                    f"({prof.province_name or 'eyalet bilinmiyor'}).\n"
                    f"Profilde 'yok' görüyorsan `/status` ile yenile."
                )
            )

        countries = game_api.list_countries(acc.token)
        named = re.search(r"ülke\s*[:=]?\s*(.+)$", text, re.I)
        if named:
            target = game_api.find_country_by_name(countries, named.group(1).strip())
            if target:
                result = game_api.select_country(acc.token, target["id"])
                return AgentResult(reply=format_country_result(result))

        for hint in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{4,}", text):
            if hint.lower() in ("neden", "gidebilir", "ülkeye", "katıl", "seç", "git"):
                continue
            target = game_api.find_country_by_name(countries, hint)
            if target:
                result = game_api.select_country(acc.token, target["id"])
                return AgentResult(reply=format_country_result(result))

        try:
            result = game_api.auto_assign_country(acc.token)
            return AgentResult(reply=format_country_result(result))
        except Exception as auto_err:
            buttons = [
                [(c.get("name", "?")[:40], f"country:{c['id']}")]
                for c in countries[:6]
                if c.get("id")
            ]
            return AgentResult(
                reply=(
                    f"Otomatik atama başarısız: {auto_err}\n\n"
                    "Aşağıdan ülke seç veya `ülke: İsim` yaz:\n\n"
                    + format_countries(countries, limit=6)
                ),
                inline_buttons=buttons or None,
            )

    return None
