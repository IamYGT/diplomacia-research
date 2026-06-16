from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BOT_DIR / ".env")

# httpx her getUpdates poll'unu INFO loglayıp error log'u şişiriyordu — uyarı seviyesine düşür.
import logging as _logging

_logging.getLogger("httpx").setLevel(_logging.WARNING)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_raw_admins = os.environ.get("TELEGRAM_ADMIN_IDS", "")
TELEGRAM_ADMIN_IDS: set[int] = {
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
}

BOT_PUBLIC = os.environ.get("BOT_PUBLIC", "1").strip().lower() in ("1", "true", "yes", "on")
MAX_ACCOUNTS_PER_USER = max(1, int(os.environ.get("MAX_ACCOUNTS_PER_USER", "5")))

API_BASE = os.environ.get("DIPLOMACIA_API_BASE", "https://diplomacia.com.tr/api").rstrip("/")
DATA_DIR = Path(os.environ.get("DATA_DIR", BOT_DIR / "data"))
AUTOFARM_INTERVAL_SEC = int(os.environ.get("AUTOFARM_INTERVAL_SEC", "620"))
STAT_QUEUE_INTERVAL_SEC = int(os.environ.get("STAT_QUEUE_INTERVAL_SEC", "60"))
READINESS_CACHE_SEC = float(os.environ.get("READINESS_CACHE_SEC", "60"))
FARM_DELAY_SEC = float(os.environ.get("FARM_DELAY_SEC", "6"))
PILL_COOLDOWN_MS = 600_000

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
_fallback_raw = os.environ.get(
    "GEMINI_MODEL_FALLBACK",
    "gemini-2.5-flash-lite,gemini-flash-lite-latest",
)
GEMINI_MODEL_FALLBACK: list[str] = []
for m in [GEMINI_MODEL] + [x.strip() for x in _fallback_raw.split(",") if x.strip()]:
    if m not in GEMINI_MODEL_FALLBACK:
        GEMINI_MODEL_FALLBACK.append(m)

_coach_raw = os.environ.get("GEMINI_COACH_MODEL", "gemini-2.5-flash-lite,gemini-flash-lite-latest")
GEMINI_COACH_MODELS: list[str] = [x.strip() for x in _coach_raw.split(",") if x.strip()]
GEMINI_THINKING_BUDGET = int(os.environ.get("GEMINI_THINKING_BUDGET", "0"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "accounts.db"
LEGACY_AUTH = DATA_DIR / "import-auth.json"
# Eski şifreli kayıtlar için (migration v5) — çoğu kurulumda gerekmez
BOT_DB_SECRET = os.environ.get("BOT_DB_SECRET", "")
PENTEST_JWT = Path(os.environ.get("PENTEST_JWT_FILE", "/root/pentest-logs/raw/diplomacia/player_jwt.txt"))
INTEL_PATH = Path(os.environ.get("DIPLOMACIA_INTEL", BOT_DIR.parent / "engagement" / "intel" / "merged.json"))
if not LEGACY_AUTH.exists():
    for candidate in (Path("/root/diplomacia-auth.json"), PENTEST_JWT):
        if candidate.exists():
            LEGACY_AUTH = candidate
            break
