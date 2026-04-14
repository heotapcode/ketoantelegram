"""
Start Handler - /start, /help và menu chính
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import get_or_create_user
from keyboards.inline import main_menu_keyboard
from config import ADMIN_TELEGRAM_ID

router = Router()


WELCOME_TEXT = """
🤖 <b>AI Kế Toán Bot</b> - Xin chào <b>{name}</b>!

Tôi là trợ lý kế toán AI, giúp bạn:
📦 Quản lý vật tư & tự gán mã
📥 Nhập kho  |  📤 Xuất kho
💰 Tính lãi lỗ theo SP & theo kỳ
📊 Báo cáo tồn kho & xuất Excel
👥 Quản lý NCC & Khách hàng

━━━━━━━━━━━━━━━━━━━━
Chọn chức năng bên dưới:
"""

HELP_TEXT = """
📖 <b>HƯỚNG DẪN SỬ DỤNG</b>

<b>Lệnh nhanh:</b>
/start - Mở menu chính
/help - Xem hướng dẫn
/stock - Xem tồn kho nhanh
/search [từ khóa] - Tìm vật tư
/lowstock - Vật tư sắp hết

<b>Cách sử dụng:</b>
1️⃣ Bấm nút trên menu để chọn chức năng
2️⃣ Làm theo hướng dẫn từng bước
3️⃣ Xác nhận thao tác khi được hỏi

<b>Quy tắc mã vật tư tự động:</b>
• NVL-xxx-xxxx = Nguyên vật liệu
• HH-xxx-xxxx  = Hàng hóa
• TP-xxx-xxxx  = Thành phẩm
• CCDC-xxx-xxxx = Công cụ dụng cụ

💡 <i>Mã được tạo tự động khi thêm vật tư mới</i>
"""


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    """Xử lý lệnh /start"""
    await state.clear()

    # Tạo hoặc lấy user
    user = await get_or_create_user(
        session,
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
    )

    # Nếu là admin đầu tiên, auto set role ADMIN
    if message.from_user.id == ADMIN_TELEGRAM_ID and user.role != "ADMIN":
        user.role = "ADMIN"
        await session.commit()

    await message.answer(
        WELCOME_TEXT.format(name=message.from_user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Xử lý lệnh /help"""
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Quay về menu chính"""
    await state.clear()
    await callback.message.edit_text(
        WELCOME_TEXT.format(name=callback.from_user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Hủy thao tác hiện tại"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Đã hủy thao tác.\n\n" + WELCOME_TEXT.format(name=callback.from_user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
