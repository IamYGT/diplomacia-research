"""35+ kullanıcılar için sade arayüz — büyük butonlar, az jargon."""

from __future__ import annotations

import html
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .easy_role import (
    default_program_idle_text,
    farm_program_idle_text,
    war_ui_enabled,
)
from .modules.mission_types import MissionPhase, MissionRuntime, PhaseStatus
from .user_errors import format_ms
from .help_easy import format_help_easy_html
from .version import get_version_label

PHASE_LABELS_TR: dict[str, str] = {
    "war_tick": "⚔️ Savaşa katılıyor",
    "farm_tick": "🌾 Fabrikada çalışıyor",
    "train_tick": "🏋️ Antrenman yapıyor",
}

STATUS_LABELS_TR: dict[str, str] = {
    "pending": "Sırada bekliyor",
    "in_progress": "Şu an yapıyor",
    "waiting": "Kısa süre bekleyecek",
    "done": "Bu adım bitti",
    "failed": "Bu adımda sorun oldu",
    "skipped": "Bu adım atlandı",
}


def phase_label_tr(phase_value: str | None) -> str:
    if not phase_value:
        return "✅ Program tamamlandı"
    return PHASE_LABELS_TR.get(phase_value, "Devam ediyor")


def status_label_tr(status: str | None) -> str:
    if not status:
        return ""
    raw = status.value if isinstance(status, PhaseStatus) else str(status)
    return STATUS_LABELS_TR.get(raw, raw)


def format_program_status(rt: MissionRuntime | None, *, account_name: str = "") -> str:
    if not rt:
        if account_name and not war_ui_enabled(account_name):
            return farm_program_idle_text(account_name)
        if account_name:
            return default_program_idle_text(account_name)
        return default_program_idle_text("hesabın")
    phase = (
        rt.plan.phases[rt.phase_index].phase.value
        if rt.phase_index < len(rt.plan.phases)
        else None
    )
    show_war = any(p.phase == MissionPhase.WAR_TICK for p in rt.plan.phases)
    target = html.escape(str(rt.plan.war_label or "seçili savaş"))
    wait = ""
    if rt.phase_status == PhaseStatus.WAITING and rt.wait_reason:
        reason = {
            "war_cooldown": "Savaş için bekleme süresi",
            "travel": "Yolculuk bitene kadar",
            "work_cooldown": "Fabrika için bekleme",
            "training_cooldown": "Antrenman için bekleme",
        }.get(rt.wait_reason, "Kısa bekleme")
        if rt.wait_until:
            wait = f"\n⏳ {reason} — birazdan devam eder."
    war_line = f"Hedef savaş: {target}\n" if show_war else ""
    return (
        f"<b>📋 Program çalışıyor</b>\n\n"
        f"Hesap: <b>{html.escape(rt.account_name)}</b>\n"
        f"Şu an: <b>{phase_label_tr(phase)}</b>\n"
        f"{war_line}"
        f"Durum: {status_label_tr(rt.phase_status)}{wait}\n\n"
        "<i>Devam etmek için «Programı Çalıştır» butonuna bas.</i>"
    )


def format_program_result(
    ok: bool,
    *,
    complete: bool = False,
    wait_ms: int | None = None,
    detail: str = "",
    rewards: list[str] | None = None,
) -> str:
    reward_block = ""
    if rewards:
        reward_block = "\n\n" + "\n".join(rewards)
    if complete:
        steps = "Fabrika ve antrenman adımları bitti."
        return (
            "✅ <b>Program tamamlandı!</b>\n\n"
            f"{steps}"
            f"{reward_block}"
        )
    if wait_ms and wait_ms > 0:
        return (
            f"⏳ <b>Biraz beklemen gerekiyor</b>\n\n"
            f"{format_ms(wait_ms)} sonra tekrar «Programı Çalıştır» de."
            f"{reward_block}"
        )
    if ok:
        base = "✅ <b>Adım tamam</b> — devam etmek için tekrar basabilirsin."
        if detail:
            base = f"✅ <b>Adım tamam</b>\n{detail}"
        return f"{base}{reward_block}"
    return f"❌ <b>İşlem olmadı</b>\n{html.escape(detail or 'Biraz sonra tekrar dene.')}"


