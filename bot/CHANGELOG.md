# Changelog

Semantik versiyonlama: `MAJOR.MINOR.PATCH` (`bot/VERSION`).

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
