import time
import uuid
from typing import Optional, Dict

from aiogram import Router, Bot
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ChosenInlineResult,
)

from database import Database
from utils.checks import (
    build_check_keyboard,
    build_share_text,
    generate_check_code,
    format_user_text,
)

router = Router()
db = Database()

INLINE_CACHE: Dict[str, Dict] = {}


def parse_inline_query_text(text: str) -> Optional[Dict]:
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3:
        return None
    amount_raw, activations_raw, remainder = parts[0], parts[1], parts[2].strip()
    try:
        amount = float(amount_raw.replace(",", "."))
        activations = int(activations_raw)
    except ValueError:
        return None
    if amount < 0.1 or activations < 1 or not remainder:
        return None
    return {
        "amount": amount,
        "activations": activations,
        "text": remainder,
    }


def cleanup_cache():
    now = time.time()
    expired_keys = [key for key, value in INLINE_CACHE.items() if now - value.get("created_at", now) > 180]
    for key in expired_keys:
        INLINE_CACHE.pop(key, None)


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    cleanup_cache()
    user = await db.get_user(inline_query.from_user.id)
    if not user:
        result = InlineQueryResultArticle(
            id="start_required",
            title="Запустите @arbuzcas_bot",
            description="Нажмите, чтобы открыть бота",
            input_message_content=InputTextMessageContent(
                message_text="Чтобы создавать чеки, сначала запустите @arbuzcas_bot и нажмите /start.",
                parse_mode="HTML",
            ),
            url="https://t.me/arbuzcas_bot",
        )
        await inline_query.answer([result], cache_time=5, is_personal=True)
        return
    
    parsed = parse_inline_query_text(inline_query.query)
    if not parsed:
        hint = InlineQueryResultArticle(
            id="usage_hint",
            title="Формат: сумма количество текст",
            description="Например: 5 10 Подарок другу",
            input_message_content=InputTextMessageContent(
                message_text="Введите запрос в формате <code>5 10 Подарок другу</code>\n"
                             "где первое число — сумма активации, второе — количество.",
                parse_mode="HTML",
            ),
        )
        await inline_query.answer([hint], cache_time=1, is_personal=True)
        return
    
    total_cost = parsed["amount"] * parsed["activations"]
    if user["balance"] < total_cost:
        insufficient = InlineQueryResultArticle(
            id="not_enough_funds",
            title="Недостаточно средств",
            description=f"Нужно ${total_cost:.2f}, у вас ${user['balance']:.2f}",
            input_message_content=InputTextMessageContent(
                message_text=f"❌ Недостаточно средств для создания чека на ${parsed['amount']:.2f} "
                             f"× {parsed['activations']} активаций (нужно ${total_cost:.2f}).",
                parse_mode="HTML",
            ),
        )
        await inline_query.answer([insufficient], cache_time=1, is_personal=True)
        return
    
    cache_id = str(uuid.uuid4())
    INLINE_CACHE[cache_id] = {
        "user_id": inline_query.from_user.id,
        "amount": parsed["amount"],
        "activations": parsed["activations"],
        "text": parsed["text"],
        "created_at": time.time(),
    }
    
    # Формируем превью сообщения (будет заменено после создания чека)
    preview_text = (
        f"🎫 <b>Чек</b>\n\n"
        f"{format_user_text(parsed['text'])}\n\n"
        f"💰 Сумма: ${parsed['amount']:.2f}\n"
        f"📊 Активаций: {parsed['activations']}\n"
        f"⏳ Создаётся..."
    )
    result = InlineQueryResultArticle(
        id=cache_id,
        title=f"Чек ${parsed['amount']:.2f} × {parsed['activations']}",
        description=f"Стоимость ${total_cost:.2f}. {parsed['text'][:30]}...",
        input_message_content=InputTextMessageContent(
            message_text=preview_text,
            parse_mode="HTML",
        ),
    )
    await inline_query.answer([result], cache_time=1, is_personal=True)


@router.chosen_inline_result()
async def handle_chosen_inline_result(chosen_result: ChosenInlineResult, bot: Bot):
    data = INLINE_CACHE.pop(chosen_result.result_id, None)
    if not data:
        parsed = parse_inline_query_text(chosen_result.query or "")
        if not parsed:
            await bot.edit_message_text(
                inline_message_id=chosen_result.inline_message_id,
                text="❌ Не удалось создать чек. Попробуйте снова.",
                parse_mode="HTML",
            )
            return
        data = parsed
        data["user_id"] = chosen_result.from_user.id
    elif data["user_id"] != chosen_result.from_user.id:
        await bot.edit_message_text(
            inline_message_id=chosen_result.inline_message_id,
            text="❌ Запрос устарел. Попробуйте снова.",
            parse_mode="HTML",
        )
        return
    
    user = await db.get_user(chosen_result.from_user.id)
    if not user:
        await bot.edit_message_text(
            inline_message_id=chosen_result.inline_message_id,
            text="❌ Сначала запустите бота через /start.",
            parse_mode="HTML",
        )
        return
    
    amount = data["amount"]
    activations = data["activations"]
    text = data["text"]
    total_cost = amount * activations
    
    if user["balance"] < total_cost:
        await bot.edit_message_text(
            inline_message_id=chosen_result.inline_message_id,
            text=f"❌ Недостаточно средств (нужно ${total_cost:.2f}, у вас ${user['balance']:.2f}).",
            parse_mode="HTML",
        )
        return
    
    user_id = chosen_result.from_user.id
    await db.update_balance(user_id, -total_cost)
    check_code = generate_check_code()
    await db.create_check(
        creator_id=user_id,
        check_code=check_code,
        total_activations=activations,
        amount_per_activation=amount,
        requires_captcha=False,
        captcha_result=None,
        image_url=None,
        text=text,
        button_text=None,
        button_url=None,
    )
    check = await db.get_check(check_code)
    message_text = build_share_text(check)
    keyboard = build_check_keyboard(check_code, None, None)
    
    await bot.edit_message_text(
        inline_message_id=chosen_result.inline_message_id,
        text=message_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )

