from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
)

from .account_config import get_config, role_label, normalize_role, BOT_ROLES, ROLE_LABELS_TR
from .fleet_manager import count_by_role, fleet_rows
from .dynamic_context import snapshot_account, snapshot_cache_age_sec
from .stealth_client import cooldown_remaining_sec
from .user_errors import format_ms
from .store import Account, list_accounts
from .version import get_version_label

if TYPE_CHECKING:
    pass

# Alt klavye → intent_router / doğrudan handler anahtarı
MENU_LABELS: dict[str, str] = {
    "🏠 ana sayfa": "dashboard",
    "🌾 farm yap": "farm yap",
    "💊 can doldur": "hap kullan",
    "⚡ stat harca": "stat harca",
    "⚡ statlar": "statlar",
    "🎁 günlük ödül": "günlük",
    "⚙️ ayarlar": "ayarlar",
    "❓ yardım": "yardım",
    "👥 filo": "filo",
    # Eski etiketler (geriye uyum)
    "📊 durum": "dashboard",
    "🌾 akıllı farm": "akıllı farm",
    "💊 hap kullan": "hap kullan",
    "📋 planım": "planım",
    "🎁 günlük": "günlük",
    "🤖 hesaplar": "tüm hesaplar",
}

BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Ana sayfa ve klavye"),
    BotCommand("connect", "Diplomacia hesabını bağla"),
    BotCommand("menu", "Kontrol paneli"),
    BotCommand("farm", "Tek farm döngüsü"),
    BotCommand("accounts", "Hesaplarım"),
    BotCommand("fleet", "Çoklu hesap filosu"),
    BotCommand("setrole", "Hesap rolü: farm|war|hybrid"),
    BotCommand("settings", "Bot ayarları"),
    BotCommand("help", "Nasıl kullanılır?"),
]

WORK_MODE_TR = {
    "own": "Kendi fabrika",
    "foreign": "Yabancı fabrika",
    "fixed": "Sabit fabrika",
    "auto": "Otomatik",
}


def normalize_menu_text(text: str) -> str | None:
    return MENU_LABELS.get(text.strip().lower())


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🏠 Ana Sayfa"), KeyboardButton("🌾 Farm Yap")],
            [KeyboardButton("💊 Can Doldur"), KeyboardButton("⚡ Statlar"), KeyboardButton("🎁 Günlük Ödül")],
            [KeyboardButton("⚙️ Ayarlar"), KeyboardButton("👥 Filo"), KeyboardButton("❓ Yardım")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Butona bas veya yaz: farm yap, planım…",
    )


def _bar(pct: int, width: int = 10) -> str:
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def _work_mode_label(mode: str) -> str:
    return WORK_MODE_TR.get(mode, mode)


def _next_steps(snap: dict, acc: Account) -> list[str]:
    """Öncelik sırasına göre kullanıcıya net yönlendirme."""
    steps: list[str] = []
    health = int(snap.get("health") or 0)
    pills = int(snap.get("pills") or 0)
    passive = int(snap.get("passive_available") or 0)

    if health < 50 and pills > 0:
        steps.append("1️⃣ Can çok düşük → <b>💊 Can Doldur</b>")
    elif health < 100 and pills > 0:
        steps.append("1️⃣ Canı yükselt → <b>💊 Can Doldur</b>")
    if passive > 0:
        steps.append(f"{'2️⃣' if steps else '1️⃣'} Statlar otomatik (altın + pasif) — <b>⚡ Statlar</b>")
    if snap.get("premium") and snap.get("auto_work_active"):
        steps.append("⭐ Premium auto/work açık — sunucu farm yapıyor, <b>akıllı farm gerekmez</b>")
    elif snap.get("premium") and not snap.get("auto_work_active"):
        steps.append("⭐ Premium var — autofarm auto/work'ü açar; eyalette olduğundan emin ol")
    if snap.get("free_attack"):
        n = len(steps) + 1
        steps.append(f"{n}️⃣ Ücretsiz antrenman hazır → <b>⋯ Daha → Antrenman</b>")
    if snap.get("quests_claimable"):
        n = len(steps) + 1
        steps.append(f"{n}️⃣ {snap['quests_claimable']} görev ödülü → <b>⋯ Daha → Görev topla</b>")
    if snap.get("work_ready") and not (snap.get("premium") and snap.get("auto_work_active")):
        n = len(steps) + 1
        steps.append(f"{n}️⃣ Fabrika hazır → <b>🌾 Farm Yap</b>")
    elif not steps and not (snap.get("premium") and snap.get("auto_work_active")):
        steps.append("1️⃣ Work bekleniyor — biraz sonra <b>🌾 Farm Yap</b>")
    if not acc.autofarm:
        steps.append("💡 Otomatik farm kapalı — <b>⚙️ Ayarlar</b>dan açabilirsin")
    return steps[:3]


