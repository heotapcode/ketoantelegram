"""
Inline Keyboards - Tất cả bàn phím tương tác
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import MATERIAL_CODE_PREFIXES, COMMON_UNITS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu chính"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Quản lý Vật tư", callback_data="menu_material"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Nhập kho", callback_data="menu_import"),
        InlineKeyboardButton(text="📤 Xuất kho", callback_data="menu_export"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Báo cáo", callback_data="menu_report"),
        InlineKeyboardButton(text="💰 Lãi / Lỗ", callback_data="menu_profit"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Đối tác", callback_data="menu_partner"),
        InlineKeyboardButton(text="⚙️ Cài đặt", callback_data="menu_settings"),
    )
    return builder.as_markup()


def material_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu quản lý vật tư"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Thêm vật tư mới", callback_data="mat_add"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Danh sách vật tư", callback_data="mat_list"),
        InlineKeyboardButton(text="🔍 Tìm kiếm", callback_data="mat_search"),
    )
    builder.row(
        InlineKeyboardButton(text="⚠️ Tồn kho thấp", callback_data="mat_low_stock"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    """Chọn nhóm vật tư"""
    builder = InlineKeyboardBuilder()
    for code, name in MATERIAL_CODE_PREFIXES.items():
        builder.row(
            InlineKeyboardButton(text=f"{code} - {name}", callback_data=f"cat_{code}")
        )
    builder.row(
        InlineKeyboardButton(text="❌ Hủy", callback_data="cancel"),
    )
    return builder.as_markup()


def unit_keyboard() -> InlineKeyboardMarkup:
    """Chọn đơn vị tính"""
    builder = InlineKeyboardBuilder()
    for i in range(0, len(COMMON_UNITS), 3):
        row_units = COMMON_UNITS[i:i + 3]
        builder.row(
            *[InlineKeyboardButton(text=u, callback_data=f"unit_{u}") for u in row_units]
        )
    builder.row(
        InlineKeyboardButton(text="✏️ Nhập đơn vị khác", callback_data="unit_custom"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Hủy", callback_data="cancel"),
    )
    return builder.as_markup()


def confirm_keyboard(prefix: str = "confirm") -> InlineKeyboardMarkup:
    """Xác nhận / Hủy"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Xác nhận", callback_data=f"{prefix}_yes"),
        InlineKeyboardButton(text="❌ Hủy", callback_data=f"{prefix}_no"),
    )
    return builder.as_markup()


def materials_list_keyboard(materials: list, action: str = "select") -> InlineKeyboardMarkup:
    """Danh sách vật tư dạng nút"""
    builder = InlineKeyboardBuilder()
    for mat in materials[:20]:  # Giới hạn 20 items
        builder.row(
            InlineKeyboardButton(
                text=f"{mat.material_code} | {mat.name} ({mat.current_stock:,.0f} {mat.unit})",
                callback_data=f"matsel_{action}_{mat.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def partner_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu đối tác"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Thêm NCC", callback_data="partner_add_SUPPLIER"),
        InlineKeyboardButton(text="➕ Thêm KH", callback_data="partner_add_CUSTOMER"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 DS Nhà cung cấp", callback_data="partner_list_SUPPLIER"),
        InlineKeyboardButton(text="📋 DS Khách hàng", callback_data="partner_list_CUSTOMER"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def partners_list_keyboard(partners: list, action: str = "select") -> InlineKeyboardMarkup:
    """Danh sách đối tác dạng nút"""
    builder = InlineKeyboardBuilder()
    for p in partners[:20]:
        builder.row(
            InlineKeyboardButton(
                text=f"{p.code} | {p.name}",
                callback_data=f"partsel_{action}_{p.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="⏭ Bỏ qua", callback_data=f"partsel_{action}_skip"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def report_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu báo cáo"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Tồn kho", callback_data="report_stock"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Nhập kho trong kỳ", callback_data="report_import"),
        InlineKeyboardButton(text="📤 Xuất kho trong kỳ", callback_data="report_export"),
    )
    builder.row(
        InlineKeyboardButton(text="💰 Lãi lỗ theo SP", callback_data="report_profit_product"),
        InlineKeyboardButton(text="📈 Lãi lỗ theo kỳ", callback_data="report_profit_period"),
    )
    builder.row(
        InlineKeyboardButton(text="📎 Xuất Excel tồn kho", callback_data="report_excel"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def period_keyboard() -> InlineKeyboardMarkup:
    """Chọn kỳ báo cáo"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Hôm nay", callback_data="period_today"),
        InlineKeyboardButton(text="📅 7 ngày", callback_data="period_7d"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Tháng này", callback_data="period_month"),
        InlineKeyboardButton(text="📅 Quý này", callback_data="period_quarter"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Năm nay", callback_data="period_year"),
        InlineKeyboardButton(text="📅 Tất cả", callback_data="period_all"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại", callback_data="back_main"),
    )
    return builder.as_markup()


def back_keyboard(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Quay lại Menu", callback_data=callback_data),
    )
    return builder.as_markup()
