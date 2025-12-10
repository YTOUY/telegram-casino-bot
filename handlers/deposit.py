from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import logging
import os
import aiosqlite

from database import Database
from config import TON_ADDRESS, MAX_DEPOSIT
from crypto_pay import crypto_pay
from ton_price import get_ton_to_usd_rate, usd_to_ton, ton_to_usd
from ton_chain import find_incoming_tx_by_comment
from xrocket_api import create_invoice as xrocket_create_invoice

router = Router()
db = Database()
logger = logging.getLogger(__name__)


async def send_photo_deposit(callback: CallbackQuery, image_filename: str, text: str, keyboard=None):
    """Вспомогательная функция для отправки фото в deposit"""
    # Сначала пытаемся отредактировать существующее сообщение
    try:
        # Если сообщение содержит фото, редактируем caption
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return True
        else:
            # Если сообщение текстовое, редактируем текст
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return True
    except Exception as edit_error:
        # Если редактирование не удалось, отправляем новое сообщение с фото
        logger.warning(f"Не удалось отредактировать сообщение: {edit_error}. Отправляю новое сообщение с фото.")
    
    # Отправляем новое сообщение с фото
    image_path = os.path.join(os.getcwd(), image_filename)
    if os.path.exists(image_path):
        photo_bytes = None
        use_fs_input = False
        
        try:
            # Читаем файл в байты для более надежной отправки
            with open(image_path, 'rb') as f:
                photo_bytes = f.read()
            
            # Проверяем, что файл не пустой
            if len(photo_bytes) == 0:
                logger.warning(f"Файл {image_filename} пустой, пробую использовать FSInputFile")
                use_fs_input = True
        except Exception as e:
            logger.warning(f"Не удалось прочитать файл {image_filename} в байты: {e}. Пробую использовать FSInputFile")
            use_fs_input = True
        
        try:
            # Используем FSInputFile для прямого чтения или BufferedInputFile для байтов
            if use_fs_input:
                photo = FSInputFile(image_path)
            else:
                photo = BufferedInputFile(photo_bytes, filename=image_filename)
            
            await callback.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке фото {image_filename}: {e}")
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            return False
    else:
        logger.warning(f"Файл {image_filename} не найден по пути: {image_path}")
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return False


async def safe_edit_message(callback: CallbackQuery, text: str, keyboard=None):
    """Безопасное редактирование сообщения: проверяет тип и использует правильный метод"""
    try:
        # Если сообщение содержит фото, редактируем caption
        if callback.message.photo:
            logger.info(f"📝 Редактирую caption сообщения с фото для пользователя {callback.from_user.id}")
            await callback.message.edit_caption(
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Caption успешно отредактирован")
        else:
            # Если сообщение текстовое, редактируем текст
            logger.info(f"📝 Редактирую текстовое сообщение для пользователя {callback.from_user.id}")
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Текстовое сообщение успешно отредактировано")
    except Exception as e:
        # Если редактирование не удалось, отправляем новое сообщение
        logger.warning(f"⚠️ Не удалось отредактировать сообщение, отправляю новое: {e}", exc_info=True)
        try:
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            logger.info(f"✅ Новое сообщение успешно отправлено")
        except Exception as e2:
            logger.error(f"❌ Критическая ошибка при отправке нового сообщения: {e2}", exc_info=True)


class DepositStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_tx = State()
    waiting_for_withdraw_amount = State()


# Тестовый обработчик для проверки работы callback_query
@router.callback_query(F.data == "test_callback")
async def test_callback_handler(callback: CallbackQuery):
    """Тестовый обработчик для проверки работы callback_query"""
    logger.info(f"🧪 TEST callback received: {callback.data}")
    await callback.answer("Тест работает!", show_alert=True)


@router.callback_query(F.data == "back_to_deposit")
async def back_to_deposit_menu(callback: CallbackQuery):
    """Вернуться к меню депозита"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    text = f"""💵 <b>Депозит</b>

💰 <b>Баланс:</b> {balance_ton:.4f} TON

<b>Минимальный депозит:</b> $0.1 (0.1 TON)

<b>Выберите способ пополнения:</b>"""
    
    from keyboards import get_deposit_keyboard
    await safe_edit_message(callback, text, get_deposit_keyboard())


@router.callback_query(F.data == "wallet_menu")
async def wallet_menu(callback: CallbackQuery):
    """Вернуться к меню кошелька"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    balance_usd = user.get("balance", 0.0)
    locked_balance_usd = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    
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
    await send_photo_deposit(callback, "кошелек.jpg", text, get_wallet_keyboard())


@router.callback_query(F.data == "wallet_deposit")
async def wallet_deposit(callback: CallbackQuery):
    """Показать меню депозита из кошелька"""
    logger.info(f"🔵 wallet_deposit вызван для пользователя {callback.from_user.id}")
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user = await db.get_user(callback.from_user.id)
    if not user:
        logger.warning(f"⚠️ Пользователь {callback.from_user.id} не найден в БД")
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    text = f"""💵 <b>Депозит</b>

💰 <b>Баланс:</b> {balance_ton:.4f} TON

<b>Минимальный депозит:</b> $0.1 (0.1 TON)

<b>Выберите способ пополнения:</b>"""
    
    from keyboards import get_deposit_keyboard
    await safe_edit_message(callback, text, get_deposit_keyboard())


@router.callback_query(F.data == "wallet_withdraw")
async def wallet_withdraw(callback: CallbackQuery):
    """Показать меню вывода"""
    logger.info(f"🔵 wallet_withdraw вызван для пользователя {callback.from_user.id}")
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user = await db.get_user(callback.from_user.id)
    if not user:
        logger.warning(f"⚠️ Пользователь {callback.from_user.id} не найден в БД")
        return
    
    balance_usd = user.get("balance", 0.0)
    locked_balance_usd = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    locked_balance_ton = usd_to_ton(locked_balance_usd, ton_rate)
    
    # Определяем доступный баланс для вывода (только обычный баланс)
    withdrawable_balance = balance_usd
    withdrawable_balance_ton = balance_ton
    
    text = f"""➖ <b>Вывод средств</b>

💰 <b>Доступно для вывода:</b> {withdrawable_balance_ton:.4f} TON (${withdrawable_balance:.2f})"""
    
    if locked_balance_usd > 0 and rollover_requirement > 0:
        text += f"\n🔒 <b>Заблокировано:</b> {locked_balance_ton:.4f} TON (${locked_balance_usd:.2f})"
        text += f"\n📊 <b>Требуется отыграть:</b> ${rollover_requirement:.2f}"
        text += f"\n\n⚠️ <i>Заблокированные средства можно вывести только после выполнения требования отыгрыша.</i>"
    
    text += f"\n\n<b>Выберите способ вывода:</b>"
    
    from keyboards import get_withdrawal_keyboard
    await safe_edit_message(callback, text, get_withdrawal_keyboard())


@router.callback_query(F.data == "withdraw_gifts")
async def withdraw_gifts_menu(callback: CallbackQuery):
    """Показать меню вывода подарками"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    if balance_usd <= 0:
        await callback.answer("❌ Недостаточно средств на балансе", show_alert=True)
        return
    
    from gifts import GIFTS_CONFIG
    from keyboards import get_gifts_withdrawal_keyboard
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Получаем доступные подарки из БД релеера
    available_relay_gifts = await db.get_all_relay_gifts(include_transferred=False)
    logger.info(f"📊 Найдено доступных подарков в БД релеера: {len(available_relay_gifts)}")
    
    # Создаем словарь доступных подарков из БД (группируем по эмодзи и названию)
    available_gifts_dict = {}
    for relay_gift in available_relay_gifts:
        emoji = relay_gift.get("emoji", "")
        gift_name = relay_gift.get("gift_name", "")
        
        # Ищем подарок в конфиге по эмодзи или названию
        gift_config = None
        for config_emoji, config_info in GIFTS_CONFIG.items():
            # Сравниваем по эмодзи (если есть) или по названию
            if emoji and config_emoji == emoji:
                gift_config = {"emoji": config_emoji, **config_info}
                break
            elif gift_name and config_info.get("name", "").lower() == gift_name.lower():
                gift_config = {"emoji": config_emoji, **config_info}
                break
        
        if gift_config:
            # Используем ключ из конфига (эмодзи) для группировки
            key = config_emoji if config_emoji else gift_name
            if key not in available_gifts_dict:
                available_gifts_dict[key] = gift_config
    
    # Если нет доступных подарков в БД, показываем сообщение
    if not available_gifts_dict:
        text = f"""🎁 <b>Вывод подарками</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON

❌ <b>Нет доступных подарков</b>

В данный момент у релеера нет доступных подарков для вывода.
Попробуйте позже."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="withdraw_gifts")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit")]
        ])
        await safe_edit_message(callback, text, keyboard)
        return
    
    text = f"""🎁 <b>Вывод подарками</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON

📦 <b>Доступно подарков:</b> {len(available_gifts_dict)}

Выберите подарок для вывода:"""
    
    # Показываем первую страницу (page=0) только доступных подарков
    keyboard = get_gifts_withdrawal_keyboard(available_gifts_dict, balance_ton, ton_rate, page=0)
    
    await safe_edit_message(callback, text, keyboard)


