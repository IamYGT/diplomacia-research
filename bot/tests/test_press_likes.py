"""Press (makale) otomatik beğenme testleri."""

from __future__ import annotations

from unittest.mock import patch

from diplomacy_bot.press_likes import auto_like_articles, like_article, list_press_articles, format_like_result_html


def _fake_api_factory(responses):
    """responses: dict (method, path_sub) -> (status, body). GET list / POST vote ayrımı method ile."""
    calls = []

    def _api(method, path, token, body=None, delay=0.0):
        calls.append((method, path, body))
        m = method.upper()
        # En spesifik eşleşmeyi bul: önce tam method+sub çifti.
        for (rmeth, rsub), val in responses.items():
            if rmeth.upper() == m and rsub in path:
                return val
        return 200, {}

    _api.calls = calls
    return _api


def test_list_press_articles_parses_articles():
    api = _fake_api_factory({("GET", "/press"): (200, {"articles": [{"id": "a1", "title": "X", "my_vote": None}]})})
    arts = list_press_articles("tok", _api=api)
    assert len(arts) == 1 and arts[0]["id"] == "a1"


def test_like_article_success():
    api = _fake_api_factory({("POST", "/vote"): (200, {"score": 5, "my_vote": 1, "vote_power": 2})})
    r = like_article("tok", "a1", _api=api)
    assert r["ok"] is True and r["score"] == 5 and r["my_vote"] == 1


def test_like_article_failure_status():
    api = _fake_api_factory({("POST", "/vote"): (400, {"error": "bad"})})
    r = like_article("tok", "a1", _api=api)
    assert r["ok"] is False and r["status"] == 400


def test_auto_like_only_unvoted():
    """Sadece my_vote None olan makaleler beğenilir; 1/-1 olanlar atlanır."""
    api = _fake_api_factory(
        {
            ("GET", "/press"): (
                200,
                {
                    "articles": [
                        {"id": "a1", "title": "One", "my_vote": None},
                        {"id": "a2", "title": "Two", "my_vote": 1},
                        {"id": "a3", "title": "Three", "my_vote": None},
                        {"id": "a4", "title": "Four", "my_vote": -1},
                    ]
                },
            ),
            ("POST", "/vote"): (200, {"score": 1, "my_vote": 1}),
        }
    )
    res = auto_like_articles("tok", "ygt", max_per_run=10, _api=api)
    assert res["liked"] == 2
    assert res["skipped"] == 2
    assert res["errors"] == 0
    vote_calls = [c for c in api.calls if c[0] == "POST" and "/vote" in c[1]]
    voted_ids = {c[1] for c in vote_calls}
    assert "/press/a1/vote" in voted_ids and "/press/a3/vote" in voted_ids
    assert all("a2" not in v and "a4" not in v for v in voted_ids)


def test_auto_like_respects_max_per_run():
    api = _fake_api_factory(
        {
            ("GET", "/press"): (200, {"articles": [{"id": f"a{i}", "title": str(i), "my_vote": None} for i in range(10)]}),
            ("POST", "/vote"): (200, {"score": 1, "my_vote": 1}),
        }
    )
    res = auto_like_articles("tok", "ygt", max_per_run=3, _api=api)
    assert res["liked"] == 3


def test_auto_like_stops_on_rate_limit():
    api = _fake_api_factory(
        {
            ("GET", "/press"): (200, {"articles": [{"id": f"a{i}", "title": str(i), "my_vote": None} for i in range(10)]}),
            ("POST", "/vote"): (429, {"error": "rate"}),
        }
    )
    res = auto_like_articles("tok", "ygt", max_per_run=10, _api=api)
    assert res["liked"] == 0
    assert res["errors"] >= 1
    vote_calls = [c for c in api.calls if c[0] == "POST" and "/vote" in c[1]]
    assert len(vote_calls) < 10


def test_auto_like_skips_on_cooldown():
    with patch("diplomacy_bot.press_likes.cooldown_remaining_sec", return_value=30):
        res = auto_like_articles("tok", "ygt")
    assert res["skipped"] == -1  # cooldown işareti
    assert res["liked"] == 0


def test_format_like_result_html():
    res = {"liked": 2, "skipped": 1, "errors": 0, "samples": [{"title": "Selam", "score": 3}]}
    out = format_like_result_html(res)
    assert "2 makale beğenildi" in out and "Selam" in out
    empty = format_like_result_html({"liked": 0, "skipped": 5, "errors": 0})
    assert "oylanmış" in empty
    cd = format_like_result_html({"skipped": -1, "cooldown_sec": 42})
    assert "42s" in cd and "limit" in cd.lower()
