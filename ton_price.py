"""
Модуль для получения актуального курса TON к USD
Использует CoinGecko API (бесплатный, не требует API ключа)
"""
import aiohttp
import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)

# Кэш для курса (обновляется каждые 5 минут)
_ton_price_cache = {
    "price": 2.5,  # Значение по умолчанию
    "timestamp": 0
}

CACHE_DURATION = 300  # 5 минут в секундах


async def get_ton_to_usd_rate() -> float:
    """
    Получить актуальный курс TON к USD
    Использует кэш для уменьшения количества запросов к API
    """
    import time
    current_time = time.time()
    
    # Проверяем кэш
    if current_time - _ton_price_cache["timestamp"] < CACHE_DURATION:
        return _ton_price_cache["price"]
    
    try:
        async with aiohttp.ClientSession() as session:
            # CoinGecko API для получения цены TON
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "the-open-network",
                "vs_currencies": "usd"
            }
            
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=2)) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get("the-open-network", {}).get("usd")
                    
                    if price:
                        _ton_price_cache["price"] = float(price)
                        _ton_price_cache["timestamp"] = current_time
                        logger.info(f"Курс TON обновлен: ${price}")
                        return float(price)
                    else:
                        logger.warning("Не удалось получить цену TON из ответа API")
                        return _ton_price_cache["price"]
                else:
                    logger.warning(f"Ошибка API CoinGecko: статус {response.status}")
                    return _ton_price_cache["price"]
                    
    except asyncio.TimeoutError:
        logger.warning("Таймаут при запросе курса TON")
        return _ton_price_cache["price"]
    except Exception as e:
        logger.error(f"Ошибка при получении курса TON: {e}")
        return _ton_price_cache["price"]


def usd_to_ton(usd_amount: float, ton_rate: Optional[float] = None) -> float:
    """
    Конвертировать USD в TON
    Если ton_rate не указан, используется кэшированное значение
    """
    if ton_rate is None:
        ton_rate = _ton_price_cache["price"]
    return usd_amount / ton_rate if ton_rate > 0 else 0.0


def ton_to_usd(ton_amount: float, ton_rate: Optional[float] = None) -> float:
    """
    Конвертировать TON в USD
    Если ton_rate не указан, используется кэшированное значение
    """
    if ton_rate is None:
        ton_rate = _ton_price_cache["price"]
    return ton_amount * ton_rate



















