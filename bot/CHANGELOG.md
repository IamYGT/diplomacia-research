# Changelog

Semantik versiyonlama: `MAJOR.MINOR.PATCH` (`bot/VERSION`).

## [4.6.0] — 2026-06-16

### Changed — Telegram modülü bölündü (refactor)
- `telegram_app.py` 2773→1401 satır: 24 bağımsız UI/account helper `telegram_helpers.py`'ye (split adım 1)
- `_handle_callback` (1041 satır callback router) `callbacks.py`'ye taşındı (split adım 2) — app re-export (test geri-uyumu)
- Helper'lar sadece dış modüllerden import eder (acyclic graph); `_send_dashboard` monkey-patch hedefi olduğu için app'te kaldı
- Yeni `tests/test_callbacks_import.py` — acyclic + re-export regresyon testi

### Fixed
- **429 rate-limit blokajı:** `stealth_client` 429'da retry yapmaz (290sn→1.8sn) — cooldown set + dönüş
- **Scheduler overlap:** `STAT_QUEUE_INTERVAL_SEC` 15→60sn — tick API 90-180sn'i aşınca sürekli "maximum running instances" skip
- **Dashboard boş snapshot:** stat_queue cooldown aktifken tick upgrade denemez → `_last_429_at` sonsuz yenilenme + dashboard 6 paralel 429 gider
- **httpx getUpdates log gürültüsü:** her 10sn INFO → WARNING (8MB error log)
- **Test sync:** split sonrası `test_default_account` patch hedefi `telegram_helpers`, snapshot fixture `_live: True`

### Added
- `stat_queue.py` cooldown skip — rate limit'e saygı, upgrade spam önle
- `tests/test_callbacks_import.py` — split acyclic garantisi

## [4.5.3] — 2026-06-14

### Fixed — Dashboard açılış süresi
- **İki aşamalı yükleme:** önce 3 çekirdek API (profil/auto/pasif) → panel anında; readiness (görev/antrenman/savaş) arka planda
- `snapshot_account(..., enrich=False)` — kritik yoldan +3 sıralı API kaldırıldı
- `probe_readiness_light` — 3 probe **paralel** (hesap proxy + interactive_fast thread başına)
- 429 cooldown + önbellek yok → bekleme mesajı (180 sn uyku yerine)
- `INTERACTIVE_API_TIMEOUT_SEC=15` — Tor interactive isteklerinde üst sınır
- `DASHBOARD_CORE_TIMEOUT_SEC` / `DASHBOARD_ENRICH_TIMEOUT_SEC` — aşama zaman aşımı

## [4.5.2] — 2026-06-14

### Fixed — Konsol JWT script SyntaxError
- `String(s||'')` → `String(s?s:'')` — kopyada `||` silinince `s''` hatası
- `JSON.parse(v)||{}` → ayrı try/catch — `parse(v){}` bozulması giderildi
- Telegram `/connect` mesajına yedek tek satır + uyarı
- `validate_oneliner_js()` — Node syntax testi

## [4.5.1] — 2026-06-14

### Refactor — öneriler uygulandı
- `readiness_probes.py` — ortak `probe_readiness_light` / `probe_readiness_full` / `fetch_readiness_pack`
- Readiness **60 sn cache** (`READINESS_CACHE_SEC`) — snapshot yenilemede gereksiz API azaltıldı
- `dashboard_markup.py` — görev/antrenman/hap hızlı butonları + ⋯ Daha rozeti
- `feature_handlers` → `fetch_readiness_pack` (game_features duplicate bypass)
- `scripts/probe_init_data.py` — `GET /init/data` canlı probe
- Snapshot invalidate → readiness cache temizlenir

## [4.5.0] — 2026-06-14

### Dashboard v2
- Snapshot readiness: `quests_claimable`, `training_ready`, `craft_ready`, `war_active` — `_next_steps` ve **Hazır:** rozeti artık çalışır
- Work countdown (`~45 sn`), veri yaşı footer (`veri 12 sn önce`), API hata satırı
- Profilden `active_skills` → stat kuyruk özeti ana sayfada
- `dashboard_readiness.py` — hafif enrich (quests, antrenman, savaş)

### Stat paneli
- **Durum + Kuyruk** tek satır (`format_stat_status_combined`) — tekrar kaldırıldı

### API keşif
- `data/api_probe_extra.json` — 16 probe-only path (`/init/data`, paytr, …)
- `catalog.load_catalog()` ana katalog + probe birleşimi

## [4.4.11] — 2026-06-14

