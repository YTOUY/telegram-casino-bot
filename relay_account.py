import asyncio
import logging
from typing import List, Optional, Dict
from telethon import TelegramClient, errors, functions, types, events
from telethon.errors.rpcbaseerrors import BadRequestError
from telethon.tl.types import InputPeerChannel

from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, ADMIN_IDS

logger = logging.getLogger(__name__)

# Глобальный клиент релеера
_relay_client: Optional[TelegramClient] = None
_relay_phone: str = "+17622913437"  # Номер телефона релеера


def get_relay_client() -> Optional[TelegramClient]:
    """Получить клиент релеера"""
    return _relay_client


async def init_relay_client() -> bool:
    """Инициализировать клиент релеера"""
    global _relay_client
    
    try:
        _relay_client = TelegramClient("relay_session", api_id=TELEGRAM_API_ID, api_hash=TELEGRAM_API_HASH)
        await _relay_client.start(phone=_relay_phone)
        logger.info("✅ Клиент релеера успешно инициализирован")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации клиента релеера: {e}", exc_info=True)
        return False


async def close_relay_client():
    """Закрыть клиент релеера"""
    global _relay_client
    if _relay_client:
        await _relay_client.disconnect()
        _relay_client = None
        logger.info("✅ Клиент релеера закрыт")


def key_of(gift: types.TypeStarGift) -> str:
    """Получение ссылки на подарок"""
    return f'https://t.me/nft/{gift.slug}' if getattr(gift, 'slug', None) else f'id:{gift.id}'


async def get_self_gifts(client: TelegramClient) -> List[types.StarGiftUnique]:
    """Получение подарков с профиля аккаунта"""
    try:
        saved: types.payments.SavedStarGifts = await client(
            functions.payments.GetSavedStarGiftsRequest(
                peer=types.InputPeerSelf(),
                offset='', 
                limit=1000
            )
        )
        gifts = [g for g in saved.gifts
                 if isinstance(g.gift, types.StarGiftUnique)]
        
        return gifts
    except Exception as e:
        logger.error(f"Ошибка при получении подарков: {e}", exc_info=True)
        return []


async def send_gift(client: TelegramClient, gift_object: types.SavedStarGift, destination_id: types.TypeInputPeer) -> str:
    """Отправка подарка"""
    k = key_of(gift_object.gift)

    invoice = None

    if gift_object.msg_id:
        invoice = types.InputInvoiceStarGiftTransfer(
            stargift=types.InputSavedStarGiftUser(msg_id=gift_object.msg_id),
            to_id=destination_id
        )
    else:
        channel = await client.get_entity(gift_object.gift.owner_id.channel_id)
        channel_peer = InputPeerChannel(channel_id=channel.id, access_hash=channel.access_hash)

        invoice = types.InputInvoiceStarGiftTransfer(
            stargift=types.InputSavedStarGiftChat(peer=channel_peer, saved_id=gift_object.saved_id),
            to_id=destination_id
        )
    
    try:
        form = await client(functions.payments.GetPaymentFormRequest(invoice=invoice))
        price = sum(p.amount for p in form.invoice.prices)   # Stars
        if price == 0:
            # иногда Telegram всё-таки шлёт 0 → безопаснее прямой трансфер
            raise BadRequestError(400, 'NO_PAYMENT_NEEDED', None)
        await client(functions.payments.SendStarsFormRequest(
            form_id=form.form_id, invoice=invoice))
        return "SUCCESS"

    except BadRequestError as e:
        logger.error(f"Ошибка при отправке подарка {k}: {e.message}")

        if "BALANCE_TOO_LOW" in e.message:
            return "BALANCE_TOO_LOW"
        elif e.message == 'NO_PAYMENT_NEEDED':
            # бесплатный перевод
            try:
                await client(functions.payments.TransferStarGiftRequest(
                    stargift=types.InputSavedStarGiftUser(msg_id=gift_object.msg_id),
                    to_id=destination_id
                ))
                return "SUCCESS"
            except BadRequestError as e2:
                if e2.message in {'STARGIFT_NOT_UNIQUE', 'STARGIFT_USAGE_LIMITED'}:
                    logger.warning(f'⏩ Skip {k} ({e2.message})')
                    return "STARGIFT_NOT_UNIQUE"
                else:
                    logger.error(f"Ошибка при бесплатном переводе: {e2.message}")
                    return "ERROR"
        elif e.message in {'STARGIFT_NOT_UNIQUE', 'STARGIFT_USAGE_LIMITED'}:
            logger.warning(f'⏩ Skip {k} ({e.message})')
            return "STARGIFT_NOT_UNIQUE"
        else:
            logger.error(f"Неизвестная ошибка: {e.message}")
            return "ERROR"
    except Exception as e:
        logger.error(f"Критическая ошибка при отправке подарка: {e}", exc_info=True)
        return "ERROR"


