"""
Run PyInstaller for EIS, then zip the onedir output under tools/dist/.
Set CIMODE=true|false (case-insensitive) to record CI vs local builds in logs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
DIST_DIR = TOOLS_DIR / "dist"
BUILD_DIR = TOOLS_DIR / "build"
ENTRY_SCRIPT = PROJECT_ROOT / "tools" / "eis_bundle_entry.py"
APP_NAME = "eis"
ZIP_STEM = DIST_DIR / APP_NAME  # -> tools/dist/eis.zip


def parse_cimode() -> bool:
    raw = os.environ.get("CIMODE")
    if raw is None or raw.strip() == "":
        return False
    v = raw.strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off"):
        return False
    return False


def pyinstaller_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        str(ENTRY_SCRIPT),
        "--name",
        APP_NAME,
        "--paths",
        str(PROJECT_ROOT),
        "--noconsole",
        "--noupx",
        "--noconfirm",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--hidden-import",
        "pyodbc",
    ]


def zip_artifact() -> Path:
    bundle_dir = DIST_DIR / APP_NAME
    if not bundle_dir.is_dir():
        print(f"Expected build output directory not found: {bundle_dir}", flush=True)
        sys.exit(1)
    zip_path = Path(str(ZIP_STEM) + ".zip")
    if zip_path.is_file():
        zip_path.unlink()
    shutil.make_archive(str(ZIP_STEM), "zip", root_dir=str(DIST_DIR), base_dir=APP_NAME)
    return zip_path


def main() -> None:
    cimode = parse_cimode()
    print(f"CIMode: {cimode}", flush=True)
    print("Starting build.", flush=True)
    print("Building...", flush=True)

    if not ENTRY_SCRIPT.is_file():
        print(f"Entry script not found: {ENTRY_SCRIPT}", flush=True)
        sys.exit(1)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(pyinstaller_command(), cwd=str(PROJECT_ROOT))
    if proc.returncode != 0:
        sys.exit(proc.returncode)

    print("Build complete.", flush=True)
    print("Zipping...", flush=True)
    zip_path = zip_artifact()
    print(f"Created archive: {zip_path}", flush=True)
    print("Build finished!", flush=True)


if __name__ == "__main__":
    main()
