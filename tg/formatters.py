import html
from collections import defaultdict

from db.models import Category, OrderItemRead


def format_category_list(category: Category, rows: list[OrderItemRead]) -> str:
    """
    Форматирует список позиций одной категории в HTML (parse_mode="HTML").

    Пользовательский текст экранируется — иначе символы вроде < или &
    ломают разбор разметки на стороне Telegram.

    Для табака группирует по марке:
        🌿 Табак

        Dark Side:
          • Двойное яблоко
          • Виноград минт

        Bonche:
          • Клубника

    Для бара/прочего группирует по подкатегории:
        🍹 Бар

        Алко:
          • Пиво Стелла, Пиво Бад

        Снеки:
          • Чипсы Принглс
    """
    header = html.escape(category.label())
    if not rows:
        return f"{header}\n\n<i>— список пуст —</i>"

    # Группируем по подкатегории (None — позиции без неё, например «Прочее»)
    groups: dict[str | None, list[str]] = defaultdict(list)
    for item in rows:
        groups[item.subcategory].append(item.content)

    lines = [header, ""]
    for subcat, contents in groups.items():
        if subcat:
            lines.append(f"<b>{html.escape(subcat)}:</b>")
        for content in contents:
            # Каждая запись может быть многострочной — разбиваем
            for line in content.splitlines():
                line = line.strip()
                if line:
                    lines.append(f"  • {html.escape(line)}")
        lines.append("")

    return "\n".join(lines).rstrip()
