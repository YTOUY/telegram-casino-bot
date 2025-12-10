"""
Скрипт для тестирования обработчика /start
Запустите этот скрипт для проверки, работает ли обработчик
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN
from handlers import start_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(start_router)
    
    logger.info("Тестовый бот запущен. Отправьте /start в боте.")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(test())













