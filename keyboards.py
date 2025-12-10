from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from typing import List, Dict


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню с клавиатурными кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💼 Кошелек"),
                KeyboardButton(text="🎮 Игры")
            ],
            [
                KeyboardButton(text="👤 Профиль"),
                KeyboardButton(text="⚙️ Настройки")
            ],
            [
                KeyboardButton(text="🏆 Топ"),
                KeyboardButton(text="⚔️ PvP")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_remove_keyboard():
    """Скрыть существующую reply keyboard"""
    return ReplyKeyboardRemove(remove_keyboard=True)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ панели"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="💰 Пополнение баланса", callback_data="admin_deposit"),
        ],
        [
            InlineKeyboardButton(text="💳 Баланс Crypto Pay", callback_data="admin_crypto_balance"),
        ],
        [
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="admin_promo_codes"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_user_search"),
        ],
        [
            InlineKeyboardButton(text="🤝 Партнеры", callback_data="admin_partners"),
        ],
        [
            InlineKeyboardButton(text="💬 Чаты", callback_data="admin_chats"),
        ],
        [
            InlineKeyboardButton(text="📈 Графики", callback_data="admin_charts"),
        ],
        [
            InlineKeyboardButton(text="🎫 Лотереи", callback_data="admin_lotteries"),
        ],
        [
            InlineKeyboardButton(text="📥 Экспорт данных", callback_data="admin_export"),
        ],
    ])
    return keyboard


def get_games_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню игр"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Дартс", callback_data="game_dart"),
            InlineKeyboardButton(text="🎲 Кубик", callback_data="game_dice"),
        ],
        [
            InlineKeyboardButton(text="🎰 Слоты", callback_data="game_slots"),
            InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_bowling"),
        ],
        [
            InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basketball"),
            InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football"),
        ]
    ])
    return keyboard


