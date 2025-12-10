import asyncio
import logging
import os
import aiosqlite
from io import BytesIO

from html import escape

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from keyboards import get_main_menu_keyboard, get_remove_keyboard
from utils.checks import (
    format_user_text,
    build_check_keyboard,
    build_share_text,
    decode_slot_symbols,
    build_captcha_keyboard,
    build_captcha_text,
    notify_check_owner,
)
from utils.referrals import build_referral_view
from utils.referrals import build_referral_view
from utils.subscription import check_subscription, get_subscription_keyboard
from config import REQUIRED_CHANNEL, REQUIRED_CHANNEL_ID

router = Router()
db = Database()
logger = logging.getLogger(__name__)

# Проверяем доступность PIL для обработки изображений
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL не установлен, проверка изображений будет пропущена")


async def send_photo(message_or_callback, image_filename: str, text: str, keyboard=None, is_callback: bool = False):
    """Вспомогательная функция для отправки фото"""
    image_path = os.path.join(os.getcwd(), image_filename)
    logger.info(f"📷 Попытка отправить фото: {image_filename}, путь: {image_path}, существует: {os.path.exists(image_path)}")
    
    if os.path.exists(image_path):
        photo_bytes = None
        pil_processed = False
        
        # Пытаемся проверить и исправить изображение с помощью PIL
        if PIL_AVAILABLE:
            try:
                # Открываем и проверяем изображение
                img = Image.open(image_path)
                img.verify()  # Проверяем целостность
                
                # Открываем снова для работы (verify закрывает файл)
                img = Image.open(image_path)
                img.load()  # Загружаем все данные
                
                # Сохраняем в BytesIO для получения исправленных байтов
                output = BytesIO()
                
                # Определяем формат сохранения
                if img.format == 'PNG':
                    # Для PNG сохраняем как есть
                    img.save(output, format='PNG', optimize=True)
                elif img.format in ['JPEG', 'JPG']:
                    # Для JPEG конвертируем в RGB если нужно
                    if img.mode != 'RGB':
                        if img.mode == 'RGBA':
                            # Создаем белый фон и вставляем изображение
                            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                            rgb_img.paste(img, mask=img.split()[-1])
                            img = rgb_img
                        else:
                            # Для других режимов просто конвертируем
                            img = img.convert('RGB')
                    img.save(output, format='JPEG', quality=95, optimize=True)
                else:
                    # Для других форматов конвертируем в PNG
                    if img.mode == 'RGBA':
                        # Сохраняем RGBA как PNG
                        img.save(output, format='PNG', optimize=True)
                    else:
                        # Конвертируем в RGB и сохраняем как PNG
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        img.save(output, format='PNG', optimize=True)
                
                photo_bytes = output.getvalue()
                pil_processed = True
                logger.info(f"✅ Изображение {image_filename} проверено и исправлено с помощью PIL")
            except Exception as pil_error:
                # Если PIL не может обработать файл, попробуем отправить напрямую
                logger.warning(f"⚠️ PIL не смог обработать файл {image_filename}: {pil_error}. Пробую отправить напрямую.")
        
        # Если PIL не доступен или не смог обработать, читаем файл напрямую
        if photo_bytes is None:
            try:
                with open(image_path, 'rb') as f:
                    photo_bytes = f.read()
                logger.info(f"📖 Файл {image_filename} прочитан напрямую ({len(photo_bytes)} байт)")
            except Exception as read_error:
                logger.error(f"❌ Не удалось прочитать файл {image_filename}: {read_error}")
                photo_bytes = None
        
        # Проверяем, что файл не пустой
        if not photo_bytes or len(photo_bytes) == 0:
            logger.warning(f"⚠️ Файл {image_filename} пустой или не прочитан")
            # Проверяем тип клавиатуры и тип чата
            from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
            if is_callback:
                is_group = message_or_callback.message.chat.type in ['group', 'supergroup']
            else:
                is_group = message_or_callback.chat.type in ['group', 'supergroup']
            is_reply_keyboard = isinstance(keyboard, ReplyKeyboardMarkup)
            
            # В группах всегда скрываем ReplyKeyboardMarkup
            if is_group:
                if is_reply_keyboard:
                    final_keyboard = ReplyKeyboardRemove(remove_keyboard=True)
                else:
                    final_keyboard = keyboard  # InlineKeyboardMarkup или None
            else:
                final_keyboard = keyboard
            
            # Отправляем текстовое сообщение
            try:
                logger.info(f"🔄 Файл пустой, отправляю текстовое сообщение")
                if is_callback:
                    await message_or_callback.message.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
                else:
                    await message_or_callback.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
                logger.info(f"✅ Текстовое сообщение успешно отправлено")
                return False
            except Exception as e:
                logger.error(f"Критическая ошибка при отправке сообщения: {e}", exc_info=True)
                return False
        
        # Пытаемся отправить фото
        try:
            # Используем BufferedInputFile для обработанных PIL изображений или FSInputFile для прямого чтения
            if pil_processed:
                photo = BufferedInputFile(photo_bytes, filename=image_filename)
            else:
                # Для прямого чтения используем FSInputFile
                photo = FSInputFile(image_path)
            
            # Проверяем тип клавиатуры и тип чата
            from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
            if is_callback:
                is_group = message_or_callback.message.chat.type in ['group', 'supergroup']
            else:
                is_group = message_or_callback.chat.type in ['group', 'supergroup']
            is_reply_keyboard = isinstance(keyboard, ReplyKeyboardMarkup)
            
            # В группах всегда скрываем ReplyKeyboardMarkup
            if is_group:
                if is_reply_keyboard:
                    final_keyboard = ReplyKeyboardRemove(remove_keyboard=True)
                else:
                    final_keyboard = keyboard  # InlineKeyboardMarkup или None
            else:
                final_keyboard = keyboard
            
            # Отправляем новое сообщение с фото
            if is_callback:
                await message_or_callback.message.answer_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=final_keyboard,
                    parse_mode="HTML"
                )
            else:
                await message_or_callback.answer_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=final_keyboard,
                    parse_mode="HTML"
                )
            logger.info(f"✅ Фото {image_filename} успешно отправлено")
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке фото {image_filename}: {e}", exc_info=True)
            # Проверяем тип клавиатуры и тип чата
            from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
            if is_callback:
                is_group = message_or_callback.message.chat.type in ['group', 'supergroup']
            else:
                is_group = message_or_callback.chat.type in ['group', 'supergroup']
            is_reply_keyboard = isinstance(keyboard, ReplyKeyboardMarkup)
            
            # В группах всегда скрываем ReplyKeyboardMarkup
            if is_group:
                if is_reply_keyboard:
                    final_keyboard = ReplyKeyboardRemove(remove_keyboard=True)
                else:
                    final_keyboard = keyboard  # InlineKeyboardMarkup или None
            else:
                final_keyboard = keyboard
            
            # Если не удалось отправить фото, отправляем обычное сообщение
            try:
                logger.info(f"🔄 Попытка отправить текстовое сообщение вместо фото")
                if is_callback:
                    await message_or_callback.message.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
                else:
                    await message_or_callback.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
                logger.info(f"✅ Текстовое сообщение успешно отправлено")
                return False
            except Exception as e2:
                logger.error(f"Критическая ошибка при отправке сообщения: {e2}", exc_info=True)
                return False
    else:
        logger.warning(f"Файл {image_filename} не найден по пути: {image_path}")
        # Проверяем тип клавиатуры и тип чата
        from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
        if is_callback:
            is_group = message_or_callback.message.chat.type in ['group', 'supergroup']
        else:
            is_group = message_or_callback.chat.type in ['group', 'supergroup']
        is_reply_keyboard = isinstance(keyboard, ReplyKeyboardMarkup)
        
        # В группах всегда скрываем ReplyKeyboardMarkup
        if is_group:
            if is_reply_keyboard:
                final_keyboard = ReplyKeyboardRemove(remove_keyboard=True)
            else:
                final_keyboard = keyboard  # InlineKeyboardMarkup или None
        else:
            final_keyboard = keyboard
        
        # Если файл не найден, отправляем обычное сообщение
        try:
            logger.info(f"🔄 Файл не найден, отправляю текстовое сообщение")
            if is_callback:
                await message_or_callback.message.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
            else:
                await message_or_callback.answer(text, reply_markup=final_keyboard, parse_mode="HTML")
            logger.info(f"✅ Текстовое сообщение успешно отправлено (файл не найден)")
            return False
        except Exception as e:
            logger.error(f"Критическая ошибка при отправке сообщения: {e}", exc_info=True)
            return False


