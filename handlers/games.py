from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile, InputMediaPhoto
from aiogram.fsm.context import FSMContext
import random
import asyncio
import logging
import time
import os
import math
import re

from database import Database
from config import GAME_CONFIGS, MAX_BET

logger = logging.getLogger(__name__)
from keyboards import (
    get_game_keyboard, get_dice_betting_keyboard, get_dart_betting_keyboard,
    get_bowling_betting_keyboard, get_football_betting_keyboard,
    get_basketball_betting_keyboard, get_slots_keyboard,
    get_games_menu_keyboard
)

router = Router(name="games")
db = Database()

# Состояния для игр
GAME_STATES = {}

# Состояния по message_id для быстрого поиска
DICE_MESSAGE_STATES = {}

# Последняя игра для каждого пользователя (для кнопки "Повторить игру")
LAST_GAME = {}  # {user_id: {"game_type": str, "bet_type": str, "bet": float}}

# Активные игры для блокировки кнопок (для игр с несколькими бросками)
ACTIVE_GAMES = {}  # {user_id: True}

# Базовая ставка для арбузов для каждого пользователя
BASE_BET_ARBUZZ = {}  # {user_id: float}

STATE_TIMEOUT = 30  # секунды


def _clear_game_state(user_id: int):
    if user_id in GAME_STATES:
        for msg_id, uid in list(DICE_MESSAGE_STATES.items()):
            if uid == user_id:
                del DICE_MESSAGE_STATES[msg_id]
        del GAME_STATES[user_id]
    if user_id in ACTIVE_GAMES:
        del ACTIVE_GAMES[user_id]


def cleanup_user_state(user_id: int):
    now = time.time()
    state = GAME_STATES.get(user_id)
    if state:
        started_at = state.get("started_at", now)
        if now - started_at > STATE_TIMEOUT:
            logger.warning(f"⏱ Зависшее состояние игры очищено для пользователя {user_id}")
            _clear_game_state(user_id)
            return
    active_ts = ACTIVE_GAMES.get(user_id)
    if active_ts:
        started_at = active_ts if isinstance(active_ts, (int, float)) else now
        if now - started_at > STATE_TIMEOUT:
            logger.warning(f"⏱ Сброс блокировки игр для пользователя {user_id}")
            del ACTIVE_GAMES[user_id]


def is_user_busy(user_id: int) -> bool:
    cleanup_user_state(user_id)
    return user_id in ACTIVE_GAMES or user_id in GAME_STATES


def get_multiplier(config: dict, bet_type: str) -> float:
    """Возвращает коэффициент с учетом динамических типов ставок"""
    multipliers = config.get("multipliers", {})
    if bet_type.startswith("exact_"):
        return multipliers.get("exact", 1.0)
    return multipliers.get(bet_type, 1.0)


