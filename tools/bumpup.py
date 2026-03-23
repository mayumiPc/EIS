from __future__ import annotations

import argparse
from datetime import datetime
import re
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
CONSTANTS_PATH = ROOT / "constants.py"

SKIP_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
}
SKIP_SUFFIXES = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".pt",
    ".onnx",
    ".sqlite",
    ".tmp",
    ".next",
    ".invalid",
    ".pyc",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bump app version and update constants metadata.")
    p.add_argument(
        "--part",
        choices=("major", "minor", "patch"),
        default="patch",
        help="Which version part to bump when version input is blank (default: patch)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing files",
    )
    return p.parse_args()


def read_current_version(constants_text: str) -> str:
    m = re.search(r'^\s*APP_VERSION\s*=\s*"([^"]+)"\s*$', constants_text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("APP_VERSION not found in constants.py")
    return m.group(1)


def parse_version_loose(version: str) -> tuple[int, int, int]:
    m = re.fullmatch(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", version.strip())
    if not m:
        raise RuntimeError(f"Unsupported version format: {version!r}. Expected x, x.y, or x.y.z")
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return major, minor, patch


def bump_version(version: str, part: str) -> str:
    major, minor, patch = parse_version_loose(version)
    if part == "major":
        return f"{major + 1}.0"
    if part == "minor":
        return f"{major}.{minor + 1}"
    return f"{major}.{minor}.{patch + 1}"


def normalize_version_input(value: str) -> str:
    _major, _minor, _patch = parse_version_loose(value)
    return value.strip()


def should_skip(path: Path) -> bool:
    for p in path.parts:
        if p in SKIP_DIRS:
            return True
    return path.suffix.lower() in SKIP_SUFFIXES


def iter_target_files() -> list[Path]:
    files: list[Path] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if should_skip(rel):
            continue
        files.append(p)
    return files


def replace_version_in_file(path: Path, old: str, new: str, dry_run: bool) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False

    updated = text.replace(f"v{old}", f"v{new}").replace(old, new)
    if updated == text:
        return False

    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return True


def update_constants_fields(text: str, copyright_value: str, last_updated_value: str) -> str:
    def _set_or_add(pattern: str, replacement_line: str, src: str) -> str:
        if re.search(pattern, src, flags=re.MULTILINE):
            return re.sub(pattern, replacement_line, src, count=1, flags=re.MULTILINE)
        if not src.endswith("\n"):
            src += "\n"
        return src + replacement_line + "\n"

    out = text
    out = _set_or_add(
        r'^\s*COPYRIGHT_YEAR\s*=\s*"[^"]*"\s*$',
        f'COPYRIGHT_YEAR = "{copyright_value}"',
        out,
    )
    out = _set_or_add(
        r'^\s*LAST_UPDATED_YEAR\s*=\s*"[^"]*"\s*$',
        f'LAST_UPDATED_YEAR = "{last_updated_value}"',
        out,
    )
    return out


def prompt_user_values(current_version: str, part: str) -> tuple[str, str, str]:
    now_year = str(datetime.now().year)

    version_in = input(f"New version (Enter=auto bump from {current_version}): ").strip()
    if version_in:
        new_version = normalize_version_input(version_in)
    else:
        new_version = bump_version(current_version, part)

    copyright_default = f"{now_year}, mayumiPc"
    copyright_in = input(
        f'COPYRIGHT_YEAR (Enter= "{copyright_default}"): '
    ).strip()
    copyright_value = copyright_in if copyright_in else copyright_default

    last_updated_in = input(
        f'LAST_UPDATED_YEAR (Enter= "{now_year}"): '
    ).strip()
    last_updated_value = last_updated_in if last_updated_in else now_year
    return new_version, copyright_value, last_updated_value


def main() -> int:
    args = parse_args()

    if not CONSTANTS_PATH.is_file():
        print(f"[ERROR] constants.py not found: {CONSTANTS_PATH}")
        return 1

    constants_text = CONSTANTS_PATH.read_text(encoding="utf-8")
    old_version = read_current_version(constants_text)

    try:
        new_version, copyright_value, last_updated_value = prompt_user_values(
            old_version, args.part
        )
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[INFO] cancelled.")
        return 1

    changed: list[Path] = []
    for path in iter_target_files():
        if replace_version_in_file(path, old_version, new_version, args.dry_run):
            changed.append(path)

    updated_constants = update_constants_fields(
        CONSTANTS_PATH.read_text(encoding="utf-8"),
        copyright_value,
        last_updated_value,
    )
    before_constants = CONSTANTS_PATH.read_text(encoding="utf-8")
    if updated_constants != before_constants:
        if not args.dry_run:
            CONSTANTS_PATH.write_text(updated_constants, encoding="utf-8")
        if CONSTANTS_PATH not in changed:
            changed.append(CONSTANTS_PATH)

    readme_txt = ROOT / "readme.txt"
    if not readme_txt.exists():
        print("[INFO] readme.txt not found (skip).")

    if not changed:
        print(f"[INFO] No files updated. version={old_version}")
        return 0

    print(f"[OK] version: {old_version} -> {new_version}")
    print(f'[OK] COPYRIGHT_YEAR="{copyright_value}"')
    print(f'[OK] LAST_UPDATED_YEAR="{last_updated_value}"')
    for p in sorted(changed):
        print(f" - {p.relative_to(ROOT)}")
    if args.dry_run:
        print("[INFO] dry-run: no files were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

