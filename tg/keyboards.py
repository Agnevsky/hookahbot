from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from db.models import Category


def _kb(buttons: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=cb) for text, cb in row]
        for row in buttons
    ])


# ================================================================
#  CALLBACK DATA
# ================================================================
CB_ADD_TOBACCO   = "add:tobacco"
CB_ADD_BAR       = "add:bar"
CB_ADD_OTHER     = "add:other"

CB_LIST_TOBACCO  = "list:tobacco"
CB_LIST_BAR      = "list:bar"
CB_LIST_OTHER    = "list:other"

CB_CLEAR_TOBACCO = "clear:tobacco"
CB_CLEAR_BAR     = "clear:bar"
CB_CLEAR_OTHER   = "clear:other"

CB_BAR_DRINKS    = "bar:drinks"
CB_BAR_SNACKS    = "bar:snacks"
CB_BAR_TEA       = "bar:tea"

CB_DRINKS_ALCO   = "drinks:alco"
CB_DRINKS_SOFT   = "drinks:soft"

CB_MENU_LIST     = "menu:list"
CB_MENU_CLEAR    = "menu:clear"

CB_BACK_MAIN     = "back:main"
CB_BACK_BAR      = "back:bar"
CB_CANCEL        = "cancel"


# ================================================================
#  КЛАВИАТУРЫ
# ================================================================
def _badge(n: int) -> str:
    """Счётчик на кнопке; у пустого списка не показываем, чтобы не шуметь."""
    return f" · {n}" if n else ""


def main_menu(counts: dict[Category, int]) -> InlineKeyboardMarkup:
    """Верхний ряд — добавление, ниже два действия с выбором категории на втором шаге."""
    total = sum(counts.values())
    return _kb([
        [("🌿 Табак", CB_ADD_TOBACCO), ("🍹 Бар", CB_ADD_BAR), ("📦 Прочее", CB_ADD_OTHER)],
        [(f"📋 Список заказа{_badge(total)}", CB_MENU_LIST)],
        [("🗑 Очистить список", CB_MENU_CLEAR)],
    ])


def _pick_menu(counts: dict[Category, int], cb: dict[Category, str]) -> InlineKeyboardMarkup:
    return _kb([
        [
            (f"🌿 Табак{_badge(counts[Category.TOBACCO])}", cb[Category.TOBACCO]),
            (f"🍹 Бар{_badge(counts[Category.BAR])}",       cb[Category.BAR]),
            (f"📦 Прочее{_badge(counts[Category.OTHER])}",  cb[Category.OTHER]),
        ],
        [("◀️ Назад", CB_BACK_MAIN)],
    ])


def list_menu(counts: dict[Category, int]) -> InlineKeyboardMarkup:
    """Выбор категории для просмотра."""
    return _pick_menu(counts, {
        Category.TOBACCO: CB_LIST_TOBACCO,
        Category.BAR:     CB_LIST_BAR,
        Category.OTHER:   CB_LIST_OTHER,
    })


def clear_menu(counts: dict[Category, int]) -> InlineKeyboardMarkup:
    """Выбор категории для очистки."""
    return _pick_menu(counts, {
        Category.TOBACCO: CB_CLEAR_TOBACCO,
        Category.BAR:     CB_CLEAR_BAR,
        Category.OTHER:   CB_CLEAR_OTHER,
    })

BAR_MENU = _kb([
    [("🥤 Напитки", CB_BAR_DRINKS), ("🍿 Снеки", CB_BAR_SNACKS), ("🫖 Чай", CB_BAR_TEA)],
    [("◀️ Назад",   CB_BACK_MAIN)],
])

DRINKS_MENU = _kb([
    [("🍺 Алко",   CB_DRINKS_ALCO), ("🧃 Б/алко", CB_DRINKS_SOFT)],
    [("◀️ Назад",  CB_BACK_BAR)],
])

CANCEL_KB = _kb([[("❌ Отмена", CB_CANCEL)]])


def tobacco_brands_kb() -> InlineKeyboardMarkup:
    brands = settings.TOBACCO_BRANDS
    rows = [
        [(brand, f"brand:{brand}") for brand in brands[i:i + 2]]
        for i in range(0, len(brands), 2)
    ]
    rows.append([("◀️ Назад", CB_BACK_MAIN)])
    return _kb(rows)