async def process_game_result(bot, user_id: int, chat_id: int, game_type: str, bet_type: str, 
                              bet: float, required_throws: int, emoticon: str, currency: str = "dollar"):
    """Обрабатывает результат игры после всех бросков"""
    try:
        logger.info(f"🎮 Обработка результата игры для пользователя {user_id}, ставка {bet_type}")
        if user_id not in GAME_STATES:
            logger.warning(f"⚠️ Состояние игры не найдено для пользователя {user_id}")
            return
        
        state = GAME_STATES[user_id]
        
        # ЗАЩИТА ОТ ДВОЙНОЙ ОБРАБОТКИ: проверяем, не обработана ли игра уже
        if state.get("result_processed", False):
            logger.warning(f"⚠️ Игра для пользователя {user_id} уже обработана, пропускаем повторную обработку")
            return
        
        # Помечаем игру как обработанную
        state["result_processed"] = True
        # Используем реальные результаты из состояния
        throws = state.get("throws", [])
        logger.info(f"🎲 Фактические результаты бросков: {throws}")
        
        # Получаем конфигурацию игры
        config = GAME_CONFIGS.get(game_type)
        if not config:
            logger.error(f"❌ Конфигурация игры {game_type} не найдена")
            return
        
        # Проверяем выигрыш
        multiplier = get_multiplier(config, bet_type)
        win = 0
        is_win = False
        first_result = throws[0] if throws else 0
        
        # Логика проверки выигрыша (копируем из handle_dice_result)
        if game_type == "dice":
            if bet_type == "even":
                is_win = first_result % 2 == 0
            elif bet_type == "odd":
                is_win = first_result % 2 == 1
            elif bet_type.startswith("exact_"):
                target_num = int(bet_type.split("_")[1])
                is_win = first_result == target_num
            elif bet_type == "pair":
                is_win = len(throws) >= 2 and throws[0] == throws[1]
            elif bet_type == "3_even":
                is_win = len(throws) >= 3 and all(t % 2 == 0 for t in throws[:3])
            elif bet_type == "3_odd":
                is_win = len(throws) >= 3 and all(t % 2 == 1 for t in throws[:3])
            elif bet_type == "18":
                is_win = len(throws) >= 5 and sum(throws[:5]) == 18
            elif bet_type == "21":
                is_win = len(throws) >= 5 and sum(throws[:5]) == 21
            elif bet_type == "111":
                is_win = len(throws) >= 3 and all(t == 1 for t in throws[:3])
            elif bet_type == "333":
                is_win = len(throws) >= 3 and all(t == 3 for t in throws[:3])
            elif bet_type == "666":
                is_win = len(throws) >= 3 and all(t == 6 for t in throws[:3])
        
        elif game_type == "dart":
            if bet_type == "red":
                is_win = first_result in [2, 4, 6]  
            elif bet_type == "white":
                is_win = first_result in [3, 5]
            elif bet_type == "center":
                is_win = first_result == 6  
            elif bet_type == "miss":
                is_win = first_result == 1
            elif bet_type == "3_red":
                is_win = len(throws) >= 3 and all(t in [2, 4, 6] for t in throws[:3])  
            elif bet_type == "3_white":
                is_win = len(throws) >= 3 and all(t in [3, 5] for t in throws[:3])
            elif bet_type == "3_center":
                is_win = len(throws) >= 3 and all(t == 6 for t in throws[:3])  
            elif bet_type == "3_miss":
                is_win = len(throws) >= 3 and all(t == 1 for t in throws[:3])
        
        elif game_type == "bowling":
            if bet_type == "0-3":
                is_win = first_result <= 3
            elif bet_type == "4-6":
                is_win = 4 <= first_result <= 6
            elif bet_type == "strike":
                is_win = first_result == 6
            elif bet_type == "miss":
                is_win = first_result in [0, 1]  # 1 также считается промахом
            elif bet_type == "2_strike":
                is_win = len(throws) >= 2 and all(t == 6 for t in throws[:2])
            elif bet_type == "3_strike":
                is_win = len(throws) >= 3 and all(t == 6 for t in throws[:3])
            elif bet_type == "2_miss":
                is_win = len(throws) >= 2 and all(t in [0, 1] for t in throws[:2])  # 1 также считается промахом
            elif bet_type == "3_miss":
                is_win = len(throws) >= 3 and all(t in [0, 1] for t in throws[:3])  # 1 также считается промахом
        
        elif game_type == "football":
            # Для футбола: 3, 4, 5 - гол, 1, 2 - мимо, 3 - в центр (штанга)
            if bet_type == "goal":
                # Гол: значения 3, 4, 5
                is_win = first_result in [3, 4, 5]
            elif bet_type == "miss":
                # Мимо: значения 1, 2
                is_win = first_result in [1, 2]
            elif bet_type == "center":
                # В центр (штанга): значение 3
                is_win = first_result == 3
            elif bet_type == "hattrick":
                # 3 гола подряд (3, 4 или 5)
                is_win = len(throws) >= 3 and all(t in [3, 4, 5] for t in throws[:3])
            elif bet_type == "5_goals":
                # 5 голов подряд (3, 4 или 5)
                is_win = len(throws) >= 5 and all(t in [3, 4, 5] for t in throws[:5])
            elif bet_type == "10_goals":
                # 10 голов подряд (3, 4 или 5)
                is_win = len(throws) >= 10 and all(t in [3, 4, 5] for t in throws[:10])
            elif bet_type == "6_miss":
                # 6 промахов подряд (1, 2 или 3)
                is_win = len(throws) >= 6 and all(t in [1, 2, 3] for t in throws[:6])
        
        elif game_type == "basketball":
            # Для баскетбола: 4 и 5 - попадание (гол), 2 - мимо, 5 - чистый гол, 3 - застрял, 1 - мимо
            # Значение 5 - это чистый гол, но он также считается простым попаданием
            if bet_type == "hit":
                is_win = first_result in [4, 5]
            elif bet_type == "miss":
                is_win = first_result in [1, 2]
            elif bet_type == "clean":
                is_win = first_result == 5
            elif bet_type == "stuck":
                is_win = first_result == 3
            elif bet_type == "2_hit":
                is_win = len(throws) >= 2 and all(t in [4, 5] for t in throws[:2])
            elif bet_type == "3_hit":
                is_win = len(throws) >= 3 and all(t in [4, 5] for t in throws[:3])
            elif bet_type == "2_clean":
                is_win = len(throws) >= 2 and all(t == 5 for t in throws[:2])
            elif bet_type == "3_clean":
                is_win = len(throws) >= 3 and all(t == 5 for t in throws[:3])
            elif bet_type == "6_hit":
                is_win = len(throws) >= 6 and all(t in [4, 5] for t in throws[:6])
        
        elif game_type == "dice_7":
            # Для "Кубик: +- 7" нужны 2 броска
            if len(throws) < 2:
                # Если еще не все броски, продолжаем
                logger.warning(f"⚠️ Недостаточно бросков для dice_7: {len(throws)}/2")
                return
            
            dice_sum = sum(throws[:2])
            
            if bet_type == "less_7":
                is_win = dice_sum < 7
            elif bet_type == "equal_7":
                is_win = dice_sum == 7
            elif bet_type == "more_7":
                is_win = dice_sum > 7
        
        # Рассчитываем выигрыш
        if is_win:
            win = bet * multiplier
            if currency == "arbuzz":
                # Игра на арбузз коины
                await db.update_arbuzz_balance(user_id, win)  # Добавляем выигрыш (ставка уже списана)
                logger.info(f"🎉 Выигрыш! {win:.0f} AC (ставка {bet:.0f} x {multiplier})")
            else:
                # Игра на доллары
                await db.update_balance(user_id, win)  # Добавляем выигрыш (ставка уже списана)
                logger.info(f"🎉 Выигрыш! ${win:.2f} (ставка ${bet:.2f} x {multiplier})")
                
                # Начисляем 1000 арбузз коинов за первую победу в день (только на доллары)
                try:
                    first_win_given = await db.check_and_give_first_win_arbuzz(user_id, "dollar")
                    if first_win_given:
                        logger.info(f"🎉 1000 арбузз коинов за первую победу в день выданы пользователю {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при выдаче арбузз коинов за первую победу: {e}", exc_info=True)
        else:
            # Ставка уже списана при начале игры
            win = 0
            if currency == "dollar":
                # Увеличиваем счетчик проигранных средств только для долларов
                await db.update_user_total_lost(user_id, bet)
            logger.info(f"😔 Проигрыш. Ставка {bet:.2f} {'AC' if currency == 'arbuzz' else '$'} уже списана")
        
        # Сохраняем выигрыш в состояние для мини-аппа
        state["win"] = win
        
        # Сохраняем результат игры
        if game_type == "dice_7":
            game_result = sum(throws[:2]) if len(throws) >= 2 else first_result
        else:
            game_result = first_result if len(throws) == 1 else sum(throws)
        await db.add_game(user_id, game_type, bet, game_result, win, bet_type, currency=currency)
        
        # Если игра из мини-аппа, сохраняем результат для API
        if state.get("mini_app") and state.get("game_id"):
            try:
                from api_server import MINI_APP_GAMES
                game_id = state.get("game_id")
                user = await db.get_user(user_id)
                new_balance = user.get('balance', 0.0) if user else 0.0
                
                if game_id in MINI_APP_GAMES:
                    MINI_APP_GAMES[game_id]['status'] = 'completed'
                    MINI_APP_GAMES[game_id]['result'] = game_result
                    MINI_APP_GAMES[game_id]['win'] = win
                    MINI_APP_GAMES[game_id]['new_balance'] = new_balance
                    MINI_APP_GAMES[game_id]['game_type'] = game_type
                    logger.info(f"✅ Результат игры из мини-аппа сохранен: game_id={game_id}, result={game_result}, win={win}")
            except Exception as e:
                logger.error(f"Ошибка сохранения результата для мини-аппа: {e}", exc_info=True)
        
        # Начисляем реферальный бонус рефералу
        try:
            from utils.referrals import send_referral_earnings_notification, send_level_up_notification
            referral_bonus = await db.process_referral_bonus(user_id, bet, win)
            if referral_bonus:
                logger.info(f"💰 Реферальный бонус начислен: ${referral_bonus['bonus']:.2f} для пользователя {referral_bonus['referrer_id']}")
                
                # Отправляем уведомление о заработке, если включены уведомления
                if referral_bonus.get("send_notification"):
                    try:
                        await send_referral_earnings_notification(
                            bot, 
                            referral_bonus["referrer_id"],
                            referral_bonus["bonus"],
                            referral_bonus["bet_amount"]
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка при отправке уведомления о заработке: {e}")
                
                # Проверяем повышение уровня
                if referral_bonus["old_level"] < referral_bonus["new_level"]:
                    logger.info(f"🎉 Повышение уровня для пользователя {referral_bonus['referrer_id']}: {referral_bonus['old_level']} -> {referral_bonus['new_level']}")
                    try:
                        await send_level_up_notification(
                            bot,
                            referral_bonus["referrer_id"],
                            referral_bonus["old_level"],
                            referral_bonus["new_level"],
                            referral_bonus["old_percent"],
                            referral_bonus["new_percent"]
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка при отправке уведомления о повышении уровня: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке реферального бонуса: {e}", exc_info=True)
        
        # Получаем обновленный баланс
        user = await db.get_user(user_id)
        if currency == "arbuzz":
            balance = user.get("arbuzz_balance", 0) if user else 0
            balance_text = f"{balance:.0f} AC"
            currency_symbol = ""
        else:
            balance = user["balance"] if user else 0
            balance_text = f"${balance:.2f}"
            currency_symbol = "$"
        
        # Отправляем сообщение с результатом
        game_name = config.get("name", "Игра")
        game_emoticon = config.get("emoticon", "🎮")
        bet_type_name = get_bet_type_name(game_type, bet_type)
        
        # Форматируем ставки и выигрыш в зависимости от валюты
        if currency == "arbuzz":
            bet_str = f"{bet:.0f} AC"
            win_str = f"{win:.0f} AC" if is_win else f"{bet:.0f} AC"
        else:
            bet_str = f"${bet:.2f}"
            win_str = f"${win:.2f}" if is_win else f"${bet:.2f}"
        
        if is_win:
            text = f"""🎉 <b>Поздравляем! Вы выиграли!</b>

{game_emoticon} <b>{game_name}</b>

Игра - <b>{bet_type_name}</b>
Ставка - <b>{bet_str}</b>

💰 Выиграли: {win_str}
💰 Новый баланс: {balance_text}

Что хотите сделать дальше?"""
        else:
            text = f"""😔 <b>К сожалению, вы проиграли</b>

{game_emoticon} <b>{game_name}</b>

Игра - <b>{bet_type_name}</b>
Ставка - <b>{bet_str}</b>

💰 Потеряно: {bet_str}
💰 Новый баланс: {balance_text}

Что хотите сделать дальше?"""
        
        # Создаем клавиатуру с кнопками
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        result_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Повторить игру", callback_data="repeat_game"),
            ],
            [
                InlineKeyboardButton(text="🎮 Выбрать другую игру", callback_data="games_menu"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main"),
            ]
        ])
        
        await asyncio.sleep(random.uniform(3, 4))
        try:
            # Получаем message_id исходного сообщения пользователя из состояния
            original_message_id = state.get("original_message_id")
            
            # В группах используем reply на исходное сообщение пользователя, в личных чатах - обычное сообщение
            if original_message_id:
                # Проверяем тип чата через bot.get_chat
                try:
                    chat = await bot.get_chat(chat_id)
                    if chat.type in ['group', 'supergroup']:
                        await bot.send_message(
                            chat_id=chat_id, 
                            text=text, 
                            reply_markup=result_keyboard, 
                            parse_mode="HTML",
                            reply_to_message_id=original_message_id
                        )
                    else:
                        await bot.send_message(chat_id=chat_id, text=text, reply_markup=result_keyboard, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении информации о чате: {e}")
                    await bot.send_message(chat_id=chat_id, text=text, reply_markup=result_keyboard, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=result_keyboard, parse_mode="HTML")
            logger.info(f"✅ Сообщение с результатом игры отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке сообщения с результатом: {e}", exc_info=True)
        
        # Отправляем стикеры для каждого эмодзи результата в один ряд
        try:
            await send_result_stickers(bot, chat_id, game_type, throws, original_message_id)
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке стикеров результата: {e}", exc_info=True)
        
        # Сохраняем последнюю игру перед очисткой состояния (сохраняем custom_multiplier для ракетки)
        last_game_data = {
            "game_type": game_type,
            "bet_type": bet_type,
            "bet": bet,
            "currency": currency  # Сохраняем валюту
        }
        # Сохраняем custom_multiplier если это кастомная ставка
        if bet_type == "custom" and user_id in GAME_STATES:
            custom_multiplier = GAME_STATES[user_id].get("custom_multiplier")
            if custom_multiplier:
                last_game_data["custom_multiplier"] = custom_multiplier
        LAST_GAME[user_id] = last_game_data
        
        # Очищаем состояние и разблокируем кнопки
        if user_id in GAME_STATES:
            for msg_id, uid in list(DICE_MESSAGE_STATES.items()):
                if uid == user_id:
                    del DICE_MESSAGE_STATES[msg_id]
            del GAME_STATES[user_id]
        
        # Разблокируем кнопки для игр с несколькими бросками
        if user_id in ACTIVE_GAMES:
            del ACTIVE_GAMES[user_id]
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_game_result: {e}", exc_info=True)


def get_sticker_name_for_result(game_type: str, result: int) -> str:
    """Получить имя стикера для результата игры"""
    # Для кубика - просто число
    if game_type == "dice":
        return f"dice_{result}"
    
    # Для боулинга - количество сбитых кеглей
    if game_type == "bowling":
        if result == 6:  # В боулинге 6 = страйк (все кегли)
            return "bowling_strike"
        elif result == 0 or result == 1:
            return "bowling_miss"
        else:
            return f"bowling_{result}"
    
    # Для дартса - просто по значению dice (1-6)
    if game_type == "dart":
        return f"darts_{result}"
    
    # Для футбола - просто по значению dice (1-5)
    if game_type == "football":
        return f"football_{result}"
    
    # Для баскетбола - просто по значению dice (1-5)
    if game_type == "basketball":
        return f"basketball_{result}"
    
    # По умолчанию
    return f"{game_type}_{result}"


async def send_result_stickers(bot, chat_id: int, game_type: str, throws: list, original_message_id: int = None):
    """Отправить стикеры для каждого эмодзи результата в один ряд"""
    if not throws or len(throws) == 0:
        logger.warning("⚠️ Нет результатов для отправки стикеров")
        return
    
    try:
        # Определяем, является ли чат группой
        is_group = False
        if original_message_id:
            try:
                chat = await bot.get_chat(chat_id)
                is_group = chat.type in ['group', 'supergroup']
            except Exception as e:
                logger.warning(f"⚠️ Не удалось определить тип чата: {e}")
        
        # Получаем стикеры для каждого результата
        stickers_to_send = []
        for throw_result in throws:
            sticker_name = get_sticker_name_for_result(game_type, throw_result)
            sticker = await db.get_sticker(sticker_name)
            if sticker:
                stickers_to_send.append(sticker['file_id'])
                logger.info(f"✅ Найден стикер для {sticker_name}: {sticker['file_id']}")
            else:
                logger.warning(f"⚠️ Стикер {sticker_name} не найден в базе данных")
        
        # Отправляем все стикеры быстро последовательно, чтобы они были в один ряд
        if stickers_to_send:
            logger.info(f"📤 Отправляю {len(stickers_to_send)} стикеров в один ряд")
            for i, sticker_file_id in enumerate(stickers_to_send):
                try:
                    if is_group and original_message_id and i == 0:
                        # Первый стикер в группе - отвечаем на исходное сообщение
                        await bot.send_sticker(
                            chat_id=chat_id,
                            sticker=sticker_file_id,
                            reply_to_message_id=original_message_id
                        )
                    else:
                        # Остальные стикеры - отправляем без reply, чтобы они были рядом
                        await bot.send_sticker(
                            chat_id=chat_id,
                            sticker=sticker_file_id
                        )
                    # Минимальная задержка между стикерами для отправки в один ряд
                    if i < len(stickers_to_send) - 1:
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"❌ Ошибка при отправке стикера {i+1}/{len(stickers_to_send)}: {e}")
            logger.info(f"✅ Все стикеры отправлены успешно")
        else:
            logger.warning("⚠️ Нет стикеров для отправки")
    except Exception as e:
        logger.error(f"❌ Ошибка в send_result_stickers: {e}", exc_info=True)