def format_welcome_html(uid: int, account_name: str | None, *, gemini_ok: bool, linked: bool) -> str:
    ai = "🧠 AI koç hazır" if gemini_ok else "ℹ️ AI kapalı — butonlar yeterli"
    if linked and account_name:
        return (
            f"<b>Merhaba! Diplomacia Bot {get_version_label()}</b>\n\n"
            f"Aktif hesap: <b>{html.escape(account_name)}</b>\n"
            f"{ai}\n\n"
            "<b>Nasıl kullanılır?</b>\n"
            "• Alttaki butonlara bas — komut ezberlemene gerek yok\n"
            "• <b>🏠 Ana Sayfa</b> = canlı özet ve hızlı aksiyonlar\n"
            "• <b>⚙️ Ayarlar</b> = otomatik farm, fabrika modu\n\n"
            f"<i>Telegram ID: <code>{uid}</code></i>"
        )
    return (
        f"<b>Merhaba! Diplomacia Bot {get_version_label()}</b>\n\n"
        "Henüz Diplomacia hesabın bağlı değil.\n\n"
        "<b>3 adımda başla:</b>\n"
        "1️⃣ <code>/connect</code> — konsol kodu gelir\n"
        "2️⃣ Oyunda F12 → Console → kodu yapıştır\n"
        "3️⃣ <code>eyJ…</code> token'ı buraya yapıştır\n\n"
        f"{ai}\n"
        f"<i>Telegram ID: <code>{uid}</code></i>"
    )


def format_token_guide_html() -> str:
    return (
        f"<b>🔗 Diplomacia hesabını bağla</b> — {get_version_label()}\n\n"
        "<b>1. Oyuna gir</b>\n"
        "<a href=\"https://diplomacia.com.tr/\">diplomacia.com.tr</a> — giriş yap.\n\n"
        "<b>2. Konsol kodu</b>\n"
        "Alttaki <b>📋 Konsol kodu</b> butonuna bas veya /connect yaz.\n"
        "Bot sana tek satırlık kodu gönderir.\n\n"
        "<b>3. Tarayıcıda</b>\n"
        "• <b>F12</b> → <b>Console</b>\n"
        "• Kodu yapıştır → <b>Enter</b>\n"
        "• Çıkan <code>eyJ…</code> satırını kopyala\n\n"
        "<b>4. Buraya yapıştır</b>\n"
        "Token'ı <b>tek mesaj</b> olarak gönder.\n\n"
        "<i>Pano hatası (NotAllowedError) = normal — konsoldan elle kopyala.</i>\n\n"
        "⚠️ Token oturum anahtarıdır. Kimseyle paylaşma."
    )


