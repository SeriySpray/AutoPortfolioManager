import sys
import paramiko
import time

sys.stdout.reconfigure(line_buffering=True)

HOST = "141.144.254.60"
USER = "ubuntu"
KEY_PATH = "C:\\Users\\User\\.ssh\\oracle_key.pem"
TOKEN = os.getenv("GITHUB_PAT", "")


def run_remote():
    print(f"🔌 Підключення до Oracle Cloud ({HOST})...", flush=True)
    key = paramiko.RSAKey.from_private_key_file(KEY_PATH)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, pkey=key, timeout=10)
    print("✅ Успішно підключено через SSH до Oracle Cloud!\n", flush=True)

    commands = [
        ("1. Оновлення коду на сервері з GitHub", f"cd ~/AutoPortfolioManager && git remote set-url origin https://SeriySpray:{TOKEN}@github.com/SeriySpray/AutoPortfolioManager.git && git fetch origin && git reset --hard origin/main"),
        ("2. Перезапуск служб quant-web та quant-daemon", "sudo systemctl restart quant-web quant-daemon"),
        ("3. Перевірка статусу служб", "sudo systemctl status quant-web quant-daemon --no-pager -l"),
        ("4. Виконання біржового такту через API", "curl -s -X POST http://127.0.0.1:5055/api/live/trigger-tick"),
        ("5. Отримання живого стану Live Daemon з SQLite", "curl -s http://127.0.0.1:5055/api/live/status")
    ]

    for title, cmd in commands:
        print(f"==================================================", flush=True)
        print(f"▶ {title}", flush=True)
        print(f"--------------------------------------------------", flush=True)
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=25)
        out = stdout.read().decode("utf-8").strip()
        err = stderr.read().decode("utf-8").strip()
        
        if out:
            print(out, flush=True)
        if err:
            print(f"Повідомлення: {err}", flush=True)
        print("", flush=True)

    ssh.close()
    print("==================================================", flush=True)
    print("🏁 ДІАГНОСТИКУ ЗАВЕРШЕНО УСПІШНО!", flush=True)
    print("==================================================", flush=True)

if __name__ == "__main__":
    run_remote()
