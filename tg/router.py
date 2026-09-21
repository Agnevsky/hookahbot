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
    cb_list_pick,
    cb_clear_pick,
    text_input_handler,
    cb_cancel,
    cb_stale,
    STATE_MAIN,
    STATE_TOBACCO_BRAND,
    STATE_BAR_SUB,
    STATE_DRINKS_SUB,
    STATE_INPUT,
    STATE_LIST_PICK,
    STATE_CLEAR_PICK,
)
from tg.keyboards import CB_CANCEL

_TEXT = filters.TEXT & ~filters.COMMAND

# Паттерны для каждого состояния
_MAIN_CB    = "^(add:|menu:)"
_LIST_CB    = "^(list:|back:main)"
_CLEAR_CB   = "^(clear:|back:main)"
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
            STATE_LIST_PICK: [
                CallbackQueryHandler(cb_list_pick, pattern=_LIST_CB),
            ],
            STATE_CLEAR_PICK: [
                CallbackQueryHandler(cb_clear_pick, pattern=_CLEAR_CB),
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
