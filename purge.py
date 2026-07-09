"""Purge transient PixelVault working directories after explicit confirmation."""

from __future__ import annotations

import shutil
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TARGET_DIRS = [
    BASE_DIR / "uploads",
    BASE_DIR / "PixelHopping" / "trash",
    BASE_DIR / "PixelHopping" / "preload",
    BASE_DIR / "PixelHopping" / "laundering",
    BASE_DIR / "encoded_png",
    BASE_DIR / "decode_uploads",
]
CONFIRMATION_TEXT = "PURGE PIXELVAULT"


def purge_directory_contents(directory: Path) -> int:
    """Delete every child inside directory while leaving the directory itself."""
    directory.mkdir(parents=True, exist_ok=True)

    deleted_count = 0
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        deleted_count += 1

    return deleted_count


def main() -> None:
    print("This will delete the entire contents of:")
    for directory in TARGET_DIRS:
        print(f" - {directory}")

    confirmation = input(f"\nType {CONFIRMATION_TEXT!r} to continue: ").strip()
    if confirmation != CONFIRMATION_TEXT:
        print("Purge cancelled.")
        return

    total_deleted = 0
    for directory in TARGET_DIRS:
        deleted_count = purge_directory_contents(directory)
        total_deleted += deleted_count
        print(f"Purged {deleted_count} item(s) from {directory}")

    print(f"\nDone. Deleted {total_deleted} item(s).")
# peepeepoopoo

if __name__ == "__main__":
    main()
