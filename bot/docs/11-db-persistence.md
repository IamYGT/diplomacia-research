# SQLite kalıcılık katmanı

Bot `data/accounts.db` üzerinde SQLite kullanır (WAL mode).

## Tablolar

| Tablo | Amaç |
|-------|------|
| `accounts` | JWT (`token`), `token_exp_at`, proxy, autofarm |
| `account_secrets` | Şifreli email/şifre (otomatik login) |
| `account_config` | Rol, fabrika modu, savaş ayarları |
| `game_snapshots` | Panel özeti — restart sonrası anında gösterim |
| `action_log` | Farm, connect, autofarm kayıtları |
| `bot_sessions` | Telegram kullanıcı → aktif hesap |
| `schema_migrations` | Şema sürümü |

## Ortam

```env
SNAPSHOT_CACHE_TTL_SEC=20
SNAPSHOT_STALE_SEC=90
```

## Migration

`init_db()` → `db_migrate.run_migrations()` sıralı uygular. Manuel müdahale gerekmez.

## Token kaynağı (tek doğruluk: DB)

| Katman | Rol |
|--------|-----|
| `accounts.token` | **Runtime kaynak** — tüm API çağrıları buradan |
| `account_secrets` | Opsiyonel otomatik login (Fernet şifreli) |
| `data/token_inbox/*.jwt` | **Geçici import kuyruğu** — `/fleetinbox` veya `connect` sonrası DB'ye yazılır ve dosya silinir |
| `import-auth.json` | Yalnızca boş DB bootstrap (ilk kurulum) |

Modül: `token_db.py` → `get_stored_token()`, `persist_account_token()`

## Güvenlik

- JWT `accounts.token` kolonunda **düz metin** (`eyJ…`) saklanır — basit okuma/yedekleme.