@router.message(Command("hidekeyboard", "скрыть"))
async def cmd_hide_keyboard(message: Message):
    """Скрыть reply keyboard"""
    from keyboards import get_remove_keyboard
    remove_kb = get_remove_keyboard()
    await message.answer("⌨️ Клавиатура скрыта", reply_markup=remove_kb)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    # Блокируем /start в группах
    if message.chat.type in ['group', 'supergroup']:
        return
    
    logger.info("=" * 50)
    logger.info("🚀 КОМАНДА /START ОБРАБАТЫВАЕТСЯ!")
    logger.info(f"🚀 Пользователь: {message.from_user.id}, текст: {message.text}")
    logger.info("=" * 50)
    try:
        # Получаем текущее состояние
        current_state = await state.get_state()
        # Очищаем состояние только если это не состояние создания промокода
        if current_state and not str(current_state).startswith("PromoCodeStates"):
            await state.clear()
            logger.info("✓ Состояние очищено")
        else:
            logger.info(f"✓ Состояние не очищено (текущее состояние: {current_state})")
        
        logger.info(f"🔵 Обработчик cmd_start вызван для пользователя {message.from_user.id}")
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or "User"
        
        logger.info(f"📝 Создание пользователя: {user_id}, {username}")
        
        # Создаем пользователя, если его нет
        try:
            referral_code = None
            check_code = None
            if message.text and len(message.text.split()) > 1:
                param = message.text.split()[1]
                if param.startswith("check_"):
                    # Это активация чека
                    check_code = param.replace("check_", "")
                    logger.info(f"🎫 Код чека: {check_code}")
                else:
                    # Это реферальный код
                    referral_code = param
                    logger.info(f"📎 Реферальный код: {referral_code}")
            
            is_new_user, referred_by = await db.create_user(user_id, username, referral_code)
            
            # Если это активация чека, обрабатываем её
            if check_code:
                await handle_check_activation(message, check_code, state)
                return
            
            # Проверяем, не промокод ли это
            if message.text and len(message.text.split()) > 1:
                param = message.text.split()[1]
                if param.startswith("promo_"):
                    promo_param = param.replace("promo_", "")
                    # Ищем промокод по activation_link или по code
                    promo = await db.get_promo_code(promo_param)
                    if not promo:
                        # Пробуем найти по activation_link
                        async with aiosqlite.connect(db.db_path) as database:
                            database.row_factory = aiosqlite.Row
                            async with database.execute(
                                "SELECT * FROM promo_codes WHERE activation_link = ?", (promo_param,)
                            ) as cursor:
                                row = await cursor.fetchone()
                                if row:
                                    promo = dict(row)
                    
                    if promo:
                        await handle_promo_activation(message, promo['code'], state)
                    else:
                        await message.answer("❌ Промокод не найден")
                    return
            logger.info("✓ Пользователь создан/обновлен")
            
            # Проверяем и выдаем ежедневные арбузз коины
            try:
                daily_given = await db.check_and_give_daily_arbuzz(user_id)
                if daily_given:
                    logger.info(f"🎁 Ежедневные 100 арбузз коинов выданы пользователю {user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка при выдаче ежедневных арбузз коинов: {e}", exc_info=True)
        except Exception as db_error:
            logger.error(f"❌ Ошибка при создании пользователя: {db_error}", exc_info=True)
            await message.answer("❌ Ошибка при инициализации. Попробуйте удалить базу данных database.db и перезапустить бота.")
            return
        
        # Отправляем реферальное уведомление, если это новый пользователь с реферальным кодом
        if is_new_user and referred_by:
            try:
                referred_by_user = await db.get_user(referred_by)
                if referred_by_user and referred_by_user.get("referral_notifications", True):
                    # Получаем имя нового пользователя
                    new_user_name = username or "юз"
                    # Формируем имя с @ для пользователя с username, или просто имя
                    if message.from_user.username:
                        display_name = f"@{message.from_user.username}"
                    else:
                        display_name = new_user_name
                    
                    # Отправляем уведомление рефералу
                    try:
                        await message.bot.send_message(
                            referred_by,
                            f"Поздравляем, у вас новый реферал - {display_name}"
                        )
                        logger.info(f"✅ Реферальное уведомление отправлено пользователю {referred_by} о новом реферале {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при отправке реферального уведомления: {e}")
            except Exception as e:
                logger.error(f"❌ Ошибка при проверке реферального уведомления: {e}")
        
        # Получаем данные пользователя
        user = await db.get_user(user_id)
        balance_usd = user["balance"] if user else 0.00
        logger.info(f"💰 Баланс пользователя: ${balance_usd:.2f}")
        
        # Выполняем все тяжелые операции параллельно для ускорения
        top_position, top_win, favorite_game = await asyncio.gather(
            db.get_user_top_position(user_id),
            db.get_user_top_win(user_id),
            db.get_user_favorite_game(user_id),
            return_exceptions=True
        )
        
        # Обрабатываем возможные ошибки
        if isinstance(top_position, Exception):
            logger.error(f"Ошибка при получении позиции в топе: {top_position}")
            top_position = 1
        if isinstance(top_win, Exception):
            logger.error(f"Ошибка при получении топ-выигрыша: {top_win}")
            top_win = None
        if isinstance(favorite_game, Exception):
            logger.error(f"Ошибка при получении любимой игры: {favorite_game}")
            favorite_game = "🎲 Кубик"
        
        # Формируем информацию о пользователе
        user_display_name = username or "Пользователь"
        
        # Формируем финальный текст с актуальными данными
        top_win_text = ""
        if top_win:
            top_win_text = f"🏆 ТОР-победа: ${top_win['win']:.2f} (х{top_win['multiplier']:.2f})"
        else:
            top_win_text = "🏆 ТОР-победа: $0.00 (х0.00)"
        
        # Формируем главное меню с описанием казино
        text = f"""🎰 <b>Добро пожаловать в Arbuz Game!</b>

🚀 <b>Начни играть прямо сейчас!</b>

📌 <b><a href="https://t.me/cryptogifts_ru">Тгк основное</a></b>
📌 <b><a href="https://t.me/arbuzikgame">Тгк казино</a></b>

<blockquote>
👤 <b>{user_display_name}</b>
💰 Баланс: ${balance_usd:.2f}
🏆 Топ: #{top_position}
</blockquote>"""
        
        keyboard = get_main_menu_keyboard()
        # Проверяем тип клавиатуры для логирования
        from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
        if isinstance(keyboard, ReplyKeyboardMarkup):
            logger.info(f"📤 Отправка сообщения с клавиатурой ({len(keyboard.keyboard)} рядов)")
        elif isinstance(keyboard, ReplyKeyboardRemove):
            logger.info(f"📤 Отправка сообщения с удалением клавиатуры")
        else:
            logger.info(f"📤 Отправка сообщения без клавиатуры")
        logger.info(f"📝 Текст сообщения (первые 100 символов): {text[:100]}...")
        
        # Отправляем фото старта
        await send_photo(message, "старт.jpg", text, keyboard, is_callback=False)
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в cmd_start: {e}", exc_info=True)
        logger.error(f"❌ Детали ошибки: {type(e).__name__}: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при запуске бота. Попробуйте позже.")
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")


@router.message(F.text == "➕ Депозит")
async def show_deposit(message: Message, state: FSMContext):
    """Показать меню депозита"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    logger.info("=" * 50)
    logger.info(f"🔵 Обработчик show_deposit вызван для пользователя {message.from_user.id}")
    logger.info(f"📝 Текст сообщения: '{message.text}'")
    logger.info("=" * 50)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    balance_usd = user["balance"]
    text = f"""💵 <b>Депозит</b>
    
💰 <b>Баланс:</b> ${balance_usd:.2f}
    
<b>Минимальный депозит:</b> $0.10

<b>Выберите способ пополнения:</b>"""
    
    from keyboards import get_deposit_keyboard
    keyboard = get_deposit_keyboard()
    logger.info(f"📤 Отправка меню депозита с inline-кнопками: {len(keyboard.inline_keyboard)} рядов")
    # Логируем все callback_data для отладки
    for row in keyboard.inline_keyboard:
        for button in row:
            logger.info(f"   Кнопка: {button.text} -> callback_data: {button.callback_data}")
    # Для депозита нет отдельного изображения, отправляем обычное сообщение
    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(F.text == "🎮 Игры")
async def show_games(message: Message, state: FSMContext):
    """Показать меню игр"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    logger.info("=" * 50)
    logger.info(f"🔵 Обработчик show_games вызван для пользователя {message.from_user.id}")
    logger.info(f"📝 Текст сообщения: '{message.text}'")
    logger.info("=" * 50)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    balance_usd = user["balance"]
    
    text = f"""🎮 <b>Игры</b>

🙌 <b>Твой шанс выиграть до х1000</b>

ℹ️ <i>Все исходы определяются через Telegram</i>

💰 <b>Баланс:</b> ${balance_usd:.2f}"""
    
    from keyboards import get_games_menu_keyboard
    keyboard = get_games_menu_keyboard()
    logger.info(f"📤 Отправка меню игр с inline-кнопками: {len(keyboard.inline_keyboard)} рядов")
    await send_photo(message, "игры.jpg", text, keyboard, is_callback=False)


