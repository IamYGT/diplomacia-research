from __future__ import annotations

import re
from dataclasses import asdict
from typing import TYPE_CHECKING

from . import farmer, game_api
from .account_config import get_config, update_config_field
from .dynamic_context import format_plan_summary, invalidate_snapshot_cache
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

    if _match(text, [r"^yardım$", r"^help$", r"komutlar", r"ne yapmalı", r"ne yapayım", r"nasıl kullan"]):
        from .telegram_ui import format_help_html

        return AgentResult(
            reply=format_help_html(),
            parse_mode="HTML",
            inline_buttons=[
                [("🏠 Ana Sayfa", "dash:home"), ("🌾 Farm", "action:farm")],
                [("🔗 Bağlan", "menu:connect"), ("⋯ Daha", "menu:extras")],
            ],
        )

    if _match(text, [r"^connect$", r"token", r"jwt", r"bağlan", r"hesap bağla", r"konsol"]):
        from .telegram_ui import format_token_guide_html

        return AgentResult(
            reply=format_token_guide_html() + "\n\n<i>/connect yaz — konsol kodu ayrı mesajda gelir.</i>",
            parse_mode="HTML",
            inline_buttons=[
                [("📋 Konsol kodu", "connect:script"), ("🔗 Oyunu aç", "menu:connect")],
            ],
        )

    acc = get_account(default_account) if default_account else None
    if not acc:
        return AgentResult(
            reply="Henüz hesap bağlı değil.\n\n`/connect` komutu ile JWT token rehberini aç, token'ı yapıştır.",
            inline_buttons=[[("🔗 Bağlan", "menu:connect")]],
        )

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
        from .modules import premium as premium_mod
        from .modules.orchestrator import tick_account

        if premium_mod.premium_auto_work_active(acc.token):
            r = tick_account(acc.token, acc.name)
            update_after_farm(acc.name, r.balance_after)
            invalidate_snapshot_cache(acc.name)
            msg = (
                "⭐ Premium auto/work açık — sunucu farm yapıyor.\n"
                "Bot tick: stat + premium sync (manuel work yok).\n"
            )
            if r.actions:
                msg += f"📎 `{str(r.actions)[:300]}`"
            return AgentResult(reply=msg)

        r = tick_account(acc.token, acc.name)
        update_after_farm(acc.name, r.balance_after)
        invalidate_snapshot_cache(acc.name)
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

    if _match(text, [r"^statlar$", r"stat\s*merkez", r"pasif\s*detay", r"yetenekler"]):
        from . import game_features
        from .account_config import get_config
        from .stat_board import format_stat_board_html, stat_board_callback_rows
        from .account_runtime import interactive_account_context

        def _board():
            with interactive_account_context(acc):
                return game_features.fetch_stat_board(acc.token, acc.name)

        pack = _board()
        if not pack.get("ok"):
            return AgentResult(reply=f"❌ {pack.get('error')}")
        analysis = pack.get("analysis") or {}
        return AgentResult(
            reply=format_stat_board_html(pack, analysis, get_config(acc.name)),
            inline_buttons=stat_board_callback_rows(analysis),
            parse_mode="HTML",
        )

    if _match(text, [r"önce\s", r"öncelik", r"öncelikli"]):
        from . import game_features
        from .account_config import get_config, update_config_field
        from .stat_board import (
            format_stat_board_html,
            resolve_active_skill_key,
            skill_short_name,
            stat_board_callback_rows,
        )
        from .account_runtime import interactive_account_context

        cleaned = re.sub(
            r"(?i)\b(önce|öncelik|öncelikli|stat|statlar|yükselt|olsun|yap)\b",
            " ",
            text,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        def _prio():
            with interactive_account_context(acc):
                pack = game_features.fetch_stat_board(acc.token, acc.name)
                if not pack.get("ok"):
                    return None, pack
                skill = resolve_active_skill_key(pack.get("analysis") or {}, cleaned)
                if not skill:
                    return None, pack
                cfg = get_config(acc.name)
                prio = [s for s in cfg.stat_priority if s != skill]
                prio.insert(0, skill)
                update_config_field(acc.name, stat_priority=prio)
                return skill, pack

        skill, pack = _prio()
        if not skill:
            return AgentResult(reply="❌ Hangi stat? Örnek: «önce Kışla» veya «öncelik Bilim insanı»")
        analysis = pack.get("analysis") or {}
        name = skill_short_name(skill)
        return AgentResult(
            reply=f"✅ Önce yükseltilen: <b>{name}</b>\n\n"
            + format_stat_board_html(pack, analysis, get_config(acc.name)),
            inline_buttons=stat_board_callback_rows(analysis),
            parse_mode="HTML",
        )

    if _match(text, [r"elmas.*stat", r"stat.*elmas", r"💎.*stat"]):
        from . import game_features
        from .stat_board import format_stat_spend_result_html
        from .account_runtime import interactive_account_context

        def _dia():
            with interactive_account_context(acc):
                return game_features.run_skill_upgrade_priority(
                    acc.token, acc.name, currency="diamond"
                )

        r = _dia()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_stat_spend_result_html(r), parse_mode="HTML")

    if _match(text, [r"stat\s*yükselt", r"stat\s*oto", r"oto\s*stat", r"stat\s*şimdi"]):
        from . import game_features
        from .stat_board import format_stat_spend_result_html
        from .account_runtime import interactive_account_context

        def _auto():
            with interactive_account_context(acc):
                return game_features.run_stat_auto_now(acc.token, acc.name)

        r = _auto()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_stat_spend_result_html(r), parse_mode="HTML")

    if _match(text, [r"pasif\s+.+\s*harca", r"stat\s*harca\s+\w", r"stat\s*(\d+)\s*harca", r"stat\s*harca\s*(\d+)"]):
        from . import game_features
        from .stat_board import format_stat_spend_result_html, resolve_passive_skill_key
        from .account_runtime import interactive_account_context

        token = re.sub(r"(?i)pasif|stat|harca|puan", "", text).strip()

        def _spend():
            with interactive_account_context(acc):
                pack = game_features.fetch_stat_board(acc.token, acc.name)
                analysis = pack.get("analysis") or {}
                skill = resolve_passive_skill_key(analysis, token) if token else None
                if not skill and token.isdigit():
                    skill = resolve_passive_skill_key(analysis, token)
                if skill:
                    return game_features.run_stat_spend(acc.token, acc.name, skill=skill)
                return game_features.run_stat_spend(acc.token, acc.name)

        r = _spend()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_stat_spend_result_html(r), parse_mode="HTML")

    if _match(text, [r"stat\s*harca", r"pasif\s*stat\s*harca", r"skill\s*harca", r"puan\s*harca"]):
        from . import game_features
        from .stat_board import format_stat_board_html, format_stat_spend_result_html, stat_board_callback_rows
        from .account_config import get_config
        from .account_runtime import interactive_account_context

        def _spend():
            with interactive_account_context(acc):
                return game_features.run_stat_spend(acc.token, acc.name)

        r = _spend()
        invalidate_snapshot_cache(acc.name)
        if r.get("ok"):
            return AgentResult(reply=format_stat_spend_result_html(r), parse_mode="HTML")

        def _board():
            with interactive_account_context(acc):
                return game_features.fetch_stat_board(acc.token, acc.name)

        pack = _board()
        analysis = pack.get("analysis") or {}
        if pack.get("ok"):
            return AgentResult(
                reply=format_stat_board_html(pack, analysis, get_config(acc.name)),
                inline_buttons=stat_board_callback_rows(analysis),
                parse_mode="HTML",
            )
        return AgentResult(reply=f"❌ {r.get('error') or pack.get('error')}")

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
        from . import game_features
        from .account_config import get_config
        from .war_board import format_war_board_html, war_board_callback_rows
        from .account_runtime import interactive_account_context

        def _wars():
            with interactive_account_context(acc):
                return game_features.fetch_war_board(acc.token, acc.name)

        pack = _wars()
        if not pack.get("ok"):
            return AgentResult(reply=f"❌ {pack.get('error')}")
        analysis = pack.get("analysis") or {}
        return AgentResult(
            reply=format_war_board_html(pack.get("data") or {}, analysis, get_config(acc.name)),
            inline_buttons=war_board_callback_rows(analysis),
            parse_mode="HTML",
        )

    if _match(text, [r"katkı\s*(\d+)", r"savaş\s*(\d+)\s*katk"]):
        m = re.search(r"(\d+)", text)
        if m:
            idx = int(m.group(1))
            from .account_runtime import interactive_account_context

            def _contrib():
                with interactive_account_context(acc):
                    pack = game_features.fetch_war_board(acc.token, acc.name)
                    numbered = (pack.get("analysis") or {}).get("numbered") or []
                    pick = next((w for w in numbered if w.get("index") == idx), None)
                    if not pick:
                        return {"ok": False, "error": f"#{idx} yok"}
                    return game_features.run_war_contribute(
                        acc.token, acc.name, war_id=str(pick["id"])
                    )

            r = _contrib()
            from .feature_reports import format_war_contribute_html

            return AgentResult(
                reply=format_war_contribute_html(r, r.get("analysis")),
                parse_mode="HTML",
            )

    if _match(text, [r"hedef\s*savaş\s*(\d+)", r"savaş\s*hedef\s*(\d+)", r"war\s*(\d+)\s*hedef"]):
        m = re.search(r"(\d+)", text)
        if m:
            idx = int(m.group(1))
            from . import game_features
            from .account_config import update_config_field
            from .account_runtime import interactive_account_context

            def _board():
                with interactive_account_context(acc):
                    return game_features.fetch_war_board(acc.token, acc.name)

            pack = _board()
            numbered = (pack.get("analysis") or {}).get("numbered") or []
            pick = next((w for w in numbered if w.get("index") == idx), None)
            if pick and pick.get("id"):
                update_config_field(acc.name, target_war_id=str(pick["id"]))
                title = pick.get("display_title") or pick.get("war_name") or idx
                return AgentResult(
                    reply=f"✅ Hedef savaş: **#{idx}** {title}",
                    inline_buttons=[[("⚔️ Savaş panosu", "action:wars"), ("🗡️ Katkı", "action:warcontrib")]],
                )
            return AgentResult(reply=f"❌ #{idx} savaş bulunamadı — önce `savaş` yazıp listeyi gör.")

    if _match(text, [r"savaşa\s*katk", r"katkı\s*ver", r"contribute"]):
        from . import game_features
        from .response_format import format_war_contribute
        from .account_runtime import interactive_account_context

        def _contrib():
            with interactive_account_context(acc):
                return game_features.run_war_contribute(acc.token, acc.name)

        r = _contrib()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_war_contribute(r))

    if _match(text, [r"antrenman", r"training", r"ücretsiz\s*saldır"]):
        from . import game_features
        from .response_format import format_training_bundle
        from .account_runtime import interactive_account_context

        def _train():
            with interactive_account_context(acc):
                war = game_features.fetch_training_war(acc.token)
                atk = game_features.run_training_attack(acc.token, acc.name)
                return war, atk

        war, atk = _train()
        invalidate_snapshot_cache(acc.name)
        tw = war.get("war") if war.get("ok") else None
        return AgentResult(reply=format_training_bundle(tw, atk))

    if _match(
        text,
        [
            r"fabrikam",
            r"fabrika\s*merkez",
            r"fabrika\s*durum",
            r"fabrika\s*list",
            r"^fabrika$",
        ],
    ):
        from . import game_features
        from .account_config import get_config
        from .factory_board import factory_board_callback_rows, format_factory_board_html
        from .account_runtime import interactive_account_context

        def _board():
            with interactive_account_context(acc):
                return game_features.fetch_factory_board(acc.token, acc.name)

        pack = _board()
        if not pack.get("ok") and not pack.get("factories"):
            return AgentResult(reply=f"❌ {pack.get('error')}")
        analysis = pack.get("analysis") or {}
        return AgentResult(
            reply=format_factory_board_html(pack, analysis, get_config(acc.name)),
            inline_buttons=factory_board_callback_rows(analysis),
            parse_mode="HTML",
        )

    if _match(text, [r"fabrika\s*(\d+)\s*kapat", r"kapat\s*fabrika\s*(\d+)"]):
        m = re.search(r"(\d+)", text)
        if m:
            idx = int(m.group(1))
            from .account_runtime import interactive_account_context

            def _close():
                with interactive_account_context(acc):
                    pack = game_features.fetch_factory_board(acc.token, acc.name)
                    owned = pack.get("owned_ids") or []
                    if not (0 < idx <= len(owned)):
                        return {"ok": False, "error": f"#{idx} yok"}
                    return game_features.run_factory_action(
                        acc.token, acc.name, "close", factory_id=owned[idx - 1]
                    )

            from .factory_board import format_factory_action_html

            r = _close()
            invalidate_snapshot_cache(acc.name)
            return AgentResult(reply=format_factory_action_html(r), parse_mode="HTML")

    if _match(text, [r"fabrika\s*kur", r"fabrika\s*inşa", r"build\s*factory"]):
        from .account_runtime import interactive_account_context
        from .factory_board import format_factory_action_html

        def _build():
            with interactive_account_context(acc):
                return game_features.run_factory_action(acc.token, acc.name, "build")

        r = _build()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_factory_action_html(r), parse_mode="HTML")

    if _match(text, [r"fabrikadan\s*ayrıl", r"fabrika\s*ayrıl", r"leave\s*factory"]):
        from .account_runtime import interactive_account_context
        from .factory_board import format_factory_action_html

        def _leave():
            with interactive_account_context(acc):
                return game_features.run_factory_action(acc.token, acc.name, "leave")

        r = _leave()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_factory_action_html(r), parse_mode="HTML")

    if _match(text, [r"fabrika\s*(\d+)\s*çek", r"çek\s*fabrika\s*(\d+)", r"withdraw\s*(\d+)"]):
        m = re.search(r"(\d+)", text)
        if m:
            idx = int(m.group(1))
            from .account_runtime import interactive_account_context
            from .factory_board import format_factory_action_html

            def _wd():
                with interactive_account_context(acc):
                    pack = game_features.fetch_factory_board(acc.token, acc.name)
                    owned = pack.get("owned_ids") or []
                    if not (0 < idx <= len(owned)):
                        return {"ok": False, "error": f"#{idx} yok"}
                    return game_features.run_factory_action(
                        acc.token, acc.name, "withdraw", factory_id=owned[idx - 1]
                    )

            r = _wd()
            invalidate_snapshot_cache(acc.name)
            return AgentResult(reply=format_factory_action_html(r), parse_mode="HTML")

    if _match(text, [r"fabrika\s*ana\s*(\d+)", r"ana\s*fabrika\s*(\d+)"]):
        m = re.search(r"(\d+)", text)
        if m:
            idx = int(m.group(1))
            from .account_runtime import interactive_account_context

            def _prim():
                with interactive_account_context(acc):
                    pack = game_features.fetch_factory_board(acc.token, acc.name)
                    owned = pack.get("owned_ids") or []
                    if not (0 < idx <= len(owned)):
                        return None
                    update_config_field(acc.name, primary_factory_id=owned[idx - 1])
                    return owned[idx - 1]

            fid = _prim()
            if fid:
                return AgentResult(reply=f"✅ Ana fabrika: #{idx}\n`{fid}`")
            return AgentResult(reply=f"❌ #{idx} fabrika yok")

    if _match(text, [r"asker", r"military", r"birlik", r"ordu"]):
        from . import game_features
        from .response_format import format_military_bundle, format_military_ops
        from .account_runtime import interactive_account_context

        def _mil():
            with interactive_account_context(acc):
                m = game_features.fetch_military(acc.token)
                o = game_features.fetch_military_ops(acc.token)
                return m, o

        m, o = _mil()
        if not m.get("ok"):
            return AgentResult(reply=f"❌ {m.get('error')}")
        text_out = format_military_bundle(m.get("data") or {})
        if o.get("ok") and o.get("data"):
            text_out += "\n\n" + format_military_ops(o["data"])
        return AgentResult(reply=text_out)

    if _match(text, [r"hap\s*üret", r"craft", r"elmas\s*hap"]):
        from . import game_features
        from .response_format import format_craft_result
        from .account_runtime import interactive_account_context

        def _craft():
            with interactive_account_context(acc):
                return game_features.run_craft_pills(acc.token, acc.name)

        r = _craft()
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_craft_result(r))

    if _match(text, [r"\bonline\b", r"kaç\s*kişi", r"oyuncu\s*say"]):
        from . import game_features
        from .response_format import format_online_info
        from .account_runtime import interactive_account_context

        def _on():
            with interactive_account_context(acc):
                return game_features.fetch_online(acc.token)

        r = _on()
        if not r.get("ok"):
            return AgentResult(reply=f"❌ {r.get('error')}")
        return AgentResult(reply=format_online_info(r))

    if _match(text, [r"otomasyon", r"auto\s*durum", r"auto\s*status"]):
        from . import game_features
        from .response_format import format_auto_status_detail
        from .account_runtime import interactive_account_context

        def _auto():
            with interactive_account_context(acc):
                return game_features.fetch_auto_status(acc.token)

        return AgentResult(reply=format_auto_status_detail(_auto()))

    if _match(text, [r"pasif\s*detay", r"skill\s*list", r"yetenek\s*list"]):
        from . import game_features
        from .response_format import format_passive_detail
        from .account_runtime import interactive_account_context

        def _ps():
            with interactive_account_context(acc):
                return game_features.fetch_passive_detail(acc.token)

        r = _ps()
        if not r.get("ok"):
            return AgentResult(reply=f"❌ {r.get('error')}")
        return AgentResult(reply=format_passive_detail(r.get("data") or {}))

    if _match(text, [r"\bping\b", r"bağlantı\s*test"]):
        from . import game_features
        from .response_format import format_ping_result
        from .account_runtime import interactive_account_context

        def _ping():
            with interactive_account_context(acc):
                return game_features.run_ping(acc.token)

        return AgentResult(reply=format_ping_result(_ping()))

    if _match(text, [r"görev\s*list", r"görevlerim"]):
        from . import game_features
        from .feature_reports import format_quest_board_html
        from .account_runtime import interactive_account_context

        def _q():
            with interactive_account_context(acc):
                return game_features.fetch_quests(acc.token)

        r = _q()
        if not r.get("ok"):
            return AgentResult(reply=f"❌ {r.get('error')}")
        return AgentResult(
            reply=format_quest_board_html(r.get("quests") or [], r.get("analysis")),
            inline_buttons=[[("📜 Görev topla", "action:quests"), ("🏠 Ana Sayfa", "dash:home")]],
            parse_mode="HTML",
        )

    if _match(
        text,
        [r"durum", r"ne durumda", r"bakiye", r"profil", r"hesabım", r"şu an", r"status"],
    ):
        p = game_api.get_profile(acc.token)
        return AgentResult(reply=format_profile({"player": asdict(p)}))

    if _match(text, [r"farm\s*merkez", r"elmas\s*hap", r"hap\s*döng", r"^farm$"]):
        from . import game_features
        from .account_config import get_config
        from .farm_board import farm_board_callback_rows, format_farm_board_html
        from .account_runtime import interactive_account_context

        def _board():
            with interactive_account_context(acc):
                return game_features.fetch_farm_board(acc.token, acc.name)

        pack = _board()
        if not pack.get("ok"):
            return AgentResult(reply=f"❌ {pack.get('error')}")
        analysis = pack.get("analysis") or {}
        return AgentResult(
            reply=format_farm_board_html(pack, analysis, get_config(acc.name)),
            inline_buttons=farm_board_callback_rows(analysis),
            parse_mode="HTML",
        )

    if _match(text, [r"farm", r"çalış", r"fabrika", r"iş yap", r"grind", r"farm yap"]):
        cycles = 1
        m = re.search(r"(\d+)\s*(kez|tur|döngü|x)", text.lower())
        if m:
            cycles = min(int(m.group(1)), 10)
        if cycles > 1:
            r = farmer.run_farm(acc.token, acc.name, cycles)
            update_after_farm(acc.name, r.balance_after)
            invalidate_snapshot_cache(acc.name)
            return AgentResult(reply=farmer.format_farm_result(r))

        from .dynamic_context import peek_snapshot_cache
        from .user_errors import format_farm_preflight
        from . import game_features
        from .farm_board import farm_board_callback_rows, format_farm_board_html, format_farm_action_html
        from .account_config import get_config
        from .account_runtime import interactive_account_context

        snap = peek_snapshot_cache(acc.name) or {}
        if format_farm_preflight(snap):

            def _board():
                with interactive_account_context(acc):
                    return game_features.fetch_farm_board(acc.token, acc.name)

            pack = _board()
            analysis = pack.get("analysis") or {}
            return AgentResult(
                reply=format_farm_board_html(pack, analysis, get_config(acc.name)),
                inline_buttons=farm_board_callback_rows(analysis),
                parse_mode="HTML",
            )

        def _work():
            with interactive_account_context(acc):
                return game_features.run_farm_work(acc.token, acc.name)

        result = _work()
        invalidate_snapshot_cache(acc.name)
        if result.get("farm_result"):
            update_after_farm(acc.name, result["farm_result"].balance_after)
        return AgentResult(
            reply=format_farm_action_html(result),
            inline_buttons=[[("🌾 Farm merkezi", "action:farmboard"), ("🔄 Tekrar", "farm:work")]],
            parse_mode="HTML",
        )

    if _match(text, [r"günlük", r"daily", r"günün ödül"]):
        _, d = game_api.daily_claim(acc.token)
        invalidate_snapshot_cache(acc.name)
        return AgentResult(reply=format_api_result("/players/daily-claim", d))

    if _match(text, [r"görev\s*topla", r"görev\s*claim", r"ödül\s*al", r"quest\s*claim"]):
        from . import game_features
        from .feature_reports import format_quest_claim_html
        from .account_runtime import interactive_account_context

        def _claim():
            with interactive_account_context(acc):
                return game_features.claim_quests_smart(acc.token)

        pack = _claim()
        invalidate_snapshot_cache(acc.name)
        if not pack.get("ok"):
            return AgentResult(reply=f"❌ {pack.get('error')}")
        return AgentResult(
            reply=format_quest_claim_html(pack.get("results") or [], pack.get("analysis")),
            parse_mode="HTML",
        )

    if _match(text, [r"görev", r"quest"]):
        res = call("GET", "/quests", token=acc.token, delay=0.3)
        return AgentResult(reply=format_quests(res.get("data", {})))

    if _match(text, [r"hap\s*kullan", r"can\s*doldur", r"pills", r"sağlık"]):
        from .dynamic_context import peek_snapshot_cache
        from .user_errors import format_hap_preflight, format_pill_error

        snap = peek_snapshot_cache(acc.name) or {}
        block = format_hap_preflight(snap)
        if block:
            return AgentResult(reply=block)
        result = game_api.try_use_pills(acc.token)
        if result.get("ok"):
            invalidate_snapshot_cache(acc.name)
            return AgentResult(reply=format_pills(result.get("data") or {}))
        return AgentResult(reply=format_pill_error(result.get("data"), exc=result.get("error")))

    if _match(text, [r"makale", r"gazete", r"press", r"yazı paylaş"]):
        if not _match(text, [r"başlık", r"title", r"konu:"]) or len(text) < 30:
            return AgentResult(
                reply=(
                    "📰 Makale için başlık + içerik gerekli.\n\n"
                    "Örnek:\n"
                    "`makale başlık: Rapor konu: Bugün fabrikada 2500 altın kazandım...`\n\n"
                    "💡 <b>makale beğen</b> yaz → yeni makaleleri anlık beğen\n"
                    "💡 <b>makale beğen aç</b> → otomatik beğenme (~5 dk)"
                ),
                parse_mode="HTML",
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