async def find_gift_in_relay_profile(client: TelegramClient, emoji: str) -> Optional[types.SavedStarGift]:
    """Найти подарок в профиле релеера по эмодзи"""
    try:
        gifts = await get_self_gifts(client)
        
        # Ищем подарок по эмодзи (нужно проверить атрибуты подарка)
        for gift in gifts:
            # Проверяем атрибуты подарка для определения эмодзи
            if hasattr(gift.gift, 'attributes') and gift.gift.attributes:
                # Атрибуты могут содержать информацию об эмодзи
                # Это упрощенная проверка, может потребоваться доработка
                gift_emoji = None
                # Пытаемся найти эмодзи в атрибутах
                for attr in gift.gift.attributes:
                    if hasattr(attr, 'name') and emoji in attr.name:
                        gift_emoji = emoji
                        break
                
                if gift_emoji == emoji:
                    return gift
        
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске подарка в профиле релеера: {e}", exc_info=True)
        return None


async def transfer_gift_to_user(client: TelegramClient, gift: types.SavedStarGift, user_id: int) -> bool:
    """Передать подарок пользователю"""
    try:
        # Получаем entity пользователя по user_id
        destination = await client.get_input_entity(user_id)
        
        result = await send_gift(client, gift, destination)
        
        if result == "SUCCESS":
            logger.info(f"✅ Подарок успешно передан пользователю {user_id}")
            return True
        else:
            logger.warning(f"⚠️ Не удалось передать подарок пользователю {user_id}: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка при передаче подарка пользователю {user_id}: {e}", exc_info=True)
        return False


def get_emoji_by_gift_name(gift_name: str) -> Optional[str]:
    """Получить эмодзи подарка по его имени из конфига"""
    from gifts import GIFTS_CONFIG
    
    for emoji, info in GIFTS_CONFIG.items():
        if info["name"].lower() == gift_name.lower():
            return emoji
    return None


def get_gift_info_by_name(gift_name: str) -> Optional[Dict]:
    """Получить информацию о подарке по имени из конфига"""
    from gifts import GIFTS_CONFIG
    
    if not gift_name:
        return None
    
    gift_name_lower = gift_name.lower().strip()
    
    # Сначала точное совпадение
    for emoji, info in GIFTS_CONFIG.items():
        if info["name"].lower() == gift_name_lower:
            return {"emoji": emoji, **info}
    
    # Затем частичное совпадение (если название содержит имя подарка)
    for emoji, info in GIFTS_CONFIG.items():
        config_name_lower = info["name"].lower()
        if gift_name_lower in config_name_lower or config_name_lower in gift_name_lower:
            return {"emoji": emoji, **info}
    
    return None


def get_gift_info_from_attributes(gift: types.StarGiftUnique) -> Optional[Dict]:
    """Получить информацию о подарке из его атрибутов и title"""
    from gifts import GIFTS_CONFIG
    
    # Сначала пытаемся использовать title подарка (например, "Sakura Flower")
    if hasattr(gift, 'title') and gift.title:
        gift_info = get_gift_info_by_name(gift.title)
        if gift_info:
            logger.info(f"✅ Подарок определен по title: {gift.title}")
            return gift_info
    
    if not hasattr(gift, 'attributes') or not gift.attributes:
        return None
    
    # Логируем атрибуты для отладки
    attributes_info = []
    for attr in gift.attributes:
        if hasattr(attr, 'name'):
            attributes_info.append(attr.name)
    
    logger.info(f"  Атрибуты подарка: {attributes_info}")
    
    # Обычно первый атрибут - это модель (название подарка)
    # Пытаемся найти подарок по первому атрибуту
    if len(attributes_info) > 0:
        model_name = attributes_info[0]
        
        # Пытаемся найти подарок по названию модели
        gift_info = get_gift_info_by_name(model_name)
        if gift_info:
            return gift_info
        
        # Если не нашли по точному совпадению, пытаемся найти по частичному совпадению
        model_name_lower = model_name.lower()
        for emoji, info in GIFTS_CONFIG.items():
            gift_name_lower = info["name"].lower()
            # Проверяем, содержит ли название модели название подарка или наоборот
            if model_name_lower in gift_name_lower or gift_name_lower in model_name_lower:
                return {"emoji": emoji, **info}
    
    return None


