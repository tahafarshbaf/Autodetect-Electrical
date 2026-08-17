from docxtpl import DocxTemplate
from persiantools import digits
from persiantools.jdatetime import JalaliDate

template_path = r"C:\Users\Azar Fonoon\Desktop\template.docx"
output_path = r"C:\Users\Azar Fonoon\Desktop\TFP.docx"

price = 11253000  # ریال

price_num = digits.en_to_fa(f"{price:,}")
price_text = digits.to_word(price) + " ریال"
date_text = JalaliDate.today().strftime("%Y/%m/%d")

doc = DocxTemplate(template_path)

context = {
    "price": price_num,
    "price_text": price_text,
    "date": date_text,
}

doc.render(context)
doc.save(output_path)

print("Done")