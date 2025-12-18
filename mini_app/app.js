// Telegram Web App API
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Состояние приложения
const appState = {
    currentPage: 'play',
    user: null,
    balance: 0,
    baseBet: 1.0,
    stickers: {},
    checkStep: 1,
    currentGameId: null,
    selectedGameMode: null,
    selectedBet: 1.0,
    gameInProgress: false,  // Флаг активной игры для блокировки повторных запусков
    slotsSpinUsed: false,    // Слоты: можно крутить только 1 раз (на сессию мини-аппа)
    slotsLastSymbols: null,   // Слоты: последние выпавшие символы (чтобы не терять результат при навигации)
    tonRate: 5.0,  // Курс TON к USD (обновляется каждые 10 минут)
    tonRateUpdateInterval: null,  // Интервал обновления курса
    topRefreshInterval: null,  // Интервал автоматического обновления топа
    currentTopCategory: 'players',  // Текущая категория топа
    currentTopPeriod: 'day'  // Текущий период топа (по умолчанию день)
};

// API endpoints
// ВАЖНО: Замените на реальный URL вашего API сервера!
// API сервер должен быть доступен по публичному URL (например, через ngrok, VPS или другой хостинг)
// Пример: 'https://your-api-server.com:8080/api' или 'https://your-api-domain.com/api'

let API_BASE = '/api'; // дефолт, если сайт сам проксирует /api

// Netlify (включая netlify dev на localhost): используем Netlify Function как прокси
const isLocalHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const isNetlifyHost = window.location.hostname.endsWith('netlify.app');
if (isLocalHost || isNetlifyHost) {
    API_BASE = '/.netlify/functions/api-proxy/api';
}

// Максимальная сумма депозита
const MAX_DEPOSIT = 1000;

console.log('🌐 API_BASE установлен:', API_BASE, '(hostname:', window.location.hostname + ')');

// Получить initData для API запросов
function getInitData() {
    // Пробуем получить initData из разных источников
    // Telegram WebApp API предоставляет initData как строку
    if (tg.initData && tg.initData.length > 0) {
        console.log('✅ Используется tg.initData');
        return tg.initData;
    }
    
    // Если initData недоступен, пробуем получить из initDataUnsafe
    // Это может произойти в некоторых случаях (например, в тестовом режиме)
    if (tg.initDataUnsafe) {
        console.warn('⚠️ initData недоступен, используется initDataUnsafe');
        // В реальном приложении нужно формировать правильную строку initData
        // из initDataUnsafe, но для тестирования можно попробовать пустую строку
        // или сформировать базовую строку
        if (tg.initDataUnsafe.query_id) {
            // Формируем минимальную строку initData (неполная, но может работать для теста)
            const params = [];
            if (tg.initDataUnsafe.user) {
                params.push(`user=${encodeURIComponent(JSON.stringify(tg.initDataUnsafe.user))}`);
            }
            if (tg.initDataUnsafe.query_id) {
                params.push(`query_id=${tg.initDataUnsafe.query_id}`);
            }
            if (tg.initDataUnsafe.auth_date) {
                params.push(`auth_date=${tg.initDataUnsafe.auth_date}`);
            }
            if (tg.initDataUnsafe.hash) {
                params.push(`hash=${tg.initDataUnsafe.hash}`);
            }
            return params.join('&');
        }
    }
    
    console.error('❌ initData недоступен!');
    return '';
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', async () => {
    // Получаем данные пользователя из Telegram
    const initData = tg.initDataUnsafe;
    appState.user = {
        id: initData.user?.id,
        firstName: initData.user?.first_name,
        lastName: initData.user?.last_name,
        username: initData.user?.username,
        photoUrl: initData.user?.photo_url
    };

    // Загружаем данные пользователя
    await loadUserData();
    
    // Инициализируем UI сразу после загрузки данных
    updateUI();
    
    // Запускаем обновление курса TON каждые 10 минут (не блокируем загрузку)
    // Используем setTimeout чтобы не блокировать инициализацию
    setTimeout(() => {
        startTONRateUpdates();
    }, 1000);
    
    // Показываем начальный экран
    showSplashScreen();
    
    // Инициализируем навигацию
    initNavigation();
    
    // Инициализируем страницы
    initPages();
    
    // Загружаем стикеры
    await loadStickers();
});

// Показать начальный экран
function showSplashScreen() {
    const splashScreen = document.getElementById('splash-screen');
    const welcomeSticker = document.getElementById('welcome-sticker');
    const welcomeText = document.querySelector('.welcome-text');
    const loadingCircle = document.querySelector('.loading-circle');
    
    // Показываем стикер сразу
    welcomeSticker.style.display = 'block';
    welcomeSticker.style.opacity = '0';
    
    // Загружаем и показываем стикер (анимация 2 секунды)
    loadWelcomeSticker().then(stickerUrl => {
        if (stickerUrl) {
            // Проверяем формат файла по URL
            // TGS файлы обычно имеют расширение .tgs или содержат 'tgs' в пути
            const isTgs = stickerUrl.toLowerCase().includes('.tgs') || 
                         stickerUrl.toLowerCase().includes('/tgs/') ||
                         stickerUrl.toLowerCase().includes('tgs') ||
                         stickerUrl.toLowerCase().endsWith('.tgs');
            
            console.log('🔍 Проверка формата стикера:', { stickerUrl, isTgs });
            
            if (isTgs) {
                // Для TGS файлов используем библиотеку lottie-web для отображения
                // Библиотеки уже загружены в HTML
                console.log('🎬 Обнаружен TGS стикер, начинаем загрузку...');
                
                // Проверяем наличие библиотек
                const checkAndLoad = () => {
                    if (window.lottie && window.pako) {
                        console.log('✅ Библиотеки lottie и pako готовы');
                        loadTgsSticker(welcomeSticker, stickerUrl);
                    } else {
                        console.warn('⚠️ Библиотеки еще не загружены, ждем...');
                        setTimeout(checkAndLoad, 100);
                    }
                };
                
                // Ждем загрузки библиотек (максимум 5 секунд)
                let attempts = 0;
                const maxAttempts = 50;
                const checkInterval = setInterval(() => {
                    attempts++;
                    if (window.lottie && window.pako) {
                        clearInterval(checkInterval);
                        loadTgsSticker(welcomeSticker, stickerUrl);
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        console.error('❌ Библиотеки не загрузились за 5 секунд');
                        showStickerFallback(welcomeSticker, true);
                    }
                }, 100);
            } else {
                // Для обычных изображений (PNG, WEBP и т.д.)
                const img = document.createElement('img');
                img.src = stickerUrl;
                img.alt = 'Welcome';
                img.style.width = '100%';
                img.style.height = '100%';
                img.style.objectFit = 'contain';
                img.style.display = 'block';
                img.onload = () => {
                    welcomeSticker.innerHTML = '';
                    welcomeSticker.appendChild(img);
                    welcomeSticker.style.opacity = '1';
                    console.log('✅ Стикер отображен:', stickerUrl);
                };
                img.onerror = () => {
                    console.error('❌ Ошибка загрузки изображения стикера:', stickerUrl);
                    showStickerFallback(welcomeSticker);
                };
            }
        } else {
            // Если стикер не загрузился, показываем сообщение об ошибке
            console.error('❌ Стикер не найден в базе данных. Используйте команду /sticker для добавления стикера с названием "welcome"');
            showStickerFallback(welcomeSticker, true);
        }
    }).catch(error => {
        console.error('❌ Ошибка при загрузке стикера:', error);
        showStickerFallback(welcomeSticker, true);
    });
    
    // Через 2 секунды показываем текст и начинаем загрузку
    setTimeout(() => {
        if (welcomeText) {
            welcomeText.style.display = 'block';
        }
        if (loadingCircle) {
            loadingCircle.style.display = 'block';
        }
    }, 2000);
    
    // Через 5 секунд (2 сек стикер + 3 сек загрузка) показываем основное приложение
    setTimeout(async () => {
        splashScreen.classList.add('hidden');
        document.getElementById('main-app').classList.remove('hidden');
        // Загружаем игры сразу после показа основного приложения
        await loadGames();
    }, 5000);
}

// Загрузить приветственный стикер
async function loadWelcomeSticker() {
    // Сначала пробуем загрузить локальный TGS файл из папки stickers
    const localPaths = [
        'stickers/welcome/welcome.tgs',
        '../stickers/welcome/welcome.tgs',
        '/stickers/welcome/welcome.tgs'
    ];
    
    for (const path of localPaths) {
        try {
            const response = await fetch(path, { method: 'HEAD' });
            if (response.ok) {
                console.log('✅ Локальный TGS стикер найден:', path);
                return path;
            }
        } catch (e) {
            // Продолжаем поиск
        }
    }
    
    // Если локальный файл не найден, пробуем через API
    try {
        const response = await fetch(`${API_BASE}/sticker/welcome`, {
            headers: {
                'X-Telegram-Init-Data': tg.initData || ''
            }
        });
        
        console.log('🔍 Запрос стикера welcome через API, статус:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('📦 Данные стикера из API:', data);
            
            const stickerUrl = data.file_url || data.file_id;
            if (stickerUrl) {
                console.log('✅ Стикер загружен через API:', stickerUrl);
                return stickerUrl;
            } else {
                console.warn('⚠️ Стикер найден, но URL отсутствует. Данные:', data);
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.warn('⚠️ Стикер не найден через API, статус:', response.status, errorData);
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки стикера через API:', error);
    }
    
    console.warn('⚠️ Стикер не найден ни локально, ни через API');
    return null; // Вернем null, чтобы показать fallback
}

// Показать fallback для стикера
function showStickerFallback(element, showError = false) {
    // НЕ показываем fallback эмодзи, если стикер не найден
    // Вместо этого показываем пустой контейнер или сообщение
    if (showError) {
        element.innerHTML = `<div style="width: 200px; height: 200px; background: rgba(0,255,136,0.1); border-radius: 20px; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 14px; color: var(--accent-red); text-align: center; padding: 20px; animation: stickerAnimation 2s ease-in-out;">
            <div>⚠️</div>
            <div style="margin-top: 10px;">Стикер не найден</div>
            <div style="font-size: 12px; margin-top: 5px; color: var(--text-secondary);">Используйте /sticker для добавления стикера "welcome"</div>
        </div>`;
    } else {
        // Пустой контейнер с анимацией
        element.innerHTML = `<div style="width: 200px; height: 200px; background: rgba(0,255,136,0.1); border-radius: 20px; animation: stickerAnimation 2s ease-in-out;"></div>`;
    }
    element.style.opacity = '1';
}

// Загрузить библиотеку lottie-web для TGS стикеров
function loadLottieLibrary() {
    return new Promise((resolve, reject) => {
        if (window.lottie) {
            resolve();
            return;
        }
        
        // Проверяем, загружена ли библиотека из HTML
        if (document.querySelector('script[src*="lottie"]')) {
            // Ждем немного, чтобы библиотека загрузилась
            setTimeout(() => {
                if (window.lottie) {
                    resolve();
                } else {
                    reject(new Error('Lottie не загрузилась'));
                }
            }, 500);
        } else {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/build/player/lottie.min.js';
            script.onload = () => resolve();
            script.onerror = () => reject();
            document.head.appendChild(script);
        }
    });
}

// Загрузить TGS стикер через lottie
async function loadTgsSticker(element, tgsUrl) {
    // Очищаем элемент перед загрузкой
    element.innerHTML = '';
    
    // Добавляем cache buster если его еще нет (более агрессивный)
    if (tgsUrl && !tgsUrl.includes('?v=') && !tgsUrl.includes('&v=')) {
        const separator = tgsUrl.includes('?') ? '&' : '?';
        tgsUrl = `${tgsUrl}${separator}v=${Date.now()}_${Math.random().toString(36).substring(7)}`;
    }
    try {
        console.log('🎬 Загрузка TGS стикера:', tgsUrl);
        
        // Загружаем TGS файл с полным отключением кэша
        const response = await fetch(tgsUrl, { 
            cache: 'no-store',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache'
            }
        });
        if (!response.ok) {
            throw new Error(`Не удалось загрузить TGS файл: ${response.status}`);
        }
        
        const tgsData = await response.arrayBuffer();
        console.log('📦 TGS файл загружен, размер:', tgsData.byteLength, 'байт');
        
        // TGS файлы - это gzip-сжатые Lottie JSON файлы
        // Нужно распаковать их и загрузить через lottie
        // Используем библиотеку pako для распаковки gzip
        if (!window.pako) {
            // Загружаем pako для распаковки gzip
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/pako@2.1.0/dist/pako.min.js';
                script.onload = () => resolve();
                script.onerror = () => reject();
                document.head.appendChild(script);
            });
        }
        
        // Распаковываем gzip
        const decompressed = pako.inflate(new Uint8Array(tgsData), { to: 'string' });
        const lottieJson = JSON.parse(decompressed);
        console.log('✅ TGS распакован в Lottie JSON');
        
        // Валидация Lottie JSON
        if (!lottieJson.v || !lottieJson.layers || !Array.isArray(lottieJson.layers)) {
            throw new Error('Невалидный Lottie JSON: отсутствуют обязательные поля');
        }
        console.log(`📋 Lottie версия: ${lottieJson.v}, слоев: ${lottieJson.layers.length}, размеры: ${lottieJson.w || '?'}x${lottieJson.h || '?'}`);
        
        // Создаем контейнер для анимации
        const lottieContainer = document.createElement('div');
        lottieContainer.style.width = '100%';
        lottieContainer.style.height = '100%';
        lottieContainer.style.display = 'flex';
        lottieContainer.style.alignItems = 'center';
        lottieContainer.style.justifyContent = 'center';
        element.innerHTML = '';
        element.appendChild(lottieContainer);
        
        // Загружаем анимацию через lottie
        if (window.lottie) {
            // Уничтожаем старую анимацию, если она существует
            if (element._lottieAnim) {
                try {
                    element._lottieAnim.destroy();
                } catch (e) {
                    console.warn('Ошибка при уничтожении старой анимации:', e);
                }
                element._lottieAnim = null;
            }
            
            // Проверяем валидность данных перед загрузкой
            if (!lottieJson.layers || !Array.isArray(lottieJson.layers) || lottieJson.layers.length === 0) {
                throw new Error('Lottie JSON не содержит слоев или слои пусты');
            }
            
            console.log(`📋 Lottie данные: версия=${lottieJson.v || '?'}, размеры=${lottieJson.w || '?'}x${lottieJson.h || '?'}, слоев=${lottieJson.layers.length}`);
            
            const anim = lottie.loadAnimation({
                container: lottieContainer,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                animationData: lottieJson
            });
            
            // Проверяем, что анимация создана успешно
            if (!anim) {
                throw new Error('Не удалось создать Lottie анимацию');
            }
            
            // Сохраняем ссылку на анимацию для последующего уничтожения
            element._lottieAnim = anim;
            
            // Добавляем обработчик ошибок анимации
            anim.addEventListener('data_failed', () => {
                console.error('❌ Lottie анимация: ошибка загрузки данных');
            });
            
            anim.addEventListener('config_ready', () => {
                console.log('✅ Lottie анимация: конфигурация готова');
            });
            
            anim.addEventListener('data_ready', () => {
                console.log('✅ Lottie анимация: данные готовы');
            });
            
            element.style.opacity = '1';
            element.style.animation = 'stickerAnimation 2s ease-in-out';
            console.log('✅ TGS стикер успешно загружен и воспроизводится');
        } else {
            throw new Error('Lottie библиотека не загружена');
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки TGS стикера:', error);
        console.error('❌ Детали ошибки:', {
            message: error.message,
            stack: error.stack,
            url: tgsUrl,
            hasLottie: !!window.lottie,
            hasPako: !!window.pako
        });
        
        // Не показываем ошибку - просто оставляем пустым (стикер будет позже)
        element.innerHTML = '';
        element.style.opacity = '0.5';
    }
}

// Загрузить все стикеры
async function loadStickers() {
    try {
        const response = await fetch(`${API_BASE}/stickers`);
        if (response.ok) {
            const data = await response.json();
            data.forEach(sticker => {
                appState.stickers[sticker.name] = sticker.file_id;
            });
        }
    } catch (error) {
        console.error('Ошибка загрузки стикеров:', error);
    }
}

// Загрузить данные пользователя
async function loadUserData() {
    try {
        // Убеждаемся, что initData передается
        const initData = getInitData();
        
        console.log('📡 Запрос данных пользователя...', {
            API_BASE: API_BASE,
            hasInitData: !!initData,
            initDataLength: initData ? initData.length : 0,
            userId: appState.user?.id,
            hostname: window.location.hostname
        });
        
        if (!initData) {
            console.warn('⚠️ initData отсутствует! Запрос может не пройти авторизацию.');
        }
        
        const requestUrl = `${API_BASE}/user`;
        console.log('🔗 URL запроса:', requestUrl);
        
        const response = await fetch(requestUrl, {
            method: 'GET',
            headers: {
                'X-Telegram-Init-Data': initData || '',
                'Content-Type': 'application/json'
            }
        });
        
        console.log('📥 Ответ получен:', {
            status: response.status,
            statusText: response.statusText,
            ok: response.ok,
            headers: Object.fromEntries(response.headers.entries())
        });
        
        // Проверяем Content-Type перед парсингом
        const contentType = response.headers.get('content-type') || '';
        const isJson = contentType.includes('application/json');
        
        // Читаем ответ как текст сначала (можно прочитать только один раз!)
        const responseText = await response.text();
        
        // Пробуем распарсить как JSON независимо от Content-Type
        let data = null;
        try {
            data = JSON.parse(responseText);
        } catch (parseError) {
            // Не удалось распарсить как JSON
            console.warn('⚠️ Ответ не JSON! Content-Type:', contentType);
            console.warn('⚠️ Первые 200 символов ответа:', responseText.substring(0, 200));
            
            // Если это HTML (обычно означает что Netlify Function не работает)
            if (responseText.trim().startsWith('<!DOCTYPE') || responseText.trim().startsWith('<!doctype') || responseText.includes('<html')) {
                const errorMsg = 'Netlify Function не работает. Получен HTML вместо JSON.';
                console.error('❌', errorMsg);
                showToast('Ошибка подключения к серверу');
                return;
            }
            
            // Показываем общую ошибку без технических деталей
            console.error('❌ Не удалось обработать ответ:', responseText.substring(0, 200));
            showToast('Ошибка подключения к серверу');
            return;
        }
        
        // Обрабатываем ответ
        if (response.ok && data.balance !== undefined) {
            // Успешный ответ с данными пользователя
            const newBalance = parseFloat(data.balance) || 0;
            const newBaseBet = parseFloat(data.base_bet) || 1.0;
            
            console.log('✅ Данные пользователя загружены:', {
                balance: newBalance,
                base_bet: newBaseBet,
                raw_data: data
            });
            
            // Обновляем баланс только если он изменился или если текущий баланс равен 0
            if (appState.balance !== newBalance || appState.balance === 0) {
                appState.balance = newBalance;
                console.log(`💰 Баланс обновлен: $${newBalance.toFixed(2)}`);
            }
            appState.baseBet = newBaseBet;
            // Обновляем selectedBet если он еще не был установлен или равен дефолтному значению
            if (appState.selectedBet === 1.0 || appState.selectedBet === 0) {
                appState.selectedBet = newBaseBet;
            }
            updateUI();
        } else {
            // Ошибка в ответе
            console.error('❌ Ошибка в ответе:', data);
            
            // Показываем ошибку пользователю только если это не 401 (неавторизован)
            if (response.status !== 401) {
                const errorMsg = data.error || data.message || `Ошибка загрузки (${response.status})`;
                showToast(errorMsg);
            } else {
                console.warn('⚠️ 401 Unauthorized - возможно проблема с initData или авторизацией');
            }
        }
    } catch (error) {
        console.error('❌ Критическая ошибка загрузки данных пользователя:', {
            error: error,
            message: error.message,
            stack: error.stack,
            API_BASE: API_BASE,
            name: error.name
        });
        
        // Показываем пользователю понятное сообщение об ошибке
        let errorMessage = 'Ошибка подключения к серверу';
        
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            errorMessage = 'Не удалось подключиться к серверу. Проверьте интернет-соединение.';
        } else if (error.name === 'AbortError') {
            errorMessage = 'Таймаут подключения к серверу';
        } else if (error.message && (error.message.includes('JSON') || error.message.includes('Content-Type'))) {
            errorMessage = 'Ошибка подключения к серверу. Попробуйте позже.';
        } else if (error.message && (error.message.includes('fetch failed') || error.message.includes('Failed to fetch'))) {
            errorMessage = 'Не удалось подключиться к серверу. Проверьте интернет-соединение.';
        } else if (error.message) {
            errorMessage = `Ошибка: ${error.message}`;
        }
        
        showToast(errorMessage);
    }
}

