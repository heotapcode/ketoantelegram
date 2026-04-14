import json
import logging
import google.generativeai as genai
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from rapidfuzz import process, fuzz

from config import GOOGLE_API_KEY
from database.crud import (
    get_all_materials, search_materials, search_partners,
    get_all_partners
)
from keyboards.inline import confirm_keyboard, main_menu_keyboard, materials_list_keyboard
from utils.formatters import format_currency, format_number

logger = logging.getLogger(__name__)
router = Router()

# Configure Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
else:
    model = None

class ChatAIState(StatesGroup):
    confirm_action = State()
    select_material = State()

CHAT_SYSTEM_PROMPT = """
Bạn là trợ lý ảo điều hành kho. Phân tích câu lệnh của người dùng và trả về JSON.
Các hành động hỗ trợ: 
- IMPORT (Nhập kho)
- EXPORT (Xuất kho)
- SEARCH_STOCK (Xem tồn kho/Tìm kiếm)
- REPORT_PROFIT (Xem lãi lỗ)

Cấu trúc JSON:
{
  "action": "IMPORT/EXPORT/SEARCH_STOCK/REPORT_PROFIT",
  "material_name": "tên vật tư",
  "quantity": 10.5,
  "partner_name": "tên đối tác kinh doanh",
  "price": 50000,
  "is_ambiguous": false
}
Nếu thông tin nào không có, để null. Nếu câu lệnh không rõ ràng, set is_ambiguous: true.
"""

@router.message(F.text & ~F.text.startswith("/"))
async def handle_chat_command(message: Message, state: FSMContext, session: AsyncSession):
    if not model:
        await message.answer("⚠️ Bot chưa cấu hình AI.")
        return

    # 1. Phân tích intent bằng AI
    try:
        response = model.generate_content([CHAT_SYSTEM_PROMPT, message.text])
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        intent = json.loads(text.strip())
    except Exception as e:
        logger.error(f"AI Parse Error: {e}")
        return # Để các handler khác xử lý hoặc bỏ qua

    if intent.get("is_ambiguous") or not intent.get("action"):
        await message.answer("🤔 Xin lỗi, tôi chưa hiểu ý bạn. Bạn có thể nói rõ hơn được không? (VD: Nhập 10 thép, Kiểm tra tồn kho sắt...)")
        return

    # 2. Xử lý tìm kiếm vật tư (Fuzzy Match)
    action = intent["action"]
    mat_name = intent.get("material_name")
    
    selected_material = None
    if mat_name:
        all_mats = await get_all_materials(session)
        names = [m.name for m in all_mats]
        # Lấy 10 kết quả tốt nhất
        matches = process.extract(mat_name, names, scorer=fuzz.partial_ratio, limit=10)
        
        # Nếu có kết quả khớp 100%
        if matches and matches[0][1] == 100:
            selected_material = next(m for m in all_mats if m.name == matches[0][0])
        else:
            # Hiện danh sách lựa chọn
            matched_mats = []
            for m_name, score, _ in matches:
                if score > 50:
                    matched_mats.append(next(m for m in all_mats if m.name == m_name))
            
            if matched_mats:
                await state.update_data(pending_intent=intent)
                await state.set_state(ChatAIState.select_material)
                # Dùng bàn phím danh sách vật tư nhưng đổi prefix
                kb = materials_list_keyboard(matched_mats, action="aisel")
                await message.answer(f"🔍 Tôi tìm thấy một số vật tư giống với '<b>{mat_name}</b>'. Vui lòng chọn:", 
                                   reply_markup=kb, parse_mode="HTML")
                return
            elif action in ["IMPORT", "EXPORT"]:
                await message.answer(f"❌ Không tìm thấy vật tư nào tương tự '<b>{mat_name}</b>'. Bạn hãy kiểm tra lại tên nhé.", parse_mode="HTML")
                return

    # 3. Tổng hợp và yêu cầu xác nhận
    await ask_confirmation(message, state, intent, selected_material, session)

