#!/usr/bin/env python3
"""Diplomacia bot giriş — fatal hatalarda Telegram bildirimi."""
from __future__ import annotations

from diplomacy_bot.crash_notify import install_crash_hooks, send_crash_notify


def main() -> None:
    install_crash_hooks()
    try:
        from diplomacy_bot.bootstrap import install_bootstrap

        install_bootstrap()

        from diplomacy_bot.telegram_app import run

        run()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        if code and code != 0:
            send_crash_notify(
                "Bot SystemExit",
                f"exit_code={code}",
                dedupe_key=f"systemexit:{code}",
            )
        raise
    except BaseException as e:
        send_crash_notify(
            "Bot run() crash",
            "main.run() exception",
            exc=e,
            dedupe_key=f"run:{type(e).__name__}",
        )
        raise


if __name__ == "__main__":
    main()
