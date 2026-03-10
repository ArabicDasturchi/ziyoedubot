import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

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
    waiting_user_search = State()
    waiting_setting_value = State()

def get_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi Test Qo'shish", callback_data="add_test")],
        [InlineKeyboardButton(text="🗂 Testlar Ro'yxati", callback_data="list_tests")],
        [InlineKeyboardButton(text="📢 Reklama Tarqatish", callback_data="st_broadcast")],
        [InlineKeyboardButton(text="🔍 Foydalanuvchi Qidirish", callback_data="search_user")],
        [InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="st_settings"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="st_global")]
    ])

@dp.message(Command("start"))
async def start_admin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("🛠 <b>Ziyo Admin Panel - Ultra Full</b>", reply_markup=get_admin_main(), parse_mode="HTML")

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🛠 <b>Boshqaruv menyusi:</b>", reply_markup=get_admin_main(), parse_mode="HTML")

# --- TEST QO'SHISH ---
@dp.callback_query(F.data == "add_test")
async def start_add_test(callback: CallbackQuery, state: FSMContext):
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
        await message.answer(f"📢 <b>{len(users)} kishiga xabar yuborildi!</b>", reply_markup=get_admin_main())
    except Exception as e:
        logging.error(f"Saqlashda xato: {e}")
        await message.answer(f"❌ Saqlashda xato: {e}")
    await state.clear()

# --- QOLGANLAR ---
@dp.callback_query(F.data == "st_global")
async def stats(callback: CallbackQuery):
    u, r = await db.get_stats()
    await callback.message.edit_text(f"📊 <b>Statistika:</b>\n\n👤 Foydalanuvchilar: {u}\n📝 Yechilgan testlar: {r}", reply_markup=get_admin_main())

@dp.callback_query(F.data == "list_tests")
async def list_tests(callback: CallbackQuery):
    tests = await db.get_all_tests()
    if not tests: await callback.answer("📂 Testlar yo'q!", show_alert=True); return
    
    txt = f"🗂 <b>Barcha testlar ({len(tests)} ta):</b>\n\nQuyidagilardan birini o'chirishingiz mumkin:"
    kb = []
    for i, t in enumerate(tests[:20], 1): # Tartib raqam bilan ko'rsatamiz
        kb.append([InlineKeyboardButton(text=f"🗑 {i}. {t['title'][:25]}", callback_data=f"del_{t['id']}")])
    
    if len(tests) > 1:
        kb.append([InlineKeyboardButton(text="💣 BARCHASINI O'CHIRISH", callback_data="confirm_del_all")])
    
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")])
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

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

@dp.callback_query(F.data.startswith("del_"))
async def del_t(callback: CallbackQuery):
    t_id = int(callback.data.split("_")[1])
    await db.delete_test(t_id)
    await callback.answer("✅ Test o'chirildi!")
    await list_tests(callback)

@dp.callback_query(F.data == "search_user")
async def search_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_user_search); await callback.message.edit_text("🔍 Foydalanuvchi ID sini kiriting:")

@dp.message(AdminStates.waiting_user_search)
async def bc_search(message: Message, state: FSMContext):
    if not message.text.isdigit(): await message.answer("⚠️ Faqat raqam kiriting!"); return
    u = await db.get_user(int(message.text))
    if u: await message.answer(f"👤 {u['full_name']}\n📱 {u['phone']}\n📅 {u['registered_at']}", reply_markup=get_admin_main())
    else: await message.answer("❌ Topilmadi.", reply_markup=get_admin_main())
    await state.clear()

@dp.callback_query(F.data == "st_settings")
async def show_settings(callback: CallbackQuery):
    ch = await db.get_setting("channels")
    text = f"⚙️ <b>Sozlamalar:</b>\n\n📢 Kanallar:\n<code>{ch}</code>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallarni tahrirlash", callback_data="set_ch")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "set_ch")
async def set_ch_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_setting_value)
    await callback.message.edit_text("✍️ Yangi kanallarni yuboring (Format: <code>@ch1,@ch2</code>):", parse_mode="HTML")

@dp.message(AdminStates.waiting_setting_value)
async def process_setting_value(message: Message, state: FSMContext):
    await db.update_setting("channels", message.text.strip())
    await message.answer("✅ Yangilandi!", reply_markup=get_admin_main()); await state.clear()

@dp.callback_query(F.data == "st_broadcast")
async def bc_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_broadcast_text); await callback.message.edit_text("📢 Reklama matnini yuboring:")

@dp.message(AdminStates.waiting_broadcast_text)
async def bc_tx(message: Message, state: FSMContext):
    await state.update_data(txt=message.text); await state.set_state(AdminStates.waiting_broadcast_photo); await message.answer("📸 Rasm yoki <code>/skip</code>")

@dp.message(AdminStates.waiting_broadcast_photo)
async def bc_ph(message: Message, state: FSMContext):
    p = message.photo[-1].file_id if message.photo else None
    
    if p:
        # User Bot uchun valid file_id olish
        u_bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
        temp_p = f"temp_bc_{p}"
        try:
            # 1. Yuklab olish
            file = await bot.get_file(p)
            await bot.download_file(file.file_path, temp_p)
            
            # 2. Quyida ishlatish uchun qayta yuklash
            from aiogram.types import FSInputFile
            msg = await u_bot.send_photo(ADMIN_ID, FSInputFile(temp_p))
            p = msg.photo[-1].file_id
            
            # 3. O'chirish
            if os.path.exists(temp_p): os.remove(temp_p)
        except Exception as e:
            logging.error(f"Broadcast rasmida xato: {e}")
            if os.path.exists(temp_p): os.remove(temp_p)
        await u_bot.session.close()

    await state.update_data(p=p); await state.set_state(AdminStates.waiting_broadcast_button); await message.answer("🔗 Tugma (Nom | link) yoki /skip")

@dp.message(AdminStates.waiting_broadcast_button)
async def bc_fi(message: Message, state: FSMContext):
    data = await state.get_data(); u_bot = Bot(token=os.getenv("USER_BOT_TOKEN")); kb = None
    if "|" in message.text:
        try: n, l = message.text.split("|"); kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=n.strip(), url=l.strip())]])
        except: pass
    users = await db.get_all_users()
    for u_id in users:
        try:
            if data['p']: await u_bot.send_photo(u_id, data['p'], caption=data['txt'], reply_markup=kb, parse_mode="HTML")
            else: await u_bot.send_message(u_id, data['txt'], reply_markup=kb, parse_mode="HTML")
            await asyncio.sleep(0.05)
        except: pass
    await u_bot.session.close(); await message.answer("✅ Tarqatildi!", reply_markup=get_admin_main()); await state.clear()

async def main():
    await db.init_db(); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