def format_onboarding_guide_html(*, keyboard_hidden: bool = False, war_enabled: bool = True) -> str:
    war_block = (
        "2️⃣ <b>⚔️ Savaşa Vur</b>\n"
        "   Açık savaşa tek tıkla katılır.\n\n"
    )
    program_line = (
        "   Üçünü sırayla yapar: savaş → altın → antrenman.\n\n"
        if war_enabled
        else "   Fabrika + antrenman sırasını yapar.\n\n"
    )
    base = (
        "<b>👋 İlk kez mi? — 3 buton yeterli</b>\n\n"
        "1️⃣ <b>🌾 Altın Kazan</b>\n"
        "   Fabrikada çalışır, para toplar.\n\n"
        + (war_block if war_enabled else "")
        + "3️⃣ <b>▶️ Programı Çalıştır</b>\n"
        + program_line
    )
    if keyboard_hidden:
        return (
            base
            + "<i>Alttaki butonları kapattıysan sorun değil — "
            "üstteki <b>Ana | Savaş | Seyahat</b> sekmeleriyle gezebilirsin.\n"
            "Takılırsan «🔄 Yenile» veya «🏠 Ana».</i>"
        )
    return (
        base
        + "<i>Alttaki büyük butonlara basman yeterli.\n"
        "Üstte <b>Ana | Savaş | Seyahat</b> sekmeleri de var.\n"
        "Takılırsan «❓ Yardım» veya «🏠 Ana Sayfa».</i>"
    )


def summarize_mission_step_rewards(step) -> list[str]:
    """Program adımı sonrası 35+ için net ödül satırları."""
    lines: list[str] = []
    phase = step.phase.value if getattr(step, "phase", None) else None

    for action in step.actions or []:
        if not isinstance(action, dict):
            continue
        farm = action.get("farm")
        if isinstance(farm, dict) and farm.get("ok"):
            earned = farm.get("earned") or {}
            money = int(earned.get("money") or 0)
            diamonds = int(earned.get("diamonds") or 0)
            xp = int(earned.get("xp") or 0)
            if money > 0:
                lines.append(f"💰 <b>Altın kazandın:</b> +{money:,}")
            if diamonds > 0:
                lines.append(f"💎 <b>Elmas:</b> +{diamonds:,}")
            if xp > 0:
                lines.append(f"⭐ <b>Deneyim:</b> +{xp:,}")
            continue

        if action.get("ok") and (action.get("war_id") or action.get("side")):
            data = (action.get("result") or {}).get("data") or {}
            dmg = data.get("damage") or data.get("contribution")
            if dmg is not None:
                lines.append(f"⚔️ <b>Savaş katkın:</b> {dmg}")
            else:
                lines.append("⚔️ <b>Savaşa katıldın</b> — vuruş gönderildi.")
            continue

        training = action.get("training")
        if isinstance(training, dict):
            if training.get("ok"):
                d = (training.get("result") or {}).get("data") or {}
                reward = d.get("earned") or d.get("reward") or {}
                xp = int(reward.get("xp") or 0) if isinstance(reward, dict) else 0
                if xp:
                    lines.append(f"🏋️ <b>Antrenman:</b> +{xp:,} XP")
                else:
                    lines.append("🏋️ <b>Antrenman tamam</b>")
            elif training.get("skipped") == "free_attack_cooldown":
                lines.append("🏋️ Antrenman için henüz erken — sonra tekrar dene.")

    if not lines and phase == "war_tick" and step.ok:
        lines.append("⚔️ <b>Savaş adımı tamam</b>")
    elif not lines and phase == "farm_tick" and step.ok:
        lines.append("🌾 <b>Fabrika adımı tamam</b>")
    elif not lines and phase == "train_tick" and step.ok:
        lines.append("🏋️ <b>Antrenman adımı tamam</b>")

    return lines


def format_program_step_message(step) -> str:
    """Program adımı — ana mesaj + ödül özeti."""
    rewards = summarize_mission_step_rewards(step)
    if step.mission_complete:
        return format_program_result(True, complete=True, rewards=rewards)
    if step.blocked and step.wait_ms:
        return format_program_result(False, wait_ms=step.wait_ms, rewards=rewards)
    if step.ok:
        return format_program_result(True, rewards=rewards)
    return format_program_result(False, detail=step.error or "")



def dashboard_headline(snap: dict, *, autofarm: bool, war_enabled: bool = True) -> str:
    health = int(snap.get("health") or 0)
    if health < 40:
        return "⚠️ <b>Canın çok düşük</b> — önce «Can Doldur»"
    if health < 100 and int(snap.get("pills") or 0) > 0:
        return "💊 <b>Canını yükselt</b> — «Can Doldur» butonuna bas"
    if snap.get("work_ready"):
        return "✅ <b>Fabrika hazır</b> — «Altın Kazan» veya «Programı Çalıştır»"
    if war_enabled and int(snap.get("war_active") or 0) > 0:
        return "⚔️ <b>Savaş var</b> — «Savaşa Vur» veya programı başlat"
    if snap.get("training_ready"):
        return "🏋️ <b>Antrenman hazır</b> — programı çalıştırabilirsin"
    if not autofarm:
        return "💡 İstersen ayarlardan otomatik farm açabilirsin"
    return "👆 Alttaki büyük butonlardan birine bas — yeterli"


