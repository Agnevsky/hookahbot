import html
import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from config import Responsible, settings
from db.fill import Announced, FillAlert, new_alerts, reset_announced, status
from db.models import BarSub, Category, OrderItemCreate
from db.queries import (
    add_item,
    counts_by_category,
    get_breakdown,
    get_counts,
    get_items_by_category,
    clear_category,
    get_all_user_ids,
    register_user,
)
from tg.formatters import format_category_list, format_fill_alert
from tg.keyboards import (
    main_menu, list_menu, clear_menu, BAR_MENU, DRINKS_MENU, CANCEL_KB,
    tobacco_brands_kb,
    CB_ADD_TOBACCO, CB_ADD_BAR, CB_ADD_OTHER,
    CB_LIST_TOBACCO, CB_LIST_BAR, CB_LIST_OTHER,
    CB_CLEAR_TOBACCO, CB_CLEAR_BAR, CB_CLEAR_OTHER,
    CB_MENU_LIST, CB_MENU_CLEAR, CB_SEND_PREFIX,
    CB_BAR_DRINKS, CB_BAR_SNACKS, CB_BAR_TEA,
    CB_DRINKS_ALCO, CB_DRINKS_SOFT,
    CB_BACK_MAIN, CB_BACK_BAR,
)

log = logging.getLogger(__name__)

# ── Состояния ────────────────────────────────────────────────────
(
    STATE_MAIN,
    STATE_TOBACCO_BRAND,
    STATE_BAR_SUB,
    STATE_DRINKS_SUB,
    STATE_INPUT,
    STATE_LIST_PICK,
    STATE_CLEAR_PICK,
) = range(7)

CTX_CAT    = "category"
CTX_SUBCAT = "subcategory"
CTX_PROMPT = "prompt_msg_id"   # сообщение «напишите ответным…», убираем после ввода

BD_ANNOUNCED = "fill_announced"  # bot_data: какие уровни заполненности уже объявлены


# ================================================================
#  УТИЛИТЫ
# ================================================================

def _is_admin(update: Update) -> bool:
    return update.effective_user.id in settings.ADMIN_IDS


def _announced(ctx: ContextTypes.DEFAULT_TYPE) -> Announced:
    return ctx.bot_data.setdefault(BD_ANNOUNCED, {})


async def _main_kb(update: Update) -> InlineKeyboardMarkup:
    return main_menu(await get_counts(), is_admin=_is_admin(update))


async def _list_kb() -> InlineKeyboardMarkup:
    return list_menu(await get_counts())


async def _clear_kb() -> InlineKeyboardMarkup:
    return clear_menu(await get_counts())


async def _answer(update: Update, text: str, **kwargs) -> None:
    """Ответить на callback и отредактировать сообщение с клавиатурой."""
    q = update.callback_query
    await q.answer()
    try:
        await q.edit_message_text(text, **kwargs)
    except BadRequest as e:
        # Текст и клавиатура не изменились — Telegram считает это ошибкой,
        # для пользователя же ничего не произошло.
        if "message is not modified" not in str(e).lower():
            raise


async def _delete_msg(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int | None) -> None:
    """Удалить сообщение, молча пережив «уже удалено» и «старше 48 часов»."""
    if not message_id:
        return
    try:
        await ctx.bot.delete_message(chat_id, message_id)
    except BadRequest:
        pass


async def _prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE, text: str, **kwargs) -> int:
    """Попросить написать позицию, запомнив сообщение — потом его уберём."""
    await _answer(update, text, reply_markup=CANCEL_KB, **kwargs)
    ctx.user_data[CTX_PROMPT] = update.callback_query.message.message_id
    return STATE_INPUT


async def _finish(update: Update, text: str, **kwargs) -> None:
    """
    Завершить действие: убрать служебное сообщение и прислать меню вниз.

    Меню всегда оказывается последним сообщением в чате, листать вверх
    за ним не надо.
    """
    q = update.callback_query
    await q.answer()
    chat = q.message.chat
    try:
        await q.message.delete()
    except BadRequest:
        pass
    await chat.send_message(text, reply_markup=await _main_kb(update), **kwargs)


