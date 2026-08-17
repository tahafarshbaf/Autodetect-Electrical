import streamlit as st
from PIL import Image, ImageGrab
from ultralytics import YOLO
from excel_export import fill_template, count_pages_in_template
from terminal_calc import get_terminal_size, WIRE_SIZE_TABLE
from cable_ocr import build_ocr_engine, extract_wire_counts_from_images
import pandas as pd
import datetime
import io
import os


def gregorian_to_jalali(g_year, g_month, g_day):
    """
    Converts a Gregorian date to the Jalali (Shamsi/Persian) calendar.
    Pure Python implementation — no internet or external library needed.
    Returns (jalali_year, jalali_month, jalali_day).
    """
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy = g_year - 1600
    gm = g_month - 1
    gd = g_day - 1

    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((g_year % 4 == 0 and g_year % 100 != 0) or (g_year % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]
    else:
        jm = 12
        jd = j_day_no + 1

    return jy, jm, jd


def today_jalali_string():
    """Returns today's date in Jalali calendar as 'YYYY/MM/DD'."""
    today = datetime.date.today()
    jy, jm, jd = gregorian_to_jalali(today.year, today.month, today.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def _set_today_jalali_date():
    """
    Callback for the 'Today (Shamsi)' button. Callbacks run BEFORE the
    script reruns and the widget is re-instantiated, so it's safe to
    write to st.session_state here (unlike doing it after the widget
    with the same key has already been created in the current run).
    """
    st.session_state["date_input_value"] = today_jalali_string()

st.set_page_config(page_title="Vision Scan", layout="wide")

# ---------------------------
# Configuration
# ---------------------------
# Put your logo file next to this script (or give a full path).
# Supported formats: png, jpg, jpeg.
LOGO_PATH = r"C:\Users\Azar Fonoon\Desktop\farshbaf\logo.png"

# Path to your YOLO model weights.
# Use a pretrained model name (auto-downloaded) like "yolov8n.pt",
# or a path to your own custom-trained .pt file, e.g. "runs/train/weights/best.pt"
MODEL_PATH = r"C:\Users\Azar Fonoon\Downloads\best.pt"


@st.cache_resource
def load_model():
    """Loads the YOLO model once and caches it across reruns."""
    return YOLO(MODEL_PATH)


@st.cache_resource
def load_cable_ocr_engine():
    """Loads the PaddleOCR engine used for reading cable-size labels off
    single-line diagram images. Cached across reruns since loading it is
    slow."""
    return build_ocr_engine()


model = load_model()

# ---------------------------
# Header with logo
# ---------------------------
header_col1, header_col2 = st.columns([1, 6])
with header_col1:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=80)
    else:
        st.markdown(
            "<div style='width:80px;height:80px;border:1px solid #ccc;"
            "display:flex;align-items:center;justify-content:center;"
            "color:#999;font-size:12px;'>LOGO</div>",
            unsafe_allow_html=True,
        )
with header_col2:
    st.title("Vision Scan")
    st.caption(f"Detect and count electrical elements")

# ---------------------------
# Sidebar settings
# ---------------------------
with st.sidebar:
    st.header("Settings")
    confidence_threshold = st.slider(
        "Confidence threshold",
        min_value=0.0,
        max_value=1.0,
        value=0.25,
        step=0.05,
    )
    st.markdown("---")
    st.info(f"Model classes: {len(model.names)}")


def run_detection(image: Image.Image, threshold: float):
    """
    Runs real YOLO inference on the given image.
    Returns (result_image, detections) where:
      - result_image is a PIL.Image with boxes drawn on it
      - detections is a list of {"class": str, "confidence": float}
    """
    results = model.predict(image, conf=threshold, verbose=False)
    result = results[0]

    # result.plot() returns a numpy array in BGR order; convert to RGB PIL image
    result_array = result.plot()[:, :, ::-1]
    result_image = Image.fromarray(result_array)

    detections = []
    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        detections.append({"class": model.names[cls_id], "confidence": conf})

    return result_image, detections


def get_clipboard_image():
    """
    Reads the latest clipboard content.
    Returns a PIL.Image object if it's an image, otherwise None.
    Note: only works when the app is run locally
    (on the same machine where the browser is open).
    """
    try:
        content = ImageGrab.grabclipboard()
        if isinstance(content, Image.Image):
            return content
        return None
    except Exception as e:
        st.error(f"Error reading clipboard: {e}")
        return None


# ---------------------------
# Image source: manual upload or clipboard
# ---------------------------
st.subheader("Select Image")

col_a, col_b = st.columns([1, 1])
with col_a:
    st.markdown("**Method 1: Manual Upload**")
    uploaded_files = st.file_uploader(
        "Choose image files",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

with col_b:
    st.markdown("**Method 2: Read from Clipboard**")
    st.caption("First copy an image (e.g. via Print Screen or copying a file), then click the button below.")
    st.warning(
        "Note: this button reads the clipboard of the machine running the "
        "server, not your own clipboard if you're connecting from another "
        "computer on the network. This option only works correctly when you "
        "are using the app on the same machine as the server."
    )
    if st.button("Read Latest Image from Clipboard"):
        clipboard_image = get_clipboard_image()
        if clipboard_image is not None:
            st.session_state["clipboard_image"] = clipboard_image
            st.success("Image successfully read from clipboard.")
        else:
            st.warning("Clipboard content is not an image, or the clipboard is empty.")

    if "clipboard_image" in st.session_state:
        if st.button("Clear Clipboard Image"):
            del st.session_state["clipboard_image"]
            st.rerun()

# ---------------------------
# Collect all images (uploaded + clipboard) into one list
# Each item: {"name": ..., "image": PIL.Image}
# ---------------------------
images_to_process = []

if uploaded_files:
    for file in uploaded_files:
        images_to_process.append({"name": file.name, "image": Image.open(file)})

if "clipboard_image" in st.session_state:
    images_to_process.append({"name": "clipboard_image.png", "image": st.session_state["clipboard_image"]})

if not images_to_process:
    st.warning("No file uploaded.")
else:
    # ---------------------------
    # Thumbnail preview of all selected images before running detection
    # ---------------------------
    st.markdown("#### Selected Images")
    thumb_cols = st.columns(min(len(images_to_process), 6))
    for i, item in enumerate(images_to_process):
        with thumb_cols[i % len(thumb_cols)]:
            # Pass the full-resolution image and let Streamlit scale it
            # down to fit the column. Pre-shrinking to a small size (e.g.
            # 120px) and then stretching it back up via use_container_width
            # is what caused the blurry preview — downscaling a full-res
            # image stays sharp, upscaling a tiny one doesn't.
            st.image(item["image"], caption=item["name"], use_container_width=True)

    st.markdown("---")

    # ---------------------------
    # Run detection on all images with a progress bar
    # ---------------------------
    progress_bar = st.progress(0, text="Starting detection...")
    all_results = []

    for idx, item in enumerate(images_to_process):
        progress_bar.progress(
            (idx) / len(images_to_process),
            text=f"Processing {item['name']} ({idx + 1}/{len(images_to_process)})...",
        )

        image = item["image"]
        result_image, detections = run_detection(image, confidence_threshold)
        all_results.append({"name": item["name"], "image": image, "result_image": result_image, "detections": detections})

    progress_bar.progress(1.0, text="Detection complete.")
    progress_bar.empty()

    st.markdown("---")

    # ---------------------------
    # Per-image results with an editable class/count table
    # ---------------------------
    st.markdown("#### Results (edit class names or counts if needed)")

    edited_counts_per_image = []

    for idx, item in enumerate(all_results):
        st.markdown(f"### Image {idx + 1}: {item['name']}")

        col1, col2 = st.columns(2)
        with col1:
            st.image(item["image"], caption="Original Image", use_container_width=True)
        with col2:
            st.image(item["result_image"], caption="Detection Result", use_container_width=True)

        # Build the initial class -> count table from raw detections
        initial_counts = {}
        for d in item["detections"]:
            initial_counts[d["class"]] = initial_counts.get(d["class"], 0) + 1

        initial_rows = [
            {"Class": cls, "Count": count}
            for cls, count in sorted(initial_counts.items(), key=lambda x: -x[1])
        ]
        initial_df = pd.DataFrame(initial_rows, columns=["Class", "Count"])

        editor_key = f"editor_{idx}_{item['name']}"

        col_edit, col_reset = st.columns([5, 1])
        with col_edit:
            st.markdown("**Detected Objects** (editable — fix class names or counts, add/remove rows as needed):")
        with col_reset:
            if st.button("Reset", key=f"reset_{editor_key}"):
                if editor_key in st.session_state:
                    del st.session_state[editor_key]
                st.rerun()

        edited_df = st.data_editor(
            initial_df,
            key=editor_key,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Class": st.column_config.TextColumn("Class", required=True),
                "Count": st.column_config.NumberColumn("Count", min_value=0, step=1, required=True),
            },
        )

        # Convert the edited table back into a class -> count dict for this image
        image_counts = {}
        for _, row in edited_df.iterrows():
            cls = str(row.get("Class", "")).strip()
            count = row.get("Count", 0)
            if cls and pd.notna(count) and count > 0:
                image_counts[cls] = image_counts.get(cls, 0) + int(count)

        edited_counts_per_image.append(image_counts)

        # Download button for result image
        buf = io.BytesIO()
        item["result_image"].save(buf, format="PNG")
        st.download_button(
            label="Download Result Image",
            data=buf.getvalue(),
            file_name=f"result_{item['name']}",
            mime="image/png",
            key=f"download_{idx}",
        )

        st.markdown("---")

    # ---------------------------
    # Summary across all images, based on the EDITED counts
    # ---------------------------
    class_totals = {}
    for image_counts in edited_counts_per_image:
        for cls, count in image_counts.items():
            class_totals[cls] = class_totals.get(cls, 0) + count

    st.markdown("#### Summary Across All Images")
    total_objects = sum(class_totals.values())
    if class_totals:
        st.write(f"Total objects found: **{total_objects}** across **{len(images_to_process)}** image(s)")
        summary_cols = st.columns(min(len(class_totals), 4))
        for i, (cls, count) in enumerate(sorted(class_totals.items(), key=lambda x: -x[1])):
            with summary_cols[i % len(summary_cols)]:
                st.metric(label=cls, value=count)

        # ---------------------------
        # Export to Excel using the company BOQ template
        # ---------------------------
        st.markdown("#### Export to Excel")

        export_col1, export_col2 = st.columns([1, 1])
        with export_col1:
            template_file = st.file_uploader(
                "Upload your Excel template (.xlsx)",
                type=["xlsx"],
                key="template_uploader",
            )
        with export_col2:
            panel_name_input = st.text_input("Panel Name", value="")
            client_name_input = st.text_input("Client Name (To:)", value="")

            if "date_input_value" not in st.session_state:
                st.session_state["date_input_value"] = ""

            date_input = st.text_input("Date", key="date_input_value")
            st.button("Fill Today's Date (Shamsi)", on_click=_set_today_jalali_date)

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

        if template_file is not None:
            try:
                template_file.seek(0)  # reset again since it was read above
                excel_buffer = fill_template(
                    template_file,
                    class_totals,
                    panel_name=panel_name_input,
                    date=date_input,
                    client_name=client_name_input,
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
        st.write("No objects found in any of the selected images.")


# ===========================================================================
# Terminal Size & Count Calculation
#
# This section is independent from the object-detection section above: it
# has its own image uploader (for cable schedule / single-line diagram
# images) and always shows, regardless of whether detection was run above.
#
# Rule: the terminal size is one step above the wire size in the standard
# size table (see terminal_calc.WIRE_SIZE_TABLE). Any wire size beyond the
# table's range needs a busbar instead of a terminal, and gets flagged
# with a warning.
# ===========================================================================
st.markdown("---")
st.header("Terminal Size & Count Calculation")
st.caption(
    "Rule: the terminal size is one step above the wire size in the "
    "standard size table. A wire size beyond the table's range needs a "
    "busbar instead of a terminal."
)

st.markdown("**Select Images**")
terminal_col_a, terminal_col_b = st.columns([1, 1])
with terminal_col_a:
    st.markdown("**Method 1: Manual Upload**")
    terminal_uploaded_files = st.file_uploader(
        "Upload cable/wire schedule images for this section",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="terminal_calc_images",
    )

with terminal_col_b:
    st.markdown("**Method 2: Read from Clipboard**")
    st.caption("First copy an image (e.g. via Print Screen or copying a file), then click the button below.")
    st.warning(
        "Note: this button reads the clipboard of the machine running the "
        "server, not your own clipboard if you're connecting from another "
        "computer on the network. This option only works correctly when you "
        "are using the app on the same machine as the server."
    )
    if st.button("Read Latest Image from Clipboard", key="terminal_clipboard_read"):
        terminal_clipboard_image = get_clipboard_image()
        if terminal_clipboard_image is not None:
            st.session_state["terminal_clipboard_image"] = terminal_clipboard_image
            st.session_state["terminal_clipboard_version"] = (
                st.session_state.get("terminal_clipboard_version", 0) + 1
            )
            st.success("Image successfully read from clipboard.")
        else:
            st.warning("Clipboard content is not an image, or the clipboard is empty.")

    if "terminal_clipboard_image" in st.session_state:
        if st.button("Clear Clipboard Image", key="terminal_clipboard_clear"):
            del st.session_state["terminal_clipboard_image"]
            st.rerun()

# ---------------------------------------------------------------------------
# Combine uploaded files + clipboard image into one list, same pattern as
# the YOLO section above: {"name": ..., "image": PIL.Image}
# ---------------------------------------------------------------------------
terminal_images_to_process = []

if terminal_uploaded_files:
    for f in terminal_uploaded_files:
        f.seek(0)
        terminal_images_to_process.append({"name": f.name, "image": Image.open(f)})

if "terminal_clipboard_image" in st.session_state:
    terminal_images_to_process.append(
        {"name": "clipboard_image.png", "image": st.session_state["terminal_clipboard_image"]}
    )

if terminal_images_to_process:
    # Only re-run OCR when the set of selected images actually changes, so
    # we don't re-process (slow) on every widget interaction, and so we
    # don't clobber the user's manual edits to the table below. Uploaded
    # files are identified by (name, size); the clipboard image is
    # identified by a version counter bumped on every new clipboard read.
    upload_signature = (
        tuple(sorted((f.name, f.size) for f in (terminal_uploaded_files or []))),
        st.session_state.get("terminal_clipboard_version", 0),
    )

    if st.session_state.get("terminal_calc_images_signature") != upload_signature:
        with st.spinner("Reading wire sizes from the selected image(s)..."):
            ocr_engine = load_cable_ocr_engine()
            pil_images = [item["image"] for item in terminal_images_to_process]
            extracted_counts = extract_wire_counts_from_images(pil_images, ocr_engine)

        st.session_state["terminal_calc_images_signature"] = upload_signature

        if extracted_counts:
            st.session_state["terminal_calc_table"] = pd.DataFrame(
                [
                    {"Wire Size (mm²)": size, "Count": count}
                    for size, count in sorted(extracted_counts.items())
                ]
            )
            # Drop the data_editor's own widget state so it picks up the
            # freshly extracted table instead of stale prior edits.
            if "terminal_calc_editor" in st.session_state:
                del st.session_state["terminal_calc_editor"]
            st.success(
                f"Extracted {sum(extracted_counts.values())} conductor(s) across "
                f"{len(extracted_counts)} size(s) from the selected image(s). "
                f"You can still edit the table below."
            )
            st.rerun()
        else:
            st.warning(
                "No wire-size labels were recognized in the selected image(s). "
                "You can enter them manually below."
            )

    st.markdown("**Selected Images**")
    terminal_thumb_cols = st.columns(min(len(terminal_images_to_process), 6))
    for i, item in enumerate(terminal_images_to_process):
        with terminal_thumb_cols[i % len(terminal_thumb_cols)]:
            # Full-resolution image, same reasoning as the YOLO section
            # above: let st.image downscale it instead of pre-shrinking
            # to 120px and stretching that back up (which blurred it).
            st.image(item["image"], caption=item["name"], use_container_width=True)

st.markdown(
    "**Enter Wire Sizes** (read the sizes off the images above, one row per wire size)"
)

if "terminal_calc_table" not in st.session_state:
    st.session_state["terminal_calc_table"] = pd.DataFrame(
        [{"Wire Size (mm²)": WIRE_SIZE_TABLE[0], "Count": 1}]
    )

terminal_df = st.data_editor(
    st.session_state["terminal_calc_table"],
    key="terminal_calc_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Wire Size (mm²)": st.column_config.SelectboxColumn(
            "Wire Size (mm²)", options=WIRE_SIZE_TABLE, required=True
        ),
        "Count": st.column_config.NumberColumn(
            "Count", min_value=1, step=1, required=True
        ),
    },
)

if not terminal_df.empty:
    terminal_result_rows = []
    busbar_warning_sizes = []

    for _, row in terminal_df.iterrows():
        wire_size = row.get("Wire Size (mm²)")
        count = row.get("Count", 0)
        if wire_size is None or pd.isna(count) or count <= 0:
            continue

        terminal_size, needs_busbar = get_terminal_size(wire_size)

        if needs_busbar:
            terminal_result_rows.append(
                {
                    "Wire Size (mm²)": wire_size,
                    "Terminal Size (mm²)": "—",
                    "Count": int(count),
                    "Note": "⚠️ Use busbar (out of range)",
                }
            )
            busbar_warning_sizes.append(wire_size)
        else:
            terminal_result_rows.append(
                {
                    "Wire Size (mm²)": wire_size,
                    "Terminal Size (mm²)": terminal_size,
                    "Count": int(count),
                    "Note": "",
                }
            )

    if terminal_result_rows:
        st.markdown("**Results**")
        terminal_result_df = pd.DataFrame(terminal_result_rows)
        st.dataframe(terminal_result_df, use_container_width=True)

        if busbar_warning_sizes:
            sizes_list = ", ".join(
                f"{s} mm²" for s in sorted(set(busbar_warning_sizes))
            )
            st.warning(
                f"⚠️ The following wire size(s) exceed the terminal table "
                f"range and require a busbar instead of a terminal: {sizes_list}"
            )

        # Totals grouped by terminal size (rows that don't need a busbar)
        terminals_needed = {}
        for r in terminal_result_rows:
            if r["Terminal Size (mm²)"] != "—":
                terminals_needed[r["Terminal Size (mm²)"]] = (
                    terminals_needed.get(r["Terminal Size (mm²)"], 0) + r["Count"]
                )

        if terminals_needed:
            st.markdown("**Total Terminals Needed (by size)**")
            totals_cols = st.columns(min(len(terminals_needed), 5))
            for i, (size, total) in enumerate(sorted(terminals_needed.items())):
                with totals_cols[i % len(totals_cols)]:
                    st.metric(label=f"{size} mm²", value=total)