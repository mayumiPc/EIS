"""
インストール／リポジトリルートの解決。

PyInstaller で固めた場合は ``sys.executable`` のあるディレクトリ（通常 ``dist/eis/``）を返す。
開発時は ``eis`` パッケージの1つ上（リポジトリルート）を返す。

注意: リポジトリ直下に ``eis.py`` を置くとパッケージ名 ``eis`` と衝突しうるため、
エントリは ``python -m eis`` または ``run_ui.py`` / ``tools/eis_bundle_entry.py`` を使うこと。
"""
from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_root() -> Path:
    """
    実行ファイル基準のルート。

    - フリーズ時: ``eis.exe`` と同じフォルダ（onedir 想定）
    - 開発時: リポジトリルート（``eis/`` の親）
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]
