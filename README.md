# Hookah Bar Order Bot

Telegram-бот для учёта заказов кальянной — табак, бар, прочее.

## Структура проекта

```
hookahbot/
├── bot.py               — точка входа, persistence и обработчик ошибок
├── config.py            — настройки через pydantic-settings
├── .env                 — токены и пароли (в git не коммитится!)
├── .env.example         — шаблон .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── db/
│   ├── models.py        — SQLAlchemy модели + Pydantic схемы
│   ├── session.py       — async engine и фабрика сессий
│   └── queries.py       — все запросы к БД
│
└── tg/
    ├── keyboards.py     — все клавиатуры и callback_data
    ├── handlers.py      — хендлеры диалога
    ├── formatters.py    — форматирование списков (HTML)
    └── router.py        — регистрация хендлеров
```

## Запуск на сервере (Docker)

На сервере нужен только Docker с плагином compose. Отдельно ставить
PostgreSQL и создавать базу вручную **не нужно**: база поднимается
контейнером и создаётся из `POSTGRES_DB`, а таблицы бот создаёт сам
при первом старте.

```bash
git clone <репозиторий> hookahbot
cd hookahbot

cp .env.example .env
nano .env          # подставить реальный BOT_TOKEN и пароль БД

docker compose up -d --build
docker compose logs -f bot
```

Обновление после пуша новых коммитов:

```bash
git pull
docker compose up -d --build
```

### Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Создание БД в контейнере postgres |
| `DATABASE_URL` | Строка подключения бота. Хост — `postgres` (имя сервиса), **не** `localhost` |
| `PERSISTENCE_PATH` | Необязательно. Файл состояния диалогов, по умолчанию `data/bot_state.pickle` |

Пример:
```env
DATABASE_URL=postgresql+asyncpg://hookah:change_me@postgres:5432/hookah_bot
```

### Данные

Два именованных тома переживают пересборку контейнеров:

- `postgres_data` — сама база;
- `bot_data` — состояние диалогов (`/app/data`), чтобы кнопки продолжали
  работать после перезапуска бота.

## Локальный запуск без Docker

```bash
pip install -r requirements.txt
cp .env.example .env    # DATABASE_URL с хостом localhost
python bot.py
```

---

## Как пользоваться

`/start` — регистрация и главное меню. Меню — сетка 3×3: колонки это
категории (Табак / Бар / Прочее), ряды — действия.

| | Табак | Бар | Прочее |
|---|---|---|---|
| ➕ | выбрать марку → написать название | Напитки (Алко / Б-алко), Снеки, Чай → написать что закончилось | написать что нужно |
| 📋 | показать список категории | | |
| 🗑 | очистить список категории | | |

При очистке списка всем остальным зарегистрированным пользователям
приходит оповещение, что заказ сделан.

> Ролей и ограничений доступа сейчас нет — очистить список может любой,
> кто знает бота.

---

## База данных

Таблица `registered_users`:

| Колонка | Тип | Описание |
|---|---|---|
| id | SERIAL | Первичный ключ |
| telegram_id | BIGINT UNIQUE | Telegram ID |
| username | TEXT | @username, если есть |
| full_name | TEXT | Имя пользователя |
| registered_at | TIMESTAMPTZ | Время регистрации |

Таблица `order_items`:

| Колонка | Тип | Описание |
|---|---|---|
| id | SERIAL | Первичный ключ |
| category | TEXT | tobacco / bar / other |
| subcategory | TEXT | Марка, Алко, Снеки и т.д. |
| content | TEXT | Что нужно заказать |
| added_by | BIGINT | Telegram ID добавившего |
| added_at | TIMESTAMPTZ | Время добавления |
| is_done | BOOLEAN | Зарезервировано; очистка сейчас удаляет строки физически |