async def sync_relay_gifts_to_db(database) -> Dict[str, int]:
    """Синхронизировать подарки релеера с базой данных"""
    """Возвращает словарь {emoji: count} с количеством подарков каждого типа"""
    if not _relay_client:
        logger.warning("⚠️ Клиент релеера не инициализирован")
        return {}
    
    try:
        gifts = await get_self_gifts(_relay_client)
        gift_counts = {}
        available_message_ids = []  # Список message_id подарков, которые есть в профиле
        
        for gift in gifts:
            # Получаем информацию о подарке
            msg_id = gift.msg_id if hasattr(gift, 'msg_id') else None
            gift_id = gift.gift.id if hasattr(gift.gift, 'id') else None
            slug = gift.gift.slug if hasattr(gift.gift, 'slug') else None
            
            # Пропускаем подарки без message_id (они не могут быть сохранены)
            if not msg_id or msg_id == 0:
                logger.warning(f"⚠️ Пропускаю подарок без message_id: slug={slug}")
                continue
            
            available_message_ids.append(msg_id)
            
            # Пытаемся определить подарок из title и атрибутов
            # Сначала используем title напрямую
            gift_name = None
            emoji = ""
            gift_info = None
            
            if hasattr(gift.gift, 'title') and gift.gift.title:
                gift_title = gift.gift.title
                logger.info(f"🔍 Пытаюсь определить подарок по title: '{gift_title}'")
                # Пытаемся найти в конфиге по title
                gift_info = get_gift_info_by_name(gift_title)
                if gift_info:
                    emoji = gift_info.get("emoji", "")
                    gift_name = gift_info.get("name")
                    logger.info(f"✅ Подарок определен по title при синхронизации: {gift_name} ({emoji})")
                else:
                    logger.warning(f"⚠️ Подарок '{gift_title}' не найден в конфиге по title")
            
            # Если не нашли по title, пытаемся по атрибутам
            if not gift_info:
                gift_info = get_gift_info_from_attributes(gift.gift)
                if gift_info:
                    emoji = gift_info.get("emoji", "")
                    gift_name = gift_info.get("name")
                    logger.info(f"✅ Подарок определен по атрибутам при синхронизации: {gift_name} ({emoji})")
            
            # Если все еще не нашли, используем title как имя подарка
            if not gift_name and hasattr(gift.gift, 'title') and gift.gift.title:
                gift_name = gift.gift.title
                logger.warning(f"⚠️ Подарок не найден в конфиге, используем title: {gift_name}, Slug: {slug}")
            
            # Добавляем в базу данных
            # Используем title как имя, если gift_name не определен
            final_gift_name = gift_name
            if not final_gift_name and hasattr(gift.gift, 'title') and gift.gift.title:
                final_gift_name = gift.gift.title
            
            await database.add_relay_gift(
                message_id=msg_id,
                emoji=emoji,
                gift_name=final_gift_name,
                gift_id=gift_id,
                slug=slug
            )
            
            # Подсчитываем количество (используем эмодзи или имя для группировки)
            if emoji:
                gift_counts[emoji] = gift_counts.get(emoji, 0) + 1
            elif final_gift_name:
                # Если нет эмодзи, группируем по имени
                gift_counts[final_gift_name] = gift_counts.get(final_gift_name, 0) + 1
        
        # Очищаем подарки, которых больше нет в профиле релеера
        if available_message_ids:
            deleted_count = await database.clear_unavailable_gifts(available_message_ids)
            if deleted_count > 0:
                logger.info(f"🗑️ Удалено {deleted_count} недоступных подарков из базы данных")
        
        return gift_counts
    except Exception as e:
        logger.error(f"❌ Ошибка при синхронизации подарков: {e}", exc_info=True)
        return {}


