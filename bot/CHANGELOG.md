# Changelog

Semantik versiyonlama: `MAJOR.MINOR.PATCH` (`bot/VERSION`).

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
