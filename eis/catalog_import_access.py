"""
Access (.accdb) から内部 SQLite カタログへ取り込む（pyodbc はここでのみ使用）。

実行中は本体 ``eis_installation_catalog.sqlite`` には触れず、
``eis_installation_catalog.sqlite.next`` のみを書き込む。
本体への反映はプロセス起動直後 ``apply_pending_catalog_on_startup()`` が行う。
"""
from __future__ import annotations

import gc
import sqlite3
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from .catalog_template import (
    ACCESS_COLUMNS_REQUIRED,
    ACCESS_TABLE,
    CatalogImportError,
    create_empty_catalog_schema,
    default_catalog_sqlite_path,
    pending_catalog_next_path,
    write_catalog_meta,
    JP_TO_SQLITE_COL,
)


def _connect_access(accdb_path: Path) -> Any:
    try:
        import pyodbc
    except ImportError as e:
        raise CatalogImportError("pyodbc が未インストールです。pip install pyodbc を実行してください。") from e
    conn_str = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(accdb_path.resolve()) + ";"
    )
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        raise CatalogImportError(
            "Access に接続できません。Microsoft Access Database Engine (ACE) の ODBC ドライバが必要です。"
        ) from e


def _access_cell_to_python(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def _adapt_value_for_sqlite(v: Any) -> Any:
    """pyodbc が返す型を sqlite3 が確実に受け付ける形にする。"""
    if v is None:
        return None
    if isinstance(v, (bytes, memoryview)):
        return bytes(v) if isinstance(v, memoryview) else v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def _retry_os(
    op: Callable[[], None],
    *,
    attempts: int = 20,
    delay_sec: float = 0.05,
    err: type[Exception] | tuple[type[Exception], ...] = OSError,
) -> None:
    last: BaseException | None = None
    for _ in range(attempts):
        try:
            op()
            return
        except err as e:
            last = e
            time.sleep(delay_sec)
    assert last is not None
    raise last


def import_access_to_sqlite(
    accdb_path: Path,
    sqlite_out_path: Path | None = None,
) -> int:
    """
    指定 .accdb を読み、**中間ファイル** ``*.sqlite.next`` のみを作成・上書きする。
    本体 ``*.sqlite`` への反映は起動時 ``apply_pending_catalog_on_startup()`` に任せる。

    戻り値: 取り込んだ行数。
    """
    accdb_path = Path(accdb_path)
    if not accdb_path.is_file():
        raise CatalogImportError(f"ファイルがありません: {accdb_path}")
    if accdb_path.suffix.lower() not in (".accdb", ".mdb"):
        raise CatalogImportError("拡張子は .accdb または .mdb を指定してください。")

    sqlite_out_path = sqlite_out_path or default_catalog_sqlite_path()
    sqlite_out_path.parent.mkdir(parents=True, exist_ok=True)

    access_conn = _connect_access(accdb_path)
    try:
        cur = access_conn.cursor()
        try:
            cur.execute(f"SELECT TOP 1 * FROM [{ACCESS_TABLE}]")
        except Exception as e:
            raise CatalogImportError(
                f"テーブル「{ACCESS_TABLE}」を読めません。設置カタログ用の .accdb か確認してください。"
            ) from e
        desc_raw = [d[0] for d in (cur.description or [])]
        desc = [_access_cell_to_python(x) if not isinstance(x, str) else str(x).strip() for x in desc_raw]
        missing = [c for c in ACCESS_COLUMNS_REQUIRED if c not in desc]
        if missing:
            raise CatalogImportError(
                "Access データベースに必要な列がありません: "
                + ", ".join(missing)
                + "\n（検出された列: "
                + ", ".join(desc)
                + "）"
            )

        select_cols = ", ".join(f"[{c}]" for c in ACCESS_COLUMNS_REQUIRED)
        cur.execute(f"SELECT {select_cols} FROM [{ACCESS_TABLE}]")
        raw_rows = cur.fetchall()
    finally:
        access_conn.close()

    build_path = pending_catalog_next_path(sqlite_out_path)
    try:
        _retry_os(
            lambda: build_path.unlink() if build_path.exists() else None,
            err=(PermissionError, OSError),
        )
    except OSError:
        pass

    insert_sqlite_cols = [JP_TO_SQLITE_COL[jp] for jp in ACCESS_COLUMNS_REQUIRED]
    placeholders = ", ".join("?" * len(insert_sqlite_cols))
    insert_sql = (
        "INSERT INTO eis_installations ("
        + ", ".join(insert_sqlite_cols)
        + ") VALUES ("
        + placeholders
        + ")"
    )

    batch: list[tuple[Any, ...]] = []
    for row in raw_rows:
        batch.append(
            tuple(
                _adapt_value_for_sqlite(_access_cell_to_python(row[i]))
                for i in range(len(ACCESS_COLUMNS_REQUIRED))
            )
        )

    conn: sqlite3.Connection | None = None
    wrote_next = False
    try:
        try:
            conn = sqlite3.connect(str(build_path), timeout=60.0)
            conn.execute("PRAGMA journal_mode=DELETE")
            create_empty_catalog_schema(conn)
            icur = conn.cursor()
            try:
                icur.executemany(insert_sql, batch)
            except sqlite3.Error as e:
                raise CatalogImportError(f"SQLite への行の書き込みに失敗しました: {e}") from e
            write_catalog_meta(conn, source_accdb=str(accdb_path.resolve()))
            conn.commit()
            wrote_next = True
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
                conn = None
            gc.collect()
            time.sleep(0.08)

        return len(batch)
    finally:
        if not wrote_next and build_path.exists():
            try:
                build_path.unlink(missing_ok=True)
            except OSError:
                pass
