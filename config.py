from typing import Literal

from pydantic import BaseModel, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Responsible(BaseModel):
    """Ответственный за категории: получает их оповещения и списки."""
    name:        str   # в дательном падеже — для кнопки «Отправить Юре»
    telegram_id: int
    categories:  list[Literal["tobacco", "bar", "other"]]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    DATABASE_URL: str

    # Файл с состоянием диалогов — переживает перезапуск контейнера
    PERSISTENCE_PATH: str = "data/bot_state.pickle"

    # Заполненность: сколько позиций считается «100 %»
    CAPACITY_TOBACCO:    PositiveInt = 50
    CAPACITY_BAR_DRINKS: PositiveInt = 15   # алко + б/алко вместе
    CAPACITY_OTHER:      PositiveInt = 15

    # На каких процентах рассылать оповещение (каждый порог — один раз до очистки)
    FILL_THRESHOLDS: list[PositiveInt] = [50, 80, 100]

    # Кто за что отвечает. Им уходят оповещения о заполненности их категорий,
    # а у администратора для каждого есть кнопка «📤 Отправить …» — шлёт
    # список и заполненность. Категорию без ответственного оповещения
    # получают все зарегистрированные.
    # Задаётся в .env JSON-списком — Telegram ID не храним в коде.
    RESPONSIBLE: list[Responsible] = []

    # Кто видит кнопки «📤 Отправить …» и управляет марками табака (.env)
    ADMIN_IDS: list[int] = []

    # ─── Веб-приложение (Telegram Mini App) ─────────────────────
    # Публичный HTTPS-адрес приложения, например https://hookah.example.com/
    # Пусто — кнопка «Открыть приложение» в боте не показывается.
    WEBAPP_URL: str = ""
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: PositiveInt = 8080
    # Сколько секунд действительна подпись initData от Telegram
    WEBAPP_AUTH_TTL: PositiveInt = 24 * 60 * 60

    # Марки табака по умолчанию — ими заполняется пустая таблица марок
    # при первом запуске. Дальше марки редактируются в веб-приложении.
    TOBACCO_BRANDS: list[str] = [
        "Dark Side",
        "Must Have",
        "Black Burn",
        "Trofimoff's",
        "Bonche",
        "Crown",
        "Chabacco",
        "Tangiers",
        "Северный",
        "Deus",
        "Bliss",
        "ДГМ",
        "База",
        "Starline",
        "Take",
        "Хулиган",
        "Sebero",
        "Sapphire",
    ]


settings = Settings()