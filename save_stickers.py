"""
Скрипт для сохранения стикеров из базы данных в файлы .tgs
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
                    
                    # Скачиваем файл
                    async with session.get(download_url) as file_response:
                        if file_response.status == 200:
                            async with aiofiles.open(file_path, 'wb') as f:
                                async for chunk in file_response.content.iter_chunked(8192):
                                    await f.write(chunk)
                            return True
    return False


def get_game_folder(name: str) -> str:
    """Определить папку для стикера на основе его названия"""
    if name.startswith("dice_"):
        return "dice"
    elif name.startswith("darts_"):
        return "darts"
    elif name.startswith("football_"):
        return "football"
    elif name.startswith("basketball_"):
        return "basketball"
    elif name.startswith("bowling_"):
        return "bowling"
    elif name.startswith("slots_"):
        return "slots"
    elif name == "welcome":
        return "welcome"
    elif name in ["win", "lose"]:
        return "results"
    else:
        return "other"


async def save_all_stickers():
    """Сохранить все стикеры из базы данных в файлы"""
    db = Database()
    
    # Получаем все стикеры из базы данных
    stickers = await db.get_all_stickers()
    
    if not stickers:
        print("❌ Стикеры не найдены в базе данных")
        return
    
    print(f"📦 Найдено стикеров: {len(stickers)}")
    
    # Основная папка для всех стикеров (на том же уровне, что и папка bowling)
    base_stickers_dir = "stickers"
    os.makedirs(base_stickers_dir, exist_ok=True)
    
    saved_count = 0
    failed_count = 0
    
    for sticker in stickers:
        name = sticker["name"]
        file_id = sticker["file_id"]
        
        # Определяем папку для игры
        game_folder = get_game_folder(name)
        game_dir = os.path.join(base_stickers_dir, game_folder)
        os.makedirs(game_dir, exist_ok=True)
        
        # Определяем расширение файла
        file_extension = ".tgs"
        
        # Сохраняем только имя файла без префикса игры (например, dice_1 -> 1.tgs, но dice_base -> base.tgs)
        if name.startswith(f"{game_folder}_"):
            file_name = name.replace(f"{game_folder}_", "")
        else:
            file_name = name
        
        file_path = os.path.join(game_dir, f"{file_name}{file_extension}")
        
        print(f"📥 Скачиваю стикер: {name} -> {game_folder}/{file_name}{file_extension}...")
        
        try:
            success = await download_sticker(BOT_TOKEN, file_id, file_path)
            if success:
                print(f"✅ Сохранен: {file_path}")
                saved_count += 1
            else:
                print(f"❌ Ошибка при скачивании: {name}")
                failed_count += 1
        except Exception as e:
            print(f"❌ Ошибка при сохранении {name}: {e}")
            failed_count += 1
        
        # Небольшая задержка, чтобы не перегружать API
        await asyncio.sleep(0.5)
    
    print(f"\n✅ Сохранено: {saved_count}")
    print(f"❌ Ошибок: {failed_count}")
    print(f"📁 Файлы сохранены в: {os.path.abspath(base_stickers_dir)}/")
    print(f"\n📂 Структура папок:")
    print(f"   stickers/")
    print(f"   ├── dice/")
    print(f"   ├── darts/")
    print(f"   ├── football/")
    print(f"   ├── basketball/")
    print(f"   ├── bowling/")
    print(f"   ├── slots/")
    print(f"   ├── welcome/")
    print(f"   └── results/")


if __name__ == "__main__":
    print("🚀 Начинаю сохранение стикеров...")
    asyncio.run(save_all_stickers())

