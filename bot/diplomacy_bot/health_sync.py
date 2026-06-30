"""Can/hap — profile öncelikli (auto/status ile uyumsuzluk giderimi)."""

from __future__ import annotations

from typing import Any, Callable

ApiFn = Callable[..., tuple[int, Any]]


def work_health(token: str, *, _api: ApiFn | None = None, auto_status: dict | None = None) -> int:
    """Farm/savaş hazırlığı — /players/profile health (work gate gerçeği)."""
    from .game_api import get_profile

    try:
        return int(get_profile(token).health or 0)
    except Exception:
        status = auto_status
        if status is None:
            from .modules.economy import get_auto_status

            api = _api
            if api is None:
                from .game_api import api as default_api

                api = default_api
            status = get_auto_status(token, _api=api) or {}
        return int(status.get("health") or 0)


def analyze_auto_with_profile(
    token: str,
    status: dict | None = None,
    *,
    _api: ApiFn | None = None,
) -> dict[str, Any]:
    """Auto/status analizi — can için profile öncelikli tek giriş noktası."""
    from .feature_analysis import analyze_auto_status

    if status is None:
        from .modules.economy import get_auto_status

        api = _api
        if api is None:
            from .game_api import api as default_api

            api = default_api
        status = get_auto_status(token, _api=api) or {}
    profile_h = work_health(token, _api=_api, auto_status=status)
    return analyze_auto_status(status, profile_health=profile_h)


def health_dashboard_banner(snap: dict) -> str:
    """Can 0 + hap varken üst uyarı satırı."""
    health = snap_health(snap)
    pills = int(snap.get("pills") or 0)
    pill_cd = int(snap.get("pill_cooldown_ms") or 0)
    if pills <= 0 or health >= 100:
        return ""
    if health == 0:
        if pill_cd > 0:
            from .user_errors import format_ms

            return f"🚨 <b>Can 0</b> · hap bekleme {format_ms(pill_cd)} — sonra 💊 Can Doldur"
        return (
            f"🚨 <b>Can 0 — farm durdu</b> · {pills:,} hap hazır\n"
            "<i>💊 Can Doldur veya <code>hap kullan</code> yaz</i>"
        )
    if pill_cd > 0:
        return ""
    return f"💊 Can {health}/100 · farm öncesi <b>Can Doldur</b> önerilir"


def snap_health(snap: dict) -> int:
    """Snapshot can — 0 geçerli, eksik → 0."""
    h = snap.get("health")
    return int(h) if h is not None else 0


def premium_auto_work_note(snap: dict) -> str:
    """Premium sunucu farm rozeti + düşük can uyarısı."""
    if not snap.get("premium"):
        return ""
    if snap.get("auto_work_active"):
        health = snap_health(snap)
        line = "⭐ <b>Premium auto-work aktif</b> — sunucu farm yapıyor"
        if health < 100:
            pill_cd = int(snap.get("pill_cooldown_ms") or 0)
            if pill_cd > 0:
                from .user_errors import format_ms

                line += f"\n<i>Can {health}/100 · hap CD {format_ms(pill_cd)} — manuel farm beklemede</i>"
            else:
                line += f"\n<i>Can {health}/100 — <code>hap kullan</code> önerilir</i>"
        return line
    return "⭐ Premium — auto/work kapalı; eyalette olduğundan emin ol"


def install_health_sync_hooks() -> None:
    """Dashboard üst uyarısı — telegram_ui dosya limiti bypass."""
    from . import telegram_ui as ui

    if getattr(ui, "_health_sync_installed", False):
        return

    _orig = ui.format_dashboard_html
    _orig_steps = ui._next_steps

    def _next_steps_premium_health(snap, acc):
        steps = _orig_steps(snap, acc)
        if not (snap.get("premium") and snap.get("auto_work_active")):
            return steps
        health = snap_health(snap)
        if health >= 100:
            return steps
        steps = [
            s
            for s in steps
            if "Premium auto/work" not in s and "akıllı farm gerekmez" not in s
        ]
        pill_cd = int(snap.get("pill_cooldown_ms") or 0)
        if pill_cd > 0:
            from .user_errors import format_ms

            steps.insert(0, f"1️⃣ Can {health}/100 — hap CD {format_ms(pill_cd)}, sonra 💊 Can Doldur")
        else:
            steps.insert(0, f"1️⃣ Can {health}/100 → <b>💊 Can Doldur</b>")
        steps.insert(1, "⭐ Sunucu auto-work açık — manuel farm gerekmez")
        return steps[:3]

    ui._next_steps = _next_steps_premium_health  # type: ignore[assignment]

    def format_dashboard_html_with_health(acc, snap=None):
        body = _orig(acc, snap)
        if snap is None:
            from .dynamic_context import snapshot_account

            snap = snapshot_account(acc)
        prefix_parts: list[str] = []
        banner = health_dashboard_banner(snap)
        if banner and banner not in body:
            prefix_parts.append(banner)
        prem = premium_auto_work_note(snap)
        if prem and prem not in body:
            prefix_parts.append(prem)
        if prefix_parts:
            return "\n\n".join(prefix_parts) + "\n\n" + body
        return body

    ui.format_dashboard_html = format_dashboard_html_with_health  # type: ignore[assignment]
    ui._health_sync_installed = True
    from .game_features_health import install_game_features_health_patch

    install_game_features_health_patch()
