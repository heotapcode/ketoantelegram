"""
FSM States - Quản lý trạng thái multi-step flows
"""
from aiogram.fsm.state import State, StatesGroup


class AddMaterialForm(StatesGroup):
    """Flow: Thêm vật tư mới"""
    name = State()          # Nhập tên vật tư
    category = State()      # Chọn nhóm
    unit = State()          # Chọn/nhập đơn vị tính
    custom_unit = State()   # Nhập đơn vị tùy chỉnh
    cost_price = State()    # Nhập giá vốn
    selling_price = State() # Nhập giá bán
    min_stock = State()     # Nhập tồn kho tối thiểu
    confirm = State()       # Xác nhận


class ImportForm(StatesGroup):
    """Flow: Nhập kho"""
    search = State()        # Tìm vật tư
    select = State()        # Chọn vật tư
    quantity = State()      # Nhập số lượng
    unit_price = State()    # Nhập đơn giá
    partner = State()       # Chọn NCC
    invoice = State()       # Nhập số hóa đơn
    confirm = State()       # Xác nhận


class ExportForm(StatesGroup):
    """Flow: Xuất kho"""
    search = State()        # Tìm vật tư
    select = State()        # Chọn vật tư
    quantity = State()      # Nhập số lượng
    unit_price = State()    # Nhập đơn giá bán
    partner = State()       # Chọn KH
    invoice = State()       # Nhập số hóa đơn
    confirm = State()       # Xác nhận


class AddPartnerForm(StatesGroup):
    """Flow: Thêm đối tác"""
    name = State()          # Nhập tên
    phone = State()         # Nhập SĐT
    address = State()       # Nhập địa chỉ
    confirm = State()       # Xác nhận


class SearchMaterialForm(StatesGroup):
    """Flow: Tìm kiếm vật tư"""
    keyword = State()       # Nhập từ khóa
