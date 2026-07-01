# Filo Komuta Merkezi — Sprint Takip

**Vizyon:** Google hesap → token yapıştır → dokunma. ~20 işçi hesap AOD/Hürmüz'de ana fabrikada çalışır; premium yok; elmas→hap→can→farm; saatte 1 antrenman.

**Sürüm:** 4.28.29 ✅ Faz 4.5–4.56
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
| 1.6 | `MAX_ACCOUNTS_PER_USER=20` worker limiti | ✅ | Ana hesap varsa toplam kapasite 21: 1 main + 20 worker |
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
| 4.17 | Filo sonuç navigasyonu | ✅ | Her sonuçta `Durum / Başlat / İşlemler / Ana panel` |
| 4.18 | Sade filo ana paneli | ✅ | Ana ekranda sadece başlat/durum/AOD/işlemler + hesap rolü |
| 4.19 | Sade işlemler menüsü | ✅ | Duplicate `Hybrid/Bootstrap` ayrımı kaldırıldı |
| 4.20 | Mission plan görünürlüğü | ✅ | Region/autopilot sonuçları gerçek faz planını gösterir |
| 4.21 | Boş autopilot rehberi | ✅ | Worker yoksa token_inbox dosya yolu gösterilir |
| 4.22 | Boş status rehberi | ✅ | `/fleet status` gerçek `u{uid}_01.jwt` yolunu gösterir |
| 4.23 | Fabrika eksik uyarısı | ✅ | Region/autopilot sonucu ana fabrika UUID eksikse uyarır |
| 4.24 | Filo menü tazeliği | ✅ | Eski `İşlemler/Ana panel` butonu yeni görünür panel açar |
| 4.25 | Training bekleme görünürlüğü | ✅ | `/fleet status` sıradaki antrenman denemesi bekleyen hesap sayısını gösterir |
| 4.26 | API keşif kabiliyet özeti | ✅ | Keşif çıktısı work/permit ve training aday route sayılarını gösterir |
| 4.27 | Inbox retry güvenliği | ✅ | Başarısız token import processed işaretlenmez, sonraki tur tekrar denenir |
| 4.28 | Autopilot hedef politikası | ✅ | Argümanlı `/fleetstart`/`/fleetregion` sonraki otomatik token hedefini kaydeder |
| 4.29 | Filo menü edit/reply kuralı | ✅ | Eski menü yeni mesaj açar, yeni menü yerinde güncellenir |
| 4.30 | Worker darboğaz özeti | ✅ | `/fleet status` hazır değil/runtime/training skip sebeplerini tek satır özetler |
| 4.31 | Permit API keşif kapsamı | ✅ | Discovery `/employment` ve `/work-permits` aday path'lerini de tarar |
| 4.32 | Eski işlem butonu koruması | ✅ | Eski `Başlat/AOD` result butonları yan etkili işlem üretmeden güncel panele yönlendirir |
| 4.33 | Fleetstart command UAT | ✅ | `/fleetstart Hürmüz vote` handler policy kaydı + cevap üretimi testli |
| 4.34 | Eski alt-menü işlem koruması | ✅ | Eski `Fabrika/Hürmüz/Inbox/Hazırla/Onar` butonları işlem çalıştırmadan güncel panele yönlendirir |
| 4.35 | Başlat hedefi görünürlüğü | ✅ | `/fleet status` kayıtlı autopilot hedefini ve bekleyen inbox token sayısını gösterir |
| 4.36 | Eski bölge işlem koruması | ✅ | Eski `İkamet/Oy ver` butonları işlem çalıştırmadan güncel panele yönlendirir |
| 4.37 | Mission farm hap hazırlığı | ✅ | Region/AOD farm fazı work öncesi elmas→hap hazırlığını normal tick ile eşitler |
| 4.38 | Token-aware inbox processed key | ✅ | Aynı `u{uid}_NN.jwt` slotuna yeni JWT konursa otomatik import yeniden çalışır |
| 4.39 | Ana + 20 worker limiti | ✅ | Main hesap tanımlıysa 20 worker eklenebilir; 22. toplam hesap reddedilir |
| 4.40 | Training attack retry normalizasyonu | ✅ | Attack endpoint cooldown/HTTP hata döndürürse worker retry zamanı yazar |
| 4.41 | Ana panel inbox sayacı | ✅ | Bekleyen token varsa `▶️ Başlat` butonu `▶️ N tokeni başlat` olur |
| 4.42 | Inbox autopilot lock | ✅ | Telegram watcher ve worker aynı UID için aynı anda autopilot başlatamaz |
| 4.43 | Token inbox callback autopilot | ✅ | Alt menü `Token inbox` artık import+onarım+mission sonucunu gösterir |
| 4.44 | API keyword context keşfi | ✅ | Discovery route bulamayan permit/training create kelimeleri için bundle snippet basar |
| 4.45 | 20 token inbox autopilot kanıtı | ✅ | `u{uid}_01.jwt`…`u{uid}_20.jwt` tek autopilot çağrısında import+onarım+mission |
| 4.46 | Inbox tarama fail-open | ✅ | Tek bozuk/okunamayan token dosyası sağlam token batch'ini durdurmaz |
| 4.47 | Slot player_id çakışma koruması | ✅ | Aynı `u{uid}_NN` adı farklı Diplomacia hesabını sessizce ezemez |
| 4.48 | Slot çakışması auto-spam önleme | ✅ | Terminal slot hatası aynı token için processed olur; yeni token hash'i retry açar |
| 4.49 | Duplicate player_id koruması | ✅ | Aynı Diplomacia hesabı iki farklı worker slotuna eklenemez |
| 4.50 | Inbox candidate tek karar noktası | ✅ | Refresh/duplicate token dosyaları sessizce düşmez; karar `connect_core`da verilir |
| 4.51 | Pending inbox fresh sayaçları | ✅ | Ana panel/status yalnız processed olmayan tokenları bekliyor sayar |
| 4.52 | Autopilot inbox uyarıları | ✅ | Slot/duplicate import hatası dosya adı ve aksiyonla görünür |
| 4.53 | Training exception retry | ✅ | Beklenmeyen training hatası 5 dk retry planlar ve action_log'a düşer |
| 4.54 | Mission exception görünürlüğü | ✅ | Worker mission exception action_log'a düşer, hesap sessizce kaybolmaz |
| 4.55 | Darboğaz exception özeti | ✅ | `/fleet status` training/mission exception sayılarını görünür özetler |
| 4.56 | Eski buton görünür status | ✅ | Stale yan etkili Telegram butonları kompakt güncel filo status'u ile yönlendirir |

