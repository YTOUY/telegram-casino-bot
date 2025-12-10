from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import aiosqlite
import random
import string
import os
import io
import csv

from database import Database
from config import ADMIN_IDS
from keyboards import get_admin_keyboard
from crypto_pay import crypto_pay
import logging

logger = logging.getLogger(__name__)

# Импорты для графиков и экспорта
try:
    import matplotlib
    matplotlib.use('Agg')  # Используем backend без GUI
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib import font_manager
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib не установлен, графики будут недоступны")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas не установлен, экспорт в Excel будет недоступен")

router = Router()
db = Database()


class BroadcastStates(StatesGroup):
    waiting_for_content = State()
    waiting_for_photo = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_channel = State()
    waiting_for_channels = State()  # Для множественного выбора каналов


class PartnerStates(StatesGroup):
    waiting_partner_user_id = State()
    waiting_partner_prefix = State()
    waiting_partner_level_percent = State()


class UserSearchStates(StatesGroup):
    waiting_query = State()


class UserStatsStates(StatesGroup):
    waiting_stats_user_id = State()


class PromoCodeStates(StatesGroup):
    waiting_code = State()
    waiting_amount = State()
    waiting_activations = State()
    waiting_channel_choice = State()
    waiting_channel_username = State()
    waiting_deposit_type = State()
    waiting_rollover = State()
    waiting_min_deposit = State()
    waiting_publish_choice = State()
    waiting_channel_for_publish = State()
    waiting_edit_code = State()
    waiting_edit_amount = State()
    waiting_edit_activations = State()
    waiting_edit_channel = State()


class DepositStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_deposit_amount = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_type = State()


class SupportReplyStates(StatesGroup):
    waiting_reply_text = State()
    waiting_withdraw_type = State()


class LotteryStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_ticket_price = State()
    waiting_max_tickets = State()
    waiting_finish_type = State()
    waiting_finish_value = State()
    waiting_finish_datetime = State()
    waiting_finish_participants = State()
    waiting_prizes_count = State()
    waiting_prize_position = State()
    waiting_prize_type = State()
    waiting_prize_value = State()
    waiting_prize_description = State()
    waiting_broadcast = State()


class StickerStates(StatesGroup):
    waiting_stickers = State()
    waiting_names = State()


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


def is_russian(text: str) -> bool:
    """Проверка, содержит ли текст русские символы"""
    return any('\u0400' <= char <= '\u04FF' for char in text)


def generate_random_link(length: int = 8) -> str:
    """Генерация случайной ссылки из английских букв"""
    return ''.join(random.choices(string.ascii_uppercase, k=length))


async def show_admin_panel(message: Message):
    """Общая функция для показа админ панели"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    logger.info(f"🔍 Запрос админ панели от пользователя {user_id} (@{username})")
    
    if not is_admin(user_id):
        logger.warning(f"❌ Пользователь {user_id} (@{username}) не является администратором.")
        logger.warning(f"   Текущие ADMIN_IDS: {ADMIN_IDS}")
        # Не отправляем никакого сообщения, просто игнорируем
        return
    
    logger.info(f"✅ Пользователь {user_id} является администратором, показываю админ панель")
    
    try:
        text = """🔐 <b>Админ Панель</b>

Выберите действие:"""
        
        keyboard = get_admin_keyboard()
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        logger.info(f"✅ Админ панель успешно отправлена пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке админ панели: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при открытии админ панели: {str(e)}")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ панель - обработка команды /admin"""
    await show_admin_panel(message)


@router.message(F.text == "/admin")
async def cmd_admin_text(message: Message):
    """Админ панель - обработка текста /admin (на случай если команда не распознается)"""
    await show_admin_panel(message)


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Выберите тип рассылки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Рассылка пользователям", callback_data="broadcast_to_users")],
            [InlineKeyboardButton(text="📢 Публикация в канал(ы)", callback_data="broadcast_to_channel")],
            [InlineKeyboardButton(text="🌐 Общая рассылка (каналы + пользователи)", callback_data="broadcast_to_all")],
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_to_users")
async def broadcast_to_users(callback: CallbackQuery, state: FSMContext):
    """Рассылка пользователям"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(broadcast_type="users")
    
    await callback.message.answer(
        "📢 <b>Рассылка пользователям</b>\n\n"
        "Отправьте текст сообщения для рассылки.\n"
        "Если хотите отправить с фото, сначала отправьте фото, затем текст.\n"
        "Или отправьте только текст без фото.\n\n"
        "<b>📝 Поддержка HTML-форматирования:</b>\n\n"
        "• <b>Жирный текст</b>: &lt;b&gt;текст&lt;/b&gt;\n"
        "• <i>Курсив</i>: &lt;i&gt;текст&lt;/i&gt;\n"
        "• <u>Подчеркнутый</u>: &lt;u&gt;текст&lt;/u&gt;\n"
        "• <s>Зачеркнутый</s>: &lt;s&gt;текст&lt;/s&gt;\n"
        "• <code>Моноширинный</code>: &lt;code&gt;текст&lt;/code&gt;\n"
        "• <a href=\"https://example.com\">Ссылка</a>: &lt;a href=\"URL\"&gt;текст&lt;/a&gt;\n"
        "• <b><a href=\"https://example.com\">Жирная ссылка</a></b>: &lt;b&gt;&lt;a href=\"URL\"&gt;текст&lt;/a&gt;&lt;/b&gt;\n"
        "• <pre>Блок кода</pre>: &lt;pre&gt;текст&lt;/pre&gt;\n"
        "• <blockquote>Цитата</blockquote>: &lt;blockquote&gt;текст&lt;/blockquote&gt;\n\n"
        "<b>Примеры:</b>\n"
        "&lt;b&gt;Важное объявление&lt;/b&gt;\n"
        "&lt;a href=\"https://t.me/channel\"&gt;Наш канал&lt;/a&gt;\n"
        "&lt;b&gt;&lt;a href=\"https://t.me/channel\"&gt;СЛЕДИТЬ ЗА ВСЕМИ ОБНОВЛЕНИЯМИ МОЖНО ТУТ&lt;/a&gt;&lt;/b&gt;\n"
        "&lt;blockquote&gt;Цитата из новости&lt;/blockquote&gt;\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.waiting_for_content)
    await callback.answer()


@router.callback_query(F.data == "broadcast_to_channel")
async def broadcast_to_channel(callback: CallbackQuery, state: FSMContext):
    """Публикация в канал(ы)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(broadcast_type="channel", channels=[])
    
    await callback.message.answer(
        "📢 <b>Публикация в канал(ы)</b>\n\n"
        "Отправьте ссылки на каналы (можно несколько, каждую с новой строки) в формате:\n"
        "• @channel_username\n"
        "• https://t.me/channel_username\n"
        "• t.me/channel_username\n\n"
        "<b>Пример:</b>\n"
        "@arbuzikgame\n"
        "@cryptogifts_ru\n\n"
        "<b>⚠️ Важно:</b> Бот должен быть администратором каналов!\n\n"
        "После ввода всех каналов отправьте /done\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.waiting_for_channels)
    await callback.answer()


@router.callback_query(F.data == "broadcast_to_all")
async def broadcast_to_all(callback: CallbackQuery, state: FSMContext):
    """Общая рассылка (каналы + пользователи)"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(broadcast_type="all", channels=[])
    
    await callback.message.answer(
        "🌐 <b>Общая рассылка</b>\n\n"
        "Сначала укажите каналы (можно несколько, каждую с новой строки) в формате:\n"
        "• @channel_username\n"
        "• https://t.me/channel_username\n"
        "• t.me/channel_username\n\n"
        "<b>Пример:</b>\n"
        "@arbuzikgame\n"
        "@cryptogifts_ru\n\n"
        "<b>⚠️ Важно:</b> Бот должен быть администратором каналов!\n\n"
        "После ввода всех каналов отправьте /done\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.waiting_for_channels)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_content, F.photo)
async def handle_broadcast_photo(message: Message, state: FSMContext):
    """Обработка фото для рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""
    
    # Если нет подписи, просим ввести текст
    if not caption:
        await state.update_data(
            photo_id=photo_id,
            has_photo=True
        )
        await state.set_state(BroadcastStates.waiting_for_content)
        await message.answer(
            "📷 Фото получено!\n"
            "Теперь отправьте текст подписи к фото (или отправьте /skip чтобы без текста):"
        )
        return
    
    await state.update_data(
        photo_id=photo_id,
        text=caption,
        has_photo=True
    )
    
    await message.answer(
        f"📷 Фото получено!\n"
        f"Текст подписи: {caption}\n\n"
        f"Хотите добавить кнопку?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="broadcast_add_button")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="broadcast_send_now")],
        ])
    )


@router.message(BroadcastStates.waiting_for_content, F.text)
async def handle_broadcast_text(message: Message, state: FSMContext):
    """Обработка текста для рассылки"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    # Проверяем, есть ли уже фото в состоянии
    data = await state.get_data()
    has_photo = data.get("has_photo", False)
    photo_id = data.get("photo_id")
    
    # Если есть фото, это текст подписи
    if has_photo and photo_id:
        if message.text == "/skip":
            await state.update_data(text="")
        else:
            await state.update_data(text=message.text)
        
        data = await state.get_data()
        text = data.get("text", "")
        
        await message.answer(
            f"✅ Все готово!\n"
            f"Фото: ✓\n"
            f"Текст: {text if text else '(нет)'}\n\n"
            f"Хотите добавить кнопку?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да", callback_data="broadcast_add_button")],
                [InlineKeyboardButton(text="❌ Нет", callback_data="broadcast_send_now")],
            ])
        )
        return
    
    # Если нет фото, это обычный текст
    await state.update_data(
        text=message.text,
        has_photo=False
    )
    
    await message.answer(
        f"📝 Текст получен!\n\n"
        f"Хотите добавить кнопку?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="broadcast_add_button")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="broadcast_send_now")],
        ])
    )


@router.callback_query(F.data == "broadcast_add_button")
async def add_broadcast_button(callback: CallbackQuery, state: FSMContext):
    """Добавить кнопку к рассылке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "🔘 Введите текст для кнопки (например: 'Перейти на сайт'):"
    )
    await state.set_state(BroadcastStates.waiting_for_button_text)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_button_text)
async def handle_button_text(message: Message, state: FSMContext):
    """Обработка текста кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    await state.update_data(button_text=message.text)
    await message.answer("🔗 Теперь введите URL для кнопки (например: https://example.com):")
    await state.set_state(BroadcastStates.waiting_for_button_url)


@router.message(BroadcastStates.waiting_for_button_url)
async def handle_button_url(message: Message, state: FSMContext):
    """Обработка URL кнопки"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    await state.update_data(button_url=message.text)
    data = await state.get_data()
    
    text = "✅ Кнопка добавлена!\n\n"
    text += f"Текст кнопки: {data.get('button_text')}\n"
    text += f"URL: {data.get('button_url')}\n\n"
    text += "Отправить рассылку?"
    
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_send_now")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")],
        ])
    )


@router.message(BroadcastStates.waiting_for_channel)
async def handle_channel_link(message: Message, state: FSMContext):
    """Обработка ссылки на канал (старый формат - один канал)"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    # Парсим ссылку на канал
    channel_link = message.text.strip()
    channel_username = None
    
    # Извлекаем username из разных форматов ссылок
    if channel_link.startswith("https://t.me/"):
        channel_username = channel_link.replace("https://t.me/", "").lstrip("@")
    elif channel_link.startswith("t.me/"):
        channel_username = channel_link.replace("t.me/", "").lstrip("@")
    elif channel_link.startswith("@"):
        channel_username = channel_link.lstrip("@")
    else:
        channel_username = channel_link
    
    if not channel_username:
        await message.answer("❌ Неверный формат ссылки. Попробуйте снова:")
        return
    
    await state.update_data(channel_username=channel_username)
    
    await message.answer(
        f"✅ Канал получен: @{channel_username}\n\n"
        f"📢 <b>Публикация в канал</b>\n\n"
        "Отправьте текст сообщения для публикации.\n"
        "Если хотите отправить с фото, сначала отправьте фото, затем текст.\n"
        "Или отправьте только текст без фото.\n\n"
        "<b>📝 Поддержка HTML-форматирования:</b>\n\n"
        "• <b>Жирный текст</b>: &lt;b&gt;текст&lt;/b&gt;\n"
        "• <i>Курсив</i>: &lt;i&gt;текст&lt;/i&gt;\n"
        "• <u>Подчеркнутый</u>: &lt;u&gt;текст&lt;/u&gt;\n"
        "• <s>Зачеркнутый</s>: &lt;s&gt;текст&lt;/s&gt;\n"
        "• <code>Моноширинный</code>: &lt;code&gt;текст&lt;/code&gt;\n"
        "• <a href=\"https://example.com\">Ссылка</a>: &lt;a href=\"URL\"&gt;текст&lt;/a&gt;\n"
        "• <b><a href=\"https://example.com\">Жирная ссылка</a></b>: &lt;b&gt;&lt;a href=\"URL\"&gt;текст&lt;/a&gt;&lt;/b&gt;\n"
        "• <pre>Блок кода</pre>: &lt;pre&gt;текст&lt;/pre&gt;\n"
        "• <blockquote>Цитата</blockquote>: &lt;blockquote&gt;текст&lt;/blockquote&gt;\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastStates.waiting_for_content)


@router.message(BroadcastStates.waiting_for_channels)
async def handle_channels_links(message: Message, state: FSMContext):
    """Обработка ссылок на каналы (множественный выбор)"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    if message.text == "/done":
        # Завершаем ввод каналов
        data = await state.get_data()
        channels = data.get("channels", [])
        
        if not channels:
            await message.answer("❌ Вы не добавили ни одного канала. Попробуйте снова:")
            return
        
        broadcast_type = data.get("broadcast_type", "channel")
        
        channels_text = "\n".join([f"• @{ch}" for ch in channels])
        type_text = "Публикация в каналы" if broadcast_type == "channel" else "Общая рассылка"
        
        await message.answer(
            f"✅ Каналы получены ({len(channels)}):\n{channels_text}\n\n"
            f"📢 <b>{type_text}</b>\n\n"
            "Отправьте текст сообщения для публикации.\n"
            "Если хотите отправить с фото, сначала отправьте фото, затем текст.\n"
            "Или отправьте только текст без фото.\n\n"
            "<b>📝 Поддержка HTML-форматирования:</b>\n\n"
            "• <b>Жирный текст</b>: &lt;b&gt;текст&lt;/b&gt;\n"
            "• <i>Курсив</i>: &lt;i&gt;текст&lt;/i&gt;\n"
            "• <u>Подчеркнутый</u>: &lt;u&gt;текст&lt;/u&gt;\n"
            "• <s>Зачеркнутый</s>: &lt;s&gt;текст&lt;/s&gt;\n"
            "• <code>Моноширинный</code>: &lt;code&gt;текст&lt;/code&gt;\n"
            "• <a href=\"https://example.com\">Ссылка</a>: &lt;a href=\"URL\"&gt;текст&lt;/a&gt;\n"
            "• <b><a href=\"https://example.com\">Жирная ссылка</a></b>: &lt;b&gt;&lt;a href=\"URL\"&gt;текст&lt;/a&gt;&lt;/b&gt;\n"
            "• <pre>Блок кода</pre>: &lt;pre&gt;текст&lt;/pre&gt;\n"
            "• <blockquote>Цитата</blockquote>: &lt;blockquote&gt;текст&lt;/blockquote&gt;\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        
        await state.set_state(BroadcastStates.waiting_for_content)
        return
    
    # Парсим каналы (может быть несколько, каждое с новой строки)
    lines = message.text.strip().split('\n')
    data = await state.get_data()
    channels = data.get("channels", [])
    
    for line in lines:
        channel_link = line.strip()
        if not channel_link:
            continue
        
        channel_username = None
        
        # Извлекаем username из разных форматов ссылок
        if channel_link.startswith("https://t.me/"):
            channel_username = channel_link.replace("https://t.me/", "").lstrip("@")
        elif channel_link.startswith("t.me/"):
            channel_username = channel_link.replace("t.me/", "").lstrip("@")
        elif channel_link.startswith("@"):
            channel_username = channel_link.lstrip("@")
        else:
            channel_username = channel_link
        
        if channel_username and channel_username not in channels:
            channels.append(channel_username)
    
    await state.update_data(channels=channels)
    
    channels_text = "\n".join([f"• @{ch}" for ch in channels])
    await message.answer(
        f"✅ Добавлено каналов: {len(channels)}\n\n"
        f"Список каналов:\n{channels_text}\n\n"
        f"Продолжайте добавлять каналы или отправьте /done для продолжения"
    )


@router.callback_query(F.data == "broadcast_send_now")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отправить рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    data = await state.get_data()
    broadcast_type = data.get("broadcast_type", "users")
    text = data.get("text", "")
    has_photo = data.get("has_photo", False)
    photo_id = data.get("photo_id")
    button_text = data.get("button_text")
    button_url = data.get("button_url")
    channel_username = data.get("channel_username")  # Старый формат (один канал)
    channels = data.get("channels", [])  # Новый формат (несколько каналов)
    
    # Создаем клавиатуру если есть кнопка
    reply_markup = None
    if button_text and button_url:
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, url=button_url)]
        ])
    
    # Получаем бота из callback
    bot = callback.bot
    
    # Если публикация в канал(ы) или общая рассылка
    if broadcast_type in ["channel", "all"]:
        # Поддерживаем старый формат (один канал) и новый (несколько каналов)
        if channel_username:
            channels = [channel_username]
        elif not channels:
            await callback.answer("❌ Каналы не указаны", show_alert=True)
            return
        
        try:
            await callback.message.answer(f"📤 Публикую в {len(channels)} канал(ов)...")
            
            channels_success = []
            channels_failed = []
            
            for channel in channels:
                try:
                    if has_photo:
                        await bot.send_photo(
                            chat_id=f"@{channel}",
                            photo=photo_id,
                            caption=text,
                            reply_markup=reply_markup,
                            parse_mode="HTML"
                        )
                    else:
                        await bot.send_message(
                            chat_id=f"@{channel}",
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode="HTML"
                        )
                    channels_success.append(channel)
                except Exception as e:
                    error_msg = str(e)
                    channels_failed.append((channel, error_msg))
                    logger.error(f"Ошибка при публикации в канал @{channel}: {error_msg}")
            
            # Формируем результат
            result_text = f"✅ <b>Публикация завершена!</b>\n\n"
            if channels_success:
                result_text += f"📢 Успешно опубликовано в {len(channels_success)} канал(ов):\n"
                for ch in channels_success:
                    result_text += f"• @{ch}\n"
            
            if channels_failed:
                result_text += f"\n❌ Ошибки ({len(channels_failed)}):\n"
                for ch, err in channels_failed:
                    result_text += f"• @{ch}: {err[:50]}...\n"
            
            await callback.message.answer(result_text, parse_mode="HTML")
        except Exception as e:
            error_msg = str(e)
            await callback.message.answer(
                f"❌ <b>Ошибка публикации!</b>\n\n"
                f"Ошибка: {error_msg}",
                parse_mode="HTML"
            )
        
        # Если это только публикация в каналы (не общая рассылка), завершаем
        if broadcast_type == "channel":
            await state.clear()
            await callback.answer()
            return
    
    # Если общая рассылка, продолжаем рассылку пользователям
    # Если рассылка только пользователям или общая рассылка
    if broadcast_type in ["users", "all"]:
        # Рассылка пользователям
        try:
            users = await db.get_all_users()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении списка пользователей: {e}", exc_info=True)
            await callback.message.answer(
                f"❌ <b>Ошибка!</b>\n\n"
                f"Не удалось получить список пользователей: {str(e)}",
                parse_mode="HTML"
            )
            await state.clear()
            await callback.answer()
            return
        
        total = len(users)
        sent = 0
        failed = 0
        blocked = 0
        
        if total == 0:
            await callback.message.answer("❌ В базе данных нет пользователей для рассылки")
            await state.clear()
            await callback.answer()
            return
        
        await callback.message.answer(f"📤 Начинаю рассылку для {total} пользователей...")
        logger.info(f"📢 Начинаю рассылку для {total} пользователей")
        
        for user in users:
            user_id = user["user_id"]
            try:
                # Проверяем, что reply_markup не является ReplyKeyboardMarkup или ReplyKeyboardRemove (не поддерживается в рассылке)
                from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
                final_reply_markup = reply_markup
                if isinstance(reply_markup, (ReplyKeyboardMarkup, ReplyKeyboardRemove)):
                    # В рассылке не используем ReplyKeyboardMarkup или ReplyKeyboardRemove, только InlineKeyboardMarkup или None
                    final_reply_markup = None
                
                if has_photo:
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=photo_id,
                        caption=text,
                        reply_markup=final_reply_markup,
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=final_reply_markup,
                        parse_mode="HTML"
                    )
                sent += 1
                if sent % 10 == 0:  # Логируем каждые 10 сообщений
                    logger.info(f"📤 Отправлено: {sent}/{total}")
                await asyncio.sleep(0.05)  # Небольшая задержка чтобы не попасть в лимит
            except Exception as e:
                failed += 1
                error_msg = str(e)
                error_lower = error_msg.lower()
                # Игнорируем стандартные ошибки (бот заблокирован, чат не найден и т.д.)
                if any(phrase in error_lower for phrase in [
                    "bot was blocked", 
                    "chat not found", 
                    "user is deactivated",
                    "peer_id_invalid",
                    "forbidden",
                    "blocked"
                ]):
                    blocked += 1
                    # Это нормальные ошибки, не логируем
                    pass
                elif any(phrase in error_lower for phrase in [
                    "bad request: message is too long",
                    "bad request: can't parse entities"
                ]):
                    # Ошибки форматирования - логируем
                    logger.warning(f"⚠️ Ошибка форматирования при отправке пользователю {user_id}: {error_msg}")
                else:
                    # Логируем нестандартные ошибки с полным текстом
                    logger.warning(f"⚠️ Ошибка отправки пользователю {user_id}: {error_msg}")
        
        result_text = f"✅ <b>Рассылка завершена!</b>\n\n"
        result_text += f"📊 Всего пользователей: {total}\n"
        result_text += f"✅ Отправлено: {sent}\n"
        result_text += f"❌ Ошибок: {failed}"
        if blocked > 0:
            result_text += f"\n🚫 Заблокировано: {blocked}"
        
        await callback.message.answer(result_text, parse_mode="HTML")
        logger.info(f"✅ Рассылка завершена: отправлено {sent}, ошибок {failed}, заблокировано {blocked}")
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отменить рассылку"""
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена")
    await callback.answer()


@router.callback_query(F.data == "admin_deposit")
async def admin_deposit_menu(callback: CallbackQuery, state: FSMContext):
    """Меню пополнения баланса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "💰 <b>Пополнение баланса</b>\n\n"
        "Введите ID пользователя или username (без @):",
        parse_mode="HTML"
    )
    await state.set_state(DepositStates.waiting_user_id)
    await callback.answer()


