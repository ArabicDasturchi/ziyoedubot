import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

import database as db

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("USER_BOT_TOKEN"))
dp = Dispatcher()

class UserStates(StatesGroup):
    waiting_phone = State()
    main_menu = State()
    solving_test = State()
    interactive_marking = State()

def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Mavjud Testlar"), KeyboardButton(text="📊 Mening Natijalarim")],
            [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="🆘 Yordam")]
        ],
        resize_keyboard=True
    )

async def check_all_subscriptions(user_id):
    """Barcha majburiy kanallarni tekshiradi va ulanmaganlarini ro'yxatini qaytaradi."""
    channels_str = await db.get_setting("channels")
    if not channels_str: return [], []
    
    channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]
    unsubscribed = []
    
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed.append(ch)
        except Exception as e:
            err_msg = str(e)
            if "member list is inaccessible" in err_msg:
                logging.error(f"❌ DIQQAT: Bot '{ch}' kanalida ADMIN emas! Iltimos, botni admin qiling.")
            else:
                logging.error(f"Xato: {ch} tekshirib bo'lmadi: {e}")
            unsubscribed.append(ch)
            
    return unsubscribed, channels

@dp.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Foydalanuvchi ma'lumotlarini o'chiradi (Testing uchun)."""
    await db.reset_user(message.from_user.id)
    await state.clear()
    await message.answer("🔄 Profilingiz tozalandi. Endi qaytadan /start bosing.")

async def start_logic(user_id, message_obj, state: FSMContext, is_callback=False):
    """Botning asosiy kirish mantig'i: Kontakt -> Obuna -> Menyu."""
    user = await db.get_user(user_id)
    if not user:
        await db.add_user(user_id, "", "")
        user = await db.get_user(user_id)

    # 1. Kontakt kiritilganligini tekshirish (MUTLAQ BIRINCHI!)
    if not user or not user.get("phone") or user.get("phone") == "None" or user.get("phone") == "":
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Kontaktni yuborish", request_contact=True)]], 
            resize_keyboard=True,
            one_time_keyboard=True
        )
        text = "<b>Diagnostik TEST | Matematika</b>\n\nBotdan foydalanish uchun kontaktingizni yuboring (<i>pastdagi tugmani bosing</i>):"
        if is_callback:
            await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_obj.answer(text, reply_markup=kb, parse_mode="HTML")
        await state.set_state(UserStates.waiting_phone)
        return

    # 2. KONTAKT BOR BO'LSA -> ENDI OBUNANI TEKSHIRISH
    unsub_list, _ = await check_all_subscriptions(user_id)
    if unsub_list:
        text = f"<b>Diagnostik TEST | Matematika</b>\n\n⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz shart:\n\n"
        kb_list = []
        for ch in unsub_list:
            text += f"👉 <b>{ch}</b>\n"
            kb_list.append([InlineKeyboardButton(text=f"➕ {ch} kanaliga ulanish", url=f"https://t.me/{ch.replace('@','')}")])
        
        text += "\nKanalga obuna bo‘lib, <b>«✅ Obuna bo‘ldim»</b> ni bosing."
        kb_list.append([InlineKeyboardButton(text="✅ Obuna bo‘ldim", callback_data="check_sub")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
        
        if is_callback:
            await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
        else:
            await message_obj.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    # 3. Hamma narsa joyida (Kontakt + Obuna) -> Asosiy menyu
    text = "✅ <b>Obuna tasdiqlandi!</b>\n\nTestlarni boshlash uchun menyudan tanlang:"
    if is_callback:
        await bot.send_message(user_id, text, reply_markup=get_main_kb(), parse_mode="HTML")
    else:
        await message_obj.answer(text, reply_markup=get_main_kb(), parse_mode="HTML")
    await state.set_state(UserStates.main_menu)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await start_logic(message.from_user.id, message, state)

@dp.message(UserStates.waiting_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    await db.update_user_phone(message.from_user.id, message.contact.phone_number)
    await message.answer("✅ Kontakt muvaffaqiyatli saqlandi!", reply_markup=ReplyKeyboardRemove())
    await start_logic(message.from_user.id, message, state)

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, state: FSMContext):
    unsub_list, _ = await check_all_subscriptions(callback.from_user.id)
    if not unsub_list:
        try: await callback.message.delete()
        except: pass
        await start_logic(callback.from_user.id, callback.message, state, is_callback=True)
    else:
        await callback.answer(f"❌ Siz hali barcha kanallarga ulanmagansiz!", show_alert=True)

@dp.message(F.text == "📝 Mavjud Testlar")
async def show_tests(message: Message, state: FSMContext):
    tests = await db.get_all_tests()
    if not tests:
        await message.answer("📂 Hozircha mavjud testlar yo'q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📄 {t['title']}", callback_data=f"view_{t['id']}")] for t in tests
    ])
    await message.answer("👇 Mavjud diagnostik testlar:", reply_markup=kb)

