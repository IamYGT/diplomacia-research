# Gerçek Savaş — Bölge Katkısı

## API

| Endpoint | Rol |
|----------|-----|
| `GET /wars` | Aktif savaşlar |
| `GET /wars/my-country` | Ülkenin savaşları |
| `POST /wars/{id}/contribute` | `{"side": "attacker"\|"defender", ...}` |
| `GET /wars/war-targets?from_province=` | Hedef eyaletler |

## Bot config

| Alan | Açıklama |
|------|----------|
| `war_enabled` | true/false |
| `target_war_id` | Sabit savaş UUID (opsiyonel) |
| `target_province` | Bölge adı filtresi |
| `contribute_side` | attacker / defender / auto |

## Akış

1. `init/data` veya `/wars` → aktif savaş listesi
2. Hedef bölge ile eşleşen savaş seç
3. `military/me` → yeterli birim var mı
4. `contribute`

## Premium

Hub hesap: `auto/toggle` war modu ile 24s otomatik katkı.
