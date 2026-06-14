# 24 Saat Zamanlayıcı

## Tick modeli

Her hesap için `orchestrator.tick(account)` — autofarm job bunu çağırır (eski `run_farm` yerine).

```
tick():
  1. stats.spend_if_available()      # ~0ms, öncelik
  2. premium.sync_auto_modes()       # hub only
  3. training.attack_if_ready()      # free_attack_available
  4. war.contribute_if_configured()   # opsiyonel
  5. economy.work_cycle()            # pills + work
  6. log snapshot
```

## Zaman kısıtları

| Kaynak | API alanı | Bekleme |
|--------|-----------|---------|
| Work | `auto/status.next_work_in_ms` | Cooldown bitene kadar skip |
| Hap | `pill_cooldown_ms` | craft/use sonrası |
| Training | `free_attack_cooldown_ms` | 1 saat |
| Autofarm interval | `AUTOFARM_INTERVAL_SEC` | 620s default |

## Paralel hesaplar

- Sıralı tick (proxy stagger) — `stagger_farm_sec`
- Aynı anda max 1 worker (`max_concurrent_workers`)

## Günlük hedef metrikleri

| Metrik | Hedef |
|--------|-------|
| Work döngüsü | ~100–120/gün |
| Elmas net | ≥ 0 (ROI pozitif) |
| Pasif stat | `available_points` = 0 |
| Training attack | free cooldown boşken at |
