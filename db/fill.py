"""Заполненность списков: пулы с общей ёмкостью и пороги оповещений."""
from dataclasses import dataclass

from config import settings
from db.models import BarSub, Breakdown, Category


@dataclass(frozen=True)
class Pool:
    """Группа позиций с общей ёмкостью — тем, что считается «100 %»."""
    title:         str
    category:      Category
    capacity:      int
    subcategories: frozenset[str] | None = None   # None — вся категория

    def count(self, breakdown: Breakdown) -> int:
        return sum(
            n for (category, sub), n in breakdown.items()
            if category == self.category
            and (self.subcategories is None or sub in self.subcategories)
        )


# Снеки и чай в заполненности не участвуют
POOLS: tuple[Pool, ...] = (
    Pool("🌿 Табак",   Category.TOBACCO, settings.CAPACITY_TOBACCO),
    Pool("🍹 Напитки", Category.BAR,     settings.CAPACITY_BAR_DRINKS,
         frozenset({BarSub.ALCO, BarSub.SOFT})),
    Pool("📦 Прочее",  Category.OTHER,   settings.CAPACITY_OTHER),
)


@dataclass(frozen=True)
class FillAlert:
    pool:      Pool
    count:     int
    threshold: int   # пересечённый порог, %

    @property
    def percent(self) -> int:
        return self.count * 100 // self.pool.capacity


def _threshold_count(capacity: int, percent: int) -> int:
    """Сколько позиций нужно для порога: 80 % от 15 → 12. Округление вверх."""
    return (capacity * percent + 99) // 100


def crossed_thresholds(before: Breakdown, after: Breakdown) -> list[FillAlert]:
    """
    Какие пулы пересекли порог при переходе before → after.

    Состояние не хранится: порог срабатывает, когда позиций было меньше
    него, а стало не меньше. После очистки счётчик падает до нуля, и
    пороги «взводятся» заново сами.

    Если одно сообщение перескочило несколько порогов (вставили длинный
    список), оповещаем только о старшем.
    """
    alerts = []
    for pool in POOLS:
        was, now = pool.count(before), pool.count(after)
        crossed = [
            pct for pct in settings.FILL_THRESHOLDS
            if was < _threshold_count(pool.capacity, pct) <= now
        ]
        if crossed:
            alerts.append(FillAlert(pool, now, max(crossed)))
    return alerts
