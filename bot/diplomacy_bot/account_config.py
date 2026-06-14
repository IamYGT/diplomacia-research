from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from .config import DB_PATH

DEFAULT_STAT_PRIORITY = ["kisla", "savas_teknikleri", "bilim_insani", "ekonomi"]

# Canlı probe (ygt/kalemiye): pasif skill anahtarı vergi_uzmani
CLASS_STAT_PRIORITY: dict[str, list[str]] = {
    "kalemiye": ["vergi_uzmani", "ekonomi", "bilim_insani", "kisla"],
    "er": ["kisla", "savas_teknikleri", "bilim_insani"],
    "bilim_insani": ["bilim_insani", "kisla", "savas_teknikleri"],
}


@dataclass
class AccountConfig:
    account_name: str
    role: str = "farmer"  # farmer | premium_hub
    work_mode: str = "own"  # own | foreign | fixed | auto
    preferred_factory_id: str | None = None
    allow_auto_build: bool = False
    stat_priority: list[str] = field(default_factory=lambda: list(DEFAULT_STAT_PRIORITY))
    war_enabled: bool = False
    target_war_id: str | None = None
    contribute_side: str = "auto"  # attacker | defender | auto
    training_enabled: bool = True
    is_premium_hub: bool = False
    craft_pills_when_low: bool = True
    min_pill_stock: int = 5
    craft_diamond_batch: int = 3000


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_config_table() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS account_config (
                account_name TEXT PRIMARY KEY,
                role TEXT DEFAULT 'farmer',
                work_mode TEXT DEFAULT 'own',
                preferred_factory_id TEXT,
                allow_auto_build INTEGER DEFAULT 0,
                stat_priority_json TEXT DEFAULT '[]',
                war_enabled INTEGER DEFAULT 0,
                target_war_id TEXT,
                contribute_side TEXT DEFAULT 'auto',
                training_enabled INTEGER DEFAULT 1,
                is_premium_hub INTEGER DEFAULT 0,
                craft_pills_when_low INTEGER DEFAULT 1,
                min_pill_stock INTEGER DEFAULT 5,
                craft_diamond_batch INTEGER DEFAULT 3000
            )
            """
        )


def get_config(account_name: str) -> AccountConfig:
    init_config_table()
    name = account_name.strip().lower()
    with _conn() as c:
        row = c.execute("SELECT * FROM account_config WHERE account_name=?", (name,)).fetchone()
    if not row:
        return AccountConfig(account_name=name)
    priority = json.loads(row["stat_priority_json"] or "[]")
    if not priority:
        priority = list(DEFAULT_STAT_PRIORITY)
    return AccountConfig(
        account_name=name,
        role=row["role"] or "farmer",
        work_mode=row["work_mode"] or "own",
        preferred_factory_id=row["preferred_factory_id"],
        allow_auto_build=bool(row["allow_auto_build"]),
        stat_priority=priority,
        war_enabled=bool(row["war_enabled"]),
        target_war_id=row["target_war_id"],
        contribute_side=row["contribute_side"] or "auto",
        training_enabled=bool(row["training_enabled"]),
        is_premium_hub=bool(row["is_premium_hub"]),
        craft_pills_when_low=bool(row["craft_pills_when_low"]),
        min_pill_stock=int(row["min_pill_stock"] or 5),
        craft_diamond_batch=int(row["craft_diamond_batch"] or 3000),
    )


def save_config(cfg: AccountConfig) -> None:
    init_config_table()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO account_config (
                account_name, role, work_mode, preferred_factory_id, allow_auto_build,
                stat_priority_json, war_enabled, target_war_id, contribute_side,
                training_enabled, is_premium_hub, craft_pills_when_low,
                min_pill_stock, craft_diamond_batch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                role=excluded.role,
                work_mode=excluded.work_mode,
                preferred_factory_id=excluded.preferred_factory_id,
                allow_auto_build=excluded.allow_auto_build,
                stat_priority_json=excluded.stat_priority_json,
                war_enabled=excluded.war_enabled,
                target_war_id=excluded.target_war_id,
                contribute_side=excluded.contribute_side,
                training_enabled=excluded.training_enabled,
                is_premium_hub=excluded.is_premium_hub,
                craft_pills_when_low=excluded.craft_pills_when_low,
                min_pill_stock=excluded.min_pill_stock,
                craft_diamond_batch=excluded.craft_diamond_batch
            """,
            (
                cfg.account_name,
                cfg.role,
                cfg.work_mode,
                cfg.preferred_factory_id,
                1 if cfg.allow_auto_build else 0,
                json.dumps(cfg.stat_priority),
                1 if cfg.war_enabled else 0,
                cfg.target_war_id,
                cfg.contribute_side,
                1 if cfg.training_enabled else 0,
                1 if cfg.is_premium_hub else 0,
                1 if cfg.craft_pills_when_low else 0,
                cfg.min_pill_stock,
                cfg.craft_diamond_batch,
            ),
        )


def update_config_field(account_name: str, **fields: object) -> AccountConfig:
    cfg = get_config(account_name)
    for key, value in fields.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    save_config(cfg)
    return cfg
