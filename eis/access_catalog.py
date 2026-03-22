"""
後方互換: 定数・ヘルパは catalog_template / catalog_sqlite に移行済み。
アプリは InstallationCatalog（内部 SQLite）のみを読む。.accdb 直接読込は廃止。
"""
from __future__ import annotations

import re
from pathlib import Path

# テンプレート定数（UI・取り込みで共通）
from .catalog_template import (  # noqa: F401
    ACCESS_TABLE,
    COL_CAPACITY,
    COL_CITY,
    COL_ID,
    COL_KIND,
    COL_LOAD,
    COL_MEDIA,
    COL_MAKER,
    COL_NAME,
    COL_PREF,
    COL_USE,
    FILTER_COLUMNS,
    LIST_COLUMNS,
    CatalogError,
    catalog_sqlite_is_valid,
    default_catalog_sqlite_path,
)

TABLE = ACCESS_TABLE  # 旧ドキュメント・互換用
from .catalog_sqlite import InstallationCatalog

# 旧コード向けエイリアス
AccessCatalog = InstallationCatalog
AccessCatalogError = CatalogError


def find_project_accdb(root: Path | None = None) -> Path:
    """任意: プロジェクト直下の .accdb を探す（取り込み元候補のヒント用）。"""
    root = root or Path(__file__).resolve().parents[1]
    found = sorted(root.glob("*.accdb"))
    if not found:
        raise FileNotFoundError("プロジェクト直下に .accdb がありません（例: 設置場所.accdb）。")
    return found[0]


def manufacturer_to_training_class(maker: str | None) -> str | None:
    """DBのメーカー表記を学習ラベル（英小文字クラス名）に変換。"""
    if not maker or not str(maker).strip():
        return None
    u = re.sub(r"\s+", "", str(maker).upper())
    u = re.sub(r"（.*?）", "", u)  # strip （推定）等
    if "MITSUBISHI" in u or "MISUBISHI" in u:
        return "mitsubishi"
    if "HITACHI" in u:
        return "hitachi"
    if "OTIS" in u:
        return "otis"
    if "TOSHIBA" in u:
        return "toshiba"
    if "THYSSEN" in u or "TKE" in u:
        return "thyssenkrupp"
    if "WESTINGHOUSE" in u:
        return "westinghouse"
    if "MONTGOMERY" in u:
        return "montgomery"
    return None