// Обновить курс TON
async function updateTONRate() {
    try {
        const response = await fetch(`${API_BASE}/ton-rate`, {
            method: 'GET',
            headers: {
                'X-Telegram-Init-Data': getInitData()
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            appState.tonRate = parseFloat(data.rate) || 5.0;
            console.log(`✅ Курс TON обновлен: $${appState.tonRate.toFixed(2)} за 1 TON`);
            updateUI(); // Обновляем UI с новым курсом
        } else {
            console.warn('⚠️ Не удалось обновить курс TON, используется значение по умолчанию');
            // Используем значение по умолчанию если API не отвечает
            if (!appState.tonRate || appState.tonRate === 0) {
                appState.tonRate = 5.0;
            }
        }
    } catch (error) {
        console.error('❌ Ошибка обновления курса TON:', error);
        // Используем значение по умолчанию при ошибке
        if (!appState.tonRate || appState.tonRate === 0) {
            appState.tonRate = 5.0;
        }
    }
}

// Запустить периодическое обновление курса TON (каждые 10 минут)
function startTONRateUpdates() {
    // Обновляем сразу при загрузке
    updateTONRate();
    
    // Обновляем каждые 10 минут (600000 мс)
    if (appState.tonRateUpdateInterval) {
        clearInterval(appState.tonRateUpdateInterval);
    }
    appState.tonRateUpdateInterval = setInterval(updateTONRate, 600000);
}

// Обновить UI
function updateUI() {
    // Обновляем баланс (если элемент существует)
    const balanceAmountEl = document.getElementById('balance-amount');
    if (balanceAmountEl) {
        balanceAmountEl.textContent = `$${appState.balance.toFixed(2)}`;
    }
    
    // Обновляем баланс в TON (если элемент существует)
    const balanceTonEl = document.getElementById('balance-ton');
    if (balanceTonEl) {
        if (appState.balance > 0 && appState.tonRate > 0) {
            const balanceTon = appState.balance / appState.tonRate;
            balanceTonEl.textContent = `${balanceTon.toFixed(4)} TON`;
        } else {
            balanceTonEl.textContent = '0.0000 TON';
        }
    }
    
    // Обновляем базовую ставку (если элемент существует)
    const baseBetValueEl = document.getElementById('base-bet-value');
    if (baseBetValueEl) {
        baseBetValueEl.textContent = `$${appState.baseBet.toFixed(2)}`;
    }
    
    // Обновляем профиль (если элементы существуют)
    if (appState.user) {
        const profileNameEl = document.getElementById('profile-name');
        if (profileNameEl) {
            profileNameEl.textContent = 
                `${appState.user.firstName} ${appState.user.lastName || ''}`.trim();
        }
        
        const profileUsernameEl = document.getElementById('profile-username');
        if (profileUsernameEl) {
            profileUsernameEl.textContent = 
                appState.user.username ? `@${appState.user.username}` : '';
        }
        
        const userAvatarEl = document.getElementById('user-avatar');
        if (userAvatarEl && appState.user.photoUrl) {
            userAvatarEl.src = appState.user.photoUrl;
        }
    }
}

// Инициализация навигации
function initNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const page = btn.dataset.page;
            switchPage(page);
            
            // Обновляем активную кнопку
            navButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

// Переключение страниц
function switchPage(pageName) {
    // Скрываем все страницы
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // Скрываем контейнеры методов пополнения/вывода при переключении страниц
    const depositMethods = document.getElementById('deposit-methods');
    const withdrawMethods = document.getElementById('withdraw-methods');
    if (depositMethods) depositMethods.classList.add('hidden');
    if (withdrawMethods) withdrawMethods.classList.add('hidden');
    
    // Останавливаем автообновление топа, если уходим со страницы топа
    if (appState.currentPage === 'top' && pageName !== 'top') {
        stopTopAutoRefresh();
    }
    
    // Останавливаем автообновление рулетки, если уходим со страницы рулетки
    if (appState.currentPage === 'roulette' && pageName !== 'roulette') {
        closeRoulettePage();
    }
    
    // Показываем нужную страницу
    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.classList.add('active');
        appState.currentPage = pageName;
        
        // Обновляем UI перед загрузкой данных страницы
        updateUI();
        
        // Загружаем данные для страницы
        loadPageData(pageName);
    }
}

// Загрузить данные для страницы
async function loadPageData(pageName) {
    if (pageName === 'settings') {
        await loadSettings();
    }
    switch (pageName) {
        case 'play':
            await loadGames();
            break;
        case 'wallet':
            await loadWalletData();
            // При загрузке страницы кошелька скрываем контейнеры методов
            const depositMethods = document.getElementById('deposit-methods');
            const withdrawMethods = document.getElementById('withdraw-methods');
            if (depositMethods) depositMethods.classList.add('hidden');
            if (withdrawMethods) withdrawMethods.classList.add('hidden');
            break;
        case 'profile':
            await loadProfileData();
            break;
        case 'wallet':
            // Кошелек теперь доступен через профиль, но оставляем для обратной совместимости
            await loadWalletData();
            break;
        case 'top':
            // Загружаем топ с периодом "day" по умолчанию
            await loadTopData('players', 'day');
            // Запускаем автоматическое обновление топа каждые 30 секунд
            startTopAutoRefresh();
            break;
        case 'settings':
            await loadSettings();
            break;
        case 'roulette':
            await openRoulettePage();
            break;
    }
}

// Загрузить игры
async function loadGames() {
    const gamesGrid = document.getElementById('games-grid');
    const games = [
        { id: 'dice', name: 'Кубик', baseSticker: 'dice_base' },
        { id: 'dart', name: 'Дартс', baseSticker: 'darts_base' },
        { id: 'bowling', name: 'Боулинг', baseSticker: 'bowling_base' },
        { id: 'football', name: 'Футбол', baseSticker: 'football_base' },
        { id: 'basketball', name: 'Баскетбол', baseSticker: 'basketball_base' },
        { id: 'slots', name: 'Слоты', baseSticker: 'slots_base' }
    ];
    
    // Сначала показываем карточки игр с плейсхолдерами загрузки
    gamesGrid.innerHTML = games.map(game => `
        <div class="game-card" data-game="${game.id}">
            <div class="game-sticker" data-sticker="${game.baseSticker}">
                <div style="width: 100%; height: 100%; background: rgba(0,255,136,0.1); border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                    <div class="loading-circle" style="width: 30px; height: 30px; border-width: 3px;"></div>
                </div>
            </div>
            <div class="game-name">${game.name}</div>
        </div>
    `).join('');
    
    // Загружаем стикеры для каждой игры параллельно
    const loadPromises = games.map(async (game) => {
        const stickerElement = gamesGrid.querySelector(`[data-sticker="${game.baseSticker}"]`);
        if (stickerElement) {
            try {
                // Принудительно перезагружаем стикер (очищаем перед загрузкой)
                stickerElement.innerHTML = '';
                await loadStickerForElement(stickerElement, game.baseSticker);
            } catch (error) {
                console.error(`Ошибка загрузки стикера ${game.baseSticker}:`, error);
                // Оставляем плейсхолдер при ошибке
            }
        }
    });
    
    // Ждем загрузки всех стикеров
    await Promise.all(loadPromises);
    
    // Добавляем обработчики кликов
    document.querySelectorAll('.game-card').forEach(card => {
        card.addEventListener('click', () => {
            const gameId = card.dataset.game;
            startGame(gameId);
        });
        
        // Добавляем пульсирующую анимацию при наведении
        card.addEventListener('mouseenter', function() {
            if (!this.classList.contains('pulsating')) {
                this.classList.add('pulsating');
                this.style.animation = 'pulseGlow 2s infinite';
            }
        });
        card.addEventListener('mouseleave', function() {
            this.classList.remove('pulsating');
            this.style.animation = '';
        });
    });
}

// Начать игру
async function startGame(gameId) {
    // Открываем страницу игры вместо модального окна
    showGamePage(gameId);
}

// Показать модальное окно выбора режима игры
// Показать страницу игры
function showGamePage(gameId) {
    const gameNames = {
        'dice': 'Кубик',
        'dart': 'Дартс',
        'bowling': 'Боулинг',
        'football': 'Футбол',
        'basketball': 'Баскетбол',
        'slots': 'Слоты'
    };
    
    const gameName = gameNames[gameId] || 'Игра';
    
    // Сохраняем текущий gameId для использования в обработчиках
    appState.currentGameId = gameId;
    appState.selectedGameMode = null;
    appState.selectedBet = appState.baseBet;
    
    // Обновляем заголовок страницы
    const gamePageTitle = document.getElementById('game-page-title');
    if (gamePageTitle) {
        gamePageTitle.textContent = gameName;
    }
    
    // Инициализируем шаг 1: Выбор ставки
    const isSlots = gameId === 'slots';
    
    // Для слотов устанавливаем selectedBet из baseBet
    if (isSlots) {
        appState.selectedBet = appState.baseBet || 1.0;
    }
    
    initBetStep({ nextStep: isSlots ? 'slots' : 'modes' });
    
    if (!isSlots) {
        // Инициализируем шаг 2: Выбор режима
        initModesStep(gameId);
        
        // Инициализируем шаг 3: Подтверждение
        initStartStep(gameId);
    } else {
        // Инициализация экрана слотов (визуал + призы)
        initSlotsStep();
    }
    
    // Обработчик кнопки "Назад"
    const backBtn = document.getElementById('btn-back-to-games');
    if (backBtn) {
        backBtn.onclick = () => {
            switchPage('play');
        };
    }
    
    // Показываем первый шаг
    showGameStep('bet');
    
    // Переключаемся на страницу игры
    switchPage('game');
}

// Показать конкретный шаг игры
function showGameStep(stepName) {
    const steps = ['bet', 'modes', 'start', 'slots'];
    steps.forEach(step => {
        const stepEl = document.getElementById(`game-step-${step}`);
        if (stepEl) {
            if (step === stepName) {
                stepEl.classList.remove('hidden');
                stepEl.classList.add('active');
            } else {
                stepEl.classList.add('hidden');
                stepEl.classList.remove('active');
            }
        }
    });
}

// Инициализация шага выбора ставки
function initBetStep(options = {}) {
    const nextStep = options.nextStep || 'modes';

    // Клонируем input, чтобы не накапливались обработчики при повторном открытии страницы игры
    let betInput = document.getElementById('game-bet-input');
    if (betInput) {
        const newBetInput = betInput.cloneNode(true);
        betInput.parentNode.replaceChild(newBetInput, betInput);
        betInput = newBetInput;
    }

    if (betInput) {
        betInput.value = appState.baseBet.toFixed(2);
        
        // Обновляем значение базовой ставки в кнопке
        const betBaseValue = document.getElementById('bet-base-value');
        if (betBaseValue) {
            betBaseValue.textContent = `$${appState.baseBet.toFixed(2)}`;
        }
        
        // Обработчик изменения ставки
        betInput.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value) || 0;
            if (value > 0) {
                appState.selectedBet = Math.min(Math.max(value, 0.1), 30);
                e.target.value = appState.selectedBet.toFixed(2);
            }
            updateBetQuickButtons();
        });
    }
    
    // Кнопки быстрого выбора ставки
    let betBtnMin = document.getElementById('bet-btn-min');
    let betBtnBase = document.getElementById('bet-btn-base');
    let betBtnMax = document.getElementById('bet-btn-max');

    // Клонируем кнопки для сброса обработчиков
    if (betBtnMin && betBtnMin.parentNode) {
        const clone = betBtnMin.cloneNode(true);
        betBtnMin.parentNode.replaceChild(clone, betBtnMin);
        betBtnMin = clone;
    }
    if (betBtnBase && betBtnBase.parentNode) {
        const clone = betBtnBase.cloneNode(true);
        betBtnBase.parentNode.replaceChild(clone, betBtnBase);
        betBtnBase = clone;
    }
    if (betBtnMax && betBtnMax.parentNode) {
        const clone = betBtnMax.cloneNode(true);
        betBtnMax.parentNode.replaceChild(clone, betBtnMax);
        betBtnMax = clone;
    }
    
    if (betBtnMin) {
        betBtnMin.addEventListener('click', () => {
            setBetValue(0.1);
        });
    }
    
    if (betBtnBase) {
        betBtnBase.addEventListener('click', () => {
            setBetValue(appState.baseBet);
        });
    }
    
    if (betBtnMax) {
        betBtnMax.addEventListener('click', () => {
            setBetValue(30);
        });
    }
    
    // Кнопка "Далее"
    const btnNextToModes = document.getElementById('btn-next-to-modes');
    if (btnNextToModes && btnNextToModes.parentNode) {
        const btn = btnNextToModes.cloneNode(true);
        btnNextToModes.parentNode.replaceChild(btn, btnNextToModes);
        btn.addEventListener('click', () => {
            const betInput = document.getElementById('game-bet-input');
            const bet = parseFloat(betInput?.value || appState.baseBet);
            
            if (isNaN(bet) || bet < 0.1) {
                showToast('Минимальная ставка: $0.10');
                return;
            }
            
            if (bet > 30) {
                showToast('Максимальная ставка: $30.00');
                return;
            }
            
            // Проверяем баланс
            if (appState.balance < bet) {
                showToast(`Недостаточно средств! Нужно $${bet.toFixed(2)}, у вас $${appState.balance.toFixed(2)}`);
                return;
            }
            
            appState.selectedBet = bet;
            if (nextStep === 'slots') {
                initSlotsStep();
                showGameStep('slots');
            } else {
                showGameStep(nextStep);
            }
        });
    }
    
    updateBetQuickButtons();
}

// Установить значение ставки
function setBetValue(value) {
    appState.selectedBet = Math.min(Math.max(value, 0.1), 30);
    const betInput = document.getElementById('game-bet-input');
    if (betInput) {
        betInput.value = appState.selectedBet.toFixed(2);
    }
    updateBetQuickButtons();
}

// Обновить состояние кнопок быстрого выбора ставки
function updateBetQuickButtons() {
    const betInput = document.getElementById('game-bet-input');
    const currentBet = parseFloat(betInput?.value || appState.baseBet);
    
    const betBtnMin = document.getElementById('bet-btn-min');
    const betBtnBase = document.getElementById('bet-btn-base');
    const betBtnMax = document.getElementById('bet-btn-max');
    
    [betBtnMin, betBtnBase, betBtnMax].forEach(btn => {
        if (btn) btn.classList.remove('active');
    });
    
    if (Math.abs(currentBet - 0.1) < 0.01 && betBtnMin) {
        betBtnMin.classList.add('active');
    } else if (Math.abs(currentBet - appState.baseBet) < 0.01 && betBtnBase) {
        betBtnBase.classList.add('active');
    } else if (Math.abs(currentBet - 30) < 0.01 && betBtnMax) {
        betBtnMax.classList.add('active');
    }
}

// Инициализация шага выбора режима
function initModesStep(gameId) {
    const modes = getGameModes(gameId);
    const modesContainer = document.getElementById('game-modes-container');
    if (modesContainer) {
        modesContainer.innerHTML = modes.map(mode => `
            <button class="game-mode-btn" data-mode="${mode.value}">
                <span class="mode-name">${mode.name.split(' x')[0]}</span>
                <span class="mode-multiplier">x${mode.name.split(' x')[1] || ''}</span>
            </button>
        `).join('');
    }
    
    // Обработчики выбора режима
    const modeButtons = modesContainer?.querySelectorAll('.game-mode-btn') || [];
    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Убираем выделение с других кнопок
            modeButtons.forEach(b => {
                b.classList.remove('active');
            });
            
            // Выделяем выбранную кнопку
            btn.classList.add('active');
            appState.selectedGameMode = btn.dataset.mode;
            
            // Активируем кнопку "Далее"
            const btnNextToStart = document.getElementById('btn-next-to-start');
            if (btnNextToStart) {
                btnNextToStart.disabled = false;
            }
        });
    });
    
    // Кнопка "Назад" к выбору ставки
    const btnBackToBet = document.getElementById('btn-back-to-bet');
    if (btnBackToBet) {
        btnBackToBet.addEventListener('click', () => {
            showGameStep('bet');
        });
    }
    
    // Кнопка "Далее" к подтверждению
    const btnNextToStart = document.getElementById('btn-next-to-start');
    if (btnNextToStart) {
        // Изначально отключаем кнопку
        btnNextToStart.disabled = true;
        
        btnNextToStart.addEventListener('click', () => {
            if (!appState.selectedGameMode) {
                showToast('Выберите режим игры');
                return;
            }
            updateStartStep();
            showGameStep('start');
        });
    }
}

// Инициализация шага подтверждения и запуска
function initStartStep(gameId) {
    const startBtn = document.getElementById('start-game-btn');
    if (startBtn) {
        // Удаляем старые обработчики, заменяя кнопку
        const newStartBtn = startBtn.cloneNode(true);
        startBtn.parentNode.replaceChild(newStartBtn, startBtn);
        
        // Добавляем обработчик запуска игры
        newStartBtn.addEventListener('click', async () => {
            // Проверяем, не идет ли уже игра
            if (appState.gameInProgress) {
                showToast('Игра уже запущена! Дождитесь завершения текущей игры.');
                return;
            }
            
            if (!appState.selectedGameMode) {
                showToast('Выберите режим игры');
                return;
            }
            
            const bet = appState.selectedBet;
            
            if (isNaN(bet) || bet < 0.1) {
                showToast('Минимальная ставка: $0.10');
                return;
            }
            
            if (bet > 30) {
                showToast('Максимальная ставка: $30.00');
                return;
            }
            
            // Проверяем баланс перед запуском
            if (appState.balance < bet) {
                showToast(`Недостаточно средств! Нужно $${bet.toFixed(2)}, у вас $${appState.balance.toFixed(2)}`);
                return;
            }
            
            // Блокируем кнопку и запускаем игру
            appState.gameInProgress = true;
            newStartBtn.disabled = true;
            newStartBtn.style.opacity = '0.5';
            newStartBtn.style.cursor = 'not-allowed';
            newStartBtn.textContent = 'Игра запущена...';
            
            try {
                await launchGame(gameId, bet, appState.selectedGameMode);
            } catch (error) {
                // В случае ошибки разблокируем кнопку
                appState.gameInProgress = false;
                newStartBtn.disabled = false;
                newStartBtn.style.opacity = '1';
                newStartBtn.style.cursor = 'pointer';
                newStartBtn.textContent = 'Начать игру';
            }
        });
    }
    
    // Кнопка "Назад" к выбору режима
    const btnBackToModes = document.getElementById('btn-back-to-modes');
    if (btnBackToModes) {
        btnBackToModes.addEventListener('click', () => {
            showGameStep('modes');
        });
    }
}

// Обновить шаг подтверждения
function updateStartStep() {
    const summaryBet = document.getElementById('summary-bet');
    const summaryMode = document.getElementById('summary-mode');
    
    if (summaryBet) {
        summaryBet.textContent = `$${appState.selectedBet.toFixed(2)}`;
    }
    
    if (summaryMode) {
        const modes = getGameModes(appState.currentGameId);
        const selectedMode = modes.find(m => m.value === appState.selectedGameMode);
        if (selectedMode) {
            summaryMode.textContent = selectedMode.name;
        } else {
            summaryMode.textContent = '-';
        }
    }
}

// Извлечь коэффициент из названия режима (например, "x1.9" -> 1.9)
function extractCoefficient(modeName) {
    const match = modeName.match(/x([\d.]+)/);
    if (match && match[1]) {
        return parseFloat(match[1]);
    }
    // Если коэффициент не найден, возвращаем 0 (такие режимы будут в начале)
    return 0;
}

// Получить доступные режимы для игры (как в боте), отсортированные по возрастанию коэффициентов
function getGameModes(gameId) {
    const modesMap = {
        'dice': [
            { value: 'even', name: 'Чет x1.9' },
            { value: 'odd', name: 'Нечет x1.9' },
            { value: '3_even', name: '3 Чет x7' },
            { value: '3_odd', name: '3 Нечет x7' },
            { value: 'exact_1', name: '1 x5.55' },
            { value: 'exact_2', name: '2 x5.55' },
            { value: 'exact_3', name: '3 x5.55' },
            { value: 'exact_4', name: '4 x5.55' },
            { value: 'exact_5', name: '5 x5.55' },
            { value: 'exact_6', name: '6 x5.55' },
            { value: 'pair', name: 'Пара x5.55' },
            { value: '18', name: '18 x8' },
            { value: '21', name: '21 x11' },
            { value: '111', name: '111 x100' },
            { value: '333', name: '333 x100' },
            { value: '666', name: '666 x100' },
            { value: 'dice_7_more_7', name: '>7 x2.4' },
            { value: 'dice_7_less_7', name: '<7 x2.4' },
            { value: 'dice_7_equal_7', name: '=7 x6.0' }
        ],
        'dart': [
            { value: 'white', name: 'Белое x2' },
            { value: 'red', name: 'Красное x1.4' },
            { value: 'center', name: 'Центр x6' },
            { value: 'miss', name: 'Отскок x6' },
            { value: '3_red', name: '3 Красных x7' },
            { value: '3_white', name: '3 Белых x21' },
            { value: '3_center', name: '3 в Центр x100' },
            { value: '3_miss', name: '3 Мимо x100' }
        ],
        'bowling': [
            { value: '0-3', name: '0-3 шт x1.9' },
            { value: '4-6', name: '4-6 шт x1.9' },
            { value: 'strike', name: 'Страйк x5' },
            { value: 'miss', name: 'Промах x5' },
            { value: '2_strike', name: '2 Страйка x30' },
            { value: '2_miss', name: '2 Мимо x30' },
            { value: '3_strike', name: '3 Страйка x100' },
            { value: '3_miss', name: '3 Мимо x100' }
        ],
        'football': [
            { value: 'goal', name: 'Гол x1.4' },
            { value: 'miss', name: 'Промах x2.5' },
            { value: 'center', name: 'В центр x1.9' },
            { value: 'hattrick', name: 'Хет-трик x4' },
            { value: '5_goals', name: '5 Голов x11' },
            { value: '10_goals', name: '10 Голов x100' },
            { value: '6_miss', name: '6 Промахов x100' }
        ],
        'basketball': [
            { value: 'hit', name: 'Гол x2' },
            { value: 'miss', name: 'Мимо x1.4' },
            { value: 'clean', name: 'Чистый гол x6' },
            { value: 'stuck', name: 'Застрял x5' },
            { value: '2_hit', name: '2 Попал x5' },
            { value: '2_clean', name: '2 Чистых x15' },
            { value: '3_hit', name: '3 Попал x12' },
            { value: '3_clean', name: '3 Чистых x77' },
            { value: '6_hit', name: '6 Попал x100' }
        ]
    };
    
    const modes = modesMap[gameId] || [{ value: 'even', name: 'Четное' }];
    
    // Сортируем режимы по возрастанию коэффициентов
    return modes.sort((a, b) => {
        const coeffA = extractCoefficient(a.name);
        const coeffB = extractCoefficient(b.name);
        return coeffA - coeffB;
    });
}

/* ===== СЛОТЫ (1 прокрут) ===== */
const SLOT_SYMBOLS = [
    { key: 'seven', name: '7', src: 'assets/seven.svg', emoji: '7️⃣' },
    { key: 'grape', name: 'Виноград', src: 'assets/grape.svg', emoji: '🍇' },
    { key: 'lemon', name: 'Лимон', src: 'assets/lemon.svg', emoji: '🍋' },
    { key: 'bar', name: 'BAR', src: 'assets/bar.svg', emoji: 'BAR' }
];

// Множители призов (только комбинации из 3 одинаковых символов)
const SLOT_MULTIPLIERS = {
    '777': 20,              // 777 - 20x
    'grape_grape_grape': 10, // 🍇🍇🍇 - 10x
    'lemon_lemon_lemon': 7,  // 🍋🍋🍋 - 7x
    'bar_bar_bar': 5        // BAR BAR BAR - 5x
};

const slotsUiState = {
    spinIntervals: [null, null, null],
    spinTokens: [0, 0, 0],
    revealTimeouts: []
};

function getSlotSymbol(key) {
    return SLOT_SYMBOLS.find(s => s.key === key) || SLOT_SYMBOLS[0];
}

function normalizeSlotToken(token) {
    const t = String(token || '').trim();
    if (!t) return null;
    const tLower = t.toLowerCase();
    // Поддержка разных форматов символов
    if (tLower === '7' || tLower === 'seven' || tLower === 'семь' || t === '7️⃣') return 'seven';
    if (tLower === 'grape' || tLower === 'виноград' || tLower === 'виног' || t === '🍒' || t === '🍇' || tLower === 'cherry') return 'grape';
    if (tLower === 'lemon' || tLower === 'лимон' || t === '🍌' || t === '🍋' || tLower === 'banana') return 'lemon';
    if (tLower === 'bar' || tLower === 'бар' || tLower === 'bak' || t === 'Bar' || t === 'BAR') return 'bar';
    return null;
}

// Вычислить выигрыш на основе символов (только комбинации из 3 одинаковых символов)
function calculateSlotsWin(symbols, bet) {
    if (!Array.isArray(symbols) || symbols.length !== 3) return 0;
    
    const [s1, s2, s3] = symbols.map(normalizeSlotToken);
    
    // Проверяем только комбинации из 3 одинаковых символов
    if (s1 === s2 && s2 === s3) {
        const comboKey = `${s1}_${s2}_${s3}`;
        if (comboKey === 'seven_seven_seven') {
            return bet * SLOT_MULTIPLIERS['777'];
        } else if (comboKey === 'lemon_lemon_lemon') {
            return bet * SLOT_MULTIPLIERS['lemon_lemon_lemon'];
        } else if (comboKey === 'grape_grape_grape') {
            return bet * SLOT_MULTIPLIERS['grape_grape_grape'];
        } else if (comboKey === 'bar_bar_bar') {
            return bet * SLOT_MULTIPLIERS['bar_bar_bar'];
        }
    }
    
    // Если нет выигрышной комбинации, возвращаем 0
    return 0;
}

function extractSlotsSymbols(result) {
    const candidates =
        (Array.isArray(result?.symbols) && result.symbols) ||
        (Array.isArray(result?.throws) && result.throws) ||
        (Array.isArray(result?.result) && result.result) ||
        null;

    let raw = [];
    if (candidates) {
        raw = candidates;
    } else if (typeof result?.result === 'string') {
        raw = result.result.split(/[,\s|/]+/g).filter(Boolean);
    }

    const normalized = raw
        .map(normalizeSlotToken)
        .filter(Boolean);

    if (normalized.length >= 3) return normalized.slice(0, 3);

    // Fallback: случайные символы (чтобы UI не ломался, если бэк пришлет другой формат)
    const fallback = [];
    for (let i = 0; i < 3; i++) {
        fallback.push(SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)].key);
    }
    return fallback;
}

function clearSlotsRevealTimeouts() {
    slotsUiState.revealTimeouts.forEach(t => clearTimeout(t));
    slotsUiState.revealTimeouts = [];
}

function stopAllSlotSpinners() {
    for (let i = 0; i < 3; i++) {
        // Инвалидируем все отложенные "тики" для этой строки
        slotsUiState.spinTokens[i] += 1;
        if (slotsUiState.spinIntervals[i]) {
            clearInterval(slotsUiState.spinIntervals[i]);
            slotsUiState.spinIntervals[i] = null;
        }
    }
}

function setSlotsSpinButtonState() {
    const btn = document.getElementById('slots-spin-btn');
    if (!btn) return;

    if (appState.gameInProgress) {
        btn.disabled = true;
        btn.textContent = 'Крутим...';
        return;
    }

    if (appState.slotsSpinUsed) {
        btn.disabled = false;
        btn.textContent = 'Повторить';
        return;
    }

    btn.disabled = false;
    btn.textContent = 'Крутить (1 раз)';
}

