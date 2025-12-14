"""
Скрипт для скачивания стикера slots_base через API сервера
Этот скрипт работает даже если стикер сохранен на сервере
"""
import asyncio
import os
import aiohttp
import aiofiles
import sys
import io
from config import BOT_TOKEN

# URL API сервера (замените на ваш)
API_BASE = os.getenv("API_BASE", "http://141.8.198.144:8081/api")

async def download_sticker_from_api(sticker_name: str, output_path: str):
    """Скачать стикер через API сервера"""
    url = f"{API_BASE}/sticker/{sticker_name}"
    
    print(f"📡 Запрашиваю стикер '{sticker_name}' через API: {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 404:
                print(f"❌ Стикер '{sticker_name}' не найден на сервере")
                return False
            
            if response.status != 200:
                error_text = await response.text()
                print(f"❌ Ошибка API (статус {response.status}): {error_text}")
                return False
            
            data = await response.json()
            file_url = data.get('file_url') or data.get('file_id')
            
            if not file_url:
                print(f"❌ URL файла не найден в ответе API")
                return False
            
            print(f"📥 Скачиваю стикер с URL: {file_url}")
            
            # Скачиваем файл
            async with session.get(file_url) as file_response:
                if file_response.status == 200:
                    # Создаем директорию, если её нет
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    async with aiofiles.open(output_path, 'wb') as f:
                        async for chunk in file_response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return True
                else:
                    print(f"❌ Ошибка при скачивании файла (статус {file_response.status})")
                    return False


async def main():
    """Основная функция"""
    # Устанавливаем UTF-8 для вывода в Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("🚀 Скачивание стикера slots_base через API сервера...")
    print("=" * 50)
    print(f"📡 API сервер: {API_BASE}")
    print()
    
    # Путь к файлу
    file_path = os.path.join("mini_app", "stickers", "slots", "base.tgs")
    
    # Пробуем разные варианты имени
    sticker_names = ["slots_base", "1 slots_base"]
    
    success = False
    for name in sticker_names:
        print(f"🔍 Пробую найти стикер '{name}'...")
        if await download_sticker_from_api(name, file_path):
            file_size = os.path.getsize(file_path)
            print(f"✅ Стикер '{name}' успешно скачан!")
            print(f"📊 Размер файла: {file_size / 1024:.2f} KB")
            print(f"📁 Путь: {os.path.abspath(file_path)}")
            
            # Проверяем, что файл не пустой и имеет правильный размер
            if file_size < 1000:
                print(f"⚠️ ВНИМАНИЕ: Файл слишком маленький ({file_size} байт), возможно поврежден!")
            elif file_size > 500000:
                print(f"⚠️ ВНИМАНИЕ: Файл слишком большой ({file_size} байт), возможно это не TGS!")
            else:
                print(f"✅ Размер файла выглядит нормально для TGS стикера")
            
            success = True
            break
        print()
    
    if not success:
        print("❌ Не удалось скачать стикер")
        print("💡 Убедитесь, что:")
        print("   1. API сервер работает и доступен")
        print("   2. Стикер был сохранен через команду /sticker")
        print("   3. Название стикера правильное (slots_base)")
    
    print("=" * 50)
    print("✅ Готово!")


if __name__ == "__main__":
    asyncio.run(main())







