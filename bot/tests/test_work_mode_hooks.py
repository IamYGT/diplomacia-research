"""work_mode world hook testleri."""

from __future__ import annotations

from diplomacy_bot.work_mode_hooks import SETFABRIC_HELP, VALID_MODES


def test_setfabric_help_mentions_world():
    assert "world" in SETFABRIC_HELP
    assert "dünya" in SETFABRIC_HELP.lower() or "Dünya" in SETFABRIC_HELP


def test_valid_modes_includes_world():
    assert "world" in VALID_MODES


def test_work_mode_labels_patched():
    from diplomacy_bot.work_mode_hooks import install_work_mode_hooks
    from diplomacy_bot import factory_board as fb
    from diplomacy_bot import telegram_ui as ui

    install_work_mode_hooks()
    assert fb.WORK_MODE_LABELS.get("world") == "Dünya"
    assert ui.WORK_MODE_TR.get("world") == "Dünya fabrikası"


def test_farm_war_tab_note():
    from diplomacy_bot.easy_role import append_farm_war_tab_note

    out = append_farm_war_tab_note("<b>test</b>")
    assert "izleme" in out
    assert "katkı kapalı" in out