---

## Operatör runbook (20 hesap)

```bash
# 1. Ortam — 20 worker + varsa 1 ana hesap
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
python3 scripts/discover_frontend_api.py --keyword-context
```

**Filo paneli (v4.28.29):** ana ekranda `▶️ Başlat | 📋 Durum | 🇦🇴 AOD | ⚙️ İşlemler` ve hesap rol seçimi var; pending inbox token varsa başlat butonu `▶️ N tokeni başlat` diye görünür. Teknik tick/autofarm aksiyonları ana ekrandan kaldırıldı; alt menüde fabrika, Hürmüz, token inbox, hazırla, ikamet, onar, oy. Alt menüdeki `Token inbox` artık yalnız import değil, kaydedilmiş hedef politikayla import+onarım+mission autopilot sonucunu gösterir. Filo sonuç/status mesajları gerçek mission planını, doğru `data/token_inbox/u{uid}_01.jwt` yolunu ve ana fabrika UUID eksikse görünür uyarıyı gösterir. Autopilot sonucunda slot/duplicate import hatası ilgili `u{uid}_NN` adıyla ve dosyayı boş slota taşıma/kaldırma aksiyonuyla görünür. Eski filo menü butonları 3 dakikadan sonra yeni görünür panel açar; yeni menü tıklamaları yerinde güncellenir. Eski result, alt-menü ve bölge işlem butonları yan etkili işlem üretmeden kompakt güncel status + yeni navigasyonla yönlendirir. `/fleet status` antrenman cooldown bekleyen hesapları, worker darboğaz özetini, mission/training exception sayılarını, kayıtlı `▶️ Başlat` hedefini ve bekleyen inbox token sayısını gösterir; ana hesap varsa kapasite `21/21` olarak 1 main + 20 worker senaryosuna göre hesaplanır. Pending inbox sayaçları yalnız processed olmayan tokenları sayar, böylece terminal duplicate/slot dosyaları Başlat butonunu kirletmez. Region/AOD mission farm fazı work öncesi elmas→hap hazırlığını da çalıştırır. Worker mission exception artık `worker_mission_exception` action_log kaydı üretir; kalıcı plan sessizce takılı kalmaz. Training attack endpoint cooldown/429/HTTP hata döndürürse worker retry zamanı yazar, her tick spam denemez; beklenmeyen training exception da 5 dk retry planlar ve `training_exception` action_log kaydı üretir. Başarısız inbox token importu processed olmaz, sonraki otomatik turda yeniden denenir; aynı `u{uid}_NN.jwt` slotuna farklı JWT konursa token hash değiştiği için otomatik import tekrar denenir ama mevcut slot farklı `player_id` taşıyorsa eski worker sessizce ezilmez. Refresh ve duplicate token dosyaları candidate filtresinde sessizce düşmez; karar `connect_core`da verilir. Aynı Diplomacia `player_id` başka worker slotuna tekrar eklenemez; duplicate token terminal hata sayılır ve aynı token için auto-watch/worker spam'i üretmez. Bu terminal slot çakışması aynı token için processed sayılır, böylece watcher/worker aynı hatayı tekrar tekrar Telegram'a basmaz; dosyaya farklı token konduğunda hash değiştiği için retry açılır. Telegram watcher ve worker aynı UID için dosya lock kullandığından aynı inbox batch'i için çift autopilot/mission enqueue azaltılır. Tek bozuk/okunamayan inbox dosyası artık sağlam tokenları durdurmaz; dosya atlanır ve kalan batch ilerler. `u{uid}_01.jwt`…`u{uid}_20.jwt` dosyalarının tek autopilot çağrısında 20 import, 20 onarım ve 20 mission enqueue ürettiği unit testle kanıtlandı. API discovery `--keyword-context` ile permit/employment/training create kelimelerinin statik bundle bağlamı mutating probe yapmadan incelenir. Argümanlı `/fleetstart Hürmüz vote` ve `/fleetregion ...` sonraki otomatik inbox/Start akışının hedef politikasını kaydeder; `/fleetstart Hürmüz vote` komut handler'ı bu akışı test eder.

