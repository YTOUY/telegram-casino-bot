"""
Скрипт для удаления стикера slots_base из базы данных
"""
import asyncio
import sys
import io
from database import Database

async def delete_slots_base_sticker():
    """Удалить стикер slots_base из базы данных"""
    db = Database()
    
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("🗑️ Удаление стикера slots_base из базы данных...")
    print("=" * 50)
    
    # Ищем все варианты названий
    sticker_names = ["slots_base", "1 slots_base"]
    
    deleted_count = 0
    for name in sticker_names:
        # Проверяем, существует ли стикер
        sticker = await db.get_sticker(name)
        if sticker:
            print(f"📋 Найден стикер: '{name}' (ID: {sticker['id']})")
            success = await db.delete_sticker(name)
            if success:
                deleted_count += 1
                print(f"   ✅ Удален: '{name}'")
            else:
                print(f"   ❌ Ошибка при удалении: '{name}'")
        else:
            print(f"   ℹ️ Стикер '{name}' не найден в базе данных")
    
    # Также ищем все стикеры, содержащие "slots" в имени
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
            all_slots_stickers = [dict(row) for row in rows]
    
    if all_slots_stickers:
        print(f"\n📋 Найдено других стикеров со слотами: {len(all_slots_stickers)}")
        for st in all_slots_stickers:
            print(f"   - '{st['name']}' (ID: {st['id']})")
            # Удаляем все найденные стикеры со слотами
            success = await db.delete_sticker(st['name'])
            if success:
                deleted_count += 1
                print(f"     ✅ Удален")
            else:
                print(f"     ❌ Ошибка при удалении")
    
    print("=" * 50)
    print(f"✅ Удалено стикеров: {deleted_count}")
    print("✅ Готово!")


if __name__ == "__main__":
    asyncio.run(delete_slots_base_sticker())







