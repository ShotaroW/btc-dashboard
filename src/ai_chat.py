import ollama
import pandas as pd

MODEL = "qwen2.5:14b"

SYSTEM_PROMPT = """\
あなたはBitcoin価格ダッシュボードのAIアシスタントです。
以下のリアルタイムデータをもとに、ユーザーの質問に日本語で簡潔に答えてください。
投資アドバイスや将来の価格予測は行わず、データの傾向や事実の説明に留めてください。

【ダッシュボードの現在のデータ】
{context}\
"""


def build_context(df: pd.DataFrame, range_label: str, current_price: float | None) -> str:
    if current_price is None:
        return "現在の価格データを取得できていません。"

    if df.empty:
        return f"現在のBTC価格: {current_price:,.0f}円（履歴データなし）"

    price_min = df["price_jpy"].min()
    price_max = df["price_jpy"].max()
    price_first = df["price_jpy"].iloc[0]
    price_last = df["price_jpy"].iloc[-1]
    change_pct = (price_last - price_first) / price_first * 100

    return (
        f"表示期間: {range_label}\n"
        f"現在価格: {current_price:,.0f}円\n"
        f"期間高値: {price_max:,.0f}円\n"
        f"期間安値: {price_min:,.0f}円\n"
        f"期間騰落率: {change_pct:+.2f}%\n"
        f"データ件数: {len(df)}件"
    )


def explain_prediction(current_price: float, forecast_df: pd.DataFrame) -> str:
    last = forecast_df.iloc[-1]
    change_pct = (last["yhat"] - current_price) / current_price * 100

    prompt = (
        f"現在のBTC価格: {current_price:,.0f}円\n"
        f"Prophetによる24時間後の予測:\n"
        f"  予測価格: {last['yhat']:,.0f}円\n"
        f"  予測上限: {last['yhat_upper']:,.0f}円\n"
        f"  予測下限: {last['yhat_lower']:,.0f}円\n"
        f"  変化率: {change_pct:+.2f}%\n\n"
        "この予測結果を2〜3文でわかりやすく解説してください。"
        "最後に「あくまで統計的な予測であり、投資判断の根拠にはなりません」と添えてください。"
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": "あなたはBitcoin価格ダッシュボードのAIアシスタントです。日本語で答えてください。"},
            {"role": "user", "content": prompt},
        ],
    )
    return response["message"]["content"]


def stream_ai_response(messages: list, context: str):
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            *messages,
        ],
        stream=True,
    )
    for chunk in response:
        yield chunk["message"]["content"]