def simplify_dashboard_html(body: str) -> str:
    replacements = [
        ("📌 Şimdi ne yapmalı?", "👆 Sıradaki işin"),
        ("<b>🤖 Bot durumu</b>", "<b>⚙️ Otomatik ayarlar</b>"),
        ("Görev:", "Mod:"),
        ("work+stat (~10 dk)", "yaklaşık 10 dakikada bir"),
        ("stat+premium sync (~10 dk)", "yaklaşık 10 dakikada bir"),
        ("⏳ API bekleme:", "⏳ Kısa ara:"),
        (" UTC", ""),
        ("⋯ Daha →", "menüden"),
    ]
    out = body
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def format_welcome_easy_html(uid: int, account_name: str | None, *, gemini_ok: bool, linked: bool) -> str:
    if linked and account_name:
        return (
            f"<b>Hoş geldin!</b> Diplomacia Bot {get_version_label()}\n\n"
            f"Hesabın: <b>{html.escape(account_name)}</b>\n\n"
            "<b>3 büyük buton yeterli:</b>\n"
            "🌾 Altın Kazan · ⚔️ Savaşa Vur · ▶️ Programı Çalıştır\n\n"
            "Alttaki klavyeden birine bas — gerisi bot halleder.\n\n"
            f"<i>Telegram numaran: {uid}</i>"
        )
    return (
        f"<b>Hoş geldin!</b> Diplomacia Bot {get_version_label()}\n\n"
        "Önce oyun hesabını bağlaman lazım.\n\n"
        "<b>Adımlar:</b>\n"
        "1️⃣ /connect yaz\n"
        "2️⃣ Oyunda konsola kodu yapıştır\n"
        "3️⃣ Çıkan uzun metni buraya gönder\n\n"
        "<i>Bitince büyük butonlarla oynarsın — komut bilmen gerekmez.</i>"
    )


EASY_MENU_LABELS: dict[str, str] = {
    "🏠 ana sayfa": "dashboard",
    "⚔️ savaş": "war_tab",
    "🚶 seyahat": "travel_tab",
    "🌾 altın kazan": "farm yap",
    "🌾 farm yap": "farm yap",
    "⚔️ savaşa vur": "savaşa vur",
    "▶️ programı çalıştır": "programı çalıştır",
    "▶️ programi calistir": "programı çalıştır",
    "🛑 programı durdur": "programı durdur",
    "💊 can doldur": "hap kullan",
    "🎁 günlük hediye": "günlük",
    "🎁 günlük": "günlük",
    "❓ yardım": "yardım",
    "⚙️ ayarlar": "ayarlar",
    "⚡ statlar": "statlar",
    "👥 filo": "filo",
    "📊 durum": "dashboard",
}


def main_reply_keyboard_easy() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("🏠 Ana Sayfa"),
                KeyboardButton("⚔️ Savaş"),
                KeyboardButton("🚶 Seyahat"),
            ],
            [
                KeyboardButton("🌾 Altın Kazan"),
                KeyboardButton("▶️ Programı Çalıştır"),
            ],
            [
                KeyboardButton("💊 Can Doldur"),
                KeyboardButton("🎁 Günlük Hediye"),
            ],
            [KeyboardButton("❓ Yardım"), KeyboardButton("⚙️ Ayarlar")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Sekmeler veya buton…",
    )


def program_hub_markup(account_name: str) -> InlineKeyboardMarkup:
    name = account_name.strip().lower()
    war_row = (
        [
            InlineKeyboardButton("⚔️ Savaşa Vur", callback_data=f"easy:war:{name}"),
            InlineKeyboardButton("🌾 Altın Kazan", callback_data="action:farmboard"),
        ]
        if war_ui_enabled(name)
        else [InlineKeyboardButton("🌾 Altın Kazan", callback_data="action:farmboard")]
    )
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Programı Çalıştır", callback_data=f"easy:run:{name}")],
            war_row,
            [
                InlineKeyboardButton("📋 Programı Başlat", callback_data=f"easy:start:{name}"),
                InlineKeyboardButton("🛑 Durdur", callback_data=f"easy:stop:{name}"),
            ],
            [InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")],
        ]
    )


def dashboard_easy_row(account_name: str) -> list[InlineKeyboardButton]:
    name = account_name.strip().lower()
    row = [
        InlineKeyboardButton("▶️ Programı Çalıştır", callback_data=f"easy:run:{name}"),
    ]
    if war_ui_enabled(name):
        row.append(InlineKeyboardButton("⚔️ Savaşa Vur", callback_data=f"easy:war:{name}"))
    return row


def matches_easy_phrase(text: str, patterns: list[str]) -> bool:
    tl = text.lower().strip()
    return any(re.search(p, tl, re.I) for p in patterns)
