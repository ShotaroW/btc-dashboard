import sqlite3
import time
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
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
USDJPY_URL = "https://api.exchangerate.host/convert?from=USD&to=JPY"
USDJPY_FALLBACK_URL = "https://open.er-api.com/v6/latest/USD"
HISTORICAL_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
FETCH_INTERVAL_SECONDS = 60
RATE_LIMIT_RETRY_SECONDS = 5


def ensure_table_exists():
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
    conn.commit()
    conn.close()


def fetch_btc_price():
    ticker_response = requests.get(BINANCE_TICKER_URL, timeout=10)
    ticker_response.raise_for_status()
    ticker_data = ticker_response.json()
    btc_usdt = float(ticker_data["price"])

    usd_jpy = None
    fx_errors = []

    try:
        fx_response = requests.get(USDJPY_URL, timeout=10)
        fx_response.raise_for_status()
        fx_data = fx_response.json()

        if "result" in fx_data and fx_data["result"] is not None:
            usd_jpy = float(fx_data["result"])
        elif "info" in fx_data and isinstance(fx_data["info"], dict) and "quote" in fx_data["info"]:
            usd_jpy = float(fx_data["info"]["quote"])
        elif "rates" in fx_data and isinstance(fx_data["rates"], dict) and "JPY" in fx_data["rates"]:
            usd_jpy = float(fx_data["rates"]["JPY"])
        else:
            fx_errors.append(f"Unexpected exchangerate.host response: {fx_data}")
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        fx_errors.append(f"exchangerate.host failed: {e}")

    if usd_jpy is None:
        try:
            fallback_response = requests.get(USDJPY_FALLBACK_URL, timeout=10)
            fallback_response.raise_for_status()
            fallback_data = fallback_response.json()

            if (
                isinstance(fallback_data, dict)
                and fallback_data.get("result") == "success"
                and "rates" in fallback_data
                and "JPY" in fallback_data["rates"]
            ):
                usd_jpy = float(fallback_data["rates"]["JPY"])
            else:
                fx_errors.append(f"Unexpected fallback FX response: {fallback_data}")
        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            fx_errors.append(f"fallback FX API failed: {e}")

    if usd_jpy is None:
        raise RuntimeError("USD/JPY の取得に失敗しました: " + " | ".join(fx_errors))

    price_jpy = btc_usdt * usd_jpy
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return timestamp, float(price_jpy)


def fetch_latest_price_with_cache():
    last_fetch_time = st.session_state.get("last_fetch_time", 0.0)
    cached_price = st.session_state.get("latest_price")

    if cached_price is not None and time.time() - last_fetch_time < FETCH_INTERVAL_SECONDS:
        return cached_price

    try:
        latest_price = fetch_btc_price()
        st.session_state["latest_price"] = latest_price
        st.session_state["last_fetch_time"] = time.time()
        st.session_state["last_fetch_failed"] = False
        return latest_price
    except (requests.exceptions.RequestException, RuntimeError):
        st.session_state["last_fetch_failed"] = True
        if cached_price is not None:
            return cached_price
        time.sleep(RATE_LIMIT_RETRY_SECONDS)
        latest_price = fetch_btc_price()
        st.session_state["latest_price"] = latest_price
        st.session_state["last_fetch_time"] = time.time()
        st.session_state["last_fetch_failed"] = False
        return latest_price


def save_price(timestamp, price_jpy):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM btc_price WHERE timestamp = ? LIMIT 1",
        (timestamp,),
    )
    exists = cur.fetchone()

    if not exists:
        cur.execute(
            "INSERT INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
            (timestamp, price_jpy),
        )
        conn.commit()

    conn.close()


def save_bulk_data(records):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.executemany(
        "INSERT INTO btc_price (timestamp, price_jpy) VALUES (?, ?)",
        records,
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


def fetch_historical_data(days=7):
    try:
        response = requests.get(
            HISTORICAL_URL,
            params={"vs_currency": "jpy", "days": days},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        records = []
        seen = set()

        for ts, price in prices:
            dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
            if dt not in seen:
                seen.add(dt)
                records.append((dt, float(price)))

        return records

    except requests.exceptions.HTTPError as e:
        response = e.response
        if response is not None and response.status_code == 429:
            print("⚠ 履歴データ取得でレート制限。スキップします")
            return []
        raise


def bootstrap_historical_data_if_needed():
    existing_df = load_data()

    # 一度だけ実行（セッションで制御）
    if existing_df.empty and not st.session_state.get("historical_loaded"):
        records = fetch_historical_data(days=7)
        if records:
            save_bulk_data(records)
        st.session_state["historical_loaded"] = True


st.set_page_config(page_title="BTC Price Dashboard", layout="wide")

refresh_count = st_autorefresh(
    interval=60 * 1000,
    key="btc_refresh",
    debounce=False,
)

ensure_table_exists()
bootstrap_historical_data_if_needed()

timestamp, price = fetch_latest_price_with_cache()
save_price(timestamp, price)

df = load_data()

range_option = st.radio(
    "表示期間",
    ["1時間", "1日", "1週間"],
    horizontal=True,
)

latest_time = df["timestamp"].max() if not df.empty else None

if latest_time is not None:
    if range_option == "1時間":
        filtered_df = df[df["timestamp"] >= latest_time - pd.Timedelta(hours=1)].copy()
    elif range_option == "1日":
        filtered_df = df[df["timestamp"] >= latest_time - pd.Timedelta(days=1)].copy()
    else:
        filtered_df = df[df["timestamp"] >= latest_time - pd.Timedelta(days=7)].copy()
else:
    filtered_df = df.copy()

st.title("BTC Price Dashboard")
st.write("Bitcoin price history")
st.write(f"Latest price: {price:,.0f} JPY")
st.write(f"Last updated: {timestamp}")

if st.session_state.get("last_fetch_failed"):
    st.info("最新価格の取得に失敗したため、直近の取得済みデータを表示しています。")

if len(filtered_df) >= 2:
    nearest = alt.selection_point(
        nearest=True,
        on="mouseover",
        fields=["timestamp"],
        empty=False,
    )

    base = alt.Chart(filtered_df).encode(
        x=alt.X("timestamp:T", title="Time"),
        y=alt.Y(
            "price_jpy:Q",
            title="Price (JPY)",
            scale=alt.Scale(zero=False, nice=True),
        ),
    )

    line = base.mark_line(
        color="#8fd3ff",
        strokeWidth=3,
    )

    selectors = alt.Chart(filtered_df).mark_point(opacity=0).encode(
        x="timestamp:T",
        tooltip=[
            alt.Tooltip("timestamp:T", title="Time", format="%Y-%m-%d %H:%M:%S"),
            alt.Tooltip("price_jpy:Q", title="Price (JPY)", format=",.0f"),
        ],
    ).add_params(nearest)

    points = base.mark_circle(
        color="#8fd3ff",
        size=90,
    ).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0))
    )

    chart = alt.layer(
        line,
        selectors,
        points,
    ).properties(height=450).interactive()

    st.altair_chart(chart, use_container_width=True)
else:
    st.warning(f"{range_option} の表示に必要なデータがまだ少ないです。60秒ごとに自動更新されます。")
