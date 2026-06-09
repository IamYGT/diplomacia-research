from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import DATA_DIR

CATALOG_PATH = DATA_DIR / "api_catalog.json"
MECHANICS_PATH = DATA_DIR / "game_mechanics.md"


@lru_cache(maxsize=1)
def load_catalog() -> list[dict]:
    if CATALOG_PATH.exists():
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return data.get("endpoints", [])
    return []


def search_endpoints(query: str, limit: int = 25) -> list[dict]:
    q = query.lower().strip()
    if not q:
        return load_catalog()[:limit]
    out = []
    for ep in load_catalog():
        blob = f"{ep.get('method','')} {ep.get('path','')}".lower()
        if q in blob:
            out.append(ep)
            if len(out) >= limit:
                break
    return out


def catalog_for_prompt(max_items: int = 120) -> str:
    lines = []
    for ep in load_catalog()[:max_items]:
        inf = "?" if ep.get("inferred") else ""
        lines.append(f"{ep['method']} {ep['path']}{inf}")
    extra = len(load_catalog()) - max_items
    if extra > 0:
        lines.append(f"... +{extra} endpoint daha (catalog.json)")
    return "\n".join(lines)


def load_mechanics() -> str:
    if MECHANICS_PATH.exists():
        return MECHANICS_PATH.read_text(encoding="utf-8")[:6000]
    return "Diplomacia geopolitik strateji MMO — altın, elmas, fabrika, savaş, siyaset."