function renderSlotsPrizes(bet) {
    const container = document.getElementById('slots-prizes');
    if (!container) return;

    const safeBet = Math.max(0, Number(bet) || 0);
    const dollarIcon = 'assets/dollar-svgrepo-com.svg';

    // Комбинации из 3 символов
    const combos = [
        { symbols: ['seven', 'seven', 'seven'], multiplier: SLOT_MULTIPLIERS['777'], name: '777' },
        { symbols: ['grape', 'grape', 'grape'], multiplier: SLOT_MULTIPLIERS['grape_grape_grape'], name: 'Виноград' },
        { symbols: ['lemon', 'lemon', 'lemon'], multiplier: SLOT_MULTIPLIERS['lemon_lemon_lemon'], name: 'Лимон' },
        { symbols: ['bar', 'bar', 'bar'], multiplier: SLOT_MULTIPLIERS['bar_bar_bar'], name: 'BAR' }
    ];

    container.innerHTML = combos.map(combo => {
        const sym = getSlotSymbol(combo.symbols[0]);
        const amount = safeBet * combo.multiplier;
        return `
            <div class="slots-prize-item">
                <div class="slots-prize-left">
                    <div class="slots-prize-symbols">
                        <img class="slots-prize-symbol" src="${sym.src}" alt="${sym.name}">
                        <img class="slots-prize-symbol" src="${sym.src}" alt="${sym.name}">
                        <img class="slots-prize-symbol" src="${sym.src}" alt="${sym.name}">
                    </div>
                    <div class="slots-prize-name">
                        ${combo.name}<span class="slots-prize-mult">x${combo.multiplier}</span>
                    </div>
                </div>
                <div class="slots-prize-right">
                    <img class="slots-dollar" src="${dollarIcon}" alt="$">
                    <span>$${amount.toFixed(2)}</span>
                </div>
            </div>
        `;
    }).join('');
}

function setSlotsBetDisplay() {
    // Убеждаемся что selectedBet установлен из baseBet
    if (!appState.selectedBet || appState.selectedBet === 0) {
        appState.selectedBet = appState.baseBet || 1.0;
    }
    
    // Обновляем отображение баланса
    const balanceEl = document.getElementById('slots-balance-amount');
    if (balanceEl) {
        balanceEl.textContent = `$${appState.balance.toFixed(2)}`;
    }
    
    // Обновляем отображение ставки
    const betEl = document.getElementById('slots-bet-amount');
    if (betEl) {
        betEl.textContent = `$${appState.selectedBet.toFixed(2)}`;
    }
    
    renderSlotsPrizes(appState.selectedBet);
    
    console.log('🎰 Слоты: данные обновлены:', {
        balance: appState.balance,
        selectedBet: appState.selectedBet,
        baseBet: appState.baseBet
    });
}

function resetSlotsRows() {
    clearSlotsRevealTimeouts();
    stopAllSlotSpinners();

    for (let i = 0; i < 3; i++) {
        const reel = document.getElementById(`slots-reel-${i}`);
        const strip = document.getElementById(`slots-strip-${i}`);
        if (!reel || !strip) continue;

        reel.classList.remove('is-blurred');
        strip.style.transition = 'none';
        strip.style.transform = 'translateY(0px)';
        strip.style.paddingTop = ''; // Сбрасываем padding
        strip.style.justifyContent = 'flex-start'; // Возвращаем стандартное выравнивание
        strip.innerHTML = '';

        // Плейсхолдер: 3 символа для каждого барабана (3x3 сетка)
        for (let j = 0; j < 3; j++) {
            const placeholder = SLOT_SYMBOLS[(i + j) % SLOT_SYMBOLS.length];
            const img = document.createElement('img');
            img.className = 'slots-symbol';
            img.src = placeholder.src;
            img.alt = placeholder.name;
            img.style.opacity = '0.55';
            strip.appendChild(img);
        }
    }
}

function startRowSpin(rowIndex, targetSymbol = null) {
    const reel = document.getElementById(`slots-reel-${rowIndex}`);
    const strip = document.getElementById(`slots-strip-${rowIndex}`);
    if (!reel || !strip) return;

    reel.classList.add('is-blurred');
    reel.classList.add('is-spinning');
    strip.style.transition = 'none';
    strip.style.transform = 'translateY(0px)';
    strip.innerHTML = '';

    // Заполняем ленту символами с большим gap между ними
    const itemsCount = 50; // Больше символов для плавной прокрутки
    const targetSym = targetSymbol ? getSlotSymbol(targetSymbol) : null;
    
    // Создаем ленту, гарантируя что целевой символ будет в нужной позиции
    for (let i = 0; i < itemsCount; i++) {
        let sym;
        // Если это позиция где должен быть целевой символ (ближе к концу), используем его
        if (targetSym && i >= itemsCount - 8 && i < itemsCount - 2) {
            sym = targetSym;
        } else {
            sym = SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
        }
        const img = document.createElement('img');
        img.className = 'slots-symbol';
        img.src = sym.src;
        img.alt = sym.name;
        strip.appendChild(img);
    }

    // Увеличиваем stepPx для большего расстояния между символами (96px вместо 88px)
    const stepPx = 96; // высота символа (80px) + увеличенный gap (16px)
    let position = 0;
    let speed = 10; // Еще более быстрая скорость для максимальной плавности
    let busy = false;
    const token = (slotsUiState.spinTokens[rowIndex] += 1);
    
    // Вычисляем целевую позицию для остановки (если есть целевой символ)
    const targetPosition = targetSym ? (itemsCount - 5) * stepPx : null;
    
    const spin = () => {
        if (busy) return;
        busy = true;

        position += stepPx;
        
        // Если приближаемся к целевой позиции, начинаем замедление
        let currentSpeed = speed;
        if (targetPosition && position >= targetPosition - stepPx * 4) {
            // Замедляем при приближении к цели
            const distanceToTarget = targetPosition - position;
            if (distanceToTarget > 0) {
                currentSpeed = Math.max(speed, Math.min(250, speed + (distanceToTarget / stepPx) * 8));
            } else if (position >= targetPosition) {
                // Достигли цели - останавливаемся
                strip.style.transition = 'none';
                strip.style.transform = `translateY(-${targetPosition}px)`;
                busy = false;
                return;
            }
        }
        
        // Максимально плавная timing функция
        strip.style.transition = `transform ${currentSpeed}ms cubic-bezier(0.1, 0, 0.1, 1)`;
        strip.style.transform = `translateY(-${position}px)`;

        setTimeout(() => {
            // Если спин уже остановили/перезапустили — выходим
            if (token !== slotsUiState.spinTokens[rowIndex]) return;
            
            // Если достигли целевой позиции, останавливаемся
            if (targetPosition && position >= targetPosition) {
                strip.style.transition = 'none';
                strip.style.transform = `translateY(-${targetPosition}px)`;
                busy = false;
                return;
            }
            
            strip.style.transition = 'none';
            
            // Сбрасываем позицию и перемещаем элементы для бесконечной прокрутки
            const currentY = position % (stepPx * itemsCount);
            strip.style.transform = `translateY(-${currentY}px)`;
            
            // Перемещаем элементы для бесконечной прокрутки
            while (position >= stepPx) {
                if (strip.lastElementChild) {
                    strip.insertBefore(strip.lastElementChild, strip.firstElementChild);
                }
                position -= stepPx;
            }
            
            // Плавное замедление
            if (speed < 180) {
                speed += 0.6;
            }
            
            busy = false;
        }, currentSpeed + 1);
    };
    
    slotsUiState.spinIntervals[rowIndex] = setInterval(spin, speed);
}

function startSlotsSpinVisual(targetSymbols = null) {
    clearSlotsRevealTimeouts();
    stopAllSlotSpinners();
    for (let i = 0; i < 3; i++) {
        const targetSymbol = targetSymbols && targetSymbols[i] ? targetSymbols[i] : null;
        startRowSpin(i, targetSymbol);
    }
}

function stopSingleSlotReel(index, symbolKey) {
    const reel = document.getElementById(`slots-reel-${index}`);
    const strip = document.getElementById(`slots-strip-${index}`);
    if (!reel || !strip) return;

    // Останавливаем спин для этого барабана
    slotsUiState.spinTokens[index] += 1;
    if (slotsUiState.spinIntervals[index]) {
        clearInterval(slotsUiState.spinIntervals[index]);
        slotsUiState.spinIntervals[index] = null;
    }

    const sym = getSlotSymbol(symbolKey);
    
    // Определяем размеры в зависимости от размера экрана
    const isMobile = window.innerWidth <= 480;
    const isSmallMobile = window.innerWidth <= 360;
    const largeSymbolHeight = isSmallMobile ? 220 : (isMobile ? 200 : 120); // Большой центральный символ
    const smallSymbolHeight = isSmallMobile ? 100 : (isMobile ? 90 : 50); // Маленькие размытые символы
    const gap = isSmallMobile ? 28 : (isMobile ? 24 : 16);
    const windowHeight = isSmallMobile ? 340 : (isMobile ? 320 : 220); // Высота окна барабана
    const windowCenter = windowHeight / 2; // центр окна
    const padding = isSmallMobile ? 20 : (isMobile ? 16 : 8); // padding strip
    
    // Создаем ленту: только 3 символа - размытый сверху, большой в центре, размытый снизу
    strip.innerHTML = '';
    strip.style.transition = 'none';
    strip.style.justifyContent = 'flex-start'; // Начинаем сверху
    
    // Случайный символ сверху (размытый, маленький)
    const topRandomSym = SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
    const topImg = document.createElement('img');
    topImg.className = 'slots-symbol slots-symbol-blurred';
    topImg.src = topRandomSym.src;
    topImg.alt = topRandomSym.name;
    // Не устанавливаем inline стили для размеров - используем CSS классы
    strip.appendChild(topImg);
    
    // Большой центральный символ (выигрышный)
    const targetImg = document.createElement('img');
    targetImg.className = 'slots-symbol slots-symbol-final slots-symbol-final-large';
    targetImg.src = sym.src;
    targetImg.alt = sym.name;
    // Не устанавливаем inline стили для размеров - используем CSS классы
    strip.appendChild(targetImg);
    
    // Случайный символ снизу (размытый, маленький)
    const bottomRandomSym = SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
    const bottomImg = document.createElement('img');
    bottomImg.className = 'slots-symbol slots-symbol-blurred';
    bottomImg.src = bottomRandomSym.src;
    bottomImg.alt = bottomRandomSym.name;
    // Не устанавливаем inline стили для размеров - используем CSS классы
    strip.appendChild(bottomImg);
    
    // Вычисляем позицию чтобы большой символ (индекс 1) был в центре окна или немного ниже
    // Учитываем padding сверху для смещения вниз
    const paddingTop = isSmallMobile ? 45 : (isMobile ? 50 : 60); // padding-top из CSS (обновлено)
    const largeSymbolCenterY = windowCenter + 15; // центр окна + небольшое смещение вниз
    
    // Позиция центра большого символа в текущей структуре strip (с учетом padding-top)
    const topSymbolHeight = paddingTop + smallSymbolHeight + gap; // padding-top + высота верхнего символа + gap
    const currentLargeSymbolCenterY = topSymbolHeight + (largeSymbolHeight / 2);
    
    // Вычисляем смещение для центрирования (отрицательное значение смещает вниз)
    const offset = currentLargeSymbolCenterY - largeSymbolCenterY;
    
    // Плавно центрируем большой символ (смещаем вниз)
    strip.style.transition = 'transform 600ms cubic-bezier(0.2, 0, 0.2, 1)';
    // Всегда смещаем вниз для лучшей видимости
    strip.style.transform = `translateY(-${Math.max(offset, 20)}px)`;
    
    // Убираем blur плавно
    setTimeout(() => {
        reel.classList.remove('is-blurred');
        reel.classList.remove('is-spinning');
    }, 500);
}

function stopSlotsSpinWithResult(symbolKeys) {
    // Останавливаем все барабаны сразу (используется при инициализации, когда показываем сохраненные результаты)
    stopAllSlotSpinners();

    // Определяем размеры в зависимости от размера экрана
    const isMobile = window.innerWidth <= 480;
    const isSmallMobile = window.innerWidth <= 360;
    const largeSymbolHeight = isSmallMobile ? 220 : (isMobile ? 200 : 120); // Большой центральный символ
    const smallSymbolHeight = isSmallMobile ? 100 : (isMobile ? 90 : 50); // Маленькие размытые символы
    const gap = isSmallMobile ? 28 : (isMobile ? 24 : 16);
    const windowHeight = isSmallMobile ? 340 : (isMobile ? 320 : 220); // Высота окна барабана
    const windowCenter = windowHeight / 2; // центр окна
    const padding = isSmallMobile ? 20 : (isMobile ? 16 : 8); // padding strip

    for (let i = 0; i < 3; i++) {
        const reel = document.getElementById(`slots-reel-${i}`);
        const strip = document.getElementById(`slots-strip-${i}`);
        if (!reel || !strip) continue;

        const sym = getSlotSymbol(symbolKeys[i]);
        
        // Создаем ленту: только 3 символа - размытый сверху, большой в центре, размытый снизу
        strip.innerHTML = '';
        strip.style.transition = 'none';
        strip.style.justifyContent = 'flex-start'; // Начинаем сверху для правильного позиционирования
        
        // Случайный символ сверху (размытый, маленький)
        const topRandomSym = SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
        const topImg = document.createElement('img');
        topImg.className = 'slots-symbol slots-symbol-blurred';
        topImg.src = topRandomSym.src;
        topImg.alt = topRandomSym.name;
        // Не устанавливаем inline стили для размеров - используем CSS классы
        strip.appendChild(topImg);
        
        // Большой центральный символ (выигрышный)
        const targetImg = document.createElement('img');
        targetImg.className = 'slots-symbol slots-symbol-final slots-symbol-final-large';
        targetImg.src = sym.src;
        targetImg.alt = sym.name;
        // Не устанавливаем inline стили для размеров - используем CSS классы
        strip.appendChild(targetImg);
        
        // Случайный символ снизу (размытый, маленький)
        const bottomRandomSym = SLOT_SYMBOLS[Math.floor(Math.random() * SLOT_SYMBOLS.length)];
        const bottomImg = document.createElement('img');
        bottomImg.className = 'slots-symbol slots-symbol-blurred';
        bottomImg.src = bottomRandomSym.src;
        bottomImg.alt = bottomRandomSym.name;
        // Не устанавливаем inline стили для размеров - используем CSS классы
        strip.appendChild(bottomImg);
        
        // Вычисляем позицию чтобы большой символ (индекс 1) был в центре окна или немного ниже
        // Учитываем padding сверху для смещения вниз
        const paddingTop = isSmallMobile ? 45 : (isMobile ? 50 : 60); // padding-top из CSS (обновлено)
        const largeSymbolCenterY = windowCenter + 15; // центр окна + небольшое смещение вниз
        
        // Позиция центра большого символа в текущей структуре strip (с учетом padding-top)
        const topSymbolHeight = paddingTop + smallSymbolHeight + gap; // padding-top + высота верхнего символа + gap
        const currentLargeSymbolCenterY = topSymbolHeight + (largeSymbolHeight / 2);
        
        // Вычисляем смещение для центрирования (отрицательное значение смещает вниз)
        const offset = currentLargeSymbolCenterY - largeSymbolCenterY;
        
        // Плавно центрируем большой символ (смещаем вниз)
        strip.style.transition = 'transform 600ms cubic-bezier(0.2, 0, 0.2, 1)';
        // Всегда смещаем вниз для лучшей видимости
        strip.style.transform = `translateY(-${Math.max(offset, 20)}px)`;
        
        reel.classList.remove('is-blurred');
        reel.classList.remove('is-spinning');
    }
}

function revealSlotRow(index) {
    const reel = document.getElementById(`slots-reel-${index}`);
    if (reel) {
        reel.classList.remove('is-blurred');
        reel.classList.remove('is-spinning');
        reel.classList.add('is-revealed');
        
        // Эффект появления
        setTimeout(() => {
            reel.classList.remove('is-revealed');
        }, 500);
    }
}

function initSlotsStep() {
    // Убеждаемся что selectedBet установлен из baseBet при открытии слотов
    if (!appState.selectedBet || appState.selectedBet === 0) {
        appState.selectedBet = appState.baseBet || 1.0;
    }
    
    setSlotsBetDisplay();
    clearSlotsRevealTimeouts();
    stopAllSlotSpinners();

    if (appState.slotsSpinUsed && Array.isArray(appState.slotsLastSymbols) && appState.slotsLastSymbols.length >= 3) {
        stopSlotsSpinWithResult(appState.slotsLastSymbols);
        revealSlotRow(0);
        revealSlotRow(1);
        revealSlotRow(2);
    } else {
        resetSlotsRows();
    }
    setSlotsSpinButtonState();

    // Кнопка "Крутить"
    const spinBtn = document.getElementById('slots-spin-btn');
    if (spinBtn && spinBtn.parentNode) {
        const btn = spinBtn.cloneNode(true);
        spinBtn.parentNode.replaceChild(btn, spinBtn);
        btn.addEventListener('click', async () => {
            if (appState.gameInProgress) return;
            
            // Если прокрут уже использован, сбрасываем состояние для повторной игры
            if (appState.slotsSpinUsed) {
                appState.slotsSpinUsed = false;
                appState.slotsLastSymbols = null;
                resetSlotsRows();
                setSlotsSpinButtonState();
                return;
            }

            const bet = appState.selectedBet;
            if (isNaN(bet) || bet < 0.1) {
                showToast('Минимальная ставка: $0.10');
                return;
            }
            if (bet > 30) {
                showToast('Максимальная ставка: $30.00');
                return;
            }
            if (appState.balance < bet) {
                showToast(`Недостаточно средств! Нужно $${bet.toFixed(2)}, у вас $${appState.balance.toFixed(2)}`);
                return;
            }

            appState.gameInProgress = true;
            appState.slotsLastSymbols = null;
            setSlotsSpinButtonState();
            startSlotsSpinVisual();

            try {
                const initData = getInitData();
                const response = await fetch(`${API_BASE}/game/start`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Telegram-Init-Data': initData || ''
                    },
                    body: JSON.stringify({
                        game_type: 'slots',
                        bet: bet,
                        bet_type: 'spin'
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `Ошибка запуска слотов (${response.status})`);
                }

                const data = await response.json();
                appState.slotsSpinUsed = true;
                showToast('Слот отправлен! Результат придёт из бота.');
                checkGameResult(data.game_id);
            } catch (e) {
                console.error('Ошибка запуска слотов:', e);
                showToast(e.message || 'Ошибка запуска слотов');
                appState.gameInProgress = false;
                stopAllSlotSpinners();
                resetSlotsRows();
                setSlotsSpinButtonState();
            }
        });
    }

    // Кнопка "Изменить ставку"
    const backBtn = document.getElementById('slots-back-to-bet');
    if (backBtn && backBtn.parentNode) {
        const btn = backBtn.cloneNode(true);
        backBtn.parentNode.replaceChild(btn, backBtn);
        btn.addEventListener('click', () => {
            showGameStep('bet');
        });
    }
}

function handleSlotsGameCompleted(result) {
    const symbols = extractSlotsSymbols(result);
    appState.slotsLastSymbols = symbols;

    // Вычисляем выигрыш
    const win = calculateSlotsWin(symbols, appState.selectedBet);
    
    // Поочередно останавливаем барабаны и снимаем blur
    clearSlotsRevealTimeouts();
    
    // Первый барабан останавливается через 0.8 секунды (быстрее)
    slotsUiState.revealTimeouts.push(setTimeout(() => {
        stopSingleSlotReel(0, symbols[0]);
        revealSlotRow(0);
    }, 800));
    
    // Второй барабан останавливается через 1.4 секунды
    slotsUiState.revealTimeouts.push(setTimeout(() => {
        stopSingleSlotReel(1, symbols[1]);
        revealSlotRow(1);
    }, 1400));
    
    // Третий барабан останавливается через 2 секунды
    slotsUiState.revealTimeouts.push(setTimeout(() => {
        stopSingleSlotReel(2, symbols[2]);
        revealSlotRow(2);
        appState.gameInProgress = false;
        setSlotsSpinButtonState();
        
        // Показываем результат выигрыша
                if (win > 0) {
                    playWinSound();
                    showToast(`Вы выиграли 💎 $${win.toFixed(2)}!`);
        } else {
            showToast('К сожалению, вы не выиграли');
        }
    }, 2000));
}