async def process_dice_result_after_delay(bot, message_id: int, user_id: int, chat_id: int, 
                                          game_type: str, bet_type: str, bet: float, 
                                          required_throws: int, emoticon: str, currency: str = "dollar"):
    """Обрабатывает результат dice через некоторое время после отправки"""
    try:
        logger.info(f"🔍 Проверяем результат dice message_id={message_id} для пользователя {user_id}")
        
        # Проверяем состояние
        if user_id not in GAME_STATES:
            logger.warning(f"⚠️ Состояние игры не найдено для пользователя {user_id}")
            return
        
        state = GAME_STATES[user_id]
        # Получаем currency из состояния, если есть
        if "currency" in state:
            currency = state["currency"]
        current_throw = state.get("current_throw", 0)
        
        # Если требуются дополнительные броски — выполняем их здесь и сразу читаем значения из ответа
        while current_throw < required_throws:
            if current_throw > 0:
                # В групповых чатах отвечаем на исходное сообщение пользователя
                original_message_id = state.get("original_message_id")
                # Проверяем тип чата через bot.get_chat
                try:
                    chat_info = await bot.get_chat(chat_id)
                    is_group = chat_info.type in ['group', 'supergroup']
                except:
                    is_group = False
                
                if is_group and original_message_id:
                    # В группах отвечаем на сообщение пользователя
                    next_dice = await bot.send_dice(
                        chat_id=chat_id,
                        emoji=emoticon,
                        reply_to_message_id=original_message_id
                    )
                else:
                    # В личных чатах отправляем без reply
                    next_dice = await bot.send_dice(chat_id=chat_id, emoji=emoticon)
                state["throws"].append(next_dice.dice.value)
                state["dice_message_id"] = next_dice.message_id
                DICE_MESSAGE_STATES[next_dice.message_id] = user_id
                logger.info(f"✅ Бросок {current_throw + 1}/{required_throws}: value={next_dice.dice.value}")
            # Пауза между бросками для нескольких эмодзи ~ максимально быстрая (0.05 секунды)
            await asyncio.sleep(0.05)
            current_throw += 1
            state["current_throw"] = current_throw
        
        # Все броски выполнены — считаем результат
        await process_game_result(bot, user_id, chat_id, game_type, bet_type, bet, required_throws, emoticon, currency)
    except Exception as e:
        logger.error(f"❌ Ошибка в process_dice_result_after_delay: {e}", exc_info=True)


def get_bet_type_name(game_type: str, bet_type: str) -> str:
    """Преобразовать bet_type в читаемое название режима игры"""
    bet_type_names = {
        "dice": {
            "even": "Чет",
            "odd": "Нечет",
            "exact_1": "Точное число 1",
            "exact_2": "Точное число 2",
            "exact_3": "Точное число 3",
            "exact_4": "Точное число 4",
            "exact_5": "Точное число 5",
            "exact_6": "Точное число 6",
            "pair": "Пара",
            "3_even": "3 Чет",
            "3_odd": "3 Нечет",
            "18": "Сумма 18",
            "21": "Сумма 21",
            "111": "Три единицы",
            "333": "Три тройки",
            "666": "Три шестерки",
        },
        "dart": {
            "red": "Красное",
            "white": "Белое",
            "center": "Центр",
            "miss": "Отскок",
            "3_red": "3 Красных",
            "3_white": "3 Белых",
            "3_center": "3 в Центр",
            "3_miss": "3 Мимо",
        },
        "bowling": {
            "0-3": "0-3 кегли",
            "4-6": "4-6 кеглей",
            "strike": "Страйк",
            "miss": "Промах",
            "2_strike": "2 Страйка",
            "3_strike": "3 Страйка",
            "2_miss": "2 Мимо",
            "3_miss": "3 Мимо",
        },
        "football": {
            "goal": "Гол",
            "miss": "Промах",
            "center": "В центр",
            "hattrick": "Хет-трик",
            "5_goals": "5 Голов",
            "10_goals": "10 Голов",
            "6_miss": "6 Промахов",
        },
        "basketball": {
            "hit": "Гол",
            "miss": "Мимо",
            "clean": "Чистый гол",
            "stuck": "Застрял",
            "2_hit": "2 Попал",
            "2_clean": "2 Чистых",
            "3_hit": "3 Попал",
            "3_clean": "3 Чистых",
            "6_hit": "6 Попал",
        },
        "slots": {
            "3_axe": "3 Топора",
            "2_axe": "2 Топора",
            "3_cherry": "3 Вишни",
            "2_cherry": "2 Вишни",
            "3_lemon": "3 Лимона",
            "2_lemon": "2 Лимона",
            "3_bar": "3 BAR",
            "2_bar": "2 BAR",
        },
        "dice_7": {
            "less_7": "Меньше 7",
            "equal_7": "Равно 7",
            "more_7": "Больше 7",
        },
    }
    
    game_bet_types = bet_type_names.get(game_type, {})
    return game_bet_types.get(bet_type, bet_type)


def get_required_throws(bet_type: str, game_type: str = None) -> int:
    """Определить количество необходимых бросков для типа ставки"""
    # Ставки, требующие несколько бросков
    multi_throw_bets = {
        # Дартс - несколько бросков
        "3_red": 3, "3_white": 3, "3_center": 3, "3_miss": 3,
        # Кубик - несколько бросков
        "3_even": 3, "3_odd": 3, "111": 3, "333": 3, "666": 3,
        "18": 5, "21": 5, "pair": 2,
        # Боулинг - несколько бросков
        "2_strike": 2, "3_strike": 3, "2_miss": 2, "3_miss": 3,
        # Футбол - несколько бросков
        "hattrick": 3, "5_goals": 5, "10_goals": 10, "6_miss": 6,
        # Баскетбол - несколько бросков
        "2_hit": 2, "3_hit": 3, "2_clean": 2, "3_clean": 3, "6_hit": 6,
        # Кубик: +- 7 - всегда 2 броска
        "less_7": 2, "equal_7": 2, "more_7": 2,
    }
    result = multi_throw_bets.get(bet_type, 1)
    logger.info(f"🔍 get_required_throws: bet_type='{bet_type}', game_type='{game_type}' -> {result} бросков")
    return result


async def send_game_photo(callback: CallbackQuery, image_filename: str, text: str, keyboard):
    """Вспомогательная функция для отправки фото игры"""
    # Проверяем тип клавиатуры и тип чата
    from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
    is_group = callback.message.chat.type in ['group', 'supergroup']
    is_reply_keyboard = isinstance(keyboard, ReplyKeyboardMarkup)
    
    # В группах всегда скрываем ReplyKeyboardMarkup
    if is_group:
        if is_reply_keyboard:
            final_keyboard = ReplyKeyboardRemove(remove_keyboard=True)
        else:
            final_keyboard = keyboard  # InlineKeyboardMarkup или None
    else:
        final_keyboard = keyboard
    
    image_path = os.path.join(os.getcwd(), image_filename)
    if not os.path.exists(image_path):
        logger.warning(f"Файл {image_filename} не найден по пути: {image_path}")
        await _fallback_edit_message(callback, text, final_keyboard)
        return False

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
    
    async def _send_new_photo():
        # Создаем новый экземпляр для отправки
        if use_fs_input:
            photo = FSInputFile(image_path)
        else:
            photo = BufferedInputFile(photo_bytes, filename=image_filename)
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=final_keyboard,
            parse_mode="HTML"
        )

    try:
        if callback.message.photo:
            # Для редактирования медиа
            if use_fs_input:
                photo_for_edit = FSInputFile(image_path)
            else:
                photo_for_edit = BufferedInputFile(photo_bytes, filename=image_filename)
            media = InputMediaPhoto(media=photo_for_edit, caption=text, parse_mode="HTML")
            await callback.message.edit_media(media=media, reply_markup=final_keyboard)
        else:
            await _send_new_photo()
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении фото {image_filename}: {e}", exc_info=True)
        # Если редактирование не удалось, пробуем отправить новое сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        try:
            await _send_new_photo()
            return True
        except Exception as e2:
            logger.error(f"Ошибка при отправке нового фото {image_filename}: {e2}", exc_info=True)
            await _fallback_edit_message(callback, text, final_keyboard)
            return False


async def _fallback_edit_message(callback: CallbackQuery, text: str, keyboard):
    """Редактирование сообщения текстом, если изображения нет"""
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


def get_rules_text(game_type: str) -> str:
    """Получить текст правил для игры"""
    rules = {
        "dice": """🎲 <b>Правила</b>

🙏 Чет x1.9 - 1 четный бросок;
🙏 Нечет x1.9 - 1 нечетный бросок;
🙏 3 Чет x7 - 3 четных броска;
🙏 3 Нечет x7 - 3 нечетных подряд;
1️⃣ Точное число x5.55 - выпало выбранное число;
🫂 Пара x5.55 - 2 одинаковых броска;
🔞 18 x8 - 5 бросков с общей суммой 18;
💀 21 x11 - 5 бросков с общей суммой 21;
🍀 111 x100 - 3 броска, все единицы;
☘️ 333 x100 - 3 броска, все тройки;
🐍 666 x100 - 3 броска, все шестерки;

<i>Все анимации случайны и генерируются с помощью Telegram API</i>""",
        
        "dart": """🎯 <b>Правила</b>

⚪ Белое x2 - 1 бросок, попади в белое;
🔴 Красное x1.4 - 1 бросок, попади в красное;
🍏 Центр x6 - 1 бросок, попади в яблочко;
🌨️ Отскок x6 - 1 бросок, отскок;
🚩 3 Красных x7 - 3 броска, все в красное;
🥚 3 Белых x21 - 3 броска, все в белом;
🏹 3 в Центр x100 - трижды попади в яблочко;
🏹 3 Мимо x100 - трижды промахнись;

<i>Все анимации случайны и генерируются с помощью Telegram API</i>""",
        
        "bowling": """🎳 <b>Правила</b>

👌 0-3 шт х1.9 - сбей меньше 3-х кеглей;
✋ 4-6 шт х1.9 - сбей больше 3-х кеглей;
👏 Страйк х5 - сбей все кегли;
🤷 Промах х5 - промахнись;
💪 2 Страйка х30 - сбей все кегли дважды в ряд;
🎳 2 Мимо х30 - промахнись дважды;
🏆 3 Страйка х100 - сбей все кегли трижды в ряд;
🪦 3 Мимо х100 - промахнись трижды;

<i>Все анимации случайны и генерируются с помощью Telegram API</i>""",
        
        "football": """⚽ <b>Правила</b>

⚽ Гол x1.4 - забей гол;
🥅 Промах x2.5 - бей мимо ворот;
🎯 В центр x1.9 - попади в центр;
🎩 Хет-трик x4 - забей гол трижды в ряд;
🖐️ 5 Голов x11 - забей гол пять раз в ряд;
👑 10 Голов x100 - забей гол десять раз в ряд;
💀 6 Промахов x100 - промахнись шесть раз мимо ворот;

<i>Все анимации случайны и генерируются с помощью Telegram API</i>""",
        
        "basketball": """🏀 <b>Правила</b>

⚽ Гол x2 – закинь мяч в сетку;
👋 Мимо x1.4 – промахнись мимо сетки;
💧 Чистый гол x6 – закинь мяч в кольцо не касаясь сетки;
🔒 Застрял x5 – мяч застрял;
🔄 2 Попал x5 – дважды закинь мяч в сетку;
🌊 2 Чистых x15 - дважды закинь мяч в кольцо;
⚡ 3 Броска x12 – трижды закинь мяч в сетку;
🌪️ 3 Чистых x77 – трижды закинь мяч в кольцо;
🔥 6 Попал x100 - попади в сетку шесть раз в ряд;

<i>Все анимации случайны и генерируются с помощью Telegram API</i>""",
        
    }
    return rules.get(game_type, "Правила не найдены")


