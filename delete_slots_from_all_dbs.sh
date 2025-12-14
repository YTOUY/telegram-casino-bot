#!/bin/bash
# Скрипт для удаления стикеров slots_base из всех баз данных на сервере

echo "🔍 Проверяю все базы данных на сервере..."
echo "=================================================="

# Список баз данных
DB_PATHS=(
    "/opt/telegram_bot_test/database.db"
    "/opt/telegram_bot/database.db"
    "/root/database.db"
)

TOTAL_DELETED=0

for DB_PATH in "${DB_PATHS[@]}"; do
    if [ -f "$DB_PATH" ]; then
        echo ""
        echo "📁 Проверяю базу: $DB_PATH"
        
        # Проверяем наличие таблицы stickers
        if sqlite3 "$DB_PATH" ".tables" 2>/dev/null | grep -q "stickers"; then
            echo "   ✅ Таблица stickers найдена"
            
            # Показываем найденные стикеры со слотами
            SLOTS_STICKERS=$(sqlite3 "$DB_PATH" "SELECT name FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';" 2>/dev/null)
            
            if [ -n "$SLOTS_STICKERS" ]; then
                echo "   📋 Найдены стикеры со слотами:"
                echo "$SLOTS_STICKERS" | while read -r name; do
                    echo "      - $name"
                done
                
                # Удаляем стикеры
                sqlite3 "$DB_PATH" "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';" 2>/dev/null
                DELETED=$(sqlite3 "$DB_PATH" "SELECT changes();" 2>/dev/null)
                
                if [ "$DELETED" -gt 0 ]; then
                    echo "   ✅ Удалено стикеров: $DELETED"
                    TOTAL_DELETED=$((TOTAL_DELETED + DELETED))
                fi
            else
                echo "   ℹ️ Стикеры со слотами не найдены"
            fi
        else
            echo "   ⚠️ Таблица stickers не найдена"
        fi
    else
        echo ""
        echo "📁 База данных не найдена: $DB_PATH"
    fi
done

echo ""
echo "=================================================="
echo "✅ Всего удалено стикеров из всех баз: $TOTAL_DELETED"
echo "✅ Готово!"







