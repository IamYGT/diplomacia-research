# Diplomacia Research — PC'ye aktarma

## 1. Tarayıcıdan (arkadaşlar + sen)

Site (DNS aktif olduktan sonra):

**https://diplomacia.ygtlabs.ai/**

Tek tık arşiv:

**https://diplomacia.ygtlabs.ai/download/diplomacia-research.tar.gz**

## 2. SCP ile (Mac / Linux / WSL)

```bash
scp root@49.12.188.137:/var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/public/download/diplomacia-research.tar.gz ~/Downloads/
cd ~/Downloads && tar -xzf diplomacia-research.tar.gz
```

## 3. rsync — tüm klasör (canlı kopya)

```bash
rsync -avz --exclude='.git' \
  root@49.12.188.137:/var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/ \
  ~/diplomacia-research/
```

## 4. Windows (WinSCP / FileZilla)

| Alan | Değer |
|------|--------|
| Host | `49.12.188.137` |
| Protokol | SFTP |
| Uzak dosya | `/var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/public/download/diplomacia-research.tar.gz` |

## DNS

Cloudflare A kaydı eklendi: `diplomacia.ygtlabs.ai` → `49.12.188.137` (**DNS only**, gri bulut — origin wildcard SSL).

TTL propagate: birkaç dakika. Doğrulama: `dig +short diplomacia.ygtlabs.ai @1.1.1.1` → `49.12.188.137`

## Site yenileme (sunucuda)

```bash
python3 /var/www/vhosts/ygtlabs.ai/diplomacia.ygtlabs.ai/scripts/build_public_site.py
```
