import os
import sqlite3

import pandas as pd

DB_NAME = "data/btc_data.db"


def ensure_table_exists():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS btc_price (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL UNIQUE,
                price_jpy REAL NOT NULL
            )
            """
        )


def save_price(timestamp, price_jpy):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
            (timestamp, price_jpy),
        )


def save_bulk_data(records):
    with sqlite3.connect(DB_NAME) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
            records,
        )


def load_data():
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM btc_price ORDER BY timestamp",
            conn,
        )
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
