import time
import yfinance as yf
import sqlalchemy as db
from sqlalchemy import text
import pandas as pd

'''
Downloads data from:
#SPY (S&P500 INDEX)
#QQQ (NASDAQ)
#^VIX (VOLATILITY)
#DX=F (DOLLAR INDEX FUTURES)
#GC=F (GOLD FUTURES)
'''

#creates the database engine
#engine = db.create_engine('sqlite:///../data/raw/data.db')


def get_info(ticker, engine, period='max'):
    """
    Returns:
        'inserted'   — new rows were written to the DB
        'up_to_date' — data exists but nothing new to add
        'error'      — something went wrong (download or DB failure)
    """
    # --- Download (with retry) ---
    max_retries = 3
    retry_delay = 5  # seconds between retries
    data = None

    for attempt in range(1, max_retries + 1):
        try:
            stock = yf.Ticker(ticker)
            if period == 'max':
                data = stock.history(period=period, interval='1d')
            else:
                data = stock.history(start=period, interval='1d')

            if data is not None and not data.empty:
                break  # success

            print(f'[{ticker}] Empty response on attempt {attempt}/{max_retries}, retrying in {retry_delay}s...')
        except KeyError as e:
            print(f'[{ticker}] Unexpected response (KeyError: {e}) on attempt {attempt}/{max_retries}. '
                  f'Try: pip install --upgrade yfinance')
        except Exception as e:
            print(f'[{ticker}] Download error on attempt {attempt}/{max_retries}: {e}')

        if attempt < max_retries:
            time.sleep(retry_delay)

    if data is None or data.empty:
        print(f'[{ticker}] Failed after {max_retries} attempts — skipping.')
        return 'error'

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
        return 'error'

    if last_date:
        last_date = pd.to_datetime(last_date).normalize()
        data = data[data['date'].dt.normalize() > last_date]

    if data.empty:
        print(f'[{ticker}] Already up to date, no new rows to insert.')
        return 'up_to_date'

    # --- Save ---
    try:
        with engine.connect() as conn:
            data[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']].to_sql(
                'Stocks', conn, if_exists='append', index=False)
            conn.commit()
        print(f'[{ticker}] {len(data)} rows inserted.')
        return 'inserted'
    except Exception as e:
        print(f'[{ticker}] Failed to write to database: {e}')
        return 'error'


def get_market_prices(engine):
    tickers = ['SPY', 'QQQ', '^VIX', 'DX-Y.NYB', 'GC=F']
    failed = []

    for ticker in tickers:
        print(f'Fetching {ticker}...')
        status = get_info(ticker, engine)
        if status == 'error':
            failed.append(ticker)

    if failed:
        print(f'\nThe following tickers had issues: {failed}')
    else:
        print('\nAll tickers fetched successfully.')


#first iteration to get all data
if __name__ == '__main__':
    engine = db.create_engine('sqlite:///../data/raw/data.db')
    get_market_prices(engine)