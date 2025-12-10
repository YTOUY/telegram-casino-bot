# 📊 Инструкция по просмотру статистики через командную строку

## 🔌 Подключение к серверу

```bash
ssh root@141.8.198.144
cd /opt/telegram_bot
```

---

## 🎮 Просмотр ставок (игр)

### Последние 20 ставок с заголовками
```bash
sqlite3 database.db -header -column "SELECT * FROM games ORDER BY created_at DESC LIMIT 20;"
```

### Последние 50 ставок с информацией о пользователях
```bash
sqlite3 database.db -header -column "SELECT g.id, g.user_id, u.username, g.game_type, g.bet_type, g.bet, g.result, g.win, g.created_at FROM games g LEFT JOIN users u ON g.user_id = u.user_id ORDER BY g.created_at DESC LIMIT 50;"
```

### Ставки за последний час
```bash
# Убедитесь, что вы находитесь в директории /opt/telegram_bot
cd /opt/telegram_bot
sqlite3 database.db -header -column "SELECT * FROM games WHERE created_at >= datetime('now', '-1 hour') ORDER BY created_at DESC;"
```

### Ставки за последний час с информацией о пользователях
```bash
# Убедитесь, что вы находитесь в директории /opt/telegram_bot
cd /opt/telegram_bot
sqlite3 database.db -header -column "SELECT g.id, g.user_id, u.username, g.game_type, g.bet_type, g.bet, g.result, g.win, g.created_at FROM games g LEFT JOIN users u ON g.user_id = u.user_id WHERE g.created_at >= datetime('now', '-1 hour') ORDER BY g.created_at DESC;"
```

### Ставки за последний час с читаемыми названиями типов ставок
```bash
# Убедитесь, что вы находитесь в директории /opt/telegram_bot
cd /opt/telegram_bot
sqlite3 database.db -header -column "
SELECT 
    g.id, 
    g.user_id, 
    u.username, 
    g.game_type,
    CASE 
        WHEN g.game_type = 'dice' AND g.bet_type = 'even' THEN 'Чет'
        WHEN g.game_type = 'dice' AND g.bet_type = 'odd' THEN 'Нечет'
        WHEN g.game_type = 'dice' AND g.bet_type LIKE 'exact_%' THEN 'Точное число ' || SUBSTR(g.bet_type, 7)
        WHEN g.game_type = 'dice' AND g.bet_type = 'pair' THEN 'Пара'
        WHEN g.game_type = 'dice' AND g.bet_type = '3_even' THEN '3 Чет'
        WHEN g.game_type = 'dice' AND g.bet_type = '3_odd' THEN '3 Нечет'
        WHEN g.game_type = 'dice' AND g.bet_type = '18' THEN 'Сумма 18'
        WHEN g.game_type = 'dice' AND g.bet_type = '21' THEN 'Сумма 21'
        WHEN g.game_type = 'dart' AND g.bet_type = 'red' THEN 'Красное'
        WHEN g.game_type = 'dart' AND g.bet_type = 'white' THEN 'Белое'
        WHEN g.game_type = 'dart' AND g.bet_type = 'center' THEN 'Центр'
        WHEN g.game_type = 'dart' AND g.bet_type = 'miss' THEN 'Отскок'
        WHEN g.game_type = 'bowling' AND g.bet_type = '0-3' THEN '0-3 кегли'
        WHEN g.game_type = 'bowling' AND g.bet_type = '4-6' THEN '4-6 кеглей'
        WHEN g.game_type = 'bowling' AND g.bet_type = 'strike' THEN 'Страйк'
        WHEN g.game_type = 'bowling' AND g.bet_type = 'miss' THEN 'Промах'
        WHEN g.game_type = 'football' AND g.bet_type = 'goal' THEN 'Гол'
        WHEN g.game_type = 'football' AND g.bet_type = 'miss' THEN 'Промах'
        WHEN g.game_type = 'football' AND g.bet_type = 'center' THEN 'В центр'
        WHEN g.game_type = 'basketball' AND g.bet_type = 'hit' THEN 'Гол'
        WHEN g.game_type = 'basketball' AND g.bet_type = 'miss' THEN 'Мимо'
        WHEN g.game_type = 'basketball' AND g.bet_type = 'clean' THEN 'Чистый гол'
        ELSE COALESCE(g.bet_type, '-')
    END as bet_type_name,
    g.bet, 
    g.result, 
    g.win, 
    g.created_at 
FROM games g 
LEFT JOIN users u ON g.user_id = u.user_id 
WHERE g.created_at >= datetime('now', '-1 hour') 
ORDER BY g.created_at DESC;
"
```

