# Hookah Bar Order Bot

Telegram-бот для учёта заказов — табак, бар, прочее.

## Структура проекта

```
hookah_bot/
├── bot.py               — точка входа
├── config.py            — настройки через pydantic-settings
├── .env                 — токены и ID (не коммитить в git!)
├── requirements.txt
│
├── db/
│   ├── __init__.py      — публичный API пакета
│   ├── models.py        — SQLAlchemy модели + Pydantic схемы
│   ├── session.py       — async engine и фабрика сессий
│   └── queries.py       — все запросы к БД
│
└── tg/
    ├── __init__.py
    ├── keyboards.py     — все клавиатуры
    ├── staff_handlers.py — хендлеры кальянщиков
    ├── admin_handlers.py — хендлеры администраторов
    └── router.py        — регистрация хендлеров
```

## Быстрый старт

### 1. Установить зависимости
```bash
pip install -r requirements.txt
```

### 2. Создать базу данных
```sql
CREATE DATABASE hookah_bot;
```

### 3. Заполнить .env

```env
BOT_TOKEN=токен_от_BotFather
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hookah_bot
ADMIN_IDS=111111111,222222222
STAFF_IDS=333333333,444444444
```

> Узнать свой Telegram ID: написать [@userinfobot](https://t.me/userinfobot)

### 4. Запустить

```bash
python bot.py
```

Таблицы в БД создадутся автоматически при первом запуске.

---

## Роли

### 🧑‍🍳 Кальянщик (`STAFF_IDS`)
- **Табак** → выбирает марку → пишет название
- **Бар** → Напитки (Алко / Б-алко) / Снеки / Чай → пишет что закончилось
- **Прочее** → пишет всё что нужно заказать

### 👔 Администратор (`ADMIN_IDS`)
- **📋 Табак / Бар / Прочее** — смотрит список по категории
- **📋 Всё сразу** — полный список всех категорий
- **✅ Закрыть ...** — помечает позиции заказанными (очищает список)

---

## База данных

Таблица `order_items`:

| Колонка | Тип | Описание |
|---|---|---|
| id | SERIAL | Первичный ключ |
| category | TEXT | tobacco / bar / other |
| subcategory | TEXT | Марка, Алко, Снеки и т.д. |
| content | TEXT | Что нужно заказать |
| added_by | BIGINT | Telegram ID кальянщика |
| added_at | TIMESTAMPTZ | Время добавления |
| is_done | BOOLEAN | Заказано или нет |
