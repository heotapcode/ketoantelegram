"""
Cấu hình ứng dụng - Đọc từ file .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./accounting.db")

# Admin
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Cấu hình mã vật tư
MATERIAL_CODE_PREFIXES = {
    "NVL": "Nguyên vật liệu",      # TK 152
    "HH": "Hàng hóa",              # TK 156
    "TP": "Thành phẩm",            # TK 155
    "CCDC": "Công cụ dụng cụ",     # TK 153
    "PHT": "Phụ tùng thay thế",    # TK 1534
}

# Đơn vị tính phổ biến
COMMON_UNITS = [
    "Cái", "Chiếc", "Bộ", "Hộp", "Thùng",
    "KG", "Gram", "Tấn",
    "Mét", "m²", "m³",
    "Lít", "Chai", "Can",
    "Cuộn", "Tấm", "Thanh",
]

# Roles
ROLE_ADMIN = "ADMIN"
ROLE_ACCOUNTANT = "ACCOUNTANT"
ROLE_VIEWER = "VIEWER"
