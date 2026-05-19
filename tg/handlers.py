import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import settings
from db.models import Category, OrderItemCreate
from db.queries import (
    add_item,
    get_items_by_category,
    clear_category,
    get_all_user_ids,
    register_user,
)
from tg.formatters import format_category_list
from tg.keyboards import (
    MAIN_MENU, BAR_MENU, DRINKS_MENU, CANCEL_KB,
    tobacco_brands_kb,
    CB_ADD_TOBACCO, CB_ADD_BAR, CB_ADD_OTHER,
    CB_LIST_TOBACCO, CB_LIST_BAR, CB_LIST_OTHER,
    CB_CLEAR_TOBACCO, CB_CLEAR_BAR, CB_CLEAR_OTHER,
    CB_BAR_DRINKS, CB_BAR_SNACKS, CB_BAR_TEA,
    CB_DRINKS_ALCO, CB_DRINKS_SOFT,
    CB_BACK_MAIN, CB_BACK_BAR, CB_CANCEL,
)

log = logging.getLogger(__name__)

# ── Состояния ────────────────────────────────────────────────────
(
    STATE_MAIN,
    STATE_TOBACCO_BRAND,
    STATE_BAR_SUB,
    STATE_DRINKS_SUB,
    STATE_INPUT,
) = range(5)

CTX_CAT    = "category"
CTX_SUBCAT = "subcategory"


# ================================================================
#  УТИЛИТЫ
# ================================================================

async def _answer(update: Update, text: str, **kwargs) -> None:
    """Ответить на callback и отредактировать сообщение с клавиатурой."""
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(text, **kwargs)


async def _answer_list(update: Update, text: str) -> None:
    """Показать список — отдельным сообщением чтобы не затирать меню."""
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(text, parse_mode="Markdown")


# ================================================================
#  /start
# ================================================================

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    is_new = await register_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
    greeting = (
        f"👋 Привет, {user.first_name}! Ты зарегистрирован.\n"
        "Теперь будешь получать оповещения об очистке списков."
        if is_new else "Выберите действие:"
    )
    await update.message.reply_text(greeting, reply_markup=MAIN_MENU)
    return STATE_MAIN


# ================================================================
#  ГЛАВНОЕ МЕНЮ — callback
# ================================================================

async def cb_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    # ── Добавить ─────────────────────────────────────────────────
    if data == CB_ADD_TOBACCO:
        await _answer(update, "Выберите марку табака:", reply_markup=tobacco_brands_kb())
        return STATE_TOBACCO_BRAND

    if data == CB_ADD_BAR:
        await _answer(update, "Выберите раздел:", reply_markup=BAR_MENU)
        return STATE_BAR_SUB

    if data == CB_ADD_OTHER:
        ctx.user_data[CTX_CAT]    = Category.OTHER
        ctx.user_data[CTX_SUBCAT] = None
        await _answer(update, "Что нужно заказать?\n\nНапишите ответным сообщением:", reply_markup=CANCEL_KB)
        return STATE_INPUT

    # ── Показать список ───────────────────────────────────────────
    list_map = {
        CB_LIST_TOBACCO: Category.TOBACCO,
        CB_LIST_BAR:     Category.BAR,
        CB_LIST_OTHER:   Category.OTHER,
    }
    if data in list_map:
        cat  = list_map[data]
        rows = await get_items_by_category(cat)
        await _answer_list(update, format_category_list(cat, rows))
        return STATE_MAIN

    # ── Очистить ──────────────────────────────────────────────────
    clear_map = {
        CB_CLEAR_TOBACCO: Category.TOBACCO,
        CB_CLEAR_BAR:     Category.BAR,
        CB_CLEAR_OTHER:   Category.OTHER,
    }
    if data in clear_map:
        cat = clear_map[data]
        await clear_category(cat)
        await _answer(update, f"✅ Список «{cat.label()}» очищен.", reply_markup=MAIN_MENU)
        await _notify_all(
            ctx,
            sender_id=update.effective_user.id,
            message=f"🔔 Заказ *{cat.label()}* сделан — список очищен.",
        )
        return STATE_MAIN

    return STATE_MAIN


