"""Intent dispatch öncelik matrisi — fast-path handler çakışma/shadowing koruması.

Bu test, "ben neredeyim → savaş bulunamadı" sınıfı bug'ı regression'a karşı sabitler.
run_agent sırası: try_travel_fast_path → try_updates_fast_path → try_war_reference_fast_path
→ try_fast_path (route_intent). Her handler çok geniş regex'in diğerini gölgelememesi
gerekir. Matris, hangi ifadenin hangi handler'a düşeceğini açıkça belirtir.

Yeni fast-path eklerken veya regex değiştirirken bu matrisi güncelle — aksi halde
CI yakalar. Bu, merkezi intent sınıflandırıcı refactor'üne geçişin güvenli köprüsü.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from diplomacy_bot.intent_travel_fast import try_travel_fast_path
from diplomacy_bot.intent_updates_fast import try_updates_fast_path
from diplomacy_bot.intent_war_fast import try_war_reference_fast_path
from diplomacy_bot.game_api import Profile


def _profile():
    return Profile(
        player_id="p1",
        username="Y.G.T",
        balance=1000,
        diamonds=0,
        xp=1,
        level=51,
        health=100,
        health_pills=0,
        onboarding_step=None,
        country_name="TÜRKELİ",
        province_name="Kaliforniya",
    )


@contextmanager
def _noop_ctx(*a, **k):
    yield


class _FakeAcc:
    name = "ygt"
    token = "tok"
    proxy_id = ""
    proxy_url = None


# --- War fast-path: agresif-yutma regression ----------------------------------
# "ben neredeyim → savaş bulunamadı" bug'ının sınıfı: war fast-path, savaş anahtar
# kelimesi içermeyen serbest metni yutuyordu. Bu ifadeler None (fall-through) vermeli.
WAR_REJECTS = (
    "ben neredeyim",
    "neredeyim",
    "nerede yaşıyorum",
    "ne zaman",
    "kimim ben",
    "naber",
    "selam",
    "farm yap",
    "stat yükselt",
    "güncelleme",
)

# War fast-path KABUL etmeli (None DEĞİL): URL / UUID / sayı / savaş anahtar kelimesi.
WAR_ACCEPTS = (
    "diplomacia.com.tr/wars/war/42",
    "12345678-1234-1234-1234-123456789012",
    "42",
    "sırbistan savaşı",
    "savaşa katkı",
    "hedef savaş 3",
    "saldırgan",
    "savunmacı",
)


def test_war_rejects_natural_language():
    """War fast-path doğal dili yutmamalı — AI koça/route_intent'e düşmeli."""
    for q in WAR_REJECTS:
        r = try_war_reference_fast_path(q, _FakeAcc())
        assert r is None, f"WAR yutmamalı: {q!r}"


def test_war_accepts_real_references():
    """War fast-path gerçek savaş referanslarını kabul etmeli (None dönmemeli)."""
    for q in WAR_ACCEPTS:
        with patch("diplomacy_bot.war_commands.resolve_and_configure_war") as rc:
            rc.return_value = {"ok": True, "summary": "TEST"}
            with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                r = try_war_reference_fast_path(q, _FakeAcc())
        assert r is not None, f"WAR kabul etmeli: {q!r}"


# --- Location/travel fast-path ------------------------------------------------
LOCATION_PHRASES = (
    "ben neredeyim",
    "neredeyim",
    "konumum",
    "nerede yaşıyorum",
    "hangi bölge",
    "hangi eyalet",
    "ikametgah",
    "adresim ne",
    "lokasyon",
    "bulunduğum yer",
)
TRAVEL_PHRASES = (
    "seyahat durum",
    "seyahat iptal",
    "git Kaliforniya",
    "Kaliforniya eyaletine git",
    "Kaliforniya'ya git",
    "Ankara'ya git",
    "İzmir'e git",
)


def test_location_phrases_caught_by_travel():
    """Lokasyon ifadeleri war'a düşmeden travel fast-path'ta yakalanmalı."""
    for q in LOCATION_PHRASES:
        with patch("diplomacy_bot.travel_commands.format_travel_status", return_value="✅ Seyahat yok"):
            with patch("diplomacy_bot.game_api.get_profile", return_value=_profile()):
                with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                    r = try_travel_fast_path(q, _FakeAcc())
        assert r is not None, f"LOKASYON travel'da yakalanmalı: {q!r}"
        assert "Kaliforniya" in r.reply


