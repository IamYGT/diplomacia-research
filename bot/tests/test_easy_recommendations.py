"""Kolay mod önerileri — onboarding, ödül özeti, dispatch."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from diplomacy_bot.easy_mode import (
    format_onboarding_guide_html,
    format_program_step_message,
    summarize_mission_step_rewards,
)
from diplomacy_bot.modules.mission_types import MissionPhase, MissionStepResult, PhaseStatus
from diplomacy_bot.onboarding_store import is_easy_guide_shown, mark_easy_guide_shown


def test_onboarding_guide_has_three_buttons():
    text = format_onboarding_guide_html()
    assert "Altın Kazan" in text
    assert "Savaşa Vur" in text
    assert "Programı Çalıştır" in text


def test_summarize_farm_rewards():
    step = MissionStepResult(
        "ygt",
        "m1",
        MissionPhase.FARM_TICK,
        PhaseStatus.DONE,
        ok=True,
        actions=[{"farm": {"ok": True, "earned": {"money": 1200, "diamonds": 3}}}],
    )
    lines = summarize_mission_step_rewards(step)
    assert any("1,200" in line or "1200" in line for line in lines)
    assert any("Altın" in line for line in lines)


def test_format_program_step_shows_rewards():
    step = MissionStepResult(
        "ygt",
        "m1",
        MissionPhase.FARM_TICK,
        PhaseStatus.DONE,
        ok=True,
        actions=[{"farm": {"ok": True, "earned": {"money": 500}}}],
    )
    msg = format_program_step_message(step)
    assert "Altın kazandın" in msg
    assert "500" in msg


def test_onboarding_store_roundtrip(tmp_path, monkeypatch):
    from diplomacy_bot import store

    db = tmp_path / "t.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    store.init_db()
    assert not is_easy_guide_shown(999)
    mark_easy_guide_shown(999)
    assert is_easy_guide_shown(999)


@pytest.mark.asyncio
async def test_easy_menu_dispatch_program():
    from diplomacy_bot.telegram_easy import handle_easy_menu_action

    acc = SimpleNamespace(name="ygt", token="tok")
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    with (
        patch("diplomacy_bot.telegram_easy._resolve_account", return_value=(acc, [acc])),
        patch(
            "diplomacy_bot.telegram_easy._run_program_step",
            new=AsyncMock(return_value=("✅ test", None)),
        ),
    ):
        handled = await handle_easy_menu_action("programı çalıştır", update, context)

    assert handled is True
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_easy_menu_dispatch_unknown():
    from diplomacy_bot.telegram_easy import handle_easy_menu_action

    acc = SimpleNamespace(name="ygt", token="tok")
    update = MagicMock()
    context = MagicMock()
    with patch("diplomacy_bot.telegram_easy._resolve_account", return_value=(acc, [acc])):
        handled = await handle_easy_menu_action("farm yap", update, context)
    assert handled is False


def test_settings_easy_patch_multi_account():
    from diplomacy_bot.settings_easy import install_settings_easy_patch
    from diplomacy_bot.store import Account
    from diplomacy_bot import telegram_ui as ui

    install_settings_easy_patch()
    accs = [
        Account(1, "a", "t", "p", "u", True, 0, 0, "", "", "active"),
        Account(2, "b", "t", "p", "u", True, 0, 0, "", "", "active"),
    ]
    markup = ui.settings_inline_markup(accs[0], user_accs=accs)
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("Diğer Hesaplar" in label for label in labels)
