"""
Detection page: upload or paste electrical-panel images, run YOLO
detection, and review/edit the detected class counts.

The final edited totals are stored in st.session_state["yolo_class_totals"]
so the Export page can pick them up later.
"""

import io

import pandas as pd
import streamlit as st
from PIL import Image

from shared import load_model, run_detection, get_clipboard_image, render_header

render_header("Detect and count electrical elements")

model = load_model()

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
    # Keep any previously computed totals available to the Export page even
    # while this page has nothing selected, instead of wiping them out.
else:
    # ---------------------------
    # Thumbnail preview of all selected images before running detection
    # ---------------------------
    st.markdown("#### Selected Images")
    thumb_cols = st.columns(min(len(images_to_process), 6))
    for i, item in enumerate(images_to_process):
        with thumb_cols[i % len(thumb_cols)]:
            # Pass the full-resolution image and let Streamlit scale it
            # down to fit the column. Pre-shrinking to a small size and
            # then stretching it back up via use_container_width is what
            # caused blurry previews — downscaling a full-res image stays
            # sharp, upscaling a tiny one doesn't.
            st.image(item["image"], caption=item["name"], use_container_width=True)

    st.markdown("---")

    # ---------------------------
    # Run detection on all images with a progress bar
    # (run_detection is cached by image content + threshold, see shared.py,
    # so re-visiting this page or editing a table below won't re-run YOLO
    # on images that haven't changed)
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
    # Summary across all images, based on the EDITED counts.
    # Stored in session_state so the Export page can use it.
    # ---------------------------
    class_totals = {}
    for image_counts in edited_counts_per_image:
        for cls, count in image_counts.items():
            class_totals[cls] = class_totals.get(cls, 0) + count

    st.session_state["yolo_class_totals"] = class_totals
    st.session_state["yolo_image_count"] = len(images_to_process)

    st.markdown("#### Summary Across All Images")
    total_objects = sum(class_totals.values())
    if class_totals:
        st.write(f"Total objects found: **{total_objects}** across **{len(images_to_process)}** image(s)")
        summary_cols = st.columns(min(len(class_totals), 4))
        for i, (cls, count) in enumerate(sorted(class_totals.items(), key=lambda x: -x[1])):
            with summary_cols[i % len(summary_cols)]:
                st.metric(label=cls, value=count)
        st.info("Go to the **Export** page to write these results into the Excel BOQ template.")
    else:
        st.write("No objects found in any of the selected images.")
