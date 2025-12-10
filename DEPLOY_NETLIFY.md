# Развертывание мини-приложения на Netlify

## Подготовка

1. **Убедитесь, что папка `nft` находится в `тг каз для 11/`**:
   ```
   тг каз для 11/
   ├── mini_app/
   ├── nft/
   │   ├── tgs/
   │   └── png/
   └── ...
   ```

2. **Проверьте структуру файлов** в `mini_app/`:
   - `index.html`
   - `styles.css`
   - `app.js`
   - `netlify.toml`
   - `_headers`

## Развертывание через Netlify CLI

### 1. Установите Netlify CLI (если еще не установлен):
```bash
npm install -g netlify-cli
```

### 2. Войдите в Netlify:
```bash
netlify login
```

### 3. Перейдите в папку mini_app:
```bash
cd "тг каз для 11/mini_app"
```

### 4. Инициализируйте проект:
```bash
netlify init
```
Выберите:
- "Create & configure a new site"
- Выберите команду (оставьте пустым или `echo 'No build'`)
- Выберите директорию публикации: `.` (текущая папка mini_app)

### 5. Разверните:
```bash
netlify deploy --prod
```

## Развертывание через веб-интерфейс Netlify

1. Зайдите на [netlify.com](https://netlify.com) и войдите в аккаунт

2. Нажмите "Add new site" → "Deploy manually"

3. **ВАЖНО**: Создайте ZIP архив всей папки `тг каз для 11` (включая `mini_app` и `nft`)

4. Загрузите ZIP архив в Netlify

5. Или используйте GitHub:
   - Создайте репозиторий на GitHub
   - Загрузите всю папку `тг каз для 11` в репозиторий
   - В Netlify: "Add new site" → "Import an existing project"
   - Подключите репозиторий
   - Настройки:
     - Build command: (оставьте пустым)
     - Publish directory: `mini_app`

## Настройка после развертывания

1. **Получите URL вашего сайта** (например: `https://your-site.netlify.app`)

2. **Обновите URL в боте** (`handlers/mini_app.py`):
   ```python
   web_app_url = "https://your-site.netlify.app/index.html"
   ```

3. **Настройте API_BASE в app.js**:
   Откройте `mini_app/app.js` и обновите:
   ```javascript
   const API_BASE = 'https://your-backend-api.com/api';
   ```
   (Замените на URL вашего бэкенд API)

## Структура файлов для Netlify

При развертывании из папки `mini_app`:

```
mini_app/              # Публикуется на Netlify
├── index.html
├── styles.css
├── app.js
├── netlify.toml
├── _headers
└── nft/               # Подарки (доступны через nft/tgs/ и nft/png/)
    ├── tgs/
    └── png/
```

## Важные замечания

- Netlify автоматически обрабатывает SPA благодаря `netlify.toml`
- Все запросы перенаправляются на `index.html` для правильной работы роутинга
- Заголовки в `_headers` обеспечивают безопасность и правильную работу с Telegram Web App
- Подарки загружаются из папки `nft/` внутри `mini_app/` (путь `nft/tgs/` и `nft/png/`)
- Убедитесь, что папка `nft` скопирована в `mini_app/` перед развертыванием

## Обновление сайта

После изменений в коде:
```bash
cd "тг каз для 11/mini_app"
netlify deploy --prod
```

Или при использовании GitHub - просто сделайте push, Netlify автоматически обновит сайт.

## Проверка работы

1. Откройте бота в Telegram
2. Отправьте команду `/miniapp`
3. Нажмите кнопку "Открыть ArbuzCasino"
4. Мини-приложение должно открыться
5. Проверьте работу подарков в разделе "Кошелек" → "Пополнить" → "Подарки"