async def _show_list(update: Update, category: Category) -> None:
    """
    Показать список отдельным сообщением, а меню прислать новым под ним.

    Список остаётся в чате нетронутым (по нему идут закупаться), а меню
    всегда оказывается последним сообщением — не надо листать вверх.
    """
    q = update.callback_query
    await q.answer()

    rows = await get_items_by_category(category)
    chat = q.message.chat

    try:
        await q.message.delete()
    except BadRequest:
        pass  # сообщение старше 48 часов удалить нельзя — не страшно

    await chat.send_message(format_category_list(category, rows), parse_mode="HTML")
    await chat.send_message("Выберите действие:", reply_markup=await _main_kb(update))


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
    await update.message.reply_text(greeting, reply_markup=await _main_kb(update))
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
        return await _prompt(update, ctx, "Что нужно заказать?\n\nНапишите ответным сообщением:")

    # ── Показать список / очистить: сперва спрашиваем категорию ───
    if data == CB_MENU_LIST:
        await _answer(update, "Какой список показать?", reply_markup=await _list_kb())
        return STATE_LIST_PICK

    if data == CB_MENU_CLEAR:
        await _answer(update, "Какой список очистить?", reply_markup=await _clear_kb())
        return STATE_CLEAR_PICK

    # ── «Отправить …» (только администратор) ──────────────────────
    if data.startswith(CB_SEND_PREFIX):
        person = _responsible_by_id(data.removeprefix(CB_SEND_PREFIX))
        # Кнопки видит только админ, но callback_data можно подделать —
        # проверяем ещё раз здесь
        if not _is_admin(update) or person is None:
            await update.callback_query.answer("Недоступно", show_alert=True)
            return STATE_MAIN
        report = await _send_to_responsible(ctx, person)
        await _finish(update, report, parse_mode="HTML")
        return STATE_MAIN

    return STATE_MAIN


# ================================================================
#  ВЫБОР КАТЕГОРИИ ДЛЯ ПРОСМОТРА / ОЧИСТКИ
# ================================================================

_LIST_MAP = {
    CB_LIST_TOBACCO: Category.TOBACCO,
    CB_LIST_BAR:     Category.BAR,
    CB_LIST_OTHER:   Category.OTHER,
}

_CLEAR_MAP = {
    CB_CLEAR_TOBACCO: Category.TOBACCO,
    CB_CLEAR_BAR:     Category.BAR,
    CB_CLEAR_OTHER:   Category.OTHER,
}


async def cb_list_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=await _main_kb(update))
        return STATE_MAIN

    if data in _LIST_MAP:
        await _show_list(update, _LIST_MAP[data])
        return STATE_MAIN

    await _answer(update, "Какой список показать?", reply_markup=await _list_kb())
    return STATE_LIST_PICK


async def cb_clear_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=await _main_kb(update))
        return STATE_MAIN

    if data in _CLEAR_MAP:
        cat = _CLEAR_MAP[data]
        await clear_category(cat)
        reset_announced(_announced(ctx), cat)
        await _finish(update, f"✅ Список «{cat.label()}» очищен.\n\nВыберите действие:")
        await _notify_all(
            ctx,
            sender_id=update.effective_user.id,
            message=f"🔔 Заказ <b>{html.escape(cat.label())}</b> сделан — список очищен.",
        )
        return STATE_MAIN

    await _answer(update, "Какой список очистить?", reply_markup=await _clear_kb())
    return STATE_CLEAR_PICK


# ================================================================
#  ТАБАК
# ================================================================

async def cb_tobacco_brand(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=await _main_kb(update))
        return STATE_MAIN

    if data.startswith("brand:"):
        brand = data.removeprefix("brand:")
        if brand in settings.TOBACCO_BRANDS:
            ctx.user_data[CTX_CAT]    = Category.TOBACCO
            ctx.user_data[CTX_SUBCAT] = brand
            return await _prompt(
                update, ctx,
                f"Марка: <b>{html.escape(brand)}</b>\n\nНапишите название табака ответным сообщением:",
                parse_mode="HTML",
            )

    await _answer(update, "Выберите марку из списка:", reply_markup=tobacco_brands_kb())
    return STATE_TOBACCO_BRAND