### Все ставки конкретного пользователя
```bash
sqlite3 database.db -header -column "SELECT * FROM games WHERE user_id = 1000402293 ORDER BY created_at DESC;"
```

### Статистика по ставкам
```bash
sqlite3 database.db -header -column "SELECT COUNT(*) as total, SUM(bet) as total_bets, SUM(win) as total_wins FROM games;"
```

### Статистика по типам игр
```bash
sqlite3 database.db -header -column "SELECT game_type, COUNT(*) as count, SUM(bet) as total_bets, SUM(win) as total_wins FROM games GROUP BY game_type;"
```

### Статистика по пользователю (игры, депозиты, выводы)
```bash
sqlite3 database.db -header -column "
SELECT 
    (SELECT COUNT(*) FROM games WHERE user_id = 1000402293) as total_games,
    (SELECT SUM(bet) FROM games WHERE user_id = 1000402293) as total_bets,
    (SELECT SUM(win) FROM games WHERE user_id = 1000402293) as total_wins,
    (SELECT SUM(amount) FROM deposits WHERE user_id = 1000402293) as total_deposits,
    (SELECT SUM(amount) FROM withdrawals WHERE user_id = 1000402293) as total_withdrawals;
"
```

---

## 💰 Просмотр депозитов

### Последние 20 депозитов
```bash
sqlite3 database.db -header -column "SELECT * FROM deposits ORDER BY created_at DESC LIMIT 20;"
```

### Депозиты с информацией о пользователях
```bash
sqlite3 database.db -header -column "SELECT d.id, d.user_id, u.username, d.amount, d.method, d.status, d.created_at FROM deposits d LEFT JOIN users u ON d.user_id = u.user_id ORDER BY d.created_at DESC LIMIT 20;"
```

### Депозиты конкретного пользователя
```bash
sqlite3 database.db -header -column "SELECT * FROM deposits WHERE user_id = 1000402293 ORDER BY created_at DESC;"
```

### Статистика по депозитам
```bash
sqlite3 database.db -header -column "SELECT COUNT(*) as total, SUM(amount) as total_amount, method, COUNT(*) as count FROM deposits GROUP BY method;"
```

### Общая статистика по депозитам
```bash
sqlite3 database.db -header -column "SELECT COUNT(*) as total_deposits, SUM(amount) as total_amount FROM deposits;"
```

### Топ пользователей по депозитам
```bash
sqlite3 database.db -header -column "SELECT d.user_id, u.username, COUNT(*) as deposits_count, SUM(d.amount) as total_deposited FROM deposits d LEFT JOIN users u ON d.user_id = u.user_id GROUP BY d.user_id ORDER BY total_deposited DESC LIMIT 10;"
```

### Депозиты за сегодня
```bash
sqlite3 database.db -header -column "SELECT * FROM deposits WHERE DATE(created_at) = DATE('now') ORDER BY created_at DESC;"
```

---

## 💸 Просмотр выводов

### Последние 20 выводов
```bash
sqlite3 database.db -header -column "SELECT * FROM withdrawals ORDER BY created_at DESC LIMIT 20;"
```

### Выводы с информацией о пользователях
```bash
sqlite3 database.db -header -column "SELECT w.id, w.user_id, u.username, w.amount, w.method, w.gift_emoji, w.gift_name, w.status, w.created_at FROM withdrawals w LEFT JOIN users u ON w.user_id = u.user_id ORDER BY w.created_at DESC LIMIT 20;"
```

### Выводы конкретного пользователя
```bash
sqlite3 database.db -header -column "SELECT * FROM withdrawals WHERE user_id = 1000402293 ORDER BY created_at DESC;"
```

### Статистика по выводам
```bash
sqlite3 database.db -header -column "SELECT COUNT(*) as total, SUM(amount) as total_amount, method, COUNT(*) as count FROM withdrawals GROUP BY method;"
```

### Общая статистика по выводам
```bash
sqlite3 database.db -header -column "SELECT COUNT(*) as total_withdrawals, SUM(amount) as total_amount FROM withdrawals;"
```

### Выводы подарками
```bash
sqlite3 database.db -header -column "SELECT * FROM withdrawals WHERE gift_name IS NOT NULL ORDER BY created_at DESC;"
```

