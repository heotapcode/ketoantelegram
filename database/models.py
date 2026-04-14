"""
Database Models - Tất cả bảng dữ liệu
"""
from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, BigInteger, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.engine import Base


# ============================================================
# USERS - Quản lý người dùng Telegram
# ============================================================
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="VIEWER")  # ADMIN, ACCOUNTANT, VIEWER
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    transactions: Mapped[list["InventoryTransaction"]] = relationship(back_populates="created_by_user")

    def __repr__(self):
        return f"<User {self.full_name} ({self.role})>"


# ============================================================
# CATEGORIES - Nhóm vật tư (NVL, HH, TP, CCDC...)
# ============================================================
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)        # VD: NVL, HH
    name: Mapped[str] = mapped_column(String(100))                     # VD: Nguyên vật liệu
    prefix: Mapped[str] = mapped_column(String(10))                    # Prefix cho mã vật tư
    account_number: Mapped[str | None] = mapped_column(String(10), nullable=True)  # TK kế toán
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    materials: Mapped[list["Material"]] = relationship(back_populates="category")

    def __repr__(self):
        return f"<Category {self.code}: {self.name}>"


# ============================================================
# MATERIALS - Danh mục vật tư
# ============================================================
class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"))
    unit: Mapped[str] = mapped_column(String(20))                     # Đơn vị tính
    cost_price: Mapped[float] = mapped_column(Float, default=0)       # Giá vốn (bình quân)
    selling_price: Mapped[float] = mapped_column(Float, default=0)    # Giá bán
    current_stock: Mapped[float] = mapped_column(Float, default=0)    # Tồn kho hiện tại
    min_stock: Mapped[float] = mapped_column(Float, default=0)        # Tồn kho tối thiểu
    total_stock_value: Mapped[float] = mapped_column(Float, default=0) # Tổng giá trị tồn kho
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    category: Mapped["Category"] = relationship(back_populates="materials")
    transactions: Mapped[list["InventoryTransaction"]] = relationship(back_populates="material")
    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="material")

    # Index
    __table_args__ = (
        Index("idx_material_category", "category_id"),
    )

    def __repr__(self):
        return f"<Material {self.material_code}: {self.name}>"


# ============================================================
# PARTNERS - Nhà cung cấp & Khách hàng
# ============================================================
class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    partner_type: Mapped[str] = mapped_column(String(20))             # SUPPLIER / CUSTOMER
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    transactions: Mapped[list["InventoryTransaction"]] = relationship(back_populates="partner")

    def __repr__(self):
        return f"<Partner {self.code}: {self.name} ({self.partner_type})>"


# ============================================================
# INVENTORY_TRANSACTIONS - Phiếu xuất nhập kho
# ============================================================
class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"))
    transaction_type: Mapped[str] = mapped_column(String(10))          # IMPORT / EXPORT
    quantity: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    partner_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("partners.id"), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_before: Mapped[float] = mapped_column(Float, default=0)     # Tồn trước giao dịch
    stock_after: Mapped[float] = mapped_column(Float, default=0)      # Tồn sau giao dịch
    cost_price_at_time: Mapped[float] = mapped_column(Float, default=0)  # Giá vốn tại thời điểm
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    material: Mapped["Material"] = relationship(back_populates="transactions")
    partner: Mapped["Partner | None"] = relationship(back_populates="transactions")
    created_by_user: Mapped["User | None"] = relationship(back_populates="transactions")

    # Indexes
    __table_args__ = (
        Index("idx_trans_material", "material_id"),
        Index("idx_trans_type", "transaction_type"),
        Index("idx_trans_date", "created_at"),
    )

    def __repr__(self):
        return f"<Transaction {self.transaction_type} #{self.id}>"


# ============================================================
# PRICE_HISTORY - Lịch sử thay đổi giá
# ============================================================
class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"))
    old_cost: Mapped[float] = mapped_column(Float)
    new_cost: Mapped[float] = mapped_column(Float)
    old_selling: Mapped[float] = mapped_column(Float, default=0)
    new_selling: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relationships
    material: Mapped["Material"] = relationship(back_populates="price_history")

    def __repr__(self):
        return f"<PriceHistory material={self.material_id}>"
