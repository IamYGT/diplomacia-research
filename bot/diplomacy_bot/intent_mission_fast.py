from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .easy_mode import format_program_status, program_hub_markup

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_mission_fast_path(text: str, acc) -> "AgentResult | None":
    from .ai_agent import AgentResult
    from .account_runtime import interactive_account_context
    from .mission_store import clear_mission, enqueue_mission, get_active_mission
    from .war_commands import resolve_and_configure_war
    from .war_resolver import parse_war_reference

    tl = text.lower().strip()
    if re.search(r"\b(görev\s*iptal|mission\s*cancel|görevi\s*durdur|program\s*durdur)\b", tl):
        clear_mission(acc.name)
        return AgentResult(
            reply="🛑 Program durduruldu.\n\nTekrar başlamak için «Programı Çalıştır» butonuna bas.",
            inline_buttons=[[("▶️ Programı Çalıştır", f"easy:run:{acc.name}")]],
        )

    if re.search(r"\b(görev\s*durum|mission\s*status|aktif\s*görev|program\s*durum)\b", tl):
        rt = get_active_mission(acc.name)
        return AgentResult(
            reply=format_program_status(rt, account_name=acc.name),
            parse_mode="HTML",
            inline_buttons=[
                [("▶️ Devam Et", f"easy:run:{acc.name}")],
                [("🛑 Durdur", f"easy:stop:{acc.name}")],
            ],
        )

    start = re.search(
        r"\b(görev\s*başlat|mission\s*start|görev\s*oluştur|yeni\s*görev|program\s*başlat)\b",
        text,
        re.I,
    )
    if not start and not (parse_war_reference(text).get("url_number") and "görev" in tl):
        return None

    war_id = None
    war_label = None
    side = None
    if re.search(r"\bsaldırgan\b|\battacker\b", tl):
        side = "attacker"
    elif re.search(r"\bsavunmacı\b|\bdefender\b", tl):
        side = "defender"

    ref = parse_war_reference(text)
    if ref.get("url_number") or ref.get("text_query") or ref.get("uuid"):

        def _resolve():
            with interactive_account_context(acc):
                return resolve_and_configure_war(acc.token, acc.name, text, side=side)

        r = _resolve()
        if r.get("ambiguous"):
            return AgentResult(reply=r.get("prompt", "Birden fazla savaş bulundu — hangisi olduğunu yaz."))
        if not r.get("ok"):
            return AgentResult(reply=f"❌ {r.get('error', 'Savaş bulunamadı')}")
        war_id = r.get("war_id")
        war_label = r.get("summary")

    enqueue_mission(
        acc.name,
        target_war_id=war_id,
        contribute_side=side or "auto",
        war_label=war_label,
    )
    return AgentResult(
        reply=(
            "✅ <b>Program başlatıldı</b>\n\n"
            "Sıra: savaş → altın → antrenman\n"
            f"{war_label or 'Hedef savaş ayarlandı'}\n\n"
            "«Programı Çalıştır» ile ilk adımı başlat."
        ),
        parse_mode="HTML",
        inline_buttons=[
            [("▶️ Programı Çalıştır", f"easy:run:{acc.name}")],
            [("🛑 İptal", f"easy:stop:{acc.name}")],
        ],
    )