@router.callback_query(F.data.startswith("gifts_page_"))
async def gifts_page_handler(callback: CallbackQuery):
    """Обработчик пагинации подарков"""
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    # Парсим номер страницы
    try:
        page = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        page = 0
    
    from gifts import GIFTS_CONFIG
    from keyboards import get_gifts_withdrawal_keyboard
    
    # Получаем доступные подарки из БД релеера (обновляем список)
    available_relay_gifts = await db.get_all_relay_gifts(include_transferred=False)
    
    # Создаем словарь доступных подарков из БД
    available_gifts_dict = {}
    for relay_gift in available_relay_gifts:
        emoji = relay_gift.get("emoji", "")
        gift_name = relay_gift.get("gift_name", "")
        
        # Ищем подарок в конфиге по эмодзи или названию
        gift_config = None
        for config_emoji, config_info in GIFTS_CONFIG.items():
            if emoji and config_emoji == emoji:
                gift_config = {"emoji": config_emoji, **config_info}
                break
            elif gift_name and config_info.get("name", "").lower() == gift_name.lower():
                gift_config = {"emoji": config_emoji, **config_info}
                break
        
        if gift_config:
            key = config_emoji if config_emoji else gift_name
            if key not in available_gifts_dict:
                available_gifts_dict[key] = gift_config
    
    if not available_gifts_dict:
        text = f"""🎁 <b>Вывод подарками</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON

❌ <b>Нет доступных подарков</b>

В данный момент у релеера нет доступных подарков для вывода."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="withdraw_gifts")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit")]
        ])
        await safe_edit_message(callback, text, keyboard)
        return
    
    text = f"""🎁 <b>Вывод подарками</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON

📦 <b>Доступно подарков:</b> {len(available_gifts_dict)}

Выберите подарок для вывода:"""
    
    keyboard = get_gifts_withdrawal_keyboard(available_gifts_dict, balance_ton, ton_rate, page=page)
    
    await safe_edit_message(callback, text, keyboard)


@router.callback_query(F.data.startswith("withdraw_gift_"))
async def withdraw_gift(callback: CallbackQuery):
    """Обработка выбора подарка для вывода"""
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    # Парсим callback_data: withdraw_gift_{name_safe}
    # Формат: withdraw_gift_Plush_Pepe
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка обработки запроса", show_alert=True)
        return
    
    gift_name = parts[2].replace("_", " ") if len(parts) > 2 else ""
    
    from gifts import GIFTS_CONFIG, get_gift_by_name
    
    # Ищем подарок по имени
    gift_info = get_gift_by_name(gift_name)
    
    # Если не нашли, ищем в конфиге напрямую
    if not gift_info:
        for emoji, info in GIFTS_CONFIG.items():
            if info["name"].lower() == gift_name.lower():
                gift_info = {"emoji": emoji, **info}
                break
    
    if not gift_info:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return
    
    # Получаем эмодзи из найденного подарка
    gift_emoji = gift_info.get("emoji", "")
    gift_name_for_search = gift_info.get("name")
    
    # Цена подарка в TON (из конфига)
    # При выводе цена на 10% больше базовой
    gift_price_ton = gift_info["price_ton"] * 1.1
    
    # Конвертируем цену подарка в USD для списания с баланса
    gift_price_usd = ton_to_usd(gift_price_ton, ton_rate)
    
    if balance_usd < gift_price_usd:
        await callback.answer("❌ Недостаточно средств на балансе", show_alert=True)
        return
    
    # Списываем баланс сразу после проверки (до передачи подарка)
    logger.info(f"💰 Начинаю списание баланса для вывода подарка: user_id={callback.from_user.id}, сумма={gift_price_usd:.2f} USD ({gift_price_ton:.4f} TON), подарок={gift_info['name']}")
    await db.update_balance(callback.from_user.id, -gift_price_usd)
    balance_deducted = True  # Флаг, что баланс был списан
    
    # Получаем актуальный баланс после списания
    updated_user = await db.get_user(callback.from_user.id)
    if updated_user:
        actual_balance_usd = updated_user["balance"]
        logger.info(f"✅ Баланс списан. Новый баланс: {actual_balance_usd:.2f} USD (было: {balance_usd:.2f} USD)")
    else:
        logger.error(f"❌ Не удалось получить обновленный баланс пользователя {callback.from_user.id}")
        actual_balance_usd = balance_usd - gift_price_usd
    
    # Проверяем наличие подарка у релаера
    from relay_account import get_relay_client
    from database import Database
    
    relay_client = get_relay_client()
    gift_transferred = False
    saved_gift = None  # Инициализируем для использования дальше в коде
    
    if relay_client:
        try:
            # ПРИОРИТЕТ 1: Ищем подарок в базе данных релаера по названию (приоритет поиска)
            saved_gift = await db.get_available_relay_gift(emoji=gift_emoji, gift_name=gift_name_for_search)
            
            # ПРИОРИТЕТ 2: Если не нашли по точному названию, пробуем найти по частичному совпадению
            if not saved_gift and gift_name_for_search:
                # Пробуем разные варианты названия
                search_variants = [
                    gift_name_for_search,  # Точное название
                    gift_name_for_search.lower(),  # В нижнем регистре
                    gift_name_for_search.upper(),  # В верхнем регистре
                ]
                
                for variant in search_variants:
                    saved_gift = await db.get_available_relay_gift(gift_name=variant)
                    if saved_gift:
                        logger.info(f"✅ Подарок найден по варианту названия: '{variant}'")
                        break
            
            # ПРИОРИТЕТ 3: Если все еще не нашли, ищем по эмодзи (если есть)
            if not saved_gift and gift_emoji:
                saved_gift = await db.get_available_relay_gift(emoji=gift_emoji)
            
            # Если не нашли, логируем для отладки
            if not saved_gift:
                logger.warning(f"⚠️ Подарок {gift_emoji} {gift_name_for_search} не найден в базе данных релаера. Ищем все доступные подарки...")
                # Получаем все доступные подарки для отладки
                all_gifts = await db.get_all_relay_gifts(include_transferred=False)
                logger.info(f"📊 Всего доступных подарков в БД: {len(all_gifts)}")
                for gift in all_gifts[:10]:  # Показываем первые 10 для отладки
                    logger.info(f"  - Эмодзи: {gift.get('emoji', 'N/A')}, Имя: {gift.get('gift_name', 'N/A')}, Slug: {gift.get('slug', 'N/A')}")
            
            if saved_gift:
                # Получаем подарок из Telethon
                from relay_account import get_self_gifts
                gifts = await get_self_gifts(relay_client)
                
                # Ищем нужный подарок по message_id или slug
                telethon_gift = None
                for gift in gifts:
                    if hasattr(gift, 'msg_id') and gift.msg_id == saved_gift.get('message_id'):
                        telethon_gift = gift
                        break
                    elif hasattr(gift.gift, 'slug') and gift.gift.slug == saved_gift.get('slug'):
                        telethon_gift = gift
                        break
                
                if telethon_gift:
                    # Передаем подарок пользователю
                    from relay_account import transfer_gift_to_user
                    gift_transferred = await transfer_gift_to_user(
                        relay_client, 
                        telethon_gift,
                        callback.from_user.id
                    )
                    
                    if gift_transferred:
                        # Отмечаем подарок как переданный
                        await db.mark_gift_as_transferred(saved_gift['message_id'], callback.from_user.id)
                        logger.info(f"✅ Подарок {gift_emoji} {gift_info['name']} передан пользователю {callback.from_user.id}")
                    else:
                        logger.warning(f"⚠️ Не удалось передать подарок пользователю {callback.from_user.id}")
                else:
                    logger.warning(f"⚠️ Подарок {gift_emoji} {gift_info['name']} не найден в Telethon клиенте")
            else:
                logger.warning(f"⚠️ Подарок {gift_emoji} {gift_info['name']} не найден в базе данных релаера")
        except Exception as e:
            logger.error(f"❌ Ошибка при передаче подарка: {e}", exc_info=True)
    else:
        logger.warning("⚠️ Клиент релаера недоступен, пропускаем передачу подарка")
    
    # Обрабатываем результат передачи подарка
    if gift_transferred:
        # Записываем вывод
        await db.add_withdrawal(
            callback.from_user.id,
            gift_price_usd,
            "gift",
            gift_emoji if gift_emoji else None,
            gift_info["name"]
        )
        
        # Получаем актуальный баланс после списания
        final_user = await db.get_user(callback.from_user.id)
        if final_user:
            new_balance_usd = final_user["balance"]
        else:
            new_balance_usd = actual_balance_usd
        new_balance_ton = usd_to_ton(new_balance_usd, ton_rate)
        
        # Финальная проверка: убеждаемся, что баланс действительно списан
        verification_user = await db.get_user(callback.from_user.id)
        if verification_user:
            verified_balance = verification_user["balance"]
            expected_balance = balance_usd - gift_price_usd
            if abs(verified_balance - expected_balance) > 0.01:  # Допускаем небольшую погрешность округления
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Баланс не соответствует ожидаемому! user_id={callback.from_user.id}, ожидалось={expected_balance:.2f} USD, фактически={verified_balance:.2f} USD")
                # Принудительно списываем баланс еще раз
                await db.update_balance(callback.from_user.id, -(verified_balance - expected_balance))
                logger.info(f"🔧 Баланс исправлен принудительным списанием")
            else:
                logger.info(f"✅ Проверка баланса пройдена: user_id={callback.from_user.id}, баланс={verified_balance:.2f} USD (ожидалось {expected_balance:.2f} USD)")
        
        logger.info(f"✅ Вывод подарка завершен: user_id={callback.from_user.id}, подарок={gift_info['name']}, списано={gift_price_usd:.2f} USD, остаток={new_balance_usd:.2f} USD")
        
        # Получаем дополнительную информацию о подарке
        gift_slug = saved_gift.get("slug") if saved_gift else None
        
        # Формируем ссылку на подарок
        gift_link_text = f"{gift_emoji if gift_emoji else ''} {gift_info['name']}"
        if gift_slug:
            gift_link = f"https://t.me/nft/{gift_slug}"
            gift_link_text = f'<a href="{gift_link}">{gift_emoji if gift_emoji else ""} {gift_info["name"]}</a>'
        
        # Формируем сообщение в требуемом формате
        text = f"""✅ Подарок {gift_link_text} успешно выведен