def get_deposit_keyboard() -> InlineKeyboardMarkup:
    """Меню депозита"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 TON", callback_data="deposit_ton"),
            InlineKeyboardButton(text="🏝️ CryptoBot", callback_data="deposit_cryptobot"),
        ],
        [
            InlineKeyboardButton(text="🚀 xRocket", callback_data="deposit_xrocket"),
        ],
        [
            InlineKeyboardButton(text="🎁 Подарки", callback_data="deposit_gifts"),
        ],
    ])
    return keyboard


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔔 Реф. уведомления", callback_data="setting_ref_notif"),
        ],
        [
            InlineKeyboardButton(text="💰 Базовая ставка", callback_data="setting_base_bet"),
        ],
        [
            InlineKeyboardButton(text="🎫 Создать чек", callback_data="setting_create_check"),
        ],
        [
            InlineKeyboardButton(text="🎫 Лотереи", callback_data="lottery_menu"),
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка", callback_data="setting_support"),
        ],
    ])
    return keyboard


def get_game_keyboard(game_type: str, current_bet: float = 1.0, currency: str = "dollar") -> InlineKeyboardMarkup:
    """Клавиатура для игры"""
    from config import MAX_BET
    
    # Определяем формат в зависимости от валюты
    if currency == "arbuzz":
        currency_symbol = ""
        currency_suffix = " AC"
        min_bet = 1.0
    else:
        currency_symbol = "$"
        currency_suffix = ""
        min_bet = 0.1
    
    # Вычисляем уменьшение и увеличение на 50%
    decrease = current_bet * 0.5  # 50% уменьшение
    increase = current_bet * 0.5  # 50% увеличение
    
    # Вычисляем новые значения ставки
    new_bet_decrease = max(min_bet, current_bet - decrease)  # Минимум зависит от валюты
    new_bet_increase = min(MAX_BET, current_bet + increase)  # Максимум MAX_BET
    
    # Форматируем в зависимости от валюты
    if currency == "arbuzz":
        decrease_text = f"− {new_bet_decrease:.0f}{currency_suffix}"
        current_text = f"✓ {current_bet:.0f}{currency_suffix}"
        increase_text = f"+ {new_bet_increase:.0f}{currency_suffix}"
    else:
        decrease_text = f"− {currency_symbol}{new_bet_decrease:.2f}"
        current_text = f"✓ {currency_symbol}{current_bet:.2f}"
        increase_text = f"+ {currency_symbol}{new_bet_increase:.2f}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=decrease_text, callback_data=f"bet_{game_type}_{new_bet_decrease:.2f}"),
            InlineKeyboardButton(text=current_text, callback_data=f"bet_confirm_{game_type}_{current_bet:.2f}"),
            InlineKeyboardButton(text=increase_text, callback_data=f"bet_{game_type}_{new_bet_increase:.2f}"),
        ],
        [
            InlineKeyboardButton(text="🎮 Игры", callback_data="games_menu"),
            InlineKeyboardButton(text="📋 Правила", callback_data=f"rules_{game_type}"),
        ],
    ])
    return keyboard


def get_dice_betting_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ставок для кубика"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🙏 Чет x1.9", callback_data="bet_type_dice_even"),
            InlineKeyboardButton(text="🙏 Нечет x1.9", callback_data="bet_type_dice_odd"),
        ],
        [
            InlineKeyboardButton(text="🙏 3 Чет x7", callback_data="bet_type_dice_3_even"),
            InlineKeyboardButton(text="🙏 3 Нечет x7", callback_data="bet_type_dice_3_odd"),
        ],
        [
            InlineKeyboardButton(text="1️⃣ 1", callback_data="bet_type_dice_exact_1"),
            InlineKeyboardButton(text="2️⃣ 2", callback_data="bet_type_dice_exact_2"),
            InlineKeyboardButton(text="3️⃣ 3", callback_data="bet_type_dice_exact_3"),
            InlineKeyboardButton(text="4️⃣ 4", callback_data="bet_type_dice_exact_4"),
            InlineKeyboardButton(text="5️⃣ 5", callback_data="bet_type_dice_exact_5"),
            InlineKeyboardButton(text="6️⃣ 6", callback_data="bet_type_dice_exact_6"),
        ],
        [
            InlineKeyboardButton(text="🫂 Пара x5.55", callback_data="bet_type_dice_pair"),
            InlineKeyboardButton(text="🔞 18 x8", callback_data="bet_type_dice_18"),
            InlineKeyboardButton(text="💀 21 x11", callback_data="bet_type_dice_21"),
        ],
        [
            InlineKeyboardButton(text="🍀 111 x100", callback_data="bet_type_dice_111"),
            InlineKeyboardButton(text="☘️ 333 x100", callback_data="bet_type_dice_333"),
            InlineKeyboardButton(text="🐍 666 x100", callback_data="bet_type_dice_666"),
        ],
        [
            InlineKeyboardButton(text="🎯 >7 x2.4", callback_data="bet_type_dice_7_more_7"),
            InlineKeyboardButton(text="🎯 <7 x2.4", callback_data="bet_type_dice_7_less_7"),
            InlineKeyboardButton(text="🎯 =7 x6.0", callback_data="bet_type_dice_7_equal_7"),
        ],
    ])
    return keyboard


def get_dart_betting_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ставок для дартса"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Белое x2", callback_data="bet_type_dart_white"),
            InlineKeyboardButton(text="🔴 Красное x1.4", callback_data="bet_type_dart_red"),
        ],
        [
            InlineKeyboardButton(text="🍏 Центр x6", callback_data="bet_type_dart_center"),
            InlineKeyboardButton(text="🌨️ Отскок x6", callback_data="bet_type_dart_miss"),
        ],
        [
            InlineKeyboardButton(text="🚩 3 Красных x7", callback_data="bet_type_dart_3_red"),
            InlineKeyboardButton(text="🥚 3 Белых x21", callback_data="bet_type_dart_3_white"),
        ],
        [
            InlineKeyboardButton(text="🏹 3 в Центр x100", callback_data="bet_type_dart_3_center"),
            InlineKeyboardButton(text="🏹 3 Мимо x100", callback_data="bet_type_dart_3_miss"),
        ],
    ])
    return keyboard


def get_bowling_betting_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ставок для боулинга"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👌 0-3 шт x1.9", callback_data="bet_type_bowling_0-3"),
            InlineKeyboardButton(text="✋ 4-6 шт x1.9", callback_data="bet_type_bowling_4-6"),
        ],
        [
            InlineKeyboardButton(text="👏 Страйк x5", callback_data="bet_type_bowling_strike"),
            InlineKeyboardButton(text="🤷 Промах x5", callback_data="bet_type_bowling_miss"),
        ],
        [
            InlineKeyboardButton(text="💪 2 Страйка x30", callback_data="bet_type_bowling_2_strike"),
            InlineKeyboardButton(text="🎳 2 Мимо x30", callback_data="bet_type_bowling_2_miss"),
        ],
        [
            InlineKeyboardButton(text="🏆 3 Страйка x100", callback_data="bet_type_bowling_3_strike"),
            InlineKeyboardButton(text="🪦 3 Мимо x100", callback_data="bet_type_bowling_3_miss"),
        ],
    ])
    return keyboard


def get_football_betting_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ставок для футбола"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚽ Гол x1.4", callback_data="bet_type_football_goal"),
            InlineKeyboardButton(text="🥅 Промах x2.5", callback_data="bet_type_football_miss"),
        ],
        [
            InlineKeyboardButton(text="🎯 В центр x1.9", callback_data="bet_type_football_center"),
        ],
        [
            InlineKeyboardButton(text="🎩 Хет-трик x4", callback_data="bet_type_football_hattrick"),
            InlineKeyboardButton(text="🖐️ 5 Голов x11", callback_data="bet_type_football_5_goals"),
        ],
        [
            InlineKeyboardButton(text="👑 10 Голов x100", callback_data="bet_type_football_10_goals"),
            InlineKeyboardButton(text="💀 6 Промахов x100", callback_data="bet_type_football_6_miss"),
        ],
    ])
    return keyboard


def get_basketball_betting_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура ставок для баскетбола"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚽ Гол x2", callback_data="bet_type_basketball_hit"),
            InlineKeyboardButton(text="👋 Мимо x1.4", callback_data="bet_type_basketball_miss"),
        ],
        [
            InlineKeyboardButton(text="💧 Чистый гол x6", callback_data="bet_type_basketball_clean"),
            InlineKeyboardButton(text="🔒 Застрял x5", callback_data="bet_type_basketball_stuck"),
        ],
        [
            InlineKeyboardButton(text="🔄 2 Попал x5", callback_data="bet_type_basketball_2_hit"),
            InlineKeyboardButton(text="🌊 2 Чистых x15", callback_data="bet_type_basketball_2_clean"),
        ],
        [
            InlineKeyboardButton(text="✏️ 3 Попал x12", callback_data="bet_type_basketball_3_hit"),
            InlineKeyboardButton(text="🌪️ 3 Чистых x77", callback_data="bet_type_basketball_3_clean"),
        ],
        [
            InlineKeyboardButton(text="🔥 6 Попал x100", callback_data="bet_type_basketball_6_hit"),
        ],
    ])
    return keyboard


def get_slots_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для слотов"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😎 10 СПИНОВ", callback_data="slots_spins_10"),
            InlineKeyboardButton(text="🤑 100 СПИНОВ", callback_data="slots_spins_100"),
        ],
        [
            InlineKeyboardButton(text="😊 1 СПИН", callback_data="slots_spin_1"),
        ],
        [
            InlineKeyboardButton(text="🗓️ Множители", callback_data="slots_multipliers"),
            InlineKeyboardButton(text="🎮 Игры", callback_data="games_menu"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ]
    ])
    return keyboard




def get_jackpot_keyboard(jackpot_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для джекпота"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Играть", callback_data=f"jackpot_play_{jackpot_type}"),
        ],
        [
            InlineKeyboardButton(text="🎮 Игры", callback_data="games_menu"),
            InlineKeyboardButton(text="📋 Правила", callback_data=f"jackpot_rules_{jackpot_type}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ]
    ])
    return keyboard


def get_wallet_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура кошелька"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Пополнить", callback_data="wallet_deposit"),
        ],
        [
            InlineKeyboardButton(text="➖ Вывести", callback_data="wallet_withdraw"),
        ]
    ])
    return keyboard


def get_top_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора категории топа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="♟️ Топ игроков", callback_data="top_category_players"),
            InlineKeyboardButton(text="✨ Топ чатов", callback_data="top_category_chats"),
        ],
    ])
    return keyboard


def get_top_period_keyboard(category: str = "players") -> InlineKeyboardMarkup:
    """Клавиатура выбора периода топа"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 За день", callback_data=f"top_{category}_day"),
            InlineKeyboardButton(text="📆 За месяц", callback_data=f"top_{category}_month"),
        ],
        [
            InlineKeyboardButton(text="🌍 За все время", callback_data=f"top_{category}_all"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="top_back"),
        ],
    ])
    return keyboard


