# Diplomacia — Tersine Mühendislik + İleri Zafiyet Taraması

**Tarih:** 2026-06-09  
**Hesap:** Ercan2 (test)  
**Çıktı:** `output/reverse/reverse_probe.json`, `output/reverse/phase2_probe.json`

---

## Özet

| Vektör | Sonuç | Kanıt |
|--------|-------|-------|
| Rakip fabrika join/withdraw IDOR | **Kısmi** | join rakip fabrika **200**; withdraw/fire/close **404/403** |
| Socket.IO kanal sızıntısı | **Kısmi bilgi** (tasarım) | `global_history` + canlı `global_message`; yabancı DM yok |
| Transfer race condition | **Test edilemedi / güvenli** | Lv1 → 403 seviye; paralel → CF 1010 |
| Top player email/balance | **Güvenli** | `#1 UhtreD` profilde email/balance yok |
| RE: gizli endpoint | `/mod/grant-gold` → 403 | Moderatör korumalı |

---

## 1. Factory IDOR (mutation)

**Hedef fabrika (rakip):** `ac44f956-…` — sahip `6dc0b507-…`

| Endpoint | Body | HTTP | Yanıt |
|----------|------|------|-------|
| `POST /factories/join` | `{factory_id}` rakip | **200** | "Fabrikaya katıldınız!" (phase2, ayrıldıktan sonra) |
| `POST /factories/leave` | `{}` | 200 | Ayrıldınız |
| `POST /factories/withdraw` | rakip id + amount | 404 | Fabrika bulunamadı / yetki yok |
| `POST /factories/fire` | rakip owner | 403 | Sahibi değilsiniz |
| `POST /factories/rename/close/salary` | rakip id | 404 | Yetki yok |
| `POST /factories/work` | `{}` | 200 | **Kendi** fabrikasında (`is_owner: true`) — IDOR değil |

**Sonuç:** Para çekme / sahibi işlemleri korumalı. Ancak **herhangi bir `factory_id` ile işçi olarak katılmak mümkün** — bu tasarım (açık fabrika) veya düşük öncelikli IDOR olabilir; rakip bütçesinden çekim yok, `work` can şartı (3/100) yüzünden test edilemedi.

**Checkpoint 5 (2026-06-09):** `reverse_probe.probe_factory_idor` yeniden koşuldu — `join` 200 (işçi katılımı), `withdraw`/`close`/`fire`/`rename` 403/404, `exploited_count: 0`. Kanıt: `output/reverse/factory_idor_checkpoint5.json`

**İstihbarat (read IDOR, önceki turlar):** `GET /factories/player/{uuid}` → rakip fabrika seviye/bütçe/tip.

---

## 2. Socket.IO

**Bağlantı:** `wss://diplomacia.com.tr` — `auth: { token, lang }`  
**Bundle event'leri (RE):** `global_message`, `global_history`, `dm_message`, `dm_send`, `dm_new`, `conf_message`, `conf_send`, `country_announcement`, `revolution`, `chat_ban`, `chat_delete`, …

| Test | Gözlem |
|------|--------|
| Connect + dinle | `global_history` → son ~50 global mesaj (player_id, username, avatar) |
| `emit global_message` | Kendi mesajın herkese yayınlanır (beklenen) |
| `emit dm_send` → top1 | Yabancı `dm_message` dinlemede gelmedi |
| `emit conf_send` | `conf_message` alınmadı (muhtemelen oda üyeliği şart) |

**Değerlendirme:** Global sohbet kasıtlı olarak herkese açık. **Cross-user DM sniffing** bu testte yok. `requests` paketi olmadan python-socketio bağlanamıyor — script'e `pip install requests` eklendi.

**Checkpoint 6 (2026-06-09):** `scripts/socket_transfer_probe.py` — connect OK, `global_history` + `global_message` alındı, `dm_send` fake UUID'ye emit → **foreign_dm_received: false**. Bundle'dan 33 event (`socket_events_enum.json`). Chat-relevant: `global_message`, `global_history`, `dm_message`, `dm_send`, `dm_new`, `conf_message`, `conf_send`, `country_announcement`, `revolution`, `chat_ban`, `chat_delete`, `chat_bulk_delete`, `chat_error`.

---

## 3. Transfer race

- Paralel 8× `POST /transfer/send` → `recipient_id` sahte UUID, `amount: 100`
- Tüm thread'ler: **403** — "Para göndermek için en az 5. seviye" (hesap API'de lv1 görünüyor)
- Bakiye delta: **0**
- Self-transfer race: **CF 1010** (paralel istek ban)

**Sonuç:** Race exploit kanıtlanmadı; seviye gate + Cloudflare paralel POST'u kesiyor.

**Checkpoint 6:** Ercan2 lv4 — `POST /transfer/send` tek istek **403** (min lv5), paralel race **atlandı**, bakiye delta **0**. Kanıt: `output/reverse/socket_transfer_checkpoint6.json`

---

## 4. Top 10 oyuncu — email / balance

Leaderboard kaynağı: `GET /countries/leaderboard/world?page=1&limit=10`

**#1 UhtreD** (`6a3043a9-…`):
- `GET /players/{id}` → 200, alanlar: username, xp, reputation, cabinet, skills…
- **`email` yok, `balance` yok** (CONFIRMED `phase2_probe.json`)
- `GET /players/profile` (kendi) → email + balance **sadece oturum sahibi**

Yanlış alarm: `donation-history` JSON'unda `"resources"` anahtarı var → otomatik tarayıcı "leak" saydı; **gerçek bakiye sızıntısı değil**.

---

## 5. API tersine mühendislik (bundle)

**Base:** `https://diplomacia.com.tr/api`  
**Factory modülü yolları:** `/factories/build`, `join`, `leave`, `work`, `work-status`, `withdraw`, `withdraw-resources`, `fire`, `salary`, `rename`, `close`, `level-up`, `move`, `my`, `player/{id}`, `region`, `country`, `world`, `tax`

**Fuzz (gizli):**
- `/players/me` → 400 Geçersiz oyuncu ID
- `/mod/grant-gold` GET/POST → 403 Moderatör yetkisi gerekli

---

## 6. Hâlâ geçerli exploit (önceki tur)

`POST /players/complete-step` adımları 3–5 → tutorial ödülleri API ile alınabiliyor (+200k altın bandı). Replay sonrası `success: false`.

---

## Scriptler

```bash
/var/www/research/scrapling-venv/bin/pip install requests  # socket.io için
python scripts/reverse_probe.py   # ~5 dk, DELAY=3s
python scripts/phase2_probe.py  # leave→join, socket, self-race
```

---

## Sonraki turlar (öneri)

1. Ayrıldıktan sonra `join` rakip fabrika — phase2 fix ile yeniden koş
2. Lv5+ hesap veya mod test hesabı ile transfer race (CF bypass: sıralı değil kademeli paralel)
3. İki token ile A→B DM: B soketinde A'nın mesajı görünüyor mu (hedefli DM testi)
4. `conf_send` için aktif konferans/parlamento oturumu ID'si RE ile bulunup tekrar dene