💰 С вашего баланса списано: {gift_price_ton:.4f} TON"""
        
        # ВАЖНО: Убеждаемся, что баланс НЕ возвращается при успешной передаче
        # Сбрасываем флаг, чтобы баланс точно не вернулся
        balance_deducted = False
    else:
        # Если подарок не был передан, возвращаем баланс обратно
        if balance_deducted:
            logger.warning(f"⚠️ Подарок не был передан, возвращаю баланс: user_id={callback.from_user.id}, сумма={gift_price_usd:.2f} USD")
            await db.update_balance(callback.from_user.id, gift_price_usd)
            
            # Проверяем, что баланс вернулся
            restored_user = await db.get_user(callback.from_user.id)
            if restored_user:
                restored_balance = restored_user["balance"]
                logger.info(f"✅ Баланс возвращен. Текущий баланс: {restored_balance:.2f} USD (должно быть ~{balance_usd:.2f} USD)")
            else:
                logger.error(f"❌ Не удалось проверить возврат баланса для пользователя {callback.from_user.id}")
        
        text = f"""❌ <b>Подарок недоступен</b>

🎁 <b>Подарок:</b> {gift_emoji if gift_emoji else ''} {gift_info['name']}

⚠️ К сожалению, этот подарок временно недоступен в профиле релаера.

💰 Баланс не был списан.

Попробуйте выбрать другой подарок или обратитесь в поддержку."""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_withdraw"),
        ]
    ])
    
    await safe_edit_message(callback, text, back_keyboard)
    
    if gift_transferred:
        await callback.answer("✅ Подарок успешно выведен!")
    else:
        await callback.answer("❌ Подарок недоступен", show_alert=True)


@router.callback_query(F.data == "deposit_gifts")
async def deposit_gifts(callback: CallbackQuery):
    """Показать информацию о пополнении подарками"""
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    balance_usd = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    
    from gifts import format_gifts_list
    
    text = f"""🎁 <b>Подарки</b>

Отправляйте подарки на @arbuzrelayer

{format_gifts_list()}

📌 Правила пополнения Подарками - /i"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Создаем клавиатуру с кнопкой "Отправить подарок" и "Назад"
    deposit_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✈️ Отправить подарок", url="https://t.me/arbuzrelayer"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
        ]
    ])
    
    await safe_edit_message(callback, text, deposit_keyboard)


@router.callback_query(F.data.startswith("deposit_") & ~F.data.startswith("deposit_amount_") & ~F.data.startswith("deposit_custom_") & ~(F.data == "deposit_gifts"))
async def handle_deposit_method(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора метода депозита"""
    logger.info(f"🔔 CALLBACK RECEIVED! Data: {callback.data}, User: {callback.from_user.id}")
    try:
        method = callback.data.split("_")[1]
        logger.info(f"✅ Parsed method: {method}")
    except IndexError:
        logger.error(f"❌ Error parsing deposit method from: {callback.data}")
        await callback.answer("Ошибка обработки запроса", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    # Используем user_id как memo
    user_id = callback.from_user.id
    
    # Создаем клавиатуру с кнопкой "Назад" к депозиту
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
        ]
    ])
    
    # Показываем выбор суммы для всех методов кроме crypto (для xRocket сначала спросим валюту)
    if method in ["tonkeeper", "cryptobot"]:
        # Сохраняем метод в состоянии
        await callback.answer()
        
        method_names = {
            "tonkeeper": "💎 Tonkeeper",
            "cryptobot": "🏝️ CryptoBot",
        }
        
        text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Выберите сумму пополнения:</b>"""
        
        # Создаем клавиатуру с кнопками быстрого выбора
        amount_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="$1", callback_data=f"deposit_amount_{method}_1"),
                InlineKeyboardButton(text="$5", callback_data=f"deposit_amount_{method}_5"),
                InlineKeyboardButton(text="$10", callback_data=f"deposit_amount_{method}_10"),
            ],
            [
                InlineKeyboardButton(text="$20", callback_data=f"deposit_amount_{method}_20"),
                InlineKeyboardButton(text="$30", callback_data=f"deposit_amount_{method}_30"),
            ],
            [
                InlineKeyboardButton(text="✏️ Ввести свою сумму", callback_data=f"deposit_custom_{method}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
            ]
        ])
        
        await safe_edit_message(callback, text, amount_keyboard)
        return
    
    if method == "ton":
        # Прямой депозит через TON с автоматическим начислением
        user = await db.get_user(callback.from_user.id)
        balance_usd = user["balance"] if user else 0
        ton_rate = await get_ton_to_usd_rate()
        balance_ton = usd_to_ton(balance_usd, ton_rate)
        
        # Формируем ссылку ton://transfer как на скриншоте
        ton_transfer_link = f"ton://transfer/{TON_ADDRESS}?text={user_id}"
        
        text = f"""💎 <b>TON</b>

💰 <b>Баланс:</b> {balance_ton:.4f} TON

📌 <b>Инструкция:</b>
1. Нажмите кнопку "Перейти" ниже
2. Выберите сумму для отправки
3. <b>ОБЯЗАТЕЛЬНО укажите в комментарии (memo):</b> <code>{user_id}</code>
4. Баланс начислится автоматически в течение 30 секунд

💡 <b>Минимальная сумма:</b> 0.1 TON
💡 <b>Максимальная сумма:</b> {usd_to_ton(MAX_DEPOSIT, ton_rate):.4f} TON (${MAX_DEPOSIT:.2f})

⚠️ <b>ВАЖНО:</b> Без указания вашего ID (<code>{user_id}</code>) в комментарии транзакции баланс НЕ будет начислен автоматически!

<a href="{ton_transfer_link}">🔗 Открыть кошелек</a>"""
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        ton_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Перейти", url=ton_transfer_link),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
            ]
        ])
        
        await safe_edit_message(callback, text, ton_keyboard)
        await callback.answer()
        return
    
    if method == "xrocket":
        # xRocket - только USDC, пропускаем выбор валюты и сразу переходим к выбору суммы
        await state.update_data(xrocket_coin="USDC")
        coin = "USDC"
        
        text = f"""🚀 <b>xRocket</b> <b>(0% комиссии)</b>

Валюта: <b>{coin}</b>

<b>Выберите сумму пополнения:</b>"""
        
        amount_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="$1", callback_data=f"xrocket_amount_{coin}_1"),
                InlineKeyboardButton(text="$5", callback_data=f"xrocket_amount_{coin}_5"),
                InlineKeyboardButton(text="$10", callback_data=f"xrocket_amount_{coin}_10"),
            ],
            [
                InlineKeyboardButton(text="$20", callback_data=f"xrocket_amount_{coin}_20"),
                InlineKeyboardButton(text="$30", callback_data=f"xrocket_amount_{coin}_30"),
            ],
            [
                InlineKeyboardButton(text="✏️ Ввести сумму", callback_data=f"xrocket_custom_{coin}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
            ]
        ])
        await safe_edit_message(callback, text, amount_keyboard)
        await callback.answer()
        return
    
    elif method == "crypto":
        # Показываем выбор криптовалюты
        text = f"""🔗 <b>Крипта</b>

<b>Выберите криптовалюту для пополнения:</b>"""
        
        # Создаем клавиатуру с выбором криптовалюты
        crypto_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💎 TON", callback_data="crypto_coin_TON"),
                InlineKeyboardButton(text="💵 USDT", callback_data="crypto_coin_USDT"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_deposit"),
            ]
        ])
        
        await safe_edit_message(callback, text, crypto_keyboard)
        await callback.answer()
        return
    
    await callback.answer()

