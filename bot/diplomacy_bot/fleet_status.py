"""Filo durum özeti — kapasite, sonraki adım, detay tablo."""

from __future__ import annotations

from .account_balance import resolve_display_balance
from .account_config import get_config
from .account_main import get_main_account_name
from .auth import scoped_list_accounts
from .game_api import api as game_api
from .store import get_account


def _factory_id_from_dict(f: dict) -> str:
    return str(f.get("id") or f.get("factory_id") or "")


def _fetch_factory_worker_stats(token: str, factory_id: str) -> dict:
    fid = factory_id.strip()
    for path in ("/factories/my", "/factories/region"):
        st, data = game_api("GET", path, token, delay=0.15)
        if st != 200 or not isinstance(data, dict):
            continue
        factories = data.get("factories") or data.get("data") or []
        if isinstance(factories, dict):
            factories = list(factories.values())
        for f in factories:
            if not isinstance(f, dict) or _factory_id_from_dict(f) != fid:
                continue
            workers = int(f.get("worker_count") or f.get("workers") or 0)
            cap = f.get("max_workers") or f.get("capacity") or f.get("worker_limit")
            try:
                cap_i = int(cap) if cap is not None else None
            except (TypeError, ValueError):
                cap_i = None
            return {"workers": workers, "capacity": cap_i, "name": str(f.get("name") or "")}
    return {}


def count_fleet_on_factory(telegram_user_id: int, factory_id: str) -> int:
    fid = factory_id.strip()
    if not fid:
        return 0
    return sum(
        1
        for acc in scoped_list_accounts(telegram_user_id)
        if (get_config(acc.name).preferred_factory_id or "").strip() == fid
    )


def compute_fleet_next_steps(telegram_user_id: int) -> list[str]:
    from .fleet_command import resolve_operator_factory
    from .token_watch import list_inbox_import_candidates

    accs = scoped_list_accounts(telegram_user_id)
    if not accs:
        return ["Token yapıştır veya <code>/fleetinbox</code>"]
    steps: list[str] = []
    fid, _, err = resolve_operator_factory(telegram_user_id)
    if err or not fid:
        steps.append("Ana hesapta fabrika panelinden 🎯 ana fabrika işaretle")
    inbox_pending = len(list_inbox_import_candidates(telegram_user_id))
    if inbox_pending:
        steps.append(f"<code>/fleetinbox</code> — {inbox_pending} token bekliyor")
    if sum(1 for a in accs if not a.autofarm) > len(accs) // 2:
        steps.append("<code>/fleetbootstrap hybrid</code>")
    if fid and any(
        get_config(a.name).work_mode != "fixed"
        or (get_config(a.name).preferred_factory_id or "") != fid
        for a in accs
    ):
        steps.append("<code>/fleetfactory main</code>")
    elif fid and not _main_residence_ok(telegram_user_id):
        steps.append("<code>/fleetaod</code> — ikamet + tam kurulum")
    elif fid and _main_residence_ok(telegram_user_id):
        steps.append("<code>/fleetvote</code> — aktif seçime oy ver")
    return steps[:4]


def format_post_aod_footer() -> str:
    """AOD kurulum sonrası kısa rehber."""
    return (
        "<b>Sonraki adım:</b>\n"
        "→ <code>/fleetvote</code> — seçim varsa oy ver\n"
        "→ <code>/fleet status</code> — filo doğrulama"
    )


def _main_residence_ok(telegram_user_id: int, target: str = "Hürmüz") -> bool:
    main = get_main_account_name(telegram_user_id)
    if not main or not (acc := get_account(main)):
        return False
    try:
        from .account_runtime import account_context
        from .fleet_residence import get_residence_info

        with account_context(acc):
            info = get_residence_info(acc.token)
        cur = (info.get("residence_province") or info.get("province") or "").strip().lower()
        return cur == target.strip().lower()
    except Exception:
        return False


def format_next_steps_footer(telegram_user_id: int) -> str:
    steps = compute_fleet_next_steps(telegram_user_id)
    if not steps:
        return ""
    return "<b>Sonraki adım:</b>\n" + "\n".join(f"→ {s}" for s in steps)


