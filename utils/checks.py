import random
import string
from html import escape
from typing import List, Optional, Dict

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

BOT_USERNAME = "arbuzcas_bot"


def build_check_link(check_code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=check_{check_code}"


def decode_slot_symbols(value: int) -> List[str]:
    """Декодировать значение слота Telegram в символы."""
    if value == 64:
        return ["7", "7", "7"]
    mapping = [1, 2, 3, 0]
    v = value - 1
    left_idx = mapping[v & 3]
    center_idx = mapping[(v >> 2) & 3]
    right_idx = mapping[(v >> 4) & 3]
    base_symbols = ["7", "Bar", "🍇", "🍋"]
    return [
        base_symbols[left_idx],
        base_symbols[center_idx],
        base_symbols[right_idx],
    ]


def format_user_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return f"<b>{escape(text)}</b>"


def build_check_keyboard(check_code: str, button_text: Optional[str], button_url: Optional[str]) -> InlineKeyboardMarkup:
    link = build_check_link(check_code)
    buttons = []
    if button_text:
        buttons.append([
            InlineKeyboardButton(text=button_text, url=button_url or link)
        ])
    buttons.append([
        InlineKeyboardButton(text="🔗 Открыть чек", url=link)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_share_text(check: Dict) -> str:
    base_parts = [
        f"💰 Сумма: ${check['amount_per_activation']:.2f}",
        f"📊 Осталось активаций: {check['remaining_activations']}/{check['total_activations']}",
        f"🔗 Чек: {build_check_link(check['check_code'])}",
    ]
    body = "\n".join(base_parts)
    user_text = format_user_text(check.get("text"))
    header = "🎫 <b>Чек</b>"
    if user_text:
        return f"{header}\n\n{user_text}\n\n{body}"
    return f"{header}\n\n{body}"


def generate_check_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def build_captcha_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7", callback_data="captcha_7"),
            InlineKeyboardButton(text="Bar", callback_data="captcha_Bar"),
        ],
        [
            InlineKeyboardButton(text="🍇", callback_data="captcha_🍇"),
            InlineKeyboardButton(text="🍋", callback_data="captcha_🍋"),
        ]
    ])


def build_captcha_text(user_sequence: List[str], total_slots: int) -> str:
    filled = user_sequence + ["◻️"] * max(0, total_slots - len(user_sequence))
    display = " | ".join(filled[:total_slots])
    return (
        "🎰 <b>Капча</b>\n\n"
        f"Результат слота: {display}\n\n"
        "Выберите символы в правильном порядке, нажимая на кнопки:"
    )


async def notify_check_owner(db, bot, check_id: int, check_code: str, actor_user):
    """Уведомить создателя чека о новой активации"""
    try:
        check = await db.get_check_by_id(check_id)
        if not check:
            return
        creator_id = check.get("creator_id")
        if not creator_id or creator_id == actor_user.id:
            return
        remaining = check.get("remaining_activations", 0)
        total = check.get("total_activations", 0)
        actor_name = actor_user.full_name or actor_user.username or "Пользователь"
        mention = f"<a href='tg://user?id={actor_user.id}'>{escape(actor_name)}</a>"
        text = f"""🎫 <b>Ваш чек <code>{check_code}</code> активирован</b>

👤 Пользователь: {mention}
🔂 Осталось активаций: {remaining}/{total}"""
        await bot.send_message(creator_id, text, parse_mode="HTML")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Не удалось отправить уведомление создателю чека: {e}")