@router.callback_query(F.data.startswith("xrocket_coin_"))
async def xrocket_choose_coin(callback: CallbackQuery, state: FSMContext):
    """xRocket: выбор валюты, далее выбор суммы"""
    coin = callback.data.split("_")[2]  # USDT / USDC / TON
    await state.update_data(xrocket_coin=coin)
    text = f"""🚀 <b>xRocket</b> <b>(0% комиссии)</b>

Вы выбрали: <b>{coin}</b>

<b>Выберите сумму пополнения:</b>"""
    amount_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$1", callback_data=f"xrocket_amount_{coin}_1"),
            InlineKeyboardButton(text="$5", callback_data=f"xrocket_amount_{coin}_5"),
            InlineKeyboardButton(text="$10", callback_data=f"xrocket_amount_{coin}_10"),
        ],
        [
            InlineKeyboardButton(text="$20", callback_data=f"xrocket_amount_{coin}_20"),
            InlineKeyboardButton(text="$30", callback_data=f"xrocket_amount_{coin}_30"),
        ],
        [
            InlineKeyboardButton(text="✏️ Ввести сумму", callback_data=f"xrocket_custom_{coin}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="deposit_xrocket"),
        ]
    ])
    await safe_edit_message(callback, text, amount_keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("xrocket_amount_"))
async def xrocket_amount(callback: CallbackQuery, state: FSMContext):
    """xRocket: выбор суммы и выдача ссылки"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    _, _, coin, amount_str = callback.data.split("_", 3)
    amount = float(amount_str)
    
    # Проверка максимального депозита
    if amount > MAX_DEPOSIT:
        await callback.answer(f"❌ Максимальная сумма пополнения: ${MAX_DEPOSIT:.2f}", show_alert=True)
        return
    
    user_id = callback.from_user.id
    # Создаем инвойс через xRocket API для получения inv_* ссылки
    method_link = None
    try:
        inv = await xrocket_create_invoice(coin=coin, amount_usd=amount, memo=str(user_id))
        if inv:
            # Используем pay_url если есть, иначе формируем из inv_token
            if inv.get("pay_url"):
                method_link = inv["pay_url"]
            elif inv.get("inv_token"):
                token = inv['inv_token']
                # Формируем правильную ссылку: https://t.me/xrocket?start=inv_<token>
                # Пример: https://t.me/xrocket?start=inv_xxUTtBleE6jKZxW
                if token.startswith("inv_"):
                    # Токен уже с префиксом inv_, используем как есть
                    method_link = f"https://t.me/xrocket?start={token}"
                elif token.startswith("oinv"):
                    # Токен с префиксом oinv, убираем его и добавляем inv_
                    clean_token = token[4:]  # Убираем "oinv"
                    method_link = f"https://t.me/xrocket?start=inv_{clean_token}"
                else:
                    # Токен без префикса, добавляем inv_
                    method_link = f"https://t.me/xrocket?start=inv_{token}"
    except Exception as e:
        logger.error(f"xRocket invoice create failed: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания инвойса. Попробуйте позже.", show_alert=True)
        return
    
    # Если не удалось создать инвойс, показываем ошибку с подробностями
    if not method_link:
        error_text = """❌ <b>Ошибка создания инвойса xRocket</b>

API xRocket временно недоступен.

<b>Что делать:</b>
• Попробуйте использовать другой метод пополнения
• Используйте 💎 Tonkeeper или 🏝️ CryptoBot
• Или попробуйте позже

Извините за неудобства!"""
        
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад к депозиту", callback_data="back_to_deposit"),
            ],
            [
                InlineKeyboardButton(text="💎 Tonkeeper", callback_data="deposit_tonkeeper"),
                InlineKeyboardButton(text="🏝️ CryptoBot", callback_data="deposit_cryptobot"),
            ]
        ])
        
        await callback.message.answer(error_text, reply_markup=error_keyboard, parse_mode="HTML")
        await callback.answer("❌ API xRocket недоступен", show_alert=True)
        return
    
    text = f"""🚀 <b>xRocket</b> <b>(0% комиссии)</b>

Валюта: <b>{coin}</b>
Сумма: <b>${amount:.2f}</b>

Нажмите кнопку ниже для оплаты:"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплатить", url=method_link),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="deposit_xrocket"),
        ]
    ])
    await safe_edit_message(callback, text, kb)
    await callback.answer()

@router.callback_query(F.data.startswith("xrocket_custom_"))
async def xrocket_custom(callback: CallbackQuery, state: FSMContext):
    """xRocket: пользовательская сумма"""
    coin = callback.data.split("_")[2]
    await state.update_data(deposit_method="xrocket", xrocket_coin=coin)
    await state.set_state(DepositStates.waiting_for_amount)
    text = f"""🚀 <b>xRocket</b> <b>(0% комиссии)</b>

Валюта: <b>{coin}</b>

✏️ <b>Введите сумму пополнения:</b>

Минимальная сумма: $0.10 (0.1 TON)
Максимальная сумма: ${MAX_DEPOSIT:.2f}"""
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="deposit_xrocket"),
        ]
    ])
    await safe_edit_message(callback, text, back_kb)
    await callback.answer()

@router.callback_query(F.data.startswith("crypto_coin_"))
async def handle_crypto_coin(callback: CallbackQuery):
    """Обработка выбора криптовалюты для пополнения"""
    coin = callback.data.split("_")[2]  # TON или USDT
    
    user_id = callback.from_user.id
    
    # TODO: Заменить на реальные адреса когда пользователь их предоставит
    # Пока используем TON_ADDRESS для обеих валют
    coin_address = TON_ADDRESS
    
    coin_names = {
        "TON": "💎 TON",
        "USDT": "💵 USDT"
    }
    
    text = f"""🔗 <b>Крипта</b>

👉 Отправьте монеты на адрес в сети TON:

<code>{coin_address}</code>

⚠️ <b>Memo:</b> {user_id}

✅ Принимаются: {coin_names[coin]}
❌ Не отправляйте любые другие монеты"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="deposit_crypto"),
        ]
    ])
    
    await safe_edit_message(callback, text, back_keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_amount_"))
async def handle_deposit_amount(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора суммы депозита"""
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка обработки запроса")
        return
    
    method = parts[2]
    amount = float(parts[3])
    
    # Проверка максимального депозита
    if amount > MAX_DEPOSIT:
        await callback.answer(f"❌ Максимальная сумма пополнения: ${MAX_DEPOSIT:.2f}", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    # Используем user_id как memo
    user_id = callback.from_user.id
    
    method_names = {
        "tonkeeper": "💎 Tonkeeper",
        "cryptobot": "🏝️ CryptoBot",
        "xrocket": "🚀 xRocket"
    }
    
    # Для Crypto Bot используем инвойсы через Crypto Pay API
    if method == "cryptobot":
        try:
            logger.info(f"🔍 Создание инвойса для пользователя {user_id}, сумма: {amount}")
            # Создаем инвойс через Crypto Pay
            invoice = await crypto_pay.create_invoice(
                asset="USDT",
                amount=str(amount),
                description=f"Пополнение баланса на ${amount:.2f}",
                payload=str(user_id),  # Передаем user_id в payload для идентификации
                expires_in=3600  # Инвойс действителен 1 час
            )
            
            logger.info(f"📋 Результат создания инвойса: {invoice}")
            
            # В Crypto Pay API URL может быть в разных полях
            invoice_url = invoice.get("pay_url") or invoice.get("bot_invoice_url") or invoice.get("invoice_url") if invoice else None
            invoice_id = invoice.get("invoice_id") if invoice else None
            if not invoice_id:
                invoice_id = invoice.get("id") if invoice else None
            
            if invoice and invoice_url:
                logger.info(f"✅ Инвойс создан успешно, URL: {invoice_url}")
                text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f}