@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message, state: FSMContext):
    """Показать настройки"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    logger.info("=" * 50)
    logger.info(f"🔵 Обработчик show_settings вызван для пользователя {message.from_user.id}")
    logger.info(f"📝 Текст сообщения: '{message.text}'")
    logger.info("=" * 50)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    ref_notif = "Вкл" if user["referral_notifications"] else "Выкл"
    base_bet = user["base_bet"]
    
    text = f"""⚙️ <b>Настройки</b>

📌 Реф. увед — получайте уведомления о каждом новом реферале
📌 Базовая ставка — ставка, установленная по умолчанию для всех игр

<b>Текущие настройки:</b>
🔔 Реф. увед.: {ref_notif}
💰 Базовая ставка: ${base_bet:.2f}"""
    
    from keyboards import get_settings_keyboard
    keyboard = get_settings_keyboard()
    logger.info(f"📤 Отправка меню настроек с inline-кнопками: {len(keyboard.inline_keyboard)} рядов")
    result = await send_photo(message, "настройки.jpg", text, keyboard, is_callback=False)
    if not result:
        logger.warning(f"⚠️ Сообщение настроек не было отправлено, попытка повторной отправки")
        try:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            logger.info("✅ Сообщение настроек отправлено повторно")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при отправке настроек: {e}", exc_info=True)


@router.message(F.text == "👯 Рефералы")
async def show_referral(message: Message, state: FSMContext):
    """Показать реферальную систему"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    logger.info("=" * 50)
    logger.info(f"🔵 Обработчик show_referral вызван для пользователя {message.from_user.id}")
    logger.info(f"📝 Текст сообщения: '{message.text}'")
    logger.info("=" * 50)
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    user["referral_count"] = await db.get_referral_count(user_id)
    text, keyboard, _ = await build_referral_view(user, db=db)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text == "💼 Кошелек")
async def show_wallet(message: Message, state: FSMContext):
    """Показать кошелек"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    balance_usd = user.get("balance", 0.0)
    locked_balance_usd = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    
    from ton_price import get_ton_to_usd_rate, usd_to_ton
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    locked_balance_ton = usd_to_ton(locked_balance_usd, ton_rate)
    
    text = f"""💼 <b>Кошелек</b>

