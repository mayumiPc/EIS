"""
アプリケーションエントリ（``python -m eis``）。

PyInstaller は ``tools/eis_bundle_entry.py`` からここを import し、成果物名 ``eis.exe`` とする。
"""
from __future__ import annotations

import os
import sys


def _ensure_cwd_install_root() -> None:
    from eis.paths import install_root

    root = install_root()
    try:
        os.chdir(root)
    except OSError:
        pass


def run_smoke_lite() -> int:
    """
    ビルド検証用（高速）: wx + カタログ起動フックのみ。torch は import しない。
    """
    _ensure_cwd_install_root()
    from eis.paths import install_root

    root = install_root()
    if not root.is_dir():
        print(f"[eis-smoke-lite] FAIL: install root is not a directory: {root}", file=sys.stderr)
        return 1
    try:
        print("[eis-smoke-lite] import wx ...", flush=True)
        import wx  # noqa: F401
    except Exception as exc:
        print(f"[eis-smoke-lite] FAIL: wx import: {exc}", file=sys.stderr)
        return 1
    try:
        print("[eis-smoke-lite] catalog apply_pending_catalog_on_startup ...", flush=True)
        from eis.catalog_template import apply_pending_catalog_on_startup

        apply_pending_catalog_on_startup()
    except Exception as exc:
        print(f"[eis-smoke-lite] FAIL: catalog startup: {exc}", file=sys.stderr)
        return 1
    print(f"[eis-smoke-lite] OK root={root}", flush=True)
    return 0


def run_smoke_full() -> int:
    """
    ビルド検証用（重い）: EISFrame まで import（torch / torchvision を読む）。
    リリース前や完全検証用。環境変数 EIS_SMOKE_FULL=1 または --eis-smoke。
    """
    code = run_smoke_lite()
    if code != 0:
        return code
    from eis.paths import install_root

    root = install_root()
    try:
        print("[eis-smoke] import EISFrame (torch; slow) ...", flush=True)
        from eis.ui import EISFrame  # noqa: F401
    except Exception as exc:
        print(f"[eis-smoke] FAIL: EISFrame import: {exc}", file=sys.stderr)
        return 1
    print(f"[eis-smoke] OK (full) root={root}", flush=True)
    return 0


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--eis-smoke-lite", action="store_true")
    p.add_argument("--eis-smoke", action="store_true")
    known, _unknown = p.parse_known_args()
    if known.eis_smoke:
        raise SystemExit(run_smoke_full())
    if known.eis_smoke_lite:
        raise SystemExit(run_smoke_lite())

    _ensure_cwd_install_root()

    import wx

    from eis.catalog_template import apply_pending_catalog_on_startup
    from eis.ui import EISFrame

    apply_pending_catalog_on_startup()
    app = wx.App(False)
    frame = EISFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