Нажмите на кнопку ниже для оплаты:"""
                
                pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="💳 Оплатить", url=invoice_url),
                    ],
                    [
                        InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_invoice_{invoice_id}"),
                    ],
                    [
                        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
                    ]
                ])
                
                await safe_edit_message(callback, text, pay_keyboard)
                await callback.answer()
                return
            else:
                logger.error(f"❌ Ошибка создания инвойса для пользователя {user_id}. Ответ: {invoice}")
                await callback.answer("Ошибка создания счета на оплату. Попробуйте позже.", show_alert=True)
                return
        except Exception as e:
            logger.error(f"❌ Ошибка при создании инвойса: {e}", exc_info=True)
            await callback.answer(f"Ошибка создания счета на оплату: {str(e)}", show_alert=True)
            return
    
    # Для xRocket создаем инвойс через API
    if method == "xrocket":
        try:
            # Для xRocket нужна валюта, по умолчанию USDT
            coin = "USDT"
            inv = await xrocket_create_invoice(coin=coin, amount_usd=amount, memo=str(user_id))
            if inv:
                # Используем pay_url если есть, иначе формируем из inv_token
                if inv.get("pay_url"):
                    method_link = inv["pay_url"]
                elif inv.get("inv_token"):
                    token = inv['inv_token']
                    # Формируем правильную ссылку: https://t.me/xrocket?start=inv_<token>
                    # Пример: https://t.me/xrocket?start=inv_xxUTtBleE6jKZxW
                    if token.startswith("inv_"):
                        method_link = f"https://t.me/xrocket?start={token}"
                    else:
                        # Токен без префикса inv_, добавляем его
                        method_link = f"https://t.me/xrocket?start=inv_{token}"
                else:
                    await callback.answer("❌ Ошибка: не удалось получить ссылку для оплаты. Попробуйте позже.", show_alert=True)
                    return
            else:
                await callback.answer("❌ Ошибка создания инвойса. Попробуйте позже.", show_alert=True)
                return
        except Exception as e:
            logger.error(f"xRocket invoice create failed: {e}", exc_info=True)
            await callback.answer("❌ Ошибка создания инвойса. Попробуйте позже.", show_alert=True)
            return
        
        text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f}

Нажмите на кнопку ниже для оплаты:"""
        
        pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Оплатить", url=method_link),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
            ]
        ])
        
        await safe_edit_message(callback, text, pay_keyboard)
        await callback.answer()
        return
    
    # Для других методов используем прямые ссылки
    method_links = {
        # Формат из скрина: ton://transfer/<address>?text=<memo>
        # Сумму пользователь выставит в Tonkeeper вручную; memo обязателен
        "tonkeeper": f"ton://transfer/{TON_ADDRESS}?text={user_id}",
    }
    
    text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f} (${amount:.0f} $USDT)

⚠️ <b>Memo:</b> {user_id}

Нажмите на кнопку ниже для пополнения:"""
    
    # Создаем клавиатуру со ссылкой
    pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Пополнить", url=method_links[method]),
        ],
        [
            InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"confirm_transfer_{method}_{amount}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
        ]
    ])
    
    await safe_edit_message(callback, text, pay_keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("deposit_custom_"))
async def handle_deposit_custom(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса на ввод своей суммы"""
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка обработки запроса")
        return
    
    method = parts[2]
    
    # Сохраняем метод в состоянии
    await state.update_data(deposit_method=method)
    await state.set_state(DepositStates.waiting_for_amount)
    
    method_names = {
        "tonkeeper": "💎 Tonkeeper",
        "cryptobot": "🏝️ CryptoBot",
        "xrocket": "🚀 xRocket"
    }
    
    text = f"""{method_names[method]} <b>(0% комиссии)</b>

✏️ <b>Введите сумму пополнения:</b>

Минимальная сумма: $0.10 (0.1 TON)
Максимальная сумма: ${MAX_DEPOSIT:.2f}"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
        ]
    ])
    
    await safe_edit_message(callback, text, back_keyboard)
    await callback.answer()


@router.message(DepositStates.waiting_for_amount, F.text)
async def handle_custom_amount(message: Message, state: FSMContext):
    """Обработка введенной суммы"""
    try:
        amount = float(message.text.replace(",", "."))
        
        if amount < 0.1:
            await message.answer("❌ Минимальная сумма пополнения: $0.10 (0.1 TON)")
            return
        
        if amount > MAX_DEPOSIT:
            await message.answer(f"❌ Максимальная сумма пополнения: ${MAX_DEPOSIT:.2f}")
            return
        
        data = await state.get_data()
        method = data.get("deposit_method")
        
        if not method:
            await state.clear()
            await message.answer("❌ Ошибка: метод пополнения не найден")
            return
        
        # Используем user_id как memo
        user_id = message.from_user.id
        
        method_names = {
            "tonkeeper": "💎 Tonkeeper",
            "cryptobot": "🏝️ CryptoBot",
            "xrocket": "🚀 xRocket"
        }
        
        # Для Crypto Bot используем инвойсы через Crypto Pay API
        if method == "cryptobot":
            try:
                logger.info(f"🔍 Создание инвойса для пользователя {user_id}, сумма: {amount}")
                # Создаем инвойс через Crypto Pay
                invoice = await crypto_pay.create_invoice(
                    asset="USDT",
                    amount=str(amount),
                    description=f"Пополнение баланса на ${amount:.2f}",
                    payload=str(user_id),  # Передаем user_id в payload для идентификации
                    expires_in=3600  # Инвойс действителен 1 час
                )
                
                logger.info(f"📋 Результат создания инвойса: {invoice}")
                
                # В Crypto Pay API URL может быть в разных полях
                invoice_url = invoice.get("pay_url") or invoice.get("bot_invoice_url") or invoice.get("invoice_url") if invoice else None
                invoice_id = invoice.get("invoice_id") if invoice else None
                if not invoice_id:
                    invoice_id = invoice.get("id") if invoice else None
                
                if invoice and invoice_url:
                    logger.info(f"✅ Инвойс создан успешно, URL: {invoice_url}")
                    text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f}

Нажмите на кнопку ниже для оплаты:"""
                    
                    pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="💳 Оплатить", url=invoice_url),
                        ],
                        [
                            InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_invoice_{invoice_id}"),
                        ],
                        [
                            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
                        ]
                    ])
                    
                    await message.answer(text, reply_markup=pay_keyboard, parse_mode="HTML")
                    await state.clear()
                    return
                else:
                    logger.error(f"❌ Ошибка создания инвойса для пользователя {user_id}. Ответ: {invoice}")
                    await message.answer("❌ Ошибка создания счета на оплату. Попробуйте позже.")
                    await state.clear()
                    return
            except Exception as e:
                logger.error(f"❌ Ошибка при создании инвойса: {e}", exc_info=True)
                await message.answer(f"❌ Ошибка создания счета на оплату: {str(e)}")
                await state.clear()
                return
        
        # Для xRocket создаем инвойс через API
        if method == "xrocket":
            try:
                coin = data.get("xrocket_coin", "USDT")
                inv = await xrocket_create_invoice(coin=coin, amount_usd=amount, memo=str(user_id))
                if inv:
                    # Используем pay_url если есть, иначе формируем из inv_token
                    if inv.get("pay_url"):
                        method_link = inv["pay_url"]
                    elif inv.get("inv_token"):
                        token = inv['inv_token']
                        # Формируем правильную ссылку: https://t.me/xrocket?start=inv_<token>
                        # Пример: https://t.me/xrocket?start=inv_xxUTtBleE6jKZxW
                        if token.startswith("inv_"):
                            method_link = f"https://t.me/xrocket?start={token}"
                        else:
                            # Токен без префикса inv_, добавляем его
                            method_link = f"https://t.me/xrocket?start=inv_{token}"
                    else:
                        await message.answer("❌ Ошибка: не удалось получить ссылку для оплаты. Попробуйте позже.")
                        await state.clear()
                        return
                else:
                    await message.answer("❌ Ошибка создания инвойса. Попробуйте позже.")
                    await state.clear()
                    return
            except Exception as e:
                logger.error(f"xRocket invoice create failed (custom amount): {e}", exc_info=True)
                await message.answer("❌ Ошибка создания инвойса. Попробуйте позже.")
                await state.clear()
                return
            
            text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f}

