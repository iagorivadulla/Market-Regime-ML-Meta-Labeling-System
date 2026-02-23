import fredapi
from dotenv import load_dotenv
import os
import pandas as pd
import sqlalchemy as db
from sqlalchemy import text

'''
to get a free api key go to https://fredaccount.stlouisfed.org/apikey
'''

def get_data(serie):
    '''
    Process and store in the db the indicator
    '''

    # Approximate fixed lags in days from value date to publication as FREDAPI doesn't offers real publish dates for old publications
    rate_lags = {
        'UNRATE': 45,  # ~6 weeks after reference month end
        'CPIAUCSL': 15,  # ~2 weeks after reference month end
        'M2SL': 30,
        'WALCL': 7,
        'NFCI': 7,
        'ICSA': 5,  # Thursdays, covers prior week
    }

    # creates the database engine
    engine = db.create_engine('sqlite:///data.db')

    # uploads the api key from .env
    load_dotenv()
    api_key = os.getenv("API_KEY")

    # loads the api key
    fred = fredapi.Fred(api_key)

    #get the data
    data = fred.get_series(serie)
    #drop nan values
    data = data.dropna()

    if serie in rate_lags:
        data.index = data.index + pd.DateOffset(days=rate_lags[serie])

    # convert Series to DataFrame
    data = data.reset_index()
    data.columns = ['date', 'value']

    # remove timezone info
    data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)

    # add series name
    data['serie'] = serie

    #get last day registered in the db
    with engine.connect() as conn:
        result = conn.execute(text((f'SELECT MAX(date) FROM Macro WHERE serie = "{serie}"')))
        last_date = result.scalar() #scalar returns one single value

    if last_date:
        last_date = pd.to_datetime(last_date).normalize()
        data = data[data['date'].dt.normalize() > last_date]

    if data.empty:
        print(f'No data found for {serie}')
        return None

    with engine.connect() as conn:
        data[['date', 'value', 'serie']].to_sql('Macro', conn, if_exists='append', index=False)
        conn.commit()
        print(f'{serie}: {len(data)} files created')

def get_fed_data():
    indicators = [
        # Interest rates and monetary policy
        'FEDFUNDS',  # Effective Fed Funds Rate
        'DFF',  # Daily Fed Funds Rate
        'T10Y2Y',  # 10Y-2Y spread (yield curve)
        'T10Y3M',  # 10Y-3M spread (curve inversion)
        'GS10',  # 10Y Treasury yield
        'GS2',  # 2Y Treasury yield

        # Financial conditions and credit
        'BAMLH0A0HYM2',  # High Yield OAS spread
        'BAMLC0A0CM',  # Investment Grade OAS spread
        'NFCI',  # Chicago Fed National Financial Conditions Index

        # Macro / economic activity
        'UNRATE',  # Unemployment rate
        'CPIAUCSL',  # CPI inflation
        'T5YIE',  # 5Y breakeven inflation
        'T10YIE',  # 10Y breakeven inflation
        'ICSA',  # Weekly jobless claims

        # Liquidity and Fed balance sheet
        'WALCL',  # Fed total assets
        'M2SL',  # M2 money supply

        # Sentiment / money market
        'SOFR',  # Secured Overnight Financing Rate
        'TEDRATE',  # TED spread
    ]


    for serie in indicators:
        get_data(serie)



if __name__ == '__main__':

    #first creation of the macro table
    get_fed_data()
