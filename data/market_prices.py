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
engine = db.create_engine('sqlite:///data.db')


def get_info(ticker, period = 'max'):
    #get data from ticker and period
    stock = yf.Ticker(ticker)

    if period == 'max':
        data = stock.history(period=period, interval='1d')  # gets 1d interval historic data
    else:
        data = stock.history(start=period, interval='1d')
    # create the col for the ticker in the db
    data['ticker'] = ticker
    # reset the index
    data = data.reset_index()
    #delete timezone
    data['Date'] = data['Date'].dt.tz_localize(None)
    # rename the columns in dataframe to match with the db
    data.rename(
        columns={'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'},
        inplace=True)

    #get last date registered in the db
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT MAX(date) FROM Stocks WHERE ticker = "{ticker}"'))
        last_date = result.scalar() #scalar() returns one single value

    #avoid duplicated data using last date
    if last_date:
        last_date = pd.to_datetime(last_date).normalize()
        data = data[data['date'].dt.normalize() > last_date]

    if data.empty:
        print('No data for ' + ticker)
        return None

    with engine.connect() as conn:
        data[['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']].to_sql(
            'Stocks', conn, if_exists='append', index=False)
        conn.commit()
        print(f'{ticker}: {len(data)} files created')


def get_market_prices():
    #list with the tickers names
    tickers = ['SPY', 'QQQ', '^VIX', 'DX-Y.NYB', 'GC=F']

    for ticker in tickers:
        get_info(ticker)
        print(f'{ticker} data retrieved')


#first iteration to get all data
if __name__ == '__main__':
    get_market_prices()


