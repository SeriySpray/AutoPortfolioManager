#!/usr/bin/env python3
import os
import sys
import socket
import urllib.request
import json
import subprocess

print("==================================================")
print("🔍 ДІАГНОСТИКА СЕРВЕРА AUTOPORTFOLIO // ORACLE CLOUD")
print("==================================================")

# 1. Check Public IP
try:
    public_ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode("utf-8").strip()
    print(f"🌐 Публічна IP-адреса сервера: {public_ip}")
except Exception as e:
    public_ip = "UNKNOWN"
    print(f"⚠️ Не вдалося визначити публічну IP: {e}")

# 2. Check Port 5000 Listening
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
result = sock.connect_ex(("127.0.0.1", 5000))
if result == 0:
    print("✅ Веб-сервер активний і слухає порт 5000 (localhost:5000)")
else:
    print("❌ Веб-сервер НЕ запущено або порт 5000 закритий локально!")
sock.close()

# 3. Test Local API Endpoints
endpoints = [
    ("/api/cached-tickers", "Список збережених компаній"),
    ("/api/live/status", "Статус торгового демона"),
    ("/api/math-variables", "Квантові змінні")
]

print("\n🧪 ТЕСТУВАННЯ ВНУТРІШНІХ API ЕНДПОІНТІВ:")
for path, desc in endpoints:
    url = f"http://127.0.0.1:5000{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.getcode()
            headers = dict(response.info())
            cors = headers.get("Access-Control-Allow-Origin", "NONE")
            print(f"  • [{status}] {path} ({desc}) -> CORS: {cors} ✅")
    except Exception as e:
        print(f"  • [ПОМИЛКА] {path}: {e} ❌")

# 4. Check Linux iptables Rules
print("\n🔥 ПЕРЕВІРКА ФАЄРВОЛУ СЕРВЕРА (iptables / UFW):")
if os.name != 'nt':
    try:
        out = subprocess.check_output(["sudo", "iptables", "-L", "INPUT", "-v", "-n"], stderr=subprocess.STDOUT).decode("utf-8")
        if "5000" in out:
            print("  • Правило порту 5000 знайдено в iptables: ACCEPT ✅")
        else:
            print("  • ⚠️ Порт 5000 відсутній у правилах iptables! Виконайте: sudo iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT")
    except Exception as e:
        print(f"  • Перевірка iptables пропущена ({e})")
else:
    print("  • Локальна ОС: Windows (перевірка iptables не потрібна)")

print("\n==================================================")
print(f"🎯 ДЛЯ ДОСТУПУ З БРАУЗЕРА ВІДКРИЙТЕ: http://{public_ip}:5000")
print("Якщо сторінка не завантажується, перевірте Ingress Rules у консолі Oracle Cloud!")
print("==================================================")
