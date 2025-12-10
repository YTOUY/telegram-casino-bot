from html import escape
from urllib.parse import quote_plus
import logging
from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

if TYPE_CHECKING:
    from aiogram import Bot

from config import REFERRAL_LEVELS

BOT_LINK = "https://t.me/arbuzcas_bot"
logger = logging.getLogger(__name__)


def get_referral_percent(total_volume: float) -> tuple[int, float]:
    """Получить реферальный уровень и процент на основе объема
    
    Returns:
        tuple: (level, percent) - уровень и процент реферального вознаграждения
    """
    level = 1
    percent = 0.5
    
    for idx, lvl in enumerate(REFERRAL_LEVELS, start=1):
        if total_volume >= lvl["volume"]:
            level = idx
            percent = lvl["percent"]
    
    return level, percent


def get_next_level_info(current_level: int, current_volume: float) -> dict:
    """Получить информацию о следующем уровне"""
    if current_level >= len(REFERRAL_LEVELS):
        return None
    
    next_level_config = REFERRAL_LEVELS[current_level]  # Следующий уровень (индекс уже на уровень выше)
    volume_needed = next_level_config["volume"] - current_volume
    return {
        "level": current_level + 1,
        "percent": next_level_config["percent"],
        "volume_needed": max(0, volume_needed),
        "volume_total": next_level_config["volume"]
    }


async def build_referral_view(user: dict, include_back: bool = False, back_callback: str = None, db=None):
    referral_code = user["referral_code"]
    total_volume = user["total_volume"]
    total_earned = user["total_earned"]
    referral_count = user.get("referral_count", 0)
    referral_balance = user.get("referral_balance", 0.0)
    user_id = user["user_id"]

    # Проверяем, является ли пользователь партнером
    partner_info = None
    if db:
        partner_info = await db.get_partner(user_id)
    
    # Определяем процент и текст
    if partner_info:
        # Партнер
        percent = partner_info.get("referral_percent", 0.0)
        prefix = partner_info.get("prefix", "")
        percent_text = f"💲 Вы получаете {percent}% с проигрышей рефералов"
        if prefix:
            percent_text += f"\n🏷 Префикс: [{prefix}]"
    else:
        # Обычный пользователь - всегда 5%
        percent = 5.0
        percent_text = f"💲 Вы получаете {percent}% с проигрышей рефералов"

    ref_link = f"{BOT_LINK}?start={referral_code}"

    text = f"""🎁🫂 <b>Рефералы</b>

{percent_text}

<b>Ваша статистика:</b>
🫂 Рефералы: {referral_count}
📦 Общий объём: ${total_volume:.2f}
📊 Всего получено: ${total_earned:.2f}
💰 Реферальный баланс: ${referral_balance:.2f}"""

    text += f"""

<b>Ваша реферальная ссылка:</b>
🔗 {escape(ref_link)}"""

    share_text = quote_plus("🎰 ArbuzGame — играй и зарабатывай!")
    share_url = f"https://t.me/share/url?url={quote_plus(ref_link)}&text={share_text}"

    keyboard_rows = [
        [InlineKeyboardButton(text="📤 Поделиться", url=share_url)],
    ]
    
    # Добавляем кнопку "Вывести" всегда (даже если баланс 0, чтобы пользователь видел опцию)
    keyboard_rows.append([InlineKeyboardButton(text="💵 Вывести", callback_data="withdraw_referral_balance")])
    
    if include_back and back_callback:
        keyboard_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return text, keyboard, ref_link


async def send_referral_earnings_notification(bot: "Bot", referrer_id: int, bonus: float, bet_amount: float):
    """Отправить уведомление рефералу о заработке с реферала
    
    Args:
        bot: Экземпляр бота
        referrer_id: ID реферала
        bonus: Сумма начисленного бонуса
        bet_amount: Сумма ставки реферала
    """
    try:
        text = f"""💰 <b>Заработок с реферала!</b>

🎮 Ваш реферал сделал ставку: ${bet_amount:.2f}

💵 Вы получили: ${bonus:.2f}

Продолжайте привлекать рефералов и зарабатывайте больше!"""
        
        await bot.send_message(referrer_id, text, parse_mode="HTML")
        logger.info(f"✅ Уведомление о заработке отправлено пользователю {referrer_id}: ${bonus:.2f}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о заработке пользователю {referrer_id}: {e}")


async def send_level_up_notification(bot: "Bot", referrer_id: int, old_level: int, new_level: int, old_percent: float, new_percent: float):
    """Отправить уведомление рефералу о повышении уровня
    
    Args:
        bot: Экземпляр бота
        referrer_id: ID реферала
        old_level: Старый уровень
        new_level: Новый уровень
        old_percent: Старый процент
        new_percent: Новый процент
    """
    try:
        text = f"""🎉 <b>Поздравляем! Повышение уровня!</b>

🏢 Уровень {old_level} → Уровень {new_level}

📊 Процент: {old_percent}% → {new_percent}%

💎 Теперь вы получаете {new_percent}% от объема игр ваших рефералов!

Продолжайте привлекать рефералов для еще большего заработка!"""
        
        await bot.send_message(referrer_id, text, parse_mode="HTML")
        logger.info(f"✅ Уведомление о повышении уровня отправлено пользователю {referrer_id}: {old_level} -> {new_level}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о повышении уровня пользователю {referrer_id}: {e}")
