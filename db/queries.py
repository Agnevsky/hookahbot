from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    BrandRead,
    Breakdown,
    Category,
    OrderItem,
    OrderItemCreate,
    OrderItemRead,
    RegisteredUser,
    TobaccoBrand,
    split_positions,
)
from db.session import AsyncSessionFactory


def _session() -> AsyncSession:
    return AsyncSessionFactory()


# ================================================================
#  ПОЛЬЗОВАТЕЛИ
# ================================================================

async def register_user(telegram_id: int, username: str | None, full_name: str | None) -> bool:
    """Зарегистрировать пользователя. Возвращает True если новый."""
    async with _session() as session:
        exists = await session.scalar(
            select(RegisteredUser).where(RegisteredUser.telegram_id == telegram_id)
        )
        if exists:
            return False
        session.add(RegisteredUser(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        ))
        await session.commit()
        return True


async def get_all_user_ids() -> list[int]:
    """Получить telegram_id всех зарегистрированных пользователей."""
    async with _session() as session:
        rows = await session.scalars(select(RegisteredUser.telegram_id))
        return list(rows)


async def get_user_names() -> dict[int, str]:
    """telegram_id → имя, чтобы показать, кто добавил позицию."""
    async with _session() as session:
        rows = await session.execute(
            select(RegisteredUser.telegram_id, RegisteredUser.full_name, RegisteredUser.username)
        )
        return {tid: (name or (f"@{username}" if username else str(tid))) for tid, name, username in rows}


# ================================================================
#  ЗАКАЗЫ — ЗАПИСЬ
# ================================================================

async def add_items(data: OrderItemCreate) -> list[OrderItemRead]:
    """
    Добавить позиции. Многострочный текст (вставили список) превращается
    в несколько записей — по одной на строку, чтобы каждую потом можно
    было отредактировать или удалить отдельно.
    """
    positions = split_positions(data.content)
    async with _session() as session:
        items = [
            OrderItem(
                category=data.category,
                subcategory=data.subcategory,
                content=position,
                added_by=data.added_by,
            )
            for position in positions
        ]
        session.add_all(items)
        await session.commit()
        return [OrderItemRead.model_validate(item) for item in items]


async def update_item(item_id: int, content: str, subcategory: str | None) -> OrderItemRead | None:
    """Изменить текст и подкатегорию позиции. None — позиции уже нет."""
    async with _session() as session:
        item = await session.get(OrderItem, item_id)
        if item is None:
            return None
        item.content     = content
        item.subcategory = subcategory
        await session.commit()
        return OrderItemRead.model_validate(item)


async def get_item(item_id: int) -> OrderItemRead | None:
    async with _session() as session:
        item = await session.get(OrderItem, item_id)
        return OrderItemRead.model_validate(item) if item else None


async def delete_items(item_ids: list[int]) -> list[OrderItemRead]:
    """Удалить позиции по id. Возвращает то, что реально удалено."""
    if not item_ids:
        return []
    async with _session() as session:
        rows = await session.scalars(
            delete(OrderItem).where(OrderItem.id.in_(item_ids)).returning(OrderItem)
        )
        deleted = [OrderItemRead.model_validate(r) for r in rows]
        await session.commit()
        return deleted


async def split_multiline_items() -> int:
    """
    Разовая миграция: старые многострочные записи → по записи на строку.
    Время и автор сохраняются. Возвращает, сколько записей разбито.
    """
    async with _session() as session:
        rows = list(await session.scalars(
            select(OrderItem).where(OrderItem.content.contains("\n"))
        ))
        for row in rows:
            for position in split_positions(row.content):
                session.add(OrderItem(
                    category=row.category,
                    subcategory=row.subcategory,
                    content=position,
                    added_by=row.added_by,
                    added_at=row.added_at,
                    is_done=row.is_done,
                ))
            await session.delete(row)
        await session.commit()
        return len(rows)


