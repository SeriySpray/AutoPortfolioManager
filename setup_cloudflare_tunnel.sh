#!/bin/bash
# ==============================================================================
# Cloudflare Zero-Conflict Tunnel (Port 5055)
# ==============================================================================

set -e

echo "🌐 [1/3] Завантаження Cloudflare Tunnel..."
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

echo "🔧 [2/3] Налаштування фонового сервісу тунелю (quant-tunnel.service)..."
INSTALL_DIR=$(pwd)

sudo tee /etc/systemd/system/quant-tunnel.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Cloudflare HTTPS Tunnel
After=network.target quant-web.service

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/cloudflared tunnel --url http://127.0.0.1:5055
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable quant-tunnel.service
sudo systemctl restart quant-tunnel.service

echo "🚀 [3/3] Отримання публічного HTTPS посилання на дашборд..."
sleep 4

echo ""
echo "=================================================================="
echo "✅ КВАНТОВИЙ ДАШБОРД ТА КАМЕРА ТЕПЕР ПРАЦЮЮТЬ ПАРАЛЕЛЬНО 24/7!"
echo "------------------------------------------------------------------"
echo "🔗 ВАШЕ ПУБЛІЧНЕ HTTPS ПОСИЛАННЯ:"
journalctl -u quant-tunnel.service -n 50 --no-pager -l | grep -o 'https://[-a-zA-Z0-9@:%._\+~#=]\+\.trycloudflare\.com' | tail -n 1
echo "------------------------------------------------------------------"
echo "💡 Якщо посилання вище порожнє, виконайте:"
echo "   journalctl -u quant-tunnel.service -n 25 --no-pager -l"
echo "=================================================================="