Нажмите на кнопку ниже для оплаты:"""
            
            pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💳 Оплатить", url=method_link),
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
                ]
            ])
            
            await message.answer(text, reply_markup=pay_keyboard, parse_mode="HTML")
            await state.clear()
            return
        
        # Для других методов используем прямые ссылки
        method_links = {
            "tonkeeper": f"ton://transfer/{TON_ADDRESS}?text={user_id}",
        }
        
        text = f"""{method_names[method]} <b>(0% комиссии)</b>

<b>Сумма пополнения:</b> ${amount:.2f} (${amount:.0f} $USDT)

⚠️ <b>ВАЖНО - Memo (комментарий):</b> <code>{user_id}</code>

📌 <b>Инструкция:</b>
1. Нажмите кнопку "Пополнить" ниже
2. <b>ОБЯЗАТЕЛЬНО укажите в комментарии (memo):</b> <code>{user_id}</code>
3. Баланс начислится автоматически в течение 30 секунд

⚠️ <b>Без указания вашего ID в комментарии транзакции баланс НЕ будет начислен автоматически!</b>

Нажмите на кнопку ниже для пополнения:"""
        
        # Создаем клавиатуру со ссылкой
        pay_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 Пополнить", url=method_links[method]),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"deposit_{method}"),
            ]
        ])
        
        await message.answer(text, reply_markup=pay_keyboard, parse_mode="HTML")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (например: 10.5 или 10)")


@router.callback_query(F.data == "withdraw_custom")
async def handle_withdraw_custom(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса на ввод своей суммы для вывода"""
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    balance = user["balance"]
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance, ton_rate)
    
    await state.set_state(DepositStates.waiting_for_withdraw_amount)
    
    text = f"""➖ <b>Вывод средств</b>

💰 <b>Ваш баланс:</b> {balance_ton:.4f} TON (${balance:.2f})

✏️ <b>Введите сумму для вывода:</b>

Минимальная сумма: $0.10"""
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_withdraw"),
        ]
    ])
    
    await safe_edit_message(callback, text, back_keyboard)