def test_travel_phrases_caught_by_travel():
    for q in TRAVEL_PHRASES:
        # Seyahat komutları network gerektirir; run_travel/format_travel_status mock'la.
        with patch("diplomacy_bot.travel_commands.run_travel", return_value={"ok": True, "message": "OK"}):
            with patch("diplomacy_bot.travel_commands.format_travel_status", return_value="✅ Seyahat yok"):
                with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                    r = try_travel_fast_path(q, _FakeAcc())
        assert r is not None, f"TRAVEL handler'a girmeli: {q!r}"


def test_travel_does_not_swallow_non_travel():
    """Travel fast-path seyahat/lokasyon dışı metni yutmamalı (None)."""
    for q in ("farm yap", "stat yükselt", "savaş", "naber", "güncelleme"):
        r = try_travel_fast_path(q, _FakeAcc())
        assert r is None, f"TRAVEL yutmamalı: {q!r}"


# --- Updates fast-path --------------------------------------------------------
UPDATES_PHRASES = (
    "güncelleme",
    "yenilik",
    "changelog",
    "ne değişti",
    "yeni özellik",
)


def test_updates_phrases_caught():
    for q in UPDATES_PHRASES:
        with patch("diplomacy_bot.bot_updates.format_updates_html", return_value="UPDATES"):
            with patch("diplomacy_bot.bot_updates.updates_inline_markup", return_value=[]):
                r = try_updates_fast_path(q, _FakeAcc())
        assert r is not None, f"UPDATES yakalanmalı: {q!r}"


def test_updates_does_not_swallow_other():
    for q in ("farm yap", "ben neredeyim", "savaş", "naber"):
        r = try_updates_fast_path(q, _FakeAcc())
        assert r is None, f"UPDATES yutmamalı: {q!r}"


# --- Öncelik sırası: çakışan ifadeler doğru handler'a gider -------------------
# Aynı kelime farklı handler'larda olabilir; sıralı dispatch ilk eşleşeni seçer.
# Bu test sıralamayı (travel → updates → war → route) belgeler.
def test_dispatch_priority_order_documented():
    """Sıralı dispatch: travel > updates > war > route_intent.

    Örnek: 'neredeyim' war kelimesi içerse bile travel önce yakalar (eğer war
    kelimesi yoksa). Bu test önceliği sabitler; handler eklerken sıralamayı
    run_agent'de (ai_agent.run_agent) güncelle ve burayı da güncelle.
    """
    # 'ben neredeyim' — travel önce yakalar, war'a hiç gitmez.
    with patch("diplomacy_bot.travel_commands.format_travel_status", return_value="✅ Seyahat yok"):
        with patch("diplomacy_bot.game_api.get_profile", return_value=_profile()):
            with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                travel_r = try_travel_fast_path("ben neredeyim", _FakeAcc())
    assert travel_r is not None
    # Aynı ifade war fast-path'ta None olmalı (travel öncelikli).
    assert try_war_reference_fast_path("ben neredeyim", _FakeAcc()) is None


# --- Press (makale beğen) routing ---------------------------------------------
# "makale beğen" route_intent'te yakalanır; war/travel fast-path yutmaz.
# Toggle (aç/kapat) + anlık çalıştırma davranışı.
def test_makale_begen_phrases_reach_router():
    """'makale beğen' ifadeleri war/travel fast-path'lerde None vermeli (router'a düşer)."""
    for q in ("makale beğen aç", "makale beğen kapat", "makale beğen"):
        assert try_war_reference_fast_path(q, _FakeAcc()) is None, f"WAR yutmamalı: {q!r}"
        assert try_travel_fast_path(q, _FakeAcc()) is None, f"TRAVEL yutmamalı: {q!r}"
        assert try_updates_fast_path(q, _FakeAcc()) is None, f"UPDATES yutmamalı: {q!r}"


def test_makale_begen_toggle_via_router():
    """route_intent 'makale beğen aç/kapat' → config toggle + doğru mesaj."""
    from diplomacy_bot.intent_router import try_fast_path
    from diplomacy_bot.account_config import update_config_field, get_config

    with patch("diplomacy_bot.press_likes.auto_like_articles", return_value={"liked": 0, "skipped": 0, "errors": 0, "samples": []}):
        r_on = try_fast_path("makale beğen aç", "ygt")
        assert r_on is not None and "açıl" in r_on.reply.lower()
        assert get_config("ygt").auto_like_articles is True

        r_off = try_fast_path("makale beğen kapat", "ygt")
        assert r_off is not None and "kapatıl" in r_off.reply.lower()
        assert get_config("ygt").auto_like_articles is False

        r_now = try_fast_path("makale beğen", "ygt")
        assert r_now is not None and "makale" in r_now.reply.lower()