def format_factory_capacity_line(telegram_user_id: int, factory_id: str) -> str:
    import html

    main = get_main_account_name(telegram_user_id)
    if not main or not (acc := get_account(main)):
        return ""
    stats = _fetch_factory_worker_stats(acc.token, factory_id)
    if not stats:
        return ""
    assigned = count_fleet_on_factory(telegram_user_id, factory_id)
    workers = int(stats.get("workers") or 0)
    cap = stats.get("capacity")
    parts = [f"👷 Fabrika: {workers} çalışan"]
    if cap:
        parts.append(f"kapasite ~{cap}")
    parts.append(f"· filoda {assigned} hesap bağlı")
    line = " · ".join(parts)
    if cap and assigned > cap:
        return f"🔴 {html.escape(line)} — <b>kapasite aşımı</b>"
    if assigned > workers + 2:
        return f"🟡 {html.escape(line)} — kayıtlı çalışandan fazla işçi"
    return f"🟢 {html.escape(line)}"


def _mission_label(account_name: str) -> str:
    try:
        from .mission_store import get_active_mission

        rt = get_active_mission(account_name)
        if not rt:
            return ""
        if rt.phase_index >= len(rt.plan.phases):
            phase = "done"
        else:
            phase = rt.plan.phases[rt.phase_index].phase.value
        status = rt.phase_status.value
        return f"{phase}:{status}"
    except Exception:
        return ""


def format_fleet_ops_status(telegram_user_id: int, *, detailed: bool = True) -> str:
    import html

    from .config import MAX_ACCOUNTS_PER_USER
    from .fleet_command import resolve_operator_factory

    accs = scoped_list_accounts(telegram_user_id)
    if not accs:
        return (
            "👥 Henüz hesap yok.\n\n"
            "<i>Token yapıştır veya <code>data/token_inbox/u{uid}_01.jwt</code> + "
            "<code>/fleetinbox</code></i>"
        )
    fid, prov, err = resolve_operator_factory(telegram_user_id)
    af_on = sum(1 for a in accs if a.autofarm)
    roles: dict[str, int] = {}
    for a in accs:
        r = get_config(a.name).role
        roles[r] = roles.get(r, 0) + 1
    role_bits = " · ".join(f"{html.escape(k)}:{v}" for k, v in sorted(roles.items()))
    head = [
        f"<b>👥 Filo komuta — {len(accs)}/{MAX_ACCOUNTS_PER_USER} hesap</b>",
        f"🟢 autofarm: {af_on}/{len(accs)} · {role_bits}",
    ]
    if fid:
        head.append(f"🏭 Operatör fabrika: <code>{html.escape(fid[:12])}…</code>")
        if prov:
            head.append(f"📍 Eyalet: <b>{html.escape(prov)}</b>")
        if cap_line := format_factory_capacity_line(telegram_user_id, fid):
            head.append(cap_line)
    elif err:
        head.append(f"⚠️ {html.escape(err)}")
    from .fleet_metrics import format_fleet_metrics_line

    if metrics := format_fleet_metrics_line(telegram_user_id):
        head.append(metrics)
    head.append("")
    if detailed:
        head.append("<b>Hesap</b>  af  rol  mod  fabrika  bakiye  mission")
        for acc in accs[:20]:
            cfg = get_config(acc.name)
            af = "🟢" if acc.autofarm else "⚪"
            pref = (cfg.preferred_factory_id or "")[:6]
            fab = f"{pref}…" if pref else "—"
            bal = resolve_display_balance(acc).format()
            mission = _mission_label(acc.name) or "—"
            head.append(
                f"{af} <code>{html.escape(acc.name)}</code> "
                f"{html.escape(cfg.role[:4])} {html.escape(cfg.work_mode[:5])} "
                f"{html.escape(fab)} {bal} {html.escape(mission)}"
            )
    else:
        for acc in accs[:15]:
            cfg = get_config(acc.name)
            af = "🟢" if acc.autofarm else "⚪"
            pref = (cfg.preferred_factory_id or "")[:8]
            head.append(
                f"{af} <code>{html.escape(acc.name)}</code> · {html.escape(cfg.role)} · "
                f"{html.escape(cfg.work_mode)}" + (f" `{html.escape(pref)}…`" if pref else "")
            )
    if len(accs) > 20:
        head.append(f"<i>… +{len(accs) - 20} hesap</i>")
    if footer := format_next_steps_footer(telegram_user_id):
        head.append(f"\n{footer}")
    head.append(
        "\n<i>/fleetaod · /fleetinbox · /fleetfactory main · /fleetresidence Hürmüz</i>"
    )
    return "\n".join(head)
