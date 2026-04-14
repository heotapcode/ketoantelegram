"""
Partner Handler - Quản lý nhà cung cấp & khách hàng
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import create_partner, get_partners_by_type, get_all_partners
from keyboards.inline import partner_menu_keyboard, confirm_keyboard, main_menu_keyboard
from states.forms import AddPartnerForm

router = Router()


@router.callback_query(F.data == "menu_partner")
async def show_partner_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👥 <b>QUẢN LÝ ĐỐI TÁC</b>\n\nChọn thao tác:",
        reply_markup=partner_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# THÊM ĐỐI TÁC
# ============================================================
@router.callback_query(F.data.startswith("partner_add_"))
async def start_add_partner(callback: CallbackQuery, state: FSMContext):
    partner_type = callback.data.replace("partner_add_", "")
    type_name = "Nhà cung cấp" if partner_type == "SUPPLIER" else "Khách hàng"

    await state.update_data(partner_type=partner_type, type_name=type_name)
    await state.set_state(AddPartnerForm.name)

    await callback.message.edit_text(
        f"➕ <b>THÊM {type_name.upper()}</b>\n\n"
        f"📝 Nhập <b>tên {type_name}</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddPartnerForm.name)
async def process_partner_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Tên quá ngắn. Nhập lại:")
        return

    await state.update_data(name=name)
    await state.set_state(AddPartnerForm.phone)
    await message.answer(
        f"✅ Tên: <b>{name}</b>\n\n"
        "📞 Nhập <b>số điện thoại</b> (hoặc gõ 'skip'):",
        parse_mode="HTML",
    )


@router.message(AddPartnerForm.phone)
async def process_partner_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if phone.lower() == "skip":
        phone = None

    await state.update_data(phone=phone)
    await state.set_state(AddPartnerForm.address)
    await message.answer(
        "📍 Nhập <b>địa chỉ</b> (hoặc gõ 'skip'):",
        parse_mode="HTML",
    )


@router.message(AddPartnerForm.address)
async def process_partner_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if address.lower() == "skip":
        address = None

    await state.update_data(address=address)
    data = await state.get_data()
    await state.set_state(AddPartnerForm.confirm)

    summary = (
        f"📋 <b>XÁC NHẬN THÊM {data['type_name'].upper()}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Tên: <b>{data['name']}</b>\n"
        f"📞 SĐT: {data.get('phone') or '(Không có)'}\n"
        f"📍 Địa chỉ: {address or '(Không có)'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 Mã đối tác sẽ được <b>tự động tạo</b>\n\n"
        "Xác nhận?"
    )
    await message.answer(summary, reply_markup=confirm_keyboard("addpart"), parse_mode="HTML")


@router.callback_query(AddPartnerForm.confirm, F.data == "addpart_yes")
async def confirm_add_partner(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()

    try:
        partner = await create_partner(
            session,
            name=data["name"],
            partner_type=data["partner_type"],
            phone=data.get("phone"),
            address=data.get("address"),
        )

        type_icon = "🏭" if data["partner_type"] == "SUPPLIER" else "🧑‍💼"
        await callback.message.edit_text(
            f"✅ <b>ĐÃ THÊM {data['type_name'].upper()}!</b>\n\n"
            f"{type_icon} Mã: <code>{partner.code}</code>\n"
            f"📝 Tên: {partner.name}\n"
            f"📞 SĐT: {partner.phone or '(Không có)'}\n"
            f"📍 ĐC: {partner.address or '(Không có)'}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Lỗi: {str(e)}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AddPartnerForm.confirm, F.data == "addpart_no")
async def cancel_add_partner(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Đã hủy.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# DANH SÁCH ĐỐI TÁC
# ============================================================
@router.callback_query(F.data.startswith("partner_list_"))
async def list_partners(callback: CallbackQuery, session: AsyncSession):
    partner_type = callback.data.replace("partner_list_", "")
    type_name = "NHÀ CUNG CẤP" if partner_type == "SUPPLIER" else "KHÁCH HÀNG"
    type_icon = "🏭" if partner_type == "SUPPLIER" else "🧑‍💼"

    partners = await get_partners_by_type(session, partner_type)

    if not partners:
        await callback.message.edit_text(
            f"{type_icon} Chưa có {type_name.lower()} nào.",
            reply_markup=partner_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = f"{type_icon} <b>DANH SÁCH {type_name}</b> ({len(partners)})\n\n"
    for p in partners:
        text += f"📋 <code>{p.code}</code> | <b>{p.name}</b>\n"
        if p.phone:
            text += f"   📞 {p.phone}\n"
        if p.address:
            text += f"   📍 {p.address}\n"
        text += "\n"

    await callback.message.edit_text(
        text, reply_markup=partner_menu_keyboard(), parse_mode="HTML",
    )
    await callback.answer()
