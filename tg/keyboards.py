from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings


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
# Верхний ряд — добавление, ниже два действия с выбором категории на втором шаге
MAIN_MENU = _kb([
    [("🌿 Табак", CB_ADD_TOBACCO), ("🍹 Бар", CB_ADD_BAR), ("📦 Прочее", CB_ADD_OTHER)],
    [("📋 Список заказа", CB_MENU_LIST)],
    [("🗑 Очистить список", CB_MENU_CLEAR)],
])

# Выбор категории для просмотра
LIST_MENU = _kb([
    [("🌿 Табак", CB_LIST_TOBACCO), ("🍹 Бар", CB_LIST_BAR), ("📦 Прочее", CB_LIST_OTHER)],
    [("◀️ Назад", CB_BACK_MAIN)],
])

# Выбор категории для очистки
CLEAR_MENU = _kb([
    [("🌿 Табак", CB_CLEAR_TOBACCO), ("🍹 Бар", CB_CLEAR_BAR), ("📦 Прочее", CB_CLEAR_OTHER)],
    [("◀️ Назад", CB_BACK_MAIN)],
])

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