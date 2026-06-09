#!/usr/bin/env python3
"""Markdown → HTML + public index + indirilebilir arşiv (hassas veri scrub)."""
import html
import json
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PUBLIC = ROOT / "public"
REPORTS = PUBLIC / "reports"
DATA = PUBLIC / "data"
DOWNLOAD = PUBLIC / "download"
EXPORT = ROOT / "export"

SENSITIVE_KEYS = {"email", "password", "token", "authorization", "purchaseToken"}


def scrub_obj(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.lower() in SENSITIVE_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = scrub_obj(v)
        return out
    if isinstance(obj, list):
        return [scrub_obj(x) for x in obj]
    return obj


def md_to_html(text: str) -> str:
    """Minimal markdown → HTML (bağımlılık yok)."""
    lines = text.split("\n")
    out = []
    in_code = False
    in_table = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if "|" in line and line.strip().startswith("|"):
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            tag = "th" if not out or out[-1] == "<table>" else "td"
            if tag == "th":
                out.append("<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{inline_md(c)}</td>" for c in cells) + "</tr>")
            continue
        elif in_table:
            out.append("</table>")
            in_table = False
        if line.startswith("### "):
            out.append(f"<h3>{inline_md(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline_md(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline_md(line[2:])}</h1>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.startswith("- "):
            out.append(f"<li>{inline_md(line[2:])}</li>")
        elif line.strip() == "":
            out.append("")
        else:
            out.append(f"<p>{inline_md(line)}</p>")
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")
    body = "\n".join(out)
    body = re.sub(r"(<li>.*?</li>\n?)+", lambda m: "<ul>" + m.group(0) + "</ul>", body, flags=re.S)
    return body


def inline_md(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def page_shell(title: str, body: str, breadcrumb: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} — Diplomacia Research</title>
  <link rel="stylesheet" href="/assets/site.css">
</head>
<body>
  <header class="top">
    <a href="/" class="logo">Diplomacia Research</a>
    <nav>
      <a href="/">Özet</a>
      <a href="/guide/">İnteraktif Rehber</a>
      <a href="/reports/">Raporlar</a>
      <a href="/data/">Ham veri</a>
      <a href="/download/diplomacia-research.tar.gz">İndir (.tar.gz)</a>
    </nav>
  </header>
  <main class="content">
    {f'<p class="crumb"><a href="/">Ana sayfa</a> / {html.escape(breadcrumb)}</p>' if breadcrumb else ''}
    {body}
  </main>
  <footer class="foot">Strategos RE · {datetime.now(timezone.utc).strftime("%Y-%m-%d")} UTC · İç araştırma</footer>
</body>
</html>"""


def build_reports():
    REPORTS.mkdir(parents=True, exist_ok=True)
    index_items = []
    for md in sorted(DOCS.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        body = md_to_html(text)
        out_name = md.stem + ".html"
        (REPORTS / out_name).write_text(
            page_shell(md.stem, body, md.name), encoding="utf-8"
        )
        title = md.stem
        m = re.search(r"^#\s+(.+)", text)
        if m:
            title = m.group(1).strip()
        index_items.append((md.name, out_name, title))
    # reports index
    links = "".join(
        f'<li><a href="/reports/{fn}"><code>{md}</code> — {html.escape(t)}</a></li>'
        for md, fn, t in index_items
    )
    (REPORTS / "index.html").write_text(
        page_shell("Raporlar", f"<h1>Raporlar</h1><ul class='doc-list'>{links}</ul>", "Raporlar"),
        encoding="utf-8",
    )
    return index_items


def copy_data():
    if DATA.exists():
        shutil.rmtree(DATA)
    shutil.copytree(ROOT / "output", DATA)
    for jf in DATA.rglob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            jf.write_text(json.dumps(scrub_obj(data), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    if (DOCS / "api-endpoints.json").exists():
        shutil.copy(DOCS / "api-endpoints.json", DATA / "api-endpoints.json")


def build_data_index():
    sections = ["crawl", "exploits", "security", "reverse"]
    blocks = ["<h1>Ham veri (JSON)</h1><p>E-posta ve token alanları scrub edildi.</p>"]
    for sec in sections:
        d = DATA / sec
        if not d.is_dir():
            continue
        blocks.append(f"<h2>{sec}/</h2><ul>")
        for f in sorted(d.glob("*.json")):
            rel = f.relative_to(PUBLIC)
            blocks.append(f'<li><a href="/{rel.as_posix()}">{f.name}</a></li>')
        blocks.append("</ul>")
    root_json = list(DATA.glob("*.json"))
    if root_json:
        blocks.append("<h2>root</h2><ul>")
        for f in sorted(root_json):
            rel = f.relative_to(PUBLIC)
            blocks.append(f'<li><a href="/{rel.as_posix()}">{f.name}</a></li>')
        blocks.append("</ul>")
    (DATA / "index.html").write_text(page_shell("Ham veri", "\n".join(blocks), "Ham veri"), encoding="utf-8")


def build_home(report_items):
    highlights = """
    <section class="hero">
      <h1>Diplomacia / Strategos Araştırma Hub</h1>
      <p class="lead">API tersine mühendislik, güvenlik audit, ekonomi exploit ve oyun mekanikleri — <strong>diplomacia.com.tr</strong></p>
      <div class="stats">
        <div class="stat"><span class="n">213</span><span class="l">REST endpoint</span></div>
        <div class="stat"><span class="n">52+</span><span class="l">Exploit testi</span></div>
        <div class="stat"><span class="n">48+</span><span class="l">API crawl</span></div>
        <div class="stat"><span class="n">12</span><span class="l">Rapor</span></div>
      </div>
      <p class="cta">
        <a class="btn" href="/guide/">İnteraktif Ustalık Rehberi →</a>
        <a class="btn btn-secondary" href="/download/diplomacia-research.tar.gz">Tüm klasörü indir (tar.gz)</a>
      </p>
    </section>
    <section class="grid">
      <div class="card"><h2>Öne çıkan bulgular</h2>
        <ul>
          <li><strong>Quest claim:</strong> <code>POST /quests/{quest_key}/claim</code> — UUID değil key (work_1 → +5k)</li>
          <li><strong>Tutorial farm:</strong> <code>complete-step</code> tek sefer ~200k (yeni hesap)</li>
          <li><strong>Factory farm:</strong> work döngüsü ~2.4k / 10 dk</li>
          <li><strong>Factory join:</strong> rakip fabrikaya işçi olarak katılım mümkün</li>
          <li><strong>Stack:</strong> Expo SDK 55, React 19, Socket.IO EIO4, Leaflet 1.9.4</li>
        </ul>
      </div>
      <div class="card"><h2>Raporlar</h2><ul class="doc-list compact">
    """
    for md, fn, title in report_items[:8]:
        highlights += f'<li><a href="/reports/{fn}">{html.escape(title)}</a></li>'
    highlights += """</ul><p><a href="/reports/">Tüm raporlar →</a></p></div></section>"""
    (PUBLIC / "index.html").write_text(page_shell("Ana sayfa", highlights), encoding="utf-8")


def build_archive():
    EXPORT.mkdir(parents=True, exist_ok=True)
    DOWNLOAD.mkdir(parents=True, exist_ok=True)
    archive = EXPORT / "diplomacia-research.tar.gz"
    pub_archive = DOWNLOAD / "diplomacia-research.tar.gz"
    # Scrubbed output for public archive
    scrub_dir = EXPORT / "_scrubbed_output"
    if scrub_dir.exists():
        shutil.rmtree(scrub_dir)
    shutil.copytree(ROOT / "output", scrub_dir)
    for jf in scrub_dir.rglob("*.json"):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            jf.write_text(json.dumps(scrub_obj(data), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    with tarfile.open(archive, "w:gz") as tar:
        for name in ["docs", "scripts", "public"]:
            p = ROOT / name
            if p.exists():
                tar.add(p, arcname=f"diplomacia-research/{name}")
        tar.add(scrub_dir, arcname="diplomacia-research/output")
        readme = (
            "Diplomacia Research Export\n"
            f"Generated: {datetime.now(timezone.utc).isoformat()}\n"
            "output/ JSON email ve token alanları scrub edildi.\n"
            "Auth token bu arşivde YOK.\n"
        )
        import tempfile
        import os
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tf:
            tf.write(readme)
            tmp = tf.name
        tar.add(tmp, arcname="diplomacia-research/README.txt")
        os.unlink(tmp)
    shutil.copy(archive, pub_archive)


def refresh_guide_meta():
    regen = ROOT / "scripts" / "regenerate-guide-meta.py"
    if regen.is_file():
        subprocess.run(["python3", str(regen)], check=True, cwd=str(ROOT))


def verify_guide():
    verify = ROOT / "scripts" / "verify-guide.sh"
    if verify.is_file():
        subprocess.run(["bash", str(verify)], check=True, cwd=str(ROOT))


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "assets").mkdir(exist_ok=True)
    items = build_reports()
    copy_data()
    refresh_guide_meta()
    build_data_index()
    build_home(items)
    build_archive()
    verify_guide()
    print(f"OK public={PUBLIC} archive={DOWNLOAD / 'diplomacia-research.tar.gz'}")


if __name__ == "__main__":
    main()
