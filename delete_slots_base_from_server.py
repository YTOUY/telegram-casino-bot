"""
Скрипт для удаления стикера slots_base из серверной базы данных
Можно запустить на сервере или через SSH
"""
import asyncio
import aiosqlite
import sys
import io
import os

# Путь к серверной базе данных (замените на реальный путь на сервере)
SERVER_DB_PATH = os.getenv("SERVER_DB_PATH", "/opt/telegram_bot_test/database.db")

async def delete_slots_base_from_server():
    """Удалить стикер slots_base из серверной базы данных"""
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("🗑️ Удаление стикера slots_base из серверной базы данных...")
    print("=" * 50)
    print(f"📁 Путь к базе данных: {SERVER_DB_PATH}")
    
    if not os.path.exists(SERVER_DB_PATH):
        print(f"❌ База данных не найдена по пути: {SERVER_DB_PATH}")
        print("💡 Убедитесь, что путь правильный или установите переменную окружения SERVER_DB_PATH")
        return
    
    async with aiosqlite.connect(SERVER_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Ищем все стикеры со слотами
        async with db.execute(
            "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
            stickers = [dict(row) for row in rows]
        
        if not stickers:
            print("✅ Стикеры со слотами не найдены в базе данных")
            return
        
        print(f"📋 Найдено стикеров со слотами: {len(stickers)}")
        for st in stickers:
            print(f"   - '{st['name']}' (ID: {st['id']})")
        
        # Удаляем все найденные стикеры
        deleted_count = 0
        for sticker in stickers:
            try:
                await db.execute("DELETE FROM stickers WHERE name = ?", (sticker['name'],))
                await db.commit()
                deleted_count += 1
                print(f"   ✅ Удален: '{sticker['name']}'")
            except Exception as e:
                print(f"   ❌ Ошибка при удалении '{sticker['name']}': {e}")
        
        print("=" * 50)
        print(f"✅ Удалено стикеров: {deleted_count}/{len(stickers)}")
        print("✅ Готово!")


if __name__ == "__main__":
    asyncio.run(delete_slots_base_from_server())







