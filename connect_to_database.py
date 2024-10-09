import sqlite3

# функция для подключения к бд.
def connect_to_database():
    try:
        conn = sqlite3.connect('database/time_tracking.db')
        cursor = conn.cursor()
        return conn, cursor
    except sqlite3.Error as e:
        return None, None