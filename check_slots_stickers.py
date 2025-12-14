"""
Скрипт для проверки всех стикеров в базе данных (для отладки)
"""
import asyncio
import aiosqlite
import sys
import io
from database import Database

async def check_all_stickers():
    """Проверить все стикеры в базе данных"""
    db = Database()
    
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("🔍 Проверяю все стикеры в базе данных...")
    print("=" * 50)
    
    # Получаем все стикеры
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM stickers ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            all_stickers = [dict(row) for row in rows]
    
    if not all_stickers:
        print("❌ В базе данных нет стикеров")
        return
    
    print(f"📋 Всего стикеров в базе данных: {len(all_stickers)}\n")
    
    # Показываем все стикеры
    for idx, st in enumerate(all_stickers, 1):
        print(f"{idx}. Имя: '{st['name']}'")
        print(f"   ID: {st['id']}")
        print(f"   File ID: {st['file_id'][:50]}...")
        print(f"   Тип: {st.get('sticker_type', 'не указан')}")
        print()
    
    # Ищем стикеры со слотами (любые варианты)
    slots_stickers = [st for st in all_stickers if 'slots' in st['name'].lower() or 'slot' in st['name'].lower()]
    
    # Также ищем стикеры с похожими названиями
    print("=" * 50)
    print("🔍 Ищу стикеры с похожими названиями...")
    similar_names = [st for st in all_stickers if any(word in st['name'].lower() for word in ['base', 'game', 'icon'])]
    if similar_names:
        print(f"📋 Найдено стикеров с похожими названиями: {len(similar_names)}")
        for st in similar_names[:10]:  # Показываем первые 10
            print(f"   - '{st['name']}' (ID: {st['id']})")
    
    if slots_stickers:
        print("=" * 50)
        print(f"🎰 Найдено стикеров со слотами: {len(slots_stickers)}")
        for st in slots_stickers:
            print(f"   - '{st['name']}' (ID: {st['id']})")
    else:
        print("=" * 50)
        print("❌ Стикеры со слотами не найдены")
        print("💡 Возможно, стикер был сохранен в другую базу данных или под другим названием")
    
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(check_all_stickers())







