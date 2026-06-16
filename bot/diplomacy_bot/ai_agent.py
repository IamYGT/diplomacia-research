from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from . import game_api
from .catalog import catalog_for_prompt, load_mechanics
from .config import GEMINI_API_KEY
from .game_coach import answer_teach_full, is_teach_question
from .gemini_client import generate_json
from .intent_router import try_fast_path
from .response_format import format_step_results
from .game_client import call
from .safety import action_summary, classify_action, sanitize_path
from .store import get_account, list_accounts
from .dynamic_context import build_ai_context
from .version import get_version_label

log = logging.getLogger(__name__)

PLAN_JSON_SCHEMA = """
{
  "reply_tr": "kullanıcıya Türkçe özet/plan",
  "account": "varsayılan hesap adı (örn ercan2)",
  "steps": [
    {
      "method": "GET|POST",
      "path": "/players/profile",
      "body": {} veya null,
      "path_params": {"id": "uuid"},
      "query": {"page": "1"},
      "why": "kısa sebep"
    }
  ],
  "needs_confirmation": false
}
"""


@dataclass
class AgentResult:
    reply: str
    steps_run: list[dict] = field(default_factory=list)
    needs_confirmation: bool = False
    pending_actions: list[dict] = field(default_factory=list)
    inline_buttons: list[list[tuple[str, str]]] | None = None
    parse_mode: str | None = "Markdown"


def _accounts_context(telegram_user_id: int | None = None) -> str:
    from .auth import scoped_list_accounts

    if telegram_user_id:
        accounts = scoped_list_accounts(telegram_user_id)
    else:
        accounts = list_accounts()
    lines = []
    for a in accounts:
        try:
            p = game_api.get_profile(a.token)
            lines.append(
                f"- {a.name}: player_id={p.player_id}, user={p.username}, "
                f"balance={p.balance}, lv={p.level}, hp={p.health}"
            )
        except Exception as e:
            lines.append(f"- {a.name}: profil hatası ({e})")
    return "\n".join(lines) or "(hesap yok)"


def _build_plan_system(default_account: str = "ygt", telegram_user_id: int | None = None) -> str:
    accounts = _accounts_context(telegram_user_id)
    mechanics = load_mechanics()
    catalog = catalog_for_prompt()
    return (
        f"Sen Diplomacia oyun API orkestratörüsün ({get_version_label()}). Türkçe yanıt ver.\n"
        "Görev: kullanıcı AKSİYON isteğini API çağrılarına çevir ve sonucu yorumla.\n"
        "Saf bilgi/öğretme sorularında steps=[] ve reply_tr ile kısa yönlendirme ver.\n"
        "Önce hızlı komutlar (farm, stat harca, akıllı farm) yeterliyse steps=[] bırak.\n\n"
        f"{build_ai_context(default_account)}\n\n"
        f"HESAPLAR:\n{accounts}\n\n"
        f"OYUN:\n{mechanics}\n\n"
        f"API KATALOĞU (method path):\n{catalog}\n\n"
        f"ÇIKTI JSON ŞEMASI:\n{PLAN_JSON_SCHEMA}\n\n"
        "KURALLAR:\n"
        "- En fazla 6 adım\n"
        "- Auth/upload/mod endpoint KULLANMA\n"
        "- Transfer, savaş ilanı, büyük market işlemleri için needs_confirmation=true\n"
        "- Farm: POST /auto/use-pills sonra POST /factories/work\n"
        '- Ülke yoksa: GET /players/profile; POST /countries/auto-assign veya POST /countries/select body country_id\n'
        "- Makale/gazete: başlık+metin yoksa POST /press YAPMA\n"
        "- Bilinmeyen path uydurma; katalogdan seç\n"
        "- reply_tr kısa; ham JSON yazma\n"
    )


def plan(user_message: str, default_account: str = "ercan2", *, telegram_user_id: int | None = None) -> dict:
    user = f"Varsayılan hesap: {default_account}\n\nKullanıcı: {user_message}"
    return generate_json(_build_plan_system(default_account, telegram_user_id), user)


def execute_steps(
    steps: list[dict],
    default_account: str,
    *,
    allow_confirm: bool = False,
) -> tuple[list[dict], list[dict], bool]:
    """Returns (results, pending_confirm, had_blocked)"""
    results: list[dict] = []
    pending: list[dict] = []
    had_blocked = False

    for step in steps[:8]:
        method = str(step.get("method", "GET")).upper()
        path = sanitize_path(str(step.get("path", "/players/profile")))
        body = step.get("body")
        if body is not None and not isinstance(body, (dict, list)):
            body = None
        account_name = str(step.get("account") or default_account).lower()
        acc = get_account(account_name)
        if not acc:
            results.append({"step": step, "error": f"hesap yok: {account_name}"})
            continue

        risk = classify_action(method, path, body if isinstance(body, dict) else None)
        if risk == "blocked":
            had_blocked = True
            results.append({"step": step, "error": "engelli endpoint", "risk": risk})
            continue
        if risk == "confirm" and not allow_confirm:
            pending.append({**step, "account": account_name})
            continue

        path_params = step.get("path_params") or {}
        if "{id}" in path and "id" not in path_params:
            path_params["id"] = acc.player_id

        res = call(
            method,
            path,
            token=acc.token,
            body=body,
            query=step.get("query"),
            path_params={k: str(v) for k, v in path_params.items()},
            delay=1.5,
        )
        results.append({"step": step, "account": account_name, "result": res})

    return results, pending, had_blocked


