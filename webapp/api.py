"""
HTTP-API веб-приложения (Telegram Mini App) и раздача фронтенда.

Работает в одном процессе с ботом: использует тот же объект бота для
рассылок и тот же bot_data — пороги заполненности общие, оповещения
не дублируются.
"""
import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from telegram.ext import Application

from config import settings
from db.fill import POOLS, FillAlert, fill_level
from db.models import BarSub, Category, OrderItemCreate, split_positions
from db.queries import (
    add_brand,
    add_items,
    clear_category,
    delete_brand,
    delete_items,
    get_all_items,
    get_breakdown,
    get_item,
    get_user_names,
    list_brands,
    register_user,
    update_item,
)
from notify import after_clear, after_items_changed, responsible_by_id, send_to_responsible
from webapp.auth import InitDataError, TgUser, validate_init_data

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

MAX_POSITION_LEN = 300   # символов в одной позиции
MAX_POSITIONS    = 100   # позиций за одно добавление

CATEGORY_META = {
    Category.TOBACCO: {"title": "Табак",  "emoji": "🌿"},
    Category.BAR:     {"title": "Бар",    "emoji": "🍹"},
    Category.OTHER:   {"title": "Прочее", "emoji": "📦"},
}
BAR_SUBS = [
    {"value": BarSub.ALCO.value,   "emoji": "🍺"},
    {"value": BarSub.SOFT.value,   "emoji": "🧃"},
    {"value": BarSub.SNACKS.value, "emoji": "🍿"},
    {"value": BarSub.TEA.value,    "emoji": "🫖"},
]


# ================================================================
#  СХЕМЫ ЗАПРОСОВ
# ================================================================

class ItemsCreate(BaseModel):
    category:    Category
    subcategory: str | None = None
    content:     str = Field(min_length=1, max_length=MAX_POSITION_LEN * MAX_POSITIONS)