💰 <b>Доступный баланс:</b> {balance_ton:.4f} TON (${balance_usd:.2f})
🔒 <b>Заблокированный баланс:</b> {locked_balance_ton:.4f} TON (${locked_balance_usd:.2f})
🍉 <b>Демо баланс (Arbuzz Coins):</b> {arbuzz_balance:.0f} AC"""
    
    if locked_balance_usd > 0 and rollover_requirement > 0:
        text += f"\n\n⚠️ <b>Требуется отыграть:</b> ${rollover_requirement:.2f}"
        text += f"\n<i>Заблокированные средства можно использовать для игр, но вывести их можно будет только после выполнения требования отыгрыша.</i>"
    
    text += "\n\nВыберите действие:"
    
    from keyboards import get_wallet_keyboard
    wallet_keyboard = get_wallet_keyboard()
    logger.info(f"💼 Отправляю кошелек для пользователя {user_id}, клавиатура: {wallet_keyboard}")
    await send_photo(message, "кошелек.jpg", text, wallet_keyboard, is_callback=False)


async def build_profile_view(user_id: int, user: dict):
    balance_usd = user["balance"]
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    top_position = await db.get_user_top_position(user_id)
    top_win = await db.get_user_top_win(user_id)
    total_turnover_usd = await db.get_user_total_turnover(user_id)
    total_deposits_usd = await db.get_user_total_deposits(user_id)
    total_withdrawals_usd = await db.get_user_total_withdrawals(user_id)
    
    username = user["username"] or "Пользователь"
    
    best_bet_text = "Нет данных"
    if top_win:
        best_bet_text = f"${top_win['win']:.2f} (x{top_win['multiplier']:.2f}) - {top_win['game_type']}"
    
    text = f"""👤 <b>Профиль</b>

👤 <b>Игрок:</b> {username}
💰 <b>Баланс:</b> ${balance_usd:.2f}
🍉 <b>Демо баланс (Arbuzz Coins):</b> {arbuzz_balance:.0f} AC
🏆 <b>Место в топе:</b> #{top_position}

📊 <b>Статистика:</b>
📈 <b>Оборот за все время:</b> ${total_turnover_usd:.2f}
➕ <b>Депозиты:</b> ${total_deposits_usd:.2f}
➖ <b>Выводы:</b> ${total_withdrawals_usd:.2f}
🎯 <b>Лучшая ставка:</b> {best_bet_text}"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎫 Чеки", callback_data="profile_checks"),
            InlineKeyboardButton(text="🤝 Рефералка", callback_data="profile_referral"),
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="profile_promo_codes"),
        ]
    ])
    return text, keyboard


@router.message(F.text == "👤 Профиль")
async def show_profile(message: Message, state: FSMContext):
    """Показать профиль"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    # Очищаем состояние при переходе в меню
    await state.clear()
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    text, keyboard = await build_profile_view(user_id, user)
    await send_photo(message, "профиль.jpg", text, keyboard, is_callback=False)


@router.message(F.text == "🏆 Топ")
async def show_top(message: Message, state: FSMContext):
    """Показать топ с выбором категории"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    await state.clear()
    from keyboards import get_top_category_keyboard
    
    text = """🏆 <b>ТОП</b>

🏆 Выберите категорию топа:"""
    
    # Отправляем только текстовое сообщение без фото
    await message.answer(text, reply_markup=get_top_category_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("top_category_"))
