from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_war_contrib_fast_path(text: str, acc) -> "AgentResult | None":
    from .ai_agent import AgentResult
    from .account_runtime import interactive_account_context
    from .war_contribute_format import enrich_war_contribute_pack, format_war_contribute_html_enhanced
    from .war_ops import run_war_contribute

    if not re.search(
        r"\b(katkı|katkı\s*ver|savaşa\s*katk|savaşa\s*katıl|war\s*contrib)\b",
        text,
        re.I,
    ):
        return None

    def _run():
        with interactive_account_context(acc):
            return run_war_contribute(acc.token, acc.name)

    pack = enrich_war_contribute_pack(_run(), acc.name)
    return AgentResult(
        reply=format_war_contribute_html_enhanced(pack, pack.get("analysis")),
        parse_mode="HTML",
        inline_buttons=[[("⚔️ Savaş panosu", "action:wars"), ("🗡️ Katkı", "action:warcontrib")]],
    )
