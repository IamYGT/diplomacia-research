# Diplomacy Bot — Mimari Patron (Python)

**Sürüm:** 1.0 · **Tarih:** 2026-06-30 · **Durum:** Hedef mimari (kademeli migrasyon)

Operatör kararı: **Python'da kal, mimariyi düzelt.** Dil değiştirme yok.

---

## 1. Problem özeti (mevcut)

| Sorun | Kök neden |
|-------|-----------|
| Stale import / hook | `main.py` önce bootstrap → sonra telegram |
| Token çift kaynak | DB + `token_inbox` dosyaları (kısmen düzeltildi v4.24) |
| 280+ dosya karmaşası | UI + domain + infra aynı pakette |
| `store.py` 498 satır | ✅ 78 satır facade (`adapters/sqlite/*`) |
| Monkey-patch hook | ✅ `bootstrap/registry` explicit wiring |

---

## 2. Hedef: 4 katman + 2 process

```
┌─────────────────────────────────────────────────────────┐
│  PROCESS A: diplomacy-telegram (PTB long-poll)          │
│  telegram/handlers · formatters · keyboards             │
└──────────────────────────┬──────────────────────────────┘
                           │ çağrı (sync/async facade)
┌──────────────────────────▼──────────────────────────────┐
│  DOMAIN (saf Python — Telegram/import yok)              │
│  accounts · fleet · farm · war · travel · tokens        │
└──────────────────────────┬──────────────────────────────┘
                           │ ports (Protocol)
┌──────────────────────────▼──────────────────────────────┐
│  ADAPTERS                                               │
│  sqlite_repo · diplomacia_api · tor_stealth · gemini    │
└──────────────────────────┬──────────────────────────────┘
                           │
                    data/accounts.db

┌─────────────────────────────────────────────────────────┐
│  PROCESS B: diplomacy-worker (APScheduler / asyncio)    │
│  autofarm_tick · fleet_batch · token_refresh · inbox     │
└─────────────────────────────────────────────────────────┘
```

**Kural:** Domain katmanı `telegram`, `telegram.ext` import **etmez**.

---

## 3. Paket yapısı (hedef dizin)

```
bot/diplomacy_bot/
  bootstrap.py           # Tek wiring — hook YOK
  config.py
  domain/
    accounts.py          # scope, resolve, main account
    tokens.py            # token_db taşınır
    fleet.py             # batch ops orchestration
    farm.py              # tick, quick farm
    snapshot.py          # dynamic_context özü
  ports/
    game_client.py       # Protocol: profile, work, travel…
    account_repo.py      # Protocol: get/save/list accounts
    token_store.py
    snapshot_cache.py
  adapters/
    sqlite/
      accounts.py        # store.py parçası (<300 satır)
      config.py
      snapshots.py
      secrets.py         # account_credentials
      action_log.py
    http/
      game_api.py        # stealth_client + contract validate
      route_registry.py
    telegram/            # ince — sadece adapter değil UI
      handlers/
      screens/           # accounts_screen, dashboard_screen
      formatters/        # accounts_picker, dashboard_html
      keyboards/
  jobs/
    autofarm.py
    fleet_inbox_watch.py
    token_refresh.py
  ai/
    intent_router.py
    agent.py
```

**Mevcut dosyalar** kademeli taşınır; big-bang rewrite yok.

---

## 4. Sınır kuralları (HARD)

### 4.1 Dosya boyutu
- **Max 300 satır** / dosya (test hariç)
- Aşarsa: alt modül aç, `__init__.py` re-export

### 4.2 Import yönü (acyclic)

```
telegram → domain → ports ← adapters
                ↑
              jobs → domain
```

