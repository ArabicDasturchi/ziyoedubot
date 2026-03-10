import os
import base64
from openai import OpenAI
from dotenv import load_dotenv
import io

load_dotenv()

# OpenAI sozlamalari
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def analyze_test(content, is_image=False, mode="solver"):
    """
    OpenAI (GPT-4o) orqali professional xizmatlar.
    """
    prompts = {
        "solver": "Siz ZiyoEdubot test yechish mutaxassisiz. Testni tahlil qiling, 1a2B3c4D formatida javob bering va har birini ilmiy tushuntiring. Til: O'zbek.",
        "mentor": "Siz ZiyoEdubot AI Mentorisiz. Mavzuni o'quvchiga dars o'tgandek qiziqarli va sodda tushuntiring. Til: O'zbek.",
        "editor": "Siz akademik tahrirchisiz. Matnni grammatik va uslubiy jihatdan mukammal holatga keltiring. Til: O'zbek.",
        "exam": "Siz imtihon savollari tuzuvchisiz. Berilgan mavzu bo'yicha 5 ta qiziqarli va murakkab test savollarini (variantlari bilan) tuzing. Til: O'zbek.",
        "dict": "Siz professional tarjimon va tilshunosiz. Berilgan so'zni ingliz, rus va o'zbek tillarida tarjima qiling, urg'usini ko'rsating va gapda ishlatib bering. Til: O'zbek.",
        "motivator": "Siz ta'lim va shaxsiy rivojlanish bo'yicha motivatormisiz. O'quvchilarga o'qishga ishtiyoq beruvchi, kuchli va ilhomlantiruvchi gaplar ayting. Til: O'zbek.",
        "planner": "Siz professional o'quv reja tuzuvchisiz. Foydalanuvchi aytgan fan yoki maqsad uchun eng effektiv haftalik o'quv rejasini tuzib bering. Til: O'zbek."
    }

    system_prompt = prompts.get(mode, prompts["solver"])
    
    try:
        messages = [{"role": "system", "content": system_prompt}]
        
        if is_image:
            base64_image = base64.b64encode(content).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Iltimos, ushbu kontentni professional tahlil qiling."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            })
        else:
            messages.append({"role": "user", "content": content})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=3000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI Error: {e}") # Changed from logging.error to print as logging is not imported
        error_msg = str(e)
        if "insufficient_quota" in error_msg or "429" in error_msg:
            return "⚠️ <b>Hozirda AI xizmatida vaqtinchalik cheklov (Quota) yuzaga keldi.</b>\n\nIltimos, ushbu holat bo'yicha admin bilan bog'laning yoki birozdan so'ng qayta urinib ko'ring."
        return f"❌ <b>Tizimda xatolik yuz berdi.</b>\n\nIltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning."