async def handle_top_category(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора категории топа"""
    await callback.answer()
    
    category = callback.data.replace("top_category_", "")
    logger.info(f"🏆 Выбрана категория топа: {category}")
    
    from keyboards import get_top_period_keyboard
    
    category_names = {
        "players": "Топ игроков",
        "chats": "Топ чатов"
    }
    category_name = category_names.get(category, "Топ игроков")
    
    text = f"""🏆 <b>{category_name}</b>

Выберите период для просмотра топа:"""
    
    await callback.message.edit_text(text, reply_markup=get_top_period_keyboard(category), parse_mode="HTML")


@router.callback_query(F.data.startswith("top_"))
async def handle_top_period(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора периода топа"""
    await callback.answer()
    
    # Формат: top_players_day, top_chats_month, top_players_all
    parts = callback.data.replace("top_", "").split("_")
    
    if len(parts) < 2:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return
    
    category = parts[0]  # players или chats
    period = parts[1]   # day, month, all
    
    logger.info(f"🏆 Топ запрошен: категория={category}, период={period}, callback_data={callback.data}")
    
    period_names = {
        "day": "За день",
        "month": "За месяц",
        "all": "За все время"
    }
    period_name = period_names.get(period, "За все время")
    
    category_names = {
        "players": "Топ игроков",
        "chats": "Топ чатов"
    }
    category_name = category_names.get(category, "Топ игроков")
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    username = user.get("username") if user else callback.from_user.username or "Пользователь"
    
    if category == "players":
        # Получаем топ игроков
        top_players = await db.get_top_by_turnover(period, limit=10)
        logger.info(f"🏆 Получено игроков в топе: {len(top_players)}, период={period}")
        
        # Получаем позицию и оборот пользователя
        user_position = await db.get_user_turnover_position(user_id, period)
        user_turnover = await db.get_user_turnover(user_id, period)
        logger.info(f"🏆 Пользователь {user_id}: позиция={user_position}, оборот={user_turnover}, период={period}")
        
        # Формируем текст
        text = f"""🏆 <b>{category_name} - {period_name}</b>

<blockquote>
Ваше место в топе: #{user_position}
Ваш оборот: ${user_turnover:.2f}
</blockquote>


<b>Топ 10 игроков:</b>

"""
        
        # Добавляем топ 10 игроков
        for i, player in enumerate(top_players, 1):
            player_username = player.get("username") or f"ID{player['user_id']}"
            turnover = player.get("turnover", 0)
            text += f"{i}. {player_username} - ${turnover:.2f}\n"
    
    elif category == "chats":
        # Для чатов пока что заглушка
        text = f"""🏆 <b>{category_name} - {period_name}</b>

📊 <b>Топ чатов</b>

Функция в разработке..."""
    
    from keyboards import get_top_period_keyboard
    await callback.message.edit_text(text, reply_markup=get_top_period_keyboard(category), parse_mode="HTML")


@router.callback_query(F.data == "top_back")
async def handle_top_back(callback: CallbackQuery, state: FSMContext):
    """Вернуться к выбору категории топа"""
    await callback.answer()
    
    from keyboards import get_top_category_keyboard
    
    text = """🏆 <b>ТОП</b>

🏆 Выберите категорию топа:"""
    
    await callback.message.edit_text(text, reply_markup=get_top_category_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    try:
        await callback.message.delete()
    except Exception:
        pass


async def render_profile_checks(callback: CallbackQuery):
    user_id = callback.from_user.id
    checks = await db.get_checks_by_creator(user_id, limit=5)
    
    if not checks:
        text = "🎫 <b>Мои чеки</b>\n\nУ вас пока нет созданных чеков."
        keyboard_rows = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_back")]]
    else:
        lines = []
        keyboard_rows = []
        for idx, check in enumerate(checks, start=1):
            lines.append(
                f"{idx}. <code>{check['check_code']}</code> — ${check['amount_per_activation']:.2f}, "
                f"осталось {check['remaining_activations']}/{check['total_activations']}"
            )
            keyboard_rows.append([
                InlineKeyboardButton(text=f"📤 {check['check_code']}", callback_data=f"check_share_{check['check_code']}"),
                InlineKeyboardButton(text="🗑", callback_data=f"check_delete_{check['check_code']}"),
            ])
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_back")])
        text = "🎫 <b>Мои чеки</b>\n\n" + "\n".join(lines)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "profile_checks")
async def profile_checks(callback: CallbackQuery):
    """Управление созданными чеками"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    await render_profile_checks(callback)


@router.callback_query(F.data == "profile_back")
async def profile_back(callback: CallbackQuery):
    """Возврат к профилю"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
    
    text, keyboard = await build_profile_view(user_id, user)
    await send_photo(callback, "профиль.jpg", text, keyboard, is_callback=True)


@router.callback_query(F.data == "profile_referral")
async def profile_referral(callback: CallbackQuery):
    """Показать реферальную систему в профиле"""
    try:
        await callback.answer()  # Моментальный ответ на нажатие кнопки
    except Exception as e:
        # Игнорируем ошибку, если callback уже обработан или устарел
        error_msg = str(e).lower()
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning(f"Устаревший callback query в profile_referral: {e}")
        pass  # Игнорируем ошибку
    
    user = await db.get_user(callback.from_user.id)
    
    if not user:
        return
    
    user["referral_count"] = await db.get_referral_count(callback.from_user.id)
    # Убеждаемся, что referral_balance есть в словаре
    if "referral_balance" not in user:
        user["referral_balance"] = 0.0
    
    text, keyboard, _ = await build_referral_view(user, include_back=True, back_callback="profile_back", db=db)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("check_delete_"))
async def handle_check_delete(callback: CallbackQuery):
    """Удаление чека"""
    code = callback.data.split("_", 2)[2]
    user_id = callback.from_user.id
    
    deleted = await db.delete_check(code, user_id)
    if deleted:
        await render_profile_checks(callback)
        await callback.answer("Чек удалён")
    else:
        await callback.answer("❌ Не удалось удалить чек", show_alert=True)


