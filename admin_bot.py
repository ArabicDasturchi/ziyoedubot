import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from dotenv import load_dotenv
import pandas as pd
import database as db

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("ADMIN_BOT_TOKEN"))
dp = Dispatcher()

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

class AdminStates(StatesGroup):
    waiting_test_title = State()
    waiting_test_type = State()
    waiting_test_content = State()
    waiting_test_keys_mode = State()
    waiting_test_keys_text = State()
    waiting_test_keys_interactive = State()
    waiting_broadcast_text = State()
    waiting_broadcast_photo = State()
    waiting_broadcast_button = State()
    waiting_setting_value = State()
    waiting_sub_admin_id = State()
    waiting_sub_admin_name = State()

def get_super_admin_menu():
    """Asosiy admin uchun to'liq menyu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi Test Qo'shish", callback_data="add_test")],
        [InlineKeyboardButton(text="🗂 Testlar Ro'yxati", callback_data="list_tests")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="search_user"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="st_global")],
        [InlineKeyboardButton(text="📢 Reklama Tarqatish", callback_data="st_broadcast")],
        [InlineKeyboardButton(text="👨‍🏫 Sub-Adminlar", callback_data="manage_subadmins"),
         InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="st_settings")],
    ])

def get_sub_admin_menu():
    """Sub-admin (o'qituvchi) uchun cheklangan menyu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi Test Qo'shish", callback_data="add_test")],
        [InlineKeyboardButton(text="🗂 Testlar Ro'yxati", callback_data="list_tests")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="search_user"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="st_global")],
    ])

async def get_user_menu(user_id):
    """Foydalanuvchi darajasiga qarab menyuni qaytaradi"""
    if user_id == ADMIN_ID:
        return get_super_admin_menu()
    return get_sub_admin_menu()

@dp.message(Command("start"))
async def start_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid != ADMIN_ID and not await db.is_sub_admin(uid):
        return
    await state.clear()
    menu = await get_user_menu(uid)
    prefix = "🔑 <b>Asosiy Admin Panel</b>" if uid == ADMIN_ID else "👨‍🏫 <b>O'qituvchi Panel</b>"
    await message.answer(prefix, reply_markup=menu, parse_mode="HTML")

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if uid != ADMIN_ID and not await db.is_sub_admin(uid):
        return
    await state.clear()
    menu = await get_user_menu(uid)
    prefix = "🔑 <b>Asosiy Admin Panel</b>" if uid == ADMIN_ID else "👨‍🏫 <b>O'qituvchi Panel</b>"
    await callback.message.edit_text(prefix, reply_markup=menu, parse_mode="HTML")

# --- TEST QO'SHISH (Super admin ham, Sub-admin ham qo'sha oladi) ---
@dp.callback_query(F.data == "add_test")
async def start_add_test(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if uid != ADMIN_ID and not await db.is_sub_admin(uid):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_test_title)
    await callback.message.edit_text("📄 <b>Yangi test nomini kiriting:</b>", parse_mode="HTML")

