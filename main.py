import asyncio
import logging
import os
from datetime import datetime, time
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

from config import BOT_TOKEN, ADMIN_IDS
from database import Database
from handlers import (
    start_router,
    games_router,
    deposit_router,
    settings_router,
    referral_router,
    admin_router,
    inline_router,
    pvp_router,
    lottery_router,
)
from handlers.mini_app import router as mini_app_router
from handlers.group_commands import router as group_commands_router
from handlers.chat_tracking import router as chat_tracking_router
from middlewares.subscription import SubscriptionMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def start_bot():
    """Главная функция запуска бота"""
    # Инициализация базы данных
    db = Database()
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    logger.info(f"📋 Админы: {ADMIN_IDS}")
    
    # Регистрация middleware для проверки подписки
    # Применяем только к роутерам, которые не являются админскими
    subscription_middleware = SubscriptionMiddleware()
    
    # Регистрация роутеров
    # ВАЖНО: games_router должен быть ПЕРВЫМ для обработки dice сообщений
    # чтобы они не перехватывались другими обработчиками
    logger.info("Регистрация роутеров...")
    dp.include_router(admin_router)  # Админ панель ПЕРВОЙ для обработки команд /admin (без middleware)
    logger.info("  ✓ admin_router зарегистрирован (первым для команд)")
    dp.include_router(group_commands_router)  # Групповые команды ПЕРВЫМИ для обработки команд в группах
    logger.info("  ✓ group_commands_router зарегистрирован (для групповых команд)")
    dp.include_router(pvp_router)  # PvP роутер ПЕРЕД games_router для обработки PvP команд в группах
    logger.info("  ✓ pvp_router зарегистрирован (перед games_router для PvP команд)")
    dp.include_router(games_router)  # Игры ПОСЛЕ group_commands для обработки игровых команд в группах
    logger.info("  ✓ games_router зарегистрирован (для игровых команд в группах)")
    dp.include_router(start_router)
    logger.info("  ✓ start_router зарегистрирован")
    dp.include_router(referral_router)  # Регистрируем раньше deposit_router для приоритета обработки withdraw_referral_balance
    logger.info("  ✓ referral_router зарегистрирован")
    dp.include_router(deposit_router)
    logger.info("  ✓ deposit_router зарегистрирован")
    dp.include_router(lottery_router)  # Регистрируем раньше settings_router для приоритета обработки lottery_menu
    logger.info("  ✓ lottery_router зарегистрирован")
    dp.include_router(settings_router)
    logger.info("  ✓ settings_router зарегистрирован")
    dp.include_router(inline_router)
    logger.info("  ✓ inline_router зарегистрирован")
    dp.include_router(mini_app_router)
    logger.info("  ✓ mini_app_router зарегистрирован")
    dp.include_router(chat_tracking_router)  # Отслеживание чатов В КОНЦЕ, чтобы не мешать другим обработчикам
    logger.info("  ✓ chat_tracking_router зарегистрирован (для отслеживания чатов)")
    
    # Применяем middleware для проверки подписки ко всем роутерам кроме админского
    routers_to_check = [
        start_router,
        games_router,
        deposit_router,
        settings_router,
        referral_router,
        inline_router,
        pvp_router,
        lottery_router,
        group_commands_router,
        chat_tracking_router,
    ]
    
    for router_obj in routers_to_check:
        router_obj.message.middleware(subscription_middleware)
        router_obj.callback_query.middleware(subscription_middleware)
    
    logger.info("  ✓ SubscriptionMiddleware применен ко всем роутерам (кроме admin)")
    
    # Проверяем количество зарегистрированных обработчиков
    try:
        # В aiogram 3.x обработчики хранятся в dp.callback_query.handlers
        total_handlers = len(list(dp.callback_query.handlers))
        logger.info(f"Всего обработчиков callback_query: {total_handlers}")
        
        # Проверяем обработчики в каждом роутере
        for router_name, router_obj in [
            ("admin", admin_router),
            ("start", start_router),
            ("games", games_router),
            ("deposit", deposit_router),
            ("settings", settings_router),
            ("referral", referral_router),
            ("pvp", pvp_router),
            ("inline", inline_router),
        ]:
            router_handlers = len(list(router_obj.callback_query.handlers))
            if router_handlers > 0:
                logger.info(f"  {router_name}_router: {router_handlers} обработчиков callback_query")
            
            # Проверяем обработчики команд
            message_handlers = list(router_obj.message.handlers)
            command_handlers = [h for h in message_handlers if hasattr(h, 'filters')]
            if command_handlers:
                logger.info(f"  {router_name}_router: {len(message_handlers)} обработчиков сообщений")
    except Exception as e:
        logger.warning(f"Ошибка при проверке обработчиков: {e}")
    
    logger.info("Бот запущен")
    
    # Запуск автоматического проверщика TON платежей (в фоне)
    try:
        from ton_payment_checker import start_payment_checker, set_bot_instance
        # Передаем экземпляр бота для отправки уведомлений
        set_bot_instance(bot)
        # Запускаем проверщик платежей каждые 30 секунд
        asyncio.create_task(start_payment_checker(interval_seconds=30))
        logger.info("Автоматический проверщик TON платежей запущен")
    except Exception as e:
        logger.warning(f"Не удалось запустить проверщик TON платежей: {e}")
        logger.warning("Автоматическое начисление TON платежей будет недоступно")
    
    # Инициализация релеера для работы с подарками
    try:
        from relay_account import init_relay_client, sync_relay_gifts_to_db, setup_gift_handler, get_relay_client
        relay_initialized = await init_relay_client()
        
        if relay_initialized:
            logger.info("✅ Релеер успешно инициализирован")
            
            # Синхронизируем подарки с базой данных
            gift_counts = await sync_relay_gifts_to_db(db)
            
            # Настраиваем обработчик входящих подарков
            relay_client = get_relay_client()
            if relay_client:
                await setup_gift_handler(relay_client, db, bot)
                logger.info("✅ Обработчик входящих подарков настроен")
            
            # Запускаем автоматическую синхронизацию подарков каждую минуту
            from relay_account import start_gifts_sync
            asyncio.create_task(start_gifts_sync(db, interval_seconds=60))
            logger.info("✅ Автоматическая синхронизация подарков запущена (каждую минуту)")
            
            # Отправляем уведомление админам о подарках на аккаунте релеера
            from relay_account import get_self_gifts, get_relay_client
            
            relay_client = get_relay_client()
            if relay_client:
                try:
                    gifts = await get_self_gifts(relay_client)
                    total_gifts = len(gifts)
                    
                    message = f"🎁 <b>Подарки на аккаунте релеера</b>\n\n"
                    message += f"Всего подарков: <b>{total_gifts}</b>\n\n"
                    message += "Отправляйте подарки на <a href=\"https://t.me/arbuzrelayer\">@arbuzrelayer</a>\n\n"
                    
                    if gifts:
                        message += "<b>Ссылки на подарки:</b>\n\n"
                        # Группируем подарки по названию для подсчета
                        gifts_by_name = {}
                        for gift in gifts:
                            gift_title = gift.gift.title if hasattr(gift.gift, 'title') and gift.gift.title else "Неизвестный"
                            slug = gift.gift.slug if hasattr(gift.gift, 'slug') else None
                            
                            if slug:
                                gift_link = f"https://t.me/nft/{slug}"
                                if gift_title not in gifts_by_name:
                                    gifts_by_name[gift_title] = {"count": 0, "link": gift_link}
                                gifts_by_name[gift_title]["count"] += 1
                        
                        # Сортируем по количеству (от большего к меньшему)
                        sorted_gifts = sorted(gifts_by_name.items(), key=lambda x: x[1]["count"], reverse=True)
                        
                        for gift_title, gift_data in sorted_gifts:
                            count = gift_data["count"]
                            link = gift_data["link"]
                            if count > 1:
                                message += f"<a href=\"{link}\">{gift_title}</a> — {count} шт.\n"
                            else:
                                message += f"<a href=\"{link}\">{gift_title}</a>\n"
                    else:
                        message += "На аккаунте релеера пока нет подарков."
                    
                    # Отправляем каждому админу
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(admin_id, message, parse_mode="HTML", disable_web_page_preview=True)
                            logger.info(f"✅ Уведомление о подарках отправлено админу {admin_id}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки уведомления админу {admin_id}: {e}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении подарков для админов: {e}", exc_info=True)
        else:
            logger.warning("⚠️ Не удалось инициализировать релеера")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации релеера: {e}", exc_info=True)
        logger.warning("⚠️ Функционал работы с подарками будет недоступен")
    
    # Запуск планировщика автоматических задач для PvP #100
    try:
        from handlers.pvp import send_pvp_100_10min_reminder, auto_finish_pvp_100
        asyncio.create_task(schedule_pvp_100_tasks(bot))
        logger.info("✅ Планировщик автоматических задач PvP #100 запущен")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика PvP #100: {e}", exc_info=True)
    
    # Запуск планировщика для автоматической проверки и завершения лотерей
    try:
        asyncio.create_task(schedule_lottery_checker(bot))
        logger.info("✅ Планировщик автоматических лотерей запущен")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске планировщика лотерей: {e}", exc_info=True)
    
    # Запуск API сервера параллельно с ботом
    try:
        from api_server import start_api_server
        api_port = int(os.getenv("API_PORT", "8080"))
        api_runner = await start_api_server(port=api_port)
        logger.info(f"✅ API сервер запущен на порту {api_port}")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске API сервера: {e}", exc_info=True)
        logger.warning("⚠️ API сервер не запущен, мини-апп может не работать")
    
    # Запуск polling с skip_updates для пропуска старых обновлений
    await dp.start_polling(bot, skip_updates=True)


