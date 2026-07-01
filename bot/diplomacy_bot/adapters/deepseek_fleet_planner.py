"""DeepSeek fleet planner adapter — adapter: HTTP client for safe JSON decisions."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from ..domain.fleet_llm_decision import FleetLlmDecision, build_decision_prompt, normalize_llm_decision

PostJson = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]

SYSTEM_PROMPT = (
    "Sen Diplomacia filo planlayıcısısın. Token, JWT, şifre veya gizli veri isteme. "
    "Sadece verilen güvenli hesap özetlerine göre izinli JSON alanlarıyla operasyon hedefi üret. "
    "Bilinmeyen aksiyon yazma; mümkünse Hürmüz + ana fabrika + farm + saatlik antrenman varsay."
)


def plan_fleet_with_deepseek(
    operator_text: str,
    account_summaries: list[dict[str, Any]],
    *,
    fallback: Any | None = None,
    _post_json: PostJson | None = None,
) -> FleetLlmDecision:
    if not DEEPSEEK_API_KEY and _post_json is None:
        raise RuntimeError("DEEPSEEK_API_KEY tanımlı değil (.env)")
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_decision_prompt(operator_text, account_summaries)},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = (_post_json or _post)(f"{DEEPSEEK_BASE_URL}/chat/completions", payload, headers)
    return normalize_llm_decision(_extract_json(body), fallback=fallback)


def _post(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"DeepSeek HTTP {e.code}: {err}") from e


def _extract_json(body: dict[str, Any]) -> dict[str, Any]:
    content = body.get("content")
    if content is None:
        choices = body.get("choices") or []
        if choices and isinstance(choices[0], dict):
            content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise RuntimeError("DeepSeek JSON content yok")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise RuntimeError("DeepSeek JSON object döndürmedi")
    return parsed
