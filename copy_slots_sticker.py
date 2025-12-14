"""
Быстрый скрипт для копирования стикера slots_base из базы данных в папку mini_app/stickers/slots/
"""
import asyncio
import os
import aiohttp
import aiofiles
import aiosqlite
from config import BOT_TOKEN
from database import Database

async def download_sticker(bot_token: str, file_id: str, file_path: str):
    """Скачать стикер через Telegram Bot API"""
    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("ok"):
                    file_path_telegram = data["result"]["file_path"]
                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path_telegram}"
                    
                    print(f"📥 Скачиваю стикер...")
                    
                    # Скачиваем файл
                    async with session.get(download_url) as file_response:
                        if file_response.status == 200:
                            # Создаем директорию, если её нет
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            
                            async with aiofiles.open(file_path, 'wb') as f:
                                async for chunk in file_response.content.iter_chunked(8192):
                                    await f.write(chunk)
                            return True
    return False


async def copy_slots_sticker():
    """Скопировать стикер slots_base из БД в папку"""
    db = Database()
    
    # Показываем путь к базе данных
    db_path = os.path.abspath(db.db_path)
    print(f"📁 Используется база данных: {db_path}")
    
    if not os.path.exists(db.db_path):
        print(f"❌ База данных не найдена по пути: {db_path}")
        print("💡 Возможные решения:")
        print("   1. Убедитесь, что база данных находится в текущей папке")
        print("   2. Если бот работает на сервере, скопируйте database.db с сервера")
        print("   3. Или установите переменную окружения:")
        print("      set DATABASE_PATH=путь_к_базе")
        return
    
    print("🔍 Ищу стикер slots_base в базе данных...")
    
    sticker = None
    
    # Ищем стикер в базе данных
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        
        # Сначала покажем все стикеры для отладки
        async with db_conn.execute("SELECT name FROM stickers ORDER BY id DESC LIMIT 20") as cursor:
            all_stickers = await cursor.fetchall()
            if all_stickers:
                print(f"📋 Последние стикеры в БД (первые 20):")
                for row in all_stickers:
                    print(f"   - {row['name']}")
        
        # Ищем стикеры со слотами (разные варианты)
        async with db_conn.execute(
            "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%' ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            stickers = [dict(row) for row in rows]
        
        # Приоритет: сначала точное совпадение "slots_base", потом "1 slots_base"
        for name in ["slots_base", "1 slots_base"]:
            for st in stickers:
                if st['name'] == name:
                    sticker = st
                    print(f"✅ Найден стикер с приоритетным именем: '{sticker['name']}'")
                    break
            if sticker:
                break
        
        # Если не нашли, ищем стикеры начинающиеся с "1 " (возможно сохранен как "1 slots_base")
        if not sticker:
            async with db_conn.execute(
                "SELECT * FROM stickers WHERE name LIKE '1 %slots%' OR name LIKE '1 %slot%' ORDER BY id DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                stickers_with_1 = [dict(row) for row in rows]
                if stickers_with_1:
                    print(f"\n🔍 Найдены стикеры начинающиеся с '1 slots':")
                    for st in stickers_with_1:
                        print(f"   - '{st['name']}' (ID: {st['id']})")
                    sticker = stickers_with_1[0]  # Берем первый найденный
        
        # Если все еще не нашли, берем самый новый из найденных со слотами
        if not sticker and stickers:
            sticker = stickers[0]
            print(f"📌 Используется самый новый стикер со слотами: '{sticker['name']}'")
    
    if not sticker:
        print("❌ Стикер slots_base не найден в базе данных")
        print("💡 Сначала сохраните стикер через команду /sticker в боте")
        print("💡 Убедитесь, что используете правильную базу данных (где работает бот)")
        return
    
    print(f"✅ Используется стикер: '{sticker['name']}' (ID: {sticker['id']})")
    
    # Путь к файлу
    file_path = os.path.join("mini_app", "stickers", "slots", "base_new.tgs")
    
    print(f"📁 Сохраняю в: {os.path.abspath(file_path)}")
    
    try:
        success = await download_sticker(BOT_TOKEN, sticker['file_id'], file_path)
        if success:
            file_size = os.path.getsize(file_path)
            print(f"✅ Готово! Файл сохранен ({file_size / 1024:.2f} KB)")
            print(f"📁 Путь: {os.path.abspath(file_path)}")
        else:
            print(f"❌ Ошибка при скачивании стикера")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    import sys
    import io
    
    # UTF-8 для Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        os.environ["DATABASE_PATH"] = db_path
        print(f"📁 Используется указанная база данных: {db_path}")
    
    print("🚀 Копирую стикер slots_base из БД...")
    print("=" * 50)
    asyncio.run(copy_slots_sticker())
    print("=" * 50)