async def schedule_pvp_100_tasks(bot: Bot):
    """Планировщик автоматических задач для PvP #100"""
    from handlers.pvp import send_pvp_100_10min_reminder, auto_finish_pvp_100
    
    reminder_time = time(22, 55)  # 22:55
    finish_time = time(23, 5)     # 23:05
    
    reminder_sent_today = False
    finish_done_today = False
    last_date = datetime.now().date()
    
    logger.info("🕐 Планировщик PvP #100 запущен. Ожидание времени 22:55 и 23:05...")
    
    while True:
        try:
            now = datetime.now()
            current_time = now.time()
            current_date = now.date()
            
            # Сбрасываем флаги при смене дня
            if current_date != last_date:
                reminder_sent_today = False
                finish_done_today = False
                last_date = current_date
                logger.info("🔄 Новый день, сброс флагов планировщика")
            
            # Проверяем, нужно ли отправить напоминание в 22:55
            if not reminder_sent_today:
                if current_time.hour == reminder_time.hour and current_time.minute == reminder_time.minute:
                    logger.info("⏰ Время 22:55! Отправляю напоминание о дуэли #100...")
                    try:
                        await send_pvp_100_10min_reminder(bot)
                        reminder_sent_today = True
                        logger.info("✅ Напоминание за 10 минут отправлено")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при отправке напоминания: {e}", exc_info=True)
            
            # Проверяем, нужно ли завершить дуэль в 23:05 или позже
            if not finish_done_today:
                # Если уже прошло 23:05, завершаем дуэль
                if (current_time.hour > finish_time.hour or 
                    (current_time.hour == finish_time.hour and current_time.minute >= finish_time.minute)):
                    logger.info("⏰ Время 23:05 или позже! Запускаю игру дуэли #100...")
                    try:
                        await auto_finish_pvp_100(bot)
                        finish_done_today = True
                        logger.info("✅ Автоматическое завершение дуэли #100 выполнено")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при автоматическом завершении: {e}", exc_info=True)
            
            # Если мы близко к нужному времени, проверяем чаще (каждые 10 секунд)
            # Иначе проверяем каждую минуту
            if ((current_time.hour == 22 and current_time.minute >= 54) or 
                (current_time.hour == 23 and current_time.minute <= 6)):
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд в критическое время
            else:
                await asyncio.sleep(60)  # Проверяем каждую минуту в остальное время
            
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике PvP #100: {e}", exc_info=True)
            await asyncio.sleep(60)  # Ждем минуту перед повтором


