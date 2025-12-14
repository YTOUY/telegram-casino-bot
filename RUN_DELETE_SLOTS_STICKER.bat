@echo off
chcp 65001 >nul
echo Скопируйте и выполните эту команду на сервере:
echo.
echo ssh root@141.8.198.144
echo cd /opt/telegram_bot_test
echo sqlite3 database.db "DELETE FROM stickers WHERE name LIKE '%%slots%%' OR name LIKE '%%slot%%';"
echo.
echo Или выполните Python скрипт на сервере:
echo python3 delete_slots_base_from_server.py
echo.
pause







