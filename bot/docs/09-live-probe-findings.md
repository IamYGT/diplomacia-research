# Canlı probe bulguları (ygt @ 2026-06-14)

## Hesap: ygt (premium hub adayı)

| Alan | Değer |
|------|-------|
| Sınıf | kalemiye (probe: vergi_uzmani pasif) |
| Eyalet | Hürmüz |
| Premium | evet |
| Pasif puan | 7 (harcanmamış) |
| Hap | 2679 |
| Work cooldown | 0 (hazır) |
| Free attack | hazır |
| Training war | yok (404) |
| Aktif savaş | 5 (ülke) |
| Fabrika (own) | `26ce706f-fb32-429b-8f48-1f36e0703119` |

## Oyun öğrenmeleri

1. **Pasif skill ≠ aktif skill** — `kisla` aktif profilde; pasif API anahtarı `vergi_uzmani` (kalemiye)
2. **Training war** — `/training-wars/my` 404 = antrenman savaşı yok; free_attack yine de true olabilir
3. **Premium** — `auto/toggle` eyalet dışındayken 403; manuel orchestrator work foreign ile çalışır
4. **Eyalet uyumu** — `own` mod Tahran fabrikası + Hürmüz oyuncu = join hatası; `foreign` veya seyahat gerekli

## Bot aksiyonları

- `CLASS_STAT_PRIORITY` eklendi (kalemiye → vergi_uzmani)
- `module_probe.py` — modül snapshot
- Test sayısı: 29

## Komut

```bash
python3 scripts/module_probe.py ygt --json
python3 scripts/module_probe.py ygt --tick   # state değiştirir
```
