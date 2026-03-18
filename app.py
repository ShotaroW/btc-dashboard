import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = "data/btc_data.db"

conn = sqlite3.connect(DB_NAME)

df = pd.read_sql_query(
    "SELECT * FROM btc_price ORDER BY timestamp",
    conn
)

conn.close()

st.title("BTC Price Dashboard")

st.write("Bitcoin price history")

st.line_chart(df["price_jpy"])