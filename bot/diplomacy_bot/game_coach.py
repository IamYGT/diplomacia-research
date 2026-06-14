from __future__ import annotations

import re
from dataclasses import asdict

from . import game_api
from .catalog import load_mechanics
from .config import GEMINI_COACH_MODELS, GEMINI_THINKING_BUDGET
from .gemini_client import generate_text

ACTION_VERBS = re.compile(
    r"\b(farm|yap|katıl|gönder|çalış|claim|topla|al\b|seç|kur|başlat|onayla|listele)\b",
    re.I,
)

TEACH_PATTERNS = [
    r"ne işe yar",
    r"ne işe yarıyor",
    r"nedir\b",
    r"ne demek",
    r"nasıl çalış",
    r"nasıl yapıl",
    r"ne için",
    r"tavsiye",
    r"strateji",
    r"öğret",
    r"anlat",
    r"açıkla",
    r"rehber",
    r"ipucu",
    r"farkı ne",
    r"ne zaman",
    r"niçin",
    r"niye\b",
    r"can\b",
    r"hap\b",
    r"sağlık",
    r"xp\b",
    r"itibar",
    r"elmas",
    r"fabrika",
    r"savaş",
    r"eyalet",
    r"ülke",
    r"görev",
    r"level",
    r"seviye",
]


def is_teach_question(text: str) -> bool:
    t = text.lower().strip()
    if len(t) < 4:
        return False
    if ACTION_VERBS.search(t) and not re.search(r"ne işe yar|nedir|nasıl|tavsiye|anlat|açıkla", t):
        return False
    return any(re.search(p, t) for p in TEACH_PATTERNS)


def _topic_match(text: str) -> str | None:
    t = text.lower()
    topics = [
        ("can", [r"\bcan\b", r"sağlık", r"hap", r"health", r"pills"]),
        ("fabrika", [r"fabrika", r"work", r"çalış", r"farm"]),
        ("savaş", [r"savaş", r"war", r"asker", r"military"]),
        ("ülke", [r"ülke", r"eyalet", r"country", r"province"]),
        ("ekonomi", [r"altın", r"elmas", r"bakiye", r"para", r"ekonomi"]),
        ("görev", [r"görev", r"quest", r"xp", r"itibar", r"level", r"seviye"]),
        ("siyaset", [r"parti", r"seçim", r"kabine", r"parlamento"]),
    ]
    for name, patterns in topics:
        if any(re.search(p, t) for p in patterns):
            return name
    return None


def _local_can_answer(profile: game_api.Profile | None) -> str:
    hp = profile.health if profile else "?"
    pills = profile.health_pills if profile else "?"
    personal = ""
    if profile:
        if profile.health < 50 and profile.health_pills > 0:
            personal = f"\n\n📍 *Senin durumun:* {profile.health}/100 can, {profile.health_pills} hap — `hap kullan` yaz."
        elif profile.health < 100:
            personal = f"\n\n📍 *Senin durumun:* {profile.health}/100 can."
    return (
        "❤️ *Can (0–100)* — çalışma enerjin.\n\n"
        "• Fabrikada `work` yapmak için can harcanır; **can 0 ise çalışamazsın**\n"
        "• `hap kullan` → `POST /auto/use-pills` ile 100'e doldurur (~10 dk cooldown)\n"
        "• Tipik farm döngüsü: hap → fabrikaya katıl → work → ~2.500 altın + 20 💎\n"
        "• Can zamanla da yavaş yenilenir ama farm için hap şart\n\n"
        "💡 *Tavsiye:* Her farm öncesi can 100 olsun. `farm yap` komutu bunu otomatik dener."
        + personal
    )