// Запустить игру с параметрами
async function launchGame(gameId, bet, mode) {
    try {
        // Обрабатываем специальные режимы dice_7
        let gameType = gameId;
        let betType = mode;
        
        // Если режим начинается с dice_7_, то это специальный режим для dice_7
        if (mode.startsWith('dice_7_')) {
            gameType = 'dice_7';
            betType = mode.replace('dice_7_', ''); // Убираем префикс dice_7_
        }
        
        // Отправляем запрос боту для запуска игры
        const response = await fetch(`${API_BASE}/game/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg.initData
            },
            body: JSON.stringify({
                game_type: gameType,
                bet: bet,
                bet_type: betType
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            // Бот отправит dice в чат с пользователем
            showToast('Игра запущена! Проверьте чат с ботом - там появится dice.');
            
            // Обновляем баланс
            await loadUserData();
            
            // Периодически проверяем результат игры
            checkGameResult(data.game_id);
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.error || 'Ошибка запуска игры';
            
            // Разблокируем кнопку при ошибке
            appState.gameInProgress = false;
            const startBtn = document.getElementById('start-game-btn');
            if (startBtn) {
                startBtn.disabled = false;
                startBtn.style.opacity = '1';
                startBtn.style.cursor = 'pointer';
                startBtn.textContent = 'Начать игру';
            }
            
            if (errorMsg.includes('balance') || errorMsg.includes('средств')) {
                showToast(`Недостаточно средств! Нужно $${bet.toFixed(2)}`);
            } else {
                showToast(errorMsg);
            }
        }
    } catch (error) {
        console.error('Ошибка запуска игры:', error);
        showToast('Ошибка запуска игры');
        
        // Разблокируем кнопку при ошибке
        appState.gameInProgress = false;
        const startBtn = document.getElementById('start-game-btn');
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.style.opacity = '1';
            startBtn.style.cursor = 'pointer';
            startBtn.textContent = 'Начать игру';
        }
    }
}

// Проверить результат игры
async function checkGameResult(gameId) {
    const maxAttempts = 40; // Максимум 20 секунд (40 попыток по 0.5 секунды)
    let attempts = 0;
    
    const checkInterval = setInterval(async () => {
        attempts++;
        
        try {
            const response = await fetch(`${API_BASE}/game/result/${gameId}`, {
                headers: {
                    'X-Telegram-Init-Data': tg.initData
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.completed) {
                    clearInterval(checkInterval);
                    if (data.game_type === 'slots') {
                        handleSlotsGameCompleted(data);
                    } else {
                        displayGameResult(data);
                    }
                    // Обновляем баланс
                    await loadUserData();
                } else if (data.status === 'timeout' || data.status === 'error') {
                    clearInterval(checkInterval);
                    showToast(data.status === 'timeout' ? 'Таймаут ожидания результата' : 'Ошибка игры');

                    // Снимаем блокировки (в т.ч. для слотов)
                    appState.gameInProgress = false;
                    if (appState.currentGameId === 'slots') {
                        appState.slotsSpinUsed = false;
                        appState.slotsLastSymbols = null;
                        resetSlotsRows();
                        setSlotsSpinButtonState();
                    } else {
                        const startBtn = document.getElementById('start-game-btn');
                        if (startBtn) {
                            startBtn.disabled = false;
                            startBtn.style.opacity = '1';
                            startBtn.style.cursor = 'pointer';
                            startBtn.textContent = 'Начать игру';
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Ошибка проверки результата:', error);
        }
        
        if (attempts >= maxAttempts) {
            clearInterval(checkInterval);
            showToast('Таймаут ожидания результата');
            // Разблокируем кнопку при таймауте
            appState.gameInProgress = false;
            if (appState.currentGameId === 'slots') {
                appState.slotsSpinUsed = false;
                appState.slotsLastSymbols = null;
                resetSlotsRows();
                setSlotsSpinButtonState();
            } else {
                const startBtn = document.getElementById('start-game-btn');
                if (startBtn) {
                    startBtn.disabled = false;
                    startBtn.style.opacity = '1';
                    startBtn.style.cursor = 'pointer';
                    startBtn.textContent = 'Начать игру';
                }
            }
        }
    }, 500); // Проверяем каждые 0.5 секунды для быстрого отклика
}

// Отобразить результат игры
function displayGameResult(result) {
    // Логируем для отладки
    console.log('🎮 displayGameResult вызвана:', {
        result: result.result,
        throws: result.throws,
        throwsType: typeof result.throws,
        isArray: Array.isArray(result.throws),
        throwsLength: result.throws ? result.throws.length : 0,
        gameType: result.game_type
    });
    
    // ВАЖНО: Если есть массив throws (результаты каждого броска), используем его для стикеров
    // Иначе используем result (сумму) для обратной совместимости
    let stickerNames = [];
    
    // Проверяем наличие throws и что это массив
    if (result.throws && Array.isArray(result.throws) && result.throws.length > 0) {
        // Используем массив throws для создания стикеров
        console.log('✅ Используем массив throws:', result.throws);
        stickerNames = result.throws.map(throwValue => {
            const stickerName = getStickerNameForResult(result.game_type, throwValue);
            console.log(`  → Бросок ${throwValue} → стикер ${stickerName}`);
            return stickerName;
        });
    } else {
        // Нет throws или это не массив - используем result (сумму) для обратной совместимости
        console.log('⚠️ throws отсутствует или не массив, используем result:', result.result);
        stickerNames = [getStickerNameForResult(result.game_type, result.result)];
    }
    
    console.log('🎨 Итоговые названия стикеров:', stickerNames);
    
    // Показываем модальное окно с результатом
    showGameResultModal(result, stickerNames);
    
    // Обновляем баланс
    appState.balance = result.new_balance;
    
    // Разблокируем кнопку "Начать игру" после завершения игры
    appState.gameInProgress = false;
    const startBtn = document.getElementById('start-game-btn');
    if (startBtn) {
        startBtn.disabled = false;
        startBtn.style.opacity = '1';
        startBtn.style.cursor = 'pointer';
        startBtn.textContent = 'Начать игру';
    }
    
    updateUI();
}

// Получить название стикера для результата игры
function getStickerNameForResult(gameType, result) {
    // Для кубика - просто число
    if (gameType === 'dice') {
        return `dice_${result}`;
    }
    
    // Для боулинга - количество сбитых кеглей
    if (gameType === 'bowling') {
        if (result === 6) {  // В боулинге 6 = страйк (все кегли)
            return 'bowling_strike';
        } else if (result === 0 || result === 1) {
            return 'bowling_miss';
        } else {
            return `bowling_${result}`;
        }
    }
    
    // Для дартса - просто по значению dice (1-6)
    if (gameType === 'dart') {
        return `darts_${result}`;
    }
    
    // Для футбола - просто по значению dice (1-5)
    if (gameType === 'football') {
        return `football_${result}`;
    }
    
    // Для баскетбола - просто по значению dice (1-5)
    if (gameType === 'basketball') {
        return `basketball_${result}`;
    }
    
    // По умолчанию
    return `${gameType}_${result}`;
}

// Воспроизвести звук победы
function playWinSound() {
    if (localStorage.getItem('soundEnabled') === 'false') return;
    
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Создаем приятный мелодичный звук победы
        const frequencies = [523.25, 659.25, 783.99, 1046.50]; // До, Ми, Соль, До (мажорный аккорд)
        let currentFreq = 0;
        
        const playNote = (freq, time, duration) => {
            const osc = audioContext.createOscillator();
            const gain = audioContext.createGain();
            
            osc.frequency.value = freq;
            osc.type = 'sine';
            
            gain.gain.setValueAtTime(0.3, time);
            gain.gain.exponentialRampToValueAtTime(0.01, time + duration);
            
            osc.connect(gain);
            gain.connect(audioContext.destination);
            
            osc.start(time);
            osc.stop(time + duration);
        };
        
        const now = audioContext.currentTime;
        frequencies.forEach((freq, i) => {
            playNote(freq, now + i * 0.1, 0.3);
        });
    } catch (e) {
        console.log('Не удалось воспроизвести звук победы:', e);
    }
}

// Воспроизвести звук поражения
function playLoseSound() {
    if (localStorage.getItem('soundEnabled') === 'false') return;
    
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Создаем низкий грустный звук
        oscillator.frequency.value = 200;
        oscillator.type = 'sawtooth';
        
        gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
        
        // Добавляем второй звук для эффекта
        setTimeout(() => {
            const osc2 = audioContext.createOscillator();
            const gain2 = audioContext.createGain();
            
            osc2.connect(gain2);
            gain2.connect(audioContext.destination);
            
            osc2.frequency.value = 150;
            osc2.type = 'sawtooth';
            
            gain2.gain.setValueAtTime(0.15, audioContext.currentTime);
            gain2.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.4);
            
            osc2.start(audioContext.currentTime);
            osc2.stop(audioContext.currentTime + 0.4);
        }, 200);
    } catch (e) {
        console.log('Не удалось воспроизвести звук поражения:', e);
    }
}

// Показать модальное окно результата игры
async function showGameResultModal(result, stickerNames) {
    // Определяем стикер победы/поражения
    const resultStickerName = result.win > 0 ? 'results_win' : 'results_lose';
    const isWin = result.win > 0;
    
    // Воспроизводим звук
    if (isWin) {
        playWinSound();
    } else {
        playLoseSound();
    }
    
    // Если stickerNames - строка (старая версия), преобразуем в массив
    if (typeof stickerNames === 'string') {
        stickerNames = [stickerNames];
    }
    
    // Создаем временное модальное окно для результата
    const modal = document.createElement('div');
    modal.className = `modal active ${isWin ? 'win' : 'lose'}`;
    modal.id = 'game-result-modal';
    
    // Создаем контейнер для стикеров результатов (несколько стикеров в ряд)
    const stickersHTML = stickerNames.map((stickerName, index) => 
        `<div class="result-sticker" data-sticker="${stickerName}" style="display: inline-block; margin: 0 5px; animation-delay: ${index * 0.1}s;"></div>`
    ).join('');
    
    modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h2>🎮 Результат игры</h2>
            </div>
            <div class="modal-body" style="text-align: center;">
                <div class="result-stickers-container">
                    ${stickersHTML}
                </div>
                <div class="win-lose-sticker" data-sticker="${resultStickerName}" style="animation-delay: ${stickersHTML.length * 0.1 + 0.1}s;"></div>
                ${isWin ? 
                    `<div class="result-win-text">🎉 Выигрыш: $${result.win.toFixed(2)}</div>` : 
                    `<div class="result-lose-text">😔 Проигрыш</div>`
                }
                <div class="result-display-enhanced">
                    Результат: ${result.result}
                </div>
                <div class="balance-display-enhanced">
                    💰 Новый баланс: $${result.new_balance.toFixed(2)}
                </div>
                <button class="btn-primary" id="btn-understand-result" style="width: 100%; margin-top: 20px; animation: fadeIn 0.5s ease-out 0.5s both;">Понятно</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Загружаем стикеры через API для каждого стикера результата
    const stickerElements = modal.querySelectorAll('.result-sticker');
    for (let i = 0; i < stickerElements.length; i++) {
        await loadStickerForElement(stickerElements[i], stickerNames[i]);
    }
    
    // Загружаем стикер победы/поражения
    await loadStickerForElement(modal.querySelector('.win-lose-sticker'), resultStickerName);
    
    // Добавляем вибрацию для мобильных устройств
    if (navigator.vibrate && localStorage.getItem('vibrationEnabled') !== 'false') {
        if (isWin) {
            navigator.vibrate([100, 50, 100, 50, 200]); // Паттерн победы
        } else {
            navigator.vibrate([200]); // Одиночная вибрация поражения
        }
    }
    
    // Обработчик кнопки "Понятно"
    const understandBtn = document.getElementById('btn-understand-result');
    if (understandBtn) {
        understandBtn.addEventListener('click', () => {
            modal.style.animation = 'resultModalSlideOut 0.3s ease-in forwards';
            setTimeout(() => modal.remove(), 300);
        });
    }
    
    // Закрытие по клику на backdrop
    modal.querySelector('.modal-backdrop').addEventListener('click', () => {
        modal.style.animation = 'resultModalSlideOut 0.3s ease-in forwards';
        setTimeout(() => modal.remove(), 300);
    });
}

// Добавляем анимацию закрытия модального окна
const style = document.createElement('style');
style.textContent = `
    @keyframes resultModalSlideOut {
        to {
            opacity: 0;
            transform: scale(0.8) translateY(50px);
        }
    }
`;
document.head.appendChild(style);

// Получить путь к локальному стикеру
function getLocalStickerPath(stickerName) {
    // Маппинг названий стикеров на пути к файлам в папке stickers
    const stickerMap = {
        // Приветственный стикер
        'welcome': 'stickers/welcome/welcome.tgs',
        
        // Результаты игр
        'results_win': 'stickers/results/win.tgs',
        'results_lose': 'stickers/results/lose.tgs',
        
        // Кубик
        'dice_1': 'stickers/dice/1.tgs',
        'dice_2': 'stickers/dice/2.tgs',
        'dice_3': 'stickers/dice/3.tgs',
        'dice_4': 'stickers/dice/4.tgs',
        'dice_5': 'stickers/dice/5.tgs',
        'dice_6': 'stickers/dice/6.tgs',
        'dice_base': 'stickers/dice/base.tgs',
        
        // Дартс
        'darts_1': 'stickers/darts/1.tgs',
        'darts_2': 'stickers/darts/2.tgs',
        'darts_3': 'stickers/darts/3.tgs',
        'darts_4': 'stickers/darts/4.tgs',
        'darts_5': 'stickers/darts/5.tgs',
        'darts_6': 'stickers/darts/6.tgs',
        'darts_base': 'stickers/darts/base.tgs',
        
        // Боулинг (GIF файлы)
        'bowling_0': 'stickers/bowling/bowling_0_pin.gif',
        'bowling_1': 'stickers/bowling/bowling_1_pins.gif',
        'bowling_2': 'stickers/bowling/bowling_1_pins.gif', // Используем bowling_1_pins для значения 2
        'bowling_3': 'stickers/bowling/bowling_3_pins.gif',
        'bowling_4': 'stickers/bowling/bowling_4_pins.gif',
        'bowling_5': 'stickers/bowling/bowling_5_pins.gif',
        'bowling_6': 'stickers/bowling/bowling_6_pins.gif',
        'bowling_strike': 'stickers/bowling/bowling_6_pins.gif', // Страйк = все кегли сбиты
        'bowling_miss': 'stickers/bowling/bowling_0_pin.gif', // Промах = 0 кеглей
        'bowling_base': 'stickers/bowling/bowling_animation.gif',
        
        // Футбол
        'football_1': 'stickers/football/1.tgs',
        'football_2': 'stickers/football/2.tgs',
        'football_3': 'stickers/football/3.tgs',
        'football_4': 'stickers/football/4.tgs',
        'football_5': 'stickers/football/5.tgs',
        'football_base': 'stickers/football/base.tgs',
        
        // Баскетбол
        'basketball_1': 'stickers/basketball/1.tgs',
        'basketball_2': 'stickers/basketball/2.tgs',
        'basketball_3': 'stickers/basketball/3.tgs',
        'basketball_4': 'stickers/basketball/4.tgs',
        'basketball_5': 'stickers/basketball/5.tgs',
        'basketball_base': 'stickers/basketball/base.tgs',

        // Слоты
        'slots_base': 'stickers/slots/base_new.tgs'
    };
    
    return stickerMap[stickerName] || null;
}

// Загрузить стикер для элемента
async function loadStickerForElement(element, stickerName) {
    if (!element || !stickerName) return;
    
    // Определяем размер стикера в зависимости от типа
    const isResultSticker = element.classList.contains('result-sticker') || element.classList.contains('win-lose-sticker');
    const stickerSize = isResultSticker ? '100px' : '150px';
    
    // Устанавливаем размер контейнера
    if (isResultSticker) {
        element.style.width = stickerSize;
        element.style.height = stickerSize;
        element.style.margin = '0 auto';
    }
    
    // Очищаем элемент перед загрузкой нового стикера
    element.innerHTML = '';
    element.style.opacity = '0';
    
    // Сначала пробуем загрузить локальный файл из папки stickers
    const localPath = getLocalStickerPath(stickerName);
    if (localPath) {
        try {
            // Добавляем агрессивный cache buster с timestamp и random числом
            const cacheBuster = `?v=${Date.now()}_${Math.random().toString(36).substring(7)}`;
            const localPathWithCache = localPath + cacheBuster;
            
            console.log(`🔄 Загрузка стикера ${stickerName} с cache buster: ${cacheBuster}`);
            
            const response = await fetch(localPath, { method: 'HEAD', cache: 'no-store' });
            if (response.ok) {
                console.log(`✅ Локальный стикер найден: ${localPath}`);
                // Проверяем формат файла (GIF или TGS)
                const pathLower = localPath.toLowerCase();
                const isGif = pathLower.endsWith('.gif');
                const isTgs = pathLower.endsWith('.tgs');
                
                console.log(`🔍 Формат локального файла: ${isGif ? 'GIF' : (isTgs ? 'TGS' : 'Unknown')}, путь: ${localPath}`);
                
                if (isGif) {
                    // Для GIF файлов создаем img элемент
                    const img = document.createElement('img');
                    img.src = localPathWithCache; // Используем версию с cache buster
                    img.alt = 'Sticker';
                    img.style.width = stickerSize;
                    img.style.height = stickerSize;
                    img.style.objectFit = 'contain';
                    img.onerror = () => {
                        console.error('❌ Ошибка загрузки GIF изображения');
                        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px;"></div>`;
                    };
                    element.appendChild(img);
                    element.style.opacity = '1';
                    return;
                } else if (isTgs) {
                    // Для TGS файлов используем loadTgsSticker
                    console.log('🎬 Определен TGS формат, загружаю через loadTgsSticker');
                    
                    // Убеждаемся, что библиотеки загружены
                    if (!window.lottie || !window.pako) {
                        console.log('⏳ Ожидание загрузки библиотек lottie/pako...');
                        await new Promise((resolve) => {
                            let attempts = 0;
                            const maxAttempts = 50; // 5 секунд максимум
                            const checkLibs = setInterval(() => {
                                attempts++;
                                if (window.lottie && window.pako) {
                                    clearInterval(checkLibs);
                                    console.log('✅ Библиотеки загружены');
                                    resolve();
                                } else if (attempts >= maxAttempts) {
                                    clearInterval(checkLibs);
                                    console.error('❌ Библиотеки не загрузились за отведенное время');
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                    
                    if (window.lottie && window.pako) {
                        try {
                            await loadTgsSticker(element, localPathWithCache);
                            return;
                        } catch (error) {
                            console.error('❌ Ошибка при загрузке TGS стикера:', error);
                            // Не показываем ошибку - стикер будет позже
                            element.innerHTML = '';
                            element.style.opacity = '0.3';
                        }
                    } else {
                        console.error('❌ Библиотеки lottie или pako не загружены');
                        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(255,0,0,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️ Библиотеки не загружены</div>`;
                    }
                } else {
                    console.warn(`⚠️ Неизвестный формат файла: ${localPath}, пробуем как TGS`);
                    // Для файлов без расширения пробуем как TGS (может быть это стикер из API)
                    if (window.lottie && window.pako) {
                        try {
                            await loadTgsSticker(element, localPathWithCache);
                            return;
                        } catch (error) {
                            console.warn('⚠️ Не удалось загрузить как TGS, пробуем как изображение:', error);
                        }
                    }
                    // Fallback на изображение
                    const img = document.createElement('img');
                    img.src = localPathWithCache;
                    img.style.width = stickerSize;
                    img.style.height = stickerSize;
                    img.style.objectFit = 'contain';
                    element.appendChild(img);
                }
            }
        } catch (e) {
            console.warn(`⚠️ Локальный стикер не найден: ${localPath}, пробуем через API`, e);
        }
    }
    
    // Если локальный файл не найден, пробуем через API
    try {
        const initData = getInitData();
        const response = await fetch(`${API_BASE}/sticker/${stickerName}`, {
            headers: {
                'X-Telegram-Init-Data': initData
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log(`📦 Данные стикера ${stickerName} из API:`, data);
            
            const stickerUrl = data.file_url || data.file_id;
            if (stickerUrl) {
                console.log(`✅ URL стикера ${stickerName}:`, stickerUrl);
                
                // Проверяем формат файла по URL и данным
                const urlLower = stickerUrl.toLowerCase();
                // Для slots_base всегда пробуем как TGS, так как это должен быть TGS стикер
                const isTgs = stickerName === 'slots_base' || 
                             urlLower.endsWith('.tgs') || 
                             urlLower.includes('.tgs') ||
                             urlLower.includes('file_') || // Telegram file URLs обычно TGS
                             data.is_tgs === true;
                
                console.log(`🔍 Формат стикера ${stickerName}: ${isTgs ? 'TGS' : 'Image'}`);
                console.log(`🔍 URL стикера: ${stickerUrl}`);
                console.log(`🔍 Данные из API:`, data);
                
                if (isTgs) {
                    // Для TGS файлов используем loadTgsSticker
                    console.log('🎬 Загружаю как TGS через loadTgsSticker');
                    
                    // Убеждаемся, что библиотеки загружены
                    if (!window.lottie || !window.pako) {
                        console.log('⏳ Ожидание загрузки библиотек lottie/pako...');
                        await new Promise((resolve) => {
                            let attempts = 0;
                            const maxAttempts = 50; // 5 секунд максимум
                            const checkLibs = setInterval(() => {
                                attempts++;
                                if (window.lottie && window.pako) {
                                    clearInterval(checkLibs);
                                    console.log('✅ Библиотеки загружены');
                                    resolve();
                                } else if (attempts >= maxAttempts) {
                                    clearInterval(checkLibs);
                                    console.error('❌ Библиотеки не загрузились за отведенное время');
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                    
                    if (window.lottie && window.pako) {
                        try {
                            await loadTgsSticker(element, stickerUrl);
                            return;
                        } catch (error) {
                            console.error('❌ Ошибка при загрузке TGS стикера через API:', error);
                            // Не показываем ошибку - стикер будет позже
                            element.innerHTML = '';
                            element.style.opacity = '0.3';
                            return;
                        }
                    } else {
                        console.error('❌ Библиотеки lottie или pako не загружены');
                        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(255,0,0,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️ Библиотеки не загружены</div>`;
                        return;
                    }
                } else {
                    // Для обычных изображений (PNG, WEBP, GIF и т.д.)
                    console.log(`🖼️ Загрузка изображения стикера: ${stickerUrl}`);
                    const img = document.createElement('img');
                    img.src = stickerUrl;
                    img.alt = 'Sticker';
                    img.style.width = stickerSize;
                    img.style.height = stickerSize;
                    img.style.objectFit = 'contain';
                    img.style.display = 'block';
                    img.onload = () => {
                        console.log(`✅ Изображение стикера ${stickerName} загружено`);
                    };
                    img.onerror = (e) => {
                        console.error(`❌ Ошибка загрузки изображения стикера ${stickerName}:`, e);
                        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️</div>`;
                    };
                    element.innerHTML = '';
                    element.appendChild(img);
                }
            } else {
                console.warn(`⚠️ Стикер ${stickerName} найден, но URL отсутствует`);
                element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️</div>`;
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.warn(`⚠️ Стикер ${stickerName} не найден через API, статус:`, response.status, errorData);
            // Если стикер не найден, показываем fallback
            element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️</div>`;
        }
    } catch (error) {
        console.error(`❌ Ошибка загрузки стикера ${stickerName}:`, error);
        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">⚠️</div>`;
    }
}

// Загрузить данные кошелька
async function loadWalletData() {
    // Обновляем данные пользователя для синхронизации баланса
    await loadUserData();
    updateUI();
    // Проверяем статус подключения кошелька
    checkWalletConnectionStatus();
}

// Инициализация страниц
function initPages() {
    // Кошелек - пополнение/вывод
    const depositBtn = document.getElementById('btn-deposit');
    const withdrawBtn = document.getElementById('btn-withdraw');
    const connectWalletBtn = document.getElementById('btn-connect-wallet');
    
    if (depositBtn) {
        depositBtn.addEventListener('click', () => {
            showDepositMethods();
        });
    }
    
    if (withdrawBtn) {
        withdrawBtn.addEventListener('click', () => {
            showWithdrawMethods();
        });
    }
    
    // Кнопка подключения TON кошелька
    if (connectWalletBtn) {
        connectWalletBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('🔗 Нажата кнопка подключения кошелька');
            try {
                await connectTONWallet();
            } catch (error) {
                console.error('Ошибка при нажатии кнопки:', error);
                showToast('Ошибка: ' + (error.message || error));
            }
        });
    } else {
        console.warn('⚠️ Кнопка btn-connect-wallet не найдена!');
    }
    
    // Проверяем статус подключения кошелька при загрузке страницы кошелька
    checkWalletConnectionStatus();
    
    // Кнопка кошелек в профиле
    const walletProfileBtn = document.getElementById('btn-wallet-profile');
    if (walletProfileBtn) {
        walletProfileBtn.addEventListener('click', () => {
            switchPage('wallet');
            // Обновляем активную кнопку в навигации
            const navButtons = document.querySelectorAll('.nav-btn');
            navButtons.forEach(b => b.classList.remove('active'));
        });
    }
    
    // Настройки
    document.getElementById('btn-base-bet').addEventListener('click', () => {
        showModal('modal-base-bet');
    });
    
    document.getElementById('btn-create-check').addEventListener('click', () => {
        showModal('modal-create-check');
        initCheckCreation();
    });
    
    document.getElementById('btn-lotteries').addEventListener('click', () => {
        showModal('modal-lotteries');
        loadLotteries();
    });
    
    document.getElementById('btn-support').addEventListener('click', () => {
        // Отправляем команду поддержки в бота через Telegram WebApp API
        try {
            // Используем tg.openTelegramLink для открытия бота с командой /start support
            // Это откроет чат с ботом (в котором открыто мини-приложение) и автоматически отправит команду /start support
            if (tg && tg.openTelegramLink) {
                // Открываем бота с параметром start=support
                // Это автоматически отправит команду /start support в чат с ботом
                tg.openTelegramLink('tg://resolve?start=support');
            } else if (tg && tg.sendData) {
                // Альтернативный способ - отправляем данные боту
                // Бот должен обработать эти данные и открыть поддержку
                tg.sendData(JSON.stringify({ action: 'support', command: '/support' }));
            } else {
                showToast('Откройте бота и отправьте команду /support');
            }
        } catch (error) {
            console.error('Ошибка при открытии поддержки:', error);
            showToast('Ошибка при открытии поддержки');
        }
    });


    // Переключатель реферальных уведомлений
    const refNotificationsToggle = document.getElementById('ref-notifications-toggle');
    if (refNotificationsToggle) {
        // Загружаем текущее состояние
        loadSettings();
        
        refNotificationsToggle.addEventListener('change', async (e) => {
            await toggleRefNotifications(e.target.checked);
        });
    }

    // Переключатель звуков
    const soundToggle = document.getElementById('sound-toggle');
    if (soundToggle) {
        soundToggle.checked = localStorage.getItem('soundEnabled') !== 'false';
        soundToggle.addEventListener('change', (e) => {
            localStorage.setItem('soundEnabled', e.target.checked);
            showToast(e.target.checked ? '🔊 Звуки включены' : '🔇 Звуки выключены');
        });
    }

    // Переключатель вибрации
    const vibrationToggle = document.getElementById('vibration-toggle');
    if (vibrationToggle) {
        vibrationToggle.checked = localStorage.getItem('vibrationEnabled') !== 'false';
        vibrationToggle.addEventListener('change', (e) => {
            localStorage.setItem('vibrationEnabled', e.target.checked);
            if (e.target.checked && 'vibrate' in navigator) {
                navigator.vibrate(50);
            }
            showToast(e.target.checked ? '📳 Вибрация включена' : '📳 Вибрация выключена');
        });
    }
    
    // Модальные окна
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.modal;
            if (modalId === 'modal-deposit-ton') {
                closeDepositTONModal();
            } else {
                hideModal(modalId);
            }
        });
    });
    
    // Закрытие модальных окон при клике на backdrop
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) {
                const modal = backdrop.closest('.modal');
                if (modal) {
                    const modalId = modal.id;
                    if (modalId === 'modal-deposit-ton') {
                        closeDepositTONModal();
                    } else {
                        hideModal(modalId);
                    }
                }
            }
        });
    });
    
    // Обработчик для кнопки подтверждения пополнения TON
    const depositTONConfirmBtn = document.getElementById('btn-deposit-ton-confirm');
    if (depositTONConfirmBtn) {
        depositTONConfirmBtn.addEventListener('click', async () => {
            await processTONDeposit();
        });
    }
    
    // Закрытие модального окна при клике на backdrop
    const depositTONModal = document.getElementById('modal-deposit-ton');
    if (depositTONModal) {
        const backdrop = depositTONModal.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.addEventListener('click', () => {
                closeDepositTONModal();
            });
        }
        
        // Обработчик Enter в поле ввода суммы
        const amountInput = document.getElementById('deposit-ton-amount');
        if (amountInput) {
            amountInput.addEventListener('keypress', async (e) => {
                if (e.key === 'Enter') {
                    await processTONDeposit();
                }
            });
        }
    }
    
    // Сохранение базовой ставки
    document.getElementById('save-base-bet').addEventListener('click', async () => {
        const value = parseFloat(document.getElementById('base-bet-input').value);
        if (value >= 0.1) {
            await saveBaseBet(value);
            hideModal('modal-base-bet');
        }
    });
    
    // Инициализация рулетки
    initRoulette();
}

