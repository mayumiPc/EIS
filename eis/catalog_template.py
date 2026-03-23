"""
アプリが解釈する設置カタログのテンプレート（内部 SQLite スキーマと Access 取り込み仕様）。
実行時の一覧・検索はこの SQLite のみを参照し、.accdb は取り込み時のみ pyodbc で読む。

「完全保証」ではない: 取り込みは ACCESS_TABLE / ACCESS_COLUMNS_REQUIRED の検証と列値の正規化に限る。
内部 SQLite が有効なら元 .accdb は通常運用に不要だが、再取り込みには別途 .accdb が必要。
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

# --- Access 側の期待スキーマ（取り込み元）---
ACCESS_TABLE = "設置場所"

COL_ID = "ID"
COL_MAKER = "メーカー"
COL_KIND = "種類"
COL_PREF = "都道府県"
COL_CITY = "市区町村"
COL_NAME = "設置場所の名称"
COL_MEDIA = "動画・画像・音声"
COL_USE = "用途"
COL_LOAD = "積載"
COL_CAPACITY = "定員"

FILTER_COLUMNS = (COL_MAKER, COL_KIND, COL_PREF, COL_CITY, COL_USE, COL_LOAD, COL_CAPACITY)

LIST_COLUMNS = (
    COL_ID,
    COL_MAKER,
    COL_KIND,
    COL_PREF,
    COL_NAME,
    COL_USE,
    COL_LOAD,
    COL_CAPACITY,
)

# --- 内部 SQLite（アプリが常に読む側）---
TEMPLATE_SCHEMA_VERSION = 1
INTERNAL_TABLE = "eis_installations"
META_TABLE = "eis_catalog_meta"

# 日本語キー（UI/API）→ SQLite 物理列名
JP_TO_SQLITE_COL: dict[str, str] = {
    COL_ID: "id",
    COL_MAKER: "maker",
    COL_KIND: "kind",
    COL_PREF: "prefecture",
    COL_CITY: "city",
    COL_NAME: "site_name",
    COL_MEDIA: "media",
    COL_USE: "use_case",
    COL_LOAD: "load_val",
    COL_CAPACITY: "capacity",
}

# Access に必須の列（取り込み時に検証・SELECT 順序）
ACCESS_COLUMNS_REQUIRED: tuple[str, ...] = tuple(JP_TO_SQLITE_COL.keys())

SQLITE_TO_JP: dict[str, str] = {v: k for k, v in JP_TO_SQLITE_COL.items()}

CATALOG_SQLITE_REL = Path("data/eis_installation_catalog.sqlite")


def project_root() -> Path:
    from eis.paths import install_root

    return install_root()


def default_catalog_sqlite_path() -> Path:
    return project_root() / CATALOG_SQLITE_REL


def pending_catalog_next_path(sqlite_path: Path | None = None) -> Path:
    """取り込み中間ファイル（実行中プロセスでは本体に差し替えない）。"""
    p = sqlite_path or default_catalog_sqlite_path()
    return p.with_suffix(p.suffix + ".next")


def apply_pending_catalog_on_startup() -> bool:
    """
    wx / InstallationCatalog が本体 SQLite を開く **前** に必ず呼ぶ。
    有効な ``*.sqlite.next`` があれば ``eis_installation_catalog.sqlite`` へ置き換える。
    成功したら True。
    """
    sqlite = default_catalog_sqlite_path()
    nxt = pending_catalog_next_path(sqlite)
    if not nxt.is_file():
        return False
    if not catalog_sqlite_is_valid(nxt):
        try:
            bad = nxt.with_name(nxt.name + ".invalid")
            bad.unlink(missing_ok=True)
            nxt.rename(bad)
        except OSError:
            pass
        return False
    for _ in range(40):
        try:
            os.replace(str(nxt), str(sqlite))
            return True
        except OSError:
            time.sleep(0.08)
    print(
        "EIS: 内部カタログの反映に失敗しました（.sqlite.next を本体に置けません）。"
        " 他プロセスが data\\eis_installation_catalog.sqlite を開いている可能性があります。",
        file=sys.stderr,
    )
    return False


def has_stuck_pending_catalog() -> bool:
    """起動時の反映に失敗し、有効な .next だけが残っているとき True。"""
    sqlite = default_catalog_sqlite_path()
    nxt = pending_catalog_next_path(sqlite)
    if not nxt.is_file() or not catalog_sqlite_is_valid(nxt):
        return False
    return not catalog_sqlite_is_valid(sqlite)


class CatalogError(Exception):
    pass


class CatalogImportError(CatalogError):
    pass


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri()
    return sqlite3.connect(f"{uri}?mode=ro", uri=True)


def catalog_sqlite_is_valid(path: Path | None = None) -> bool:
    """内部カタログファイルが存在し、テンプレートのスキーマバージョンと一致するか。"""
    path = path or default_catalog_sqlite_path()
    if not path.is_file():
        return False
    try:
        conn = _connect_ro(path)
    except sqlite3.Error:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?)",
            (INTERNAL_TABLE, META_TABLE),
        )
        names = {r[0] for r in cur.fetchall()}
        if INTERNAL_TABLE not in names or META_TABLE not in names:
            return False
        cur.execute(f"PRAGMA table_info({INTERNAL_TABLE})")
        cols = {row[1] for row in cur.fetchall()}
        expected = set(JP_TO_SQLITE_COL.values())
        if not expected.issubset(cols):
            return False
        cur.execute(f'SELECT value FROM "{META_TABLE}" WHERE key = ?', ("schema_version",))
        row = cur.fetchone()
        if not row:
            return False
        return int(row[0]) == TEMPLATE_SCHEMA_VERSION
    except (sqlite3.Error, TypeError, ValueError):
        return False
    finally:
        conn.close()


def create_empty_catalog_schema(conn: sqlite3.Connection) -> None:
    """内部テーブルとメタテーブルを作成（データ行は別途投入）。"""
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {INTERNAL_TABLE}")
    cur.execute(
        f"""
        CREATE TABLE {INTERNAL_TABLE} (
            id INTEGER,
            maker TEXT,
            kind TEXT,
            prefecture TEXT,
            city TEXT,
            site_name TEXT,
            media TEXT,
            use_case TEXT,
            load_val TEXT,
            capacity TEXT
        )
        """
    )
    cur.execute(f"DROP TABLE IF EXISTS {META_TABLE}")
    cur.execute(
        f"""
        CREATE TABLE {META_TABLE} (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()


def write_catalog_meta(conn: sqlite3.Connection, *, source_accdb: str) -> None:
    from datetime import datetime, timezone

    cur = conn.cursor()
    cur.execute(f'DELETE FROM "{META_TABLE}"')
    cur.executemany(
        f'INSERT INTO "{META_TABLE}" (key, value) VALUES (?, ?)',
        [
            ("schema_version", str(TEMPLATE_SCHEMA_VERSION)),
            ("source_accdb", source_accdb),
            ("imported_at", datetime.now(timezone.utc).isoformat()),
        ],
    )
    conn.commit()
