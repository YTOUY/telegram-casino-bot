-- Удаление всех стикеров со слотами из базы данных
DELETE FROM stickers WHERE name LIKE '%slots%' OR name LIKE '%slot%';

-- Проверка результата
SELECT 'Удалено стикеров со слотами' as result;







