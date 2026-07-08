"""
Central DB access for the RockAuto pipeline.
Mirrors config/config.php: XAMPP MariaDB on 127.0.0.1:3307, db 'supreme_parts',
user 'root', empty password. Override via env (SP_DB_HOST, SP_DB_PORT, SP_DB_NAME,
SP_DB_USER, SP_DB_PASS) so the same code runs in CI / other machines.
"""
from __future__ import annotations
import os
import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    "host": os.getenv("SP_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("SP_DB_PORT", "3307")),
    "user": os.getenv("SP_DB_USER", "root"),
    "password": os.getenv("SP_DB_PASS", ""),
    "database": os.getenv("SP_DB_NAME", "supreme_parts"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}


def connect() -> "pymysql.connections.Connection":
    """Return a new autocommit=False connection. Caller manages commit/close."""
    return pymysql.connect(**DB_CONFIG)


def ping() -> bool:
    """Cheap connectivity check used by smoke tests."""
    try:
        conn = connect()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[db] connection failed: {exc}")
        return False


if __name__ == "__main__":
    print("DB reachable:", ping())
