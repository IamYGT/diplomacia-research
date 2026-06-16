# Konsol token varyantları

> **Bot kullanıcıları:** `/connect` veya **📋 Konsol kodu** butonu — doğrulanmış tek satır otomatik gelir.

Oyunda giriş yaptıktan sonra **F12 → Console** — aşağıdan birini yapıştır (geliştirici / yedek).

---

## V1 — Tam script (önerilen)

Dosya: `bot/scripts/diplomacia-grab-token.js`  
Tüm dosyayı konsola yapıştır → otomatik `grabToken()` çalışır.

---

## V2 — Tek satır: storage tara + kopyala (güncel)

Konsol odakta değilken `Clipboard` hatası verir — bu sürüm `execCommand` + `prompt` yedekli:

```javascript
(()=>{const J=/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/;const g=s=>{const m=String(s?s:'').match(J);return m?m[0]:null};const cp=t=>{try{const a=document.createElement('textarea');a.value=t;a.style.cssText='position:fixed;top:0;left:0;width:2px;height:2px;opacity:0';document.body.appendChild(a);a.focus();a.select();const ok=document.execCommand('copy');a.remove();return ok}catch(e){return false}};const h=[];[localStorage,sessionStorage].forEach(S=>{for(let i=0;i<S.length;i++){const v=S.getItem(S.key(i)),t=g(v);if(t)h.push(t);let p={};try{p=JSON.parse(v)}catch(e){}try{Object.values(p).forEach(x=>{const j=g(x);if(j)h.push(j)})}catch(e){}}});const t=[...new Set(h)][0];if(!t)return console.warn('JWT yok — giriş yap, F5, tekrar dene');const ok=cp(t);console.log((ok?'📋 Panoya kopyalandı':'⚠️ Panoya kopyalanamadı — alttaki satırı elle kopyala')+'\n'+t);if(!ok)prompt('Token — Ctrl+C, Enter:',t);return t})();
```

**Senin durumunda:** Token zaten konsolda göründü — `📋 Kopyalandı:` altındaki `eyJ…` satırını seçip Telegram bota yapıştırman yeterli.

---

## V3 — Sadece `localStorage.token`

```javascript
copy(localStorage.getItem('token')||localStorage.getItem('accessToken')||'BULUNAMADI')
```

Not: `copy()` sadece Chrome'da var. Yoksa:

```javascript
console.log(localStorage.getItem('token')||localStorage.getItem('accessToken'))
```

---

## V4 — Network hook (storage boşsa)

Önce bunu yapıştır, sonra oyunda menüye tıkla (profil, fabrika…):

```javascript
(()=>{const J=/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/;const f=window.fetch;const cp=t=>{try{const a=document.createElement('textarea');a.value=t;a.style.cssText='position:fixed;opacity:0';document.body.appendChild(a);a.focus();a.select();document.execCommand('copy');a.remove()}catch(e){prompt('Ctrl+C:',t)}};window.fetch=function(i,o){const a=o?.headers?.Authorization||o?.headers?.authorization||'';const m=String(a).match(J);if(m){console.log('✅',m[0]);cp(m[0])}return f.apply(this,arguments)};console.log('🎣 30sn — oyunda tıkla')})();
```

---

## V5 — Ekranda kutu (mobil / copy çalışmazsa)

`diplomacia-grab-token.js` yüklendikten sonra:

```javascript
showTokenBox()
```

---

## V6 — Debug: hangi anahtarlar var?

```javascript
[...Array(localStorage.length)].map(i=>localStorage.key(i))
```

```javascript
[...Array(sessionStorage.length)].map(i=>sessionStorage.key(i))
```

JWT içeren değer:

```javascript
[...Array(localStorage.length)].map(i=>{const k=localStorage.key(i),v=localStorage.getItem(k);return k+': '+((v||'').includes('eyJ')?'JWT VAR':v?.slice(0,40))})
```

---

## Test checklist

1. [ ] Giriş yapılmış (ana ekran)
2. [ ] Konsol varyantı `eyJ` döndürüyor
3. [ ] Telegram → bota yapıştır → `✅ bağlandı` mesajı
4. [ ] `/start` → dashboard açılıyor

## Sorun giderme

| Belirti | Dene |
|---------|------|
| JWT yok | V4 network hook + oyunda tıkla |
| `copy is not defined` | V2 veya V5 |
| `NotAllowedError` Clipboard / Document not focused | Konsoldaki `eyJ…` satırını elle kopyala veya güncel V2 (prompt açılır) |
| `SyntaxError: missing )` | Kod bozulmuş — `/connect` ile yeni kod al; `String(s?s:'')` ve `JSON.parse` satırına dikkat |
| Mobil | Masaüstü Chrome “Site isteği” → desktop mode |
