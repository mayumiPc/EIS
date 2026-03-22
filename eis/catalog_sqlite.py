"""
内部 SQLite 上の設置カタログを読む（.accdb には接続しない）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .catalog_template import (
    COL_CAPACITY,
    COL_CITY,
    COL_ID,
    COL_KIND,
    COL_LOAD,
    COL_MAKER,
    COL_PREF,
    COL_USE,
    FILTER_COLUMNS,
    JP_TO_SQLITE_COL,
    LIST_COLUMNS,
    SQLITE_TO_JP,
    CatalogError,
    default_catalog_sqlite_path,
)


class InstallationCatalog:
    """テンプレートに沿った内部カタログ（SQLite）を検索・集計する。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else default_catalog_sqlite_path()
        if not self.db_path.is_file():
            raise CatalogError(f"内部カタログがありません: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.db_path.resolve()), timeout=30.0)
        except sqlite3.Error as e:
            raise CatalogError(f"内部カタログを開けません: {e}") from e
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.Error:
            pass
        return conn

    def _row_tuple_to_ui_dict(self, names: list[str], r: tuple[Any, ...]) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for i, name in enumerate(names):
            jp = SQLITE_TO_JP.get(name)
            if jp is None:
                continue
            v = r[i]
            if isinstance(v, bytes):
                v = v.hex()
            d[jp] = v
        return d

    def distinct_values(self, column: str) -> list[str]:
        if column not in FILTER_COLUMNS:
            raise ValueError(column)
        scol = JP_TO_SQLITE_COL[column]
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT DISTINCT {scol} FROM eis_installations "
                f"WHERE {scol} IS NOT NULL ORDER BY {scol}"
            )
            out: list[str] = []
            for (v,) in cur.fetchall():
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    out.append(s)
            return out
        finally:
            conn.close()

    def distinct_cities(self, prefecture: str | None) -> list[str]:
        scity = JP_TO_SQLITE_COL[COL_CITY]
        spref = JP_TO_SQLITE_COL[COL_PREF]
        conn = self._connect()
        try:
            cur = conn.cursor()
            if prefecture:
                cur.execute(
                    f"SELECT DISTINCT {scity} FROM eis_installations "
                    f"WHERE {spref} = ? AND {scity} IS NOT NULL ORDER BY {scity}",
                    (prefecture,),
                )
            else:
                cur.execute(
                    f"SELECT DISTINCT {scity} FROM eis_installations "
                    f"WHERE {scity} IS NOT NULL ORDER BY {scity}"
                )
            out: list[str] = []
            for (v,) in cur.fetchall():
                if v is None:
                    continue
                s = str(v).strip()
                if s:
                    out.append(s)
            return out
        finally:
            conn.close()

    def search(
        self,
        maker: str | None = None,
        kind: str | None = None,
        prefecture: str | None = None,
        city: str | None = None,
        use_: str | None = None,
        load: str | None = None,
        capacity: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if maker:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_MAKER]} = ?")
            params.append(maker)
        if kind:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_KIND]} = ?")
            params.append(kind)
        if prefecture:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_PREF]} = ?")
            params.append(prefecture)
        if city:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_CITY]} = ?")
            params.append(city)
        if use_:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_USE]} = ?")
            params.append(use_)
        if load:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_LOAD]} = ?")
            params.append(load)
        if capacity:
            conditions.append(f"{JP_TO_SQLITE_COL[COL_CAPACITY]} = ?")
            params.append(capacity)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cols_sql = ", ".join(JP_TO_SQLITE_COL[c] for c in LIST_COLUMNS)
        sid = JP_TO_SQLITE_COL[COL_ID]
        sql = (
            f"SELECT {cols_sql} FROM eis_installations{where} "
            f"ORDER BY {sid} LIMIT {int(limit)}"
        )
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            names = [d[0] for d in cur.description or []]
            rows: list[dict[str, Any]] = []
            for r in cur.fetchall():
                rows.append(self._row_tuple_to_ui_dict(names, r))
            return rows
        finally:
            conn.close()