async def handle_check_activation(message: Message, check_code: str, state: FSMContext):
    """Обработка активации чека"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    # Получаем чек
    check = await db.get_check(check_code)
    if not check:
        await message.answer("❌ Чек не найден")
        return
    
    # Проверяем, не активировал ли уже пользователь этот чек
    if await db.has_user_activated_check(check["id"], user_id):
        await message.answer("❌ Вы уже активировали этот чек")
        return
    
    # Проверяем, есть ли еще активации
    if check["remaining_activations"] <= 0:
        await message.answer("❌ Чек исчерпан (все активации использованы)")
        return
    
    # Если нужна капча, показываем её
    if check["requires_captcha"]:
        dice_message = await message.answer_dice(emoji="🎰")
        symbols = decode_slot_symbols(dice_message.dice.value)
        captcha_result = "".join(symbols)
        total_slots = len(symbols)
        await asyncio.sleep(3)

        await state.update_data(
            check_id=check["id"],
            check_code=check_code,
            captcha_result=captcha_result,
            captcha_total=total_slots,
        )
        
        captcha_message = await message.answer(
            build_captcha_text([], total_slots),
            reply_markup=build_captcha_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(
            captcha_message_id=captcha_message.message_id,
            captcha_chat_id=captcha_message.chat.id,
        )
        return
    
    # Проверяем тип депозита
    deposit_type = check.get("deposit_type", "no_deposit")
    if deposit_type == "deposit":
        min_deposit = check.get("min_deposit", 0.0)
        user_total_deposits = await db.get_user_total_deposits(user_id)
        if user_total_deposits < min_deposit:
            await message.answer(
                f"❌ <b>Недостаточно депозитов для активации чека</b>\n\n"
                f"Требуется минимальный депозит: ${min_deposit:.2f}\n"
                f"Ваш общий депозит: ${user_total_deposits:.2f}",
                parse_mode="HTML"
            )
            return
    
    # Если капча не нужна, сразу активируем
    success = await db.activate_check(check["id"], user_id)
    if success:
        amount = check["amount_per_activation"]
        rollover_multiplier = check.get("rollover_multiplier", 1.0)
        
        # Если есть отыгрыш, добавляем средства в заблокированный баланс
        if rollover_multiplier > 1.0:
            await db.add_rollover_requirement(user_id, amount, rollover_multiplier)
            user = await db.get_user(user_id)
            rollover_requirement = user.get("rollover_requirement", 0.0)
            
            text = f"""✅ <b>Чек активирован!</b>

💰 Получено: ${amount:.2f}
📊 Требуется отыграть: ${rollover_requirement:.2f} (${amount:.2f} × {rollover_multiplier})

⚠️ <b>Внимание:</b> Вы сможете использовать полученные средства для игр, но вывести их можно будет только после выполнения требования отыгрыша."""
        else:
            # Если отыгрыша нет, добавляем на обычный баланс
            await db.update_balance(user_id, amount)
            
            text = f"""✅ <b>Чек активирован!</b>

💰 Получено: ${amount:.2f}

