#!/usr/bin/env python3
"""guide-meta.json — crawl + docs kanıtından tek kaynak üret."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data" / "guide-meta.json"
INIT = ROOT / "output" / "crawl" / "init_data.json"
PUBLIC_INIT = ROOT / "public" / "data" / "crawl" / "init_data.json"


def load_init():
    for p in (INIT, PUBLIC_INIT):
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for key in ("world_summary",):
            ws = data.get(key)
            if isinstance(ws, dict):
                return ws
        inner = data.get("data")
        if isinstance(inner, dict):
            ws = inner.get("world_summary")
            if isinstance(ws, dict):
                return ws
        if "total_players" in data:
            return data
    return {}


def main():
    ws = load_init()
    existing = {}
    if OUT.is_file():
        existing = json.loads(OUT.read_text(encoding="utf-8"))

    meta = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "app_version": existing.get("app_version", "1.5.0"),
        "expo_sdk": existing.get("expo_sdk", "55.0.0"),
        "world": {
            "total_players": int(ws.get("total_players", existing.get("world", {}).get("total_players", 4977))),
            "countries": int(ws.get("total_countries", ws.get("countries_count", existing.get("world", {}).get("countries", 21)))),
            "provinces": int(ws.get("total_provinces", ws.get("provinces_count", existing.get("world", {}).get("provinces", 59)))),
            "factories": int(ws.get("total_factories", ws.get("factories_count", existing.get("world", {}).get("factories", 3029)))),
            "api_endpoints": int(existing.get("world", {}).get("api_endpoints", 210)),
        },
        "economy": existing.get(
            "economy",
            {
                "gold_per_work": 2404,
                "diamonds_per_work": 20,
                "xp_per_work": 17,
                "factory_build_elmas_cost": 10000,
                "pill_cooldown_minutes": 10,
                "tutorial_bonus_gold": 250000,
                "quest_bonus_gold": 75000,
            },
        ),
        "quests": existing.get(
            "quests",
            {
                "work_1": {"reward_gold": 5000, "path": "/quests/work_1/claim"},
                "work_3": {"reward_gold": 20000, "path": "/quests/work_3/claim"},
                "work_5": {"reward_gold": 50000, "path": "/quests/work_5/claim"},
            },
        ),
        "checklist": existing.get(
            "checklist",
            [
                {"id": "tutorial", "label": "Tutorial complete-step 0–5", "reward": "~250.000 altın"},
                {"id": "work_1", "label": "Quest work_1 claim", "reward_gold": 5000},
                {"id": "work_3", "label": "Quest work_3 claim", "reward_gold": 20000},
                {"id": "work_5", "label": "Quest work_5 claim", "reward_gold": 50000},
                {"id": "factory", "label": "Elmas fabrikası kur", "reward": "−10.000 elmas"},
                {"id": "first_work", "label": "İlk factories/work", "reward_gold": 2404},
            ],
        ),
        "onboarding": existing.get(
            "onboarding",
            {"endpoint": "/players/complete-step", "steps": [0, 1, 2, 3, 4, 5], "replay_blocked": True},
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK {OUT} players={meta['world']['total_players']}")


if __name__ == "__main__":
    main()
