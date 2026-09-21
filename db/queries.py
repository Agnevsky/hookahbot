from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Category, OrderItem, OrderItemCreate, OrderItemRead, RegisteredUser
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


# ================================================================
#  ЗАКАЗЫ — ЗАПИСЬ
# ================================================================

async def add_item(data: OrderItemCreate) -> OrderItemRead:
    async with _session() as session:
        item = OrderItem(**data.model_dump())
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return OrderItemRead.model_validate(item)


# ================================================================
#  ЗАКАЗЫ — ЧТЕНИЕ
# ================================================================

async def get_items_by_category(category: Category) -> list[OrderItemRead]:
    """Незакрытые позиции одной категории, сгруппированные по подкатегории."""
    async with _session() as session:
        rows = await session.scalars(
            select(OrderItem)
            .where(OrderItem.category == category, OrderItem.is_done.is_(False))
            .order_by(OrderItem.subcategory, OrderItem.added_at)
        )
        return [OrderItemRead.model_validate(r) for r in rows]


async def get_all_items() -> dict[Category, list[OrderItemRead]]:
    async with _session() as session:
        rows = await session.scalars(
            select(OrderItem)
            .where(OrderItem.is_done.is_(False))
            .order_by(OrderItem.category, OrderItem.subcategory, OrderItem.added_at)
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