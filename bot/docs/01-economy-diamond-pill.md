# Ekonomi — Elmas / Hap ROI

## Oyuncu gözlemi (operatör)

1. ~3000 elmas → hap craft (`POST /auto/craft-pills` veya market)
2. Hap ile fabrikada çalış (`POST /factories/work`)
3. Her work: **+20 elmas** (elmas fabrikası, Kalemiye +%20 bonus ile daha fazla)
4. 24 saat sonunda harcanan elmasın büyük kısmı geri kazanılır

## API

| Endpoint | Rol |
|----------|-----|
| `GET /auto/status` | `health`, `health_pills`, `pill_cooldown_ms`, `next_work_in_ms` |
| `POST /auto/craft-pills` | Elmas → hap (`{"diamonds": N}`) |
| `POST /auto/use-pills` | Can düşükken hap |
| `POST /factories/work` | `earned.money`, `earned.diamonds`, `earned.xp` |

## Matematik (rehber sabitleri)

| Sabit | Değer |
|-------|-------|
| Altın/work | ~2.404 (Kalemiye +%20 → ~2.885) |
| Elmas/work | ~20 (+ bonus) |
| Hap cooldown | ~600.000 ms (10 dk) |
| Teorik work/gün | ~144 (pratik 100–120) |

**ROI örneği:** 3000 elmas hap'a gitti → 3000/20 = **150 work** ile elmas başabaş (cooldown ve kesintisiz çalışma varsayımı).

## Bot kararı (`economy.py`)

```
if health < threshold AND pills > 0:
    use_pills()
elif pills < min_stock AND diamonds >= craft_batch:
    craft_pills(batch)   # batch = min(available, target_stock_cost)
else:
    work()               # her work +20 elmas
```

## Yapılmayacaklar

- Elmas 0 iken craft zorlama (400 döner)
- Premium olmayan hesapta `auto/toggle` (403)
