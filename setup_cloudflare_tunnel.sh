#!/bin/bash
# ==============================================================================
# Cloudflare Zero-Config Tunnel (100% Guaranteed Access without OCI Firewall issues)
# ==============================================================================

set -e

echo "🌐 [1/2] Завантаження Cloudflare Tunnel..."
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
else
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
fi

curl -sL "$CLOUDFLARED_URL" -o cloudflared
chmod +x cloudflared

echo "🚀 [2/2] Створення захищеного публічного HTTPS-тунелю до портів дашборду..."
echo "------------------------------------------------------------------"
echo "✅ За кілька секунд з'явиться пряме публічне посилання на ваш дашборд!"
echo "   (Працює В ОБХІД усіх фаєрволів Oracle, VCN, iptables та провайдерів)"
echo "------------------------------------------------------------------"

./cloudflared tunnel --url http://127.0.0.1:5000
