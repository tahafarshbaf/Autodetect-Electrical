"""
Shared constants, cached resource loaders, detection helpers, clipboard/date
helpers, and the shared UI theme/header for the multi-page Streamlit app.
"""

import base64
import hashlib
import os

import streamlit as st
from PIL import Image, ImageGrab
from ultralytics import YOLO
from persiantools.jdatetime import JalaliDate

from cable_ocr import build_ocr_engine
from config import LOGO_PATH, MODEL_PATH, PR_FILE_PATH


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


# ---------------------------------------------------------------------------
# Detection results cache.
#
# A plain process-wide dict instead of @st.cache_data: caching needs to
# work per-image (so an unchanged image is never re-run), but the actual
# inference call needs to happen once for a whole BATCH of images at a
# time (so the model processes them together instead of one-by-one). A
# single @st.cache_data-wrapped function can't do both at once, since
# its cache key would have to be the whole batch, which misses the cache
# entirely the moment even one new image is added to the batch.
# ---------------------------------------------------------------------------
_detection_cache: dict = {}


def _image_cache_key(image: Image.Image, threshold: float):
    """Content-based cache key: same image bytes + same threshold ->
    same key, regardless of which upload/session produced the image."""
    rgb_bytes = image.tobytes()
    digest = hashlib.sha256(rgb_bytes).hexdigest()
    return (digest, image.size, threshold)


def _process_result(model, result):
    """Turns one ultralytics Result object into (annotated_image, detections)."""
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


def run_detection_batch(images: list, threshold: float):
    """
    Runs YOLO inference on a list of PIL images in ONE batched
    model.predict() call, instead of looping and calling predict() once
    per image.

    This matters most on a GPU (and still helps some on CPU): the model
    processes the whole batch together rather than paying per-call
    overhead N times over, so for a typical multi-image panel upload
    this can noticeably cut total analysis time compared to calling
    predict() image-by-image.

    Images already analyzed at the same threshold are served straight
    from an in-process cache and excluded from the batch entirely, so
    re-running analysis on unchanged images stays instant and doesn't
    waste a model call.

    Args:
        images: list of PIL.Image objects (any mode; converted to RGB).
        threshold: confidence threshold, shared across the whole batch.

    Returns:
        List of (result_image, detections) tuples, in the same order as
        the input `images` list.
    """
    model = load_model()

    # Normalize once up front so hashing and inference both see the same
    # RGB representation of each image.
    rgb_images = [img.convert("RGB") for img in images]
    cache_keys = [_image_cache_key(img, threshold) for img in rgb_images]

    pending_indices = [i for i, key in enumerate(cache_keys) if key not in _detection_cache]

    if pending_indices:
        pending_images = [rgb_images[i] for i in pending_indices]
        # The actual batching happens here: passing a list to predict()
        # runs it as one batched forward pass instead of N separate calls.
        pending_results = model.predict(pending_images, conf=threshold, verbose=False)

        for i, result in zip(pending_indices, pending_results):
            _detection_cache[cache_keys[i]] = _process_result(model, result)

    return [_detection_cache[key] for key in cache_keys]


def run_detection(image: Image.Image, threshold: float):
    """Single-image convenience wrapper around run_detection_batch(), for
    any call site that only has one image on hand at a time."""
    return run_detection_batch([image], threshold)[0]


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