### Changed — Kuyruk satırı skill adı
- Pending: `Kışla bitince → 118 sn` veya `Kışla bitince → Savaş teknikleri · 118 sn`
- Başka skill hazırsa: `Savaş teknikleri hazır — 15 sn içinde otomatik`

## [4.4.10] — 2026-06-14

### Changed — Stat paneli kuyruk satırı
- **Kuyruk:** `{X} sn sonra otomatik` — `preview_stat_queue` / `should_tick_now` kararı panelde
- Hazır stat varken: «Hazır — en geç 15 sn içinde otomatik»
- Durum metni: farm tick yerine kuyruk odaklı açıklama

## [4.4.9] — 2026-06-14

### Fixed — Stat kuyruk cooldown sonrası devam etmiyordu
- `stat_queue_job` (~15 sn): pending bitince otomatik sonraki yükseltme
- **Kritik:** Pending skill varken tüm kuyruk atlanıyordu — artık sıradaki hazır stat hemen denenir
- `should_tick_now`: hazır skill varsa beklemeden tick; yoksa `pending_at` uyanması
- `skill_is_pending`: süre bitince veya seviye yakalanınca false (takılı pending temizlenir)
- Yükseltme sonrası `note_pending_wake` — cooldown bitişinde cron gibi tekrar

### Added
- `STAT_QUEUE_INTERVAL_SEC` (varsayılan 15)
- `tests/test_stat_queue.py`

## [4.4.8] — 2026-06-14

### Changed — Premium hesaplar
- Autofarm tick: `is_premium` + `auto/status` sorgusu — panelde gün + Auto/work durumu
- Premium + auto/work açık → manuel work / farm yap atlanır (sunucu farm yapar)
- Tüm premium hesaplarda `sync_premium_modes` (sadece hub rolü değil)
- Dashboard: «akıllı farm gerekmez» yönlendirmesi premium auto/work açıkken

## [4.4.7] — 2026-06-14

