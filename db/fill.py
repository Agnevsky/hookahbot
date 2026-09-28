"""Заполненность списков: пулы с общей ёмкостью и пороги оповещений."""
from dataclasses import dataclass

from config import settings
from db.models import BarSub, Breakdown, Category

# Какой уровень (%) по каждому пулу уже объявлен — живёт в bot_data
# и переживает перезапуск благодаря PicklePersistence.
Announced = dict[str, int]


@dataclass(frozen=True)
class Pool:
    """Группа позиций с общей ёмкостью — тем, что считается «100 %»."""
    key:           str
    title:         str
    category:      Category
    capacity:      int
    subcategories: frozenset[str] | None = None    # None — вся категория
    recipients:    tuple[int, ...] | None = None   # None — все зарегистрированные

    def count(self, breakdown: Breakdown) -> int:
        return sum(
            n for (category, sub), n in breakdown.items()
            if category == self.category
            and (self.subcategories is None or sub in self.subcategories)
        )


# Снеки и чай в заполненности не участвуют
POOLS: tuple[Pool, ...] = (
    Pool("tobacco", "🌿 Табак", Category.TOBACCO, settings.CAPACITY_TOBACCO,
         recipients=tuple(settings.TOBACCO_ALERT_IDS) or None),
    Pool("drinks", "🍹 Напитки", Category.BAR, settings.CAPACITY_BAR_DRINKS,
         subcategories=frozenset({BarSub.ALCO, BarSub.SOFT})),
    Pool("other", "📦 Прочее", Category.OTHER, settings.CAPACITY_OTHER),
)


@dataclass(frozen=True)
class FillAlert:
    pool:  Pool
    count: int
    level: int   # достигнутый порог, %

    @property
    def percent(self) -> int:
        return self.count * 100 // self.pool.capacity


def _threshold_count(capacity: int, percent: int) -> int:
    """Сколько позиций нужно для порога: 80 % от 15 → 12. Округление вверх."""
    return (capacity * percent + 99) // 100


def fill_level(pool: Pool, count: int) -> int:
    """Старший достигнутый порог, % (0 — ни одного)."""
    return max(
        (pct for pct in settings.FILL_THRESHOLDS
         if count >= _threshold_count(pool.capacity, pct)),
        default=0,
    )


def new_alerts(breakdown: Breakdown, announced: Announced) -> list[FillAlert]:
    """
    Что пора объявить — и отметить в announced как объявленное.

    Объявляем, если достигнутый уровень выше уже объявленного. Поэтому
    пропущенный порог (например, его добавили в настройки, когда список
    уже был выше) догоняется на ближайшем добавлении, а не теряется.
    Уровень ниже объявленного бывает только после очистки — тогда
    просто запоминаем его.
    """
    alerts = []
    for pool in POOLS:
        count = pool.count(breakdown)
        level = fill_level(pool, count)
        if level > announced.get(pool.key, 0):
            alerts.append(FillAlert(pool, count, level))
        announced[pool.key] = level
    return alerts


def current_alerts(breakdown: Breakdown) -> list[FillAlert]:
    """Состояние всех пулов, дошедших хотя бы до младшего порога."""
    alerts = []
    for pool in POOLS:
        count = pool.count(breakdown)
        if level := fill_level(pool, count):
            alerts.append(FillAlert(pool, count, level))
    return alerts


def reset_announced(announced: Announced, category: Category) -> None:
    """Список очищен — пороги его пулов снова активны."""
    for pool in POOLS:
        if pool.category == category:
            announced[pool.key] = 0
