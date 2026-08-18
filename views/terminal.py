"""
Terminal Size & Count Calculation page.

Upload (or paste) single-line diagram images, automatically extract wire
sizes via OCR, and calculate the required terminal size for each — one
step above the wire size in the standard size table. Wire sizes beyond
the table's range are flagged: a busbar must be used instead of a
terminal.

The final results (wire size / terminal size / count / busbar note) are
stored in st.session_state["terminal_results"] so the Export page can
write them into the Excel BOQ template.
"""

import pandas as pd
import streamlit as st
from PIL import Image

from cable_ocr import extract_wire_counts_from_images
from terminal_calc import get_terminal_size, WIRE_SIZE_TABLE
from shared import load_cable_ocr_engine, get_clipboard_image, render_header

render_header("Calculate terminal size and count from cable size labels")

st.header("Terminal Size & Count Calculation")
st.caption(
    "Rule: the terminal size is one step above the wire size in the "
    "standard size table. A wire size beyond the table's range needs a "
    "busbar instead of a terminal."
)

st.markdown("**Select Images**")
terminal_col_a, terminal_col_b = st.columns([1, 1])
with terminal_col_a:
    st.markdown("**Method 1: Manual Upload**")
    terminal_uploaded_files = st.file_uploader(
        "Upload cable/wire schedule images for this section",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="terminal_calc_images",
    )

with terminal_col_b:
    st.markdown("**Method 2: Read from Clipboard**")
    st.caption("First copy an image (e.g. via Print Screen or copying a file), then click the button below.")
    st.warning(
        "Note: this button reads the clipboard of the machine running the "
        "server, not your own clipboard if you're connecting from another "
        "computer on the network. This option only works correctly when you "
        "are using the app on the same machine as the server."
    )
    if st.button("Read Latest Image from Clipboard", key="terminal_clipboard_read"):
        terminal_clipboard_image = get_clipboard_image()
        if terminal_clipboard_image is not None:
            st.session_state["terminal_clipboard_image"] = terminal_clipboard_image
            st.session_state["terminal_clipboard_version"] = (
                st.session_state.get("terminal_clipboard_version", 0) + 1
            )
            st.success("Image successfully read from clipboard.")
        else:
            st.warning("Clipboard content is not an image, or the clipboard is empty.")

    if "terminal_clipboard_image" in st.session_state:
        if st.button("Clear Clipboard Image", key="terminal_clipboard_clear"):
            del st.session_state["terminal_clipboard_image"]
            st.rerun()

# ---------------------------------------------------------------------------
# Combine uploaded files + clipboard image into one list, same pattern as
# the Detection page: {"name": ..., "image": PIL.Image}
# ---------------------------------------------------------------------------
terminal_images_to_process = []

if terminal_uploaded_files:
    for f in terminal_uploaded_files:
        f.seek(0)
        terminal_images_to_process.append({"name": f.name, "image": Image.open(f)})

if "terminal_clipboard_image" in st.session_state:
    terminal_images_to_process.append(
        {"name": "clipboard_image.png", "image": st.session_state["terminal_clipboard_image"]}
    )

if terminal_images_to_process:
    # Only re-run OCR when the set of selected images actually changes, so
    # we don't re-process (slow) on every widget interaction, and so we
    # don't clobber the user's manual edits to the table below. Uploaded
    # files are identified by (name, size); the clipboard image is
    # identified by a version counter bumped on every new clipboard read.
    upload_signature = (
        tuple(sorted((f.name, f.size) for f in (terminal_uploaded_files or []))),
        st.session_state.get("terminal_clipboard_version", 0),
    )

    if st.session_state.get("terminal_calc_images_signature") != upload_signature:
        with st.spinner("Reading wire sizes from the selected image(s)..."):
            ocr_engine = load_cable_ocr_engine()
            pil_images = [item["image"] for item in terminal_images_to_process]
            extracted_counts = extract_wire_counts_from_images(pil_images, ocr_engine)

        st.session_state["terminal_calc_images_signature"] = upload_signature

        if extracted_counts:
            st.session_state["terminal_calc_table"] = pd.DataFrame(
                [
                    {"Wire Size (mm²)": size, "Count": count}
                    for size, count in sorted(extracted_counts.items())
                ]
            )
            # Drop the data_editor's own widget state so it picks up the
            # freshly extracted table instead of stale prior edits.
            if "terminal_calc_editor" in st.session_state:
                del st.session_state["terminal_calc_editor"]
            st.success(
                f"Extracted {sum(extracted_counts.values())} conductor(s) across "
                f"{len(extracted_counts)} size(s) from the selected image(s). "
                f"You can still edit the table below."
            )
            st.rerun()
        else:
            st.warning(
                "No wire-size labels were recognized in the selected image(s). "
                "You can enter them manually below."
            )

    st.markdown("**Selected Images**")
    terminal_thumb_cols = st.columns(min(len(terminal_images_to_process), 6))
    for i, item in enumerate(terminal_images_to_process):
        with terminal_thumb_cols[i % len(terminal_thumb_cols)]:
            # Full-resolution image, same reasoning as the Detection page:
            # let st.image downscale it instead of pre-shrinking to a
            # small size and stretching that back up (which blurred it).
            st.image(item["image"], caption=item["name"], use_container_width=True)

