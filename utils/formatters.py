"""
Formatters - Định dạng số, tiền tệ, ngày giờ
"""
from datetime import datetime


def format_currency(amount: float) -> str:
    """Format số tiền VNĐ: 1,500,000 ₫"""
    if amount >= 0:
        return f"{amount:,.0f} ₫"
    return f"-{abs(amount):,.0f} ₫"


def format_number(num: float) -> str:
    """Format số: 1,500.5"""
    if num == int(num):
        return f"{int(num):,}"
    return f"{num:,.1f}"


def format_date(dt: datetime) -> str:
    """Format ngày: 13/04/2026"""
    return dt.strftime("%d/%m/%Y")


def format_datetime(dt: datetime) -> str:
    """Format ngày giờ: 13/04/2026 23:30"""
    return dt.strftime("%d/%m/%Y %H:%M")


def format_profit_indicator(profit: float) -> str:
    """Hiển thị lãi/lỗ với emoji"""
    if profit > 0:
        return f"📈 +{format_currency(profit)}"
    elif profit < 0:
        return f"📉 {format_currency(profit)}"
    return "➖ 0 ₫"


def format_material_info(material) -> str:
    """Format thông tin vật tư dạng card"""
    lines = [
        f"┌─────────────────────────────┐",
        f"│ 📦 THÔNG TIN VẬT TƯ",
        f"├─────────────────────────────┤",
        f"│ Mã:      {material.material_code}",
        f"│ Tên:     {material.name}",
        f"│ ĐVT:     {material.unit}",
        f"│ Giá vốn: {format_currency(material.cost_price)}",
        f"│ Giá bán: {format_currency(material.selling_price)}",
        f"│ Tồn kho: {format_number(material.current_stock)} {material.unit}",
    ]
    if material.min_stock > 0:
        status = "🟢" if material.current_stock >= material.min_stock else "🔴"
        lines.append(f"│ Tồn min: {format_number(material.min_stock)} {material.unit} {status}")

    lines.append(f"└─────────────────────────────┘")
    return "\n".join(lines)


def format_transaction_info(transaction, material) -> str:
    """Format thông tin giao dịch"""
    icon = "📥" if transaction.transaction_type == "IMPORT" else "📤"
    type_text = "NHẬP KHO" if transaction.transaction_type == "IMPORT" else "XUẤT KHO"

    lines = [
        f"┌─────────────────────────────┐",
        f"│ {icon} {type_text} THÀNH CÔNG!",
        f"├─────────────────────────────┤",
        f"│ Vật tư:   {material.name}",
        f"│ Mã:       {material.material_code}",
        f"│ Số lượng: {format_number(transaction.quantity)} {material.unit}",
        f"│ Đơn giá:  {format_currency(transaction.unit_price)}",
        f"│ Thành tiền: {format_currency(transaction.total_amount)}",
    ]
    if transaction.invoice_number:
        lines.append(f"│ Hóa đơn: {transaction.invoice_number}")
    lines.extend([
        f"├─────────────────────────────┤",
        f"│ Tồn trước: {format_number(transaction.stock_before)} {material.unit}",
        f"│ Tồn sau:   {format_number(transaction.stock_after)} {material.unit}",
        f"│ Giá vốn BQ: {format_currency(material.cost_price)}",
        f"└─────────────────────────────┘",
    ])
    return "\n".join(lines)