Средства зачислены на ваш баланс и доступны для вывода."""
        
        user_text_formatted = format_user_text(check.get("text"))
        if user_text_formatted:
            text += f"\n\n{user_text_formatted}"

        result_keyboard = build_check_keyboard(
            check_code,
            check.get("button_text"),
            check.get("button_url"),
        )

        if check["image_url"]:
            await message.answer_photo(photo=check["image_url"], caption=text, reply_markup=result_keyboard, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=result_keyboard, parse_mode="HTML")
        
        await notify_check_owner(db, message.bot, check["id"], check_code, message.from_user)
    else:
        await message.answer("❌ Ошибка при активации чека")


class PromoCodeInputStates(StatesGroup):
    waiting_promo_code = State()


@router.callback_query(F.data == "profile_promo_codes")
async def profile_promo_codes(callback: CallbackQuery, state: FSMContext):
    """Показать меню промокодов"""
    await callback.answer()
    
    await callback.message.answer(
        "🎟️ <b>Промокоды</b>\n\n"
        "Введите код промокода для активации:\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(PromoCodeInputStates.waiting_promo_code)


@router.message(PromoCodeInputStates.waiting_promo_code)
async def handle_promo_code_input(message: Message, state: FSMContext):
    """Обработка ввода промокода"""
    # Проверяем, что это текстовое сообщение
    if not message.text:
        await message.answer("❌ Пожалуйста, введите код промокода текстом")
        return
    
    logger.info(f"📝 Получен ввод промокода от пользователя {message.from_user.id}: {message.text}")
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Ввод промокода отменен")
        return
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    if not message.text.strip():
        await message.answer("❌ Пожалуйста, введите код промокода")
        return
    
    promo_code = message.text.strip().upper()
    logger.info(f"🎟️ Обработка промокода: {promo_code}")
    await handle_promo_activation(message, promo_code, state)


async def handle_promo_activation(message: Message, promo_code: str, state: FSMContext):
    """Обработка активации промокода"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Получаем промокод
    promo = await db.get_promo_code(promo_code)
    if not promo:
        await message.answer("❌ Промокод не найден")
        await state.clear()
        return
    
    # Проверяем, не активировал ли уже пользователь этот промокод
    promo_id = promo["id"]
    if await db.has_user_activated_promo(promo_id, user_id):
        await message.answer("❌ Вы уже активировали этот промокод")
        await state.clear()
        return
    
    # Проверяем, есть ли еще активации
    if promo["remaining_activations"] <= 0:
        await message.answer("❌ Промокод исчерпан (все активации использованы)")
        await state.clear()
        return
    
    # Проверяем тип депозита
    deposit_type = promo.get("deposit_type", "no_deposit")
    if deposit_type == "deposit":
        min_deposit = promo.get("min_deposit", 0.0)
        user_total_deposits = await db.get_user_total_deposits(user_id)
        if user_total_deposits < min_deposit:
            await message.answer(
                f"❌ <b>Недостаточно депозитов для активации промокода</b>\n\n"
                f"Требуется минимальный депозит: ${min_deposit:.2f}\n"
                f"Ваш общий депозит: ${user_total_deposits:.2f}",
                parse_mode="HTML"
            )
            await state.clear()
            return
    
    # Проверяем подписку на канал, если требуется
    if promo["requires_channel_subscription"] and promo["channel_username"]:
        channel_username = promo["channel_username"].lstrip('@')
        try:
            member = await message.bot.get_chat_member(f"@{channel_username}", user_id)
            if member.status not in ["member", "administrator", "creator"]:
                await message.answer(
                    f"❌ Для активации промокода необходимо подписаться на канал @{channel_username}\n\n"
                    f"Подпишитесь и попробуйте снова."
                )
                await state.clear()
                return
        except Exception as e:
            logger.error(f"Ошибка при проверке подписки на канал: {e}")
            await message.answer(
                f"❌ Ошибка при проверке подписки на канал. Убедитесь, что бот является администратором канала @{channel_username}"
            )
            await state.clear()
            return
    
    # Активируем промокод
    success = await db.activate_promo_code(promo_id, user_id)
    if success:
        amount = promo["amount"]
        rollover_multiplier = promo.get("rollover_multiplier", 1.0)
        
        # Все равно записываем как депозит для статистики
        await db.add_deposit(user_id, amount, "promo_code")
        
        # Если есть отыгрыш, добавляем средства в заблокированный баланс
        if rollover_multiplier > 1.0:
            await db.add_rollover_requirement(user_id, amount, rollover_multiplier)
            user = await db.get_user(user_id)
            rollover_requirement = user.get("rollover_requirement", 0.0)
            
            text = f"""✅ <b>Промокод активирован!</b>

🎟️ Промокод: <code>{promo_code}</code>
💰 Получено: ${amount:.2f}
📊 Требуется отыграть: ${rollover_requirement:.2f} (${amount:.2f} × {rollover_multiplier})

⚠️ <b>Внимание:</b> Вы сможете использовать полученные средства для игр, но вывести их можно будет только после выполнения требования отыгрыша.

Спасибо за использование промокода! 🎉"""
        else:
            # Если отыгрыша нет, добавляем на обычный баланс
            await db.update_balance(user_id, amount)
            
            # Получаем обновленный баланс
            updated_user = await db.get_user(user_id)
            new_balance = updated_user["balance"]
            
            text = f"""✅ <b>Промокод активирован!</b>

🎟️ Промокод: <code>{promo_code}</code>
💰 Получено: ${amount:.2f}
💵 Ваш баланс: ${new_balance:.2f}

Спасибо за использование промокода! 🎉"""
        
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Ошибка при активации промокода")
    
    await state.clear()


@router.callback_query(F.data.startswith("activate_promo_"))
async def activate_promo_from_button(callback: CallbackQuery, state: FSMContext):
    """Активация промокода через кнопку"""
    try:
        await callback.answer()
    except Exception as e:
        # Игнорируем ошибку "query is too old"
        error_msg = str(e).lower()
        if "too old" not in error_msg and "timeout" not in error_msg:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка при ответе на callback: {e}")
    
    promo_code = callback.data.replace("activate_promo_", "").upper()
    await handle_promo_activation(callback.message, promo_code, state)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Обработчик проверки подписки на канал"""
    user_id = callback.from_user.id
    
    # Проверяем подписку (используем ID канала, если указан)
    is_subscribed = await check_subscription(
        bot, 
        user_id, 
        channel=REQUIRED_CHANNEL, 
        channel_id=REQUIRED_CHANNEL_ID
    )
    
    if is_subscribed:
        # Если подписан, показываем главное меню
        await callback.answer("✅ Отлично! Вы подписаны на канал")
        
        # Показываем главное меню
        user = await db.get_user(user_id)
        if not user:
            username = callback.from_user.username or callback.from_user.first_name or "User"
            await db.create_user(user_id, username)
            user = await db.get_user(user_id)
        
        balance = user.get("balance", 0.0) if user else 0.0
        from ton_price import get_ton_to_usd_rate, usd_to_ton
        ton_rate = await get_ton_to_usd_rate()
        balance_ton = usd_to_ton(balance, ton_rate)
        
        text = f"""🎰 <b>Добро пожаловать!</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON (${balance:.2f})

Выберите действие:"""
        
        keyboard = get_main_menu_keyboard()
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        # Если не подписан, показываем сообщение снова
        channel_username = REQUIRED_CHANNEL.lstrip("@")
        text = f"""🔒 <b>Требуется подписка</b>

Для использования бота необходимо подписаться на наш канал:

📢 <b>@{channel_username}</b>

После подписки нажмите кнопку "✅ Я подписался" для проверки."""
        
        keyboard = get_subscription_keyboard(REQUIRED_CHANNEL)
        
        try:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        await callback.answer("❌ Вы еще не подписаны на канал", show_alert=True)

