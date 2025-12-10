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
    selectedGameMode: null
};

// API endpoints
// ВАЖНО: Замените на реальный URL вашего API сервера!
// API сервер должен быть доступен по публичному URL (например, через ngrok, VPS или другой хостинг)
// Пример: 'https://your-api-server.com:8080/api' или 'https://your-api-domain.com/api'

let API_BASE = '/api'; // По умолчанию относительный путь (для локальной разработки)

// Для продакшена на Netlify используем Netlify Function как прокси
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    // Мини-апп развернут на: https://arbuzcas.netlify.app
    // Используем Netlify Function для проксирования запросов (решает проблему HTTPS -> HTTP)
    API_BASE = '/.netlify/functions/api-proxy/api';
}

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
    try {
        console.log('🎬 Загрузка TGS стикера:', tgsUrl);
        
        // Загружаем TGS файл
        const response = await fetch(tgsUrl);
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
            const anim = lottie.loadAnimation({
                container: lottieContainer,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                animationData: lottieJson
            });
            
            element.style.opacity = '1';
            element.style.animation = 'stickerAnimation 2s ease-in-out';
            console.log('✅ TGS стикер успешно загружен и воспроизводится');
        } else {
            throw new Error('Lottie библиотека не загружена');
        }
    } catch (error) {
        console.error('❌ Ошибка загрузки TGS стикера:', error);
        // Показываем fallback только если это критическая ошибка
        if (error.message.includes('Lottie')) {
            showStickerFallback(element, true);
        } else {
            // Пробуем показать стикер как изображение (может быть это не TGS)
            console.warn('⚠️ Пробуем показать как обычное изображение');
            const img = document.createElement('img');
            img.src = tgsUrl;
            img.style.width = '100%';
            img.style.height = '100%';
            img.style.objectFit = 'contain';
            img.onload = () => {
                element.innerHTML = '';
                element.appendChild(img);
                element.style.opacity = '1';
            };
            img.onerror = () => {
                showStickerFallback(element, true);
            };
        }
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
        
        if (!isJson) {
            // Если ответ не JSON, читаем как текст для диагностики
            const text = await response.text();
            console.error('❌ Ответ не JSON! Content-Type:', contentType);
            console.error('❌ Первые 500 символов ответа:', text.substring(0, 500));
            console.error('❌ URL запроса:', requestUrl);
            
            // Если это HTML (обычно означает что Netlify Function не работает)
            if (text.trim().startsWith('<!DOCTYPE') || text.trim().startsWith('<!doctype') || text.includes('<html')) {
                const errorMsg = 'Netlify Function не работает. Получен HTML вместо JSON. ' +
                    'Проверьте: 1) Развертывание функции на Netlify, 2) Логи функций: https://app.netlify.com/projects/arbuzcas/logs/functions';
                console.error('❌', errorMsg);
                throw new Error(errorMsg);
            }
            
            throw new Error(`Ожидался JSON, получен ${contentType || 'неизвестный тип'}. Ответ: ${text.substring(0, 100)}`);
        }
        
        if (response.ok) {
            const data = await response.json();
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
            updateUI();
        } else {
            let errorData = {};
            try {
                const text = await response.text();
                errorData = text ? JSON.parse(text) : {};
            } catch (e) {
                console.error('Ошибка парсинга ответа:', e);
            }
            
            console.error('❌ Ошибка загрузки данных пользователя:', {
                status: response.status,
                statusText: response.statusText,
                error: errorData,
                url: requestUrl
            });
            
            // Показываем ошибку пользователю только если это не 401 (неавторизован)
            if (response.status !== 401) {
                showToast(`Ошибка загрузки баланса (${response.status})`);
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
        
        // Более детальное сообщение об ошибке
        let errorMessage = 'Ошибка подключения к серверу';
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            errorMessage = 'Не удалось подключиться к серверу. Проверьте настройки API.';
        } else if (error.name === 'AbortError') {
            errorMessage = 'Таймаут подключения к серверу';
        } else {
            errorMessage = `Ошибка: ${error.message}`;
        }
        
        showToast(errorMessage);
    }
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
    if (balanceTonEl && appState.balance > 0) {
        // Примерный курс 1 TON = 5 USD (можно добавить API для получения курса)
        const tonRate = 5.0;
        const balanceTon = appState.balance / tonRate;
        balanceTonEl.textContent = `${balanceTon.toFixed(4)} TON`;
    } else if (balanceTonEl) {
        balanceTonEl.textContent = '0.0000 TON';
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
        btn.addEventListener('click', () => {
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
        case 'top':
            await loadTopData();
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
    if (gameId === 'slots') {
        // Для слотов открываем страницу слотов
        showToast('Слоты в разработке');
        return;
    }
    
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
        'basketball': 'Баскетбол'
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
    initBetStep();
    
    // Инициализируем шаг 2: Выбор режима
    initModesStep(gameId);
    
    // Инициализируем шаг 3: Подтверждение
    initStartStep(gameId);
    
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
    const steps = ['bet', 'modes', 'start'];
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
function initBetStep() {
    const betInput = document.getElementById('game-bet-input');
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
    const betBtnMin = document.getElementById('bet-btn-min');
    const betBtnBase = document.getElementById('bet-btn-base');
    const betBtnMax = document.getElementById('bet-btn-max');
    
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
    
    // Кнопка "Далее" к выбору режима
    const btnNextToModes = document.getElementById('btn-next-to-modes');
    if (btnNextToModes) {
        btnNextToModes.addEventListener('click', () => {
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
            showGameStep('modes');
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
            
            // Запускаем игру
            await launchGame(gameId, bet, appState.selectedGameMode);
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

// Получить доступные режимы для игры (как в боте)
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
    
    return modesMap[gameId] || [{ value: 'even', name: 'Четное' }];
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
            
            if (errorMsg.includes('balance') || errorMsg.includes('средств')) {
                showToast(`Недостаточно средств! Нужно $${bet.toFixed(2)}`);
            } else {
                showToast(errorMsg);
            }
        }
    } catch (error) {
        console.error('Ошибка запуска игры:', error);
        showToast('Ошибка запуска игры');
    }
}

// Проверить результат игры
async function checkGameResult(gameId) {
    const maxAttempts = 10; // Максимум 5 секунд (10 попыток по 0.5 секунды)
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
                    displayGameResult(data);
                    // Обновляем баланс
                    await loadUserData();
                } else if (data.status === 'timeout' || data.status === 'error') {
                    clearInterval(checkInterval);
                    showToast(data.status === 'timeout' ? 'Таймаут ожидания результата' : 'Ошибка игры');
                }
            }
        } catch (error) {
            console.error('Ошибка проверки результата:', error);
        }
        
        if (attempts >= maxAttempts) {
            clearInterval(checkInterval);
            showToast('Таймаут ожидания результата');
        }
    }, 500); // Проверяем каждые 0.5 секунды для быстрого отклика
}