async def prompt_deposit_amount(message: Message, state: FSMContext, user: dict):
    user_id = user["user_id"]
    balance = user["balance"]
    username = user.get("username", "Неизвестно")

    await state.update_data(target_user_id=user_id)
    await message.answer(
        f"👤 <b>Пользователь найден:</b>\n\n"
        f"ID: {user_id}\n"
        f"Username: @{username}\n"
        f"Текущий баланс: ${balance:.2f}\n\n"
        f"Введите сумму для пополнения (например: 10.50):",
        parse_mode="HTML"
    )
    await state.set_state(DepositStates.waiting_deposit_amount)


def build_user_search_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Пополнить", callback_data=f"admin_deposit_user_{user_id}")],
        [InlineKeyboardButton(text="➖ Снять баланс", callback_data=f"admin_withdraw_user_{user_id}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_stats_user_{user_id}")],
        [InlineKeyboardButton(text="💬 Открыть чат", url=f"tg://user?id={user_id}")]
    ])


@router.callback_query(F.data == "admin_user_search")
async def admin_user_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Введите username (без @) или ID пользователя.\n"
        "Для отмены отправьте /cancel.",
        parse_mode="HTML"
    )
    await state.set_state(UserSearchStates.waiting_query)
    await callback.answer()


# ВАЖНО: Специфичные обработчики с состояниями должны быть ПЕРЕД общим обработчиком
@router.message(UserSearchStates.waiting_query, F.text)
async def handle_user_search(message: Message, state: FSMContext):
    """Обработка поиска пользователя - только в состоянии waiting_query"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"🔍 Обработка поиска пользователя для админа {message.from_user.id}")
    
    query = message.text.strip()
    if query.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Поиск отменён")
        return
    
    query = query.lstrip("@")
    results = []
    if query.isdigit():
        user = await db.get_user(int(query))
        if user:
            results = [user]
    else:
        results = await db.search_users(query, limit=5)
    
    if not results:
        await message.answer("❌ Пользователи не найдены")
        await state.clear()
        return
    
    for user in results:
        balance = user.get('balance', 0.0)
        locked_balance = user.get('locked_balance', 0.0)
        text = (
            f"👤 <b>{user.get('username') or 'Без ника'}</b>\n"
            f"ID: {user['user_id']}\n"
            f"💰 Обычный баланс: ${balance:.2f}\n"
            f"🔒 Заблокированный баланс: ${locked_balance:.2f}\n"
            f"📅 Регистрация: {user.get('created_at', '—')}"
        )
        await message.answer(
            text,
            reply_markup=build_user_search_keyboard(user["user_id"]),
            parse_mode="HTML"
        )
    
    await state.clear()


# ==================== ПРОМОКОДЫ (ПЕРЕД ПАРТНЕРАМИ ДЛЯ ПРИОРИТЕТА) ====================
# Обработчики промокодов должны быть ПЕРЕД общими обработчиками

@router.message(PromoCodeStates.waiting_code)
async def handle_promo_code(message: Message, state: FSMContext):
    """Обработка кода промокода"""
    if not is_admin(message.from_user.id):
        return
    
    # Проверяем, что это текстовое сообщение
    if not message.text:
        await message.answer("❌ Пожалуйста, введите код промокода текстом")
        return
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    # Игнорируем другие команды
    if message.text.startswith("/"):
        return
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎟️ Обработка кода промокода от админа {message.from_user.id}: {message.text}")
    
    code = message.text.strip().upper()
    
    if not code:
        await message.answer("❌ Код промокода не может быть пустым. Введите код:")
        return
    
    # Проверяем, не существует ли уже такой промокод
    existing = await db.get_promo_code(code)
    if existing:
        await message.answer("❌ Промокод с таким кодом уже существует. Введите другой:")
        return
    
    # Если промокод на русском, генерируем случайную ссылку
    activation_link = None
    if is_russian(code):
        activation_link = generate_random_link()
        # Сохраняем и code, и activation_link
        await state.update_data(code=code, activation_link=activation_link)
        await message.answer(
            f"✅ Код промокода: <code>{code}</code>\n"
            f"🔗 Ссылка для активации: <code>{activation_link}</code>\n\n"
            f"Введите сумму начисления (например: 10 или 10.5):\n\n"
            f"Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await state.set_state(PromoCodeStates.waiting_amount)
        return
    
    # Сохраняем код промокода
    await state.update_data(code=code)
    await message.answer(
        f"✅ Код промокода: <code>{code}</code>\n\n"
        "Введите сумму начисления (например: 10 или 10.5):\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_amount)


@router.message(PromoCodeStates.waiting_amount)
async def handle_promo_amount(message: Message, state: FSMContext):
    """Обработка суммы промокода"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите сумму текстом")
        return
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    try:
        amount = float(message.text.strip().replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0. Введите сумму:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число (например: 10 или 10.5):")
        return
    
    await state.update_data(amount=amount)
    await message.answer(
        f"✅ Сумма: ${amount:.2f}\n\n"
        "Введите количество активаций (например: 100):\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_activations)


@router.message(PromoCodeStates.waiting_activations)
async def handle_promo_activations(message: Message, state: FSMContext):
    """Обработка количества активаций"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите количество активаций текстом")
        return
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    try:
        activations = int(message.text.strip())
        if activations <= 0:
            await message.answer("❌ Количество должно быть больше 0. Введите количество:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число (например: 100):")
        return
    
    await state.update_data(activations=activations)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, требуется", callback_data="promo_channel_yes")],
        [InlineKeyboardButton(text="❌ Нет, не требуется", callback_data="promo_channel_no")],
    ])
    
    await message.answer(
        f"✅ Количество активаций: {activations}\n\n"
        "Требуется ли подписка на канал для активации?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "promo_channel_yes")
async def promo_channel_yes(callback: CallbackQuery, state: FSMContext):
    """Требуется подписка на канал"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(requires_channel=True)
    await callback.message.answer(
        "Введите username канала (без @, например: mychannel):\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_channel_username)
    await callback.answer()


@router.callback_query(F.data == "promo_channel_no")
async def promo_channel_no(callback: CallbackQuery, state: FSMContext):
    """Не требуется подписка на канал"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(requires_channel=False, channel_username=None)
    
    # Спрашиваем тип депозита
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Бездепный", callback_data="promo_deposit_no"),
            InlineKeyboardButton(text="💰 Депный", callback_data="promo_deposit_yes"),
        ]
    ])
    
    await callback.message.answer(
        "Выберите тип промокода:\n\n"
        "• <b>Бездепный</b> - не требуется депозит для активации\n"
        "• <b>Депный</b> - требуется минимальный депозит для активации",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(PromoCodeStates.waiting_deposit_type)
    await callback.answer()


@router.callback_query(F.data == "promo_deposit_no")
async def promo_deposit_no(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора бездепного промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Проверяем, что все данные сохранены
    data = await state.get_data()
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 Данные в состоянии при выборе бездепного: {data}")
    
    await state.update_data(deposit_type="no_deposit", min_deposit=0.0)
    
    await callback.message.answer(
        "Введите множитель отыгрыша (например: 2 для x2, 3 для x3, или 1 если отыгрыш не нужен):\n\n"
        "Отыгрыш означает, что пользователь получит указанную сумму, но сможет вывести её только после того, "
        "как сделает ставок на сумму равную полученной сумме × множитель отыгрыша.\n\n"
        "Например: если пользователь получил $10 с отыгрышем x3, то он должен сделать ставок на $30, "
        "прежде чем сможет вывести эти $10.\n\n"
        "Для отмены отправьте /cancel"
    )
    await state.set_state(PromoCodeStates.waiting_rollover)
    await callback.answer()


@router.callback_query(F.data == "promo_deposit_yes")
async def promo_deposit_yes(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора депного промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Проверяем, что все данные сохранены
    data = await state.get_data()
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 Данные в состоянии при выборе депного: {data}")
    
    await state.update_data(deposit_type="deposit")
    
    await callback.message.answer(
        "Введите минимальный депозит для активации промокода (например: 10 или 10$):\n\n"
        "Для отмены отправьте /cancel"
    )
    await state.set_state(PromoCodeStates.waiting_min_deposit)
    await callback.answer()


@router.message(PromoCodeStates.waiting_min_deposit)
async def handle_promo_min_deposit(message: Message, state: FSMContext):
    """Обработка минимального депозита для промокода"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    text = message.text.replace('$', '').replace(',', '.').replace(' ', '').strip()
    try:
        min_deposit = float(text)
        if min_deposit < 0:
            await message.answer("❌ Минимальный депозит должен быть больше или равен 0")
            return
        
        await state.update_data(min_deposit=min_deposit)
        
        # Теперь спрашиваем отыгрыш
        await message.answer(
            "Введите множитель отыгрыша (например: 2 для x2, 3 для x3, или 1 если отыгрыш не нужен):\n\n"
            "Отыгрыш означает, что пользователь получит указанную сумму, но сможет вывести её только после того, "
            "как сделает ставок на сумму равную полученной сумме × множитель отыгрыша.\n\n"
            "Например: если пользователь получил $10 с отыгрышем x3, то он должен сделать ставок на $30, "
            "прежде чем сможет вывести эти $10.\n\n"
            "Для отмены отправьте /cancel"
        )
        await state.set_state(PromoCodeStates.waiting_rollover)
    except ValueError:
        await message.answer("❌ Введите число (например: 10 или 10$)")


@router.message(PromoCodeStates.waiting_rollover)
async def handle_promo_rollover(message: Message, state: FSMContext):
    """Обработка отыгрыша для промокода"""
    if not is_admin(message.from_user.id):
        return
    
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    text = message.text.replace('x', '').replace('X', '').replace(',', '.').replace(' ', '').strip()
    try:
        rollover_multiplier = float(text)
        if rollover_multiplier < 1:
            await message.answer("❌ Множитель отыгрыша должен быть больше или равен 1")
            return
        
        await state.update_data(rollover_multiplier=rollover_multiplier)
        
        # Проверяем, что все необходимые данные есть перед завершением
        data_check = await state.get_data()
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Проверка данных перед завершением создания промокода: {data_check}")
        
        # Проверяем наличие обязательных данных
        if not data_check.get("code") or not data_check.get("amount") or not data_check.get("activations"):
            missing = []
            if not data_check.get("code"):
                missing.append("код")
            if not data_check.get("amount"):
                missing.append("сумма")
            if not data_check.get("activations"):
                missing.append("активации")
            await message.answer(
                f"❌ Ошибка: потеряны данные при создании промокода.\n\n"
                f"Отсутствуют: {', '.join(missing)}\n\n"
                f"Пожалуйста, начните создание промокода заново."
            )
            await state.clear()
            return
        
        # Завершаем создание промокода
        await finish_promo_creation(message, state)
    except ValueError:
        await message.answer("❌ Введите число (например: 2 для x2 или 1 если отыгрыш не нужен).\n\n"
                             "Множитель 1 означает, что отыгрыш не требуется, и пользователь сможет сразу вывести полученную сумму.")


@router.message(PromoCodeStates.waiting_channel_username)
async def handle_channel_username(message: Message, state: FSMContext):
    """Обработка username канала"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"📝 Обработка username канала от админа {message.from_user.id}: {message.text}")
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите username канала текстом")
        return
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Создание промокода отменено")
        return
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    channel_username = message.text.strip().lstrip('@')
    
    if not channel_username:
        await message.answer("❌ Username канала не может быть пустым. Введите username:")
        return
    
    logger.info(f"✅ Сохранение username канала: {channel_username}")
    await state.update_data(channel_username=channel_username)
    
    # Спрашиваем тип депозита после ввода канала
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Бездепный", callback_data="promo_deposit_no"),
            InlineKeyboardButton(text="💰 Депный", callback_data="promo_deposit_yes"),
        ]
    ])
    
    await message.answer(
        "Выберите тип промокода:\n\n"
        "• <b>Бездепный</b> - не требуется депозит для активации\n"
        "• <b>Депный</b> - требуется минимальный депозит для активации",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(PromoCodeStates.waiting_deposit_type)


@router.message(PromoCodeStates.waiting_channel_for_publish)
async def handle_publish_channel(message: Message, state: FSMContext):
    """Обработка канала для публикации - должен быть ПЕРЕД обработчиком партнера"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"📢 Обработка username канала для публикации от админа {message.from_user.id}: {message.text}")
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введите username канала текстом")
        return
    
    # Проверяем команду отмены
    if message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Публикация промокода отменена")
        return
    
    # Игнорируем команды
    if message.text.startswith("/"):
        return
    
    channel_username = message.text.strip().lstrip('@')
    
    if not channel_username:
        await message.answer("❌ Username канала не может быть пустым. Введите username:")
        return
    
    data = await state.get_data()
    promo_id = data.get("promo_id")
    
    if not promo_id:
        await message.answer("❌ Ошибка: промокод не найден в состоянии")
        await state.clear()
        return
    
    promo = await db.get_promo_code_by_id(promo_id)
    if not promo:
        await message.answer("❌ Промокод не найден")
        await state.clear()
        return
    
    # Используем основной экземпляр бота
    bot = message.bot
    
    promo_text = f"""🎟️ <b>НОВЫЙ ПРОМОКОД</b>

<code>{promo['code']}</code> - <code>${promo['amount']:.2f}</code> - <code>{promo['total_activations']}</code> активаций

Для активации промокода перейдите в раздел "Профиль" - "Промокоды" и введите данный промокод!"""
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    # Используем activation_link если есть, иначе code
    link_code = promo.get('activation_link') or promo['code']
    promo_link = f"https://t.me/arbuzcas_bot?start=promo_{link_code}"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Активировать промокод", url=promo_link)],
    ])
    
    try:
        await bot.send_message(
            f"@{channel_username}",
            promo_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await message.answer(f"✅ Промокод опубликован в канал @{channel_username}")
        logger.info(f"✅ Промокод {promo['code']} опубликован в канал @{channel_username}")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Ошибка при публикации промокода в канал @{channel_username}: {e}")
        await message.answer(f"❌ Ошибка при публикации: {error_msg}")
    
    await state.clear()


# ВАЖНО: Специфичные обработчики для партнеров - должны быть ПЕРЕД общими обработчиками
@router.message(PartnerStates.waiting_partner_user_id, F.text)
async def handle_partner_user_id(message: Message, state: FSMContext):
    """Обработка ввода username/ID партнера"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"✅ Обработка ввода партнера (username/ID) для админа {message.from_user.id}: {message.text}")
    
    query = message.text.strip().lstrip("@")
    
    # Проверка на отмену
    if query.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Добавление партнера отменено")
        return
    
    user = None
    
    # Пытаемся найти по ID
    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        # Ищем по username
        users = await db.search_users(query, limit=1)
        if users:
            user = users[0]
    
    if not user:
        await message.answer("❌ Пользователь не найден. Проверьте ID или username")
        return
    
    user_id = user["user_id"]
    username = user.get("username", "неизвестно")
    
    # Проверяем, не является ли уже партнером
    existing_partner = await db.get_partner(user_id)
    if existing_partner:
        await message.answer(
            f"❌ Пользователь @{username} (ID: {user_id}) уже является партнером.\n"
            f"Префикс: [{existing_partner['prefix']}]"
        )
        await state.clear()
        return
    
    # Сохраняем ID партнера и просим ввести префикс
    await state.update_data(partner_user_id=user_id)
    logger.info(f"✅ Пользователь найден: {user_id} (@{username}), запрашиваем префикс")
    await message.answer(
        f"✅ <b>Пользователь найден:</b>\n\n"
        f"ID: {user_id}\n"
        f"Username: @{username}\n\n"
        f"Введите префикс для партнера (например: ARB, PARTNER и т.д.):",
        parse_mode="HTML"
    )
    await state.set_state(PartnerStates.waiting_partner_prefix)


@router.message(PartnerStates.waiting_partner_prefix, F.text)
async def handle_partner_prefix(message: Message, state: FSMContext):
    """Обработка ввода префикса партнера"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"✅ Обработка префикса партнера: {message.text}")
    
    prefix = message.text.strip()
    
    # Проверка на отмену
    if prefix.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Добавление партнера отменено")
        return
    
    if len(prefix) > 20:
        await message.answer("❌ Префикс слишком длинный (максимум 20 символов)")
        return
    
    await state.update_data(partner_prefix=prefix)
    
    # Показываем кнопки для выбора одного процента
    text = f"✅ Префикс установлен: {prefix}\n\n"
    text += "💲 <b>Выберите процент, который партнер будет получать с проигрышей рефералов:</b>"
    
    keyboard_buttons = []
    # Создаем кнопки с процентами по 3 в ряд (начинаем с 8%)
    percents = [8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0]
    row = []
    for i, percent in enumerate(percents):
        button = InlineKeyboardButton(
            text=f"{percent}%",
            callback_data=f"partner_percent_{percent}"
        )
        row.append(button)
        # Каждые 3 кнопки создаем новый ряд
        if len(row) == 3 or i == len(percents) - 1:
            keyboard_buttons.append(row)
            row = []
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# Общий обработчик для пополнения - должен быть ПОСЛЕ специфичных обработчиков
@router.message(DepositStates.waiting_user_id, F.text)
async def handle_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя или username для пополнения"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"💰 Обработка ввода username/ID для пополнения баланса: {message.text}")
    query = message.text.strip().lstrip("@")
    
    # Проверка на отмену
    if query.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Пополнение отменено")
        return
    
    user = None
    
    # Пытаемся найти по ID
    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        # Ищем по username
        users = await db.search_users(query, limit=1)
        if users:
            user = users[0]
    
    if not user:
        await message.answer(f"❌ Пользователь не найден. Проверьте ID или username")
        await state.clear()
        return
    
    await prompt_deposit_amount(message, state, user)


@router.callback_query(F.data.startswith("admin_deposit_user_"))
async def admin_deposit_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        user_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    await prompt_deposit_amount(callback.message, state, user)
    await callback.answer("Введите сумму пополнения")


@router.callback_query(F.data.startswith("admin_withdraw_user_"))
async def admin_withdraw_user(callback: CallbackQuery, state: FSMContext):
    """Начать процесс снятия баланса у пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        user_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    balance = user.get("balance", 0.0)
    locked_balance = user.get("locked_balance", 0.0)
    username = user.get("username", "Неизвестно")
    
    # Сохраняем user_id в состоянии
    await state.update_data(target_user_id=user_id)
    
    # Показываем информацию о балансах и предлагаем выбрать тип
    text = f"""➖ <b>Снятие баланса</b>

👤 <b>Пользователь:</b>
ID: {user_id}
Username: @{username}

💰 <b>Текущие балансы:</b>
• Обычный баланс: ${balance:.2f}
• Заблокированный баланс: ${locked_balance:.2f}

Выберите, какой баланс снять:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Обычный баланс", callback_data=f"admin_withdraw_type_{user_id}_balance")],
        [InlineKeyboardButton(text="🔒 Заблокированный баланс", callback_data=f"admin_withdraw_type_{user_id}_locked")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_withdraw")]
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_withdraw_type_"))
async def admin_withdraw_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа баланса для снятия"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        # Формат: admin_withdraw_type_{user_id}_{type}
        parts = callback.data.split("_")
        user_id = int(parts[3])
        balance_type = parts[4]  # "balance" или "locked"
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные", show_alert=True)
        return
    
    user = await db.get_user(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    balance = user.get("balance", 0.0)
    locked_balance = user.get("locked_balance", 0.0)
    username = user.get("username", "Неизвестно")
    
    # Сохраняем данные в состоянии
    await state.update_data(
        target_user_id=user_id,
        withdraw_type=balance_type
    )
    
    # Определяем доступный баланс и название
    if balance_type == "balance":
        available = balance
        balance_name = "обычный баланс"
    else:
        available = locked_balance
        balance_name = "заблокированный баланс"
    
    if available <= 0:
        await callback.answer(
            f"❌ У пользователя нет {balance_name} для снятия",
            show_alert=True
        )
        return
    
    text = f"""➖ <b>Снятие {balance_name}</b>

👤 <b>Пользователь:</b>
ID: {user_id}
Username: @{username}

💰 <b>Доступно для снятия:</b> ${available:.2f}

Введите сумму для снятия (например: 10.50):
Для отмены отправьте /cancel"""
    
    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(DepositStates.waiting_withdraw_amount)
    await callback.answer()


@router.callback_query(F.data == "admin_cancel_withdraw")
async def admin_cancel_withdraw(callback: CallbackQuery, state: FSMContext):
    """Отмена снятия баланса"""
    await state.clear()
    await callback.message.answer("❌ Снятие баланса отменено")
    await callback.answer()


@router.message(DepositStates.waiting_withdraw_amount, F.text)
async def handle_withdraw_amount(message: Message, state: FSMContext):
    """Обработка суммы снятия баланса"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"➖ Обработка суммы снятия баланса: {message.text}")
    
    # Проверка на отмену
    text = message.text.strip()
    if text.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Снятие баланса отменено")
        return
    
    # Проверяем, что текст является числом
    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 10.50 или 1000)")
        return
    
    logger.info(f"✅ Сумма снятия распознана: {amount}")
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0")
        return
    
    data = await state.get_data()
    user_id = data.get("target_user_id")
    withdraw_type = data.get("withdraw_type")
    
    if not user_id or not withdraw_type:
        await message.answer("❌ Ошибка: данные не найдены в состоянии")
        await state.clear()
        return
    
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    balance = user.get("balance", 0.0)
    locked_balance = user.get("locked_balance", 0.0)
    username = user.get("username", "Неизвестно")
    
    # Проверяем доступный баланс
    if withdraw_type == "balance":
        available = balance
        balance_name = "обычный баланс"
    else:
        available = locked_balance
        balance_name = "заблокированный баланс"
    
    if amount > available:
        await message.answer(
            f"❌ <b>Недостаточно средств</b>\n\n"
            f"Доступно для снятия: ${available:.2f}\n"
            f"Запрошено: ${amount:.2f}",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Снимаем баланс
    try:
        if withdraw_type == "balance":
            await db.update_balance(user_id, -amount)
        else:
            await db.decrease_locked_balance(user_id, amount)
        
        # Получаем обновленные данные
        user = await db.get_user(user_id)
        new_balance = user.get("balance", 0.0)
        new_locked = user.get("locked_balance", 0.0)
        
        await message.answer(
            f"✅ <b>Баланс снят!</b>\n\n"
            f"👤 Пользователь: {user_id} (@{username})\n"
            f"💰 Снято из {balance_name}: ${amount:.2f}\n\n"
            f"💰 Новый обычный баланс: ${new_balance:.2f}\n"
            f"🔒 Новый заблокированный баланс: ${new_locked:.2f}",
            parse_mode="HTML"
        )
        
        # Уведомляем пользователя
        try:
            bot = message.bot
            await bot.send_message(
                chat_id=user_id,
                text=f"⚠️ <b>С вашего баланса снято</b>\n\n"
                     f"💰 Снято из {balance_name}: ${amount:.2f}\n\n"
                     f"💰 Новый обычный баланс: ${new_balance:.2f}\n"
                     f"🔒 Новый заблокированный баланс: ${new_locked:.2f}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя {user_id}: {e}")
        
        logger.info(f"✅ Баланс снят у пользователя {user_id}: ${amount:.2f} из {balance_name}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при снятии баланса: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при снятии баланса: {str(e)}")
    
    await state.clear()


@router.callback_query(F.data.startswith("admin_stats_user_"))
async def admin_stats_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        user_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return
    
    text = await build_user_stats_text(user_id, period="all")
    if not text:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Добавляем кнопки для выбора периода
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Статистика за день", callback_data=f"admin_stats_user_day_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_user_search")],
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_stats_user_day_"))
async def admin_stats_user_day_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа")
        return
    
    try:
        user_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("Некорректный ID", show_alert=True)
        return
    
    text = await build_user_stats_text(user_id, period="day")
    if not text:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    # Добавляем кнопки для выбора периода
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Вся статистика", callback_data=f"admin_stats_user_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_user_search")],
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(DepositStates.waiting_deposit_amount, F.text)
async def handle_deposit_amount(message: Message, state: FSMContext):
    """Обработка суммы пополнения"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    logger.info(f"💰 Обработка суммы пополнения баланса: {message.text}")
    
    # Проверка на отмену
    text = message.text.strip()
    if text.lower() in {"/cancel", "cancel"}:
        await state.clear()
        await message.answer("❌ Пополнение отменено")
        return
    
    # Проверяем, что текст является числом
    try:
        # Пробуем преобразовать в float (поддерживаем запятую и точку)
        amount = float(text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число (например: 10.50 или 1000)")
        return
    
    logger.info(f"✅ Сумма пополнения распознана: {amount}")
    
    if amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0")
        return
    
    data = await state.get_data()
    user_id = data.get("target_user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден в состоянии")
        await state.clear()
        return
    
    # Пополняем баланс
    await db.update_balance(user_id, amount)
    user = await db.get_user(user_id)
    new_balance = user["balance"]
    
    await message.answer(
        f"✅ <b>Баланс пополнен!</b>\n\n"
        f"👤 Пользователь: {user_id}\n"
        f"💰 Пополнено: ${amount:.2f}\n"
        f"💰 Новый баланс: ${new_balance:.2f}",
        parse_mode="HTML"
    )
    
    # Уведомляем пользователя
    try:
        bot = message.bot
        await bot.send_message(
            chat_id=user_id,
            text=f"💰 <b>Ваш баланс пополнен!</b>\n\n"
                 f"Пополнено: ${amount:.2f}\n"
                 f"Новый баланс: ${new_balance:.2f}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю: {e}")
    
    await state.clear()
    logger.info(f"✅ Баланс успешно пополнен: пользователь {user_id}, сумма {amount}")


@router.callback_query(F.data == "admin_crypto_balance")
async def admin_crypto_balance(callback: CallbackQuery):
    """Проверка баланса Crypto Pay"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.answer("⏳ Проверяю баланс...")
    
    try:
        balance_info = await crypto_pay.get_balance()
        
        if balance_info is None:
            await callback.message.answer(
                "❌ <b>Ошибка получения баланса</b>\n\n"
                "Не удалось получить информацию о балансе Crypto Pay.\n"
                "Проверьте настройки API токена.",
                parse_mode="HTML"
            )
            return
        
        # Формируем сообщение с балансами
        text = "💳 <b>Баланс Crypto Pay</b>\n\n"
        
        if not balance_info:
            text += "⚠️ Балансы не найдены"
        else:
            for asset_balance in balance_info:
                # API возвращает currency_code, а не asset_code
                currency_code = asset_balance.get("currency_code") or asset_balance.get("asset_code", "UNKNOWN")
                available = float(asset_balance.get("available", 0))
                # API возвращает onhold, а не locked
                onhold = float(asset_balance.get("onhold", 0) or asset_balance.get("locked", 0))
                total = available + onhold
                
                # Показываем только валюты с ненулевым балансом
                if total > 0:
                    text += f"<b>{currency_code}</b>\n"
                    text += f"  💰 Доступно: {available:.4f}\n"
                    if onhold > 0:
                        text += f"  🔒 Заблокировано: {onhold:.4f}\n"
                    text += f"  📊 Всего: {total:.4f}\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Активные чеки", callback_data="admin_active_checks")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_crypto_balance")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении баланса Crypto Pay: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Ошибка получения баланса</b>\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_active_checks")
async def admin_active_checks(callback: CallbackQuery):
    """Показать активные чеки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.answer("⏳ Загружаю активные чеки...")
    
    try:
        # Получаем активные чеки
        checks_info = await crypto_pay.get_checks(status="active", asset="USDT")
        
        if checks_info is None:
            await callback.message.answer(
                "❌ <b>Ошибка получения чеков</b>\n\n"
                "Не удалось получить информацию об активных чеках.",
                parse_mode="HTML"
            )
            return
        
        # checks_info может быть словарем с ключом "items" или списком
        checks_list = checks_info.get("items", []) if isinstance(checks_info, dict) else (checks_info if isinstance(checks_info, list) else [])
        
        if not checks_list:
            text = "✅ <b>Активные чеки</b>\n\n"
            text += "📋 Активных чеков нет.\n"
            text += "Все средства разблокированы."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_active_checks")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_crypto_balance")],
            ])
        else:
            text = f"📋 <b>Активные чеки</b> ({len(checks_list)})\n\n"
            text += "<i>Заблокированные средства зарезервированы для этих чеков.</i>\n\n"
            
            total_locked = 0.0
            keyboard_buttons = []
            
            for idx, check in enumerate(checks_list):
                check_id = check.get("check_id", "N/A")
                amount = float(check.get("amount", 0))
                asset = check.get("asset", "USDT")
                hash_code = check.get("hash", "N/A")
                created_at = check.get("created_at", "")
                pin_to_user = check.get("pin_to_user", {})
                bot_check_url = check.get("bot_check_url", "")
                
                total_locked += amount
                
                # Форматируем дату
                try:
                    from datetime import datetime
                    if created_at:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_str = dt.strftime("%d.%m.%Y %H:%M")
                    else:
                        created_str = "N/A"
                except:
                    created_str = created_at
                
                user_id = pin_to_user.get("user_id") if pin_to_user else None
                user_info = f"👤 ID: {user_id}" if user_id else "👤 Любой"
                
                text += f"🎫 <b>Чек #{check_id}</b>\n"
                text += f"  💰 Сумма: {amount:.4f} {asset}\n"
                text += f"  🔗 Hash: <code>{hash_code}</code>\n"
                text += f"  {user_info}\n"
                text += f"  📅 Создан: {created_str}\n\n"
                
                # Добавляем кнопки для каждого чека
                row = []
                if bot_check_url:
                    # Кнопка для получения чека (первые 64 символа текста)
                    button_text = f"💳 Чек #{check_id}"[:64]
                    row.append(InlineKeyboardButton(
                        text=button_text,
                        url=bot_check_url
                    ))
                # Кнопка удаления чека
                row.append(InlineKeyboardButton(
                    text=f"🗑️ #{check_id}",
                    callback_data=f"admin_delete_check_{check_id}"
                ))
                keyboard_buttons.append(row)
            
            text += f"<b>💰 Всего заблокировано: {total_locked:.4f} USDT</b>\n\n"
            text += "<i>Нажмите на кнопку с чеком, чтобы получить средства, или удалите чек для разблокировки.</i>"
            
            # Кнопки управления
            keyboard_buttons.append([
                InlineKeyboardButton(text="🗑️ Удалить все", callback_data="admin_delete_all_checks")
            ])
            keyboard_buttons.append([
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_active_checks"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_crypto_balance")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении активных чеков: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Ошибка получения чеков</b>\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("admin_delete_check_"))
async def admin_delete_check(callback: CallbackQuery):
    """Удалить конкретный чек"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Извлекаем ID чека из callback_data
    check_id_str = callback.data.replace("admin_delete_check_", "")
    try:
        check_id = int(check_id_str)
    except ValueError:
        await callback.answer("❌ Неверный ID чека", show_alert=True)
        return
    
    await callback.answer("⏳ Удаляю чек...")
    
    try:
        result = await crypto_pay.delete_check(check_id)
        
        if result and result.get("error"):
            error_name = result.get("name", "unknown")
            error_description = result.get("description", "")
            await callback.message.answer(
                f"❌ <b>Ошибка удаления чека</b>\n\n"
                f"Чек #{check_id}\n"
                f"Ошибка: {error_description or error_name}",
                parse_mode="HTML"
            )
        else:
            # Получаем информацию о чеке для отображения суммы
            checks_info = await crypto_pay.get_checks(status="active", asset="USDT")
            amount = 0.0
            if checks_info:
                checks_list = checks_info.get("items", []) if isinstance(checks_info, dict) else (checks_info if isinstance(checks_info, list) else [])
                for check in checks_list:
                    if check.get("check_id") == check_id:
                        amount = float(check.get("amount", 0))
                        break
            
            text = f"✅ <b>Чек удален</b>\n\n"
            text += f"🎫 Чек #{check_id}\n"
            if amount > 0:
                text += f"💰 Разблокировано: {amount:.4f} USDT"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Активные чеки", callback_data="admin_active_checks")],
                [InlineKeyboardButton(text="💳 Баланс", callback_data="admin_crypto_balance")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
            ])
            
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении чека #{check_id}: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Ошибка удаления чека</b>\n\n"
            f"Чек #{check_id}\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_delete_all_checks")
async def admin_delete_all_checks(callback: CallbackQuery):
    """Удалить все активные чеки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.answer("⏳ Удаляю активные чеки...")
    
    try:
        # Получаем активные чеки
        checks_info = await crypto_pay.get_checks(status="active", asset="USDT")
        
        if checks_info is None:
            await callback.message.answer(
                "❌ <b>Ошибка получения чеков</b>\n\n"
                "Не удалось получить информацию об активных чеках.",
                parse_mode="HTML"
            )
            return
        
        checks_list = checks_info.get("items", []) if isinstance(checks_info, dict) else (checks_info if isinstance(checks_info, list) else [])
        
        if not checks_list:
            await callback.message.answer(
                "✅ <b>Нет активных чеков</b>\n\n"
                "Нечего удалять.",
                parse_mode="HTML"
            )
            return
        
        deleted_count = 0
        failed_count = 0
        total_unlocked = 0.0
        
        for check in checks_list:
            check_id = check.get("check_id")
            amount = float(check.get("amount", 0))
            
            if check_id:
                try:
                    result = await crypto_pay.delete_check(check_id)
                    if result and not result.get("error"):
                        deleted_count += 1
                        total_unlocked += amount
                        logger.info(f"✅ Чек #{check_id} удален, разблокировано {amount:.4f} USDT")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️ Не удалось удалить чек #{check_id}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Ошибка при удалении чека #{check_id}: {e}")
        
        text = f"✅ <b>Удаление чеков завершено</b>\n\n"
        text += f"🗑️ Удалено: {deleted_count}\n"
        if failed_count > 0:
            text += f"❌ Ошибок: {failed_count}\n"
        text += f"💰 Разблокировано: {total_unlocked:.4f} USDT"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Баланс", callback_data="admin_crypto_balance")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении чеков: {e}", exc_info=True)
        await callback.message.answer(
            f"❌ <b>Ошибка удаления чеков</b>\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_stats")
