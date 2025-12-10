import re
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import Database
from keyboards import (
    get_deposit_keyboard, get_games_menu_keyboard, get_wallet_keyboard,
    get_top_category_keyboard
)
from handlers.start import build_profile_view, send_photo
from handlers.deposit import safe_edit_message
from handlers.games import GAME_CONFIGS

router = Router(name="group_commands")
db = Database()
logger = logging.getLogger(__name__)

# Маппинг названий игр на типы
GAME_NAMES = {
    "куб": "dice", "кубик": "dice", "кубы": "dice",
    "дартс": "dart", "дарт": "dart",
    "боулинг": "bowling", "боул": "bowling",
    "футбол": "football", "фут": "football",
    "баскетбол": "basketball", "баскет": "basketball",
    "слоты": "slots", "слот": "slots"
}

# Маппинг режимов игр
GAME_MODES = {
    "dice": {
        "чет": "even", "четное": "even", "четный": "even",
        "нечет": "odd", "нечетное": "odd", "нечетный": "odd",
        "1": "exact_1", "2": "exact_2", "3": "exact_3",
        "4": "exact_4", "5": "exact_5", "6": "exact_6",
        "пара": "pair", "18": "18", "21": "21",
        "111": "111", "333": "333", "666": "666"
    },
    "dart": {
        "красное": "red", "красный": "red", "крас": "red",
        "белое": "white", "белый": "white", "бел": "white",
        "центр": "center", "мимо": "miss", "отскок": "miss"
    },
    "bowling": {
        "0-3": "0-3", "4-6": "4-6",
        "страйк": "strike", "страй": "strike",
        "мимо": "miss", "промах": "miss"
    },
    "football": {
        "гол": "goal", "голы": "goal",
        "мимо": "miss", "промах": "miss",
        "центр": "center", "хет-трик": "hattrick", "хеттрик": "hattrick"
    },
    "basketball": {
        "гол": "hit", "попал": "hit",
        "мимо": "miss", "промах": "miss",
        "чистый": "clean", "чистый гол": "clean",
        "застрял": "stuck", "застря": "stuck"
    }
}


def is_group_chat(message: Message) -> bool:
    """Проверяет, является ли чат группой или супергруппой"""
    return message.chat.type in ['group', 'supergroup']


# /start обрабатывается в start.py с проверкой на группы


