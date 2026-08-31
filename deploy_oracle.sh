#!/bin/bash
# ==============================================================================
# AutoPortfolioManager - Safe Multi-Project Deployment for Oracle Cloud
# Coexists cleanly with existing projects (cameras, web servers, docker containers)
# ==============================================================================

set -e

echo "🚀 [1/5] Встановлення необхідних пакетів..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv git curl
elif command -v dnf &> /dev/null; then
    sudo dnf update -y
    sudo dnf install -y python39 python39-devel python39-pip git curl
fi

INSTALL_DIR=$(pwd)
echo "📂 Робоча директорія: $INSTALL_DIR"

echo "🐍 [2/5] Створення віртуального середовища Python..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ [3/5] Налаштування ізольованих systemd сервісів на порту 5000..."

# 1. Gunicorn Backend on dedicated port 5000
sudo tee /etc/systemd/system/quant-web.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Gunicorn Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app --timeout 180 --access-logfile - --error-logfile -
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

echo "🔥 [4/5] Розблокування порту 5000 в iptables..."
sudo iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT 2>/dev/null || true

if command -v ufw &> /dev/null; then
    sudo ufw allow 5000/tcp || true
fi

echo "🔄 [5/5] Запуск сервісів..."
sudo systemctl daemon-reload
sudo systemctl enable quant-web.service
sudo systemctl enable quant-daemon.service
sudo systemctl restart quant-web.service
sudo systemctl restart quant-daemon.service

echo ""
echo "=================================================="
echo "✅ КВАНТОВИЙ СЕРВІС УСПІШНО ЗАПУЩЕНО!"
echo "   • Працює в ізоляції на порті 5000, не зачіпаючи камеру"
echo "--------------------------------------------------"
echo "💡 ДЛЯ ОТРИМАННЯ ПРЯМОГО ПУБЛІЧНОГО HTTPS ПОСИЛАННЯ:"
echo "   ./setup_cloudflare_tunnel.sh"
echo "=================================================="
