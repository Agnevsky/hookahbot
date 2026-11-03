"""
Рассылки и оповещения — общие для бота и веб-приложения.

Функции принимают объект бота и bot_data приложения, поэтому их можно
звать и из хендлеров (ctx.bot, ctx.bot_data), и из HTTP-API
(application.bot, application.bot_data).
"""
import html
import logging
from dataclasses import dataclass, field
from typing import Any

from telegram import Bot
from telegram.error import TelegramError

from config import Responsible, settings
from db.fill import Announced, FillAlert, new_alerts, reset_announced, status
from db.models import Breakdown, Category
from db.queries import get_all_user_ids, get_breakdown, get_items_by_category
from tg.formatters import format_category_list, format_fill_alert

log = logging.getLogger(__name__)

BD_ANNOUNCED = "fill_announced"  # bot_data: какие уровни заполненности уже объявлены

_TG_LIMIT = 4000   # у Telegram 4096, оставляем запас на эмодзи


def announced(bot_data: dict[str, Any]) -> Announced:
    return bot_data.setdefault(BD_ANNOUNCED, {})


def why(e: TelegramError) -> str:
    """Причина недоставки — по-человечески."""
    msg = e.message.lower()
    if "blocked" in msg:
        return "заблокировал бота"
    if "initiate" in msg or "chat not found" in msg:
        return "ещё не нажимал /start в боте"
    return e.message


def responsible_ids(category: Category) -> list[int]:
    return [r.telegram_id for r in settings.RESPONSIBLE if category in r.categories]


def responsible_by_id(raw: str | int) -> Responsible | None:
    return next((r for r in settings.RESPONSIBLE if str(r.telegram_id) == str(raw)), None)


def chunks(text: str) -> list[str]:
    """Разбить длинное сообщение по строкам — теги в каждой строке закрыты."""
    parts, current = [], ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > _TG_LIMIT and current:
            parts.append(current)
            current = line
        else:
            current = candidate
    parts.append(current)
    return parts


async def deliver(bot: Bot, text: str, recipients: list[int]) -> tuple[int, list[str]]:
    """Разослать сообщение. Возвращает (доставлено, [«id — причина» для недоставленных])."""
    sent, failed = 0, []
    for uid in recipients:
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            sent += 1
        except TelegramError as e:
            log.warning("Не удалось отправить оповещение %s: %s", uid, e)
            failed.append(f"{uid} — {why(e)}")
    return sent, failed


async def send_fill_alert(bot: Bot, alert: FillAlert, sender_id: int) -> None:
    """
    Разослать оповещение о заполненности ответственным за категорию пула
    (если их нет — всем зарегистрированным), кроме отправителя.
    """
    recipients = responsible_ids(alert.pool.category) or await get_all_user_ids()
    targets = [uid for uid in recipients if uid != sender_id]
    sent, _ = await deliver(bot, format_fill_alert(alert), targets)
    log.info(
        "Оповещение «%s» %d%%: доставлено %d из %d",
        alert.pool.key, alert.level, sent, len(targets),
    )


async def after_items_changed(
    bot: Bot,
    bot_data: dict[str, Any],
    sender_id: int,
) -> tuple[Breakdown, list[FillAlert]]:
    """
    Пересчитать заполненность после добавления/удаления и разослать
    оповещения о новых порогах. Возвращает (разбивку, новые оповещения) —
    добавившему их показывают прямо в ответе.
    """
    breakdown = await get_breakdown()
    alerts = new_alerts(breakdown, announced(bot_data))
    for alert in alerts:
        await send_fill_alert(bot, alert, sender_id=sender_id)
    return breakdown, alerts


async def notify_all(bot: Bot, sender_id: int, message: str) -> None:
    """Всем зарегистрированным, кроме отправителя."""
    targets = [uid for uid in await get_all_user_ids() if uid != sender_id]
    await deliver(bot, message, targets)


async def after_clear(bot: Bot, bot_data: dict[str, Any], category: Category, sender_id: int) -> None:
    """Список очищен: пороги снова активны, всем — оповещение."""
    reset_announced(announced(bot_data), category)
    await notify_all(
        bot,
        sender_id=sender_id,
        message=f"🔔 Заказ <b>{html.escape(category.label())}</b> сделан — список очищен.",
    )


@dataclass
class SendResult:
    ok:         bool
    categories: list[Category] = field(default_factory=list)
    error:      str | None = None


async def send_to_responsible(bot: Bot, bot_data: dict[str, Any], person: Responsible) -> SendResult:
    """
    Отправить ответственному его списки с заполненностью — всегда,
    независимо от порогов.
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

    try:
        for text in messages:
            for chunk in chunks(text):
                await bot.send_message(person.telegram_id, chunk, parse_mode="HTML")
    except TelegramError as e:
        log.warning("Не удалось отправить %s (%s): %s", person.name, person.telegram_id, e)
        return SendResult(ok=False, categories=categories, error=why(e))

    # Отправленный вручную уровень автоматика повторять не будет
    ann = announced(bot_data)
    for alert in sent_alerts:
        ann[alert.pool.key] = max(ann.get(alert.pool.key, 0), alert.level)

    log.info("Списки отправлены %s (%s): %s", person.name, person.telegram_id,
             ", ".join(c.value for c in categories))
    return SendResult(ok=True, categories=categories)
