from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_war_reference_fast_path(text: str, acc) -> "AgentResult | None":
    """War URL veya 'sırbistan savaşı' gibi metin → hedef savaş ayarla."""
    from .ai_agent import AgentResult
    from .account_config import update_config_field
    from .account_runtime import interactive_account_context
    from .war_commands import resolve_and_configure_war
    from .war_resolver import parse_war_reference

    side = None
    tl = text.lower()
    if re.search(r"\bsaldırgan\b|\battacker\b", tl):
        side = "attacker"
    elif re.search(r"\bsavunmacı\b|\bdefender\b", tl):
        side = "defender"

    ref = parse_war_reference(text)
    has_ref = bool(ref.get("url_number") or ref.get("text_query") or ref.get("uuid"))
    if not has_ref and side is None:
        return None
    # Saf serbest metin (URL/UUID/sayı değil) ancak savaş anahtar kelimesi içermiyorsa
    # savaş referansı değildir — "ben neredeyim" gibi doğal sorular yutuluyordu.
    # Gerçek savaş ref'leri ya URL/UUID/sayı taşır ya da "savaş/war/katkı/hedef/ceph" içerir.
    if (
        ref.get("text_query")
        and not ref.get("url_number")
        and not ref.get("uuid")
        and side is None
        and not re.search(r"savaş|war|katkı|hedef|ceph", text, re.I)
    ):
        return None

    if side and not has_ref:
        update_config_field(acc.name, contribute_side=side)
        return AgentResult(
            reply=f"✅ Savaş tarafı: **{'Saldırgan' if side == 'attacker' else 'Savunmacı'}** ({side})",
            inline_buttons=[[("⚔️ Savaş panosu", "action:wars"), ("🗡️ Katkı", "action:warcontrib")]],
        )

    def _setwar():
        with interactive_account_context(acc):
            return resolve_and_configure_war(acc.token, acc.name, text, side=side)

    r = _setwar()
    if r.get("ambiguous"):
        return AgentResult(reply=r.get("prompt", "Birden fazla savaş eşleşti."))
    if not r.get("ok"):
        return AgentResult(reply=f"❌ {r.get('error', 'savaş bulunamadı')}")
    side_hint = ""
    if r.get("needs_side_choice"):
        side_hint = (
            "\n\nHangi tarafa katılacaksın?\n"
            "• `saldırgan` veya `savunmacı` yaz\n"
            "• veya alttaki butonları kullan"
        )
    return AgentResult(
        reply=f"✅ Hedef savaş ayarlandı\n\n{r.get('summary')}{side_hint}",
        inline_buttons=[
            [("🔴 Saldırgan", "war:side:attacker"), ("🔵 Savunmacı", "war:side:defender")],
            [("⚔️ Savaş panosu", "action:wars"), ("🗡️ Katkı", "action:warcontrib")],
        ],
    )
