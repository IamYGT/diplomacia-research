from __future__ import annotations

import html
from typing import TYPE_CHECKING

from telegram import (
    BotCommand,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
)

from .account_config import get_config
from .dynamic_context import snapshot_account
from .stealth_client import cooldown_remaining_sec
from .store import Account, list_accounts
from .version import get_version_label

if TYPE_CHECKING:
    pass

# Alt klavye → intent_router / doğrudan handler anahtarı
MENU_LABELS: dict[str, str] = {
    "🏠 ana sayfa": "dashboard",
    "🌾 farm yap": "akıllı farm",
    "💊 can doldur": "hap kullan",
    "⚡ stat harca": "stat harca",
    "🎁 günlük ödül": "günlük",
    "⚙️ ayarlar": "ayarlar",
    "❓ yardım": "yardım",
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
    BotCommand("menu", "Kontrol paneli"),
    BotCommand("farm", "Tek farm döngüsü"),
    BotCommand("accounts", "Hesaplarım"),
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
            [KeyboardButton("💊 Can Doldur"), KeyboardButton("⚡ Stat Harca"), KeyboardButton("🎁 Günlük Ödül")],
            [KeyboardButton("⚙️ Ayarlar"), KeyboardButton("❓ Yardım")],
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
        steps.append(f"{'2️⃣' if steps else '1️⃣'} {passive} pasif puan birikti → <b>⚡ Stat Harca</b>")
    if snap.get("work_ready"):
        n = len(steps) + 1
        steps.append(f"{n}️⃣ Fabrika hazır → <b>🌾 Farm Yap</b>")
    elif not steps:
        steps.append("1️⃣ Work bekleniyor — biraz sonra <b>🌾 Farm Yap</b>")
    if not acc.autofarm:
        steps.append("💡 Otomatik farm kapalı — <b>⚙️ Ayarlar</b>dan açabilirsin")
    return steps[:3]


def format_welcome_html(uid: int, account_name: str, *, gemini_ok: bool) -> str:
    ai = "🧠 AI koç hazır" if gemini_ok else "ℹ️ AI kapalı — butonlar yeterli"
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


def format_dashboard_html(acc: Account, snap: dict | None = None) -> str:
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    cd = cooldown_remaining_sec()

    health = int(snap.get("health") or 0)
    pills = int(snap.get("pills") or 0)
    passive = int(snap.get("passive_available") or 0)
    work_ready = snap.get("work_ready", False)
    af = "🟢 Açık" if snap.get("autofarm") or acc.autofarm else "⚪ Kapalı"

    steps = _next_steps(snap, acc)
    steps_block = "<b>📌 Şimdi ne yapmalı?</b>\n" + "\n".join(steps) + "\n\n"

    status_emoji = "🟢" if health >= 80 and work_ready else ("🟡" if health >= 30 else "🔴")

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
        f"<b>🤖 Bot durumu</b>\n"
        f"Otomatik farm: {af}\n"
        f"Fabrika: {_work_mode_label(cfg.work_mode)}"
        f" · Work: {'✅ hazır' if work_ready else '⏳ bekliyor'}\n"
        f"{'⭐ Premium' if snap.get('premium') else ''}"
        f"{f' · Merkez hesap' if cfg.is_premium_hub else ''}\n"
        f"{f'⏳ API bekleme: {cd}s' if cd > 0 else ''}\n\n"
        f"{steps_block}"
        f"<i>🔄 Yenile butonu ile güncelle · {get_version_label()}</i>"
    )


def format_settings_html(acc: Account, snap: dict | None = None) -> str:
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    af = "🟢 Açık" if acc.autofarm else "⚪ Kapalı"
    return (
        f"<b>⚙️ Ayarlar — {html.escape(acc.name)}</b>\n\n"
        f"<b>Otomatik farm</b>  {af}\n"
        f"<i>Her ~10 dk otomatik çalışır</i>\n\n"
        f"<b>Fabrika modu</b>  {_work_mode_label(cfg.work_mode)}\n"
        f"<i>foreign = başka eyaletteki fabrikada çalış</i>\n\n"
        f"<b>Proxy</b>  <code>{html.escape(acc.proxy_id or 'direkt')}</code>\n"
        f"<b>Oyuncu</b>  {html.escape(str(snap.get('username') or '?'))}\n\n"
        "<i>Değiştirmek için alttaki butonları kullan</i>"
    )


