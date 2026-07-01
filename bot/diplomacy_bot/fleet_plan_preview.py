"""Fleet plan preview — telegram: show natural-language fleet target safely."""

from __future__ import annotations

import html

from telegram import Update
from telegram.ext import ContextTypes

from .domain.fleet_missions import FleetMissionTarget, build_region_phase_dicts
from .fleet_region_mission_ui import format_phase_plan
from .fleet_start_planner import FleetStartPlan, resolve_fleet_start_plan
from .fleet_ui_markup import fleet_nav_inline_markup
from .telegram_helpers import user_required


def format_fleet_plan_preview_html(plan: FleetStartPlan) -> str:
    target = FleetMissionTarget(province=plan.province, **plan.opts)
    phases = [str(row.get("phase") or "") for row in build_region_phase_dicts(target)]
    source = "DeepSeek planı" if plan.source == "deepseek" else "Klasik parser"
    if plan.warnings:
        source = "Parser fallback"
    lines = [
        "<b>🧭 Filo hedef önizleme</b>",
        f"📍 Bölge: <b>{html.escape(plan.province)}</b>",
        f"🧠 Kaynak: {html.escape(source)}",
    ]
    if plan.opts.get("vote"):
        lines.append("🗳 Oy: ülke seçimi")
    if plan.opts.get("province_vote"):
        lines.append("🏛 Eyalet oyu: açık")
    if plan.opts.get("independent_citizenship"):
        lines.append("🪪 Bağımsız vatandaşlık: açık")
    if cid := str(plan.opts.get("citizenship_country_id") or ""):
        lines.append(f"🪪 Vatandaşlık ülke: <code>{html.escape(cid)}</code>")
    if vid := str(plan.opts.get("visa_country_id") or ""):
        lines.append(f"📋 Vize ülke: <code>{html.escape(vid)}</code>")
    if phase_text := format_phase_plan(phases):
        lines.append(f"\n🧩 Plan: {html.escape(phase_text)}")
    command_args = _command_args(plan)
    lines.append("\n<b>Uygula</b>")
    lines.append(f"<code>/fleetstart {html.escape(command_args)}</code>")
    lines.append(f"<code>/fleetregion {html.escape(command_args)}</code>")
    lines.append("\n<i>Bu sadece önizleme; işlem başlatmaz.</i>")
    return "\n".join(lines)


def _command_args(plan: FleetStartPlan) -> str:
    parts = [plan.province]
    if plan.opts.get("vote"):
        parts.append("vote")
    if plan.opts.get("province_vote"):
        parts.append("eyaletoy")
    if plan.opts.get("independent_citizenship"):
        parts.append("independent")
    if cid := str(plan.opts.get("citizenship_country_id") or ""):
        parts.append(f"citizen:{cid}")
    if vid := str(plan.opts.get("visa_country_id") or ""):
        parts.append(f"visa:{vid}")
    if cand := str(plan.opts.get("candidate_id") or ""):
        parts.append(f"candidate:{cand}")
    return " ".join(parts)


@user_required
async def cmd_fleetplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from . import telegram_app as ta

    uid = ta._uid(update)
    msg = update.effective_message
    if not msg:
        return
    plan = resolve_fleet_start_plan(uid, list(context.args or []))
    await msg.reply_text(
        format_fleet_plan_preview_html(plan),
        parse_mode="HTML",
        reply_markup=fleet_nav_inline_markup(),
    )
