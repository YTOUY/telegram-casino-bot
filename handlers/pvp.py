import asyncio
import logging
import uuid
import random
import aiosqlite
from typing import Optional, Dict, List

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from keyboards import (
    get_pvp_menu_keyboard,
    get_pvp_game_select_keyboard,
    get_pvp_players_count_keyboard,
    get_pvp_my_duels_keyboard,
    get_pvp_duel_actions_keyboard,
)

router = Router(name="pvp")
db = Database()
logger = logging.getLogger(__name__)

# ID канала для PvP
PVP_CHANNEL_ID = -1003160160959  # @pvparbuz
PVP_CHANNEL_USERNAME = "pvparbuz"

# Комиссия 10%
PVP_COMMISSION = 0.10

# Комиссия за игру с ботом 3%
PVP_BOT_COMMISSION = 0.03

# ID каналов для рассылки
ARBUZIK_CHANNEL = "@arbuzikgame"
CRYPTOGIFTS_CHANNEL = "@cryptogifts_ru"


def generate_binary_link(number: int) -> str:
    """Генерирует красивую ссылку из 1 и 0 для номера дуэли"""
    # Преобразуем число в бинарное представление
    binary = bin(number)[2:]  # Убираем префикс '0b'
    # Для 100: "1100100" - это уже красиво
    # Можно дополнить до 8 символов для симметрии
    if len(binary) < 8:
        binary = binary.zfill(8)
    # Возвращаем ссылку с префиксом pvp_
    return f"pvp_{binary}"


def generate_500_link() -> str:
    """Генерирует красивую ссылку из 5 и 0 для PvP #500"""
    # Создаем ссылку из символов 5 и 0
    # Например: "pvp_500" или "pvp_5050" или что-то подобное
    return "pvp_5050"  # Можно изменить на другую комбинацию из 5 и 0


class PvPStates(StatesGroup):
    waiting_for_bet = State()
    waiting_for_pvp500_amount = State()


@router.message(F.text == "⚔️ PvP")
async def show_pvp_menu(message: Message, state: FSMContext):
    """Показать меню PvP"""
    # Работает только в личных чатах
    if message.chat.type in ['group', 'supergroup']:
        return
    await state.clear()
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer("Ошибка: пользователь не найден")
        return
    
    text = """⚔️ <b>PvP</b>

Выберите действие:"""
    
    keyboard = get_pvp_menu_keyboard()
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(
    F.text & 
    F.chat.type.in_(["group", "supergroup"])
)
async def handle_text_pvp_command(message: Message):
    """Обработка текстовых команд для создания PvP в группах"""
    try:
        text = message.text.strip().lower()
        user_id = message.from_user.id
        
        # Проверяем, начинается ли сообщение с "pvp" или "пвп"
        if not (text.startswith("pvp") or text.startswith("пвп")):
            return
        
        # Получаем пользователя
        user = await db.get_user(user_id)
        if not user:
            username = message.from_user.username or f"user_{user_id}"
            await db.create_user(user_id, username)
            user = await db.get_user(user_id)
        
        if not user:
            return
        
        balance = user.get("balance", 0.0)
        
        # Парсим команду: "pvp игра игроки ставка" или "пвп игра игроки ставка"
        # Примеры: "pvp боулинг 2 10", "pvp кубы 3 5", "пвп дартс 4 20"
        import re
        
        # Убираем префикс "pvp" или "пвп"
        text_clean = re.sub(r'^(pvp|пвп)\s+', '', text, flags=re.IGNORECASE).strip()
        
        # Словарь игр для PvP
        pvp_games = {
            "боулинг": "bowling",
            "bowling": "bowling",
            "🎳": "bowling",
            "кубы": "dice",
            "кубик": "dice",
            "кубики": "dice",
            "dice": "dice",
            "🎲": "dice",
            "дартс": "dart",
            "дарт": "dart",
            "dart": "dart",
            "🎯": "dart"
        }
        
        game_names = {
            "bowling": "🎳 Боулинг",
            "dice": "🎲 Кубы",
            "dart": "🎯 Дартс"
        }
        
        # Ищем тип игры в тексте
        game_type = None
        for pattern, game in pvp_games.items():
            if pattern in text_clean:
                game_type = game
                # Убираем найденный паттерн из текста
                text_clean = text_clean.replace(pattern, "").strip()
                break
        
        if not game_type:
            await message.reply(
                "❌ <b>Ошибка:</b> Не указан тип игры!\n\n"
                "📋 <b>Формат команды:</b>\n"
                "<code>PvP [игра] [игроки] [ставка]</code>\n\n"
                "🎮 <b>Доступные игры:</b>\n"
                "• Боулинг / Bowling / 🎳\n"
                "• Кубы / Dice / 🎲\n"
                "• Дартс / Dart / 🎯\n\n"
                "📝 <b>Примеры:</b>\n"
                "<code>PvP боулинг 2 10</code>\n"
                "<code>PvP кубы 3 5</code>\n"
                "<code>PvP дартс 4 20</code>",
                parse_mode="HTML"
            )
            return
        
        # Извлекаем числа: количество игроков и ставку
        numbers = re.findall(r'\d+\.?\d*', text_clean)
        
        if len(numbers) < 2:
            await message.reply(
                "❌ <b>Ошибка:</b> Не указаны количество игроков и ставка!\n\n"
                "📋 <b>Формат команды:</b>\n"
                f"<code>PvP {game_names[game_type]} [игроки] [ставка]</code>\n\n"
                "📝 <b>Пример:</b>\n"
                f"<code>PvP {game_names[game_type]} 2 10</code>",
                parse_mode="HTML"
            )
            return
        
        try:
            max_players = int(numbers[0])
            bet_amount = float(numbers[1])
        except (ValueError, IndexError):
            await message.reply("❌ Неверный формат чисел. Используйте: PvP [игра] [игроки] [ставка]")
            return
        
        # Проверяем количество игроков
        if max_players < 2 or max_players > 4:
            await message.reply("❌ Количество игроков должно быть от 2 до 4")
            return
        
        # Проверяем ставку
        if bet_amount < 0.1:
            await message.reply("❌ Минимальная ставка: $0.10")
            return
        
        if bet_amount > balance:
            await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${balance:.2f}")
            return
        
        # Проверяем, не занят ли пользователь другой игрой
        from handlers.games import is_user_busy
        if is_user_busy(user_id):
            await message.reply("⏳ У вас уже идет игра, подождите завершения...")
            return
        
        # Создаем PvP дуэль
        import uuid
        unique_link = f"pvp_{uuid.uuid4().hex[:12]}"
        
        logger.info(
            f"🎮 Создание PvP из текстовой команды в группе: "
            f"user_id={user_id}, game_type={game_type}, "
            f"max_players={max_players}, bet_amount={bet_amount}"
        )
        
        # Списываем ставку
        await db.update_balance(user_id, -bet_amount)
        
        # Создаем дуэль
        duel_id = await db.create_pvp_duel(
            creator_id=user_id,
            game_type=game_type,
            max_players=max_players,
            bet_amount=bet_amount,
            unique_link=unique_link
        )
        
        if not duel_id:
            # Возвращаем баланс, если не удалось создать
            await db.update_balance(user_id, bet_amount)
            await message.reply("❌ Ошибка при создании PvP. Попробуйте позже.")
            return
        
        # Создатель автоматически добавляется как участник в create_pvp_duel
        # Отправляем сообщение в канал
        await start_pvp_game_in_channel(message.bot, duel_id)
        
        # Получаем username бота для формирования ссылки
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username
        duel_link = f"https://t.me/{bot_username}?start={unique_link}"
        
        # Отправляем подтверждение в группу с ссылкой
        game_name = game_names.get(game_type, "Игра")
        await message.reply(
            f"✅ <b>PvP создан!</b>\n\n"
            f"🎮 <b>Игра:</b> {game_name}\n"
            f"👥 <b>Игроков:</b> 1/{max_players}\n"
            f"💰 <b>Ставка:</b> ${bet_amount:.2f}\n"
            f"🔗 <b>ID дуэли:</b> #{duel_id}\n\n"
            f"⏳ <b>Дуэль в ожидании присоединения</b>\n\n"
            f"🔗 <a href=\"{duel_link}\">Ссылка на дуэль</a>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_text_pvp_command: {e}", exc_info=True)


@router.callback_query(F.data == "pvp_menu")
async def pvp_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик меню PvP"""
    await callback.answer()
    await state.clear()
    
    text = """⚔️ <b>PvP</b>

Выберите действие:"""
    
    keyboard = get_pvp_menu_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "pvp_create")
async def pvp_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание PvP - сначала выбор игры"""
    await callback.answer()
    await state.clear()
    
    text = """⚔️ <b>Создать PvP</b>

📋 <b>Шаг 1: Выберите игру (ОБЯЗАТЕЛЬНО)</b>

⚠️ <b>Внимание:</b> Выбор игры обязателен для создания PvP!

Выберите в какой игре вы хотите посоревноваться с другими пользователями:"""
    
    keyboard = get_pvp_game_select_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("pvp_game_"))
async def pvp_select_game(callback: CallbackQuery, state: FSMContext):
    """Выбор игры для PvP"""
    await callback.answer()
    
    game_type = callback.data.replace("pvp_game_", "")
    game_names = {
        "bowling": "🎳 Боулинг",
        "dice": "🎲 Кубы",
        "dart": "🎯 Дартс"
    }
    game_name = game_names.get(game_type, "Игра")
    
    await state.update_data(game_type=game_type)
    
    text = f"""⚔️ <b>Создать PvP</b>

✅ <b>Шаг 1:</b> Игра выбрана - {game_name}

📋 <b>Шаг 2: Выберите количество игроков</b>

Выберите количество игроков (минимум 2, максимум 4):"""
    
    keyboard = get_pvp_players_count_keyboard(game_type=game_type)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("pvp_players_"))