LOCAL_ANSWERS: dict[str, str] = {
    "fabrika": (
        "🏭 *Fabrika sistemi*\n\n"
        "• `POST /factories/build` — elmas fabrikası kur (−10.000 💎)\n"
        "• `join` → `work` — çalış, altın+elmas+XP kazan\n"
        "• Fabrika **bulunduğun eyalette** olmalı; ülke değiştirince eski fabrikada çalışamazsın\n"
        "• ROI: ~10 dk'da bir ~2.500 altın (can + hap cooldown)\n\n"
        "💡 `farm yap` veya `ne durumdayım` ile başla."
    ),
    "savaş": (
        "⚔️ *Savaş*\n\n"
        "• Ülke eyaletleri birbirine savaş ilan eder\n"
        "• `POST /wars/{id}/contribute` — asker/güç katkısı (kabine/MP yetkisi gerekebilir)\n"
        "• Training savaşları eğitim amaçlı; standard savaşlarda fetih hedefi var\n"
        "• `savaş durumu` — ülke savaşlarını görürsün\n\n"
        "💡 Önce ülkeye katıl, asker eğit (`military/train`), sonra katkı."
    ),
    "ülke": (
        "🌍 *Ülke & eyalet*\n\n"
        "• Ülke seçmeden fabrika çalışır ama siyaset/savaş kısıtlı\n"
        "• `ülkeye katıl` — otomatik atama\n"
        "• `ülke listele` — seçenekler + butonlar\n"
        "• Eyalet = haritadaki bölge; fabrika ve çalışma eyalete bağlı\n\n"
        "💡 Aktif oyuncuysan güçlü ülke veya arkadaşının ülkesini seç."
    ),
    "ekonomi": (
        "💰 *Ekonomi özeti*\n\n"
        "• *Altın* — genel para, transfer, market\n"
        "• *Elmas* — premium, fabrika kurma, hap craft\n"
        "• *Kaynaklar* — NTE, deri, petrol (fabrika/depo)\n"
        "• En hızlı gelir: fabrika work döngüsü + günlük ödül + görev claim\n"
        "• Yeni hesap: onboarding step 0–5 (~250k tek sefer, replay yok)\n\n"
        "💡 `farm yap` | `görev topla` | `günlük`"
    ),
    "görev": (
        "📋 *Görev & ilerleme*\n\n"
        "• `work_1`, `work_3`, `work_5` — fabrika çalışma görevleri (quest_key ile claim)\n"
        "• XP → level; itibar → sıralama/siyaset etkisi\n"
        "• `görev` — liste | `görev topla` — hazır ödülleri al\n\n"
        "💡 UUID ile değil `quest_key` ile claim et."
    ),
    "siyaset": (
        "🏛️ *Siyaset*\n\n"
        "• Parti kur/katıl → seçim → parlamento → kabine rolleri\n"
        "• Başkan, dışişleri, savunma vb. roller devlet aksiyonları açar\n"
        "• Vatandaşlık başvurusu ve vize sistemi var\n\n"
        "💡 Önce ülke + itibar, sonra parti."
    ),
}


def local_answer(text: str, profile: game_api.Profile | None) -> str | None:
    topic = _topic_match(text)
    if topic == "can":
        return _local_can_answer(profile)
    if topic and topic in LOCAL_ANSWERS:
        base = LOCAL_ANSWERS[topic]
        if profile and topic == "fabrika":
            return base + f"\n\n📍 Şu an: {profile.province_name or '?'} eyaletinde olmalısın."
        return base
    return None


def _coach_system() -> str:
    return (
        "Sen Diplomacia (geopolitik strateji MMO) uzman koçusun. Türkçe konuş.\n"
        "Görevin: oyunu ÖĞRET, strateji öner, mekanikleri sade anlat.\n"
        "API komutu çalıştırma — kullanıcı aksiyon isterse hangi komutu yazacağını söyle.\n"
        "Yapı: kısa başlık → madde madde açıklama → kişisel tavsiye → bot komutu önerisi.\n"
        "Emoji kullan ama abartma. 150-400 kelime. Bilmediğin şeyi uydurma.\n\n"
        "OYUN BİLGİSİ:\n"
        + load_mechanics()
    )


