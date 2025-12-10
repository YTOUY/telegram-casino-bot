import aiohttp
import logging
from typing import Optional, Dict
from config import CRYPTO_PAY_TOKEN

logger = logging.getLogger(__name__)

CRYPTO_PAY_API_URL = "https://pay.crypt.bot/api"


class CryptoPay:
    def __init__(self, token: str):
        self.token = token
        self.base_url = CRYPTO_PAY_API_URL
    
    async def get_invoices(
        self,
        invoice_ids: Optional[str] = None,
        status: Optional[str] = None,
        asset: Optional[str] = None,
        payload: Optional[str] = None,
        count: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Optional[Dict]:
        """Получить информацию об инвойсах"""
        url = f"{self.base_url}/getInvoices"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data: Dict = {}
        if invoice_ids:
            data["invoice_ids"] = invoice_ids
        if status:
            data["status"] = status
        if asset:
            data["asset"] = asset
        if payload:
            data["payload"] = payload
        if count is not None:
            data["count"] = count
        if offset is not None:
            data["offset"] = offset
        
        logger.info(f"📤 Запрос getInvoices: {data}")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (getInvoices): статус {response.status}, результат: {result}")
                if response.status == 200 and result.get("ok"):
                    return result.get("result")
                logger.error(f"❌ Ошибка getInvoices: HTTP {response.status}, ответ: {result}")
                return None
    
    async def create_invoice(
        self,
        asset: str = "USDT",
        amount: str = None,
        description: str = None,
        paid_btn_name: str = None,
        paid_btn_url: str = None,
        payload: str = None,
        allow_comments: bool = True,
        allow_anonymous: bool = True,
        expires_in: int = None
    ) -> Optional[Dict]:
        """Создать счет на оплату"""
        url = f"{self.base_url}/createInvoice"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data = {
            "asset": asset,
        }
        
        if amount:
            data["amount"] = amount
        if description:
            data["description"] = description
        if paid_btn_name:
            data["paid_btn_name"] = paid_btn_name
        if paid_btn_url:
            data["paid_btn_url"] = paid_btn_url
        if payload:
            data["payload"] = payload
        if expires_in:
            data["expires_in"] = expires_in
        
        data["allow_comments"] = allow_comments
        data["allow_anonymous"] = allow_anonymous
        
        logger.info(f"📤 Отправка запроса на создание инвойса: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (createInvoice): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        # Логируем ошибку от API
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        logger.error(f"❌ Crypto Pay API ошибка (createInvoice): {error_name} (код: {error_code}), сообщение: {error_message}, данные: {data}")
                        return None
                else:
                    # Логируем HTTP ошибку
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (createInvoice): статус {response.status}, ответ: {result}")
                    return None
    
    async def create_check(
        self,
        asset: str = "USDT",
        amount: str = None,
        pin_to_user_id: int = None
    ) -> Optional[Dict]:
        """Создать чек"""
        url = f"{self.base_url}/createCheck"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data = {
            "asset": asset,
        }
        
        if amount:
            data["amount"] = amount
        if pin_to_user_id:
            data["pin_to_user_id"] = pin_to_user_id
        
        logger.info(f"📤 Отправка запроса на создание чека: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (createCheck): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        # Логируем ошибку от API
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        error_description = result.get("error", {}).get("description", "")
                        logger.error(f"❌ Crypto Pay API ошибка (createCheck): {error_name} (код: {error_code}), сообщение: {error_message}, описание: {error_description}, данные: {data}")
                        # Возвращаем словарь с ошибкой для обработки
                        return {"error": True, "code": error_code, "name": error_name, "message": error_message, "description": error_description}
                else:
                    # Логируем HTTP ошибку
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (createCheck): статус {response.status}, ответ: {result}")
                    # Извлекаем информацию об ошибке из ответа, если она есть
                    error_info = result.get("error", {})
                    error_code = error_info.get("code", response.status)
                    error_name = error_info.get("name", "HTTP_ERROR")
                    error_message = error_info.get("message", "HTTP error")
                    error_description = error_info.get("description", "")
                    return {
                        "error": True,
                        "code": error_code,
                        "name": error_name,
                        "message": error_message,
                        "description": error_description
                    }
    
    async def delete_check(self, check_id: int) -> Optional[Dict]:
        """Удалить чек"""
        url = f"{self.base_url}/deleteCheck"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data = {"check_id": check_id}
        
        logger.info(f"📤 Отправка запроса на удаление чека: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (deleteCheck): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        error_description = result.get("error", {}).get("description", "")
                        logger.error(f"❌ Crypto Pay API ошибка (deleteCheck): {error_name} (код: {error_code}), сообщение: {error_message}, описание: {error_description}, данные: {data}")
                        return {
                            "error": True,
                            "code": error_code,
                            "name": error_name,
                            "message": error_message,
                            "description": error_description
                        }
                else:
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (deleteCheck): статус {response.status}, ответ: {result}")
                    error_info = result.get("error", {})
                    error_code = error_info.get("code", response.status)
                    error_name = error_info.get("name", "HTTP_ERROR")
                    error_message = error_info.get("message", "HTTP error")
                    error_description = error_info.get("description", "")
                    return {
                        "error": True,
                        "code": error_code,
                        "name": error_name,
                        "message": error_message,
                        "description": error_description
                    }
    
    async def get_checks(
        self,
        status: Optional[str] = None,
        asset: Optional[str] = None
    ) -> Optional[Dict]:
        """Получить список чеков"""
        url = f"{self.base_url}/getChecks"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        params = {}
        if status:
            params["status"] = status
        if asset:
            params["asset"] = asset
        
        logger.info(f"📤 Запрос getChecks: {params}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (getChecks): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        logger.error(f"❌ Crypto Pay API ошибка (getChecks): {error_name} (код: {error_code}), сообщение: {error_message}")
                        return None
                else:
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (getChecks): статус {response.status}, ответ: {result}")
                    return None
    
    async def get_me(self) -> Optional[Dict]:
        """Получить информацию о боте"""
        url = f"{self.base_url}/getMe"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        return result.get("result")
                return None
    
    async def get_balance(self) -> Optional[Dict]:
        """Получить баланс бота"""
        url = f"{self.base_url}/getBalance"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        logger.info(f"📤 Запрос getBalance")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (getBalance): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        logger.error(f"❌ Crypto Pay API ошибка (getBalance): {error_name} (код: {error_code}), сообщение: {error_message}")
                        return None
                else:
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (getBalance): статус {response.status}, ответ: {result}")
                    return None
    
    async def transfer(
        self,
        user_id: int,
        asset: str,
        amount: str,
        spend_id: str,
        comment: Optional[str] = None,
        disable_send_notification: bool = False
    ) -> Optional[Dict]:
        """Перевести средства пользователю"""
        url = f"{self.base_url}/transfer"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        data = {
            "user_id": user_id,
            "asset": asset,
            "amount": amount,
            "spend_id": spend_id,
        }
        
        if comment:
            data["comment"] = comment
        data["disable_send_notification"] = disable_send_notification
        
        logger.info(f"📤 Отправка запроса на перевод средств: {data}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (transfer): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result")
                    else:
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        error_description = result.get("error", {}).get("description", "")
                        logger.error(f"❌ Crypto Pay API ошибка (transfer): {error_name} (код: {error_code}), сообщение: {error_message}, описание: {error_description}, данные: {data}")
                        return {
                            "error": True,
                            "code": error_code,
                            "name": error_name,
                            "message": error_message,
                            "description": error_description
                        }
                else:
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (transfer): статус {response.status}, ответ: {result}")
                    error_info = result.get("error", {})
                    error_code = error_info.get("code", response.status)
                    error_name = error_info.get("name", "HTTP_ERROR")
                    error_message = error_info.get("message", "HTTP error")
                    error_description = error_info.get("description", "")
                    return {
                        "error": True,
                        "code": error_code,
                        "name": error_name,
                        "message": error_message,
                        "description": error_description
                    }
    
    async def get_exchange_rates(self) -> Optional[list]:
        """Получить курсы обмена"""
        url = f"{self.base_url}/getExchangeRates"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        logger.info(f"📤 Запрос getExchangeRates")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                logger.info(f"📡 Crypto Pay API ответ (getExchangeRates): статус {response.status}, результат: {result}")
                if response.status == 200:
                    if result.get("ok"):
                        return result.get("result", [])
                    else:
                        error_code = result.get("error", {}).get("code", "unknown")
                        error_name = result.get("error", {}).get("name", "unknown")
                        error_message = result.get("error", {}).get("message", "unknown")
                        logger.error(f"❌ Crypto Pay API ошибка (getExchangeRates): {error_name} (код: {error_code}), сообщение: {error_message}")
                        return None
                else:
                    logger.error(f"❌ Crypto Pay API HTTP ошибка (getExchangeRates): статус {response.status}, ответ: {result}")
                    return None


# Создаем глобальный экземпляр
crypto_pay = CryptoPay(CRYPTO_PAY_TOKEN)

