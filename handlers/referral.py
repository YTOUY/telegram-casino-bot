from aiogram import Router, F
from aiogram.types import CallbackQuery
import aiosqlite

from database import Database
from utils.referrals import build_referral_view

router = Router()
db = Database()


@router.callback_query(F.data == "referral_menu")
async def show_referral_menu(callback: CallbackQuery):
    """Показать меню рефералов"""
    import logging
    logger = logging.getLogger(__name__)
    try:
        await callback.answer()  # Моментальный ответ на нажатие кнопки
    except Exception as e:
        # Игнорируем ошибку, если callback уже обработан или устарел
        error_msg = str(e).lower()
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning(f"Устаревший callback query в show_referral_menu: {e}")
        pass  # Игнорируем ошибку
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
    
    user["referral_count"] = await db.get_referral_count(user_id)
    # Убеждаемся, что referral_balance есть в словаре
    if "referral_balance" not in user:
        user["referral_balance"] = 0.0
    
    text, keyboard, _ = await build_referral_view(user, include_back=True, back_callback="back_main", db=db)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "withdraw_referral_balance")
async def withdraw_referral_balance(callback: CallbackQuery):
    """Вывести реферальный баланс на основной"""
    import logging
    logger = logging.getLogger(__name__)
    
    user_id = callback.from_user.id
    logger.info(f"🔄 Обработка вывода реферального баланса для пользователя {user_id}")
    
    try:
        await callback.answer()
    except Exception as e:
        # Игнорируем ошибку, если callback уже обработан или устарел
        error_msg = str(e).lower()
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning(f"Устаревший callback query в withdraw_referral_balance: {e}")
        pass  # Игнорируем ошибку
    
    try:
        user = await db.get_user(user_id)
        
        if not user:
            logger.error(f"❌ Пользователь {user_id} не найден")
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        # Получаем referral_balance, проверяя наличие поля в базе
        referral_balance = user.get("referral_balance")
        if referral_balance is None:
            # Если поля нет в результате, проверяем напрямую в базе
            async with aiosqlite.connect(db.db_path) as database:
                database.row_factory = aiosqlite.Row
                async with database.execute(
                    "SELECT referral_balance FROM users WHERE user_id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        referral_balance = row["referral_balance"] if "referral_balance" in row.keys() else 0.0
                    else:
                        referral_balance = 0.0
        
        # Преобразуем в float на случай, если это строка
        try:
            referral_balance = float(referral_balance) if referral_balance else 0.0
        except (ValueError, TypeError):
            referral_balance = 0.0
        
        logger.info(f"💰 Реферальный баланс пользователя {user_id}: ${referral_balance:.2f}")
        
        if referral_balance <= 0:
            logger.info(f"⚠️ Реферальный баланс пуст для пользователя {user_id}")
            await callback.answer("❌ Реферальный баланс пуст", show_alert=True)
            return
        
        # Определяем, откуда был вызван вывод (из профиля или из главного меню)
        back_callback = "back_main"  # По умолчанию возврат в главное меню
        if callback.message.reply_markup and callback.message.reply_markup.inline_keyboard:
            for row in callback.message.reply_markup.inline_keyboard:
                for button in row:
                    if button.callback_data == "profile_back":
                        back_callback = "profile_back"
                        break
        
        # Переводим реферальный баланс на основной баланс
        logger.info(f"💸 Перевод ${referral_balance:.2f} с реферального баланса на основной для пользователя {user_id}")
        async with aiosqlite.connect(db.db_path) as database:
            # Сначала проверяем, существует ли поле referral_balance
            try:
                await database.execute(
                    """UPDATE users 
                       SET balance = balance + ?,
                           referral_balance = 0.00
                       WHERE user_id = ?""",
                    (referral_balance, user_id),
                )
                await database.commit()
                logger.info(f"✅ Баланс успешно обновлен для пользователя {user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка при обновлении баланса: {e}")
                # Пробуем альтернативный способ - только обновление balance
                await db.update_balance(user_id, referral_balance)
                # Обнуляем referral_balance отдельным запросом
                try:
                    async with aiosqlite.connect(db.db_path) as database2:
                        await database2.execute(
                            "UPDATE users SET referral_balance = 0.00 WHERE user_id = ?",
                            (user_id,)
                        )
                        await database2.commit()
                except Exception as e2:
                    logger.warning(f"⚠️ Не удалось обнулить referral_balance: {e2}")
        
        await callback.answer(f"✅ ${referral_balance:.2f} переведено на основной баланс", show_alert=True)
        
        # Обновляем информацию о пользователе и показываем обновленное меню
        user = await db.get_user(user_id)
        if user:
            user["referral_count"] = await db.get_referral_count(user_id)
            if "referral_balance" not in user:
                user["referral_balance"] = 0.0
            text, keyboard, _ = await build_referral_view(user, include_back=True, back_callback=back_callback, db=db)
            
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отредактировать сообщение: {e}")
                await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            logger.error(f"❌ Не удалось получить обновленные данные пользователя {user_id}")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при выводе реферального баланса: {e}", exc_info=True)
        try:
            await callback.answer("❌ Произошла ошибка при выводе баланса", show_alert=True)
        except:
            pass




