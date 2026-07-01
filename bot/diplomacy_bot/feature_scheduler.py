"""Feature job kaydı — tek giriş (alert, hap CD, …)."""

from __future__ import annotations

import logging

from telegram.ext import Application

log = logging.getLogger(__name__)


def register_all_feature_jobs(app: Application) -> None:
    """Tüm arka plan feature job'ları."""
    if getattr(app, "_feature_scheduler_registered", False):
        return
    from .event_alerts import alert_watch_job
    from .fleet_inbox_watch import fleet_inbox_watch_job
    from .pill_cooldown_watch import pill_cooldown_watch_job
    from .training_watch import training_watch_job

    app.job_queue.run_repeating(alert_watch_job, interval=120, first=60)
    app.job_queue.run_repeating(pill_cooldown_watch_job, interval=90, first=45)
    app.job_queue.run_repeating(training_watch_job, interval=300, first=180)
    from .config import FLEET_INBOX_WATCH_INTERVAL_SEC

    app.job_queue.run_repeating(
        fleet_inbox_watch_job,
        interval=FLEET_INBOX_WATCH_INTERVAL_SEC,
        first=240,
    )
    app._feature_scheduler_registered = True
    log.info(
        "Feature scheduler: alert 120s, pill_cd 90s, training 300s, inbox_watch %ss",
        FLEET_INBOX_WATCH_INTERVAL_SEC,
    )


def install_feature_scheduler_hook() -> None:
    """telegram_app._post_init — job_queue üzerinden feature job kaydı."""
    from . import telegram_app as ta

    if getattr(ta, "_feature_scheduler_hook_installed", False):
        return

    _orig = ta._post_init

    async def _post_init(application: Application) -> None:
        await _orig(application)
        register_all_feature_jobs(application)

    ta._post_init = _post_init
    ta._feature_scheduler_hook_installed = True
    log.info("Feature scheduler post_init hook kuruldu")
