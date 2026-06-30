from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

ApiFn = Any

_WAR_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?diplomacia\.com\.tr/wars/war/(\d+)",
    re.I,
)
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def parse_war_reference(text: str) -> dict[str, str | None]:
    """URL, UUID veya serbest metinden savaş referansı çıkar."""
    raw = (text or "").strip()
    out: dict[str, str | None] = {
        "raw": raw or None,
        "url_number": None,
        "uuid": None,
        "text_query": None,
    }
    if not raw:
        return out

    m = _WAR_URL_RE.search(raw)
    if m:
        out["url_number"] = m.group(1)
        return out

    um = _UUID_RE.search(raw)
    if um:
        out["uuid"] = um.group(0)
        return out

    if raw.isdigit():
        out["url_number"] = raw
        return out

    out["text_query"] = raw
    return out


def _war_matches_number(war: dict, number: str) -> bool:
    n = str(number)
    for key in ("number", "war_number", "display_number", "seq", "index"):
        if str(war.get(key) or "") == n:
            return True
    wid = str(war.get("id") or "")
    if wid.startswith(n):
        return True
    return False


def _war_matches_text(war: dict, query: str) -> bool:
    q = _fold(query)
    if not q:
        return False
    blob = " ".join(
        str(war.get(k) or "")
        for k in (
            "war_name",
            "attacker_name",
            "defender_name",
            "attacker_province",
            "defender_province",
            "attacker_country",
            "defender_country",
        )
    )
    return q in _fold(blob)


def _collect_wars(lists: list[list[dict]]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for wars in lists:
        for w in wars:
            wid = str(w.get("id") or "")
            if not wid or wid in seen:
                continue
            seen.add(wid)
            out.append(w)
    return out


def format_war_sides(war: dict, *, index: int | None = None) -> str:
    """Telegram onay metni — saldırgan/savunmacı kim."""
    atk = war.get("attacker_name") or war.get("attacker_province") or "?"
    defn = war.get("defender_name") or war.get("defender_province") or "?"
    prov_a = war.get("attacker_province") or "?"
    prov_d = war.get("defender_province") or "?"
    prefix = f"#{index} " if index else ""
    name = war.get("war_name") or ""
    title = f"{prefix}{name}".strip() or f"{prefix}Savaş"
    return (
        f"{title}\n"
        f"🔴 Saldırgan: {atk} (📍 {prov_a})\n"
        f"🔵 Savunmacı: {defn} (📍 {prov_d})"
    )


def format_side_choice_prompt(war: dict) -> str:
    sides = format_war_sides(war)
    return (
        f"{sides}\n\n"
        "Hangi tarafa katkı vereceksin?\n"
        "• Saldırgan (attacker)\n"
        "• Savunmacı (defender)"
    )


def resolve_war_from_reference(
    wars: list[dict],
    ref: dict[str, str | None],
) -> dict | None:
    if not wars:
        return None

    uid = ref.get("uuid")
    if uid:
        for w in wars:
            if str(w.get("id") or "").lower() == uid.lower():
                return w

    num = ref.get("url_number")
    if num:
        for w in wars:
            if _war_matches_number(w, num):
                return w

    query = ref.get("text_query")
    if query:
        matches = [w for w in wars if _war_matches_text(w, query)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return {"_ambiguous": True, "matches": matches, "query": query}

    return None


def fetch_all_wars(token: str, *, _api: Callable[..., tuple[int, Any]]) -> list[dict]:
    """GET /wars + /wars/my-country birleşik liste."""
    lists: list[list[dict]] = []
    for path in ("/wars", "/wars/my-country"):
        st, data = _api("GET", path, token, delay=0.25)
        if st == 200 and isinstance(data, dict):
            lists.append(data.get("wars") or [])
    return _collect_wars(lists)


def resolve_war(
    token: str,
    text: str,
    *,
    _api: Callable[..., tuple[int, Any]],
) -> dict[str, Any]:
    """Metin/URL → savaş kaydı + taraf seçim ipuçları."""
    ref = parse_war_reference(text)
    wars = fetch_all_wars(token, _api=_api)
    war = resolve_war_from_reference(wars, ref)
    if war is None:
        return {
            "ok": False,
            "error": "savaş bulunamadı",
            "ref": ref,
            "war_count": len(wars),
        }
    if war.get("_ambiguous"):
        matches = war.get("matches") or []
        lines = [format_war_sides(w, index=i + 1) for i, w in enumerate(matches[:5])]
        return {
            "ok": False,
            "ambiguous": True,
            "matches": matches,
            "prompt": "Birden fazla eşleşme:\n\n" + "\n\n".join(lines),
            "ref": ref,
        }
    return {
        "ok": True,
        "war": war,
        "war_id": str(war.get("id")),
        "sides_prompt": format_side_choice_prompt(war),
        "ref": ref,
    }