st.markdown(
    "**Enter Wire Sizes** (read the sizes off the images above, one row per wire size)"
)

if "terminal_calc_table" not in st.session_state:
    st.session_state["terminal_calc_table"] = pd.DataFrame(
        [{"Wire Size (mm²)": WIRE_SIZE_TABLE[0], "Count": 1}]
    )

terminal_df = st.data_editor(
    st.session_state["terminal_calc_table"],
    key="terminal_calc_editor",
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Wire Size (mm²)": st.column_config.SelectboxColumn(
            "Wire Size (mm²)", options=WIRE_SIZE_TABLE, required=True
        ),
        "Count": st.column_config.NumberColumn(
            "Count", min_value=1, step=1, required=True
        ),
    },
)

terminal_result_rows = []

if not terminal_df.empty:
    busbar_warning_sizes = []

    for _, row in terminal_df.iterrows():
        wire_size = row.get("Wire Size (mm²)")
        count = row.get("Count", 0)
        if wire_size is None or pd.isna(count) or count <= 0:
            continue

        terminal_size, needs_busbar = get_terminal_size(wire_size)

        if needs_busbar:
            terminal_result_rows.append(
                {
                    "Wire Size (mm²)": wire_size,
                    "Terminal Size (mm²)": "—",
                    "Count": int(count),
                    "Note": "⚠️ Use busbar (out of range)",
                }
            )
            busbar_warning_sizes.append(wire_size)
        else:
            terminal_result_rows.append(
                {
                    "Wire Size (mm²)": wire_size,
                    "Terminal Size (mm²)": terminal_size,
                    "Count": int(count),
                    "Note": "",
                }
            )

    if terminal_result_rows:
        st.markdown("**Results**")
        terminal_result_df = pd.DataFrame(terminal_result_rows)
        st.dataframe(terminal_result_df, use_container_width=True)

        if busbar_warning_sizes:
            sizes_list = ", ".join(
                f"{s} mm²" for s in sorted(set(busbar_warning_sizes))
            )
            st.warning(
                f"⚠️ The following wire size(s) exceed the terminal table "
                f"range and require a busbar instead of a terminal: {sizes_list}"
            )

        # Totals grouped by terminal size (rows that don't need a busbar)
        terminals_needed = {}
        for r in terminal_result_rows:
            if r["Terminal Size (mm²)"] != "—":
                terminals_needed[r["Terminal Size (mm²)"]] = (
                    terminals_needed.get(r["Terminal Size (mm²)"], 0) + r["Count"]
                )

        if terminals_needed:
            st.markdown("**Total Terminals Needed (by size)**")
            totals_cols = st.columns(min(len(terminals_needed), 5))
            for i, (size, total) in enumerate(sorted(terminals_needed.items())):
                with totals_cols[i % len(totals_cols)]:
                    st.metric(label=f"{size} mm²", value=total)

        st.info("Go to the **Export** page to write these results into the Excel BOQ template.")

# Store the computed results (list of dicts) for the Export page, regardless
# of whether anything matched, so Export always reflects the latest state.
st.session_state["terminal_results"] = terminal_result_rows
