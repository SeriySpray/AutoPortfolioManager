#!/bin/bash
# ==============================================================================
# AutoPortfolioManager - 1-Click Oracle Cloud Deployment Script
# Supports: Ubuntu 20.04/22.04/24.04 LTS & Oracle Linux 8/9
# ==============================================================================

set -e

echo "🚀 [1/6] Оновлення системних пакетів та встановлення залежностей..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv git curl build-essential libpq-dev
elif command -v dnf &> /dev/null; then
    sudo dnf update -y
    sudo dnf install -y python39 python39-devel python39-pip git curl gcc gcc-c++
fi

INSTALL_DIR=$(pwd)
echo "📂 Робоча директорія: $INSTALL_DIR"

echo "🐍 [2/6] Створення віртуального середовища Python..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "🔧 [3/6] Налаштування systemd сервісів для цілодобової роботи 24/7..."

# 1. Web Dashboard Service
sudo tee /etc/systemd/system/quant-web.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Web Dashboard
After=network.target

[Service]
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 2. Real-Time Quant Daemon Service
sudo tee /etc/systemd/system/quant-daemon.service > /dev/null <<EOF
[Unit]
Description=AutoPortfolioManager Real-Time Trading Daemon
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

echo "🔥 [4/6] Відкриття портів у фаєрволі (Port 5000)..."
if command -v ufw &> /dev/null; then
    sudo ufw allow 5000/tcp || true
elif command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --zone=public --add-port=5000/tcp --permanent || true
    sudo firewall-cmd --reload || true
fi

echo "🔄 [5/6] Активація та запуск сервісів..."
sudo systemctl daemon-reload
sudo systemctl enable quant-web.service
sudo systemctl enable quant-daemon.service
sudo systemctl restart quant-web.service
sudo systemctl restart quant-daemon.service

echo "✅ [6/6] УСПІШНО ВСТАНОВЛЕНО ТА ЗАПУЩЕНО!"
echo "--------------------------------------------------"
echo "🌐 Веб-панель: http://$(curl -s ifconfig.me):5000"
echo "📊 Статус веб-сервісу: sudo systemctl status quant-web"
echo "🤖 Статус реального демона: sudo systemctl status quant-daemon"
echo "📜 Перегляд логів у реальному часі: journalctl -u quant-daemon -f"
echo "--------------------------------------------------"
