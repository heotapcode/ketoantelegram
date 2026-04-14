"""
Inventory Handler - Nhập kho & Xuất kho
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import (
    search_materials, get_all_materials,
    get_partners_by_type, create_import_transaction, create_export_transaction,
    get_user_by_telegram_id,
)
from database.models import Material
from keyboards.inline import (
    materials_list_keyboard, partners_list_keyboard,
    confirm_keyboard, main_menu_keyboard, back_keyboard,
)
from states.forms import ImportForm, ExportForm
from utils.formatters import format_currency, format_number, format_transaction_info

router = Router()


# ============================================================
# NHẬP KHO
# ============================================================
@router.callback_query(F.data == "menu_import")
async def start_import(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.set_state(ImportForm.search)

    materials = await get_all_materials(session)
    if not materials:
        await callback.message.edit_text(
            "📥 <b>NHẬP KHO</b>\n\n⚠️ Chưa có vật tư nào. Vui lòng thêm vật tư trước.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📥 <b>NHẬP KHO</b>\n\n"
        "Chọn vật tư cần nhập hoặc nhập từ khóa tìm kiếm:",
        reply_markup=materials_list_keyboard(materials, "import"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ImportForm.search)
async def search_import_material(message: Message, state: FSMContext, session: AsyncSession):
    """Tìm vật tư để nhập kho"""
    keyword = message.text.strip()
    materials = await search_materials(session, keyword)

    if not materials:
        await message.answer(
            f"🔍 Không tìm thấy vật tư: <b>{keyword}</b>\nThử lại:",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔍 Kết quả: <b>{keyword}</b>\nChọn vật tư:",
        reply_markup=materials_list_keyboard(materials, "import"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("matsel_import_"))
async def select_import_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    material_id = int(callback.data.split("_")[-1])
    material = await session.get(Material, material_id)

    if not material:
        await callback.answer("❌ Không tìm thấy vật tư!", show_alert=True)
        return

    await state.update_data(material_id=material_id, material_name=material.name,
                            material_code=material.material_code, material_unit=material.unit,
                            current_stock=material.current_stock, current_cost=material.cost_price)
    await state.set_state(ImportForm.quantity)

    await callback.message.edit_text(
        f"📥 <b>NHẬP KHO</b>\n\n"
        f"📦 Vật tư: <b>{material.name}</b>\n"
        f"📋 Mã: <code>{material.material_code}</code>\n"
        f"📊 Tồn hiện tại: <b>{format_number(material.current_stock)} {material.unit}</b>\n\n"
        f"📝 Nhập <b>số lượng</b> cần nhập kho:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ImportForm.quantity)
async def process_import_quantity(message: Message, state: FSMContext):
    try:
        qty = float(message.text.strip().replace(",", ""))
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số dương! VD: 500")
        return

    data = await state.get_data()
    await state.update_data(quantity=qty)
    await state.set_state(ImportForm.unit_price)

    cost_hint = f"\n<i>💡 Giá vốn hiện tại: {format_currency(data.get('current_cost', 0))}</i>" if data.get('current_cost', 0) > 0 else ""

    await message.answer(
        f"✅ Số lượng: <b>{format_number(qty)} {data['material_unit']}</b>\n\n"
        f"💰 Nhập <b>đơn giá nhập</b> (VNĐ):{cost_hint}",
        parse_mode="HTML",
    )


@router.message(ImportForm.unit_price)
async def process_import_price(message: Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip().replace(",", "").replace(".", ""))
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số! VD: 15000")
        return

    await state.update_data(unit_price=price)
    await state.set_state(ImportForm.partner)

    # Lấy danh sách NCC
    suppliers = await get_partners_by_type(session, "SUPPLIER")

    if suppliers:
        await message.answer(
            f"✅ Đơn giá: <b>{format_currency(price)}</b>\n\n"
            "👥 Chọn <b>Nhà cung cấp</b>:",
            reply_markup=partners_list_keyboard(suppliers, "import"),
            parse_mode="HTML",
        )
    else:
        await state.update_data(partner_id=None, partner_name="(Không có)")
        await state.set_state(ImportForm.invoice)
        await message.answer(
            f"✅ Đơn giá: <b>{format_currency(price)}</b>\n\n"
            "📄 Nhập <b>số hóa đơn</b> (hoặc gõ 'skip' để bỏ qua):",
            parse_mode="HTML",
        )


@router.callback_query(ImportForm.partner, F.data.startswith("partsel_import_"))
async def select_import_partner(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    partner_id_str = callback.data.split("_")[-1]

    if partner_id_str == "skip":
        await state.update_data(partner_id=None, partner_name="(Không có)")
    else:
        from database.models import Partner
        partner = await session.get(Partner, int(partner_id_str))
        await state.update_data(partner_id=partner.id, partner_name=partner.name)

    await state.set_state(ImportForm.invoice)
    await callback.message.edit_text(
        "📄 Nhập <b>số hóa đơn</b> (hoặc gõ 'skip' để bỏ qua):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ImportForm.invoice)
async def process_import_invoice(message: Message, state: FSMContext):
    invoice = message.text.strip()
    if invoice.lower() == "skip":
        invoice = None

    await state.update_data(invoice_number=invoice)
    data = await state.get_data()
    await state.set_state(ImportForm.confirm)

    total = data["quantity"] * data["unit_price"]
    summary = (
        "📋 <b>XÁC NHẬN NHẬP KHO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Vật tư: <b>{data['material_name']}</b>\n"
        f"📋 Mã: <code>{data['material_code']}</code>\n"
        f"📊 Số lượng: <b>{format_number(data['quantity'])} {data['material_unit']}</b>\n"
        f"💰 Đơn giá: <b>{format_currency(data['unit_price'])}</b>\n"
        f"💵 Thành tiền: <b>{format_currency(total)}</b>\n"
        f"👥 NCC: {data.get('partner_name', '(Không có)')}\n"
        f"📄 Hóa đơn: {invoice or '(Không có)'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Xác nhận nhập kho?"
    )
    await message.answer(summary, reply_markup=confirm_keyboard("import"), parse_mode="HTML")


@router.callback_query(ImportForm.confirm, F.data == "import_yes")
async def confirm_import(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()

    try:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        transaction = await create_import_transaction(
            session,
            material_id=data["material_id"],
            quantity=data["quantity"],
            unit_price=data["unit_price"],
            partner_id=data.get("partner_id"),
            invoice_number=data.get("invoice_number"),
            user_id=user.id if user else None,
        )

        material = await session.get(Material, data["material_id"])
        await callback.message.edit_text(
            f"<code>{format_transaction_info(transaction, material)}</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Lỗi nhập kho: {str(e)}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(ImportForm.confirm, F.data == "import_no")
async def cancel_import(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Đã hủy nhập kho.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# XUẤT KHO
# ============================================================
@router.callback_query(F.data == "menu_export")
async def start_export(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    await state.set_state(ExportForm.search)

    materials = await get_all_materials(session)
    if not materials:
        await callback.message.edit_text(
            "📤 <b>XUẤT KHO</b>\n\n⚠️ Chưa có vật tư nào.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    # Chỉ hiện vật tư có tồn kho > 0
    in_stock = [m for m in materials if m.current_stock > 0]
    if not in_stock:
        await callback.message.edit_text(
            "📤 <b>XUẤT KHO</b>\n\n⚠️ Tất cả vật tư đều hết hàng!",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📤 <b>XUẤT KHO</b>\n\n"
        "Chọn vật tư cần xuất hoặc nhập từ khóa tìm kiếm:",
        reply_markup=materials_list_keyboard(in_stock, "export"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ExportForm.search)
async def search_export_material(message: Message, state: FSMContext, session: AsyncSession):
    keyword = message.text.strip()
    materials = await search_materials(session, keyword)
    in_stock = [m for m in materials if m.current_stock > 0]

    if not in_stock:
        await message.answer(
            f"🔍 Không tìm thấy vật tư có tồn kho: <b>{keyword}</b>",
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔍 Kết quả: <b>{keyword}</b>\nChọn vật tư:",
        reply_markup=materials_list_keyboard(in_stock, "export"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("matsel_export_"))
async def select_export_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    material_id = int(callback.data.split("_")[-1])
    material = await session.get(Material, material_id)

    if not material:
        await callback.answer("❌ Không tìm thấy!", show_alert=True)
        return

    await state.update_data(
        material_id=material_id, material_name=material.name,
        material_code=material.material_code, material_unit=material.unit,
        current_stock=material.current_stock, selling_price=material.selling_price,
        cost_price=material.cost_price,
    )
    await state.set_state(ExportForm.quantity)

    await callback.message.edit_text(
        f"📤 <b>XUẤT KHO</b>\n\n"
        f"📦 Vật tư: <b>{material.name}</b>\n"
        f"📋 Mã: <code>{material.material_code}</code>\n"
        f"📊 Tồn kho: <b>{format_number(material.current_stock)} {material.unit}</b>\n\n"
        f"📝 Nhập <b>số lượng</b> cần xuất:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ExportForm.quantity)
async def process_export_quantity(message: Message, state: FSMContext):
    try:
        qty = float(message.text.strip().replace(",", ""))
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số dương!")
        return

    data = await state.get_data()
    if qty > data["current_stock"]:
        await message.answer(
            f"⚠️ Tồn kho không đủ!\n"
            f"Hiện có: <b>{format_number(data['current_stock'])} {data['material_unit']}</b>\n"
            f"Yêu cầu: {format_number(qty)} {data['material_unit']}\n\n"
            "Nhập lại số lượng:",
            parse_mode="HTML",
        )
        return

    await state.update_data(quantity=qty)
    await state.set_state(ExportForm.unit_price)

    price_hint = f"\n<i>💡 Giá bán mặc định: {format_currency(data.get('selling_price', 0))}</i>" if data.get('selling_price', 0) > 0 else ""

    await message.answer(
        f"✅ Số lượng: <b>{format_number(qty)} {data['material_unit']}</b>\n\n"
        f"💲 Nhập <b>đơn giá bán</b> (VNĐ):{price_hint}",
        parse_mode="HTML",
    )


@router.message(ExportForm.unit_price)
async def process_export_price(message: Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text.strip().replace(",", "").replace(".", ""))
        if price < 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số! VD: 22000")
        return

    await state.update_data(unit_price=price)
    await state.set_state(ExportForm.partner)

    customers = await get_partners_by_type(session, "CUSTOMER")

    if customers:
        await message.answer(
            f"✅ Đơn giá: <b>{format_currency(price)}</b>\n\n"
            "👥 Chọn <b>Khách hàng</b>:",
            reply_markup=partners_list_keyboard(customers, "export"),
            parse_mode="HTML",
        )
    else:
        await state.update_data(partner_id=None, partner_name="(Không có)")
        await state.set_state(ExportForm.invoice)
        await message.answer(
            f"✅ Đơn giá: <b>{format_currency(price)}</b>\n\n"
            "📄 Nhập <b>số hóa đơn</b> (hoặc gõ 'skip' để bỏ qua):",
            parse_mode="HTML",
        )


@router.callback_query(ExportForm.partner, F.data.startswith("partsel_export_"))
async def select_export_partner(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    partner_id_str = callback.data.split("_")[-1]

    if partner_id_str == "skip":
        await state.update_data(partner_id=None, partner_name="(Không có)")
    else:
        from database.models import Partner
        partner = await session.get(Partner, int(partner_id_str))
        await state.update_data(partner_id=partner.id, partner_name=partner.name)

    await state.set_state(ExportForm.invoice)
    await callback.message.edit_text(
        "📄 Nhập <b>số hóa đơn</b> (hoặc gõ 'skip' để bỏ qua):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ExportForm.invoice)
async def process_export_invoice(message: Message, state: FSMContext):
    invoice = message.text.strip()
    if invoice.lower() == "skip":
        invoice = None

    await state.update_data(invoice_number=invoice)
    data = await state.get_data()
    await state.set_state(ExportForm.confirm)

    total = data["quantity"] * data["unit_price"]
    profit_per_unit = data["unit_price"] - data.get("cost_price", 0)
    total_profit = profit_per_unit * data["quantity"]
    profit_icon = "📈" if total_profit >= 0 else "📉"

    summary = (
        "📋 <b>XÁC NHẬN XUẤT KHO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Vật tư: <b>{data['material_name']}</b>\n"
        f"📋 Mã: <code>{data['material_code']}</code>\n"
        f"📊 Số lượng: <b>{format_number(data['quantity'])} {data['material_unit']}</b>\n"
        f"💲 Đơn giá bán: <b>{format_currency(data['unit_price'])}</b>\n"
        f"💵 Thành tiền: <b>{format_currency(total)}</b>\n"
        f"👥 KH: {data.get('partner_name', '(Không có)')}\n"
        f"📄 Hóa đơn: {invoice or '(Không có)'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{profit_icon} Lãi/lỗ dự kiến: <b>{format_currency(total_profit)}</b>/đơn\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Xác nhận xuất kho?"
    )
    await message.answer(summary, reply_markup=confirm_keyboard("export"), parse_mode="HTML")


@router.callback_query(ExportForm.confirm, F.data == "export_yes")
async def confirm_export(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()

    try:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        transaction = await create_export_transaction(
            session,
            material_id=data["material_id"],
            quantity=data["quantity"],
            unit_price=data["unit_price"],
            partner_id=data.get("partner_id"),
            invoice_number=data.get("invoice_number"),
            user_id=user.id if user else None,
        )

        material = await session.get(Material, data["material_id"])
        await callback.message.edit_text(
            f"<code>{format_transaction_info(transaction, material)}</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Lỗi xuất kho: {str(e)}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(ExportForm.confirm, F.data == "export_no")
async def cancel_export(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Đã hủy xuất kho.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
