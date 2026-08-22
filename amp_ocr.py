"""
Extracts the amperage (or other numeric rating) written near a
YOLO-detected element box, and builds/decodes the composite class-name
keys used to keep per-amperage counts separate through the rest of the
pipeline (detection.py -> excel_export.py).

Since the number's position relative to the box can vary (below,
beside, overlapping, etc.), this module expands the detected box by a
margin in every direction and runs OCR on that expanded crop, rather
than assuming a fixed side. If more than one number turns up in the
expanded crop (e.g. a neighboring element's rating leaking in), the one
OCR was most confident about is kept.
"""

import re
import numpy as np
from PIL import Image

# Matches "63A", "63 A", "100A", or a bare number like "63"
AMPERAGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*A?\b", re.IGNORECASE)

# Separator used to attach an amperage reading to a YOLO class name, e.g.
# "MCB3P" + amperage "63" -> "MCB3P__63A". Kept separate from the digit
# that already starts the class's spec (e.g. "3P") so excel_export.py's
# split_class_name() can tell the two apart.
AMPERAGE_KEY_SEPARATOR = "__"


def expand_box(box, margin_ratio: float, image_size, min_margin_px: int = 25):
    """
    Expands a (x1, y1, x2, y2) box by margin_ratio * box_width/height in
    every direction (or min_margin_px, whichever is larger), clamped to
    the image bounds.

    min_margin_px exists because margin_ratio alone gives very little
    absolute space around small boxes (e.g. a 30x30px element), which can
    crop off part of the amperage text or leave too little context for
    PaddleOCR's text-detection stage to localize it reliably.
    """
    x1, y1, x2, y2 = box
    width, height = x2 - x1, y2 - y1
    margin_x = max(width * margin_ratio, min_margin_px)
    margin_y = max(height * margin_ratio, min_margin_px)

    img_w, img_h = image_size
    ex1 = max(0, x1 - margin_x)
    ey1 = max(0, y1 - margin_y)
    ex2 = min(img_w, x2 + margin_x)
    ey2 = min(img_h, y2 + margin_y)
    return int(ex1), int(ey1), int(ex2), int(ey2)


def prep_crop_for_ocr(image: Image.Image, upscale: int = 3) -> Image.Image:
    """
    Upscales a small crop so tiny text is easier for OCR to resolve.
    Deliberately does NOT force contrast enhancement or binarization —
    testing showed PaddleOCR's own preprocessing handles small crops
    better than a fixed manual contrast/threshold, which can hurt
    accuracy on regions whose local brightness varies.
    """
    gray = image.convert("L")
    w, h = gray.size
    return gray.resize((w * upscale, h * upscale), Image.LANCZOS)


def parse_amperage(text: str):
    """Returns the first numeric value found in text, or None if nothing matches."""
    match = AMPERAGE_PATTERN.search(text)
    return match.group(1) if match else None


def extract_amperage_near_box(image: Image.Image, box, ocr_engine, margin_ratio: float = 0.6):
    """
    Expands the given box by margin_ratio in all directions (plus a
    minimum absolute pixel padding — see expand_box()), runs OCR on the
    expanded crop, and returns the best-guess amperage string (e.g.
    "63"), or None if no number was recognized.

    Args:
        image: the full original PIL image the detection came from.
        box: (x1, y1, x2, y2) in pixel coordinates, as returned by YOLO.
        ocr_engine: a PaddleOCR instance (reuse load_cable_ocr_engine()).
        margin_ratio: how far to expand the box relative to its own size,
                      in every direction. Increase this if the number is
                      often missed; decrease it if a neighboring
                      element's number gets picked up by mistake.

    Returns:
        The recognized amperage value as a string (e.g. "63"), or None.
    """
    crop_box = expand_box(box, margin_ratio, image.size)
    crop = image.crop(crop_box)
    if crop.width < 2 or crop.height < 2:
        return None

    prepped = prep_crop_for_ocr(crop)
    crop_np = np.array(prepped.convert("RGB"))

    results = ocr_engine.predict(crop_np)
    candidates = []
    for res in results:
        for text, score in zip(res["rec_texts"], res["rec_scores"]):
            value = parse_amperage(text)
            if value is not None:
                candidates.append((value, score))

    if not candidates:
        return None

    # If several numbers were found in the expanded crop (e.g. a
    # neighboring element's rating), keep the most confident one.
    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[0][0]


def extract_amperages_for_detections(image: Image.Image, detections: list, ocr_engine, margin_ratio: float = 0.6):
    """
    Runs extract_amperage_near_box() for every detection in `detections`
    (each dict must have a "box" key: (x1, y1, x2, y2)) and returns a new
    list of detection dicts with an added "amperage" key.
    """
    enriched = []
    for detection in detections:
        amperage = extract_amperage_near_box(image, detection["box"], ocr_engine, margin_ratio)
        enriched.append({**detection, "amperage": amperage})
    return enriched


def build_class_key(class_name: str, amperage) -> str:
    """
    Builds the composite key used to keep per-amperage counts separate in
    a class_totals dict, e.g.:
        build_class_key("MCB3P", "63") -> "MCB3P__63A"
        build_class_key("MCB3P", "")   -> "MCB3P"   (unchanged)

    excel_export.split_class_name() decodes this back into a spec string
    like "3P 63A" when filling the BOQ template.
    """
    amperage_str = str(amperage).strip() if amperage else ""
    if not amperage_str:
        return class_name
    if not amperage_str.upper().endswith("A"):
        amperage_str = f"{amperage_str}A"
    return f"{class_name}{AMPERAGE_KEY_SEPARATOR}{amperage_str}"