async def ask_confirmation(message: Message, state: FSMContext, intent: dict, material, session):
    action = intent["action"]
    qty = intent.get("quantity")
    price = intent.get("price")
    partner_name = intent.get("partner_name")
    
    text = "🤖 <b>XÁC NHẬN CÂU LỆNH AI</b>\n━━━━━━━━━━━━━━━\n"
    
    if action == "IMPORT":
        text += "📥 <b>Hành động:</b> Nhập kho\n"
    elif action == "EXPORT":
        text += "📤 <b>Hành động:</b> Xuất kho\n"
    elif action == "SEARCH_STOCK":
        text += "🔍 <b>Hành động:</b> Kiểm tra tồn kho\n"
    elif action == "REPORT_PROFIT":
        text += "💰 <b>Hành động:</b> Báo cáo lãi lỗ\n"

    if material:
        text += f"📦 <b>Vật tư:</b> {material.name}\n"
        text += f"🔢 <b>Số lượng:</b> {format_number(qty or 1)} {material.unit}\n"
    
    if partner_name:
        text += f"🏢 <b>Đối tác:</b> {partner_name}\n"
    
    if price:
        text += f"💵 <b>Đơn giá:</b> {format_currency(price)}\n"

    text += "━━━━━━━━━━━━━━━\nBấm nút xác nhận để thực hiện:"
    
    await state.update_data(ai_final_intent=intent, ai_material_id=material.id if material else None)
    await state.set_state(ChatAIState.confirm_action)
    
    # Dùng confirm_keyboard với prefix 'ai_cmd'
    from keyboards.inline import confirm_keyboard
    await message.answer(text, reply_markup=confirm_keyboard("ai_cmd"), parse_mode="HTML")

@router.callback_query(ChatAIState.select_material, F.data.startswith("matsel_aisel_"))
async def handle_ai_material_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    mat_id = int(callback.data.split("_")[-1])
    material = await session.get(get_all_materials.__wrapped__.__func__, mat_id) # Shortcut to get material
    # Re-fetch correctly
    from database.models import Material
    material = await session.get(Material, mat_id)
    
    data = await state.get_data()
    intent = data["pending_intent"]
    
    await callback.message.delete()
    await ask_confirmation(callback.message, state, intent, material, session)
    await callback.answer()

@router.callback_query(ChatAIState.confirm_action, F.data == "ai_cmd_yes")
async def execute_ai_command(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    intent = data["ai_final_intent"]
    mat_id = data.get("ai_material_id")
    action = intent["action"]
    
    try:
        if action == "SEARCH_STOCK":
            # Chuyển hướng sang handler vật tư hoặc hiện kết quả nhanh
            if mat_id:
                from database.models import Material
                m = await session.get(Material, mat_id)
                text = f"📦 <b>Thông tin tồn kho:</b>\n\n<code>{m.material_code}</code> | <b>{m.name}</b>\n"
                text += f"➤ Tồn hiện tại: <b>{format_number(m.current_stock)} {m.unit}</b>\n"
                text += f"➤ Giá vốn: {format_currency(m.cost_price)}"
                await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
            else:
                await callback.message.edit_text("🔍 Bạn muốn tìm vật tư nào? Vui lòng nói rõ tên.", reply_markup=main_menu_keyboard())
        
        elif action == "REPORT_PROFIT":
            # Chuyển hướng sang menu báo cáo hoặc hiện nhanh
            from database.crud import calculate_period_summary
            from datetime import datetime
            summary = await calculate_period_summary(session) # Lấy tổng hợp tất cả
            
            text = (
                f"💰 <b>TỔNG HỢP LÃI LỖ (TẤT CẢ)</b>\n\n"
                f"📥 Nhập kho: <b>{format_currency(summary['total_import'])}</b>\n"
                f"📤 Xuất kho: <b>{format_currency(summary['total_export'])}</b>\n"
                f"🏷️ Giá vốn: {format_currency(summary['total_cogs'])}\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>LÃI GỘP: {format_currency(summary['gross_profit'])}</b>\n"
            )
            await callback.message.edit_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
            
        elif action in ["IMPORT", "EXPORT"]:
            # Gọi trực tiếp CRUD
            from database.crud import create_import_transaction, create_export_transaction
            if not mat_id:
                raise ValueError("Thiếu thông tin vật tư.")
            
            qty = intent.get("quantity", 0)
            if qty <= 0:
                raise ValueError("Số lượng phải lớn hơn 0.")
            
            # Xử lý NCC/KH
            p_id = None
            if intent.get("partner_name"):
                partners = await search_partners(session, intent["partner_name"])
                if partners: p_id = partners[0].id

            if action == "IMPORT":
                await create_import_transaction(session, mat_id, qty, intent.get("price", 0), p_id, user_id=callback.from_user.id)
            else:
                await create_export_transaction(session, mat_id, qty, intent.get("price", 0), p_id, user_id=callback.from_user.id)
            
            await callback.message.edit_text(f"✅ Đã thực hiện <b>{action}</b> thành công!", reply_markup=main_menu_keyboard(), parse_mode="HTML")

    except Exception as e:
        await callback.message.edit_text(f"❌ Lỗi thực thi: {str(e)}", reply_markup=main_menu_keyboard())

    await state.clear()
    await callback.answer()

@router.callback_query(ChatAIState.confirm_action, F.data == "ai_cmd_no")
async def cancel_ai_command(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Đã hủy lệnh.", reply_markup=main_menu_keyboard())
    await callback.answer()
