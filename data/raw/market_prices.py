import yfinance as yf
import sqlalchemy as db
from sqlalchemy import text
import pandas as pd

'''
Downloads data from:
#SPY (S&P500 INDEX)
#QQQ (NASDAQ)
#^VIX (VOLATILITY)
#DX-Y.NYB (DOLLAR INDEX)
#GC=F (GOLD FUTURES)
'''

#creates the database engine
#engine = db.create_engine('sqlite:///../data/raw/data.db')


def get_info(ticker, engine, period='max'):
    # --- Download ---
    try:
        stock = yf.Ticker(ticker)
        if period == 'max':
            data = stock.history(period=period, interval='1d')
        else:
            data = stock.history(start=period, interval='1d')
    except KeyError as e:
        print(f'[{ticker}] Yahoo Finance returned an unexpected response (KeyError: {e}). '
              f'Try updating yfinance: pip install --upgrade yfinance')
        return None
    except Exception as e:
        print(f'[{ticker}] Failed to download data: {e}')
        return None

    if data.empty:
        print(f'[{ticker}] No data returned — ticker may be invalid or delisted.')
        return None

    # --- Transform ---
    data['ticker'] = ticker
    data = data.reset_index()
    data['Date'] = data['Date'].dt.tz_localize(None)
    data.rename(
        columns={'Date': 'date', 'Open': 'open', 'High': 'high',
                 'Low': 'low', 'Close': 'close', 'Volume': 'volume'},
        inplace=True)

    # --- Deduplication ---
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT MAX(date) FROM Stocks WHERE ticker = "{ticker}"'))
            last_date = result.scalar()
    except Exception as e:
        print(f'[{ticker}] Could not query last date from DB: {e}')
        return None

    if last_date:
        last_date = pd.to_datetime(last_date).normalize()
        data = data[data['date'].dt.normalize() > last_date]

    if data.empty:
        print(f'[{ticker}] Already up to date, no new rows to insert.')
        return None

    # --- Save ---
    try:
        with engine.connect() as conn:
            data[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']].to_sql(
                'Stocks', conn, if_exists='append', index=False)
            conn.commit()
        print(f'[{ticker}] {len(data)} rows inserted.')
    except Exception as e:
        print(f'[{ticker}] Failed to write to database: {e}')
        return None


def get_market_prices(engine):
    tickers = ['SPY', 'QQQ', '^VIX', 'DX-Y.NYB', 'GC=F']
    failed = []

    for ticker in tickers:
        print(f'Fetching {ticker}...')
        result = get_info(ticker, engine)
        if result is None and ticker not in ['SPY']:  # get_info prints its own reason
            failed.append(ticker)

    if failed:
        print(f'\nThe following tickers had issues: {failed}')


#first iteration to get all data
if __name__ == '__main__':
    engine = db.create_engine('sqlite:///../data/raw/data.db')
    get_market_prices(engine)