@router.callback_query(F.data.startswith("game_"))
async def handle_game_select(callback: CallbackQuery):
    """Обработка выбора игры"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    logger.info(f"🎮 Game select callback: {callback.data} from user {callback.from_user.id}")
    game_type = callback.data.split("_")[1]
    logger.info(f"🎮 Parsed game_type: {game_type}")
    
    if game_type not in GAME_CONFIGS:
        logger.warning(f"⚠️ Game type {game_type} not found in GAME_CONFIGS")
        return
    
    config = GAME_CONFIGS[game_type]
    user = await db.get_user(callback.from_user.id)
    user_id = callback.from_user.id
    
    # Проверяем, используется ли демо-баланс (арбузы)
    use_arbuzz = False
    base_bet = user.get("base_bet", 1.0) if user else 1.0
    balance = user.get("balance", 0.0) if user else 0.0
    arbuzz_balance = user.get("arbuzz_balance", 0.0) if user else 0.0
    
    # Если установлена базовая ставка в арбузах, используем арбузы
    if user_id in BASE_BET_ARBUZZ:
        use_arbuzz = True
        base_bet = BASE_BET_ARBUZZ[user_id]
        balance = arbuzz_balance
        balance_text = f"{balance:.0f} AC"
    # Если не установлена, но нет долларов, но есть арбузы - используем арбузы
    elif balance < base_bet and arbuzz_balance >= base_bet:
        use_arbuzz = True
        base_bet = BASE_BET_ARBUZZ.get(user_id, base_bet)
        balance = arbuzz_balance
        balance_text = f"{balance:.0f} AC"
        logger.info(f"🔄 Автоматически переключаемся на арбузы: долларов=${balance:.2f}, арбузов={arbuzz_balance:.0f}")
    else:
        balance_text = f"${balance:.2f}"
    
    # Для слотов и джекпотов специальная обработка
    if game_type == "slots":
        text = f"""🎰 <b>Слоты</b>

💰 <b>Баланс:</b> {balance_text}"""
        await send_game_photo(callback, "слоты.jpg", text, get_slots_keyboard())
        return
    
    # Для остальных игр показываем клавиатуру игры
    text = f"""{config["emoticon"]} <b>{config["name"]}</b>

💰 <b>Баланс:</b> {balance_text}

<b>Выберите ставку и тип ставки:</b>"""
    
    keyboard = get_game_keyboard(game_type, base_bet, currency="arbuzz" if use_arbuzz else "dollar")
    
    # Добавляем клавиатуру ставок в зависимости от типа игры
    if game_type == "dice":
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buttons = keyboard.inline_keyboard.copy()
        betting_kb = get_dice_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await send_game_photo(callback, "кубики.jpg", text, keyboard)
    elif game_type == "dart":
        from aiogram.types import InlineKeyboardMarkup
        buttons = keyboard.inline_keyboard.copy()
        betting_kb = get_dart_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await send_game_photo(callback, "дартс.jpg", text, keyboard)
    elif game_type == "bowling":
        from aiogram.types import InlineKeyboardMarkup
        buttons = keyboard.inline_keyboard.copy()
        betting_kb = get_bowling_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        # Для боулинга нет изображения, проверяем тип сообщения
        try:
            if callback.message.photo:
                # Если сообщение с фото, редактируем caption
                await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            else:
                # Если обычное сообщение, редактируем текст
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
            # Если не удалось отредактировать, отправляем новое сообщение
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    elif game_type == "football":
        from aiogram.types import InlineKeyboardMarkup
        buttons = keyboard.inline_keyboard.copy()
        betting_kb = get_football_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await send_game_photo(callback, "футбол.jpg", text, keyboard)
    elif game_type == "basketball":
        from aiogram.types import InlineKeyboardMarkup
        buttons = keyboard.inline_keyboard.copy()
        betting_kb = get_basketball_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await send_game_photo(callback, "баскетбол.jpg", text, keyboard)
    else:
        # Для других игр проверяем тип сообщения
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("bet_confirm_"))
async def handle_bet_confirm(callback: CallbackQuery):
    """Обработка подтверждения ставки (просто показывает что ставка выбрана)"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    parts = callback.data.split("_")
    if len(parts) < 4:
        return
    
    game_type = parts[2]
    try:
        bet_amount = float(parts[3])
    except (ValueError, IndexError):
        return


@router.callback_query(lambda c: c.data.startswith("bet_") and not c.data.startswith("bet_type_") and not c.data.startswith("bet_confirm_"))
async def handle_bet_select(callback: CallbackQuery):
    """Обработка выбора суммы ставки"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    parts = callback.data.split("_")
    if len(parts) < 3:
        return
    
    game_type = parts[1]
    try:
        bet_amount = float(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Неверная сумма ставки", show_alert=True)
        return
    
    if bet_amount < 0.1:
        await callback.answer("Минимальная ставка: $0.10", show_alert=True)
        return
    
    if bet_amount > MAX_BET:
        await callback.answer(f"Максимальная ставка: ${MAX_BET:.2f}", show_alert=True)
        return
    
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Проверяем, используется ли демо-баланс (арбузы)
    use_arbuzz = False
    balance = user.get("balance", 0.0)
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    
    # Если установлена базовая ставка в арбузах, используем арбузы
    if user_id in BASE_BET_ARBUZZ:
        use_arbuzz = True
        balance = arbuzz_balance
        balance_text = f"{balance:.0f} AC"
        bet_text = f"{bet_amount:.0f} AC"
    else:
        balance_text = f"${balance:.2f}"
        bet_text = f"${bet_amount:.2f}"
    
    # Обновляем базовую ставку (только для долларов)
    if not use_arbuzz:
        await db.update_setting(callback.from_user.id, "base_bet", bet_amount)
    
    config = GAME_CONFIGS.get(game_type, {})
    
    text = f"""{config.get("emoticon", "🎮")} <b>{config.get("name", "Игра")}</b>

💰 <b>Баланс:</b> {balance_text}
💰 <b>Ставка:</b> {bet_text}

