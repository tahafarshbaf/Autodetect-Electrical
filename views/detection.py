"""Modern Detection page for electrical-panel image analysis."""

import io

import pandas as pd
import streamlit as st
from PIL import Image

from amp_ocr import extract_amperages_for_detections, build_class_key
from shared import load_model, run_detection, get_clipboard_image, render_header, load_cable_ocr_engine

render_header("AI-powered detection, counting and review of electrical equipment")

model = load_model()

with st.sidebar:
    st.markdown("## Analysis Settings")
    confidence_threshold = st.slider(
        "Confidence threshold", 0.0, 1.0, 0.25, 0.05,
        help="Higher values reduce low-confidence detections."
    )
    st.divider()
    read_amperage = st.checkbox(
        "Also read amperage near each element (OCR)",
        value=False,
        help="Slower — runs OCR on the area around every detected box to "
             "read the amperage rating written next to it.",
    )
    amperage_margin_ratio = 0.6
    if read_amperage:
        amperage_margin_ratio = st.slider(
            "Amperage search radius (relative to box size)",
            0.1, 2.0, 0.6, 0.1,
            help="How far around each detected box to look for the "
                 "amperage number. Increase if numbers are being missed; "
                 "decrease if a neighboring element's number gets picked "
                 "up by mistake.",
        )
    st.divider()
    st.metric("Model classes", len(model.names))
    st.caption("YOLO inference runs locally with the configured model.")

# ---------------------------------------------------------------------------
# Upload / clipboard workspace
# ---------------------------------------------------------------------------
st.markdown("## 1. Add panel images")
source_left, source_right = st.columns(2)

