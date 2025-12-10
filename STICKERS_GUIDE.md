# Руководство по сохранению стикеров

## Команда /sticker

Используйте команду `/sticker` для сохранения стикеров в базу данных.

### Процесс сохранения:

1. Отправьте команду `/sticker` боту
2. Отправьте все стикеры, которые нужно сохранить (по одному)
3. После отправки всех стикеров отправьте сообщение с названиями в формате:

```
1 название1
2 название2
3 название3
```

Или с указанием типа:

```
1 название1 тип
2 название2 тип
```

### Названия стикеров для игр

#### Приветственный стикер:
```
1 welcome
```

#### Кубик (Dice):
```
1 dice_1
2 dice_2
3 dice_3
4 dice_4
5 dice_5
6 dice_6
```

#### Дартс (Dart):
```
1 darts_1
2 darts_2
3 darts_3
4 darts_center
5 darts_miss
6 darts_red
7 darts_white
```

#### Боулинг (Bowling):
```
1 bowling_0
2 bowling_1
3 bowling_2
4 bowling_3
5 bowling_4
6 bowling_5
7 bowling_6
8 bowling_strike
9 bowling_miss
```

#### Футбол (Football):
```
1 football_goal        # Гол (значения 3, 4, 5)
2 football_miss         # Промах (значения 1, 2)
3 football_center       # В центр/штанга (значение 3)
4 football_clean_goal   # Чистый гол (значение 5)
5 football_post         # Штанга (значение 3, альтернатива center)
```

#### Баскетбол (Basketball):
```
1 basketball_hit        # Попадание (значения 4, 5)
2 basketball_miss       # Мимо (значения 1, 2)
3 basketball_clean      # Чистый гол (значение 5)
4 basketball_stuck      # Застрял (значение 3)
5 basketball_rim        # Попадание в обод (значение 4)
```

### Полный список стикеров для сохранения:

#### Приветственный стикер:
```
1 welcome
```

#### Кубик (Dice) - 1 базовый + 6 результатов:
```
2 dice_base        # Базовый стикер для кнопки
3 dice_1
4 dice_2
5 dice_3
6 dice_4
7 dice_5
8 dice_6
```

#### Дартс (Dart) - 1 базовый + 6 результатов:
```
9 darts_base       # Базовый стикер для кнопки
10 darts_1
11 darts_2
12 darts_3
13 darts_4
14 darts_5
15 darts_6
```

#### Футбол (Football) - 1 базовый + 5 результатов:
```
16 football_base    # Базовый стикер для кнопки
17 football_1
18 football_2
19 football_3
20 football_4
21 football_5
```

#### Баскетбол (Basketball) - 1 базовый + 5 результатов:
```
22 basketball_base  # Базовый стикер для кнопки
23 basketball_1
24 basketball_2
25 basketball_3
26 basketball_4
27 basketball_5
```

#### Слоты (Slots) - 1 базовый:
```
28 slots_base       # Базовый стикер для кнопки
```

#### Боулинг (Bowling) - 1 базовый:
```
29 bowling_base     # Базовый стикер для кнопки
(Также уже сохранены: bowling_0, bowling_1, bowling_2, bowling_3, bowling_4, bowling_5, bowling_6, bowling_strike, bowling_miss)
```

#### Результаты игры - 2 стикера:
```
30 win              # Стикер для победы
31 lose             # Стикер для поражения
```

### Пример использования:

1. Отправьте `/sticker`
2. Отправьте все стикеры по порядку (приветственный, кубик, дартс, футбол, баскетбол)
3. Отправьте сообщение с названиями:
```
1 welcome
2 dice_1
3 dice_2
4 dice_3
5 dice_4
6 dice_5
7 dice_6
2 dice_base
3 dice_1
4 dice_2
5 dice_3
6 dice_4
7 dice_5
8 dice_6
9 darts_base
10 darts_1
11 darts_2
12 darts_3
13 darts_4
14 darts_5
15 darts_6
16 football_base
17 football_1
18 football_2
19 football_3
20 football_4
21 football_5
22 basketball_base
23 basketball_1
24 basketball_2
25 basketball_3
26 basketball_4
27 basketball_5
28 slots_base
29 bowling_base
30 win
31 lose
```

### Примечания:

- Названия должны быть уникальными
- Если стикер с таким названием уже существует, он будет обновлен
- Можно указать тип стикера (например, `game`, `welcome`, `result`)
- Для отмены отправьте `/cancel`