---

## UAT teyit matrisi

| Adım | Komut / UI | Beklenen | Durum |
|------|------------|----------|-------|
| U1 | `/fleetinbox` | token_inbox dosyaları bağlanır | ✅ `u515491882_ygt1` bağlandı |
| U2 | `/fleetaod` | bootstrap+fabrika+seyahat+ikamet batch OK | 🟡 bootstrap 3/3 — ana fabrika UUID gerekli |
| U3 | `/fleetvote` | aktif seçimde oy veya net hata | 🔲 canlı |
| U4 | `/fleet status` | rol, mod, bakiye, kapasite + 24s metrik | ✅ 2 hesap tablosu |
| U5 | ⚙️ İşlemler menüsü | alt klavye açılır | 🔲 canlı |
| U6 | 20 worker + ana hesap limit | 21. toplam hesap main varsa kabul, 22. toplam reddedilir | ✅ unit `test_connect_core.py`, 🔲 canlı |
| U7 | `worker_training` | cooldown bitince free attack denemesi | ✅ unit, 🔲 canlı |
| U8 | `/fleetregion Hürmüz vote` | kalıcı region mission kuyruğu | ✅ unit, 🔲 canlı |
| U9 | 1 ana + 20 worker dry-run | repair + audit + AOD/region + training | ✅ `test_fleet_goal_dryrun.py` |
| U10 | `/fleetstart Hürmüz vote` | repair + kalıcı region mission tek cevap | ✅ command unit `test_fleet_autopilot_policy.py`, 🔲 canlı |
| U11 | 20 inbox token + tek autopilot | 20 import + 20 repair + 20 mission, main skip | ✅ `test_fleet_autopilot_inbox_20.py`, 🔲 canlı |

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
- [x] 20 token inbox autopilot: `u{uid}_01.jwt`…`u{uid}_20.jwt` tek çağrıda mission kuyruğuna gider
- [x] Token inbox fail-open: bozuk/okunamayan tek dosya sağlam batch'i düşürmez
- [x] Slot güvenliği: mevcut `u{uid}_NN` farklı `player_id` ile overwrite edilmez
- [x] Slot çakışması auto-spam önleme: terminal hata aynı token için processed olur
- [x] Duplicate güvenliği: aynı `player_id` iki farklı worker slotuna eklenmez
- [x] Inbox candidate filtresi refresh/duplicate dosyalarını sessizce düşürmez
- [x] Pending sayaçları processed tokenları bekliyor diye göstermez
- [x] Autopilot sonucu slot/duplicate import hatasını aksiyonlu gösterir
- [x] Training exception retry: beklenmeyen hata 5 dk backoff + action_log yazar
- [x] Mission exception görünürlüğü: worker_mission_exception action_log yazar
- [x] Darboğaz özeti: training/mission exception sayılarını gösterir
- [x] Eski buton yönlendirmesi: yan etkili stale buton kompakt status gösterir
- [x] Token refresh kaynak yoksa 30 dk backoff; Telegram paketi sistem+venv import OK
- [x] Region/AOD mission farm fazı work öncesi elmas→hap hazırlığı çalıştırır
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
| Aynı inbox slotu yeniden kullanılacak | Eski processed key aynı dosya adına bağlıydı | v4.28.11 sonrası token hash değişirse watcher tekrar dener |
| Token refresh tekrar tekrar deniyor | Kaynak yok / login başarısız | Worker hesap bazlı 30 dk backoff yazar; manuel force refresh backoff'u aşar |
| 22. toplam hesap | Limit | `MAX_ACCOUNTS_PER_USER=20` → main varsa 1 ana + 20 worker |
| Çalışma izni yok | API endpoint keşfedilmedi | `api_route_registry.py` güncellenmeden otomasyon ekleme |
| Antrenman saldırmıyor | `/training-wars/my` boş, cooldown veya attack HTTP hatası | Worker next-attempt yazar; savaş oluşturma/join endpoint keşfi ayrı |

