import streamlit as st
from PIL import Image, ImageGrab
from ultralytics import YOLO
from excel_export import fill_template
import io
import os

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
    st.caption(f"Using YOLO model: {MODEL_PATH}")

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
    st.warning("Please upload an image or read one from the clipboard.")
else:
    # ---------------------------
    # Thumbnail preview of all selected images before running detection
    # ---------------------------
    st.markdown("#### Selected Images")
    thumb_cols = st.columns(min(len(images_to_process), 6))
    for i, item in enumerate(images_to_process):
        with thumb_cols[i % len(thumb_cols)]:
            thumbnail = item["image"].copy()
            thumbnail.thumbnail((120, 120))
            st.image(thumbnail, caption=item["name"], use_container_width=True)

    st.markdown("---")

    # ---------------------------
    # Run detection on all images with a progress bar
    # ---------------------------
    progress_bar = st.progress(0, text="Starting detection...")
    all_results = []
    class_totals = {}  # class name -> total count across all images

    for idx, item in enumerate(images_to_process):
        progress_bar.progress(
            (idx) / len(images_to_process),
            text=f"Processing {item['name']} ({idx + 1}/{len(images_to_process)})...",
        )

        image = item["image"]
        result_image, detections = run_detection(image, confidence_threshold)
        all_results.append({"name": item["name"], "image": image, "result_image": result_image, "detections": detections})

        for d in detections:
            class_totals[d["class"]] = class_totals.get(d["class"], 0) + 1

    progress_bar.progress(1.0, text="Detection complete.")
    progress_bar.empty()

    # ---------------------------
    # Summary of detections across all images
    # ---------------------------
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
            date_input = st.text_input("Date", value="")

        if template_file is not None:
            try:
                excel_buffer = fill_template(
                    template_file,
                    class_totals,
                    panel_name=panel_name_input,
                    date=date_input,
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

    st.markdown("---")

    # ---------------------------
    # Per-image results
    # ---------------------------
    for idx, item in enumerate(all_results):
        st.markdown(f"### Image {idx + 1}: {item['name']}")

        col1, col2 = st.columns(2)
        with col1:
            st.image(item["image"], caption="Original Image", use_container_width=True)
        with col2:
            st.image(item["result_image"], caption="Detection Result", use_container_width=True)

        # Detected objects list
        detections = item["detections"]
        if detections:
            st.markdown("**Detected Objects:**")
            for d in detections:
                st.write(f"- {d['class']}  —  confidence: {d['confidence'] * 100:.1f}%")
        else:
            st.write("No objects found above this confidence threshold.")

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