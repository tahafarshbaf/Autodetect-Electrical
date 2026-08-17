"""
OCR test script using PaddleOCR (v3.x API).

Install requirements:
    pip install paddlepaddle paddleocr
    # First run will download model weights automatically.
    # Note: PaddleOCR does not support Persian directly; "en" and "ch" (Chinese)
    # are among its best-supported languages.

Usage:
    python ocr_paddleocr.py
    (edit IMAGE_PATH below to point to your image)
"""

import re
import time
from paddleocr import PaddleOCR

# ==== EDIT THIS ====
IMAGE_PATH = r"C:\Users\Azar Fonoon\Desktop\test7.png"
LANG = "en"
CONFIDENCE_THRESHOLD = 0.35  # only keep results with confidence >= this value (0.0 - 1.0)
# ====================


def extract_text(image_path: str, lang: str = "en"):
    """Extract text from an image. Returns a list of (text, confidence) tuples."""
    ocr = PaddleOCR(
        lang=lang,
        text_detection_model_name="PP-OCRv6_small_det",  # lighter/faster than the default medium model
        text_recognition_model_name="PP-OCRv6_small_rec",  # lighter/faster than the default medium model
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,  # skip if your text is always upright
        enable_mkldnn=False,  # workaround for a oneDNN/PIR bug in paddlepaddle 3.3.0 on some CPUs
    )
    result = ocr.predict(image_path)

    extracted = []
    for res in result:
        texts = res["rec_texts"]
        scores = res["rec_scores"]
        extracted.extend(zip(texts, scores))
    return extracted


def filter_by_confidence(results, threshold: float):
    """Keep only results whose confidence score is >= threshold."""
    return [(text, conf) for text, conf in results if conf >= threshold]


def extract_digits(results):
    """Filter extracted text down to digit sequences only."""
    digits_found = []
    for text, _conf in results:
        digits_found.extend(re.findall(r"\d+", text))
    return digits_found


def main():
    print("=== PaddleOCR ===")
    print(f"Image: {IMAGE_PATH}")
    print(f"Language: {LANG}\n")

    start = time.time()
    results = extract_text(IMAGE_PATH, lang=LANG)
    elapsed = time.time() - start

    results = filter_by_confidence(results, CONFIDENCE_THRESHOLD)

    print(f"--- Detected text (confidence >= {CONFIDENCE_THRESHOLD}) ---")
    if not results:
        print("(no text detected)")
    for text, conf in results:
        print(f"[{conf:.2f}] {text}")

    print("\n--- Digits only ---")
    digits = extract_digits(results)
    print(", ".join(digits) if digits else "(no digits detected)")

    print(f"\nProcessing time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()