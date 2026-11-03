"""
Проверка подписи Telegram Mini App (initData).

Telegram подписывает данные пользователя ключом, производным от токена бота,
поэтому подделать их, не зная токена, нельзя:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(Exception):
    pass


@dataclass(frozen=True)
class TgUser:
    id:         int
    first_name: str
    last_name:  str | None = None
    username:   str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)


def _secret(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign(fields: dict[str, str], bot_token: str) -> str:
    """Подписать поля так же, как это делает Telegram (нужно для тестов)."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    return hmac.new(_secret(bot_token), check.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str, bot_token: str, max_age: int) -> TgUser:
    """Проверить initData и вернуть пользователя. Бросает InitDataError."""
    try:
        fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as e:
        raise InitDataError("initData не разбирается") from e

    received = fields.pop("hash", None)
    if not received or not hmac.compare_digest(sign(fields, bot_token), received):
        raise InitDataError("неверная подпись")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as e:
        raise InitDataError("неверный auth_date") from e
    if time.time() - auth_date > max_age:
        raise InitDataError("сессия устарела — откройте приложение заново")

    try:
        user = json.loads(fields["user"])
        return TgUser(
            id=int(user["id"]),
            first_name=str(user.get("first_name") or ""),
            last_name=user.get("last_name"),
            username=user.get("username"),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise InitDataError("нет данных пользователя") from e
