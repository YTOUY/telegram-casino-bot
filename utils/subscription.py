"""
Утилиты для проверки подписки на канал
"""
import logging
from typing import Optional
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def check_subscription(bot: Bot, user_id: int, channel: str = None, channel_id: int = None) -> bool:
    """
    Проверяет, подписан ли пользователь на канал
    
    Args:
        bot: Экземпляр бота
        user_id: ID пользователя
        channel: Username канала (например, "@arbuzikgame") - опционально
        channel_id: ID канала (например, -1003236997426) - приоритетнее чем username
    
    Returns:
        True если пользователь подписан, False если нет
    """
    try:
        # Используем ID канала если указан, иначе username
        if channel_id:
            chat_id = channel_id
        elif channel:
            # Убираем @ если есть
            channel_username = channel.lstrip("@")
            chat_id = f"@{channel_username}"
        else:
            logger.error("Не указан ни channel, ни channel_id для проверки подписки")
            return True  # В случае ошибки разрешаем доступ
        
        # Получаем информацию о статусе пользователя в канале
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        
        # Проверяем статус подписки
        # member, administrator, creator - подписан
        # left, kicked, restricted - не подписан
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            return True
        else:
            return False
            
    except TelegramBadRequest as e:
        # Если канал не найден или бот не может проверить подписку
        logger.error(f"Ошибка при проверке подписки на канал {channel_id or channel}: {e}")
        # В случае ошибки разрешаем доступ (чтобы не блокировать пользователей)
        return True
    except Exception as e:
        logger.error(f"Неожиданная ошибка при проверке подписки: {e}", exc_info=True)
        # В случае ошибки разрешаем доступ
        return True


def get_subscription_keyboard(channel: str) -> "InlineKeyboardMarkup":
    """
    Создает клавиатуру с кнопкой подписки на канал
    
    Args:
        channel: Username канала (например, "@arbuzikgame")
    
    Returns:
        InlineKeyboardMarkup с кнопкой подписки
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    channel_username = channel.lstrip("@")
    channel_url = f"https://t.me/{channel_username}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_url),
        ],
        [
            InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"),
        ],
    ])
    
    return keyboard