# ================================================================
#  ЗАКАЗЫ — ЧТЕНИЕ
# ================================================================

async def get_items_by_category(category: Category) -> list[OrderItemRead]:
    """Незакрытые позиции одной категории, сгруппированные по подкатегории."""
    async with _session() as session:
        rows = await session.scalars(
            select(OrderItem)
            .where(OrderItem.category == category, OrderItem.is_done.is_(False))
            .order_by(OrderItem.subcategory, OrderItem.added_at, OrderItem.id)
        )
        return [OrderItemRead.model_validate(r) for r in rows]


async def get_breakdown() -> Breakdown:
    """Сколько позиций ждёт заказа — по (категория, подкатегория)."""
    async with _session() as session:
        rows = await session.execute(
            select(OrderItem.category, OrderItem.subcategory, OrderItem.content)
            .where(OrderItem.is_done.is_(False))
        )
        breakdown: Breakdown = defaultdict(int)
        for category, subcategory, content in rows:
            if n := len(split_positions(content)):
                breakdown[(Category(category), subcategory)] += n
        return dict(breakdown)


def counts_by_category(breakdown: Breakdown) -> dict[Category, int]:
    counts = {c: 0 for c in Category}
    for (category, _), n in breakdown.items():
        counts[category] += n
    return counts


async def get_counts() -> dict[Category, int]:
    """Сколько позиций ждёт заказа в каждой категории."""
    return counts_by_category(await get_breakdown())


async def get_all_items() -> dict[Category, list[OrderItemRead]]:
    async with _session() as session:
        rows = await session.scalars(
            select(OrderItem)
            .where(OrderItem.is_done.is_(False))
            .order_by(OrderItem.category, OrderItem.subcategory, OrderItem.added_at, OrderItem.id)
        )
        grouped: dict[Category, list[OrderItemRead]] = {c: [] for c in Category}
        for row in rows:
            grouped[Category(row.category)].append(OrderItemRead.model_validate(row))
        return grouped


# ================================================================
#  ЗАКАЗЫ — ОЧИСТКА
# ================================================================

async def clear_category(category: Category) -> None:
    """Удалить все позиции категории (физически, не флагом)."""
    async with _session() as session:
        await session.execute(
            delete(OrderItem).where(OrderItem.category == category)
        )
        await session.commit()


# ================================================================
#  МАРКИ ТАБАКА
# ================================================================

async def seed_brands(defaults: list[str]) -> bool:
    """Заполнить пустую таблицу марок значениями по умолчанию."""
    async with _session() as session:
        if await session.scalar(select(func.count()).select_from(TobaccoBrand)):
            return False
        session.add_all(
            TobaccoBrand(name=name, position=i) for i, name in enumerate(defaults)
        )
        await session.commit()
        return True


async def list_brands() -> list[BrandRead]:
    async with _session() as session:
        rows = await session.scalars(
            select(TobaccoBrand).order_by(TobaccoBrand.position, TobaccoBrand.id)
        )
        return [BrandRead.model_validate(r) for r in rows]


async def get_brand(brand_id: int) -> BrandRead | None:
    async with _session() as session:
        brand = await session.get(TobaccoBrand, brand_id)
        return BrandRead.model_validate(brand) if brand else None


async def add_brand(name: str) -> BrandRead | None:
    """Добавить марку в конец списка. None — такая уже есть."""
    async with _session() as session:
        last = await session.scalar(select(func.max(TobaccoBrand.position)))
        brand = TobaccoBrand(name=name, position=(last or 0) + 1)
        session.add(brand)
        try:
            await session.commit()
        except IntegrityError:
            return None
        return BrandRead.model_validate(brand)


async def delete_brand(brand_id: int) -> bool:
    """Убрать марку из списка. Уже добавленные позиции этой марки остаются."""
    async with _session() as session:
        result = await session.execute(
            delete(TobaccoBrand).where(TobaccoBrand.id == brand_id)
        )
        await session.commit()
        return bool(result.rowcount)
