"""Son autofarm/tick özeti — coach dashboard ve kullanıcı geri bildirimi."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

_lock = Lock()
_ACTIVITY: dict[str, deque[tuple[float, str]]] = {}
_MAX = 5


def record_tick_result(account_name: str, result) -> None:
    """TickResult veya benzeri nesneden kısa aktivite satırı kaydet."""
    name = account_name.strip().lower()
    line = _summarize(result)
    if not line:
        return
    with _lock:
        dq = _ACTIVITY.setdefault(name, deque(maxlen=_MAX))
        dq.append((time.time(), line))


def _summarize(result) -> str:
    if result is None:
        return ""
    err = getattr(result, "error", None) or ""
    if err and not getattr(result, "ok", False):
        return f"⚠️ {str(err)[:72]}"
    try:
        from .autofarm_notify import _action_labels

        labels = _action_labels(result)
    except Exception:
        labels = []
    if labels:
        return ", ".join(labels[:6])
    earned = int(getattr(result, "earned_money", 0) or 0)
    if earned > 0:
        return f"💰 +{earned:,}"
    if getattr(result, "ok", False):
        return "✓ tick"
    return ""


def format_activity_line(account_name: str, *, max_age_sec: float = 7200) -> str:
    """Coach için son tick özeti; yoksa boş string."""
    name = account_name.strip().lower()
    with _lock:
        dq = _ACTIVITY.get(name)
        if not dq:
            return ""
        ts, line = dq[-1]
    if time.time() - ts > max_age_sec:
        return ""
    age = int(time.time() - ts)
    if age < 60:
        ago = f"{age}sn önce"
    elif age < 3600:
        ago = f"{age // 60}dk önce"
    else:
        ago = f"{age // 3600}sa önce"
    return f"{line} ({ago})"


def record_mission_step(account_name: str, step) -> None:
    """MissionStepResult → kısa aktivite satırı."""
    name = account_name.strip().lower()
    if getattr(step, "blocked", False):
        wait = int(getattr(step, "wait_ms", 0) or 0)
        line = f"⏳ bekle {wait // 1000}sn" if wait else "⏳ bekle"
    elif getattr(step, "mission_complete", False):
        line = "✅ program bitti"
    elif getattr(step, "ok", False):
        parts = []
        for act in getattr(step, "actions", []) or []:
            if not isinstance(act, dict):
                continue
            if act.get("war"):
                parts.append("⚔️ savaş")
            if act.get("farm") or act.get("economy"):
                parts.append("🌾 farm")
            if act.get("training"):
                parts.append("🏋️ antrenman")
        line = ", ".join(parts) if parts else "✓ adım"
    else:
        err = str(getattr(step, "error", "") or "")[:72]
        line = f"⚠️ {err}" if err else "⚠️ adım"
    with _lock:
        dq = _ACTIVITY.setdefault(name, deque(maxlen=_MAX))
        dq.append((time.time(), line))


def last_entries(account_name: str, n: int = 3) -> list[str]:
    name = account_name.strip().lower()
    with _lock:
        dq = _ACTIVITY.get(name)
        if not dq:
            return []
        return [line for _, line in list(dq)[-n:]]
