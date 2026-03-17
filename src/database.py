import sqlite3

DB_NAME = "data/btc_data.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def create_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS btc_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            price_jpy REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def insert_price(timestamp, price_jpy):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
        (timestamp, price_jpy)
    )
    conn.commit()
    conn.close()