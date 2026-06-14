from __future__ import annotations

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def get_version() -> str:
    if _VERSION_FILE.exists():
        return _VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    return "0.0.0"


def get_version_label() -> str:
    v = get_version()
    return f"v{v}"


__version__ = get_version()
