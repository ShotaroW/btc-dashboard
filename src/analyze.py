import sqlite3
import pandas as pd

DB_NAME = "data/btc_data.db"

conn = sqlite3.connect(DB_NAME)

df = pd.read_sql_query(
    "SELECT * FROM btc_price ORDER BY timestamp DESC",
    conn
)

print(df)

conn.close()