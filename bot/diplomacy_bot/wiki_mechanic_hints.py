"""Wiki sayfa başlığı/içeriğinden olası API yolları — admin wikitext'te path yazmasa da."""
from __future__ import annotations

import re
from typing import Iterable

# (regex on title+excerpt, suggested paths) — api_catalog ile hizalı
_RULES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"fabrika|factory|çalışma|calisma", re.I), (
        "/factories/my", "/factories/work", "/factories/join", "/factories/region",
        "/factories/world", "/factories/build", "/factories/work-status", "/auto/use-pills",
    )),
    (re.compile(r"pazar|market", re.I), ("/market/list", "/market", "/market/{id}/buy")),
    (re.compile(r"savaş|savas|war|ateşkes|ateskes|kışla|kisla|asker", re.I), (
        "/wars", "/wars/my-country", "/wars/{id}/contribute", "/military/me", "/military/train",
        "/training-wars/my", "/training-wars/{id}/attack", "/auto/toggle",
    )),
    (re.compile(r"eyalet|seyahat|harita|province|vatandaş|vatandas|citizenship", re.I), (
        "/provinces/all", "/provinces/travel/status", "/provinces/travel/start",
        "/citizenship/my", "/visas/pending-count",
    )),
    (re.compile(r"görev|gorev|quest", re.I), ("/quests", "/quests/{id}/claim")),
    (re.compile(r"bağış|bagis|transfer|para gönder", re.I), ("/transfer/send",)),
    (re.compile(r"seçim|secim|parti|parlamento|kabine|election", re.I), (
        "/parties/my", "/elections/active", "/parliament/proposals", "/cabinet/my-role",
    )),
    (re.compile(r"beceri|skill|pasif|level|xp|unvan", re.I), (
        "/players/profile", "/players/passive-skills", "/players/skills/upgrade", "/xp/history",
    )),
    (re.compile(r"elmas|diamond|premium|iap", re.I), (
        "/players/diamonds/packages", "/players/diamonds/iap-verify", "/auto/craft-pills",
    )),
    (re.compile(r"online|sohbet|chat|makale|press", re.I), (
        "/online", "/online/players", "/chat/conversations", "/press/articles",
    )),
    (re.compile(r"dünya|dunya|world", re.I), ("/world/summary", "/factories/world")),
]


def infer_api_paths(title: str, wikitext: str = "", excerpt: str = "") -> list[str]:
    blob = f"{title}\n{excerpt}\n{wikitext[:2000]}"
    found: set[str] = set()
    for pattern, paths in _RULES:
        if pattern.search(blob):
            found.update(paths)
    return sorted(found)


def infer_for_pages(pages: Iterable[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for page in pages:
        title = str(page.get("title") or "")
        inferred = infer_api_paths(
            title,
            str(page.get("wikitext") or ""),
            str(page.get("plain_excerpt") or ""),
        )
        explicit = list(page.get("api_paths") or [])
        merged = sorted(set(explicit) | set(inferred))
        if merged:
            out[title] = merged
    return out


def all_inferred_paths(pages: Iterable[dict]) -> list[str]:
    s: set[str] = set()
    for paths in infer_for_pages(pages).values():
        s.update(paths)
    return sorted(s)