async def schedule_lottery_checker(bot: Bot):
    """Планировщик для автоматической проверки и завершения лотерей"""
    logger.info("🎫 Планировщик лотерей запущен. Проверка каждую минуту...")
    db = Database()  # Создаем экземпляр базы данных
    
    while True:
        try:
            # Проверяем все активные лотереи
            lotteries = await db.get_active_lotteries()
            
            for lottery in lotteries:
                try:
                    should_finish = False
                    
                    # Проверяем условие завершения по времени
                    if lottery["finish_type"] == "time" and lottery["finish_datetime"]:
                        try:
                            finish_datetime = datetime.strptime(lottery["finish_datetime"], "%Y-%m-%d %H:%M")
                            if datetime.now() >= finish_datetime:
                                should_finish = True
                                logger.info(f"🎫 Лотерея #{lottery['id']} завершается по времени")
                        except ValueError:
                            logger.error(f"❌ Ошибка парсинга времени завершения для лотереи #{lottery['id']}")
                    
                    # Проверяем условие завершения по участникам
                    elif lottery["finish_type"] == "participants" and lottery["finish_participants"]:
                        if lottery["total_tickets"] >= lottery["finish_participants"]:
                            should_finish = True
                            logger.info(f"🎫 Лотерея #{lottery['id']} завершается по количеству участников")
                    
                    # Если нужно завершить - проводим розыгрыш
                    if should_finish:
                        await finish_lottery_draw(bot, lottery["id"])
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка при проверке лотереи #{lottery['id']}: {e}", exc_info=True)
            
            # Проверяем каждую минуту
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике лотерей: {e}", exc_info=True)
            await asyncio.sleep(60)


