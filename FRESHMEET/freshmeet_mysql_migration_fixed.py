"""Copy FreshMeet data from freshmeet_admin.db into the existing freshmeet_db.

Keep beside freshmeet_admin.db and run:
    py freshmeet_mysql_migration_fixed.py
"""
from pathlib import Path
import getpass
import sqlite3
import sys

try:
    import mysql.connector
except ImportError:
    print("MySQL connector missing. Install with: py -m pip install mysql-connector-python")
    raise SystemExit(1)

BASE_DIR = Path(__file__).resolve().parent
SQLITE_FILE = BASE_DIR / "freshmeet_admin.db"
MYSQL_DATABASE = "freshmeet_db"
TABLES = [
    "admins", "customers", "sellers", "riders",
    "products", "orders", "payments", "complaints", "notifications"
]


def main():
    print("FreshMeet SQLite -> MySQL migration", flush=True)
    print(f"Source: {SQLITE_FILE}", flush=True)
    print(f"Target: {MYSQL_DATABASE}", flush=True)
    if not SQLITE_FILE.is_file():
        print("ERROR: freshmeet_admin.db is not in this folder.", flush=True)
        return 1

    password = getpass.getpass("Enter MySQL root password: ")
    if not password:
        print("ERROR: Empty password input. Run again and type your password before Enter.", flush=True)
        return 1

    source = None
    target = None
    cur = None
    transaction_started = False
    try:
        print("Checking SQLite source...", flush=True)
        source = sqlite3.connect(str(SQLITE_FILE))
        source.row_factory = sqlite3.Row
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check: {integrity}")

        print("Connecting to MySQL (Pure Python mode)...", flush=True)
        target = mysql.connector.connect(
            host="127.0.0.1", port=3306, user="root", password=password,
            database=MYSQL_DATABASE, charset="utf8mb4", use_pure=True,
            connection_timeout=10
        )
        print("MySQL connection successful.", flush=True)
        cur = target.cursor()

        source_columns_by_table = {}
        for table in TABLES:
            source_columns = [r["name"] for r in source.execute(f'PRAGMA table_info("{table}")')]
            if not source_columns:
                raise RuntimeError(f"Source table missing: {table}")
            source_columns_by_table[table] = source_columns
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            target_columns = {r[0] for r in cur.fetchall()}
            missing = [c for c in source_columns if c not in target_columns]
            if missing:
                raise RuntimeError(f"MySQL table {table} missing columns: {', '.join(missing)}")

        # Preserve SQLite's UNIQUE constraint on riders.email.
        cur.execute("SHOW INDEX FROM `riders`")
        indexes = cur.fetchall()
        unique_email = any(str(r[4]).lower() == "email" and int(r[1]) == 0 for r in indexes)
        if not unique_email:
            print("Adding UNIQUE constraint to riders.email...", flush=True)
            cur.execute("ALTER TABLE `riders` ADD CONSTRAINT `riders_email` UNIQUE (`email`)")

        # Avoid duplicate insertion or overwriting data if a prior attempt succeeded.
        counts_before = {}
        for table in TABLES:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            counts_before[table] = int(cur.fetchone()[0])
        nonempty = {t: n for t, n in counts_before.items() if n}
        if nonempty:
            details = ", ".join(f"{t}={n}" for t, n in nonempty.items())
            raise RuntimeError("Destination tables are not empty; stopped without copying rows: " + details)

        target.start_transaction()
        transaction_started = True
        copied = {}
        for table in TABLES:
            cols = source_columns_by_table[table]
            rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
            if rows:
                col_sql = ", ".join(f"`{c}`" for c in cols)
                marks = ", ".join(["%s"] * len(cols))
                sql = f"INSERT INTO `{table}` ({col_sql}) VALUES ({marks})"
                values = [tuple(row[c] for c in cols) for row in rows]
                cur.executemany(sql, values)
            copied[table] = len(rows)
            print(f"Copied {table}: {len(rows)}", flush=True)

        target.commit()
        transaction_started = False
        print("\nMIGRATION SUCCESSFUL", flush=True)
        print("Total records copied:", sum(copied.values()), flush=True)
        print("Original SQLite file and uploads folder were not changed.", flush=True)
        return 0

    except Exception as exc:
        if target is not None and transaction_started:
            try:
                target.rollback()
            except Exception:
                pass
        print("\nMIGRATION FAILED", flush=True)
        print(f"{type(exc).__name__}: {exc}", flush=True)
        return 1
    finally:
        if cur is not None:
            try: cur.close()
            except Exception: pass
        if target is not None:
            try: target.close()
            except Exception: pass
        if source is not None:
            source.close()


if __name__ == "__main__":
    raise SystemExit(main())
