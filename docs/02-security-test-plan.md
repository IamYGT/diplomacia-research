# Diplomacia — Güvenlik Test Planı (Auth / JWT / Yetki)

> **Kapsam:** Yapısal JWT analizi + mobil bundle (`/tmp/diplomacia-index.js`) endpoint envanteri.  
> **Hedef API:** `https://diplomacia.com.tr/api` · **Socket:** `https://diplomacia.com.tr`  
> **Secret okunmadı:** `/root/diplomacia-auth.json` bu planda kullanılmaz.  
> **Ön koşul:** Geçerli normal kullanıcı JWT’si (test hesabı); mod/admin hesapları ayrı env’de.

---

## 1. JWT yapı analizi (secret gerekmez)

### 1.1 Bilinen format

| Alan | Tip (beklenen) | Rol |
|------|----------------|-----|
| `alg` | `HS256` | Simetrik imza — sunucu secret ile doğrular |
| `id` | UUID/string | Oturum sahibi oyuncu kimliği — **yetki ve IDOR testlerinin hedef alanı** |
| `username` | string | Görüntüleme / log; tek başına yetki kaynağı olmamalı |
| `tv` | integer | **Token version** — oturum geçersiz kılma sayacı |
| `iat` | unix ts | Token üretim zamanı |
| `exp` | unix ts | Token sona erme (~**7 gün**, `exp - iat ≈ 604800`) |

Header + payload Base64URL ile decode edilebilir; imza doğrulaması secret olmadan yapılamaz — bu plan yalnızca **yapısal çıkarım** ve **sunucu davranışı** testlerini kapsar.

### 1.2 `tv` (token version) — çıkarım

Kısa claim adı `tv`; endüstride `token_version` / `session_version` ile aynı desen.

**Beklenen sunucu davranışı:**

1. Login/register sonrası DB’deki `token_version` (veya eşdeğeri) JWT `tv` alanına yazılır.
2. Her istekte middleware: `jwt.tv === user.token_version` değilse **401** (veya token refresh reddi).
3. Şifre değişimi, hesap ban, “tüm oturumları kapat”, moderasyon müdahalesi gibi olaylarda DB sayacı artırılır → eski token’lar geçersiz kalır.

**Test edilecek (tv odaklı):**

| # | Senaryo | Beklenen |
|---|---------|----------|
| T1 | Geçerli token ile `/players/profile` | 200 |
| T2 | Payload’da `tv` +1 (imza bozuk) | 401 |
| T3 | Payload’da `tv` -1 veya 0 (imza bozuk) | 401 |
| T4 | Eski token (logout/şifre değişimi sonrası) | 401 tüm korumalı route’larda |
| T5 | `tv` claim’i tamamen silinmiş token | 401 |

> Not: İmza manipülasyonu testleri **bilerek geçersiz imza** ile yapılır; amaç sunucunun claim’i güvenmeden reddetmesidir.

### 1.3 ~7 günlük `exp` — çıkarım

- `exp - iat ≈ 604800` saniye → uzun ömürlü mobil oturum.
- **Risk:** Çalınan token 7 gün geçerli kalabilir (tv invalidation yoksa).
- **Test:** Süresi dolmuş token (`exp` geçmiş) → 401; sınırda token (`exp` ± birkaç saniye) → tutarlı davranış.

### 1.4 HS256 yapısal riskler (secret olmadan planlanır)

| Risk | Test |
|------|------|
| `alg:none` / algoritma confusion | `{"alg":"none"}` header + payload; imzasız veya boş imza ile istek |
| `alg` değiştirme (HS256→RS256 vb.) | Sunucu yalnızca HS256 kabul etmeli |
| Claim injection | `id` değiştirilmiş imzasız payload → reddedilmeli |
| `username` ile yetki | Aynı `id`, farklı `username` (imzalı değilse reddedilmeli) |

---

## 2. Bundle’dan endpoint envanteri

Kaynak: mobil API modülü (`API_BASE_URL = https://diplomacia.com.tr/api`).

### 2.1 Auth (authAPI)

| Method | Path | Not |
|--------|------|-----|
| POST | `/auth/register` | device_fingerprint gönderilir |
| POST | `/auth/login` | |
| POST | `/auth/google` | id_token + device_fingerprint |
| POST | `/auth/verify-turnstile` | cf_token |

### 2.2 Mod (modAPI) — **moderatör yetkisi beklenir**

| Method | Path | Body / params |
|--------|------|----------------|
| GET | `/mod/status/{playerId}` | Hedef oyuncu moderasyon durumu |
| POST | `/mod/punish` | `target_id`, `type`, `duration_label`, `reason` |
| GET | `/mod/punishment-history` | `page`, opsiyonel `type` |
| POST | `/mod/hide-article/{articleId}` | |

UI: `player.is_moderator === true` iken mod menüleri açılır (client-side; **sunucu zorunlu doğrulamalı**).

### 2.3 Moderation (moderationAPI) — **moderatör / raporlama**

