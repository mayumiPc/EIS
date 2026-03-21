from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from train import train

CLASS_NAMES = ("mitsubishi", "hitachi", "otis", "toshiba", "thyssenkrupp", "westinghouse", "montgomery")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def build_dataset(out_root: Path) -> None:
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
                    if f.is_file() and f.suffix.lower() in IMAGE_EXT:
                        shutil.copy2(f, out_root / split / c / f.name)


def main() -> int:
    out = Path("dataset_base")
    build_dataset(out)
    train(out, epochs=10, batch_size=16, lr=1e-3, model_path=Path("models/eis_classifier_base.pt"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

