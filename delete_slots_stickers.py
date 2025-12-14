"""
Скрипт для удаления всех стикеров слотов из базы данных и файлов
"""
import asyncio
import os
import aiosqlite
import sys
import io
from database import Database

async def delete_all_slots_stickers():
    """Удалить все стикеры слотов из базы данных и файлов"""
    db = Database()
    
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("🗑️ Начинаю удаление всех стикеров слотов...")
    print("=" * 50)
    
    # Находим все стикеры, содержащие "slots" в имени
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM stickers WHERE name LIKE '%slots%' ORDER BY name"
        ) as cursor:
            rows = await cursor.fetchall()
            stickers = [dict(row) for row in rows]
    
    if not stickers:
        print("✅ Стикеры слотов не найдены в базе данных")
        print("=" * 50)
        return
    
    print(f"📋 Найдено стикеров слотов в базе данных: {len(stickers)}")
    for idx, st in enumerate(stickers, 1):
        print(f"   {idx}. '{st['name']}' (ID: {st['id']})")
    
    # Удаляем из базы данных
    print("\n🗑️ Удаляю стикеры из базы данных...")
    deleted_count = 0
    for sticker in stickers:
        success = await db.delete_sticker(sticker['name'])
        if success:
            deleted_count += 1
            print(f"   ✅ Удален: '{sticker['name']}'")
        else:
            print(f"   ❌ Ошибка при удалении: '{sticker['name']}'")
    
    print(f"\n✅ Удалено из базы данных: {deleted_count}/{len(stickers)}")
    
    # Удаляем файлы из папки mini_app/stickers/slots/
    print("\n🗑️ Удаляю файлы стикеров...")
    slots_dir = os.path.join("mini_app", "stickers", "slots")
    
    if not os.path.exists(slots_dir):
        print(f"   ⚠️ Папка {slots_dir} не найдена")
    else:
        files_deleted = 0
        for filename in os.listdir(slots_dir):
            file_path = os.path.join(slots_dir, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    files_deleted += 1
                    print(f"   ✅ Удален файл: {filename}")
                except Exception as e:
                    print(f"   ❌ Ошибка при удалении файла {filename}: {e}")
        
        print(f"\n✅ Удалено файлов: {files_deleted}")
    
    print("=" * 50)
    print("✅ Готово!")


if __name__ == "__main__":
    asyncio.run(delete_all_slots_stickers())