@dp.callback_query(F.data.startswith("view_"))
async def view_test(callback: CallbackQuery, state: FSMContext):
    await callback.answer("⏳ Yuklanmoqda...")
    
    test_id = int(callback.data.split("_")[1])
    test = await db.get_test(test_id)
    
    if not test:
        await callback.message.answer("❌ Test topilmadi!")
        return
    
    # Ma'lumotlarni dict ko'rinishida olamiz
    f_id = test['file_id']
    t_title = test['title']
    t_type = test.get('test_type', 'pdf')
    
    logging.info(f"DEBUG: Test yuborilmoqda: {t_title} ({t_type})")
    
    await state.update_data(current_test_id=test_id)
    await state.set_state(UserStates.solving_test)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Belgilash orqali", callback_data=f"mark_{test_id}")],
        [InlineKeyboardButton(text="⌨️ Matn ko'rinishida yuborish", callback_data="switch_to_manual")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="show_tests_list")]
    ])
    
    caption = f"📋 <b>Test: {t_title}</b>\n\nJavoblarni quyidagi usullardan biri bilan yuboring:"
    
    try:
        if t_type == "pdf":
            await bot.send_document(callback.message.chat.id, f_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        elif t_type == "image":
            await bot.send_photo(callback.message.chat.id, f_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        elif t_type == "text":
            await bot.send_message(callback.message.chat.id, f"📝 <b>Matnli Test: {t_title}</b>\n\n{f_id}\n\n{caption}", reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.answer(f"⚠️ Noma'lum test formati: {t_type}")
            
    except Exception as e:
        logging.error(f"Test yuborishda xato: {e}")
        await callback.message.answer(f"❌ Faylni yuborishda xatolik yuz berdi: {e}")

@dp.callback_query(F.data == "show_tests_list")
async def back_to_tests(callback: CallbackQuery, state: FSMContext):
    try: await callback.message.delete()
    except: pass
    await show_tests(callback.message, state)

@dp.callback_query(F.data.startswith("mark_"))
async def start_marking(callback: CallbackQuery, state: FSMContext):
    test_id = int(callback.data.split("_")[1])
    test = await db.get_test(test_id)
    if not test: return
    
    keys = re.findall(r"(\d+)([a-z])", test['keys'])
    await state.update_data(current_test_id=test_id, user_ans={}, total=len(keys), marking_msg_id=None)
    
    await callback.message.answer("📝 <b>Javoblarni belgilashni boshlaymiz:</b>\n1-savoldan boshlanadi:", parse_mode="HTML")
    await state.set_state(UserStates.interactive_marking)
    
    # Yangi belgilash xabarini yuborib, uning message_id sini saqlaymiz
    sent = await bot.send_message(
        chat_id=callback.message.chat.id,
        text=f"📝 <b>Javoblarni belgilash:</b>\n\nSavol: 1/{len(keys)}\nTanlangan: <b>Ø</b>\n\n👇 Javobni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A", callback_data="ans_1_a"), InlineKeyboardButton(text="B", callback_data="ans_1_b"), InlineKeyboardButton(text="C", callback_data="ans_1_c"), InlineKeyboardButton(text="D", callback_data="ans_1_d")],
            [InlineKeyboardButton(text="⬅️ Oldingi", callback_data="move_0"), InlineKeyboardButton(text="Keyingi ➡️", callback_data="move_2")],
            [InlineKeyboardButton(text="⌨️ Qo'lda kiritish", callback_data="switch_to_manual")],
            [InlineKeyboardButton(text="✅ Yakunlash", callback_data="finish_marking")]
        ]),
        parse_mode="HTML"
    )
    await state.update_data(marking_msg_id=sent.message_id)
    try: await callback.answer()
    except: pass

