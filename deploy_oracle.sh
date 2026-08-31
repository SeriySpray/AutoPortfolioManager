#!/bin/bash
# ==============================================================================
# AutoPortfolioManager - Bulletproof Production Deployment for Oracle Cloud
# Includes: Gunicorn + Nginx Reverse Proxy on Port 80 + Iptables Unblock
# ==============================================================================

set -e

echo "🚀 [1/6] Встановлення системних пакетів та Nginx..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv git curl nginx iptables-persistent netfilter-persistent
elif command -v dnf &> /dev/null; then
    sudo dnf update -y
    sudo dnf install -y python39 python39-devel python39-pip git curl nginx iptables-services
fi

INSTALL_DIR=$(pwd)
echo "📂 Робоча директорія: $INSTALL_DIR"

echo "🐍 [2/6] Налаштування Python venv та бібліотек..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "🔧 [3/6] Налаштування Nginx на стандартний порт 80..."
sudo tee /etc/nginx/conf.d/quant.conf > /dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 180s;
        proxy_connect_timeout 180s;
    }
}
EOF

# Remove default nginx site if on Ubuntu/Debian
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo systemctl restart nginx || sudo service nginx restart

echo "⚙️ [4/6] Створення systemd сервісів (Gunicorn Web + Live Daemon)..."

# 1. Gunicorn Web Service
sudo tee /etc/systemd/system/quant-web.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Gunicorn Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app:app --timeout 180 --access-logfile - --error-logfile -
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 2. Real-Time Quant Daemon
sudo tee /etc/systemd/system/quant-daemon.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Real-Time Quant Daemon
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python live_trader_daemon.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "🔥 [5/6] Повне розблокування фаєрволу сервера (Політика ACCEPT для Port 80 та 5000)..."
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT 1 -p tcp --dport 443 -j ACCEPT 2>/dev/null || true

if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save || true
fi

if command -v ufw &> /dev/null; then
    sudo ufw allow 80/tcp || true
    sudo ufw allow 5000/tcp || true
    sudo ufw allow 443/tcp || true
fi

if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --zone=public --add-port=80/tcp --permanent 2>/dev/null || true
    sudo firewall-cmd --zone=public --add-port=5000/tcp --permanent 2>/dev/null || true
    sudo firewall-cmd --reload 2>/dev/null || true
fi

echo "🔄 [6/6] Запуск та активація сервісів..."
sudo systemctl daemon-reload
sudo systemctl enable quant-web.service
sudo systemctl enable quant-daemon.service
sudo systemctl restart quant-web.service
sudo systemctl restart quant-daemon.service

SERVER_IP=$(curl -s ifconfig.me || curl -s api.ipify.org || echo "YOUR_SERVER_IP")

echo ""
echo "=================================================="
echo "✅ РОЗГОРТАННЯ ЗАВЕРШЕНО УСПІШНО!"
echo "🌐 1. Стандартний веб-доступ (Port 80): http://${SERVER_IP}"
echo "🌐 2. Прямий доступ (Port 5000):        http://${SERVER_IP}:5000"
echo "--------------------------------------------------"
echo "💡 ЯКЩО ПОРТИ ВСЕ ЩЕ БЛОКУЮТЬСЯ ОРАКЛОМ, ЗАПУСТІТЬ ТУНЕЛЬ:"
echo "   ./setup_cloudflare_tunnel.sh"
echo "=================================================="