async def pvp_select_players(callback: CallbackQuery, state: FSMContext):
    """Выбор количества игроков"""
    await callback.answer()
    
    players_count = int(callback.data.replace("pvp_players_", ""))
    data = await state.get_data()
    game_type = data.get("game_type")
    
    if not game_type:
        await callback.answer("Ошибка: игра не выбрана", show_alert=True)
        # Возвращаемся к выбору игры
        text = """⚔️ <b>Создать PvP</b>

📋 <b>Шаг 1: Выберите игру (ОБЯЗАТЕЛЬНО)</b>

⚠️ <b>Внимание:</b> Выбор игры обязателен для создания PvP!

Выберите в какой игре вы хотите посоревноваться с другими пользователями:"""
        keyboard = get_pvp_game_select_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    game_names = {
        "bowling": "🎳 Боулинг",
        "dice": "🎲 Кубы",
        "dart": "🎯 Дартс"
    }
    game_name = game_names.get(game_type, "Игра")
    
    await state.update_data(max_players=players_count)
    await state.set_state(PvPStates.waiting_for_bet)
    
    text = f"""⚔️ <b>Создать PvP</b>

✅ <b>Шаг 1:</b> Игра - {game_name}
✅ <b>Шаг 2:</b> Игроков - {players_count}

📋 <b>Шаг 3: Введите сумму ставки</b>

Введите сумму ставки (минимум $0.10):"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к выбору игроков", callback_data=f"pvp_game_{game_type}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(PvPStates.waiting_for_bet)
async def pvp_enter_bet(message: Message, state: FSMContext):
    """Обработка ввода ставки"""
    logger.info(f"🎯 PvP обработчик ввода ставки вызван для пользователя {message.from_user.id}, текст: {message.text}")
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        logger.error(f"❌ Пользователь {user_id} не найден")
        await message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА: игра должна быть выбрана
    data = await state.get_data()
    game_type = data.get("game_type")
    
    if not game_type:
        logger.warning(f"⚠️ Попытка создать PvP без выбора игры для пользователя {user_id}")
        await message.answer(
            "❌ <b>Ошибка: игра не выбрана!</b>\n\n"
            "Пожалуйста, сначала выберите игру для PvP.",
            parse_mode="HTML"
        )
        # Возвращаемся к выбору игры
        text = """⚔️ <b>Создать PvP</b>

📋 <b>Шаг 1: Выберите игру (ОБЯЗАТЕЛЬНО)</b>

⚠️ <b>Внимание:</b> Выбор игры обязателен!

Выберите в какой игре вы хотите посоревноваться с другими пользователями:"""
        keyboard = get_pvp_game_select_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        return
    
    # Проверяем, что это текстовое сообщение
    if not message.text:
        logger.warning(f"⚠️ Сообщение не является текстом")
        await message.answer("❌ Пожалуйста, введите сумму ставки числом")
        return
    
    try:
        bet_text = message.text.strip().lower()
        use_arbuzz = False
        
        # Проверяем, указана ли ставка в арбузах
        arbuzz_keywords = ["арбузов", "арбуз", "ас", "arbuz", "ac", "арбуза", "арбузы"]
        bet_amount = None
        
        # Пытаемся извлечь число и проверить ключевые слова
        import re
        
        # Сначала проверяем, есть ли ключевые слова арбузов в тексте
        has_arbuzz_keyword = any(keyword in bet_text for keyword in arbuzz_keywords)
        
        # Ищем число в тексте (может быть с точкой или запятой, до или после ключевых слов)
        number_match = re.search(r'\d+[.,]?\d*', bet_text)
        if number_match:
            bet_amount = float(number_match.group().replace(",", "."))
            # Если найдено ключевое слово арбузов, используем арбузы
            if has_arbuzz_keyword:
                use_arbuzz = True
        else:
            # Если не найдено число, пробуем просто float
            try:
                bet_amount = float(bet_text.replace(",", "."))
            except ValueError:
                raise ValueError("Не удалось извлечь число из ставки")
        
        logger.info(f"💰 Введенная ставка: {bet_amount:.2f}, в арбузах: {use_arbuzz}")
        
        if bet_amount < 0.1:
            logger.warning(f"⚠️ Ставка слишком мала: {bet_amount:.2f}")
            currency_text = "арбузов" if use_arbuzz else "$"
            await message.answer(f"❌ Минимальная ставка: 0.1 {currency_text}")
            return
        
        # Проверяем баланс в зависимости от валюты
        if use_arbuzz:
            arbuzz_balance = user.get("arbuzz_balance", 0.0)
            if bet_amount > arbuzz_balance:
                logger.warning(f"⚠️ Недостаточно арбузов: баланс {arbuzz_balance:.0f}, нужно {bet_amount:.0f}")
                await message.answer(f"❌ Недостаточно арбузов. Ваш баланс: {arbuzz_balance:.0f} AC")
                return
            # Для арбузов сохраняем информацию, что ставка в арбузах
            # Но в PvP ставки всегда в долларах, поэтому конвертируем 1:1 или используем как есть
            # Пока оставим как есть - арбузы используются как валюта в PvP тоже
            await state.update_data(use_arbuzz=True)
        else:
            if bet_amount > user["balance"]:
                logger.warning(f"⚠️ Недостаточно средств: баланс ${user['balance']:.2f}, нужно ${bet_amount:.2f}")
                await message.answer(f"❌ Недостаточно средств. Ваш баланс: ${user['balance']:.2f}")
                return
        
        data = await state.get_data()
        game_type = data.get("game_type")
        max_players = data.get("max_players")
        use_arbuzz = data.get("use_arbuzz", False)
        logger.info(f"📋 Данные из состояния: game_type={game_type}, max_players={max_players}, use_arbuzz={use_arbuzz}")
        
        if not game_type or not max_players:
            logger.error(f"❌ Данные не найдены в состоянии: game_type={game_type}, max_players={max_players}")
            await message.answer("❌ Ошибка: данные не найдены. Начните заново.")
            await state.clear()
            return
        
        # Списываем ставку в зависимости от валюты
        if use_arbuzz:
            await db.update_arbuzz_balance(user_id, -bet_amount)
            currency_text = f"{bet_amount:.0f} AC"
        else:
            await db.update_balance(user_id, -bet_amount)
            currency_text = f"${bet_amount:.2f}"
        
        # Генерируем уникальную ссылку
        unique_link = f"pvp_{uuid.uuid4().hex[:12]}"
        
        # Создаем дуэль
        logger.info(f"🎮 Создание дуэли: game_type={game_type}, max_players={max_players}, bet_amount={bet_amount}")
        duel_id = await db.create_pvp_duel(
            creator_id=user_id,
            game_type=game_type,
            max_players=max_players,
            bet_amount=bet_amount,
            unique_link=unique_link
        )
        logger.info(f"✅ Дуэль создана с ID: {duel_id}")
        
        # Получаем username бота
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username
        # Формируем ссылку на дуэль
        duel_link = f"https://t.me/{bot_username}?start={unique_link}"
        logger.info(f"🔗 Ссылка на дуэль: {duel_link}")
        
        text = f"""✅ <b>Дуэль создана!</b>

🎮 Игра: {game_type}
👥 Игроков: {max_players}
💰 Ставка: {currency_text}

⏳ <b>Дуэль в ожидании присоединения</b>

