"""Diplomacia Wiki (MediaWiki) snapshot — çek, kaydet, yükle."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WIKI_BASE = "https://wiki.diplomacia.com.tr"
WIKI_API = f"{WIKI_BASE}/api.php"
USER_AGENT = "Mozilla/5.0 (compatible; DiplomacyResearch-WikiSync/1.0)"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_DATA_DIR = _REPO_ROOT / "data" / "wiki"
SNAPSHOTS_DIR = WIKI_DATA_DIR / "snapshots"
MANIFEST_PATH = WIKI_DATA_DIR / "manifest.json"

_API_PATH_RE = re.compile(
    r"/(?:players|factories|provinces|wars|auto|quests|countries|military|"
    r"training-wars|training|market|transfer|parties|parliament|cabinet|"
    r"diplomacy|visas|citizenship|world|online|economy|election|elections|"
    r"chat|press|skills|passive-skills|xp|init|block|upload|mod)[a-z0-9_\-/{}]*",
    re.I,
)
_WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
_METHOD_HINT_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[a-z0-9_\-/{}]+)", re.I)
_TR_CHAR_RE = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


@dataclass
class WikiPage:
    pageid: int
    title: str
    revision_id: int | None
    wikitext: str
    content_hash: str
    api_paths: list[str] = field(default_factory=list)
    wiki_links: list[str] = field(default_factory=list)
    plain_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pageid": self.pageid,
            "title": self.title,
            "revision_id": self.revision_id,
            "content_hash": self.content_hash,
            "wikitext": self.wikitext,
            "api_paths": self.api_paths,
            "wiki_links": self.wiki_links,
            "plain_excerpt": self.plain_excerpt,
        }


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _wiki_get(params: dict[str, Any], *, timeout: float = 40) -> dict[str, Any]:
    url = WIKI_API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _title_score(title: str) -> int:
    score = 10 if _TR_CHAR_RE.search(title) else 0
    if any(x in title for x in ("Cadastro", "Doação", "Províncias", "Conquistas", "Unidades")):
        score -= 5
    return score


def _normalize_title_key(title: str) -> str:
    t = title.lower().strip()
    for a, b in (("ı", "i"), ("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "", t)


def _wikitext_plain_excerpt(text: str, limit: int = 400) -> str:
    t = re.sub(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]", r"\2\1", text)
    t = re.sub(r"'''+?|\{\|.*?\|\}|\{\{[^}]+\}\}", " ", t, flags=re.S)
    t = re.sub(r"^[=]+([^=]+)[=]+$", r"\1", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()[:limit]


def extract_api_paths(text: str) -> list[str]:
    found: set[str] = set()
    for m in _API_PATH_RE.findall(text):
        p = "/" + m.lstrip("/").split("?")[0].rstrip("/")
        if len(p) > 2:
            found.add(p)
    for _method, path in _METHOD_HINT_RE.findall(text):
        for m in _API_PATH_RE.findall(path):
            found.add("/" + m.lstrip("/").split("?")[0].rstrip("/"))
    return sorted(found)


def extract_wiki_links(text: str) -> list[str]:
    return sorted({m.strip() for m in _WIKI_LINK_RE.findall(text) if m.strip()})


def list_all_page_ids() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    apcontinue: str | None = None
    while True:
        params: dict[str, Any] = {"action": "query", "list": "allpages", "aplimit": 500}
        if apcontinue:
            params["apcontinue"] = apcontinue
        data = _wiki_get(params)
        out.extend(data.get("query", {}).get("allpages", []))
        apcontinue = data.get("continue", {}).get("apcontinue")
        if not apcontinue:
            break
        time.sleep(0.2)
    return out


def fetch_revisions(page_ids: list[int], *, batch_size: int = 12) -> dict[int, WikiPage]:
    pages: dict[int, WikiPage] = {}
    for i in range(0, len(page_ids), batch_size):
        chunk = page_ids[i : i + batch_size]
        data = _wiki_get(
            {
                "action": "query",
                "prop": "revisions",
                "pageids": "|".join(str(x) for x in chunk),
                "rvprop": "content|ids",
                "rvslots": "main",
            },
            timeout=60,
        )
        for raw in data.get("query", {}).get("pages", {}).values():
            if raw.get("missing"):
                continue
            rev = (raw.get("revisions") or [{}])[0]
            wikitext = rev.get("slots", {}).get("main", {}).get("*") or rev.get("*") or ""
            pages[int(raw["pageid"])] = WikiPage(
                pageid=int(raw["pageid"]),
                title=str(raw.get("title") or ""),
                revision_id=rev.get("revid"),
                wikitext=wikitext,
                content_hash=content_hash(wikitext),
                api_paths=extract_api_paths(wikitext),
                wiki_links=extract_wiki_links(wikitext),
                plain_excerpt=_wikitext_plain_excerpt(wikitext),
            )
        time.sleep(0.25)
    return pages


def dedupe_pages(pages: dict[int, WikiPage]) -> dict[int, WikiPage]:
    buckets: dict[str, list[WikiPage]] = {}
    for p in pages.values():
        if p.wikitext.strip():
            buckets.setdefault(_normalize_title_key(p.title), []).append(p)
    out: dict[int, WikiPage] = {}
    for group in buckets.values():
        best = max(group, key=lambda x: (_title_score(x.title), len(x.wikitext), x.pageid))
        out[best.pageid] = best
    return out


def fetch_snapshot(*, dedupe: bool = True) -> dict[str, Any]:
    listed = list_all_page_ids()
    pages = fetch_revisions([int(p["pageid"]) for p in listed])
    if dedupe:
        pages = dedupe_pages(pages)
    return {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "wiki_base": WIKI_BASE,
        "listed_pages": len(listed),
        "stored_pages": len(pages),
        "api_paths": sorted({ap for p in pages.values() for ap in p.api_paths}),
        "pages": {str(pid): p.to_dict() for pid, p in pages.items()},
    }


def snapshot_id_from_ts(ts: str) -> str:
    return ts.replace(":", "").replace("-", "")


def save_snapshot(payload: dict[str, Any], *, snapshots_dir: Path | None = None) -> Path:
    root = snapshots_dir or SNAPSHOTS_DIR
    root.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    pages = data.pop("pages")
    sid = snapshot_id_from_ts(data["fetched_at"])
    dest = root / sid
    dest.mkdir(parents=True, exist_ok=True)
    meta = {**data, "snapshot_id": sid}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (dest / "pages.jsonl").open("w", encoding="utf-8") as f:
        for page in sorted(pages.values(), key=lambda x: x["title"]):
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
    hints = {
        "api_paths": meta.get("api_paths", []),
        "by_page": {p["title"]: p.get("api_paths", []) for p in pages.values() if p.get("api_paths")},
    }
    (dest / "api_hints.json").write_text(json.dumps(hints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from .wiki_diff import enrich_snapshot_api_paths

    enriched = enrich_snapshot_api_paths({**meta, "pages": pages})
    (dest / "api_hints_inferred.json").write_text(
        json.dumps(
            {"api_paths": enriched["api_paths"], "by_page": enriched.get("api_hints_inferred", {})},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    meta["api_paths_inferred"] = enriched["api_paths"]
    _update_manifest(sid, meta)
    return dest


def _update_manifest(snapshot_id: str, meta: dict[str, Any]) -> None:
    WIKI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    history = list(manifest.get("history") or [])
    if not history or history[-1] != snapshot_id:
        history.append(snapshot_id)
    manifest.update(
        {
            "current": snapshot_id,
            "previous": manifest.get("current"),
            "history": history[-20:],
            "updated_at": meta.get("fetched_at"),
            "stored_pages": meta.get("stored_pages"),
        }
    )
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_snapshot(snapshot_id: str, *, snapshots_dir: Path | None = None) -> dict[str, Any]:
    dest = (snapshots_dir or SNAPSHOTS_DIR) / snapshot_id
    if not dest.exists():
        raise FileNotFoundError(f"snapshot yok: {dest}")
    meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
    pages: dict[str, Any] = {}
    with (dest / "pages.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                page = json.loads(line)
                pages[str(page["pageid"])] = page
    meta["pages"] = pages
    hints = dest / "api_hints.json"
    if hints.exists():
        meta["api_hints"] = json.loads(hints.read_text(encoding="utf-8"))
    return meta