<b>Выберите тип ставки:</b>"""
    
    keyboard = get_game_keyboard(game_type, bet_amount, currency="arbuzz" if use_arbuzz else "dollar")
    
    # Добавляем клавиатуру ставок в зависимости от типа игры
    from aiogram.types import InlineKeyboardMarkup
    buttons = keyboard.inline_keyboard.copy()
    
    if game_type == "dice":
        betting_kb = get_dice_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
    elif game_type == "dart":
        betting_kb = get_dart_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
    elif game_type == "bowling":
        betting_kb = get_bowling_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
    elif game_type == "football":
        betting_kb = get_football_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
    elif game_type == "basketball":
        betting_kb = get_basketball_betting_keyboard()
        buttons.extend(betting_kb.inline_keyboard)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Проверяем тип сообщения перед редактированием
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
        # Если не удалось отредактировать, отправляем новое сообщение
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def start_game_with_params(bot, user_id: int, chat_id: int, game_type: str, bet_type: str, bet: float, message_for_answer=None, callback_for_answer=None, currency: str = "dollar"):
    """Запускает игру с указанными параметрами"""
    user = await db.get_user(user_id)
    if not user:
        if callback_for_answer:
            await callback_for_answer.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        elif message_for_answer:
            # В группах используем reply, в личных чатах - answer
            if message_for_answer.chat.type in ['group', 'supergroup']:
                await message_for_answer.reply("❌ Ошибка: пользователь не найден")
            else:
                await message_for_answer.answer("❌ Ошибка: пользователь не найден")
        return False
    
    # Определяем баланс в зависимости от валюты
    if currency == "arbuzz":
        balance = user.get("arbuzz_balance", 0.0)
        balance_text = f"{balance:.0f} AC"
        currency_symbol = ""
        bet_display = f"{bet:.0f} AC"
    else:
        balance = user.get("balance", 0.0)
        balance_text = f"${balance:.2f}"
        currency_symbol = "$"
        bet_display = f"${bet:.2f}"
    
    # Проверка максимальной ставки (только для долларов)
    if currency == "dollar" and bet > MAX_BET:
        if callback_for_answer:
            await callback_for_answer.answer(f"❌ Максимальная ставка: ${MAX_BET:.2f}", show_alert=True)
        elif message_for_answer:
            # В группах используем reply, в личных чатах - answer
            if message_for_answer.chat.type in ['group', 'supergroup']:
                await message_for_answer.reply(f"❌ Максимальная ставка: ${MAX_BET:.2f}")
            else:
                await message_for_answer.answer(f"❌ Максимальная ставка: ${MAX_BET:.2f}")
        logger.warning(f"❌ Превышена максимальная ставка! Ставка=${bet:.2f}, максимум=${MAX_BET:.2f}")
        return False
    
    if balance < bet:
        # Используем callback.answer если доступен (для показа alert), иначе message.answer/reply
        if callback_for_answer:
            await callback_for_answer.answer(f"❌ Недостаточно средств! Нужно {bet_display}, у вас {balance_text}", show_alert=True)
        elif message_for_answer:
            # В группах используем reply, в личных чатах - answer
            if message_for_answer.chat.type in ['group', 'supergroup']:
                await message_for_answer.reply(f"❌ Недостаточно средств! Нужно {bet_display}, у вас {balance_text}")
            else:
                await message_for_answer.answer(f"❌ Недостаточно средств! Нужно {bet_display}, у вас {balance_text}")
        logger.warning(f"❌ Недостаточно средств в start_game_with_params! Баланс={balance_text}, нужно={bet_display}")
        return False
    
    # Списываем баланс сразу при начале игры
    if currency == "arbuzz":
        # Списываем арбузы
        await db.update_arbuzz_balance(user_id, -bet)
        logger.info(f"💰 Списан демо-баланс: {bet:.0f} AC для пользователя {user_id}")
    else:
        # Списываем доллары
        # Уменьшаем отыгрыш при ставке (только для долларов)
        await db.decrease_rollover(user_id, bet)
        await db.update_balance(user_id, -bet)
        logger.info(f"💰 Списан баланс: ${bet:.2f} для пользователя {user_id}")
    
    # Отправляем dice через Telegram API
    config = GAME_CONFIGS.get(game_type)
    if not config:
        if message_for_answer:
            # В группах используем reply, в личных чатах - answer
            if message_for_answer.chat.type in ['group', 'supergroup']:
                await message_for_answer.reply("Игра не найдена")
            else:
                await message_for_answer.answer("Игра не найдена")
        return False
    
    # Получаем эмодзи для игры - явно указываем для каждой игры
    if game_type == "dart":
        emoticon = "🎯"
    elif game_type == "bowling":
        emoticon = "🎳"
    elif game_type == "dice":
        emoticon = "🎲"
    elif game_type == "basketball":
        emoticon = "🏀"
    elif game_type == "football":
        emoticon = "⚽"
    elif game_type == "slots":
        emoticon = "🎰"
    else:
        emoticon = "🎲"  # По умолчанию кубик
    
    logger.info(f"🎯 Игра: {game_type}, Эмодзи: '{emoticon}', Тип ставки: {bet_type}")
    
    # Определяем количество необходимых бросков
    required_throws = get_required_throws(bet_type, game_type)
    
    logger.info(f"📊 Для ставки {bet_type} (игра {game_type}) требуется {required_throws} бросков")
    
    # Для dice_7 всегда нужно 2 броска
    if game_type == "dice_7":
        required_throws = 2
    
    # Отправляем первый dice и сохраняем информацию о ставке
    # В групповых чатах используем reply_to_message_id, чтобы эмодзи отправлялись как ответ на сообщение пользователя
    if message_for_answer:
        if message_for_answer.chat.type in ['group', 'supergroup']:
            # В группах отвечаем на сообщение пользователя
            dice_message = await bot.send_dice(
                chat_id=message_for_answer.chat.id,
                emoji=emoticon,
                reply_to_message_id=message_for_answer.message_id
            )
        else:
            # В личных чатах используем обычный answer_dice
            dice_message = await message_for_answer.answer_dice(emoji=emoticon)
    else:
        dice_message = await bot.send_dice(chat_id=chat_id, emoji=emoticon)
    
    logger.info(f"✅ Первый dice отправлен для игры {game_type}, эмодзи: '{emoticon}', пользователь {user_id}, ставка {bet}, тип {bet_type}, нужно бросков: {required_throws}")
    logger.info(f"📌 Dice message_id: {dice_message.message_id}, chat_id: {dice_message.chat.id}")
    
    # Определяем message_id исходного сообщения пользователя
    original_message_id = None
    if message_for_answer:
        # Если есть reply_to_message, используем его (это исходное сообщение пользователя)
        if message_for_answer.reply_to_message:
            original_message_id = message_for_answer.reply_to_message.message_id
        else:
            # Иначе используем само сообщение (для текстовых команд это сообщение пользователя)
            original_message_id = message_for_answer.message_id
    
    # Сохраняем данные о ставке и первый реальный бросок
    game_state = {
        "dice_message_id": dice_message.message_id,
        "game_type": game_type,
        "bet_type": bet_type,
        "bet": bet,
        "chat_id": chat_id,
        "user_id": user_id,
        "required_throws": required_throws,
        "throws": [dice_message.dice.value],  # первый бросок сразу известен из ответа
        "current_throw": 1,
        "emoticon": emoticon,
        "last_dice_message_id": dice_message.message_id,  # Сохраняем последний message_id
        "started_at": time.time(),
        "original_message_id": original_message_id,  # Сохраняем message_id исходного сообщения пользователя
    }
    
    GAME_STATES[user_id] = game_state
    DICE_MESSAGE_STATES[dice_message.message_id] = user_id
    
    logger.info(f"✅ Состояние игры сохранено для пользователя {user_id}: {game_state}")
    logger.info(f"📊 Всего состояний: {len(GAME_STATES)}, DICE_MESSAGE_STATES: {len(DICE_MESSAGE_STATES)}")
    
    # Сохраняем валюту в состояние игры
    game_state["currency"] = currency
    
    # Запускаем задачу для проверки результата dice через некоторое время
    # В aiogram 3.x результат dice может приходить не через обработчик сообщений
    asyncio.create_task(process_dice_result_after_delay(
        bot,
        dice_message.message_id,
        user_id,
        chat_id,
        game_type,
        bet_type,
        bet,
        required_throws,
        emoticon,
        currency  # Используем переданную валюту
    ))
    
    return True


async def start_game_from_text(message: Message, game_type: str, bet_type: str, bet: float, state: FSMContext = None):
    """Запускает игру из текстовой команды (для групп)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Определяем валюту из состояния, если есть
    currency = "dollar"
    if state:
        state_data = await state.get_data()
        currency = state_data.get("currency", "dollar")
    
    # Используем существующую функцию start_game_with_params
    success = await start_game_with_params(
        message.bot,
        user_id,
        chat_id,
        game_type,
        bet_type,
        bet,
        message_for_answer=message,
        callback_for_answer=None,
        currency=currency
    )
    
    if not success:
        await message.reply("❌ Ошибка при запуске игры")
    
    return success


@router.callback_query(F.data.startswith("bet_type_"))
async def handle_bet_type(callback: CallbackQuery):
    """Обработка выбора типа ставки"""
    logger.info(f"🎯 handle_bet_type вызван: callback.data = {callback.data}")
    # Убираем префикс "bet_type_"
    data_without_prefix = callback.data[9:]  # "bet_type_" = 9 символов
    
    # Специальная обработка для dice_7
    if data_without_prefix.startswith("dice_7_"):
        game_type = "dice_7"
        bet_type = data_without_prefix[7:]  # Убираем "dice_7_"
    else:
        # Обычный парсинг для других игр
        parts = data_without_prefix.split("_", 1)  # Разделяем только на первую часть
        if len(parts) == 2:
            game_type = parts[0]
            bet_type = parts[1]
        else:
            game_type = parts[0]
            bet_type = ""
    
    logger.info(f"🎯 Парсинг: game_type = {game_type}, bet_type = {bet_type}")
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли активная игра с несколькими бросками
    if is_user_busy(user_id):
        await callback.answer("⏳ Игра уже идет, подождите завершения...", show_alert=True)
        return
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    # Проверяем, используется ли демо-баланс (арбузы)
    use_arbuzz = False
    base_bet = user.get("base_bet", 1.0)
    balance = user.get("balance", 0.0)
    arbuzz_balance = user.get("arbuzz_balance", 0.0)
    
    # Если установлена базовая ставка в арбузах, используем арбузы
    if user_id in BASE_BET_ARBUZZ:
        use_arbuzz = True
        base_bet = BASE_BET_ARBUZZ[user_id]
        balance = arbuzz_balance
        balance_text = f"{balance:.0f} AC"
        bet_text = f"{base_bet:.0f} AC"
    else:
        balance_text = f"${balance:.2f}"
        bet_text = f"${base_bet:.2f}"
    
    # Проверяем максимальную ставку (только для долларов)
    if not use_arbuzz and base_bet > MAX_BET:
        await callback.answer(f"❌ Максимальная ставка: ${MAX_BET:.2f}", show_alert=True)
        return
    
    # Проверяем баланс ДО отправки ответа и добавления в ACTIVE_GAMES
    logger.info(f"💰 Проверка баланса: баланс={balance_text}, ставка={bet_text}, достаточно={balance >= base_bet}")
    if balance < base_bet:
        logger.warning(f"❌ Недостаточно средств! Баланс={balance_text}, нужно={bet_text}")
        await callback.answer(f"❌ Недостаточно средств! Нужно {bet_text}, у вас {balance_text}", show_alert=True)
        return
    
    # Только после всех проверок отправляем подтверждение
    await callback.answer("Ставка принята, ожидайте результат...")  # Моментальный ответ на нажатие кнопки
    
    required_throws = get_required_throws(bet_type, game_type)
    
    # Для dice_7 всегда нужно 2 броска
    if game_type == "dice_7":
        required_throws = 2
    
    # Если требуется несколько бросков, блокируем кнопки
    if required_throws > 1:
        ACTIVE_GAMES[user_id] = time.time()
        # Отредактируем сообщение, показав что игра идет
        try:
            config = GAME_CONFIGS.get(game_type, {})
            game_emoticon = config.get("emoticon", "🎮")
            text = f"""{game_emoticon} <b>{config.get("name", "Игра")}</b>

💰 <b>Баланс:</b> {balance_text}
💰 <b>Ставка:</b> {bet_text}

⏳ <b>Игра идет, ожидайте результат...</b>"""
            from aiogram.types import InlineKeyboardMarkup
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[]), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
    
    # Определяем валюту
    currency_str = "arbuzz" if use_arbuzz else "dollar"
    
    # Запускаем игру (передаем callback для показа alert при ошибках)
    game_started = await start_game_with_params(
        callback.bot,
        user_id,
        callback.message.chat.id,
        game_type,
        bet_type,
        base_bet,
        callback.message,
        callback,  # Передаем callback для показа alert
        currency=currency_str  # Передаем валюту
    )
    
    # Если игра не запустилась (например, из-за недостатка средств), очищаем состояние
    if not game_started:
        if user_id in ACTIVE_GAMES:
            del ACTIVE_GAMES[user_id]
        if user_id in GAME_STATES:
            del GAME_STATES[user_id]


@router.callback_query(F.data == "repeat_game")
async def handle_repeat_game(callback: CallbackQuery):
    """Обработка кнопки 'Повторить игру'"""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли активная игра
    if is_user_busy(user_id):
        await callback.answer("⏳ Игра уже идет, подождите завершения...", show_alert=True)
        return
    
    # Проверяем, есть ли сохраненная последняя игра
    if user_id not in LAST_GAME:
        await callback.answer("Нет сохраненной игры для повтора", show_alert=True)
        return
    
    last_game = LAST_GAME[user_id]
    game_type = last_game["game_type"]
    bet_type = last_game["bet_type"]
    bet = last_game["bet"]
    currency = last_game.get("currency", "dollar")  # Получаем валюту из последней игры
    custom_multiplier = last_game.get("custom_multiplier")  # Восстанавливаем кастомный множитель
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    # Получаем баланс в зависимости от валюты
    if currency == "arbuzz":
        balance = user.get("arbuzz_balance", 0.0)
        balance_text = f"{balance:.0f} AC"
        bet_text = f"{bet:.0f} AC"
    else:
        balance = user.get("balance", 0.0)
        balance_text = f"${balance:.2f}"
        bet_text = f"${bet:.2f}"
    
    # Проверяем баланс ДО отправки ответа и добавления в ACTIVE_GAMES
    logger.info(f"💰 Проверка баланса (повтор): баланс={balance_text}, ставка={bet_text}, достаточно={balance >= bet}")
    if balance < bet:
        logger.warning(f"❌ Недостаточно средств! Баланс={balance_text}, нужно={bet_text}")
        await callback.answer(f"❌ Недостаточно средств! Нужно {bet_text}, у вас {balance_text}", show_alert=True)
        return
    
    # Только после всех проверок отправляем подтверждение
    await callback.answer("Повторяем игру...")  # Моментальный ответ на нажатие кнопки
    
    required_throws = get_required_throws(bet_type, game_type)
    
    # Для dice_7 всегда нужно 2 броска
    if game_type == "dice_7":
        required_throws = 2
    
    # Если требуется несколько бросков, блокируем кнопки
    if required_throws > 1:
        ACTIVE_GAMES[user_id] = time.time()
    
    # Запускаем игру с теми же параметрами (передаем callback для показа alert при ошибках)
    game_started = await start_game_with_params(
        callback.bot,
        user_id,
        callback.message.chat.id,
        game_type,
        bet_type,
        bet,
        callback.message,
        callback,  # Передаем callback для показа alert
        currency=currency  # Передаем валюту из последней игры
    )
    
    # Если игра не запустилась (например, из-за недостатка средств), очищаем состояние
    if not game_started:
        if user_id in ACTIVE_GAMES:
            del ACTIVE_GAMES[user_id]
        if user_id in GAME_STATES:
            del GAME_STATES[user_id]


# Обработчик ввода кастомного множителя для ракетки
# ВАЖНО: Этот обработчик должен проверять состояние, чтобы не перехватывать все сообщения
# Также исключаем кнопки главного меню
MAIN_MENU_BUTTONS = ["💼 Кошелек", "🎮 Игры", "👤 Профиль", "⚙️ Настройки", "💬 Поддержка", "👯 Рефералы", "➕ Депозит"]

@router.message(
    lambda m: (m.text and 
               not m.text.startswith("/") and
               m.text not in MAIN_MENU_BUTTONS and
               m.from_user.id in GAME_STATES and
               GAME_STATES.get(m.from_user.id, {}).get("waiting_custom_multiplier", False))
)
async def handle_custom_multiplier(message: Message):
    """Обработка ввода кастомного множителя для ракетки"""
    user_id = message.from_user.id
    
    logger.info(f"🚀 Обработка ввода кастомного множителя для пользователя {user_id}")
    
    # Получаем состояние
    state = GAME_STATES[user_id]
    
    try:
        multiplier = float(message.text.replace(",", "."))
        
        if multiplier < 1.0 or multiplier > 100.0:
            if message.chat.type in ['group', 'supergroup']:
                await message.reply("❌ Множитель должен быть от 1.0 до 100.0")
            else:
                await message.answer("❌ Множитель должен быть от 1.0 до 100.0")
            return
        
        # Сохраняем кастомный множитель
        state["custom_multiplier"] = multiplier
        state["waiting_custom_multiplier"] = False
        
        game_type = state.get("game_type", "dice")
        bet = state.get("bet", 1.0)
        
        user = await db.get_user(user_id)
        if not user:
            if message.chat.type in ['group', 'supergroup']:
                await message.reply("❌ Ошибка: пользователь не найден")
            else:
                await message.answer("❌ Ошибка: пользователь не найден")
            del GAME_STATES[user_id]
            return
        
        balance = user["balance"]
        
        if balance < bet:
            if message.chat.type in ['group', 'supergroup']:
                await message.reply(f"❌ Недостаточно средств! Нужно ${bet:.2f}, у вас ${balance:.2f}")
            else:
                await message.answer(f"❌ Недостаточно средств! Нужно ${bet:.2f}, у вас ${balance:.2f}")
            del GAME_STATES[user_id]
            return
        
        # Запускаем игру с кастомным множителем
        if message.chat.type in ['group', 'supergroup']:
            await message.reply("✅ Множитель принят! Запускаем ракетку...")
        else:
            await message.answer("✅ Множитель принят! Запускаем ракетку...")
        
        game_started = await start_game_with_params(
            message.bot,
            user_id,
            message.chat.id,
            game_type,
            "custom",  # Используем "custom" как bet_type
            bet,
            message,
            None
        )
        
        if not game_started:
            if user_id in GAME_STATES:
                del GAME_STATES[user_id]
    
    except ValueError:
        if message.chat.type in ['group', 'supergroup']:
            await message.reply("❌ Неверный формат. Введите число (например: 2.5 или 10)")
        else:
            await message.answer("❌ Неверный формат. Введите число (например: 2.5 или 10)")


# Обработчик команд "куб 7+", "куб 7-", "куб 7" ТОЛЬКО для групп
@router.message(
    F.text.regexp(re.compile(r'^(куб|кубик)\s*7\s*([+\-])?$', re.IGNORECASE)) &
    F.chat.type.in_(["group", "supergroup"])
)
async def handle_dice_7_command(message: Message, state: FSMContext):
    """Обработка команд 'куб 7+', 'куб 7-', 'куб 7' для игры Кубик: +- 7"""
    try:
        text_clean = message.text.strip().lower()
        user_id = message.from_user.id
        
        match = re.match(r'^(куб|кубик)\s*7\s*([+\-])?$', text_clean)
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
        
        # Получаем пользователя
        user = await db.get_user(user_id)
        if not user:
            username = message.from_user.username or f"user_{user_id}"
            await db.create_user(user_id, username)
            user = await db.get_user(user_id)
        
        if not user:
            return
        
        # Проверяем, используется ли демо-баланс (арбузы)
        use_arbuzz = "арбуз" in text_clean or " ac" in text_clean or text_clean.endswith("ac")
        
        # Получаем базовую ставку
        if use_arbuzz:
            # Используем базовую ставку для арбузов, если установлена
            base_bet = BASE_BET_ARBUZZ.get(user_id, user.get("base_bet", 1.0))
            balance = user.get("arbuzz_balance", 0.0)
            balance_text = f"{balance:.0f} AC"
            bet_display = f"{base_bet:.0f} AC"
        else:
            base_bet = user.get("base_bet", 1.0)
            balance = user.get("balance", 0.0)
            balance_text = f"${balance:.2f}"
            bet_display = f"${base_bet:.2f}"
        
        # Если не указано явно, но нет долларов, но есть арбузы - используем арбузы
        if not use_arbuzz:
            balance_usd = user.get("balance", 0.0)
            arbuzz_balance = user.get("arbuzz_balance", 0.0)
            if balance_usd < base_bet and arbuzz_balance >= base_bet:
                use_arbuzz = True
                base_bet = BASE_BET_ARBUZZ.get(user_id, base_bet)
                balance = arbuzz_balance
                balance_text = f"{balance:.0f} AC"
                bet_display = f"{base_bet:.0f} AC"
                logger.info(f"🔄 Автоматически переключаемся на арбузы: долларов=${balance_usd:.2f}, арбузов={arbuzz_balance:.0f}")
        
        # Проверяем баланс
        if balance < base_bet:
            if message.chat.type in ['group', 'supergroup']:
                await message.reply(f"❌ Недостаточно средств! Нужно {bet_display}, у вас {balance_text}")
            else:
                await message.answer(f"❌ Недостаточно средств! Нужно {bet_display}, у вас {balance_text}")
            return
        
        # Проверяем, не занят ли пользователь другой игрой
        if is_user_busy(user_id):
            if message.chat.type in ['group', 'supergroup']:
                await message.reply("⏳ У вас уже идет игра, подождите завершения...")
            else:
                await message.answer("⏳ У вас уже идет игра, подождите завершения...")
            return
        
        logger.info(f"🎲 Запуск игры 'Кубик: +- 7' с типом ставки: {bet_type}, команда: '{text_clean}', валюта: {'арбузы' if use_arbuzz else 'доллары'}")
        
        currency_str = "arbuzz" if use_arbuzz else "dollar"
        game_started = await start_game_with_params(
            message.bot,
            user_id,
            message.chat.id,
            "dice_7",
            bet_type,
            base_bet,
            message,
            None,
            currency=currency_str
        )
        
        if not game_started:
            if message.chat.type in ['group', 'supergroup']:
                await message.reply("❌ Не удалось запустить игру. Проверьте баланс.")
            else:
                await message.answer("❌ Не удалось запустить игру. Проверьте баланс.")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды 'Кубик: +- 7': {e}", exc_info=True)


# Обработчик быстрых команд для игр в личном чате бота
# ОТКЛЮЧЕНО: Команды типа "куб 4" работают ТОЛЬКО в группах, не в личных чатах
# Это необходимо, чтобы кнопки бота работали корректно в личных чатах
# Весь код функции handle_text_game_command_private удален


