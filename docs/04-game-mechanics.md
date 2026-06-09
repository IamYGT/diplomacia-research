# Diplomacia — Oyun Mekanikleri Özeti

Kaynak: wiki (78 bölüm) + API crawl + client i18n

## Core loop

1. **Kayıt** → ülke/bağımsız bölge seçimi → **sınıf seç** (kalemiye, asker vb.)
2. **Günlük rutin:** çalış (HP/can), görevler, günlük ödül
3. **Ekonomi:** fabrika kur/çalış, pazar, bağış
4. **Askeriye:** birim eğit, savaşa katkı, kışla yükselt
5. **Siyaset:** parti, seçim, parlamento, kabine
6. **Sosyal:** gazete, DM, global chat, konferans

## Kaynaklar

| Kaynak | Kullanım |
|--------|----------|
| Altın (`balance`) | Genel para, transfer, market |
| Elmas (`diamonds`) | Premium, sağlık hapı craft, IAP |
| NTE, deri, petrol, altın (kaynak) | Fabrika/depo |
| XP | Level, unvan |
| Sağlık / hap | Çalışma limiti |

## Sınıflar (örnek: Kalemiye)

- +50 Kışla Becerisi
- +%20 Elmas Fabrikası Geliri
- +%10 Kaynak Fabrikası Geliri

## Savaş

- `war_type: standard`, `war_goals: [fetih]`
- Eyalet bazlı: attacker_province vs defender_province
- `contribute`, ateşkes, otomatik savaş modu (`auto/status`)
- Mutluluk → isyan (rebellion) mekaniği

## Siyaset

- Siyasi partiler (`/parties/*`)
- Parlamento teklifleri, veto, vergi (`/parliament/*`)
- Kabine rolleri: president, foreign_affairs vb.
- Vatandaşlık başvurusu, vize sistemi

## Otomasyon

- `auto/work` — otomatik çalışma
- `auto/war` — otomatik savaş katkısı
- Bölge günlük kaynak limiti (`province_resource_limit`)

## Monetizasyon

- Elmas paketleri (`/players/diamonds/packages`)
- IAP verify (`/players/diamonds/iap-verify`)
- Premium hediye (`gift-premium`)
