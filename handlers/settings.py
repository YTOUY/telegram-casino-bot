import asyncio
import os

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from utils.checks import (
    decode_slot_symbols,
    format_user_text,
    build_check_keyboard,
    build_share_text,
    build_check_link,
    generate_check_code,
    build_captcha_keyboard,
    build_captcha_text,
    notify_check_owner,
)

router = Router()
db = Database()
import logging
logger = logging.getLogger(__name__)


async def edit_settings_message(callback: CallbackQuery, text: str, keyboard=None):
    """Редактирует сообщение с настройками (поддерживает фото и текст)"""
    try:
        # Проверяем, есть ли фото в сообщении
        if callback.message.photo:
            # Если есть фото, редактируем caption
            await callback.message.edit_caption(
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Если нет фото, редактируем текст
            await callback.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        return True
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения настроек: {e}")
        # Если не удалось отредактировать (например, текст не изменился), просто возвращаем успех
        return True


class CheckStates(StatesGroup):
    waiting_activations = State()
    waiting_amount = State()
    waiting_captcha_choice = State()
    waiting_deposit_type = State()
    waiting_rollover = State()
    waiting_min_deposit = State()
    waiting_image = State()
    waiting_text = State()
    waiting_button_text = State()


class SupportStates(StatesGroup):
    waiting_message = State()


@router.callback_query(F.data == "setting_create_check")
async def start_create_check(callback: CallbackQuery, state: FSMContext):
    """Начать создание чека"""
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    balance = user["balance"]
    
    if balance < 0.1:
        await callback.answer("❌ Недостаточно средств на балансе", show_alert=True)
        return
    
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    await callback.message.answer(
        f"🎫 <b>Создание чека</b>\n\n"
        f"💰 Ваш баланс: ${balance:.2f}\n\n"
        f"Введите количество активаций (сколько раз можно активировать чек):",
        parse_mode="HTML"
    )
    await state.set_state(CheckStates.waiting_activations)


@router.callback_query(F.data.startswith("setting_") & ~(F.data == "setting_create_check"))
async def handle_setting_toggle(callback: CallbackQuery, state: FSMContext):
    """Обработка изменения настроек"""
    setting_type = callback.data.split("_")[1]
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    if setting_type == "ref" and callback.data.endswith("notif"):
        await callback.answer()  # Моментальный ответ
        # Переключаем уведомления о рефералах
        new_value = not user["referral_notifications"]
        await db.update_setting(callback.from_user.id, "referral_notifications", new_value)
        status = "включены" if new_value else "выключены"
        
        # Обновляем сообщение
        user = await db.get_user(callback.from_user.id)
        ref_notif = "Вкл" if user["referral_notifications"] else "Выкл"
        base_bet = user["base_bet"]
        
        text = f"""⚙️ <b>Настройки</b>

📌 Реф. увед — получайте уведомления о каждом новом реферале
📌 Базовая ставка — ставка, установленная по умолчанию для всех игр

<b>Текущие настройки:</b>
🔔 Реф. увед.: {ref_notif}
💰 Базовая ставка: ${base_bet:.2f}"""
        
        from keyboards import get_settings_keyboard
        await edit_settings_message(callback, text, get_settings_keyboard())
        
    elif setting_type == "base" and callback.data.endswith("bet"):
        await callback.answer()  # Моментальный ответ
        # Изменение базовой ставки через FSM
        await callback.message.answer("💰 Введите новую базовую ставку (например: 3 или 3$):")
        # Используем состояние для ожидания ввода
        # Состояние будет обработано в отдельном обработчике
    elif setting_type == "support":
        await callback.answer()
        # Показываем поддержку и просим отправить сообщение
        import os
        text = """💬 <b>Поддержка</b>

Если у вас возникли вопросы или проблемы, напишите ваше сообщение, и администратор ответит вам в ближайшее время."""
        
        try:
            image_path = os.path.join(os.getcwd(), "поддержка.jpg")
            if os.path.exists(image_path):
                # Читаем файл в байты для более надежной отправки
                with open(image_path, 'rb') as f:
                    photo_bytes = f.read()
                
                # Проверяем, что файл не пустой
                if len(photo_bytes) > 0:
                    # Используем BufferedInputFile для более надежной отправки
                    photo = BufferedInputFile(photo_bytes, filename="поддержка.jpg")
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=text,
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.answer(text, parse_mode="HTML")
            else:
                await callback.message.answer(text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото поддержки: {e}")
            await callback.message.answer(text, parse_mode="HTML")
        
        # Просим пользователя отправить сообщение
        await callback.message.answer(
            "📝 Напишите ваше сообщение для администратора:\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await state.set_state(SupportStates.waiting_message)




@router.message(lambda m: m.text and '$' in m.text and (
    m.text.replace('$', '').replace(',', '.').replace(' ', '').replace('-', '').isdigit() or
    m.text.replace('$', '').replace(',', '.').replace(' ', '').replace('-', '').replace('.', '', 1).isdigit()
))
async def handle_bet_change(message: Message, state: FSMContext):
    """Обработка изменения ставки через сообщение типа '3$' или '3'"""
    # Проверяем FSM состояние - если есть активное состояние, игнорируем
    current_state = await state.get_state()
    if current_state:
        return  # Игнорируем, если есть активное FSM состояние (создание чека, депозит и т.д.)
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return  # Игнорируем, если пользователь не найден
    
    # Проверяем, что сообщение выглядит как команда изменения ставки (начинается с числа и содержит $)
    if not message.text or '$' not in message.text:
        return

    # Извлекаем число из сообщения
    text = message.text.replace('$', '').replace(',', '.').replace(' ', '').strip()
    try:
        bet_amount = float(text)
        if bet_amount < 0.1:
            await message.answer("❌ Минимальная ставка: $0.10")
            return
        
        # Обновляем базовую ставку
        await db.update_setting(user_id, "base_bet", bet_amount)
        await message.answer(f"✅ Базовая ставка установлена: ${bet_amount:.2f}")
    except ValueError:
        pass  # Игнорируем, если не число


@router.message(CheckStates.waiting_activations)
async def handle_activations_count(message: Message, state: FSMContext):
    """Обработка количества активаций"""
    try:
        activations = int(message.text)
        if activations < 1:
            await message.answer("❌ Количество активаций должно быть больше 0")
            return
        
        await state.update_data(activations=activations)
        await message.answer(
            f"✅ Количество активаций: {activations}\n\n"
            f"Введите сумму за каждую активацию (например: 5 или 5$):"
        )
        await state.set_state(CheckStates.waiting_amount)
    except ValueError:
        await message.answer("❌ Введите число (например: 10)")


@router.message(CheckStates.waiting_amount)
async def handle_check_amount(message: Message, state: FSMContext):
    """Обработка суммы за активацию"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Извлекаем число
    text = message.text.replace('$', '').replace(',', '.').replace(' ', '').strip()
    try:
        amount = float(text)
        if amount < 0.1:
            await message.answer("❌ Минимальная сумма: $0.10")
            return
        
        data = await state.get_data()
        activations = data.get("activations", 1)
        total_cost = amount * activations
        
        balance = user["balance"]
        if balance < total_cost:
            await message.answer(
                f"❌ Недостаточно средств!\n"
                f"Нужно: ${total_cost:.2f}\n"
                f"У вас: ${balance:.2f}"
            )
            await state.clear()
            return
        
        await state.update_data(amount=amount, total_cost=total_cost)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="check_captcha_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="check_captcha_no"),
            ]
        ])
        
        await message.answer(
            f"✅ Сумма за активацию: ${amount:.2f}\n"
            f"💰 Общая стоимость: ${total_cost:.2f}\n\n"
            f"Нужна ли капча для активации чека?",
            reply_markup=keyboard
        )
        await state.set_state(CheckStates.waiting_captcha_choice)
    except ValueError:
        await message.answer("❌ Введите число (например: 5 или 5$)")


@router.callback_query(F.data.startswith("check_captcha_"))
async def handle_captcha_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора капчи"""
    requires_captcha = callback.data.endswith("yes")
    await state.update_data(requires_captcha=requires_captcha)
    
    await callback.answer()
    
    # Спрашиваем тип депозита
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Бездепный", callback_data="check_deposit_no"),
            InlineKeyboardButton(text="💰 Депный", callback_data="check_deposit_yes"),
        ]
    ])
    
    await callback.message.answer(
        "Выберите тип чека:\n\n"
        "• <b>Бездепный</b> - не требуется депозит для активации\n"
        "• <b>Депный</b> - требуется минимальный депозит для активации",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(CheckStates.waiting_deposit_type)


@router.callback_query(F.data.startswith("check_deposit_"))
async def handle_deposit_type_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа депозита"""
    is_deposit = callback.data.endswith("yes")
    deposit_type = "deposit" if is_deposit else "no_deposit"
    await state.update_data(deposit_type=deposit_type)
    
    await callback.answer()
    
    if is_deposit:
        # Если депный, спрашиваем минимальный депозит
        await callback.message.answer(
            "Введите минимальный депозит для активации чека (например: 10 или 10$):\n\n"
            "Для отмены отправьте /cancel"
        )
        await state.set_state(CheckStates.waiting_min_deposit)
    else:
        # Если бездепный, спрашиваем отыгрыш
        await callback.message.answer(
            "Введите множитель отыгрыша (например: 2 для x2, 3 для x3, или 1 если отыгрыш не нужен):\n\n"
            "Отыгрыш означает, что пользователь получит указанную сумму, но сможет вывести её только после того, "
            "как сделает ставок на сумму равную полученной сумме × множитель отыгрыша.\n\n"
            "Например: если пользователь получил $10 с отыгрышем x3, то он должен сделать ставок на $30, "
            "прежде чем сможет вывести эти $10.\n\n"
            "Для отмены отправьте /cancel"
        )
        await state.set_state(CheckStates.waiting_rollover)


@router.message(CheckStates.waiting_min_deposit)
async def handle_min_deposit(message: Message, state: FSMContext):
    """Обработка минимального депозита"""
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание чека отменено")
        return
    
    text = message.text.replace('$', '').replace(',', '.').replace(' ', '').strip()
    try:
        min_deposit = float(text)
        if min_deposit < 0:
            await message.answer("❌ Минимальный депозит должен быть больше или равен 0")
            return
        
        await state.update_data(min_deposit=min_deposit)
        
        # Теперь спрашиваем отыгрыш
        await message.answer(
            "Введите множитель отыгрыша (например: 2 для x2, 3 для x3, или 1 если отыгрыш не нужен):\n\n"
            "Отыгрыш означает, что пользователь получит указанную сумму, но сможет вывести её только после того, "
            "как сделает ставок на сумму равную полученной сумме × множитель отыгрыша.\n\n"
            "Например: если пользователь получил $10 с отыгрышем x3, то он должен сделать ставок на $30, "
            "прежде чем сможет вывести эти $10.\n\n"
            "Для отмены отправьте /cancel"
        )
        await state.set_state(CheckStates.waiting_rollover)
    except ValueError:
        await message.answer("❌ Введите число (например: 10 или 10$)")


@router.message(CheckStates.waiting_rollover)
async def handle_rollover(message: Message, state: FSMContext):
    """Обработка отыгрыша"""
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание чека отменено")
        return
    
    text = message.text.replace('x', '').replace('X', '').replace(',', '.').replace(' ', '').strip()
    try:
        rollover_multiplier = float(text)
        if rollover_multiplier < 1:
            await message.answer("❌ Множитель отыгрыша должен быть больше или равен 1")
            return
        
        await state.update_data(rollover_multiplier=rollover_multiplier)
        
        # Переходим к тексту чека
        await message.answer(
            "Введите текст для чека (или отправьте /skip чтобы пропустить):"
        )
        await state.set_state(CheckStates.waiting_text)
    except ValueError:
        await message.answer("❌ Введите число (например: 2 для x2 или 1 если отыгрыш не нужен).\n\n"
                             "Множитель 1 означает, что отыгрыш не требуется, и пользователь сможет сразу вывести полученную сумму.")


@router.message(CheckStates.waiting_text)
async def handle_check_text(message: Message, state: FSMContext):
    """Обработка текста чека"""
    text = message.text if message.text != "/skip" else None
    await state.update_data(text=text)
    
    await message.answer(
        "Отправьте картинку для чека (или отправьте /skip чтобы пропустить):"
    )
    await state.set_state(CheckStates.waiting_image)


@router.message(CheckStates.waiting_image, F.photo)
async def handle_check_image(message: Message, state: FSMContext):
    """Обработка картинки чека"""
    photo = message.photo[-1]  # Берем самое большое фото
    file_id = photo.file_id
    
    await state.update_data(image_url=file_id)
    
    await message.answer(
        "Введите текст для кнопки (или отправьте /skip чтобы пропустить):"
    )
    await state.set_state(CheckStates.waiting_button_text)


@router.message(CheckStates.waiting_image)
async def handle_check_image_skip(message: Message, state: FSMContext):
    """Пропуск картинки"""
    if message.text == "/skip":
        await state.update_data(image_url=None)
        await message.answer(
            "Введите текст для кнопки (или отправьте /skip чтобы пропустить):"
        )
        await state.set_state(CheckStates.waiting_button_text)
    else:
        await message.answer("❌ Отправьте картинку или /skip")


@router.message(CheckStates.waiting_button_text)
async def handle_check_button_text(message: Message, state: FSMContext):
    """Обработка текста кнопки и создание чека"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    button_text = message.text if message.text != "/skip" else None
    button_url = None  # URL будет генерироваться при создании чека
    
    data = await state.get_data()
    activations = data.get("activations")
    amount = data.get("amount")
    total_cost = data.get("total_cost")
    requires_captcha = data.get("requires_captcha", False)
    image_url = data.get("image_url")
    text = data.get("text")
    deposit_type = data.get("deposit_type", "no_deposit")
    min_deposit = data.get("min_deposit", 0.0)
    rollover_multiplier = data.get("rollover_multiplier", 1.0)
    
    # Списываем баланс
    await db.update_balance(user_id, -total_cost)
    
    # Генерируем уникальный код чека
    check_code = generate_check_code()
    
    # Создаем чек
    check_id = await db.create_check(
        creator_id=user_id,
        check_code=check_code,
        total_activations=activations,
        amount_per_activation=amount,
        requires_captcha=requires_captcha,
        captcha_result=None,
        image_url=image_url,
        text=text,
        button_text=button_text,
        button_url=None,
        rollover_multiplier=rollover_multiplier,
        deposit_type=deposit_type,
        min_deposit=min_deposit
    )
    
    # Отправляем результат
    deposit_type_text = "💰 Депный" if deposit_type == "deposit" else "✅ Бездепный"
    rollover_text = f"x{rollover_multiplier}" if rollover_multiplier > 1 else "Нет"
    
    result_text = f"""✅ <b>Чек создан!</b>

💰 Списанно с баланса: ${total_cost:.2f}
🎫 Код чека: <code>{check_code}</code>
📊 Активаций: {activations}
💵 Сумма за активацию: ${amount:.2f}
{'🔒 Капча: включена' if requires_captcha else '🔓 Капча: выключена'}
📌 Тип: {deposit_type_text}"""
    
    if deposit_type == "deposit":
        result_text += f"\n💳 Мин. депозит: ${min_deposit:.2f}"
    
    result_text += f"\n🎰 Отыгрыш: {rollover_text}"
    result_text += f"\n\n🔗 <b>Ссылка на чек:</b>\n{build_check_link(check_code)}"""

    user_text_formatted = format_user_text(text)
    if user_text_formatted:
        result_text += f"\n\n{user_text_formatted}"
    
    # Если есть картинка, отправляем с картинкой
    if image_url:
        await message.answer_photo(photo=image_url, caption=result_text, parse_mode="HTML")
    else:
        await message.answer(result_text, parse_mode="HTML")
    
    # Добавляем кнопку "ПОДЕЛИТСЯ"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    share_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 ПОДЕЛИТСЯ", callback_data=f"check_share_{check_code}"),
        ]
    ])
    
    await message.answer("Нажмите кнопку ниже, чтобы поделиться чеком:", reply_markup=share_keyboard)
    
    await state.clear()