async def admin_stats_menu(callback: CallbackQuery):
    """Меню статистики"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Общая статистика", callback_data="stats_general")],
        [InlineKeyboardButton(text="📅 Статистика за сегодня", callback_data="stats_today")],
        [InlineKeyboardButton(text="👤 Статистика пользователя", callback_data="stats_user")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
    ])
    
    await callback.message.answer(
        "📊 <b>Статистика</b>\n\nВыберите тип статистики:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "stats_general")
async def show_general_stats(callback: CallbackQuery):
    """Показать общую статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Получаем общую статистику из БД
    import aiosqlite
    
    async with aiosqlite.connect(db.db_path) as database:
        database.row_factory = aiosqlite.Row
        
        # Всего пользователей
        async with database.execute("SELECT COUNT(*) as count FROM users") as cursor:
            total_users = (await cursor.fetchone())["count"]
        
        # Всего игр
        async with database.execute("SELECT COUNT(*) as count FROM games") as cursor:
            total_games = (await cursor.fetchone())["count"]
        
        # Общий оборот (сумма всех ставок, исключая арбуз коины)
        async with database.execute("SELECT SUM(bet) as total FROM games WHERE currency IS NULL OR currency != 'arbuzz'") as cursor:
            total_bets = (await cursor.fetchone())["total"] or 0
        
        # Общие выигрыши
        async with database.execute("SELECT SUM(win) as total FROM games WHERE win > 0") as cursor:
            total_wins = (await cursor.fetchone())["total"] or 0
        
        # Общий баланс всех пользователей
        async with database.execute("SELECT SUM(balance) as total FROM users") as cursor:
            total_balance = (await cursor.fetchone())["total"] or 0
    
    text = f"""📊 <b>Общая статистика</b>

👥 Всего пользователей: {total_users}
🎮 Всего игр: {total_games}
💰 Общий оборот: ${total_bets:.2f}
🎉 Общие выигрыши: ${total_wins:.2f}
💵 Общий баланс: ${total_balance:.2f}"""
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "stats_today")
async def show_today_stats(callback: CallbackQuery):
    """Показать статистику за сегодня"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    import aiosqlite
    today = datetime.now().date()
    
    async with aiosqlite.connect(db.db_path) as database:
        database.row_factory = aiosqlite.Row
        
        # Новые пользователи сегодня
        async with database.execute(
            "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = ?",
            (today,)
        ) as cursor:
            new_users = (await cursor.fetchone())["count"]
        
        # Игры сегодня
        async with database.execute(
            "SELECT COUNT(*) as count FROM games WHERE DATE(created_at) = ?",
            (today,)
        ) as cursor:
            games_today = (await cursor.fetchone())["count"]
        
        # Оборот сегодня (исключая арбуз коины)
        async with database.execute(
            "SELECT SUM(bet) as total FROM games WHERE DATE(created_at) = ? AND (currency IS NULL OR currency != 'arbuzz')",
            (today,)
        ) as cursor:
            bets_today = (await cursor.fetchone())["total"] or 0
        
        # Выигрыши сегодня
        async with database.execute(
            "SELECT SUM(win) as total FROM games WHERE DATE(created_at) = ? AND win > 0",
            (today,)
        ) as cursor:
            wins_today = (await cursor.fetchone())["total"] or 0
    
    text = f"""📅 <b>Статистика за сегодня</b>

