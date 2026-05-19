from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    DATABASE_URL: str

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