def format_help_html() -> str:
    return (
        f"<b>❓ Diplomacia Bot — Kısa rehber</b> {get_version_label()}\n\n"
        "<b>En sık kullanılanlar</b>\n"
        "🏠 Ana Sayfa — özet + hızlı butonlar\n"
        "🌾 Farm Yap — fabrikada çalış (altın/elmas)\n"
        "💊 Can Doldur — hap kullan\n"
        "⚡ Stat Harca — biriken pasif puanları harca\n"
        "🎁 Günlük Ödül — günlük hediyeyi al\n"
        "⚙️ Ayarlar — otomatik farm, fabrika modu\n\n"
        "<b>Yazarak da olur</b>\n"
        "<code>akıllı farm</code> · <code>planım</code> · <code>hesaplar</code>\n\n"
        "<b>Komutlar</b> (isteğe bağlı)\n"
        "/menu · /farm · /accounts · /settings · /help\n\n"
        "<i>Sorun olursa /start ile sıfırla</i>"
    )


def format_accounts_html(default_name: str) -> str:
    accs = list_accounts()
    if not accs:
        return "<b>Hesap yok</b>\n\nHesap eklemek için geliştiriciyle iletişime geç."
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


def back_home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton("🏠 Ana Sayfa", callback_data="dash:home")


def dashboard_inline_markup(acc: Account, snap: dict | None = None) -> InlineKeyboardMarkup:
    snap = snap or snapshot_account(acc)
    health = int(snap.get("health") or 0)
    passive = int(snap.get("passive_available") or 0)

    row1: list[InlineKeyboardButton] = [
        InlineKeyboardButton("🌾 Farm", callback_data="action:smartfarm"),
        InlineKeyboardButton("🔄 Yenile", callback_data="dash:refresh"),
    ]
    if health < 100:
        row1.insert(1, InlineKeyboardButton("💊 Can", callback_data="action:hap"))
    if passive > 0:
        row1.append(InlineKeyboardButton(f"⚡ Stat ({passive})", callback_data="action:stat"))

    rows: list[list[InlineKeyboardButton]] = [row1]
    rows.append(
        [
            InlineKeyboardButton("🎁 Günlük", callback_data="action:daily"),
            InlineKeyboardButton("📋 Plan", callback_data="action:plan"),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="menu:settings"),
        ]
    )
    rows.append([InlineKeyboardButton("🎮 Oyunu Aç", url="https://diplomacia.com.tr/")])

    fid = snap.get("factory_id") or get_config(acc.name).preferred_factory_id
    if fid:
        rows.append(
            [InlineKeyboardButton("📋 Fabrika ID", copy_text=CopyTextButton(text=str(fid)))]
        )

    accs = list_accounts()
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.append(switch)
    else:
        rows.append([InlineKeyboardButton("👤 Hesaplar", callback_data="menu:accounts")])

    return InlineKeyboardMarkup(rows)


def settings_inline_markup(acc: Account) -> InlineKeyboardMarkup:
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
    accs = list_accounts()
    if len(accs) > 1:
        switch = []
        for a in accs[:4]:
            label = f"⭐{a.name}" if a.name == acc.name else a.name
            switch.append(InlineKeyboardButton(label, callback_data=f"nav:account:{a.name}"))
        rows.insert(-1, switch)
    return InlineKeyboardMarkup(rows)


def accounts_inline_markup(default_name: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for a in list_accounts()[:6]:
        mark = "⭐ " if a.name == default_name else ""
        rows.append(
            [InlineKeyboardButton(f"{mark}{a.name}", callback_data=f"nav:account:{a.name}")]
        )
    rows.append([back_home_button()])
    return InlineKeyboardMarkup(rows)


def result_with_home_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[back_home_button()]])


async def setup_bot_ui(application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
