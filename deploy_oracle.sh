#!/bin/bash
# ==============================================================================
# AutoPortfolioManager - Production Deployment for Oracle Cloud & Linux VPS
# ==============================================================================

set -e

echo "🚀 [1/5] Встановлення системних пакетів..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv git curl iptables-persistent netfilter-persistent
elif command -v dnf &> /dev/null; then
    sudo dnf update -y
    sudo dnf install -y python39 python39-devel python39-pip git curl iptables-services
fi

INSTALL_DIR=$(pwd)
echo "📂 Робоча директорія: $INSTALL_DIR"

echo "🐍 [2/5] Створення віртуального середовища та встановлення бібліотек..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "🔧 [3/5] Створення systemd сервісів (Gunicorn Web + Live Daemon)..."

# 1. Web Dashboard via Gunicorn (Production WSGI)
sudo tee /etc/systemd/system/quant-web.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Gunicorn Production Web Server
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app --timeout 120 --access-logfile - --error-logfile -
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 2. Real-Time Quant Daemon
sudo tee /etc/systemd/system/quant-daemon.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Real-Time Quant Trading Daemon
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

echo "🔥 [4/5] Розблокування портів у фаєрволі сервера (Port 5000 & 80)..."
# Oracle Linux specific iptables insertion at index 1 (before any REJECT rules)
sudo iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT || true
sudo iptables -I INPUT 1 -p tcp --dport 80 -j ACCEPT || true

if command -v netfilter-persistent &> /dev/null; then
    sudo netfilter-persistent save || true
fi

if command -v ufw &> /dev/null; then
    sudo ufw allow 5000/tcp || true
    sudo ufw allow 80/tcp || true
fi

if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --zone=public --add-port=5000/tcp --permanent || true
    sudo firewall-cmd --reload || true
fi

echo "🔄 [5/5] Перезапуск та активація сервісів..."
sudo systemctl daemon-reload
sudo systemctl enable quant-web.service
sudo systemctl enable quant-daemon.service
sudo systemctl restart quant-web.service
sudo systemctl restart quant-daemon.service

SERVER_IP=$(curl -s ifconfig.me || curl -s api.ipify.org || echo "YOUR_SERVER_IP")

echo ""
echo "=================================================="
echo "✅ РОЗГОРТАННЯ ЗАВЕРШЕНО УСПІШНО!"
echo "🌐 API та Веб-панель доступні за адресою: http://${SERVER_IP}:5000"
echo "🔍 Тест працездатності API:"
echo "   curl http://localhost:5000/api/cached-tickers"
echo "=================================================="
