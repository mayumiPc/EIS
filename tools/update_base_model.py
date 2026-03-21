from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.train_base_model import main as train_base_main


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    bdir = path.parent / "archive"
    bdir.mkdir(parents=True, exist_ok=True)
    out = bdir / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    shutil.copy2(path, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()
    base = Path("models/eis_classifier_base.pt")
    if not a.no_backup:
        b = backup(base)
        print(f"Backup created: {b}" if b else "Backup skipped: no existing model.")
    print("Updating base model...")
    code = train_base_main()
    print("Base model update complete." if code == 0 else "Base model update failed.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

