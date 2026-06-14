# Diplomacia Telegram Bot v3.0.0

Modüler 24s farm bot + dinamik AI koç + multi-IP.

## Versiyon

```bash
cat bot/VERSION                    # 3.0.0
python3 scripts/bump_version.py patch --note "Açıklama"
/version                           # Telegram
```

Changelog: `bot/CHANGELOG.md`

## Kurulum

```bash
cd bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/rules.example.yaml data/accounts/rules.yaml
```

## AI (dinamik)

Serbest mesajlar canlı oyuncu durumuna göre yanıtlanır:

| Mesaj | Davranış |
|-------|----------|
| `akıllı farm` | orchestrator tick (stat+training+work) |
| `planım` | hesap config özeti |
| `stat harca` | pasif skill spend |
| `fabrika ayarla foreign` | work_mode güncelle |
| `can ne işe yarıyor` | koç + profil bağlamı |

Gemini planlayıcı `dynamic_context` ile canlı probe alır.

## Modüller

`diplomacy_bot/modules/` — docs: `bot/docs/`

## Test

```bash
.venv/bin/python3 -m unittest discover -s tests -q
python3 ../scripts/module_probe.py ygt --json
```

## Başlat

```bash
bash ../scripts/start_bot.sh
```
