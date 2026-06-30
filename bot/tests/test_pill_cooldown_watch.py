"""Hap CD bitiş bildirimi testleri."""

from diplomacy_bot.pill_cooldown_watch import check_pill_cooldown_cleared


def test_notify_when_cooldown_clears():
    ev = check_pill_cooldown_cleared(
        "ygt",
        pill_cooldown_ms=0,
        health=0,
        pills=500,
        prev_cd=120000,
    )
    assert ev is not None
    assert "hap kullanılabilir" in ev["title"].lower()
    assert "500" in ev["body"]
    assert ev.get("with_markup") is True


def test_no_notify_when_still_on_cooldown():
    assert (
        check_pill_cooldown_cleared("ygt", pill_cooldown_ms=60000, health=0, pills=500, prev_cd=120000)
        is None
    )


def test_no_notify_on_first_seen():
    assert check_pill_cooldown_cleared("ygt", pill_cooldown_ms=0, health=0, pills=500, prev_cd=None) is None


def test_no_notify_when_health_full():
    assert check_pill_cooldown_cleared("ygt", pill_cooldown_ms=0, health=100, pills=5, prev_cd=1000) is None