👥 Новых пользователей: {new_users}
🎮 Игр сыграно: {games_today}
💰 Оборот: ${bets_today:.2f}
🎉 Выигрыши: ${wins_today:.2f}"""
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


async def build_user_stats_text(user_id: int, period: str = "all") -> Optional[str]:
    """
    Построить текст статистики пользователя
    
    Args:
        user_id: ID пользователя
        period: "all" для всей статистики, "day" для статистики за день
    """
    user = await db.get_user(user_id)
    if not user:
        return None
    
    # Определяем условие для периода
    if period == "day":
        date_filter = "DATE(created_at) = DATE('now', 'localtime')"
        period_text = "за сегодня"
    else:
        date_filter = "1=1"
        period_text = "всего"
    
    async with aiosqlite.connect(db.db_path) as database:
        database.row_factory = aiosqlite.Row
        
        async with database.execute(
            f"SELECT COUNT(*) as count FROM games WHERE user_id = ? AND {date_filter}",
            (user_id,)
        ) as cursor:
            total_games = (await cursor.fetchone())["count"]
        
        async with database.execute(
            f"SELECT SUM(bet) as total FROM games WHERE user_id = ? AND {date_filter} AND (currency IS NULL OR currency != 'arbuzz')",
            (user_id,)
        ) as cursor:
            total_bets = (await cursor.fetchone())["total"] or 0
        
        async with database.execute(
            f"SELECT SUM(win) as total FROM games WHERE user_id = ? AND win > 0 AND {date_filter}",
            (user_id,)
        ) as cursor:
            total_wins = (await cursor.fetchone())["total"] or 0
        
        async with database.execute(
            f"SELECT COUNT(*) as count FROM games WHERE user_id = ? AND win > 0 AND {date_filter}",
            (user_id,)
        ) as cursor:
            win_games = (await cursor.fetchone())["count"]
        
        # Для статистики за день считаем проигрыши за день
        if period == "day":
            async with database.execute(
                f"SELECT SUM(bet) as total FROM games WHERE user_id = ? AND win = 0 AND {date_filter} AND (currency IS NULL OR currency != 'arbuzz')",
                (user_id,)
            ) as cursor:
                day_lost = (await cursor.fetchone())["total"] or 0
        else:
            day_lost = None
    
    balance = user["balance"]
    username = user.get("username", "Неизвестно")
    created_at = user.get("created_at", "Неизвестно")
    total_lost = user.get("total_lost", 0.0)
    
    text = (
        f"👤 <b>Статистика пользователя ({period_text})</b>\n\n"
        f"ID: {user_id}\n"
        f"Username: @{username}\n"
        f"📅 Регистрация: {created_at}\n\n"
    )
    
    if period == "day":
        text += (
            f"💰 Баланс: ${balance:.2f}\n"
            f"🎮 Игр сыграно: {total_games}\n"
            f"💵 Оборот: ${total_bets:.2f}\n"
            f"🏆 Выигрыши: ${total_wins:.2f} ({win_games} игр)\n"
            f"💸 Слито за день: ${day_lost:.2f}"
        )
    else:
        text += (
            f"💰 Баланс: ${balance:.2f}\n"
            f"🎮 Игр сыграно: {total_games}\n"
            f"💵 Оборот: ${total_bets:.2f}\n"
            f"🏆 Выигрыши: ${total_wins:.2f} ({win_games} игр)\n"
            f"💸 Всего слито: ${total_lost:.2f}"
        )
    
    return text


@router.callback_query(F.data == "stats_user")
async def ask_user_stats(callback: CallbackQuery, state: FSMContext):
    """Запросить статистику пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "👤 <b>Статистика пользователя</b>\n\n"
        "Введите ID пользователя или username (без @):",
        parse_mode="HTML"
    )
    await state.set_state(UserStatsStates.waiting_stats_user_id)
    await callback.answer()


# ==================== ОБРАБОТЧИКИ ПОДДЕРЖКИ (должны быть ПЕРЕД другими обработчиками сообщений) ====================

@router.message(SupportReplyStates.waiting_reply_text)
async def handle_support_reply_text(message: Message, state: FSMContext):
    """Обработка текста ответа администратора"""
    logger.info(f"🔵 Обработчик ответа поддержки вызван, user_id: {message.from_user.id}")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ Пользователь {message.from_user.id} не является администратором")
        await state.clear()
        return
    
    # Проверяем команду отмены
    if message.text and message.text.strip().lower() == "/cancel":
        logger.info("❌ Отмена ответа администратором")
        await state.clear()
        await message.answer("❌ Отправка ответа отменена")
        return
    
    # Проверяем, что есть текст или медиа
    if not message.text and not message.photo and not message.video and not message.document:
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение или медиа-файл")
        return
    
    data = await state.get_data()
    support_message_id = data.get("support_message_id")
    user_id = data.get("user_id")
    
    if not support_message_id or not user_id:
        await state.clear()
        await message.answer("❌ Ошибка: данные не найдены")
        return
    
    # Получаем сообщение поддержки
    support_message = await db.get_support_message(support_message_id)
    if not support_message:
        await state.clear()
        await message.answer("❌ Сообщение не найдено")
        return
    
    reply_text = message.text or (message.caption if message.photo else "Медиа-сообщение")
    admin_id = message.from_user.id
    
    # Сохраняем ответ в базу данных
    logger.info(f"💾 Сохранение ответа в БД: message_id={support_message_id}, user_id={user_id}, admin_id={admin_id}")
    success = await db.reply_to_support_message(support_message_id, reply_text, admin_id)
    logger.info(f"✅ Ответ сохранен в БД: {success}")
    
    # Отправляем ответ пользователю
    bot = message.bot
    try:
        reply_message = f"""💬 <b>Ответ от администратора</b>

{reply_text}

━━━━━━━━━━━━━━━━━━━━
Ваше сообщение: {support_message['message_text']}"""
        
        logger.info(f"📤 Отправка ответа пользователю {user_id} (username: @{support_message['username']})")
        
        if message.photo:
            # Если админ отправил фото, отправляем с фото
            logger.info(f"📷 Отправка ответа с фото пользователю {user_id}")
            await bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=reply_message,
                parse_mode="HTML"
            )
        else:
            logger.info(f"📝 Отправка текстового ответа пользователю {user_id}")
            await bot.send_message(
                chat_id=user_id,
                text=reply_message,
                parse_mode="HTML"
            )
        
        logger.info(f"✅ Ответ успешно отправлен пользователю {user_id}")
        await message.answer(
            f"✅ Ответ отправлен пользователю @{support_message['username']} (ID: {user_id})",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке ответа пользователю {user_id}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при отправке ответа пользователю. Возможно, пользователь заблокировал бота.\n\nОшибка: {str(e)}",
            parse_mode="HTML"
        )
    
    await state.clear()
    logger.info(f"🧹 Состояние очищено после отправки ответа")


