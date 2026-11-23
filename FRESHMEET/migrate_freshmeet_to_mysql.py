"""Safely copy FreshMeet SQLite records into the existing MySQL database.

Place this file beside freshmeet_admin.db in the FRESHMEET project folder,
then run: py migrate_freshmeet_to_mysql.py
"""

from pathlib import Path
import getpass
import sqlite3
import sys

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("MySQL Python connector is not installed.")
    print("Install it with: py -m pip install mysql-connector-python")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
SQLITE_FILE = BASE_DIR / "freshmeet_admin.db"
MYSQL_DATABASE = "freshmeet_db"

# Parent tables must be copied before tables that reference them.
TABLES = [
    "admins",
    "customers",
    "sellers",
    "riders",
    "products",
    "orders",
    "payments",
    "complaints",
    "notifications",
]


def main():
    if not SQLITE_FILE.is_file():
        print(f"ERROR: Could not find {SQLITE_FILE}")
        print("Keep this script in the same folder as freshmeet_admin.db.")
        return 1

    print("FreshMeet SQLite to MySQL migration")
    print(f"Source file: {SQLITE_FILE}")
    print(f"Target database: {MYSQL_DATABASE}")
    print("MySQL password is requested privately; it will not be saved in this file.")
    password = getpass.getpass("Enter MySQL root password: ")

    sqlite_conn = None
    mysql_conn = None
    cursor = None

    try:
        sqlite_conn = sqlite3.connect(str(SQLITE_FILE))
        sqlite_conn.row_factory = sqlite3.Row
        integrity = sqlite_conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")

        mysql_conn = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password=password,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
        )
        cursor = mysql_conn.cursor()

        # Ensure all expected destination tables exist and have matching columns.
        for table in TABLES:
            source_columns = [row["name"] for row in sqlite_conn.execute(f'PRAGMA table_info("{table}")')]
            if not source_columns:
                raise RuntimeError(f"Source table '{table}' was not found in SQLite.")

            cursor.execute(f"SHOW COLUMNS FROM `{table}`")
            target_columns = {row[0] for row in cursor.fetchall()}
            missing = [column for column in source_columns if column not in target_columns]
            if missing:
                raise RuntimeError(
                    f"MySQL table '{table}' is missing columns: {', '.join(missing)}. "
                    "No records have been copied."
                )

        # Stop if the destination already contains data; this prevents duplicates.
        existing_counts = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            existing_counts[table] = count
        non_empty = {table: count for table, count in existing_counts.items() if count != 0}
        if non_empty:
            details = ", ".join(f"{table}={count}" for table, count in non_empty.items())
            raise RuntimeError(
                "The MySQL destination is not empty (" + details + "). "
                "To avoid duplicates or overwriting data, migration was stopped."
            )

        # Add the SQLite riders.email UNIQUE rule if it has not already been added.
        cursor.execute("SHOW INDEX FROM `riders` WHERE Key_name = 'riders_email'")
        if not cursor.fetchall():
            cursor.execute("ALTER TABLE `riders` ADD CONSTRAINT `riders_email` UNIQUE (`email`)")

        mysql_conn.start_transaction()
        copied_counts = {}

        for table in TABLES:
            source_columns = [row["name"] for row in sqlite_conn.execute(f'PRAGMA table_info("{table}")')]
            quoted_columns = ", ".join(f"`{column}`" for column in source_columns)
            placeholders = ", ".join(["%s"] * len(source_columns))
            insert_sql = f"INSERT INTO `{table}` ({quoted_columns}) VALUES ({placeholders})"

            rows = sqlite_conn.execute(f'SELECT * FROM "{table}"').fetchall()
            if rows:
                values = [tuple(row[column] for column in source_columns) for row in rows]
                cursor.executemany(insert_sql, values)
            copied_counts[table] = len(rows)

        mysql_conn.commit()

        print("\nMigration completed successfully!")
        print("Records copied:")
        for table in TABLES:
            print(f"  {table}: {copied_counts[table]}")
        print(f"Total records copied: {sum(copied_counts.values())}")
        print("\nThe original freshmeet_admin.db file was not changed or deleted.")
        print("The uploads folder was not changed.")
        return 0

    except Exception as exc:
        if mysql_conn is not None and mysql_conn.is_connected():
            mysql_conn.rollback()
        print("\nMIGRATION STOPPED. Any uncommitted MySQL inserts were rolled back.")
        print(f"Reason: {exc}")
        return 1

    finally:
        if cursor is not None:
            cursor.close()
        if mysql_conn is not None and mysql_conn.is_connected():
            mysql_conn.close()
        if sqlite_conn is not None:
            sqlite_conn.close()


if __name__ == "__main__":
    sys.exit(main())
