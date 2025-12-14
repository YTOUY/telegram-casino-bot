# Удаление стикера slots_base из базы данных

## Способ 1: Через SSH (рекомендуется)

Выполните на сервере:

```bash
ssh root@141.8.198.144
cd /opt/telegram_bot_test
sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
sqlite3 database.db "SELECT 'Удалено стикеров: ' || changes();"
```

## Способ 2: Через скрипт

1. Скопируйте файл `delete_slots_sticker_server.sh` на сервер
2. Выполните:
```bash
chmod +x delete_slots_sticker_server.sh
bash delete_slots_sticker_server.sh
```

## Способ 3: Прямой SQL запрос

```sql
DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';
```

## Проверка

После удаления проверьте:
```bash
sqlite3 database.db "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';"
```

Должно вернуть пустой результат.







