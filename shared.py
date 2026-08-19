"""
Shared constants, cached resource loaders, and helper functions used by
every page of the multi-page app (views/detection.py, views/terminal.py,
views/export.py).

Putting these here (instead of duplicating them in each page) means the
YOLO model and the PaddleOCR engine are each loaded exactly once per
server process and reused across all pages, and the clipboard/date/logo
helpers stay consistent everywhere.
"""

import os

import streamlit as st
from PIL import Image, ImageGrab
from ultralytics import YOLO
from persiantools.jdatetime import JalaliDate

from cable_ocr import build_ocr_engine

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Put your logo file next to this script (or give a full path).
# Supported formats: png, jpg, jpeg.
LOGO_PATH = r"C:\Users\Azar Fonoon\Desktop\farshbaf\logo.png"

# Path to your YOLO model weights.
# Use a pretrained model name (auto-downloaded) like "yolov8n.pt",
# or a path to your own custom-trained .pt file, e.g. "runs/train/weights/best.pt"
MODEL_PATH = r"C:\Users\Azar Fonoon\Downloads\best.pt"

# Path to the company's PR (Price Request / Proposal) tracking Excel file.
# New entries are appended to this file from the Export page.
PR_FILE_PATH = r"C:\Users\Azar Fonoon\Desktop\PR - 1405.xlsx"


# ---------------------------------------------------------------------------
# Cached resource loaders
# ---------------------------------------------------------------------------
@st.cache_resource
def load_model():
    """Loads the YOLO model once and caches it across reruns and pages."""
    return YOLO(MODEL_PATH)


@st.cache_resource
def load_cable_ocr_engine():
    """Loads the PaddleOCR engine used for reading cable-size labels off
    single-line diagram images. Cached across reruns and pages since
    loading it is slow."""
    return build_ocr_engine()


# ---------------------------------------------------------------------------
# Cached YOLO inference
#
# Detection used to re-run on every widget interaction anywhere in the
# app (Streamlit reruns the whole script top to bottom on every
# interaction), which is why the app felt slower and slower as more
# images piled up in a session. Caching by the image's raw pixel content
# + confidence threshold means it only re-runs when one of those actually
# changes.
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _run_detection_cached(image_bytes: bytes, size, mode: str, threshold: float):
    model = load_model()
    image = Image.frombytes(mode, size, image_bytes)
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


def run_detection(image: Image.Image, threshold: float):
    """
    Runs YOLO inference on the given image and returns
    (result_image, detections), where result_image is a PIL.Image with
    boxes drawn on it and detections is a list of
    {"class": str, "confidence": float}.

    Cached on (pixel bytes, size, mode, threshold) — see
    _run_detection_cached above.
    """
    rgb_image = image.convert("RGB")
    return _run_detection_cached(
        rgb_image.tobytes(), rgb_image.size, rgb_image.mode, threshold
    )


# ---------------------------------------------------------------------------
# Clipboard image reading (used by both the Detection and Terminal pages)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Jalali (Shamsi) date helpers (used by the Export page)
#
# Both of these used to be backed by a hand-rolled gregorian_to_jalali()
# conversion. That's now replaced with persiantools.jdatetime.JalaliDate
# — the same library tfp_generator.py / TFP.py already use for the
# price-to-Persian-words conversion — so date handling is consistent
# across the whole app instead of split between a custom implementation
# and a library.
# ---------------------------------------------------------------------------
def today_jalali_year() -> str:
    """Returns just today's Jalali year, e.g. '1405'. Used to build the
    DRAW NO field (e.g. 'DRAW NO: 1405-92')."""
    return f"{JalaliDate.today().year:04d}"


def today_jalali_string(separator: str = "/"):
    """Returns today's date in Jalali calendar as 'YYYY<sep>MM<sep>DD'.
    Defaults to '/' (used by the BOQ template's date field); pass '-' for
    the PR tracking file, which uses dash-separated dates."""
    today = JalaliDate.today()
    return f"{today.year:04d}{separator}{today.month:02d}{separator}{today.day:02d}"


# ---------------------------------------------------------------------------
# Shared page header (logo + title), rendered at the top of every page for
# a consistent look across Detection / Terminal / Export.
# ---------------------------------------------------------------------------
def render_header(subtitle: str):
    """Renders the shared logo + title header used at the top of every page."""
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
        st.title("Autodetect Electrical")
        st.caption(subtitle)