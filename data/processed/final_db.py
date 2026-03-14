import pandas as pd
import sqlalchemy as db

def final_db(engine):
    #engine = db.create_engine('sqlite:///../raw/data.db')

    stocks = pd.read_sql('SELECT * FROM stocks_processed', engine)
    fed = pd.read_sql('SELECT * FROM macro_processed', engine)
    events = pd.read_sql('SELECT * FROM events_processed', engine)
    event_day = pd.read_sql('SELECT * FROM events_countdown', engine)

    for df_temp in (stocks, fed, events, event_day):
        df_temp['date'] = pd.to_datetime(df_temp['date'])
        df_temp.set_index('date', inplace=True)

    df = pd.concat([events, fed, stocks, event_day], axis=1).dropna()

    return df