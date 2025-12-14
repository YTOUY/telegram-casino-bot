# Инструкция по развертыванию тестового бота

## Цель
Запустить тестовый бот для мини-аппа отдельно от основного бота на том же сервере.

## Преимущества
- ✅ Основной бот продолжает работать без изменений
- ✅ Отдельная база данных для тестов
- ✅ Отдельный API порт (8081)
- ✅ Обычные пользователи не видят мини-апп
- ✅ Можно тестировать без риска для основного бота

---

## Шаг 1: Подготовка

### 1.1. Создайте тестового бота через @BotFather

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Создайте нового бота (например: `ArbuzCasinoTestBot`)
4. Скопируйте токен бота (понадобится позже)

### 1.2. Подготовьте файлы на локальном компьютере

Убедитесь, что все файлы тестового бота находятся в папке `тг каз для 11`

---

## Шаг 2: Подключение к серверу

```bash
ssh root@141.8.198.144
```

Введите пароль при запросе.

---

## Шаг 3: Поиск основного бота

```bash
# Проверьте где запущен основной бот
ps aux | grep python | grep main.py

# Или проверьте systemd сервисы
systemctl list-units | grep telegram

# Или найдите папку с основным ботом
find /opt /home /root -name "main.py" -type f 2>/dev/null | grep -v venv
```

Обычно основной бот находится в `/opt/telegram_bot`

---

## Шаг 4: Создание папки для тестового бота

```bash
mkdir -p /opt/telegram_bot_test
cd /opt/telegram_bot_test
pwd
```

Должно показать: `/opt/telegram_bot_test`

---

## Шаг 5: Загрузка файлов на сервер

**На вашем локальном компьютере** (PowerShell, из папки `тг каз для 11`):

```powershell
scp -r * root@141.8.198.144:/opt/telegram_bot_test/
```

Дождитесь завершения загрузки (может занять несколько минут).

---

## Шаг 6: Проверка загруженных файлов

**На сервере:**

```bash
cd /opt/telegram_bot_test
ls -la
```

Должны быть видны файлы: `main.py`, `config.py`, `requirements.txt`, `api_server.py` и т.д.

---

## Шаг 7: Создание виртуального окружения

```bash
cd /opt/telegram_bot_test
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Это может занять несколько минут.

---

## Шаг 8: Настройка config.py

```bash
nano config.py
```

Измените:
- `BOT_TOKEN` - вставьте токен тестового бота (из шага 1.1)
- База данных будет автоматически создана как `database.db` в папке `/opt/telegram_bot_test/`

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Шаг 9: Изменение порта API в main.py

```bash
nano main.py
```

Найдите строку (около строки 240):
```python
api_port = int(os.getenv("API_PORT", "8080"))
```

Замените на:
```python
api_port = int(os.getenv("API_PORT", "8081"))  # Тестовый бот на порту 8081
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Шаг 10: Открытие порта 8081 в файрволе

```bash
# Проверьте статус файрвола
ufw status

# Откройте порт 8081
ufw allow 8081/tcp

# Перезагрузите файрвол
ufw reload

# Проверьте что порт открыт
ufw status | grep 8081
```

Должно показать что порт 8081 открыт.

---

## Шаг 11: Создание systemd сервиса

```bash
nano /etc/systemd/system/telegram-bot-test.service
```

Вставьте следующее содержимое:

```ini
[Unit]
Description=Telegram Bot Test Service (Mini App)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram_bot_test
Environment="PATH=/opt/telegram_bot_test/venv/bin"
ExecStart=/opt/telegram_bot_test/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Шаг 12: Запуск тестового бота

```bash
# Перезагрузите systemd
systemctl daemon-reload

# Включите автозапуск
systemctl enable telegram-bot-test

# Запустите бота
systemctl start telegram-bot-test

# Проверьте статус
systemctl status telegram-bot-test
```

Должно показать `active (running)`.

---

## Шаг 13: Проверка работы

### 13.1. Проверьте логи

```bash
journalctl -u telegram-bot-test -n 50
```

Ищите строки:
- `✅ API сервер запущен на порту 8081`
- `Бот запущен`
- Нет критических ошибок

### 13.2. Проверьте что порт слушается

```bash
ss -tlnp | grep 8081
```

Должен быть процесс, слушающий порт 8081.

### 13.3. Проверьте API (должна быть ошибка авторизации)

```bash
curl http://localhost:8081/api/user
```

Должна быть ошибка 401 (Unauthorized) - это нормально, значит API работает.

---

## Шаг 14: Настройка мини-аппа на Netlify

### 14.1. Обновите app.js

В файле `mini_app/app.js` убедитесь что:

```javascript
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    API_BASE = 'http://141.8.198.144:8081/api';
}
```

### 14.2. Разверните на Netlify

**Вариант А: Через веб-интерфейс**
1. Откройте https://app.netlify.com
2. Нажмите "Add new site" → "Deploy manually"
3. Перетащите папку `mini_app` в окно
4. Дождитесь завершения деплоя
5. Скопируйте URL (например: `https://arbuzcas.netlify.app`)