def coach_with_gemini(
    user_message: str,
    profile: game_api.Profile | None,
    *,
    account_name: str,
) -> str:
    ctx = ""
    if profile:
        ctx = (
            f"\n\nOyuncu bağlamı ({account_name}): "
            f"lv{profile.level}, can {profile.health}/100, hap {profile.health_pills}, "
            f"altın {profile.balance:,}, elmas {profile.diamonds}, "
            f"ülke {profile.country_name or 'yok'}, eyalet {profile.province_name or 'yok'}"
        )
    user = f"Soru: {user_message}{ctx}"
    return generate_text(
        _coach_system(),
        user,
        temperature=0.75,
        thinking_budget=GEMINI_THINKING_BUDGET,
        google_search=False,
        models=GEMINI_COACH_MODELS,
    )


def answer_teach(
    user_message: str,
    default_account: str,
    *,
    use_gemini: bool = True,
) -> str:
    profile = None
    acc = None
    try:
        from .store import get_account

        acc = get_account(default_account)
        if acc:
            profile = game_api.get_profile(acc.token)
    except Exception:
        pass

    local = local_answer(user_message, profile)
    if local and not use_gemini:
        return local

    # Bilinen konularda yerel rehber yeterli (anında, API'siz)
    if local and _topic_match(user_message) in ("can", "fabrika", "ekonomi", "görev", "ülke", "savaş", "siyaset"):
        return local

    if use_gemini:
        try:
            return coach_with_gemini(user_message, profile, account_name=default_account)
        except Exception:
            if local:
                return local + "\n\n_(Gemini yoğun — yerel rehber)_"
            raise

    return local or "Bu konuda `yardım` veya daha spesifik sor — örn. `can ne işe yarıyor`"


def _button_priority(
    profile: game_api.Profile | None,
    topic: str | None,
    action: str,
) -> int:
    """Düşük puan = önce göster. Can 0 veya can konusu → hap öncelikli."""
    health = profile.health if profile else 100
    pills = profile.health_pills if profile else 0
    low_health = health < 100 and pills > 0

    if action == "hap":
        if not low_health:
            return 99
        if health == 0 or topic == "can":
            return 0
        if health < 50:
            return 1
        return 4

    if action == "farm":
        if topic in ("fabrika", "ekonomi"):
            return 2 if low_health and health == 0 else 1
        if low_health and health == 0:
            return 3
        return 2

    if action == "quests":
        return 1 if topic == "görev" else 5

    return 50


def coach_action_buttons(
    profile: game_api.Profile | None,
    topic: str | None,
) -> list[list[tuple[str, str]]] | None:
    """Koç cevabı altında profil/topic'e göre sıralı hızlı aksiyon butonları."""
    candidates: list[tuple[int, tuple[str, str]]] = []

    if profile and profile.health < 100 and profile.health_pills > 0:
        candidates.append(
            (_button_priority(profile, topic, "hap"), ("💊 Hap kullan", "action:hap"))
        )
    if topic in ("can", "fabrika", "ekonomi", "görev", None):
        candidates.append(
            (_button_priority(profile, topic, "farm"), ("🌾 Farm yap", "action:farm"))
        )
    if topic in ("görev", "ekonomi", None):
        candidates.append(
            (_button_priority(profile, topic, "quests"), ("🎁 Görev topla", "action:quests"))
        )

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return [[btn for _, btn in candidates[:3]]]


class TeachAnswer:
    __slots__ = ("text", "inline_buttons")

    def __init__(self, text: str, inline_buttons: list[list[tuple[str, str]]] | None = None):
        self.text = text
        self.inline_buttons = inline_buttons


def answer_teach_full(
    user_message: str,
    default_account: str,
    *,
    use_gemini: bool = True,
) -> TeachAnswer:
    text = answer_teach(user_message, default_account, use_gemini=use_gemini)
    profile = None
    try:
        from .store import get_account

        acc = get_account(default_account)
        if acc:
            profile = game_api.get_profile(acc.token)
    except Exception:
        pass
    return TeachAnswer(text, coach_action_buttons(profile, _topic_match(user_message)))
