from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from .config import GEMINI_API_KEY, GEMINI_MODEL_FALLBACK

log = logging.getLogger(__name__)


def _call(
    payload: dict,
    *,
    parse_json: bool,
    models: list[str] | None = None,
) -> Any:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil (.env)")

    data = json.dumps(payload).encode()
    errors: list[str] = []
    model_list = models or GEMINI_MODEL_FALLBACK

    for model in model_list:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.loads(r.read().decode())
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            log.info("Gemini OK: %s", model)
            if parse_json:
                return json.loads(text)
            return text
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:300]
            errors.append(f"{model}: HTTP {e.code}")
            log.warning("Gemini %s failed: %s %s", model, e.code, err[:120])
            if e.code not in (429, 503, 500, 502, 504):
                break
            continue
        except Exception as e:
            errors.append(f"{model}: {e}")
            log.warning("Gemini %s error: %s", model, e)
            continue

    raise RuntimeError("Gemini tüm modeller başarısız: " + "; ".join(errors[-3:]))


def generate_json(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    models: list[str] | None = None,
) -> dict:
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }
    return _call(payload, parse_json=True, models=models)


def generate_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.7,
    thinking_budget: int | None = None,
    google_search: bool = False,
    models: list[str] | None = None,
) -> str:
    gen_cfg: dict[str, Any] = {"temperature": temperature}
    if thinking_budget and thinking_budget > 0:
        gen_cfg["thinkingConfig"] = {"thinkingBudget": thinking_budget}

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": gen_cfg,
    }
    if google_search:
        payload["tools"] = [{"google_search": {}}]

    result = _call(payload, parse_json=False, models=models)
    return str(result).strip()


def verify_connection() -> dict:
    """Startup smoke — seçili model + gecikme (ms)."""
    import time

    from .config import GEMINI_MODEL

    t0 = time.perf_counter()
    out = generate_json(
        'Sadece JSON: {"reply_tr":"ok","ok":true}',
        "ping",
        models=[GEMINI_MODEL],
    )
    ms = int((time.perf_counter() - t0) * 1000)
    return {"model": GEMINI_MODEL, "latency_ms": ms, "ok": bool(out.get("reply_tr"))}