- ❌ `domain` → `telegram`
- ❌ `adapters/sqlite` → `telegram`
- ❌ `from telegram_ui import format_X` modül üstünde (handler'larda lazy veya `screens/`)

### 4.3 Tek kaynak gerçekleri

| Veri | Tek yazma | Tek okuma |
|------|-----------|-----------|
| JWT | `domain.tokens.persist()` | `domain.tokens.get()` |
| Bakiye gösterim | `account_balance.refresh()` | `account_balance.display()` |
| Aktif hesap | `bot_sessions` + context | `domain.accounts.default_for_user()` |
| API çağrısı | `adapters.http.game_api` | contract validate zorunlu |

### 4.4 Bootstrap (hook yerine)

```python
# bootstrap.py — main.py SIRASI
def create_app():
    install_bootstrap()      # 1. adapters wire
    from diplomacy_bot.adapters.telegram.app import build_application
    return build_application()
```

`main.py` düzeni:

```python
install_bootstrap()                    # ÖNCE
from diplomacy_bot.adapters.telegram.app import run
run()
```

**Yasak:** `runtime_install.install_all_runtime_hooks()` monkey-patch.

### 4.5 token_inbox

- **Geçici kuyruk** — import sonrası `consume_inbox_for_account()` ile sil
- Runtime **asla** dosyadan token okumaz

---

## 5. Domain modül sözleşmeleri

### `domain.accounts`
```python
def list_for_user(telegram_user_id: int) -> list[Account]: ...
def resolve(name: str, telegram_user_id: int) -> Account | None: ...
def set_active(telegram_user_id: int, name: str) -> None: ...
```

### `domain.tokens`
```python
def persist(name: str, jwt: str, *, telegram_user_id: int) -> Account: ...
def get(name: str) -> str: ...
def refresh_if_needed(acc: Account) -> RefreshResult: ...
```

### `domain.fleet`
```python
async def run_batch(op: FleetOp, *, telegram_user_id: int) -> FleetBatchResult: ...
```

### `domain.snapshot`
```python
def get_live(acc: Account, *, force: bool = False) -> dict: ...
def invalidate(name: str) -> None: ...
```

Token expired → snapshot `error` + UI **token recovery ekranı**; stale cache gösterme.

---

## 6. Test piramidi

| Katman | Araç | Örnek |
|--------|------|-------|
| Domain unit | pytest | `test_domain_tokens.py` |
| Contract | pytest + fixtures | `api_route_contract` |
| Adapter integration | pytest + temp DB | `test_sqlite_accounts.py` |
| Telegram | harness mock Update | `telegram_harness.py` |
| E2E smoke | `live_health_probe.py` | staging only |

**Sıra:** Contract → test (kırmızı) → kod (Contract Before Code).

---

## 7. Migrasyon fazları

| Faz | İş | Done kriteri |
|-----|-----|--------------|
| **M0** | `bootstrap.py` + main sırası | Hook'suz açılış, testler geçer |
| **M1** | `token_db` → `domain/tokens` | inbox consume, tek yazma yolu |
| **M2** | `accounts_screen` + picker → `telegram/screens` | stale import yok |
| **M3** | `store.py` → `adapters/sqlite/*` | store.py <100 satır facade |
| **M4** | `runtime_install` sil | 0 monkey-patch |
| **M5** | `diplomacy-worker` process | autofarm PM2 ayrı |
| **M6** | `dashboard_publish` token-expired fix | stale fallback yok |
| **M7** | `autofarm_delivery` tek kaynak | worker + bot aynı HTTP push |
| **M8** | PTB job explicit wiring | `jobs/autofarm_telegram_job.py` |
| **M9** | Tüm PTB jobs → `jobs/*` | stat_queue + press_like wired |
| **M10** | `handlers/` + registry | onboarding + job stubs |
| **M11** | `handlers/cmd_accounts` | accounts/add/remove/status |

**Mevcut durum (2026-06-30):** M0–M11 ✅ · **Sıradaki:** `handlers/cmd_farm.py`

---

## 8. Yeni feature checklist

Yeni kod eklerken agent şunu doğrular:

- [ ] Hangi katman? (domain / adapter / telegram / job)
- [ ] Dosya <300 satır mı?
- [ ] Import yönü ihlal ediyor mu?
- [ ] DB tek kaynak mı?
- [ ] Contract test var mı? (API ise zorunlu)
- [ ] `scoped_list_accounts` kullanıldı mı? (multi-tenant)

---

## 9. Anti-pattern listesi

| ❌ Yapma | ✅ Yap |
|---------|--------|
| `runtime_install` patch | `bootstrap.py` registry |
| `telegram_helpers` üstünden `format_*` import | `screens/*.py` lazy |
| `last_balance` UI'da doğrudan | `account_balance` |
| `list_accounts()` operatör UI'da | `scoped_list_accounts()` |
| `store.py` 50+ satır ekleme | `adapters/sqlite/new_module.py` |
| Inbox'tan runtime okuma | DB + consume on import |

---

## 10. Referans harita (mevcut → hedef)

| Mevcut | Hedef |
|--------|-------|
| `connect_core.py` | `domain/tokens.py` |
| `token_db.py` | `domain/tokens.py` |
| `auth.py` | `domain/accounts.py` |
| `fleet_command.py` | `domain/fleet.py` |
| `dynamic_context.py` | `domain/snapshot.py` |
| `game_api.py` | `adapters/http/game_api.py` |
| `store.py` | `adapters/sqlite/*` |
| `telegram_app.py` | `adapters/telegram/handlers/` |
| `runtime_install.py` | **sil** → `bootstrap.py` |
| `accounts_picker.py` | `telegram/formatters/accounts.py` |

---

*Patron: operatör onayı 2026-06-30. Agent bu belgeye aykırı PR önermez.*
