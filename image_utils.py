from PIL import Image, ImageDraw, ImageFont
import io
import textwrap

def generate_answer_image(text, output_path="answer.png"):
    """
    Matnni chiroyli ko'rinishdagi rasmga aylantirish.
    """
    # Rasm o'lchamini va fondni tanlang (oq fond)
    img_width = 800
    img_height = 1000  # Matn uzunligiga qarab o'zgarishi mumkin
    bg_color = (255, 255, 255)
    text_color = (0, 0, 0)
    
    # Rasm yaratish
    img = Image.new('RGB', (img_width, img_height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Arial shriftidan foydalanamiz (agar bo'lmasa, default tanlanadi)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
        
    # Matnni satrlarga bo'lib chiqamiz
    margin = 30
    offset = 30
    for line in textwrap.wrap(text, width=60):
        draw.text((margin, offset), line, font=font, fill=text_color)
        offset += font.getbbox(line)[3] + 10
        
    # Rasmni RAMda (In-memory) saqlaymiz
    output = io.BytesIO()
    final_img = img.crop((0, 0, img_width, offset + margin)) # Keraksiz joylarni kesish
    final_img.save(output, format='PNG')
    output.seek(0)
    return output