@dp.message(AdminStates.waiting_test_title)
async def process_test_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 PDF Fayl", callback_data="type_pdf")],
        [InlineKeyboardButton(text="📸 Rasm", callback_data="type_image")],
        [InlineKeyboardButton(text="✍️ Matn", callback_data="type_text")]
    ])
    await message.answer("📁 <b>Test formatini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_test_type)

@dp.callback_query(F.data.startswith("type_"))
async def process_test_type(callback: CallbackQuery, state: FSMContext):
    t_type = callback.data.split("_")[1]
    await state.update_data(t_type=t_type)
    prompts = {"pdf": "📎 <b>PDF yuboring:</b>", "image": "📸 <b>Rasm yuboring:</b>", "text": "✍️ <b>Matn yozing:</b>"}
    await callback.message.edit_text(prompts[t_type], parse_mode="HTML")
    await state.set_state(AdminStates.waiting_test_content)

@dp.message(AdminStates.waiting_test_content)
async def process_test_content(message: Message, state: FSMContext):
    data = await state.get_data(); t_type = data['t_type']; content = None
    
    # Avval Admin botdan kelgan file_id yoki matnni olamiz
    if t_type == "pdf":
        if message.document: content = message.document.file_id
        else: await message.answer("⚠️ Iltimos, PDF fayl yuboring!"); return
    elif t_type == "image":
        if message.photo: content = message.photo[-1].file_id
        else: await message.answer("⚠️ Iltimos, rasm yuboring!"); return
    elif t_type == "text":
        if message.text: content = message.text
        else: await message.answer("⚠️ Iltimos, matn yuboring!"); return

    # Agar bu fayl bo'lsa (PDF yoki Rasm), uni USER BOT orqali qayta yuklab, 
    # unga mos keladigan file_id ni olishimiz shart!
    if t_type in ["pdf", "image"]:
        u_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
        temp_path = f"target_{t_type}.{'pdf' if t_type=='pdf' else 'jpg'}"
        try:
            # 1. Admin bot orqali faylni yuklab olamiz
            file_info = await bot.get_file(content)
            await bot.download_file(file_info.file_path, temp_path)
            
            # 2. User bot orqali adminga qayta yuboramiz (va yangi file_id olamiz)
            from aiogram.types import FSInputFile
            input_file = FSInputFile(temp_path)
            
            if t_type == "pdf":
                msg = await u_bot.send_document(ADMIN_ID, input_file)
                content = msg.document.file_id
            else: # image
                msg = await u_bot.send_photo(ADMIN_ID, input_file)
                content = msg.photo[-1].file_id
            
            # Botni yopamiz (bu file handle larni bo'shatadi)
            await u_bot.session.close()
            
            # 3. Vaqtinchalik faylni o'chiramiz (biroz kutib, sistemaga beramiz)
            if os.path.exists(temp_path):
                import time
                for _ in range(3): # Uch marta urinib ko'ramiz
                    try: os.remove(temp_path); break
                    except: time.sleep(0.5)
            
        except Exception as e:
            err_msg = str(e)
            if "Forbidden: bot was blocked by the user" in err_msg:
                await message.answer("⚠️ <b>XATOLIK:</b> Men (User Bot) sizga fayl yubora olmayapman.\n\nIltimos, o'quvchilar botiga (@ZiyoChashmasibot) kirib <b>/start</b> bosing va qaytadan urinib ko'ring!")
            else:
                logging.error(f"User botga yuklashda xato: {e}")
                await message.answer(f"❌ Faylni User Botga o'tkazishda xato: {e}")
            
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
            await u_bot.session.close()
            return
    
    await state.update_data(content=content, keys_dict={}, keys_str="")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Belgilash (Interaktiv)", callback_data="key_mode_mark")],
        [InlineKeyboardButton(text="⌨️ Matn ko'rinishida yozish", callback_data="key_mode_text")]
    ])
    await message.answer("🔑 <b>Javoblar kalitini kiritish:</b>\n\nIstalgan usuldan foydalaning. Ikkala usul ham **sinxron** ishlaydi: interaktivda belgilaganlaringiz matnga, matnda yozganlaringiz interaktivga avtomatik o'tadi.", reply_markup=kb, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_test_keys_mode)

async def show_keys_marking(message, q_num, keys_dict):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data=f"adm_ans_{q_num}_a"),
         InlineKeyboardButton(text="B", callback_data=f"adm_ans_{q_num}_b"),
         InlineKeyboardButton(text="C", callback_data=f"adm_ans_{q_num}_c"),
         InlineKeyboardButton(text="D", callback_data=f"adm_ans_{q_num}_d")],
        [InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"adm_move_{q_num-1}"),
         InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"adm_move_{q_num+1}")],
        [InlineKeyboardButton(text="⌨️ Matnga o'tish (Sinxron)", callback_data="key_mode_text")],
        [InlineKeyboardButton(text="✅ Saqlash", callback_data="adm_finish_keys")]
    ])
    sel = keys_dict.get(q_num, "Ø").upper()
    keys_preview = "".join([f"{k}{v}" for k, v in sorted(keys_dict.items())])
    text = f"🔑 <b>Interaktiv belgilash:</b>\n\nSavol: <b>{q_num}</b>\nTanlangan: <b>{sel}</b>\n\nHozirgi kalitlar: <code>{keys_preview or '...'}</code>"
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e): logging.error(f"Edit error: {e}")

