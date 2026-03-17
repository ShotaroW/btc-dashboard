import requests
from datetime import datetime
from database import create_table, insert_price

url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=jpy"

response = requests.get(url, timeout=10)
response.raise_for_status()

data = response.json()
price = data["bitcoin"]["jpy"]
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

create_table()
insert_price(timestamp, price)

print(f"{timestamp} に {price} 円 を保存しました")