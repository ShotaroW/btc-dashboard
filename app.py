import time

import altair as alt
import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.ai_chat import build_context, explain_prediction, stream_ai_response
from src.database import ensure_table_exists, load_data, save_bulk_data, save_price
from src.fetcher import fetch_btc_price, fetch_historical_data
from src.predictor import predict_price

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

FETCH_INTERVAL_SECONDS = 60


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
        raise


def bootstrap_historical_data_if_needed():
    existing_df = load_data()
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

try:
    timestamp, price = fetch_latest_price_with_cache()
    save_price(timestamp, price)
    fetch_error = False
except (requests.exceptions.RequestException, RuntimeError) as e:
    fetch_error = True
    timestamp, price = None, None

df = load_data()

range_option = st.radio(
    "表示期間",
    ["1日", "1週間"],
    horizontal=True,
)

latest_time = df["timestamp"].max() if not df.empty else None

if latest_time is not None:
    if range_option == "1日":
        filtered_df = df[df["timestamp"] >= latest_time - pd.Timedelta(days=1)].copy()
    else:
        filtered_df = df[df["timestamp"] >= latest_time - pd.Timedelta(days=7)].copy()
else:
    filtered_df = df.copy()

st.title("BTC Price Dashboard")
st.write("Bitcoin price history")

if fetch_error:
    st.error("価格の取得に失敗しました。ネットワーク接続を確認してください。")
else:
    st.write(f"最新価格: {price:,.0f} 円")
    st.write(f"最終更新: {timestamp}")

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

# --- 価格予測 ---
st.divider()
st.subheader("24時間価格予測")

if st.button("予測を実行"):
    with st.spinner("Prophetで予測中..."):
        forecast_df = predict_price(df)

    if forecast_df.empty:
        st.warning("予測に必要なデータが不足しています。しばらく待ってから再実行してください。")
    else:
        st.session_state["forecast_df"] = forecast_df
        if not fetch_error and price is not None:
            with st.spinner("AIが解説中..."):
                try:
                    explanation = explain_prediction(price, forecast_df)
                    st.session_state["forecast_explanation"] = explanation
                except Exception:
                    st.session_state["forecast_explanation"] = None

if "forecast_df" in st.session_state:
    forecast_df = st.session_state["forecast_df"]
    latest_ts = df["timestamp"].max()
    future_df = forecast_df[forecast_df["ds"] > latest_ts]

    hist_line = alt.Chart(df.tail(72)).mark_line(
        color="#8fd3ff", strokeWidth=2
    ).encode(
        x=alt.X("timestamp:T", title="Time"),
        y=alt.Y("price_jpy:Q", title="Price (JPY)", scale=alt.Scale(zero=False)),
    )

    forecast_line = alt.Chart(future_df).mark_line(
        color="#ffaa00", strokeWidth=2, strokeDash=[6, 3]
    ).encode(
        x="ds:T",
        y=alt.Y("yhat:Q", scale=alt.Scale(zero=False)),
    )

    band = alt.Chart(future_df).mark_area(
        color="#ffaa00", opacity=0.15
    ).encode(
        x="ds:T",
        y="yhat_lower:Q",
        y2="yhat_upper:Q",
    )

    st.altair_chart(
        (hist_line + band + forecast_line).properties(height=350).interactive(),
        use_container_width=True,
    )

    explanation = st.session_state.get("forecast_explanation")
    if explanation:
        st.info(explanation)

# --- AIチャット ---
st.divider()
st.subheader("AIに質問する")

if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = []

for msg in st.session_state["chat_messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("BTCについて質問してください（例：今の価格は高い？）"):
    st.session_state["chat_messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    context = build_context(filtered_df, range_option, price if not fetch_error else None)

    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(
                stream_ai_response(st.session_state["chat_messages"], context)
            )
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})
        except Exception:
            st.error("Ollamaに接続できませんでした。`ollama serve` が起動しているか確認してください。")
