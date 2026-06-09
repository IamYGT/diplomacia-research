# Diplomacia — Teknik Mimari

## Genel bakış

```
[Browser/Mobile Web]
    Expo React Native Web SPA (~4.8MB bundle)
         │
         ▼
[Cloudflare] — Turnstile, CSP, HSTS, WAF
         │
         ▼
[diplomacia.com.tr]
    ├── /           → SPA shell
    ├── /api/*      → Strategos REST API (JWT)
    ├── /coats/*    → Ülke arması PNG
    └── Socket.IO   → Realtime (token auth)
         │
         ▼
[strategos-backend-production.up.railway.app] (internal/proxy)
```

## Frontend

- **Framework:** Expo + React Native Web
- **Routing:** React Navigation
- **Harita:** Leaflet.js
- **i18n:** 7+ dil (TR, EN, ES, AR, ID, RU, PT)
- **Push:** Expo notifications (`projectId: 28b49941-...`)

## Auth

| Adım | Mekanizma |
|------|-----------|
| Kayıt/Giriş | Email+şifre veya Google OAuth (`POST /auth/google`) |
| Bot koruması | Cloudflare Turnstile (`POST /auth/verify-turnstile`) |
| Oturum | JWT HS256 → `localStorage.token` |
| API | `Authorization: Bearer <jwt>` |
| Socket | `io(SOCKET_URL, { auth: { token, lang } })` |

### JWT claims

| Claim | Açıklama |
|-------|----------|
| `id` | Oyuncu UUID |
| `username` | Görünen ad |
| `tv` | Token version (session invalidation) |
| `iat` / `exp` | ~7 gün ömür |

Moderatör/kabine yetkisi JWT'de değil — `players/profile` cevabında (`is_moderator`, `cabinet_role`).

## API modülleri (client)

38 modül: auth, players, countries, province, factory, market, war, military, election, party, parliament, cabinet, diplomacy, press, chat, quest, skills, citizenship, visa, transfer, conference, world, upload, block, moderation, mod, auto, trainingWar, militaryOps, economy, xp, passiveSkills

Tam liste: [api-endpoints.json](api-endpoints.json)

## Wiki

Statik HTML: [wiki.diplomacia.com.tr](https://wiki.diplomacia.com.tr/wiki) — 78 mekanik bölümü
