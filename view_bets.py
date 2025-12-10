#!/usr/bin/env python3
"""
Простой скрипт для просмотра ставок из базы данных
"""
import aiosqlite
import asyncio
from datetime import datetime

async def view_bets(limit=50):
    """Просмотр ставок из базы данных"""
    async with aiosqlite.connect('database.db') as db:
        # Включаем режим строк (для получения словарей)
        db.row_factory = aiosqlite.Row
        
        # Определяем, какая таблица существует: bets или games
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('bets', 'games')")
        tables = await cursor.fetchall()
        table_name = None
        if tables:
            # Приоритет таблице bets, если она есть
            for table in tables:
                if table[0] == 'bets':
                    table_name = 'bets'
                    break
            if not table_name and tables:
                table_name = tables[0][0]
        
        if not table_name:
            print("Таблица bets или games не найдена в базе данных")
            return
        
        print(f"Используется таблица: {table_name}\n")
        
        # Получаем структуру таблицы
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        columns_info = await cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        # Получаем общее количество ставок
        cursor = await db.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        total = await cursor.fetchone()
        print(f"=== Всего ставок в базе: {total['count']} ===\n")
        
        # Формируем запрос в зависимости от структуры таблицы
        if 'game_type' in column_names:
            # Таблица games
            query = f"""
                SELECT 
                    g.id,
                    g.user_id,
                    u.username,
                    g.game_type,
                    g.bet,
                    g.result,
                    g.win,
                    g.created_at
                FROM {table_name} g
                LEFT JOIN users u ON g.user_id = u.user_id
                ORDER BY g.created_at DESC
                LIMIT ?
            """
        else:
            # Таблица bets - используем все доступные колонки
            query = f"""
                SELECT 
                    b.*,
                    u.username
                FROM {table_name} b
                LEFT JOIN users u ON b.user_id = u.user_id
                ORDER BY b.created_at DESC
                LIMIT ?
            """
        
        cursor = await db.execute(query, (limit,))
        rows = await cursor.fetchall()
        
        if not rows:
            print("Ставок пока нет в базе данных")
            return
        
        print(f"Последние {len(rows)} ставок:\n")
        
        # Определяем формат вывода в зависимости от структуры
        if 'game_type' in column_names:
            print(f"{'ID':<6} {'User ID':<12} {'Username':<20} {'Игра':<15} {'Ставка':<10} {'Результат':<12} {'Выигрыш':<12} {'Дата':<20}")
            print("-" * 120)
            
            for row in rows:
                username = row['username'] or 'без ника'
                if len(username) > 18:
                    username = username[:18] + '..'
                
                game_type = row['game_type'] or 'неизвестно'
                if len(game_type) > 13:
                    game_type = game_type[:13] + '..'
                
                result = str(row['result']) if row['result'] is not None else 'N/A'
                win = f"${row['win']:.2f}" if row['win'] else "$0.00"
                bet = f"${row['bet']:.2f}"
                
                created_at = row['created_at'] or 'N/A'
                if len(created_at) > 19:
                    created_at = created_at[:19]
                
                print(f"{row['id']:<6} {row['user_id']:<12} {username:<20} {game_type:<15} {bet:<10} {result:<12} {win:<12} {created_at:<20}")
        else:
            # Для таблицы bets выводим все колонки
            print("Доступные колонки:", ', '.join(column_names))
            print("-" * 120)
            for row in rows:
                row_dict = dict(row)
                print(f"ID: {row_dict.get('id', 'N/A')}")
                for key, value in row_dict.items():
                    if key != 'id':
                        print(f"  {key}: {value}")
                print("-" * 120)
        
        # Статистика
        print("\n" + "=" * 120)
        print("Статистика:")
        
        # Общая сумма ставок
        bet_column = 'bet' if 'bet' in column_names else column_names[2] if len(column_names) > 2 else None
        if bet_column:
            cursor = await db.execute(f"SELECT SUM({bet_column}) as total_bets FROM {table_name}")
            total_bets = await cursor.fetchone()
            print(f"Общая сумма ставок: ${total_bets['total_bets'] or 0:.2f}")
        
        # Общая сумма выигрышей
        win_column = 'win' if 'win' in column_names else None
        if win_column:
            cursor = await db.execute(f"SELECT SUM({win_column}) as total_wins FROM {table_name} WHERE {win_column} > 0")
            total_wins = await cursor.fetchone()
            print(f"Общая сумма выигрышей: ${total_wins['total_wins'] or 0:.2f}")
            
            # Количество выигрышных ставок
            cursor = await db.execute(f"SELECT COUNT(*) as wins FROM {table_name} WHERE {win_column} > 0")
            wins_count = await cursor.fetchone()
            print(f"Выигрышных ставок: {wins_count['wins']}")
            
            # Количество проигрышных ставок
            cursor = await db.execute(f"SELECT COUNT(*) as losses FROM {table_name} WHERE {win_column} = 0 OR {win_column} IS NULL")
            losses_count = await cursor.fetchone()
            print(f"Проигрышных ставок: {losses_count['losses']}")

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    asyncio.run(view_bets(limit))

