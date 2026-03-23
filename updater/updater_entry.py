from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

import requests
import wx


_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from constants import APP_FULL_NAME, APP_NAME  # noqa: E402


DEFAULT_GITHUB_REPO = "mayumiPc/eis"


def _parse_semver(v: str) -> tuple[int, int, int]:
    s = (v or "").strip()
    if s.startswith("v"):
        s = s[1:]
    parts = []
    buf = ""
    for ch in s:
        if ch.isdigit():
            buf += ch
        else:
            if buf:
                parts.append(int(buf))
                buf = ""
    if buf:
        parts.append(int(buf))
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def _version_compare(a: str, b: str) -> int:
    ta = _parse_semver(a)
    tb = _parse_semver(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def terminate_process(pid: int) -> None:
    if pid <= 0:
        return
    try:
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)  # PROCESS_TERMINATE = 1
        if not handle:
            return
        ctypes.windll.kernel32.TerminateProcess(handle, 1)
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return


def sync_dir(
    src_root: Path,
    dst_root: Path,
    *,
    skip_rel_prefixes: tuple[str, ...],
    src_base: Path | None = None,
) -> None:
    """
    src_root 配下を dst_root に上書きコピーする。
    skip_rel_prefixes で指定した相対パス以下はコピーしない（自己差し替え防止用）。
    """
    if src_base is None:
        src_base = src_root

    for entry in src_root.iterdir():
        rel = entry.relative_to(src_base).as_posix()
        skip = False
        for pfx in skip_rel_prefixes:
            if rel == pfx or rel.startswith(pfx + "/"):
                skip = True
                break
        if skip:
            continue

        dst = dst_root / entry.name
        if entry.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            sync_dir(entry, dst, skip_rel_prefixes=skip_rel_prefixes, src_base=src_base)
        else:
            if dst.exists():
                try:
                    dst.unlink()
                except OSError:
                    pass
            shutil.copy2(entry, dst)


