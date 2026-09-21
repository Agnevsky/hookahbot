from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from tg.handlers import (
    cmd_start,
    cb_main_menu,
    cb_tobacco_brand,
    cb_bar_sub,
    cb_drinks_sub,
    text_input_handler,
    cb_cancel,
    cb_stale,
    STATE_MAIN,
    STATE_TOBACCO_BRAND,
    STATE_BAR_SUB,
    STATE_DRINKS_SUB,
    STATE_INPUT,
)
from tg.keyboards import CB_CANCEL

_TEXT = filters.TEXT & ~filters.COMMAND

# Паттерны для каждого состояния
_MAIN_CB    = "^(add:|list:|clear:)"
_BRAND_CB   = "^(brand:|back:main)"
_BAR_CB     = "^(bar:|back:main)"
_DRINKS_CB  = "^(drinks:|back:bar)"


def register_handlers(app: Application) -> None:
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            STATE_MAIN: [
                CallbackQueryHandler(cb_main_menu, pattern=_MAIN_CB),
            ],
            STATE_TOBACCO_BRAND: [
                CallbackQueryHandler(cb_tobacco_brand, pattern=_BRAND_CB),
            ],
            STATE_BAR_SUB: [
                CallbackQueryHandler(cb_bar_sub, pattern=_BAR_CB),
            ],
            STATE_DRINKS_SUB: [
                CallbackQueryHandler(cb_drinks_sub, pattern=_DRINKS_CB),
            ],
            STATE_INPUT: [
                MessageHandler(_TEXT, text_input_handler),
                CallbackQueryHandler(cb_cancel, pattern=f"^{CB_CANCEL}$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(cb_cancel, pattern=f"^{CB_CANCEL}$"),
        ],
        per_user=True,
        per_chat=True,
        name="order_conversation",
        persistent=True,
    )
    app.add_handler(conv)

    # Нажатие на кнопку старого сообщения, для которого состояние уже потеряно:
    # без этого хендлера у пользователя просто бесконечно крутится спиннер.
    app.add_handler(CallbackQueryHandler(cb_stale))