def connect_inline_markup(*, include_script_btn: bool = True) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton("🔗 Oyunu aç", url="https://diplomacia.com.tr/"),
        InlineKeyboardButton("📖 Rehber", callback_data="menu:connect"),
    ]
    rows: list[list[InlineKeyboardButton]] = [row1]
    if include_script_btn:
        rows.append(
            [InlineKeyboardButton("📋 Konsol kodu", callback_data="connect:script")]
        )
    rows.append([InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")])
    return InlineKeyboardMarkup(rows)


def format_dashboard_html(acc: Account, snap: dict | None = None) -> str:
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    cd = cooldown_remaining_sec()

    health = int(snap.get("health") or 0)
    pills = int(snap.get("pills") or 0)
    passive = int(snap.get("passive_available") or 0)
    work_ready = snap.get("work_ready", False)
    work_wait_ms = int(snap.get("work_wait_ms") or 0)
    af = "🟢 Açık" if snap.get("autofarm") or acc.autofarm else "⚪ Kapalı"

    steps = _next_steps(snap, acc)
    steps_block = "<b>📌 Şimdi ne yapmalı?</b>\n" + "\n".join(steps) + "\n\n"

    status_emoji = "🟢" if health >= 80 and work_ready else ("🟡" if health >= 30 else "🔴")

    prem = snap.get("premium")
    prem_bits = ""
    if prem:
        prem_bits = "⭐ Premium"
        if snap.get("premium_days_left"):
            prem_bits += f" · {int(snap['premium_days_left'])} gün"
        prem_bits += f" · Auto/work {'🟢' if snap.get('auto_work_active') else '⚪'}"
    if cfg.is_premium_hub:
        prem_bits += (" · " if prem_bits else "") + "Merkez hesap"
    af_hint = "stat+premium sync (~10 dk)" if prem else "work+stat (~10 dk)"

    work_line = "✅ hazır"
    if not work_ready and work_wait_ms > 0:
        work_line = f"⏳ {format_ms(work_wait_ms)}"
    elif not work_ready:
        work_line = "⏳ bekliyor"

    badges: list[str] = []
    qc = int(snap.get("quests_claimable") or 0)
    if qc:
        badges.append(f"📜 {qc} görev")
    if snap.get("training_ready"):
        badges.append("🏋️ antrenman")
    if int(snap.get("war_active") or 0):
        badges.append(f"⚔️ {snap['war_active']} savaş")
    if snap.get("craft_ready"):
        badges.append("💎 hap üret")
    badge_line = " · ".join(badges)
    if badge_line:
        badge_line = f"<b>Hazır:</b> {html.escape(badge_line)}\n"

    stat_q = snap.get("stat_queue_summary")
    stat_line = ""
    if stat_q and cfg.stat_auto_enabled:
        stat_line = f"⚡ Stat kuyruk: {html.escape(str(stat_q))}\n"

    err_line = ""
    if snap.get("error"):
        err_line = f"⚠️ {html.escape(str(snap['error'])[:100])}\n"

    age = snapshot_cache_age_sec(acc.name)
    age_note = ""
    if age is not None:
        age_note = f" · veri {int(age)} sn önce"
    elif snap.get("fetched_at"):
        age_note = f" · veri {int(__import__('time').time() - float(snap['fetched_at']))} sn önce"

    return (
        f"<b>{status_emoji} {html.escape(str(snap.get('username') or acc.name))}</b>"
        f" · Seviye {snap.get('level', '?')}"
        f" · {html.escape(str(snap.get('class') or '?'))}\n"
        f"📍 {html.escape(str(snap.get('province') or '?'))}"
        f" · {html.escape(str(snap.get('country') or 'Bağımsız'))}\n\n"
        f"<b>💰 Para</b>  {int(snap.get('balance') or 0):,} altın"
        f"  ·  {int(snap.get('diamonds') or 0):,} elmas\n"
        f"<b>❤️ Can</b>  {_bar(health)} {health}/100"
        f"  ·  {pills} hap\n"
        f"<b>⚡ Stat</b>  {passive} bekleyen puan\n\n"
        f"{badge_line}"
        f"{stat_line}"
        f"<b>🤖 Bot durumu</b>\n"
        f"Otomatik farm: {af} — {af_hint}\n"
        f"Görev: <b>{role_label(cfg.role)}</b> · {_work_mode_label(cfg.work_mode)}\n"
        f"Work: {work_line}\n"
        f"{html.escape(prem_bits) + chr(10) if prem_bits else ''}"
        f"{f'⏳ API bekleme: {cd}s' + chr(10) if cd > 0 else ''}"
        f"{err_line}\n"
        f"{steps_block}"
        f"<i>🕐 {datetime.now(timezone.utc).strftime('%H:%M')} UTC{age_note}</i>"
    )


def format_settings_html(acc: Account, snap: dict | None = None) -> str:
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    af = "🟢 Açık" if acc.autofarm else "⚪ Kapalı"
    return (
        f"<b>⚙️ Ayarlar — {html.escape(acc.name)}</b>\n\n"
        f"<b>Otomatik farm</b>  {af}\n"
        f"<i>{'Premium: stat + auto/work sync (~10 dk)' if snap.get('premium') else 'Her ~10 dk work + stat (~10 dk)'}</i>\n\n"
        f"<b>Fabrika modu</b>  {_work_mode_label(cfg.work_mode)}\n"
        f"<i>foreign = başka eyaletteki fabrikada çalış</i>\n\n"
        f"<b>Proxy</b>  <code>{html.escape(acc.proxy_id or 'direkt')}</code>\n"
        f"<b>Oyuncu</b>  {html.escape(str(snap.get('username') or '?'))}\n"
        f"<b>Görev rolü</b>  {role_label(cfg.role)}\n\n"
        "<i>Değiştirmek için alttaki butonları kullan</i>"
    )


def format_help_html() -> str:
    return (
        f"<b>❓ Diplomacia Bot — Kısa rehber</b> {get_version_label()}\n\n"
        "<b>En sık kullanılanlar</b>\n"
        "🏠 Ana Sayfa — özet + hızlı butonlar\n"
        "🌾 Farm Yap — fabrikada çalış (altın/elmas)\n"
        "💊 Can Doldur — hap kullan\n"
        "⚡ Statlar — farm döngüsünde altınla otomatik yükseltir\n"
        "🎁 Günlük Ödül — günlük hediyeyi al\n"
        "⚙️ Ayarlar — otomatik farm, fabrika modu\n\n"
        "<b>Yazarak da olur</b>\n"
        "<code>akıllı farm</code> · <code>planım</code> · <code>savaş</code>\n"
        "<code>savaş 2</code> hedef · <code>katkı 1</code> · <code>/setwar 2</code>\n"
        "<code>fabrika</code> · <code>fabrika kapat 1</code> · <code>ana fabrika 1</code>\n"
        "<code>statlar</code> · otomatik altın · <code>/setstat Kışla, Bilim insanı</code>\n"
        "<code>farm</code> · <code>farm merkezi</code> · elmas→hap döngüsü\n\n"
        "<b>Komutlar</b> (isteğe bağlı)\n"
        "/connect · /menu · /farm · /accounts · /settings · /help\n\n"
        "<b>İlk kez mi?</b> <code>/connect</code> ile JWT token rehberi\n\n"
        "<i>Sorun olursa panelde <b>🔄 Yenile</b> butonuna bas</i>"
    )


def format_no_ai_fallback_html() -> str:
    return (
        "<b>ℹ️ AI koç şu an kapalı</b> — sorun değil, bot tamamen butonlarla çalışır.\n\n"
        "<b>En hızlı yol:</b>\n"
        "🏠 <b>Ana Sayfa</b> — canlı özet + farm / can / stat\n"
        "🌾 <b>Farm Yap</b> — tek tık çalışma döngüsü\n"
        "⋯ <b>Daha</b> — görev, savaş, fabrika, antrenman…\n\n"
        "<b>Yazarak da olur:</b>\n"
        "<code>farm yap</code> · <code>ne durumdayım</code> · <code>planım</code>\n"
        "<code>can ne işe yarıyor</code> — yerel rehber (AI gerekmez)\n\n"
        "<i>Alttaki butonlara basman yeterli.</i>"
    )


def no_ai_fallback_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home"),
                InlineKeyboardButton("🌾 Farm", callback_data="action:farmboard"),
            ],
            [
                InlineKeyboardButton("⋯ Daha", callback_data="menu:extras"),
                InlineKeyboardButton("📋 Plan", callback_data="action:plan"),
            ],
        ]
    )