def fetch_latest_release(repo: str, app_name: str) -> tuple[str, str]:
    """
    Return: (latest_version, asset_download_url)
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"User-Agent": f"{app_name}-updater"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    tag = data.get("tag_name") or ""
    assets = data.get("assets") or []
    expected_asset_name = f"{app_name}.zip"

    asset = None
    for a in assets:
        if (a.get("name") or "") == expected_asset_name:
            asset = a
            break
    if asset is None:
        # フォールバック: .zip の先頭を使う
        for a in assets:
            if str(a.get("name") or "").lower().endswith(".zip"):
                asset = a
                break

    if asset is None:
        raise RuntimeError(f"Release asset not found (expected: {expected_asset_name}).")

    asset_url = asset.get("browser_download_url")
    if not asset_url:
        raise RuntimeError("Release asset download URL not found.")

    latest_version = tag.lstrip("v")
    if not latest_version:
        raise RuntimeError("Latest version tag not found.")
    return latest_version, asset_url


def download_with_progress(url: str, out_path: Path, dialog: wx.Frame) -> None:
    headers = {"User-Agent": "EIS-Updater"}
    r = requests.get(url, headers=headers, stream=True, timeout=60)
    r.raise_for_status()
    total = int(r.headers.get("Content-Length") or 0)
    downloaded = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = int(downloaded * 100 / total)
                dialog.set_progress(percent, f"Downloading... {percent}%")
            else:
                dialog.set_progress(0, f"Downloading... {downloaded} bytes")

    dialog.set_progress(100, "Download complete.")


class UpdateProgressFrame(wx.Frame):
    def __init__(self, title: str) -> None:
        super().__init__(parent=None, title=title, size=(480, 120))
        panel = wx.Panel(self)

        vbox = wx.BoxSizer(wx.VERTICAL)
        self.status = wx.StaticText(panel, label="Starting...", style=wx.ALIGN_CENTRE)
        vbox.Add(self.status, 0, wx.ALL | wx.EXPAND, 12)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 12)

        panel.SetSizer(vbox)
        self.Centre()

    def set_progress(self, percent: int, status: str) -> None:
        percent = max(0, min(100, percent))
        self.gauge.SetValue(percent)
        self.status.SetLabel(status)
        self.Refresh()
        wx.YieldIfNeeded()


def run_updater(args: argparse.Namespace) -> int:
    target_dir = Path(args.target_dir).resolve()
    current_version = args.current_version
    app_name = args.app_name
    parent_pid = int(args.parent_pid) if args.parent_pid else 0

    if not target_dir.is_dir():
        wx.MessageBox("Invalid target directory.", "Updater", wx.OK | wx.ICON_ERROR)
        return 1

    app_exe = target_dir / f"{app_name}.exe"
    if not app_exe.is_file():
        wx.MessageBox("Target application executable not found.", "Updater", wx.OK | wx.ICON_ERROR)
        return 1

    latest_version, asset_url = fetch_latest_release(args.repo, app_name)

    if _version_compare(latest_version, current_version) <= 0:
        wx.MessageBox("Already up to date.", "Updater", wx.OK | wx.ICON_INFORMATION)
        return 0

    confirm = wx.MessageBox(
        f"version:{latest_version} にアップデートできます。アップデートしますか？",
        "Updater",
        wx.YES_NO | wx.ICON_QUESTION,
    )
    if confirm != wx.YES:
        return 0

    tmp_dir = Path(tempfile.gettempdir()) / f"eis_updater_{int(time.time())}"
    work_dir = tmp_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    zip_path = tmp_dir / f"{app_name}.zip"

    dlg = UpdateProgressFrame(f"{APP_FULL_NAME} - Updater")
    dlg.Show()

    try:
        dlg.set_progress(0, "Downloading...")
        download_with_progress(asset_url, zip_path, dlg)

        dlg.set_progress(0, "Extracting...")
        extract_root = work_dir / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            zf.extractall(str(extract_root))

        dlg.set_progress(10, "Stopping application...")
        terminate_process(parent_pid)
        # Windows のロック回避（多少待つ）
        for _ in range(30):
            time.sleep(0.2)
            try:
                if app_exe.exists():
                    # 実行中でも上書き失敗は起こり得るため、あくまで短い待機
                    pass
            except Exception:
                pass

        dlg.set_progress(30, "Applying update...")

        # zip の最上位に app_name ディレクトリが入っている想定
        new_root = extract_root / app_name
        if not new_root.is_dir():
            # フォールバック: ディレクトリが1つしかなければそれを採用
            dirs = [p for p in extract_root.iterdir() if p.is_dir()]
            if len(dirs) == 1:
                new_root = dirs[0]
            else:
                new_root = extract_root

        # updater 自身の上書き（自己差し替え）を避ける
        skip_rel_prefixes = ("public/updater", "updater")
        sync_dir(new_root, target_dir, skip_rel_prefixes=skip_rel_prefixes, src_base=new_root)

        dlg.set_progress(100, "Starting updated application...")

        subprocess.Popen([str(target_dir / f"{app_name}.exe")], cwd=str(target_dir))

        wx.MessageBox("Build update finished.", "Updater", wx.OK | wx.ICON_INFORMATION)
        return 0
    except Exception as exc:
        wx.MessageBox(f"Update failed: {exc}", "Updater", wx.OK | wx.ICON_ERROR)
        return 1
    finally:
        try:
            dlg.Destroy()
        except Exception:
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--target-dir", required=False, default="")
    p.add_argument("--current-version", required=False, default="")
    p.add_argument("--parent-pid", required=False, default="0")
    p.add_argument("--app-name", default=APP_NAME)
    p.add_argument("--repo", default=DEFAULT_GITHUB_REPO)
    return p.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])

    # wx を使うため App を作る
    app = wx.App(False)
    try:
        if not args.target_dir or not args.current_version:
            wx.MessageBox(
                "This updater cannot be run directly. Launch it from the main app.",
                "Updater",
                wx.OK | wx.ICON_WARNING,
            )
            return 1
        return run_updater(args)
    finally:
        try:
            app.Destroy()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
