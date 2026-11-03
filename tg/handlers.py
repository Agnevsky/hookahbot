"""
Бот — только вход в веб-приложение и канал оповещений.

Всё управление списками живёт в приложении: здесь /start регистрирует
пользователя (чтобы ему приходили оповещения) и показывает кнопку
«Открыть приложение». На любое другое сообщение — то же приглашение.
"""
import html
import logging

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config import settings
from db.queries import get_counts, register_user
from tg.formatters import plural_positions
from tg.keyboards import open_app_kb

log = logging.getLogger(__name__)


async def _welcome_text(first_name: str | None, is_new: bool) -> str:
    total = sum((await get_counts()).values())
    name = html.escape(first_name or "")
    lines = [
        f"👋 Привет, {name}!" if name else "👋 Привет!",
        "",
        "Здесь собираем заказ для кальянной: 🌿 табак, 🍹 бар и 📦 всё остальное.",
        "",
    ]
    if settings.WEBAPP_URL:
        lines.append("Список, добавление и правка — в приложении. Откройте его кнопкой ниже "
                     "или «Заказ» рядом с полем ввода.")
    else:
        lines.append("⚠️ Приложение пока не настроено — обратитесь к администратору.")
    lines += ["", f"Сейчас в заказе: <b>{plural_positions(total)}</b>." if total else "Сейчас заказ пуст."]
    if is_new:
        lines += ["", "🔔 Вы подписаны на оповещения о заполненности и очистке списков."]
    return "\n".join(lines)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    is_new = await register_user(
        telegram_id=user.id,
        username=user.username,
        full_name=user.full_name,
    )
    await update.effective_message.reply_text(
        await _welcome_text(user.first_name, is_new),
        parse_mode="HTML",
        reply_markup=open_app_kb(),
    )


async def any_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Любой текст — подсказать, где теперь всё делается."""
    user = update.effective_user
    await register_user(user.id, user.username, user.full_name)
    await update.effective_message.reply_text(
        "Всё управление заказом — в приложении 👇",
        reply_markup=open_app_kb(),
    )


async def cb_stale(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка из старого меню: убираем её и отправляем в приложение."""
    q = update.callback_query
    await q.answer("Меню переехало в приложение")
    try:
        await q.edit_message_reply_markup(reply_markup=open_app_kb())
    except BadRequest:
        pass   # сообщение старше 48 часов или уже без кнопок
