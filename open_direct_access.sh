#!/bin/bash
# ==============================================================================
# 100% Direct Public IP Access for Oracle Cloud (Without Cloudflare)
# Completely removes Oracle's default blocking iptables REJECT rules
# ==============================================================================

set -e

echo "🔥 [1/3] Повне скидання блокуючих правил фаєрволу Oracle (iptables flush)..."
# Oracle Cloud sets a default REJECT rule at the OS level. We set default policy to ACCEPT:
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT
sudo iptables -F
sudo iptables -X
sudo iptables -t nat -F
sudo iptables -t mangle -F

# Save clean ACCEPT policy across reboots
if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save || true
fi
if [ -d "/etc/iptables" ]; then
    sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null || true
fi

echo "⚙️ [2/3] Налаштування Gunicorn на прослуховування всіх інтерфейсів (0.0.0.0:5055)..."
INSTALL_DIR=$(pwd)

sudo tee /etc/systemd/system/quant-web.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Direct Gunicorn Web Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:5055 app:app --timeout 180 --access-logfile - --error-logfile -
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
Environment=PORT=5055

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart quant-web.service

SERVER_IP=$(curl -s ifconfig.me || curl -s api.ipify.org || echo "YOUR_SERVER_IP")

echo "✅ [3/3] ПРЯМИЙ ДОСТУП АКТИВОВАНО!"
echo "=================================================="
echo "🌐 Пряме посилання у браузері:"
echo "   http://${SERVER_IP}:5055"
echo "=================================================="
echo "💡 ВАЖЛИВО ДЛЯ ORACLE CLOUD CONSOLE:"
echo "   В Ingress Rules вашої VCN має бути додано порт 5055 (TCP, 0.0.0.0/0)"
echo "=================================================="
