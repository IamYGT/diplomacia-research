from __future__ import annotations

import html
from typing import Any

from .user_errors import format_ms
from .war_resolver import format_war_sides


def enrich_war_contribute_pack(pack: dict[str, Any], account_name: str) -> dict[str, Any]:
    """war_ops çıktısını feature_reports / callbacks ile uyumlu hale getirir."""
    if pack.get("analysis"):
        return pack
    from .account_config import get_config
    from .war_board import analyze_wars_enriched

    cfg = get_config(account_name)
    war = pack.get("war") or {}
    numbered = []
    if war:
        numbered.append(
            {
                "id": war.get("id"),
                "index": war.get("index"),
                "display_title": war.get("name") or war.get("war_name"),
                "my_side": pack.get("side"),
            }
        )
    pack["analysis"] = analyze_wars_enriched(
        {"wars": [war]} if war else {},
        cfg,
        player_country=None,
    )
    if numbered and not pack["analysis"].get("numbered"):
        pack["analysis"]["numbered"] = numbered
    inner = pack.setdefault("result", {})
    if pack.get("side"):
        inner["side"] = pack["side"]
    if war.get("index") is not None:
        inner["war_index"] = war.get("index")
    return pack


def _prep_lines(prep: list[dict]) -> str:
    bits: list[str] = []
    for item in prep:
        if not isinstance(item, dict):
            continue
        if item.get("use_pills", {}).get("ok"):
            bits.append("💊 hap kullanıldı")
        mil = item.get("military") or {}
        if mil.get("ok"):
            bits.append("🪖 asker hazırlandı")
        elif mil.get("trained"):
            bits.append("🏋️ asker eğitildi")
    return " · ".join(bits)


def format_war_contribute_html_enhanced(result: dict, analysis: dict | None = None) -> str:
    """war_ops + legacy game_features çıktıları için birleşik HTML."""
    if result.get("skipped") == "war_cooldown":
        ms = int(result.get("cooldown_ms") or 0)
        return f"⏳ <b>Savaş katkısı beklemede</b>\n{format_ms(ms)} sonra tekrar dene."
    if result.get("skipped") == "traveling":
        ms = int(result.get("remaining_ms") or 0)
        return f"🚶 <b>Seyahat halindesin</b>\nVarınca katkı ver — kalan: {format_ms(ms)}."
    if result.get("skipped") == "no_target_war":
        return "⚔️ Hedef savaş yok — önce savaş linki veya «sırbistan savaşı» ile hedef seç."
    if result.get("skipped") == "no_active_war":
        return "⚔️ Aktif savaş yok — önce ülke savaşı bekle."

    if result.get("ok"):
        war = result.get("war") or {}
        sides = format_war_sides(war) if war else ""
        side = result.get("side") or (result.get("result") or {}).get("side", "?")
        side_tr = "Saldırgan" if side == "attacker" else ("Savunmacı" if side == "defender" else str(side))
        idx = (result.get("result") or {}).get("war_index")
        war_tag = f" #{idx}" if idx else ""
        d = (result.get("result") or {}).get("data") or {}
        if isinstance(result.get("result"), dict) and result["result"].get("data"):
            d = result["result"]["data"]
        msg = html.escape(str(d.get("message") or "Katkı gönderildi"))
        dmg = d.get("damage") or d.get("contribution")
        extra = f"\nKatkı: {dmg}" if dmg is not None else ""
        troops = d.get("troops_sent") or d.get("units_sent")
        if troops is not None:
            extra += f"\nAsker: {troops}"
        prep = _prep_lines(result.get("prep") or [])
        prep_block = f"\n<i>{html.escape(prep)}</i>" if prep else ""
        war_block = f"\n{sides}" if sides else ""
        return (
            f"<b>⚔️ Savaşa katkı{war_tag}</b> — {html.escape(side_tr)} ✅\n"
            f"{msg}{extra}{prep_block}{war_block}"
        )

    if result.get("skipped"):
        sk = html.escape(str(result["skipped"]))
        err = result.get("error")
        tail = f"\n{html.escape(str(err))}" if err else ""
        return f"⚔️ Katkı atlandı: <code>{sk}</code>{tail}"

    err = html.escape(str(result.get("error") or result)[:240])
    return f"⚔️ Savaş katkısı başarısız\n{err}"


def patch_war_contribute_shims() -> None:
    """game_features.run_war_contribute + feature_reports.format_war_contribute_html."""
    from . import feature_reports, game_features
    from .war_ops import run_war_contribute as war_ops_contribute

    if getattr(game_features, "_war_ops_shim_installed", False):
        return

    _orig = game_features.run_war_contribute

    def run_war_contribute_shim(
        token: str, account_name: str, *, war_id: str | None = None
    ) -> dict:
        pack = war_ops_contribute(token, account_name, war_id=war_id)
        return enrich_war_contribute_pack(pack, account_name)

    game_features.run_war_contribute = run_war_contribute_shim  # type: ignore[assignment]
    game_features._war_ops_shim_installed = True
    game_features._run_war_contribute_legacy = _orig

    feature_reports.format_war_contribute_html = format_war_contribute_html_enhanced  # type: ignore[assignment]
    feature_reports._format_war_contribute_html_legacy = getattr(
        feature_reports, "format_war_contribute_html", None
    )
