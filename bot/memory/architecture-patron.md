# Memory — Diplomacy Bot Mimari Patron

**Kayıt:** 2026-06-30
**Operatör talimatı:** "Mimari patron sensin — Python için en iyi mimari, memory + skill"

## Özet kararlar

1. **Python'da kal** — rewrite yok
2. **4 katman:** telegram → domain → ports ← adapters
3. **2 process:** telegram (PTB) + worker (autofarm/filo/token)
4. **DB tek kaynak:** `accounts.token`, `account_secrets`; inbox geçici kuyruk
5. **Hook'ları kaldır** → `bootstrap.py` explicit wiring
6. **Max 300 satır/dosya** — `store.py` ve `telegram_app.py` split zorunlu
7. **Contract-first** API değişiklikleri

## Skill

`~/.claude/skills/tier-3-domain/diplomacy-bot-architecture/SKILL.md`

## Tam belge

`bot/docs/ARCHITECTURE-PATRON.md`

## Migrasyon durumu

- ✅ M0 bootstrap.py + main sırası (v4.25.0)
- ✅ token_db, accounts_screen, account_balance, inbox consume (v4.24)
- ✅ dashboard token-expired stale skip (v4.25.0)
- ✅ M4 domain_registry + runtime_install silindi (v4.26.7)
- ✅ M7 autofarm_delivery (v4.26.8)
- ✅ M8 explicit PTB job wiring (v4.26.9)
- ✅ M9 tüm PTB jobs → jobs/* (v4.27.0)
- ✅ M10 handlers/ onboarding + registry (v4.27.1)
- ✅ M11 handlers/cmd_accounts (v4.27.2)
- ⏳ handlers/cmd_farm dilimi

## Agent davranışı

Yeni kod önerirken ARCHITECTURE-PATRON'a aykırı diff **reddet/ düzelt**.
Bootstrap `hooks/` veya `domain_registry` kullan — monkey-patch yasak.

## Operatör API keşif izni

**Kayıt:** 2026-07-01

Operatör Diplomacia domaininde API keşfine izin verdi. Yeni fleet/worker davranışı
tasarlarken sık sık `https://diplomacia.com.tr/` frontend bundle'ı, wiki snapshot ve
`https://diplomacia.com.tr/api` safe GET/contract probe kaynaklarını kontrol et.

Güvenli çizgi:

- Statik HTML/JS bundle ve wiki keşfi serbest.
- Safe GET endpointleri düşük rate ile probelenebilir.
- State değiştiren endpointler önce `api_route_registry.py` + replay/contract'a
  eklenir; canlı mutating probe yalnız kontrollü token ve açık amaçla yapılır.
- Endpoint keşfedilmeden çalışma izni/antrenman savaşı oluşturma gibi kabiliyetleri
  botta hazır göstermeyeceksin.