# ВАЖНО: Обработчик статистики должен быть ПЕРЕД общим обработчиком
# Используем фильтр состояния, чтобы обработчик срабатывал ТОЛЬКО в нужном состоянии
@router.message(UserStatsStates.waiting_stats_user_id, F.text)
async def show_user_stats(message: Message, state: FSMContext):
    """Показать статистику пользователя - только в состоянии waiting_stats_user_id"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(message.from_user.id):
        return
    
    current_state = await state.get_state()
    logger.info(f"📊 Admin router show_user_stats: состояние={current_state}, текст={message.text[:50] if message.text else 'None'}")
    
    logger.info(f"✅ Обработка ввода для статистики: {message.text}")
    query = message.text.strip().lstrip("@")
    user = None
    
    # Пытаемся найти по ID
    if query.isdigit():
        user = await db.get_user(int(query))
    else:
        # Ищем по username
        users = await db.search_users(query, limit=1)
        if users:
            user = users[0]
    
    if not user:
        await message.answer(f"❌ Пользователь не найден. Проверьте ID или username")
        await state.clear()
        return
    
    text = await build_user_stats_text(user["user_id"])
    await message.answer(text, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "admin_partners")
async def admin_partners_menu(callback: CallbackQuery):
    """Меню партнеров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить партнера", callback_data="partner_add")],
        [InlineKeyboardButton(text="📋 Список партнеров", callback_data="partner_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
    ])
    
    await callback.message.answer(
        "🤝 <b>Управление партнерами</b>\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "partner_add")
async def add_partner_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление партнера"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(callback.from_user.id):
        try:
            await callback.answer("❌ У вас нет доступа")
        except Exception:
            pass
        return
    
    logger.info(f"🔍 add_partner_start вызван для пользователя {callback.from_user.id}")
    
    # Отвечаем на callback сразу, чтобы избежать ошибки "query is too old"
    try:
        await callback.answer()
    except Exception as e:
        error_msg = str(e).lower()
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning(f"Устаревший callback query в add_partner_start: {e}")
        pass
    
    await callback.message.answer(
        "🤝 <b>Добавление партнера</b>\n\n"
        "Введите ID пользователя или username (без @):",
        parse_mode="HTML"
    )
    
    await state.set_state(PartnerStates.waiting_partner_user_id)
    set_state_result = await state.get_state()
    logger.info(f"📊 Состояние установлено: {set_state_result}")


# Обработчик партнера перемещен выше для приоритета


@router.callback_query(F.data.startswith("partner_percent_"))
async def handle_partner_percent(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора процента для партнера"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Парсим callback_data: partner_percent_{percent}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка обработки", show_alert=True)
        return
    
    percent = float(parts[2])
    
    data = await state.get_data()
    partner_user_id = data.get("partner_user_id")
    prefix = data.get("partner_prefix")
    
    if not partner_user_id or not prefix:
        await callback.answer("❌ Ошибка: данные не найдены", show_alert=True)
        await state.clear()
        return
    
    # Сохраняем партнера с выбранным процентом
    await db.create_partner(partner_user_id, prefix, percent, None)
    
    user = await db.get_user(partner_user_id)
    username = user.get("username", "неизвестно")
    
    text = f"✅ <b>Партнер добавлен!</b>\n\n"
    text += f"👤 Пользователь: {partner_user_id} (@{username})\n"
    text += f"🏷 Префикс: {prefix}\n"
    text += f"💲 Процент с проигрышей: {percent}%"
    
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except:
        await callback.message.answer(text, parse_mode="HTML")
    
    await callback.answer(f"✅ Партнер сохранен с процентом {percent}%!")
    await state.clear()


@router.callback_query(F.data == "partner_list")
async def show_partners_list(callback: CallbackQuery):
    """Показать список партнеров"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    partners = await db.get_all_partners()
    
    if not partners:
        await callback.message.answer("📋 <b>Список партнеров</b>\n\nПартнеры не найдены", parse_mode="HTML")
        await callback.answer()
        return
    
    text = "📋 <b>Список партнеров</b>\n\n"
    
    import json
    from config import REFERRAL_LEVELS
    
    for i, partner in enumerate(partners, 1):
        user_id = partner["user_id"]
        username = partner.get("username", "неизвестно")
        prefix = partner["prefix"]
        percent = partner["referral_percent"]
        level_percents_str = partner.get("level_percents")
        referrals = partner["total_referrals"]
        volume = partner["total_volume"]
        
        text += f"<b>{i}. [{prefix}] @{username}</b>\n"
        text += f"ID: {user_id}\n"
        
        # Если есть проценты для уровней, показываем их
        if level_percents_str:
            try:
                level_percents = json.loads(level_percents_str)
                text += f"📊 <b>Проценты по уровням:</b>\n"
                for idx, level_config in enumerate(REFERRAL_LEVELS, 1):
                    # Пробуем получить процент по числовому ключу или строковому
                    level_percent = level_percents.get(idx) or level_percents.get(str(idx))
                    if level_percent:
                        volume_threshold = level_config["volume"]
                        text += f"  Ур.{idx} (${volume_threshold:,.0f}): {level_percent}%\n"
            except:
                text += f"Реф. процент: {percent}%\n"
        else:
            text += f"Реф. процент: {percent}%\n"
        
        text += f"Рефералов: {referrals}\n"
        text += f"Оборот: ${volume:.2f}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_partners")],
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_chats")
async def admin_chats_menu(callback: CallbackQuery):
    """Меню чатов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    chats = await db.get_all_chats()
    
    if not chats:
        await callback.message.answer(
            "💬 <b>Чаты</b>\n\n"
            "Бот еще не добавлен ни в один чат как администратор.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    text = f"💬 <b>Чаты где бот администратор</b>\n\n"
    text += f"Всего чатов: {len(chats)}\n\n"
    
    for i, chat in enumerate(chats, 1):
        chat_id = chat["chat_id"]
        chat_type = chat.get("chat_type", "unknown")
        title = chat.get("title") or "Без названия"
        username = chat.get("username")
        invite_link = chat.get("invite_link")
        bot_added_at = chat.get("bot_added_at", "Неизвестно")
        messages_count = chat.get("messages_count", 0)
        last_message_at = chat.get("last_message_at")
        
        text += f"<b>{i}. {title}</b>\n"
        if username:
            text += f"@{username}\n"
        text += f"ID: {chat_id}\n"
        text += f"Тип: {chat_type}\n"
        text += f"📅 Добавлен: {bot_added_at}\n"
        text += f"💬 Сообщений от бота: {messages_count}\n"
        if last_message_at:
            text += f"🕐 Последнее сообщение: {last_message_at}\n"
        if invite_link:
            text += f"🔗 <a href=\"{invite_link}\">Ссылка-приглашение</a>\n"
        text += f"💬 <a href=\"tg://resolve?domain={username or chat_id}\">Открыть чат</a>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_chats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
    ])
    
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "admin_finish_pvp_100")
async def admin_finish_pvp_100(callback: CallbackQuery):
    """Завершить дуэль PvP #100 вручную"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    logger.info(f"🔧 Админ {callback.from_user.id} пытается завершить PvP #100")
    
    try:
        from handlers.pvp import start_pvp_game_in_channel
        
        # Проверяем, существует ли PvP #100
        duel = await db.get_pvp_duel(duel_id=100)
        if not duel:
            logger.warning("PvP #100 не найдена")
            await callback.answer("❌ PvP #100 не найдена", show_alert=True)
            return
        
        logger.info(f"PvP #100 найдена, статус: {duel.get('status')}")
        
        # Проверяем статус дуэли
        if duel.get("status") in ["finished", "cancelled"]:
            logger.info("PvP #100 уже завершена или отменена")
            await callback.answer("❌ PvP #100 уже завершена или отменена", show_alert=True)
            return
        
        # Получаем участников
        participants = await db.get_pvp_participants(100)
        logger.info(f"Участников в PvP #100: {len(participants)}")
        
        if not participants:
            await callback.answer("❌ В PvP #100 нет участников", show_alert=True)
            return
        
        await callback.answer("🚀 Запускаю игру PvP #100...")
        logger.info("Запускаю start_pvp_game_in_channel для дуэли #100")
        
        # Запускаем игру
        await start_pvp_game_in_channel(callback.bot, 100)
        
        logger.info("✅ Игра PvP #100 успешно запущена")
        
        await callback.message.answer(
            f"✅ <b>Дуэль PvP #100 завершена!</b>\n\n"
            f"👥 Участников: {len(participants)}\n"
            f"💰 Призовой фонд: ${duel['total_pot']:.2f}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении PvP #100: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        await callback.message.answer(
            f"❌ <b>Ошибка при завершении PvP #100</b>\n\n"
            f"Ошибка: {str(e)}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    """Вернуться в админ меню"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    text = """🔐 <b>Админ Панель</b>

Выберите действие:"""
    
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode="HTML")
    await callback.answer()


# ==================== ПРОМОКОДЫ (CALLBACK HANDLERS) ====================
# Обработчики сообщений промокодов уже зарегистрированы выше (перед обработчиком партнера)

@router.callback_query(F.data == "admin_promo_codes")
async def admin_promo_codes_menu(callback: CallbackQuery):
    """Меню промокодов"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Получаем все промокоды
    promos = await db.get_all_promo_codes()
    
    # Автоматически обновляем промокоды с исчерпанными активациями
    # (можно добавить пометку или скрыть их)
    active_promos = []
    exhausted_promos = []
    
    for promo in promos:
        if promo['remaining_activations'] > 0:
            active_promos.append(promo)
        else:
            exhausted_promos.append(promo)
    
    text = "🎟️ <b>Промокоды</b>\n\n"
    
    if not promos:
        text += "Промокодов пока нет.\n\n"
    else:
        text += "<b>Активные промокоды:</b>\n\n"
        if active_promos:
            for promo in active_promos[:10]:  # Показываем первые 10
                text += f"<code>{promo['code']}</code>\n"
                text += f"💰 ${promo['amount']:.2f} | "
                text += f"Активаций: {promo['remaining_activations']}/{promo['total_activations']}\n"
                if promo['requires_channel_subscription']:
                    text += f"📢 Канал: @{promo['channel_username']}\n"
                text += "\n"
        else:
            text += "Активных промокодов нет.\n\n"
        
        if exhausted_promos:
            text += f"\n<b>Исчерпанные промокоды ({len(exhausted_promos)}):</b>\n"
            for promo in exhausted_promos[:5]:  # Показываем первые 5 исчерпанных
                text += f"<code>{promo['code']}</code> - исчерпан\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_create_promo")],
    ])
    
    # Добавляем кнопки только для активных промокодов
    for promo in active_promos[:10]:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"⚙️ Управление {promo['code']}", 
                callback_data=f"promo_manage_{promo['id']}"
            )
        ])
    
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


@router.callback_query(F.data == "admin_create_promo")
async def start_create_promo(callback: CallbackQuery, state: FSMContext):
    """Начать создание промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.message.answer(
        "🎟️ <b>Создание промокода</b>\n\n"
        "Введите код промокода:\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(PromoCodeStates.waiting_code)
    await callback.answer()


async def finish_promo_creation(message_or_callback, state: FSMContext):
    """Завершить создание промокода"""
    import logging
    logger = logging.getLogger(__name__)
    
    data = await state.get_data()
    logger.info(f"🔍 Все данные в состоянии перед завершением: {data}")
    
    code = data.get("code")
    amount = data.get("amount")
    activations = data.get("activations")
    requires_channel = data.get("requires_channel", False)
    channel_username = data.get("channel_username")
    deposit_type = data.get("deposit_type", "no_deposit")
    min_deposit = data.get("min_deposit", 0.0)
    rollover_multiplier = data.get("rollover_multiplier", 1.0)
    
    logger.info(f"🎟️ Завершение создания промокода: code={code}, amount={amount}, activations={activations}, requires_channel={requires_channel}, channel={channel_username}, deposit_type={deposit_type}, min_deposit={min_deposit}, rollover={rollover_multiplier}")
    
    if not code or not amount or not activations:
        missing = []
        if not code:
            missing.append("code")
        if not amount:
            missing.append("amount")
        if not activations:
            missing.append("activations")
        logger.error(f"❌ Недостаточно данных для создания промокода. Отсутствуют: {missing}. Все данные: {data}")
        
        error_msg = f"❌ Ошибка: недостаточно данных для создания промокода.\n\nОтсутствуют: {', '.join(missing)}\n\nПожалуйста, начните создание промокода заново."
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(error_msg)
        else:
            await message_or_callback.message.answer(error_msg)
        await state.clear()
        return
    
    # Создаем промокод
    activation_link = data.get("activation_link")
    try:
        promo_id = await db.create_promo_code(
            code=code,
            amount=amount,
            total_activations=activations,
            requires_channel_subscription=requires_channel,
            created_by=message_or_callback.from_user.id,
            channel_username=channel_username,
            activation_link=activation_link,
            rollover_multiplier=rollover_multiplier,
            deposit_type=deposit_type,
            min_deposit=min_deposit
        )
        logger.info(f"✅ Промокод создан с ID: {promo_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании промокода: {e}", exc_info=True)
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(f"❌ Ошибка при создании промокода: {e}")
        else:
            await message_or_callback.message.answer(f"❌ Ошибка при создании промокода: {e}")
        await state.clear()
        return
    
    # Генерируем ссылку для активации
    from config import BOT_TOKEN
    bot_username = "arbuzcas_bot"  # Замените на username вашего бота
    
    # Если есть сохраненная ссылка (для русских промокодов), используем её
    activation_link = data.get("activation_link")
    if activation_link:
        promo_link = f"https://t.me/{bot_username}?start=promo_{activation_link}"
    else:
        promo_link = f"https://t.me/{bot_username}?start=promo_{code}"
    
    # Формируем сообщение для админа
    deposit_type_text = "💰 Депный" if deposit_type == "deposit" else "✅ Бездепный"
    rollover_text = f"x{rollover_multiplier}" if rollover_multiplier > 1 else "Нет"
    
    promo_text = f"""<b>НОВЫЙ ПРОМОКОД</b>

<code>{code}</code> - <code>${amount:.2f}</code> - <code>{activations}</code> активаций
📌 Тип: {deposit_type_text}"""
    
    if deposit_type == "deposit":
        promo_text += f"\n💳 Мин. депозит: ${min_deposit:.2f}"
    
    promo_text += f"\n🎰 Отыгрыш: {rollover_text}"
    promo_text += "\n\nДля активации промокода перейдите в раздел \"Профиль\" - \"Промокоды\" и введите данный промокод, либо вы можете использовать ссылку ниже для активации чека напрямую!"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Активировать промокод", url=promo_link)],
        [InlineKeyboardButton(text="📢 Разослать всем пользователям", callback_data=f"promo_broadcast_{promo_id}")],
        [InlineKeyboardButton(text="❌ Отказаться", callback_data="promo_cancel_broadcast")],
    ])
    
    try:
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(promo_text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message_or_callback.message.answer(promo_text, reply_markup=keyboard, parse_mode="HTML")
        logger.info(f"✅ Сообщение о создании промокода отправлено админу")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке сообщения о промокоде: {e}", exc_info=True)
    
    await state.clear()


@router.callback_query(F.data.startswith("promo_broadcast_"))
async def promo_broadcast_all(callback: CallbackQuery):
    """Разослать промокод всем пользователям"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await callback.answer("📢 Начинаю рассылку...")
    
    # Получаем всех пользователей
    users = await db.get_all_users()
    total_users = len(users)
    logger.info(f"📢 Начинаю рассылку промокода {promo['code']} для {total_users} пользователей")
    
    # Используем основной экземпляр бота из callback
    bot = callback.bot
    
    promo_text = f"""🎟️ <b>Новый промокод!</b>

<code>{promo['code']}</code>

💰 Сумма: ${promo['amount']:.2f}

Для активации перейдите в "Профиль" - "Промокоды" и введите код: <code>{promo['code']}</code>"""
    
    if promo['requires_channel_subscription']:
        promo_text += f"\n\n📢 Требуется подписка на канал: @{promo['channel_username']}"
    
    # Используем URL-ссылку вместо callback_data для прямой активации
    bot_username = "arbuzcas_bot"
    # Используем activation_link если есть, иначе code
    link_code = promo.get('activation_link') or promo['code']
    promo_link = f"https://t.me/{bot_username}?start=promo_{link_code}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟️ Активировать промокод", url=promo_link)],
    ])
    
    sent = 0
    failed = 0
    blocked = 0
    
    for user in users:
        try:
            await bot.send_message(
                user['user_id'],
                promo_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            sent += 1
            if sent % 10 == 0:  # Логируем каждые 10 сообщений
                logger.info(f"📤 Отправлено: {sent}/{total_users}")
            await asyncio.sleep(0.05)  # Задержка между сообщениями
        except Exception as e:
            failed += 1
            error_msg = str(e).lower()
            if "blocked" in error_msg or "forbidden" in error_msg:
                blocked += 1
            logger.debug(f"Ошибка при отправке промокода пользователю {user['user_id']}: {e}")
    
    result_text = f"✅ <b>Рассылка завершена!</b>\n\n"
    result_text += f"📊 Всего пользователей: {total_users}\n"
    result_text += f"✅ Отправлено: {sent}\n"
    result_text += f"❌ Ошибок: {failed}"
    if blocked > 0:
        result_text += f"\n🚫 Заблокировано: {blocked}"
    
    await callback.message.answer(result_text, parse_mode="HTML")
    logger.info(f"✅ Рассылка завершена: отправлено {sent}, ошибок {failed}")


@router.callback_query(F.data == "promo_cancel_broadcast")
async def promo_cancel_broadcast(callback: CallbackQuery):
    """Отказаться от рассылки"""
    await callback.answer("❌ Рассылка отменена")
    await callback.message.edit_text("✅ Промокод создан, но рассылка не выполнена.")


@router.callback_query(F.data.startswith("promo_manage_"))
async def promo_manage_menu(callback: CallbackQuery):
    """Меню управления промокодом"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    # Обновляем данные промокода перед показом (на случай если активации изменились)
    promo = await db.get_promo_code_by_id(promo_id)
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    status_emoji = "✅" if promo['remaining_activations'] > 0 else "❌"
    status_text = "Активен" if promo['remaining_activations'] > 0 else "Исчерпан"
    
    text = f"""⚙️ <b>Управление промокодом</b>

🎟️ Код: <code>{promo['code']}</code>
💰 Сумма: ${promo['amount']:.2f}
📊 Активаций: {promo['remaining_activations']}/{promo['total_activations']}
{status_emoji} Статус: {status_text}"""
    
    if promo['requires_channel_subscription']:
        text += f"\n📢 Канал: @{promo['channel_username']}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"promo_edit_{promo_id}")],
        [InlineKeyboardButton(text="📢 Опубликовать", callback_data=f"promo_publish_{promo_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"promo_delete_{promo_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_promo_codes")],
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        # Если не удалось отредактировать, отправляем новое сообщение
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


@router.callback_query(F.data.startswith("promo_publish_"))
async def promo_publish_to_channel(callback: CallbackQuery, state: FSMContext):
    """Опубликовать промокод в канал"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    await state.update_data(promo_id=promo_id)
    
    await callback.message.answer(
        "Введите username канала (без @, например: mychannel):\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_channel_for_publish)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_edit_code_"))
