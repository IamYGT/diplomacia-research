# Hesap State Machine

## Durumlar

```
IDLE → TRAVELING → WORKING → COOLDOWN → IDLE
         ↓
      WAR_CONTRIB
         ↓
      TRAINING_ATTACK
```

## DB: `account_config`

| Kolon | Tip | Default |
|-------|-----|---------|
| account_name | TEXT PK | |
| role | TEXT | `farmer` |
| work_mode | TEXT | `own` |
| preferred_factory_id | TEXT | null |
| allow_auto_build | INT | 0 |
| stat_priority_json | TEXT | `["kisla",...]` |
| war_enabled | INT | 0 |
| target_war_id | TEXT | null |
| training_enabled | INT | 1 |
| is_premium_hub | INT | 0 |

## Geçiş kuralları

- `TRAVELING`: `provinces/travel/status` → iş yok
- `WORKING`: `work-status.working` → leave önce join
- `COOLDOWN`: `next_work_in_ms` > 0 → training/stats yapılabilir

## Telegram persistence

`/config` — JSON dump  
`/setmode work foreign` — work_mode güncelle