def format_extras_html() -> str:
    return (
        f"<b>⋯ Ek özellikler</b> {get_version_label()}\n\n"
        "Aşağıdaki butonlar doğrudan oyun API'sine bağlanır:\n"
        "📜 Görevler · ⚔️ Savaş · 🏋️ Antrenman · 🪖 Asker\n"
        "🏭 Fabrika · 💎 Hap üret · 🌍 Ülkeler · 🌐 Online\n"
        "🤖 Otomasyon · ⚡ Pasif stat · 📡 Ping\n\n"
        "<i>İşlem bitince 🏠 Ana Sayfa ile dönebilirsin</i>"
    )


def format_accounts_html(default_name: str, accs: list[Account] | None = None) -> str:
    accs = accs if accs is not None else list_accounts()
    if not accs:
        return (
            "<b>Hesap yok</b>\n\n"
            "Diplomacia hesabını bağlamak için <code>/connect</code> komutunu kullan.\n"
            "Token (<code>eyJ…</code>) alma rehberi orada."
        )
    lines = ["<b>👤 Hesaplarım</b>\n"]
    for a in accs:
        mark = "⭐ " if a.name == default_name else "   "
        af = "🟢" if a.autofarm else "⚪"
        lines.append(
            f"{mark}<b>{html.escape(a.name)}</b> — {html.escape(a.username or '?')}\n"
            f"      {a.last_balance:,}₺ {af} · {html.escape(a.proxy_id or 'direkt')}"
        )
    lines.append("\n<i>⭐ = şu an aktif hesap · Seçmek için butona bas</i>")
    return "\n".join(lines)


