#!/usr/bin/env bash
set -euo pipefail

WEBHOOK_URL="https://dostigator.bitrix24.ru/rest/1/rio3f7m0fudq3ts2/"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Bitrix24 MCP — установка ==="

# 1. Проверяем Python
if ! command -v python3 &>/dev/null; then
    echo "ОШИБКА: python3 не найден. Установите Python 3.11+ и повторите."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(sys.version_info >= (3,11))')
if [ "$PY_VER" != "True" ]; then
    echo "ОШИБКА: нужен Python 3.11+. Текущая версия: $(python3 --version)"
    exit 1
fi

# 2. Создаём виртуальное окружение
VENV="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV" ]; then
    echo ">> Создаю виртуальное окружение..."
    python3 -m venv "$VENV"
fi

PY="$VENV/bin/python"
PIP="$VENV/bin/pip"

# 3. Устанавливаем зависимости
echo ">> Устанавливаю зависимости..."
"$PIP" install --upgrade pip -q
"$PIP" install mcp httpx python-dotenv -q

# 4. Создаём .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ">> Создаю .env..."
    echo "BITRIX24_WEBHOOK_URL=$WEBHOOK_URL" > "$SCRIPT_DIR/.env"
else
    echo ">> .env уже существует, пропускаю."
fi

# 5. Регистрируем MCP-сервер в Claude Code
if command -v claude &>/dev/null; then
    echo ">> Регистрирую MCP-сервер в Claude Code..."
    claude mcp add bitrix24 "$PY" "$SCRIPT_DIR/server.py" \
        -e "BITRIX24_WEBHOOK_URL=$WEBHOOK_URL" 2>/dev/null && \
        echo ">> MCP-сервер 'bitrix24' зарегистрирован." || \
        echo ">> Не удалось зарегистрировать автоматически (см. ниже)."
else
    echo ">> claude CLI не найден — добавьте MCP вручную (см. ниже)."
fi

# 6. Проверяем соединение с Bitrix24
echo ">> Проверяю соединение с Bitrix24..."
"$PY" - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else '.')
from dotenv import load_dotenv
load_dotenv()
import httpx, json, os

url = os.environ.get("BITRIX24_WEBHOOK_URL", "").rstrip("/")
try:
    r = httpx.get(f"{url}/profile.json", timeout=10)
    data = r.json()
    if "result" in data:
        u = data["result"]
        print(f"✓ Подключено! Пользователь: {u.get('NAME','')} {u.get('LAST_NAME','')} (ID {u.get('ID','')})")
    else:
        print(f"✗ Ответ: {json.dumps(data, ensure_ascii=False)}")
except Exception as e:
    print(f"✗ Ошибка соединения: {e}")
PYEOF

echo ""
echo "=== Готово ==="
echo ""
echo "Если claude CLI не нашёлся, добавьте MCP вручную:"
echo ""
echo "  claude mcp add bitrix24 $PY $SCRIPT_DIR/server.py \\"
echo "    -e BITRIX24_WEBHOOK_URL=$WEBHOOK_URL"
echo ""
echo "Затем перезапустите Claude Code — появятся инструменты задач Bitrix24."