@router.message(F.text.regexp(re.compile(r'^(деп|пополнить)\s+([\d.,]+)$', re.IGNORECASE)))
async def cmd_deposit_group(message: Message, state: FSMContext):
    """Обработка команд деп/пополнить с суммой"""
    if not is_group_chat(message):
        return
    
    match = re.match(r'^(деп|пополнить)\s+([\d.,]+)$', message.text, re.IGNORECASE)
    if not match:
        return
    
    amount_str = match.group(2).replace(",", ".")
    try:
        amount = float(amount_str)
    except ValueError:
        await message.reply("❌ Неверный формат суммы")
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance_usd = user["balance"]
    text = f"""💵 <b>Депозит</b>
    
💰 <b>Баланс:</b> ${balance_usd:.2f}
    
<b>Минимальный депозит:</b> $0.10

<b>Выберите способ пополнения:</b>"""
    
    keyboard = get_deposit_keyboard()
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text.regexp(re.compile(r'^(балик|баланс|б)$', re.IGNORECASE)))
async def cmd_balance_group(message: Message):
    """Обработка команд баланс/балик/б"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance_usd = user.get("balance", 0.0)
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    await message.reply(
        f"💰 <b>Ваш баланс:</b> ${balance_usd:.2f}\n"
        f"🍉 <b>Арбуз коины:</b> {arbuzz_balance:.0f} AC",
        parse_mode="HTML"
    )


@router.message(F.text.regexp(re.compile(r'^игры$', re.IGNORECASE)))
async def cmd_games_group(message: Message):
    """Обработка команды игры"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance_usd = user["balance"]
    text = f"""🎮 <b>Игры</b>

🙌 <b>Твой шанс выиграть до х1000</b>

ℹ️ <i>Все исходы определяются через Telegram</i>

💰 <b>Баланс:</b> ${balance_usd:.2f}"""
    
    keyboard = get_games_menu_keyboard()
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text.regexp(re.compile(r'^(\d+)\s*арбуз(ов|а|ы|е)?$', re.IGNORECASE)))
async def cmd_set_bet_arbuzz_group(message: Message, state: FSMContext):
    """Обработка установки базовой ставки в арбузах через (сумма) арбуз/арбузов - работает в группах и личных чатах"""
    
    match = re.match(r'^(\d+)\s*арбуз(ов|а|ы|е)?$', message.text, re.IGNORECASE)
    if not match:
        return
    
    bet_amount = float(match.group(1))
    
    # Проверка минимальной ставки
    if bet_amount < 1:
        await message.reply("❌ Минимальная ставка: 1 AC")
        return
    
    # Проверка максимальной ставки
    from config import MAX_BET
    if bet_amount > MAX_BET:
        await message.reply(f"❌ Максимальная ставка: {MAX_BET:.0f} AC")
        return
    
    # Получаем пользователя
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        username = message.from_user.username or f"user_{user_id}"
        await db.create_user(user_id, username)
        user = await db.get_user(user_id)
    
    if not user:
        return
    
    # Импортируем BASE_BET_ARBUZZ из games.py
    from handlers.games import BASE_BET_ARBUZZ
    
    # Сохраняем базовую ставку для арбузов
    BASE_BET_ARBUZZ[user_id] = bet_amount
    
    # Выводим сообщение об установке ставки
    await message.reply(f"Базовая ставка установлена - {bet_amount:.0f} АС", parse_mode="HTML")
    
    logger.info(
        f"💰 Базовая ставка в арбузах установлена: "
        f"user_id={user_id}, bet_amount={bet_amount} AC"
    )


@router.message(F.text.regexp(re.compile(r'^([\d.,]+)\$$')))
async def cmd_set_bet_group(message: Message, state: FSMContext):
    """Обработка установки ставки через (сумма)$ - работает в группах и личных чатах"""
    match = re.match(r'^([\d.,]+)\$$', message.text)
    if not match:
        return
    
    amount_str = match.group(1).replace(",", ".")
    try:
        amount = float(amount_str)
        if amount < 0.1:
            await message.reply("❌ Минимальная ставка: $0.10")
            return
        
        # Проверка максимальной ставки
        from config import MAX_BET
        if amount > MAX_BET:
            await message.reply(f"❌ Максимальная ставка: ${MAX_BET:.2f}")
            return
        
        # Сохраняем ставку в состояние
        await state.update_data(base_bet=amount)
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        if user:
            await db.update_user_base_bet(user_id, amount)
        
        await message.reply(f"✅ <b>Ставка установлена:</b> ${amount:.2f}", parse_mode="HTML")
    except ValueError:
        await message.reply("❌ Неверный формат суммы")


