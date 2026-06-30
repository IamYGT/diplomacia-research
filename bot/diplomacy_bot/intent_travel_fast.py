from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ai_agent import AgentResult


def try_travel_fast_path(text: str, acc) -> "AgentResult | None":
    from .ai_agent import AgentResult
    from .account_runtime import interactive_account_context
    from .travel_commands import format_travel_status, run_travel

    t = text.strip().lower()

    # Lokasyon sorguları — "ben neredeyim", "neredeyim", "konumum", "hangi bölge".
    # Seyahat anahtar kelimesi gerekmeden yakalanır; aksi halde bu doğal sorular
    # war fast-path tarafından "savaş referansı" sanılıp yutuluyordu.
    if re.search(
        r"nerede\s*yim|^nerede|konum|ikamet|adres|lokasyon|nerede\s*(yaşıyorum|oturuyorum)"
        r"|hangi\s*(bölge|eyalet|ülke)|bulunduğu\w*\s*(bölge|yer|eyalet|ülke)|mek[aa]n",
        t,
    ):
        def _location():
            from .game_api import get_profile
            with interactive_account_context(acc):
                prof = get_profile(acc.token)
                status = format_travel_status(acc.token)
            province = prof.province_name or "?"
            country = prof.country_name or "?"
            on_move = "yolda" in status.lower() or "→" in status
            travel_line = f"\n🚶 {status}" if on_move else ""
            return (
                f"📍 <b>{province}</b> · {country}\n"
                f"🗺️ {prof.username} · Seviye {prof.level}{travel_line}"
            )

        return AgentResult(reply=_location(), parse_mode="HTML")

    # Gate: seyahat/travel/eyalet anahtar kelimesi VEYA "git" kelimesi (herhangi bir
    # konumda — "X'e git", "git X", "X eyaletine git" hepsini kapsar).
    if not re.search(r"seyahat|travel|\beyalet\b|\bgit\b|gitmek", t):
        return None

    if re.search(r"seyahat\s*durum|travel\s*status|neredeyim", t):
        def _status():
            with interactive_account_context(acc):
                return format_travel_status(acc.token)

        return AgentResult(reply=_status())

    if re.search(r"seyahat\s*iptal|travel\s*cancel", t):
        def _cancel():
            with interactive_account_context(acc):
                return run_travel(acc.token, "iptal")

        r = _cancel()
        return AgentResult(reply="✅ Seyahat iptal edildi" if r.get("ok") else f"❌ {r.get('error', 'iptal başarısız')}")

    raw = text.strip()
    dest: str | None = None
    # 1) Emir kipi: "git X" / "seyahat X" / "travel X" / "seyahat et X"
    m = re.search(r"(?:seyahat(?:\s+et)?|git|travel)\s+(?:to\s+)?(.+)$", raw, re.I)
    if m:
        dest = m.group(1)
    # 2) Türkçe doğal sıra: "X'e git", "X'a git", "X'ye git", "X eyaletine git",
    #    "X eyaletine". Yönelme ekini ('ya/'ye/'a/'e) soyup eyalet adını al.
    if dest is None:
        m2 = re.search(r"^(.+?)(?:\s+eyaletine)?\s*(?:eyaletine)?\s*git(?:mek(?:\s+\w+)*)?\s*$", raw, re.I)
        if m2:
            cand = m2.group(1).strip()
            cand = re.sub(r"['']\s*[yea]{1,2}$", "", cand).strip()  # "Kaliforniya'ya" → "Kaliforniya"
            if cand.lower().endswith(" eyaletine"):
                cand = cand[: -len(" eyaletine")].strip()
            dest = cand
    # 3) Saf "...eyaletine" / "...eyaletine git" kalıbı
    if dest is None:
        m3 = re.search(r"^(.+?)\s*(?:eyaletine|eyaletine\s*git)\s*$", raw, re.I)
        if m3:
            dest = m3.group(1)
    if not dest or len(dest) < 2:
        return None
    dest = dest.strip("«»\"'")

    def _go():
        with interactive_account_context(acc):
            return run_travel(acc.token, dest)

    r = _go()
    if r.get("message"):
        return AgentResult(reply=r["message"])
    if r.get("ambiguous"):
        return AgentResult(reply=f"❌ {r.get('error')}")
    if r.get("skipped") == "already_there":
        return AgentResult(reply=f"✅ Zaten hedeftesin: {r.get('province')}")
    if r.get("traveling"):
        mins = max(0, int(r.get("remaining_ms") or 0) // 60_000)
        return AgentResult(
            reply=f"🚶 Seyahat başladı → {r.get('destination')}\n⏳ ~{mins} dk"
        )
    if r.get("ok"):
        return AgentResult(reply=f"🚶 Seyahat başlatıldı → {dest}")
    return AgentResult(reply=f"❌ {r.get('error', 'seyahat başarısız')}")
