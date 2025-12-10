# Настройка тестового бота на том же сервере

## Цель
Запустить тестовый бот для мини-аппа отдельно от основного бота, чтобы:
- Обычные пользователи не могли заходить в мини-апп
- Использовать отдельную базу данных
- Тестировать без влияния на основной бот

## Решение: Два бота на одном сервере

### Структура на сервере:
```
/opt/telegram_bot/          # Основной бот (работает)
├── main.py
├── config.py
├── database.db             # Основная БД
└── ...

/opt/telegram_bot_test/     # Тестовый бот (новый)
├── main.py
├── config.py
├── test_database.db        # Тестовая БД
└── ...
```

## Шаги настройки

### 1. Подключитесь к серверу
```bash
ssh root@141.8.198.144
```

### 2. Создайте папку для тестового бота
```bash
mkdir -p /opt/telegram_bot_test
cd /opt/telegram_bot_test
```

### 3. Скопируйте файлы бота
```bash
# Скопируйте все файлы из основного бота
cp -r /opt/telegram_bot/* /opt/telegram_bot_test/
```

### 4. Создайте отдельный конфиг для тестового бота

Отредактируйте `/opt/telegram_bot_test/config.py`:

```python
# Используйте ТЕСТОВЫЙ токен бота (создайте нового бота через @BotFather)
BOT_TOKEN = os.getenv("TEST_BOT_TOKEN", "ваш-тестовый-токен-бота")

# Используйте отдельную базу данных
DATABASE_PATH = "/opt/telegram_bot_test/test_database.db"

# API порт другой (например, 8081 вместо 8080)
API_PORT = 8081  # Основной бот использует 8080
```

### 5. Создайте тестового бота через @BotFather

1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Создайте нового бота (например: `ArbuzCasinoTestBot`)
4. Скопируйте токен
5. Вставьте токен в `config.py` тестового бота

### 6. Настройте main.py для другого порта

Отредактируйте `/opt/telegram_bot_test/main.py`:

Найдите строку:
```python
api_port = int(os.getenv("API_PORT", "8080"))
```

Замените на:
```python
api_port = int(os.getenv("API_PORT", "8081"))  # Другой порт!
```

### 7. Создайте отдельный systemd сервис

```bash
nano /etc/systemd/system/telegram-bot-test.service
```

Содержимое:
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

### 8. Настройте виртуальное окружение для тестового бота

```bash
cd /opt/telegram_bot_test
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 9. Откройте порт 8081 в файрволе

```bash
ufw allow 8081/tcp
ufw reload
```

### 10. Запустите тестовый бот

```bash
systemctl daemon-reload
systemctl enable telegram-bot-test
systemctl start telegram-bot-test
systemctl status telegram-bot-test
```

### 11. Обновите app.js для тестового бота

В `mini_app/app.js` измените:
```javascript
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    // Тестовый бот использует порт 8081
    API_BASE = 'http://141.8.198.144:8081/api';
}
```

### 12. Настройте мини-апп для тестового бота

В `handlers/mini_app.py` (или где настраивается URL мини-аппа) для тестового бота:
```python
# Только для тестового бота
web_app_url = "https://arbuzcas.netlify.app/index.html"
```

## Проверка работы

1. **Проверьте основной бот:**
```bash
systemctl status telegram-bot
# Должен работать на порту 8080
```

2. **Проверьте тестовый бот:**
```bash
systemctl status telegram-bot-test
# Должен работать на порту 8081
```

3. **Проверьте API:**
- Основной: `http://141.8.198.144:8080/api/user`
- Тестовый: `http://141.8.198.144:8081/api/user`

4. **Проверьте базы данных:**
```bash
# Основная БД
ls -lh /opt/telegram_bot/database.db

# Тестовая БД
ls -lh /opt/telegram_bot_test/test_database.db
```

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

## Важно!

- ✅ Основной бот продолжает работать как обычно
- ✅ Тестовый бот использует отдельную БД
- ✅ Пользователи основного бота не видят мини-апп
- ✅ Мини-апп доступен только через тестового бота
- ✅ Можно тестировать без риска для основного бота

## После тестирования

Когда мини-апп будет готов:
1. Можно перенести настройки в основной бот
2. Или оставить тестовый бот для дальнейших экспериментов
3. Или удалить тестового бота:
```bash
systemctl stop telegram-bot-test
systemctl disable telegram-bot-test
rm /etc/systemd/system/telegram-bot-test.service
rm -rf /opt/telegram_bot_test
```

