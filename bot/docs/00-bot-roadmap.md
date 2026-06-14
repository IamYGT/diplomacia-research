# Diplomacia Bot v3 — Yol Haritası

## Vizyon

Bot tek bir "farm döngüsü" değil; **24 saatlik oyuncu simülasyonu** yapmalı:

| Kanal | Süre | Öncelik |
|-------|------|---------|
| Fabrika çalışması | 24s (hap cooldown ile) | Altın + elmas ROI |
| Pasif stat (skill point) | Sürekli birikir | **En değerli** — boşa gitmemeli |
| Antrenman savaşı | 24s | Ücretsiz saldırı gücü |
| Gerçek savaş katkısı | Savaş aktifken | Bölge hedefi |
| Premium auto | Sadece hub hesap | `auto/work` + `auto/war` |

## Modül haritası

| Dosya | Modül | Durum |
|-------|-------|-------|
| [01-economy-diamond-pill.md](01-economy-diamond-pill.md) | Elmas → hap → +20 elmas/work ROI | Spec + kod |
| [02-factory-work.md](02-factory-work.md) | Kendi / yabancı fabrika, sezgisel join | Spec + kod |
| [03-stats-passive-skills.md](03-stats-passive-skills.md) | Pasif stat harcama önceliği | Spec + kod |
| [04-training-war.md](04-training-war.md) | 24s antrenman | Spec + kod |
| [05-war-contribute.md](05-war-contribute.md) | Bölgesel savaş katkısı | Spec |
| [06-premium-hub.md](06-premium-hub.md) | Tek premium, çok hesap | Spec |
| [07-24h-scheduler.md](07-24h-scheduler.md) | Paralel zamanlayıcı | Spec + kod |
| [08-account-state.md](08-account-state.md) | Hesap state machine | Spec + kod |

## Kod dizini

```
diplomacy_bot/modules/
  economy.py      # elmas/hap kararı
  factory.py      # fabrika join (yabancı destekli)
  stats.py        # passive-skills spend
  training.py     # training-wars
  war.py          # wars/contribute
  premium.py      # auto/status, toggle
  scheduler.py    # 24h döngü planlayıcı
  orchestrator.py # tek tick: tüm modüller
```

## Fazlar

1. **Faz A (şimdi):** Dokümantasyon + factory fix + orchestrator iskelet
2. **Faz B:** Stat modülü + scheduler
3. **Faz C:** Training + war + premium hub
4. **Faz D:** Telegram komutları (`/plan`, `/setfabric`, `/setstat`)
