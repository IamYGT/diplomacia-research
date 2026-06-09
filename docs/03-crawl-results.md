# Authenticated Crawl Sonuçları

**Tarih:** 2026-06-09  
**Hesap:** Ercan2 (kalemiye, Bükreş bağımsız)  
**Script:** `scripts/full_audit.py`

## Özet

| Metrik | Değer |
|--------|-------|
| GET endpoint test | 52 |
| HTTP 200 | 48 |
| HTTP 400 (beklenen) | 3 |
| HTTP 403/404 | 1 |

## Başarısız / beklenen hatalar

| Endpoint | Status | Not |
|----------|--------|-----|
| `/players/blocked` | 400 | Muhtemelen query/body gerekli |
| `/wars/war-targets` | 400 | `?from_province=` zorunlu |
| `/training-wars/my` | 404 | Aktif training war yok |
| `/moderation/reports/count` | 403 | Normal user — doğru |

## Dünya snapshot (world/summary)

- 4974 oyuncu, 21 ülke, 59 eyalet, 19 bağımsız bölge
- 3 aktif savaş, 41 ittifak, 409 parti, 3025 fabrika
- Events: war_declared, war_ended, alliance_formed, embargo_imposed

## Önemli endpoint yanıt yapıları

### init/data
`factories`, `work_status`, `active_wars`, `ended_wars`, `world_summary`, `travel_status`

### military/me
`barracks`, `units`, `military_power`, `unit_config`

### auto/status
`auto_work_active`, `auto_war_active`, `health`, `health_pills`, `province_resource_limit`

### market
`listings`, `total` — açık pazar emirleri

### press
`articles`, gazete sistemi + `guides` rehber makaleleri

Ham JSON: `output/crawl/*.json`
