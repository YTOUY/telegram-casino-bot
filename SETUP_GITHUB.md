# Настройка GitHub для Cloud Agents

## Шаги для подключения к GitHub:

1. **Создайте репозиторий на GitHub:**
   - Перейдите на https://github.com/new
   - Название: `telegram-casino-bot` (или любое другое)
   - Выберите Private или Public
   - НЕ добавляйте README, .gitignore или лицензию
   - Нажмите "Create repository"

2. **Добавьте remote в локальный репозиторий:**
   ```bash
   cd "тг каз для 11"
   git remote add origin https://github.com/ВАШ_USERNAME/telegram-casino-bot.git
   ```

3. **Закоммитьте изменения:**
   ```bash
   git add .
   git commit -m "Initial commit"
   ```

4. **Запушьте код:**
   ```bash
   git push -u origin master
   ```

5. **Вернитесь в Cursor и нажмите "Refresh" в настройках Cloud Agents**

## Альтернатива: Использовать существующий репозиторий

Если у вас уже есть репозиторий на GitHub:
```bash
cd "тг каз для 11"
git remote add origin https://github.com/ВАШ_USERNAME/ВАШ_РЕПОЗИТОРИЙ.git
git push -u origin master
```
