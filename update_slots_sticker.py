"""
Скрипт для обновления стикера slots_base из базы данных в локальный файл
Поддерживает поиск по разным вариантам имени: "1 slots_base", "slots_base" и т.д.

ВАЖНО: Если стикер был сохранен через бота на сервере, используйте серверную базу данных!
Установите переменную окружения: set DATABASE_PATH=путь_к_серверной_базе
Или скопируйте database.db с сервера в локальную папку.
"""
import asyncio
import os
import aiohttp
import aiofiles
from database import Database
from config import BOT_TOKEN

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
                    
                    print(f"📥 Скачиваю стикер с URL: {download_url}")
                    
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


async def find_slots_base_sticker(db: Database):
    """Найти стикер slots_base, пробуя разные варианты имени"""
    import aiosqlite
    
    # Сначала ищем все стикеры, содержащие "slots" (более широкий поиск)
    print("🔍 Ищу все стикеры содержащие 'slots' или 'slot'...")
    
    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            "SELECT * FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%' ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            stickers = [dict(row) for row in rows]
    
    if not stickers:
        print("❌ Стикеры со слотами не найдены в базе данных")
        print("💡 Проверьте, что стикер был сохранен в правильную базу данных")
        print("💡 Если стикер был сохранен на сервере, используйте серверную базу данных")
        return None
    
    if len(stickers) > 1:
        print(f"⚠️ Найдено {len(stickers)} стикеров с 'slots_base' в имени:")
        for idx, st in enumerate(stickers, 1):
            print(f"   {idx}. '{st['name']}' (ID: {st['id']}, File ID: {st['file_id'][:30]}...)")
    
    # Приоритет: сначала точное совпадение "slots_base", потом "1 slots_base", потом самый новый
    priority_names = ["slots_base", "1 slots_base"]
    
    for priority_name in priority_names:
        for sticker in stickers:
            if sticker['name'] == priority_name:
                print(f"✅ Выбран стикер с приоритетным именем '{priority_name}' (ID: {sticker['id']})")
                return sticker
    
    # Если приоритетных нет, берем самый новый
    print(f"📌 Используется самый новый стикер (ID: {stickers[0]['id']}, имя: '{stickers[0]['name']}')")
    print(f"💡 Совет: для правильной работы используйте название 'slots_base'")
    return stickers[0]


async def update_slots_sticker():
    """Обновить стикер slots_base из базы данных"""
    db = Database()
    
    # Ищем стикер с поддержкой разных вариантов имени
    sticker = await find_slots_base_sticker(db)
    
    if not sticker:
        print("❌ Стикер 'slots_base' не найден в базе данных")
        print("💡 Используйте команду /sticker в боте для сохранения стикера")
        print("💡 Сохраните стикер как: 1 slots_base")
        return
    
    print(f"✅ Стикер найден!")
    print(f"📋 Имя: '{sticker['name']}'")
    print(f"📋 ID в БД: {sticker['id']}")
    print(f"📋 File ID: {sticker['file_id']}")
    
    # Путь к файлу в mini_app/stickers/slots/base.tgs
    file_path = os.path.join("mini_app", "stickers", "slots", "base.tgs")
    
    print(f"📁 Сохраняю в: {os.path.abspath(file_path)}")
    
    try:
        success = await download_sticker(BOT_TOKEN, sticker['file_id'], file_path)
        if success:
            file_size = os.path.getsize(file_path)
            print(f"✅ Стикер успешно сохранен!")
            print(f"📊 Размер файла: {file_size / 1024:.2f} KB")
            print(f"📁 Путь: {os.path.abspath(file_path)}")
        else:
            print(f"❌ Ошибка при скачивании стикера")
    except Exception as e:
        print(f"❌ Ошибка при сохранении: {e}")


if __name__ == "__main__":
    import sys
    import io
    import aiosqlite
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # Показываем, какую базу данных используем
    db_path = os.getenv("DATABASE_PATH", "database.db")
    print(f"📁 Используется база данных: {os.path.abspath(db_path)}")
    if not os.path.exists(db_path):
        print(f"⚠️ ВНИМАНИЕ: База данных не найдена по пути: {db_path}")
        print("💡 Если стикер был сохранен на сервере, скопируйте database.db с сервера")
        print("💡 Или установите переменную окружения: set DATABASE_PATH=путь_к_базе")
    print()
    
    print("🚀 Начинаю обновление стикера slots_base...")
    print("=" * 50)
    asyncio.run(update_slots_sticker())
    print("=" * 50)
    print("✅ Готово!")