async def promo_edit_code_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование кода промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(editing_promo_id=promo_id)
    await callback.message.answer(
        f"✏️ <b>Редактирование кода промокода</b>\n\n"
        f"Текущий код: <code>{promo['code']}</code>\n\n"
        f"Введите новый код промокода:\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_edit_code)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_edit_amount_"))
async def promo_edit_amount_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование суммы промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(editing_promo_id=promo_id)
    await callback.message.answer(
        f"💰 <b>Редактирование суммы промокода</b>\n\n"
        f"Текущая сумма: ${promo['amount']:.2f}\n\n"
        f"Введите новую сумму (например: 10 или 10.5):\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_edit_amount)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_edit_activations_"))
async def promo_edit_activations_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование количества активаций"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(editing_promo_id=promo_id)
    await callback.message.answer(
        f"📊 <b>Редактирование активаций</b>\n\n"
        f"Текущее количество: {promo['total_activations']}\n"
        f"Использовано: {promo['total_activations'] - promo['remaining_activations']}\n"
        f"Осталось: {promo['remaining_activations']}\n\n"
        f"Введите новое общее количество активаций:\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_edit_activations)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_edit_channel_"))
async def promo_edit_channel_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование канала"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(editing_promo_id=promo_id)
    current_channel = promo.get('channel_username', 'не установлен')
    await callback.message.answer(
        f"📢 <b>Редактирование канала</b>\n\n"
        f"Текущий канал: @{current_channel}\n\n"
        f"Введите новый username канала (без @) или отправьте 'нет' чтобы убрать требование подписки:\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    await state.set_state(PromoCodeStates.waiting_edit_channel)
    await callback.answer()


@router.message(PromoCodeStates.waiting_edit_code)
async def handle_edit_code(message: Message, state: FSMContext):
    """Обработка нового кода промокода"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith("/"):
        if message.text and message.text.strip().lower() == "/cancel":
            await state.clear()
            await message.answer("❌ Редактирование отменено")
        return
    
    data = await state.get_data()
    promo_id = data.get("editing_promo_id")
    
    if not promo_id:
        await message.answer("❌ Ошибка: промокод не найден")
        await state.clear()
        return
    
    new_code = message.text.strip().upper()
    
    # Проверяем, не существует ли уже такой промокод
    existing = await db.get_promo_code(new_code)
    if existing and existing['id'] != promo_id:
        await message.answer("❌ Промокод с таким кодом уже существует. Введите другой:")
        return
    
    await db.update_promo_code(promo_id, code=new_code)
    await message.answer(f"✅ Код промокода обновлен: <code>{new_code}</code>", parse_mode="HTML")
    await state.clear()


@router.message(PromoCodeStates.waiting_edit_amount)
async def handle_edit_amount(message: Message, state: FSMContext):
    """Обработка новой суммы промокода"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith("/"):
        if message.text and message.text.strip().lower() == "/cancel":
            await state.clear()
            await message.answer("❌ Редактирование отменено")
        return
    
    try:
        amount = float(message.text.strip().replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например: 10 или 10.5):")
        return
    
    data = await state.get_data()
    promo_id = data.get("editing_promo_id")
    
    if not promo_id:
        await message.answer("❌ Ошибка: промокод не найден")
        await state.clear()
        return
    
    await db.update_promo_code(promo_id, amount=amount)
    await message.answer(f"✅ Сумма промокода обновлена: ${amount:.2f}")
    await state.clear()


@router.message(PromoCodeStates.waiting_edit_activations)
async def handle_edit_activations(message: Message, state: FSMContext):
    """Обработка нового количества активаций"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith("/"):
        if message.text and message.text.strip().lower() == "/cancel":
            await state.clear()
            await message.answer("❌ Редактирование отменено")
        return
    
    try:
        activations = int(message.text.strip())
        if activations <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число:")
        return
    
    data = await state.get_data()
    promo_id = data.get("editing_promo_id")
    
    if not promo_id:
        await message.answer("❌ Ошибка: промокод не найден")
        await state.clear()
        return
    
    await db.update_promo_code(promo_id, total_activations=activations)
    await message.answer(f"✅ Количество активаций обновлено: {activations}")
    await state.clear()


@router.message(PromoCodeStates.waiting_edit_channel)
async def handle_edit_channel(message: Message, state: FSMContext):
    """Обработка нового канала"""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or message.text.startswith("/"):
        if message.text and message.text.strip().lower() == "/cancel":
            await state.clear()
            await message.answer("❌ Редактирование отменено")
        return
    
    data = await state.get_data()
    promo_id = data.get("editing_promo_id")
    
    if not promo_id:
        await message.answer("❌ Ошибка: промокод не найден")
        await state.clear()
        return
    
    channel_text = message.text.strip().lower()
    
    if channel_text in ['нет', 'no', 'убрать', 'remove']:
        await db.update_promo_code(promo_id, requires_channel_subscription=False, channel_username=None)
        await message.answer("✅ Требование подписки на канал убрано")
    else:
        channel_username = message.text.strip().lstrip('@')
        await db.update_promo_code(promo_id, requires_channel_subscription=True, channel_username=channel_username)
        await message.answer(f"✅ Канал обновлен: @{channel_username}")
    
    await state.clear()


@router.callback_query(F.data.startswith("promo_delete_"))
async def promo_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"promo_delete_execute_{promo_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"promo_manage_{promo_id}")],
    ])
    
    try:
        await callback.message.edit_text(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы уверены, что хотите удалить промокод <code>{promo['code']}</code>?\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        # Если не удалось отредактировать (например, сообщение не изменилось), отправляем новое
        await callback.message.answer(
            f"⚠️ <b>Подтверждение удаления</b>\n\n"
            f"Вы уверены, что хотите удалить промокод <code>{promo['code']}</code>?\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.callback_query(F.data.startswith("promo_delete_execute_"))
async def promo_delete_execute(callback: CallbackQuery):
    """Удалить промокод"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    code_before_delete = promo['code']
    await db.delete_promo_code(promo_id)
    await callback.answer("✅ Промокод удален", show_alert=True)
    
    # Показываем сообщение об успешном удалении
    try:
        await callback.message.edit_text(
            f"✅ <b>Промокод удален</b>\n\n"
            f"Промокод <code>{code_before_delete}</code> был успешно удален.",
            parse_mode="HTML"
        )
    except:
        await callback.message.answer(
            f"✅ <b>Промокод удален</b>\n\n"
            f"Промокод <code>{code_before_delete}</code> был успешно удален.",
            parse_mode="HTML"
        )
    
    # Возвращаемся в меню промокодов через небольшую задержку
    await asyncio.sleep(1)
    await admin_promo_codes_menu(callback)


@router.callback_query(F.data.startswith("promo_edit_"))
async def promo_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Меню редактирования промокода"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    promo_id = int(callback.data.split("_")[-1])
    promo = await db.get_promo_code_by_id(promo_id)
    
    if not promo:
        await callback.answer("❌ Промокод не найден", show_alert=True)
        return
    
    await state.update_data(editing_promo_id=promo_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить код", callback_data=f"promo_edit_code_{promo_id}")],
        [InlineKeyboardButton(text="💰 Изменить сумму", callback_data=f"promo_edit_amount_{promo_id}")],
        [InlineKeyboardButton(text="📊 Изменить активации", callback_data=f"promo_edit_activations_{promo_id}")],
        [InlineKeyboardButton(text="📢 Изменить канал", callback_data=f"promo_edit_channel_{promo_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"promo_manage_{promo_id}")],
    ])
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование промокода</b>\n\n"
        f"🎟️ Код: <code>{promo['code']}</code>\n"
        f"💰 Сумма: ${promo['amount']:.2f}\n"
        f"📊 Активаций: {promo['remaining_activations']}/{promo['total_activations']}\n\n"
        f"Выберите что изменить:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== ОБРАБОТЧИКИ ПОДДЕРЖКИ ====================

@router.callback_query(F.data.startswith("support_reply_"))
async def handle_support_reply_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Ответить' на сообщение поддержки"""
    logger.info(f"🔵 Обработчик support_reply вызван: {callback.data}, user_id: {callback.from_user.id}")
    
    if not is_admin(callback.from_user.id):
        logger.warning(f"❌ Пользователь {callback.from_user.id} не является администратором")
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    try:
        message_id = int(callback.data.replace("support_reply_", ""))
        logger.info(f"📝 ID сообщения поддержки: {message_id}")
    except ValueError as e:
        logger.error(f"❌ Ошибка парсинга ID сообщения: {e}")
        await callback.answer("❌ Ошибка: неверный ID сообщения", show_alert=True)
        return
    
    # Получаем сообщение поддержки
    support_message = await db.get_support_message(message_id)
    if not support_message:
        logger.warning(f"⚠️ Сообщение поддержки {message_id} не найдено")
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return
    
    # Проверяем, не отвечено ли уже
    if support_message.get("replied_to"):
        logger.info(f"ℹ️ На сообщение {message_id} уже был дан ответ")
        await callback.answer("ℹ️ На это сообщение уже был дан ответ", show_alert=True)
        return
    
    # Очищаем предыдущее состояние, если есть
    await state.clear()
    
    # Сохраняем ID сообщения в состояние
    await state.update_data(support_message_id=message_id, user_id=support_message["user_id"])
    logger.info(f"✅ Состояние установлено для ответа на сообщение {message_id}, user_id: {support_message['user_id']}")
    
    # Просим администратора написать ответ
    await callback.message.answer(
        f"💬 <b>Ответ на сообщение поддержки</b>\n\n"
        f"👤 Пользователь: @{support_message['username']} (ID: {support_message['user_id']})\n"
        f"📝 Сообщение: {support_message['message_text']}\n\n"
        f"Напишите ваш ответ:\n\n"
        f"Для отмены отправьте /cancel",
        parse_mode="HTML"
    )
    
    await state.set_state(SupportReplyStates.waiting_reply_text)
    await callback.answer("✅ Готов к ответу")


@router.callback_query(F.data == "admin_export")
async def admin_export_menu(callback: CallbackQuery):
    """Меню экспорта данных"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Пользователи", callback_data="export_users"),
            InlineKeyboardButton(text="💰 Депозиты", callback_data="export_deposits"),
        ],
        [
            InlineKeyboardButton(text="💸 Выводы", callback_data="export_withdrawals"),
            InlineKeyboardButton(text="🎮 Игры", callback_data="export_games"),
        ],
        [
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="export_promo"),
            InlineKeyboardButton(text="🤝 Партнеры", callback_data="export_partners"),
        ],
        [
            InlineKeyboardButton(text="📦 Все данные", callback_data="export_all"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back"),
        ],
    ])
    
    await callback.message.edit_text(
        "📥 <b>Экспорт данных</b>\n\n"
        "Выберите тип данных для экспорта:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export_"))
async def export_data(callback: CallbackQuery):
    """Экспорт данных в CSV"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    export_type = callback.data.replace("export_", "")
    
    try:
        await callback.answer("⏳ Генерирую файл...")
        
        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output)
        
        if export_type == "users":
            users = await db.get_all_users()
            writer.writerow(["ID", "Username", "Баланс (USD)", "Баланс реферальный", "Заблокирован", "Отыгрыш", "Объем", "Заработано", "Реферальный код", "Приглашен", "Создан"])
            for user in users:
                writer.writerow([
                    user.get("user_id"),
                    user.get("username", ""),
                    user.get("balance", 0),
                    user.get("referral_balance", 0),
                    user.get("locked_balance", 0),
                    user.get("rollover_requirement", 0),
                    user.get("total_volume", 0),
                    user.get("total_earned", 0),
                    user.get("referral_code", ""),
                    user.get("referred_by", ""),
                    user.get("created_at", "")
                ])
            filename = "users_export.csv"
            caption = "📊 Экспорт пользователей"
            
        elif export_type == "deposits":
            deposits = await db.get_all_deposits()
            writer.writerow(["ID", "User ID", "Username", "Сумма (USD)", "Метод", "Статус", "Дата"])
            for deposit in deposits:
                user = await db.get_user(deposit.get("user_id"))
                username = user.get("username", "N/A") if user else "N/A"
                writer.writerow([
                    deposit.get("id"),
                    deposit.get("user_id"),
                    username,
                    deposit.get("amount", 0),
                    deposit.get("method", ""),
                    deposit.get("status", ""),
                    deposit.get("created_at", "")
                ])
            filename = "deposits_export.csv"
            caption = "💰 Экспорт депозитов"
            
        elif export_type == "withdrawals":
            withdrawals = await db.get_all_withdrawals()
            writer.writerow(["ID", "User ID", "Username", "Сумма (USD)", "Метод", "Подарок", "Статус", "Дата"])
            for withdrawal in withdrawals:
                user = await db.get_user(withdrawal.get("user_id"))
                username = user.get("username", "N/A") if user else "N/A"
                gift_info = ""
                if withdrawal.get("gift_emoji") or withdrawal.get("gift_name"):
                    gift_info = f"{withdrawal.get('gift_emoji', '')} {withdrawal.get('gift_name', '')}"
                writer.writerow([
                    withdrawal.get("id"),
                    withdrawal.get("user_id"),
                    username,
                    withdrawal.get("amount", 0),
                    withdrawal.get("method", ""),
                    gift_info,
                    withdrawal.get("status", ""),
                    withdrawal.get("created_at", "")
                ])
            filename = "withdrawals_export.csv"
            caption = "💸 Экспорт выводов"
            
        elif export_type == "games":
            games = await db.get_all_games()
            writer.writerow(["ID", "User ID", "Username", "Тип игры", "Ставка", "Результат", "Выигрыш", "Дата"])
            for game in games:
                user = await db.get_user(game.get("user_id"))
                username = user.get("username", "N/A") if user else "N/A"
                writer.writerow([
                    game.get("id"),
                    game.get("user_id"),
                    username,
                    game.get("game_type", ""),
                    game.get("bet", 0),
                    game.get("result", 0),
                    game.get("win", 0),
                    game.get("created_at", "")
                ])
            filename = "games_export.csv"
            caption = "🎮 Экспорт игр"
            
        elif export_type == "promo":
            promo_codes = await db.get_all_promo_codes()
            writer.writerow(["ID", "Код", "Сумма", "Всего активаций", "Осталось", "Требует подписки", "Канал", "Отыгрыш", "Тип депозита", "Мин. депозит", "Создан"])
            for promo in promo_codes:
                writer.writerow([
                    promo.get("id"),
                    promo.get("code", ""),
                    promo.get("amount", 0),
                    promo.get("total_activations", 0),
                    promo.get("remaining_activations", 0),
                    promo.get("requires_channel_subscription", False),
                    promo.get("channel_username", ""),
                    promo.get("rollover_multiplier", 1.0),
                    promo.get("deposit_type", ""),
                    promo.get("min_deposit", 0),
                    promo.get("created_at", "")
                ])
            filename = "promo_export.csv"
            caption = "🎟️ Экспорт промокодов"
            
        elif export_type == "partners":
            partners = await db.get_all_partners()
            writer.writerow(["ID", "User ID", "Username", "Префикс", "Процент", "Уровни", "Рефералов", "Объем", "Создан"])
            for partner in partners:
                user = await db.get_user(partner.get("user_id"))
                username = user.get("username", "N/A") if user else "N/A"
                writer.writerow([
                    partner.get("id"),
                    partner.get("user_id"),
                    username,
                    partner.get("prefix", ""),
                    partner.get("referral_percent", 0),
                    partner.get("level_percents", ""),
                    partner.get("total_referrals", 0),
                    partner.get("total_volume", 0),
                    partner.get("created_at", "")
                ])
            filename = "partners_export.csv"
            caption = "🤝 Экспорт партнеров"
            
        elif export_type == "all":
            # Экспорт всех данных в один файл (разные листы если Excel, или несколько CSV)
            if PANDAS_AVAILABLE:
                # Используем Excel с несколькими листами
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Пользователи
                    users = await db.get_all_users()
                    if users:
                        df_users = pd.DataFrame(users)
                        df_users.to_excel(writer, sheet_name='Пользователи', index=False)
                    
                    # Депозиты
                    deposits = await db.get_all_deposits()
                    if deposits:
                        df_deposits = pd.DataFrame(deposits)
                        df_deposits.to_excel(writer, sheet_name='Депозиты', index=False)
                    
                    # Выводы
                    withdrawals = await db.get_all_withdrawals()
                    if withdrawals:
                        df_withdrawals = pd.DataFrame(withdrawals)
                        df_withdrawals.to_excel(writer, sheet_name='Выводы', index=False)
                    
                    # Игры
                    games = await db.get_all_games()
                    if games:
                        df_games = pd.DataFrame(games)
                        df_games.to_excel(writer, sheet_name='Игры', index=False)
                
                output.seek(0)
                file_data = output.read()
                file_obj = BufferedInputFile(file_data, filename="all_data_export.xlsx")
                await callback.message.answer_document(
                    document=file_obj,
                    caption="📦 Экспорт всех данных (Excel)"
                )
                await callback.answer("✅ Файл отправлен")
                return
            else:
                # Если pandas недоступен, отправляем CSV с пользователями
                users = await db.get_all_users()
                writer.writerow(["ID", "Username", "Баланс (USD)", "Создан"])
                for user in users:
                    writer.writerow([
                        user.get("user_id"),
                        user.get("username", ""),
                        user.get("balance", 0),
                        user.get("created_at", "")
                    ])
                filename = "all_data_export.csv"
                caption = "📦 Экспорт всех данных (CSV)"
        else:
            await callback.answer("❌ Неизвестный тип экспорта", show_alert=True)
            return
        
        # Отправляем CSV файл
        output.seek(0)
        file_data = output.getvalue().encode('utf-8-sig')  # UTF-8 с BOM для Excel
        file_obj = BufferedInputFile(file_data, filename=filename)
        
        await callback.message.answer_document(
            document=file_obj,
            caption=caption
        )
        await callback.answer("✅ Файл отправлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при экспорте данных: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data == "admin_charts")
async def admin_charts_menu(callback: CallbackQuery):
    """Меню графиков"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    if not MATPLOTLIB_AVAILABLE:
        text = """❌ <b>Графики недоступны</b>

Для работы графиков необходимо установить библиотеку matplotlib.

Установите на сервере:
<code>pip install matplotlib pandas openpyxl</code>

После установки перезапустите бота."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("❌ matplotlib не установлен", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Доходы/Расходы", callback_data="chart_profit"),
            InlineKeyboardButton(text="💰 Депозиты", callback_data="chart_deposits"),
        ],
        [
            InlineKeyboardButton(text="💸 Выводы", callback_data="chart_withdrawals"),
            InlineKeyboardButton(text="🎮 Игры", callback_data="chart_games"),
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="chart_users"),
            InlineKeyboardButton(text="📊 Общая статистика", callback_data="chart_overview"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back"),
        ],
    ])
    
    await callback.message.edit_text(
        "📈 <b>Графики и аналитика</b>\n\n"
        "Выберите тип графика:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chart_"))