# Обработчик текстовых команд для игр в группах
# ВАЖНО: Этот обработчик должен быть ПЕРВЫМ для обработки игровых команд
@router.message(
    F.text & 
    F.chat.type.in_(["group", "supergroup"])
)
async def handle_text_game_command(message: Message):
    """Обработка текстовых команд для игр в групповых чатах"""
    try:
        text = message.text.strip().lower()
        user_id = message.from_user.id
        
        # Логирование для отладки
        logger.info(f"🎮 handle_text_game_command вызван: text='{text}', user_id={user_id}")
        
        # Пропускаем команды PvP - они обрабатываются в pvp_router
        if text.startswith("pvp") or text.startswith("пвп"):
            logger.debug(f"⚠️ Пропускаем PvP команду: {text}")
            return
        
        # Пропускаем команды из group_commands.py - они обрабатываются там
        # Команды: деп, пополнить, баланс, балик, б, игры, топ, профиль, статистика, кошелек, вб, вывод, чек, отправить, /send
        group_commands = [
            "деп", "пополнить", "баланс", "балик", "б", "игры", "топ", 
            "профиль", "статистика", "кошелек", "вб", "вывод", "чек", 
            "отправить", "/send"
        ]
        
        # Проверяем, является ли это командой из group_commands
        import re
        # Проверяем точные совпадения
        if text in group_commands:
            return
        
        # Проверяем команды с параметрами (деп 100, пополнить 50, вывод 10, и т.д.)
        if re.match(r'^(деп|пополнить|вывод|отправить|/send)\s+', text):
            logger.debug(f"⚠️ Пропускаем команду с параметрами: {text}")
            return
        
        # Команды с $ (10$, 100$) обрабатываются в group_commands.py, пропускаем их здесь
        if re.match(r'^[\d.,]+\s*\$$', text):
            logger.debug(f"⚠️ Пропускаем команду с $: {text}")
            return
        
        # Команды PvP/пвп
        if re.match(r'^(pvp|пвп)\s+', text, re.IGNORECASE):
            logger.debug(f"⚠️ Пропускаем PvP команду: {text}")
            return
        
        # ОБРАБОТКА ФОРМАТА "число арбуз/арбузов" - установка базовой ставки в арбузах
        # Поддерживаем: "1 арбуз", "10 арбузов", "5 арбуза", "3 арбузы", "1 арбуз", "1арбуз" и т.д.
        arbuzz_pattern = re.match(r'^(\d+)\s*арбуз(ов|а|ы|е)?$', text, re.IGNORECASE)
        if arbuzz_pattern:
            bet_amount = float(arbuzz_pattern.group(1))
            logger.info(f"🍉 Обнаружена установка базовой ставки в арбузах: {bet_amount} AC, текст: '{text}'")
            
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
            user = await db.get_user(user_id)
            if not user:
                username = message.from_user.username or f"user_{user_id}"
                await db.create_user(user_id, username)
                user = await db.get_user(user_id)
            
            if not user:
                return
            
            # Сохраняем базовую ставку для арбузов в глобальное хранилище
            BASE_BET_ARBUZZ[user_id] = bet_amount
            
            # Выводим сообщение об установке ставки
            await message.reply(f"✅ <b>Базовая ставка установлена:</b> {bet_amount:.0f} AC", parse_mode="HTML")
            
            logger.info(
                f"💰 Базовая ставка в арбузах установлена: "
                f"user_id={user_id}, bet_amount={bet_amount} AC"
            )
            
            return
        
        # Получаем пользователя ДО всех проверок
        user = await db.get_user(user_id)
        if not user:
            # Создаем пользователя, если его нет
            username = message.from_user.username or f"user_{user_id}"
            await db.create_user(user_id, username)
            user = await db.get_user(user_id)
        
        if not user:
            return
        
        # Проверяем, не занят ли пользователь другой игрой
        if is_user_busy(user_id):
            await message.reply("⏳ У вас уже идет игра, подождите завершения...")
            return
        
        # Парсим команду
        import re
        
        # Убираем лишние пробелы и приводим к нижнему регистру
        text_clean = re.sub(r'\s+', ' ', text).strip().lower()
        
        # Команды "куб 7+", "куб 7-", "куб 7" обрабатываются отдельным обработчиком handle_dice_7_command
        
        # ОСОБАЯ ОБРАБОТКА ДЛЯ КУБИКА - поддерживаем все типы ставок
        # Сначала определяем game_patterns
        game_patterns = {
            "dice": {
                "patterns": ["кубик", "кубики", "🎲", "dice", "кости", "костя", "куб", "кубы"],
                "name": "Кубик",
                "min": 1,
                "max": 6
            },
        }
        dice_patterns = game_patterns["dice"]["patterns"]
        is_dice_command = any(pattern in text_clean for pattern in dice_patterns)
        
        if is_dice_command:
            logger.info(f"🎲 Обнаружена команда кубика: text_clean='{text_clean}'")
            
            # Проверяем, используется ли демо-баланс (арбузы)
            use_arbuzz = False
            base_bet = user.get("base_bet", 1.0)
            balance = user.get("balance", 0.0)
            arbuzz_balance = user.get("arbuzz_balance", 0.0)
            
            # Если установлена базовая ставка в арбузах, используем арбузы
            if user_id in BASE_BET_ARBUZZ:
                use_arbuzz = True
                base_bet = BASE_BET_ARBUZZ[user_id]
                balance = arbuzz_balance
            # Если не установлена, но нет долларов, но есть арбузы - используем арбузы
            elif balance < base_bet and arbuzz_balance >= base_bet:
                use_arbuzz = True
                base_bet = BASE_BET_ARBUZZ.get(user_id, base_bet)
                balance = arbuzz_balance
                logger.info(f"🔄 Автоматически переключаемся на арбузы: долларов=${user.get('balance', 0.0):.2f}, арбузов={arbuzz_balance:.0f}")
            
            # Проверяем баланс
            if balance < base_bet:
                balance_text = f"{balance:.0f} AC" if use_arbuzz else f"${balance:.2f}"
                bet_text = f"{base_bet:.0f} AC" if use_arbuzz else f"${base_bet:.2f}"
                await message.reply(f"❌ Недостаточно средств! Нужно {bet_text}, у вас {balance_text}")
                return
            
            # Специальные комбинации для кубика (проверяем в порядке приоритета)
            bet_type = None
            game_type = "dice"
            
            # 1. Специальные комбинации: 111, 333, 666
            if "111" in text_clean:
                bet_type = "111"
                logger.info(f"✅ Определен тип ставки: 111")
            elif "333" in text_clean:
                bet_type = "333"
                logger.info(f"✅ Определен тип ставки: 333")
            elif "666" in text_clean:
                bet_type = "666"
                logger.info(f"✅ Определен тип ставки: 666")
            # 2. Суммы: 18, 21
            elif "18" in text_clean and "21" not in text_clean:
                bet_type = "18"
            elif "21" in text_clean:
                bet_type = "21"
            # 3. 3 четных / 3 нечетных
            elif re.search(r'3\s*чет|три\s*чет|3\s*even', text_clean):
                bet_type = "3_even"
            elif re.search(r'3\s*нечет|три\s*нечет|3\s*odd', text_clean):
                bet_type = "3_odd"
            # 4. Четное / Нечетное
            elif re.search(r'\bчет|\beven', text_clean):
                bet_type = "even"
            elif re.search(r'\bнечет|\bodd', text_clean):
                bet_type = "odd"
            # 5. Пара
            elif re.search(r'\bпара|\bpair', text_clean):
                bet_type = "pair"
            # 6. Точное число (1-6)
            else:
                numbers = re.findall(r'\d+', text_clean)
                if numbers:
                    number = int(numbers[0])
                    if 1 <= number <= 6:
                        bet_type = f"exact_{number}"
            
            if bet_type:
                currency_str = "arbuzz" if use_arbuzz else "dollar"
                
                # Запускаем игру
                logger.info(
                    f"🎮 Запуск игры кубик из текстовой команды: "
                    f"user_id={user_id}, bet_type={bet_type}, bet={base_bet}, currency={currency_str}, text='{text}'"
                )
                
                game_started = await start_game_with_params(
                    message.bot,
                    user_id,
                    message.chat.id,
                    game_type,
                    bet_type,
                    base_bet,
                    message,
                    None,
                    currency=currency_str
                )
                
                if not game_started:
                    await message.reply("❌ Не удалось запустить игру. Проверьте баланс.")
                
                return
            else:
                logger.warning(f"⚠️ Не удалось определить тип ставки для команды кубика: text='{text_clean}'")
        
        # ОБРАБОТКА ДЛЯ ДРУГИХ ИГР (дартс, боулинг, футбол, баскетбол)
        # Извлекаем все числа из текста
        numbers = re.findall(r'\d+', text_clean)
        
        if not numbers:
            # Если нет числа, не обрабатываем
            return
        
        number = int(numbers[0])
        
        # Ищем паттерн игры в тексте (кроме кубика, он уже обработан)
        for game_type, game_info in game_patterns.items():
            if game_type == "dice":
                continue  # Кубик уже обработан
            
            for pattern in game_info["patterns"]:
                # Проверяем различные варианты: "дартс 3", "3 дартс", "дартс3", "3дартс"
                pattern_lower = pattern.lower()
                text_lower = text_clean.lower()
                
                # Варианты расположения: паттерн перед числом, число перед паттерном, вместе
                if (pattern_lower in text_lower and 
                    (text_lower.startswith(pattern_lower) or 
                     text_lower.endswith(pattern_lower) or
                     f"{pattern_lower} {number}" in text_lower or
                     f"{number} {pattern_lower}" in text_lower or
                     f"{pattern_lower}{number}" in text_lower or
                     f"{number}{pattern_lower}" in text_lower)):
                    
                    min_val = game_info["min"]
                    max_val = game_info["max"]
                    
                    # Проверяем диапазон
                    if number < min_val or number > max_val:
                        await message.reply(
                            f"❌ Для {game_info['name']} можно выбрать число от {min_val} до {max_val}"
                        )
                        return
                    
                    # Формируем тип ставки (для других игр только exact)
                    bet_type = f"exact_{number}"
                    
                    # Запускаем игру
                    logger.info(
                        f"🎮 Запуск игры из текстовой команды: "
                        f"user_id={user_id}, game_type={game_type}, "
                        f"bet_type={bet_type}, bet={base_bet}, text='{text}'"
                    )
                    
                    game_started = await start_game_with_params(
                        message.bot,
                        user_id,
                        message.chat.id,
                        game_type,
                        bet_type,
                        base_bet,
                        message,
                        None
                    )
                    
                    if not game_started:
                        await message.reply("❌ Не удалось запустить игру. Проверьте баланс.")
                    
                    return
        
        # Если команда не распознана, просто выходим без ответа
        # Не логируем, чтобы не спамить логи обычными сообщениями
        return
        
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_text_game_command: {e}", exc_info=True)


# Пробуем разные способы фильтрации
@router.message(F.dice)
async def handle_dice_result(message: Message):
    """Обработка результата dice - ТОЛЬКО для dice, отправленных ботом"""
    try:
        logger.info(f"🎲🎲🎲 ПОЛУЧЕН DICE РЕЗУЛЬТАТ! 🎲🎲🎲")
        logger.info(f"🎲 Message ID: {message.message_id}, Chat ID: {message.chat.id}")
        logger.info(f"🎲 From user: {message.from_user.id if message.from_user else 'None'}")
        logger.info(f"🎲 Dice value: {message.dice.value if message.dice else 'None'}")
        logger.info(f"🎲 Dice emoji: {message.dice.emoji if message.dice else 'None'}")
        logger.info(f"🎲 Доступные состояния: {list(GAME_STATES.keys())}")
        logger.info(f"🎲 DICE_MESSAGE_STATES: {list(DICE_MESSAGE_STATES.keys())}")
    except Exception as e:
        logger.error(f"❌ Ошибка в начале handle_dice_result: {e}", exc_info=True)
        return
    
    # КРИТИЧЕСКИ ВАЖНО: Обрабатываем ТОЛЬКО dice, отправленные ботом
    # Проверяем, что отправитель - бот (когда бот отправляет dice, from_user.id == bot.id)
    bot_info = await message.bot.get_me()
    bot_id = bot_info.id
    
    if message.from_user and message.from_user.id != bot_id:
        # Это dice от пользователя, игнорируем
        logger.info(f"⚠️ Игнорируем dice от пользователя {message.from_user.id} (не от бота). Message ID: {message.message_id}")
        return
    
    # Дополнительная проверка: dice должен быть в DICE_MESSAGE_STATES (это означает, что бот его отправил)
    user_id = DICE_MESSAGE_STATES.get(message.message_id)
    
    if not user_id or user_id not in GAME_STATES:
        # Dice не найден в списке отправленных ботом - игнорируем
        logger.warning(f"⚠️ Dice message_id {message.message_id} не найден в DICE_MESSAGE_STATES. Это не dice от бота, игнорируем.")
        return
    
    state = GAME_STATES[user_id]
    
    # Проверяем соответствие эмодзи
    dice_emoji = message.dice.emoji
    expected_emoji = state.get("emoticon")
    if dice_emoji != expected_emoji:
        logger.warning(f"⚠️ Несоответствие эмодзи: получено '{dice_emoji}', ожидалось '{expected_emoji}'")
        # Не прерываем выполнение, но логируем
    
    # Добавляем результат в историю
    result = message.dice.value
    state["throws"].append(result)
    state["current_throw"] += 1
    
    logger.info(f"🎮 Бросок {state['current_throw']}/{state['required_throws']}: результат={result}, история={state['throws']}, bet_type={state.get('bet_type', 'unknown')}")
    
    game_type = state["game_type"]
    bet_type = state["bet_type"]
    bet = state["bet"]
    throws = state["throws"]
    current_throw = state["current_throw"]
    required_throws = state["required_throws"]
    
    # Если нужно еще бросков - отправляем следующий dice
    if current_throw < required_throws:
        remaining = required_throws - current_throw
        logger.info(f"🔄 Нужно еще {remaining} бросков (текущий: {current_throw}, требуется: {required_throws}), отправляем следующий dice...")
        # Пауза между бросками для нескольких эмодзи ~ максимально быстрая (0.05 секунды)
        await asyncio.sleep(0.05)
        
        # Отправляем следующий dice в тот же чат
        # В групповых чатах отвечаем на исходное сообщение пользователя
        original_message_id = state.get("original_message_id")
        if message.chat.type in ['group', 'supergroup'] and original_message_id:
            # В группах отвечаем на сообщение пользователя
            next_dice = await message.bot.send_dice(
                chat_id=message.chat.id,
                emoji=state["emoticon"],
                reply_to_message_id=original_message_id
            )
        else:
            # В личных чатах отправляем без reply
            next_dice = await message.bot.send_dice(
                chat_id=message.chat.id,
                emoji=state["emoticon"]
            )
        
        # Обновляем состояние
        state["dice_message_id"] = next_dice.message_id
        DICE_MESSAGE_STATES[next_dice.message_id] = user_id
        
        # Удаляем старый message_id из словаря
        if message.message_id in DICE_MESSAGE_STATES:
            del DICE_MESSAGE_STATES[message.message_id]
        
        logger.info(f"✅ Отправлен следующий dice (бросок {current_throw + 1}/{required_throws}), message_id={next_dice.message_id}, bet_type={bet_type}")
        return
    else:
        logger.info(f"✅ Все броски завершены: {current_throw}/{required_throws}, bet_type={bet_type}")
    
    # Все броски сделаны - вызываем process_game_result для обработки результата
    # ВАЖНО: Используем единую функцию process_game_result, чтобы избежать двойной обработки
    logger.info(f"🎮 Все броски завершены! Вызываем process_game_result: тип={game_type}, ставка={bet}, тип_ставки={bet_type}, пользователь={user_id}, история={throws}")
    
    # Проверяем, не обработана ли игра уже (защита от двойной обработки)
    if state.get("result_processed", False):
        logger.warning(f"⚠️ Игра для пользователя {user_id} уже обработана в handle_dice_result, пропускаем")
        return
    
        # Вызываем единую функцию обработки результата
    currency = state.get("currency", "dollar")
    await process_game_result(message.bot, user_id, message.chat.id, game_type, bet_type, bet, required_throws, state.get("emoticon", "🎲"), currency)
    return


