import aiosqlite
import os
import logging
from typing import Optional, List, Dict

DATABASE_PATH = os.getenv("DATABASE_PATH", "database.db")
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0.00,
                    base_bet REAL DEFAULT 1.00,
                    referral_notifications BOOLEAN DEFAULT 1,
                    animations BOOLEAN DEFAULT 1,
                    language TEXT DEFAULT 'ru',
                    referral_code TEXT,
                    referred_by INTEGER,
                    total_volume REAL DEFAULT 0.00,
                    total_earned REAL DEFAULT 0.00,
                    referral_balance REAL DEFAULT 0.00,
                    locked_balance REAL DEFAULT 0.00,
                    rollover_requirement REAL DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица рефералов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    referral_id INTEGER,
                    volume REAL DEFAULT 0.00,
                    earned REAL DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица игр
            await db.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    game_type TEXT,
                    bet REAL,
                    result INTEGER,
                    win REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица джекпотов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jackpots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jackpot_type TEXT,
                    current_bet REAL,
                    current_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица победителей джекпотов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jackpot_winners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    jackpot_type TEXT,
                    amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица партнеров
            await db.execute("""
                CREATE TABLE IF NOT EXISTS partners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    prefix TEXT,
                    referral_percent REAL,
                    level_percents TEXT,
                    total_referrals INTEGER DEFAULT 0,
                    total_volume REAL DEFAULT 0.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Добавляем поле level_percents если его нет (миграция)
            try:
                await db.execute("ALTER TABLE partners ADD COLUMN level_percents TEXT")
            except:
                pass  # Поле уже существует
            
            # Добавляем поле referral_balance если его нет (миграция)
            try:
                await db.execute("ALTER TABLE users ADD COLUMN referral_balance REAL DEFAULT 0.00")
            except:
                pass  # Поле уже существует
            
            # Добавляем поля для отыгрыша в users (миграция)
            try:
                await db.execute("ALTER TABLE users ADD COLUMN locked_balance REAL DEFAULT 0.00")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN rollover_requirement REAL DEFAULT 0.00")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN total_lost REAL DEFAULT 0.00")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN arbuzz_balance REAL DEFAULT 0.00")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_daily_arbuzz_date TEXT")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN first_win_today_arbuzz BOOLEAN DEFAULT 0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_win_date TEXT")
            except:
                pass
            
            # Добавляем поле bet_type в games (миграция)
            try:
                await db.execute("ALTER TABLE games ADD COLUMN bet_type TEXT")
            except:
                pass  # Поле уже существует
            
            # Добавляем поле currency в games (миграция)
            try:
                await db.execute("ALTER TABLE games ADD COLUMN currency TEXT DEFAULT 'dollar'")
            except:
                pass  # Поле уже существует
            
            # Добавляем поля для отыгрыша и типа депозита в checks (миграция)
            try:
                await db.execute("ALTER TABLE checks ADD COLUMN rollover_multiplier REAL DEFAULT 1.0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE checks ADD COLUMN deposit_type TEXT DEFAULT 'no_deposit'")
            except:
                pass
            try:
                await db.execute("ALTER TABLE checks ADD COLUMN min_deposit REAL DEFAULT 0.0")
            except:
                pass
            
            # Добавляем поля для отыгрыша и типа депозита в promo_codes (миграция)
            try:
                await db.execute("ALTER TABLE promo_codes ADD COLUMN rollover_multiplier REAL DEFAULT 1.0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE promo_codes ADD COLUMN deposit_type TEXT DEFAULT 'no_deposit'")
            except:
                pass
            try:
                await db.execute("ALTER TABLE promo_codes ADD COLUMN min_deposit REAL DEFAULT 0.0")
            except:
                pass

            # Таблица депозитов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    method TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица выводов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    method TEXT,
                    gift_emoji TEXT,
                    gift_name TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица chain_payments (для отслеживания TON транзакций)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chain_payments (
                    tx_hash TEXT PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица чеков
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_code TEXT UNIQUE NOT NULL,
                    creator_id INTEGER NOT NULL,
                    total_activations INTEGER NOT NULL,
                    remaining_activations INTEGER NOT NULL,
                    amount_per_activation REAL NOT NULL,
                    requires_captcha BOOLEAN DEFAULT 0,
                    captcha_result TEXT,
                    image_url TEXT,
                    text TEXT,
                    button_text TEXT,
                    button_url TEXT,
                    rollover_multiplier REAL DEFAULT 1.0,
                    deposit_type TEXT DEFAULT 'no_deposit',
                    min_deposit REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица активаций чеков (для отслеживания кто активировал)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS check_activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(check_id, user_id)
                )
            """)

            # Таблица промокодов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    amount REAL NOT NULL,
                    total_activations INTEGER NOT NULL,
                    remaining_activations INTEGER NOT NULL,
                    requires_channel_subscription BOOLEAN DEFAULT 0,
                    channel_username TEXT,
                    rollover_multiplier REAL DEFAULT 1.0,
                    deposit_type TEXT DEFAULT 'no_deposit',
                    min_deposit REAL DEFAULT 0.0,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица подарков релаера (для отслеживания доступных подарков)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS relay_gifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER UNIQUE NOT NULL,
                    emoji TEXT NOT NULL,
                    gift_name TEXT,
                    gift_id INTEGER,
                    slug TEXT,
                    gift_date INTEGER,
                    from_user_id INTEGER,
                    from_username TEXT,
                    is_available BOOLEAN DEFAULT 1,
                    transferred_to INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transferred_at TIMESTAMP
                )
            """)
            
            # Миграция: добавляем новые поля если их нет
            try:
                await db.execute("ALTER TABLE relay_gifts ADD COLUMN slug TEXT")
            except:
                pass
            try:
                await db.execute("ALTER TABLE relay_gifts ADD COLUMN gift_date INTEGER")
            except:
                pass
            try:
                await db.execute("ALTER TABLE relay_gifts ADD COLUMN from_user_id INTEGER")
            except:
                pass
            try:
                await db.execute("ALTER TABLE relay_gifts ADD COLUMN from_username TEXT")
            except:
                pass
            try:
                await db.execute("ALTER TABLE promo_codes ADD COLUMN activation_link TEXT")
            except:
                pass

            # Таблица активаций промокодов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_activations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    promo_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(promo_id, user_id)
                )
            """)

            # Таблица сообщений поддержки
            await db.execute("""
                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    replied_to INTEGER,
                    reply_text TEXT,
                    replied_at TIMESTAMP,
                    replied_by INTEGER
                )
            """)

            # Таблица чатов (где бот является администратором)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_type TEXT,
                    title TEXT,
                    username TEXT,
                    invite_link TEXT,
                    bot_added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    bot_is_admin BOOLEAN DEFAULT 1,
                    messages_count INTEGER DEFAULT 0,
                    last_message_at TIMESTAMP
                )
            """)

            # Таблица PvP дуэлей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_duels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER NOT NULL,
                    game_type TEXT NOT NULL,
                    max_players INTEGER NOT NULL,
                    bet_amount REAL NOT NULL,
                    status TEXT DEFAULT 'waiting',
                    unique_link TEXT UNIQUE NOT NULL,
                    channel_message_id INTEGER,
                    winner_id INTEGER,
                    total_pot REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    duel_mode TEXT DEFAULT 'standard',
                    min_bet REAL DEFAULT 0.0,
                    max_bet REAL DEFAULT 0.0,
                    auto_start_players INTEGER DEFAULT 0
                )
            """)

            # Таблица участников PvP дуэлей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    dice_result INTEGER,
                    dice_emoji TEXT,
                    position INTEGER,
                    bet_amount REAL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(duel_id, user_id)
                )
            """)

            # Таблица билетов для PvP #500 (поддержка множественных билетов)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pvp_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticket_position INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица лотерей
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lotteries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'active',
                    ticket_price REAL NOT NULL,
                    max_tickets_per_user INTEGER NOT NULL,
                    finish_type TEXT NOT NULL,
                    finish_value TEXT,
                    finish_datetime TEXT,
                    finish_participants INTEGER,
                    total_tickets INTEGER DEFAULT 0,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP
                )
            """)

            # Таблица билетов лотереи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticket_number INTEGER NOT NULL,
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(lottery_id, ticket_number)
                )
            """)

            # Таблица победителей лотереи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_winners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticket_number INTEGER NOT NULL,
                    prize_type TEXT NOT NULL,
                    prize_value TEXT NOT NULL,
                    prize_description TEXT,
                    position INTEGER NOT NULL,
                    won_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица призов лотереи (для каждого места)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS lottery_prizes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lottery_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    prize_type TEXT NOT NULL,
                    prize_value TEXT NOT NULL,
                    prize_description TEXT,
                    UNIQUE(lottery_id, position)
                )
            """)
            
            # Миграции для новых полей PvP (слот-турнир режим)
            try:
                await db.execute("ALTER TABLE pvp_duels ADD COLUMN duel_mode TEXT DEFAULT 'standard'")
            except:
                pass
            try:
                await db.execute("ALTER TABLE pvp_duels ADD COLUMN min_bet REAL DEFAULT 0.0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE pvp_duels ADD COLUMN max_bet REAL DEFAULT 0.0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE pvp_duels ADD COLUMN auto_start_players INTEGER DEFAULT 0")
            except:
                pass
            try:
                await db.execute("ALTER TABLE pvp_participants ADD COLUMN bet_amount REAL")
            except:
                pass

            # Таблица стикеров для мини-приложения
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stickers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT NOT NULL,
                    sticker_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(self, user_id: int, username: str, referral_code: Optional[str] = None):
        """Создать пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли пользователь ДО обработки реферального кода
            existing_user = await self.get_user(user_id)
            is_new_user = not existing_user
            
            referred_by = None
            # Реферал засчитывается ТОЛЬКО если это новый пользователь
            if is_new_user and referral_code:
                # Найти пользователя по реферальному коду
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT user_id FROM users WHERE referral_code = ?", (referral_code,)
                ) as cursor:
                    ref_user = await cursor.fetchone()
                    if ref_user:
                        referred_by = ref_user["user_id"]
                        # Проверяем, что реферал не пытается зарегистрировать сам себя
                        if referred_by == user_id:
                            referred_by = None

            if is_new_user:
                # Создаем нового пользователя
                await db.execute(
                    """INSERT INTO users (user_id, username, referral_code, referred_by, balance)
                       VALUES (?, ?, ?, ?, 0.00)""",
                    (user_id, username, f"ref_{user_id}", referred_by),
                )
            else:
                # Обновляем username если изменился (но НЕ меняем referred_by)
                await db.execute(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (username, user_id)
                )
            await db.commit()
            
            # Возвращаем информацию о том, был ли создан новый пользователь и установлен ли referred_by
            return is_new_user, referred_by

    async def update_user_base_bet(self, user_id: int, base_bet: float):
        """Обновить базовую ставку пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET base_bet = ? WHERE user_id = ?",
                (base_bet, user_id)
            )
            await db.commit()

    async def update_balance(self, user_id: int, amount: float):
        """Обновить баланс пользователя (положительное значение - пополнение, отрицательное - списание)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущий баланс для логирования
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                old_balance = row[0] if row else 0.0
            
            # Обновляем баланс
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()
            
            # Получаем новый баланс для логирования
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                new_balance = row[0] if row else 0.0
            
            # Логируем операцию
            operation = "ПОПОЛНЕНИЕ" if amount > 0 else "СПИСАНИЕ"
            logger.info(
                f"💰 {operation}: user_id={user_id}, "
                f"сумма={amount:+.2f} USD, "
                f"баланс: {old_balance:.2f} → {new_balance:.2f} USD"
            )
    
    async def add_locked_balance(self, user_id: int, amount: float, rollover_multiplier: float):
        """Добавить заблокированный баланс с отыгрышем (deprecated, используйте add_rollover_requirement)"""
        await self.add_rollover_requirement(user_id, amount, rollover_multiplier)
    
    async def add_rollover_requirement(self, user_id: int, amount: float, rollover_multiplier: float):
        """Добавить требование отыгрыша: добавляет средства в заблокированный баланс и устанавливает требование отыгрыша
        
        Логика:
        - Средства добавляются в заблокированный баланс (locked_balance) - их нельзя вывести до выполнения отыгрыша
        - Средства НЕ добавляются на обычный баланс (balance) - они будут доступны только после отыгрыша
        - Устанавливается требование отыгрыша (rollover_requirement) - сумма, которую нужно отыграть
        - После выполнения отыгрыша, средства из locked_balance перейдут в balance
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Добавляем средства в заблокированный баланс (нельзя вывести до выполнения отыгрыша)
            await db.execute(
                "UPDATE users SET locked_balance = locked_balance + ? WHERE user_id = ?",
                (amount, user_id),
            )
            # НЕ добавляем на обычный баланс - средства будут доступны только после отыгрыша
            # Увеличиваем требование отыгрыша (сумма * множитель)
            rollover_amount = amount * rollover_multiplier
            await db.execute(
                "UPDATE users SET rollover_requirement = rollover_requirement + ? WHERE user_id = ?",
                (rollover_amount, user_id),
            )
            await db.commit()
    
    async def decrease_rollover(self, user_id: int, bet_amount: float):
        """Уменьшить требование отыгрыша при ставке и перевести средства из заблокированного в доступный баланс
        
        Логика:
        - При активации промокода/чека с отыгрышем: средства идут в locked_balance
        - При отыгрыше: rollover_requirement уменьшается
        - Когда требование полностью выполнено: средства из locked_balance переходят в balance (становятся доступными для вывода)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущее требование и балансы
            user = await self.get_user(user_id)
            if not user:
                return
            
            current_requirement = user.get("rollover_requirement", 0.0)
            locked_balance = user.get("locked_balance", 0.0)
            
            if current_requirement <= 0:
                # Если требования нет, но есть заблокированный баланс - переводим в доступный
                if locked_balance > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance + ?, locked_balance = 0.0 WHERE user_id = ?",
                        (locked_balance, user_id),
                    )
                    await db.commit()
                return
            
            # Уменьшаем требование на сумму ставки
            old_requirement = current_requirement
            new_requirement = max(0.0, current_requirement - bet_amount)
            await db.execute(
                "UPDATE users SET rollover_requirement = ? WHERE user_id = ?",
                (new_requirement, user_id),
            )
            
            # Если требование полностью выполнено, переводим все заблокированные средства в доступный баланс
            if new_requirement == 0.0 and locked_balance > 0:
                await db.execute(
                    "UPDATE users SET balance = balance + ?, locked_balance = 0.0 WHERE user_id = ?",
                    (locked_balance, user_id),
                )
            elif old_requirement > 0 and locked_balance > 0:
                # Вычисляем, какую долю требования выполнили
                completed_fraction = (old_requirement - new_requirement) / old_requirement
                # Переводим соответствующую долю заблокированных средств в доступный баланс
                unlocked_amount = locked_balance * completed_fraction
                
                if unlocked_amount > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance + ?, locked_balance = locked_balance - ? WHERE user_id = ?",
                        (unlocked_amount, unlocked_amount, user_id),
                    )
            
            await db.commit()
    
    async def get_withdrawable_balance(self, user_id: int) -> float:
        """Получить сумму, которую можно вывести (обычный баланс + заблокированный, если отыгрыш выполнен)"""
        user = await self.get_user(user_id)
        if not user:
            return 0.0
        
        balance = user.get("balance", 0.0)
        locked_balance = user.get("locked_balance", 0.0)
        rollover_requirement = user.get("rollover_requirement", 0.0)
        
        # Если есть заблокированные средства с отыгрышем
        if locked_balance > 0 and rollover_requirement > 0:
            # Отыгрыш не выполнен - можно вывести только обычный баланс
            return balance
        
        # Если отыгрыш выполнен или нет заблокированных средств, можно вывести все
        if rollover_requirement == 0.0:
            return balance + locked_balance
        
        # Иначе только обычный баланс
        return balance
    
    async def decrease_locked_balance(self, user_id: int, amount: float):
        """Уменьшить заблокированный баланс"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET locked_balance = locked_balance - ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()

    async def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя"""
        user = await self.get_user(user_id)
        return user["balance"] if user else 0.0

    async def update_setting(self, user_id: int, setting: str, value):
        """Обновить настройку пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE users SET {setting} = ? WHERE user_id = ?",
                (value, user_id),
            )
            await db.commit()

    async def add_game(self, user_id: int, game_type: str, bet: float, result: int, win: float, bet_type: str = None, currency: str = "dollar"):
        """Добавить запись об игре"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO games (user_id, game_type, bet, result, win, bet_type, currency)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, game_type, bet, result, win, bet_type, currency),
            )
            await db.commit()

    async def get_jackpot(self, jackpot_type: str) -> Optional[Dict]:
        """Получить информацию о джекпоте"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM jackpots WHERE jackpot_type = ? ORDER BY id DESC LIMIT 1",
                (jackpot_type,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_or_update_jackpot(self, jackpot_type: str, bet: float, amount: float):
        """Создать или обновить джекпот"""
        async with aiosqlite.connect(self.db_path) as db:
            jackpot = await self.get_jackpot(jackpot_type)
            if jackpot:
                await db.execute(
                    """UPDATE jackpots 
                       SET current_bet = ?, current_amount = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE jackpot_type = ?""",
                    (bet, amount, jackpot_type),
                )
            else:
                await db.execute(
                    """INSERT INTO jackpots (jackpot_type, current_bet, current_amount)
                       VALUES (?, ?, ?)""",
                    (jackpot_type, bet, amount),
                )
            await db.commit()

    async def add_jackpot_winner(self, user_id: int, jackpot_type: str, amount: float):
        """Добавить победителя джекпота"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO jackpot_winners (user_id, jackpot_type, amount)
                   VALUES (?, ?, ?)""",
                (user_id, jackpot_type, amount),
            )
            await db.commit()

    async def get_jackpot_winners(self, jackpot_type: str, limit: int = 10) -> List[Dict]:
        """Получить список победителей джекпота"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT jw.*, u.username 
                   FROM jackpot_winners jw
                   LEFT JOIN users u ON jw.user_id = u.user_id
                   WHERE jw.jackpot_type = ?
                   ORDER BY jw.id DESC
                   LIMIT ?""",
                (jackpot_type, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def create_partner(self, user_id: int, prefix: str, referral_percent: float, level_percents: str = None):
        """Создать партнера"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли уже партнер
            partner = await self.get_partner(user_id)
            if partner:
                if level_percents:
                    await db.execute(
                        """UPDATE partners SET prefix = ?, referral_percent = ?, level_percents = ?
                           WHERE user_id = ?""",
                        (prefix, referral_percent, level_percents, user_id),
                    )
                else:
                    await db.execute(
                        """UPDATE partners SET prefix = ?, referral_percent = ?
                           WHERE user_id = ?""",
                        (prefix, referral_percent, user_id),
                    )
            else:
                if level_percents:
                    await db.execute(
                        """INSERT INTO partners (user_id, prefix, referral_percent, level_percents)
                           VALUES (?, ?, ?, ?)""",
                        (user_id, prefix, referral_percent, level_percents),
                    )
                else:
                    await db.execute(
                        """INSERT INTO partners (user_id, prefix, referral_percent)
                           VALUES (?, ?, ?)""",
                        (user_id, prefix, referral_percent),
                    )
            await db.commit()

    async def get_partner(self, user_id: int) -> Optional[Dict]:
        """Получить партнера"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM partners WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_partner_stats(self, user_id: int, referrals: int = 0, volume: float = 0.0):
        """Обновить статистику партнера"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE partners 
                   SET total_referrals = total_referrals + ?,
                       total_volume = total_volume + ?
                   WHERE user_id = ?""",
                (referrals, volume, user_id),
            )
            await db.commit()

    async def get_all_partners(self) -> List[Dict]:
        """Получить всех партнеров"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT p.*, u.username 
                   FROM partners p
                   LEFT JOIN users u ON p.user_id = u.user_id
                   ORDER BY p.created_at DESC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_partner(self, user_id: int):
        """Удалить партнера"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM partners WHERE user_id = ?", (user_id,)
            )
            await db.commit()

    async def get_user_top_position(self, user_id: int) -> int:
        """Получить позицию пользователя в топе по сумме потраченных на игры денег"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем сумму всех ставок пользователя
            async with db.execute(
                """SELECT COALESCE(SUM(bet), 0) as total_spent 
                   FROM games 
                   WHERE user_id = ?""",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                user_total = row[0] if row else 0
            
            # Считаем сколько пользователей потратили больше (используем подзапрос)
            async with db.execute(
                """SELECT COUNT(*) + 1 as position
                   FROM (
                       SELECT user_id, SUM(bet) as total_spent
                       FROM games
                       WHERE user_id != ?
                       GROUP BY user_id
                       HAVING SUM(bet) > ?
                   )""",
                (user_id, user_total)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1

    async def get_user_top_win(self, user_id: int) -> Optional[Dict]:
        """Получить максимальный выигрыш пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT win, bet, game_type 
                   FROM games 
                   WHERE user_id = ? AND win > 0 
                   ORDER BY win DESC 
                   LIMIT 1""",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    multiplier = row["win"] / row["bet"] if row["bet"] > 0 else 0
                    return {
                        "win": row["win"],
                        "bet": row["bet"],
                        "game_type": row["game_type"],
                        "multiplier": multiplier
                    }
                return None

    async def get_top_by_turnover(self, period: str = "all", limit: int = 10) -> List[Dict]:
        """Получить топ игроков по обороту (сумма всех ставок)
        
        Args:
            period: "day", "week", или "all"
            limit: количество игроков в топе
        
        Returns:
            Список словарей с user_id, username, turnover
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Определяем условие для периода
            if period == "day":
                date_filter = "DATE(g.created_at) = DATE('now', 'localtime')"
            elif period == "week":
                date_filter = "g.created_at >= datetime('now', '-7 days', 'localtime')"
            elif period == "month":
                date_filter = "g.created_at >= datetime('now', '-30 days', 'localtime')"
            else:  # all
                date_filter = "1=1"
            
            query = f"""
                SELECT 
                    g.user_id,
                    u.username,
                    COALESCE(SUM(g.bet), 0) as turnover
                FROM games g
                LEFT JOIN users u ON g.user_id = u.user_id
                WHERE {date_filter} AND (g.currency IS NULL OR g.currency != 'arbuzz')
                GROUP BY g.user_id
                ORDER BY turnover DESC
                LIMIT ?
            """
            
            async with db.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_user_turnover_position(self, user_id: int, period: str = "all") -> int:
        """Получить позицию пользователя в топе по обороту
        
        Args:
            user_id: ID пользователя
            period: "day", "week", или "all"
        
        Returns:
            Позиция в топе (начиная с 1)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Определяем условие для периода
            if period == "day":
                date_filter = "DATE(created_at) = DATE('now', 'localtime')"
            elif period == "week":
                date_filter = "created_at >= datetime('now', '-7 days', 'localtime')"
            elif period == "month":
                date_filter = "created_at >= datetime('now', '-30 days', 'localtime')"
            else:  # all
                date_filter = "1=1"
            
            # Получаем оборот пользователя (исключая арбуз коины)
            async with db.execute(
                f"""
                SELECT COALESCE(SUM(bet), 0) as turnover
                FROM games
                WHERE user_id = ? AND {date_filter} AND (currency IS NULL OR currency != 'arbuzz')
                """,
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                user_turnover = row[0] if row else 0
            
            # Считаем сколько пользователей имеют больший оборот (исключая арбуз коины)
            async with db.execute(
                f"""
                SELECT COUNT(*) + 1 as position
                FROM (
                    SELECT user_id, SUM(bet) as turnover
                    FROM games
                    WHERE user_id != ? AND {date_filter} AND (currency IS NULL OR currency != 'arbuzz')
                    GROUP BY user_id
                    HAVING SUM(bet) > ?
                )
                """,
                (user_id, user_turnover)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1
    
    async def get_user_turnover(self, user_id: int, period: str = "all") -> float:
        """Получить оборот пользователя (сумма всех ставок)
        
        Args:
            user_id: ID пользователя
            period: "day", "week", или "all"
        
        Returns:
            Оборот пользователя
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Определяем условие для периода
            if period == "day":
                date_filter = "DATE(created_at) = DATE('now', 'localtime')"
            elif period == "week":
                date_filter = "created_at >= datetime('now', '-7 days', 'localtime')"
            elif period == "month":
                date_filter = "created_at >= datetime('now', '-30 days', 'localtime')"
            else:  # all
                date_filter = "1=1"
            
            async with db.execute(
                f"""
                SELECT COALESCE(SUM(bet), 0) as turnover
                FROM games
                WHERE user_id = ? AND {date_filter} AND (currency IS NULL OR currency != 'arbuzz')
                """,
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0.0

    async def get_user_favorite_game(self, user_id: int) -> Optional[str]:
        """Получить любимую игру пользователя (самая часто играемая)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT game_type, COUNT(*) as count 
                   FROM games 
                   WHERE user_id = ? 
                   GROUP BY game_type 
                   ORDER BY count DESC 
                   LIMIT 1""",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    game_emojis = {
                        "dice": "🎲",
                        "dart": "🎯",
                        "bowling": "🎳",
                        "football": "⚽",
                        "basketball": "🏀",
                        "slots": "🎰"
                    }
                    game_type = row[0]
                    emoji = game_emojis.get(game_type, "🎮")
                    return emoji * 3
                return "🎲🎲🎲"  # По умолчанию

    async def add_deposit(self, user_id: int, amount: float, method: str):
        """Добавить запись о депозите"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO deposits (user_id, amount, method)
                   VALUES (?, ?, ?)""",
                (user_id, amount, method),
            )
            await db.commit()

    async def add_deposit_with_status(self, user_id: int, amount: float, method: str, status: str = "pending"):
        """Добавить запись о депозите с произвольным статусом"""
        async with aiosqlite.connect(self.db_path) as db:
            # Обновление схемы: создаем таблицу для защиты от дублей по tx_hash
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chain_payments (
                    tx_hash TEXT PRIMARY KEY,
                    user_id INTEGER,
                    amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(
                """INSERT INTO deposits (user_id, amount, method, status)
                   VALUES (?, ?, ?, ?)""",
                (user_id, amount, method, status),
            )
            await db.commit()

    async def is_chain_payment_new(self, tx_hash: str) -> bool:
        """Проверить, что tx_hash еще не зафиксирован"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM chain_payments WHERE tx_hash = ?",
                (tx_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is None

    async def save_chain_payment(self, tx_hash: str, user_id: int, amount: float):
        """Зафиксировать tx_hash, чтобы не было дублей"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO chain_payments (tx_hash, user_id, amount) VALUES (?, ?, ?)",
                (tx_hash, user_id, amount)
            )
            await db.commit()

    async def add_withdrawal(self, user_id: int, amount: float, method: str, gift_emoji: str = None, gift_name: str = None):
        """Добавить запись о выводе"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO withdrawals (user_id, amount, method, gift_emoji, gift_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, method, gift_emoji, gift_name),
            )
            await db.commit()

    async def get_user_total_deposits(self, user_id: int) -> float:
        """Получить общую сумму депозитов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM deposits WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0.0

    async def get_user_total_withdrawals(self, user_id: int) -> float:
        """Получить общую сумму выводов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM withdrawals WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0.0

    async def get_user_total_turnover(self, user_id: int) -> float:
        """Получить общий оборот пользователя (сумма всех ставок, исключая арбуз коины)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COALESCE(SUM(bet), 0) as total FROM games WHERE user_id = ? AND (currency IS NULL OR currency != 'arbuzz')",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0.0

    async def create_check(self, creator_id: int, check_code: str, total_activations: int, 
                          amount_per_activation: float, requires_captcha: bool, 
                          captcha_result: Optional[str] = None, image_url: Optional[str] = None,
                          text: Optional[str] = None, button_text: Optional[str] = None,
                          button_url: Optional[str] = None, rollover_multiplier: float = 1.0,
                          deposit_type: str = 'no_deposit', min_deposit: float = 0.0) -> int:
        """Создать чек"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO checks (check_code, creator_id, total_activations, remaining_activations,
                   amount_per_activation, requires_captcha, captcha_result, image_url, text, button_text, button_url,
                   rollover_multiplier, deposit_type, min_deposit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (check_code, creator_id, total_activations, total_activations, amount_per_activation,
                 requires_captcha, captcha_result, image_url, text, button_text, button_url,
                 rollover_multiplier, deposit_type, min_deposit)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_check(self, check_code: str) -> Optional[Dict]:
        """Получить чек по коду"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checks WHERE check_code = ?", (check_code,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def activate_check(self, check_id: int, user_id: int) -> bool:
        """Активировать чек для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, не активировал ли уже этот пользователь
            async with db.execute(
                "SELECT 1 FROM check_activations WHERE check_id = ? AND user_id = ?",
                (check_id, user_id)
            ) as cursor:
                if await cursor.fetchone():
                    return False  # Уже активировал
            
            # Проверяем, есть ли еще активации
            check = await self.get_check_by_id(check_id)
            if not check or check["remaining_activations"] <= 0:
                return False
            
            # Добавляем активацию
            await db.execute(
                "INSERT INTO check_activations (check_id, user_id) VALUES (?, ?)",
                (check_id, user_id)
            )
            
            # Уменьшаем количество оставшихся активаций
            await db.execute(
                "UPDATE checks SET remaining_activations = remaining_activations - 1 WHERE id = ?",
                (check_id,)
            )
            
            await db.commit()
            return True

    async def get_check_by_id(self, check_id: int) -> Optional[Dict]:
        """Получить чек по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checks WHERE id = ?", (check_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def has_user_activated_check(self, check_id: int, user_id: int) -> bool:
        """Проверить, активировал ли пользователь чек"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM check_activations WHERE check_id = ? AND user_id = ?",
                (check_id, user_id)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def get_checks_by_creator(self, creator_id: int, limit: int = 5) -> List[Dict]:
        """Получить список чеков пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM checks
                   WHERE creator_id = ?
                   ORDER BY id DESC
                   LIMIT ?""",
                (creator_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_check(self, check_code: str, creator_id: int) -> bool:
        """Удалить чек вместе с активациями"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checks WHERE check_code = ? AND creator_id = ?",
                (check_code, creator_id),
            ) as cursor:
                check = await cursor.fetchone()
            if not check:
                return False
            check_id = check["id"]
            await db.execute(
                "DELETE FROM check_activations WHERE check_id = ?",
                (check_id,),
            )
            await db.execute(
                "DELETE FROM checks WHERE id = ?",
                (check_id,),
            )
            await db.commit()
            return True

    async def search_users(self, query: str, limit: int = 5) -> List[Dict]:
        """Поиск пользователей по username или ID"""
        normalized = f"%{query.lower()}%"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM users
                   WHERE LOWER(COALESCE(username, '')) LIKE ?
                      OR CAST(user_id AS TEXT) LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (normalized, normalized, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_referral_count(self, user_id: int) -> int:
        """Получить количество рефералов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT COUNT(*) as count FROM users WHERE referred_by = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return row["count"] if row else 0

    async def process_referral_bonus(self, user_id: int, bet_amount: float, win_amount: float = 0.0) -> Optional[Dict]:
        """Начислить реферальный бонус рефералу за игру реферала
        
        Args:
            user_id: ID игрока (реферала)
            bet_amount: Сумма ставки игрока
            win_amount: Сумма выигрыша (0 если проиграл)
        
        Returns:
            dict с информацией о начисленном бонусе или None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Получаем информацию о игроке
            user = await self.get_user(user_id)
            if not user or not user.get("referred_by"):
                return None  # У пользователя нет реферала
            
            referrer_id = user["referred_by"]
            
            # Получаем информацию о реферале
            referrer = await self.get_user(referrer_id)
            if not referrer:
                return None
            
            # Проверяем, является ли реферал партнером
            partner = await self.get_partner(referrer_id)
            is_partner = partner is not None
            
            # Определяем процент и условие начисления:
            # - Партнер: процент из базы данных только с проигрышей (win_amount == 0)
            # - Обычный пользователь: 5% только с проигрышей (win_amount == 0)
            if is_partner:
                referrer_percent = partner.get("referral_percent", 8.0)
            else:
                referrer_percent = 5.0
            
            # И партнеры, и обычные пользователи получают только с проигрышей
            should_credit = (win_amount == 0.0)
            
            if not should_credit:
                return None  # Не начисляем бонус
            
            # Вычисляем бонус (процент от ставки)
            bonus = bet_amount * (referrer_percent / 100)
            
            # Обновляем объем и заработок реферала
            # ВАЖНО: Деньги начисляются ВСЕГДА, независимо от настроек уведомлений!
            await db.execute(
                """UPDATE users 
                   SET total_volume = total_volume + ?, 
                       total_earned = total_earned + ?,
                       referral_balance = referral_balance + ?
                   WHERE user_id = ?""",
                (bet_amount, bonus, bonus, referrer_id),
            )
            await db.commit()
            
            # Логируем начисление
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Реферальный бонус зачислен в referral_balance: ${bonus:.2f} для пользователя {referrer_id} (независимо от уведомлений)")
            
            # Проверяем, включены ли уведомления о рефералах (только для отправки сообщения, НЕ для начисления!)
            send_notification = referrer.get("referral_notifications", True)
            
            # Получаем обновленную информацию о реферале
            updated_referrer = await self.get_user(referrer_id)
            
            return {
                "referrer_id": referrer_id,
                "bonus": bonus,
                "old_level": 0,
                "new_level": 0,
                "old_percent": referrer_percent,
                "new_percent": referrer_percent,
                "bet_amount": bet_amount,
                "send_notification": send_notification,
                "total_volume": updated_referrer["total_volume"],
                "total_earned": updated_referrer["total_earned"],
                "is_partner": is_partner
            }

    async def create_promo_code(self, code: str, amount: float, total_activations: int, 
                                requires_channel_subscription: bool, created_by: int,
                                channel_username: str = None, activation_link: str = None,
                                rollover_multiplier: float = 1.0, deposit_type: str = 'no_deposit',
                                min_deposit: float = 0.0) -> int:
        """Создать промокод"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO promo_codes (code, amount, total_activations, remaining_activations,
                   requires_channel_subscription, channel_username, created_by, activation_link,
                   rollover_multiplier, deposit_type, min_deposit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, amount, total_activations, total_activations, requires_channel_subscription, channel_username, created_by, activation_link,
                 rollover_multiplier, deposit_type, min_deposit)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_promo_code(self, code: str) -> Optional[Dict]:
        """Получить промокод по коду"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM promo_codes WHERE code = ?", (code,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def activate_promo_code(self, promo_id: int, user_id: int) -> bool:
        """Активировать промокод для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, не активировал ли уже этот пользователь
            async with db.execute(
                "SELECT 1 FROM promo_activations WHERE promo_id = ? AND user_id = ?",
                (promo_id, user_id)
            ) as cursor:
                if await cursor.fetchone():
                    return False  # Уже активировал
            
            # Проверяем, есть ли еще активации
            promo = await self.get_promo_code_by_id(promo_id)
            if not promo or promo["remaining_activations"] <= 0:
                return False
            
            # Добавляем активацию
            await db.execute(
                "INSERT INTO promo_activations (promo_id, user_id) VALUES (?, ?)",
                (promo_id, user_id)
            )
            
            # Уменьшаем количество оставшихся активаций
            await db.execute(
                "UPDATE promo_codes SET remaining_activations = remaining_activations - 1 WHERE id = ?",
                (promo_id,)
            )
            
            await db.commit()
            return True

    async def get_promo_code_by_id(self, promo_id: int) -> Optional[Dict]:
        """Получить промокод по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM promo_codes WHERE id = ?", (promo_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def has_user_activated_promo(self, promo_id: int, user_id: int) -> bool:
        """Проверить, активировал ли пользователь промокод"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT 1 FROM promo_activations WHERE promo_id = ? AND user_id = ?",
                (promo_id, user_id)
            ) as cursor:
                return await cursor.fetchone() is not None

    async def get_all_promo_codes(self) -> List[Dict]:
        """Получить все промокоды"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM promo_codes
                   ORDER BY created_at DESC"""
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_promo_code(self, promo_id: int) -> bool:
        """Удалить промокод"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))
            await db.commit()
            return True

    async def update_promo_code(self, promo_id: int, code: str = None, amount: float = None, 
                                total_activations: int = None, requires_channel_subscription: bool = None,
                                channel_username: str = None) -> bool:
        """Обновить промокод"""
        async with aiosqlite.connect(self.db_path) as db:
            updates = []
            params = []
            
            if code is not None:
                updates.append("code = ?")
                params.append(code)
            if amount is not None:
                updates.append("amount = ?")
                params.append(amount)
            if total_activations is not None:
                updates.append("total_activations = ?")
                params.append(total_activations)
                # Также обновляем remaining_activations если нужно
                promo = await self.get_promo_code_by_id(promo_id)
                if promo:
                    used = promo['total_activations'] - promo['remaining_activations']
                    new_remaining = max(0, total_activations - used)
                    updates.append("remaining_activations = ?")
                    params.append(new_remaining)
            if requires_channel_subscription is not None:
                updates.append("requires_channel_subscription = ?")
                params.append(1 if requires_channel_subscription else 0)
            if channel_username is not None:
                updates.append("channel_username = ?")
                params.append(channel_username)
            
            if not updates:
                return False
            
            params.append(promo_id)
            query = f"UPDATE promo_codes SET {', '.join(updates)} WHERE id = ?"
            await db.execute(query, params)
            await db.commit()
            return True

    async def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_deposits(self) -> List[Dict]:
        """Получить все депозиты"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deposits ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_withdrawals(self) -> List[Dict]:
        """Получить все выводы"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM withdrawals ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_games(self) -> List[Dict]:
        """Получить все игры"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM games ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_deposits_by_date_range(self, start_date, end_date) -> List[Dict]:
        """Получить депозиты за период"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM deposits WHERE created_at >= ? AND created_at <= ? ORDER BY created_at ASC",
                (start_date.isoformat(), end_date.isoformat())
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_withdrawals_by_date_range(self, start_date, end_date) -> List[Dict]:
        """Получить выводы за период"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM withdrawals WHERE created_at >= ? AND created_at <= ? ORDER BY created_at ASC",
                (start_date.isoformat(), end_date.isoformat())
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ПОДАРКАМИ РЕЛАЕРА ====================
    
    async def add_relay_gift(self, message_id: int, emoji: str, gift_name: str = None, 
                           gift_id: int = None, slug: str = None, gift_date: int = None,
                           from_user_id: int = None, from_username: str = None) -> bool:
        """Добавить или обновить подарок релаера в базе данных"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Сначала проверяем, существует ли запись
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT is_available FROM relay_gifts WHERE message_id = ?", 
                    (message_id,)
                ) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # Если запись существует и доступна, обновляем её
                    if existing["is_available"] == 1:
                        await db.execute("""
                            UPDATE relay_gifts 
                            SET emoji = ?, gift_name = ?, gift_id = ?, slug = ?, 
                                gift_date = ?, from_user_id = ?, from_username = ?
                            WHERE message_id = ? AND is_available = 1
                        """, (emoji, gift_name, gift_id, slug, gift_date, from_user_id, from_username, message_id))
                    # Если подарок уже передан, не обновляем
                else:
                    # Если записи нет, вставляем новую
                    await db.execute("""
                        INSERT INTO relay_gifts 
                        (message_id, emoji, gift_name, gift_id, slug, gift_date, from_user_id, from_username, is_available)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (message_id, emoji, gift_name, gift_id, slug, gift_date, from_user_id, from_username))
                
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении подарка релаера: {e}")
                return False
    
    async def get_available_relay_gift(self, emoji: str = None, gift_name: str = None, slug: str = None) -> Optional[Dict]:
        """Получить доступный подарок релаера по эмодзи, имени или slug (приоритет по названию)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # ПРИОРИТЕТ 1: Ищем сначала по названию (точное совпадение)
            if gift_name:
                async with db.execute("""
                    SELECT * FROM relay_gifts 
                    WHERE gift_name = ? AND is_available = 1 
                    AND gift_name IS NOT NULL AND gift_name != ''
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (gift_name,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            
            # ПРИОРИТЕТ 2: Ищем по названию (частичное совпадение, case-insensitive)
            if gift_name:
                async with db.execute("""
                    SELECT * FROM relay_gifts 
                    WHERE LOWER(gift_name) LIKE LOWER(?) AND is_available = 1 
                    AND gift_name IS NOT NULL AND gift_name != ''
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (f"%{gift_name}%",)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            
            # ПРИОРИТЕТ 3: Ищем по slug (если указан)
            if slug:
                async with db.execute("""
                    SELECT * FROM relay_gifts 
                    WHERE slug = ? AND is_available = 1 
                    AND slug IS NOT NULL AND slug != ''
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (slug,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            
            # ПРИОРИТЕТ 4: Ищем по эмодзи (если указано)
            if emoji:
                async with db.execute("""
                    SELECT * FROM relay_gifts 
                    WHERE emoji = ? AND is_available = 1 
                    AND emoji != '' AND emoji IS NOT NULL
                    AND gift_name IS NOT NULL AND gift_name != ''
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (emoji,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            
            return None
    
    async def mark_gift_as_transferred(self, message_id: int, user_id: int) -> bool:
        """Отметить подарок как переданный пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    UPDATE relay_gifts 
                    SET is_available = 0, transferred_to = ?, transferred_at = CURRENT_TIMESTAMP
                    WHERE message_id = ?
                """, (user_id, message_id))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при отметке подарка как переданного: {e}")
                return False
    
    async def get_relay_gifts_count(self, emoji: str = None) -> int:
        """Получить количество доступных подарков релаера (опционально по эмодзи)"""
        async with aiosqlite.connect(self.db_path) as db:
            if emoji:
                async with db.execute("""
                    SELECT COUNT(*) as count FROM relay_gifts 
                    WHERE emoji = ? AND is_available = 1
                """, (emoji,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
            else:
                async with db.execute("""
                    SELECT COUNT(*) as count FROM relay_gifts 
                    WHERE is_available = 1
                """) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
    
    async def clear_unavailable_gifts(self, available_message_ids: List[int]) -> int:
        """Очистить подарки, которых больше нет в профиле релеера"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                if not available_message_ids:
                    # Если список пуст, не удаляем ничего (может быть ошибка синхронизации)
                    return 0
                
                # Формируем плейсхолдеры для IN запроса
                placeholders = ','.join('?' * len(available_message_ids))
                
                # Удаляем подарки, которых нет в списке доступных (и которые еще не переданы)
                # Не удаляем переданные подарки, так как они могут быть нужны для истории
                cursor = await db.execute(f"""
                    DELETE FROM relay_gifts 
                    WHERE message_id NOT IN ({placeholders}) 
                    AND is_available = 1
                """, available_message_ids)
                
                deleted_count = cursor.rowcount
                await db.commit()
                return deleted_count
            except Exception as e:
                logger.error(f"Ошибка при очистке недоступных подарков: {e}")
                return 0
    
    async def get_all_relay_gifts(self, emoji: str = None, include_transferred: bool = False) -> List[Dict]:
        """Получить все подарки релаера из базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if emoji:
                if include_transferred:
                    async with db.execute("""
                        SELECT * FROM relay_gifts 
                        WHERE emoji = ?
                        ORDER BY created_at DESC
                    """, (emoji,)) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
                else:
                    async with db.execute("""
                        SELECT * FROM relay_gifts 
                        WHERE emoji = ? AND is_available = 1
                        ORDER BY created_at DESC
                    """, (emoji,)) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
            else:
                if include_transferred:
                    async with db.execute("""
                        SELECT * FROM relay_gifts 
                        ORDER BY created_at DESC
                    """) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
                else:
                    async with db.execute("""
                        SELECT * FROM relay_gifts 
                        WHERE is_available = 1
                        ORDER BY created_at DESC
                    """) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ПОДДЕРЖКОЙ ====================
    
    async def create_support_message(self, user_id: int, username: str, message_text: str) -> int:
        """Создать сообщение поддержки от пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO support_messages (user_id, username, message_text)
                VALUES (?, ?, ?)
            """, (user_id, username, message_text))
            await db.commit()
            return cursor.lastrowid
    
    async def get_support_message(self, message_id: int) -> Optional[Dict]:
        """Получить сообщение поддержки по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM support_messages WHERE id = ?", (message_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_unreplied_support_messages(self) -> List[Dict]:
        """Получить все неотвеченные сообщения поддержки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM support_messages 
                WHERE replied_to IS NULL
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def reply_to_support_message(self, message_id: int, reply_text: str, admin_id: int) -> bool:
        """Ответить на сообщение поддержки"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE support_messages 
                SET replied_to = ?, reply_text = ?, replied_at = CURRENT_TIMESTAMP, replied_by = ?
                WHERE id = ?
            """, (message_id, reply_text, admin_id, message_id))
            await db.commit()
            return True

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С PvP ДУЭЛЯМИ ====================
    
    async def create_pvp_duel(self, creator_id: int, game_type: str, max_players: int, bet_amount: float, unique_link: str, duel_id: int = None, 
                              duel_mode: str = "standard", min_bet: float = 0.0, max_bet: float = 0.0, auto_start_players: int = 0) -> int:
        """Создать PvP дуэль
        
        Args:
            creator_id: ID создателя
            game_type: Тип игры
            max_players: Максимальное количество игроков
            bet_amount: Ставка (для стандартного режима) или минимальная ставка (для slot_tournament)
            unique_link: Уникальная ссылка
            duel_id: ID дуэли (опционально)
            duel_mode: Режим дуэли ('standard' или 'slot_tournament')
            min_bet: Минимальная ставка (для slot_tournament)
            max_bet: Максимальная ставка (для slot_tournament)
            auto_start_players: Количество игроков для автозапуска (0 = по max_players)
        """
        async with aiosqlite.connect(self.db_path) as db:
            if duel_id:
                # Создаем дуэль с указанным ID
                await db.execute("""
                    INSERT INTO pvp_duels (id, creator_id, game_type, max_players, bet_amount, unique_link, status, total_pot, 
                                         duel_mode, min_bet, max_bet, auto_start_players)
                    VALUES (?, ?, ?, ?, ?, ?, 'waiting', ?, ?, ?, ?, ?)
                """, (duel_id, creator_id, game_type, max_players, bet_amount, unique_link, 
                      bet_amount if duel_mode == "standard" else 0.0, duel_mode, min_bet, max_bet, auto_start_players))
                await db.commit()
                created_duel_id = duel_id
            else:
                # Создаем дуэль с автоматическим ID
                cursor = await db.execute("""
                    INSERT INTO pvp_duels (creator_id, game_type, max_players, bet_amount, unique_link, status, total_pot,
                                         duel_mode, min_bet, max_bet, auto_start_players)
                    VALUES (?, ?, ?, ?, ?, 'waiting', ?, ?, ?, ?, ?)
                """, (creator_id, game_type, max_players, bet_amount, unique_link,
                      bet_amount if duel_mode == "standard" else 0.0, duel_mode, min_bet, max_bet, auto_start_players))
                await db.commit()
                created_duel_id = cursor.lastrowid
            
            # Добавляем создателя как первого участника (только если это не системный пользователь)
            if creator_id != 0:
                # Для slot_tournament создатель не добавляется автоматически (он должен поставить ставку)
                if duel_mode == "standard":
                    await db.execute("""
                        INSERT INTO pvp_participants (duel_id, user_id, position, bet_amount)
                        VALUES (?, ?, 1, ?)
                    """, (created_duel_id, creator_id, bet_amount))
                    await db.commit()
            
            return created_duel_id
    
    async def get_pvp_duel(self, duel_id: int = None, unique_link: str = None) -> Optional[Dict]:
        """Получить PvP дуэль по ID или ссылке"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if duel_id:
                async with db.execute(
                    "SELECT * FROM pvp_duels WHERE id = ?", (duel_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
            elif unique_link:
                async with db.execute(
                    "SELECT * FROM pvp_duels WHERE unique_link = ?", (unique_link,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None
            return None
    
    async def get_pvp_participants(self, duel_id: int) -> List[Dict]:
        """Получить список участников дуэли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT p.*, u.username 
                FROM pvp_participants p
                LEFT JOIN users u ON p.user_id = u.user_id
                WHERE p.duel_id = ?
                ORDER BY p.position ASC
            """, (duel_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def join_pvp_duel(self, duel_id: int, user_id: int, bet_amount: float = None) -> bool:
        """Присоединиться к PvP дуэли
        
        Args:
            duel_id: ID дуэли
            user_id: ID пользователя
            bet_amount: Ставка (для slot_tournament режима, опционально)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, не присоединился ли уже
            async with db.execute(
                "SELECT 1 FROM pvp_participants WHERE duel_id = ? AND user_id = ?",
                (duel_id, user_id)
            ) as cursor:
                if await cursor.fetchone():
                    return False  # Уже присоединился
            
            # Получаем информацию о дуэли
            duel = await self.get_pvp_duel(duel_id=duel_id)
            if not duel:
                return False
            
            # Определяем ставку
            duel_mode = duel.get("duel_mode", "standard")
            if duel_mode == "slot_tournament":
                if bet_amount is None:
                    return False  # Для slot_tournament ставка обязательна
                # Проверяем лимиты ставки
                min_bet = duel.get("min_bet", 0.0)
                max_bet = duel.get("max_bet", 0.0)
                if min_bet > 0 and bet_amount < min_bet:
                    return False
                if max_bet > 0 and bet_amount > max_bet:
                    return False
                actual_bet = bet_amount
            else:
                actual_bet = duel["bet_amount"]
            
            # Проверяем, есть ли еще место
            participants = await self.get_pvp_participants(duel_id)
            if len(participants) >= duel["max_players"]:
                return False
            
            # Проверяем статус
            if duel["status"] != "waiting":
                return False
            
            # Добавляем участника
            position = len(participants) + 1
            await db.execute("""
                INSERT INTO pvp_participants (duel_id, user_id, position, bet_amount)
                VALUES (?, ?, ?, ?)
            """, (duel_id, user_id, position, actual_bet))
            
            # Обновляем общий банк
            await db.execute("""
                UPDATE pvp_duels SET total_pot = total_pot + ? WHERE id = ?
            """, (actual_bet, duel_id))
            
            await db.commit()
            
            # Проверяем, заполнилась ли дуэль или достигнут лимит для автозапуска
            participants = await self.get_pvp_participants(duel_id)
            auto_start_players = duel.get("auto_start_players", 0)
            if auto_start_players > 0:
                # Автозапуск при достижении определенного количества игроков
                if len(participants) >= auto_start_players:
                    await db.execute("""
                        UPDATE pvp_duels SET status = 'ready', started_at = CURRENT_TIMESTAMP WHERE id = ?
                    """, (duel_id,))
                    await db.commit()
            elif len(participants) >= duel["max_players"]:
                await db.execute("""
                    UPDATE pvp_duels SET status = 'ready', started_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (duel_id,))
                await db.commit()
            
            return True
    
    async def cancel_pvp_duel(self, duel_id: int, creator_id: int) -> bool:
        """Отменить PvP дуэль (только создатель)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, что это создатель
            duel = await self.get_pvp_duel(duel_id=duel_id)
            if not duel or duel["creator_id"] != creator_id:
                return False
            
            # Проверяем, что дуэль еще не началась
            if duel["status"] not in ["waiting", "ready"]:
                return False
            
            # Отменяем дуэль
            await db.execute("""
                UPDATE pvp_duels SET status = 'cancelled', finished_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (duel_id,))
            await db.commit()
            return True
    
    async def start_pvp_duel(self, duel_id: int, channel_message_id: int) -> bool:
        """Начать PvP дуэль"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE pvp_duels SET status = 'active', channel_message_id = ? WHERE id = ?
            """, (channel_message_id, duel_id))
            await db.commit()
            return True
    
    async def finish_pvp_duel(self, duel_id: int, winner_id: int) -> bool:
        """Завершить PvP дуэль с победителем"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE pvp_duels SET status = 'finished', winner_id = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?
            """, (winner_id, duel_id))
            await db.commit()
            return True
    
    async def update_participant_result(self, duel_id: int, user_id: int, dice_result: int, dice_emoji: str) -> bool:
        """Обновить результат участника"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE pvp_participants SET dice_result = ?, dice_emoji = ? WHERE duel_id = ? AND user_id = ?
            """, (dice_result, dice_emoji, duel_id, user_id))
            await db.commit()
            return True
    
    async def get_user_pvp_duels(self, user_id: int, status: str = None) -> List[Dict]:
        """Получить дуэли пользователя (созданные или в которых участвует)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                async with db.execute("""
                    SELECT DISTINCT d.* FROM pvp_duels d
                    LEFT JOIN pvp_participants p ON d.id = p.duel_id
                    WHERE (d.creator_id = ? OR p.user_id = ?) AND d.status = ?
                    ORDER BY d.created_at DESC
                """, (user_id, user_id, status)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
            else:
                async with db.execute("""
                    SELECT DISTINCT d.* FROM pvp_duels d
                    LEFT JOIN pvp_participants p ON d.id = p.duel_id
                    WHERE d.creator_id = ? OR p.user_id = ?
                    ORDER BY d.created_at DESC
                """, (user_id, user_id)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
    
    async def get_active_pvp_duels(self) -> List[Dict]:
        """Получить активные дуэли (ожидающие присоединения)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT d.*, COUNT(p.id) as current_players
                FROM pvp_duels d
                LEFT JOIN pvp_participants p ON d.id = p.duel_id
                WHERE d.status IN ('waiting', 'ready')
                GROUP BY d.id
                ORDER BY d.created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С БИЛЕТАМИ PvP #500 ====================
    
    async def get_pvp_tickets_count(self, duel_id: int) -> int:
        """Получить количество проданных билетов для дуэли"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) as count FROM pvp_tickets WHERE duel_id = ?",
                (duel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def get_pvp_tickets(self, duel_id: int) -> List[Dict]:
        """Получить все билеты для дуэли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT t.*, u.username 
                FROM pvp_tickets t
                LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.duel_id = ?
                ORDER BY t.ticket_position ASC
            """, (duel_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def add_pvp_tickets(self, duel_id: int, user_id: int, amount: float, ticket_positions: List[int]) -> bool:
        """Добавить билеты для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            for position in ticket_positions:
                await db.execute("""
                    INSERT INTO pvp_tickets (duel_id, user_id, ticket_position, amount)
                    VALUES (?, ?, ?, ?)
                """, (duel_id, user_id, position, amount / len(ticket_positions)))
            await db.commit()
            return True
    
    async def get_user_tickets_count(self, duel_id: int, user_id: int) -> int:
        """Получить количество билетов пользователя в дуэли"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) as count FROM pvp_tickets WHERE duel_id = ? AND user_id = ?",
                (duel_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def get_ticket_owner(self, duel_id: int, ticket_position: int) -> Optional[Dict]:
        """Получить владельца билета по позиции"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT t.*, u.username 
                FROM pvp_tickets t
                LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.duel_id = ? AND t.ticket_position = ?
            """, (duel_id, ticket_position)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ЧАТАМИ ====================
    
    async def add_or_update_chat(self, chat_id: int, chat_type: str, title: str = None, 
                                 username: str = None, invite_link: str = None, 
                                 bot_is_admin: bool = True):
        """Добавить или обновить информацию о чате"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли чат
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT chat_id FROM chats WHERE chat_id = ?", (chat_id,)
            ) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                # Обновляем существующий чат
                await db.execute("""
                    UPDATE chats 
                    SET chat_type = ?, title = ?, username = ?, invite_link = ?, 
                        bot_is_admin = ?, bot_added_at = COALESCE(bot_added_at, CURRENT_TIMESTAMP)
                    WHERE chat_id = ?
                """, (chat_type, title, username, invite_link, 1 if bot_is_admin else 0, chat_id))
            else:
                # Создаем новый чат
                await db.execute("""
                    INSERT INTO chats (chat_id, chat_type, title, username, invite_link, bot_is_admin)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chat_id, chat_type, title, username, invite_link, 1 if bot_is_admin else 0))
            await db.commit()
    
    async def increment_chat_messages(self, chat_id: int):
        """Увеличить счетчик сообщений от бота в чате"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE chats 
                SET messages_count = messages_count + 1, 
                    last_message_at = CURRENT_TIMESTAMP
                WHERE chat_id = ?
            """, (chat_id,))
            await db.commit()
    
    async def get_all_chats(self) -> List[Dict]:
        """Получить все чаты где бот является администратором"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM chats 
                WHERE bot_is_admin = 1
                ORDER BY bot_added_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_chat(self, chat_id: int) -> Optional[Dict]:
        """Получить информацию о чате"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM chats WHERE chat_id = ?", (chat_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def update_user_total_lost(self, user_id: int, amount: float):
        """Увеличить сумму проигранных средств пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET total_lost = total_lost + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С АРБУЗЗ КОИНАМИ ====================
    
    async def get_arbuzz_balance(self, user_id: int) -> float:
        """Получить баланс арбузз коинов пользователя"""
        user = await self.get_user(user_id)
        return user.get("arbuzz_balance", 0.0) if user else 0.0
    
    async def update_arbuzz_balance(self, user_id: int, amount: float):
        """Обновить баланс арбузз коинов пользователя (положительное значение - пополнение, отрицательное - списание)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET arbuzz_balance = arbuzz_balance + ? WHERE user_id = ?",
                (amount, user_id),
            )
            await db.commit()
            logger.info(f"💰 Арбузз коины: user_id={user_id}, сумма={amount:+.2f}")
    
    async def check_and_give_daily_arbuzz(self, user_id: int) -> bool:
        """Проверить и выдать ежедневные 100 арбузз коинов (если еще не выданы сегодня)"""
        async with aiosqlite.connect(self.db_path) as db:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            user = await self.get_user(user_id)
            if not user:
                return False
            
            last_date = user.get("last_daily_arbuzz_date")
            
            if last_date != today:
                # Выдаем ежедневные 100 арбузз коинов
                await db.execute(
                    "UPDATE users SET arbuzz_balance = arbuzz_balance + 100, last_daily_arbuzz_date = ? WHERE user_id = ?",
                    (today, user_id),
                )
                await db.commit()
                logger.info(f"🎁 Ежедневные 100 арбузз коинов выданы пользователю {user_id}")
                return True
            return False
    
    async def check_and_give_first_win_arbuzz(self, user_id: int, bet_type: str) -> bool:
        """Проверить и выдать 1000 арбузз коинов за первую победу в день (только если победа на $)"""
        if bet_type != "dollar":  # Только для побед на доллары
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            user = await self.get_user(user_id)
            if not user:
                return False
            
            last_win_date = user.get("last_win_date")
            first_win_today = user.get("first_win_today_arbuzz", False)
            
            # Если это новый день или еще не было победы сегодня
            if last_win_date != today or not first_win_today:
                # Выдаем 1000 арбузз коинов за первую победу
                await db.execute(
                    "UPDATE users SET arbuzz_balance = arbuzz_balance + 1000, first_win_today_arbuzz = 1, last_win_date = ? WHERE user_id = ?",
                    (today, user_id),
                )
                await db.commit()
                logger.info(f"🎉 1000 арбузз коинов за первую победу в день выданы пользователю {user_id}")
                return True
            return False
    
    async def reset_daily_win_flag(self, user_id: int):
        """Сбросить флаг первой победы в день (вызывается при смене дня)"""
        async with aiosqlite.connect(self.db_path) as db:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            
            user = await self.get_user(user_id)
            if not user:
                return
            
            last_win_date = user.get("last_win_date")
            
            # Если это новый день, сбрасываем флаг
            if last_win_date != today:
                await db.execute(
                    "UPDATE users SET first_win_today_arbuzz = 0 WHERE user_id = ?",
                    (user_id,),
                )
                await db.commit()

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ЛОТЕРЕЯМИ ====================
    
    async def create_lottery(self, title: str, description: str, ticket_price: float, 
                            max_tickets_per_user: int, finish_type: str, created_by: int,
                            finish_value: str = None, finish_datetime: str = None, 
                            finish_participants: int = None) -> int:
        """Создать лотерею"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO lotteries (title, description, ticket_price, max_tickets_per_user,
                    finish_type, finish_value, finish_datetime, finish_participants, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, description, ticket_price, max_tickets_per_user, finish_type, 
                  finish_value, finish_datetime, finish_participants, created_by))
            await db.commit()
            return cursor.lastrowid
    
    async def add_lottery_prize(self, lottery_id: int, position: int, prize_type: str, 
                               prize_value: str, prize_description: str = None) -> bool:
        """Добавить приз для определенного места в лотерее"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO lottery_prizes 
                    (lottery_id, position, prize_type, prize_value, prize_description)
                    VALUES (?, ?, ?, ?, ?)
                """, (lottery_id, position, prize_type, prize_value, prize_description))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении приза лотереи: {e}")
                return False
    
    async def get_lottery(self, lottery_id: int) -> Optional[Dict]:
        """Получить информацию о лотерее"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM lotteries WHERE id = ?", (lottery_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_active_lotteries(self) -> List[Dict]:
        """Получить все активные лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM lotteries 
                WHERE status = 'active'
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_lottery_prizes(self, lottery_id: int) -> List[Dict]:
        """Получить все призы лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM lottery_prizes 
                WHERE lottery_id = ?
                ORDER BY position ASC
            """, (lottery_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def buy_lottery_ticket(self, lottery_id: int, user_id: int) -> Optional[int]:
        """Купить билет лотереи. Возвращает номер билета или None при ошибке"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем лотерею
            lottery = await self.get_lottery(lottery_id)
            if not lottery or lottery["status"] != "active":
                return None
            
            # Проверяем лимит билетов на пользователя
            user_tickets = await self.get_user_lottery_tickets_count(lottery_id, user_id)
            if user_tickets >= lottery["max_tickets_per_user"]:
                return None
            
            # Проверяем баланс
            user = await self.get_user(user_id)
            if not user or user["balance"] < lottery["ticket_price"]:
                return None
            
            # Списываем средства
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (lottery["ticket_price"], user_id)
            )
            
            # Генерируем номер билета (следующий доступный)
            next_ticket_number = lottery["total_tickets"] + 1
            
            # Добавляем билет
            await db.execute("""
                INSERT INTO lottery_tickets (lottery_id, user_id, ticket_number)
                VALUES (?, ?, ?)
            """, (lottery_id, user_id, next_ticket_number))
            
            # Увеличиваем счетчик билетов
            await db.execute("""
                UPDATE lotteries SET total_tickets = total_tickets + 1 WHERE id = ?
            """, (lottery_id,))
            
            await db.commit()
            return next_ticket_number
    
    async def get_user_lottery_tickets_count(self, lottery_id: int, user_id: int) -> int:
        """Получить количество билетов пользователя в лотерее"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT COUNT(*) as count FROM lottery_tickets 
                WHERE lottery_id = ? AND user_id = ?
            """, (lottery_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def get_lottery_tickets(self, lottery_id: int) -> List[Dict]:
        """Получить все билеты лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT t.*, u.username 
                FROM lottery_tickets t
                LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.lottery_id = ?
                ORDER BY t.ticket_number ASC
            """, (lottery_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def finish_lottery(self, lottery_id: int) -> bool:
        """Завершить лотерею (изменить статус)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE lotteries 
                SET status = 'finished', finished_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (lottery_id,))
            await db.commit()
            return True
    
    async def add_lottery_winner(self, lottery_id: int, user_id: int, ticket_number: int,
                                prize_type: str, prize_value: str, prize_description: str,
                                position: int) -> bool:
        """Добавить победителя лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO lottery_winners 
                    (lottery_id, user_id, ticket_number, prize_type, prize_value, 
                     prize_description, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (lottery_id, user_id, ticket_number, prize_type, prize_value, 
                      prize_description, position))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при добавлении победителя лотереи: {e}")
                return False
    
    async def get_lottery_winners(self, lottery_id: int) -> List[Dict]:
        """Получить всех победителей лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT w.*, u.username 
                FROM lottery_winners w
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE w.lottery_id = ?
                ORDER BY w.position ASC
            """, (lottery_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_all_lotteries(self) -> List[Dict]:
        """Получить все лотереи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM lotteries 
                ORDER BY created_at DESC
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def delete_lottery(self, lottery_id: int) -> bool:
        """Удалить лотерею (только если нет билетов)"""
        async with aiosqlite.connect(self.db_path) as db:
            lottery = await self.get_lottery(lottery_id)
            if not lottery:
                return False
            
            if lottery["total_tickets"] > 0:
                return False  # Нельзя удалить лотерею с билетами
            
            await db.execute("DELETE FROM lottery_prizes WHERE lottery_id = ?", (lottery_id,))
            await db.execute("DELETE FROM lotteries WHERE id = ?", (lottery_id,))
            await db.commit()
            return True
    
    async def save_sticker(self, name: str, file_id: str, file_unique_id: str, sticker_type: Optional[str] = None) -> bool:
        """Сохранить стикер"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT OR REPLACE INTO stickers (name, file_id, file_unique_id, sticker_type)
                    VALUES (?, ?, ?, ?)
                """, (name, file_id, file_unique_id, sticker_type))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при сохранении стикера: {e}")
                return False
    
    async def get_sticker(self, name: str) -> Optional[Dict]:
        """Получить стикер по имени"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM stickers WHERE name = ?", (name,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def get_all_stickers(self, sticker_type: Optional[str] = None) -> List[Dict]:
        """Получить все стикеры или по типу"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if sticker_type:
                async with db.execute(
                    "SELECT * FROM stickers WHERE sticker_type = ? ORDER BY name", (sticker_type,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
            else:
                async with db.execute(
                    "SELECT * FROM stickers ORDER BY name"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
    
    async def delete_sticker(self, name: str) -> bool:
        """Удалить стикер"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("DELETE FROM stickers WHERE name = ?", (name,))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка при удалении стикера: {e}")
                return False

