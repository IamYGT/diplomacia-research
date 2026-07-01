#!/usr/bin/env python3
"""M11 — telegram_app: account commands extract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "diplomacy_bot" / "telegram_app.py"

ACCOUNTS_IMPORT = (
    "from .handlers.cmd_accounts import (\n"
    "    cmd_accounts,\n"
    "    cmd_add,\n"
    "    cmd_remove,\n"
    "    cmd_setaccount,\n"
    "    cmd_status,\n"
    "    cmd_whoami,\n"
    ")\n"
)

ANCHOR = "    send_connect_package as _send_connect_package,\n)\n"
START = "@user_required\nasync def cmd_whoami"
END = "@user_required\nasync def cmd_farm"

HELPERS_IMPORT = (
    "from .handlers.account_helpers import (\n"
    "    api_for_account as _api_for_account,\n"
    "    profile_for_account as _profile_for_account,\n"
    "    proxy_ctx as _proxy_ctx,\n"
    ")\n"
)

SAVE_STUB = (
    "\n"
    "async def _save_account(update, name, token, *, uid=None, context=None):\n"
    '    """Bootstrap öncesi stub — connect_save.wire_save_account() üzerine yazar."""\n'
    '    raise RuntimeError("install_bootstrap() önce çağrılmalı")\n'
    "\n"
)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "from .handlers.cmd_accounts import" in text:
        print("already patched m11")
        return
    if ANCHOR not in text:
        raise SystemExit("onboarding import anchor not found")
    text = text.replace(ANCHOR, ANCHOR + "\n" + ACCOUNTS_IMPORT, 1)
    if "account_helpers" not in text:
        needle2 = "    cmd_whoami,\n)\n"
        text = text.replace(needle2, needle2 + "\n" + HELPERS_IMPORT + SAVE_STUB, 1)

    i0 = text.find(START)
    i1 = text.find(END)
    if i0 < 0 or i1 < 0:
        raise SystemExit(f"account block not found ({i0}, {i1})")
    text = text[:i0] + text[i1:]

    PATH.write_text(text, encoding="utf-8")
    print(f"patched m11 {PATH} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
