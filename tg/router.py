from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from tg.handlers import any_message, cb_stale, cmd_start


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, any_message))
    # Кнопки старых сообщений с меню — до перехода на приложение
    app.add_handler(CallbackQueryHandler(cb_stale))