| Method | Path | Not |
|--------|------|-----|
| POST | `/moderation/report` | Chat şikayeti |
| POST | `/moderation/report-article` | |
| GET | `/moderation/reports` | `status`, `type` query |
| GET | `/moderation/reports/count` | |
| POST | `/moderation/reports/{id}/punish` | |
| POST | `/moderation/reports/{id}/dismiss` | |
| POST | `/moderation/article-reports/{id}/punish` | |
| POST | `/moderation/article-reports/{id}/dismiss` | |
| GET | `/moderation/ban-status/player/{id}` | |
| GET | `/moderation/ban-status/party/{id}` | |
| POST | `/moderation/ban-avatar` | `player_id`, `hours` |
| POST | `/moderation/unban-avatar` | |
| POST | `/moderation/ban-username` | |
| POST | `/moderation/ban-party-logo` | |
| POST | `/moderation/unban-party-logo` | |
| POST | `/moderation/ban-party-name` | |
| POST | `/moderation/ban-party-description` | |
| POST | `/moderation/ban-party-abbreviation` | |
| POST | `/moderation/quick-ban/{playerId}` | |

### 2.4 Admin — ayrı `adminAPI` yok

- **`/players/report-admin`**: normal kullanıcı → admin’e mesaj (POST); admin paneli değil.
- **`/world/banned-players`**: ban listesi (token gerekir).
- Kabine / devlet: `cabinet_role` (`president`, `foreign_affairs`, …) — oyun içi yetki, JWT claim değil; profil cevabından gelir.

### 2.5 IDOR adayları (UUID / player id ile)

| Method | Path | Test |
|--------|------|------|
| GET | `/players/{id}` | Başka oyuncu profili — sadece public alanlar mı? |
| GET | `/players/{id}/xp-history` | Başka oyuncunun XP geçmişi |
| GET | `/players/{id}/donation-history` | Başka oyuncunun bağış geçmişi |
| GET | `/factories/player/{id}` | |
| GET | `/military/player/{id}` | |
| GET | `/parties/player/{id}` | |
| GET | `/press/player/{id}` | |
| GET | `/moderation/ban-status/player/{id}` | Mod-only olmalı |
| POST | `/moderation/ban-avatar` | `player_id` başkası — 403 |
| POST | `/cabinet/assign` | `player_id` — kabine rolü |
| POST | `/players/diamonds/gift-premium` | `recipient_player_id` |

### 2.6 Muhtemelen public (token’sız client çağrısı)

| Method | Path |
|--------|------|
| GET | `/countries` |
| GET | `/provinces/all` |

Diğer ~250 path bundle’da token ile çağrılıyor; yine de **Authorization header’sız** probe yapılacak.

---

## 3. Saldırı vektörleri — geçerli kullanıcı token’ı ile test

### 3.1 JWT manipülasyonu

| ID | Vektör | Adımlar | Pass kriteri |
|----|--------|---------|--------------|
| J1 | **alg:none** | Header `alg:none`, payload aynı `id`, imza boş/`null` | 401, asla 200 |
| J2 | **id swap (unsigned)** | Payload `id` → başka UUID, imza orijinal veya yok | 401 veya yalnızca kendi verisi |
| J3 | **id swap (re-sign)** | Secret bilinmiyorsa atla; bilinirse yalnızca kontrollü pentest | Başka kullanıcı verisi dönmemeli |
| J4 | **username spoof** | JWT `username` değiştir (imzasız) | Reddedilmeli |
| J5 | **tv bypass** | `tv` kaldır / sabitle | 401 |
| J6 | **exp ignore** | `exp` geleceğe al (imzasız) | Reddedilmeli |
| J7 | **Expired token** | `exp` geçmiş orijinal token | 401 |

### 3.2 IDOR — başka oyuncu UUID

Test kullanıcısı: **A** (token). Hedef: **B** (bilinen UUID, farklı hesap).

| ID | İstek | Beklenen |
|----|-------|----------|
| I1 | `GET /players/{B}` | Public profil OK; email/ iç veri yok |
| I2 | `GET /players/{B}/xp-history` | 403 veya boş; B’nin geçmişi sızmamalı |
| I3 | `GET /players/{B}/donation-history` | 403 |
| I4 | `PATCH`/`PUT` `/players/bio` + body’de başka id | Yalnızca A güncellenmeli |
| I5 | `POST /players/diamonds/gift-premium` + `recipient_player_id=B` | İş kuralına uygun; negatif bakiye / yetkisiz hediye yok |
| I6 | `POST /cabinet/assign` + `player_id=B` | Kabine rolü yalnızca yetkili devlet yetkilisi |

### 3.3 Mod / moderation endpoint probing (normal user token)

Normal kullanıcı **A** ile tüm mod/moderation POST/GET:

