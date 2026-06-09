# Diplomacia — Full Crawl + Security Audit Özeti

**Tarih:** 2026-06-09  
**Hedef:** [diplomacia.com.tr](https://diplomacia.com.tr/)  
**Generator:** `scripts/generate_audit_summary.py` → `output/audit_summary.json`

---

## Sonuç (tek cümle)

Normal kullanıcı token ile **0 CRITICAL** bulgu; mod/JWT/auth katmanları sağlam; ekonomi exploit'leri replay/race ile kapalı; Socket.IO'da foreign DM yok; transfer race **Lv5+ hesap olmadan test edilemedi**.

---

## Kapsam matrisi

| Alan | Script | Sonuç | Kanıt |
|------|--------|-------|-------|
| GET crawl (52) | `full_audit.py` | 48/52 OK | `output/crawl/` |
| JWT / mod / auth | `full_audit.py` | 0 CRITICAL | `output/security/findings.json` |
| Exploit mutation (52) | `exploit_probe.py` | P1 IDOR read | `07-exploit-report.md` |
| Bakiye farm | `balance_exploit_probe.py` | Onboarding replay kapalı | `08-balance-exploit-report.md` |
| Onboarding replay | `onboarding_step_probe.py` | delta 0 | `onboarding_replay_probe.json` |
| Factory IDOR | `reverse_probe` / cp5 | exploited 0 | `factory_idor_checkpoint5.json` |
| Endpoint envanter | `extract_endpoints.py` | **213** route | `api-endpoints.json` |
| Socket.IO | `socket_transfer_probe.py` | connect OK, foreign_dm false | `socket_transfer_checkpoint6.json` |
| Transfer race | `socket_transfer_probe.py` | **BLOCKED** lv4&lt;lv5 | aynı artefakt |

---

## Güvenlik — kapalı vektörler ✅

- Auth'suz hassas route → **401**
- JWT `alg:none` → **403**
- Mod/moderation → **403** (normal user)
- Onboarding step replay → `success: false`, bakiye delta **0**
- Factory withdraw/close/rename (rakip) → **403/404**
- Transfer (lv4) → **403** min seviye 5
- Socket foreign DM sniff → **false**

---

## Bilinen avantajlar (oyun tasarımı / P2)

| Bulgu | Etki | Replay |
|-------|------|--------|
| Onboarding step API (yeni hesap) | ~250k tek sefer | Kapalı |
| `GET /factories/player/{uuid}` | Rakip fabrika istihbaratı | N/A |
| `POST /factories/join` (açık fabrika) | İşçi katılımı | Tasarım |
| Global chat history | Herkese açık mesajlar | Kasıtlı |

---

## Açık test kalemleri

1. **Transfer paralel race** — Lv5+ hesap gerekli (Ercan2 şu an lv4)
2. **Yeni hesap step-skip** — Cloudflare Turnstile kayıt engeli
3. **conf_send** yetkisi — aktif konferans üyeliği ile tekrar

---

## Checkpoint zaman çizelgesi

| CP | İçerik |
|----|--------|
| 1–3 | Crawl, exploit, RE, IDOR |
| 4 | Onboarding replay + farm eyalet fix |
| 5 | 213 endpoint dump + factory IDOR |
| 6 | Socket.IO + transfer lv5 gate |
| 7 | Bu özet + `audit_summary.json` |
| 8 | `verify-audit.sh` + public site sync — **AUDIT COMPLETE** |

---

## Komutlar

```bash
python3 scripts/generate_audit_summary.py
python3 scripts/full_audit.py
python3 scripts/socket_transfer_probe.py
python3 scripts/extract_endpoints.py
```
