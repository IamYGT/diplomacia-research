"""Intent routing regression — lokasyon sorguları war fast-path'e düşmemeli.

Bug geçmişi: "ben neredeyim" gibi doğal sorular try_war_reference_fast_path
tarafından "savaş referansı" sanılıp yutuluyordu (war 2+ kelimelik metni kabul
ediyordu). Düzeltme: war fast-path sadece gerçek referans (URL/UUID/sayı) veya
savaş anahtar kelimesi içeren metni kabul eder; lokasyon intent'i travel
fast-path'ta savaş kelime gate'inden önce yakalanır.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

from diplomacy_bot.intent_travel_fast import try_travel_fast_path
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


# --- FIX 2: war fast-path artık agresif değil ---------------------------------

def test_war_fastpath_rejects_natural_questions():
    """Doğal sorular war referansı sananmamalı (None = fall-through)."""
    for q in ("ben neredeyim", "neredeyim", "ne zaman", "kimim ben", "nerede yaşıyorum"):
        assert try_war_reference_fast_path(q, _FakeAcc()) is None, f"{q!r} war'a düşmemeli"


def test_war_fastpath_accepts_url_reference():
    """URL referansı war handler'a gitmeli — API çağrısını mock'la."""
    with patch("diplomacy_bot.war_commands.resolve_and_configure_war") as rc:
        rc.return_value = {"ok": True, "summary": "TEST SAVAŞI"}
        with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
            r = try_war_reference_fast_path("diplomacia.com.tr/wars/war/42", _FakeAcc())
    assert r is not None


# --- FIX 1: lokasyon intent'i savaş kelime gate'inden önce ---------------------

def test_location_intent_catches_various_phrasings():
    """Çeşitli lokasyon ifadeleri travel fast-path'ta yakalanmalı."""
    queries = (
        "ben neredeyim",
        "neredeyim",
        "konumum",
        "nerede yaşıyorum",
        "hangi bölge",
        "ikametgah",
        "adresim ne",
        "lokasyon",
    )
    for q in queries:
        with patch("diplomacy_bot.travel_commands.format_travel_status", return_value="✅ Seyahat yok"):
            with patch("diplomacy_bot.game_api.get_profile", return_value=_profile()):
                with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                    r = try_travel_fast_path(q, _FakeAcc())
        assert r is not None, f"{q!r} lokasyon intent'ine düşmeli"
        assert "Kaliforniya" in r.reply, f"{q!r} cevabında eyalet olmalı"


def test_location_answer_is_concise_and_address_focused():
    """Cevap doğrudan adrese yönelik olmalı — tüm profil dökümü değil."""
    with patch("diplomacy_bot.travel_commands.format_travel_status", return_value="✅ Seyahat yok"):
        with patch("diplomacy_bot.game_api.get_profile", return_value=_profile()):
            with patch("diplomacy_bot.account_runtime.interactive_account_context", _noop_ctx):
                r = try_travel_fast_path("ben neredeyim", _FakeAcc())
    assert r is not None
    # Adres başlık satırında eyalet + ülke bir arada.
    assert "Kaliforniya" in r.reply and "TÜRKELİ" in r.reply
    # Tam profil dökümü olmamalı (altın/elmas/xp satırları yok).
    assert "altın" not in r.reply.lower() and "elmas" not in r.reply.lower()
    assert r.parse_mode == "HTML"
