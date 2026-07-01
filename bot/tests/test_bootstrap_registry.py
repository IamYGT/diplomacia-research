"""M4 explicit bootstrap hook testleri."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_explicit_hooks_registry_count():
    from diplomacy_bot.bootstrap import registry

    assert len(registry._EXPLICIT_HOOKS) >= 15


def test_explicit_hooks_install_marks_telegram():
    from diplomacy_bot.bootstrap.registry import install_explicit_hooks

    install_explicit_hooks()
    from diplomacy_bot import telegram_app as ta

    assert getattr(ta, "_mission_hook_installed", False)
    assert getattr(ta, "_easy_hook_installed", False)
    assert getattr(ta, "_dashboard_flood_installed", False)
    from diplomacy_bot import token_recovery_hooks

    assert token_recovery_hooks._INSTALLED


def test_explicit_dashboard_release_badge():
    from diplomacy_bot import telegram_ui as ui
    from diplomacy_bot.bootstrap import registry
    from diplomacy_bot.bootstrap.hooks.dashboard_release_badge import install_dashboard_release_badge

    registry._INSTALLED = False
    if hasattr(ui, "_release_badge_installed"):
        delattr(ui, "_release_badge_installed")
    install_dashboard_release_badge()
    assert getattr(ui, "_release_badge_installed", False) is True


def test_domain_hooks_registry_count():
    from diplomacy_bot.bootstrap import domain_registry

    assert len(domain_registry._DOMAIN_HOOKS) >= 7


def test_ptb_jobs_wired():
    from diplomacy_bot.bootstrap.hooks.telegram_ptb_jobs import install_telegram_ptb_jobs
    from diplomacy_bot import telegram_app as ta
    from diplomacy_bot.jobs.autofarm_telegram_job import run_autofarm_telegram_job
    from diplomacy_bot.jobs.press_like_telegram_job import run_press_like_telegram_job
    from diplomacy_bot.jobs.stat_queue_telegram_job import run_stat_queue_telegram_job

    if hasattr(ta, "_ptb_jobs_wired"):
        delattr(ta, "_ptb_jobs_wired")
    install_telegram_ptb_jobs()
    assert ta.autofarm_job is run_autofarm_telegram_job
    assert ta.stat_queue_job is run_stat_queue_telegram_job
    assert ta.press_like_job is run_press_like_telegram_job


def test_domain_hooks_install_ai_fast_paths():
    from diplomacy_bot.bootstrap.domain_registry import install_domain_hooks

    install_domain_hooks()
    from diplomacy_bot import ai_agent

    assert getattr(ai_agent, "_extra_fast_paths_installed", False)
