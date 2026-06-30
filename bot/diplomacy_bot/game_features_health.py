"""game_features can senkronu — dosya limiti bypass (runtime patch)."""

from __future__ import annotations


def install_game_features_health_patch() -> None:
    from . import game_features as gf

    if getattr(gf, "_health_auto_patched", False):
        return

    from .feature_analysis import build_readiness
    from .health_sync import analyze_auto_with_profile
    from .modules import economy

    def fetch_auto_status(token: str) -> dict:
        status = economy.get_auto_status(token) or {}
        return {
            "ok": bool(status),
            "status": status,
            "analysis": analyze_auto_with_profile(token, status),
        }

    _orig_extras = gf.fetch_extras_readiness

    def fetch_extras_readiness(token: str, account_name: str) -> dict:
        result = _orig_extras(token, account_name)
        try:
            aa = analyze_auto_with_profile(token)
            result = dict(result)
            result["auto"] = aa
            result["readiness"] = build_readiness(
                quests_analysis=result.get("quests"),
                auto_analysis=aa,
                wars_analysis=result.get("wars"),
                passive_analysis=result.get("passive"),
                craft_analysis=result.get("craft"),
                training_analysis=result.get("training"),
            )
        except Exception:
            pass
        return result

    gf.fetch_auto_status = fetch_auto_status
    gf.fetch_extras_readiness = fetch_extras_readiness
    gf._health_auto_patched = True
