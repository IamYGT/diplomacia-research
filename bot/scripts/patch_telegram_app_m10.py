#!/usr/bin/env python3
"""M10 — telegram_app: onboarding extract + job stubs + registry."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "diplomacy_bot" / "telegram_app.py"

MARKER_IMPORT = "log = logging.getLogger(__name__)\n"
IMPORT_BLOCK = (
    "log = logging.getLogger(__name__)\n\n"
    "from .handlers.cmd_onboarding import (\n"
    "    cmd_connect,\n"
    "    cmd_start,\n"
    "    send_connect_package as _send_connect_package,\n"
    ")\n"
)

START_CONNECT = "async def _send_connect_package("
END_CMD_START = "        _set_pending_connect(context, uid, True)\n\n\n@user_required\nasync def cmd_menu"

JOB_STUBS = '''async def stat_queue_job(context: ContextTypes.DEFAULT_TYPE):
    from .jobs.stat_queue_telegram_job import run_stat_queue_telegram_job

    await run_stat_queue_telegram_job(context)


async def press_like_job(context: ContextTypes.DEFAULT_TYPE):
    from .jobs.press_like_telegram_job import run_press_like_telegram_job

    await run_press_like_telegram_job(context)


async def autofarm_job(context: ContextTypes.DEFAULT_TYPE):
    from .jobs.autofarm_telegram_job import run_autofarm_telegram_job

    await run_autofarm_telegram_job(context)


'''

OLD_HANDLER_LOOP_START = "    for name, handler in ["
OLD_HANDLER_LOOP_END = "        app.add_handler(CommandHandler(name, handler))\n"
NEW_HANDLER_REG = "    from .handlers.registry import register_command_handlers\n\n    register_command_handlers(app)\n"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    if "from .handlers.cmd_onboarding import" in text:
        print("already patched")
        return

    if MARKER_IMPORT not in text:
        raise SystemExit("marker not found")
    text = text.replace(MARKER_IMPORT, IMPORT_BLOCK, 1)

    i0 = text.find(START_CONNECT)
    i1 = text.find(END_CMD_START)
    if i0 < 0 or i1 < 0:
        raise SystemExit("onboarding block not found")
    text = text[:i0] + text[i1:]

    j0 = text.find("async def stat_queue_job")
    j1 = text.find("\ndef run() -> None:")
    if j0 < 0 or j1 < 0:
        raise SystemExit("job block not found")
    text = text[:j0] + JOB_STUBS + text[j1 + 1 :]

    loop_start = text.find(OLD_HANDLER_LOOP_START)
    loop_end = text.find(OLD_HANDLER_LOOP_END, loop_start)
    if loop_start < 0 or loop_end < 0:
        raise SystemExit("handler loop not found")
    loop_end += len(OLD_HANDLER_LOOP_END)
    text = text[:loop_start] + NEW_HANDLER_REG + text[loop_end:]

    PATH.write_text(text, encoding="utf-8")
    print(f"patched {PATH} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