def get_withdrawal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура вывода средств"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="$10", callback_data="withdraw_10"),
            InlineKeyboardButton(text="$20", callback_data="withdraw_20"),
            InlineKeyboardButton(text="$50", callback_data="withdraw_50"),
            InlineKeyboardButton(text="$100", callback_data="withdraw_100"),
        ],
        [
            InlineKeyboardButton(text="$250", callback_data="withdraw_250"),
            InlineKeyboardButton(text="$500", callback_data="withdraw_500"),
            InlineKeyboardButton(text="$1000", callback_data="withdraw_1000"),
            InlineKeyboardButton(text="$2500", callback_data="withdraw_2500"),
        ],
        [
            InlineKeyboardButton(text="Max", callback_data="withdraw_max"),
        ],
        [
            InlineKeyboardButton(text="✏️ Ввести свою сумму", callback_data="withdraw_custom"),
        ],
        [
            InlineKeyboardButton(text="🎁 Подарок", callback_data="withdraw_gifts"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_menu"),
        ]
    ])
    return keyboard


def get_gifts_withdrawal_keyboard(gifts_config: Dict, user_balance_ton: float, ton_rate: float, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура выбора подарка для вывода с пагинацией"""
    keyboard_buttons = []
    
    # price_ton в конфиге указан в TON
    # При выводе цена на 10% больше базовой
    # Сравниваем цены в TON напрямую
    # Создаем список доступных подарков
    available_gifts = []
    for emoji, gift_info in gifts_config.items():
        base_price_ton = gift_info.get("price_ton", 0)  # базовая цена в TON
        price_ton = base_price_ton * 1.1  # +10% при выводе
        # Сравниваем цены в TON
        if price_ton <= user_balance_ton:
            available_gifts.append({
                "emoji": emoji,
                "name": gift_info["name"],
                "price_ton": price_ton
            })
    
    # Сортируем по цене по возрастанию (от меньшего к большему)
    available_gifts.sort(key=lambda x: x["price_ton"], reverse=False)
    
    # Пагинация: 10 подарков на страницу (5 рядов по 2 кнопки)
    gifts_per_page = 10
    total_pages = (len(available_gifts) + gifts_per_page - 1) // gifts_per_page if available_gifts else 1
    
    # Ограничиваем номер страницы
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1
    
    # Вычисляем индексы для текущей страницы
    start_idx = page * gifts_per_page
    end_idx = min(start_idx + gifts_per_page, len(available_gifts))
    
    # Группируем по 2 кнопки в ряд (5 рядов = 10 подарков)
    for i in range(start_idx, end_idx, 2):
        row = []
        for j in range(2):
            if i + j < end_idx:
                gift = available_gifts[i + j]
                emoji = gift["emoji"] if gift["emoji"] else ""
                name = gift["name"]
                price_ton = gift["price_ton"]
                button_text = f"{emoji} {name} {price_ton:.4f} TON"[:64]  # Ограничение длины текста
                # Используем имя для callback_data (заменяем пробелы на подчеркивания)
                name_safe = name.replace(" ", "_").replace("-", "_")
                callback_data = f"withdraw_gift_{name_safe}"[:64]
                row.append(InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data
                ))
        if row:
            keyboard_buttons.append(row)
    
    # Кнопки навигации по страницам
    navigation_buttons = []
    if total_pages > 1:
        if page > 0:
            navigation_buttons.append(
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"gifts_page_{page - 1}")
            )
        if page < total_pages - 1:
            navigation_buttons.append(
                InlineKeyboardButton(text="➡️ Дальше", callback_data=f"gifts_page_{page + 1}")
            )
        if navigation_buttons:
            keyboard_buttons.append(navigation_buttons)
    
    # Кнопка "Отправить подарок" и "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(text="✈️ Отправить подарок", url="https://t.me/arbuzrelayer"),
    ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="wallet_withdraw"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_pvp_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню PvP"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Создать PvP", callback_data="pvp_create"),
        ],
        [
            InlineKeyboardButton(text="📋 Активные PvP", callback_data="pvp_active"),
            InlineKeyboardButton(text="📋 Мои PvP", callback_data="pvp_my_duels"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main"),
        ]
    ])
    return keyboard


def get_pvp_game_select_keyboard() -> InlineKeyboardMarkup:
    """Выбор игры для PvP"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎳 Боулинг", callback_data="pvp_game_bowling"),
            InlineKeyboardButton(text="🎲 Кубы", callback_data="pvp_game_dice"),
        ],
        [
            InlineKeyboardButton(text="🎯 Дартс", callback_data="pvp_game_dart"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu"),
        ]
    ])
    return keyboard


