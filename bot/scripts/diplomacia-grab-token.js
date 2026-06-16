/**
 * Diplomacia JWT — tarayıcı konsolundan token al
 *
 * Kullanım:
 * 1. https://diplomacia.com.tr/ adresinde GİRİŞ YAP (ana ekran görünsün)
 * 2. F12 → Console
 * 3. Bu dosyanın içeriğini yapıştır VEYA aşağıdaki tek satırlık varyantlardan birini
 * 4. Çıkan token'ı Telegram bota yapıştır (/connect)
 *
 * Tek satır kaynak: diplomacy_bot/token_console.py → CONSOLE_GRAB_TOKEN_ONELINER
 */
(function () {
  "use strict";

  const JWT_RE = /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/;

  function isJwt(s) {
    return typeof s === "string" && JWT_RE.test(s.trim());
  }

  function extractJwt(s) {
    if (!s) return null;
    const m = String(s).match(JWT_RE);
    return m ? m[0] : null;
  }

  function walkJson(val, out, path) {
    if (val == null) return;
    if (typeof val === "string") {
      const j = extractJwt(val);
      if (j) out.push({ path, token: j, preview: j.slice(0, 24) + "…" });
      try {
        const parsed = JSON.parse(val);
        walkJson(parsed, out, path + " (json)");
      } catch (_) {}
      return;
    }
    if (Array.isArray(val)) {
      val.forEach((v, i) => walkJson(v, out, path + "[" + i + "]"));
      return;
    }
    if (typeof val === "object") {
      for (const [k, v] of Object.entries(val)) {
        walkJson(v, out, path ? path + "." + k : k);
      }
    }
  }

  function scanStorage(store, label) {
    const hits = [];
    try {
      for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        const raw = store.getItem(key);
        walkJson(raw, hits, label + ":" + key);
        const direct = extractJwt(raw);
        if (direct) hits.push({ path: label + ":" + key, token: direct, preview: direct.slice(0, 24) + "…" });
      }
    } catch (e) {
      console.warn(label, e);
    }
    return hits;
  }

  function scanCookies() {
    const hits = [];
    document.cookie.split(";").forEach((part) => {
      const [k, ...rest] = part.trim().split("=");
      const v = rest.join("=");
      const j = extractJwt(decodeURIComponent(v || ""));
      if (j) hits.push({ path: "cookie:" + k.trim(), token: j, preview: j.slice(0, 24) + "…" });
    });
    return hits;
  }

  function dedupe(hits) {
    const seen = new Set();
    return hits.filter((h) => {
      if (seen.has(h.token)) return false;
      seen.add(h.token);
      return true;
    });
  }

  function decodePayload(token) {
    try {
      const b = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return JSON.parse(atob(b));
    } catch (_) {
      return null;
    }
  }

  async function copyText(text) {
    try {
      window.focus();
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.cssText = "position:fixed;top:0;left:0;width:2px;height:2px;opacity:0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        if (ok) return true;
      } catch (_) {}
      prompt("Token — Ctrl+C, Enter:", text);
      return false;
    }
  }

  function pickBest(hits) {
    const priority = ["token", "accessToken", "access_token", "authToken", "jwt", "auth"];
    for (const name of priority) {
      const h = hits.find((x) => x.path.toLowerCase().includes(name));
      if (h) return h;
    }
    return hits[0] || null;
  }

  /** Ana fonksiyon — tüm depoları tara */
  function grabToken(options) {
    options = options || {};
    const hits = dedupe([
      ...scanStorage(localStorage, "localStorage"),
      ...scanStorage(sessionStorage, "sessionStorage"),
      ...scanCookies(),
    ]);

    console.log("🔍 Diplomacia token taraması —", hits.length, "adet JWT bulundu");
    hits.forEach((h, i) => {
      const payload = decodePayload(h.token);
      console.log(
        i + 1 + ".",
        h.path,
        payload ? "→ @" + (payload.username || payload.sub || payload.id || "?") : "",
        h.preview
      );
    });

    if (!hits.length) {
      console.warn(
        "❌ JWT bulunamadı. Giriş yaptın mı? Sayfayı yenile (F5) ve tekrar dene.\n" +
          "   Alternatif: grabTokenFromNetwork() sonra oyunda bir menüye tıkla."
      );
      return null;
    }

    const best = pickBest(hits);
    const token = best.token;
    const payload = decodePayload(token);

    if (options.copy !== false) {
      copyText(token).then((ok) => {
        console.log(ok ? "📋 Panoya kopyalandı!" : "⚠️ Kopyalanamadı — aşağıdaki token'ı elle seç:");
        console.log("%c" + token, "font-size:11px;word-break:break-all");
      });
    } else {
      console.log("%c" + token, "font-size:11px;word-break:break-all");
    }

    if (payload) {
      console.log("👤 Payload:", payload);
    }
    console.log("📤 Telegram: token'ı bota tek mesaj olarak yapıştır (/connect)");

    return { token, path: best.path, payload, all: hits };
  }

  /** Sonraki API isteğinden Bearer yakala */
  function grabTokenFromNetwork(timeoutMs) {
    timeoutMs = timeoutMs || 30000;
    console.log("🎣 Network hook aktif —", timeoutMs / 1000, "sn içinde oyunda tıkla (profil, fabrika…)");

    const origFetch = window.fetch;
    const origOpen = XMLHttpRequest.prototype.open;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
    let done = false;

    function finish(token, source) {
      if (done) return;
      done = true;
      window.fetch = origFetch;
      XMLHttpRequest.prototype.open = origOpen;
      XMLHttpRequest.prototype.setRequestHeader = origSetHeader;
      clearTimeout(timer);
      console.log("✅ Network'ten alındı:", source);
      copyText(token);
      console.log("%c" + token, "font-size:11px;word-break:break-all");
      return token;
    }

    window.fetch = function (input, init) {
      const headers = (init && init.headers) || {};
      const auth =
        headers.Authorization ||
        headers.authorization ||
        (typeof input === "object" && input.headers && input.headers.get && input.headers.get("Authorization"));
      const j = extractJwt(auth || "");
      if (j) finish(j, "fetch");
      return origFetch.apply(this, arguments);
    };

    const xhrHeaders = {};
    XMLHttpRequest.prototype.open = function () {
      xhrHeaders[this] = {};
      return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
      if (this && name && String(name).toLowerCase() === "authorization") {
        const j = extractJwt(value);
        if (j) finish(j, "xhr");
      }
      return origSetHeader.apply(this, arguments);
    };

    const timer = setTimeout(() => {
      if (!done) {
        done = true;
        window.fetch = origFetch;
        XMLHttpRequest.prototype.open = origOpen;
        XMLHttpRequest.prototype.setRequestHeader = origSetHeader;
        console.warn("⏱️ Süre doldu — grabToken() ile storage dene.");
      }
    }, timeoutMs);

    return "Hook kuruldu — oyunda bir işlem yap.";
  }

  /** Ekranda kopyala kutusu */
  function showTokenBox() {
    const r = grabToken({ copy: false });
    if (!r) return;
    const old = document.getElementById("dip-token-box");
    if (old) old.remove();
    const box = document.createElement("div");
    box.id = "dip-token-box";
    box.style.cssText =
      "position:fixed;z-index:2147483647;top:12px;right:12px;max-width:min(420px,92vw);" +
      "background:#111;color:#0f0;padding:14px;border-radius:10px;font:13px/1.4 monospace;" +
      "box-shadow:0 8px 32px #0008;border:1px solid #333";
    box.innerHTML =
      "<b style='color:#fff'>Diplomacia JWT</b> (" +
      (r.payload && r.payload.username ? r.payload.username : r.path) +
      ")<br><textarea id='dip-tok-ta' style='width:100%;height:88px;margin:8px 0;font:11px monospace'>" +
      r.token +
      "</textarea>" +
      "<button id='dip-copy-btn' style='padding:6px 12px;cursor:pointer'>📋 Kopyala</button> " +
      "<button id='dip-close-btn' style='padding:6px 12px;cursor:pointer'>✕</button>";
    document.body.appendChild(box);
    document.getElementById("dip-copy-btn").onclick = () => {
      const ta = document.getElementById("dip-tok-ta");
      ta.select();
      document.execCommand("copy");
      alert("Kopyalandı — Telegram bota yapıştır");
    };
    document.getElementById("dip-close-btn").onclick = () => box.remove();
    return r.token;
  }

  /** Debug — tüm storage anahtarlarını listele */
  function debugStorage() {
    console.table(
      ["localStorage", "sessionStorage"].flatMap((label) => {
        const s = label === "localStorage" ? localStorage : sessionStorage;
        const rows = [];
        for (let i = 0; i < s.length; i++) {
          const k = s.key(i);
          const v = (s.getItem(k) || "").slice(0, 80);
          rows.push({ store: label, key: k, preview: v + (v.length >= 80 ? "…" : "") });
        }
        return rows;
      })
    );
  }

  // Global export (konsoldan çağrı)
  window.grabToken = grabToken;
  window.grabTokenFromNetwork = grabTokenFromNetwork;
  window.showTokenBox = showTokenBox;
  window.debugStorage = debugStorage;

  console.log(
    "✅ Diplomacia token araçları yüklendi:\n" +
      "   grabToken()           — storage tara + panoya kopyala (ÖNERİLEN)\n" +
      "   grabTokenFromNetwork()— sonraki API isteğinden yakala\n" +
      "   showTokenBox()        — ekranda kopyala kutusu\n" +
      "   debugStorage()        — anahtar listesi (JWT yoksa)\n"
  );

  return grabToken();
})();
