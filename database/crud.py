"""
CRUD Operations - Tất cả thao tác database
"""
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import (
    User, Category, Material, Partner,
    InventoryTransaction, PriceHistory
)


# ============================================================
# USER CRUD
# ============================================================
async def get_or_create_user(session: AsyncSession, telegram_id: int,
                             full_name: str, username: str = None) -> User:
    """Lấy user hoặc tạo mới nếu chưa có"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            role="VIEWER",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def update_user_role(session: AsyncSession, telegram_id: int, new_role: str) -> User | None:
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.role = new_role
        await session.commit()
    return user


async def get_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.is_active == True))
    return list(result.scalars().all())


# ============================================================
# CATEGORY CRUD
# ============================================================
async def get_all_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(
        select(Category).where(Category.is_active == True).order_by(Category.code)
    )
    return list(result.scalars().all())


async def get_category_by_code(session: AsyncSession, code: str) -> Category | None:
    result = await session.execute(
        select(Category).where(Category.code == code)
    )
    return result.scalar_one_or_none()


async def create_default_categories(session: AsyncSession):
    """Tạo các nhóm vật tư mặc định"""
    defaults = [
        ("NVL", "Nguyên vật liệu", "NVL", "152"),
        ("HH", "Hàng hóa", "HH", "156"),
        ("TP", "Thành phẩm", "TP", "155"),
        ("CCDC", "Công cụ dụng cụ", "CCDC", "153"),
        ("PHT", "Phụ tùng thay thế", "PHT", "1534"),
    ]

    for code, name, prefix, account in defaults:
        existing = await get_category_by_code(session, code)
        if not existing:
            cat = Category(
                code=code, name=name,
                prefix=prefix, account_number=account
            )
            session.add(cat)

    await session.commit()


# ============================================================
# MATERIAL CRUD
# ============================================================
async def generate_material_code(session: AsyncSession, category_code: str,
                                  material_name: str) -> str:
    """
    Tự động sinh mã vật tư theo format: [NHÓM]-[LOẠI]-[SỐ THỨ TỰ]
    VD: NVL-THEP-0001
    """
    import unicodedata
    import re

    # Bỏ dấu tiếng Việt và lấy keyword chính
    name_normalized = unicodedata.normalize('NFD', material_name)
    name_ascii = ''.join(
        c for c in name_normalized
        if unicodedata.category(c) != 'Mn'
    )
    # Lấy từ đầu tiên có ý nghĩa (>2 ký tự), viết hoa
    words = re.findall(r'[a-zA-Z]{2,}', name_ascii)
    type_code = words[0].upper()[:4] if words else "ITEM"

    # Đếm số vật tư hiện có cùng prefix
    prefix = f"{category_code}-{type_code}-"
    result = await session.execute(
        select(func.count(Material.id)).where(
            Material.material_code.like(f"{prefix}%")
        )
    )
    count = result.scalar() or 0
    seq = count + 1

    return f"{prefix}{seq:04d}"


async def create_material(session: AsyncSession, name: str, category_code: str,
                           unit: str, cost_price: float = 0,
                           selling_price: float = 0, min_stock: float = 0,
                           description: str = None) -> Material:
    """Tạo vật tư mới với mã tự động"""
    category = await get_category_by_code(session, category_code)
    if not category:
        raise ValueError(f"Không tìm thấy nhóm vật tư: {category_code}")

    material_code = await generate_material_code(session, category_code, name)

    material = Material(
        material_code=material_code,
        name=name,
        category_id=category.id,
        unit=unit,
        cost_price=cost_price,
        selling_price=selling_price,
        min_stock=min_stock,
        description=description,
    )
    session.add(material)
    await session.commit()
    await session.refresh(material)
    return material


async def get_material_by_code(session: AsyncSession, code: str) -> Material | None:
    result = await session.execute(
        select(Material).where(Material.material_code == code)
    )
    return result.scalar_one_or_none()


async def search_materials(session: AsyncSession, keyword: str) -> list[Material]:
    """Tìm kiếm vật tư theo tên hoặc mã"""
    keyword_pattern = f"%{keyword}%"
    result = await session.execute(
        select(Material).where(
            and_(
                Material.is_active == True,
                or_(
                    Material.name.ilike(keyword_pattern),
                    Material.material_code.ilike(keyword_pattern),
                )
            )
        ).order_by(Material.material_code)
    )
    return list(result.scalars().all())


async def get_all_materials(session: AsyncSession) -> list[Material]:
    result = await session.execute(
        select(Material).where(Material.is_active == True).order_by(Material.material_code)
    )
    return list(result.scalars().all())


async def get_low_stock_materials(session: AsyncSession) -> list[Material]:
    """Lấy danh sách vật tư có tồn kho dưới mức tối thiểu"""
    result = await session.execute(
        select(Material).where(
            and_(
                Material.is_active == True,
                Material.min_stock > 0,
                Material.current_stock < Material.min_stock,
            )
        ).order_by(Material.material_code)
    )
    return list(result.scalars().all())


async def update_material(session: AsyncSession, material_id: int, **kwargs) -> Material | None:
    result = await session.execute(
        select(Material).where(Material.id == material_id)
    )
    material = result.scalar_one_or_none()
    if material:
        for key, value in kwargs.items():
            if hasattr(material, key):
                setattr(material, key, value)
        await session.commit()
        await session.refresh(material)
    return material


async def delete_material(session: AsyncSession, material_id: int) -> bool:
    """Soft delete vật tư"""
    material = await session.get(Material, material_id)
    if material:
        material.is_active = False
        await session.commit()
        return True
    return False


# ============================================================
# PARTNER CRUD
# ============================================================
async def generate_partner_code(session: AsyncSession, partner_type: str) -> str:
    """Sinh mã đối tác: NCC-001 hoặc KH-001"""
    prefix = "NCC" if partner_type == "SUPPLIER" else "KH"
    result = await session.execute(
        select(func.count(Partner.id)).where(
            Partner.code.like(f"{prefix}-%")
        )
    )
    count = result.scalar() or 0
    return f"{prefix}-{count + 1:03d}"


async def create_partner(session: AsyncSession, name: str, partner_type: str,
                          phone: str = None, address: str = None,
                          tax_code: str = None) -> Partner:
    code = await generate_partner_code(session, partner_type)
    partner = Partner(
        code=code, name=name, partner_type=partner_type,
        phone=phone, address=address, tax_code=tax_code,
    )
    session.add(partner)
    await session.commit()
    await session.refresh(partner)
    return partner


async def get_partners_by_type(session: AsyncSession, partner_type: str) -> list[Partner]:
    result = await session.execute(
        select(Partner).where(
            and_(Partner.partner_type == partner_type, Partner.is_active == True)
        ).order_by(Partner.code)
    )
    return list(result.scalars().all())


async def get_all_partners(session: AsyncSession) -> list[Partner]:
    result = await session.execute(
        select(Partner).where(Partner.is_active == True).order_by(Partner.code)
    )
    return list(result.scalars().all())


async def search_partners(session: AsyncSession, keyword: str) -> list[Partner]:
    keyword_pattern = f"%{keyword}%"
    result = await session.execute(
        select(Partner).where(
            and_(
                Partner.is_active == True,
                or_(
                    Partner.name.ilike(keyword_pattern),
                    Partner.code.ilike(keyword_pattern),
                )
            )
        ).order_by(Partner.code)
    )
    return list(result.scalars().all())


# ============================================================
# INVENTORY TRANSACTION CRUD
# ============================================================
async def create_import_transaction(session: AsyncSession, material_id: int,
                                     quantity: float, unit_price: float,
                                     partner_id: int = None,
                                     invoice_number: str = None,
                                     note: str = None,
                                     user_id: int = None) -> InventoryTransaction:
    """
    Nhập kho - Cập nhật giá vốn bình quân gia quyền
    Giá vốn mới = (Tồn cũ × Giá vốn cũ + SL nhập × Đơn giá nhập) / (Tồn cũ + SL nhập)
    """
    material = await session.get(Material, material_id)
    if not material:
        raise ValueError("Không tìm thấy vật tư")

    stock_before = material.current_stock
    total_before = material.total_stock_value

    # Tính giá vốn bình quân gia quyền
    total_import = quantity * unit_price
    new_total_value = total_before + total_import
    new_stock = stock_before + quantity
    new_cost_price = new_total_value / new_stock if new_stock > 0 else unit_price

    # Lưu lịch sử giá nếu thay đổi
    if material.cost_price != new_cost_price:
        price_log = PriceHistory(
            material_id=material.id,
            old_cost=material.cost_price,
            new_cost=new_cost_price,
            reason=f"Nhập kho {quantity} {material.unit} @ {unit_price:,.0f}₫"
        )
        session.add(price_log)

    # Cập nhật vật tư
    material.current_stock = new_stock
    material.cost_price = round(new_cost_price, 2)
    material.total_stock_value = round(new_total_value, 2)

    # Tạo phiếu nhập
    transaction = InventoryTransaction(
        material_id=material_id,
        transaction_type="IMPORT",
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_import,
        partner_id=partner_id,
        invoice_number=invoice_number,
        note=note,
        stock_before=stock_before,
        stock_after=new_stock,
        cost_price_at_time=new_cost_price,
        created_by=user_id,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def create_export_transaction(session: AsyncSession, material_id: int,
                                     quantity: float, unit_price: float,
                                     partner_id: int = None,
                                     invoice_number: str = None,
                                     note: str = None,
                                     user_id: int = None) -> InventoryTransaction:
    """
    Xuất kho - Kiểm tra tồn kho và tính giá vốn xuất
    Giá vốn xuất = giá bình quân gia quyền hiện tại
    """
    material = await session.get(Material, material_id)
    if not material:
        raise ValueError("Không tìm thấy vật tư")

    if material.current_stock < quantity:
        raise ValueError(
            f"Tồn kho không đủ! Hiện có: {material.current_stock:,.1f} {material.unit}, "
            f"yêu cầu xuất: {quantity:,.1f} {material.unit}"
        )

    stock_before = material.current_stock
    total_export = quantity * unit_price
    cost_of_goods = quantity * material.cost_price  # Giá vốn hàng xuất

    # Cập nhật tồn kho
    material.current_stock = stock_before - quantity
    material.total_stock_value = material.current_stock * material.cost_price

    # Tạo phiếu xuất
    transaction = InventoryTransaction(
        material_id=material_id,
        transaction_type="EXPORT",
        quantity=quantity,
        unit_price=unit_price,
        total_amount=total_export,
        partner_id=partner_id,
        invoice_number=invoice_number,
        note=note,
        stock_before=stock_before,
        stock_after=material.current_stock,
        cost_price_at_time=material.cost_price,
        created_by=user_id,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def get_transactions(session: AsyncSession, material_id: int = None,
                            trans_type: str = None,
                            start_date: datetime = None,
                            end_date: datetime = None,
                            limit: int = 50) -> list[InventoryTransaction]:
    """Lấy danh sách giao dịch với bộ lọc"""
    query = select(InventoryTransaction)
    conditions = []

    if material_id:
        conditions.append(InventoryTransaction.material_id == material_id)
    if trans_type:
        conditions.append(InventoryTransaction.transaction_type == trans_type)
    if start_date:
        conditions.append(InventoryTransaction.created_at >= start_date)
    if end_date:
        conditions.append(InventoryTransaction.created_at <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(InventoryTransaction.created_at.desc()).limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


# ============================================================
# FINANCE / LÃI LỖ
# ============================================================
async def calculate_profit_by_material(session: AsyncSession,
                                        start_date: datetime = None,
                                        end_date: datetime = None) -> list[dict]:
    """Tính lãi lỗ theo từng vật tư"""
    materials = await get_all_materials(session)
    results = []

    for material in materials:
        # Lấy tổng xuất kho (doanh thu)
        export_query = select(
            func.sum(InventoryTransaction.total_amount),
            func.sum(InventoryTransaction.quantity),
        ).where(
            and_(
                InventoryTransaction.material_id == material.id,
                InventoryTransaction.transaction_type == "EXPORT",
            )
        )
        if start_date:
            export_query = export_query.where(InventoryTransaction.created_at >= start_date)
        if end_date:
            export_query = export_query.where(InventoryTransaction.created_at <= end_date)

        export_result = await session.execute(export_query)
        export_row = export_result.one()
        revenue = export_row[0] or 0
        export_qty = export_row[1] or 0

        # Tính giá vốn hàng xuất (dùng giá vốn bình quân tại thời điểm)
        cost_query = select(
            func.sum(InventoryTransaction.quantity * InventoryTransaction.cost_price_at_time),
        ).where(
            and_(
                InventoryTransaction.material_id == material.id,
                InventoryTransaction.transaction_type == "EXPORT",
            )
        )
        if start_date:
            cost_query = cost_query.where(InventoryTransaction.created_at >= start_date)
        if end_date:
            cost_query = cost_query.where(InventoryTransaction.created_at <= end_date)

        cost_result = await session.execute(cost_query)
        cogs = cost_result.scalar() or 0  # Cost of Goods Sold

        profit = revenue - cogs
        margin = (profit / revenue * 100) if revenue > 0 else 0

        if export_qty > 0:  # Chỉ hiện những vật tư có giao dịch xuất
            results.append({
                "material": material,
                "revenue": revenue,
                "cogs": cogs,
                "profit": profit,
                "margin": margin,
                "export_qty": export_qty,
            })

    # Sắp xếp theo lãi lỗ
    results.sort(key=lambda x: x["profit"], reverse=True)
    return results


async def calculate_period_summary(session: AsyncSession,
                                    start_date: datetime = None,
                                    end_date: datetime = None) -> dict:
    """Tổng hợp lãi lỗ theo kỳ"""
    # Tổng nhập kho
    import_query = select(
        func.sum(InventoryTransaction.total_amount),
        func.count(InventoryTransaction.id),
    ).where(InventoryTransaction.transaction_type == "IMPORT")

    if start_date:
        import_query = import_query.where(InventoryTransaction.created_at >= start_date)
    if end_date:
        import_query = import_query.where(InventoryTransaction.created_at <= end_date)

    import_result = await session.execute(import_query)
    import_row = import_result.one()

    # Tổng xuất kho
    export_query = select(
        func.sum(InventoryTransaction.total_amount),
        func.count(InventoryTransaction.id),
    ).where(InventoryTransaction.transaction_type == "EXPORT")

    if start_date:
        export_query = export_query.where(InventoryTransaction.created_at >= start_date)
    if end_date:
        export_query = export_query.where(InventoryTransaction.created_at <= end_date)

    export_result = await session.execute(export_query)
    export_row = export_result.one()

    total_import = import_row[0] or 0
    total_export = export_row[0] or 0

    # Tính giá vốn hàng xuất
    cogs_query = select(
        func.sum(InventoryTransaction.quantity * InventoryTransaction.cost_price_at_time),
    ).where(InventoryTransaction.transaction_type == "EXPORT")

    if start_date:
        cogs_query = cogs_query.where(InventoryTransaction.created_at >= start_date)
    if end_date:
        cogs_query = cogs_query.where(InventoryTransaction.created_at <= end_date)

    cogs_result = await session.execute(cogs_query)
    total_cogs = cogs_result.scalar() or 0

    gross_profit = total_export - total_cogs
    margin = (gross_profit / total_export * 100) if total_export > 0 else 0

    return {
        "total_import": total_import,
        "total_export": total_export,
        "total_cogs": total_cogs,
        "gross_profit": gross_profit,
        "margin": margin,
        "import_count": import_row[1] or 0,
        "export_count": export_row[1] or 0,
    }
