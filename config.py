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
    FILL_THRESHOLDS: list[PositiveInt] = [80, 100]

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
    ]


settings = Settings()