// Показать методы пополнения
async function showDepositMethods() {
    const modal = document.getElementById('modal-deposit-methods');
    const methodsList = document.getElementById('deposit-methods-list');
    
    if (!modal || !methodsList) {
        console.error('Модальное окно методов пополнения не найдено');
        showToast('Ошибка: модальное окно не найдено');
        return;
    }
    
    // Показываем индикатор загрузки
    methodsList.innerHTML = `
        <div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
            <div style="font-size: 48px; margin-bottom: 20px;">⏳</div>
            <div style="font-size: 16px; font-weight: 500;">Загрузка методов...</div>
        </div>
    `;
    
    // Открываем модальное окно сразу, чтобы показать загрузку
    showModal('modal-deposit-methods');
    
    // Загружаем методы из API
    try {
        const response = await fetch(`${API_BASE}/wallet/deposit-methods`, {
            method: 'GET',
            headers: {
                'X-Telegram-Init-Data': getInitData()
            }
        });
        
        if (!response.ok) {
            let errorMessage = `Ошибка ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorData.message || errorMessage;
                if (errorData.detail) {
                    errorMessage += `: ${errorData.detail}`;
                }
            } catch (e) {
                // Если не удалось распарсить JSON, используем statusText
                errorMessage = response.statusText || errorMessage;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        const methods = data.methods || [];
        
        // Если методов нет, показываем сообщение
        if (methods.length === 0) {
            methodsList.innerHTML = `
                <div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
                    <div style="font-size: 48px; margin-bottom: 20px;">📭</div>
                    <div style="font-size: 16px; font-weight: 500;">Методы пополнения пока недоступны</div>
                </div>
            `;
            return;
        }
        
        // Очищаем список
        methodsList.innerHTML = '';
        
        // Создаем кнопки для каждого метода
        methods.forEach(method => {
            const methodBtn = document.createElement('button');
            methodBtn.className = 'method-btn';
            methodBtn.id = `deposit-${method.id}`;
            
            // Иконки для разных методов
            let iconSvg = '';
            if (method.id === 'ton') {
                iconSvg = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                    <path d="M2 17l10 5 10-5"></path>
                    <path d="M2 12l10 5 10-5"></path>
                </svg>`;
            } else if (method.id === 'cryptobot') {
                iconSvg = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
                </svg>`;
            } else if (method.id === 'gifts') {
                iconSvg = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 12 20 22 4 22 4 12"></polyline>
                    <rect x="2" y="7" width="20" height="5"></rect>
                    <line x1="12" y1="22" x2="12" y2="7"></line>
                    <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                    <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
                </svg>`;
            }
            
            methodBtn.innerHTML = `
                ${iconSvg}
                <span>${method.icon || ''} ${method.name || method.id}</span>
            `;
            
            // Добавляем обработчик клика
            methodBtn.addEventListener('click', async () => {
                hideModal('modal-deposit-methods');
                if (method.id === 'ton') {
                    showDepositTONModal();
                } else if (method.id === 'cryptobot') {
                    showDepositCryptoBotModal();
                } else if (method.id === 'gifts') {
                    await showDepositGiftsModal();
                }
            });
            
            methodsList.appendChild(methodBtn);
        });
    } catch (error) {
        console.error('Ошибка загрузки методов пополнения:', error);
        
        // Определяем тип ошибки для более информативного сообщения
        let errorTitle = 'Ошибка загрузки методов пополнения';
        let errorMessage = error.message || 'Не удалось загрузить методы';
        let errorIcon = '❌';
        
        if (errorMessage.includes('404') || errorMessage.includes('Not Found')) {
            errorTitle = 'Метод не найден';
            errorMessage = 'Эндпоинт для методов пополнения не найден на сервере. Возможно, функция еще не реализована.';
            errorIcon = '🔍';
        } else if (errorMessage.includes('401') || errorMessage.includes('Unauthorized')) {
            errorTitle = 'Ошибка авторизации';
            errorMessage = 'Не удалось авторизоваться. Попробуйте перезагрузить страницу.';
            errorIcon = '🔐';
        } else if (errorMessage.includes('500') || errorMessage.includes('Internal Server Error')) {
            errorTitle = 'Ошибка сервера';
            errorMessage = 'На сервере произошла ошибка. Попробуйте позже.';
            errorIcon = '⚠️';
        }
        
        // Показываем ошибку внутри модального окна
        methodsList.innerHTML = `
            <div style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 48px; margin-bottom: 20px;">${errorIcon}</div>
                <div style="font-size: 16px; font-weight: 500; margin-bottom: 10px; color: var(--accent-red);">${errorTitle}</div>
                <div style="font-size: 14px; color: var(--text-secondary); margin-top: 10px; line-height: 1.5;">${errorMessage}</div>
                <button class="btn-primary" onclick="showDepositMethods()" style="margin-top: 20px; width: auto; padding: 10px 20px;">
                    🔄 Попробовать снова
                </button>
            </div>
        `;
        
        showToast(errorTitle);
    }
}

// Показать модальное окно пополнения через CryptoBot
async function showDepositCryptoBotModal() {
    // Создаем модальное окно для выбора суммы
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'modal-deposit-cryptobot';
    modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h2>🏝️ CryptoBot</h2>
                <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="check-step">
                    <label>Сумма пополнения (USD):</label>
                    <input type="number" id="cryptobot-amount" class="input-field" step="0.01" min="0.1" max="${MAX_DEPOSIT || 1000}" placeholder="Введите сумму">
                    <div style="margin-top: 10px; font-size: 12px; color: var(--text-secondary);">
                        Минимальная сумма: $0.10
                    </div>
                </div>
                <div class="bet-quick-buttons" style="margin-top: 15px;">
                    <button class="bet-quick-btn" data-value="1">$1</button>
                    <button class="bet-quick-btn" data-value="5">$5</button>
                    <button class="bet-quick-btn" data-value="10">$10</button>
                    <button class="bet-quick-btn" data-value="20">$20</button>
                    <button class="bet-quick-btn" data-value="30">$30</button>
                </div>
                <div class="modal-actions">
                    <button class="btn-primary" id="btn-cryptobot-confirm">Создать инвойс</button>
                    <button class="btn-secondary" onclick="this.closest('.modal').remove()">Отмена</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Обработчики быстрого выбора суммы
    modal.querySelectorAll('.bet-quick-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            modal.querySelectorAll('.bet-quick-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('cryptobot-amount').value = btn.dataset.value;
        });
    });
    
    // Обработчик создания инвойса
    modal.querySelector('#btn-cryptobot-confirm').addEventListener('click', async () => {
        await processCryptoBotDeposit();
    });
    
    // Закрытие по backdrop
    modal.querySelector('.modal-backdrop').addEventListener('click', () => {
        modal.remove();
    });
}

