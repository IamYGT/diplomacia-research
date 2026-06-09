from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode

from .config import API_BASE, FARM_DELAY_SEC


def normalize_path(path: str, params: dict[str, str] | None = None) -> str:
    """`/wars/{id}/contribute` + params id=xxx → /wars/xxx/contribute"""
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    params = params or {}
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key in params:
            return str(params[key])
        return m.group(0)

    p = re.sub(r"\{(\w+)\}", repl, p)
    p = p.split("?")[0]
    if "?" in path:
        qs = path.split("?", 1)[1]
        if qs and "=" not in p:
            p = f"{p}?{qs}"
    return p


def call(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | list | None = None,
    query: dict[str, Any] | None = None,
    delay: float = FARM_DELAY_SEC,
    path_params: dict[str, str] | None = None,
) -> dict[str, Any]:
    method = method.upper()
    url_path = normalize_path(path, path_params)
    if query:
        sep = "&" if "?" in url_path else "?"
        url_path = f"{url_path}{sep}{urlencode(query)}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; DiplomacyYGTBot/2.0)",
        "Origin": "https://diplomacia.com.tr",
        "Referer": "https://diplomacia.com.tr/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None and method in ("POST", "PUT", "PATCH", "DELETE"):
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()

    time.sleep(delay if token else 0.2)
    req = urllib.request.Request(API_BASE + url_path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode()
            parsed: Any
            if raw.strip().startswith(("{", "[")):
                parsed = json.loads(raw)
            else:
                parsed = {"raw": raw[:800]}
            return {"ok": True, "status": r.status, "method": method, "path": url_path, "data": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"error": raw[:500]}
        return {"ok": False, "status": e.code, "method": method, "path": url_path, "data": parsed}