# ================================================================
#  ТАБАК
# ================================================================

async def cb_tobacco_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=MAIN_MENU)
        return STATE_MAIN

    if data.startswith("brand:"):
        brand = data.removeprefix("brand:")
        if brand in settings.TOBACCO_BRANDS:
            ctx.user_data[CTX_CAT]    = Category.TOBACCO
            ctx.user_data[CTX_SUBCAT] = brand
            await _answer(
                update,
                f"Марка: *{brand}*\n\nНапишите название табака ответным сообщением:",
                parse_mode="Markdown",
                reply_markup=CANCEL_KB,
            )
            return STATE_INPUT

    await _answer(update, "Выберите марку из списка:", reply_markup=tobacco_brands_kb())
    return STATE_TOBACCO_BRAND


# ================================================================
#  БАР
# ================================================================

async def cb_bar_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=MAIN_MENU)
        return STATE_MAIN

    if data == CB_BAR_DRINKS:
        await _answer(update, "Выберите тип напитков:", reply_markup=DRINKS_MENU)
        return STATE_DRINKS_SUB

    sub_map = {CB_BAR_SNACKS: "Снеки", CB_BAR_TEA: "Чай"}
    if data in sub_map:
        ctx.user_data[CTX_CAT]    = Category.BAR
        ctx.user_data[CTX_SUBCAT] = sub_map[data]
        await _answer(
            update,
            f"Что нужно заказать ({sub_map[data]})?\n\nНапишите ответным сообщением:",
            reply_markup=CANCEL_KB,
        )
        return STATE_INPUT

    await _answer(update, "Выберите раздел:", reply_markup=BAR_MENU)
    return STATE_BAR_SUB


async def cb_drinks_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_BAR:
        await _answer(update, "Выберите раздел:", reply_markup=BAR_MENU)
        return STATE_BAR_SUB

    drinks_map = {CB_DRINKS_ALCO: "Алко", CB_DRINKS_SOFT: "Б/алко"}
    if data in drinks_map:
        ctx.user_data[CTX_CAT]    = Category.BAR
        ctx.user_data[CTX_SUBCAT] = drinks_map[data]
        await _answer(
            update,
            f"Что закончилось ({drinks_map[data]})?\n\nНапишите ответным сообщением:",
            reply_markup=CANCEL_KB,
        )
        return STATE_INPUT

    await _answer(update, "Выберите тип:", reply_markup=DRINKS_MENU)
    return STATE_DRINKS_SUB


# ================================================================
#  ВВОД ТЕКСТА (обычное сообщение)
# ================================================================

async def text_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    await add_item(OrderItemCreate(
        category=ctx.user_data[CTX_CAT],
        subcategory=ctx.user_data.get(CTX_SUBCAT),
        content=text,
        added_by=update.effective_user.id,
    ))

    subcat = ctx.user_data.get(CTX_SUBCAT)
    label  = f" [{subcat}]" if subcat else ""
    await update.message.reply_text(
        f"✅ Добавлено{label}! Что-то ещё?",
        reply_markup=MAIN_MENU,
    )
    return STATE_MAIN


# ── Отмена через инлайн кнопку ────────────────────────────────────
async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await _answer(update, "Отменено. Выберите действие:", reply_markup=MAIN_MENU)
    return STATE_MAIN


# ================================================================
#  ОПОВЕЩЕНИЕ ВСЕХ
# ================================================================

async def _notify_all(
    ctx: ContextTypes.DEFAULT_TYPE,
    sender_id: int,
    message: str,
) -> None:
    for uid in await get_all_user_ids():
        if uid == sender_id:
            continue
        try:
            await ctx.bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
        except Exception as e:
            log.warning("Не удалось отправить оповещение %s: %s", uid, e)