"""
Database Middleware - Inject DB session vào mỗi handler
"""
from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.engine import async_session


class DatabaseMiddleware(BaseMiddleware):
    """Middleware inject AsyncSession vào handler data"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            return await handler(event, data)