### Выводы обычными методами
```bash
sqlite3 database.db -header -column "SELECT * FROM withdrawals WHERE gift_name IS NULL ORDER BY created_at DESC;"
```

---

## 👤 Просмотр пользователей

### Информация о пользователе по ID
```bash
sqlite3 database.db -header -column "SELECT * FROM users WHERE user_id = 1000402293;"
```

### Информация о пользователе (краткая)
```bash
sqlite3 database.db -header -column "SELECT user_id, username, balance, locked_balance, rollover_requirement, created_at FROM users WHERE user_id = 1000402293;"
```

### Поиск пользователя по username
```bash
sqlite3 database.db -header -column "SELECT * FROM users WHERE username LIKE '%username%';"
```

### Все пользователи
```bash
sqlite3 database.db -header -column "SELECT user_id, username, balance, locked_balance, rollover_requirement FROM users ORDER BY user_id;"
```

### Топ пользователей по балансу
```bash
sqlite3 database.db -header -column "SELECT user_id, username, balance, locked_balance FROM users ORDER BY balance DESC LIMIT 10;"
```

---

## 📋 Просмотр таблиц

### Список всех таблиц
```bash
sqlite3 database.db ".tables"
```

### Структура таблицы
```bash
sqlite3 database.db ".schema games"
sqlite3 database.db ".schema users"
sqlite3 database.db ".schema deposits"
sqlite3 database.db ".schema withdrawals"
```

### Количество записей в таблицах
```bash
sqlite3 database.db "SELECT 'users' as table_name, COUNT(*) as count FROM users UNION ALL SELECT 'games', COUNT(*) FROM games UNION ALL SELECT 'deposits', COUNT(*) FROM deposits UNION ALL SELECT 'withdrawals', COUNT(*) FROM withdrawals;"
```

---

## 🔍 Полезные команды

### Войти в интерактивный режим SQLite
```bash
sqlite3 database.db
```

Внутри SQLite:
```sql
.headers on
.mode column
SELECT * FROM games ORDER BY created_at DESC LIMIT 20;
.quit
```

### Экспорт данных в CSV
```bash
sqlite3 database.db -header -csv "SELECT * FROM games ORDER BY created_at DESC LIMIT 100;" > games_export.csv
```

### Поиск по всем таблицам
```bash
sqlite3 database.db "SELECT 'games' as table_name, COUNT(*) FROM games WHERE user_id = 1000402293 UNION ALL SELECT 'deposits', COUNT(*) FROM deposits WHERE user_id = 1000402293 UNION ALL SELECT 'withdrawals', COUNT(*) FROM withdrawals WHERE user_id = 1000402293;"
```

---

## 📊 Быстрая статистика (все в одном)

```bash
sqlite3 database.db -header -column "
SELECT 
    'Всего пользователей' as metric,
    COUNT(*) as value
FROM users
UNION ALL
SELECT 
    'Всего ставок',
    COUNT(*)
FROM games
UNION ALL
SELECT 
    'Общая сумма ставок',
    ROUND(SUM(bet), 2)
FROM games
UNION ALL
SELECT 
    'Общая сумма выигрышей',
    ROUND(SUM(win), 2)
FROM games
UNION ALL
SELECT 
    'Всего депозитов',
    COUNT(*)
FROM deposits
UNION ALL
SELECT 
    'Общая сумма депозитов',
    ROUND(SUM(amount), 2)
FROM deposits
UNION ALL
SELECT 
    'Всего выводов',
    COUNT(*)
FROM withdrawals
UNION ALL
SELECT 
    'Общая сумма выводов',
    ROUND(SUM(amount), 2)
FROM withdrawals;
"
```

---

## 💡 Советы

1. **Используйте `-header -column`** для красивого форматирования вывода
2. **Используйте `LIMIT`** чтобы не выводить слишком много данных
3. **Используйте `ORDER BY created_at DESC`** для сортировки по дате (новые сверху)
4. **Замените `1000402293`** на нужный ID пользователя
5. **Используйте `LEFT JOIN`** для объединения данных из разных таблиц

---

## 🚨 Важно

- Все команды выполняются на сервере после подключения через SSH
- База данных находится в `/opt/telegram_bot/database.db`
- Будьте осторожны с командами `UPDATE` и `DELETE` - они изменяют данные!

