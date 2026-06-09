# Güvenlik Bulguları — İlk Audit

**Tarih:** 2026-06-09  
**Token:** Normal kullanıcı (is_moderator: false)  
**Script:** `scripts/full_audit.py`

## Özet tablo

| ID | Test | Sonuç | Severity |
|----|------|-------|----------|
| S1 | Auth'suz `/init/data`, `/players/profile`, `/mod/*` | 401 | OK |
| S2 | JWT `alg:none` | 403 | OK |
| S3 | Fake UUID `/players/{id}` | 404 | OK |
| S4 | Kendi profil UUID ile | 200 | OK |
| S5 | Normal user → `POST /mod/punish` | 403 | OK |
| S5 | Normal user → `GET /moderation/reports` | 403 | OK |
| S5 | Normal user → `POST /moderation/ban-avatar` | 403 | OK |
| S9 | Transfer min amount | 400 ($100 min) | OK |
| S10 | `/countries` auth'suz | 200 | INFO (public) |
| S11 | JWT tv=1, exp 7 gün | INFO | |

**CRITICAL: 0**

## Pozitif gözlemler

1. Mod/moderation endpoint'leri sunucu tarafında rol kontrolü yapıyor — client bundle'da endpoint görünse bile 403.
2. JWT alg:none reddediliyor (403).
3. Hassas route'lar auth'suz 401.

## Cloudflare Error 1010

Hızlı ardışık IDOR isteklerinde (sunucu IP) Cloudflare **1010** döndü — bot/rate koruması. Crawl script'ine `sleep(0.15)` eklendi; agresif fuzz için residential proxy veya yavaş tempo gerekir.

## İzlenmesi gereken alanlar (P1-P2)

| Alan | Risk | Önerilen test |
|------|------|---------------|
| IDOR `/players/{uuid}` | Başka oyuncu profili 200 dönebilir (oyun tasarımı) | Gerçek UUID ile balance/email sızıyor mu? |
| `/online/players` | 403 (whitelist?) | Sadece mod/whitelist erişimi |
| `/countries/leaderboard/*` | Bazı route'lar 403 | Token/ülke bağımlı erişim |
| JWT 7 gün ömür | Çalıntı token | tv invalidation logout'ta test |
| IAP verify | Sahte purchase token | Invalid token → reject |
| Socket.IO | Token ile bağlantı | Başka kullanıcı kanalına subscribe? |
| Transfer `/transfer/send` | Ekonomi | IDOR + race (staging) |
| Upload endpoints | Dosya upload | MIME/size/path traversal |

## Mod endpoint mesajları (kanıt)

- `Moderatör yetkisi gerekli.`
- `Bu işlem için moderatör yetkisi gerekli.`

Ham: `output/security/findings.json`

---

## Checkpoint 4–7 ek bulgular (2026-06-09)

| ID | Test | Sonuç | Severity |
|----|------|-------|----------|
| CP4 | Onboarding step 0–5 replay (lv6 hesap) | delta 0, success false | OK |
| CP5 | Factory mutation IDOR re-probe | exploited 0 | OK |
| CP6 | Socket.IO connect + foreign DM | foreign_dm false | OK |
| CP6 | Transfer send (lv4) | 403 min lv5 | OK (gate) |
| CP7 | Transfer paralel race | **BLOCKED** — lv5+ hesap yok | INFO |

Özet: `docs/11-audit-summary.md` · `output/audit_summary.json`
