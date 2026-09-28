import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, PicklePersistence

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
    log.info("Пороги оповещений: %s%%", settings.FILL_THRESHOLDS)
    log.info(
        "Ёмкость: табак %d, напитки %d, прочее %d",
        settings.CAPACITY_TOBACCO, settings.CAPACITY_BAR_DRINKS, settings.CAPACITY_OTHER,
    )
    for r in settings.RESPONSIBLE:
        log.info("Ответственный: %s (%s) — %s", r.name, r.telegram_id, ", ".join(r.categories))
    log.info("Администраторы: %s", settings.ADMIN_IDS or "нет")


async def on_shutdown(app: Application) -> None:
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
