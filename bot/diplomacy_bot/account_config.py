from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

DEFAULT_STAT_PRIORITY = ["kisla", "savas_teknikleri", "bilim_insani", "ekonomi"]

# Çoklu hesap görev profilleri
BOT_ROLES = ("farm", "war", "hybrid", "hub", "off")
ROLE_LABELS_TR = {
    "farm": "🌾 Farm",
    "war": "⚔️ Savaş",
    "hybrid": "🔀 Karma",
    "hub": "⭐ Premium hub",
    "off": "⏸ Durdu",
}
_LEGACY_ROLE_MAP = {
    "farmer": "farm",
    "premium_hub": "hub",
    "warrior": "war",
}


def normalize_role(role: str | None) -> str:
    r = (role or "farm").strip().lower()
    r = _LEGACY_ROLE_MAP.get(r, r)
    return r if r in BOT_ROLES else "farm"


def role_label(role: str | None) -> str:
    return ROLE_LABELS_TR.get(normalize_role(role), role or "?")


def apply_role_defaults(cfg: "AccountConfig") -> "AccountConfig":
    """Rol seçilince war/training/hub bayraklarını tutarlı yap."""
    role = normalize_role(cfg.role)
    cfg.role = role
    if role == "farm":
        cfg.war_enabled = False
        cfg.training_enabled = True
    elif role == "war":
        cfg.war_enabled = True
        cfg.training_enabled = True
    elif role == "hybrid":
        cfg.war_enabled = True
        cfg.training_enabled = True
    elif role == "hub":
        cfg.war_enabled = False
        cfg.training_enabled = False
        cfg.is_premium_hub = True
    return cfg

# Canlı probe (ygt/kalemiye): pasif skill anahtarı vergi_uzmani
CLASS_STAT_PRIORITY: dict[str, list[str]] = {
    "kalemiye": ["vergi_uzmani", "ekonomi", "bilim_insani", "kisla"],
    "er": ["kisla", "savas_teknikleri", "bilim_insani"],
    "bilim_insani": ["bilim_insani", "kisla", "savas_teknikleri"],
}


@dataclass
class AccountConfig:
    account_name: str
    role: str = "farm"  # farm | war | hybrid | hub | off
    work_mode: str = "own"  # own | foreign | world | fixed | auto
    preferred_factory_id: str | None = None
    allow_auto_build: bool = False
    stat_priority: list[str] = field(default_factory=lambda: list(DEFAULT_STAT_PRIORITY))
    stat_auto_enabled: bool = True  # altınla otomatik yükselt + pasif harca (farm döngüsü)
    war_enabled: bool = False
    target_war_id: str | None = None
    contribute_side: str = "auto"  # attacker | defender | auto
    auto_travel_enabled: bool = False  # bölge uyumsuzluğunda seyahat başlat
    war_intensity: str = "normal"  # normal | max — ana hesap agresif katkı profili
    training_enabled: bool = True
    is_premium_hub: bool = False
    craft_pills_when_low: bool = True
    min_pill_stock: int = 5
    craft_diamond_batch: int = 3000
    primary_factory_id: str | None = None
    default_salary_rate: int = 87
    default_build_name: str = "BotFarm"
    auto_like_articles: bool = False  # gazetede yeni makaleleri otomatik beğen


def _migrate_config_columns(c: sqlite3.Connection) -> None:
    cols = {row[1] for row in c.execute("PRAGMA table_info(account_config)").fetchall()}
    for col, ddl in (
        ("primary_factory_id", "ALTER TABLE account_config ADD COLUMN primary_factory_id TEXT"),
        ("default_salary_rate", "ALTER TABLE account_config ADD COLUMN default_salary_rate INTEGER DEFAULT 87"),
        ("default_build_name", "ALTER TABLE account_config ADD COLUMN default_build_name TEXT DEFAULT 'BotFarm'"),
        ("stat_auto_enabled", "ALTER TABLE account_config ADD COLUMN stat_auto_enabled INTEGER DEFAULT 1"),
        ("auto_travel_enabled", "ALTER TABLE account_config ADD COLUMN auto_travel_enabled INTEGER DEFAULT 0"),
        ("war_intensity", "ALTER TABLE account_config ADD COLUMN war_intensity TEXT DEFAULT 'normal'"),
        ("auto_like_articles", "ALTER TABLE account_config ADD COLUMN auto_like_articles INTEGER DEFAULT 0"),
    ):
        if col not in cols:
            c.execute(ddl)


