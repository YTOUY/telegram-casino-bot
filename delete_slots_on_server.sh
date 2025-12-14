#!/bin/bash
# Скрипт для удаления стикера slots_base
# Скопируйте этот скрипт на сервер и выполните: bash delete_slots_on_server.sh

cd /opt/telegram_bot_test 2>/dev/null || cd /opt/telegram_bot 2>/dev/null || echo "⚠️ Не удалось перейти в стандартную директорию"

if [ -f "database.db" ]; then
    echo "✅ Найдена база данных: $(pwd)/database.db"
    echo "🗑️ Удаляю стикеры со слотами..."
    sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
    DELETED=$(sqlite3 database.db "SELECT changes();")
    echo "✅ Удалено стикеров: $DELETED"
else
    echo "❌ База данных не найдена в текущей директории"
    echo "🔍 Ищу базу данных..."
    DB_PATH=$(find /opt /home /root -name "database.db" -type f 2>/dev/null | head -1)
    if [ -n "$DB_PATH" ]; then
        echo "✅ Найдена база данных: $DB_PATH"
        sqlite3 "$DB_PATH" "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
        DELETED=$(sqlite3 "$DB_PATH" "SELECT changes();")
        echo "✅ Удалено стикеров: $DELETED"
    else
        echo "❌ База данных не найдена!"
    fi
fi