def format_fleet_html(active_name: str, accs: list[Account] | None = None) -> str:
    accs = accs if accs is not None else list_accounts()
    counts = count_by_role(accounts=accs)
    rows = fleet_rows(live=False, accounts=accs)
    lines = [
        f"<b>👥 Filo — {len(rows)} hesap</b>",
        f"🌾 {counts.get('farm', 0)} farm · ⚔️ {counts.get('war', 0)} savaş · "
        f"🔀 {counts.get('hybrid', 0)} karma · ⭐ {counts.get('hub', 0)} hub · "
        f"⏸ {counts.get('off', 0)} durdu\n",
    ]
    by_role: dict[str, list] = {r: [] for r in BOT_ROLES}
    for r in rows:
        by_role.setdefault(r.role, []).append(r)

    for role in ("war", "farm", "hybrid", "hub", "off"):
        group = by_role.get(role) or []
        if not group:
            continue
        lines.append(f"<b>{ROLE_LABELS_TR[role]}</b>")
        for r in group:
            star = "⭐ " if r.name == active_name else ""
            af = "🟢" if r.autofarm else "⚪"
            lines.append(
                f"  {star}<code>{html.escape(r.name)}</code> {html.escape(r.username)} "
                f"· {r.balance:,}₺ {af} · <code>{html.escape(r.proxy_id)}</code>"
            )
        lines.append("")
    lines.append("<i>Rol değiştir: hesaba bas · Toplu tick: alttaki butonlar</i>")
    return "\n".join(lines)


def fleet_inline_markup(active_name: str, accs: list[Account] | None = None) -> InlineKeyboardMarkup:
    accs = accs if accs is not None else list_accounts()
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("🌾 Farm tick", callback_data="fleet:tick:farm"),
            InlineKeyboardButton("⚔️ Savaş tick", callback_data="fleet:tick:war"),
            InlineKeyboardButton("🔀 Tümü", callback_data="fleet:tick:all"),
        ],
        [
            InlineKeyboardButton("🟢 Farm autofarm aç", callback_data="fleet:af:on:farm"),
            InlineKeyboardButton("⚔️ Savaş autofarm aç", callback_data="fleet:af:on:war"),
        ],
    ]
    for acc in accs[:8]:
        cfg = get_config(acc.name)
        mark = "⭐" if acc.name == active_name else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{mark}{acc.name} → {ROLE_LABELS_TR.get(normalize_role(cfg.role), '?')}",
                    callback_data=f"role:pick:{acc.name}",
                )
            ]
        )
    rows.append([back_home_button()])
    return InlineKeyboardMarkup(rows)


