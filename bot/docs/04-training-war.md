# Antrenman Savaşı — 24 Saat

## Mekanik

- `GET /training-wars/my` — aktif antrenman savaşı (yoksa 404)
- `POST /training-wars/{id}/attack` — saldırı (ücretsiz cooldown: `auto/status.free_attack_*`)

## auto/status alanları

```json
{
  "free_attack_available": true,
  "free_attack_cooldown_ms": 3600000,
  "auto_war_active": false,
  "auto_war_until": null
}
```

## 24 saat dengesi

| Aktivite | Paralel? | Not |
|----------|----------|-----|
| Fabrika work | Evet | Hap cooldown ~10dk aralık |
| Training attack | Evet | Saatlik free attack + aktif training war |
| Pasif stat spend | Evet | Anlık, work arasında |

Bot **work beklerken** training attack atabilir (scheduler slot).

## Premium hub

Premium hesapta `POST /auto/toggle` `mode: war` → 24s auto_war (sadece hub).

Alt hesaplar: manuel `training-wars/.../attack` + `wars/.../contribute`.