@dp.callback_query(F.data == "key_mode_mark")
async def key_mode_mark(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    k_dict = data.get("keys_dict", {})
    await show_keys_marking(callback.message, max(1, len(k_dict) + 1 if k_dict else 1), k_dict)
    await state.set_state(AdminStates.waiting_test_keys_interactive)
    try: await callback.answer()
    except: pass


@dp.callback_query(F.data == "key_mode_text")
async def key_mode_text(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Interaktivdagi ma'lumotni matnga aylantiramiz
    k_dict = data.get("keys_dict", {})
    current_keys = "".join([f"{k}{v}" for k, v in sorted(k_dict.items())])
    
    await state.set_state(AdminStates.waiting_test_keys_text)
    await callback.message.edit_text(
        f"✍️ <b>Matn ko'rinishida kiriting:</b>\n\nJoriy holat: <code>{current_keys or 'yozilmagan'}</code>\n\nFormat: <code>1a2b3c...</code> shaklida yuboring. Interaktivga qaytish uchun kalitni yuboring va menyuni kuting.", 
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_test_keys_text)
async def process_keys_text(message: Message, state: FSMContext):
    keys = message.text.lower().replace(" ", "")
    # Matnni Dict ga aylantiramiz (Sinxronizatsiya)
    found_keys = re.findall(r'(\d+)([a-z])', keys)
    new_dict = {int(k): v for k, v in found_keys}
    
    await state.update_data(keys_dict=new_dict)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Belgilashga qaytish", callback_data="key_mode_mark")],
        [InlineKeyboardButton(text="✅ Shu holatda saqlash", callback_data="adm_finish_keys")]
    ])
    await message.answer(f"✅ <b>Matn qabul qilindi!</b>\nKalitlar: <code>{keys}</code>\n\nTanlang:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("adm_ans_"))
async def process_adm_ans(callback: CallbackQuery, state: FSMContext):
    p = callback.data.split("_"); q_num, ans = int(p[2]), p[3]
    data = await state.get_data(); k_dict = data.get("keys_dict", {}); k_dict[q_num] = ans
    await state.update_data(keys_dict=k_dict)
    await show_keys_marking(callback.message, q_num + 1, k_dict)
    try: await callback.answer()
    except: pass

@dp.callback_query(F.data.startswith("adm_move_"))
async def move_adm_keys(callback: CallbackQuery, state: FSMContext):
    new_q = int(callback.data.split("_")[2]); data = await state.get_data()
    if new_q > 0: await show_keys_marking(callback.message, new_q, data['keys_dict'])
    await callback.answer()

@dp.callback_query(F.data == "adm_finish_keys")
async def finish_adm_keys(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data(); k_dict = data.get('keys_dict', {})
    if not k_dict: 
        await callback.answer("⚠️ Kalitlar kiritilmagan!", show_alert=True)
        return
    
    keys_str = "".join([f"{k}{v}" for k, v in sorted(k_dict.items())])
    await state.update_data(keys_str=keys_str)
    
    text = f"🏁 <b>Test Kalitlari Tayyor!</b>\n\n🔢 Savollar soni: <b>{len(k_dict)} ta</b>\n🔑 Kalitlar: <code>{keys_str}</code>\n\nBarchasi to'g'rimi? Ma'lumotlar avtomatik sinxronlandi."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash va Saqlash", callback_data="adm_confirm_save")],
        [InlineKeyboardButton(text="⌨️ Matnni tahrirlash", callback_data="key_mode_text")],
        [InlineKeyboardButton(text="🔢 Belgilashga qaytish", callback_data="key_mode_mark")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "adm_confirm_save")
async def adm_confirm_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await finalize_test(callback.message, state, data['title'], data['content'], data['keys_str'], data['t_type'])
    await callback.answer("✅ Test muvaffaqiyatli saqlandi!")

@dp.message(AdminStates.waiting_test_keys_text)
async def process_keys_text(message: Message, state: FSMContext):
    data = await state.get_data(); keys = message.text.lower().replace(" ", "")
    await finalize_test(message, state, data['title'], data['content'], keys, data['t_type'])

async def finalize_test(message, state, title, content, keys, t_type):
    if not keys:
        await message.answer("⚠️ <b>Kalitlar topilmadi!</b>\nIltimos, javoblarni <code>1a2b3c...</code> formatida yozib yuboring:", parse_mode="HTML")
        await state.set_state(AdminStates.waiting_test_keys_text)
        return

    try:
        await db.add_test(title, content, keys, t_type)
        questions_count = len(re.findall(r'(\d+)([a-z])', keys))
        await message.answer(f"✅ <b>Muvaffaqiyatli saqlandi!</b>\n\n📄 Test: {title}\n🔢 Savollar: {questions_count}", parse_mode="HTML")
        
        # AVTOMATIK E'LON
        users = await db.get_all_users()
        u_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
        bc_text = f"🆕 <b>Yangi test qo'shildi!</b>\n\n📄 Test: <b>{title}</b>\n\nJavoblarni yuborish usulini tanlang:\n\n1️⃣ <b>Belgilash orqali</b>\n2️⃣ <b>Matn ko'rinishida</b>\n\n👇 Marhamat, botga kiring!"
        for u_id in users:
            try: await u_bot.send_message(u_id, bc_text, parse_mode="HTML"); await asyncio.sleep(0.05)
            except: pass
        await u_bot.session.close()
        menu = await get_user_menu(message.chat.id)
        await message.answer(f"📢 <b>{len(users)} kishiga xabar yuborildi!</b>", reply_markup=menu, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Saqlashda xato: {e}")
        await message.answer(f"❌ Saqlashda xato: {e}")
    await state.clear()

# --- QOLGANLAR ---
@dp.callback_query(F.data == "st_global")
async def stats_menu(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid != ADMIN_ID and not await db.is_sub_admin(uid):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    u, r = await db.get_stats()
    
    txt = (
        f"📊 <b>Umumiy Statistika</b>\n\n"
        f"👤 <b>Foydalanuvchilar:</b> {u} ta\n"
        f"📝 <b>Bajarilgan testlar:</b> {r} ta\n\n"
        f"<i>Qaysi turdagi hisobotni ko'rmoqchisiz?</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Reyting (Faqat 1-urinish)", callback_data="stats_users")],
        [InlineKeyboardButton(text="📋 Barcha urinishlar (Tarix)", callback_data="stats_history")],
        [InlineKeyboardButton(text="📑 Testlar bo'yicha", callback_data="stats_tests")],
        [InlineKeyboardButton(text="📥 Natijalarni Excelda yuklab olish", callback_data="stats_excel")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "stats_history")
async def stats_history(callback: CallbackQuery):
    history = await db.get_all_results_history(limit=50) # Oxirgi 50 ta
    if not history:
        await callback.answer("⚠️ Tarix hali mavjud emas!", show_alert=True)
        return
    
    txt = "📋 <b>Oxirgi natijalar (Barcha urinishlar):</b>\n\n"
    for r in history:
        name = r['full_name'] or r['username'] or "Nomsiz"
        txt += f"👤 <b>{name}</b>\n"
        txt += f"   └ {r['test_title'][:15]}.. | ✅ {r['score']}/{r['total']} | 🕒 {r['timestamp'][11:16]}\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="st_global")]
    ])
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "stats_excel")
async def download_results_excel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID and not await db.is_sub_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    
    await callback.answer("⏳ Fayl tayyorlanmoqda, kuting...")
    
    data = await db.get_all_results_for_excel()
    if not data:
        await callback.message.answer("⚠️ Hali natijalar mavjud emas!")
        return
    
    # DataFrame yaratamiz
    df = pd.DataFrame(data)
    
    # Sarlavhalarni chiroyli qilamiz
    df.columns = ["Ism Familiya", "Username", "Telefon", "Test Nomi", "Ball", "Jami savol", "Sana"]
    
    # Excel faylga saqlaymiz
    file_path = "Test_Natijalari.xlsx"
    df.to_excel(file_path, index=False)
    
    # Faylni yuboramiz
    await callback.message.answer_document(
        document=FSInputFile(file_path),
        caption=f"📊 <b>Barcha test natijalari</b>\n\nJami yozuvlar: {len(data)} ta\nSana: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        parse_mode="HTML"
    )
    
    # Vaqtinchalik faylni o'chiramiz
    if os.path.exists(file_path):
        os.remove(file_path)