# Состояние для капчи (хранит последовательность нажатий)
CAPTCHA_STATES = {}  # {user_id: {"check_id": int, "check_code": str, "captcha_result": str, "user_sequence": list}}


@router.callback_query(F.data.startswith("captcha_"))
async def handle_captcha_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки капчи"""
    user_id = callback.from_user.id
    
    # Получаем данные из состояния
    data = await state.get_data()
    check_id = data.get("check_id")
    check_code = data.get("check_code")
    captcha_result = data.get("captcha_result")
    
    if not check_id or not captcha_result:
        await callback.answer("❌ Ошибка: данные капчи не найдены", show_alert=True)
        return
    
    # Инициализируем состояние капчи, если его нет
    if user_id not in CAPTCHA_STATES:
        CAPTCHA_STATES[user_id] = {
            "check_id": check_id,
            "check_code": check_code,
            "captcha_result": captcha_result,
            "user_sequence": []
        }
    
    # Добавляем выбранный символ
    selected_symbol = callback.data.replace("captcha_", "")
    CAPTCHA_STATES[user_id]["user_sequence"].append(selected_symbol)
    
    user_sequence = CAPTCHA_STATES[user_id]["user_sequence"]
    # Правильно разбиваем строку на символы (учитываем эмодзи и обычные символы)
    expected_sequence = []
    i = 0
    while i < len(captcha_result):
        # Проверяем, является ли текущий символ началом эмодзи
        if captcha_result[i] in ["🍇", "🍋"]:
            expected_sequence.append(captcha_result[i])
            i += 1
        elif captcha_result[i:i+3] == "Bar":
            expected_sequence.append("Bar")
            i += 3
        elif captcha_result[i] == "7":
            expected_sequence.append("7")
            i += 1
        else:
            # Если не распознали, берем один символ
            expected_sequence.append(captcha_result[i])
            i += 1
    
    captcha_total = data.get("captcha_total", len(expected_sequence))
    try:
        await callback.message.edit_text(
            build_captcha_text(user_sequence, captcha_total),
            reply_markup=build_captcha_keyboard(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    # Проверяем длину
    if len(user_sequence) < len(expected_sequence):
        await callback.answer(f"Выбрано: {' → '.join(user_sequence)}")
        return
    
    # Проверяем правильность
    if user_sequence == expected_sequence:
        # Капча пройдена!
        check = await db.get_check_by_id(check_id)
        if not check:
            await callback.answer("❌ Чек не найден", show_alert=True)
            del CAPTCHA_STATES[user_id]
            await state.clear()
            return
        
        # Активируем чек
        success = await db.activate_check(check_id, user_id)
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

            check_code = data.get("check_code", check["check_code"])
            result_keyboard = build_check_keyboard(
                check_code,
                check.get("button_text"),
                check.get("button_url"),
            )

            if check["image_url"]:
                await callback.message.answer_photo(photo=check["image_url"], caption=text, reply_markup=result_keyboard, parse_mode="HTML")
            else:
                await callback.message.answer(text, reply_markup=result_keyboard, parse_mode="HTML")
            
            await notify_check_owner(db, callback.message.bot, check["id"], check_code, callback.from_user)
            await callback.answer("✅ Капча пройдена! Чек активирован")
        else:
            await callback.answer("❌ Ошибка при активации чека", show_alert=True)
        
        # Очищаем состояние
        if user_id in CAPTCHA_STATES:
            del CAPTCHA_STATES[user_id]
        await state.clear()
    else:
        # Неправильная последовательность
        await callback.answer("❌ Неправильная последовательность! Попробуйте снова.", show_alert=True)
        # Очищаем последовательность
        if user_id in CAPTCHA_STATES:
            del CAPTCHA_STATES[user_id]
        
        check = await db.get_check_by_id(check_id)
        if check and check["requires_captcha"]:
            dice_message = await callback.message.answer_dice(emoji="🎰")
            symbols = decode_slot_symbols(dice_message.dice.value)
            new_result = "".join(symbols)
            await asyncio.sleep(3)

            captcha_message = await callback.message.answer(
                build_captcha_text([], len(symbols)),
                reply_markup=build_captcha_keyboard(),
                parse_mode="HTML"
            )
            await state.clear()
            await state.update_data(
                check_id=check_id,
                check_code=check_code,
                captcha_result=new_result,
                captcha_total=len(symbols),
                captcha_message_id=captcha_message.message_id,
                captcha_chat_id=captcha_message.chat.id,
            )


@router.callback_query(F.data.startswith("check_share_"))
async def handle_check_share(callback: CallbackQuery):
    """Обработка кнопки 'ПОДЕЛИТСЯ' для чека"""
    check_code = callback.data.replace("check_share_", "")
    check = await db.get_check(check_code)
    
    if not check:
        await callback.answer("❌ Чек не найден", show_alert=True)
        return
    
    share_text = build_share_text(check)
    keyboard = build_check_keyboard(
        check_code,
        check.get("button_text"),
        check.get("button_url"),
    )
    
    if check["image_url"]:
        await callback.message.answer_photo(photo=check["image_url"], caption=share_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.message.answer(share_text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer("Сообщение готово к пересылке")


@router.message(SupportStates.waiting_message)
async def handle_support_message(message: Message, state: FSMContext):
    """Обработка сообщения поддержки от пользователя"""
    # Проверяем команду отмены
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Отправка сообщения отменена")
        return
    
    # Проверяем, что есть текст или медиа
    if not message.text and not message.photo and not message.video and not message.document:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение или медиа-файл")
        return
    
    user_id = message.from_user.id
    username = message.from_user.username or f"ID: {user_id}"
    message_text = message.text or (message.caption if message.photo else "Медиа-сообщение")
    
    # Сохраняем сообщение в базу данных
    support_message_id = await db.create_support_message(user_id, username, message_text)
    
    # Отправляем сообщение всем администраторам
    from config import ADMIN_IDS
    from datetime import datetime
    
    # Форматируем время
    current_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    admin_text = f"""💬 <b>Новое сообщение поддержки</b>

👤 <b>Пользователь:</b> @{username} (ID: {user_id})
🕐 <b>Время:</b> {current_time}
📝 <b>Сообщение:</b>

{message_text}

━━━━━━━━━━━━━━━━━━━━
ID сообщения: {support_message_id}"""
    
    # Создаем клавиатуру с кнопкой "Ответить"
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💬 Ответить",
                callback_data=f"support_reply_{support_message_id}"
            )
        ]
    ])
    
    # Отправляем всем администраторам
    bot = message.bot
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            if message.photo:
                # Если есть фото, отправляем с фото
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=admin_text,
                    reply_markup=reply_keyboard,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    reply_markup=reply_keyboard,
                    parse_mode="HTML"
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения поддержки администратору {admin_id}: {e}")
    
    # Подтверждаем пользователю
    if sent_count > 0:
        await message.answer(
            "✅ Ваше сообщение отправлено администраторам. Ответ придет в ближайшее время.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при отправке сообщения. Попробуйте позже.",
            parse_mode="HTML"
        )
    
    await state.clear()

