"""
🤖 AI Kế Toán Bot - Entry Point
Bot Telegram hỗ trợ kế toán nội bộ doanh nghiệp
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database.engine import init_db, async_session
from database.crud import create_default_categories
from middlewares.db import DatabaseMiddleware

# Import all routers
from handlers.start import router as start_router
from handlers.material import router as material_router
from handlers.inventory import router as inventory_router
from handlers.partner import router as partner_router
from handlers.report import router as report_router
from handlers.invoice import router as invoice_router


# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Khởi tạo khi bot start"""
    logger.info("🚀 Bot đang khởi động...")

    # Khởi tạo database
    await init_db()
    logger.info("✅ Database đã khởi tạo")

    # Tạo danh mục vật tư mặc định
    async with async_session() as session:
        await create_default_categories(session)
    logger.info("✅ Danh mục vật tư mặc định đã tạo")

    # Thông tin bot
    bot_info = await bot.get_me()
    logger.info(f"✅ Bot @{bot_info.username} đã sẵn sàng!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("🤖 AI Kế Toán Bot - Running")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━")


async def main():
    """Main function"""
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        logger.error("❌ BOT_TOKEN chưa được cấu hình!")
        logger.error("📝 Mở file .env và thay 'your_bot_token_here' bằng token từ @BotFather")
        logger.error("   1. Mở Telegram → tìm @BotFather")
        logger.error("   2. Gõ /newbot → đặt tên bot → lấy token")
        logger.error("   3. Paste token vào file .env")
        sys.exit(1)

    # Khởi tạo Bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Khởi tạo Dispatcher
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Register routers (thứ tự quan trọng!)
    dp.include_router(start_router)
    dp.include_router(material_router)
    dp.include_router(inventory_router)
    dp.include_router(partner_router)
    dp.include_router(report_router)
    dp.include_router(invoice_router)

    # Startup hook
    dp.startup.register(on_startup)

    # Bắt đầu polling
    logger.info("⏳ Đang kết nối Telegram...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot đã dừng.")
