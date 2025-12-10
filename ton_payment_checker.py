"""
Автоматическая проверка TON транзакций и начисление баланса пользователям
"""
import asyncio
import logging
from typing import Optional
from database import Database
from ton_chain import get_all_incoming_transactions, MIN_DEPOSIT_NANO
from ton_price import get_ton_to_usd_rate, ton_to_usd, usd_to_ton
from config import TON_ADDRESS, BOT_TOKEN
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)

db = Database()

# Глобальный экземпляр бота для отправки сообщений
bot_instance: Optional[Bot] = None

def set_bot_instance(bot: Bot):
    """Установить экземпляр бота для отправки уведомлений"""
    global bot_instance
    bot_instance = bot


async def process_ton_payments():
    """
    Проверяет все входящие TON транзакции и автоматически начисляет баланс
    пользователям по memo (user_id).
    """
    try:
        logger.info(f"🔍 Проверяю TON транзакции на адресе {TON_ADDRESS}...")
        
        # Получаем все входящие транзакции
        transactions = await get_all_incoming_transactions(TON_ADDRESS, limit=100)
        
        if not transactions:
            logger.debug("Нет транзакций для проверки")
            return
        
        # Получаем курс TON к USD
        ton_rate = await get_ton_to_usd_rate()
        
        processed = 0
        credited = 0
        
        for tx in transactions:
            tx_hash = tx.get("hash")
            comment = tx.get("comment")
            amount_nano = tx.get("amount_nano", 0)
            
            logger.debug(f"🔍 Проверяю транзакцию: hash={tx_hash}, comment={comment}, amount_nano={amount_nano}")
            
            if not tx_hash:
                logger.debug(f"⚠️ Транзакция без хеша: {tx}")
                continue
            
            # Проверяем, что транзакция еще не обработана
            is_new = await db.is_chain_payment_new(tx_hash)
            if not is_new:
                logger.debug(f"⏭️ Транзакция {tx_hash} уже обработана, пропускаю")
                continue
            
            # Проверяем минимальную сумму
            if amount_nano < MIN_DEPOSIT_NANO:
                logger.info(f"⚠️ Транзакция {tx_hash} меньше минимума: {amount_nano / 1e9:.4f} TON (минимум: {MIN_DEPOSIT_NANO / 1e9:.4f} TON)")
                continue
            
            # Комментарий должен быть числом (user_id)
            if not comment:
                logger.info(f"⚠️ Транзакция {tx_hash} без комментария (memo). Сумма: {amount_nano / 1e9:.4f} TON. Пропускаю.")
                logger.debug(f"💡 Подсказка: для автоматического начисления баланса укажите ваш user_id в комментарии транзакции")
                continue
            
            # Пробуем извлечь user_id из комментария
            comment_str = str(comment).strip()
            logger.debug(f"🔍 Комментарий транзакции {tx_hash}: '{comment_str}'")
            
            try:
                user_id = int(comment_str)
                logger.debug(f"✅ Извлечен user_id из комментария: {user_id}")
            except (ValueError, TypeError) as e:
                logger.debug(f"⚠️ Не удалось извлечь user_id из комментария '{comment_str}': {e}")
                # Пропускаем транзакции с невалидным комментарием
                continue
            
            # Конвертируем сумму в USD
            amount_ton = amount_nano / 1e9
            amount_usd = ton_to_usd(amount_ton, ton_rate)
            
            # Проверяем, существует ли пользователь
            user = await db.get_user(user_id)
            if not user:
                logger.warning(f"Пользователь {user_id} не найден для транзакции {tx_hash}")
                # Пропускаем, но сохраняем транзакцию, чтобы не проверять повторно
                await db.save_chain_payment(tx_hash, user_id, amount_usd)
                continue
            
            # Начисляем баланс
            try:
                await db.update_balance(user_id, amount_usd)
                await db.add_deposit(user_id, amount_usd, "ton_auto")
                await db.save_chain_payment(tx_hash, user_id, amount_usd)
                
                # Отправляем уведомление пользователю
                if bot_instance:
                    try:
                        user_balance = await db.get_balance(user_id)
                        user_balance_ton = usd_to_ton(user_balance, ton_rate)
                        
                        notification_text = f"""✅ <b>Баланс пополнен автоматически!</b>

💰 <b>Получено:</b> {amount_ton:.4f} TON (${amount_usd:.2f})
💰 <b>Текущий баланс:</b> {user_balance_ton:.4f} TON (${user_balance:.2f})

🔗 <b>Транзакция:</b> <code>{tx_hash}</code>

<i>Спасибо за использование бота!</i>"""
                        
                        await bot_instance.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode=ParseMode.HTML
                        )
                        logger.info(f"📨 Уведомление отправлено пользователю {user_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
                
                credited += 1
                logger.info(
                    f"✅ Автоматически начислен баланс: "
                    f"user_id={user_id}, amount={amount_ton:.4f} TON (${amount_usd:.2f}), "
                    f"tx_hash={tx_hash}"
                )
            except Exception as e:
                logger.error(f"❌ Ошибка при начислении баланса для {user_id}: {e}", exc_info=True)
            
            processed += 1
        
        if credited > 0:
            logger.info(f"✨ Обработано транзакций: {processed}, начислено балансов: {credited}")
        elif processed == 0 and len(transactions) > 0:
            logger.debug(f"ℹ️ Все {len(transactions)} транзакций уже обработаны или не подходят условиям")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке TON транзакций: {e}", exc_info=True)


async def start_payment_checker(interval_seconds: int = 30):
    """
    Запускает периодическую проверку TON транзакций.
    
    Args:
        interval_seconds: Интервал проверки в секундах (по умолчанию 30)
    """
    logger.info(f"🚀 Запущен автоматический проверщик TON платежей (интервал: {interval_seconds}с)")
    
    while True:
        try:
            await process_ton_payments()
        except Exception as e:
            logger.error(f"Ошибка в проверщике платежей: {e}", exc_info=True)
        
        await asyncio.sleep(interval_seconds)