@router.message(DepositStates.waiting_for_withdraw_amount, F.text)
async def handle_custom_withdraw_amount(message: Message, state: FSMContext):
    """Обработка введенной суммы для вывода"""
    try:
        amount = float(message.text.replace(",", "."))
        
        if amount < 0.1:
            await message.answer("❌ Минимальная сумма вывода: $0.10")
            await state.clear()
            return
        
        user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            await state.clear()
            return
        
        # Получаем данные пользователя для проверки отыгрыша
        balance = user.get("balance", 0.0)
        locked_balance = user.get("locked_balance", 0.0)
        rollover_requirement = user.get("rollover_requirement", 0.0)
        
        # Проверяем, есть ли заблокированные средства с отыгрышем
        if locked_balance > 0 and rollover_requirement > 0:
            # Есть заблокированные средства с невыполненным отыгрышем
            # Если сумма вывода меньше заблокированной суммы, разрешаем вывод
            if amount <= locked_balance:
                # Разрешаем вывод из заблокированных средств
                pass  # Продолжаем обработку
            elif amount > locked_balance:
                # Если сумма вывода больше заблокированной, проверяем обычный баланс
                # Можно вывести только обычный баланс (не заблокированные средства!)
                if balance < (amount - locked_balance):
                    await message.answer(
                        f"❌ <b>Недостаточно средств для вывода</b>\n\n"
                        f"💰 Доступно для вывода: ${balance:.2f}\n"
                        f"🔒 Заблокировано (с отыгрышем): ${locked_balance:.2f}\n"
                        f"📊 Требуется отыграть: ${rollover_requirement:.2f}\n\n"
                        f"⚠️ <b>Внимание!</b> У вас есть средства, полученные с отыгрышем.\n"
                        f"Эти средства можно использовать для игр, но вывести их можно будет только после выполнения требования отыгрыша.\n\n"
                        f"Вы можете вывести только обычный баланс: <b>${balance:.2f}</b>",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return
                # Дополнительная проверка: сумма вывода не должна превышать обычный баланс + заблокированную сумму
                if amount > (balance + locked_balance):
                    await message.answer(
                        f"❌ <b>Недостаточно средств для вывода</b>\n\n"
                        f"💰 Доступно для вывода: ${balance:.2f}\n"
                        f"🔒 Заблокировано (с отыгрышем): ${locked_balance:.2f}\n"
                        f"📊 Требуется отыграть: ${rollover_requirement:.2f}\n\n"
                        f"⚠️ <b>Внимание!</b> Вы пытаетесь вывести сумму, которая превышает доступные средства.\n"
                        f"Максимальная сумма для вывода: <b>${balance + locked_balance:.2f}</b>",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return
        else:
            # Нет заблокированных средств или отыгрыш выполнен - проверяем общий доступный баланс
            withdrawable_balance = await db.get_withdrawable_balance(message.from_user.id)
            if withdrawable_balance < amount:
                await message.answer(f"❌ Недостаточно средств на балансе. Доступно: ${withdrawable_balance:.2f}")
                await state.clear()
                return
        
        commission = amount * 0.002  # 0.20% комиссия
        final_amount = amount - commission
        
        # Проверяем баланс Crypto Pay перед созданием чека
        try:
            balance_info = await crypto_pay.get_balance()
            if balance_info:
                # Ищем баланс USDT (API возвращает currency_code, а не asset_code)
                usdt_balance = None
                for asset_balance in balance_info:
                    currency_code = asset_balance.get("currency_code") or asset_balance.get("asset_code")
                    if currency_code == "USDT":
                        usdt_balance = float(asset_balance.get("available", 0))
                        break
                
                if usdt_balance is not None and usdt_balance < final_amount:
                    logger.warning(f"⚠️ Недостаточно средств на балансе Crypto Pay: {usdt_balance:.4f} USDT, требуется: {final_amount:.4f} USDT")
                    await message.answer(
                        "❌ Произошла ошибка при выводе, обратитесь в поддержку!",
                        parse_mode="HTML"
                    )
                    await state.clear()
                    return
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке баланса Crypto Pay: {e}")
            # Продолжаем создание чека, если проверка не удалась
        
        # Создаем чек через Crypto Pay API
        try:
            check = await crypto_pay.create_check(
                asset="USDT",
                amount=str(final_amount),
                pin_to_user_id=message.from_user.id
            )
            
            # Проверяем, есть ли ошибка в ответе
            if check and check.get("error"):
                error_name = check.get("name", "unknown")
                error_description = check.get("description", "")
                
                if error_name == "METHOD_DISABLED":
                    await message.answer(
                        "❌ <b>Создание чеков временно недоступно</b>\n\n"
                        "Метод создания чеков отключен в настройках Crypto Pay.\n"
                        "Обратитесь к администратору для включения этой функции.",
                        parse_mode="HTML"
                    )
                elif error_name == "NOT_ENOUGH_COINS":
                    await message.answer(
                        "❌ Произошла ошибка при выводе, обратитесь в поддержку!",
                        parse_mode="HTML"
                    )
                else:
                    await message.answer(
                        f"❌ <b>Ошибка создания чека</b>\n\n"
                        f"Причина: {error_description or error_name or 'Неизвестная ошибка'}\n\n"
                        f"Попробуйте позже или обратитесь в поддержку.",
                        parse_mode="HTML"
                    )
                await state.clear()
                return
            
            # API возвращает bot_check_url, а не check_url
            check_url = check.get("bot_check_url") or check.get("check_url")
            if check and check_url:
                # Списываем баланс с учетом отыгрыша
                if locked_balance > 0 and rollover_requirement > 0:
                    # Есть заблокированные средства с невыполненным отыгрышем
                    if amount <= locked_balance:
                        # Если сумма вывода меньше или равна заблокированной сумме, списываем из заблокированного баланса
                        await db.decrease_locked_balance(message.from_user.id, amount)
                    else:
                        # Если сумма вывода больше заблокированной суммы, списываем сначала заблокированный, потом обычный
                        await db.decrease_locked_balance(message.from_user.id, locked_balance)
                        remaining = amount - locked_balance
                        await db.update_balance(message.from_user.id, -remaining)
                else:
                    # Нет заблокированных средств или отыгрыш выполнен - списываем как обычно
                    if balance >= amount:
                        # Если достаточно обычного баланса, списываем только его
                        await db.update_balance(message.from_user.id, -amount)
                    else:
                        # Если недостаточно обычного баланса, списываем весь обычный и часть заблокированного
                        remaining = amount - balance
                        await db.update_balance(message.from_user.id, -balance)
                        # Уменьшаем заблокированный баланс
                        await db.decrease_locked_balance(message.from_user.id, remaining)
                
                # Записываем вывод
                await db.add_withdrawal(message.from_user.id, amount, "crypto_pay")
                
                text = f"""✅ <b>Чек на вывод создан</b>

💰 Сумма: ${amount:.2f}
💸 Комиссия (0.20%): ${commission:.2f}
💵 К получению: ${final_amount:.2f}

Нажмите на кнопку ниже, чтобы получить средства:"""
                
                check_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="💳 Получить средства", url=check_url),
                    ],
                    [
                        InlineKeyboardButton(text="⬅️ К кошельку", callback_data="wallet_menu"),
                    ]
                ])
                
                await message.answer(text, reply_markup=check_keyboard, parse_mode="HTML")
                await state.clear()
            else:
                # Если check None или не содержит bot_check_url, но и не содержит error
                logger.error(f"❌ Ошибка создания чека для пользователя {message.from_user.id}, ответ: {check}")
                if check:
                    error_description = check.get("description", "Неизвестная ошибка")
                    await message.answer(
                        f"❌ <b>Ошибка создания чека</b>\n\n"
                        f"Причина: {error_description}\n\n"
                        f"Попробуйте позже или обратитесь в поддержку.",
                        parse_mode="HTML"
                    )
                else:
                    await message.answer("❌ Ошибка создания чека на вывод. Попробуйте позже.")
                await state.clear()
        except Exception as e:
            logger.error(f"❌ Ошибка при создании чека: {e}", exc_info=True)
            await message.answer("❌ Ошибка создания чека на вывод. Попробуйте позже.")
            await state.clear()
            
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (например: 10.5 или 10)")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке суммы вывода: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("withdraw_"))
async def handle_withdrawal(callback: CallbackQuery):
    """Обработка вывода средств"""
    # Исключаем обработку вывода реферального баланса (он обрабатывается в referral.py)
    if callback.data == "withdraw_referral_balance":
        return
    
    # Исключаем обработку кастомного вывода (он обрабатывается отдельно)
    if callback.data == "withdraw_custom":
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return
    
    # Получаем данные пользователя для проверки отыгрыша
    balance = user.get("balance", 0.0)
    locked_balance = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    
    if callback.data == "withdraw_max":
        # Для "Max" определяем доступный баланс
        if locked_balance > 0 and rollover_requirement > 0:
            # Есть заблокированные средства - можно вывести заблокированные + обычный баланс
            withdrawable_balance = balance + locked_balance
        else:
            # Нет заблокированных средств или отыгрыш выполнен
            withdrawable_balance = await db.get_withdrawable_balance(callback.from_user.id)
        amount = withdrawable_balance
    else:
        amount = float(callback.data.split("_")[1])
    
    # Проверяем доступный баланс
    if locked_balance > 0 and rollover_requirement > 0:
        # Есть заблокированные средства с невыполненным отыгрышем
        # Если сумма вывода меньше заблокированной суммы, разрешаем вывод
        if amount <= locked_balance:
            # Разрешаем вывод из заблокированных средств
            pass  # Продолжаем обработку
        elif amount > locked_balance:
            # Если сумма вывода больше заблокированной, проверяем общий баланс
            total_available = balance + locked_balance
            if amount > total_available:
                await callback.answer(
                    f"❌ Недостаточно средств для вывода\n\n"
                    f"💰 Доступно для вывода: ${balance:.2f}\n"
                    f"🔒 Заблокировано (с отыгрышем): ${locked_balance:.2f}\n"
                    f"📊 Требуется отыграть: ${rollover_requirement:.2f}\n\n"
                    f"⚠️ Вы пытаетесь вывести сумму, которая превышает доступные средства.\n"
                    f"Максимальная сумма для вывода: ${total_available:.2f}",
                    show_alert=True
                )
                return
            # Проверяем, что обычного баланса достаточно для части, превышающей заблокированную сумму
            if balance < (amount - locked_balance):
                await callback.answer(
                    f"❌ Недостаточно средств для вывода\n\n"
                    f"💰 Доступно для вывода: ${balance:.2f}\n"
                    f"🔒 Заблокировано (с отыгрышем): ${locked_balance:.2f}\n"
                    f"📊 Требуется отыграть: ${rollover_requirement:.2f}\n\n"
                    f"⚠️ Внимание! У вас есть средства, полученные с отыгрышем.\n"
                    f"Вы можете вывести только обычный баланс: ${balance:.2f}",
                    show_alert=True
                )
                return
    else:
        # Нет заблокированных средств или отыгрыш выполнен - проверяем общий доступный баланс
        withdrawable_balance = await db.get_withdrawable_balance(callback.from_user.id)
        if withdrawable_balance < amount:
            await callback.answer("Недостаточно средств на балансе", show_alert=True)
            return
    
    commission = amount * 0.002  # 0.20% комиссия
    final_amount = amount - commission
    
    # Проверяем баланс Crypto Pay перед созданием чека
    try:
        balance_info = await crypto_pay.get_balance()
        if balance_info:
            # Ищем баланс USDT (API возвращает currency_code, а не asset_code)
            usdt_balance = None
            for asset_balance in balance_info:
                currency_code = asset_balance.get("currency_code") or asset_balance.get("asset_code")
                if currency_code == "USDT":
                    usdt_balance = float(asset_balance.get("available", 0))
                    break
            
            if usdt_balance is not None and usdt_balance < final_amount:
                logger.warning(f"⚠️ Недостаточно средств на балансе Crypto Pay: {usdt_balance:.4f} USDT, требуется: {final_amount:.4f} USDT")
                await callback.answer(
                    "❌ Произошла ошибка при выводе, обратитесь в поддержку!",
                    show_alert=True
                )
                return
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке баланса Crypto Pay: {e}")
        # Продолжаем создание чека, если проверка не удалась
    
    # Создаем чек через Crypto Pay API
    try:
        check = await crypto_pay.create_check(
            asset="USDT",
            amount=str(final_amount),
            pin_to_user_id=callback.from_user.id
        )
        
        # Проверяем, есть ли ошибка в ответе
        if check and check.get("error"):
            error_name = check.get("name", "unknown")
            error_description = check.get("description", "")
            
            if error_name == "METHOD_DISABLED":
                await callback.answer(
                    "❌ Создание чеков временно недоступно\n\n"
                    "Метод создания чеков отключен в настройках Crypto Pay.\n"
                    "Обратитесь к администратору для включения этой функции.",
                    show_alert=True
                )
            elif error_name == "NOT_ENOUGH_COINS":
                await callback.answer(
                    "❌ Произошла ошибка при выводе, обратитесь в поддержку!",
                    show_alert=True
                )
            else:
                await callback.answer(
                    f"❌ Ошибка создания чека\n\n"
                    f"Причина: {error_description or 'Неизвестная ошибка'}\n\n"
                    f"Попробуйте позже или обратитесь в поддержку.",
                    show_alert=True
                )
            return
        
        # API возвращает bot_check_url, а не check_url
        check_url = check.get("bot_check_url") or check.get("check_url") if check else None
        if check and check_url:
            # Списываем баланс с учетом отыгрыша
            if locked_balance > 0 and rollover_requirement > 0:
                # Есть заблокированные средства с невыполненным отыгрышем
                if amount <= locked_balance:
                    # Если сумма вывода меньше или равна заблокированной сумме, списываем из заблокированного баланса
                    await db.decrease_locked_balance(callback.from_user.id, amount)
                else:
                    # Если сумма вывода больше заблокированной суммы, списываем сначала заблокированный, потом обычный
                    await db.decrease_locked_balance(callback.from_user.id, locked_balance)
                    remaining = amount - locked_balance
                    await db.update_balance(callback.from_user.id, -remaining)
            else:
                # Нет заблокированных средств или отыгрыш выполнен - списываем как обычно
                current_user = await db.get_user(callback.from_user.id)
                current_balance = current_user.get("balance", 0.0)
                current_locked = current_user.get("locked_balance", 0.0)
                
                if current_balance >= amount:
                    # Если достаточно обычного баланса, списываем только его
                    await db.update_balance(callback.from_user.id, -amount)
                else:
                    # Если недостаточно обычного баланса, списываем весь обычный и часть заблокированного
                    remaining = amount - current_balance
                    await db.update_balance(callback.from_user.id, -current_balance)
                    # Уменьшаем заблокированный баланс
                    await db.decrease_locked_balance(callback.from_user.id, remaining)
            
            # Записываем вывод
            await db.add_withdrawal(callback.from_user.id, amount, "crypto_pay")
            
            text = f"""✅ <b>Чек на вывод создан</b>

💰 Сумма: ${amount:.2f}
💸 Комиссия (0.20%): ${commission:.2f}
💵 К получению: ${final_amount:.2f}

Нажмите на кнопку ниже, чтобы получить средства:"""
            
            check_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="💳 Получить средства", url=check_url),
                ]
            ])
            
            await callback.message.answer(text, reply_markup=check_keyboard, parse_mode="HTML")
            await callback.answer()
        else:
            # Если check None или не содержит bot_check_url, но и не содержит error
            logger.error(f"❌ Ошибка создания чека для пользователя {callback.from_user.id}, ответ: {check}")
            if check:
                error_description = check.get("description", "Неизвестная ошибка")
                await callback.answer(
                    f"❌ Ошибка создания чека\n\n"
                    f"Причина: {error_description}\n\n"
                    f"Попробуйте позже или обратитесь в поддержку.",
                    show_alert=True
                )
            else:
                await callback.answer("Ошибка создания чека на вывод", show_alert=True)
    except Exception as e:
        logger.error(f"❌ Ошибка при создании чека: {e}", exc_info=True)
        await callback.answer("Ошибка создания чека на вывод", show_alert=True)

