#!/usr/bin/env python3
"""Build script for Bury Explain.

Zips the *contents* of src/bury_explain/ (files at the zip root, not nested
inside a folder, since AnkiWeb requires this layout) into dist/bury_explain.ankiaddon.

Stdlib only. Run with: python3 build.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src" / "bury_explain"
DIST_DIR = REPO_ROOT / "dist"
OUTPUT_PATH = DIST_DIR / "bury_explain.ankiaddon"
CONFIG_PATH = SRC_DIR / "config.json"

EXCLUDED_DIR_NAMES = {"__pycache__", "user_files"}
EXCLUDED_FILE_NAMES = {"meta.json"}


def write_config_json() -> None:
    """Regenerate config.json from logic.DEFAULT_CONFIG so the two never drift."""
    sys.path.insert(0, str(SRC_DIR))
    import logic  # noqa: E402  (import after sys.path insert, stdlib-only module)

    CONFIG_PATH.write_text(
        json.dumps(logic.DEFAULT_CONFIG, indent=4) + "\n", encoding="utf-8"
    )


def is_excluded(path: Path) -> bool:
    """Return True if any path component should exclude this file."""
    for part in path.parts:
        if part in EXCLUDED_DIR_NAMES:
            return True
        if part.startswith("."):
            return True
    if path.suffix == ".pyc":
        return True
    if path.name in EXCLUDED_FILE_NAMES:
        return True
    return False


def main() -> int:
    if not SRC_DIR.is_dir() or not any(SRC_DIR.iterdir()):
        print(
            "src/bury_explain/ is missing or empty, run after TCK-030 lands "
            "the add-on source.",
            file=sys.stderr,
        )
        return 1

    write_config_json()

    DIST_DIR.mkdir(exist_ok=True)

    file_count = 0
    with zipfile.ZipFile(OUTPUT_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC_DIR.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(SRC_DIR)
            if is_excluded(rel):
                continue
            zf.write(path, arcname=str(rel))
            file_count += 1

    if file_count == 0:
        print(
            "No files found to package in src/bury_explain/, run after "
            "TCK-030 lands the add-on source.",
            file=sys.stderr,
        )
        OUTPUT_PATH.unlink(missing_ok=True)
        return 1

    print(f"Built {OUTPUT_PATH} ({file_count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