**Вариант Б: Через CLI**
```powershell
cd mini_app
netlify init  # Создайте новый сайт
netlify deploy --prod
```

---

## Шаг 15: Настройка мини-аппа в тестовом боте

### 15.1. Найдите где настраивается мини-апп

```bash
# На сервере
grep -r "web_app_url\|mini_app\|Mini App" /opt/telegram_bot_test/handlers/
```

Обычно это файл `handlers/mini_app.py` или `handlers/start.py`

### 15.2. Обновите URL мини-аппа

```bash
nano /opt/telegram_bot_test/handlers/mini_app.py
```

Найдите строку с `web_app_url` и замените на URL вашего Netlify сайта:

```python
web_app_url = "https://arbuzcas.netlify.app/index.html"
```

Или если используете другой файл, найдите где создается кнопка мини-аппа и обновите URL там.

### 15.3. Перезапустите тестовый бот

```bash
systemctl restart telegram-bot-test
systemctl status telegram-bot-test
```

---

## Шаг 16: Настройка в @BotFather

1. Откройте @BotFather в Telegram
2. Найдите вашего тестового бота
3. Отправьте команду для настройки Mini App (или используйте меню)
4. Вставьте URL: `https://arbuzcas.netlify.app/index.html`

---

## Проверка работы

1. Откройте тестового бота в Telegram
2. Нажмите кнопку "Открыть мини-апп" (или команду для открытия)
3. Мини-апп должен открыться
4. Проверьте что баланс загружается (может быть 0, это нормально для нового бота)
5. Проверьте что подарки загружаются

---

## Управление тестовым ботом

### Остановить:
```bash
systemctl stop telegram-bot-test
```

### Запустить:
```bash
systemctl start telegram-bot-test
```

### Перезапустить:
```bash
systemctl restart telegram-bot-test
```

### Посмотреть логи:
```bash
journalctl -u telegram-bot-test -n 50 -f
```

Нажмите `Ctrl+C` чтобы выйти из просмотра логов.

### Посмотреть статус:
```bash
systemctl status telegram-bot-test
```

---

## Структура на сервере

```
/opt/telegram_bot/          # Основной бот (работает)
├── main.py
├── config.py
├── database.db             # Основная БД
├── venv/
└── ...

/opt/telegram_bot_test/     # Тестовый бот (новый)
├── main.py
├── config.py
├── database.db             # Тестовая БД (отдельная!)
├── venv/
├── mini_app/               # Файлы мини-аппа
└── ...
```

---

## Важные замечания

- ✅ Основной бот продолжает работать на порту 8080
- ✅ Тестовый бот работает на порту 8081
- ✅ Базы данных полностью разделены
- ✅ Пользователи основного бота не видят мини-апп
- ✅ Мини-апп доступен только через тестового бота

---

## Решение проблем

### Проблема: API не отвечает (404 или ошибка подключения)

1. Проверьте что тестовый бот запущен:
```bash
systemctl status telegram-bot-test
```

2. Проверьте логи:
```bash
journalctl -u telegram-bot-test -n 100 | grep -i "api\|8081\|error"
```

3. Проверьте что порт открыт:
```bash
ufw status | grep 8081
ss -tlnp | grep 8081
```

4. Проверьте что API работает локально:
```bash
curl http://localhost:8081/api/user
```

### Проблема: CORS ошибки

API сервер уже настроен с CORS заголовками. Если все равно есть ошибки, проверьте логи API сервера.

### Проблема: Баланс показывает 0

Это нормально для нового тестового бота. База данных пустая. Можно:
- Пополнить баланс через команды бота
- Или скопировать данные из основной БД (не рекомендуется для теста)

### Проблема: Мини-апп не открывается

1. Проверьте URL в @BotFather
2. Проверьте что сайт на Netlify доступен
3. Откройте консоль браузера (F12) и проверьте ошибки

---

## После тестирования

Когда мини-апп будет готов к продакшену:

1. Можно перенести настройки в основной бот
2. Или оставить тестового бота для дальнейших экспериментов
3. Или удалить тестового бота:

```bash
systemctl stop telegram-bot-test
systemctl disable telegram-bot-test
rm /etc/systemd/system/telegram-bot-test.service
rm -rf /opt/telegram_bot_test
```

---

## Контакты и поддержка

Если возникли проблемы:
1. Проверьте логи: `journalctl -u telegram-bot-test -n 100`
2. Проверьте статус: `systemctl status telegram-bot-test`
3. Проверьте порт: `ss -tlnp | grep 8081`

---

**Последнее обновление:** 10 декабря 2025

