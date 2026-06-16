# SQLite kalıcılık katmanı

Bot `data/accounts.db` üzerinde SQLite kullanır (WAL mode).

## Tablolar

| Tablo | Amaç |
|-------|------|
| `accounts` | JWT (şifreli), proxy, autofarm |
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

## Güvenlik

- JWT `accounts.token` kolonunda **düz metin** (`eyJ…`) saklanır — basit okuma/yedekleme.