@router.callback_query(F.data.startswith("confirm_transfer_"))
async def confirm_transfer(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал 'Я оплатил' для Tonkeeper/xRocket — просим ссылку на транзакцию"""
    try:
        _, _, method, amount_str = callback.data.split("_", 3)
        amount = float(amount_str)
    except Exception:
        await callback.answer("Ошибка обработки данных", show_alert=True)
        return
    await state.update_data(confirm_method=method, confirm_amount=amount)
    await state.set_state(DepositStates.waiting_for_tx)
    await callback.message.answer(
        "🔗 Отправьте ссылку на транзакцию (например, tonviewer.com) или хэш. "
        "Мы отметим платеж как ожидающий подтверждения и зачислим после проверки.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(DepositStates.waiting_for_tx, F.text)
async def handle_tx_link(message: Message, state: FSMContext):
    """Получаем ссылку/хэш транзакции, ставим депозит в pending"""
    data = await state.get_data()
    method = data.get("confirm_method", "unknown")
    amount = float(data.get("confirm_amount", 0.0))
    if amount <= 0:
        await state.clear()
        await message.answer("❌ Сумма не определена. Попробуйте заново выбрать способ пополнения.")
        return
    user_id = message.from_user.id

    # Пытаемся сразу авто-проверить через TON chain (tonkeeper/xrocket переводятся на один адрес с memo=user_id)
    credited = False
    try:
        if method in ["tonkeeper", "xrocket"]:
            # Ищем входящую транзакцию с комментарием=user_id и суммой >= ожидаемой (в наноTON)
            min_amount_nano = int(amount * 1e9 * 0.98)  # допускаем 2% расхождение
            found = await find_incoming_tx_by_comment(TON_ADDRESS, str(user_id), min_amount_nano)
            if found:
                tx_hash, amount_nano = found
                # Защита от дублей
                if await db.is_chain_payment_new(tx_hash):
                    # В USD считаем по курсу
                    ton_rate = await get_ton_to_usd_rate()
                    amount_ton = amount_nano / 1e9
                    amount_usd = ton_to_usd(amount_ton, ton_rate)
                    await db.update_balance(user_id, amount_usd)
                    await db.add_deposit(user_id, amount_usd, method)
                    await db.save_chain_payment(tx_hash, user_id, amount_usd)
                    new_balance_usd = await db.get_balance(user_id)
                    new_balance_ton = usd_to_ton(new_balance_usd, ton_rate)
                    await message.answer(
                        f"✅ <b>Платеж подтвержден в сети TON</b>\n\n"
                        f"Метод: {method}\n"
                        f"Сумма: {amount_ton:.4f} TON\n"
                        f"Хеш: <code>{tx_hash}</code>\n\n"
                        f"Новый баланс: {new_balance_ton:.4f} TON",
                        parse_mode="HTML"
                    )
                    credited = True
    except Exception as e:
        logger.error(f"Ошибка авто-проверки TON: {e}", exc_info=True)

    if not credited:
        # Сохраняем pending депозит (на ручную/отложенную проверку)
        try:
            await db.add_deposit_with_status(user_id, amount, method, status="pending")
        except Exception as e:
            logger.error(f"Не удалось записать pending депозит: {e}", exc_info=True)
        await message.answer(
            "🕒 <b>Платеж на проверке</b>\n\n"
            "Мы получили вашу заявку и ссылку/хэш. "
            "Зачисление произойдет после подтверждения. Спасибо!",
            parse_mode="HTML"
        )
    await state.clear()


@router.callback_query(F.data.startswith("check_invoice_"))
async def check_invoice_status(callback: CallbackQuery):
    """Проверить статус инвойса CryptoBot (Crypto Pay) и зачислить средства"""
    try:
        parts = callback.data.split("_")
        invoice_id = parts[2] if len(parts) > 2 else None
        if not invoice_id:
            await callback.answer("Некорректный инвойс", show_alert=True)
            return
        
        # Запрашиваем инвойс
        result = await crypto_pay.get_invoices(invoice_ids=str(invoice_id))
        if not result:
            await callback.answer("Информация о платеже недоступна. Попробуйте позже.", show_alert=True)
            return
        
        invoices = result.get("items") or result.get("invoices") or []
        if not invoices:
            await callback.answer("Инвойс не найден", show_alert=True)
            return
        
        invoice = invoices[0]
        status = invoice.get("status")
        is_paid = invoice.get("paid") or (status == "paid")
        if not is_paid:
            await callback.answer("Платеж пока не оплачен. Попробуйте позже.", show_alert=True)
            return
        
        # Определяем сумму и зачисляем
        amount_str = str(invoice.get("amount", "0"))
        asset = invoice.get("asset", "USDT")
        try:
            amount = float(amount_str)
        except Exception:
            amount = 0.0
        
        if amount <= 0:
            await callback.answer("Не удалось определить сумму платежа", show_alert=True)
            return
        
        # В USDT считаем 1:1 к USD
        credited_usd = amount if asset.upper() == "USDT" else amount
        
        # Убедимся, что пользователь существует
        user = await db.get_user(callback.from_user.id)
        if not user:
            username = callback.from_user.username or f"user_{callback.from_user.id}"
            await db.create_user(callback.from_user.id, username)
        
        # Проверка: не зачисляли ли уже этот инвойс?
        # У нас нет таблицы инвойсов, поэтому простой вариант – на стороне Crypto Pay
        # предполагается, что один и тот же invoice_id не будет проверен дважды после оплаты.
        
        await db.update_balance(callback.from_user.id, credited_usd)
        await db.add_deposit(callback.from_user.id, credited_usd, "cryptobot")
        
        # Сообщение об успехе
        ton_rate = await get_ton_to_usd_rate()
        new_balance_usd = await db.get_balance(callback.from_user.id)
        new_balance_ton = usd_to_ton(new_balance_usd, ton_rate)
        
        text = f"""✅ <b>Платеж получен</b>

💳 Метод: CryptoBot
💵 Сумма: ${credited_usd:.2f}
💰 Новый баланс: {new_balance_ton:.4f} TON"""
        
        back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ К депозиту", callback_data="back_to_deposit"),
            ],
            [
                InlineKeyboardButton(text="💼 Кошелек", callback_data="wallet_menu"),
            ]
        ])
        
        # Меняем текст, если есть сообщение, иначе отправляем новое
        await safe_edit_message(callback, text, back_keyboard)
        
        await callback.answer("Платеж зачислен ✅")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки инвойса: {e}", exc_info=True)
        await callback.answer("Ошибка при проверке платежа", show_alert=True)

# Универсальный обработчик для отладки - должен быть ПОСЛЕДНИМ в роутере
# Ловит все необработанные callback_query в этом роутере
# Временно отключен, чтобы не мешать работе других обработчиков
# @router.callback_query()
# async def debug_all_callbacks(callback: CallbackQuery):
#     """Отладочный обработчик - логирует все необработанные callback_query"""
#     logger.warning(f"⚠️ DEBUG: Необработанный callback_query в deposit_router: {callback.data} от пользователя {callback.from_user.id}")
#     await callback.answer(f"Обработчик не найден для: {callback.data}", show_alert=True)

