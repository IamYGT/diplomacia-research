# Stat — Pasif Skill Önceliği

## Neden kritik

Profilde `skills` (aktif: kisla, bilim_insani…) ve `passive_skills` / `passive_skill_points` ayrı.
**Pasif stat puanları birikir; harcanmazsa kayıp.**

## API

| Endpoint | Rol |
|----------|-----|
| `GET /players/passive-skills` | `available_points`, `passive_skills` |
| `POST /players/passive-skills/spend` | `{"skill": "...", "points": N}` |
| `POST /players/skills/upgrade` | Aktif skill (`kisla`, type: `gold`/`diamond`) |
| `GET /players/profile` | `skills`, `passive_skill_points` snapshot |

## Öncelik sırası (varsayılan — config ile değişir)

1. **Kışla becerisi** (`kisla`) — askeri güç, antrenman/savaş
2. **Savaş teknikleri** (`savas_teknikleri`)
3. **Bilim insanı** (`bilim_insani`) — araştırma
4. Sınıfa göre: Kalemiye → ekonomi pasifleri

## Bot tick

Her orchestrator döngüsünde **önce** stat kontrol:

```
points = get_passive_skills().available_points
if points > 0:
    spend(next_priority_skill, points)
```

## Çoklu hesap

Stat puanı hesap başına bağımsız — her hesap kendi `stat_priority` listesini taşır.