@dp.callback_query(F.data == "stats_users")
async def stats_users(callback: CallbackQuery):
    users_data = await db.get_detailed_stats_by_user()
    if not users_data:
        await callback.answer("⚠️ Ma'lumot topilmadi!", show_alert=True)
        return
    
    txt = "👥 <b>Foydalanuvchilar reytingi:</b>\n\n"
    # Faqat test bajarganlarni ajratib olamiz
    active_users = [u for u in users_data if u['tests_count'] > 0]
    
    if not active_users:
        txt = "👥 <b>Foydalanuvchilar:</b>\n\nHali echilgan testlar yo'q."
    else:
        for i, u in enumerate(active_users[:20], 1): # Top 20
            name = u['full_name'] or u['username'] or f"ID: {u['user_id']}"
            corr = u['total_correct'] or 0
            ques = u['total_questions'] or 0
            err = ques - corr
            count = u['tests_count']
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            txt += f"{medal} <b>{name}</b>\n"
            txt += f"   └ 📝 {count} ta test | ✅ {corr} | ❌ {err}\n\n"
            
        if len(active_users) > 20:
            txt += f"<i>...va yana {len(active_users)-20} ta faol foydalanuvchi.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📑 Testlar bo'yicha", callback_data="stats_tests")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="st_global")]
    ])
    
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "stats_tests")
async def stats_tests_list(callback: CallbackQuery):
    tests = await db.get_all_tests()
    if not tests:
        await callback.answer("📂 Testlar mavjud emas!", show_alert=True)
        return
    
    txt = "📑 <b>Testlar bo'yicha statistika:</b>\n\nNatijalarni ko'rish uchun testni tanlang:"
    kb = []
    
    for t in tests[:25]:
        kb.append([InlineKeyboardButton(text=f"📋 {t['title'][:25]}", callback_data=f"st_test_det_{t['id']}")])
    
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="st_global")])
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("st_test_det_"))
async def stats_test_details(callback: CallbackQuery):
    test_id = int(callback.data.split("_")[3])
    test = await db.get_test(test_id)
    results = await db.get_results_by_test_detailed(test_id)
    
    if not test:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return
    
    txt = f"📊 <b>Natija:</b> {test['title']}\n"
    txt += f"👥 <b>Qatnashchilar:</b> {len(results)} ta\n\n"
    
    if not results:
        txt += "ℹ️ Ushbu test hali hech kim tomondan ishlanmagan."
    else:
        for i, r in enumerate(results[:25], 1):
            name = r['full_name'] or r['username'] or "Nomsiz"
            txt += f"{i}. 👤 <b>{name}</b>\n"
            txt += f"   └ ✅ {r['score']}/{r['total']} | 📱 {r['phone'] or '-'}\n"
            
        if len(results) > 25:
            txt += f"\n<i>...va yana {len(results)-25} ta natija.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📑 Testlar ro'yxati", callback_data="stats_tests")],
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="st_global")]
    ])
    
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "list_tests")
async def list_tests(callback: CallbackQuery):
    tests = await db.get_all_tests()
    if not tests: await callback.answer("📂 Testlar yo'q!", show_alert=True); return
    
    txt = f"🗂 <b>Barcha testlar ({len(tests)} ta):</b>\n\nBoshqarish uchun test ustiga bosing:"
    kb = []
    for i, t in enumerate(tests[:25], 1): 
        kb.append([
            InlineKeyboardButton(text=f"📋 {i}. {t['title'][:30]}", callback_data=f"test_manage_{t['id']}")
        ])
    
    if len(tests) > 1:
        kb.append([InlineKeyboardButton(text="💣 BARCHASINI O'CHIRISH", callback_data="confirm_del_all")])
    
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("test_manage_"))
async def test_manage(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    test = await db.get_test(t_id)
    if not test:
        await callback.answer("❌ Test topilmadi!", show_alert=True)
        return
    
    txt = f"⚙️ <b>Testni boshqarish:</b>\n\n📄 Nomi: <b>{test['title']}</b>\n🔑 Kalitlar: <code>{test['keys']}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Natijalarni ko'rish", callback_data=f"st_test_det_{t_id}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"confirm_del_single_{t_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="list_tests")]
    ])
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("confirm_del_single_"))
async def confirm_del_single(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[3])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"del_test_{t_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"test_manage_{t_id}")]
    ])
    await callback.message.edit_text("⚠️ <b>Ushbu testni o'chirishni tasdiqlaysizmi?</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "confirm_del_all")
async def confirm_del_all(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, hammasini o'chir!", callback_data="del_all_now")],
        [InlineKeyboardButton(text="❌ Yo'q, bekor qilish", callback_data="list_tests")]
    ])
    await callback.message.edit_text("⚠️ <b>DIQQAT!</b>\n\nBarcha testlarni o'chirib tashlamoqchimisiz? Bu amalni qaytarib bo'lmaydi!", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "del_all_now")
