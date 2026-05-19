import logging

from telegram.ext import Application

from config import settings
from db.session import init_db, close_db
from tg.router import register_handlers

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


async def on_startup(app: Application) -> None:
    await init_db()
    log.info("БД инициализирована")


async def on_shutdown(app: Application) -> None:
    await close_db()
    log.info("Соединение с БД закрыто")


def main() -> None:
    app = Application.builder().token(settings.BOT_TOKEN).build()
    app.post_init     = on_startup
    app.post_shutdown = on_shutdown
    register_handlers(app)
    log.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()