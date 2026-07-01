"""Fleet region mission Telegram helpers."""

from __future__ import annotations

from .fleet_residence import DEFAULT_RESIDENCE_PROVINCE


_PHASE_LABELS = {
    "assign_config": "hazırla",
    "travel_to_province": "seyahat",
    "residence_set": "ikamet",
    "citizenship_apply": "vatandaşlık",
    "independent_citizenship": "bağımsız vatandaşlık",
    "visa_apply": "vize",
    "election_vote": "oy",
    "farm_tick": "farm",
}


def format_phase_plan(phases: list[str] | tuple[str, ...]) -> str:
    labels = [_PHASE_LABELS.get(str(p), str(p)) for p in phases if str(p)]
    return " → ".join(labels)


def _empty_autopilot_hint(result) -> str:
    if getattr(result.repair, "total", 0) or getattr(result.mission.batch, "total", 0):
        return ""
    inbox = getattr(result, "inbox", None)
    if not inbox or getattr(inbox, "ok", 0):
        return ""
    uid = int(getattr(result, "telegram_user_id", 0) or 0)
    name = f"u{uid}_01.jwt" if uid else "u<telegram_id>_01.jwt"
    return (
        "🟡 Henüz worker yok.\n"
        f"Token dosyasını <code>data/token_inbox/{name}</code> olarak bırak "
        "ve tekrar <b>▶️ Başlat</b>."
    )


def parse_region_args(args: list[str]) -> tuple[str, dict]:
    province_parts: list[str] = []
    opts = {
        "vote": False,
        "province_vote": False,
        "candidate_id": "",
        "citizenship_country_id": "",
        "independent_citizenship": False,
        "visa_country_id": "",
    }
    pending: str | None = None
    for raw in args:
        arg = raw.strip()
        low = arg.lower()
        if pending:
            opts[pending] = arg
            pending = None
            continue
        if low in ("vote", "oy"):
            opts["vote"] = True
            continue
        if low in ("provincevote", "province_vote", "eyaletoy", "eyalet-oy"):
            opts["province_vote"] = True
            continue
        if low in ("independent", "independence", "bagimsiz", "bağımsız"):
            opts["independent_citizenship"] = True
            continue
        if low in ("candidate", "aday"):
            pending = "candidate_id"
            opts["vote"] = True
            continue
        if low in ("citizen", "citizenship", "vatandas", "vatandaş"):
            pending = "citizenship_country_id"
            continue
        if low in ("visa", "vize"):
            pending = "visa_country_id"
            continue
        if ":" in arg:
            key, value = arg.split(":", 1)
            k = key.lower()
            if k in ("candidate", "aday"):
                opts["candidate_id"] = value
                opts["vote"] = True
                continue
            if k in ("citizen", "citizenship", "vatandas", "vatandaş"):
                opts["citizenship_country_id"] = value
                continue
            if k in ("visa", "vize"):
                opts["visa_country_id"] = value
                continue
        province_parts.append(arg)
    return (" ".join(province_parts) or DEFAULT_RESIDENCE_PROVINCE), opts


def format_region_mission_html(result, province: str) -> str:
    import html

    lines = [
        f"<b>🧭 Filo bölge mission</b> → <b>{html.escape(province)}</b>",
        f"<code>{html.escape(result.fleet_id)}</code>",
        f"{result.batch.ok}/{result.batch.total} hesap kalıcı plana alındı\n",
    ]
    if plan := format_phase_plan(getattr(result, "phases", [])):
        lines.append(f"🧩 Plan: {html.escape(plan)}\n")
    for warning in getattr(result, "warnings", [])[:3]:
        lines.append(f"⚠️ {html.escape(str(warning))}")
    for r in result.batch.results[:20]:
        icon = "✅" if r.ok else "❌"
        lines.append(f"{icon} <code>{html.escape(r.account_name)}</code> — {html.escape(r.message)}")
    lines.append("\n<i>Worker listedeki plan fazlarını kaldığı yerden sürdürecek.</i>")
    lines.append("\n<code>/fleet status</code> ile mission fazlarını izle.")
    return "\n".join(lines)


def format_autopilot_html(result) -> str:
    import html

    inbox_line = f"📥 Inbox: {result.inbox.ok}/{result.inbox.total} import"
    if result.inbox.total == 1 and result.inbox.results and not result.inbox.results[0].ok:
        if "boş" in result.inbox.results[0].message.lower():
            inbox_line = "📥 Inbox: yeni token yok"
    lines = [
        f"<b>▶️ Filo autopilot</b> → <b>{html.escape(result.province)}</b>",
        inbox_line,
        f"🛠 Otonomi: {result.repair.ok}/{result.repair.total} hesap hazır",
        f"🧭 Mission: {result.mission.batch.ok}/{result.mission.batch.total} hesap kuyruğa alındı",
        f"<code>{html.escape(result.mission.fleet_id)}</code>\n",
    ]
    if plan := format_phase_plan(getattr(result.mission, "phases", [])):
        lines.append(f"🧩 Plan: {html.escape(plan)}\n")
    for warning in getattr(result.mission, "warnings", [])[:3]:
        lines.append(f"⚠️ {html.escape(str(warning))}")
    empty_hint = _empty_autopilot_hint(result)
    if empty_hint:
        lines.append(empty_hint)
    if empty_hint:
        lines.append("\n<code>/fleet status</code> ile hesaplar bağlanınca izle.")
        return "\n".join(lines)
    for row in result.mission.batch.results[:20]:
        icon = "✅" if row.ok else "❌"
        lines.append(f"{icon} <code>{html.escape(row.account_name)}</code> — {html.escape(row.message)}")
    lines.append("\n<i>Worker artık plan fazlarını, farm, stat, hap ve antrenmanı sürdürecek.</i>")
    lines.append("\n<code>/fleet status</code> ile izle · <code>/fleet audit</code> ile eksik kontrol et.")
    return "\n".join(lines)
