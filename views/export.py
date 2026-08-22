"""
Export page.

Three connected actions:

1. Add Entry to PR Tracking File — appends a new row to the company's PR
   (Price Request) tracking file on disk (PR_FILE_PATH in shared.py).
   The PR number this produces is then offered as the default for...

2. Export to Excel — combines results from the Detection page
   (st.session_state["yolo_class_totals"]) and the Terminal page
   (st.session_state["terminal_results"]) and writes them into the
   company's BOQ template, including a "DRAW NO: <year>-<PR number>"
   field built from the PR number above.

3. Generate Word Proposal (TFP) — fills a Word proposal template
   (uploaded fresh from the UI, like the Excel template) using
   docxtpl, reusing the Client Name / Project Type / Date / PR Number
   fields already collected above, plus Panel Color / Indicator Code /
   Delivery Time / Delivery Location, plus a price and panel count
   read from a separately-uploaded "panel price" Excel file
   (panel_price.py).

Terminal results are merged into the same class_totals dict that
excel_export.fill_template() already understands, using a naming
convention that reuses fill_template's existing "split on first digit"
logic (see excel_export.split_class_name):
    "Terminal2.5mm²" -> element name "Terminal", spec "2.5mm²"
    "Busbar16mm²"     -> element name "Busbar",   spec "16mm²"
If you want Terminal/Busbar rows to sort in a specific position instead
of alphabetically after the rest, add "Terminal" and "Busbar" to
CLASS_PRIORITY_ORDER in excel_export.py.
"""

import streamlit as st

from views.excel_export import fill_template, count_pages_in_template
from pr_tracker import add_pr_entry
from panel_price import read_panel_price
from tfp_generator import generate_proposal
from shared import today_jalali_string, today_jalali_year, render_header, PR_FILE_PATH

render_header("Get a PR code and export all results to the Excel BOQ template")

yolo_class_totals = st.session_state.get("yolo_class_totals", {})
terminal_results = st.session_state.get("terminal_results", [])

# ---------------------------------------------------------------------------
# Recap of what's coming from each page, so it's clear what will be
# written before the user commits to an export.
# ---------------------------------------------------------------------------
st.markdown("#### Results Recap")
recap_col1, recap_col2 = st.columns(2)
with recap_col1:
    st.markdown("**From Detection page**")
    if yolo_class_totals:
        st.write(f"{sum(yolo_class_totals.values())} object(s) across {len(yolo_class_totals)} class(es)")
        st.dataframe(
            [{"Class": cls, "Count": count} for cls, count in sorted(yolo_class_totals.items(), key=lambda x: -x[1])],
            use_container_width=True,
        )
    else:
        st.caption("No detection results yet — visit the Detection page first.")

with recap_col2:
    st.markdown("**From Terminal page**")
    if terminal_results:
        st.write(f"{len(terminal_results)} row(s)")
        st.dataframe(terminal_results, use_container_width=True)
    else:
        st.caption("No terminal-calculation results yet — visit the Terminal page first.")

# ---------------------------------------------------------------------------
# Shared Panel / Client / Date info, used by the PR entry, the Excel
# export, and the Word proposal below.
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("#### Project Info")

info_col1, info_col2 = st.columns([1, 1])
with info_col1:
    panel_name_input = st.text_input("Panel Name", value="")
    client_name_input = st.text_input("Client Name", value="")
    panel_color_input = st.text_input(
        "Panel Color",
        value="RAL 7032",
        help="Defaults to RAL 7032 since most projects use this color. "
    )
    indicator_code_input = st.text_input(
        "Indicator Code",
        value="",
    )
