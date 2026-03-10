const { GoogleGenerativeAI } = require("@google/generative-ai");
require('dotenv').config();

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" }); // Tezkor va rasmlarni yaxshi taniydi

async function solveTest(input, isImage = false) {
    try {
        const prompt = `
    Siz professional o'qituvchi va test tahlilchisisiz. 
    Sizga berilgan test savolini tahlil qiling va to'g'ri javobni (Variantni) aniqlang.
    
    Javobingiz quyidagi struktura bo'yicha bo'lishi kerak:
    1. 📝 Savolning qisqacha mazmuni.
    2. ✅ To'g'ri javob varianti.
    3. 💡 Tushuntirish (Nima uchun aynan shu javob to'g'ri ekanligini ilmiy va sodda tushuntiring).
    
    Javob faqat O'zbek tilida (lotin alifbosida) bo'lsin. Professionallikni saqlang.
    `;

        if (isImage) {
            // Rasmli test
            const result = await model.generateContent([
                prompt,
                {
                    inlineData: {
                        data: input.buffer.toString("base64"),
                        mimeType: input.mimeType,
                    },
                },
            ]);
            return result.response.text();
        } else {
            // Matnli test
            const result = await model.generateContent([prompt, input]);
            return result.response.text();
        }
    } catch (error) {
        console.error("AI Error:", error);
        return "Xatolik yuz berdi: AI testni tahlil qila olmadi. Iltimos, qaytadan urinib ko'ring yoki rasm sifatini tekshiring.";
    }
}

module.exports = { solveTest };