@router.message(F.text.regexp(re.compile(r'^(куб|кубик)\s*7\s*([+\-])?$', re.IGNORECASE)))
async def cmd_dice_7_group(message: Message, state: FSMContext):
    """Обработка команд 'куб 7+', 'куб 7-', 'куб 7' для игры Кубик: +- 7"""
    logger.info(f"🔍 group_commands: cmd_dice_7_group вызван: text='{message.text}', chat_type={message.chat.type}")
    if not is_group_chat(message):
        logger.info(f"⚠️ group_commands: не групповой чат, пропускаем")
        return
    
    match = re.match(r'^(куб|кубик)\s*7\s*([+\-])?$', message.text.lower())
    if not match:
        return
    
    modifier = match.group(2) if match.group(2) else None
    
    # Определяем тип ставки
    if modifier == '+':
        bet_type = "more_7"  # Больше 7
    elif modifier == '-':
        bet_type = "less_7"  # Меньше 7
    else:
        bet_type = "equal_7"  # Равно 7
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    # Получаем ставку из состояния или базовую ставку
    state_data = await state.get_data()
    bet = state_data.get("base_bet", user.get("base_bet", 1.0))
    
    # Проверяем, используется ли демо-баланс (арбузы)
    use_arbuzz = "арбуз" in message.text.lower() or " ac" in message.text.lower() or message.text.lower().endswith("ac")
    
    # Если не указано явно, но нет долларов, но есть арбузы - используем арбузы
    if not use_arbuzz:
        balance_usd = user.get("balance", 0.0)
        arbuzz_balance = user.get("arbuzz_balance", 0.0)
        if balance_usd < bet and arbuzz_balance >= bet:
            use_arbuzz = True
            logger.info(f"🔄 Автоматически переключаемся на арбузы: долларов=${balance_usd:.2f}, арбузов={arbuzz_balance:.0f}")
    
    if use_arbuzz:
        # Используем демо-баланс (арбузы)
        arbuzz_balance = user.get("arbuzz_balance", 0.0)
        if arbuzz_balance < bet:
            await message.reply(f"❌ Недостаточно арбузов. Ваш баланс: {arbuzz_balance:.0f} AC")
            return
        # Сохраняем валюту в состояние
        await state.update_data(currency="arbuzz")
    else:
        # Используем обычный баланс (доллары)
        balance_usd = user.get("balance", 0.0)
        if balance_usd < bet:
            await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${balance_usd:.2f}")
            return
        # Сохраняем валюту в состояние
        await state.update_data(currency="dollar")
    
    # Импортируем функцию запуска игры из games.py
    from handlers.games import start_game_with_params
    
    # Запускаем игру
    try:
        currency_str = "arbuzz" if use_arbuzz else "dollar"
        game_started = await start_game_with_params(
            message.bot,
            user_id,
            message.chat.id,
            "dice_7",
            bet_type,
            bet,
            message,
            None,
            currency=currency_str
        )
        if not game_started:
            await message.reply("❌ Не удалось запустить игру. Проверьте баланс.")
    except Exception as e:
        logger.error(f"Ошибка при запуске игры 'Кубик: +- 7': {e}", exc_info=True)
        await message.reply("❌ Ошибка при запуске игры")


@router.message(F.text.regexp(re.compile(r'^([а-яё]+)\s+([а-яё\d-]+)$', re.IGNORECASE)))
async def cmd_game_start_group(message: Message, state: FSMContext):
    """Обработка команд типа 'куб чет', 'кубик 666', 'дартс красное' и т.д."""
    logger.info(f"🔍 group_commands: cmd_game_start_group вызван: text='{message.text}', chat_type={message.chat.type}")
    if not is_group_chat(message):
        logger.info(f"⚠️ group_commands: не групповой чат, пропускаем")
        return
    
    match = re.match(r'^([а-яё]+)\s+([а-яё\d-]+)$', message.text.lower())
    if not match:
        return
    
    game_name = match.group(1).strip()
    mode_name = match.group(2).strip()
    
    # Определяем тип игры
    game_type = GAME_NAMES.get(game_name)
    if not game_type:
        return  # Неизвестная игра
    
    # Определяем режим игры
    modes = GAME_MODES.get(game_type, {})
    bet_type = modes.get(mode_name)
    if not bet_type:
        return  # Неизвестный режим
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    # Получаем ставку из состояния или базовую ставку
    state_data = await state.get_data()
    bet = state_data.get("base_bet", user.get("base_bet", 1.0))
    
    # Проверяем, используется ли демо-баланс (арбузы)
    # Если в тексте есть "арбуз" или "ac", используем демо-баланс
    use_arbuzz = "арбуз" in message.text.lower() or " ac" in message.text.lower() or message.text.lower().endswith("ac")
    
    # Если не указано явно, но нет долларов, но есть арбузы - используем арбузы
    if not use_arbuzz:
        balance_usd = user.get("balance", 0.0)
        arbuzz_balance = user.get("arbuzz_balance", 0.0)
        if balance_usd < bet and arbuzz_balance >= bet:
            use_arbuzz = True
            logger.info(f"🔄 Автоматически переключаемся на арбузы: долларов=${balance_usd:.2f}, арбузов={arbuzz_balance:.0f}")
    
    if use_arbuzz:
        # Используем демо-баланс (арбузы)
        arbuzz_balance = user.get("arbuzz_balance", 0.0)
        if arbuzz_balance < bet:
            await message.reply(f"❌ Недостаточно арбузов. Ваш баланс: {arbuzz_balance:.0f} AC")
            return
        # Сохраняем валюту в состояние
        await state.update_data(currency="arbuzz")
    else:
        # Используем обычный баланс (доллары)
        balance_usd = user.get("balance", 0.0)
        if balance_usd < bet:
            await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${balance_usd:.2f}")
            return
        # Сохраняем валюту в состояние
        await state.update_data(currency="dollar")
    
    # Импортируем функцию запуска игры из games.py
    from handlers.games import start_game_from_text
    
    # Запускаем игру
    try:
        await start_game_from_text(message, game_type, bet_type, bet, state)
    except Exception as e:
        logger.error(f"Ошибка при запуске игры: {e}", exc_info=True)
        await message.reply("❌ Ошибка при запуске игры")


