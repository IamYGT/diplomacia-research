"""Fabrika merkezi testleri."""

from diplomacy_bot.account_config import AccountConfig
from diplomacy_bot.factory_board import (
    analyze_factory_board_enriched,
    factory_board_callback_rows,
    format_factory_board_html,
    format_factory_action_html,
    resolve_factory_index,
)


def _sample_pack():
    return {
        "factories": [
            {
                "id": "26ce706f-fb32-429b-8f48-1f36e0703119",
                "name": "BotFarm",
                "level": 1,
                "type": "elmas",
                "province_name": "Tahran",
                "worker_count": 0,
                "balance": 1200,
                "salary_rate": 87,
            }
        ],
        "work": {"working": False, "factory_id": None},
        "auto": {"next_work_in_ms": 385000},
        "region_factories": [
            {"id": "r1", "name": "AOG ELMAS", "owner_name": "Ares", "type": "elmas", "level": 80},
            {"id": "r2", "name": "Hürmüz Elmas", "owner_name": "SİSTEM", "type": "elmas", "level": 50},
        ],
        "province": "Hürmüz",
        "profile": {"diamonds": 5000},
    }


def test_analyze_factory_board_numbered():
    cfg = AccountConfig("test", primary_factory_id="26ce706f-fb32-429b-8f48-1f36e0703119")
    a = analyze_factory_board_enriched(_sample_pack(), cfg)
    assert len(a["owned_numbered"]) == 1
    assert a["owned_numbered"][0]["index"] == 1
    assert a["owned_numbered"][0]["is_primary"] is True
    assert len(a["region_numbered"]) == 2
    assert a["region_numbered"][0]["index"] == 1
    assert a["owned_ids"][0].startswith("26ce")


def test_format_factory_board_html():
    pack = _sample_pack()
    cfg = AccountConfig("test")
    html_out = format_factory_board_html(pack, analyze_factory_board_enriched(pack, cfg), cfg)
    assert "1." in html_out
    assert "BotFarm" in html_out
    assert "R1." in html_out
    assert "AOG ELMAS" in html_out
    assert "Fabrika merkezi" in html_out


def test_factory_callback_rows():
    pack = _sample_pack()
    rows = factory_board_callback_rows(analyze_factory_board_enriched(pack, AccountConfig("x")))
    assert any("fab:primary:1" in cb for row in rows for _, cb in row)


def test_resolve_factory_index():
    a = analyze_factory_board_enriched(_sample_pack(), AccountConfig("x"))
    assert resolve_factory_index(a, list_kind="owned", index=1) == "26ce706f-fb32-429b-8f48-1f36e0703119"
    assert resolve_factory_index(a, list_kind="region", index=1) == "r1"


def test_format_factory_action_ok():
    out = format_factory_action_html({"ok": True, "action": "close", "message": "Kapandı"})
    assert "✅" in out


def test_run_factory_action_requires_id():
    from diplomacy_bot import game_features

    r = game_features.run_factory_action("tok", "test", "close")
    assert r["ok"] is False
    assert "factory_id" in r.get("error", "")
