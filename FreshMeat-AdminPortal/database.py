import os
import re
from pathlib import Path

import mysql.connector
from mysql.connector.errors import Error as MySQLError


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def _load_local_env():
    """
    Load simple KEY=VALUE settings from the project's .env file.
    Existing OS environment variables take priority.
    """
    if not ENV_FILE.is_file():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


_load_local_env()


class HybridRow(dict):
    """
    Dictionary row that supports both row['column'] and row[0].
    The existing Flask routes use both SQLite row access styles.
    """

    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                key = tuple(self.keys())[key]
            except IndexError:
                raise IndexError("row index out of range") from None
        return super().__getitem__(key)


class CursorAdapter:
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    @staticmethod
    def _prepare_query(query, params):
        sql = query.strip()
        values = tuple(params or ())

        # SQLite PRAGMA table_info(table) -> MySQL information_schema query.
        pragma_match = re.fullmatch(
            r"PRAGMA\s+table_info\s*\(\s*([A-Za-z0-9_]+)\s*\)\s*;?",
            sql,
            flags=re.IGNORECASE,
        )
        if pragma_match:
            table_name = pragma_match.group(1)
            return (
                """
                SELECT
                    COLUMN_NAME AS name,
                    ORDINAL_POSITION AS cid,
                    DATA_TYPE AS type
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (table_name,),
            )

        # SQLite sqlite_master table lookup -> MySQL information_schema.
        if "sqlite_master" in sql.lower():
            return (
                """
                SELECT TABLE_NAME AS name
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_TYPE = 'BASE TABLE'
                  AND TABLE_NAME = %s
                """,
                values,
            )

        # MySQL uses CHAR instead of SQLite's TEXT cast target.
        sql = re.sub(
            r"CAST\s*\((.*?)\s+AS\s+TEXT\s*\)",
            r"CAST(\1 AS CHAR)",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # The current app uses SQLite ? placeholders. Convert them to MySQL %s.
        sql = sql.replace("?", "%s")
        return sql, values

    def execute(self, query, params=None):
        sql, values = self._prepare_query(query, params)
        self._cursor.execute(sql, values)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return HybridRow(row) if row is not None else None

    def fetchall(self):
        return [HybridRow(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        return [HybridRow(row) for row in rows]

    def close(self):
        self._cursor.close()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def description(self):
        return self._cursor.description

    def __iter__(self):
        for row in self._cursor:
            yield HybridRow(row)


class ConnectionAdapter:
    def __init__(self, raw_connection):
        self._connection = raw_connection

    def execute(self, query, params=None):
        raw_cursor = self._connection.cursor(dictionary=True, buffered=True)
        cursor = CursorAdapter(raw_cursor)
        try:
            cursor.execute(query, params)
            return cursor
        except Exception:
            cursor.close()
            raise

    def cursor(self):
        raw_cursor = self._connection.cursor(dictionary=True, buffered=True)
        return CursorAdapter(raw_cursor)

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


def get_db_connection():
    """
    Open a MySQL connection to freshmeet_db.

    Put the password in the local .env file. Do not upload .env or commit it
    to GitHub. use_pure=True avoids the native connector crash seen earlier.
    """
    password = os.environ.get("MYSQL_PASSWORD")
    if not password or password == "PUT_YOUR_MYSQL_PASSWORD_HERE":
        raise RuntimeError(
            "MySQL password is not configured. Create a .env file in the "
            "FRESHMEET project folder and set MYSQL_PASSWORD."
        )

    try:
        raw_connection = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "root"),
            password=password,
            database=os.environ.get("MYSQL_DATABASE", "freshmeet_db"),
            charset="utf8mb4",
            use_pure=True,
            connection_timeout=10,
            autocommit=False,
        )
    except (MySQLError, ValueError) as error:
        raise RuntimeError(
            "Could not connect to MySQL. Check that MySQL Server is running "
            "and that MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, "
            "and MYSQL_DATABASE in .env are correct. Original error: "
            f"{error}"
        ) from error

    return ConnectionAdapter(raw_connection)


def init_db():
    """
    Validate the existing MySQL schema without dropping or recreating tables.
    The schema and records were already migrated into freshmeet_db.
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT TABLE_NAME AS name
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_TYPE = 'BASE TABLE'
            """
        ).fetchall()

        existing = {row["name"].lower() for row in rows}
        required = {
            "admins",
            "customers",
            "sellers",
            "riders",
            "products",
            "orders",
            "notifications",
            "payments",
            "complaints",
        }
        missing = sorted(required - existing)

        if missing:
            raise RuntimeError(
                "Required FreshMeet MySQL tables are missing: "
                + ", ".join(missing)
            )
    finally:
        conn.close()

    print("FreshMeet MySQL database verified successfully!")
