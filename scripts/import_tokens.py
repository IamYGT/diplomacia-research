#!/usr/bin/env python3
"""JWT token listesini import et — proxy otomatik atanır, autofarm açılır."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BOT = Path(__file__).resolve().parents[1] / "bot"
sys.path.insert(0, str(BOT))

from diplomacy_bot.account_pool import assign_proxy_slots, prepare_egress  # noqa: E402
from diplomacy_bot.game_api import get_profile  # noqa: E402
from diplomacy_bot.stealth_client import reset_request_proxy, set_request_proxy  # noqa: E402
from diplomacy_bot.store import add_account, init_db, list_accounts, set_autofarm  # noqa: E402


def load_tokens(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "accounts" in raw:
        return raw["accounts"]
    raise SystemExit("JSON: liste veya {accounts: [...]} bekleniyor")


def import_one(name: str, token: str, proxy_id: str, proxy_url: str, enable_autofarm: bool) -> str:
    prepare_egress(proxy_id)
    tok = set_request_proxy(proxy_url or None)
    try:
        prof = get_profile(token)
    finally:
        reset_request_proxy(tok)
    acc = add_account(name, token, prof.player_id, prof.username, proxy_id, proxy_url)
    if enable_autofarm:
        set_autofarm(acc.name, True)
    return f"OK {acc.name} -> {prof.username} lv{prof.level} proxy={proxy_id} autofarm={enable_autofarm}"


def main() -> None:
    p = argparse.ArgumentParser(description="Diplomacia hesap token import")
    p.add_argument("file", nargs="?", default=str(BOT / "data" / "tokens.json"), help="tokens.json yolu")
    p.add_argument("--no-autofarm", action="store_true", help="autofarm kapalı import")
    args = p.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(f"Dosya yok: {path}")
        print('Örnek: [{"name":"acc01","token":"eyJ..."}]')
        sys.exit(1)

    init_db()
    entries = load_tokens(path)
    names = [str(e.get("name", f"acc{i+1:02d}")).strip().lower() for i, e in enumerate(entries)]
    slots = assign_proxy_slots(names)

    results = []
    for e, name in zip(entries, names):
        token = (e.get("token") or "").strip()
        if not token:
            results.append(f"SKIP {name}: token yok")
            continue
        proxy_id, proxy_url = slots[name]
        if e.get("proxy_id"):
            proxy_id = e["proxy_id"]
            from diplomacy_bot.account_pool import get_proxy_by_id

            slot = get_proxy_by_id(proxy_id)
            proxy_url = slot.url if slot else proxy_url
        try:
            results.append(import_one(name, token, proxy_id, proxy_url, not args.no_autofarm))
        except Exception as ex:
            results.append(f"FAIL {name}: {ex}")

    print("\n".join(results))
    print(f"\nToplam hesap: {len(list_accounts())}")


if __name__ == "__main__":
    main()
