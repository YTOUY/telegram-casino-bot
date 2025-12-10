import aiohttp
import logging
import re
from typing import Optional, Dict
from config import XROCKET_API_KEY, TON_ADDRESS

logger = logging.getLogger(__name__)

# Правильный endpoint xRocket Pay API согласно документации
XROCKET_API_BASE = "https://pay.xrocket.tg"


async def create_invoice(coin: str, amount_usd: float, memo: str) -> Optional[Dict]:
    """
    Создает инвойс в xRocket и возвращает словарь с данными:
    { 'invoice_id': str, 'inv_token': str, 'pay_url': str }
    inv_token подходит для deep-link: https://t.me/xrocket?start=inv_<inv_token>
    Формат ссылки: https://t.me/xrocket?start=inv_oinv2N6z4iHKhIZ
    """
    if not XROCKET_API_KEY:
        logger.warning("XROCKET_API_KEY is empty")
        return None
    
    logger.info(f"🔍 Attempting to create xRocket invoice: coin={coin}, amount={amount_usd}, memo={memo}")

    # Формируем payload согласно документации xRocket Pay API
    # Согласно схеме CreateInvoiceDto из документации
    currency_map = {
        "USDT": "USDT",
        "USDC": "USDC", 
        "TON": "TON"
    }
    currency = currency_map.get(coin.upper(), coin.upper())
    
    payload = {
        "amount": float(amount_usd),      # Сумма в USD
        "numPayments": 1,                 # Для разового платежа (по умолчанию 1)
        "currency": currency,             # USDT / USDC / TON
        "description": f"Пополнение баланса на ${amount_usd:.2f}",
        "hiddenMessage": "Спасибо за оплату!",
        "commentsEnabled": True,
        "payload": str(memo),             # user_id как payload для идентификации
    }
    
    # Согласно документации, авторизация через заголовок Rocket-Pay-Key
    headers = {
        "Rocket-Pay-Key": XROCKET_API_KEY,
        "Content-Type": "application/json",
    }
    
    # Правильный endpoint согласно документации: POST /tg-invoices
    url = f"{XROCKET_API_BASE}/tg-invoices"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                # Проверяем статус ответа
                if resp.status == 200 or resp.status == 201:
                    try:
                        data = await resp.json()
                        logger.info(f"xRocket createInvoice: HTTP {resp.status}, URL: {url}, data={data}")
                        
                        # Проверяем, есть ли данные
                        if data:
                            # API возвращает структуру: {'success': True, 'data': {...}}
                            # Нужно извлечь данные из поля 'data'
                            invoice_data = data.get("data") or data
                            
                            # Согласно документации, ответ содержит поле "link" со ссылкой
                            # Также может быть поле "id" для invoice_id
                            pay_url = invoice_data.get("link") or invoice_data.get("payUrl") or invoice_data.get("url")
                            invoice_id = invoice_data.get("id") or invoice_data.get("invoiceId")
                            
                            # Извлекаем токен из ссылки, если она есть
                            inv_token = None
                            if pay_url and "start=inv_" in pay_url:
                                # Извлекаем токен из ссылки https://t.me/xrocket?start=inv_xxx
                                match = re.search(r'start=inv_([^&]+)', pay_url)
                                if match:
                                    inv_token = f"inv_{match.group(1)}"
                            
                            if pay_url:
                                result = {
                                    "invoice_id": invoice_id,
                                    "inv_token": inv_token or "",
                                    "pay_url": pay_url,
                                }
                                logger.info(f"✅ xRocket invoice created successfully: {result}")
                                return result
                            else:
                                logger.warning(f"xRocket API returned data but no link found: {data}")
                        else:
                            logger.warning(f"xRocket API returned empty data, status: {resp.status}")
                    except Exception as json_error:
                        text = await resp.text()
                        logger.warning(f"xRocket API response is not JSON (URL: {url}): {text[:200]}, error: {json_error}")
                else:
                    text = await resp.text()
                    logger.warning(f"xRocket API returned status {resp.status} (URL: {url}): {text[:500]}")
                    # Если получили JSON с ошибкой, логируем полностью
                    try:
                        error_data = await resp.json()
                        logger.warning(f"xRocket API error details: {error_data}")
                    except:
                        pass
    except aiohttp.ClientError as e:
        logger.warning(f"xRocket createInvoice connection error via {url}: {e}")
    except Exception as e:
        logger.warning(f"xRocket createInvoice failed via {url}: {e}")
    
    logger.error(f"❌ xRocket createInvoice failed: all endpoints tried, none worked. Check API key and network connectivity.")
    return None


