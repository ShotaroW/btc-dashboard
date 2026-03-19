import pandas as pd
from prophet import Prophet  # type: ignore[import-untyped]


def predict_price(df: pd.DataFrame, periods: int = 24) -> pd.DataFrame:
    """
    過去の価格データからProphetで24時間先を予測する。
    戻り値: ds, yhat, yhat_lower, yhat_upper の DataFrame（空の場合はデータ不足）
    """
    if df.empty:
        return pd.DataFrame()

    # データを1時間足にリサンプリングして頻度を統一する
    df_hourly = (
        df.set_index("timestamp")["price_jpy"]
        .resample("h")
        .last()
        .dropna()
        .reset_index()
        .rename(columns={"timestamp": "ds", "price_jpy": "y"})
    )

    if len(df_hourly) < 10:
        return pd.DataFrame()

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=False,
        yearly_seasonality=False,
        changepoint_prior_scale=0.1,
    )
    model.fit(df_hourly)

    future = model.make_future_dataframe(periods=periods, freq="h")
    forecast = model.predict(future)

    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