def _conn() -> sqlite3.Connection:
    from .store import _conn as store_conn

    return store_conn()


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
                craft_diamond_batch INTEGER DEFAULT 3000,
                primary_factory_id TEXT,
                default_salary_rate INTEGER DEFAULT 87,
                default_build_name TEXT DEFAULT 'BotFarm',
                auto_like_articles INTEGER DEFAULT 0
            )
            """
        )
        _migrate_config_columns(c)


def get_config(account_name: str) -> AccountConfig:
    init_config_table()
    name = account_name.strip().lower()
    with _conn() as c:
        row = c.execute("SELECT * FROM account_config WHERE account_name=?", (name,)).fetchone()
    if not row:
        cfg = AccountConfig(account_name=name)
        return apply_role_defaults(cfg)
    priority = json.loads(row["stat_priority_json"] or "[]")
    if not priority:
        priority = list(DEFAULT_STAT_PRIORITY)
    cfg = AccountConfig(
        account_name=name,
        role=row["role"] or "farm",
        work_mode=row["work_mode"] or "own",
        preferred_factory_id=row["preferred_factory_id"],
        allow_auto_build=bool(row["allow_auto_build"]),
        stat_priority=priority,
        stat_auto_enabled=bool(row["stat_auto_enabled"]) if "stat_auto_enabled" in row.keys() else True,
        war_enabled=bool(row["war_enabled"]),
        target_war_id=row["target_war_id"],
        contribute_side=row["contribute_side"] or "auto",
        auto_travel_enabled=bool(row["auto_travel_enabled"]) if "auto_travel_enabled" in row.keys() else False,
        war_intensity=(row["war_intensity"] or "normal") if "war_intensity" in row.keys() else "normal",
        training_enabled=bool(row["training_enabled"]),
        is_premium_hub=bool(row["is_premium_hub"]),
        craft_pills_when_low=bool(row["craft_pills_when_low"]),
        min_pill_stock=int(row["min_pill_stock"] or 5),
        craft_diamond_batch=int(row["craft_diamond_batch"] or 3000),
        primary_factory_id=row["primary_factory_id"] if "primary_factory_id" in row.keys() else None,
        default_salary_rate=int(row["default_salary_rate"] or 87) if "default_salary_rate" in row.keys() else 87,
        default_build_name=(row["default_build_name"] or "BotFarm") if "default_build_name" in row.keys() else "BotFarm",
        auto_like_articles=bool(row["auto_like_articles"]) if "auto_like_articles" in row.keys() else False,
    )
    return apply_role_defaults(cfg)


def save_config(cfg: AccountConfig) -> None:
    cfg = apply_role_defaults(cfg)
    init_config_table()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO account_config (
                account_name, role, work_mode, preferred_factory_id, allow_auto_build,
                stat_priority_json, stat_auto_enabled, war_enabled, target_war_id, contribute_side,
                auto_travel_enabled, war_intensity,
                training_enabled, is_premium_hub, craft_pills_when_low,
                min_pill_stock, craft_diamond_batch,
                primary_factory_id, default_salary_rate, default_build_name,
                auto_like_articles
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_name) DO UPDATE SET
                role=excluded.role,
                work_mode=excluded.work_mode,
                preferred_factory_id=excluded.preferred_factory_id,
                allow_auto_build=excluded.allow_auto_build,
                stat_priority_json=excluded.stat_priority_json,
                stat_auto_enabled=excluded.stat_auto_enabled,
                war_enabled=excluded.war_enabled,
                target_war_id=excluded.target_war_id,
                contribute_side=excluded.contribute_side,
                auto_travel_enabled=excluded.auto_travel_enabled,
                war_intensity=excluded.war_intensity,
                training_enabled=excluded.training_enabled,
                is_premium_hub=excluded.is_premium_hub,
                craft_pills_when_low=excluded.craft_pills_when_low,
                min_pill_stock=excluded.min_pill_stock,
                craft_diamond_batch=excluded.craft_diamond_batch,
                primary_factory_id=excluded.primary_factory_id,
                default_salary_rate=excluded.default_salary_rate,
                default_build_name=excluded.default_build_name,
                auto_like_articles=excluded.auto_like_articles
            """,
            (
                cfg.account_name,
                cfg.role,
                cfg.work_mode,
                cfg.preferred_factory_id,
                1 if cfg.allow_auto_build else 0,
                json.dumps(cfg.stat_priority),
                1 if cfg.stat_auto_enabled else 0,
                1 if cfg.war_enabled else 0,
                cfg.target_war_id,
                cfg.contribute_side,
                1 if cfg.auto_travel_enabled else 0,
                cfg.war_intensity,
                1 if cfg.training_enabled else 0,
                1 if cfg.is_premium_hub else 0,
                1 if cfg.craft_pills_when_low else 0,
                cfg.min_pill_stock,
                cfg.craft_diamond_batch,
                cfg.primary_factory_id,
                cfg.default_salary_rate,
                cfg.default_build_name,
                1 if cfg.auto_like_articles else 0,
            ),
        )


def update_config_field(account_name: str, **fields: object) -> AccountConfig:
    cfg = get_config(account_name)
    for key, value in fields.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
    save_config(cfg)
    return cfg
