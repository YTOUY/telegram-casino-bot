import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER

from database import Database

router = Router(name="chat_tracking")
db = Database()
logger = logging.getLogger(__name__)


@router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def bot_added_to_chat(event: ChatMemberUpdated, bot: Bot):
    """Обработчик добавления бота в чат/группу"""
    try:
        chat = event.chat
        chat_id = chat.id
        chat_type = chat.type
        
        # Получаем информацию о чате
        title = chat.title if hasattr(chat, 'title') else None
        username = chat.username if hasattr(chat, 'username') else None
        
        # Пытаемся получить ссылку-приглашение
        invite_link = None
        try:
            # Получаем информацию о боте в чате
            bot_member = await bot.get_chat_member(chat_id, bot.id)
            if bot_member.status in ['administrator', 'creator']:
                # Если бот админ, пытаемся получить ссылку-приглашение
                try:
                    # Проверяем, есть ли у бота права на создание ссылок
                    if hasattr(bot_member, 'can_invite_users') and bot_member.can_invite_users:
                        chat_invite_link = await bot.export_chat_invite_link(chat_id)
                        invite_link = chat_invite_link
                except Exception as e:
                    logger.warning(f"Не удалось получить ссылку-приглашение для чата {chat_id}: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при получении информации о боте в чате {chat_id}: {e}")
        
        # Сохраняем информацию о чате
        await db.add_or_update_chat(
            chat_id=chat_id,
            chat_type=chat_type,
            title=title,
            username=username,
            invite_link=invite_link,
            bot_is_admin=True
        )
        
        logger.info(f"✅ Бот добавлен в чат: {chat_id} ({title or username or 'без названия'})")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке добавления бота в чат: {e}", exc_info=True)


@router.my_chat_member(ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
async def bot_removed_from_chat(event: ChatMemberUpdated):
    """Обработчик удаления бота из чата/группы"""
    try:
        chat_id = event.chat.id
        
        # Обновляем статус бота в чате
        await db.add_or_update_chat(
            chat_id=chat_id,
            chat_type=event.chat.type,
            title=event.chat.title if hasattr(event.chat, 'title') else None,
            username=event.chat.username if hasattr(event.chat, 'username') else None,
            bot_is_admin=False
        )
        
        logger.info(f"❌ Бот удален из чата: {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке удаления бота из чата: {e}", exc_info=True)


@router.message(F.chat.type.in_(['group', 'supergroup']) & F.from_user.is_bot)
async def track_bot_messages(message: Message, bot: Bot):
    """Отслеживание сообщений от бота в группах - выполняется в фоне, не блокирует обработку"""
    # Выполняем в фоне, чтобы не блокировать обработку других сообщений
    try:
        # Проверяем, что сообщение от нашего бота
        if not message.from_user:
            return
        
        bot_id = message.from_user.id
        # Получаем ID нашего бота
        try:
            bot_info = await bot.get_me()
            if bot_info.id != bot_id:
                return  # Это не наш бот, пропускаем
        except Exception as e:
            logger.warning(f"Не удалось получить информацию о боте: {e}")
            return
        
        chat_id = message.chat.id
        
        # Выполняем операции с БД в фоне, не блокируя обработку
        try:
            # Увеличиваем счетчик сообщений
            await db.increment_chat_messages(chat_id)
            
            # Также обновляем информацию о чате, если её еще нет
            chat = await db.get_chat(chat_id)
            if not chat:
                await db.add_or_update_chat(
                    chat_id=chat_id,
                    chat_type=message.chat.type,
                    title=message.chat.title if hasattr(message.chat, 'title') else None,
                    username=message.chat.username if hasattr(message.chat, 'username') else None,
                    bot_is_admin=True
                )
        except Exception as db_error:
            # Логируем ошибку, но не прерываем работу бота
            logger.warning(f"Ошибка при обновлении статистики чата {chat_id}: {db_error}")
    except Exception as e:
        # Логируем ошибку, но не прерываем работу бота
        logger.warning(f"Ошибка при отслеживании сообщений бота: {e}")