async def del_all_now(callback: CallbackQuery):
    await db.delete_all_tests()
    await callback.answer("💥 Barcha testlar o'chirildi!", show_alert=True)
    await back_to_admin(callback, None)

@dp.callback_query(F.data.startswith("del_test_"))
async def del_t(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[2])
    await db.delete_test(t_id)
    await callback.answer("✅ Test o'chirildi!")
    await list_tests(callback)

@dp.callback_query(F.data == "search_user")
async def show_all_users(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if uid != ADMIN_ID and not await db.is_sub_admin(uid):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await state.clear()
    users_list = await db.get_all_users_info()
    if not users_list:
        menu = await get_user_menu(uid)
        await callback.message.edit_text("👥 Hozircha foydalanuvchilar yo'q.", reply_markup=menu)
        return
    
    txt = f"👥 <b>Barcha foydalanuvchilar ({len(users_list)} ta):</b>\n\n"
    for i, u in enumerate(users_list[:30], 1):
        full_name = u.get('full_name') or ''
        username = u.get('username') or ''
        phone = u.get('phone', '-') or '-'
        uid = u.get('user_id', '-')
        reg = u.get('registered_at', '-')
        
        # Ism ko'rsatish: full_name → @username → ID
        if full_name.strip():
            display_name = full_name
        elif username:
            display_name = f"@{username}"
        else:
            display_name = f"ID: {uid}"
        
        txt += f"<b>{i}.</b> 👤 {display_name}\n   📱 {phone}\n   🆔 <code>{uid}</code>\n   📅 {reg}\n\n"
    
    if len(users_list) > 30:
        txt += f"<i>...va yana {len(users_list)-30} ta foydalanuvchi</i>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "st_settings")
async def show_settings(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Bu funksiya faqat asosiy admin uchun!", show_alert=True)
        return
    ch = await db.get_setting("channels")
    text = f"⚙️ <b>Sozlamalar:</b>\n\n📢 Kanallar:\n<code>{ch}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallarni tahrirlash", callback_data="set_ch")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "set_ch")
