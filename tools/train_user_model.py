from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path
import sys

from PIL import Image, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from train import train

CLASS_NAMES = ("mitsubishi", "hitachi", "otis", "toshiba", "thyssenkrupp", "westinghouse", "montgomery")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def is_image(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXT


def valid_image(p: Path) -> bool:
    try:
        with Image.open(p) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def collect(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        if p.is_file() and is_image(p):
            out.append(p)
        elif p.is_dir():
            out.extend([f for f in p.rglob("*") if f.is_file() and is_image(f)])
    return out


def import_file_mode(inputs: list[Path], label: str, dst_root: Path) -> int:
    t = dst_root / label
    t.mkdir(parents=True, exist_ok=True)
    copied = 0
    for i, src in enumerate(collect(inputs), start=1):
        if not valid_image(src):
            continue
        out = t / f"{i:06d}{src.suffix.lower()}"
        shutil.copy2(src, out)
        copied += 1
    return copied


def import_zip_mode(zips: list[Path], dst_root: Path, fallback_label: str | None) -> int:
    copied = 0
    temp = dst_root.parent / "_tmp_zip"
    for z in zips:
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z, "r") as zh:
            zh.extractall(temp)
        class_matched = False
        for c in CLASS_NAMES:
            d = temp / c
            if d.exists():
                copied += import_file_mode([d], c, dst_root)
                class_matched = True
        if not class_matched and fallback_label:
            copied += import_file_mode([temp], fallback_label, dst_root)
        shutil.rmtree(temp, ignore_errors=True)
    return copied


def merge_base_with_user(user_raw: Path, out_root: Path) -> None:
    if out_root.exists():
        shutil.rmtree(out_root)
    for split in ("train", "val", "test"):
        for c in CLASS_NAMES:
            (out_root / split / c).mkdir(parents=True, exist_ok=True)
    for src_root in (Path("dataset"), Path("dataset_legacy")):
        if not src_root.exists():
            continue
        for split in ("train", "val", "test"):
            for c in CLASS_NAMES:
                src = src_root / split / c
                if not src.exists():
                    continue
                for f in src.glob("*"):
                    if f.is_file() and is_image(f):
                        shutil.copy2(f, out_root / split / c / f.name)
    for c in CLASS_NAMES:
        src = user_raw / c
        if not src.exists():
            continue
        for f in src.glob("*"):
            if f.is_file() and is_image(f):
                shutil.copy2(f, out_root / "train" / c / f.name)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-mode", choices=["file", "zip"], required=True)
    p.add_argument("--inputs", nargs="+", required=True)
    p.add_argument("--label", choices=CLASS_NAMES, default=None)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--out-model", type=Path, default=Path("models/eis_classifier_user.pt"))
    a = p.parse_args()

    user_raw = Path("dataset_user/raw")
    user_raw.mkdir(parents=True, exist_ok=True)
    inputs = [Path(x) for x in a.inputs]
    if a.source_mode == "file":
        if not a.label:
            raise ValueError("--label is required in file mode")
        copied = import_file_mode(inputs, a.label, user_raw)
    else:
        copied = import_zip_mode(inputs, user_raw, a.label)
    if copied == 0:
        raise RuntimeError("No valid user image imported.")
    print(f"Imported user images: {copied}")

    combined = Path("dataset_combined_user")
    merge_base_with_user(user_raw, combined)
    train(combined, epochs=a.epochs, batch_size=a.batch_size, lr=a.lr, model_path=a.out_model)
    print(f"User model saved to: {a.out_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