async def finish_lottery_draw(bot: Bot, lottery_id: int):
    """Завершить лотерею и провести розыгрыш"""
    import random
    db = Database()  # Создаем экземпляр базы данных
    
    try:
        lottery = await db.get_lottery(lottery_id)
        
        if not lottery or lottery["status"] != "active":
            return
        
        tickets = await db.get_lottery_tickets(lottery_id)
        if not tickets:
            logger.warning(f"🎫 Лотерея #{lottery_id} не имеет билетов")
            await db.finish_lottery(lottery_id)
            return
        
        prizes = await db.get_lottery_prizes(lottery_id)
        if not prizes:
            logger.warning(f"🎫 Лотерея #{lottery_id} не имеет призов")
            await db.finish_lottery(lottery_id)
            return
        
        # Сортируем призы по позиции
        prizes = sorted(prizes, key=lambda x: x["position"])
        
        # Проводим розыгрыш
        winners = []
        available_tickets = tickets.copy()
        
        for prize in prizes:
            if not available_tickets:
                break
            
            # Выбираем случайный билет
            winning_ticket = random.choice(available_tickets)
            available_tickets.remove(winning_ticket)
            
            winners.append({
                "ticket": winning_ticket,
                "prize": prize
            })
        
        # Сохраняем победителей и начисляем призы
        for winner_info in winners:
            ticket = winner_info["ticket"]
            prize = winner_info["prize"]
            
            # Добавляем победителя
            await db.add_lottery_winner(
                lottery_id=lottery_id,
                user_id=ticket["user_id"],
                ticket_number=ticket["ticket_number"],
                prize_type=prize["prize_type"],
                prize_value=prize["prize_value"],
                prize_description=prize["prize_description"],
                position=prize["position"]
            )
            
            # Начисляем приз
            if prize["prize_type"] == "balance":
                amount = float(prize["prize_value"])
                await db.update_balance(ticket["user_id"], amount)
                
                # Отправляем уведомление
                try:
                    await bot.send_message(
                        ticket["user_id"],
                        f"🎉 <b>Поздравляем! Вы выиграли в лотерее!</b>\n\n"
                        f"🎫 <b>Лотерея:</b> {lottery['title']}\n"
                        f"🎫 <b>Билет:</b> #{ticket['ticket_number']}\n"
                        f"🏆 <b>Место:</b> {prize['position']}\n"
                        f"💰 <b>Приз:</b> ${amount:.2f}\n\n"
                        f"Средства начислены на ваш баланс!",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления победителю: {e}")
            
            elif prize["prize_type"] == "gift":
                # Ищем подарок
                gift = await db.get_available_relay_gift(gift_name=prize["prize_value"])
                if gift:
                    # Отправляем подарок
                    from relay_account import get_relay_client
                    relay_client = get_relay_client()
                    if relay_client:
                        try:
                            await db.mark_gift_as_transferred(gift["message_id"], ticket["user_id"])
                            logger.info(f"🎁 Подарок {prize['prize_value']} отправлен пользователю {ticket['user_id']}")
                        except Exception as e:
                            logger.error(f"Ошибка при отправке подарка: {e}")
                    
                    # Отправляем уведомление
                    try:
                        await bot.send_message(
                            ticket["user_id"],
                            f"🎉 <b>Поздравляем! Вы выиграли в лотерее!</b>\n\n"
                            f"🎫 <b>Лотерея:</b> {lottery['title']}\n"
                            f"🎫 <b>Билет:</b> #{ticket['ticket_number']}\n"
                            f"🏆 <b>Место:</b> {prize['position']}\n"
                            f"🎁 <b>Приз:</b> {prize['prize_description']}\n\n"
                            f"Подарок отправлен!",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления победителю: {e}")
                else:
                    logger.warning(f"🎁 Подарок {prize['prize_value']} не найден для пользователя {ticket['user_id']}")
        
        # Завершаем лотерею
        await db.finish_lottery(lottery_id)
        
        logger.info(f"✅ Лотерея #{lottery_id} завершена автоматически. Победителей: {len(winners)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при автоматическом завершении лотереи #{lottery_id}: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