| ID | Endpoint | Beklenen |
|----|----------|----------|
| M1 | `POST /mod/punish` | **403** |
| M2 | `GET /mod/punishment-history` | **403** veya boş |
| M3 | `POST /mod/hide-article/{id}` | **403** |
| M4 | `GET /mod/status/{random}` | **403** veya sınırlı public |
| M5 | `POST /moderation/reports/{id}/punish` | **403** |
| M6 | `POST /moderation/ban-avatar` | **403** |
| M7 | `POST /moderation/quick-ban/{B}` | **403** |
| M8 | `GET /moderation/reports?status=pending` | **403** |

**Fail:** 200 + moderasyon yan etkisi (ban, punish kaydı, article hide).

### 3.4 Admin / yüksek yetki probing

| ID | Hedef | Not |
|----|-------|-----|
| A1 | `/players/report-admin` | Normal kullanıcı POST — spam/rate limit |
| A2 | `/world/banned-players` | Sadece whitelist/mod? |
| A3 | `/cabinet/{countryId}/broadcast` | `cabinet_role` sunucuda doğrulanmalı |
| A4 | `/wars/declare`, `/diplomacy/embargo/impose` | Devlet yetkisi |
| A5 | `/upload/country-flag`, `/upload/avatar` | Başka entity id ile upload |
| A6 | Bilinmeyen path’ler | `/admin`, `/internal`, `/debug`, `/api/v1/admin` → 404/403 |

Client `is_whitelisted` flag’i login/profile’da gelir — whitelist-only endpoint var mı ayrıca taranacak.

### 3.5 Eksik auth (Authorization yok)

| ID | Yöntem | Örnek path’ler |
|----|--------|----------------|
| N1 | Header yok | `/players/profile`, `/players/ping`, `/wars`, `/factories/my` |
| N2 | Header yok | Tüm POST mutation (transfer, buy, declare war) |
| N3 | Boş `Bearer ` | Aynı set |
| N4 | Geçersiz rastgele JWT | 401 tutarlı JSON hata |

**Pass:** Korumalı route’ların tamamı 401/403; yalnızca bilinen public GET’ler 200.

### 3.6 Socket auth

Bundle: `io(SOCKET_URL, { auth: { token, lang } })`.

| ID | Test | Beklenen |
|----|------|----------|
| S1 | Geçersiz token ile connect | Red / disconnect |
| S2 | Başka kullanıcı `id`’li JWT (geçerliyse) | Yalnızca kendi odaları |
| S3 | Mod-only event’ler (chat delete/ban) | Sunucu `is_moderator` doğrulaması |

---

## 4. Test yürütme

### 4.1 Araçlar

- **curl / httpie** — REST probe
- **jwt.io** veya `base64 -d` — payload inceleme (secret paylaşılmaz)
- **Burp / OWASP ZAP** — tekrarlanabilir kayıt
- **Mod hesabı** (ayrı credential) — pozitif mod testleri için

### 4.2 Örnek curl şablonları

```bash
# Profil (baseline)
curl -sS -H "Authorization: Bearer $TOKEN_A" \
  "https://diplomacia.com.tr/api/players/profile"

# IDOR — başka oyuncu
curl -sS -H "Authorization: Bearer $TOKEN_A" \
  "https://diplomacia.com.tr/api/players/${UUID_B}/xp-history"

# Mod probe (normal user)
curl -sS -X POST -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"target_id":"'"$UUID_B"'","type":"chat","duration_label":"1 saat","reason":"pentest"}' \
  "https://diplomacia.com.tr/api/mod/punish"

# Auth yok
curl -sS "https://diplomacia.com.tr/api/players/profile"
```

### 4.3 Sonuç kaydı

Her test için:

| Alan | Değer |
|------|--------|
| Test ID | J1, I2, M5, … |
| HTTP status | |
| Response özeti | Hata kodu / `error` alanı |
| Yan etki | DB’de ban/punish oluştu mu? |
| Sonuç | PASS / FAIL |

---

## 5. Öncelik sırası

1. **P0:** J1–J2, M1–M8, N1–N2 (mod + auth bypass)
2. **P1:** I1–I6 (IDOR veri sızıntısı)
3. **P2:** T2–T5 (`tv` invalidation), S1–S3 (socket)
4. **P3:** Kabine / ekonomi mutation IDOR, rate limit

---

## 6. Bilinen client-side ipuçları (sunucu doğrulamalı)

- `player.is_moderator` — UI gate; **tek başına güvenlik değil**
- `is_whitelisted` — login/profile; backend eşlemesi test edilmeli
- `cabinet_role` + `cabinet_country_id` — devlet aksiyonları
- Global token fallback: `setGlobalToken` / `b` ref — Authorization header her istekte `Bearer` (bundle `h()` helper)

---

## 7. Kapsam dışı

- JWT secret brute-force / HS256 key recovery
- `/root/diplomacia-auth.json` içeriği
- Production’da destructive test (gerçek ban, gerçek savaş ilanı) — staging veya test hesapları

---

*Oluşturulma: 2026-06-09 · Kaynak: yapısal JWT bilgisi + `/tmp/diplomacia-index.js` API modülü (satır ~248).*
