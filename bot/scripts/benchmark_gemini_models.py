#!/usr/bin/env python3
"""Gemini model benchmark — hız + JSON/text başarı oranı."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
import os

KEY = os.environ.get("GEMINI_API_KEY", "")
if not KEY:
    print("GEMINI_API_KEY yok")
    sys.exit(1)

CANDIDATES = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


def list_models() -> set[str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={KEY}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
        return {
            m["name"].replace("models/", "")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        }
    except Exception as e:
        print(f"list_models failed: {e}")
        return set()


def probe(model: str, *, json_mode: bool) -> tuple[bool, float, str]:
    gen_cfg: dict = {"temperature": 0.2, "maxOutputTokens": 128}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": "Diplomacia oyun botu. Türkçe kısa cevap."}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            '{"reply_tr":"farm yap","account":"ygt","steps":[],"needs_confirmation":false}'
                            if json_mode
                            else "Can hapı ne işe yarar? Tek cümle."
                        )
                    }
                ],
            }
        ],
        "generationConfig": gen_cfg,
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={KEY}"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = json.loads(r.read().decode())
        elapsed = time.perf_counter() - t0
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        if json_mode:
            json.loads(text)
        return True, elapsed, text[:60].replace("\n", " ")
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:120]
        return False, time.perf_counter() - t0, f"HTTP {e.code}: {err}"
    except Exception as e:
        return False, time.perf_counter() - t0, str(e)[:120]


def main() -> None:
    available = list_models()
    models = [m for m in CANDIDATES if m in available] if available else CANDIDATES
    print(f"Testing {len(models)} models (available in API: {len(available)})\n")
    print(f"{'model':<28} {'text':>6} {'json':>6} {'avg_ms':>8}  note")
    print("-" * 72)

    scores: list[tuple[str, float, bool, bool]] = []

    for model in models:
        ok_text, t_text, note_text = probe(model, json_mode=False)
        ok_json, t_json, note_json = probe(model, json_mode=True)
        if ok_text and ok_json:
            avg = (t_text + t_json) / 2 * 1000
            scores.append((model, avg, True, True))
            print(f"{model:<28} {t_text*1000:5.0f}ms {t_json*1000:5.0f}ms {avg:7.0f}ms  OK")
        else:
            fail = note_text if not ok_text else note_json
            print(f"{model:<28} {'FAIL':>6} {'FAIL' if not ok_json else 'ok':>6} {'—':>8}  {fail[:40]}")

    if not scores:
        print("\nHiçbir model geçmedi.")
        sys.exit(2)

    scores.sort(key=lambda x: x[1])
    best = scores[0][0]
    print(f"\nWINNER (fastest both modes): {best}")
    print(f"RUNNER_UP: {scores[1][0] if len(scores) > 1 else best}")


if __name__ == "__main__":
    main()
