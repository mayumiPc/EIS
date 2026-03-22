"""
ユーザー追加学習に紐づく成果物のみを削除する（初回モデル・dataset/ 等は触れない）。

削除対象（プロジェクトルートからの相対パス・完全一致のみ）:
  - models/eis_classifier_user.pt
  - dataset_user/  （ディレクトリごと）
  - dataset_combined_user/  （ディレクトリごと）
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import NamedTuple


class UserTrainingResetResult(NamedTuple):
    deleted: list[str]
    skipped_missing: list[str]
    errors: list[str]


# ホワイトリスト: ここに無いパスは絶対に削除しない
_ALLOWED_FILE = Path("models/eis_classifier_user.pt")
_ALLOWED_DIRS = (Path("dataset_user"), Path("dataset_combined_user"))


def _resolved_child(root: Path, relative: Path) -> Path:
    """root 直下の relative のみ。root 外へ出る解決は拒否。"""
    r = root.resolve()
    candidate = (r / relative).resolve()
    try:
        candidate.relative_to(r)
    except ValueError:
        raise ValueError(f"パスがプロジェクト外を指します: {relative}")
    return candidate


def reset_user_training_artifacts(project_root: Path | None = None) -> UserTrainingResetResult:
    """
    ユーザー学習用モデルと、その学習で使うコピーデータのみ削除する。
    models/eis_classifier_base.pt, dataset/, dataset_legacy/, *.accdb 等は削除しない。
    """
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    deleted: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # 1) ユーザーモデルファイル
    try:
        fpath = _resolved_child(root, _ALLOWED_FILE)
        if fpath.is_file():
            fpath.unlink()
            deleted.append(str(fpath.relative_to(root)))
        elif fpath.exists():
            errors.append(f"想定がファイルだがディレクトリです（削除しません）: {_ALLOWED_FILE}")
        else:
            skipped.append(str(_ALLOWED_FILE))
    except Exception as e:
        errors.append(f"{_ALLOWED_FILE}: {e}")

    # 2) ディレクトリ（各々ホワイトリストの1要素と完全一致のパスのみ）
    for rel in _ALLOWED_DIRS:
        try:
            dpath = _resolved_child(root, rel)
            if dpath.is_dir():
                shutil.rmtree(dpath)
                deleted.append(str(rel.as_posix()) + "/")
            elif dpath.exists():
                errors.append(f"想定がディレクトリだがファイルです（削除しません）: {rel}")
            else:
                skipped.append(str(rel) + "/")
        except Exception as e:
            errors.append(f"{rel}: {e}")

    return UserTrainingResetResult(deleted=deleted, skipped_missing=skipped, errors=errors)
