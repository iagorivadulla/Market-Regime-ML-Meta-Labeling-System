import pandas as pd
import sqlalchemy as db

def final_db():
    engine = db.create_engine('sqlite:///../raw/data.db')

    stocks = pd.read_sql('SELECT * FROM stocks_processed', con=engine)
    fed = pd.read_sql('SELECT * FROM macro_processed', con=engine)
    events = pd.read_sql('SELECT * FROM events_processed', con=engine)
    event_day = pd.read_sql('SELECT * FROM events_countdown', con=engine)

    df = pd.concat([events, fed, stocks, event_day], axis=1, sort=True).dropna(how='any')

    return df