"""Autofarm Telegram bildirimleri — zengin HTML, token hatası ayrı."""

from __future__ import annotations

import html
import os
import time

from .account_config import get_config, role_label
from .modules.orchestrator import TickResult
from .store import Account
from .token_recovery import is_token_auth_error

_INTERVAL = int(os.environ.get("AUTOFARM_INTERVAL_SEC", "620"))
_RECOVERY_COOLDOWN = float(os.environ.get("TOKEN_RECOVERY_NOTIFY_COOLDOWN_SEC", "3600"))
_last_recovery_sent: dict[str, float] = {}


def tick_is_token_error(r: TickResult) -> bool:
    return is_token_auth_error(r.error or "")


def should_send_recovery_for_account(account_name: str) -> bool:
    now = time.time()
    last = _last_recovery_sent.get(account_name, 0.0)
    if now - last < _RECOVERY_COOLDOWN:
        return False
    _last_recovery_sent[account_name] = now
    return True


def reset_recovery_cooldown(account_name: str) -> None:
    _last_recovery_sent.pop(account_name.strip().lower(), None)


def _action_labels(r: TickResult) -> list[str]:
    labels: list[str] = []
    for action in r.actions or []:
        if not isinstance(action, dict):
            continue
        if action.get("war"):
            labels.append("⚔️ savaş")
        if action.get("training"):
            labels.append("🏋️ antrenman")
        if action.get("economy") or action.get("economy_pre"):
            labels.append("💊 hap")
        if action.get("passive_stats") or action.get("passive_stats_post"):
            labels.append("⚡ stat")
        if action.get("stat_upgrades") or action.get("stat_upgrades_post"):
            labels.append("📈 yükseltme")
        if action.get("premium"):
            labels.append("⭐ premium")
        if action.get("skipped"):
            sk = action["skipped"]
            if sk == "premium_auto_work":
                h = action.get("health")
                if h is not None and int(h) < 100:
                    cd = int(action.get("pill_cooldown_ms") or 0)
                    if cd > 0:
                        from .user_errors import format_ms

                        labels.append(f"⏭ premium · can {h}/100 · hap CD {format_ms(cd)}")
                    else:
                        labels.append(f"⏭ premium · can {h}/100 — hap gerek")
                else:
                    labels.append("⏭ premium farm (sunucu)")
            else:
                labels.append("⏭ premium farm")
        if action.get("use_pills_pre"):
            pre = action["use_pills_pre"]
            if isinstance(pre, dict) and pre.get("ok"):
                labels.append("💊 can dolduruldu")
            else:
                labels.append("💊 can")
        if action.get("travel"):
            labels.append("🚶 seyahat")
        rd = action.get("routine_daily")
        if isinstance(rd, dict) and rd.get("claimed"):
            labels.append("🎁 günlük")
        rq = action.get("routine_quests")
        if isinstance(rq, dict) and rq.get("claimed_count"):
            labels.append(f"📜 {rq['claimed_count']} görev")
    if r.earned_money > 0 and "🌾 farm" not in labels:
        labels.append("🌾 farm")
    return labels


def format_autofarm_success_html(acc: Account, r: TickResult) -> str:
    cfg = get_config(acc.name)
    tag = role_label(cfg.role)
    user = html.escape(r.username or acc.username or acc.name)
    mins = max(1, _INTERVAL // 60)
    lines = [
        f"<b>🤖 Otomatik tur</b> · {html.escape(acc.name)} · {tag}",
        f"👤 {user}",
    ]
    if r.earned_money > 0 or r.earned_xp or r.earned_diamonds:
        bits = []
        if r.earned_money > 0:
            bits.append(f"+{r.earned_money:,}₺")
        if r.earned_xp:
            bits.append(f"+{r.earned_xp} XP")
        if r.earned_diamonds:
            bits.append(f"+{r.earned_diamonds}💎")
        lines.append(f"✅ <b>{' · '.join(bits)}</b>")
    acts = _action_labels(r)
    if acts:
        lines.append("📋 " + " · ".join(dict.fromkeys(acts)))
    for action in r.actions or []:
        if not isinstance(action, dict) or action.get("skipped") != "premium_auto_work":
            continue
        h = action.get("health")
        if h is None or int(h) >= 100:
            break
        cd = int(action.get("pill_cooldown_ms") or 0)
        if cd > 0:
            from .user_errors import format_ms

            lines.append(
                f"<i>ℹ️ Premium auto-work açık; can {h}/100 · hap bekleme {format_ms(cd)}</i>"
            )
        else:
            lines.append(
                f"<i>ℹ️ Premium auto-work açık; can {h}/100 — <code>hap kullan</code> önerilir</i>"
            )
        break
    if r.balance_after:
        lines.append(f"💰 Bakiye: <b>{r.balance_after:,}₺</b>")
    if r.error and r.ok:
        lines.append(f"<i>ℹ️ {html.escape(str(r.error)[:80])}</i>")
    lines.append(f"<i>Sonraki tur ~{mins} dk · /kolay ile program</i>")
    return "\n".join(lines)


def format_autofarm_wait_html(acc: Account, r: TickResult) -> str | None:
    """Seyahat / cooldown — kısa bilgi, spam yok."""
    err = (r.error or "").strip()
    if not err or tick_is_token_error(r):
        return None
    low = err.lower()
    if r.error and str(r.error).startswith(("⏳", "❤️", "💊", "🏭", "🧳")):
        return (
            f"<b>⏳ {html.escape(acc.name)}</b> — {html.escape(err)}\n"
            f"<i>Otomatik tur bekliyor</i>"
        )
    if "seyahat" in low or "travel" in low:
        return (
            f"<b>🚶 {html.escape(acc.name)}</b> — yoldasın\n"
            f"<i>Varınca otomatik devam eder</i>"
        )
    if "cooldown" in low or "bekle" in low:
        return (
            f"<b>⏳ {html.escape(acc.name)}</b> — {html.escape(err[:100])}\n"
            f"<i>Limit bitince tekrar dener</i>"
        )
    if r.ok or r.earned_money > 0:
        return None
    if not r.actions and not err:
        return None
    if "iş yok" in low or err == "paused":
        return None
    return (
        f"<b>ℹ️ {html.escape(acc.name)}</b> — {html.escape(err[:100])}\n"
        f"<i>Detay için Ana Sayfa</i>"
    )


def format_autofarm_message(acc: Account, r: TickResult) -> str | None:
    if tick_is_token_error(r):
        return None
    if r.error == "paused":
        return None
    if r.ok or r.earned_money > 0 or (r.actions and not r.error):
        return format_autofarm_success_html(acc, r)
    return format_autofarm_wait_html(acc, r)


def format_autofarm_token_recovery_intro(acc: Account) -> str:
    user = html.escape(acc.username or acc.name)
    return (
        f"<b>🔑 Oturum kapandı — {html.escape(acc.name)}</b>\n"
        f"👤 {user}\n\n"
        "Otomatik farm <b>duraklatıldı</b> (token yenilenene kadar).\n\n"
        "Aşağıdaki adımları izle — token'ı bu sohbete yapıştırman yeterli."
    )
