from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import logging
import json
from typing import Optional

from database import Database
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

router = Router()
db = Database()


@router.message(Command("miniapp"))
async def cmd_miniapp(message: Message):
    """Команда для открытия мини-приложения"""
    # URL мини-приложения
    web_app_url = "https://arbuzcas.netlify.app/index.html"
    
    keyboard = {
        "inline_keyboard": [[
            {
                "text": "🎰 Открыть ArbuzCasino",
                "web_app": {"url": web_app_url}
            }
        ]]
    }
    
    await message.answer(
        "🎰 <b>Добро пожаловать в ArbuzCasino!</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть мини-приложение:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def get_sticker_file_url(bot: Bot, file_id: str) -> Optional[str]:
    """Получить URL файла стикера"""
    try:
        file = await bot.get_file(file_id)
        return f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    except Exception as e:
        logger.error(f"Ошибка получения URL стикера: {e}")
        return None


async def get_welcome_sticker() -> Optional[dict]:
    """Получить приветственный стикер"""
    sticker = await db.get_sticker("welcome")
    return sticker


async def get_game_sticker(game_type: str, result: int) -> Optional[dict]:
    """Получить стикер для результата игры"""
    sticker_name = f"{game_type}_{result}"
    sticker = await db.get_sticker(sticker_name)
    return sticker

