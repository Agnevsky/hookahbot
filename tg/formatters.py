from collections import defaultdict
from datetime import datetime

from db.models import Category, OrderItemRead


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%d.%m %H:%M")


def format_category_list(category: Category, rows: list[OrderItemRead]) -> str:
    """
    Форматирует список позиций одной категории.

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
    if not rows:
        return f"{category.label()}\n\n_— список пуст —_"

    # Группируем по подкатегории
    groups: dict[str, list[str]] = defaultdict(list)
    for item in rows:
        key = item.subcategory or "—"
        groups[key].append(item.content)

    lines = [category.label(), ""]
    for subcat, contents in groups.items():
        lines.append(f"*{subcat}:*")
        for content in contents:
            # Каждая запись может быть многострочной — разбиваем
            for line in content.splitlines():
                line = line.strip()
                if line:
                    lines.append(f"  • {line}")
        lines.append("")

    return "\n".join(lines).rstrip()