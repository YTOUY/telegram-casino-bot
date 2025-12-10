"""
Middleware для проверки подписки на канал
"""
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.filters import Command

from config import REQUIRED_CHANNEL, REQUIRED_CHANNEL_ID, ADMIN_IDS
from utils.subscription import check_subscription, get_subscription_keyboard

logger = logging.getLogger(__name__)


class SubscriptionMiddleware(BaseMiddleware):
    """Middleware для проверки подписки на канал"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверяет подписку перед обработкой события"""
        
        # Получаем бота из данных
        bot: Any = data.get("bot")
        if not bot:
            return await handler(event, data)
        
        # Получаем user_id в зависимости от типа события
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        
        if not user_id:
            return await handler(event, data)
        
        # Админы всегда имеют доступ
        if user_id in ADMIN_IDS:
            return await handler(event, data)
        
        # Проверяем подписку (используем ID канала, если указан)
        is_subscribed = await check_subscription(
            bot, 
            user_id, 
            channel=REQUIRED_CHANNEL, 
            channel_id=REQUIRED_CHANNEL_ID
        )
        
        if not is_subscribed:
            # Если пользователь не подписан, показываем сообщение
            channel_username = REQUIRED_CHANNEL.lstrip("@")
            text = f"""🔒 <b>Требуется подписка</b>

Для использования бота необходимо подписаться на наш канал:

📢 <b>@{channel_username}</b>

После подписки нажмите кнопку "✅ Я подписался" для проверки."""
            
            keyboard = get_subscription_keyboard(REQUIRED_CHANNEL)
            
            if isinstance(event, Message):
                # Если это команда /start, отправляем новое сообщение
                if event.text and event.text.startswith("/start"):
                    await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
                else:
                    # Для других команд/сообщений редактируем или отправляем новое
                    try:
                        await event.answer(text, reply_markup=keyboard, parse_mode="HTML")
                    except:
                        pass
                return  # Не обрабатываем дальше
            
            elif isinstance(event, CallbackQuery):
                # Для callback_query проверяем, не это ли кнопка проверки подписки
                # Разрешаем обработку callback для проверки подписки
                if event.data == "check_subscription":
                    return await handler(event, data)
                
                # Для других callback показываем сообщение
                try:
                    await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                except:
                    try:
                        await event.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
                    except:
                        pass
                try:
                    await event.answer("❌ Сначала подпишитесь на канал", show_alert=True)
                except:
                    pass
                return  # Не обрабатываем дальше
        
        # Если подписан, продолжаем обработку
        return await handler(event, data)