# Хендлер для получения всех входящих УНИКАЛЬНЫХ (NFT) подарков
async def setup_gift_handler(client: TelegramClient, database, bot=None):
    """Настроить обработчик входящих подарков"""
    @client.on(events.Raw())
    async def handler(event):
        if isinstance(event, types.UpdateNewMessage):
            if isinstance(event.message, types.MessageService):
                if isinstance(event.message.action, types.MessageActionStarGiftUnique):
                    gift = event.message.action.gift
                    logger.info(f"🎁 Получен новый подарок: {gift}")
                    
                    # Извлекаем информацию о подарке
                    gift_id = gift.gift_id if hasattr(gift, 'gift_id') else None
                    slug = gift.slug if hasattr(gift, 'slug') else None
                    
                    # Пытаемся определить подарок по атрибутам
                    gift_info = None
                    emoji = None
                    gift_name = None
                    gift_price_ton = None
                    
                    # Получаем информацию о подарке из title и атрибутов
                    # Сначала пытаемся использовать title
                    if hasattr(gift, 'title') and gift.title:
                        gift_info = get_gift_info_by_name(gift.title)
                        if gift_info:
                            emoji = gift_info.get("emoji", "")
                            gift_name = gift_info.get("name")
                            gift_price_ton = gift_info.get("price_ton")
                            logger.info(f"✅ Подарок определен по title: {gift_name} ({emoji}), цена: {gift_price_ton} TON")
                        else:
                            # Если не нашли в конфиге, используем title как имя
                            gift_name = gift.title
                            logger.warning(f"⚠️ Подарок '{gift.title}' не найден в конфиге, используем title как имя")
                    
                    # Если не нашли по title, пытаемся по атрибутам
                    if not gift_info and hasattr(gift, 'attributes') and gift.attributes:
                        gift_info = get_gift_info_from_attributes(gift)
                        if gift_info:
                            emoji = gift_info.get("emoji", "")
                            gift_name = gift_info.get("name")
                            gift_price_ton = gift_info.get("price_ton")
                            logger.info(f"✅ Подарок определен по атрибутам: {gift_name} ({emoji}), цена: {gift_price_ton} TON")
                    
                    # Если все еще не нашли, используем title как имя (если есть)
                    if not gift_name and hasattr(gift, 'title') and gift.title:
                        gift_name = gift.title
                        logger.warning(f"⚠️ Подарок не найден в конфиге, используем title: {gift_name}")
                    
                    # Если не удалось определить по атрибутам, пытаемся по slug
                    if not gift_info and slug:
                        logger.warning(f"⚠️ Не удалось определить подарок по атрибутам, slug: {slug}")
                        # Можно попробовать использовать slug для получения информации через API
                        # Но пока оставляем как есть
                    
                    # Если не удалось определить, оставляем пустым
                    if not emoji:
                        emoji = ""
                    
                    # Получаем информацию об отправителе
                    from_user_id = event.message.peer_id.user_id if hasattr(event.message.peer_id, 'user_id') else None
                    from_username = None
                    
                    # Проверяем, является ли сообщение входящим (когда релееру отправляют подарок) или исходящим (когда релеер отправляет)
                    # Если event.message.out == True, то это исходящее сообщение (релеер отправляет подарок) - это НЕ депозит
                    # Если event.message.out == False, то это входящее сообщение (релееру отправляют подарок) - это депозит
                    is_outgoing = getattr(event.message, 'out', False)
                    
                    if from_user_id:
                        try:
                            user = await client.get_entity(from_user_id)
                            from_username = user.username if hasattr(user, 'username') else None
                        except:
                            pass
                    
                    # Проверяем, является ли отправитель пользователем бота (депозит)
                    # Если пользователь отправил подарок релееру, зачисляем баланс
                    # Проверяем, что это не сообщение из канала (т.е. это личное сообщение)
                    # И что это входящее сообщение (не исходящее)
                    is_deposit = False
                    if from_user_id and bot and hasattr(event.message.peer_id, 'user_id') and not is_outgoing:
                        # Это входящее личное сообщение от пользователя - депозит
                        is_deposit = True
                        logger.info(f"📥 Обнаружен входящий подарок от пользователя {from_user_id} - это депозит")
                    elif is_outgoing:
                        logger.info(f"📤 Обнаружен исходящий подарок (релеер отправляет) - это НЕ депозит, пропускаю обработку депозита")
                    
                    if is_deposit:
                        try:
                            # Для депозита используем информацию о подарке
                            from ton_price import get_ton_to_usd_rate, ton_to_usd
                            
                            # Сначала пытаемся использовать title напрямую
                            if not gift_info and hasattr(gift, 'title') and gift.title:
                                gift_info = get_gift_info_by_name(gift.title)
                                if gift_info:
                                    emoji = gift_info.get("emoji", "")
                                    gift_name = gift_info.get("name")
                                    gift_price_ton = gift_info.get("price_ton")
                                    logger.info(f"✅ Подарок определен по title при депозите: {gift_name} ({emoji}), цена: {gift_price_ton} TON")
                            
                            # Если не нашли по title, пытаемся по атрибутам
                            if not gift_info:
                                gift_info = get_gift_info_from_attributes(gift)
                                if gift_info:
                                    emoji = gift_info.get("emoji", "")
                                    gift_name = gift_info.get("name")
                                    gift_price_ton = gift_info.get("price_ton")
                                    logger.info(f"✅ Подарок определен по атрибутам при депозите: {gift_name} ({emoji}), цена: {gift_price_ton} TON")
                            
                            # Если все еще не нашли, используем title как имя
                            if not gift_name and hasattr(gift, 'title') and gift.title:
                                gift_name = gift.title
                                logger.warning(f"⚠️ Подарок '{gift.title}' не найден в конфиге при депозите, используем title как имя")
                            
                            # Если нашли подарок в конфиге, зачисляем баланс
                            # При депозите цена на 10% меньше базовой
                            if gift_price_ton and gift_name:
                                ton_rate = await get_ton_to_usd_rate()
                                deposit_price_ton = gift_price_ton * 0.9  # -10% при депозите
                                gift_price_usd = ton_to_usd(deposit_price_ton, ton_rate)
                                
                                # Проверяем, существует ли пользователь в базе данных
                                user = await database.get_user(from_user_id)
                                if not user:
                                    # Создаем пользователя, если его нет
                                    username = from_username or f"user_{from_user_id}"
                                    await database.create_user(from_user_id, username)
                                    logger.info(f"✅ Создан новый пользователь {from_user_id} при депозите подарком")
                                
                                # Зачисляем баланс пользователю
                                await database.update_balance(from_user_id, gift_price_usd)
                                await database.add_deposit(from_user_id, gift_price_usd, "gift")
                                
                                # Отправляем уведомление пользователю
                                try:
                                    gift_display = f"{emoji} " if emoji else ""
                                    # Формируем ссылку на подарок
                                    gift_link = f"https://t.me/nft/{slug}" if slug else None
                                    
                                    message_text = f"Ваш подарок "
                                    if gift_link:
                                        message_text += f"<a href=\"{gift_link}\">{gift_display}{gift_name}</a>"
                                    else:
                                        message_text += f"{gift_display}{gift_name}"
                                    message_text += f" добавлен, на ваш баланс зачислено - {deposit_price_ton:.4f} TON (${gift_price_usd:.2f})"
                                    
                                    await bot.send_message(
                                        from_user_id,
                                        message_text,
                                        parse_mode="HTML",
                                        disable_web_page_preview=True
                                    )
                                    logger.info(f"✅ Баланс зачислен пользователю {from_user_id} за подарок {gift_name}: {gift_price_usd:.2f} USD")
                                except Exception as e:
                                    logger.error(f"Ошибка отправки уведомления пользователю {from_user_id}: {e}")
                            else:
                                logger.warning(f"⚠️ Не удалось определить подарок для пользователя {from_user_id}. Slug: {slug}, атрибуты: {[attr.name for attr in (gift.attributes if hasattr(gift, 'attributes') and gift.attributes else [])]}")
                        except Exception as e:
                            logger.error(f"Ошибка при обработке депозита подарком: {e}", exc_info=True)
                    
                    # Добавляем в базу данных (для вывода)
                    # Используем title как имя, если gift_name не определен
                    final_gift_name = gift_name
                    if not final_gift_name and hasattr(gift, 'title') and gift.title:
                        final_gift_name = gift.title
                    
                    await database.add_relay_gift(
                        message_id=event.message.id,
                        emoji=emoji,
                        gift_name=final_gift_name,
                        gift_id=gift_id,
                        slug=slug,
                        gift_date=event.message.date.timestamp() if hasattr(event.message, 'date') else None,
                        from_user_id=from_user_id,
                        from_username=from_username
                    )
                    
                    # Уведомления админам о новых подарках отключены по запросу


async def start_gifts_sync(database, interval_seconds: int = 60):
    """Автоматическая синхронизация подарков релеера с базой данных каждые N секунд"""
    logger.info(f"🔄 Запуск автоматической синхронизации подарков (интервал: {interval_seconds} секунд)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            
            if not _relay_client:
                logger.warning("⚠️ Клиент релеера не инициализирован, пропускаю синхронизацию")
                continue
            
            logger.info("🔄 Начинаю автоматическую синхронизацию подарков...")
            gift_counts = await sync_relay_gifts_to_db(database)
            
            if gift_counts:
                total_gifts = sum(gift_counts.values())
                logger.info(f"✅ Синхронизация завершена. Доступно подарков: {total_gifts} (типов: {len(gift_counts)})")
            else:
                logger.info("✅ Синхронизация завершена. Доступных подарков не найдено")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при автоматической синхронизации подарков: {e}", exc_info=True)
            # Продолжаем работу даже при ошибке, ждем перед следующей попыткой
            await asyncio.sleep(interval_seconds)

