from docxtpl import DocxTemplate
from persiantools import digits
from persiantools.jdatetime import JalaliDate
import os
from pathlib import Path

template_path = r"C:\Users\Azar Fonoon\Desktop\template.docx"
output_path = r"C:\Users\Azar Fonoon\Desktop\TFP.docx"

try:
    # Validate template exists
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    # Prepare output directory
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    price = 11253000  # ریال
    price_num = digits.en_to_fa("ریال" + f"{price:,}")
    price_text = digits.to_word(price) + " ریال"
    date_text = JalaliDate.today().strftime("%Y/%m/%d")
    pr = "92"
    client_name = "ستاره باران"

    doc = DocxTemplate(template_path)

    context = {
        "price": price_num,
        "price_text": price_text,
        "date": date_text,
        "PR": pr,
        "client_name": client_name
    }

    doc.render(context)
    doc.save(output_path)
    print(" File generated successfully at:", output_path)

except FileNotFoundError as e:
    print(f" Error: {e}")
except PermissionError:
    print(f" Permission denied: Cannot write to {output_path}")
except Exception as e:
    print(f" Unexpected error: {e}")