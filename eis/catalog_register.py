"""
内部カタログ（SQLite）へのテンプレート準拠の1行登録。
推論結果ダイアログから呼び出す。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .catalog_template import (
    ACCESS_COLUMNS_REQUIRED,
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
    INTERNAL_TABLE,
    JP_TO_SQLITE_COL,
    CatalogError,
    catalog_sqlite_is_valid,
    default_catalog_sqlite_path,
)

# 推論クラス名（英小文字）→ メーカー欄の初期候補（日本語表記の一例）
TRAINING_CLASS_TO_SUGGESTED_MAKER_JA: dict[str, str] = {
    "mitsubishi": "三菱",
    "hitachi": "日立",
    "otis": "オーチス",
    "toshiba": "東芝",
    "thyssenkrupp": "ティセンクルップ",
    "westinghouse": "ウェスティングハウス",
    "montgomery": "モンゴメリー",
}


class CatalogRegisterError(CatalogError):
    pass


def training_class_to_suggested_maker_ja(class_name: str) -> str:
    return TRAINING_CLASS_TO_SUGGESTED_MAKER_JA.get(class_name.lower().strip(), class_name)


def _norm(v: Any) -> Any:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _next_id(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT MAX({JP_TO_SQLITE_COL[COL_ID]}) FROM {INTERNAL_TABLE}")
    row = cur.fetchone()
    m = row[0] if row and row[0] is not None else None
    try:
        base = int(m) if m is not None else 0
    except (TypeError, ValueError):
        base = 0
    return base + 1


def insert_row_jp(
    row: dict[str, Any],
    *,
    db_path: Path | None = None,
    auto_id: bool = True,
    manual_id: int | None = None,
) -> int:
    """
    テンプレート列（日本語キー COL_*）に沿って 1 行 INSERT。
    必須: COL_MAKER, COL_NAME（設置場所の名称）。
    COL_ID は auto_id 時に自動採番。manual_id 指定時は重複チェック。
    戻り値: 登録した id。
    """
    path = db_path or default_catalog_sqlite_path()
    if not catalog_sqlite_is_valid(path):
        raise CatalogRegisterError(
            "内部カタログがありません。Access からの取り込みを完了し、再起動したあとに登録してください。"
        )

    maker = _norm(row.get(COL_MAKER))
    site = _norm(row.get(COL_NAME))
    if not maker:
        raise CatalogRegisterError("メーカーは必須です。")
    if not site:
        raise CatalogRegisterError("設置場所の名称は必須です。")

    if auto_id:
        new_id: int | None = None
    else:
        if manual_id is None:
            raise CatalogRegisterError("ID を指定してください。")
        new_id = int(manual_id)

    values_jp: dict[str, Any] = {
        COL_ID: new_id,
        COL_MAKER: maker,
        COL_KIND: _norm(row.get(COL_KIND)),
        COL_PREF: _norm(row.get(COL_PREF)),
        COL_CITY: _norm(row.get(COL_CITY)),
        COL_NAME: site,
        COL_MEDIA: _norm(row.get(COL_MEDIA)),
        COL_USE: _norm(row.get(COL_USE)),
        COL_LOAD: _norm(row.get(COL_LOAD)),
        COL_CAPACITY: _norm(row.get(COL_CAPACITY)),
    }

    sqlite_cols = [JP_TO_SQLITE_COL[jp] for jp in ACCESS_COLUMNS_REQUIRED]
    conn = sqlite3.connect(str(path.resolve()), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        cur = conn.cursor()
        if auto_id:
            new_id = _next_id(conn)
            values_jp[COL_ID] = new_id
        else:
            assert new_id is not None
            cur.execute(
                f"SELECT 1 FROM {INTERNAL_TABLE} WHERE {JP_TO_SQLITE_COL[COL_ID]} = ? LIMIT 1",
                (new_id,),
            )
            if cur.fetchone():
                raise CatalogRegisterError(f"ID {new_id} は既に使用されています。")

        placeholders = ", ".join("?" * len(sqlite_cols))
        sql = f"INSERT INTO {INTERNAL_TABLE} ({', '.join(sqlite_cols)}) VALUES ({placeholders})"
        params = [values_jp[jp] for jp in ACCESS_COLUMNS_REQUIRED]
        cur.execute(sql, params)
        conn.commit()
    except CatalogRegisterError:
        conn.rollback()
        raise
    except sqlite3.Error as e:
        conn.rollback()
        raise CatalogRegisterError(f"SQLite エラー: {e}") from e
    finally:
        conn.close()

    assert new_id is not None
    return int(new_id)