async def generate_chart(callback: CallbackQuery):
    """Генерация графиков"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    if not MATPLOTLIB_AVAILABLE:
        text = """❌ <b>Графики недоступны</b>

Для работы графиков необходимо установить библиотеку matplotlib.

Установите на сервере:
<code>pip install matplotlib pandas openpyxl</code>

После установки перезапустите бота."""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_charts")],
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("❌ matplotlib не установлен", show_alert=True)
        return
    
    chart_type = callback.data.replace("chart_", "")
    
    try:
        await callback.answer("⏳ Генерирую график...")
        
        # Настройка русского шрифта для matplotlib
        try:
            plt.rcParams['font.family'] = 'DejaVu Sans'
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        if chart_type == "profit":
            # График доходов/расходов
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            deposits = await db.get_deposits_by_date_range(start_date, end_date)
            withdrawals = await db.get_withdrawals_by_date_range(start_date, end_date)
            
            # Группируем по дням
            deposit_dict = {}
            withdrawal_dict = {}
            
            for deposit in deposits:
                try:
                    created_at = deposit.get("created_at", "")
                    if created_at:
                        # Пробуем разные форматы даты
                        try:
                            date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        except:
                            try:
                                date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
                            except:
                                date = datetime.strptime(created_at.split()[0], "%Y-%m-%d").date()
                        deposit_dict[date] = deposit_dict.get(date, 0) + deposit.get("amount", 0)
                except:
                    pass
            
            for withdrawal in withdrawals:
                try:
                    created_at = withdrawal.get("created_at", "")
                    if created_at:
                        # Пробуем разные форматы даты
                        try:
                            date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        except:
                            try:
                                date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
                            except:
                                date = datetime.strptime(created_at.split()[0], "%Y-%m-%d").date()
                        withdrawal_dict[date] = withdrawal_dict.get(date, 0) + withdrawal.get("amount", 0)
                except:
                    pass
            
            # Создаем список всех дат
            all_dates = sorted(set(list(deposit_dict.keys()) + list(withdrawal_dict.keys())))
            
            deposit_values = [deposit_dict.get(date, 0) for date in all_dates]
            withdrawal_values = [withdrawal_dict.get(date, 0) for date in all_dates]
            profit_values = [deposit_values[i] - withdrawal_values[i] for i in range(len(all_dates))]
            
            ax.plot(all_dates, deposit_values, label='Депозиты', marker='o', linewidth=2)
            ax.plot(all_dates, withdrawal_values, label='Выводы', marker='s', linewidth=2)
            ax.plot(all_dates, profit_values, label='Прибыль', marker='^', linewidth=2, linestyle='--')
            
            ax.set_title('Доходы и расходы за последние 30 дней', fontsize=14, fontweight='bold')
            ax.set_xlabel('Дата')
            ax.set_ylabel('Сумма (USD)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.xticks(rotation=45)
            plt.tight_layout()
            
        elif chart_type == "deposits":
            # График депозитов по дням
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            deposits = await db.get_deposits_by_date_range(start_date, end_date)
            
            deposit_dict = {}
            for deposit in deposits:
                try:
                    created_at = deposit.get("created_at", "")
                    if created_at:
                        try:
                            date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        except:
                            try:
                                date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
                            except:
                                date = datetime.strptime(created_at.split()[0], "%Y-%m-%d").date()
                        deposit_dict[date] = deposit_dict.get(date, 0) + deposit.get("amount", 0)
                except:
                    pass
            
            dates = sorted(deposit_dict.keys())
            values = [deposit_dict[date] for date in dates]
            
            ax.bar(dates, values, color='green', alpha=0.7)
            ax.set_title('Депозиты за последние 30 дней', fontsize=14, fontweight='bold')
            ax.set_xlabel('Дата')
            ax.set_ylabel('Сумма (USD)')
            ax.grid(True, alpha=0.3, axis='y')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.xticks(rotation=45)
            plt.tight_layout()
            
        elif chart_type == "withdrawals":
            # График выводов по дням
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            withdrawals = await db.get_withdrawals_by_date_range(start_date, end_date)
            
            withdrawal_dict = {}
            for withdrawal in withdrawals:
                try:
                    created_at = withdrawal.get("created_at", "")
                    if created_at:
                        try:
                            date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        except:
                            try:
                                date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
                            except:
                                date = datetime.strptime(created_at.split()[0], "%Y-%m-%d").date()
                        withdrawal_dict[date] = withdrawal_dict.get(date, 0) + withdrawal.get("amount", 0)
                except:
                    pass
            
            dates = sorted(withdrawal_dict.keys())
            values = [withdrawal_dict[date] for date in dates]
            
            ax.bar(dates, values, color='red', alpha=0.7)
            ax.set_title('Выводы за последние 30 дней', fontsize=14, fontweight='bold')
            ax.set_xlabel('Дата')
            ax.set_ylabel('Сумма (USD)')
            ax.grid(True, alpha=0.3, axis='y')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            plt.xticks(rotation=45)
            plt.tight_layout()
            
        elif chart_type == "games":
            # График игр по типам
            games = await db.get_all_games()
            
            game_types = {}
            for game in games:
                game_type = game.get("game_type", "unknown")
                game_types[game_type] = game_types.get(game_type, 0) + 1
            
            if game_types:
                types = list(game_types.keys())
                counts = list(game_types.values())
                
                ax.bar(types, counts, color='blue', alpha=0.7)
                ax.set_title('Распределение игр по типам', fontsize=14, fontweight='bold')
                ax.set_xlabel('Тип игры')
                ax.set_ylabel('Количество')
                ax.grid(True, alpha=0.3, axis='y')
                plt.xticks(rotation=45)
                plt.tight_layout()
            else:
                ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', fontsize=16)
                ax.set_title('Распределение игр по типам', fontsize=14, fontweight='bold')
            
        elif chart_type == "users":
            # График регистраций пользователей
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            users = await db.get_all_users()
            
            user_dict = {}
            for user in users:
                created_at = user.get("created_at", "")
                if created_at:
                    try:
                        try:
                            date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
                        except:
                            try:
                                date = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").date()
                            except:
                                date = datetime.strptime(created_at.split()[0], "%Y-%m-%d").date()
                        if start_date.date() <= date <= end_date.date():
                            user_dict[date] = user_dict.get(date, 0) + 1
                    except:
                        pass
            
            if user_dict:
                dates = sorted(user_dict.keys())
                values = [user_dict[date] for date in dates]
                
                ax.bar(dates, values, color='purple', alpha=0.7)
                ax.set_title('Регистрации пользователей за последние 30 дней', fontsize=14, fontweight='bold')
                ax.set_xlabel('Дата')
                ax.set_ylabel('Количество')
                ax.grid(True, alpha=0.3, axis='y')
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
                plt.xticks(rotation=45)
                plt.tight_layout()
            else:
                ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', fontsize=16)
                ax.set_title('Регистрации пользователей', fontsize=14, fontweight='bold')
            
        elif chart_type == "overview":
            # Общая статистика (pie chart)
            deposits = await db.get_all_deposits()
            withdrawals = await db.get_all_withdrawals()
            users = await db.get_all_users()
            games = await db.get_all_games()
            
            total_deposits = sum(d.get("amount", 0) for d in deposits)
            total_withdrawals = sum(w.get("amount", 0) for w in withdrawals)
            total_users = len(users)
            total_games = len(games)
            
            # Создаем несколько графиков
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            
            # График 1: Доходы vs Расходы
            axes[0, 0].pie([total_deposits, total_withdrawals], 
                          labels=['Депозиты', 'Выводы'],
                          autopct='%1.1f%%',
                          colors=['green', 'red'])
            axes[0, 0].set_title('Депозиты vs Выводы', fontweight='bold')
            
            # График 2: Прибыль
            profit = total_deposits - total_withdrawals
            axes[0, 1].bar(['Прибыль'], [profit], color='blue' if profit > 0 else 'red')
            axes[0, 1].set_title(f'Общая прибыль: ${profit:.2f}', fontweight='bold')
            axes[0, 1].set_ylabel('USD')
            
            # График 3: Пользователи
            axes[1, 0].bar(['Пользователи'], [total_users], color='purple')
            axes[1, 0].set_title(f'Всего пользователей: {total_users}', fontweight='bold')
            axes[1, 0].set_ylabel('Количество')
            
            # График 4: Игры
            axes[1, 1].bar(['Игры'], [total_games], color='orange')
            axes[1, 1].set_title(f'Всего игр: {total_games}', fontweight='bold')
            axes[1, 1].set_ylabel('Количество')
            
            plt.tight_layout()
        
        # Сохраняем график в память
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        
        file_obj = BufferedInputFile(buffer.read(), filename=f"chart_{chart_type}.png")
        
        await callback.message.answer_photo(
            photo=file_obj,
            caption=f"📈 График: {chart_type}"
        )
        
        plt.close(fig)
        await callback.answer("✅ График отправлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации графика: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        try:
            plt.close('all')
        except:
            pass


@router.callback_query(F.data == "admin_lotteries")
async def admin_lotteries_menu(callback: CallbackQuery, state: FSMContext):
    """Меню управления лотереями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    # Очищаем состояние FSM при отмене создания лотереи
    await state.clear()
    
    lotteries = await db.get_all_lotteries()
    active_lotteries = [l for l in lotteries if l["status"] == "active"]
    
    text = f"""🎫 <b>Управление лотереями</b>

📊 Активных лотерей: {len(active_lotteries)}
📋 Всего лотерей: {len(lotteries)}

Выберите действие:"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать лотерею", callback_data="lottery_create")],
        [InlineKeyboardButton(text="📋 Список лотерей", callback_data="lottery_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Создание лотереи отменено")


@router.callback_query(F.data == "lottery_create")
async def lottery_create_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание лотереи"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.clear()
    await state.set_state(LotteryStates.waiting_title)
    
    text = """🎫 <b>Создание лотереи</b>

📝 <b>Шаг 1/10:</b> Введите название лотереи

Пример: Новогодняя лотерея 2025"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(LotteryStates.waiting_title)
async def lottery_set_title(message: Message, state: FSMContext):
    """Установить название лотереи"""
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(title=message.text)
    await state.set_state(LotteryStates.waiting_description)
    
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {message.text}

📝 <b>Шаг 2/10:</b> Введите описание лотереи

Пример: Выиграй призы в нашей новогодней лотерее!"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_description)
async def lottery_set_description(message: Message, state: FSMContext):
    """Установить описание лотереи"""
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(description=message.text)
    await state.set_state(LotteryStates.waiting_ticket_price)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {data['title']}
✅ <b>Описание:</b> {data['description']}

📝 <b>Шаг 3/10:</b> Введите цену одного билета (в USD)

Пример: 1.5"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_ticket_price)
async def lottery_set_ticket_price(message: Message, state: FSMContext):
    """Установить цену билета"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        price = float(message.text.replace(",", "."))
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например: 1.5)")
        return
    
    await state.update_data(ticket_price=price)
    await state.set_state(LotteryStates.waiting_max_tickets)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {data['title']}
✅ <b>Описание:</b> {data['description']}
✅ <b>Цена билета:</b> ${price:.2f}

📝 <b>Шаг 4/10:</b> Введите максимальное количество билетов для одного пользователя

Пример: 10"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_max_tickets)
async def lottery_set_max_tickets(message: Message, state: FSMContext):
    """Установить максимум билетов на пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        max_tickets = int(message.text)
        if max_tickets <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число (например: 10)")
        return
    
    await state.update_data(max_tickets_per_user=max_tickets)
    await state.set_state(LotteryStates.waiting_finish_type)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {data['title']}
✅ <b>Цена билета:</b> ${data['ticket_price']:.2f}
✅ <b>Макс. билетов на пользователя:</b> {max_tickets}

📝 <b>Шаг 5/10:</b> Выберите условие завершения лотереи"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ По времени", callback_data="lottery_finish_time")],
        [InlineKeyboardButton(text="👥 По количеству участников", callback_data="lottery_finish_participants")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "lottery_finish_time")
async def lottery_finish_time(callback: CallbackQuery, state: FSMContext):
    """Выбрано завершение по времени"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(finish_type="time")
    await state.set_state(LotteryStates.waiting_finish_datetime)
    
    text = """🎫 <b>Создание лотереи</b>

✅ <b>Условие завершения:</b> По времени

📝 <b>Шаг 6/10:</b> Введите дату и время завершения (формат: YYYY-MM-DD HH:MM)

Пример: 2025-01-15 20:00"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "lottery_finish_participants")
async def lottery_finish_participants(callback: CallbackQuery, state: FSMContext):
    """Выбрано завершение по участникам"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await state.update_data(finish_type="participants")
    await state.set_state(LotteryStates.waiting_finish_participants)
    
    text = """🎫 <b>Создание лотереи</b>

✅ <b>Условие завершения:</b> По количеству участников

📝 <b>Шаг 6/10:</b> Введите количество участников для завершения

Пример: 100"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(LotteryStates.waiting_finish_datetime)
async def lottery_set_finish_datetime(message: Message, state: FSMContext):
    """Установить дату и время завершения"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        datetime_str = message.text.strip()
        # Проверяем формат
        datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте: YYYY-MM-DD HH:MM\nПример: 2025-01-15 20:00")
        return
    
    await state.update_data(finish_datetime=datetime_str, finish_value=datetime_str)
    await state.set_state(LotteryStates.waiting_prizes_count)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {data['title']}
✅ <b>Цена билета:</b> ${data['ticket_price']:.2f}
✅ <b>Завершение:</b> {datetime_str}

📝 <b>Шаг 7/10:</b> Введите количество выигрышных мест

Пример: 3"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_finish_participants)
async def lottery_set_finish_participants(message: Message, state: FSMContext):
    """Установить количество участников для завершения"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        participants = int(message.text)
        if participants <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число (например: 100)")
        return
    
    await state.update_data(finish_participants=participants, finish_value=str(participants))
    await state.set_state(LotteryStates.waiting_prizes_count)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Название:</b> {data['title']}
✅ <b>Цена билета:</b> ${data['ticket_price']:.2f}
✅ <b>Завершение:</b> При {participants} участниках

📝 <b>Шаг 7/10:</b> Введите количество выигрышных мест

Пример: 3"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_prizes_count)
async def lottery_set_prizes_count(message: Message, state: FSMContext):
    """Установить количество призов"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        prizes_count = int(message.text)
        if prizes_count <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число (например: 3)")
        return
    
    await state.update_data(prizes_count=prizes_count, current_prize=1)
    await state.set_state(LotteryStates.waiting_prize_type)
    
    data = await state.get_data()
    text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Выигрышных мест:</b> {prizes_count}

📝 <b>Шаг 8/10 - Приз #{1}/{prizes_count}:</b> Выберите тип приза"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Баланс", callback_data="lottery_prize_balance")],
        [InlineKeyboardButton(text="🎁 Подарок", callback_data="lottery_prize_gift")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("lottery_prize_"))
async def lottery_prize_type(callback: CallbackQuery, state: FSMContext):
    """Выбран тип приза"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    prize_type = callback.data.replace("lottery_prize_", "")
    data = await state.get_data()
    current_prize = data.get("current_prize", 1)
    
    await state.update_data(current_prize_type=prize_type)
    
    if prize_type == "balance":
        await state.set_state(LotteryStates.waiting_prize_value)
        text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Тип приза #{current_prize}:</b> Баланс

📝 Введите сумму приза (в USD)

