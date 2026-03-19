from datetime import datetime

import requests

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
USDJPY_URL = "https://api.exchangerate.host/convert?from=USD&to=JPY"
USDJPY_FALLBACK_URL = "https://open.er-api.com/v6/latest/USD"
HISTORICAL_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"


def fetch_btc_price():
    ticker_response = requests.get(BINANCE_TICKER_URL, timeout=10)
    ticker_response.raise_for_status()
    btc_usdt = float(ticker_response.json()["price"])

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
        if e.response is not None and e.response.status_code == 429:
            print("⚠ 履歴データ取得でレート制限。スキップします")
            return []
        raise