async def set_ch_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_setting_value)
    await callback.message.edit_text("✍️ Yangi kanallarni yuboring (Format: <code>@ch1,@ch2</code>):", parse_mode="HTML")

@dp.message(AdminStates.waiting_setting_value)
async def process_setting_value(message: Message, state: FSMContext):
    await db.update_setting("channels", message.text.strip())
    menu = await get_user_menu(message.from_user.id)
    await message.answer("✅ Yangilandi!", reply_markup=menu)
    await state.clear()

@dp.callback_query(F.data == "st_broadcast")
async def bc_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Bu funksiya faqat asosiy admin uchun!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.message.edit_text("📢 Reklama matnini yuboring:")

@dp.message(AdminStates.waiting_broadcast_text)
async def bc_tx(message: Message, state: FSMContext):
    await state.update_data(txt=message.text)
    await state.set_state(AdminStates.waiting_broadcast_photo)
    await message.answer("📸 Rasm yoki <code>/skip</code>")

@dp.message(AdminStates.waiting_broadcast_photo)
async def bc_ph(message: Message, state: FSMContext):
    p = message.photo[-1].file_id if message.photo else None
    if p:
        u_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
        temp_p = f"temp_bc_{p}"
        try:
            file = await bot.get_file(p)
            await bot.download_file(file.file_path, temp_p)
            from aiogram.types import FSInputFile
            msg = await u_bot.send_photo(ADMIN_ID, FSInputFile(temp_p))
            p = msg.photo[-1].file_id
            if os.path.exists(temp_p): os.remove(temp_p)
        except Exception as e:
            logging.error(f"Broadcast rasmida xato: {e}")
            if os.path.exists(temp_p): os.remove(temp_p)
        await u_bot.session.close()
    await state.update_data(p=p)
    await state.set_state(AdminStates.waiting_broadcast_button)
    await message.answer("🔗 Tugma (Nom | link) yoki /skip")