# ================================================================
#  БАР
# ================================================================

async def cb_bar_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_MAIN:
        await _answer(update, "Выберите действие:", reply_markup=await _main_kb(update))
        return STATE_MAIN

    if data == CB_BAR_DRINKS:
        await _answer(update, "Выберите тип напитков:", reply_markup=DRINKS_MENU)
        return STATE_DRINKS_SUB

    sub_map = {CB_BAR_SNACKS: BarSub.SNACKS.value, CB_BAR_TEA: BarSub.TEA.value}
    if data in sub_map:
        ctx.user_data[CTX_CAT]    = Category.BAR
        ctx.user_data[CTX_SUBCAT] = sub_map[data]
        return await _prompt(
            update, ctx,
            f"Что нужно заказать ({sub_map[data]})?\n\nНапишите ответным сообщением:",
        )

    await _answer(update, "Выберите раздел:", reply_markup=BAR_MENU)
    return STATE_BAR_SUB


async def cb_drinks_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == CB_BACK_BAR:
        await _answer(update, "Выберите раздел:", reply_markup=BAR_MENU)
        return STATE_BAR_SUB

    drinks_map = {CB_DRINKS_ALCO: BarSub.ALCO.value, CB_DRINKS_SOFT: BarSub.SOFT.value}
    if data in drinks_map:
        ctx.user_data[CTX_CAT]    = Category.BAR
        ctx.user_data[CTX_SUBCAT] = drinks_map[data]
        return await _prompt(
            update, ctx,
            f"Что закончилось ({drinks_map[data]})?\n\nНапишите ответным сообщением:",
        )

    await _answer(update, "Выберите тип:", reply_markup=DRINKS_MENU)
    return STATE_DRINKS_SUB


# ================================================================
#  ВВОД ТЕКСТА (обычное сообщение)
# ================================================================

async def text_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await _delete_msg(ctx, update.effective_chat.id, ctx.user_data.pop(CTX_PROMPT, None))

    category = ctx.user_data.get(CTX_CAT)
    if category is None:
        # Состояние потеряно (например, перезапуск без сохранённых данных)
        await update.message.reply_text(
            "Не понял, к какой категории это относится. Выберите действие:",
            reply_markup=await _main_kb(update),
        )
        return STATE_MAIN

    text   = update.message.text.strip()
    subcat = ctx.user_data.get(CTX_SUBCAT)

    sender = update.effective_user.id
    await add_item(OrderItemCreate(
        category=category,
        subcategory=subcat,
        content=text,
        added_by=sender,
    ))
    breakdown = await get_breakdown()
    alerts = new_alerts(breakdown, _announced(ctx))

    # Добавившему — предупреждение прямо в подтверждении, остальным — рассылкой
    label = f" [{html.escape(subcat)}]" if subcat else ""
    await update.message.reply_text(
        "\n\n".join([f"✅ Добавлено{label}! Что-то ещё?", *map(format_fill_alert, alerts)]),
        parse_mode="HTML",
        reply_markup=main_menu(counts_by_category(breakdown), is_admin=_is_admin(update)),
    )
    for alert in alerts:
        await _send_fill_alert(ctx, alert, sender_id=sender)
    return STATE_MAIN


# ── Отмена через инлайн кнопку ────────────────────────────────────
async def cb_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.pop(CTX_PROMPT, None)
    await _finish(update, "Отменено. Выберите действие:")
    return STATE_MAIN