class ItemUpdate(BaseModel):
    content:     str = Field(min_length=1, max_length=MAX_POSITION_LEN)
    subcategory: str | None = None

    @field_validator("content")
    @classmethod
    def _one_line(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("пустая позиция")
        return v


class ItemsDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def _clean(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("пустое название")
        return v


# ================================================================
#  ПРИЛОЖЕНИЕ
# ================================================================

def create_web_app(tg_app: Application) -> FastAPI:
    api = FastAPI(title="Hookah orders", docs_url=None, redoc_url=None, openapi_url=None)
    bot = tg_app.bot
    bot_data: dict[str, Any] = tg_app.bot_data

    # ── Авторизация: заголовок «Authorization: tma <initData>» ─────
    async def current_user(authorization: Annotated[str | None, Header()] = None) -> TgUser:
        if not authorization or not authorization.startswith("tma "):
            raise HTTPException(401, "Откройте приложение через Telegram")
        try:
            user = validate_init_data(
                authorization.removeprefix("tma "),
                settings.BOT_TOKEN,
                settings.WEBAPP_AUTH_TTL,
            )
        except InitDataError as e:
            raise HTTPException(401, f"Нет доступа: {e}") from e
        return user

    def is_admin(user: TgUser) -> bool:
        return user.id in settings.ADMIN_IDS

    async def admin_user(user: Annotated[TgUser, Depends(current_user)]) -> TgUser:
        if not is_admin(user):
            raise HTTPException(403, "Только для администратора")
        return user

    User  = Annotated[TgUser, Depends(current_user)]
    Admin = Annotated[TgUser, Depends(admin_user)]

    async def check_subcategory(category: Category, sub: str | None, keep: str | None = None) -> str | None:
        """Подкатегория должна подходить к категории. keep — текущая (марку могли убрать из списка)."""
        sub = sub or None
        if category is Category.OTHER:
            return None
        if category is Category.BAR:
            if sub not in {s.value for s in BarSub}:
                raise HTTPException(422, "Выберите раздел бара")
            return sub
        if sub == keep and sub is not None:
            return sub
        if sub not in {b.name for b in await list_brands()}:
            raise HTTPException(422, "Выберите марку табака")
        return sub

    def alert_json(alert: FillAlert) -> dict:
        return {
            "pool": alert.pool.key, "title": alert.pool.title, "count": alert.count,
            "capacity": alert.pool.capacity, "percent": alert.percent, "level": alert.level,
        }

    # ── Состояние целиком: одним запросом, приложение маленькое ──────
    @api.get("/api/state")
    async def state(user: User) -> dict:
        await register_user(user.id, user.username, user.full_name)
        grouped   = await get_all_items()
        breakdown = await get_breakdown()
        names     = await get_user_names()
        admin     = is_admin(user)

        categories = []
        for category, items in grouped.items():
            categories.append({
                "key":   category.value,
                **CATEGORY_META[category],
                "count": sum(len(split_positions(i.content)) for i in items),
                "items": [
                    {
                        "id":          i.id,
                        "subcategory": i.subcategory,
                        "content":     i.content,
                        "added_at":    i.added_at.isoformat(),
                        "added_by":    names.get(i.added_by, ""),
                        "mine":        i.added_by == user.id,
                    }
                    for i in items
                ],
            })

        pools = []
        for pool in POOLS:
            count = pool.count(breakdown)
            pools.append({
                "key": pool.key, "title": pool.title, "category": pool.category.value,
                "count": count, "capacity": pool.capacity,
                "percent": count * 100 // pool.capacity, "level": fill_level(pool, count),
            })

        return {
            "me": {"id": user.id, "name": user.first_name, "is_admin": admin},
            "categories": categories,
            "pools": pools,
            "brands": [b.model_dump() for b in await list_brands()],
            "bar_subs": BAR_SUBS,
            "thresholds": settings.FILL_THRESHOLDS,
            "responsible": [
                {"id": r.telegram_id, "name": r.name, "categories": r.categories}
                for r in settings.RESPONSIBLE
            ] if admin else [],
        }

    # ── Позиции ─────────────────────────────────────────────────────
    @api.post("/api/items")
    async def create_items(body: ItemsCreate, user: User) -> dict:
        positions = split_positions(body.content)
        if not positions:
            raise HTTPException(422, "Напишите хотя бы одну позицию")
        if len(positions) > MAX_POSITIONS:
            raise HTTPException(422, f"Не больше {MAX_POSITIONS} позиций за раз")
        if any(len(p) > MAX_POSITION_LEN for p in positions):
            raise HTTPException(422, f"Позиция длиннее {MAX_POSITION_LEN} символов")

        sub = await check_subcategory(body.category, body.subcategory)
        created = await add_items(OrderItemCreate(
            category=body.category, subcategory=sub,
            content="\n".join(positions), added_by=user.id,
        ))
        _, alerts = await after_items_changed(bot, bot_data, sender_id=user.id)
        log.info("WebApp: %s добавил %d поз. в %s/%s", user.id, len(created), body.category, sub)
        return {"added": len(created), "alerts": [alert_json(a) for a in alerts]}

    @api.patch("/api/items/{item_id}")
    async def edit_item(item_id: int, body: ItemUpdate, user: User) -> dict:
        current = await get_item(item_id)
        if current is None:
            raise HTTPException(404, "Позиция уже удалена")
        category = Category(current.category)
        sub = await check_subcategory(category, body.subcategory, keep=current.subcategory)
        await update_item(item_id, body.content, sub)
        # Смена раздела бара (снеки → алко) меняет заполненность
        _, alerts = await after_items_changed(bot, bot_data, sender_id=user.id)
        log.info("WebApp: %s изменил позицию %d", user.id, item_id)
        return {"ok": True, "alerts": [alert_json(a) for a in alerts]}

    @api.post("/api/items/delete")
    async def remove_items(body: ItemsDelete, user: User) -> dict:
        deleted = await delete_items(body.ids)
        log.info("WebApp: %s удалил позиции %s", user.id, [d.id for d in deleted])
        return {"deleted": len(deleted)}

    @api.post("/api/categories/{category}/clear")
    async def clear(category: Category, user: User) -> dict:
        await clear_category(category)
        await after_clear(bot, bot_data, category, sender_id=user.id)
        log.info("WebApp: %s очистил %s", user.id, category)
        return {"ok": True}

    # ── Марки табака (администратор) ────────────────────────────────
    @api.post("/api/brands")
    async def create_brand(body: BrandCreate, user: Admin) -> dict:
        brand = await add_brand(body.name)
        if brand is None:
            raise HTTPException(409, "Такая марка уже есть")
        return brand.model_dump()

    @api.delete("/api/brands/{brand_id}")
    async def remove_brand(brand_id: int, user: Admin) -> dict:
        if not await delete_brand(brand_id):
            raise HTTPException(404, "Марка не найдена")
        return {"ok": True}

    # ── «Отправить ответственному» (администратор) ──────────────────
    @api.post("/api/send/{telegram_id}")
    async def send(telegram_id: int, user: Admin) -> dict:
        person = responsible_by_id(telegram_id)
        if person is None:
            raise HTTPException(404, "Ответственный не найден")
        result = await send_to_responsible(bot, bot_data, person)
        if not result.ok:
            raise HTTPException(502, f"Не доставлено {person.name}: {result.error}")
        return {"ok": True, "name": person.name}

    # ── Фронтенд ────────────────────────────────────────────────────
    @api.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        return {"ok": True}

    @api.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        # Без кеша: после деплоя Telegram сразу подхватит новую версию
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return api
