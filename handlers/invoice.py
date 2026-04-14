import os
import json
import logging
import google.generativeai as genai
from typing import List, Dict, Any
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, Document, PhotoSize, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from rapidfuzz import process, fuzz

from config import GOOGLE_API_KEY
from database.crud import (
    get_all_materials, create_material, get_category_by_code,
    create_import_transaction, search_partners, create_partner,
    get_partners_by_type
)
from keyboards.inline import confirm_keyboard, main_menu_keyboard
from utils.formatters import format_currency, format_number

logger = logging.getLogger(__name__)
router = Router()

# Cấu hình Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

class InvoiceState(StatesGroup):
    confirm_invoice = State()

# Prompt cho AI
SYSTEM_PROMPT = """
Bạn là một trợ lý kế toán chuyên nghiệp. Nhiệm vụ của bạn là trích xuất thông tin từ hóa đơn (invoice) hoặc phiếu nhập kho. 
Vui lòng trả về kết quả dưới dạng JSON với cấu trúc sau:
{
  "vendor": "Tên nhà cung cấp",
  "invoice_no": "Số hóa đơn (nếu có)",
  "items": [
    {
      "name": "Tên mặt hàng",
      "quantity": 10.5,
      "unit": "ĐVT (cái, kg, m...)",
      "price": 50000
    }
  ]
}
Chú ý:
- Nếu không tìm thấy tên nhà cung cấp, để null.
- Số lượng và đơn giá phải là số.
- Tên mặt hàng cần chuẩn hóa (viết hoa chữ cái đầu, bỏ các ký hiệu thừa).
"""

@router.message(F.photo | (F.document.mime_type.startswith("image/")) | (F.document.mime_type == "application/pdf"))
async def handle_invoice_upload(message: Message, state: FSMContext, bot):
    if not GOOGLE_API_KEY:
        await message.answer("⚠️ Bot chưa được cấu hình API Key cho Gemini. Vui lòng liên hệ Admin.")
        return

    wait_msg = await message.answer("🔍 Đang xử lý hóa đơn, vui lòng đợi giây lát...")

    try:
        # Download file
        file_id = ""
        if message.photo:
            file_id = message.photo[-1].file_id
        else:
            file_id = message.document.file_id
        
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Download sang memory
        from io import BytesIO
        file_data = BytesIO()
        await bot.download_file(file_path, file_data)
        file_bytes = file_data.getvalue()

        # Gọi Gemini
        contents = [
            SYSTEM_PROMPT,
            {"mime_type": message.document.mime_type if message.document else "image/jpeg", "data": file_bytes}
        ]
        
        response = model.generate_content(contents)
        
        # Trích xuất JSON từ phản hồi của Gemini
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        
        data = json.loads(text.strip())
        
        if not data.get("items"):
            await wait_msg.edit_text("❌ Không thể trích xuất các mặt hàng từ tài liệu này.")
            return

        await state.update_data(invoice_data=data)
        
        # Hiển thị tóm tắt và xác nhận
        text = f"📄 <b>KẾT QUẢ NHẬN DIỆN HÓA ĐƠN</b>\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"🏢 NCC: <b>{data.get('vendor', 'Không rõ')}</b>\n"
        text += f"🧾 Số HĐ: <b>{data.get('invoice_no', 'N/A')}</b>\n\n"
        
        total_amount = 0
        for i, item in enumerate(data['items'], 1):
            amount = item['quantity'] * item['price']
            total_amount += amount
            text += f"{i}. <b>{item['name']}</b>\n"
            text += f"   {format_number(item['quantity'])} {item['unit']} x {format_currency(item['price'])} = {format_currency(amount)}\n"
        
        text += f"━━━━━━━━━━━━━━━━━━━━\n"
        text += f"💰 <b>TỔNG CỘNG: {format_currency(total_amount)}</b>\n\n"
        text += "Hệ thống sẽ tự động gán mã vật tư và nhà cung cấp. Xác nhận hạch toán nhập kho?"

        await state.set_state(InvoiceState.confirm_invoice)
        await wait_msg.edit_text(text, reply_markup=confirm_keyboard("invoice"), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error processing invoice: {str(e)}")
        await wait_msg.edit_text(f"❌ Có lỗi xảy ra khi xử lý hóa đơn: {str(e)}")

@router.callback_query(InvoiceState.confirm_invoice, F.data == "invoice_yes")
async def confirm_invoice_process(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    invoice_data = data.get("invoice_data")
    await state.clear()

    if not invoice_data:
        await callback.answer("Dữ liệu không còn hiệu lực.")
        return

    await callback.message.edit_text("⏳ Đang xử lý hạch toán kho và vật tư...")

    try:
        # 1. Xử lý Đối tác (NCC)
        vendor_name = invoice_data.get("vendor")
        partner_id = None
        if vendor_name:
            partners = await search_partners(session, vendor_name)
            if partners:
                partner_id = partners[0].id # Lấy cái đầu tiên gần đúng nhất
            else:
                # Tạo NCC mới
                new_partner = await create_partner(session, vendor_name, "SUPPLIER")
                partner_id = new_partner.id

        # 2. Xử lý Vật tư và Nhập kho
        all_materials = await get_all_materials(session)
        material_names = [m.name for m in all_materials]
        
        processed_count = 0
        for item in invoice_data["items"]:
            # Tìm vật tư gần đúng
            match = None
            if material_names:
                best_match = process.extractOne(item["name"], material_names, scorer=fuzz.token_sort_ratio)
                if best_match and best_match[1] > 80: # Độ tương đồng > 80%
                    match = next(m for m in all_materials if m.name == best_match[0])
            
            # Nếu không tìm thấy, tạo vật tư mới
            if not match:
                # Mặc định gán vào nhóm HH (Hàng hóa) hoặc tự đoán
                category_code = "HH" 
                match = await create_material(
                    session, 
                    name=item["name"], 
                    category_code=category_code, 
                    unit=item["unit"],
                    cost_price=item["price"]
                )
            
            # Thực hiện nhập kho
            await create_import_transaction(
                session,
                material_id=match.id,
                quantity=item["quantity"],
                unit_price=item["price"],
                partner_id=partner_id,
                invoice_number=invoice_data.get("invoice_no"),
                note="Nhập kho tự động từ hóa đơn AI",
                user_id=callback.from_user.id
            )
            processed_count += 1

        await callback.message.edit_text(
            f"✅ <b>HẠCH TOÁN THÀNH CÔNG!</b>\n\n"
            f"📍 Đã xử lý <b>{processed_count}</b> mặt hàng.\n"
            f"🏢 Nhà cung cấp: <b>{vendor_name or 'N/A'}</b>\n"
            f"📦 Kho đã được cập nhật.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error confirming invoice: {str(e)}")
        await callback.message.edit_text(f"❌ Lỗi khi hạch toán: {str(e)}", reply_markup=main_menu_keyboard())
    
    await callback.answer()

@router.callback_query(InvoiceState.confirm_invoice, F.data == "invoice_no")
async def cancel_invoice_process(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Đã hủy xử lý hóa đơn.", reply_markup=main_menu_keyboard())
    await callback.answer()
