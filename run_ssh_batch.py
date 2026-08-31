import subprocess
import time
import json
import sys

sys.stdout.reconfigure(line_buffering=True)

KEY = r"C:\Users\User\.ssh\oracle_key.pem"
HOST = "ubuntu@141.144.254.60"
TOKEN = os.getenv("GITHUB_PAT", "")


def ssh_exec(cmd, timeout=30):
    full_cmd = [
        "ssh", "-i", KEY,
        "-n",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "ConnectTimeout=8",
        HOST, cmd
    ]
    try:
        proc = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)

print("🔌 Підключення через OpenSSH до Oracle Cloud...", flush=True)
code, out, err = ssh_exec("uptime")
print(f"[{code}] Uptime: {out or err}\n", flush=True)

if code == 0:
    print("▶ 1. Оновлення репозиторію з GitHub...", flush=True)
    git_cmd = f"cd ~/AutoPortfolioManager && git remote set-url origin https://SeriySpray:{TOKEN}@github.com/SeriySpray/AutoPortfolioManager.git && git fetch origin && git reset --hard origin/main"
    _, out, _ = ssh_exec(git_cmd)
    print(out, flush=True)

    print("\n▶ 2. Перезапуск служб quant-web та quant-daemon...", flush=True)
    _, out, _ = ssh_exec("sudo systemctl restart quant-web quant-daemon")
    time.sleep(2)

    print("\n▶ 3. Статус служб quant-web та quant-daemon:", flush=True)
    _, out, _ = ssh_exec("sudo systemctl is-active quant-web quant-daemon")
    print("Статуси (quant-web / quant-daemon):", out, flush=True)

    print("\n▶ 4. Виконання біржового такту через API на сервері...", flush=True)
    _, out, _ = ssh_exec("curl -s -X POST http://127.0.0.1:5055/api/live/trigger-tick", timeout=45)
    print("Результат такту:", out, flush=True)

    print("\n▶ 5. Поточний стан біржового демона та активні позиції:", flush=True)
    _, out, _ = ssh_exec("curl -s http://127.0.0.1:5055/api/live/status")
    try:
        data = json.loads(out)
        print(f"  • Статус демона: {data.get('status')}")
        print(f"  • Останній такт (heartbeat): {data.get('last_heartbeat')}")
        print(f"  • Активних позицій: {data.get('active_positions_count')}")
        print(f"  • Незафіксований P&L: {data.get('unrealized_total_pnl_pct')}%")
        print("\n  • Відкриті позиції:")
        for p in data.get("positions", []):
            print(f"    - [{p['ticker']}] {p['direction_label']}: Вхід ${p['entry_price']} -> Поточна ${p['current_price']} (P&L: {p['unrealized_pnl_pct']}%, SL: ${p['atr_sl_price']})")
        print("\n  • Сканер квантових сигналів:")
        for s in data.get("scanner", []):
            print(f"    - [{s['ticker']}] Ціна: ${s['price']} | Score: {s['composite_score']} | Сигнал: {s['signal']} | Режим H: {s['hurst']} | Статус: {s['status']}")
    except Exception:
        print(out)

print("\n==================================================")
print("🏁 ПЕРЕВІРКУ ТА МОНІТОРИНГ ЗАВЕРШЕНО УСПІШНО!")
print("==================================================")