# ── Кнопка из устаревшего сообщения ───────────────────────────────
async def cb_stale(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback, для которого состояние диалога уже не найдено."""
    q = update.callback_query
    await q.answer("Сессия устарела", show_alert=False)
    await q.message.reply_text(
        "Эта кнопка устарела. Нажмите /start, чтобы открыть меню заново.",
    )


# ================================================================
#  РАССЫЛКИ
# ================================================================

def _why(e: TelegramError) -> str:
    """Причина недоставки — по-человечески."""
    msg = e.message.lower()
    if "blocked" in msg:
        return "заблокировал бота"
    if "initiate" in msg or "chat not found" in msg:
        return "ещё не нажимал /start в боте"
    return e.message


async def _deliver(
    ctx: ContextTypes.DEFAULT_TYPE,
    text: str,
    recipients: list[int],
) -> tuple[int, list[str]]:
    """Разослать сообщение. Возвращает (доставлено, [«id — причина» для недоставленных])."""
    sent, failed = 0, []
    for uid in recipients:
        try:
            await ctx.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            sent += 1
        except TelegramError as e:
            log.warning("Не удалось отправить оповещение %s: %s", uid, e)
            failed.append(f"{uid} — {_why(e)}")
    return sent, failed


async def _send_fill_alert(
    ctx: ContextTypes.DEFAULT_TYPE,
    alert: FillAlert,
    sender_id: int,
) -> tuple[int, int, list[str]]:
    """
    Разослать оповещение о заполненности ответственным за категорию пула
    (если их нет — всем зарегистрированным).
    Возвращает (доставлено, всего адресатов, [недоставленные]).
    """
    recipients = _responsible_ids(alert.pool.category) or await get_all_user_ids()
    targets = [uid for uid in recipients if uid != sender_id]
    sent, failed = await _deliver(ctx, format_fill_alert(alert), targets)
    log.info(
        "Оповещение «%s» %d%%: доставлено %d из %d",
        alert.pool.key, alert.level, sent, len(targets),
    )
    return sent, len(targets), failed


def _responsible_ids(category: Category) -> list[int]:
    return [r.telegram_id for r in settings.RESPONSIBLE if category in r.categories]


def _responsible_by_id(raw: str) -> Responsible | None:
    return next((r for r in settings.RESPONSIBLE if str(r.telegram_id) == raw), None)


_TG_LIMIT = 4000   # у Telegram 4096, оставляем запас на эмодзи


def _chunks(text: str) -> list[str]:
    """Разбить длинное сообщение по строкам — теги в каждой строке закрыты."""
    chunks, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > _TG_LIMIT and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    chunks.append(current)
    return chunks


async def _send_to_responsible(ctx: ContextTypes.DEFAULT_TYPE, person: Responsible) -> str:
    """
    Отправить ответственному его списки с заполненностью — всегда,
    независимо от порогов. Возвращает отчёт для администратора.
    """
    breakdown  = await get_breakdown()
    categories = [c for c in Category if c in person.categories]

    sent_alerts: list[FillAlert] = []
    messages: list[str] = []
    for category in categories:
        pools = status(category, breakdown)
        sent_alerts += pools
        rows = await get_items_by_category(category)
        messages.append(
            "\n".join(map(format_fill_alert, pools))
            + "\n\n"
            + format_category_list(category, rows)
        )

    name = html.escape(person.name)
    try:
        for text in messages:
            for chunk in _chunks(text):
                await ctx.bot.send_message(person.telegram_id, chunk, parse_mode="HTML")
    except TelegramError as e:
        log.warning("Не удалось отправить %s (%s): %s", person.name, person.telegram_id, e)
        return f"⚠️ Не доставлено {name}: {html.escape(_why(e))}.\n\nВыберите действие:"

    # Отправленный вручную уровень автоматика повторять не будет
    announced = _announced(ctx)
    for alert in sent_alerts:
        announced[alert.pool.key] = max(announced.get(alert.pool.key, 0), alert.level)

    log.info("Списки отправлены %s (%s): %s", person.name, person.telegram_id,
             ", ".join(c.value for c in categories))
    titles = ", ".join(html.escape(c.label()) for c in categories)
    return f"📤 Отправлено {name}: {titles}.\n\nВыберите действие:"


async def _notify_all(
    ctx: ContextTypes.DEFAULT_TYPE,
    sender_id: int,
    message: str,
) -> None:
    """Всем зарегистрированным, кроме отправителя."""
    targets = [uid for uid in await get_all_user_ids() if uid != sender_id]
    await _deliver(ctx, message, targets)