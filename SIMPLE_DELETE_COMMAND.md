# Простая команда для удаления стикера slots_base

## Выполните на сервере:

```bash
# Перейдите в правильную директорию
cd /opt/telegram_bot_test

# Проверьте наличие таблицы
sqlite3 database.db ".tables" | grep stickers

# Удалите стикеры со слотами
sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"

# Проверьте результат
sqlite3 database.db "SELECT name FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
```

## Или используйте скрипт:

```bash
# Скопируйте скрипт на сервер или создайте его:
cat > /tmp/delete_slots.sh << 'EOF'
#!/bin/bash
cd /opt/telegram_bot_test
sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
echo "Удалено стикеров: $(sqlite3 database.db 'SELECT changes();')"
EOF

chmod +x /tmp/delete_slots.sh
/tmp/delete_slots.sh
```

## Если база данных в другом месте:

```bash
# Найдите базу данных
find /opt /home /root -name "database.db" -type f 2>/dev/null

# Затем выполните для найденного пути:
sqlite3 /путь/к/database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
```