def role_picker_markup(account_name: str) -> InlineKeyboardMarkup:
    rows = []
    for role in ("farm", "war", "hybrid", "hub", "off"):
        rows.append(
            [
                InlineKeyboardButton(
                    ROLE_LABELS_TR[role],
                    callback_data=f"role:set:{account_name}:{role}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("« Filo", callback_data="menu:fleet")])
    return InlineKeyboardMarkup(rows)


def back_home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")


def dashboard_inline_markup(
    acc: Account,
    snap: dict | None = None,
    *,
    user_accs: list[Account] | None = None,
) -> InlineKeyboardMarkup:
    snap = snap or {}
    health = int(snap.get("health") or 0)
    passive = int(snap.get("passive_available") or 0)

    row1: list[InlineKeyboardButton] = [
        InlineKeyboardButton("🌾 Farm", callback_data="action:farmboard"),
        InlineKeyboardButton("🔄 Yenile", callback_data="dash:refresh"),
    ]
    if health < 100:
        row1.insert(1, InlineKeyboardButton("💊 Can", callback_data="action:hap"))
    stat_label = "⚡ Statlar"
    row1.append(InlineKeyboardButton(stat_label, callback_data="action:statboard"))

    rows: list[list[InlineKeyboardButton]] = [row1]
    rows.append(
        [
            InlineKeyboardButton("🎁 Günlük", callback_data="action:daily"),
            InlineKeyboardButton("📋 Plan", callback_data="action:plan"),
            InlineKeyboardButton("⋯ Daha", callback_data="menu:extras"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("👥 Filo", callback_data="menu:fleet"),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="menu:settings"),
            InlineKeyboardButton("🎮 Oyun", url="https://diplomacia.com.tr/"),
        ]
    )

    fid = snap.get("factory_id") or get_config(acc.name).preferred_factory_id
    if fid:
        rows.append(
            [InlineKeyboardButton("📋 Fabrika ID", callback_data="action:copyfactory")]
        )

    accs = user_accs if user_accs is not None else list_accounts()
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.append(switch)
    else:
        rows.append([InlineKeyboardButton("👤 Hesaplar", callback_data="menu:accounts")])

    return InlineKeyboardMarkup(rows)


def settings_inline_markup(acc: Account, *, user_accs: list[Account] | None = None) -> InlineKeyboardMarkup:
    cfg = get_config(acc.name)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                "🔴 Farmı Kapat" if acc.autofarm else "🟢 Farmı Aç",
                callback_data="toggle:autofarm",
            ),
        ],
        [
            InlineKeyboardButton(
                ROLE_LABELS_TR["farm"] + (" ✓" if normalize_role(cfg.role) == "farm" else ""),
                callback_data=f"role:set:{acc.name}:farm",
            ),
            InlineKeyboardButton(
                ROLE_LABELS_TR["war"] + (" ✓" if normalize_role(cfg.role) == "war" else ""),
                callback_data=f"role:set:{acc.name}:war",
            ),
            InlineKeyboardButton(
                ROLE_LABELS_TR["hybrid"] + (" ✓" if normalize_role(cfg.role) == "hybrid" else ""),
                callback_data=f"role:set:{acc.name}:hybrid",
            ),
        ],
        [
            InlineKeyboardButton(
                "✓ Yabancı" if cfg.work_mode == "foreign" else "Yabancı fabrika",
                callback_data="cfg:foreign",
            ),
            InlineKeyboardButton(
                "✓ Kendi" if cfg.work_mode == "own" else "Kendi fabrika",
                callback_data="cfg:own",
            ),
            InlineKeyboardButton(
                "✓ Oto" if cfg.work_mode == "auto" else "Otomatik",
                callback_data="cfg:auto",
            ),
        ],
        [back_home_button()],
    ]
    accs = user_accs if user_accs is not None else list_accounts()
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.insert(-1, switch)
    return InlineKeyboardMarkup(rows)


def accounts_inline_markup(default_name: str, accs: list[Account] | None = None) -> InlineKeyboardMarkup:
    accs = accs if accs is not None else list_accounts()
    rows: list[list[InlineKeyboardButton]] = []
    for a in accs[:6]:
        mark = "⭐ " if a.name == default_name else ""
        rows.append(
            [InlineKeyboardButton(f"{mark}{a.name}", callback_data=f"nav:account:{a.name}")]
        )
    rows.append([back_home_button()])
    return InlineKeyboardMarkup(rows)


def extras_inline_markup(snap: dict | None = None) -> InlineKeyboardMarkup:
    snap = snap or {}
    qc = snap.get("quests_claimable") or 0
    pp = snap.get("passive_available") or 0
    q_badge = f" ({qc})" if qc else ""
    p_badge = f" ({pp})" if pp else ""
    t_badge = " ✓" if snap.get("training_ready") else ""
    c_badge = " ✓" if snap.get("craft_ready") else ""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"⚡ Stat merkezi{p_badge}",
                    callback_data="action:statboard",
                ),
                InlineKeyboardButton(f"📜 Görev topla{q_badge}", callback_data="action:quests"),
            ],
            [
                InlineKeyboardButton("📋 Görev listesi", callback_data="action:questlist"),
                InlineKeyboardButton("⚔️ Savaş", callback_data="action:wars"),
            ],
            [
                InlineKeyboardButton("🗡️ Katkı ver", callback_data="action:warcontrib"),
                InlineKeyboardButton(f"🏋️ Antrenman{t_badge}", callback_data="action:training"),
            ],
            [
                InlineKeyboardButton("🪖 Asker", callback_data="action:military"),
                InlineKeyboardButton("🏭 Fabrikam", callback_data="action:myfactory"),
            ],
            [
                InlineKeyboardButton(f"💎 Hap / Farm{c_badge}", callback_data="action:farmboard"),
                InlineKeyboardButton("🌍 Ülkeler", callback_data="action:countries"),
            ],
            [
                InlineKeyboardButton("🌐 Online", callback_data="action:online"),
                InlineKeyboardButton("🤖 Otomasyon", callback_data="action:autostatus"),
            ],
            [
                InlineKeyboardButton("🧠 Akıllı farm", callback_data="action:smartfarm"),
                InlineKeyboardButton("📡 Ping", callback_data="action:ping"),
            ],
            [back_home_button()],
        ]
    )


def result_with_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[back_home_button()]])


async def setup_bot_ui(application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