// Обработать пополнение через CryptoBot
async function processCryptoBotDeposit() {
    const amountInput = document.getElementById('cryptobot-amount');
    const amount = parseFloat(amountInput?.value);
    
    if (!amount || amount < 0.1) {
        showToast('Минимальная сумма пополнения: $0.10');
        return;
    }
    
    if (amount > (MAX_DEPOSIT || 1000)) {
        showToast(`Максимальная сумма пополнения: $${MAX_DEPOSIT || 1000}`);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/wallet/cryptobot-invoice`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': getInitData()
            },
            body: JSON.stringify({ amount })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            showToast(errorData.error || 'Ошибка создания инвойса');
            return;
        }
        
        const data = await response.json();
        
        // Открываем ссылку на оплату
        window.open(data.invoice_url, '_blank');
        
        // Закрываем модальное окно
        document.getElementById('modal-deposit-cryptobot')?.remove();
        
        showToast('Инвойс создан! Откройте ссылку для оплаты.');
        
        // Можно добавить проверку статуса инвойса через deposit_id
    } catch (error) {
        console.error('Ошибка создания инвойса CryptoBot:', error);
        showToast('Ошибка создания инвойса');
    }
}

// Показать модальное окно пополнения подарками
async function showDepositGiftsModal() {
    // Загружаем список подарков из API
    try {
        const response = await fetch(`${API_BASE}/gifts`, {
            method: 'GET',
            headers: {
                'X-Telegram-Init-Data': getInitData()
            }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки подарков');
        }
        
        const data = await response.json();
        // Обрабатываем разные форматы ответа API
        let gifts = [];
        if (Array.isArray(data)) {
            gifts = data;
        } else if (data.gifts && Array.isArray(data.gifts)) {
            gifts = data.gifts;
        } else {
            console.warn('Неожиданный формат данных подарков:', data);
        }
        
        // Создаем модальное окно
        const modal = document.createElement('div');
        modal.className = 'modal active';
        modal.id = 'modal-deposit-gifts';
        modal.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="modal-content" style="max-width: 90%; max-height: 90vh; overflow-y: auto;">
                <div class="modal-header">
                    <h2>🎁 Пополнение подарками</h2>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
                </div>
                <div class="modal-body">
                    <div style="margin-bottom: 20px; text-align: center;">
                        <a href="https://t.me/arbuzrelayer" target="_blank" class="btn-primary" style="display: inline-block; text-decoration: none;">
                            ✈️ Отправить подарок
                        </a>
                    </div>
                    <div class="gifts-grid" id="gifts-grid">
                        ${gifts.length > 0 ? gifts.map(gift => {
                            const emoji = gift.emoji || '🎁';
                            const giftName = gift.name || '';
                            const priceTon = gift.price_ton || gift.price || 0;
                            const priceTonBlack = gift.price_ton_black || gift.price_black || priceTon;
                            
                            // Преобразуем имя подарка в имя файла PNG
                            const fileName = giftNameToFileName(giftName);
                            // Путь к изображению из папки nft/png (на Netlify файлы должны быть в mini_app/nft/png/)
                            const imageUrl = fileName ? `/nft/png/${fileName}.png` : '';
                            
                            return `
                                <div class="gift-item">
                                    <div class="gift-image-container">
                                        ${imageUrl ? `
                                            <img src="${imageUrl}" alt="${giftName}" class="gift-image" 
                                                 onerror="this.onerror=null; this.style.display='none'; this.nextElementSibling.style.display='block';"
                                                 style="width: 100%; height: 100%; object-fit: contain;">
                                            <div style="font-size: 48px; display: none;">${emoji}</div>
                                        ` : `
                                            <div style="font-size: 48px;">${emoji}</div>
                                        `}
                                    </div>
                                    <div class="gift-info">
                                        <div class="gift-price">${priceTon.toFixed(2)} TON</div>
                                        <div class="gift-price-black">⚫️ ${priceTonBlack.toFixed(2)} TON</div>
                                    </div>
                                </div>
                            `;
                        }).join('') : '<div style="text-align: center; color: var(--text-secondary);">Подарки временно недоступны</div>'}
                    </div>
                    <div style="margin-top: 20px; text-align: center; color: var(--text-secondary); font-size: 12px;">
                        Отправьте подарок на @arbuzrelayer для пополнения баланса
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Закрытие по backdrop
        modal.querySelector('.modal-backdrop').addEventListener('click', () => {
            modal.remove();
        });
    } catch (error) {
        console.error('Ошибка загрузки подарков:', error);
        showToast('Ошибка загрузки подарков');
    }
}

// Показать методы вывода
function showWithdrawMethods() {
    const modal = document.getElementById('modal-withdraw-methods');
    const methodsList = document.getElementById('withdraw-methods-list');
    
    if (!modal || !methodsList) {
        console.error('Модальное окно методов вывода не найдено');
        return;
    }
    
    // Создаем кнопки методов, если их еще нет
    if (!methodsList.querySelector('.method-btn') || methodsList.children.length === 0) {
        methodsList.innerHTML = `
            <button class="method-btn" id="withdraw-ton">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                    <path d="M2 17l10 5 10-5"></path>
                    <path d="M2 12l10 5 10-5"></path>
                </svg>
                <span>TON</span>
            </button>
            <button class="method-btn" id="withdraw-gifts">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 12 20 22 4 22 4 12"></polyline>
                    <rect x="2" y="7" width="20" height="5"></rect>
                    <line x1="12" y1="22" x2="12" y2="7"></line>
                    <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                    <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
                </svg>
                <span style="color: var(--accent-green);">Подарки</span>
            </button>
        `;
        
        // Добавляем обработчики событий
        const withdrawTonBtn = document.getElementById('withdraw-ton');
        const withdrawGiftsBtn = document.getElementById('withdraw-gifts');
        
        if (withdrawTonBtn) {
            withdrawTonBtn.addEventListener('click', () => {
                hideModal('modal-withdraw-methods');
                showToast('Вывод TON в разработке');
            });
        }
        
        if (withdrawGiftsBtn) {
            withdrawGiftsBtn.addEventListener('click', async () => {
                hideModal('modal-withdraw-methods');
                await showGifts(true);
            });
        }
    }
    
    // Показываем модальное окно
    showModal('modal-withdraw-methods');
}

// Глобальная переменная для TON Connect UI
let tonConnectUI = null;

// TonConnect UI может экспортироваться по-разному в зависимости от сборки/CDN.
// Частый вариант для UMD: window.TON_CONNECT_UI.TonConnectUI
function getTonConnectUIClass() {
    return (
        window.TonConnectUI ||
        (window.TON_CONNECT_UI && window.TON_CONNECT_UI.TonConnectUI) ||
        (typeof TonConnectUI !== 'undefined' ? TonConnectUI : undefined)
    );
}

function isTonConnectUIReady() {
    return typeof getTonConnectUIClass() !== 'undefined';
}

// Инициализация TON Connect SDK
async function initTONConnectSDK() {
    // Проверяем, загружена ли библиотека
    if (isTonConnectUIReady()) {
        return;
    }
    
    // Проверяем, не загружается ли уже скрипт (в HTML или динамически)
    const existingScript = document.querySelector('script[src*="tonconnect-ui"]');
    if (existingScript) {
        // Ждем пока загрузится (максимум 5 секунд)
        let attempts = 0;
        while (!isTonConnectUIReady() && attempts < 50) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        if (isTonConnectUIReady()) {
            return;
        }
    }
    
    // Если скрипт уже в HTML, просто ждем
    if (document.querySelector('script[src*="tonconnect-ui"]')) {
        let attempts = 0;
        while (!isTonConnectUIReady() && attempts < 100) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        if (isTonConnectUIReady()) {
            return;
        }
        throw new Error('TonConnectUI не стал доступен после загрузки скрипта (ожидается window.TON_CONNECT_UI.TonConnectUI или window.TonConnectUI)');
    }
    
    // Загружаем скрипт динамически (если не был загружен из HTML)
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        // unpkg иногда блокируется в WebView, jsdelivr обычно стабильнее
        script.src = 'https://cdn.jsdelivr.net/npm/@tonconnect/ui@latest/dist/tonconnect-ui.min.js';
        script.async = true;
        
        script.onload = () => {
            // Ждем пока TonConnectUI станет доступен (максимум 10 секунд)
            let attempts = 0;
            const checkInterval = setInterval(() => {
                if (isTonConnectUIReady()) {
                    clearInterval(checkInterval);
                    console.log('✅ TON Connect SDK загружен');
                    resolve();
                } else if (attempts >= 100) {
                    clearInterval(checkInterval);
                    reject(new Error('TonConnectUI не стал доступен после загрузки скрипта'));
                }
                attempts++;
            }, 100);
        };
        
        script.onerror = () => {
            reject(new Error('Не удалось загрузить TON Connect SDK'));
        };
        
        document.head.appendChild(script);
    });
}

// Инициализация TON Connect UI
async function initTONConnectUI() {
    try {
        // Загружаем SDK
        await initTONConnectSDK();
        
        // Проверяем что TonConnectUI доступен (пробуем разные варианты)
        const TonConnectUIClass = getTonConnectUIClass();
        if (typeof TonConnectUIClass === 'undefined') {
            throw new Error('TonConnectUI не загружен. Проверьте подключение к интернету и консоль браузера.');
        }
        
        if (!tonConnectUI) {
            // Определяем правильный URL для manifest
            const manifestUrl = window.location.origin + '/tonconnect-manifest.json';
            console.log('Инициализация TON Connect с manifest:', manifestUrl);
            
            try {
                tonConnectUI = new TonConnectUIClass({
                    manifestUrl: manifestUrl,
                    buttonRootId: undefined, // Не используем встроенную кнопку
                    language: 'ru'
                });

                // Дожидаемся восстановления сессии (если поддерживается)
                if (tonConnectUI.connectionRestored && typeof tonConnectUI.connectionRestored.then === 'function') {
                    try {
                        await tonConnectUI.connectionRestored;
                    } catch (e) {
                        console.warn('⚠️ TON Connect: не удалось восстановить сессию:', e);
                    }
                }
                
                // Обработка изменений статуса кошелька
                tonConnectUI.onStatusChange((wallet) => {
                    if (wallet) {
                        console.log('TON кошелек подключен:', wallet.account?.address || wallet.address);
                        updateWalletConnectionUI(wallet);
                    } else {
                        console.log('TON кошелек отключен');
                        updateWalletConnectionUI(null);
                    }
                });
                
                console.log('✅ TON Connect UI инициализирован');
            } catch (initError) {
                console.error('Ошибка создания TonConnectUI:', initError);
                throw new Error('Не удалось создать TonConnectUI: ' + initError.message);
            }
        }
        
        return tonConnectUI;
    } catch (error) {
        console.error('Ошибка инициализации TON Connect:', error);
        throw error;
    }
}

// Подключить TON кошелек
async function connectTONWallet() {
    console.log('🚀 Начало подключения TON кошелька...');
    try {
        console.log('📦 Инициализация TON Connect UI...');
        const ui = await initTONConnectUI();
        console.log('✅ TON Connect UI инициализирован:', ui);

        // На всякий случай ждём восстановления соединения перед чтением ui.wallet
        if (ui.connectionRestored && typeof ui.connectionRestored.then === 'function') {
            try { await ui.connectionRestored; } catch (_) {}
        }
        
        // Проверяем, подключен ли уже кошелек
        const wallet = ui.wallet;
        if (wallet) {
            console.log('✅ Кошелек уже подключен:', wallet);
            showToast('Кошелек уже подключен');
            updateWalletConnectionUI(wallet);
            return;
        }
        
        // Открываем модальное окно подключения
        console.log('📱 Открываем модальное окно TON Connect...');
        showToast('Подключение кошелька...');
        
        if (typeof ui.openModal === 'function') {
            await ui.openModal();
            console.log('✅ Модальное окно открыто');
        } else {
            console.error('❌ ui.openModal не является функцией!', typeof ui.openModal);
            // Пробуем альтернативный способ
            if (typeof ui.connectWallet === 'function') {
                await ui.connectWallet();
            } else {
                throw new Error('Метод openModal недоступен. Попробуйте обновить страницу.');
            }
        }
        
        // Обновляем UI после подключения (через обработчик onStatusChange)
    } catch (error) {
        console.error('❌ Ошибка подключения кошелька:', error);
        const errorMsg = error.message || error.toString();
        showToast('Ошибка подключения кошелька: ' + errorMsg);
        throw error; // Пробрасываем ошибку дальше для обработки
    }
}

// Проверить статус подключения кошелька
async function checkWalletConnectionStatus() {
    try {
        const ui = await initTONConnectUI();
        if (ui.connectionRestored && typeof ui.connectionRestored.then === 'function') {
            try { await ui.connectionRestored; } catch (_) {}
        }
        const wallet = ui.wallet;
        updateWalletConnectionUI(wallet);
    } catch (error) {
        console.error('Ошибка проверки статуса кошелька:', error);
    }
}

// Отключить TON кошелек
async function disconnectTONWallet() {
    console.log('🔌 Отключение TON кошелька...');
    try {
        const ui = await initTONConnectUI();
        if (ui && typeof ui.disconnect === 'function') {
            await ui.disconnect();
            console.log('✅ Кошелек отключен');
            showToast('Кошелек отключен');
            updateWalletConnectionUI(null);
        } else {
            // Если метод disconnect недоступен, просто очищаем состояние
            console.warn('⚠️ Метод disconnect недоступен, очищаем состояние вручную');
            updateWalletConnectionUI(null);
            showToast('Кошелек отключен');
        }
    } catch (error) {
        console.error('❌ Ошибка отключения кошелька:', error);
        showToast('Ошибка отключения кошелька: ' + (error.message || error));
    }
}

// Конвертировать адрес в формат UQ...
function convertToUQFormat(address) {
    if (!address) return '';
    
    // Если адрес уже в формате UQ, возвращаем как есть
    if (address.startsWith('UQ')) {
        return address;
    }
    
    try {
        // Используем TonWeb для конвертации если доступен
        if (typeof window.TonWeb !== 'undefined' && window.TonWeb.utils && window.TonWeb.utils.Address) {
            const TonWeb = window.TonWeb;
            try {
                // Создаем объект Address из строки (поддерживает любой формат: EQ, UQ, 0:...)
                const addressObj = new TonWeb.utils.Address(address);
                // Конвертируем в user-friendly формат UQ (non-bounceable)
                // toString параметры: (isUserFriendly, isUrlSafe, isBounceable)
                // isBounceable = false -> UQ формат (non-bounceable)
                const uqAddress = addressObj.toString(true, true, false);
                // Убеждаемся что адрес начинается с UQ
                if (uqAddress.startsWith('UQ')) {
                    return uqAddress;
                } else if (uqAddress.startsWith('EQ')) {
                    // Если все еще EQ, пытаемся еще раз с явным указанием
                    return addressObj.toString(true, true, false);
                }
                return uqAddress;
            } catch (e) {
                console.error('Ошибка конвертации через TonWeb:', e);
            }
        }
        
        // Fallback: если адрес в формате EQ, просто заменяем префикс на UQ
        // Это не идеально, но для отображения должно работать
        if (address.startsWith('EQ')) {
            return 'UQ' + address.substring(2);
        }
        
        // Если адрес в формате "0:...", конвертируем в UQ формат
        if (address.includes(':')) {
            const parts = address.split(':');
            if (parts.length === 2) {
                const workchain = parseInt(parts[0]);
                const hexAddress = parts[1];
                
                // Конвертируем hex в bytes
                const addressBytes = [];
                for (let i = 0; i < hexAddress.length; i += 2) {
                    addressBytes.push(parseInt(hexAddress.substr(i, 2), 16));
                }
                
                // Создаем массив: workchain (1 byte) + address (32 bytes)
                const addressWithWorkchain = [workchain, ...addressBytes];
                
                // Конвертируем в base64url
                const base64 = btoa(String.fromCharCode(...addressWithWorkchain))
                    .replace(/\+/g, '-')
                    .replace(/\//g, '_')
                    .replace(/=/g, '');
                
                return 'UQ' + base64;
            }
        }
    } catch (error) {
        console.error('Ошибка конвертации адреса:', error);
        // В случае ошибки пытаемся хотя бы заменить EQ на UQ
        if (address.startsWith('EQ')) {
            return 'UQ' + address.substring(2);
        }
        return address;
    }
    
    return address;
}

// Обновить UI статуса подключения кошелька
function updateWalletConnectionUI(wallet) {
    const statusText = document.getElementById('wallet-status-text');
    const addressContainer = document.getElementById('wallet-address-container');
    const addressClickable = document.getElementById('wallet-address');
    const addressText = document.getElementById('wallet-address-text');
    const connectBtn = document.getElementById('btn-connect-wallet');
    
    if (wallet) {
        const rawAddress = wallet.account?.address || wallet.address || '';
        
        // Конвертируем адрес в формат UQ
        const address = convertToUQFormat(rawAddress);
        
        // Скрываем кнопку подключения
        if (connectBtn) {
            connectBtn.classList.add('hidden');
        }
        
        // Показываем адрес кошелька
        if (addressContainer) {
            addressContainer.classList.remove('hidden');
        }
        if (addressText && address) {
            // Убеждаемся что адрес начинается с UQ (если все еще EQ, заменяем)
            let finalAddress = address;
            if (address.startsWith('EQ')) {
                finalAddress = 'UQ' + address.substring(2);
                console.log('Адрес конвертирован из EQ в UQ:', finalAddress);
            }
            
            // Форматируем адрес: показываем UQ и первые символы + ... + последние символы
            let formattedAddress;
            if (finalAddress.startsWith('UQ')) {
                // Для UQ формата показываем: UQ + первые 8 символов после UQ + ... + последние 8 символов
                const addressPart = finalAddress.substring(2); // Убираем префикс UQ
                if (addressPart.length <= 16) {
                    formattedAddress = finalAddress; // Показываем полностью если короткий
                } else {
                    const startPart = addressPart.substring(0, 8);
                    const endPart = addressPart.substring(addressPart.length - 8);
                    formattedAddress = `UQ${startPart}...${endPart}`;
                }
            } else if (finalAddress.length <= 20) {
                formattedAddress = finalAddress;
            } else {
                const startPart = finalAddress.substring(0, 6);
                const endPart = finalAddress.substring(finalAddress.length - 6);
                formattedAddress = `${startPart}...${endPart}`;
            }
            addressText.textContent = formattedAddress;
            addressText.title = `Нажмите, чтобы отключить кошелек\nПолный адрес: ${finalAddress}`;
        }
        
        // Удаляем старые обработчики и добавляем новый для отключения
        if (addressClickable) {
            // Клонируем элемент чтобы удалить все старые обработчики
            const newAddressClickable = addressClickable.cloneNode(true);
            addressClickable.parentNode.replaceChild(newAddressClickable, addressClickable);
            
            // Добавляем обработчик клика для отключения
            newAddressClickable.addEventListener('click', async () => {
                await disconnectTONWallet();
            });
        }
    } else {
        // Показываем кнопку подключения
        if (connectBtn) {
            connectBtn.classList.remove('hidden');
        }
        if (statusText) {
            statusText.textContent = '🔗 Подключить TON кошелек';
        }
        
        // Скрываем адрес кошелька
        if (addressContainer) {
            addressContainer.classList.add('hidden');
        }
        if (connectBtn) {
            connectBtn.style.background = '';
            connectBtn.style.opacity = '1';
        }
    }
}

// Показать модальное окно для пополнения через TON
function showDepositTONModal() {
    const modal = document.getElementById('modal-deposit-ton');
    if (modal) {
        modal.classList.add('active');
        // Сбрасываем форму
        const amountInput = document.getElementById('deposit-ton-amount');
        if (amountInput) {
            amountInput.value = '';
        }
    }
}

// Закрыть модальное окно пополнения TON
function closeDepositTONModal() {
    const modal = document.getElementById('modal-deposit-ton');
    if (modal) {
        modal.classList.remove('active');
    }
}

// Выполнить пополнение через TON Connect
async function processTONDeposit() {
    const amountInput = document.getElementById('deposit-ton-amount');
    const amount = parseFloat(amountInput?.value);
    
    if (!amount || amount <= 0) {
        showToast('Введите корректную сумму');
        return;
    }
    
    if (amount < 0.01) {
        showToast('Минимальная сумма пополнения: 0.01 TON');
        return;
    }
    
    try {
        // Получаем адрес для пополнения с API
        const response = await fetch(`${API_BASE}/wallet/deposit-address`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': getInitData()
            },
            body: JSON.stringify({
                amount: amount,
                currency: 'TON'
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Ошибка получения адреса для пополнения');
        }
        
        const data = await response.json();
        const depositAddress = data.address || data.deposit_address;
        
        if (!depositAddress) {
            throw new Error('Адрес для пополнения не получен');
        }
        
        // Инициализируем TON Connect UI
        const ui = await initTONConnectUI();
        
        // Проверяем, подключен ли кошелек
        // TON Connect UI может хранить информацию о кошельке в разных местах
        const wallet = ui.wallet || ui.account || (ui.connectionRestored && ui.connectionRestored.account);
        if (!wallet) {
            // Если кошелек не подключен, открываем модальное окно подключения
            showToast('Подключите кошелек для пополнения');
            ui.openModal();
            return; // Прерываем выполнение, пользователь должен подключить кошелек
        }
        
        // Конвертируем сумму в наноTON (1 TON = 1,000,000,000 наноTON)
        const amountInNano = Math.floor(amount * 1000000000);
        
        // Получаем user_id для memo (комментария транзакции)
        const userId = appState.user?.id;
        if (!userId) {
            throw new Error('User ID не найден');
        }
        
        // Создаем payload с текстовым комментарием (user_id) для автоматического начисления баланса
        // TON Connect ожидает Base64-encoded BoC для payload
        const commentText = String(userId);
        console.log('📝 Создание payload с комментарием (user_id):', commentText);
        
        let payloadBase64 = '';
        
        // Ждём загрузки библиотеки tonweb (если она ещё не загружена)
        let attempts = 0;
        while (attempts < 50 && typeof window.TonWeb === 'undefined') {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }
        
        try {
            // Используем tonweb для создания правильного BoC
            if (typeof window.TonWeb === 'undefined') {
                throw new Error('Библиотека TonWeb не загружена. Проверьте подключение скрипта в HTML.');
            }
            
            const TonWeb = window.TonWeb;
            
            // Создаем cell с текстовым комментарием используя tonweb
            // Формат: opcode 0 (32 бита) + UTF-8 текст
            const cell = new TonWeb.boc.Cell();
            cell.bits.writeUint(0, 32); // opcode для текстового комментария
            cell.bits.writeString(commentText); // текст комментария
            
            // Конвертируем в Base64 BoC
            const bocBytes = await cell.toBoc();
            payloadBase64 = TonWeb.utils.bytesToBase64(bocBytes);
            
            if (!payloadBase64 || payloadBase64.length === 0) {
                throw new Error('Payload пустой после создания через TonWeb');
            }
            
            console.log('✅ Payload создан через TonWeb, длина:', payloadBase64.length, 'первые 50 символов:', payloadBase64.substring(0, 50));
        } catch (error) {
            console.error('❌ Ошибка создания payload через TonWeb:', error);
            console.error('Доступные глобальные объекты:', Object.keys(window).filter(k => k.toLowerCase().includes('ton')));
            throw new Error('Не удалось создать payload с комментарием: ' + error.message + '. Убедитесь, что библиотека TonWeb загружена.');
        }
        
        // Создаем транзакцию согласно документации TON Connect
        // validUntil - время истечения транзакции (5 минут от текущего времени)
        const transaction = {
            validUntil: Math.floor(Date.now() / 1000) + 300, // 5 минут
            messages: [
                {
                    address: depositAddress,
                    amount: amountInNano.toString(), // Сумма в нанотонах как строка
                    payload: payloadBase64 // Payload с текстовым комментарием (user_id) в формате Base64-encoded BoC
                }
            ]
        };
        
        console.log('Отправка транзакции:', {
            address: depositAddress,
            amount: amountInNano,
            amountTON: amount,
            memo: String(userId),
            payloadLength: payloadBase64.length,
            payloadPreview: payloadBase64.substring(0, 50) + '...'
        });
        
        // Отправляем транзакцию
        const result = await ui.sendTransaction(transaction);
        
        console.log('Транзакция отправлена:', result);
        
        // Проверяем, что транзакция была успешно отправлена
        if (!result || !result.boc) {
            throw new Error('Транзакция не была отправлена');
        }
        
        showToast('Транзакция отправлена! Ожидаем подтверждения...');
        closeDepositTONModal();
        
        // Проверяем статус пополнения на сервере
        if (data.deposit_id || data.id) {
            await checkDepositStatus(data.deposit_id || data.id);
        } else {
            // Если deposit_id не получен, просто обновляем баланс через задержку
            setTimeout(async () => {
                await loadUserData();
            }, 5000);
        }
        
    } catch (error) {
        console.error('Ошибка пополнения через TON:', error);
        
        // Обработка различных типов ошибок согласно документации
        const errorMessage = error.message || error.toString();
        
        if (errorMessage.includes('User rejected') || 
            errorMessage.includes('declined') || 
            errorMessage.includes('rejected')) {
            showToast('Транзакция отменена пользователем');
        } else if (errorMessage.includes('timeout') || 
                   errorMessage.includes('Timeout')) {
            showToast('Время ожидания истекло');
        } else if (errorMessage.includes('not connected') || 
                   errorMessage.includes('wallet')) {
            showToast('Кошелек не подключен');
        } else {
            showToast(errorMessage || 'Ошибка пополнения через TON');
        }
    }
}

// Проверить статус пополнения
async function checkDepositStatus(depositId) {
    if (!depositId) return;
    
    const maxAttempts = 30; // 30 попыток (60 секунд)
    let attempts = 0;
    
    const checkInterval = setInterval(async () => {
        attempts++;
        
        try {
            const response = await fetch(`${API_BASE}/wallet/deposit-status/${depositId}`, {
                headers: {
                    'X-Telegram-Init-Data': getInitData()
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'completed' || data.status === 'confirmed' || data.status === 'success') {
                    clearInterval(checkInterval);
                    showToast('Пополнение подтверждено!');
                    await loadUserData();
                    return;
                } else if (data.status === 'failed' || data.status === 'error') {
                    clearInterval(checkInterval);
                    showToast('Ошибка при обработке пополнения');
                    return;
                }
            }
        } catch (error) {
            console.error('Ошибка проверки статуса:', error);
        }
        
        if (attempts >= maxAttempts) {
            clearInterval(checkInterval);
            console.log('Превышено максимальное количество попыток проверки статуса');
        }
    }, 2000); // Проверяем каждые 2 секунды
}

// Показать подарки
async function showGifts(isWithdraw = false) {
    try {
        console.log('🎁 Загрузка подарков...', { API_BASE, initData: !!getInitData() });
        
        // Убеждаемся, что контейнер видим
        const methodsContainer = isWithdraw 
            ? document.getElementById('withdraw-methods')
            : document.getElementById('deposit-methods');
        
        if (!methodsContainer) {
            console.error('❌ Контейнер методов не найден!');
            showToast('Ошибка: контейнер не найден');
            return;
        }
        
        // Показываем контейнер перед загрузкой
        methodsContainer.classList.remove('hidden');
        
        // Показываем индикатор загрузки
        const loadingIndicator = document.createElement('div');
        loadingIndicator.className = 'loading-indicator';
        loadingIndicator.innerHTML = '<div class="loading-circle"></div><div>Загрузка подарков...</div>';
        loadingIndicator.style.cssText = 'text-align: center; padding: 20px; color: var(--text-secondary);';
        methodsContainer.appendChild(loadingIndicator);
        
        try {
            // Создаем AbortController для timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 секунд
            
            const response = await fetch(`${API_BASE}/gifts`, {
                headers: {
                    'X-Telegram-Init-Data': getInitData()
                },
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            // Удаляем индикатор загрузки
            loadingIndicator.remove();
            
            if (response.ok) {
                const gifts = await response.json();
                console.log('✅ Подарки получены:', gifts);
                
                if (gifts && Array.isArray(gifts) && gifts.length > 0) {
                    displayGifts(gifts, isWithdraw);
                    // Убеждаемся, что контейнер видим после отображения
                    methodsContainer.classList.remove('hidden');
                } else {
                    console.warn('⚠️ Список подарков пуст или не является массивом:', gifts);
                    if (!Array.isArray(gifts)) {
                        showToast('Ошибка: неверный формат данных подарков');
                    } else {
                        showToast('Подарки не найдены');
                    }
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                console.error('❌ Ошибка загрузки подарков:', response.status, errorData);
                
                // Показываем сообщение об ошибке в контейнере
                const errorMsg = document.createElement('div');
                errorMsg.className = 'error-message';
                errorMsg.style.cssText = 'text-align: center; padding: 20px; color: var(--accent-red);';
                errorMsg.textContent = `Ошибка загрузки подарков (${response.status})`;
                methodsContainer.appendChild(errorMsg);
                
                showToast('Ошибка загрузки подарков');
            }
        } catch (fetchError) {
            // Удаляем индикатор загрузки
            loadingIndicator.remove();
            
            console.error('❌ Ошибка сети при загрузке подарков:', fetchError);
            
            // Показываем сообщение об ошибке в контейнере
            const errorMsg = document.createElement('div');
            errorMsg.className = 'error-message';
            errorMsg.style.cssText = 'text-align: center; padding: 20px; color: var(--accent-red);';
            
            if (fetchError.name === 'TimeoutError' || fetchError.name === 'AbortError') {
                errorMsg.textContent = 'Таймаут подключения к серверу';
            } else if (fetchError.message.includes('Failed to fetch')) {
                errorMsg.textContent = 'Ошибка подключения к серверу. Проверьте настройки API.';
            } else {
                errorMsg.textContent = `Ошибка: ${fetchError.message}`;
            }
            
            methodsContainer.appendChild(errorMsg);
            showToast('Ошибка подключения к серверу');
        }
    } catch (error) {
        console.error('❌ Критическая ошибка загрузки подарков:', error);
        showToast('Ошибка загрузки подарков');
    }
}

// Маппинг имен подарков на имена файлов (если имя в конфиге не совпадает с именем файла)
const GIFT_NAME_TO_FILE_MAP = {
    'plush pepe': 'plush-pepe',
    'heart locket': 'heart-locket',
    'durovs cap': 'durovs-cap',
    'precious peach': 'precious-peach',
    'b-day candle': 'b-day-candle',
    'jack-in-the-box': 'jack-in-the-box',
    'snoop dogg': 'snoop-dogg',
    'stellar rocket': 'stellar-rocket',
    'westside sign': 'westside-sign',
    'low rider': 'low-rider',
    'snoop cigar': 'snoop-cigar',
    'swag bag': 'swag-bag',
    'valentine box': 'valentine-box',
    'cupid charm': 'cupid-charm',
    'joyful bundle': 'joyful-bundle',
    'whip cupcake': 'whip-cupcake',
    'lush bouquet': 'lush-bouquet',
    'heart locket': 'heart-locket',
    'bow tie': 'bow-tie',
    'heroic helmet': 'heroic-helmet',
    'nail bracelet': 'nail-bracelet',
    'restless jar': 'restless-jar',
    'light sword': 'light-sword',
    'gem signet': 'gem-signet',
    'holiday drink': 'holiday-drink',
    'big year': 'big-year',
    'xmas stocking': 'xmas-stocking',
    'snake box': 'snake-box',
    'pet snake': 'pet-snake',
    'bonded ring': 'bonded-ring',
    'easter egg': 'easter-egg',
    'jack-in-the-box': 'jack-in-the-box',
    'neko helmet': 'neko-helmet',
    'candy cane': 'candy-cane',
    'tama gadget': 'tama-gadget',
    'electric skull': 'electric-skull',
    'snow globe': 'snow-globe',
    'winter wreath': 'winter-wreath',
    'record player': 'record-player',
    'top hat': 'top-hat',
    'sleigh bell': 'sleigh-bell',
    'sakura flower': 'sakura-flower',
    'diamond ring': 'diamond-ring',
    'toy bear': 'toy-bear',
    'love potion': 'love-potion',
    'loot bag': 'loot-bag',
    'star notepad': 'star-notepad',
    'ion gem': 'ion-gem',
    'lol pop': 'lol-pop',
    'mini oscar': 'mini-oscar',
    'ginger cookie': 'ginger-cookie',
    'swiss watch': 'swiss-watch',
    'eternal candle': 'eternal-candle',
    'crystal ball': 'crystal-ball',
    'flying broom': 'flying-broom',
    'astral shard': 'astral-shard',
    'bunny muffin': 'bunny-muffin',
    'hypno lollipop': 'hypno-lollipop',
    'mad pumpkin': 'mad-pumpkin',
    'voodoo doll': 'voodoo-doll',
    'snow mittens': 'snow-mittens',
    'jingle bells': 'jingle-bells',
    'desk calendar': 'desk-calendar',
    'cookie heart': 'cookie-heart',
    'love candle': 'love-candle',
    'hanging star': 'hanging-star',
    'witch hat': 'witch-hat',
    'jester hat': 'jester-hat',
    'party sparkler': 'party-sparkler',
    'lunar snake': 'lunar-snake',
    'genie lamp': 'genie-lamp',
    'homemade cake': 'homemade-cake',
    'spy agaric': 'spy-agaric',
    'scared cat': 'scared-cat',
    'skull flower': 'skull-flower',
    'trapped heart': 'trapped-heart',
    'sharp tongue': 'sharp-tongue',
    'evil eye': 'evil-eye',
    'hex pot': 'hex-pot',
    'kissed frog': 'kissed-frog',
    'magic potion': 'magic-potion',
    'vintage cigar': 'vintage-cigar',
    'berry box': 'berry-box',
    'eternal rose': 'eternal-rose',
    'perfume bottle': 'perfume-bottle',
    'mighty arm': 'mighty-arm',
    'input key': 'input-key',
    'ionic dryer': 'ionic-dryer',
    'moon pendant': 'moon-pendant',
    'fresh socks': 'fresh-socks',
    'sky stilettos': 'sky-stilettos',
    'clover pin': 'clover-pin',
    'artisan brick': 'artisan-brick',
    'spring basket': 'spring-basket',
    'ice cream': 'ice-cream',
    'happy brownie': 'happy-brownie',
    'mousse cake': 'mousse-cake',
    'instant ramen': 'instant-ramen',
    'faith amulet': 'faith-amulet',
    'bling binky': 'bling-binky',
    'money pot': 'money-pot',
    'pretty posy': 'pretty-posy',
    'ufc strike': 'ufc-strike',
    'khabibs papakha': 'khabibs-papakha',
    'signet ring': 'signet-ring',
    'spiced wine': 'spiced-wine',
    'santa hat': 'santa-hat',
    'jolly chimp': 'jolly-chimp',
    'jelly bunny': 'jelly-bunny'
};

// Преобразовать имя подарка в имя файла
function giftNameToFileName(name) {
    if (!name) return '';
    
    // Преобразуем имя в нижний регистр для поиска в маппинге
    const nameLower = name.toLowerCase().trim();
    
    // Сначала проверяем маппинг
    if (GIFT_NAME_TO_FILE_MAP[nameLower]) {
        const mappedName = GIFT_NAME_TO_FILE_MAP[nameLower];
        console.log(`✅ Маппинг подарка: "${name}" -> "${mappedName}.png"`);
        return mappedName;
    }
    
    // Если маппинга нет, преобразуем имя стандартным способом
    let fileName = nameLower
        .replace(/'/g, '')  // Убираем апострофы (например, "Durov's Cap" -> "durovs cap")
        .replace(/[^a-z0-9\s-]+/g, '')  // Убираем все не буквы/цифры/пробелы/дефисы (включая эмодзи)
        .trim()
        .replace(/\s+/g, '-')  // Заменяем пробелы на дефис
        .replace(/^-+|-+$/g, '')  // Убираем дефисы в начале и конце
        .replace(/-+/g, '-');  // Заменяем множественные дефисы на один
    
    console.log(`📦 Преобразование имени подарка: "${name}" -> "${fileName}.png"`);
    return fileName;
}

// Отобразить подарки
function displayGifts(gifts, isWithdraw) {
    const methodsContainer = isWithdraw 
        ? document.getElementById('withdraw-methods')
        : document.getElementById('deposit-methods');
    
    if (!methodsContainer) {
        console.error('❌ Контейнер методов не найден!');
        return;
    }
    
    // Убеждаемся, что контейнер видим
    methodsContainer.classList.remove('hidden');
    
    // Удаляем старую сетку подарков если она есть
    const oldGiftsGrid = methodsContainer.querySelector('.gifts-grid');
    if (oldGiftsGrid) {
        oldGiftsGrid.remove();
    }
    
    // Удаляем старую кнопку "Отправить подарок" если она есть (только для пополнения)
    if (!isWithdraw) {
        const oldSendBtn = methodsContainer.querySelector('a[href*="arbuzrelayer"]');
        if (oldSendBtn) {
            oldSendBtn.remove();
        }
    }
    
    // Удаляем старые кнопки методов (TON, CryptoBot) если они есть
    const oldMethodBtns = methodsContainer.querySelectorAll('.method-btn:not([id*="gifts"])');
    oldMethodBtns.forEach(btn => {
        // Сохраняем только кнопку "Подарки" если она есть
        if (!btn.id.includes('gifts') && !btn.id.includes('deposit-gifts') && !btn.id.includes('withdraw-gifts')) {
            btn.remove();
        }
    });
    
    // Для пополнения показываем кнопку "Отправить подарок" сверху
    if (!isWithdraw) {
        const sendGiftBtn = document.createElement('a');
        sendGiftBtn.href = 'https://t.me/arbuzrelayer';
        sendGiftBtn.target = '_blank';
        sendGiftBtn.className = 'method-btn';
        sendGiftBtn.style.cssText = 'text-decoration: none; display: block; margin-bottom: 20px; width: 100%;';
        sendGiftBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display: inline-block; vertical-align: middle; margin-right: 8px;">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
            <span>Отправить подарок</span>
        `;
        methodsContainer.insertBefore(sendGiftBtn, methodsContainer.firstChild);
    }
    
    // Создаем сетку подарков
    const giftsGrid = document.createElement('div');
    giftsGrid.className = 'gifts-grid';
    giftsGrid.style.marginTop = isWithdraw ? '0' : '0';
    
    gifts.forEach(gift => {
        const giftItem = document.createElement('div');
        giftItem.className = 'gift-item';
        
        // Определяем путь к изображению подарка из папки nft/png
        const fileName = giftNameToFileName(gift.name);
        
        // Для Netlify используем абсолютный путь от корня сайта
        // Файлы находятся в папке nft/png/ в корне мини-аппа
        // На Netlify путь должен быть '/nft/png/...' (абсолютный путь)
        const giftImagePathPng = `/nft/png/${fileName}.png`;
        
        // Используем ТОЛЬКО локальные PNG файлы из папки nft/png
        const imageUrl = giftImagePathPng;
        
        console.log(`📦 Загрузка изображения подарка "${gift.name}": ${imageUrl} (файл: ${fileName}.png)`);
        
        // Создаем элемент изображения с обработкой ошибок
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = gift.name;
        img.className = 'gift-image';
        img.onerror = function() {
            console.error(`❌ Не удалось загрузить изображение подарка: "${gift.name}"`, imageUrl);
            // Показываем placeholder вместо скрытия
            this.style.display = 'none';
            const placeholder = this.parentElement.querySelector('.gift-placeholder');
            if (placeholder) {
                placeholder.style.display = 'flex';
            }
        };
        img.onload = function() {
            console.log(`✅ Изображение загружено: "${gift.name}"`, imageUrl);
        };
        
        giftItem.innerHTML = `
            <div class="gift-image-container">
                <div class="gift-placeholder" style="display: none; width: 100%; height: 100%; background: rgba(0,255,136,0.1); border-radius: 10px; align-items: center; justify-content: center; color: var(--text-secondary); font-size: 12px;">
                    ${gift.name}
                </div>
            </div>
            <div class="gift-info">
                <div class="gift-price">${gift.price_ton ? gift.price_ton.toFixed(4) : '0.0000'} TON</div>
                <div class="gift-price-black">⚫️ ${gift.price_ton_black ? gift.price_ton_black.toFixed(4) : '0.0000'} TON</div>
            </div>
        `;
        
        // Добавляем изображение в контейнер
        const imageContainer = giftItem.querySelector('.gift-image-container');
        imageContainer.insertBefore(img, imageContainer.firstChild);
        
        // Делаем элемент неактивным (нельзя кликать)
        giftItem.style.pointerEvents = 'none';
        
        giftsGrid.appendChild(giftItem);
    });
    
    methodsContainer.appendChild(giftsGrid);
    console.log(`✅ Отображено подарков: ${gifts.length}`);
}

