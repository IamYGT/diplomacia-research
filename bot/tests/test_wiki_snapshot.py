"""Wiki snapshot diff ve API çıkarımı testleri."""

from __future__ import annotations

import json
from pathlib import Path

from diplomacy_bot.wiki_diff import diff_snapshots
from diplomacy_bot.wiki_snapshot import (
    WikiPage,
    content_hash,
    dedupe_pages,
    extract_api_paths,
    extract_wiki_links,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "wiki_pages_sample.json"


def test_extract_api_paths_from_wikitext():
    text = "Otomatik çalışma POST /auto/work ve GET /factories/world kullanır."
    paths = extract_api_paths(text)
    assert "/auto/work" in paths
    assert "/factories/world" in paths


def test_extract_wiki_links():
    text = "[[Vatandaşlık]] ve [[seçimler|Seçimler]] sayfalarına bak."
    links = extract_wiki_links(text)
    assert "Vatandaşlık" in links
    assert "seçimler" in links


def test_dedupe_prefers_turkish_title():
    pages = {
        4: WikiPage(4, "Baslangic Bolgesi", 1, "eski ascii", content_hash("a")),
        31: WikiPage(31, "Başlangıç Bölgesi", 2, "türkçe içerik uzun", content_hash("b")),
    }
    out = dedupe_pages(pages)
    assert len(out) == 1
    assert 31 in out


def test_diff_detects_new_api_path():
    old = {
        "snapshot_id": "old",
        "api_paths": ["/auto/status"],
        "pages": {
            "1": {
                "pageid": 1,
                "title": "Günlük Rutinler",
                "content_hash": "aaa",
                "api_paths": ["/auto/status"],
                "plain_excerpt": "eski",
                "revision_id": 1,
            }
        },
    }
    new = {
        "snapshot_id": "new",
        "api_paths": ["/auto/status", "/factories/world"],
        "pages": {
            "1": {
                "pageid": 1,
                "title": "Günlük Rutinler",
                "content_hash": "bbb",
                "api_paths": ["/auto/status", "/factories/world"],
                "plain_excerpt": "yeni dünya fabrikası",
                "revision_id": 2,
            }
        },
    }
    d = diff_snapshots(old, new)
    assert d["summary"]["changed"] == 1
    assert "/factories/world" in d["new_api_paths"]
    assert d["changed_pages"][0]["new_api_paths"] == ["/factories/world"]


def test_fixture_sample_valid_json():
    if not FIXTURE.exists():
        return
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert "pages" in data