def get_pvp_players_count_keyboard(game_type: str = None) -> InlineKeyboardMarkup:
    """Выбор количества игроков для PvP"""
    keyboard_buttons = [
        [
            InlineKeyboardButton(text="2 игрока", callback_data="pvp_players_2"),
            InlineKeyboardButton(text="3 игрока", callback_data="pvp_players_3"),
        ],
        [
            InlineKeyboardButton(text="4 игрока", callback_data="pvp_players_4"),
        ],
    ]
    
    # Кнопка "Назад" - возвращаемся к выбору игры
    if game_type:
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Назад к выбору игры", callback_data="pvp_create"),
        ])
    else:
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_create"),
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_pvp_my_duels_keyboard(duels: List[Dict]) -> InlineKeyboardMarkup:
    """Клавиатура для списка моих дуэлей"""
    keyboard_buttons = []
    for duel in duels[:10]:  # Максимум 10 дуэлей
        status_emoji = "⏳" if duel["status"] == "waiting" else "✅" if duel["status"] == "finished" else "❌"
        game_emoji = {"bowling": "🎳", "dice": "🎲", "dart": "🎯"}.get(duel["game_type"], "🎮")
        button_text = f"{status_emoji} {game_emoji} #{duel['id']}"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"pvp_duel_{duel['id']}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_menu"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)


def get_pvp_duel_actions_keyboard(duel_id: int, is_creator: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий с дуэлью"""
    keyboard_buttons = []
    
    if is_creator:
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"pvp_cancel_{duel_id}"),
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔗 Ссылка на дуэль", callback_data=f"pvp_link_{duel_id}"),
    ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pvp_my_duels"),
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
