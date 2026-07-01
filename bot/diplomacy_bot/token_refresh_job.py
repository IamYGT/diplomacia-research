"""Periyodik token yenileme job'ı."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

log = logging.getLogger(__name__)


async def token_refresh_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    from .token_refresh_service import run_refresh_cycle

    try:
        results = await asyncio.to_thread(run_refresh_cycle)
        ok = [r for r in results if r.ok]
        if ok:
            log.info(
                "token_refresh_job: %d/%d yenilendi: %s",
                len(ok),
                len(results),
                ", ".join(f"{r.account_name}({r.source})" for r in ok),
            )
        elif results:
            log.debug(
                "token_refresh_job: %d hesap yenilenemedi",
                len(results),
            )
    except Exception:
        log.exception("token_refresh_job failed")


def install_token_refresh_job() -> None:
    from .feature_scheduler import register_all_feature_jobs

    if getattr(register_all_feature_jobs, "_token_refresh_hooked", False):
        return

    _orig = register_all_feature_jobs

    def register_all_feature_jobs_patched(app):
        _orig(app)
        if not app.job_queue:
            return
        from .config import TOKEN_REFRESH_INTERVAL_SEC

        app.job_queue.run_repeating(
            token_refresh_job,
            interval=TOKEN_REFRESH_INTERVAL_SEC,
            first=120,
            name="token_refresh",
        )
        log.info("token_refresh job kayıtlı interval=%ss", TOKEN_REFRESH_INTERVAL_SEC)

    register_all_feature_jobs_patched._token_refresh_hooked = True  # type: ignore[attr-defined]
    import diplomacy_bot.feature_scheduler as fs

    fs.register_all_feature_jobs = register_all_feature_jobs_patched  # type: ignore[assignment]
    log.info("token_refresh job hook kuruldu")
