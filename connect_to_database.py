import sqlite3
from contextlib import contextmanager
from config import DATABASE_PATH
import logging

# функция для подключения к бд.
@contextmanager
def database_connection():
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        yield conn, cursor
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

# Usage example:
# with database_connection() as (conn, cursor):
#     cursor.execute("SELECT * FROM users")
#     users = cursor.fetchall()
