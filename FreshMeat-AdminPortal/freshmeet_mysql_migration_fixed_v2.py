"""Safely copy FreshMeet rows from freshmeet_admin.db into MySQL freshmeet_db.

Place this file beside freshmeet_admin.db and run:
    py freshmeet_mysql_migration_fixed_v2.py

The script never deletes or modifies the SQLite source. It only inserts into
MySQL when all nine destination tables are empty. It preserves primary-key IDs.
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
    "admins", "customers", "sellers", "riders", "products",
    "orders", "payments", "complaints", "notifications",
]


def main() -> int:
    print("FreshMeet SQLite -> MySQL migration", flush=True)
    print(f"Source: {SQLITE_FILE}", flush=True)
    print(f"Target: {MYSQL_DATABASE}", flush=True)

    if not SQLITE_FILE.is_file():
        print("ERROR: freshmeet_admin.db is not in this folder.", flush=True)
        return 1

    password = getpass.getpass("Enter MySQL root password: ")
    if not password:
        print("ERROR: Password was empty. Run the script again and type your password.", flush=True)
        return 1

    source = None
    target = None
    cursor = None
    try:
        print("Checking SQLite source...", flush=True)
        source = sqlite3.connect(str(SQLITE_FILE))
        source.row_factory = sqlite3.Row
        integrity = source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        # Read all source table definitions and rows before writing anything.
        source_columns_by_table = {}
        source_rows_by_table = {}
        for table in TABLES:
            info = source.execute(f'PRAGMA table_info("{table}")').fetchall()
            columns = [row["name"] for row in info]
            if not columns:
                raise RuntimeError(f"Source table is missing: {table}")
            source_columns_by_table[table] = columns
            source_rows_by_table[table] = source.execute(
                f'SELECT * FROM "{table}"'
            ).fetchall()

        print("Connecting to MySQL (Pure Python mode)...", flush=True)
        target = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password=password,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            use_pure=True,
            connection_timeout=10,
        )
        print("MySQL connection successful.", flush=True)
        cursor = target.cursor()

        # Confirm every SQLite column exists in the already-created MySQL tables.
        for table in TABLES:
            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            target_columns = {row[0] for row in cursor.fetchall()}
            missing = [col for col in source_columns_by_table[table] if col not in target_columns]
            if missing:
                raise RuntimeError(
                    f"MySQL table {table} is missing column(s): {', '.join(missing)}"
                )

        # Preserve SQLite's UNIQUE constraint on riders.email, without adding it twice.
        cursor.execute("SHOW INDEX FROM `riders`")
        indexes = cursor.fetchall()
        has_unique_email = any(
            int(row[1]) == 0 and str(row[4]).lower() == "email"
            for row in indexes
        )
        if not has_unique_email:
            print("Adding UNIQUE constraint to riders.email...", flush=True)
            cursor.execute(
                "ALTER TABLE `riders` ADD CONSTRAINT `riders_email` UNIQUE (`email`)"
            )
            target.commit()  # ALTER TABLE performs an implicit commit in MySQL.

        # Do not insert into an already-populated destination (prevents duplicates).
        existing_counts = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            existing_counts[table] = int(cursor.fetchone()[0])
        occupied = {table: count for table, count in existing_counts.items() if count > 0}
        if occupied:
            details = ", ".join(f"{table}={count}" for table, count in occupied.items())
            raise RuntimeError(
                "Destination is not empty; no rows were copied. Existing counts: " + details
            )

        # Important: do not call start_transaction() here. Connector/Python may
        # already have an implicit transaction after the preflight SELECTs.
        # Commit preflight work, then let the first INSERT open the transaction.
        target.commit()
        copied = {}
        print("Copying records...", flush=True)

        for table in TABLES:
            columns = source_columns_by_table[table]
            rows = source_rows_by_table[table]
            if rows:
                col_sql = ", ".join(f"`{column}`" for column in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                insert_sql = f"INSERT INTO `{table}` ({col_sql}) VALUES ({placeholders})"
                values = [tuple(row[column] for column in columns) for row in rows]
                cursor.executemany(insert_sql, values)
            copied[table] = len(rows)
            print(f"Copied {table}: {len(rows)} record(s)", flush=True)

        target.commit()

        print("\nMIGRATION SUCCESSFUL", flush=True)
        print("Records copied:", sum(copied.values()), flush=True)
        for table in TABLES:
            print(f"  {table}: {copied[table]}", flush=True)
        print("Original SQLite database and uploads folder were not changed.", flush=True)
        return 0

    except Exception as exc:
        if target is not None:
            try:
                target.rollback()
            except Exception:
                pass
        print("\nMIGRATION FAILED", flush=True)
        print(f"{type(exc).__name__}: {exc}", flush=True)
        print("The original SQLite database was not changed.", flush=True)
        return 1
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if target is not None:
            try:
                target.close()
            except Exception:
                pass
        if source is not None:
            source.close()


if __name__ == "__main__":
    raise SystemExit(main())
