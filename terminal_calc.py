"""
Terminal size calculation module.

Company rule: the terminal size for a given wire (cable) cross-section is
one step ABOVE that wire size in the standard size table below. If the
wire size is already the largest one in the table (or larger), there is
no bigger terminal size to use, so a busbar (شینه) must be used instead
and a warning should be raised.

Import get_terminal_size() (and WIRE_SIZE_TABLE, if you need the raw list
for a dropdown) from app.py / main.py.
"""

# ---------------------------------------------------------------------------
# Standard wire cross-section sizes (mm^2), in increasing order.
# Edit this list if your standard sizes ever change.
# ---------------------------------------------------------------------------
WIRE_SIZE_TABLE = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70]


def get_terminal_size(wire_size: float):
    """
    Returns the terminal size for a given wire size, following the rule
    "the terminal size is one step above the wire size" in
    WIRE_SIZE_TABLE.

    Args:
        wire_size: the wire cross-section in mm^2. Must be one of the
                    values in WIRE_SIZE_TABLE (use snap_to_wire_size()
                    first if the value might not land exactly on a table
                    entry, e.g. raw OCR output).

    Returns:
        (terminal_size, needs_busbar):
            - terminal_size: float, or None when the wire size is already
              the largest one in the table (no terminal size applies).
            - needs_busbar: True if a busbar must be used instead of a
              terminal (wire size is at or beyond the table's range).

    Raises:
        ValueError: if wire_size is not an exact entry in WIRE_SIZE_TABLE.
    """
    try:
        index = WIRE_SIZE_TABLE.index(wire_size)
    except ValueError:
        raise ValueError(
            f"Wire size {wire_size} mm² is not one of the standard sizes "
            f"{WIRE_SIZE_TABLE}. Use snap_to_wire_size() first if the "
            f"value comes from OCR or free-text input."
        )

    if index + 1 >= len(WIRE_SIZE_TABLE):
        # Already at the largest available size -> no terminal fits, use a busbar
        return None, True

    return WIRE_SIZE_TABLE[index + 1], False


def snap_to_wire_size(value: float):
    """
    Rounds a raw numeric value UP to the nearest standard wire size in
    WIRE_SIZE_TABLE. Useful when the wire size comes from OCR or manual
    entry and might not land exactly on a table value.

    Returns None if the value is larger than the biggest standard size
    (which itself means a busbar is needed — see get_terminal_size()).
    """
    for size in WIRE_SIZE_TABLE:
        if value <= size:
            return size
    return None
