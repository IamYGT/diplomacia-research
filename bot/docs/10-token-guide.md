# Diplomacia Bot — Token (JWT) Alma Rehberi

Bot, Diplomacia hesabını **JWT token** ile bağlar. Token şifren değildir; yine de kimseyle paylaşma.

## Hızlı özet (konsol — önerilen)

1. [diplomacia.com.tr](https://diplomacia.com.tr/) adresinde giriş yap
2. **F12** → **Console**
3. `bot/scripts/diplomacia-grab-token.js` dosyasının tamamını yapıştır → Enter
4. Token panoya kopyalanır → Telegram bota yapıştır (`/connect`)

Tek satır varyantlar: `docs/console-token-variants.md`

## Hızlı özet (manuel)

1. [diplomacia.com.tr](https://diplomacia.com.tr/) adresinde giriş yap
2. Tarayıcıda **F12** → **Application** (Uygulama) sekmesi
3. **Local Storage** → `https://diplomacia.com.tr`
4. `token` veya `auth` anahtarındaki değeri kopyala (`eyJ…` ile başlar)
5. Telegram’da bota yapıştır veya `/connect` komutunu kullan

## Adım adım (Chrome / Edge)

### 1. Oyuna giriş

- Bilgisayardan veya telefondan tarayıcıda oyuna gir
- Karakterin yüklendiğinden emin ol (ana ekran görünsün)

### 2. Geliştirici araçları

- **Windows/Linux:** `F12` veya `Ctrl+Shift+I`
- **Mac:** `Cmd+Option+I`

### 3. Token’ı bul

**Yöntem A — Local Storage (önerilen)**

1. **Application** / **Uygulama** sekmesi
2. Sol menü: **Local Storage** → site adresi
3. `token`, `accessToken` veya benzeri anahtarı ara
4. Değer `eyJ` ile başlayan uzun metin olmalı

**Yöntem B — Network**

1. **Network** sekmesi, sayfayı yenile (`F5`)
2. `api` veya `profile` isteğine tıkla
3. **Headers** → `Authorization: Bearer eyJ…`
4. `Bearer ` kısmını **kopyalama**; sadece `eyJ…` kısmını al

### 4. Bota gönder

Telegram’da:

```
/connect
```

Rehberi oku, ardından token’ı **tek mesaj** olarak yapıştır.

Alternatif:

```
/add ana
```

Sonra JWT’yi yapıştır (ikinci hesap / takma ad için).

## Sık sorunlar

| Sorun | Çözüm |
|-------|--------|
| Token geçersiz | Oyundan çıkıp tekrar gir; yeni token al |
| `eyJ` ile başlamıyor | Yanlış alanı kopyaladın; Local Storage’daki JWT’yi seç |
| Bu hesap başka kullanıcıda | Aynı oyuncu başka Telegram’a bağlı; önce `/disconnect` veya destek |
| Bot yanıt vermiyor | `/start` sonra tekrar dene |

## Güvenlik

- Token = oturum anahtarı. Paylaşırsan hesabın kontrolü gider.
- Bot token’ı şifreli diskte saklar; yine de güvenilir ortamda kullan.
- Şüphelenirsen oyunda şifre değiştir ve yeni token ile `/connect` yap.

## Telegram komutları

| Komut | Açıklama |
|-------|----------|
| `/connect` | İlk bağlantı + rehber |
| `/add isim` | Ek hesap (filo) |
| `/accounts` | Bağlı hesaplar |
| `/remove isim` | Hesabı bottan kaldır |
| `/start` | Ana panel |
