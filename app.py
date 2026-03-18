import sqlite3
from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Streamlitの右上ツールバーを非表示
st.markdown(
    """
    <style>
    div[data-testid="stToolbar"] {
        visibility: hidden;
        height: 0;
        position: fixed;
    }
    button[title="View fullscreen"] {
        visibility: hidden;
    }
    .vega-embed summary {
        display: none !important;
    }
    .vega-actions {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

DB_NAME = "data/btc_data.db"
URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=jpy"


def fetch_btc_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    data = response.json()

    price_jpy = data["bitcoin"]["jpy"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return timestamp, float(price_jpy)


def save_price(timestamp, price_jpy):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS btc_price (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            price_jpy REAL NOT NULL
        )
        """
    )

    cur.execute(
        "INSERT INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
        (timestamp, price_jpy),
    )

    conn.commit()
    conn.close()


def load_data():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(
        "SELECT * FROM btc_price ORDER BY timestamp",
        conn,
    )
    conn.close()

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


st.set_page_config(page_title="BTC Price Dashboard", layout="wide")

refresh_count = st_autorefresh(
    interval=60 * 1000,
    key="btc_refresh",
    debounce=False,
)

timestamp, price = fetch_btc_price()
save_price(timestamp, price)

df = load_data()

st.title("BTC Price Dashboard")
st.write("Bitcoin price history")
st.write(f"Latest price: {price:,.0f} JPY")
st.write(f"Last updated: {timestamp}")

if len(df) >= 2:
    base = alt.Chart(df).encode(
        x=alt.X("timestamp:T", title="Time"),
        y=alt.Y("price_jpy:Q", title="Price (JPY)"),
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%Y-%m-%d %H:%M:%S"),
            alt.Tooltip("price_jpy:Q", title="Price (JPY)", format=",.0f"),
        ],
    )

    line = base.mark_line()
    points = base.mark_circle(size=70)

    chart = (line + points).interactive()
    st.altair_chart(chart, use_container_width=True)
else:
    st.warning("データがまだ少ないです。60秒ほど待つと自動で点が増えます。")
