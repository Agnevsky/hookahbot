from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, DateTime, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Category(StrEnum):
    TOBACCO = "tobacco"
    BAR     = "bar"
    OTHER   = "other"

    def label(self) -> str:
        return {
            Category.TOBACCO: "🌿 Табак",
            Category.BAR:     "🍹 Бар",
            Category.OTHER:   "📦 Прочее",
        }[self]


def split_positions(content: str) -> list[str]:
    """
    Разбить запись на отдельные позиции.

    Одна запись может быть многострочной (вставили список) — каждая
    непустая строка считается и показывается отдельной позицией.
    """
    return [line.strip() for line in content.splitlines() if line.strip()]


class Base(DeclarativeBase):
    pass


# ── Зарегистрированные пользователи ──────────────────────────────
class RegisteredUser(Base):
    __tablename__ = "registered_users"

    id:          Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username:    Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name:   Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ── Позиции заказа ────────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = "order_items"

    id:          Mapped[int]      = mapped_column(primary_key=True, autoincrement=True)
    category:    Mapped[str]      = mapped_column(Text, nullable=False, index=True)
    subcategory: Mapped[str|None] = mapped_column(Text, nullable=True)
    content:     Mapped[str]      = mapped_column(Text, nullable=False)
    added_by:    Mapped[int]      = mapped_column(BigInteger, nullable=False)
    added_at:    Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_done:     Mapped[bool]     = mapped_column(Boolean, default=False, nullable=False)


# ── Pydantic схемы ────────────────────────────────────────────────
class OrderItemCreate(BaseModel):
    category:    Category
    subcategory: str | None = None
    content:     str
    added_by:    int


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          int
    category:    str
    subcategory: str | None
    content:     str
    added_by:    int
    added_at:    datetime
    is_done:     bool