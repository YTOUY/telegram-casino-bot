from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging

from database import Database
from keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="lottery")
db = Database()


async def _show_lottery_menu(message, user_id, is_callback=False):
    """Вспомогательная функция для показа меню лотерей"""
    try:
        lotteries = await db.get_active_lotteries()
        
        if not lotteries:
            text = """🎫 <b>Лотереи</b>

В данный момент нет активных лотерей."""
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="lottery_menu")],
                [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")]
            ])
        else:
            text = f"""🎫 <b>Активные лотереи</b>

Найдено активных лотерей: {len(lotteries)}

Выберите лотерею для участия:"""
            
            keyboard_buttons = []
            for lottery in lotteries[:10]:  # Показываем первые 10
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"🎫 {lottery['title'][:30]}",
                        callback_data=f"lottery_view_{lottery['id']}"
                    )
                ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔄 Обновить", callback_data="lottery_menu"),
                InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        if is_callback:
            # Проверяем, есть ли фото в сообщении
            try:
                logger.info(f"🎫 Редактирование сообщения, есть фото: {bool(message.photo)}")
                if message.photo:
                    # Если есть фото, редактируем caption
                    await message.edit_caption(
                        caption=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    logger.info("🎫 Сообщение с фото успешно отредактировано")
                else:
                    # Если нет фото, редактируем текст
                    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
                    logger.info("🎫 Текстовое сообщение успешно отредактировано")
            except Exception as e:
                logger.error(f"❌ Ошибка при редактировании сообщения лотереи: {e}", exc_info=True)
                # Если не удалось отредактировать, отправляем новое сообщение
                try:
                    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
                    logger.info("🎫 Новое сообщение успешно отправлено")
                except Exception as e2:
                    logger.error(f"❌ Критическая ошибка при отправке сообщения лотереи: {e2}", exc_info=True)
        else:
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            logger.info("🎫 Ответ на команду /lottery отправлен")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в _show_lottery_menu: {e}", exc_info=True)


@router.message(Command("lottery"))
async def lottery_menu_command(message: Message):
    """Обработка команды /lottery"""
    user_id = message.from_user.id
    logger.info(f"🎫 Обработка команды /lottery, user_id={user_id}")
    await _show_lottery_menu(message, user_id, is_callback=False)


@router.callback_query(F.data == "lottery_menu")
async def lottery_menu_callback(callback: CallbackQuery):
    """Обработка callback lottery_menu"""
    try:
        user_id = callback.from_user.id
        logger.info(f"🎫 ========== lottery_menu_callback ВЫЗВАН ==========")
        logger.info(f"🎫 Обработка callback для lottery_menu, user_id={user_id}, callback_data={callback.data}")
        await callback.answer()
        await _show_lottery_menu(callback.message, user_id, is_callback=True)
        logger.info(f"🎫 ========== lottery_menu_callback ЗАВЕРШЕН ==========")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в lottery_menu_callback: {e}", exc_info=True)
        try:
            await callback.answer("❌ Ошибка при открытии лотерей", show_alert=True)
        except:
            pass


async def _show_lottery_details(message, user_id: int, lottery_id: int, is_callback=False):
    """Вспомогательная функция для показа деталей лотереи"""
    lottery = await db.get_lottery(lottery_id)
    
    if not lottery or lottery["status"] != "active":
        if is_callback:
            try:
                await message.answer("❌ Лотерея не найдена или завершена")
            except:
                pass
        return
    
    prizes = await db.get_lottery_prizes(lottery_id)
    user_tickets_count = await db.get_user_lottery_tickets_count(lottery_id, user_id)
    user = await db.get_user(user_id)
    balance = user["balance"] if user else 0.0
    
    # Форматируем условие завершения
    finish_text = ""
    if lottery["finish_type"] == "time":
        finish_text = f"⏰ До {lottery['finish_datetime']}"
    elif lottery["finish_type"] == "participants":
        finish_text = f"👥 При {lottery['finish_participants']} участниках"
    
    text = f"""🎫 <b>{lottery['title']}</b>

📄 {lottery['description']}

━━━━━━━━━━━━━━━━━━━━

💰 <b>Цена билета:</b> ${lottery['ticket_price']:.2f}
👤 <b>Ваши билеты:</b> {user_tickets_count}/{lottery['max_tickets_per_user']}
📊 <b>Всего билетов:</b> {lottery['total_tickets']}
{finish_text}

━━━━━━━━━━━━━━━━━━━━

🏆 <b>Призы:</b>
"""
    
    for prize in sorted(prizes, key=lambda x: x["position"]):
        text += f"{prize['position']}. {prize['prize_description']}\n"
    
    text += f"\n💰 <b>Ваш баланс:</b> ${balance:.2f}"
    
    keyboard_buttons = []
    
    can_buy = (user_tickets_count < lottery["max_tickets_per_user"] and 
               balance >= lottery["ticket_price"])
    
    if can_buy:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"💰 Купить билет (${lottery['ticket_price']:.2f})",
                callback_data=f"lottery_buy_{lottery_id}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"lottery_view_{lottery_id}"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="lottery_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    # Проверяем, есть ли фото в сообщении
    try:
        if is_callback and message.photo:
            # Если есть фото, редактируем caption
            await message.edit_caption(
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        elif is_callback:
            # Если нет фото, редактируем текст
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            # Отправляем новое сообщение
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"❌ Ошибка при отображении деталей лотереи: {e}", exc_info=True)
        if is_callback:
            try:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                pass


@router.callback_query(F.data.startswith("lottery_view_"))
async def lottery_view(callback: CallbackQuery):
    """Просмотр конкретной лотереи"""
    await callback.answer()
    
    try:
        lottery_id = int(callback.data.replace("lottery_view_", ""))
        user_id = callback.from_user.id
        await _show_lottery_details(callback.message, user_id, lottery_id, is_callback=True)
    except ValueError:
        logger.error(f"❌ Ошибка парсинга lottery_id из callback_data: {callback.data}")
        await callback.answer("❌ Ошибка при открытии лотереи", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Ошибка в lottery_view: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при открытии лотереи", show_alert=True)


@router.callback_query(F.data.startswith("lottery_buy_"))
async def lottery_buy_ticket(callback: CallbackQuery):
    """Купить билет лотереи"""
    try:
        lottery_id = int(callback.data.replace("lottery_buy_", ""))
        user_id = callback.from_user.id
        
        logger.info(f"🎫 Покупка билета лотереи #{lottery_id} пользователем {user_id}")
        
        lottery = await db.get_lottery(lottery_id)
        
        if not lottery or lottery["status"] != "active":
            await callback.answer("❌ Лотерея не найдена или завершена", show_alert=True)
            return
        
        # Покупаем билет
        ticket_number = await db.buy_lottery_ticket(lottery_id, user_id)
        
        if not ticket_number:
            user = await db.get_user(user_id)
            balance = user["balance"] if user else 0.0
            user_tickets_count = await db.get_user_lottery_tickets_count(lottery_id, user_id)
            
            if user_tickets_count >= lottery["max_tickets_per_user"]:
                await callback.answer("❌ Вы достигли лимита билетов", show_alert=True)
            elif balance < lottery["ticket_price"]:
                await callback.answer("❌ Недостаточно средств", show_alert=True)
            else:
                await callback.answer("❌ Ошибка при покупке билета", show_alert=True)
            return
        
        # Проверяем, нужно ли завершить лотерею
        updated_lottery = await db.get_lottery(lottery_id)
        
        # Если завершение по участникам и достигнуто нужное количество
        if (lottery["finish_type"] == "participants" and 
            lottery["finish_participants"] and 
            updated_lottery["total_tickets"] >= lottery["finish_participants"]):
            # Автоматически завершаем лотерею (розыгрыш будет через планировщик)
            pass
        
        # Обновляем информацию о лотерее
        await _show_lottery_details(callback.message, user_id, lottery_id, is_callback=True)
        
        # Отправляем подтверждение
        await callback.answer(f"✅ Билет #{ticket_number} куплен!")
        logger.info(f"🎫 Билет #{ticket_number} успешно куплен пользователем {user_id} для лотереи #{lottery_id}")
    except ValueError:
        logger.error(f"❌ Ошибка парсинга lottery_id из callback_data: {callback.data}")
        await callback.answer("❌ Ошибка при покупке билета", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Ошибка в lottery_buy_ticket: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при покупке билета", show_alert=True)


@router.callback_query(F.data == "back_main")
async def back_to_main_menu(callback: CallbackQuery):
    """Вернуться в главное меню - показывает то же самое, что и /start"""
    await callback.answer()
    from handlers.games import send_game_photo
    from keyboards import get_main_menu_keyboard
    
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
    
    balance = user["balance"] if user else 0.00
    username = user.get("username") or callback.from_user.username or callback.from_user.first_name or "User"
    
    # Получаем статистику пользователя (как в /start)
    top_position = await db.get_user_top_position(user_id)
    top_win = await db.get_user_top_win(user_id)
    favorite_game = await db.get_user_favorite_game(user_id)
    
    # Формируем информацию о пользователе
    user_display_name = username or "Пользователь"
    top_win_text = ""
    if top_win:
        top_win_text = f"🏆 ТОР-победа: ${top_win['win']:.2f} (х{top_win['multiplier']:.2f})"
    else:
        top_win_text = "🏆 ТОР-победа: $0.00 (х0.00)"
    
    # Формируем сообщение в том же формате, что и /start
    text = f"""📌 Подпишись: @arbuzikgame

<blockquote>
🌈 {user_display_name}, /top-{top_position}
{top_win_text}
🎮 Любимая игра: {favorite_game}
</blockquote>

💰 Баланс: ${balance:.2f}"""
    
    keyboard = get_main_menu_keyboard()
    
    # Отправляем фото старта
    await send_game_photo(callback, "старт.jpg", text, keyboard)

