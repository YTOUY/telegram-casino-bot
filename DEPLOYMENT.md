# Инструкция по развертыванию и обновлению бота на сервере

## 📋 Содержание
1. [Первоначальная установка](#первоначальная-установка)
2. [Обновление кода](#обновление-кода)
3. [Управление базой данных](#управление-базой-данных)
4. [Управление сервисом](#управление-сервисом)
5. [Просмотр логов](#просмотр-логов)
6. [Решение проблем](#решение-проблем)
7. [Автоматические бэкапы](#автоматические-бэкапы)
8. [Диагностика производительности](#диагностика-производительности)

---

## 🚀 Первоначальная установка

### 1. Подключение к серверу

```bash
ssh root@141.8.198.144
```

### 2. Обновление системы

```bash
apt update && apt upgrade -y
```

### 3. Установка зависимостей

```bash
# Установка Python и необходимых инструментов
apt install -y python3 python3-venv python3-pip git curl

# Проверка версии Python
python3 --version
```

### 4. Создание директории для бота

```bash
mkdir -p /opt/telegram_bot
cd /opt/telegram_bot
```

### 5. Загрузка файлов проекта

**Вариант A: Через SCP (с локального компьютера)**

На вашем локальном компьютере (PowerShell):
```powershell
cd "F:\ytouy\Documents\тг каз для 11"
scp -r * root@141.8.198.144:/opt/telegram_bot/
```

**Вариант B: Через Git (если есть репозиторий)**
```bash
cd /opt/telegram_bot
git clone <ваш_репозиторий_url> .
```

**Вариант C: Через WinSCP/FileZilla**
- Используйте графический клиент для загрузки всех файлов

### 6. Настройка виртуального окружения

```bash
cd /opt/telegram_bot

# Создание виртуального окружения
python3 -m venv venv

# Активация виртуального окружения
source venv/bin/activate

# Обновление pip
pip install --upgrade pip

# Установка зависимостей
pip install -r requirements.txt
```

### 7. Настройка конфигурации

```bash
nano config.py
```

Убедитесь, что указаны:
- `BOT_TOKEN` - токен бота от @BotFather
- `ADMIN_IDS` - список ID администраторов
- `CRYPTO_PAY_TOKEN` - токен Crypto Pay (если используется)
- Другие необходимые настройки

### 8. Создание systemd сервиса

```bash
nano /etc/systemd/system/telegram-bot.service
```

Содержимое файла:
```ini
[Unit]
Description=Telegram Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram_bot
Environment="PATH=/opt/telegram_bot/venv/bin"
ExecStart=/opt/telegram_bot/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 9. Запуск сервиса

```bash
# Перезагрузка systemd
systemctl daemon-reload

# Включение автозапуска
systemctl enable telegram-bot

# Запуск бота
systemctl start telegram-bot

# Проверка статуса
systemctl status telegram-bot
```

---

## 🔄 Обновление кода

### Метод 1: Через SCP (рекомендуется для небольших изменений)

**На локальном компьютере:**
```powershell
cd "F:\ytouy\Documents\тг каз для 11"

# Загрузить конкретный файл
scp handlers/settings.py root@141.8.198.144:/opt/telegram_bot/handlers/

# Загрузить всю директорию handlers
scp -r handlers/* root@141.8.198.144:/opt/telegram_bot/handlers/

# Загрузить все файлы проекта
scp -r * root@141.8.198.144:/opt/telegram_bot/
```


**На сервере:**
```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Если изменились зависимости, обновить их
source venv/bin/activate
pip install -r requirements.txt

# Запустить бота
systemctl start telegram-bot

# Проверить статус
systemctl status telegram-bot
```

### Метод 2: Через Git (если используется)

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Получить обновления
git pull origin main

# Обновить зависимости (если изменились)
source venv/bin/activate
pip install -r requirements.txt

# Запустить бота
systemctl start telegram-bot
```

### Метод 3: Редактирование напрямую на сервере

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Редактировать файл
nano handlers/settings.py
# или
vim handlers/settings.py

# Запустить бота
systemctl start telegram-bot
```

---

## 💾 Управление базой данных

### Создание бэкапа

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Создать бэкап
cp database.db database.db.backup
# Или с датой
cp database.db database.db.backup.$(date +%Y%m%d_%H%M%S)

# Запустить бота
systemctl start telegram-bot
```

### Восстановление из бэкапа

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Восстановить из бэкапа
cp database.db.backup database.db

# Запустить бота
systemctl start telegram-bot
```

### Удаление и пересоздание базы данных

⚠️ **ВНИМАНИЕ: Все данные будут потеряны!**

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Создать бэкап (на всякий случай)
cp database.db database.db.backup.$(date +%Y%m%d_%H%M%S)

# Удалить базу данных
rm database.db
# Или удалить все связанные файлы
rm -f database.db database.db-journal database.db-wal database.db-shm

# Запустить бота (база создастся автоматически)
systemctl start telegram-bot
```

### Загрузка базы данных с локального компьютера

**На локальном компьютере:**
```powershell
cd "F:\ytouy\Documents\тг каз для 11"
scp database.db root@141.8.198.144:/opt/telegram_bot/
```

**На сервере:**
```bash
cd /opt/telegram_bot
systemctl stop telegram-bot

# Убедиться, что файл загружен
ls -lh database.db

# Установить правильные права
chown root:root database.db
chmod 644 database.db

# Запустить бота
systemctl start telegram-bot
```

---

## ⚙️ Управление сервисом

### Основные команды

```bash
# Запустить бота
systemctl start telegram-bot

# Остановить бота
systemctl stop telegram-bot

# Перезапустить бота
systemctl restart telegram-bot

# Проверить статус
systemctl status telegram-bot

# Включить автозапуск
systemctl enable telegram-bot

# Отключить автозапуск
systemctl disable telegram-bot
```

### Проверка работы

```bash
# Проверить, что процесс запущен
ps aux | grep python

# Проверить порты (если используется веб-хук)
netstat -tlnp | grep python
```

---

## 📊 Просмотр логов

### Основные команды

```bash
# Просмотр последних 50 строк логов
journalctl -u telegram-bot -n 50

# Просмотр логов в реальном времени
journalctl -u telegram-bot -f

# Просмотр логов за сегодня
journalctl -u telegram-bot --since today

# Просмотр логов за последний час
journalctl -u telegram-bot --since "1 hour ago"

# Просмотр логов с определенной даты
journalctl -u telegram-bot --since "2025-11-29 10:00:00"

# Сохранить логи в файл
journalctl -u telegram-bot -n 100 > /tmp/bot_logs.txt
```

### Поиск ошибок

```bash
# Поиск ошибок в логах
journalctl -u telegram-bot | grep -i error

# Поиск критических ошибок
journalctl -u telegram-bot | grep -i "critical\|fatal\|exception"
```

---

## 🔧 Решение проблем

### Проблема: Бот не запускается

1. **Проверьте логи:**
```bash
journalctl -u telegram-bot -n 50
```

2. **Проверьте синтаксис Python:**
```bash
cd /opt/telegram_bot
source venv/bin/activate
python3 -m py_compile main.py
python3 -m py_compile handlers/*.py
```

3. **Проверьте конфигурацию:**
```bash
cd /opt/telegram_bot
source venv/bin/activate
python3 -c "import config; print('Config OK')"
```

4. **Запустите бота вручную для просмотра ошибок:**
```bash
cd /opt/telegram_bot
source venv/bin/activate
python3 main.py
```

### Проблема: Модули не найдены

```bash
cd /opt/telegram_bot
source venv/bin/activate

# Переустановить зависимости
pip install -r requirements.txt

# Проверить установленные пакеты
pip list
```

### Проблема: Ошибки базы данных

```bash
cd /opt/telegram_bot

# Остановить бота
systemctl stop telegram-bot

# Проверить целостность базы данных
sqlite3 database.db "PRAGMA integrity_check;"

# Если база повреждена, восстановить из бэкапа
cp database.db.backup database.db
```

### Проблема: Недостаточно прав

```bash
# Установить правильные права на файлы
cd /opt/telegram_bot
chown -R root:root .
chmod 644 *.py
chmod 755 handlers/ utils/
```

---

## 🔄 Автоматические бэкапы

### Создание скрипта бэкапа

```bash
nano /opt/telegram_bot/backup_db.sh
```

Содержимое скрипта:
```bash
#!/bin/bash
BACKUP_DIR="/opt/telegram_bot/backups"
mkdir -p $BACKUP_DIR

# Создать бэкап базы данных
cp /opt/telegram_bot/database.db "$BACKUP_DIR/database_$(date +%Y%m%d_%H%M%S).db"

# Удалить старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "database_*.db" -mtime +7 -delete

echo "Backup created: database_$(date +%Y%m%d_%H%M%S).db"
```

Сделать скрипт исполняемым:
```bash
chmod +x /opt/telegram_bot/backup_db.sh
```

### Настройка автоматических бэкапов через cron

```bash
crontab -e
```

Добавьте строки:
```cron
# Бэкап каждый день в 3:00
0 3 * * * /opt/telegram_bot/backup_db.sh

# Бэкап каждые 6 часов
0 */6 * * * /opt/telegram_bot/backup_db.sh

# Бэкап каждый час
0 * * * * /opt/telegram_bot/backup_db.sh
```

### Ручной запуск бэкапа

```bash
/opt/telegram_bot/backup_db.sh
```

---

## 📝 Быстрая шпаргалка

### Обновление одного файла
```bash
# На локальном компьютере
scp handlers/settings.py root@141.8.198.144:/opt/telegram_bot/handlers/

# На сервере
systemctl restart telegram-bot
```

### Обновление нескольких файлов (после изменений в database.py и games.py)
```bash
# На локальном компьютере (PowerShell)
cd "F:\ytouy\Documents\тг каз для 11"

# Загрузить database.py
scp database.py root@141.8.198.144:/opt/telegram_bot/

# Загрузить handlers/games.py
scp handlers/games.py root@141.8.198.144:/opt/telegram_bot/handlers/

# На сервере
ssh root@141.8.198.144
cd /opt/telegram_bot
systemctl restart telegram-bot
systemctl status telegram-bot
```

### Обновление файлов базы данных и игр (после добавления bet_type)
```bash
# На локальном компьютере (PowerShell) - все одной командой
cd "F:\ytouy\Documents\тг каз для 11"
scp database.py root@141.8.198.144:/opt/telegram_bot/
scp handlers/games.py root@141.8.198.144:/opt/telegram_bot/handlers/

# На сервере
ssh root@141.8.198.144
cd /opt/telegram_bot
systemctl stop telegram-bot
systemctl start telegram-bot
journalctl -u telegram-bot -f
```

### Полное обновление проекта
```bash
# На локальном компьютере
scp -r * root@141.8.198.144:/opt/telegram_bot/

# На сервере
cd /opt/telegram_bot
systemctl stop telegram-bot
source venv/bin/activate
pip install -r requirements.txt
systemctl start telegram-bot
```

### Просмотр статуса и логов
```bash
systemctl status telegram-bot
journalctl -u telegram-bot -f
```

### Бэкап базы данных
```bash
cd /opt/telegram_bot
systemctl stop telegram-bot
cp database.db database.db.backup.$(date +%Y%m%d_%H%M%S)
systemctl start telegram-bot
```

---

## 🔐 Безопасность

### Рекомендации

1. **Не храните токены в Git:**
   - Используйте `.env` файлы или переменные окружения
   - Добавьте `config.py` в `.gitignore`

2. **Регулярные обновления:**
   ```bash
   apt update && apt upgrade -y
   ```

3. **Firewall:**
   ```bash
   ufw allow 22/tcp
   ufw enable
   ```

4. **Мониторинг:**
   - Регулярно проверяйте логи
   - Настройте уведомления об ошибках

---

## 📞 Полезные команды

```bash
# Размер базы данных
du -h /opt/telegram_bot/database.db

# Размер всех файлов проекта
du -sh /opt/telegram_bot/*

# Проверка места на диске
df -h

# Использование памяти
free -h

# Активные процессы Python
ps aux | grep python

# Проверка сетевых подключений
netstat -tulpn | grep python
```

---

## 🌐 Веб-интерфейс для базы данных

### Установка SQLite Web (рекомендуется)

SQLite Web - простой веб-интерфейс для просмотра и редактирования SQLite базы данных.

**На сервере:**

```bash
cd /opt/telegram_bot
source venv/bin/activate

# Установка SQLite Web
pip install sqlite-web

# Запуск веб-интерфейса (на порту 8080)
sqlite_web /opt/telegram_bot/database.db --host 0.0.0.0 --port 8080
```

**Доступ:**
- Откройте в браузере: `http://141.8.198.144:8080`
- Если порт закрыт, откройте его в firewall:
  ```bash
  ufw allow 8080/tcp
  ```

**Запуск в фоне (через systemd):**

Создайте сервис для веб-интерфейса:
```bash
nano /etc/systemd/system/sqlite-web.service
```

Содержимое:
```ini
[Unit]
Description=SQLite Web Interface
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telegram_bot
Environment="PATH=/opt/telegram_bot/venv/bin"
ExecStart=/opt/telegram_bot/venv/bin/sqlite_web /opt/telegram_bot/database.db --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
systemctl daemon-reload
systemctl enable sqlite-web
systemctl start sqlite-web
systemctl status sqlite-web
```

### Альтернатива: phpLiteAdmin

Если предпочитаете PHP-решение:

```bash
# Установка PHP и веб-сервера
apt install -y php php-sqlite3 nginx

# Скачивание phpLiteAdmin
cd /var/www/html
wget https://raw.githubusercontent.com/phalcon/phpliteadmin/master/phpliteadmin.php

# Настройка прав
chown www-data:www-data phpliteadmin.php
chmod 644 phpliteadmin.php

# Настройка nginx (опционально)
# Создайте виртуальный хост для доступа к phpLiteAdmin
```

### Безопасность

⚠️ **ВАЖНО:** Веб-интерфейс должен быть защищен!

1. **Используйте аутентификацию:**
   - Настройте базовую аутентификацию в nginx
   - Или используйте VPN/SSH туннель

2. **Ограничьте доступ по IP:**
   ```bash
   # В nginx конфигурации
   allow YOUR_IP_ADDRESS;
   deny all;
   ```

3. **Используйте SSH туннель (самый безопасный способ):**
   ```bash
   # На локальном компьютере
   # Если порт 8080 занят, используйте другой (например, 8081)
   ssh -L 8081:localhost:8080 root@141.8.198.144
   
   # Затем откройте в браузере: http://localhost:8081
   # Или если порт 8080 свободен:
   ssh -L 8080:localhost:8080 root@141.8.198.144
   # http://localhost:8080
   ```
   
   **Если получаете ошибку "Address already in use":**
   - Используйте другой локальный порт (8081, 8082 и т.д.)
   - Или проверьте, что занимает порт: `netstat -ano | findstr :8080` (Windows)

---

## 📚 Дополнительная информация

- **Расположение файлов:** `/opt/telegram_bot/`
- **Логи сервиса:** `journalctl -u telegram-bot`
- **Конфигурация:** `/opt/telegram_bot/config.py`
- **База данных:** `/opt/telegram_bot/database.db`
- **Сервис systemd:** `/etc/systemd/system/telegram-bot.service`
- **Веб-интерфейс БД:** `http://141.8.198.144:8080` (после установки)

---

**Последнее обновление:** 29 ноября 2025

