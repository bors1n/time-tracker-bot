import sqlite3

def create_tables():
    # Подключение к базе данных SQLite
    conn = sqlite3.connect('database/time_tracking.db', check_same_thread=False)
    cursor = conn.cursor()

    # Создаем таблицы, если их нет
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        project_name TEXT
    );
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS time_tracking (
        tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        project_id INTEGER,
        start_time REAL,
        end_time REAL,
        total_pause_time REAL,
        total_work_time REAL
    );
    ''')
    conn.commit()
    conn.close()