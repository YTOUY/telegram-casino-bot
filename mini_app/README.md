# Telegram Mini App - ArbuzCasino

## Структура файлов

```
mini_app/
├── index.html      # Основной HTML файл
├── styles.css      # Стили приложения
├── app.js          # JavaScript логика
└── README.md       # Этот файл
```

## Установка и настройка

### 1. Размещение файлов

Загрузите файлы мини-приложения на ваш веб-сервер (например, через GitHub Pages, Vercel, или ваш собственный сервер).

### 2. Настройка URL

В файле `handlers/mini_app.py` замените `web_app_url` на ваш реальный URL:

```python
web_app_url = "https://your-domain.com/mini_app/index.html"
```

### 3. Настройка API endpoints

В файле `app.js` замените `API_BASE` на URL вашего API:

```javascript
const API_BASE = 'https://your-api-domain.com/api';
```

### 4. Создание API endpoints

Вам нужно создать следующие API endpoints на бэкенде:

#### GET `/api/user`
Возвращает данные пользователя
```json
{
  "balance": 100.00,
  "base_bet": 1.0,
  "referral_count": 5,
  "referral_balance": 10.50
}
```

#### GET `/api/sticker/welcome`
Возвращает приветственный стикер
```json
{
  "file_id": "CAACAgIAAxkBAA...",
  "file_url": "https://api.telegram.org/file/bot..."
}
```

#### GET `/api/stickers`
Возвращает все стикеры
```json
[
  {
    "name": "dice_1",
    "file_id": "CAACAgIAAxkBAA...",
    "file_unique_id": "AgAD..."
  }
]
```

#### POST `/api/game/start`
Запускает игру
```json
{
  "game_type": "dice",
  "bet": 1.0
}
```
Ответ:
```json
{
  "game_id": 123,
  "status": "started"
}
```

#### GET `/api/game/result/{game_id}`
Проверяет результат игры
```json
{
  "completed": true,
  "result": 5,
  "win": 5.55,
  "new_balance": 105.55
}
```

#### POST `/api/settings/base-bet`
Сохраняет базовую ставку
```json
{
  "base_bet": 2.0
}
```

#### POST `/api/check/create`
Создает чек
```json
{
  "amount": 10.0,
  "activations": 5,
  "text": "Привет!"
}
```

#### GET `/api/lotteries`
Возвращает список лотерей

#### POST `/api/lottery/participate`
Участие в лотерее
```json
{
  "lottery_id": 1
}
```

#### GET `/api/gifts`
Возвращает список подарков

#### GET `/api/top`
Возвращает топ игроков/чатов
Параметры: `category` (players/chats), `period` (day/month/all)

#### GET `/api/profile`
Возвращает данные профиля

### 5. Интеграция TON Connect

Для интеграции TON Connect добавьте в `app.js`:

```javascript
import { TonConnectUIProvider } from '@tonconnect/ui-react';

// В функции initTONConnect:
const tonConnectUI = new TonConnectUI({
    manifestUrl: 'https://your-domain.com/tonconnect-manifest.json'
});

tonConnectUI.openWallet();
```

Создайте файл `tonconnect-manifest.json`:

```json
{
  "url": "https://your-domain.com/mini_app/index.html",
  "name": "ArbuzCasino",
  "iconUrl": "https://your-domain.com/icon.png"
}
```

### 6. Аутентификация

Все запросы к API должны включать заголовок:
```
X-Telegram-Init-Data: <initData>
```

На бэкенде проверяйте подпись initData для безопасности.

## Использование команды /sticker

1. Отправьте `/sticker` боту
2. Отправьте стикеры (по одному)
3. Отправьте названия в формате:
```
1 welcome
2 dice_1
3 dice_2
...
```

Подробнее см. `STICKERS_GUIDE.md`

## Цветовая схема

- Фон: `#1a1a2e` (темно-синий)
- Карточки: `#0f1419` (черный)
- Навигация: `#000000` (черный)
- Акцент: `#00ff88` (зеленый)
- Текст: `#ffffff` (белый)
- Вторичный текст: `#888888` (серый)

## Особенности

- Адаптивный дизайн для мобильных устройств
- Интеграция с Telegram Web App API
- Поддержка TON Connect для платежей
- Анимации и переходы
- Модальные окна с размытием фона
- Toast уведомления

## Тестирование

1. Откройте бота в Telegram
2. Отправьте команду `/miniapp`
3. Нажмите кнопку "Открыть ArbuzCasino"
4. Мини-приложение откроется в Telegram

## Поддержка

При возникновении проблем проверьте:
- Правильность URL в настройках
- Доступность API endpoints
- Корректность сохранения стикеров
- Логи бота на наличие ошибок

