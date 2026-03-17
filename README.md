# BTC Dashboard

A simple Python project that collects Bitcoin price data, stores it in SQLite, and analyzes it.

## Project Overview

This project demonstrates a basic data pipeline:

1. Fetch Bitcoin price from an API
2. Store the data in a SQLite database
3. Analyze the stored data
4. (Later) Visualize the data with a dashboard

## Project Structure

```
btc-dashboard
│
├ data/                 # SQLite database
│   └ btc_data.db
│
├ src/
│   ├ fetch_data.py     # Fetch BTC price from API
│   ├ database.py       # Database connection and insert logic
│   └ analyze.py        # Read and analyze stored data
│
├ app.py                # Dashboard (planned)
├ requirements.txt      # Python dependencies
└ README.md
```

## How to Run

### 1. Install dependencies

```
pip install -r requirements.txt
```

or

```
pip install requests pandas
```

### 2. Fetch Bitcoin price

```
python src/fetch_data.py
```

This will:
- Call the CoinGecko API
- Get the BTC price
- Save it to the SQLite database

### 3. Analyze stored data

```
python src/analyze.py
```

This reads the stored BTC price data from the database.

## Technologies Used

- Python
- Requests
- SQLite
- Pandas

## Future Improvements

- Streamlit dashboard
- Price trend visualization
- Automatic periodic data collection
