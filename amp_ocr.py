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


def extract_amperage_near_box(image: Image.Image, box, ocr_engine, margin_ratio: float = 0.6,
                               min_confidence: float = 0.5):
    """
    Expands the given box by margin_ratio in all directions (plus a
    minimum absolute pixel padding — see expand_box()), runs OCR on the
    expanded crop, and returns the best-guess amperage string (e.g.
    "63"), or None if no number was recognized with enough confidence.

    Candidate numbers are ranked by a combination of OCR confidence AND
    physical distance from the actual detected element within the crop
    — not confidence alone. On a densely-packed panel, a neighboring
    element's rating often sits well inside the expanded crop too, and
    can easily have a *higher* raw OCR confidence than the real target's
    number (better lighting, less overlap, clearer font). Weighting by
    proximity makes the reading actually attached to this element win
    even when a neighbor's text was read more "confidently" - this is
    the main source of readings getting attached to the wrong element
    when many detections are OCR'd together.

    Args:
        image: the full original PIL image the detection came from.
        box: (x1, y1, x2, y2) in pixel coordinates, as returned by YOLO.
        ocr_engine: a PaddleOCR instance (reuse load_cable_ocr_engine()).
        margin_ratio: how far to expand the box relative to its own size,
                      in every direction. Increase this if the number is
                      often missed; decrease it if a neighboring
                      element's number gets picked up by mistake.
        min_confidence: minimum RAW OCR confidence (0-1) the winning
                         candidate must have to be accepted at all. Below
                         this, None is returned instead of a guess - a
                         blank amperage the user fills in by hand is
                         safer than a wrong one, since a wrong reading
                         silently splits what should be one equipment
                         count into multiple "different" BOQ line items
                         (see build_class_key).

    Returns:
        The recognized amperage value as a string (e.g. "63"), or None.
    """
    crop_box = expand_box(box, margin_ratio, image.size)
    crop = image.crop(crop_box)
    if crop.width < 2 or crop.height < 2:
        return None

    prepped = prep_crop_for_ocr(crop)
    crop_np = np.array(prepped.convert("RGB"))

    # Where the actual YOLO box sits within this crop, in the SAME
    # upscaled coordinate space prep_crop_for_ocr() produced - used below
    # to measure how close each candidate text is to the real element,
    # rather than trusting OCR confidence alone.
    upscale_x = prepped.width / crop.width
    upscale_y = prepped.height / crop.height
    ex1, ey1, ex2, ey2 = crop_box
    x1, y1, x2, y2 = box
    target_center = (
        (x1 - ex1 + (x2 - x1) / 2) * upscale_x,
        (y1 - ey1 + (y2 - y1) / 2) * upscale_y,
    )
    crop_diagonal = (prepped.width ** 2 + prepped.height ** 2) ** 0.5

    results = ocr_engine.predict(crop_np)
    candidates = []
    for res in results:
        texts = res["rec_texts"]
        scores = res["rec_scores"]
        # rec_boxes: array of [x_min, y_min, x_max, y_max] per recognized
        # text, same order as rec_texts/rec_scores. Older PaddleOCR
        # builds may not include it - degrade gracefully to
        # confidence-only ranking (the previous behavior) if so.
        boxes = res.get("rec_boxes")

        for i, (text, score) in enumerate(zip(texts, scores)):
            value = parse_amperage(text)
            if value is None:
                continue

            if boxes is not None and i < len(boxes):
                bx1, by1, bx2, by2 = boxes[i]
                text_center = ((bx1 + bx2) / 2, (by1 + by2) / 2)
                distance = (
                    (text_center[0] - target_center[0]) ** 2
                    + (text_center[1] - target_center[1]) ** 2
                ) ** 0.5
                proximity = max(0.0, 1 - distance / crop_diagonal)
                ranking_score = score * proximity
            else:
                ranking_score = score

            candidates.append({"value": value, "raw_score": score, "ranking_score": ranking_score})

    if not candidates:
        return None

    # Proximity decides which candidate wins when several numbers are in
    # the crop, but acceptance is judged on that winner's RAW OCR
    # confidence - a nearby-but-illegible reading shouldn't be accepted
    # just because nothing else was closer.
    candidates.sort(key=lambda c: c["ranking_score"], reverse=True)
    best = candidates[0]
    if best["raw_score"] < min_confidence:
        return None

    return best["value"]


def extract_amperages_for_detections(image: Image.Image, detections: list, ocr_engine, margin_ratio: float = 0.6,
                                      min_confidence: float = 0.5):
    """
    Runs extract_amperage_near_box() for every detection in `detections`
    (each dict must have a "box" key: (x1, y1, x2, y2)) and returns a new
    list of detection dicts with an added "amperage" key.
    """
    enriched = []
    for detection in detections:
        amperage = extract_amperage_near_box(
            image, detection["box"], ocr_engine, margin_ratio, min_confidence
        )
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