@router.message(F.text.regexp(re.compile(r'^(отправить|/send)\s+([\d.,]+)\$$', re.IGNORECASE)))
async def cmd_send_money_group(message: Message):
    """Обработка команд отправить/send для перевода средств"""
    if not is_group_chat(message):
        return
    
    # Проверяем, что сообщение является ответом на другое сообщение
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение пользователя, которому хотите отправить средства")
        return
    
    match = re.match(r'^(отправить|/send)\s+([\d.,]+)\$$', message.text, re.IGNORECASE)
    if not match:
        return
    
    amount_str = match.group(2).replace(",", ".")
    try:
        amount = float(amount_str)
        if amount < 0.1:
            await message.reply("❌ Минимальная сумма перевода: $0.10")
            return
    except ValueError:
        await message.reply("❌ Неверный формат суммы")
        return
    
    sender_id = message.from_user.id
    recipient_id = message.reply_to_message.from_user.id
    
    # Нельзя отправлять самому себе
    if sender_id == recipient_id:
        await message.reply("❌ Нельзя отправить средства самому себе")
        return
    
    sender = await db.get_user(sender_id)
    if not sender:
        await db.create_user(sender_id, message.from_user.username or message.from_user.first_name or "User")
        sender = await db.get_user(sender_id)
    
    if sender["balance"] < amount:
        await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${sender['balance']:.2f}")
        return
    
    # Списываем у отправителя
    await db.update_balance(sender_id, -amount)
    
    # Начисляем получателю
    recipient = await db.get_user(recipient_id)
    if not recipient:
        await db.create_user(recipient_id, message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name or "User")
        recipient = await db.get_user(recipient_id)
    
    await db.update_balance(recipient_id, amount)
    
    sender_name = message.from_user.username or message.from_user.first_name or "Пользователь"
    recipient_name = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name or "Пользователь"
    
    await message.reply(
        f"✅ <b>Перевод выполнен</b>\n\n"
        f"👤 От: {sender_name}\n"
        f"👤 Кому: {recipient_name}\n"
        f"💰 Сумма: ${amount:.2f}",
        parse_mode="HTML"
    )


