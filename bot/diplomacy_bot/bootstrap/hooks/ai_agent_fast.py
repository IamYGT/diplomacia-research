"""AI agent fast-path — domain bootstrap (M4)."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def install_ai_agent_fast_paths() -> None:
    from diplomacy_bot import ai_agent

    if getattr(ai_agent, "_extra_fast_paths_installed", False):
        return

    _orig = ai_agent.run_agent

    def run_agent_patched(
        user_message,
        default_account="ercan2",
        *,
        allow_confirm=False,
        telegram_user_id=None,
    ):
        if not allow_confirm:
            from diplomacy_bot.store import get_account

            acc = get_account(default_account)
            if acc:
                from diplomacy_bot.intent_easy_fast import try_easy_fast_path
                from diplomacy_bot.intent_mission_fast import try_mission_fast_path
                from diplomacy_bot.intent_war_contrib_fast import try_war_contrib_fast_path

                easy = try_easy_fast_path(user_message, acc)
                if easy is not None:
                    return easy
                mission_fast = try_mission_fast_path(user_message, acc)
                if mission_fast is not None:
                    return mission_fast
                contrib_fast = try_war_contrib_fast_path(user_message, acc)
                if contrib_fast is not None:
                    return contrib_fast
        return _orig(
            user_message,
            default_account,
            allow_confirm=allow_confirm,
            telegram_user_id=telegram_user_id,
        )

    ai_agent.run_agent = run_agent_patched  # type: ignore[assignment]
    ai_agent._extra_fast_paths_installed = True
    log.info("AI agent fast-path (domain bootstrap) kuruldu")