// Инициализация создания чека
function initCheckCreation() {
    appState.checkStep = 1;
    document.getElementById('check-step-1').classList.remove('hidden');
    document.getElementById('check-step-2').classList.add('hidden');
    document.getElementById('check-step-3').classList.add('hidden');
    document.getElementById('check-next').classList.remove('hidden');
    document.getElementById('check-create').classList.add('hidden');
    
    document.getElementById('check-next').addEventListener('click', () => {
        if (appState.checkStep === 1) {
            appState.checkStep = 2;
            document.getElementById('check-step-1').classList.add('hidden');
            document.getElementById('check-step-2').classList.remove('hidden');
        } else if (appState.checkStep === 2) {
            appState.checkStep = 3;
            document.getElementById('check-step-2').classList.add('hidden');
            document.getElementById('check-step-3').classList.remove('hidden');
            document.getElementById('check-next').classList.add('hidden');
            document.getElementById('check-create').classList.remove('hidden');
        }
    });
    
    document.getElementById('check-create').addEventListener('click', async () => {
        await createCheck();
    });
}

// Создать чек
async function createCheck() {
    const amount = parseFloat(document.getElementById('check-amount').value);
    const activations = parseInt(document.getElementById('check-activations').value);
    const text = document.getElementById('check-text').value;
    
    try {
        const response = await fetch(`${API_BASE}/check/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg.initData
            },
            body: JSON.stringify({
                amount,
                activations,
                text
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            showToast(`Чек создан: ${data.check_code}`);
            hideModal('modal-create-check');
        }
    } catch (error) {
        console.error('Ошибка создания чека:', error);
        showToast('Ошибка создания чека');
    }
}

// Загрузить лотереи
async function loadLotteries() {
    try {
        const response = await fetch(`${API_BASE}/lotteries`, {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });
        
        if (response.ok) {
            const lotteries = await response.json();
            displayLotteries(lotteries);
        }
    } catch (error) {
        console.error('Ошибка загрузки лотерей:', error);
    }
}

// Отобразить лотереи
function displayLotteries(lotteries) {
    const listContainer = document.getElementById('lotteries-list');
    
    if (lotteries.length === 0) {
        listContainer.innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Нет активных лотерей</p>';
        return;
    }
    
    listContainer.innerHTML = lotteries.map(lottery => {
        const userTickets = lottery.user_tickets !== undefined ? lottery.user_tickets : 0;
        const maxTickets = lottery.max_tickets_per_user || 999;
        const canBuy = userTickets < maxTickets;
        const buttonText = canBuy ? 'Участвовать' : 'Лимит достигнут';
        const buttonClass = canBuy ? 'btn-primary' : 'btn-primary';
        const buttonStyle = canBuy ? '' : 'opacity: 0.6; cursor: not-allowed;';
        
        return `
        <div class="lottery-item" style="background: var(--bg-card); border: 2px solid var(--border-color); border-radius: 12px; padding: 15px; margin-bottom: 10px;">
            <h3 style="margin-bottom: 10px;">${lottery.title}</h3>
            <p style="color: var(--text-secondary); margin-bottom: 10px;">${lottery.description}</p>
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <span>Ваши билеты: <b>${userTickets}/${maxTickets}</b></span>
                <span>Цена: <b>$${lottery.ticket_price.toFixed(2)}</b></span>
            </div>
            <div style="margin-bottom: 10px; color: var(--text-secondary); font-size: 0.9em;">
                Всего билетов: ${lottery.total_tickets || 0}
            </div>
            <button class="${buttonClass}" onclick="${canBuy ? `participateLottery(${lottery.id})` : ''}" style="${buttonStyle}" ${!canBuy ? 'disabled' : ''}>${buttonText}</button>
        </div>
        `;
    }).join('');
}

// Участвовать в лотерее
async function participateLottery(lotteryId) {
    try {
        const response = await fetch(`${API_BASE}/lottery/participate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg.initData
            },
            body: JSON.stringify({
                lottery_id: lotteryId
            })
        });
        
        if (response.ok) {
            showToast('Вы участвуете в лотерее!');
            // Обновляем данные пользователя
            await loadUserData();
            // Перезагружаем список лотерей чтобы обновить количество билетов
            await loadLotteries();
        } else {
            const errorData = await response.json().catch(() => ({ error: 'Неизвестная ошибка' }));
            showToast(errorData.error || 'Ошибка участия в лотерее');
        }
    } catch (error) {
        console.error('Ошибка участия в лотерее:', error);
        showToast('Ошибка участия в лотерее');
    }
}

// Загрузить данные профиля
async function loadProfileData() {
    try {
        // Сначала обновляем UI с текущими данными пользователя
        updateUI();
        
        // Затем загружаем данные профиля с сервера
        const response = await fetch(`${API_BASE}/profile`, {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('Данные профиля получены:', data);
            
            // Реферальная система
            const referralCountEl = document.getElementById('referral-count');
            const referralBalanceEl = document.getElementById('referral-balance');
            const referralLinkEl = document.getElementById('referral-link');
            
            if (referralCountEl) {
                referralCountEl.textContent = data.referral_count || 0;
            }
            
            if (referralBalanceEl) {
                referralBalanceEl.textContent = `$${(data.referral_balance || 0).toFixed(2)}`;
            }
            
            if (referralLinkEl) {
                referralLinkEl.value = data.referral_link || '';
            }
            
            
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.error('Ошибка загрузки профиля:', response.status, errorData);
        }
    } catch (error) {
        console.error('Ошибка загрузки профиля:', error);
    }
}

// Анимация числовых значений
function animateValue(element, start, end, duration, isCurrency = false) {
    const startTime = performance.now();
    const prefix = isCurrency ? '$' : '';
    const suffix = isCurrency ? '.00' : '';
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Используем easing функцию для плавной анимации
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(start + (end - start) * easeOutQuart);
        
        if (isCurrency) {
            element.textContent = `${prefix}${current.toFixed(2)}`;
        } else {
            element.textContent = current;
        }
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            if (isCurrency) {
                element.textContent = `${prefix}${end.toFixed(2)}`;
            } else {
                element.textContent = end;
            }
        }
    }
    
    requestAnimationFrame(update);
}


// Загрузить данные топа
async function loadTopData(category = 'players', period = 'day') {
    try {
        // Сохраняем текущие параметры для автообновления
        appState.currentTopCategory = category;
        appState.currentTopPeriod = period;
        
        const response = await fetch(`${API_BASE}/top?category=${category}&period=${period}`, {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            // Данные пользователя теперь приходят вместе с топом
            const userData = data.user || { position: null, turnover: 0 };
            displayTop(data, userData);
        } else {
            const errorData = await response.json().catch(() => ({}));
            showToast(errorData.error || 'Ошибка загрузки топа');
        }
    } catch (error) {
        console.error('Ошибка загрузки топа:', error);
        showToast('Ошибка загрузки топа');
    }
}

// Запустить автоматическое обновление топа
function startTopAutoRefresh() {
    // Останавливаем предыдущий интервал, если он был
    stopTopAutoRefresh();
    
    // Показываем индикатор автообновления
    const indicator = document.getElementById('top-refresh-status');
    if (indicator) {
        indicator.textContent = '🔄 Автообновление';
        indicator.style.opacity = '1';
    }
    
    // Обновляем топ каждые 30 секунд
    appState.topRefreshInterval = setInterval(() => {
        // Обновляем только если мы на странице топа
        if (appState.currentPage === 'top') {
            // Показываем анимацию обновления
            const statusEl = document.getElementById('top-refresh-status');
            if (statusEl) {
                statusEl.textContent = '⏳ Обновление...';
            }
            
            loadTopData(appState.currentTopCategory, appState.currentTopPeriod).then(() => {
                // После загрузки возвращаем обычный статус
                if (statusEl && appState.currentPage === 'top') {
                    statusEl.textContent = '🔄 Автообновление';
                }
            });
        }
    }, 30000); // 30 секунд
}

// Остановить автоматическое обновление топа
function stopTopAutoRefresh() {
    if (appState.topRefreshInterval) {
        clearInterval(appState.topRefreshInterval);
        appState.topRefreshInterval = null;
    }
    
    // Скрываем индикатор автообновления
    const indicator = document.getElementById('top-refresh-status');
    if (indicator) {
        indicator.style.opacity = '0.5';
    }
}

// Получить аватар пользователя
function getUserAvatar(userId, photoUrlFromApi = null) {
    // Если аватар пришел из API, используем его
    if (photoUrlFromApi) {
        return photoUrlFromApi;
    }
    
    // Пытаемся получить аватар из Telegram WebApp
    if (window.Telegram && window.Telegram.WebApp) {
        // Для текущего пользователя используем данные из WebApp
        if (window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user) {
            const currentUserId = window.Telegram.WebApp.initDataUnsafe.user.id;
            if (userId == currentUserId) {
                return window.Telegram.WebApp.initDataUnsafe.user.photo_url || '';
            }
        }
    }
    // Для других пользователей возвращаем пустую строку (будет показан placeholder)
    return '';
}

// Отобразить топ
function displayTop(data, userData = {}) {
    // Сохраняем данные топа для использования в модальном окне
    window.currentTopData = data;
    
    const topList = document.getElementById('top-list');
    const topPodium = document.getElementById('top-podium');
    const userPositionEl = document.getElementById('user-position');
    const userTurnoverEl = document.getElementById('user-turnover');
    
    // Проверяем, есть ли сообщение о том, что топ чатов не реализован
    if (data.message) {
        topPodium.innerHTML = '';
        topList.innerHTML = `<div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
            <div style="font-size: 48px; margin-bottom: 20px;">🚧</div>
            <div style="font-size: 16px; font-weight: 500; margin-bottom: 10px;">${data.message}</div>
        </div>`;
        if (userPositionEl) userPositionEl.textContent = '-';
        if (userTurnoverEl) userTurnoverEl.textContent = '$0.00';
        return;
    }
    
    // Обновляем статистику пользователя
    if (userPositionEl) {
        userPositionEl.textContent = `#${userData.position || '-'}`;
    }
    if (userTurnoverEl) {
        userTurnoverEl.textContent = `$${(userData.turnover || 0).toFixed(2)}`;
    }
    
    const topPlayers = data.top || [];
    const currentUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
    
    // Если топ пустой, показываем сообщение
    if (topPlayers.length === 0) {
        topPodium.innerHTML = '';
        topList.innerHTML = `<div style="text-align: center; padding: 40px 20px; color: var(--text-secondary);">
            <div style="font-size: 48px; margin-bottom: 20px;">📊</div>
            <div style="font-size: 16px; font-weight: 500;">Пока нет данных для отображения</div>
        </div>`;
        return;
    }
    
    // Подиум для топ-3
    if (topPodium && topPlayers.length >= 3) {
        const podiumPlayers = [
            topPlayers[1], // 2 место (серебро) - слева
            topPlayers[0], // 1 место (золото) - центр
            topPlayers[2]  // 3 место (бронза) - справа
        ];
        
        topPodium.innerHTML = podiumPlayers.map((item, podiumIndex) => {
            const actualRank = podiumIndex === 0 ? 2 : (podiumIndex === 1 ? 1 : 3);
            const avatar = getUserAvatar(item.user_id, item.photo_url);
            
            return `
                <div class="podium-item" onclick="showUserProfile(${item.user_id})">
                    <div class="podium-rank">#${actualRank}</div>
                    ${avatar ? `<img src="${avatar}" alt="${item.username}" class="podium-avatar" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ''}
                    ${!avatar ? `<div class="podium-avatar" style="background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,200,255,0.2)); display: flex; align-items: center; justify-content: center;">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                    </div>` : ''}
                    <div class="podium-name">${escapeHtml(item.username || `ID${item.user_id}`)}</div>
                    <div class="podium-value">$${item.turnover.toFixed(2)}</div>
                </div>
            `;
        }).join('');
    } else if (topPodium) {
        topPodium.innerHTML = '';
    }
    
    // Список остальных участников (начиная с 4 места)
    const remainingPlayers = topPlayers.slice(3);
    
    topList.innerHTML = remainingPlayers.map((item, index) => {
        const rank = index + 4; // Начинаем с 4 места
        const isCurrentUser = currentUserId && item.user_id == currentUserId;
        const avatar = getUserAvatar(item.user_id, item.photo_url);
        
        return `
            <div class="top-item ${isCurrentUser ? 'current-user' : ''}" onclick="showUserProfile(${item.user_id})" style="animation-delay: ${index * 0.05}s">
                <div class="top-item-position">#${rank}</div>
                ${avatar ? `<img src="${avatar}" alt="${item.username}" class="top-item-avatar" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">` : ''}
                ${!avatar ? `<div class="top-item-avatar" style="background: linear-gradient(135deg, rgba(0,255,136,0.2), rgba(0,200,255,0.2)); display: flex; align-items: center; justify-content: center;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                </div>` : ''}
                <div class="top-item-info">
                    <div class="top-item-name">${escapeHtml(item.username || `ID${item.user_id}`)}${isCurrentUser ? ' (Вы)' : ''}</div>
                    <div class="top-item-stats">Оборот: $${item.turnover.toFixed(2)}</div>
                </div>
                <div class="top-item-value">$${item.turnover.toFixed(2)}</div>
            </div>
        `;
    }).join('');
    
    // Если пользователь не в топ-3, но есть в списке, прокручиваем к нему
    if (currentUserId && remainingPlayers.some(p => p.user_id == currentUserId)) {
        setTimeout(() => {
            const userItem = topList.querySelector('.current-user');
            if (userItem) {
                userItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, 500);
    }
    
    // Инициализируем фильтры (только один раз)
    if (!window.topFiltersInitialized) {
        document.querySelectorAll('.btn-filter').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const period = document.querySelector('.btn-period.active')?.dataset.period || appState.currentTopPeriod || 'day';
                loadTopData(btn.dataset.category, period);
                // Перезапускаем автообновление с новыми параметрами
                startTopAutoRefresh();
            });
        });
        
        document.querySelectorAll('.btn-period').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.btn-period').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                const category = document.querySelector('.btn-filter.active')?.dataset.category || appState.currentTopCategory || 'players';
                loadTopData(category, btn.dataset.period);
                // Перезапускаем автообновление с новыми параметрами
                startTopAutoRefresh();
            });
        });
        
        window.topFiltersInitialized = true;
    }
}

// Экранирование HTML для безопасности
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Показать профиль пользователя
function showUserProfile(userId) {
    // Находим данные пользователя из текущего топа
    const topData = window.currentTopData || { top: [] };
    const userData = topData.top.find(u => u.user_id == userId);
    
    if (!userData) {
        showToast('Данные пользователя не найдены');
        return;
    }
    
    // Получаем аватар (используем photo_url из данных пользователя если есть)
    const avatar = getUserAvatar(userId, userData?.photo_url);
    
    // Заполняем модальное окно
    const modal = document.getElementById('modal-user-profile');
    const avatarEl = document.getElementById('profile-modal-avatar');
    const placeholderEl = avatarEl.nextElementSibling;
    const nameEl = document.getElementById('profile-modal-name');
    const idEl = document.getElementById('profile-modal-id');
    const positionEl = document.getElementById('profile-modal-position');
    const turnoverEl = document.getElementById('profile-modal-turnover');
    
    // Устанавливаем аватар
    if (avatar) {
        avatarEl.src = avatar;
        avatarEl.style.display = 'block';
        placeholderEl.style.display = 'none';
    } else {
        avatarEl.style.display = 'none';
        placeholderEl.style.display = 'flex';
    }
    
    // Устанавливаем данные
    nameEl.textContent = userData.username || `ID${userId}`;
    idEl.textContent = `ID: ${userId}`;
    
    // Находим позицию пользователя
    const position = topData.top.findIndex(u => u.user_id == userId) + 1;
    positionEl.textContent = `#${position}`;
    turnoverEl.textContent = `$${userData.turnover.toFixed(2)}`;
    
    // Показываем модальное окно
    showModal('modal-user-profile');
}

// Сохранить базовую ставку
async function saveBaseBet(value) {
    try {
        const response = await fetch(`${API_BASE}/settings/base-bet`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg.initData
            },
            body: JSON.stringify({
                base_bet: value
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            appState.baseBet = data.base_bet || value;
            // Обновляем данные пользователя для синхронизации
            await loadUserData();
            updateUI();
            updateSettingsUI();
            showToast('✅ Базовая ставка сохранена');
        } else {
            const errorData = await response.json().catch(() => ({}));
            showToast(errorData.error || 'Ошибка сохранения ставки');
        }
    } catch (error) {
        console.error('Ошибка сохранения базовой ставки:', error);
        showToast('Ошибка сохранения');
    }
}

// Загрузить настройки
async function loadSettings() {
    try {
        if (!appState.user || !appState.user.id) {
            await loadUserData();
        }
        
        // Загружаем реферальные уведомления
        const refNotificationsToggle = document.getElementById('ref-notifications-toggle');
        if (refNotificationsToggle && appState.user) {
            refNotificationsToggle.checked = appState.user.referral_notifications || false;
        }
        
        // Обновляем UI настроек
        updateSettingsUI();
    } catch (error) {
        console.error('Ошибка загрузки настроек:', error);
    }
}

// Обновить UI настроек
function updateSettingsUI() {
    // Обновляем базовую ставку
    const baseBetValue = document.getElementById('base-bet-value');
    if (baseBetValue && appState.baseBet) {
        baseBetValue.textContent = `$${appState.baseBet.toFixed(2)}`;
    }
}

// Переключить реферальные уведомления
async function toggleRefNotifications(enabled) {
    try {
        const response = await fetch(`${API_BASE}/settings/ref-notifications`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': tg.initData
            },
            body: JSON.stringify({
                referral_notifications: enabled
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (appState.user) {
                appState.user.referral_notifications = data.referral_notifications || enabled;
            }
            showToast(enabled ? '🔔 Реферальные уведомления включены' : '🔕 Реферальные уведомления выключены');
            
            // Вибрация при переключении
            if (localStorage.getItem('vibrationEnabled') !== 'false' && 'vibrate' in navigator) {
                navigator.vibrate(30);
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            showToast(errorData.error || 'Ошибка сохранения настройки');
            // Возвращаем переключатель в исходное состояние
            const toggle = document.getElementById('ref-notifications-toggle');
            if (toggle) {
                toggle.checked = !enabled;
            }
        }
    } catch (error) {
        console.error('Ошибка переключения реферальных уведомлений:', error);
        showToast('Ошибка сохранения');
        // Возвращаем переключатель в исходное состояние
        const toggle = document.getElementById('ref-notifications-toggle');
        if (toggle) {
            toggle.checked = !enabled;
        }
    }
}

// Показать модальное окно
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

// Скрыть модальное окно
function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Показать toast уведомление
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Копировать реферальную ссылку
document.getElementById('copy-referral-link')?.addEventListener('click', () => {
    const input = document.getElementById('referral-link');
    input.select();
    document.execCommand('copy');
    showToast('Ссылка скопирована!');
});

// ========== РУЛЕТКА ==========

// Состояние рулетки
const rouletteState = {
    sectors: 12, // Количество секторов
    currentSector: 0,
    bets: {}, // {sector: [{user_id, bet, avatar, percentage}]}
    totalBets: 0, // Общая сумма всех ставок
    userBet: 0, // Ставка текущего пользователя
    userSector: null, // Сектор текущего пользователя
    countdown: 60,
    countdownInterval: null,
    refreshInterval: null,
    wheelCanvas: null,
    wheelCtx: null,
    isSpinning: false,
    topTab: 'games', // 'games' или 'users'
    countdownStarted: false, // Начался ли отсчет
    minPlayers: 2, // Минимум игроков для начала отсчета
    currentRotation: 0, // Текущий угол поворота колеса
    spinningAnimation: null // ID анимации вращения
};

// Инициализация рулетки
function initRoulette() {
    const roulettePage = document.getElementById('page-roulette');
    if (!roulettePage) return;
    
    // Инициализация Canvas для колеса
    const canvas = document.getElementById('roulette-wheel');
    if (canvas) {
        rouletteState.wheelCanvas = canvas;
        rouletteState.wheelCtx = canvas.getContext('2d');
        resizeRouletteCanvas();
        // Удаляем старый обработчик resize если есть, чтобы не накапливались
        window.removeEventListener('resize', resizeRouletteCanvas);
        window.addEventListener('resize', resizeRouletteCanvas);
    }
    
    // Кнопка "Поставить" - клонируем для удаления старых обработчиков
    let betBtn = document.getElementById('btn-place-bet');
    if (betBtn && betBtn.parentNode) {
        const newBetBtn = betBtn.cloneNode(true);
        betBtn.parentNode.replaceChild(newBetBtn, betBtn);
        betBtn = newBetBtn;
        betBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            placeRouletteBet();
        });
    }
    
    // Кнопка добавления к ставке - клонируем для удаления старых обработчиков
    let addBetBtn = document.getElementById('btn-add-bet');
    if (addBetBtn && addBetBtn.parentNode) {
        const newAddBetBtn = addBetBtn.cloneNode(true);
        addBetBtn.parentNode.replaceChild(newAddBetBtn, addBetBtn);
        addBetBtn = newAddBetBtn;
        addBetBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            addToBet();
        });
    }
    
    // Поле ввода ставки - клонируем для удаления старых обработчиков
    let betInput = document.getElementById('roulette-bet-input');
    if (betInput && betInput.parentNode) {
        const newBetInput = betInput.cloneNode(true);
        // Сохраняем значение (нормализуем: используем точку для number input)
        const currentValue = betInput.value || '1.00';
        newBetInput.value = currentValue.replace(',', '.');
        betInput.parentNode.replaceChild(newBetInput, betInput);
        betInput = newBetInput;
        
        // Устанавливаем начальное значение если пустое
        if (!betInput.value || betInput.value === '') {
            betInput.value = (appState.baseBet || 1.0).toFixed(2);
        }
        
        betInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                placeRouletteBet();
            }
        });
        
        // Обработчик для ввода - нормализуем значение (заменяем запятую на точку)
        betInput.addEventListener('input', (e) => {
            let value = e.target.value;
            // Заменяем запятую на точку для корректной работы с type="number"
            if (value.includes(',')) {
                value = value.replace(',', '.');
                e.target.value = value;
            }
        });
    }
    
    // Быстрые кнопки ставок - клонируем для удаления старых обработчиков
    document.querySelectorAll('.bet-quick-btn-roulette').forEach(btn => {
        if (btn.parentNode) {
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
            
            newBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                // Убираем активность с других кнопок
                document.querySelectorAll('.bet-quick-btn-roulette').forEach(b => b.classList.remove('active'));
                newBtn.classList.add('active');
                
                const value = newBtn.dataset.value;
                const input = document.getElementById('roulette-bet-input');
                if (input) {
                    if (value === 'base') {
                        input.value = appState.baseBet.toFixed(2);
                    } else {
                        input.value = parseFloat(value).toFixed(2);
                    }
                    // Фокусируем поле ввода
                    input.focus();
                }
            });
        }
    });
    
    // Кнопка чат (если есть)
    const chatBtn = document.getElementById('btn-roulette-chat');
    if (chatBtn && chatBtn.parentNode) {
        const newChatBtn = chatBtn.cloneNode(true);
        chatBtn.parentNode.replaceChild(newChatBtn, chatBtn);
        newChatBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            showToast('Чат скоро будет доступен');
        });
    }
}

// Изменение размера Canvas
function resizeRouletteCanvas() {
    if (!rouletteState.wheelCanvas) return;
    
    const wrapper = rouletteState.wheelCanvas.closest('.roulette-wheel-wrapper');
    if (!wrapper) return;
    
    const size = Math.max(Math.min(wrapper.offsetWidth, wrapper.offsetHeight), 50); // Минимальный размер 50px
    rouletteState.wheelCanvas.width = size;
    rouletteState.wheelCanvas.height = size;
    
    drawRouletteWheel();
}