@router.message(F.text.regexp(re.compile(r'^топ$', re.IGNORECASE)))
async def cmd_top_group(message: Message):
    """Обработка команды топ"""
    if not is_group_chat(message):
        return
    
    text = """🏆 <b>ТОП</b>

🏆 Выберите категорию топа:"""
    
    keyboard = get_top_category_keyboard()
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text.regexp(re.compile(r'^(профиль|статистика)$', re.IGNORECASE)))
async def cmd_profile_group(message: Message):
    """Обработка команд профиль/статистика"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    text, keyboard = await build_profile_view(user_id, user)
    await send_photo(message, "профиль.jpg", text, keyboard, is_callback=False)


@router.message(F.text.regexp(re.compile(r'^кошелек$', re.IGNORECASE)))
async def cmd_wallet_group(message: Message):
    """Обработка команды кошелек"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance_usd = user.get("balance", 0.0)
    locked_balance_usd = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    
    from ton_price import get_ton_to_usd_rate, usd_to_ton
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    locked_balance_ton = usd_to_ton(locked_balance_usd, ton_rate)
    
    text = f"""💼 <b>Кошелек</b>

💰 <b>Доступный баланс:</b> {balance_ton:.4f} TON (${balance_usd:.2f})
🔒 <b>Заблокированный баланс:</b> {locked_balance_ton:.4f} TON (${locked_balance_usd:.2f})"""
    
    if locked_balance_usd > 0 and rollover_requirement > 0:
        text += f"\n\n⚠️ <b>Требуется отыграть:</b> ${rollover_requirement:.2f}"
        text += f"\n<i>Заблокированные средства можно использовать для игр, но вывести их можно будет только после выполнения требования отыгрыша.</i>"
    
    text += "\n\nВыберите действие:"
    
    keyboard = get_wallet_keyboard()
    await send_photo(message, "кошелек.jpg", text, keyboard, is_callback=False)


@router.message(F.text.regexp(re.compile(r'^вб$', re.IGNORECASE)))
async def cmd_all_balance_bet_group(message: Message, state: FSMContext):
    """Обработка команды вб (весь баланс)"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance = user["balance"]
    if balance < 0.1:
        await message.reply("❌ Недостаточно средств для ставки")
        return
    
    # Устанавливаем ставку равной всему балансу
    await state.update_data(base_bet=balance)
    await db.update_user_base_bet(user_id, balance)
    
    await message.reply(f"✅ <b>Ставка установлена на весь баланс:</b> ${balance:.2f}", parse_mode="HTML")


@router.message(F.text.regexp(re.compile(r'^вывод\s+([\d.,]+)$', re.IGNORECASE)))
async def cmd_withdraw_amount_group(message: Message):
    """Обработка команды вывод с суммой"""
    if not is_group_chat(message):
        return
    
    match = re.match(r'^вывод\s+([\d.,]+)$', message.text, re.IGNORECASE)
    if not match:
        return
    
    amount_str = match.group(1).replace(",", ".")
    try:
        amount = float(amount_str)
        if amount < 0.1:
            await message.reply("❌ Минимальная сумма вывода: $0.10")
            return
    except ValueError:
        await message.reply("❌ Неверный формат суммы")
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    # Используем логику из deposit.py для создания чека
    # Создаем чек напрямую через crypto_pay
    from crypto_pay import crypto_pay
    from ton_price import get_ton_to_usd_rate, usd_to_ton
    
    balance = user["balance"]
    if balance < amount:
        await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${balance:.2f}")
        return
    
    commission = amount * 0.002  # 0.20% комиссия
    final_amount = amount - commission
    
    try:
        check = await crypto_pay.create_check(
            asset="USDT",
            amount=str(final_amount),
            pin_to_user_id=user_id
        )
        
        if check and check.get("error"):
            await message.reply("❌ Ошибка создания чека. Попробуйте позже.")
            return
        
        check_url = check.get("bot_check_url") or check.get("check_url") if check else None
        if check and check_url:
            await db.update_balance(user_id, -amount)
            await db.add_withdrawal(user_id, amount, "crypto_pay")
            
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
            
            await message.reply(text, reply_markup=check_keyboard, parse_mode="HTML")
        else:
            await message.reply("❌ Ошибка создания чека. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при создании чека: {e}", exc_info=True)
        await message.reply("❌ Ошибка создания чека. Попробуйте позже.")


@router.message(F.text.regexp(re.compile(r'^вывод$', re.IGNORECASE)))
async def cmd_withdraw_group(message: Message):
    """Обработка команды вывод (окно вывода)"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance_usd = user.get("balance", 0.0)
    locked_balance_usd = user.get("locked_balance", 0.0)
    rollover_requirement = user.get("rollover_requirement", 0.0)
    
    from ton_price import get_ton_to_usd_rate, usd_to_ton
    ton_rate = await get_ton_to_usd_rate()
    balance_ton = usd_to_ton(balance_usd, ton_rate)
    locked_balance_ton = usd_to_ton(locked_balance_usd, ton_rate)
    
    text = f"""➖ <b>Вывод средств</b>

💰 <b>Доступно для вывода:</b> {balance_ton:.4f} TON (${balance_usd:.2f})"""
    
    if locked_balance_usd > 0 and rollover_requirement > 0:
        text += f"\n🔒 <b>Заблокировано:</b> {locked_balance_ton:.4f} TON (${locked_balance_usd:.2f})"
        text += f"\n📊 <b>Требуется отыграть:</b> ${rollover_requirement:.2f}"
        text += f"\n\n⚠️ <i>Заблокированные средства можно вывести только после выполнения требования отыгрыша.</i>"
    
    text += f"\n\n<b>Выберите способ вывода:</b>"
    
    from keyboards import get_withdrawal_keyboard
    keyboard = get_withdrawal_keyboard()
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text.regexp(re.compile(r'^чек$', re.IGNORECASE)))
async def cmd_check_group(message: Message):
    """Обработка команды чек (создать чек)"""
    if not is_group_chat(message):
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    balance = user["balance"]
    if balance < 0.1:
        await message.reply("❌ Недостаточно средств на балансе для создания чека")
        return
    
    # Показываем инструкцию по созданию чека через inline
    await message.reply(
        "🎫 <b>Создание чека</b>\n\n"
        "Для создания чека используйте inline-режим:\n"
        "1. Начните вводить @ваш_бот в любом чате\n"
        "2. Введите формат: <code>сумма количество текст</code>\n"
        "Например: <code>5 10 Подарок другу</code>\n\n"
        "💰 Ваш баланс: ${balance:.2f}",
        parse_mode="HTML"
    )


