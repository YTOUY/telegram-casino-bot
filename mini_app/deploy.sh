#!/bin/bash
# Скрипт для деплоя на Netlify
# Запустите: bash deploy.sh

echo "🚀 Деплой на Netlify..."

# Проверяем наличие Netlify CLI
if ! command -v netlify &> /dev/null; then
    echo "❌ Netlify CLI не установлен!"
    echo "Установите: npm install -g netlify-cli"
    exit 1
fi

# Переходим в папку скрипта
cd "$(dirname "$0")"

echo "📦 Деплой в продакшен..."
netlify deploy --prod

if [ $? -eq 0 ]; then
    echo "✅ Деплой успешно завершен!"
else
    echo "❌ Ошибка при деплое!"
    exit 1
fi
