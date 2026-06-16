"""Tarayıcı konsolundan JWT alma — bot içinde paylaşılan snippet."""

from __future__ import annotations

import subprocess


# Tek satır V2 — || yok (Telegram/kopya bazen || siler → SyntaxError)
CONSOLE_GRAB_TOKEN_ONELINER = (
    "(()=>{const J=/eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+/;"
    "const g=s=>{const m=String(s?s:'').match(J);return m?m[0]:null};"
    "const cp=t=>{try{const a=document.createElement('textarea');a.value=t;"
    "a.style.cssText='position:fixed;top:0;left:0;width:2px;height:2px;opacity:0';"
    "document.body.appendChild(a);a.focus();a.select();const ok=document.execCommand('copy');"
    "a.remove();return ok}catch(e){return false}};const h=[];"
    "[localStorage,sessionStorage].forEach(S=>{for(let i=0;i<S.length;i++){"
    "const v=S.getItem(S.key(i)),t=g(v);if(t)h.push(t);let p={};try{p=JSON.parse(v)}catch(e){}"
    "try{Object.values(p).forEach(x=>{const j=g(x);if(j)h.push(j)})}catch(e){}}});"
    "const t=[...new Set(h)][0];"
    "if(!t)return console.warn('JWT yok — giriş yap, F5, tekrar dene');"
    "const ok=cp(t);"
    "console.log((ok?'📋 Panoya kopyalandı':'⚠️ Elle kopyala')+'\\n'+t);"
    "if(!ok)prompt('Token — Ctrl+C, Enter:',t);return t})();"
)

# En kısa yedek — syntax hatası olursa bunu dene
CONSOLE_GRAB_TOKEN_FALLBACK = (
    "console.log(localStorage.getItem('token')||localStorage.getItem('accessToken')"
    "||sessionStorage.getItem('token')||'JWT yok — giriş yap, F5')"
)


def validate_oneliner_js() -> None:
    """Node ile syntax kontrolü — CI/test."""
    import tempfile

    script = CONSOLE_GRAB_TOKEN_ONELINER + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
        path = f.name
    proc = subprocess.run(
        ["node", "--check", path],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        raise SyntaxError(proc.stderr or proc.stdout or "invalid JS oneliner")


def format_console_script_telegram() -> str:
    """Telegram'dan konsola kopyalamak için düz metin (parse_mode yok)."""
    return (
        "📋 Konsol kodu\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "1. diplomacia.com.tr → giriş yap\n"
        "2. F12 → Console\n"
        "3. Aşağıdaki satırın TAMAMINI yapıştır → Enter\n"
        "   ⚠️ Satırı bölme / düzenleme — || veya () silinirse hata verir\n"
        "4. Çıkan eyJ… token'ı bu sohbete yapıştır\n\n"
        f"{CONSOLE_GRAB_TOKEN_ONELINER}\n\n"
        "💡 SyntaxError alırsan yedek (tek satır):\n"
        f"{CONSOLE_GRAB_TOKEN_FALLBACK}\n\n"
        "💡 NotAllowedError = normal — konsoldaki eyJ… satırını elle kopyala."
    )


def format_console_script_html() -> str:
    """Kısa HTML özet + kod referansı (uzun snippet ayrı mesajda)."""
    import html as html_mod

    return (
        "<b>📋 Konsol kodu gönderildi</b>\n\n"
        "Sonraki mesajdaki tek satırı tarayıcı konsoluna yapıştır.\n"
        f"<code>{html_mod.escape(CONSOLE_GRAB_TOKEN_ONELINER[:72])}…</code>"
    )
