"""
Technical and Financial Proposal (TFP) generation module.

Fills the company's Word proposal template (uploaded fresh from the UI
each time, like the Excel BOQ template) using docxtpl. The template's
placeholders use Jinja2 double-curly-brace syntax, e.g. {{ price }},
matching the context keys built in generate_proposal() below.

This reuses the same price->Persian-text logic as the standalone
TFP.py script, but takes every value as an argument instead of hard-
coding them, so it can be called from views/export.py.

Install requirement (add to requirements.txt if not already there):
    pip install docxtpl persiantools
"""

from io import BytesIO

from docxtpl import DocxTemplate
from persiantools import digits


def generate_proposal(
    template_file,
    price,
    panel_count,
    pr_number: str,
    client_name: str,
    project_type: str,
    date_str: str,
    panel_color: str = "",
    indicator_code: str = "",
    delivery_time: str = "",
    delivery_location: str = "",
):
    """
    Fills the Word proposal template with the given values and returns
    a BytesIO object ready for download.

    Args:
        template_file: path to the .docx template, or a file-like object
                        (e.g. a Streamlit UploadedFile).
        price: the panel price (a number), read from the "panel price"
               Excel file via panel_price.read_panel_price().
        panel_count: number of panels, read from the same Excel file.
        pr_number: the PR number (e.g. from the "PR Number" field on the
                   Export page, which comes from pr_tracker.add_pr_entry).
        client_name: company/client name, goes into {{ client_name }}.
        project_type: project type text, goes into {{ project_type }}.
        date_str: pre-formatted Jalali date string, e.g. "1405/05/26"
                   (matches the "Date" field already on the Export page).
        panel_color: panel color text (e.g. "RAL 7035"), goes into
                     {{ panel_color }}.
        indicator_code: indicator code text, goes into
                        {{ indicator_code }}.
        delivery_time: delivery time text (e.g. "30 روز کاری"), goes
                       into {{ delivery_time }}.
        delivery_location: delivery location text (e.g. factory
                            warehouse address), goes into
                            {{ delivery_location }}.

    Returns:
        BytesIO object containing the filled .docx file, ready for
        st.download_button.
    """
    price = int(price)
    # Same conversion as the original TFP.py: digit-grouped Persian
    # numerals for {{ price }}, and the full Persian word form for
    # {{ price_text }} (e.g. for "amount in words" on the document).
    price_num = digits.en_to_fa("ریال" + f"{price:,}")
    price_text = digits.to_word(price) + " ریال"

    doc = DocxTemplate(template_file)
    context = {
        "price": price_num,
        "price_text": price_text,
        "date": date_str,
        "PR": str(pr_number),
        "client_name": client_name,
        "project_type": project_type,
        "panel_count": panel_count,
        "panel_color": panel_color,
        "indicator_code": indicator_code,
        "delivery_time": delivery_time,
        "delivery_location": delivery_location,
    }
    doc.render(context)

    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output