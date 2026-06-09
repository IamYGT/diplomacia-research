# Quest Claim Kök Neden + Stack & CVE

**Tarih:** 2026-06-09

---

## Quest claim — bug değil, yanlış endpoint

| Deneme | Sonuç |
|--------|--------|
| `POST /quests/{uuid}/claim` | 400 `Geçersiz görev.` |
| `POST /quests/{quest_key}/claim` | **200** + ödül |

Client (bundle kanıtı): `claimReward(token, e.quest_key)` → `/quests/work_1/claim`

### CONFIRMED ödüller (Ercan2)

| quest_key | Ödül | Replay |
|-----------|------|--------|
| `work_1` | +5.000 altın | `Ödül zaten alındı.` |
| `work_3` | +20.000 altın | `Ödül zaten alındı.` |
| `work_5` | +50.000 (tamamlanınca) | tek sefer |

**Sürekli farm:** Hayır — replay kapalı. **Gizli key brute:** Bilinmeyen key → `Geçersiz görev.`

---

## Stack envanteri

### Frontend (CONFIRMED — bundle manifest)

| Bileşen | Sürüm / kanıt |
|---------|----------------|
| Uygulama | **Diplomacia 1.5.0** |
| Expo SDK | **55.0.0** |
| Slug / scheme | `strategos` / `com.targan.strategos` |
| React | **19.x** (`react.dev/errors` in bundle) |
| React Navigation | `@react-navigation` |
| i18next | present |
| Leaflet | **1.9.4** |
| Socket.IO client | **Engine.IO 4** (handshake `EIO=4`) |
| Expo projectId | `28b49941-1e41-4561-8c11-e3476780997b` |

### Edge / CDN

| Bileşen | Kanıt |
|---------|--------|
| Cloudflare | `server: cloudflare`, Turnstile CSP |
| HSTS | `max-age=31536000` |

### Backend (kısmi — header sızıntısı sınırlı)

| Bileşen | Kanıt | Sürüm |
|---------|--------|-------|
| API host | `diplomacia.com.tr/api` | — |
| Railway | `server: railway-hikari` (direkt subdomain 404) | UNVERIFIED Node sürümü |
| Socket.IO server | EIO4 polling handshake | **v4.x** (minor UNVERIFIED) |
| JWT | HS256, `tv` claim | — |
| DB | — | UNVERIFIED (muhtemelen PostgreSQL — Railway tipik) |

---

## CVE değerlendirmesi

### Socket.IO — CVE-2024-38355 (DoS)

- **Etki:** Crafted paket → Node process crash
- **Patch:** `socket.io >= 4.6.2`
- **Diplomacia:** Sunucu **EIO 4** kullanıyor; **tam npm sürümü bilinmiyor** → `< 4.6.2` ise risk UNVERIFIED yüksek
- **Kaynak:** [GHSA-25hc-qcg6-38wj](https://github.com/socketio/socket.io/security/advisories/GHSA-25hc-qcg6-38wj)

### Leaflet — CVE-2025-69993 (XSS bindPopup)

- **Bundle:** Leaflet **1.9.4** (etkilenen aralık)
- **Not:** Leaflet maintainers CVE'yi **DISPUTED** — uygulama sanitize etmeli
- **Diplomacia riski:** Harita popup'ına kullanıcı/API metni HTML olarak gidiyorsa stored XSS mümkün; kanıt için popup içeriği trace gerekir
- **Kaynak:** [Leaflet #10214](https://github.com/Leaflet/Leaflet/issues/10214)

### Diğer

| Alan | Durum |
|------|--------|
| JWT `alg:none` | 403 — kapalı (önceki audit) |
| Express/Fastify sürümü | Header'da yok — CVE eşlemesi UNVERIFIED |
| Expo 55 / React 19 | CVE için hedefli `npm audit` backend repo olmadan yapılamaz |

---

## Exploit özeti (yüksek para)

```
# Doğru claim (quest_key ile):
POST /api/quests/work_1/claim   → +5.000
POST /api/quests/work_3/claim   → +20.000
POST /api/quests/work_5/claim   → +50.000 (5/5 work sonrası)

# Yanlış (audit script hatası):
POST /api/quests/{uuid}/claim   → Geçersiz görev
```

**Tek seferlik toplam günlük quest (work serisi):** ~75.000 altın + elmas (replay yok).
