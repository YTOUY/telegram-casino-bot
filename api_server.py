"""
API сервер для мини-приложения Telegram
Обрабатывает запросы от мини-аппа
"""
import asyncio
import logging
import json
import hmac
import hashlib
from urllib.parse import parse_qs, unquote
from aiohttp import web
from aiohttp.web import Request, Response
from typing import Optional, Dict
import os

from database import Database
from config import BOT_TOKEN, TON_ADDRESS, MAX_DEPOSIT
from handlers.mini_app import get_sticker_file_url
from handlers.games import process_game_result, GAME_STATES, ACTIVE_GAMES
from aiogram import Bot
from ton_price import get_ton_to_usd_rate, ton_to_usd, usd_to_ton
import secrets
import aiosqlite

logger = logging.getLogger(__name__)

db = Database()
bot = Bot(token=BOT_TOKEN)

# Активные игры для мини-аппа
MINI_APP_GAMES = {}  # {game_id: {"user_id": int, "game_type": str, "bet": float, "status": str}}


def verify_telegram_init_data(init_data: str) -> Optional[Dict]:
    """Проверка подписи initData от Telegram"""
    try:
        # Парсим initData
        data_dict = {}
        for pair in init_data.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                data_dict[key] = unquote(value)
        
        # Проверяем подпись
        if 'hash' not in data_dict:
            return None
        
        hash_value = data_dict.pop('hash')
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        
        # Создаем секретный ключ
        secret_key = hmac.new(
            "WebAppData".encode(),
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Вычисляем хеш
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if calculated_hash != hash_value:
            logger.warning("Неверная подпись initData")
            return None
        
        # Парсим user данные
        if 'user' in data_dict:
            user_data = json.loads(data_dict['user'])
            return user_data
        
        return None
    except Exception as e:
        logger.error(f"Ошибка проверки initData: {e}")
        return None


async def get_user_from_request(request: Request) -> Optional[Dict]:
    """Получить данные пользователя из запроса"""
    init_data = request.headers.get('X-Telegram-Init-Data', '')
    if not init_data:
        return None
    
    return verify_telegram_init_data(init_data)


async def handle_user(request: Request) -> Response:
    """GET /api/user - Получить данные пользователя"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        user = await db.get_user(user_id)
        if not user:
            # Создаем пользователя если его нет
            await db.create_user(user_id, user_data.get('username'))
            user = await db.get_user(user_id)
        
        # Получаем реферальную статистику
        referral_count = await db.get_referral_count(user_id)
        referral_balance = user.get('referral_balance', 0.0)
        balance = user.get('balance', 0.0)
        base_bet = user.get('base_bet', 1.0)
        
        logger.info(f"Пользователь {user_id}: баланс = {balance}, базовая ставка = {base_bet}, реферальный баланс = {referral_balance}")
        
        return web.json_response({
            "balance": balance,
            "base_bet": base_bet,
            "referral_count": referral_count,
            "referral_balance": referral_balance,
            "username": user.get('username'),
            "first_name": user_data.get('first_name'),
            "last_name": user_data.get('last_name'),
            "photo_url": user_data.get('photo_url')
        })
    except Exception as e:
        logger.error(f"Ошибка получения данных пользователя: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_sticker_welcome(request: Request) -> Response:
    """GET /api/sticker/welcome - Получить приветственный стикер"""
    try:
        sticker = await db.get_sticker("welcome")
        if not sticker:
            logger.warning("⚠️ Приветственный стикер 'welcome' не найден в базе данных")
            return web.json_response({"error": "Sticker not found. Use /sticker command to add a sticker named 'welcome'"}, status=404)
        
        # Получаем URL файла стикера
        try:
            file_url = await get_sticker_file_url(bot, sticker['file_id'])
            
            if not file_url:
                logger.error(f"❌ Не удалось получить URL для стикера {sticker['file_id']}")
                # Пробуем создать URL напрямую через file_id
                # Но сначала нужно получить file_path через get_file
                try:
                    file_info = await bot.get_file(sticker['file_id'])
                    if file_info and file_info.file_path:
                        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
                        logger.info(f"✅ URL получен через get_file: {file_url}")
                    else:
                        logger.error(f"❌ file_path не найден для стикера {sticker['file_id']}")
                        return web.json_response({"error": "Failed to get sticker file path"}, status=500)
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении file_path: {e}")
                    return web.json_response({"error": "Failed to get sticker URL"}, status=500)
            
            # Определяем, является ли это TGS файлом
            is_tgs = file_url.lower().endswith('.tgs') or '.tgs' in file_url.lower()
            
            logger.info(f"✅ Приветственный стикер загружен: {file_url} (TGS: {is_tgs})")
            return web.json_response({
                "file_id": sticker['file_id'],
                "file_unique_id": sticker.get('file_unique_id'),
                "file_url": file_url,
                "file_path": file_info.file_path if 'file_info' in locals() else None,
                "is_tgs": is_tgs,
                "name": sticker.get('name', 'welcome')
            })
        except Exception as e:
            logger.error(f"❌ Ошибка при получении URL стикера: {e}", exc_info=True)
            return web.json_response({"error": f"Failed to get sticker URL: {str(e)}"}, status=500)
    except Exception as e:
        logger.error(f"❌ Ошибка получения стикера: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_sticker(request: Request) -> Response:
    """GET /api/sticker/{name} - Получить стикер по имени"""
    sticker_name = request.match_info.get('name')
    if not sticker_name:
        return web.json_response({"error": "Sticker name required"}, status=400)
    
    try:
        sticker = await db.get_sticker(sticker_name)
        if not sticker:
            logger.warning(f"⚠️ Стикер '{sticker_name}' не найден в базе данных")
            return web.json_response({"error": "Sticker not found"}, status=404)
        
        # Получаем URL файла стикера
        file_url = await get_sticker_file_url(bot, sticker['file_id'])
        
        if not file_url:
            logger.warning(f"⚠️ Не удалось получить URL для стикера {sticker['file_id']}, пробуем через get_file")
            # Пробуем создать URL напрямую через file_id
            try:
                file_info = await bot.get_file(sticker['file_id'])
                if file_info and file_info.file_path:
                    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
                    logger.info(f"✅ URL получен через get_file: {file_url}")
                else:
                    logger.error(f"❌ file_path не найден для стикера {sticker['file_id']}")
                    return web.json_response({"error": "Failed to get sticker file path"}, status=500)
            except Exception as e:
                logger.error(f"❌ Ошибка при получении file_path: {e}")
                return web.json_response({"error": "Failed to get sticker URL"}, status=500)
        
        # Определяем, является ли это TGS файлом
        is_tgs = file_url.lower().endswith('.tgs') or '.tgs' in file_url.lower()
        
        logger.info(f"✅ Стикер '{sticker_name}' загружен: {file_url} (TGS: {is_tgs})")
        
        return web.json_response({
            "file_id": sticker['file_id'],
            "file_url": file_url,
            "is_tgs": is_tgs
        })
    except Exception as e:
        logger.error(f"❌ Ошибка получения стикера '{sticker_name}': {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_stickers(request: Request) -> Response:
    """GET /api/stickers - Получить все стикеры"""
    try:
        stickers = await db.get_all_stickers()
        return web.json_response([
            {
                "name": s['name'],
                "file_id": s['file_id'],
                "file_unique_id": s['file_unique_id']
            }
            for s in stickers
        ])
    except Exception as e:
        logger.error(f"Ошибка получения стикеров: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_game_start(request: Request) -> Response:
    """POST /api/game/start - Запустить игру"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        data = await request.json()
        game_type = data.get('game_type')
        bet = float(data.get('bet', 1.0))
        bet_type = data.get('bet_type', 'even')  # Режим игры, по умолчанию четное
        
        if not game_type:
            return web.json_response({"error": "game_type required"}, status=400)
        
        # Проверяем баланс
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        balance = user.get('balance', 0.0)
        if balance < bet:
            return web.json_response({"error": "Insufficient balance"}, status=400)
        
        # Создаем игру (ставка будет списана в start_game_with_params)
        import time
        game_id = int(time.time() * 1000)  # Простой ID на основе времени
        
        MINI_APP_GAMES[game_id] = {
            "user_id": user_id,
            "game_type": game_type,
            "bet": bet,
            "bet_type": bet_type,
            "status": "started",
            "created_at": time.time()
        }
        
        # Запускаем игру через бота (отправляем dice в чат)
        try:
            # Для игр кроме слотов отправляем dice в чат с ботом
            if game_type != 'slots':
                # Импортируем функции из handlers/games.py
                from handlers.games import GAME_STATES, DICE_MESSAGE_STATES, start_game_with_params
                
                # Используем существующую функцию start_game_with_params для запуска игры
                # Это обеспечит правильную интеграцию с системой обработки результатов
                success = await start_game_with_params(
                    bot=bot,
                    user_id=user_id,
                    chat_id=user_id,  # В личном чате chat_id = user_id
                    game_type=game_type,
                    bet_type=bet_type,  # Используем переданный режим игры
                    bet=bet,
                    message_for_answer=None,  # Нет исходного сообщения
                    callback_for_answer=None,
                    currency="dollar"
                )
                
                if success:
                    # Сохраняем game_id в состояние игры для связи с мини-аппом
                    if user_id in GAME_STATES:
                        GAME_STATES[user_id]["game_id"] = game_id
                        GAME_STATES[user_id]["mini_app"] = True
                    
                    logger.info(f"🎮 Игра запущена из мини-аппа: game_id={game_id}, user_id={user_id}, game_type={game_type}")
                    
                    # Запускаем задачу для проверки результата
                    asyncio.create_task(check_mini_app_game_result(game_id, user_id))
                else:
                    logger.error(f"Не удалось запустить игру для пользователя {user_id}")
                    return web.json_response({"error": "Failed to start game"}, status=500)
            else:
                # Для слотов обрабатываем отдельно
                # Списываем баланс
                await db.decrease_rollover(user_id, bet)
                await db.update_balance(user_id, -bet)
                logger.info(f"💰 Списан баланс для слотов из мини-аппа: ${bet:.2f}, user_id={user_id}")
                
                # Отправляем слот в личный чат пользователя
                slot_message = await bot.send_dice(chat_id=user_id, emoji="🎰")
                
                # Сохраняем информацию о слот-сообщении
                MINI_APP_GAMES[game_id]['slot_message_id'] = slot_message.message_id
                MINI_APP_GAMES[game_id]['slot_chat_id'] = slot_message.chat.id
                
                logger.info(f"🎰 Слот отправлен для мини-аппа: game_id={game_id}, user_id={user_id}, message_id={slot_message.message_id}")
                
                # Запускаем задачу для обработки результата слота
                asyncio.create_task(process_mini_app_slots_result(game_id, user_id, bet, slot_message))
        except Exception as e:
            logger.error(f"Ошибка запуска игры: {e}", exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)
        
        return web.json_response({
            "game_id": game_id,
            "status": "started"
        })
    except Exception as e:
        logger.error(f"Ошибка запуска игры: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def process_mini_app_slots_result(game_id: int, user_id: int, bet: float, slot_message):
    """Обработать результат слота из мини-аппа"""
    try:
        # Ждем завершения анимации слота (Telegram dice анимация длится ~2-3 секунды)
        await asyncio.sleep(3)
        
        # Получаем значение слота из сообщения
        # После завершения анимации (3 секунды) dice.value будет содержать финальное значение
        slot_value = None
        if hasattr(slot_message, 'dice') and slot_message.dice:
            slot_value = slot_message.dice.value
        
        # Если значение еще не готово (анимация не завершена), получаем обновленное сообщение
        if slot_value is None or slot_value == 0:
            try:
                # Получаем обновленное сообщение через get_chat_member и затем через get_updates
                # Или просто ждем еще немного - после 3 секунд значение должно быть готово
                await asyncio.sleep(0.5)
                # Пробуем получить сообщение заново через bot.get_chat
                # Но проще всего - использовать значение из исходного сообщения после ожидания
                # В aiogram dice.value обновляется автоматически в объекте сообщения
                if hasattr(slot_message, 'dice') and slot_message.dice:
                    slot_value = slot_message.dice.value
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить значение слота: {e}")
        
        # Если все еще нет значения, используем случайное (для тестирования)
        # В продакшене это не должно происходить, так как анимация завершится за 3 секунды
        if slot_value is None or slot_value == 0:
            import random
            slot_value = random.randint(1, 64)
            logger.warning(f"⚠️ Не удалось получить значение слота, используем случайное: {slot_value}")
        
        # Декодируем символы
        from utils.checks import decode_slot_symbols
        symbols = decode_slot_symbols(slot_value)
        
        # Проверяем выигрыш (используя множители из config.py)
        multiplier = 0
        if symbols[0] == symbols[1] == symbols[2]:
            # 3 одинаковых символа
            if symbols[0] == "7":
                multiplier = 20  # 777 - 20x
            elif symbols[0] == "🍇":
                multiplier = 10  # 🍇🍇🍇 - 10x
            elif symbols[0] == "🍋":
                multiplier = 7   # 🍋🍋🍋 - 7x
            elif symbols[0] == "Bar":
                multiplier = 5   # BAR BAR BAR - 5x
        
        win = bet * multiplier
        
        # Зачисляем выигрыш
        if win > 0:
            await db.update_balance(user_id, win)
            logger.info(f"💰 Зачислен выигрыш для слотов из мини-аппа: ${win:.2f}, user_id={user_id}")
        
        # Сохраняем игру в БД
        await db.add_game(user_id, "slots", bet, 0, win, None, currency="dollar")
        
        # Получаем новый баланс
        user = await db.get_user(user_id)
        new_balance = user.get('balance', 0.0) if user else 0.0
        
        # Обновляем статус игры в MINI_APP_GAMES
        if game_id in MINI_APP_GAMES:
            MINI_APP_GAMES[game_id]['status'] = 'completed'
            MINI_APP_GAMES[game_id]['result'] = slot_value  # Значение слота (1-64)
            MINI_APP_GAMES[game_id]['symbols'] = symbols  # Массив символов ["7", "Bar", "🍇"]
            MINI_APP_GAMES[game_id]['win'] = win
            MINI_APP_GAMES[game_id]['new_balance'] = new_balance
            MINI_APP_GAMES[game_id]['game_type'] = 'slots'
            MINI_APP_GAMES[game_id]['throws'] = symbols  # Для совместимости с другими играми
            logger.info(f"✅ Слот из мини-аппа обработан: game_id={game_id}, symbols={symbols}, win={win}")
        else:
            logger.error(f"❌ game_id {game_id} не найден в MINI_APP_GAMES!")
            
    except Exception as e:
        logger.error(f"Ошибка обработки слота из мини-аппа: {e}", exc_info=True)
        if game_id in MINI_APP_GAMES:
            MINI_APP_GAMES[game_id]['status'] = 'error'


async def check_mini_app_game_result(game_id: int, user_id: int):
    """Проверить результат игры из мини-аппа"""
    max_attempts = 20  # Увеличиваем для слотов (нужно больше времени)
    attempts = 0
    
    try:
        from handlers.games import GAME_STATES
        
        # Проверяем тип игры
        game_info = MINI_APP_GAMES.get(game_id, {})
        game_type = game_info.get('game_type', 'unknown')
        
        # Для слотов проверяем MINI_APP_GAMES напрямую
        if game_type == 'slots':
            while attempts < max_attempts:
                await asyncio.sleep(0.5)
                attempts += 1
                
                if game_id in MINI_APP_GAMES and MINI_APP_GAMES[game_id].get('status') == 'completed':
                    logger.info(f"✅ Слот завершен: game_id={game_id}")
                    break
                elif game_id in MINI_APP_GAMES and MINI_APP_GAMES[game_id].get('status') in ['error', 'timeout']:
                    logger.warning(f"⚠️ Слот завершен с ошибкой: game_id={game_id}, status={MINI_APP_GAMES[game_id].get('status')}")
                    break
            
            return  # Для слотов не используем GAME_STATES
        
        # Для остальных игр используем стандартную логику
        while attempts < max_attempts:
            await asyncio.sleep(0.5)  # Проверяем каждые 0.5 секунды для быстрого отклика
            attempts += 1
            
            # Проверяем состояние игры
            state = GAME_STATES.get(user_id)
            if not state:
                # Если состояние удалено, возможно игра завершена
                # Проверяем MINI_APP_GAMES напрямую
                if game_id in MINI_APP_GAMES and MINI_APP_GAMES[game_id].get('status') == 'completed':
                    break
                # Если прошло больше 2 секунд, проверяем еще раз
                if attempts >= 4:
                    # Возможно игра уже обработана, но состояние удалено
                    # Проверяем MINI_APP_GAMES еще раз
                    if game_id in MINI_APP_GAMES and MINI_APP_GAMES[game_id].get('status') == 'completed':
                        break
                continue
            
            # Проверяем, обработан ли результат
            if state.get("result_processed", False) and state.get("game_id") == game_id:
                # Игра обработана, получаем результат
                throws = state.get("throws", [])
                logger.info(f"🔍 check_mini_app_game_result: throws из состояния={throws}, тип={type(throws)}, is_list={isinstance(throws, list)}")
                
                if throws:
                    # ВАЖНО: result - это сумма для отображения, но throws - это массив каждого броска
                    result = throws[0] if len(throws) == 1 else sum(throws)
                    game_type = state.get("game_type", "dice")
                    
                    # Получаем информацию о выигрыше из состояния игры
                    # (process_game_result уже обработал результат и сохранил в БД)
                    win = state.get("win", 0.0)
                    
                    # Получаем новый баланс
                    user = await db.get_user(user_id)
                    new_balance = user.get('balance', 0.0) if user else 0.0
                    
                    # Обновляем статус игры в MINI_APP_GAMES
                    # ВАЖНО: Сохраняем throws как список, даже если он уже был сохранен в process_game_result
                    if game_id in MINI_APP_GAMES:
                        MINI_APP_GAMES[game_id]['status'] = 'completed'
                        MINI_APP_GAMES[game_id]['result'] = result  # Сумма для отображения
                        # ВАЖНО: Всегда сохраняем throws из состояния, так как это самый актуальный источник
                        # НИКОГДА не используем result (сумму) как fallback для throws!
                        if isinstance(throws, list) and len(throws) > 0:
                            MINI_APP_GAMES[game_id]['throws'] = throws.copy()  # ВАЖНО: Массив каждого броска для стикеров
                            logger.info(f"💾 Сохранен throws в check_mini_app_game_result: {throws} → {MINI_APP_GAMES[game_id]['throws']}")
                        elif 'throws' not in MINI_APP_GAMES[game_id] or not MINI_APP_GAMES[game_id].get('throws'):
                            # Если throws не список или пустой - это ошибка, НЕ создаем из result!
                            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: throws не является списком в check_mini_app_game_result! throws={throws}, тип: {type(throws)}")
                            # НЕ используем result, так как это сумма! Оставляем пустой список
                            MINI_APP_GAMES[game_id]['throws'] = []
                        MINI_APP_GAMES[game_id]['win'] = win
                        MINI_APP_GAMES[game_id]['new_balance'] = new_balance
                        MINI_APP_GAMES[game_id]['game_type'] = game_type
                        logger.info(f"📋 MINI_APP_GAMES после сохранения: throws={MINI_APP_GAMES[game_id].get('throws')}")
                    else:
                        logger.error(f"❌ game_id {game_id} не найден в MINI_APP_GAMES!")
                    
                    logger.info(f"✅ Игра из мини-аппа завершена: game_id={game_id}, result={result}, throws={throws}, win={win}")
                    break
                else:
                    logger.error(f"❌ throws пустой в check_mini_app_game_result! state={state}")
            
            # Дополнительная проверка: если состояние уже удалено, но игра завершена в MINI_APP_GAMES
            if game_id in MINI_APP_GAMES and MINI_APP_GAMES[game_id].get('status') == 'completed':
                # Игра уже завершена, throws должен быть сохранен в process_game_result
                if MINI_APP_GAMES[game_id].get('throws'):
                    logger.info(f"✅ Игра уже завершена в MINI_APP_GAMES: game_id={game_id}, throws={MINI_APP_GAMES[game_id].get('throws')}")
                    break
            
            # Проверяем, не истекло ли время ожидания
            if attempts >= max_attempts:
                logger.warning(f"⏱ Таймаут ожидания результата игры: game_id={game_id}")
                if game_id in MINI_APP_GAMES:
                    MINI_APP_GAMES[game_id]['status'] = 'timeout'
                break
        
    except Exception as e:
        logger.error(f"Ошибка проверки результата игры: {e}", exc_info=True)
        if game_id in MINI_APP_GAMES:
            MINI_APP_GAMES[game_id]['status'] = 'error'


async def handle_game_result(request: Request) -> Response:
    """GET /api/game/result/{game_id} - Получить результат игры"""
    game_id = int(request.match_info.get('game_id', 0))
    if not game_id:
        return web.json_response({"error": "game_id required"}, status=400)
    
    try:
        game_data = MINI_APP_GAMES.get(game_id)
        if not game_data:
            return web.json_response({"error": "Game not found"}, status=404)
        
        if game_data['status'] == 'completed':
            game_type = game_data.get('game_type', 'unknown')
            
            # Для слотов используем symbols вместо throws
            if game_type == 'slots':
                symbols = game_data.get('symbols', [])
                result = game_data.get('result')  # Значение слота (1-64)
                
                logger.info(f"📤 Отправка результата слота: game_id={game_id}, result={result}, symbols={symbols}")
                
                return web.json_response({
                    "completed": True,
                    "result": result,
                    "symbols": symbols,  # Массив символов ["7", "Bar", "🍇"]
                    "throws": symbols,  # Для совместимости с другими играми
                    "win": game_data.get('win', 0.0),
                    "new_balance": game_data.get('new_balance', 0.0),
                    "game_type": game_type
                })
            
            # Для остальных игр используем стандартную логику
            throws = game_data.get('throws')
            result = game_data.get('result')
            
            # Логируем для отладки
            logger.info(f"📤 Отправка результата игры: game_id={game_id}, result={result}, throws={throws}, throws_type={type(throws)}, is_list={isinstance(throws, list)}")
            
            # ВАЖНО: Убеждаемся, что throws это список
            # НИКОГДА не используем result (сумму) как fallback для throws!
            if not isinstance(throws, list) or len(throws) == 0:
                # Если throws не список или пустой - это КРИТИЧЕСКАЯ ОШИБКА!
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: throws отсутствует или не список для game_id={game_id}! throws={throws}, тип: {type(throws)}, result={result}")
                logger.error(f"❌ Полные данные игры: {game_data}")
                # НЕ используем result, так как это сумма! Оставляем пустой список
                # Лучше показать ошибку, чем неправильные данные
                throws = []
            
            # Дополнительная проверка: если throws это список с одним элементом, который равен result, 
            # и result > 6 (что означает сумму), то возможно это ошибка - но мы все равно отправим throws
            logger.info(f"📤 Финальный throws для отправки: {throws} (тип: {type(throws)}, длина: {len(throws) if isinstance(throws, list) else 'N/A'})")
            
            return web.json_response({
                "completed": True,
                "result": result,
                "throws": throws,  # ВАЖНО: Массив каждого броска для отображения стикеров
                "win": game_data.get('win', 0.0),
                "new_balance": game_data.get('new_balance', 0.0),
                "game_type": game_data['game_type']
            })
        else:
            return web.json_response({
                "completed": False,
                "status": game_data['status']
            })
    except Exception as e:
        logger.error(f"Ошибка получения результата игры: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_settings_base_bet(request: Request) -> Response:
    """POST /api/settings/base-bet - Сохранить базовую ставку"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        data = await request.json()
        base_bet = float(data.get('base_bet', 1.0))
        
        if base_bet < 0.1:
            return web.json_response({"error": "Base bet must be at least 0.1"}, status=400)
        
        await db.update_user_base_bet(user_id, base_bet)
        return web.json_response({"success": True, "base_bet": base_bet})
    except Exception as e:
        logger.error(f"Ошибка сохранения базовой ставки: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_check_create(request: Request) -> Response:
    """POST /api/check/create - Создать чек"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        data = await request.json()
        amount = float(data.get('amount', 0.0))
        activations = int(data.get('activations', 1))
        text = data.get('text', '')
        
        if amount < 0.1:
            return web.json_response({"error": "Amount must be at least 0.1"}, status=400)
        
        # Проверяем баланс
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        total_amount = amount * activations
        balance = user.get('balance', 0.0)
        if balance < total_amount:
            return web.json_response({"error": "Insufficient balance"}, status=400)
        
        # Создаем чек (упрощенная реализация)
        import secrets
        check_code = secrets.token_hex(8)
        
        # Сохраняем чек в базе (нужно добавить таблицу checks в database.py)
        # Пока возвращаем код чека
        
        return web.json_response({
            "success": True,
            "check_code": check_code
        })
    except Exception as e:
        logger.error(f"Ошибка создания чека: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_lotteries(request: Request) -> Response:
    """GET /api/lotteries - Получить список лотерей"""
    user_data = await get_user_from_request(request)
    user_id = user_data.get('id') if user_data else None
    
    try:
        lotteries = await db.get_active_lotteries()
        
        # Для каждой лотереи получаем количество билетов пользователя
        result = []
        for l in lotteries:
            lottery_id = l['id']
            user_tickets = 0
            
            # Получаем количество билетов пользователя в этой лотерее
            if user_id:
                try:
                    # Получаем количество билетов пользователя (правильный порядок аргументов: lottery_id, user_id)
                    user_tickets = await db.get_user_lottery_tickets_count(lottery_id, user_id)
                except Exception as e:
                    # Если метод не реализован или произошла ошибка, используем 0
                    logger.debug(f"Не удалось получить билеты пользователя для лотереи {lottery_id}: {e}")
                    user_tickets = 0
            
            result.append({
                "id": lottery_id,
                "title": l['title'],
                "description": l.get('description', ''),
                "total_tickets": l.get('total_tickets', 0),
                "user_tickets": user_tickets,  # Количество билетов пользователя
                "ticket_price": l.get('ticket_price', 0.0),
                "max_tickets_per_user": l.get('max_tickets_per_user', 999)  # Максимум билетов на пользователя
            })
        
        return web.json_response(result)
    except Exception as e:
        logger.error(f"Ошибка получения лотерей: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_lottery_participate(request: Request) -> Response:
    """POST /api/lottery/participate - Участвовать в лотерее"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        data = await request.json()
        lottery_id = int(data.get('lottery_id', 0))
        
        if not lottery_id:
            return web.json_response({"error": "lottery_id required"}, status=400)
        
        # Получаем лотерею
        lottery = await db.get_lottery(lottery_id)
        if not lottery:
            return web.json_response({"error": "Lottery not found"}, status=404)
        
        if lottery['status'] != 'active':
            return web.json_response({"error": "Lottery is not active"}, status=400)
        
        # Используем buy_lottery_ticket, который делает все проверки и добавляет билет
        ticket_number = await db.buy_lottery_ticket(lottery_id, user_id)
        
        if not ticket_number:
            # Проверяем причину ошибки
            user = await db.get_user(user_id)
            if not user:
                return web.json_response({"error": "User not found"}, status=404)
            
            balance = user.get('balance', 0.0)
            user_tickets_count = await db.get_user_lottery_tickets_count(lottery_id, user_id)
            
            if user_tickets_count >= lottery.get('max_tickets_per_user', 999):
                return web.json_response({"error": "Вы достигли лимита билетов"}, status=400)
            elif balance < lottery.get('ticket_price', 0.0):
                return web.json_response({"error": "Недостаточно средств"}, status=400)
            else:
                return web.json_response({"error": "Ошибка при покупке билета"}, status=400)
        
        return web.json_response({"success": True, "ticket_number": ticket_number})
    except Exception as e:
        logger.error(f"Ошибка участия в лотерее: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_gifts(request: Request) -> Response:
    """GET /api/gifts - Получить список подарков"""
    try:
        # Получаем конфигурацию подарков для цен
        from gifts import GIFTS_CONFIG
        
        # Возвращаем ВСЕ подарки из конфига, а не только из БД релеера
        # Это позволяет показывать все доступные подарки даже если они еще не синхронизированы
        gifts_list = []
        
        for emoji, config_info in GIFTS_CONFIG.items():
            gift_name = config_info.get('name', '')
            price_ton = config_info.get('price_ton', 0.0)
            price_ton_black = config_info.get('price_ton_black', 0.0)
            
            if gift_name:  # Пропускаем подарки без имени
                gifts_list.append({
                    "name": gift_name,
                    "price_ton": price_ton,
                    "price_ton_black": price_ton_black,
                    "image_url": ""  # Изображения загружаются локально из nft/png/
                })
        
        logger.info(f"Возвращено подарков из конфига: {len(gifts_list)}")
        return web.json_response(gifts_list)
    except Exception as e:
        logger.error(f"Ошибка получения подарков: {e}", exc_info=True)
        return web.json_response({"error": str(e)}, status=500)


async def get_user_photo_url(user_id: int) -> Optional[str]:
    """Получить URL аватара пользователя через Telegram Bot API"""
    try:
        # Пытаемся получить фото профиля пользователя
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.photos and len(photos.photos) > 0:
            # Берем самое большое фото
            photo = photos.photos[0][-1]
            file = await bot.get_file(photo.file_id)
            return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    except Exception as e:
        logger.debug(f"Не удалось получить аватар для пользователя {user_id}: {e}")
    return None


async def handle_top(request: Request) -> Response:
    """GET /api/top - Получить топ игроков/чатов"""
    category = request.query.get('category', 'players')
    period = request.query.get('period', 'day')
    
    try:
        # Получаем данные текущего пользователя
        user_data = await get_user_from_request(request)
        user_id = user_data.get('id') if user_data else None
        
        if category == 'chats':
            # Топ чатов - получаем из таблицы chats
            try:
                top_chats = await db.get_top_chats_by_turnover(period=period, limit=100)
                
                return web.json_response({
                    "top": [
                        {
                            "chat_id": c['chat_id'],
                            "title": c.get('title', f"Чат {c['chat_id']}"),
                            "username": c.get('username'),
                            "turnover": c.get('turnover', 0.0)
                        }
                        for c in top_chats
                    ],
                    "user": None  # Для чатов позиция пользователя не применима
                })
            except Exception as e:
                logger.error(f"Ошибка получения топа чатов: {e}", exc_info=True)
                # Если метод не реализован, возвращаем пустой список
                return web.json_response({
                    "top": [],
                    "user": None,
                    "message": "Топ чатов пока не реализован"
                })
        else:
            # Топ игроков
            top_players = await db.get_top_by_turnover(period=period, limit=100)
            
            # Получаем аватарки для всех пользователей в топе
            top_with_avatars = []
            for p in top_players:
                photo_url = await get_user_photo_url(p['user_id'])
                top_with_avatars.append({
                    "user_id": p['user_id'],
                    "username": p.get('username', f"ID{p['user_id']}"),
                    "turnover": p.get('turnover', 0.0),
                    "photo_url": photo_url
                })
            
            # Получаем позицию и оборот текущего пользователя
            user_position = None
            user_turnover = None
            if user_id:
                try:
                    user_position = await db.get_user_turnover_position(user_id, period)
                    user_turnover = await db.get_user_turnover(user_id, period)
                except Exception as e:
                    logger.warning(f"Ошибка получения данных пользователя для топа: {e}")
            
            return web.json_response({
                "top": top_with_avatars,
                "user": {
                    "position": user_position,
                    "turnover": user_turnover
                } if user_id else None
            })
    except Exception as e:
        logger.error(f"Ошибка получения топа: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_profile(request: Request) -> Response:
    """GET /api/profile - Получить данные профиля"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        user = await db.get_user(user_id)
        if not user:
            return web.json_response({"error": "User not found"}, status=404)
        
        referral_count = await db.get_referral_count(user_id)
        referral_code = user.get('referral_code', '')
        
        # Формируем реферальную ссылку
        if referral_code:
            referral_link = f"https://t.me/arbuzcas_bot?start={referral_code}"
        else:
            referral_link = ""
            logger.warning(f"У пользователя {user_id} отсутствует referral_code")
        
        logger.info(f"Профиль пользователя {user_id}: referral_code={referral_code}, referral_link={referral_link}")
        
        return web.json_response({
            "referral_count": referral_count,
            "referral_balance": user.get('referral_balance', 0.0),
            "referral_link": referral_link
        })
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_wallet_deposit_methods(request: Request) -> Response:
    """GET /api/wallet/deposit-methods - Получить список методов пополнения"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    try:
        # Список методов пополнения (соответствует keyboards.py get_deposit_keyboard)
        methods = [
            {
                "id": "ton",
                "name": "TON",
                "icon": "💎",
                "description": "Пополнение через TON кошелек"
            },
            {
                "id": "cryptobot",
                "name": "CryptoBot",
                "icon": "🏝️",
                "description": "Пополнение через CryptoBot"
            },
            {
                "id": "xrocket",
                "name": "xRocket",
                "icon": "🚀",
                "description": "Пополнение через xRocket"
            },
            {
                "id": "gifts",
                "name": "Подарки",
                "icon": "🎁",
                "description": "Пополнение через подарки"
            }
        ]
        
        return web.json_response({"methods": methods})
    except Exception as e:
        logger.error(f"Ошибка получения методов пополнения: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_wallet_deposit_address(request: Request) -> Response:
    """POST /api/wallet/deposit-address - Получить адрес для пополнения через TON"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        data = await request.json()
        amount_ton = float(data.get('amount', 0.0))
        currency = data.get('currency', 'TON')
        
        if amount_ton < 0.01:
            return web.json_response({"error": "Минимальная сумма пополнения: 0.01 TON"}, status=400)
        
        # Получаем курс TON
        ton_rate = await get_ton_to_usd_rate()
        amount_usd = ton_to_usd(amount_ton, ton_rate)
        
        # Проверяем максимальную сумму
        if amount_usd > MAX_DEPOSIT:
            return web.json_response({
                "error": f"Максимальная сумма пополнения: ${MAX_DEPOSIT:.2f} ({usd_to_ton(MAX_DEPOSIT, ton_rate):.4f} TON)"
            }, status=400)
        
        # Создаем запись о депозите со статусом pending
        deposit_id = await db.add_deposit_with_status(user_id, amount_usd, "ton_connect", "pending")
        
        logger.info(f"Создан депозит для пользователя {user_id}: {amount_ton:.4f} TON (${amount_usd:.2f}), deposit_id={deposit_id}")
        
        return web.json_response({
            "address": TON_ADDRESS,
            "deposit_address": TON_ADDRESS,
            "deposit_id": deposit_id,
            "amount_ton": amount_ton,
            "amount_usd": amount_usd,
            "memo": str(user_id),  # user_id в качестве memo для автоматического начисления
            "currency": currency
        })
    except Exception as e:
        logger.error(f"Ошибка создания депозита: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


async def handle_wallet_deposit_status(request: Request) -> Response:
    """GET /api/wallet/deposit-status/{deposit_id} - Проверить статус депозита"""
    user_data = await get_user_from_request(request)
    if not user_data:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_data.get('id')
    if not user_id:
        return web.json_response({"error": "Invalid user data"}, status=400)
    
    try:
        deposit_id = int(request.match_info.get('deposit_id', 0))
        if not deposit_id:
            return web.json_response({"error": "deposit_id required"}, status=400)
        
        # Получаем депозит
        deposit = await db.get_deposit_by_id(deposit_id)
        if not deposit:
            return web.json_response({"error": "Deposit not found"}, status=404)
        
        # Проверяем, что депозит принадлежит пользователю
        if deposit.get('user_id') != user_id:
            return web.json_response({"error": "Unauthorized"}, status=403)
        
        status = deposit.get('status', 'pending')
        
        # Если статус pending, проверяем транзакции в блокчейне
        if status == 'pending':
            # Проверяем, была ли транзакция с memo = user_id и нужной суммой
            from ton_chain import find_incoming_tx_by_comment
            from ton_price import get_ton_to_usd_rate
            
            amount_usd = deposit.get('amount', 0.0)
            ton_rate = await get_ton_to_usd_rate()
            amount_ton = usd_to_ton(amount_usd, ton_rate)
            min_amount_nano = int(amount_ton * 0.98 * 1e9)  # Допускаем 2% расхождение
            
            tx_result = await find_incoming_tx_by_comment(
                TON_ADDRESS,
                str(user_id),
                min_amount_nano
            )
            
            if tx_result:
                tx_hash, amount_nano = tx_result
                # Проверяем, что транзакция еще не обработана
                if await db.is_chain_payment_new(tx_hash):
                    # Начисляем баланс
                    await db.update_balance(user_id, amount_usd)
                    await db.save_chain_payment(tx_hash, user_id, amount_usd)
                    
                    # Обновляем статус депозита
                    async with aiosqlite.connect(db.db_path) as conn:
                        await conn.execute(
                            "UPDATE deposits SET status = 'completed' WHERE id = ?",
                            (deposit_id,)
                        )
                        await conn.commit()
                    
                    status = 'completed'
                    logger.info(f"Депозит {deposit_id} подтвержден автоматически: tx_hash={tx_hash}")
        
        return web.json_response({
            "deposit_id": deposit_id,
            "status": status,
            "amount": deposit.get('amount', 0.0),
            "created_at": deposit.get('created_at')
        })
    except Exception as e:
        logger.error(f"Ошибка проверки статуса депозита: {e}", exc_info=True)
        return web.json_response({"error": "Internal server error"}, status=500)


def create_app() -> web.Application:
    """Создать приложение aiohttp"""
    app = web.Application()
    
    # CORS middleware
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == 'OPTIONS':
                return web.Response(
                    headers={
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type, X-Telegram-Init-Data'
                    }
                )
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Telegram-Init-Data'
            return response
        return middleware_handler
    
    app.middlewares.append(cors_middleware)
    
    # Routes
    app.router.add_get('/api/user', handle_user)
    app.router.add_get('/api/sticker/welcome', handle_sticker_welcome)
    app.router.add_get('/api/sticker/{name}', handle_sticker)
    app.router.add_get('/api/stickers', handle_stickers)
    app.router.add_post('/api/game/start', handle_game_start)
    app.router.add_get('/api/game/result/{game_id}', handle_game_result)
    app.router.add_post('/api/settings/base-bet', handle_settings_base_bet)
    app.router.add_post('/api/check/create', handle_check_create)
    app.router.add_get('/api/lotteries', handle_lotteries)
    app.router.add_post('/api/lottery/participate', handle_lottery_participate)
    app.router.add_get('/api/gifts', handle_gifts)
    app.router.add_get('/api/top', handle_top)
    app.router.add_get('/api/profile', handle_profile)
    app.router.add_get('/api/wallet/deposit-methods', handle_wallet_deposit_methods)
    app.router.add_post('/api/wallet/deposit-address', handle_wallet_deposit_address)
    app.router.add_get('/api/wallet/deposit-status/{deposit_id}', handle_wallet_deposit_status)
    
    return app


async def start_api_server(port: int = 8080):
    """Запустить API сервер"""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 API сервер запущен на порту {port}")
    return runner

