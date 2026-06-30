from __future__ import annotations

from typing import TYPE_CHECKING

from .easy_mode import format_program_status, format_help_easy_html, matches_easy_phrase

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_easy_fast_path(text: str, acc) -> "AgentResult | None":
    from .ai_agent import AgentResult
    from .account_runtime import interactive_account_context
    from .mission_store import clear_mission, enqueue_mission, get_active_mission
    from .modules.mission_executor import run_mission_step
    from .war_contribute_format import enrich_war_contribute_pack, format_war_contribute_html_enhanced
    from .war_ops import run_war_contribute

    if matches_easy_phrase(
        text,
        [
            r"program\s*(durdur|iptal|bitir)",
            r"görev\s*(durdur|iptal)",
            r"dur\s*program",
        ],
    ):
        clear_mission(acc.name)
        return AgentResult(
            reply="🛑 Program durduruldu.\n\nTekrar başlamak için «Programı Çalıştır» de.",
            inline_buttons=[[("▶️ Programı Çalıştır", f"easy:run:{acc.name}")]],
        )

    if matches_easy_phrase(
        text,
        [
            r"program\s*(çalış|calis|başlat|baslat|devam)",
            r"günlük\s*program",
            r"programı\s*çalış",
            r"^devam\s*et$",
            r"^başla$",
        ],
    ):
        rt = get_active_mission(acc.name)
        if not rt:
            enqueue_mission(acc.name)
            rt = get_active_mission(acc.name)
        with interactive_account_context(acc):
            step = run_mission_step(acc.token, rt)
        from .easy_mode import format_program_step_message

        status = format_program_status(get_active_mission(acc.name), account_name=acc.name)
        head = format_program_step_message(step)
        return AgentResult(
            reply=f"{head}\n\n{status}",
            parse_mode="HTML",
            inline_buttons=[
                [("▶️ Devam Et", f"easy:run:{acc.name}")],
                [("🛑 Durdur", f"easy:stop:{acc.name}")],
            ],
        )

    if matches_easy_phrase(
        text,
        [
            r"savaşa\s*vur",
            r"savaş\s*yap",
            r"savaşa\s*katıl",
            r"^katkı\s*ver$",
        ],
    ):
        with interactive_account_context(acc):
            pack = enrich_war_contribute_pack(run_war_contribute(acc.token, acc.name), acc.name)
        return AgentResult(
            reply=format_war_contribute_html_enhanced(pack, pack.get("analysis")),
            parse_mode="HTML",
            inline_buttons=[
                [("⚔️ Tekrar Vur", f"easy:war:{acc.name}")],
                [("🏠 Ana Sayfa", "dash:home")],
            ],
        )

    if matches_easy_phrase(text, [r"kolay\s*menü", r"kolay\s*kullanım"]):
        return AgentResult(
            reply=format_help_easy_html(),
            parse_mode="HTML",
            inline_buttons=[[("📋 Program Menüsü", f"easy:hub:{acc.name}")]],
        )

    return None
