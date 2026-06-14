# Premium Hub — Tek Premium, Çok Hesap

## Operatör stratejisi

- **Bir** hesapta premium satın alındı (IAP veya elmas)
- Diğer hesaplara premium **alınmayacak**
- Hub hesap premium özelliklerini kullanır: `auto/work`, `auto/war`, `craft-pills` otomasyonu

## API

| Endpoint | Premium? |
|----------|----------|
| `POST /auto/toggle` | Evet (403 normal) |
| `GET /auto/status` | Hayır |
| `POST /players/diamonds/gift-premium` | Hub → alt? (iş kuralı doğrulanmalı) |

## Bot modeli

```yaml
accounts:
  ercan2:  # hub
    role: premium_hub
    auto_work: true
    auto_war: true
  alt01:
    role: farmer
    auto_work: false  # manuel orchestrator
  alt02:
    role: farmer
```

## `is_premium` kontrolü

`GET /players/profile` → `is_premium`, `premium_until`, `premium_days_left`

Premium değilse `auto/toggle` çağrılmaz — orchestrator manuel work döngüsü.

## Gelecek: gift-premium

Alt hesaba premium hediye **istenmiyor** (maliyet). Hub sadece kendi auto modunu kullanır.
