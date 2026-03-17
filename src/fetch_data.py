import requests

url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=jpy"

response = requests.get(url, timeout=10)
response.raise_for_status()

data = response.json()
price = data["bitcoin"]["jpy"]

print(price)