# Инструкция по удалению стикера slots_base из базы данных

## Выполните на сервере:

```bash
# Подключитесь к серверу
ssh root@141.8.198.144

# Перейдите в папку с базой данных
cd /opt/telegram_bot_test

# Выполните SQL команду для удаления
sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"

# Проверьте результат
sqlite3 database.db "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
```

Или используйте SQL файл:

```bash
sqlite3 database.db < delete_slots_sticker.sql
```

## Альтернативный способ - через Python скрипт на сервере:

1. Скопируйте файл `delete_slots_base_from_server.py` на сервер
2. Установите переменную окружения:
   ```bash
   export SERVER_DB_PATH="/opt/telegram_bot_test/database.db"
   ```
3. Запустите:
   ```bash
   python3 delete_slots_base_from_server.py
   ```