// Отрисовка колеса рулетки
function drawRouletteWheel() {
    if (!rouletteState.wheelCtx || !rouletteState.wheelCanvas) return;
    
    const ctx = rouletteState.wheelCtx;
    const canvas = rouletteState.wheelCanvas;
    
    // Проверяем, что canvas имеет валидный размер
    if (canvas.width < 30 || canvas.height < 30) {
        console.warn('Canvas слишком маленький для отрисовки рулетки');
        return;
    }
    
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.max(Math.min(centerX, centerY) - 15, 10); // Минимальный радиус 10px
    
    // Очистка
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Рисуем фон колеса (темный круг)
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.fillStyle = '#1a1a1a';
    ctx.fill();
    
    // Сохраняем контекст для поворота
    ctx.save();
    ctx.translate(centerX, centerY);
    ctx.rotate((rouletteState.currentRotation * Math.PI) / 180);
    ctx.translate(-centerX, -centerY);
    
    // Вычисляем размеры секторов на основе процентов ставок
    const sectorSizes = calculateSectorSizes();
    
    // Проверяем, есть ли секторы для отрисовки
    const hasSectors = sectorSizes.some(size => size > 0);
    
    // Цвета для секторов (разные цвета для разных игроков)
    const sectorColors = [
        ['#7DD3FC', '#0EA5E9'], // Голубой
        ['#FBBF24', '#F59E0B'], // Оранжевый
        ['#F9A8D4', '#EC4899'], // Розовый
        ['#A78BFA', '#8B5CF6'], // Фиолетовый
        ['#34D399', '#10B981'], // Зеленый
        ['#F87171', '#EF4444'], // Красный
        ['#60A5FA', '#3B82F6'], // Синий
        ['#FCD34D', '#FBBF24'], // Желтый
        ['#A7F3D0', '#6EE7B7'], // Светло-зеленый
        ['#C7D2FE', '#818CF8'], // Индиго
        ['#FBCFE8', '#F472B6'], // Пинк
        ['#BFDBFE', '#60A5FA']  // Светло-синий
    ];
    
    // Рисуем только секторы со ставками
    if (hasSectors) {
        let currentAngle = -Math.PI / 2;
        let sectorColorIndex = 0;
        
        for (let i = 0; i < rouletteState.sectors; i++) {
            const sectorSize = sectorSizes[i];
            
            // Пропускаем секторы без ставок (размер 0 или null)
            if (!sectorSize || sectorSize <= 0) {
                continue;
            }
            
            const sectorAngleSize = sectorSize * 2 * Math.PI;
            const startAngle = currentAngle;
            const endAngle = currentAngle + sectorAngleSize;
            const midAngle = (startAngle + endAngle) / 2;
            
            const sectorBets = rouletteState.bets[i] || [];
            
            // Получаем цвет для сектора
            const colors = sectorColors[sectorColorIndex % sectorColors.length];
            sectorColorIndex++;
            
            // Рисуем сектор
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.arc(centerX, centerY, radius, startAngle, endAngle);
            ctx.closePath();
            
            // Используем простой цвет вместо градиента для лучшего качества
            ctx.fillStyle = colors[1]; // Более насыщенный цвет
            ctx.fill();
            
            // Обводка сектора
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Разделительные линии между секторами
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(
                centerX + Math.cos(startAngle) * radius,
                centerY + Math.sin(startAngle) * radius
            );
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Аватары в секторах (рисуем только первый аватар в центре сектора)
            if (sectorBets.length > 0 && sectorBets[0]) {
                const avatarRadius = radius * 0.65; // Позиция ближе к краю
                const avatarX = centerX + Math.cos(midAngle) * avatarRadius;
                const avatarY = centerY + Math.sin(midAngle) * avatarRadius;
                const avatarSize = Math.min(radius * 0.25, 40); // Размер аватара зависит от размера колеса
                
                const bet = sectorBets[0]; // Берем первого игрока в секторе
                
                // Рисуем аватар
                if (bet.avatar) {
                    const img = new Image();
                    img.crossOrigin = 'anonymous';
                    img.onload = () => {
                        // Рисуем круглый аватар без обводки и эффектов
                        ctx.save();
                        ctx.beginPath();
                        ctx.arc(avatarX, avatarY, avatarSize / 2, 0, 2 * Math.PI);
                        ctx.clip();
                        ctx.drawImage(img, avatarX - avatarSize / 2, avatarY - avatarSize / 2, avatarSize, avatarSize);
                        ctx.restore();
                        
                        // Перерисовываем после загрузки только если не идет вращение
                        if (!rouletteState.isSpinning) {
                            drawRouletteWheel();
                        }
                    };
                    img.onerror = () => {
                        // Если аватар не загрузился, рисуем простой круг
                        ctx.save();
                        ctx.beginPath();
                        ctx.arc(avatarX, avatarY, avatarSize / 2, 0, 2 * Math.PI);
                        ctx.fillStyle = '#555555';
                        ctx.fill();
                        ctx.fillStyle = '#ffffff';
                        ctx.font = `bold ${avatarSize / 3}px Arial`;
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillText('?', avatarX, avatarY);
                        ctx.restore();
                    };
                    img.src = bet.avatar;
                }
            }
            
            currentAngle = endAngle;
        }
    }
    
    // Восстанавливаем контекст
    ctx.restore();
    
    // Внешняя обводка колеса
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 4;
    ctx.shadowBlur = 0;
    ctx.shadowColor = 'transparent';
    ctx.stroke();
}

// Вычисление размеров секторов на основе процентов ставок
function calculateSectorSizes() {
    const sizes = new Array(rouletteState.sectors).fill(0);
    
    // Вычисляем процент каждой ставки по секторам
    const sectorTotals = {};
    let totalWithBets = 0;
    
    // Проверяем формат данных ставок
    // Может быть объект {sector: [bets]} или массив
    const bets = rouletteState.bets || {};
    
    for (let sector = 0; sector < rouletteState.sectors; sector++) {
        // Поддерживаем разные форматы: bets[sector] или bets[sector.toString()]
        const sectorBets = bets[sector] || bets[sector.toString()] || [];
        let sectorTotal = 0;
        
        if (Array.isArray(sectorBets)) {
            sectorBets.forEach(bet => {
                const betAmount = typeof bet === 'number' ? bet : (bet.bet || bet.amount || 0);
                sectorTotal += betAmount;
            });
        } else if (typeof sectorBets === 'number') {
            sectorTotal = sectorBets;
        }
        
        if (sectorTotal > 0) {
            sectorTotals[sector] = sectorTotal;
            totalWithBets += sectorTotal;
        }
    }
    
    // Если нет ставок, не отрисовываем секторы (возвращаем все нули)
    if (totalWithBets === 0) {
        console.log('⚠️ Нет ставок для отрисовки секторов');
        return sizes; // Все нули - секторы не будут отрисованы
    }
    
    // Распределяем пропорционально - только для секторов со ставками
    for (let i = 0; i < rouletteState.sectors; i++) {
        if (sectorTotals[i] && sectorTotals[i] > 0) {
            sizes[i] = sectorTotals[i] / totalWithBets;
        }
        // Секторы без ставок остаются 0 - они не будут отрисованы
    }
    
    console.log('📐 Размеры секторов:', sizes);
    return sizes;
}

// Обновление аватарки в центре - больше не используется, только счетчик
function updateCenterAvatar(avatarUrl) {
    // Аватар больше не показываем в центре, только счетчик
    // Функция оставлена для совместимости, но ничего не делает
}

// Загрузка данных рулетки
async function loadRouletteData() {
    try {
        const response = await fetch(`${API_BASE}/roulette/data`, {
            headers: {
                'X-Telegram-Init-Data': getInitData()
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Обновляем статистику
            const participants = data.participants || 0;
            document.getElementById('roulette-participants').textContent = participants;
            document.getElementById('roulette-total-bets').textContent = `$${(data.total_bets || 0).toFixed(2)}`;
            document.getElementById('roulette-user-bet').textContent = `$${(data.user_bet || 0).toFixed(2)}`;
            
            // Обновляем номер игры и количество игроков
            document.getElementById('roulette-game-id').textContent = data.game_id || '-';
            document.getElementById('roulette-players-count').textContent = participants;
            
            // Обновляем ставки и общую сумму
            rouletteState.bets = data.bets || {};
            rouletteState.totalBets = data.total_bets || 0;
            rouletteState.userBet = data.user_bet || 0;
            rouletteState.userSector = data.user_sector || null;
            
            // Логируем для отладки
            console.log('📊 Данные рулетки:', {
                bets: rouletteState.bets,
                totalBets: rouletteState.totalBets,
                userBet: rouletteState.userBet
            });
            
            // Обновляем игроков
            updateRoulettePlayers(data.players || []);
            
            // Аватар больше не показываем в центре
            
            // Обновляем счетчик - начинаем только при 2+ игроках
            if (data.countdown !== undefined) {
                rouletteState.countdown = data.countdown;
                
                // Начинаем отсчет только если есть минимум 2 игрока
                if (participants >= rouletteState.minPlayers) {
                    if (!rouletteState.countdownStarted) {
                        rouletteState.countdownStarted = true;
                        startCountdown();
                    } else if (!rouletteState.countdownInterval) {
                        // Если отсчет уже начался, но интервал остановлен, перезапускаем
                        startCountdown();
                    }
                    updateCountdown();
                } else {
                    // Если игроков меньше 2, останавливаем счетчик
                    if (rouletteState.countdownInterval) {
                        clearInterval(rouletteState.countdownInterval);
                        rouletteState.countdownInterval = null;
                    }
                    rouletteState.countdownStarted = false;
                    const countdownEl = document.getElementById('roulette-countdown');
                    if (countdownEl) {
                        countdownEl.textContent = 'Ждем...';
                        countdownEl.style.fontSize = '24px';
                    }
                }
            }
            
            // Перерисовываем колесо
            drawRouletteWheel();
        }
    } catch (error) {
        console.error('Ошибка загрузки данных рулетки:', error);
    }
}

// Обновление списка игроков
function updateRoulettePlayers(players) {
    const container = document.getElementById('roulette-players');
    if (!container) return;
    
    container.innerHTML = '';
    
    players.forEach(player => {
        const avatar = document.createElement('img');
        avatar.className = 'roulette-player-avatar';
        avatar.src = player.avatar || 'https://via.placeholder.com/40';
        avatar.alt = player.name || 'Player';
        avatar.onerror = () => {
            avatar.style.display = 'none';
        };
        container.appendChild(avatar);
    });
}

// Обновление счетчика
function updateCountdown() {
    const countdownEl = document.getElementById('roulette-countdown');
    if (countdownEl) {
        countdownEl.textContent = rouletteState.countdown;
        countdownEl.style.fontSize = '42px'; // Возвращаем нормальный размер
        
        // Плавная анимация без ярких цветов
        countdownEl.style.animation = 'countdownPulse 2s ease-in-out infinite';
        countdownEl.style.color = '#888888'; // Серый цвет
    }
}

// Запуск счетчика
function startCountdown() {
    if (rouletteState.countdownInterval) {
        clearInterval(rouletteState.countdownInterval);
    }
    
    // Обновляем счетчик сразу
    updateCountdown();
    
    rouletteState.countdownInterval = setInterval(() => {
        rouletteState.countdown--;
        updateCountdown();
        
        // Когда счетчик доходит до 0, запускаем вращение колеса
        if (rouletteState.countdown <= 0) {
            clearInterval(rouletteState.countdownInterval);
            rouletteState.countdownInterval = null;
            spinWheel();
        }
    }, 1000);
}

// Вычисление выигрышного сектора по текущему углу поворота
function calculateWinningSectorFromRotation() {
    // Указатель находится вверху (-90° = -Math.PI/2)
    // Секторы начинаются сверху с -Math.PI/2
    // После поворота на currentRotation, нужно найти, какой сектор под указателем
    
    // Текущий угол поворота в радианах
    const rotationRad = (rouletteState.currentRotation * Math.PI) / 180;
    
    // Угол под указателем (вверху = -Math.PI/2)
    const pointerAngle = -Math.PI / 2;
    
    // Обратный поворот: какой угол был под указателем до поворота колеса
    // Если колесо повернуто на rotationRad, то элемент в позиции angle теперь в позиции (angle + rotationRad)
    // Значит, элемент под указателем был в позиции (pointerAngle - rotationRad)
    const angleUnderPointer = pointerAngle - rotationRad;
    
    // Нормализуем угол в диапазон [0, 2π]
    let normalizedAngle = angleUnderPointer % (2 * Math.PI);
    if (normalizedAngle < 0) {
        normalizedAngle += 2 * Math.PI;
    }
    
    // Вычисляем размеры секторов
    const sectorSizes = calculateSectorSizes();
    
    // Находим, в какой сектор попадает этот угол
    let currentAngle = 0; // В нормализованных координатах начинаем с 0
    for (let i = 0; i < rouletteState.sectors; i++) {
        const sectorSize = sectorSizes[i] || 0;
        if (sectorSize > 0) {
            const sectorAngleSize = sectorSize * 2 * Math.PI;
            const sectorEndAngle = currentAngle + sectorAngleSize;
            
            // Проверяем, попадает ли угол в этот сектор
            if (normalizedAngle >= currentAngle && normalizedAngle < sectorEndAngle) {
                return i;
            }
            
            currentAngle = sectorEndAngle;
        }
    }
    
    // Если не нашли (не должно происходить), возвращаем первый сектор со ставкой
    for (let i = 0; i < rouletteState.sectors; i++) {
        if (sectorSizes[i] > 0) {
            return i;
        }
    }
    
    return 0; // Fallback
}

// Вращение колеса
async function spinWheel() {
    if (rouletteState.isSpinning) return;
    
    rouletteState.isSpinning = true;
    const countdownEl = document.getElementById('roulette-countdown');
    const wheelEl = document.getElementById('roulette-wheel');
    
    if (countdownEl) {
        countdownEl.textContent = '🎰';
        countdownEl.style.fontSize = '48px';
    }
    
    // Добавляем класс для анимации вращения
    if (wheelEl) {
        wheelEl.classList.add('is-spinning');
        const wrapper = wheelEl.closest('.roulette-wheel-wrapper');
        if (wrapper) {
            wrapper.classList.add('is-spinning');
        }
    }
    
    // Вычисляем размеры секторов
    const sectorSizes = calculateSectorSizes();
    
    // Выбираем случайный выигрышный сектор (из тех, где есть ставки)
    const sectorsWithBets = [];
    for (let i = 0; i < rouletteState.sectors; i++) {
        if (sectorSizes[i] > 0) {
            sectorsWithBets.push(i);
        }
    }
    
    // Если есть секторы со ставками, выбираем случайный из них
    // Если нет, выбираем случайный из всех
    const availableSectors = sectorsWithBets.length > 0 ? sectorsWithBets : 
                             Array.from({length: rouletteState.sectors}, (_, i) => i);
    const randomWinningSectorIndex = Math.floor(Math.random() * availableSectors.length);
    const randomWinningSector = availableSectors[randomWinningSectorIndex];
    
    // Вычисляем центр выигрышного сектора с учетом размеров секторов
    // Секторы начинаются сверху с -Math.PI/2
    let currentAngle = -Math.PI / 2;
    let winningSectorCenterAngle = -Math.PI / 2;
    
    for (let i = 0; i < rouletteState.sectors; i++) {
        const sectorSize = sectorSizes[i] || 0;
        if (sectorSize > 0) {
            const sectorAngleSize = sectorSize * 2 * Math.PI;
            const midAngle = currentAngle + sectorAngleSize / 2;
            
            if (i === randomWinningSector) {
                winningSectorCenterAngle = midAngle;
                break;
            }
            
            currentAngle += sectorAngleSize;
        }
    }
    
    // Вычисляем финальный угол поворота так, чтобы центр выбранного сектора оказался под указателем (вверху)
    // Указатель находится вверху (-90° или -Math.PI/2)
    // Чтобы центр сектора оказался вверху, нужно повернуть на противоположный угол
    const totalRotations = 5 + Math.random() * 2; // 5-7 полных оборотов для эффекта
    const finalRotationRad = -winningSectorCenterAngle + (totalRotations * 2 * Math.PI);
    const finalAngle = finalRotationRad * (180 / Math.PI); // Конвертируем в градусы
    
    const startTime = Date.now();
    const startRotation = rouletteState.currentRotation;
    
    // Продолжительность вращения
    const spinDuration = 3000 + Math.random() * 1000; // 3-4 секунды
    
    // Плавная easing функция без резких движений
    function smoothEase(t) {
        // Плавное замедление без пружинных эффектов
        return 1 - Math.pow(1 - t, 3);
    }
    
    function animate() {
        const currentTime = Date.now();
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / spinDuration, 1);
        
        // Используем плавную easing функцию
        const easedProgress = smoothEase(progress);
        
        // Вычисляем текущий угол с учетом easing
        rouletteState.currentRotation = startRotation + (finalAngle * easedProgress);
        
        drawRouletteWheel();
        
        // Обновляем текст счетчика во время вращения
        if (countdownEl && progress < 0.95) {
            countdownEl.textContent = '...';
        }
        
        if (progress < 1) {
            rouletteState.spinningAnimation = requestAnimationFrame(animate);
        } else {
            // Анимация завершена
            rouletteState.currentRotation = startRotation + finalAngle;
            drawRouletteWheel();
            
            // Убираем класс анимации
            if (wheelEl) {
                wheelEl.classList.remove('is-spinning');
                const wrapper = wheelEl.closest('.roulette-wheel-wrapper');
                if (wrapper) {
                    wrapper.classList.remove('is-spinning');
                }
            }
            
            rouletteState.isSpinning = false;
            
            // Вычисляем реальный выигрышный сектор по положению указателя
            const actualWinningSector = calculateWinningSectorFromRotation();
            
            // Небольшая задержка перед отправкой результата
            setTimeout(() => {
                finishRound(actualWinningSector);
            }, 300);
        }
    }
    
    animate();
}

// Завершение раунда
async function finishRound(winningSector) {
    try {
        const response = await fetch(`${API_BASE}/roulette/finish`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': getInitData()
            },
            body: JSON.stringify({ winning_sector: winningSector })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Показываем результат
            const countdownEl = document.getElementById('roulette-countdown');
            if (countdownEl) {
                if (data.winner) {
                    countdownEl.textContent = `Победитель: ${data.winner.username || 'Игрок'}!`;
                    showToast(`🎉 Выигрыш: $${data.win_amount?.toFixed(2) || '0.00'}`);
                } else {
                    countdownEl.textContent = 'Раунд завершен';
                }
            }
            
            // Обновляем данные
            await loadUserData();
            await loadRouletteData();
            
            // Сбрасываем состояние для нового раунда
            setTimeout(() => {
                rouletteState.countdown = 60;
                rouletteState.countdownStarted = false;
                rouletteState.currentRotation = 0;
                if (countdownEl) {
                    countdownEl.textContent = '60';
                }
                drawRouletteWheel();
            }, 5000);
        }
    } catch (error) {
        console.error('Ошибка завершения раунда:', error);
    }
}

// Добавление к ставке
function addToBet() {
    const betInput = document.getElementById('roulette-bet-input');
    if (!betInput) return;
    
    // Нормализуем значение (заменяем запятую на точку)
    const normalizedValue = betInput.value.replace(',', '.');
    const currentBet = parseFloat(normalizedValue) || 0;
    const addAmount = appState.baseBet || 1.0;
    const newBet = currentBet + addAmount;
    
    // Проверяем баланс
    if (newBet > appState.balance) {
        showToast('Недостаточно средств');
        betInput.value = appState.balance.toFixed(2);
        return;
    }
    
    betInput.value = newBet.toFixed(2);
    betInput.focus();
}

// Размещение ставки
async function placeRouletteBet() {
    const betInput = document.getElementById('roulette-bet-input');
    if (!betInput) {
        console.error('Поле ввода ставки не найдено');
        showToast('Ошибка: поле ввода ставки не найдено');
        return;
    }
    
    // Нормализуем значение (заменяем запятую на точку)
    const normalizedValue = betInput.value.replace(',', '.');
    const bet = parseFloat(normalizedValue);
    
    if (!bet || isNaN(bet) || bet < 0.1) {
        showToast('Минимальная ставка: $0.10');
        // Восстанавливаем корректное значение
        betInput.value = '1,00';
        return;
    }
    
    if (bet > appState.balance) {
        showToast('Недостаточно средств');
        return;
    }
    
    // Проверяем, не идет ли уже вращение
    if (rouletteState.isSpinning) {
        showToast('Дождитесь завершения раунда');
        return;
    }
    
    // Блокируем кнопку
    const betBtn = document.getElementById('btn-place-bet');
    if (betBtn) {
        betBtn.disabled = true;
        betBtn.textContent = 'Размещение...';
    }
    
    try {
        console.log('Отправка ставки:', bet);
        const response = await fetch(`${API_BASE}/roulette/bet`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-Init-Data': getInitData()
            },
            body: JSON.stringify({ bet })
        });
        
        console.log('Ответ сервера:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('Данные ответа:', data);
            showToast('Ставка размещена!');
            
            // Аватар больше не показываем в центре
            
            await loadUserData(); // Обновляем баланс
            await loadRouletteData(); // Обновляем данные рулетки
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.error('Ошибка ответа:', errorData);
            showToast(errorData.error || 'Ошибка размещения ставки');
        }
    } catch (error) {
        console.error('Ошибка размещения ставки:', error);
        showToast('Ошибка размещения ставки: ' + error.message);
    } finally {
        // Разблокируем кнопку
        if (betBtn) {
            betBtn.disabled = false;
            betBtn.textContent = 'Поставить';
        }
    }
}

// Загрузка топа
async function loadRouletteTop() {
    const container = document.getElementById('roulette-top-content');
    if (!container) return;
    
    try {
        const endpoint = rouletteState.topTab === 'games' 
            ? `${API_BASE}/roulette/top/games`
            : `${API_BASE}/roulette/top/users`;
        
        const response = await fetch(endpoint, {
            headers: {
                'X-Telegram-Init-Data': getInitData()
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            renderRouletteTop(data.items || []);
        }
    } catch (error) {
        console.error('Ошибка загрузки топа:', error);
    }
}

// Отрисовка топа
function renderRouletteTop(items) {
    const container = document.getElementById('roulette-top-content');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (items.length === 0) {
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Пока нет данных</div>';
        return;
    }
    
    items.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'roulette-top-item';
        
        const avatar = item.avatar || 'https://via.placeholder.com/40';
        const name = item.name || item.username || 'Игрок';
        const value = rouletteState.topTab === 'games' 
            ? `Игра #${item.game_id || index + 1}`
            : `$${(item.total || 0).toFixed(2)}`;
        
        div.innerHTML = `
            <div class="roulette-top-rank">${index + 1}</div>
            <img class="roulette-top-avatar" src="${avatar}" alt="${name}" onerror="this.style.display='none'">
            <div class="roulette-top-info">
                <div class="roulette-top-name">${name}</div>
                <div class="roulette-top-value">${value}</div>
            </div>
        `;
        
        container.appendChild(div);
    });
}

// Загрузка стикера ruletka_base (больше не используется)
async function loadRouletteBaseSticker() {
    // Аватар больше не показываем в центре, только счетчик
    // Функция оставлена для совместимости
}

// Открытие страницы рулетки
async function openRoulettePage() {
    const loadingEl = document.getElementById('roulette-loading');
    const contentEl = document.getElementById('roulette-content');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (contentEl) contentEl.style.display = 'none';

    try {
        // Инициализируем обработчики событий для кнопок ставок
        initRoulette();
        
        // Инициализируем Canvas если еще не инициализирован
        if (!rouletteState.wheelCanvas || !rouletteState.wheelCtx) {
            const canvas = document.getElementById('roulette-wheel');
            if (canvas) {
                rouletteState.wheelCanvas = canvas;
                rouletteState.wheelCtx = canvas.getContext('2d');
                resizeRouletteCanvas();
            }
        }

        // Загружаем данные
        await loadRouletteData();
        
        // Аватар больше не показываем в центре
        
        // Запускаем автообновление
        startRouletteAutoRefresh();
        
        // Счетчик запустится автоматически при загрузке данных если есть 2+ игрока
    } catch (error) {
        console.error('Ошибка загрузки рулетки:', error);
        showToast('Ошибка загрузки рулетки');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
        if (contentEl) contentEl.style.display = 'block';
    }
}

// Закрытие страницы рулетки
function closeRoulettePage() {
    if (rouletteState.countdownInterval) {
        clearInterval(rouletteState.countdownInterval);
        rouletteState.countdownInterval = null;
    }
    
    if (rouletteState.refreshInterval) {
        clearInterval(rouletteState.refreshInterval);
        rouletteState.refreshInterval = null;
    }
}

// Автообновление каждые 0.5 секунд
function startRouletteAutoRefresh() {
    if (rouletteState.refreshInterval) {
        clearInterval(rouletteState.refreshInterval);
    }
    
    rouletteState.refreshInterval = setInterval(() => {
        loadRouletteData();
    }, 500);
}


// Инициализация при загрузке удалена - теперь инициализация происходит
// при вызове initPages() и при открытии страницы рулетки через openRoulettePage()
