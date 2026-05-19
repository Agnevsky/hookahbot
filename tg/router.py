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
    STATE_MAIN,
    STATE_TOBACCO_BRAND,
    STATE_BAR_SUB,
    STATE_DRINKS_SUB,
    STATE_INPUT,
)
from tg.keyboards import (
    CB_ADD_TOBACCO, CB_ADD_BAR, CB_ADD_OTHER,
    CB_LIST_TOBACCO, CB_LIST_BAR, CB_LIST_OTHER,
    CB_CLEAR_TOBACCO, CB_CLEAR_BAR, CB_CLEAR_OTHER,
    CB_CANCEL,
)

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
    )
    app.add_handler(conv)