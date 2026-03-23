"""
PyInstaller 用ブートストラップ（成果物 ``eis.exe`` のエントリスクリプト）。

- フリーズ後: ブートローダがパスを設定するため ``eis.__main__`` だけ呼ぶ。
- 開発時: リポジトリルートを ``sys.path`` に入れてから同じく ``eis.__main__`` を実行。

リポジトリ直下に ``eis.py`` を置かないこと（パッケージ ``eis`` と名前衝突するため）。
通常の起動は ``python -m eis`` または ``run_ui.py``。
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

if not getattr(sys, "frozen", False):
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

from eis.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