async def show_marking_step(chat_id, q_num, total, user_ans, message_id=None):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data=f"ans_{q_num}_a"), 
         InlineKeyboardButton(text="B", callback_data=f"ans_{q_num}_b"), 
         InlineKeyboardButton(text="C", callback_data=f"ans_{q_num}_c"), 
         InlineKeyboardButton(text="D", callback_data=f"ans_{q_num}_d")],
        [InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"move_{q_num-1}"), 
         InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"move_{q_num+1}")],
        [InlineKeyboardButton(text="⌨️ Qo'lda kiritish", callback_data="switch_to_manual")],
        [InlineKeyboardButton(text="✅ Yakunlash", callback_data="finish_marking")]
    ])
    sel = user_ans.get(q_num, "Ø").upper()
    text = f"📝 <b>Javoblarni belgilash:</b>\n\nSavol: {q_num}/{total}\nTanlangan: <b>{sel}</b>\n\n👇 Javobni tanlang:"
    
    try:
        if message_id:
            # Keyword argumentlar bilan chaqiramiz (aiogram 3 uchun to'g'ri usul)
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        if "message is not modified" not in str(e):
            logging.error(f"UI Update error: {e}")

@dp.callback_query(F.data == "switch_to_manual")
async def switch_manual(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.solving_test)
    # Belgilash xabarini o'chirib, yangi matn xabari yuboramiz
    # (edit_text PDF/Photo xabarda ishlamaydi)
    try: await callback.message.delete()
    except: pass
    await bot.send_message(
        chat_id=callback.message.chat.id,
        text="✍️ <b>Javoblarni yuboring:</b>\n\nFormat: <code>1a2b3c...</code>\n\nMisol: <code>1a2b3c4d5a...</code>",
        parse_mode="HTML"
    )
    try: await callback.answer()
    except: pass

@dp.callback_query(F.data.startswith("ans_"))
async def process_ans(callback: CallbackQuery, state: FSMContext):
    p = callback.data.split("_"); q_num, ans = int(p[1]), p[2]
    data = await state.get_data()
    user_ans = data['user_ans']
    user_ans[q_num] = ans
    await state.update_data(user_ans=user_ans)
    
    next_q = q_num + 1 if q_num < data['total'] else q_num
    await show_marking_step(
        chat_id=callback.message.chat.id,
        q_num=next_q,
        total=data['total'],
        user_ans=user_ans,
        message_id=data.get('marking_msg_id')
    )
    try: await callback.answer()
    except: pass

@dp.callback_query(F.data.startswith("move_"))
async def move_step(callback: CallbackQuery, state: FSMContext):
    new_q = int(callback.data.split("_")[1])
    data = await state.get_data()
    if 1 <= new_q <= data['total']:
        await show_marking_step(
            chat_id=callback.message.chat.id,
            q_num=new_q,
            total=data['total'],
            user_ans=data['user_ans'],
            message_id=data.get('marking_msg_id')
        )
    try: await callback.answer()
    except: pass

@dp.callback_query(F.data == "finish_marking")
async def finish_marking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_ans = data.get('user_ans', {})
    
    if not user_ans:
        await callback.answer("⚠️ Hech qanday javob belgilanmagan!", show_alert=True)
        return
    
    # Javoblarni string formatiga o'tkazamiz
    ans_str = "".join([f"{k}{v}" for k, v in sorted(user_ans.items())])
    test_id = data.get('current_test_id')
    
    # Belgilash xabarini o'chiramiz
    try: await callback.message.delete()
    except: pass
    
    # Natijani hisoblash va yuborish
    await calculate_and_send_results(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id,
        test_id=test_id,
        user_ans_str=ans_str,
        state=state
    )
    try: await callback.answer()
    except: pass

