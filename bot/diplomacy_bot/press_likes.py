"""Gazete (press) makalelerini otomatik beğen.

API (frontend JS'ten tersine mühendislik):
  - Liste: GET /press?tab=new&page=1&lang=all  → {articles: [...]}
    her makalede my_vote alanı: null=oylanmamış, 1=beğenilmiş, -1=beğenilmemiş.
  - Beğen: POST /press/{id}/vote  body {vote: 1}  → {score, my_vote:1, vote_power}
    Tek seferlik — my_vote ayarlandıktan sonra değiştirilemez.

Otomasyon: tab=new (en yeni) sayfa 1 çekilir, my_vote None olanlar beğenilir.
Her çalışmada max_per_run ile sınırlı — rate-limit'ten kaçınmak için. Per-account
"son görülen makale id" takibi yok; my_vote None kontrolü yeterli dedup sağlar
(oy kalıcı olduğundan aynı makale iki kez beğenilemez).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .stealth_client import cooldown_remaining_sec

log = logging.getLogger(__name__)

ApiFn = Any
default_api = None  # runtime'da set

_MAX_PER_RUN = 10  # rate-limit güvenliği: bir döngüde en fazla bu kadar beğeni
_DELAY_SEC = 0.5  # her beğeni arası bekleme


def _game_api():
    """Geç import — sirkülar önlemek için çağrı anında."""
    from .game_api import api
    return api


def list_press_articles(token: str, *, tab: str = "new", page: int = 1, _api: ApiFn | None = None) -> list[dict]:
    """Gazete makalelerini listele (tab: new|hot|trending)."""
    api = _api or _game_api()
    st, data = api("GET", f"/press?tab={tab}&page={page}&lang=all", token, delay=0.3)
    if st != 200 or not isinstance(data, dict):
        return []
    return list(data.get("articles") or [])


def like_article(token: str, article_id: str, *, _api: ApiFn | None = None) -> dict:
    """Tek makale beğen (vote=1). Dönüş: {ok, status, score, my_vote, data}."""
    api = _api or _game_api()
    st, data = api("POST", f"/press/{article_id}/vote", token, {"vote": 1}, delay=_DELAY_SEC)
    body = data if isinstance(data, dict) else {}
    return {
        "ok": st == 200 and body.get("my_vote") == 1,
        "status": st,
        "score": body.get("score"),
        "my_vote": body.get("my_vote"),
        "vote_power": body.get("vote_power"),
        "data": body,
    }


def auto_like_articles(
    token: str,
    account_name: str,
    *,
    max_per_run: int = _MAX_PER_RUN,
    _api: ApiFn | None = None,
) -> dict:
    """En yeni makaleleri beğen — my_vote None olanlara vote=1 gönder.

    Rate-limit aktifse (cooldown) atla. max_per_run ile sınır. Oy kalıcı olduğu
    için aynı makale birden fazla çalışmada beğenilmez (API my_vote None kontrolü).
    """
    result = {"account": account_name, "liked": 0, "skipped": 0, "errors": 0, "samples": []}
    # Oyun-side cooldown aktifse bekleme — dashboard/profile kilitlemesin.
    cd = cooldown_remaining_sec()
    if cd > 0:
        result["skipped"] = -1  # cooldown işareti
        result["cooldown_sec"] = cd
        return result

    api = _api or _game_api()
    try:
        articles = list_press_articles(token, tab="new", page=1, _api=api)
    except Exception as e:
        log.warning("press list failed acc=%s: %s", account_name, e)
        result["errors"] += 1
        return result

    if not articles:
        return result

    cap = max(1, int(max_per_run))
    for art in articles:
        if result["liked"] >= cap:
            break
        # Sadece oylanmamış makaleler (my_vote None). 1/-1 ise atla.
        mv = art.get("my_vote")
        if mv is not None:
            result["skipped"] += 1
            continue
        aid = art.get("id")
        if not aid:
            continue
        try:
            r = like_article(token, str(aid), _api=api)
        except Exception as e:
            log.warning("press like failed acc=%s art=%s: %s", account_name, aid, e)
            result["errors"] += 1
            continue
        if r["ok"]:
            result["liked"] += 1
            if len(result["samples"]) < 3:
                result["samples"].append(
                    {"id": aid, "title": (art.get("title") or "")[:40], "score": r.get("score")}
                )
        else:
            result["errors"] += 1
            # Rate-limit / cooldown geldi ise gerisini bırak.
            if r.get("status") in (429,):
                log.info("press like rate-limited acc=%s — dur", account_name)
                break
        time.sleep(_DELAY_SEC)

    log.info(
        "press auto-like acc=%s liked=%d skipped=%d errors=%d",
        account_name, result["liked"], result["skipped"], result["errors"],
    )
    return result


def format_like_result_html(res: dict) -> str:
    """Bildirim mesajı — beğenilen makale özetleri."""
    if res.get("skipped", 0) < 0:
        sec = int(res.get("cooldown_sec") or cooldown_remaining_sec() or 0)
        return (
            f"⏳ API limiti aktif{f' ({sec}s kaldı)' if sec else ''}\n"
            "Farm yoğunken beğenme bekletilir — biraz sonra <code>makale beğen</code> dene."
        )
    liked = res.get("liked", 0)
    skipped = int(res.get("skipped", 0) or 0)
    errors = int(res.get("errors", 0) or 0)
    if liked <= 0:
        if errors > 0:
            return (
                "📰 Makale beğenme başarısız\n"
                f"Hata: {errors} · Atlanan (zaten oylu): {skipped}\n"
                "<i>Biraz bekleyip tekrar dene.</i>"
            )
        if skipped > 0:
            return (
                "📰 Beğenilecek yeni makale yok\n"
                f"Liste tarandı — {skipped} makale zaten oylanmış.\n"
                "<i>Sürekli beğeni için: <code>makale beğen aç</code></i>"
            )
        return (
            "📰 Beğenilecek makale bulunamadı\n"
            "<i>Gazetede yeni yazı çıkınca <code>makale beğen</code> veya otomatik modu aç.</i>"
        )
    import html as _html
    lines = [f"📰 <b>{liked} makale beğenildi</b>"]
    for s in res.get("samples") or []:
        lines.append(f"  • {_html.escape(s.get('title') or '?')} (skor {s.get('score')})")
    extra = res.get("liked", 0) - len(res.get("samples") or [])
    if extra > 0:
        lines.append(f"  · ve {extra} makale daha")
    return "\n".join(lines)
