# Diplomacia Engagement — Repo Entegrasyonu

Pentest logları `scripts/sync_engagement.py` ile buraya bağlanır.

## Dizinler

| Yol | Kaynak |
|-----|--------|
| `intel/merged.json` | findings + knowledge_pool + manifest birleşimi |
| `pentest/` | symlink → `~/pentest-logs/engagements/diplomacia` |
| `raw/` | symlink → `~/pentest-logs/raw/diplomacia` |
| `docs/` | symlink → engagement docs (wave logları) |

## Sync

```bash
python3 scripts/sync_engagement.py
```

Bot `DIPLOMACIA_INTEL` env ile `intel/merged.json` okur.