@router.callback_query(F.data.startswith("rules_"))
async def handle_rules(callback: CallbackQuery):
    """Показать правила игры"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    game_type = callback.data.split("_")[1]
    rules_text = get_rules_text(game_type)
    
    # Создаем клавиатуру с кнопкой "Назад" к игре
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"game_{game_type}"),
        ]
    ])
    
    # Проверяем тип сообщения перед редактированием
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=rules_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(rules_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
        await callback.message.answer(rules_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("rules_"))
async def handle_rules(callback: CallbackQuery):
    """Показать правила игры"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    game_type = callback.data.split("_")[1]
    rules_text = get_rules_text(game_type)
    
    # Создаем клавиатуру с кнопкой "Назад" к игре
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"game_{game_type}"),
        ]
    ])
    
    # Проверяем тип сообщения перед редактированием
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=rules_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await callback.message.edit_text(rules_text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка при редактировании сообщения правил: {e}", exc_info=True)
        await callback.message.answer(rules_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("slots_"))
async def handle_slots(callback: CallbackQuery):
    """Обработка слотов"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    if callback.data == "slots_multipliers":
        text = """🗓️ <b>Slots Множители</b>

777 - 20x
🍇🍇🍇 - 10x
🍋🍋🍋 - 7x
BAR BAR BAR - 5x

<i>Все анимации случайны и генерируются с помощью Telegram API</i>"""
        
        # Создаем клавиатуру с кнопкой "Назад" к слотам
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="game_slots"),
            ]
        ])

        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка при показе множителей слотов: {e}", exc_info=True)
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    if callback.data.startswith("slots_spin") or callback.data.startswith("slots_spins"):
        # Логика игры в слоты
        parts = callback.data.split("_")
        num_spins = int(parts[-1]) if len(parts) > 0 and parts[-1].isdigit() else 1
        user_id = callback.from_user.id
        
        # Проверяем, есть ли активная игра
        if is_user_busy(user_id):
            await callback.answer("⏳ Игра уже идет, подождите завершения...", show_alert=True)
            return
        
        user = await db.get_user(user_id)
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
            return
        
        balance = user["balance"]
        base_bet = user["base_bet"]
        total_bet = base_bet * num_spins
        
        logger.info(f"💰 Проверка баланса (слоты): баланс=${balance:.2f}, ставка=${total_bet:.2f} ({num_spins} спинов), достаточно={balance >= total_bet}")
        if balance < total_bet:
            logger.warning(f"❌ Недостаточно средств! Баланс=${balance:.2f}, нужно=${total_bet:.2f}")
            await callback.answer(f"❌ Недостаточно средств! Нужно ${total_bet:.2f}, у вас ${balance:.2f}", show_alert=True)
            return
        
        # Если несколько спинов, блокируем кнопки
        if num_spins > 1:
            ACTIVE_GAMES[user_id] = time.time()
            # Отредактируем сообщение, показав что игра идет
            try:
                text = f"""🎰 <b>Слоты</b>

💰 <b>Баланс:</b> ${balance:.2f}

⏳ <b>Игра идет ({num_spins} спинов), ожидайте результат...</b>"""
                from aiogram.types import InlineKeyboardMarkup
                await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[]), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения слотов: {e}")
        
        # Уменьшаем отыгрыш при ставке
        await db.decrease_rollover(user_id, total_bet)
        
        # Списываем баланс
        await db.update_balance(user_id, -total_bet)
        logger.info(f"💰 Списан баланс для слотов: ${total_bet:.2f} ({num_spins} спинов по ${base_bet:.2f})")
        
        # Отправляем слоты быстро подряд
        total_win = 0
        results = []
        slot_messages = []
        
        # Отправляем все слоты быстро подряд
        for spin in range(num_spins):
            slot_message = await callback.message.answer_dice(emoji="🎰")
            slot_messages.append(slot_message)
            # Минимальная задержка между отправкой слотов (0.05 секунды)
            if spin < num_spins - 1:
                await asyncio.sleep(0.05)
        
        # Ждем завершения анимации последнего слота (Telegram dice анимация длится ~2-3 секунды)
        await asyncio.sleep(3)
        
        # Теперь обрабатываем результаты всех слотов
        for spin, slot_message in enumerate(slot_messages):
            # Получаем результат слота (значение dice для слотов: 1-64)
            # Telegram slots dice: значение от 1 до 64, где каждая комбинация кодируется 3 двухбитными значениями
            slot_value = slot_message.dice.value
            
            # Определяем символы на основе официальной логики Telegram:
            # value состоит из трёх 2-битных значений (по одному на каждый барабан), инкрементированных на 1.
            # map := [1,2,3,0]
            # Если value == 64 — это выигрыш 7 7 7.
            symbols = []
            if slot_value == 64:
                # Выигрышная комбинация: 7 7 7
                symbols = ["7️⃣", "7️⃣", "7️⃣"]
            else:
                mapping = [1, 2, 3, 0]
                v = slot_value - 1
                left_idx = mapping[v & 3]
                center_idx = mapping[(v >> 2) & 3]
                right_idx = mapping[(v >> 4) & 3]
                
                # Порядок эмодзи подогнан под реальную анимацию Telegram:
                # index 1 -> BAR, 2 -> виноград, 3 -> лимон
                base_symbols = ["7️⃣", "BAR", "🍇", "🍋"]
                symbols = [
                    base_symbols[left_idx],
                    base_symbols[center_idx],
                    base_symbols[right_idx],
                ]
            
            # Проверяем выигрыш
            multiplier = 0
            if symbols[0] == symbols[1] == symbols[2]:
                # 3 одинаковых
                if symbols[0] == "7️⃣":
                    multiplier = 20
                elif symbols[0] == "🍇":
                    multiplier = 10
                elif symbols[0] == "🍋":
                    multiplier = 7
                elif symbols[0] == "BAR":
                    multiplier = 5
            
            win = base_bet * multiplier
            total_win += win
            results.append({
                "symbols": symbols,
                "win": win,
                "multiplier": multiplier
            })
        
        # Зачисляем выигрыш
        if total_win > 0:
            await db.update_balance(user_id, total_win)
        
        # Сохраняем результаты
        for result in results:
            await db.add_game(user_id, "slots", base_bet, 0, result["win"], None, currency="dollar")
        
        # Разблокируем кнопки для нескольких спинов
        if user_id in ACTIVE_GAMES:
            del ACTIVE_GAMES[user_id]
        
        # Получаем обновленный баланс
        user = await db.get_user(user_id)
        balance = user["balance"]
        
        # Формируем сообщение с результатами
        result_text = f"""🎰 <b>Результаты слотов</b>

💰 Ставка: ${total_bet:.2f} ({num_spins} спинов по ${base_bet:.2f})
💰 Выигрыш: ${total_win:.2f}
💰 Новый баланс: ${balance:.2f}

<b>Детали:</b>"""
        
        for i, result in enumerate(results, 1):
            symbols_str = " ".join(result["symbols"])
            if result["multiplier"] > 0:
                result_text += f"\n{i}. {symbols_str} - x{result['multiplier']:.2f} = ${result['win']:.2f}"
            else:
                result_text += f"\n{i}. {symbols_str} - проигрыш"
        
        # Клавиатура
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        result_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Еще раз", callback_data="game_slots"),
            ],
            [
                InlineKeyboardButton(text="🎮 Другие игры", callback_data="games_menu"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Главное меню", callback_data="back_main"),
            ]
        ])
        
        await callback.message.answer(result_text, reply_markup=result_keyboard, parse_mode="HTML")
        return
    
    await callback.answer()


@router.callback_query(F.data == "games_menu")
async def show_games_menu(callback: CallbackQuery):
    """Показать меню игр"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        return
    
    balance = user["balance"]
    
    text = f"""🎮 <b>Игры</b>

🙌 <b>Твой шанс выиграть до х1000</b>

ℹ️ <i>Все исходы определяются через Telegram</i>

💰 <b>Баланс:</b> ${balance:.2f}"""
    
    await send_game_photo(callback, "игры.jpg", text, get_games_menu_keyboard())


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    """Вернуться в главное меню - показывает то же самое, что и /start"""
    await callback.answer()  # Моментальный ответ на нажатие кнопки
    from keyboards import get_main_menu_keyboard
    from database import Database
    
    db = Database()
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
    await callback.answer()