🔗 <a href="{duel_link}">Ссылка на дуэль</a>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔗 Открыть канал", url=f"https://t.me/{PVP_CHANNEL_USERNAME}"),
            ],
            [
                InlineKeyboardButton(text="📋 Мои PvP", callback_data="pvp_my_duels"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu"),
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
        
    except ValueError as e:
        logger.error(f"❌ Ошибка при преобразовании ставки: {e}, текст: {message.text}")
        await message.answer("❌ Пожалуйста, введите корректную сумму (например: 10.5)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании дуэли: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при создании дуэли. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data == "pvp_active")
async def pvp_active_duels(callback: CallbackQuery):
    """Показать активные PvP дуэли"""
    await callback.answer()
    
    duels = await db.get_active_pvp_duels()
    
    if not duels:
        text = """📋 <b>Активные PvP</b>

Нет активных дуэлей в ожидании присоединения."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    text = """📋 <b>Активные PvP</b>

Выберите дуэль для присоединения:

"""
    
    game_emojis = {"bowling": "🎳", "dice": "🎲", "dart": "🎯"}
    
    keyboard_buttons = []
    for duel in duels[:10]:  # Максимум 10
        game_emoji = game_emojis.get(duel["game_type"], "🎮")
        current_players = duel.get("current_players", 1)
        
        text += f"{game_emoji} Дуэль #{duel['id']} - {current_players}/{duel['max_players']} игроков - ${duel['bet_amount']:.2f}\n"
        button_text = f"{game_emoji} #{duel['id']} ({current_players}/{duel['max_players']})"
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"pvp_join_{duel['id']}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("pvp_join_"))
async def pvp_join_duel(callback: CallbackQuery, state: FSMContext):
    """Присоединиться к дуэли"""
    await callback.answer()
    
    duel_id = int(callback.data.replace("pvp_join_", ""))
    user_id = callback.from_user.id
    
    # Получаем информацию о дуэли
    duel = await db.get_pvp_duel(duel_id=duel_id)
    if not duel:
        await callback.answer("❌ Дуэль не найдена", show_alert=True)
        return
    
    # Проверяем баланс
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Проверяем, не присоединился ли уже
    participants = await db.get_pvp_participants(duel_id)
    if any(p["user_id"] == user_id for p in participants):
        await callback.answer("❌ Вы уже присоединились к этой дуэли", show_alert=True)
        return
    
    # Стандартный режим
    if user["balance"] < duel["bet_amount"]:
        await callback.answer(f"❌ Недостаточно средств. Нужно: ${duel['bet_amount']:.2f}", show_alert=True)
        return
    
    # Списываем ставку
    await db.update_balance(user_id, -duel["bet_amount"])
    
    # Присоединяемся
    success = await db.join_pvp_duel(duel_id, user_id)
    
    if not success:
        # Возвращаем деньги если не удалось присоединиться
        await db.update_balance(user_id, duel["bet_amount"])
        await callback.answer("❌ Не удалось присоединиться к дуэли", show_alert=True)
        return
    
    # Получаем обновленную информацию о дуэли
    duel = await db.get_pvp_duel(duel_id=duel_id)
    participants = await db.get_pvp_participants(duel_id)
    
    # Формируем ссылку
    # Получаем username бота
    bot_info = await callback.message.bot.get_me()
    bot_username = bot_info.username
    duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
    
    if len(participants) >= duel["max_players"]:
        # Дуэль заполнена, запускаем игру
        text = f"""✅ <b>Вы присоединились к дуэли!</b>

🎮 Игра: {duel['game_type']}
👥 Игроков: {len(participants)}/{duel['max_players']}
💰 Ставка: ${duel['bet_amount']:.2f}

🎉 <b>Дуэль заполнена! Игра начинается...</b>

🔗 <a href="{duel_link}">Ссылка на дуэль</a>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔗 Открыть канал", url=f"https://t.me/{PVP_CHANNEL_USERNAME}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_active"),
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        # Запускаем игру в канале
        await start_pvp_game_in_channel(callback.bot, duel_id)
    else:
        text = f"""✅ <b>Вы присоединились к дуэли!</b>

🎮 Игра: {duel['game_type']}
👥 Игроков: {len(participants)}/{duel['max_players']}
💰 Ставка: ${duel['bet_amount']:.2f}

⏳ <b>Ожидание других игроков...</b>

🔗 <a href="{duel_link}">Ссылка на дуэль</a>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔗 Открыть канал", url=f"https://t.me/{PVP_CHANNEL_USERNAME}"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_active"),
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "pvp_my_duels")
async def pvp_my_duels(callback: CallbackQuery):
    """Показать мои PvP дуэли (только активные)"""
    await callback.answer()
    
    user_id = callback.from_user.id
    # Получаем только активные дуэли (waiting, ready, active)
    all_duels = await db.get_user_pvp_duels(user_id)
    active_duels = [d for d in all_duels if d.get("status") in ["waiting", "ready", "active"]]
    
    if not active_duels:
        text = """📋 <b>Мои PvP</b>

У вас пока нет активных дуэлей."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    keyboard = get_pvp_my_duels_keyboard(active_duels)
    text = f"""📋 <b>Мои PvP</b>

Активных дуэлей: {len(active_duels)}

Выберите дуэль:"""
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


async def _pvp_show_duel_internal(callback: CallbackQuery, duel_id: int):
    """Внутренняя функция для отображения информации о дуэли"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    duel = await db.get_pvp_duel(duel_id=duel_id)
    if not duel:
        await callback.answer("❌ Дуэль не найдена", show_alert=True)
        return
    
    participants = await db.get_pvp_participants(duel_id)
    is_creator = duel["creator_id"] == user_id
    
    game_emojis = {"bowling": "🎳", "dice": "🎲", "dart": "🎯"}
    game_emoji = game_emojis.get(duel["game_type"], "🎮")
    
    status_texts = {
        "waiting": "⏳ Ожидание присоединения",
        "ready": "✅ Готова к запуску",
        "active": "🎮 Игра идет",
        "finished": "🏆 Завершена",
        "cancelled": "❌ Отменена"
    }
    status_text = status_texts.get(duel["status"], duel["status"])
    
    # Вычисляем выигрыш (с комиссией 10%)
    total_pot = duel["total_pot"]
    commission = total_pot * PVP_COMMISSION
    win_amount = total_pot - commission
    
    duel_mode = duel.get("duel_mode", "standard")
    
    text = f"""⚔️ <b>Дуэль #{duel_id}</b>

📊 <b>СТАТИСТИКА:</b>

{game_emoji} <b>Игра:</b> {duel['game_type']}
👥 <b>Игроков:</b> {len(participants)}/{duel['max_players']}"""
    
    text += f"\n💰 <b>Ставка:</b> ${duel['bet_amount']:.2f}"
    
    text += f"\n🏆 <b>Банк:</b> ${duel['total_pot']:.2f}"
    text += f"\n📊 <b>Статус:</b> {status_text}"

    text += f"\n\n<b>Участники:</b>\n"
    
    # Сортируем участников по результату
    participants_sorted = sorted(participants, key=lambda p: p.get("dice_result", 0) or 0, reverse=True)
    
    for i, p in enumerate(participants_sorted, 1):
        username = p.get("username") or f"ID{p['user_id']}"
        if p["user_id"] == duel["creator_id"]:
            username += " 👑"
        
        # Для обычных PvP показываем результат кубика
        dice_result = p.get("dice_result")
        if dice_result:
            text += f"{i}. {username} - 🎲 {dice_result}\n"
        else:
            text += f"{i}. {username}\n"
    
    if duel["status"] == "finished" and duel["winner_id"]:
        winner = await db.get_user(duel["winner_id"])
        winner_name = winner.get("username") if winner else f"ID{duel['winner_id']}"
        winner_result = next((p.get("dice_result", 0) or 0 for p in participants if p["user_id"] == duel["winner_id"]), 0)
        
        text += f"\n🏆 <b>Победитель:</b> {winner_name} (🎲 {winner_result})"
        text += f"\n💰 <b>Выигрыш:</b> ${win_amount:.2f}"
        text += f"\n📉 <b>Комиссия:</b> ${commission:.2f} (10%)"
    
    # Получаем username бота
    bot_info = await callback.message.bot.get_me()
    bot_username = bot_info.username
    duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔗 Ссылка", url=duel_link),
        ],
    ])
    
    # Добавляем кнопку "Сыграть с ботом" если дуэль в ожидании и пользователь участник
    is_participant = any(p["user_id"] == user_id for p in participants)
    if duel["status"] == "waiting" and is_participant:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🤖 Сыграть с ботом", callback_data=f"pvp_play_bot_{duel_id}"),
        ])
    
    if is_creator and duel["status"] in ["waiting", "ready"]:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"pvp_cancel_{duel_id}"),
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_my_duels"),
    ])
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("pvp_show_"))
async def pvp_show_duel_from_callback(callback: CallbackQuery):
    """Показать информацию о дуэли из callback с pvp_show_"""
    duel_id = int(callback.data.replace("pvp_show_", ""))
    await _pvp_show_duel_internal(callback, duel_id)


@router.callback_query(F.data.startswith("pvp_duel_"))
async def pvp_show_duel(callback: CallbackQuery):
    """Показать информацию о дуэли"""
    duel_id = int(callback.data.replace("pvp_duel_", ""))
    await _pvp_show_duel_internal(callback, duel_id)


@router.callback_query(F.data.startswith("pvp_cancel_"))
async def pvp_cancel_duel(callback: CallbackQuery):
    """Отменить дуэль"""
    await callback.answer()
    
    duel_id = int(callback.data.replace("pvp_cancel_", ""))
    user_id = callback.from_user.id
    
    # Отменяем дуэль
    success = await db.cancel_pvp_duel(duel_id, user_id)
    
    if not success:
        await callback.answer("❌ Не удалось отменить дуэль", show_alert=True)
        return
    
    # Возвращаем деньги всем участникам
    duel = await db.get_pvp_duel(duel_id=duel_id)
    participants = await db.get_pvp_participants(duel_id)
    
    for participant in participants:
        bet_amount = duel["bet_amount"]
        await db.update_balance(participant["user_id"], bet_amount)
        try:
            await callback.bot.send_message(
                participant["user_id"],
                f"❌ Дуэль #{duel_id} была отменена создателем. Ваша ставка ${bet_amount:.2f} возвращена."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления об отмене: {e}")
    
    await callback.answer("✅ Дуэль отменена, деньги возвращены участникам")
    
    # Обновляем сообщение
    await _pvp_show_duel_internal(callback, duel_id)


@router.callback_query(F.data.startswith("pvp_play_bot_"))
async def pvp_play_with_bot(callback: CallbackQuery):
    """Игра с ботом в PvP - запускаем сразу без комиссии"""
    await callback.answer("✅ Игра с ботом запускается...")
    
    duel_id = int(callback.data.replace("pvp_play_bot_", ""))
    user_id = callback.from_user.id
    
    # Получаем информацию о дуэли
    duel = await db.get_pvp_duel(duel_id=duel_id)
    if not duel:
        await callback.answer("❌ Дуэль не найдена", show_alert=True)
        return
    
    # Проверяем статус
    if duel["status"] != "waiting":
        await callback.answer("❌ Дуэль уже началась или завершена", show_alert=True)
        return
    
    # Проверяем, является ли пользователь участником
    participants = await db.get_pvp_participants(duel_id)
    is_participant = any(p["user_id"] == user_id for p in participants)
    if not is_participant:
        await callback.answer("❌ Вы не являетесь участником этой дуэли", show_alert=True)
        return
    
    # Создаем бота-соперника (используем ID 0 как системный)
    bot_user_id = 0
    
    # Проверяем, есть ли системный пользователь
    bot_user = await db.get_user(bot_user_id)
    if not bot_user:
        await db.create_user(bot_user_id, "Bot")
    
    # Добавляем бота как участника (если еще не добавлен)
    bot_is_participant = any(p["user_id"] == bot_user_id for p in participants)
    if not bot_is_participant:
        # Добавляем бота как участника
        position = len(participants) + 1
        async with aiosqlite.connect(db.db_path) as database:
            await database.execute("""
                INSERT INTO pvp_participants (duel_id, user_id, position)
                VALUES (?, ?, ?)
            """, (duel_id, bot_user_id, position))
            
            # Обновляем общий банк (бот не платит ставку, так как это игра с ботом)
            await database.execute("""
                UPDATE pvp_duels SET total_pot = total_pot + ? WHERE id = ?
            """, (duel["bet_amount"], duel_id))
            await database.commit()
        
        # Обновляем статус дуэли на ready, если заполнена
        updated_participants = await db.get_pvp_participants(duel_id)
        if len(updated_participants) >= duel["max_players"]:
            async with aiosqlite.connect(db.db_path) as database:
                await database.execute("""
                    UPDATE pvp_duels SET status = 'ready', started_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (duel_id,))
                await database.commit()
    
    # Запускаем игру сразу
    await start_pvp_game_in_channel(callback.bot, duel_id)


@router.message(F.text.startswith("/start pvp_"))
async def pvp_join_via_link(message: Message, state: FSMContext):
    """Присоединение к дуэли по ссылке"""
    logger.info(f"🔵 PvP обработчик /start pvp_ вызван: {message.text}")
    unique_link = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    if not unique_link:
        logger.warning("⚠️ PvP обработчик: unique_link не найден")
        return
    
    duel = await db.get_pvp_duel(unique_link=unique_link)
    if not duel:
        await message.reply("❌ Дуэль не найдена или уже завершена")
        return
    
    duel_id = duel["id"]
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.reply("Ошибка: пользователь не найден")
        return
    
    # Специальная логика для PvP #500
    if duel_id == 500:
        await handle_pvp_500_join(message, duel, user_id, user, state)
        return
    
    # Проверяем статус
    if duel["status"] == "finished":
        participants = await db.get_pvp_participants(duel_id)
        winner = await db.get_user(duel["winner_id"]) if duel["winner_id"] else None
        winner_name = winner.get("username") if winner else f"ID{duel['winner_id']}"
        
        text = f"""🏆 <b>Дуэль #{duel_id} завершена</b>

🏆 <b>Победитель:</b> {winner_name}
💰 <b>Выигрыш:</b> ${duel['total_pot'] * (1 - PVP_COMMISSION):.2f}

<b>Участники:</b>
"""
        for i, p in enumerate(participants, 1):
            username = p.get("username") or f"ID{p['user_id']}"
            text += f"{i}. {username}\n"
        
        await message.reply(text, parse_mode="HTML")
        return
    
    if duel["status"] == "cancelled":
        await message.reply("❌ Эта дуэль была отменена")
        return
    
    
    # Стандартный режим
    # Проверяем баланс
    if user["balance"] < duel["bet_amount"]:
        await message.reply(f"❌ Недостаточно средств. Нужно: ${duel['bet_amount']:.2f}")
        return
    
    # Проверяем, не присоединился ли уже
    participants = await db.get_pvp_participants(duel_id)
    if any(p["user_id"] == user_id for p in participants):
        await message.reply("❌ Вы уже присоединились к этой дуэли")
        return
    
    # Списываем ставку
    await db.update_balance(user_id, -duel["bet_amount"])
    
    # Присоединяемся
    success = await db.join_pvp_duel(duel_id, user_id)
    
    if not success:
        # Возвращаем деньги
        await db.update_balance(user_id, duel["bet_amount"])
        await message.reply("❌ Не удалось присоединиться к дуэли")
        return
    
    # Получаем обновленную информацию
    duel = await db.get_pvp_duel(duel_id=duel_id)
    participants = await db.get_pvp_participants(duel_id)
    
    if len(participants) >= duel["max_players"]:
        # Дуэль заполнена, запускаем игру
        await message.reply(
            f"✅ Вы присоединились! Дуэль заполнена, игра начинается...\n\n"
            f"🔗 <a href='https://t.me/{PVP_CHANNEL_USERNAME}'>Открыть канал</a>",
            parse_mode="HTML"
        )
        await start_pvp_game_in_channel(message.bot, duel_id)
    else:
        await message.reply(
            f"✅ Вы присоединились к дуэли!\n\n"
            f"👥 Игроков: {len(participants)}/{duel['max_players']}\n"
            f"⏳ Ожидание других игроков...\n\n"
            f"🔗 <a href='https://t.me/{PVP_CHANNEL_USERNAME}'>Открыть канал</a>",
            parse_mode="HTML"
        )


async def start_pvp_game_in_channel(bot: Bot, duel_id: int):
    """Запустить игру PvP в канале"""
    try:
        duel = await db.get_pvp_duel(duel_id=duel_id)
        if not duel:
            logger.error(f"Дуэль {duel_id} не найдена")
            return
        
        # Специальная логика для PvP #500 - обрабатывается отдельно
        if duel_id == 500:
            tickets_count = await db.get_pvp_tickets_count(duel_id)
            if tickets_count < 128:
                logger.error(f"Недостаточно билетов для дуэли {duel_id}: {tickets_count}/128")
                return
            # Для #500 используем отдельную функцию
            await handle_pvp_500_game(bot, duel_id, duel)
            return
        
        participants = await db.get_pvp_participants(duel_id)
        
        # Для PvP #100 запускаем даже если участников меньше максимума (но есть хотя бы один)
        if duel_id == 100:
            if len(participants) == 0:
                logger.error(f"Нет участников для дуэли {duel_id}")
                return
        # Для остальных дуэлей требуется полное заполнение или статус ready (для игры с ботом)
        else:
            # Если статус ready, значит дуэль готова к запуску (например, с ботом)
            if duel.get("status") == "ready":
                if len(participants) == 0:
                    logger.error(f"Нет участников для дуэли {duel_id}")
                    return
            elif len(participants) < duel["max_players"]:
                logger.error(f"Недостаточно участников для дуэли {duel_id}")
                return
        
        # Обновляем статус
        await db.start_pvp_duel(duel_id, 0)  # channel_message_id будет обновлен после отправки
        
        # Получаем username бота один раз
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Переменная для хранения сообщения со слотом (для PvP #100)
        slot_message = None
        
        # Специальная логика для PvP #100 - используем слоты
        if duel_id == 100:
            # Для PvP #100: кидается ОДИН слот для всех, выигрывает участник с номером = значению
            game_emoji = "🎰"
            
            # Формируем ссылку на дуэль
            duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
            
            # Создаем кнопку со ссылкой на PvP
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=f"#{duel_id}",
                    url=duel_link
                )
            ]])
            
            # Кидаем ОДИН слот для всех участников
            max_attempts = 10
            attempt = 0
            
            while attempt < max_attempts:
                attempt += 1
                
                # Удаляем предыдущее сообщение, если это перекид
                if attempt > 1 and slot_message:
                    try:
                        await bot.delete_message(chat_id=PVP_CHANNEL_ID, message_id=slot_message.message_id)
                        await asyncio.sleep(2)
                    except Exception as e:
                        logger.error(f"Ошибка при удалении сообщения: {e}")
                
                # Отправляем один слот
                slot_message = await bot.send_dice(
                    chat_id=PVP_CHANNEL_ID,
                    emoji=game_emoji,
                    reply_markup=keyboard
                )
                
                # Ждем результата
                await asyncio.sleep(4)
                
                # Получаем результат
                slot_value = slot_message.dice.value
                
                logger.info(f"PvP #100: Выпало значение {slot_value}")
                
                # Если значение 26-64 - перекид
                if slot_value > 25:
                    logger.info(f"PvP #100: Значение {slot_value} > 25, перекидываем")
                    continue
                
                # Если значение 1-25 - определяем победителя по номеру позиции
                winner_position = slot_value
                
                # Находим участника с этой позицией
                winner_participant = None
                for participant in participants:
                    if participant.get("position") == winner_position:
                        winner_participant = participant
                        break
                
                if winner_participant:
                    winner_id = winner_participant["user_id"]
                    # Сохраняем результат для победителя
                    await db.update_participant_result(duel_id, winner_id, slot_value, game_emoji)
                    logger.info(f"PvP #100: Победитель определен - участник #{winner_position} (user_id: {winner_id})")
                    break
                else:
                    logger.warning(f"PvP #100: Участник с позицией {winner_position} не найден, перекидываем")
                    continue
            else:
                # Если не удалось определить победителя за max_attempts попыток
                logger.error(f"PvP #100: Не удалось определить победителя после {max_attempts} попыток")
                # Берем первого участника как победителя
                winner_id = participants[0]["user_id"]
                await db.update_participant_result(duel_id, winner_id, slot_value if slot_message else 0, game_emoji)
        else:
            # Обычная логика для других PvP
            # Определяем эмодзи для игры
            game_emojis = {
                "bowling": "🎳",
                "dice": "🎲",
                "dart": "🎯"
            }
            game_emoji = game_emojis.get(duel["game_type"], "🎮")
            
            # Словарь для хранения сообщений с кубиками (user_id -> message_id)
            dice_messages = {}
            
            # Функция для отправки кубиков и определения победителя
            async def roll_dice_and_find_winner():
                """Бросает кубики для всех участников и определяет победителя"""
                for participant in participants:
                    user = await db.get_user(participant["user_id"])
                    
                    # Специальная обработка для бота (user_id == 0)
                    if participant["user_id"] == 0:
                        username = "ArbuzCas"
                        user_url = f"https://t.me/arbuzcas_bot"
                    else:
                        username = user.get("username") if user else f"ID{participant['user_id']}"
                        # Формируем ссылку на пользователя
                        user_url = f"https://t.me/{username}" if user and user.get("username") else f"tg://user?id={participant['user_id']}"
                    
                    # Формируем ссылку на дуэль
                    duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
                    
                    # Создаем кнопки: первая строка - ссылка на пользователя, вторая строка - ссылка на дуэль
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=f"👤 {username}",
                                url=user_url
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=f"#{duel_id}",
                                url=duel_link
                            )
                        ]
                    ])
                    
                    # Отправляем кубик с кнопкой
                    dice_message = await bot.send_dice(
                        chat_id=PVP_CHANNEL_ID,
                        emoji=game_emoji,
                        reply_markup=keyboard
                    )
                    
                    # Сохраняем message_id для отправки пользователю
                    dice_messages[participant["user_id"]] = dice_message.message_id
                    
                    # Ждем результата кубика
                    await asyncio.sleep(4)
                    
                    # Получаем результат
                    dice_result = dice_message.dice.value
                    
                    # Обновляем результат участника
                    await db.update_participant_result(duel_id, participant["user_id"], dice_result, game_emoji)
                
                # Получаем результаты всех участников
                participants_with_results = await db.get_pvp_participants(duel_id)
                results = [(p["user_id"], p.get("dice_result", 0) or 0) for p in participants_with_results]
                
                # Находим максимальное значение
                max_result = max(results, key=lambda x: x[1])[1]
                
                # Находим всех участников с максимальным результатом
                winners = [p for p in results if p[1] == max_result]
                
                # Проверяем, есть ли ничья среди максимальных значений
                if len(winners) > 1:
                    # Ничья среди максимальных - перекидываем все
                    logger.info(f"Ничья среди максимальных значений ({max_result}), перекидываем все кубики")
                    return None  # Возвращаем None, чтобы перекинуть все
                
                # Есть единственный победитель
                winner_id = winners[0][0]
                return winner_id
            
            # Бросаем кубики до тех пор, пока не определится победитель
            winner_id = None
            max_attempts_regular = 10  # Защита от бесконечного цикла
            attempt_regular = 0
            
            while winner_id is None and attempt_regular < max_attempts_regular:
                attempt_regular += 1
                # Очищаем предыдущие результаты перед новым броском
                if attempt_regular > 1:
                    # Небольшая задержка перед перекидыванием
                    await asyncio.sleep(2)
                    
                    # Удаляем предыдущие сообщения с кубиками
                    for user_id, msg_id in dice_messages.items():
                        try:
                            await bot.delete_message(chat_id=PVP_CHANNEL_ID, message_id=msg_id)
                        except Exception as e:
                            logger.error(f"Ошибка при удалении сообщения {msg_id}: {e}")
                    dice_messages.clear()
                    
                    # Очищаем результаты участников в БД
                    for participant in participants:
                        await db.update_participant_result(duel_id, participant["user_id"], None, game_emoji)
                
                winner_id = await roll_dice_and_find_winner()
            
            if winner_id is None:
                logger.error(f"Не удалось определить победителя после {max_attempts_regular} попыток")
                # В случае ошибки берем первого участника
                winner_id = participants[0]["user_id"]
        
        # Обновляем дуэль с победителем (winner_id уже определен выше)
        await db.finish_pvp_duel(duel_id, winner_id)
        
        # Проверяем, если это дуэль #99, создаем автоматически #100
        if duel_id == 99:
            await create_special_pvp_100(bot)
        
        # Проверяем, если это дуэль #400, отправляем рассылку о предстоящей #500
        if duel_id == 400:
            await send_pvp_500_announcement_400(bot)
        
        # Проверяем, если это дуэль #499, отправляем рассылку о запуске #500
        if duel_id == 499:
            await send_pvp_500_announcement_499(bot)
        
        # Вычисляем выигрыш (с комиссией 10%)
        total_pot = duel["total_pot"]
        commission = total_pot * PVP_COMMISSION
        win_amount = total_pot - commission
        
        # Начисляем выигрыш победителю
        await db.update_balance(winner_id, win_amount)
        
        # Получаем информацию о победителе
        winner_user = await db.get_user(winner_id)
        winner_name = winner_user.get("username") if winner_user else f"ID{winner_id}"
        
        # Получаем финальные результаты
        participants_with_results = await db.get_pvp_participants(duel_id)
        winner_result = next((p.get("dice_result", 0) or 0 for p in participants_with_results if p["user_id"] == winner_id), 0)
        
        # Для PvP #100 отправляем сообщение в канал о победителе
        if duel_id == 100:
            try:
                # Находим позицию победителя
                winner_position = next((p.get("position", 0) for p in participants_with_results if p["user_id"] == winner_id), 0)
                
                # Формируем ссылку на слот
                slot_link = f"https://t.me/{PVP_CHANNEL_USERNAME}/{slot_message.message_id}" if slot_message else f"https://t.me/{PVP_CHANNEL_USERNAME}"
                
                # Формируем текст сообщения
                winner_text = f"""🏆 <b>PvP #100 ЗАВЕРШЕНА!</b>

🎰 <b>Выпало значение:</b> <code>{winner_result}</code>

🎯 <b>Победитель:</b> Участник #{winner_position}
👤 <b>Имя:</b> {winner_name}

💰 <b>Выигрыш:</b> ${win_amount:.2f}

🔗 <a href="{slot_link}">Смотреть слот</a>"""
                
                # Отправляем сообщение в канал
                await bot.send_message(
                    chat_id=PVP_CHANNEL_ID,
                    text=winner_text,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Сообщение о победителе PvP #100 отправлено в канал")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения о победителе в канал: {e}", exc_info=True)
        
        # Отправляем личные сообщения каждому участнику
        for participant in participants:
            try:
                user = await db.get_user(participant["user_id"])
                username = user.get("username") if user else f"ID{participant['user_id']}"
                participant_result = next((p.get("dice_result", 0) or 0 for p in participants_with_results if p["user_id"] == participant["user_id"]), 0)
                
                # Для обычных PvP используем кубики
                dice_message_id = dice_messages.get(participant["user_id"])
                if dice_message_id:
                    dice_link = f"https://t.me/{PVP_CHANNEL_USERNAME}/{dice_message_id}"
                else:
                    dice_link = f"https://t.me/{PVP_CHANNEL_USERNAME}"
                
                # Формируем текст сообщения
                if participant["user_id"] == winner_id:
                    message_text = (
                        f"🏆 <b>Поздравляем! Вы победили в PvP #{duel_id}!</b>\n\n"
                        f"🎮 <b>Игра:</b> {duel['game_type']}\n"
                        f"🎲 <b>Ваш результат:</b> {participant_result}\n"
                        f"💰 <b>Выигрыш:</b> ${win_amount:.2f}\n\n"
                        f"🔗 <a href='{dice_link}'>Ваш кубик</a>"
                    )
                else:
                    message_text = (
                        f"⚔️ <b>PvP #{duel_id} завершена</b>\n\n"
                        f"🎮 <b>Игра:</b> {duel['game_type']}\n"
                        f"🎲 <b>Ваш результат:</b> {participant_result}\n"
                        f"🏆 <b>Победитель:</b> {winner_name} ({winner_result})\n"
                        f"💰 <b>Выигрыш:</b> ${win_amount:.2f}\n\n"
                        f"🔗 <a href='{dice_link}'>Ваш кубик</a>"
                    )
                
                await bot.send_message(
                    participant["user_id"],
                    message_text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления участнику {participant['user_id']}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка при запуске игры в канале: {e}", exc_info=True)


async def create_special_pvp_100(bot: Bot):
    """Создать специальный PvP #100 автоматически после завершения #99"""
    try:
        # Проверяем, не создана ли уже дуэль #100
        existing_duel = await db.get_pvp_duel(duel_id=100)
        if existing_duel:
            logger.info("PvP #100 уже существует")
            return
        
        # Генерируем красивую ссылку из 1 и 0
        unique_link = generate_binary_link(100)
        
        # Параметры для PvP #100
        game_type = "dice"  # Используем кубики
        max_players = 25
        bet_amount = 0.1
        
        # Создаем дуэль с системным пользователем (можно использовать ID 0 или специальный)
        # Но лучше использовать первого пользователя из БД или специальный ID
        # Для автоматического создания используем ID 0 (системный)
        creator_id = 0
        
        # Проверяем, есть ли системный пользователь, если нет - создаем
        system_user = await db.get_user(0)
        if not system_user:
            await db.create_user(0, "system")
        
        # Создаем дуэль с конкретным ID=100
        try:
            duel_id = await db.create_pvp_duel(
                creator_id=creator_id,
                game_type=game_type,
                max_players=max_players,
                bet_amount=bet_amount,
                unique_link=unique_link,
                duel_id=100  # Указываем конкретный ID
            )
        except Exception as e:
            # Если не удалось создать с ID=100 (возможно, ID занят), создаем с автоматическим ID
            logger.warning(f"Не удалось создать PvP с ID=100, создаю с автоматическим ID: {e}")
            duel_id = await db.create_pvp_duel(
                creator_id=creator_id,
                game_type=game_type,
                max_players=max_players,
                bet_amount=bet_amount,
                unique_link=unique_link
            )
        
        if not duel_id:
            logger.error("Не удалось создать PvP #100")
            return
        
        logger.info(f"✅ Создан специальный PvP с ID: {duel_id}")
        
        # Отправляем рассылку в каналы
        await send_pvp_100_announcement(bot, duel_id, unique_link)
        
    except Exception as e:
        logger.error(f"Ошибка при создании специального PvP #100: {e}", exc_info=True)


async def send_pvp_100_announcement(bot: Bot, duel_id: int, unique_link: str):
    """Отправить рассылку о запуске PvP #100 в каналы"""
    try:
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Формируем ссылку на дуэль
        duel_link = f"https://t.me/{bot_username}?start={unique_link}"
        
        # Формируем текст сообщения
        text = f"""<b>PvP #{duel_id} ЗАПУЩЕНО!</b>

<i>PvP #{duel_id} создано автоматически ботом и уже доступно для каждого пользователя</i>

💰 <b>Ставка</b> - <b>0.1$</b>

👥 <b>Количество игроков</b> - <b>25!</b>

🏆 <b>ПОБЕДИТЕЛЬ ПОЛУЧАЕТ НА БАЛАНС 2.5$</b>"""
        
        # Создаем кнопку со ссылкой на дуэль
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"🎮 Присоединиться к PvP #{duel_id}",
                url=duel_link
            )
        ]])
        
        # Отправляем в канал @arbuzikgame
        try:
            await bot.send_message(
                chat_id=ARBUZIK_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка отправлена в {ARBUZIK_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {ARBUZIK_CHANNEL}: {e}")
        
        # Отправляем в канал @cryptogifts_ru
        try:
            await bot.send_message(
                chat_id=CRYPTOGIFTS_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка отправлена в {CRYPTOGIFTS_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {CRYPTOGIFTS_CHANNEL}: {e}")
        
        # Рассылаем всем пользователям бота
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку PvP #{duel_id} всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:  # Пропускаем системного пользователя
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    # Логируем только каждую 10-ю ошибку, чтобы не засорять логи
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке рассылки о PvP #100: {e}", exc_info=True)


async def send_pvp_100_reminder(bot: Bot):
    """Отправить напоминание о PvP #100 в каналы и всем пользователям при запуске бота"""
    try:
        # Проверяем, существует ли PvP #100
        duel = await db.get_pvp_duel(duel_id=100)
        if not duel:
            logger.info("PvP #100 не найдено, пропускаем рассылку напоминания")
            return
        
        # Проверяем статус дуэли - рассылаем только если она еще не завершена
        if duel.get("status") in ["finished", "cancelled"]:
            logger.info("PvP #100 уже завершена или отменена, пропускаем рассылку")
            return
        
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Формируем ссылку на дуэль
        duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
        
        # Формируем текст сообщения с правилами
        text = f"""🎉 <b>НАПОМИНАНИЕ О PvP #100!</b>

🎊 <b>Юбилейная дуэль уже доступна!</b>

━━━━━━━━━━━━━━━━━━━━

🎰 <b>СПЕЦИАЛЬНЫЙ ФОРМАТ ИГРЫ:</b>

<b>Правила PvP #100:</b>
• Кидается <b>ОДИН слот 🎰</b> для всех участников
• Если выпало <b>1-25</b> - выигрывает участник с <b>номером позиции = значению</b> ✅
• Если выпало <b>26-64</b> - перекид 🔄
• Например: выпало <b>15</b> → побеждает участник <b>#15</b>!

━━━━━━━━━━━━━━━━━━━━

💰 <b>Ставка:</b> <code>0.1$</code>
👥 <b>Количество игроков:</b> <code>25</code>
🏆 <b>Призовой фонд:</b> <code>2.5$</code>

━━━━━━━━━━━━━━━━━━━━

⚡ <b>Успейте присоединиться!</b>
🎯 <b>Только для первых 25 участников!</b>"""
        
        # Создаем кнопку со ссылкой на дуэль
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"🎮 Присоединиться к PvP #100",
                url=duel_link
            )
        ]])
        
        # Отправляем в канал @arbuzikgame
        try:
            await bot.send_message(
                chat_id=ARBUZIK_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Напоминание отправлено в {ARBUZIK_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания в {ARBUZIK_CHANNEL}: {e}")
        
        # Отправляем в канал @cryptogifts_ru
        try:
            await bot.send_message(
                chat_id=CRYPTOGIFTS_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Напоминание отправлено в {CRYPTOGIFTS_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания в {CRYPTOGIFTS_CHANNEL}: {e}")
        
        # Рассылаем всем пользователям бота
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку напоминания о PvP #100 всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:  # Пропускаем системного пользователя
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    # Логируем только каждую 10-ю ошибку, чтобы не засорять логи
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка напоминания завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке напоминания всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания о PvP #100: {e}", exc_info=True)


async def send_pvp_100_10min_reminder(bot: Bot):
    """Отправить напоминание за 10 минут до конца дуэли #100 в 22:55"""
    try:
        # Проверяем, существует ли PvP #100
        duel = await db.get_pvp_duel(duel_id=100)
        if not duel:
            logger.info("PvP #100 не найдено, пропускаем рассылку напоминания")
            return
        
        # Проверяем статус дуэли - рассылаем только если она еще не завершена
        if duel.get("status") in ["finished", "cancelled"]:
            logger.info("PvP #100 уже завершена или отменена, пропускаем рассылку")
            return
        
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Формируем ссылку на дуэль
        duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
        
        # Получаем количество участников
        participants = await db.get_pvp_participants(100)
        current_players = len(participants)
        max_players = duel.get("max_players", 25)
        
        # Формируем красивое сообщение с HTML
        text = f"""⏰ <b>ДО КОНЦА ДУЭЛИ #100 ОСТАЛОСЬ 10 МИНУТ!</b>

🎯 <b>Участвуй скорее!</b>

━━━━━━━━━━━━━━━━━━━━

⚔️ <b>Дуэль #{duel['id']}</b>
👥 <b>Участников:</b> {current_players}/{max_players}
💰 <b>Ставка:</b> <code>${duel['bet_amount']:.2f}</code>
🏆 <b>Призовой фонд:</b> <code>${duel['total_pot']:.2f}</code>

━━━━━━━━━━━━━━━━━━━━

🎰 <b>Специальный формат:</b>
• Кидается <b>ОДИН слот</b> для всех
• Выигрывает участник с номером = значению слота
• Если выпало 26-64 - перекид

━━━━━━━━━━━━━━━━━━━━

⚡ <b>Не упусти свой шанс!</b>
🎮 <b>Присоединяйся прямо сейчас!</b>"""
        
        # Создаем кнопку со ссылкой на дуэль
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎮 Присоединиться к дуэли #100",
                url=duel_link
            )
        ]])
        
        # Отправляем в канал @arbuzikgame
        try:
            await bot.send_message(
                chat_id=ARBUZIK_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Напоминание за 10 минут отправлено в {ARBUZIK_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания в {ARBUZIK_CHANNEL}: {e}")
        
        # Отправляем в канал @cryptogifts_ru
        try:
            await bot.send_message(
                chat_id=CRYPTOGIFTS_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Напоминание за 10 минут отправлено в {CRYPTOGIFTS_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания в {CRYPTOGIFTS_CHANNEL}: {e}")
        
        # Рассылаем всем пользователям бота
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку напоминания за 10 минут всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:  # Пропускаем системного пользователя
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    # Логируем только каждую 10-ю ошибку, чтобы не засорять логи
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка напоминания за 10 минут завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке напоминания всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания за 10 минут о PvP #100: {e}", exc_info=True)


async def auto_finish_pvp_100(bot: Bot):
    """Автоматически подвести итоги дуэли #100 в 23:05"""
    try:
        # Проверяем, существует ли PvP #100
        duel = await db.get_pvp_duel(duel_id=100)
        if not duel:
            logger.info("PvP #100 не найдено, пропускаем автоматическое завершение")
            return
        
        # Проверяем статус дуэли - запускаем только если она еще не завершена
        if duel.get("status") in ["finished", "cancelled"]:
            logger.info("PvP #100 уже завершена или отменена, пропускаем автоматическое завершение")
            return
        
        # Получаем участников
        participants = await db.get_pvp_participants(100)
        
        # Если нет участников, не запускаем
        if not participants:
            logger.info("PvP #100 не имеет участников, пропускаем автоматическое завершение")
            return
        
        # Если участников меньше максимума, но есть хотя бы один - все равно запускаем
        logger.info(f"🚀 Автоматически запускаю игру PvP #100 в 23:05. Участников: {len(participants)}")
        
        # Запускаем игру
        await start_pvp_game_in_channel(bot, 100)
        
        logger.info("✅ Автоматическое завершение PvP #100 выполнено")
            
    except Exception as e:
        logger.error(f"Ошибка при автоматическом завершении PvP #100: {e}", exc_info=True)


async def handle_pvp_500_game(bot: Bot, duel_id: int, duel: Dict):
    """Обработка игры PvP #500 с 2 слотами для определения 2 победителей"""
    try:
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        duel_link = f"https://t.me/{bot_username}?start={duel['unique_link']}"
        
        # Создаем кнопку со ссылкой на PvP
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"#{duel_id}",
                url=duel_link
            )
        ]])
        
        # Кидаем первый слот
        slot1_message = None
        slot1_value = None
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # Удаляем предыдущее сообщение, если это перекид
            if attempt > 1 and slot1_message:
                try:
                    await bot.delete_message(chat_id=PVP_CHANNEL_ID, message_id=slot1_message.message_id)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения: {e}")
            
            # Отправляем первый слот
            slot1_message = await bot.send_dice(
                chat_id=PVP_CHANNEL_ID,
                emoji="🎰",
                reply_markup=keyboard
            )
            
            # Ждем результата
            await asyncio.sleep(4)
            
            # Получаем результат
            slot1_value = slot1_message.dice.value
            logger.info(f"PvP #500: Первый слот выпал: {slot1_value}")
            
            # Если значение 1-64 - валидно
            if 1 <= slot1_value <= 64:
                break
            else:
                logger.warning(f"PvP #500: Первый слот выпал невалидное значение {slot1_value}, перекидываем")
                continue
        
        if slot1_value is None or not (1 <= slot1_value <= 64):
            logger.error("PvP #500: Не удалось получить валидное значение первого слота")
            slot1_value = 1  # Значение по умолчанию
        
        # Первый победитель - позиция = slot1_value
        winner1_position = slot1_value
        winner1_ticket = await db.get_ticket_owner(duel_id, winner1_position)
        
        if not winner1_ticket:
            logger.error(f"PvP #500: Не найден билет на позиции {winner1_position}")
            # Берем первый доступный билет
            tickets = await db.get_pvp_tickets(duel_id)
            if tickets:
                winner1_ticket = tickets[0]
            else:
                logger.error("PvP #500: Нет билетов вообще!")
                return
        
        winner1_id = winner1_ticket["user_id"]
        
        # Кидаем второй слот
        slot2_message = None
        slot2_value = None
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # Удаляем предыдущее сообщение, если это перекид
            if attempt > 1 and slot2_message:
                try:
                    await bot.delete_message(chat_id=PVP_CHANNEL_ID, message_id=slot2_message.message_id)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Ошибка при удалении сообщения: {e}")
            
            # Отправляем второй слот
            slot2_message = await bot.send_dice(
                chat_id=PVP_CHANNEL_ID,
                emoji="🎰",
                reply_markup=keyboard
            )
            
            # Ждем результата
            await asyncio.sleep(4)
            
            # Получаем результат
            slot2_value = slot2_message.dice.value
            logger.info(f"PvP #500: Второй слот выпал: {slot2_value}")
            
            # Если значение 1-64 - валидно
            if 1 <= slot2_value <= 64:
                break
            else:
                logger.warning(f"PvP #500: Второй слот выпал невалидное значение {slot2_value}, перекидываем")
                continue
        
        if slot2_value is None or not (1 <= slot2_value <= 64):
            logger.error("PvP #500: Не удалось получить валидное значение второго слота")
            slot2_value = 1  # Значение по умолчанию
        
        # Второй победитель - позиция = slot1_value + slot2_value
        winner2_position = slot1_value + slot2_value
        # Если позиция выходит за пределы 128, берем по модулю
        if winner2_position > 128:
            winner2_position = winner2_position % 128
            if winner2_position == 0:
                winner2_position = 128
        
        winner2_ticket = await db.get_ticket_owner(duel_id, winner2_position)
        
        if not winner2_ticket:
            logger.error(f"PvP #500: Не найден билет на позиции {winner2_position}")
            # Берем следующий доступный билет
            tickets = await db.get_pvp_tickets(duel_id)
            for ticket in tickets:
                if ticket["ticket_position"] != winner1_position:
                    winner2_ticket = ticket
                    break
            if not winner2_ticket:
                # Если не нашли, берем первый билет (но не тот же что winner1)
                if tickets and len(tickets) > 1:
                    winner2_ticket = tickets[1]
                else:
                    logger.error("PvP #500: Не удалось найти второго победителя!")
                    return
        
        winner2_id = winner2_ticket["user_id"]
        
        # Вычисляем выигрыш (с комиссией 10%)
        total_pot = duel["total_pot"]
        commission = total_pot * PVP_COMMISSION
        win_amount_per_winner = (total_pot - commission) / 2  # Делим между двумя победителями
        
        # Начисляем выигрыш победителям
        await db.update_balance(winner1_id, win_amount_per_winner)
        await db.update_balance(winner2_id, win_amount_per_winner)
        
        # Обновляем дуэль (сохраняем первого победителя в winner_id, второго можно сохранить отдельно)
        await db.finish_pvp_duel(duel_id, winner1_id)
        
        # Получаем информацию о победителях
        winner1_user = await db.get_user(winner1_id)
        winner1_name = winner1_user.get("username") if winner1_user else f"ID{winner1_id}"
        
        winner2_user = await db.get_user(winner2_id)
        winner2_name = winner2_user.get("username") if winner2_user else f"ID{winner2_id}"
        
        # Отправляем сообщение в канал о победителях
        winner_text = f"""🏆 <b>PvP #500 ЗАВЕРШЕНА!</b>

🎰 <b>Первый слот:</b> <code>{slot1_value}</code>
🎰 <b>Второй слот:</b> <code>{slot2_value}</code>

━━━━━━━━━━━━━━━━━━━━

🥇 <b>Первый победитель:</b>
🎫 <b>Позиция:</b> #{winner1_position}
👤 <b>Имя:</b> {winner1_name}
💰 <b>Выигрыш:</b> ${win_amount_per_winner:.2f}

🥈 <b>Второй победитель:</b>
🎫 <b>Позиция:</b> #{winner2_position} (первое + второе = {slot1_value} + {slot2_value})
👤 <b>Имя:</b> {winner2_name}
💰 <b>Выигрыш:</b> ${win_amount_per_winner:.2f}

━━━━━━━━━━━━━━━━━━━━

🔗 <a href="{duel_link}">Ссылка на дуэль</a>"""
        
        await bot.send_message(
            chat_id=PVP_CHANNEL_ID,
            text=winner_text,
            parse_mode="HTML"
        )
        
        # Отправляем личные сообщения победителям
        for winner_id, winner_name, position, slot_value in [
            (winner1_id, winner1_name, winner1_position, slot1_value),
            (winner2_id, winner2_name, winner2_position, slot2_value)
        ]:
            try:
                await bot.send_message(
                    winner_id,
                    f"🏆 <b>Поздравляем! Вы победили в PvP #500!</b>\n\n"
                    f"🎫 <b>Ваша позиция:</b> #{position}\n"
                    f"💰 <b>Выигрыш:</b> ${win_amount_per_winner:.2f}\n\n"
                    f"🔗 <a href='https://t.me/{PVP_CHANNEL_USERNAME}'>Открыть канал</a>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления победителю {winner_id}: {e}")
        
        logger.info(f"✅ PvP #500 завершена. Победители: {winner1_name} (позиция {winner1_position}) и {winner2_name} (позиция {winner2_position})")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке игры PvP #500: {e}", exc_info=True)


