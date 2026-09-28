from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Кому слать оповещения о заполненности табака. Пусто — всем зарегистрированным.
    # Остальные списки всегда уходят всем зарегистрированным.
    TOBACCO_ALERT_IDS: list[int] = [1217267542, 496484865]

    # Кто видит кнопку ручной рассылки оповещений
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