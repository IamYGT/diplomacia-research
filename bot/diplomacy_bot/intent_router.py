from __future__ import annotations

import re
from dataclasses import asdict
from typing import TYPE_CHECKING

from . import farmer, game_api
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
            return AgentResult(
                reply=(
                    f"İyidir patron 😎 *{p.username}* hazır.\n"
                    f"💰 {p.balance:,} | lv{p.level} | ❤️ {p.health}/100\n\n"
                    f"Farm: `farm yap` | Durum: `ne durumdayım`"
                )
            )
        except Exception as e:
            return AgentResult(reply=f"Selam! (profil: {e})")

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
