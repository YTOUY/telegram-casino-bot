// Netlify Function для проксирования API запросов
// Это решает проблему смешанного контента (HTTPS -> HTTP)

exports.handler = async (event, context) => {
    // Разрешаем CORS
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-Telegram-Init-Data',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    };

    // Обработка OPTIONS запросов
    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 200,
            headers,
            body: '',
        };
    }

    try {
        // Получаем путь из запроса
        // Убираем префикс функции и добавляем /api если нужно
        let path = event.path.replace('/.netlify/functions/api-proxy', '');
        
        // Если путь начинается с /api, используем его как есть
        // Если нет, добавляем /api
        if (!path.startsWith('/api')) {
            path = '/api' + (path || '');
        }
        
        // URL API сервера
        const apiUrl = `http://141.8.198.144:8081${path}`;
        
        // Параметры запроса
        const requestOptions = {
            method: event.httpMethod,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Копируем заголовки из запроса (проверяем разные варианты написания)
        const initDataHeader = event.headers['x-telegram-init-data'] || 
                              event.headers['X-Telegram-Init-Data'] ||
                              event.headers['X-Telegram-Init-Data'.toLowerCase()];
        
        if (initDataHeader) {
            requestOptions.headers['X-Telegram-Init-Data'] = initDataHeader;
        }

        // Добавляем тело запроса для POST/PUT/PATCH
        if (event.body && ['POST', 'PUT', 'PATCH'].includes(event.httpMethod)) {
            requestOptions.body = event.body;
        }

        // Добавляем query параметры
        const queryString = event.queryStringParameters 
            ? '?' + new URLSearchParams(event.queryStringParameters).toString()
            : '';
        
        const fullUrl = apiUrl + queryString;

        console.log('Proxying request:', {
            method: event.httpMethod,
            path: path,
            fullUrl: fullUrl,
            hasInitData: !!initDataHeader
        });

        // Выполняем запрос к API с таймаутом
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 секунд таймаут
        
        try {
            const response = await fetch(fullUrl, {
                ...requestOptions,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            const data = await response.text();
            
            // Определяем Content-Type из ответа
            const contentType = response.headers.get('content-type') || 'application/json';

            console.log('API response:', {
                status: response.status,
                contentType: contentType,
                dataLength: data.length,
                url: fullUrl
            });

            return {
                statusCode: response.status,
                headers: {
                    ...headers,
                    'Content-Type': contentType,
                },
                body: data,
            };
        } catch (fetchError) {
            clearTimeout(timeoutId);
            
            // Логируем детальную информацию об ошибке
            console.error('Fetch error:', {
                message: fetchError.message,
                name: fetchError.name,
                url: fullUrl,
                method: event.httpMethod
            });
            
            throw fetchError;
        }
    } catch (error) {
        console.error('Ошибка проксирования API:', error);
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({ 
                error: 'Ошибка подключения к API серверу',
                message: error.message,
                details: process.env.NETLIFY_DEV ? error.stack : undefined
            }),
        };
    }
};

