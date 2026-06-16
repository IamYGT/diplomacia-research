#!/usr/bin/env python3
"""GET /init/data probe — katalog dışı bootstrap endpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diplomacy_bot.config import API_BASE, DATA_DIR
from diplomacy_bot.game_api import api


def _load_token(account: str) -> str:
    from diplomacy_bot.store import get_account, init_db

    init_db()
    acc = get_account(account.strip().lower())
    if not acc or not acc.token:
        raise SystemExit(f"Hesap yok veya token eksik: {account}")
    return acc.token


def probe_init_data(token: str) -> dict:
    st, body = api("GET", "/init/data", token, delay=0.2)
    return {"status": st, "body": body if isinstance(body, dict) else {"raw": body}}


def summarize(body: dict) -> dict:
    if not isinstance(body, dict):
        return {}
    keys = sorted(body.keys())
    out: dict = {"top_level_keys": keys[:40]}
    for hint in ("factories", "wars", "world_summary", "player", "quests"):
        if hint in body:
            val = body[hint]
            if isinstance(val, list):
                out[hint] = f"list[{len(val)}]"
            elif isinstance(val, dict):
                out[hint] = f"dict[{len(val)} keys]"
            else:
                out[hint] = type(val).__name__
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Probe Diplomacia GET /init/data")
    p.add_argument("--account", "-a", default="ygt", help="Bot hesap adı")
    p.add_argument("--out", "-o", type=Path, help="JSON çıktı dosyası")
    args = p.parse_args()

    token = _load_token(args.account)
    result = probe_init_data(token)
    summary = summarize(result.get("body") or {})
    report = {"api_base": API_BASE, "summary": summary, **result}

    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)

    out = args.out or DATA_DIR / "probe_init_data_latest.json"
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\nWrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
