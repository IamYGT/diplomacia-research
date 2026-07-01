"""Yeni hesap — tüm otomatik özellikler varsayılan açık."""

from __future__ import annotations

import logging

from .account_config import get_config, save_config

log = logging.getLogger(__name__)

# Kullanıcı kapatmadığı sürece yeni kayıtta açık gelir
AUTO_FEATURE_FIELDS = (
    "auto_token_refresh",
    "auto_daily_claim",
    "auto_quest_claim",
    "auto_like_articles",
    "stat_auto_enabled",
    "training_enabled",
    "craft_pills_when_low",
    "auto_travel_enabled",
)


def apply_auto_defaults_for_new_account(account_name: str) -> None:
    """İlk bağlantıda autofarm + config bayraklarını aç."""
    from .store import set_autofarm

    name = account_name.strip().lower()
    set_autofarm(name, True)
    cfg = get_config(name)
    for field in AUTO_FEATURE_FIELDS:
        if hasattr(cfg, field):
            setattr(cfg, field, True)
    save_config(cfg)
    log.info("auto_defaults applied acc=%s fields=%s autofarm=on", name, AUTO_FEATURE_FIELDS)


def auto_features_summary() -> str:
    """Kullanıcıya gösterilecek kısa özet."""
    return (
        "🤖 <b>Otomatik özellikler açık:</b> farm, günlük/görev, token yenileme, "
        "gazete beğeni, stat, antrenman, hap üretimi, seyahat.\n"
        "<i>Kapatmak için ayarlar veya /tokenauto off, /autofarm off</i>"
    )
