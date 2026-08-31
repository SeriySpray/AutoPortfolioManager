#!/bin/bash
# ==============================================================================
# Direct Foreground Cloudflare Tunnel Runner (Shows live link directly on screen)
# ==============================================================================

if [ ! -f "cloudflared" ]; then
    ARCH=$(uname -m)
    if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
    else
        URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    fi
    curl -L "$URL" -o cloudflared
    chmod +x cloudflared
fi

echo "🚀 Запуск тунелю на порт 5055... Шукайте посилання https://xxx.trycloudflare.com нижче:"
./cloudflared tunnel --url http://127.0.0.1:5055