@dp.message(AdminStates.waiting_broadcast_button)
async def bc_fi(message: Message, state: FSMContext):
    data = await state.get_data()
    u_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
    kb = None
    if "|" in message.text:
        try:
            n, l = message.text.split("|")
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=n.strip(), url=l.strip())]])
        except: pass
    users = await db.get_all_users()
    for u_id in users:
        try:
            if data['p']: await u_bot.send_photo(u_id, data['p'], caption=data['txt'], reply_markup=kb, parse_mode="HTML")
            else: await u_bot.send_message(u_id, data['txt'], reply_markup=kb, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except: pass
    await u_bot.session.close()
    await message.answer("✅ Tarqatildi!", reply_markup=get_super_admin_menu())
    await state.clear()

# ===== SUB-ADMIN BOSHQARUVI (faqat Super Admin) =====
@dp.callback_query(F.data == "manage_subadmins")
async def manage_subadmins(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Faqat asosiy admin!", show_alert=True)
        return
    admins = await db.get_all_sub_admins()
    txt = f"👨‍🏫 <b>Sub-Adminlar ({len(admins)} ta):</b>\n\n"
    for i, a in enumerate(admins, 1):
        name = a.get('full_name') or 'Nomsiz'
        uid = a.get('user_id')
        txt += f"{i}. 👤 {name} | 🆔 <code>{uid}</code>\n"
    if not admins:
        txt += "Hozircha sub-adminlar yo'q.\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Sub-Admin Qo'shish", callback_data="add_subadmin")],
        [InlineKeyboardButton(text="🗑 Sub-Admin O'chirish", callback_data="remove_subadmin")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(txt, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "add_subadmin")
async def add_subadmin_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Faqat asosiy admin!", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_sub_admin_id)
    await callback.message.edit_text(
        "👨‍🏫 <b>Yangi Sub-Admin qo'shish:</b>\n\nO'qituvchining Telegram <b>ID raqamini</b> yuboring.\n\n"
        "<i>💡 ID ni bilish uchun: o'qituvchi @userinfobot ga /start yuboring</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.waiting_sub_admin_id)
async def process_subadmin_id(message: Message, state: FSMContext):
    if not message.text.lstrip('-').isdigit():
        await message.answer("⚠️ Faqat raqam kiriting! Masalan: <code>123456789</code>", parse_mode="HTML")
        return
    await state.update_data(new_sub_id=int(message.text))
    await state.set_state(AdminStates.waiting_sub_admin_name)
    await message.answer("✍️ O'qituvchining ismini kiriting (Masalan: <code>Aziz Karimov</code>):", parse_mode="HTML")

@dp.message(AdminStates.waiting_sub_admin_name)
async def process_subadmin_name(message: Message, state: FSMContext):
    data = await state.get_data()
    new_id = data['new_sub_id']
    name = message.text.strip()
    await db.add_sub_admin(new_id, name)
    # Yangi sub-adminga xabar yuboramiz
    try:
        await bot.send_message(
            new_id,
            f"🎉 <b>Tabriklaymiz, {name}!</b>\n\nSiz ZiyoEdubot admin panelida <b>O'qituvchi</b> sifatida qo'shildingiz.\n\nTest qo'shish va statistikani ko'rish uchun /start bosing!",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Sub-adminga xabar yuborib bo'lmadi: {e}")
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Sub-Adminlarga qaytish", callback_data="manage_subadmins")],
        [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="back_to_admin")]
    ])
    await message.answer(
        f"✅ <b>{name}</b> sub-admin sifatida qo'shildi!\n🆔 ID: <code>{new_id}</code>\n\nUga bildirishnoma yuborildi.",
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data == "remove_subadmin")
async def remove_subadmin_list(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Faqat asosiy admin!", show_alert=True)
        return
    admins = await db.get_all_sub_admins()
    if not admins:
        await callback.answer("Sub-adminlar yo'q!", show_alert=True)
        return
    kb_list = []
    for a in admins:
        name = a.get('full_name') or 'Nomsiz'
        uid = a.get('user_id')
        kb_list.append([InlineKeyboardButton(text=f"🗑 {name} ({uid})", callback_data=f"del_sub_{uid}")])
    kb_list.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="manage_subadmins")])
    await callback.message.edit_text(
        "🗑 <b>O'chirish uchun sub-adminni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("del_sub_"))
async def delete_subadmin(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Faqat asosiy admin!", show_alert=True)
        return
    sub_id = int(callback.data.split("_")[2])
    await db.remove_sub_admin(sub_id)
    # Sub-adminga xabar
    try:
        await bot.send_message(sub_id, "ℹ️ Siz admin paneliga kirishingiz bekor qilindi.")
    except: pass
    await callback.answer("✅ Sub-admin o'chirildi!")
    await manage_subadmins(callback)

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
