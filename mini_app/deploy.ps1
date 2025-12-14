# Скрипт для деплоя на Netlify
# Запустите: .\deploy.ps1

Write-Host "🚀 Деплой на Netlify..." -ForegroundColor Green

# Проверяем наличие Netlify CLI
$netlifyInstalled = Get-Command netlify -ErrorAction SilentlyContinue

if (-not $netlifyInstalled) {
    Write-Host "❌ Netlify CLI не установлен!" -ForegroundColor Red
    Write-Host "Установите: npm install -g netlify-cli" -ForegroundColor Yellow
    exit 1
}

# Переходим в папку mini_app
Set-Location $PSScriptRoot

Write-Host "📦 Деплой в продакшен..." -ForegroundColor Cyan
netlify deploy --prod

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Деплой успешно завершен!" -ForegroundColor Green
} else {
    Write-Host "❌ Ошибка при деплое!" -ForegroundColor Red
    exit 1
}
