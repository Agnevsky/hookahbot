import asyncio
import contextlib
import logging
from pathlib import Path

import uvicorn
from telegram import MenuButtonDefault, MenuButtonWebApp, Update, WebAppInfo
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes, PicklePersistence

from config import settings
from db.queries import seed_brands, split_multiline_items
from db.session import init_db, close_db
from tg.router import register_handlers
from webapp.api import create_web_app

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# Веб-сервер и его задача — живут вне bot_data (тот сохраняется в pickle)
_web: dict[str, object] = {}


class _WebServer(uvicorn.Server):
    """uvicorn без своих обработчиков сигналов — остановкой управляет бот."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield

    def install_signal_handlers(self) -> None:   # старые версии uvicorn
        pass


async def _start_web(app: Application) -> None:
    config = uvicorn.Config(
        create_web_app(app),
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
        log_level="warning",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = _WebServer(config)
    _web["server"] = server
    _web["task"]   = asyncio.create_task(server.serve())
    log.info("Веб-приложение слушает %s:%d", settings.WEBAPP_HOST, settings.WEBAPP_PORT)


async def _setup_menu_button(app: Application) -> None:
    """Кнопка слева от поля ввода: открывает приложение одним нажатием."""
    try:
        if settings.WEBAPP_URL:
            await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text="Заказ", web_app=WebAppInfo(url=settings.WEBAPP_URL),
            ))
        else:
            await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())
    except TelegramError:
        log.warning("Не удалось настроить кнопку меню", exc_info=True)


async def on_startup(app: Application) -> None:
    await init_db()
    if await seed_brands(settings.TOBACCO_BRANDS):
        log.info("Марки табака заполнены значениями по умолчанию")
    if n := await split_multiline_items():
        log.info("Многострочные записи разбиты на позиции: %d", n)
    log.info("БД инициализирована")
    log.info("Пороги оповещений: %s%%", settings.FILL_THRESHOLDS)
    log.info(
        "Ёмкость: табак %d, напитки %d, прочее %d",
        settings.CAPACITY_TOBACCO, settings.CAPACITY_BAR_DRINKS, settings.CAPACITY_OTHER,
    )
    for r in settings.RESPONSIBLE:
        log.info("Ответственный: %s (%s) — %s", r.name, r.telegram_id, ", ".join(r.categories))
    log.info("Администраторы: %s", settings.ADMIN_IDS or "нет")
    if not settings.RESPONSIBLE:
        log.warning("RESPONSIBLE не задан — оповещения о заполненности уйдут всем")

    await _start_web(app)
    await _setup_menu_button(app)


async def on_shutdown(app: Application) -> None:
    server, task = _web.pop("server", None), _web.pop("task", None)
    if server is not None and task is not None:
        server.should_exit = True
        await task
        log.info("Веб-приложение остановлено")
    await close_db()
    log.info("Соединение с БД закрыто")


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловит любое исключение в хендлерах, чтобы пользователь не остался без ответа."""
    log.error("Ошибка при обработке апдейта", exc_info=ctx.error)

    if not isinstance(update, Update):
        return
    chat = update.effective_chat
    if chat is None:
        return
    try:
        await ctx.bot.send_message(
            chat.id,
            "⚠️ Что-то пошло не так. Попробуйте ещё раз или нажмите /start",
        )
    except Exception:
        log.warning("Не удалось сообщить пользователю об ошибке", exc_info=True)


def main() -> None:
    state_file = Path(settings.PERSISTENCE_PATH)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .persistence(PicklePersistence(filepath=state_file))
        .build()
    )
    app.post_init     = on_startup
    app.post_shutdown = on_shutdown
    app.add_error_handler(on_error)
    register_handlers(app)
    log.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
