"""
Run PyInstaller for EIS, then zip the onedir output.
Set CIMODE=true|false (case-insensitive) to record CI mode in logs.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
ENTRY_SCRIPT = PROJECT_ROOT / "tools" / "eis_bundle_entry.py"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants import APP_NAME  # noqa: E402

# Output directory names (always created under current working directory).
DIST_DIR_NAME = "dist"
BUILD_DIR_NAME = "build"

# Package data directories (relative to project root). Keep iterable for extensibility.
PACKAGE_DATA_DIRS: tuple[str, ...] = (
    "public",
)


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


def resolve_output_dirs() -> tuple[Path, Path]:
    run_root = Path.cwd().resolve()
    dist_dir = run_root / DIST_DIR_NAME
    build_dir = run_root / BUILD_DIR_NAME
    return dist_dir, build_dir


def build_add_data_args() -> list[str]:
    args: list[str] = []
    sep = os.pathsep
    for rel_dir in PACKAGE_DATA_DIRS:
        src = PROJECT_ROOT / rel_dir
        if src.exists():
            args += ["--add-data", f"{src}{sep}{rel_dir}"]
    return args


def pyinstaller_command(dist_dir: Path, build_dir: Path) -> list[str]:
    cmd = [
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
        str(dist_dir),
        "--workpath",
        str(build_dir),
        "--hidden-import",
        "pyodbc",
    ]
    cmd += build_add_data_args()
    return cmd


def zip_artifact(dist_dir: Path) -> Path:
    bundle_dir = dist_dir / APP_NAME
    if not bundle_dir.is_dir():
        print(f"Expected build output directory not found: {bundle_dir}", flush=True)
        sys.exit(1)
    zip_stem = dist_dir / APP_NAME
    zip_path = Path(str(zip_stem) + ".zip")
    if zip_path.is_file():
        zip_path.unlink()
    shutil.make_archive(str(zip_stem), "zip", root_dir=str(dist_dir), base_dir=APP_NAME)
    return zip_path


def main() -> None:
    dist_dir, build_dir = resolve_output_dirs()
    cimode = parse_cimode()
    print(f"Starting build for {APP_NAME}.", flush=True)
    print(f"CI mode: {cimode}", flush=True)
    print("Building...", flush=True)

    if not ENTRY_SCRIPT.is_file():
        print(f"Entry script not found: {ENTRY_SCRIPT}", flush=True)
        sys.exit(1)

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        pyinstaller_command(dist_dir, build_dir),
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr, flush=True)
        sys.exit(proc.returncode)

    print(f"Build process Success (exit code: {proc.returncode})", flush=True)
    print("Zipping...", flush=True)
    zip_artifact(dist_dir)
    print("Build finished!", flush=True)


if __name__ == "__main__":
    main()