def run_agent(
    user_message: str,
    default_account: str = "ercan2",
    *,
    allow_confirm: bool = False,
    telegram_user_id: int | None = None,
) -> AgentResult:
    if not allow_confirm:
        fast = try_fast_path(user_message, default_account)
        if fast is not None:
            return fast

    if is_teach_question(user_message):
        try:
            taught = answer_teach_full(user_message, default_account, use_gemini=bool(GEMINI_API_KEY))
            return AgentResult(reply=taught.text, inline_buttons=taught.inline_buttons)
        except Exception as e:
            log.warning("coach failed: %s", e)
            return AgentResult(
                reply=f"❌ Koç modu hatası: {e}\n\nDene: `can ne işe yarıyor` veya `farm yap`"
            )

    try:
        plan_data = plan(user_message, default_account, telegram_user_id=telegram_user_id)
    except RuntimeError as e:
        fast = try_fast_path(user_message, default_account)
        if fast is not None:
            fast.reply = f"⚡ Gemini yoğun — hızlı mod:\n\n{fast.reply}"
            return fast
        return AgentResult(reply=f"❌ AI hatası: {e}\n\nFarm/durum için: `farm yap` veya `ne durumdayım`")

    reply = plan_data.get("reply_tr") or "Tamam."
    account = plan_data.get("account") or default_account
    steps = plan_data.get("steps") or []
    needs_conf = bool(plan_data.get("needs_confirmation"))

    if not steps and not needs_conf:
        return AgentResult(reply=reply)

    if needs_conf and not allow_confirm:
        return AgentResult(
            reply=reply + "\n\n⚠️ Onay gerekli — /confirm ile onayla veya /cancel",
            needs_confirmation=True,
            pending_actions=[{**s, "account": s.get("account") or account} for s in steps],
        )

    results, pending, blocked = execute_steps(steps, account, allow_confirm=allow_confirm)
    out = reply
    if results:
        formatted = format_step_results(results)
        if formatted:
            out += "\n\n" + formatted
    if pending:
        out += "\n\n⚠️ Onay bekleyen adımlar var — /confirm"
        return AgentResult(
            reply=out,
            steps_run=results,
            needs_confirmation=True,
            pending_actions=pending,
        )
    if blocked:
        out += "\n\n⛔ Bazı endpoint'ler güvenlik nedeniyle engellendi."
    return AgentResult(reply=out, steps_run=results)


def run_confirmed(pending: list[dict], default_account: str) -> AgentResult:
    results, still_pending, _ = execute_steps(pending, default_account, allow_confirm=True)
    reply = "✅ Onaylı işlemler çalıştırıldı.\n\n" + format_step_results(results)
    if still_pending:
        reply += "\n\n⚠️ Hâlâ bekleyen adım var."
    return AgentResult(reply=reply, steps_run=results, pending_actions=still_pending)


def direct_api(
    method: str,
    path: str,
    account_name: str,
    body: dict | None = None,
    *,
    allow_confirm: bool = False,
) -> AgentResult:
    step = {"method": method, "path": path, "body": body}
    risk = classify_action(method, path, body)
    if risk == "blocked":
        return AgentResult(reply=f"⛔ Engelli: {action_summary(method, path, body)}")
    if risk == "confirm" and not allow_confirm:
        return AgentResult(
            reply=f"⚠️ Onay gerekli:\n`{action_summary(method, path, body)}`\n/confirm",
            needs_confirmation=True,
            pending_actions=[{**step, "account": account_name}],
        )
    acc = get_account(account_name)
    if not acc:
        return AgentResult(reply=f"Hesap yok: {account_name}")
    res = call(method, path, token=acc.token, body=body, delay=1.0)
    icon = "✅" if res.get("ok") else "⚠️"
    snippet = json.dumps(res.get("data"), ensure_ascii=False)[:1200]
    return AgentResult(
        reply=f"{icon} HTTP {res.get('status')} `{res.get('path')}`\n```json\n{snippet}\n```",
        steps_run=[{"result": res}],
    )


def interpret_api_result(method: str, path: str, result: dict, question: str) -> str:
    """Gemini ile API çıktısını Türkçe yorumla."""
    if not GEMINI_API_KEY:
        return json.dumps(result.get("data"), ensure_ascii=False)[:800]
    sys_p = "Sen Diplomacia oyun asistanısın. API yanıtını operatöre Türkçe, kısa ve aksiyon odaklı özetle."
    user_p = f"Soru: {question}\n{method} {path}\nYanıt: {json.dumps(result, ensure_ascii=False)[:4000]}"
    try:
        out = generate_json(sys_p, user_p)
        return out.get("reply_tr") or out.get("summary") or str(out)[:800]
    except Exception as e:
        log.warning("interpret failed: %s", e)
        return json.dumps(result.get("data"), ensure_ascii=False)[:800]