Пример: 50.0"""
    else:
        await state.set_state(LotteryStates.waiting_prize_description)
        text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Тип приза #{current_prize}:</b> Подарок

📝 Введите название подарка (для поиска в базе)

Пример: Rose"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(LotteryStates.waiting_prize_value)
async def lottery_set_prize_value(message: Message, state: FSMContext):
    """Установить значение приза (баланс)"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        prize_value = float(message.text.replace(",", "."))
        if prize_value <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например: 50.0)")
        return
    
    data = await state.get_data()
    current_prize = data.get("current_prize", 1)
    prizes_count = data.get("prizes_count", 1)
    
    # Сохраняем приз
    if "prizes" not in data:
        data["prizes"] = []
    
    data["prizes"].append({
        "position": current_prize,
        "type": "balance",
        "value": str(prize_value),
        "description": f"${prize_value:.2f}"
    })
    
    await state.update_data(prizes=data["prizes"])
    
    if current_prize < prizes_count:
        # Переходим к следующему призу
        await state.update_data(current_prize=current_prize + 1)
        await state.set_state(LotteryStates.waiting_prize_type)
        
        text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Приз #{current_prize}:</b> ${prize_value:.2f}

📝 <b>Шаг 8/10 - Приз #{current_prize + 1}/{prizes_count}:</b> Выберите тип приза"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Баланс", callback_data="lottery_prize_balance")],
            [InlineKeyboardButton(text="🎁 Подарок", callback_data="lottery_prize_gift")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
        ])
    else:
        # Все призы добавлены, завершаем создание
        await lottery_finalize_create_with_broadcast(message, state, send_broadcast=False)
        return
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(LotteryStates.waiting_prize_description)
async def lottery_set_prize_description(message: Message, state: FSMContext):
    """Установить описание приза (подарок)"""
    if not is_admin(message.from_user.id):
        return
    
    gift_name = message.text.strip()
    data = await state.get_data()
    current_prize = data.get("current_prize", 1)
    prizes_count = data.get("prizes_count", 1)
    prize_type = data.get("current_prize_type", "gift")
    
    # Сохраняем приз
    if "prizes" not in data:
        data["prizes"] = []
    
    data["prizes"].append({
        "position": current_prize,
        "type": "gift",
        "value": gift_name,
        "description": gift_name
    })
    
    await state.update_data(prizes=data["prizes"])
    
    if current_prize < prizes_count:
        # Переходим к следующему призу
        await state.update_data(current_prize=current_prize + 1)
        await state.set_state(LotteryStates.waiting_prize_type)
        
        text = f"""🎫 <b>Создание лотереи</b>

✅ <b>Приз #{current_prize}:</b> {gift_name}

📝 <b>Шаг 8/10 - Приз #{current_prize + 1}/{prizes_count}:</b> Выберите тип приза"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Баланс", callback_data="lottery_prize_balance")],
            [InlineKeyboardButton(text="🎁 Подарок", callback_data="lottery_prize_gift")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
        ])
    else:
        # Все призы добавлены, спрашиваем об авторассылке
        await state.set_state(LotteryStates.waiting_broadcast)
        
        data = await state.get_data()
        text = f"""🎫 <b>Создание лотереи</b>

✅ Все призы добавлены!

📝 <b>Шаг 9/10:</b> Отправить рассылку о новой лотерее?

Выберите действие:"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, отправить всем", callback_data="lottery_broadcast_yes")],
            [InlineKeyboardButton(text="❌ Нет, пропустить", callback_data="lottery_broadcast_no")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_lotteries")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "lottery_broadcast_yes")
async def lottery_broadcast_yes(callback: CallbackQuery, state: FSMContext):
    """Подтверждение авторассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.answer()
    await lottery_finalize_create_with_broadcast(callback.message, state, send_broadcast=True)


@router.callback_query(F.data == "lottery_broadcast_no")
async def lottery_broadcast_no(callback: CallbackQuery, state: FSMContext):
    """Отказ от авторассылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    await callback.answer()
    await lottery_finalize_create_with_broadcast(callback.message, state, send_broadcast=False)


async def lottery_finalize_create_with_broadcast(message: Message, state: FSMContext, send_broadcast: bool = False):
    """Завершить создание лотереи с опциональной авторассылкой"""
    data = await state.get_data()
    
    # Создаем лотерею
    lottery_id = await db.create_lottery(
        title=data["title"],
        description=data["description"],
        ticket_price=data["ticket_price"],
        max_tickets_per_user=data["max_tickets_per_user"],
        finish_type=data["finish_type"],
        created_by=message.from_user.id,
        finish_value=data["finish_value"],
        finish_datetime=data.get("finish_datetime"),
        finish_participants=data.get("finish_participants")
    )
    
    # Добавляем призы
    prizes = data.get("prizes", [])
    for prize in prizes:
        await db.add_lottery_prize(
            lottery_id=lottery_id,
            position=prize["position"],
            prize_type=prize["type"],
            prize_value=prize["value"],
            prize_description=prize["description"]
        )
    
    # Если нужна рассылка
    if send_broadcast:
        await send_lottery_broadcast(message.bot, lottery_id, data)
    
    await state.clear()
    
    text = f"""✅ <b>Лотерея создана!</b>

🎫 <b>ID:</b> #{lottery_id}
📝 <b>Название:</b> {data['title']}
💰 <b>Цена билета:</b> ${data['ticket_price']:.2f}
👥 <b>Макс. билетов на пользователя:</b> {data['max_tickets_per_user']}

🏆 <b>Призы:</b>
"""
    for prize in prizes:
        text += f"{prize['position']}. {prize['description']}\n"
    
    if send_broadcast:
        text += "\n✅ Рассылка отправлена!"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 К списку лотерей", callback_data="lottery_list")],
        [InlineKeyboardButton(text="⬅️ В админ панель", callback_data="admin_back")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def send_lottery_broadcast(bot: Bot, lottery_id: int, lottery_data: dict):
    """Отправить рассылку о новой лотерее"""
    from handlers.pvp import ARBUZIK_CHANNEL, CRYPTOGIFTS_CHANNEL
    
    try:
        # Получаем информацию о лотерее
        lottery = await db.get_lottery(lottery_id)
        prizes = await db.get_lottery_prizes(lottery_id)
        
        # Формируем условие завершения
        finish_text = ""
        if lottery["finish_type"] == "time":
            finish_text = f"⏰ До {lottery['finish_datetime']}"
        elif lottery["finish_type"] == "participants":
            finish_text = f"👥 При {lottery['finish_participants']} участниках"
        
        # Формируем текст рассылки
        text = f"""🎉 <b>НОВАЯ ЛОТЕРЕЯ!</b>

🎫 <b>{lottery['title']}</b>

📄 {lottery['description']}

━━━━━━━━━━━━━━━━━━━━

💰 <b>Цена билета:</b> ${lottery['ticket_price']:.2f}
👥 <b>Макс. билетов на пользователя:</b> {lottery['max_tickets_per_user']}
{finish_text}

━━━━━━━━━━━━━━━━━━━━

🏆 <b>Призы:</b>
"""
        
        for prize in sorted(prizes, key=lambda x: x["position"]):
            text += f"{prize['position']}. {prize['prize_description']}\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
        text += "🎯 <b>Успейте приобрести билеты!</b>"
        
        # Получаем username бота для ссылки
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        # Создаем кнопку
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🎫 Участвовать в лотерее",
                url=f"https://t.me/{bot_username}?start=lottery_{lottery_id}"
            )
        ]])
        
        # Отправляем в каналы
        channels = [ARBUZIK_CHANNEL, CRYPTOGIFTS_CHANNEL]
        for channel in channels:
            try:
                await bot.send_message(
                    chat_id=channel,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Рассылка лотереи #{lottery_id} отправлена в {channel}")
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке в {channel}: {e}")
        
        # Рассылаем всем пользователям
        try:
            all_users = await db.get_all_users()
            logger.info(f"📢 Начинаю рассылку лотереи #{lottery_id} всем пользователям. Всего пользователей: {len(all_users)}")
            
            success_count = 0
            error_count = 0
            
            for user in all_users:
                user_id = user.get("user_id")
                if not user_id or user_id == 0:
                    continue
                
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    success_count += 1
                    
                    if success_count % 30 == 0:
                        await asyncio.sleep(1)
                        
                except Exception as e:
                    error_count += 1
                    if error_count % 10 == 0:
                        logger.warning(f"Ошибка при отправке пользователю {user_id} (ошибок уже: {error_count}): {e}")
                    continue
            
            logger.info(f"✅ Рассылка лотереи завершена. Успешно: {success_count}, Ошибок: {error_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при рассылке всем пользователям: {e}", exc_info=True)
            
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке рассылки лотереи: {e}", exc_info=True)


@router.callback_query(F.data == "lottery_list")
async def lottery_list(callback: CallbackQuery):
    """Список лотерей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    lotteries = await db.get_all_lotteries()
    
    if not lotteries:
        text = "📋 <b>Список лотерей</b>\n\nЛотерей пока нет."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_lotteries")]
        ])
    else:
        text = "📋 <b>Список лотерей</b>\n\n"
        keyboard_buttons = []
        
        for lottery in lotteries[:20]:  # Показываем первые 20
            status_emoji = "🟢" if lottery["status"] == "active" else "🔴"
            text += f"{status_emoji} #{lottery['id']} - {lottery['title']}\n"
            text += f"   💰 ${lottery['ticket_price']:.2f} | 📊 {lottery['total_tickets']} билетов\n\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"#{lottery['id']} - {lottery['title'][:20]}",
                    callback_data=f"lottery_manage_{lottery['id']}"
                )
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_lotteries")
        ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("lottery_manage_"))
async def lottery_manage(callback: CallbackQuery):
    """Управление конкретной лотереей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    lottery_id = int(callback.data.replace("lottery_manage_", ""))
    lottery = await db.get_lottery(lottery_id)
    
    if not lottery:
        await callback.answer("❌ Лотерея не найдена", show_alert=True)
        return
    
    prizes = await db.get_lottery_prizes(lottery_id)
    tickets = await db.get_lottery_tickets(lottery_id)
    winners = await db.get_lottery_winners(lottery_id)
    
    status_text = "🟢 Активна" if lottery["status"] == "active" else "🔴 Завершена"
    
    text = f"""🎫 <b>Лотерея #{lottery_id}</b>

{status_text}
📝 <b>Название:</b> {lottery['title']}
📄 <b>Описание:</b> {lottery['description']}
💰 <b>Цена билета:</b> ${lottery['ticket_price']:.2f}
👥 <b>Макс. билетов на пользователя:</b> {lottery['max_tickets_per_user']}
📊 <b>Продано билетов:</b> {lottery['total_tickets']}
⏰ <b>Завершение:</b> {lottery['finish_type']} - {lottery['finish_value']}

🏆 <b>Призы:</b>
"""
    for prize in sorted(prizes, key=lambda x: x["position"]):
        text += f"{prize['position']}. {prize['prize_description']}\n"
    
    if winners:
        text += f"\n🏆 <b>Победители:</b>\n"
        for winner in sorted(winners, key=lambda x: x["position"]):
            username = winner.get("username", f"ID{winner['user_id']}")
            text += f"{winner['position']}. {username} - {winner['prize_description']}\n"
    
    keyboard_buttons = []
    
    if lottery["status"] == "active":
        keyboard_buttons.append([
            InlineKeyboardButton(text="🎲 Завершить розыгрыш", callback_data=f"lottery_finish_{lottery_id}")
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"lottery_delete_{lottery_id}")
    ])
    keyboard_buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="lottery_list")
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("lottery_finish_"))
async def lottery_finish_draw(callback: CallbackQuery):
    """Завершить лотерею и провести розыгрыш"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    lottery_id = int(callback.data.replace("lottery_finish_", ""))
    lottery = await db.get_lottery(lottery_id)
    
    if not lottery or lottery["status"] != "active":
        await callback.answer("❌ Лотерея не найдена или уже завершена", show_alert=True)
        return
    
    tickets = await db.get_lottery_tickets(lottery_id)
    if not tickets:
        await callback.answer("❌ Нет билетов для розыгрыша", show_alert=True)
        return
    
    prizes = await db.get_lottery_prizes(lottery_id)
    if not prizes:
        await callback.answer("❌ Нет призов в лотерее", show_alert=True)
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
    bot = callback.bot
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
                # Отправляем подарок (нужно будет добавить логику отправки)
                from relay_account import get_relay_client
                relay_client = get_relay_client()
                if relay_client:
                    try:
                        # Логика отправки подарка
                        await db.mark_gift_as_transferred(gift["message_id"], ticket["user_id"])
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
    
    # Завершаем лотерею
    await db.finish_lottery(lottery_id)
    
    # Формируем сообщение о результатах
    text = f"""✅ <b>Розыгрыш завершен!</b>

🎫 <b>Лотерея:</b> {lottery['title']}
📊 <b>Всего билетов:</b> {len(tickets)}
🏆 <b>Победителей:</b> {len(winners)}

<b>Победители:</b>
"""
    for winner_info in winners:
        ticket = winner_info["ticket"]
        prize = winner_info["prize"]
        username = ticket.get("username", f"ID{ticket['user_id']}")
        text += f"{prize['position']}. {username} (билет #{ticket['ticket_number']}) - {prize['prize_description']}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 К списку лотерей", callback_data="lottery_list")],
        [InlineKeyboardButton(text="⬅️ В админ панель", callback_data="admin_back")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Розыгрыш завершен!")


@router.callback_query(F.data.startswith("lottery_delete_"))
async def lottery_delete(callback: CallbackQuery):
    """Удалить лотерею"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    lottery_id = int(callback.data.replace("lottery_delete_", ""))
    lottery = await db.get_lottery(lottery_id)
    
    if not lottery:
        await callback.answer("❌ Лотерея не найдена", show_alert=True)
        return
    
    if lottery["total_tickets"] > 0:
        await callback.answer("❌ Нельзя удалить лотерею с билетами", show_alert=True)
        return
    
    success = await db.delete_lottery(lottery_id)
    
    if success:
        await callback.answer("✅ Лотерея удалена")
        await lottery_list(callback)
    else:
        await callback.answer("❌ Ошибка при удалении", show_alert=True)


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    """Вернуться в админ панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа")
        return
    
    text = """🔐 <b>Админ Панель</b>

Выберите действие:"""
    
    keyboard = get_admin_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(Command("sticker"))
async def cmd_sticker(message: Message, state: FSMContext):
    """Команда для сохранения стикеров"""
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(StickerStates.waiting_stickers)
    await message.answer(
        "📎 Отправьте стикеры, которые нужно сохранить.\n"
        "После отправки всех стикеров отправьте сообщение с названиями в формате:\n\n"
        "1 название1\n"
        "2 название2\n"
        "3 название3\n\n"
        "Или отправьте /cancel для отмены."
    )


@router.message(StickerStates.waiting_stickers)
async def process_stickers(message: Message, state: FSMContext):
    """Обработка стикеров и названий"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    # Проверяем, является ли это командой отмены
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Отмена сохранения стикеров")
        return
    
    # Если это стикер, сохраняем его во временное состояние
    if message.sticker:
        stickers_data = await state.get_data()
        stickers_list = stickers_data.get("stickers", [])
        
        stickers_list.append({
            "file_id": message.sticker.file_id,
            "file_unique_id": message.sticker.file_unique_id,
            "set_name": message.sticker.set_name,
            "emoji": message.sticker.emoji
        })
        
        await state.update_data(stickers=stickers_list)
        await message.answer(f"✅ Стикер #{len(stickers_list)} получен. Отправьте следующий или названия.")
        return
    
    # Если это текст с названиями
    if message.text:
        stickers_data = await state.get_data()
        stickers_list = stickers_data.get("stickers", [])
        
        if not stickers_list:
            await message.answer("❌ Сначала отправьте стикеры!")
            return
        
        # Парсим названия
        lines = message.text.strip().split('\n')
        names_map = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Формат: "1 название" или "1 название тип"
            parts = line.split(None, 1)
            if len(parts) >= 2:
                try:
                    index = int(parts[0]) - 1  # Индекс с 0
                    name_parts = parts[1].split(None, 1)
                    name = name_parts[0]
                    sticker_type = name_parts[1] if len(name_parts) > 1 else None
                    
                    if 0 <= index < len(stickers_list):
                        names_map[index] = {"name": name, "type": sticker_type}
                except ValueError:
                    continue
        
        # Сохраняем стикеры в базу данных
        saved_count = 0
        errors = []
        
        for index, sticker_info in enumerate(stickers_list):
            if index in names_map:
                name_info = names_map[index]
                success = await db.save_sticker(
                    name=name_info["name"],
                    file_id=sticker_info["file_id"],
                    file_unique_id=sticker_info["file_unique_id"],
                    sticker_type=name_info.get("type")
                )
                if success:
                    saved_count += 1
                else:
                    errors.append(f"Стикер #{index + 1} ({name_info['name']})")
            else:
                errors.append(f"Стикер #{index + 1} (нет названия)")
        
        # Формируем ответ
        result_text = f"✅ Сохранено стикеров: {saved_count}\n"
        if errors:
            result_text += f"\n❌ Ошибки:\n" + "\n".join(errors)
        
        await message.answer(result_text)
        await state.clear()
        return
    
    await message.answer("❌ Отправьте стикер или текст с названиями")