with source_left:
    with st.container(border=True):
        st.markdown("### Upload images")
        uploaded_files = st.file_uploader(
            "JPG, JPEG or PNG",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        st.caption("You can analyze multiple panel images in one run.")

with source_right:
    with st.container(border=True):
        st.markdown("### Clipboard")
        st.caption("Copy a panel image, then bring it directly into the workspace.")
        if st.button("Read image from clipboard", use_container_width=True):
            clipboard_image = get_clipboard_image()
            if clipboard_image is not None:
                st.session_state["clipboard_image"] = clipboard_image
                st.success("Clipboard image added.")
            else:
                st.warning("The clipboard does not contain an image.")
        if "clipboard_image" in st.session_state:
            if st.button("Remove clipboard image", use_container_width=True):
                del st.session_state["clipboard_image"]
                st.rerun()

images_to_process = []
if uploaded_files:
    for file in uploaded_files:
        images_to_process.append({"name": file.name, "image": Image.open(file)})
if "clipboard_image" in st.session_state:
    images_to_process.append({"name": "clipboard_image.png", "image": st.session_state["clipboard_image"]})

if not images_to_process:
    st.markdown("## 2. Ready when you are")
    st.info("Add one or more panel images above to start the analysis.")
    st.stop()

st.markdown("## 2. Review input")
preview_cols = st.columns(min(len(images_to_process), 4))
for i, item in enumerate(images_to_process):
    with preview_cols[i % len(preview_cols)]:
        with st.container(border=True):
            st.image(item["image"], use_container_width=True)
            st.caption(item["name"])

st.markdown("## 3. Analyze")
if st.button("Analyze panel images", type="primary", use_container_width=True):
    progress = st.progress(0, text="Preparing YOLO analysis...")
    all_results = []

    ocr_engine = load_cable_ocr_engine() if read_amperage else None

    for idx, item in enumerate(images_to_process):
        progress.progress(
            idx / len(images_to_process),
            text=f"Analyzing {item['name']} ({idx + 1}/{len(images_to_process)})...",
        )
        result_image, detections = run_detection(item["image"], confidence_threshold)

        if read_amperage:
            detections = extract_amperages_for_detections(
                item["image"], detections, ocr_engine, margin_ratio=amperage_margin_ratio
            )

        all_results.append({
            "name": item["name"],
            "image": item["image"],
            "result_image": result_image,
            "detections": detections,
        })

    progress.progress(1.0, text="Analysis complete.")
    progress.empty()
    st.session_state["detection_results"] = all_results
    st.session_state["detection_threshold"] = confidence_threshold

results = st.session_state.get("detection_results")
if not results:
    st.info("Click **Analyze panel images** to run detection.")
    st.stop()

st.markdown("## 4. Review detection results")

edited_counts_per_image = []
for idx, item in enumerate(results):
    with st.container(border=True):
        st.markdown(f"### {item['name']}")
        image_col, result_col = st.columns(2)
        with image_col:
            st.image(item["image"], caption="Original", use_container_width=True)
        with result_col:
            st.image(item["result_image"], caption="AI detection", use_container_width=True)

        # Amperage is per-instance (each physical element can carry a
        # different rating), so whenever amperage data is available for
        # this image, group counts by (class, amperage) instead of by
        # class alone.
        has_amperage_data = any("amperage" in d for d in item["detections"])

        initial_counts = {}
        for detection in item["detections"]:
            cls = detection["class"]
            amperage = (detection.get("amperage") or "") if has_amperage_data else ""
            key = (cls, amperage)
            initial_counts[key] = initial_counts.get(key, 0) + 1

        if has_amperage_data:
            initial_df = pd.DataFrame(
                [
                    {"Class": cls, "Amperage": amperage, "Count": count}
                    for (cls, amperage), count in sorted(initial_counts.items(), key=lambda x: -x[1])
                ],
                columns=["Class", "Amperage", "Count"],
            )
        else:
            initial_df = pd.DataFrame(
                [
                    {"Class": cls, "Count": count}
                    for (cls, _amperage), count in sorted(initial_counts.items(), key=lambda x: -x[1])
                ],
                columns=["Class", "Count"],
            )

        editor_key = f"editor_{idx}_{item['name']}"

        edit_col, action_col = st.columns([4, 1])
        with edit_col:
            st.caption("Verify the AI result. You can rename, add, remove or correct quantities.")
        with action_col:
            if st.button("Reset", key=f"reset_{editor_key}", use_container_width=True):
                st.session_state.pop(editor_key, None)
                st.rerun()

        column_config = {
            "Class": st.column_config.TextColumn("Equipment", required=True),
            "Count": st.column_config.NumberColumn("Quantity", min_value=0, step=1, required=True),
        }
        if has_amperage_data:
            column_config["Amperage"] = st.column_config.TextColumn(
                "Amperage", help="Leave blank if the rating wasn't read correctly."
            )

        edited_df = st.data_editor(
            initial_df,
            key=editor_key,
            num_rows="dynamic",
            use_container_width=True,
            column_config=column_config,
        )

        image_counts = {}
        for _, row in edited_df.iterrows():
            cls = str(row.get("Class", "")).strip()
            count = row.get("Count", 0)
            amperage = str(row.get("Amperage", "") or "").strip() if has_amperage_data else ""
            if cls and pd.notna(count) and count > 0:
                key = build_class_key(cls, amperage)
                image_counts[key] = image_counts.get(key, 0) + int(count)
        edited_counts_per_image.append(image_counts)

        buffer = io.BytesIO()
        item["result_image"].save(buffer, format="PNG")
        st.download_button(
            "Download annotated image",
            buffer.getvalue(),
            f"result_{item['name']}",
            "image/png",
            key=f"download_{idx}",
        )

class_totals = {}
for image_counts in edited_counts_per_image:
    for cls, count in image_counts.items():
        class_totals[cls] = class_totals.get(cls, 0) + count

st.session_state["yolo_class_totals"] = class_totals
st.session_state["yolo_image_count"] = len(results)

st.markdown("## 5. Analysis summary")
total_objects = sum(class_totals.values())
summary_a, summary_b, summary_c = st.columns(3)
with summary_a:
    st.metric("Images analyzed", len(results))
with summary_b:
    st.metric("Objects detected", total_objects)
with summary_c:
    st.metric("Equipment types", len(class_totals))

if class_totals:
    st.markdown("### Equipment quantities")
    metric_cols = st.columns(min(max(len(class_totals), 1), 4))
    for i, (cls, count) in enumerate(sorted(class_totals.items(), key=lambda x: -x[1])):
        with metric_cols[i % len(metric_cols)]:
            st.metric(cls, count)

    st.success("Detection results are ready. Continue to **Terminal** or **Export & Reports** from the top navigation.")
else:
    st.warning("No equipment remains in the reviewed results.")