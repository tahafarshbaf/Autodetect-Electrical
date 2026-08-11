"""
Script to rename files in a folder (numbered from 1 to N)

Usage:
    python rename_files.py

Then enter the folder path, file extension, and optional prefix.
"""

import os


def rename_files(folder_path: str, extension: str, prefix: str = "", start: int = 1, zero_pad: int = 0):
    """
    Rename all files with a given extension in a folder.

    folder_path: path to the folder
    extension: file extension without the dot (e.g. jpg or txt)
    prefix: base name for the new files (if empty, only the number is used)
    start: starting number (default: 1)
    zero_pad: number of digits for zero-padding (e.g. 3 -> 001, 002, ...) - 0 means no padding
    """
    extension = extension.lower().lstrip(".")

    # Find matching files and sort by current name
    files = [
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith("." + extension)
    ]
    files.sort()

    if not files:
        print(f"No files with extension .{extension} were found in this folder.")
        return

    print(f"{len(files)} file(s) found. Starting rename...\n")

    # Step 1: rename to temporary names to avoid name collisions
    temp_names = []
    for i, filename in enumerate(files):
        old_path = os.path.join(folder_path, filename)
        temp_path = os.path.join(folder_path, f"__temp_{i}__.{extension}")
        os.rename(old_path, temp_path)
        temp_names.append(temp_path)

    # Step 2: final rename with numbering
    for i, temp_path in enumerate(temp_names):
        number = start + i
        if zero_pad > 0:
            number_str = str(number).zfill(zero_pad)
        else:
            number_str = str(number)

        if prefix:
            new_name = f"{prefix}_{number_str}.{extension}"
        else:
            new_name = f"{number_str}.{extension}"
        new_path = os.path.join(folder_path, new_name)
        os.rename(temp_path, new_path)
        print(f"-> {new_name}")

    print("\nRenaming completed successfully.")


if __name__ == "__main__":
    folder = input("Enter the folder path: ").strip().strip('"').strip("'")
    ext = input("Enter the file extension (e.g. jpg): ").strip()
    base_name = input("Base name for files (press Enter for numbers only, no prefix): ").strip()

    pad_input = input("Number of digits for zero-padding (press Enter for none, e.g. 3 -> 001): ").strip()
    pad = int(pad_input) if pad_input.isdigit() else 0

    rename_files(folder, ext, base_name, start=1, zero_pad=pad)