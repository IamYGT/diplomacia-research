"""Feature scheduler hook testleri."""

from unittest.mock import MagicMock, patch

from diplomacy_bot.feature_scheduler import (
    install_feature_scheduler_hook,
    register_all_feature_jobs,
)


def test_register_all_feature_jobs_once():
    app = MagicMock()
    app._feature_scheduler_registered = False
    app.job_queue = MagicMock()
    register_all_feature_jobs(app)
    assert app.job_queue.run_repeating.call_count == 2
    register_all_feature_jobs(app)
    assert app.job_queue.run_repeating.call_count == 2


def test_install_feature_scheduler_hook_calls_register():
    import asyncio

    import diplomacy_bot.telegram_app as ta

    orig = ta._post_init
    orig_installed = getattr(ta, "_feature_scheduler_hook_installed", False)

    async def orig_post(application):
        application._orig_ran = True

    try:
        ta._post_init = orig_post
        ta._feature_scheduler_hook_installed = False
        install_feature_scheduler_hook()
        app = MagicMock()
        with patch(
            "diplomacy_bot.feature_scheduler.register_all_feature_jobs"
        ) as reg:
            asyncio.run(ta._post_init(app))
            assert app._orig_ran is True
            reg.assert_called_once_with(app)
    finally:
        ta._post_init = orig
        ta._feature_scheduler_hook_installed = orig_installed


def test_pill_ready_markup():
    from diplomacy_bot.event_notify import pill_ready_reply_markup

    mk = pill_ready_reply_markup()
    assert mk["inline_keyboard"][0][0]["callback_data"] == "dash:home"
    assert mk["inline_keyboard"][0][1]["callback_data"] == "farm:hap"
