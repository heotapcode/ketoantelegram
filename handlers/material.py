"""
Material Handler - Quản lý vật tư (CRUD + auto-code)
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import (
    create_material, get_all_materials, search_materials,
    get_low_stock_materials, get_material_by_code,
)
from keyboards.inline import (
    material_menu_keyboard, category_keyboard, unit_keyboard,
    confirm_keyboard, materials_list_keyboard, back_keyboard,
    main_menu_keyboard,
)
from states.forms import AddMaterialForm, SearchMaterialForm
from utils.formatters import format_material_info, format_currency, format_number

router = Router()


# ============================================================
# MENU VẬT TƯ
# ============================================================
@router.callback_query(F.data == "menu_material")
async def show_material_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📦 <b>QUẢN LÝ VẬT TƯ</b>\n\nChọn thao tác:",
        reply_markup=material_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# THÊM VẬT TƯ MỚI
# ============================================================
@router.callback_query(F.data == "mat_add")
async def start_add_material(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddMaterialForm.name)
    await callback.message.edit_text(
        "➕ <b>THÊM VẬT TƯ MỚI</b>\n\n"
        "📝 Nhập <b>tên vật tư</b>:\n"
        "<i>(VD: Thép cuộn phi 10, Ốc vít M8...)</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddMaterialForm.name)
async def process_material_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Tên vật tư quá ngắn. Vui lòng nhập lại:")
        return

    await state.update_data(name=name)
    await state.set_state(AddMaterialForm.category)
    await message.answer(
        f"✅ Tên: <b>{name}</b>\n\n"
        "📂 Chọn <b>nhóm vật tư</b>:",
        reply_markup=category_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(AddMaterialForm.category, F.data.startswith("cat_"))
async def process_material_category(callback: CallbackQuery, state: FSMContext):
    category_code = callback.data.replace("cat_", "")
    await state.update_data(category_code=category_code)
    await state.set_state(AddMaterialForm.unit)
    await callback.message.edit_text(
        f"✅ Nhóm: <b>{category_code}</b>\n\n"
        "📏 Chọn <b>đơn vị tính</b>:",
        reply_markup=unit_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(AddMaterialForm.unit, F.data.startswith("unit_"))
async def process_material_unit(callback: CallbackQuery, state: FSMContext):
    unit = callback.data.replace("unit_", "")
    if unit == "custom":
        await state.set_state(AddMaterialForm.custom_unit)
        await callback.message.edit_text(
            "✏️ Nhập đơn vị tính tùy chỉnh:",
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await state.update_data(unit=unit)
    await state.set_state(AddMaterialForm.cost_price)
    await callback.message.edit_text(
        f"✅ ĐVT: <b>{unit}</b>\n\n"
        "💰 Nhập <b>giá vốn</b> (VNĐ):\n"
        "<i>(VD: 15000 hoặc 0 nếu chưa biết)</i>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AddMaterialForm.custom_unit)
async def process_custom_unit(message: Message, state: FSMContext):
    unit = message.text.strip()
    await state.update_data(unit=unit)
    await state.set_state(AddMaterialForm.cost_price)
    await message.answer(
        f"✅ ĐVT: <b>{unit}</b>\n\n"
        "💰 Nhập <b>giá vốn</b> (VNĐ):\n"
        "<i>(VD: 15000 hoặc 0 nếu chưa biết)</i>",
        parse_mode="HTML",
    )


@router.message(AddMaterialForm.cost_price)
async def process_cost_price(message: Message, state: FSMContext):
    try:
        cost = float(message.text.strip().replace(",", "").replace(".", ""))
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số! VD: 15000")
        return

    await state.update_data(cost_price=cost)
    await state.set_state(AddMaterialForm.selling_price)
    await message.answer(
        f"✅ Giá vốn: <b>{format_currency(cost)}</b>\n\n"
        "💲 Nhập <b>giá bán</b> (VNĐ):\n"
        "<i>(VD: 22000 hoặc 0 nếu chưa biết)</i>",
        parse_mode="HTML",
    )


@router.message(AddMaterialForm.selling_price)
async def process_selling_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "").replace(".", ""))
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số! VD: 22000")
        return

    await state.update_data(selling_price=price)
    await state.set_state(AddMaterialForm.min_stock)
    await message.answer(
        f"✅ Giá bán: <b>{format_currency(price)}</b>\n\n"
        "📊 Nhập <b>mức tồn kho tối thiểu</b>:\n"
        "<i>(Hệ thống sẽ cảnh báo khi dưới mức này. Nhập 0 để bỏ qua)</i>",
        parse_mode="HTML",
    )


@router.message(AddMaterialForm.min_stock)
async def process_min_stock(message: Message, state: FSMContext):
    try:
        min_stock = float(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số! VD: 100")
        return

    await state.update_data(min_stock=min_stock)
    data = await state.get_data()
    await state.set_state(AddMaterialForm.confirm)

    summary = (
        "📋 <b>XÁC NHẬN THÊM VẬT TƯ MỚI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 Tên: <b>{data['name']}</b>\n"
        f"📂 Nhóm: <b>{data['category_code']}</b>\n"
        f"📏 ĐVT: <b>{data['unit']}</b>\n"
        f"💰 Giá vốn: <b>{format_currency(data['cost_price'])}</b>\n"
        f"💲 Giá bán: <b>{format_currency(data['selling_price'])}</b>\n"
        f"📊 Tồn min: <b>{format_number(min_stock)}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 Mã vật tư sẽ được <b>tự động tạo</b>\n\n"
        "Xác nhận thêm vật tư này?"
    )
    await message.answer(summary, reply_markup=confirm_keyboard("addmat"), parse_mode="HTML")


@router.callback_query(AddMaterialForm.confirm, F.data == "addmat_yes")
async def confirm_add_material(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()

    try:
        material = await create_material(
            session,
            name=data["name"],
            category_code=data["category_code"],
            unit=data["unit"],
            cost_price=data["cost_price"],
            selling_price=data["selling_price"],
            min_stock=data.get("min_stock", 0),
        )

        await callback.message.edit_text(
            "✅ <b>ĐÃ TẠO VẬT TƯ MỚI!</b>\n\n"
            f"<code>{format_material_info(material)}</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Lỗi: {str(e)}\n\nVui lòng thử lại.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AddMaterialForm.confirm, F.data == "addmat_no")
async def cancel_add_material(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ Đã hủy thêm vật tư.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# DANH SÁCH VẬT TƯ
# ============================================================
@router.callback_query(F.data == "mat_list")
async def list_materials(callback: CallbackQuery, session: AsyncSession):
    materials = await get_all_materials(session)

    if not materials:
        await callback.message.edit_text(
            "📦 Chưa có vật tư nào.\n\n"
            "Bấm ➕ để thêm vật tư mới.",
            reply_markup=material_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = f"📦 <b>DANH SÁCH VẬT TƯ</b> ({len(materials)} items)\n\n"
    for m in materials[:15]:
        stock_icon = "🟢" if m.current_stock >= m.min_stock or m.min_stock == 0 else "🔴"
        text += f"{stock_icon} <code>{m.material_code}</code> | {m.name} | {format_number(m.current_stock)} {m.unit}\n"

    if len(materials) > 15:
        text += f"\n<i>... và {len(materials) - 15} vật tư khác</i>"

    await callback.message.edit_text(
        text,
        reply_markup=material_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# TÌM KIẾM VẬT TƯ
# ============================================================
@router.callback_query(F.data == "mat_search")
async def start_search(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchMaterialForm.keyword)
    await callback.message.edit_text(
        "🔍 Nhập <b>tên hoặc mã</b> vật tư cần tìm:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SearchMaterialForm.keyword)
async def process_search(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    keyword = message.text.strip()
    materials = await search_materials(session, keyword)

    if not materials:
        await message.answer(
            f"🔍 Không tìm thấy vật tư nào với từ khóa: <b>{keyword}</b>",
            reply_markup=material_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    text = f"🔍 Kết quả tìm kiếm: <b>{keyword}</b> ({len(materials)} kết quả)\n\n"
    for m in materials:
        text += f"📦 <code>{m.material_code}</code>\n"
        text += f"   {m.name} | {format_number(m.current_stock)} {m.unit}\n"
        text += f"   Giá vốn: {format_currency(m.cost_price)} | Giá bán: {format_currency(m.selling_price)}\n\n"

    await message.answer(text, reply_markup=material_menu_keyboard(), parse_mode="HTML")


# ============================================================
# TỒN KHO THẤP
# ============================================================
@router.callback_query(F.data == "mat_low_stock")
async def show_low_stock(callback: CallbackQuery, session: AsyncSession):
    materials = await get_low_stock_materials(session)

    if not materials:
        await callback.message.edit_text(
            "✅ <b>Tất cả vật tư đều đủ tồn kho!</b>\n\n"
            "Không có vật tư nào dưới mức tối thiểu.",
            reply_markup=material_menu_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = f"⚠️ <b>CẢNH BÁO TỒN KHO THẤP</b> ({len(materials)} items)\n\n"
    for m in materials:
        text += (
            f"🔴 <code>{m.material_code}</code> | {m.name}\n"
            f"   Tồn: <b>{format_number(m.current_stock)}</b> / "
            f"Min: {format_number(m.min_stock)} {m.unit}\n\n"
        )

    await callback.message.edit_text(
        text, reply_markup=material_menu_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


# ============================================================
# LỆNH NHANH: /stock, /search, /lowstock
# ============================================================
@router.message(Command("stock"))
async def cmd_stock(message: Message, session: AsyncSession):
    materials = await get_all_materials(session)
    if not materials:
        await message.answer("📦 Chưa có vật tư nào.")
        return

    text = "📦 <b>TỒN KHO HIỆN TẠI</b>\n\n"
    total_value = 0
    for m in materials:
        value = m.current_stock * m.cost_price
        total_value += value
        stock_icon = "🟢" if m.current_stock >= m.min_stock or m.min_stock == 0 else "🔴"
        text += f"{stock_icon} {m.material_code} | {m.name}: <b>{format_number(m.current_stock)}</b> {m.unit}\n"

    text += f"\n━━━━━━━━━━━━━━━\n💰 Tổng giá trị tồn kho: <b>{format_currency(total_value)}</b>"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("search"))
async def cmd_search(message: Message, session: AsyncSession):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("🔍 Cách dùng: /search [từ khóa]\nVD: /search thép")
        return

    keyword = parts[1]
    materials = await search_materials(session, keyword)
    if not materials:
        await message.answer(f"🔍 Không tìm thấy: {keyword}")
        return

    text = f"🔍 Kết quả: <b>{keyword}</b>\n\n"
    for m in materials:
        text += f"📦 {m.material_code} | {m.name} | {format_number(m.current_stock)} {m.unit}\n"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("lowstock"))
async def cmd_lowstock(message: Message, session: AsyncSession):
    materials = await get_low_stock_materials(session)
    if not materials:
        await message.answer("✅ Tất cả vật tư đều đủ tồn kho!")
        return

    text = f"⚠️ <b>TỒN KHO THẤP</b> ({len(materials)} items)\n\n"
    for m in materials:
        text += f"🔴 {m.material_code} | {m.name}: {format_number(m.current_stock)}/{format_number(m.min_stock)} {m.unit}\n"
    await message.answer(text, parse_mode="HTML")
