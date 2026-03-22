"""One-off: print Access tables and columns for 設置場所.accdb (or first *.accdb)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    acc = list(ROOT.glob("*.accdb"))
    if not acc:
        print("No .accdb in project root")
        return
    p = acc[0]
    print("DB:", p)

    import pyodbc

    conn_str = r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(p.resolve()) + ";"
    c = pyodbc.connect(conn_str)
    cur = c.cursor()
    tables = [r.table_name for r in cur.tables(tableType="TABLE") if not r.table_name.startswith("MSys")]
    print("TABLES:", tables)
    for t in tables:
        print("\n===", t, "===")
        try:
            cols = [r.column_name for r in cur.columns(table=t)]
            print("columns:", cols)
            cur.execute(f"SELECT COUNT(*) FROM [{t}]")
            n = cur.fetchone()[0]
            print("rows:", n)
            cur.execute(f"SELECT TOP 3 * FROM [{t}]")
            rows = cur.fetchall()
            for row in rows:
                print(row)
        except Exception as e:
            print("err:", e)
    c.close()


if __name__ == "__main__":
    main()
