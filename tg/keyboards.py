from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from config import settings


def open_app_kb(text: str = "📱 Открыть приложение") -> InlineKeyboardMarkup | None:
    """Единственная кнопка бота — открыть веб-приложение."""
    if not settings.WEBAPP_URL:
        return None
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(text, web_app=WebAppInfo(url=settings.WEBAPP_URL)),
    ]])
