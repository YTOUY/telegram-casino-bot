#!/bin/bash
# Скрипт для просмотра логов бота с фильтрацией по throws

echo "🔍 Поиск записей о throws в логах..."
echo ""

# Если бот запущен как systemd сервис
if systemctl is-active --quiet telegram-bot 2>/dev/null; then
    echo "📋 Последние записи о throws:"
    journalctl -u telegram-bot -n 200 | grep -i "throws\|🎲\|💾\|📤\|displayGameResult"
    echo ""
    echo "❌ Ошибки связанные с throws:"
    journalctl -u telegram-bot -n 200 | grep -i "❌.*throws\|критическая.*throws\|error.*throws"
else
    echo "⚠️ Бот не запущен как systemd сервис"
    echo "Проверьте логи вручную или через screen/tmux"
fi