with info_col2:
    project_type_input = st.text_input(
        "Project Type",
        value="",
        placeholder="e.g. Tableau, Busduct, etc.",
        key="pr_project_type",
    )

    if "date_input_value" not in st.session_state:
        st.session_state["date_input_value"] = ""

    def _set_today_jalali_date():
        """
        Callback for the 'Today (Shamsi)' button. Callbacks run BEFORE
        the script reruns and the widget is re-instantiated, so it's
        safe to write to st.session_state here (unlike doing it after
        the widget with the same key has already been created in the
        current run).
        """
        st.session_state["date_input_value"] = today_jalali_string()

    date_input = st.text_input("Date", key="date_input_value")
    st.button("Fill Today's Date (Shamsi)", on_click=_set_today_jalali_date)

    delivery_time_input = st.text_input(
        "Delivery Time",
        value="",
    )
    delivery_location_input = st.text_area(
        "Delivery Location",
        value=(
            "انبار كارخانه اين شركت واقع در جاده آذر شهر- شهرك صنعتي"
            "سليمي – خيابان 45 متري اصلي – انتهاي 30 متري چهارم شمالي"
        ),
        help="Defaults to the company factory warehouse address since "
             "most projects deliver there. Change it if this project "
             "needs a different delivery location.",
    )

# ===========================================================================
# Step 1: Add Entry to PR Tracking File
#
# Appends a new row to the PR tracking file on disk. Reuses the Client
# Name and Project Type fields above. The resulting PR number becomes
# the default for the "PR Number" field used in the Excel export and
# Word proposal below.
# ===========================================================================
st.markdown("---")
st.header("1. Add Entry to PR Tracking File")
st.caption(
    f"Appends a new row to {PR_FILE_PATH}: always right after the last "
    "row that has a PR number, using (last number + 1), regardless of "
    "any empty rows before it."
)

if st.button("Add to PR File"):
    if not client_name_input:
        st.warning("Please fill in the Client Name field above first.")
    elif not project_type_input:
        st.warning("Please fill in the Project Type field above.")
    else:
        try:
            row, pr_number = add_pr_entry(
                PR_FILE_PATH,
                project_type=project_type_input,
                customer_name=client_name_input,
                date_str=today_jalali_string(separator="-"),
            )
            st.session_state["last_pr_number"] = str(pr_number)
            st.success(
                f"Added PR #{pr_number} to row {row} of the PR tracking file."
            )
        except PermissionError:
            st.error(
                "Couldn't save the PR file — it looks like it's currently "
                "open in Excel. Please close it and try again."
            )
        except FileNotFoundError:
            st.error(
                f"PR file not found at {PR_FILE_PATH}. Check PR_FILE_PATH "
                f"in shared.py."
            )
        except Exception as e:
            st.error(f"Could not update the PR file: {e}")

# ===========================================================================
# Step 2: Export to Excel
# ===========================================================================
st.markdown("---")
st.header("2. Export to Excel")

if not yolo_class_totals and not terminal_results:
    st.info("No detection/terminal results yet — you can still use Steps 1 and 3 below.")

combined_totals = {}
busbar_sizes_present = set()