@router.message(F.text.regexp(re.compile(r'^(pvp|пвп)\s+([\d.,]+)\s+(\d+)$', re.IGNORECASE)))
async def cmd_pvp_group(message: Message, state: FSMContext):
    """Обработка команд pvp/пвп сумма кол-во игроков"""
    if not is_group_chat(message):
        return
    
    match = re.match(r'^(pvp|пвп)\s+([\d.,]+)\s+(\d+)$', message.text, re.IGNORECASE)
    if not match:
        return
    
    amount_str = match.group(2).replace(",", ".")
    players_count = int(match.group(3))
    
    try:
        amount = float(amount_str)
        if amount < 0.1:
            await message.reply("❌ Минимальная ставка: $0.10")
            return
    except ValueError:
        await message.reply("❌ Неверный формат суммы")
        return
    
    if players_count < 2 or players_count > 4:
        await message.reply("❌ Количество игроков должно быть от 2 до 4")
        return
    
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, message.from_user.username or message.from_user.first_name or "User")
        user = await db.get_user(user_id)
    
    if user["balance"] < amount:
        await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${user['balance']:.2f}")
        return
    
    # Используем логику из pvp.py для создания дуэли
    # По умолчанию используем боулинг, но можно расширить
    game_type = "bowling"  # Можно сделать выбор игры
    
    # Списываем ставку
    await db.update_balance(user_id, -amount)
    
    # Создаем дуэль
    import uuid
    unique_link = f"pvp_{uuid.uuid4().hex[:12]}"
    duel_id = await db.create_pvp_duel(
        creator_id=user_id,
        game_type=game_type,
        max_players=players_count,
        bet_amount=amount,
        unique_link=unique_link
    )
    
    # Получаем username бота
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username
    duel_link = f"https://t.me/{bot_username}?start={unique_link}"
    
    await message.reply(
        f"✅ <b>PvP дуэль создана!</b>\n\n"
        f"🎮 Игра: Боулинг\n"
        f"💰 Ставка: ${amount:.2f}\n"
        f"👥 Игроков: {players_count}\n"
        f"🔗 Ссылка: {duel_link}\n\n"
        f"Отправьте ссылку другим игрокам для участия!",
        parse_mode="HTML"
    )

