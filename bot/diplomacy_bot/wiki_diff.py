"""Wiki snapshot diff ve bot registry karşılaştırması."""
from __future__ import annotations

from typing import Any


def _pages_by_title(pages: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["title"]: p for p in pages.values()}


def diff_snapshots(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_pages = _pages_by_title(old.get("pages") or {})
    new_pages = _pages_by_title(new.get("pages") or {})
    old_titles = set(old_pages)
    new_titles = set(new_pages)

    added_titles = sorted(new_titles - old_titles)
    removed_titles = sorted(old_titles - new_titles)
    changed: list[dict[str, Any]] = []
    for title in sorted(old_titles & new_titles):
        o, n = old_pages[title], new_pages[title]
        if o.get("content_hash") != n.get("content_hash"):
            changed.append(
                {
                    "title": title,
                    "old_revision": o.get("revision_id"),
                    "new_revision": n.get("revision_id"),
                    "old_excerpt": (o.get("plain_excerpt") or "")[:120],
                    "new_excerpt": (n.get("plain_excerpt") or "")[:120],
                    "new_api_paths": sorted(set(n.get("api_paths") or []) - set(o.get("api_paths") or [])),
                    "removed_api_paths": sorted(set(o.get("api_paths") or []) - set(n.get("api_paths") or [])),
                }
            )

    old_api = set(old.get("api_paths") or [])
    new_api = set(new.get("api_paths") or [])
    return {
        "old_snapshot": old.get("snapshot_id"),
        "new_snapshot": new.get("snapshot_id"),
        "added_pages": [{"title": t, "api_paths": new_pages[t].get("api_paths", [])} for t in added_titles],
        "removed_pages": removed_titles,
        "changed_pages": changed,
        "new_api_paths": sorted(new_api - old_api),
        "removed_api_paths": sorted(old_api - new_api),
        "summary": {
            "added": len(added_titles),
            "removed": len(removed_titles),
            "changed": len(changed),
            "new_api_paths": len(new_api - old_api),
        },
    }


def compare_with_bot_registry(api_paths: list[str]) -> dict[str, Any]:
    from .api_route_registry import normalize_route_path, registry_keys

    reg_paths = {p for _m, p in registry_keys()}
    wiki_norm = {normalize_route_path(p) for p in api_paths}
    return {
        "wiki_api_count": len(wiki_norm),
        "registry_count": len(reg_paths),
        "missing_in_registry": sorted(p for p in wiki_norm if p not in reg_paths),
    }


def wiki_registry_aligned() -> dict[str, Any]:
    """Son wiki snapshot'taki inferred API yolları registry'de mi."""
    from .wiki_snapshot import load_manifest, load_snapshot

    manifest = load_manifest()
    if not manifest.get("current"):
        return {"ok": True, "skipped": True, "reason": "wiki snapshot yok"}
    snap = enrich_snapshot_api_paths(load_snapshot(manifest["current"]))
    report = compare_with_bot_registry(snap.get("api_paths") or [])
    report["ok"] = not report.get("missing_in_registry")
    report["snapshot"] = manifest["current"]
    return report


def enrich_snapshot_api_paths(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Explicit + mekanik çıkarımı birleştir."""
    from .wiki_mechanic_hints import all_inferred_paths, infer_for_pages

    pages = list((snapshot.get("pages") or {}).values())
    inferred = all_inferred_paths(pages)
    explicit = list(snapshot.get("api_paths") or [])
    merged = sorted(set(explicit) | set(inferred))
    out = dict(snapshot)
    out["api_paths"] = merged
    out["api_hints_inferred"] = infer_for_pages(pages)
    return out