## API keşif politikası

Operatör Diplomacia domaininde API keşfine izin verdi. Rutin akış:

1. `python3 scripts/discover_frontend_api.py --show-missing`
2. `python3 scripts/discover_frontend_api.py --keyword-context`
3. Safe GET route'ları contract/probe ile doğrula.
4. State değiştiren route'ları önce `api_route_registry.py` + replay cassette'e ekle.
5. Endpoint bulunmadan bot ekranında kabiliyeti "hazır" gösterme.

2026-07-01 bundle teyidi: keşif çıktısı `capability:work` ve
`capability:training` aday sayılarını yazdırır. Discovery `/employment` ve
`/work-permits` prefix'lerini de tarar. Ayrı `work permit/employment` endpointi ve
`training-wars create` endpointi canlı bundle'da görünmedi; `/fleet status`
bunları bekleyen gelişmiş kabiliyet olarak gösterir.
`--keyword-context` canlı statik bağlamında `trainingWarAPI` sadece `getMy` ve
`attack` gösterdi; `create` framework kodu, `permit` ise yasal/askeri metin
bağlamında geçti.

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
| 2026-07-01 | 4.28.29 | Eski yan etkili Telegram butonları kompakt güncel status ile yönlendirir |
| 2026-07-01 | 4.28.28 | `/fleet status` darboğaz özeti training/mission exception sayılarını gösterir |
| 2026-07-01 | 4.28.27 | Worker mission exception action_log görünürlüğüne bağlandı |
| 2026-07-01 | 4.28.26 | Worker training exception'ı 5 dk retry planına ve action_log görünürlüğüne bağlandı |
| 2026-07-01 | 4.28.25 | Autopilot sonucu slot/duplicate import hatasını dosya adı ve aksiyonla gösterir |
| 2026-07-01 | 4.28.24 | Ana panel/status pending inbox sayaçları processed terminal tokenları dışlar |
| 2026-07-01 | 4.28.23 | Inbox candidate filtresi refresh/duplicate dosyalarını saklamaz; karar connect_core'a taşındı |
| 2026-07-01 | 4.28.22 | Aynı Diplomacia player_id iki farklı worker slotuna eklenmez; duplicate token auto-spam'i kesilir |
| 2026-07-01 | 4.28.21 | Slot çakışması terminal hata sayılır; aynı token auto-watch/worker spam'i üretmez |
| 2026-07-01 | 4.28.20 | Mevcut inbox slotu farklı player_id taşıyan tokenla sessizce overwrite edilmez |
| 2026-07-01 | 4.28.19 | Token inbox taraması tek bozuk dosyayı atlayıp sağlam token batch'ini korur |
| 2026-07-01 | 4.28.18 | 20 `u{uid}_NN.jwt` inbox tokenı tek autopilot çağrısında import+onarım+mission kuyruğuna kanıtlandı |
| 2026-07-01 | 4.28.17 | API discovery `--keyword-context` ile route dışı permit/training create bağlamı basar |
| 2026-07-01 | 4.28.16 | Alt menü `Token inbox` callback'i import yerine tam autopilot sonucunu gösterir |
| 2026-07-01 | 4.28.15 | Inbox watcher ve worker aynı UID için ortak lock kullanır |
| 2026-07-01 | 4.28.14 | Ana filo paneli bekleyen inbox token sayısını Başlat butonunda gösterir |
| 2026-07-01 | 4.28.13 | Training attack cooldown/HTTP hata cevapları retry planına bağlandı |
| 2026-07-01 | 4.28.12 | `MAX_ACCOUNTS_PER_USER=20` ana hesap varsa 20 worker + 1 main kapasite verir |
| 2026-07-01 | 4.28.11 | Inbox processed state dosya adı yerine token hash'i de içerir; aynı slotta yeni JWT retry edilir |
| 2026-07-01 | 4.28.10 | Region/AOD mission farm fazı normal autofarm gibi work öncesi hap hazırlığı yapar |
| 2026-07-01 | 4.28.9 | Eski `İkamet/Oy ver` callback'leri stale ise işlem çalıştırmadan güncel nav mesajı açar |
| 2026-07-01 | 4.28.8 | `/fleet status` kayıtlı autopilot hedefini ve bekleyen inbox token sayısını gösterir |
| 2026-07-01 | 4.28.7 | Eski alt-menü yan etkili filo komutları stale ise işlem çalıştırmadan güncel nav mesajı açar |
| 2026-07-01 | 4.28.6 | `/fleetstart Hürmüz vote` command handler policy kaydı ve Telegram cevap üretimi testli |
| 2026-07-01 | 4.28.5 | Eski `Başlat/AOD` result butonları stale ise işlem çalıştırmadan güncel nav mesajı açar |
| 2026-07-01 | 4.28.4 | API discovery `/employment` ve `/work-permits` prefix'lerini tarar; U6 unit kanıtı dokümana işlendi |
| 2026-07-01 | 4.28.3 | `/fleet status` hazır değil/runtime/training skip darboğazlarını tek satır özetler |
| 2026-07-01 | 4.28.2 | Filo menü callback'leri stale navigation kuralını gerçekten uygular |
| 2026-07-01 | 4.28.1 | Argümanlı fleetstart/region hedefi kaydedilir; parametresiz autopilot bu policy'yi kullanır |
| 2026-07-01 | 4.28.0 | Başarısız inbox token importları processed işaretlenmez; otomatik retry korunur |
| 2026-07-01 | 4.27.9 | API keşif script'i work/permit ve training candidate özet satırları yazar |
| 2026-07-01 | 4.27.8 | `/fleet status` training next-attempt bekleyen hesapları metrik satırında gösterir |
| 2026-07-01 | 4.27.7 | Eski filo `İşlemler/Ana panel` callback'leri görünür yeni panel açar |
| 2026-07-01 | 4.27.6 | Region/autopilot sonucunda ana fabrika UUID eksikliği görünür uyarı olur |
| 2026-07-01 | 4.27.5 | Boş `/fleet status` gerçek token_inbox yolunu ve `/fleetstart` akışını gösterir |
| 2026-07-01 | 4.27.4 | Boş autopilot sonucunda token_inbox dosya yolu ve tekrar başlatma rehberi |
| 2026-07-01 | 4.27.3 | Region/autopilot sonuçlarında gerçek mission faz planı görünür |
| 2026-07-01 | 4.27.2 | İşlemler menüsünde duplicate Hybrid/Bootstrap ayrımı kaldırıldı |
| 2026-07-01 | 4.27.1 | Filo ana paneli sadeleşti; teknik tick butonları alt menüye indi |
| 2026-07-01 | 4.27.0 | Filo sonuç mesajlarına ortak geri dönüş navigasyonu |
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
