#!/bin/bash
# Скрипт для поиска базы данных и удаления стикера slots_base

echo "🔍 Ищу базу данных на сервере..."
echo "=================================================="

# Возможные пути к базе данных
DB_PATHS=(
    "/opt/telegram_bot_test/database.db"
    "/opt/telegram_bot/database.db"
    "/root/database.db"
    "/home/*/database.db"
    "$(find /opt /home /root -name "database.db" -type f 2>/dev/null | head -1)"
)

DB_PATH=""

# Проверяем каждый путь
for path in "${DB_PATHS[@]}"; do
    if [ -f "$path" ]; then
        # Проверяем наличие таблицы stickers
        if sqlite3 "$path" ".tables" 2>/dev/null | grep -q "stickers"; then
            DB_PATH="$path"
            echo "✅ Найдена база данных: $DB_PATH"
            break
        fi
    fi
done

# Если не нашли, пробуем найти через find
if [ -z "$DB_PATH" ]; then
    echo "🔍 Ищу базу данных через find..."
    FOUND_DB=$(find /opt /home /root -name "database.db" -type f 2>/dev/null | head -1)
    if [ -n "$FOUND_DB" ]; then
        if sqlite3 "$FOUND_DB" ".tables" 2>/dev/null | grep -q "stickers"; then
            DB_PATH="$FOUND_DB"
            echo "✅ Найдена база данных: $DB_PATH"
        fi
    fi
fi

if [ -z "$DB_PATH" ]; then
    echo "❌ База данных с таблицей stickers не найдена!"
    echo "💡 Проверьте путь вручную:"
    echo "   sqlite3 /opt/telegram_bot_test/database.db '.tables'"
    exit 1
fi

echo ""
echo "📋 Проверяю стикеры со слотами..."
sqlite3 "$DB_PATH" "SELECT name, id FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"

echo ""
echo "🗑️ Удаляю стикеры со слотами..."
sqlite3 "$DB_PATH" "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"

DELETED=$(sqlite3 "$DB_PATH" "SELECT changes();")
echo ""
echo "✅ Удалено стикеров: $DELETED"

echo ""
echo "📋 Проверка результата..."
sqlite3 "$DB_PATH" "SELECT name FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"

if [ $? -eq 0 ]; then
    echo "✅ Готово! Стикеры со слотами удалены."
else
    echo "✅ Готово!"
fi
