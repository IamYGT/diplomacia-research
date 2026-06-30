from __future__ import annotations

"""Kullanıcıya gösterilecek aksiyon hata / cooldown mesajları."""


def format_ms(ms: int | float | None) -> str:
    if not ms or int(ms) <= 0:
        return "biraz"
    sec = int(ms) // 1000
    if sec < 60:
        return f"~{sec} sn"
    mins = sec // 60
    rem = sec % 60
    if rem:
        return f"~{mins} dk {rem} sn"
    return f"~{mins} dk"


def format_pill_error(data: dict | None = None, *, exc: str | None = None) -> str:
    data = data or {}
    msg = str(data.get("error") or data.get("message") or exc or "").lower()
    remaining = int(data.get("remaining_ms") or data.get("pill_cooldown_ms") or 0)
    if remaining > 0 or "bekleme" in msg or "cooldown" in msg:
        return f"⏳ Hap cooldown — {format_ms(remaining)} sonra tekrar dene."
    if "yok" in msg or "stok" in msg:
        return "💊 Hap yok. Elmas craft veya marketten al."
    if exc:
        return f"💊 Hap kullanılamadı: {exc[:120]}"
    return "💊 Hap kullanılamadı. Panelde 🔄 Yenile ile durumu güncelle."


def format_work_error(error: str | None = None, *, cooldown_ms: int | None = None) -> str:
    if cooldown_ms and int(cooldown_ms) > 0:
        return f"⏳ Fabrika work cooldown — {format_ms(cooldown_ms)} sonra tekrar dene."
    err = (error or "").lower()
    if "cooldown" in err or "bekleme" in err:
        return f"⏳ Work beklemede — {format_ms(cooldown_ms)} sonra dene."
    if "seyahat" in err or "travel" in err:
        return "🧳 Seyahat halindesin — varınca tekrar dene."
    if "can" in err or "health" in err or "sağlık" in err:
        return "❤️ Can düşük — önce 💊 Can Doldur."
    if "fabrika" in err or "join" in err:
        return f"🏭 Fabrika hatası: {error[:160]}"
    return error or "🌾 Farm başarısız. Panelde 🔄 Yenile ile tekrar dene."


def format_hap_preflight(snap: dict) -> str | None:
    from .health_sync import snap_health

    health = snap_health(snap)
    pills = int(snap.get("pills") or snap.get("health_pills") or 0)
    pill_cd = int(snap.get("pill_cooldown_ms") or 0)
    if health >= 100:
        return "❤️ Can zaten dolu (100/100)."
    if pills <= 0:
        return "💊 Hap yok — elmas craft veya önce farm ile kazan."
    if pill_cd > 0:
        return f"⏳ Hap cooldown — {format_ms(pill_cd)} sonra tekrar dene."
    return None


def format_farm_preflight(snap: dict) -> str | None:
    from .health_sync import snap_health

    work_wait = int(snap.get("work_wait_ms") or 0)
    if work_wait > 0:
        return f"⏳ Work cooldown — {format_ms(work_wait)} sonra tekrar dene."
    health = snap_health(snap)
    if health <= 0:
        pills = int(snap.get("pills") or 0)
        pill_cd = int(snap.get("pill_cooldown_ms") or 0)
        if pills <= 0:
            return "❤️ Can 0 ve hap yok — önce hap craft veya bekle."
        if pill_cd > 0:
            return f"❤️ Can 0 — hap cooldown {format_ms(pill_cd)}, sonra 💊 Can Doldur."
        return "❤️ Can 0 — önce 💊 Can Doldur, sonra farm."
    return None


def format_stat_preflight(snap: dict) -> str | None:
    passive = int(snap.get("passive_available") or 0)
    if passive <= 0:
        return "⚡ Harcanacak pasif stat puanı yok."
    return None


def format_quest_claim_preflight(snap: dict) -> str | None:
    claimable = int(snap.get("quests_claimable") or 0)
    if claimable <= 0:
        return "📜 Toplanabilir görev ödülü yok — önce görevleri tamamla (farm/savaş)."
    return None


def format_training_preflight(snap: dict) -> str | None:
    if not snap.get("training_enabled", True):
        return "🏋️ Antrenman kapalı — farm/war/hybrid rolünde açılır."
    if not snap.get("free_attack", snap.get("free_attack_available")):
        ms = int(snap.get("free_attack_cooldown_ms") or snap.get("attack_ms") or 0)
        if ms > 0:
            return f"⏳ Antrenman saldırısı — {format_ms(ms)} sonra."
        return "🏋️ Ücretsiz antrenman saldırısı hazır değil."
    return None


def format_war_contrib_preflight(snap: dict, cfg=None) -> str | None:
    from .account_config import get_config, normalize_role

    if cfg is None and snap.get("account_name"):
        cfg = get_config(str(snap["account_name"]))
    role = normalize_role(getattr(cfg, "role", None) if cfg else snap.get("role"))
    if role not in ("war", "hybrid"):
        return "⚔️ Savaş katkısı için war veya hybrid rolü seç."
    if not int(snap.get("war_active") or 0):
        return "⚔️ Ülkenin aktif savaşı yok."
    return None


def format_craft_preflight(snap: dict, cfg=None) -> str | None:
    from .account_config import get_config

    if cfg is None and snap.get("account_name"):
        cfg = get_config(str(snap["account_name"]))
    cfg = cfg or get_config("ygt")
    diamonds = int(snap.get("diamonds") or 0)
    pills = int(snap.get("pills") or 0)
    if diamonds <= 0:
        return "💎 Elmas yok — farm ile kazan veya premium."
    if pills >= cfg.min_pill_stock and diamonds < cfg.craft_diamond_batch:
        return f"💊 Hap stoğu yeterli ({pills}) — craft şart değil."
    return None


def format_daily_preflight(snap: dict) -> str | None:
    if snap.get("daily_claimed"):
        return "🎁 Günlük ödül bugün zaten alınmış."
    return None
