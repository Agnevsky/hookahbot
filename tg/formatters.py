import html
from collections import defaultdict

from db.fill import FillAlert
from db.models import Category, OrderItemRead, split_positions


def format_fill_alert(alert: FillAlert) -> str:
    """Оповещение о заполненности (HTML)."""
    title = html.escape(alert.pool.title)
    stats = f"{alert.count} из {alert.pool.capacity}"
    if alert.threshold >= 100:
        return f"🔴 <b>{title}</b>: список заполнен ({stats}) — пора делать заказ!"
    return f"🟡 <b>{title}</b>: заполнено на {alert.percent}% ({stats}) — скоро пора заказывать."


def plural_positions(n: int) -> str:
    """1 позиция, 2 позиции, 5 позиций, 11 позиций, 21 позиция."""
    if n % 10 == 1 and n % 100 != 11:
        word = "позиция"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "позиции"
    else:
        word = "позиций"
    return f"{n} {word}"


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
    # Группируем по подкатегории (None — позиции без неё, например «Прочее»)
    groups: dict[str | None, list[str]] = defaultdict(list)
    for item in rows:
        positions = split_positions(item.content)
        if positions:  # не заводим пустую группу — иначе заголовок без пунктов
            groups[item.subcategory].extend(positions)

    total = sum(len(positions) for positions in groups.values())
    header = html.escape(category.label())
    if not total:
        return f"{header}\n\n<i>— список пуст —</i>"

    lines = [f"{header} · {plural_positions(total)}", ""]
    for subcat, positions in groups.items():
        if subcat:
            lines.append(f"<b>{html.escape(subcat)}</b> · {len(positions)}")
        for position in positions:
            lines.append(f"  • {html.escape(position)}")
        lines.append("")

    return "\n".join(lines).rstrip()
