#!/bin/bash
# ==============================================================================
# Cloudflare Zero-Conflict Tunnel Installer (Port 5055)
# ==============================================================================

echo "🌐 [1/3] Завантаження Cloudflare Tunnel бінарника..."
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
else
    CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
fi

if [ ! -f "cloudflared" ] || [ ! -s "cloudflared" ]; then
    echo "Завантаження з: $CLOUDFLARED_URL"
    curl -L "$CLOUDFLARED_URL" -o cloudflared
    chmod +x cloudflared
fi

INSTALL_DIR=$(pwd)

echo "🔧 [2/3] Налаштування фонового сервісу (quant-tunnel.service)..."
sudo tee /etc/systemd/system/quant-tunnel.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Cloudflare HTTPS Tunnel
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/cloudflared tunnel --url http://127.0.0.1:5055
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable quant-tunnel.service
sudo systemctl restart quant-tunnel.service

echo "🚀 [3/3] Очікування генерації HTTPS-посилання (5 секунд)..."
sleep 5

echo ""
echo "=================================================================="
echo "✅ ТУНЕЛЬ УСПІШНО АКТИВОВАНО!"
echo "------------------------------------------------------------------"
echo "🔗 ВАШЕ ПУБЛІЧНЕ ПОСИЛАННЯ:"
journalctl -u quant-tunnel.service -n 50 --no-pager -l | grep -o 'https://[-a-zA-Z0-9@:%._\+~#=]\+\.trycloudflare\.com' | tail -n 1
echo "------------------------------------------------------------------"
echo "💡 Якщо посилання вище не відобразилось, виконайте:"
echo "   ./run_tunnel_direct.sh"
echo "=================================================================="