async def handle_pvp_500_join(message: Message, duel: Dict, user_id: int, user: Dict, state: FSMContext):
    """Обработка присоединения к PvP #500 с поддержкой множественных билетов"""
    try:
        # Проверяем статус
        if duel["status"] == "finished":
            tickets = await db.get_pvp_tickets(500)
            winners = []
            # Получаем информацию о победителях из базы
            # Для #500 может быть 2 победителя, нужно проверить структуру
            await message.reply("🏆 PvP #500 завершена. Проверьте канал для результатов.")
            return
        
        if duel["status"] == "cancelled":
            await message.reply("❌ Эта дуэль была отменена")
            return
        
        # Проверяем, заполнена ли дуэль (128 билетов)
        tickets_count = await db.get_pvp_tickets_count(500)
        if tickets_count >= 128:
            await message.reply("❌ Все билеты распроданы! Дуэль заполнена.")
            return
        
        # Показываем правила и просим ввести сумму
        text = """🎰 <b>PvP #500 - Специальная игра!</b>

📋 <b>Правила:</b>
• Участие стоит неограниченное количество раз
• Сумма должна быть кратна <b>0.1$</b>
• Минимальная ставка: <b>0.1$</b>
• Максимальная ставка: <b>5$</b>
• <b>0.1$ = 1 билет</b>
• Всего <b>128 билетов</b>
• <b>2 победителя</b>

🎰 <b>Механика:</b>
• Кидается <b>2 слота 🎰</b>
• Первое значение = первый победитель
• Второе значение = первое + второе = второй победитель

🎫 <b>Честное распределение:</b>
• Если покупка > 0.5$: 5 билетов в начало (1-5), остальные в конец (124-128)

━━━━━━━━━━━━━━━━━━━━

💰 <b>Введите сумму ставки (0.1 - 5.0):</b>"""
        
        await state.set_state(PvPStates.waiting_for_pvp500_amount)
        await state.update_data(duel_id=500)
        await message.reply(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке присоединения к PvP #500: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка. Попробуйте позже.")


@router.message(PvPStates.waiting_for_pvp500_amount)
async def handle_pvp500_amount(message: Message, state: FSMContext):
    """Обработка ввода суммы для PvP #500"""
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)
        
        if not user:
            await message.reply("Ошибка: пользователь не найден")
            await state.clear()
            return
        
        # Парсим сумму
        try:
            amount = float(message.text.replace(",", "."))
        except ValueError:
            await message.reply("❌ Пожалуйста, введите корректную сумму (например: 1.5)")
            return
        
        # Проверяем ограничения
        if amount < 0.1:
            await message.reply("❌ Минимальная ставка: $0.10")
            return
        
        if amount > 5.0:
            await message.reply("❌ Максимальная ставка: $5.00")
            return
        
        # Проверяем кратность 0.1
        if round(amount, 1) != amount:
            await message.reply("❌ Сумма должна быть кратна 0.1$ (например: 0.1, 0.5, 1.0, 2.5)")
            return
        
        # Проверяем баланс
        if user["balance"] < amount:
            await message.reply(f"❌ Недостаточно средств. Ваш баланс: ${user['balance']:.2f}")
            return
        
        # Получаем информацию о дуэли
        data = await state.get_data()
        duel_id = data.get("duel_id", 500)
        duel = await db.get_pvp_duel(duel_id=duel_id)
        
        if not duel:
            await message.reply("❌ Дуэль не найдена")
            await state.clear()
            return
        
        # Проверяем статус
        if duel["status"] != "waiting":
            await message.reply("❌ Дуэль уже началась или завершена")
            await state.clear()
            return
        
        # Вычисляем количество билетов
        ticket_count = int(amount / 0.1)
        
        # Проверяем, есть ли место для всех билетов
        current_tickets = await db.get_pvp_tickets_count(duel_id)
        if current_tickets + ticket_count > 128:
            available = 128 - current_tickets
            await message.reply(
                f"❌ Недостаточно свободных билетов!\n"
                f"Доступно: {available} билетов\n"
                f"Вы пытаетесь купить: {ticket_count} билетов"
            )
            return
        
        # Списываем средства
        await db.update_balance(user_id, -amount)
        
        # Распределяем позиции билетов
        ticket_positions = []
        
        if amount > 0.5:
            # Если покупка > 0.5: 5 билетов в начало (1-5), остальные в конец (124-128)
            # Получаем занятые позиции
            existing_tickets = await db.get_pvp_tickets(duel_id)
            occupied_start = {t["ticket_position"] for t in existing_tickets if 1 <= t["ticket_position"] <= 5}
            occupied_end = {t["ticket_position"] for t in existing_tickets if 124 <= t["ticket_position"] <= 128}
            
            # Распределяем 5 билетов в начало
            start_positions = [i for i in range(1, 6) if i not in occupied_start][:5]
            ticket_positions.extend(start_positions)
            
            # Остальные билеты в конец
            remaining = ticket_count - len(start_positions)
            if remaining > 0:
                end_positions = [i for i in range(124, 129) if i not in occupied_end][:remaining]
                ticket_positions.extend(end_positions)
                
                # Если все еще остались билеты, заполняем оставшиеся позиции по порядку
                if len(ticket_positions) < ticket_count:
                    all_occupied = {t["ticket_position"] for t in existing_tickets}
                    for pos in range(1, 129):
                        if pos not in all_occupied and len(ticket_positions) < ticket_count:
                            ticket_positions.append(pos)
        else:
            # Если покупка <= 0.5: распределяем по порядку
            existing_tickets = await db.get_pvp_tickets(duel_id)
            all_occupied = {t["ticket_position"] for t in existing_tickets}
            
            for pos in range(1, 129):
                if pos not in all_occupied and len(ticket_positions) < ticket_count:
                    ticket_positions.append(pos)
        
        # Добавляем билеты
        await db.add_pvp_tickets(duel_id, user_id, amount, ticket_positions)
        
        # Обновляем банк
        async with aiosqlite.connect(db.db_path) as database:
            await database.execute(
                "UPDATE pvp_duels SET total_pot = total_pot + ? WHERE id = ?",
                (amount, duel_id)
            )
            await database.commit()
        
        # Проверяем, заполнилась ли дуэль
        current_tickets = await db.get_pvp_tickets_count(duel_id)
        
        await state.clear()
        
        if current_tickets >= 128:
            # Дуэль заполнена, запускаем игру
            await message.reply(
                f"✅ Вы купили {ticket_count} билетов на сумму ${amount:.2f}!\n"
                f"🎫 Ваши позиции: {', '.join(map(str, ticket_positions))}\n\n"
                f"🎉 <b>Дуэль заполнена! Игра начинается...</b>\n\n"
                f"🔗 <a href='https://t.me/{PVP_CHANNEL_USERNAME}'>Открыть канал</a>",
                parse_mode="HTML"
            )
            await start_pvp_game_in_channel(message.bot, duel_id)
        else:
            await message.reply(
                f"✅ Вы купили <b>{ticket_count} билетов</b> на сумму <b>${amount:.2f}</b>!\n"
                f"🎫 <b>Ваши позиции:</b> {', '.join(map(str, ticket_positions))}\n\n"
                f"📊 <b>Продано билетов:</b> {current_tickets}/128\n"
                f"⏳ <b>Осталось:</b> {128 - current_tickets} билетов\n\n"
                f"💡 Вы можете купить еще билетов!",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке суммы для PvP #500: {e}", exc_info=True)
        await message.reply("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()


async def send_pvp_500_announcement_400(bot: Bot):
    """Отправить рассылку о предстоящей PvP #500 после завершения #400"""
    try:
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Формируем текст сообщения
        text = """🎉 <b>СКОРО ЗАПУСК PvP #500!</b>

🎊 <i>Специальная игра уже на подходе!</i>

━━━━━━━━━━━━━━━━━━━━

📋 <b>Правила PvP #500:</b>

💰 <b>Участие:</b>
• <i>Неограниченное</i> количество раз
• Сумма кратна <code>0.1$</code>
• Минимальная ставка: <b>0.1$</b>
• Максимальная ставка: <b>5$</b>
• <code>0.1$ = 1 билет</code>
• Всего <b>128 билетов</b>
• <b>2 победителя</b> 🏆

🎰 <b>Механика:</b>
• Кидается <b>2 слота 🎰</b>
• <i>Первое значение</i> = <b>первый победитель</b>
• <i>Второе значение</i> = <b>первое + второе</b> = <b>второй победитель</b>

🎫 <b>Честное распределение:</b>
<blockquote>Если покупка > 0.5$: 
5 билетов в начало (1-5), 
остальные в конец (124-128)</blockquote>

━━━━━━━━━━━━━━━━━━━━

⚡ <b>Следите за обновлениями!</b>
🎯 <i>PvP #500 скоро будет запущено!</i>"""
        
        # Создаем кнопку со ссылкой на бота с автоматическим /start
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎮 Перейти к боту",
                url=f"https://t.me/{bot_username}?start=start"
            )
        ]])
        
        # Отправляем в канал @arbuzikgame
        try:
            await bot.send_message(
                chat_id=ARBUZIK_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка о предстоящей PvP #500 отправлена в {ARBUZIK_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {ARBUZIK_CHANNEL}: {e}")
        
        # Отправляем в канал @cryptogifts_ru
        try:
            await bot.send_message(
                chat_id=CRYPTOGIFTS_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка о предстоящей PvP #500 отправлена в {CRYPTOGIFTS_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {CRYPTOGIFTS_CHANNEL}: {e}")
        
        # Рассылаем всем пользователям бота
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку о предстоящей PvP #500 всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:  # Пропускаем системного пользователя
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    # Логируем только каждую 10-ю ошибку
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке рассылки о предстоящей PvP #500: {e}", exc_info=True)


async def send_pvp_500_announcement_499(bot: Bot):
    """Отправить рассылку о запуске PvP #500 после завершения #499"""
    try:
        # Проверяем, существует ли PvP #500
        duel = await db.get_pvp_duel(duel_id=500)
        if not duel:
            logger.warning("PvP #500 не найдено, пропускаем рассылку")
            return
        
        # Получаем username бота
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Формируем ссылку на PvP #500 (из символов 5 и 0)
        unique_link = duel.get("unique_link", generate_500_link())
        duel_link = f"https://t.me/{bot_username}?start={unique_link}"
        
        # Формируем текст сообщения
        text = """🎉 <b>PvP #500 ЗАПУЩЕНО!</b>

🎊 <i>Специальная игра уже доступна!</i>

━━━━━━━━━━━━━━━━━━━━

📋 <b>Правила PvP #500:</b>

💰 <b>Участие:</b>
• <i>Неограниченное</i> количество раз
• Сумма кратна <code>0.1$</code>
• Минимальная ставка: <b>0.1$</b>
• Максимальная ставка: <b>5$</b>
• <code>0.1$ = 1 билет</code>
• Всего <b>128 билетов</b>
• <b>2 победителя</b> 🏆

🎰 <b>Механика:</b>
• Кидается <b>2 слота 🎰</b>
• <i>Первое значение</i> = <b>первый победитель</b>
• <i>Второе значение</i> = <b>первое + второе</b> = <b>второй победитель</b>

🎫 <b>Честное распределение:</b>
<blockquote>Если покупка > 0.5$: 
5 билетов в начало (1-5), 
остальные в конец (124-128)</blockquote>

━━━━━━━━━━━━━━━━━━━━

⚡ <b>Успейте присоединиться!</b>
🎯 <i>Только <b>128 билетов</b>!</i>"""
        
        # Создаем кнопку со ссылкой на PvP #500
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎮 Присоединиться к PvP #500",
                url=duel_link
            )
        ]])
        
        # Отправляем в канал @arbuzikgame
        try:
            await bot.send_message(
                chat_id=ARBUZIK_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка о запуске PvP #500 отправлена в {ARBUZIK_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {ARBUZIK_CHANNEL}: {e}")
        
        # Отправляем в канал @cryptogifts_ru
        try:
            await bot.send_message(
                chat_id=CRYPTOGIFTS_CHANNEL,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            logger.info(f"✅ Рассылка о запуске PvP #500 отправлена в {CRYPTOGIFTS_CHANNEL}")
        except Exception as e:
            logger.error(f"Ошибка при отправке рассылки в {CRYPTOGIFTS_CHANNEL}: {e}")
        
        # Рассылаем всем пользователям бота
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку о запуске PvP #500 всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:  # Пропускаем системного пользователя
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    # Небольшая задержка, чтобы не превысить лимиты Telegram
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    # Логируем только каждую 10-ю ошибку
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"Ошибка при рассылке всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Ошибка при отправке рассылки о запуске PvP #500: {e}", exc_info=True)

