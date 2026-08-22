"""
Shared constants, cached resource loaders, detection helpers, clipboard/date
helpers, and the shared UI theme/header for the multi-page Streamlit app.
"""

import base64
import os

import streamlit as st
from PIL import Image, ImageGrab
from ultralytics import YOLO
from persiantools.jdatetime import JalaliDate

from cable_ocr import build_ocr_engine

LOGO_PATH = r"C:\Users\Azar Fonoon\Desktop\farshbaf\logo.png"
MODEL_PATH = r"C:\Users\Azar Fonoon\Downloads\best.pt"
PR_FILE_PATH = r"C:\Users\Azar Fonoon\Desktop\PR - 1405.xlsx"


# ---------------------------------------------------------------------------
# UI theme
# ---------------------------------------------------------------------------
def load_css():
    """Load the application's custom CSS theme."""
    css_path = os.path.join(os.path.dirname(__file__), "assets", "styles.css")
    if not os.path.exists(css_path):
        return
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_header(subtitle: str):
    """Render a consistent product header across all pages."""
    load_css()

    logo_html = "<div class='ae-logo-placeholder'>AE</div>"
    if os.path.exists(LOGO_PATH):
        try:
            with open(LOGO_PATH, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("ascii")
            ext = os.path.splitext(LOGO_PATH)[1].lower().replace(".", "") or "png"
            if ext == "jpg":
                ext = "jpeg"
            logo_html = f"<img class='ae-logo' src='data:image/{ext};base64,{encoded}' />"
        except OSError:
            pass

    st.markdown(
        f"""
        <div class='ae-header'>
            {logo_html}
            <div>
                <div class='ae-brand'>Autodetect Electrical</div>
                <div class='ae-subtitle'>{subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def load_model():
    return YOLO(MODEL_PATH)


@st.cache_resource
def load_cable_ocr_engine():
    return build_ocr_engine()


@st.cache_data(show_spinner=False)
def _run_detection_cached(image_bytes: bytes, size, mode: str, threshold: float):
    model = load_model()
    image = Image.frombytes(mode, size, image_bytes)
    results = model.predict(image, conf=threshold, verbose=False)
    result = results[0]
    result_array = result.plot()[:, :, ::-1]
    result_image = Image.fromarray(result_array)

    detections = []
    for box in result.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        # Pixel-space box coordinates, needed by amp_ocr.py to crop the
        # area around each element and OCR the amperage written near it.
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
        detections.append({
            "class": model.names[cls_id],
            "confidence": conf,
            "box": (x1, y1, x2, y2),
        })

    return result_image, detections


def run_detection(image: Image.Image, threshold: float):
    rgb_image = image.convert("RGB")
    return _run_detection_cached(
        rgb_image.tobytes(), rgb_image.size, rgb_image.mode, threshold
    )


def get_clipboard_image():
    try:
        content = ImageGrab.grabclipboard()
        if isinstance(content, Image.Image):
            return content
        return None
    except Exception as e:
        st.error(f"Error reading clipboard: {e}")
        return None


def today_jalali_year() -> str:
    return f"{JalaliDate.today().year:04d}"


def today_jalali_string(separator: str = "/"):
    today = JalaliDate.today()
    return f"{today.year:04d}{separator}{today.month:02d}{separator}{today.day:02d}"