if yolo_class_totals or terminal_results:
    # Build the combined class_totals dict that goes into the Excel template.
    combined_totals = dict(yolo_class_totals)

    for row in terminal_results:
        count = row["Count"]
        if row["Terminal Size (mm²)"] == "—":
            # This wire size needs a busbar instead of a terminal.
            key = f"Busbar{row['Wire Size (mm²)']}mm²"
            busbar_sizes_present.add(row["Wire Size (mm²)"])
        else:
            key = f"Terminal{row['Terminal Size (mm²)']}mm²"
        combined_totals[key] = combined_totals.get(key, 0) + count

    if busbar_sizes_present:
        st.warning(
            "⚠️ The export below includes busbar line item(s) for wire size(s) "
            + ", ".join(f"{s} mm²" for s in sorted(busbar_sizes_present))
            + " that exceeded the terminal table range."
        )

    export_col1, export_col2 = st.columns([1, 1])
    with export_col1:
        template_file = st.file_uploader(
            "Upload your Excel template (.xlsx)",
            type=["xlsx"],
            key="template_uploader",
        )
    with export_col2:
        pr_number_input = st.text_input(
            "PR Number (for DRAW NO)",
            value=st.session_state.get("last_pr_number", ""),
            help="Auto-filled after adding a PR entry above. You can also "
                 "type a number in manually.",
        )

        page_number_input = 1
        if template_file is not None:
            try:
                total_pages = count_pages_in_template(template_file)
                template_file.seek(0)  # reset read position after inspecting it
                page_number_input = st.number_input(
                    f"Page Number (this template has {total_pages} page(s))",
                    min_value=1,
                    max_value=total_pages,
                    value=1,
                    step=1,
                )
            except Exception as e:
                st.error(f"Could not read the template's page count: {e}")

    draw_no_input = ""
    if pr_number_input.strip():
        draw_no_input = f"DRAW NO: {today_jalali_year()}-{pr_number_input.strip()}"
        st.caption(f"Will write **{draw_no_input}** into the template.")

    if template_file is not None:
        try:
            template_file.seek(0)  # reset again since it was read above
            excel_buffer = fill_template(
                template_file,
                combined_totals,
                panel_name=panel_name_input,
                date=date_input,
                client_name=client_name_input,
                draw_no=draw_no_input,
                start_page=page_number_input,
            )
            st.download_button(
                label="Download Filled Excel Report",
                data=excel_buffer,
                file_name="detection_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except ValueError as e:
            st.error(str(e))
    else:
        st.info("Upload your Excel template above to enable the export.")
else:
    # No detection/terminal data yet: still let the user type a PR number
    # manually so Step 3 (Word proposal) below can use it.
    pr_number_input = st.text_input(
        "PR Number",
        value=st.session_state.get("last_pr_number", ""),
        help="Auto-filled after adding a PR entry above. You can also "
             "type a number in manually.",
    )

# ===========================================================================
# Step 3: Generate Word Proposal (TFP)
#
# Uses the Client Name / Project Type / Date / PR Number / Panel Color /
# Indicator Code / Delivery Time / Delivery Location fields already
# collected above, plus price and panel count read from a separately
# uploaded "panel price" Excel file (see panel_price.py — it currently
# reads placeholder cells B2/B3; update those to the real cell addresses
# once confirmed).
# ===========================================================================
st.markdown("---")
st.header("3. Generate Word Proposal (TFP)")
st.caption(
    "Fills the Word template's {{ price }}, {{ price_text }}, {{ date }}, "
    "{{ PR }}, {{ client_name }}, {{ project_type }}, {{ panel_color }}, "
    "{{ indicator_code }}, {{ delivery_time }} and {{ delivery_location }} "
    "fields using the info above, plus price and panel count read from the "
    "panel price Excel file."
)

tfp_col1, tfp_col2 = st.columns([1, 1])
with tfp_col1:
    word_template_file = st.file_uploader(
        "Upload your Word template (.docx)",
        type=["docx"],
        key="word_template_uploader",
    )
with tfp_col2:
    panel_price_file = st.file_uploader(
        "Upload the Panel Price Excel file (.xlsx)",
        type=["xlsx"],
        key="panel_price_uploader",
    )

if word_template_file is not None and panel_price_file is not None:
    try:
        price, panel_count = read_panel_price(panel_price_file)
        st.caption(f"Read from panel price file: price = {price:,}, panel count = {panel_count}")

        if not pr_number_input.strip():
            st.warning("Please fill in the PR Number field above first (or add a PR entry in Step 1).")
        elif not client_name_input:
            st.warning("Please fill in the Client Name field above first.")
        elif not project_type_input:
            st.warning("Please fill in the Project Type field above first.")
        else:
            word_buffer = generate_proposal(
                word_template_file,
                price=price,
                panel_count=panel_count,
                pr_number=pr_number_input.strip(),
                client_name=client_name_input,
                project_type=project_type_input,
                date_str=date_input,
                panel_color=panel_color_input,
                indicator_code=indicator_code_input,
                delivery_time=delivery_time_input,
                delivery_location=delivery_location_input,
            )
            st.download_button(
                label="Download Word Proposal",
                data=word_buffer,
                file_name="TFP.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
    except ValueError as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Could not generate the Word proposal: {e}")
else:
    st.info("Upload both the Word template and the panel price Excel file above to enable generation.")