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
    RESPONSIBLE: list[Responsible] = [
        Responsible(name="Юре",  telegram_id=1217267542, categories=["tobacco"]),
        Responsible(name="Жене", telegram_id=496484865,  categories=["bar", "other"]),
    ]

    # Кто видит кнопки «📤 Отправить …»
    ADMIN_IDS: list[int] = [8251607484]

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