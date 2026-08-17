"""
Extract cable-size labels from single-line diagram images and expand them
into individual conductor (wire) counts, ready for the terminal-size
calculation in terminal_calc.py.

Counting rule (as confirmed for this project):
  - "AxB"   (e.g. "3x1.5")   -> A separate terminals of size B, one per
                                 conductor.
  - "AxB+C" (e.g. "3x25+16") -> A terminals of size B (the phase
                                 conductors) PLUS 1 terminal of size C
                                 (the neutral/earth conductor), counted
                                 separately because it's a different size.

This module reuses the column-splitting + rotation + OCR pipeline from
the standalone ocr.py script, but works directly on in-memory PIL images
(e.g. from a Streamlit file_uploader) instead of file paths, so it can be
called straight from the Streamlit app.

Install requirements (run once):
    pip install paddleocr paddlepaddle pillow numpy opencv-python-headless
"""

import re
import numpy as np
from PIL import Image, ImageEnhance

from terminal_calc import snap_to_wire_size

# ---------------------------------------------------------------------------
# OCR engine
# ---------------------------------------------------------------------------
# Deferred import so this module can be imported (and its parsing/expansion
# functions unit-tested) without the heavy paddleocr package installed.
# The caller (main.py) is expected to wrap this in @st.cache_resource so
# the model is only loaded once per app session.
def build_ocr_engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,  # we already rotate columns ourselves
        use_doc_unwarping=False,
        use_textline_orientation=True,       # new name for the old use_angle_cls
        enable_mkldnn=False,  # works around a known paddlepaddle 3.3.x CPU bug:
                               # "NotImplementedError: ConvertPirAttribute2RuntimeAttribute
                               # not support [pir::ArrayAttribute<pir::DoubleAttribute>]"
                               # If this still errors, downgrade instead:
                               # pip install paddlepaddle==3.2.2
    )


# ---------------------------------------------------------------------------
# Column detection + preprocessing (same approach as the standalone ocr.py)
# ---------------------------------------------------------------------------
def detect_column_bounds(gray_img: Image.Image, dark_threshold: int = 128,
                          line_score_ratio: float = 0.6) -> list[int]:
    """Finds the x-coordinates of vertical separator lines in a diagram image."""
    arr = np.array(gray_img)
    dark = (arr < dark_threshold).astype(int)
    col_sum = dark.sum(axis=0)

    threshold = col_sum.max() * line_score_ratio
    raw_line_cols = np.where(col_sum > threshold)[0]

    # merge adjacent x's that belong to the same line (e.g. 566, 567)
    lines = []
    for x in raw_line_cols:
        if not lines or x - lines[-1][-1] > 2:
            lines.append([x])
        else:
            lines[-1].append(x)
    line_positions = [int(np.mean(group)) for group in lines]

    bounds = [0] + line_positions + [gray_img.width]
    return sorted(set(bounds))


def prep_column_for_ocr(gray_img: Image.Image, x0: int, x1: int,
                         upscale: int = 3, contrast: float = 2.0,
                         bin_threshold: int = 200) -> Image.Image:
    """Crops one column, rotates it so vertical text becomes horizontal,
    then upscales + boosts contrast + binarizes for a clean OCR input."""
    crop = gray_img.crop((x0, 0, x1, gray_img.height))

    # Rotate 90 deg clockwise: if your diagrams read top-to-bottom instead
    # of bottom-to-top, change this to rotate(90).
    rotated = crop.rotate(-90, expand=True)

    w, h = rotated.size
    upscaled = rotated.resize((w * upscale, h * upscale), Image.LANCZOS)
    enhanced = ImageEnhance.Contrast(upscaled).enhance(contrast)

    arr = np.array(enhanced)
    binarized = np.where(arr < bin_threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(binarized)


# ---------------------------------------------------------------------------
# Cable label parsing
# ---------------------------------------------------------------------------
# Matches patterns like: 3x1.5, 3x25+16, 4x2.5, 3 x 25 + 16
CABLE_SIZE_PATTERN = re.compile(
    r"(\d+)\s*[xX×]\s*(\d+(?:\.\d+)?)(?:\s*\+\s*(\d+(?:\.\d+)?))?"
)


def parse_cable_labels(text: str):
    """
    Pulls all (conductor_count, main_size, extra_size) tuples out of a
    block of OCR text, e.g.:
        "3x1.5"   -> [(3, 1.5, None)]
        "3x25+16" -> [(3, 25.0, 16.0)]
    """
    parsed = []
    for m in CABLE_SIZE_PATTERN.finditer(text):
        count_str, main_str, extra_str = m.groups()
        parsed.append((
            int(count_str),
            float(main_str),
            float(extra_str) if extra_str else None,
        ))
    return parsed


def expand_to_wire_counts(parsed_labels) -> dict:
    """
    Expands parsed (conductor_count, main_size, extra_size) tuples into a
    {wire_size: terminal_count} dict, following the project's counting
    rule: "AxB" -> A terminals of size B; "AxB+C" -> A terminals of size B
    PLUS 1 terminal of size C (counted separately).

    Raw sizes are snapped UP to the nearest standard size in
    terminal_calc.WIRE_SIZE_TABLE before counting, in case OCR noise
    means a value doesn't land exactly on a table entry. Sizes larger
    than the table's max are dropped here (get_terminal_size handles
    the "needs busbar" case for terminal_calc.WIRE_SIZE_TABLE's own
    largest entry, but a size beyond the table entirely has nothing to
    snap to).
    """
    counts = {}
    for conductor_count, main_size, extra_size in parsed_labels:
        snapped_main = snap_to_wire_size(main_size)
        if snapped_main is not None:
            counts[snapped_main] = counts.get(snapped_main, 0) + conductor_count

        if extra_size is not None:
            snapped_extra = snap_to_wire_size(extra_size)
            if snapped_extra is not None:
                counts[snapped_extra] = counts.get(snapped_extra, 0) + 1

    return counts


# ---------------------------------------------------------------------------
# Full pipeline: one in-memory image -> wire size counts
# ---------------------------------------------------------------------------
def extract_wire_counts_from_image(image: Image.Image, ocr_engine) -> dict:
    """
    Runs the full pipeline (column split -> rotate -> OCR -> parse ->
    expand) on a single in-memory diagram image and returns a
    {wire_size: terminal_count} dict for that image.
    """
    gray = image.convert("L")
    bounds = detect_column_bounds(gray)

    all_parsed = []
    for i in range(len(bounds) - 1):
        x0, x1 = bounds[i], bounds[i + 1]
        if x1 - x0 < 15:
            continue  # skip slivers / noise

        col_img = prep_column_for_ocr(gray, x0, x1)
        col_np = np.array(col_img.convert("RGB"))

        # PaddleOCR 3.x: predict() returns a list of result objects, one
        # per input image, each exposing "rec_texts" (list of strings).
        results = ocr_engine.predict(col_np)
        lines = []
        for res in results:
            lines.extend(res["rec_texts"])

        full_text = " | ".join(lines)
        all_parsed.extend(parse_cable_labels(full_text))

    return expand_to_wire_counts(all_parsed)


def extract_wire_counts_from_images(images, ocr_engine) -> dict:
    """
    Runs extract_wire_counts_from_image() over several images and merges
    the results into one combined {wire_size: terminal_count} dict.
    """
    combined = {}
    for image in images:
        for size, count in extract_wire_counts_from_image(image, ocr_engine).items():
            combined[size] = combined.get(size, 0) + count
    return combined