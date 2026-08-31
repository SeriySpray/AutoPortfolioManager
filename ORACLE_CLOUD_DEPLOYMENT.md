# ☁️ Керівництво з Розгортання та Запуску Quant Engine на Сервері Oracle Cloud

Цей посібник містить повну покрокову інструкцію для розгортання квантової платформи та **цілодобового автономного демона реального часу (24/7 Real-Time Live Daemon)** на вашому сервері Oracle Cloud (OCI) або будь-якому Linux VPS.

---

## 🏗️ 1. Архітектура реального часу на сервері

На сервері запускаються два паралельні незалежні процеси через `systemd`:
1. **`quant-daemon.service` (`live_trader_daemon.py`):**
   - Фоновий воркер, який постійно отримує свіжі ринкові дані (OHLCV).
   - Оцінює квантові фактори ($w_{\text{MOM}}, w_{\text{MR}}, \text{Hurst}, \text{ATR}, \Delta\text{Slope}$).
   - Керує активними позиціями, відстежує динамічний **ATR Stop-Loss** та фіксує P&L у базі даних `live_portfolio.db`.
   - Надсилає миттєві сповіщення про відкриття/закриття угод у **Telegram**.
2. **`quant-web.service` (`app.py`):**
   - Веб-панель керування на порті `:5000` з доступом через браузер з будь-якого пристрою.

---

## 🚀 2. Швидкий запуск в 1 команду (1-Click Deployment)

### Крок 2.1. Підключіться до вашого сервера через SSH:
```bash
ssh ubuntu@<IP_АДРЕСА_ВАШОГО_СЕРВЕРА_ORACLE>
# або для Oracle Linux:
ssh opc@<IP_АДРЕСА_ВАШОГО_СЕРВЕРА_ORACLE>
```

### Крок 2.2. Завантажте файли проєкту на сервер:
```bash
# Клонуйте ваш репозиторій або скопіюйте файли через SCP / rsync:
git clone https://github.com/your-username/AutoPortfolioManager.git
cd AutoPortfolioManager
```

### Крок 2.3. Запустіть автоматичний скрипт встановлення:
```bash
chmod +x deploy_oracle.sh
./deploy_oracle.sh
```

Скрипт автоматично:
- Встановить необхідні системні пакети (Python, pip, venv, gcc);
- Створить віртуальне середовище та встановить усі математичні бібліотеки;
- Зареєструє та запустить системні сервіси `quant-web` та `quant-daemon`;
- Налаштує автозапуск при перезавантаженні сервера.

---

## 🔒 3. Відкриття порту 5000 в Oracle Cloud Security List

Щоб веб-інтерфейс був доступний у браузері, необхідно дозволити вхідний трафік у панелі Oracle Cloud:

1. Відкрийте **Oracle Cloud Console** &rarr; **Networking** &rarr; **Virtual Cloud Networks (VCN)**.
2. Перейдіть у вашу VCN &rarr; **Security Lists** &rarr; **Default Security List**.
3. Натисніть **Add Ingress Rules** і додайте правило:
   - **Source CIDR:** `0.0.0.0/0`
   - **IP Protocol:** `TCP`
   - **Destination Port Range:** `5000`
   - **Description:** `Quant Web Dashboard`
4. На самому сервері (якщо використовується iptables на Oracle Linux):
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo netfilter-persistent save || sudo service iptables save
```

---

## 📱 4. Налаштування Telegram-сповіщень у реальному часі (Опціонально)

Щоб отримувати сигнали на телефон у Telegram:
1. Створіть бота в [@BotFather](https://t.me/botfather) та отримайте `TELEGRAM_BOT_TOKEN`.
2. Дізнайтеся ваш `chat_id` через [@userinfobot](https://t.me/userinfobot).
3. Додайте їх у змінні оточення сервера:
```bash
echo "export TELEGRAM_BOT_TOKEN='ваш_токен'" >> ~/.bashrc
echo "export TELEGRAM_CHAT_ID='ваш_chat_id'" >> ~/.bashrc
source ~/.bashrc
```
4. Перезапустіть демона:
```bash
sudo systemctl restart quant-daemon
```

---

## 🐳 5. Альтернативний запуск через Docker Compose

Якщо ви віддаєте перевагу контейнерам Docker:
```bash
# Встановлення Docker та Docker Compose
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER

# Запуск платформи
docker-compose up -d --build
```

---

## 🛠️ 6. Корисні команди для моніторингу сервера

- **Перевірити статус торгового демона:**
  ```bash
  sudo systemctl status quant-daemon
  ```
- **Переглянути живі логи у реальному часі:**
  ```bash
  journalctl -u quant-daemon -f
  ```
- **Перезапустити процеси:**
  ```bash
  sudo systemctl restart quant-daemon quant-web
  ```
- **Перевірити активні позиції у базі SQLite:**
  ```bash
  sqlite3 live_portfolio.db "SELECT * FROM positions;"
  ```
