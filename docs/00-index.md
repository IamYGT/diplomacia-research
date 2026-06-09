# Diplomacia Research Hub

> Son güncelleme: 2026-06-09  
> Hedef: [diplomacia.com.tr](https://diplomacia.com.tr/)  
> Backend codename: **Strategos** (Railway)

## Doküman haritası

| Dosya | İçerik |
|-------|--------|
| [01-architecture.md](01-architecture.md) | Teknik mimari, stack, auth |
| [02-security-test-plan.md](02-security-test-plan.md) | Pentest planı, JWT, mod/IDOR vektörleri |
| [03-crawl-results.md](03-crawl-results.md) | Authenticated API crawl özeti (52 GET) |
| [04-game-mechanics.md](04-game-mechanics.md) | Oyun modülleri ve ekonomi/savaş/siyaset |
| [api-endpoints.json](api-endpoints.json) | **213** REST endpoint envanteri (`extract_endpoints.py`) |
| [07-exploit-report.md](07-exploit-report.md) | **52 exploit testi** — avantaj/sömürü analizi |
| [08-balance-exploit-report.md](08-balance-exploit-report.md) | **Bakiye artırma** — onboarding API farm + kapalı vektörler |
| [09-reverse-engineering-report.md](09-reverse-engineering-report.md) | **RE + ileri tarama** — factory join, socket, race, top10 leak |
| [10-quest-claim-stack-cve.md](10-quest-claim-stack-cve.md) | Quest claim (`quest_key`), stack sürümleri, CVE |
| [11-audit-summary.md](11-audit-summary.md) | **Full audit özeti** — checkpoint 1–7 konsolidasyon |
| **Public site** | https://diplomacia.ygtlabs.ai/ (nginx static) |
| **İnteraktif rehber** | https://diplomacia.ygtlabs.ai/guide/ — animasyonlu max-verim playbook |
| **İndir** | https://diplomacia.ygtlabs.ai/download/diplomacia-research.tar.gz |
| [../output/exploits/exploit_results.json](../output/exploits/exploit_results.json) | Ham exploit sonuçları |
| [../output/security/findings.json](../output/security/findings.json) | Otomatik güvenlik bulguları |
| [../output/crawl/](../output/crawl/) | Ham API yanıtları (JSON) |

## Hızlı özet

- **Oyuncu sayısı:** ~4974 · **Ülke:** 21 · **Eyalet:** 59 · **Parti:** 409
- **Stack:** Expo/React Native Web + Cloudflare + JWT API + Socket.IO
- **İlk audit:** 48/52 GET OK · **0 CRITICAL** güvenlik bulgusu (normal user token)
- **Mod endpoint'leri:** 403 — "Moderatör yetkisi gerekli" ✅
- **JWT alg:none:** 403 ✅
- **Auth'suz hassas route:** 401 ✅

## Scriptler

```bash
# Tam crawl + güvenlik
python3 /var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/scripts/full_audit.py

# Socket.IO + transfer gate (checkpoint 6)
python3 /var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/scripts/socket_transfer_probe.py

# Scrapling wiki (ayrı)
source /var/www/research/scrapling-venv/bin/activate
python /var/www/research/diplomacia-research/scrape_diplomacia.py
```

## Verify

```bash
bash /var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/scripts/verify-audit.sh
bash /var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/scripts/verify-guide.sh
```

## Tamamlanan (2026-06-09)

- İnteraktif ustalık rehberi (`public/guide/`) + `public/data/guide-meta.json`
- Public hub + CF DNS + tar.gz arşiv

## Checkpoint 4 (2026-06-09)

- `scripts/onboarding_step_probe.py` — complete-step replay güvenli (delta 0)
- `scripts/farm_work_loop.py` — eyalet uyumsuzluğunda leave + yerel fabrika
- Artefaktlar: `output/exploits/onboarding_replay_probe.json`, `farm_work_loop_probe.json`

## Checkpoint 5 (2026-06-09)

- `scripts/extract_endpoints.py` — bundle + `api_catalog` → **213 endpoint** (`docs/api-endpoints.json`)
- Factory IDOR re-probe: `output/reverse/factory_idor_checkpoint5.json` (join açık, withdraw/close korumalı)

## Checkpoint 6 (2026-06-09)

- `scripts/socket_transfer_probe.py` — Socket.IO bağlandı, **33 bundle event**, foreign DM yok
- Transfer: lv4 → lv5 gate aktif, race atlandı, bakiye delta 0
- Artefaktlar: `output/reverse/socket_transfer_checkpoint6.json`, `socket_events_enum.json`

## Checkpoint 7 (2026-06-09)

- `scripts/generate_audit_summary.py` → `output/audit_summary.json`
- [11-audit-summary.md](11-audit-summary.md) — full crawl + security konsolidasyon
- Transfer race: **BLOCKED** (test hesabı lv4, min lv5)

## Checkpoint 8 — DONE (2026-06-09)

- `scripts/verify-audit.sh` — audit completion verify (critical=0, artefacts OK)
- `build_public_site.py` — 11-audit-summary public hub'a sync
- **Goal complete:** crawl + security audit dokümante; 3 açık kalem opsiyonel (lv5+ race, Turnstile, conf_send)

## Opsiyonel sonraki araştırma

1. Transfer race — **Lv5+** hesap ile paralel race
2. Yeni hesap onboarding — Turnstile bypass veya manuel kayıt
