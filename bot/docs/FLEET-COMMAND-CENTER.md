# Filo Komuta Merkezi — Sprint Takip

**Vizyon:** Google hesap → token yapıştır → dokunma. ~20 işçi hesap AOD/Hürmüz'de ana fabrikada çalışır; premium yok; elmas→hap→can→farm; saatte 1 antrenman.

**Sürüm:** 4.26.9 ✅ Faz 4.5–4.16
**Son güncelleme:** 2026-07-01

---

## Faz 1 — İşçi filosu MVP

| # | Epic | Durum | Dosya / kanıt |
|---|------|--------|----------------|
| 1.1 | Fleet factory assign (`/fleetfactory`) | ✅ | `fleet_command.py`, `fleet_command_hooks.py` |
| 1.2 | Kapalı ekonomi döngüsü (hap work CD'den bağımsız) | ✅ | `modules/factory.py`, `modules/orchestrator.py` |
| 1.3 | Worker training sidecar (saatlik saldırı) | ✅ | `jobs/worker_training.py`, cooldown-aware next attempt |
| 1.4 | Fleet bootstrap (`/fleetbootstrap`) | ✅ | `fleet_command.py` |
| 1.5 | Fleet status (fabrika modu satırı) | ✅ | `fleet_command_hooks.py` `/fleetops` |
| 1.6 | `MAX_ACCOUNTS_PER_USER=20` dokümantasyon | ✅ | `.env.example`, bu dosya |
| 1.7 | Unit + integration testler | ✅ | `tests/test_fleet_command.py` |

## Faz 2 — Komuta konsolu

| # | Epic | Durum |
|---|------|--------|
| 2.1 | `/fleet status` detaylı tablo | ✅ | `fleet_status.py`, `/fleetops` |
| 2.2 | Fabrika kapasitesi / worker_count uyarısı | ✅ | `format_factory_capacity_line` |
| 2.3 | `fleet:af:on:hybrid` | ✅ | `fleet_callbacks.py` |
| 2.4 | Token inbox otomatik eşleme | ✅ | `/fleetinbox`, `token_watch.py` |

## Faz 3 — Bölge operasyonları

| # | Epic | Durum |
|---|------|--------|
| 3.1 | Toplu ikamet `/players/residence` | ✅ | `fleet_residence.py`, `/fleetresidence` |
| 3.2 | Seçim oyu | ✅ | `/fleetvote`, `cast_election_vote` |
| 3.3 | Vize / vatandaşlık API | ✅ | `/fleetcitizen`, `/fleetvisa` |
| 3.4 | `/fleetaod` tek komut zinciri | ✅ | `fleet_region_hooks.py` |
| 3.5 | Durable bölge mission (`travel→residence→vote/visa/citizen→farm`) | ✅ | `/fleetregion`, `modules/mission_region.py` |
| 3.6 | Çalışma izni | 🟡 | API registry'de ayrı endpoint yok; keşif bekliyor |

## Faz 4 — Otomasyon & UAT (sıradaki)

| # | Epic | Durum | Not |
|---|------|--------|-----|
| 4.1 | Zamanlanmış autopilot job (yeni hesap gelince) | ✅ | `fleet_inbox_watch.py`, `FLEET_INBOX_AUTO_SETUP` |
| 4.2 | Filo hata runbook (JWT süresi, kapasite dolu, seyahat CD) | ✅ | `/fleethelp`, `/help filo` |
| 4.3 | Canlı UAT — 5→20 hesap kademeli | 🟡 | U1/U2/U4 headless teyit |
| 4.4 | Filo metrik özeti (günlük farm/attack sayacı) | ✅ | `fleet_metrics.py`, `/fleet status` |
| 4.5 | Worker stat queue | ✅ | `jobs/worker_stat_queue.py` |
| 4.6 | Craft→hap→work invariant | ✅ | `test_modules_orchestrator.py` |
| 4.7 | Training cooldown retry scheduler | ✅ | `test_worker_training.py` |
| 4.8 | 20 hesap dry-run goal testi | ✅ | `test_fleet_goal_dryrun.py` |
| 4.9 | Token refresh backoff + Telegram deps | ✅ | `token_refresh_service.py`, `requirements.txt` kurulum teyidi |
| 4.10 | Kolay/program callback fresh panel | ✅ | `telegram_navigation.py`, `telegram_easy.py`, `telegram_mission.py` |
| 4.11 | Training skip görünürlüğü | ✅ | `training_skip` action_log + `/fleet status` 24s bekleme metriği |
| 4.12 | Tek tuş filo autopilot | ✅ | `/fleetstart`, `/fleet start`, panel `▶️ Başlat` |
| 4.13 | Autopilot inbox import | ✅ | `/fleetstart` önce token_inbox import eder |
| 4.14 | Inbox watcher autopilot | ✅ | `FLEET_INBOX_AUTO_SETUP=1` yeni token → autopilot |
| 4.15 | Frontend API keşfi + capability satırı | ✅ | `scripts/discover_frontend_api.py`, `/fleet status` |
| 4.16 | Keşfedilen bölge politikası fazları | ✅ | `independent`, `eyaletoy` opsiyonel mission fazları |

---

## Operatör runbook (20 hesap)

```bash
# 1. Ortam
export MAX_ACCOUNTS_PER_USER=20

# 2. Ana hesap fabrika UUID (coach veya fabrika panelinden)
# 3. Alt hesaplar: token → data/token_inbox/u{uid}_01.jwt …
# 4. Telegram:
/fleetstart Hürmüz vote     # önerilen tek akış: inbox + onar + Hürmüz mission + oy opsiyonu
/fleetbootstrap hybrid      # işçi hesaplara rol + oto açık; ana hesabı atlar
/fleetinbox                 # token_inbox'tan toplu bağla
/fleetfactory main          # ana fabrikaya bağla
/fleettravel Hürmüz         # toplu seyahat
/fleet status               # detaylı komuta tablosu
/fleet audit                # otonomi eksik listesi
/fleet repair               # otonomi eksiklerini otomatik aç
/fleetrepair                # aynı onarımın direkt komutu
/fleetaod                   # tek komut: bootstrap+fabrika+seyahat+ikamet
/fleetregion Hürmüz vote    # kalıcı mission: seyahat+ikamet+oy+farm
/fleetregion Hürmüz independent eyaletoy  # opsiyonel: bağımsız vatandaşlık + eyalet oyu
/fleetresidence Hürmüz      # toplu ikamet
/fleetvote                  # aktif seçime oy
/fleetcitizen               # vatandaşlık başvurusu (ana ülke)
/autofarm on all

# Opsiyonel otomasyon (varsayılan kapalı):
export FLEET_INBOX_AUTO_SETUP=1   # yeni jwt → otomatik autopilot+Telegram özeti

# API keşfi (non-mutating frontend bundle taraması):
python3 scripts/discover_frontend_api.py --show-missing
```

**Filo paneli (v4.26.5):** üst satır `▶️ Başlat | 🇦🇴 AOD | 📋 Durum` → alt menüde fabrika, seyahat, bootstrap, inbox, ikamet, oy.

---

## UAT teyit matrisi

| Adım | Komut / UI | Beklenen | Durum |
|------|------------|----------|-------|
| U1 | `/fleetinbox` | token_inbox dosyaları bağlanır | ✅ `u515491882_ygt1` bağlandı |
| U2 | `/fleetaod` | bootstrap+fabrika+seyahat+ikamet batch OK | 🟡 bootstrap 3/3 — ana fabrika UUID gerekli |
| U3 | `/fleetvote` | aktif seçimde oy veya net hata | 🔲 canlı |
| U4 | `/fleet status` | rol, mod, bakiye, kapasite + 24s metrik | ✅ 2 hesap tablosu |
| U5 | ⚙️ İşlemler menüsü | alt klavye açılır | 🔲 canlı |
| U6 | 20 hesap limit | 21. hesap reddedilir | 🔲 canlı |
| U7 | `worker_training` | cooldown bitince free attack denemesi | ✅ unit, 🔲 canlı |
| U8 | `/fleetregion Hürmüz vote` | kalıcı region mission kuyruğu | ✅ unit, 🔲 canlı |
| U9 | 1 ana + 20 worker dry-run | repair + audit + AOD/region + training | ✅ `test_fleet_goal_dryrun.py` |
| U10 | `/fleetstart Hürmüz vote` | repair + kalıcı region mission tek cevap | ✅ unit, 🔲 canlı |

---

## Teyit matrisi (otomatik test)

- [x] Yeni hesap bağlanınca auto_defaults + autofarm açık
- [x] `/fleetfactory main` tüm alt hesaplarda `work_mode=fixed` + UUID
- [x] Work CD varken düşük canda hap kullanılıyor
- [x] Hap yok + can 0 iken `craft-pills → use-pills → factories/work`
- [x] `worker_training` free_attack_available iken saldırı deniyor
- [x] `worker_training` cooldown ms dönerse next-attempt planlıyor
- [x] `worker_training` no-war/cooldown skip nedenini action_log'a yazar
- [x] İkamet `province_id` fallback (`test_fleet_residence`)
- [x] Durable mission: `citizenship_apply`, `visa_apply`, `election_vote`
- [x] Durable mission: `independent_citizenship`, province scoped `election_vote`
- [x] Frontend bundle API keşfi: `factories.move`, `players.independent-citizenship`,
      `military-ops join/leave`, `provinces/election/vote` registry'ye alındı
- [x] 20 worker dry-run: main skip, repair, audit, AOD/region enqueue, training tick
- [x] Token refresh kaynak yoksa 30 dk backoff; Telegram paketi sistem+venv import OK
- [x] `fleet_ui_markup` + `fleet_callbacks` 350 satır altında
- [x] Targeted tests: fleet missions, region UI, worker training, orchestrator, arch_check

---

## Troubleshooting (Faz 4 taslağı)

| Semptom | Olası neden | Aksiyon |
|---------|-------------|---------|
| İkamet HTTP 400 | Eyalet adı / cooldown | `/fleetresidence Hürmüz` tekrar; `province_id` fallback otomatik |
| Fabrika atama fail | Ana hesapta fabrika yok | Ana hesapta fabrika kur, `/fleetfactory main` |
| Inbox boş | Yanlış dosya adı | `data/token_inbox/u{telegram_uid}_01.jwt` |
| JWT expired | Token süresi | `/loginkaydet` veya yeni token inbox |
| Token refresh tekrar tekrar deniyor | Kaynak yok / login başarısız | Worker hesap bazlı 30 dk backoff yazar; manuel force refresh backoff'u aşar |
| 21. hesap | Limit | `MAX_ACCOUNTS_PER_USER=20` env |
| Çalışma izni yok | API endpoint keşfedilmedi | `api_route_registry.py` güncellenmeden otomasyon ekleme |
| Antrenman saldırmıyor | `/training-wars/my` boş veya cooldown | Worker next-attempt yazar; savaş oluşturma/join endpoint keşfi ayrı |

## API keşif politikası

Operatör Diplomacia domaininde API keşfine izin verdi. Rutin akış:

1. `python3 scripts/discover_frontend_api.py --show-missing`
2. Safe GET route'ları contract/probe ile doğrula.
3. State değiştiren route'ları önce `api_route_registry.py` + replay cassette'e ekle.
4. Endpoint bulunmadan bot ekranında kabiliyeti "hazır" gösterme.

2026-07-01 bundle teyidi: ayrı `work permit/employment` endpointi ve
`training-wars create` endpointi görünmedi; `/fleet status` bunları bekleyen
gelişmiş kabiliyet olarak gösterir.

---

## Mimari patron

Tam belge: `docs/ARCHITECTURE-PATRON.md` · Skill: `diplomacy-bot-architecture`

## Modül haritası (v4.24.0)

```
accounts_picker.py     — /accounts metin + 2 sütun buton
auth.py                — scoped_list_accounts (admin kendi hesapları)
fleet_command.py       — çekirdek batch ops
fleet_status.py        — detay tablo, next steps, AOD footer
fleet_command_hooks.py — Telegram komutları (<220 satır)
fleet_callbacks.py     — inline callback zinciri
fleet_ui_markup.py     — kompakt panel + alt menü
fleet_residence.py     — ikamet, oy, vize, run_aod_setup
fleet_region_hooks.py  — bölge komutları + AOD callback
fleet_region_mission_ui.py — /fleetregion parse + format
fleet_inbox_import.py  — headless inbox bağlama
fleet_inbox_watch.py   — 300s job, otomatik AOD (env ile)
fleet_metrics.py     — 24s farm/antrenman özeti
action_log_query.py  — action_log sayım sorguları
connect_core.py      — ortak hesap bağlama
fleet_help.py        — /fleethelp runbook
domain/fleet_missions.py — AOD/region mission phase planı
modules/mission_region.py — vote/visa/citizen mission fazları
jobs/worker_training.py — cooldown-aware antrenman sidecar
```

---

## Changelog

| Tarih | Sürüm | Not |
|-------|-------|-----|
| 2026-07-01 | 4.26.9 | `independent` ve `eyaletoy` bölge mission opsiyonları |
| 2026-07-01 | 4.26.8 | Frontend API keşif script'i, registry genişletme ve fleet capability satırı |
| 2026-07-01 | 4.26.7 | Inbox watcher ve worker setup artık autopilot zincirini çağırır |
| 2026-07-01 | 4.26.6 | `/fleetstart` token_inbox import + repair + region mission zinciri |
| 2026-07-01 | 4.26.5 | `/fleetstart` autopilot ve panel `▶️ Başlat` |
| 2026-07-01 | 4.26.4 | Training skip action_log + fleet metrics bekleme sayacı |
| 2026-07-01 | 4.26.3 | Kolay/program/onboarding eski callback'lerinde görünür yeni panel fallback |
| 2026-07-01 | 4.26.2 | Telegram paketleri kuruldu, token refresh backoff, token_extract domain helper |
| 2026-07-01 | 4.26.1 | Telegram stale panel fallback, 20 hesap dry-run testi, `/fleetrepair` doküman netliği |
| 2026-07-01 | 4.26.0 | durable `/fleetregion`, mission region phases, training cooldown scheduler, craft→hap→work test |
| 2026-06-30 | 4.25.0 | M0 bootstrap.py, main sırası, dashboard token-dead fix, arch_check |
| 2026-06-30 | 4.24.0 | token_db — DB tek kaynak, inbox consume |
| 2026-06-30 | 4.23.3 | /accounts canlı bakiye + ~ stale + 🔑 token uyarısı |
| 2026-06-30 | 4.23.2 | stale import fix — accounts_screen + consumer rebind |
| 2026-06-30 | 4.23.1 | /accounts fix — admin scope, accounts_picker UI, test_accounts_picker |
| 2026-06-30 | 4.23.0 | Faz 4.4 metrikler, atomic inbox state, UAT U1/U4 |
| 2026-06-30 | 4.20.1 | UI split, ikamet fallback, UAT matrisi, press replay |
| 2026-06-30 | 4.20.0 | Faz 3 — ikamet, seçim oyu, vatandaşlık/vize, /fleetaod |
| 2026-06-30 | 4.19.0 | Faz 2 — detay tablo, kapasite uyarısı, hybrid oto, inbox import |
| 2026-06-30 | 4.18.0 | Faz 1 tamamlandı — filo komuta, hap CD fix, training watch |