// Отобразить результат игры
function displayGameResult(result) {
    // Определяем название стикера на основе типа игры и результата
    let stickerName = getStickerNameForResult(result.game_type, result.result);
    
    // Показываем модальное окно с результатом
    showGameResultModal(result, stickerName);
    
    // Обновляем баланс
    appState.balance = result.new_balance;
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

// Показать модальное окно результата игры
async function showGameResultModal(result, stickerName) {
    // Определяем стикер победы/поражения
    const resultStickerName = result.win > 0 ? 'results_win' : 'results_lose';
    
    // Создаем временное модальное окно для результата
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'game-result-modal';
    
    modal.innerHTML = `
        <div class="modal-backdrop"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h2>Результат игры</h2>
            </div>
            <div class="modal-body" style="text-align: center;">
                <div class="result-sticker" data-sticker="${stickerName}"></div>
                <div class="win-lose-sticker" data-sticker="${resultStickerName}"></div>
                <div style="font-size: 24px; margin: 20px 0 10px; color: ${result.win > 0 ? 'var(--accent-green)' : 'var(--accent-red)'};">
                    ${result.win > 0 ? `Выигрыш: $${result.win.toFixed(2)}` : 'Проигрыш'}
                </div>
                <div class="result-display" style="font-size: 16px; color: var(--text-secondary); white-space: nowrap; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; padding: 10px 0;">
                    Результат: ${result.result}
                </div>
                <div style="font-size: 16px; color: var(--text-secondary); margin-top: 5px; margin-bottom: 20px;">
                    Новый баланс: $${result.new_balance.toFixed(2)}
                </div>
                <button class="btn-primary" id="btn-understand-result" style="width: 100%;">Понятно</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Загружаем стикеры через API
    await loadStickerForElement(modal.querySelector('.result-sticker'), stickerName);
    await loadStickerForElement(modal.querySelector('.win-lose-sticker'), resultStickerName);
    
    // Обработчик кнопки "Понятно"
    const understandBtn = document.getElementById('btn-understand-result');
    if (understandBtn) {
        understandBtn.addEventListener('click', () => {
            modal.remove();
        });
    }
    
    // Закрытие по клику на backdrop (опционально)
    modal.querySelector('.modal-backdrop').addEventListener('click', () => {
        modal.remove();
    });
}

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
        'slots_base': 'stickers/slots/base.tgs'
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
    
    // Сначала пробуем загрузить локальный файл из папки stickers
    const localPath = getLocalStickerPath(stickerName);
    if (localPath) {
        try {
            const response = await fetch(localPath, { method: 'HEAD' });
            if (response.ok) {
                console.log(`✅ Локальный стикер найден: ${localPath}`);
                // Проверяем формат файла (GIF или TGS)
                const isGif = localPath.toLowerCase().endsWith('.gif');
                if (isGif) {
                    // Для GIF файлов создаем img элемент
                    const img = document.createElement('img');
                    img.src = localPath;
                    img.alt = 'Sticker';
                    img.style.width = stickerSize;
                    img.style.height = stickerSize;
                    img.style.objectFit = 'contain';
                    img.onerror = () => {
                        element.innerHTML = `<div style="width: ${stickerSize}; height: ${stickerSize}; background: rgba(0,255,136,0.1); border-radius: 20px;"></div>`;
                    };
                    element.innerHTML = '';
                    element.appendChild(img);
                    return;
                } else {
                    // Для TGS файлов используем loadTgsSticker
                    if (window.lottie && window.pako) {
                        await loadTgsSticker(element, localPath);
                        return;
                    } else {
                        // Ждем загрузки библиотек
                        const checkLibs = setInterval(() => {
                            if (window.lottie && window.pako) {
                                clearInterval(checkLibs);
                                loadTgsSticker(element, localPath);
                            }
                        }, 100);
                        setTimeout(() => {
                            clearInterval(checkLibs);
                            if (!window.lottie || !window.pako) {
                                console.error('❌ Библиотеки не загрузились');
                            }
                        }, 5000);
                        return;
                    }
                }
            }
        } catch (e) {
            console.warn(`⚠️ Локальный стикер не найден: ${localPath}, пробуем через API`);
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
                const isTgs = urlLower.endsWith('.tgs') || 
                             urlLower.includes('.tgs') ||
                             data.is_tgs === true;
                
                console.log(`🔍 Формат стикера ${stickerName}: ${isTgs ? 'TGS' : 'Image'}`);
                
                if (isTgs) {
                    // Для TGS файлов используем loadTgsSticker
                    if (window.lottie && window.pako) {
                        await loadTgsSticker(element, stickerUrl);
                    } else {
                        // Ждем загрузки библиотек
                        console.log('⏳ Ожидание загрузки библиотек для TGS...');
                        const checkLibs = setInterval(() => {
                            if (window.lottie && window.pako) {
                                clearInterval(checkLibs);
                                loadTgsSticker(element, stickerUrl);
                            }
                        }, 100);
                        setTimeout(() => {
                            clearInterval(checkLibs);
                            if (!window.lottie || !window.pako) {
                                console.error('❌ Библиотеки не загрузились для TGS стикера');
                                // Fallback на изображение, если библиотеки не загрузились
                                const img = document.createElement('img');
                                img.src = stickerUrl;
                                img.alt = 'Sticker';
                                img.style.width = stickerSize;
                                img.style.height = stickerSize;
                                img.style.objectFit = 'contain';
                                element.innerHTML = '';
                                element.appendChild(img);
                            }
                        }, 5000);
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
}

// Инициализация страниц
function initPages() {
    // Кошелек - пополнение/вывод
    const depositBtn = document.getElementById('btn-deposit');
    const withdrawBtn = document.getElementById('btn-withdraw');
    
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
        tg.openTelegramLink('https://t.me/your_support_bot');
    });
    
    // Модальные окна
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            const modalId = btn.dataset.modal;
            hideModal(modalId);
        });
    });
    
    // Сохранение базовой ставки
    document.getElementById('save-base-bet').addEventListener('click', async () => {
        const value = parseFloat(document.getElementById('base-bet-input').value);
        if (value >= 0.1) {
            await saveBaseBet(value);
            hideModal('modal-base-bet');
        }
    });
}

// Показать методы пополнения
function showDepositMethods() {
    const depositMethods = document.getElementById('deposit-methods');
    const withdrawMethods = document.getElementById('withdraw-methods');
    
    // Скрываем методы вывода
    if (withdrawMethods) withdrawMethods.classList.add('hidden');
    
    // Показываем методы пополнения
    if (depositMethods) {
        depositMethods.classList.remove('hidden');
        
        // Если контейнер пустой или не содержит кнопок, создаем их
        if (!depositMethods.querySelector('.method-btn') || depositMethods.children.length === 0) {
            depositMethods.innerHTML = `
        <button class="method-btn" id="deposit-ton">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
            <span>TON (TON Connect)</span>
        </button>
        <button class="method-btn" id="deposit-cryptobot">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
                <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
            </svg>
            <span>CryptoBot</span>
        </button>
        <button class="method-btn" id="deposit-gifts">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 12 20 22 4 22 4 12"></polyline>
                <rect x="2" y="7" width="20" height="5"></rect>
                <line x1="12" y1="22" x2="12" y2="7"></line>
                <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
            </svg>
            <span>Подарки</span>
        </button>
    `;
            
            // Добавляем обработчики событий
            const depositTonBtn = document.getElementById('deposit-ton');
            const depositCryptobotBtn = document.getElementById('deposit-cryptobot');
            const depositGiftsBtn = document.getElementById('deposit-gifts');
            
            if (depositTonBtn) {
                depositTonBtn.addEventListener('click', () => {
                    initTONConnect();
                });
            }
            
            if (depositCryptobotBtn) {
                depositCryptobotBtn.addEventListener('click', () => {
                    showToast('CryptoBot в разработке');
                });
            }
            
            if (depositGiftsBtn) {
                depositGiftsBtn.addEventListener('click', async () => {
                    // Убеждаемся, что контейнер видим перед загрузкой подарков
                    const depositMethods = document.getElementById('deposit-methods');
                    if (depositMethods) {
                        depositMethods.classList.remove('hidden');
                    }
                    // Загружаем и показываем подарки
                    await showGifts(false);
                });
            }
        }
    }
}

// Показать методы вывода
function showWithdrawMethods() {
    const depositMethods = document.getElementById('deposit-methods');
    const withdrawMethods = document.getElementById('withdraw-methods');
    
    // Скрываем методы пополнения
    if (depositMethods) depositMethods.classList.add('hidden');
    
    // Показываем методы вывода
    if (withdrawMethods) {
        withdrawMethods.classList.remove('hidden');
        
        // Если контейнер пустой или не содержит кнопок, создаем их
        if (!withdrawMethods.querySelector('.method-btn') || withdrawMethods.children.length === 0) {
            withdrawMethods.innerHTML = `
        <button class="method-btn" id="withdraw-ton">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                <path d="M2 17l10 5 10-5"></path>
                <path d="M2 12l10 5 10-5"></path>
            </svg>
            <span>TON</span>
        </button>
        <button class="method-btn" id="withdraw-gifts">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 12 20 22 4 22 4 12"></polyline>
                <rect x="2" y="7" width="20" height="5"></rect>
                <line x1="12" y1="22" x2="12" y2="7"></line>
                <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
                <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
            </svg>
            <span>Подарки</span>
        </button>
    `;
            
            // Добавляем обработчики событий
            const withdrawTonBtn = document.getElementById('withdraw-ton');
            const withdrawGiftsBtn = document.getElementById('withdraw-gifts');
            
            if (withdrawTonBtn) {
                withdrawTonBtn.addEventListener('click', () => {
                    showToast('Вывод TON в разработке');
                });
            }
            
            if (withdrawGiftsBtn) {
                withdrawGiftsBtn.addEventListener('click', async () => {
                    await showGifts(true);
                });
            }
        }
    }
}

// Инициализация TON Connect
async function initTONConnect() {
    try {
        // Загружаем TON Connect SDK
        if (typeof TonConnectUI === 'undefined') {
            // Если SDK не загружен, загружаем его
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/@tonconnect/ui@latest/dist/tonconnect-ui.min.js';
            script.onload = () => {
                initTONConnectUI();
            };
            document.head.appendChild(script);
        } else {
            initTONConnectUI();
        }
    } catch (error) {
        console.error('Ошибка инициализации TON Connect:', error);
        showToast('Ошибка подключения к TON Connect');
    }
}

function initTONConnectUI() {
    try {
        const tonConnectUI = new TonConnectUI({
            manifestUrl: window.location.origin + '/tonconnect-manifest.json'
        });
        
        // Открываем кошелек для подключения
        tonConnectUI.openWallet();
        
        // Обработка подключения
        tonConnectUI.onStatusChange((wallet) => {
            if (wallet) {
                // Кошелек подключен, можно выполнить транзакцию
                showToast('TON кошелек подключен');
                // Здесь можно добавить логику для пополнения
            }
        });
    } catch (error) {
        console.error('Ошибка TON Connect UI:', error);
        showToast('Ошибка TON Connect');
    }
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
    'plush pepe': 'jolly-chimp',  // Пример маппинга, если файл называется по-другому
    'durovs cap': 'khabibs-papakha',  // Пример
    'precious peach': 'pretty-posy',
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
    'khabibs papakha': 'khabibs-papakha'
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
    
    listContainer.innerHTML = lotteries.map(lottery => `
        <div class="lottery-item" style="background: var(--bg-card); border: 2px solid var(--border-color); border-radius: 12px; padding: 15px; margin-bottom: 10px;">
            <h3 style="margin-bottom: 10px;">${lottery.title}</h3>
            <p style="color: var(--text-secondary); margin-bottom: 10px;">${lottery.description}</p>
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <span>Билетов: ${lottery.total_tickets}</span>
                <span>Цена: $${lottery.ticket_price.toFixed(2)}</span>
            </div>
            <button class="btn-primary" onclick="participateLottery(${lottery.id})">Участвовать</button>
        </div>
    `).join('');
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
            await loadUserData();
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
            
            const referralCountEl = document.getElementById('referral-count');
            const referralBalanceEl = document.getElementById('referral-balance');
            const referralLinkEl = document.getElementById('referral-link');
            
            if (referralCountEl) {
                referralCountEl.textContent = data.referral_count || 0;
            } else {
                console.warn('Элемент referral-count не найден');
            }
            
            if (referralBalanceEl) {
                referralBalanceEl.textContent = `$${(data.referral_balance || 0).toFixed(2)}`;
            } else {
                console.warn('Элемент referral-balance не найден');
            }
            
            if (referralLinkEl) {
                referralLinkEl.value = data.referral_link || '';
                console.log('Реферальная ссылка установлена:', data.referral_link);
                
                // Если ссылка пустая, показываем предупреждение
                if (!data.referral_link) {
                    console.warn('Реферальная ссылка пустая!');
                }
            } else {
                console.error('Элемент referral-link не найден!');
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            console.error('Ошибка загрузки профиля:', response.status, errorData);
        }
    } catch (error) {
        console.error('Ошибка загрузки профиля:', error);
    }
}

// Загрузить данные топа
async function loadTopData(category = 'players', period = 'day') {
    try {
        const response = await fetch(`${API_BASE}/top?category=${category}&period=${period}`, {
            headers: {
                'X-Telegram-Init-Data': tg.initData
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            displayTop(data);
        }
    } catch (error) {
        console.error('Ошибка загрузки топа:', error);
    }
}

// Отобразить топ
function displayTop(data) {
    const topList = document.getElementById('top-list');
    
    topList.innerHTML = data.top.map((item, index) => `
        <div class="top-item" onclick="showUserProfile(${item.user_id})">
            <div class="top-item-position">#${index + 1}</div>
            <div class="top-item-name">${item.username || `ID${item.user_id}`}</div>
            <div class="top-item-value">$${item.turnover.toFixed(2)}</div>
        </div>
    `).join('');
    
    // Инициализируем фильтры
    document.querySelectorAll('.btn-filter').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadTopData(btn.dataset.category, 'day');
        });
    });
    
    document.querySelectorAll('.btn-period').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.btn-period').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const category = document.querySelector('.btn-filter.active')?.dataset.category || 'players';
            loadTopData(category, btn.dataset.period);
        });
    });
}

// Показать профиль пользователя
function showUserProfile(userId) {
    showToast(`Профиль пользователя #${userId}`);
    // Здесь можно открыть модальное окно с профилем
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
            showToast('Базовая ставка сохранена');
        } else {
            const errorData = await response.json().catch(() => ({}));
            showToast(errorData.error || 'Ошибка сохранения ставки');
        }
    } catch (error) {
        console.error('Ошибка сохранения базовой ставки:', error);
        showToast('Ошибка сохранения');
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