@dp.message(UserStates.solving_test)
async def check_answers(message: Message, state: FSMContext):
    if message.text in ["📝 Mavjud Testlar", "📊 Mening Natijalarim", "👤 Profilim", "🆘 Yordam"]:
        await state.set_state(UserStates.main_menu)
        return
    
    user_ans_str = message.text.lower().replace(" ", "")
    data = await state.get_data()
    test_id = data.get("current_test_id")
    
    await calculate_and_send_results(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        test_id=test_id,
        user_ans_str=user_ans_str,
        state=state,
        message=message
    )

async def calculate_and_send_results(chat_id, user_id, test_id, user_ans_str, state, message=None):
    test = await db.get_test(test_id)
    if not test:
        await bot.send_message(chat_id=chat_id, text="❌ Test topilmadi!")
        return
    
    correct_keys = re.findall(r"(\d+)([a-z])", test['keys'])
    user_keys = re.findall(r"(\d+)([a-z])", user_ans_str)
    
    if not user_keys:
        if message:
            await message.answer("⚠️ Javoblarni <code>1a2b3c...</code> shaklida yuboring.", parse_mode="HTML")
        return
    
    correct_map = {int(k): v for k, v in correct_keys}
    score, details = 0, ""
    
    for k, v in user_keys:
        k_int = int(k)
        if k_int in correct_map:
            if correct_map[k_int] == v:
                score += 1
                details += f"✅ {k}-{v.upper()}\n"
            else:
                details += f"❌ {k}-{v.upper()} (To'g'ri: {correct_map[k_int].upper()})\n"
    
    total = len(correct_map)
    percent = (score / total * 100) if total > 0 else 0
    
    result_text = (
        f"📊 <b>Natija: {test['title']}</b>\n\n"
        f"✅ To'g'ri: <b>{score}/{total}</b>\n"
        f"📈 Foiz: <b>{percent:.1f}%</b>\n\n"
        f"🗒 Tahlil:\n{details}"
    )
    
    # 1. Avval natijani yuboramiz
    await bot.send_message(chat_id=chat_id, text=result_text, parse_mode="HTML")
    
    # 2. Keyin asosiy menyu — alohida xabarda
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    main_kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Mavjud Testlar"), KeyboardButton(text="📊 Mening Natijalarim")],
        [KeyboardButton(text="👤 Profilim"), KeyboardButton(text="🆘 Yordam")]
    ], resize_keyboard=True)
    await bot.send_message(chat_id=chat_id, text="🏠 Keyingi testni tanlang:", reply_markup=main_kb)
    
    await db.save_result(user_id, test_id, user_ans_str, score, total)
    await state.set_state(UserStates.main_menu)

@dp.message(F.text == "📊 Mening Natijalarim")
async def show_results(message: Message):
    res = await db.get_user_results(message.from_user.id)
    if not res:
        await message.answer("📊 Sizda hali natijalar yo'q.")
        return
        
    txt = "📊 <b>Oxirgi natijalaringiz:</b>\n\n"
    for r in res[:10]: 
        # r['title'], r['score'], r['total'] dan foydalanamiz
        txt += f"📌 {r['title']}: <b>{r['score']}/{r['total']}</b>\n"
    await message.answer(txt, parse_mode="HTML")

@dp.message(F.text == "👤 Profilim")
async def show_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    await message.answer(f"👤 Profil:\nID: {message.from_user.id}\nTel: {user['phone']}", parse_mode="HTML")

@dp.message(F.text == "🆘 Yordam")
async def help_cmd(message: Message):
    await message.answer("🆘 <b>ZiyoEdubot Support Center</b>\n\nAdmin: @Buronovshahzod_2001\n\nSavollaringiz bo'lsa xabar qoldiring.", parse_mode="HTML")

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