### Fixed — Stat otomatik farm ile çalışmıyordu
- `farm yap` / farm merkezi **work** yolu `run_quick_farm` kullanıyordu — stat atlanıyordu
- Artık her work öncesi + sonrası `run_stat_automation` (pasif + altın yükselt)
- Orchestrator: farm kazancından sonra ikinci stat pass (aynı tick'te yeni bakiye)
- `run_stat_automation()` ortak helper — «Şimdi uygula» ile aynı mantık

## [4.4.6] — 2026-06-14

### Fixed — Dashboard yükleme (kritik)
- Snapshot API çağrıları thread pool'da `interactive_fast` bağlamını kaybediyordu → **istek başına ~6 sn** gecikme
- Tek thread + düşük delay (`SNAPSHOT_API_DELAY_SEC`, varsayılan 0.08 sn) — panel ~1 sn içinde
- Önbellek varsa anında gösterilir; API 429'da önbellek + bekleme süresi
- Zaman aşımı / hata: sonsuz «Hazırlanıyor» yerine önbellek veya hata mesajı

## [4.4.5] — 2026-06-14

### Changed — Stat paneli durum netliği
- **Durum:** satırı — «Kışla bitince → Savaş teknikleri sıraya girer (24 sn)»
- Aktif stat satırları: `▶ sıradaki` · `⏳ yükseliyor` · kalan süre veya tahmini
- **Yenile** artık paneli günceller (`stat:refresh`) — yeni mesaj açmaz; pending varken `⏳ Yenile`
- **Şimdi uygula** sonucu: neden yapılmadığı açıklanır (sıra bekliyor vb.)

### Fixed
- API süre vermezse `~27 sn (tahmini)` — belirsiz «bekliyor» kaldırıldı

## [4.4.4] — 2026-06-14

### Changed
- Pending stat: panelde kalan süre (`24 sn kaldı`) — `pending_at` sayacı
- Yetersiz bakiye/elmas: API `required` → «Yetersiz bakiye. Gerekli: 12.500 ₺»
- Ana menüden Statlar: yeni mesaj (dashboard edit yerine) — güncel panel garantisi

### Added
- `format_upgrade_error` · `pending_seconds_remaining` unit testleri

## [4.4.3] — 2026-06-14

### Fixed
- `menu:accounts` callback — `NameError: uid` (`_send_accounts_picker` düzeltildi)
- `/setstat` — hesap seçimi `resolve_account` ile (bozuk `_default_account(uid)` çağrısı)

## [4.4.2] — 2026-06-14

### Changed — Stat paneli 30+ UX (isim, numara yok)
- Liste: «Kışla — seviye 52» (1/2/3 ve `bilim_insani` yok)
- Butonlar: `Kışla` · `Bilim insanı` · `Savaş teknikleri` (öncelik için)
- Komutlar: `önce Kışla` · `/setstat Bilim insanı, Kışla`
- «Otomatik: Açık» · «Şimdi uygula» — sade Türkçe

## [4.4.1] — 2026-06-14

### Fixed — Stat yükseltme API
- Oyun `type: money|diamond` bekliyor (`gold`/`altin` değil) — `Geçersiz yükseltme tipi` düzeltildi
- Yükseltme cooldown (`pending_at`, `cooldown_ms`) panelde ⏳ olarak gösterilir
- Cooldown'daki skill otomatik döngüde atlanır

## [4.4.0] — 2026-06-14

### Changed — Statlar tam otomatik (altın)
- **Varsayılan:** farm/akıllı döngüde pasif puan + altınla aktif stat yükseltme otomatik
- Panel sadeleştirildi: sıra + seviyeler; ham API anahtarı ve buton labirenti kaldırıldı
- `stat_auto_enabled` DB (varsayılan açık) · `🟢 Oto AÇIK` / `▶️ Şimdi` butonları
- Elle müdahale: `💎 Elmas` · `# öncelik` · otomatik kapalıyken pasif harca

### Added
- `stats.auto_upgrade_gold()` — öncelik sırası, tick başına 5 yükseltme
- `run_stat_auto_now()` — tek tıkla otomasyon özeti

## [4.3.0] — 2026-06-14

### Changed — Stat merkezi: asıl statlar öncelikli
- **Aktif skill** (Kışla, Bilim insanı, Savaş teknikleri) artık birincil liste — numaralı `1. 2. 3.`
- Pasif puanlar ikincil bölüm: `P1. P2.` + ⚡ butonları
- `POST /players/skills/upgrade` — ⬆️N altın · 💎N elmas yükseltme
- `stat:up:N:gold|diamond` · `stat:uppri` · `stat:pspend:N` callback'leri
- `stat_priority` DB artık **aktif stat** upgrade önceliği
- Komutlar: `stat yükselt` · `stat 1 yükselt` · `kisla yükselt`

### Fixed
- `modules/stats.py` — `spend_passive` geri yüklendi + `upgrade_skill` eklendi

## [4.2.0] — 2026-06-14

### Added — Farm merkezi (elmas↔hap döngüsü)
- Work/hap cooldown görünür — CD varken düz metin yerine panel
- ROI: work başına elmas, başabaş work sayısı, günlük tahmin
- Inline: 🌾 çalış · 💎500/1000/3000 craft · 💊 can · 🧠 akıllı döngü
- `farm:toggle:autocraft` — DB `craft_pills_when_low`
- Craft batch tıklanınca `craft_diamond_batch` DB'ye yazılır

### Changed
- `🌾 Farm` butonu → farm merkezi (cooldown'da da açılır)
- `farm yap` — CD varsa panel, yoksa çalış + sonuç
- `action:craft` → farm merkezine yönlendirildi

## [4.1.0] — 2026-06-14

### Added — Stat merkezi
- **⚡ Stat merkezi** — numaralı pasif skill listesi + aktif skill özeti
- Inline: ⚡N harca · #N öncelik · 🗡️ hepsini harca · 🎯 önerilene
- Ana sayfa ve ⋯ menüde her zaman görünür (`action:statboard`)
- DB `stat_priority` — buton veya `/setstat kisla,ekonomi`
- Komutlar: `statlar` · `stat harca` · `stat 2 harca` · `/setstat 1`

### Changed
- Eski `action:stat` kör harcama → stat panosu açar
- `stat_board.py` — fabrika/savaş panosu ile aynı UX kalıbı

## [4.0.0] — 2026-06-14

### Added — Fabrika merkezi v2
- Numaralı sahip fabrikaları (`1.`) + bölge listesi (`R1.`, `R2.`)
- Tüm fabrika aksiyonları: katıl, ayrıl, çalış, kur, kapat (onaylı), para çek, seviye atla
- DB alanları: `primary_factory_id`, `default_salary_rate`, `default_build_name`
- Inline: 🎯 ana · 📌 sabit · 💰 çek · ⬆️ level · 🔒 kapat · R➕ katıl · mod değiştir
- `action_log` → `fab:close`, `fab:join`, `fab:work` vb.
- Komutlar: `fabrika`, `fabrika kapat 1`, `fabrika kur`, `ana fabrika 1`

### Changed
- `factory_board.py` — savaş panosu ile aynı UX kalıbı
- `game_features.run_factory_action()` — merkezi API sarmalayıcı

## [3.9.0] — 2026-06-14

### Added — Savaş panosu v2
- Numaralı liste (1, 2, 3…) + güç çubuğu + kalan süre
- Senin ülken / saldırgan-savunucu tarafı otomatik
- Inline: 🎯N hedef seç · 🗡️N katkı · taraf değiştir
- `/setwar 2` · `savaş 2` · `katkı 1` komutları

### Changed
- `war_board.py` — zengin analiz ve markup
- Katkı doğrudan seçilen savaşa gider

## [3.8.0] — 2026-06-14

### Added
- `scripts/benchmark_gemini_models.py` — model hız/kararlılık testi
- Startup Gemini smoke (`verify_connection`)

### Changed
- Varsayılan model: **gemini-2.5-flash-lite** (~500–650ms JSON+text)
- `GEMINI_THINKING_BUDGET=0` — koç modu hızlandırıldı
- Fallback: `gemini-flash-lite-latest` (2.0 modeller quota 429 veriyor)

## [3.7.1] — 2026-06-14

### Changed
- JWT artık düz metin `accounts.token` — Fernet şifreleme kaldırıldı
- Migration v5: mevcut şifreli kayıtlar `eyJ…` olarak geri açılır

## [3.7.0] — 2026-06-14

### Added
- SQLite migration sistemi (`schema_migrations`, v1–v4)
- `game_snapshots` — panel verisi restart sonrası kalıcı
- `action_log` — farm/connect/autofarm audit
- `bot_sessions` — varsayılan hesap + pending_connect DB'de
- JWT Fernet şifreleme (`token_enc`, `BOT_DB_SECRET`)
- WAL mode + indexler (`telegram_user_id`, `player_id`)

### Changed
- `dynamic_context` — bellek → SQLite → canlı API katmanı
- `/connect`, farm, autofarm → `log_action` kaydı

## [3.6.2] — 2026-06-14

### Added
- `token_console.py` — doğrulanmış konsol snippet tek kaynak
- `/connect` + **📋 Konsol kodu** butonu → snippet Telegram'dan kopyalanır
- `connect:script` callback — kodu tekrar gönder

### Changed
- Token rehberi: F12 → yapıştır → eyJ bota akışı
- Konsol V2: `execCommand` + `prompt` yedek (NotAllowedError)

## [3.6.1] — 2026-06-14

### Fixed
- Dashboard yavaşlığı: okuma işlemlerinde Tor NEWNYM kaldırıldı (~4–14 sn kazanç)
- Panel önbelleği anında gösterilir (stale-while-revalidate, 90 sn)
- Snapshot TTL 20 sn; paylaşımlı thread pool; interactive API delay düşürüldü

## [3.6.0] — 2026-06-14

### Added
- **Global bot** — `BOT_PUBLIC=1` (varsayılan): herkes kullanabilir
- `/connect` — JWT token alma rehberi + self-service kayıt
- `docs/10-token-guide.md` — detaylı token rehberi
- Hesap sahipliği: `telegram_user_id` (kullanıcı başına izole hesaplar)
- `MAX_ACCOUNTS_PER_USER` — filo limiti (varsayılan 5)

### Changed
- `admin_only` → çoğu komut `user_required` (herkese açık)
- Yönetici: `/intel`, `/proxies`, `/setproxy`, `/endpoints`, `/api`
- Autofarm bildirimi → hesap sahibinin Telegram ID'sine
- AI/filo yalnızca kullanıcının kendi hesaplarını görür

## [3.5.1] — 2026-06-14

### Fixed
- `GEMINI_API_KEY` yokken ham geliştirici mesajı yerine kullanıcı dostu panel + inline butonlar
- Yerel koç (`local_answer` / `answer_teach_full`) Gemini olmadan öncelikli
- `yardım` / `ne yapmalıyım` → hızlı yol (`intent_router`)

## [3.5.0] — 2026-06-14

### Added
- `feature_analysis.py` — görev/savaş/fabrika/antrenman ekonomi analizi + hazırlık özeti
- `feature_reports.py` — zengin HTML panolar (ilerleme çubuğu, ödül dökümü, sıradaki adımlar)
- `feature_handlers.py` — ek menü canlı hazırlık + tüm ⋯ Daha aksiyonları

### Changed
- Her özellik: paralel API paketleri, preflight mesajları, rozetli ek menü
- Farm / plan / günlük / stat / görev: detaylı HTML raporlar
- Fabrikam: bölge fabrikaları + work + auto durumu tek panelde
- Plan: canlı snapshot + sıradaki aksiyon zinciri

## [3.4.0] — 2026-06-14

### Added
- **⋯ Daha** menüsü — 12 yeni inline aksiyon (görev, savaş, antrenman, asker, fabrika, hap craft, ülkeler, online, otomasyon, pasif stat, ping, akıllı farm)
- `game_features.py` — API keşif sarmalayıcıları (`/factories/my`, `/military/me`, `/training-wars`, `/online`, vb.)
- `bot/data/api_catalog.json` — 213 endpoint (`/endpoints` komutu)

### Changed
- Yardım metni: `/start ile sıfırla` → `🔄 Yenile` butonu
- Hata mesajlarında panel yenileme yönlendirmesi

## [3.3.7] — 2026-06-14

### Changed
- Menü geçişleri: anında takipli mesaj (`cevap birazdan iletilecek`), çift Telegram edit kaldırıldı
- Dashboard / farm / hap / stat / günlük / plan: arka plan görevi (`spawn_tracked`) — callback bloklanmıyor
- Klavye menüsü (Ana sayfa, Ayarlar, Filo, Hesaplar): geçiş metni + tek edit

## [3.3.0] — 2026-06-14

### Added
- **Çoklu hesap filosu** (`fleet_manager.py`) — 10+ hesap yönetimi
- Hesap rolleri: `farm` | `war` | `hybrid` | `hub` | `off`
- Telegram **👥 Filo** paneli — rol grupları, toplu tick, autofarm açma
- `/fleet`, `/setrole` komutları
- Orchestrator rol-aware: savaş hesapları fabrika atlar, farm hesapları savaş atlar

### Changed
- Autofarm job → `tick_one` + rol filtresi
- Ayarlar ekranında görev rolü seçimi (Farm/Savaş/Karma)

## [3.2.0] — 2026-06-14

### Added
- Sadeleştirilmiş klavye: Ana Sayfa, Farm, Can, Stat, Günlük, Ayarlar, Yardım
- «Şimdi ne yapmalı?» akıllı yönlendirme panelde
- Ayarlar ekranı: otomatik farm, fabrika modu (Kendi/Yabancı/Otomatik)
- Hesap seçici inline butonlar
- Aksiyon sonrası «🏠 Ana Sayfa» dönüş butonu
- `/menu` ve `/settings` komutları

### Changed
- Türkçe etiketler (foreign → Yabancı fabrika)
- Klavye butonları AI yerine doğrudan handler'a gider
- `/accounts` görsel hesap listesi + seçim

### Fixed
- Ölü `ercan2` varsayılan hesap otomatik `ygt`'ye düşer

## [3.1.0] — 2026-06-14

### Added
- Telegram UI modülü: HTML dashboard, persistent reply keyboard, inline aksiyonlar
- `/dashboard` — canlı kontrol paneli (can, ekonomi, bot modu, uyarılar)
- Bot komut menüsü (`set_my_commands`) + MenuButtonCommands
- Copy-to-clipboard fabrika ID, hesap switcher, autofarm toggle inline
- Alt menü kısayolları (📊 Durum, 🌾 Akıllı Farm, …)

### Fixed
- `NameError: log` — bot PM2 crash

## [3.0.0] — 2026-06-14

### Added
- Modüler bot v3: `economy`, `factory`, `stats`, `training`, `war`, `premium`, `orchestrator`
- Hesap config (`account_config`) — work_mode, fabrika, stat önceliği, premium hub
- Multi-IP: Tor pool, stealth client, `rules.yaml` proxy atama
- Telegram: `/setfabric`, `/plan`, `/version`, `/proxies`, `/intel`
- `scripts/module_probe.py`, `verify_bot.py`, `import_tokens.py`
- Dokümantasyon: `bot/docs/00-09`
- 32+ birim testi

### Changed
- Autofarm → orchestrator tick (stat + training + war + work)
- Fabrika: eyalet uyumu, `foreign` mod, otomatik build kapalı (varsayılan)
- AI: dinamik bağlam, genişletilmiş intent router

### Fixed
- Yanlış eyalette fabrika seçimi (Tahran fabrika / Hürmüz oyuncu)
- Kalemiye pasif stat: `vergi_uzmani` önceliği

## [2.1.0] — önceki

- Gemini koç, intent router, çoklu hesap DB
