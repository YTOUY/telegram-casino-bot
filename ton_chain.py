import aiohttp
import logging
import base64
from typing import Optional, Tuple, List, Dict
from config import TONCENTER_API_KEY, TON_ADDRESS

logger = logging.getLogger(__name__)

TONCENTER_API = "https://toncenter.com/api/v2"
# Минимальная сумма депозита: 0.1 TON (в наноTON)
MIN_DEPOSIT_NANO = int(0.1 * 1e9)  # 100,000,000 наноTON = 0.1 TON


async def find_incoming_tx_by_comment(
    address: str,
    comment: str,
    min_amount_nano: int,
    limit: int = 50,
) -> Optional[Tuple[str, int]]:
    """
    Ищет входящую транзакцию на address с текстовым комментарием == comment
    и суммой >= min_amount_nano. Возвращает (tx_hash, amount_nano) или None.
    """
    params = {
        "address": address,
        "limit": limit,
        "archival": "true",
    }
    # Поддержка обоих методов авторизации: query параметр или заголовок
    headers = {}
    if TONCENTER_API_KEY:
        # Используем query параметр (поддерживается и работает)
        params["api_key"] = TONCENTER_API_KEY
        # Также можно использовать заголовок X-API-Key (дополнительная опция)
        # headers["X-API-Key"] = TONCENTER_API_KEY

    url = f"{TONCENTER_API}/getTransactions"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            try:
                data = await resp.json()
            except Exception:
                logger.error("TONCENTER getTransactions: failed to decode JSON")
                return None

            if resp.status != 200 or not data.get("ok"):
                logger.error(f"TONCENTER error: HTTP {resp.status}, body={data}")
                return None

            transactions = data.get("result", [])
            # Перебираем транзакции, ищем входящие (in_msg) с нужным комментом
            for tx in transactions:
                in_msg = tx.get("in_msg") or {}
                value_str = in_msg.get("value", "0")
                msg_data = in_msg.get("msg_data") or {}
                tx_comment = None
                if isinstance(msg_data, dict):
                    tx_comment = msg_data.get("text") or msg_data.get("comment")

                try:
                    amount_nano = int(value_str)
                except Exception:
                    amount_nano = 0

                # Проверяем сумму и ровное совпадение комментария
                if amount_nano >= min_amount_nano and tx_comment is not None and str(tx_comment).strip() == str(comment).strip():
                    tx_hash = tx.get("transaction_id", {}).get("hash") or tx.get("utime_string") or ""
                    if tx_hash:
                        return tx_hash, amount_nano
    return None


async def get_all_incoming_transactions(address: str, limit: int = 100) -> List[Dict]:
    """
    Получает все входящие транзакции на адрес.
    Возвращает список транзакций с комментариями и суммами.
    """
    params = {
        "address": address,
        "limit": limit,
        "archival": "true",
    }
    # Поддержка обоих методов авторизации: query параметр или заголовок
    headers = {}
    if TONCENTER_API_KEY:
        # Используем query параметр (поддерживается и работает)
        params["api_key"] = TONCENTER_API_KEY
        # Также можно использовать заголовок X-API-Key (дополнительная опция)
        # headers["X-API-Key"] = TONCENTER_API_KEY

    url = f"{TONCENTER_API}/getTransactions"
    transactions = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=15) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    logger.error("TONCENTER getTransactions: failed to decode JSON")
                    return []

                if resp.status != 200 or not data.get("ok"):
                    logger.error(f"TONCENTER error: HTTP {resp.status}, body={data}")
                    return []

                tx_list = data.get("result", [])
                for tx in tx_list:
                    in_msg = tx.get("in_msg")
                    if not in_msg:
                        continue
                    
                    value_str = in_msg.get("value", "0")
                    msg_data = in_msg.get("msg_data") or {}
                    
                    # Извлекаем комментарий из разных полей
                    tx_comment = None
                    if isinstance(msg_data, dict):
                        # В TON комментарии могут быть в разных форматах:
                        # 1. Прямой текст (text)
                        # 2. Base64 закодированный текст
                        # 3. Hex закодированный текст
                        
                        # Сначала пробуем прямые поля
                        tx_comment = (
                            msg_data.get("text") 
                            or msg_data.get("comment")
                            or msg_data.get("msg_body")
                            or msg_data.get("body")
                            or (msg_data.get("msg") if isinstance(msg_data.get("msg"), str) else None)
                        )
                        
                        # Если есть base64 или hex данные, пробуем декодировать
                        if not tx_comment:
                            # Пробуем base64 декодирование
                            base64_data = msg_data.get("base64") or msg_data.get("b64")
                            if base64_data:
                                try:
                                    decoded = base64.b64decode(base64_data)
                                    tx_comment = decoded.decode('utf-8', errors='ignore').strip()
                                    logger.debug(f"🔓 Декодирован base64 комментарий: {tx_comment}")
                                except Exception as e:
                                    logger.debug(f"⚠️ Ошибка декодирования base64: {e}")
                            
                            # Пробуем hex декодирование
                            if not tx_comment:
                                hex_data = msg_data.get("hex") or msg_data.get("body_hex")
                                if hex_data and isinstance(hex_data, str):
                                    try:
                                        decoded = bytes.fromhex(hex_data)
                                        tx_comment = decoded.decode('utf-8', errors='ignore').strip()
                                        logger.debug(f"🔓 Декодирован hex комментарий: {tx_comment}")
                                    except Exception as e:
                                        logger.debug(f"⚠️ Ошибка декодирования hex: {e}")
                    
                    # Если не нашли в msg_data, пробуем в корне in_msg
                    if not tx_comment and isinstance(in_msg, dict):
                        tx_comment = in_msg.get("message") or in_msg.get("comment") or in_msg.get("text")
                    
                    # Если комментарий все еще base64 строка, пробуем декодировать
                    if tx_comment and isinstance(tx_comment, str) and len(tx_comment) > 0:
                        # Проверяем, является ли это base64
                        try:
                            # Пробуем декодировать как base64
                            decoded = base64.b64decode(tx_comment)
                            decoded_str = decoded.decode('utf-8', errors='ignore').strip()
                            # Если декодирование успешно и результат не пустой, используем его
                            if decoded_str and decoded_str.isprintable():
                                tx_comment = decoded_str
                                logger.debug(f"🔓 Декодирован base64 комментарий из строки: {tx_comment}")
                        except Exception:
                            # Не base64, оставляем как есть
                            pass
                    
                    try:
                        amount_nano = int(value_str)
                    except Exception:
                        amount_nano = 0
                    
                    # Получаем хеш транзакции
                    tx_hash_obj = tx.get("transaction_id") or {}
                    tx_hash = None
                    if isinstance(tx_hash_obj, dict):
                        tx_hash = tx_hash_obj.get("hash")
                    elif isinstance(tx_hash_obj, str):
                        tx_hash = tx_hash_obj
                    
                    if not tx_hash:
                        # Попробуем получить из другого поля
                        tx_hash = tx.get("hash") or tx.get("transaction_id")
                    
                    if tx_hash and amount_nano >= MIN_DEPOSIT_NANO:
                        transactions.append({
                            "hash": tx_hash,
                            "amount_nano": amount_nano,
                            "comment": tx_comment,
                            "lt": tx.get("transaction_id", {}).get("lt") or tx.get("lt"),
                            "utime": tx.get("utime") or tx.get("transaction_id", {}).get("utime"),
                        })
    except Exception as e:
        logger.error(f"Ошибка при получении транзакций: {e}", exc_info=True)
    
    return transactions
