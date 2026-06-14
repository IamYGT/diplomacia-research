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

# Alt menü kısayolları — on_text bunları yakalar
MENU_LABELS: dict[str, str] = {
    "📊 durum": "ne durumdayım",
    "🌾 akıllı farm": "akıllı farm",
    "💊 hap kullan": "hap kullan",
    "⚡ stat harca": "stat harca",
    "📋 planım": "planım",
    "🎁 günlük": "günlük",
    "🤖 hesaplar": "tüm hesaplar",
    "❓ yardım": "yardım",
}

BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Başlat ve klavye"),
    BotCommand("dashboard", "Canlı kontrol paneli"),
    BotCommand("status", "Hızlı özet"),
    BotCommand("farm", "Farm döngüsü"),
    BotCommand("plan", "24s bot planı"),
    BotCommand("accounts", "Hesap listesi"),
    BotCommand("autofarm", "Otomatik farm aç/kapat"),
    BotCommand("play", "AI komut (doğal dil)"),
    BotCommand("version", "Sürüm bilgisi"),
    BotCommand("help", "Tüm komutlar"),
]


def normalize_menu_text(text: str) -> str | None:
    key = text.strip().lower()
    return MENU_LABELS.get(key)


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Durum"), KeyboardButton("🌾 Akıllı Farm"), KeyboardButton("💊 Hap kullan")],
            [KeyboardButton("⚡ Stat harca"), KeyboardButton("📋 Planım"), KeyboardButton("🎁 Günlük")],
            [KeyboardButton("🤖 Hesaplar"), KeyboardButton("❓ Yardım")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Farm, plan, koç sorusu…",
    )


def _bar(pct: int, width: int = 10) -> str:
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    return "█" * filled + "░" * (width - filled)


def format_dashboard_html(acc: Account, snap: dict | None = None) -> str:
    snap = snap or snapshot_account(acc)
    cfg = get_config(acc.name)
    cd = cooldown_remaining_sec()
    cd_line = f"⏳ API cooldown: <b>{cd}s</b>" if cd > 0 else "✅ API hazır"

    health = int(snap.get("health") or 0)
    pills = int(snap.get("pills") or 0)
    passive = int(snap.get("passive_available") or 0)
    work_ready = snap.get("work_ready", False)
    premium = "⭐" if snap.get("premium") else "—"
    af = "🟢 ON" if snap.get("autofarm") or acc.autofarm else "⚪ OFF"

    alerts: list[str] = []
    if health < 100 and pills > 0:
        alerts.append("💊 Can düşük — hap kullan")
    if passive > 0:
        alerts.append(f"⚡ {passive} pasif stat bekliyor")
    if not work_ready:
        alerts.append("⏱ Work cooldown aktif")
    if snap.get("error"):
        alerts.append(f"⚠️ {html.escape(str(snap['error'])[:80])}")

    alert_block = ""
    if alerts:
        alert_block = "<b>⚠️ Aksiyon</b>\n" + "\n".join(f"• {html.escape(a)}" for a in alerts) + "\n\n"

    factory = snap.get("factory_id") or cfg.preferred_factory_id or "—"
    if factory != "—" and len(str(factory)) > 12:
        factory_short = f"{str(factory)[:8]}…"
    else:
        factory_short = str(factory)

    return (
        f"<b>🎮 Diplomacia Panel {get_version_label()}</b>\n"
        f"<b>{html.escape(str(snap.get('username') or acc.name))}</b> "
        f"· lv{snap.get('level', '?')} · {html.escape(str(snap.get('class') or '?'))}\n"
        f"📍 {html.escape(str(snap.get('province') or '?'))} · {html.escape(str(snap.get('country') or 'bağımsız'))}\n\n"
        f"<b>💰 Ekonomi</b>\n"
        f"Altın: <code>{int(snap.get('balance') or 0):,}</code> · "
        f"Elmas: <code>{int(snap.get('diamonds') or 0):,}</code>\n\n"
        f"<b>❤️ Can</b> {_bar(health)} <code>{health}/100</code> · hap <code>{pills}</code>\n\n"
        f"<b>⚙️ Bot</b>\n"
        f"Autofarm {af} · mod <code>{cfg.work_mode}</code> · hub {'evet' if cfg.is_premium_hub else 'hayır'}\n"
        f"Premium {premium} · proxy <code>{html.escape(acc.proxy_id or 'direct')}</code>\n"
        f"Work: {'✅ hazır' if work_ready else '⏳ bekle'} · "
        f"Training atk: {'✅' if snap.get('free_attack') else '—'}\n"
        f"Fabrika: <code>{html.escape(factory_short)}</code>\n"
        f"{cd_line}\n\n"
        f"{alert_block}"
        f"<i>Güncelle: butonlar veya /dashboard</i>"
    )


def dashboard_inline_markup(acc: Account, snap: dict | None = None) -> InlineKeyboardMarkup:
    snap = snap or snapshot_account(acc)
    health = int(snap.get("health") or 0)
    passive = int(snap.get("passive_available") or 0)
    rows: list[list[InlineKeyboardButton]] = []

    row1: list[InlineKeyboardButton] = [
        InlineKeyboardButton("🌾 Akıllı Farm", callback_data="action:smartfarm"),
    ]
    if health < 100:
        row1.append(InlineKeyboardButton("💊 Hap", callback_data="action:hap"))
    if passive > 0:
        row1.append(InlineKeyboardButton(f"⚡ Stat ({passive})", callback_data="action:stat"))
    rows.append(row1)

    rows.append(
        [
            InlineKeyboardButton("📋 Plan", callback_data="action:status"),
            InlineKeyboardButton("🎁 Günlük", callback_data="action:daily"),
            InlineKeyboardButton(
                "Autofarm OFF" if acc.autofarm else "Autofarm ON",
                callback_data="toggle:autofarm",
            ),
        ]
    )

    rows.append(
        [
            InlineKeyboardButton("🌍 Foreign mod", callback_data="cfg:foreign"),
            InlineKeyboardButton("🔄 Yenile", callback_data="dash:refresh"),
            InlineKeyboardButton("🎮 Oyun", url="https://diplomacia.com.tr/"),
        ]
    )

    fid = snap.get("factory_id") or get_config(acc.name).preferred_factory_id
    if fid:
        rows.append(
            [
                InlineKeyboardButton(
                    "📋 Fabrika ID kopyala",
                    copy_text=CopyTextButton(text=str(fid)),
                ),
            ]
        )

    accs = list_accounts()
    if len(accs) > 1:
        switch_row = []
        for a in accs[:4]:
            mark = "⭐ " if a.name == acc.name else ""
            switch_row.append(
                InlineKeyboardButton(f"{mark}{a.name}", callback_data=f"nav:account:{a.name}")
            )
        rows.append(switch_row)

    return InlineKeyboardMarkup(rows)


async def setup_bot_ui(application) -> None:
    """post_init: komut menüsü + menu button (Bot API best practice)."""
    await application.bot.set_my_commands(BOT_COMMANDS)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
