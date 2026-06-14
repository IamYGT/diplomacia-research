# Fabrika — Kendi vs Yabancı Fabrika

## Sorun (mevcut bot)

`factory_service.ensure_factory()` her zaman:
1. Eyalette fabrika yoksa **yeni elmas fabrikası kurar** (−10.000 elmas)
2. `prepare_join` eyalet uyumsuzluğunda yine **BotFarm2** kurar

Oyuncu başka bir fabrikada çalışmak istediğinde bot bunu ezer.

## Tasarım

### Hesap config (`account_config`)

| Alan | Açıklama |
|------|----------|
| `work_mode` | `auto` \| `own` \| `foreign` \| `fixed` |
| `preferred_factory_id` | `fixed` modda UUID |
| `allow_auto_build` | false → asla `factories/build` çağırma |
| `province_match_required` | foreign'da false — seyahat sonrası join |

### Mod davranışı

| Mod | Davranış |
|-----|----------|
| `fixed` | Sadece `preferred_factory_id`'ye join → work |
| `foreign` | `GET /factories/region` veya world list → en iyi verimli açık fabrika |
| `own` | `GET /factories/my` — sahip olunan veya eyaletteki |
| `auto` | Eski davranış (geri uyumluluk) — build izinli |

### API

| Endpoint | Rol |
|----------|-----|
| `GET /factories/work-status` | `working: true/false` |
| `POST /factories/leave` | Mevcut fabrikadan ayrıl |
| `POST /factories/join` | `{"factory_id": "uuid"}` — **herhangi açık fabrikaya** (RE: 200) |
| `POST /factories/work` | Çalış |
| `GET /provinces/travel/status` | Seyahat halinde mi |

### Join akışı (yeni)

```
1. work-status → working? leave
2. travel/status → seyahatteyse bekle / skip
3. resolve_factory_id(config) → UUID
4. join(factory_id)
5. bölge hatası + allow_auto_build → build (sadece auto mod)
6. pills → work
```

## Telegram

- `/setfabric <uuid>` — fixed mod
- `/setfabric own` — kendi fabrikası
- `/setfabric auto` — eski davranış
- `/workstatus` — nerede çalışıyor
